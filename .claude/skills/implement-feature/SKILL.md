---
name: implement-feature
description: "Self-evaluating agentic workflow: plan → validate → implement with blocker handling → learn"
argument-hint: "<issue-number>"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git *), Bash(gh *), Bash(poe *), Bash(uv run *), CronCreate, CronDelete, CronList, ToolSearch
---

Implement GitHub issue $ARGUMENTS for HyperAdmin using the self-evaluating agentic loop.

---

## Phase A — Planning Loop (no code written yet)

### A1. Read and understand the issue

```bash
gh issue view $ARGUMENTS
```

Then:
- Read `ROADMAP.md` to confirm scope and priority — do NOT expand scope beyond the issue
- Read every source file and test file referenced in the issue body
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
- [ ] Coverage target for new code: 99%

**Git — git-workflow.md**
- [ ] All commits use identity `user.name="Claude Code"`, `user.email="noreply+claude-code@anthropic.com"`
- [ ] No `Co-Authored-By` trailers on any commit
- [ ] Commit messages follow Conventional Commits: `type(scope): description (#$ARGUMENTS)`
- [ ] PR will be created with `GH_TOKEN="$CLAUDE_GH_TOKEN"` — verify token is set before proceeding

### A4. Gate decision

**If ALL items are PASS** → proceed to Phase B.

**If ANY item is FAIL**:
1. List every failing item and the specific question that must be answered to resolve it
2. Post the list as a questionnaire on the issue:
   ```bash
   gh issue comment $ARGUMENTS --body "$(cat <<'EOF'
   ## Planning Gate — Questions Before Implementation

   Before I can proceed, the following items in my plan are ambiguous or blocked:

   <list each failing checklist item and your specific question>

   Please update the issue with your answers and re-run `/implement-feature $ARGUMENTS`.
   EOF
   )"
   ```
3. Print: `STOPPED: Questionnaire posted on issue #$ARGUMENTS. Re-run this skill after the issue is updated.`
4. **HALT. Do not write any code.**

---

## Phase B — Implementation with Blocker Handling

### B1. Create worktree and branch

Always work in an isolated worktree branched from the latest `develop`. Never commit or branch off whatever the current working tree happens to be on.

```bash
# Fetch latest develop first
git fetch origin develop

# Derive paths
REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_PATH="${REPO_ROOT}/../hyper-admin-issue-$ARGUMENTS"
BRANCH_NAME="feat/issue-$ARGUMENTS"

# Create worktree+branch, or resume and rebase if it already exists.
# This project uses rebase-merge: every merged PR rewrites commit hashes on develop,
# so any existing branch MUST be rebased from origin/develop before new work is added.
if git worktree list | grep -qF "[$BRANCH_NAME]"; then
  echo "Resuming existing worktree at $WORKTREE_PATH — rebasing onto origin/develop"
  cd "$WORKTREE_PATH"
  git rebase origin/develop
else
  git worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" origin/develop
  echo "Created new worktree at $WORKTREE_PATH"
  cd "$WORKTREE_PATH"
fi
```

All subsequent commands (file edits, `poe lint`, `poe test`, `uv run`, etc.) run from inside the worktree path `$WORKTREE_PATH`.

If a draft PR already exists for this branch, resume from the rebased worktree state — do not restart.

### B2. TDD execution loop

For each sub-task in the plan, in strict order:

1. **Write the failing test first** — unit test in `tests/unit/` or E2E in `tests/e2e/`
2. **Implement the minimal code** to make the test pass
3. **Refactor** — add strict type hints, remove any placeholders, ensure line length ≤ 100
4. **Verify**: `uv run poe test`

After completing all backend sub-tasks (before moving to UI), run an early lint check:
```bash
uv run poe lint
```
Fix any issues before continuing to UI sub-tasks.

### B3. Blocker protocol

When you encounter a blocker (failing test you cannot fix, missing dependency, unclear
requirement, architectural ambiguity, or any issue that prevents moving forward):

**Step 1 — Search memory for prior solutions:**

Read your project memory index (`MEMORY.md`) and any files whose description
matches the blocker topic. The auto-memory system provides the concrete path
at runtime.

**If a relevant solution is found** → apply it and continue. Update the memory entry if you
discovered a refinement.

**If no solution is found** → proceed to Step 2.

**Step 2 — Document, commit WIP, and halt:**

```bash
# Commit everything in-progress (skip pre-commit hooks — this is a WIP save)
git -c user.name="Claude Code" -c user.email="noreply+claude-code@anthropic.com" \
  commit -n -m "wip: partial implementation, blocked (#$ARGUMENTS)"

git push origin HEAD

# Create draft PR (or update existing one)
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create --draft --fill
# If draft already exists: GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr ready --undo
```

Post blocker details as an issue comment:
```bash
gh issue comment $ARGUMENTS --body "$(cat <<'EOF'
## Implementation Blocker

**What was attempted:** <describe what you tried>

**The blocker:** <precise description of the error, ambiguity, or missing piece>

**What is needed to unblock:** <specific ask — e.g., clarify X, provide Y, decide between A and B>

Draft PR with current progress is open. Re-run `/implement-feature $ARGUMENTS` after the blocker is resolved.
EOF
)"
```

Print: `STOPPED: Blocker documented on issue #$ARGUMENTS. Draft PR contains current progress.`

**HALT.**

### B4. Memory update after resolving a blocker

Once a blocker is resolved (either by memory lookup or by human input on the issue), write a
memory entry before continuing:

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
uv run poe lint   # must pass with zero errors
uv run poe test   # all unit + E2E tests must pass
```

Do not proceed until both pass. Fix every failure before continuing.

### C2. Final self-review

Confirm each item before committing:
- [ ] New test files exist for all new logic
- [ ] `selectinload()` used for every relationship query
- [ ] No commented-out code, no `TODO` or `pass` placeholders
- [ ] No `.ha-*` CSS class selectors in E2E tests
- [ ] Type hints on all new functions and methods

### C3. Commit and open PR

Rebase onto the latest `develop` before committing. This project uses rebase-merge: merged PRs
rewrite hashes on `develop`, so the branch must be current to produce a clean diff.

```bash
git fetch origin develop
git rebase origin/develop

git -c user.name="Claude Code" -c user.email="noreply+claude-code@anthropic.com" \
  commit -m "feat: <description> (#$ARGUMENTS)"

git push origin HEAD
```

**If a draft PR already exists** (from a prior blocker stop):
```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr ready
```

**If no PR exists yet:**
```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create --fill
```

**If `CLAUDE_GH_TOKEN` is not set: STOP and tell the user** — do not create the PR under their identity.

### C4. Write implementation memory

Write a memory entry summarizing what was learned — focus on non-obvious decisions and
patterns that future implementations should reuse:

```markdown
---
name: issue-$ARGUMENTS-learnings
description: <one-line summary of the key pattern or decision made>
type: project
---

<Lead with the key decision or pattern>

**Why:** <what drove this decision — constraint, architectural rule, tradeoff>

**How to apply:** <when and how future implementations should use this pattern>
```

Add the entry to `MEMORY.md`.

---

## Phase D — PR Review Monitor

Register a cron job that watches the PR every 10 minutes and drives it through its full lifecycle:
CI failures → review changes → approved → merged → close issue. All states are handled autonomously.

### D1. Capture PR number and branch

```bash
PR_NUMBER=$(GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr view --json number -q .number)
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)
echo "Monitoring PR #$PR_NUMBER on branch $BRANCH_NAME for issue #$ARGUMENTS"
```

### D2. Check for existing monitor (resume guard)

Use `CronList` to see if a monitor for this issue is already registered. If a cron whose name
matches `pr-monitor-$ARGUMENTS` already exists, skip D3 — it is already running.

### D3. Register the monitoring cron

Use `CronCreate` with:
- **Name:** `pr-monitor-$ARGUMENTS`
- **Schedule:** `*/10 * * * *`
- **Prompt** (with `$ARGUMENTS` and `$PR_NUMBER` substituted at registration time):

```
You are the PR lifecycle monitor for issue #$ARGUMENTS in yevheniidehtiar/hyper-admin.
Run every step in order. Do not skip steps.

## Step 1 — Fetch full PR state

Run both commands:
  gh pr view $PR_NUMBER --json number,state,reviewDecision,mergedAt,headRefName \
    --repo yevheniidehtiar/hyper-admin
  gh pr checks $PR_NUMBER --repo yevheniidehtiar/hyper-admin

Collect:
  - `state`          (OPEN / MERGED / CLOSED)
  - `reviewDecision` (null / REVIEW_REQUIRED / APPROVED / CHANGES_REQUESTED)
  - `failingChecks`  — list of check names where status is FAIL or ERROR

## Step 2 — Merged → close issue and stop

If `state == "MERGED"`:
  1. Close the issue:
       gh issue close $ARGUMENTS --reason completed \
         --comment "Closed: merged via PR #$PR_NUMBER." \
         --repo yevheniidehtiar/hyper-admin
  2. Delete this cron using CronDelete (name: pr-monitor-$ARGUMENTS).
  3. Print: "PR #$PR_NUMBER merged. Issue #$ARGUMENTS closed. Monitor stopped."
  HALT.

## Step 3 — Failing CI checks → diagnose and fix

If `failingChecks` is non-empty:
  1. For each failing check, fetch the log:
       gh run list --branch $BRANCH_NAME --repo yevheniidehtiar/hyper-admin \
         --json databaseId,name,conclusion --limit 5
       gh run view <run-id> --log-failed --repo yevheniidehtiar/hyper-admin
  2. Check out the branch and rebase onto latest develop:
       git fetch origin
       git checkout $BRANCH_NAME
       git rebase origin/develop
     Rebase is required because this project uses rebase-merge — merged PRs rewrite hashes
     on develop, and a stale branch produces a misleading diff and may fail CI on tree conflicts.
  3. Read the error output carefully. Diagnose root cause (lint error, type error,
     failing test, import error, etc.) and apply the minimal fix using Edit/Write.
  4. Run the same check locally to confirm the fix:
       uv run poe lint   (if lint check failed)
       uv run poe test   (if test check failed)
     Do not proceed until the local check passes.
  5. Commit and push (force-with-lease because rebase rewrites history):
       git -c user.name="Claude Code" -c user.email="noreply+claude-code@anthropic.com" \
         commit -m "fix(ci): fix failing checks (#$ARGUMENTS)"
       git push --force-with-lease origin HEAD
  6. Comment on the PR:
       gh pr comment $PR_NUMBER \
         --body "CI fix pushed: $(git rev-parse --short HEAD) — re-running checks." \
         --repo yevheniidehtiar/hyper-admin
  7. Print: "CI fixes pushed. Continuing to monitor."
  Continue (do NOT stop the cron — wait for checks to go green).

## Step 4 — Changes requested → apply review feedback

If `reviewDecision == "CHANGES_REQUESTED"` (and no failing checks from Step 3):
  1. Fetch all review comments:
       gh api repos/yevheniidehtiar/hyper-admin/pulls/$PR_NUMBER/reviews
       gh api repos/yevheniidehtiar/hyper-admin/pulls/$PR_NUMBER/comments
  2. Check out the branch and rebase onto latest develop:
       git fetch origin
       git checkout $BRANCH_NAME
       git rebase origin/develop
     Rebase is required because this project uses rebase-merge — merged PRs rewrite hashes
     on develop, and a stale branch produces a misleading diff.
  3. Read each review comment and apply the requested change using Edit/Write.
  4. Run quality gates locally:
       uv run poe lint
       uv run poe test
     Fix any failures before committing.
  5. Commit and push (force-with-lease because rebase rewrites history):
       git -c user.name="Claude Code" -c user.email="noreply+claude-code@anthropic.com" \
         commit -m "fix(review): address review feedback (#$ARGUMENTS)"
       git push --force-with-lease origin HEAD
  6. Re-request review from the reviewer(s) who left change requests:
       gh pr edit $PR_NUMBER --add-reviewer <reviewer-login> \
         --repo yevheniidehtiar/hyper-admin
  7. Comment on the issue:
       gh issue comment $ARGUMENTS \
         --body "Review feedback addressed in $(git rev-parse --short HEAD). Re-requested review." \
         --repo yevheniidehtiar/hyper-admin
  8. Print: "Review changes applied. Re-requested review. Continuing to monitor."
  Continue (do NOT stop the cron).

## Step 5 — Approved and checks green → enable auto-merge

If `reviewDecision == "APPROVED"` and `failingChecks` is empty and `state == "OPEN"`:
  1. Enable squash auto-merge:
       GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr merge $PR_NUMBER --auto --squash \
         --repo yevheniidehtiar/hyper-admin
  2. Comment on the PR:
       gh pr comment $PR_NUMBER \
         --body "Auto-merge enabled — all checks green and review approved." \
         --repo yevheniidehtiar/hyper-admin
  3. Print: "PR #$PR_NUMBER approved and checks green. Auto-merge enabled."
  Continue (do NOT stop the cron — next cycle detects the merge).

## Step 6 — Waiting

If `state == "OPEN"` and no action was taken in Steps 3–5:
  Print: "PR #$PR_NUMBER is open — checks: <summary>, review: <reviewDecision>. Next check in 10 min."
  HALT (cron fires again automatically).
```

### D4. Confirm registration

After `CronCreate` succeeds, print:
```
Monitor registered: pr-monitor-$ARGUMENTS (every 10 min)
  PR: #$PR_NUMBER
  Issue: #$ARGUMENTS
  Branch: $BRANCH_NAME
  Will fix failing CI checks, address review changes, enable auto-merge on approval,
  close issue on merge, and stop itself automatically.
```

**DONE.** The workflow is now fully autonomous until the issue is closed.
