"""Autopilot state: cooldown parsing, retry budgets, jobs and the pull request decisions.

Covers ops/autopilot/lib/state.py and the budget-driven half of ops/autopilot/lib/plan.py.
No ``gh`` and no network: the planner is fed plain dicts, the command line runs in a
subprocess against a temporary state file.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIB = _REPO_ROOT / "ops" / "autopilot" / "lib"
sys.path.insert(0, str(_LIB))

import plan
import state as st

NOW = 1_800_000_000  # 2027-01-15 08:00:00 UTC
UTC = timezone.utc
KYIV = timezone(timedelta(hours=2))
BOT = "hyperadmin-bot"
LIMIT_MESSAGE = "Claude AI usage limit reached|{epoch}"


# --- the state file -------------------------------------------------------------------------


def test_a_missing_state_file_is_an_empty_state(tmp_path: Path) -> None:
    state = st.load(tmp_path / "nowhere" / "state.json")

    assert state == st.new_state()
    assert state["cooldown_until"] == 0
    assert state["janitor"] == {"approved": False, "last_run": 0, "candidates": []}
    assert not (tmp_path / "nowhere").exists()


def test_save_and_load_round_trip_and_leave_no_temp_file(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "state.json"
    state = st.new_state()
    st.bump(state, "prs", 12, "fix")
    state["cooldown_until"] = NOW + 60

    st.save(path, state)

    assert st.load(path) == state
    assert [item.name for item in path.parent.iterdir()] == ["state.json"]


def test_a_state_from_an_older_version_gets_the_missing_keys(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"cooldown_until": 5, "janitor": {"approved": True}, "extra": 1}))

    state = st.load(path)

    assert state["cooldown_until"] == 5
    assert state["janitor"] == {"approved": True, "last_run": 0, "candidates": []}
    assert state["jobs"] == {}
    assert state["digest"] == {"last_date": "", "notes": []}
    assert "extra" not in state


@pytest.mark.parametrize("text", ["{not json", "[]", '{"jobs": []}'])
def test_a_broken_state_file_is_an_error_not_an_empty_state(tmp_path: Path, text: str) -> None:
    path = tmp_path / "state.json"
    path.write_text(text)

    with pytest.raises(st.StateError):
        st.load(path)


def test_set_path_and_get_path() -> None:
    state = st.new_state()

    st.set_path(state, "epics.epic-demo.spec", "approved")
    st.set_path(state, "janitor.approved", True)

    assert st.get_path(state, "epics.epic-demo.spec") == "approved"
    assert st.get_path(state, "epics.epic-demo") == {"spec": "approved"}
    assert st.janitor_approved(state) is True
    assert st.get_path(state, "epics.missing.spec") is None
    assert st.get_path(state, "cooldown_until.deeper") is None
    with pytest.raises(st.StateError):
        st.set_path(state, "cooldown_until.deeper", 1)


def test_the_janitor_is_a_dry_run_until_approved() -> None:
    state = st.new_state()

    assert st.janitor_approved(state) is False
    state["janitor"]["approved"] = "yes"
    assert st.janitor_approved(state) is False
    state["janitor"]["approved"] = True
    assert st.janitor_approved(state) is True


# --- cooldown parsing -----------------------------------------------------------------------


def test_the_epoch_of_the_usage_limit_message_ends_the_cooldown() -> None:
    result = {"is_error": True, "result": LIMIT_MESSAGE.format(epoch=NOW + 7200)}

    assert st.parse_usage_limit(result, now=NOW) == NOW + 7200


def test_an_epoch_in_milliseconds_is_read_as_seconds() -> None:
    result = {"is_error": True, "result": LIMIT_MESSAGE.format(epoch=(NOW + 900) * 1000)}

    assert st.parse_usage_limit(result, now=NOW) == NOW + 900


@pytest.mark.parametrize("epoch", [NOW - 10, NOW, NOW + 8 * 24 * 3600])
def test_an_implausible_epoch_falls_back_to_the_next_five_hour_boundary(epoch: int) -> None:
    result = {"is_error": True, "result": LIMIT_MESSAGE.format(epoch=epoch)}

    assert st.parse_usage_limit(result, now=NOW) == st.next_boundary(NOW)


@pytest.mark.parametrize(
    ("now", "boundary"),
    [(0, 18_000), (17_999, 18_000), (18_000, 36_000), (NOW, 1_800_000_000 + 18_000)],
)
def test_next_boundary_is_the_next_multiple_of_five_hours(now: int, boundary: int) -> None:
    assert st.next_boundary(now) == boundary
    assert 0 < st.next_boundary(now) - now <= st.FIVE_HOURS


@pytest.mark.parametrize(
    "result",
    [
        {"is_error": True, "api_error_status": 429, "result": "API Error"},
        {"is_error": False, "api_error_status": 429, "result": ""},
        {"is_error": True, "result": "Claude usage limit reached."},
        {"is_error": True, "result": "You've hit your limit for this period"},
        {"is_error": True, "result": "Rate limit exceeded, try again later"},
    ],
)
def test_limit_results_without_a_time_wait_for_the_next_boundary(result: dict) -> None:
    assert st.parse_usage_limit(result, now=NOW) == st.next_boundary(NOW)


@pytest.mark.parametrize(
    ("text", "local"),
    [
        ("You've hit your limit · resets 3pm (Europe/Kyiv)", (15, 0, 0)),
        ("Usage limit reached. Your limit resets at 11:30 am.", (11, 30, 0)),
        ("usage limit; resets 9am", (9, 0, 1)),
        ("usage limit; resets 12am", (0, 0, 1)),
        ("usage limit; resets 12pm", (12, 0, 0)),
    ],
)
def test_a_reset_clock_time_is_the_next_such_time_in_the_local_zone(
    text: str, local: tuple[int, int, int]
) -> None:
    hour, minute, days_ahead = local
    now_local = datetime.fromtimestamp(NOW, KYIV)  # 10:00 in UTC+2
    expected = now_local.replace(hour=hour, minute=minute, second=0) + timedelta(days=days_ahead)

    until = st.parse_usage_limit({"is_error": True, "result": text}, now=NOW, tz=KYIV)

    assert until == int(expected.timestamp())
    assert until > NOW


def test_a_nonsense_reset_time_falls_back_to_the_boundary() -> None:
    result = {"is_error": True, "result": "usage limit, resets 25pm"}

    assert st.parse_usage_limit(result, now=NOW, tz=UTC) == st.next_boundary(NOW)


@pytest.mark.parametrize(
    "result",
    [
        {
            "is_error": False,
            "result": "Implemented rate limit middleware; the usage limit resets daily.",
        },
        {"is_error": False, "result": LIMIT_MESSAGE.format(epoch=NOW + 100)},
        {"is_error": True, "result": "Reached max turns (250)"},
        {"is_error": True, "api_error_status": 500, "result": "Internal server error"},
        {"is_error": True},
        {},
    ],
)
def test_other_results_set_no_cooldown(result: dict) -> None:
    assert st.parse_usage_limit(result, now=NOW) is None


def test_output_that_is_not_a_json_result_is_matched_on_its_text() -> None:
    raw = "Error: " + LIMIT_MESSAGE.format(epoch=NOW + 300)

    assert st.parse_usage_limit(None, raw, now=NOW) == NOW + 300
    assert st.parse_usage_limit(None, "You have hit your limit", now=NOW) == st.next_boundary(NOW)
    assert st.parse_usage_limit(None, "git reset --hard; the timer resets", now=NOW) is None
    assert st.parse_usage_limit(None, "", now=NOW) is None
    assert st.parse_usage_limit([1, 2], "", now=NOW) is None


def test_in_cooldown() -> None:
    state = st.new_state()

    assert st.in_cooldown(state, NOW) is False
    state["cooldown_until"] = NOW + 1
    assert st.in_cooldown(state, NOW) is True
    assert st.in_cooldown(state, NOW + 1) is False


# --- retry budgets --------------------------------------------------------------------------


def test_the_budgets_match_the_plan() -> None:
    assert st.BUDGETS["rerun"] == 1
    assert st.BUDGETS["fix"] == 3
    assert st.BUDGETS["review"] == 2


@pytest.mark.parametrize("kind", sorted(st.BUDGETS))
def test_a_budget_allows_exactly_its_number_of_attempts(kind: str) -> None:
    state = st.new_state()

    for attempt in range(1, st.BUDGETS[kind] + 1):
        assert st.allowed(state, "prs", 7, kind) is True
        assert st.bump(state, "prs", 7, kind) == attempt

    assert st.allowed(state, "prs", 7, kind) is False
    assert st.remaining(state, "prs", 7, kind) == 0
    assert st.used(state, "prs", 7, kind) == st.BUDGETS[kind]


def test_budgets_are_counted_per_item_and_per_kind() -> None:
    state = st.new_state()
    for _ in range(3):
        st.bump(state, "prs", 7, "fix")

    assert st.allowed(state, "prs", 7, "fix") is False
    assert st.allowed(state, "prs", 7, "review") is True
    assert st.allowed(state, "prs", 8, "fix") is True
    assert st.allowed(state, "prs", "7", "fix") is False
    assert state["prs"] == {"7": {"fix": 3}}


def test_a_refund_never_goes_below_zero() -> None:
    state = st.new_state()

    assert st.bump(state, "prs", 7, "fix", by=-1) == 0
    st.bump(state, "prs", 7, "fix")
    assert st.bump(state, "prs", 7, "fix", by=-1) == 0
    assert st.remaining(state, "prs", 7, "fix") == 3


# --- jobs -----------------------------------------------------------------------------------


def job(kind: str, job_id: str = "j1", **fields: object) -> dict:
    return {"id": job_id, "kind": kind, "target": "t", "slot": 1, "pid": 4242, **fields}


@pytest.mark.parametrize(
    ("spec", "scope", "key", "kind"),
    [
        (job("implement", story="st-1"), "stories", "st-1", "implement"),
        (job("review", pr=12), "prs", "12", "review"),
        (job("fix-pr", pr=12), "prs", "12", "fix"),
        (job("fix-develop", run="99"), "runs", "99", "fix-develop"),
        (job("approve-sdd", epic="epic-demo"), "epics", "epic-demo", "sdd"),
        (job("integrate-epic", epic="epic-demo", pr=100), "epics", "epic-demo", "integrate"),
    ],
)
def test_starting_a_job_charges_its_budget(spec: dict, scope: str, key: str, kind: str) -> None:
    state = st.new_state()

    st.job_start(state, spec, NOW)

    assert state["jobs"]["j1"]["started_at"] == NOW
    assert st.used(state, scope, key, kind) == 1


def test_a_digest_job_draws_from_no_budget() -> None:
    state = st.new_state()

    st.job_start(state, job("digest", slot=0), NOW)

    assert (state["prs"], state["stories"], state["epics"], state["runs"]) == ({}, {}, {}, {})


def test_a_finished_job_is_removed_and_keeps_its_charge() -> None:
    state = st.new_state()
    st.job_start(state, job("fix-pr", pr=12), NOW)

    outcome = st.job_finish(state, "j1", result={"is_error": False, "result": "done"}, now=NOW + 60)

    assert outcome["status"] == "ok"
    assert outcome["job"]["pr"] == 12
    assert state["jobs"] == {}
    assert st.used(state, "prs", 12, "fix") == 1
    assert state["cooldown_until"] == 0
    assert state["digest"]["notes"] == []


@pytest.mark.parametrize(
    ("result", "raw", "rc"),
    [
        ({"is_error": True, "result": "Reached max turns"}, "", 1),
        ({"is_error": False, "result": "fine"}, "", 124),
        (None, "", 124),
        (None, "Traceback: boom", 1),
    ],
)
def test_a_failed_job_is_an_error_and_is_noted(result: object, raw: str, rc: int) -> None:
    state = st.new_state()
    st.job_start(state, job("fix-pr", pr=12, target="12"), NOW)

    outcome = st.job_finish(state, "j1", result=result, raw=raw, rc=rc, now=NOW + 60)

    assert outcome["status"] == "error"
    assert st.used(state, "prs", 12, "fix") == 1
    assert state["cooldown_until"] == 0
    assert [note["text"] for note in state["digest"]["notes"]] == ["fix-pr 12 failed (job j1)"]


def test_a_job_that_hit_the_usage_limit_sets_the_cooldown_and_gets_its_budget_back() -> None:
    state = st.new_state()
    st.job_start(state, job("implement", story="st-1"), NOW)
    result = {"is_error": True, "result": LIMIT_MESSAGE.format(epoch=NOW + 3600)}

    outcome = st.job_finish(state, "j1", result=result, rc=1, now=NOW + 5)

    assert outcome["status"] == "cooldown"
    assert outcome["cooldown_until"] == NOW + 3600
    assert state["cooldown_until"] == NOW + 3600
    assert st.in_cooldown(state, NOW + 5) is True
    assert st.used(state, "stories", "st-1", "implement") == 0
    assert state["digest"]["notes"] == []


def test_a_later_cooldown_is_never_shortened() -> None:
    state = st.new_state()
    state["cooldown_until"] = NOW + 9000
    st.job_start(state, job("review", pr=1), NOW)
    result = {"is_error": True, "result": LIMIT_MESSAGE.format(epoch=NOW + 100)}

    st.job_finish(state, "j1", result=result, now=NOW)

    assert state["cooldown_until"] == NOW + 9000


def test_finishing_an_unknown_job_changes_nothing() -> None:
    state = st.new_state()

    assert st.job_finish(state, "ghost", result={}, now=NOW) == {"status": "unknown-job"}
    assert state == st.new_state()


def test_denied_tool_calls_are_counted_and_noted() -> None:
    state = st.new_state()
    st.job_start(state, job("implement", story="st-1"), NOW)
    result = {
        "is_error": False,
        "permission_denials": [{"tool_name": "Bash"}, {"tool_name": "Bash"}],
    }

    outcome = st.job_finish(state, "j1", result=result, now=NOW)

    assert outcome["status"] == "ok"
    assert outcome["permission_denials"] == 2
    assert state["digest"]["notes"][0]["text"] == "implement j1: 2 denied tool calls"


def test_the_session_of_an_implement_job_is_kept_for_fix_pr() -> None:
    state = st.new_state()
    st.job_start(state, job("implement", story="st-1", slot=2, session="planned"), NOW)

    st.job_finish(state, "j1", result={"is_error": False, "session_id": "actual"}, now=NOW)

    assert state["stories"]["st-1"] == {"implement": 1, "session": "actual", "slot": 2}


def test_reap_drops_jobs_whose_runner_is_gone() -> None:
    state = st.new_state()
    st.job_start(state, job("implement", "alive", story="st-1", pid=10), NOW)
    st.job_start(state, job("fix-pr", "dead", pr=5, target="5", pid=11), NOW)
    st.job_start(state, job("review", "nopid", pr=6, pid=0), NOW)

    gone = st.reap(state, lambda pid: pid == 10, NOW + 30)

    assert sorted(gone) == ["dead", "nopid"]
    assert list(state["jobs"]) == ["alive"]
    assert st.used(state, "prs", 5, "fix") == 1
    assert "fix-pr 5 died (job dead)" in [note["text"] for note in state["digest"]["notes"]]


def test_busy_items_and_used_slots() -> None:
    state = st.new_state()
    st.job_start(state, job("implement", "a", story="st-1", slot=1), NOW)
    st.job_start(state, job("fix-pr", "b", pr=12, slot=3), NOW)
    st.job_start(state, job("digest", "c", slot=0), NOW)

    assert st.busy(state, "story") == {"st-1"}
    assert st.busy(state, "pr") == {"12"}
    assert st.busy(state, "epic") == set()
    assert st.used_slots(state) == {1, 3}


# --- digest notes ---------------------------------------------------------------------------


def test_notes_are_kept_once_and_bounded() -> None:
    state = st.new_state()

    assert st.add_note(state, "PR #1 is green", NOW) is True
    assert st.add_note(state, "PR #1 is green", NOW + 900) is False
    for number in range(st.NOTE_LIMIT + 5):
        st.add_note(state, f"note {number}", NOW)

    notes = state["digest"]["notes"]
    assert len(notes) == st.NOTE_LIMIT
    assert notes[-1] == {"at": NOW, "text": f"note {st.NOTE_LIMIT + 4}"}


def test_the_digest_is_due_once_a_day_after_the_hour() -> None:
    state = st.new_state()  # NOW is 08:00 UTC

    assert st.digest_due(state, NOW, 8, UTC) is True
    assert st.digest_due(state, NOW, 9, UTC) is False
    assert st.digest_due(state, NOW, 9, KYIV) is True

    st.add_note(state, "something", NOW)
    st.digest_sent(state, NOW, UTC)

    assert state["digest"] == {"last_date": "2027-01-15", "notes": []}
    assert st.digest_due(state, NOW + 3600, 8, UTC) is False
    assert st.digest_due(state, NOW + 24 * 3600, 8, UTC) is True


# --- the command line (what the shell calls) ------------------------------------------------


def run_state(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_LIB / "state.py"), "--state", str(path), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_usage_limit_drill(tmp_path: Path) -> None:
    """A fake limit result goes through the same commands the job runner uses."""
    path = tmp_path / "home" / "state.json"
    result = tmp_path / "result.json"
    epoch = int(time.time()) + 3600  # the command line uses the real clock
    result.write_text(json.dumps({"is_error": True, "result": LIMIT_MESSAGE.format(epoch=epoch)}))

    assert run_state(path, "init").returncode == 0
    spec = json.dumps(job("implement", "job-1", story="st-1"))
    assert run_state(path, "job-start", spec).returncode == 0
    assert json.loads(path.read_text())["stories"] == {"st-1": {"implement": 1}}

    finished = run_state(path, "job-finish", "job-1", "--rc", "1", "--result", str(result))

    assert finished.returncode == 0, finished.stderr
    outcome = json.loads(finished.stdout)
    assert outcome["status"] == "cooldown"
    state = json.loads(path.read_text())
    assert state["cooldown_until"] == outcome["cooldown_until"] == epoch
    assert state["jobs"] == {}
    assert state["stories"] == {"st-1": {"implement": 0}}
    assert run_state(path, "get", "cooldown_until").stdout.strip() == str(state["cooldown_until"])
    assert "cooldown: until" in run_state(path, "show").stdout
    assert not (path.parent / "state.json.lock.d").exists()


def test_cli_set_get_note_bump_and_reap(tmp_path: Path) -> None:
    path = tmp_path / "state.json"

    assert run_state(path, "get", "janitor.approved").stdout == "false\n"
    assert not path.exists()
    assert run_state(path, "set", "janitor.approved", "true").returncode == 0
    assert run_state(path, "get", "janitor.approved").stdout == "true\n"
    assert run_state(path, "bump", "prs", "12", "rerun").stdout == "1\n"
    assert run_state(path, "note", "hello").returncode == 0
    dead = json.dumps(job("review", "job-9", pr=3, pid=2_000_000_000))
    assert run_state(path, "job-start", dead).returncode == 0
    assert run_state(path, "reap").stdout == "job-9\n"
    assert run_state(path, "digest-sent").returncode == 0

    state = json.loads(path.read_text())
    assert state["jobs"] == {}
    assert state["prs"] == {"12": {"rerun": 1}, "3": {"review": 1}}
    assert state["digest"]["notes"] == []
    assert state["digest"]["last_date"]


def test_cli_refuses_a_broken_state_file(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{broken")

    failed = run_state(path, "note", "x")

    assert failed.returncode == 1
    assert "state:" in failed.stderr
    assert path.read_text() == "{broken"
    assert not (tmp_path / "state.json.lock.d").exists()


def test_cli_job_finish_without_a_result_file_is_an_error_outcome(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    run_state(path, "job-start", json.dumps(job("fix-pr", "job-2", pr=4)))

    finished = run_state(
        path, "job-finish", "job-2", "--rc", "124", "--result", str(tmp_path / "x")
    )

    assert json.loads(finished.stdout)["status"] == "error"


# --- check classification -------------------------------------------------------------------


def check(conclusion: str = "SUCCESS", status: str = "COMPLETED", run: int = 1) -> dict:
    return {
        "__typename": "CheckRun",
        "name": "unit",
        "status": status,
        "conclusion": conclusion,
        "detailsUrl": f"https://github.com/o/r/actions/runs/{run}/job/9",
    }


@pytest.mark.parametrize(
    ("rollup", "expected"),
    [
        (None, ("none", [])),
        ([], ("none", [])),
        ([check(), check("SKIPPED"), check("NEUTRAL")], ("green", [])),
        ([check(), check("", "IN_PROGRESS")], ("pending", [])),
        ([check(), check("", "QUEUED"), check("FAILURE")], ("failed", [])),
        (
            [check("CANCELLED", run=5), check("TIMED_OUT", run=6), check()],
            ("cancelled", ["5", "6"]),
        ),
        ([check("CANCELLED", run=5), check("CANCELLED", run=5)], ("cancelled", ["5"])),
        ([check("CANCELLED", run=5), check("FAILURE")], ("failed", ["5"])),
        ([check("STARTUP_FAILURE")], ("failed", [])),
        (
            [{"__typename": "StatusContext", "context": "codecov", "state": "SUCCESS"}],
            ("green", []),
        ),
        (
            [{"__typename": "StatusContext", "context": "codecov", "state": "PENDING"}],
            ("pending", []),
        ),
        ([{"__typename": "StatusContext", "context": "codecov", "state": "ERROR"}], ("failed", [])),
    ],
)
def test_classify_checks(rollup: list[dict] | None, expected: tuple[str, list[str]]) -> None:
    assert plan.classify_checks(rollup) == expected


# --- pull request decisions -----------------------------------------------------------------


def pull(
    number: int = 12,
    *,
    base: str = "epic/epic-demo",
    head: str = "feat/st-1",
    author: str = BOT,
    checks: list[dict] | None = None,
    labels: tuple[str, ...] = (),
    mergeable: str = "MERGEABLE",
    draft: bool = False,
    body: str = "Story: st-1\n",
) -> dict:
    return {
        "number": number,
        "title": "feat(core): something",
        "author": {"login": author},
        "baseRefName": base,
        "headRefName": head,
        "isDraft": draft,
        "mergeable": mergeable,
        "labels": [{"name": label} for label in labels],
        "body": body,
        "statusCheckRollup": [check()] if checks is None else checks,
    }


def decide(*prs: dict, **inputs: object) -> list[tuple[str, ...]]:
    """Plan for the given pull requests; return ``(kind, *first args)`` without info rows."""
    base: dict[str, object] = {"now": NOW, "limit": 3, "pool": 3, "bot": BOT, "prs": list(prs)}
    base.update(inputs)
    return [
        (action.kind, *action.args[:2]) for action in plan.build_plan(base) if action.kind != "info"
    ]


def spent(**counters: int) -> dict:
    return {"prs": {"12": counters}}


def test_failed_checks_start_a_fix_round_until_the_budget_is_spent() -> None:
    red = pull(checks=[check("FAILURE")])

    assert decide(red) == [("spawn", "fix-pr", "12")]
    assert decide(red, state=spent(fix=2)) == [("spawn", "fix-pr", "12")]
    assert decide(red, state=spent(fix=3)) == [
        ("needs-human", "12", "fix budget spent (checks failed)")
    ]


def test_an_escalated_pull_request_is_not_escalated_twice() -> None:
    red = pull(checks=[check("FAILURE")])

    assert decide(red, state={"prs": {"12": {"fix": 3, "escalated": True}}}) == []
    assert decide(pull(checks=[check("FAILURE")], labels=("needs-human",))) == [("note",)]


def test_cancelled_checks_are_rerun_once_then_fixed() -> None:
    cancelled = pull(checks=[check("CANCELLED", run=77), check()])

    assert decide(cancelled) == [("rerun-pr", "12", "77")]
    assert decide(cancelled, state=spent(rerun=1)) == [("spawn", "fix-pr", "12")]
    assert decide(cancelled, state=spent(rerun=1, fix=3)) == [
        ("needs-human", "12", "fix budget spent (checks cancelled again after one rerun)")
    ]


def test_a_conflicting_pull_request_is_rebased_by_a_fix_round() -> None:
    conflicting = pull(mergeable="CONFLICTING", labels=("ai-approved",))

    actions = plan.build_plan({"now": NOW, "limit": 3, "bot": BOT, "prs": [conflicting]})

    spawn = next(action for action in actions if action.kind == "spawn")
    assert spawn.args[:5] == ("fix-pr", "12", "1", "feat/st-1", "origin/feat/st-1")
    assert json.loads(spawn.args[5])["reason"] == "conflicts with its base branch"


def test_review_findings_start_a_fix_round() -> None:
    assert decide(pull(labels=("ai-changes-requested",))) == [("spawn", "fix-pr", "12")]
    assert decide(pull(labels=("ai-changes-requested",)), state=spent(fix=3)) == [
        ("needs-human", "12", "fix budget spent (review asked for changes)")
    ]


def test_a_green_unreviewed_pull_request_is_reviewed_at_most_twice() -> None:
    green = pull()

    assert decide(green) == [("spawn", "review", "12")]
    assert decide(green, state=spent(review=1)) == [("spawn", "review", "12")]
    assert decide(green, state=spent(review=2)) == [
        ("needs-human", "12", "review budget spent without an approval")
    ]


def test_an_approved_green_pull_request_is_merged_when_up_to_date() -> None:
    approved = pull(labels=("ai-approved",))

    assert decide(approved, behind={"12": "0"}) == [("merge", "12", "st-1")]
    assert decide(approved, behind={"12": "3"}) == [("update-branch", "12")]
    assert decide(approved, behind={}) == []
    assert decide(pull(labels=("ai-approved",), mergeable="UNKNOWN"), behind={"12": "0"}) == []


def test_nothing_is_merged_while_checks_run_or_are_missing() -> None:
    running = pull(labels=("ai-approved",), checks=[check("", "IN_PROGRESS")])
    silent = pull(labels=("ai-approved",), checks=[])

    assert decide(running, behind={"12": "0"}) == []
    assert decide(silent, behind={"12": "0"}) == []


def test_a_merge_without_a_story_line_is_noted() -> None:
    approved = pull(labels=("ai-approved",), body="no story line")

    assert decide(approved, behind={"12": "0"}) == [("note",), ("merge", "12", "")]


def test_draft_and_busy_and_foreign_pull_requests_are_left_alone() -> None:
    red = [check("FAILURE")]
    busy = {"jobs": {"j": {"kind": "fix-pr", "pr": 12, "slot": 1, "pid": 1}}}

    assert decide(pull(checks=red, draft=True)) == []
    assert decide(pull(checks=red), state=busy) == []
    assert decide(pull(checks=red, author="someone-else")) == []
    assert decide(pull(checks=red), bot="") == []


def test_pull_requests_to_develop_are_repaired_but_never_merged() -> None:
    to_develop = {"base": "develop", "head": "fix/develop-99"}

    assert decide(pull(checks=[check("FAILURE")], **to_develop)) == [("spawn", "fix-pr", "12")]
    assert decide(pull(labels=("ai-approved",), **to_develop), behind={"12": "0"}) == [("note",)]
    assert decide(pull(draft=True, **to_develop)) == []


def test_the_scope_setting_limits_repairs_to_autopilot_branches() -> None:
    red = [check("FAILURE")]
    legacy = pull(checks=red, base="develop", head="feat/legacy")
    own = pull(13, checks=red, base="develop", head="fix/develop-99")

    assert decide(legacy, own) == [("spawn", "fix-pr", "12"), ("spawn", "fix-pr", "13")]
    assert decide(legacy, own, pr_scope="autopilot") == [("spawn", "fix-pr", "13")]


def test_a_green_dependabot_pull_request_goes_to_the_digest() -> None:
    green = pull(base="develop", head="dependabot/uv/ruff", author="app/dependabot")
    red = pull(
        13,
        base="develop",
        head="dependabot/uv/x",
        author="app/dependabot",
        checks=[check("FAILURE")],
    )

    actions = plan.build_plan({"now": NOW, "limit": 3, "bot": BOT, "prs": [green, red]})

    assert [(action.kind, action.why) for action in actions] == [
        ("note", "Dependabot PR #12 is green and waits for the owner")
    ]


def test_fix_pr_resumes_the_implement_session_only_in_its_own_slot() -> None:
    red = pull(checks=[check("FAILURE")])
    memory = {"stories": {"st-1": {"session": "abc", "slot": 2}}}
    taken = {**memory, "jobs": {"j": {"kind": "implement", "story": "st-9", "slot": 2, "pid": 1}}}

    def spawned(state: dict) -> tuple[str, str]:
        actions = plan.build_plan(
            {"now": NOW, "limit": 3, "pool": 3, "bot": BOT, "prs": [red], "state": state}
        )
        spawn = next(action for action in actions if action.kind == "spawn")
        return spawn.args[2], json.loads(spawn.args[5])["resume"]

    assert spawned(memory) == ("2", "abc")
    assert spawned(taken) == ("1", "")
    assert spawned({}) == ("1", "")


# --- cooldown, slots and memory at spawn time -----------------------------------------------


def test_no_job_is_spawned_during_a_cooldown_but_deterministic_actions_continue() -> None:
    cooling = {"cooldown_until": NOW + 600}
    red = pull(checks=[check("FAILURE")])
    cancelled = pull(13, checks=[check("CANCELLED", run=5)], head="feat/st-2", body="Story: st-2\n")
    approved = pull(14, labels=("ai-approved",), head="feat/st-3", body="Story: st-3\n")

    actions = plan.build_plan(
        {
            "now": NOW,
            "limit": 3,
            "bot": BOT,
            "prs": [red, cancelled, approved],
            "behind": {"14": "0"},
            "state": cooling,
            "digest_hour": 0,
        }
    )

    assert [(action.kind, *action.args[:1]) for action in actions if action.kind != "info"] == [
        ("rerun-pr", "13"),
        ("merge", "14"),
    ]
    assert actions[-1].why == "2 jobs wait (usage-limit cooldown)"
    assert decide(red, state={"cooldown_until": NOW - 1}) == [("spawn", "fix-pr", "12")]


def test_jobs_beyond_the_free_slots_wait_and_repairs_go_first() -> None:
    prs = [
        pull(21, head="feat/a", body="Story: a\n"),
        pull(22, head="feat/b", body="Story: b\n", checks=[check("FAILURE")]),
        pull(23, head="feat/c", body="Story: c\n"),
        pull(24, head="feat/d", body="Story: d\n", labels=("ai-changes-requested",)),
    ]

    actions = plan.build_plan({"now": NOW, "limit": 3, "pool": 3, "bot": BOT, "prs": prs})

    assert [action.args[:3] for action in actions if action.kind == "spawn"] == [
        ("fix-pr", "22", "1"),
        ("fix-pr", "24", "2"),
        ("review", "21", "3"),
    ]
    assert actions[-1].why == "1 jobs wait (no free slot)"


def test_running_jobs_hold_their_slots() -> None:
    held = {"jobs": {"j": {"kind": "review", "pr": 99, "slot": 2, "pid": 1}}}
    prs = [pull(21, checks=[check("FAILURE")]), pull(22, checks=[check("FAILURE")]), pull(23)]

    actions = plan.build_plan(
        {"now": NOW, "limit": 3, "pool": 3, "bot": BOT, "prs": prs, "state": held}
    )

    assert [action.args[:3] for action in actions if action.kind == "spawn"] == [
        ("fix-pr", "21", "1"),
        ("fix-pr", "22", "3"),
    ]


def test_low_memory_means_one_job_at_a_time() -> None:
    prs = [pull(21, checks=[check("FAILURE")]), pull(22, checks=[check("FAILURE")])]

    def slots(**inputs: object) -> list[str]:
        base = {"now": NOW, "limit": 3, "pool": 3, "bot": BOT, "prs": prs, **inputs}
        return [action.args[2] for action in plan.build_plan(base) if action.kind == "spawn"]

    assert slots(mem_free_gb=16.0) == ["1", "2"]
    assert slots(mem_free_gb=None) == ["1", "2"]
    assert slots(mem_free_gb=3.9) == ["1"]
    assert slots(limit=1) == ["1"]
    assert slots(limit=0) == []


def test_the_digest_needs_no_slot_and_runs_once_a_day() -> None:
    def digest(**inputs: object) -> list[tuple[str, ...]]:
        return decide(digest_hour=0, **inputs)

    assert digest(limit=0) == [("spawn", "digest", "daily")]
    assert (
        digest(
            state={
                "digest": {
                    "last_date": datetime.fromtimestamp(NOW, UTC).astimezone().date().isoformat()
                }
            }
        )
        == []
    )
    assert digest(state={"jobs": {"j": {"kind": "digest", "slot": 0, "pid": 1}}}) == []
    assert decide() == []


# --- develop and nightly workflows ----------------------------------------------------------


def run(run_id: int, conclusion: str | None = "success", status: str = "completed") -> dict:
    return {
        "databaseId": run_id,
        "status": status,
        "conclusion": conclusion,
        "workflowName": "Test",
        "url": f"https://github.com/o/r/actions/runs/{run_id}",
    }


def health(
    push: list[dict] | None = None, nightly: list[dict] | None = None, **inputs: object
) -> list:
    runs = {"push": {"Test": push or []}, "nightly": {"Demo": nightly or []}}
    return decide(runs=runs, **inputs)


def test_a_green_or_still_running_develop_needs_nothing() -> None:
    assert health([run(3), run(2, "failure")]) == []
    assert health([run(3, None, "in_progress"), run(2, "failure")]) == []
    assert health([]) == []


def test_a_red_develop_run_starts_one_fix_develop_job() -> None:
    actions = plan.build_plan(
        {
            "now": NOW,
            "limit": 3,
            "bot": BOT,
            "runs": {"push": {"Test": [run(3, "failure")], "CI": [run(4, "failure")]}},
        }
    )

    spawns = [action for action in actions if action.kind == "spawn"]
    assert [action.args[:5] for action in spawns] == [
        ("fix-develop", "4", "1", "fix/develop-4", "origin/develop")
    ]
    assert json.loads(spawns[0].args[5])["run"] == "4"


def test_a_cancelled_develop_run_is_rerun_once() -> None:
    assert health([run(3, "cancelled")]) == [("rerun-run", "3")]
    assert health([run(3, "timed_out")]) == [("rerun-run", "3")]
    assert health([run(3, "cancelled")], state={"runs": {"3": {"rerun": 1}}}) == [("note",)]
    assert health([run(3, "timed_out")], state={"runs": {"3": {"rerun": 1}}}) == [
        ("spawn", "fix-develop", "3")
    ]


def test_develop_is_not_repaired_twice_for_the_same_run() -> None:
    red = [run(3, "failure")]
    fix_open = pull(50, base="develop", head="fix/develop-3", checks=[check("", "IN_PROGRESS")])
    running = {"jobs": {"j": {"kind": "fix-develop", "run": "3", "slot": 1, "pid": 1}}}

    assert health(red, state={"runs": {"3": {"fix-develop": 1}}}) == [("note",)]
    assert health(red, prs=[fix_open]) == [("note",)]
    assert health(red, state=running) == []


def test_a_nightly_workflow_is_repaired_only_when_red_twice() -> None:
    assert health(nightly=[run(9, "failure"), run(8)]) == []
    assert health(nightly=[run(9, "failure")]) == []
    assert health(nightly=[run(9, "failure"), run(8, "failure"), run(7)]) == [
        ("spawn", "fix-develop", "9")
    ]
    assert health(nightly=[run(9, "cancelled"), run(8, "failure")]) == [("rerun-run", "9")]


# --- plan rows ------------------------------------------------------------------------------


def test_an_action_row_has_eight_unit_separated_fields() -> None:
    row = plan.Action("merge", "why\nit|is so", ("12", "st-1")).row()

    assert row.split(plan.SEP) == ["merge", "12", "st-1", "", "", "", "", "why it|is so"]


def test_plan_cli_reads_a_directory_of_observations(tmp_path: Path) -> None:
    (tmp_path / "env.json").write_text(
        json.dumps(
            {"now": NOW, "limit": 3, "pool": 3, "bot": BOT, "state_file": str(tmp_path / "s.json")}
        )
    )
    (tmp_path / "prs.json").write_text(json.dumps([pull(labels=("ai-approved",))]))
    (tmp_path / "behind.tsv").write_text("12\t0\n13\t\n")
    (tmp_path / "epic-branches.txt").write_text("")
    (tmp_path / "runs" / "push").mkdir(parents=True)
    (tmp_path / "runs" / "push" / "Test.json").write_text(json.dumps([run(3, "cancelled")]))
    (tmp_path / "runs" / "push" / "Empty.json").write_text("[]")

    done = subprocess.run(
        [sys.executable, str(_LIB / "plan.py"), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    rows = [line.split(plan.SEP) for line in done.stdout.splitlines()]
    assert [row[:3] for row in rows] == [["rerun-run", "3", ""], ["merge", "12", "st-1"]]
    assert not (tmp_path / "s.json").exists()
