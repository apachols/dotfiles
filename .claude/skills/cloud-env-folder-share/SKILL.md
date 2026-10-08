---
name: cloud-env-folder-share
description: "Set up a folder shared between your laptop and a GitHub Codespace or Rover Roverspace, so you and an agent in the cloud env can both read and write the same files (Obsidian notes, test results, agent output). Asks a few questions, then installs and runs a Mutagen live sync, including the Roverspace workarounds. Run it on the laptop. Use when the user says /cloud-env-folder-share, asks to share or sync a folder with a codespace or roverspace, set up mutagen, or fix a broken mutagen sync."
allowed-tools: Bash, Read, AskUserQuestion
---

# Cloud dev folder share

Sets up a laptop folder that stays in sync with a folder in a Codespace or Roverspace.
`scripts/cloud-env-folder-share.sh` does the work; this file decides what to pass it. Call the
script by its absolute path, the `scripts/` dir next to this SKILL.md (`<skill>` below).

Read `references/gotchas.md` before debugging a sync that's already set up.

## Step 1: Make sure this is the laptop

Mutagen runs on the laptop and reaches into the cloud env over ssh. If `$CODESPACES` or
`$CODER` is set, you're inside a cloud env: stop, and tell the user to run this skill from
Claude Code on their laptop.

## Step 2: Ask

Use `AskUserQuestion`, one call, recommended option first:

1. **Where?** Codespace / Roverspace / Both.
2. **Which folders?** Default `~/mutagen` on the laptop ↔ `~/mutagen` in the cloud env. Offer
   "same folder name in an Obsidian vault" as the second option. Never sync anything inside
   `/workspaces/web`.
3. **Keep it running?** Start Mutagen at login (`mutagen daemon register`) and
   put a `cloud-env-folder-share` command on `PATH` (Recommended) / just set it up now.

Then, per environment:

- **Codespace**: `gh codespace list --json name,displayName,repository,state`. If exactly one
  is `Available`, use it and say so; otherwise ask which. If none is running, ask the user to
  start one.
- **Roverspace**: ask for the workspace name and their Coder username. The host is
  `devcontainer.<workspace>.<coder-user>.coder`. If `~/.ssh/config` or the user names a
  different host, use that.

## Step 3: Preflight

1. `mutagen version`. If it's missing, offer
   `brew install mutagen-io/mutagen/mutagen` and run it on yes.
2. Codespace: `gh auth status`. Then get the ssh alias:
   `<skill>/scripts/cloud-env-folder-share.sh codespace-host <codespace-name>`. It may add one
   `Include` line to the top of `~/.ssh/config`; tell the user if it did.
3. Roverspace: remind the user the Coder VPN must be up.
4. `<skill>/scripts/cloud-env-folder-share.sh check <host>` for every host. On failure, show
   the error and stop; don't try to fix ssh keys or VPN yourself.

## Step 4: Set up

Session names: `<codespace|roverspace>-<local folder basename>`, e.g. `roverspace-mutagen`.

`<skill>/scripts/cloud-env-folder-share.sh up --kind <codespace|roverspace> --host <host> --local <dir> --remote <dir> --name <name>`

Run it once per environment. It's safe to re-run: it resumes an existing session, and for a
Roverspace it re-stages the agent first.

## Step 5: Verify

1. Write `cloud-env-folder-share-test.md` with a timestamp into the local folder.
2. `mutagen sync flush <name>`, then `mutagen sync list <name>` should show
   `Watching for changes` and no conflicts.
3. `ssh <host> cat <remote dir>/cloud-env-folder-share-test.md` should print the timestamp.
4. Delete the local test file, flush again, and check it's gone remotely too.

## Step 6: Make it repeatable

If the user said yes to "keep it running":

1. `mutagen daemon register`.
2. Link the script: `mkdir -p ~/.local/bin && ln -sfn <skill>/scripts/cloud-env-folder-share.sh ~/.local/bin/cloud-env-folder-share`.
   Warn if `~/.local/bin` isn't on `PATH`.

Finish with the exact command(s) to bring the share back, e.g.
`cloud-env-folder-share up --kind roverspace --host ... --local ~/mutagen --remote mutagen --name roverspace-mutagen`.
For a Roverspace, tell them to run it after any workspace rebuild or fresh clone of the repo,
not only after a reboot. Offer to add a short shell function with that line to their shell rc
file, and edit the file only on yes.

Also tell them:
- `cloud-env-folder-share status` shows sessions and conflicts; `stop <name>` ends one and keeps
  the files.
- Don't point a second sync tool (an Obsidian sync plugin, Dropbox) at the same folder.
