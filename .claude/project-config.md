# HyperAdmin Project Configuration

Shared constants for all Claude Code commands and agents.
Reference this file in commands via `@.claude/project-config.md`.

## Project Management: GitPM (.meta/)

This project uses **gitpm** for git-native project management. All issue, epic, milestone,
and roadmap data lives in `.meta/` as plain-text YAML/Markdown files.

**Agents read `.meta/` files directly** — no GitHub Projects API. Writes are limited: planning
PRs add new files, and the autopilot writes status in the open-epic and close-epic commits.
PRs are managed via `gh pr` (gitpm does not handle PRs). Mid-epic progress labels and comments
on story issues are written by the autopilot via `gh issue`.

### GitPM CLI

```bash
# Pinned npm release (@gitpm/cli + @gitpm/sync-github), same versions as CI:
./scripts/gitpm.sh <command> [args...]
```

`push` and `sync` are refused locally: the GitPM Sync workflow (`.github/workflows/gitpm-sync.yml`)
owns them.

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

# Story status is written by the autopilot only (see Status State Machine below).
# Syncing .meta/ to GitHub is done by the GitPM Sync workflow after a merge to develop.

# Validate .meta/ tree integrity
./scripts/gitpm.sh validate
```

### Sync Workflow

```
open-epic / close-epic commit on epic/<slug> → `./scripts/gitpm.sh validate`
  → epic PR (CI validates + previews the sync)
  → owner approves, rebase-merge to develop → GitPM Sync workflow pushes status/labels to GitHub
```

Planning PRs that only add new `.meta` files (new epics, stories) go to `develop` directly and
sync the same way.

Do not run `gitpm push` yourself, even after bulk edits: CI keeps the sync state on the
`gitpm-state` branch, and a local push can create duplicate issues. The first live sync, and any
re-run, is started from Actions > GitPM Sync > Run workflow (untick `dry_run`).

---

## Epic Branch Protocol

**The epic is the unit of work ownership, and its branch is the lock.** An epic in flight has
exactly one branch `epic/<slug>`, where `<slug>` names the epic directory under `.meta/epics/`
(`ops/autopilot/README.md` has the exact mapping). Whoever creates the branch owns the epic.

```
develop  ──────────────────────────────●──▶   owner approves 1 PR per epic
           \                          /
epic/<slug> ●──st-01──st-02──st-03───┘        autopilot rebase-merges story PRs, no human
             ▲         ▲
        feat/st-01  feat/st-02 ...            worker worktrees, one per story
```

### Lock = branch creation through the API

```bash
SLUG="<slug>"
SHA=$(gh api "repos/$REPO/git/ref/heads/develop" --jq .object.sha)

# Returns 422 "Reference already exists" when another run already owns the epic.
GH_TOKEN="$CLAUDE_GH_TOKEN" gh api -X POST "repos/$REPO/git/refs" \
  -f ref="refs/heads/epic/$SLUG" -f sha="$SHA"
```

A plain `git push` of an existing ref exits 0, so it is not a lock. Only the API call is. On 422,
pick a different epic.

### Open the epic

1. First commit on `epic/<slug>`, touching only the epic's `epic.md`:
   `status: in_progress`, `locked_by: autopilot`, `branch: epic/<slug>`.
   Message: `chore(meta): open epic <slug>`.
2. Open the epic PR `epic/<slug>` → `develop` as a **draft** straight away. Every story merge
   pushes the epic branch, so CI runs on the integrated state and the owner can watch the diff grow.

### Story PRs

- Branch from `origin/epic/<slug>`, target `epic/<slug>`, and carry a `Story: <story-id>` line in
  the PR body.
- The tick merges a story PR with `gh pr merge --rebase --delete-branch` when all checks are green,
  the PR has `ai-approved` and no `needs-human`, and it is rebased on the epic tip. `--auto` is not
  usable on `epic/**` (no pending rules there).
- Story PRs do not edit `status:` in `.meta` (see `.claude/rules/conflict-avoidance.md`).

### Close and integrate the epic (`integrate-epic` job)

Gate: zero open PRs with base `epic/<slug>`, the `review(spec)` story is approved, all AI review
threads are resolved.

1. Rebase `epic/<slug>` on `origin/develop`, force-push with lease. GitHub's rebase-merge needs a
   clean replay, so the branch must be exactly rebased.
2. Commit `chore(meta): close epic <slug>`: epic `status: done`, lock fields (`locked_by`, `branch`)
   removed, every story and the `review(spec)` story `status: done`.
3. Mark the PR ready, request the owner's review, enable `gh pr merge --auto --rebase`.
4. **Freeze the branch.** Any further push dismisses the owner's approval.

After the owner approves, the story commits land linearly on `develop` and the GitPM Sync workflow
updates all issues in one run.

### Rebasing the epic branch

Only at creation, when `develop` changes a hotspot file the epic also touches, and right before the
PR is marked ready. Only when no story PR is open against it, or the same job rebases every open
story branch too. Always `--force-with-lease`.

### Rules

- **Never start story work without the epic branch.** Its existence, plus the open-epic commit, is
  the proof of ownership.
- **`.meta` status changes for an epic live in the two commits above** and nowhere else.
- **A stale epic** (branch exists, no story PR for more than 48 hours, no running job) is reported
  in the digest. Nobody deletes the branch without the owner's go.

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
DEFAULT_BASE_BRANCH="develop"             # Base for epic branches and for hotfix / standalone PRs
EPIC_BRANCH_PATTERN="epic/<slug>"         # Base for story PRs of an epic
DEV_AGENT_LIMIT=3                         # Max parallel implement jobs (1 when free memory < 4 GB)
```

Autopilot runtime (see `ops/autopilot/README.md`):

| Name | Value |
|------|-------|
| Entry point | `ops/autopilot/autopilot.sh tick` (launchd label `com.hyperadmin.autopilot`, every 15 min) |
| Job prompts | `ops/autopilot/prompts/{implement,review,fix-pr,fix-develop,approve-sdd,integrate-epic,digest}.md` |
| State | `~/.hyperadmin-autopilot/state.json` (cooldown, running jobs, retry counters) |
| Worktree pool | `.claude/worktrees/ap-1..3` |
| `AUTOPILOT=1` | Set for every headless job; skills use it to tell an unattended run from an interactive one |
| `AUTOPILOT_DRY_RUN=1` | The tick prints its planned actions and takes none |

## GitHub Auth

PRs, label writes and epic-branch creation use the bot token:

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
  └── epic/<slug> branches: one per epic in flight, created and merged into by the autopilot
  └── story PRs target epic/<slug>; the autopilot rebase-merges them, no human
  └── one epic PR (epic/<slug> → develop) per epic; the owner approves it
  └── hotfix, Dependabot and fix-develop PRs target develop; the owner approves them

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
| `todo` | planning PR / human | Ready for implementation |
| `done` | autopilot (close-epic commit) | Story PR merged into the epic branch |
| `cancelled` | human / triage | No longer needed |

The autopilot is the only writer of `status:` once an epic is open, and it writes it in exactly two
commits on the epic branch:

| Commit | Content |
|--------|---------|
| `chore(meta): open epic` | `epic.md`: `status: in_progress`, `locked_by: autopilot`, `branch: epic/<slug>` |
| `chore(meta): close epic` | `epic.md`: `status: done`, lock fields removed; every story and the `review(spec)` story: `status: done` |

There are no per-story status commits, so `in_progress` and `in_review` are not written to story
files while an epic is in flight. Mid-epic progress is shown by the `ap:*` labels on the story
issue (below). The GitPM Sync workflow overwrites the status-mapped labels when the epic PR merges
to `develop`, which is the correct final state.

## Label State Machine (GitHub-native, written by the autopilot)

Story issue:

```
ap:in-progress → ap:in-review → ap:done
```

Story PR (base `epic/<slug>`):

```
PR opened → review job → ai-approved            → all checks green → rebase-merged by the tick
                       ↘ ai-changes-requested   → fix-pr job → review job again
```

| Label | On | Set by | Meaning |
|-------|----|--------|---------|
| `ap:in-progress` | story issue | autopilot tick | An `implement` job is running for the story |
| `ap:in-review` | story issue | autopilot tick | Story PR is open (one comment links it) |
| `ap:done` | story issue | autopilot tick | Story PR merged into the epic branch |
| `ai-approved` | PR | `review` job | Reviewer verdict: approved (the bot cannot approve its own PR) |
| `ai-changes-requested` | PR | `review` job | Reviewer verdict: changes required; details in the review comment |
| `needs-human` | PR or issue | any job | Hard stop or exhausted retry budget; the exact question is in a comment |
| `superseded` | story issue | planning PR | Story replaced by other work; not picked up |

A story PR is merged when all of its checks are green, it carries `ai-approved`, it does not carry
`needs-human`, and it is rebased on the epic branch tip.

Retry budgets (kept in `~/.hyperadmin-autopilot/state.json`): one CI rerun for a cancelled or
timed-out check, 3 `fix-pr` rounds per PR, 2 `review` rounds per PR, then `needs-human`.
