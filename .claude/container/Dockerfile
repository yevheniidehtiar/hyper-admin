# Claude Code Remote Environment — YOLO mode
#
# Safe to run with --dangerously-skip-permissions because:
# - Network is locked to a whitelist by init-firewall.sh
# - Container has its own copy of the repo (no host volume mount)
#
# Usage:
#   just cc-local                              # interactive YOLO TUI
#   just cc-run "fix the lint errors"          # headless task
#   just cc-up                                 # remote-control server

FROM node:20-bookworm

# ── System packages (single apt layer) ────────────────────────────────────────
# gosu is included here so there is no second apt-get run later.
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
    # Firewall + privilege drop
    iptables \
    gosu \
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

# ── Non-root user ──────────────────────────────────────────────────────────────
# The ENTRYPOINT must run as root to apply iptables rules.
# gosu in init-firewall.sh drops to 'claude' before exec'ing the CMD,
# making claude the effective user for every process (remote-control, bash…).
RUN useradd -m -s /bin/bash claude

# ── uv (fast Python package manager) ──────────────────────────────────────────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ── Claude Code ────────────────────────────────────────────────────────────────
RUN npm install -g @anthropic-ai/claude-code

# ── Firewall entrypoint ────────────────────────────────────────────────────────
# Copied explicitly so a firewall-only change doesn't bust the dep-install cache.
COPY .claude/container/scripts/init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh

# ── Git identity for Claude Code commits ───────────────────────────────────────
RUN git config --global user.name "Claude Code" \
    && git config --global user.email "noreply+claude-code@anthropic.com" \
    && su claude -c "git config --global user.name 'Claude Code'" \
    && su claude -c "git config --global user.email 'noreply+claude-code@anthropic.com'"

# ── Runtime environment ────────────────────────────────────────────────────────
# /opt/venv is outside /app so a future volume mount cannot shadow it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    DISABLE_AUTOUPDATER=1 \
    CLAUDE_CONFIG_DIR=/home/claude/.claude

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
RUN git config --global --add safe.directory /app \
    && uv run pre-commit install --install-hooks || true \
    && chown -R claude:claude /app /opt/venv

# ── Entrypoint ─────────────────────────────────────────────────────────────────
# Runs as root to apply iptables, then gosu drops to claude.
ENTRYPOINT ["/usr/local/bin/init-firewall.sh"]
# Default: remote-control server (requires prior `just cc-login`)
# Override: `just cc-local` → interactive YOLO TUI
#           `just cc-shell` → bash
CMD ["claude", "remote-control", "--permission-mode", "bypassPermissions"]
