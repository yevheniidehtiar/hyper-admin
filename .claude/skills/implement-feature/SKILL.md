---
name: implement-feature
description: "Self-evaluating agentic workflow: plan → validate → implement with self-unblocking → open the PR"
argument-hint: "<issue-number> [base-branch]"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Write, Edit, Agent, Bash(git *), Bash(gh *), Bash(uv run *), Bash(uv sync *), Bash(./scripts/gitpm.sh *)
---

Implement one story using the self-evaluating agentic loop.

Arguments: `$ARGUMENTS`

- First token: the GitHub issue number of the story (`ISSUE` below).
- Optional second token: the base branch (`BASE` below). Story PRs of an epic use `epic/<slug>`;
  standalone work uses `develop`. When it is omitted, derive it in A1.

This skill ends when the PR is open. Review, CI repair, rebases and the merge belong to the
autopilot tick (`ops/autopilot/autopilot.sh tick`), not to this session.

It never waits for a human. When something is unclear, apply the decision ladder below and keep
going. Only the hard stops end the run early.

---

## Decision ladder (used by the A4 gate and by B3 blockers)

Work down the list and stop at the first step that answers the question:

1. **Memory.** Read the project memory index (`MEMORY.md`) and the entries whose description
   matches the topic.
2. **Project sources.** The story, its SDD (`docs/specs/`), `CONSTITUTION.md`, `.claude/rules/`,
   and the existing code and tests for the nearest similar feature.
3. **Research subagent.** Spawn one `Agent` with a narrow question (library behaviour, prior art
   in the repo, an upstream API). Use its answer as input, not as a decision.
4. **Decide.** Choose the most reversible option that satisfies `CONSTITUTION.md`. Record it in the
   `## Assumptions` section of the PR body and, when the story has an SDD, as a row in the SDD's
   Decision Log. Continue.

### Hard stops

Do not decide these yourself:

- secrets or billing
- pushing to the public mirror
- deleting data
- a PyPI release
- breaking public API (`__init__.py` exports, semver major)
- changing runtime dependency floors (`[project.dependencies]`)
- data-model migrations

On a hard stop: post the exact question as one comment on the issue, add the `needs-human` label
to the issue, and move on. Finish every part of the story that does not depend on the answer, open
the PR as a draft, put `needs-human` on the PR as well, and end the run. Never loop or sleep
waiting for a reply.

The merge rule reads the label on the PR ("`ai-approved` and no `needs-human`"), so the label on
the issue alone does not keep the PR out of the merge path. A PR that carries `needs-human` stays
a draft: this skill never runs `gh pr ready` on it (see C3).

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh issue comment "$ISSUE" --body "$(cat <<'EOF'
## needs-human

**Question:** <one precise question with the options you see>

**Why it is a hard stop:** <which item of the list above>

**State:** <what is done, what waits on the answer; link to the draft PR>
EOF
)"
GH_TOKEN="$CLAUDE_GH_TOKEN" gh issue edit "$ISSUE" --add-label needs-human

# As soon as the draft PR exists (B3 opens it):
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr edit <pr> --add-label needs-human
```

---

## Phase A — Planning Loop (no code written yet)

### A1. Read the story and resolve the base branch

```bash
ISSUE=<first token of the arguments>
BASE=<second token of the arguments, may be empty>

# Find story file by issue number
STORY_FILE=$(grep -rl "issue_number: $ISSUE" .meta/stories/ .meta/epics/*/stories/ 2>/dev/null | head -1)
cat "$STORY_FILE"
STORY_ID=$(grep -m1 '^id:' "$STORY_FILE" | awk '{print $2}')

# Parent epic, when the story lives under .meta/epics/<epic>/stories/
EPIC_FILE="$(dirname "$(dirname "$STORY_FILE")")/epic.md"
```

Resolve `BASE` when it was not passed:

1. The story has a parent epic and `git ls-remote --heads origin 'epic/*'` shows that epic's
   branch (its name is also the `branch:` field of `epic.md` on that branch) → `BASE=epic/<slug>`.
2. The story is standalone (`.meta/stories/`) → `BASE=develop`.
3. The story has a parent epic but no epic branch exists → the epic is not open. Do not create the
   branch yourself: the autopilot tick owns the lock (see Epic Branch Protocol in
   `.claude/project-config.md`). Print `SKIPPED: epic for #$ISSUE is not open` and end the run.
   This is a normal outcome, not an escalation: post nothing.

**Autopilot run (`AUTOPILOT=1`): check out the work branch now, before reading anything else.**
The job runs inside a reused pool worktree (`.claude/worktrees/ap-N`) whose checkout is whatever
the previous job left, while the architect rewrites story bodies and the SDD on the epic branch.
Planning from that checkout would use a stale story or SDD.

An earlier run may have left work behind (a hard stop that has since been answered, or a draft PR
after three failed fix attempts). Look for it first and resume from it. Never reset an existing
branch to the base: that drops its commits, and the later push would overwrite the branch behind
the draft PR.

```bash
git fetch origin "$BASE"
if git ls-remote --exit-code --heads origin "feat/issue-$ISSUE" >/dev/null; then
  # Earlier run, pushed: resume from the remote branch
  git fetch origin "feat/issue-$ISSUE"
  git switch -C "feat/issue-$ISSUE" "origin/feat/issue-$ISSUE"
  git rebase "origin/$BASE"
elif git rev-parse -q --verify "refs/heads/feat/issue-$ISSUE" >/dev/null; then
  # Earlier run, never pushed: resume from the local branch
  git switch "feat/issue-$ISSUE"
  git rebase "origin/$BASE"
else
  git switch -C "feat/issue-$ISSUE" "origin/$BASE"
fi

cat "$STORY_FILE"   # read the story again, now from the right checkout
```

When resuming, read the existing commits (`git log "origin/$BASE"..HEAD`), the draft PR body and
the answers on the issue, and plan only what is still missing.

Then:
- Read `ROADMAP.md` to confirm scope and priority. Do NOT expand scope beyond the story
- Read the SDD the story links to (`Spec: docs/specs/{slug}.md`), if any
- Read every source file and test file referenced in the story body
- Explore relevant modules in `src/hyperadmin/` to understand existing patterns

### A2. Create an implementation plan

Decompose the issue into ordered sub-tasks. Each sub-task must state:
- Target file path
- What changes (new function, new class, updated logic)
- Which test file and test name will cover it

Order MUST follow this strict bottom-up sequence — no exceptions:
1. Domain models and core contracts (`core/`, `adapters/`)
2. Business logic and unit tests
3. Views, routes, and middleware (`views/`, `routing.py`)
4. UI templates and E2E tests (`templates/`, `tests/e2e/`)

### A3. Self-evaluate the plan

Evaluate every item below. Label each **PASS** or **FAIL**:

**Architecture — CONSTITUTION.md**
- [ ] No sub-task puts business logic inside a view handler or template
- [ ] No sub-task imports from an outer layer into `core/` (dependency direction: `views/ → core/ → adapters/`)
- [ ] No new file is named `utils.py`, `helpers.py`, `misc.py`, or `common.py`
- [ ] No sub-task touches Phase 3 domains (`auth/`, `actions/`, `uploads/`) unless the issue explicitly targets Phase 3
- [ ] Module nesting stays ≤ 2 levels deep; modules stay under ~300 LOC (flag if exceeded)

**Ordering — planning-playbook.md**
- [ ] Models and core contracts are completed before any business logic sub-task
- [ ] Business logic is completed before any view/route sub-task
- [ ] Views/routes are completed before any UI/template sub-task
- [ ] No sub-task depends on a later sub-task in the plan

**Code style — code-style.md**
- [ ] Every new function and method in the plan carries type hints
- [ ] No line exceeds 100 characters
- [ ] Relationship queries use `selectinload()`; large collections use pagination
- [ ] No placeholder code: no `pass`, no `TODO`, no commented-out blocks in final code

**Testing — testing.md**
- [ ] Every logic sub-task has a corresponding test-first step (failing test before implementation)
- [ ] E2E tests use accessibility-first locators: `get_by_role` > `get_by_label` > `get_by_text` > `get_by_test_id`
- [ ] E2E tests contain NO `page.locator('.ha-*')` or positional CSS selectors
- [ ] Every changed line under `src/` is covered (`poe test:cov-diff`, 100% patch)

**Conflicts — conflict-avoidance.md**
- [ ] The plan touches only the files in the story's `## Files to Change` (plus new files)
- [ ] No sub-task edits a story's or epic's `status:` in `.meta`
- [ ] Hotspot files get a minimal diff in their own hunk

**Git — git-workflow.md**
- [ ] All commits use identity `user.name="Claude Code"`, `user.email="noreply+claude-code@anthropic.com"`
- [ ] No `Co-Authored-By` trailers on any commit
- [ ] Commit messages follow Conventional Commits: `type(scope): description (#<issue>)`
- [ ] PR will be created with `GH_TOKEN="$CLAUDE_GH_TOKEN"` against `$BASE`

### A4. Gate decision

**If ALL items are PASS** → proceed to Phase B.

**If ANY item is FAIL**, do not post a questionnaire and do not stop. For each failing item:

1. If the plan itself is wrong (ordering, a forbidden file name, a missing test step), fix the plan
   and re-evaluate.
2. If the item fails because something is ambiguous or undecided, run the decision ladder. The
   outcome of step 4 goes into your notes for the PR's `## Assumptions` section.
3. If resolving it needs one of the hard stops, follow the hard-stop procedure for that part only
   and plan the rest of the story around it.

Proceed to Phase B once every item is PASS or covered by a recorded assumption.

---

## Phase B — Implementation with self-unblocking

### B1. Start the worktree

**Autopilot run (`AUTOPILOT=1`)**: the job already runs inside a pool worktree
(`.claude/worktrees/ap-N`) and A1 put it on `feat/issue-$ISSUE`. Do not create another worktree
and do not switch again.

**Interactive run**: `/wt feat/issue-$ISSUE $BASE` creates an isolated worktree. It starts from
`origin/feat/issue-$ISSUE` when that branch exists (resume, then `git rebase "origin/$BASE"`) and
from `origin/$BASE` otherwise.

Then sync the environment (interactive runs only; the autopilot pool syncs its worktrees itself):
```bash
uv sync --all-extras
```

All subsequent commands (file edits, `uv run poe lint`, `uv run poe test`, etc.) run from inside
the worktree.

### B2. TDD execution loop

For each sub-task in the plan, in strict order:

1. **Write the failing test first** — unit test in `tests/unit/` or E2E in `tests/e2e/`
2. **Implement the minimal code** to make the test pass
3. **Refactor** — add strict type hints, remove any placeholders, ensure line length ≤ 100
4. **Verify**: `uv run poe test:unit`

After completing all backend sub-tasks (before moving to UI), run an early lint check:
```bash
uv run poe lint
```
Fix any issues before continuing to UI sub-tasks.

### B3. Blocker protocol

A blocker is anything that prevents moving forward: a failing test you cannot fix, a missing
dependency, an unclear requirement, an architectural ambiguity.

Run the decision ladder:

- Steps 1–3 found the answer → apply it and continue.
- Otherwise step 4: pick the most reversible option, write it down for `## Assumptions` (and the
  SDD Decision Log), continue.
- The blocker is a hard stop → follow the hard-stop procedure. Commit what is done (hooks on, never
  `--no-verify`; if a hook fails, fix the cause), push, and open the PR as a draft against `$BASE`
  so the progress is visible:

  ```bash
  git add -A
  git -c user.name="Claude Code" -c user.email="noreply+claude-code@anthropic.com" \
    commit -m "feat: partial implementation, waiting on a decision (#$ISSUE)"
  git push --force-with-lease origin HEAD
  # Skip the create when a draft PR already exists from an earlier run
  GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create --draft --base "$BASE" \
    --title "<type(scope): description> (#$ISSUE)" --body-file <body-file, see C3>
  GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr edit --add-label needs-human
  ```

  Then continue with any sub-task that does not depend on the answer. End the run when nothing
  independent is left. The PR stays a draft with `needs-human` for the rest of this run, however
  much of the story gets finished.

A test that still fails after three distinct fix attempts is not a reason to stop either: record
what was tried in the PR body, mark the PR as draft, and end the run. The tick's `fix-pr` job and
its retry budget take over.

### B4. Memory update after resolving a blocker

Once a blocker is resolved by steps 2–4 of the ladder, write a memory entry before continuing so
the next run stops at step 1:

Create a new file in your project memory directory (the directory containing `MEMORY.md`).

Name it descriptively (e.g., `feedback_sqlmodel_inspector.md`). Use this format:

```markdown
---
name: <short descriptive name>
description: <one-line summary — used to match against future blockers>
type: feedback
---

<Lead with the rule or pattern that resolves the blocker>

**Why:** <what caused the blocker and why this solution works>

**How to apply:** <concrete steps or code snippet; when to apply this>
```

Then update `MEMORY.md` to add a pointer:
```
- [filename.md](filename.md) — one-line hook matching the memory description
```

---

## Phase C — Submission

### C1. Full quality gates

```bash
uv run poe lint                                  # pre-commit hooks, zero errors
uv run ruff check . && uv run ruff format --check .   # what CI runs
uv run poe test:cov-diff                         # unit tests + 100% of changed lines covered
uv run poe test:e2e                              # only when the story touches templates, CSS or views
```

Do not proceed until they pass. Fix every failure before continuing.

`test:cov-diff` compares against `origin/develop`. On an epic branch the diff also contains the
epic's earlier stories; they are covered already, so the result still has to be 100%.

### C2. Final self-review

Confirm each item before committing:
- [ ] New test files exist for all new logic
- [ ] `selectinload()` used for every relationship query
- [ ] No commented-out code, no `TODO` or `pass` placeholders
- [ ] No `.ha-*` CSS class selectors in E2E tests
- [ ] Type hints on all new functions and methods
- [ ] No `.meta` `status:` edits in the diff

### C3. Commit and open PR

Commit first, then rebase onto the latest base, then push. `git rebase` refuses to start with
uncommitted changes, so the order matters. This project uses rebase-merge: merged PRs rewrite
hashes on the base branch, so the branch must be current to produce a clean diff.

```bash
git add -A
git -c user.name="Claude Code" -c user.email="noreply+claude-code@anthropic.com" \
  commit -m "feat: <description> (#$ISSUE)"

git fetch origin "$BASE"
git rebase "origin/$BASE"

git push --force-with-lease origin HEAD
```

If the rebase changed anything under `src/` or `tests/`, run the C1 gates again before the push.

Write the PR body to a file. The `Story:` line and the `## Assumptions` section are required: the
tick matches the PR to its story by the first, the reviewer and the owner read the second.

```markdown
Story: <STORY_ID>
Issue: #<ISSUE>

## Summary
<what changed and why, 2–5 lines>

## Assumptions
<one bullet per decision taken at ladder step 4: the question, the option chosen, why it is the
most reversible one. Write "None." when there were none.>

## Test plan
- `poe test:cov-diff`: <result>
- <manual test scenarios for user-facing changes>
```

**If a draft PR already exists** (from a hard stop or from an earlier run), update its body, then
check whether a question is still open before touching the draft state:

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr edit --body-file <body-file>
gh pr view --json labels --jq '.labels[].name'
gh issue view "$ISSUE" --json labels --jq '.labels[].name'
```

- `needs-human` is on the PR or on the issue, or this run raised a hard stop: **do not run
  `gh pr ready`**. Leave the PR a draft and go to C5. The owner's answer removes the label; the
  next run of this skill finishes the story and marks the PR ready.
- Neither carries `needs-human`, the story is complete and the C1 gates pass:

  ```bash
  GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr ready
  ```

**If no PR exists yet:**
```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create --base "$BASE" \
  --title "<type(scope): description> (#$ISSUE)" --body-file <body-file>
```

**If `CLAUDE_GH_TOKEN` is not set:** do not create the PR under the user's identity. Leave the
branch pushed, print `STOPPED: CLAUDE_GH_TOKEN is not set`, and end the run.

### C4. Write implementation memory

Write a memory entry summarizing what was learned — focus on non-obvious decisions and
patterns that future implementations should reuse:

```markdown
---
name: issue-<ISSUE>-learnings
description: <one-line summary of the key pattern or decision made>
type: project
---

<Lead with the key decision or pattern>

**Why:** <what drove this decision — constraint, architectural rule, tradeoff>

**How to apply:** <when and how future implementations should use this pattern>
```

Add the entry to `MEMORY.md`.

### C5. Hand over

Print the PR number, whether it is a draft (and the open `needs-human` question when there is
one), the base branch and the list of assumptions, then end the run.

From here the autopilot tick owns the PR: the `review` job sets `ai-approved` or
`ai-changes-requested`, the `fix-pr` job repairs failing checks and review findings, and the tick
rebase-merges the PR into `$BASE` when everything is green. Do not register a monitor, do not
merge, do not close the issue, and do not edit the story's status.

For an interactive debugging run without launchd, `/autopilot-tick` runs one tick by hand.
