# ERP load test and regression gate

Locust scenarios for the ERP example (`locustfile.py`) plus a CI gate that catches performance
regressions by comparing repeated runs of a PR's base and head.

## How the gate works

One short Locust run is too noisy to gate on, so the `smoke` job in
`.github/workflows/loadtest.yml`:

1. checks out the PR base and head into two directories and runs `uv sync` in each;
2. runs `scripts/loadtest_repeat.sh` for base, head, base, head, ... (N times each, default 5) on
   the same runner, so slow-runner periods hit both sides equally. Each iteration starts a fresh
   SQLite app, seeds 1000 rows and runs Locust headless for 90s with 20 users (about 2.5 min per iteration, so ~10 iterations
   plus setup take 25-30 min; the job times out at 40);
3. aggregates each side into per-endpoint medians (with min/max spread) of req/s, p50, p95, p99,
   plus a pooled error rate (`baselines aggregate`);
4. compares head against base (`baselines compare`). It fails when, for an endpoint with enough
   pooled requests, the median p50 or p95 rises by more than the tolerance (default 15%)
   and by more than 20 ms in absolute terms (write endpoints, POST/PUT/PATCH/DELETE, gate on p50 only: their p95 swings on SQLite write-lock stalls); when the head error rate exceeds 1%; when an
   endpoint with enough base traffic vanishes from head or collapses below the pooled request
   minimum; or when either side has fewer than 3 usable runs. "Enough" means the total requests
   per side across all runs is at least 100 (about 20 per run over 5 runs), so one thin run does
   not exclude an endpoint. Endpoints below the pooled minimum are skipped with a note showing
   the pooled counts, and a zero base metric (Locust "N/A") is noted, not compared.

req/s and p99 are shown in the table but never gate: the scenario has think time
(`wait_time = between(0.5, 2.0)`), so load is closed-loop and req/s barely moves with latency (a
latency regression would otherwise be counted two or three times); p99 over a few dozen requests
per run is one slow request. The `Aggregated` row pools every request of the whole task mix, the
most stable signal, so its p50 and p95 gate with the same tolerance and absolute floor as the
other rows (its req/s and p99 stay informational). Both sides run head's `examples/erp/loadtest/` (CI copies it over
base), so editing the locustfile does not change the workload between sides.

The markdown table goes to the job summary and to `report.md` in the `locust-smoke-report`
artifact, next to every run's CSV. Dispatch the workflow manually to change `runs` and `tolerance`.

The nightly PostgreSQL job runs Locust 3 times and uploads the aggregate. It compares against
`baselines/nightly-postgres.json` only when that file exists; to enable it, commit the
`nightly-postgres.json` from a nightly run's artifact.

## Run it locally

Both checkouts need `uv sync --all-extras`. Alternate manually, one run per call, so drift is shared:

```bash
for i in 1 2 3; do
  FIRST_RUN=$i scripts/loadtest_repeat.sh ../base-checkout out/base 1
  FIRST_RUN=$i scripts/loadtest_repeat.sh .               out/head 1
done

uv run python -m examples.erp.loadtest.baselines aggregate --stats out/base/run*_stats.csv --out out/base.json
uv run python -m examples.erp.loadtest.baselines aggregate --stats out/head/run*_stats.csv --out out/head.json
uv run python -m examples.erp.loadtest.baselines compare --base out/base.json --head out/head.json --tolerance 0.15
```

`scripts/loadtest_repeat.sh <checkout> <out-dir> <N>` runs N times against one app instance and
writes `run1_stats.csv` to `runN_stats.csv`. Tune it with `RUN_TIME`, `USERS`, `SPAWN_RATE`,
`SEED_COUNT`, `PORT`, `LOCUSTFILE` and `FIRST_RUN`. The script refuses to start when the port is
taken, runs the app in its own process group (killed on exit), fails when the app dies or the seed
fails, and does not fail on failed requests (the compare step judges errors).

## Tuning

- `--tolerance` (relative, `0.15` is 15%): raise it if the gate flaps, lower it to be stricter.
- `--max-error-rate` (default `0.01`), `--min-requests` (default `100`, total per side across all runs), `--min-runs`
  (default `3`) and `--min-delta-ms` (default `20`, the absolute floor under which a rise is
  ignored however large the ratio).
- More runs (`runs` input or N) tighten the median more cheaply than a longer run time.

The original single-run comparison still works: `baselines --stats run_stats.csv [--update-baseline]`.

## Noise caveats

- Shared CI runners vary a lot. Medians over alternating runs reduce that, but do not remove it:
  expect a few percent of noise and widen the tolerance rather than rerunning until green.
- Rare endpoints (create, update, delete) may still get too few pooled requests and are skipped; the
  `Aggregated` row and high-traffic list/detail endpoints carry the signal.
- Head is checked out at the PR head commit and base at the PR base commit, so changes merged to
  the base after the PR branched also show up in the diff.
- Absolute numbers are only meaningful within one run of the job.
