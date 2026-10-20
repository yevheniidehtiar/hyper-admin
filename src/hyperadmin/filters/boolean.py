"""Boolean filters: a tri-state ``Any/Yes/No`` and the "Mine only" owner switch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from hyperadmin.core.filtering import FilterCondition
from hyperadmin.filters.base import FilterBinding, FilterDef, is_truthy, query_value

if TYPE_CHECKING:
    from hyperadmin.filters.base import FilterRenderContext

_FALSE = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True, kw_only=True)
class BooleanFilter(FilterDef):
    """Tri-state radio on a boolean column: ``{field}=`` (any), ``1`` (yes) or ``0`` (no)."""

    template: ClassVar[str] = "components/filters/boolean.html"
    value_type: ClassVar[Any] = bool

    def parse(self, qs: Any) -> dict[str, Any]:
        raw = query_value(qs, self.field)
        if is_truthy(raw):
            return {"value": True}
        if raw is not None and raw.lower() in _FALSE:
            return {"value": False}
        return {}

    def compile(
        self, parsed: dict[str, Any], binding: FilterBinding | None = None
    ) -> list[FilterCondition]:
        if "value" not in parsed:
            return []
        return self.typed_conditions(binding, {"": "true" if parsed["value"] else "false"})

    def describe(self, parsed: dict[str, Any]) -> str | None:
        if "value" not in parsed:
            return None
        return "Yes" if parsed["value"] else "No"

    def context(self, ctx: FilterRenderContext) -> dict[str, Any]:
        base = super().context(ctx)
        value = base["parsed"].get("value")
        base["state"] = "" if value is None else ("1" if value else "0")
        return base


@dataclass(frozen=True, kw_only=True)
class IsOwnerFilter(FilterDef):
    """The "Mine only" switch (``is_owner=1``): rows an owner column assigns to the current user.

    Compares each of ``owner_fields`` to ``binding.user_key`` (what the v0.5.8
    auth pipeline sets as ``request.state.user_key``). One field compiles to an
    ``exact`` condition; several compile to one ``any_of`` condition (created
    *or* assigned to me). With no user key (anonymous) nothing is applied, so
    the filter can never widen a result.

    Args:
        owner_fields: One column name, or several to OR together.
        help_text: Sidebar hint saying what "mine" means for this model.
    """

    template: ClassVar[str] = "components/filters/is_owner.html"

    owner_fields: tuple[str, ...] | list[str] | str
    label: str | None = "Mine only"
    help_text: str | None = None
    field: str = field(init=False, default="")

    def __post_init__(self) -> None:
        names = (self.owner_fields,) if isinstance(self.owner_fields, str) else self.owner_fields
        cleaned = tuple(dict.fromkeys(name.strip() for name in names if name and name.strip()))
        if not cleaned:
            msg = "IsOwnerFilter needs at least one owner field"
            raise ValueError(msg)
        object.__setattr__(self, "owner_fields", cleaned)
        object.__setattr__(self, "field", cleaned[0])

    @property
    def slug(self) -> str:
        return "is_owner"

    @property
    def query_keys(self) -> tuple[str, ...]:
        return ("is_owner",)

    def parse(self, qs: Any) -> dict[str, Any]:
        return {"is_owner": True} if is_truthy(query_value(qs, "is_owner")) else {}

    def compile(
        self, parsed: dict[str, Any], binding: FilterBinding | None = None
    ) -> list[FilterCondition]:
        user_key = binding.user_key if binding is not None else None
        if not parsed.get("is_owner") or user_key is None:
            return []
        fields = tuple(self.owner_fields)
        if len(fields) == 1:
            return [FilterCondition(fields[0], "exact", user_key)]
        return [FilterCondition(fields[0], "any_of", tuple((name, user_key) for name in fields))]

    def describe(self, parsed: dict[str, Any]) -> str | None:
        return self.title if parsed.get("is_owner") else None
