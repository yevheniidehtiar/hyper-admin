#!/usr/bin/env bash
# Firewall for Claude Code YOLO container
#
# Whitelists only the services Claude Code needs, then drops everything else.
# This makes --dangerously-skip-permissions safe by ensuring Claude cannot
# reach arbitrary internet services even if prompt-injected.
#
# Required capability: NET_ADMIN (set in docker-compose.yml)
#
# Allowlist:
#   - api.anthropic.com        — Claude API (headless / API-key sessions)
#   - claude.ai                — OAuth login + remote-control session relay
#   - statsig.anthropic.com    — feature flags used by Claude Code
#   - github.com               — code hosting + gh CLI
#   - api.github.com           — gh CLI API
#   - registry.npmjs.org       — npm (Claude Code updates)
#   - pypi.org                 — Python packages
#   - files.pythonhosted.org   — PyPI file downloads
#
# Based on Anthropic's official devcontainer pattern:
# https://github.com/anthropics/claude-code/tree/main/.devcontainer

set -euo pipefail

ALLOW_HOSTS=(
    # Anthropic services
    "api.anthropic.com"
    "claude.ai"                   # OAuth login + remote-control session relay
    "statsig.anthropic.com"       # feature flags
    # Code hosting
    "github.com"
    "api.github.com"
    "objects.githubusercontent.com"
    # Package registries
    "registry.npmjs.org"
    "pypi.org"
    "files.pythonhosted.org"
    "uv.astral.sh"
    "ghcr.io"
    # MCP servers
    "mcp.slack.com"
)

# ── Flush existing rules ────────────────────────────────────────────────────────
iptables -F OUTPUT 2>/dev/null || true
iptables -F INPUT  2>/dev/null || true

# ── Always allow loopback ──────────────────────────────────────────────────────
iptables -A OUTPUT -o lo -j ACCEPT
iptables -A INPUT  -i lo -j ACCEPT

# ── Allow established/related connections ──────────────────────────────────────
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT  -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# ── Allow DNS ─────────────────────────────────────────────────────────────────
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# ── Whitelist specific hosts ───────────────────────────────────────────────────
for host in "${ALLOW_HOSTS[@]}"; do
    # Resolve all IPs (A records) and allow HTTPS to each
    while IFS= read -r ip; do
        [ -z "$ip" ] && continue
        iptables -A OUTPUT -p tcp -d "$ip" --dport 443 -j ACCEPT
        iptables -A OUTPUT -p tcp -d "$ip" --dport 80  -j ACCEPT
    done < <(getent ahostsv4 "$host" 2>/dev/null | awk '{print $1}' | sort -u)
done

# ── Allow SSH (git over SSH) ──────────────────────────────────────────────────
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT

# ── Drop everything else ───────────────────────────────────────────────────────
iptables -A OUTPUT -j DROP

echo "[firewall] Rules applied — outbound locked to whitelist" >&2

# Drop from root to the unprivileged 'claude' user before handing off.
# bypassPermissions (used by remote-control) requires a non-root process.
# gosu re-execs the process so it runs as 'claude', not as a root child.
exec gosu claude "$@"
