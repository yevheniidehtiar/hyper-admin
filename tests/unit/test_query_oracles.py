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
from hyperadmin.core.inlines import InlineModelSpec
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


# ---------------------------------------------------------------------------
# Review follow-ups
# ---------------------------------------------------------------------------

_SECRETS = ("h3abc", "h1abc", "h2abc", "key-zzz", "key-aaa", "key-bbb")


@pytest.mark.parametrize(
    "path",
    [
        "/admin/ororder",
        "/admin/ororder/create",
        "/admin/ororder/1/edit",
        "/admin/ororder/choices/customer",
    ],
)
def test_relation_labels_never_print_sensitive_values(path: str) -> None:
    """Scenario: relation labels never print a secret of the target row."""
    client, _ = _client()

    resp = client.get(path)

    assert resp.status_code == 200
    for secret in _SECRETS:
        assert secret not in resp.text
    assert "zed-1" in resp.text


def test_relation_labels_skip_an_override_sensitive_label_field() -> None:
    client, _ = _client(user_options=AdminOptions(sensitive_fields={"username": True}))

    resp = client.get("/admin/ororder/choices/customer")

    assert resp.status_code == 200
    assert "zed-1" not in resp.text
    assert sorted(_choice_values(resp.text)) == ["1", "2", "3"]


def test_writing_a_reference_to_a_row_hidden_by_the_target_admin_is_refused() -> None:
    """Scenario: a crafted write cannot link to a row the target admin hides."""
    client, engine = _client(user_admin=OrActiveUserAdmin)

    resp = client.put(
        "/admin/ororder/1", data={"title": "o1", "customer_id": "3"}, follow_redirects=False
    )

    assert resp.status_code == 422
    assert _scalar(engine, "SELECT customer_id FROM oracle_order WHERE id = 1") is None


def test_creating_with_a_reference_to_a_hidden_row_is_refused() -> None:
    client, engine = _client(user_admin=OrActiveUserAdmin)

    resp = client.post(
        "/admin/ororder", data={"title": "new", "customer_id": "3"}, follow_redirects=False
    )

    assert resp.status_code == 422
    assert _scalar(engine, "SELECT count(*) FROM oracle_order") == 1


def test_writing_a_reference_to_a_visible_row_still_works() -> None:
    client, engine = _client(user_admin=OrActiveUserAdmin)

    resp = client.put(
        "/admin/ororder/1", data={"title": "o1", "customer_id": "2"}, follow_redirects=False
    )

    assert resp.status_code == 303
    assert _scalar(engine, "SELECT customer_id FROM oracle_order WHERE id = 1") == 2


def _scalar(engine: AsyncEngine, sql: str) -> Any:
    async def _run() -> Any:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql))).scalar()

    return anyio.run(_run)


# Override-only sensitive field (no marker, no secret-looking name) -----------


class PbPerson(SQLModel, table=True):
    __tablename__ = "oracle_pb_person"

    id: int | None = Field(default=None, primary_key=True)
    ssn: str = ""
    age: int = 0


class PbVisit(SQLModel, table=True):
    __tablename__ = "oracle_pb_visit"

    id: int | None = Field(default=None, primary_key=True)
    note: str = ""
    person_id: int | None = Field(default=None, foreign_key="oracle_pb_person.id")

    person: Optional[PbPerson] = Relationship()  # noqa: UP045


class PbPersonAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class PbVisitAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


def _person_client() -> TestClient:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def _seed_people() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
            await conn.execute(
                text("INSERT INTO oracle_pb_person (id, ssn, age) VALUES (1, '111-22-3333', 30)")
            )

    anyio.run(_seed_people)
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(PbPerson, PbPersonAdmin, options=AdminOptions(sensitive_fields={"ssn": True}))
    site.register(PbVisit, PbVisitAdmin, options=AdminOptions())
    admin.mount(path="/admin")
    return TestClient(app)


def test_list_search_does_not_match_an_override_sensitive_field() -> None:
    """Scenario: a field made sensitive by the admin override is not searchable."""
    client = _person_client()

    def _row_count(term: str) -> int:
        resp = client.get(f"/admin/pbperson?search={term}", headers={"hx-request": "true"})
        assert resp.status_code == 200
        return resp.text.count('data-testid="list-row"')

    # The result must not depend on whether the term matches the secret.
    assert _row_count("111-22") == _row_count("zzzz-none")


def test_choices_search_does_not_match_an_override_sensitive_field() -> None:
    client = _person_client()

    hit = client.get("/admin/pbvisit/choices/person?q=111-22")
    miss = client.get("/admin/pbvisit/choices/person?q=zzzz-none")

    assert hit.status_code == miss.status_code == 200
    assert _choice_values(hit.text) == _choice_values(miss.text)


def test_choices_label_hides_an_override_sensitive_field() -> None:
    client = _person_client()

    resp = client.get("/admin/pbvisit/choices/person")

    assert _choice_values(resp.text) == ["1"]
    assert "111-22" not in resp.text


@pytest.mark.anyio
@pytest.mark.parametrize("adapter_cls", [SQLModelAdapter, SQLAlchemyAdapter])
async def test_empty_search_fields_disable_search(adapter_cls: type) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _seed(engine)

    items, total = await adapter_cls(OrUser, engine).list(search="zzz-none", search_fields=[])

    assert total == 3
    assert len(items) == 3


# Inline formsets with a secret column -----------------------------------------


class PbAccount(SQLModel, table=True):
    __tablename__ = "oracle_pb_account"

    id: int | None = Field(default=None, primary_key=True)
    name: str = ""

    api_keys: list["PbApiKey"] = Relationship(back_populates="account")


class PbApiKey(SQLModel, table=True):
    __tablename__ = "oracle_pb_api_key"

    id: int | None = Field(default=None, primary_key=True)
    account_id: int | None = Field(default=None, foreign_key="oracle_pb_account.id")
    name: str = ""
    api_token: str

    account: Optional[PbAccount] = Relationship(back_populates="api_keys")  # noqa: UP045


class PbAccountAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


def _account_client() -> tuple[TestClient, AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def _seed_accounts() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
            await conn.execute(text("INSERT INTO oracle_pb_account (id, name) VALUES (1, 'acme')"))
            await conn.execute(
                text(
                    "INSERT INTO oracle_pb_api_key (id, account_id, name, api_token) "
                    "VALUES (1, 1, 'ci', 'SUPERSECRETTOKEN')"
                )
            )

    anyio.run(_seed_accounts)
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(
        PbAccount,
        PbAccountAdmin,
        options=AdminOptions(
            inlines=[
                InlineModelSpec(model=PbApiKey, fk_field="account_id", relationship_name="api_keys")
            ]
        ),
    )
    admin.mount(path="/admin")
    return TestClient(app), engine


def test_inline_rows_never_render_a_stored_secret() -> None:
    """Scenario: an inline child's secret is write-only on the parent's edit page."""
    client, _ = _account_client()

    resp = client.get("/admin/pbaccount/1/edit")

    assert resp.status_code == 200
    assert "SUPERSECRETTOKEN" not in resp.text
    assert 'name="pbapikey-0-api_token"' in resp.text


def test_empty_inline_secret_keeps_the_stored_value() -> None:
    client, engine = _account_client()

    resp = client.put(
        "/admin/pbaccount/1",
        data={
            "name": "acme",
            "pbapikey-0-pk": "1",
            "pbapikey-0-name": "ci-renamed",
            "pbapikey-0-api_token": "",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert _scalar(engine, "SELECT name FROM oracle_pb_api_key WHERE id = 1") == "ci-renamed"
    assert (
        _scalar(engine, "SELECT api_token FROM oracle_pb_api_key WHERE id = 1")
        == "SUPERSECRETTOKEN"
    )


def test_non_empty_inline_secret_is_written() -> None:
    client, engine = _account_client()

    resp = client.put(
        "/admin/pbaccount/1",
        data={
            "name": "acme",
            "pbapikey-0-pk": "1",
            "pbapikey-0-name": "ci",
            "pbapikey-0-api_token": "rotated",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    assert _scalar(engine, "SELECT api_token FROM oracle_pb_api_key WHERE id = 1") == "rotated"


# Non-string fields matched by the name heuristic ------------------------------


class RvDoc(SQLModel, table=True):
    __tablename__ = "oracle_rv_doc"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    is_secret: bool = True


class RvMarked(SQLModel, table=True):
    __tablename__ = "oracle_rv_marked"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    flag: bool = Field(default=True, schema_extra={"json_schema_extra": {SENSITIVE_MARKER: True}})


class RvAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


def _doc_client() -> tuple[TestClient, AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def _seed_docs() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
            await conn.execute(
                text("INSERT INTO oracle_rv_doc (id, title, is_secret) VALUES (1, 'd', 0)")
            )
            await conn.execute(
                text("INSERT INTO oracle_rv_marked (id, title, flag) VALUES (1, 'm', 0)")
            )

    anyio.run(_seed_docs)
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(RvDoc, RvAdmin, options=AdminOptions())
    site.register(RvMarked, type("RvMarkedAdmin", (RvAdmin,), {}), options=AdminOptions())
    admin.mount(path="/admin")
    return TestClient(app), engine


def test_name_heuristic_only_applies_to_text_fields() -> None:
    assert is_sensitive("is_secret", RvDoc.model_fields["is_secret"]) is False
    assert is_sensitive("flag", RvMarked.model_fields["flag"]) is True
    assert "is_secret" not in sensitive_field_names(RvDoc)


def test_saving_a_form_as_rendered_keeps_a_secret_looking_boolean() -> None:
    """Scenario: a boolean named like a secret round-trips through the edit form."""
    client, engine = _doc_client()

    page = client.get("/admin/rvdoc/1/edit")
    resp = client.put("/admin/rvdoc/1", data={"title": "edited"}, follow_redirects=False)

    assert re.search(r'<input[^>]*name="is_secret"', page.text)
    assert not re.search(r'<input[^>]*name="is_secret"[^>]*checked', page.text)
    assert resp.status_code == 303
    assert _scalar(engine, "SELECT is_secret FROM oracle_rv_doc WHERE id = 1") == 0


def test_a_marked_non_text_field_is_left_out_of_the_edit_form() -> None:
    client, engine = _doc_client()

    page = client.get("/admin/rvmarked/1/edit")
    resp = client.put(
        "/admin/rvmarked/1", data={"title": "edited", "flag": "on"}, follow_redirects=False
    )

    assert 'name="flag"' not in page.text
    assert resp.status_code == 303
    assert _scalar(engine, "SELECT flag FROM oracle_rv_marked WHERE id = 1") == 0
