#!/usr/bin/env python3
"""Build the "Who owns that?" static site from Jira Assets exports and the web repo.

Inputs:
  --components  JSON from AQL `objectSchemaId = 42` (Technology Components: concepts,
                subconcepts and components in one result)
  --groups      JSON from AQL `objectTypeId = 15` (People Directory > Groups: the teams)
  --web         a checkout of roverdotcom/web, for taxonomy.yml, code subconcept tags,
                URL routes, CODEOWNERS and CODEWATCHERS

Either export can instead be fetched with --from-api (ATLASSIAN_EMAIL + ATLASSIAN_API_TOKEN).

Writes <out>/index.html, app.js, style.css (copied from ../site) and data.json, plus
<out>/_source/, a copy of this skill, so `yard pull who-owns-that` recovers the builder.
Stdlib only, except `pathspec` for CODEOWNERS matching (web's venv has it).
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
import tempfile
import types
import urllib.request
from collections import Counter
from collections import defaultdict
from datetime import datetime
from datetime import timezone
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
SITE_SRC = SKILL_DIR / "site"
# The People Directory stores only channel ids; names come from this map (id -> name).
SLACK_CHANNELS = SKILL_DIR / "scripts" / "slack_channels.json"
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
# bin/file-owners credits a file to a concept's team with this looser pattern.
FILE_CONCEPT_REF = re.compile(r"CONCEPTS\.(\w+)\.(\w+)")
CODEOWNERS = ".github/CODEOWNERS"
CODEWATCHERS = "danger/CODEWATCHERS"
# bin/subdivide-files defaults.
PURITY_THRESHOLD = 0.8
MIN_FILES = 3
NO_OWNER = "no_owner"
URL_CALLS = {"path", "re_path", "url"}
REACT_ROUTES = re.compile(r"^src/frontend/react-app/src/routes/[^/]+\.tsx?$")
TS_PATH_PROP = re.compile(
    r"^\s*path:\s*(?:'([^']*)'|\"([^\"]*)\"|`([^`]*)`|([A-Za-z_$][\w$.]*))"
)
TS_CONCEPT_PROP = re.compile(r"^\s*concept:\s*CONCEPTS\.(\w+)\.(\w+)")
TS_PAGE_PROP = re.compile(r"^\s*pageName:\s*['\"]([^'\"]+)")
TS_CONST_STR = re.compile(
    r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*['\"`]([^'\"`$]*)['\"`]"
)
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

    groups = [
        {"id": obj["id"], "key": obj["objectKey"]} | attrs(obj, GROUP_ATTRS)
        for obj in groups_export["objects"]
    ]
    return {
        "concepts": sorted(concepts, key=by_name),
        "subconcepts": sorted(subconcepts, key=by_name),
        "components": sorted(components, key=by_name),
        "groups": groups,
    }


def by_name(r: dict) -> str:
    return (r.get("name") or "").lower()


def select_teams(
    groups: list[dict], owning: set[str], handles: dict[str, set[str]]
) -> list[dict]:
    """Groups covers the whole company; keep only teams that own something."""
    teams = [g for g in groups if g.get("name") in owning]
    for name in sorted(n for n in owning - {t.get("name") for t in teams} if n):
        teams.append({"name": name, "missingFromDirectory": True})
    for t in teams:
        if t["name"] in handles:
            t["github"] = sorted(handles[t["name"]])
        if t["name"].startswith("@") and "/" not in t["name"]:
            t["person"] = True
    return sorted(teams, key=by_name)


def team_resolver(groups: list[dict], taxonomy_teams: dict[str, str]):
    """Map a CODEOWNERS handle like @roverdotcom/client-platform to a People Directory name."""
    known = {}
    for field in ("name", "context"):
        for g in groups:
            values = g.get(field) or []
            for value in [values] if isinstance(values, str) else values:
                for key in name_keys(value):
                    known.setdefault(key, g["name"])

    def resolve(handle: str) -> str:
        # The same normalization as normalize_team in bin/file-owners.
        slug = (
            handle.removeprefix("@roverdotcom/")
            .removesuffix("-contractors")
            .replace("-", "_")
        )
        for candidate in (taxonomy_teams.get(slug), slug):
            for key in name_keys(candidate):
                if key in known:
                    return known[key]
        return taxonomy_teams.get(slug) or handle

    return resolve


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


def concept_files(web: Path, ref: str) -> dict[str, str]:
    """Every file at ref that mentions CONCEPTS.x.y, except the generated taxonomy."""
    listing = subprocess.run(
        ["git", "-C", str(web), "grep", "-l", "-E", r"CONCEPTS\.\w+\.\w+", ref],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    # git grep on a tree prints "<ref>:<path>".
    files = [f.split(":", 1)[1] for f in listing]
    return git_files(web, ref, [f for f in files if f not in GENERATED])


def scan_code(texts: dict[str, str]) -> list[tuple[str, int, str, str]]:
    tags = []
    for rel, text in texts.items():
        if SKIP_PATH.search(rel):
            continue
        if rel.endswith(".py"):
            tags += python_tags(text, rel)
        elif rel.endswith((".ts", ".tsx")):
            tags += ts_tags(text, rel)
    return tags


def web_module(web: Path, ref: str, path: str) -> types.ModuleType:
    """Load a helper script from web at ref, so the site agrees with bin/file-owners."""
    text = git_files(web, ref, [path]).get(path)
    if text is None:
        die(f"no {path} at {ref}")
    module = types.ModuleType(Path(path).stem.replace("-", "_"))
    exec(compile(text, path, "exec"), module.__dict__)
    return module


def path_ownership(
    web: Path, ref: str, texts: dict[str, str], key_team: dict[str, str], resolve
) -> tuple[dict, dict[str, set[str]]]:
    """Owners of every tracked file, the way bin/file-owners and bin/subdivide-files see them.

    Each file gets its CODEOWNERS owners, then CODEWATCHERS, then the teams of the
    CONCEPTS keys it mentions; the first is its primary owner. To keep data.json small,
    a directory stores its most common owner set and only the files that differ are listed.
    """
    try:
        from pathspec.patterns.gitwildmatch import GitWildMatchPattern
    except ImportError:
        die("CODEOWNERS matching needs pathspec; run with web's venv python")
    ownership = web_module(web, ref, "bin/ownership.py")
    subdivide = web_module(web, ref, "bin/subdivide-files").subdivide
    rule_texts = git_files(web, ref, [CODEOWNERS, CODEWATCHERS])
    if CODEOWNERS not in rule_texts:
        die(f"no {CODEOWNERS} at {ref}")
    with tempfile.TemporaryDirectory() as tmp:

        def rules(path: str, compile_fn):
            copy = Path(tmp) / Path(path).name
            copy.write_text(rule_texts.get(path, ""))
            return ownership.parse_rules(str(copy), compile_fn)

        co_rules = rules(CODEOWNERS, lambda p: GitWildMatchPattern(p).regex)
        cw_rules = rules(
            CODEWATCHERS, lambda p: re.compile(ownership.codewatchers_to_regex(p))
        )

    file_concepts = {}
    for rel, text in texts.items():
        keys = dict.fromkeys(f"{c}.{s}" for c, s in FILE_CONCEPT_REF.findall(text))
        teams = [key_team[k] for k in keys if key_team.get(k)]
        if teams:
            file_concepts[rel] = teams

    files = subprocess.run(
        ["git", "-C", str(web), "ls-tree", "-r", "--name-only", "-z", ref],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")[:-1]
    owner_sets, set_ids = [[]], {(): 0}
    owner_of, primary = {}, {}
    handles = defaultdict(set)
    with_codeowners = 0
    for f in files:
        entries = []
        for source, found in (
            ("codeowners", ownership.find_codeowners(f, co_rules)),
            ("codewatchers", ownership.find_codewatchers(f, cw_rules)),
        ):
            for handle in found:
                team = resolve(handle)
                handles[team].add(handle)
                entries.append((team, source))
        with_codeowners += any(source == "codeowners" for _, source in entries)
        entries += [(t, "concepts") for t in file_concepts.get(f, [])]
        entries = tuple(dict.fromkeys(entries))
        if entries not in set_ids:
            set_ids[entries] = len(owner_sets)
            owner_sets.append([list(e) for e in entries])
        owner_of[f] = set_ids[entries]
        primary[f] = entries[0][0] if entries else NO_OWNER

    by_dir = defaultdict(list)
    for f in files:
        by_dir[f.rpartition("/")[0]].append(f)
    dirs, exceptions = {}, {}
    for d, members in sorted(by_dir.items()):
        default = Counter(owner_of[f] for f in members).most_common(1)[0][0]
        dirs[d] = [default, len(members)]
        exceptions.update({f: owner_of[f] for f in members if owner_of[f] != default})

    # File and owned-file counts for "dir/*" (direct) and "dir/**" (recursive) globs.
    direct, recursive = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for f in files:
        owned = int(primary[f] != NO_OWNER)
        d = f.rpartition("/")[0]
        direct[d][0] += 1
        direct[d][1] += owned
        parts = d.split("/") if d else []
        for i in range(len(parts) + 1):
            counts = recursive["/".join(parts[:i])]
            counts[0] += 1
            counts[1] += owned
    globs = []
    for g in subdivide("", primary, PURITY_THRESHOLD, MIN_FILES):
        base = g.glob.rstrip("*").rstrip("/")
        files_n, owned_n = (recursive if g.glob.endswith("**") else direct)[base]
        team = None if g.team == NO_OWNER else g.team
        globs.append([g.glob, team, round(g.purity, 2), files_n, owned_n])

    # Sorted paths share long prefixes, so each stores only what differs from the last.
    encoded, prev = [], ""
    for d, (default, n) in dirs.items():
        shared = len(os.path.commonprefix([prev, d]))
        encoded.append([shared, d[shared:], default, n])
        prev = d

    team_files = Counter(t for t in primary.values() if t != NO_OWNER)
    return {
        "owners": owner_sets,
        "dirs": encoded,
        "files": exceptions,
        "map": globs,
        "teamFiles": dict(sorted(team_files.items())),
        "stats": {
            "files": len(files),
            "codeowners": with_codeowners,
            "owned": sum(1 for t in primary.values() if t != NO_OWNER),
            "codeownersRules": len(co_rules),
            "codewatchersRules": len(cw_rules),
        },
    }, handles


def call_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    return func.attr if isinstance(func, ast.Attribute) else ""


def own_concept(node: ast.AST) -> str | None:
    """The first CONCEPTS.x.y inside node, not counting nested URL patterns."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        sub = stack.pop(0)
        if isinstance(sub, ast.Call) and call_name(sub.func) in URL_CALLS | {
            "label_url_resolver"
        }:
            continue
        if (
            isinstance(sub, ast.Attribute)
            and isinstance(sub.value, ast.Attribute)
            and isinstance(sub.value.value, ast.Name)
            and sub.value.value.id == "CONCEPTS"
        ):
            return f"{sub.value.attr}.{sub.attr}"
        stack.extend(ast.iter_child_nodes(sub))
    return None


def django_routes(text: str, rel: str) -> list[tuple]:
    """URL patterns labelled with a subconcept, directly or by label_url_resolver.

    A pattern is relative to wherever its urls.py is included, so it is not a full URL.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    rows = []

    def visit(node: ast.AST, inherited: str | None) -> None:
        if isinstance(node, ast.Call):
            name = call_name(node.func)
            if name == "label_url_resolver" and node.args:
                inherited = own_concept(ast.Expr(node.args[0])) or inherited
            elif (
                name in URL_CALLS
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                key = own_concept(node) or inherited
                url_name = next(
                    (
                        k.value.value
                        for k in node.keywords
                        if k.arg == "name" and isinstance(k.value, ast.Constant)
                    ),
                    "",
                )
                if key:
                    rows.append(
                        ("django", node.args[0].value, url_name, key, rel, node.lineno)
                    )
        for child in ast.iter_child_nodes(node):
            visit(child, inherited)

    visit(tree, None)
    return rows


def react_routes(text: str, rel: str) -> list[tuple]:
    """Route objects in react-app/src/routes with a `concept`, read line by line.

    A route without its own concept takes the one a trailing `.map(...)` adds to every
    route in the file. Paths that are imported constants keep the constant's name.
    """
    consts = {}
    for line in text.splitlines():
        if m := TS_CONST_STR.match(line):
            consts[m.group(1)] = m.group(2)
    stack, done, map_line = [], [], None
    for lineno, line in enumerate(text.splitlines(), 1):
        if map_line is None and re.search(r"\]\s*\.map\(", line):
            map_line = lineno
        if stack:
            if m := TS_PATH_PROP.match(line):
                value = next(g for g in m.groups() if g is not None)
                stack[-1].setdefault("path", (consts.get(value, value), lineno))
            elif m := TS_CONCEPT_PROP.match(line):
                stack[-1].setdefault("concept", f"{m.group(1)}.{m.group(2)}")
            elif m := TS_PAGE_PROP.match(line):
                stack[-1].setdefault("page", m.group(1))
        for ch in line:
            if ch == "{":
                stack.append({"line": lineno})
            elif ch == "}" and stack:
                done.append(stack.pop())
    default = next(
        (
            o["concept"]
            for o in done
            if "concept" in o and "path" not in o and map_line and o["line"] >= map_line
        ),
        None,
    )
    return [
        (
            "react",
            o["path"][0],
            o.get("page", ""),
            o.get("concept") or default,
            rel,
            o["path"][1],
        )
        for o in done
        if "path" in o and (o.get("concept") or default)
    ]


def url_routes(texts: dict[str, str], key_to_sub: dict[str, str]) -> list[list]:
    rows = []
    for rel, text in texts.items():
        if SKIP_PATH.search(rel):
            continue
        if rel.endswith("urls.py"):
            rows += django_routes(text, rel)
        elif REACT_ROUTES.match(rel):
            rows += react_routes(text, rel)
    return sorted(
        [kind, pattern, name, key_to_sub[key], rel, line]
        for kind, pattern, name, key, rel, line in rows
        if key in key_to_sub
    )


def parse_taxonomy(text: str) -> tuple[dict, dict[str, str]]:
    """concept.subconcept -> {name: 'Concept: Subconcept', team} from taxonomy.yml, plus
    team slug -> description.

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
    return result, teams


def name_keys(name: str | None) -> list[str]:
    """`inbox_chat` should match "Inbox & Chat", so also compare with & dropped."""
    if not name:
        return []
    return [norm(name), re.sub(r"[^a-z0-9]+", "", name.lower())]


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
    if not data["subconcepts"] or not data["components"] or not data["groups"]:
        die(
            "an export is missing subconcepts, components or teams; refusing to publish an empty site"
        )

    web = Path(args.web).resolve()
    sha = subprocess.run(
        ["git", "-C", str(web), "rev-parse", "--verify", f"{args.ref}^{{commit}}"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not sha:
        die(
            f"{args.ref} is not a commit in {web}; run `git -C {web} fetch origin master`"
        )
    taxonomy_text = git_files(web, sha, ["taxonomy.yml"]).get("taxonomy.yml")
    if not taxonomy_text:
        die(f"no taxonomy.yml at {args.ref}")
    taxonomy, taxonomy_teams = parse_taxonomy(taxonomy_text)
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
    data_subs = {s["name"]: s for s in data["subconcepts"]}
    key_team = {}
    for code_key, entry in taxonomy.items():
        sub = data_subs.get(key_to_sub.get(code_key))
        team = (sub or {}).get("team") or entry.get("team")
        if team and norm(team) != norm(NO_OWNER):
            key_team[code_key] = team

    texts = concept_files(web, sha)
    resolve = team_resolver(data["groups"], taxonomy_teams)
    paths, handles = path_ownership(web, sha, texts, key_team, resolve)
    routes = url_routes(texts, key_to_sub)

    groups = data.pop("groups")
    owning = (
        {s.get("team") for s in data["subconcepts"]}
        | {c.get("team") for c in data["components"]}
        | {team for owners in paths["owners"] for team, _ in owners}
    )
    data["teams"] = select_teams(groups, owning, handles)
    channels = json.loads(SLACK_CHANNELS.read_text()) if SLACK_CHANNELS.exists() else {}
    unnamed = []
    for t in data["teams"]:
        if t.get("slack") in channels:
            t["slackName"] = channels[t["slack"]]
        elif t.get("slack"):
            unnamed.append(t["slack"])

    code = defaultdict(list)
    unknown_keys = defaultdict(int)
    seen = set()
    for code_key, line, symbol, rel in scan_code(texts):
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
        "routes": routes,
        "paths": paths,
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
    st = paths["stats"]
    print(
        f"files {st['files']}: {st['codeowners']} with a CODEOWNERS owner, {st['owned']} with any owner; "
        f"{len(paths['map'])} ownership globs; URL routes {len(routes)}"
    )
    if unnamed:
        print(
            f"Slack channels missing from {SLACK_CHANNELS.name}: {' '.join(sorted(unnamed))}"
        )
    print(f"data.json {(out / 'data.json').stat().st_size // 1024} KB")
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
