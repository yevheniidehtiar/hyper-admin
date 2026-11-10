---
description: "Start work in a new isolated worktree branched from develop (or a given base branch)"
argument-hint: "<branch-name> [base-branch]"
---

Start a new isolated worktree session for feature work. This ensures parallel agents
don't collide and keeps the main working tree clean.

## Arguments

`$ARGUMENTS`

- First token: the branch name (`BRANCH`). If it is missing, generate a random name
  (e.g., `work/agent-<4-random-hex-chars>`).
- Optional second token: the base branch (`BASE`). Default: `develop`. Story work for an epic
  passes `epic/<slug>`.

## Steps

1. **Fetch the base**

```bash
git fetch origin "$BASE"
```

2. **Enter worktree**

Use `EnterWorktree` with the branch name.

3. **Reset to the base tip, or resume the branch**

If the branch already exists on `origin` (an earlier run pushed work, possibly behind a draft PR),
resume from it. Resetting it to the base would drop that work:

```bash
git fetch origin "$BRANCH" && git reset --hard "origin/$BRANCH" && git rebase "origin/$BASE"
```

Otherwise this is a fresh worktree with no prior work: reset to the tip of the base
instead of rebasing (avoids replaying the entire history and hitting conflicts):

```bash
git reset --hard "origin/$BASE"
```

4. **Bootstrap the environment**

```bash
uv sync --all-extras
```

5. **Confirm ready**

Print a status summary:
- Worktree path
- Branch name
- Base branch and base commit (short SHA + subject)
- Environment status (uv sync result)

Then say: **Ready. What are we working on?**
