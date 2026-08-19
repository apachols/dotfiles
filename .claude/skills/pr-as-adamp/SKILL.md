---
name: pr-as-adamp
description: "Create or update a Rover web PR the way adamp writes them: run the normal create-pr flow, then shape every section with adamp's personal PR style guide (bundled pr-template.md). Use when the user says /pr-as-adamp, 'make my PR', 'PR as me', 'PR in my style', or asks for a PR that follows their template/style notes."
allowed-tools: Bash(gh:*), Bash(git:*), Grep, Glob, Read, Skill, mcp__gateway__atlassian_getJiraIssue
---

# PR as adamp

Wrapper around the `create-pr` skill. `create-pr` decides *which* sections exist and does the git/gh mechanics; this skill decides *how each section is written*.

## Step 1: Read the style guide

Read `pr-template.md` next to this SKILL.md. It is the canonical copy of adamp's annotated PR template — the fenced ```` ``` ```` blocks in it are **style notes for you**, not PR body content. Never copy a style-note block into a PR body.

## Step 2: Run create-pr

Invoke the `create-pr` skill (`Skill(skill: "create-pr")`) and follow all of its steps: mode detection, base branch, Jira ticket extraction, diff gathering, repo template discovery, commit/push, `gh pr create --draft` / `gh pr edit`.

Section contract stays create-pr's: the **repo's own** PR template (e.g. `.github/PULL_REQUEST_TEMPLATE/*.md`) defines which sections exist. `pr-template.md` never adds, renames, or reorders sections — it only governs wording and content of sections the repo template already has.

## Step 3: Apply adamp's style on top

Where `pr-template.md` and create-pr's guidance disagree on *wording or content of a section*, **pr-template.md wins**. Key overrides to expect:

- **Always delete the template's placeholder/italic prompt bullets.** No `_What is changing in this PR?_` left behind.
- **Ultra-concise bullet points everywhere.** Fewest words that still convey the fact. No prose paragraphs — including the "reason for this pull request" section (create-pr's "2-4 sentences" gives way to bullets, ≤150 words, audience = "familiar with Rover but not this area", no description of what was *not* changed).
- **Deployment sections**: 1–3 bullets, each a measurable outcome (prod behavior, Splunk, Datadog).
- **Breaking-changes section**: delete the `> [!NOTE]` info box. Decide the checkbox from the diff, and warn the user in chat if the diff looks like it *does* contain breaking changes.
- **Brands**: remove the "this is a temporary question" annotation; keep Rover / Cat in a Flat / DogBuddy / MadPaws checked unless the diff is brand-scoped.
- **AI code generation**: always check "All or nearly all (>75%)". Add **no** note on AI tool use, and delete the `> [!TIP]` "optionally add a note" callout. (This overrides create-pr's web.md, which asks for a note.)
- **Reviewer instructions**: delete the whole section when there are no frontend changes. Leave the a11y checkbox unchecked when it stays.
- **Before testing**: answer feature flags first, then users/fixtures. Nest sub-bullets for multi-step setup. Name the specific fixture template + the options the tester must pick, and link it, e.g. `http://rover.local:8001/dev/fixtures/templates/1-standard-scenario`. Find candidates by grepping `(FixtureSetTemplate)` — the slug is defined a few lines below each class. Default to `1-standard-scenario` only when nothing fits better.
- **Acceptance tests**: delete the `> [!IMPORTANT]` accessibility box. Use a `### Test Cases` section of checkbox test cases, each followed by ordered bullets that walk the reviewer through the manual test, with nested `[ ]` expectation lines. If any a11y testing is needed, put it in its own `### Accessibility Test Cases` section *before* `### Test Cases`. Never list "run these unit tests" as a manual step. Anything not practical to manual-test goes in a `### Out of Scope` section at the end, one bullet per item with the reason.
- **shell_plus blocks**: fence as ```` ```python ````. Never one-liners via `m shell_plus -c "..."`. Assume the reviewer copies the whole block into a shell_plus session. Don't import model classes (shell_plus auto-imports them). Prefer `.last()` to grab the most recent fixture-created record.

## Step 4: Pre-send check

Before calling `gh pr create` / `gh pr edit`, verify the body:

1. No style-note fenced block, no `> [!NOTE]` / `> [!TIP]` / `> [!IMPORTANT]` box, no "temporary question" annotation.
2. No leftover italic placeholder bullets.
3. Every section is bullets, not prose; each bullet is as short as it can be.
4. Every section the repo template has is present; no section invented.
5. Test cases are runnable start-to-finish by someone else, with fixture + flag setup named.

Then create/update the draft PR, and report the URL plus any breaking-change warning.
