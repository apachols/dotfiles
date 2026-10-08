# Test Suite Format

Shape of the two PR body sections this skill writes: `## Before testing` and
`## Acceptance tests`. The inside of one test case is in `testcase-format.md`.

## Before testing

Local (or staging) env setup the test cases need, as bullets. Nest sub-bullets when a step has
substeps.

Answer the feature flag question first: each flag name, its admin link, and how to flip it.
Then list every fixture template the cases use, each with its template page link. Each test
case builds its own fixture through a `/run` link, so this list is only a summary.

Find candidates by grepping `(FixtureSetTemplate)`; the slug is a few lines below each class.
Pick the template that best fits the code paths under test, and fall back to
`1-standard-scenario` only when nothing fits better.

```
- 🚩 Feature Flags
  - `rollout_recurring_sales_tax_recoupment`
  - http://rover.local:8001/admin/statsig_gates/rollout_recurring_sales_tax_recoupment/
  - ON = Create New Override => Environment => Pass. OFF = delete the override. Allow ~1 min for the SDK.
- 📄 Fixture Templates
  - `uc-recurring-scenario`
  - http://rover.local:8001/dev/fixtures/templates/uc-recurring-scenario
- 📍 Tax address: `postal_code = 96814` (Honolulu, HI)
- ✏️ Edit a week: stay page => **Modify schedule** => **Manage current week** => check/uncheck a walk
```

After flags and fixtures, add a bullet for any setup or workflow several cases share, so each
case can refer to it in one line instead of repeating it.

## Acceptance tests

- Delete the repo template's `> [!IMPORTANT]` accessibility box and its placeholder bullets.
- If any accessibility testing is needed, put it in its own `### Accessibility Test Cases`
  section, before `### Test Cases`.
- Title each case with a `## Test Case N` heading. No `___` separators: GitHub draws a rule
  under a `##` heading. The sections inside a case stay at `###`.

```
### Test Cases

## Test Case 1
- [ ] Rollout flag off, nothing enrolls

<single test case body>

## Test Case 2
- [ ] Rollout flag on, everyone enrolls

<single test case body>

## Test Case 3
- [ ] Rollout flag on, recurring booking cycling

<single test case body>
```

Write every `<single test case body>` per `testcase-format.md`.

`execute-test-case` slices the PR body on these `## Test Case N` headings, so keep the heading
text exact.

### Coverage

- The suite should exercise every behavior the diff changes.
- Never list "run these unit tests" as a manual step. CI runs them.
- Anything not realistic or practical to manual-test goes in a final `### Out of Scope`
  section, one bullet per item with the reason:

```
### Out of Scope

- It wasn't possible to manual test the /landing/signup page, since that is 3rd party hosted and not available in local dev
- We should test the Elasticsearch changes by deploying to staging, and doing a couple test searches
- No test steps added for Search Scores, as it isn't possible to test in local dev currently
```

## shell_plus blocks

- Fence them as ```` ```python ```` so GitHub highlights them. Mostly-python is fine.
- Assume the tester copies the whole block and pastes it into a shell_plus session.
- Never write a one-liner via `m shell_plus -c "..."`.
- Don't import model classes; shell_plus auto-imports them.
- Use `.last()` to grab the most recent stay / conversation / etc. Test cases build their data
  from fixtures, so the newest record is usually the right one.
