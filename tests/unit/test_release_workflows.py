"""Version, commitizen config and the release/publish chain (st-v058-byoa-50, SDD section E)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from importlib.metadata import version as dist_version
from pathlib import Path
from typing import Any

import pytest
import yaml

import hyperadmin

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"
_PYPROJECT = (_REPO_ROOT / "pyproject.toml").read_text()
_SMOKE_SCRIPT = _REPO_ROOT / "scripts" / "smoke_test_wheel.py"
_PR_EVENTS = {"pull_request", "pull_request_target"}


def _pyproject_version() -> str:
    match = re.search(r'^version = "([^"]+)"$', _PYPROJECT, re.MULTILINE)
    assert match is not None
    return match.group(1)


def _commitizen_section() -> str:
    start = _PYPROJECT.index("[tool.commitizen]")
    end = _PYPROJECT.index("\n[", start + 1)
    return _PYPROJECT[start:end]


def _load_workflow(name: str) -> dict[Any, Any]:
    data = yaml.safe_load((_WORKFLOWS / name).read_text())
    assert isinstance(data, dict)
    return data


def _triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    # PyYAML parses the bare ``on`` key as boolean True (YAML 1.1).
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict)
    return triggers


def _runs(job: dict[str, Any]) -> str:
    return "\n".join(step.get("run", "") for step in job["steps"])


# --- version ---------------------------------------------------------------


def test_version_exposed() -> None:
    """
    Scenario: version exposed
      Given hyperadmin installed
      When  hyperadmin.__version__ is read
      Then  it equals the pyproject version
    """
    assert hyperadmin.__version__ == _pyproject_version()
    assert hyperadmin.__version__ == dist_version("hyper-admin")
    assert "__version__" in hyperadmin.__all__


def test_first_release_is_the_pep440_prerelease_0_5_0a1() -> None:
    """
    Scenario: the first PyPI release is an honest pre-release
      Given the pyproject metadata
      When  the version is read
      Then  it is the PEP 440 pre-release 0.5.0a1
    """
    assert _pyproject_version() == "0.5.0a1"


def test_commitizen_uses_pep440_and_major_version_zero() -> None:
    """
    Scenario: commitizen bumps stay pre-1.0 and PEP 440
      Given the commitizen configuration
      When  it is read
      Then  version_scheme is pep440 and major_version_zero is true
    """
    section = _commitizen_section()
    assert 'version_scheme = "pep440"' in section
    assert "major_version_zero = true" in section


def test_install_docs_pin_the_released_distribution() -> None:
    """
    Scenario: install docs name the published pre-release
      Given README.md and docs/getting-started.md
      When  a user reads the install lines
      Then  they install hyper-admin pinned to the pyproject version
      And   the import name hyperadmin is called out
    """
    pin = f"hyper-admin=={_pyproject_version()}"
    for doc in ("README.md", "docs/getting-started.md"):
        text = (_REPO_ROOT / doc).read_text()
        assert f"pip install {pin}" in text, doc
        assert "import name" in text and "`hyperadmin`" in text, doc
        assert "pip install hyperadmin" not in text, doc


def test_changelog_has_a_section_for_the_version() -> None:
    """
    Scenario: the changelog announces the release
      Given CHANGELOG.md
      When  it is read
      Then  it has a section for the pyproject version
    """
    changelog = (_REPO_ROOT / "CHANGELOG.md").read_text()
    assert f"## [{_pyproject_version()}]" in changelog


# --- publish.yml -------------------------------------------------------------


def test_draft_releases_do_not_publish() -> None:
    """
    Scenario: draft releases do not publish
      Given a draft GitHub release
      When  it is created
      Then  publish.yml does not run
    """
    triggers = _triggers(_load_workflow("publish.yml"))
    assert set(triggers) == {"workflow_call", "workflow_dispatch"}
    assert "--draft" not in (_WORKFLOWS / "release.yml").read_text()


def test_publish_takes_the_version_to_publish_as_an_input() -> None:
    """
    Scenario: publish builds the tagged version
      Given publish.yml is called or dispatched
      When  its inputs are read
      Then  both triggers require the version
      And   the build checks out the v<version> tag
    """
    workflow = _load_workflow("publish.yml")
    triggers = _triggers(workflow)
    for trigger in ("workflow_call", "workflow_dispatch"):
        assert triggers[trigger]["inputs"]["version"]["required"] is True, trigger
    (checkout,) = [
        s for s in workflow["jobs"]["build"]["steps"] if "actions/checkout" in s.get("uses", "")
    ]
    assert checkout["with"]["ref"] == "v${{ inputs.version }}"


def test_smoke_test_before_upload() -> None:
    """
    Scenario: smoke test before upload
      Given a published GitHub release
      When  publish.yml runs
      Then  the build job imports hyperadmin from the built wheel before the publish job starts
    """
    jobs = _load_workflow("publish.yml")["jobs"]
    build = _runs(jobs["build"])

    assert "uv build" in build
    assert "twine check" in build
    # A clean venv with only the wheel (plus TestClient's httpx), never the project's dev deps.
    assert "uv venv" in build and "--no-project" in build
    assert "dist/*.whl" in build
    assert "uv sync" not in build and "--all-extras" not in build
    assert "scripts/smoke_test_wheel.py" in build
    assert build.index("twine check") < build.index("smoke_test_wheel.py")
    assert jobs["publish"]["needs"] == "build"


def test_publish_job_uses_trusted_publishing_from_the_pypi_environment() -> None:
    """
    Scenario: upload uses trusted publishing
      Given the publish job
      When  it uploads to PyPI
      Then  it runs in the pypi environment with an OIDC token and no API token secret
    """
    workflow = _load_workflow("publish.yml")
    publish = workflow["jobs"]["publish"]

    assert publish["environment"] == "pypi"
    assert publish["permissions"] == {"id-token": "write"}
    assert "uv publish --trusted-publishing always" in _runs(publish)
    assert "secrets." not in (_WORKFLOWS / "publish.yml").read_text()
    assert workflow["permissions"] == {"contents": "read"}


@pytest.mark.parametrize("name", sorted(p.name for p in _WORKFLOWS.glob("*.yml")))
def test_no_workflow_publishes_or_releases_on_pull_requests(name: str) -> None:
    """
    Scenario: pull requests never publish
      Given any workflow that can run on a pull request
      When  it is read
      Then  it neither publishes to PyPI nor creates a release
    """
    workflow = _load_workflow(name)
    if not set(_triggers(workflow)) & _PR_EVENTS:
        return
    text = (_WORKFLOWS / name).read_text()
    for forbidden in ("uv publish", "gh release create", "publish.yml", "pypa/gh-action-pypi"):
        assert forbidden not in text, f"{name} runs {forbidden!r} on a pull request"


def test_publish_job_refuses_pull_request_events() -> None:
    """
    Scenario: a reusable call from a PR context cannot publish
      Given publish.yml is called by a workflow triggered by a pull request
      When  the publish job is evaluated
      Then  its condition excludes pull_request and pull_request_target
    """
    condition = _load_workflow("publish.yml")["jobs"]["publish"]["if"]
    for event in _PR_EVENTS:
        assert f"github.event_name != '{event}'" in condition


# --- release.yml -------------------------------------------------------------


def test_release_is_dispatched_by_hand_and_never_pushes_a_commit() -> None:
    """
    Scenario: release never pushes to master
      Given release.yml
      When  it runs
      Then  it is only manually dispatched from master
      And   it neither bumps the version nor pushes a branch
    """
    workflow = _load_workflow("release.yml")
    assert set(_triggers(workflow)) == {"workflow_dispatch"}
    text = (_WORKFLOWS / "release.yml").read_text()
    for forbidden in ("cz bump", "git commit", "git push origin main", "git push origin master"):
        assert forbidden not in text, forbidden
    assert "refs/heads/master" in workflow["jobs"]["release"]["if"]


def test_release_checks_the_input_against_pyproject() -> None:
    """
    Scenario: a mismatched version input fails the release
      Given inputs.version differs from the pyproject version
      When  release.yml runs
      Then  the release job fails before tagging
    """
    release = _runs(_load_workflow("release.yml")["jobs"]["release"])
    assert "pyproject.toml" in release
    assert '"$VERSION" != "$PYPROJECT_VERSION"' in release
    assert "exit 1" in release
    assert release.index("exit 1") < release.index("git push origin")
    # The input reaches the script through env, never by template interpolation.
    assert "${{ inputs.version }}" not in release


def test_release_pushes_the_tag_then_creates_a_prerelease() -> None:
    """
    Scenario: pre-release versions become GitHub pre-releases
      Given a version with an a, b or rc suffix
      When  release.yml runs
      Then  it pushes the v<version> tag and runs gh release create --prerelease
    """
    release = _runs(_load_workflow("release.yml")["jobs"]["release"])
    assert 'git push origin "refs/tags/v$VERSION"' in release
    assert 'gh release create "v$VERSION"' in release
    assert "--generate-notes" in release and "--verify-tag" in release
    assert "--prerelease" in release
    assert "(a|b|rc)[0-9]+$" in release
    assert release.index("git push origin") < release.index("gh release create")


def test_release_calls_publish_in_the_same_run() -> None:
    """
    Scenario: the GITHUB_TOKEN release still publishes
      Given release.yml created the GitHub release with GITHUB_TOKEN
      When  the release job finishes
      Then  publish.yml runs as a reusable workflow in the same run with the version
    """
    jobs = _load_workflow("release.yml")["jobs"]
    publish = jobs["publish"]
    assert publish["uses"] == "./.github/workflows/publish.yml"
    assert publish["needs"] == "release"
    assert publish["with"]["version"] == "${{ inputs.version }}"
    assert publish["permissions"]["id-token"] == "write"


# --- wheel smoke script -----------------------------------------------------


def _run_smoke(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("HYPERADMIN_")}
    return subprocess.run(
        [sys.executable, str(_SMOKE_SCRIPT), *args],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_smoke_script_serves_the_zero_config_admin(tmp_path: Path) -> None:
    """
    Scenario: the wheel smoke test makes a real request
      Given hyperadmin installed with its runtime dependencies
      When  the smoke script builds a FastAPI app and mounts Admin(app) at /admin
      Then  GET /admin/ returns 200 and the script exits 0
    """
    result = _run_smoke(tmp_path, "--expect-version", hyperadmin.__version__)

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"hyperadmin {hyperadmin.__version__}" in result.stdout
    assert "GET /admin/ -> 200" in result.stdout


def test_smoke_script_fails_on_a_version_mismatch(tmp_path: Path) -> None:
    """
    Scenario: a wheel built from the wrong commit is not uploaded
      Given the installed hyperadmin version differs from the release version
      When  the smoke script runs with --expect-version
      Then  it exits non-zero
    """
    result = _run_smoke(tmp_path, "--expect-version", "0.0.0")

    assert result.returncode != 0
    assert "version mismatch" in result.stderr
