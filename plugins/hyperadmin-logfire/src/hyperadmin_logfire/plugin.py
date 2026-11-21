"""Entry point the HyperAdmin plugin loader discovers (``hyperadmin.plugins`` group).

The plugin contributes no UI seams. HTTP and SQL spans come from ``instrument_admin()``;
adapter spans and validation/auth events come from lifecycle hook methods once core fires
them (``docs/specs/plugin-logfire.md``, phases A and B).
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

    def on_before_adapter_call(self, *, admin: Any, model: Any, op: str, kwargs: Any) -> None:  # noqa: ARG002
        """Open an ``admin.adapter.<op>`` span."""
        open_span(model=model, op=op, kwargs=dict(kwargs or {}))

    def on_after_adapter_call(
        self,
        *,
        admin: Any,  # noqa: ARG002
        model: Any,
        op: str,
        result: Any,
        error: BaseException | None = None,
    ) -> None:
        """Close the innermost adapter span, recording ``error`` when the call raised."""
        close_span(model=model, op=op, result=result, error=error)
