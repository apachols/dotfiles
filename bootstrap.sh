#!/bin/bash
set -euo pipefail

# Where this script actually lives: /workspaces/.codespaces/.persistedshare/dotfiles
# in GitHub Codespaces, $HOME/.config/coderv2/dotfiles in roverspaces (Coder),
# ~/git/dotfiles locally. Never hardcode one of them.
DOTFILES_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Symlink .bash_profile (-f so a re-run repoints a stale/dangling link)
ln -sfn "$DOTFILES_PATH/.bash_profile" "$HOME/.bash_profile"
echo "linked $HOME/.bash_profile -> $DOTFILES_PATH/.bash_profile"

# Have .bashrc source it. Append-only: never rewrite ~/.bashrc, because the
# cloud env image owns that file and other startup scripts edit it too.
# Leftover duplicate source lines from older bootstraps are harmless.
SOURCE_LINE='source $HOME/.bash_profile'
touch "$HOME/.bashrc"
if ! grep -qxF "$SOURCE_LINE" "$HOME/.bashrc"; then
    echo "$SOURCE_LINE" >> "$HOME/.bashrc"
    echo "added .bash_profile source line to $HOME/.bashrc"
fi

# Append gitconfig, exactly once
MARKER="# --- dotfiles gitconfig ---"
touch "$HOME/.gitconfig"
if ! grep -qxF "$MARKER" "$HOME/.gitconfig"; then
    { echo "$MARKER"; cat "$DOTFILES_PATH/.gitconfig"; } >> "$HOME/.gitconfig"
    echo "appended $DOTFILES_PATH/.gitconfig to $HOME/.gitconfig"
fi
