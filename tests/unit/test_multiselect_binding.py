"""Unit tests for multiselect form binding and value coercion (#168)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from hyperadmin.core.adapters import BaseAdapter
from hyperadmin.views.dynamic import DynamicModelView
from hyperadmin.views.forms import (
    MultiSelectWidget,
    PydanticForm,
    RelationMultiSelectWidget,
)

if TYPE_CHECKING:
    import builtins

    from hyperadmin.core.choices import ChoiceItem


# -- Models --


class Article(BaseModel):
    title: str
    tags: list[str] = []
    is_published: bool = False


# -- Helpers --


class StubAdapter(BaseAdapter):
    def __init__(self, model: Any) -> None:
        self.model = model
        self.inspector = SimpleNamespace(relationships=[], c=[])

    async def get(self, pk: Any) -> Any:
        return None

    async def list(self, **kwargs: Any) -> tuple[list[Any], int]:
        return [], 0

    async def create(self, data: dict[str, Any]) -> Any:
        return SimpleNamespace(id=1, **data)

    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        return SimpleNamespace(id=pk, **data)

    async def delete(self, pk: Any) -> None:
        pass

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


class FakeFormData:
    """Mimics Starlette's ImmutableMultiDict with getlist() support."""

    def __init__(self, items: list[tuple[str, str]]) -> None:
        self._items = items

    def __iter__(self):
        seen: set[str] = set()
        for k, _v in self._items:
            if k not in seen:
                seen.add(k)
                yield k

    def __getitem__(self, key: str) -> str:
        for k, v in reversed(self._items):
            if k == key:
                return v
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        return any(k == key for k, _ in self._items)

    def keys(self):
        return list(dict(self._items).keys())

    def items(self):
        seen: set[str] = set()
        for k, v in self._items:
            if k not in seen:
                seen.add(k)
                yield k, v

    def getlist(self, key: str) -> list[str]:
        return [v for k, v in self._items if k == key]


# -- Tests: _extract_form_data --


def test_extract_multiselect_uses_getlist() -> None:
    """Multi-value fields use getlist() instead of losing values via dict()."""
    form = PydanticForm(
        Article,
        widgets={"tags": MultiSelectWidget(choices=[])},
    )
    # Force field generation
    _ = form.fields

    form_data = FakeFormData(
        [
            ("title", "Hello"),
            ("tags", "python"),
            ("tags", "fastapi"),
            ("tags", "htmx"),
            ("is_published", "on"),
        ]
    )
    data = DynamicModelView._extract_form_data(form_data, form)
    assert data["tags"] == ["python", "fastapi", "htmx"]
    assert data["title"] == "Hello"


def test_extract_relation_multiselect_uses_getlist() -> None:
    """RelationMultiSelectWidget fields also use getlist()."""
    form = PydanticForm(
        Article,
        widgets={"tags": RelationMultiSelectWidget(choices_url="/choices/tags")},
    )
    _ = form.fields

    form_data = FakeFormData(
        [
            ("title", "Hello"),
            ("tags", "1"),
            ("tags", "2"),
        ]
    )
    data = DynamicModelView._extract_form_data(form_data, form)
    assert data["tags"] == ["1", "2"]


def test_extract_absent_multiselect_yields_empty_list() -> None:
    """When no values submitted for multiselect, field gets empty list."""
    form = PydanticForm(
        Article,
        widgets={"tags": MultiSelectWidget(choices=[])},
    )
    _ = form.fields

    form_data = FakeFormData([("title", "Hello")])
    data = DynamicModelView._extract_form_data(form_data, form)
    assert data["tags"] == []


def test_extract_absent_checkbox_yields_false() -> None:
    """Absent checkbox fields get False (existing behaviour preserved)."""
    form = PydanticForm(Article)
    _ = form.fields

    form_data = FakeFormData([("title", "Hello")])
    data = DynamicModelView._extract_form_data(form_data, form)
    assert data["is_published"] is False


def test_extract_single_value_fields_unchanged() -> None:
    """Regular text fields keep single-value dict() behavior."""
    form = PydanticForm(Article)
    _ = form.fields

    form_data = FakeFormData([("title", "Hello"), ("is_published", "on")])
    data = DynamicModelView._extract_form_data(form_data, form)
    assert data["title"] == "Hello"


def test_extract_preserves_single_multiselect_value() -> None:
    """When only one value submitted for multiselect, it's still a list."""
    form = PydanticForm(
        Article,
        widgets={"tags": MultiSelectWidget(choices=[])},
    )
    _ = form.fields

    form_data = FakeFormData([("title", "Hello"), ("tags", "python")])
    data = DynamicModelView._extract_form_data(form_data, form)
    assert data["tags"] == ["python"]
