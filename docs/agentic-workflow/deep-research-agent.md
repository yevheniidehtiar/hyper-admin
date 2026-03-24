# Agent 1: Deep Research Agent

| Property | Value |
|---|---|
| **Tier** | High-Reasoning Model (e.g. Claude Opus, OpenAI o1) |
| **Trigger** | Human submits a raw idea or feature request |
| **Purpose** | Clarify ambiguous ideas through structured Q&A until understanding > 85% |
| **Est. Cost** | 50k - 150k tokens per research session |

## How It Works

The Deep Research agent takes a raw, potentially vague idea and turns it into a precise, actionable specification through an iterative questionnaire. It doesn't write code — it writes understanding.

### Process

1. **Architecture scan** — reads the codebase to understand what exists today
2. **Gap analysis** — identifies what the idea requires vs what already exists
3. **Questionnaire generation** — asks 3-5 targeted questions per round:
    - "Should retries apply to all HTTP methods or only idempotent ones?"
    - "What's the desired circuit breaker threshold — fail count or error rate?"
    - "Should the retry configuration be per-client or per-request?"
4. **Understanding scoring** — self-evaluates 0-100% across: scope, constraints, edge cases, backward compatibility, testing requirements
5. **Iteration** — repeats until understanding > 85% or max 5 iterations

## Output Contract

```json
{
  "understanding_score": 0.89,
  "iteration_count": 3,
  "architecture_snapshot": {
    "languages": ["python"],
    "modules": [],
    "test_coverage": 0.42,
    "public_api_surface": []
  },
  "idea": {
    "raw": "Original human input",
    "refined": "Precise specification after Q&A",
    "scope": "mvp",
    "constraints": ["Must maintain backward compat with v0.x"],
    "out_of_scope": ["Connection pooling (deferred to v0.3)"],
    "acceptance_criteria": [
      "Exponential backoff with jitter",
      "Configurable max retries (default: 3)",
      "Circuit breaker trips after 5 consecutive failures"
    ]
  }
}
```

## Guardrails

- **Max 5 iterations.** If understanding < 85% after 5, escalate to human with summary of what's unclear
- **Minimum 5% improvement per iteration.** If stalled, explain what's blocking and request more context
- **Never assume.** Assumptions are the #1 cause of wasted dev agent cycles

## Prompt Template

```
You are a Deep Research Agent for OSS library planning.

Your job is to take a raw idea and produce a precise specification by asking
the right questions. You have access to the codebase via Claude Code.

Steps:
1. Read the codebase structure (ls, key files, pyproject.toml)
2. Identify what exists and what's missing for the proposed idea
3. Generate 3-5 targeted questions per round
4. After each round, score your understanding (0-100%) across:
   - Scope clarity (what's in/out)
   - Technical constraints (backward compat, dependencies)
   - Edge cases (error handling, concurrency, limits)
   - Testing requirements (what must be tested, what coverage)
   - Definition of Done (when is this "finished"?)
5. Stop when total score > 85% or after 5 rounds

Output the structured JSON specification matching the output contract.
Never assume. If something is ambiguous, ask.
```
