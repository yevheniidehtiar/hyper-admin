"""ActionDef dataclass and @action decorator for HyperAdmin custom actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class ActionDef:
    """Metadata for a custom admin action registered on a ModelAdmin class.

    Instances are created automatically by the :func:`action` decorator and
    attached to the decorated method as ``method._action_def``.

    Args:
        name: Unique slug for the action, derived from the decorated function's name.
        label: Human-readable label shown on the action button.
        handler: The unbound function (method) that implements the action.
        requires_selection: Reserved for future bulk-action support. When ``True``
            the action requires one or more items to be selected before running.
    """

    name: str
    label: str
    handler: Callable[..., Any]
    requires_selection: bool = False


def action(
    label: str,
    *,
    requires_selection: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that marks a :class:`~hyperadmin.core.model.ModelAdmin` method as a custom action.

    The decorated method must be ``async`` and accept ``(self, request, item_id)`` as
    its signature.  It may return a :class:`starlette.responses.Response` to override
    the default post-action redirect, or return ``None`` to accept the default
    behaviour (HTMX redirect to the model list view).

    Example::

        from hyperadmin.core.actions import action


        class UserAdmin(ModelAdmin):
            @action(label="Deactivate")
            async def deactivate(self, request, item_id):
                user = await self.adapter.get(pk=item_id)
                if user:
                    await self.adapter.update(user, {"is_active": False})

    Args:
        label: Human-readable label shown on the action button.
        requires_selection: Reserved for future bulk-action support.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn._action_def = ActionDef(  # type: ignore[attr-defined]
            name=fn.__name__,
            label=label,
            handler=fn,
            requires_selection=requires_selection,
        )
        return fn

    return decorator


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
