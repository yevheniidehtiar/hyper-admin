---
name: fix-issue
description: Implement a GitHub issue end-to-end following TDD — branch, code, tests, PR
argument-hint: "<issue-number>"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(git *), Bash(gh *), Bash(poe *), Bash(uv run *)
---

Fix GitHub issue $ARGUMENTS for HyperAdmin.

## Steps

### 1. Read the issue
```bash
gh issue view $ARGUMENTS
```
Check `ROADMAP.md` to confirm priority and scope. Do not expand scope.

### 2. Start worktree

Run `/start fix/issue-$ARGUMENTS` to create an isolated worktree branched from `develop`,
rebase onto latest, and bootstrap the environment.

### 3. Explore before changing
- Read relevant source files in `src/hyperadmin/`
- Read existing tests to understand patterns

### 4. TDD loop — for each component
1. Write a failing unit test in `tests/unit/`
2. Implement minimal code to make it pass
3. Refactor — strict type hints, no commented-out code

### 5. E2E test (if UI is involved)
- Write/update Playwright test in `tests/e2e/`
- Use `ha-*` CSS selectors (see `.claude/rules/testing.md`)
- `poe test:e2e` to verify

### 6. Pre-submission checks
```bash
poe lint
poe test
```
All must pass. Fix any failures before continuing.

### 7. Commit and PR
```bash
git -c user.name="Claude Code" -c user.email="noreply+claude-code@anthropic.com" \
  commit -m "fix: <description> (#$ARGUMENTS)"
git push origin HEAD
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create --fill
```

**Important**: if `CLAUDE_GH_TOKEN` is not set, stop and ask the user to add it — do not create the PR under their identity.
