## Conflict Avoidance

Goal: parallel PRs merge without conflicts, or very rarely. Merges are rebase-only, so every conflict costs a
rebase. Apply these rules when planning stories and when writing code.

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

- Feature PRs do **not** edit a story's or an epic's `status:`.
- `status:` changes happen in exactly two commits per epic, both written by the autopilot on the epic branch:
  `chore(meta): open epic` (epic `in_progress`, `locked_by: autopilot`, `branch: epic/<slug>`) and
  `chore(meta): close epic` (epic, its stories and the `review(spec)` story `done`, lock fields removed) right
  before the epic PR is marked ready. No per-story status commits, no status-sync PRs to `develop`.
- Mid-epic progress is shown on GitHub, not in `.meta`: labels `ap:in-progress`, `ap:in-review`, `ap:done` on
  the story issue.
- Feature PRs may add new `.meta` files (new stories, epics); that is additive and does not conflict.

### Branch hygiene

- Branch from a fresh base (`git fetch origin <base>` first): `origin/epic/<slug>` for a story of an epic,
  `origin/develop` for hotfix and standalone work.
- Keep PRs small and merge them the same day where possible. Long-lived branches collect conflicts.
- `git pull --rebase origin <base>` before every push.
- Force-push with `--force-with-lease` only.
- No pre-emptive rebases of open PRs (`gh pr update-branch`): `develop` does not require up-to-date branches, the
  rebase merge rebases at merge time anyway, and a push restarts CI and dismisses approvals. After each `develop`
  merge, the autopilot tick finds the open PRs whose `mergeable` turned `CONFLICTING`; only the autopilot rebases
  them (`fix-pr` job). Revisit this if the ruleset turns on strict status checks.
- **Epic-branch exception.** A story PR must be rebased on the tip of `epic/<slug>` before the tick merges it, so
  the tick rebases story PRs as part of merging. The epic branch itself is rebased on `develop` only at creation,
  when `develop` changes a hotspot file the epic also touches, and right before the epic PR is marked ready, and
  only when no story PR is open against it (or the same job rebases every open story branch too). Once the epic
  PR is marked ready the branch is frozen: any push dismisses the owner's approval.

### Stacking

- Do not stack PRs under rebase-only merges: rebasing the base rewrites its commits and the child PR conflicts.
  Story PRs on an epic branch are not a stack: each one branches from the epic tip and merges into it.
- If stacking is unavoidable, run `git rebase --onto origin/develop <old-base-tip>` on the child right after the base
  merges, then force-push with lease.

### Planning

- Every story has a `## Files to Change` section.
- Before dispatching parallel work, build a touched-files matrix (story × file) from those sections. Two stories that
  share a file get a `Blocked by` dependency, or the shared part is pulled into a seam PR.

### Side effects

- Changes to ignore files (`.gitignore`, `.dockerignore`), lint/type/coverage config, or CI scope ship as their own
  PR. They change what every other open PR is checked against.
