## Secrets — check before every commit

**This repo is public.** Before staging or committing anything here, re-read
your own diff and confirm it contains no tokens, API keys, passwords,
connection strings, or private URLs — including ones you only moved or
reformatted.

Secrets belong in `.secrets`, never in a tracked file. `.secrets` is gitignored
and sourced last by `.bash_profile`, so anything derived from a secret (a URL
with a token in it, for example) must also be derived in `.secrets` — a
derivation in `.bashrc` or an rc file runs before the tokens exist and silently
builds an empty value.

If a value must be referenced from a tracked file, reference the variable
(`$GEMFURY_API_TOKEN`), never the value. In Codespaces and roverspaces, real
values come from platform secrets and reach non-login Claude sessions via
`.claude/hooks/codespace-env.sh`.

If you find a secret already committed, stop and tell me — it needs rotating,
not just deleting.

## Rules for all Cloud Dev Envs (Codespaces && Roverspaces)

My dotfiles live at `/workspaces/.codespaces/.persistedshare/dotfiles` in a
codespace (`$DOTFILES_PATH`, aliased to `dotfiles`).

**In a Cloud Dev Env, never edit anything under `$DOTFILES_PATH` yourself.** All
dotfiles edits are made from my laptop and pushed. Show me the change as a
snippet or a diff in chat and let me apply it there. The reason: my update
command is `dotfiles && personalize && web`, where `dotfiles` does a `git pull`
and _refuses to run on a dirty tree_ — so an uncommitted edit made here
silently blocks my whole workflow.

`personalize` (defined in `.codespacesrc`) then installs everything: it
`cp -f`s each `.claude/hooks/*.sh` into `~/.claude/hooks/`, symlinks
`.claude/CLAUDE.md` and `.claude/skills/*`, and deep-merges
`CLAUDE_SETTINGS_ADDITIONS` into `~/.claude/settings.json`. Don't run
`personalize` yourself — it needs `$DOTFILES_PATH` and `$WEB`, which are unset
in your shells, and it will misfire.

Never edit the installed copies under `~/.claude/` to "fix" something. Hooks are
copies and `settings.json` is a merge, so edits there are invisible to version
control and get overwritten on my next `personalize`.

## Rules for Roverspaces

Nothing specific to Roverspaces yet, but keep this block, to distinguish between RS/CS.

## Rules for Codespaces

IF you are running in a codespace, and once, at the start of each session, run this command:

```
echo "CODESPACE_NAME=$CODESPACE_NAME GITHUB_TOKEN=${GITHUB_TOKEN:+set}" && gh auth status
```

If these variables are undefined, or gh auth status fails, STOP and notify the user.
If everything is defined and we are authed for `gh`, continue, no output necessary.

### Where a change belongs

Your Bash tool shells are non-interactive and non-login, so they do **not**
source `.bash_profile`, `.bashrc`, or `.codespacesrc`. Only shell functions,
aliases, `shopt` flags and `PATH` reach you, via Claude Code's per-session
snapshot in `~/.claude/shell-snapshots/`. Every other `export` is dropped.

One rc file per environment, all sourced from `.bash_profile`:

```
| Environment                                   | rc file           |
| --------------------------------------------- | ----------------  |
| Work laptop (`adam.pacholski`)                | `.roverrc`        |
| Home laptop (`adamp`)                         | `.homerc`         |
| Codespace, me sshed in (`vscode`/`codespace`) | `.codespacesrc`   |
| Roverspace, me sshed in (`vscode`/`codespace`)| `.roverspacesrc`  |
| Non-interactive Claude session (desktop app, sshd, IDE) | `.claude/hooks/codespace-env.sh` |
```

```
| Kind of change                                   | Goes in   |
| ------------------------------------------------ | --------  |
| Shell function, alias, `shopt` flag — same everywhere | `.bashrc` |
| `PATH` prefix                                    | each per-environment rc file that needs it — **not** `.bashrc` |
| Env var, especially a computed one               | `.claude/hooks/codespace-env.sh`, appended to `$CLAUDE_ENV_FILE` |
| Static env var, permission, or hook registration | `CLAUDE_SETTINGS_ADDITIONS` in `.codespacesrc` |
```

`PATH` prefixes are per-environment even when the directory exists everywhere,
because `.bash_profile` sources the env rc file **first** and `.bashrc`
**after**. Anything `.bashrc` prepends therefore lands ahead of what the rc file
set up: ahead of pyenv shims and `/opt/homebrew/bin` on the home laptop, and
ahead of `venv/bin` in a codespace (`.codespacesrc` runs `activate`). A shared
`PATH` line in `.bashrc` can silently shadow the right `python` or `pip` in an
environment I wasn't thinking about. Duplicate the line per rc file instead.

Changes to `codespace-env.sh`, `.bashrc`, or an rc file only take effect in a
**new** Claude session — the hook runs at `SessionStart` and the shell snapshot
is taken then. If I just ran `personalize`, say so rather than assuming the
current session already has the change.

## Rules for Rover Web

When you are working in the `web` repo, please strictly follow these conventions:

- DO NOT commit or push any code unless I ask for that explicitly (ask first)

The `web` repository is FULL of files with common / repeated / duplicate file names - forms.py, models.py, etc. Always print file names namespaced to the django app folder they are in: seo/models.py, api/current/serializers/models.py.

### Mypy Type Checking

When you need to run mypy type checking on python changes, some of the available info on how to run is outdated.

Please use this method, which is what CI uses to check PRs after they go up. If you run into trouble running type checking this way, let the user know.

```shell
python -m mypy --config-file config/mypy.ini --explicit-package-bases $FILENM1 $FILENM2
```

### Running Unit Tests

- DO NOT run any unit tests unless I ask for that explicitly (ask first)

When you offer to run unit tests, ALWAYS offer to run only changed tests files, and in those files PREFER to run only changed test suite classes. CI will catch any other tests that failed in other places in the same app. If you think there is a good reason to run an entire folder or entire app worth of tests, please let the user know, and explain your reasoning as concisely as possible.

### Rules for Shell Plus Blocks:

- Please use "python" syntax highlighting for shell plus blocks
- It's okay that shell plus scripts are only "mostly python", we just want Pretty Good syntax highlighting.
- Always assume the user will click "copy" and then paste the whole shell plus block into a shell plus session
- Never set up the shell plus blocks as "one-liners" using m shell_plus -c "'from stays.event_notifications ...'"
- You don't ever need to import models classes, all the models in the django app are automatically imported in our shell_plus sessions

### Running shell_plus Yourself (Agents)

The rules above are about blocks I copy-paste. When _you_ need to run shell_plus
non-interactively — DB verification during a test case, answering a question
about real data — follow these instead:

- **Never** use `m shell_plus -c "<multi-line python>"`. Passing multi-line
  Python through `bash -lc` does not parse reliably.
- **Never** create the script with the Write/Edit tools. The `python-format.sh`
  PostToolUse hook runs ruff on every `.py` file you write, and a reformat that
  splits a compact script across more lines breaks it when piped in: the
  interactive console treats each physical line as its own statement, so you get
  `IndentationError`/`SyntaxError`.
- Write the script with a bash heredoc into the scratchpad directory, then pipe
  it in:

```bash
cat > "/path/to/scratchpad/verify.py" <<'PY'
b = Booking.objects.get(pk=123)
print(b.status, b.start_date)
PY
m shell_plus --plain < "/path/to/scratchpad/verify.py"
```

- Because the console parses line by line, keep top-level statements flat and do
  not put blank lines inside an indented block — a blank line ends the block.
