"""Unit tests for ``AdminOptions.object_permission_checker`` (C2-A, #477).

Covers the BDD scenarios from the story:

- Default ``AdminOptions()`` exposes ``object_permission_checker is None``.
- Constructing ``AdminOptions(object_permission_checker=...)`` retains the value.
"""

from __future__ import annotations

from hyperadmin.core.auth import DefaultObjectPermissionChecker
from hyperadmin.core.options import AdminOptions


def test_admin_options_object_permission_checker_defaults_to_none() -> None:
    """Scenario: default is None (no object-level checks).

    Given a model registered with default options
    When  the model's options are inspected
    Then  ``options.object_permission_checker`` is ``None``
    """
    # Given / When
    options = AdminOptions()

    # Then
    assert options.object_permission_checker is None


def test_admin_options_accepts_object_permission_checker() -> None:
    """Scenario: AdminOptions accepts object_permission_checker.

    Given a model registered with ``options=AdminOptions(object_permission_checker=my_checker)``
    When  the model's options are inspected
    Then  ``options.object_permission_checker`` is ``my_checker``
    """
    # Given
    checker = DefaultObjectPermissionChecker()

    # When
    options = AdminOptions(object_permission_checker=checker)

    # Then
    assert options.object_permission_checker is checker
