---
description: Create stories in .meta/ from an implementation plan for agent-driven development
argument-hint: "<feature or fix request>"
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - Agent
  - Write
  - Edit
---

@.claude/project-config.md

You are a planning agent. Your job is to analyze the request, produce an implementation plan,
and create `.meta/` story and epic files for each plan step. Do NOT implement anything yourself.

## Request

$ARGUMENTS

## Instructions

### 1. Analyze

- Read CONSTITUTION.md, ROADMAP.md, .claude/rules/planning-playbook.md, and any files relevant to the request
- Break the request into discrete, independently implementable tasks
- Order tasks strictly by dependency and architectural layer (Architecture/Models -> Business Logic -> View/Middleware -> UI), following the Planning Playbook.

### 2. Size each task

Assign a size label based on complexity:
- `size:S` — single file, < 50 lines changed, straightforward (good for fix-issue skill)
- `size:M` — 2-4 files, moderate logic, may need tests
- `size:L` — cross-cutting, architectural, or needs deep context (Claude-level)

### 3. Determine issue type

Use Conventional Commit types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`

### 4. Create a tracking epic in .meta/

Create an epic directory and file:

```bash
EPIC_SLUG=$(echo "$SHORT_DESCRIPTION" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')
mkdir -p .meta/epics/$EPIC_SLUG/stories
```

Write `.meta/epics/$EPIC_SLUG/epic.md`:

```yaml
---
type: epic
id: <generate-nanoid>
title: "epic: $SHORT_DESCRIPTION"
status: backlog
priority: medium
owner: null
labels:
  - epic
  - agent-task
milestone_ref:
  id: <milestone-id-from-.meta/roadmap/milestones/>
github:
  issue_number: null
  repo: <owner/repo>
created_at: <ISO-8601>
updated_at: <ISO-8601>
---

## Overview
<brief description of the overall goal>

## Tasks
- [ ] story-slug-1
- [ ] story-slug-2
...
```

### 5. Create child stories in .meta/

For each task, create a story file at `.meta/epics/$EPIC_SLUG/stories/<story-slug>.md`:

```yaml
---
type: story
id: <generate-nanoid>
title: "type(scope): description"
status: backlog
priority: medium
assignee: null
labels:
  - agent-task
  - size:SIZE
  - TYPE_LABEL
estimate: null
epic_ref:
  id: <epic-id-from-step-4>
github:
  issue_number: null
  repo: <owner/repo>
created_at: <ISO-8601>
updated_at: <ISO-8601>
---

## Context
<why this task exists, what it enables>

## Scenarios

**Scenario: <behavior description>**
  Given <precondition>
  When  <action>
  Then  <outcome>

## Acceptance Criteria
- [ ] criterion 1
- [ ] criterion 2

## Files Likely Affected
- `path/to/file.py`

## Dependencies
Depends on: <story-slug> (if any)

## Notes for Implementer
<relevant CONSTITUTION.md rules, patterns to follow, edge cases>
```

Map type to labels: `feat` → `enhancement`, `fix` → `bug`, `docs` → `documentation`.
For types without existing labels (`refactor`, `test`, `chore`, `perf`), use only `agent-task` + size.

### 5.5 Generate IDs

Use a simple nanoid-style ID for each entity. Generate via:
```bash
cat /dev/urandom | LC_ALL=C tr -dc 'a-zA-Z0-9_' | head -c 12
```

### 6. Sync to GitHub

After all `.meta/` files are created, push to GitHub to create the corresponding issues:

```bash
# Validate the tree first
bun "$GITPM_CLI" validate --meta-dir .meta

# Push to create GitHub issues from .meta/ stories
bun "$GITPM_CLI" push --meta-dir .meta --token "$GITHUB_TOKEN"

# Pull back to get the assigned issue numbers
bun "$GITPM_CLI" pull --meta-dir .meta --token "$GITHUB_TOKEN"
```

After the pull, each story file will have its `github.issue_number` populated.

### 7. Output summary

Print a markdown table:

```
| Story | Title | Size | Type | Depends On |
|-------|-------|------|------|------------|
| story-slug | feat(auth): add login endpoint | S | feat | — |
| story-slug-2 | test(auth): add login tests | S | test | story-slug |
```

End with: "Created N stories in .meta/. Epic: $EPIC_SLUG. Synced to GitHub."
