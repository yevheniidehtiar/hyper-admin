# Autopilot

The local supervisor that delivers epics without a person in the loop. A launchd agent
(`com.hyperadmin.autopilot`) runs one tick every 15 minutes on the owner's Mac, with the Max
subscription and no API key. The owner approves one pull request per epic, the occasional fix
to `develop`, and answers what the daily digest asks.

It replaces `ops/conductor/` (a Docker loop that needed an API key and ran in plan mode).

## What a tick does

A tick is cheap first and spends tokens only when there is work.

1. **Lock and state.** One tick at a time (a `mkdir` lock; macOS has no `flock`). State lives in
   `~/.hyperadmin-autopilot/state.json`: cooldown, running jobs, retry counters, janitor approval,
   digest notes.
2. **Look, with `gh` and `git` only.** Open pull requests and their checks, the last runs of the
   push and nightly workflows, `epic/**` branches, a snapshot of `.meta` taken with `git archive`
   (nothing is checked out), free memory.
3. **Janitor.** Once a day, list worktrees and branches whose pull request is merged (see below).
4. **Plan.** `lib/plan.py` turns the observations into actions. It has no side effects, so a dry
   run prints exactly what a live tick would do.
5. **Act.** Deterministic actions run directly (rerun a cancelled check, rebase an approved pull
   request on its epic branch, rebase-merge it, open an epic). Everything that needs judgement
   is a headless `claude -p` job in a worktree of the fixed pool `.claude/worktrees/ap-1..3`.

```bash
AUTOPILOT_DRY_RUN=1 ops/autopilot/autopilot.sh tick   # or: poe autopilot:dry-run
```

A dry run reads GitHub and git, prints the plan and changes nothing: no job, no merge, no label,
no branch, no fetch, no state file. Its only writes go to a temporary directory it removes.

## Jobs

| Job | Does | Model | Budget |
|---|---|---|---|
| `implement <story>` | implements one story on a branch cut from `epic/<slug>`, opens the PR to the epic branch | opus | 2 per story |
| `review <pr>` | reviews a green story PR, comments, returns a verdict; the tick sets `ai-approved` or `ai-changes-requested` | sonnet | 2 per PR |
| `fix-pr <pr>` | repairs failed checks, conflicts or review findings, one round per run | opus | 3 per PR |
| `fix-develop <run>` | fixes or reverts what broke `develop` on `fix/develop-<run>`, PR to `develop` for the owner | opus | 1 per workflow, until that workflow is green again |
| `approve-sdd <epic>` | architect review of the epic's SDD, approves or escalates | opus | 2 per epic |
| `integrate-epic <slug>` | rebases the epic on `develop`, close-epic commit, marks the PR ready with auto-merge | sonnet | 2 per epic |
| `digest` | writes the daily digest from the queued notes | haiku | once a day |

A cancelled or timed-out CI run is rerun once before anything else. When a budget is spent the
item gets `needs-human` and one comment, and the tick moves on. After fixing it by hand, run
`ops/autopilot/autopilot.sh reset pr <number>` and remove the label.

Each job runs as:

```bash
AUTOPILOT=1 claude -p "<prompts/_common.md + prompts/<job>.md + arguments>" \
  --permission-mode acceptEdits --permission-prompts none \
  --allowedTools 'Bash(git:*)' 'Bash(gh pr:*)' 'Bash(gh api:*)' 'Bash(gh run:*)' 'Bash(gh issue:*)' \
                 'Bash(uv run:*)' 'Bash(./scripts/gitpm.sh:*)' Read Edit Write Glob Grep Agent \
  --disallowedTools 'Bash(gh release:*)' 'Bash(gh repo:*)' 'Bash(git push:*<public mirror>*)' \
  --output-format json --max-turns <n> --model <model> --session-id <uuid>
```

- No `--dangerously-skip-permissions`. Anything outside the allowlist is denied without a prompt
  and shows up in the result's `permission_denials`, which the digest reports.
- `review` and `digest` only read, so they get a narrower set: `--tools Read Glob Grep Bash`
  (no edit tools exist for them), `--permission-mode manual`, and an allowlist of read
  commands (`gh pr view|diff|list|checks`, `gh issue view|list`, `gh run view`,
  `git log|diff|show|status`); `review` may also run `gh pr comment`. The digest runs in
  `~/.hyperadmin-autopilot`, not in a checkout.
- One job per branch: a job is not started while another job, running or queued in the same
  tick, uses its branch, and a pool slot with a running job is never switched away.
- No `--max-budget-usd`: it counts list prices and would stop long runs on a subscription.
- A wall-clock limit per job (a small `perl` alarm wrapper; macOS has no `timeout`) ends the
  job's whole process group, because a job can block at the usage limit instead of failing.
- Prompts are read from the checkout the autopilot runs from, not from the job's branch.
- `review` and `approve-sdd` return a verdict through `--json-schema`
  (`prompts/<job>.schema.json`); the runner applies it, the model does not set labels.
- `fix-pr` resumes the session that implemented the story when it ran in the same pool slot.
- The job acts on GitHub as the bot (`GH_TOKEN` is set from `CLAUDE_GH_TOKEN`) and commits as
  `Claude Code`. `AUTOPILOT=1` turns the interactive hooks in `.claude/settings.json` off.

## Epics and stories

- An epic's branch is `epic/<slug>`, where the slug is the directory name under `.meta/epics/`.
  Creating the branch through the API is the lock: a second attempt gets 422.
- The tick opens an epic only when its slug matches `AUTOPILOT_EPICS` (a regex, matched against
  the whole slug). The default is empty: nothing is opened until the owner enables an epic.
  `AUTOPILOT_MAX_EPICS` (default 2) bounds the epics in progress.
- Opening an epic is one commit through the contents API (`chore(meta): open epic <slug>`:
  `status: in_progress`, `locked_by: autopilot`, `branch: epic/<slug>`) and a draft pull request
  to `develop`.
- A story is ready when its status is `todo`, it is not labelled `deferred` or `needs-human`,
  every dependency is done, and its files do not overlap a story in flight. Dependencies are
  read from `## Blocked by` and from `Blocked by:` / `Depends on:` lines under `## Dependencies`
  (`#123`, a story file name in backticks, or `(st-id)`). A dependency written in words only
  blocks the story and is printed, so it can be fixed in the story.
- Files come from `## Files to Change` (also `## Files`, `## Files Likely Affected`,
  `## Files to modify`). Two stories collide when they share a file, when one names a directory
  the other writes into, or when both touch the same hotspot (`pyproject.toml`/`uv.lock`,
  `.github/`, visual snapshots, and the single hotspot files of
  `.claude/rules/conflict-avoidance.md`). A story without a files section runs alone in its epic.
- A story counts as done when a pull request with `Story: <id>` in its body is merged into the
  epic branch. A pull request without that line is matched by its head branch (the story's
  working branch), and the runner adds the line after the implement job. Feature pull requests
  do not edit `.meta` status; the story issue gets `ap:in-progress`, `ap:in-review`, `ap:done`
  instead.
- A story pull request is merged with `gh pr merge --rebase --delete-branch` when all its checks
  are green, it carries `ai-approved`, has no `needs-human`, and is not behind its epic branch
  (the tick rebases it with `gh pr update-branch --rebase` first when it is).
- `ai-approved` counts only for the commit the reviewer saw. The reviewed head is kept in
  `state.json` and the merge uses `--match-head-commit`. A rebase the tick asks GitHub for
  carries the approval over; anything a `fix-pr` job pushes afterwards drops the label and is
  reviewed again (that review is not charged to the two rounds). Setting the label by hand
  does not merge a pull request: the reviewer job has to approve the head commit.
- A draft epic pull request that conflicts with `develop` is left alone until the end:
  `fix-pr` must not rebase a branch that story pull requests build on, so the rebase is
  `integrate-epic`'s. Failed checks on it are still repaired, with normal commits.
- When every story is merged and no story pull request is open, `integrate-epic` hands the epic
  pull request to the owner. From then on the branch is frozen. If `develop` moves and the
  ready pull request conflicts before the owner approved it, the tick turns it back into a
  draft and integrates it once more; after that, or when its checks go red, the digest says it
  needs a look instead of asking for an approval.
- If opening an epic stops between creating the branch and the open-epic commit, the next tick
  sees an epic branch whose `epic.md` lacks `locked_by: autopilot` and makes the commit, then
  opens the draft pull request.

## Usage limits

A job result with `api_error_status` 429, or `is_error` with usage-limit wording, sets
`cooldown_until`: the epoch from `Claude AI usage limit reached|<epoch>` when present, else the
"resets 3pm" time, else the next five-hour boundary. The job's budget is refunded. During the
cooldown ticks keep doing the deterministic work and start no jobs.

## Janitor

Lists, at most once a day, what is safe to remove: worktrees and local branches whose pull
request is merged, whose tree is clean and whose commits all have an equivalent in
`origin/develop` (`git cherry`), plus merged remote `worktree-*` and `ap-*` branches. Job files
older than seven days are dropped.

It is a dry run until the owner approves it once:

```bash
ops/autopilot/autopilot.sh janitor            # list only, never removes
ops/autopilot/autopilot.sh janitor approve    # recorded in state.json; later ticks remove
ops/autopilot/autopilot.sh janitor revoke
```

Run the scan and clean up before the first live tick: every stale worktree carries its own
`.venv`.

## Commands

| poe | script | |
|---|---|---|
| `poe autopilot:tick` | `autopilot.sh tick` | one tick now |
| `poe autopilot:dry-run` | `AUTOPILOT_DRY_RUN=1 autopilot.sh tick` | print the plan only |
| `poe autopilot:status` | `autopilot.sh status` | state summary and launchd status |
| `poe autopilot:logs` | `autopilot.sh logs [N]` | tail of the tick log |
| `poe autopilot:install` | `autopilot.sh install` | render the plist and load it into launchd |
| `poe autopilot:uninstall` | `autopilot.sh uninstall` | unload and remove the plist |

`autopilot.sh pause` and `autopilot.sh resume` stop and restart ticks without touching launchd.
The `justfile` has the same commands as `just autopilot-<name>`.

## Configuration

Environment, or `~/.hyperadmin-autopilot/config.env` (sourced by the script, kept out of the
repository):

| Variable | Default | |
|---|---|---|
| `CLAUDE_GH_TOKEN` | required | bot token; a live tick refuses to run without it |
| `AUTOPILOT_EPICS` | empty | regex of epic slugs the tick may open |
| `AUTOPILOT_MAX_EPICS` | `2` | epics in progress at once |
| `DEV_AGENT_LIMIT` | `3` | jobs at once (1 when less than 4 GB of memory is free) |
| `AUTOPILOT_PR_SCOPE` | `all` | `autopilot` limits repairs to epic, story and `fix/develop-*` pull requests |
| `AUTOPILOT_DIGEST_HOUR` | `8` | local hour after which the daily digest is written |
| `AUTOPILOT_SLACK_WEBHOOK` | empty | digest target; else `AUTOPILOT_DIGEST_ISSUE` (an issue number); else only `~/.hyperadmin-autopilot/digests/` |
| `AUTOPILOT_MODEL_<JOB>` | see table | model per job, for example `AUTOPILOT_MODEL_FIX_PR=sonnet` |
| `AUTOPILOT_DRY_RUN` | `0` | `1` prints actions only |
| `AUTOPILOT_DRY_FETCH` | `0` | `1` lets a dry run `git fetch` first |
| `AUTOPILOT_HOME` | `~/.hyperadmin-autopilot` | state, logs, job files |
| `AUTOPILOT_NET_SECONDS` | `120` | wall-clock limit of one `gh` or remote `git` call of the tick |
| `AUTOPILOT_INSTALL_ANYWHERE` | `0` | `1` lets `install` run from a checkout other than the main one |

## Before the first live tick

1. The `epic/**` CI lane is merged: without it story pull requests get no checks, and the tick
   waits on them forever (it says so in its output).
2. The labels exist (`scripts/setup-github.sh`); a tick lists the missing ones.
3. `claude` runs headless in a login shell: `zsh -lc 'claude -p "say ok" --output-format json'`.
4. `git push` works without a prompt from that shell (the jobs set `GIT_TERMINAL_PROMPT=0`).
5. A dry run prints a plan you agree with, and the janitor list has been dealt with.
6. `AUTOPILOT_EPICS` names the pilot epic.
7. The digest has somewhere to go: `AUTOPILOT_SLACK_WEBHOOK`, or `AUTOPILOT_DIGEST_ISSUE` set to
   the number of a standing issue (the autopilot does not create one). With neither, the
   digest is only written to `~/.hyperadmin-autopilot/digests/`.

Then `poe autopilot:install`, run from the main checkout: launchd runs the `autopilot.sh` and
the prompts of the checkout named in the plist, so `install` refuses a feature worktree, and
the main checkout has to stay on `develop`. The tick never prompts: its `gh` and remote `git`
calls run with `GIT_TERMINAL_PROMPT=0`, ssh `BatchMode` and a wall-clock limit each, and a
job that is far past its own limit is dropped from the state even if its pid is in use again. `launchctl print gui/$UID/com.hyperadmin.autopilot` shows it
loaded; `pmset` settings decide whether the Mac wakes for the schedule.

## Files

```
ops/autopilot/
  autopilot.sh                          tick, job runner, janitor, install and owner commands
  com.hyperadmin.autopilot.plist.tmpl   launchd agent template
  lib/gh.sh                             read-only collectors and the bot-identity write helpers
  lib/state.sh                          tick lock and state wrappers
  lib/state.py                          state file, usage-limit parsing, retry budgets
  lib/ready.py                          .meta parsing, dependencies, story readiness
  lib/overlap.py                        files sections, hotspots, overlap matrix
  lib/plan.py                           observations -> actions (no side effects)
  prompts/                              one prompt per job, _common.md, verdict schemas
```

The Python is standard library only and is covered by `tests/unit/test_autopilot_*.py`.
