"""Unit tests for FKPool: population, sampling contract, and Pareto skew (#250/#251)."""

import random
from collections import Counter

import pytest

from hyperadmin.loadtest import pool as pool_module
from hyperadmin.loadtest.pool import EmptyPoolError, FKPool


def _pool(seed=42, pareto_a=1.16):
    return FKPool(pareto_a=pareto_a, rng=random.Random(seed))  # noqa: S311 - test RNG


class TestPopulation:
    def test_extend_and_size(self):
        p = _pool()
        p.extend("accounts", [1, 2, 3])
        p.extend("accounts", [4, 5])
        assert p.size("accounts") == 5
        assert len(p) == 5

    def test_size_of_unknown_table_is_zero(self):
        assert _pool().size("nope") == 0

    def test_len_sums_across_tables(self):
        p = _pool()
        p.extend("accounts", range(10))
        p.extend("contacts", range(3))
        assert len(p) == 13

    def test_contains(self):
        p = _pool()
        p.extend("accounts", [1])
        assert "accounts" in p
        assert "contacts" not in p

    def test_pareto_a_must_exceed_one(self):
        with pytest.raises(ValueError, match="pareto_a"):
            FKPool(pareto_a=1.0)


class TestSamplingContract:
    def test_sample_empty_pool_raises(self):
        """
        Scenario: empty FK pool when child batch starts
          Given a child table whose parent pool was never populated
          When  the seeder samples the parent
          Then  an EmptyPoolError naming the parent is raised
        """
        with pytest.raises(EmptyPoolError, match="accounts"):
            _pool().sample("accounts")

    def test_sample_many_empty_pool_raises(self):
        with pytest.raises(EmptyPoolError):
            _pool().sample_many("accounts", 5)

    def test_sample_returns_member(self):
        p = _pool()
        p.extend("accounts", [10, 20, 30])
        for _ in range(50):
            assert p.sample("accounts") in {10, 20, 30}

    def test_sample_many_returns_n_members(self):
        p = _pool()
        ids = list(range(100, 200))
        p.extend("accounts", ids)
        drawn = p.sample_many("accounts", 500)
        assert len(drawn) == 500
        assert set(drawn) <= set(ids)

    def test_sample_many_zero_returns_empty(self):
        p = _pool()
        p.extend("accounts", [1, 2, 3])
        assert p.sample_many("accounts", 0) == []

    def test_sample_many_negative_raises(self):
        p = _pool()
        p.extend("accounts", [1, 2, 3])
        with pytest.raises(ValueError, match="n must be >= 0"):
            p.sample_many("accounts", -1)

    def test_single_member_pool_always_returns_it(self):
        p = _pool()
        p.extend("accounts", [99])
        assert p.sample("accounts") == 99
        assert p.sample_many("accounts", 10) == [99] * 10


class TestParetoSkew:
    def _skew_fraction(self, drawn, n_accounts):
        """Fraction of draws landing in the top 20% of account ranks."""
        top_cut = n_accounts // 5  # ranks [0, top_cut) are the "hot" 20%
        hot = sum(1 for pk in drawn if pk < top_cut)
        return hot / len(drawn)

    def test_top_20_percent_own_roughly_80_percent_numpy_path(self):
        """
        Scenario: FK reference distribution follows the configured Pareto skew
          Given 1000 Accounts and 100000 Invoices
          When  invoice.account_id values are tallied
          Then  the top 20% of accounts own ~80% of invoices (within +/- 5%)
        """
        p = _pool()
        p.extend("accounts", range(1000))  # PKs 0..999 == ranks
        drawn = p.sample_many("accounts", 100_000)  # >= 64 -> numpy fast path
        fraction = self._skew_fraction(drawn, 1000)
        assert 0.75 <= fraction <= 0.85

    def test_top_20_percent_skew_stdlib_path(self, monkeypatch):
        # Force the pure-stdlib fallback and confirm the same skew holds.
        monkeypatch.setattr(pool_module, "_HAS_NUMPY", False)
        p = _pool()
        p.extend("accounts", range(1000))
        drawn = p.sample_many("accounts", 100_000)
        fraction = self._skew_fraction(drawn, 1000)
        assert 0.75 <= fraction <= 0.85

    def test_no_id_referenced_more_than_total_draws(self):
        p = _pool()
        p.extend("accounts", range(1000))
        n = 100_000
        counts = Counter(p.sample_many("accounts", n))
        assert max(counts.values()) <= n
        assert all(pk in range(1000) for pk in counts)

    def test_distribution_is_reproducible_under_fixed_seed(self):
        a = _pool(seed=7)
        b = _pool(seed=7)
        a.extend("accounts", range(500))
        b.extend("accounts", range(500))
        assert a.sample_many("accounts", 1000) == b.sample_many("accounts", 1000)

    def test_scalar_sample_is_reproducible(self):
        a = _pool(seed=7)
        b = _pool(seed=7)
        a.extend("accounts", range(500))
        b.extend("accounts", range(500))
        assert [a.sample("accounts") for _ in range(200)] == [
            b.sample("accounts") for _ in range(200)
        ]
