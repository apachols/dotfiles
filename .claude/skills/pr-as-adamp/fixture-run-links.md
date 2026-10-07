# Fixture Run Links

A test case's fixture step links to the template's `/run` page. One click builds the fixture
with the given options and lands the tester on an entry point:

```
http://rover.local:8001/dev/fixtures/templates/<slug>/run?entrypoint=<entry_point>&impersonate=true&<optionName>=<JSON value>&...
```

Don't link the bare template page and list options for the tester to pick. That leaves a form
to fill and an entry point to click, and Playwright trips on the form's duplicate `root_*` ids.

## 1. Find the template

Grep `(FixtureSetTemplate)` for candidates. The `slug` is a few lines below each class, next to
`options_serializer_class`.

## 2. Read its options and entry points

With the local server up, the template API returns both, in the names and values the URL takes:

```bash
curl -s --compressed -H 'Accept: application/vnd.rover.api.camel+json' \
  http://rover.local:8001/api/v7/fixtures/templates/<slug>/ \
  | jq '{entryPoints: [.metadata.entryPoints[] | select(.isDeeplink | not) | .name], options: (.properties | map_values({type, default, enum}))}'
```

Without the server, read the source:

- **Option names**: the options serializer's fields, base classes included, camelCased
  (`booking_engine_state` → `bookingEngineState`).
- **Enum values**: the choice key, which isn't always the attribute name. A `Choices` triple is
  `(key, attribute, label)`, so `RECURRING_SERVICE_TYPES_CHOICES.walking` is `"dog-walking"`.
- **Entry points**: the keys of the dict `get_entry_points()` returns. Skip `*_deeplink` ones;
  they open the mobile app.

## 3. Choose the values

- Pass every option the test case depends on, even one that equals the default. Leave the rest out.
- Pick the entry point where the next instruction starts, e.g. `view_as_requester` when the
  requester acts first.
- Keep `impersonate=true`. Entry points impersonate through admin `become_user`, which needs a
  staff session.

## 4. Encode the values

The page `JSON.parse`s each value and validates it against the schema before it builds, so a
value must be JSON of the option's schema `type`. A string option needs quotes even when it looks
like a number: `postalCode=96814` parses to a number, fails validation, and nothing gets built.
Generate the query string rather than hand-encoding it:

```bash
python3 -c 'import json, urllib.parse as up; o = {"bookingEngineState": "booked", "serviceType": "dog-walking", "postalCode": "96814"}; print("&".join(f"{k}={up.quote(json.dumps(v))}" for k, v in o.items()))'
```

## 5. Write the instruction

The link builds the fixture and enters it, so one instruction replaces "build the fixture" and
"open it as the requester":

```
* Build a booked recurring walk relationship in Honolulu, open it as the requester
  - http://rover.local:8001/dev/fixtures/templates/uc-recurring-scenario/run?entrypoint=view_as_requester&impersonate=true&bookingEngineState=%22booked%22&serviceType=%22dog-walking%22&postalCode=%2296814%22
```

- Describe the scenario in words on the instruction line. The URL carries the values.
- Every visit to a `/run` link builds a new fixture. To act as another entity on the same build,
  send the tester to the latest build and name the entry point:
  `http://rover.local:8001/dev/fixtures/builds/` => latest build => `view_as_provider`.
- For "same fixture as Test Case 1", repeat the full link so each case runs on its own.
