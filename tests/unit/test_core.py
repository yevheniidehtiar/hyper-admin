"""Unit tests for the hyperadmin.core module."""

from hyperadmin import core


def test_import_core() -> None:
    """Verify that the hyperadmin.core module can be imported."""
    assert core is not None
