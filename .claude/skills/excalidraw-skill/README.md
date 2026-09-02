# Excalidraw Diagram Skill

A coding agent skill that generates beautiful and practical Excalidraw diagrams from natural language descriptions. Not just boxes-and-arrows - diagrams that **argue visually**.

Compatible with any coding agent that supports skills. For agents that read from `.claude/skills/` (like [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [OpenCode](https://github.com/nicepkg/OpenCode)), just drop it in and go.

## What Makes This Different

- **Diagrams that argue, not display.** Every shape/group of shapes mirrors the concept it represents — fan-outs for one-to-many, timelines for sequences, convergence for aggregation. No uniform card grids.
- **Evidence artifacts.** As an example, technical diagrams include real code snippets and actual JSON payloads.
- **Built-in visual validation.** A Playwright-based render pipeline lets the agent see its own output, catch layout issues (overlapping text, misaligned arrows, unbalanced spacing), and fix them in a loop before delivering.
- **Brand-customizable.** All colors and brand styles live in a single file (`references/color-palette.md`). Swap it out and every diagram follows your palette.

## Installation

This skill lives in the dotfiles repo and is symlinked into `~/.claude/skills/`, so it
is available to every project:

```bash
ln -s ~/git/dotfiles/.claude/skills/excalidraw-skill ~/.claude/skills/excalidraw-skill
```

Forked from [coleam00/excalidraw-diagram-skill](https://github.com/coleam00/excalidraw-diagram-skill).

## Setup

The skill includes a render pipeline that lets the agent visually validate its diagrams. There are two ways to set it up:

**Option A: Ask your coding agent (easiest)**

Just tell your agent: *"Set up the Excalidraw diagram skill renderer by following the instructions in SKILL.md."* It will run the commands for you.

**Option B: Manual**

```bash
cd ~/.claude/skills/excalidraw-skill/references
uv sync
uv run playwright install chromium
```

## Output directory

The skill asks once where new diagrams should go and remembers the answer in
`~/.config/excalidraw-skill/config.json` (outside this repo — it is machine-specific).

```bash
python3 references/output_dir.py --get          # show current default
python3 references/output_dir.py --set ~/diagrams  # change it
python3 references/output_dir.py --clear        # go back to being asked
```

## Vendored renderer

`references/vendor/` holds a self-contained `@excalidraw/excalidraw` 0.18.1 ESM bundle plus
the font faces it fetches at runtime, so rendering needs no network. Upstream imported
`@excalidraw/excalidraw` from esm.sh unpinned, which broke when a transitive dependency
404'd on the CDN.

To re-vendor (e.g. to take a newer Excalidraw):

```bash
cd references/vendor
npm i @excalidraw/excalidraw@<version> react react-dom esbuild
node build.mjs
```

`build.mjs` stubs the editor-only dependencies (mermaid, cytoscape, katex) and the
non-English locales, which `exportToSvg` never touches and which otherwise more than
double the bundle. Font faces come from the package's `dist/prod/fonts`; the 12MB Xiaolai
CJK family is deliberately excluded, so CJK text in a diagram falls back to a system font.

Because Chromium refuses ES module imports over `file://`, the render script serves
`references/` on an ephemeral localhost port for the duration of a render.

## Usage

Ask your coding agent to create a diagram:

> "Create an Excalidraw diagram showing how the AG-UI protocol streams events from an AI agent to a frontend UI"

The skill handles the rest — concept mapping, layout, JSON generation, rendering, and visual validation.

## Customize Colors

Edit `references/color-palette.md` to match your brand. Everything else in the skill is universal design methodology.

## File Structure

```
excalidraw-skill/
  SKILL.md                          # Design methodology + workflow
  references/
    color-palette.md                # Brand colors (edit this to customize)
    element-templates.md            # JSON templates for each element type
    json-schema.md                  # Excalidraw JSON format reference
    render_excalidraw.py            # Render .excalidraw to PNG
    render_template.html            # Browser template for rendering
    pyproject.toml                  # Python dependencies (playwright)
```
