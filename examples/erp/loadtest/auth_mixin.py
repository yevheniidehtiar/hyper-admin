"""Session-auth mixin for Locust users.

HyperAdmin uses cookie-session auth, so each simulated user logs in once in ``on_start`` and
relies on Locust's per-user ``requests.Session`` to carry the session cookie on every
subsequent request. A failed login stops that user rather than letting it hammer the login
wall with unauthenticated traffic that would skew the stats.

Password hashing makes a login cost about a second of CPU, so with hundreds of users the login
burst can outlast the whole measurement window. ``LOADTEST_LOGIN_SESSIONS=N`` caps the logins
at ``N`` per Locust process: the first ``N`` users log in and every later user reuses one of
their session cookies. Unset (the default), every user logs in.
"""

from __future__ import annotations

import logging
import os
import random
import re
from http import HTTPStatus

import gevent
from locust.exception import StopUser

from examples.erp.loadtest import endpoints

logger = logging.getLogger(__name__)

# Substring the login page renders on bad credentials (see auth/views.py).
_LOGIN_ERROR_MARKER = "Invalid username or password"

# The CSRF token the login form carries (``csrf_input()`` in templates/login.html).
_CSRF_INPUT = re.compile(r'name="csrf_token" value="([^"]+)"')

# Header every later unsafe request sends the token in (``settings.csrf_header_name``).
CSRF_HEADER = "X-CSRF-Token"

# Logged-in sessions this process may hand out (LOADTEST_LOGIN_SESSIONS), how many logins it
# has started, and the (cookies, CSRF token) of each finished one.
_SESSION_LIMIT = int(os.environ.get("LOADTEST_LOGIN_SESSIONS", "0"))
_logins_started = 0
_sessions: list[tuple[dict[str, str], str]] = []


class HyperAdminAuthMixin:
    """Mix in before ``HttpUser`` to authenticate via ``POST {ADMIN_PREFIX}/login``."""

    login_path = f"{endpoints.ADMIN_PREFIX}/login"

    def on_start(self) -> None:
        global _logins_started  # noqa: PLW0603 - per-process session pool shared by all users
        if _SESSION_LIMIT and _logins_started >= _SESSION_LIMIT:
            self._reuse_session()
            return
        _logins_started += 1
        self._login()
        if _SESSION_LIMIT:
            _sessions.append(
                (self.client.cookies.get_dict(), self.client.headers.get(CSRF_HEADER, ""))
            )

    def _reuse_session(self) -> None:
        """Copy the cookies and CSRF token of a session another user of this process opened."""
        for _ in range(600):  # wait up to a minute for the first login to finish
            if _sessions:
                break
            gevent.sleep(0.1)
        else:
            logger.error("No logged-in session to reuse — stopping user")
            raise StopUser
        cookies, token = random.choice(_sessions)  # noqa: S311 - load spreading, not security
        self.client.cookies.update(cookies)
        if token:
            self.client.headers[CSRF_HEADER] = token

    def _login(self) -> None:
        username = os.environ.get("LOADTEST_USER", "admin")
        password = os.environ.get("LOADTEST_PASSWORD", "admin")
        # The admin enforces CSRF (signed double-submit): GET the login page for the token and
        # its cookie, post the token with the form, then send it as a header on every later
        # POST/PUT/DELETE. The token is tied to the cookie, not the login, so it stays valid.
        page = self.client.get(self.login_path, name="GET /admin/login")
        match = _CSRF_INPUT.search(page.text)
        token = match.group(1) if match else ""
        if token:
            self.client.headers[CSRF_HEADER] = token
        with self.client.post(
            self.login_path,
            data={"username": username, "password": password, "csrf_token": token},
            name="POST /admin/login",
            catch_response=True,
        ) as response:
            # On success the POST 302-redirects to /admin/ and is followed to a 200. On failure
            # the login form is re-rendered (still 200) with an error marker.
            if response.status_code == HTTPStatus.OK and _LOGIN_ERROR_MARKER not in response.text:
                response.success()
                return
            response.failure(f"login failed for {username!r}: status={response.status_code}")
            logger.error(
                "Locust user could not authenticate as %r (status %s) — stopping user",
                username,
                response.status_code,
            )
            raise StopUser
