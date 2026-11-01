"""A scalar column annotated as ``str`` keeps the column's own type (#778)."""

from typing import Annotated, Any

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from hyperadmin.adapters.schema import build_sqlalchemy_schema
from hyperadmin.core.introspection import infer_search_fields

Flag = Annotated[str, mapped_column(Boolean)]


class _Base(DeclarativeBase):
    pass


class Recipe(_Base):
    __tablename__ = "misannotated_recipe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    public: Mapped[str | None] = mapped_column(Boolean, default=False)
    required_flag: Mapped[str] = mapped_column(Boolean, default=False)
    servings: Mapped[str | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[str] = mapped_column(Float, default=0.0)
    wrapped: Mapped[Flag] = mapped_column(Boolean, default=False)
    code: Mapped[str | None] = mapped_column(String(10), nullable=True)


def _annotation(field: str) -> Any:
    return build_sqlalchemy_schema(Recipe).model_fields[field].annotation


def test_boolean_column_annotated_as_optional_str_is_an_optional_bool() -> None:
    """
    Scenario: a boolean column mis-annotated as str is not searched as text
      Given Mapped[str | None] = mapped_column(Boolean)
      When  the schema is built
      Then  the field's type is bool | None
    """
    assert _annotation("public") == bool | None


def test_required_boolean_column_annotated_as_str_is_a_bool() -> None:
    """
    Scenario: a non-optional mis-annotation keeps the field required
      Given Mapped[str] = mapped_column(Boolean)
      When  the schema is built
      Then  the field's type is bool
    """
    assert _annotation("required_flag") is bool


def test_integer_and_float_columns_annotated_as_str_use_the_column_type() -> None:
    """
    Scenario: numeric columns annotated as str use the column's type
      Given Integer and Float columns annotated as str
      When  the schema is built
      Then  the fields are int | None and float
    """
    assert _annotation("servings") == int | None
    assert _annotation("rating") is float


def test_annotated_alias_over_a_boolean_column_is_a_bool() -> None:
    """
    Scenario: a mis-annotation hidden in an Annotated alias is also corrected
      Given Mapped[Flag] where Flag = Annotated[str, mapped_column(Boolean)]
      When  the schema is built
      Then  the field's type is bool
    """
    assert _annotation("wrapped") is bool


def test_string_columns_annotated_as_str_stay_text() -> None:
    """
    Scenario: a real string column is unchanged
      Given Mapped[str | None] over a String column
      When  the schema is built
      Then  the field's type is str | None
    """
    assert _annotation("code") == str | None


def test_miscast_boolean_is_not_an_inferred_search_field() -> None:
    """
    Scenario: the mis-annotated boolean drops out of inferred search
      Given the model above
      When  search fields are inferred
      Then  name and code are searchable and the boolean and numeric columns are not
    """
    fields = infer_search_fields(Recipe)
    assert "name" in fields
    assert "public" not in fields
    assert "servings" not in fields


def test_column_without_a_python_type_keeps_its_annotation() -> None:
    """
    Scenario: a column type with no Python type is left as annotated
      Given Mapped[str] over a column whose type has no python_type
      When  the annotation is resolved
      Then  str is kept
    """
    from sqlalchemy import Column
    from sqlalchemy.types import UserDefinedType

    from hyperadmin.adapters.schema import _prefer_column_scalar

    class Opaque(UserDefinedType[Any]):
        cache_ok = True

        def get_col_spec(self, **kw: Any) -> str:
            return "TEXT"

    assert _prefer_column_scalar(str, Column("c", Opaque())) is str
