import threading
from typing import Any


class SiteRegistry:
    """A central, thread-safe registry for managing administrative models.

    This registry acts as a single source of truth for all models that HyperAdmin
    manages. It uses a `threading.Lock` to ensure that registrations and other
    operations are atomic, making it safe for use in multi-threaded web applications.
    """

    def __init__(self) -> None:
        self._registry: dict[Any, Any] = {}
        self._lock = threading.Lock()

    def register(self, model: Any, admin_class: Any = None) -> None:
        """
        Registers a model with an optional admin class.

        Args:
            model: The model class or instance to register.
            admin_class: The admin class to associate with the model.

        Raises:
            ValueError: If the model is already registered.
        """
        with self._lock:
            if model in self._registry:
                raise ValueError(f"Model {model} is already registered.")
            self._registry[model] = admin_class

    def unregister(self, model: Any) -> None:
        """
        Unregisters a model.

        Args:
            model: The model class or instance to unregister.

        Raises:
            ValueError: If the model is not registered.
        """
        with self._lock:
            if model not in self._registry:
                raise ValueError(f"Model {model} is not registered.")
            del self._registry[model]

    def get_registered_models(self) -> list[Any]:
        """
        Returns a list of all registered models.

        Returns:
            A list of registered models.
        """
        with self._lock:
            return list(self._registry.keys())
