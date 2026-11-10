---
description: Bootstrap a fresh cloud/isolated environment from zero — install prerequisites, sync deps, verify toolchain
---

You are setting up a **fresh, isolated environment** for HyperAdmin development.
Work through each phase in order. Print a clear status line after every step.
If any step fails, diagnose the root cause and fix it before continuing — do not skip.

---

## Phase 1 — Detect environment

Run these checks and report what you find:

```bash
uname -s          # OS: Linux / Darwin / ...
python3 --version # Python available?
uv --version      # uv available?
git --version     # git available?
```

Summarise the gap: which tools are missing and need to be installed.

---

## Phase 2 — Install missing prerequisites

Install only what is missing. Use the correct method for the detected OS.

### uv (Python package + project manager — required for everything)

```bash
# Linux / macOS (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Then reload PATH:
source $HOME/.local/bin/env 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
```

Verify: `uv --version` must print a version string.

### poe (task runner)

Nothing to install: `poethepoet` is a dev dependency and comes with `uv sync --all-extras` in
Phase 3. Run tasks as `uv run poe <task>`.

### Python 3.11+ (uv manages its own Python, but verify the minimum)

```bash
uv python install 3.11   # installs a managed Python if none found
```

Verify: `uv run python --version` reports 3.11 or higher.

### git (should be pre-installed; install if missing)

```bash
# Debian/Ubuntu
apt-get install -y git

# macOS
xcode-select --install
```

---

## Phase 3 — Sync project dependencies

```bash
uv sync --all-extras
```

This installs all runtime + dev + extras into `.venv/`. Expected output: `Installed N packages`.

If this fails:
- Check that `pyproject.toml` exists in the current directory.
- Check Python version compatibility: HyperAdmin requires Python >=3.11.

---

## Phase 4 — Install pre-commit hooks

```bash
uv run pre-commit install
```

> **Worktree note**: If you see `Cowardly refusing to install hooks with core.hooksPath set`,
> this means hooks are already managed by the parent repo. This is expected and safe to ignore —
> the hooks are already active. Continue to Phase 5.

---

## Phase 5 — Install Playwright browser (required for E2E tests)

```bash
uv run playwright install chromium --with-deps
```

This downloads the Chromium binary used by `poe test:e2e`. On a headless server,
`--with-deps` installs the system-level libraries Chromium needs.

Verify: `uv run playwright --version` prints a version string.

---

## Phase 6 — Verify required environment variables

Check which of these are set. Print their presence (not their values):

| Variable | Purpose | Required for |
|----------|---------|-------------|
| `CLAUDE_GH_TOKEN` | GitHub bot token for PR creation | Creating PRs as the bot account |
| `GITHUB_TOKEN` | General GitHub API access | `gh` CLI, issue/label operations |
| `ANTHROPIC_API_KEY` | Claude API access | Any agent that calls Claude directly |

```bash
for var in CLAUDE_GH_TOKEN GITHUB_TOKEN ANTHROPIC_API_KEY; do
  if [ -n "${!var}" ]; then echo "$var: SET"; else echo "$var: MISSING"; fi
done
```

For any missing variable that is needed for the planned work, instruct the user on how to set it:

```bash
export CLAUDE_GH_TOKEN="ghp_..."     # add to ~/.zshrc / ~/.bashrc for persistence
export GITHUB_TOKEN="ghp_..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Phase 7 — Smoke test the toolchain

Run the following in order and report pass/fail for each:

```bash
uv run poe --help                    # task runner works, lists all tasks
uv run python -c "import hyperadmin; print('import OK')"   # package importable
uv run ruff check src --quiet        # linter works
uv run mypy src --quiet              # type checker works (warnings OK, errors not)
uv run pytest tests/unit/ -q --tb=short -x   # unit tests pass
```

If all pass, print:

```
✓ Environment is fully operational.
  - uv: <version>
  - poe: <version>
  - Python: <version>
  - Playwright: <version>
  Run `uv run poe --help` to see all available tasks.
```

If any step fails, show the error output and suggest the fix before stopping.
