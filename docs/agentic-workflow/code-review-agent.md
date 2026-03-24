# Agent 4: Code Review Agent

| Property | Value |
|---|---|
| **Tier** | Production Model (e.g. {{ default_ai_model }}) |
| **Trigger** | PR submitted (by Jules, human, or Claude Code) |
| **Purpose** | Review code quality, correctness, backward compat, produce audit trail |
| **Est. Cost** | 15k - 40k tokens per PR review |

## What It Reviews

1. **Correctness** — does the code do what the task specification says?
2. **Style & consistency** — matches project conventions (ruff enforced + patterns)
3. **Backward compatibility** — does this change break existing public API?
4. **Test coverage** — are acceptance criteria from the task covered by tests?
5. **Security** — no obvious vulnerabilities (dependency injection, input validation)
6. **Documentation** — public API changes reflected in docstrings and changelog

## Audit Trail

Every review produces a structured comment on the PR:

```markdown
## Code review — automated

**Reviewer**: {{ default_ai_model }} (via claude-code-action)
**Verdict**: ✅ Approved / ⚠️ Changes requested / ❌ Rejected

### Checklist
- [x] Acceptance criteria from #17 met
- [x] Type hints complete
- [x] Tests cover happy path + error cases
- [ ] Missing: test for retry exhaustion scenario
- [x] No backward-compatibility breaks detected
- [x] Docstrings present on public methods

### Detailed findings
1. `retry_with_backoff()` — consider adding a `on_retry` callback hook
   for observability. Not blocking, but recommended for v0.2.
2. Line 45: `sleep(backoff * 2 ** attempt)` — should add jitter to
   prevent thundering herd. Spec requires this. **Blocking.**

### Quality score: 8/10
### Merge rationale: Approve after addressing finding #2 (jitter).
```

This audit trail is persisted as a PR comment — visible to all future contributors, searchable, and part of the permanent project record.

## Implementation

Uses `anthropics/claude-code-action` GitHub Action:

```yaml
name: Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          model: {{ default_ai_model }}
          prompt: |
            Review this PR against its linked issue specification.
            Check: correctness, backward compat, test coverage, style.
            Output structured review with verdict, checklist, findings,
            quality score (1-10), and merge rationale.
            If changes needed, be specific about what and why.
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

!!! note "API cost"
    The GitHub Action uses API credits (~€5-15/month for 20-40 PRs), not your Pro subscription.
    **Zero-cost alternative:** Run review manually via `claude` CLI using your Pro quota.

## Community PR Handling

Community PRs follow a different escalation path:

- Same review quality as internal PRs
- If changes requested: constructive comment explaining *why*
- No update after 14 days: polite ping
- No update after 30 days: close with "feel free to reopen"
- On merge: add contributor to `CONTRIBUTORS.md`
