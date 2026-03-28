# HyperAdmin — justfile
set shell := ["bash", "-cu"]
set dotenv-load := true

# List available recipes
default:
    @just --list

# ── Setup ─────────────────────────────────────────────────────

# Bootstrap development environment (.venv + pre-commit)
bootstrap:
    uv sync --all-extras
    uv run pre-commit install
    @echo "✓ Environment ready"

setup: bootstrap

# ── Quality ───────────────────────────────────────────────────

# Run linter and formatter
lint:
    uv run ruff check . --fix
    uv run ruff format .

# Alias for lint
fmt: lint

# Run type checkers (mypy + pyright)
type-check:
    uv run mypy src
    uv run pyright src

# Run security audits
audit:
    uv run pip-audit
    uv run safety check

# Check code complexity
complexity:
    uv run radon cc src -n C

# Run full quality suite
qa: lint type-check audit test-cov
    @echo "✓ Project is healthy"

# Run tests
test:
    uv run poe test:unit

# Run tests with coverage (fail under 80%)
test-cov:
    uv run pytest --tb=short --cov=src/hyperadmin --cov-report=term-missing --cov-fail-under=80

# Run e2e tests
test-e2e:
    uv run poe test:e2e

# ── Build ─────────────────────────────────────────────────────

# Build distribution packages (wheel + sdist)
build:
    uv build

# ── Docker ────────────────────────────────────────────────────


# ── Claude Code ───────────────────────────────────────────────

_compose := "docker compose -f .claude/container/docker-compose.yml"

# Build the Claude Code remote container image
cc-build:
    {{ _compose }} build

# Start Claude Code remote-control server (requires prior `just cc-login`)
cc-up:
    {{ _compose }} up

# Build and start in one step
cc-start: cc-build cc-up

# One-time OAuth login for Max subscription
cc-login:
    {{ _compose }} run --rm claude claude login

# Open an interactive shell inside the container
cc-shell:
    {{ _compose }} run --rm claude bash

# Interactive YOLO session in the container (full TUI, no task arg needed)
cc-local:
    {{ _compose }} run --rm claude claude --dangerously-skip-permissions

# Run a headless YOLO task: just cc-run "fix the lint errors"
cc-run task:
    {{ _compose }} run --rm claude claude --dangerously-skip-permissions -p "{{ task }}"

# Run container security tests
cc-test:
    UV_PROJECT_ENVIRONMENT=.venv uv run pytest .claude/container/tests/test_container_security.py -v

# ── Docs ──────────────────────────────────────────────────────

# Serve documentation locally
docs:
    uv run mkdocs serve

# Deploy documentation to GitHub Pages
docs-deploy:
    uv run mkdocs gh-deploy --force


# ── Release ───────────────────────────────────────────────────

# Create a new release using commitizen (automated semver)
release:
    #!/usr/bin/env bash
    if [ -n "$(git status --porcelain)" ]; then
        echo "❌ Working directory is not clean. Commit or stash changes first."
        exit 1
    fi
    CURRENT_BRANCH=$(git branch --show-current)
    if [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "develop" ]; then
        echo "❌ Not on release branch (main or develop). Current: $CURRENT_BRANCH"
        exit 1
    fi
    echo "==> Bumping version and generating changelog..."
    uv run cz bump --changelog
    echo "==> Pushing changes and tags..."
    git push origin "$CURRENT_BRANCH" --tags
    echo "✓ Release successful"

# ── Infrastructure ────────────────────────────────────────────

# Configure GitHub labels for the 8-agent workflow
setup-github repo="":
    bash scripts/setup-github.sh {{ repo }}


# Harden repository security and branch rules
secure repo="":
    bash scripts/secure-repo.sh {{ repo }}

# -- Local dev -------------────────────────────────────────────

# Run erp example
run-erp:
    uv run uvicorn examples.erp.main:app --log-level debug --reload --port 8001

run-simple:
    uv run uvicorn examples.simple.main:app --log-level debug --reload --port 8002

# ── Utils ─────────────────────────────────────────────────────

# Remove build artifacts and caches
clean:
    #!/usr/bin/env bash
    rm -rf dist/ site/ .pytest_cache/ __pycache__/ *.egg-info/ .ruff_cache/ .mypy_cache/ .pyright_cache/
    find . -type d -name "__pycache__" -exec rm -rf {} +
    @echo "✓ Cleaned"
