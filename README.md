# dotfiles
Batteries-included shell + Claude Code setup for four environments: work laptop, home laptop, GitHub Codespaces, and roverspaces (Coder). One clone, one bootstrap, done.
## Install
```bash
git clone https://github.com/apachols/dotfiles
./bootstrap.sh
exec bash -l
```

`bootstrap.sh` figures out where it lives, symlinks `.bash_profile` into `$HOME`, makes `.bashrc` source it, and appends `.gitconfig`. Safe to re-run.

In Codespaces and roverspaces the platform clones this repo and runs `bootstrap.sh` for you.
## How it loads
`.bash_profile` detects the environment, sets `$DOTFILES_PATH` and `$WEB`, then sources one rc file plus the shared ones.

| Environment | Detected by | rc file |
| --- | --- | --- |
| Work laptop | `$USER = adam.pacholski` | `.roverrc` |
| Home laptop | `$USER = adamp` | `.homerc` |
| GitHub Codespaces | `$CODESPACES` | `.codespacesrc` |
| roverspaces (Coder) | `$ROVERSPACE_NAME` / `$CODER` | `.roverspacesrc` |

Then, for every environment: `.bash_prompt`, `.bashrc`, `.secrets`.
### Where a change belongs
| Kind of change | Goes in |
| --- | --- |
| Alias, function, `shopt` — same everywhere | `.bashrc` |
| `PATH` prefix | each rc file that needs it, **never** `.bashrc` |
| Env var for non-login Claude sessions | `.claude/hooks/codespace-env.sh` |
| Static env var, permission, hook registration | `CLAUDE_SETTINGS_ADDITIONS` in the rc file |
| Anything secret | `.secrets` (gitignored, sourced last) |

`PATH` lives per-environment because `.bash_profile` sources the rc file first and `.bashrc` after — a shared `PATH` line in `.bashrc` would land ahead of pyenv shims, Homebrew, or a codespace venv.
## What's in here
- `.claude/CLAUDE.md` — global instructions, symlinked to `~/.claude/CLAUDE.md`.
  
- `.claude/skills/` — personal skills, symlinked into `~/.claude/skills/`.
  
- `.claude/hooks/` — copied into `~/.claude/hooks/`:
  
  - `codespace-env.sh` (SessionStart) gives non-login Claude sessions the env a login shell would have set up.
    
  - `python-format.sh` (PostToolUse) runs ruff on every `.py` Claude writes.
    
  - `rover-doctor.sh` checks a session has the tooling the web repo needs.
    
- `personal.py` — local Django settings overrides, copied into the web repo.
  
- `alfred/` — Alfred workflow scripts.
  
## Secrets

This repo is public. Tokens, keys, and any URL containing one go in `.secrets`,
which is gitignored and sourced last by `.bash_profile` — so derive anything
that embeds a secret there too, not in `.bashrc` or an rc file. Tracked files
reference the variable, never the value. Check your diff before every commit.

## Updating a remote environment
```bash
dotfiles && personalize && web
```

`dotfiles` pulls (and refuses on a dirty tree — so never edit dotfiles from inside a codespace). `personalize` reinstalls the symlinks, hooks, and `~/.claude/settings.json` merge. Hook and rc changes only reach a **new** Claude session.
