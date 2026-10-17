"""Timezone-aware datetime handling in ``PydanticForm`` (st-v058-byoa-32, BYOA SDD A.6/A.7).

``PydanticForm.validate()`` parses datetime strings with the column's kind
(``adapter.datetime_kind``) and the display timezone: aware columns localise
naive input and store UTC, naive columns keep the wall-clock value. An
untouched value keeps the original datetime, and an unparsable one is a
translated field error. Datetime widgets cover ``AwareDatetime``,
``NaiveDatetime``, ``Annotated`` and PEP 604 optionals, and every "now" default
factory hides its field.
"""

from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional
from zoneinfo import ZoneInfo

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, NaiveDatetime
from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.core.timezones import annotation_datetime_kind, format_datetime_input, utc_now
from hyperadmin.views.forms import (
    CheckboxInput,
    DateTimeInput,
    FloatInput,
    InlineFormset,
    NumberInput,
    PydanticForm,
    SelectInput,
    SelectWidget,
)
from hyperadmin.views.template_filters import resolve_request_tz

AMSTERDAM = ZoneInfo("Europe/Amsterdam")


class AwareEvent(BaseModel):
    title: str = "event"
    starts_at: AwareDatetime


class NaiveEvent(BaseModel):
    title: str = "event"
    starts_at: datetime


class OptionalEvent(BaseModel):
    starts_at: datetime | None = None


class _MyDatetime(datetime):
    pass


class Colour(enum.Enum):
    RED = "red"


class Pep604Fields(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    aware_at: AwareDatetime
    naive_at: NaiveDatetime
    annotated_at: Annotated[datetime, Field(description="annotated")]
    subclass_at: _MyDatetime
    optional_at: datetime | None = None
    typing_optional_at: Optional[datetime] = None  # noqa: UP045
    count: int | None = None
    flag: bool | None = None
    ratio: float | None = None
    colour: Colour | None = None
    label: str | None = None


class Stamped(BaseModel):
    title: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    touched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _aware(_field: str) -> str:
    return "aware"


# ---------------------------------------------------------------------------
# validate(): localisation
# ---------------------------------------------------------------------------


def test_aware_column_localised() -> None:
    """
    Scenario: aware column localised
      Given tz Europe/Amsterdam
      And   an aware column
      When  '2026-07-01T10:00' is validated
      Then  the instance holds 08:00Z
    """
    # Given
    form = PydanticForm(AwareEvent, timezone=AMSTERDAM)

    # When
    instance, errors = form.validate({"title": "x", "starts_at": "2026-07-01T10:00"})

    # Then
    assert errors == {}
    assert isinstance(instance, AwareEvent)
    assert instance.starts_at == datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
    assert instance.starts_at.utcoffset() == timedelta(0)


def test_naive_column_kept() -> None:
    """
    Scenario: naive column kept
      Given a naive column
      When  '2026-07-01T10:00' is validated
      Then  the naive value is kept
    """
    # Given
    form = PydanticForm(NaiveEvent, timezone=AMSTERDAM)

    # When
    instance, errors = form.validate({"title": "x", "starts_at": "2026-07-01T10:00"})

    # Then
    assert errors == {}
    assert isinstance(instance, NaiveEvent)
    assert instance.starts_at == datetime(2026, 7, 1, 10, 0)
    assert instance.starts_at.tzinfo is None


def test_datetime_kind_resolver_overrides_the_annotation() -> None:
    """
    Scenario: the adapter's column kind wins over a plain annotation
      Given a plain ``datetime`` field whose column the resolver reports as aware
      And   tz Europe/Amsterdam
      When  '2026-07-01T10:00' is validated
      Then  the instance holds 08:00Z
    """
    form = PydanticForm(NaiveEvent, timezone=AMSTERDAM, datetime_kind=_aware)

    instance, errors = form.validate({"title": "x", "starts_at": "2026-07-01T10:00"})

    assert errors == {}
    assert isinstance(instance, NaiveEvent)
    assert instance.starts_at == datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)


def test_resolver_returning_none_falls_back_to_the_annotation() -> None:
    """
    Scenario: an unknown kind falls back to the annotation
      Given a resolver that knows no field
      And   an ``AwareDatetime`` field
      When  '2026-07-01T10:00' is validated in Europe/Amsterdam
      Then  the value is localised as aware
    """
    form = PydanticForm(AwareEvent, timezone=AMSTERDAM, datetime_kind=lambda _name: None)

    instance, _ = form.validate({"title": "x", "starts_at": "2026-07-01T10:00"})

    assert isinstance(instance, AwareEvent)
    assert instance.starts_at == datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)


def test_empty_optional_datetime_becomes_none() -> None:
    """
    Scenario: an empty optional datetime is None
      Given an optional datetime field
      When  '' is validated
      Then  the instance holds None and there is no error
    """
    form = PydanticForm(OptionalEvent, timezone=AMSTERDAM)

    instance, errors = form.validate({"starts_at": ""})

    assert errors == {}
    assert isinstance(instance, OptionalEvent)
    assert instance.starts_at is None


# ---------------------------------------------------------------------------
# validate(): unchanged value and invalid input
# ---------------------------------------------------------------------------


def test_unchanged_value_preserved() -> None:
    """
    Scenario: unchanged value preserved
      Given the submitted string equals the formatted initial value
      When  the form validates
      Then  the original datetime with microseconds is kept
    """
    # Given
    original = datetime(2026, 7, 1, 8, 0, 5, 123456, tzinfo=timezone.utc)
    form = PydanticForm(AwareEvent, timezone=AMSTERDAM, initial={"starts_at": original})
    submitted = format_datetime_input(original, AMSTERDAM)
    assert submitted == "2026-07-01T10:00:05"

    # When
    instance, errors = form.validate({"title": "x", "starts_at": submitted})

    # Then
    assert errors == {}
    assert isinstance(instance, AwareEvent)
    assert instance.starts_at == original
    assert instance.starts_at.microsecond == 123456


def test_changed_value_replaces_the_initial_value() -> None:
    """
    Scenario: an edited value is parsed, not preserved
      Given an initial datetime with microseconds
      When  a different datetime string is validated
      Then  the parsed value replaces it
    """
    original = datetime(2026, 7, 1, 10, 0, 5, 123456)
    form = PydanticForm(NaiveEvent, timezone=AMSTERDAM, initial={"starts_at": original})

    instance, _ = form.validate({"title": "x", "starts_at": "2026-07-02T11:00"})

    assert isinstance(instance, NaiveEvent)
    assert instance.starts_at == datetime(2026, 7, 2, 11, 0)


def test_invalid_datetime() -> None:
    """
    Scenario: invalid datetime
      Given 'not-a-date' submitted
      When  the form validates
      Then  a translated field error is shown
    """
    # Given
    form = PydanticForm(NaiveEvent, timezone=AMSTERDAM)

    # When
    instance, errors = form.validate({"title": "x", "starts_at": "not-a-date"})

    # Then
    assert instance is None
    assert [str(e) for e in errors["starts_at"]] == ["Enter a valid date/time"]
    field = next(f for f in form.fields if f.name == "starts_at")
    assert [str(e) for e in field.errors or []] == ["Enter a valid date/time"]


def test_input_pydantic_accepts_but_the_form_rejects_is_an_error() -> None:
    """
    Scenario: a non-ISO datetime is rejected even when pydantic would coerce it
      Given a unix-timestamp string submitted for a datetime field
      When  the form validates
      Then  no instance is returned and the field has the datetime error
    """
    form = PydanticForm(NaiveEvent, timezone=AMSTERDAM)

    instance, errors = form.validate({"title": "x", "starts_at": "1720000000"})

    assert instance is None
    assert [str(e) for e in errors["starts_at"]] == ["Enter a valid date/time"]


def test_invalid_datetime_is_reported_with_other_field_errors() -> None:
    """
    Scenario: datetime and other field errors are reported together
      Given 'not-a-date' for the datetime and a non-numeric count
      When  the form validates
      Then  both fields carry an error
    """

    class Mixed(BaseModel):
        starts_at: datetime
        count: int

    form = PydanticForm(Mixed)

    instance, errors = form.validate({"starts_at": "not-a-date", "count": "many"})

    assert instance is None
    assert set(errors) == {"starts_at", "count"}
    assert [str(e) for e in errors["starts_at"]] == ["Enter a valid date/time"]


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------


def test_aware_datetime_widget() -> None:
    """
    Scenario: AwareDatetime widget
      Given a field annotated AwareDatetime
      When  the form is built
      Then  DateTimeInput is chosen
    """
    # Given / When
    form = PydanticForm(AwareEvent)

    # Then
    widget = next(f.widget for f in form.fields if f.name == "starts_at")
    assert isinstance(widget, DateTimeInput)


@pytest.mark.parametrize(
    ("field_name", "widget_cls"),
    [
        ("aware_at", DateTimeInput),
        ("naive_at", DateTimeInput),
        ("annotated_at", DateTimeInput),
        ("subclass_at", DateTimeInput),
        ("optional_at", DateTimeInput),
        ("typing_optional_at", DateTimeInput),
        ("count", NumberInput),
        ("flag", CheckboxInput),
        ("ratio", FloatInput),
        ("colour", SelectWidget),
    ],
)
def test_widget_for_optional_and_datetime_annotations(field_name: str, widget_cls: type) -> None:
    """
    Scenario: PEP 604 optionals and datetime markers pick their typed widget
      Given a field annotated ``X | None`` or a datetime marker type
      When  the form is built
      Then  the widget for ``X`` is chosen, not a text input
    """
    form = PydanticForm(Pep604Fields)

    widget = next(f.widget for f in form.fields if f.name == field_name)

    assert type(widget) is widget_cls


@pytest.mark.parametrize(
    ("field_name", "widget_cls"),
    [
        ("aware_at", DateTimeInput),
        ("optional_at", DateTimeInput),
        ("count", NumberInput),
        ("flag", CheckboxInput),
        ("ratio", FloatInput),
        ("colour", SelectInput),
    ],
)
def test_inline_widget_for_optional_and_datetime_annotations(
    field_name: str, widget_cls: type
) -> None:
    """
    Scenario: inline rows pick the same typed widgets
      Given an inline model field annotated ``X | None`` or ``AwareDatetime``
      When  an inline row is built
      Then  the widget for ``X`` is chosen
    """
    spec = InlineModelSpec(model=Pep604Fields, fk_field="label", fields=[field_name])
    formset = InlineFormset(spec=spec)

    formset.build_empty_rows(1)

    widget = formset.rows[0].fields[0].widget
    assert type(widget) is widget_cls


@pytest.mark.parametrize(
    ("annotation", "kind"),
    [
        (AwareDatetime, "aware"),
        (NaiveDatetime, "naive"),
        (datetime, "naive"),
        (Annotated[AwareDatetime, "meta"], "aware"),
        (AwareDatetime | None, "aware"),
        (Optional[datetime], "naive"),  # noqa: UP045
        (AwareDatetime | NaiveDatetime, None),
        (str, None),
        (None, None),
    ],
)
def test_annotation_datetime_kind(annotation: Any, kind: str | None) -> None:
    """
    Scenario: an annotation declares its datetime kind
      Given a type annotation
      When  annotation_datetime_kind reads it
      Then  aware markers are 'aware', other datetimes 'naive', the rest None
    """
    assert annotation_datetime_kind(annotation) == kind


# ---------------------------------------------------------------------------
# Auto-now fields
# ---------------------------------------------------------------------------


def test_utc_now_hidden() -> None:
    """
    Scenario: utc_now hidden
      Given default_factory=utc_now
      When  the form is built
      Then  the field is excluded
    """
    # Given / When
    form = PydanticForm(Stamped)

    # Then
    names = [f.name for f in form.fields]
    assert "created_at" not in names
    assert "touched_at" not in names
    assert names == ["title"]
    assert form.auto_now_field_names == frozenset({"created_at", "touched_at"})


# ---------------------------------------------------------------------------
# Request timezone resolution
# ---------------------------------------------------------------------------


class _State:
    def __init__(self, tz: Any = None) -> None:
        self.hyperadmin_timezone = tz


class _Request:
    def __init__(self, tz: Any = None) -> None:
        self.state = _State(tz)


@pytest.mark.parametrize(
    ("request_obj", "default", "expected"),
    [
        (None, None, timezone.utc),
        (_Request(), AMSTERDAM, AMSTERDAM),
        (_Request("Asia/Tokyo"), AMSTERDAM, ZoneInfo("Asia/Tokyo")),
        (_Request("Not/AZone"), AMSTERDAM, AMSTERDAM),
        (_Request(), "Europe/Amsterdam", timezone.utc),
    ],
)
def test_resolve_request_tz(request_obj: Any, default: Any, expected: Any) -> None:
    """
    Scenario: the request's display timezone is resolved outside a template
      Given a request with or without a hyperadmin_timezone override
      When  resolve_request_tz is called with the admin default
      Then  a valid override wins, else the default tzinfo, else UTC
    """
    assert resolve_request_tz(request_obj, default) == expected


# ---------------------------------------------------------------------------
# DynamicModelView wiring
# ---------------------------------------------------------------------------


class TzMeeting(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}

    id: int | None = SQLField(default=None, primary_key=True)
    title: str = ""
    starts_at: datetime = SQLField(sa_type=DateTime(timezone=True))  # type: ignore[call-overload]
    local_at: datetime | None = None


class _Admin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture(autouse=True)
def cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


@pytest.fixture
def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database():
        async with eng.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(setup_database)
    return eng


def _seed(engine: Any, row: SQLModel) -> None:
    async def _add():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(row)
            await session.commit()

    anyio.run(_add)


def _rows(engine: Any) -> list[TzMeeting]:
    async def _fetch():
        async with AsyncSession(engine) as session:
            return list((await session.exec(select(TzMeeting))).all())

    return anyio.run(_fetch)


def _mount(engine: Any, *, options: AdminOptions | None = None) -> TestClient:
    app = FastAPI()
    settings = HyperAdminSettings(create_tables=False, timezone="Europe/Amsterdam")
    admin = Admin(app=app, engine=engine, settings=settings)
    site.register(TzMeeting, _Admin, options=options or AdminOptions())
    admin.mount(path="/admin")
    return TestClient(app)


def _as_utc(value: datetime) -> datetime:
    # SQLite drops the offset: a stored aware value comes back as naive UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def test_create_view_localises_an_aware_column(engine) -> None:
    """
    Scenario: create localises an aware column in the admin timezone
      Given the admin timezone is Europe/Amsterdam
      And   a DateTime(timezone=True) column
      When  the create form posts '2026-07-01T10:00'
      Then  the stored instant is 08:00Z
      And   a naive column keeps the wall-clock value
    """
    client = _mount(engine)

    response = client.post(
        "/admin/tzmeeting",
        data={"title": "x", "starts_at": "2026-07-01T10:00", "local_at": "2026-07-01T10:00"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    [row] = _rows(engine)
    assert _as_utc(row.starts_at) == datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
    assert row.local_at == datetime(2026, 7, 1, 10, 0)


def test_create_view_rejects_an_invalid_datetime(engine) -> None:
    """
    Scenario: create shows the datetime error
      Given the create form
      When  'not-a-date' is posted for a datetime
      Then  the response is 422 with the translated error and nothing is stored
    """
    client = _mount(engine)

    response = client.post("/admin/tzmeeting", data={"title": "x", "starts_at": "not-a-date"})

    assert response.status_code == 422
    assert "Enter a valid date/time" in response.text
    assert _rows(engine) == []


def test_create_view_honours_the_per_request_timezone(engine) -> None:
    """
    Scenario: a per-request timezone override localises input
      Given a middleware sets request.state.hyperadmin_timezone to Asia/Tokyo
      When  the create form posts '2026-07-01T10:00' for an aware column
      Then  the stored instant is 01:00Z
    """
    client = _mount(engine)

    @client.app.middleware("http")  # type: ignore[attr-defined]
    async def _tokyo(request, call_next):
        request.state.hyperadmin_timezone = "Asia/Tokyo"
        return await call_next(request)

    response = client.post(
        "/admin/tzmeeting",
        data={"title": "x", "starts_at": "2026-07-01T10:00"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    [row] = _rows(engine)
    assert _as_utc(row.starts_at) == datetime(2026, 7, 1, 1, 0, tzinfo=timezone.utc)


def test_update_view_keeps_an_unchanged_datetime(engine) -> None:
    """
    Scenario: an untouched datetime keeps its microseconds on edit
      Given a stored row whose datetimes have microseconds
      When  the edit form posts their formatted values with a new title
      Then  the title changes and both datetimes are unchanged
    """
    stored_local = datetime(2026, 7, 1, 10, 0, 5, 123456)
    stored_at = datetime(2026, 7, 1, 8, 0, 5, 654321)
    _seed(engine, TzMeeting(id=1, title="old", starts_at=stored_at, local_at=stored_local))
    client = _mount(engine)

    response = client.put(
        "/admin/tzmeeting/1",
        data={
            "title": "new",
            "starts_at": format_datetime_input(stored_at, AMSTERDAM),
            "local_at": format_datetime_input(stored_local, AMSTERDAM),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    [row] = _rows(engine)
    assert row.title == "new"
    assert row.local_at == stored_local
    assert row.starts_at.replace(tzinfo=None) == stored_at


def test_inline_save_localises_an_aware_column(engine) -> None:
    """
    Scenario: inline list editing localises an aware column
      Given starts_at is list-editable and the admin timezone is Europe/Amsterdam
      When  '2026-07-02T12:00' is saved inline
      Then  the stored instant is 10:00Z
    """
    _seed(
        engine,
        TzMeeting(id=1, title="m", starts_at=datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)),
    )
    client = _mount(engine, options=AdminOptions(list_editable=["starts_at"]))

    response = client.post(
        "/admin/tzmeeting/1/inline/starts_at", data={"starts_at": "2026-07-02T12:00"}
    )

    assert response.status_code == 200
    [row] = _rows(engine)
    assert _as_utc(row.starts_at) == datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc)
