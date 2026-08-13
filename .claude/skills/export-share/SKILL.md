---
name: export-share
description: Exports the current conversation to markdown like /export, cleans it up - strips out "checking this / researching that" status chatter and applies formatting tweaks - then offers to share it as a claude.ai Artifact, a Slack Canvas, or a private GitHub Gist and returns the link.
---

# Export Share

> **IMPORTANT:** The exported conversation may contain sensitive data. Before
> saving or publishing, carefully review the content and **redact any
> environment variable values, secret keys, API tokens, credentials, or other
> non-shareable information**. Replace redacted values with a placeholder like
> `[REDACTED]`. Never publish an Artifact until this review is complete.

## Output directory (OUTPUT_DIR)

export-share remembers where to save clean exports in a flat config file at
`~/.claude/export-share-output-dir` (single line, just the absolute path — same
pattern as the caveman plugin's `~/.claude/.caveman-active` flag file).

On every invocation, before doing anything else:

1. Read `~/.claude/export-share-output-dir` if it exists.
2. **If it exists and is non-empty:** treat its contents as `OUTPUT_DIR` and
   print one line: `export-share output dir: <OUTPUT_DIR>`. Do not ask again.
3. **If it does not exist (or is empty):** ask the user where to save clean
   exports, suggesting `~/obsidian/remote-sync/` as the default (this is the
   user's mutagen-synced directory shared with codespaces — see `remotesync`).
   Once they answer, write their chosen path as `OUTPUT_DIR` — a single line,
   no trailing newline requirements — to `~/.claude/export-share-output-dir`,
   creating the directory itself with `mkdir -p` if it doesn't exist yet.

Use `OUTPUT_DIR` (not `/tmp`) as the save location in step 6 below.

When the user invokes this skill, do the following:

1. Reproduce the full conversation as markdown (same content /export produces).
2. Remove the ascii art at the top
3. Add the following info at the top in a code block

claud-code-version: $CLAUDECODEVERSION
model-version: $MODELVERSION
working-directory: $WORKINGDIR

4. Remove transient status lines — anything that's just narration of tool use
   ("Let me check…", "Searching for…", "Researching…", spinner text, etc.).
5. **Redact sensitive data** — scan for environment variable values, secret
   keys, API tokens, passwords, credentials, or any other non-shareable
   information and replace each value with `[REDACTED]`.
6. Save this as a file to `OUTPUT_DIR` (see above). Filename should start with a timestamp.

Print the full path of the new clean export file so the user can open the file.

## Sharing (optional)

After saving the clean markdown file, print its path and then offer sharing
options as a numbered list:

```text
How would you like to share this?

1. Create a claude.ai Artifact (private link)
2. Upload to Slack as a Canvas
3. Create a private GitHub Gist (`gh` CLI)
4. Don't share — just keep the local file
```

Skip the prompt if the user already picked a destination in their invocation
(e.g. "/export-share as artifact", "/export-share to slack",
"/export-share as gist").

**Do not check whether Slack is available before the user chooses.** Only probe
for Slack tooling after they pick the Slack option — checking up front costs
tokens and blocks on work that may never be needed.

### Option 1 — claude.ai Artifact

1. Call the **Artifact** tool with `file_path` set to the saved `.md` file.
2. Markdown artifacts keep their filename identity, so no `title` param is
   needed; the timestamped filename names it.
3. Pass a one-sentence `description` summarizing the conversation topic.
4. Pass a `favicon` emoji that fits the conversation subject (e.g. 📝 for a
   general export). Keep it stable if you re-publish the same export.
5. Print the returned Artifact URL so the user can open and share it.

Notes:

- The Artifact is **private by default** — only the user can see it until they
  choose to share it. Say so when you return the link.
- Artifacts are self-contained: markdown renders natively, no external assets.
  The clean export is plain markdown, so it publishes as-is.
- To update a previously published export, edit the same file and call the
  Artifact tool again with the same `file_path` (redeploys to the same URL).

### Option 2 — Slack Canvas

1. Find the Slack MCP canvas tool. Slack MCP tools are deferred, so their
   schemas are not loaded up front — run
   `ToolSearch("+slack canvas create")` to locate and load one. If that returns
   nothing, try `ToolSearch("+slack")` to see what Slack tools exist at all.
2. If no Slack MCP tool is available, tell the user plainly:

   > Slack MCP isn't connected in this session, so I can't create a Canvas.
   > The local markdown file is still at `<path>`. You can add the Slack MCP
   > server (`claude mcp add`) and re-run, or share as a claude.ai Artifact
   > instead.

   Then offer the Artifact option again. Do not try to shell out to `curl` or
   the Slack API directly.
3. If a canvas-creation tool is available, call it with:
   - **title**: the export filename or a short conversation summary.
   - **content**: the cleaned markdown. Slack Canvas accepts a markdown
     subset — if the tool rejects the content, simplify it (drop HTML, deeply
     nested lists, and footnotes) and retry once.
4. Create the Canvas as a **standalone canvas owned by the current user** — do
   not pass a channel and do not share it to any channel or user. The user will
   share it themselves.
5. Print the returned Canvas URL (or canvas ID if no URL comes back).

Notes:

- The exported transcript can be long. If the canvas tool errors on size, split
  the content and say so, or fall back to the Artifact option — don't silently
  truncate the transcript.
- The same redaction review applies: never upload an export to Slack before the
  sensitive-data pass above is complete.

### Option 3 — Private GitHub Gist (`gh` CLI)

1. Check the `gh` CLI is present and authenticated:

   ```bash
   gh auth status
   ```

   If `gh` is not installed or not authenticated, tell the user plainly:

   > The `gh` CLI isn't available/authenticated here, so I can't create a Gist.
   > The local markdown file is still at `<path>`. Run `gh auth login` and
   > re-run, or share as a claude.ai Artifact instead.

   Then offer the Artifact option again. Do not fall back to `curl` against the
   GitHub API.
2. Create the gist from the saved file. `gh gist create` makes a **secret**
   gist by default — never pass `--public`:

   ```bash
   gh gist create "<OUTPUT_DIR>/<timestamped-file>.md" --desc "<one-line conversation summary>"
   ```

   The command prints the gist URL on success.
3. Print the returned Gist URL so the user can open and share it.

Notes:

- **A secret gist is unlisted, not access-controlled.** It won't show on the
  user's profile or in GitHub search, but anyone who has the URL can read it
  without signing in. Say this when returning the link — it is weaker than the
  Artifact private link.
- Gists are per-account and may land on a work GitHub account. If `gh auth
  status` shows multiple accounts or a work host, name the account the gist
  will be created under and confirm before creating it.
- The same redaction review applies: never create a gist before the
  sensitive-data pass above is complete. A pushed gist is effectively public
  once the URL leaks — deleting it later does not undo caching or indexing.
- To update a previously created gist, use `gh gist edit <gist-id-or-url>
  --filename <name>.md <path>` rather than creating a new one.
