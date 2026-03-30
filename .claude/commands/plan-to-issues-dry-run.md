---
description: Preview GitHub issues from an implementation plan without creating them
argument-hint: "<feature or fix request>"
allowed-tools:
  - Read
  - Glob
  - Grep
  - Agent
---

You are a planning agent. Your job is to analyze the request and produce a preview of
GitHub issues that WOULD be created. Do NOT create any issues or run any gh commands.

## Request

$ARGUMENTS

## Instructions

### 1. Analyze

- Read CONSTITUTION.md, ROADMAP.md, and any files relevant to the request
- Break the request into discrete, independently implementable tasks
- Order tasks by dependency (upstream first)

### 2. Size each task

Assign a size label based on complexity:
- `size:small` — single file, < 50 lines changed, straightforward (good for fix-issue skill)
- `size:medium` — 2-4 files, moderate logic, may need tests
- `size:large` — cross-cutting, architectural, or needs deep context (Claude-level)

### 3. Output preview

For each issue, output the full issue as it would be created:

---

### Issue N: `type(scope): description`

**Labels:** `agent-task`, `size:SIZE`, `TYPE_LABEL`

#### Context
<why this task exists>

#### Acceptance Criteria
- [ ] criterion 1
- [ ] criterion 2

#### Files Likely Affected
- `path/to/file.py`

#### Dependencies
Depends on: Issue N (if any)

#### Notes for Implementer
<relevant rules, patterns, edge cases>

---

### 4. Summary table

End with a summary table:

```
| # | Title | Size | Type | Depends On |
|---|-------|------|------|------------|
| 1 | feat(auth): add login endpoint | small | feat | — |
| 2 | test(auth): add login tests | small | test | 1 |
```

And: "This is a dry run. Run `/plan-to-issues <same request>` to create these issues."
