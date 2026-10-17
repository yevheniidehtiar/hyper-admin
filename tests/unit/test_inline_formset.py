"""InlineFormset primary-key codec (st-v058-byoa-31, BYOA SDD A.6).

``InlineFormset`` takes the inline model's ``PrimaryKeyInfo`` (``pk``) and parses
every submitted ``<prefix>-<i>-pk`` through it instead of guessing ``int()``. A
value the codec rejects becomes a row error; a parsed value is still only a
claim, which the adapter's ownership check verifies before any write.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel

from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.primary_key import DEFAULT_PK, PrimaryKeyInfo
from hyperadmin.views.forms import InlineFormset

UUID_PK = PrimaryKeyInfo(attr="id", python_type=uuid.UUID, generated=True)
STR_PK = PrimaryKeyInfo(attr="code", python_type=str, generated=False)


class UuidLine(BaseModel):
    id: uuid.UUID | None = None
    order_id: Any = None
    sku: str


class CodeLine(BaseModel):
    code: str | None = None
    order_id: Any = None
    sku: str


def _uuid_formset() -> InlineFormset:
    return InlineFormset(spec=InlineModelSpec(model=UuidLine, fk_field="order_id"), pk=UUID_PK)


def _code_formset() -> InlineFormset:
    return InlineFormset(spec=InlineModelSpec(model=CodeLine, fk_field="order_id"), pk=STR_PK)


def test_inline_uuid_pk_updates_that_uuid():
    """
    Scenario: inline UUID pk
      Given an inline model with a UUID pk
      When  the submitted '-pk' is a UUID string
      Then  the row updates that UUID
    """
    child = uuid.uuid4()
    formset = _uuid_formset()
    form_data = {"uuidline-0-pk": str(child).upper(), "uuidline-0-sku": "a"}

    rows = formset.extract_submitted_data(form_data)
    valid, errors = formset.validate_rows(rows, parent_pk=uuid.uuid4())

    assert errors == {}
    assert valid[0]["_pk"] == child
    assert isinstance(valid[0]["_pk"], uuid.UUID)


def test_inline_uuid_pk_marks_a_row_for_deletion():
    """
    Scenario: inline UUID pk delete
      Given an inline model with a UUID pk
      When  a row with a UUID string '-pk' is submitted with DELETE
      Then  the delete row carries that UUID
    """
    child = uuid.uuid4()
    formset = _uuid_formset()
    form_data = {"uuidline-0-pk": str(child), "uuidline-0-DELETE": "on"}

    rows = formset.extract_submitted_data(form_data)

    assert rows == [{"_delete": True, "_pk": child}]


def test_inline_invalid_pk_is_rejected_with_an_error():
    """
    Scenario: inline invalid pk
      Given an inline '-pk' value that is not a valid UUID
      When  the formset validates
      Then  the row is rejected with an error
    """
    formset = _uuid_formset()
    form_data = {"uuidline-0-pk": "not-a-uuid", "uuidline-0-sku": "a"}

    rows = formset.extract_submitted_data(form_data)
    valid, errors = formset.validate_rows(rows, parent_pk=uuid.uuid4())

    assert valid == []
    assert list(errors) == [0]
    assert "pk" in errors[0]


def test_inline_invalid_pk_on_a_delete_row_is_rejected():
    """
    Scenario: inline invalid pk on delete
      Given an inline '-pk' value that is not a valid UUID marked DELETE
      When  the formset validates
      Then  the row is rejected with an error instead of being deleted
    """
    formset = _uuid_formset()
    form_data = {"uuidline-0-pk": "zzz", "uuidline-0-DELETE": "on"}

    rows = formset.extract_submitted_data(form_data)
    valid, errors = formset.validate_rows(rows)

    assert valid == []
    assert "pk" in errors[0]


def test_inline_invalid_pk_is_shown_on_the_rebuilt_row():
    """
    Scenario: invalid pk shown on re-render
      Given an inline '-pk' value that is not a valid UUID
      When  the formset rebuilds rows from the submitted data
      Then  the row carries a pk error and reports has_errors
      And   the raw value is kept so a resubmit is never turned into a create
    """
    formset = _uuid_formset()
    form_data = {"uuidline-0-pk": "not-a-uuid", "uuidline-0-sku": "a"}

    formset.rebuild_from_submitted(form_data)

    row = formset.rows[0]
    assert row.pk == "not-a-uuid"
    assert row.pk_errors
    assert row.has_errors is True


def test_inline_valid_pk_is_parsed_on_the_rebuilt_row():
    """
    Scenario: valid pk parsed on re-render
      Given an inline '-pk' value that is a valid UUID string
      When  the formset rebuilds rows from the submitted data
      Then  the row pk is that UUID and the row has no pk error
    """
    child = uuid.uuid4()
    formset = _uuid_formset()

    formset.rebuild_from_submitted({"uuidline-0-pk": str(child), "uuidline-0-sku": "a"})

    row = formset.rows[0]
    assert row.pk == child
    assert row.pk_errors is None
    assert row.has_errors is False


def test_inline_str_pk_keeps_leading_zeros():
    """
    Scenario: natural str pk keeps leading zeros
      Given an inline model with a natural str pk
      When  the submitted '-pk' is '007'
      Then  the row pk is the string '007', not the int 7
    """
    formset = _code_formset()

    rows = formset.extract_submitted_data({"codeline-0-pk": "007", "codeline-0-sku": "a"})

    assert rows[0]["_pk"] == "007"


def test_inline_display_fields_exclude_the_inline_pk_attr():
    """
    Scenario: inline display excludes the codec's pk attr
      Given an inline model whose pk attribute is 'code'
      When  the formset lists its display fields
      Then  'code' and the FK field are excluded
    """
    assert _code_formset().display_fields == ["sku"]


def test_inline_rows_populated_from_instances_use_the_pk_codec():
    """
    Scenario: existing rows carry the codec's pk
      Given existing inline instances keyed by 'code'
      When  the formset is populated from them
      Then  each row's pk is the instance's 'code'
    """
    formset = _code_formset()

    formset.populate_from_instances([CodeLine(code="007", sku="a")])

    assert formset.rows[0].pk == "007"


def test_inline_formset_defaults_to_the_int_id_pk():
    """
    Scenario: defaults are back-compatible
      Given an InlineFormset built without a pk
      When  an int '-pk' is submitted
      Then  the formset uses DEFAULT_PK and the row pk is an int
    """

    class IntLine(BaseModel):
        id: int | None = None
        order_id: int | None = None
        sku: str

    formset = InlineFormset(spec=InlineModelSpec(model=IntLine, fk_field="order_id"))

    rows = formset.extract_submitted_data({"intline-0-pk": "42", "intline-0-sku": "a"})

    assert formset.pk is DEFAULT_PK
    assert rows[0]["_pk"] == 42


def test_inline_empty_pk_is_rejected_instead_of_creating_a_row():
    """
    Scenario: posted empty pk is not re-created
      Given an inline row rendered with an empty natural str key (hidden '-pk' = '')
      When  the form is submitted
      Then  the row is rejected with a pk error instead of being treated as a new row
    """
    formset = _code_formset()

    rows = formset.extract_submitted_data({"codeline-0-pk": "", "codeline-0-sku": "a"})
    valid, errors = formset.validate_rows(rows, parent_pk=1)

    assert rows[0]["_pk_invalid"] == ""
    assert valid == []
    assert "pk" in errors[0]


def test_inline_empty_pk_on_a_delete_row_is_rejected_not_skipped():
    """
    Scenario: posted empty pk marked DELETE is not silently dropped
      Given an inline row with an empty natural str key marked DELETE
      When  the form is submitted
      Then  the delete row is kept and rejected with a pk error
    """
    formset = _code_formset()

    rows = formset.extract_submitted_data({"codeline-0-pk": "", "codeline-0-DELETE": "on"})
    valid, errors = formset.validate_rows(rows)

    assert rows == [{"_delete": True, "_pk_invalid": ""}]
    assert valid == []
    assert "pk" in errors[0]


def test_inline_empty_pk_is_kept_on_the_rebuilt_row():
    """
    Scenario: posted empty pk survives a re-render
      Given an inline row with an empty natural str key
      When  the formset rebuilds rows from the submitted data
      Then  the row keeps the empty key and carries a pk error
    """
    formset = _code_formset()

    formset.rebuild_from_submitted({"codeline-0-pk": "", "codeline-0-sku": "a"})

    row = formset.rows[0]
    assert row.pk == ""
    assert row.pk_errors


def test_inline_new_row_without_pk_input_is_a_create():
    """
    Scenario: new row still creates
      Given an extra inline row that posts no '-pk' input
      When  the form is submitted
      Then  the row carries no key and is treated as a create
    """
    formset = _code_formset()

    rows = formset.extract_submitted_data({"codeline-0-sku": "a"})
    formset.rebuild_from_submitted({"codeline-0-sku": "a"})

    assert "_pk" not in rows[0]
    assert "_pk_invalid" not in rows[0]
    assert formset.rows[0].pk is None
