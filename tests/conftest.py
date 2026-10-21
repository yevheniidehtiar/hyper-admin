from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from typing import Any, TypeVar

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from hyperadmin.core.csrf import CsrfTokenSigner

# WIP: oauth backend test requires cryptography + providers/tokens modules not yet merged.
# Remove this entry once the oauth package is complete (issue #441).
collect_ignore = ["unit/test_oauth_backend.py"]

_ClientT = TypeVar("_ClientT", bound="httpx.Client | httpx.AsyncClient")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _dispose_async_engines(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Dispose every ``AsyncEngine`` a test created once the test is over.

    Most tests build a throw-away ``sqlite+aiosqlite`` engine and never dispose
    it. Its pooled connections are then closed by the garbage collector, from
    ``aiosqlite.Connection.__del__``, which binds the close request to whatever
    event loop happens to be current at that moment: usually a loop of a later
    test that closes before the connection's worker thread answers, so the
    thread dies with ``RuntimeError: Event loop is closed`` and pytest reports
    a ``PytestUnhandledThreadExceptionWarning`` against an unrelated test.
    Closing the connections deterministically, inside a live loop, removes the
    race; it also keeps the worker-thread count flat under ``pytest -n auto``.

    Engines created before the test (module-level or higher-scoped fixtures)
    are not tracked: disposing them would drop their in-memory databases.
    """
    created: list[AsyncEngine] = []
    original_init = AsyncEngine.__init__

    def tracking_init(self: AsyncEngine, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        created.append(self)

    monkeypatch.setattr(AsyncEngine, "__init__", tracking_init)
    yield
    monkeypatch.undo()

    async def dispose_all() -> None:
        for engine in created:
            await engine.dispose()

    if created:
        # On a helper thread with a loop of its own: the Playwright sync API keeps
        # a loop running on the test thread, where ``asyncio.run`` would refuse.
        worker = threading.Thread(target=asyncio.run, args=(dispose_all(),), name="dispose-engines")
        worker.start()
        worker.join()


def with_csrf(
    client: _ClientT,
    secret_key: str,
    *,
    cookie_name: str = "hyperadmin_csrf",
    header_name: str = "X-CSRF-Token",
) -> _ClientT:
    """Give ``client`` a valid CSRF cookie and token pair (SDD D.1), then return it.

    The token is signed with the admin's ``secret_key``, set as the
    ``hyperadmin_csrf`` cookie and sent as the ``X-CSRF-Token`` header on every
    request, so tests that POST to an admin with CSRF enforced (any auth
    configured) pass the double-submit check. Works for ``TestClient`` and
    ``httpx.AsyncClient`` alike.
    """
    token = CsrfTokenSigner(secret_key).issue()
    client.cookies.set(cookie_name, token)
    client.headers[header_name] = token
    return client


@pytest.fixture
def csrf_client() -> Any:
    """The :func:`with_csrf` helper, as a fixture: ``csrf_client(client, secret_key)``."""
    return with_csrf
