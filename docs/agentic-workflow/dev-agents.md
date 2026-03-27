# Agent 3: Dev Agents (Tiered)

| Property | Value |
|---|---|
| **Tier** | Claude Code (all sizes) |
| **Trigger** | Task dispatched from workload queue (GitHub Issue assigned) |
| **Purpose** | Implement code changes according to task specification |
| **Est. Cost** | 20k - 100k tokens per implementation task |

## Tiering Strategy

```
Incoming task from workload queue
  │
  ├── size:S → Claude Code via fix-issue skill (lightweight TDD loop)
  ├── size:M → Claude Code via implement-feature skill (full self-eval loop)
  └── size:L → Claude Code via implement-feature skill + human checkpoint gate
```

> **Note**: Gemini CLI and Jules are paused — Google AI is currently unavailable.
> All dispatch goes to Claude Code. Jules/Gemini entries are kept below for when
> Google AI becomes available again.

### Claude Code — fix-issue skill (size:S)

- One-liner fixes, small utility functions, config tweaks
- Lightweight loop: branch → explore → test-first → implement → lint+test → PR
- Runs in an isolated worktree dispatched by the conductor
- Example: "Add a `--verbose` flag to the CLI parser"

### Claude Code — implement-feature skill (size:M)

- Core dev agent for most implementation work
- Full self-evaluating loop: plan → validate against 16+ checklist items → TDD → PR
- Blocker protocol: searches memory, saves WIP as draft PR, halts with issue comment
- Runs in an isolated worktree dispatched by the conductor
- Example: "Implement `RetryPolicy` class with exponential backoff and jitter"

### Claude Code — implement-feature + human checkpoint (size:L)

- Complex tasks requiring deep architectural reasoning
- Conductor pauses after planning phase and presents plan to human for approval
- Human approves or adjusts scope before implementation begins
- Example: "Redesign the plugin system to support async hooks"

### Paused: Gemini CLI (size:S) / Jules (size:M–L)

- Previously used for high-volume parallel dispatch (Jules: 15 concurrent tasks)
- Currently unavailable — Google AI blocked/broken as of 2026-03
- Re-enable by updating `scripts/setup-github.sh` labels and conductor dispatch logic

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
