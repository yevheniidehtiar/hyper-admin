## Git & GitHub Workflow

### Commit authorship

All commits made by Claude must use the Claude Code identity — not the user's identity, not co-authored:

```bash
git commit \
  -c user.name="Claude Code" \
  -c user.email="noreply+claude-code@anthropic.com" \
  -m "type: description (#issue)"
```

Never add `Co-Authored-By` trailers. The user must remain a clean reviewer.

### PR authorship

PRs must be created using `CLAUDE_GH_TOKEN` so they are owned by the bot account, not the user:

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create --fill
```

If `CLAUDE_GH_TOKEN` is not set, stop and tell the user — do not create the PR under their identity.

### Commit message format

Follow Conventional Commits (enforced by commitizen):
```
type(optional-scope): description (#issue-number)
```
Valid types: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`
