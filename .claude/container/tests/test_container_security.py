"""
Container security integration tests.

Requires Docker with BuildKit and NET_ADMIN capability support.
Skipped automatically when Docker is unavailable.

Run:
    pytest .claude/container/tests/test_container_security.py -v
    pytest .claude/container/tests/test_container_security.py -v --no-header -rN
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parents[3]  # hyper-admin/
CONTAINER_DIR = REPO_ROOT / ".claude" / "container"
COMPOSE_FILE = CONTAINER_DIR / "docker-compose.yml"
FIREWALL_TEST = CONTAINER_DIR / "tests" / "test_firewall.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _image_exists() -> bool:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "images",
            "--quiet",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return bool(result.stdout.strip())


def _compose_run(*cmd: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run a command inside the claude service via docker compose run."""
    return subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "run",
            "--rm",
            "--no-deps",
            "claude",
            *cmd,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

needs_docker = pytest.mark.skipif(
    not _docker_available(),
    reason="Docker not available",
)


@pytest.fixture(scope="session")
def built_image():
    """Build the container image once per test session."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "build",
            "--progress",
            "plain",
        ],
        capture_output=True,
        text=True,
        timeout=600,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        pytest.fail(f"docker compose build failed:\n{result.stdout}\n{result.stderr}")
    return True


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@needs_docker
class TestFirewallRules:
    """Verify the iptables whitelist applied by init-firewall.sh."""

    def test_firewall_script_passes(self, built_image):
        """Run the full firewall test suite inside the container."""
        result = _compose_run("bash", str(Path("/app") / FIREWALL_TEST.relative_to(REPO_ROOT)))
        print(result.stdout, file=sys.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
        assert result.returncode == 0, "One or more firewall assertions failed — see output above."

    @pytest.mark.parametrize(
        "host,port",
        [
            ("api.anthropic.com", 443),
            ("claude.ai", 443),
            ("github.com", 443),
            ("api.github.com", 443),
            ("registry.npmjs.org", 443),
            ("pypi.org", 443),
        ],
    )
    def test_whitelisted_host_reachable(self, built_image, host: str, port: int):
        result = _compose_run(
            "bash",
            "-c",
            f"timeout 5 bash -c '>/dev/tcp/{host}/{port}' && echo OPEN || echo BLOCKED",
        )
        assert "OPEN" in result.stdout, f"{host}:{port} should be reachable but was blocked"

    @pytest.mark.parametrize(
        "host,port",
        [
            ("google.com", 443),
            ("example.com", 443),
            ("1.1.1.1", 443),
            ("httpbin.org", 443),
        ],
    )
    def test_blocked_host_unreachable(self, built_image, host: str, port: int):
        result = _compose_run(
            "bash",
            "-c",
            f"timeout 5 bash -c '>/dev/tcp/{host}/{port}' && echo OPEN || echo BLOCKED",
        )
        assert "BLOCKED" in result.stdout, (
            f"{host}:{port} should be blocked by the firewall but was reachable — "
            "potential firewall misconfiguration!"
        )


@needs_docker
class TestToolchain:
    """Verify that all required tools are installed in the image."""

    @pytest.mark.parametrize("binary", ["claude", "uv", "gh", "git", "python3", "rg"])
    def test_binary_present(self, built_image, binary: str):
        result = _compose_run("which", binary)
        assert result.returncode == 0, f"'{binary}' not found in container PATH"

    def test_claude_version(self, built_image):
        result = _compose_run("claude", "--version")
        assert result.returncode == 0
        assert result.stdout.strip(), "claude --version produced no output"

    def test_hyperadmin_installed(self, built_image):
        # Use the venv python directly (avoids uv re-solving against volume-mounted src).
        # Check package metadata rather than importing (import triggers db side-effects).
        result = _compose_run(
            "/opt/venv/bin/python",
            "-c",
            "import importlib.metadata; print(importlib.metadata.version('hyper-admin'))",
        )
        assert result.returncode == 0, f"hyper-admin not installed in /opt/venv:\n{result.stderr}"
        assert result.stdout.strip(), "version string was empty"


@needs_docker
class TestContainerHardening:
    """Verify security-relevant container properties."""

    def test_firewall_rules_applied(self, built_image):
        """iptables OUTPUT chain must have a DROP rule (firewall is active)."""
        result = _compose_run(
            "bash", "-c", "iptables -L OUTPUT -n | grep -q DROP && echo LOCKED || echo OPEN"
        )
        assert "LOCKED" in result.stdout, (
            "Firewall DROP rule not found — init-firewall.sh may not have run"
        )

    def test_no_api_key_in_env_by_default(self, built_image):
        """ANTHROPIC_API_KEY must not be baked into the image."""
        result = _compose_run("bash", "-c", "printenv ANTHROPIC_API_KEY || echo NOT_SET")
        assert "NOT_SET" in result.stdout, (
            "ANTHROPIC_API_KEY is baked into the image — remove it from the Dockerfile"
        )

    def test_git_identity_is_claude_code(self, built_image):
        """git user must be Claude Code, not a human identity."""
        result = _compose_run("git", "config", "--global", "user.email")
        assert "claude-code@anthropic.com" in result.stdout
