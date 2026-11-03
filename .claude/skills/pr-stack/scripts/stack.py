#!/usr/bin/env python3
"""Collect a PR stack's git topology as JSON for the pr-stack page.

Usage: stack.py <branch | PR number> [--repo PATH] [--out stack.json]

Every branch below the target comes from origin (fresh after a fetch), so the
page shows upstream commits the target does not have yet. The target itself is
read from the local ref when one exists, because that is what sits on disk.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from datetime import timezone


MERGE_RE = re.compile(r"Merge (?:remote-tracking )?branch '(?:origin/)?([^']+)'")
MASTER_PENDING_CAP = 300


def run(*args, repo, check=True):
    out = subprocess.run(args, cwd=repo, capture_output=True, text=True)
    if check and out.returncode != 0:
        sys.exit(f"{' '.join(args)} failed:\n{out.stderr}")
    return out.stdout.strip()


def git(repo, *args, check=True):
    return run("git", *args, repo=repo, check=check)


def lines(text):
    return [line for line in text.splitlines() if line]


def pr_for_branch(repo, branch):
    raw = run(
        "gh",
        "pr",
        "list",
        "--head",
        branch,
        "--state",
        "open",
        "--limit",
        "1",
        "--json",
        "number,title,baseRefName,author,url,body,isDraft",
        repo=repo,
        check=False,
    )
    prs = json.loads(raw or "[]")
    return prs[0] if prs else None


def prs_based_on(repo, branch):
    raw = run(
        "gh",
        "pr",
        "list",
        "--base",
        branch,
        "--state",
        "open",
        "--json",
        "headRefName",
        repo=repo,
        check=False,
    )
    return [pr["headRefName"] for pr in json.loads(raw or "[]")]


def resolve_target(repo, arg):
    if arg.isdigit():
        return run(
            "gh",
            "pr",
            "view",
            arg,
            "--json",
            "headRefName",
            "--jq",
            ".headRefName",
            repo=repo,
        )
    return arg


def discover(repo, target, default):
    """Candidate branches: PR base chains, PRs based on those, and branches merged into the target.

    Candidates the target turns out not to contain are dropped in main().
    """
    prs, queue, seen = {}, [target], set()
    while queue:
        branch = queue.pop(0)
        if branch in seen or branch == default:
            continue
        seen.add(branch)
        pr = pr_for_branch(repo, branch)
        if pr is None and branch != target:
            continue
        prs[branch] = pr
        if pr:
            queue.append(pr["baseRefName"])
        if branch != target:
            queue.extend(prs_based_on(repo, branch))
        if branch == target:
            ref = (
                branch
                if git(repo, "rev-parse", "--verify", "-q", branch, check=False)
                else f"origin/{branch}"
            )
            subjects = lines(
                git(repo, "log", "--merges", "--format=%s", f"origin/{default}..{ref}")
            )
            queue.extend(m.group(1) for s in subjects if (m := MERGE_RE.search(s)))
    return prs


def is_ancestor(repo, older, newer):
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", older, newer], cwd=repo
        ).returncode
        == 0
    )


def pick_ref(repo, branch, is_target):
    local = git(repo, "rev-parse", "--verify", "-q", f"refs/heads/{branch}", check=False)
    remote = git(
        repo, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{branch}", check=False
    )
    if is_target and local:
        return f"refs/heads/{branch}", "local"
    if local and remote and local != remote and is_ancestor(repo, remote, local):
        return f"refs/heads/{branch}", "local (unpushed commits)"
    if remote:
        return f"refs/remotes/origin/{branch}", "origin"
    return f"refs/heads/{branch}", "local"


def commit_info(repo, shas):
    if not shas:
        return {}
    fmt = "%H%x1f%h%x1f%P%x1f%cI%x1f%an%x1f%s%x1e"
    proc = subprocess.run(
        ["git", "log", "--no-walk=unsorted", f"--format={fmt}", "--stdin"],
        cwd=repo,
        input="\n".join(shas),
        capture_output=True,
        text=True,
        check=True,
    )
    info = {}
    for rec in proc.stdout.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, short, parents, date, author, subject = rec.split("\x1f")
        info[sha] = {
            "short": short,
            "subject": subject,
            "date": date,
            "author": author,
            "merge": len(parents.split()) > 1,
        }
    return info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--out", default="-")
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args()
    repo = args.repo

    default = run(
        "gh",
        "repo",
        "view",
        "--json",
        "defaultBranchRef",
        "--jq",
        ".defaultBranchRef.name",
        repo=repo,
    )
    target = resolve_target(repo, args.target)
    prs = discover(repo, target, default)
    branches = [default, *prs]

    if not args.no_fetch:
        git(repo, "fetch", "-q", "origin", *branches)

    refs, sources = {}, {}
    for b in branches:
        refs[b], sources[b] = pick_ref(repo, b, b == target)
    tips = {b: git(repo, "rev-parse", refs[b]) for b in branches}

    # First-parent "own" commits of each branch, oldest first. The default
    # branch has no own range; it is handled per target below.
    own = {}
    for b in branches[1:]:
        base = prs[b]["baseRefName"] if prs.get(b) else default
        base_ref = refs.get(base, f"refs/remotes/origin/{base}")
        own[b] = lines(
            git(repo, "rev-list", "--reverse", "--first-parent", refs[b], f"^{base_ref}")
        )

    all_shas = set()
    relations = {}
    for t in branches[1:]:
        rel = {}
        fork = git(repo, "merge-base", refs[t], refs[default])
        pending = lines(
            git(
                repo,
                "rev-list",
                "--reverse",
                "--first-parent",
                f"{fork}..{refs[default]}",
            )
        )
        rel[default] = {
            "included": [fork],
            "pending": pending[-MASTER_PENDING_CAP:],
            "pendingTotal": len(pending),
        }
        all_shas.update([fork, *rel[default]["pending"]])
        for b in branches[1:]:
            # A branch built on top of t is above it in the stack, not part of it.
            if b == t or is_ancestor(repo, tips[t], tips[b]):
                continue
            missing = set(lines(git(repo, "rev-list", refs[b], f"^{refs[t]}")))
            cherry = lines(git(repo, "cherry", refs[t], refs[b], check=False))
            equivalent = {line[2:] for line in cherry if line.startswith("- ")}
            flags = [(sha not in missing) or (sha in equivalent) for sha in own[b]]
            if not any(flags):
                continue
            cut = max(i for i, ok in enumerate(flags) if ok) + 1
            rel[b] = {
                "included": own[b][:cut],
                "pending": own[b][cut:],
                "pendingTotal": len(own[b]) - cut,
                "rebasedCopies": sum(1 for sha in own[b][:cut] if sha in missing),
            }
            all_shas.update(own[b])
        stack_refs = [f"^{refs[b]}" for b in rel if b != default]
        rel[t] = {
            "included": lines(
                git(
                    repo,
                    "rev-list",
                    "--reverse",
                    "--first-parent",
                    refs[t],
                    f"^{refs[default]}",
                    *stack_refs,
                )
            ),
            "pending": [],
            "pendingTotal": 0,
        }
        all_shas.update(rel[t]["included"])
        relations[t] = rel

    keep = set(relations[target])
    branches = [b for b in branches if b in keep]
    relations = {
        t: {b: r for b, r in rel.items() if b in keep}
        for t, rel in relations.items()
        if t in keep
    }
    all_shas = {
        sha
        for rel in relations.values()
        for r in rel.values()
        for sha in r["included"] + r["pending"]
    }

    # Column order: a branch sits right of every branch it contains.
    def depth(b):
        return 0 if b == default else len(relations[b]) - 1

    order = sorted(branches, key=lambda b: (depth(b), b))
    for t, rel in relations.items():
        members = [b for b in order if b in rel]
        for b in members:
            if b == t:
                continue
            later = [
                c for c in members[members.index(b) + 1 :] if c == t or b in relations[c]
            ]
            rel[b]["child"] = later[0] if later else t

    origin_tip = git(
        repo, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{target}", check=False
    )
    divergence = None
    if origin_tip and origin_tip != tips[target]:
        ahead, behind = git(
            repo, "rev-list", "--left-right", "--count", f"{tips[target]}...{origin_tip}"
        ).split()
        divergence = {
            "originTip": origin_tip[:11],
            "ahead": int(ahead),
            "behind": int(behind),
        }

    data = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo": run(
            "gh",
            "repo",
            "view",
            "--json",
            "nameWithOwner",
            "--jq",
            ".nameWithOwner",
            repo=repo,
        ),
        "repoPath": git(repo, "rev-parse", "--show-toplevel"),
        "checkedOut": git(repo, "branch", "--show-current"),
        "defaultBranch": default,
        "target": target,
        "targetDivergence": divergence,
        "order": order,
        "branches": {
            b: {
                "ref": refs[b],
                "source": sources[b],
                "tip": tips[b],
                "pr": None
                if not prs.get(b)
                else {
                    "number": prs[b]["number"],
                    "title": prs[b]["title"],
                    "url": prs[b]["url"],
                    "author": prs[b]["author"]["login"],
                    "authorName": prs[b]["author"].get("name") or "",
                    "base": prs[b]["baseRefName"],
                    "draft": prs[b]["isDraft"],
                    "bodyExcerpt": (prs[b]["body"] or "")[:1200],
                },
                "nickname": default if b == default else None,
                "summary": None,
            }
            for b in branches
        },
        "relations": relations,
        "commits": commit_info(repo, sorted(all_shas)),
    }
    text = json.dumps(data, indent=1)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w") as f:
            f.write(text + "\n")
        print(
            f"wrote {args.out}: {len(order)} branches, target {target}", file=sys.stderr
        )


if __name__ == "__main__":
    main()
