"""Built-in seed-plan generators, addressable by name from the CLI ``--plan`` flag."""

from __future__ import annotations

from collections.abc import Callable

from hyperadmin.loadtest.generators.auth import build_auth_plan
from hyperadmin.loadtest.generators.erp import build_erp_plan
from hyperadmin.loadtest.plan import SeedPlan

PlanBuilder = Callable[..., SeedPlan]

PLAN_BUILDERS: dict[str, PlanBuilder] = {
    "erp": build_erp_plan,
    "auth": build_auth_plan,
}


def build_plan(name: str, *, seed: int = 42) -> SeedPlan:
    """Build a named plan, or raise ``KeyError`` listing the available plans."""
    try:
        builder = PLAN_BUILDERS[name]
    except KeyError:
        available = ", ".join(sorted(PLAN_BUILDERS))
        raise KeyError(f"unknown plan {name!r}; available plans: {available}") from None
    return builder(seed=seed)


__all__ = ["PLAN_BUILDERS", "build_auth_plan", "build_erp_plan", "build_plan"]
