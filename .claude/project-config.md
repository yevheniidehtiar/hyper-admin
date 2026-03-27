# HyperAdmin Project Configuration

Shared constants for all Claude Code commands and agents.
Reference this file in commands via `@.claude/project-config.md`.

## Runtime-Derived Variables

These must be derived at the start of any command that uses GitHub:

```bash
# Derive owner and repo from current git remote — works in any fork
REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')
OWNER=$(echo "$REPO" | cut -d'/' -f1)
REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)
```

## Static Constants

```bash
PUBLIC_REPO="Damdy-OSS/hyper-admin"      # Official public OSS mirror — never push autonomously
PROJECT_NAME_PREFIX="HyperAdmin:"         # Prefix for GitHub ProjectV2 names
DEFAULT_BASE_BRANCH="develop"             # Target branch for all autonomous merges
DEV_AGENT_LIMIT=3                         # Max dev agents per conductor cycle
CONDUCTOR_CYCLE_LIMIT=3                   # Max cycles per session (9 issues total cap)
MERGE_QUEUE_DEPTH=2                       # Max concurrent merge-granted PRs (prevents post-rebase conflicts)
```

## GitHub Auth

All GitHub writes by agents must use the bot token:

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN"
```

Never use the user's ambient `GH_TOKEN` for issue/PR creation.
If `CLAUDE_GH_TOKEN` is unset, stop and report to the user — do not fall back to user identity.

## Repository Topology

```
$REPO  (private dev, default branch: develop)
  └── autonomous agents open PRs here
  └── review-agent auto-approves here
  └── conductor grants merge permission here
  └── delivery-manager merges to develop here

Damdy-OSS/hyper-admin  (public OSS mirror)
  └── receives human-reviewed merges only
  └── NEVER written to by autonomous agents
```

## Label State Machine (Issue + PR lifecycle)

```
idea → researched → planned → approved → in-progress → review
     → merge-requested → merge-granted → released
                       ↘ merge-deferred  (conductor adds reason as PR comment)
```

| Label | Set by | Meaning |
|-------|--------|---------|
| `in-progress` | conductor / delivery-manager | Dev agent claimed the issue |
| `review` | dev agent (on PR) | PR open, awaiting review |
| `merge-requested` | delivery-manager | PR approved + CI green, queued for conductor |
| `merge-granted` | conductor | Safe to merge, no conflict risk |
| `merge-deferred` | conductor | Merge blocked; reason in PR comment |
| `needs-human` | any agent | Escalation required |
| `released` | delivery-manager | Merged and closed |
