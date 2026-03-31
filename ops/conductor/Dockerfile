FROM node:22-slim AS base

# System deps for Claude Code + git + gh CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates jq python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install gh CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y gh && rm -rf /var/lib/apt/lists/*

# Install uv (Python project manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Status directory for health checks
RUN mkdir -p /run/conductor

WORKDIR /workspace

COPY supervisor.sh /usr/local/bin/supervisor.sh
RUN chmod +x /usr/local/bin/supervisor.sh

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD /usr/local/bin/healthcheck.sh

COPY healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/healthcheck.sh

ENTRYPOINT ["/usr/local/bin/supervisor.sh"]
