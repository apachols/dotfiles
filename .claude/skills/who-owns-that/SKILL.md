---
name: who-owns-that
description: Refresh and republish the "Who owns that?" Yard site (https://who-owns-that.yard.roversvc.com), a fuzzy search over Rover's Technology Components ownership data in Jira Assets joined with the subconcept tags in the web repo. Use when the user asks to refresh, update, rebuild, redeploy or republish the who-owns-that site or the ownership search, says ownership changed in Jira Assets or taxonomy.yml, or asks to change how that site looks or searches.
---

# Who owns that?

Builds a static site from three sources and publishes it to `who-owns-that` on Yard:

| Source | What it gives | How it is read |
|---|---|---|
| Jira Assets schema 42, Technology Components | Concepts, subconcepts (each with one owning team), components | Atlassian MCP, AQL `objectSchemaId = 42` |
| Jira Assets People Directory, Groups (type 15) | Team Slack channel, DRI, parent team, former names | Atlassian MCP, AQL `objectTypeId = 15` |
| `web` at `origin/master` | `taxonomy.yml` (for drift), every `CONCEPTS.x.y` tag in code, URL routes labelled with a subconcept, and the owners of every tracked file from `.github/CODEOWNERS` and `danger/CODEWATCHERS` | `git cat-file`, never the working tree |

`scripts/build.py` joins them into `data.json` beside the files in `site/`. The page is plain
HTML/JS with no dependencies, because Yard blocks every CDN.

File ownership runs `bin/ownership.py` and `subdivide()` from `bin/subdivide-files`, loaded from
the same ref, so the site gives the same owners as `bin/file-owners` in the `code-ownership`
plugin. CODEOWNERS matching needs `pathspec`, so run the build with web's venv `python3`
(`pip install pathspec` anywhere else).

The home of this skill is `.claude/skills/who-owns-that/` in Adam Pacholski's dotfiles. Each
build also copies it to `_source/` in the published site, so if you have only the live site,
`yard pull who-owns-that ./who-owns-that` recovers it. Run the steps below from
`./who-owns-that/_source/`; `<skill>` means that directory.

## Refresh and publish

1. **Export both AQL queries through the Atlassian MCP.** Call
   `queryAssetsObjectsUsingAql` twice with `cloudId: "https://roverdotcom.atlassian.net"`
   and `limit: "1000"`:
   - `aql: "objectSchemaId = 42"` (about 330 objects, 500K characters)
   - `aql: "objectTypeId = 15"` (about 80 objects)

   Both results are too large to return inline, so the harness saves each to a file and
   gives you its path. Pass those paths to the build. Do not read or summarize the files;
   `build.py` validates them and refuses a partial page (`isLast: false`).

2. **Build from `origin/master`.**

   ```bash
   git -C /workspaces/web fetch -q origin master
   python3 -I <skill>/scripts/build.py --components <schema-42 file> --groups <groups file> --web /workspaces/web
   ```

   It prints counts, the number of drift rows, file coverage and the `data.json` size. Compare
   them with the live site's numbers (the line under the search box, and the code map page). A large drop means an export went
   wrong, so stop and investigate before publishing. Output goes to
   `~/.cache/who-owns-that/dist` unless you pass `--out`.

   The People Directory stores only Slack channel ids. If the build prints
   `Slack channels missing from slack_channels.json`, call the Slack MCP's `slack_read_channel`
   with each id and `limit: 1` (its reply starts `Channel: #name (id)`) and add the names to
   `scripts/slack_channels.json`. A team without a name still links to its channel.

3. **Check the Yard login.** `yard whoami --json` must print an `email`. It reports a missing
   login in its output, not its exit code. If you're signed out, run
   `yard login --device-code` in the user's terminal and give them the URL and code it prints.
   If `yard` is missing, install it with
   `gh api /repos/roverdotcom/yard/contents/install.sh -H "Accept: application/vnd.github.raw" | bash`
   (it installs to `~/.local/bin`).

4. **Publish.** This replaces the whole site and cannot be undone, but every file is
   regenerated from source, so nothing is lost.

   ```bash
   yard publish ~/.cache/who-owns-that/dist who-owns-that --yes --json
   ```

   Report the URL and the counts from step 2.

## Without Claude

`build.py --from-api` fetches both exports itself with `ATLASSIAN_EMAIL` and
`ATLASSIAN_API_TOKEN` (an API token from id.atlassian.com, kept in `.secrets`). It uses
Basic auth against
`/gateway/api/jsm/assets/workspace/<id>/v1/object/aql`. This is the path a GitHub Action
would use (with `YARD_CI=true yard publish`). It has not yet been run against the live API, so
check its counts against an MCP-built site the first time.

## Changing the site

- `site/app.js` holds search scoring (`tokenScore`, `scoreDoc`, `KIND_BOOST`) and every page
  renderer. Routes are hash fragments (`#q=`, `#team=`, `#sub=`, `#teams`, `#drift`,
  `#paths`, `#path=`, `#about`), so Yard needs no `--spa`.
- A query that looks like a path (has a `/` or a file extension) also searches code paths;
  one that starts with `/` lists URL routes first. `pathMatches` and `rollup` in `app.js`
  read `data.paths`, which stores each directory's most common owner set and only the files
  that differ from it.
- Django route patterns are relative to wherever their `urls.py` is included, and React route
  objects are read line by line in `react_routes`. Both are approximations, labelled as such.
- Attribute ids in `build.py` (`SUBCONCEPT_ATTRS` etc.) come from
  `listAssetsObjectTypeAttributes` for types 32, 33, 34 and 15. If a field goes missing after
  someone edits the schema, re-list the attributes and update the ids.
- Preview locally with `python3 -m http.server -d ~/.cache/who-owns-that/dist 8765`.

## Guardrails

- The site is readable by every logged-in Rover employee. The data is internal org structure
  (team names, DRIs, Slack channel ids), which is already visible to everyone in Jira.
- This site is a read-only copy. To change ownership, follow the
  [Updating Technology Components](https://roverdotcom.atlassian.net/wiki/spaces/TECH/pages/1961002737/Updating+Technology+Components)
  runbook. Never edit Jira Assets from this skill.
