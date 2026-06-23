---
name: export-clean
description: Exports the current conversation to markdown like /export, then cleans it up — wraps the Claude logo in a code block, strips out "checking this / researching that" status chatter, and applies formatting tweaks.
---

# Export Clean

When the user invokes this skill, do the following:

1. Reproduce the full conversation as markdown (same content /export produces).
2. Wrap the ASCII Claude logo header in a fenced code block so it renders monospaced.
3. Remove transient status lines — anything that's just narration of tool use
   ("Let me check…", "Searching for…", "Researching…", spinner text, etc.).
4. Save this as a file to /tmp/claude-export-clean/
5. Copy the contents of the file (the cleaned export output) to the clipboard

Save the result to `conversation-export.md` in the working directory.
