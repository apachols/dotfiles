---
name: publish-adamp-testresults
description: Publish the execute-test-case results tree to the adamp-testresults Yard site, merging the live site into the local directory first so no previously published run is ever lost. Use when the user asks to publish, share, push, or upload test results, wants a shareable link to a test run, says "publish my test results" or "put that on yard", or after execute-test-case finishes a run and the user wants it online.
---

# Publish adamp-testresults

Publishes the `execute-test-case` results directory to `https://adamp-testresults.yard.roversvc.com/`.

`yard publish` replaces a site's entire contents and has no undo, so publishing a local
directory that is missing runs the site already has would silently delete them. This skill
pulls the live site into the results dir first, rebuilds the index pages over the merged
tree, then publishes the union — so a fresh Codespace or a half-synced Obsidian folder
heals instead of clobbering.

## Run it

```bash
python3 <skill>/scripts/publish.py
```

Substitute the absolute path of this skill directory. Stdlib only — no `uv` needed for this
script, though it shells out to the `execute-test-case` build script, which does use `uv`.

Report the published URL and the `local:` `file://` URL it prints, both verbatim.

Flags:

- `--dry-run` — everything except the publish. Prints what would be replaced. Use this when
  the user is unsure, or when anything about the tree looks unexpected.
- `--no-pull` — publish the local tree as-is. **This deletes any run that exists only on the
  site.** It is the only way to make a deletion stick (see below). Never pass it unless the
  user has asked to remove something.
- `--site` / `--results-dir` — override the defaults.

## What it does, in order

1. Resolves the results dir from `~/.claude/execute-test-case.json` (`resultsDir`), the same
   state `execute-test-case` writes. Site id comes from `yardSite` in that file, else
   `adamp-testresults`.
2. Checks the Yard login. `yard whoami` reports a missing credential in its **output**, so the
   script checks for an `email` in `--json` rather than trusting the exit code.
3. `yard pull <site> <dir> --force` — adds and replaces, never deletes. Prints each run it
   merged back. A site that has never been published is not an error.
4. Rebuilds every `index.html` via the `execute-test-case` build command.
   **This must run after the pull**, because `--force` overwrites a locally-built
   `index.html` with the published one.
5. Refuses symlinks (Yard rejects them rather than following, which would 404 silently) and
   confirms `index.html` is at the root.
6. `yard publish <dir> <site> --yes --json`, and prints the URL.

## Deleting a run

Pulling in place means the merge is one-way: the local directory only ever gains runs. To
remove one for real, delete it in **both** places — locally, then publish with `--no-pull`:

```bash
rm -rf <results-dir>/<run-slug>
python3 <skill>/scripts/publish.py --no-pull
```

Without `--no-pull` the next pull resurrects it from the site.

## Guardrails

- The site is `PUBLIC` — every logged-in Rover employee can read it. Test evidence carries
  fixture data and screenshots of local dev. If a run contains anything that should not be
  broadly visible, say so before publishing rather than after.
- `yard pull` is a snapshot, not a checkout: a publish by someone else between the pull and
  the publish is silently overwritten. Single-writer site, so this is theoretical — but check
  `yard sites` for `LAST PUBLISHED` / `BY` if a publish is unexpectedly large or small.
- The admin links in the reports point at `http://rover.local:8001` and only resolve for
  someone running local dev. That is expected; the pages already say so.
- Do not offer to publish automatically after every run. Publishing is opt-in per the user.
