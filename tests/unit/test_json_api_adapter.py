"""Unit tests for JsonApiAdapter protocol and response envelope schema."""

from __future__ import annotations

import builtins
from dataclasses import asdict
from typing import Any
from unittest.mock import MagicMock

import pytest

from hyperadmin.core.adapters import (
    JsonApiAdapter,
    ListEnvelope,
    PaginationMeta,
)
from hyperadmin.core.choices import ChoiceItem

# ---------------------------------------------------------------------------
# Concrete test double
# ---------------------------------------------------------------------------


class _StubJsonApiAdapter(JsonApiAdapter):
    """Minimal concrete implementation for testing."""

    def __init__(self) -> None:
        # Bypass BaseAdapter.__init__ — we don't need a real model/engine
        self.model = None
        self.engine = None
        self._records: builtins.list[dict[str, Any]] = []

    # -- JsonApiAdapter abstract -------------------------------------------

    def to_dict(self, record: Any) -> dict[str, Any]:
        return dict(record)

    # -- BaseAdapter abstracts (minimal stubs) -----------------------------

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

    async def save_inline_rows(
        self, spec: Any, rows: builtins.list[dict[str, Any]], parent_pk: Any
    ) -> None:
        pass


# ---------------------------------------------------------------------------
# PaginationMeta tests
# ---------------------------------------------------------------------------


class TestPaginationMeta:
    def test_fields(self) -> None:
        meta = PaginationMeta(total=100, page=2, page_size=25)
        assert meta.total == 100
        assert meta.page == 2
        assert meta.page_size == 25

    def test_as_dict(self) -> None:
        meta = PaginationMeta(total=50, page=1, page_size=10)
        assert asdict(meta) == {"total": 50, "page": 1, "page_size": 10}


# ---------------------------------------------------------------------------
# ListEnvelope tests
# ---------------------------------------------------------------------------


class TestListEnvelope:
    def test_structure(self) -> None:
        meta = PaginationMeta(total=2, page=1, page_size=10)
        envelope = ListEnvelope(data=[{"id": 1}, {"id": 2}], meta=meta)
        assert len(envelope.data) == 2
        assert envelope.meta is meta

    def test_as_dict_matches_spec(self) -> None:
        """Envelope serialises to ``{data: [...], meta: {total, page, page_size}}``."""
        meta = PaginationMeta(total=1, page=1, page_size=10)
        envelope = ListEnvelope(data=[{"name": "Alice"}], meta=meta)
        d = asdict(envelope)
        assert set(d.keys()) == {"data", "meta"}
        assert set(d["meta"].keys()) == {"total", "page", "page_size"}

    def test_empty_data(self) -> None:
        envelope = ListEnvelope(data=[], meta=PaginationMeta(total=0, page=1, page_size=10))
        assert envelope.data == []
        assert envelope.meta.total == 0


# ---------------------------------------------------------------------------
# JsonApiAdapter tests
# ---------------------------------------------------------------------------


class TestJsonApiAdapter:
    def test_is_abstract(self) -> None:
        """Cannot instantiate JsonApiAdapter directly."""
        with pytest.raises(TypeError):
            JsonApiAdapter(model=MagicMock(), engine=MagicMock())  # type: ignore[abstract]

    def test_to_dict(self) -> None:
        adapter = _StubJsonApiAdapter()
        record = {"id": 1, "name": "Test"}
        assert adapter.to_dict(record) == {"id": 1, "name": "Test"}

    @pytest.mark.anyio
    async def test_list_as_envelope_empty(self) -> None:
        adapter = _StubJsonApiAdapter()
        envelope = await adapter.list_as_envelope()
        assert isinstance(envelope, ListEnvelope)
        assert envelope.data == []
        assert envelope.meta.total == 0
        assert envelope.meta.page == 1
        assert envelope.meta.page_size == 10

    @pytest.mark.anyio
    async def test_list_as_envelope_with_records(self) -> None:
        adapter = _StubJsonApiAdapter()
        adapter._records = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"},
        ]
        envelope = await adapter.list_as_envelope(page=1, page_size=2)
        assert len(envelope.data) == 2
        assert envelope.meta.total == 3
        assert envelope.meta.page == 1
        assert envelope.meta.page_size == 2
        assert envelope.data[0] == {"id": 1, "name": "Alice"}
        assert envelope.data[1] == {"id": 2, "name": "Bob"}

    @pytest.mark.anyio
    async def test_list_as_envelope_second_page(self) -> None:
        adapter = _StubJsonApiAdapter()
        adapter._records = [{"id": i, "name": f"item-{i}"} for i in range(1, 6)]
        envelope = await adapter.list_as_envelope(page=2, page_size=2)
        assert len(envelope.data) == 2
        assert envelope.data[0]["id"] == 3
        assert envelope.data[1]["id"] == 4
        assert envelope.meta.total == 5

    @pytest.mark.anyio
    async def test_list_as_envelope_passes_filters(self) -> None:
        adapter = _StubJsonApiAdapter()
        adapter._records = [{"id": 1}]
        envelope = await adapter.list_as_envelope(
            search="x", filters={"status": "active"}, order_by="name"
        )
        assert isinstance(envelope, ListEnvelope)


# ---------------------------------------------------------------------------
# Export tests
# ---------------------------------------------------------------------------


class TestExports:
    def test_importable_from_core(self) -> None:
        from hyperadmin.core import JsonApiAdapter as JA
        from hyperadmin.core import ListEnvelope as LE
        from hyperadmin.core import PaginationMeta as PM

        assert JA is JsonApiAdapter
        assert LE is ListEnvelope
        assert PM is PaginationMeta
