---
name: execute-test-case
description: Execute one or more acceptance-test cases from a Rover web PR body ("## Test Case N" sections) against local dev with Playwright, then write a browsable evidence report (result.md + screenshots + generated index.html pages) into the user's test-results directory. Use whenever the user asks to run, execute, verify, or QA a PR's test case(s), "test case 2 on PR 101753", "run the acceptance tests for my PR", "report coverage for this PR", or wants screenshots/proof that a PR's manual test plan passes. Remembers the results directory across sessions; asks for it only on first use.
---

# Execute test case

Run a PR's manual acceptance test case(s) end to end, capture evidence, and render the evidence
as a static HTML tree the user opens with `file://`. No server is involved.

`scripts/testresults.py` is self-contained: run it with `uv run --script` (deps declared inline,
resolved by uv on first run). Commands below write `<skill>/scripts/testresults.py`; substitute
the absolute path of this skill directory (the directory containing this SKILL.md).

## 1. Resolve the results directory (state)

```bash
uv run --script <skill>/scripts/testresults.py get-dir
```

- **Exit 0** — prints the remembered dir. Tell the user, verbatim, before doing anything else:
  `writing test results to <DIR>`
- **Exit 1** (first use) — ask the user with AskUserQuestion: "Where do you want to store the test
  results?" Offer a sensible default (e.g. `~/obsidian/remote-sync/testresults`) and accept any
  path. Then:
  ```bash
  uv run --script <skill>/scripts/testresults.py set-dir <PATH>
  ```
  and print `writing test results to <PATH>`.

State lives in `~/.claude/execute-test-case.json` (override with `EXECUTE_TEST_CASE_CONFIG`).
Never store state inside the skill directory — it is shared via git.

## 2. Identify PR and test case(s)

1. PR number: from the user, else the PR for the current branch (`gh pr view --json number`).
   In Codespaces `gh` needs a login shell: `bash -lc 'gh pr view N --json number,title,body,headRefName'`.
2. Read the PR body. Test cases are `## Test Case N` sections with `### Test Conditions`,
   `### Test Execution`, `### Expected Result`, and a `<details>` block of manual instructions.
   Also read "Before testing" (feature flags, fixture templates, shell_plus snippets).
3. If the user did not name a case, list the cases (number + title) and ask which to run.
   "All" is a valid answer.
4. Record `git rev-parse --short=12 HEAD` and the branch; confirm the checked-out branch is the PR
   branch. If not, stop and say so — do not test the wrong code.

## 3. Create the run directory

```bash
uv run --script <skill>/scripts/testresults.py new-run --pr <N>
```

Prints `<DIR>/<YYYYMMDDTHHMMZ>-pr-<N>`. Every artifact for this run goes under it. One run dir per
invocation, even when running several cases. Note the UTC start time for `run.json`.

## 4. Execute each test case

Before touching the browser, read the Rover site interaction guide in the `web` checkout:

```bash
cat .claude/skills/rover-site-interaction/SKILL.md
```

It carries the credentials, fixture templates and entrypoints, service-type slugs, URL patterns,
and modal/cookie quirks. Read it in full — do not guess a fixture slug or a password. Then read
[Rover webapp Playwright testing best practices](#rover-webapp-playwright-testing-best-practices)
below for the `execute-test-case`-specific rules that layer on top of it.

Drive the browser with `playwright-cli` (ad-hoc). Per case:

1. `mkdir -p <run>/test-case-<K>/screenshots`.
2. **Capture the spec.** Copy the PR body's whole `## Test Case N` section — heading, Test
   Conditions, Test Execution, Expected Result, and the `<details>` manual-instructions block —
   verbatim into `<run>/test-case-<K>/test-case.md`. Do not summarize or reword it: this is the
   record of what the PR asked for at this commit, so a later run can tell a real regression from
   a rewritten test case. The case page renders it in a collapsed block at the top.
3. **Preconditions.** Set feature flags / switches exactly as "Test Conditions" says. Record the
   as-found state so it can be restored. Screenshot each flag admin page.
4. **Fixture.** Create the fixture template named in the PR with the specified parameters. Use the
   fixture entry point (`view_as_requester`, etc.) to authenticate.

   Heads up: some fixtures 500 on the page load right after the build completes — the records
   that were just created are not visible to that request yet (race condition). Refresh the page;
   it should load. If it still 500s after a refresh, stop and tell the user.
5. **DB checks.** Where the PR gives a `shell_plus` snippet, run it via `m shell_plus` and record
   the values. Screenshot admin pages that prove non-obvious data state.
6. **Execute.** Follow "Test Execution". Screenshot the full page, then each element the
   "Expected Result" bullets talk about. Read the actual text / numbers off the page — do not
   infer them.
7. **Admin links.** For every scenario the case ran — each fixture build, each variant, each
   separate conversation — record one admin link, in `adminLinks` in the `result.md` frontmatter
   (schema in `references/result-format.md`). Prefer the **conversation** admin page: it is the
   hub of the domain and everything else (requests, orders, relationships, users) is reachable
   from it. Fall back to the **order** admin page, then to whatever record the case is actually
   about. One link per scenario is the target — do not dump every record you visited.

   Get the URL by navigating there, not by guessing a path: open the conversation in admin (search
   its OPK from the conversation admin changelist, or follow the link from the order) and copy the
   address bar. Absolute URLs including the local host (`http://rover.local:8001/...`), so the
   link works from the results page.
8. **Verdict.** `pass` only if every expected-result bullet matches exactly. Otherwise `fail`
   with the mismatch, or `blocked` if a precondition could not be established.
9. **Restore** flags/switches to their as-found state. Say so in the notes.
10. **Log friction.** Whenever something outside the test case itself gets in the way — a broken or
    missing dev-env dependency, a service that had to be restarted, a fixture that 500s, a stale
    migration, a wrong or missing credential, a flaky selector, a PR-body link that 404s, a slug or
    URL in a skill doc that no longer matches the app, a workaround you had to invent — append an
    entry to `<run>/issues.md` (see step 5). Log it even when you worked around it: the point is a
    list the user can act on later. Do not let logging an issue change the verdict — a dev-env
    problem is `blocked`, not `fail`, only when it stopped the case from running.

Screenshot naming: `NN-kebab-slug.png`, zero-padded, in execution order
(`01-rollout-gate-on.png`, `04-price-ledger.png`). The gallery caption is derived from the slug.
Save them with `playwright-cli screenshot --path <run>/test-case-<K>/screenshots/NN-slug.png`
(or the equivalent for the tool in use); crop to the element where a full page would bury it.

## 5. Write the report files

Read `references/result-format.md` for the exact schemas and a worked example. In short:

- `<run>/test-case-<K>/test-case.md` — the PR's `## Test Case N` section, verbatim (step 4.2).
- `<run>/test-case-<K>/result.md` — YAML frontmatter (`testCase`, `title`, `status`, `executedAt`,
  `executedBy`, `method`, `model`, `effort`, `tokenSpend`, `pr`, `branch`, `ticket`, `adminLinks`)
  then markdown: **Agent run** table (first section, right under the `**Result:**` line), Environment,
  Flag state, Fixture / data setup, Preconditions verified in the DB, Expected vs actual table (one
  row per expected-result bullet, each citing a screenshot), Screenshots table, Notes / follow-ups.
- `<run>/run.json` — run manifest (`runId`, `startedAt`, `finishedAt`, `pr`, `prUrl`, `ticket`,
  `title`, `branch`, `commit`, `target`, `executedBy`, `model`, `effort`, `tokenSpend`, `cases[]`).

### Recording the agent's own identity and cost

Every `result.md` records which model ran the case, at what effort/thinking level, and roughly what
it cost. The renderer only prints frontmatter keys it knows about, so write the values **twice**:
in the frontmatter (machine-readable) and in the **Agent run** markdown table (what the reader
sees on the case page).

| Field | Where the value comes from |
|---|---|
| `model` | The model name and exact model ID from this session's environment (e.g. `Opus 5 (claude-opus-5)`). Do not guess a version. |
| `effort` | The reasoning/effort or thinking level in force for this session (e.g. `high`), plus fast mode if on. If nothing set it, write `default`. |
| `tokenSpend` | Cumulative token usage for the session at the time the case finished, as the harness reports it. |

Token spend is session-cumulative, not per-case: when several cases share one invocation, note the
running total per case and say so. If a value genuinely is not available, write `unavailable` —
never invent a number.
- `<run>/README.md` — one-paragraph summary plus a Case / Title / Result table; say which of the
  PR's cases were **not** executed. Do not link `issues.md` by hand — the build links it.
- `<run>/issues.md` — the friction log from step 4.10. Create it only if there was something to
  log; skip the file entirely on a clean run. Format: `# Issues hit during this run`, then one
  `## <short title>` per problem with these lines:

  - **What happened** — the symptom, with the exact error text quoted.
  - **Where** — the case number and step, or "setup" / "environment".
  - **Workaround** — what you did to get past it, or `none — blocked`.
  - **Suggested fix** — the concrete change, and where it belongs (dev env, a skill doc, the PR
    body, the app). Write `unknown` rather than guessing.

  Keep the entries independent — the user may act on one and ignore the rest. The build turns
  this file into `<run>/issues.html` and puts a banner linking to it at the top of the run page
  and every case page, so the headings are what the reader scans — make them specific.

## 6. Build and hand off

```bash
uv run --script <skill>/scripts/testresults.py build
```

Regenerates `index.html` at the root, run, and case levels (all relative links, inline CSS), plus
`issues.html` for any run that has an `issues.md`.
The case page carries, in order: verdict header, the collapsed original test description from
`test-case.md`, the rendered `result.md`, the `adminLinks` table, then the screenshot gallery.
Report to the user:

- the `open: file://...` URL the build printed, plus the direct `file://` URL of the run page
- a one-line verdict per case
- anything that changed outside the results dir (PR body edits, fixture data left behind, flags
  restored)
- if `issues.md` exists, a single line calling it out with the `file://` URL of the generated
  `issues.html`, e.g. `hit 3 environment issues — see file:///<run>/issues.html`. Do not paste the
  entries into chat; one line plus the link. Say nothing about issues on a clean run.

## Rover webapp Playwright testing best practices

`execute-test-case`-specific rules for driving the Rover webapp. These sit on top of
`rover-site-interaction`; that skill is the general guide, this section is what test-case
execution needs in addition.

### Feature flags

- **Gargoyle flags.** Go to `/admin/nexus/gargoyle`, search for the flag, and set it to
  **Global** (enabled) or **Disabled**. Consult the user before using **Selective** — its
  conditions are easy to get wrong and hard to notice.
- **Statsig gates.** Go to the gate's page directly (e.g.
  `/admin/statsig_gates/rollout_recurring_sales_tax_recoupment/`) or search the flag name in
  `/admin/statsig_gates/`. For local, set **environment type** to `development` and set the **ID**
  to the Codespace ID. The admin dropdown should offer that Codespace as its only option — if it
  does not, get the value from the Codespace env var and tell the user the dropdown looked wrong:
  ```bash
  echo $CODESPACE_NAME   # e.g. bookish-space-guide-4v94j4pjxv2q6gx
  ```

Screenshot every flag page after the change, and record the as-found value so step 4.7 can
restore it.

## Guardrails

- Never mark `pass` on a partial match; quote the mismatching actual value.
- Do not edit the PR body unless the user asks — but if a link in it 404s, say so in the notes.
- Leave the local dev DB usable: fixture data may stay, flags must be restored.
- If `uv` is missing, fall back to `pip install markdown pyyaml` and run the script with `python3`.
