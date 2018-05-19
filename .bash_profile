# Load the shell dotfiles, and then some:
# * ~/.path can be used to extend `$PATH`.
# * ~/.extra can be used for other settings you don’t want to commit.
for file in $HOME/git/dotfiles/.{path,bash_prompt,bashrc,gitprompt,exports,aliases,functions,extra}; do
  [ -r "$file" ] && source "$file"
done
unset file