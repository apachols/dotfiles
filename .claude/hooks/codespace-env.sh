#!/usr/bin/env bash
# SessionStart hook: make a session that never ran a login shell look like one.
#
# Claude Code prepends the contents of $CLAUDE_ENV_FILE to each Bash tool
# invocation, which is how we replace what /etc/profile.d/codespaces.sh and
# .codespacesrc do for login shells. Sessions that skip those - the Claude
# desktop app, sshd into the Codespace, IDE extensions - get it all from here.
#
# Hook scripts are spawned by the harness, not through the Bash tool, so they
# never see this file. Anything a hook needs must be resolved by path inside the
# hook itself: see python-format.sh.
[ -n "$CLAUDE_ENV_FILE" ] || exit 0

# --- Codespace secrets: CODESPACE_NAME, GITHUB_TOKEN, AWS creds, ... ---------
secrets=/workspaces/.codespaces/shared/.env-secrets
if [ -r "$secrets" ]; then
    while IFS= read -r line; do
        case "$line" in
            *=*) printf 'export %s=%q\n' "${line%%=*}" "$(printf %s "${line#*=}" | base64 -d 2>/dev/null)" ;;
        esac
    done < "$secrets" >> "$CLAUDE_ENV_FILE"
fi

# --- Gemfury pip index, which .codespacesrc builds for login shells -----------
# Read the token back out of .env-secrets rather than $GEMFURY_API_TOKEN: this
# script is spawned by the harness, so its own environment is not guaranteed to
# carry the Codespace secrets even though the loop above just exported them into
# $CLAUDE_ENV_FILE for the Bash tool.
if [ -r "$secrets" ]; then
    fury=$(sed -n 's/^GEMFURY_API_TOKEN=//p' "$secrets" | head -1 | base64 -d 2>/dev/null)
    [ -n "$fury" ] &&
        printf 'export GEMFURY_READ_URL=%q\n' \
            "https://repo.fury.io/${fury}/roverdotcom/" >> "$CLAUDE_ENV_FILE"
fi

# --- User-installed tools (claude, uv, ...) that a login shell puts on PATH ---
[ -d "$HOME/.local/bin" ] &&
    printf 'export PATH=%q:"$PATH"\n' "$HOME/.local/bin" >> "$CLAUDE_ENV_FILE"

# --- Repo tooling that `source venv/bin/activate` would have supplied --------
repo="${CLAUDE_PROJECT_DIR:-}"
[ -n "$repo" ] || repo="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -n "$repo" ] || repo="${WEB:-}"

if [ -d "$repo/venv/bin" ]; then
    printf 'export VIRTUAL_ENV=%q\n' "$repo/venv" >> "$CLAUDE_ENV_FILE"
    for dir in "$repo/venv/bin" "$repo/dev-env/cli"; do
        [ -d "$dir" ] && printf 'export PATH=%q:"$PATH"\n' "$dir" >> "$CLAUDE_ENV_FILE"
    done
fi

# config/hooks/pre-commit is a silent no-op without this, so `git commit` skips
# ruff, pnpm lint and the git-config checks and says nothing about it.
[ -f "$repo/.pre-commit-config.yaml" ] &&
    printf 'export PRE_COMMIT_ENABLED=true\n' >> "$CLAUDE_ENV_FILE"

# --- Report whatever is still missing into the session -----------------------
doctor="$HOME/.claude/hooks/rover-doctor.sh"
[ -x "$doctor" ] && exec "$doctor" --hook "$repo"
exit 0
