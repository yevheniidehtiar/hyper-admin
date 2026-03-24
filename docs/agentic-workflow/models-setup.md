# Models Setup & Plans

To balance cost, performance, and reasoning capabilities, this workflow supports three standard model configurations. Choose the one that best fits your project's budget and complexity.

## Model Tiers

| Tier | Characteristics | Typical Models |
|---|---|---|
| **High-Reasoning** | Deep architecture analysis, complex planning, bug root-cause. | Claude Opus, OpenAI o1, Gemini 1.5 Pro |
| **Production** | Code implementation, structured review, standard triage. | Claude Sonnet, GPT-4o, Gemini 1.5 Pro/Flash |
| **Utility** | Unit tests, documentation, simple fixes, formatting. | Gemini 1.5 Flash, GPT-4o-mini |

## Recommended Plans

### 1. The "Eco" Plan (Budget-First)
*Best for: Side projects, small utilities, or early-stage experiments.*

- **Deep Research**: Production Model (e.g. Sonnet)
- **Implementation**: Utility Model (e.g. Flash)
- **QA/Review**: Production Model
- **Estimated Cost**: ~€5-10 / month (API usage) or standard Pro subscription.

### 2. The "Balanced" Plan (Standard OSS)
*Best for: Production-grade libraries with regular community contributions.*

- **Deep Research**: High-Reasoning Model (e.g. Opus/o1)
- **Implementation**: Production Model (e.g. Sonnet)
- **QA/Review**: Production Model
- **Estimated Cost**: ~€47 / month (Subscription-based: Google AI Pro + Claude Pro).

### 3. The "Power" Plan (High-Velocity)
*Best for: Complex systems, security-critical code, or high-traffic projects.*

- **Deep Research**: High-Reasoning Model (Strict iteration)
- **Implementation**: High-Reasoning Model + Human verification
- **QA/Review**: High-Reasoning Model (Cross-check)
- **Estimated Cost**: €100+ / month (Heavy API usage).

## Configuration

Settings are primarily controlled via `CLAUDE.md`, `GEMINI.md`, and the `.mcp.json` configuration.

- **Primary Model**: Used for implementing code and running review tasks.
- **Research Model**: Used specifically for the `plan` and `research` commands.
- **Utility Model**: Used for lightweight background tasks like `lint` or `docs`.
