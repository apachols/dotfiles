#!/usr/bin/env bash
# SessionStart hook: make a session that never ran a login shell look like one.
#
# Claude Code prepends the contents of $CLAUDE_ENV_FILE to each Bash tool
# invocation, which is how we replace what /etc/profile.d/codespaces.sh and
# .codespacesrc do for login shells. Sessions that skip those - the Claude
# desktop app, sshd into the Codespace, IDE extensions - get it all from here.
#
# Also runs in roverspaces (Coder), which already covers most of this itself:
# $BASH_ENV sources a Coder-generated script into every bash process (secrets,
# PATH, PRE_COMMIT_ENABLED), and Claude's shell-snapshot mechanism sources
# captured functions/aliases/PATH before every Bash tool call. Neither carries
# plain `export FOO=bar` rc-file statements, which is the one real gap in both
# environments - see LOAD-BEARING EXPORTS below.
#
# Blocks marked CODESPACES-ONLY are already dead weight in roverspaces (their
# `[ -r "$secrets" ]` guards no-op them) - delete outright once Codespaces is gone.
#
# Hook scripts are spawned by the harness, not through the Bash tool, so they
# never see this file. Anything a hook needs must be resolved by path inside the
# hook itself: see python-format.sh.
[ -n "$CLAUDE_ENV_FILE" ] || exit 0

# --- CODESPACES-ONLY ----------------------------------------------------------
# --- Codespace secrets: CODESPACE_NAME, GITHUB_TOKEN, AWS creds, ... ---------
secrets=/workspaces/.codespaces/shared/.env-secrets
if [ -r "$secrets" ]; then
    while IFS= read -r line; do
        case "$line" in
            *=*) printf 'export %s=%q\n' "${line%%=*}" "$(printf %s "${line#*=}" | base64 -d 2>/dev/null)" ;;
        esac
    done < "$secrets" >> "$CLAUDE_ENV_FILE"
fi

# --- CODESPACES-ONLY: roverspaces gets GEMFURY_READ_URL from $BASH_ENV already ---
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
# Not Codespaces-only: still real in roverspaces too, in case the shell
# snapshot was captured before a `pip install` or similar ran.
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

# --- EXPORTS FOR AGENT SHELLS -------------------------------------------------
# Neither the shell snapshot nor $BASH_ENV carries plain `export FOO=bar`
# statements from .bashrc/.codespacesrc/.roverspacesrc - both capture functions,
# aliases and PATH, not arbitrary env vars. Most such exports are cosmetic
# (BRANCH_COLOR); these actually change behavior, so mirror them here by hand.
# There's no safe way to source the rc files directly - they cd and activate a
# venv - so keep this list in sync with its source of truth on the left.
printf 'export DC_PARAMS=%q\n' "--profile stripe" >> "$CLAUDE_ENV_FILE"                    # .codespacesrc / .roverspacesrc
printf 'export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=%q\n' "1" >> "$CLAUDE_ENV_FILE"        # .bashrc
printf 'export CLAUDE_CODE_DISABLE_ARTIFACT=%q\n' "0" >> "$CLAUDE_ENV_FILE"                # .bashrc

# --- Report whatever is still missing into the session -----------------------
doctor="$HOME/.claude/hooks/rover-doctor.sh"
[ -x "$doctor" ] && exec "$doctor" --hook "$repo"
exit 0
