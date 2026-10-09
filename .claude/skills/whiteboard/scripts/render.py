"""Render a whiteboard deck file into a single artifact page.

Usage: python3 render.py path/to/deck.yaml [out.html]
Renders each slide's .excalidraw file to SVG and PNG with the excalidraw-skill
renderer, inlines the SVGs, and writes index.html next to the deck unless an
output path is given. Prints each diagram's aspect ratio and exits 1 when one
falls outside roughly 3:4..4:3.
"""

import html
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml


SKILLS = Path(__file__).resolve().parents[2]
TEMPLATE = SKILLS / "whiteboard" / "assets" / "template.html"
EXCALIDRAW = next(
    p
    for p in (
        SKILLS / "excalidraw-skill" / "references",
        Path.home() / ".claude" / "skills" / "excalidraw-skill" / "references",
    )
    if (p / "render_excalidraw.py").exists()
)
# 3:4 is 0.75 and 4:3 is 1.33; the band allows a little slack either side.
LOW, HIGH = 0.7, 1.45


def load(deck_path):
    deck = yaml.safe_load(Path(deck_path).read_text())
    ids = [s["id"] for s in deck["slides"]]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        sys.exit(f"duplicate slide ids: {sorted(dupes)}")
    for s in deck["slides"]:
        if s.get("parent") and s["parent"] not in ids:
            sys.exit(f"slide {s['id']} has unknown parent {s['parent']}")
        s["diagram"] = Path(deck_path).parent / s.get("diagram", f"{s['id']}.excalidraw")
        if not s["diagram"].exists():
            sys.exit(f"slide {s['id']}: no diagram at {s['diagram']}")
    return deck


def draw(path):
    """Render one .excalidraw file and return its SVG markup and width/height ratio."""
    result = subprocess.run(
        ["uv", "run", "--project", str(EXCALIDRAW), "python",
         str(EXCALIDRAW / "render_excalidraw.py"), str(path), "--svg"],
        capture_output=True, text=True,
    )
    if result.returncode:
        sys.exit(f"{path}: {result.stderr.strip()}")
    svg = path.with_suffix(".svg").read_text()
    box = re.search(r'viewBox="[\d.-]+ [\d.-]+ ([\d.]+) ([\d.]+)"', svg)
    return svg, float(box.group(1)) / float(box.group(2))


def crumbs(slide, by_id):
    path = []
    while slide:
        path.append(slide)
        slide = by_id.get(slide["parent"]) if slide.get("parent") else None
    return list(reversed(path))


# A repo path with an extension, optionally followed by :line or :start-end.
CITATION = re.compile(r"[\w.-]+(?:/[\w.-]+)*\.[A-Za-z]{1,5}(?::\d+(?:-\d+)?)?")


def cite(text):
    """Escape evidence text and wrap each file citation so one click selects it."""
    out, pos = [], 0
    for m in CITATION.finditer(text):
        if "/" not in m.group() and ":" not in m.group():
            continue
        out.append(html.escape(text[pos : m.start()]))
        out.append(f'<code class="cite" title="Click to copy">{html.escape(m.group())}</code>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def inline(text):
    parts = html.escape(text).split("`")
    return "".join(f"<code>{p}</code>" if i % 2 else p for i, p in enumerate(parts))


def section(i, s, svg, by_id):
    crumb = " <span class=sep>/</span> ".join(
        f'<a href="#{c["id"]}">{html.escape(c["title"])}</a>'
        if c is not s
        else f"<span>{html.escape(c['title'])}</span>"
        for c in crumbs(s, by_id)
    )
    notes = "".join(f"<li>{inline(n)}</li>" for n in s["notes"])
    evidence = "".join(
        f"<tr><th>{html.escape(k)}</th><td>{cite(v)}</td></tr>"
        for k, v in (s.get("evidence") or {}).items()
    )
    return f"""
<section class="slide" id="{s["id"]}" data-i="{i}">
  <header class="slide-head">
    <nav class="crumbs">{crumb}</nav>
    <h2>{html.escape(s["title"])}</h2>
  </header>
  <div class="board">{svg}</div>
  <ul class="notes">{notes}</ul>
  <details class="evidence"><summary>Show me the code</summary><div class="tw"><table>{evidence}</table></div></details>
</section>"""


def main():
    deck_path = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else deck_path.parent / "index.html"
    deck = load(deck_path)
    slides = deck["slides"]
    by_id = {s["id"]: s for s in slides}
    bad = 0
    svgs = {}
    print(f"{'slide':<28} ratio")
    for s in slides:
        svgs[s["id"]], ratio = draw(s["diagram"])
        flag = "" if LOW <= ratio <= HIGH else "  <-- outside roughly 3:4..4:3"
        bad += bool(flag)
        print(f"{s['id']:<28} {ratio:5.2f}{flag}")
    page = TEMPLATE.read_text()
    for key, value in {
        "{{TITLE}}": html.escape(deck["title"]),
        "{{EYEBROW}}": html.escape(deck.get("eyebrow", "Whiteboard session")),
        "{{QUESTION}}": html.escape(deck["question"]),
        "{{SOURCE}}": html.escape(deck["source"]),
        "{{SLIDES}}": "\n".join(
            section(i, s, svgs[s["id"]], by_id) for i, s in enumerate(slides)
        ),
        "{{IDS}}": json.dumps([s["id"] for s in slides]),
    }.items():
        page = page.replace(key, value)
    out.write_text(page)
    print(f"wrote {out}; PNGs are next to each .excalidraw")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
