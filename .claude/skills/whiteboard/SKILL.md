---
name: whiteboard
description: 'Explain existing code as a zoomable whiteboard deck, like a system design interview run in reverse: one big-picture diagram, then one box opened at a time down to the lines of code, every box and arrow backed by a file:line. Publishes a slide-style claude.ai Artifact with back/next, breadcrumbs and "show me the code" evidence. Use when the user asks to whiteboard something, walk through how part of the codebase works, explain why a change or PR was needed for someone new to the area, or answer a reviewer''s "how does this actually happen" question. Invoke with /whiteboard.'
---

# whiteboard

Explain code one level at a time. Slide 1 shows the main building blocks. Each
later slide opens one box from its parent, until the last slides show the actual
lines. The output is a **deck file** (YAML) that `scripts/render.py` turns into
one artifact page. Content and rendering stay separate, so fixing a slide means
editing the deck and re-rendering.

The worked example is `examples/seller-completed-carry-over.yaml`. It answers
"why did this PR need to reload the order?" in five slides, for a reader new to
commerce. Read it before writing a first deck.

Needs `pyyaml`. `measure.py` also needs `playwright-cli` and one download of
Mermaid from cdn.jsdelivr.net, which it caches in `~/.cache/whiteboard/`.

## Session loop

1. **Pin the question.** Write it into the deck's `question` field as one
   sentence. When the user pasted a reviewer's question or an earlier agent's
   explanation, the deck answers that and the final message drafts a reply.
2. **Research before drawing.** Find the call site behind every box and arrow:
   grep, `git show`, or an Explore subagent for wide sweeps. Without this you
   draw the architecture you expect instead of the real one. See "Evidence".
3. **Write the deck** at `<scratchpad>/whiteboard/<slug>/deck.yaml`, starting
   with level 1. Ask where the user keeps decks only if they want to keep one.
4. **Render and measure.**
   ```bash
   python3 <skill>/scripts/render.py <deck>.yaml
   python3 <skill>/scripts/measure.py <deck>.yaml --shots
   ```
   Fix any slide `measure.py` flags (see Layout), and look at the PNGs for
   clipped or italicized labels. Re-run until it exits 0.
5. **Publish** `index.html` with the Artifact tool, with icon `diagram` on the
   first publish. Republish the same path after every change so the URL stays
   the same.
6. **Take corrections.** When the user says a box or arrow is wrong, fix its
   evidence first and then the diagram. Add slides when they ask to open another
   box.

## Deck format

```yaml
title: "Seller-completed on recurring refunds"   # page title, 2-5 words
eyebrow: "Whiteboard session · recurring sales tax · PR 101593"
question: "Why did PR 101593 need to reload the order before the carry-over?"
source: "roverdotcom/web PR 101593 head, plus master commit 916acb525a5"
slides:
- id: big-picture            # stable, used in URLs and breadcrumbs
  level: 1                   # 1 big blocks, 2 one block opened, 3 code
  parent: null
  title: "How a booking turns into money"
  diagram: |
    flowchart TB
      CONV[conversations] --> COM[commerce]
  notes:
    - "What flows where, and why. Backticks render as `code`."
  evidence:                  # key: box or edge id, value: file:line + what is there
    "CONV->COM": "conversations/models/request.py:1156 calls complete_checkout_off_session"
- id: off-session
  level: 2
  parent: big-picture
  focus: COM                 # the parent's box this slide opens
  ...
```

`render.py` rejects duplicate ids and unknown parents. Order slides so that
reading top to bottom walks down the zoom path. A sibling (a second level-3
slide under the same parent) goes after the first one's children.

## Rules for each slide

1. **Keep box ids stable across levels.** The box a slide opens (`focus`) keeps
   its id from the parent, so a reader can find it again.
2. **About 7 boxes per diagram.** If a diagram needs more, zoom in another level.
3. **Two or three bullets.** Each bullet says what flows where and why, not what
   the boxes are. Name the real function and file, never "the handler".
4. **Back every box and arrow with evidence.** It appears under "Show me the
   code".
5. **Keep the diagram between 3:4 and 4:3.** Chains of five or more boxes in one
   row or one column are the usual problem. `measure.py` flags them, and
   `references/mermaid-layout.md` has measured fixes.

## Evidence

- Take line numbers from the ref being explained. For a PR, that's the PR head
  (`git fetch origin pull/<n>/head:pr-<n>`, then
  `git show pr-<n>:<path> | grep -n ...`), not master or your working tree.
- Cite paths relative to the Django app (`commerce/interface_utils.py:79`), since
  the repo is full of duplicate file names.
- For "why did this change", find the commit that moved the behavior (`git show
  <sha> -- <path>`, then grep for the removed `^-` line) and cite both sides.
- Re-check claims from earlier agents or reviewers. If one said "likely", read
  the code that settles it, for example whether a value is a live model or a
  dataclass snapshot, and then state it plainly.
- Follow the consequence one step further than the bug. "The flag isn't set"
  becomes "so the refund order stops at INVOICED and the refund isn't issued",
  with its own file:line.

## Layout

Read `references/mermaid-layout.md` before writing diagrams. In short:

- Start flowcharts `TB`. Use `LR` only for three boxes or fewer in a row.
- Wrap a long chain into subgraph rows linked subgraph to subgraph.
- Put two groups side by side with `GROUP_A ~~~ GROUP_B`.
- Wrap labels at about 22 characters. Don't use `#`. Keep identifiers that start
  with `_` whole on one line.

## The page

`assets/template.html` holds the page: a sticky pager (back/next, numbered dots,
arrow keys and j/k), breadcrumbs, a "zoom out to parent" link, and light and
dark themes. Keep its pager logic. It marks the current slide as the last one
whose top has reached the nav bar. An IntersectionObserver band was tried first,
and it marked the wrong slide whenever a slide was short.

To change the look, edit the template, not `render.py`. The eyebrow, title,
question and source come from the deck.

## Final message

- The link, plus one line on what the deck covers.
- The answer in a few numbered steps, with file:line for each claim, so someone
  who never opens the deck still gets it.
- When the question came from someone else, a short drafted reply they can
  paste.
- What wasn't verified (tests not run, the page not looked at).
