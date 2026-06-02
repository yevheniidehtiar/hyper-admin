"""Unit tests for the resumable checkpoint store (#252)."""

import json

import pytest

from hyperadmin.loadtest.checkpoint import (
    CheckpointState,
    CheckpointStore,
    PlanHashMismatchError,
    TableProgress,
    describe_drift,
    validate_resume,
)
from hyperadmin.loadtest.plan import SeedPlan, TablePlan


def _factory(pool, rng, seq):
    return {"id": seq}


def _plan(invoice_target=100, *, columns=("id",)):
    return SeedPlan(
        (
            TablePlan("accounts", 10, _factory, ("id",)),
            TablePlan("invoices", invoice_target, _factory, columns, fk_parents=("accounts",)),
        )
    )


def _state(plan, *, completed_invoices=0):
    return CheckpointState(
        plan_hash=plan.hash(),
        rng_seed=42,
        started_at="2026-05-05T10:15:00Z",
        tables={
            "accounts": TableProgress(target=10, completed=10, last_pk=10),
            "invoices": TableProgress(
                target=100, completed=completed_invoices, last_pk=completed_invoices or None
            ),
        },
    )


class TestTableProgress:
    def test_remaining_and_done(self):
        p = TableProgress(target=100, completed=35)
        assert p.remaining == 65
        assert not p.is_done
        p.completed = 100
        assert p.remaining == 0
        assert p.is_done

    def test_remaining_never_negative(self):
        assert TableProgress(target=10, completed=15).remaining == 0


class TestRoundTrip:
    def test_save_then_load_roundtrips(self, tmp_path):
        store = CheckpointStore(tmp_path / ".hyperadmin-seed.json")
        plan = _plan()
        state = _state(plan, completed_invoices=35)
        store.save(state)
        loaded = store.load()
        assert loaded.plan_hash == state.plan_hash
        assert loaded.rng_seed == 42
        assert loaded.tables["invoices"].completed == 35
        assert loaded.tables["invoices"].last_pk == 35

    def test_saved_file_is_human_readable_json(self, tmp_path):
        store = CheckpointStore(tmp_path / "state.json")
        plan = _plan()
        store.save(_state(plan))
        raw = json.loads((tmp_path / "state.json").read_text())
        assert raw["rng_seed"] == 42
        assert set(raw["tables"]) == {"accounts", "invoices"}

    def test_save_with_fsync(self, tmp_path):
        store = CheckpointStore(tmp_path / "state.json")
        plan = _plan()
        store.save(_state(plan), fsync=True)
        assert store.exists()
        # No leftover temp file after the atomic replace.
        assert not (tmp_path / "state.json.tmp").exists()

    def test_remove_is_idempotent(self, tmp_path):
        store = CheckpointStore(tmp_path / "state.json")
        store.save(_state(_plan()))
        assert store.exists()
        store.remove()
        assert not store.exists()
        store.remove()  # no error on second call

    def test_corrupt_file_raises_valueerror(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text('{"plan_hash": "x"}')  # missing required keys
        with pytest.raises(ValueError, match="corrupt checkpoint"):
            CheckpointStore(path).load()


class TestResumeValidation:
    def test_matching_plan_validates(self):
        plan = _plan()
        validate_resume(_state(plan), plan)  # no raise

    def test_target_drift_aborts_with_named_table(self):
        """
        Scenario: schema-drift on resume aborts cleanly
          Given a checkpoint written for invoices target 100
          And   the plan now targets 200 invoices
          When  validate_resume runs
          Then  it raises naming the invoices target change
        """
        old_plan = _plan(invoice_target=100)
        state = _state(old_plan)
        new_plan = _plan(invoice_target=200)
        with pytest.raises(PlanHashMismatchError, match=r"invoices.*100 -> 200"):
            validate_resume(state, new_plan)

    def test_column_drift_aborts(self):
        old_plan = _plan(columns=("id",))
        state = _state(old_plan)
        new_plan = _plan(columns=("id", "amount"))
        with pytest.raises(PlanHashMismatchError, match="plan structure changed"):
            validate_resume(state, new_plan)

    def test_table_set_change_described(self):
        plan = _plan()
        state = _state(plan)
        del state.tables["invoices"]
        state.plan_hash = "sha256:deadbeef"  # force mismatch
        msg = describe_drift(state, plan)
        assert "table set/order changed" in msg
