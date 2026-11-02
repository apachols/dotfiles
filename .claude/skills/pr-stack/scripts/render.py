#!/usr/bin/env python3
"""Render stack.json into the pr-stack page.

Usage: render.py <stack.json> [--out index.html]

Exits 1 when a branch is missing its nickname or summary, or a summary runs
past 50 words, so the page never ships with blank bubbles.
"""

import argparse
import json
import sys
from pathlib import Path


TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template.html"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stack")
    parser.add_argument("--out")
    args = parser.parse_args()

    stack_path = Path(args.stack)
    data = json.loads(stack_path.read_text())
    problems = []
    for name, branch in data["branches"].items():
        if name == data["defaultBranch"]:
            continue
        nickname = branch.get("nickname") or ""
        summary = branch.get("summary") or ""
        if not nickname or len(nickname.split()) > 2:
            problems.append(f"{name}: nickname must be 1 or 2 words, got {nickname!r}")
        if not summary:
            problems.append(f"{name}: summary is empty")
        elif len(summary.split()) > 50:
            problems.append(f"{name}: summary is {len(summary.split())} words, max 50")
    if problems:
        sys.exit("\n".join(problems))

    target = data["branches"][data["target"]]
    title = f"{target['nickname']} PR Stack"
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = (
        TEMPLATE.read_text()
        .replace("__TITLE__", title)
        .replace("__STACK_JSON__", payload)
    )

    out = Path(args.out) if args.out else stack_path.with_name("index.html")
    out.write_text(html)
    print(f"wrote {out} ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
