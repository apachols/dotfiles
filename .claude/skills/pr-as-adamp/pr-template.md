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
- Written by the create-pr-test-suite skill, together with "Acceptance tests". Use its output as is.
```

- 🚩 _Are there any feature flags to enable?_
- 📄 _Are there any users or fixtures to create?_

## Acceptance tests

```
Style Notes
- Written by the create-pr-test-suite skill, together with "Before testing". Use its output as is.
```

> [!IMPORTANT]
> ♿️ If any features should be tested for accessibility, be sure to include them here.

- [ ] _Given ..., When ..., Then ..._
- [ ] _Given ..., When ..., Then ..._
