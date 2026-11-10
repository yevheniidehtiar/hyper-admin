---
name: fix-issue
description: Implement a GitHub issue end-to-end following TDD — branch, code, tests, PR
argument-hint: "<issue-number> [base-branch]"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Write, Edit, Agent, Bash(git *), Bash(gh *), Bash(uv run *), Bash(uv sync *), Bash(./scripts/gitpm.sh *)
---

Fix one story in HyperAdmin.

Arguments: `$ARGUMENTS`

- First token: the GitHub issue number (`ISSUE` below).
- Optional second token: the base branch (`BASE` below). Default: the story's epic branch
  `epic/<slug>` when the story belongs to an open epic, otherwise `develop`.

This skill ends when the PR is open. Review, CI repair and the merge belong to the autopilot tick.
It never waits for a human: when something is unclear, use the decision ladder.

## Decision ladder

1. Memory (`MEMORY.md` and matching entries).
2. The story, its SDD, `CONSTITUTION.md`, `.claude/rules/`, existing code and tests.
3. One research subagent with a narrow question.
4. Choose the most reversible option that satisfies `CONSTITUTION.md`, record it under
   `## Assumptions` in the PR body (and in the SDD Decision Log when there is an SDD), continue.

Hard stops (post the exact question as an issue comment, add the `needs-human` label, finish what
does not depend on the answer, open a draft PR, end the run): secrets or billing, pushing to the
public mirror, deleting data, a PyPI release, breaking public API (`__init__.py` exports, semver
major), changing runtime dependency floors, data-model migrations.

## Steps

### 1. Read the story from .meta/
```bash
ISSUE=<first token of the arguments>
BASE=<second token, or resolved as described above>
STORY_FILE=$(grep -rl "issue_number: $ISSUE" .meta/stories/ .meta/epics/*/stories/ 2>/dev/null | head -1)
cat "$STORY_FILE"
STORY_ID=$(grep -m1 '^id:' "$STORY_FILE" | awk '{print $2}')
```
Check `ROADMAP.md` to confirm priority and scope. Do not expand scope.

### 2. Start worktree

Autopilot run (`AUTOPILOT=1`): the job is already in a pool worktree
(`.claude/worktrees/ap-N`), so only switch the branch:

```bash
git fetch origin "$BASE"
git switch -C "fix/issue-$ISSUE" "origin/$BASE"
```

Interactive run: `/wt fix/issue-$ISSUE $BASE` creates an isolated worktree branched from
`origin/$BASE`, then:

```bash
uv sync --all-extras
```

### 3. Explore before changing
- Read relevant source files in `src/hyperadmin/`
- Read existing tests to understand patterns

### 4. TDD loop — for each component
1. Write a failing unit test in `tests/unit/`
2. Implement minimal code to make it pass
3. Refactor — strict type hints, no commented-out code

### 5. E2E test (if UI is involved)
- Write/update Playwright test in `tests/e2e/`
- Use accessibility-first locators (`get_by_role` > `get_by_label` > `get_by_text` >
  `get_by_test_id`); never `ha-*` CSS selectors (see `.claude/rules/testing.md`)
- `uv run poe test:e2e` to verify

### 6. Pre-submission checks
```bash
uv run poe lint
uv run ruff check . && uv run ruff format --check .
uv run poe test:cov-diff
```
All must pass. Fix any failures before continuing. Never commit with `--no-verify`.

### 7. Commit and PR
```bash
git fetch origin "$BASE"
git rebase "origin/$BASE"
git -c user.name="Claude Code" -c user.email="noreply+claude-code@anthropic.com" \
  commit -m "fix: <description> (#$ISSUE)"
git push --force-with-lease origin HEAD
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create --base "$BASE" \
  --title "fix: <description> (#$ISSUE)" --body-file <body-file>
```

The PR body must contain:

```markdown
Story: <STORY_ID>
Issue: #<ISSUE>

## Summary
<what was wrong and how it is fixed>

## Assumptions
<one bullet per decision taken at ladder step 4, or "None.">

## Test plan
- `poe test:cov-diff`: <result>
```

Do not edit the story's `status:` in `.meta`, do not merge, and do not close the issue: the
autopilot tick does that.

**Important**: if `CLAUDE_GH_TOKEN` is not set, do not create the PR under the user's identity.
Leave the branch pushed, print `STOPPED: CLAUDE_GH_TOKEN is not set`, and end the run.
