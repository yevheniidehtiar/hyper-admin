#!/usr/bin/env python3
"""Touched-files parsing and overlap checks for autopilot dispatch.

Reads the "Files to Change" section of ``.meta`` story files and answers one question:
may two stories run at the same time? They may not when they share a file, when one names a
directory the other writes into, or when both touch the same hotspot (see
``.claude/rules/conflict-avoidance.md``).

Pure standard library, no ``gh`` and no network, so the tick can call it for free and the unit
tests can import it directly.

Usage:
  overlap.py STORY.md [STORY.md ...]    print the overlap matrix, exit 1 when anything is shared
"""

from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path

# "## Files to Change" is the convention; older stories say "Files", "Files Likely Affected",
# "Files to modify" or "Files to create", and they are read the same way.
SECTION = re.compile(
    r"^##+[ \t]*Files"
    r"(?:[ \t]+(?:to[ \t]+change|likely[ \t]+affected|likely[ \t]+to[ \t]+change"
    r"|to[ \t]+modify|to[ \t]+create(?:/modify)?))?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
NEXT_SECTION = re.compile(r"^##\s", re.MULTILINE)
# A backticked token that looks like a file (has an extension) or a directory (ends with "/").
PATH = re.compile(r"`([^`\s]*\.[A-Za-z0-9]+|[^`\s]+/)`")

# Hotspots that are a whole class of files: two stories conflict when both touch the class,
# even through different files. The key is what the stories are said to share.
HOTSPOT_GROUPS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pyproject.toml + uv.lock", re.compile(r"^(pyproject\.toml|uv\.lock)$")),
    (".github/", re.compile(r"^\.github(/|$)")),
    ("tests/e2e/snapshots/", re.compile(r"^tests/e2e/snapshots(/|$)")),
)
# Hotspots that are single files: the key is the path itself.
HOTSPOT_FILES = re.compile(
    r"^(\.gitignore|src/hyperadmin/core/app\.py|src/hyperadmin/.*/__init__\.py"
    r"|src/hyperadmin/static/css/(hyperadmin|_tokens)\.css"
    r"|src/hyperadmin/templates/(_base|_sidebar|_navbar)\.html|tests/e2e/conftest\.py)$"
)


def files_to_change(text: str) -> set[str]:
    """Return the paths named in the story's files section (empty when it has none)."""
    match = SECTION.search(text)
    if not match:
        return set()
    body = text[match.end() :]
    following = NEXT_SECTION.search(body)
    if following:
        body = body[: following.start()]
    return {path.strip("/") for path in PATH.findall(body)}


def hotspot_key(path: str) -> str | None:
    """Return the hotspot a path belongs to, or ``None`` for an ordinary file."""
    for key, pattern in HOTSPOT_GROUPS:
        if pattern.match(path):
            return key
    if HOTSPOT_FILES.match(path):
        return path
    return None


def hotspots(files: set[str] | frozenset[str]) -> set[str]:
    """Return the hotspot keys a set of files touches."""
    return {key for key in map(hotspot_key, files) if key is not None}


def paths_overlap(first: str, second: str) -> bool:
    """Tell whether two paths are the same file or one is a directory holding the other."""
    return first == second or first.startswith(second + "/") or second.startswith(first + "/")


def shared(first: set[str] | frozenset[str], second: set[str] | frozenset[str]) -> list[str]:
    """List what two file sets have in common: files, nested paths and hotspot classes."""
    found = {
        min(a, b, key=len)
        for a, b in itertools.product(sorted(first), sorted(second))
        if paths_overlap(a, b)
    }
    found |= hotspots(first) & hotspots(second)
    return sorted(found)


def conflicts(
    candidate: set[str] | frozenset[str], running: dict[str, set[str] | frozenset[str]]
) -> dict[str, list[str]]:
    """Map each running story that collides with ``candidate`` to what they share."""
    result = {}
    for name, files in running.items():
        common = shared(candidate, files)
        if common:
            result[name] = common
    return result


def matrix(stories: dict[str, set[str]]) -> list[tuple[str, str, list[str]]]:
    """Return every pair of stories that share something, with what they share."""
    pairs = []
    for (first, first_files), (second, second_files) in itertools.combinations(stories.items(), 2):
        common = shared(first_files, second_files)
        if common:
            pairs.append((first, second, common))
    return pairs


def main(argv: list[str] | None = None) -> int:
    """Print the overlap matrix for the given story files."""
    paths = sys.argv[1:] if argv is None else argv
    if not paths:
        sys.stderr.write((__doc__ or "").strip() + "\n")
        return 2
    stories = {path: files_to_change(Path(path).read_text(encoding="utf-8")) for path in paths}
    pairs = matrix(stories)
    out = sys.stdout.write
    for first, second, common in pairs:
        out(f"OVERLAP  {first}\n    with {second}\n         {', '.join(common)}\n")
    for name, files in stories.items():
        hot = sorted(hotspots(files))
        if hot:
            out(f"HOTSPOT  {name}: {', '.join(hot)}\n")
    missing = [name for name, files in stories.items() if not files]
    if missing:
        out("NO files section (cannot check): " + ", ".join(missing) + "\n")
    if not pairs:
        out(f"clean: {len(stories)} stories, no shared files\n")
    return 1 if pairs else 0


if __name__ == "__main__":
    sys.exit(main())
