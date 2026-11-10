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

Hard stops (post the exact question as an issue comment, add the `needs-human` label to the issue,
finish what does not depend on the answer, open a draft PR, add `needs-human` to the PR too, end
the run): secrets or billing, pushing to the public mirror, deleting data, a PyPI release, breaking
public API (`__init__.py` exports, semver major), changing runtime dependency floors, data-model
migrations.

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh issue edit "$ISSUE" --add-label needs-human
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr edit <pr> --add-label needs-human   # once the draft PR exists
```

The merge rule reads the label on the PR, so the issue label alone is not enough. A PR with
`needs-human` stays a draft: never run `gh pr ready` on it.

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
(`.claude/worktrees/ap-N`), so only switch the branch. If the branch exists from an earlier run,
resume from it. Never reset an existing branch to the base: that drops its commits, and the push in
step 7 would overwrite the branch behind the draft PR.

```bash
git fetch origin "$BASE"
if git ls-remote --exit-code --heads origin "fix/issue-$ISSUE" >/dev/null; then
  # Earlier run, pushed: resume from the remote branch
  git fetch origin "fix/issue-$ISSUE"
  git switch -C "fix/issue-$ISSUE" "origin/fix/issue-$ISSUE"
  git rebase "origin/$BASE"
elif git rev-parse -q --verify "refs/heads/fix/issue-$ISSUE" >/dev/null; then
  # Earlier run, never pushed: resume from the local branch
  git switch "fix/issue-$ISSUE"
  git rebase "origin/$BASE"
else
  git switch -C "fix/issue-$ISSUE" "origin/$BASE"
fi

cat "$STORY_FILE"   # read the story again: the pool worktree may have been on a stale checkout
```

Interactive run: `/wt fix/issue-$ISSUE $BASE` creates an isolated worktree (from
`origin/fix/issue-$ISSUE` when that branch exists, else from `origin/$BASE`), then:

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
Commit first, then rebase (`git rebase` refuses to start with uncommitted changes), then push:

```bash
git add -A
git -c user.name="Claude Code" -c user.email="noreply+claude-code@anthropic.com" \
  commit -m "fix: <description> (#$ISSUE)"
git fetch origin "$BASE"
git rebase "origin/$BASE"
git push --force-with-lease origin HEAD
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create --base "$BASE" \
  --title "fix: <description> (#$ISSUE)" --body-file <body-file>
```

If a draft PR already exists from an earlier run, update it with `gh pr edit --body-file` instead
of creating one. Run `gh pr ready` only when neither the PR nor the issue carries `needs-human`
and this run raised no hard stop; otherwise leave it a draft and end the run.

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
