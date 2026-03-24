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
| `agent:jules` | `#D4E5AE` | Assigned to Jules |
| `agent:ai` | `#F9D0C4` | assigned to {{ default_ai_model }} |
| `epic` | `#7057FF` | Parent issue with sub-issues |
| `community` | `#BFDADC` | From external contributor |
| `scheduled:auto` | `#FEF2C0` | Created by scheduled agent (high confidence) |
| `scheduled:review-needed` | `#F9D0C4` | Needs human review |

## Project Memory

Stored as `.github/project-memory.json` in the repository — version-controlled with full history:

```json
{
  "current_version": "0.1.0",
  "supported_versions": ["0.1.x"],
  "pending_deprecations": [],
  "roadmap": {
    "next_milestone": "v0.2.0",
    "planned_features": ["Plugin system", "Async support"],
    "tech_debt_items": 3
  },
  "agent_performance": {
    "jules_success_rate": 0.85,
    "avg_review_iterations": 1.3,
    "avg_task_completion_hours": 2.1
  },
  "community": {
    "contributors": 0,
    "open_issues": 12,
    "weekly_downloads": 0
  }
}
```

All agents read from and write to this file. It's version-controlled, so you have full history of project state evolution.

## GitHub Features Utilised

| Feature | Status | Usage |
|---|---|---|
| Projects V2 (REST + GraphQL API) | GA | Create board, add items, set custom fields |
| Sub-issues | GA (April 2025) | Epic → Task hierarchy |
| Issue dependencies | GA (August 2025) | `blocked_by` / `blocking` between tasks |
| Issue types (Bug, Feature, Task) | GA (April 2025) | Classify epics vs tasks |
| Milestones | Stable | Group tasks into releases |
| Labels | Stable | Size, agent tier, area, state |
| Custom fields on Projects | GA | Estimated hours, agent tier |
| Roadmap view | GA | Timeline with dependencies |
| Advanced search (`is:blocked`) | GA | Find bottleneck tasks |
