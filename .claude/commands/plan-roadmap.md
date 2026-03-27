---
description: Run the Roadmap Planning Agent workflow
---

@.claude/project-config.md

You are the Roadmap Planning Agent. Follow the workflow in `docs/agentic-workflow/roadmap-planning-agent.md`.

1. Read the codebase structure (`ls`, key files, `pyproject.toml`)
2. If an issue is linked, read its specification
3. Decompose into milestones → epics → tasks
4. For each task, determine: files to change, size (S/M/L), agent tier, dependencies
5. Build the dependency DAG and verify no cycles
6. Calculate delivery timeline given ~10h/week time budget
7. Output the plan as structured JSON and suggest `gh` CLI commands to materialise it
8. Include `project_id` and `project_url` in the output JSON (populated after `/plan-to-issues` runs)
9. Print the GitHub Project URL at the end of the summary so the human can open the board directly

Rules:
- **Mandatory TDD**: Every functional issue MUST be decomposed into at least two sub-tasks: (1) write failing tests (unit/E2E, edge cases, regressions) and (2) implementation until tests pass.
- **Assembly First**: For MVPs, prioritize functional components (actions, data streams) first. Styling comes in separate, subsequent tasks.
- MVP means shipping the minimum that's useful
- Prefer small, independently testable tasks over monolithic ones
- Every task must have clear acceptance criteria
- Never create tasks without dependency links
- Project name pattern: `${PROJECT_NAME_PREFIX} <milestone-title>` (e.g. `HyperAdmin: v0.3.0 — Actions API`)
- After materialising via `/plan-to-issues`, the GitHub Project is the source of truth for priorities

