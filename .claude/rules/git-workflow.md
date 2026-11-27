## Git & GitHub Workflow

### Commit authorship

All agent commits use the bot account identity (author and committer), not the owner's identity, not co-authored:

```bash
git -c user.name="dodjer88" \
    -c user.email="11336795+dodjer88@users.noreply.github.com" \
    commit -m "type: description (#issue)"
```

The `-c` flags belong to the `git` command, not to `commit` — combining them with `commit -m` causes a fatal error.

Never add `Co-Authored-By` trailers. No AI attribution anywhere: no "Generated with ..." footer and no tool or model named as author in commit messages, PR titles, PR bodies or review comments. The user must remain a clean reviewer.

### PR authorship

PRs must be created using `CLAUDE_GH_TOKEN` so they are owned by the bot account, not the user:

```bash
GH_TOKEN="$CLAUDE_GH_TOKEN" gh pr create --base <base> --fill
```

If `CLAUDE_GH_TOKEN` is not set, stop and tell the user — do not create the PR under their identity.

### Base branch per PR type

| PR type | Branch from | PR base | Merged by |
|---------|-------------|---------|-----------|
| Feature, fix, docs, planning (`.meta` only), dependencies | `origin/develop` | `develop` | owner approves |
| Release | `develop` | `master` | owner only |

- Merges are rebase-only. Squash and merge commits are not available.
- Dependency, ignore-file, lint/coverage config and CI changes ship as their own small PR.
- Never hand-merge `uv.lock`: take `origin/develop`'s lock, rebase, then run `uv lock` and commit the result.
- Never open a PR against `master` and never push to the public mirror from an agent session.

### Commit message format

Follow Conventional Commits (enforced by commitizen):
```
type(optional-scope): description (#issue-number)
```
Valid types: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`
