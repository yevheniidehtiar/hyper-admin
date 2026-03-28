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

# ── Project dependencies ───────────────────────────────────────────────────────
WORKDIR /app

# Copy only manifests first for layer caching
COPY pyproject.toml uv.lock* ./

# Install all Python deps (including dev/test/e2e extras)
RUN uv sync --all-extras --frozen

# Copy the rest of the project
COPY . .

# Install Playwright browsers (needed for E2E tests)
RUN uv run playwright install --with-deps chromium

# Install pre-commit hooks
RUN git config --global --add safe.directory /app \
    && uv run pre-commit install --install-hooks || true

# ── Firewall ───────────────────────────────────────────────────────────────────
COPY .claude/container/scripts/init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh

# ── Git identity for Claude Code commits ───────────────────────────────────────
RUN git config --global user.name "Claude Code" \
    && git config --global user.email "noreply+claude-code@anthropic.com"

# ── Runtime environment ────────────────────────────────────────────────────────
ENV DISABLE_AUTOUPDATER=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
# Tell Claude Code where to look for credentials (mounted volume)
ENV CLAUDE_CONFIG_DIR=/root/.claude

# Entrypoint: apply firewall rules then hand off to CMD
ENTRYPOINT ["/usr/local/bin/init-firewall.sh"]
# Default: start remote-control server (requires prior `claude login`)
# Override with `docker compose run claude bash` for an interactive shell
CMD ["claude", "remote-control"]
