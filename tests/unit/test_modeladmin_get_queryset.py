"""Unit tests for the ``ModelAdmin.get_queryset`` hook (BDD scenarios from issue #479).

Each test maps 1:1 to a scenario in
``.meta/epics/epicauth-object-level-permissions-mvp-otpmfa/stories/featcore-add-getqueryset-hook-to-modeladmin-base.md``.

The hook mirrors :meth:`hyperadmin.core.adapters.BaseAdapter.get_queryset` semantics:
synchronous, accepts an optional ``Request`` and returns a dict of equality filters that
will be merged into list/detail queries by C2-C view-layer wiring.
"""

from __future__ import annotations

from typing import Any

from hyperadmin.core.model import ModelAdmin


class _DummyModel:
    """Lightweight stand-in for an ORM model class used in ``ModelAdmin`` tests."""

    __name__ = "Dummy"


def test_default_get_queryset_returns_empty_dict() -> None:
    """
    Scenario: default get_queryset returns no filters
      Given a model with default ModelAdmin
      When  ``get_queryset(request)`` is called
      Then  result is ``{}``
    """
    # Given a default ModelAdmin instance bound to a model
    admin = ModelAdmin(model=_DummyModel)

    # When get_queryset is called (with and without an explicit request)
    result_default = admin.get_queryset()
    result_with_none = admin.get_queryset(request=None)

    # Then both return an empty dict (no filtering — backward compatible)
    assert result_default == {}
    assert result_with_none == {}


def test_subclass_override_get_queryset_returns_override_value() -> None:
    """
    Scenario: custom get_queryset filters by user
      Given a ModelAdmin overriding ``get_queryset`` to return owner-scoped filters
      When  the request carries a user with id=5
      Then  ``get_queryset`` returns ``{"owner_id": 5}``
    """

    class _FakeUser:
        id = 5

    class _FakeState:
        user = _FakeUser()

    class _FakeRequest:
        state = _FakeState()

    class OwnerScopedAdmin(ModelAdmin):
        def get_queryset(self, request: Any | None = None) -> dict[str, Any]:
            return {"owner_id": request.state.user.id}

    # Given a subclass overriding get_queryset
    admin = OwnerScopedAdmin(model=_DummyModel)

    # When get_queryset is called with a request whose state carries a user id
    filters = admin.get_queryset(_FakeRequest())

    # Then the override's value is returned verbatim
    assert filters == {"owner_id": 5}
