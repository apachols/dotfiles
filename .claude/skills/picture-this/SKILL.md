---
name: picture-this
description: 'Answer the current question or rephrase the current answer with a rendered inline diagram, and then explain briefly how that diagram works.  Great for code architecture, bug reproduction, explaining a change set, tracing control flow, etc. Invoke with /picture-this; stays on until "stop picture-this" or "normal mode".'
---

# picture-this

To explain code, architecture, control flow, or data flow, or any other interaction between several moving parts, use the following output format:

1.  Rendered Diagram (`show_widget`)
2.  Bullet Points
3.  Relevant Files And Links List

Coding behavior is unchanged — this only shapes explanations. Keep following all
other instructions (tool use, permissions, project conventions).

## <1> Diagram Section Rules

Draw the diagram with `mcp__visualize__show_widget`. It renders inline in the
session, so the user sees a picture, not markup. Never emit a bare ```mermaid
fence, an artifact, or an ASCII diagram unless the fallback rule below applies.

Do not narrate the tool call. Call it, then write sections 2 and 3. Do not
restate in prose what the diagram already shows.

### Choosing the form

| Subject                                          | Form                                    |
| ------------------------------------------------ | --------------------------------------- |
| Control flow, call paths, request paths, state   | mermaid `flowchart` / `stateDiagram-v2` |
| Ordered interaction between actors over time      | mermaid `sequenceDiagram`                |
| Database schema, model relationships              | mermaid `erDiagram`                      |
| Class / type hierarchy                            | mermaid `classDiagram`                   |
| Anything layout-custom (nesting, annotated shapes) | hand-authored SVG                       |

Mermaid handles its own layout — reach for it first. Only hand-author SVG when
the picture needs placement mermaid can't express.

### Mermaid boilerplate

`show_widget` sandboxes the widget and allows esm.sh, so import mermaid there.
Use this init block as-is — `fontFamily` and `fontSize` drive layout
measurement, and deviating clips text.

```html
<style>
#d { overflow-x: auto; }
#d svg { max-width: 100%; height: auto; }
</style>
<div id="d" style="min-height:200px"></div>
<script type="module">
import mermaid from 'https://esm.sh/mermaid@11/dist/mermaid.esm.min.mjs';
const themeMode = document.documentElement.dataset.mode;
const dark = themeMode ? themeMode === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
await document.fonts.ready;
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  fontFamily: '"anthropic-sans", sans-serif',
  themeVariables: {
    darkMode: dark,
    fontSize: '13px',
    fontFamily: '"anthropic-sans", sans-serif',
    lineColor: dark ? '#9c9a92' : '#73726c',
    textColor: dark ? '#c2c0b6' : '#3d3d3a',
    primaryColor: dark ? '#2a2a28' : '#F5F4EF',
    primaryBorderColor: dark ? '#4a4a46' : '#c9c7bd',
    primaryTextColor: dark ? '#c2c0b6' : '#3d3d3a',
    clusterBkg: dark ? '#232321' : '#FAF9F5',
    clusterBorder: dark ? '#3d3d3a' : '#dcdad0',
  },
});
const { svg } = await mermaid.render('d-svg', `flowchart TB
  A["step one"] --> B["step two"]
`);
document.getElementById('d').innerHTML = svg;
</script>
```

### Visual Elements

| Category | Elements                             | Usage                        |
| -------- | ------------------------------------ | ---------------------------- |
| Grouping | mermaid `subgraph`, one per path     | Component / path boundaries  |
| Emphasis | `classDef` + `class`                 | Good path, gap, no-op        |
| Status   | `✓` `✗` `⏳` `🔄` `⚠️` `🔴`          | Inline in node labels        |
| Legend   | HTML `<div>` under the diagram       | Explain every symbol used    |

Semantic `classDef` palette — green for the working/eligible path, red for the
bug or ordering gap, grey for a no-op, dashed for an aside:

```
classDef ok   fill:#E7F3EC,stroke:#7FB894,color:#14532D;
classDef bad  fill:#FBEAE5,stroke:#E0A08C,color:#7C2D12;
classDef noop fill:#EDEDEA,stroke:#c9c7bd,color:#3d3d3a;
classDef note fill:transparent,stroke-dasharray:4 4,stroke:#a8a69c,color:#73726c;
```

Those fills are light-mode values. When `dark` is true, remap them after
rendering, or the text goes unreadable:

```js
if (dark) {
  const m = {'#E7F3EC':'#16301F','#7FB894':'#3F7554','#14532D':'#BFE3CC',
             '#FBEAE5':'#3A1C13','#E0A08C':'#8A4B33','#7C2D12':'#F2C9B8',
             '#EDEDEA':'#2a2a28'};
  document.querySelectorAll('#d [fill],#d [stroke]').forEach(el => {
    for (const a of ['fill','stroke']) {
      const v = (el.getAttribute(a) || '').toUpperCase();
      const hit = Object.keys(m).find(k => k.toUpperCase() === v);
      if (hit) el.setAttribute(a, m[hit]);
    }
    const st = el.getAttribute('style');
    if (st) el.setAttribute('style', Object.entries(m).reduce((s,[k,v]) => s.replace(new RegExp(k,'gi'), v), st));
  });
}
```

### Formatting Rules

| Rule           | Value                              | Reason                          |
| -------------- | ---------------------------------- | ------------------------------- |
| Node labels    | `file.py:LINE` + what happens       | Same specificity as section 2   |
| Line breaks    | `<br/>` inside `"…"` labels         | Keeps nodes narrow              |
| Width          | `overflow-x: auto` on the container | Wide diagrams scroll, not clip  |
| Colors         | Only via the `classDef` palette     | Survives light and dark mode    |
| Legend         | Whenever symbols or colors appear   | Self-documenting                |
| `title`        | Specific snake_case, not "diagram"  | Names the download, disambiguates |

- Control flow and call stacks: `flowchart TB`. Request paths: `flowchart LR`,
  numbered steps.
- One diagram per answer. If two states matter (before/after, current/proposed),
  draw the one asked for and offer the other.

### Style reference

`mcp__visualize__read_me` holds the full design system. The boilerplate above is
enough for ordinary diagrams — call `read_me` only for an unusual form. Its
output exceeds the tool result limit and gets spilled to a file; `grep` that file
for the section you need instead of reading it whole.

### Fallback

If `mcp__visualize__show_widget` is unavailable (plain terminal, no visualize
MCP), fall back to plain ASCII: box drawing `┌─┬─┐ │ ├─┼─┤ └─┴─┘`, arrows
`──► ◄── ◄─► ──✗ ──✓`, max 80 characters wide, legend for every symbol. Say
in one line that the rendered diagram wasn't available.

## <2> Bullet Point Section Rules

- Name the actual function or file. Never "the system," "the handler," "the layer."
- If it doesn't fit, say what you left out and offer to expand that piece.

## <3> Relevant Files And Links section rules

### Files

- use relative paths from the repository root. example: src/aplaceforrover/CLAUDE.md
- include the relevant line number and or method or variable name

Example Output:

- src/aplaceforrover/recurring/flags.py:120 - recurring_schedule_web_management
- src/aplaceforrover/docker-dev.yml:14 - config block for webhook container

### Links

- Links should be printed in plain text, not marked up as a link, so they are easy to copy

Example Output:

https://github.com/
https://www.google.com/

## Persistence

After answering the question fully, or at a change of topic, or when the user moves on, please turn off picture-this mode and return to following all previous instructions.
