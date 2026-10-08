"""Query oracles on secret columns (st-v058-byoa-53).

Spec: ``docs/specs/bring-your-own-app.md`` sections D.2, D.3 and Owner decision 7.

Before the fix a user who can list a model could probe a secret column such as
``password_hash`` through four query paths (search, sort, URL filters and the
FK choices endpoint), and the detail and edit pages showed it outright. Each
test below reproduces one oracle and fails on the unfixed code.
"""

import re
from typing import Any, Optional

import anyio
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlalchemy import SQLAlchemyAdapter
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.auth.models import User as AuthUser
from hyperadmin.core.introspection import (
    infer_list_display,
    infer_list_filter,
    infer_search_fields,
)
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.sensitive import SENSITIVE_MARKER, is_sensitive, sensitive_field_names
from hyperadmin.core.settings import HyperAdminSettings

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class OrUser(SQLModel, table=True):
    __tablename__ = "oracle_user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = ""
    email: str = ""
    password_hash: str = ""
    api_key: str = Field(default="", schema_extra={"json_schema_extra": {SENSITIVE_MARKER: True}})
    is_active: bool = True


class OrOrder(SQLModel, table=True):
    __tablename__ = "oracle_order"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    customer_id: int | None = Field(default=None, foreign_key="oracle_user.id")

    customer: Optional[OrUser] = Relationship()  # noqa: UP045


class OrUserAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class OrActiveUserAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter

    def get_queryset(self, request: Request | None = None) -> dict[str, Any]:
        return {"is_active": True}


class OrOrderAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def _clean() -> Any:
    site._registry = {}
    yield
    site._registry = {}


# Default order is by id: zed-1, amy-2, bob-3.
# Sorting by password_hash would give amy-2, bob-3, zed-1.
_USERS = [
    {"id": 1, "username": "zed-1", "password_hash": "h3abc", "api_key": "key-zzz"},
    {"id": 2, "username": "amy-2", "password_hash": "h1abc", "api_key": "key-aaa"},
    {"id": 3, "username": "bob-3", "password_hash": "h2abc", "api_key": "key-bbb", "active": 0},
]


async def _seed(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        for u in _USERS:
            await conn.execute(
                text(
                    "INSERT INTO oracle_user (id, username, email, password_hash, api_key, "
                    "is_active) VALUES (:id, :username, '', :password_hash, :api_key, :active)"
                ),
                {**u, "active": u.get("active", 1)},
            )
        await conn.execute(text("INSERT INTO oracle_order (id, title) VALUES (1, 'o1')"))


def _client(
    user_admin: type[ModelAdmin] = OrUserAdmin,
    user_options: AdminOptions | None = None,
) -> tuple[TestClient, AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    anyio.run(_seed, engine)
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(OrUser, user_admin, options=user_options or AdminOptions())
    site.register(OrOrder, OrOrderAdmin, options=AdminOptions())
    admin.mount(path="/admin")
    return TestClient(app), engine


def _listed(html: str) -> list[str]:
    """Return the usernames in row order."""
    return re.findall(r"(zed-1|amy-2|bob-3)", html)


def _rows(client: TestClient, query: str) -> list[str]:
    resp = client.get(f"/admin/oruser?{query}", headers={"hx-request": "true"})
    assert resp.status_code == 200
    seen: list[str] = []
    for name in _listed(resp.text):
        if name not in seen:
            seen.append(name)
    return seen


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------


def test_unknown_sort_by_falls_back_to_the_default_sort() -> None:
    """Scenario: unknown sort_by falls back to the default sort."""
    client, _ = _client()

    assert _rows(client, "sort_by=nope") == ["zed-1", "amy-2", "bob-3"]


def test_sort_by_on_a_sensitive_field_is_ignored() -> None:
    """Scenario: sort_by on a sensitive field is ignored."""
    client, _ = _client()

    assert _rows(client, "sort_by=password_hash") == ["zed-1", "amy-2", "bob-3"]
    assert _rows(client, "sort_by=password_hash&sort_direction=desc") == [
        "zed-1",
        "amy-2",
        "bob-3",
    ]


def test_sort_by_a_displayed_column_still_works() -> None:
    client, _ = _client()

    assert _rows(client, "sort_by=username") == ["amy-2", "bob-3", "zed-1"]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_does_not_match_sensitive_fields() -> None:
    """Scenario: search does not match sensitive fields."""
    client, _ = _client()

    assert _rows(client, "search=abc") == []
    assert _rows(client, "search=key-") == []


def test_search_still_matches_regular_fields() -> None:
    client, _ = _client()

    assert _rows(client, "search=amy") == ["amy-2"]


@pytest.mark.anyio
@pytest.mark.parametrize("adapter_cls", [SQLModelAdapter, SQLAlchemyAdapter])
async def test_adapter_fallback_search_skips_sensitive_columns(adapter_cls: type) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _seed(engine)
    adapter = adapter_cls(OrUser, engine)

    items, total = await adapter.list(search="abc")

    assert (items, total) == ([], 0)


@pytest.mark.anyio
async def test_sqlalchemy_adapter_honours_search_fields() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _seed(engine)
    adapter = SQLAlchemyAdapter(OrUser, engine)

    items, _ = await adapter.list(search="amy", search_fields=["email"])

    assert items == []


# ---------------------------------------------------------------------------
# URL filters
# ---------------------------------------------------------------------------


def test_filtering_on_a_non_whitelisted_column_is_ignored() -> None:
    """Scenario: filtering on a non-whitelisted column is ignored."""
    client, _ = _client()

    assert _rows(client, "filter_password_hash=h1abc") == ["zed-1", "amy-2", "bob-3"]


def test_filtering_on_a_whitelisted_column_still_works() -> None:
    client, _ = _client()

    assert _rows(client, "filter_is_active=false") == ["bob-3"]


def test_explicit_list_filter_on_a_sensitive_field_is_ignored() -> None:
    client, _ = _client(user_options=AdminOptions(list_filter=["is_active", "password_hash"]))

    assert _rows(client, "filter_password_hash=h1abc") == ["zed-1", "amy-2", "bob-3"]


# ---------------------------------------------------------------------------
# Detail and edit pages
# ---------------------------------------------------------------------------


def test_detail_page_hides_sensitive_fields() -> None:
    """Scenario: detail page hides sensitive fields."""
    client, _ = _client()

    resp = client.get("/admin/oruser/1")

    assert resp.status_code == 200
    assert "zed-1" in resp.text
    for secret in ("h3abc", "key-zzz", ">Password Hash<", ">Api Key<"):
        assert secret not in resp.text


def test_edit_form_never_renders_the_stored_secret() -> None:
    client, _ = _client()

    resp = client.get("/admin/oruser/1/edit")

    assert resp.status_code == 200
    assert "h3abc" not in resp.text
    assert "key-zzz" not in resp.text


def test_empty_sensitive_submission_keeps_the_stored_value() -> None:
    client, engine = _client()

    resp = client.put(
        "/admin/oruser/1",
        data={
            "username": "zed-renamed",
            "email": "",
            "password_hash": "",
            "api_key": "",
            "is_active": "on",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303

    async def _row() -> Any:
        async with engine.connect() as conn:
            return (
                await conn.execute(
                    text("SELECT username, password_hash, api_key FROM oracle_user WHERE id = 1")
                )
            ).first()

    assert tuple(anyio.run(_row)) == ("zed-renamed", "h3abc", "key-zzz")


def test_non_empty_sensitive_submission_is_written() -> None:
    client, engine = _client()

    client.put(
        "/admin/oruser/1",
        data={"username": "zed-1", "email": "", "password_hash": "new", "is_active": "on"},
        follow_redirects=False,
    )

    async def _hash() -> Any:
        async with engine.connect() as conn:
            return (
                await conn.execute(text("SELECT password_hash FROM oracle_user WHERE id = 1"))
            ).scalar()

    assert anyio.run(_hash) == "new"


def test_sensitive_fields_option_overrides_in_both_directions() -> None:
    client, _ = _client(
        user_options=AdminOptions(sensitive_fields={"password_hash": False, "username": True})
    )

    resp = client.get("/admin/oruser/1")

    assert "h3abc" in resp.text
    assert ">Username<" not in resp.text


# ---------------------------------------------------------------------------
# Choices endpoint
# ---------------------------------------------------------------------------


def _choice_values(html: str) -> list[str]:
    return [v for v in re.findall(r'value="([^"]*)"', html) if v]


def test_choices_ignore_undeclared_cascade_parameters() -> None:
    """Scenario: choices ignore undeclared cascade parameters."""
    client, _ = _client()

    resp = client.get("/admin/ororder/choices/customer?password_hash=h1abc")

    assert resp.status_code == 200
    assert sorted(_choice_values(resp.text)) == ["1", "2", "3"]


def test_choices_apply_the_target_admin_queryset() -> None:
    """Scenario: choices apply the target admin queryset."""
    client, _ = _client(user_admin=OrActiveUserAdmin)

    resp = client.get("/admin/ororder/choices/customer")

    assert resp.status_code == 200
    assert sorted(_choice_values(resp.text)) == ["1", "2"]


def test_choices_search_does_not_match_sensitive_columns() -> None:
    client, _ = _client()

    resp = client.get("/admin/ororder/choices/customer?q=h1abc")

    assert resp.status_code == 200
    assert _choice_values(resp.text) == []


def test_choices_forward_a_declared_cascade_key() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    anyio.run(_seed, engine)
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(OrUser, OrUserAdmin, options=AdminOptions())
    site.register(
        OrOrder, OrOrderAdmin, options=AdminOptions(dependent_fields={"customer_id": "username"})
    )
    admin.mount(path="/admin")
    client = TestClient(app)

    resp = client.get("/admin/ororder/choices/customer?username=amy-2&email=nope")

    assert _choice_values(resp.text) == ["2"]


# ---------------------------------------------------------------------------
# core.sensitive and smart defaults
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["password", "password_hash", "hash", "api_secret", "secret_key", "refresh_token", "token"],
)
def test_secret_looking_names_are_sensitive(name: str) -> None:
    assert is_sensitive(name) is True


@pytest.mark.parametrize("name", ["username", "email", "hashtag", "passwords_page", "tokenizer"])
def test_regular_names_are_not_sensitive(name: str) -> None:
    assert is_sensitive(name) is False


def test_marker_makes_any_field_sensitive() -> None:
    assert is_sensitive("api_key", OrUser.model_fields["api_key"]) is True


def test_overrides_win_in_both_directions() -> None:
    overrides = {"password_hash": False, "email": True}
    assert is_sensitive("password_hash", overrides=overrides) is False
    assert is_sensitive("email", overrides=overrides) is True
    assert sensitive_field_names(OrUser, overrides) == {"api_key", "email"}


def test_builtin_user_password_hash_is_marked() -> None:
    extra = AuthUser.model_fields["password_hash"].json_schema_extra
    assert isinstance(extra, dict)
    assert extra.get(SENSITIVE_MARKER) is True


def test_inferred_defaults_exclude_sensitive_fields() -> None:
    for inferred in (infer_search_fields(OrUser), infer_list_display(OrUser)):
        assert "password_hash" not in inferred
        assert "api_key" not in inferred
    assert "password_hash" not in infer_list_filter(OrUser)
