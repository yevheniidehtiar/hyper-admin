## Conflict Avoidance

Goal: parallel PRs merge without conflicts, or very rarely. Merges are rebase-only, so every conflict costs a
manual rebase. Apply these rules when planning stories and when writing code.

### Additive by default

- A feature adds **new files**. It registers through an extension point (plugin registry, router include,
  CSS/template glob discovery, lazy `__all__`) instead of appending to a shared list.
- If no seam exists, ship a small **seam PR first** (adds the extension point, no feature), merge it, then open the
  feature PRs in parallel on top of it.

### Hotspot files

One owner per wave. Keep diffs minimal, touch only the lines you need, and keep your change in its own hunk (append
at a stable anchor, never reflow or re-sort neighbouring lines).

- `pyproject.toml`, `uv.lock`
- `.gitignore`, `.github/**`
- `src/hyperadmin/core/app.py`
- `__init__.py` re-exports
- `src/hyperadmin/static/css/hyperadmin.css`, `_tokens.css`
- `src/hyperadmin/templates/_base.html`, `_sidebar.html`, `_navbar.html`
- `tests/e2e/conftest.py`
- visual snapshots (`tests/e2e/snapshots/`)

If your story needs a hotspot that another in-flight story owns, add a `Blocked by` on that story or ask the owner.

### Dependencies lane

- Dependency, extra and version changes go in their **own small PR** — never bundled into a feature PR.
- Never hand-merge `uv.lock`. On conflict: take `origin/develop`'s lock, rebase, then run `uv lock` and commit the
  result.

### `.meta` status

- Feature PRs do **not** edit a story's `status:`. Until the merge-event automation lands, only the merge-sync PR does.
- Feature PRs may add new `.meta` files (new stories, epics); that is additive and does not conflict.

### Branch hygiene

- Branch from a fresh `origin/develop` (`git fetch origin develop` first).
- Keep PRs small and merge them the same day where possible. Long-lived branches collect conflicts.
- `git pull --rebase origin develop` before every push. The head session auto-rebases open PRs server-side after each
  merge; pull before you push again.
- Force-push with `--force-with-lease` only.

### Stacking

- Do not stack PRs under rebase-only merges: rebasing the base rewrites its commits and the child PR conflicts.
- If stacking is unavoidable, run `git rebase --onto origin/develop <old-base-tip>` on the child right after the base
  merges, then force-push with lease.

### Planning

- Every story has a `## Files to Change` section.
- Before dispatching parallel work, build a touched-files matrix (story × file) from those sections. Two stories that
  share a file get a `Blocked by` dependency, or the shared part is pulled into a seam PR.

### Side effects

- Changes to ignore files (`.gitignore`, `.dockerignore`), lint/type/coverage config, or CI scope ship as their own
  PR. They change what every other open PR is checked against.
