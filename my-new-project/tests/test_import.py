"""Test my-new-project."""

import my-new-project


def test_import() -> None:
    """Test that the package can be imported."""
    assert isinstance(my-new-project.__name__, str)
