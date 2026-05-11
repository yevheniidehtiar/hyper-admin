"""Unit tests for AdminOptions relation_filters / relation_display / autocomplete."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlmodel import Field, SQLModel

from hyperadmin.core.options import AdminOptions, RelationDependency


class _Product(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    supplier_id: int
    variant_id: int | None = None


def test_relation_filters_defaults_to_none():
    opts = AdminOptions()
    assert opts.relation_filters is None


def test_relation_display_defaults_to_none():
    opts = AdminOptions()
    assert opts.relation_display is None


def test_use_autocomplete_widget_defaults_to_true():
    opts = AdminOptions()
    assert opts.use_autocomplete_widget is True


def test_relation_filters_accepts_dependency_model():
    opts = AdminOptions(
        relation_filters={"variant_id": RelationDependency(depends_on="supplier_id")}
    )
    assert opts.relation_filters is not None
    assert opts.relation_filters["variant_id"].depends_on == "supplier_id"
    assert opts.relation_filters["variant_id"].placeholder is None


def test_relation_filters_accepts_dict_payload():
    """Pydantic coerces a dict into a RelationDependency."""
    opts = AdminOptions(
        relation_filters={
            "variant_id": {"depends_on": "supplier_id", "placeholder": "Pick a supplier first"}
        }
    )
    assert opts.relation_filters is not None
    assert opts.relation_filters["variant_id"].placeholder == "Pick a supplier first"


def test_relation_dependency_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        RelationDependency(depends_on="x", unknown="y")  # type: ignore[call-arg]


def test_relation_display_accepts_format_string():
    opts = AdminOptions(relation_display={"supplier_id": "{name} — {city}"})
    assert opts.relation_display is not None
    assert opts.relation_display["supplier_id"] == "{name} — {city}"


def test_relation_display_accepts_callable():
    def _label(instance: object) -> str:
        return str(instance)

    opts = AdminOptions(relation_display={"supplier_id": _label})
    assert opts.relation_display is not None
    assert opts.relation_display["supplier_id"] is _label


def test_validate_against_model_passes_for_known_field():
    opts = AdminOptions(
        relation_filters={"variant_id": RelationDependency(depends_on="supplier_id")}
    )
    # supplier_id exists on _Product — should not raise.
    opts.validate_against_model(_Product)


def test_validate_against_model_raises_for_unknown_field():
    opts = AdminOptions(relation_filters={"variant_id": RelationDependency(depends_on="missing")})
    with pytest.raises(ValueError, match="depends_on='missing' not in form fields"):
        opts.validate_against_model(_Product)


def test_validate_against_model_noop_when_relation_filters_unset():
    """No relation_filters → validation is a no-op."""
    opts = AdminOptions()
    opts.validate_against_model(_Product)  # must not raise


def test_use_autocomplete_widget_can_be_disabled():
    opts = AdminOptions(use_autocomplete_widget=False)
    assert opts.use_autocomplete_widget is False
