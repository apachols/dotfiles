# Single Test Case Format

Canonical shape of **one** test case in the `### Test Cases` section of a PR body.
The block wrapper around test cases (the `## Test Case N` headings) lives in
`pr-template.md` — this file governs only what goes *inside* one case.

## Shape

```
## Test Case N
[ ] <one-line summary of what this case proves>

### Test Conditions
- <precondition>
- <precondition>
### Test Execution
<the user action being tested>
### Expected Result
- <observable outcome>
- <observable outcome>

<details>
<summary>Manual Test Instructions</summary>

* <instruction line>
  - <detail line / link>
* <instruction line>
  - <detail line / link>

</details>
```

## Why the steps are collapsed

- On first read the reviewer should see only the **intention** of each test — conditions, action, expected result
- The manual steps stay inside `<details>` so they are collapsed by default
- When executing, the reviewer opens one case at a time and follows just those instructions
- Never hoist the manual steps out of the `<details>` block, and never leave it open

## Test Conditions / Test Execution / Expected Result

- Describe only the intention and internal logic of the test
- Leave out the details — those go in Manual Test Instructions
- We are constructing a proof of correctness
- If we set up XYZ specific things, and then do some user action, what should we expect?
- Expected Result bullets are observable: DB field values, OLIs, ledger lines, page state

## Manual Test Instructions

- Assume the tester is familiar with the Rover web app but is trying to execute multiple tests correctly as quickly as possible
- Each instruction combines one line of instruction text, and one line of detail
- The detail line includes a hyperlink to the local test environment where possible
- Where a link isn't possible, the detail line provides extra detail on how to execute
- Link to admin **list** pages — record-specific edit page URLs need an id, and the test records don't exist yet
- It's okay to roll a common workflow, like "book a stay", into a single line with a description instead of four steps and four links
- Never list "run these unit tests" as a manual step — CI does that

## Example

```
## Test Case 1
[ ] Rollout flag off, nothing enrolls

### Test Conditions
- With the flag off
- In a taxable US state
- With a non-Bright-Horizons user
- On Unified Checkout
### Test Execution
Book a new recurring relationship without using fixture templates
### Expected Result
- `rbr.sales_tax_recoupment_enabled is False`
- No `sales-tax` OLI on the order
- No tax line on the checkout ledger

<details>
<summary>Manual Test Instructions</summary>

* Set flag OFF at
  - http://rover.local:8001/admin/statsig_gates/rollout_recurring_sales_tax_recoupment/
* Create a user with /uc-recurring-scenario/, but leave the booking
  - http://rover.local:8001/dev/fixtures/templates/uc-recurring-scenario/
* Find the sitter in search, and send a recurring request
  - http://rover.local:8001/search/?service_type=dog-walking&frequency=recurring
* Book the request, and expect checkout ledger to show sales tax
  - search => contact => inbox => book
* Expect rbr.sales_tax_recoupment_enabled to be False in the RBR admin
  - http://rover.local:8001/admin/recurring/recurringbillingrelationship/?q=
* Expect no sales-tax OLI on the order in the order admin
  - http://rover.local:8001/admin/orders/order/?q=

</details>
```
