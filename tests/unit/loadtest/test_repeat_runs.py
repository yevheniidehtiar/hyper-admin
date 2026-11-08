"""Unit tests for the repeated-run aggregate/compare regression gate."""

from pathlib import Path

import pytest
from examples.erp.loadtest import baselines as bl
from examples.erp.loadtest import repeat_runs as rr

from tests.unit.loadtest.test_baselines import _csv, _row

EP = "GET /admin/contact [list]"


def _run(rps=10.0, p50=10, p95=100, p99=120, count=500, failures=0, name=EP):
    text = _csv(_row(name, count=count, failures=failures, p50=p50, p95=p95, p99=p99, rps=rps))
    return bl.parse_locust_stats(text)


def _agg(**kwargs):
    return rr.aggregate_runs([_run(**kwargs) for _ in range(3)])


class TestAggregate:
    def test_median_and_spread(self):
        agg = rr.aggregate_runs([_run(p95=90), _run(p95=100), _run(p95=3000)])[EP]
        assert agg.runs == 3
        assert agg.requests == 1500
        assert (agg.p95.median, agg.p95.low, agg.p95.high) == (100, 90, 3000)

    def test_pooled_error_rate_and_missing_endpoint(self):
        runs = [_run(count=100, failures=10), _run(count=300, failures=0), {}]
        agg = rr.aggregate_runs(runs)[EP]
        assert agg.runs == 2
        assert agg.error_rate == pytest.approx(10 / 400)

    def test_json_roundtrip(self, tmp_path: Path):
        agg = _agg()
        path = tmp_path / "sub" / "agg.json"
        rr.dump_aggregate(path, agg)
        assert rr.load_aggregate(path) == agg


def _agg_of(*per_run, name=EP):
    """Aggregate with one run per kwargs dict, so a single run can be an outlier."""
    return rr.aggregate_runs([_run(name=name, **kw) for kw in per_run])


def _same(n=3, name=EP, **kw):
    return _agg_of(*([kw] * n), name=name)


class TestCompare:
    def test_within_tolerance_passes(self):
        cmp = rr.compare_aggregates(_agg(), _agg(rps=9.0, p95=110, p99=130), tolerance=0.15)
        assert cmp.findings == []
        assert cmp.rows[0][3] == "OK"

    def test_synthetic_regression_fails(self):
        cmp = rr.compare_aggregates(_agg(p50=100, p95=1000), _agg(p50=200, p95=1500))
        assert {f.kind for f in cmp.findings} == {"p50", "p95"}
        assert cmp.rows[0][3] == "REGRESSED p50, p95"

    def test_improvement_passes(self):
        cmp = rr.compare_aggregates(_agg(), _agg(rps=20.0, p95=50, p99=60))
        assert cmp.findings == []

    def test_tolerance_is_configurable(self):
        base, head = _same(p95=1000), _same(p95=1100)
        assert rr.compare_aggregates(base, head, tolerance=0.05).findings
        assert not rr.compare_aggregates(base, head, tolerance=0.15).findings

    @pytest.mark.parametrize("metric", ["p50", "p95"])
    @pytest.mark.parametrize(("head_value", "regressed"), [(1140, False), (1160, True)])
    def test_latency_tolerance_boundary(self, metric, head_value, regressed):
        """
        Scenario: a rise just inside the tolerance passes, just outside fails
          Given a base median of 1000 ms and a 15% tolerance
          When  head's median is 1140 ms or 1160 ms
          Then  only 1160 ms is a finding, for exactly that metric
        """
        base = _same(**{metric: 1000})
        head = _same(**{metric: head_value})
        cmp = rr.compare_aggregates(base, head, tolerance=0.15)
        assert [f.kind for f in cmp.findings] == ([metric] if regressed else [])

    def test_exactly_at_limit_passes(self):
        cmp = rr.compare_aggregates(_same(p95=1000), _same(p95=1150), tolerance=0.15)
        assert cmp.findings == []

    def test_p99_and_rps_are_informational(self):
        cmp = rr.compare_aggregates(_same(), _same(rps=1.0, p99=5000))
        assert cmp.findings == []
        assert cmp.rows[0][3] == "OK"

    def test_absolute_delta_floor_ignores_tiny_latencies(self):
        base, head = _same(p95=10), _same(p95=19)  # +90% but 9 ms
        assert not rr.compare_aggregates(base, head, min_delta_ms=20).findings
        assert rr.compare_aggregates(base, head, min_delta_ms=5).findings

    def test_median_not_mean_or_first_run(self):
        """
        Scenario: one outlier run does not move the verdict
          Given base runs of p95 1000 ms and head runs of 1000, 1000 and 9000 ms
          Then  head's median is unchanged and there is no finding
          And   two slow runs out of three do fail
        """
        base = _same(p95=1000)
        assert not rr.compare_aggregates(
            base, _agg_of({"p95": 9000}, {"p95": 1000}, {"p95": 1000})
        ).findings
        slow = _agg_of({"p95": 1000}, {"p95": 2000}, {"p95": 2000})
        assert [f.kind for f in rr.compare_aggregates(base, slow).findings] == ["p95"]

    def test_error_rate_over_max_fails(self):
        cmp = rr.compare_aggregates(_agg(), _agg(failures=50), max_error_rate=0.01)
        assert [f.kind for f in cmp.findings] == ["error_rate"]

    def test_too_few_base_requests_skipped_with_note(self):
        cmp = rr.compare_aggregates(_agg(count=10), _agg(p95=900), min_requests=100)
        assert cmp.findings == []
        assert cmp.rows[0][3] == "SKIPPED"
        assert "too few requests" in cmp.notes[0]

    def test_skipped_endpoint_still_checks_errors(self):
        cmp = rr.compare_aggregates(_agg(count=10), _agg(count=10, failures=5), min_requests=100)
        assert cmp.rows[0][3] == "REGRESSED errors"

    def test_one_thin_run_counts_not_the_total(self):
        """
        Scenario: the request minimum applies per run
          Given base runs of 500, 500 and 5 requests
          Then  the endpoint is skipped although the total is above the minimum
        """
        base = _agg_of({"count": 500}, {"count": 500}, {"count": 5})
        cmp = rr.compare_aggregates(base, _same(p95=900), min_requests=100)
        assert cmp.rows[0][3] == "SKIPPED"

    def test_head_collapse_is_a_finding_not_skipped(self):
        """
        Scenario: head stops serving an endpoint
          Given base serves 500 requests per run
          When  head serves 0 in one run
          Then  a "requests" finding is raised
        """
        head = _agg_of({"count": 500}, {"count": 500}, {"count": 0})
        cmp = rr.compare_aggregates(_agg(), head, min_requests=100)
        assert [f.kind for f in cmp.findings] == ["requests"]
        assert cmp.rows[0][3] == "REGRESSED requests"

    def test_endpoint_missing_from_head_is_a_finding(self):
        base = rr.aggregate_runs([_run(), _run(name="GET /gone")] * 3)
        head = _agg()
        cmp = rr.compare_aggregates(base, head)
        assert [(f.name, f.kind) for f in cmp.findings] == [("GET /gone", "missing")]

    def test_sparse_endpoint_missing_from_head_is_only_a_note(self):
        base = rr.aggregate_runs([_run(), _run(name="GET /rare", count=3)] * 3)
        cmp = rr.compare_aggregates(base, _agg())
        assert cmp.findings == []
        assert any("GET /rare" in n and "missing from head" in n for n in cmp.notes)

    def test_zero_base_metric_is_noted_not_compared(self):
        cmp = rr.compare_aggregates(_same(p95=0), _same(p95=5000))
        assert cmp.findings == []
        assert any("base p95 is 0" in n for n in cmp.notes)

    def test_aggregated_row_never_gates_latency(self):
        base = _same(name="Aggregated", p95=1000)
        head = _same(name="Aggregated", p95=5000)
        cmp = rr.compare_aggregates(base, head)
        assert cmp.findings == []
        assert cmp.rows[0][3] == "INFO"

    @pytest.mark.parametrize("side", ["base", "head"])
    def test_too_few_runs_fails(self, side):
        """
        Scenario: too few runs on one side
          Given 2 runs on one side and 3 on the other
          Then  a "runs" finding is raised for that side
        """
        few, enough = _same(n=2), _same(n=3)
        base, head = (few, enough) if side == "base" else (enough, few)
        cmp = rr.compare_aggregates(base, head, min_runs=3)
        assert [(f.name, f.kind) for f in cmp.findings] == [(side, "runs")]
        assert rr.compare_aggregates(base, head, min_runs=2).findings == []

    def test_new_endpoints(self):
        head = rr.aggregate_runs([_run(), _run(count=500, failures=200, name="new")] * 3)
        head.update(rr.aggregate_runs([_run(failures=100, name="new")] * 3))
        cmp = rr.compare_aggregates(_agg(), head)
        statuses = {r[0]: r[3] for r in cmp.rows}
        assert statuses[EP] == "OK"
        assert statuses["new"] == "REGRESSED errors"

    def test_legacy_aggregate_json_without_min_run_requests(self, tmp_path: Path):
        path = tmp_path / "old.json"
        rr.dump_aggregate(path, _agg())
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        del data[EP]["min_run_requests"]
        path.write_text(json.dumps(data), encoding="utf-8")
        assert rr.load_aggregate(path)[EP].min_run_requests == 500


class TestRender:
    def test_markdown_pass_and_fail(self):
        ok = rr.render_markdown(rr.compare_aggregates(_agg(), _agg()), tolerance=0.15)
        assert "**PASSED**" in ok and "| `GET /admin/contact [list]` |" in ok
        bad_cmp = rr.compare_aggregates(_agg(p95=1000), _agg(p95=5000), tolerance=0.15)
        bad = rr.render_markdown(bad_cmp, tolerance=0.15)
        assert "**FAILED**" in bad and "+400.0%" in bad

    def test_new_row_and_notes_rendered(self):
        cmp = rr.compare_aggregates({}, _agg(), min_runs=0)
        text = rr.render_markdown(cmp, tolerance=0.15)
        assert "NEW" in text and "Notes:" in text

    def test_delta_zero_base(self):
        assert rr._delta(0.0, 5.0) == "n/a"


class TestCli:
    def _write_runs(self, tmp_path: Path, prefix: str, **kwargs) -> list[str]:
        paths = []
        for i in range(3):
            p = tmp_path / f"{prefix}{i}.csv"
            p.write_text(_csv(_row(EP, count=500, **kwargs)), encoding="utf-8")
            paths.append(str(p))
        return paths

    def test_aggregate_then_compare_pass_and_fail(self, tmp_path, monkeypatch, capsys):
        summary = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        base = self._write_runs(tmp_path, "base", p95=1000)
        good = self._write_runs(tmp_path, "good", p95=1050)
        slow = self._write_runs(tmp_path, "slow", p95=3000)
        for name, files in (("base", base), ("good", good), ("slow", slow)):
            out = tmp_path / f"{name}.json"
            assert bl.run(["aggregate", "--stats", *files, "--out", str(out)]) == 0
        base_json, good_json, slow_json = (tmp_path / f"{n}.json" for n in ("base", "good", "slow"))
        assert bl.run(["compare", "--base", str(base_json), "--head", str(good_json)]) == 0
        assert bl.run(["compare", "--base", str(base_json), "--head", str(slow_json)]) == 1
        assert "FAILED" in capsys.readouterr().out
        assert summary.read_text(encoding="utf-8").count("Load test regression gate") == 2

    def test_compare_without_summary_env(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        files = self._write_runs(tmp_path, "r")
        agg = tmp_path / "a.json"
        assert bl.run(["aggregate", "--stats", *files, "--out", str(agg)]) == 0
        report = tmp_path / "out" / "report.md"
        cmd = ["compare", "--base", str(agg), "--head", str(agg), "--report", str(report)]
        assert bl.run(cmd) == 0
        assert "PASSED" in report.read_text(encoding="utf-8")

    def test_aggregate_min_runs_and_missing_files(self, tmp_path, capsys):
        files = self._write_runs(tmp_path, "r")
        out = tmp_path / "o.json"
        args = ["aggregate", "--stats", *files, str(tmp_path / "nope.csv"), "--out", str(out)]
        assert bl.run([*args, "--min-runs", "4"]) == 1
        assert "need 4" in capsys.readouterr().err
        assert bl.run([*args, "--min-runs", "3"]) == 0

    def test_aggregate_empty_stats_errors(self, tmp_path, capsys):
        empty = tmp_path / "e.csv"
        empty.write_text(_csv(), encoding="utf-8")
        assert bl.run(["aggregate", "--stats", str(empty), "--out", str(tmp_path / "o.json")]) == 1
        assert "no endpoint rows" in capsys.readouterr().err

    def test_run_reads_sys_argv_when_none(self, tmp_path, monkeypatch):
        files = self._write_runs(tmp_path, "r")
        out = tmp_path / "o.json"
        monkeypatch.setattr(
            "sys.argv", ["baselines", "aggregate", "--stats", *files, "--out", str(out)]
        )
        assert bl.run() == 0
        assert out.exists()
