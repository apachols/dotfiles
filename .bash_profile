# BRANCH_COLOR is used in bash_prompt - default is RED
export BRANCH_COLOR='31m'

# First, figure out where to load the dotfiles from
PROJECTS_PATH="$HOME/git/"
[ $USER = 'vscode' ] && PROJECTS_PATH="/workspaces/.codespaces/.persistedshare/dotfiles/"

# Next, load the dotfiles appropriate to environment.  Each of these sources .bashrc
[ $USER = 'adampacholski' ] && source "$PROJECTS_PATH/dotfiles/.roverrc"
[ $USER = 'dev' ] && source "$PROJECTS_PATH/dotfiles/.roverec2rc"
[ $USER = 'adamp' ] && source "$PROJECTS_PATH/dotfiles/.homerc"
[ $USER = 'vscode' ] && source "$PROJECTS_PATH/dotfiles/.codespacesrc"

# Load the rest of the files, which are not env specific
for file in $PROJECTS_PATH/dotfiles/.{path,bash_prompt,bashrc,exports,aliases,secrets}; do
  [ -r "$file" ] && source "$file"
done
unset file
