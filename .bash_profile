# Load the shell dotfiles, and then some:
# * ~/.path can be used to extend `$PATH`.
# * ~/.extra can be used for other settings you don’t want to commit.
for file in $HOME/git/dotfiles/.{path,bash_prompt,bashrc,gitprompt,exports,aliases,functions,extra}; do
  [ -r "$file" ] && source "$file"
done
unset file

[ $USER = 'adampacholski' ] && source "$HOME/git/dotfiles/.roverrc"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
export PATH=/$HOME/.local/bin:$PATH

export PATH="$HOME/.yarn/bin:$HOME/.config/yarn/global/node_modules/.bin:$PATH"
