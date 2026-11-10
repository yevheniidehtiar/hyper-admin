---
type: epic
id: ep-autopilot-01
title: "epic(autopilot): hands-off delivery with one owner approval per epic"
status: in_progress
priority: high
owner: null
labels:
  - planned
  - area:ci
  - dx
  - size:L
milestone_ref: null
created_at: 2026-11-10T00:00:00Z
updated_at: 2026-11-10T00:00:00Z
---

## Overview

The repo describes an autonomous agent pipeline, but almost none of it runs without the owner: every PR to `develop`
waits for a manual approval, all `claude-code-action` jobs are disabled, the documented epic lock (a squash-merged
`.meta` PR) cannot work under rebase-only merges, agents stop on a questionnaire instead of unblocking themselves, and
CI repair dies with the interactive session.

This epic replaces that with a local autopilot. Owner decisions of 2026-11-09:

| Decision | Choice |
|---|---|
| Runtime for unattended agents | Local Mac only (launchd label `com.hyperadmin.autopilot`), subscription login, no API key |
| Human approval | Once per epic (the `epic/<slug>` to `develop` PR). Story PRs merge without a human |
| SDD gate | The software-architect agent approves. The owner decides only on breaking public API, new runtime dependencies and data-model migrations |
| Release (`develop` to `master`, PyPI) | Stays the owner's call |

Target design in short:

- **One branch per epic.** `epic/<slug>` is created through the GitHub refs API, which fails with 422 when the ref
  exists, so branch creation is the epic lock. Story PRs target the epic branch and carry a `Story: <story-id>` line.
  A draft `epic/<slug>` to `develop` PR is open from day one and is marked ready when all stories are done.
- **`.meta` on the epic branch, two commits per epic**: `chore(meta): open epic` and `chore(meta): close epic`. No
  per-story status commits. Mid-epic progress is shown with the labels `ap:in-progress`, `ap:in-review`, `ap:done` on
  the story issue.
- **A tick every 15 minutes** (`ops/autopilot/autopilot.sh tick`) does deterministic `gh`/`git` checks first and
  spawns a headless job only when one is needed: `implement`, `review`, `fix-pr`, `fix-develop`, `approve-sdd`,
  `integrate-epic`, `digest`. Jobs run in the pool worktrees `.claude/worktrees/ap-1..3` with `AUTOPILOT=1`. State
  lives in `~/.hyperadmin-autopilot/state.json`. `DEV_AGENT_LIMIT` caps the workers; `AUTOPILOT_DRY_RUN=1` prints the
  planned actions and takes none.
- **Review verdict by label**: `ai-approved` or `ai-changes-requested` (the bot cannot approve its own PR).
- **Self-unblocking**: memory, then story/SDD/CONSTITUTION/code, then a research subagent, then the most reversible
  option, written under `## Assumptions` in the PR body. Hard stops post `needs-human` and never block the tick.
- **Self-repair**: red `develop` runs, failing or cancelled PR checks and `CONFLICTING` PRs are handled by the tick.

**Design record:** the owner-approved autopilot plan of 2026-11-09, summarised above and in the stories. There is no
`docs/specs/` SDD and no `review(spec)` story: the epic changes workflow tooling only, with no change under
`src/hyperadmin/` and no change to the public API.

## Stories

| ID | Story | Size | Branch | Blocked by |
|---|---|---|---|---|
| st-autopilot-01 | [ci(autopilot): epic branch lane](stories/ciautopilot-epic-branch-lane.md) | S | `ci/autopilot-epic-lane` | none |
| st-autopilot-02 | [feat(autopilot): local supervisor](stories/featautopilot-local-supervisor.md) | L | `feat/autopilot-supervisor` | st-autopilot-01 |
| st-autopilot-03 | [refactor(agents): epic-branch flow and self-unblocking](stories/refactoragents-epic-branch-flow-and-self-unblocking.md) | L | `refactor/agents-epic-branch-flow` | st-autopilot-01 |
| st-autopilot-04 | [docs(agentic-workflow): autopilot](stories/docsagentic-workflow-autopilot.md) | M | `docs/agentic-workflow-autopilot` | st-autopilot-01, st-autopilot-02 |

This epic is delivered as five non-stacked PRs to `develop`. The fifth is the `chore(meta)` PR that adds this epic; it
has no story of its own. The epic bootstraps the autopilot, so it does not run on an `epic/autopilot` branch itself.

The epic and its four stories are `status: in_progress` from the start, because all four branches already exist. That
keeps the project manager, the swarm and the tick from picking them up as ready `todo` work. The usual merge-sync
`chore(meta)` PR sets them to `done`.

st-autopilot-01 merges first: until `epic/**` is in `pull_request.branches`, story PRs against an epic branch get no
CI at all. It is also the only story that touches `.github/**`, and it is pushed under the owner's git credential
because the bot token lacks the `workflow` scope.

### Touched-files matrix

| File | 01 | 02 | 03 | 04 |
|---|---|---|---|---|
| `.github/workflows/{ci,test,gitpm-sync,loadtest}.yml`, `code-review.yml` (delete) | x | | | |
| `.github/CODEOWNERS` (new), `.github/PULL_REQUEST_TEMPLATE.md` | x | | | |
| `scripts/secure-repo.sh` | x | | | |
| `ops/autopilot/**` (new), `ops/conductor/**` (delete) | | x | | |
| `pyproject.toml` | | x | | |
| `justfile` | | x | | x |
| `tests/unit/test_autopilot_*.py` (new) | | x | | |
| `.claude/settings.json` | | x | | |
| `.claude/project-config.md` | | | x | |
| `.claude/skills/{implement-feature,fix-issue}/SKILL.md` | | | x | |
| `.claude/agents/**`, `.claude/commands/**`, `.claude/rules/**` | | | x | |
| `CLAUDE.md`, `AGENTS.md` | | | x | |
| `docs/agentic-workflow/**` | | | | x |
| `CONTRIBUTING.md`, `docs/contributing.md` | | | | x |
| `scripts/setup-github.sh` | | | | x |

`justfile` is the only shared file. 02 appends the `autopilot` aliases; 04 changes one word in the `release` recipe
(`main` to `master`). The hunks are apart, and 04 is blocked by 02 so that it rebases last. Hotspots: `.github/**`
(owner 01) and `pyproject.toml` (owner 02, poe tasks only, no dependency or `uv.lock` change).

Overlap with `epic-conflict-avoidance`: st-conflict-01 and st-conflict-02 (both `todo`) also edit
`docs/contributing.md`. st-autopilot-04 creates `## Merge hygiene` there with `### Story status` and
`### Conflicting PRs`; st-conflict-01/02 then add only `### Dependencies` and `### Releases` under it.

## Supersedes

- `st-conflict-03` (ci(meta): set .meta story status from PR merge events): an Action cannot commit to `develop`
  under the PR-only ruleset. Status now changes in the open-epic and close-epic commits on the epic branch.
- `st-conflict-04` (ci: detect and label conflicting PRs after develop merges): the tick finds `CONFLICTING` PRs and
  rebases them itself.

Both are `status: cancelled` with the `superseded` label (GitPM has no `superseded` status).

Follow-up, outside this epic's files: `.meta/epics/epic-conflict-avoidance/epic.md` still lists both stories as
ordinary rows, plans `meta-status.yml` and `conflict-check.yml` in its matrix and promises merge-event status sync,
and st-conflict-01 still plans the `## Merge hygiene` heading with stubs for 03/04. Both need a small `chore(meta)`
edit once the owner agrees.

## Out of scope

- Releases (`develop` to `master`, `cz bump`, PyPI): manual, unchanged.
- GitHub-hosted agent runs and API-key based workflows.
- Applying the `epic-branches` ruleset. st-autopilot-01 stores the payload; the owner applies it.
- The janitor go-ahead and `poe autopilot:install` on the owner's machine: local steps after the PRs merge.
