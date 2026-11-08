# ERP load test and regression gate

Locust scenarios for the ERP example (`locustfile.py`) plus a CI gate that catches performance
regressions by comparing repeated runs of a PR's base and head.

## How the gate works

One short Locust run is too noisy to gate on, so the `smoke` job in
`.github/workflows/loadtest.yml`:

1. checks out the PR base and head into two directories and runs `uv sync` in each;
2. runs `scripts/loadtest_repeat.sh` for base, head, base, head, ... (N times each, default 5) on
   the same runner, so slow-runner periods hit both sides equally. Each iteration starts a fresh
   SQLite app, seeds 1000 rows and runs Locust headless for 30s;
3. aggregates each side into per-endpoint medians (with min/max spread) of req/s, p50, p95, p99,
   plus a pooled error rate (`baselines aggregate`);
4. compares head against base (`baselines compare`) and fails if, for an endpoint with enough
   requests, the median req/s drops or the median p95 or p99 rises by more than the tolerance
   (default 15%), or the head error rate exceeds 1%. Endpoints with fewer than 100 total requests
   on either side are skipped with a note.

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
`SEED_COUNT`, `PORT` and `FIRST_RUN`. The run files come from the checkout's own `locustfile.py`.

## Tuning

- `--tolerance` (relative, `0.15` is 15%): raise it if the gate flaps, lower it to be stricter.
- `--max-error-rate` (default `0.01`) and `--min-requests` (default `100`, total across runs).
- More runs (`runs` input or N) tighten the median more cheaply than a longer run time.

The original single-run comparison still works: `baselines --stats run_stats.csv [--update-baseline]`.

## Noise caveats

- Shared CI runners vary a lot. Medians over alternating runs reduce that, but do not remove it:
  expect a few percent of noise and widen the tolerance rather than rerunning until green.
- Rare endpoints (create, update, delete) get few requests in 30s and are skipped; the
  `Aggregated` row and high-traffic list/detail endpoints carry the signal.
- Base is the PR's base commit, not the merge base, so changes merged to the base after the PR
  branched also show up in the diff.
- If the PR changes the load test itself, base and head run different workloads.
- Absolute numbers are only meaningful within one run of the job.
