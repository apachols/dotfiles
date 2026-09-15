#!/usr/bin/env bash
# SessionStart hook: export the Codespace secrets to every Bash tool command.
# Claude Code prepends the contents of $CLAUDE_ENV_FILE to each Bash tool
# invocation, which replaces what /etc/profile.d/codespaces.sh does for
# login shells.
[ -n "$CLAUDE_ENV_FILE" ] || exit 0
secrets=/workspaces/.codespaces/shared/.env-secrets
[ -r "$secrets" ] || exit 0
while IFS= read -r line; do
  case "$line" in
    *=*) printf 'export %s=%q\n' "${line%%=*}" "$(printf %s "${line#*=}" | base64 -d 2>/dev/null)" ;;
  esac
done < "$secrets" >> "$CLAUDE_ENV_FILE"
