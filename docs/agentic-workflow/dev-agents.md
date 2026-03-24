# Agent 3: Dev Agents (Tiered)

| Property | Value |
|---|---|
| **Tier** | Production (Primary) / Utility (Tests) |
| **Trigger** | Task dispatched from workload queue (GitHub Issue assigned) |
| **Purpose** | Implement code changes according to task specification |
| **Est. Cost** | 20k - 100k tokens per implementation task |

## Tiering Strategy

```
Incoming task from workload queue
  │
  ├── size:S → Gemini CLI (inline fix, < 30 min)
  ├── size:M → Jules (async PR, 1-4h)
  └── size:L → Jules + Claude Code (plan first, then implement)
```

### Gemini CLI (size:S)

- One-liner fixes, small utility functions, config changes
- Run directly in terminal, no async overhead
- Example: "Add a `--verbose` flag to the CLI parser"

### Jules (size:M)

- Core dev agent — handles most implementation work
- Runs async on Google Cloud VM, creates PR when done
- 15 concurrent tasks = dispatch an entire milestone at once
- Example: "Implement `RetryPolicy` class with exponential backoff and jitter"

### Claude Code (size:L or fallback)

- Complex tasks requiring deep architectural reasoning
- Interactive — you guide the implementation in real-time
- Fallback when Jules produces a PR that fails review
- Example: "Redesign the plugin system to support async hooks"

## TDD-First Execution

Dev agents must strictly follow the TDD order planned by the Roadmap agent:

1.  **Test Task**: Implement the requested tests (unit/E2E) in the appropriate directory (`tests/`). Verify they fail as expected.
2.  **Implementation Task**: Write the minimal code in `src/` to satisfy the tests. Verify they pass with `just test`.

## Task Dispatch Protocol

Each task (GitHub Issue) includes a structured body:

```markdown
## Task specification

**Scope**: `src/core/retry.py` (new file)
**Agent**: jules
**Size**: M
**Blocked by**: #16 (base HTTP client)

## Acceptance criteria
- [ ] `RetryPolicy` dataclass with: max_retries, backoff_factor, jitter
- [ ] `retry_with_backoff()` async decorator
- [ ] Respects `Retry-After` header when present
- [ ] Type hints on all public API
- [ ] Docstrings with examples

## Context for agent
The HTTP client in `src/core/http.py` needs retry capability.
See the base client class `HttpClient` for the interface.

## Pre-commit requirements
- ruff format + ruff check must pass
- mypy --strict must pass
- pytest must pass with >80% coverage on new code
```

## Failure Handling

```
Task submitted to Jules
  → Jules creates PR
    → CI passes?
      Yes → Move to Code Review
      No  → Jules retries (max 3 auto-retries)
        → Still failing?
          Yes → Label: "needs-human"
            → Same failure each time? → Spec problem, escalate
            → Different each time? → Try Claude Code
```

## Parallel Execution

Jules's 15-concurrent-task capability is the superpower. For a milestone with 12 tasks where 8 are independent:

1. Dispatch all 8 independent tasks to Jules simultaneously
2. Use Claude Code for the 1-2 complex tasks
3. Queue 2-3 dependent tasks to auto-dispatch when blockers close

Turns a serial multi-week effort into a parallel 1-2 day burst.
