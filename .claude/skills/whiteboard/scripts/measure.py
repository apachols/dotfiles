"""Render every diagram in a deck with Mermaid and report its aspect ratio.

Usage: python3 measure.py path/to/deck.yaml [--shots]
Prints width x height and width/height per slide and flags anything outside
3:4..4:3. --shots also saves one PNG per diagram into <deck dir>/.measure/.

Needs playwright-cli on PATH and network access to cdn.jsdelivr.net once
(Mermaid is cached in ~/.cache/whiteboard/).
"""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import INIT  # noqa: E402
from render import load  # noqa: E402


MERMAID_VERSION = "11.4.1"
MERMAID_URL = (
    f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js"
)
CACHE = Path.home() / ".cache" / "whiteboard" / f"mermaid-{MERMAID_VERSION}.min.js"
# 3:4 is 0.75 and 4:3 is 1.33; the band allows a little slack either side.
LOW, HIGH = 0.7, 1.45

PAGE = """<!doctype html><meta charset=utf-8><body style="font:14px sans-serif">
<script src="mermaid.min.js"></script>
<script>
const D = %s;
mermaid.initialize({startOnLoad: false});
(async () => {
  const out = {};
  let n = 0;
  for (const [k, v] of Object.entries(D)) {
    try {
      const {svg} = await mermaid.render("m" + n++, v);
      const div = document.createElement("div");
      div.innerHTML = svg; div.id = "box-" + k; document.body.appendChild(div);
      const r = div.querySelector("svg").getBBox();
      out[k] = [Math.round(r.width), Math.round(r.height)];
    } catch (e) { out[k] = "ERR " + e.message; }
  }
  window.OUT = out;
})();
</script>"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def cli(*args):
    return subprocess.run(
        ["playwright-cli", *args], capture_output=True, text=True
    ).stdout


def eval_result(expr):
    lines = cli("eval", expr).splitlines()
    if "### Result" not in lines:
        return None
    value = json.loads(lines[lines.index("### Result") + 1])
    return json.loads(value) if value else None


def main():
    deck_path = Path(sys.argv[1]).resolve()
    shots = "--shots" in sys.argv
    work = deck_path.parent / ".measure"
    work.mkdir(exist_ok=True)
    os.chdir(work)  # playwright-cli writes its session logs into the cwd

    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MERMAID_URL, CACHE)
    (work / "mermaid.min.js").write_bytes(CACHE.read_bytes())

    deck = load(deck_path)
    diagrams = {s["id"]: INIT + s["diagram"] for s in deck["slides"]}
    (work / "index.html").write_text(PAGE % json.dumps(diagrams))

    # playwright-cli refuses file:// pages, so serve the folder over HTTP.
    handler = partial(QuietHandler, directory=str(work))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/index.html"

    try:
        cli("open", url)
        cli("goto", url)
        out = None
        for _ in range(40):
            out = eval_result("() => window.OUT ? JSON.stringify(window.OUT) : ''")
            if out:
                break
            time.sleep(0.5)
        if not out:
            sys.exit("Mermaid never finished rendering; is playwright-cli working?")

        bad = 0
        print(f"{'slide':<28} {'w x h':>11}  ratio")
        for sid, dims in out.items():
            if isinstance(dims, str):
                bad += 1
                print(f"{sid:<28} {dims}")
                continue
            w, h = dims
            ratio = w / h
            flag = "" if LOW <= ratio <= HIGH else "  <-- outside roughly 3:4..4:3"
            bad += bool(flag)
            print(f"{sid:<28} {w:>5} x {h:<5} {ratio:5.2f}{flag}")
            if shots:
                cli("screenshot", f"#box-{sid}", f"--filename={work / sid}.png")
        if shots:
            print(f"screenshots in {work}")
        sys.exit(1 if bad else 0)
    finally:
        cli("close")
        server.shutdown()


if __name__ == "__main__":
    main()
