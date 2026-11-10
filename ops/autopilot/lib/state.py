#!/usr/bin/env python3
"""Autopilot state: cooldown, running jobs, retry budgets, janitor approval, digest notes.

Everything the tick remembers between runs lives in one JSON file
(``~/.hyperadmin-autopilot/state.json``). This module owns its shape and every rule that reads
or changes it, so the shell never edits JSON by hand:

* usage-limit detection in a ``claude -p --output-format json`` result and the cooldown it sets
* retry budgets (one CI rerun, three fix rounds and two review rounds per pull request, ...)
* the running-job table and what a finished job leaves behind

Pure standard library. The functions are side-effect free on plain dicts; only the command
line at the bottom touches the file, under a ``mkdir`` lock (macOS has no ``flock``).

Usage:
  state.py --state FILE COMMAND [ARGS]     run ``state.py --help`` for the commands
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path

VERSION = 1
FIVE_HOURS = 5 * 60 * 60
MAX_COOLDOWN = 7 * 24 * 60 * 60
NOTE_LIMIT = 200
STALE_LOCK = 120
HTTP_TOO_MANY_REQUESTS = 429
NOON = 12

# How many times each kind of work may be tried before the item goes to ``needs-human``.
BUDGETS = {
    "rerun": 1,  # rerun a cancelled or timed-out CI run
    "fix": 3,  # fix-pr rounds per pull request
    "review": 2,  # review rounds per pull request
    "implement": 2,  # implement attempts per story
    "sdd": 2,  # approve-sdd attempts per epic
    "integrate": 2,  # integrate-epic attempts per epic
    "fix-develop": 1,  # fix-develop attempts per workflow, until that workflow is green again
}
# A job this long past its own wall-clock limit is gone, whatever its pid says now.
REAP_MARGIN = 600
# Which budget a spawned job draws from: job -> (scope, field of the job that is the key, kind).
JOB_BUDGET = {
    "implement": ("stories", "story", "implement"),
    "review": ("prs", "pr", "review"),
    "fix-pr": ("prs", "pr", "fix"),
    "fix-develop": ("workflows", "workflow", "fix-develop"),
    "approve-sdd": ("epics", "epic", "sdd"),
    "integrate-epic": ("epics", "epic", "integrate"),
}

LIMIT_TEXT = re.compile(r"usage limit|hit your limit|rate limit|resets", re.IGNORECASE)
# Output that is not a JSON result (a crash, a kill) is matched more strictly.
LIMIT_RAW = re.compile(r"usage limit|hit your limit|rate limit", re.IGNORECASE)
LIMIT_EPOCH = re.compile(r"Claude AI usage limit reached\|(\d{9,13})")
RESETS_AT = re.compile(r"resets(?: at)?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)", re.IGNORECASE)


class StateError(Exception):
    """The state file exists but cannot be used."""


def new_state() -> dict:
    """Return an empty state."""
    return {
        "version": VERSION,
        "cooldown_until": 0,
        "jobs": {},
        "prs": {},
        "runs": {},
        "workflows": {},
        "stories": {},
        "epics": {},
        "janitor": {"approved": False, "last_run": 0, "candidates": []},
        "digest": {"last_date": "", "notes": []},
    }


def normalise(data: object) -> dict:
    """Fill the keys a state written by an older version may lack."""
    if not isinstance(data, dict):
        raise StateError("state is not a JSON object")
    state = new_state()
    for key, default in state.items():
        value = data.get(key, default)
        if isinstance(default, dict):
            if not isinstance(value, dict):
                raise StateError(f"state key {key!r} is not an object")
            value = {**default, **value}
        state[key] = value
    return state


def load(path: str | Path) -> dict:
    """Read the state file; a missing file is an empty state, a broken one is an error."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return new_state()
    try:
        return normalise(json.loads(text))
    except json.JSONDecodeError as error:
        raise StateError(f"{path}: {error}") from error


def save(path: str | Path, state: dict) -> None:
    """Write the state file atomically (temp file, then rename)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)


# --- cooldown ---------------------------------------------------------------------------------


def _local(now: int, tz: tzinfo | None) -> datetime:
    """Return ``now`` as an aware datetime in ``tz`` (the system zone when ``None``)."""
    return datetime.fromtimestamp(now, timezone.utc).astimezone(tz)


def next_boundary(now: int) -> int:
    """Return the next five-hour boundary after ``now`` (epoch seconds)."""
    return (now // FIVE_HOURS + 1) * FIVE_HOURS


def _reset_clock(text: str, now: int, tz: tzinfo | None) -> int | None:
    """Read "resets 3pm" or "resets at 3:30 pm" as the next such time in ``tz``."""
    match = RESETS_AT.search(text)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2) or 0)
    if not 1 <= hour <= NOON or minute >= 60:  # noqa: PLR2004
        return None
    hour = hour % NOON + (NOON if match.group(3).lower() == "pm" else 0)
    current = _local(now, tz)
    reset = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if reset <= current:
        reset += timedelta(days=1)
    return int(reset.timestamp())


def parse_usage_limit(
    result: object, raw: str = "", *, now: int, tz: tzinfo | None = None
) -> int | None:
    """Return the epoch until which jobs must not be spawned, or ``None``.

    A job hit the usage limit when its result carries ``api_error_status == 429``, or
    ``is_error`` together with limit wording in ``result``. A failed run that printed no JSON
    at all counts when its raw output carries the wording. A successful result never counts,
    whatever it says: stories about rate limiting must not pause the autopilot.

    The cooldown ends at the epoch of ``Claude AI usage limit reached|<epoch>`` when present,
    else at the "resets 3pm" clock time, else at the next five-hour boundary.
    """
    if isinstance(result, dict):
        text = str(result.get("result") or "")
        limited = result.get("api_error_status") == HTTP_TOO_MANY_REQUESTS or (
            bool(result.get("is_error")) and bool(LIMIT_TEXT.search(text))
        )
    else:
        text = raw
        limited = bool(LIMIT_RAW.search(text))
    if not limited:
        return None
    epoch = LIMIT_EPOCH.search(text)
    if epoch:
        until = int(epoch.group(1))
        if until > 10**11:  # milliseconds
            until //= 1000
        if now < until <= now + MAX_COOLDOWN:
            return until
    return _reset_clock(text, now, tz) or next_boundary(now)


def in_cooldown(state: dict, now: int) -> bool:
    """Tell whether spawning is paused."""
    return int(state.get("cooldown_until") or 0) > now


# --- retry budgets ----------------------------------------------------------------------------


def used(state: dict, scope: str, key: object, kind: str) -> int:
    """Return how many attempts of ``kind`` the item has used."""
    return int(state.get(scope, {}).get(str(key), {}).get(kind, 0))


def remaining(state: dict, scope: str, key: object, kind: str) -> int:
    """Return how many attempts of ``kind`` the item has left."""
    return max(0, BUDGETS[kind] - used(state, scope, key, kind))


def allowed(state: dict, scope: str, key: object, kind: str) -> bool:
    """Tell whether the item may be tried once more."""
    return remaining(state, scope, key, kind) > 0


def bump(state: dict, scope: str, key: object, kind: str, by: int = 1) -> int:
    """Record ``by`` attempts (negative to refund) and return the new count."""
    entry = state.setdefault(scope, {}).setdefault(str(key), {})
    entry[kind] = max(0, int(entry.get(kind, 0)) + by)
    return entry[kind]


def _budget_of(job: dict) -> tuple[str, str, str] | None:
    """Return the (scope, key, kind) budget a job draws from."""
    budget = JOB_BUDGET.get(str(job.get("kind")))
    if budget is None:
        return None
    scope, key_field, kind = budget
    key = job.get(key_field)
    return None if key in (None, "") else (scope, str(key), kind)


# --- jobs -------------------------------------------------------------------------------------


def job_start(state: dict, job: dict, now: int) -> dict:
    """Register a spawned job and charge its budget."""
    job_id = str(job["id"])
    entry = {**job, "started_at": now}
    state["jobs"][job_id] = entry
    budget = _budget_of(entry)
    if budget:
        bump(state, *budget)
    return entry


def job_finish(
    state: dict,
    job_id: str,
    *,
    result: object,
    raw: str = "",
    rc: int = 0,
    now: int,
    tz: tzinfo | None = None,
) -> dict:
    """Remove a finished job and record what it leaves behind.

    Returns ``{"status": ok | error | cooldown | unknown-job, "job": ..., ...}``. A job that
    ran into the usage limit gets its budget back and sets ``cooldown_until``.
    """
    job = state["jobs"].pop(str(job_id), None)
    if job is None:
        return {"status": "unknown-job"}
    outcome: dict = {"status": "ok", "job": job}
    until = parse_usage_limit(result, raw, now=now, tz=tz)
    failed = rc != 0 or not isinstance(result, dict) or bool(result.get("is_error"))
    if until is not None:
        state["cooldown_until"] = max(int(state.get("cooldown_until") or 0), until)
        budget = _budget_of(job)
        if budget:
            bump(state, *budget, by=-1)
        outcome.update(status="cooldown", cooldown_until=until)
    elif failed:
        outcome["status"] = "error"
    if isinstance(result, dict):
        _remember_session(state, job, result)
        denials = result.get("permission_denials") or []
        if denials:
            outcome["permission_denials"] = len(denials)
            add_note(state, f"{job.get('kind')} {job_id}: {len(denials)} denied tool calls", now)
    if outcome["status"] == "error":
        add_note(state, f"{job.get('kind')} {job.get('target', '')} failed (job {job_id})", now)
    return outcome


def _remember_session(state: dict, job: dict, result: dict) -> None:
    """Keep the session of an implement job so ``fix-pr`` can resume it."""
    session = result.get("session_id") or job.get("session")
    if job.get("kind") == "implement" and job.get("story") and session:
        entry = state["stories"].setdefault(str(job["story"]), {})
        entry.update(session=session, slot=job.get("slot"))


def _overdue(job: dict, now: int) -> bool:
    """Tell whether a job is past its wall-clock limit by more than the margin."""
    started, limit = int(job.get("started_at") or 0), int(job.get("timeout") or 0)
    return started > 0 and limit > 0 and now > started + limit + REAP_MARGIN


def clear(state: dict, scope: str, key: object) -> bool:
    """Forget everything recorded for one item of a scope; return whether there was any."""
    return state.get(scope, {}).pop(str(key), None) is not None


def reap(state: dict, alive, now: int) -> list[str]:
    """Drop jobs whose runner process is gone and return their ids.

    ``alive`` is a callable taking a pid. After a reboot a pid can belong to another process,
    so a job far past its own wall-clock limit is dropped as well. The budget stays charged:
    a job that died without a result still used its attempt.
    """
    gone = [
        job_id
        for job_id, job in state["jobs"].items()
        if not job.get("pid") or not alive(int(job["pid"])) or _overdue(job, now)
    ]
    for job_id in gone:
        job = state["jobs"].pop(job_id)
        add_note(state, f"{job.get('kind')} {job.get('target', '')} died (job {job_id})", now)
    return gone


def busy(state: dict, field: str) -> set[str]:
    """Return the values of ``field`` (pr, story, epic, run) across the running jobs."""
    return {str(job[field]) for job in state["jobs"].values() if job.get(field) not in (None, "")}


def used_slots(state: dict) -> set[int]:
    """Return the worktree pool slots the running jobs hold."""
    return {int(job["slot"]) for job in state["jobs"].values() if int(job.get("slot") or 0) > 0}


# --- digest notes and janitor ------------------------------------------------------------------


def add_note(state: dict, text: str, now: int) -> bool:
    """Queue a line for the next digest; identical lines are kept once."""
    notes = state["digest"].setdefault("notes", [])
    if any(note.get("text") == text for note in notes):
        return False
    notes.append({"at": now, "text": text})
    del notes[:-NOTE_LIMIT]
    return True


def digest_due(state: dict, now: int, hour: int, tz: tzinfo | None = None) -> bool:
    """Tell whether today's digest still has to be sent (after ``hour`` local time)."""
    current = _local(now, tz)
    return current.hour >= hour and state["digest"].get("last_date") != current.date().isoformat()


def digest_sent(state: dict, now: int, tz: tzinfo | None = None) -> None:
    """Mark today's digest as sent and clear the queued notes."""
    current = _local(now, tz)
    state["digest"] = {"last_date": current.date().isoformat(), "notes": []}


def janitor_approved(state: dict) -> bool:
    """Tell whether the owner has approved real clean-up (the default is a dry run)."""
    return state["janitor"].get("approved") is True


def set_path(state: dict, dotted: str, value: object) -> None:
    """Set ``a.b.c`` in the state, creating objects on the way."""
    *parents, leaf = dotted.split(".")
    node = state
    for part in parents:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise StateError(f"{dotted}: {part!r} is not an object")
    node[leaf] = value


def get_path(state: dict, dotted: str) -> object:
    """Return ``a.b.c`` from the state, or ``None`` when it is absent."""
    node: object = state
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


# --- command line ------------------------------------------------------------------------------


@contextlib.contextmanager
def locked(path: Path, wait: float = 30.0):
    """Hold the state lock (a directory next to the file) while the block runs."""
    lock = path.with_name(path.name + ".lock.d")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            with contextlib.suppress(OSError):
                # State commands take milliseconds: a lock this old was left by a dead process.
                if time.time() - lock.stat().st_mtime > STALE_LOCK:
                    lock.rmdir()
                    continue
            if time.monotonic() > deadline:
                raise StateError(f"state lock {lock} is held; remove it if no tick runs") from None
            time.sleep(0.1)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            lock.rmdir()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_result(path: str | None) -> tuple[object, str]:
    """Load a job result file: the parsed JSON object (or ``None``) and the raw text."""
    if not path:
        return None, ""
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, ""
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError:
        return None, raw


def _show(state: dict, now: int) -> str:
    cooldown = int(state.get("cooldown_until") or 0)
    until = f"until {_local(cooldown, None):%F %R}" if cooldown > now else "no"
    janitor = "approved" if janitor_approved(state) else "dry run (not approved)"
    candidates = len(state["janitor"].get("candidates") or [])
    notes = len(state["digest"].get("notes") or [])
    lines = [
        f"cooldown: {until}",
        f"janitor: {janitor}, {candidates} candidates",
        f"digest: last {state['digest'].get('last_date') or 'never'}, {notes} notes queued",
        f"jobs running: {len(state['jobs'])}",
    ]
    lines += [
        f"  {job_id}  {job.get('kind')} {job.get('target', '')}  slot {job.get('slot', 0)}  "
        f"pid {job.get('pid', '?')}  {(now - int(job.get('started_at', now))) // 60} min"
        for job_id, job in sorted(state["jobs"].items())
    ]
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read and change the autopilot state file.")
    parser.add_argument("--state", required=True, help="path of state.json")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="create the file when missing")
    commands.add_parser("show", help="print a summary")
    commands.add_parser("reap", help="drop jobs whose runner died")
    get = commands.add_parser("get", help="print one value as JSON")
    get.add_argument("path")
    put = commands.add_parser("set", help="set one value (JSON)")
    put.add_argument("path")
    put.add_argument("value")
    note = commands.add_parser("note", help="queue a digest line")
    note.add_argument("text")
    budget = commands.add_parser("bump", help="charge a retry budget")
    budget.add_argument("scope")
    budget.add_argument("key")
    budget.add_argument("kind", choices=sorted(BUDGETS))
    budget.add_argument("--by", type=int, default=1, help="attempts to add (negative refunds)")
    forget = commands.add_parser("clear", help="forget one item of a scope")
    forget.add_argument("scope", choices=["prs", "runs", "workflows", "stories", "epics"])
    forget.add_argument("key")
    start = commands.add_parser("job-start", help="register a spawned job (JSON object)")
    start.add_argument("job")
    finish = commands.add_parser("job-finish", help="record a finished job")
    finish.add_argument("id")
    finish.add_argument("--rc", type=int, default=0)
    finish.add_argument("--result", help="file holding the claude JSON result")
    commands.add_parser("digest-sent", help="mark today's digest as sent")
    return parser


def _run(args: argparse.Namespace, state: dict, now: int) -> tuple[str, bool]:  # noqa: PLR0911
    """Apply one command; return what to print and whether the state changed."""
    if args.command == "init":
        return "", True
    if args.command == "show":
        return _show(state, now), False
    if args.command == "get":
        return json.dumps(get_path(state, args.path)) + "\n", False
    if args.command == "set":
        set_path(state, args.path, json.loads(args.value))
        return "", True
    if args.command == "note":
        add_note(state, args.text, now)
        return "", True
    if args.command == "bump":
        return f"{bump(state, args.scope, args.key, args.kind, args.by)}\n", True
    if args.command == "clear":
        return "", clear(state, args.scope, args.key)
    if args.command == "reap":
        return "".join(f"{job_id}\n" for job_id in reap(state, _pid_alive, now)), True
    if args.command == "job-start":
        job_start(state, json.loads(args.job), now)
        return "", True
    if args.command == "digest-sent":
        digest_sent(state, now)
        return "", True
    result, raw = _read_result(args.result)
    outcome = job_finish(state, args.id, result=result, raw=raw, rc=args.rc, now=now)
    return json.dumps(outcome) + "\n", True


def main(argv: list[str] | None = None) -> int:
    """Run one state command under the state lock."""
    args = _parser().parse_args(argv)
    path = Path(args.state)
    now = int(time.time())
    try:
        if args.command in {"show", "get"}:
            output, _ = _run(args, load(path), now)
        else:
            with locked(path):
                state = load(path)
                output, changed = _run(args, state, now)
                if changed:
                    save(path, state)
    except (StateError, json.JSONDecodeError) as error:
        sys.stderr.write(f"state: {error}\n")
        return 1
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
