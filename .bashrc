PATH="/usr/local/bin:$PATH"

export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"

export BASH_SILENCE_DEPRECATION_WARNING=1

export GREP_OPTIONS="--color=auto"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

#
# ALIAS
#

alias ..="cd .."
alias ...="cd ../.."
alias ....="cd ../../.."

bind '"\e\e[C": forward-word'
bind '"\e\e[D": backward-word'

alias ll='ls -AlG'
alias s='subl'
alias a='atom'
alias v='code -r'

alias gitdiff='git diff --color'
alias gitchgs='git diff --color origin/master...HEAD'
alias branch='echo $(__git_ps1) | pbcopy'

alias yargs='xargs -n 1'

alias myip="ipconfig getifaddr en0 | xargs echo -n | pbcopy"

alias ngrok='/Applications/ngrok'

alias rabble='cd ~/git/rabble'

# Added by serverless binary installer
export PATH="$HOME/.serverless/bin:$PATH"
alias slack='export SLACK_DEVELOPER_MENU=true && open -a /Applications/Slack.app'

#
# FUNCTION TOWN
#

function creds()
{
    grep -Eo ".{0,18}credentials.{0,18}" $1 | sort | uniq
}

function game()
{
    grep -Eo '"rabble.{0,12}' $1
}

function ogg()
{
  ffmpeg -i "$1" -c:a libvorbis -qscale:a 3 output.ogg
}

function mp3()
{
  ffmpeg -i $1 -b:a 256000 newfilename.mp3
}

function remote()
{
  git remote -v | grep fetch | awk '{print $2}';
}

function wheres()
{
 find . -iname "*$1";
}

function diffbranches()
{
  if [[ -z "$1" ]] ; then
    b1='origin/master'
  else
    b1="$1"
  fi
  if [[ -z "$2" ]] ; then
    b2='HEAD'
  else
    b2="$2"
  fi
  repo=$( git remote -v | awk -F':' '/fetch/{print $2;}' | awk '{print $1;}' | sed s/.git//g )
  hB1=$(git rev-parse --short $b1)
  hB2=$(git rev-parse --short $b2)
  link="https://gitweb.realsecure.flyingcroc.net/?p=$repo.git;a=commitdiff;hp="$hB1';h='$hB2
  echo $link
}

function gitfiles()
{
  target="master"
  if ! [[ -z $1 ]] ; then
    target="$1"
  fi
  git diff --name-only origin/$target...HEAD
}
