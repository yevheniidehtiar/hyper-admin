from __future__ import annotations

from typing import Any, TypeVar

import httpx
import pytest

from hyperadmin.core.csrf import CsrfTokenSigner

# WIP: oauth backend test requires cryptography + providers/tokens modules not yet merged.
# Remove this entry once the oauth package is complete (issue #441).
collect_ignore = ["unit/test_oauth_backend.py"]

_ClientT = TypeVar("_ClientT", bound="httpx.Client | httpx.AsyncClient")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


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
