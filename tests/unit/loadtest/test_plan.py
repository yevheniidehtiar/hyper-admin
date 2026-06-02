"""Unit tests for SeedPlan / TablePlan: ordering invariants, scaling, and plan hashing."""

import pytest

from hyperadmin.loadtest.plan import SeedPlan, TablePlan


def _factory(pool, rng, seq):
    return {"id": seq}


def _table(name, count, *, parents=(), unique=(), columns=("id",)):
    return TablePlan(
        name=name,
        target_count=count,
        row_factory=_factory,
        columns=columns,
        fk_parents=parents,
        unique_columns=unique,
    )


class TestTablePlanValidation:
    def test_negative_target_count_rejected(self):
        with pytest.raises(ValueError, match="target_count"):
            _table("a", -1)

    def test_empty_columns_rejected(self):
        with pytest.raises(ValueError, match="must declare its columns"):
            _table("a", 1, columns=())

    def test_unique_column_must_be_in_columns(self):
        with pytest.raises(ValueError, match="not in columns"):
            _table("a", 1, columns=("id",), unique=("email",))


class TestSeedPlanOrdering:
    def test_parent_must_precede_child(self):
        """
        Scenario: child references a parent not yet seeded
          Given a plan where Invoices precede Accounts
          When  the plan is constructed
          Then  a ValueError naming the missing parent is raised
        """
        with pytest.raises(ValueError, match="not seeded earlier"):
            SeedPlan(
                (
                    _table("invoices", 10, parents=("accounts",)),
                    _table("accounts", 5),
                )
            )

    def test_valid_parent_child_order_accepted(self):
        plan = SeedPlan(
            (
                _table("accounts", 5),
                _table("invoices", 10, parents=("accounts",)),
            )
        )
        assert plan.table("invoices").fk_parents == ("accounts",)

    def test_duplicate_table_rejected(self):
        with pytest.raises(ValueError, match="duplicate table"):
            SeedPlan((_table("a", 1), _table("a", 2)))

    def test_empty_plan_rejected(self):
        with pytest.raises(ValueError, match="at least one table"):
            SeedPlan(())

    def test_non_positive_pareto_rejected(self):
        with pytest.raises(ValueError, match="pareto_a"):
            SeedPlan((_table("a", 1),), pareto_a=0)

    def test_table_lookup_missing_raises_keyerror(self):
        plan = SeedPlan((_table("a", 1),))
        with pytest.raises(KeyError):
            plan.table("nope")


class TestSeedPlanScaling:
    def test_scaling_preserves_ratio_and_sums_exactly(self):
        """
        Scenario: --count scales per-table shares proportionally
          Given a plan with weights 1:3
          When  scaled to a total of 100
          Then  the tables get 25 and 75 and the sum is exactly 100
        """
        plan = SeedPlan((_table("a", 1), _table("b", 3)))
        scaled = plan.scaled(100)
        counts = [t.target_count for t in scaled.tables]
        assert counts == [25, 75]
        assert sum(counts) == 100

    def test_largest_remainder_distributes_leftover(self):
        # 3 equal weights into 100 -> 34/33/33 (sum 100), not 33/33/33.
        plan = SeedPlan((_table("a", 1), _table("b", 1), _table("c", 1)))
        counts = [t.target_count for t in plan.scaled(100).tables]
        assert sum(counts) == 100
        assert max(counts) - min(counts) <= 1

    def test_scaling_to_zero_yields_zero_rows(self):
        plan = SeedPlan((_table("a", 1), _table("b", 3)))
        assert [t.target_count for t in plan.scaled(0).tables] == [0, 0]

    def test_every_table_gets_at_least_one_row(self):
        # A tiny share must not collapse a low-weight parent to zero rows.
        plan = SeedPlan((_table("accounts", 1), _table("invoices", 9999)))
        counts = [t.target_count for t in plan.scaled(100).tables]
        assert counts[0] >= 1
        assert sum(counts) == 100

    def test_total_below_table_count_rejected(self):
        plan = SeedPlan((_table("a", 1), _table("b", 1), _table("c", 1)))
        with pytest.raises(ValueError, match="number of tables"):
            plan.scaled(2)

    def test_negative_total_rejected(self):
        plan = SeedPlan((_table("a", 1),))
        with pytest.raises(ValueError, match="total_count"):
            plan.scaled(-5)

    def test_zero_weight_plan_cannot_scale(self):
        plan = SeedPlan((_table("a", 0),))
        with pytest.raises(ValueError, match="weights sum to 0"):
            plan.scaled(10)

    def test_scaling_preserves_pareto_and_factory(self):
        plan = SeedPlan((_table("a", 1),), pareto_a=2.0)
        scaled = plan.scaled(10)
        assert scaled.pareto_a == 2.0
        assert scaled.tables[0].row_factory is _factory


class TestSeedPlanHash:
    def test_hash_is_deterministic(self):
        plan_a = SeedPlan((_table("a", 1), _table("b", 2, parents=("a",))))
        plan_b = SeedPlan((_table("a", 1), _table("b", 2, parents=("a",))))
        assert plan_a.hash() == plan_b.hash()
        assert plan_a.hash().startswith("sha256:")

    def test_hash_changes_when_target_count_changes(self):
        """
        Scenario: schema-drift on resume aborts cleanly
          Given a plan hash for invoices target 100
          When  the invoices target changes to 200
          Then  the plan hash differs so a resume can detect the drift
        """
        before = SeedPlan((_table("invoices", 100),)).hash()
        after = SeedPlan((_table("invoices", 200),)).hash()
        assert before != after

    def test_hash_changes_when_columns_change(self):
        before = SeedPlan((_table("a", 1, columns=("id",)),)).hash()
        after = SeedPlan((_table("a", 1, columns=("id", "name")),)).hash()
        assert before != after

    def test_hash_changes_when_fk_edges_change(self):
        before = SeedPlan((_table("a", 1), _table("b", 1))).hash()
        after = SeedPlan((_table("a", 1), _table("b", 1, parents=("a",)))).hash()
        assert before != after

    def test_hash_changes_with_pareto(self):
        before = SeedPlan((_table("a", 1),), pareto_a=1.16).hash()
        after = SeedPlan((_table("a", 1),), pareto_a=2.0).hash()
        assert before != after

    def test_hash_ignores_row_factory_identity(self):
        # Two distinct factory callables with identical declared columns hash the same.
        def other_factory(pool, rng, seq):
            return {"id": seq}

        plan_a = SeedPlan((_table("a", 1),))
        plan_b = SeedPlan((TablePlan("a", 1, other_factory, ("id",)),))
        assert plan_a.hash() == plan_b.hash()
