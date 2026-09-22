#!/bin/bash
set -euo pipefail

# Where this script actually lives: /workspaces/.codespaces/.persistedshare/dotfiles
# in GitHub Codespaces, $HOME/.config/coderv2/dotfiles in roverspaces (Coder),
# ~/git/dotfiles locally. Never hardcode one of them.
DOTFILES_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Symlink .bash_profile (-f so a re-run repoints a stale/dangling link)
ln -sfn "$DOTFILES_PATH/.bash_profile" "$HOME/.bash_profile"
echo "linked $HOME/.bash_profile -> $DOTFILES_PATH/.bash_profile"

# Have .bashrc source it, exactly once. Older versions of this script appended a
# hardcoded "source /home/$USER/.bash_profile" on every run, so strip any
# existing .bash_profile source line before adding the canonical one back.
SOURCE_LINE="source \$HOME/.bash_profile"
touch "$HOME/.bashrc"
sed -i.bak -E '/^[[:space:]]*(source|\.)[[:space:]]+.*\.bash_profile[[:space:]]*$/d' "$HOME/.bashrc"
rm -f "$HOME/.bashrc.bak"
echo "$SOURCE_LINE" >> "$HOME/.bashrc"
echo "set .bash_profile source line in $HOME/.bashrc"

# Append gitconfig, exactly once
MARKER="# --- dotfiles gitconfig ---"
touch "$HOME/.gitconfig"
if ! grep -qxF "$MARKER" "$HOME/.gitconfig"; then
    { echo "$MARKER"; cat "$DOTFILES_PATH/.gitconfig"; } >> "$HOME/.gitconfig"
    echo "appended $DOTFILES_PATH/.gitconfig to $HOME/.gitconfig"
fi
