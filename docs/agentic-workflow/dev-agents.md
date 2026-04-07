# Dev Agent

| Property | Value |
|---|---|
| **Runtime** | Claude Code (Opus for size:M/L, Sonnet for size:S) |
| **Trigger** | User runs `/implement-feature <issue>`, `/fix-issue <issue>`, or launches without arguments |
| **Purpose** | Pick up GitHub issues, implement code changes, manage issue lifecycle end-to-end |
| **Est. Cost** | 20k–100k tokens per implementation task |

---

## Core Behavior

The dev agent is **proactive and self-directed**. It does not wait to be told what to do —
it finds work, claims it, implements it, and drives the PR through to merge.

### Invocation modes

| Mode | What happens |
|---|---|
| `/implement-feature 375` | Implements issue #375 directly |
| `/fix-issue 401` | Lightweight TDD fix for issue #401 |
| No issue given | Runs the **work discovery** protocol (see below) |

---

## Work Discovery Protocol (no issue provided)

When the dev agent starts without a specific issue number:

### 1. Find the active milestone

```bash
# Read milestones from .meta/
for f in .meta/roadmap/milestones/*.md; do
  STATUS=$(grep '^status:' "$f" | awk '{print $2}')
  [ "$STATUS" = "open" ] && head -10 "$f" && break
done
```

If no open milestone exists, report that and stop.

### 2. List ready stories in that milestone

```bash
# Find the milestone ID
MILESTONE_ID=$(grep '^id:' "$MILESTONE_FILE" | awk '{print $2}')

# Find epics linked to this milestone
EPIC_DIRS=$(grep -rl "$MILESTONE_ID" .meta/epics/*/epic.md 2>/dev/null | xargs -I{} dirname {})

# Find stories with status=todo and agent-task label in those epics
for DIR in $EPIC_DIRS; do
  grep -rl 'status: todo' "$DIR/stories/" 2>/dev/null \
    | xargs grep -l 'agent-task' 2>/dev/null
done
```

Prioritize by:
1. Issues with `blocked_by` dependencies already closed (unblocked)
2. Issues labeled `size:S` before `size:M` before `size:L`
3. Issues with higher priority labels (`P0` > `P1` > `P2` > `P3`)

If no `agent-task` issues are unassigned, fall back to any unassigned issue in the milestone.

### 3. Present the pick to the user

```
Found 4 ready tickets in v0.3.0 — Zero-Config & Auth:

  #363  feat(core): model introspection utility          size:M  P1
  #364  feat(core): infer list_display                   size:S  P1
  #365  feat(core): infer search_fields                  size:S  P1
  #368  feat(core): extend AdminOptions None defaults    size:S  P2

Start with #364? (Y / pick another / skip)
```

On confirmation, proceed to implementation.

---

## Issue Lifecycle Management

The dev agent owns the full lifecycle of every issue it works on.
All label and project board mutations happen **automatically** — never deferred.

### Status transitions (in .meta/)

| Event | .meta/ status | GitHub label sync |
|---|---|---|
| Agent claims story | `in_progress` | Add `in-progress`, remove `ready` |
| Planning gate fails | `in_progress` + `needs-clarification` label | Sync via `gitpm push` |
| Blocker hit (draft PR) | `in_progress` + `blocked` label | Sync via `gitpm push` |
| PR created | `in_review` | Add `review` label to PR |
| PR merged | `done` | Sync via `gitpm push` |

Update the `.meta/` story file frontmatter directly, then sync labels to GitHub:

```bash
# After editing .meta/ story status, sync to GitHub:
bun "$GITPM_CLI" push --meta-dir .meta --token "$GITHUB_TOKEN"

# PR labels still managed via gh pr (gitpm doesn't handle PRs):
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr edit <pr-number> --add-label "review"
```

### Issue comments

The agent posts structured comments at every significant state change:

- **Claimed**: "Starting work on this issue. Branch: `feat/issue-<N>`"
- **Plan ready**: Summary of implementation plan (sub-tasks, files to touch)
- **Blocker**: Detailed blocker description with specific unblock request
- **PR opened**: Link to PR with brief description of changes
- **PR merged**: "Completed. Merged via PR #<N>."

---

## Execution Flow

```
1. /start feat/issue-<N>         ← isolated worktree + env bootstrap
2. Claim issue (labels + board)
3. Phase A: Planning loop         ← read issue, plan, self-evaluate
4. Phase B: TDD implementation    ← test-first, blocker protocol
5. Phase C: Submission            ← lint, test, commit, PR
6. Phase D: PR monitor cron       ← CI fix, review changes, auto-merge
7. Issue closed on merge          ← labels + board updated
```

### Step 1 — Start worktree

Every implementation begins with `/start`:

```
/start feat/issue-<N>
```

This creates an isolated worktree from `develop`, rebases, bootstraps `uv sync --all-extras`,
and confirms the environment is ready.

### Step 2 — Claim the issue

Immediately after entering the worktree:

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh issue edit <N> \
  --remove-label "ready" --add-label "in-progress"
gh issue comment <N> --body "Starting work. Branch: \`feat/issue-<N>\`"
```

Update the project board status to "In progress".

### Steps 3–6 — Planning, implementation, submission, monitoring

These phases are defined in the skill files:

| Size | Skill | Behavior |
|---|---|---|
| `size:S` | `fix-issue` | Lightweight TDD loop, no self-eval gate |
| `size:M` | `implement-feature` | Full self-evaluating plan, TDD, blocker protocol, PR monitor |
| `size:L` | `implement-feature` + human checkpoint | Plan presented to user for approval before implementation |

See:
- `.claude/skills/implement-feature/SKILL.md` — full agentic workflow
- `.claude/skills/fix-issue/SKILL.md` — lightweight workflow

### Step 7 — Post-merge cleanup

The PR monitor cron (Phase D of `implement-feature`) handles:
1. Closing the issue with a comment linking the merged PR
2. Removing `in-progress`, adding `done`
3. Updating project board to "Done"
4. Deleting the monitor cron

---

## Dispatch by Conductor

When dispatched by the conductor agent (see `conductor.md`), dev agents run in parallel:

- Up to **3 concurrent agents** in isolated worktrees per cycle
- Conductor assigns issues, dev agents handle everything from claim to merge
- Independent tasks dispatched in parallel; dependent tasks queued
- Max 3 cycles per conductor session (9 issues total cap)

---

## Failure Handling

```
Task dispatched
  -> Agent creates PR
    -> CI passes?
      Yes -> Move to Code Review (add `review` label)
      No  -> Agent auto-fixes (max 2 retries via PR monitor)
        -> Still failing?
          Yes -> Label: "blocked", escalate with issue comment
```

### Blocker protocol

1. Search agent memory for prior solutions
2. If found: apply and continue, update memory if refined
3. If not found: commit WIP, push draft PR, post blocker comment on issue, label `blocked`, HALT

### Unrecoverable failures

If the agent cannot proceed after 2 CI fix attempts or encounters an architectural ambiguity:
- Post a detailed comment on the issue explaining what was tried
- Label the issue `blocked`
- Keep the draft PR with WIP code for context
- HALT and wait for human input

---

## Rules Enforced

Dev agents enforce all project rules during the planning gate:

| Rule | Source | Check |
|---|---|---|
| Module boundaries, dependency direction | `CONSTITUTION.md` | No cross-layer imports |
| Bottom-up task ordering | `planning-playbook.md` | Models before logic before views before UI |
| Type hints, `selectinload()`, line length | `code-style.md` | All new code |
| Accessibility-first locators, no `ha-*` selectors | `testing.md` | All E2E tests |
| Claude Code identity, Conventional Commits | `git-workflow.md` | All commits and PRs |
| BDD scenarios | `bdd-conventions.md` | Every feat/test issue |
| SDD for large features | `sdd-conventions.md` | size:L or multi-module |
