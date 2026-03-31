#!/usr/bin/env bash
# Conductor supervisor — runs the conductor agent in a loop,
# restarts on completion, pauses on "needs-human", exits on fatal error.
#
# Status file protocol (/run/conductor/status.json):
#   state: running | completed | needs-human | error | starting
#   cycle: current cycle number
#   last_heartbeat: epoch timestamp
#   message: human-readable status
#   session_id: claude session ID for resume

set -euo pipefail

STATUS_FILE="/run/conductor/status.json"
LOG_DIR="/run/conductor/logs"
mkdir -p "$LOG_DIR"

CYCLE=0
MAX_CYCLES="${CONDUCTOR_MAX_CYCLES:-9}"
COOLDOWN="${CONDUCTOR_COOLDOWN:-300}"
HUMAN_POLL="${CONDUCTOR_HUMAN_POLL:-600}"
MAX_BUDGET="${CONDUCTOR_MAX_BUDGET:-20.00}"
MAX_TURNS="${CONDUCTOR_MAX_TURNS:-50}"
WEBHOOK_URL="${CONDUCTOR_WEBHOOK_URL:-}"
STARTED_AT=""

# --- helpers ---

json_escape() {
  python3 -c "import json,sys; print(json.dumps(sys.stdin.read().strip()))" <<< "$1"
}

write_status() {
  local state="$1" message="$2" session_id="${3:-}"
  local escaped_msg
  escaped_msg=$(json_escape "$message")
  cat > "$STATUS_FILE" <<EOF
{
  "state": "$state",
  "cycle": $CYCLE,
  "last_heartbeat": $(date +%s),
  "message": $escaped_msg,
  "session_id": "$session_id",
  "started_at": "${STARTED_AT}",
  "pid": $$
}
EOF
}

notify() {
  local message="$1" level="${2:-info}"
  echo "[$(date -Iseconds)] [$level] $message"

  if [[ -n "$WEBHOOK_URL" ]]; then
    local payload
    payload=$(python3 -c "
import json, sys
print(json.dumps({
    'text': f'conductor ({sys.argv[2]}): {sys.argv[1]}',
    'level': sys.argv[2],
    'cycle': int(sys.argv[3])
}))" "$message" "$level" "$CYCLE")
    curl -sf -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -d "$payload" 2>/dev/null || true
  fi
}

# Sleep in small increments so the heartbeat stays fresh for the health check.
# Writes a status update every 30s during the wait.
sleep_with_heartbeat() {
  local total="$1" state="$2" message="$3"
  local elapsed=0 step=30
  while [[ $elapsed -lt $total ]]; do
    local remaining=$((total - elapsed))
    local chunk=$(( remaining < step ? remaining : step ))
    sleep "$chunk"
    elapsed=$((elapsed + chunk))
    write_status "$state" "$message (${elapsed}/${total}s)"
  done
}

check_prerequisites() {
  local missing=()
  [[ -z "${ANTHROPIC_API_KEY:-}" ]] && missing+=("ANTHROPIC_API_KEY")
  [[ -z "${CLAUDE_GH_TOKEN:-}" ]]   && missing+=("CLAUDE_GH_TOKEN")

  if [[ ${#missing[@]} -gt 0 ]]; then
    write_status "error" "Missing env vars: ${missing[*]}"
    notify "Missing required env vars: ${missing[*]}" "error"
    exit 1
  fi

  if ! command -v claude &>/dev/null; then
    write_status "error" "claude CLI not found"
    notify "claude CLI not found in PATH" "error"
    exit 1
  fi

  if [[ ! -d "/workspace/.git" ]]; then
    write_status "error" "No git repo at /workspace"
    notify "No git repo mounted at /workspace" "error"
    exit 1
  fi
}

run_cycle() {
  CYCLE=$((CYCLE + 1))
  local log_file="$LOG_DIR/cycle-${CYCLE}.json"

  write_status "running" "Cycle $CYCLE starting" ""
  notify "Cycle $CYCLE/$MAX_CYCLES starting"

  cd /workspace
  git fetch origin develop 2>/dev/null || true
  git checkout develop 2>/dev/null || true
  git pull origin develop 2>/dev/null || true

  local exit_code=0
  claude -p "/run-autonomous-team" \
    --output-format json \
    --max-turns "$MAX_TURNS" \
    --max-budget-usd "$MAX_BUDGET" \
    --permission-mode plan \
    > "$log_file" 2>&1 || exit_code=$?

  local session_id=""
  local result=""
  if [[ -f "$log_file" ]]; then
    session_id=$(jq -r '.session_id // empty' "$log_file" 2>/dev/null || true)
    result=$(jq -r '.result // empty' "$log_file" 2>/dev/null || true)
  fi

  if [[ $exit_code -eq 0 ]]; then
    if echo "$result" | grep -qiE "needs-human|needs.human|STOP.*user|blocked.*human|cannot.continue"; then
      write_status "needs-human" "Cycle $CYCLE halted — needs human input" "$session_id"
      notify "Cycle $CYCLE needs human intervention: $(echo "$result" | head -c 200)" "warn"
      return 2
    fi

    write_status "completed" "Cycle $CYCLE completed successfully" "$session_id"
    notify "Cycle $CYCLE completed"
    return 0
  else
    write_status "error" "Cycle $CYCLE failed (exit $exit_code)" "$session_id"
    notify "Cycle $CYCLE failed with exit code $exit_code" "error"
    return 1
  fi
}

wait_for_human() {
  notify "Waiting for human input (polling every ${HUMAN_POLL}s)" "warn"
  local wait_count=0
  local max_waits=12  # 12 * 10min = 2 hours max wait

  while [[ $wait_count -lt $max_waits ]]; do
    sleep_with_heartbeat "$HUMAN_POLL" "needs-human" "Waiting for human ($((wait_count + 1))/$max_waits)"
    wait_count=$((wait_count + 1))

    # Check if human resolved blockers (issues with in-progress but no blocked label)
    local unblocked
    unblocked=$(cd /workspace && GH_TOKEN="$CLAUDE_GH_TOKEN" gh issue list \
      --label "in-progress" --state open \
      --json number,labels \
      --jq '[.[] | select([.labels[].name] | index("blocked") | not)] | length' 2>/dev/null || echo "0")

    if [[ "$unblocked" -gt 0 ]]; then
      notify "Detected unblocked issues — resuming" "info"
      return 0
    fi
  done

  notify "Max human wait exceeded (${max_waits} polls). Stopping." "error"
  write_status "error" "Timed out waiting for human input"
  return 1
}

# --- Main loop ---

STARTED_AT=$(date -Iseconds)
check_prerequisites
write_status "starting" "Supervisor starting, max $MAX_CYCLES cycles"
notify "Conductor supervisor started (max $MAX_CYCLES cycles, cooldown ${COOLDOWN}s)"

while [[ $CYCLE -lt $MAX_CYCLES ]]; do
  cycle_result=0
  run_cycle || cycle_result=$?

  case $cycle_result in
    0)
      if [[ $CYCLE -lt $MAX_CYCLES ]]; then
        sleep_with_heartbeat "$COOLDOWN" "completed" "Cooling down before cycle $((CYCLE + 1))"
      fi
      ;;
    1)
      notify "Backing off 60s after error" "warn"
      sleep_with_heartbeat 60 "error" "Backing off after cycle $CYCLE error"
      ;;
    2)
      wait_for_human || exit 1
      ;;
  esac
done

write_status "completed" "All $MAX_CYCLES cycles finished"
notify "Conductor finished all $MAX_CYCLES cycles" "info"
exit 0
