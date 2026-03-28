#!/usr/bin/env bash
# Security tests for the container firewall.
# Run INSIDE the container — every test asserts on network reachability.
#
# Exit codes: 0 = all passed, 1 = one or more failures.

set -euo pipefail

PASS=0
FAIL=0
TIMEOUT=5   # seconds per connection attempt

green() { printf '\033[32m✓\033[0m %s\n' "$*"; }
red()   { printf '\033[31m✗\033[0m %s\n' "$*"; }

# ── Helpers ────────────────────────────────────────────────────────────────────

# Assert a TCP connection to host:port succeeds within $TIMEOUT seconds.
assert_reachable() {
    local label="$1" host="$2" port="${3:-443}"
    if timeout "$TIMEOUT" bash -c ">/dev/tcp/$host/$port" 2>/dev/null; then
        green "$label ($host:$port) — reachable (EXPECTED)"
        PASS=$(( PASS + 1 ))
    else
        red   "$label ($host:$port) — BLOCKED (unexpected)"
        FAIL=$(( FAIL + 1 ))
    fi
}

# Assert a TCP connection to host:port FAILS within $TIMEOUT seconds.
assert_blocked() {
    local label="$1" host="$2" port="${3:-443}"
    if timeout "$TIMEOUT" bash -c ">/dev/tcp/$host/$port" 2>/dev/null; then
        red   "$label ($host:$port) — reachable (UNEXPECTED — firewall hole!)"
        FAIL=$(( FAIL + 1 ))
    else
        green "$label ($host:$port) — blocked (EXPECTED)"
        PASS=$(( PASS + 1 ))
    fi
}

# Assert a DNS lookup succeeds.
assert_dns() {
    local label="$1" host="$2"
    if getent hosts "$host" &>/dev/null; then
        green "$label DNS ($host) — resolves (EXPECTED)"
        PASS=$(( PASS + 1 ))
    else
        red   "$label DNS ($host) — failed (unexpected)"
        FAIL=$(( FAIL + 1 ))
    fi
}

# ── DNS ────────────────────────────────────────────────────────────────────────
echo ""
echo "=== DNS ==="
assert_dns "Anthropic API"  "api.anthropic.com"
assert_dns "Claude.ai"      "claude.ai"
assert_dns "GitHub"         "github.com"
assert_dns "PyPI"           "pypi.org"

# ── Allowed hosts (whitelist) ──────────────────────────────────────────────────
echo ""
echo "=== Whitelisted hosts (must be reachable) ==="
assert_reachable "Anthropic API"        "api.anthropic.com"
assert_reachable "Claude.ai"            "claude.ai"
assert_reachable "Statsig"              "statsig.anthropic.com"
assert_reachable "GitHub"               "github.com"
assert_reachable "GitHub API"           "api.github.com"
assert_reachable "npm registry"         "registry.npmjs.org"
assert_reachable "PyPI"                 "pypi.org"
assert_reachable "PyPI files"           "files.pythonhosted.org"
assert_reachable "GitHub SSH"           "github.com" "22"

# ── Blocked hosts (not on whitelist) ──────────────────────────────────────────
echo ""
echo "=== Non-whitelisted hosts (must be blocked) ==="
assert_blocked "Google"                 "google.com"
assert_blocked "Cloudflare DNS"         "1.1.1.1"
assert_blocked "Example.com"            "example.com"
assert_blocked "httpbin"                "httpbin.org"
assert_blocked "AWS metadata"           "169.254.169.254" "80"

# ── Toolchain smoke checks ─────────────────────────────────────────────────────
echo ""
echo "=== Toolchain ==="
for cmd in claude uv gh python3 git rg; do
    if command -v "$cmd" &>/dev/null; then
        green "$cmd — found ($(command -v "$cmd"))"
        PASS=$(( PASS + 1 ))
    else
        red   "$cmd — NOT FOUND"
        FAIL=$(( FAIL + 1 ))
    fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────"
printf "Passed: %d   Failed: %d\n" "$PASS" "$FAIL"
echo "─────────────────────────────"

[ "$FAIL" -eq 0 ]
