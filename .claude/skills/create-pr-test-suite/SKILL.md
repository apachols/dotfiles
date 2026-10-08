---
name: create-pr-test-suite
description: "Write the manual acceptance test suite for a Rover web PR the way adamp writes them: the `## Before testing` setup (flags, fixture templates) and the `## Acceptance tests` section of `## Test Case N` cases, each with collapsed Test Details and Manual Test Instructions and a one-click fixture `/run` link. Use when the user says /create-pr-test-suite, asks to write, draft, rewrite, or add test cases or a test plan for a PR or the current branch, or when pr-as-adamp reaches the testing sections. Output is the format execute-test-case runs."
allowed-tools: Bash(gh:*), Bash(git:*), Bash(curl:*), Bash(python3:*), Grep, Glob, Read, mcp__gateway__atlassian_getJiraIssue
---

# Create PR test suite

Writes the two testing sections of a PR body: `## Before testing` and `## Acceptance tests`.
Someone else, or the `execute-test-case` skill, should be able to run each case start to finish
from what is written.

## Step 1: Read the format guides

Read **all three** files next to this SKILL.md:

- `suite-format.md` — the two sections, the `## Test Case N` wrapper, Out of Scope, shell_plus
  rules.
- `testcase-format.md` — the inside of **one** test case.
- `fixture-run-links.md` — how to read a fixture template's options and entry points, and build
  the one-click `/run` link a fixture step uses.

## Step 2: Gather the change

- **Called from `pr-as-adamp`**: the diff and Jira context are already in hand. Use them.
- **Standalone**: take the PR number from the user, or find the current branch's PR with
  `gh pr view --json number,title,body,baseRefName`. Read the diff (`gh pr diff`, or
  `git diff origin/master...HEAD` when there's no PR yet) and the Jira ticket from the branch
  name or PR title.
- When the PR body already has test cases, treat them as a draft to fix, not to discard: keep
  the cases' intent unless the diff shows it's wrong.

## Step 3: Design the suite

1. List every behavior the diff changes, including the guard paths (flag off, ineligible user,
   unaffected product).
2. Name the 2–4 variables those behaviors branch on: flag on/off, enrolled or not, taxable
   state or not, cancel vs. partial refund.
3. Pick the permutations that cover every behavior from step 1 with the fewest cases. Each case
   should prove something no other case proves.
4. Move anything impractical to manual-test into Out of Scope with the reason.

## Step 4: Fixtures and links

- Choose the fixture template per `suite-format.md`.
- Build each fixture step's `/run` link per `fixture-run-links.md`. Prefer reading options from
  the local template API over the source when the server is up.
- Every other detail line links to a local-env page (admin list pages, flag admin) or says
  exactly how to do the step.

## Step 5: Self-check

Before handing the sections back, verify:

1. `## Before testing` answers flags first (name, admin link, how to flip), then fixture
   templates, each linked.
2. No `> [!IMPORTANT]` box and no italic placeholder bullets left from the repo template.
3. Every case matches `testcase-format.md`: all four parts present, Test Details and Manual
   Test Instructions each collapsed in their own `<details>`.
4. Top-line names are composed of the permuted variables and distinct from each other.
5. Every detail line is a local-env link or an explicit how-to, and every fixture step is a
   `/run` link with its options and entry point.
6. No "run these unit tests" step. Impractical items are in `### Out of Scope` with reasons.
7. shell_plus blocks follow `suite-format.md`.

## Step 6: Deliver

- **Called from `pr-as-adamp`**: return the two sections' markdown for it to place in the body.
  Don't edit the PR.
- **Standalone, PR exists**: show the suite in chat and ask before changing the PR. On yes,
  replace only the testing sections: `## Before testing` up to `## Acceptance tests`, and
  `## Acceptance tests` to the end of the body (its cases use `##` headings, so don't stop at
  the next `##`). Keep the rest of the body byte for byte, and
  `gh pr edit <n> --body-file <file>`. Strip `\r` from the fetched body before slicing it.
- **Standalone, no PR**: print the two sections in chat, ready to paste.
