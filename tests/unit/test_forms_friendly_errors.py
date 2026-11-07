"""Readable validation messages and the error summary (st-ux-erp-06)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from hyperadmin import Admin
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.forms import PydanticForm, friendly_error


class _Invoice(BaseModel):
    number: str
    date_issued: date
    quantity: int
    price: float
    note: str | None = None


def _validate(data: dict[str, str]) -> dict[str, list[str]]:
    _, errors = PydanticForm(_Invoice).validate(data)
    return {name: [str(m) for m in msgs] for name, msgs in errors.items()}


def test_blank_date_reads_enter_a_date() -> None:
    """
    Scenario: friendly message for a missing date
      Given the invoice form with Date issued empty
      When  the form validates
      Then  the field says "Enter a date"
    """
    errors = _validate({"number": "A1", "date_issued": "", "quantity": "1", "price": "2"})

    assert errors == {"date_issued": ["Enter a date"]}


def test_garbage_date_reads_enter_a_valid_date() -> None:
    """
    Scenario: an unparsable date is explained
      Given the invoice form with Date issued "tomorrow"
      When  the form validates
      Then  the field says "Enter a valid date"
    """
    errors = _validate({"number": "A1", "date_issued": "tomorrow", "quantity": "1", "price": "2"})

    assert errors == {"date_issued": ["Enter a valid date"]}


def test_number_and_missing_errors_use_plain_wording() -> None:
    """
    Scenario: no Pydantic wording reaches the user for common errors
      Given the invoice form with a bad integer, a bad number and no number field
      When  the form validates
      Then  each field gets plain wording
    """
    errors = _validate({"date_issued": "2026-01-01", "quantity": "x", "price": "y"})

    assert errors == {
        "number": ["This field is required"],
        "quantity": ["Enter a whole number"],
        "price": ["Enter a number"],
    }


def test_blank_required_text_reads_required() -> None:
    """
    Scenario: an empty required text input is reported as required
      Given a text field with a minimum length of one
      When  it is submitted blank
      Then  the field says "This field is required"
    """
    error = {"type": "string_too_short", "input": "", "ctx": {"min_length": 1}, "msg": "x"}

    assert str(friendly_error(error)) == "This field is required"


def test_unmapped_error_types_keep_the_pydantic_translation() -> None:
    """
    Scenario: other error types are unchanged
      Given a greater_than error
      When  it is turned into a message
      Then  it is the translated pydantic wording
    """
    error = {"type": "greater_than", "input": 1, "ctx": {"gt": 5}, "msg": "x"}

    assert str(friendly_error(error)) == "Input should be greater than 5"


@pytest.mark.parametrize(("count", "heading"), [(1, "There is a problem with 1 field"), (2, "2")])
def test_error_summary_lists_every_invalid_field(count: int, heading: str) -> None:
    """
    Scenario: error summary at the top lists every invalid field
      Given a form with invalid fields
      When  the summary renders
      Then  it names each field with its message and links to the field
    """
    admin = Admin(app=FastAPI(), settings=HyperAdminSettings(create_tables=False))
    data = {"number": "A1", "date_issued": "", "quantity": "1", "price": "2"}
    if count == 2:
        data["quantity"] = "x"
    form = PydanticForm(_Invoice)
    form.validate(data)

    html = admin.templates.get_template("components/error_summary.html").render(form=form)

    assert 'data-testid="error-summary"' in html
    assert 'href="#date_issued"' in html
    assert "Date issued: Enter a date" in html
    assert heading in html
    assert ('href="#quantity"' in html) is (count == 2)


def test_error_summary_is_absent_without_errors() -> None:
    """
    Scenario: a valid form shows no summary
      Given a form that validated
      When  the summary renders
      Then  nothing is rendered
    """
    admin = Admin(app=FastAPI(), settings=HyperAdminSettings(create_tables=False))
    form = PydanticForm(_Invoice)
    form.validate({"number": "A1", "date_issued": "2026-01-01", "quantity": "1", "price": "2"})

    html = admin.templates.get_template("components/error_summary.html").render(form=form)

    assert html.strip() == ""


def test_error_summary_lists_inline_row_and_form_level_errors() -> None:
    """
    Scenario: inline row and non-field errors appear in the summary
      Given a valid parent form, an inline row with a bad quantity, a row with only a key error
        and an error keyed to no field
      When  the summary renders
      Then  it links to the invalid row input and the row, and lists the form-level message
    """

    admin = Admin(app=FastAPI(), settings=HyperAdminSettings(create_tables=False))
    form = PydanticForm(_Invoice)
    form.validate({"number": "A1", "date_issued": "2026-01-01", "quantity": "1", "price": "2"})
    bad_field = SimpleNamespace(name="qty", label="Qty", errors=["Enter a whole number"])
    good_field = SimpleNamespace(name="sku", label="Sku", errors=None)
    rows = [
        SimpleNamespace(index=0, has_errors=False, fields=[good_field], pk_errors=None),
        SimpleNamespace(index=1, has_errors=True, fields=[good_field, bad_field], pk_errors=None),
        SimpleNamespace(index=2, has_errors=True, fields=[good_field], pk_errors=["Bad key"]),
        SimpleNamespace(index=3, has_errors=True, fields=[good_field], pk_errors=None),
    ]
    formset = SimpleNamespace(prefix="items", title="Items", rows=rows)

    html = admin.templates.get_template("components/error_summary.html").render(
        form=form,
        inline_formsets=[formset],
        errors={"number": ["ignored, a known field"], "__root__": ["Totals do not match"], "x": []},
    )

    assert 'href="#items-1-qty"' in html
    assert "Items #2 - Qty: Enter a whole number" in html
    assert 'href="#inline-items-row-2"' in html
    assert "Items #3: Bad key" in html
    assert 'href="#inline-items-row-3"' in html
    assert "Totals do not match" in html
    assert "ignored" not in html
    assert "There are problems with 4 fields" in html
