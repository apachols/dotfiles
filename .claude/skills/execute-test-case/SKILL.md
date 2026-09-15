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
2. **Preconditions.** Set feature flags / switches exactly as "Test Conditions" says. Record the
   as-found state so it can be restored. Screenshot each flag admin page.
3. **Fixture.** Create the fixture template named in the PR with the specified parameters. Use the
   fixture entry point (`view_as_requester`, etc.) to authenticate.

   Heads up: some fixtures 500 on the page load right after the build completes — the records
   that were just created are not visible to that request yet (race condition). Refresh the page;
   it should load. If it still 500s after a refresh, stop and tell the user.
4. **DB checks.** Where the PR gives a `shell_plus` snippet, run it via `m shell_plus` and record
   the values. Screenshot admin pages that prove non-obvious data state.
5. **Execute.** Follow "Test Execution". Screenshot the full page, then each element the
   "Expected Result" bullets talk about. Read the actual text / numbers off the page — do not
   infer them.
6. **Verdict.** `pass` only if every expected-result bullet matches exactly. Otherwise `fail`
   with the mismatch, or `blocked` if a precondition could not be established.
7. **Restore** flags/switches to their as-found state. Say so in the notes.

Screenshot naming: `NN-kebab-slug.png`, zero-padded, in execution order
(`01-rollout-gate-on.png`, `04-price-ledger.png`). The gallery caption is derived from the slug.
Save them with `playwright-cli screenshot --path <run>/test-case-<K>/screenshots/NN-slug.png`
(or the equivalent for the tool in use); crop to the element where a full page would bury it.

## 5. Write the report files

Read `references/result-format.md` for the exact schemas and a worked example. In short:

- `<run>/test-case-<K>/result.md` — YAML frontmatter (`testCase`, `title`, `status`, `executedAt`,
  `executedBy`, `method`, `pr`, `branch`, `ticket`) then markdown: Environment, Flag state,
  Fixture / data setup, Preconditions verified in the DB, Expected vs actual table (one row per
  expected-result bullet, each citing a screenshot), Screenshots table, Notes / follow-ups.
- `<run>/run.json` — run manifest (`runId`, `startedAt`, `finishedAt`, `pr`, `prUrl`, `ticket`,
  `title`, `branch`, `commit`, `target`, `executedBy`, `cases[]`).
- `<run>/README.md` — one-paragraph summary plus a Case / Title / Result table; say which of the
  PR's cases were **not** executed.

## 6. Build and hand off

```bash
uv run --script <skill>/scripts/testresults.py build
```

Regenerates `index.html` at the root, run, and case levels (all relative links, inline CSS).
Report to the user:

- the `open: file://...` URL the build printed, plus the direct `file://` URL of the run page
- a one-line verdict per case
- anything that changed outside the results dir (PR body edits, fixture data left behind, flags
  restored)

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
