#!/bin/bash
# HyperAdmin autopilot: the local supervisor that runs delivery unattended.
#
# launchd calls `autopilot.sh tick` every 15 minutes. A tick first looks at GitHub and git
# with plain commands (no tokens spent), lets lib/plan.py decide what to do, and only then
# starts headless `claude -p` jobs in a fixed pool of worktrees. See ops/autopilot/README.md.
#
#   AUTOPILOT_DRY_RUN=1 autopilot.sh tick    print the plan, change nothing
#
# Written for the bash 3.2 that ships with macOS: no flock, no timeout, no associative arrays.

set -euo pipefail

AP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AP_LIB="$AP_DIR/lib"
AP_REPO="${AUTOPILOT_REPO:-$(cd "$AP_DIR/../.." && pwd)}"
AP_HOME="${AUTOPILOT_HOME:-$HOME/.hyperadmin-autopilot}"
AP_STATE_FILE="$AP_HOME/state.json"
AP_LABEL="com.hyperadmin.autopilot"
AP_PLIST="$HOME/Library/LaunchAgents/$AP_LABEL.plist"
AP_POOL=3

# Owner settings (AUTOPILOT_EPICS, AUTOPILOT_SLACK_WEBHOOK, ...) live outside the repository.
if [ -f "$AP_HOME/config.env" ]; then
  # shellcheck disable=SC1091  # optional file in the owner's home
  . "$AP_HOME/config.env"
fi

AP_PYTHON="${AUTOPILOT_PYTHON:-python3}"
AP_DRY="${AUTOPILOT_DRY_RUN:-0}"
AP_MIRROR="${AUTOPILOT_MIRROR:-Damdy-OSS}"
# Identity of every commit the autopilot and its jobs make (author and committer).
AP_GIT_NAME="${AUTOPILOT_GIT_NAME:-dodjer88}"
AP_GIT_EMAIL="${AUTOPILOT_GIT_EMAIL:-11336795+dodjer88@users.noreply.github.com}"
DEV_AGENT_LIMIT="${DEV_AGENT_LIMIT:-3}"
AP_MAIN=""
AP_GH_REPO=""
AP_BOT=""
TICK_TMP=""
TICK_LOCKED=0

# shellcheck source=ops/autopilot/lib/state.sh
. "$AP_LIB/state.sh"
# shellcheck source=ops/autopilot/lib/gh.sh
. "$AP_LIB/gh.sh"

dry() {
  [ "$AP_DRY" = "1" ]
}

log() {
  local line
  line="$(date '+%Y-%m-%d %H:%M:%S') $*"
  echo "$line"
  if ! dry && [ -d "$AP_HOME/logs" ]; then
    echo "$line" >>"$AP_HOME/logs/autopilot.log"
  fi
}

die() {
  log "error: $*"
  exit 1
}

# planned WHAT WHY: announce an action; returns 1 in a dry run so the caller stops there.
planned() {
  if dry; then
    log "DRY  $1  # $2"
    return 1
  fi
  log "DO   $1  # $2"
}

require_tools() {
  local tool
  for tool in git gh jq perl "$AP_PYTHON"; do
    command -v "$tool" >/dev/null 2>&1 || die "$tool is not on PATH"
  done
}

# main_checkout: the main worktree of this repository (the pool lives under it).
main_checkout() {
  dirname "$(git -C "$AP_REPO" rev-parse --path-format=absolute --git-common-dir)"
}

# with_alarm SECONDS COMMAND...: run a command with a wall-clock limit. macOS has no
# timeout(1); perl puts the command in its own process group and, when the alarm fires,
# ends the whole group so tools started by the job do not outlive it.
with_alarm() {
  perl -e '
    my $limit = shift;
    my $pid = fork();
    die "fork: $!" unless defined $pid;
    if (!$pid) { setpgrp(0, 0); exec @ARGV; exit 127; }
    my $late = 0;
    $SIG{ALRM} = sub { $late = 1; kill "TERM", -$pid; sleep 10; kill "KILL", -$pid; };
    alarm $limit;
    my $done;
    do { $done = waitpid($pid, 0); } while ($done == -1 && $!{EINTR});
    my $status = $?;
    exit 124 if $late;
    exit(($status & 127) ? 128 + ($status & 127) : $status >> 8);
  ' "$@"
}

# job_defaults JOB: print "model max-turns minutes"; AUTOPILOT_MODEL_<JOB> overrides the model.
job_defaults() {
  local model turns minutes override
  case "$1" in
    implement) model=opus turns=250 minutes=120 ;;
    review) model=sonnet turns=60 minutes=30 ;;
    fix-pr) model=opus turns=150 minutes=60 ;;
    fix-develop) model=opus turns=150 minutes=60 ;;
    approve-sdd) model=opus turns=100 minutes=45 ;;
    integrate-epic) model=sonnet turns=100 minutes=45 ;;
    digest) model=haiku turns=15 minutes=10 ;;
    *) return 1 ;;
  esac
  override="AUTOPILOT_MODEL_$(printf '%s' "$1" | tr 'a-z-' 'A-Z_')"
  echo "${!override:-$model} $turns $minutes"
}

# ── worktree pool ─────────────────────────────────────────────────────────────

# slot_busy SLOT: true when the state lists a running job in that pool slot.
slot_busy() {
  state get jobs | jq -e --argjson slot "$1" 'any(.[]?; .slot == $slot)' >/dev/null 2>&1
}

# pool_prepare SLOT JOB BRANCH BASE: point .claude/worktrees/ap-SLOT at the job's branch.
# The worktree is reused between jobs; `uv sync` runs only when uv.lock changed.
pool_prepare() {
  local slot="$1" job="$2" branch="$3" base="$4"
  local wt="$AP_MAIN/.claude/worktrees/ap-$slot" other lock stamp
  if [ ! -e "$wt/.git" ]; then
    git -C "$AP_MAIN" worktree prune
    git -C "$AP_MAIN" worktree add --detach "$wt" origin/develop >/dev/null || return 1
  else
    git -C "$wt" reset --hard -q || return 1
    git -C "$wt" clean -fdq || return 1
  fi
  if [ "$job" = "review" ] || [ -z "$branch" ]; then
    git -C "$wt" checkout -q --detach "$base" || return 1
  else
    # A slot whose runner died may still hold this branch; an idle slot can let go of it.
    # A slot with a running job never does: the planner gives a branch to one job at a time,
    # and if that ever fails this job is not started rather than pulling the branch away.
    for other in 1 2 3; do
      if [ "$other" != "$slot" ] && [ -e "$AP_MAIN/.claude/worktrees/ap-$other/.git" ] &&
        [ "$(git -C "$AP_MAIN/.claude/worktrees/ap-$other" branch --show-current)" = "$branch" ]; then
        if slot_busy "$other"; then
          log "  !! $branch is in use by the job in ap-$other"
          return 1
        fi
        git -C "$AP_MAIN/.claude/worktrees/ap-$other" checkout -q --detach || return 1
      fi
    done
    # A second implement attempt continues the branch the first one pushed.
    if [ "$job" = "implement" ] && git -C "$wt" rev-parse -q --verify "origin/$branch^{commit}" >/dev/null 2>&1; then
      base="origin/$branch"
    fi
    if git -C "$wt" rev-parse -q --verify "refs/heads/$branch^{commit}" >/dev/null 2>&1 &&
      git -C "$wt" merge-base --is-ancestor "$base" "refs/heads/$branch" 2>/dev/null; then
      # The local branch is the base plus commits an earlier attempt never pushed (a job
      # ended by the wall-clock limit, say): keep them, the next attempt continues there.
      git -C "$wt" checkout -q "$branch" || return 1
    else
      # --no-track: a plain `git push` must never land on the base (the epic branch).
      git -C "$wt" checkout -q --no-track -B "$branch" "$base" || return 1
    fi
  fi
  lock="$(git -C "$wt" rev-parse HEAD:uv.lock 2>/dev/null || true)"
  stamp="$AP_HOME/pool/ap-$slot.uvlock"
  if [ ! -d "$wt/.venv" ] || [ "$(cat "$stamp" 2>/dev/null || true)" != "$lock" ]; then
    log "  .. uv sync in ap-$slot"
    (cd "$wt" && with_alarm 900 uv sync --all-extras --quiet) || return 1
    echo "$lock" >"$stamp"
  fi
}

# ── actions ───────────────────────────────────────────────────────────────────

do_rerun_run() {
  planned "rerun workflow run $1" "$2" || return 0
  state bump runs "$1" rerun >/dev/null
  gh_bot run rerun "$1" -R "$AP_GH_REPO" --failed
}

do_rerun_pr() {
  local pr="$1" runs="$2" run
  planned "rerun cancelled checks of PR #$pr (runs $runs)" "$3" || return 0
  state bump prs "$pr" rerun >/dev/null
  for run in $runs; do
    gh_bot run rerun "$run" -R "$AP_GH_REPO" --failed || log "  !! rerun of $run failed"
  done
}

do_clear_budget() {
  planned "clear the retry counters of $1 '$2'" "$3" || return 0
  state clear "$1" "$2"
}

# do_update_branch PR SHA WHY: let GitHub rebase an approved story PR on its epic branch.
# The approval is tied to a commit, so it is moved to the rebased head: the same commits,
# replayed by GitHub on a base that was itself reviewed. If the new head does not show up
# in time the approval stays on the old commit and the PR is simply reviewed again.
do_update_branch() {
  local pr="$1" old="$2" new="" try
  planned "rebase PR #$pr on its base (gh pr update-branch --rebase)" "$3" || return 0
  gh_bot pr update-branch "$pr" -R "$AP_GH_REPO" --rebase || return 1
  if [ -z "$old" ] || [ "$(state_value "prs.$pr.approved_sha")" != "$old" ]; then
    return 0
  fi
  for try in 1 2 3 4 5; do
    new="$(pr_head "$pr")"
    if [ -n "$new" ] && [ "$new" != "$old" ]; then
      state set "prs.$pr.approved_sha" "\"$new\""
      return 0
    fi
    [ "$try" = 5 ] || sleep 3
  done
  log "  .. PR #$pr: rebased head not visible yet; it will be reviewed again"
}

# do_merge PR STORY ISSUE SHA WHY: merge exactly the commit the reviewer approved.
do_merge() {
  local pr="$1" story="$2" issue="$3" sha="$4"
  planned "rebase-merge story PR #$pr${story:+ (story $story)}${sha:+ at ${sha:0:9}}" "$5" || return 0
  [ -n "$sha" ] || return 1
  gh_bot pr merge "$pr" -R "$AP_GH_REPO" --rebase --delete-branch --match-head-commit "$sha" || return 1
  issue_stage "$issue" ap:done
  state note "merged story PR #$pr${story:+ ($story)} into its epic branch"
}

# do_epic_to_draft PR SLUG WHY: a ready epic PR that conflicts with develop can never
# auto-merge. Take it back to draft so integrate-epic rebases and hands it over again.
do_epic_to_draft() {
  local pr="$1" slug="$2"
  planned "turn epic PR #$pr back into a draft (auto-merge off)" "$3" || return 0
  gh_bot pr merge "$pr" -R "$AP_GH_REPO" --disable-auto >/dev/null 2>&1 || true
  gh_bot pr ready "$pr" -R "$AP_GH_REPO" --undo || return 1
  state note "epic $slug: PR #$pr conflicted with develop after the hand-over; it is integrated again"
}

do_needs_human() {
  local pr="$1" reason="$2"
  planned "label PR #$pr needs-human" "$3" || return 0
  state set "prs.$pr.escalated" true
  label_swap pr "$pr" needs-human
  gh_bot pr comment "$pr" -R "$AP_GH_REPO" --body "The autopilot stopped working on this pull request: $reason.

Fix what blocks it, then run \`ops/autopilot/autopilot.sh reset pr $pr\` and remove the \`needs-human\` label to hand it back." >/dev/null
  state note "PR #$pr needs a human: $reason"
}

# do_open_epic_pr SLUG: open the draft pull request epic/<slug> -> develop.
do_open_epic_pr() {
  local slug="$1" title issue body
  planned "open draft PR epic/$slug -> develop" "$2" || return 0
  title="$(sed -n 's/^title:[[:space:]]*//p' "$TICK_TMP/meta/develop/epics/$slug/epic.md" | head -1 | sed -e 's/^"//' -e 's/"$//')"
  issue="$(sed -n 's/^[[:space:]]*issue_number:[[:space:]]*//p' "$TICK_TMP/meta/develop/epics/$slug/epic.md" | head -1)"
  body="Epic branch for \`$slug\`${issue:+ (epic #$issue)}.

Story pull requests are rebase-merged into \`epic/$slug\` by the autopilot once CI is green and the reviewer agent has approved them. This pull request stays a draft until every story and the spec review are done; then it is rebased on \`develop\`, marked ready and handed to the owner for the one approval this epic needs."
  gh_bot pr create -R "$AP_GH_REPO" --draft --base develop --head "epic/$slug" \
    --title "${title:-epic: $slug}" --body "$body"
}

# do_open_epic SLUG: take the epic. Creating the branch through the API is the lock: a second
# attempt gets 422 "Reference already exists". The first commit marks the epic in_progress.
do_open_epic() {
  local slug="$1" branch="epic/$1" sha
  planned "create branch $branch from develop (lock), commit 'chore(meta): open epic', open draft PR" "$2" || return 0
  sha="$(gh_ro api "repos/$AP_GH_REPO/git/ref/heads/develop" --jq .object.sha)" || return 1
  if ! gh_bot api -X POST "repos/$AP_GH_REPO/git/refs" -f "ref=refs/heads/$branch" -f "sha=$sha" >/dev/null; then
    log "  .. $branch already exists or could not be created; leaving it alone"
    return 0
  fi
  # If the commit fails here the branch stays: a later tick sees an epic branch without
  # `locked_by: autopilot` and plans open-epic-commit, then open-epic-pr.
  open_epic_commit "$slug" || return 1
  do_open_epic_pr "$slug" "$2"
}

# do_open_epic_commit SLUG WHY: make the open-epic commit on a branch that lacks it.
do_open_epic_commit() {
  planned "commit 'chore(meta): open epic $1' on epic/$1" "$2" || return 0
  open_epic_commit "$1"
}

# open_epic_commit SLUG: write status in_progress and the lock fields into the epic.md of
# the epic branch, as one commit through the contents API (no checkout needed).
open_epic_commit() {
  local slug="$1" branch="epic/$1" path=".meta/epics/$1/epic.md" blob
  blob="$(gh_ro api "repos/$AP_GH_REPO/contents/$path?ref=$branch" --jq .sha)" || return 1
  gh_ro api "repos/$AP_GH_REPO/contents/$path?ref=$branch" -H "Accept: application/vnd.github.raw" \
    >"$TICK_TMP/epic.md" || return 1
  "$AP_PYTHON" "$AP_LIB/ready.py" open-epic "$TICK_TMP/epic.md" "$slug" >"$TICK_TMP/epic.new.md" || return 1
  gh_bot api -X PUT "repos/$AP_GH_REPO/contents/$path" \
    -f "message=chore(meta): open epic $slug" -f "branch=$branch" -f "sha=$blob" \
    -f "content=$(base64 <"$TICK_TMP/epic.new.md" | tr -d '\n')" \
    -f "author[name]=$AP_GIT_NAME" -f "author[email]=$AP_GIT_EMAIL" \
    -f "committer[name]=$AP_GIT_NAME" -f "committer[email]=$AP_GIT_EMAIL" \
    >/dev/null || return 1
  state note "opened epic $slug on $branch"
}

# do_spawn JOB TARGET SLOT BRANCH BASE META WHY: start one headless job in the background.
do_spawn() {
  local job="$1" target="$2" slot="$3" branch="$4" base="$5" meta="$6" why="$7"
  local id cwd session resume model turns minutes
  planned "spawn $job $target (slot $slot${branch:+, branch $branch})" "$why" || return 0
  command -v claude >/dev/null 2>&1 || {
    log "  !! claude is not on PATH"
    return 1
  }
  id="$(date +%Y%m%d-%H%M%S)-$job-$(safe_name "$target")"
  # A job without a pool slot (the digest) reads only: it runs outside every checkout.
  cwd="$AP_HOME"
  if [ "$slot" -gt 0 ]; then
    cwd="$AP_MAIN/.claude/worktrees/ap-$slot"
    if ! pool_prepare "$slot" "$job" "$branch" "$base"; then
      log "  !! could not prepare ap-$slot for $job $target"
      state note "$job $target was not started: worktree ap-$slot could not be prepared"
      return 1
    fi
  fi
  read -r model turns minutes <<EOF
$(job_defaults "$job")
EOF
  session="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  # fix-pr continues the session that implemented the story when its transcript is here.
  resume="$(printf '%s' "$meta" | jq -r '.resume // empty')"
  if [ -n "$resume" ] && [ ! -f "$HOME/.claude/projects/$(printf '%s' "$cwd" | tr '/.' '-')/$resume.jsonl" ]; then
    resume=""
  fi
  jq -n --argjson meta "$meta" --arg id "$id" --arg kind "$job" --arg target "$target" \
    --argjson slot "$slot" --arg branch "$branch" --arg base "$base" --arg cwd "$cwd" \
    --arg session "$session" --arg resume "$resume" --arg model "$model" --argjson turns "$turns" \
    --argjson timeout "$((minutes * 60))" --arg repo "$AP_GH_REPO" \
    '$meta + {id: $id, kind: $kind, target: $target, slot: $slot, branch: $branch, base: $base,
      cwd: $cwd, session: $session, resume: $resume, model: $model, turns: $turns,
      timeout: $timeout, repo: $repo}' >"$AP_HOME/jobs/$id.job.json"
  if [ "$job" = "digest" ]; then
    jq -n --argjson digest "$(state get digest)" --argjson janitor "$(state get janitor)" \
      '{notes: [$digest.notes[]?.text], janitor: $janitor}' >"$AP_HOME/jobs/$id.input.json"
  fi
  (
    cd "$AP_MAIN"
    if command -v caffeinate >/dev/null 2>&1; then
      nohup caffeinate -i "$AP_DIR/autopilot.sh" run-job "$id" >>"$AP_HOME/logs/$id.log" 2>&1 </dev/null &
    else
      nohup "$AP_DIR/autopilot.sh" run-job "$id" >>"$AP_HOME/logs/$id.log" 2>&1 </dev/null &
    fi
  )
  if [ "$job" = "implement" ]; then
    issue_stage "$(printf '%s' "$meta" | jq -r '.issue // empty')" ap:in-progress
  fi
}

# execute_plan FILE: carry out the rows lib/plan.py wrote. One failing action never stops
# the others.
execute_plan() {
  local kind a b c d e f why
  while IFS="$(printf '\037')" read -r -u 3 kind a b c d e f why; do
    case "$kind" in
      info) log "  .. $why" ;;
      note)
        log "  note: $why"
        dry || state note "$why"
        ;;
      rerun-run) do_rerun_run "$a" "$why" || log "  !! rerun-run $a failed" ;;
      clear-budget) do_clear_budget "$a" "$b" "$why" || log "  !! clear-budget $a $b failed" ;;
      rerun-pr) do_rerun_pr "$a" "$b" "$why" || log "  !! rerun-pr $a failed" ;;
      update-branch) do_update_branch "$a" "$b" "$why" || log "  !! update-branch $a failed" ;;
      merge) do_merge "$a" "$b" "$c" "$d" "$why" || log "  !! merge of PR #$a failed" ;;
      needs-human) do_needs_human "$a" "$b" "$why" || log "  !! needs-human on PR #$a failed" ;;
      epic-to-draft) do_epic_to_draft "$a" "$b" "$why" || log "  !! epic-to-draft of PR #$a failed" ;;
      open-epic) do_open_epic "$a" "$why" || log "  !! open-epic $a failed" ;;
      open-epic-commit) do_open_epic_commit "$a" "$why" || log "  !! open-epic-commit $a failed" ;;
      open-epic-pr) do_open_epic_pr "$a" "$why" || log "  !! open-epic-pr $a failed" ;;
      spawn) do_spawn "$a" "$b" "$c" "$d" "$e" "$f" "$why" || log "  !! spawn $a $b failed" ;;
      *) log "  !! unknown plan row: $kind" ;;
    esac
  done 3<"$1"
}

# ── janitor ───────────────────────────────────────────────────────────────────

# in_develop REF: true when every commit of REF has an equivalent in origin/develop.
in_develop() {
  local out
  out="$(git -C "$AP_MAIN" cherry origin/develop "$1" 2>/dev/null)" || return 1
  ! printf '%s\n' "$out" | grep -q '^+'
}

# janitor_worktree PATH BRANCH LOCKED: print a candidate row when the worktree is safe to drop.
janitor_worktree() {
  local path="$1" branch="$2" locked="$3"
  [ -n "$path" ] && [ -n "$branch" ] && [ "$locked" = "0" ] || return 0
  echo "$branch" >>"$TICK_TMP/checked-out.txt"
  case "$path" in
    "$AP_MAIN" | "$AP_REPO" | "$AP_MAIN"/.claude/worktrees/ap-[0-9]*) return 0 ;;
  esac
  grep -qxF "$branch" "$TICK_TMP/merged-heads.txt" || return 0
  [ -d "$path" ] || return 0
  # --no-optional-locks: looking at a worktree must not rewrite its index.
  [ -z "$(git --no-optional-locks -C "$path" status --porcelain 2>/dev/null | head -1)" ] || return 0
  in_develop "$branch" || return 0
  printf 'worktree\t%s\t%s\n' "$path" "$branch"
}

# janitor_scan: list what could be removed, one row per item: KIND <tab> NAME <tab> BRANCH.
# Only work whose pull request is merged, whose tree is clean and whose commits are all in
# develop qualifies. Nothing is changed here.
janitor_scan() {
  local line path="" branch="" locked=0 name sha started="$SECONDS"
  gh_ro pr list -R "$AP_GH_REPO" --state merged --limit 500 --json headRefName \
    --jq '.[].headRefName' | sort -u >"$TICK_TMP/merged-heads.txt"
  : >"$TICK_TMP/checked-out.txt"
  git -C "$AP_MAIN" worktree list --porcelain >"$TICK_TMP/worktrees.txt"
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      "worktree "*)
        janitor_worktree "$path" "$branch" "$locked"
        path="${line#worktree }" branch="" locked=0
        ;;
      "branch refs/heads/"*) branch="${line#branch refs/heads/}" ;;
      locked*) locked=1 ;;
    esac
  done <"$TICK_TMP/worktrees.txt"
  janitor_worktree "$path" "$branch" "$locked"
  git -C "$AP_MAIN" for-each-ref refs/heads --format='%(refname:short)' >"$TICK_TMP/branches.txt"
  while IFS= read -r name; do
    if [ $((SECONDS - started)) -gt "${AUTOPILOT_JANITOR_SECONDS:-120}" ]; then
      log "  .. janitor scan stopped after $((SECONDS - started)) s; the rest waits for the next run" >&2
      break
    fi
    case "$name" in
      develop | master | main | epic/*) continue ;;
    esac
    grep -qxF "$name" "$TICK_TMP/checked-out.txt" && continue
    grep -qxF "$name" "$TICK_TMP/merged-heads.txt" || continue
    in_develop "$name" || continue
    printf 'branch\t%s\t\n' "$name"
  done <"$TICK_TMP/branches.txt"
  net_git -C "$AP_MAIN" ls-remote --heads origin 'worktree-*' 'ap-*' 2>/dev/null >"$TICK_TMP/remote-heads.txt" || true
  while read -r sha name; do
    name="${name#refs/heads/}"
    grep -qxF "$name" "$TICK_TMP/merged-heads.txt" || continue
    git -C "$AP_MAIN" cat-file -e "$sha^{commit}" 2>/dev/null || continue
    in_develop "$sha" || continue
    printf 'remote\t%s\t\n' "$name"
  done <"$TICK_TMP/remote-heads.txt"
}

# janitor_apply FILE: remove the listed items (only ever called after the owner's approval).
janitor_apply() {
  local kind name branch count=0 limit="${AUTOPILOT_JANITOR_BATCH:-30}"
  while IFS="$(printf '\t')" read -r -u 3 kind name branch; do
    [ "$count" -lt "$limit" ] || break
    count=$((count + 1))
    case "$kind" in
      worktree)
        log "DO   janitor: remove worktree $name and branch $branch"
        # No --force: git itself refuses a worktree with changes.
        if git -C "$AP_MAIN" worktree remove "$name"; then
          git -C "$AP_MAIN" branch -D "$branch" >/dev/null || log "  !! could not delete $branch"
        else
          log "  !! could not remove $name"
        fi
        ;;
      branch)
        log "DO   janitor: delete local branch $name"
        git -C "$AP_MAIN" branch -D "$name" >/dev/null || log "  !! could not delete $name"
        ;;
      remote)
        log "DO   janitor: delete remote branch $name"
        net_git -C "$AP_MAIN" push origin --delete "$name" >/dev/null 2>&1 || log "  !! could not delete origin/$name"
        ;;
    esac
  done 3<"$1"
}

# janitor MODE: scan once a day ("auto") or now ("force"). Until the owner approves
# (`autopilot.sh janitor approve`, kept in state.json) the result is only listed.
janitor() {
  local mode="$1" now last count approved
  now="$(date +%s)"
  if ! dry; then
    find "$AP_HOME/jobs" -type f -mtime +7 -delete 2>/dev/null || true
  fi
  last="$(state_value janitor.last_run)"
  if [ "$mode" != "force" ] && [ $((now - ${last:-0})) -lt 86400 ]; then
    return 0
  fi
  janitor_scan >"$TICK_TMP/janitor.tsv"
  count="$(wc -l <"$TICK_TMP/janitor.tsv" | tr -d ' ')"
  approved="$(state_value janitor.approved)"
  if dry || [ "$approved" != "true" ]; then
    log "janitor (dry run, not approved): $count removable items"
    head -n "${AUTOPILOT_JANITOR_SHOW:-40}" "$TICK_TMP/janitor.tsv" | sed 's/^/  would remove /'
    if [ "$count" -gt "${AUTOPILOT_JANITOR_SHOW:-40}" ]; then
      echo "  ... and $((count - ${AUTOPILOT_JANITOR_SHOW:-40})) more"
    fi
    if ! dry; then
      state set janitor.candidates "$(jq -R -s 'split("\n") | map(select(. != ""))' <"$TICK_TMP/janitor.tsv")"
      state set janitor.last_run "$now"
      [ "$count" -eq 0 ] || state note "janitor: $count worktrees and branches can be removed; approve with 'autopilot.sh janitor approve'"
    fi
    return 0
  fi
  log "janitor: $count removable items"
  janitor_apply "$TICK_TMP/janitor.tsv"
  state set janitor.candidates '[]'
  state set janitor.last_run "$now"
}

# ── tick ──────────────────────────────────────────────────────────────────────

tick_cleanup() {
  case "$TICK_TMP" in
    */autopilot-tick.*) rm -rf "$TICK_TMP" ;;
  esac
  if [ "$TICK_LOCKED" = "1" ]; then
    lock_release tick
  fi
}

tick_setup() {
  require_tools
  AP_MAIN="$(main_checkout)"
  AP_GH_REPO="$(repo_slug)"
  [ -n "$AP_GH_REPO" ] || die "cannot tell the GitHub repository from the origin remote"
  # Nobody answers a prompt under launchd: a credential or host-key question must fail at
  # once instead of holding the tick (and its lock) for good.
  export GIT_TERMINAL_PROMPT=0
  export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -oBatchMode=yes}"
  trap tick_cleanup EXIT
  if ! dry; then
    [ -n "${CLAUDE_GH_TOKEN:-}" ] || die "CLAUDE_GH_TOKEN is not set (the bot identity is required)"
    mkdir -p "$AP_HOME/jobs" "$AP_HOME/logs" "$AP_HOME/pool" "$AP_HOME/digests"
    if ! lock_acquire tick; then
      log "another tick is running; nothing to do"
      exit 0
    fi
    TICK_LOCKED=1
  fi
  TICK_TMP="$(mktemp -d "${TMPDIR:-/tmp}/autopilot-tick.XXXXXX")"
}

cmd_tick() {
  local missing
  if paused; then
    echo "autopilot is paused ($AP_HOME/PAUSE exists)"
    return 0
  fi
  tick_setup
  log "tick start: repo $AP_GH_REPO, checkout $AP_REPO$(dry && echo ', DRY RUN (nothing is changed)')"
  if dry; then
    if [ "${AUTOPILOT_DRY_FETCH:-0}" = "1" ]; then
      with_alarm 300 git -C "$AP_REPO" fetch origin --prune --quiet || die "git fetch failed or timed out"
    else
      log "  .. dry run: no git fetch; origin/develop is as of $(git -C "$AP_REPO" log -1 --format=%cr origin/develop)"
    fi
  else
    state init
    state reap >/dev/null
    with_alarm 300 git -C "$AP_REPO" fetch origin --prune --quiet || die "git fetch failed or timed out"
  fi
  state show | sed 's/^/  state: /'
  AP_BOT="$(bot_login)"
  if [ -z "$AP_BOT" ]; then
    log "  !! bot login unknown (set CLAUDE_GH_TOKEN or AUTOPILOT_BOT_LOGIN): pull requests are left alone"
  fi
  missing="$(missing_labels)"
  if [ -n "$missing" ]; then
    log "  !! labels missing in $AP_GH_REPO: $missing(run scripts/setup-github.sh)"
  fi
  collect_prs
  collect_runs
  collect_epics
  collect_issues
  collect_meta
  collect_env
  # The janitor goes first: stale worktrees are the main disk cost, the pool comes after.
  janitor auto
  "$AP_PYTHON" "$AP_LIB/plan.py" "$TICK_TMP" >"$TICK_TMP/plan.rows"
  log "plan: $(grep -cv -e "^info" -e "^note" "$TICK_TMP/plan.rows" || true) actions, bot ${AP_BOT:-unknown}, limit $DEV_AGENT_LIMIT"
  execute_plan "$TICK_TMP/plan.rows"
  log "tick done"
}

# ── job runner ────────────────────────────────────────────────────────────────

# job_field FILE NAME: print one field of a job spec ("" when absent).
job_field() {
  jq -r --arg name "$2" '.[$name] // empty | tostring' "$1"
}

# after_job: the deterministic follow-up of a finished job (labels, comments, state).
after_job() {
  local spec="$1" result="$2" status="$3" kind pr issue story branch epic verdict text day
  local body head approved
  kind="$(job_field "$spec" kind)"
  pr="$(job_field "$spec" pr)"
  case "$kind" in
    implement)
      issue="$(job_field "$spec" issue)"
      story="$(job_field "$spec" story)"
      branch="$(job_field "$spec" branch)"
      pr="$(gh_bot pr list -R "$AP_GH_REPO" --head "$branch" --state open --json number --jq '.[0].number // empty' || true)"
      if [ -n "$pr" ]; then
        # The Story line is how the tick links the pull request to its story; add it when
        # the job forgot (the planner also falls back to the head branch).
        body="$(gh_ro pr view "$pr" -R "$AP_GH_REPO" --json body --jq .body 2>/dev/null || true)"
        if [ -n "$story" ] && ! printf '%s\n' "$body" | grep -qE '^Story:[[:space:]]*`?[A-Za-z0-9_.-]+'; then
          gh_bot pr edit "$pr" -R "$AP_GH_REPO" --body "Story: $story

$body" >/dev/null || log "  !! could not add the Story line to PR #$pr"
        fi
        issue_stage "$issue" ap:in-review
        [ -z "$issue" ] || gh_bot issue comment "$issue" -R "$AP_GH_REPO" \
          --body "The autopilot opened #$pr for this story." >/dev/null || true
      else
        state note "implement $story ended without a pull request ($status)"
      fi
      ;;
    review)
      verdict="$(jq -r '.structured_output.verdict // empty' "$result" 2>/dev/null || true)"
      head="$(job_field "$spec" head_sha)"
      case "$verdict" in
        approve)
          # The approval stands for the commit that was reviewed; the tick merges only that.
          state set "prs.$pr.approved_sha" "\"$head\""
          label_swap pr "$pr" ai-approved ai-changes-requested
          ;;
        request_changes)
          state set "prs.$pr.approved_sha" '""'
          label_swap pr "$pr" ai-changes-requested ai-approved
          ;;
        *) state note "review of PR #$pr returned no verdict ($status)" ;;
      esac
      ;;
    fix-pr)
      if [ "$status" = "ok" ]; then
        gh_bot pr edit "$pr" -R "$AP_GH_REPO" --remove-label ai-changes-requested >/dev/null 2>&1 || true
        approved="$(state_value "prs.$pr.approved_sha")"
        head="$(pr_head "$pr")"
        if [ -n "$approved" ] && [ -n "$head" ] && [ "$head" != "$approved" ]; then
          # The fix changed an approved pull request: what it pushed is reviewed before the
          # merge, and that extra review does not count against the two rounds.
          state set "prs.$pr.approved_sha" '""'
          state bump prs "$pr" review --by -1 >/dev/null
          gh_bot pr edit "$pr" -R "$AP_GH_REPO" --remove-label ai-approved >/dev/null 2>&1 || true
        fi
      fi
      ;;
    approve-sdd)
      epic="$(job_field "$spec" epic)"
      verdict="$(jq -r '.structured_output.verdict // empty' "$result" 2>/dev/null || true)"
      case "$verdict" in
        approved | escalated) state set "epics.$epic.spec" "\"$verdict\"" ;;
        *) state note "approve-sdd $epic returned no verdict ($status)" ;;
      esac
      ;;
    digest)
      [ "$status" = "ok" ] || return 0
      day="$(date +%F)"
      text="$(jq -r '.result // empty' "$result")"
      [ -n "$text" ] || return 0
      printf '%s\n' "$text" >"$AP_HOME/digests/$day.md"
      if [ -n "${AUTOPILOT_SLACK_WEBHOOK:-}" ]; then
        curl -fsS --max-time 30 -X POST -H 'Content-Type: application/json' \
          -d "$(jq -n --arg text "$text" '{text: $text}')" "$AUTOPILOT_SLACK_WEBHOOK" >/dev/null || return 1
      elif [ -n "${AUTOPILOT_DIGEST_ISSUE:-}" ]; then
        gh_bot issue comment "$AUTOPILOT_DIGEST_ISSUE" -R "$AP_GH_REPO" \
          --body-file "$AP_HOME/digests/$day.md" >/dev/null || return 1
      else
        log "digest written to $AP_HOME/digests/$day.md only: set AUTOPILOT_SLACK_WEBHOOK or AUTOPILOT_DIGEST_ISSUE to have it delivered"
      fi
      state digest-sent
      ;;
  esac
}

# cmd_run_job ID: run one job to its end. Started in the background by the tick.
cmd_run_job() {
  local id="$1" spec="$AP_HOME/jobs/$1.job.json" result="$AP_HOME/jobs/$1.result.json"
  local kind cwd prompt rc=0 outcome status schema
  local -a flags
  [ -f "$spec" ] || die "no job spec $spec"
  AP_MAIN="$(main_checkout)"
  AP_GH_REPO="$(job_field "$spec" repo)"
  kind="$(job_field "$spec" kind)"
  cwd="$(job_field "$spec" cwd)"
  state job-start "$(jq -c --argjson pid "$$" '. + {pid: $pid}' "$spec")"
  # Prompts are read from this checkout, not from the job's branch.
  prompt="$(cat "$AP_DIR/prompts/_common.md" "$AP_DIR/prompts/$kind.md")

## Job arguments

$(jq -r 'del(.cwd, .session, .resume, .resume_slot, .model, .turns, .timeout, .slot, .id)
  | to_entries | map(select(.value != null and .value != "")) | map("- \(.key): \(.value)") | join("\n")' "$spec")"
  if [ -f "$AP_HOME/jobs/$id.input.json" ]; then
    prompt="$prompt

## Input

$(cat "$AP_HOME/jobs/$id.input.json")"
  fi
  case "$kind" in
    review | digest)
      # These jobs only read and report, so they get no edit tools at all (--tools), no
      # edit-accepting mode, and an allowlist of read commands. review may post its comment.
      flags=(--permission-mode manual --permission-prompts none
        --tools Read Glob Grep Bash
        --allowedTools Read Glob Grep 'Bash(gh pr view:*)' 'Bash(gh pr diff:*)' 'Bash(gh pr list:*)'
        'Bash(gh pr checks:*)' 'Bash(gh issue view:*)' 'Bash(gh issue list:*)' 'Bash(gh run view:*)'
        'Bash(git log:*)' 'Bash(git diff:*)' 'Bash(git show:*)' 'Bash(git status:*)')
      if [ "$kind" = "review" ]; then
        flags+=('Bash(gh pr comment:*)')
      fi
      ;;
    *)
      flags=(--permission-mode acceptEdits --permission-prompts none
        --allowedTools 'Bash(git:*)' 'Bash(gh pr:*)' 'Bash(gh api:*)' 'Bash(gh run:*)' 'Bash(gh issue:*)'
        'Bash(uv run:*)' 'Bash(./scripts/gitpm.sh:*)' Read Edit Write Glob Grep Agent
        --disallowedTools 'Bash(gh release:*)' 'Bash(gh repo:*)' "Bash(git push:*${AP_MIRROR}*)")
      ;;
  esac
  flags+=(--output-format json --max-turns "$(job_field "$spec" turns)" --model "$(job_field "$spec" model)")
  if [ -n "$(job_field "$spec" resume)" ]; then
    flags+=(--resume "$(job_field "$spec" resume)")
  else
    flags+=(--session-id "$(job_field "$spec" session)")
  fi
  schema="$AP_DIR/prompts/$kind.schema.json"
  if [ -f "$schema" ]; then
    flags+=(--json-schema "$(jq -c . "$schema")")
  fi
  log "job $id: $kind $(job_field "$spec" target) in $cwd"
  (
    cd "$cwd"
    # The job acts as the bot on GitHub and commits with the configured identity. AUTOPILOT=1 turns the
    # interactive hooks of .claude/settings.json into no-ops.
    # shellcheck disable=SC2031  # gh_bot sets GH_TOKEN in its own subshell; this is another one
    export AUTOPILOT=1 GH_TOKEN="${CLAUDE_GH_TOKEN:-}" GIT_TERMINAL_PROMPT=0
    # GH_REPO: plain `gh` finds the repository even where the job runs outside a checkout.
    export GH_REPO="$AP_GH_REPO"
    export GIT_AUTHOR_NAME="$AP_GIT_NAME" GIT_AUTHOR_EMAIL="$AP_GIT_EMAIL"
    export GIT_COMMITTER_NAME="$AP_GIT_NAME" GIT_COMMITTER_EMAIL="$AP_GIT_EMAIL"
    with_alarm "$(job_field "$spec" timeout)" claude -p "$prompt" "${flags[@]}" \
      >"$result" 2>"$AP_HOME/jobs/$id.stderr"
  ) || rc=$?
  outcome="$(state job-finish "$id" --rc "$rc" --result "$result")"
  status="$(printf '%s' "$outcome" | jq -r '.status // "error"')"
  log "job $id: finished, rc $rc, status $status"
  if [ "$(job_field "$spec" slot)" -gt 0 ]; then
    git -C "$cwd" checkout -q --detach 2>/dev/null || true
  fi
  if [ "$status" != "cooldown" ]; then
    after_job "$spec" "$result" "$status" || log "job $id: follow-up failed"
  fi
}

# ── owner commands ────────────────────────────────────────────────────────────

cmd_status() {
  echo "home: $AP_HOME$(paused && echo ' (PAUSED)')"
  state show
  if command -v launchctl >/dev/null 2>&1; then
    launchctl print "gui/$(id -u)/$AP_LABEL" 2>/dev/null | grep -E '^[[:space:]]*(state|last exit code|run interval) =' ||
      echo "launchd: $AP_LABEL is not loaded"
  fi
}

cmd_logs() {
  [ -f "$AP_HOME/logs/autopilot.log" ] || die "no log yet at $AP_HOME/logs/autopilot.log"
  tail -n "${1:-100}" "$AP_HOME/logs/autopilot.log"
}

cmd_install() {
  local main branch
  if dry; then
    log "DRY  render $AP_PLIST from the template (repository $AP_REPO) and bootstrap it into launchd"
    return 0
  fi
  # launchd runs the autopilot.sh and the prompts of the checkout named in the plist. A
  # feature worktree is on some branch and may be removed later, so only the main checkout
  # is accepted unless the owner insists.
  main="$(main_checkout)"
  branch="$(git -C "$AP_REPO" branch --show-current)"
  if [ "$AP_REPO" != "$main" ] && [ "${AUTOPILOT_INSTALL_ANYWHERE:-0}" != "1" ]; then
    die "install from the main checkout ($main), not from $AP_REPO (AUTOPILOT_INSTALL_ANYWHERE=1 overrides)"
  fi
  echo "installing for $AP_REPO (branch ${branch:-detached}); this checkout must stay on develop"
  mkdir -p "$AP_HOME/logs" "$(dirname "$AP_PLIST")"
  sed -e "s|@REPO@|$AP_REPO|g" -e "s|@HOME@|$HOME|g" -e "s|@LABEL@|$AP_LABEL|g" \
    "$AP_DIR/$AP_LABEL.plist.tmpl" >"$AP_PLIST"
  plutil -lint "$AP_PLIST"
  launchctl bootout "gui/$(id -u)/$AP_LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$AP_PLIST"
  echo "installed $AP_PLIST; check with: $0 status"
}

cmd_uninstall() {
  if dry; then
    log "DRY  bootout $AP_LABEL and remove $AP_PLIST"
    return 0
  fi
  launchctl bootout "gui/$(id -u)/$AP_LABEL" 2>/dev/null || true
  rm -f "$AP_PLIST"
  echo "uninstalled $AP_LABEL (state stays in $AP_HOME)"
}

cmd_janitor() {
  case "${1:-scan}" in
    scan)
      # Listing only: a scan never removes anything, whatever the approval says.
      AP_DRY=1
      tick_setup
      janitor force
      ;;
    approve)
      state set janitor.approved true
      echo "janitor approved: the next tick removes what the scan lists"
      ;;
    revoke)
      state set janitor.approved false
      echo "janitor back to dry run"
      ;;
    *) die "usage: autopilot.sh janitor [scan|approve|revoke]" ;;
  esac
}

cmd_reset() {
  [ "${1:-}" = "pr" ] && [ -n "${2:-}" ] || die "usage: autopilot.sh reset pr NUMBER"
  state set "prs.$2" '{}'
  echo "retry budgets of PR #$2 cleared"
}

usage() {
  cat <<EOF
usage: autopilot.sh COMMAND

  tick                  run one tick (AUTOPILOT_DRY_RUN=1 prints the plan and changes nothing)
  status                state summary and launchd status
  logs [N]              last N lines of the tick log
  install | uninstall   load or remove the launchd agent $AP_LABEL
  janitor [scan|approve|revoke]
                        list removable worktrees and branches, or let ticks remove them
  pause | resume        stop or restart ticks without unloading launchd
  reset pr NUMBER       clear the retry budgets of a pull request
EOF
}

main() {
  local command="${1:-}"
  [ "$#" -gt 0 ] && shift
  case "$command" in
    tick) cmd_tick ;;
    run-job) cmd_run_job "$@" ;;
    status) cmd_status ;;
    logs) cmd_logs "$@" ;;
    install) cmd_install ;;
    uninstall) cmd_uninstall ;;
    janitor) cmd_janitor "$@" ;;
    reset) cmd_reset "$@" ;;
    pause)
      mkdir -p "$AP_HOME"
      touch "$AP_HOME/PAUSE"
      echo "paused"
      ;;
    resume)
      rm -f "$AP_HOME/PAUSE"
      echo "resumed"
      ;;
    *)
      usage
      [ -z "$command" ] || [ "$command" = "help" ] || exit 2
      ;;
  esac
}

main "$@"
