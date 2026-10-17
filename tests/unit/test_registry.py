import contextlib
import threading

import pytest

from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import SiteRegistry


class DummyModel:
    pass


class DummyAdmin(ModelAdmin):
    pass


@pytest.fixture
def registry() -> SiteRegistry:
    return SiteRegistry()


def test_register_model(registry: SiteRegistry, mocker) -> None:
    mocker.patch(
        "hyperadmin.core.registry.adapter_registry.find_adapter_for_model", return_value=None
    )
    registry.register(DummyModel, DummyAdmin)
    assert DummyModel in registry.get_registered_models()


def test_unregister_model(registry: SiteRegistry, mocker) -> None:
    mocker.patch(
        "hyperadmin.core.registry.adapter_registry.find_adapter_for_model", return_value=None
    )
    registry.register(DummyModel, DummyAdmin)
    registry.unregister(DummyModel)
    assert DummyModel not in registry.get_registered_models()


def test_register_duplicate_model_raises_error(registry: SiteRegistry, mocker) -> None:
    mocker.patch(
        "hyperadmin.core.registry.adapter_registry.find_adapter_for_model", return_value=None
    )
    registry.register(DummyModel, DummyAdmin)
    with pytest.raises(ValueError, match=r"Model .* is already registered\."):
        registry.register(DummyModel, DummyAdmin)


def test_unregister_nonexistent_model_raises_error(registry: SiteRegistry) -> None:
    with pytest.raises(ValueError, match=r"Model .* is not registered\."):
        registry.unregister(DummyModel)


def test_get_registered_models(registry: SiteRegistry, mocker) -> None:
    mocker.patch(
        "hyperadmin.core.registry.adapter_registry.find_adapter_for_model", return_value=None
    )
    registry.register(DummyModel, DummyAdmin)
    assert registry.get_registered_models() == [DummyModel]


def test_thread_safe_registration(registry: SiteRegistry, mocker) -> None:
    mocker.patch(
        "hyperadmin.core.registry.adapter_registry.find_adapter_for_model", return_value=None
    )
    threads = []
    num_threads = 10

    class Model:
        pass

    def register_model(model_class: type) -> None:
        with contextlib.suppress(ValueError):
            registry.register(model_class)

    for i in range(num_threads):
        model_class = type(f"Model{i}", (Model,), {})
        thread = threading.Thread(target=register_model, args=(model_class,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    assert len(registry.get_registered_models()) == num_threads


from hyperadmin.core.model import HyperAdminModel


def test_register_hyper_admin_model(registry: SiteRegistry, mocker) -> None:
    """Tests that a HyperAdminModel subclass can be registered."""
    mocker.patch(
        "hyperadmin.core.registry.adapter_registry.find_adapter_for_model", return_value=None
    )

    class MyAdminModel(HyperAdminModel):
        name: str

        @classmethod
        async def create(cls, data):
            pass

        @classmethod
        async def get(cls, pk):
            pass

        async def update(self, data):
            pass

        async def delete(self):
            pass

    registry.register(MyAdminModel)
    assert MyAdminModel in registry.get_registered_models()


def test_class_level_list_options_fill_unset_admin_options(registry: SiteRegistry, mocker) -> None:
    """
    Scenario: list options declared as ModelAdmin class attributes are honoured
      Given a ModelAdmin subclass with class-level list_display, search_fields and list_filter
      When  it is registered without explicit options
      Then  its options carry those lists instead of the inferred defaults
    """
    from typing import ClassVar

    mocker.patch(
        "hyperadmin.core.registry.adapter_registry.find_adapter_for_model", return_value=None
    )

    class ContactAdmin(ModelAdmin):
        list_display: ClassVar[list[str]] = ["id", "name"]
        search_fields: ClassVar[list[str]] = ["name"]
        list_filter: ClassVar[list[str]] = ["kind"]

    registry.register(DummyModel, ContactAdmin)

    options = ContactAdmin.options
    assert options.list_display == ["id", "name"]
    assert options.search_fields == ["name"]
    assert options.list_filter == ["kind"]


def test_explicit_options_win_over_class_level_list_options(registry: SiteRegistry, mocker) -> None:
    """
    Scenario: explicit AdminOptions take precedence
      Given a ModelAdmin with class-level list_display and explicit options setting list_display
      When  it is registered
      Then  the explicit list_display is kept and unset fields still come from the class
    """
    from typing import ClassVar

    from hyperadmin.core.options import AdminOptions

    mocker.patch(
        "hyperadmin.core.registry.adapter_registry.find_adapter_for_model", return_value=None
    )

    class ContactAdmin(ModelAdmin):
        list_display: ClassVar[list[str]] = ["id", "name"]
        search_fields: ClassVar[list[str]] = ["name"]

    registry.register(DummyModel, ContactAdmin, options=AdminOptions(list_display=["email"]))

    assert ContactAdmin.options.list_display == ["email"]
    assert ContactAdmin.options.search_fields == ["name"]


def test_default_admin_registration_does_not_leak_onto_model_admin(
    registry: SiteRegistry, mocker
) -> None:
    """
    Scenario: registering without an admin class leaves ModelAdmin untouched
      Given a model registered with no admin class and explicit options
      When  another ModelAdmin subclass is declared afterwards
      Then  it does not inherit the first model's options
    """
    from hyperadmin.core.options import AdminOptions

    mocker.patch(
        "hyperadmin.core.registry.adapter_registry.find_adapter_for_model", return_value=None
    )

    registry.register(DummyModel, options=AdminOptions(list_filter=["username"]))

    assert registry._registry[DummyModel] is not ModelAdmin
    assert issubclass(registry._registry[DummyModel], ModelAdmin)
    assert getattr(ModelAdmin, "options", None) is None or ModelAdmin.options.list_filter != [
        "username"
    ]
