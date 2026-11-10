#!/usr/bin/env python3
"""Story readiness for autopilot dispatch.

Loads a ``.meta`` tree and decides which stories may start now: status ``todo``, not
``deferred``, every dependency done, and no touched-file overlap with a story that is already
in flight. Also holds the small text helpers the tick needs for the open-epic commit and for
linking a pull request back to its story.

Pure standard library (no PyYAML, no ``gh``, no network): the tick runs it with the system
``python3`` and the unit tests import it directly.

Usage:
  ready.py report META_DIR [EPIC_SLUG ...]   print ready and blocked stories from a local tree
  ready.py open-epic EPIC_MD SLUG            print epic.md with the lock fields set
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import overlap

PRIORITY = {"critical": 0, "high": 1, "medium": 2, "low": 3}
EPIC_BRANCH_PREFIX = "epic/"
STORY_LINE = re.compile(r"^Story:[ \t]*`?([A-Za-z0-9_.-]+)`?[ \t]*$", re.MULTILINE)
DEP_SECTION = re.compile(
    r"^##+[ \t]*(blocked by|dependencies|depends on)[ \t]*$", re.IGNORECASE | re.MULTILINE
)
HEADING = re.compile(r"^#+\s", re.MULTILINE)
DEP_LABEL = re.compile(r"^(blocked by|depends on)[ \t]*:[ \t]*", re.IGNORECASE)
ISSUE_REF = re.compile(r"#(\d+)")
STEM_REF = re.compile(r"`([A-Za-z0-9][A-Za-z0-9_-]*)`")
ID_REF = re.compile(r"\((st-[A-Za-z0-9_-]+)\)")
EM_DASH, EN_DASH = chr(0x2014), chr(0x2013)
NOTHING = {"", "none", "n/a", "na", "-", EM_DASH, EN_DASH, "nothing"}
# A dash with spaces around it starts a free-text remark; refs are read from what precedes it.
DASHES = re.compile(rf"\s(?:{EM_DASH}|{EN_DASH}|--)\s")
UNSAFE_BRANCH = re.compile(r"[^A-Za-z0-9._-]+")
STEM_LIMIT = 40


def _scalar(value: str) -> object:
    """Convert one YAML scalar (or flow list) to a Python value."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        return [_scalar(item) for item in value[1:-1].split(",") if item.strip()]
    if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if value in {"", "null", "~"}:
        return None
    if value.isdigit():
        return int(value)
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Split a ``.meta`` file into its frontmatter and body.

    Understands the subset GitPM writes: top-level scalars, block and flow lists, and one level
    of nested mappings.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    data: dict[str, object] = {}
    key = ""
    for line in text[3:end].splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[0] not in " \t":
            key, _, value = line.partition(":")
            key = key.strip()
            data[key] = _scalar(value)
        elif key:
            _nested(data, key, stripped)
    body_start = text.find("\n", end + 1)
    return data, "" if body_start == -1 else text[body_start + 1 :]


def _nested(data: dict[str, object], key: str, item: str) -> None:
    """Add an indented frontmatter line (list item or sub-key) under ``key``."""
    current = data.get(key)
    if item.startswith("- "):
        if not isinstance(current, list):
            current = data[key] = []
        current.append(_scalar(item[2:]))
    elif ":" in item:
        if not isinstance(current, dict):
            current = data[key] = {}
        sub, _, value = item.partition(":")
        current[sub.strip()] = _scalar(value)


def _dependency_line(raw: str, *, labelled_only: bool) -> list[str]:
    """Return the dependency refs one line names."""
    line = raw.strip().lstrip("-*").strip()
    if line.lower().startswith("blocking"):
        return []
    label = DEP_LABEL.match(line)
    if label:
        line = line[label.end() :]
    elif labelled_only and not line.startswith(("#", "`")):
        return []
    line = DASHES.split(line + " ", maxsplit=1)[0].strip()
    if line.lower().strip("*_ ") in NOTHING:
        return []
    stems = STEM_REF.findall(line)
    refs = [f"#{number}" for number in ISSUE_REF.findall(line)] + stems
    if not stems:
        refs += ID_REF.findall(line)
    return refs or [f"?{line}"]


def dependency_refs(body: str) -> list[str]:
    """Return the refs a story body says it is blocked by.

    A ref is ``#<issue>``, a story file stem, a story id, or ``?<text>`` for a line that names
    a dependency in words only. ``Blocking:`` lines point the other way and are skipped.
    """
    refs: list[str] = []
    for section in DEP_SECTION.finditer(body):
        text = body[section.end() :]
        following = HEADING.search(text)
        if following:
            text = text[: following.start()]
        labelled_only = section.group(1).lower() == "dependencies"
        for raw in text.splitlines():
            for ref in _dependency_line(raw, labelled_only=labelled_only):
                if ref not in refs:
                    refs.append(ref)
    return refs


@dataclass(frozen=True)
class Story:
    """One ``.meta`` story, reduced to what dispatch needs."""

    id: str
    stem: str
    epic: str | None
    title: str = ""
    status: str = "backlog"
    priority: str = "medium"
    labels: frozenset[str] = frozenset()
    issue: int | None = None
    files: frozenset[str] = frozenset()
    deps: tuple[str, ...] = ()

    @property
    def is_spec(self) -> bool:
        """Tell whether this is the SDD approval gate of its epic."""
        return self.title.lower().startswith("review(spec)")

    @property
    def branch(self) -> str:
        """Return the working branch for this story, typed like its title."""
        kind = re.match(r"[a-z]+", self.title.lower())
        prefix = kind.group(0) if kind else "feat"
        name = f"{self.issue}-{self.stem[:STEM_LIMIT]}" if self.issue else self.id
        return f"{prefix}/{UNSAFE_BRANCH.sub('-', name).strip('-')}"


@dataclass(frozen=True)
class Epic:
    """One ``.meta`` epic."""

    slug: str
    id: str = ""
    title: str = ""
    status: str = "backlog"
    priority: str = "medium"
    labels: frozenset[str] = frozenset()
    issue: int | None = None

    @property
    def branch(self) -> str:
        """Return the epic branch name (the directory name is the slug)."""
        return EPIC_BRANCH_PREFIX + self.slug


@dataclass
class Meta:
    """A loaded ``.meta`` tree."""

    epics: dict[str, Epic] = field(default_factory=dict)
    stories: list[Story] = field(default_factory=list)

    def stories_of(self, slug: str) -> list[Story]:
        """Return the stories of one epic."""
        return [story for story in self.stories if story.epic == slug]

    def index(self) -> dict[str, Story | Epic]:
        """Map every way a dependency can name a story or epic to that item."""
        lookup: dict[str, Story | Epic] = {}
        for epic in self.epics.values():
            lookup[epic.slug] = epic
            if epic.issue:
                lookup[f"#{epic.issue}"] = epic
        for story in self.stories:
            lookup[story.stem] = story
            lookup[story.id] = story
            if story.issue:
                lookup[f"#{story.issue}"] = story
        return lookup


def _labels(data: dict[str, object]) -> frozenset[str]:
    labels = data.get("labels")
    return frozenset(str(label) for label in labels) if isinstance(labels, list) else frozenset()


def _issue(data: dict[str, object]) -> int | None:
    github = data.get("github")
    number = github.get("issue_number") if isinstance(github, dict) else None
    return number if isinstance(number, int) else None


def parse_story(text: str, stem: str, epic: str | None) -> Story:
    """Build a :class:`Story` from the text of a story file."""
    data, body = parse_frontmatter(text)
    return Story(
        id=str(data.get("id") or stem),
        stem=stem,
        epic=epic,
        title=str(data.get("title") or ""),
        status=str(data.get("status") or "backlog"),
        priority=str(data.get("priority") or "medium"),
        labels=_labels(data),
        issue=_issue(data),
        files=frozenset(overlap.files_to_change(body)),
        deps=tuple(dependency_refs(body)),
    )


def parse_epic(text: str, slug: str) -> Epic:
    """Build an :class:`Epic` from the text of an ``epic.md``."""
    data, _ = parse_frontmatter(text)
    return Epic(
        slug=slug,
        id=str(data.get("id") or slug),
        title=str(data.get("title") or ""),
        status=str(data.get("status") or "backlog"),
        priority=str(data.get("priority") or "medium"),
        labels=_labels(data),
        issue=_issue(data),
    )


def load_meta(meta_dir: str | Path) -> Meta:
    """Load every epic and story under a ``.meta`` directory."""
    root = Path(meta_dir)
    meta = Meta()
    for epic_file in sorted(root.glob("epics/*/epic.md")):
        slug = epic_file.parent.name
        meta.epics[slug] = parse_epic(epic_file.read_text(encoding="utf-8"), slug)
    for path in sorted(root.glob("epics/*/stories/*.md")):
        slug = path.parent.parent.name
        meta.stories.append(parse_story(path.read_text(encoding="utf-8"), path.stem, slug))
    for path in sorted(root.glob("stories/*.md")):
        meta.stories.append(parse_story(path.read_text(encoding="utf-8"), path.stem, None))
    return meta


def unmet_dependencies(story: Story, index: dict[str, Story | Epic], done: set[str]) -> list[str]:
    """Return why each unfinished dependency of ``story`` still blocks it."""
    reasons = []
    for ref in story.deps:
        target = index.get(ref)
        if ref.startswith("?"):
            reasons.append(f"dependency in words only: {ref[1:]!r}")
        elif target is None:
            reasons.append(f"unknown dependency {ref}")
        elif target.status != "done" and target.id not in done:
            reasons.append(f"waits for {ref} ({target.status})")
    return reasons


def _own_blockers(story: Story, done: set[str], blocked_issues: set[int]) -> str | None:
    """Return why the story cannot start regardless of other stories."""
    reason = None
    if story.status != "todo":
        reason = f"status {story.status}"
    elif story.id in done:
        reason = "already merged"
    elif story.is_spec:
        reason = "spec gate (handled by approve-sdd)"
    elif "deferred" in story.labels:
        reason = "deferred"
    elif "needs-human" in story.labels or story.issue in blocked_issues:
        reason = "needs-human"
    return reason


def select_ready(
    stories: list[Story],
    index: dict[str, Story | Epic],
    *,
    done: set[str],
    in_flight: dict[str, Story],
    blocked_issues: set[int] | frozenset[int] = frozenset(),
    exhausted: set[str] | frozenset[str] = frozenset(),
    slots: int | None = None,
) -> tuple[list[Story], dict[str, str]]:
    """Pick the stories that may start now.

    Parameters
    ----------
    stories
        Candidates, normally every story of the active epics.
    index
        ``Meta.index()`` of the tree the dependencies are resolved against.
    done
        Story ids finished outside ``.meta`` (merged into the epic branch, approved specs).
    in_flight
        Stories being implemented or under review, keyed by id.
    blocked_issues
        Issue numbers that carry ``needs-human`` on GitHub.
    exhausted
        Story ids whose implement budget is spent.
    slots
        Upper bound on the number of picks (``None`` for no bound).

    Returns
    -------
    tuple
        The picked stories in dispatch order, and a reason for every story left out.
    """
    picked: list[Story] = []
    skipped: dict[str, str] = {}
    ordered = sorted(stories, key=lambda s: (PRIORITY.get(s.priority, 2), s.issue or 0, s.stem))
    for story in ordered:
        if story.id in in_flight:
            skipped[story.id] = "in flight"
            continue
        reason = _own_blockers(story, done, blocked_issues)
        if reason is None and story.id in exhausted:
            reason = "implement budget spent"
        if reason is None:
            unmet = unmet_dependencies(story, index, done)
            reason = "; ".join(unmet) or None
        if reason is None:
            reason = _collision(story, [*in_flight.values(), *picked])
        if reason is None and slots is not None and len(picked) >= slots:
            reason = "no free slot"
        if reason is None:
            picked.append(story)
        else:
            skipped[story.id] = reason
    return picked, skipped


def _collision(story: Story, others: list[Story]) -> str | None:
    """Return why ``story`` cannot run next to ``others`` (``None`` when it can)."""
    same_epic = [other for other in others if other.epic == story.epic]
    if not story.files and same_epic:
        return f"no files section, runs alone in its epic (after {same_epic[0].id})"
    unknown = [other for other in same_epic if not other.files]
    if unknown:
        return f"{unknown[0].id} has no files section and runs alone in its epic"
    clashes = overlap.conflicts(story.files, {other.id: other.files for other in others})
    if clashes:
        name, common = next(iter(clashes.items()))
        return f"overlaps {name}: {', '.join(common)}"
    return None


def story_id_from_body(body: str | None) -> str | None:
    """Return the story id from the ``Story: <id>`` line of a pull request body."""
    match = STORY_LINE.search(body or "")
    return match.group(1) if match else None


def open_epic_text(text: str, slug: str) -> str:
    """Return ``epic.md`` with the lock fields of the open-epic commit set.

    Sets ``status: in_progress`` and writes ``locked_by: autopilot`` and
    ``branch: epic/<slug>`` right after it. Running it twice changes nothing more.
    """
    data, _ = parse_frontmatter(text)
    if not data:
        raise ValueError("epic.md has no frontmatter")
    end = text.find("\n---", 3)
    head = [
        line for line in text[:end].splitlines() if not re.match(r"(locked_by|branch)[ \t]*:", line)
    ]
    lock = ["locked_by: autopilot", f"branch: {EPIC_BRANCH_PREFIX}{slug}"]
    for position, line in enumerate(head):
        if re.match(r"status[ \t]*:", line):
            head[position : position + 1] = ["status: in_progress", *lock]
            break
    else:
        head += ["status: in_progress", *lock]
    return "\n".join(head) + text[end:]


def _report(meta_dir: str, slugs: list[str]) -> int:
    meta = load_meta(meta_dir)
    wanted = [story for story in meta.stories if not slugs or story.epic in slugs]
    picked, skipped = select_ready(wanted, meta.index(), done=set(), in_flight={})
    out = sys.stdout.write
    for story in picked:
        out(f"READY    {story.epic or '-'}  {story.id}  {story.title}\n")
    by_id = {story.id: story for story in wanted}
    for story_id, reason in skipped.items():
        if by_id[story_id].status == "todo":
            out(f"BLOCKED  {by_id[story_id].epic or '-'}  {story_id}  {reason}\n")
    out(f"{len(picked)} ready, {len(wanted)} stories read\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the ``report`` or ``open-epic`` command."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) >= 2 and args[0] == "report":  # noqa: PLR2004
        return _report(args[1], args[2:])
    if len(args) == 3 and args[0] == "open-epic":  # noqa: PLR2004
        sys.stdout.write(open_epic_text(Path(args[1]).read_text(encoding="utf-8"), args[2]))
        return 0
    sys.stderr.write((__doc__ or "").strip() + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
