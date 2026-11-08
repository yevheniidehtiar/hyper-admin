#!/usr/bin/env bash
# Run the SQLite ERP load test N times against one checkout and write run<K>_stats.csv files.
#
#   scripts/loadtest_repeat.sh <checkout-dir> <out-dir> <N>
#
# Starts the ERP example from <checkout-dir> on a fresh SQLite database, seeds it once, runs Locust
# headless N times against the same app instance (--reset-stats, no restart between runs) and
# stops the app. Needs `uv sync --all-extras` done in <checkout-dir>.
#
# Environment (all optional):
#   RUN_TIME    Locust run time per run            (default 30s)
#   USERS       concurrent users                   (default 10)
#   SPAWN_RATE  users spawned per second           (default 5)
#   SEED_COUNT  rows to seed                       (default 1000)
#   PORT        app port                           (default 8000)
#   FIRST_RUN   number of the first run file       (default 1); CI calls the script once per
#               iteration with N=1 and FIRST_RUN=<iteration> to alternate base and head.
#
# Then aggregate and compare, see examples/erp/loadtest/README.md.

set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <checkout-dir> <out-dir> <N>" >&2
  exit 2
fi

CHECKOUT=$(cd "$1" && pwd)
mkdir -p "$2"
OUT=$(cd "$2" && pwd)
N=$3
RUN_TIME="${RUN_TIME:-30s}"
USERS="${USERS:-10}"
SPAWN_RATE="${SPAWN_RATE:-5}"
SEED_COUNT="${SEED_COUNT:-1000}"
PORT="${PORT:-8000}"
FIRST_RUN="${FIRST_RUN:-1}"
HOST="http://127.0.0.1:${PORT}"

cd "$CHECKOUT"
rm -f erp.db
APP_PID=""
cleanup() {
  if [ -n "$APP_PID" ]; then
    kill "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

HYPERADMIN_SECRET_KEY="${HYPERADMIN_SECRET_KEY:-loadtest-ci}" \
  uv run uvicorn examples.erp.main:app --host 127.0.0.1 --port "$PORT" \
  > "$OUT/app-${FIRST_RUN}.log" 2>&1 &
APP_PID=$!

# Wait for the lifespan (schema + admin + demo seed) to finish.
ready=0
for _ in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$HOST/admin/login" || true)
  if [ "$code" = "200" ]; then
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" != 1 ]; then
  echo "app did not start within 120s, see $OUT/app-${FIRST_RUN}.log" >&2
  exit 1
fi

# Top up to the requested row count for representative pagination/search behaviour.
uv run hyperadmin seed --count "$SEED_COUNT" --database-url "sqlite:///erp.db" --no-progress || true

export LOADTEST_USER="${LOADTEST_USER:-admin}" LOADTEST_PASSWORD="${LOADTEST_PASSWORD:-admin}"
export LOADTEST_MAX_ID="${LOADTEST_MAX_ID:-80}"

for i in $(seq 0 $((N - 1))); do
  k=$((FIRST_RUN + i))
  echo "== ${CHECKOUT}: run ${k} (${RUN_TIME}, ${USERS} users) =="
  uv run locust -f examples/erp/loadtest/locustfile.py --host "$HOST" \
    --headless --users "$USERS" --spawn-rate "$SPAWN_RATE" --run-time "$RUN_TIME" \
    --reset-stats --csv "$OUT/run${k}" --only-summary
done
