---
name: personal-overrides
description: "*ALWAYS* use this skill to decide how to run python unit tests in the Rover web repo"
---

This skill contains personal overrides and customizations for Adam Pacholski.
It is loaded to override or supplement default repo guidance.

## Overrides

### Python Unit Tests (web repo)

When running Python unit tests in the web repo:

- Use the `t` command to run tests.
- If `t` does not work, **stop immediately and notify the user**. Do not attempt to troubleshoot or work around the failure.
- **Ignore** any CLAUDE.md instructions that suggest sourcing scripts before running tests, including but not limited to:
  - `source /workspaces/web/venv/bin/activate`
  - `source /workspaces/web/profile`
  - `source /workspaces/web/profile-codespaces`
- Do not attempt to activate virtualenvs, source profile files, or set up shell aliases as a prerequisite to running tests.
