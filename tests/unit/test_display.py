from enum import Enum, IntEnum

import pytest
from sqlmodel import Field, SQLModel

from hyperadmin.core.display import (
    get_display_name,
    get_enum_label,
    get_field_label,
    humanize_class_name,
    pluralize,
)


def test_get_display_name_overridden_str():
    class CustomUser(SQLModel):
        name: str

        def __str__(self):
            return f"User: {self.name}"

    user = CustomUser(name="Alice")
    assert get_display_name(user) == "User: Alice"


def test_get_display_name_from_name_attr():
    class UserWithName(SQLModel):
        name: str

    user = UserWithName(name="Bob")
    assert get_display_name(user) == "Bob"


def test_get_display_name_from_title_attr():
    class Product(SQLModel):
        title: str

    product = Product(title="Widget")
    assert get_display_name(product) == "Widget"


def test_get_display_name_from_email_attr():
    class Profile(SQLModel):
        email: str

    profile = Profile(email="test@example.com")
    assert get_display_name(profile) == "test@example.com"


def test_get_display_name_fallback_to_pk():
    class LegacyModel(SQLModel):
        id: int | None = Field(default=None, primary_key=True)

    item = LegacyModel(id=123)
    assert get_display_name(item) == "LegacyModel (123)"


def test_get_display_name_final_fallback():
    class EmptyModel(SQLModel):
        pass

    item = EmptyModel()
    assert get_display_name(item) == "EmptyModel object"


def test_get_display_name_empty_attribute_fallback():
    class UserWithEmptyName(SQLModel):
        id: int = Field(primary_key=True)
        name: str

    user = UserWithEmptyName(id=1, name="")
    assert get_display_name(user) == "UserWithEmptyName (1)"


# ---------------------------------------------------------------------------
# Story scenario (st-v058-byoa-23)
# ---------------------------------------------------------------------------


def test_get_display_name_falls_back_to_a_non_id_pk():
    """
    Scenario: display name falls back to the pk
      Given a model with pk 'code' and no name attribute
      When  get_display_name(pk_attr='code') runs
      Then  'Country (NL)' is returned
    """

    class Country(SQLModel):
        code: str = Field(primary_key=True)

    country = Country(code="NL")

    assert get_display_name(country, pk_attr="code") == "Country (NL)"


# ── get_field_label ────────────────────────────────────────────────────


class TestGetFieldLabel:
    @pytest.mark.parametrize(
        ("field_name", "expected"),
        [
            ("user_id", "User"),
            ("category_pk", "Category"),
            ("parent_fk", "Parent"),
            ("created_at", "Created At"),
            ("email", "Email"),
            ("is_active", "Is Active"),
            ("first_name", "First Name"),
            ("id", "Id"),
        ],
    )
    def test_label_generation(self, field_name: str, expected: str) -> None:
        assert get_field_label(field_name) == expected


class _ContactType(str, Enum):
    CUSTOMER = "Customer"
    IN_PROGRESS = "in progress"
    TO_PAY = "to_pay"
    BLANK = ""


class _Priority(IntEnum):
    VERY_HIGH = 3


class _Labelled(Enum):
    VIP = "vip"

    @property
    def label(self) -> str:
        return "Very important"


@pytest.mark.parametrize(
    ("member", "expected"),
    [
        (_ContactType.CUSTOMER, "Customer"),
        (_ContactType.IN_PROGRESS, "in progress"),
        (_ContactType.TO_PAY, "To pay"),
        (_ContactType.BLANK, "Blank"),
        (_Priority.VERY_HIGH, "Very high"),
        (_Labelled.VIP, "Very important"),
    ],
)
def test_get_enum_label_never_shows_the_class_qualified_name(member: Enum, expected: str) -> None:
    """
    Scenario: enum members get a readable label
      Given a (str, Enum) member whose str() is "ContactType.CUSTOMER"
      When  get_enum_label(member) runs
      Then  the label is its .label, its human-written value, its humanised
            slug value, or its humanised name — never the qualified name
    """
    assert get_enum_label(member) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Contact", "Contact"), ("InvoiceItem", "Invoice item"), ("HTTPLogEntry", "HTTP log entry")],
)
def test_humanize_class_name(name: str, expected: str) -> None:
    assert humanize_class_name(name) == expected


@pytest.mark.parametrize(
    ("noun", "expected"),
    [
        ("Item", "Items"),
        ("Address", "Addresses"),
        ("Box", "Boxes"),
        ("Batch", "Batches"),
        ("Journal entry", "Journal entries"),
        ("Day", "Days"),
        ("y", "ys"),
    ],
)
def test_pluralize_regular_english_nouns(noun: str, expected: str) -> None:
    """
    Scenario: sidebar labels are proper plurals
      Given a model named Address or JournalEntry
      When  its plural label is derived
      Then  it reads "Addresses" / "Journal entries", not "Addresss" / "JournalEntrys"
    """
    assert pluralize(noun) == expected
