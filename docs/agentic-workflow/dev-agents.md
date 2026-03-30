# Dev Agents

| Property | Value |
|---|---|
| **Runtime** | Claude Code (all sizes) |
| **Trigger** | Task dispatched from workload queue (GitHub Issue assigned) |
| **Purpose** | Implement code changes according to task specification |
| **Est. Cost** | 20k–100k tokens per implementation task |

## Dispatch Strategy

All development tasks are dispatched by the **conductor agent** and executed by Claude Code in isolated git worktrees.

```
Incoming task from workload queue
  │
  ├── size:S → fix-issue skill (lightweight TDD loop)
  ├── size:M → implement-feature skill (full self-eval loop)
  └── size:L → implement-feature skill + human checkpoint gate
```

### fix-issue skill (size:S)

- One-liner fixes, small utility functions, config tweaks
- Lightweight loop: branch → explore → test-first → implement → lint+test → PR
- Runs in an isolated worktree dispatched by the conductor
- Example: "Add a `--verbose` flag to the CLI parser"

### implement-feature skill (size:M)

- Core dev agent for most implementation work
- Full self-evaluating loop: plan → validate against 16+ checklist items → TDD → PR
- Blocker protocol: searches agent memory, saves WIP as draft PR, halts with issue comment
- Runs in an isolated worktree dispatched by the conductor
- Example: "Implement `RetryPolicy` class with exponential backoff and jitter"

### implement-feature + human checkpoint (size:L)

- Complex tasks requiring deep architectural reasoning
- Conductor pauses after planning phase and presents plan to human for approval
- Human approves or adjusts scope before implementation begins
- Example: "Redesign the plugin system to support async hooks"

## TDD-First Execution

Dev agents must strictly follow the TDD order:

1. **Test Task**: Write tests in the appropriate directory (`tests/`). Verify they fail.
2. **Implementation Task**: Write minimal code in `src/` to pass the tests. Verify with `just test`.

## Task Dispatch Protocol

Each task (GitHub Issue) includes a structured body:

```markdown
## Task specification

**Scope**: `src/core/retry.py` (new file)
**Size**: M

## Acceptance criteria
- [ ] `RetryPolicy` dataclass with: max_retries, backoff_factor, jitter
- [ ] `retry_with_backoff()` async decorator
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
Task dispatched to Claude Code
  → Agent creates PR
    → CI passes?
      Yes → Move to Code Review (add `review` label)
      No  → Agent retries (max 2 auto-retries)
        → Still failing?
          Yes → Label: "needs-human", escalate to human
```

## Parallel Execution

The conductor dispatches up to **3 concurrent agents** in isolated worktrees per cycle:

1. Dispatch independent tasks in parallel (up to 3 worktrees)
2. Queue dependent tasks to auto-dispatch when blockers close
3. Run up to 3 cycles per session (9 issues total cap)

This turns serial multi-week effort into parallel 1–2 day bursts.

## Rules Enforced

Dev agents (via the implement-feature skill) enforce all project rules during the planning gate:

| Rule | Check |
|------|-------|
| `CONSTITUTION.md` | Module boundaries, dependency direction |
| `planning-playbook.md` | Bottom-up task ordering |
| `code-style.md` | Type hints, selectinload(), line length |
| `testing.md` | E2E locator priority, no `ha-*` selectors |
| `git-workflow.md` | Claude Code identity, Conventional Commits |
