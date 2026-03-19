---
description: Create GitHub issues from an implementation plan for agent-driven development
argument-hint: "<feature or fix request>"
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - Agent
---

You are a planning agent. Your job is to analyze the request, produce an implementation plan,
and create one GitHub issue per plan step. Do NOT implement anything yourself.

## Request

$ARGUMENTS

## Instructions

### 1. Analyze

- Read CONSTITUTION.md, ROADMAP.md, and any files relevant to the request
- Break the request into discrete, independently implementable tasks
- Order tasks by dependency (upstream first)

### 2. Size each task

Assign a size label based on complexity:
- `size:small` — single file, < 50 lines changed, straightforward (good for Jules/Gemini)
- `size:medium` — 2-4 files, moderate logic, may need tests
- `size:large` — cross-cutting, architectural, or needs deep context (Claude-level)

### 3. Determine issue type

Use Conventional Commit types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`

### 4. Create a tracking issue

Create a parent issue that lists all child tasks as a checklist:

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh issue create \
  --title "epic: $SHORT_DESCRIPTION" \
  --label "epic,agent-task" \
  --body "$(cat <<'BODY'
## Overview
<brief description of the overall goal>

## Tasks
- [ ] #<child-1>
- [ ] #<child-2>
...
BODY
)"
```

### 5. Create child issues

For each task, create an issue:

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh issue create \
  --title "type(scope): description" \
  --label "agent-task,size:SIZE,TYPE_LABEL" \
  --body "$(cat <<'BODY'
## Context
<why this task exists, what it enables>

## Acceptance Criteria
- [ ] criterion 1
- [ ] criterion 2

## Files Likely Affected
- `path/to/file.py`

## Dependencies
Depends on: #N (if any)

## Notes for Implementer
<relevant CONSTITUTION.md rules, patterns to follow, edge cases>
BODY
)"
```

Map type to existing labels: `feat` → `enhancement`, `fix` → `bug`, `docs` → `documentation`.
For types without existing labels (`refactor`, `test`, `chore`, `perf`), use only `agent-task` + size.

### 6. Update tracking issue

After all child issues are created, edit the tracking issue body to include the actual issue numbers.

### 7. Output summary

Print a markdown table:

```
| # | Title | Size | Type | Depends On |
|---|-------|------|------|------------|
| 42 | feat(auth): add login endpoint | small | feat | — |
| 43 | test(auth): add login tests | small | test | #42 |
```

End with: "Created N issues. Tracking issue: #T"
