# BRANCH_COLOR is used in bash_prompt - default is RED
export BRANCH_COLOR='31m'
[ $USER = 'adampacholski' ] && source "$HOME/git/dotfiles/.roverrc"
[ $USER = 'dev' ] && source "$HOME/git/dotfiles/.rovervmrc"

for file in $HOME/git/dotfiles/.{path,bash_prompt,bashrc,exports,aliases}; do
  [ -r "$file" ] && source "$file"
done
unset file

