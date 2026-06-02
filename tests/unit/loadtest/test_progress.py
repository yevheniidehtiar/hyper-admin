"""Unit tests for progress reporters and reporter selection (#253)."""

import io

from hyperadmin.loadtest.progress import (
    PlainReporter,
    RichReporter,
    _format_rate,
    make_reporter,
)


class FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


class TestFormatRate:
    def test_sub_thousand_rate(self):
        assert _format_rate(500, 1.0) == "500/s"

    def test_thousands_rate(self):
        assert _format_rate(28400, 1.0) == "28.4K/s"

    def test_zero_elapsed_is_safe(self):
        # No division-by-zero; rate is reported as 0 when no time has passed.
        assert _format_rate(100, 0.0) == "0/s"


class TestPlainReporter:
    def test_advance_emits_progress_line(self):
        clock = iter([0.0, 1.0]).__next__  # start, advance
        stream = io.StringIO()
        reporter = PlainReporter(stream, clock=clock)
        reporter.start_table("invoices", 100)
        reporter.advance("invoices", 35)
        out = stream.getvalue()
        assert "table=invoices" in out
        assert "completed=35/100" in out
        assert "rate=" in out

    def test_finish_line_reports_elapsed(self):
        clock = iter([0.0, 2.0]).__next__
        stream = io.StringIO()
        reporter = PlainReporter(stream, clock=clock)
        reporter.start_table("accounts", 10)
        reporter.finish_table("accounts")
        assert "done=" in stream.getvalue()
        assert "elapsed=2.0s" in stream.getvalue()

    def test_close_is_noop(self):
        PlainReporter(io.StringIO()).close()


class TestRichReporter:
    def test_rich_reporter_lifecycle(self):
        reporter = RichReporter()
        try:
            reporter.start_table("invoices", 100)
            reporter.advance("invoices", 50)
            reporter.finish_table("invoices")
        finally:
            reporter.close()


class TestMakeReporter:
    def test_no_progress_forces_plain(self):
        reporter = make_reporter(no_progress=True, stream=FakeTTY())
        assert isinstance(reporter, PlainReporter)

    def test_non_tty_uses_plain(self):
        reporter = make_reporter(no_progress=False, stream=io.StringIO())
        assert isinstance(reporter, PlainReporter)

    def test_tty_uses_rich(self):
        reporter = make_reporter(no_progress=False, stream=FakeTTY())
        try:
            assert isinstance(reporter, RichReporter)
        finally:
            reporter.close()
