---
description: "Implement a GitHub issue end-to-end (redirects to the implement-feature skill)"
argument-hint: "<issue-number>"
---

This command delegates to the `implement-feature` skill, which:
- Starts in an isolated worktree via `/start`
- Claims the issue (labels + project board)
- Self-evaluating planning loop (validates plan against all project rules before writing any code)
- Questionnaire gate (posts to the issue and stops if the plan has gaps)
- Blocker protocol (searches memory, saves WIP as draft PR, halts with issue comment)
- Memory updates after each blocker resolution and at completion

**Usage:** `/implement-feature $ARGUMENTS`
