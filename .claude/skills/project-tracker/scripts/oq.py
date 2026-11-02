#!/usr/bin/env python3
"""Edit a project's open questions, which live in the Yard site's shared store.

The site's Questions page and this script edit the same keys, one per question
(`oq.<slug>`). Every write is compare-and-set: a write that loses a race re-reads
the question and applies the change again, so neither side erases the other.

    oq.py import FILE.md [--dry-run]     one-time load of a markdown list
    oq.py ls [--status open|resolved|all] [--tag TAG] [--json]
    oq.py show Q [--json]
    oq.py add --title T [--body B | --body-file F] [--tag TAG]... [--link 'LABEL | URL']...
    oq.py edit Q [--title T] [--body B | --body-file F]
    oq.py answer Q --summary S [--detail D | --detail-file F] [--keep-open]
    oq.py reopen Q
    oq.py tag Q +TAG -TAG ...
    oq.py link Q 'LABEL | URL' ... [--remove URL]
    oq.py rm Q --yes
    oq.py export [--out FILE.md]

Q matches a question by id or by a unique substring of its id or title. After
every change the list is exported to the project's markdown file and a JSON
backup in the data dir's _state/, because the shared store keeps no history.
Every command takes --project; without it the config's default project is used.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path


CONFIG_PATH = Path(
    os.environ.get("PROJECT_TRACKER_CONFIG", "~/.claude/project-tracker.json")
).expanduser()
PREFIX = "oq."
MAX_RETRIES = 5
LINK_RE = re.compile(r"^- \[(?P<label>[^\]]+)\]\((?P<url>[^)\s]+)\)\s*$")
CALLOUT_RE = re.compile(r"^> \[!INFO\]\s*(?P<summary>.*)$")


def die(message: str) -> None:
    sys.exit(f"oq: {message}")


def emit(value) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# --------------------------------------------------------------------------- config


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        die(f"{CONFIG_PATH} not found; run `tracker.py init` first")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def resolve_project(name: str | None) -> tuple[str, dict, dict]:
    config = load_config()
    name = name or config.get("default")
    project = config.get("projects", {}).get(name or "")
    if not project:
        die(f"unknown project {name!r}")
    return name, project, config


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- yard


class Conflict(Exception):
    pass


class Store:
    def __init__(self, site: str):
        self.site = site

    def _yard(self, *args: str, stdin: str | None = None) -> dict:
        try:
            proc = subprocess.run(
                ["yard", "shared", *args, "--site", self.site, "--json"],
                input=stdin,
                text=True,
                capture_output=True,
            )
        except FileNotFoundError:
            die("yard not found on PATH")
        if proc.returncode == 0:
            return json.loads(proc.stdout) if proc.stdout.strip() else {}
        try:
            error = json.loads(proc.stderr or proc.stdout).get("error", {})
        except json.JSONDecodeError:
            error = {"message": (proc.stderr or proc.stdout).strip()}
        code = error.get("code", "")
        if code == "version_conflict":
            raise Conflict(error.get("message", ""))
        if code == "not_found":
            raise KeyError(args[1] if len(args) > 1 else "")
        message = error.get("message", "")
        if "login" in message.lower() or "credential" in message.lower():
            die(f"{message}\nRun `yard login --device-code` and try again")
        die(f"yard shared {args[0]} failed: {code} {message}".strip())

    def keys(self) -> list[str]:
        listing = self._yard("ls")
        return sorted(
            k["key"] for k in listing.get("keys", []) if k["key"].startswith(PREFIX)
        )

    def get(self, key: str) -> tuple[dict, int]:
        item = self._yard("get", key)
        return json.loads(item["value"]), int(item["version"])

    def put(self, key: str, record: dict, if_match: str) -> int:
        body = json.dumps(record, ensure_ascii=False, indent=1)
        result = self._yard("set", key, "-", "--if-match", if_match, stdin=body)
        return int(result.get("version", 0))

    def rm(self, key: str) -> None:
        self._yard("rm", key)

    def all(self) -> list[dict]:
        keys = self.keys()
        with ThreadPoolExecutor(max_workers=8) as pool:
            items = list(pool.map(self.get, keys))
        return [{**record, "_version": version} for record, version in items]


# --------------------------------------------------------------------------- records


def slugify(title: str) -> str:
    plain = re.sub(r"['’]", "", title.lower().replace("✅", ""))
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")
    if len(slug) > 60:
        slug = slug[:60].rsplit("-", 1)[0]
    return slug or "question"


def normalize_tag(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", tag.strip().lower()).strip("-")


def parse_link(text: str) -> dict:
    label, sep, url = text.rpartition("|")
    if not sep or not url.strip().startswith(("http://", "https://")):
        die(f"a link is 'LABEL | URL', got {text!r}")
    return {"label": label.strip(), "url": url.strip()}


def ordered(records: list[dict]) -> list[dict]:
    """Open questions newest first, then resolved ones by when they were resolved."""
    open_q = [r for r in records if r["status"] == "open"]
    done = [r for r in records if r["status"] == "resolved"]
    open_q.sort(key=lambda r: r["created"], reverse=True)
    done.sort(key=lambda r: r.get("resolved") or r["created"], reverse=True)
    return open_q + done


def find(records: list[dict], query: str) -> dict:
    exact = [r for r in records if r["id"] == query or PREFIX + r["id"] == query]
    if exact:
        return exact[0]
    q = query.lower()
    hits = [r for r in records if q in r["id"] or q in r["title"].lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        die(f"no question matches {query!r}")
    die(f"{query!r} matches {len(hits)} questions: " + ", ".join(r["id"] for r in hits))


def mutate(store: Store, record: dict, change) -> dict:
    """Apply change(record) and write it, redoing the change on a fresh read after a conflict."""
    key = PREFIX + record["id"]
    current, version = (
        {k: v for k, v in record.items() if k != "_version"},
        record["_version"],
    )
    for _ in range(MAX_RETRIES):
        updated = change(json.loads(json.dumps(current)))
        updated["updated"] = iso(now())
        try:
            store.put(key, updated, str(version))
            return updated
        except Conflict:
            print(f"{record['id']}: changed by someone else, re-reading", file=sys.stderr)
            current, version = store.get(key)
    die(f"{record['id']}: still conflicting after {MAX_RETRIES} tries")


def create(store: Store, record: dict) -> dict:
    base = record["id"]
    for n in range(1, 20):
        record["id"] = base if n == 1 else f"{base}-{n}"
        try:
            store.put(PREFIX + record["id"], record, "*")
            return record
        except Conflict:
            continue
    die(f"could not find a free id for {base!r}")


# --------------------------------------------------------------------------- markdown


def parse_markdown(text: str) -> list[dict]:
    """Read `### Title` sections separated by `---`; a ✅ title is resolved."""
    questions, current, in_fence = [], None, False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            if current is not None:
                current["lines"].append(line)
            continue
        if not in_fence and line.startswith("### "):
            current = {"title": line[4:].strip(), "lines": []}
            questions.append(current)
            continue
        if not in_fence and (line.strip() == "---" or line.startswith("## ")):
            current = None
            continue
        if current is not None:
            current["lines"].append(line)

    records = []
    for q in questions:
        resolved = q["title"].startswith("✅")
        title = q["title"].lstrip("✅").strip()
        body, links, tags, summary, detail, in_callout = [], [], [], None, [], False
        for line in q["lines"]:
            if line.startswith("Tags: "):
                tags = [normalize_tag(t.strip("` ")) for t in line[6:].split(",")]
            elif match := CALLOUT_RE.match(line):
                summary, in_callout = match["summary"].strip(), True
            elif in_callout and line.startswith(">"):
                detail.append(line[1:].lstrip())
            elif match := LINK_RE.match(line.strip()):
                links.append({"label": match["label"], "url": match["url"]})
                in_callout = False
            else:
                in_callout = False
                body.append(line.rstrip())
        records.append(
            {
                "id": slugify(title),
                "title": title,
                "body": "\n".join(body).strip(),
                "status": "resolved" if resolved else "open",
                "answer": {"summary": summary or "", "detail": "\n".join(detail).strip()}
                if resolved or summary
                else None,
                "tags": sorted(t for t in set(tags) if t),
                "links": links,
            }
        )
    return records


def render_question(r: dict) -> str:
    out = ["### " + ("✅ " if r["status"] == "resolved" else "") + r["title"], ""]
    if r.get("body"):
        out += [r["body"], ""]
    if r.get("tags"):
        out += ["Tags: " + ", ".join(f"`{t}`" for t in r["tags"]), ""]
    if r.get("links"):
        out += [f"- [{l['label']}]({l['url']})" for l in r["links"]] + [""]
    answer = r.get("answer") or {}
    if answer.get("summary") or answer.get("detail"):
        out.append(f"> [!INFO] {answer.get('summary', '')}".rstrip())
        out += [f"> {line}".rstrip() for line in answer.get("detail", "").splitlines()]
        out.append("")
    return "\n".join(out)


def render_markdown(records: list[dict], site: str) -> str:
    def block(r: dict) -> str:
        return render_question(r) + "\n---\n"

    open_q = [r for r in records if r["status"] == "open"]
    done = [r for r in records if r["status"] == "resolved"]
    header = (
        "<!-- Generated by project-tracker oq.py export. Edits here are overwritten.\n"
        f"     Edit on https://{site}.yard.roversvc.com/#questions or with oq.py. -->\n\n"
    )
    return (
        header
        + f"## Open questions ({len(open_q)})\n\n---\n\n"
        + "\n".join(block(r) for r in open_q)
        + f"\n---\n---\n\n## Resolved ({len(done)})\n\n---\n\n"
        + "\n".join(block(r) for r in done)
    )


# --------------------------------------------------------------------------- commands


class Context:
    def __init__(self, args):
        self.name, self.project, self.config = resolve_project(args.project)
        self.store = Store(self.project["site"])
        self.no_export = getattr(args, "no_export", False)

    def records(self) -> list[dict]:
        return ordered(self.store.all())

    def export(self, out: str | None = None) -> None:
        path = Path(out or self.project.get("openQuestionsFile") or "").expanduser()
        if not str(path) or str(path) == ".":
            die("no export file configured; pass --out or run import first")
        records = self.records()
        path.write_text(render_markdown(records, self.project["site"]), encoding="utf-8")
        state = Path(self.project["dataDir"]).expanduser() / "_state"
        state.mkdir(parents=True, exist_ok=True)
        (state / "open-questions.json").write_text(
            json.dumps(records, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"exported {len(records)} questions to {path}", file=sys.stderr)

    def after_change(self) -> None:
        if not self.no_export and self.project.get("openQuestionsFile"):
            self.export()


def summary_row(r: dict) -> str:
    tags = " ".join(f"#{t}" for t in r.get("tags", []))
    mark = "✅" if r["status"] == "resolved" else "  "
    return f"{mark} {r['id']}  {r['title']}  {tags}".rstrip()


def cmd_import(args) -> int:
    ctx = Context(args)
    source = Path(args.file).expanduser()
    records = parse_markdown(source.read_text(encoding="utf-8"))
    if not records:
        die(f"no `### ` questions found in {source}")
    existing = set(ctx.store.keys())
    base = now()
    for i, r in enumerate(records):
        # Keep the file's order: each section lists newest first.
        stamp = iso(base - timedelta(minutes=i))
        r["created"] = r["updated"] = stamp
        if r["status"] == "resolved":
            r["resolved"] = stamp
    for r in records:
        status = "exists, skipped" if PREFIX + r["id"] in existing else "new"
        print(f"{status:16} {summary_row(r)}")
    if args.dry_run:
        print(f"dry run: {len(records)} questions parsed, nothing written")
        return 0
    created = 0
    for r in records:
        if PREFIX + r["id"] not in existing:
            create(ctx.store, r)
            created += 1
    backup = (
        Path(ctx.project["dataDir"]).expanduser() / "_state" / "open-questions.orig.md"
    )
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(source, backup)
    ctx.project["openQuestionsFile"] = str(source)
    save_config(ctx.config)
    print(f"imported {created} questions; original kept at {backup}")
    ctx.export()
    return 0


def cmd_ls(args) -> int:
    ctx = Context(args)
    records = ctx.records()
    if args.status != "all":
        records = [r for r in records if r["status"] == args.status]
    if args.tag:
        records = [r for r in records if normalize_tag(args.tag) in r.get("tags", [])]
    if args.json:
        emit(records)
    else:
        for r in records:
            print(summary_row(r))
    return 0


def cmd_show(args) -> int:
    ctx = Context(args)
    r = find(ctx.records(), args.q)
    if args.json:
        emit(r)
    else:
        print(render_question(r).strip())
    return 0


def prose_lines(text: str) -> list[str]:
    """Lines that are not bullets, indented bullet continuations, quotes or fenced code."""
    prose, in_fence = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        elif (
            not in_fence and line.strip() and not line.startswith(("- ", "* ", "  ", ">"))
        ):
            prose.append(line)
    return prose


def read_text_arg(value: str | None, path: str | None, args) -> str | None:
    if path:
        text = Path(path).expanduser().read_text(encoding="utf-8").strip()
    else:
        text = value.strip() if value is not None else None
    if text and not args.allow_prose and (prose := prose_lines(text)):
        die(
            "descriptions and answer details are bullet points, one point per `- ` line.\n"
            f"Not a bullet: {prose[0]!r}\nPass --allow-prose only if the user asked for prose."
        )
    return text


def cmd_add(args) -> int:
    ctx = Context(args)
    stamp = iso(now())
    record = create(
        ctx.store,
        {
            "id": slugify(args.title),
            "title": args.title.strip(),
            "body": read_text_arg(args.body, args.body_file, args) or "",
            "status": "open",
            "answer": None,
            "tags": sorted({normalize_tag(t) for t in args.tag if normalize_tag(t)}),
            "links": [parse_link(l) for l in args.link],
            "created": stamp,
            "updated": stamp,
        },
    )
    print(f"added {record['id']}")
    ctx.after_change()
    return 0


def cmd_edit(args) -> int:
    ctx = Context(args)
    record = find(ctx.records(), args.q)
    body = read_text_arg(args.body, args.body_file, args)

    def change(r):
        if args.title:
            r["title"] = args.title.strip()
        if body is not None:
            r["body"] = body
        return r

    mutate(ctx.store, record, change)
    print(f"edited {record['id']}")
    ctx.after_change()
    return 0


def cmd_answer(args) -> int:
    ctx = Context(args)
    record = find(ctx.records(), args.q)
    detail = read_text_arg(args.detail, args.detail_file, args) or ""

    def change(r):
        r["answer"] = {"summary": args.summary.strip(), "detail": detail}
        if not args.keep_open and r["status"] != "resolved":
            r["status"], r["resolved"] = "resolved", iso(now())
        return r

    mutate(ctx.store, record, change)
    print(
        f"answered {record['id']}" + ("" if args.keep_open else " and marked it resolved")
    )
    ctx.after_change()
    return 0


def cmd_reopen(args) -> int:
    ctx = Context(args)
    record = find(ctx.records(), args.q)

    def change(r):
        r["status"] = "open"
        r.pop("resolved", None)
        return r

    mutate(ctx.store, record, change)
    print(f"reopened {record['id']} (its answer is kept)")
    ctx.after_change()
    return 0


def cmd_tag(args) -> int:
    ctx = Context(args)
    record = find(ctx.records(), args.q)
    add = {normalize_tag(t[1:]) for t in args.tags if t.startswith("+")}
    remove = {normalize_tag(t[1:]) for t in args.tags if t.startswith("-")}
    bare = [t for t in args.tags if not t.startswith(("+", "-"))]
    if bare:
        die(f"prefix each tag with + or -: {bare}")

    def change(r):
        r["tags"] = sorted((set(r.get("tags", [])) | add) - remove - {""})
        return r

    updated = mutate(ctx.store, record, change)
    print(f"{record['id']}: tags {updated['tags']}")
    ctx.after_change()
    return 0


def cmd_link(args) -> int:
    ctx = Context(args)
    record = find(ctx.records(), args.q)
    new = [parse_link(l) for l in args.links]

    def change(r):
        links = [l for l in r.get("links", []) if l["url"] not in set(args.remove)]
        known = {l["url"] for l in links}
        r["links"] = links + [l for l in new if l["url"] not in known]
        return r

    updated = mutate(ctx.store, record, change)
    print(f"{record['id']}: {len(updated['links'])} links")
    ctx.after_change()
    return 0


def cmd_rm(args) -> int:
    ctx = Context(args)
    record = find(ctx.records(), args.q)
    if not args.yes:
        die(f"deleting {record['id']} cannot be undone; pass --yes")
    ctx.store.rm(PREFIX + record["id"])
    print(f"deleted {record['id']}")
    ctx.after_change()
    return 0


def cmd_export(args) -> int:
    Context(args).export(args.out)
    return 0


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--project", help="project name from the config (default: its default)"
    )
    parser.add_argument(
        "--no-export", action="store_true", help="skip the export after a change"
    )
    parser.add_argument(
        "--allow-prose", action="store_true", help="accept text that is not bullet points"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("import")
    p.add_argument("file")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("ls")
    p.add_argument("--status", choices=["open", "resolved", "all"], default="open")
    p.add_argument("--tag")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_ls)

    p = sub.add_parser("show")
    p.add_argument("q")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("add")
    p.add_argument("--title", required=True)
    p.add_argument("--body")
    p.add_argument("--body-file")
    p.add_argument("--tag", action="append", default=[])
    p.add_argument("--link", action="append", default=[], help="'LABEL | URL'")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("edit")
    p.add_argument("q")
    p.add_argument("--title")
    p.add_argument("--body")
    p.add_argument("--body-file")
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("answer")
    p.add_argument("q")
    p.add_argument(
        "--summary", required=True, help="one line, shown as the answer's title"
    )
    p.add_argument("--detail")
    p.add_argument("--detail-file")
    p.add_argument("--keep-open", action="store_true", help="answer without resolving")
    p.set_defaults(func=cmd_answer)

    p = sub.add_parser("reopen")
    p.add_argument("q")
    p.set_defaults(func=cmd_reopen)

    p = sub.add_parser("tag")
    p.add_argument("q")
    p.add_argument("tags", nargs="+", help="+tag to add, -tag to remove")
    p.set_defaults(func=cmd_tag)

    p = sub.add_parser("link")
    p.add_argument("q")
    p.add_argument("links", nargs="*", help="'LABEL | URL'")
    p.add_argument("--remove", action="append", default=[], metavar="URL")
    p.set_defaults(func=cmd_link)

    p = sub.add_parser("rm")
    p.add_argument("q")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_rm)

    p = sub.add_parser("export")
    p.add_argument("--out")
    p.set_defaults(func=cmd_export)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
