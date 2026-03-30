---
name: implement-feature
description: "Self-evaluating agentic workflow: plan → validate → implement with blocker handling → learn"
argument-hint: "<issue-number>"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git *), Bash(gh *), Bash(poe *), Bash(uv run *)
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

### B1. Create or resume branch

```bash
# Create fresh branch (if not already on issue branch)
git checkout -b issue-$ARGUMENTS

# If branch already exists (resuming after a prior stop):
git checkout issue-$ARGUMENTS
```

If a draft PR already exists for this branch, resume from the current state — do not restart.

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

```bash
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
