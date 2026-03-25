from hyperadmin.core import ActionDef, action


def test_action_decorator_basic():
    class MyView:
        @action(label="My Custom Label")
        def my_action(self):
            return "ok"

    # Check if the metadata is attached to the method
    assert hasattr(MyView.my_action, "_action_def")
    action_def = MyView.my_action._action_def

    assert isinstance(action_def, ActionDef)
    assert action_def.name == "my_action"
    assert action_def.label == "My Custom Label"
    assert action_def.requires_selection is False
    assert action_def.handler == MyView.my_action


def test_action_decorator_defaults():
    class MyView:
        @action()
        def some_other_action(self):
            pass

    action_def = MyView.some_other_action._action_def
    assert action_def.name == "some_other_action"
    assert action_def.label == "Some Other Action"
    assert action_def.requires_selection is False


def test_action_decorator_requires_selection():
    class MyView:
        @action(requires_selection=True)
        def bulk_delete(self):
            pass

    action_def = MyView.bulk_delete._action_def
    assert action_def.name == "bulk_delete"
    assert action_def.label == "Bulk Delete"
    assert action_def.requires_selection is True


def test_action_def_instantiation():
    def my_handler():
        pass

    adef = ActionDef(
        name="test_action",
        label="Test Action",
        handler=my_handler,
        requires_selection=True,
    )

    assert adef.name == "test_action"
    assert adef.label == "Test Action"
    assert adef.handler == my_handler
    assert adef.requires_selection is True
