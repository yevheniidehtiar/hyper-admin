"""JSON columns stay out of default list columns and are shortened in list cells (#767)."""

from __future__ import annotations

from enum import Enum

from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel

from hyperadmin.core.display import preview_structured
from hyperadmin.core.introspection import infer_list_display


class JsonBlobModel(SQLModel, table=True):
    """A row that carries a whole document in a JSON column."""

    __tablename__ = "json_blob_model"

    id: int | None = Field(default=None, primary_key=True)
    title: str = ""
    payload: dict | None = Field(default=None, sa_column=Column(JSON))


class Color(Enum):
    RED = "red"


def test_infer_list_display_leaves_json_columns_out() -> None:
    """
    Scenario: JSON columns are not default list columns
      Given a model with a JSON column and no explicit list_display
      When  list_display is inferred
      Then  the JSON column is not among the inferred columns
    """
    inferred = infer_list_display(JsonBlobModel)
    assert "payload" not in inferred
    assert "title" in inferred


def test_preview_structured_shortens_large_json_to_one_line() -> None:
    """
    Scenario: a large JSON value is truncated in a list cell
      Given a dict holding a long transcript
      When  preview_structured runs
      Then  the result is a single line of at most 80 characters ending in an ellipsis
    """
    out = preview_structured({"messages": ["hello " * 50] * 100})
    assert len(out) == 80
    assert out.endswith("…")
    assert "\n" not in out


def test_preview_structured_keeps_small_values_and_passes_others_through() -> None:
    assert preview_structured({"a": 1}) == '{"a": 1}'
    assert preview_structured([1, 2]) == "[1, 2]"
    assert preview_structured("text") == "text"
    assert preview_structured(None) is None
    assert preview_structured([]) == "[]"
    members = [Color.RED]
    assert preview_structured(members) is members
