"""Unit tests for DynamicModelView.choices_view() — HTMX autocomplete endpoint."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import builtins
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import BaseModel
from starlette.requests import Request

from hyperadmin.core.adapters import BaseAdapter
from hyperadmin.core.choices import ChoiceItem
from hyperadmin.views import dynamic as dynamic_module

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class User(BaseModel):
    name: str
    country_id: int | None = None


class StubAdapter(BaseAdapter):
    def __init__(self, model):
        self.model = model
        # Simulate inspector with a "country" relationship
        rel = SimpleNamespace(
            key="country",
            local_columns=[SimpleNamespace(key="country_id", name="country_id")],
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
        return [
            ChoiceItem(value="1", label="UK", selected=False),
            ChoiceItem(value="2", label="France", selected=False),
        ]


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
def view(tmp_path):
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="src/hyperadmin/templates")
    adapter = StubAdapter(User)
    return dynamic_module.DynamicModelView(
        adapter=adapter,
        options=SimpleNamespace(),
        templates=templates,
        app_label=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_choices_view_returns_html_options(view):
    request = _make_request()
    response = await view.choices_view(request, field_name="country")
    assert response.media_type == "text/html"
    content = response.body.decode()
    assert "UK" in content
    assert "France" in content


@pytest.mark.anyio
async def test_choices_view_limit_exceeds_max_returns_400(view):
    request = _make_request()
    with pytest.raises(HTTPException) as exc_info:
        await view.choices_view(request, field_name="country", limit=201)
    assert exc_info.value.status_code == 400
    assert "exceeds maximum" in exc_info.value.detail


@pytest.mark.anyio
async def test_choices_view_unknown_field_returns_404(view):
    request = _make_request()
    with pytest.raises(HTTPException) as exc_info:
        await view.choices_view(request, field_name="nonexistent")
    assert exc_info.value.status_code == 404


@pytest.mark.anyio
async def test_choices_view_passes_q_to_adapter(view):
    """Assert that the search query is forwarded to the adapter."""
    request = _make_request()
    view.adapter.get_choices = AsyncMock(
        return_value=[ChoiceItem(value="1", label="UK", selected=False)]
    )
    await view.choices_view(request, field_name="country", q="uk")
    view.adapter.get_choices.assert_awaited_once_with("country", q="uk", limit=50, offset=0)


@pytest.mark.anyio
async def test_choices_view_pagination(view):
    """Assert that limit/offset are forwarded to the adapter."""
    request = _make_request()
    view.adapter.get_choices = AsyncMock(return_value=[])
    await view.choices_view(request, field_name="country", limit=10, offset=20)
    view.adapter.get_choices.assert_awaited_once_with("country", q="", limit=10, offset=20)
