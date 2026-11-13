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
#   RUN_TIME    Locust run time per run            (default 90s)
#   USERS       concurrent users                   (default 20)
#   SPAWN_RATE  users spawned per second           (default 5)
#   SEED_COUNT  rows to seed                       (default 1000)
#   PORT        app port                           (default 8000)
#   LOCUSTFILE  locustfile to run                  (default: the checkout's own)
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
RUN_TIME="${RUN_TIME:-90s}"
USERS="${USERS:-20}"
SPAWN_RATE="${SPAWN_RATE:-5}"
SEED_COUNT="${SEED_COUNT:-1000}"
PORT="${PORT:-8000}"
FIRST_RUN="${FIRST_RUN:-1}"
HOST="http://127.0.0.1:${PORT}"

# The locustfile defaults to the checkout's own; CI passes head's for both sides so they run the
# same workload. LOCUSTFILE must be an absolute path or relative to the checkout.
LOCUSTFILE="${LOCUSTFILE:-examples/erp/loadtest/locustfile.py}"

port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null; }

cd "$CHECKOUT"
if port_busy; then
  echo "port ${PORT} is already in use, refusing to measure a stale app" >&2
  exit 1
fi
rm -f erp.db erp.db-wal erp.db-shm

# Job control gives the background app its own process group, so cleanup kills uvicorn and any
# wrapper (uv) together instead of leaving an orphan on the port.
set -m
APP_PID=""
cleanup() {
  set +m  # no "Terminated" job notice; the group kill below only needs the pgid
  if [ -n "$APP_PID" ]; then
    kill -TERM -- "-$APP_PID" 2>/dev/null || kill "$APP_PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$APP_PID" 2>/dev/null || break
      sleep 0.5
    done
    kill -KILL -- "-$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
    for _ in $(seq 1 20); do
      port_busy || break
      sleep 0.5
    done
  fi
}
trap cleanup EXIT

if [ -x .venv/bin/uvicorn ]; then
  UVICORN=(.venv/bin/uvicorn)
else
  UVICORN=(uv run uvicorn)
fi
HYPERADMIN_SECRET_KEY="${HYPERADMIN_SECRET_KEY:-loadtest-ci}" \
  "${UVICORN[@]}" examples.erp.main:app --host 127.0.0.1 --port "$PORT" \
  > "$OUT/app-${FIRST_RUN}.log" 2>&1 &
APP_PID=$!

# Wait for the lifespan (schema + admin + demo seed) to finish; fail fast if the app dies.
ready=0
for _ in $(seq 1 60); do
  if ! kill -0 "$APP_PID" 2>/dev/null; then
    echo "app exited during startup, see $OUT/app-${FIRST_RUN}.log" >&2
    exit 1
  fi
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

# Top up to the requested row count for representative pagination/search behaviour. A failure
# here must fail the run: a differently sized dataset on one side fakes a regression.
uv run hyperadmin seed --count "$SEED_COUNT" --database-url "sqlite:///erp.db" --no-progress

export LOADTEST_USER="${LOADTEST_USER:-admin}" LOADTEST_PASSWORD="${LOADTEST_PASSWORD:-admin}"
export LOADTEST_MAX_ID="${LOADTEST_MAX_ID:-80}"

for i in $(seq 0 $((N - 1))); do
  k=$((FIRST_RUN + i))
  echo "== ${CHECKOUT}: run ${k} (${RUN_TIME}, ${USERS} users) =="
  # Exit 0 even with failed requests: the compare step judges the error rate.
  uv run locust -f "$LOCUSTFILE" --host "$HOST" \
    --headless --users "$USERS" --spawn-rate "$SPAWN_RATE" --run-time "$RUN_TIME" \
    --reset-stats --exit-code-on-error 0 --csv "$OUT/run${k}" --only-summary
  if [ ! -s "$OUT/run${k}_stats.csv" ]; then
    echo "locust produced no $OUT/run${k}_stats.csv" >&2
    exit 1
  fi
done
