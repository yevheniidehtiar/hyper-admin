"""Adapter spans: ``admin.adapter.<op>`` opened and closed by the adapter lifecycle hooks.

The open spans live on a ``ContextVar`` stack, so an adapter call that nests another one
(inline relations, choices fetched during a list) produces nested spans, and concurrent requests
never see each other's spans (``docs/specs/plugin-logfire.md``, "Hook usage").
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

import logfire

logger = logging.getLogger(__name__)

#: Immutable stack of open spans; replaced (never mutated) so each context keeps its own view.
_open_spans: ContextVar[tuple[Any, ...]] = ContextVar("hyperadmin_logfire_open_spans", default=())


def model_name(model: Any) -> str:
    """Name of a model class (or of an instance's class)."""
    return getattr(model, "__name__", None) or type(model).__name__


def safe_attributes(op: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Whitelisted span attributes per operation: no field values, no search-free payloads."""
    if op in ("list", "list_paginated"):
        return {
            "page": kwargs.get("page"),
            "page_size": kwargs.get("page_size"),
            "search": kwargs.get("search"),
            "has_filters": bool(kwargs.get("filters")),
        }
    if op in ("get", "delete", "update", "get_related"):
        attributes: dict[str, Any] = {"pk": str(kwargs.get("pk"))}
        if op == "update":
            attributes["field_count"] = len(kwargs.get("data") or {})
        if op == "get_related":
            attributes["field"] = kwargs.get("field")
        return attributes
    if op == "create":
        return {"field_count": len(kwargs.get("data") or {})}
    if op == "get_choices":
        return {"field": kwargs.get("field"), "limit": kwargs.get("limit")}
    return {}


def open_span(*, model: Any, op: str, kwargs: dict[str, Any]) -> None:
    """Enter ``admin.adapter.<op>`` and push it on the stack."""
    # Built outside the call: logfire rewrites an f-string argument back into a ``{op}`` template.
    name = "admin.adapter." + op
    span = logfire.span(name, model=model_name(model), op=op, **safe_attributes(op, kwargs))
    span.__enter__()
    _open_spans.set((*_open_spans.get(), span))


def close_span(*, model: Any, op: str, result: Any, error: BaseException | None = None) -> None:
    """Pop and exit the innermost open span; log a warning when there is none."""
    stack = _open_spans.get()
    if not stack:
        logger.warning(
            "logfire adapter span close called but no open span found",
            extra={"model": model_name(model), "op": op},
        )
        return
    span = stack[-1]
    _open_spans.set(stack[:-1])
    if error is None:
        if op in ("list", "list_paginated"):
            items = result[0] if isinstance(result, tuple) else getattr(result, "items", result)
            if isinstance(items, list | tuple):
                span.set_attribute("result_count", len(items))
        span.__exit__(None, None, None)
    else:
        span.__exit__(type(error), error, error.__traceback__)
