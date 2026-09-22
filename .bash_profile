  # BRANCH_COLOR is used in bash_prompt - default is RED
  export BRANCH_COLOR='31m'

  # locally
  export WEB="$HOME/projects/web"
  export DOTFILES_PATH="$HOME/git/dotfiles"

  # roverspaces (Coder) - $USER is also 'codespace' here, so check this FIRST
  if [ -n "${ROVERSPACE_NAME:-}" ] || [ -n "${CODER:-}" ]; then
    ROVERSPACE=1
    export DOTFILES_PATH="$HOME/.config/coderv2/dotfiles"
    export WEB="/workspaces/web"
  # github codespaces
  elif [ -n "${CODESPACES:-}" ]; then
    export DOTFILES_PATH="/workspaces/.codespaces/.persistedshare/dotfiles"
    export WEB="/workspaces/web"
  fi

  # Next, load the dotfiles appropriate to environment
  [ -n "${ROVERSPACE:-}" ] && source "$DOTFILES_PATH/.roverspacesrc"
  [ -z "${ROVERSPACE:-}" ] && [ -n "${CODESPACES:-}" ] && source "$DOTFILES_PATH/.codespacesrc"
  [ "$USER" = 'adam.pacholski' ] && source "$DOTFILES_PATH/.roverrc"
  [ "$USER" = 'adamp' ] && source "$DOTFILES_PATH/.homerc"

  # Load the rest of the files, which are not env specific
  for file in $DOTFILES_PATH/.{path,bash_prompt,bashrc,exports,aliases,secrets}; do
    [ -r "$file" ] && source "$file"
  done
  unset file