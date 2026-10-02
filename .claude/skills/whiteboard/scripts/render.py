"""Render a whiteboard deck file into a single artifact page.

Usage: python3 render.py path/to/deck.yaml [out.html]
Writes index.html next to the deck unless an output path is given.
"""

import html
import json
import sys
from pathlib import Path

import yaml


TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template.html"

# Prepended to every diagram. fontSize drives Mermaid's own box measurement, so
# size text here rather than with page CSS, which would clip labels.
INIT = (
    '%%{init: {"themeVariables": {"fontSize": "17px"}, "flowchart": {"padding": 14}, '
    '"sequence": {"messageFontSize": 17, "noteFontSize": 16, "actorFontSize": 17}}}%%\n'
)
LEVELS = {1: "Big picture", 2: "One box opened", 3: "Code"}


def load(deck_path):
    deck = yaml.safe_load(Path(deck_path).read_text())
    ids = [s["id"] for s in deck["slides"]]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        sys.exit(f"duplicate slide ids: {sorted(dupes)}")
    for s in deck["slides"]:
        if s.get("parent") and s["parent"] not in ids:
            sys.exit(f"slide {s['id']} has unknown parent {s['parent']}")
    return deck


def crumbs(slide, by_id):
    path = []
    while slide:
        path.append(slide)
        slide = by_id.get(slide["parent"]) if slide.get("parent") else None
    return list(reversed(path))


def inline(text):
    parts = html.escape(text).split("`")
    return "".join(f"<code>{p}</code>" if i % 2 else p for i, p in enumerate(parts))


def section(i, s, slides, by_id):
    crumb = " <span class=sep>/</span> ".join(
        f'<a href="#{c["id"]}">{html.escape(c["title"])}</a>'
        if c is not s
        else f"<span>{html.escape(c['title'])}</span>"
        for c in crumbs(s, by_id)
    )
    parent = by_id.get(s["parent"]) if s.get("parent") else None
    up = (
        f'<a class="up" href="#{parent["id"]}">Zoom out to “{html.escape(parent["title"])}”</a>'
        if parent
        else ""
    )
    focus = (
        f'<span class="focus">Opening <code>{html.escape(s["focus"])}</code></span>'
        if s.get("focus")
        else ""
    )
    notes = "".join(f"<li>{inline(n)}</li>" for n in s["notes"])
    evidence = "".join(
        f"<tr><th>{html.escape(k)}</th><td><code>{html.escape(v)}</code></td></tr>"
        for k, v in (s.get("evidence") or {}).items()
    )
    return f"""
<section class="slide" id="{s["id"]}" data-i="{i}">
  <header class="slide-head">
    <div class="meta"><span class="lvl l{s["level"]}">Level {s["level"]} · {LEVELS[s["level"]]}</span>{focus}<span class="count">{i + 1} / {len(slides)}</span></div>
    <nav class="crumbs">{crumb}</nav>
    <h2>{html.escape(s["title"])}</h2>
  </header>
  <div class="board"><pre class="mermaid">{html.escape(INIT + s["diagram"])}</pre></div>
  <ul class="notes">{notes}</ul>
  <details class="evidence"><summary>Show me the code</summary><div class="tw"><table>{evidence}</table></div></details>
  <footer class="slide-foot">{up}</footer>
</section>"""


def main():
    deck_path = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else deck_path.parent / "index.html"
    deck = load(deck_path)
    slides = deck["slides"]
    by_id = {s["id"]: s for s in slides}
    page = TEMPLATE.read_text()
    for key, value in {
        "{{TITLE}}": html.escape(deck["title"]),
        "{{EYEBROW}}": html.escape(deck.get("eyebrow", "Whiteboard session")),
        "{{QUESTION}}": html.escape(deck["question"]),
        "{{SOURCE}}": html.escape(deck["source"]),
        "{{SLIDES}}": "\n".join(
            section(i, s, slides, by_id) for i, s in enumerate(slides)
        ),
        "{{IDS}}": json.dumps([s["id"] for s in slides]),
    }.items():
        page = page.replace(key, value)
    out.write_text(page)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
