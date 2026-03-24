
# HyperAdmin — Jules Instructions

## Project Overview

A modern, Pydantic-native admin interface for FastAPI, powered by HTMX.

**Repo:** https://github.com/yevheniidehtiar/hyper-admin

## Jules Async Task Conventions

Jules operates asynchronously on GitHub issues/PRs. When assigning tasks to Jules:

1. Provide full context in the issue body — Jules has no conversation history
2. Reference specific files with line numbers when relevant
3. Specify acceptance criteria explicitly
4. Use labels: `jules`, `jules:fix`, `jules:feat`, `jules:refactor`

## Task Template

```
## Task
[What needs to be done]

## Context
[Why, what exists today, constraints]

## Acceptance Criteria
- [ ] Tests pass (`just test`)
- [ ] Lint clean (`just lint`)
- [ ] Docs updated if public API changed

## Files to Focus On
- `src/...`
```

## Task Sizing

| Size | Effort | Agent |
|------|--------|-------|
| S | < 30 min | Gemini CLI (inline fix) |
| M | 1-4 hours | Jules (async PR) |
| L | 4-8 hours | Jules + Claude Code (plan first) |

## Failure Handling

- Jules auto-retries up to 3 times on CI failure
- If still failing after 3 retries → label `needs-human`
- Same failure pattern = spec problem → escalate
- Different failure each time = agent capability issue → try Claude Code

## Architecture Notes

> TODO: Fill in after scaffold.

