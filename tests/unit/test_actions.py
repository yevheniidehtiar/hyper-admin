"""Unit tests for ActionDef dataclass and @action decorator."""

import dataclasses

import pytest

from hyperadmin.core.actions import ActionDef, action, collect_actions

# ---------------------------------------------------------------------------
# ActionDef construction
# ---------------------------------------------------------------------------


async def _dummy_handler(self, request, item_id):
    pass


def test_actiondef_construction():
    ad = ActionDef(name="archive", label="Archive", handler=_dummy_handler)
    assert ad.name == "archive"
    assert ad.label == "Archive"
    assert ad.handler is _dummy_handler
    assert ad.requires_selection is False


def test_actiondef_defaults():
    ad = ActionDef(name="x", label="X", handler=_dummy_handler)
    assert ad.requires_selection is False


def test_actiondef_requires_selection_set():
    ad = ActionDef(name="bulk", label="Bulk", handler=_dummy_handler, requires_selection=True)
    assert ad.requires_selection is True


def test_actiondef_frozen():
    ad = ActionDef(name="x", label="X", handler=_dummy_handler)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ad.name = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# @action decorator
# ---------------------------------------------------------------------------


def test_action_decorator_attaches_action_def():
    @action(label="Deactivate")
    async def deactivate(self, request, item_id):
        pass

    assert hasattr(deactivate, "_action_def")
    assert isinstance(deactivate._action_def, ActionDef)


def test_action_decorator_name_from_function():
    @action(label="Do Thing")
    async def do_thing(self, request, item_id):
        pass

    assert do_thing._action_def.name == "do_thing"


def test_action_decorator_label():
    @action(label="Send Email")
    async def send_email(self, request, item_id):
        pass

    assert send_email._action_def.label == "Send Email"


def test_action_decorator_requires_selection_default():
    @action(label="X")
    async def fn(self, request, item_id):
        pass

    assert fn._action_def.requires_selection is False


def test_action_decorator_requires_selection_true():
    @action(label="Bulk Delete", requires_selection=True)
    async def bulk_delete(self, request, item_id):
        pass

    assert bulk_delete._action_def.requires_selection is True


def test_action_decorator_preserves_function():
    """The decorator must return the original function unchanged."""

    @action(label="Noop")
    async def noop(self, request, item_id):
        return 42

    assert noop.__name__ == "noop"


def test_handler_is_callable():
    called_with: list = []

    @action(label="Test")
    async def my_action(self, request, item_id):
        called_with.append((self, request, item_id))

    handler = my_action._action_def.handler
    assert callable(handler)
    import asyncio

    asyncio.run(handler("self_arg", "req_arg", 99))
    assert called_with == [("self_arg", "req_arg", 99)]


# ---------------------------------------------------------------------------
# collect_actions
# ---------------------------------------------------------------------------


def test_collect_actions_from_class():
    class MyAdmin:
        @action(label="First")
        async def first_action(self, request, item_id):
            pass

        @action(label="Second")
        async def second_action(self, request, item_id):
            pass

        def plain_method(self):
            pass

    result = collect_actions(MyAdmin)
    assert len(result) == 2
    names = {a.name for a in result}
    assert names == {"first_action", "second_action"}


def test_collect_actions_empty_class():
    class NoActions:
        def plain(self):
            pass

    assert collect_actions(NoActions) == []


def test_collect_actions_returns_action_def_instances():
    class Admin:
        @action(label="Do It")
        async def do_it(self, request, item_id):
            pass

    result = collect_actions(Admin)
    assert all(isinstance(a, ActionDef) for a in result)
