# BRANCH_COLOR is used in bash_prompt - default is RED
export BRANCH_COLOR='31m'

# locally
export WEB="$HOME/projects/web"
DOTFILES_PATH="$HOME/git/dotfiles"
# codespaces - old
[ $USER = 'vscode' ] && DOTFILES_PATH="/workspaces/.codespaces/.persistedshare/dotfiles"
[ $USER = 'vscode' ] && WEB="/workspaces/web"
# codespaces - new
[ $USER = 'codespace' ] && DOTFILES_PATH="/workspaces/.codespaces/.persistedshare/dotfiles"
[ $USER = 'codespace' ] && WEB="/workspaces/web"

# Next, load the dotfiles appropriate to environment
[ $USER = 'adampacholski' ] && source "$DOTFILES_PATH/.roverrc"
[ $USER = 'dev' ] && source "$DOTFILES_PATH/.roverec2rc"
[ $USER = 'adamp' ] && source "$DOTFILES_PATH/.homerc"
[ $USER = 'vscode' ] && source "$DOTFILES_PATH/.codespacesrc"
[ $USER = 'codespace' ] && source "$DOTFILES_PATH/.codespacesrc"

# Load the rest of the files, which are not env specific
for file in $DOTFILES_PATH/.{path,bash_prompt,bashrc,exports,aliases,secrets}; do
  [ -r "$file" ] && source "$file"
done
unset file
