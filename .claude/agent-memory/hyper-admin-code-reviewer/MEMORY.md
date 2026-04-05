---
type: reference
---

# Code Reviewer Agent Memory Index

## Files

| File | Type | Summary |
|------|------|---------|
| `environment-constraints.md` | project | GitHub API constraints, token status, self-review limitation, known open PRs |

## Cycle Log

| Date | PRs Reviewed | Outcome | Notes |
|------|-------------|---------|-------|
| 2026-04-03 | 0 | No reviews performed | gh CLI missing, API rate-limited, no tokens in env |
| 2026-04-05 | 3 (#489, #301, #485) | All APPROVED | GITHUB_TOKEN available; self-review blocked for yevheniidehtiar PRs; posted as comments |

## Recurring Patterns

### Token / Self-Review Issue
The `GITHUB_TOKEN` in the environment belongs to `yevheniidehtiar` (the repo owner).
PRs authored by that user cannot be formally approved via the GitHub review API (HTTP 422).
Workaround: post structured review as an issue comment.

### No `review` Label on Open PRs
The `review` label was used on historical closed PRs. New PRs from the conductor/agentic
workflow do not always get the label applied before the reviewer runs. Review the 3 most
substantive open PRs per run when no `review`-labeled PRs exist.

### Chore/Docs PRs (Non-Code)
For `chore` and `docs` PRs (`.meta/` migrations, documentation), the full architecture
checklist does not apply. Focus on:
1. Commit identity (Claude Code vs human)
2. Commit message format (Conventional Commits)
3. Data integrity / content quality
4. `.gitignore` correctness for any new artifacts
