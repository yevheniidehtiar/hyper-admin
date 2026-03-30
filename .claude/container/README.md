# Claude Code Remote Container

Isolated Docker environment for running Claude Code autonomously.
Safe to use with `--dangerously-skip-permissions` because the container's
outbound network is locked to a whitelist by `scripts/init-firewall.sh`.

---

## Prerequisites

- Docker with BuildKit enabled (default since Docker 23)
- A [claude.ai Max subscription](https://claude.ai) **or** an Anthropic API key
- GitHub CLI (`gh`) installed on the host (for deploy key rotation)

---

## Bootstrap (first-time setup)

Run these commands from the project root.

### 1. Build the container image

```bash
just cc-build
```

### 2. Log in to Claude Code (Max subscription OAuth)

```bash
just cc-login
```

Claude Code prints a URL — open it in your browser and complete the OAuth flow.
Credentials are saved to the `claude-credentials` Docker volume and persist
across container restarts.

**API key alternative** (headless tasks only, remote-control not supported):
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. Log in to GitHub CLI inside the container

```bash
just cc-gh-auth
```

Follow the interactive `gh auth login` prompts. This lets Claude create PRs,
comment on issues, etc. Auth is saved to the `gh-config` Docker volume.

### 4. Start the remote-control server

```bash
just cc-start
```

This builds the image, rotates the SSH deploy key (registered as a
per-repo key on GitHub), and starts the remote-control server in the
background.

### 5. Connect from Claude Code

Claude Code prints a session URL and QR code in the logs (`just cc-up` or
`docker compose -f .claude/container/docker-compose.yml logs`).

- **Desktop app:** Sessions > find your container by name
- **Browser:** open the session URL
- **QR code:** scan with the Claude.ai mobile app

Send a test prompt to verify everything works.

---

## Daily usage

| Goal | Command |
|------|---------|
| Build + rotate key + start server | `just cc-start` |
| Start server (skip build) | `just cc-up` |
| Interactive YOLO TUI | `just cc-local` |
| Headless task | `just cc-run "fix the lint errors"` |
| Interactive shell | `just cc-shell` |
| Re-authenticate Claude | `just cc-login` |
| Re-authenticate GitHub | `just cc-gh-auth` |
| Rotate SSH deploy key | `just cc-rotate-key` |
| Run container security tests | `just cc-test` |

---

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | No* | API-key auth for headless `-p` tasks |
| `CLAUDE_GH_TOKEN` | For PRs | `gh pr create` uses this token so PRs are owned by the bot |
| `GITHUB_PAT` | Via `.env` | Loaded from project `.env` at runtime |
| `SLACK_BOT_TOKEN` | Via `.env` | Loaded from project `.env` at runtime |

\* Not required when using OAuth (Max subscription). Required for API-key sessions.
   `remote-control` only works with OAuth — API keys are not supported for it.

---

## Credential persistence

| What | Docker volume | Path inside container |
|------|---------------|-----------------------|
| Claude OAuth tokens | `claude-credentials` | `/root/.claude` |
| GitHub CLI auth | `gh-config` | `/root/.config/gh` |
| SSH deploy key | host mount (`.claude/container/ssh/`) | `/root/.ssh` (read-only) |

To reset credentials (force re-login):
```bash
docker volume rm container_claude-credentials   # Claude OAuth
docker volume rm container_gh-config            # GitHub CLI
```

---

## Memory sharing

The container bridges Claude Code's project memory with the host so that
host-accumulated learnings (feedback, project context, user preferences) are
available to container agents, and multiple containers share the same memory.

**How it works:**

1. `just cc-build` stages the host memory (`~/.claude/projects/<key>/memory/`)
   into the build context at `.claude/container/host-memory/` (gitignored).
2. `docker build` bakes the snapshot into the image at `/image-memory/`.
3. At startup, `init-memory.sh` copies the snapshot into the named volume at
   `/root/.claude/projects/-app/memory/` using `cp -u` (update — newer files
   only), so container-written entries are never overwritten by a stale build.
4. Multiple containers from the same Compose share the `claude-credentials`
   named volume, so memory written by one container is visible to the others.

To refresh memory after host changes, rebuild: `just cc-build`.

---

## SSH deploy key

`just cc-rotate-key` generates an ed25519 keypair in `.claude/container/ssh/`
(gitignored) and registers it as a **per-repo read-write deploy key** on GitHub.

- Scoped to `yevheniidehtiar/hyper-admin` only (not your whole GitHub account)
- Rotated automatically on every `just cc-start`
- Old key is removed from GitHub before the new one is registered
- Mounted read-only into the container at `/root/.ssh`

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
├── Dockerfile.dockerignore     # excludes .venv, caches, secrets from build context
├── docker-compose.yml          # service definition, volumes, capabilities
├── host-memory/                # gitignored — staged by `just cc-build`
├── scripts/
│   ├── init-firewall.sh        # iptables whitelist entrypoint
│   └── init-memory.sh          # syncs host memory snapshot into named volume
├── ssh/                        # gitignored — generated deploy key
│   ├── id_ed25519
│   ├── id_ed25519.pub
│   ├── config
│   └── known_hosts
├── tests/
│   └── test_container_security.py
└── README.md                   # this file
```
