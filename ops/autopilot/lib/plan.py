#!/usr/bin/env python3
"""Turn one tick's observations into an ordered list of actions.

The shell collects facts with ``gh`` and ``git`` (open pull requests, workflow runs, epic
branches, a ``.meta`` snapshot, free memory) into a directory; this module reads them together
with the state file and decides what the tick does. It never calls ``gh`` or the network and
never changes anything, so a dry run and the unit tests see exactly what a live tick would do.

Output: one row per action, fields separated by the unit separator (0x1f):
``kind, six arguments, why``. Kinds:

  info            print only
  note            print and queue for the daily digest
  rerun-run       RUN_ID                         rerun a cancelled or timed-out develop run
  clear-budget    SCOPE KEY                      forget the retry counters of one item
  rerun-pr        PR RUN_IDS                     rerun cancelled checks of a pull request
  update-branch   PR HEAD_SHA                    rebase an approved story PR on its epic branch
  merge           PR STORY_ID ISSUE HEAD_SHA     rebase-merge a story PR into its epic branch
  needs-human     PR REASON                      label and comment once, then leave it alone
  open-epic       SLUG                           create epic/<slug> (the lock) and its draft PR
  open-epic-commit SLUG                          make the open-epic commit a branch still lacks
  open-epic-pr    SLUG                           open the missing draft PR of an epic branch
  epic-to-draft   PR SLUG                        take back a ready epic PR that conflicts
  spawn           JOB TARGET SLOT BRANCH BASE META   start a headless job

Usage:
  plan.py INPUT_DIR
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import ready
import state as st

SEP = "\x1f"
ARGS = 6
LOW_MEMORY_GB = 4
SPAWN_ORDER = ("fix-develop", "fix-pr", "integrate-epic", "approve-sdd", "review", "implement")
FAILED = {"FAILURE", "ERROR", "STARTUP_FAILURE", "ACTION_REQUIRED"}
INTERRUPTED = {"CANCELLED", "TIMED_OUT", "STALE"}
PASSING_RUN = {"success", "skipped", "neutral"}
RUN_ID = re.compile(r"/actions/runs/(\d+)")
FIX_DEVELOP_PREFIX = "fix/develop-"
DEPENDABOT = {"app/dependabot", "dependabot[bot]", "dependabot"}


@dataclass(frozen=True)
class Action:
    """One row of the plan."""

    kind: str
    why: str
    args: tuple[str, ...] = ()

    def row(self) -> str:
        """Return the action as one unit-separated line."""
        padded = [*self.args, *[""] * (ARGS - len(self.args))]
        fields = [self.kind, *padded, self.why]
        return SEP.join(str(value).replace(SEP, " ").replace("\n", " ") for value in fields)


def classify_checks(rollup: list[dict] | None) -> tuple[str, list[str]]:
    """Reduce a ``statusCheckRollup`` to one word and the runs worth rerunning.

    Returns ``none`` (no checks reported), ``failed``, ``cancelled`` (only cancelled or
    timed-out checks stand between the PR and green), ``pending`` or ``green``.
    """
    if not rollup:
        return "none", []
    seen: set[str] = set()
    interrupted: list[str] = []
    for check in rollup:
        if "status" in check or "conclusion" in check:
            finished = str(check.get("status") or "").upper() == "COMPLETED"
            value = str(check.get("conclusion") or "").upper()
        else:
            value = str(check.get("state") or "").upper()
            finished = value not in {"PENDING", "EXPECTED", ""}
        if not finished:
            seen.add("pending")
        elif value in FAILED:
            seen.add("failed")
        elif value in INTERRUPTED:
            seen.add("cancelled")
            run = RUN_ID.search(str(check.get("detailsUrl") or ""))
            if run and run.group(1) not in interrupted:
                interrupted.append(run.group(1))
        else:
            seen.add("green")
    for status in ("failed", "cancelled", "pending"):
        if status in seen:
            return status, interrupted
    return "green", interrupted


def _labels(pr: dict) -> set[str]:
    return {str(label.get("name")) for label in pr.get("labels") or []}


def _author(pr: dict) -> str:
    return str((pr.get("author") or {}).get("login") or "")


class Planner:
    """Builds the plan for one tick from a dict of observations (see :func:`load_inputs`)."""

    def __init__(self, inputs: dict) -> None:
        self.inputs = inputs
        self.now = int(inputs.get("now") or 0)
        self.state = st.normalise(inputs.get("state") or {})
        self.prs: list[dict] = list(inputs.get("prs") or [])
        self.develop: ready.Meta = inputs.get("meta") or ready.Meta()
        self.epic_meta: dict[str, ready.Meta] = inputs.get("epic_meta") or {}
        self.actions: list[Action] = []
        self.spawns: list[dict] = []
        self.candidates: list[ready.Story] = []
        self.done: set[str] = set()
        self.busy_prs = st.busy(self.state, "pr")
        self.busy_epics = st.busy(self.state, "epic")
        self._lookup: dict | None = None
        self._branches: dict[tuple[str, str], str] | None = None

    # --- small helpers --------------------------------------------------------------------

    def add(self, kind: str, why: str, *args: object) -> None:
        """Append an action row."""
        self.actions.append(Action(kind, why, tuple(str(arg) for arg in args)))

    def info(self, text: str) -> None:
        """Say something in the tick output only."""
        self.add("info", text)

    def note(self, text: str) -> None:
        """Say something in the tick output and in the next digest."""
        self.add("note", text)

    def spawn(self, job: str, target: object, why: str, **meta: object) -> None:
        """Queue a headless job; slots are handed out in :meth:`finish`."""
        self.spawns.append({"job": job, "target": str(target), "why": why, **meta})

    def _mine(self, pr: dict) -> bool:
        """Tell whether the autopilot may act on this pull request."""
        if not self.inputs.get("bot") or _author(pr) != self.inputs["bot"]:
            return False
        if self.inputs.get("pr_scope", "all") == "all":
            return True
        head, base = str(pr.get("headRefName")), str(pr.get("baseRefName"))
        prefixes = (ready.EPIC_BRANCH_PREFIX, FIX_DEVELOP_PREFIX)
        return base.startswith(ready.EPIC_BRANCH_PREFIX) or head.startswith(prefixes)

    def _story_of(self, pr: dict, slug: str | None = None) -> str:
        """Return the story a pull request delivers ("" when it cannot be told).

        The ``Story: <id>`` line of the body wins. A pull request without it is matched by its
        head branch against the working branches of the stories of its epic, so a forgotten
        line neither starts the story twice nor keeps the epic from finishing.
        """
        story = ready.story_id_from_body(pr.get("body"))
        if story:
            return story
        if self._branches is None:
            self._branches = {
                (item.epic or "", item.branch): item.id
                for item in self._index().values()
                if isinstance(item, ready.Story)
            }
        if slug is None:
            slug = str(pr.get("baseRefName") or "").removeprefix(ready.EPIC_BRANCH_PREFIX)
        return self._branches.get((slug, str(pr.get("headRefName") or "")), "")

    # --- develop and nightly workflows ----------------------------------------------------

    def develop_health(self) -> None:
        """Rerun or repair red workflow runs on ``develop``."""
        runs = self.inputs.get("runs") or {}
        for workflow, history in sorted((runs.get("push") or {}).items()):
            self._workflow(workflow, history, need=1)
        for workflow, history in sorted((runs.get("nightly") or {}).items()):
            self._workflow(workflow, history, need=2)

    def _workflow(self, workflow: str, history: list[dict], need: int) -> None:
        if not history or history[0].get("status") != "completed":
            return
        recent = [run for run in history if run.get("status") == "completed"][:need]
        if history[0].get("conclusion") in PASSING_RUN:
            # Green again: the next red streak of this workflow gets a fresh repair budget.
            if st.used(self.state, "workflows", workflow, "fix-develop"):
                self.add(
                    "clear-budget", f"{workflow} on develop is green again", "workflows", workflow
                )
            return
        if len(recent) < need or any(run.get("conclusion") in PASSING_RUN for run in recent):
            return
        latest = recent[0]
        run_id = str(latest.get("databaseId"))
        where = f"{workflow} on develop ({latest.get('url') or run_id})"
        if latest.get("conclusion") in {"cancelled", "timed_out"}:
            if st.allowed(self.state, "runs", run_id, "rerun"):
                self.add("rerun-run", f"{where} was {latest.get('conclusion')}", run_id)
                return
            if latest.get("conclusion") == "cancelled":
                self.note(f"{where} was cancelled again after one rerun")
                return
        self._repair_develop(workflow, run_id, where)

    def _repair_develop(self, workflow: str, run_id: str, where: str) -> None:
        """Start the one repair a red workflow gets.

        The budget belongs to the workflow, not to the run: every push and every night makes
        a new run, and a failure the job could not fix must not start a job per run.
        """
        open_fix = [
            pr for pr in self.prs if str(pr.get("headRefName")).startswith(FIX_DEVELOP_PREFIX)
        ]
        planned = any(spec["job"] == "fix-develop" for spec in self.spawns)
        running = any(job.get("kind") == "fix-develop" for job in self.state["jobs"].values())
        if open_fix:
            self.note(f"{where} is red; fix PR #{open_fix[0].get('number')} waits for the owner")
        elif planned or running:
            self.info(f"{where} is red; a fix-develop job is already on it")
        elif st.allowed(self.state, "workflows", workflow, "fix-develop"):
            self.spawn(
                "fix-develop",
                run_id,
                f"{where} is red",
                branch=f"{FIX_DEVELOP_PREFIX}{run_id}",
                base="origin/develop",
                run=run_id,
                workflow=workflow,
            )
        else:
            self.note(f"{workflow} on develop is still red after a fix attempt; it needs a look")

    # --- pull requests --------------------------------------------------------------------

    def pull_requests(self) -> None:
        """Decide what to do with every open pull request."""
        for pr in sorted(self.prs, key=lambda item: int(item.get("number") or 0)):
            number = pr.get("number")
            head, base = str(pr.get("headRefName")), str(pr.get("baseRefName"))
            if _author(pr) in DEPENDABOT:
                if classify_checks(pr.get("statusCheckRollup"))[0] == "green":
                    self.note(f"Dependabot PR #{number} is green and waits for the owner")
            elif not self._mine(pr):
                continue
            elif base.startswith(ready.EPIC_BRANCH_PREFIX):
                self._story_pr(pr)
            elif not head.startswith(ready.EPIC_BRANCH_PREFIX):
                self._owner_pr(pr, f"PR #{number}")

    def _blocked(self, pr: dict, what: str) -> bool:
        """Tell whether the PR must be left alone this tick."""
        if "needs-human" in _labels(pr):
            self.note(f"{what} waits for a human (needs-human)")
            return True
        return str(pr.get("number")) in self.busy_prs

    def _fix(self, pr: dict, reason: str) -> None:
        number = pr.get("number")
        if st.allowed(self.state, "prs", number, "fix"):
            head = str(pr.get("headRefName"))
            memory = self.state["stories"].get(self._story_of(pr), {})
            epic_pr = head.startswith(ready.EPIC_BRANCH_PREFIX)
            self.spawn(
                "fix-pr",
                number,
                reason,
                branch=head,
                base=f"origin/{head}",
                pr=number,
                reason=reason,
                epic_pr=epic_pr,
                # The epic field marks the epic branch as taken for the other epic jobs.
                epic=head.removeprefix(ready.EPIC_BRANCH_PREFIX) if epic_pr else "",
                resume=memory.get("session") or "",
                resume_slot=memory.get("slot") or 0,
            )
        else:
            self._escalate(pr, f"fix budget spent ({reason})")

    def _escalate(self, pr: dict, reason: str) -> None:
        number = pr.get("number")
        if not self.state["prs"].get(str(number), {}).get("escalated"):
            self.add("needs-human", f"PR #{number}: {reason}", number, reason)

    def _repair(self, pr: dict, checks: str, runs: list[str], *, rebase: bool = True) -> bool:
        """Queue the repair a red or conflicting PR needs; return whether one was needed.

        With ``rebase=False`` a conflict is not a reason for a fix round (the draft pull
        request of an epic branch, which fix-pr must not rebase).
        """
        number = pr.get("number")
        if rebase and pr.get("mergeable") == "CONFLICTING":
            self._fix(pr, "conflicts with its base branch")
        elif checks == "failed":
            self._fix(pr, "checks failed")
        elif checks == "cancelled":
            if runs and st.allowed(self.state, "prs", number, "rerun"):
                self.add("rerun-pr", f"PR #{number}: cancelled checks", number, " ".join(runs))
            else:
                self._fix(pr, "checks cancelled again after one rerun")
        else:
            return False
        return True

    def _owner_pr(self, pr: dict, what: str, *, rebase: bool = True) -> None:
        """Keep a PR to ``develop`` green; merging it is the owner's click."""
        if self._blocked(pr, what):
            return
        checks, runs = classify_checks(pr.get("statusCheckRollup"))
        if self._repair(pr, checks, runs, rebase=rebase):
            return
        if checks == "green" and not pr.get("isDraft"):
            self.note(f"{what} is green and waits for the owner: {pr.get('title')}")

    def _story_pr(self, pr: dict) -> None:
        """Drive a story PR to a rebase-merge into its epic branch."""
        number = pr.get("number")
        what = f"story PR #{number}"
        if pr.get("isDraft") or self._blocked(pr, what):
            return
        labels = _labels(pr)
        checks, runs = classify_checks(pr.get("statusCheckRollup"))
        if self._repair(pr, checks, runs):
            return
        if "ai-changes-requested" in labels:
            self._fix(pr, "review asked for changes")
        elif checks == "none":
            self.info(f"{what}: no checks reported yet (is epic/** in the workflow triggers?)")
        elif checks == "pending":
            self.info(f"{what}: checks running")
        elif "ai-approved" not in labels or not self._approved_head(pr):
            # The label alone is not enough: it must stand for the commit that is merged.
            stale = "ai-approved" in labels
            if st.allowed(self.state, "prs", number, "review"):
                head = str(pr.get("headRefName"))
                self.spawn(
                    "review",
                    number,
                    "green, changed since its approval" if stale else "green, not reviewed",
                    base=f"origin/{head}",
                    pr=number,
                    head_sha=str(pr.get("headRefOid") or ""),
                )
            else:
                self._escalate(pr, "review budget spent without an approval of its head commit")
        else:
            self._merge(pr, what)

    def _approved_head(self, pr: dict) -> bool:
        """Tell whether the reviewer approved exactly the commit the PR is at now."""
        approved = self.state["prs"].get(str(pr.get("number")), {}).get("approved_sha")
        return bool(approved) and approved == pr.get("headRefOid")

    def _merge(self, pr: dict, what: str) -> None:
        number = pr.get("number")
        sha = str(pr.get("headRefOid") or "")
        behind = (self.inputs.get("behind") or {}).get(str(number))
        if pr.get("mergeable") != "MERGEABLE" or behind is None:
            self.info(f"{what}: approved and green, mergeability not known yet")
        elif int(behind) > 0:
            self.add("update-branch", f"{what} is {behind} commits behind its epic", number, sha)
        else:
            story = self._story_of(pr)
            if not story:
                self.note(f"{what} names no story; its story will not count as done")
            item = self._index().get(story)
            issue = item.issue if item is not None and item.issue else ""
            self.add("merge", f"{what}: green, ai-approved, up to date", number, story, issue, sha)

    # --- epics ----------------------------------------------------------------------------

    def _index(self) -> dict:
        if self._lookup is None:
            self._lookup = self.develop.index()
            for meta in self.epic_meta.values():
                self._lookup.update(meta.index())
        return self._lookup

    def epics(self) -> None:
        """Advance every epic branch and open new epics when there is room."""
        slugs = [
            branch.removeprefix(ready.EPIC_BRANCH_PREFIX)
            for branch in self.inputs.get("epic_branches") or []
        ]
        working = sum(1 for slug in sorted(slugs) if self._epic(slug))
        self._open_epics(set(slugs), working)

    def _epic_pr(self, slug: str) -> dict | None:
        branch = ready.EPIC_BRANCH_PREFIX + slug
        for pr in self.prs:
            if pr.get("headRefName") == branch and pr.get("baseRefName") == "develop":
                return pr
        return None

    def _epic(self, slug: str) -> bool:
        """Plan one epic branch; return whether it still takes agent work."""
        meta = self.epic_meta.get(slug) or self.develop
        epic = meta.epics.get(slug)
        if epic is None:
            self.info(f"branch epic/{slug} has no .meta/epics/{slug}/epic.md; ignored")
            return False
        pr = self._epic_pr(slug)
        if pr is not None and not pr.get("isDraft"):
            self._ready_epic(slug, pr)
            return False
        if self._lock_commit_missing(slug, epic):
            # Nothing else can happen first: without a commit ahead of develop the draft
            # pull request cannot even be opened.
            self.add("open-epic-commit", f"epic/{slug} has no open-epic commit yet", slug)
            return True
        if pr is None:
            self.add("open-epic-pr", f"epic/{slug} has no pull request to develop", slug)
        else:
            what = f"epic PR #{pr.get('number')}"
            if pr.get("mergeable") == "CONFLICTING":
                # fix-pr must not rebase a branch that open story PRs build on; the rebase
                # on develop is integrate-epic's, when no story PR is open.
                self.info(f"{what} conflicts with develop; integrate-epic rebases it at the end")
            self._owner_pr(pr, what, rebase=False)
        stories = [story for story in meta.stories_of(slug) if story.status != "cancelled"]
        merged = (self.inputs.get("merged") or {}).get(slug) or []
        done = {self._story_of(item, slug) for item in merged}
        done |= {story.id for story in stories if story.status == "done"}
        specs = [story for story in stories if story.is_spec and story.id not in done]
        if specs and self.state["epics"].get(slug, {}).get("spec") != "approved":
            self._spec(slug)
            return True
        done |= {story.id for story in specs}
        self.done |= done
        work = [story for story in stories if not story.is_spec and story.id not in done]
        if work:
            self.candidates += work
        elif pr is not None and "needs-human" not in _labels(pr):
            self._integrate(slug, pr)
        return True

    def _lock_commit_missing(self, slug: str, epic: ready.Epic) -> bool:
        """Tell whether the epic branch still lacks its ``chore(meta): open epic`` commit.

        That happens when the branch was created and the commit then failed. Only the
        epic.md read from the epic branch itself counts (a dry run may only have develop's),
        and never once the epic is closed: the close-epic commit removes the lock fields.
        """
        return (
            slug in self.epic_meta
            and epic.locked_by != "autopilot"
            and epic.status not in {"done", "cancelled"}
            and slug not in self.busy_epics
        )

    def _ready_epic(self, slug: str, pr: dict) -> None:
        """Report an epic PR that was handed to the owner; take it back when it conflicts."""
        number = pr.get("number")
        what = f"epic PR #{number} ({slug})"
        if pr.get("mergeable") == "CONFLICTING":
            idle = slug not in self.busy_epics and "needs-human" not in _labels(pr)
            approved = pr.get("reviewDecision") == "APPROVED"
            if idle and not approved and st.allowed(self.state, "epics", slug, "integrate"):
                # develop moved after the hand-over: auto-merge can never fire like this.
                self.add(
                    "epic-to-draft", f"{what} is ready but conflicts with develop", number, slug
                )
            else:
                self.note(f"{what} is ready but conflicts with develop; it needs a look")
        elif classify_checks(pr.get("statusCheckRollup"))[0] == "failed":
            self.note(f"{what} is ready but its checks are red; it needs a look")
        else:
            self.note(f"{what} is ready and waits for the owner")

    def _spec(self, slug: str) -> None:
        if self.state["epics"].get(slug, {}).get("spec") == "escalated":
            self.note(f"epic {slug}: the SDD needs an owner decision (see the spec issue)")
        elif slug in self.busy_epics:
            self.info(f"epic {slug}: a job is running on the epic branch")
        elif st.allowed(self.state, "epics", slug, "sdd"):
            branch = ready.EPIC_BRANCH_PREFIX + slug
            self.spawn(
                "approve-sdd",
                slug,
                "review(spec) is todo",
                branch=branch,
                base=f"origin/{branch}",
                epic=slug,
            )
        else:
            self.note(f"epic {slug}: SDD not approved after {st.BUDGETS['sdd']} architect runs")

    def _integrate(self, slug: str, pr: dict) -> None:
        branch = ready.EPIC_BRANCH_PREFIX + slug
        open_stories = [item for item in self.prs if item.get("baseRefName") == branch]
        if open_stories or slug in self.busy_epics:
            self.info(f"epic {slug}: all stories merged or in review; waiting for open work")
        elif st.allowed(self.state, "epics", slug, "integrate"):
            self.spawn(
                "integrate-epic",
                slug,
                "all stories done",
                branch=branch,
                base=f"origin/{branch}",
                epic=slug,
                pr=pr.get("number"),
            )
        else:
            self.note(f"epic {slug}: integration failed twice; PR #{pr.get('number')} needs a look")

    def _open_epics(self, existing: set[str], working: int) -> None:
        todo = [
            epic
            for epic in self.develop.epics.values()
            if epic.status == "todo"
            and epic.slug not in existing
            and "deferred" not in epic.labels
            and any(story.status == "todo" for story in self.develop.stories_of(epic.slug))
        ]
        allow = str(self.inputs.get("epic_allow") or "")
        if not todo:
            return
        if not allow:
            self.info(f"{len(todo)} todo epics could be opened; none is enabled (AUTOPILOT_EPICS)")
            return
        try:
            pattern = re.compile(allow)
        except re.error as error:
            self.note(f"AUTOPILOT_EPICS is not a valid regex: {error}")
            return
        room = max(0, int(self.inputs.get("max_epics") or 1) - working)
        wanted = sorted(
            (epic for epic in todo if pattern.fullmatch(epic.slug)),
            key=lambda epic: (ready.PRIORITY.get(epic.priority, 2), epic.slug),
        )
        for epic in wanted[:room]:
            self.add("open-epic", f"{epic.title or epic.slug}: todo and enabled", epic.slug)
        if wanted[room:]:
            self.info(f"{len(wanted[room:])} enabled epics wait for a free epic lane")

    # --- stories --------------------------------------------------------------------------

    def stories(self) -> None:
        """Queue an implement job for every story that may start now."""
        index = self._index()
        in_flight: dict[str, ready.Story] = {}
        flying = st.busy(self.state, "story") | {
            self._story_of(pr)
            for pr in self.prs
            if str(pr.get("baseRefName")).startswith(ready.EPIC_BRANCH_PREFIX)
        }
        for story_id in flying:
            item = index.get(story_id)
            if isinstance(item, ready.Story):
                in_flight[item.id] = item
        exhausted = {
            story.id
            for story in self.candidates
            if not st.allowed(self.state, "stories", story.id, "implement")
        }
        picked, skipped = ready.select_ready(
            self.candidates,
            index,
            done=self.done,
            in_flight=in_flight,
            blocked_issues=set(self.inputs.get("needs_human_issues") or []),
            exhausted=exhausted,
        )
        for story in picked:
            self.spawn(
                "implement",
                story.id,
                story.title,
                branch=story.branch,
                base=f"origin/{ready.EPIC_BRANCH_PREFIX}{story.epic}",
                story=story.id,
                epic_of_story=story.epic,
                issue=story.issue,
            )
        by_id = {story.id: story for story in self.candidates}
        for story_id, reason in skipped.items():
            if by_id[story_id].status != "todo":
                continue
            if story_id in exhausted and story_id not in in_flight:
                self.note(f"story {story_id}: {st.BUDGETS['implement']} implement runs, no PR")
            else:
                self.info(f"story {story_id} waits: {reason}")

    # --- digest and slots -----------------------------------------------------------------

    def digest(self) -> None:
        """Queue the daily digest when it is due."""
        hour = self.inputs.get("digest_hour")
        running = any(job.get("kind") == "digest" for job in self.state["jobs"].values())
        if hour is not None and not running and st.digest_due(self.state, self.now, int(hour)):
            self.spawn("digest", "daily", "daily owner digest")

    @staticmethod
    def _slot(spec: dict, free: list[int]) -> int:
        """Take a free slot, preferring the one whose session the job wants to resume.

        A session can only be resumed from the worktree it ran in, so the resume request is
        dropped when that slot is taken.
        """
        wanted = int(spec.get("resume_slot") or 0)
        if spec.get("resume") and wanted in free:
            free.remove(wanted)
            return wanted
        if "resume" in spec:
            spec["resume"] = ""
        return free.pop(0)

    def finish(self) -> list[Action]:
        """Hand out worktree slots and return the finished plan."""
        limit = int(self.inputs.get("limit") or 0)
        memory = self.inputs.get("mem_free_gb")
        if memory is not None and float(memory) < LOW_MEMORY_GB and limit > 1:
            limit = 1
            self.info(f"{float(memory):.1f} GB free memory: one job at a time")
        held = st.used_slots(self.state)
        pool = range(1, int(self.inputs.get("pool") or limit) + 1)
        free = [slot for slot in pool if slot not in held][: max(0, limit - len(held))]
        cooling = st.in_cooldown(self.state, self.now)
        order = {job: position for position, job in enumerate(SPAWN_ORDER)}
        waiting = 0
        # One job per branch: a second job would detach the first one's worktree or push
        # over it. Running jobs hold their branch, and so does a job queued earlier here.
        taken = st.busy(self.state, "branch")
        for spec in sorted(self.spawns, key=lambda item: order.get(item["job"], len(order))):
            branch = str(spec.get("branch") or "")
            if branch in taken:
                self.info(f"{spec['job']} {spec['target']} waits: branch {branch} is in use")
                continue
            if cooling or (spec["job"] != "digest" and not free):
                waiting += 1
                continue
            if branch:
                taken.add(branch)
            slot = 0 if spec["job"] == "digest" else self._slot(spec, free)
            meta = {key: value for key, value in spec.items() if key not in {"why", "job"}}
            self.add(
                "spawn",
                spec["why"],
                spec["job"],
                spec["target"],
                slot,
                spec.get("branch", ""),
                spec.get("base", ""),
                json.dumps(meta, sort_keys=True),
            )
        if waiting:
            reason = "usage-limit cooldown" if cooling else "no free slot"
            self.info(f"{waiting} jobs wait ({reason})")
        return self.actions


def build_plan(inputs: dict) -> list[Action]:
    """Return the actions one tick takes for the given observations."""
    planner = Planner(inputs)
    planner.develop_health()
    planner.pull_requests()
    planner.epics()
    planner.stories()
    planner.digest()
    return planner.finish()


def _json(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _runs(folder: Path) -> dict[str, list[dict]]:
    runs: dict[str, list[dict]] = {}
    for path in sorted(folder.glob("*.json")):
        history = _json(path, [])
        if isinstance(history, list) and history:
            runs[str(history[0].get("workflowName") or path.stem)] = history
    return runs


def load_inputs(folder: str | Path) -> dict:
    """Read the directory the tick's collectors wrote into the dict :class:`Planner` takes."""
    root = Path(folder)
    inputs = dict(_json(root / "env.json", {}))  # type: ignore[call-overload]
    inputs["state"] = st.load(inputs.get("state_file") or root / "state.json")
    inputs["prs"] = _json(root / "prs.json", [])
    inputs["needs_human_issues"] = _json(root / "needs-human.json", [])
    inputs["runs"] = {"push": _runs(root / "runs/push"), "nightly": _runs(root / "runs/nightly")}
    branches = root / "epic-branches.txt"
    inputs["epic_branches"] = branches.read_text().split() if branches.exists() else []
    inputs["merged"] = {path.stem: _json(path, []) for path in (root / "merged").glob("*.json")}
    behind = root / "behind.tsv"
    inputs["behind"] = dict(
        line.split("\t")[:2]
        for line in (behind.read_text().splitlines() if behind.exists() else [])
        if "\t" in line and line.split("\t")[1].strip().isdigit()
    )
    inputs["meta"] = ready.load_meta(root / "meta/develop")
    inputs["epic_meta"] = {
        path.name: ready.load_meta(path)
        for path in (root / "meta/epics").glob("*")
        if path.is_dir()
    }
    return inputs


def main(argv: list[str] | None = None) -> int:
    """Print the plan for the observations in a directory."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        sys.stderr.write((__doc__ or "").strip() + "\n")
        return 2
    try:
        actions = build_plan(load_inputs(args[0]))
    except st.StateError as error:
        sys.stderr.write(f"plan: {error}\n")
        return 1
    sys.stdout.write("".join(action.row() + "\n" for action in actions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
