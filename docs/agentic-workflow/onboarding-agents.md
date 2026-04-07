# Onboarding for Agents

Structured reference for LLM agents operating in this repository. Read top-to-bottom on first session.

---

## 1. Reading Order

| Priority | File | Purpose |
|----------|------|---------|
| **Must** | `CLAUDE.md` | Project-wide instructions, hook-first rule, dev commands |
| **Must** | `CONSTITUTION.md` | Architecture boundaries, module structure, violation definitions |
| **Must** | `AGENTS.md` | Software Architect review checklist, hook-first planning rules |
| **Must** | `.claude/project-config.md` | Runtime constants, GitPM (.meta/) reference, status state machine |
| **Must** | `.meta/` | Git-native project state: stories, epics, milestones, roadmap |
| **Reference** | `ROADMAP.md` | Current phase, reserved Phase 3 domains |
| **Reference** | `docs/agentic-workflow/` | Full workflow spec |

---

## 2. Agents

| Agent | Model | Tools | Role |
|-------|-------|-------|------|
| `conductor` | Opus | Bash, Read, Grep, Glob, Agent, EnterWorktree, ExitWorktree, Tasks, Write | Reads `.meta/` work queue, dispatches agents, owns merge queue |
| `delivery-manager` | Haiku | Cron, Bash, Skill, Tasks, Worktree, Read, Edit, Write | PR monitoring, E2E tests, merge execution, updates `.meta/` on merge |
| `project-manager` | Sonnet | Bash, Read, Grep, Glob, Write, Agent | Sprint cadence via `.meta/`, priority triage, health |
| `hyper-admin-code-reviewer` | Sonnet | Bash, Read, Grep, Write | Architecture review, VERDICT output |
| `oss-triage-auditor` | Sonnet | Bash, Read, Grep, Glob, Write | AI-slop detection, label enforcement |

**Dispatch chain:** conductor → implement-feature skill → code-reviewer agent → delivery-manager

---

## 3. Skills

| Skill | Path | Purpose | Invoked by |
|-------|------|---------|------------|
| `implement-feature` | `.claude/skills/implement-feature/SKILL.md` | Self-evaluating TDD loop with planning gate, blocker protocol, memory | conductor |
| `fix-issue` | `.claude/skills/fix-issue/SKILL.md` | Lightweight TDD bug fix loop | conductor |

**implement-feature phases:**

- **A (Planning)**: Read issue → bottom-up plan → self-eval against 16+ checklist items → PASS → proceed; FAIL → post questionnaire, HALT
- **B (Implementation)**: TDD per sub-task → blocker protocol (search memory → commit WIP as draft PR → HALT)
- **C (Submission)**: `poe lint` + `poe test` → final checklist → commit + PR → write memory

---

## 4. Commands

| Command | Path | Purpose |
|---------|------|---------|
| `/run-autonomous-team` | `.claude/commands/run-autonomous-team.md` | Invoke conductor for full orchestration cycle |
| `/implement-feature` | `.claude/commands/implement-feature.md` | Redirects to implement-feature skill |
| `/plan-to-issues` | `.claude/commands/plan-to-issues.md` | Create GitHub issues from implementation plan |
| `/plan-to-issues-dry-run` | `.claude/commands/plan-to-issues-dry-run.md` | Preview issues without creating |
| `/plan-roadmap` | `.claude/commands/plan-roadmap.md` | Decompose spec into milestones/epics/tasks |
| `/bootstrap` | `.claude/commands/bootstrap.md` | Set up dev environment from scratch |
| `/lint` | `.claude/commands/lint.md` | Run linter and auto-fix |
| `/test` | `.claude/commands/test.md` | Run test suite with coverage |
| `/release` | `.claude/commands/release.md` | Cut a new release |
| `/refactor` | `.claude/commands/refactor.md` | Structural refactoring |
| `/optimize` | `.claude/commands/optimize.md` | Algorithmic optimization review |
| `/scaffold` | `.claude/commands/scaffold.md` | Generate new module from patterns |
| `/oss-triage-audit` | `.claude/commands/oss-triage-audit.md` | Run triage audit script |

---

## 5. Rules

| Rule | Path | Enforced by |
|------|------|-------------|
| code-style | `.claude/rules/code-style.md` | code-reviewer, implement-feature skill, `poe lint` |
| git-workflow | `.claude/rules/git-workflow.md` | code-reviewer, implement-feature skill, delivery-manager |
| planning-playbook | `.claude/rules/planning-playbook.md` | code-reviewer, implement-feature skill, plan-to-issues |
| testing | `.claude/rules/testing.md` | code-reviewer, implement-feature skill, `poe test` |

---

## 6. Enforcement Matrix

| Rule | Planning Gate | Code Review | CI |
|------|-------------|-------------|-----|
| `CONSTITUTION.md` | Architecture checklist | Module boundaries | — |
| `planning-playbook.md` | Task ordering | Bottom-up check | — |
| `code-style.md` | Type hints, patterns | Style review | `poe lint` |
| `testing.md` | E2E locator plan | Locator enforcement | `poe test` |
| `git-workflow.md` | Commit format plan | Identity + format | pre-commit |

---

## 7. Hooks & Automation

### UserPromptSubmit — `fetch-rules.sh`

Runs before every prompt. Queries Rippletide for coding rules, injects as `[Coding Rules from Rippletide]`. Both `CLAUDE.md` and `AGENTS.md` enforce naming these rules before planning or code generation.

### PostToolUse — `.claude/settings.json`

| Trigger | Action |
|---------|--------|
| `Edit` or `Write` on `*.py` | `uv run ruff format <file>` |
| `TaskUpdate` with `status=completed` | `scripts/redeploy-example.sh` |

### Permission allowlist — `.claude/settings.local.json`

Pre-approved: `uv lock/run/pip`, `poe test:unit/lint`, `git add/push/checkout`, `gh pr/issue/run/label/api`, `docker compose`.

---

## 8. MCP Servers

| Server | URL | Purpose |
|--------|-----|---------|
| Slack | `https://mcp.slack.com/mcp` | Delivery notifications |

Default model: `claude-sonnet-4-6`

---

## 9. Agent Memory

| Agent | Directory |
|-------|-----------|
| `conductor` | `.claude/agent-memory/conductor/` |
| `delivery-manager` | `.claude/agent-memory/delivery-manager/` |
| `hyper-admin-code-reviewer` | `.claude/agent-memory/hyper-admin-code-reviewer/` |

Project-level memory: `~/.claude/projects/.../memory/MEMORY.md`

Memory format:
```markdown
---
name: short name
description: one-line description
type: user | feedback | project | reference
---
Content here.
```

Save: non-obvious decisions, recurring corrections, context not derivable from code.
Do not save: code patterns, git history, anything in CLAUDE.md.

---

## 10. The 5-Agent Workflow

```
Human → Plan (/plan-to-issues) → .meta/ stories → Conductor
                                                      ↓
                     Delivery Manager ← Code Reviewer ← Dev Agents (implement-feature)
                          ↓
                   Merge → .meta/ status: done
```

| Agent | Model | Role |
|-------|-------|------|
| Conductor | Opus | Dispatches dev agents in worktrees, coordinates review, merge queue authority |
| Delivery Manager | Haiku | PR monitoring, E2E tests, merge execution, delivery notifications |
| Project Manager | Sonnet | Sprint cadence, priority triage, staleness cleanup, milestone demos |
| Code Reviewer | Sonnet | 8-section checklist, machine-readable VERDICT output |
| OSS Triage Auditor | Sonnet | AI-slop detection, duplicate detection, label lifecycle enforcement |

Story status machine (`.meta/`): `backlog → todo → in_progress → in_review → done`
PR label machine (GitHub): `review → merge-requested → merge-granted → squash-merged`
