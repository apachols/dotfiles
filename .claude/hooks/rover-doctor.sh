#!/usr/bin/env bash
# Checks that a Claude session has the tooling the web repo's hooks and commit
# path need, and makes the gaps visible instead of silent.
#
#   rover-doctor.sh              human-readable report; exit 1 if anything failed
#   rover-doctor.sh --hook REPO  silent when healthy, SessionStart JSON when not
#
# Add a check to the "CHECKS" section and both modes pick it up. This file is the
# single list of what a session needs, so it's also the answer to "what does a
# login shell give me that this session doesn't?".
set -uo pipefail

mode=report
repo=""
case "${1:-}" in
    --hook) mode=hook; repo="${2:-}" ;;
esac

log=$HOME/.claude/rover-doctor.log

# Resolve the repo root the same way in both modes.
if [ -z "$repo" ]; then
    for candidate in "${CLAUDE_PROJECT_DIR:-}" "$(git rev-parse --show-toplevel 2>/dev/null)" "${WEB:-}"; do
        if [ -n "$candidate" ] && [ -d "$candidate" ]; then
            repo=$candidate
            break
        fi
    done
fi

passed=()
failed=()
ok()   { passed+=("$1"); }
bad()  { failed+=("$1 — $2"); }

# Which platform provisioned this machine. Codespaces sets CODESPACES=true in
# the container env; Coder (roverspaces) sets CODER=true via $BASH_ENV, which
# every bash process sources, hooks included.
platform=laptop
if [ "${CODESPACES:-}" = true ]; then
    platform=codespaces
elif [ "${CODER:-}" = true ] || [ -n "${ROVERSPACE_NAME:-}" ]; then
    platform=roverspaces
fi

# In a hook, what matters is what the Bash tool will see. In Codespaces that is
# the env file the SessionStart hook just wrote; in roverspaces most of it comes
# from $BASH_ENV instead, which this process has already sourced, so fall back
# to our own environment when the file has no entry.
env_value() {
    local value=""
    if [ -n "${CLAUDE_ENV_FILE:-}" ] && [ -r "$CLAUDE_ENV_FILE" ]; then
        value=$(sed -n "s/^export $1=//p" "$CLAUDE_ENV_FILE" | tail -1 | tr -d "\"'")
    fi
    [ -n "$value" ] || value="${!1:-}"
    printf %s "$value"
}

###
# MARK: CHECKS
###

if [ -z "$repo" ]; then
    bad "repo root" "unresolvable: CLAUDE_PROJECT_DIR, git and \$WEB were all empty"
elif [ ! -f "$repo/.pre-commit-config.yaml" ]; then
    # Not the web repo (or not a repo that lints); the rest doesn't apply.
    [ "$mode" = hook ] && exit 0
    echo "rover-doctor: $repo has no .pre-commit-config.yaml, nothing to check"
    exit 0
else
    ok "repo root $repo"
fi

pinned=$(awk '/ruff-pre-commit/ {found = 1} found && /rev:/ {gsub(/^v/, "", $2); print $2; exit}' \
    "$repo/.pre-commit-config.yaml" 2>/dev/null)

ruff=$(command -v ruff 2>/dev/null)
[ -n "$ruff" ] || ruff="$repo/venv/bin/ruff"
if [ -x "$ruff" ]; then
    version=$("$ruff" --version 2>/dev/null | awk '{print $2}')
    if [ -n "$pinned" ] && [ "$version" != "$pinned" ]; then
        bad "ruff $version" "pre-commit pins $pinned; formatting won't match CI. Refresh it with: bash -lc refresh_venv"
    else
        ok "ruff $version at $ruff"
    fi
else
    bad "ruff" "not on PATH nor at $repo/venv/bin/ruff, so Python edits go unformatted. Refresh it with: bash -lc refresh_venv"
fi

pre_commit=$(command -v pre-commit 2>/dev/null)
[ -n "$pre_commit" ] || pre_commit="$repo/venv/bin/pre-commit"
if [ -x "$pre_commit" ]; then
    ok "pre-commit $("$pre_commit" --version 2>/dev/null | awk '{print $2}') at $pre_commit"
else
    bad "pre-commit" "not on PATH nor at $repo/venv/bin/pre-commit. Refresh it with: bash -lc refresh_venv"
fi

# Worktree-safe: .git is a file, not a directory, in a linked worktree.
git_hook=$(git -C "$repo" rev-parse --git-path hooks/pre-commit 2>/dev/null)
case "$git_hook" in
    /*) ;;
    *) git_hook="$repo/$git_hook" ;;
esac
if [ -x "$git_hook" ]; then
    ok "git pre-commit hook installed"
else
    bad "git pre-commit hook" "missing at $git_hook, so commits run nothing. Run: ln -nfs $repo/config/hooks/pre-commit $git_hook"
fi

if [ "$(env_value PRE_COMMIT_ENABLED)" = true ]; then
    ok "PRE_COMMIT_ENABLED=true"
else
    bad "PRE_COMMIT_ENABLED" "not true, so git commit skips every pre-commit hook without a word"
fi

if [ -n "$(env_value GITHUB_TOKEN)" ]; then
    ok "GITHUB_TOKEN exported"
else
    bad "GITHUB_TOKEN" "not exported; gh and anything that shells out to it fail without it"
fi

# The machine's identity, as the repo reads it: settings/common.py takes
# MACHINE_NAME first and CODESPACE_NAME as the fallback, and fixture tracking
# keys off CODESPACE_NAME alone. Which one must be present depends on the platform.
case "$platform" in
    codespaces)  identity_vars=(CODESPACE_NAME) ;;
    roverspaces) identity_vars=(ROVERSPACE_NAME MACHINE_NAME) ;;
    *)           identity_vars=() ;;
esac
for var in "${identity_vars[@]}"; do
    if [ -n "$(env_value "$var")" ]; then
        ok "$var exported"
    else
        bad "$var" "not exported on $platform; fixture tracking and machine-name settings misbehave without it"
    fi
done

for tool in jq pnpm npx; do
    if command -v "$tool" >/dev/null 2>&1; then
        ok "$tool $(command -v "$tool")"
    else
        bad "$tool" "not on PATH; hooks and frontend lint depend on it"
    fi
done

# Live credential check only by hand: it's a network call, and in hook mode the
# token lives in the env file rather than this process's environment.
if [ "$mode" = report ]; then
    if timeout 10 gh auth status >/dev/null 2>&1; then
        ok "gh authenticated"
    else
        bad "gh auth" "gh auth status failed; GITHUB_TOKEN may be stale"
    fi
fi

###
# MARK: OUTPUT
###

status=OK
[ ${#failed[@]} -gt 0 ] && status=DEGRADED

# One line per session, so "when did this start failing?" has an answer. The
# check names are enough; the remediation hints only clutter the log.
names=""
[ ${#failed[@]} -gt 0 ] && names=$(printf ' [%s]' "$(printf '%s, ' "${failed[@]%% — *}" | sed 's/, $//')")

mkdir -p "$(dirname "$log")"
printf '%s entrypoint=%s platform=%s mode=%s repo=%s status=%s failed=%d%s\n' \
    "$(date -u +%FT%TZ)" "${CLAUDE_CODE_ENTRYPOINT:-shell}" "$platform" "$mode" "${repo:-none}" \
    "$status" "${#failed[@]}" "$names" \
    >> "$log" 2>/dev/null

if [ "$mode" = hook ]; then
    [ "$status" = OK ] && exit 0
    context="This session's tooling is DEGRADED — say so in your first reply, and don't report lint or formatting as having run when it hasn't:"
    for entry in "${failed[@]}"; do
        context+=$'\n'"  - $entry"
    done
    context+=$'\n'"Full report: ~/.claude/hooks/rover-doctor.sh"
    jq -n --arg context "$context" \
        '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $context}}'
    exit 0
fi

for entry in "${passed[@]}"; do printf '  \033[32mok\033[0m    %s\n' "$entry"; done
for entry in "${failed[@]}"; do printf '  \033[31mFAIL\033[0m  %s\n' "$entry"; done
printf '\n%s: %d ok, %d failed\n' "$status" "${#passed[@]}" "${#failed[@]}"
[ "$status" = OK ]