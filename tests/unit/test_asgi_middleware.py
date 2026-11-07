"""Plain-ASGI contract tests for LocaleMiddleware and AuthenticationMiddleware.

Covers the scenarios of docs/specs/asgi-middleware.md (st-perf-03).
"""

from __future__ import annotations

from typing import Any

import pytest

from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.i18n.middleware import LocaleMiddleware

pytestmark = pytest.mark.anyio


class _Recorder:
    """Inner ASGI app recording the scope it receives."""

    def __init__(self) -> None:
        self.scopes: list[dict[str, Any]] = []

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.scopes.append(scope)
        if scope["type"] == "http":
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})


async def _noop_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _discard(message: dict[str, Any]) -> None:
    return None


def _http_scope(
    headers: list[tuple[bytes, bytes]] | None = None, path: str = "/"
) -> dict[str, Any]:
    return {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": headers or [],
    }


@pytest.mark.parametrize("scope_type", ["websocket", "lifespan"])
async def test_locale_non_http_scopes_pass_through_untouched(scope_type: str) -> None:
    """
    Scenario: non-HTTP scopes pass through untouched
      Given the admin app
      When  a websocket or lifespan scope arrives
      Then  each middleware forwards it to the inner app
    """
    inner = _Recorder()
    mw = LocaleMiddleware(inner, HyperAdminSettings())
    scope: dict[str, Any] = {"type": scope_type}

    await mw(scope, _noop_receive, _discard)

    assert inner.scopes == [scope]
    assert "state" not in scope


async def test_locale_sets_state_and_content_language_header() -> None:
    """
    Scenario: locale is negotiated, stored on scope state and echoed in the header
      Given supported locales and a locale cookie
      When  an http request passes the middleware
      Then  scope["state"]["locale"] is set and Content-Language is on the response
    """
    inner = _Recorder()
    mw = LocaleMiddleware(inner, HyperAdminSettings())
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    scope = _http_scope([(b"cookie", b"hyperadmin_locale=es")])
    await mw(scope, _noop_receive, send)

    assert scope["state"]["locale"] == "es"
    assert (b"content-language", b"es") in sent[0]["headers"]
    assert sent[1]["body"] == b"ok"


async def test_locale_header_disabled_leaves_response_untouched() -> None:
    """
    Scenario: locale_response_header=False omits Content-Language
      Given locale_response_header is false
      When  an http request passes the middleware
      Then  the response has no Content-Language header
    """
    inner = _Recorder()
    mw = LocaleMiddleware(inner, HyperAdminSettings(locale_response_header=False))
    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await mw(_http_scope(), _noop_receive, send)

    assert not any(k == b"content-language" for k, _ in sent[0]["headers"])
