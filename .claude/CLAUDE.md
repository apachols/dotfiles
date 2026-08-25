## GitHub CLI in Codespaces

`GITHUB_TOKEN` exists only in the login-shell env (`/etc/profile.d/codespaces.sh`).
The Bash tool runs a non-login shell, so bare `gh` fails with "gh auth login".
Run every `gh` command through a login shell:

    bash -lc 'gh pr view 100607 --json number,title,state'
