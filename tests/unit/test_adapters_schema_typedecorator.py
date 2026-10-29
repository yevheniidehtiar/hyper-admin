"""A column annotated with a SQLAlchemy type class still gets a Python field type (#772)."""

import uuid
from typing import Any

from sqlalchemy import CHAR, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from hyperadmin.adapters.introspection import introspect_primary_key
from hyperadmin.adapters.schema import build_sqlalchemy_schema


class Guid(TypeDecorator[Any]):
    """Stores a UUID as 32 hex characters, like a portable GUID column type."""

    impl = CHAR(32)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        return None if value is None else f"{uuid.UUID(str(value)).int:032x}"


class _Base(DeclarativeBase):
    pass


class Widget(_Base):
    __tablename__ = "decorated_widget"

    id: Mapped[Guid] = mapped_column(Guid, primary_key=True, default=uuid.uuid4)
    owner: Mapped[Guid | None] = mapped_column(Guid, nullable=True)


def test_column_annotated_with_a_type_decorator_uses_the_column_python_type() -> None:
    """
    Scenario: a column annotated with a SQLAlchemy type uses the column's Python type
      Given a mapped column annotated Mapped[Guid] where Guid is a TypeDecorator over CHAR
      When  the schema is built
      Then  the field's annotation is str, not Guid
    """
    fields = build_sqlalchemy_schema(Widget).model_fields

    assert fields["id"].annotation is str
    assert fields["owner"].annotation == (str | None)


def test_primary_key_of_a_type_decorator_column_builds_a_type_adapter() -> None:
    pk = introspect_primary_key(Widget)

    assert pk.python_type is str
