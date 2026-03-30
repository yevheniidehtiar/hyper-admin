# Claude Code Remote Environment — YOLO mode
#
# Safe to run with --dangerously-skip-permissions because:
# - Network is locked to a whitelist by init-firewall.sh
# - Container has its own copy of the repo (no host volume mount)
# - IS_SANDBOX=1 tells Claude Code this is a sandboxed environment
#
# Usage:
#   just cc-local                              # interactive YOLO TUI
#   just cc-run "fix the lint errors"          # headless task
#   just cc-up                                 # remote-control server

FROM node:20-bookworm

# ── System packages (single apt layer) ────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Version control & CLI
    git \
    curl \
    wget \
    unzip \
    # Code search (used by Claude Code)
    ripgrep \
    # Build toolchain (needed by some Python extensions)
    build-essential \
    # Firewall
    iptables \
    # Python runtime
    python3 \
    python3-dev \
    python3-venv \
    # Playwright browser dependencies
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# ── GitHub CLI ─────────────────────────────────────────────────────────────────
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# ── uv (fast Python package manager) ──────────────────────────────────────────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ── Claude Code ────────────────────────────────────────────────────────────────
RUN npm install -g @anthropic-ai/claude-code

# ── Firewall entrypoint ────────────────────────────────────────────────────────
# Copied explicitly so a firewall-only change doesn't bust the dep-install cache.
COPY .claude/container/scripts/init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh

# ── Memory snapshot from host ──────────────────────────────────────────────────
# Staged by `just cc-build` (_stage-memory recipe) before docker build.
# init-memory.sh syncs these into the named volume at container start.
COPY .claude/container/host-memory/ /image-memory/
COPY .claude/container/scripts/init-memory.sh /usr/local/bin/init-memory.sh
RUN chmod +x /usr/local/bin/init-memory.sh

# ── Git identity for Claude Code commits ───────────────────────────────────────
RUN git config --global user.name "Claude Code" \
    && git config --global user.email "noreply+claude-code@anthropic.com"

# ── Runtime environment ────────────────────────────────────────────────────────
# IS_SANDBOX=1 tells Claude Code it is running inside a sandbox, allowing
# --dangerously-skip-permissions to work as root (upstream issue #3490).
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    DISABLE_AUTOUPDATER=1 \
    CLAUDE_CONFIG_DIR=/root/.claude \
    IS_SANDBOX=1

# ── Python dependencies ────────────────────────────────────────────────────────
# Copy only the files hatchling needs to build + resolve deps.
# This layer is cached until pyproject.toml or uv.lock changes.
WORKDIR /app
COPY pyproject.toml uv.lock* README.md ./
COPY src/ ./src/
RUN uv sync --all-extras --frozen

# ── Playwright browsers ────────────────────────────────────────────────────────
# Depends only on /opt/venv — runs before the full COPY so source changes
# don't bust this slow (~200 MB) download.
RUN /opt/venv/bin/python -m playwright install chromium

# ── Full project copy (last heavy layer) ──────────────────────────────────────
# Everything above is cached. Only layers below re-run on source changes.
COPY . .

# ── Post-copy setup ────────────────────────────────────────────────────────────
# pre-commit install: regenerates .git/hooks/ with container python path
#   (the COPY above brings host hooks with hardcoded host paths — must overwrite)
# pre-commit install-hooks: downloads hook environments (best-effort, needs network)
RUN git config --global --add safe.directory /app \
    && uv run pre-commit install \
    && uv run pre-commit install --hook-type commit-msg \
    && (uv run pre-commit install-hooks || true)

# ── Entrypoint ─────────────────────────────────────────────────────────────────
# Applies iptables firewall, then exec's the CMD.
ENTRYPOINT ["/usr/local/bin/init-firewall.sh"]
# Default: remote-control server (requires prior `just cc-login`)
# Override: `just cc-local` → interactive YOLO TUI
#           `just cc-shell` → bash
CMD ["claude", "remote-control", "--permission-mode", "bypassPermissions", "--name", "macbook", "--spawn", "worktree", "--verbose", "--capacity", "8"]
