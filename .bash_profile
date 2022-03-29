# BRANCH_COLOR is used in bash_prompt - default is RED
export BRANCH_COLOR='31m'

# First, figure out where to load the dotfiles from
DOTFILES_PATH="$HOME/git/dotfiles/"
[ $USER = 'vscode' ] && DOTFILES_PATH="/workspaces/.codespaces/.persistedshare/dotfiles/"

# Next, load the dotfiles appropriate to environment
[ $USER = 'adampacholski' ] && source "$DOTFILES_PATH.roverrc"
[ $USER = 'dev' ] && source "$DOTFILES_PATH.roverec2rc"
[ $USER = 'adamp' ] && source "$DOTFILES_PATH.homerc"
[ $USER = 'vscode' ] && source "$DOTFILES_PATH.codespacesrc"

# Load the rest of the files, which are not env specific
for file in $DOTFILES_PATH.{path,bash_prompt,bashrc,exports,aliases,secrets}; do
  [ -r "$file" ] && source "$file"
done
unset file
