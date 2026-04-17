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

alias sonnet="claude --model sonnet"

export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

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

function goto() {
    if [ -d "$1" ]; then
        cd "$1"
    elif [ -f "$1" ]; then
        cd "$(dirname "$1")"
    else
        echo "goto: '$1' is not a valid file or directory"
        return 1
    fi
}