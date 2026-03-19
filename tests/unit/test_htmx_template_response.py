from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest
from starlette.requests import Request
from starlette.responses import Response

from hyperadmin.views.htmx import HtmxTemplateResponse


class FakeTemplate:
    def __init__(self, blocks: dict[str, Callable]):
        self.blocks = blocks

    def new_context(self, context: dict[str, Any]):  # pragma: no cover - simple passthrough
        return context


class FakeTemplates:
    def __init__(self, template: FakeTemplate):
        # env with get_template
        self.env = SimpleNamespace(get_template=lambda _name: template)
        # TemplateResponse fallback path
        self._last_template_name: str | None = None
        self._last_context: dict[str, Any] | None = None
        self._last_status: int | None = None

    def TemplateResponse(  # noqa: N802
        self, template_name: str, context: dict[str, Any], status_code: int | None = None
    ):
        self._last_template_name = template_name
        self._last_context = context
        self._last_status = status_code
        # Return a distinctive Response to assert against
        return Response(
            content=f"FULL:{template_name}", media_type="text/html", status_code=status_code or 200
        )


@pytest.fixture
def request_factory():
    def _make(headers: dict[str, str] | None = None) -> Request:
        # Minimal ASGI scope for Request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        }
        return Request(scope)

    return _make


def test_htmx_renders_only_block_when_hx_and_block_present(request_factory):
    # Given a template with a block named 'fragment'
    template = FakeTemplate(blocks={"fragment": lambda _ctx: ["<div>Fragment</div>"]})
    templates = FakeTemplates(template)

    req = request_factory({"hx-request": "true"})

    resp = HtmxTemplateResponse(templates).render(
        template_name="dummy.html",
        context={"request": req},
        request=req,
        block="fragment",
        status_code=422,
    )

    assert isinstance(resp, Response)
    assert resp.status_code == 422
    assert resp.media_type == "text/html"
    assert resp.body.decode(resp.charset) == "<div>Fragment</div>"


def test_htmx_missing_block_falls_back_to_full_template(request_factory):
    template = FakeTemplate(blocks={})
    templates = FakeTemplates(template)

    req = request_factory({"hx-request": "true"})

    resp = HtmxTemplateResponse(templates).render(
        template_name="create.html",
        context={"request": req},
        request=req,
        block="form_body",
    )

    # Should use TemplateResponse fallback path
    assert isinstance(resp, Response)
    assert resp.body.decode(resp.charset).startswith("FULL:")
    assert templates._last_template_name == "create.html"
    assert templates._last_context == {"request": req}


def test_non_htmx_always_full_template_even_with_block(request_factory):
    template = FakeTemplate(blocks={"fragment": lambda _ctx: ["X"]})
    templates = FakeTemplates(template)

    req = request_factory()  # no HX header

    resp = HtmxTemplateResponse(templates).render(
        template_name="something.html",
        context={"request": req},
        request=req,
        block="fragment",
    )

    assert isinstance(resp, Response)
    assert resp.body.decode(resp.charset) == "FULL:something.html"
