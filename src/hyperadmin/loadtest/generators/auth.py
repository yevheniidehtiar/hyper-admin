"""Auth seed plan: Users and Groups.

Independent of the ERP chain — no FK edges between the two tables. ``username`` and ``email``
derive from the global sequence so they stay unique across batches. ``password_hash`` is a
fixed placeholder: the seeder produces load-test fixtures, not authenticatable accounts.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hyperadmin.loadtest.plan import SeedPlan, TablePlan

# Non-secret placeholder; these accounts are not meant to be logged into.
_PLACEHOLDER_HASH = "$seed$" + "x" * 54

_WEIGHTS = {
    "hyperadmin_users": 100,
    "hyperadmin_groups": 5,
}


def build_auth_plan(*, seed: int = 42) -> SeedPlan:
    """Return the auth :class:`SeedPlan` with a deterministically seeded Faker."""
    from faker import Faker  # noqa: PLC0415 - dev-only dep, imported when a plan is built

    fake = Faker()
    fake.seed_instance(seed)
    created = datetime.now(timezone.utc).replace(tzinfo=None)

    def users(pool, rng, seq):  # noqa: ARG001
        return {
            "username": f"user_{seq:08d}",
            "email": f"user{seq}@{fake.domain_name()}",
            "password_hash": _PLACEHOLDER_HASH,
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "is_active": True,
            "is_superuser": False,
            "mfa_enabled": False,
            "mfa_method": None,
            "created_at": created,
            "updated_at": None,
        }

    def groups(pool, rng, seq):  # noqa: ARG001
        return {
            "name": f"group_{seq:08d}",
            "description": fake.catch_phrase(),
            "is_active": True,
            "created_at": created,
        }

    return SeedPlan(
        (
            TablePlan(
                "hyperadmin_users",
                _WEIGHTS["hyperadmin_users"],
                users,
                (
                    "username",
                    "email",
                    "password_hash",
                    "first_name",
                    "last_name",
                    "is_active",
                    "is_superuser",
                    "mfa_enabled",
                    "mfa_method",
                    "created_at",
                    "updated_at",
                ),
                unique_columns=("username",),
            ),
            TablePlan(
                "hyperadmin_groups",
                _WEIGHTS["hyperadmin_groups"],
                groups,
                ("name", "description", "is_active", "created_at"),
                unique_columns=("name",),
            ),
        )
    )


__all__ = ["build_auth_plan"]
