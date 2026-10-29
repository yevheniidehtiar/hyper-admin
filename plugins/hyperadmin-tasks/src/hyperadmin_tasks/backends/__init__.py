"""Concrete ``TaskBackend`` adapters shipped with the tasks plugin."""

from __future__ import annotations

from hyperadmin_tasks.backends.memory import InMemoryTaskBackend

__all__ = ["InMemoryTaskBackend"]
