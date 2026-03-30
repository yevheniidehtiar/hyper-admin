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

# Stage host Claude memory into build context (snapshot for container use)
_stage-memory:
    #!/usr/bin/env bash
    set -euo pipefail
    HOST_MEM="$HOME/.claude/projects/$(pwd | tr '/' '-')/memory"
    STAGE=".claude/container/host-memory"
    # Clean previous snapshot but keep .dockerkeep (ensures COPY works on fresh checkouts)
    find "$STAGE" -mindepth 1 ! -name '.dockerkeep' -delete 2>/dev/null || true
    mkdir -p "$STAGE"
    if [ -d "$HOST_MEM" ] && [ "$(ls -A "$HOST_MEM" 2>/dev/null)" ]; then
        cp "$HOST_MEM"/* "$STAGE/" 2>/dev/null || true
        echo "[memory] Staged $(find "$STAGE" -name '*.md' | wc -l | tr -d ' ') files from host memory"
    else
        echo "[memory] No host memory found — staging empty directory"
    fi

# Build the Claude Code remote container image
cc-build: _stage-memory
    {{ _compose }} build

# Start Claude Code remote-control server (requires prior `just cc-login`)
cc-up:
    {{ _compose }} up -d

# Build, rotate deploy key, and start in one step
cc-start: cc-build cc-rotate-key cc-up

# One-time OAuth login for Max subscription
cc-login:
    {{ _compose }} run --rm claude claude login

# One-time GitHub CLI login inside the container
cc-gh-auth:
    {{ _compose }} run --rm claude gh auth login

# Open an interactive shell inside the container
cc-shell:
    {{ _compose }} run --rm claude bash

# Interactive YOLO session in the container (full TUI, no task arg needed)
cc-local:
    {{ _compose }} run --rm claude claude --dangerously-skip-permissions

# Run a headless YOLO task: just cc-run "fix the lint errors"
cc-run task:
    {{ _compose }} run --rm claude claude --dangerously-skip-permissions -p "{{ task }}"

# Rotate SSH deploy key for the container (generates new key, registers with GitHub)
cc-rotate-key repo="yevheniidehtiar/hyper-admin":
    #!/usr/bin/env bash
    set -euo pipefail
    SSH_DIR=".claude/container/ssh"
    KEY_FILE="${SSH_DIR}/id_ed25519"
    TITLE="claude-sandbox-$(date +%Y%m%d)"

    mkdir -p "$SSH_DIR"

    # Remove old deploy key from GitHub if one exists
    if [ -f "${KEY_FILE}.pub" ]; then
        OLD_FP=$(ssh-keygen -lf "${KEY_FILE}.pub" | awk '{print $2}')
        OLD_ID=$(gh repo deploy-key list --repo "{{ repo }}" \
            | grep "$OLD_FP" | awk '{print $1}' || true)
        if [ -n "$OLD_ID" ]; then
            gh repo deploy-key delete "$OLD_ID" --repo "{{ repo }}" --yes
            echo "Removed old deploy key (ID: $OLD_ID)"
        fi
    fi

    # Generate new key
    rm -f "$KEY_FILE" "${KEY_FILE}.pub"
    ssh-keygen -t ed25519 -N "" -C "$TITLE" -f "$KEY_FILE" -q
    chmod 600 "$KEY_FILE"
    chmod 644 "${KEY_FILE}.pub"

    # Write ssh config so git uses this key for github.com
    cat > "${SSH_DIR}/config" <<CFG
    Host github.com
        IdentityFile /root/.ssh/id_ed25519
        UserKnownHostsFile /root/.ssh/known_hosts
        StrictHostKeyChecking accept-new
    CFG
    chmod 644 "${SSH_DIR}/config"

    # Pre-seed known_hosts so the read-only mount works
    ssh-keyscan -t ed25519 github.com > "${SSH_DIR}/known_hosts" 2>/dev/null
    chmod 644 "${SSH_DIR}/known_hosts"

    # Register as read-write deploy key
    gh repo deploy-key add "${KEY_FILE}.pub" \
        --repo "{{ repo }}" --title "$TITLE" --allow-write
    echo "Deploy key rotated: $TITLE"

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
