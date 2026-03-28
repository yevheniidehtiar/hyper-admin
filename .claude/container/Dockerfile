# Claude Code Remote Environment — YOLO mode
#
# Safe to run with --dangerously-skip-permissions because:
# - Network is locked to a whitelist by init-firewall.sh
# - Container is isolated from host filesystem (except /app mount)
#
# Usage:
#   docker compose run claude                          # interactive session
#   docker compose run claude claude \
#     --dangerously-skip-permissions -p "your task"   # headless task

FROM node:20-bookworm

# ── System packages ────────────────────────────────────────────────────────────
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

# ── Python venv location ───────────────────────────────────────────────────────
# /opt/venv is OUTSIDE /app, so the host volume mount does not override it.
# This must be set before `uv sync` so it builds to the right path.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# ── Project dependencies ───────────────────────────────────────────────────────
WORKDIR /app

# Copy manifests + files required by hatchling to build the package
COPY pyproject.toml uv.lock* README.md ./
COPY src/ ./src/

# Install all Python deps (including dev/test/e2e extras) into /opt/venv
RUN uv sync --all-extras --frozen

# Copy the rest of the project (tests, examples, .claude/, scripts/, etc.)
COPY . .

# Install Playwright browsers using the venv python directly.
RUN /opt/venv/bin/python -m playwright install chromium

# Install pre-commit hooks
RUN git config --global --add safe.directory /app \
    && uv run pre-commit install --install-hooks || true

# ── Non-root user (required: bypassPermissions is blocked for root) ────────────
# The ENTRYPOINT (init-firewall.sh) must run as root to apply iptables rules,
# so USER is not set here. Instead, gosu drops to 'claude' at the end of
# init-firewall.sh before exec'ing the CMD — making claude the effective user
# for every process (remote-control, bash, etc).
RUN apt-get update && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash claude \
    && chown -R claude:claude /app /opt/venv

# ── Firewall ───────────────────────────────────────────────────────────────────
COPY .claude/container/scripts/init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh

# ── Git identity for Claude Code commits ───────────────────────────────────────
RUN git config --global user.name "Claude Code" \
    && git config --global user.email "noreply+claude-code@anthropic.com"
RUN su claude -c "git config --global user.name 'Claude Code'" \
    && su claude -c "git config --global user.email 'noreply+claude-code@anthropic.com'"

# ── Runtime environment ────────────────────────────────────────────────────────
ENV DISABLE_AUTOUPDATER=1
# Tell Claude Code where to look for credentials (mounted volume)
ENV CLAUDE_CONFIG_DIR=/home/claude/.claude

# Entrypoint runs as root to apply iptables, then gosu drops to claude.
ENTRYPOINT ["/usr/local/bin/init-firewall.sh"]
# Default: start remote-control server (requires prior `claude login`)
# Override with `docker compose run claude bash` for an interactive shell
CMD ["claude", "remote-control", "--permission-mode", "bypassPermissions"]
