"""Committed ``uv.lock`` and locked CI installs (st-v058-byoa-12, SDD section E)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"
_UV_SYNC = re.compile(r"\buv sync\b[^\n]*")


def _load_workflow(name: str) -> dict[Any, Any]:
    data = yaml.safe_load((_WORKFLOWS / name).read_text())
    assert isinstance(data, dict)
    return data


def _triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    # PyYAML parses the bare ``on`` key as boolean True (YAML 1.1).
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict)
    return triggers


def _uv_sync_commands(name: str) -> list[str]:
    return _UV_SYNC.findall((_WORKFLOWS / name).read_text())


def test_uv_lock_is_tracked_not_ignored() -> None:
    assert (_REPO_ROOT / "uv.lock").is_file()
    result = subprocess.run(
        ["git", "check-ignore", "-q", "uv.lock"],  # noqa: S607 - git on PATH in dev and CI
        cwd=_REPO_ROOT,
        check=False,
    )
    assert result.returncode == 1, "uv.lock must not be ignored by .gitignore"


@pytest.mark.parametrize("workflow", ["ci.yml", "test.yml"])
def test_prs_to_master_and_develop_are_gated(workflow: str) -> None:
    """Scenario: PRs to develop are gated."""
    triggers = _triggers(_load_workflow(workflow))

    assert set(triggers["pull_request"]["branches"]) >= {"master", "develop"}
    assert set(triggers["push"]["branches"]) >= {"master", "develop"}


def test_ci_does_not_target_the_missing_main_branch() -> None:
    triggers = _triggers(_load_workflow("ci.yml"))

    assert "main" not in triggers["push"]["branches"]
    assert "main" not in triggers["pull_request"]["branches"]


@pytest.mark.parametrize(
    "workflow", sorted(p.name for p in _WORKFLOWS.glob("*.yml") if _uv_sync_commands(p.name))
)
def test_ci_installs_from_the_lock(workflow: str) -> None:
    """Scenario: CI fails on a stale lock (``uv sync --locked`` refuses to re-lock).

    A ``lowest-direct`` resolution cannot be locked by definition, so those
    installs are allowed to re-resolve; the same job then runs ``uv lock --check``.
    """
    text = (_WORKFLOWS / workflow).read_text()
    for command in _uv_sync_commands(workflow):
        if "--resolution" in command:
            assert "uv lock --check" in text, f"{workflow}: {command!r} skips the lock check"
        else:
            assert "--locked" in command, f"{workflow}: {command!r} is not --locked"


def test_test_workflow_checks_the_lock_in_every_job() -> None:
    workflow = _load_workflow("test.yml")
    for job_name, job in workflow["jobs"].items():
        runs = [step.get("run", "") for step in job["steps"]]
        assert any("uv lock --check" in run for run in runs), job_name


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is required to check the lock")
def test_committed_lock_matches_pyproject() -> None:
    uv = shutil.which("uv")
    assert uv is not None
    result = subprocess.run(
        [uv, "lock", "--check"],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def _lowest_direct_install_steps(workflow: dict[Any, Any]) -> list[tuple[str, str]]:
    found = []
    for job_name, job in workflow["jobs"].items():
        for step in job["steps"]:
            run = step.get("run", "")
            if "--resolution" in run and "uv sync" in run:
                found.append((job_name, run))
    return found


def test_lowest_direct_rows_keep_the_lowest_environment() -> None:
    """Scenario: lowest-direct rows really test the lowest versions.

    ``uv sync --resolution lowest-direct`` rewrites uv.lock; a later plain
    ``uv run`` would re-lock at highest and reinstall. The install step must
    restore the committed lock and turn off syncing for the following steps.
    """
    steps = _lowest_direct_install_steps(_load_workflow("test.yml"))

    assert steps
    for job_name, run in steps:
        assert "git checkout -- uv.lock" in run, job_name
        assert "UV_NO_SYNC=1" in run and "GITHUB_ENV" in run, job_name


def test_deps_bump_runs_checks_without_resyncing() -> None:
    """``poe deps:bump`` must run lint/tests on the environment it just synced."""
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text()
    start = pyproject.index('[tool.poe.tasks."deps:bump"]')
    task = pyproject[start : pyproject.index('"""', pyproject.index('"""', start) + 3)]

    # Nested ``uv run`` calls (pre-commit hooks) need the env var, not just a flag.
    for check in ("poe lint", "poe test:unit", "poe security-check"):
        assert f"UV_NO_SYNC=1 uv run {check}" in task, check
    # The upgraded lock is restored after every lowest-direct sync rewrites it.
    assert 'cp "$LOCK_BACKUP" uv.lock' in task


def test_security_audit_runs_on_the_locked_highest_set_only() -> None:
    """Old floor releases carry known advisories; audit what the lock ships."""
    workflow = _load_workflow("test.yml")
    for job_name, job in workflow["jobs"].items():
        (step,) = [s for s in job["steps"] if "security-check" in s.get("run", "")]
        assert step.get("if") == "matrix.resolution == 'highest'", job_name
