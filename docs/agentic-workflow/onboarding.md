# Agentic CLI Onboarding

> You're a new agent (or a human setting up agentic CLI tooling). This page gives you the full landscape of HyperAdmin's AI configuration in one place — what exists, where it lives, and what reading order to follow.

---

## 1. Reading Order

Start here. Each row tells you which file to read, why, and when.

| Priority | File | What it governs | When to read |
|----------|------|-----------------|--------------|
| **Must — before any code** | `CLAUDE.md` | Primary Claude Code entry point — dev commands, hook-first rule, E2E selector table | First thing, every session |
| **Must — before any code** | `CONSTITUTION.md` | Architectural law — module boundaries, dependency direction, naming bans, violation definitions | Before touching `src/` |
| **Must — before planning** | `AGENTS.md` | Hook-first planning rules + Software Architect review checklist | Before writing a plan |
| **Must — before planning** | `.claude/rules/planning-playbook.md` | Bottom-up ordering: models → logic → views → UI | Before ordering tasks |
| **Must — before code style** | `.claude/rules/code-style.md` | Python conventions — feature-grouped layout, type hints, 100-char lines, HTMX/Alpine.js | Before writing Python |
| **Must — before commits** | `.claude/rules/git-workflow.md` | Claude Code commit identity, `CLAUDE_GH_TOKEN` for PRs, Conventional Commits | Before first commit |
| **Must — before tests** | `.claude/rules/testing.md` | TDD, unit/E2E split, `data-testid` reference, Playwright Chromium install | Before writing tests |
| **Reference** | `.claude/project-config.md` | Shared constants (public repo, branch, cycle limits) + label state machine + runtime derivation pattern | Always `@`-include in commands/agents that use GitHub |
| **Reference** | `ROADMAP.md` | Current phase and reserved Phase 3 domains | When scoping a feature |
| **Reference** | `GEMINI.md` | Gemini CLI conventions (size:S tasks) | When dispatching to Gemini |
| **Reference** | `JULES.md` | Jules async task conventions (size:M tasks) | When dispatching to Jules |
| **Reference** | `docs/agentic-workflow/` | Full 8-agent workflow spec | When orchestrating a release or full feature cycle |

---

## 2. Agent Persona Files

These files are loaded by different agent runtimes. The overlapping rules (hook-first, architecture) are intentionally duplicated so each agent only needs to read its own file.

| File | Runtime | Purpose |
|------|---------|---------|
| `CLAUDE.md` | Claude Code | Primary entry point — dev commands, hook-first rule, E2E selectors, agentic workflow overview |
| `AGENTS.md` | Any (PR-triggered) | Hook-first planning rules + Software Architect structural review checklist |
| `CONSTITUTION.md` | All agents | Authoritative architectural rules — module structure, dependency direction, naming, violations |
| `GEMINI.md` | Gemini CLI | One-shot task conventions, `@file` syntax, size:S constraint, CLI architecture notes |
| `JULES.md` | Jules | Async task conventions, issue labeling (`jules`, `jules:fix`), sizing table, failure handling |

!!! info "Why so many files?"
    Each agent runtime reads its own instruction file. Duplication across files is intentional — an agent that only reads `GEMINI.md` must still know the architecture and commit rules without needing to find `CLAUDE.md`.

---

## 3. Rules (`.claude/rules/`)

Rules auto-activate when Claude Code touches files matching their `paths` glob. No explicit invocation needed.

| File | Paths trigger | Summary |
|------|--------------|---------|
| `code-style.md` | `src/hyperadmin/**/*.py` | Feature-grouped layout, snake_case files, type hints required, 100-char lines, no commented-out code, `selectinload()` for relationships, HTMX + Alpine.js |
| `git-workflow.md` | Global | All commits use Claude Code identity (never Co-Authored-By), PRs via `CLAUDE_GH_TOKEN`, Conventional Commits enforced by commitizen |
| `testing.md` | `tests/**`, `src/hyperadmin/**/*.py` | TDD-first, unit in `tests/unit/`, E2E in `tests/e2e/`, 99% coverage target, `ha-*` CSS for styling only, full `data-testid` reference |
| `planning-playbook.md` | Global | Strict bottom-up ordering: (1) Architecture/models → (2) Business logic → (3) API/views → (4) UI/HTMX. Lessons from issues #115–119. |

---

## 4. Skills (`.claude/skills/`)

Skills are multi-step agentic workflows invoked as `/skill-name`.

| Skill | Invoke as | When to use |
|-------|-----------|-------------|
| `implement-feature` | `/implement-feature <issue>` | Full self-evaluating loop — plan gate, self-eval checklist, TDD, blocker handling, memory writes. Use for new features. |
| `fix-issue` | `/fix-issue <issue>` | Lighter TDD loop — branch, explore, test, implement, PR. Use for bug fixes and small changes. |

**implement-feature** runs three phases:

- **Phase A (Planning)**: Read issue → create bottom-up plan → self-evaluate against 16+ checklist items (Architecture, Ordering, Code Style, Testing, Git) → gate: all PASS → proceed; any FAIL → post questionnaire on issue and halt.
- **Phase B (Implementation)**: TDD execution loop → blocker protocol (search memory, commit WIP as draft PR, document blocker on issue, halt).
- **Phase C (Submission)**: Full `poe lint` + `poe test` gates → final checklist → commit + PR → write memory.

---

## 5. Slash Commands (`.claude/commands/`)

| Command | Description | Typical use |
|---------|-------------|-------------|
| `/scaffold` | Generate new module + tests + `__init__.py` update | Bootstrapping a new feature module |
| `/implement-feature <issue>` | Redirects to the `implement-feature` skill | End-to-end feature implementation |
| `/lint` | Run `just lint`, auto-fix errors, re-run to confirm clean | Pre-commit quality check |
| `/test` | Run `just test-cov` with coverage, report failures | Verification after changes |
| `/release` | Check clean state, read CHANGELOG, lint+test, confirm version, `just release` | Cutting a new release |
| `/plan-roadmap` | Roadmap Planning Agent — reads codebase, decomposes to milestones/epics/tasks, builds dependency DAG | Decomposing a spec into issues |
| `/plan-to-issues <request>` | Analyze request, create epic + child GitHub issues with labels/sizes/dependencies | Materializing a plan into the issue tracker |
| `/plan-to-issues-dry-run <request>` | Same as above, preview only — no issues created | Reviewing a plan before committing |
| `/run-autonomous-team` | Launch the conductor to orchestrate dev agents through the backlog — picks ready issues, dispatches workers in worktrees, coordinates review, manages merge queue | Autonomous batch implementation |
| `/oss-triage-audit [dry-run\|live]` | Run `scripts/triage_audit.py` — AI-slop scoring, ego-PR detection, duplicate detection, lifecycle enforcement | Periodic hygiene pass on open issues/PRs |

---

## 6. Headless Agents (`.claude/agents/`)

These agents run as sub-processes via the `Agent` tool or `claude --agent <name>`. Each has its own model, tool allowlist, and memory directory.

| Agent | Model | Role |
|-------|-------|------|
| `conductor` | opus | Orchestrates autonomous team cycles — dispatches dev agents in worktrees, coordinates reviews, **owns merge queue authority** (evaluates file overlap + dependency order → `merge-granted` / `merge-deferred`) |
| `delivery-manager` | haiku | Watches label filters: adds `merge-requested` when PR is approved + CI green; executes merge when `merge-granted` appears; posts Slack delivery notifications |
| `hyper-admin-code-reviewer` | haiku | Reviews PRs against CONSTITUTION.md, planning-playbook, code-style, E2E conventions — 8-section checklist with machine-readable `VERDICT: APPROVED` / `VERDICT: CHANGES_REQUIRED` |
| `oss-triage-auditor` | sonnet | Delegates to `scripts/triage_audit.py` for AI-slop/ego-PR detection, duplicate detection, lifecycle label enforcement, TTL |

Each agent has a persistent memory directory under `.claude/agent-memory/<agent-name>/`.

---

## 7. Hooks & Automation

### UserPromptSubmit hook — `fetch-rules.sh`

Runs before every prompt. Reads the Rippletide user ID from `~/Library/Application Support/com.Rippletide.Rippletide/config.json`, queries `https://coding-agent.up.railway.app/query-rules`, and injects the response as `[Coding Rules from Rippletide]` context.

**Implication**: Both `CLAUDE.md` and `AGENTS.md` enforce a **hook-first rule** — before any planning or code generation, you must explicitly name the rules injected by this hook and apply them. If no rules are returned, state that explicitly.

### PostToolUse hooks — `.claude/settings.json`

| Trigger | Action |
|---------|--------|
| `Edit` or `Write` on any `*.py` file | Runs `uv run ruff format <file>` automatically |
| `TaskUpdate` with `status=completed` | Runs `scripts/redeploy-example.sh` |

### Permission allowlist — `.claude/settings.local.json`

Pre-approved commands (no confirmation prompt):
- `uv lock`, `uv run`, `uv pip` — dependency management
- `poe test:unit`, `poe lint` — quality gates
- `git add`, `git -c`, `git checkout`, `git push` — version control
- `gh pr`, `gh run`, `gh issue`, `gh label`, `gh api` — GitHub CLI
- `docker compose` — container orchestration

---

## 8. MCP Servers (`.mcp.json`)

| Server | URL | Purpose |
|--------|-----|---------|
| Slack | `https://mcp.slack.com/mcp` | Send/read Slack messages, notify humans about delivery status |

Default model: `claude-sonnet-4-6`

---

## 9. Agent Memory System

### Per-agent memory

Two headless agents have dedicated memory directories:

| Agent | Directory |
|-------|-----------|
| `conductor` | `.claude/agent-memory/conductor/` |
| `delivery-manager` | `.claude/agent-memory/delivery-manager/` |
| `hyper-admin-code-reviewer` | `.claude/agent-memory/hyper-admin-code-reviewer/` |

### Project-level memory (Claude Code)

The `implement-feature` skill and Claude Code sessions write to:

```
~/.claude/projects/-Users-yevheniidehtiar--projects-hyper-admin/memory/
```

This memory persists across conversations. The index is at `MEMORY.md` in that directory.

### Memory file format

```markdown
---
name: short name
description: one-line description (used for relevance matching)
type: user | feedback | project | reference
---

Memory content here.
```

!!! tip "What to save"
    Save non-obvious decisions, recurring corrections, and context that won't be derivable from the code. Do not save code patterns, git history, or anything already in CLAUDE.md.

---

## 10. Developer Commands

Quick reference for the most common tasks.

| Command | What it does |
|---------|-------------|
| `just bootstrap` / `uv sync --all-extras` | Install all deps + pre-commit hooks |
| `poe lint` | Pre-commit hooks: ruff check+format, mypy, commitizen |
| `poe test:unit` | `pytest -vv tests/unit/` |
| `poe test:e2e` | Playwright E2E (auto-installs Chromium) |
| `poe test` | Unit + E2E sequence |
| `just test-cov` | Unit tests with 80% coverage gate |
| `just type-check` | mypy + pyright |
| `just qa` | Full quality suite: lint + type-check + audit + test-cov |
| `just build` | Build wheel + sdist |
| `poe docs:serve` | MkDocs live-reload at `localhost:8080` |
| `just release` | Commitizen bump + push tags (requires clean state + release branch) |
| `poe deps:bump` | Upgrade lock file, verify across 3 Python/resolution combos |
| `just run-erp` | Run ERP example app on port 8001 |
| `just run-simple` | Run simple example app on port 8002 |

---

## 11. The 8-Agent OSS Workflow

HyperAdmin runs a fully specified 8-agent development pipeline, orchestrated entirely through GitHub's native event system (labels, sub-issues, milestones, Projects V2).

```
Human → Deep Research → Roadmap Planning → Workload Queue → Dev Agents
                                                              ↓
                         Release ← QA ← Code Review ← Dev Agents
                            ↓
                     Project Memory → Scheduled Agent
                                    → Community Ingestion
```

| # | Agent | Model tier | Role |
|---|-------|-----------|------|
| 1 | Deep Research | High-Reasoning (Opus) | Iterative Q&A to clarify ideas, outputs structured spec |
| 2 | Roadmap Planning | High-Reasoning | Decomposes spec into Milestone → Epic → Task hierarchy, dependency DAG |
| 3 | Dev Agents | Tiered (Gemini/Jules/Claude) | Parallel TDD implementation — Gemini for S, Jules for M, Claude for L |
| 4 | Code Review | Production (Sonnet) | Correctness, style, backward compat, coverage, security — structured audit trail |
| 5 | QA | Production | Compatibility matrix (Python 3.10–3.13, ubuntu+macos), unit+E2E+type+dep-audit |
| 6 | Release | Production | RC → human approval → version bump → PyPI → docs rebuild |
| 7 | Scheduled | Utility/Production | Weekly: dep staleness, compatibility freshness, tech debt scan, community health |
| 8 | Community Ingestion | Production | Triage issues/discussions/PRs — classify, label, escalate |

Label-based state machine: `idea → researched → planned → approved → in-progress → review → qa-passed → released`

For the full specification, see [Overview](index.md) and the individual agent docs linked in the nav.

---

## 12. Setting Up Your Own Agentic CLI

Use this checklist to replicate HyperAdmin's agentic setup in your own project. Each item links to the HyperAdmin reference implementation.

- [ ] **`CLAUDE.md`** at repo root — primary entry point for Claude Code; include dev commands, hook-first rule, and key file index
- [ ] **`CONSTITUTION.md`** — architectural laws with explicit violation definitions (not just guidelines)
- [ ] **`AGENTS.md`** — agent review checklists and planning rules; duplicate critical rules from CLAUDE.md so agents only need one file
- [ ] **`.claude/rules/`** with at minimum:
    - `code-style.md` (scoped to `src/**/*.py`)
    - `git-workflow.md` (global)
    - `testing.md` (scoped to `tests/**`)
    - `planning-playbook.md` (global — bottom-up ordering prevents top-down structural debt)
- [ ] **`.claude/commands/`** — slash commands for your most common multi-step workflows (lint, test, release, scaffold)
- [ ] **`.claude/skills/`** — full agentic loops; separate "light" (fix-issue) and "heavy" (implement-feature with self-eval gates) paths
- [ ] **`.claude/agents/`** — headless sub-agents for specialized roles; assign the lightest model that handles the task (haiku for review/coordination, sonnet for code)
- [ ] **`.claude/settings.json`** — PostToolUse hooks for auto-formatting and CI triggers
- [ ] **`.claude/settings.local.json`** — permission allowlist to eliminate confirmation prompts for routine commands
- [ ] **`.mcp.json`** — MCP server integrations (Slack, Linear, etc.); set `defaultModel`
- [ ] **`.claude/agent-memory/<agent-name>/`** — persistent memory directories per headless agent
- [ ] *(Optional)* **`GEMINI.md`** and **`JULES.md`** — instruction files for other agent runtimes if using a multi-agent dispatch strategy
- [ ] *(Optional)* **UserPromptSubmit hook** — for injecting external rule context before every prompt (see `.claude/hooks/fetch-rules.sh` as reference)
- [ ] *(Optional)* **`docs/agentic-workflow/`** — full workflow specs; valuable for onboarding humans and keeping orchestration decisions documented

!!! tip "Start small"
    You don't need all 12 items on day one. A `CLAUDE.md` + two rules (`code-style.md`, `git-workflow.md`) + a `/lint` command covers 80% of the value. Add skills, agents, and hooks as workflows repeat.
