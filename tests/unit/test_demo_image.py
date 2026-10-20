"""Guards for the Docker images (hosted demo, examples) and render.yaml.

Nothing in PR CI builds these images, so a repository layout change can break the
Render deploy or the nightly load test without failing any check. These tests catch
the cheap cases.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# Every image that runs `uv sync` against the repository's pyproject.toml.
DOCKERFILES = [
    ROOT / "deploy" / "demo" / "Dockerfile",
    ROOT / "examples" / "erp" / "Dockerfile",
    ROOT / "examples" / "simple" / "Dockerfile",
]
RENDER_YAML = ROOT / "render.yaml"


def _workspace_member_dirs() -> list[str]:
    """Top-level dirs of ``[tool.uv.workspace] members`` (``"plugins/*"`` -> ``"plugins"``)."""
    pyproject = (ROOT / "pyproject.toml").read_text()
    section = re.search(
        r"^\[tool\.uv\.workspace\]\n(.*?)(?=^\[|\Z)", pyproject, re.MULTILINE | re.DOTALL
    )
    if section is None:
        return []
    members = re.search(r"members\s*=\s*\[(.*?)\]", section.group(1), re.DOTALL)
    globs = re.findall(r'"([^"]+)"', members.group(1)) if members else []
    return sorted({glob.split("/", 1)[0] for glob in globs})


@pytest.mark.parametrize("dockerfile", DOCKERFILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_image_copies_every_uv_workspace_member(dockerfile: Path) -> None:
    """
    Scenario: an image can resolve the uv workspace
      Given pyproject.toml declares uv workspace members (e.g. plugins/*)
      When  the Dockerfile runs `uv sync`
      Then  every member directory has been copied into the image
    """
    text = dockerfile.read_text()
    assert "uv sync" in text
    copied = re.findall(r"^COPY\b.*?\s(\S+)/?\s+\./", text, re.MULTILINE)
    copied_dirs = {path.rstrip("/") for path in copied}

    missing = [d for d in _workspace_member_dirs() if d not in copied_dirs]

    assert not missing, f"{dockerfile.relative_to(ROOT)} does not COPY workspace members: {missing}"


def test_render_rebuilds_when_a_workspace_member_changes() -> None:
    """
    Scenario: a plugin change redeploys the demo
      Given uv workspace member directories
      When  render.yaml's buildFilter is read
      Then  each member directory is in the watched paths
    """
    watched = set(re.findall(r"^\s*-\s+(\S+)/\*\*\s*$", RENDER_YAML.read_text(), re.MULTILINE))

    missing = [d for d in _workspace_member_dirs() if d not in watched]

    assert not missing, f"render.yaml buildFilter does not watch: {missing}"
