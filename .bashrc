PATH="/usr/local/bin:$PATH"

export BASH_SILENCE_DEPRECATION_WARNING=1

#
# ALIAS
#

alias grep="grep --color=auto"

alias ..="cd .."
alias ...="cd ../.."
alias ....="cd ../../.."

bind '"\e\e[C": forward-word'
bind '"\e\e[D": backward-word'

alias ll='ls -AlG'
alias v='code -r'

alias gitdiff='git diff --color'
alias gitchgs='git diff --color origin/master...HEAD'

alias yargs='xargs -n 1'

# OSX Specific
# alias branch="echo $(git branch 2>/dev/null | grep '^*' | colrm 1 2) | pbcopy"
# alias myip="ipconfig getifaddr en0 | xargs echo -n | pbcopy"

alias ngrok='/Applications/ngrok'

#
# FUNCTION TOWN
#

function remote()
{
  git remote -v | grep fetch | awk '{print $2}';
}

function wheres()
{
 find . -iname "*$1";
}

function gitfiles()
{
  target="master"
  if ! [[ -z $1 ]] ; then
    target="$1"
  fi
  git diff --name-only origin/$target...HEAD
}
