# Cost Model: Token-Based Estimates

While this workflow is optimized for subscription-based usage (e.g., Claude Pro/Max), it is useful to understand the underlying token consumption for each agentic activity.

## Resource Consumption Tiers

| Activity | Tier | Est. Tokens / Event | Reasoning Focus |
|---|---|---|---|
| **Deep Research** | High-Reasoning | 50k - 150k | High (Iterative Q&A) |
| **Roadmap Planning** | High-Reasoning | 30k - 80k | High (DAG verification) |
| **Dev: Implementation** | Production | 20k - 100k | Medium (Context-heavy) |
| **Dev: Unit Tests** | Utility / Production | 10k - 30k | Low (Pattern matching) |
| **Code Review** | Production | 15k - 40k | Medium (Audit trail) |
| **QA / Triage** | Utility | 5k - 20k | Low (Error analysis) |

## Throughput Planning (Monthly)

For a solo developer spending ~10h/week on a project, the typical monthly volume is:

| Tool Category | Typical Volume | Est. Monthly Tokens |
|---|---|---|
| **High-Reasoning** (Planning) | ~15 sessions | 1.5M - 2.5M |
| **Production** (Implementation) | ~50 tasks | 2.5M - 5.0M |
| **Utility** (CI/CD / Background) | ~100 events | 1.0M - 2.0M |

## Capacity Tracking

If you are using API-based pricing instead of subscriptions, monitor your usage via your provider's dashboard. For subscription users, track **message limits** per window:

```
Weekly capacity report:
  High-Reasoning limit:  [####..............] 25% (Pro window)
  Production limit:      [##########........] 50% (Pro window)
  Utility limit:         [##................] 10% (Haiku)
```

## Optimization Tips

- **Batch Context**: Combine related questions into a single message to reduce redundant prompt tokens.
- **Project Context**: Use "Projects" or "Collections" features to upload the codebase once rather than sending it with every message.
- **Model Tiering**: Always use the lowest capable tier for the task (e.g., use a Utility model for generating docstrings or basic unit tests).
- **Clear Scoping**: Use the Deep Research phase to avoid "wasted implementation" tokens caused by ambiguous requirements.
