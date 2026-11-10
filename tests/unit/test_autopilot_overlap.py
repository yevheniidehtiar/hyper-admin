"""Files-section parsing and the overlap matrix of the autopilot (ops/autopilot/lib/overlap.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "ops" / "autopilot" / "lib"))

import overlap

STORY = """\
---
type: story
id: st-demo-01
---

## Summary

Touches `src/hyperadmin/ignored/before.py` in prose, which is not in the section.

## Files to Change

- `.github/workflows/conflict-check.yml` (new) — trigger on `push: develop`
- `docs/contributing.md` — fill the stub only
- **New:** `src/hyperadmin/widgets/`

## Acceptance Criteria

- [ ] `src/hyperadmin/ignored/after.py` is not part of the section either
"""


def test_files_to_change_reads_only_the_section() -> None:
    assert overlap.files_to_change(STORY) == {
        ".github/workflows/conflict-check.yml",
        "docs/contributing.md",
        "src/hyperadmin/widgets",
    }


@pytest.mark.parametrize(
    "heading",
    [
        "## Files to Change",
        "## files to change",
        "### Files to Change",
        "## Files",
        "## Files Likely Affected",
        "## Files likely to change",
        "## Files to modify",
        "## Files to create",
        "## Files to create/modify",
    ],
)
def test_files_to_change_accepts_the_heading_variants(heading: str) -> None:
    text = f"## Context\n\nintro\n\n{heading}\n- `src/hyperadmin/views/dynamic.py`\n\n## Next\n"

    assert overlap.files_to_change(text) == {"src/hyperadmin/views/dynamic.py"}


@pytest.mark.parametrize(
    "text",
    ["", "## Summary\n\n`src/a.py`\n", "## Filesystem notes\n- `src/a.py`\n", "## Files\n- none\n"],
)
def test_files_to_change_is_empty_without_a_section_or_paths(text: str) -> None:
    assert overlap.files_to_change(text) == set()


def test_files_to_change_runs_to_the_end_when_the_section_is_last() -> None:
    assert overlap.files_to_change("## Files\n- `a/b.py`\n- `c.toml`\n") == {"a/b.py", "c.toml"}


@pytest.mark.parametrize(
    ("path", "key"),
    [
        ("pyproject.toml", "pyproject.toml + uv.lock"),
        ("uv.lock", "pyproject.toml + uv.lock"),
        (".github/workflows/ci.yml", ".github/"),
        (".github", ".github/"),
        ("tests/e2e/snapshots/list/chromium.png", "tests/e2e/snapshots/"),
        (".gitignore", ".gitignore"),
        ("src/hyperadmin/core/app.py", "src/hyperadmin/core/app.py"),
        ("src/hyperadmin/auth/__init__.py", "src/hyperadmin/auth/__init__.py"),
        ("src/hyperadmin/static/css/_tokens.css", "src/hyperadmin/static/css/_tokens.css"),
        ("src/hyperadmin/templates/_base.html", "src/hyperadmin/templates/_base.html"),
        ("tests/e2e/conftest.py", "tests/e2e/conftest.py"),
        ("src/hyperadmin/views/dynamic.py", None),
        ("plugins/hyperadmin-tasks/pyproject.toml", None),
        ("docs/.github-notes.md", None),
    ],
)
def test_hotspot_key(path: str, key: str | None) -> None:
    assert overlap.hotspot_key(path) == key


def test_hotspots_of_a_file_set() -> None:
    files = {"uv.lock", "src/hyperadmin/views/list.py", ".github/dependabot.yml"}

    assert overlap.hotspots(files) == {"pyproject.toml + uv.lock", ".github/"}


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("src/a.py", "src/a.py", True),
        ("src/widgets", "src/widgets/select.py", True),
        ("src/widgets/select.py", "src/widgets", True),
        ("src/widgets", "src/widgets_extra/select.py", False),
        ("src/a.py", "src/b.py", False),
    ],
)
def test_paths_overlap(first: str, second: str, expected: bool) -> None:
    assert overlap.paths_overlap(first, second) is expected


def test_shared_lists_files_directories_and_hotspot_classes() -> None:
    first = {"src/a.py", "src/widgets", ".github/workflows/ci.yml", "pyproject.toml"}
    second = {"src/a.py", "src/widgets/select.py", ".github/CODEOWNERS", "uv.lock", "src/z.py"}

    assert overlap.shared(first, second) == [
        ".github/",
        "pyproject.toml + uv.lock",
        "src/a.py",
        "src/widgets",
    ]


def test_shared_is_empty_for_disjoint_ordinary_files() -> None:
    assert overlap.shared({"src/a.py"}, {"src/b.py", "tests/unit/test_b.py"}) == []


def test_two_different_package_inits_do_not_collide() -> None:
    first = {"src/hyperadmin/auth/__init__.py"}
    second = {"src/hyperadmin/core/__init__.py"}

    assert overlap.shared(first, second) == []
    assert overlap.shared(first, first) == ["src/hyperadmin/auth/__init__.py"]


def test_conflicts_names_only_the_colliding_running_stories() -> None:
    running = {
        "st-1": {"src/a.py"},
        "st-2": {"src/b.py"},
        "st-3": {"tests/e2e/snapshots/detail.png"},
    }

    assert overlap.conflicts({"src/a.py", "tests/e2e/snapshots/list.png"}, running) == {
        "st-1": ["src/a.py"],
        "st-3": ["tests/e2e/snapshots/"],
    }
    assert overlap.conflicts(set(), running) == {}


def test_matrix_reports_each_colliding_pair_once() -> None:
    stories = {
        "a": {"src/x.py", "pyproject.toml"},
        "b": {"src/x.py"},
        "c": {"uv.lock"},
        "d": {"src/y.py"},
    }

    assert overlap.matrix(stories) == [
        ("a", "b", ["src/x.py"]),
        ("a", "c", ["pyproject.toml + uv.lock"]),
    ]


def test_cli_prints_the_matrix_and_fails_on_overlap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    third = tmp_path / "third.md"
    first.write_text("## Files to Change\n- `src/x.py`\n- `.gitignore`\n")
    second.write_text("## Files to Change\n- `src/x.py`\n")
    third.write_text("## Summary\nno files section\n")

    code = overlap.main([str(first), str(second), str(third)])

    out = capsys.readouterr().out
    assert code == 1
    assert f"OVERLAP  {first}\n    with {second}\n         src/x.py" in out
    assert f"HOTSPOT  {first}: .gitignore" in out
    assert f"NO files section (cannot check): {third}" in out


def test_cli_is_clean_for_disjoint_stories(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("## Files to Change\n- `src/x.py`\n")
    second.write_text("## Files to Change\n- `src/y.py`\n")

    assert overlap.main([str(first), str(second)]) == 0
    assert "clean: 2 stories, no shared files" in capsys.readouterr().out


def test_cli_without_arguments_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert overlap.main([]) == 2
    assert "overlap.py STORY.md" in capsys.readouterr().err
