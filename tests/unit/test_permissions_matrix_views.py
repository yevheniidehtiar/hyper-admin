"""Permission-matrix routes, conflict handling and audit trail (st-v057-pmx-02).

Scenarios from ``docs/specs/permission-matrix-ui.md`` and the story
``.meta/epics/epic-v057-permissions-matrix/stories/featviews-matrix-routes-and-audit.md``,
run end to end through a real admin with built-in auth over SQLite.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlmodel import Field, SQLModel, select
from starlette.requests import Request

from hyperadmin.auth.backend import hash_password
from hyperadmin.auth.bridge import ExternalAuth
from hyperadmin.auth.models import Group, GroupPermission, Permission, User, UserPermission
from hyperadmin.auth.permissions import ModelPermissionChecker, PermissionSyncService
from hyperadmin.auth.session import SessionAuthBackend
from hyperadmin.core.app import Admin
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.permissions import (
    OBJECT_RULE_ADDED,
    OBJECT_RULE_REMOVED,
    PERMISSION_CHANGE,
    GroupNotFoundError,
    GroupObjectPermission,
    MatrixCell,
    MatrixChange,
    MatrixGrid,
    MatrixRow,
    ObjectRuleKey,
    ObjectRuleService,
    PermissionAudit,
    PermissionMatrixService,
    audit_for_group,
    audit_rows,
    object_rule_row,
    write_audit,
)
from hyperadmin.views import permissions_matrix as views
from hyperadmin.views.permissions_matrix import PLUGIN_NAME, SAVED_TRIGGER, PermissionMatrixPage
from tests.conftest import with_csrf

pytestmark = pytest.mark.anyio

SECRET = "test-secret"
PASSWORD = "password123"
MATRIX = "/admin/permissions-matrix/"
SAVE = "/admin/permissions-matrix/save"
HTML = {"accept": "text/html"}
HX = {"hx-request": "true"}


class Article(SQLModel, table=True):
    __tablename__ = "pmx_articles"  # type: ignore[reportIncompatibleVariableOverride]
    id: int | None = Field(default=None, primary_key=True)
    title: str = ""


class Invoice(SQLModel, table=True):
    __tablename__ = "pmx_invoices"  # type: ignore[reportIncompatibleVariableOverride]
    id: int | None = Field(default=None, primary_key=True)
    number: str = ""


class ArticleAdmin(ModelAdmin):
    permissions = [("export_article", "Can export article")]


REGISTERED = [("article", ArticleAdmin), ("invoice", ModelAdmin)]
MATRIX_CODENAME = "change_groups_permissions"


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    saved = dict(site._registry)
    site._registry = {}
    yield
    site._registry = saved


@pytest.fixture
async def engine(tmp_path: Any) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pmx.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


async def _user(engine: AsyncEngine, username: str, *, superuser: bool = False) -> int:
    async with AsyncSession(engine) as session:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=hash_password(PASSWORD),
            is_superuser=superuser,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        return user.id


async def _grant_user(engine: AsyncEngine, user_id: int, *codenames: str) -> None:
    async with AsyncSession(engine) as session:
        ids = dict((await session.execute(select(Permission.codename, Permission.id))).all())
        for codename in codenames:
            session.add(UserPermission(user_id=user_id, permission_id=ids[codename]))
        await session.commit()


@pytest.fixture
async def seeded(engine: AsyncEngine) -> dict[str, int]:
    """Permissions synced; the Editors group holds view/change article; three users.

    ``super`` is a superuser; ``editor`` holds the matrix codename plus
    ``view_article``/``change_article``/``add_invoice``; ``nobody`` holds nothing.
    """
    sync = PermissionSyncService(engine=engine)
    await sync.sync_permissions(REGISTERED)
    await sync.sync_codenames([(MATRIX_CODENAME, "Can change group permissions", None)])
    async with AsyncSession(engine) as session:
        group = Group(name="Editors")
        session.add(group)
        await session.commit()
        await session.refresh(group)
        group_id = group.id
        assert group_id is not None
        ids = dict((await session.execute(select(Permission.codename, Permission.id))).all())
        for codename in ("view_article", "change_article"):
            session.add(GroupPermission(group_id=group_id, permission_id=ids[codename]))
        await session.commit()
    editor = await _user(engine, "editor")
    await _grant_user(
        engine, editor, MATRIX_CODENAME, "view_article", "change_article", "add_invoice"
    )
    return {
        "group": group_id,
        "super": await _user(engine, "super", superuser=True),
        "editor": editor,
        "nobody": await _user(engine, "nobody"),
    }


def _build(engine: AsyncEngine, *, models: bool = True, **settings: Any) -> tuple[Admin, FastAPI]:
    app = FastAPI()
    admin = Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key=SECRET, **settings),
        auth_backend=SessionAuthBackend(engine=engine),
        permission_checker=ModelPermissionChecker(engine=engine),
        permission_registry=PermissionSyncService(engine=engine),
    )
    if models:
        site.register(Article, admin_class=ArticleAdmin)
        site.register(Invoice, admin_class=ModelAdmin)
    admin.mount("/admin")
    return admin, app


@pytest.fixture
def app(engine: AsyncEngine, seeded: dict[str, int]) -> FastAPI:
    return _build(engine)[1]


@asynccontextmanager
async def _client(app: FastAPI, username: str | None = None) -> AsyncIterator[AsyncClient]:
    """An admin client with a CSRF pair, logged in as ``username`` when given."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with_csrf(client, SECRET)
        if username:
            await client.post("/admin/login", data={"username": username, "password": PASSWORD})
        yield client


async def _granted(engine: AsyncEngine, group_id: int) -> set[str]:
    async with AsyncSession(engine) as session:
        stmt = (
            select(Permission.codename)
            .join(GroupPermission, GroupPermission.permission_id == Permission.id)
            .where(GroupPermission.group_id == group_id)
        )
        return set((await session.execute(stmt)).scalars().all())


async def _version(engine: AsyncEngine, group_id: int) -> int:
    async with AsyncSession(engine) as session:
        group = await session.get(Group, group_id)
        assert group is not None
        return group.permissions_version


async def _audit(engine: AsyncEngine, group_id: int) -> list[PermissionAudit]:
    async with AsyncSession(engine) as session:
        return await audit_for_group(session, group_id)


def _envelope(group_id: int, version: int, *changes: tuple[str, str, bool]) -> dict[str, Any]:
    return {
        "group_id": group_id,
        "version": version,
        "changes": [{"model": m, "codename": c, "granted": g} for m, c, g in changes],
    }


# ── grid ───────────────────────────────────────────────────────────────────────


async def test_matrix_loads_with_current_grid_for_selected_group(app, seeded):
    """
    Scenario: matrix loads with current grid for selected group
      Given the Editors group holds view_article and change_article
      When  a superuser opens /admin/permissions-matrix/?group_id=<Editors>
      Then  the grid has a checkbox per model x action, checked where granted
      And   the page carries the group's version and the object-rule cells
    """
    async with _client(app, "super") as client:
        response = await client.get(MATRIX, params={"group_id": seeded["group"]}, headers=HTML)

    assert response.status_code == 200
    html = response.text
    assert 'data-testid="pmatrix-group-select"' in html
    assert 'data-testid="pmatrix-cell-article-view_article"' in html
    assert 'data-testid="pmatrix-cell-article-export_article"' in html
    assert 'data-testid="pmatrix-cell-invoice-add_invoice"' in html
    assert 'data-testid="pmatrix-select-all-view"' in html
    assert 'data-testid="pmatrix-object-cell-article"' in html
    assert 'data-testid="pmatrix-save-btn"' in html
    assert 'name="version" value="0"' in html
    assert 'data-testid="pmatrix-cell-article-change_article"' in html
    checked = html.index('data-testid="pmatrix-cell-article-change_article"')
    assert "checked" in html[checked : checked + 200]


async def test_grid_defaults_to_first_group_and_htmx_gets_the_grid_block(app, seeded):
    """
    Scenario: group switch swaps the grid without a page reload
      Given one group exists
      When  the page is requested without group_id, then again as an HTMX request
      Then  both show the Editors grid, and the HTMX response is the grid block only
    """
    async with _client(app, "super") as client:
        page = await client.get(MATRIX, headers=HTML)
        fragment = await client.get(MATRIX, params={"group_id": seeded["group"]}, headers=HX)

    assert page.status_code == 200
    assert f'<option value="{seeded["group"]}" selected>Editors</option>' in page.text
    assert fragment.status_code == 200
    assert "<html" not in fragment.text
    assert 'data-testid="pmatrix-cell-article-view_article"' in fragment.text


async def test_permission_codename_gates_access_to_the_matrix(app, seeded):
    """
    Scenario: permission codename gates access to the matrix
      Given the user lacks "change_groups_permissions"
      When  GET /admin/permissions-matrix/
      Then  response is 403
    """
    async with _client(app, "nobody") as client:
        response = await client.get(MATRIX, headers=HTML)
        save = await client.post(SAVE, json=_envelope(seeded["group"], 0))

    assert response.status_code == 403
    assert save.status_code == 403


async def test_sidebar_links_the_matrix_for_holders_of_the_codename(app, seeded):
    """
    Scenario: the sidebar entry follows the codename
      Given an editor holding change_groups_permissions and a user without it
      When  each opens the dashboard
      Then  only the editor sees the Permission matrix link
    """
    async with _client(app, "editor") as editor, _client(app, "nobody") as nobody:
        with_link = await editor.get("/admin/", headers=HTML)
        without = await nobody.get("/admin/", headers=HTML)

    testid = f"sidebar-plugin-{PLUGIN_NAME}-permissions-matrix"
    assert testid in with_link.text
    assert testid not in without.text


async def test_grid_for_a_deleted_group_is_a_404_with_the_group_gone_state(app, seeded):
    """
    Scenario: group deleted mid-edit
      When  the grid is requested for a group id that no longer exists
      Then  the response is 404 and shows the "group no longer exists" state
    """
    async with _client(app, "super") as client:
        response = await client.get(MATRIX, params={"group_id": 999}, headers=HTML)

    assert response.status_code == 404
    assert 'data-testid="pmatrix-group-gone"' in response.text


async def test_grid_without_groups_shows_an_empty_state(engine):
    """
    Scenario: no groups yet
      Given no group exists
      When  a superuser opens the matrix
      Then  the empty state asks to create a group first
    """
    await PermissionSyncService(engine=engine).sync_permissions(REGISTERED)
    await _user(engine, "super", superuser=True)
    _admin, app = _build(engine)
    async with _client(app, "super") as client:
        response = await client.get(MATRIX, headers=HTML)

    assert response.status_code == 200
    assert 'data-testid="pmatrix-empty"' in response.text
    assert "No groups yet" in response.text


async def test_empty_admin_registry_renders_the_no_models_notice(engine):
    """
    Scenario: empty admin registry
      Given no model is registered (and the auth models are not auto-registered)
      When  a superuser opens the matrix for a group
      Then  the grid is replaced by the "No registered models" notice
    """
    await _user(engine, "super", superuser=True)
    async with AsyncSession(engine) as session:
        session.add(Group(name="Editors"))
        await session.commit()
    _admin, app = _build(engine, models=False, register_auth_models=False)
    async with _client(app, "super") as client:
        response = await client.get(MATRIX, headers=HTML)

    assert response.status_code == 200
    assert "No registered models" in response.text


# ── save ───────────────────────────────────────────────────────────────────────


async def test_save_returns_200_with_hx_trigger_when_version_matches(app, engine, seeded):
    """
    Scenario: save returns 200 with HX-Trigger when version matches
      Given the user has change_groups_permissions and the grid at version 0
      When  POST /admin/permissions-matrix/save with a two-cell diff and version=0
      Then  response is 200 and HX-Trigger header is "permissions-saved"
      And   exactly those cells changed and the version is now 1
    """
    group = seeded["group"]
    async with _client(app, "editor") as client:
        response = await client.post(
            SAVE,
            json=_envelope(
                group, 0, ("article", "change_article", False), ("invoice", "add_invoice", True)
            ),
            headers=HX,
        )

    assert response.status_code == 200
    assert response.headers["HX-Trigger"] == SAVED_TRIGGER
    assert 'data-testid="pmatrix-saved-banner"' in response.text
    assert 'data-version="1"' in response.text
    assert await _granted(engine, group) == {"view_article", "add_invoice"}
    assert await _version(engine, group) == 1


async def test_save_returns_409_when_version_is_stale(app, engine, seeded):
    """
    Scenario: save returns 409 when version is stale
      Given another save bumped the group's version to 1
      When  POST with version=0
      Then  response is 409 and body contains "Permissions changed elsewhere"
      And   no permission rows are mutated
    """
    group = seeded["group"]
    async with _client(app, "super") as client:
        first = await client.post(
            SAVE, json=_envelope(group, 0, ("invoice", "add_invoice", True)), headers=HX
        )
        stale = await client.post(
            SAVE, json=_envelope(group, 0, ("article", "view_article", False)), headers=HX
        )

    assert first.status_code == 200
    assert stale.status_code == 409
    assert "Permissions changed elsewhere" in stale.text
    assert 'data-testid="pmatrix-conflict-banner"' in stale.text
    assert "HX-Trigger" not in stale.headers
    assert await _granted(engine, group) == {"view_article", "change_article", "add_invoice"}
    assert await _version(engine, group) == 1


async def test_tampered_version_is_treated_as_a_conflict(app, engine, seeded):
    """
    Scenario: browser sends a tampered version
      When  POST with version=-1
      Then  the response is 409 and nothing is written
    """
    async with _client(app, "super") as client:
        response = await client.post(
            SAVE, json=_envelope(seeded["group"], -1, ("invoice", "add_invoice", True)), headers=HX
        )

    assert response.status_code == 409
    assert await _granted(engine, seeded["group"]) == {"view_article", "change_article"}


async def test_audit_log_is_written_per_diff_cell_on_save(app, engine, seeded):
    """
    Scenario: audit log is written per diff cell on save
      Given a save diff of 3 cells
      When  the save commits
      Then  3 audit rows exist with action="permission_change" and matching payloads
    """
    group = seeded["group"]
    async with _client(app, "editor") as client:
        response = await client.post(
            SAVE,
            json=_envelope(
                group,
                0,
                ("article", "change_article", False),
                ("article", "view_article", False),
                ("invoice", "add_invoice", True),
            ),
            headers=HX,
        )

    assert response.status_code == 200
    rows = await _audit(engine, group)
    assert [(r.action, r.model, r.codename, r.before, r.after) for r in rows] == [
        (PERMISSION_CHANGE, "article", "view_article", True, False),
        (PERMISSION_CHANGE, "article", "change_article", True, False),
        (PERMISSION_CHANGE, "invoice", "add_invoice", False, True),
    ]
    assert {r.actor_key for r in rows} == {str(seeded["editor"])}
    assert {r.group_id for r in rows} == {group}


async def test_privilege_escalation_rejects_the_whole_save_with_403(app, engine, seeded):
    """
    Scenario: cell change touches a permission the user can't grant
      Given the editor holds add_invoice but not delete_invoice
      When  they grant delete_invoice and add_invoice in one save
      Then  the response is 403 listing the rejected cell
      And   nothing is written, not even the grantable cell, and no audit row exists
    """
    group = seeded["group"]
    async with _client(app, "editor") as client:
        response = await client.post(
            SAVE,
            json=_envelope(
                group, 0, ("invoice", "add_invoice", True), ("invoice", "delete_invoice", True)
            ),
            headers=HX,
        )

    assert response.status_code == 403
    assert 'data-testid="pmatrix-rejected-banner"' in response.text
    assert 'data-testid="pmatrix-rejected-delete_invoice"' in response.text
    assert 'data-testid="pmatrix-rejected-add_invoice"' not in response.text
    assert await _granted(engine, group) == {"view_article", "change_article"}
    assert await _version(engine, group) == 0
    assert await _audit(engine, group) == []


async def test_revoking_a_permission_the_editor_lacks_is_allowed(app, engine, seeded):
    """
    Scenario: only grants are checked against the editor's own permissions
      Given the editor does not hold export_article, which Editors does not have either
      When  they revoke view_article (held) and the grid otherwise matches
      Then  the save commits
    """
    group = seeded["group"]
    async with _client(app, "editor") as client:
        response = await client.post(
            SAVE, json=_envelope(group, 0, ("article", "view_article", False)), headers=HX
        )

    assert response.status_code == 200
    assert await _granted(engine, group) == {"change_article"}


async def test_save_for_a_deleted_group_returns_404(app, seeded):
    """
    Scenario: group deleted mid-edit
      When  the save names a group id that no longer exists
      Then  the response is 404 "Group not found" with the group-gone banner
    """
    async with _client(app, "super") as client:
        response = await client.post(SAVE, json=_envelope(999, 0), headers=HX)

    assert response.status_code == 404
    assert 'data-testid="pmatrix-group-gone"' in response.text


async def test_unknown_codename_in_the_diff_is_a_400(app, seeded):
    """
    Scenario: tampered payload names a codename the grid has no cell for
      When  the diff contains "launch_rocket"
      Then  the response is 400 naming the codename
    """
    async with _client(app, "super") as client:
        response = await client.post(
            SAVE, json=_envelope(seeded["group"], 0, ("rocket", "launch_rocket", True))
        )

    assert response.status_code == 400
    assert "launch_rocket" in response.json()["detail"]


async def test_invalid_payloads_are_a_400(app, seeded):
    """
    Scenario: malformed save payloads
      When  the JSON body is not an envelope, is not JSON at all, or the form lacks the ints
      Then  each response is 400 "Invalid save payload"
    """
    async with _client(app, "super") as client:
        shape = await client.post(SAVE, json={"group_id": "x"})
        broken = await client.post(
            SAVE, content=b"{not json", headers={"content-type": "application/json"}
        )
        form = await client.post(SAVE, data={"group_id": "abc", "version": ""})

    for response in (shape, broken, form):
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid save payload"


async def test_form_post_of_the_full_grid_computes_the_diff(app, engine, seeded):
    """
    Scenario: the page works without JavaScript
      Given the form posts every checked cell as "perm" values
      When  it is posted (not as HTMX) with change_article unchecked and add_invoice checked
      Then  the diff is computed against the grid, saved, and the full page shows the banner
    """
    group = seeded["group"]
    async with _client(app, "super") as client:
        response = await client.post(
            SAVE,
            data={
                "group_id": str(group),
                "version": "0",
                "perm": ["view_article", "add_invoice"],
            },
            headers=HTML,
        )

    assert response.status_code == 200
    assert "<html" in response.text
    assert 'data-testid="pmatrix-saved-banner"' in response.text
    assert 'name="version" value="1"' in response.text
    assert await _granted(engine, group) == {"view_article", "add_invoice"}


async def test_non_htmx_conflict_renders_the_whole_page_with_the_banner(app, seeded):
    """
    Scenario: a conflict without JavaScript
      When  a stale form post is sent as a plain browser request
      Then  the whole page comes back with status 409 and the conflict banner
    """
    async with _client(app, "super") as client:
        response = await client.post(
            SAVE,
            data={"group_id": str(seeded["group"]), "version": "7", "perm": []},
            headers=HTML,
        )

    assert response.status_code == 409
    assert "<html" in response.text
    assert 'data-testid="pmatrix-conflict-banner"' in response.text


async def test_audit_write_failure_rolls_back_the_save(app, engine, seeded, monkeypatch, caplog):
    """
    Scenario: audit writer raises
      Given the audit write fails
      When  a valid diff is saved
      Then  the response is 500 "save failed", the permission rows and version are
            unchanged, and the error is logged
    """

    async def boom(session: Any, rows: Any) -> None:
        raise RuntimeError("audit down")

    monkeypatch.setattr(views, "write_audit", boom)
    group = seeded["group"]
    async with _client(app, "super") as client:
        with caplog.at_level(logging.ERROR, logger="hyperadmin.views.permissions_matrix"):
            response = await client.post(
                SAVE, json=_envelope(group, 0, ("invoice", "add_invoice", True)), headers=HX
            )

    assert response.status_code == 500
    assert 'data-testid="pmatrix-failed-banner"' in response.text
    assert await _granted(engine, group) == {"view_article", "change_article"}
    assert await _version(engine, group) == 0
    assert "permission matrix save failed" in caplog.text


async def test_missing_permission_row_is_a_400(app, engine, seeded, monkeypatch):
    """
    Scenario: a codename in the grid has no Permission row any more
      Given the grid still lists export_article but its row was deleted after startup
      When  it is granted
      Then  the save answers 400 naming the codename and writes nothing
    """
    group = seeded["group"]
    async with _client(app, "super") as client:
        # The first admin request ran the startup permission sync; delete the row after it.
        async with AsyncSession(engine) as session:
            stmt = select(Permission).where(Permission.codename == "export_article")
            row = (await session.execute(stmt)).scalar_one()
            await session.delete(row)
            await session.commit()
        response = await client.post(
            SAVE, json=_envelope(group, 0, ("article", "export_article", True)), headers=HX
        )

    assert response.status_code == 400
    assert "export_article" in response.text
    assert await _version(engine, group) == 0


async def test_conflict_banner_fragment(app, seeded):
    """
    Scenario: the page fetches the conflict banner on its own
      When  GET /admin/permissions-matrix/conflict?group_id=<id>
      Then  the banner fragment with a reload link for that group is returned
    """
    async with _client(app, "super") as client:
        response = await client.get(
            "/admin/permissions-matrix/conflict", params={"group_id": seeded["group"]}
        )

    assert response.status_code == 200
    assert 'data-testid="pmatrix-conflict-banner"' in response.text
    assert f"?group_id={seeded['group']}" in response.text


# ── object rules ───────────────────────────────────────────────────────────────


async def test_object_permission_column_opens_the_popover(app, engine, seeded):
    """
    Scenario: object-permission column opens an inline popover
      Given the Editors group has 2 object rules on Article
      When  the popover for Editors/Article is requested by group name and by id
      Then  both entries are listed with a remove button, and the popover has an Add form
      And   the grid's object cell counts the two rules
    """
    group = seeded["group"]
    rules = ObjectRuleService(engine=engine)
    await rules.add(group, ObjectRuleKey("article", "change_article", "1"))
    await rules.add(group, ObjectRuleKey("article", "view_article", "2"))
    async with _client(app, "super") as client:
        by_name = await client.get("/admin/permissions-matrix/object/Editors/Article")
        by_id = await client.get(f"/admin/permissions-matrix/object/{group}/article")
        grid = await client.get(MATRIX, params={"group_id": group}, headers=HTML)

    assert by_name.status_code == 200
    assert by_id.status_code == 200
    for response in (by_name, by_id):
        assert response.text.count('data-testid="pmatrix-object-entry-') == 2
        assert response.text.count('data-testid="pmatrix-object-remove-') == 2
        assert 'data-testid="pmatrix-object-add"' in response.text
        assert '<option value="export_article">' in response.text
    cell = grid.text.index('data-testid="pmatrix-object-cell-article"')
    assert "2 rules" in grid.text[cell : cell + 400]


async def test_object_popover_unknown_group_or_model_is_404(app, seeded):
    """
    Scenario: the popover is asked for a group or model that does not exist
      Then  the response is 404 in each case
    """
    group = seeded["group"]
    async with _client(app, "super") as client:
        no_group = await client.get("/admin/permissions-matrix/object/Nobody/article")
        gone = await client.get("/admin/permissions-matrix/object/999/article")
        no_model = await client.get(f"/admin/permissions-matrix/object/{group}/widget")

    assert no_group.status_code == 404
    assert gone.status_code == 404
    assert no_model.status_code == 404


async def test_object_rule_add_and_remove_are_idempotent_and_audited(app, engine, seeded):
    """
    Scenario: object rules save at once and repeating a change is a no-op
      When  a rule is added, added again, removed and removed again
      Then  the first add and the first remove answer with HX-Trigger and an audit row
      And   the repeats say "No change" and send no trigger
    """
    group = seeded["group"]
    url = f"/admin/permissions-matrix/object/{group}/article"
    rule = {"codename": "change_article", "object_pk": "42"}
    async with _client(app, "editor") as client:
        added = await client.post(url, data={"op": "add", **rule})
        again = await client.post(url, data={"op": "add", **rule})
        removed = await client.post(url, data={"op": "remove", **rule})
        gone = await client.post(url, data={"op": "remove", **rule})

    assert added.status_code == 200
    assert added.headers["HX-Trigger"] == SAVED_TRIGGER
    assert "Rule for 42 added." in added.text
    assert added.text.count('data-testid="pmatrix-object-entry-') == 1
    assert again.status_code == 200
    assert "HX-Trigger" not in again.headers
    assert "No change." in again.text
    assert removed.headers["HX-Trigger"] == SAVED_TRIGGER
    assert "Rule for 42 removed." in removed.text
    assert 'data-testid="pmatrix-object-empty"' in removed.text
    assert "HX-Trigger" not in gone.headers
    rows = await _audit(engine, group)
    assert [(r.action, r.codename, r.object_pk, r.before, r.after) for r in rows] == [
        (OBJECT_RULE_ADDED, "change_article", "42", False, True),
        (OBJECT_RULE_REMOVED, "change_article", "42", True, False),
    ]
    async with AsyncSession(engine) as session:
        left = (await session.execute(select(GroupObjectPermission))).scalars().all()
    assert left == []


async def test_object_rule_grant_the_editor_lacks_is_rejected(app, engine, seeded):
    """
    Scenario: an object rule is a grant too
      Given the editor does not hold delete_article
      When  they add a delete_article rule
      Then  the response is 403 with the rejection status and nothing is written
    """
    group = seeded["group"]
    async with _client(app, "editor") as client:
        response = await client.post(
            f"/admin/permissions-matrix/object/{group}/article",
            data={"op": "add", "codename": "delete_article", "object_pk": "1"},
        )

    assert response.status_code == 403
    assert "You can only grant permissions you have yourself." in response.text
    assert await ObjectRuleService(engine=engine).rules_for(group, "article") == []


async def test_object_rule_invalid_posts_are_a_400(app, seeded):
    """
    Scenario: malformed object-rule posts
      When  the op is unknown, the codename is not one of the model's, or the pk is blank
      Then  each response is 400
    """
    url = f"/admin/permissions-matrix/object/{seeded['group']}/article"
    async with _client(app, "super") as client:
        bad_op = await client.post(
            url, data={"op": "toggle", "codename": "view_article", "object_pk": "1"}
        )
        bad_code = await client.post(
            url, data={"op": "add", "codename": "view_invoice", "object_pk": "1"}
        )
        blank = await client.post(url, data={"op": "add", "codename": "view_article"})

    assert bad_op.status_code == 400
    assert bad_code.status_code == 400
    assert blank.status_code == 400


async def test_object_rule_service_counts_and_lookups(engine, seeded):
    """
    Scenario: the service behind the popover
      Given rules on two models
      Then  counts_for groups them by model, rules_for returns one model's rules in order,
            and add / remove report whether a row was written
    """
    group = seeded["group"]
    service = ObjectRuleService(engine=engine)
    assert await service.add(group, ObjectRuleKey("article", "view_article", "b")) is True
    assert await service.add(group, ObjectRuleKey("article", "view_article", "a")) is True
    assert await service.add(group, ObjectRuleKey("invoice", "view_invoice", "1")) is True
    assert await service.add(group, ObjectRuleKey("invoice", "view_invoice", "1")) is False
    assert await service.counts_for(group) == {"article": 2, "invoice": 1}
    assert [r.object_pk for r in await service.rules_for(group, "article")] == ["a", "b"]
    assert await service.remove(group, ObjectRuleKey("invoice", "view_invoice", "1")) is True
    assert await service.remove(group, ObjectRuleKey("invoice", "view_invoice", "1")) is False
    assert await service.counts_for(group) == {"article": 2}


# ── registration ───────────────────────────────────────────────────────────────


async def test_matrix_disabled_at_config_returns_404(engine, seeded):
    """
    Scenario: matrix disabled at config returns 404
      Given HyperAdminSettings(permissions_matrix_enabled=False)
      When  GET /admin/permissions-matrix/
      Then  response is 404, the page is not in the plugin registry and the sidebar has no link
    """
    admin, app = _build(engine, permissions_matrix_enabled=False)
    async with _client(app, "super") as client:
        response = await client.get(MATRIX, headers=HTML)
        dashboard = await client.get("/admin/", headers=HTML)

    assert response.status_code == 404
    assert PLUGIN_NAME not in admin.plugins
    assert f"sidebar-plugin-{PLUGIN_NAME}" not in dashboard.text


async def test_matrix_codename_is_configurable_and_synced(engine):
    """
    Scenario: the gate codename comes from settings
      Given HyperAdminSettings(permissions_matrix_codename="manage_access")
      Then  the page gates on it and declares it as its plugin permission
    """
    admin, _app = _build(engine, permissions_matrix_codename="manage_access")
    page = admin.plugins[PLUGIN_NAME]
    assert isinstance(page, PermissionMatrixPage)
    assert page.codename == "manage_access"
    assert [p.codename for p in admin.plugins.permissions if p.plugin == PLUGIN_NAME] == [
        "manage_access"
    ]
    assert [e.permission for e in admin.plugins.nav_entries if e.plugin == PLUGIN_NAME] == [
        "manage_access"
    ]
    with pytest.raises(ValueError, match="permissions_matrix_codename"):
        HyperAdminSettings(secret_key=SECRET, permissions_matrix_codename="Not A Codename")


async def test_matrix_is_not_registered_without_auth_or_without_the_auth_models(engine, caplog):
    """
    Scenario: built-in auth models not registered
      Given an admin without auth, and one with ExternalAuth and no built-in auth models
      Then  neither registers the page; the bridge case is logged at INFO
      And   ExternalAuth with register_auth_models=True does register it
    """
    no_auth = Admin(FastAPI(), engine=engine, settings=HyperAdminSettings(create_tables=False))
    assert PLUGIN_NAME not in no_auth.plugins

    async def get_user(request: Any) -> Any:
        return SimpleNamespace(id=1, username="host", is_superuser=True)

    with caplog.at_level(logging.INFO, logger="hyperadmin"):
        bridge = Admin(
            FastAPI(),
            engine=engine,
            settings=HyperAdminSettings(create_tables=False, secret_key=SECRET),
            auth=ExternalAuth(get_user=get_user),
        )
    assert PLUGIN_NAME not in bridge.plugins
    assert "permission matrix not registered" in caplog.text

    with_models = Admin(
        FastAPI(),
        engine=engine,
        settings=HyperAdminSettings(
            create_tables=False, secret_key=SECRET, register_auth_models=True
        ),
        auth=ExternalAuth(get_user=get_user),
    )
    assert PLUGIN_NAME in with_models.plugins


async def test_without_a_permission_checker_every_authenticated_user_may_edit(engine, seeded):
    """
    Scenario: built-in auth without a permission checker
      Given Admin(auth_backend=...) and no permission_checker
      When  a non-superuser without the codename saves a grant
      Then  the request is allowed (there is nothing to check against)
    """
    app = FastAPI()
    admin = Admin(
        app,
        engine=engine,
        settings=HyperAdminSettings(create_tables=False, secret_key=SECRET),
        auth_backend=SessionAuthBackend(engine=engine),
    )
    site.register(Article, admin_class=ArticleAdmin)
    site.register(Invoice, admin_class=ModelAdmin)
    admin.mount("/admin")
    group = seeded["group"]
    async with _client(app, "nobody") as client:
        response = await client.post(
            SAVE, json=_envelope(group, 0, ("invoice", "add_invoice", True)), headers=HX
        )

    assert response.status_code == 200
    assert await _granted(engine, group) == {"view_article", "change_article", "add_invoice"}


async def test_request_without_a_user_is_refused(engine):
    """
    Scenario: the route class let a request through without a principal
      When  the page's access check runs on a request with no user
      Then  it raises 403 "Authentication required" (defence in depth)
    """
    admin, _app = _build(engine)
    page = admin.plugins[PLUGIN_NAME]
    assert isinstance(page, PermissionMatrixPage)
    request = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(HTTPException) as excinfo:
        await page._require_access(request)  # type: ignore[arg-type]
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "Authentication required"


# ── direct calls ───────────────────────────────────────────────────────────────
# The request-driven tests above exercise these branches too, but the Python
# tracer does not record handler lines that follow a greenlet switch (the ORM
# awaits) inside the ASGI stack. Calling the pieces directly keeps the patch
# coverage honest and pins their contracts on their own.


async def test_save_diff_runs_the_before_commit_hook_in_the_same_transaction(engine, seeded):
    """
    Scenario: the audit write is atomic with the save
      Given a hook that stages audit rows on the save's session
      When  save_diff commits
      Then  the rows are there with the permission change
      And   a hook that raises abandons the save: no rows, no bump
    """
    group = seeded["group"]
    service = PermissionMatrixService(engine=engine)
    changes = [MatrixChange("invoice", "add_invoice", True)]

    async def stage(session: Any) -> None:
        await write_audit(session, audit_rows("7", group, changes))

    assert await service.save_diff(group, 0, changes, before_commit=stage) == 1
    assert [(r.actor_key, r.codename, r.after) for r in await _audit(engine, group)] == [
        ("7", "add_invoice", True)
    ]

    async def boom(session: Any) -> None:
        raise RuntimeError("audit down")

    with pytest.raises(RuntimeError, match="audit down"):
        await service.save_diff(
            group, 1, [MatrixChange("invoice", "view_invoice", True)], before_commit=boom
        )
    assert await _granted(engine, group) == {"view_article", "change_article", "add_invoice"}
    assert await _version(engine, group) == 1


async def test_object_rule_service_stages_the_audit_row_with_the_write(engine, seeded):
    """
    Scenario: an object-rule change and its audit row commit together
      When  a rule is added, then removed, each with an audit row
      Then  both audit rows exist in order
    """
    group = seeded["group"]
    service = ObjectRuleService(engine=engine)
    key = ObjectRuleKey("article", "view_article", "5")
    rule = {"model": "article", "codename": "view_article", "object_pk": "5"}
    added = object_rule_row("7", group, added=True, **rule)
    removed = object_rule_row("7", group, added=False, **rule)
    assert await service.add(group, key, audit=added) is True
    assert await service.remove(group, key, audit=removed) is True
    assert [(r.action, r.object_pk) for r in await _audit(engine, group)] == [
        (OBJECT_RULE_ADDED, "5"),
        (OBJECT_RULE_REMOVED, "5"),
    ]


def _direct_request(app: FastAPI, *, content_type: str, body: bytes, user: Any = None) -> Request:
    """A request for calling a view directly, tagged like a mounted admin request."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/permissions-matrix/save",
        "root_path": "",
        "query_string": b"",
        "headers": [(b"content-type", content_type.encode()), (b"hx-request", b"true")],
        "app": app,
        "hyperadmin": {"namespace": "hyperadmin"},
        "state": {"user": user, "user_key": 7, "user_permissions": None},
    }
    sent = False

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def _json(app: FastAPI, payload: dict[str, Any], user: Any = None) -> Request:
    body = json.dumps(payload).encode()
    return _direct_request(app, content_type="application/json", body=body, user=user)


def _form(app: FastAPI, body: bytes, user: Any = None) -> Request:
    return _direct_request(
        app, content_type="application/x-www-form-urlencoded", body=body, user=user
    )


async def test_parse_save_reads_the_json_envelope_and_the_form(engine):
    """
    Scenario: the two save bodies
      Given a JSON envelope and a form post
      Then  the envelope becomes a diff and the form the set of checked cells
      And   a body that is not JSON, or a form without integer ids, is a 400
    """
    _admin, app = _build(engine)
    parse = PermissionMatrixPage._parse_save
    diff = await parse(_json(app, _envelope(3, 4, ("article", "view_article", False))))
    assert (diff.group_id, diff.version, diff.submitted) == (3, 4, {"view_article": False})

    form = await parse(_form(app, b"group_id=3&version=4&perm=view_article&perm=add_invoice"))
    assert (form.group_id, form.version, form.submitted) == (3, 4, None)
    grid = MatrixGrid(
        group_id=3,
        group_name="Editors",
        version=4,
        actions=("view", "add"),
        rows=(
            MatrixRow(
                "article",
                {"view": MatrixCell("view_article", True), "add": MatrixCell("add_article", True)},
            ),
        ),
    )
    assert form.values(grid) == {"view_article": True, "add_article": False}

    with pytest.raises(HTTPException) as broken:
        await parse(_direct_request(app, content_type="application/json", body=b"{nope"))
    assert broken.value.status_code == 400
    with pytest.raises(HTTPException) as ints:
        await parse(_form(app, b"group_id=x"))
    assert ints.value.status_code == 400


async def test_save_view_called_directly_handles_a_vanished_group(engine, seeded, monkeypatch):
    """
    Scenario: the group disappears before, or during, the save
      Given a superuser saving a grid
      When  the group is unknown at load time, or deleted between load and commit
      Then  both answer 404 with the group-gone banner
    """
    admin, app = _build(engine)
    page = admin.plugins[PLUGIN_NAME]
    assert isinstance(page, PermissionMatrixPage)
    superuser = SimpleNamespace(id=7, is_superuser=True)

    gone = await page.save_view(_json(app, _envelope(999, 0), superuser))
    assert gone.status_code == 404
    assert b'data-testid="pmatrix-group-gone"' in gone.body

    async def deleted(*args: Any, **kwargs: Any) -> int:
        raise GroupNotFoundError(seeded["group"])

    monkeypatch.setattr(page.matrix, "save_diff", deleted)
    payload = _envelope(seeded["group"], 0, ("invoice", "add_invoice", True))
    during = await page.save_view(_json(app, payload, superuser))
    assert during.status_code == 404
    assert b'data-testid="pmatrix-group-gone"' in during.body


async def test_object_save_view_called_directly(engine, seeded):
    """
    Scenario: the popover's add form, end to end in one call
      When  a superuser adds a rule, repeats it, removes it, and then posts an unknown op
      Then  add and remove send HX-Trigger, the repeat says "No change", the bad op is a 400
    """
    admin, app = _build(engine)
    page = admin.plugins[PLUGIN_NAME]
    assert isinstance(page, PermissionMatrixPage)
    superuser = SimpleNamespace(id=7, is_superuser=True)
    group = str(seeded["group"])
    rule = b"op=add&codename=view_article&object_pk=5"

    added = await page.object_save_view(_form(app, rule, superuser), group, "article")
    assert added.status_code == 200
    assert added.headers["HX-Trigger"] == SAVED_TRIGGER
    assert b"Rule for 5 added." in added.body
    again = await page.object_save_view(_form(app, rule, superuser), group, "article")
    assert b"No change." in again.body
    assert "HX-Trigger" not in again.headers
    removed = await page.object_save_view(
        _form(app, b"op=remove&codename=view_article&object_pk=5", superuser), group, "article"
    )
    assert removed.headers["HX-Trigger"] == SAVED_TRIGGER
    assert b"Rule for 5 removed." in removed.body
    with pytest.raises(HTTPException) as bad:
        await page.object_save_view(
            _form(app, b"op=toggle&codename=view_article&object_pk=5", superuser),
            group,
            "article",
        )
    assert bad.value.status_code == 400
