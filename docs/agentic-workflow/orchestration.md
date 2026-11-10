# Orchestration: the Autopilot

Delivery runs unattended from the owner's Mac. A launchd agent wakes a small
supervisor script every 15 minutes. The script looks at GitHub and the local
checkout, decides what needs doing, and starts headless Claude Code jobs for the
parts that need a model. This page describes that design.

!!! note "What replaced what"
    The earlier design had a conductor agent, a delivery-manager agent and a
    merge queue driven by `merge-requested` / `merge-granted` labels. All three
    are gone. The supervisor in `ops/autopilot/` does their work with plain
    `gh` and `git` calls, and story PRs merge into an epic branch without a
    human.

## Owner touchpoints

The owner is asked for exactly these things:

| Touchpoint | How often | Where |
|---|---|---|
| Approve the epic PR (`epic/<slug>` → `develop`) | Once per epic | GitHub review; the merge then happens on its own |
| Approve a `fix-develop` PR or a green Dependabot PR | Rare | GitHub review, listed in the digest |
| Answer a hard-stop question | Rare | Issue labelled `needs-human`, listed in the digest |
| Go/no-go on the first janitor list | Once | Digest |
| Release `develop` → `master` and PyPI | Per release | Manual, unchanged |

Everything else (planning gate, implementation, review, merging story PRs, CI
repair, rebases, cleanup, status sync) runs without a human.

## Branch model: one branch per epic

```
develop  ──────────────────────────────●────────────────●──▶   owner approves 1 PR per epic
           \                          /                /
epic/<slug> ●──st-01──st-02──st-03───┘   epic/<other>─┘       bot rebase-merges story PRs, no human
             ▲         ▲
        feat/st-01  feat/st-02 ...                           worker worktrees, one per story
```

### The branch is the lock

An epic is claimed by creating its branch through the GitHub API:

```bash
gh api -X POST "repos/{owner}/{repo}/git/refs" \
  -f ref="refs/heads/epic/<slug>" -f sha="<develop sha>"
```

A second attempt returns `422 Reference already exists`, every time. A plain
`git push` of an existing ref exits 0, so it cannot serve as a lock.

The first commit on the branch is `chore(meta): open epic`. It sets `epic.md` to
`status: in_progress`, `locked_by: autopilot`, `branch: epic/<slug>`.

### Draft epic PR from day one

Right after creating the branch the tick opens `epic/<slug>` → `develop` as a
draft PR. Each story merge pushes the epic branch, so CI runs on the integrated
state and the owner can watch the diff grow. The PR is marked ready only when
all stories and the `review(spec)` story are done.

### Story PRs

- Base branch: `epic/<slug>`.
- Body carries a `Story: <story-id>` line and, when the agent had to choose
  something, an `## Assumptions` section.
- The tick merges with `gh pr merge --rebase --delete-branch` when **all** checks
  are green, the PR has `ai-approved`, it has no `needs-human`, and it is rebased
  on the epic tip.
- `--auto` is not used on `epic/**`: there are no pending rules there for it to
  wait on. The tick does the gating.

### `.meta` on the epic branch: two commits per epic

| Commit | When | Content |
|---|---|---|
| `chore(meta): open epic` | Branch creation | Epic `in_progress`, lock fields set |
| `chore(meta): close epic` | Right before the epic PR is marked ready | Epic `done`, stories `done`, spec story `done`, lock fields removed |

There are no per-story status commits and no daily sync PR to `develop`. Both
would cost owner clicks and would conflict when the epic branch is rebased.

Progress during an epic is visible through signals the tick writes straight to
GitHub: one of `ap:in-progress`, `ap:in-review`, `ap:done` on the story issue,
plus one comment with the PR link. When the epic merges, GitPM sync overwrites
the status-mapped labels, which is the correct final state.

### Integrating the epic

The tick starts `integrate-epic` when all stories are done. The job makes sure
these hold before it marks the PR ready:

1. No open PR has `epic/<slug>` as its base. (Otherwise deleting the branch on
   merge would retarget those PRs to `develop`.)
2. The branch is exactly rebased on `develop`. GitHub's rebase-merge fails with
   405 if the replay is not clean, even where a 3-way merge would succeed.
3. All AI review threads are resolved (`develop` requires thread resolution).

The job writes the close-epic commit, marks the PR ready, requests the owner's
review, and enables `gh pr merge --auto --rebase`. From that point the branch is
**frozen**: any push would dismiss the approval. The owner's approval merges the
PR with no further push. Story commits land linearly on `develop`, and GitPM
sync updates all issues in one run.

### Rebasing the epic branch

Only at three moments: at creation, when `develop` changes a hotspot file the
epic also touches, and before the PR is marked ready. And only when no story PR
is open against the branch, or when the same job rebases every open story
branch too. Always `--force-with-lease`.

### Milestones and releases

Milestones need no branch. When the last epic of a milestone merges, the digest
says so. The release (`develop` → `master`, `cz bump`, PyPI) stays manual.

### Repository settings behind this

- Ruleset `epic-branches` on `refs/heads/epic/**` with one rule,
  `required_linear_history`. Squash is disabled repo-wide, so rebase is the only
  merge button left. There are deliberately no required status checks (they
  would reject the bot's rebase force-push) and no pull-request rule (it would
  forbid direct pushes of the open/close commits).
- `.github/CODEOWNERS` names the owner, so the code-owner review on `develop` is
  explicit.
- `ci.yml`, `test.yml` and `gitpm-sync.yml` list `epic/**` under
  `pull_request.branches`, so story PRs get CI. A push to an epic branch runs
  Lint and the E2E shards but not the full Python/resolution matrix.

## The tick

The launchd agent `com.hyperadmin.autopilot` runs
`ops/autopilot/autopilot.sh tick` every 15 minutes under `caffeinate -i`,
through a login shell so `CLAUDE_GH_TOKEN`, the Homebrew `PATH` and the Claude
OAuth session are available. It uses the owner's Max subscription. There is no
API key and no cloud runner.

A tick is cheap first and expensive only when needed.

### 1. Lock and state

One instance at a time, enforced with a `mkdir` lock (macOS has no `flock`).
State lives in `~/.hyperadmin-autopilot/state.json`: cooldown, running jobs,
per-PR retry counters, janitor approval.

### 2. Deterministic checks (no tokens)

Plain `gh` and `git`:

- Is `develop` red? (last push runs of CI, Test, Deploy Docs, GitPM Sync.) Has a
  nightly workflow been red twice? (Load Test, Demo, Scheduled Health.)
- Open bot PRs: failing or cancelled checks, `CONFLICTING`,
  `ai-changes-requested`, or all green plus `ai-approved` (merge).
- Epics on `epic/**`: `review(spec)` still todo (architect job), all stories
  done (integrate), draft PR missing (open it).
- Free worker slots and ready stories. A story is ready when it is `todo`, not
  labelled `deferred`, its dependencies are `done`, and its `## Files to Change`
  list does not overlap a running story or a hotspot owned by one.
- Green Dependabot PRs (go to the digest).
- Janitor candidates.

### 3. Jobs

Each action becomes one headless `claude -p` job in a fixed worktree pool,
`.claude/worktrees/ap-1` to `ap-3`. Worktrees are reused (`git worktree add -B`)
and `uv sync` runs only when `uv.lock` changed. Every job has a wall-clock kill.

| Job (prompt file) | Does | Model |
|---|---|---|
| `implement <story-id>` | `implement-feature` skill with base `epic/<slug>`; opens the PR against the epic branch | Opus |
| `review <pr>` | Code reviewer with a JSON verdict; sets `ai-approved` or `ai-changes-requested` and posts a review comment | Sonnet |
| `fix-pr <pr>` | Reruns a cancelled shard once; otherwise reads the failed log, rebases, fixes, pushes with lease. Max 3 rounds | Opus |
| `fix-develop <run-id>` | Branch `fix/develop-<run-id>` from `develop`, fix or revert with evidence, PR to `develop`, digest entry | Opus |
| `approve-sdd <epic>` | Software-architect agent runs the spec gate | Opus |
| `integrate-epic <slug>` | Rebase, close-epic commit, resolve threads, mark ready, `--auto --rebase`, request review | Sonnet |
| `digest` | Daily owner digest: Slack webhook if set, else a comment on the standing autopilot issue | Haiku |

Prompts live in `ops/autopilot/prompts/` and are read from the main checkout, so
a job never runs a prompt from the branch it is working on.

Jobs run with `--permission-mode acceptEdits` and an explicit tool allowlist
(`git`, `gh pr|api|run|issue`, `uv run`, `scripts/gitpm.sh`, file tools).
`gh release`, `gh repo` and pushes to the public mirror are denied. Nothing uses
`--dangerously-skip-permissions`. Denied calls show up in the job result and are
reported in the digest. The bot cannot approve its own PR, which is why the
review verdict is a label and a comment.

Worker slots: `DEV_AGENT_LIMIT=3`, dropping to 1 when free memory is below 4 GB.

### 4. Usage limits

If a job result reports an error, HTTP 429, or a usage-limit message, the tick
sets `cooldown_until` in the state file (the reset time from the message when
present, otherwise the next 5-hour boundary). No model jobs start during
cooldown. The deterministic checks keep running, so merges of already-approved
PRs are not held up.

### 5. Operating it

| Command | Effect |
|---|---|
| `poe autopilot:install` | Render the plist from the template, load it with `launchctl bootstrap` |
| `poe autopilot:uninstall` | Unload and remove it |
| `poe autopilot:status` | Show whether the launchd agent is loaded |
| `poe autopilot:logs` | Show the tick and job logs |
| `poe autopilot:tick` | Run one tick now |
| `AUTOPILOT_DRY_RUN=1 ops/autopilot/autopilot.sh tick` | Print the planned actions, take none |

Jobs run with `AUTOPILOT=1` in the environment. Interactive-only hooks (such as
the example redeploy on task completion) skip themselves when it is set.

## Self-unblocking

Agents no longer post a questionnaire and stop. When something is unclear, in
the planning gate, during implementation, or in the spec gate, they walk this
ladder:

1. Project memory (`MEMORY.md`).
2. The story, the SDD, `CONSTITUTION.md`, the existing code.
3. A research subagent.
4. Choose the most reversible option that satisfies the constitution, write it
   under `## Assumptions` in the PR body and in the SDD Decision Log, and
   continue.

### Hard stops

For these the agent labels the issue `needs-human`, posts the exact question,
and moves on to other work. The tick is never blocked.

- Secrets or billing
- Pushing to the public mirror
- Deleting data
- A PyPI release
- Breaking public API (`__init__` exports, semver major)
- Changing runtime dependency floors
- Data-model migrations

The tool allowlist enforces the first three mechanically.

### Retry budgets

Tracked per PR in `state.json`:

| Budget | Limit | Then |
|---|---|---|
| CI rerun for a cancelled or timed-out run | 1 | Treated as a real failure |
| Fix rounds per PR | 3 | `needs-human` |
| Review rounds per PR | 2 | `needs-human` |

## Spec gate

A Draft SDD is approved by the software-architect agent
(`.claude/agents/software-architect.md`), not by a human. The `approve-sdd` job:

1. Runs the reviewer checklist from `.claude/rules/sdd-conventions.md`.
2. Resolves Open Questions with the ladder above and fills the Decision Log.
3. Sets `Status | Approved (architect)` and commits on the epic branch.
4. Comments on the spec issue. The `review(spec)` story is marked done in the
   close-epic commit; until then the tick tracks it in `state.json`.

It escalates to the owner only for breaking public API, new runtime
dependencies, or data-model migrations. The owner can still veto on the epic PR.

## Self-repair

| Signal | Response |
|---|---|
| `develop` push run red | Rerun once if cancelled or timed out. Otherwise `fix-develop` opens a PR with the logs and a one-line rationale. The owner approves it. |
| Nightly workflow red twice | Same, or an issue when the cause is external (hosting, runner) |
| Story PR checks failing | `fix-pr`, up to 3 rounds |
| PR turned `CONFLICTING` after a merge | Rebased by the tick. All PRs are bot-owned, so only the autopilot rebases. |
| Dependabot PR green | Listed in the digest for one-click approval |

## Janitor

Runs as part of the tick:

- Removes worktrees and local branches whose PR is merged. Safety checks: clean
  tree, and `git cherry` shows the commits are in `develop`.
- Deletes merged remote `worktree-*` and `ap-*` branches.
- Drops job files older than 7 days.

The first run is a dry run. Its list goes into the digest, the owner says go
once, the approval is recorded in `state.json`, and from then on it is routine.

## Labels

Created by `scripts/setup-github.sh`.

### Autopilot labels

| Label | Set by | On | Meaning |
|---|---|---|---|
| `ai-approved` | `review` job | PR | Reviewer verdict: approve |
| `ai-changes-requested` | `review` job | PR | Reviewer verdict: changes needed; `fix-pr` picks it up |
| `needs-human` | Any job | Issue or PR | Hard stop or exhausted retry budget; the question is in a comment |
| `ap:in-progress` | Tick | Story issue | A worker is implementing the story |
| `ap:in-review` | Tick | Story issue | Story PR is open |
| `ap:done` | Tick | Story issue | Story PR merged into the epic branch |
| `superseded` | Planning | Story issue | Replaced by other work; will not be implemented |

### Planning and triage labels

| Label | Purpose |
|---|---|
| `idea` | Raw idea, needs research |
| `researched` | Deep Research complete |
| `planned` | Roadmap Planning complete, stories created |
| `approved` | Owner approved the plan |
| `in-progress`, `review`, `qa-passed`, `released` | Lifecycle labels from the planning pipeline |
| `agent-task`, `ready` | Story is meant for an agent and is unblocked |
| `size:S`, `size:M`, `size:L` | Effort estimate |
| `agent:ai` | Assigned to Claude Code |
| `epic` | Parent issue with sub-issues |
| `community` | From an external contributor |
| `scheduled:auto`, `scheduled:review-needed` | Created by the scheduled agent |
| `suspicious` | Flagged by the [OSS Triage Auditor](oss-triage-auditor.md) |

The merge-queue labels (`merge-requested`, `merge-granted`, `merge-deferred`)
are no longer used.

## Project management: GitPM (`.meta/`)

Project state is plain YAML/Markdown in `.meta/`:

```
.meta/
├── roadmap/
│   ├── roadmap.yaml           # Ordered list of milestone IDs
│   └── milestones/            # One file per milestone
├── epics/
│   └── <epic-slug>/
│       ├── epic.md            # Epic frontmatter + body
│       └── stories/           # Stories nested under this epic
├── stories/                   # Standalone stories
└── sync/                      # GitHub sync config + state
```

Agents read `.meta/` directly. Writes go through commits: planning PRs create
epics and stories, and the autopilot writes the open-epic and close-epic
commits. Feature PRs do not edit `.meta` status.

Syncing to GitHub happens only in CI. When a change reaches `develop`, the GitPM
Sync workflow (`.github/workflows/gitpm-sync.yml`) pushes it to GitHub issues
and milestones, and PRs get a dry-run preview. Nobody runs a GitPM push locally.
See `.claude/project-config.md` for the full reference.

## Limits and safety rails

| Rail | Value |
|---|---|
| Concurrent workers | 3 (`DEV_AGENT_LIMIT`), 1 under memory pressure |
| Tick interval | 15 minutes, single instance |
| Fix rounds per PR | 3, then `needs-human` |
| Review rounds per PR | 2, then `needs-human` |
| Human approval | Required for anything reaching `develop` |
| Permissions | Deny by default, explicit allowlist, no skip-permissions |
| Public mirror, releases, repo settings | Not reachable from a job |
| Rollback | `fix-develop` reverts with evidence if `develop` breaks |
