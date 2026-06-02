"""Bulk synthetic-data seeding for load testing.

This package is intentionally decoupled from the admin core: it has no ``Admin()`` coupling
and is consumed only by the ``hyperadmin seed`` CLI subcommand and by ``examples/erp/seed.py``.
Import the seeder explicitly — it is not re-exported from the top-level ``hyperadmin`` package.
"""

from hyperadmin.loadtest.batch import BulkSeeder, SeedInterruptedError, SeedSummary
from hyperadmin.loadtest.checkpoint import (
    CheckpointState,
    CheckpointStore,
    PlanHashMismatchError,
)
from hyperadmin.loadtest.plan import SeedPlan, TablePlan
from hyperadmin.loadtest.pool import EmptyPoolError, FKPool

__all__ = [
    "BulkSeeder",
    "CheckpointState",
    "CheckpointStore",
    "EmptyPoolError",
    "FKPool",
    "PlanHashMismatchError",
    "SeedInterruptedError",
    "SeedPlan",
    "SeedSummary",
    "TablePlan",
]
