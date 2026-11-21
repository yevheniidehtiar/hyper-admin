"""ActionDef dataclass and @action decorator for HyperAdmin custom actions."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class ActionDef:
    """Metadata for a custom admin action registered on a ModelAdmin class.

    Instances are created automatically by the :func:`action` decorator and
    attached to the decorated method as ``method._action_def``.

    Args:
        name: Unique slug for the action, derived from the decorated function's name.
        label: Human-readable label shown on the action button.
        handler: The unbound function (method) that implements the action.
        requires_selection: When ``True`` the action requires one or more items
            to be selected before running. Auto-set to ``True`` for ``bulk=True``
            actions unless explicitly overridden.
        bulk: When ``True``, the action operates over multiple selected rows
            via the bulk endpoint at ``POST /{model}/actions/{name}/bulk``.
            The handler signature must accept a ``params`` keyword-only argument.
        form: Optional Pydantic model collected from the operator before the
            bulk handler runs. Only valid when ``bulk=True``.
    """

    name: str
    label: str
    handler: Callable[..., Any]
    requires_selection: bool = False
    bulk: bool = False
    form: type[BaseModel] | None = None


def action(
    label: str,
    *,
    requires_selection: bool | None = None,
    bulk: bool = False,
    form: type[BaseModel] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that marks a :class:`~hyperadmin.core.model.ModelAdmin` method as a custom action.

    For single-record actions (``bulk=False``, default) the decorated method must
    be ``async`` and accept ``(self, request, item_id)``. ``item_id`` is the
    row's typed primary key, parsed by the model's ``PrimaryKeyInfo``: an
    ``int`` for int-id models, a :class:`uuid.UUID` for UUID keys, a ``str``
    for natural keys. Bulk handlers receive the same typed key per row.

    For bulk actions (``bulk=True``) the handler must additionally accept a
    keyword-only ``params`` argument, which is the validated Pydantic instance
    when ``form`` is set, or ``None`` otherwise. ``bulk=True`` implies
    ``requires_selection=True`` unless the caller passes
    ``requires_selection=False`` explicitly (e.g. for "operate on all matching
    rows" actions).

    Example::

        from hyperadmin.core.actions import action


        class OrderAdmin(ModelAdmin):
            @action(label="Archive", bulk=True)
            async def archive(self, request, item_id, *, params=None): ...

    Args:
        label: Human-readable label shown on the action button.
        requires_selection: Whether the action needs selected rows. ``None`` (default)
            derives it from ``bulk``; ``True`` or ``False`` overrides that.
        bulk: Whether this is a multi-row action invoked from the list view.
        form: Pydantic model used to collect parameters before the handler runs.

    Raises:
        TypeError: If ``form`` is set without ``bulk=True``, or if a
            ``bulk=True`` handler signature does not accept a ``params``
            keyword-only argument.
    """

    if form is not None and not bulk:
        raise TypeError("form= requires bulk=True")

    resolved_requires_selection: bool = (
        bool(bulk) if requires_selection is None else bool(requires_selection)
    )

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if bulk:
            sig = inspect.signature(fn)
            params_kw = sig.parameters.get("params")
            if params_kw is None or params_kw.kind is not inspect.Parameter.KEYWORD_ONLY:
                raise TypeError(
                    f"bulk=True handler {fn.__name__!r} must accept a 'params' "
                    "keyword-only argument"
                )

        fn._action_def = ActionDef(  # type: ignore[attr-defined]
            name=fn.__name__,
            label=label,
            handler=fn,
            requires_selection=resolved_requires_selection,
            bulk=bulk,
            form=form,
        )
        return fn

    return decorator


def action_permission_codename(name: str, model_name: str) -> str:
    """Return the permission codename that lets a user run action ``name`` on a model.

    The views check it before running the action (single-row and bulk), and
    ``PermissionSyncService`` creates it at startup. The codename carries the model,
    so two models with an action of the same name get separate permissions.
    ``model_name`` is the lowercased model class name. The object-level check
    (``AdminOptions.object_permission_checker``) receives ``action_<name>`` instead.

    Example:
        >>> action_permission_codename("archive", "order")
        'action_archive_order'
    """
    return f"action_{name}_{model_name}"


def collect_actions(cls: type) -> list[ActionDef]:
    """Return all :class:`ActionDef` instances registered on *cls* via :func:`action`.

    Introspects every attribute on the class (including inherited ones) and
    collects those that carry a ``_action_def`` attribute set by the decorator.

    Args:
        cls: A :class:`~hyperadmin.core.model.ModelAdmin` subclass to inspect.

    Returns:
        A list of :class:`ActionDef` instances in the order returned by :func:`dir`.
    """
    actions: list[ActionDef] = []
    for attr_name in dir(cls):
        attr = getattr(cls, attr_name, None)
        if callable(attr) and hasattr(attr, "_action_def"):
            actions.append(attr._action_def)  # type: ignore[union-attr]
    return actions
