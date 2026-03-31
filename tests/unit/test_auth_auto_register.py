"""Tests for auto-registration of auth models when auth_backend is set (#361).

TDD: Verify that User, Group, Permission are registered with correct
AdminOptions when mount() is called with an auth_backend configured.
"""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from hyperadmin.auth.models import Group, Permission, User
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site


@pytest.fixture
def async_engine(tmp_path):
    """Create an async engine (no tables needed — registration is sync)."""
    db_file = tmp_path / "test_auto_reg.db"
    return create_async_engine(f"sqlite+aiosqlite:///{db_file}")


@pytest.fixture(autouse=True)
def clean_registry():
    """Save and restore registry state to prevent leaking between tests."""
    saved = dict(site._registry)
    yield
    site._registry = saved


def _build_auth_admin(async_engine):
    """Build Admin with auth_backend enabled."""
    from fastapi import FastAPI

    from hyperadmin.auth.permissions import (
        ModelPermissionChecker,
        PermissionSyncService,
    )
    from hyperadmin.auth.session import SessionAuthBackend
    from hyperadmin.core.app import Admin

    app = FastAPI()
    backend = SessionAuthBackend(engine=async_engine)
    admin = Admin(
        app,
        engine=async_engine,
        create_tables=False,
        auth_backend=backend,
        permission_checker=ModelPermissionChecker(engine=async_engine),
        permission_registry=PermissionSyncService(engine=async_engine),
        session_secret="test-secret",
    )
    return admin


class TestAuthAutoRegistration:
    def test_auth_models_registered_on_mount(self, async_engine):
        """User, Group, Permission appear in registry after mount()."""
        admin = _build_auth_admin(async_engine)
        admin.mount("/admin")

        assert User in site._registry
        assert Group in site._registry
        assert Permission in site._registry

    def test_user_options(self, async_engine):
        """User registered with can_delete=False and list_filter."""
        admin = _build_auth_admin(async_engine)
        admin.mount("/admin")

        user_admin = site._registry[User]
        opts: AdminOptions = user_admin.options
        assert opts.can_delete is False
        assert "is_active" in opts.list_filter
        assert "is_superuser" in opts.list_filter

    def test_permission_options(self, async_engine):
        """Permission registered with can_create=False, can_delete=False."""
        admin = _build_auth_admin(async_engine)
        admin.mount("/admin")

        perm_admin = site._registry[Permission]
        opts: AdminOptions = perm_admin.options
        assert opts.can_create is False
        assert opts.can_delete is False

    def test_group_default_options(self, async_engine):
        """Group registered with default AdminOptions."""
        admin = _build_auth_admin(async_engine)
        admin.mount("/admin")

        group_admin = site._registry[Group]
        opts: AdminOptions = group_admin.options
        assert opts.can_create is True
        assert opts.can_delete is True
        assert opts.can_edit is True

    def test_skip_already_registered(self, async_engine):
        """If auth models are already registered, skip silently."""
        custom_opts = AdminOptions(can_delete=True, list_filter=["username"])
        site.register(User, options=custom_opts)

        admin = _build_auth_admin(async_engine)
        admin.mount("/admin")

        # User keeps its original registration
        user_admin = site._registry[User]
        assert user_admin.options.can_delete is True
        assert user_admin.options.list_filter == ["username"]

        # Group and Permission are still auto-registered
        assert Group in site._registry
        assert Permission in site._registry

    def test_no_auth_backend_skips_registration(self, async_engine):
        """auth_backend=None → no auth models registered."""
        from fastapi import FastAPI

        from hyperadmin.core.app import Admin

        app = FastAPI()
        admin = Admin(app, engine=async_engine, create_tables=False)
        admin.mount("/admin")

        assert User not in site._registry
        assert Group not in site._registry
        assert Permission not in site._registry
