# OSS Library Agentic Workflow

!!! tip "New here?"
    Start with the [Agentic CLI Onboarding](onboarding.md) guide for a quick orientation of all AI agent configuration in this project.

This project follows an 8-agent workflow for AI-assisted open-source library development. Each agent has a specific role, trigger, and output contract, orchestrated through GitHub's native event system.

## Architecture

```
Human → Deep Research → Roadmap Planning → Workload Queue → Dev Agents
                                                              ↓
                                         Release ← QA ← Code Review
                                           ↓
                                    Project Memory → Feedback Loop
```

## Core Principles

- **Mandatory TDD**: Every functional change begins with failing tests. Implementation follows.
- **Assembly First**: MVPs focus on pure functionality (actions, data streams) before styling.

## Agents

| # | Agent | Tool Tier | Purpose |
|---|-------|------|---------|
| 1 | [Deep Research](deep-research-agent.md) | High-Reasoning | Clarify ideas through structured Q&A |
| 2 | [Roadmap Planning](roadmap-planning-agent.md) | High-Reasoning | Decompose specs into milestones/epics/tasks |
| 3 | [Dev Agents](dev-agents.md) | Production / Utility | Implement code changes |
| 4 | [Code Review](code-review-agent.md) | Production | Automated review with audit trail |
| 5 | [QA](qa-agent.md) | Utility / Production | Compatibility matrix + test analysis |
| 6 | [Release](release-agent.md) | Production | Changelog, versioning, publish |
| 7 | [Scheduled](scheduled-agent.md) | Utility / Production | Weekly health monitoring |
| 8 | [Community Ingestion](community-ingestion.md) | Production | Triage external contributions |

## Cross-Agent Orchestration

See [Models & Plans](models-setup.md) for tiered configuration options (Eco, Balanced, Power).

See [Orchestration](orchestration.md) for the event flow, label-based state machine, and project memory.


## Cost Model

See [Cost Model](cost-model.md) for subscription-based budgeting and throughput planning.

## Label-Based State Machine

```
idea → researched → planned → approved → in-progress → review → qa-passed → released
                                  ↑                        │
                                  └── rejected (with ctx) ──┘
```

## Human Checkpoints

Every critical transition requires human approval:

1. **Plan review** — approve the GitHub Project board
2. **Cost approval** — approve estimated spend
3. **Milestone gate** — approve next phase
4. **Release approval** — approve publish
5. **Escalation** — review agent failures
