"""Story readiness and dispatch planning of the autopilot (ops/autopilot/lib/ready.py, plan.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "ops" / "autopilot" / "lib"))

import plan
import ready

EPIC = "epic-demo"
BOT = "hyperadmin-bot"


def story_text(
    story_id: str,
    *,
    title: str = "feat(core): something",
    status: str = "todo",
    priority: str = "medium",
    labels: tuple[str, ...] = ("agent-task",),
    issue: int | None = None,
    files: tuple[str, ...] = (),
    blocked_by: tuple[str, ...] = (),
) -> str:
    """Render a ``.meta`` story file the way GitPM writes it."""
    lines = [
        "---",
        "type: story",
        f"id: {story_id}",
        f'title: "{title}"',
        f"status: {status}",
        f"priority: {priority}",
        "assignee: null",
        "labels:",
        *[f"  - {label}" for label in labels],
        "epic_ref:",
        "  id: ep-demo-01",
    ]
    if issue is not None:
        lines += ["github:", f"  issue_number: {issue}", "  repo: owner/repo"]
    lines += ["---", "", "## Summary", "", "Text."]
    if files:
        lines += ["", "## Files to Change", "", *[f"- `{path}`" for path in files]]
    lines += ["", "## Blocked by", "", *[f"- {ref}" for ref in blocked_by or ("none",)]]
    lines += ["", "## Parent", "", f"- Epic: `{EPIC}`", ""]
    return "\n".join(lines)


def make_story(story_id: str, **kwargs: object) -> ready.Story:
    """Build a parsed story of the demo epic; the file stem is ``story-<id>``."""
    epic = kwargs.pop("epic", EPIC)
    return ready.parse_story(story_text(story_id, **kwargs), f"story-{story_id}", epic)  # type: ignore[arg-type]


def make_meta(*stories: ready.Story, epic_status: str = "todo") -> ready.Meta:
    meta = ready.Meta()
    for slug in {story.epic for story in stories if story.epic}:
        meta.epics[slug] = ready.Epic(slug=slug, id=f"ep-{slug}", title=slug, status=epic_status)
    meta.stories = list(stories)
    return meta


def select(*stories: ready.Story, **kwargs: object) -> tuple[list[str], dict[str, str]]:
    """Run ``select_ready`` over the stories and return the picked ids and the skip reasons."""
    kwargs.setdefault("done", set())
    kwargs.setdefault("in_flight", {})
    picked, skipped = ready.select_ready(list(stories), make_meta(*stories).index(), **kwargs)  # type: ignore[arg-type]
    return [story.id for story in picked], skipped


# --- frontmatter ----------------------------------------------------------------------------


def test_parse_frontmatter_reads_scalars_lists_and_nested_maps() -> None:
    text = (
        "---\n"
        "type: story\n"
        "id: uqdz7fJRu_fC\n"
        'title: "feat(adapters): keyset pagination: part one"\n'
        "assignee: null\n"
        "estimate: ~\n"
        "labels:\n"
        "  - agent-task\n"
        "  - size:L\n"
        "tags: [a, 'b c', 3]\n"
        "# a comment\n"
        "epic_ref:\n"
        "  id: ep-v070b-keyset-01\n"
        "github:\n"
        "  issue_number: 228\n"
        "  repo: owner/repo\n"
        "---\n"
        "\n"
        "## Context\n"
        "Body.\n"
    )

    data, body = ready.parse_frontmatter(text)

    assert data == {
        "type": "story",
        "id": "uqdz7fJRu_fC",
        "title": "feat(adapters): keyset pagination: part one",
        "assignee": None,
        "estimate": None,
        "labels": ["agent-task", "size:L"],
        "tags": ["a", "b c", 3],
        "epic_ref": {"id": "ep-v070b-keyset-01"},
        "github": {"issue_number": 228, "repo": "owner/repo"},
    }
    assert body == "\n## Context\nBody.\n"


@pytest.mark.parametrize("text", ["no frontmatter here\n", "---\nid: x\nnever closed\n"])
def test_parse_frontmatter_without_a_block_returns_the_text(text: str) -> None:
    assert ready.parse_frontmatter(text) == ({}, text)


def test_parse_story_reduces_a_file_to_what_dispatch_needs() -> None:
    story = make_story(
        "st-1",
        title="fix(views): detail panel",
        priority="high",
        labels=("agent-task", "deferred"),
        issue=42,
        files=("src/hyperadmin/views/detail.py", "pyproject.toml"),
        blocked_by=("#41 (spec approval)",),
    )

    assert story.id == "st-1"
    assert story.stem == "story-st-1"
    assert story.epic == EPIC
    assert story.status == "todo"
    assert story.priority == "high"
    assert story.labels == {"agent-task", "deferred"}
    assert story.issue == 42
    assert story.files == {"src/hyperadmin/views/detail.py", "pyproject.toml"}
    assert story.deps == ("#41",)
    assert story.is_spec is False


def test_parse_story_falls_back_to_the_file_stem_and_backlog() -> None:
    story = ready.parse_story("no frontmatter\n", "orphan", None)

    assert (story.id, story.status, story.epic, story.issue) == ("orphan", "backlog", None, None)


# --- dependencies ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "refs"),
    [
        ("## Blocked by\n\n- none\n", []),
        ("## Blocked by\n\n- —\n", []),
        ("## Blocked by\n\n- #226\n- #227 (core contract)\n", ["#226", "#227"]),
        (
            (
                "## Blocked by\n\n- `builddeps-one-lane-policy` (st-conflict-01) — creates the"
                " `docs/contributing.md` stub\n"
            ),
            ["builddeps-one-lane-policy"],
        ),
        ("## Blocked by\n\n- (st-rh-00)\n", ["st-rh-00"]),
        (
            "## Dependencies\n- Blocked by: #228 (A4.3 adapter impl), C2.3 (#234)\n- Blocking: A4.5\n",
            ["#228", "#234"],
        ),
        ("## Dependencies\n- Blocked by: none\n- Blocking: #999\n", []),
        ("## Dependencies\nDepends on: #10, #11\n", ["#10", "#11"]),
        (
            "## Dependencies\n**Depends on:** `feat-plugin-tasks-ui-dashboard`\n",
            ["feat-plugin-tasks-ui-dashboard"],
        ),
        (
            "## Dependencies\npgtask ships abi3 wheels; see #77 for the sdist\n- Task 1.1.1: design\n",
            [],
        ),
        ("## Dependencies\n- #12\n- `other-story`\n", ["#12", "other-story"]),
        (
            "## Blocked by\n\n- ConnectionRegistry implementation\n",
            ["?ConnectionRegistry implementation"],
        ),
        ("## Blocked by\n\n- #5\n\n## Parent\n\n- Epic: #900\n", ["#5"]),
        ("## Blocked by\n- #5\n- #5 again\n", ["#5"]),
        ("## Summary\n\nMentions #1 and `a-story` outside a dependency section.\n", []),
        ("### Depends on\n- #3\n### Notes\n- #4\n", ["#3"]),
    ],
)
def test_dependency_refs(body: str, refs: list[str]) -> None:
    assert ready.dependency_refs(body) == refs


def test_unmet_dependencies_explains_each_open_ref() -> None:
    done_dep = make_story("st-done", status="done", issue=1)
    open_dep = make_story("st-open", issue=2)
    merged_dep = make_story("st-merged", issue=3)
    story = make_story(
        "st-x", blocked_by=("#1", "#2", "#3", "#404", "`story-st-open`", "words only")
    )
    index = make_meta(done_dep, open_dep, merged_dep, story).index()

    assert ready.unmet_dependencies(story, index, done={"st-merged"}) == [
        "waits for #2 (todo)",
        "unknown dependency #404",
        "waits for story-st-open (todo)",
        "dependency in words only: 'words only'",
    ]


def test_a_dependency_on_an_epic_issue_follows_the_epic_status() -> None:
    meta = make_meta(make_story("st-x", blocked_by=("#500",)))
    meta.epics["epic-other"] = ready.Epic(slug="epic-other", id="ep-o", status="done", issue=500)
    story = meta.stories[0]

    assert ready.unmet_dependencies(story, meta.index(), set()) == []

    meta.epics["epic-other"] = ready.Epic(slug="epic-other", id="ep-o", status="todo", issue=500)
    assert ready.unmet_dependencies(story, meta.index(), set()) == ["waits for #500 (todo)"]


# --- readiness ------------------------------------------------------------------------------


def test_only_todo_stories_are_ready() -> None:
    picked, skipped = select(
        make_story("st-todo", files=("a.py",)),
        make_story("st-backlog", status="backlog", files=("b.py",)),
        make_story("st-progress", status="in_progress", files=("c.py",)),
        make_story("st-done", status="done", files=("d.py",)),
        make_story("st-cancelled", status="cancelled", files=("e.py",)),
    )

    assert picked == ["st-todo"]
    assert skipped == {
        "st-backlog": "status backlog",
        "st-progress": "status in_progress",
        "st-done": "status done",
        "st-cancelled": "status cancelled",
    }


def test_deferred_and_needs_human_stories_are_skipped() -> None:
    picked, skipped = select(
        make_story("st-deferred", labels=("agent-task", "deferred"), files=("a.py",)),
        make_story("st-human", labels=("needs-human",), files=("b.py",)),
        make_story("st-issue", issue=77, files=("c.py",)),
        make_story("st-ok", issue=78, files=("d.py",)),
        blocked_issues={77},
    )

    assert picked == ["st-ok"]
    assert skipped == {
        "st-deferred": "deferred",
        "st-human": "needs-human",
        "st-issue": "needs-human",
    }


def test_a_story_waits_until_every_dependency_is_done() -> None:
    first = make_story("st-1", issue=1, files=("a.py",))
    second = make_story("st-2", issue=2, files=("b.py",), blocked_by=("#1",))
    third = make_story("st-3", issue=3, files=("c.py",), blocked_by=("#1", "`story-st-2`"))

    assert select(first, second, third) == (
        ["st-1"],
        {
            "st-2": "waits for #1 (todo)",
            "st-3": "waits for #1 (todo); waits for story-st-2 (todo)",
        },
    )


def test_a_dependency_merged_into_the_epic_branch_counts_as_done() -> None:
    first = make_story("st-1", issue=1, files=("a.py",))
    second = make_story("st-2", issue=2, files=("b.py",), blocked_by=("#1",))
    third = make_story("st-3", issue=3, files=("c.py",), blocked_by=("#2",))

    picked, skipped = select(first, second, third, done={"st-1"})

    assert picked == ["st-2"]
    assert skipped == {"st-1": "already merged", "st-3": "waits for #2 (todo)"}


def test_a_dependency_done_in_meta_counts_as_done() -> None:
    first = make_story("st-1", status="done", issue=1)
    second = make_story("st-2", issue=2, files=("b.py",), blocked_by=("#1",))

    assert select(first, second)[0] == ["st-2"]


def test_unknown_and_cancelled_dependencies_block() -> None:
    cancelled = make_story("st-c", status="cancelled", issue=9)
    picked, skipped = select(
        cancelled,
        make_story("st-1", files=("a.py",), blocked_by=("#404",)),
        make_story("st-2", files=("b.py",), blocked_by=("#9",)),
    )

    assert picked == []
    assert skipped["st-1"] == "unknown dependency #404"
    assert skipped["st-2"] == "waits for #9 (cancelled)"


def test_the_spec_gate_is_never_dispatched_as_a_story() -> None:
    spec = make_story("st-00", title="review(spec): approve the SDD", labels=("needs-human",))

    assert spec.is_spec is True
    assert select(spec) == ([], {"st-00": "spec gate (handled by approve-sdd)"})


def test_stories_in_flight_or_out_of_budget_are_skipped() -> None:
    flying = make_story("st-1", files=("a.py",))
    spent = make_story("st-2", files=("b.py",))
    free = make_story("st-3", files=("c.py",))

    picked, skipped = select(flying, spent, free, in_flight={"st-1": flying}, exhausted={"st-2"})

    assert picked == ["st-3"]
    assert skipped == {"st-1": "in flight", "st-2": "implement budget spent"}


def test_dispatch_order_is_priority_then_issue_number() -> None:
    picked, _ = select(
        make_story("st-low", priority="low", issue=1, files=("a.py",)),
        make_story("st-medium-9", issue=9, files=("b.py",)),
        make_story("st-medium-2", issue=2, files=("c.py",)),
        make_story("st-critical", priority="critical", issue=50, files=("d.py",)),
        make_story("st-high", priority="high", issue=40, files=("e.py",)),
    )

    assert picked == ["st-critical", "st-high", "st-medium-2", "st-medium-9", "st-low"]


def test_slots_bound_the_number_of_picks() -> None:
    stories = [make_story(f"st-{n}", issue=n, files=(f"f{n}.py",)) for n in range(1, 5)]

    picked, skipped = select(*stories, slots=2)

    assert picked == ["st-1", "st-2"]
    assert skipped == {"st-3": "no free slot", "st-4": "no free slot"}


# --- overlap and hotspots at dispatch -------------------------------------------------------


def test_a_story_sharing_a_file_with_a_running_story_waits() -> None:
    running = make_story("st-run", files=("src/hyperadmin/views/list.py",))
    same = make_story("st-same", issue=1, files=("src/hyperadmin/views/list.py", "tests/unit/a.py"))
    other = make_story("st-other", issue=2, files=("src/hyperadmin/views/detail.py",))

    picked, skipped = select(running, same, other, in_flight={"st-run": running})

    assert picked == ["st-other"]
    assert skipped["st-same"] == "overlaps st-run: src/hyperadmin/views/list.py"


def test_a_hotspot_owned_by_a_running_story_blocks_other_stories() -> None:
    running = make_story("st-run", files=(".github/workflows/ci.yml", "src/a.py"))
    workflow = make_story("st-ci", issue=1, files=(".github/workflows/test.yml",))
    lock = make_story("st-deps", issue=2, files=("uv.lock",))

    picked, skipped = select(running, workflow, lock, in_flight={"st-run": running})

    assert picked == ["st-deps"]
    assert skipped["st-ci"] == "overlaps st-run: .github/"


def test_a_running_story_in_another_epic_also_blocks() -> None:
    running = make_story("st-run", epic="epic-other", files=("pyproject.toml",))
    candidate = make_story("st-deps", files=("uv.lock",))

    _, skipped = select(running, candidate, in_flight={"st-run": running})

    assert skipped["st-deps"] == "overlaps st-run: pyproject.toml + uv.lock"


def test_two_ready_stories_that_overlap_are_not_picked_together() -> None:
    first = make_story("st-1", issue=1, files=("src/widgets/",))
    second = make_story("st-2", issue=2, files=("src/widgets/select.py",))
    third = make_story("st-3", issue=3, files=("src/forms.py",))

    picked, skipped = select(first, second, third)

    assert picked == ["st-1", "st-3"]
    assert skipped == {"st-2": "overlaps st-1: src/widgets"}


def test_a_story_without_a_files_section_runs_alone_in_its_epic() -> None:
    unknown = make_story("st-unknown", issue=1)
    known = make_story("st-known", issue=2, files=("src/a.py",))
    elsewhere = make_story("st-elsewhere", epic="epic-other", issue=3, files=("src/b.py",))

    picked, skipped = select(unknown, known, elsewhere)

    assert picked == ["st-unknown", "st-elsewhere"]
    assert skipped == {"st-known": "st-unknown has no files section and runs alone in its epic"}


def test_a_story_without_a_files_section_waits_for_its_epic_to_be_idle() -> None:
    running = make_story("st-run", files=("src/a.py",))
    unknown = make_story("st-unknown")

    _, skipped = select(running, unknown, in_flight={"st-run": running})

    assert skipped["st-unknown"] == "no files section, runs alone in its epic (after st-run)"


# --- small helpers --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "branch"),
    [
        ({"title": "feat(adapters): keyset", "issue": 228}, "feat/228-story-st-1"),
        ({"title": "test: unit tests"}, "test/st-1"),
        ({"title": "Refactor(core): lazy exports"}, "refactor/st-1"),
        ({"title": "(untyped) title"}, "feat/st-1"),
    ],
)
def test_story_branch(kwargs: dict[str, object], branch: str) -> None:
    assert make_story("st-1", **kwargs).branch == branch


def test_story_branch_is_a_safe_ref_name() -> None:
    story = ready.parse_story(story_text("ab cd/ef~1"), "stem", EPIC)

    assert story.branch == "feat/ab-cd-ef-1"


def test_epic_branch_is_the_directory_name() -> None:
    assert ready.Epic(slug="epic-v070b-keyset").branch == "epic/epic-v070b-keyset"


@pytest.mark.parametrize(
    ("body", "story_id"),
    [
        ("Summary\n\nStory: st-conflict-04\n\n## Assumptions\n", "st-conflict-04"),
        ("Story: `uqdz7fJRu_fC`\n", "uqdz7fJRu_fC"),
        ("Story:st-1  \nmore", "st-1"),
        ("User Story: as an admin\n", None),
        ("The Story: st-1 line must start the line\n", None),
        ("", None),
        (None, None),
    ],
)
def test_story_id_from_body(body: str | None, story_id: str | None) -> None:
    assert ready.story_id_from_body(body) == story_id


EPIC_MD = """\
---
type: epic
id: ep-demo-01
title: "epic(core): demo"
status: todo
priority: medium
labels:
  - planned
---

## Overview

status: todo in the body stays as it is.
"""


def test_open_epic_text_sets_the_lock_fields() -> None:
    opened = ready.open_epic_text(EPIC_MD, EPIC)

    assert opened == EPIC_MD.replace(
        "status: todo\npriority",
        "status: in_progress\nlocked_by: autopilot\nbranch: epic/epic-demo\npriority",
    )
    assert ready.parse_epic(opened, EPIC).status == "in_progress"
    assert ready.open_epic_text(opened, EPIC) == opened


def test_open_epic_text_adds_a_missing_status() -> None:
    opened = ready.open_epic_text("---\ntype: epic\nid: e\n---\nbody\n", "s")

    assert opened == (
        "---\ntype: epic\nid: e\nstatus: in_progress\nlocked_by: autopilot\nbranch: epic/s\n---\nbody\n"
    )


def test_open_epic_text_rejects_a_file_without_frontmatter() -> None:
    with pytest.raises(ValueError, match="no frontmatter"):
        ready.open_epic_text("# just markdown\n", EPIC)


# --- loading a tree and the command line ----------------------------------------------------


@pytest.fixture
def meta_dir(tmp_path: Path) -> Path:
    """A small ``.meta`` tree: one epic with three stories and one standalone story."""
    stories = tmp_path / "epics" / EPIC / "stories"
    stories.mkdir(parents=True)
    (tmp_path / "epics" / EPIC / "epic.md").write_text(EPIC_MD)
    (stories / "first.md").write_text(story_text("st-1", issue=1, files=("src/a.py",)))
    (stories / "second.md").write_text(
        story_text("st-2", issue=2, files=("src/b.py",), blocked_by=("#1",))
    )
    (stories / "third.md").write_text(story_text("st-3", issue=3, files=("src/a.py",)))
    (tmp_path / "stories").mkdir()
    (tmp_path / "stories" / "alone.md").write_text(story_text("st-alone", status="backlog"))
    return tmp_path


def test_load_meta_reads_epics_and_stories(meta_dir: Path) -> None:
    meta = ready.load_meta(meta_dir)

    assert list(meta.epics) == [EPIC]
    assert meta.epics[EPIC].title == "epic(core): demo"
    assert [(story.id, story.stem, story.epic) for story in meta.stories] == [
        ("st-1", "first", EPIC),
        ("st-2", "second", EPIC),
        ("st-3", "third", EPIC),
        ("st-alone", "alone", None),
    ]
    assert [story.id for story in meta.stories_of(EPIC)] == ["st-1", "st-2", "st-3"]
    index = meta.index()
    assert index["#2"] is index["second"] is index["st-2"]
    assert index[EPIC] is meta.epics[EPIC]


def test_cli_report_lists_ready_and_blocked_stories(
    meta_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert ready.main(["report", str(meta_dir), EPIC]) == 0

    assert capsys.readouterr().out.splitlines() == [
        f"READY    {EPIC}  st-1  feat(core): something",
        f"BLOCKED  {EPIC}  st-2  waits for #1 (todo)",
        f"BLOCKED  {EPIC}  st-3  overlaps st-1: src/a.py",
        "1 ready, 3 stories read",
    ]


def test_cli_open_epic_prints_the_locked_file(
    meta_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert ready.main(["open-epic", str(meta_dir / "epics" / EPIC / "epic.md"), EPIC]) == 0
    assert "status: in_progress\nlocked_by: autopilot\nbranch: epic/epic-demo\n" in (
        capsys.readouterr().out
    )


def test_cli_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert ready.main(["nonsense"]) == 2
    assert "ready.py report META_DIR" in capsys.readouterr().err


# --- the planner: epics and story dispatch --------------------------------------------------


def epic_pr(number: int = 100, *, draft: bool = True, labels: tuple[str, ...] = ()) -> dict:
    return {
        "number": number,
        "title": "epic(core): demo",
        "author": {"login": BOT},
        "baseRefName": "develop",
        "headRefName": f"epic/{EPIC}",
        "isDraft": draft,
        "mergeable": "MERGEABLE",
        "labels": [{"name": label} for label in labels],
        "body": "",
        "statusCheckRollup": [],
    }


def story_pr(number: int, story_id: str) -> dict:
    return {
        "number": number,
        "title": "feat(core): something",
        "author": {"login": BOT},
        "baseRefName": f"epic/{EPIC}",
        "headRefName": f"feat/{story_id}",
        "isDraft": True,
        "mergeable": "MERGEABLE",
        "labels": [],
        "body": f"Story: {story_id}\n",
        "statusCheckRollup": [],
    }


def plan_rows(meta: ready.Meta, **inputs: object) -> list[tuple[str, ...]]:
    """Build a plan for one active demo epic and return ``(kind, *args)`` rows without info."""
    base: dict[str, object] = {
        "now": 1_800_000_000,
        "limit": 3,
        "pool": 3,
        "bot": BOT,
        "meta": meta,
        "epic_branches": [f"epic/{EPIC}"],
        "prs": [epic_pr()],
    }
    base.update(inputs)
    return [
        (action.kind, *action.args[:2]) for action in plan.build_plan(base) if action.kind != "info"
    ]


def test_ready_stories_of_an_open_epic_are_dispatched_into_free_slots() -> None:
    meta = make_meta(
        make_story("st-1", issue=1, files=("src/a.py",)),
        make_story("st-2", issue=2, files=("src/b.py",)),
        make_story("st-3", issue=3, files=("src/c.py",), blocked_by=("#1",)),
        epic_status="in_progress",
    )

    actions = plan.build_plan(
        {
            "now": 1_800_000_000,
            "limit": 3,
            "pool": 3,
            "bot": BOT,
            "meta": meta,
            "epic_branches": [f"epic/{EPIC}"],
            "prs": [epic_pr()],
        }
    )

    spawns = [action for action in actions if action.kind == "spawn"]
    assert [action.args[:5] for action in spawns] == [
        ("implement", "st-1", "1", "feat/1-story-st-1", f"origin/epic/{EPIC}"),
        ("implement", "st-2", "2", "feat/2-story-st-2", f"origin/epic/{EPIC}"),
    ]
    assert json.loads(spawns[0].args[5]) == {
        "base": f"origin/epic/{EPIC}",
        "branch": "feat/1-story-st-1",
        "epic_of_story": EPIC,
        "issue": 1,
        "story": "st-1",
        "target": "st-1",
    }
    waits = [action.why for action in actions if action.kind == "info"]
    assert "story st-3 waits: waits for #1 (todo)" in waits


def test_a_story_merged_into_the_epic_branch_unblocks_its_dependants() -> None:
    meta = make_meta(
        make_story("st-1", issue=1, files=("src/a.py",)),
        make_story("st-2", issue=2, files=("src/b.py",), blocked_by=("#1",)),
    )

    rows = plan_rows(meta, merged={EPIC: [{"number": 7, "body": "Story: st-1\n"}]})

    assert rows == [("spawn", "implement", "st-2")]


def test_a_story_with_an_open_pull_request_is_in_flight_and_holds_its_files() -> None:
    meta = make_meta(
        make_story("st-1", issue=1, files=("src/a.py",)),
        make_story("st-2", issue=2, files=("src/a.py",)),
        make_story("st-3", issue=3, files=("src/c.py",)),
    )

    rows = plan_rows(meta, prs=[epic_pr(), story_pr(201, "st-1")])

    assert rows == [("spawn", "implement", "st-3")]


def test_a_running_implement_job_is_in_flight_and_holds_its_slot() -> None:
    meta = make_meta(
        make_story("st-1", issue=1, files=("src/a.py",)),
        make_story("st-2", issue=2, files=("src/b.py",)),
    )
    state = {"jobs": {"j1": {"kind": "implement", "story": "st-1", "slot": 1, "pid": 1}}}

    actions = plan.build_plan(
        {
            "now": 1_800_000_000,
            "limit": 3,
            "pool": 3,
            "bot": BOT,
            "meta": meta,
            "epic_branches": [f"epic/{EPIC}"],
            "prs": [epic_pr()],
            "state": state,
        }
    )

    spawns = [action.args[:3] for action in actions if action.kind == "spawn"]
    assert spawns == [("implement", "st-2", "2")]


def test_an_epic_branch_without_a_pull_request_gets_its_draft() -> None:
    meta = make_meta(make_story("st-1", status="backlog"))

    assert plan_rows(meta, prs=[]) == [("open-epic-pr", EPIC)]


def test_the_spec_gate_runs_before_any_story() -> None:
    meta = make_meta(
        make_story("st-00", title="review(spec): approve the SDD", issue=1),
        make_story("st-1", issue=2, files=("src/a.py",)),
    )

    assert plan_rows(meta) == [("spawn", "approve-sdd", EPIC)]
    assert plan_rows(meta, state={"epics": {EPIC: {"spec": "approved"}}}) == [
        ("spawn", "implement", "st-1")
    ]
    assert plan_rows(meta, state={"epics": {EPIC: {"spec": "escalated"}}}) == [("note",)]
    assert plan_rows(meta, state={"epics": {EPIC: {"sdd": 2}}}) == [("note",)]


def test_a_finished_epic_is_integrated_once_no_story_pull_request_is_open() -> None:
    meta = make_meta(
        make_story("st-1", issue=1, files=("src/a.py",)),
        make_story("st-2", status="cancelled"),
    )
    merged = {EPIC: [{"number": 7, "body": "Story: st-1\n"}]}

    assert plan_rows(meta, merged=merged) == [("spawn", "integrate-epic", EPIC)]
    assert plan_rows(meta, merged=merged, prs=[epic_pr(), story_pr(201, "st-9")]) == []
    assert plan_rows(meta, merged=merged, prs=[epic_pr(labels=("needs-human",))]) == [("note",)]
    assert plan_rows(meta, merged=merged, state={"epics": {EPIC: {"integrate": 2}}}) == [("note",)]


def test_an_epic_handed_to_the_owner_is_frozen() -> None:
    meta = make_meta(make_story("st-1", issue=1, files=("src/a.py",)))

    actions = plan.build_plan(
        {
            "now": 1_800_000_000,
            "limit": 3,
            "bot": BOT,
            "meta": meta,
            "epic_branches": [f"epic/{EPIC}"],
            "prs": [epic_pr(draft=False)],
        }
    )

    assert [(action.kind, action.why) for action in actions] == [
        ("note", f"epic PR #100 ({EPIC}) is ready and waits for the owner")
    ]


def test_epics_are_opened_only_when_enabled_and_while_there_is_room() -> None:
    meta = make_meta(
        make_story("st-a", epic="epic-a", files=("a.py",)),
        make_story("st-b", epic="epic-b", files=("b.py",)),
        make_story("st-c", epic="epic-c", status="backlog"),
    )
    meta.epics["epic-b"] = ready.Epic(slug="epic-b", status="todo", priority="high")
    meta.epics["epic-d"] = ready.Epic(slug="epic-d", status="todo", labels=frozenset({"deferred"}))
    meta.epics["epic-e"] = ready.Epic(slug="epic-e", status="backlog")

    def opened(**inputs: object) -> list[tuple[str, ...]]:
        return plan_rows(meta, epic_branches=[], prs=[], **inputs)

    assert opened() == []
    assert opened(epic_allow="epic-a") == [("open-epic", "epic-a")]
    assert opened(epic_allow="epic-.*", max_epics=2) == [
        ("open-epic", "epic-b"),
        ("open-epic", "epic-a"),
    ]
    assert opened(epic_allow="epic-.*", max_epics=1) == [("open-epic", "epic-b")]
    assert opened(epic_allow="epic") == []
    assert opened(epic_allow="epic-(") == [("note",)]


def test_an_epic_in_progress_takes_an_epic_lane() -> None:
    meta = make_meta(
        make_story("st-1", issue=1, files=("src/a.py",)),
        make_story("st-b", epic="epic-b", files=("b.py",)),
    )

    rows = plan_rows(meta, epic_allow="epic-b", max_epics=1)

    assert rows == [("spawn", "implement", "st-1")]
    assert ("open-epic", "epic-b") in plan_rows(meta, epic_allow="epic-b", max_epics=2)
