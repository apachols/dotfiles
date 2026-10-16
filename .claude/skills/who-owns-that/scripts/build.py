#!/usr/bin/env python3
"""Build the "Who owns that?" static site from Jira Assets exports and the web repo.

Inputs:
  --components  JSON from AQL `objectSchemaId = 42` (Technology Components: concepts,
                subconcepts and components in one result)
  --groups      JSON from AQL `objectTypeId = 15` (People Directory > Groups: the teams)
  --web         a checkout of roverdotcom/web, for taxonomy.yml and code subconcept tags

Either export can instead be fetched with --from-api (ATLASSIAN_EMAIL + ATLASSIAN_API_TOKEN).

Writes <out>/index.html, app.js, style.css (copied from ../site) and data.json, plus
<out>/_source/, a copy of this skill, so `yard pull who-owns-that` recovers the builder.
Stdlib only.
"""

from __future__ import annotations

import argparse
import ast
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime
from datetime import timezone
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
SITE_SRC = SKILL_DIR / "site"
DEFAULT_OUT = Path.home() / ".cache" / "who-owns-that" / "dist"

ATLASSIAN_SITE = "https://roverdotcom.atlassian.net"
ASSETS_WORKSPACE = "5f6871e3-042a-42db-9fcf-a09d00aaa3d2"
SCHEMA_ID = 42
GROUPS_TYPE_ID = 15

# AQL results carry attribute ids, not names. These are the ids from
# listAssetsObjectTypeAttributes for each object type; a renamed attribute keeps its id.
CONCEPT_ATTRS = {"426": "name", "451": "status"}
SUBCONCEPT_ATTRS = {
    "449": "name",
    "430": "short",
    "435": "concept",
    "436": "description",
    "437": "team",
    "438": "rationale",
    "439": "complexity",
    "440": "wiz",
    "450": "status",
}
COMPONENT_ATTRS = {
    "458": "name",
    "434": "short",
    "441": "concept",
    "442": "subconcept",
    "443": "type",
    "444": "description",
    "453": "team",
    "452": "status",
}
GROUP_ATTRS = {
    "164": "name",
    "340": "dri",
    "249": "parent",
    "447": "slack",
    "448": "confluence",
    "462": "status",
    "723": "context",
    "446": "jiraComponent",
}

CONCEPT_REF = re.compile(r"CONCEPTS\.([a-z0-9_]+)\.([a-z0-9_]+)")
TS_SYMBOL = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?(?:class|function|const|let|enum)\s+([A-Za-z0-9_$]+)"
)
SKIP_PATH = re.compile(
    r"(^|/)(tests?|__tests__|migrations|node_modules)/|_tests?\.py$|\.test\.tsx?$|\.spec\.tsx?$"
)
GENERATED = {
    "src/aplaceforrover/common/concept_taxonomy.py",
    "src/frontend/rsdk/src/concepts.ts",
}


def die(msg: str) -> None:
    print(f"build: {msg}", file=sys.stderr)
    sys.exit(1)


def fetch_aql(aql: str) -> dict:
    email, token = (
        os.environ.get("ATLASSIAN_EMAIL"),
        os.environ.get("ATLASSIAN_API_TOKEN"),
    )
    if not (email and token):
        die("--from-api needs ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN")
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()
    url = f"{ATLASSIAN_SITE}/gateway/api/jsm/assets/workspace/{ASSETS_WORKSPACE}/v1/object/aql"
    objects, start = [], 0
    while True:
        body = json.dumps({"qlQuery": aql}).encode()
        req = urllib.request.Request(
            f"{url}?startAt={start}&maxResults=100&includeAttributes=true",
            data=body,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            page = json.load(resp)
        objects += page.get("values", [])
        start += len(page.get("values", []))
        if page.get("isLast", True) or not page.get("values"):
            return {"objects": objects}


def load_export(path: str | None, aql: str, from_api: bool) -> dict:
    if from_api:
        return fetch_aql(aql)
    if not path:
        die(f"pass the export for `{aql}`, or --from-api")
    data = json.loads(Path(path).read_text())
    if "objects" not in data:
        die(f"{path} has no 'objects' key; is it an AQL result?")
    if data.get("isLast") is False:
        die(
            f"{path} is one page of {data.get('total')} objects; re-run the query with a higher limit"
        )
    return data


def attrs(obj: dict, mapping: dict[str, str]) -> dict:
    out = {}
    for attr in obj.get("attributes", []):
        key = mapping.get(
            str(attr.get("objectTypeAttributeId") or attr.get("attributeId"))
        )
        values = [
            v.get("displayValue")
            for v in attr.get("objectAttributeValues") or attr.get("values") or []
        ]
        values = [v for v in values if v not in (None, "")]
        if key and values:
            out[key] = values[0] if len(values) == 1 else values
    return out


def parse_assets(components_export: dict, groups_export: dict) -> dict:
    concepts, subconcepts, components = [], [], []
    for obj in components_export["objects"]:
        kind = obj["objectType"]["name"]
        base = {"id": obj["id"], "key": obj["objectKey"]}
        if kind == "Concept":
            concepts.append(base | attrs(obj, CONCEPT_ATTRS))
        elif kind == "Subconcept":
            subconcepts.append(base | attrs(obj, SUBCONCEPT_ATTRS))
        elif kind == "Component":
            components.append(base | attrs(obj, COMPONENT_ATTRS))

    owning = {s.get("team") for s in subconcepts} | {c.get("team") for c in components}
    teams = []
    for obj in groups_export["objects"]:
        team = {"id": obj["id"], "key": obj["objectKey"]} | attrs(obj, GROUP_ATTRS)
        # Groups covers the whole company; keep only teams that own something.
        if team.get("name") in owning:
            teams.append(team)
    for name in sorted(n for n in owning - {t.get("name") for t in teams} if n):
        teams.append({"name": name, "missingFromDirectory": True})

    key = lambda r: (r.get("name") or "").lower()  # noqa: E731
    return {
        "concepts": sorted(concepts, key=key),
        "subconcepts": sorted(subconcepts, key=key),
        "components": sorted(components, key=key),
        "teams": sorted(teams, key=key),
    }


def python_tags(text: str, rel: str) -> list[tuple[str, int, str, str]]:
    """(concept.subconcept, line, symbol, rel) for each CONCEPTS ref, credited to its def."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    found = []

    def refs(node: ast.AST):
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Attribute)
                and isinstance(sub.value, ast.Attribute)
                and isinstance(sub.value.value, ast.Name)
                and sub.value.value.id == "CONCEPTS"
            ):
                yield f"{sub.value.attr}.{sub.attr}", sub.lineno

    def visit(body: list[ast.stmt], prefix: str) -> None:
        for stmt in body:
            if isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{stmt.name}"
                for dec in stmt.decorator_list:
                    found.extend((k, ln, name, rel) for k, ln in refs(dec))
                own = [
                    s
                    for s in stmt.body
                    if not isinstance(
                        s, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                    )
                ]
                for s in own:
                    found.extend((k, ln, name, rel) for k, ln in refs(s))
                visit(stmt.body, f"{name}.")
            elif not prefix:
                found.extend((k, ln, "", rel) for k, ln in refs(stmt))

    visit(tree.body, "")
    return found


def ts_tags(text: str, rel: str) -> list[tuple[str, int, str, str]]:
    """Credited to the nearest preceding class/function/const, which is a heuristic."""
    found, symbol = [], ""
    for lineno, line in enumerate(text.splitlines(), 1):
        if m := TS_SYMBOL.match(line):
            symbol = m.group(1)
        found.extend(
            (f"{m.group(1)}.{m.group(2)}", lineno, symbol, rel)
            for m in CONCEPT_REF.finditer(line)
        )
    return found


def git_files(web: Path, ref: str, paths: list[str]) -> dict[str, str]:
    """Read files at a ref without touching the working tree."""
    proc = subprocess.run(
        ["git", "-C", str(web), "cat-file", "--batch"],
        input="".join(f"{ref}:{p}\n" for p in paths).encode(),
        capture_output=True,
        check=True,
    )
    out, pos = {}, 0
    buf = proc.stdout
    for p in paths:
        end = buf.index(b"\n", pos)
        header = buf[pos:end].split()
        pos = end + 1
        if header[-1] == b"missing":
            continue
        size = int(header[2])
        out[p] = buf[pos : pos + size].decode("utf-8", errors="replace")
        pos += size + 1
    return out


def scan_code(web: Path, ref: str) -> list[tuple[str, int, str, str]]:
    listing = subprocess.run(
        [
            "git",
            "-C",
            str(web),
            "grep",
            "-l",
            "-E",
            r"CONCEPTS\.[a-z0-9_]+\.[a-z0-9_]+",
            ref,
            "--",
            "*.py",
            "*.ts",
            "*.tsx",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    # git grep on a tree prints "<ref>:<path>".
    files = [f.split(":", 1)[1] for f in listing]
    files = [f for f in files if f not in GENERATED and not SKIP_PATH.search(f)]
    tags = []
    for rel, text in git_files(web, ref, files).items():
        tags += (python_tags if rel.endswith(".py") else ts_tags)(text, rel)
    return tags


def parse_taxonomy(text: str) -> dict:
    """concept.subconcept -> {name: 'Concept: Subconcept', team} from taxonomy.yml.

    Parsed line by line because the file is a fixed generated shape and this script
    must run without PyYAML.
    """
    teams, result = {}, {}
    section = concept = concept_desc = sub = None
    for raw in text.splitlines():
        line = raw.split(" #")[0].rstrip()
        if line in ("teams:", "concepts:"):
            section = line[:-1]
            continue
        m = re.match(r"^(\s*)(?:- )?(\w+): ?(.*)$", line)
        if not m:
            continue
        indent, field, value = len(m.group(1)), m.group(2), m.group(3).strip().strip('"')
        if section == "teams":
            if field == "name":
                current = value
            elif field == "description":
                teams[current] = value
        elif section == "concepts":
            if (
                indent <= 4
                and field == "name"
                and raw.lstrip().startswith("- ")
                and indent == 2
            ):
                concept, sub = value, None
            elif indent == 4 and field == "description" and sub is None:
                concept_desc = value
            elif field == "name" and indent >= 6:
                sub = value
                result[f"{concept}.{sub}"] = {"concept": concept_desc}
            elif field == "description" and sub:
                result[f"{concept}.{sub}"]["name"] = f"{concept_desc}: {value}"
            elif field == "team" and sub:
                result[f"{concept}.{sub}"]["team"] = teams.get(value, value)
    return result


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower().replace("&", "and"))


def build(args: argparse.Namespace) -> None:
    components_export = load_export(
        args.components, f"objectSchemaId = {SCHEMA_ID}", args.from_api
    )
    groups_export = load_export(
        args.groups, f"objectTypeId = {GROUPS_TYPE_ID}", args.from_api
    )
    data = parse_assets(components_export, groups_export)
    if not data["subconcepts"] or not data["components"] or not data["teams"]:
        die("an export is missing subconcepts, components or teams; refusing to publish an empty site")

    web = Path(args.web).resolve()
    sha = subprocess.run(
        ["git", "-C", str(web), "rev-parse", "--verify", f"{args.ref}^{{commit}}"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not sha:
        die(f"{args.ref} is not a commit in {web}; run `git -C {web} fetch origin master`")
    taxonomy_text = git_files(web, sha, ["taxonomy.yml"]).get("taxonomy.yml")
    if not taxonomy_text:
        die(f"no taxonomy.yml at {args.ref}")
    taxonomy = parse_taxonomy(taxonomy_text)
    by_norm = {norm(s["name"]): s for s in data["subconcepts"] if s.get("name")}

    # Match taxonomy.yml keys to Assets subconcepts by name, and record where the two
    # disagree on the owner.
    drift, unmatched = [], []
    for code_key, entry in sorted(taxonomy.items()):
        sub = by_norm.get(norm(entry.get("name", "")))
        if not sub:
            unmatched.append(
                {
                    "codeKey": code_key,
                    "taxonomyName": entry.get("name"),
                    "taxonomyTeam": entry.get("team"),
                }
            )
            continue
        sub.setdefault("codeKeys", []).append(code_key)
        if norm(entry.get("team", "")) != norm(sub.get("team", "")):
            drift.append(
                {
                    "subconcept": sub["name"],
                    "codeKey": code_key,
                    "taxonomyTeam": entry.get("team"),
                    "assetsTeam": sub.get("team"),
                }
            )

    key_to_sub = {
        k: s["name"] for s in data["subconcepts"] for k in s.get("codeKeys", [])
    }
    code = defaultdict(list)
    unknown_keys = defaultdict(int)
    seen = set()
    for code_key, line, symbol, rel in scan_code(web, sha):
        target = key_to_sub.get(code_key)
        if not target:
            unknown_keys[code_key] += 1
            continue
        if (target, rel, symbol) in seen:
            continue
        seen.add((target, rel, symbol))
        code[target].append([rel, line, symbol])

    data |= {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "assets": f"{ATLASSIAN_SITE}/jira/assets/object-schema/{SCHEMA_ID}",
            "webRef": args.ref,
            "webSha": sha,
        },
        "code": {k: sorted(v) for k, v in sorted(code.items())},
        "drift": drift,
        "unmatchedTaxonomy": unmatched,
        "unknownCodeKeys": dict(sorted(unknown_keys.items())),
    }

    out = Path(args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE_SRC, out)
    source = out / "_source"
    source.mkdir()
    shutil.copy2(SKILL_DIR / "SKILL.md", source / "SKILL.md")
    for sub in ("scripts", "site"):
        shutil.copytree(
            SKILL_DIR / sub,
            source / sub,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    (out / "data.json").write_text(
        json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    )

    n_code = sum(len(v) for v in code.values())
    print(
        f"teams {len(data['teams'])}, concepts {len(data['concepts'])}, subconcepts {len(data['subconcepts'])}, "
        f"components {len(data['components'])}, code symbols {n_code}"
    )
    print(
        f"drift (taxonomy.yml vs Assets owner): {len(drift)}; taxonomy keys with no Assets match: {len(unmatched)}"
    )
    print(f"wrote {out}")


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--components", help="AQL export of objectSchemaId = 42")
    p.add_argument("--groups", help="AQL export of objectTypeId = 15")
    p.add_argument(
        "--from-api",
        action="store_true",
        help="fetch both exports with an Atlassian API token",
    )
    p.add_argument(
        "--web",
        default=os.environ.get("WEB", "/workspaces/web"),
        help="roverdotcom/web checkout",
    )
    p.add_argument(
        "--ref",
        default="origin/master",
        help="git ref to read taxonomy.yml and code from (default origin/master)",
    )
    p.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help=f"output directory (default {DEFAULT_OUT})",
    )
    build(p.parse_args())


if __name__ == "__main__":
    main()
