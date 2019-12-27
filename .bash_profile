# Load the shell dotfiles, and then some:
# * ~/.path can be used to extend `$PATH`.
for file in $HOME/git/dotfiles/.{path,bash_prompt,bashrc,exports,aliases}; do
  [ -r "$file" ] && source "$file"
done
unset file

[ $USER = 'adampacholski' ] && source "$HOME/git/dotfiles/.roverrc"
[ $USER = 'dev' ] && source "$HOME/git/dotfiles/.rovervmrc"
