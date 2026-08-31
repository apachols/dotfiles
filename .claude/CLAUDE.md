## GitHub CLI in Codespaces

`GITHUB_TOKEN` exists only in the login-shell env (`/etc/profile.d/codespaces.sh`).
The Bash tool runs a non-login shell, so bare `gh` fails with "gh auth login".
Run every `gh` command through a login shell:

    bash -lc 'gh pr view 100607 --json number,title,state'

## Rules for Rover Web

When you are working in the `web` repo, please strictly follow these conventions:

- DO NOT run any unit tests unless I ask for that explicitly (ask first)
- DO NOT commit or push any code unless I ask for that explicitly (ask first)

The `web` repository is FULL of files with common / repeated / duplicate file names - forms.py, models.py, etc. Always print file names namespaced to the django app folder they are in: seo/models.py, api/current/serializers/models.py.

When you offer to run unit tests, ALWAYS offer to run only changed tests files, and in those files PREFER to run only changed test suite classes. CI will catch any other tests that failed in other places in the same app. If you think there is a good reason to run an entire folder or entire app worth of tests, please let the user know, and explain your reasoning as concisely as possible.
