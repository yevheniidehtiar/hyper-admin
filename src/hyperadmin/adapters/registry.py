from typing import Any

from hyperadmin.core.adapters import BaseAdapter


class AdapterNotFound(Exception):
    """Raised when no suitable adapter is found for a given model."""


class AdapterRegistry:
    def __init__(self):
        self._registry: dict[type, type[BaseAdapter]] = {}

    def register(self, orm_base_class: type, adapter_class: type[BaseAdapter]) -> None:
        """
        Registers an adapter class for a given ORM base class.
        """
        self._registry[orm_base_class] = adapter_class

    def find_adapter_for_model(self, model_class: Any) -> type[BaseAdapter]:
        """
        Finds a suitable adapter for a given model class by checking its MRO.
        """
        for base in model_class.__mro__:
            if base in self._registry:
                return self._registry[base]
        raise AdapterNotFound(
            f"No suitable adapter found for model {model_class.__name__}. "
            f"Please register an adapter for one of its base classes."
        )


adapter_registry = AdapterRegistry()
