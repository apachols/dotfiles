---
name: picture-this
description: 'Answer the current question or rephrase the current answer with a diagram, and then explain briefly how that diagram works.  Great for code architecture, bug reproduction, explaining a change set, tracing control flow, etc. Invoke with /picture-this; stays on until "stop picture-this" or "normal mode".'
---

# picture-this

To explain code, architecture, control flow, or data flow, or any other interaction between several moving parts, use the following output format:

1.  Ascii Diagram
2.  Bullet Points
3.  Relevant Files And Links List

Coding behavior is unchanged — this only shapes explanations. Keep following all
other instructions (tool use, permissions, project conventions).

## <1> Diagram Section Rules

Plain ASCII only. Never Mermaid, never HTML, never an artifact, unless otherwise requested.

### Visual Elements

| Category    | Elements                        | Usage                |
| ----------- | ------------------------------- | -------------------- |
| Box Drawing | `┌─┬─┐` `│ │ │` `├─┼─┤` `└─┴─┘` | Component boundaries |
| Arrows      | `──►` `◄──` `◄─►` `──✗` `──✓`   | Relationships, flow  |
| Status      | `✓` `✗` `⏳` `🔄` `⚠️` `🔴`     | Progress indicators  |

### Formatting Rules

| Rule          | Value              | Reason                 |
| ------------- | ------------------ | ---------------------- |
| Max width     | 80 characters      | Terminal compatibility |
| Box alignment | Vertical centers   | Visual clarity         |
| Spacing       | Between sections   | Readability            |
| Legends       | When using symbols | Self-documenting       |

- Control flow and call stacks: top to bottom. Request paths: left to right,
  numbered steps.

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
