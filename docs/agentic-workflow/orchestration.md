# Cross-Agent Orchestration

## Event Flow (GitHub-Native)

The entire orchestration runs through GitHub's native event system — no custom event bus needed:

```
Human creates issue with label "idea"
  → GitHub Action triggers Deep Research (High-Reasoning Model)
  → Deep Research completes → adds label "researched"
  → GitHub Action triggers Roadmap Planning (High-Reasoning Model)
  → Planning creates Project board + sub-issues → adds label "planned"
  → Human reviews, approves → adds label "approved"
  → GitHub Action assigns issues to Dev Agents (Production/Utility)
  → Dev agent creates PR → triggers Code Review Action
  → Review approved → triggers QA matrix
  → QA passes → adds label "qa-passed"
  → All milestone items "qa-passed" → triggers Release Agent
  → Human approves release → publish pipeline runs
```

## Label-Based State Machine

```
idea → researched → planned → approved → in-progress → review → qa-passed → released
                                  ↑                        │
                                  └── rejected (with ctx) ──┘
```

### Required Labels

| Label | Color | Purpose |
|---|---|---|
| `idea` | `#D4C5F9` | Raw idea, needs research |
| `researched` | `#C2E0C6` | Deep Research complete, score > 85% |
| `planned` | `#BFD4F2` | Roadmap Planning complete, issues created |
| `approved` | `#0E8A16` | Human approved, ready for implementation |
| `in-progress` | `#FBCA04` | Dev agent working on it |
| `review` | `#E99695` | PR submitted, awaiting review |
| `qa-passed` | `#0E8A16` | All tests green, compat matrix clean |
| `released` | `#5319E7` | Shipped in a release |
| `needs-human` | `#D93F0B` | Agent escalation, human intervention needed |
| `size:S` | `#C5DEF5` | 1-2 hours effort |
| `size:M` | `#BFD4F2` | 2-4 hours effort |
| `size:L` | `#A2C4EA` | 4-8 hours effort |
| `agent:ai` | `#F9D0C4` | Assigned to Claude Code |
| `epic` | `#7057FF` | Parent issue with sub-issues |
| `community` | `#BFDADC` | From external contributor |
| `scheduled:auto` | `#FEF2C0` | Created by scheduled agent (high confidence) |
| `scheduled:review-needed` | `#F9D0C4` | Needs human review |
| `suspicious` | `#D93F0B` | Flagged by [OSS Triage Auditor](oss-triage-auditor.md) — needs human review |

## Project Management: GitPM (.meta/)

Project state is stored as plain-text YAML/Markdown files in `.meta/` — git-native, version-controlled:

```
.meta/
├── roadmap/
│   ├── roadmap.yaml           # Ordered list of milestone IDs
│   └── milestones/            # One YAML file per milestone
├── epics/
│   └── <epic-slug>/
│       ├── epic.md            # Epic frontmatter + body
│       └── stories/           # Stories nested under this epic
├── stories/                   # Standalone stories
└── sync/                      # GitHub sync config + state
```

All agents read from and write to `.meta/` files directly. Changes are synced to GitHub
via `gitpm push`. See `.claude/project-config.md` for full reference.

## GitHub Features Utilised

| Feature | Status | Usage |
|---|---|---|
| GitPM (.meta/) | **Primary** | All issue/epic/milestone management — agents read/write directly |
| Sub-issues | GA (April 2025) | Epic → Story hierarchy (mirrored in `.meta/epics/*/stories/`) |
| Issue dependencies | GA (August 2025) | `blocked_by` / `blocking` between stories |
| Milestones | Stable | Group stories into releases (stored in `.meta/roadmap/milestones/`) |
| Labels | Stable | Size, agent tier, area — synced via `gitpm push` |
| PRs | Stable | Still managed via `gh pr` (gitpm does not handle PRs) |
| `gitpm push/pull/sync` | **Implemented** | Bidirectional sync between `.meta/` and GitHub Issues |

## Autonomous Team Orchestration

The autonomous team runs as a label-driven state machine. No agent-to-agent direct calls —
each agent filters on specific label combinations and acts.

### Conductor (`/run-autonomous-team`)

The conductor is the entry point and merge authority. It runs in the foreground and:

1. Fetches issues with `agent-task` + `ready` labels
2. Dispatches up to 3 dev agents per cycle (each in an isolated worktree)
3. Coordinates review via `hyper-admin-code-reviewer` agent
4. Evaluates `merge-requested` PRs → grants or defers based on file overlap and dependency order

### Label-Based Agent Workload Filters

| Agent | Watches | Action |
|-------|---------|--------|
| **Conductor** | Issues: `agent-task` + `ready` | Claim → dispatch dev agent in worktree |
| **Conductor** | PRs: `merge-requested` | Evaluate queue → add `merge-granted` or `merge-deferred` |
| **review-agent** | PRs: `review` | Auto-approve via `gh pr review --approve` |
| **delivery-manager** | PRs: `review` + CI green + GH approval | Add `merge-requested`, remove `review` |
| **delivery-manager** | PRs: `merge-granted` | Execute merge → add `released`, close issue |
| **project-manager** | Daily/weekly cron | Progress snapshot via `.meta/`, priority triage, team assignment, staleness cleanup |
| **project-manager** | Issues: `community` | Delegate to `oss-triage-auditor` for triage |

### Merge Queue Evaluation (Conductor)

Before granting a merge, the conductor checks:
- **File overlap**: `gh pr diff --name-only` compared across all open PRs
- **Dependency order**: `Depends on: #X` in issue body → `#X` must be closed (merged)
- **Queue depth**: max 2 concurrent merges to avoid post-rebase conflicts

### Limits and Safety Rails

| Rail | Value |
|------|-------|
| Dev agents per cycle | 3 |
| Cycles per session | 3 (9 issues max) |
| Review iterations per PR | 2 (then `needs-human`) |
| Merge queue depth | 2 simultaneous |
| Rollback | `git revert <merge-sha>` if `develop` breaks |

### Project Config

All commands and agents reference `@.claude/project-config.md` for shared constants.
Owner/repo are derived at runtime via `gh repo view` — no hardcoded values in command files.
