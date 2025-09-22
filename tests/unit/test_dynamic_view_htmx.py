from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import Response

from hyperadmin.views import dynamic as dynamic_module


class DummyAdapter:
    def __init__(self, model):
        self.model = model


class DummyModel:
    __name__ = "User"
    # mimic Pydantic v2 .model_fields
    model_fields = {"name": object(), "is_active": object()}


class FakeHtmxResponder:
    """Fake replacement for HtmxTemplateResponse used to observe calls."""

    def __init__(self, templates):  # pragma: no cover - simple passthrough
        self.templates = templates

    def render(
        self,
        *,
        template_name: str,
        context: dict,
        request: Request,
        block: str | None,
        status_code: int | None = None,
    ):
        # Assert that DynamicModelView requests the inner form block
        assert block == "form_body"
        # Return a recognizable Response
        return Response(content=f"BLOCK:{template_name}")


@pytest.fixture
def request_factory():
    def _make(headers: dict[str, str] | None = None) -> Request:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
            "app": SimpleNamespace(url_path_for=lambda name, **kw: f"/{name}"),
        }
        return Request(scope)

    return _make


@pytest.fixture(autouse=True)
def patch_htmx(monkeypatch):
    # Patch HtmxTemplateResponse class used in dynamic module
    monkeypatch.setattr(dynamic_module, "HtmxTemplateResponse", FakeHtmxResponder)


def make_view(tmp_path):
    # Build a minimal Jinja2Templates that points to real templates dir so that
    # _get_template_name resolves create/update.html present in the repo.
    from fastapi.templating import Jinja2Templates

    templates = Jinja2Templates(directory="src/hyperadmin/templates")

    view = dynamic_module.DynamicModelView(
        adapter=DummyAdapter(DummyModel),
        options=SimpleNamespace(),
        templates=templates,
        app_label=None,
    )
    return view


def test_create_form_view_uses_block_for_htmx(request_factory, tmp_path):
    view = make_view(tmp_path)
    req = request_factory({"hx-request": "true"})

    resp = (
        pytest.run(async_fn=view.create_form_view, request=req) if hasattr(pytest, "run") else None
    )
    # Since we cannot rely on pytest.anyio here, call through AnyIO directly
    # Fallback: emulate minimal async call
    import anyio

    async def call():
        return await view.create_form_view(req)

    resp = anyio.run(call)

    assert isinstance(resp, Response)
    assert resp.text.startswith("BLOCK:")
    assert resp.text.endswith("create.html")


def test_update_form_view_uses_block_for_htmx(request_factory, tmp_path):
    view = make_view(tmp_path)

    # Patch adapter.get to return an object representing the item
    async def fake_get(pk: int):
        return SimpleNamespace(id=pk, model_dump=lambda: {"id": pk, "name": "X"})

    view.adapter.get = fake_get  # type: ignore[attr-defined]

    req = request_factory({"hx-request": "true"})

    import anyio

    async def call():
        return await view.update_form_view(req, item_id=1)

    resp = anyio.run(call)

    assert isinstance(resp, Response)
    assert resp.text.startswith("BLOCK:")
    assert resp.text.endswith("update.html")
