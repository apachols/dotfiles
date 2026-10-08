#!/usr/bin/env bash
# Share a laptop folder with a Codespace or Roverspace over ssh.
# Runs on the laptop. Bash 3.2 compatible (macOS /bin/bash).
#
#   cloud-env-folder-share.sh codespace-host <codespace-name>
#   cloud-env-folder-share.sh check <ssh-host>
#   cloud-env-folder-share.sh up --kind codespace|roverspace --host H --local DIR --remote DIR --name NAME
#   cloud-env-folder-share.sh status [NAME]
#   cloud-env-folder-share.sh stop NAME
#
# --remote is relative to the remote $HOME unless it starts with /.
# references/gotchas.md explains why each workaround below exists.

set -u

die() { echo "cloud-env-folder-share: $*" >&2; exit 1; }
say() { echo "cloud-env-folder-share: $*"; }

# Print the ssh alias `gh codespace ssh --config` generates for a codespace.
# The alias includes the branch, so it is regenerated on every call.
codespace_host() {
  local name="$1" cfg="$HOME/.ssh/codespaces" main="$HOME/.ssh/config"
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  gh codespace ssh --config > "$cfg" || die "gh codespace ssh --config failed (is the codespace running?)"

  # An Include only applies at the top level of ssh_config, so put it first.
  if ! grep -qE "^Include +(~/.ssh/codespaces|$cfg)\$" "$main" 2>/dev/null; then
    local tmp
    tmp=$(mktemp) || exit 1
    { echo "Include ~/.ssh/codespaces"; echo; cat "$main" 2>/dev/null; } > "$tmp" &&
      mv "$tmp" "$main" && chmod 600 "$main"
    say "added 'Include ~/.ssh/codespaces' to the top of $main" >&2
  fi

  local host
  host=$(grep -m1 "^Host cs\.$name" "$cfg" | awk '{print $2}')
  [ -n "$host" ] || die "no ssh config entry for $name in $cfg"
  echo "$host"
}

check_host() {
  local host="$1"
  ssh -o BatchMode=yes -o ConnectTimeout=15 "$host" true ||
    die "can't ssh to $host non-interactively (VPN up? key loaded? host name right?)"
  say "ssh to $host works; lands in $(ssh "$host" pwd), \$HOME is $(ssh "$host" 'echo $HOME')"
}

remote_abs() {
  local host="$1" dir="${2#\~/}" home
  case "$dir" in /*) echo "$dir"; return ;; esac
  home=$(ssh "$host" 'echo $HOME') || return 1
  [ -n "$home" ] || return 1
  echo "$home/$dir"
}

agent_bundle() {
  local bin c
  bin=$(command -v mutagen) || return 1
  # brew keeps the bundle in libexec; release tarballs put it next to the binary
  for c in "$(brew --prefix mutagen 2>/dev/null)/libexec/mutagen-agents.tar.gz" \
    "$(dirname "$(readlink -f "$bin" 2>/dev/null || echo "$bin")")/mutagen-agents.tar.gz" \
    "$(dirname "$bin")/mutagen-agents.tar.gz"; do
    [ -f "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}

# Roverspaces start ssh sessions in /workspaces/web, not $HOME. Mutagen looks for
# its agent relative to the landing dir and its self-install fails there, so
# stage the agent and link it into the landing dir. Re-run before every resume:
# a repo rebuild deletes the link.
stage_roverspace_agent() {
  local host="$1" version remote_home landing arch agent bundle tmpdir
  version=$(mutagen version) || return 1
  remote_home=$(ssh "$host" 'echo $HOME') || return 1
  landing=$(ssh "$host" pwd) || return 1

  # leftovers from failed self-installs land in the landing dir
  ssh "$host" 'rm -f ./.mutagen-agent*'

  agent="$remote_home/.mutagen/agents/$version/mutagen-agent"
  if ssh "$host" "[ -x '$agent' ]"; then
    say "agent $version already staged on $host"
  else
    case "$(ssh "$host" uname -m)" in
      x86_64|amd64) arch=linux_amd64 ;;
      aarch64|arm64) arch=linux_arm64 ;;
      *) say "unsupported remote architecture"; return 1 ;;
    esac
    bundle=$(agent_bundle) || { say "can't find mutagen-agents.tar.gz next to the mutagen binary"; return 1; }
    tmpdir=$(mktemp -d) || return 1
    tar xzf "$bundle" -C "$tmpdir" "$arch" || { rm -rf "$tmpdir"; return 1; }
    ssh "$host" "mkdir -p '$remote_home/.mutagen/agents/$version'" &&
      scp -q "$tmpdir/$arch" "$host:$agent" &&
      ssh "$host" "chmod +x '$agent'" ||
      { rm -rf "$tmpdir"; return 1; }
    rm -rf "$tmpdir"
    say "staged agent $version ($arch) on $host"
  fi

  if [ "$landing" != "$remote_home" ]; then
    ssh "$host" "ln -sfn '$remote_home/.mutagen' '$landing/.mutagen'" || return 1
    # keep the link and leftovers out of git status when the landing dir is a repo
    ssh "$host" "gd=\$(git -C '$landing' rev-parse --git-common-dir 2>/dev/null) || exit 0
      case \"\$gd\" in /*) ;; *) gd='$landing'/\"\$gd\" ;; esac
      mkdir -p \"\$gd/info\"
      for p in .mutagen '.mutagen-agent*'; do
        grep -qxF \"\$p\" \"\$gd/info/exclude\" 2>/dev/null || echo \"\$p\" >> \"\$gd/info/exclude\"
      done"
  fi
}

session_exists() { mutagen sync list "$1" >/dev/null 2>&1; }

up() {
  local kind="" host="" local_dir="" remote="" name=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --kind) kind="$2"; shift 2 ;;
      --host) host="$2"; shift 2 ;;
      --local) local_dir="$2"; shift 2 ;;
      --remote) remote="$2"; shift 2 ;;
      --name) name="$2"; shift 2 ;;
      *) die "up: unknown argument $1" ;;
    esac
  done
  [ -n "$kind" ] && [ -n "$host" ] && [ -n "$local_dir" ] && [ -n "$remote" ] && [ -n "$name" ] ||
    die "up needs --kind --host --local --remote --name"

  mutagen daemon start >/dev/null 2>&1
  mkdir -p "$local_dir"

  if [ "$kind" = roverspace ]; then
    stage_roverspace_agent "$host" || die "agent staging failed on $host"
  fi

  if session_exists "$name"; then
    say "resuming session $name"
    mutagen sync resume "$name"
    return
  fi

  local remote_dir
  remote_dir=$(remote_abs "$host" "$remote") || die "could not read \$HOME on $host"
  ssh "$host" "mkdir -p '$remote_dir'" || die "could not create $remote_dir on $host"

  say "creating session $name ($local_dir <-> $host:$remote_dir)"
  mutagen sync create "$local_dir" "$host:$remote_dir" --name="$name" \
    --ignore-vcs --ignore=.DS_Store
}

cmd="${1:-}"
[ $# -gt 0 ] && shift
case "$cmd" in
  codespace-host) [ $# -eq 1 ] || die "usage: codespace-host <codespace-name>"; codespace_host "$1" ;;
  check) [ $# -eq 1 ] || die "usage: check <ssh-host>"; check_host "$1" ;;
  up) up "$@" ;;
  status) mutagen sync list "$@" ;;
  stop) [ $# -eq 1 ] || die "usage: stop <name>"; mutagen sync terminate "$1" ;;
  *) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
