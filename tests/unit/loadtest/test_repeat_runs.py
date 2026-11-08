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
        agg = rr.aggregate_runs([_run(p95=90), _run(p95=100), _run(p95=300)])[EP]
        assert agg.runs == 3
        assert agg.requests == 1500
        assert (agg.p95.median, agg.p95.low, agg.p95.high) == (100, 90, 300)

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


class TestCompare:
    def test_within_tolerance_passes(self):
        cmp = rr.compare_aggregates(_agg(), _agg(rps=9.0, p95=110, p99=130), tolerance=0.15)
        assert cmp.findings == []
        assert cmp.rows[0][3] == "OK"

    def test_synthetic_regression_fails(self):
        cmp = rr.compare_aggregates(_agg(), _agg(rps=7.0, p95=150, p99=200), tolerance=0.15)
        assert {f.kind for f in cmp.findings} == {"rps", "p95", "p99"}
        assert cmp.rows[0][3] == "REGRESSED req/s, p95, p99"

    def test_improvement_passes(self):
        cmp = rr.compare_aggregates(_agg(), _agg(rps=20.0, p95=50, p99=60))
        assert cmp.findings == []

    def test_tolerance_is_configurable(self):
        base, head = _agg(), _agg(p95=110)
        assert rr.compare_aggregates(base, head, tolerance=0.05).findings
        assert not rr.compare_aggregates(base, head, tolerance=0.15).findings

    def test_error_rate_over_max_fails(self):
        cmp = rr.compare_aggregates(_agg(), _agg(failures=50), max_error_rate=0.01)
        assert [f.kind for f in cmp.findings] == ["error_rate"]

    def test_too_few_requests_skipped_with_note(self):
        cmp = rr.compare_aggregates(_agg(), _agg(count=10, p95=900), min_requests=100)
        assert cmp.findings == []
        assert cmp.rows[0][3] == "SKIPPED"
        assert "too few requests" in cmp.notes[0]

    def test_skipped_endpoint_still_checks_errors(self):
        cmp = rr.compare_aggregates(_agg(), _agg(count=10, failures=5), min_requests=100)
        assert cmp.rows[0][3] == "REGRESSED errors"

    def test_new_and_removed_endpoints(self):
        base = _agg(name="old")
        head = rr.aggregate_runs([_run(), _run(count=500, failures=200, name="new")])
        head.update(rr.aggregate_runs([_run(failures=100, name="new")]))
        cmp = rr.compare_aggregates(base, head)
        statuses = {r[0]: r[3] for r in cmp.rows}
        assert statuses[EP] == "NEW"
        assert statuses["new"] == "REGRESSED errors"
        assert any("in base but missing from head" in n for n in cmp.notes)


class TestRender:
    def test_markdown_pass_and_fail(self):
        ok = rr.render_markdown(rr.compare_aggregates(_agg(), _agg()), tolerance=0.15)
        assert "**PASSED**" in ok and "| `GET /admin/contact [list]` |" in ok
        bad_cmp = rr.compare_aggregates(_agg(), _agg(p95=500), tolerance=0.15)
        bad = rr.render_markdown(bad_cmp, tolerance=0.15)
        assert "**FAILED**" in bad and "+400.0%" in bad

    def test_new_row_and_notes_rendered(self):
        cmp = rr.compare_aggregates({}, _agg())
        text = rr.render_markdown(cmp, tolerance=0.15)
        assert "NEW" in text and "Notes:" in text

    def test_delta_zero_base(self):
        assert rr._delta(0.0, 5.0) == "n/a"


class TestCli:
    def _write_runs(self, tmp_path: Path, prefix: str, **kwargs) -> list[str]:
        paths = []
        for i in range(2):
            p = tmp_path / f"{prefix}{i}.csv"
            p.write_text(_csv(_row(EP, count=500, **kwargs)), encoding="utf-8")
            paths.append(str(p))
        return paths

    def test_aggregate_then_compare_pass_and_fail(self, tmp_path, monkeypatch, capsys):
        summary = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
        base = self._write_runs(tmp_path, "base", p95=100)
        good = self._write_runs(tmp_path, "good", p95=105)
        slow = self._write_runs(tmp_path, "slow", p95=300)
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
