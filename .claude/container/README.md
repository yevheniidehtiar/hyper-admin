# Claude Code Remote Container

Isolated Docker environment for running Claude Code autonomously.
Safe to use with `--dangerously-skip-permissions` because the container's
outbound network is locked to a whitelist by `scripts/init-firewall.sh`.

---

## Prerequisites

- Docker with BuildKit enabled (default since Docker 23)
- A [claude.ai Max subscription](https://claude.ai) **or** an Anthropic API key
- `CLAUDE_GH_TOKEN` set in your shell (for PR creation under the bot account)

---

## Quick start

All commands run from this directory (`.claude/container/`).

### 1. Build the image

```bash
docker compose build
```

### 2. Authenticate (one-time)

**Max subscription (recommended):**
```bash
docker compose run --rm claude claude login
# Claude Code prints a URL — open it in your browser and complete OAuth.
# Credentials are saved to the `claude-credentials` Docker volume.
```

**API key (headless tasks only, remote-control not supported):**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. Start the remote-control server

```bash
docker compose up
```

Claude Code prints a session URL and QR code.
Open the URL in your browser or from the Claude Code desktop app to connect.

### 4. Connect from the web / desktop app

- **Browser:** open the session URL printed in step 3
- **Desktop app:** Sessions → find your container by name
- **QR code:** scan with the Claude.ai mobile app

---

## Usage modes

| Goal | Command |
|------|---------|
| Start remote-control server | `docker compose up` |
| Interactive shell inside container | `docker compose run --rm claude bash` |
| Headless task (YOLO mode) | `docker compose run --rm -e ANTHROPIC_API_KEY claude claude --dangerously-skip-permissions -p "your task"` |
| Re-authenticate | `docker compose run --rm claude claude login` |

---

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | No* | API-key auth for headless `-p` tasks |
| `CLAUDE_GH_TOKEN` | For PRs | `gh pr create` uses this token so PRs are owned by the bot |
| `DISABLE_AUTOUPDATER` | Set automatically | Prevents update prompts in non-interactive mode |

\* Not required when using OAuth (Max subscription). Required for API-key sessions.
   `remote-control` only works with OAuth — API keys are not supported for it.

---

## Credential persistence

OAuth tokens are stored in the `claude-credentials` named Docker volume
mounted at `/root/.claude` inside the container. The volume survives
`docker compose down` and `docker compose rm`.

To reset credentials (force re-login):
```bash
docker volume rm container_claude-credentials
```

---

## Network security

`scripts/init-firewall.sh` applies iptables rules at container startup
(requires the `NET_ADMIN` capability set in `docker-compose.yml`).

**Allowed outbound:**

| Host | Port | Purpose |
|------|------|---------|
| `api.anthropic.com` | 443 | Claude API |
| `claude.ai` | 443 | OAuth login + remote-control relay |
| `statsig.anthropic.com` | 443 | Feature flags |
| `github.com`, `api.github.com` | 443/22 | Code hosting, `gh` CLI |
| `objects.githubusercontent.com` | 443 | Git LFS / raw downloads |
| `registry.npmjs.org` | 443 | npm packages |
| `pypi.org`, `files.pythonhosted.org` | 443 | Python packages |
| `uv.astral.sh`, `ghcr.io` | 443 | `uv` and container images |
| `mcp.slack.com` | 443 | Slack MCP server |
| Any | 53 | DNS |

Everything else is dropped, making `--dangerously-skip-permissions` safe.

---

## File layout

```
.claude/container/
├── Dockerfile                  # node:20-bookworm + Python + uv + gh + Claude Code
├── Dockerfile.dockerignore     # excludes .venv, caches, worktrees from build context
├── docker-compose.yml          # service definition, volumes, capabilities
├── scripts/
│   └── init-firewall.sh        # iptables whitelist entrypoint
└── README.md                   # this file
```
