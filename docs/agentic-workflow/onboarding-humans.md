# Onboarding for Humans

## What is the agent system?

HyperAdmin is delivered by an autopilot. A small supervisor script runs every
15 minutes on the maintainer's Mac and starts headless Claude Code jobs that
implement stories, review pull requests, repair CI and integrate finished
epics. See [Orchestration](orchestration.md) for the full design.

Work is planned as stories in `.meta/`. Each epic gets its own branch,
`epic/<slug>`. Story PRs merge into that branch without a human. When the epic
is complete it lands on `develop` as one pull request, and that is the one the
maintainer approves.

You can still drive a single story by hand with `/implement-feature` or
`/fix-issue` in Claude Code.

## What the owner does

| Task | How often |
|------|-----------|
| Approve the epic PR (`epic/<slug>` → `develop`). It merges on approval. | Once per epic |
| Approve a `fix-develop` PR or a green Dependabot PR | Rare |
| Answer questions on issues labelled `needs-human` | Rare |
| Read the daily digest (Slack, or the standing autopilot issue) | Daily |
| Say go on the first janitor cleanup list | Once |
| Cut a release: `develop` → `master`, PyPI | Per release |

Agents escalate with `needs-human` only for secrets or billing, the public
mirror, deleting data, PyPI releases, breaking public API, runtime dependency
floors and data-model migrations, or when a PR has used up its retry budget.
For everything else they pick the most reversible option and list it under
`## Assumptions` in the PR body, where you can overrule it during review.

## Bootstrap from Zero

If you're starting on a fresh machine, CI runner, or cloud VM:

### 1. Install `uv` (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
uv --version
```

### 2. Ensure Python 3.11+

```bash
uv python install 3.11
uv run python --version
```

### 3. Sync dependencies

```bash
uv sync --all-extras
```

This also installs `poe` (Poe the Poet), the task runner used throughout the
project. Run tasks as `uv run poe <task>`, or `poe <task>` in the activated
virtual environment.

### 4. Pre-commit hooks

```bash
uv run pre-commit install
```

> **Worktree note**: If you see "Cowardly refusing to install hooks with core.hooksPath set", hooks are already managed by the parent repo.

### 5. Playwright browser (E2E tests only)

```bash
uv run playwright install chromium --with-deps
```

### 6. Environment variables

| Variable | Purpose | Required for |
|----------|---------|-------------|
| `CLAUDE_GH_TOKEN` | GitHub bot token for PR creation | Opening PRs as the bot account; the autopilot |
| `GITHUB_TOKEN` | General GitHub API access where `gh auth login` is not possible | CI runners and cloud VMs only |

```bash
export CLAUDE_GH_TOKEN="ghp_..."
```

On a workstation, `gh auth login` covers reads and everything done under your
own identity; you do not need `GITHUB_TOKEN`.

If you run the autopilot, put `CLAUDE_GH_TOKEN` in your login shell profile
(`~/.zprofile` or similar): launchd starts the tick through a login shell. Do
not export `GITHUB_TOKEN` there. `gh` prefers it over the keychain login, so
every `gh` call in the tick and its jobs would run as that token.

### 7. Smoke test

```bash
uv run poe --help
uv run python -c "import hyperadmin; print('OK')"
uv run pytest tests/unit/ -q -x
```

Or just run `/bootstrap` in Claude Code — it detects what's missing and installs everything.

## Developer Commands

| Command | What it does |
|---------|-------------|
| `uv sync --all-extras` | Install all deps |
| `poe lint` | Pre-commit hooks: ruff, mypy, commitizen |
| `poe test:unit` | `pytest tests/unit/` |
| `poe test:e2e` | Playwright E2E tests |
| `poe test` | Unit + E2E sequence |
| `poe test:cov-diff` | Coverage of changed lines |
| `poe docs:serve` | Zensical live-reload at `localhost:8080` |
| `poe docs:build` | Build the documentation site |

A `justfile` with a few extra recipes (container tooling, `just release`) is
kept for the maintainer. Contributors do not need `just`.

## Running the Autopilot

Only the maintainer runs it. It needs macOS, a logged-in Claude Code session
(Max subscription, no API key) and `CLAUDE_GH_TOKEN`.

| Command | What it does |
|---------|-------------|
| `poe autopilot:install` | Install and load the launchd agent `com.hyperadmin.autopilot` |
| `poe autopilot:status` | Show whether it is loaded |
| `poe autopilot:logs` | Show tick and job logs |
| `poe autopilot:tick` | Run one tick now |
| `poe autopilot:uninstall` | Stop and remove it |
| `AUTOPILOT_DRY_RUN=1 ops/autopilot/autopilot.sh tick` | Print what a tick would do, change nothing |

First-time setup, in this order:

1. Run `AUTOPILOT_DRY_RUN=1 ops/autopilot/autopilot.sh tick` and read the
   janitor list (stale worktrees and branches it would remove).
2. Say go on that list once and let the cleanup run. It comes before the
   worktree pool exists, because each stale worktree costs a
   `uv sync --all-extras`.
3. `poe autopilot:install`.
4. Check that it is loaded: `launchctl print gui/$UID/com.hyperadmin.autopilot`.
5. Schedule a wake with `pmset` (for example `sudo pmset repeat wakeorpoweron
   MTWRFSU 06:00:00`) so the Mac is awake for the ticks you care about.

State is kept in `~/.hyperadmin-autopilot/state.json`. Jobs run in three reused
worktrees, `.claude/worktrees/ap-1` to `ap-3`. To pause everything, uninstall
the agent; nothing else keeps running.

## How to Contribute

See [Contributing](../contributing.md) for the full guide. Key points:

- Fork → branch from `develop` → make changes → `poe lint && poe test:unit` → PR against `develop`
- Commits use [Conventional Commits](https://www.conventionalcommits.org/)
- PRs merge by rebase, so keep every commit clean
- `epic/<slug>` branches belong to the automation; do not target them unless asked
- An AI reviewer may comment on your PR and label it `ai-approved` or `ai-changes-requested`. A maintainer's review is still required to merge into `develop`.

## Setting Up Your Own Agentic CLI

Use this checklist to replicate HyperAdmin's setup in your own project:

- [ ] **`CLAUDE.md`** — primary entry point with dev commands, hook-first rule, key file index
- [ ] **`CONSTITUTION.md`** — architectural laws with explicit violation definitions
- [ ] **`.claude/rules/`** — at minimum: `code-style.md`, `git-workflow.md`, `testing.md`, `planning-playbook.md`
- [ ] **`.claude/commands/`** — slash commands for common multi-step workflows
- [ ] **`.claude/skills/`** — full agentic loops; separate "light" (fix-issue) and "heavy" (implement-feature) paths
- [ ] **`.claude/agents/`** — headless sub-agents; assign the lightest model that handles the task
- [ ] **`.claude/settings.json`** — PostToolUse hooks for auto-formatting
- [ ] **`.mcp.json`** — MCP server integrations; set `defaultModel`
- [ ] **`ops/autopilot/`** — a supervisor that does the deterministic work (checks, merges, rebases) in a script and starts a model only where judgement is needed

!!! tip "Start small"
    A `CLAUDE.md` + two rules (`code-style.md`, `git-workflow.md`) + a `/lint` command covers 80% of the value. Add skills, agents, hooks and a supervisor as workflows repeat.
