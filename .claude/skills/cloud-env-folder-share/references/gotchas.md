# What we learned about Mutagen on cloud dev envs

Why each step in `scripts/cloud-env-folder-share.sh` exists. Read this when a sync breaks.

## Both environments

- **Run Mutagen on the laptop.** The laptop's Mutagen daemon dials the cloud env over ssh and
  installs a small agent binary there. Nothing runs on the cloud side except that agent.
- **Laptop and agent versions must match.** The agent lives at
  `~/.mutagen/agents/<version>/mutagen-agent` on the remote. After `brew upgrade mutagen`, the
  next `up` stages the new version.
- **Keep the sync root out of the repo.** Use a folder under the remote `$HOME`, such as
  `~/mutagen`, never somewhere inside `/workspaces/web`.
- **Use only one sync tool per folder.** An Obsidian SFTP plugin pointed at the same folder as
  Mutagen overwrote an agent's newer edit with an older copy. One writer path per folder.
- **Sessions survive reboots only if the daemon starts.** `mutagen daemon register` starts it
  at login. Without that, run `up` again after a reboot; it resumes the existing session.
- **Conflicts aren't silent.** The default mode, `two-way-safe`, refuses to overwrite a file
  both sides changed. `mutagen sync list` shows the conflict; delete the losing copy to clear it.

## Codespaces

- **Mutagen works out of the box.** Its self-install succeeds because codespace ssh sessions
  start in `$HOME`.
- **The ssh alias comes from `gh`.** `gh codespace ssh --config` prints `Host cs.<name>.<branch>`
  entries. The script writes them to `~/.ssh/codespaces` and puts `Include ~/.ssh/codespaces` at
  the top of `~/.ssh/config`; an `Include` placed after a `Host` block only applies inside it.
- **The alias contains the branch.** After the codespace switches branch, the session's old
  alias no longer exists. `stop` the session and run `up` again; the files on both sides stay.
- **Start the codespace first.** The original `remotesync` only ever picked an `Available`
  codespace; a stopped one is untested.

## Roverspaces (Coder)

- **ssh lands in `/workspaces/web`, not `$HOME`.** Everything below follows from that.
- **Mutagen dials its agent by a relative path,** `.mutagen/agents/<version>/mutagen-agent`,
  from the landing dir, so it misses an agent installed under `$HOME`. The script links
  `/workspaces/web/.mutagen` to `$HOME/.mutagen`.
- **Mutagen's self-install can't work there.** It unpacks into `/tmp` (tmpfs) and renames into
  `$HOME` (overlayfs), which fails with `invalid cross-device link`. So the script copies the agent
  from the laptop's `mutagen-agents.tar.gz` itself.
- **Every failed self-install leaves a `.mutagen-agent<uuid>` file** in the landing dir, which
  shows up as untracked in the web repo. The script deletes them and adds `.mutagen` and
  `.mutagen-agent*` to the repo's `.git/info/exclude` (local only, never committed).
- **A repo rebuild deletes the link.** A fresh clone, workspace rebuild or `git clean` removes
  `/workspaces/web/.mutagen`. A bare `mutagen sync resume` then loops on the cross-device error
  forever. That's why `up` stages the agent before resuming, not only before creating.
- **Host names need the Coder VPN.** With Coder Connect up, the devcontainer is reachable as
  `devcontainer.<workspace>.<coder-user>.coder`.
- **Roverspaces are in beta,** so these workarounds depend on where ssh lands and how the
  filesystem is mounted. If a sync breaks after a Roverspace update, check those two first.
