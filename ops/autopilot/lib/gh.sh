# shellcheck shell=bash
# GitHub and git helpers for autopilot.sh (sourced, bash 3.2 compatible).
#
# Reads use the default gh login. Every write goes through gh_bot, which uses CLAUDE_GH_TOKEN
# so pull requests, labels and comments belong to the bot account. The collect_* functions only
# read; they fill "$TICK_TMP" with the files lib/plan.py turns into a plan.

AP_PUSH_WORKFLOWS="${AUTOPILOT_PUSH_WORKFLOWS:-CI|Test|Deploy Docs|GitPM Sync}"
AP_NIGHTLY_WORKFLOWS="${AUTOPILOT_NIGHTLY_WORKFLOWS:-Load Test|Demo|Scheduled Health Agent}"
AP_LABELS="ai-approved ai-changes-requested needs-human ap:in-progress ap:in-review ap:done"
AP_PR_FIELDS="number,title,author,baseRefName,headRefName,headRefOid,isDraft,mergeable,reviewDecision,labels,body,statusCheckRollup,url"
# Wall-clock limit of one gh or git network call. Under launchd nobody can answer a prompt
# and a stalled call would hold the tick lock for good, so every such call is bounded.
AP_NET_SECONDS="${AUTOPILOT_NET_SECONDS:-120}"

gh_ro() {
  with_alarm "$AP_NET_SECONDS" gh "$@"
}

gh_bot() {
  if [ -z "${CLAUDE_GH_TOKEN:-}" ]; then
    log "CLAUDE_GH_TOKEN is not set: refusing to write to GitHub under another identity"
    return 1
  fi
  # A subshell, so the token is in the environment of this one call only.
  (
    export GH_TOKEN="$CLAUDE_GH_TOKEN"
    with_alarm "$AP_NET_SECONDS" gh "$@"
  )
}

# net_git ARGS...: git against the remote, bounded like the gh calls.
net_git() {
  with_alarm "$AP_NET_SECONDS" git "$@"
}

# pr_head PR: print the head commit of a pull request as GitHub has it now.
pr_head() {
  gh_ro pr view "$1" -R "$AP_GH_REPO" --json headRefOid --jq .headRefOid 2>/dev/null || true
}

# repo_slug: print owner/name of the origin remote.
repo_slug() {
  if [ -n "${AUTOPILOT_GH_REPO:-}" ]; then
    echo "$AUTOPILOT_GH_REPO"
    return 0
  fi
  git -C "$AP_REPO" remote get-url origin |
    sed -E -e 's#^(git@|ssh://git@|https://)github\.com[:/]##' -e 's#\.git$##'
}

# bot_login: print the login the autopilot acts as ("" when it cannot be found).
bot_login() {
  if [ -n "${AUTOPILOT_BOT_LOGIN:-}" ]; then
    echo "$AUTOPILOT_BOT_LOGIN"
  elif [ -n "${CLAUDE_GH_TOKEN:-}" ]; then
    gh_bot api user --jq .login 2>/dev/null || true
  fi
}

# mem_free_gb: print free + inactive + speculative memory in GB ("" off macOS).
mem_free_gb() {
  command -v vm_stat >/dev/null 2>&1 || return 0
  vm_stat | awk '
    /page size of/ { size = $8 }
    /^Pages free/ { free = $3 }
    /^Pages inactive/ { inactive = $3 }
    /^Pages speculative/ { speculative = $3 }
    END { if (size) printf "%.1f", (free + inactive + speculative) * size / 1073741824 }'
}

# safe_name TEXT: make a string usable as a file name.
safe_name() {
  printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '-'
}

collect_prs() {
  gh_ro pr list -R "$AP_GH_REPO" --state open --limit 100 --json "$AP_PR_FIELDS" >"$TICK_TMP/prs.json"
}

# collect_runs: the last runs of each watched workflow. Push workflows are read on develop;
# scheduled ones run on the default branch, so they are read by event only.
collect_runs() {
  local workflow fields="databaseId,status,conclusion,workflowName,url,headSha,createdAt"
  mkdir -p "$TICK_TMP/runs/push" "$TICK_TMP/runs/nightly"
  printf '%s\n' "$AP_PUSH_WORKFLOWS" | tr '|' '\n' | while read -r workflow; do
    [ -n "$workflow" ] || continue
    gh_ro run list -R "$AP_GH_REPO" --workflow "$workflow" --branch develop --event push \
      --limit 5 --json "$fields" >"$TICK_TMP/runs/push/$(safe_name "$workflow").json" 2>/dev/null ||
      log "  .. no push runs readable for workflow '$workflow'"
  done
  printf '%s\n' "$AP_NIGHTLY_WORKFLOWS" | tr '|' '\n' | while read -r workflow; do
    [ -n "$workflow" ] || continue
    gh_ro run list -R "$AP_GH_REPO" --workflow "$workflow" --event schedule \
      --limit 5 --json "$fields" >"$TICK_TMP/runs/nightly/$(safe_name "$workflow").json" 2>/dev/null ||
      log "  .. no scheduled runs readable for workflow '$workflow'"
  done
}

# collect_epics: epic branches, the story PRs merged into each, and how far open story PRs
# are behind their epic branch.
collect_epics() {
  local branch slug number base head
  mkdir -p "$TICK_TMP/merged"
  gh_ro api "repos/$AP_GH_REPO/git/matching-refs/heads/epic/" \
    --jq '.[].ref | sub("^refs/heads/"; "")' >"$TICK_TMP/epic-branches.txt"
  while read -r branch; do
    [ -n "$branch" ] || continue
    slug="${branch#epic/}"
    gh_ro pr list -R "$AP_GH_REPO" --state merged --base "$branch" --limit 300 \
      --json number,body,headRefName >"$TICK_TMP/merged/$slug.json"
  done <"$TICK_TMP/epic-branches.txt"
  : >"$TICK_TMP/behind.tsv"
  jq -r '.[] | select(.baseRefName | startswith("epic/")) | [.number, .baseRefName, .headRefName] | @tsv' \
    "$TICK_TMP/prs.json" >"$TICK_TMP/story-prs.tsv"
  while IFS="$(printf '\t')" read -r number base head; do
    [ -n "$number" ] || continue
    printf '%s\t%s\n' "$number" \
      "$(gh_ro api "repos/$AP_GH_REPO/compare/$base...$head" --jq .behind_by 2>/dev/null || true)" \
      >>"$TICK_TMP/behind.tsv"
  done <"$TICK_TMP/story-prs.tsv"
}

collect_issues() {
  gh_ro issue list -R "$AP_GH_REPO" --state open --label needs-human --limit 200 \
    --json number --jq '[.[].number]' >"$TICK_TMP/needs-human.json"
}

# collect_meta: snapshot .meta from origin/develop, and each epic's own directory from its
# epic branch when that branch is known locally. Nothing is checked out.
collect_meta() {
  local branch slug
  mkdir -p "$TICK_TMP/meta/develop" "$TICK_TMP/meta/epics"
  git -C "$AP_REPO" archive origin/develop .meta | tar -x -C "$TICK_TMP/meta/develop" --strip-components 1
  while read -r branch; do
    [ -n "$branch" ] || continue
    slug="${branch#epic/}"
    if git -C "$AP_REPO" rev-parse -q --verify "origin/$branch^{commit}" >/dev/null 2>&1 &&
      git -C "$AP_REPO" cat-file -e "origin/$branch:.meta/epics/$slug/epic.md" 2>/dev/null; then
      mkdir -p "$TICK_TMP/meta/epics/$slug"
      git -C "$AP_REPO" archive "origin/$branch" ".meta/epics/$slug" |
        tar -x -C "$TICK_TMP/meta/epics/$slug" --strip-components 1
    else
      log "  .. $branch is not fetched here; reading its stories from origin/develop"
    fi
  done <"$TICK_TMP/epic-branches.txt"
}

# collect_env: the scalars the planner needs, as env.json.
collect_env() {
  local memory digest_hour="${AUTOPILOT_DIGEST_HOUR:-8}"
  memory="$(mem_free_gb)"
  jq -n \
    --argjson now "$(date +%s)" \
    --argjson limit "$DEV_AGENT_LIMIT" \
    --argjson pool "$AP_POOL" \
    --argjson max_epics "${AUTOPILOT_MAX_EPICS:-2}" \
    --argjson digest_hour "$digest_hour" \
    --arg memory "$memory" \
    --arg bot "$AP_BOT" \
    --arg epic_allow "${AUTOPILOT_EPICS:-}" \
    --arg pr_scope "${AUTOPILOT_PR_SCOPE:-all}" \
    --arg state_file "$AP_STATE_FILE" \
    '{now: $now, limit: $limit, pool: $pool, max_epics: $max_epics, digest_hour: $digest_hour,
      mem_free_gb: (if $memory == "" then null else ($memory | tonumber) end),
      bot: $bot, epic_allow: $epic_allow, pr_scope: $pr_scope, state_file: $state_file}' \
    >"$TICK_TMP/env.json"
}

# missing_labels: print the labels of the label machine that the repository lacks.
missing_labels() {
  local have label
  have="$(gh_ro label list -R "$AP_GH_REPO" --limit 300 --json name --jq '.[].name' 2>/dev/null || true)"
  for label in $AP_LABELS; do
    printf '%s\n' "$have" | grep -qxF "$label" || printf '%s ' "$label"
  done
}

# label_add NUMBER LABEL / label_drop NUMBER LABEL: one label on an issue or a pull request.
# Both go through the REST issues endpoint, where a pull request is an issue: `gh pr edit`
# needs token scopes that `gh issue edit` does not, and the bot token may lack them.
label_add() {
  gh_bot api -X POST "repos/$AP_GH_REPO/issues/$1/labels" -f "labels[]=$2" --silent
}

label_drop() {
  local label="${2//:/%3A}"
  gh_bot api -X DELETE "repos/$AP_GH_REPO/issues/$1/labels/${label// /%20}" --silent >/dev/null 2>&1 || true
}

# label_swap KIND NUMBER ADD [REMOVE...]: add one label and drop others on an issue or PR.
# A failure is reported with GitHub's answer, never fatal.
label_swap() {
  local kind="$1" number="$2" add="$3" label err
  shift 3
  err="$(label_add "$number" "$add" 2>&1)" ||
    log "  !! could not add label $add to $kind #$number: $(printf '%s\n' "$err" | head -1)"
  for label in "$@"; do
    label_drop "$number" "$label"
  done
}

# issue_stage ISSUE STAGE: move a story issue to ap:in-progress, ap:in-review or ap:done.
issue_stage() {
  local issue="$1" stage="$2" other others=""
  [ -n "$issue" ] || return 0
  for other in ap:in-progress ap:in-review ap:done; do
    [ "$other" = "$stage" ] || others="$others $other"
  done
  # shellcheck disable=SC2086  # the label names hold no spaces; one argument each is intended
  label_swap issue "$issue" "$stage" $others
}
