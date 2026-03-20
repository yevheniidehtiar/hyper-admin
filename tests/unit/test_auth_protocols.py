"""Tests for auth protocols and Admin integration (A2).

TDD: Verify protocol definitions, runtime_checkable, and Admin auth_backend parameter.
"""

from unittest.mock import AsyncMock

from fastapi import FastAPI


class TestProtocolDefinitions:
    def test_protocols_importable_from_core(self):
        from hyperadmin.core.auth import (
            AuthBackend,
            CurrentUserProvider,
            PermissionChecker,
            PermissionRegistry,
        )

        assert AuthBackend is not None
        assert CurrentUserProvider is not None
        assert PermissionChecker is not None
        assert PermissionRegistry is not None

    def test_auth_backend_is_runtime_checkable(self):
        from hyperadmin.core.auth import AuthBackend

        class MockBackend:
            async def authenticate(self, username: str, password: str):
                return None

            async def login(self, request, user):
                pass

            async def logout(self, request):
                pass

        assert isinstance(MockBackend(), AuthBackend)

    def test_permission_checker_is_runtime_checkable(self):
        from hyperadmin.core.auth import PermissionChecker

        class MockChecker:
            async def has_permission(self, user, codename: str) -> bool:
                return True

            async def get_user_permissions(self, user) -> set[str]:
                return set()

        assert isinstance(MockChecker(), PermissionChecker)

    def test_current_user_provider_is_runtime_checkable(self):
        from hyperadmin.core.auth import CurrentUserProvider

        class MockProvider:
            async def get_current_user(self, request):
                return None

        assert isinstance(MockProvider(), CurrentUserProvider)

    def test_permission_registry_is_runtime_checkable(self):
        from hyperadmin.core.auth import PermissionRegistry

        class MockRegistry:
            async def sync_permissions(self, registered_models: list) -> None:
                pass

        assert isinstance(MockRegistry(), PermissionRegistry)

    def test_non_conforming_class_not_instance(self):
        from hyperadmin.core.auth import AuthBackend

        class NotABackend:
            pass

        assert not isinstance(NotABackend(), AuthBackend)


class TestAdminAuthBackend:
    def test_admin_without_auth_backend(self):
        """Admin(app) still works without auth (backward compatible)."""
        from hyperadmin.core.app import Admin

        app = FastAPI()
        admin = Admin(app, create_tables=False)
        assert admin.auth_backend is None

    def test_admin_with_auth_backend(self):
        """Admin(app, auth_backend=backend) stores the backend."""
        from hyperadmin.core.app import Admin

        app = FastAPI()
        mock_backend = AsyncMock()
        admin = Admin(app, create_tables=False, auth_backend=mock_backend)
        assert admin.auth_backend is mock_backend

    def test_no_circular_imports(self):
        """python -c 'import hyperadmin' must succeed."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-c", "import hyperadmin"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"
