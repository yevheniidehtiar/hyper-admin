#!/usr/bin/env bash
# Docker HEALTHCHECK script for the conductor container.
# Returns 0 (healthy) if the supervisor is alive and responsive.
# Returns 1 (unhealthy) if stale or dead — triggers Docker restart policy.

set -euo pipefail

STATUS_FILE="/run/conductor/status.json"
STALE_THRESHOLD="${HEALTHCHECK_STALE_SECONDS:-600}"  # 10 minutes

# Status file must exist
if [[ ! -f "$STATUS_FILE" ]]; then
  echo "UNHEALTHY: no status file"
  exit 1
fi

state=$(jq -r '.state // "unknown"' "$STATUS_FILE")
last_heartbeat=$(jq -r '.last_heartbeat // 0' "$STATUS_FILE")
pid=$(jq -r '.pid // 0' "$STATUS_FILE")
now=$(date +%s)
age=$(( now - last_heartbeat ))

# Check supervisor process is alive
if [[ "$pid" -gt 0 ]] && ! kill -0 "$pid" 2>/dev/null; then
  echo "UNHEALTHY: supervisor pid $pid is dead"
  exit 1
fi

# Check heartbeat freshness
if [[ $age -gt $STALE_THRESHOLD ]]; then
  echo "UNHEALTHY: last heartbeat ${age}s ago (threshold ${STALE_THRESHOLD}s)"
  exit 1
fi

# "needs-human" is a valid state — container is alive but waiting
# "error" is transient — supervisor will retry or exit
# Both are "healthy" from Docker's perspective (don't restart)
case "$state" in
  running|completed|starting|needs-human)
    echo "HEALTHY: state=$state, heartbeat=${age}s ago"
    exit 0
    ;;
  error)
    # Only unhealthy if also stale — transient errors self-recover
    if [[ $age -gt 120 ]]; then
      echo "UNHEALTHY: error state for ${age}s"
      exit 1
    fi
    echo "HEALTHY: transient error, heartbeat=${age}s ago"
    exit 0
    ;;
  *)
    echo "UNHEALTHY: unknown state '$state'"
    exit 1
    ;;
esac
