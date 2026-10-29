"""Pick and build the configured ``TaskBackend`` from :class:`TasksSettings`."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from hyperadmin_tasks.backend import TaskBackend, TasksBackendError
from hyperadmin_tasks.backends.memory import InMemoryTaskBackend

if TYPE_CHECKING:
    from collections.abc import Callable

    from hyperadmin_tasks.settings import TasksSettings

    _Factory = Callable[[TasksSettings], object]

#: Module (under ``hyperadmin_tasks.backends``) of the optional pgtask adapter.
PGTASK_MODULE = "hyperadmin_tasks.backends.pgtask"
#: Name of the factory function the pgtask module exposes.
PGTASK_FACTORY = "create_backend"
_PGTASK_HINT = "the pgtask backend is unavailable; install hyperadmin-tasks[pgtask]"


def select_backend(settings: TasksSettings) -> TaskBackend:
    """Build the backend named by ``settings.backend`` or raise ``TasksBackendError``."""
    choice = settings.backend
    if choice == "memory":
        return InMemoryTaskBackend()
    if choice == "pgtask":
        return _verified(_load_pgtask_factory()(settings), choice)
    if ":" in choice:
        module_name, _, attr = choice.partition(":")
        return _verified(_load_factory(module_name, attr, choice)(settings), choice)
    raise TasksBackendError(
        f"unknown tasks backend '{choice}'; use 'memory', 'pgtask' or 'module:attr'"
    )


def _load_pgtask_factory() -> _Factory:
    try:
        module = import_module(PGTASK_MODULE)
    except ImportError as exc:
        raise TasksBackendError(f"{_PGTASK_HINT} ({exc})") from exc
    return _attribute(module, PGTASK_FACTORY, "pgtask")


def _load_factory(module_name: str, attr: str, choice: str) -> _Factory:
    try:
        module = import_module(module_name)
    except ImportError as exc:
        raise TasksBackendError(f"cannot import backend factory '{choice}': {exc}") from exc
    return _attribute(module, attr, choice)


def _attribute(module: object, attr: str, choice: str) -> _Factory:
    factory: _Factory | None = getattr(module, attr, None)
    if not callable(factory):
        raise TasksBackendError(f"backend factory '{choice}' is not callable")
    return factory


def _verified(candidate: object, choice: str) -> TaskBackend:
    if not isinstance(candidate, TaskBackend):
        raise TasksBackendError(
            f"backend factory '{choice}' returned {type(candidate).__name__}, "
            "which does not satisfy TaskBackend"
        )
    return candidate
