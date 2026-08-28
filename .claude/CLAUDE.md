## GitHub CLI in Codespaces

`GITHUB_TOKEN` exists only in the login-shell env (`/etc/profile.d/codespaces.sh`).
The Bash tool runs a non-login shell, so bare `gh` fails with "gh auth login".
Run every `gh` command through a login shell:

    bash -lc 'gh pr view 100607 --json number,title,state'

## Rules for Rover Web

When you are working in the `web` repo, please strictly follow these conventions:

- DO NOT run any unit tests unless I ask for that explicitly (ask first)
- DO NOT commit or push any code unless I ask for that explicitly (ask first)
