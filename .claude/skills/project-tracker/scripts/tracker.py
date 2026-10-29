#!/usr/bin/env python3
"""Keep a project's change-log site: docs, summarized entries, build and publish.

The agent reads each doc's history and writes the summaries; this script owns the
bookkeeping around them so it stays deterministic:

    tracker.py init --project urssaf --data-dir DIR --site SITE --title TITLE
    tracker.py projects
    tracker.py add-doc URL NAME
    tracker.py status [DOC]
    tracker.py window DOC DAYS          time ranges still to fetch for a DAYS-day log
    tracker.py gh-events DOC --since T  a PR's commits, reviews and comments as bursts
    tracker.py bursts EVENTS.json       group any {at, actor} events into bursts
    tracker.py snapshot DOC SRC_DIR     diff SRC_DIR against the stored copy (--commit stores it)
    tracker.py apply DOC ENTRIES.json   upsert entries, widen coverage, save the cursor
    tracker.py build
    tracker.py publish [--dry-run] [--no-pull]

Every command takes --project; without it the config's default project is used.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path


CONFIG_PATH = Path(
    os.environ.get("PROJECT_TRACKER_CONFIG", "~/.claude/project-tracker.json")
).expanduser()
SITE_TEMPLATE = Path(__file__).resolve().parent.parent / "site"
BURST_GAP = timedelta(hours=2)
DATA_FILE = "tracker.json"


def die(message: str) -> None:
    sys.exit(f"tracker: {message}")


def run(argv: list[str], **kwargs) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, text=True, **kwargs)
    except FileNotFoundError:
        die(f"{argv[0]} not found on PATH")


def emit(value) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------- time


def parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        die(f"not an ISO timestamp: {value!r}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


# --------------------------------------------------------------------------- config


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        return {"projects": {}}
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        die(f"{CONFIG_PATH} is not valid JSON")
    loaded.setdefault("projects", {})
    return loaded


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def resolve_project(name: str | None) -> tuple[str, dict]:
    config = load_config()
    name = name or config.get("default")
    if not name:
        die(f"no project configured in {CONFIG_PATH}; run `tracker.py init` first")
    project = config["projects"].get(name)
    if not project:
        known = ", ".join(sorted(config["projects"])) or "none"
        die(f"unknown project {name!r} (configured: {known})")
    return name, project


# --------------------------------------------------------------------------- data


class Tracker:
    def __init__(self, name: str, project: dict):
        self.name = name
        self.site = project["site"]
        self.title = project["title"]
        self.data_dir = Path(project["dataDir"]).expanduser()
        if not self.data_dir.is_dir():
            die(f"data dir does not exist: {self.data_dir}")
        self.path = self.data_dir / DATA_FILE
        if self.path.is_file():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"docs": [], "entries": []}

    def save(self) -> None:
        self.data["docs"].sort(key=lambda d: d["addedAt"])
        self.data["entries"].sort(key=lambda e: (e["doc"], e["start"]))
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        tmp.replace(self.path)

    def find_doc(self, ref: str) -> dict:
        docs = self.data["docs"]
        lowered = ref.lower()
        for doc in docs:
            if lowered in (doc["id"], doc["name"].lower(), doc["url"].lower()):
                return doc
        partial = [d for d in docs if lowered in d["name"].lower() or lowered in d["id"]]
        if len(partial) == 1:
            return partial[0]
        names = ", ".join(f"{d['id']} ({d['name']})" for d in docs) or "none"
        if partial:
            die(f"{ref!r} matches more than one doc: {names}")
        die(f"no doc matches {ref!r}. Docs: {names}")

    def entries_for(self, doc_id: str) -> list[dict]:
        return [e for e in self.data["entries"] if e["doc"] == doc_id]

    def state_dir(self, doc_id: str) -> Path:
        return self.data_dir / "_state" / doc_id


# --------------------------------------------------------------------------- kinds


KIND_PATTERNS = [
    ("github_pr", re.compile(r"github\.com/[^/]+/[^/]+/pull/\d+")),
    ("confluence", re.compile(r"atlassian\.net/wiki/.*/pages/\d+")),
    (
        "jira",
        re.compile(r"atlassian\.net/(browse/|jira/.*selectedIssue=)[A-Z][A-Z0-9]+-\d+"),
    ),
    ("claude_artifact", re.compile(r"claude\.ai/(code/)?artifact/")),
    ("slack_canvas", re.compile(r"slack\.com/docs/[A-Z0-9]+/F[A-Z0-9]+")),
    ("google_doc", re.compile(r"docs\.google\.com/")),
]


def detect_kind(url: str) -> str:
    for kind, pattern in KIND_PATTERNS:
        if pattern.search(url):
            return kind
    return "other"


def source_ref(kind: str, url: str) -> dict:
    """The identifiers each kind's history recipe needs, parsed once at add time."""
    if kind == "github_pr":
        m = re.search(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
        return {"repo": m.group(1), "number": int(m.group(2))}
    if kind == "confluence":
        return {"pageId": re.search(r"/pages/(\d+)", url).group(1)}
    if kind == "jira":
        return {"key": re.search(r"([A-Z][A-Z0-9]+-\d+)", url).group(1)}
    if kind == "claude_artifact":
        return {"artifactUrl": url.split("?")[0].split("#")[0]}
    if kind == "slack_canvas":
        return {"canvasId": re.search(r"/(F[A-Z0-9]+)", url).group(1)}
    return {}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "doc"


# --------------------------------------------------------------------------- commands


def cmd_init(args) -> int:
    config = load_config()
    data_dir = Path(args.data_dir).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    config["projects"][args.project] = {
        "dataDir": str(data_dir),
        "site": args.site,
        "title": args.title,
    }
    if args.default or not config.get("default"):
        config["default"] = args.project
    save_config(config)
    print(f"project {args.project}: data in {data_dir}, site {args.site}")
    return 0


def cmd_projects(args) -> int:
    emit(load_config())
    return 0


def cmd_add_doc(args) -> int:
    tracker = Tracker(*resolve_project(args.project))
    for doc in tracker.data["docs"]:
        if doc["url"] == args.url:
            die(f"already tracked as {doc['id']} ({doc['name']})")
    kind = args.kind or detect_kind(args.url)
    doc_id = slugify(args.name)
    taken = {d["id"] for d in tracker.data["docs"]}
    suffix = 2
    while doc_id in taken:
        doc_id = f"{slugify(args.name)}-{suffix}"
        suffix += 1
    doc = {
        "id": doc_id,
        "name": args.name,
        "url": args.url,
        "kind": kind,
        "source": source_ref(kind, args.url),
        "addedAt": iso(now()),
        "coverage": None,
        "cursor": {},
    }
    tracker.data["docs"].append(doc)
    tracker.save()
    emit(doc)
    return 0


def doc_status(tracker: Tracker, doc: dict) -> dict:
    entries = sorted(tracker.entries_for(doc["id"]), key=lambda e: e["start"])
    return {
        **doc,
        "entryCount": len(entries),
        "recentEntries": [
            {k: e[k] for k in ("id", "start", "end", "title", "actors")}
            for e in entries[-5:]
        ],
        "hasSnapshot": (tracker.state_dir(doc["id"]) / "snapshot").is_dir(),
    }


def cmd_status(args) -> int:
    tracker = Tracker(*resolve_project(args.project))
    docs = [tracker.find_doc(args.doc)] if args.doc else tracker.data["docs"]
    emit(
        {
            "project": tracker.name,
            "site": tracker.site,
            "dataDir": str(tracker.data_dir),
            "docs": [doc_status(tracker, d) for d in docs],
        }
    )
    return 0


def cmd_window(args) -> int:
    """Ranges to fetch so the log covers the last DAYS days without re-reading anything."""
    tracker = Tracker(*resolve_project(args.project))
    doc = tracker.find_doc(args.doc)
    end = now()
    start = end - timedelta(days=args.days)
    coverage = doc.get("coverage")
    ranges = []
    if not coverage:
        ranges.append({"from": iso(start), "to": iso(end), "reason": "initial"})
    else:
        covered_from = parse_time(coverage["from"])
        covered_to = parse_time(coverage["to"])
        if start < covered_from:
            ranges.append(
                {"from": iso(start), "to": iso(covered_from), "reason": "backfill"}
            )
        # Re-read from the start of the last entry so a burst still in progress at the
        # previous run is updated rather than split.
        resume = covered_to
        entries = tracker.entries_for(doc["id"])
        if entries:
            last_start = max(parse_time(e["start"]) for e in entries)
            resume = min(resume, last_start)
        ranges.append({"from": iso(resume), "to": iso(end), "reason": "new"})
    emit(
        {
            "doc": doc["id"],
            "kind": doc["kind"],
            "cursor": doc.get("cursor") or {},
            "fetch": ranges,
        }
    )
    return 0


def group_bursts(events: list[dict], gap: timedelta = BURST_GAP) -> list[dict]:
    """One burst per actor per stretch of activity with no gap longer than `gap`."""
    by_actor: dict[str, list[dict]] = {}
    for event in sorted(events, key=lambda e: e["at"]):
        by_actor.setdefault(event.get("actor") or "unknown", []).append(event)
    bursts = []
    for actor, items in by_actor.items():
        current: list[dict] = []
        for event in items:
            if current and parse_time(event["at"]) - parse_time(current[-1]["at"]) > gap:
                bursts.append(current)
                current = []
            current.append(event)
        if current:
            bursts.append(current)
    result = [
        {
            "start": b[0]["at"],
            "end": b[-1]["at"],
            "actor": b[0].get("actor") or "unknown",
            "count": len(b),
            "events": b,
        }
        for b in bursts
    ]
    return sorted(result, key=lambda b: b["start"])


def cmd_bursts(args) -> int:
    events = json.loads(Path(args.events).read_text(encoding="utf-8"))
    emit(group_bursts(events, timedelta(minutes=args.gap_minutes)))
    return 0


def gh_paged(path: str) -> list[dict]:
    proc = run(["gh", "api", "--paginate", "--slurp", path], capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        die(f"gh api {path} failed")
    pages = json.loads(proc.stdout)
    return [item for page in pages for item in page]


def cmd_gh_events(args) -> int:
    tracker = Tracker(*resolve_project(args.project))
    doc = tracker.find_doc(args.doc)
    if doc["kind"] != "github_pr":
        die(f"{doc['id']} is a {doc['kind']}, not a GitHub PR")
    repo, number = doc["source"]["repo"], doc["source"]["number"]
    since = parse_time(args.since)
    until = parse_time(args.until) if args.until else now()
    base = f"repos/{repo}"

    events = []
    for c in gh_paged(f"{base}/pulls/{number}/commits?per_page=100"):
        # A rebase rewrites the committer date of every commit; the author date survives.
        at = c["commit"]["author"]["date"]
        events.append(
            {
                "at": at,
                "actor": (c.get("author") or {}).get("login")
                or c["commit"]["author"]["name"],
                "type": "commit",
                "sha": c["sha"][:10],
                "text": c["commit"]["message"],
                "url": c["html_url"],
            }
        )
    for r in gh_paged(f"{base}/pulls/{number}/reviews?per_page=100"):
        # GitHub wraps every inline comment and reply in its own empty COMMENTED review.
        if not r.get("submitted_at") or (
            r["state"] == "COMMENTED" and not (r.get("body") or "").strip()
        ):
            continue
        events.append(
            {
                "at": r["submitted_at"],
                "actor": (r.get("user") or {}).get("login"),
                "type": f"review:{r['state'].lower()}",
                "reviewId": r["id"],
                "text": r.get("body") or "",
                "url": r["html_url"],
            }
        )
    for c in gh_paged(f"{base}/pulls/{number}/comments?per_page=100"):
        events.append(
            {
                "at": c["created_at"],
                "actor": (c.get("user") or {}).get("login"),
                "type": "reply" if c.get("in_reply_to_id") else "inline-comment",
                "reviewId": c.get("pull_request_review_id"),
                "path": c.get("path"),
                "text": c.get("body") or "",
                "url": c["html_url"],
            }
        )
    for c in gh_paged(f"{base}/issues/{number}/comments?per_page=100"):
        events.append(
            {
                "at": c["created_at"],
                "actor": (c.get("user") or {}).get("login"),
                "type": "comment",
                "text": c.get("body") or "",
                "url": c["html_url"],
            }
        )

    in_range = [e for e in events if since <= parse_time(e["at"]) <= until]
    for event in in_range:
        if len(event["text"]) > args.max_chars:
            event["text"] = event["text"][: args.max_chars] + " …[truncated]"
    latest = max((e["at"] for e in events), default=None)
    emit(
        {
            "doc": doc["id"],
            "range": {"from": iso(since), "to": iso(until)},
            "eventCount": len(in_range),
            "latestEventAt": latest,
            "bursts": group_bursts(in_range),
        }
    )
    return 0


def read_tree(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            try:
                files[str(path.relative_to(root))] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
    return files


def cmd_snapshot(args) -> int:
    """For sources with no readable history: diff the current copy against the last one."""
    tracker = Tracker(*resolve_project(args.project))
    doc = tracker.find_doc(args.doc)
    source = Path(args.src).expanduser().resolve()
    if not source.is_dir():
        die(f"not a directory: {source}")
    stored = tracker.state_dir(doc["id"]) / "snapshot"
    before = read_tree(stored) if stored.is_dir() else {}
    after = read_tree(source)

    diff_lines = []
    for name in sorted(set(before) | set(after)):
        if before.get(name) == after.get(name):
            continue
        diff_lines.extend(
            difflib.unified_diff(
                before.get(name, "").splitlines(),
                after.get(name, "").splitlines(),
                fromfile=f"previous/{name}",
                tofile=f"current/{name}",
                lineterm="",
                n=2,
            )
        )
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    print(
        json.dumps(
            {"doc": doc["id"], "firstSnapshot": not before, "changedFiles": changed}
        )
    )
    if before:
        print("\n".join(diff_lines))

    if args.commit:
        if stored.exists():
            shutil.rmtree(stored)
        shutil.copytree(source, stored)
        doc.setdefault("cursor", {})["snapshotAt"] = iso(now())
        tracker.save()
        print(f"stored snapshot in {stored}", file=sys.stderr)
    return 0


ENTRY_FIELDS = {"id", "start", "end", "title", "actors", "bullets", "links"}


def validate_entry(doc_id: str, raw: dict) -> dict:
    missing = {"start", "title", "bullets"} - set(raw)
    if missing:
        die(f"entry {raw.get('title', raw)!r} is missing {sorted(missing)}")
    unknown = set(raw) - ENTRY_FIELDS
    if unknown:
        die(f"entry {raw['title']!r} has unknown fields {sorted(unknown)}")
    start = parse_time(raw["start"])
    end = parse_time(raw.get("end") or raw["start"])
    if not raw["bullets"] or not all(
        isinstance(b, str) and b.strip() for b in raw["bullets"]
    ):
        die(f"entry {raw['title']!r} needs at least one non-empty bullet")
    links = raw.get("links") or []
    for link in links:
        if not {"label", "url"} <= set(link):
            die(f"entry {raw['title']!r} has a link without label and url: {link}")
    return {
        "id": raw.get("id") or f"{doc_id}-{start.strftime('%Y%m%dT%H%M')}",
        "doc": doc_id,
        "start": iso(start),
        "end": iso(max(start, end)),
        "title": raw["title"].strip(),
        "actors": raw.get("actors") or [],
        "bullets": [b.strip() for b in raw["bullets"]],
        "links": links,
    }


def cmd_apply(args) -> int:
    tracker = Tracker(*resolve_project(args.project))
    doc = tracker.find_doc(args.doc)
    raw_entries = json.loads(Path(args.entries).read_text(encoding="utf-8"))
    if not isinstance(raw_entries, list):
        die("entries file must hold a JSON list")
    entries = [validate_entry(doc["id"], e) for e in raw_entries]

    existing = {e["id"]: e for e in tracker.data["entries"]}
    stamp = iso(now())
    added = updated = 0
    for entry in entries:
        previous = existing.get(entry["id"])
        if previous and previous["doc"] != doc["id"]:
            die(f"entry id {entry['id']} belongs to {previous['doc']}")
        if previous:
            unchanged = all(
                previous.get(k) == entry[k] for k in ENTRY_FIELDS if k != "id"
            )
            entry["updated"] = previous["updated"] if unchanged else stamp
            updated += 0 if unchanged else 1
            tracker.data["entries"].remove(previous)
        else:
            entry["updated"] = stamp
            added += 1
        tracker.data["entries"].append(entry)

    if args.covered_from or args.covered_to:
        coverage = doc.get("coverage") or {}
        if args.covered_from:
            new_from = parse_time(args.covered_from)
            old = coverage.get("from")
            coverage["from"] = iso(min(new_from, parse_time(old)) if old else new_from)
        if args.covered_to:
            new_to = parse_time(args.covered_to)
            old = coverage.get("to")
            coverage["to"] = iso(max(new_to, parse_time(old)) if old else new_to)
        coverage.setdefault("from", coverage.get("to"))
        coverage.setdefault("to", coverage.get("from"))
        doc["coverage"] = coverage
    if args.cursor:
        doc.setdefault("cursor", {}).update(json.loads(args.cursor))
    doc["lastRunAt"] = stamp
    tracker.save()
    print(
        f"{doc['id']}: {added} added, {updated} updated, "
        f"{len(tracker.entries_for(doc['id']))} total; coverage {doc.get('coverage')}"
    )
    return 0


# --------------------------------------------------------------------------- site


PUBLIC_DOC_FIELDS = ("id", "name", "url", "kind", "addedAt", "coverage", "lastRunAt")


def public_data(tracker: Tracker) -> dict:
    return {
        "project": {"title": tracker.title, "site": tracker.site},
        "generatedAt": iso(now()),
        "docs": [{k: d.get(k) for k in PUBLIC_DOC_FIELDS} for d in tracker.data["docs"]],
        "entries": sorted(
            tracker.data["entries"], key=lambda e: e["start"], reverse=True
        ),
    }


def build_site(tracker: Tracker) -> Path:
    out = tracker.data_dir / "site"
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE_TEMPLATE, out)
    (out / "data.json").write_text(
        json.dumps(public_data(tracker), indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return out


def cmd_build(args) -> int:
    tracker = Tracker(*resolve_project(args.project))
    out = build_site(tracker)
    print(
        f"built {out}: {len(tracker.data['docs'])} docs, {len(tracker.data['entries'])} entries"
    )
    print(f"local preview: python3 -m http.server -d {out} 8765")
    return 0


def require_login() -> str:
    """`yard whoami` reports a missing credential in its output, so check the email."""
    proc = run(["yard", "whoami", "--json"], capture_output=True)
    email = ""
    if proc.returncode == 0:
        try:
            email = str(json.loads(proc.stdout).get("email") or "")
        except json.JSONDecodeError:
            email = ""
    if not email:
        die("not signed in to Yard. Run `yard login --device-code` and try again")
    return email


def pull_live(site: str) -> dict | None:
    scratch = Path(tempfile.mkdtemp(prefix="tracker-pull-"))
    try:
        proc = run(["yard", "pull", site, str(scratch), "--force"], capture_output=True)
        if proc.returncode != 0:
            combined = ((proc.stdout or "") + (proc.stderr or "")).lower()
            if any(token in combined for token in ("not_found", "no such site", "404")):
                return None
            sys.stderr.write((proc.stdout or "") + (proc.stderr or ""))
            die(f"yard pull failed (exit {proc.returncode})")
        live = scratch / "data.json"
        return json.loads(live.read_text(encoding="utf-8")) if live.is_file() else None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def merge_live(tracker: Tracker, live: dict) -> tuple[int, int]:
    """Copy back docs and entries the site has and this data dir lost. Local wins on ids."""
    local_docs = {d["id"] for d in tracker.data["docs"]}
    restored_docs = 0
    for doc in live.get("docs", []):
        if doc["id"] not in local_docs:
            tracker.data["docs"].append(
                {**doc, "source": source_ref(doc["kind"], doc["url"]), "cursor": {}}
            )
            restored_docs += 1
    local_entries = {e["id"] for e in tracker.data["entries"]}
    restored_entries = 0
    for entry in live.get("entries", []):
        if entry["id"] not in local_entries:
            tracker.data["entries"].append(entry)
            restored_entries += 1
    if restored_docs or restored_entries:
        tracker.save()
    return restored_docs, restored_entries


def cmd_publish(args) -> int:
    tracker = Tracker(*resolve_project(args.project))
    email = require_login()
    print(f"site {tracker.site}, as {email}")
    if args.no_pull:
        print("pull: skipped (--no-pull); anything only on the site will be DELETED")
    else:
        live = pull_live(tracker.site)
        if live is None:
            print("pull: site not published yet, nothing to merge")
        else:
            docs, entries = merge_live(tracker, live)
            print(
                f"pull: restored {docs} doc(s) and {entries} entr(ies) from the live site"
            )
    out = build_site(tracker)
    links = [p for p in out.rglob("*") if p.is_symlink()]
    if links:
        die(f"yard refuses symlinks: {links}")
    print(
        f"built: {len(tracker.data['docs'])} docs, {len(tracker.data['entries'])} entries"
    )
    if args.dry_run:
        print(
            f"dry run, not publishing. Would replace https://{tracker.site}.yard.roversvc.com/"
        )
        return 0
    proc = run(
        ["yard", "publish", str(out), tracker.site, "--yes", "--json"],
        capture_output=True,
    )
    if proc.returncode != 0:
        sys.stderr.write((proc.stdout or "") + (proc.stderr or ""))
        die(f"yard publish failed (exit {proc.returncode})")
    try:
        url = str(json.loads(proc.stdout).get("url") or "")
    except json.JSONDecodeError:
        url = proc.stdout.strip()
    print(f"published: {url or f'https://{tracker.site}.yard.roversvc.com/'}")
    return 0


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--project", help="project name from the config (default: its default)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="register a project and its data dir")
    p.add_argument("--project", dest="project", required=True)
    p.add_argument("--data-dir", required=True)
    p.add_argument("--site", required=True, help="Yard site id")
    p.add_argument("--title", required=True)
    p.add_argument("--default", action="store_true", help="make this the default project")
    p.set_defaults(func=cmd_init)

    sub.add_parser("projects", help="print the config").set_defaults(func=cmd_projects)

    p = sub.add_parser("add-doc")
    p.add_argument("url")
    p.add_argument("name")
    p.add_argument("--kind", choices=[k for k, _ in KIND_PATTERNS] + ["other"])
    p.set_defaults(func=cmd_add_doc)

    p = sub.add_parser("status")
    p.add_argument("doc", nargs="?")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("window")
    p.add_argument("doc")
    p.add_argument("days", type=int)
    p.set_defaults(func=cmd_window)

    p = sub.add_parser("gh-events")
    p.add_argument("doc")
    p.add_argument("--since", required=True)
    p.add_argument("--until")
    p.add_argument(
        "--max-chars", type=int, default=1500, help="truncate each event's text"
    )
    p.set_defaults(func=cmd_gh_events)

    p = sub.add_parser("bursts")
    p.add_argument("events", help="JSON list of objects with at and actor")
    p.add_argument(
        "--gap-minutes", type=int, default=int(BURST_GAP.total_seconds() // 60)
    )
    p.set_defaults(func=cmd_bursts)

    p = sub.add_parser("snapshot")
    p.add_argument("doc")
    p.add_argument("src", help="directory holding the doc's current content")
    p.add_argument("--commit", action="store_true", help="store SRC as the new snapshot")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("apply")
    p.add_argument("doc")
    p.add_argument("entries", help="JSON list of entries")
    p.add_argument("--covered-from")
    p.add_argument("--covered-to")
    p.add_argument("--cursor", help="JSON object merged into the doc's cursor")
    p.set_defaults(func=cmd_apply)

    sub.add_parser("build").set_defaults(func=cmd_build)

    p = sub.add_parser("publish")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--no-pull", action="store_true", help="the only way to make a deletion stick"
    )
    p.set_defaults(func=cmd_publish)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
