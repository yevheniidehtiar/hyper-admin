# Onboarding for Agents

Structured reference for LLM agents operating in this repository. Read top-to-bottom on first session.

---

## 1. Reading Order

| Priority | File | Purpose |
|----------|------|---------|
| **Must** | `CLAUDE.md` | Project-wide instructions, hook-first rule, dev commands |
| **Must** | `CONSTITUTION.md` | Architecture boundaries, module structure, violation definitions |
| **Must** | `AGENTS.md` | Hook-first planning rules; points at the software-architect agent |
| **Must** | `.claude/project-config.md` | Runtime constants, GitPM (.meta/) reference, branch-as-lock, status and label machines |
| **Must** | `.meta/` | Git-native project state: stories, epics, milestones, roadmap |
| **Reference** | `ops/autopilot/README.md` | How the local supervisor runs jobs |
| **Reference** | `docs/agentic-workflow/` | Full workflow spec, start with `orchestration.md` |

---

## 2. Agents

| Agent | Model | Role | Started by |
|-------|-------|------|------------|
| `software-architect` | Opus | Spec gate: reviews a Draft SDD, resolves open questions, approves it | `approve-sdd` job |
| `hyper-admin-code-reviewer` | Sonnet | Architecture review; JSON verdict, sets `ai-approved` or `ai-changes-requested` | `review` job |
| `project-manager` | Haiku | Daily owner digest template | `digest` job |
| `oss-triage-auditor` | Sonnet | AI-slop detection, label enforcement | Ad hoc |

There is no conductor and no delivery-manager. Dispatch, merging, rebasing and
cleanup are done by the supervisor script `ops/autopilot/autopilot.sh`, not by
an agent.

**Chain:** tick → `implement` (implement-feature skill) → `review` (code reviewer) → `fix-pr` if needed → tick merges into `epic/<slug>` → `integrate-epic` → owner approves the epic PR

---

## 3. Skills

| Skill | Path | Purpose | Invoked by |
|-------|------|---------|------------|
| `implement-feature` | `.claude/skills/implement-feature/SKILL.md` | TDD loop with planning gate and decision ladder | `implement` job, or by hand |
| `fix-issue` | `.claude/skills/fix-issue/SKILL.md` | Lightweight TDD bug fix loop | By hand, or for `size:S` stories |

Both take a base-branch argument (`epic/<slug>` for stories in an epic,
`develop` otherwise).

**implement-feature phases:**

- **A (Planning)**: Read story → bottom-up plan → self-eval against the checklist → on a failed check, resolve it with the decision ladder and continue
- **B (Implementation)**: TDD per sub-task → blockers go through the same ladder
- **C (Submission)**: `poe lint` + `poe test:unit` → final checklist → commit + PR with `Story:` line and `## Assumptions` → write memory

There is no monitoring phase. The tick watches the PR.

---

## 4. If you are an autopilot job

You were started by `ops/autopilot/autopilot.sh` with `AUTOPILOT=1` set, in one
of the pool worktrees `.claude/worktrees/ap-1..3`. Your prompt came from
`ops/autopilot/prompts/<job>.md`.

- Nobody is at the keyboard. Do not ask questions and do not wait.
- Stay inside your worktree and your branch.
- You have a tool allowlist. A denied call is a signal that the action is out of
  scope, not something to work around.
- Do the one job you were given, then exit. The next tick decides what follows.
- Do not edit `.meta` status in a story PR. Only the open-epic and close-epic
  commits change it.
- Never run a GitPM push. Sync happens in CI.

### Decision ladder

When something is unclear:

1. Project memory (`MEMORY.md`).
2. The story, the SDD, `CONSTITUTION.md`, the existing code.
3. A research subagent.
4. Choose the most reversible option that satisfies the constitution. Write it
   under `## Assumptions` in the PR body and in the SDD Decision Log. Continue.

### Hard stops

Label the issue `needs-human`, post the exact question, end the job:

- Secrets or billing
- Pushing to the public mirror
- Deleting data
- A PyPI release
- Breaking public API (`__init__` exports, semver major)
- Changing runtime dependency floors
- Data-model migrations

---

## 5. Commands

| Command | Path | Purpose |
|---------|------|---------|
| `/autopilot-tick` | `.claude/commands/autopilot-tick.md` | Run one tick interactively, for debugging |
| `/implement-feature` | `.claude/skills/implement-feature/SKILL.md` | Implement one story by hand |
| `/wt` | `.claude/commands/wt.md` | New isolated worktree; optional base branch |
| `/plan-to-issues` | `.claude/commands/plan-to-issues.md` | Create `.meta/` stories from an implementation plan |
| `/plan-roadmap` | `.claude/commands/plan-roadmap.md` | Decompose spec into milestones/epics/tasks |
| `/bootstrap` | `.claude/commands/bootstrap.md` | Set up dev environment from scratch |
| `/lint` | `.claude/commands/lint.md` | Run linter and auto-fix |
| `/test` | `.claude/commands/test.md` | Run test suite with coverage |
| `/release` | `.claude/commands/release.md` | Cut a new release (owner only) |
| `/refactor` | `.claude/commands/refactor.md` | Structural refactoring |
| `/optimize` | `.claude/commands/optimize.md` | Algorithmic optimization review |
| `/scaffold` | `.claude/commands/scaffold.md` | Generate new module from patterns |
| `/oss-triage-audit` | `.claude/commands/oss-triage-audit.md` | Run triage audit script |

---

## 6. Rules

| Rule | Path | Enforced by |
|------|------|-------------|
| code-style | `.claude/rules/code-style.md` | code-reviewer, implement-feature skill, `poe lint` |
| git-workflow | `.claude/rules/git-workflow.md` | code-reviewer, implement-feature skill, pre-commit |
| planning-playbook | `.claude/rules/planning-playbook.md` | code-reviewer, implement-feature skill, plan-to-issues |
| testing | `.claude/rules/testing.md` | code-reviewer, implement-feature skill, `poe test` |
| conflict-avoidance | `.claude/rules/conflict-avoidance.md` | tick (overlap check), code-reviewer |
| sdd-conventions | `.claude/rules/sdd-conventions.md` | software-architect |
| bdd-conventions | `.claude/rules/bdd-conventions.md` | implement-feature skill, code-reviewer |

---

## 7. Enforcement Matrix

| Rule | Planning Gate | Code Review | CI |
|------|-------------|-------------|-----|
| `CONSTITUTION.md` | Architecture checklist | Module boundaries | — |
| `planning-playbook.md` | Task ordering | Bottom-up check | — |
| `code-style.md` | Type hints, patterns | Style review | `poe lint` |
| `testing.md` | E2E locator plan | Locator enforcement | `poe test` |
| `git-workflow.md` | Commit format plan | Identity + format | pre-commit |
| `sdd-conventions.md` | Spec gate (architect) | SDD matches the code | — |

---

## 8. Hooks & Automation

### UserPromptSubmit — `fetch-rules.sh`

Runs before every prompt. Queries Rippletide for coding rules, injects as `[Coding Rules from Rippletide]`. Both `CLAUDE.md` and `AGENTS.md` enforce naming these rules before planning or code generation.

### PostToolUse — `.claude/settings.json`

| Trigger | Action |
|---------|--------|
| `Edit` or `Write` on `*.py` | `uv run ruff format <file>` |
| `TaskUpdate` with `status=completed` | `scripts/redeploy-example.sh` (skipped when `AUTOPILOT=1`) |

### Permissions

Interactive sessions use the allowlist in `.claude/settings.local.json`.
Autopilot jobs get their allowlist on the command line from the supervisor:
`git`, `gh pr|api|run|issue`, `uv run`, `scripts/gitpm.sh` and the file tools.
`gh release`, `gh repo` and pushes to the public mirror are denied.

---

## 9. MCP Servers

| Server | URL | Purpose |
|--------|-----|---------|
| Slack | `https://mcp.slack.com/mcp` | Delivery notifications |

Default model: `claude-sonnet-4-6`

---

## 10. Memory and State

| What | Where |
|------|-------|
| Project memory | `~/.claude/projects/.../memory/MEMORY.md` |
| Autopilot state (cooldown, running jobs, retry counters) | `~/.hyperadmin-autopilot/state.json` |

Agents read and write project memory. Only the supervisor writes the state file.

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

## 11. The Workflow at a Glance

```
Owner → Plan (/plan-to-issues) → .meta/ stories
                                      ↓
        tick: create epic/<slug> + draft epic PR
                                      ↓
        approve-sdd → implement → review → (fix-pr) → tick merges into epic/<slug>
                                      ↓
        integrate-epic → owner approves the epic PR → develop → GitPM Sync
```

Story status machine (`.meta/`): `backlog → todo → in_progress → in_review → done`.
On the epic branch only two commits touch it: open epic and close epic.

Story PR labels: `ai-approved | ai-changes-requested | needs-human`

Story issue labels (written by the tick): `ap:in-progress → ap:in-review → ap:done`
