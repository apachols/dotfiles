---
name: whiteboard
description: 'Explain existing code as a zoomable whiteboard deck, like a system design interview run in reverse: one system-level path from a user action to the external call, then one box opened at a time down to the lines of code, every box and arrow backed by a file:line. Publishes a slide-style claude.ai Artifact with back/next, breadcrumbs and "show me the code" evidence. Use when the user asks to whiteboard something, walk through how part of the codebase works, explain why a change or PR was needed for someone new to the area, or answer a reviewer''s "how does this actually happen" question. Invoke with /whiteboard.'
---

# whiteboard

Explain code one level at a time. Assume the reader already knows the big pieces
(which Django apps exist, that payments talks to Stripe), so skip the
architecture overview. Slide 1 is a system-design view of one path: it starts
with a user action and ends at the external call (Stripe, Avalara, a webhook).
Each later slide opens one box from its parent, until the last slides show the
actual lines. The output is a **deck file** (YAML) plus one Excalidraw diagram
per slide, which `scripts/render.py` turns into one artifact page. Content and
rendering stay separate, so fixing a slide means editing the deck or its
`.excalidraw` file and re-rendering.

The worked example is `examples/seller-completed-carry-over.yaml`. It answers
"why did this PR need to reload the order?" in four slides, for a reader new to
commerce. Read it and look at its PNGs before writing a first deck.

Diagrams are drawn with the `excalidraw-skill` skill; load it before drawing.
`render.py` needs `pyyaml`, `uv`, and that skill's renderer set up (`uv sync`
and `uv run playwright install chromium` in its `references/`).

## Session loop

1. **Pin the question.** Write it into the deck's `question` field as one
   sentence. When the user pasted a reviewer's question or an earlier agent's
   explanation, the deck answers that and the final message drafts a reply.
2. **Research before drawing.** Find the call site behind every box and arrow:
   grep, `git show`, or an Explore subagent for wide sweeps. Without this you
   draw the architecture you expect instead of the real one. See "Evidence".
3. **Write the deck** at `<scratchpad>/whiteboard/<slug>/deck.yaml`, starting
   with the user-action-to-external-call slide. Ask where the user keeps decks only if they want to keep one.
4. **Draw each slide** as `<slide id>.excalidraw` next to the deck. See
   "Drawing slides".
5. **Render and look.**
   ```bash
   python3 <skill>/scripts/render.py <deck>.yaml
   ```
   It renders every diagram to SVG and PNG, inlines the SVGs into
   `index.html`, and prints each diagram's aspect ratio. Read every PNG and
   run the excalidraw-skill fix loop on it. Re-run until it exits 0 and the
   PNGs look right.
6. **Publish** `index.html` with the Artifact tool, with icon `diagram` on the
   first publish. Republish the same path after every change so the URL stays
   the same.
7. **Take corrections.** When the user says a box or arrow is wrong, fix its
   evidence first and then the diagram. Add slides when they ask to open another
   box.

## Deck format

```yaml
title: "Seller-completed on recurring refunds"   # page title, 2-5 words
eyebrow: "Whiteboard session · recurring sales tax · PR 101593"
question: "Why did PR 101593 need to reload the order before the carry-over?"
source: "roverdotcom/web PR 101593 head, plus master commit 916acb525a5"
slides:
- id: off-session            # stable, used in URLs and breadcrumbs
  parent: null               # the first slide is the only root
  title: "Off-session checkout is the recurring payment path"
  # diagram: off-session.excalidraw   # optional; defaults to <id>.excalidraw
  notes:
    - "What flows where, and why. Backticks render as `code`."
  evidence:                  # key: element id or "A->B" arrow id, value: file:line + what is there
    "EBS->OFF": "api/current/views/conversation_views.py:1034 auto_accept_recurring_ebs_uc"
- id: refund-branch
  parent: off-session        # breadcrumbs come from parent
  ...
```

`render.py` rejects duplicate ids, unknown parents and missing diagrams. Order slides so that
reading top to bottom walks down the zoom path. A sibling (a second slide
under the same parent) goes after the first one's children.

## Rules for each slide

1. **Start at a user action and end at the external call.** That path is slide
   1. Don't add an overview slide of the apps above it.
2. **Keep box ids stable across levels.** The box a slide opens keeps the
   element id, label and color it had in the parent, so a reader can find it
   again.
3. **About 7 boxes per diagram.** If a diagram needs more, zoom in another level.
4. **Two or three bullets.** Each bullet says what flows where and why, not what
   the boxes are. Name the real function and file, never "the handler".
5. **Back every box and arrow with evidence.** It appears under "Show me the
   code".
6. **Keep the diagram between 3:4 and 4:3.** `render.py` flags anything
   outside roughly 0.7 to 1.45. Fix it by rearranging, for example wrapping a
   long chain into rows or putting two groups side by side.

## Evidence

- Take line numbers from the ref being explained. For a PR, that's the PR head
  (`git fetch origin pull/<n>/head:pr-<n>`, then
  `git show pr-<n>:<path> | grep -n ...`), not master or your working tree.
- Cite paths relative to the Django app (`commerce/interface_utils.py:79`), since
  the repo is full of duplicate file names.
  Write each one as `path:line` or `path:start-end`. `render.py` turns those into
  click-to-copy chips under "Show me the code".
- For "why did this change", find the commit that moved the behavior (`git show
  <sha> -- <path>`, then grep for the removed `^-` line) and cite both sides.
- Re-check claims from earlier agents or reviewers. If one said "likely", read
  the code that settles it, for example whether a value is a live model or a
  dataclass snapshot, and then state it plainly.
- Follow the consequence one step further than the bug. "The flag isn't set"
  becomes "so the refund order stops at INVOICED and the refund isn't issued",
  with its own file:line.

## Drawing slides

Follow `excalidraw-skill` for drawing technique, colors (its
`references/color-palette.md`), element templates and the render-view-fix
loop, with these overrides for slides:

- **Save next to the deck**, not in excalidraw-skill's remembered output
  directory, and skip its question about where to save.
- **Each slide is a simple diagram.** Zooming happens across slides, so skip
  that skill's multi-zoom and section-by-section build. The bottom slides,
  which show actual lines, may use a code-snippet evidence artifact.
- **Draw on a canvas about 1000 wide**, 750 to 1300 tall. The page scales it
  to the board width, so keep labels at 18 to 20 and titles at 24 to 28.
- **Use color for the argument.** Give the box where the bug or decision
  lives the warning or error color, and the outcome the success color, and
  keep the same color for a box on every slide it appears on.
- **Name element ids after the code** (`OFF`, `REF`, `CYCLE->OFF`) so evidence
  keys match them.

## The page

`assets/template.html` holds the page: a sticky pager (back/next, numbered
dots, arrow keys and j/k), breadcrumbs, and light and dark themes. In dark mode
it inverts the diagrams the way Excalidraw does. Keep its pager
logic. It marks the current slide as the last one whose top has reached the nav
bar. An IntersectionObserver band was tried first,
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
