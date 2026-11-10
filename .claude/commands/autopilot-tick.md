---
description: Run one autopilot tick by hand and explain what it did (interactive debugging)
argument-hint: "[--live]"
allowed-tools: Read, Grep, Glob, Bash(ops/autopilot/autopilot.sh *), Bash(AUTOPILOT_DRY_RUN=1 ops/autopilot/autopilot.sh *), Bash(gh *), Bash(git *), Bash(uv run poe autopilot:*), Bash(launchctl print *)
---

@.claude/project-config.md

Run a single autopilot tick from this session to debug the unattended pipeline. The scheduled
ticks come from launchd (`com.hyperadmin.autopilot`, every 15 min); this command is for looking at
one tick closely. It is not a second scheduler: run it once, report, stop.

Arguments: `$ARGUMENTS`

- No argument: **dry run**. The tick prints the actions it would take and takes none.
- `--live`: a real tick. Only when the user passed it explicitly.

## Steps

### 1. Preconditions

Run from the main checkout, not from a pool worktree (`.claude/worktrees/ap-1..3`): job prompts
are read from `ops/autopilot/prompts/` of the main checkout.

```bash
git rev-parse --show-toplevel
test -x ops/autopilot/autopilot.sh && echo "autopilot present"
test -n "$CLAUDE_GH_TOKEN" && echo "CLAUDE_GH_TOKEN: SET"
cat ~/.hyperadmin-autopilot/state.json 2>/dev/null
launchctl print "gui/$UID/com.hyperadmin.autopilot" 2>/dev/null | head -20
```

Report: whether the launchd job is loaded, whether a cooldown is active (`cooldown_until`), which
jobs `state.json` lists as running, and the retry counters per PR. If a scheduled tick is running
right now (the tick takes a single-instance lock), say so and stop: do not remove the lock.

### 2. Run the tick

Dry run (default):

```bash
AUTOPILOT_DRY_RUN=1 ops/autopilot/autopilot.sh tick
```

Live (`--live` only):

```bash
ops/autopilot/autopilot.sh tick
```

`uv run poe autopilot:tick` is the same call; `uv run poe autopilot:status` and
`uv run poe autopilot:logs` show the launchd side.

### 3. Explain the result

For each planned or taken action, give one line: the check that triggered it, the job
(`implement`, `review`, `fix-pr`, `fix-develop`, `approve-sdd`, `integrate-epic`, `digest`), its
argument, and the pool worktree it got. Then answer the questions a tick should always be able to
answer:

| Question | Where to look |
|----------|---------------|
| Is `develop` green? | the tick's develop check; `gh run list --branch develop --event push --limit 5` |
| Which epics are open? | `git ls-remote --heads origin 'epic/*'` and their draft PRs |
| Which story PRs are mergeable now? | all checks green, `ai-approved`, no `needs-human`, rebased on the epic tip |
| Why was a ready story not dispatched? | `DEV_AGENT_LIMIT`, unmet dependency, `deferred` label, `## Files to Change` overlap with a running story |
| Is anything waiting on the owner? | open `needs-human` items; ready epic PRs |

### 4. If something looks wrong

Report it; do not repair state by hand. In particular do not edit
`~/.hyperadmin-autopilot/state.json`, do not delete `epic/*` branches or pool worktrees, do not
merge PRs, and do not change labels. If the tick itself has a bug, the fix is a normal PR against
`ops/autopilot/`.
