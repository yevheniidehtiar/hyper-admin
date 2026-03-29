"""Unit tests for custom form layouts (#67).

Covers:
- FormLayout enum values
- AdminOptions.form_layout / form_fields configuration
- FieldsetSpec dataclass
- FieldsetGroup slug generation
- PydanticForm field ordering via form_fields
- PydanticForm.fieldset_groups grouping logic
- PydanticForm.layout_css_class for single / two-column layouts
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from hyperadmin.core.fieldsets import FieldsetSpec
from hyperadmin.core.layouts import FormLayout
from hyperadmin.core.options import AdminOptions
from hyperadmin.views.forms import FieldsetGroup, PydanticForm

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class SampleModel(BaseModel):
    name: str = Field(title="Name")
    email: str = Field(title="Email")
    age: int = Field(title="Age")
    bio: str | None = Field(None, title="Biography")


# ---------------------------------------------------------------------------
# FormLayout enum
# ---------------------------------------------------------------------------


def test_form_layout_single_value() -> None:
    assert FormLayout.SINGLE == "single"


def test_form_layout_two_column_value() -> None:
    assert FormLayout.TWO_COLUMN == "two-column"


def test_form_layout_is_string_subclass() -> None:
    assert isinstance(FormLayout.SINGLE, str)
    assert isinstance(FormLayout.TWO_COLUMN, str)


# ---------------------------------------------------------------------------
# FieldsetSpec dataclass
# ---------------------------------------------------------------------------


def test_fieldset_spec_defaults() -> None:
    fs = FieldsetSpec(name="Basic")
    assert fs.name == "Basic"
    assert fs.fields == []
    assert fs.collapsed is False
    assert fs.description is None


def test_fieldset_spec_with_fields() -> None:
    fs = FieldsetSpec(name="Info", fields=["name", "email"], collapsed=True, description="Help")
    assert fs.fields == ["name", "email"]
    assert fs.collapsed is True
    assert fs.description == "Help"


# ---------------------------------------------------------------------------
# FieldsetGroup
# ---------------------------------------------------------------------------


def test_fieldset_group_slug_auto() -> None:
    group = FieldsetGroup(name="Basic Info", fields=[])
    assert group.slug == "basic-info"


def test_fieldset_group_slug_explicit() -> None:
    group = FieldsetGroup(name="Advanced", fields=[], slug="adv")
    assert group.slug == "adv"


def test_fieldset_group_empty_name() -> None:
    group = FieldsetGroup(name="", fields=[])
    assert group.slug == ""


# ---------------------------------------------------------------------------
# AdminOptions — new fields
# ---------------------------------------------------------------------------


def test_admin_options_fieldsets_default() -> None:
    opts = AdminOptions()
    assert opts.fieldsets == []


def test_admin_options_form_layout_default() -> None:
    opts = AdminOptions()
    assert opts.form_layout == FormLayout.SINGLE


def test_admin_options_form_fields_default() -> None:
    opts = AdminOptions()
    assert opts.form_fields == []


def test_admin_options_form_layout_two_column() -> None:
    opts = AdminOptions(form_layout=FormLayout.TWO_COLUMN)
    assert opts.form_layout == FormLayout.TWO_COLUMN


def test_admin_options_form_fields_custom() -> None:
    opts = AdminOptions(form_fields=["name", "email"])
    assert opts.form_fields == ["name", "email"]


def test_admin_options_fieldsets_custom() -> None:
    opts = AdminOptions(
        fieldsets=[
            FieldsetSpec(name="Basic", fields=["name", "email"]),
            FieldsetSpec(name="Extra", fields=["age"], collapsed=True),
        ]
    )
    assert len(opts.fieldsets) == 2
    assert opts.fieldsets[0].name == "Basic"
    assert opts.fieldsets[1].collapsed is True


# ---------------------------------------------------------------------------
# PydanticForm.fields — ordering via form_fields
# ---------------------------------------------------------------------------


def test_form_fields_default_order() -> None:
    form = PydanticForm(model=SampleModel)
    names = [f.name for f in form.fields]
    assert names == ["name", "email", "age", "bio"]


def test_form_fields_custom_order() -> None:
    form = PydanticForm(model=SampleModel, form_fields=["bio", "age", "name"])
    names = [f.name for f in form.fields]
    assert names == ["bio", "age", "name"]


def test_form_fields_subset() -> None:
    """form_fields should act as both an ordering AND inclusion filter."""
    form = PydanticForm(model=SampleModel, form_fields=["email", "name"])
    names = [f.name for f in form.fields]
    assert names == ["email", "name"]
    assert "age" not in names
    assert "bio" not in names


def test_form_fields_skips_unknown() -> None:
    """Unknown field names in form_fields are silently skipped."""
    form = PydanticForm(model=SampleModel, form_fields=["name", "nonexistent", "age"])
    names = [f.name for f in form.fields]
    assert names == ["name", "age"]


# ---------------------------------------------------------------------------
# PydanticForm.layout_css_class
# ---------------------------------------------------------------------------


def test_layout_css_class_single() -> None:
    form = PydanticForm(model=SampleModel, form_layout=FormLayout.SINGLE)
    assert form.layout_css_class == ""


def test_layout_css_class_two_column() -> None:
    form = PydanticForm(model=SampleModel, form_layout=FormLayout.TWO_COLUMN)
    assert form.layout_css_class == "ha-form-grid-2"


def test_layout_css_class_none_defaults_empty() -> None:
    form = PydanticForm(model=SampleModel)
    assert form.layout_css_class == ""


# ---------------------------------------------------------------------------
# PydanticForm.fieldset_groups
# ---------------------------------------------------------------------------


def test_fieldset_groups_no_fieldsets() -> None:
    """Without fieldsets, returns a single unnamed group with all fields."""
    form = PydanticForm(model=SampleModel)
    groups = form.fieldset_groups
    assert len(groups) == 1
    assert groups[0].name == ""
    assert [f.name for f in groups[0].fields] == ["name", "email", "age", "bio"]


def test_fieldset_groups_with_fieldsets() -> None:
    form = PydanticForm(
        model=SampleModel,
        fieldsets=[
            FieldsetSpec(name="Contact", fields=["name", "email"]),
            FieldsetSpec(name="Details", fields=["age"], collapsed=True),
        ],
    )
    groups = form.fieldset_groups
    # Two declared groups + one "Other fields" for unclaimed "bio"
    assert len(groups) == 3
    assert groups[0].name == "Contact"
    assert [f.name for f in groups[0].fields] == ["name", "email"]
    assert groups[1].name == "Details"
    assert groups[1].collapsed is True
    assert [f.name for f in groups[1].fields] == ["age"]
    assert groups[2].name == "Other fields"
    assert [f.name for f in groups[2].fields] == ["bio"]


def test_fieldset_groups_all_fields_claimed() -> None:
    """When all fields are claimed, no trailing group is created."""
    form = PydanticForm(
        model=SampleModel,
        fieldsets=[
            FieldsetSpec(name="All", fields=["name", "email", "age", "bio"]),
        ],
    )
    groups = form.fieldset_groups
    assert len(groups) == 1
    assert groups[0].name == "All"


def test_fieldset_groups_unknown_fields_skipped() -> None:
    """Fields referenced in a fieldset but not on the model are skipped."""
    form = PydanticForm(
        model=SampleModel,
        fieldsets=[
            FieldsetSpec(name="Partial", fields=["name", "nonexistent"]),
        ],
    )
    groups = form.fieldset_groups
    assert groups[0].name == "Partial"
    assert [f.name for f in groups[0].fields] == ["name"]


def test_fieldset_groups_with_form_fields_ordering() -> None:
    """form_fields + fieldsets: fieldsets group the ordered fields."""
    form = PydanticForm(
        model=SampleModel,
        form_fields=["age", "name"],
        fieldsets=[
            FieldsetSpec(name="Ordered", fields=["age", "name"]),
        ],
    )
    groups = form.fieldset_groups
    assert len(groups) == 1
    assert [f.name for f in groups[0].fields] == ["age", "name"]


# --- Combined: layout + fieldsets ---


def test_two_column_with_fieldsets() -> None:
    """Two-column layout + fieldsets: layout_css_class is set, groups are formed."""
    form = PydanticForm(
        model=SampleModel,
        form_layout=FormLayout.TWO_COLUMN,
        fieldsets=[
            FieldsetSpec(name="Basic", fields=["name", "email"]),
        ],
    )
    assert form.layout_css_class == "ha-form-grid-2"
    groups = form.fieldset_groups
    assert groups[0].name == "Basic"
    assert len(groups) == 2  # Basic + Other fields (age, bio)
