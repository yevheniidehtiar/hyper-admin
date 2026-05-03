"""Tests for the ObjectPermissionChecker protocol (C1-A, #476).

TDD: Verify the runtime-checkable protocol shape and the permissive
default implementation. Maps 1:1 to BDD scenarios in the story.
"""

from __future__ import annotations

from typing import Any

import pytest


class TestObjectPermissionCheckerProtocol:
    def test_protocol_importable_from_core_auth(self) -> None:
        """ObjectPermissionChecker is exported from hyperadmin.core.auth."""
        from hyperadmin.core.auth import ObjectPermissionChecker

        assert ObjectPermissionChecker is not None

    def test_default_importable_from_core_auth(self) -> None:
        """DefaultObjectPermissionChecker is exported from hyperadmin.core.auth."""
        from hyperadmin.core.auth import DefaultObjectPermissionChecker

        assert DefaultObjectPermissionChecker is not None

    def test_protocol_exported_from_core_package(self) -> None:
        """Protocol and default are re-exported from hyperadmin.core."""
        from hyperadmin.core import (
            DefaultObjectPermissionChecker,
            ObjectPermissionChecker,
        )

        assert ObjectPermissionChecker is not None
        assert DefaultObjectPermissionChecker is not None

    def test_protocol_is_runtime_checkable(self) -> None:
        """
        Scenario: protocol is runtime-checkable
          Given a class implementing has_object_permission(user, obj, action) -> bool
          When  isinstance(instance, ObjectPermissionChecker) is evaluated
          Then  result is True
        """
        from hyperadmin.core.auth import ObjectPermissionChecker

        class MockChecker:
            async def has_object_permission(self, user: Any, obj: Any, action: str) -> bool:
                return True

        assert isinstance(MockChecker(), ObjectPermissionChecker)

    def test_non_conforming_class_is_not_an_instance(self) -> None:
        """A class missing has_object_permission is not an ObjectPermissionChecker."""
        from hyperadmin.core.auth import ObjectPermissionChecker

        class NotAChecker:
            pass

        assert not isinstance(NotAChecker(), ObjectPermissionChecker)


class TestDefaultObjectPermissionChecker:
    @pytest.mark.anyio
    async def test_default_allows_view_access(self) -> None:
        """
        Scenario: default implementation allows all access
          Given DefaultObjectPermissionChecker is used
          When  has_object_permission(user, order, "view") is called
          Then  result is True
        """
        from hyperadmin.core.auth import DefaultObjectPermissionChecker

        checker = DefaultObjectPermissionChecker()
        user = object()
        order = object()

        result = await checker.has_object_permission(user, order, "view")

        assert result is True

    @pytest.mark.anyio
    async def test_default_allows_arbitrary_action(self) -> None:
        """Default checker is permissive for any action codename."""
        from hyperadmin.core.auth import DefaultObjectPermissionChecker

        checker = DefaultObjectPermissionChecker()

        for action in ("view", "add", "change", "delete", "custom"):
            assert await checker.has_object_permission(None, None, action) is True

    @pytest.mark.anyio
    async def test_default_satisfies_protocol(self) -> None:
        """DefaultObjectPermissionChecker is itself an ObjectPermissionChecker."""
        from hyperadmin.core.auth import (
            DefaultObjectPermissionChecker,
            ObjectPermissionChecker,
        )

        assert isinstance(DefaultObjectPermissionChecker(), ObjectPermissionChecker)
