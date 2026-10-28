"""Unit tests for the SQLAlchemy schema builder (``hyperadmin.adapters.schema``)."""

import enum
import logging
import types
import uuid
from datetime import datetime
from typing import Annotated, Any, Union, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    TypeDecorator,
    func,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    column_property,
    mapped_column,
    relationship,
)
from sqlalchemy.types import UserDefinedType
from sqlmodel import Field, SQLModel

from hyperadmin.adapters.schema import build_sqlalchemy_schema, is_sqlalchemy_mapped
from hyperadmin.core.schema import schema_for
from hyperadmin.core.timezones import is_auto_now_factory


class Base(DeclarativeBase):
    pass


class Status(enum.Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class StringEnum(TypeDecorator[Status]):
    impl = String
    cache_ok = True


class Opaque(UserDefinedType[Any]):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "OPAQUE"


class OpaqueDecorator(TypeDecorator[Any]):
    impl = Opaque
    cache_ok = True


class StringDecorator(TypeDecorator[str]):
    impl = String
    cache_ok = True


def _count_rows(ctx: Any) -> int:
    return 1


def _fixed() -> int:
    return 7


class Org(Base):
    __tablename__ = "sch_org"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    status: Mapped[Status] = mapped_column(StringEnum(String(20)), default=Status.ACTIVE)
    payload: Mapped[dict] = mapped_column(JSON)
    token: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4)
    counter: Mapped[int] = mapped_column(default=_count_rows)
    fixed: Mapped[int] = mapped_column(default=_fixed)
    flagged: Mapped[bool] = mapped_column(default=False)
    sql_default: Mapped[int] = mapped_column(default=func.abs(1))
    attr_name: Mapped[str] = mapped_column("db_name", String(10))
    opaque: Mapped[Any] = mapped_column(Opaque())
    loose = mapped_column(OpaqueDecorator())
    typed = mapped_column(StringDecorator(20))
    plain_int = mapped_column(Integer, nullable=False)
    wrong_opt: Mapped[int | None] = mapped_column(Integer, nullable=False)
    _private: Mapped[int | None] = mapped_column(Integer)
    members: Mapped[list["Member"]] = relationship(back_populates="org")
    member_count = column_property(select(func.count()).scalar_subquery())


class Member(Base):
    __tablename__ = "sch_member"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("sch_org.id"))
    org: Mapped[Org] = relationship(back_populates="members")
    full_name: Mapped[str] = mapped_column(String(30))
    both: Mapped[str | None] = mapped_column(String(5), nullable=False)
    tagged: Mapped[Annotated[str, "tag"]] = mapped_column(String(5))
    union: Mapped[int | str] = mapped_column(Integer)


class Account(Base):
    __tablename__ = "sch_account"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    email: Mapped[str] = mapped_column(String(50))
    __mapper_args__ = {"polymorphic_on": "kind", "polymorphic_identity": "account"}


class Staff(Account):
    badge: Mapped[str | None] = mapped_column(String(10))
    __mapper_args__ = {"polymorphic_identity": "staff"}


class Employee(Base):
    __tablename__ = "sch_employee"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20))
    type: Mapped[str] = mapped_column(String(10))
    __mapper_args__ = {"polymorphic_on": "type", "polymorphic_identity": "employee"}


class Manager(Employee):
    __tablename__ = "sch_manager"
    id: Mapped[int] = mapped_column(ForeignKey("sch_employee.id"), primary_key=True)
    level: Mapped[int] = mapped_column()
    __mapper_args__ = {"polymorphic_identity": "manager"}


class NaturalKey(Base):
    __tablename__ = "sch_natural"
    code: Mapped[str] = mapped_column(String(5), primary_key=True)
    seq: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)


@pytest.fixture(scope="module")
def org_schema() -> type[BaseModel]:
    return build_sqlalchemy_schema(Org)


def _ann(schema: type[BaseModel], name: str) -> Any:
    return schema.model_fields[name].annotation


def test_predicate_matches_mapped_class() -> None:
    """
    Scenario: predicate matches a mapped SQLAlchemy class
      Given a DeclarativeBase model
      When  is_sqlalchemy_mapped is called with it
      Then  the result is True
    """
    assert is_sqlalchemy_mapped(Org) is True


def test_predicate_rejects_pydantic_and_sqlmodel_and_non_classes() -> None:
    """
    Scenario: predicate rejects Pydantic, SQLModel, unmapped classes and instances
      Given a Pydantic model, a SQLModel model, a plain class and an instance
      When  is_sqlalchemy_mapped is called
      Then  every result is False
    """

    class Plain(BaseModel):
        x: int

    class Hero(SQLModel, table=True):
        __tablename__ = "sch_hero"
        id: int | None = Field(default=None, primary_key=True)

    assert not is_sqlalchemy_mapped(Plain)
    assert not is_sqlalchemy_mapped(Hero)
    assert not is_sqlalchemy_mapped(int)
    assert not is_sqlalchemy_mapped(Org())


def test_schema_for_dispatches_to_builder() -> None:
    """
    Scenario: schema_for resolves a mapped class through the registry
      Given the adapters package registered the builder
      When  schema_for(Org) is called twice
      Then  the same generated class is returned
    """
    assert schema_for(Org) is schema_for(Org)
    assert schema_for(Org).__name__ == "OrgSchema"


def test_schema_name_and_config(org_schema: type[BaseModel]) -> None:
    """
    Scenario: generated class is named and configured per the spec
      Given the Org model
      When  the schema is built
      Then  it is named OrgSchema with from_attributes and arbitrary types enabled
    """
    assert org_schema.__name__ == "OrgSchema"
    assert org_schema.model_config["from_attributes"] is True
    assert org_schema.model_config["arbitrary_types_allowed"] is True


def test_field_order_follows_mapper(org_schema: type[BaseModel]) -> None:
    """
    Scenario: fields follow mapper order and use attribute keys
      Given Org declares id, name, note first and attr_name over column "db_name"
      When  the schema is built
      Then  fields start id, name, note and the field is attr_name, not db_name
    """
    names = list(org_schema.model_fields)
    assert names[:3] == ["id", "name", "note"]
    assert "attr_name" in names
    assert "db_name" not in names


def test_mapped_annotation_beats_column_type(org_schema: type[BaseModel]) -> None:
    """
    Scenario: Mapped annotations win over column python types
      Given status: Mapped[Status] over a TypeDecorator(String)
      When  the schema is built
      Then  the annotation is Status
    """
    assert _ann(org_schema, "status") is Status


def test_column_python_type_used_without_annotation(org_schema: type[BaseModel]) -> None:
    """
    Scenario: column python_type is the fallback annotation
      Given plain_int = mapped_column(Integer, nullable=False) with no Mapped[...]
      When  the schema is built
      Then  the annotation is int
    """
    assert _ann(org_schema, "plain_int") is int


def test_type_decorator_resolves_through_impl(org_schema: type[BaseModel]) -> None:
    """
    Scenario: a TypeDecorator without its own python_type resolves through impl
      Given a TypeDecorator over String and no Mapped[...] annotation
      When  the schema is built
      Then  the annotation is str
    """
    assert get_args(_ann(org_schema, "typed")) == (str, type(None))


def test_unresolvable_type_degrades_to_any(
    org_schema: type[BaseModel], caplog: pytest.LogCaptureFixture
) -> None:
    """
    Scenario: columns with no resolvable Python type degrade to Any
      Given a TypeDecorator over a type whose python_type raises NotImplementedError
      When  the schema is built
      Then  the annotation is Any (optional, being nullable), nothing raises and a debug log names it
    """
    caplog.set_level(logging.DEBUG, logger="hyperadmin.adapters.schema")
    schema = build_sqlalchemy_schema(Org)
    assert get_args(_ann(schema, "loose")) == (Any, type(None))
    assert any("Org.loose" in r.getMessage() for r in caplog.records)


def test_json_column_annotation(org_schema: type[BaseModel]) -> None:
    """
    Scenario: JSON columns accept dicts and lists
      Given a JSON column with Mapped[dict]
      When  the schema is built and a list is validated
      Then  validation accepts it only through the python_type path (dict | list | Any)
    """
    schema = build_sqlalchemy_schema(Member)
    assert schema is not None

    class Doc(Base):
        __tablename__ = "sch_doc"
        id = mapped_column(Integer, primary_key=True)
        data = mapped_column(JSON, nullable=False)

    doc_schema = build_sqlalchemy_schema(Doc)
    assert doc_schema.model_validate({"data": [1, 2]}).data == [1, 2]  # type: ignore[attr-defined]


def test_nullable_wraps_optional(org_schema: type[BaseModel]) -> None:
    """
    Scenario: nullable columns become optional
      Given note is nullable (Mapped[str | None]) and name is NOT NULL
      When  the schema is built
      Then  note is optional with default None and name is required
    """
    note = org_schema.model_fields["note"]
    assert note.default is None
    assert not note.is_required()
    assert org_schema.model_fields["name"].is_required()


def test_nullable_decides_optionality_over_annotation(org_schema: type[BaseModel]) -> None:
    """
    Scenario: column.nullable beats the Optional in the annotation
      Given Mapped[int | None] with nullable=False and Mapped[Optional[str]] with nullable=False
      When  the schema is built
      Then  both are required and their annotations are unwrapped
    """
    assert org_schema.model_fields["wrong_opt"].is_required()
    assert _ann(org_schema, "wrong_opt") is int
    member = build_sqlalchemy_schema(Member)
    assert member.model_fields["both"].is_required()
    assert _ann(member, "both") is str


def test_annotated_mapped_type_is_unwrapped() -> None:
    """
    Scenario: Annotated metadata inside Mapped[...] is stripped
      Given Mapped[Annotated[str, "tag"]] over a NOT NULL column
      When  the schema is built
      Then  the annotation is str
    """
    assert _ann(build_sqlalchemy_schema(Member), "tagged") is str


def test_union_annotation_preserved() -> None:
    """
    Scenario: a multi-member union survives unwrapping
      Given Mapped[int | str] over a NOT NULL column
      When  the schema is built
      Then  the annotation is the union of int and str
    """
    ann = _ann(build_sqlalchemy_schema(Member), "union")
    assert set(get_args(ann)) == {int, str}
    assert get_origin(ann) in (Union, types.UnionType)


def test_scalar_default(org_schema: type[BaseModel]) -> None:
    """
    Scenario: a scalar column default becomes the field default
      Given flagged has default=False
      When  the schema is built
      Then  the field default is False and it is not required
    """
    field = org_schema.model_fields["flagged"]
    assert field.default is False
    assert not field.is_required()


def test_callable_default_becomes_factory(org_schema: type[BaseModel]) -> None:
    """
    Scenario: a context-free callable default becomes default_factory
      Given created_at default=datetime.now, token default=uuid4 and fixed default=_fixed
      When  the schema is built
      Then  each field has a default_factory and datetime.now is an auto-now factory
    """
    created = org_schema.model_fields["created_at"]
    assert is_auto_now_factory(created.default_factory)
    assert org_schema.model_fields["token"].default_factory is uuid.uuid4
    assert org_schema.model_fields["fixed"].default_factory is _fixed
    required = {n: f for n, f in org_schema.model_fields.items() if f.is_required()}
    assert set(required) == {"name", "payload", "attr_name", "opaque", "plain_int", "wrong_opt"}


def test_context_callable_default_is_optional_none(org_schema: type[BaseModel]) -> None:
    """
    Scenario: a callable needing the SQLAlchemy context defaults to None
      Given counter has default=_count_rows(ctx)
      When  the schema is built
      Then  the field has no factory, default None and an optional annotation
    """
    field = org_schema.model_fields["counter"]
    assert field.default_factory is None
    assert field.default is None
    assert get_args(field.annotation) == (int, type(None))


def test_sql_expression_default_is_optional_none(org_schema: type[BaseModel]) -> None:
    """
    Scenario: a SQL-expression default is filled by the database
      Given sql_default has default=func.abs(1)
      When  the schema is built
      Then  the field default is None
    """
    assert org_schema.model_fields["sql_default"].default is None


def test_server_default_and_autoincrement_pk(org_schema: type[BaseModel]) -> None:
    """
    Scenario: server_default and autoincrement integer PKs default to None
      Given updated_at has a server_default and id is an integer PK
      When  the schema is built
      Then  both fields default to None and are not required
    """
    assert org_schema.model_fields["updated_at"].default is None
    assert org_schema.model_fields["id"].default is None
    assert not org_schema.model_fields["id"].is_required()


def test_non_autoincrement_composite_pk_columns_are_required() -> None:
    """
    Scenario: natural and non-autoincrement primary keys stay required
      Given a model with a String PK and an Integer PK with autoincrement=False
      When  the schema is built
      Then  both fields are required
    """
    schema = build_sqlalchemy_schema(NaturalKey)
    assert schema.model_fields["code"].is_required()
    assert schema.model_fields["seq"].is_required()


def test_auto_now_hint_in_json_schema_extra(org_schema: type[BaseModel]) -> None:
    """
    Scenario: server_default / onupdate leave an sa_column_kwargs hint
      Given updated_at has server_default and onupdate; name has neither
      When  the schema is built
      Then  updated_at carries both keys in json_schema_extra and name carries none
    """
    extra = org_schema.model_fields["updated_at"].json_schema_extra
    assert isinstance(extra, dict)
    assert set(extra["sa_column_kwargs"]) == {"server_default", "onupdate"}  # type: ignore[call-overload]
    assert org_schema.model_fields["name"].json_schema_extra is None


def test_string_length_becomes_max_length(org_schema: type[BaseModel]) -> None:
    """
    Scenario: String(n) becomes max_length
      Given name is String(50)
      When  the schema is built and a 51-character name is validated
      Then  validation fails on name; an Enum-backed String adds no max_length
    """
    with pytest.raises(ValidationError):
        org_schema.model_validate({"name": "x" * 51, "attr_name": "y"})
    assert not any(
        getattr(m, "max_length", None) for m in org_schema.model_fields["status"].metadata
    )


def test_relationships_hybrids_and_expressions_excluded(org_schema: type[BaseModel]) -> None:
    """
    Scenario: relationships, expression column_property and private attrs are absent
      Given Org has a members relationship, a scalar-subquery column_property and _private
      When  the schema is built
      Then  none of them is a field
    """
    assert "members" not in org_schema.model_fields
    assert "member_count" not in org_schema.model_fields
    assert "_private" not in org_schema.model_fields
    assert "org" not in build_sqlalchemy_schema(Member).model_fields


def test_single_table_inheritance_hides_discriminator() -> None:
    """
    Scenario: STI subclass schema has parent and child columns but not the discriminator
      Given Staff extends Account with polymorphic_on "kind"
      When  the schema is built per class
      Then  Staff has id, email, badge and no kind; so does Account (identity set)
    """
    staff = build_sqlalchemy_schema(Staff)
    assert list(staff.model_fields) == ["id", "email", "badge"]
    assert "kind" not in build_sqlalchemy_schema(Account).model_fields


def test_joined_table_inheritance_shared_pk_not_editable() -> None:
    """
    Scenario: JTI subclass schema merges both tables and its shared pk is not required
      Given Manager joins Employee on id
      When  the schema is built
      Then  fields include name, level and id; id is not required; the discriminator is hidden
    """
    schema = build_sqlalchemy_schema(Manager)
    assert {"id", "name", "level"} <= set(schema.model_fields)
    assert "type" not in schema.model_fields
    assert schema.model_fields["id"].default is None


def test_unresolvable_forward_ref_falls_back() -> None:
    """
    Scenario: an unresolvable annotation never raises
      Given a model whose hints cannot all be resolved via get_type_hints
      When  the schema is built
      Then  resolvable annotations are kept and the unresolvable one is ignored
    """

    class Broken(Base):
        __tablename__ = "sch_broken"
        __allow_unmapped__ = True
        id: Mapped[int] = mapped_column(primary_key=True)
        title: Mapped[str] = mapped_column(String(5))
        ghost: "Missing"  # type: ignore[name-defined]  # noqa: F821

    schema = build_sqlalchemy_schema(Broken)
    assert _ann(schema, "title") is str
    assert "ghost" not in schema.model_fields


def test_legacy_declarative_base_model() -> None:
    """
    Scenario: legacy declarative_base() models are mapped and supported
      Given a model built from sqlalchemy.orm.declarative_base()
      When  the predicate and builder run
      Then  the predicate is True and fields come from column types
    """
    from sqlalchemy.orm import declarative_base

    legacy = declarative_base()

    class Old(legacy):  # type: ignore[misc,valid-type]
        __tablename__ = "sch_old"
        id = mapped_column(Integer, primary_key=True)
        label = mapped_column(String(8), nullable=False)

    assert is_sqlalchemy_mapped(Old)
    schema = build_sqlalchemy_schema(Old)
    assert list(schema.model_fields) == ["id", "label"]
    assert schema.model_fields["label"].is_required()


def test_schema_reads_orm_instance_attributes(org_schema: type[BaseModel]) -> None:
    """
    Scenario: the schema validates ORM instances via from_attributes
      Given an Org instance with name and attr_name set
      When  model_validate is called with from_attributes
      Then  the values round-trip
    """
    org = Org(
        name="Acme",
        attr_name="a",
        payload={},
        status=Status.CLOSED,
        updated_at=datetime(2026, 1, 1),
        created_at=datetime(2026, 1, 1),
        token=uuid.uuid4(),
        counter=1,
        fixed=1,
        flagged=True,
        sql_default=1,
        opaque=1,
        plain_int=1,
        wrong_opt=1,
    )
    assert org_schema.model_validate(org, from_attributes=True).name == "Acme"  # type: ignore[attr-defined]
