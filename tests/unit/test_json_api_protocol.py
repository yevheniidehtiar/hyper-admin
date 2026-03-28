"""Unit tests for JsonApiAdapter protocol conformance, envelope shape, and pagination meta.

Covers:
- Protocol shape: JsonApiAdapter inherits BaseAdapter, requires ``to_dict``
- Envelope shape: ``ListEnvelope`` serialises to ``{data: [...], meta: {...}}``
- PaginationMeta fields: ``total``, ``page``, ``page_size`` are present and correct
- Subclass contract enforcement: missing abstract methods raise TypeError
- Dataclass invariants: field types, equality, immutability expectations
"""

from __future__ import annotations

import builtins
import inspect
from abc import ABC
from dataclasses import asdict, fields
from typing import Any
from unittest.mock import MagicMock

import pytest

from hyperadmin.core.adapters import (
    BaseAdapter,
    JsonApiAdapter,
    ListEnvelope,
    PaginationMeta,
)
from hyperadmin.core.choices import ChoiceItem

# ---------------------------------------------------------------------------
# Concrete test double
# ---------------------------------------------------------------------------


class _ConcreteJsonApiAdapter(JsonApiAdapter):
    """Fully concrete adapter for protocol testing."""

    def __init__(self, records: builtins.list[dict[str, Any]] | None = None) -> None:
        self.model = None
        self.engine = None
        self._records: builtins.list[dict[str, Any]] = records or []

    def to_dict(self, record: Any) -> dict[str, Any]:
        return dict(record)

    async def get(self, pk: Any) -> Any:
        return next((r for r in self._records if r.get("id") == pk), None)

    async def list(
        self,
        page: int = 1,
        page_size: int = 10,
        search: str | None = None,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
    ) -> tuple[builtins.list[Any], int]:
        start = (page - 1) * page_size
        end = start + page_size
        return self._records[start:end], len(self._records)

    async def create(self, data: dict[str, Any]) -> Any:
        self._records.append(data)
        return data

    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        return data

    async def delete(self, pk: Any) -> None:
        self._records = [r for r in self._records if r.get("id") != pk]

    async def get_related(self, pk: Any, field: str) -> builtins.list[Any]:
        return []

    async def get_schema(self) -> dict[str, Any]:
        return {}

    async def get_choices(
        self,
        field: str,
        q: str = "",
        limit: int = 50,
        offset: int = 0,
        **filters: Any,
    ) -> builtins.list[ChoiceItem]:
        return []


# ---------------------------------------------------------------------------
# Protocol shape: inheritance and abstract contract
# ---------------------------------------------------------------------------


class TestJsonApiAdapterProtocolShape:
    """Verify the class hierarchy and abstract method requirements."""

    def test_inherits_base_adapter(self) -> None:
        assert issubclass(JsonApiAdapter, BaseAdapter)

    def test_is_abstract(self) -> None:
        assert issubclass(JsonApiAdapter, ABC)

    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            JsonApiAdapter(model=MagicMock(), engine=MagicMock())  # type: ignore[abstract]

    def test_to_dict_is_abstract(self) -> None:
        assert getattr(JsonApiAdapter.to_dict, "__isabstractmethod__", False)

    def test_has_list_as_envelope_method(self) -> None:
        assert hasattr(JsonApiAdapter, "list_as_envelope")
        assert inspect.iscoroutinefunction(JsonApiAdapter.list_as_envelope)

    def test_list_as_envelope_is_not_abstract(self) -> None:
        """list_as_envelope is a concrete convenience method, not abstract."""
        assert not getattr(JsonApiAdapter.list_as_envelope, "__isabstractmethod__", False)

    def test_concrete_subclass_instantiates(self) -> None:
        adapter = _ConcreteJsonApiAdapter()
        assert isinstance(adapter, JsonApiAdapter)
        assert isinstance(adapter, BaseAdapter)

    def test_missing_to_dict_raises_type_error(self) -> None:
        """A subclass that implements BaseAdapter methods but not to_dict cannot be instantiated."""

        class _MissingToDict(JsonApiAdapter):
            async def get(self, pk: Any) -> Any:
                return None

            async def list(self, **kw: Any) -> tuple[builtins.list[Any], int]:
                return [], 0

            async def create(self, data: dict[str, Any]) -> Any:
                return data

            async def update(self, pk: Any, data: dict[str, Any]) -> Any:
                return data

            async def delete(self, pk: Any) -> None:
                pass

            async def get_related(self, pk: Any, field: str) -> builtins.list[Any]:
                return []

            async def get_schema(self) -> dict[str, Any]:
                return {}

            async def get_choices(self, field: str, **kw: Any) -> builtins.list[ChoiceItem]:
                return []

        with pytest.raises(TypeError):
            _MissingToDict(model=None, engine=None)  # type: ignore[abstract]

    def test_to_dict_signature(self) -> None:
        """to_dict accepts a single record argument and returns a dict."""
        sig = inspect.signature(JsonApiAdapter.to_dict)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "record" in params

    def test_list_as_envelope_signature(self) -> None:
        """list_as_envelope accepts pagination/filter keyword arguments."""
        sig = inspect.signature(JsonApiAdapter.list_as_envelope)
        param_names = set(sig.parameters.keys())
        assert {"page", "page_size", "search", "filters", "order_by"} <= param_names


# ---------------------------------------------------------------------------
# PaginationMeta dataclass
# ---------------------------------------------------------------------------


class TestPaginationMetaFields:
    """Verify PaginationMeta dataclass shape and behaviour."""

    def test_required_fields(self) -> None:
        field_names = {f.name for f in fields(PaginationMeta)}
        assert field_names == {"total", "page", "page_size"}

    def test_field_types(self) -> None:
        type_map = {f.name: f.type for f in fields(PaginationMeta)}
        assert type_map["total"] == "int"
        assert type_map["page"] == "int"
        assert type_map["page_size"] == "int"

    def test_construction(self) -> None:
        meta = PaginationMeta(total=100, page=3, page_size=25)
        assert meta.total == 100
        assert meta.page == 3
        assert meta.page_size == 25

    def test_as_dict(self) -> None:
        meta = PaginationMeta(total=42, page=1, page_size=10)
        d = asdict(meta)
        assert d == {"total": 42, "page": 1, "page_size": 10}

    def test_equality(self) -> None:
        a = PaginationMeta(total=10, page=1, page_size=5)
        b = PaginationMeta(total=10, page=1, page_size=5)
        assert a == b

    def test_inequality(self) -> None:
        a = PaginationMeta(total=10, page=1, page_size=5)
        b = PaginationMeta(total=10, page=2, page_size=5)
        assert a != b

    def test_zero_total(self) -> None:
        meta = PaginationMeta(total=0, page=1, page_size=10)
        assert meta.total == 0


# ---------------------------------------------------------------------------
# ListEnvelope dataclass
# ---------------------------------------------------------------------------


class TestListEnvelopeShape:
    """Verify ListEnvelope conforms to the response envelope spec."""

    def test_required_fields(self) -> None:
        field_names = {f.name for f in fields(ListEnvelope)}
        assert field_names == {"data", "meta"}

    def test_data_is_list_of_dicts(self) -> None:
        envelope = ListEnvelope(
            data=[{"id": 1}], meta=PaginationMeta(total=1, page=1, page_size=10)
        )
        assert isinstance(envelope.data, list)
        assert all(isinstance(item, dict) for item in envelope.data)

    def test_meta_is_pagination_meta(self) -> None:
        meta = PaginationMeta(total=5, page=1, page_size=10)
        envelope = ListEnvelope(data=[], meta=meta)
        assert isinstance(envelope.meta, PaginationMeta)
        assert envelope.meta is meta

    def test_as_dict_matches_spec(self) -> None:
        """Envelope serialises to {data: [...], meta: {total, page, page_size}}."""
        meta = PaginationMeta(total=2, page=1, page_size=10)
        envelope = ListEnvelope(data=[{"name": "Alice"}, {"name": "Bob"}], meta=meta)
        d = asdict(envelope)
        assert set(d.keys()) == {"data", "meta"}
        assert set(d["meta"].keys()) == {"total", "page", "page_size"}
        assert len(d["data"]) == 2

    def test_empty_data_envelope(self) -> None:
        envelope = ListEnvelope(data=[], meta=PaginationMeta(total=0, page=1, page_size=10))
        assert envelope.data == []
        assert envelope.meta.total == 0

    def test_envelope_preserves_record_order(self) -> None:
        records = [{"id": i, "val": f"v{i}"} for i in range(5)]
        envelope = ListEnvelope(data=records, meta=PaginationMeta(total=5, page=1, page_size=10))
        assert [r["id"] for r in envelope.data] == [0, 1, 2, 3, 4]

    def test_envelope_equality(self) -> None:
        meta = PaginationMeta(total=1, page=1, page_size=10)
        a = ListEnvelope(data=[{"id": 1}], meta=meta)
        b = ListEnvelope(data=[{"id": 1}], meta=PaginationMeta(total=1, page=1, page_size=10))
        assert a == b


# ---------------------------------------------------------------------------
# list_as_envelope integration
# ---------------------------------------------------------------------------


class TestListAsEnvelope:
    """Verify list_as_envelope produces correctly shaped envelopes."""

    @pytest.mark.anyio
    async def test_returns_list_envelope_type(self) -> None:
        adapter = _ConcreteJsonApiAdapter()
        result = await adapter.list_as_envelope()
        assert isinstance(result, ListEnvelope)

    @pytest.mark.anyio
    async def test_empty_collection(self) -> None:
        adapter = _ConcreteJsonApiAdapter()
        envelope = await adapter.list_as_envelope()
        assert envelope.data == []
        assert envelope.meta == PaginationMeta(total=0, page=1, page_size=10)

    @pytest.mark.anyio
    async def test_envelope_data_matches_to_dict_output(self) -> None:
        records = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
        adapter = _ConcreteJsonApiAdapter(records=records)
        envelope = await adapter.list_as_envelope()
        assert envelope.data == records

    @pytest.mark.anyio
    async def test_meta_reflects_full_collection_size(self) -> None:
        records = [{"id": i} for i in range(15)]
        adapter = _ConcreteJsonApiAdapter(records=records)
        envelope = await adapter.list_as_envelope(page=1, page_size=5)
        assert len(envelope.data) == 5
        assert envelope.meta.total == 15
        assert envelope.meta.page == 1
        assert envelope.meta.page_size == 5

    @pytest.mark.anyio
    async def test_pagination_second_page(self) -> None:
        records = [{"id": i} for i in range(10)]
        adapter = _ConcreteJsonApiAdapter(records=records)
        envelope = await adapter.list_as_envelope(page=2, page_size=3)
        assert [r["id"] for r in envelope.data] == [3, 4, 5]
        assert envelope.meta.total == 10
        assert envelope.meta.page == 2

    @pytest.mark.anyio
    async def test_pagination_last_partial_page(self) -> None:
        records = [{"id": i} for i in range(7)]
        adapter = _ConcreteJsonApiAdapter(records=records)
        envelope = await adapter.list_as_envelope(page=3, page_size=3)
        assert [r["id"] for r in envelope.data] == [6]
        assert envelope.meta.total == 7

    @pytest.mark.anyio
    async def test_pagination_beyond_last_page(self) -> None:
        records = [{"id": i} for i in range(5)]
        adapter = _ConcreteJsonApiAdapter(records=records)
        envelope = await adapter.list_as_envelope(page=100, page_size=10)
        assert envelope.data == []
        assert envelope.meta.total == 5

    @pytest.mark.anyio
    async def test_default_page_size(self) -> None:
        adapter = _ConcreteJsonApiAdapter()
        envelope = await adapter.list_as_envelope()
        assert envelope.meta.page_size == 10

    @pytest.mark.anyio
    async def test_custom_page_size(self) -> None:
        records = [{"id": i} for i in range(50)]
        adapter = _ConcreteJsonApiAdapter(records=records)
        envelope = await adapter.list_as_envelope(page_size=25)
        assert envelope.meta.page_size == 25
        assert len(envelope.data) == 25

    @pytest.mark.anyio
    async def test_forwards_search_filter_order(self) -> None:
        """list_as_envelope passes search/filters/order_by through to list()."""
        adapter = _ConcreteJsonApiAdapter(records=[{"id": 1}])
        envelope = await adapter.list_as_envelope(
            search="query",
            filters={"status": "active"},
            order_by="name",
        )
        # The stub ignores these params, but the call must not raise
        assert isinstance(envelope, ListEnvelope)

    @pytest.mark.anyio
    async def test_envelope_serialises_to_spec(self) -> None:
        """Full round-trip: adapter -> envelope -> dict matches JSON:API spec."""
        records = [{"id": 1, "title": "Hello"}]
        adapter = _ConcreteJsonApiAdapter(records=records)
        envelope = await adapter.list_as_envelope()
        d = asdict(envelope)
        assert d == {
            "data": [{"id": 1, "title": "Hello"}],
            "meta": {"total": 1, "page": 1, "page_size": 10},
        }


# ---------------------------------------------------------------------------
# Export conformance
# ---------------------------------------------------------------------------


class TestCoreExports:
    """Verify symbols are importable from the public core package."""

    def test_json_api_adapter_exported(self) -> None:
        from hyperadmin.core import JsonApiAdapter as JA

        assert JA is JsonApiAdapter

    def test_list_envelope_exported(self) -> None:
        from hyperadmin.core import ListEnvelope as LE

        assert LE is ListEnvelope

    def test_pagination_meta_exported(self) -> None:
        from hyperadmin.core import PaginationMeta as PM

        assert PM is PaginationMeta
