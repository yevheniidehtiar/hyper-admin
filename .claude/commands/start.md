---
description: "Start work in a new isolated worktree branched from develop"
argument-hint: "<branch-name>"
---

Start a new isolated worktree session for feature work. This ensures parallel agents
don't collide and keeps the main working tree clean.

## Steps

1. **Pull latest develop**

```bash
git fetch origin develop
```

2. **Enter worktree**

Use `EnterWorktree` with the branch name provided by the user: `$ARGUMENTS`

If `$ARGUMENTS` is empty, generate a random name (e.g., `work/agent-<4-random-hex-chars>`).

3. **Reset to latest develop**

Since this is a fresh worktree with no prior work, reset to the tip of develop
instead of rebasing (avoids replaying the entire history and hitting conflicts):

```bash
git reset --hard origin/develop
```

4. **Bootstrap the environment**

```bash
uv sync --all-extras
```

5. **Confirm ready**

Print a status summary:
- Worktree path
- Branch name
- Base commit (short SHA + subject from develop)
- Environment status (uv sync result)

Then say: **Ready. What are we working on?**
