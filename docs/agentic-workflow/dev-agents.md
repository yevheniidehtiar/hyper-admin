# Dev Agent

| Property | Value |
|---|---|
| **Runtime** | Claude Code, headless (`implement` job, Opus) or interactive |
| **Trigger** | The autopilot tick starts `implement <story-id>`; or a user runs `/implement-feature <issue>` or `/fix-issue <issue>` |
| **Purpose** | Implement one story test-first and open a PR against the epic branch |
| **Est. Cost** | 20k–100k tokens per implementation task |

---

## Core Behavior

A dev agent takes one story, implements it with TDD, and opens a pull request.
It does not pick its own work, does not merge, and does not watch CI after the
PR is open. The [autopilot tick](orchestration.md) owns all three.

When something is unclear the agent decides, records the decision, and
continues. It stops only for the hard stops listed below.

### Invocation modes

| Mode | What happens |
|---|---|
| `implement <story-id>` (autopilot job) | Runs the `implement-feature` skill with base `epic/<slug>` in a pool worktree |
| `/implement-feature 375` | Same skill, started by hand for issue #375 |
| `/fix-issue 401` | Lightweight TDD fix for issue #401 |

Both skills take the base branch as an argument. For a story inside an epic it
is `epic/<slug>`. For standalone work (a hotfix, a docs change) it is `develop`.

---

## How a story is chosen

The tick chooses, not the agent. A story is ready when:

1. Its status in `.meta/` is `todo`.
2. It is not labelled `deferred`.
3. Every story it depends on is `done`.
4. Its `## Files to Change` list does not overlap a story that is already
   running, and it does not touch a hotspot file owned by a running story.

Ready stories are dispatched while worker slots are free (`DEV_AGENT_LIMIT=3`,
or 1 when memory is low). This is why every story needs an accurate
`## Files to Change` section: it is the input to the overlap check.

---

## Status and labels

The dev agent does not edit `.meta` status and does not manage lifecycle
labels. That keeps story PRs free of `.meta` conflicts.

| Event | Who | Signal |
|---|---|---|
| Story dispatched | Tick | `ap:in-progress` on the story issue |
| PR opened | Tick | `ap:in-review` on the story issue, one comment with the PR link |
| Review verdict | `review` job | `ai-approved` or `ai-changes-requested` on the PR |
| PR merged into the epic branch | Tick | `ap:done` on the story issue |
| Epic closed | `integrate-epic` job | `chore(meta): close epic` sets stories to `done` |
| Epic merged to `develop` | GitPM Sync (CI) | Issues and status labels updated |

---

## Execution Flow

```
1. Worktree on feat/<story-id>, based on epic/<slug>
2. Phase A: Planning gate         read story + SDD, bottom-up plan, self-evaluate
3. Phase B: TDD implementation    failing test first, then the minimal code
4. Phase C: Submission            lint, tests, commit, PR against epic/<slug>
```

There is no monitoring phase. Once the PR is open the agent's job is finished.
Failing checks and review findings are handled by the `fix-pr` job, which
resumes the same session where possible.

### Step 1: worktree

Autopilot jobs run in the fixed pool `.claude/worktrees/ap-1` to `ap-3`. The
supervisor checks out the story branch there and runs `uv sync --all-extras`
only when `uv.lock` changed.

By hand, start with `/wt`, which creates an isolated worktree and takes an
optional base branch.

### Phase A: planning gate

The agent reads the story, the SDD if there is one, `CONSTITUTION.md` and the
rules, writes a bottom-up plan, and checks it against the planning checklist.

A failed check is not a stop. The agent resolves it with the decision ladder:

1. Project memory (`MEMORY.md`).
2. The story, the SDD, `CONSTITUTION.md`, the existing code.
3. A research subagent.
4. Choose the most reversible option that satisfies the constitution, record it
   under `## Assumptions`, and continue.

### Phase B: implementation

Test first, per sub-task, bottom-up (models, then logic, then views, then UI).
A blocker goes through the same ladder as the planning gate.

### Phase C: submission

```bash
poe lint
poe test:unit
uv run ruff check . && uv run ruff format --check .
poe test:cov-diff     # 100% of changed lines
```

Then commit as Claude Code (Conventional Commits) and open the PR with the bot
token. The PR body contains:

- `Story: <story-id>`: the tick uses this line to map the PR to its story.
- A summary and test notes. Manual test scenarios for user-facing changes.
- `## Assumptions`: every decision made at step 4 of the ladder, one line each.
  Omitted when there were none.

Skill definitions:

- `.claude/skills/implement-feature/SKILL.md`: full workflow
- `.claude/skills/fix-issue/SKILL.md`: lightweight workflow

The autopilot `implement` job always runs `implement-feature`, whatever the
story size. `fix-issue` is a by-hand path for a small, self-contained fix. An
SDD is required for `size:L` or multi-module work; the architect agent approves
it.

---

## Hard stops

For these the agent does not choose. It labels the issue `needs-human`, posts
the exact question, and ends the job so the tick can use the slot for other
work:

- Secrets or billing
- Pushing to the public mirror
- Deleting data
- A PyPI release
- Breaking public API (`__init__` exports, semver major)
- Changing runtime dependency floors
- Data-model migrations

The job's tool allowlist blocks the first three regardless of what the agent
decides.

---

## Failure Handling

```
Story PR opened
  -> checks green?
       yes -> review job -> ai-approved -> tick rebase-merges into epic/<slug>
                         -> ai-changes-requested -> fix-pr -> review again (max 2 review rounds)
       no  -> cancelled or timed out? -> rerun once
              otherwise -> fix-pr: read the failed log, rebase, fix, push with lease (max 3 rounds)
  -> budget exhausted -> needs-human with a summary of what was tried
```

A PR that turns `CONFLICTING` after another story merges is rebased by the
tick. Dev agents do not rebase each other's branches.

---

## Rules Enforced

Dev agents enforce all project rules during the planning gate:

| Rule | Source | Check |
|---|---|---|
| Module boundaries, dependency direction | `CONSTITUTION.md` | No cross-layer imports |
| Bottom-up task ordering | `planning-playbook.md` | Models before logic before views before UI |
| Type hints, `selectinload()`, line length | `code-style.md` | All new code |
| Accessibility-first locators, no `ha-*` selectors | `testing.md` | All E2E tests |
| Claude Code identity, Conventional Commits, base branch per PR type | `git-workflow.md` | All commits and PRs |
| Files touched match `## Files to Change`; no `.meta` status edits | `conflict-avoidance.md` | Every story PR |
| BDD scenarios | `bdd-conventions.md` | Every feat/test issue |
| SDD for large features | `sdd-conventions.md` | size:L or multi-module |
