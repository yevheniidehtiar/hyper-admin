"""Unit tests for fieldset specification and form grouping."""

from __future__ import annotations

from pydantic import BaseModel

from hyperadmin.core.fieldsets import FieldsetSpec
from hyperadmin.core.options import AdminOptions
from hyperadmin.views.forms import FieldsetGroup, PydanticForm

# --- FieldsetSpec dataclass ---


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


# --- FieldsetGroup ---


def test_fieldset_group_slug_auto() -> None:
    group = FieldsetGroup(name="Basic Info", fields=[])
    assert group.slug == "basic-info"


def test_fieldset_group_slug_explicit() -> None:
    group = FieldsetGroup(name="Advanced", fields=[], slug="adv")
    assert group.slug == "adv"


def test_fieldset_group_empty_name() -> None:
    group = FieldsetGroup(name="", fields=[])
    assert group.slug == ""


# --- AdminOptions.fieldsets ---


def test_admin_options_fieldsets_default() -> None:
    opts = AdminOptions()
    assert opts.fieldsets == []


def test_admin_options_fieldsets_set() -> None:
    opts = AdminOptions(
        fieldsets=[
            FieldsetSpec(name="Basic", fields=["name"]),
            FieldsetSpec(name="Extra", fields=["email"], collapsed=True),
        ]
    )
    assert len(opts.fieldsets) == 2
    assert opts.fieldsets[0].name == "Basic"
    assert opts.fieldsets[1].collapsed is True


# --- PydanticForm.fieldset_groups ---


class SimpleModel(BaseModel):
    name: str = ""
    email: str = ""
    age: int = 0
    bio: str = ""


def test_fieldset_groups_no_fieldsets() -> None:
    form = PydanticForm(SimpleModel)
    groups = form.fieldset_groups
    assert len(groups) == 1
    assert groups[0].name == ""
    field_names = [f.name for f in groups[0].fields]
    assert "name" in field_names
    assert "email" in field_names


def test_fieldset_groups_with_specs() -> None:
    specs = [
        FieldsetSpec(name="Identity", fields=["name", "email"]),
        FieldsetSpec(name="Details", fields=["age"], collapsed=True, description="Extra info"),
    ]
    form = PydanticForm(SimpleModel, fieldsets=specs)
    groups = form.fieldset_groups

    # 3 groups: Identity, Details, Other fields (bio is unclaimed)
    assert len(groups) == 3

    assert groups[0].name == "Identity"
    assert [f.name for f in groups[0].fields] == ["name", "email"]
    assert groups[0].collapsed is False

    assert groups[1].name == "Details"
    assert [f.name for f in groups[1].fields] == ["age"]
    assert groups[1].collapsed is True
    assert groups[1].description == "Extra info"

    assert groups[2].name == "Other fields"
    assert [f.name for f in groups[2].fields] == ["bio"]


def test_fieldset_groups_all_fields_claimed() -> None:
    specs = [
        FieldsetSpec(name="All", fields=["name", "email", "age", "bio"]),
    ]
    form = PydanticForm(SimpleModel, fieldsets=specs)
    groups = form.fieldset_groups
    assert len(groups) == 1
    assert groups[0].name == "All"
    assert len(groups[0].fields) == 4


def test_fieldset_groups_skips_unknown_fields() -> None:
    specs = [
        FieldsetSpec(name="Partial", fields=["name", "nonexistent"]),
    ]
    form = PydanticForm(SimpleModel, fieldsets=specs)
    groups = form.fieldset_groups
    # "Partial" group has only "name", remaining fields go to "Other fields"
    assert groups[0].name == "Partial"
    assert [f.name for f in groups[0].fields] == ["name"]
    assert groups[1].name == "Other fields"


def test_fieldset_groups_empty_spec_skipped() -> None:
    specs = [
        FieldsetSpec(name="Empty", fields=["nonexistent_only"]),
        FieldsetSpec(name="Real", fields=["name"]),
    ]
    form = PydanticForm(SimpleModel, fieldsets=specs)
    groups = form.fieldset_groups
    # "Empty" group should be skipped (no matching fields)
    assert groups[0].name == "Real"
    assert groups[1].name == "Other fields"


def test_fieldset_group_slug_generation() -> None:
    specs = [
        FieldsetSpec(name="Basic Info", fields=["name"]),
    ]
    form = PydanticForm(SimpleModel, fieldsets=specs)
    groups = form.fieldset_groups
    assert groups[0].slug == "basic-info"
