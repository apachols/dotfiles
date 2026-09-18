#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown>=3.5", "pyyaml>=6"]
# ///
"""Manage the PR test-case results directory and render it as a static site.

Results live under a single directory (the "results dir"), remembered in
~/.claude/execute-test-case.json so it only has to be chosen once:

    <results dir>/
      index.html                          <- generated
      <YYYYMMDDTHHMMZ>-pr-<N>/
        run.json                          <- written by the agent
        README.md                         <- written by the agent
        issues.md                         <- written by the agent (optional friction log)
        index.html                        <- generated
        issues.html                       <- generated (only when issues.md exists)
        test-case-<K>/
          result.md                       <- written by the agent (YAML frontmatter + markdown)
          test-case.md                    <- written by the agent (verbatim PR test-case section)
          index.html                      <- generated
          screenshots/NN-slug.png

Every generated page is self-contained (inline CSS, relative links), so the
tree opens directly via file:// with no server.

Commands:

    testresults.py get-dir                    print the remembered results dir (exit 1 if unset)
    testresults.py set-dir PATH               remember PATH as the results dir (creates it)
    testresults.py new-run --pr N             create <results dir>/<stamp>-pr-N/, print its path
    testresults.py build [--results-dir DIR]  (re)generate every index.html, print the root file:// URL
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import markdown
import yaml

CONFIG_PATH = Path(os.environ.get("EXECUTE_TEST_CASE_CONFIG", "~/.claude/execute-test-case.json")).expanduser()
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
ISSUE_HEADING_RE = re.compile(r"^##\s+\S", re.MULTILINE)
RUN_NAME_RE = re.compile(r"\A(?P<stamp>[0-9]{8}T[0-9]{4}Z)(?:-pr-(?P<pr>[0-9]+))?")
PR_URL_TEMPLATE = "https://github.com/roverdotcom/web/pull/{pr}"

STATUS_LABELS = {"pass": "PASS", "fail": "FAIL", "skip": "SKIPPED", "blocked": "BLOCKED"}

CSS = """
:root {
  color-scheme: light dark;
  --bg: #fff; --fg: #1a1a1a; --muted: #6b6b6b; --line: #e2e2e2;
  --card: #fafafa; --accent: #1b6ac9;
  --pass-bg: #e7f6ec; --pass-fg: #1a7f3c;
  --fail-bg: #fdeaea; --fail-fg: #b3261e;
  --skip-bg: #f0f0f0; --skip-fg: #5c5c5c;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #17181a; --fg: #e6e6e6; --muted: #9a9a9a; --line: #2f3134;
    --card: #1e2023; --accent: #6cb2f5;
    --pass-bg: #17301f; --pass-fg: #6edc95;
    --fail-bg: #38191a; --fail-fg: #f2867f;
    --skip-bg: #26282b; --skip-fg: #a8a8a8;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
.wrap { max-width: 980px; margin: 0 auto; padding: 24px 20px 80px; }
a { color: var(--accent); }
nav { font-size: 13px; color: var(--muted); margin-bottom: 18px; }
nav a { text-decoration: none; }
nav a:hover { text-decoration: underline; }
h1 { font-size: 22px; margin: 0 0 4px; line-height: 1.3; }
h2 { font-size: 17px; margin: 32px 0 10px; padding-bottom: 6px; border-bottom: 1px solid var(--line); }
h3 { font-size: 15px; margin: 22px 0 8px; }
.sub { color: var(--muted); font-size: 13px; margin: 0 0 22px; }
.badge {
  display: inline-block; padding: 1px 8px; border-radius: 10px;
  font-size: 11px; font-weight: 700; letter-spacing: .04em; vertical-align: 2px;
}
.badge.pass { background: var(--pass-bg); color: var(--pass-fg); }
.badge.fail { background: var(--fail-bg); color: var(--fail-fg); }
.badge.skip, .badge.blocked, .badge.unknown { background: var(--skip-bg); color: var(--skip-fg); }
ul.cards { list-style: none; margin: 0; padding: 0; }
ul.cards li { border: 1px solid var(--line); border-radius: 8px; margin-bottom: 8px; background: var(--card); }
ul.cards a.row {
  display: flex; align-items: baseline; gap: 12px;
  padding: 13px 16px; text-decoration: none; color: inherit;
}
ul.cards a.row:hover { background: color-mix(in srgb, var(--accent) 8%, var(--card)); }
.row .name { font-weight: 600; }
.row .meta { color: var(--muted); font-size: 13px; margin-left: auto; text-align: right; }
.md table { border-collapse: collapse; margin: 12px 0; font-size: 14px; display: block; overflow-x: auto; }
.md th, .md td { border: 1px solid var(--line); padding: 6px 10px; text-align: left; vertical-align: top; }
.md th { background: var(--card); }
.md code, code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px;
  background: var(--card); border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; }
.md pre { background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: 12px 14px; overflow-x: auto; }
.md pre code { border: 0; padding: 0; background: none; }
.md blockquote { margin: 12px 0; padding: 2px 14px; border-left: 3px solid var(--line); color: var(--muted); }
figure { margin: 0 0 26px; }
figure img {
  display: block; max-width: 100%; width: auto; height: auto;
  border: 1px solid var(--line); border-radius: 8px; background: var(--card);
}
figcaption { font-size: 13px; color: var(--muted); margin-top: 6px; }
figcaption .fname { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.empty { color: var(--muted); border: 1px dashed var(--line); border-radius: 8px; padding: 22px; text-align: center; }
details.spec {
  border: 1px solid var(--line); border-radius: 8px; background: var(--card);
  padding: 10px 14px; margin: 0 0 22px;
}
details.spec > summary {
  cursor: pointer; font-size: 13px; font-weight: 600; color: var(--muted);
  letter-spacing: .02em;
}
details.spec > summary:hover { color: var(--fg); }
details.spec .md { margin-top: 10px; }
details.spec .md > :first-child { margin-top: 0; }
details.spec .md h2 { font-size: 15px; border: 0; margin: 18px 0 8px; }
details.spec .md h3 { font-size: 14px; }
details.spec details { margin: 10px 0; padding-left: 12px; border-left: 2px solid var(--line); }
details.spec details > summary { cursor: pointer; font-size: 13px; color: var(--muted); }
table.links { border-collapse: collapse; margin: 12px 0 0; font-size: 14px; width: 100%; }
table.links th, table.links td {
  border: 1px solid var(--line); padding: 6px 10px; text-align: left; vertical-align: top;
}
table.links th { background: var(--card); }
table.links td.kind { color: var(--muted); white-space: nowrap; }
a.notice {
  display: block; margin: 0 0 18px; padding: 11px 14px; text-decoration: none;
  border: 1px solid var(--line); border-left: 3px solid var(--fail-fg);
  border-radius: 8px; background: var(--fail-bg); color: var(--fail-fg); font-size: 14px;
}
a.notice:hover { filter: brightness(1.04); text-decoration: underline; }
a.notice .what { font-weight: 600; }
.issues h2 { font-size: 16px; }
"""


# --------------------------------------------------------------------------- config


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        return {}
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def configured_results_dir() -> Path | None:
    value = load_config().get("resultsDir")
    return Path(value).expanduser() if value else None


def resolve_results_dir(override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    configured = configured_results_dir()
    if configured is None:
        sys.exit(
            f"no results dir configured. Run `testresults.py set-dir PATH` first "
            f"(config file: {CONFIG_PATH})"
        )
    return configured.resolve()


# --------------------------------------------------------------------------- rendering


def render_page(title: str, breadcrumbs: list[tuple[str, str | None]], body: str) -> str:
    crumbs = " / ".join(
        f'<a href="{html.escape(href)}">{html.escape(label)}</a>' if href else html.escape(label)
        for label, href in breadcrumbs
    )
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<link rel="icon" href="data:,">'
        f"<title>{html.escape(title)}</title>"
        f"<style>{CSS}</style></head><body><div class=\"wrap\">"
        f"<nav>{crumbs}</nav>{body}</div></body></html>\n"
    )


def badge(status: str | None) -> str:
    key = (status or "unknown").lower()
    label = STATUS_LABELS.get(key, key.upper() or "UNKNOWN")
    css = key if key in STATUS_LABELS else "unknown"
    return f'<span class="badge {css}">{html.escape(label)}</span>'


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, text[match.end():]


LEADING_H1_RE = re.compile(r"\A\s*#\s+[^\n]*\n+")
LEADING_RESULT_RE = re.compile(r"\A\s*\*\*Result:[^\n]*\n+")
EMPTY_THEAD_RE = re.compile(r"<thead>\s*<tr>(?:\s*<th></th>)+\s*</tr>\s*</thead>\s*")


def strip_redundant_heading(md_text: str) -> str:
    """Drop the body's own title and Result line - the page header renders both."""
    md_text = LEADING_H1_RE.sub("", md_text, count=1)
    return LEADING_RESULT_RE.sub("", md_text, count=1)


def to_html(md_text: str) -> str:
    rendered = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "attr_list", "sane_lists", "md_in_html"],
    )
    return EMPTY_THEAD_RE.sub("", rendered)


BARE_DETAILS_RE = re.compile(r"<details(?![^>]*\bmarkdown=)([^>]*)>", re.IGNORECASE)


def enable_md_in_details(md_text: str) -> str:
    """PR bodies wrap manual steps in <details>; keep that markdown rendering."""
    return BARE_DETAILS_RE.sub(r'<details markdown="1"\1>', md_text)


def natural_key(value: str) -> list:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def caption_for(path: Path) -> str:
    stem = re.sub(r"\A\d+[-_]", "", path.stem)
    return stem.replace("-", " ").replace("_", " ").strip().capitalize()


def pretty_stamp(stamp: str) -> str:
    match = re.match(r"\A(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})Z\Z", stamp)
    if not match:
        return stamp
    y, mo, d, h, mi = match.groups()
    return f"{y}-{mo}-{d} {h}:{mi} UTC"


def rel_href(path: Path, start: Path) -> str:
    return str(path.relative_to(start)).replace("\\", "/")


# --------------------------------------------------------------------------- model


@dataclass
class AdminLink:
    url: str
    label: str
    scenario: str = ""
    kind: str = ""


def parse_admin_links(value) -> list[AdminLink]:
    """Read `adminLinks` from result.md frontmatter, tolerating loose shapes.

    Accepts a list of mappings (`url` plus optional `label`, `scenario`, `kind`),
    bare URL strings, or a `{label: url}` mapping. Entries with no URL are dropped.
    """
    if isinstance(value, dict):
        value = [{"label": key, "url": url} for key, url in value.items()]
    if not isinstance(value, list):
        return []
    links: list[AdminLink] = []
    for entry in value:
        if isinstance(entry, str):
            url, label, scenario, kind = entry.strip(), "", "", ""
        elif isinstance(entry, dict):
            url = str(entry.get("url") or entry.get("href") or "").strip()
            label = str(entry.get("label") or "").strip()
            scenario = str(entry.get("scenario") or "").strip()
            kind = str(entry.get("kind") or "").strip()
        else:
            continue
        if not url:
            continue
        links.append(
            AdminLink(url=url, label=label or url, scenario=scenario, kind=kind)
        )
    return links


@dataclass
class Case:
    directory: Path
    meta: dict
    body_md: str
    images: list[Path]
    spec_md: str = ""
    admin_links: list[AdminLink] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.directory.name

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.slug.replace("-", " ").capitalize())

    @property
    def label(self) -> str:
        number = self.meta.get("testCase")
        if number is not None:
            return f"Test Case {number}"
        return self.slug.replace("-", " ").title()

    @property
    def status(self) -> str | None:
        status = self.meta.get("status")
        return str(status) if status else None


@dataclass
class Run:
    directory: Path
    meta: dict = field(default_factory=dict)
    cases: list[Case] = field(default_factory=list)
    issues_md: str = ""

    @property
    def issue_count(self) -> int:
        """Entries in issues.md - one per `## ` heading, else 1 for loose prose."""
        if not self.issues_md:
            return 0
        return len(ISSUE_HEADING_RE.findall(self.issues_md)) or 1

    @property
    def issues_label(self) -> str:
        count = self.issue_count
        return f"{count} issue{'s' if count != 1 else ''} logged"

    @property
    def slug(self) -> str:
        return self.directory.name

    @property
    def title(self) -> str:
        return str(self.meta.get("title") or self.slug)

    @property
    def pr(self) -> int | None:
        pr = self.meta.get("pr")
        if pr is None:
            match = RUN_NAME_RE.match(self.slug)
            pr = match.group("pr") if match else None
        try:
            return int(pr) if pr is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def pr_url(self) -> str | None:
        if self.meta.get("prUrl"):
            return str(self.meta["prUrl"])
        return PR_URL_TEMPLATE.format(pr=self.pr) if self.pr else None

    @property
    def when(self) -> str:
        stamp = self.meta.get("finishedAt") or self.meta.get("startedAt")
        if stamp:
            return str(stamp).replace("T", " ").replace("Z", " UTC")
        match = RUN_NAME_RE.match(self.slug)
        return pretty_stamp(match.group("stamp")) if match else ""

    @property
    def status(self) -> str:
        statuses = {(case.status or "unknown").lower() for case in self.cases}
        if not statuses:
            return "unknown"
        for candidate in ("fail", "blocked", "unknown", "skip"):
            if candidate in statuses:
                return candidate
        return "pass"


def load_case(directory: Path) -> Case | None:
    result = directory / "result.md"
    if not result.is_file():
        return None
    meta, body = split_frontmatter(result.read_text(encoding="utf-8"))
    shots_dir = directory / "screenshots"
    search_dir = shots_dir if shots_dir.is_dir() else directory
    images = sorted(
        (p for p in search_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES),
        key=lambda p: natural_key(p.name),
    )
    spec = directory / "test-case.md"
    spec_md = spec.read_text(encoding="utf-8") if spec.is_file() else ""
    return Case(
        directory=directory,
        meta=meta,
        body_md=strip_redundant_heading(body),
        images=images,
        spec_md=enable_md_in_details(spec_md.strip()),
        admin_links=parse_admin_links(meta.get("adminLinks")),
    )


def load_run(directory: Path) -> Run | None:
    cases = [
        case
        for case in (
            load_case(child)
            for child in sorted(directory.iterdir(), key=lambda p: natural_key(p.name))
            if child.is_dir()
        )
        if case is not None
    ]
    if not cases:
        return None
    meta = {}
    manifest = directory / "run.json"
    if manifest.is_file():
        try:
            loaded = json.loads(manifest.read_text(encoding="utf-8"))
            meta = loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            meta = {}
    issues = directory / "issues.md"
    issues_md = issues.read_text(encoding="utf-8").strip() if issues.is_file() else ""
    return Run(directory=directory, meta=meta, cases=cases, issues_md=issues_md)


def discover_runs(results_dir: Path) -> list[Run]:
    if not results_dir.is_dir():
        return []
    runs = [
        run
        for run in (
            load_run(child)
            for child in results_dir.iterdir()
            if child.is_dir() and not child.name.startswith((".", "_"))
        )
        if run is not None
    ]
    return sorted(runs, key=lambda run: run.slug, reverse=True)


# --------------------------------------------------------------------------- pages


def write_index(results_dir: Path, runs: list[Run]) -> Path:
    if runs:
        rows = "".join(
            f'<li><a class="row" href="{html.escape(run.slug)}/index.html">'
            f'<span class="name">{html.escape(run.title)}</span> {badge(run.status)}'
            f'<span class="meta">{html.escape(run.when)}<br>'
            f'{len(run.cases)} case{"s" if len(run.cases) != 1 else ""}'
            + (f" &middot; PR #{run.pr}" if run.pr else "")
            + (f" &middot; {html.escape(run.issues_label)}" if run.issues_md else "")
            + "</span></a></li>"
            for run in runs
        )
        body = (
            f"<h1>Test results</h1><p class=\"sub\">{len(runs)} run{'s' if len(runs) != 1 else ''}, "
            f"newest first.</p><ul class=\"cards\">{rows}</ul>"
        )
    else:
        body = (
            '<h1>Test results</h1><p class="empty">No runs found under '
            f"<code>{html.escape(str(results_dir))}</code>.</p>"
        )
    target = results_dir / "index.html"
    target.write_text(render_page("Test results", [("Test results", None)], body), encoding="utf-8")
    return target


def issues_notice(run: Run, href: str) -> str:
    """Banner linking to the run's friction log; empty when the run was clean."""
    if not run.issues_md:
        return ""
    return (
        f'<a class="notice" href="{html.escape(href)}">'
        f'<span class="what">{html.escape(run.issues_label)}</span> during this run &mdash; '
        "environment problems and other fixable issues hit while testing. Read them &rarr;</a>"
    )


def write_issues_page(run: Run) -> Path:
    body = (
        f"<h1>Issues &mdash; {html.escape(run.title)}</h1>"
        '<p class="sub">Environment problems and other fixable issues hit while running this '
        "test run. Not test failures &mdash; see the case pages for verdicts.</p>"
        f'<div class="md issues">{to_html(run.issues_md)}</div>'
    )
    target = run.directory / "issues.html"
    target.write_text(
        render_page(
            f"Issues — {run.slug}",
            [("Test results", "../index.html"), (run.slug, "index.html"), ("Issues", None)],
            body,
        ),
        encoding="utf-8",
    )
    return target


def write_run_page(run: Run) -> Path:
    rows = "".join(
        f'<li><a class="row" href="{html.escape(case.slug)}/index.html">'
        f'<span class="name">{html.escape(case.label)}</span> {badge(case.status)}'
        f'<span class="meta">{html.escape(case.title)}<br>'
        f'{len(case.images)} screenshot{"s" if len(case.images) != 1 else ""}</span></a></li>'
        for case in run.cases
    )
    facts = [("Executed", run.when)]
    if run.pr_url and run.pr:
        facts.append(("PR", f'<a href="{html.escape(run.pr_url)}">#{run.pr}</a>'))
    for label, key in (("Ticket", "ticket"), ("Branch", "branch"), ("Commit", "commit"),
                       ("Target", "target"), ("Executed by", "executedBy")):
        if run.meta.get(key):
            facts.append((label, f"<code>{html.escape(str(run.meta[key]))}</code>"))
    fact_rows = "".join(
        f"<tr><th>{html.escape(label)}</th><td>{value}</td></tr>" for label, value in facts if value
    )
    body = (
        f"<h1>{html.escape(run.title)} {badge(run.status)}</h1>"
        f'<p class="sub"><code>{html.escape(run.slug)}</code></p>'
        f'{issues_notice(run, "issues.html")}'
        f'<div class="md"><table>{fact_rows}</table></div>'
        f'<h2>Cases</h2><ul class="cards">{rows}</ul>'
    )
    target = run.directory / "index.html"
    target.write_text(
        render_page(run.title, [("Test results", "../index.html"), (run.slug, None)], body),
        encoding="utf-8",
    )
    return target


def render_spec(case: Case) -> str:
    """Collapsed block with the PR's original test-case text, above the result."""
    if not case.spec_md:
        return ""
    return (
        '<details class="spec"><summary>Original test description (from the PR body)'
        "</summary>"
        f'<div class="md">{to_html(case.spec_md)}</div></details>'
    )


def render_admin_links(case: Case) -> str:
    if not case.admin_links:
        return ""
    has_scenario = any(link.scenario for link in case.admin_links)
    has_kind = any(link.kind for link in case.admin_links)
    head = (
        ("<th>Scenario</th>" if has_scenario else "")
        + "<th>Admin page</th>"
        + ("<th>Type</th>" if has_kind else "")
    )
    rows = "".join(
        "<tr>"
        + (f"<td>{html.escape(link.scenario)}</td>" if has_scenario else "")
        + f'<td><a href="{html.escape(link.url)}">{html.escape(link.label)}</a></td>'
        + (f'<td class="kind">{html.escape(link.kind)}</td>' if has_kind else "")
        + "</tr>"
        for link in case.admin_links
    )
    return (
        "<h2>Admin links</h2>"
        '<p class="sub">Django admin pages for the records this case created. '
        "Only resolvable while local dev is running.</p>"
        f'<table class="links"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'
    )


def write_case_page(run: Run, case: Case) -> Path:
    gallery = "".join(
        f'<figure><a href="{html.escape(rel_href(image, case.directory))}">'
        f'<img src="{html.escape(rel_href(image, case.directory))}" '
        f'alt="{html.escape(caption_for(image))}" loading="lazy"></a>'
        f'<figcaption><span class="fname">{html.escape(image.name)}</span> &mdash; '
        f"{html.escape(caption_for(image))}</figcaption></figure>"
        for image in case.images
    )
    if not gallery:
        gallery = '<p class="empty">No screenshots for this case.</p>'
    body = (
        f"<h1>{html.escape(case.label)} {badge(case.status)}</h1>"
        f'<p class="sub">{html.escape(case.title)}</p>'
        f'{issues_notice(run, "../issues.html")}'
        f"{render_spec(case)}"
        f'<div class="md">{to_html(case.body_md)}</div>'
        f"{render_admin_links(case)}"
        f"<h2>Screenshots</h2>{gallery}"
    )
    target = case.directory / "index.html"
    target.write_text(
        render_page(
            f"{case.label} — {run.slug}",
            [("Test results", "../../index.html"), (run.slug, "../index.html"), (case.label, None)],
            body,
        ),
        encoding="utf-8",
    )
    return target


# --------------------------------------------------------------------------- commands


def cmd_get_dir(_: argparse.Namespace) -> int:
    configured = configured_results_dir()
    if configured is None:
        print(f"no results dir configured ({CONFIG_PATH})", file=sys.stderr)
        return 1
    print(configured)
    return 0


def cmd_set_dir(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    config = load_config()
    config["resultsDir"] = str(target)
    save_config(config)
    print(f"results dir set to {target} (saved in {CONFIG_PATH})")
    return 0


def cmd_new_run(args: argparse.Namespace) -> int:
    results_dir = resolve_results_dir(args.results_dir)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%MZ")
    run_dir = results_dir / f"{stamp}-pr-{args.pr}"
    run_dir.mkdir(parents=True, exist_ok=True)
    print(run_dir)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    results_dir = resolve_results_dir(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    runs = discover_runs(results_dir)
    written = [write_index(results_dir, runs)]
    for run in runs:
        written.append(write_run_page(run))
        if run.issues_md:
            written.append(write_issues_page(run))
        for case in run.cases:
            written.append(write_case_page(run, case))
    for path in written:
        print(f"wrote {rel_href(path, results_dir)}")
    if not runs:
        print(f"no runs found under {results_dir}", file=sys.stderr)
    print(f"\nopen: {written[0].as_uri()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("get-dir", help="print the remembered results dir").set_defaults(func=cmd_get_dir)

    set_dir = sub.add_parser("set-dir", help="remember PATH as the results dir")
    set_dir.add_argument("path")
    set_dir.set_defaults(func=cmd_set_dir)

    new_run = sub.add_parser("new-run", help="create a timestamped run directory for a PR")
    new_run.add_argument("--pr", type=int, required=True)
    new_run.add_argument("--results-dir", help="override the remembered results dir")
    new_run.set_defaults(func=cmd_new_run)

    build = sub.add_parser("build", help="regenerate every index.html under the results dir")
    build.add_argument("--results-dir", help="override the remembered results dir")
    build.set_defaults(func=cmd_build)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
