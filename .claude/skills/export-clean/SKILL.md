---
name: export-clean
description: Exports the current conversation to markdown like /export, then cleans it up - strips out "checking this / researching that" status chatter, and applies formatting tweaks.
---

# Export Clean

When the user invokes this skill, do the following:

1. Reproduce the full conversation as markdown (same content /export produces).
2. Remove the ascii art at the top
3. Add the following info at the top in a code block

claude-version: $CLAUDEVERSION
model-version: $MODELVERSION
working-directory: $WORKINGDIR

4. Remove transient status lines — anything that's just narration of tool use
   ("Let me check…", "Searching for…", "Researching…", spinner text, etc.).
5. Save this as a file to /tmp/claude-export-clean/. Filename should start with a timestamp.

Print the full path of the new clean export file so the user can open the file
