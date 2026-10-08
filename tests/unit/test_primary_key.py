"""Unit tests for ``hyperadmin.core.primary_key`` and the ``BaseAdapter.pk`` contract."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

import pytest
from pydantic import AwareDatetime, BaseModel

from hyperadmin.core import DEFAULT_PK, InvalidPrimaryKey, PrimaryKeyInfo
from hyperadmin.core.adapters import BaseAdapter

UUID_PK = PrimaryKeyInfo(attr="id", python_type=uuid.UUID, generated=True)
STR_PK = PrimaryKeyInfo(attr="code", python_type=str, generated=False)
INT_PK = PrimaryKeyInfo(attr="id", python_type=int, generated=True)


# ---------------------------------------------------------------------------
# Story scenarios (st-v058-byoa-13)
# ---------------------------------------------------------------------------


def test_invalid_uuid_raises_invalid_primary_key() -> None:
    """
    Scenario: invalid UUID raises InvalidPrimaryKey
      Given PrimaryKeyInfo(python_type=uuid.UUID)
      When  parse('not-a-uuid') is called
      Then  InvalidPrimaryKey is raised
    """
    with pytest.raises(InvalidPrimaryKey):
        UUID_PK.parse("not-a-uuid")


def test_int_keys_stay_numeric_in_json() -> None:
    """
    Scenario: int keys stay numeric in JSON
      Given an int PrimaryKeyInfo
      When  to_json(7) is called
      Then  the int 7 is returned
    """
    result = INT_PK.to_json(7)

    assert result == 7
    assert isinstance(result, int)
    assert json.dumps({"id": result}) == '{"id": 7}'


def test_empty_string_key_is_rejected() -> None:
    """
    Scenario: empty string key is rejected
      Given a str PrimaryKeyInfo
      When  parse('') is called
      Then  InvalidPrimaryKey is raised
    """
    with pytest.raises(InvalidPrimaryKey):
        STR_PK.parse("")


def test_third_party_adapter_gets_the_default_pk() -> None:
    """
    Scenario: third-party adapter gets the default pk
      Given a BaseAdapter subclass that does not set pk
      When  pk is read
      Then  DEFAULT_PK with attr 'id' and type int is returned
    """
    adapter = _ThirdPartyAdapter(object(), engine=None)

    assert adapter.pk is DEFAULT_PK
    assert adapter.pk.attr == "id"
    assert adapter.pk.python_type is int


# ---------------------------------------------------------------------------
# Codec details
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("info", "expected_kind", "expected_convertor"),
    [
        (INT_PK, "int", "int"),
        (UUID_PK, "uuid", "uuid"),
        (STR_PK, "str", "hyperadmin_pk"),
        (PrimaryKeyInfo(attr="d", python_type=datetime, generated=False), "other", "hyperadmin_pk"),
        (PrimaryKeyInfo(attr="b", python_type=bool, generated=False), "other", "hyperadmin_pk"),
    ],
)
def test_kind_and_path_convertor(
    info: PrimaryKeyInfo, expected_kind: str, expected_convertor: str
) -> None:
    assert info.kind == expected_kind
    assert info.path_convertor == expected_convertor


def test_int_parse_accepts_numeric_strings() -> None:
    assert INT_PK.parse("42") == 42
    assert INT_PK.parse(42) == 42


@pytest.mark.parametrize("raw", ["abc", "1.5", "", None])
def test_int_parse_rejects_non_numeric(raw: Any) -> None:
    with pytest.raises(InvalidPrimaryKey):
        INT_PK.parse(raw)


def test_invalid_primary_key_is_a_value_error() -> None:
    assert issubclass(InvalidPrimaryKey, ValueError)


def test_uuid_parse_returns_uuid_instance() -> None:
    value = uuid.uuid4()

    assert UUID_PK.parse(str(value).upper()) == value
    assert UUID_PK.parse(value) == value


def test_uuid_to_str_is_canonical_lowercase() -> None:
    value = uuid.UUID("12345678-1234-5678-1234-567812345678")

    assert UUID_PK.to_str(value) == "12345678-1234-5678-1234-567812345678"
    assert UUID_PK.to_str("12345678123456781234567812345678".upper()) == (
        "12345678-1234-5678-1234-567812345678"
    )


def test_uuid_to_json_is_a_string() -> None:
    value = uuid.uuid4()

    assert UUID_PK.to_json(value) == str(value)


def test_str_parse_keeps_value() -> None:
    assert STR_PK.parse("ABC-1") == "ABC-1"


def test_str_parse_accepts_ints_as_strings() -> None:
    assert STR_PK.parse(7) == "7"


def test_int_to_str() -> None:
    assert INT_PK.to_str(5) == "5"


def test_int_to_json_with_non_int_falls_back_to_string() -> None:
    assert INT_PK.to_json("5") == 5


def test_value_of_reads_mapping_pk_first() -> None:
    assert STR_PK.value_of({"_pk": "a", "code": "b"}) == "a"
    assert STR_PK.value_of({"code": "b"}) == "b"


def test_value_of_reads_attribute() -> None:
    class Row:
        code = "xyz"

    assert STR_PK.value_of(Row()) == "xyz"
    assert STR_PK.value_of(object()) is None


def test_composite_parse_is_not_supported() -> None:
    composite = PrimaryKeyInfo(
        attr="a", python_type=int, generated=False, composite=True, attrs=("a", "b")
    )

    with pytest.raises(NotImplementedError):
        composite.parse("1")


def test_attrs_default_to_single_attr() -> None:
    assert INT_PK.attrs == ("id",)


def test_primary_key_info_is_frozen() -> None:
    with pytest.raises(AttributeError):
        INT_PK.attr = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BaseAdapter.datetime_kind
# ---------------------------------------------------------------------------


class _Model(BaseModel):
    id: int
    created: datetime
    maybe_created: datetime | None = None
    aware: AwareDatetime | None = None
    name: str = ""


class _ThirdPartyAdapter(BaseAdapter):
    async def get(self, pk: Any) -> Any: ...
    async def list(self, *args: Any, **kwargs: Any) -> Any: ...
    async def create(self, data: dict[str, Any]) -> Any: ...
    async def update(self, pk: Any, data: dict[str, Any]) -> Any: ...
    async def delete(self, pk: Any) -> None: ...
    async def get_related(self, pk: Any, field: str) -> Any: ...
    async def get_schema(self) -> dict[str, Any]: ...
    async def get_choices(self, field: str, *args: Any, **kwargs: Any) -> Any: ...
    async def save_inline_rows(self, *args: Any, **kwargs: Any) -> None: ...


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("created", "naive"),
        ("maybe_created", "naive"),
        ("aware", "aware"),
        ("name", None),
        ("missing", None),
    ],
)
def test_base_adapter_datetime_kind(field: str, expected: str | None) -> None:
    adapter = _ThirdPartyAdapter(_Model, engine=None)

    assert adapter.datetime_kind(field) == expected


def test_base_adapter_datetime_kind_without_model_fields() -> None:
    adapter = _ThirdPartyAdapter(object, engine=None)

    assert adapter.datetime_kind("created") is None
