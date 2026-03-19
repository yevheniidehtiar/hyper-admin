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
    with pytest.raises(ValueError, match="Model .* is already registered."):
        registry.register(DummyModel, DummyAdmin)


def test_unregister_nonexistent_model_raises_error(registry: SiteRegistry) -> None:
    with pytest.raises(ValueError, match="Model .* is not registered."):
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
