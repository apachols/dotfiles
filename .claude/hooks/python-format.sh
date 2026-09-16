#!/usr/bin/env bash
# PostToolUse hook: format Python files with the project's own ruff.
#
# web's own .claude/hooks/post-edit-format.sh calls bare `ruff` and swallows both
# output streams, so in a session that never ran a login shell - Claude desktop,
# sshd into the Codespace, an IDE extension - every Python edit goes unformatted
# and nothing says so. Hook scripts are spawned by the harness rather than
# through the Bash tool, so $CLAUDE_ENV_FILE can't reach them; resolve ruff by
# path instead.
set -uo pipefail

input=$(cat -)
file_path=$(printf %s "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

case "$file_path" in
    *.py) ;;
    *) exit 0 ;;
esac
[ -f "$file_path" ] || exit 0

# .pre-commit-config.yaml excludes migrations; leave them alone here too.
case "$file_path" in
    */migrations/*) exit 0 ;;
esac

report() {
    jq -n --arg context "$1" \
        '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $context}}'
}

root=$(git -C "$(dirname "$file_path")" rev-parse --show-toplevel 2>/dev/null)
ruff=$(command -v ruff 2>/dev/null)
[ -n "$ruff" ] || ruff="$root/venv/bin/ruff"

if [ ! -x "$ruff" ]; then
    # Quiet in projects that don't use ruff, loud in the ones that do.
    if [ -n "$root" ] && grep -qs ruff "$root/.pre-commit-config.yaml"; then
        report "ruff is missing from this session (not on PATH, not at $root/venv/bin/ruff), so $file_path was NOT formatted. Say so in your reply instead of claiming the file is formatted, and run ~/.claude/hooks/rover-doctor.sh for the cause."
    fi
    exit 0
fi

errors=$(mktemp)
trap 'rm -f "$errors"' EXIT
diff_output=$("$ruff" format --diff "$file_path" 2>"$errors")

case $? in
    0)  # already formatted
        ;;
    1)  "$ruff" format "$file_path" >/dev/null 2>&1
        report "ruff formatted $file_path:"$'\n'"$diff_output"
        ;;
    *)  report "ruff could not format $file_path: $(head -c 400 "$errors")"
        ;;
esac
