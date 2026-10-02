# Mermaid layout for whiteboard slides

Mermaid has no aspect-ratio setting. You steer the shape with flow direction,
subgraph rows, and spacing, then confirm with `scripts/measure.py`. Every number
below was measured with Mermaid 11.4.1 at the 17px font set in `render.py`.

## Target shape

Width ÷ height between **0.75 (3:4) and 1.33 (4:3)**. 1.0 is fine. A chain of
six boxes in one row or one column is unreadable on a slide. `measure.py`
flags anything outside 0.7–1.45.

Boxes are wider than they are tall, so a grid's box count is not its pixel
shape. Three boxes across by two rows comes out near 2:1, and two across by
three rows comes out near 1:1.

## Patterns that worked

| Shape of the content | Layout | Measured |
| --- | --- | --- |
| Tree: one source fanning out to 2–3 branches | `flowchart TB` plus tight spacing (below) | 5.66 → 0.84 |
| Two entry points merging into one path, then splitting | `flowchart TB` plus tight spacing | 6.30 → 0.71 |
| Linear chain of 6 steps | Three rows of two: `TB` outside, `LR` subgraph rows | 11.30 → 1.05 |
| Before vs after, 3 and 4 steps | Two `TB` columns side by side, joined with `~~~` | 12.41 → 1.05 |
| Sequence diagram with 3 participants | Leave as is | 1.40 |

### Rows: a long chain wrapped into a snake

```
flowchart TB
  subgraph R1 [" "]
    direction LR
    A --> B
  end
  subgraph R2 [" "]
    direction LR
    C --> D
  end
  R1 --> R2
  style R1 fill:none,stroke:none
  style R2 fill:none,stroke:none
```

Link **subgraph to subgraph** (`R1 --> R2`), never a node in one row to a node in
the next. If any node inside a subgraph links outside it, Mermaid ignores that
subgraph's `direction` and the row collapses into a column.

### Columns: two groups side by side

```
flowchart LR
  subgraph BEFORE["Before PR 123"]
    direction TB
    b1 --> b2 --> b3
  end
  subgraph AFTER["After PR 123"]
    direction TB
    a1 --> a2 --> a3 --> a4
  end
  BEFORE ~~~ AFTER
```

Without the invisible `BEFORE ~~~ AFTER` link, Mermaid stacked the two columns
into one 1×7 column (0.27). Linking `b1 ~~~ a1` instead spread everything into
one wide row (4.00).

### Tight spacing for tall `TB` diagrams

Put this first in the diagram. It merges with the global init from `render.py`.

```
%%{init: {"flowchart": {"rankSpacing": 28, "nodeSpacing": 70}}}%%
```

It brought a TB tree from 0.68 to 0.84 by shortening the rows and widening the
gaps between neighbors.

## Labels

- **Wrap at about 22 characters** with `<br/>`, breaking long identifiers after an
  underscore: `update_order_<br/>with_sales_tax(id)`. A long single line is the
  usual cause of clipped box text.
- **A leading underscore plus a line-final underscore turns into italics.**
  `"_carry_over_<br/>seller_completed"` renders as *carry_over*. `#95;` doesn't
  help because Mermaid decodes it before parsing markdown. Keep an identifier that
  starts with `_` whole on one line: `"_carry_over_seller_completed<br/>(previous, new)"`.
- **No `#` in labels.** Mermaid reads `#...;` as an entity code. Write `PR 102311`.
- **Keep subgraph titles under about 20 characters.** A longer title wraps, and the
  second line is drawn behind the first node.
- Size text only through the init `fontSize`. Mermaid measures boxes using that
  value, so changing the font with page CSS clips labels.

## In the artifact

- The artifact host renders `<pre class="mermaid">` blocks itself. Don't load
  Mermaid on the page. `render.py` HTML-escapes the diagram source, and Mermaid
  reads the decoded text.
- The host's Mermaid version may differ from the measuring copy, so treat
  `measure.py` as a close estimate. The page also lets overflowing label text
  show (`foreignObject{overflow:visible}`) as a safety net.
