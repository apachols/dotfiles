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

export LOG_CLEANER='grep -vi synth | grep -vi health | grep -vi tasks | grep -vi task | grep -vi geo_ip_location'

alias flogs="dc logs --tail 345 web -f | $LOG_CLEANER"
alias slogs="dc logs --tail 345 web | $LOG_CLEANER"
alias blogs="dc logs --tail 34567 web | $LOG_CLEANER"
alias clogs="dc logs --tail 34567 web | grep -i task"

alias hello="echo 'hi'"

export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
export CLAUDE_CODE_DISABLE_ARTIFACT=0
export EXPERIMENTAL_TSGO=true


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

function rgp() {
  rg "$1" ./src/aplaceforrover --type py -g "!*test*"
}

function _sync_claude_skills()
{
  local source_dir="$1"
  local target_dir="$2"
  mkdir -p "$target_dir"
  for skill in "$source_dir"/*/; do
    skill="${skill%/}"
    name=$(basename "$skill")
    target="$target_dir/$name"
    if [ -e "$target" ]; then
      continue
    fi
    ln -s "$skill" "$target"
    echo "linked skill: $name"
  done
}
