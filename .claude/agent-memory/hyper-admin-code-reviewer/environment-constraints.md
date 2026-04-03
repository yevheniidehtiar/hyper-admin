---
type: project
---

# Environment Constraints

## GitHub API Access

As of 2026-04-03 (updated same date, second cycle), the code reviewer runs in an environment
with the following constraints:

### gh CLI
- `gh` is NOT installed in the execution environment.
- Cannot use `gh pr list`, `gh pr diff`, `gh pr review`, or any other `gh` subcommands.

### GitHub MCP Tools (`mcp__github__*`)
- `.mcp.json` configures only a **Slack** MCP server (`https://mcp.slack.com/mcp`).
- There is NO GitHub MCP server configured. Tools named `mcp__github__*` do not exist
  in this environment and cannot be invoked.
- The task instructs "use GitHub MCP tools" but this is not possible until the server
  is added to `.mcp.json`.

### GitHub REST API (unauthenticated)
- Direct `curl` calls to `https://api.github.com` start at 60 req/hr for the container IP.
- The rate limit is exhausted within a single reviewer cycle (confirmed 2026-04-03).
- Unauthenticated requests cannot post review comments or approve/request-changes on PRs
  (these require authentication regardless of rate limits).

### Token Availability
- `CLAUDE_GH_TOKEN`: NOT set
- `GH_TOKEN`: NOT set
- `GITHUB_TOKEN`: NOT set

### Implication
The code reviewer cannot perform any live PR review cycles until one of the following is resolved:
1. A valid `CLAUDE_GH_TOKEN` (or `GH_TOKEN`) is injected into the environment, OR
2. A GitHub MCP server is added to `.mcp.json`, OR
3. `gh` CLI is installed in the container image

Until then, every reviewer cycle will end with "no reviews can be performed."

## Known Open PRs (from 2026-04-03 cycles)

| PR # | Author | Title | Labels | Reviews | Reviewer Notes |
|------|--------|-------|--------|---------|---------------|
| #353 | dependabot[bot] | ci(deps): bump ci-dependencies group (6 updates) | dependencies, github_actions | 0 | Dependabot CI dep bump — out of scope for code review |
| #301 | alexbthundiyil-spec | docs: add research on community donation options (#279) | none | 0 | Docs-only PR: adds `docs/community/donations.md` and modifies `.github/FUNDING.yml`. Partial diff retrieved before rate limit hit. |

### PR #301 Partial Analysis (before rate limit)
Files changed:
- `.github/FUNDING.yml` — modified (5 additions, 1 deletion): adds/updates GitHub Sponsors config
- `docs/community/donations.md` — added (69 lines): research doc comparing GitHub Sponsors,
  Polar.sh, Open Collective, Ko-fi, Buy Me a Coffee

This is a pure documentation/community PR. No Python code, no architecture, no templates,
no tests. The review checklist items (module boundaries, Pydantic, business logic, E2E selectors)
do not apply. The commit message follows Conventional Commits (`docs: ...`). A full review
would only need to verify the content quality of the markdown files — which could not be
completed due to rate limiting.
