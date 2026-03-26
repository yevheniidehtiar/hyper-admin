"""Unit tests for cascading/dependent select support (#166)."""

from __future__ import annotations

import builtins
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel
from starlette.requests import Request

from hyperadmin.core.adapters import BaseAdapter
from hyperadmin.core.choices import ChoiceItem
from hyperadmin.core.options import AdminOptions
from hyperadmin.views import dynamic as dynamic_module
from hyperadmin.views.forms import RelationSelectWidget

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class City(BaseModel):
    name: str
    country_id: int | None = None


class StubAdapter(BaseAdapter):
    def __init__(self, model):
        self.model = model
        rel = SimpleNamespace(
            key="country", local_columns=[SimpleNamespace(key="country_id", name="country_id")]
        )
        self.inspector = SimpleNamespace(relationships=[rel], c=[])

    async def get(self, pk: Any) -> Any:
        return None

    async def list(self, **kwargs: Any) -> tuple[list[Any], int]:
        return [], 0

    async def create(self, data: dict[str, Any]) -> Any:
        return None

    async def update(self, pk: Any, data: dict[str, Any]) -> Any:
        return None

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
        return [ChoiceItem(value="1", label="UK", selected=False)]


def _make_request(query_string: str = "") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": query_string.encode(),
        "headers": [],
        "app": SimpleNamespace(
            url_path_for=lambda name, **kw: SimpleNamespace(
                make_absolute_url=lambda base_url=None, **kwargs: f"/{name}"
            )
        ),
    }
    return Request(scope)


@pytest.fixture
def view():
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="src/hyperadmin/templates")
    adapter = StubAdapter(City)
    options = AdminOptions(dependent_fields={"country_id": "region_id"})
    return dynamic_module.DynamicModelView(
        adapter=adapter,
        options=options,
        templates=templates,
        app_label=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_choices_view_forwards_extra_filters(view):
    """Extra query params (parent field values) are forwarded as kwargs to get_choices."""
    view.adapter.get_choices = AsyncMock(return_value=[])
    request = _make_request("country_id=3&q=&limit=50&offset=0")
    await view.choices_view(request, field_name="country", q="", limit=50, offset=0)
    view.adapter.get_choices.assert_awaited_once_with(
        "country", q="", limit=50, offset=0, country_id="3"
    )


@pytest.mark.anyio
async def test_choices_view_no_extra_filters(view):
    """When no extra params, get_choices is called without filters."""
    view.adapter.get_choices = AsyncMock(return_value=[])
    request = _make_request("q=&limit=50&offset=0")
    await view.choices_view(request, field_name="country", q="", limit=50, offset=0)
    view.adapter.get_choices.assert_awaited_once_with("country", q="", limit=50, offset=0)


def test_admin_options_dependent_fields_default():
    opts = AdminOptions()
    assert opts.dependent_fields == {}


def test_admin_options_dependent_fields_custom():
    opts = AdminOptions(dependent_fields={"city": "country_id"})
    assert opts.dependent_fields == {"city": "country_id"}


def test_relation_select_widget_dependent_on():
    widget = RelationSelectWidget(
        choices_url="/city/choices/country", preload=False, dependent_on="region_id"
    )
    assert widget.dependent_on == "region_id"


def test_relation_select_widget_dependent_on_none_default():
    widget = RelationSelectWidget(choices_url="/city/choices/country")
    assert widget.dependent_on is None


@pytest.mark.anyio
async def test_build_relation_widgets_wires_dependent_on(view):
    """_build_relation_widgets picks up dependent_fields from AdminOptions."""
    with patch("hyperadmin.views.dynamic.classify_field") as mock_classify:
        from hyperadmin.core.choices import SelectFieldMeta

        mock_classify.return_value = SelectFieldMeta(
            choices_source="relation", preload=False, multiple=False
        )
        view.adapter.get_choices = AsyncMock(return_value=[])
        widgets = await view._build_relation_widgets(field_names=[], selected_values={})

    # "country_id" field should get dependent_on="region_id" from options.dependent_fields
    assert "country_id" in widgets
    w = widgets["country_id"]
    assert isinstance(w, RelationSelectWidget)
    assert w.dependent_on == "region_id"
