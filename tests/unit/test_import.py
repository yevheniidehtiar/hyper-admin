"""Test HyperAdmin."""

import hyperadmin


def test_import() -> None:
    """Test that the package can be imported."""
    assert isinstance(hyperadmin.__name__, str)
