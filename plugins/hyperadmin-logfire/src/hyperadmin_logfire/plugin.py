"""Entry point the HyperAdmin plugin loader discovers (``hyperadmin.plugins`` group).

The plugin contributes no UI seams. HTTP and SQL spans come from ``instrument_admin()``;
adapter spans come from the ``on_before/after_adapter_call`` lifecycle hooks
(``docs/specs/plugin-logfire.md``, phases A and B). Hook methods end in ``**kwargs``, as the hook
contract asks (``docs/plugins/hooks.md``), so a later core release can pass more arguments.
"""

from __future__ import annotations

from typing import Any, ClassVar

from hyperadmin_logfire.adapter_spans import close_span, open_span

#: Entry-point name, also the key in ``admin.plugins`` and ``disabled_plugins``.
PLUGIN_NAME = "logfire"


class LogfirePlugin:
    """The ``logfire`` plugin: Pydantic Logfire spans and events for HyperAdmin."""

    name: ClassVar[str] = PLUGIN_NAME

    def __init__(self) -> None:
        #: Set by ``instrument_admin()`` so a second call is a no-op.
        self.instrumented = False

    def on_register(self, admin: Any) -> None:
        """Nothing to contribute: the plugin adds no pages, nav entries or permissions."""

    def on_before_adapter_call(self, *, model: Any, op: str, kwargs: Any, **_: Any) -> None:
        """Open an ``admin.adapter.<op>`` span."""
        open_span(model=model, op=op, kwargs=dict(kwargs or {}))

    def on_after_adapter_call(
        self,
        *,
        model: Any,
        op: str,
        result: Any,
        error: BaseException | None = None,
        **_: Any,
    ) -> None:
        """Close the innermost adapter span, recording ``error`` when the call raised."""
        close_span(model=model, op=op, result=result, error=error)
