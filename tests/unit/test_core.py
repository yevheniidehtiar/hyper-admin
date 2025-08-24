"""Unit tests for the hyperadmin.core module."""


def test_import_core() -> None:
    """Verify that the hyperadmin.core module can be imported."""
    from hyperadmin import core

    assert core is not None
