"""Unit tests for the built-in ERP/auth seed-plan generators."""

import random

import pytest

from hyperadmin.loadtest.generators import (
    PLAN_BUILDERS,
    build_auth_plan,
    build_erp_plan,
    build_plan,
)
from hyperadmin.loadtest.pool import FKPool


class TestRegistry:
    def test_known_plans_build(self):
        assert set(PLAN_BUILDERS) == {"erp", "auth"}
        assert build_plan("erp").tables
        assert build_plan("auth").tables

    def test_unknown_plan_lists_available(self):
        with pytest.raises(KeyError, match="available plans: auth, erp"):
            build_plan("nope")


class TestErpPlan:
    def test_plan_hash_is_seed_independent_and_stable(self):
        # Structure (and thus hash) does not depend on the Faker seed.
        assert build_erp_plan(seed=1).hash() == build_erp_plan(seed=999).hash()

    def test_parent_ordering_is_valid(self):
        # Construction would raise if any child preceded its parent; assert the edges too.
        plan = build_erp_plan()
        names = [t.name for t in plan.tables]
        assert names.index("erp_contacts") < names.index("erp_invoices")
        assert names.index("erp_invoices") < names.index("erp_invoice_items")
        assert names.index("erp_accounts") < names.index("erp_journal_lines")

    def test_scaling_sums_exactly(self):
        plan = build_erp_plan().scaled(10_000)
        assert sum(t.target_count for t in plan.tables) == 10_000

    def test_factories_emit_declared_columns(self):
        plan = build_erp_plan(seed=7)
        rng = random.Random(7)  # noqa: S311 - test RNG
        pool = FKPool(rng=rng)
        # Seed parent pools so FK-sampling factories can run.
        for parent in (
            "erp_contacts",
            "erp_invoices",
            "erp_bills",
            "erp_journal_entries",
            "erp_accounts",
        ):
            pool.extend(parent, range(1, 50))
        for table in plan.tables:
            row = table.row_factory(pool, rng, 1)
            assert set(row) == set(table.columns), table.name


class TestAuthPlan:
    def test_auth_plan_has_users_and_groups(self):
        names = [t.name for t in build_auth_plan().tables]
        assert names == ["hyperadmin_users", "hyperadmin_groups"]

    def test_user_factory_fills_not_null_columns(self):
        plan = build_auth_plan(seed=3)
        rng = random.Random(3)  # noqa: S311 - test RNG
        pool = FKPool(rng=rng)
        row = plan.table("hyperadmin_users").row_factory(pool, rng, 5)
        assert row["username"] == "user_00000005"
        assert row["is_active"] is True
        assert row["created_at"] is not None
