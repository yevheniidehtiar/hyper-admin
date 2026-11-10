# Agent 2: Roadmap Planning Agent

| Property | Value |
|---|---|
| **Tier** | High-Reasoning (Claude Opus) |
| **Trigger** | Deep Research agent delivers specification with score > 85% |
| **Purpose** | Decompose specification into GitHub milestones, epics, tasks with dependencies |
| **Est. Cost** | 30k - 80k tokens per initial plan |

## Core Principles for Planning

### Mandatory TDD (Test-Driven Development)
Every functional issue or feature MUST be decomposed into at least two distinct sub-tasks:
1.  **Test Case Implementation**: Write failing tests (unit and/or E2E) that cover the happy path, edge cases, and potential regressions.
2.  **Functional Implementation**: Write the minimal code necessary to make the previously written tests pass.

### Assembly First Principle
When planning MVPs or new UI-related features, follow the "Assembly First" principle:
-   **Phase 1 (Core Functional)**: Implement pure, unstyled components, actions, and data streams. Focus on data flow, logic, and core utility.
-   **Phase 2 (Styling & UX)**: Apply visual design, shadows, and layout refinements only after Phase 1 is functionally verified.

## Three-Level Hierarchy

Maps directly to GitHub's data model:

```
Milestone (v0.1.0, v0.2.0) → GitHub Milestone
  └── Epic (Feature issue with sub-issues) → GitHub Issue (type: Feature)
        └── Task (implementable in 1-4h) → GitHub Sub-Issue
```

## Input Contract

```json
{
  "project_id": "github-owner/repo",
  "understanding_score": 0.87,
  "architecture_snapshot": {
    "languages": ["python"],
    "modules": [
      { "path": "src/core/", "purpose": "Domain logic", "loc": 1200 },
      { "path": "src/api/", "purpose": "Public API surface", "loc": 400 }
    ],
    "test_coverage": 0.42,
    "existing_issues": 12
  },
  "idea": {
    "raw": "User's original description",
    "refined": "Clarified description after Q&A loop",
    "scope": "mvp",
    "constraints": [
      "Must maintain backward compat with v0.x API",
      "Solo dev, evening/weekend time budget ~10h/week"
    ]
  }
}
```

## Planning Algorithm

### Architecture Analysis

Pragmatic scan that identifies:

- **Public API surface** — functions/classes exported to users (must stay backward-compatible)
- **Internal boundaries** — module imports that create coupling
- **Test gaps** — modules with zero or low test coverage
- **Tech debt hotspots** — files with high churn, large functions, TODO/FIXME/HACK comments

### Work Breakdown

Each task includes:

- **Title** — imperative verb + noun (`Add retry logic to HTTP client`)
- **Description** — what to implement and the acceptance criteria
- **`## Files to Change`** — every file the story will touch. The autopilot uses this list to decide which stories can run in parallel, so it must be complete. Stories that share a file are given an explicit dependency or a hotspot owner.
- **Labels** — `area:core`, `size:S/M/L`, `agent:ai`
- **Estimated effort** — S=1-2h, M=2-4h, L=4-8h
- **Agent tier** — which dev agent should handle this
- **Dependencies** — `blocked_by` / `blocking` links

### Dependency DAG

Uses GitHub's native features:

- **Sub-issues** (GA April 2025): Epic → Task parent-child hierarchy
- **Issue dependencies** (GA August 2025): `blocked_by` / `blocking` between tasks

Rules:

- Core library changes block API surface changes
- API changes block documentation updates
- Implementation tasks block their corresponding test tasks
- Breaking changes grouped in same milestone with migration guide tasks
- Circular dependencies detected and resolved before materialising

### Agent Assignment Logic

| Task characteristic | Skill | Rationale |
|---|---|---|
| New file/module implementation | implement-feature | Full self-eval loop with TDD |
| Refactoring existing code | implement-feature | Good at reading context, systematic changes |
| Bug fix with clear reproduction | fix-issue | Lightweight TDD loop, fast turnaround |
| Complex architecture decision | SDD + `review(spec)` story, then implement-feature | The software-architect agent approves the SDD; the owner is asked only for breaking API, new runtime deps, or migrations |
| Test writing | fix-issue | Mechanical, straightforward scope |
| Documentation | implement-feature | Prose + code examples |
| API design review | Claude Opus (manual) | Backward compat implications |

### Delivery Timeline

```
Milestone v0.1.0 (MVP core)
  Tasks: 12 (8 via implement-feature, 3 via fix-issue, 1 Opus review)
  Claude capacity needed: ~30 messages per cycle
  Human review time: one epic PR per epic
  Calendar estimate: 1 week
```

### Epics as the unit of delivery

Each epic is delivered on its own branch, `epic/<slug>`, and reaches `develop`
as a single pull request that the owner approves once (see
[Orchestration](orchestration.md)). Plan with that in mind:

- Keep an epic small enough to review as one PR.
- Stories inside an epic should be independent where possible, so up to three
  can run at the same time.
- An epic that needs an SDD gets a `review(spec)` story. The architect agent
  completes it before implementation stories are dispatched.
- Label a story `deferred` to keep the autopilot from picking it up.

## Materialisation via GitPM (.meta/)

Plans are materialised as `.meta/` files — epics, stories, and milestones — then synced to GitHub by CI.

### Setup Sequence

```bash
# Create labels (one-time, run by the owner)
bash scripts/setup-github.sh

# Create milestones in .meta/
# Write .meta/roadmap/milestones/<slug>.md with milestone frontmatter

# Create epics + stories in .meta/
# Write .meta/epics/<slug>/epic.md and .meta/epics/<slug>/stories/<slug>.md

# Open a planning PR against develop (chore(meta): ...)
```

There is no local sync step. The planning PR shows a GitPM dry-run preview, and
when it merges to `develop` the GitPM Sync workflow
(`.github/workflows/gitpm-sync.yml`) creates the issues and milestones. Never
run a GitPM push from a workstation.

### .meta/ as the Project Board

The `.meta/` directory replaces GitHub Projects V2:

- **Status tracking**: `status` field in story frontmatter (backlog/todo/in_progress/in_review/done)
- **Priority**: `priority` field (low/medium/high/critical)
- **Size**: `size:S/M/L` in labels array
- **Roadmap**: `.meta/roadmap/roadmap.yaml` lists milestones in order
- **Epic hierarchy**: `.meta/epics/<slug>/stories/` nests stories under epics

See `.claude/commands/plan-to-issues.md` for the full creation workflow.

## Output Contract

```json
{
  "plan_id": "plan-2025-03-22-abc123",
  "project_id": "PVT_xxxxxxxxxxxx",
  "project_url": "https://github.com/users/owner/projects/1",
  "milestones": [
    {
      "title": "v0.1.0 — MVP Core",
      "due_date": "2025-04-07",
      "total_effort_hours": 32,
      "agent_assisted_hours": 12,
      "epics": [
        {
          "issue_number": 15,
          "title": "feat: HTTP client with retry logic",
          "tasks": [
            {
              "issue_number": 16,
              "title": "Implement base HTTP client class",
              "size": "M",
              "agent_tier": "ai",
              "blocked_by": [],
              "blocking": [17, 18]
            }
          ]
        }
      ]
    }
  ],
  "critical_path": [16, 17, 20, 23, 25],
  "critical_path_duration_days": 12
}
```

## Human Checkpoints

| Checkpoint | What happens | Human action |
|---|---|---|
| Plan review | Agent opens a planning PR with the `.meta/` epics and stories | Approve, modify, adjust scope |
| Epic PR | Autopilot marks `epic/<slug>` → `develop` ready when all stories are done | Approve once; it merges on approval |
| Milestone gate | The digest reports when the last epic of a milestone has merged | Cut the release or re-plan |
| Escalation | A story hits a hard stop or uses up its retry budget (`needs-human`) | Answer the question on the issue |

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Over-planning (50+ issues) | Max 20 tasks per milestone |
| Dependency chain too deep | Flag chains > 5, suggest parallel tracks |
| Stale plan | Re-run architecture scan at each milestone gate |
| GitHub API rate limits | Batch operations, respect retry-after |
