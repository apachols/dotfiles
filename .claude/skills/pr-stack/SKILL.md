---
name: pr-stack
description: 'Diagram a stacked-PR branch as an interactive claude.ai Artifact and rebase it from the page. Shows every PR the branch is built on as a bubble on a climbing lane, with upstream commits the branch does not have yet. The viewer drags each link up or down to choose what to pull in, then presses "Rebase", which sends the plan back to this session to carry out. Use when the user says /pr-stack <branch or PR number>, asks to see or update their PR stack, or wants to pull upstream changes from earlier PRs in a stack into one branch. Also handles the "pr-stack rebase request" comments that page sends.'
---

# pr-stack

`/pr-stack <branch | PR number>` builds one artifact page for that branch's
stack, and the same session then carries out the rebase the viewer asks for
from the page. A target is required. If the user gives none, ask for one,
suggesting the checked-out branch.

The page has one job: update a branch after PRs earlier in its stack moved.
Each PR is a bubble, collapsed by default, that holds the commits the target
already includes. Commits above a bubble are upstream commits the target
doesn't have yet. A link runs from each bubble (or from the commit it is
pinned to) into the next branch up. Dragging a link up pulls in more of that
branch. Dragging it down, after opening the bubble, drops commits. Any move
marks the column as edited. The "Rebase <nickname>" button sends the plan to
this session as an artifact comment.

## Build the page

1. **Collect the stack.** From the repo root:
   ```bash
   python3 <skill>/scripts/stack.py <branch-or-PR> --out <scratchpad>/pr-stack/<slug>/stack.json
   ```
   It fetches every branch in the stack and finds them three ways: PR base
   chains, open PRs based on a stack branch, and `Merge branch 'X'` commits in
   the target. Then it drops any that the target doesn't contain. Lower branches
   come from `origin/`, because the point is to see upstream changes. The target
   comes from its local ref, because that is what is on disk. For every possible
   target it records which of each branch's first-parent commits are included
   (by ancestry or `git cherry` patch-equivalence), which are pending, and which
   branch each one links into.
2. **Check the shape** before writing anything. Print the order and, for the
   target, `included/pending -> child` per branch:
   ```bash
   jq -c '.order, (.relations[.target]|map_values("\(.included|length)/\(.pendingTotal) -> \(.child)"))' stack.json
   ```
   If a PR the user expects is missing, or a branch links into the wrong child,
   find out why (a branch under another name, a squash, a PR on another base)
   before rendering. Tell the user if the local target and origin have diverged
   (`targetDivergence`).
3. **Name every PR.** For each non-default branch, fill in `nickname` (1 or 2
   words, the name someone on the project would use, e.g. "Validators",
   "API", "Frontend") and `summary` (50 words or fewer: what the PR adds and why,
   from its title, `bodyExcerpt` and commit subjects; `gh pr view` when the body
   is an empty template). Write them into `stack.json` with `jq`.
4. **Render.**
   ```bash
   python3 <skill>/scripts/render.py <scratchpad>/pr-stack/<slug>/stack.json
   ```
   It refuses to render with a missing nickname or an overlong summary.
5. **Publish** `index.html` with the Artifact tool: icon `branch`,
   `capabilities: {"comments": {}}`. The Rebase button needs that capability and
   a session watching the artifact, so check that the publish result confirms
   this session is subscribed. Republish to the same file path after every
   rebuild so the URL stays the same.

## Carry out a rebase request

The page posts a comment that starts with `pr-stack rebase request`. It names
the repo path, the target and its tip, what was checked out, and one line per
moved branch: `add N commits` or `drop N commits`, `from -> to`, then the
commits involved. Treat it as the user's instruction for this rebase only.

1. **Check it is still current.** Re-run `stack.py` for the target. If the
   target's tip or a `from` commit no longer matches, stop. Rebuild the page,
   republish, and reply in the thread that the stack moved and needs
   re-choosing.
2. **Pick where to work.**
   - If the target is the branch checked out in the repo, work there. Make sure
     the tree is clean first (`git status --porcelain`), and stop and ask if it
     isn't. Then save a backup ref: `git branch <target>-backup-<YYYYMMDD-HHMM>`.
   - Otherwise, never touch the checkout. Create a worktree on a new branch:
     ```bash
     git worktree add ../<repo>-<short-slug>-rebase-<YYYYMMDD> -b <target>-rebase-<YYYYMMDD> <target tip>
     ```
     Add `-HHMM` to the branch name if one with that date already exists.
3. **Apply the plan the way the branch is already built.**
   - **Merge-built** (the target's first-parent history has merges of stack
     branches, like `Merge remote-tracking branch 'origin/X'`): for each branch
     that adds commits, from the bottom of the stack up, `git merge --no-ff <to>`
     with the message `Merge <branch> @ <short> into <target>`.
   - **Linear** (no such merges), or any plan with a `drop`: rebuild. Start at
     the lowest branch's chosen commit. For each branch above it, cherry-pick
     that branch's own commits up to its chosen commit, skipping any already
     applied (`git cherry` shows them). Then cherry-pick the target's own
     commits (`relations[target][target].included` in `stack.json`).
     Equivalently, `git rebase --onto <new base> <old base> <branch>` when only
     the top branch moved.
   - Don't push, and don't move any branch except the target or the new
     `-rebase-` branch.
4. **Stop on conflicts.** Resolve one only when it is mechanical and the right
   answer is unambiguous (both sides added unrelated imports, a lockfile).
   Otherwise abort (`git merge --abort` / `git cherry-pick --abort`), leave the
   worktree or backup branch where it is, and report the conflicted files and
   the commit that hit them.
5. **Verify.** `git log --oneline --first-parent -15` on the result. Confirm
   each `to` commit is now an ancestor (`git merge-base --is-ancestor`) and each
   dropped commit is not. Don't run tests unless the user asks. Offer to run the
   changed test classes.
6. **Report and refresh.** Reply in the comment thread (ArtifactComments) and in
   the session. Say which branch and worktree hold the result, the commits that
   were added or dropped, the backup ref, and the push command for when they
   want it. Then re-run `stack.py` on the result and republish the same page.
   If a new `-rebase-` branch was made, pass `--repo <worktree>` and that
   branch, and keep the nicknames and summaries already written.

## Limits

- Commits are first-parent only. A branch's "own" commits are the ones on its
  first-parent chain that aren't on its PR base. A branch whose PR base is
  stale (pointing at an older branch than it was actually built on) still
  works, because the script removes every other stack branch's commits from
  the target's own commits.
- The default branch shows only its fork point plus up to 300 newer commits.
  Pulling master into a stack is allowed but is rarely what the user wants, so
  confirm it in the reply before doing it.
- The page reads a snapshot. It shows when the data was taken, and anything
  pushed afterwards is not on it until the page is rebuilt.
