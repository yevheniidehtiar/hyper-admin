# HyperAdmin Project Configuration

Shared constants for all Claude Code commands and agents.
Reference this file in commands via `@.claude/project-config.md`.

## Project Management: GitPM (.meta/)

This project uses **gitpm** for git-native project management. All issue, epic, milestone,
and roadmap data lives in `.meta/` as plain-text YAML/Markdown files.

**Agents read and write `.meta/` files directly** — no `gh issue` or GitHub Projects API.
PRs are still managed via `gh pr` (gitpm does not handle PRs).

### GitPM CLI

```bash
GITPM_CLI="${GITPM_DIR:-/tmp/gitpm-install}/packages/cli/dist/index.js"

# Or use the wrapper script:
./scripts/gitpm.sh <command> [args...]
```

### .meta/ Directory Structure

```
.meta/
├── roadmap/
│   ├── roadmap.yaml           # Ordered list of milestone IDs
│   └── milestones/            # One YAML file per milestone
├── epics/
│   └── <epic-slug>/
│       ├── epic.md            # Epic frontmatter + body
│       └── stories/           # Stories nested under this epic
├── stories/                   # Standalone stories (not in an epic)
└── sync/
    ├── github-config.yaml     # Sync configuration
    └── github-state.json      # Sync state (gitignored)
```

### Entity Frontmatter Fields

**Story/Issue:**
```yaml
type: story
id: <nanoid>
title: "type(scope): description"
status: backlog | todo | in_progress | in_review | done | cancelled
priority: low | medium | high | critical
assignee: null | "<github-login>"
labels: [agent-task, size:S, area:core, ...]
epic_ref:
  id: <parent-epic-id>
github:
  issue_number: <N>
  repo: owner/repo
```

**Epic:**
```yaml
type: epic
id: <nanoid>
title: "epic(scope): description"
status: backlog | todo | in_progress | in_review | done | cancelled
priority: low | medium | high | critical
labels: [epic, agent-task, ...]
milestone_ref:
  id: <milestone-id>
github:
  issue_number: <N>
```

**Milestone:**
```yaml
type: milestone
id: <nanoid>
title: "v0.X.Y — Title"
target_date: "YYYY-MM-DD"
status: open | closed
github:
  milestone_number: <N>
```

### Common .meta/ Operations

```bash
# Find ready stories (status=todo + label agent-task + label ready)
grep -rl 'status: todo' .meta/stories/ .meta/epics/*/stories/ \
  | xargs grep -l 'agent-task' | xargs grep -l 'ready'

# Read a story by GitHub issue number
grep -rl 'issue_number: 375' .meta/stories/ .meta/epics/*/stories/

# Update story status (edit the YAML frontmatter directly)
# Then sync to GitHub:
bun "$GITPM_CLI" push --meta-dir .meta --token "$GITHUB_TOKEN"

# Pull latest from GitHub into .meta/
bun "$GITPM_CLI" pull --meta-dir .meta --token "$GITHUB_TOKEN"

# Validate .meta/ tree integrity
bun "$GITPM_CLI" validate --meta-dir .meta
```

### Sync Workflow

```
Agent reads .meta/ → edits story frontmatter → commits .meta/ changes
  → runs `gitpm push` to sync status/labels/assignee back to GitHub
```

After bulk edits (e.g., plan-to-issues), always run `gitpm push` once at the end.

---

## Epic Locking Protocol

**The epic is the unit of work ownership.** Before an agent can work on any story inside an
epic, it must first acquire a lock on the epic by merging a `.meta/` status-change PR into
`develop`. Git merge conflicts are the distributed lock — two agents cannot claim the same
epic because the second PR will conflict.

### Lock Acquisition Flow

```
1. Agent picks an epic with status: todo
2. Branch: meta/lock-<epic-slug>
3. Edit epic.md: status → in_progress, assignee → claude-code
4. Commit + push + open PR (squash-merge, auto-merge enabled)
5. WAIT for PR to merge into develop
6. After merge: gitpm push → sync status + labels to GitHub
7. NOW the agent may begin implementing the epic's stories
```

### Step-by-Step Commands

```bash
EPIC_SLUG="<epic-directory-name>"
EPIC_FILE=".meta/epics/$EPIC_SLUG/epic.md"
ISSUE_NUMBER=$(grep 'issue_number:' "$EPIC_FILE" | awk '{print $2}')
LOCK_BRANCH="meta/lock-$EPIC_SLUG"

# 1. Branch from latest develop
git fetch origin develop
git checkout -b "$LOCK_BRANCH" origin/develop

# 2. Update epic status (edit frontmatter)
#    status: todo → in_progress
#    assignee: null → "claude-code"
#    Add locked_at and locked_by fields:
#      locked_at: <ISO-8601 timestamp>
#      locked_by: <agent-session-id or "conductor">

# 3. Commit with Claude Code identity
git add "$EPIC_FILE"
git -c user.name="Claude Code" \
    -c user.email="noreply+claude-code@anthropic.com" \
    commit -m "lock(meta): claim epic #$ISSUE_NUMBER for implementation"

# 4. Push and open PR
git push origin "$LOCK_BRANCH"
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create \
  --title "lock(meta): claim epic #$ISSUE_NUMBER — $EPIC_SLUG" \
  --body "Acquiring epic lock. Auto-merge on green." \
  --base develop

# 5. Enable auto-merge (squash)
LOCK_PR=$(GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr view --json number -q .number)
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr merge "$LOCK_PR" --auto --squash

# 6. WAIT — poll until merged
while true; do
  STATE=$(GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr view "$LOCK_PR" --json state -q .state)
  [ "$STATE" = "MERGED" ] && break
  [ "$STATE" = "CLOSED" ] && { echo "LOCK FAILED: PR closed (conflict or rejected)"; exit 1; }
  sleep 10
done

# 7. After merge — sync to adapter platform (GitHub labels/status)
git checkout develop && git pull origin develop
bun "$GITPM_CLI" push --meta-dir .meta --token "$GITHUB_TOKEN"

# 8. Now proceed with story implementation
```

### Race Condition Resolution

When two agents attempt to lock the same epic simultaneously:

```
Agent A: creates PR changing epic status: todo → in_progress  ← merges first ✓
Agent B: creates PR changing epic status: todo → in_progress  ← MERGE CONFLICT ✗
```

Agent B's PR will have a merge conflict on the epic file. Agent B MUST:
1. Detect the conflict (PR cannot merge)
2. Close its lock PR
3. Delete the lock branch
4. Pick a different epic from the queue

### Lock Release (Epic Completion)

When all stories in an epic reach `status: done`:

```bash
# Update epic status
#   status: in_progress → done
#   Remove locked_at / locked_by fields

# Same PR workflow as lock acquisition:
RELEASE_BRANCH="meta/release-$EPIC_SLUG"
git checkout -b "$RELEASE_BRANCH" origin/develop
# Edit epic.md: status → done
git add "$EPIC_FILE"
git -c user.name="Claude Code" \
    -c user.email="noreply+claude-code@anthropic.com" \
    commit -m "release(meta): complete epic #$ISSUE_NUMBER"
git push origin "$RELEASE_BRANCH"
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create \
  --title "release(meta): complete epic #$ISSUE_NUMBER" \
  --body "All stories done. Releasing epic lock." \
  --base develop
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr merge --auto --squash
```

### Rules

- **Never start story work without a merged lock PR.** The lock PR on `develop` is proof of ownership.
- **One epic per agent at a time.** An agent must release (or complete) its current epic before locking another.
- **Lock PRs are tiny.** They touch only the epic's `epic.md` file — no code, fast review, fast merge.
- **Stale lock detection.** If an epic has `status: in_progress` for >48 hours with no story PRs opened,
  the project-manager agent may force-release the lock (set `status: todo`, remove `locked_by`).

## Runtime-Derived Variables

These must be derived at the start of any command that uses GitHub PRs:

```bash
# Derive owner and repo from current git remote — works in any fork
REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')
OWNER=$(echo "$REPO" | cut -d'/' -f1)
REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)
```

## Static Constants

```bash
PUBLIC_REPO="Damdy-OSS/hyper-admin"      # Official public OSS mirror — never push autonomously
DEFAULT_BASE_BRANCH="develop"             # Target branch for all autonomous merges
DEV_AGENT_LIMIT=3                         # Max dev agents per conductor cycle
CONDUCTOR_CYCLE_LIMIT=3                   # Max cycles per session (9 issues total cap)
MERGE_QUEUE_DEPTH=2                       # Max concurrent merge-granted PRs (prevents post-rebase conflicts)
```

## GitHub Auth

PRs and label writes still use the bot token:

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN"
```

Never use the user's ambient `GH_TOKEN` for PR creation.
If `CLAUDE_GH_TOKEN` is unset, stop and report to the user — do not fall back to user identity.

GitPM sync uses `$GITHUB_TOKEN` (read/write issues, milestones).

## Repository Topology

```
$REPO  (private dev, default branch: develop)
  └── .meta/ is the source of truth for issues, epics, milestones
  └── autonomous agents open PRs here (via gh pr)
  └── review-agent auto-approves here
  └── conductor grants merge permission here
  └── delivery-manager merges to develop here

Damdy-OSS/hyper-admin  (public OSS mirror)
  └── receives human-reviewed merges only
  └── NEVER written to by autonomous agents
```

## Status State Machine (Story lifecycle in .meta/)

```
backlog → todo → in_progress → in_review → done
                                         ↘ cancelled
```

| Status | Set by | Meaning |
|--------|--------|---------|
| `backlog` | plan-to-issues | Newly created, not yet prioritized |
| `todo` | project-manager / human | Ready for implementation |
| `in_progress` | conductor / dev agent | Dev agent claimed the story |
| `in_review` | dev agent | PR open, awaiting review |
| `done` | delivery-manager | PR merged, story complete |
| `cancelled` | human / triage | No longer needed |

## Label State Machine (PR lifecycle — still GitHub-native)

```
PR opened → review label → merge-requested → merge-granted → squash-merged
                                            ↘ merge-deferred
```

| Label | Set by | Meaning |
|-------|--------|---------|
| `review` | dev agent (on PR) | PR open, awaiting review |
| `merge-requested` | delivery-manager | PR approved + CI green, queued for conductor |
| `merge-granted` | conductor | Safe to merge, no conflict risk |
| `merge-deferred` | conductor | Merge blocked; reason in PR comment |
| `needs-human` | any agent | Escalation required |
