# Onboarding for Humans

## What is the agent system?

HyperAdmin uses a 5-agent Claude Code workflow to automate development. Agents handle implementation, code review, merge coordination, project management, and community triage — all orchestrated through GitHub labels and issues.

You interact with the system via Claude Code slash commands (`/implement-feature`, `/run-autonomous-team`), and agents work autonomously within safety rails (max 3 dev agents per cycle, human approval gates).

## Bootstrap from Zero

If you're starting on a fresh machine, CI runner, or cloud VM:

### 1. Install `uv` (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
uv --version
```

### 2. Install `just` (task runner)

```bash
# macOS
brew install just

# Linux
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin
```

### 3. Ensure Python 3.10+

```bash
uv python install 3.10
uv run python --version
```

### 4. Sync dependencies

```bash
uv sync --all-extras
```

### 5. Pre-commit hooks

```bash
uv run pre-commit install
```

> **Worktree note**: If you see "Cowardly refusing to install hooks with core.hooksPath set", hooks are already managed by the parent repo.

### 6. Playwright browser (E2E tests only)

```bash
uv run playwright install chromium --with-deps
```

### 7. Environment variables

| Variable | Purpose | Required for |
|----------|---------|-------------|
| `CLAUDE_GH_TOKEN` | GitHub bot token for PR creation | Creating PRs as Claude Code identity |
| `GITHUB_TOKEN` | General GitHub API access | `gh` CLI, issues, labels |

```bash
export CLAUDE_GH_TOKEN="ghp_..."
export GITHUB_TOKEN="ghp_..."
```

### 8. Smoke test

```bash
just --list
uv run python -c "import hyperadmin; print('OK')"
uv run pytest tests/unit/ -q -x
```

Or just run `/bootstrap` in Claude Code — it detects what's missing and installs everything.

## Developer Commands

| Command | What it does |
|---------|-------------|
| `just bootstrap` | Install all deps + pre-commit hooks |
| `poe lint` | Pre-commit hooks: ruff, mypy, commitizen |
| `poe test:unit` | `pytest tests/unit/` |
| `poe test:e2e` | Playwright E2E tests |
| `poe test` | Unit + E2E sequence |
| `just qa` | Full quality suite: lint + type-check + audit + test-cov |
| `poe docs:serve` | MkDocs live-reload at `localhost:8080` |
| `just release` | Commitizen bump + push tags |

## How to Contribute

See [Contributing](../contributing.md) for the full guide. Key points:

- Fork → branch → make changes → `just lint && just test` → PR against `develop`
- Commits use [Conventional Commits](https://www.conventionalcommits.org/)
- The label system tracks issue state: `idea → approved → in-progress → review → released`
- Agents may review your PR automatically — look for `VERDICT:` comments

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
- [ ] **`.claude/agent-memory/`** — persistent memory directories per agent

!!! tip "Start small"
    A `CLAUDE.md` + two rules (`code-style.md`, `git-workflow.md`) + a `/lint` command covers 80% of the value. Add skills, agents, and hooks as workflows repeat.
