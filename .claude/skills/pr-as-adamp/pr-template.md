---

```
General Style Notes
- Always delete the existing bullet points
- Every section should be written in ultra concise bullet points
- Bullet points MUST BE shorter than 150 characters
- Use as few words as possible
```

# What is the reason for this pull request?

```
Style Notes
- Limit: 150 words
- audience should be "familiar with Rover but not familiar with this area"
- Do not include a description of what we didn't change
- ONLY the reasons for the pull request, in 1-3 bullet points
- A "reason" answers "what is changing and why are we making this change"
- Anything that is good-to-know context but is NOT a reason for the change belongs in "Additional Context" below (design rationale, why this object / layer was chosen, migration or backfill implications, row counts, alternatives considered, follow-up work)
```

- _What is changing in this PR?_
- _Why are we making these updates?_

## Additional Context

```
Style Notes
- Limit: 300 words
- Always immediately below "What is the reason for this pull request?"
- This section is NOT in the repo PR template; add it anyway as a subsection for "why are we changing this"
- Ultra concise bullet points, same as every other section
- Holds supporting context that is useful but is not a reason for the change
- Omit the section entirely if there is no context worth stating

Example of the split between the two sections:

    # What is the reason for this pull request?

    - Adds `RecurringBillingRelationship.sales_tax_recoupment_enabled`, a nullable boolean. Schema + data-compliance policy only — nothing reads or writes it yet.
    - Rover reports and remits US sales tax on recurring bookings but never charges the owner, so Rover absorbs it. Recoupment ships to **new relationships only**.

    # Additional Context

    - The relationship is the only object with the right lifetime — a recurring relationship creates a new conversation every cycle, so the existing per-conversation `SalesTaxEligibility` row would switch tax on for relationships already in flight.
    - `NULL` reads as "not enrolled", so **no backfill**: all 307,761 existing relationships keep today's behavior with zero rows written.
```

- _Supporting context that is not itself a reason for the change_

# Deployment

## How can I tell if this change has been deployed?

```
Style Notes
- Between 1 and 3 bullet points
- Each line should describe a measurable outcome (prod behavior, splunk, datadog, etc)
```

- _What new events and behaviors do we expect to occur in production?_
- _Are there dashboards that I can refer to?_
- _Are there logging messages we expect to see?_

## Did anything break? How can I tell if this code is **NOT** working in production?

```
Style Notes
- Between 1 and 3 bullet points
- Each line should describe a measurable outcome (prod behavior, splunk, datadog, etc)
```

- _Is there a particular dashboard that's useful to watch?_
- _What are potential issues we should look out for?_
- _Are there any new side effects of this change?_

## Does this code include breaking changes to our mobile apps?

```
Style Notes
- Delete the "Note" info box below
- Warn the PR author if it looks like the PR might actually contain breaking changes
```

> [!NOTE]
> A **breaking change** is any API modification that could cause issues for our iOS, Android, or React Native apps. Examples include:
>
> - Removing a key from an API response that native apps rely on
> - Changing the type of an existing key (e.g., string → integer, object → array)
> - Renaming a key in an API response without maintaining backwards compatibility
> - Changing the semantics of a value (e.g., a field that was nullable now never returns null, or vice versa)
>
> Since mobile app users may be on older versions that cannot be force-updated, breaking API changes can cause crashes or rendering failures in the wild.
>
> **Remember:** it might work for you and in your simulator, but older app versions in the wild have older React Native code and may consume the API differently.

- [x] It does not contain breaking changes
- [ ] It does

## To which brands does this work impact?

```
Style Notes
- Remove the "this is a temporary question" annotation
```

_This is a temporary question to drive multi-brand awareness for new features. For any questions, you can reach out to the [integrations team](https://rover.enterprise.slack.com/archives/C07UUJLMM2T). We will remove this question by the end of March._

- [x] Rover
- [x] Cat in a Flat
- [x] [DogBuddy](https://roverdotcom.atlassian.net/wiki/spaces/TEAM/pages/5680367065/US+DogBuddy+Expansion+-+Technical+Summary)
- [x] MadPaws
- [ ] None. It doesn't impact users

# AI tools

## Code Generation

_Roughly what percentage of the lines of code were initially authored by an AI assistant?_

```
Style Notes
- Always select "all or nearly all"
```

- [ ] None (0%)
- [ ] Some (1-25%)
- [ ] Substantial (25-75%)
- [ ] All or nearly all (>75%)

```
Style Notes
- Do not add the optional note on AI tool use
- Remove the "optionally add a note" callout
```

> [!TIP] > _Optionally add a note on the AI tool and what you used it for, e.g. "used Claude Code to generate Django Admin page and add tests"_

## Instructions for reviewers (including agents, e.g. Claude, Copilot)

```
Style Notes
- Eliminate this section entirely if there are no frontend changes
```

- [ ] Review frontend code in this diff for WCAG 2.2 AA accessibility conformance, and flag any violations. See [Accessibility Testing Checklist](https://roverdotcom.atlassian.net/wiki/spaces/TECH/pages/2645786627/Accessibility+Testing+Checklist) for more.

# Code Review Instructions

## Before testing

```
Style Notes
- This section should be local (or staging) env setup steps necessary for manual testing
- Steps should be in bullet points
- Please indent and nest bullet points if a particular step has several substeps

Answer the "are there feature flags" question first.  Show only the feature flag names:

Example Output
🚩 Feature Flags
`recurring_billing_sales_tax_enabled`
`killswitch_my_buggy_feature`

<2> For "are there users or fixtures to create", most PR manual test suites start by using fixture templates to create new DB records.

This is frequently "Standard Scenario", but use your best judgement as to which fixture best fits the codepaths we need to exercise.

Each test case should describe how to create the necessary users via the fixture templates.

In this section, simply list the fixture template names that are used in the test cases, with no additional explanation.

Example Output:

📄 Fixture Templates
`recurring-billing-scenarios`
http://rover.local:8001/dev/fixtures/templates/recurring-billing-scenarios
`standard-scenario`
http://rover.local:8001/dev/fixtures/templates/1-standard-scenario


Note: You can grep for "(FixtureSetTemplate)" and it will show all the different fixture set classes, and in the next few lines the slug (e.g. "1-standard-scenario") will be defined.
```

- 🚩 _Are there any feature flags to enable?_
- 📄 _Are there any users or fixtures to create?_

## Acceptance tests

```
Style Notes

- Remove the "If any features should be tested for accessibility" box
- If any accessibility testing is necessary, include that in its own "Accessibility Test Cases" section, inserted before the main "Test Cases" section

Test Suite Description

The preferred approach is to construct a concise test suite description such that a reviewer can execute specific steps in their own environment and see desired outcomes.

Format the acceptance tests section like this — each test case titled with a `## Test Case N` heading, no `___` separators:

### Test Cases

## Test Case 1
[ ] Rollout flag off, nothing enrolls

<single test case body>

## Test Case 2
[ ] Rollout flag on, everyone enrolls

<single test case body>

## Test Case 3
[ ] Rollout flag on, recurring booking cycling

<single test case body>

GitHub renders a `##` heading with its own horizontal rule underneath, so the headings do the
visual separating that `___` used to do. Note the heading level: the case title is `##`, and the
sections inside a case (`### Test Conditions`, etc.) stay at `###`.

The body of a single test case is NOT defined here. Read `testcase-format.md` next to this
file and follow it for every `<single test case body>` above: the Test Conditions /
Test Execution / Expected Result sections, and the collapsed Manual Test Instructions block.

Other Testing Do's and Do-Not's:
- Don't list "run these unit tests" as a manual test step, CI will do that

The test suite should completely exercise the changes to the application code, or if it isn't realistic / practical / time efficient to manual test something, that should be called out in a separate section at the end:

### Out of Scope

- It wasn't possible to manual test the /landing/signup page, since that is 3rd party hosted and not available in local dev
- We should test the Elasticsearch changes by deploying to staging, and doing a couple test searches
- No test steps added for Search Scores, as it isn't possible to test in local dev currently

Rules for Shell Plus Blocks:
- Please start code blocks for shell plus with "python" after the opening code block ticks, which will cause them to syntax highlight as python in the github PR page.
- It's okay that shell plus scripts are only "mostly python", we just want more than zero syntax highlighting.
- Always assume the user will click "copy" and then paste the whole shell plus block into a shell plus session
- Never set up the shell plus blocks as "one-liners" using m shell_plus -c "'from stays.event_notifications ...'"
- You don't ever need to import models classes, all the models in the django app are automatically imported in our shell_plus sessions
- If it's possible, always use the .last() ORM filter to grab the most recent stay / conversation / etc
- Since we use fixture data for most test cases, we should usually be able to go grab the most recent record of that type

```

> [!IMPORTANT]
> ♿️ If any features should be tested for accessibility, be sure to include them here.

- [ ] _Given ..., When ..., Then ..._
- [ ] _Given ..., When ..., Then ..._
