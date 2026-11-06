#!/usr/bin/env bash
# Run the ERP load test across a matrix of database x app CPUs x users x realtime backend.
#
#   ./scripts/loadtest_matrix.sh                 # default matrix (about an hour)
#   ./scripts/loadtest_matrix.sh pg-4cpu-400u    # only the named rows
#   RUN_TIME=5m ./scripts/loadtest_matrix.sh     # longer measurement window per row
#
# Needs Docker and `uv sync --all-extras`. The app runs in Docker with a hard CPU limit and one
# uvicorn worker per CPU; PostgreSQL (2 CPUs) and Redis run beside it. Locust runs on the host
# so it never competes with the app for the limited CPUs. Both databases are seeded once with
# SEED_ROWS rows and reused by every row of the matrix.
#
# Per-row Locust CSVs land in reports/loadtest-matrix/<row>/ and the summary table in
# reports/loadtest-matrix/summary.md (scripts/loadtest_matrix_report.py).

set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f docker-compose.loadtest-matrix.yml)
OUT=reports/loadtest-matrix
RUN_TIME="${RUN_TIME:-3m}"
SEED_ROWS="${SEED_ROWS:-100000}"
PG_URL=postgresql://hyperadmin:hyperadmin@postgres:5432/erp
SQLITE_PATH=/data/erp.db

# Per-worker pool and back-pressure (see "Sizing" in docs/compatibility.md): each uvicorn worker
# keeps DB_POOL_SIZE + DB_MAX_OVERFLOW connections and answers 503 straight away once it has
# LIMIT_CONCURRENCY requests in flight, instead of queueing them until the pool times out.
export DB_POOL_SIZE="${DB_POOL_SIZE:-10}" DB_MAX_OVERFLOW="${DB_MAX_OVERFLOW:-10}"
export DB_POOL_TIMEOUT="${DB_POOL_TIMEOUT:-10}" LIMIT_CONCURRENCY="${LIMIT_CONCURRENCY:-100}"

# name | database | app CPUs | users | realtime backend (off, memory, redis)
# SQLite stays at one worker: several processes writing one SQLite file just lock each other.
MATRIX=(
  "sqlite-1cpu-200u  sqlite 1 200 off"
  "sqlite-1cpu-400u  sqlite 1 400 off"
  "pg-1cpu-200u      pg     1 200 off"
  "pg-2cpu-200u      pg     2 200 off"
  "pg-4cpu-200u      pg     4 200 off"
  "pg-6cpu-200u      pg     6 200 off"
  "pg-1cpu-400u      pg     1 400 off"
  "pg-2cpu-400u      pg     2 400 off"
  "pg-4cpu-400u      pg     4 400 off"
  "pg-6cpu-400u      pg     6 400 off"
  "pg-9cpu-400u      pg     9 400 off"
  "pg-9cpu-800u      pg     9 800 off"
  "pg-9cpu-1200u     pg     9 1200 off"
  "pg-9cpu-1600u     pg     9 1600 off"
  "pg-4cpu-400u-rt-memory pg 4 400 memory"
  "pg-4cpu-400u-rt-redis  pg 4 400 redis"
)

docker_cpus=$(docker info --format '{{.NCPU}}')

wait_for_app() {
  for _ in $(seq 1 90); do
    code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/admin/login || true)
    [ "$code" = "200" ] && return 0
    sleep 2
  done
  echo "app did not come up; last logs:" >&2
  "${COMPOSE[@]}" logs --no-color --tail 80 app >&2
  return 1
}

# start_app <database> <cpus> <realtime>
start_app() {
  local db=$1 cpus=$2 realtime=$3
  unset DATABASE_URL REDIS_URL
  if [ "$db" = pg ]; then
    export DATABASE_URL=$PG_URL
  else
    export DATABASE_URL="sqlite+aiosqlite:///$SQLITE_PATH"
  fi
  export APP_CPUS=$cpus APP_WORKERS=$cpus DEMO_REALTIME=0
  case $realtime in
    memory) DEMO_REALTIME=1 ;;
    redis) DEMO_REALTIME=1 && export REDIS_URL=redis://redis:6379/0 ;;
  esac
  "${COMPOSE[@]}" up -d --force-recreate --no-deps app >/dev/null
  wait_for_app
}

seed() {
  local db=$1 url
  url=$PG_URL
  [ "$db" = sqlite ] && url="sqlite:///$SQLITE_PATH"
  echo "== seeding $db with $SEED_ROWS rows"
  start_app "$db" 1 off
  "${COMPOSE[@]}" exec -T app uv run --no-sync hyperadmin seed --count "$SEED_ROWS" \
    --database-url "$url" --no-progress
}

selected=("$@")
rows=()
for row in "${MATRIX[@]}"; do
  read -r name db cpus users realtime <<<"$row"
  if [ ${#selected[@]} -gt 0 ] && [[ ! " ${selected[*]} " == *" $name "* ]]; then
    continue
  fi
  if [ "$cpus" -gt "$docker_cpus" ]; then
    echo "skip $name: needs $cpus Docker CPUs, Docker has $docker_cpus"
    continue
  fi
  if [ "$db" = pg ] && [ $((cpus + 2)) -gt "$docker_cpus" ]; then
    echo "note $name: app and PostgreSQL share CPUs ($cpus + 2 > $docker_cpus Docker CPUs)"
  fi
  rows+=("$row")
done

mkdir -p "$OUT"
"${COMPOSE[@]}" build app
"${COMPOSE[@]}" up -d --wait postgres redis

# watch_row <dir> <locust pid>: poll the app log while Locust runs and stop the row early once
# WATCH_PATTERN shows up WATCH_MAX times: the app is saturated (uvicorn turning requests away,
# the pool running dry, SQLite locking) and the rest of the run would only measure the overload.
# The reason lands in <dir>/aborted; Locust still writes its CSVs on SIGTERM.
watch_row() {
  local dir=$1 pid=$2 hits
  while kill -0 "$pid" 2>/dev/null; do
    sleep "$WATCH_INTERVAL"
    hits=$("${COMPOSE[@]}" logs --no-color app 2>/dev/null | grep -o -E "$WATCH_PATTERN" | sort | uniq -c | sort -rn | head -1 || true)
    if [ -n "$hits" ] && [ "$(awk '{print $1}' <<<"$hits")" -ge "$WATCH_MAX" ]; then
      echo "   stopping early: $hits"
      echo "$hits" | sed -E 's/^ *//' >"$dir/aborted"
      kill -TERM "$pid" 2>/dev/null || true
      return
    fi
  done
}

WATCH_PATTERN="${WATCH_PATTERN:-Exceeded concurrency limit|QueuePool limit|database is locked|Traceback}"
WATCH_MAX="${WATCH_MAX:-20}"
WATCH_INTERVAL="${WATCH_INTERVAL:-5}"

seeded=" "
saturated=" "
for row in "${rows[@]}"; do
  read -r name db cpus users realtime <<<"$row"
  # Once a setup is saturated at some user count, more users on the same setup only fail harder.
  if [[ "$saturated" == *" $db-$cpus-$realtime "* ]]; then
    echo "skip $name: $db with $cpus CPU and realtime=$realtime already saturated at fewer users"
    continue
  fi
  # SEED_ROWS=0 reuses the data already in the volumes (each seed adds rows, it does not reset).
  if [ "$SEED_ROWS" -gt 0 ] && [[ "$seeded" != *" $db "* ]]; then
    seed "$db"
    seeded+="$db "
  fi

  echo "== $name: $db, $cpus CPU, $users users, realtime=$realtime"
  start_app "$db" "$cpus" "$realtime"
  rm -rf "${OUT:?}/$name" && mkdir -p "$OUT/$name"
  printf '%s\n' "$db" "$cpus" "$users" "$realtime" "$RUN_TIME" > "$OUT/$name/params"

  spawn_rate=$((users / 20))
  # Each of the 4 Locust processes logs in 5 sessions and shares them among its users, so the
  # numbers measure admin pages, not password hashing. --reset-stats drops the ramp-up.
  LOADTEST_USER=admin LOADTEST_PASSWORD=admin LOADTEST_MAX_ID=5000 LOADTEST_LOGIN_SESSIONS=5 \
    uv run locust -f examples/erp/loadtest/locustfile.py \
    --host http://127.0.0.1:8000 --headless \
    --users "$users" --spawn-rate "$spawn_rate" --run-time "$RUN_TIME" \
    --processes 4 --reset-stats --only-summary \
    --csv "$OUT/$name/locust" >"$OUT/$name/locust.log" 2>&1 &
  locust_pid=$!
  watch_row "$OUT/$name" "$locust_pid"
  wait "$locust_pid" || true
  "${COMPOSE[@]}" logs --no-color app >"$OUT/$name/app.log" 2>&1
  [ -f "$OUT/$name/aborted" ] && saturated+="$db-$cpus-$realtime "
done

"${COMPOSE[@]}" down >/dev/null
uv run python scripts/loadtest_matrix_report.py "$OUT"
