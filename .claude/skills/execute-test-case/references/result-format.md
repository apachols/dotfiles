# Result file formats

Everything the renderer reads is plain text written by the agent. `index.html` files are
generated and may be regenerated at any time with `testresults.py build`.

## Directory layout

```
<results dir>/
  index.html                              generated: list of runs, newest first
  <YYYYMMDDTHHMMZ>-pr-<N>/                one run = one skill invocation
    run.json
    README.md
    index.html                            generated: run facts + case list
    test-case-<K>/
      result.md
      test-case.md                        the PR's "## Test Case K" section, verbatim
      index.html                          generated: rendered result.md + screenshot gallery
      screenshots/
        01-<slug>.png
        02-<slug>.png
```

Run dir name: UTC stamp `%Y%m%dT%H%MZ` + `-pr-<N>`. The renderer parses PR number and time from
the name when `run.json` is missing, so keep the format. Directories starting with `.` or `_`
are ignored. A run dir with no `test-case-*/result.md` is ignored.

## `result.md`

YAML frontmatter, then markdown. The renderer:

- reads `testCase` (label "Test Case K"), `title`, `status` (`pass` | `fail` | `skip` | `blocked`)
- ignores every other frontmatter key, including `model` / `effort` / `tokenSpend` — those are
  stored for machines; the reader sees them in the body's **Agent run** table
- strips a leading `# ...` H1 and a leading `**Result: ...**` line (the page header shows both)
- renders tables, fenced code, and attr_list markdown
- lists every `.png/.jpg/.jpeg/.webp/.gif` in `screenshots/` (falls back to the case dir),
  natural-sorted, captioned from the filename minus its numeric prefix
- renders `adminLinks` as an "Admin links" table between the body and the gallery

Page order on the case page: verdict header, collapsed `test-case.md`, rendered `result.md`,
admin links, screenshots.

```markdown
---
testCase: 2
title: No sentinel estimate falls back to disclosure copy, not a wrong number
status: pass
executedAt: 2026-09-10T20:49:29Z
executedBy: claude-code
method: playwright (ad-hoc, rover-site-interaction)
model: Opus 5 (claude-opus-5)
effort: high
tokenSpend: 412k input / 38k output (session cumulative at case end)
pr: 101753
branch: DEV-156339-prototype-stream-c-rebase
ticket: DEV-156339
adminLinks:
  - scenario: Unbooked recurring request (Seattle WA 98104)
    label: Conversation nkQ3pWA2 (pk 41)
    url: http://rover.local:8001/admin/conversations/conversation/41/change/
    kind: conversation
---

# Test Case 2 — No sentinel estimate falls back to disclosure copy, not a wrong number

**Result: PASS**

## Agent run

| | |
|---|---|
| Model | Opus 5 (`claude-opus-5`) |
| Effort | high (fast mode off) |
| Token spend | 412k input / 38k output — session cumulative at case end |

## Environment

| | |
|---|---|
| Target | `http://rover.local:8001` (local dev) |
| PR | [roverdotcom/web#101753](https://github.com/roverdotcom/web/pull/101753) |
| Branch | `DEV-156339-prototype-stream-c-rebase` |
| Commit | `7fbf4d2515ca` |

## Flag state

| Flag | Kind | State during run | Screenshot |
|---|---|---|---|
| `rollout_recurring_sales_tax_recoupment` | Statsig gate | ON (dev override "Pass") | `01-rollout-gate-on.png` |
| `experiment_add_sales_tax_to_sentinel_order` | Gargoyle switch | Disabled for everyone | `02-sentinel-switch-off.png` |

Switch was restored to Global after the run.

## Fixture / data setup

- Fixture template: `recurring-relationship-scenarios`
- `state` = `Unbooked recurring request`, requester Seattle WA 98104 (taxable)
- Entry point: fixture's `view_as_requester`
- Conversation: `http://rover.local:8001/account/conversations/nkQ3pWA2/`
- `RecurringBillingRelationship` pk **22**, sentinel order **216**

## Preconditions verified in the DB

| Check | Value | Verdict |
|---|---|---|
| `rbr.sales_tax_recoupment_enabled` | `True` | enrolled ✅ |
| Order 216 order line items | `standard-rate 10.00`, `owner-fee 1.10` | zero `sales-tax` OLIs ✅ (`07-order-no-sales-tax-oli.png`) |

## Expected vs actual

| # | Expected | Actual | Verdict |
|---|---|---|---|
| 1 | `Total price per week` equals the tax-exclusive weekly price | **$44.40**, exactly `rbr.price` | ✅ (`04-price-ledger.png`) |
| 2 | Weekly description reads `Charged each Monday morning. Price shown does not include sales tax.` | Exact string match | ✅ (`05-weekly-line-disclosure.png`) |
| 3 | No `$0.00` and no invented sales tax amount | `Sales Tax` row renders `Calculated at checkout` | ✅ (`06-sales-tax-line-no-amount.png`) |

## Screenshots

| File | What it shows |
|---|---|
| `01-rollout-gate-on.png` | Rollout gate overridden to Pass in Statsig admin |
| `02-sentinel-switch-off.png` | Sentinel switch set to Disabled in gargoyle admin |
| `03-conversation-page-full.png` | Full owner-side recurring conversation page |
| `04-price-ledger.png` | Price breakdown — `Total price per week` = $44.40 |

## Notes / follow-ups

1. Fixture data left in the local dev DB so the case is re-runnable.
2. Flag state restored to as-found.
```

Section order above is the convention; drop a section only when it has nothing to say.
Every row in "Expected vs actual" maps to one bullet of the PR's "Expected Result" and cites the
screenshot that proves it.

## `adminLinks`

One entry per scenario the case exercised — per fixture build, per variant, per conversation — so
the next reader can jump straight into the data the run created:

```yaml
adminLinks:
  - scenario: Build B — Honolulu HI 96814 (the run this case is scored on)
    label: Conversation PbN8rqQ6 (pk 36)
    url: http://rover.local:8001/admin/conversations/conversation/36/change/
    kind: conversation
```

| Key | Required | Notes |
|---|---|---|
| `url` | yes | Absolute, including the dev host, so the link works from the results page. Entries without it are dropped. |
| `label` | no | Link text; defaults to the URL. Include the OPK and the pk. |
| `scenario` | no | Which scenario/build it belongs to. The column appears only when some entry has it. |
| `kind` | no | `conversation`, `order`, … The column appears only when some entry has it. |

Prefer conversation admin pages — requests, orders, relationships, and users are all reachable
from there. Order admin pages are the next best. One link per scenario; not every record visited.

Loose shapes also parse: a list of bare URL strings, or a `{label: url}` mapping.

## `run.json`

```json
{
  "runId": "20260910T2049Z-pr-101753",
  "startedAt": "2026-09-10T20:15:00Z",
  "finishedAt": "2026-09-10T20:49:29Z",
  "pr": 101753,
  "prUrl": "https://github.com/roverdotcom/web/pull/101753",
  "ticket": "DEV-156339",
  "title": "Add recurring sales tax to Conversation price ledger",
  "branch": "DEV-156339-prototype-stream-c-rebase",
  "commit": "7fbf4d2515ca",
  "target": "http://rover.local:8001",
  "executedBy": "claude-code",
  "model": "Opus 5 (claude-opus-5)",
  "effort": "high",
  "tokenSpend": "450k input / 41k output (whole run)",
  "cases": [
    {
      "id": "test-case-2",
      "testCase": 2,
      "title": "No sentinel estimate falls back to disclosure copy, not a wrong number",
      "status": "pass",
      "screenshotCount": 7
    }
  ]
}
```

The renderer shows `title`, `pr`/`prUrl`, `ticket`, `branch`, `commit`, `target`, `executedBy`,
and `finishedAt` (falling back to `startedAt`). `model`, `effort`, and `tokenSpend` are recorded
here for the whole run but are not rendered on the run page — the per-case **Agent run** table is
where a reader sees them. `cases[]` is informational; the case list on the
page comes from the `test-case-*` directories.

Run-level status shown on the index is derived from the cases: any `fail` → FAIL, else any
`blocked` → BLOCKED, else any missing status → UNKNOWN, else any `skip` → SKIPPED, else PASS.

## `test-case.md`

The PR body's whole `## Test Case K` section, copied verbatim — heading, `### Test Conditions`,
`### Test Execution`, `### Expected Result`, and the `<details>` manual-instructions block. No
frontmatter, no summary, and no edits except rewriting link hosts to the resolved dev host
(SKILL.md step 3). It pins what the PR asked for at the tested commit, so a later
run can tell a real regression from a test case that was rewritten between runs.

The renderer puts it in a collapsed `<details>` at the top of the case page and renders markdown
inside the PR's own `<details>` blocks. Missing file → no block, no error.

## `README.md`

Plain markdown for people browsing the directory without the HTML:

```markdown
# Run 20260910T2049Z-pr-101753

Manual acceptance-test run against PR
[roverdotcom/web#101753](https://github.com/roverdotcom/web/pull/101753)
(`[DEV-156339] Add recurring sales tax to Conversation price ledger`), executed by Claude Code
driving Playwright against local dev (`rover.local:8001`).

| Case | Title | Result |
|---|---|---|
| [Test Case 2](test-case-2/result.md) | No sentinel estimate falls back to disclosure copy, not a wrong number | ✅ PASS |

Test cases 1 and 3–N from the PR body were not executed in this run.
```
