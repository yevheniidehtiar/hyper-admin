# shellcheck shell=bash
# State and lock helpers for autopilot.sh (sourced, bash 3.2 compatible).
#
# The JSON itself is only ever read and written by lib/state.py; the functions here wrap it
# and provide the single-instance tick lock. macOS has no flock, so the lock is a directory:
# mkdir is atomic and fails when the directory exists.

# state COMMAND [ARGS]: run one lib/state.py command against the state file.
state() {
  "$AP_PYTHON" "$AP_LIB/state.py" --state "$AP_STATE_FILE" "$@"
}

# state_value PATH: print one scalar from the state ("" when absent or null).
state_value() {
  state get "$1" | "$AP_PYTHON" -c 'import json, sys
value = json.load(sys.stdin)
print("" if value is None else (json.dumps(value) if isinstance(value, (dict, list, bool)) else value))'
}

# lock_acquire NAME: take the lock, or return 1 when a live process holds it.
# A lock whose owner is gone (crash, reboot) is taken over.
lock_acquire() {
  local dir="$AP_HOME/$1.lock.d" owner
  if mkdir "$dir" 2>/dev/null; then
    echo "$$" >"$dir/pid"
    return 0
  fi
  owner="$(cat "$dir/pid" 2>/dev/null || true)"
  if [ -n "$owner" ] && kill -0 "$owner" 2>/dev/null; then
    return 1
  fi
  rm -f "$dir/pid"
  rmdir "$dir" 2>/dev/null || return 1
  mkdir "$dir" 2>/dev/null || return 1
  echo "$$" >"$dir/pid"
}

# lock_release NAME: drop the lock if this process holds it.
lock_release() {
  local dir="$AP_HOME/$1.lock.d"
  if [ "$(cat "$dir/pid" 2>/dev/null || true)" = "$$" ]; then
    rm -f "$dir/pid"
    rmdir "$dir" 2>/dev/null || true
  fi
}

# paused: true when the owner has paused the autopilot (touch ~/.hyperadmin-autopilot/PAUSE).
paused() {
  [ -e "$AP_HOME/PAUSE" ]
}
