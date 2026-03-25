from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class ActionCallable(Protocol):
    _action_def: "ActionDef"

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class ActionDef:
    """Definition of an administrative action.

    Attributes:
        name: The internal name of the action (usually the function name).
        label: The human-readable label for the action.
        handler: The callable that implements the action logic.
        requires_selection: Whether the action requires items to be selected.
    """

    name: str
    label: str
    handler: Callable[..., Any]
    requires_selection: bool = False


def action(
    label: str | None = None,
    requires_selection: bool = False,
) -> Callable[[F], F]:
    """Decorator to mark a method as an admin action.

    Example:
        class UserView(ModelView):
            @action(label="Activate Users", requires_selection=True)
            async def activate(self, request, items):
                ...
    """

    def decorator(func: F) -> F:
        name = func.__name__
        action_label = label or name.replace("_", " ").strip().title()

        # We attach the ActionDef to the function so it can be discovered
        # when the ModelView class is inspected.
        adef = ActionDef(
            name=name,
            label=action_label,
            handler=func,
            requires_selection=requires_selection,
        )
        setattr(func, "_action_def", adef)
        return func

    return decorator
