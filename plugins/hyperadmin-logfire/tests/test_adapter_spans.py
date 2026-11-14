"""Unit tests for adapter spans (``docs/specs/plugin-logfire.md``, phase B scenarios)."""

from __future__ import annotations

import logging
from typing import Any

import logfire
import pytest
from logfire.testing import TestExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from hyperadmin_logfire import LogfirePlugin, adapter_spans


class Product:
    pass


@pytest.fixture
def exporter() -> TestExporter:
    span_exporter = TestExporter()
    logfire.configure(
        send_to_logfire=False,
        console=False,
        additional_span_processors=[SimpleSpanProcessor(span_exporter)],
    )
    return span_exporter


def _call(plugin: LogfirePlugin, op: str, kwargs: dict[str, Any], result: Any = None) -> None:
    plugin.on_before_adapter_call(admin=None, model=Product, op=op, kwargs=kwargs)
    plugin.on_after_adapter_call(admin=None, model=Product, op=op, result=result, error=None)


def _by_name(exporter: TestExporter, name: str) -> dict[str, Any]:
    spans = exporter.exported_spans_as_dict()
    matching = [s for s in spans if s["name"] == name]
    assert len(matching) == 1, [s["name"] for s in spans]
    return matching[0]


def test_adapter_span_emitted_with_model_attribute(exporter: TestExporter) -> None:
    """
    Scenario: adapter span emitted with model attribute
      Given a logfire test sink
      When  a list adapter call runs for Product (page 1, page size 10)
      Then  the sink holds "admin.adapter.list" with model, page and page_size
      And   the span carries the result count
    """
    _call(
        LogfirePlugin(),
        "list",
        {"page": 1, "page_size": 10, "search": "x", "filters": {"a": 1}},
        result=([1, 2, 3], 3),
    )

    attributes = _by_name(exporter, "admin.adapter.list")["attributes"]
    assert attributes["model"] == "Product"
    assert attributes["op"] == "list"
    assert (attributes["page"], attributes["page_size"]) == (1, 10)
    assert attributes["search"] == "x"
    assert attributes["has_filters"] is True
    assert attributes["result_count"] == 3


def test_list_paginated_result_object_counts_items(exporter: TestExporter) -> None:
    """
    Scenario: a paginated result records its item count
      Given a logfire test sink
      When  a list_paginated call returns an object with items
      Then  the span carries result_count
    """
    result = type("Result", (), {"items": [1, 2]})()

    _call(LogfirePlugin(), "list_paginated", {"page": 2}, result=result)

    assert _by_name(exporter, "admin.adapter.list_paginated")["attributes"]["result_count"] == 2


def test_list_result_without_sequence_records_no_count(exporter: TestExporter) -> None:
    """
    Scenario: an unrecognised list result adds no count
      Given a logfire test sink
      When  a list call returns None
      Then  the span has no result_count
    """
    _call(LogfirePlugin(), "list", {}, result=None)

    assert "result_count" not in _by_name(exporter, "admin.adapter.list")["attributes"]


@pytest.mark.parametrize(
    ("op", "kwargs", "expected"),
    [
        ("get", {"pk": 7}, {"pk": "7"}),
        ("delete", {"pk": 7}, {"pk": "7"}),
        ("update", {"pk": 7, "data": {"a": 1, "b": 2}}, {"pk": "7", "field_count": 2}),
        ("create", {"data": {"secret": "x"}}, {"field_count": 1}),
        ("get_related", {"pk": 1, "field": "items"}, {"pk": "1", "field": "items"}),
        ("get_choices", {"field": "owner", "limit": 5, "q": "bob"}, {"field": "owner", "limit": 5}),
        ("get_schema", {"anything": 1}, {}),
    ],
)
def test_span_attributes_are_whitelisted(op: str, kwargs: dict[str, Any], expected: Any) -> None:
    """
    Scenario: span attributes never carry field values
      Given an adapter call with payload kwargs
      When  the attributes are computed
      Then  only whitelisted, non-PII attributes remain
    """
    assert adapter_spans.safe_attributes(op, kwargs) == expected


def test_nested_adapter_call_produces_nested_spans(exporter: TestExporter) -> None:
    """
    Scenario: nested adapter call produces nested spans
      Given a logfire test sink
      When  a get_choices call runs inside a list call
      Then  "admin.adapter.get_choices" is a child of "admin.adapter.list"
    """
    plugin = LogfirePlugin()
    plugin.on_before_adapter_call(admin=None, model=Product, op="list", kwargs={})
    _call(plugin, "get_choices", {"field": "owner", "limit": 5}, result=[])
    plugin.on_after_adapter_call(admin=None, model=Product, op="list", result=([], 0), error=None)

    parent = _by_name(exporter, "admin.adapter.list")
    child = _by_name(exporter, "admin.adapter.get_choices")
    assert child["context"]["trace_id"] == parent["context"]["trace_id"]
    assert child["parent"]["span_id"] == parent["context"]["span_id"]


def test_error_is_recorded_on_the_span(exporter: TestExporter) -> None:
    """
    Scenario: a raising adapter call closes its span with the error
      Given an open adapter span
      When  on_after_adapter_call receives an error
      Then  the span is closed and records the exception
    """
    plugin = LogfirePlugin()
    plugin.on_before_adapter_call(admin=None, model=Product, op="delete", kwargs={"pk": 1})

    plugin.on_after_adapter_call(
        admin=None, model=Product, op="delete", result=None, error=ValueError("boom")
    )

    span = _by_name(exporter, "admin.adapter.delete")
    assert [e["name"] for e in span["events"]] == ["exception"]
    assert adapter_spans._open_spans.get() == ()


def test_missing_close_span_is_logged_and_does_not_crash(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Scenario: missing close span is logged but does not crash
      Given the contextvar stack is empty
      When  on_after_adapter_call is called manually
      Then  a WARNING log is emitted
      And   no exception is raised
    """
    with caplog.at_level(logging.WARNING, logger="hyperadmin_logfire.adapter_spans"):
        LogfirePlugin().on_after_adapter_call(admin=None, model=Product, op="get", result=None)

    assert "no open span found" in caplog.text
