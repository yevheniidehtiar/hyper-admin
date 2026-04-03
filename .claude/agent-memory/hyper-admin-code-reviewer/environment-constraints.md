---
type: project
---

# Environment Constraints

## GitHub API Access

As of 2026-04-03, the code reviewer runs in an environment with the following constraints:

### gh CLI
- `gh` is NOT installed in the execution environment.
- Cannot use `gh pr list`, `gh pr diff`, `gh pr review`, or any other `gh` subcommands.

### GitHub REST API (unauthenticated)
- Direct `curl` calls to `https://api.github.com` are rate-limited by IP (`34.72.174.153`).
- Unauthenticated requests exceed GitHub's public rate limit immediately.

### Token Availability
- `CLAUDE_GH_TOKEN`: NOT set
- `GH_TOKEN`: NOT set
- `GITHUB_TOKEN`: NOT set

### Implication
The code reviewer cannot perform any live PR review cycles until one of the following is resolved:
1. `gh` CLI is installed in the container image, OR
2. A valid `CLAUDE_GH_TOKEN` (or `GH_TOKEN`) is injected into the environment, which would allow
   both `gh` CLI (if installed) and authenticated `curl` calls to the GitHub REST API.

Until then, every reviewer cycle will end at Step 3 with "no reviews can be performed."

## Known Open PRs (from prior cycles)

| PR # | Author | Type | Notes |
|------|--------|------|-------|
| #353 | Dependabot | dep bump | Out of scope for code review |
| #301 | Human contributor | feature | Out of scope for code review |

No agent-generated (Claude Code bot) PRs have been observed in any cycle to date.
