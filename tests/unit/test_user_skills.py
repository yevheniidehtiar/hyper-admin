"""Checks for the Claude Code skills and agents shipped for HyperAdmin users.

``skills/<name>/SKILL.md`` and ``agents/<name>.md`` quote HyperAdmin's API. These tests keep
them honest: valid frontmatter, complete code blocks that parse, and imports that resolve
against the installed packages.
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_FILES = sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
AGENT_FILES = sorted((REPO_ROOT / "agents").glob("*.md"))

#: Top-level packages whose imports must resolve: the core and the first-party plugins.
FIRST_PARTY = frozenset(
    {"hyperadmin", "hyperadmin_reports", "hyperadmin_tasks", "hyperadmin_logfire"}
)
#: Marker placed on the line before a python fence that must be a complete, parseable module.
COMPLETE_MARKER = "<!-- check: complete -->"

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_PYTHON_FENCE = re.compile(
    r"^(?P<marker><!-- check: complete -->\n)?```python\n(?P<body>.*?)^```",
    re.DOTALL | re.MULTILINE,
)
_SINGLE_LINE_IMPORT = re.compile(
    r"^\s*(?:from\s+([\w.]+)\s+import\s+([\w, ]+)|import\s+([\w.]+))\s*$", re.MULTILINE
)


def _frontmatter(path: Path) -> dict[str, str]:
    match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
    assert match, f"{path} has no frontmatter block"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        assert sep, f"{path}: frontmatter line {line!r} is not 'key: value'"
        fields[key.strip()] = value.strip()
    return fields


def _python_blocks(path: Path) -> list[tuple[bool, str]]:
    """Return ``(is_complete, source)`` for every python fence in ``path``."""
    return [
        (bool(m.group("marker")), m.group("body"))
        for m in _PYTHON_FENCE.finditer(path.read_text(encoding="utf-8"))
    ]


def _imports(source: str) -> list[tuple[str, str | None]]:
    """Return ``(module, name)`` pairs imported by ``source``; ``name`` is None for ``import x``."""
    try:
        tree = ast.parse(source)
    except SyntaxError:  # a partial snippet: fall back to one-line import statements
        pairs: list[tuple[str, str | None]] = []
        for from_module, names, module in _SINGLE_LINE_IMPORT.findall(source):
            if module:
                pairs.append((module, None))
            else:
                pairs.extend(
                    (from_module, name.strip()) for name in names.split(",") if name.strip()
                )
        return pairs
    pairs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            pairs.extend((node.module, alias.name) for alias in node.names)
        elif isinstance(node, ast.Import):
            pairs.extend((alias.name, None) for alias in node.names)
    return pairs


def _first_party_imports(paths: list[Path]) -> list[tuple[str, str, str | None]]:
    return [
        (path.parent.name, module, name)
        for path in paths
        for _, source in _python_blocks(path)
        for module, name in _imports(source)
        if module.split(".", 1)[0] in FIRST_PARTY
    ]


def test_skills_and_agents_are_shipped() -> None:
    """
    Scenario: the user-facing skills and agents exist
      Given the repository checkout
      When  the skills/ and agents/ folders are listed
      Then  there is at least one skill and one agent
    """
    assert SKILL_FILES
    assert AGENT_FILES


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_skill_frontmatter_names_its_folder(path: Path) -> None:
    """
    Scenario: a skill's frontmatter matches its folder
      Given a skills/<name>/SKILL.md file
      When  its frontmatter is read
      Then  ``name`` equals the folder name and ``description`` is not empty
    """
    fields = _frontmatter(path)
    assert fields.get("name") == path.parent.name
    assert fields.get("description")


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_agent_frontmatter_names_its_file(path: Path) -> None:
    """
    Scenario: an agent's frontmatter matches its file
      Given an agents/<name>.md file
      When  its frontmatter is read
      Then  ``name`` equals the file stem and ``description`` and ``tools`` are not empty
    """
    fields = _frontmatter(path)
    assert fields.get("name") == path.stem
    assert fields.get("description")
    assert fields.get("tools")


@pytest.mark.parametrize("path", AGENT_FILES, ids=lambda p: p.stem)
def test_agents_only_name_shipped_skills(path: Path) -> None:
    """
    Scenario: an agent refers only to skills that exist
      Given an agent that names hyperadmin-* skills
      When  each named skill is looked up in skills/
      Then  every one of them exists
    """
    shipped = {skill.parent.name for skill in SKILL_FILES}
    named = set(re.findall(r"`(hyperadmin-[a-z-]+)`", path.read_text(encoding="utf-8")))
    assert named
    assert named <= shipped, f"unknown skills: {sorted(named - shipped)}"


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.parent.name)
def test_complete_python_blocks_parse(path: Path) -> None:
    """
    Scenario: complete code blocks are valid Python
      Given a skill with python fences marked complete
      When  each marked block is parsed
      Then  it compiles without a syntax error
    """
    for complete, source in _python_blocks(path):
        if complete:
            compile(source, f"{path}:block", "exec", flags=ast.PyCF_ONLY_AST)


@pytest.mark.parametrize(
    ("skill", "module", "name"),
    _first_party_imports(SKILL_FILES),
    ids=str,
)
def test_skill_imports_resolve(skill: str, module: str, name: str | None) -> None:
    """
    Scenario: every hyperadmin import a skill shows exists
      Given a skill code block importing from hyperadmin or a first-party plugin
      When  the module and name are imported
      Then  both resolve
    """
    imported = importlib.import_module(module)
    if name is None or hasattr(imported, name):
        return
    importlib.import_module(f"{module}.{name}")  # ``from pkg import submodule``


def test_import_extraction_falls_back_for_partial_snippets() -> None:
    """
    Scenario: a partial snippet still yields its imports
      Given a code block that is not valid Python on its own
      When  its imports are extracted
      Then  one-line ``from`` and ``import`` statements are returned
    """
    source = "from hyperadmin import Admin, NavGroup\nimport hyperadmin.filters\nclass X(:\n"
    assert _imports(source) == [
        ("hyperadmin", "Admin"),
        ("hyperadmin", "NavGroup"),
        ("hyperadmin.filters", None),
    ]
