# Models Setup

To balance cost, performance, and reasoning capabilities, this workflow uses three Claude model tiers.

## Model Tiers

| Tier | Model | Characteristics | Used by |
|------|-------|-----------------|---------|
| **High-Reasoning** | Claude Opus | Deep architecture analysis, complex planning, orchestration | Conductor |
| **Production** | Claude Sonnet | Code review, structured analysis, standard triage | Code Reviewer, Project Manager, OSS Triage Auditor |
| **Utility** | Claude Haiku | Lightweight monitoring, simple fixes, fast responses | Delivery Manager |

## Recommended Plans

### 1. The "Eco" Plan (Budget-First)
*Best for: Side projects, small utilities, or early-stage experiments.*

- **Planning & Research**: Production (Sonnet)
- **Implementation**: Production (Sonnet)
- **QA/Review**: Production (Sonnet)
- **Estimated Cost**: ~$20/month (Claude Pro subscription)

### 2. The "Balanced" Plan (Standard OSS)
*Best for: Production-grade libraries with regular contributions.*

- **Planning & Research**: High-Reasoning (Opus)
- **Implementation**: Production (Sonnet)
- **QA/Review**: Production (Sonnet)
- **Estimated Cost**: ~$100/month (Claude Max subscription)

### 3. The "Power" Plan (High-Velocity)
*Best for: Complex systems, security-critical code, or high-traffic projects.*

- **Planning & Research**: High-Reasoning (Opus)
- **Implementation**: High-Reasoning (Opus) + Human verification
- **QA/Review**: High-Reasoning (Opus)
- **Estimated Cost**: $200+/month (heavy API usage)

## Configuration

Settings are controlled via:

- **`CLAUDE.md`** — Project-wide instructions, agent roster, hook-first rule
- **`.mcp.json`** — MCP server configuration, default model
- **`.claude/agents/*.md`** — Per-agent model tier (set in frontmatter)
- **`.claude/project-config.md`** — Runtime constants (limits, labels, repo)
