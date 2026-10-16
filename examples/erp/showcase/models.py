"""Field & widget showcase for the hosted ERP demo.

``FieldShowcase`` exists purely to exercise every HyperAdmin widget that the
rest of the ERP domain (contacts/sales/purchases/accounting) doesn't
naturally need. Each field's ``title=`` names the widget it renders so a demo
visitor can match what they see to ``docs/frontend/widgets.md``.

Two widgets from ``hyperadmin.views.forms`` are *not* exercised here:
``RelationMultiSelectWidget`` (M2M) and the ``preload=False`` / "remote"
variant of ``RelationSelectWidget``. Both require the FK/M2M field to be
exposed as a Pydantic field pointing at the ORM *relationship* attribute
(not the ``_id`` column) so that ``classify_field()`` finds it via
``mapper.relationships``. SQLModel's ``Relationship()`` does not add an
entry to ``model_fields`` for either a to-one or a to-many relationship, so
that path is unreachable through the model-declaration convention used
throughout this codebase (verified empirically; see the PR description).

``launched_at`` below is typed ``Optional[datetime]`` (``typing.Optional``)
rather than the more modern ``datetime | None``. This is a deliberate
workaround, not a style choice: ``PydanticForm._pick_widget``'s legacy
Optional-unwrapping (``views/forms.py``) only recognises
``get_origin(ann) is typing.Union``, not ``types.UnionType`` — the origin
``X | None`` actually produces. With PEP 604 syntax the unwrap silently
no-ops and the field falls through to ``TextInput`` instead of
``DateTimeInput`` (also ``CheckboxInput``/``NumberInput``/``FloatInput`` for
an optional bool/int/float). ``examples/simple/models.py`` hits the same bug
on ``User.created_at`` / ``Product.release_date``. See the PR description.

A third gap, left as-is rather than worked around: ``MultiSelectWidget``'s
enum choices (``PydanticForm._enum_choices()`` in ``views/forms.py``) are
always built with ``selected=False``, and nothing downstream re-marks them
against the field's current value. So re-opening the edit form for an
existing ``tags`` value never shows the previously-saved selections —
visible, but not fixable from here. See the PR description.
"""

import enum
from datetime import datetime
from typing import Optional

from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType, ImageType
from sqlalchemy import JSON, Column
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

from examples.erp.contacts.models import Contact

#: Mounted at /uploads/ by Admin(storage=...) in examples/erp/main.py.
showcase_storage = FileSystemStorage("uploads")


class Priority(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class ProductTag(str, enum.Enum):
    NEW = "New"
    FEATURED = "Featured"
    ON_SALE = "On Sale"
    LIMITED = "Limited"
    DISCONTINUED = "Discontinued"


class ShowcaseCategory(SQLModel, table=True):
    """Parent side of the cascading-select demo (RelationSelectWidget, preloaded)."""

    __tablename__ = "erp_showcase_categories"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)

    def __str__(self) -> str:
        return self.name


class ShowcaseSubcategory(SQLModel, table=True):
    """Child side of the cascading-select demo.

    Its ``category_id`` column is the filter target that
    ``FieldShowcaseAdmin.options.dependent_fields`` forwards when the parent
    ``category_id`` select changes.
    """

    __tablename__ = "erp_showcase_subcategories"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    category_id: int = Field(foreign_key="erp_showcase_categories.id")
    category: ShowcaseCategory = Relationship(sa_relationship_kwargs={"lazy": "selectin"})

    def __str__(self) -> str:
        return self.name


class FieldShowcase(SQLModel, table=True):
    """One model, one field per HyperAdmin widget. See the module docstring."""

    __tablename__ = "erp_field_showcase"  # type: ignore

    id: int | None = Field(default=None, primary_key=True)

    name: str = Field(
        index=True,
        title="Name (TextInput)",
        description="Plain single-line text input — the default widget.",
    )

    description: str | None = Field(
        default=None,
        title="Description (Textarea)",
        description="Long-form text; auto-selected because the field is named 'description'.",
    )

    quantity_in_stock: int = Field(
        default=0,
        ge=0,
        title="Quantity in stock (NumberInput)",
        description="Integer input, selected because the field's type is int.",
    )

    unit_price: float = Field(
        default=0.0,
        ge=0,
        title="Unit price (FloatInput)",
        description="Decimal input (step=any), selected because the field's type is float.",
    )

    is_active: bool = Field(
        default=True,
        title="Is active (CheckboxInput)",
        description="Boolean checkbox, selected because the field's type is bool.",
    )

    priority: Priority = Field(
        default=Priority.MEDIUM,
        title="Priority (SelectWidget, enum)",
        description="Single choice from a str Enum, rendered as a <select>.",
    )

    tags: list[ProductTag] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        title="Tags (MultiSelectWidget, list[Enum])",
        description="Multiple choices from a str Enum, rendered as a multi-select.",
    )

    launched_at: Optional[datetime] = Field(  # noqa: UP045 — see module docstring
        default=None,
        title="Launched at (DateTimeInput)",
        description="Date + time picker, selected because the field's type is datetime.",
    )

    manual_file: str | None = Field(
        default=None,
        sa_column=Column(FileType(storage=showcase_storage)),
        title="Manual (FileInputWidget, file)",
        description="Generic file upload — stores the uploaded filename.",
    )

    photo: str | None = Field(
        default=None,
        sa_column=Column(ImageType(storage=showcase_storage)),
        title="Photo (FileInputWidget, image)",
        description="Image upload — renders a thumbnail preview once set.",
    )

    category_id: int | None = Field(
        default=None,
        foreign_key="erp_showcase_categories.id",
        title="Category (RelationSelectWidget, preloaded FK)",
        description="Foreign key; choices are preloaded into the page.",
    )
    category: Mapped[ShowcaseCategory | None] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    subcategory_id: int | None = Field(
        default=None,
        foreign_key="erp_showcase_subcategories.id",
        title="Subcategory (RelationSelectWidget, preloaded FK)",
        description=(
            "Foreign key select widget. FieldShowcaseAdmin also configures "
            "dependent_fields/relation_filters against 'category_id' — see the "
            "module docstring for why that cascading config has no visible effect here."
        ),
    )
    subcategory: Mapped[ShowcaseSubcategory | None] = Relationship(
        sa_relationship_kwargs={"lazy": "selectin"}
    )

    supplier_id: int | None = Field(
        default=None,
        foreign_key="erp_contacts.id",
        title="Supplier (RelationSelectWidget, cross-app FK)",
        description="Foreign key into the Contacts app.",
    )
    supplier: Mapped[Contact | None] = Relationship(sa_relationship_kwargs={"lazy": "selectin"})

    def __str__(self) -> str:
        return self.name
