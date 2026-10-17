"""Unit tests for st-v058-byoa-27: translate pydantic validation messages by error type (#531).

BDD scenarios from
.meta/epics/epic-v058-bring-your-own-app/stories/feati18n-translate-pydantic-validation-messages-by-error-typ.md
(spec: docs/specs/bring-your-own-app.md, section D.4):

Scenario: validation message is translated
  Given locale 'uk'
  And   a field constrained gt=5
  When  3 is submitted
  Then  the field error shows the Ukrainian 'greater than 5' message

Scenario: unknown type falls back
  Given an unmapped error type
  When  translate_error runs
  Then  the original msg is returned
"""

from __future__ import annotations

import datetime
import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any, Literal

import anyio
import babel.support
import pytest
from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import (
    AnyUrl,
    BaseModel,
    BeforeValidator,
    Field,
    Json,
    TypeAdapter,
    ValidationError,
    field_validator,
)
from pydantic_core import PydanticCustomError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.actions import action
from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.i18n import loader, translate_error
from hyperadmin.i18n import validation_messages as vm
from hyperadmin.i18n.loader import _clear_caches, set_current_translations
from hyperadmin.views.forms import InlineFormset, PydanticForm

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

UK_GREATER_THAN_5 = "Значення має бути більшим за 5"


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_i18n_state() -> Iterator[None]:
    """Start every test with no active catalog and empty loader caches."""
    _clear_caches()
    token = set_current_translations(babel.support.NullTranslations())
    try:
        yield
    finally:
        loader.reset_current_translations(token)
        _clear_caches()


@pytest.fixture
def uk_locale() -> Iterator[None]:
    """Activate the shipped, compiled Ukrainian catalog."""
    token = set_current_translations(loader.load_translations("uk"))
    try:
        yield
    finally:
        loader.reset_current_translations(token)


def _activate_catalog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, msgs: dict[Any, Any]
) -> None:
    """Write a throwaway ``es`` catalog with *msgs* and make it the active one."""
    catalog = Catalog(locale="es", charset="utf-8")
    for msgid, msgstr in msgs.items():
        catalog.add(msgid, string=msgstr)
    target = tmp_path / "es" / "LC_MESSAGES" / "messages.mo"
    target.parent.mkdir(parents=True)
    with target.open("wb") as fh:
        write_mo(fh, catalog)
    monkeypatch.setattr(loader, "LOCALE_DIR", tmp_path)
    _clear_caches()
    set_current_translations(loader.load_translations("es"))


def _first_error(tp: Any, value: Any) -> dict[str, Any]:
    try:
        TypeAdapter(tp).validate_python(value)
    except ValidationError as exc:
        return dict(exc.errors()[0])
    pytest.fail("expected a validation error")


class _Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


class _GtFive(BaseModel):
    count: int = Field(gt=5)


class _MustBeGood(BaseModel):
    value: int = 0

    @field_validator("value")
    @classmethod
    def _check(cls, v: int) -> int:
        if v < 0:
            raise ValueError("value is bad")
        if v == 0:
            raise ValueError
        return v


# ---------------------------------------------------------------------------
# Scenario: validation message is translated
# ---------------------------------------------------------------------------


class TestValidationMessageIsTranslated:
    def test_form_field_error_shows_ukrainian_greater_than_message(self, uk_locale: None) -> None:
        """
        Scenario: validation message is translated
          Given locale 'uk'
          And   a field constrained gt=5
          When  3 is submitted
          Then  the field error shows the Ukrainian 'greater than 5' message
        """
        # Given locale 'uk' (fixture) and a form with a gt=5 field
        form = PydanticForm(_GtFive)

        # When 3 is submitted
        _instance, errs = form.validate({"count": "3"})

        # Then the field error shows the Ukrainian message
        assert [str(e) for e in errs["count"]] == [UK_GREATER_THAN_5]
        field = next(f for f in form.fields if f.name == "count")
        assert field.errors is not None
        assert str(field.errors[0]) == UK_GREATER_THAN_5

    def test_form_error_is_lazy_and_follows_the_active_locale(self) -> None:
        """
        Scenario: form errors are re-translated at render time
          Given a form error captured with no catalog active
          When  the 'uk' catalog is activated afterwards
          Then  the same error renders in Ukrainian
        """
        # Given an error captured in English
        _instance, errs = PydanticForm(_GtFive).validate({"count": "3"})
        error = errs["count"][0]
        assert isinstance(error, babel.support.LazyProxy)
        assert str(error) == "Input should be greater than 5"

        # When the uk catalog becomes active
        token = set_current_translations(loader.load_translations("uk"))
        try:
            # Then the error renders in Ukrainian
            assert str(error) == UK_GREATER_THAN_5
        finally:
            loader.reset_current_translations(token)

    def test_inline_row_error_shows_ukrainian_message(self, uk_locale: None) -> None:
        """
        Scenario: inline row validation message is translated
          Given locale 'uk'
          And   an inline model whose field is constrained gt=5
          When  a row with 3 is submitted
          Then  the row's field error shows the Ukrainian 'greater than 5' message
        """
        # Given an inline formset over a gt=5 model
        formset = InlineFormset(spec=InlineModelSpec(model=_GtFive, fk_field="parent_id"))

        # When a row with 3 is validated
        _valid, errors = formset.validate_rows([{"count": "3"}])

        # Then the row error is Ukrainian
        assert [str(e) for e in errors[0]["count"]] == [UK_GREATER_THAN_5]

    def test_bulk_action_form_error_shows_ukrainian_message(self) -> None:
        """
        Scenario: bulk action form validation message is translated
          Given the admin UI in locale 'uk'
          And   a bulk action whose form field is constrained gt=5
          When  3 is submitted to the confirm endpoint
          Then  the re-rendered form shows the Ukrainian 'greater than 5' message
        """
        # Given an admin with a bulk action whose form requires count > 5
        client = _bulk_client()
        client.cookies.set("hyperadmin_locale", "uk")

        # When 3 is submitted to the confirm endpoint
        response = client.post(
            "/admin/i18nbulkwidget/actions/recount/bulk/confirm",
            data={"ids": ["1"], "count": "3"},
        )

        # Then the form re-renders with the Ukrainian message
        assert response.status_code == 200
        assert UK_GREATER_THAN_5 in response.text
        assert "Input should be greater than 5" not in response.text

    @pytest.mark.parametrize(
        ("length", "expected"),
        [
            (1, "Рядок має містити щонайменше 1 символ"),
            (3, "Рядок має містити щонайменше 3 символи"),
            (5, "Рядок має містити щонайменше 5 символів"),
        ],
    )
    def test_ukrainian_plural_forms_follow_the_constraint(
        self, uk_locale: None, length: int, expected: str
    ) -> None:
        """
        Scenario: length messages use the locale's plural forms
          Given locale 'uk'
          And   a string field constrained min_length=<length>
          When  an empty string is submitted
          Then  the message uses the matching Ukrainian plural form
        """
        err = _first_error(Annotated[str, Field(min_length=length)], "")

        assert translate_error(err) == expected

    def test_value_error_message_is_passed_through_gettext(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """
        Scenario: a custom validator's message is translated
          Given a catalog translating the prefix and the validator's message
          When  the validator raises ValueError("value is bad")
          Then  both the prefix and the message are translated
        """
        _activate_catalog(
            monkeypatch,
            tmp_path,
            {"Value error, %(error)s": "Error de valor, %(error)s", "value is bad": "valor malo"},
        )
        try:
            _MustBeGood(value=-1)
        except ValidationError as exc:
            err = exc.errors()[0]

        assert translate_error(err) == "Error de valor, valor malo"

    def test_empty_value_error_does_not_leak_the_catalog_header(self, uk_locale: None) -> None:
        """
        Scenario: an empty validator message stays empty
          Given locale 'uk'
          When  a validator raises ValueError() with no message
          Then  the translated prefix is followed by nothing (not the catalog header)
        """
        try:
            _MustBeGood(value=0)
        except ValidationError as exc:
            err = exc.errors()[0]

        assert translate_error(err) == "Помилка значення, "

    def test_collection_field_type_is_translated(self, uk_locale: None) -> None:
        """
        Scenario: collection length messages translate the collection name
          Given locale 'uk'
          When  an empty list violates min_length=2
          Then  the message names the collection in Ukrainian
        """
        err = _first_error(Annotated[list[int], Field(min_length=2)], [])

        expected = "Список має містити щонайменше 2 елементи після валідації, а не 0"  # noqa: RUF001
        assert translate_error(err) == expected

    @pytest.mark.parametrize(
        ("tp", "value", "expected"),
        [
            (Literal["a", "b"], "z", "Значення має бути одним із: 'a' або 'b'"),  # noqa: RUF001
            (Literal["a", "b", "c"], "z", "Значення має бути одним із: 'a', 'b' або 'c'"),  # noqa: RUF001
            (_Color, "green", "Значення має бути одним із: 'red' або 'blue'"),  # noqa: RUF001
            (Literal["a"], "z", "Значення має бути одним із: 'a'"),
        ],
        ids=["two-literals", "three-literals", "enum", "single-literal"],
    )
    def test_choice_list_conjunction_is_translated(
        self, uk_locale: None, tp: Any, value: Any, expected: str
    ) -> None:
        """
        Scenario: the "or" joining enum / literal choices is translated
          Given locale 'uk'
          And   a field restricted to a set of choices
          When  a value outside the choices is submitted
          Then  the choices are joined with the Ukrainian "або", not "or"
        """
        err = _first_error(tp, value)

        assert translate_error(err) == expected

    def test_choice_containing_or_is_not_split(self, uk_locale: None) -> None:
        """
        Scenario: a choice that itself contains " or " stays intact
          Given locale 'uk'
          And   a Literal['a', 'x or y'] field
          When  'z' is submitted
          Then  only the separator between the choices is translated
        """
        err = _first_error(Literal["a", "x or y"], "z")

        assert translate_error(err) == "Значення має бути одним із: 'a' або 'x or y'"  # noqa: RUF001

    def test_unbalanced_choice_list_is_left_unchanged(self, uk_locale: None) -> None:
        """
        Scenario: an expected list with no splittable separator is kept as is
          Given locale 'uk'
          And   an enum error whose only " or " precedes an unclosed quote
          When  translate_error runs
          Then  the expected list is interpolated unchanged
        """
        err = {"type": "enum", "msg": "Input should be x or 'y", "ctx": {"expected": "x or 'y"}}

        assert translate_error(err) == "Значення має бути одним із: x or 'y"

    @pytest.mark.parametrize(
        ("tp", "value", "expected"),
        [
            (
                datetime.date,
                "x",
                "Значення має бути коректною датою або датою з часом, значення закоротке",  # noqa: RUF001
            ),
            (
                datetime.date,
                "2020-1x-01",
                "Значення має бути коректною датою або датою з часом, некоректний символ у місяці",  # noqa: RUF001
            ),
            (
                AnyUrl,
                "/relative",
                "Значення має бути коректною URL-адресою, відносна URL-адреса без бази",
            ),
        ],
        ids=["date-too-short", "date-bad-month", "relative-url"],
    )
    def test_parser_error_detail_is_translated(
        self, uk_locale: None, tp: Any, value: Any, expected: str
    ) -> None:
        """
        Scenario: the parser's error detail is translated too
          Given locale 'uk'
          And   a date or URL field
          When  a malformed value is submitted
          Then  both the message and pydantic-core's error detail are Ukrainian
        """
        err = _first_error(tp, value)

        assert translate_error(err) == expected

    def test_every_mapped_msgid_has_a_reviewed_ukrainian_translation(self) -> None:
        """
        Scenario: the Ukrainian catalog covers every mapped msgid
          Given the shipped uk messages.po
          When  each msgid of the error-type table is looked up
          Then  it exists, is not fuzzy and has a translation
        """
        po_path = loader.LOCALE_DIR / "uk" / "LC_MESSAGES" / "messages.po"
        with po_path.open("rb") as fh:
            catalog = read_po(fh)

        msgids: list[str] = [*vm._MESSAGES.values(), *vm._FIELD_TYPES, *vm._CTX_ERRORS]
        msgids.append(vm._CHOICES_JOIN)
        msgids += [pair[0] for pair, _key in vm._PLURAL_MESSAGES.values()]
        msgids.append(vm._TOO_LONG_UNKNOWN_LENGTH[0])
        for msgid in msgids:
            message = catalog.get(msgid)
            assert message is not None, msgid
            assert not message.fuzzy, msgid
            strings = message.string if isinstance(message.string, tuple) else (message.string,)
            assert all(strings), msgid


# ---------------------------------------------------------------------------
# Scenario: unknown type falls back
# ---------------------------------------------------------------------------


class TestUnknownTypeFallsBack:
    def test_unmapped_type_returns_original_msg(self) -> None:
        """
        Scenario: unknown type falls back
          Given an unmapped error type
          When  translate_error runs
          Then  the original msg is returned
        """
        # Given an unmapped error type
        err = _custom_error("totally_custom", "Custom {thing} failed", {"thing": "widget"})

        # When translate_error runs
        result = translate_error(err)

        # Then the original msg is returned
        assert result == "Custom widget failed"

    def test_unmapped_type_msg_is_still_passed_through_gettext(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """
        Scenario: unknown type falls back to gettext(msg)
          Given an unmapped error type
          And   a catalog translating its literal message
          When  translate_error runs
          Then  the catalog's translation is returned
        """
        _activate_catalog(monkeypatch, tmp_path, {"Custom widget failed": "Widget falló"})
        err = _custom_error("totally_custom", "Custom widget failed", None)

        assert translate_error(err) == "Widget falló"

    def test_ctx_not_matching_the_template_falls_back_to_msg(self) -> None:
        """
        Scenario: a mapped type with unexpected ctx falls back
          Given a 'greater_than' error whose ctx lacks the 'gt' key
          When  translate_error runs
          Then  the original msg is returned
        """
        err = {"type": "greater_than", "msg": "Input should be greater than 5", "ctx": {}}

        assert translate_error(err) == "Input should be greater than 5"

    def test_translation_with_a_bad_placeholder_falls_back_to_msg(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """
        Scenario: a broken translation does not crash validation
          Given a catalog whose translation contains a stray '%'
          When  translate_error runs for that error type
          Then  the original msg is returned
        """
        _activate_catalog(
            monkeypatch,
            tmp_path,
            {"Input should be greater than %(gt)s": "mayor que %(gt)s al 100%"},
        )
        err = _first_error(_GtFive, {"count": 3})

        assert translate_error(err) == "Input should be greater than 5"


def _custom_error(err_type: str, template: str, ctx: dict[str, Any] | None) -> dict[str, Any]:
    def _raise(_v: Any) -> Any:
        raise PydanticCustomError(err_type, template, ctx)

    return _first_error(Annotated[int, BeforeValidator(_raise)], 1)


# ---------------------------------------------------------------------------
# English output is unchanged
# ---------------------------------------------------------------------------


class _Everything(BaseModel):
    pattern: Annotated[str, Field(pattern="^a+$")] = "a"
    gt: Annotated[int, Field(gt=5)] = 6
    ge: Annotated[float, Field(ge=5)] = 5
    lt: Annotated[Decimal, Field(lt=Decimal("1.5"))] = Decimal(1)
    le: Annotated[float, Field(le=2.5)] = 1
    mult: Annotated[int, Field(multiple_of=3)] = 3
    long: Annotated[str, Field(max_length=1)] = ""
    long2: Annotated[str, Field(max_length=2)] = ""
    items: Annotated[list[int], Field(max_length=1)] = []
    tset: Annotated[set[int], Field(min_length=1)] = {1}
    color: _Color = _Color.RED
    lit: Literal["x", "y"] = "x"
    i: int = 0
    f: float = 0
    b: bool = False
    dec: Decimal = Decimal(0)
    d: datetime.date = datetime.date(2020, 1, 1)
    dt: datetime.datetime = datetime.datetime(2020, 1, 1)
    t: datetime.time = datetime.time()
    u: uuid.UUID = uuid.UUID(int=0)
    j: Json[int] = 1
    s: str = ""


_BAD_INPUTS: dict[str, Any] = {
    "pattern": "b",
    "gt": 3,
    "ge": 1,
    "lt": Decimal(2),
    "le": 3,
    "mult": 4,
    "long": "ab",
    "long2": "abc",
    "items": [1, 2],
    "tset": set(),
    "color": "green",
    "lit": "z",
    "i": "x",
    "f": "x",
    "b": "maybe",
    "dec": "x",
    "d": "x",
    "dt": "x",
    "t": "x",
    "u": "x",
    "j": "{",
    "s": 1,
}


def _english_cases() -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    try:
        _Everything(**_BAD_INPUTS)
    except ValidationError as exc:
        errors += [dict(e) for e in exc.errors()]
    for tp, value in [
        (_GtFive, {}),
        (int, None),
        (int, 1.5),
        (float, None),
        (bool, None),
        (Annotated[str, Field(min_length=1)], ""),
        (Annotated[str, Field(min_length=3)], ""),
        (Annotated[list[int], Field(min_length=1)], []),
        (Annotated[tuple[int, ...], Field(min_length=2)], (1,)),
        (Annotated[dict[str, int], Field(min_length=1)], {}),
        (Annotated[frozenset[int], Field(min_length=1)], frozenset()),
        (Annotated[set[int], Field(max_length=1)], {1, 2}),
        (Annotated[list[int], Field(max_length=1)], iter([1, 2, 3])),
    ]:
        errors.append(_first_error(tp, value))
    try:
        _MustBeGood(value=-1)
    except ValidationError as exc:
        errors.append(dict(exc.errors()[0]))
    return errors


def _url_and_assertion_errors() -> list[dict[str, Any]]:
    from pydantic import AnyUrl, model_validator

    class _Checked(BaseModel):
        x: int = 0

        @model_validator(mode="after")
        def _c(self) -> _Checked:
            assert self.x, "x must be set"
            return self

    errors = [_first_error(AnyUrl, "nope")]
    try:
        _Checked()
    except ValidationError as exc:
        errors.append(dict(exc.errors()[0]))
    return errors


_ALL_CASES = _english_cases() + _url_and_assertion_errors()


@pytest.mark.parametrize("err", _ALL_CASES, ids=[str(e["type"]) for e in _ALL_CASES])
def test_english_output_matches_pydantic_message(err: dict[str, Any]) -> None:
    """
    Scenario: with no catalog active, messages are unchanged
      Given no translation catalog is active
      When  translate_error runs on a real pydantic error
      Then  the result equals pydantic's own English msg
    """
    assert translate_error(err) == err["msg"]


def test_english_cases_cover_the_mapped_error_types() -> None:
    """
    Scenario: the English regression cases exercise the error-type table
      Given the real pydantic errors used above
      When  their types are collected
      Then  every mapped type except date_parsing/datetime_parsing is covered
    """
    covered = {e["type"] for e in _ALL_CASES}
    mapped = set(vm._MESSAGES) | set(vm._PLURAL_MESSAGES)

    # date_parsing/datetime_parsing are not raised for these inputs by the
    # supported pydantic versions (they raise the *_from_*_parsing variants).
    assert mapped - covered == {"date_parsing", "datetime_parsing"}


@pytest.mark.parametrize(
    ("err_type", "msg"),
    [
        (
            "date_parsing",
            "Input should be a valid date in the format YYYY-MM-DD, input is too short",
        ),
        ("datetime_parsing", "Input should be a valid datetime, input is too short"),
    ],
)
def test_parsing_errors_without_a_real_trigger_render_pydantic_wording(
    err_type: str, msg: str
) -> None:
    """
    Scenario: the bare date/datetime parsing types keep pydantic's wording
      Given a date_parsing or datetime_parsing error with an 'error' ctx
      When  translate_error runs with no catalog active
      Then  the result equals pydantic's English message
    """
    err = {"type": err_type, "msg": msg, "ctx": {"error": "input is too short"}}

    assert translate_error(err) == msg


def test_whole_float_bounds_render_without_fraction() -> None:
    """
    Scenario: whole float bounds render like pydantic
      Given a float field constrained ge=5.0
      When  1 is submitted
      Then  the message says '5', not '5.0'
    """
    err = _first_error(Annotated[float, Field(ge=5.0)], 1)

    assert translate_error(err) == "Input should be greater than or equal to 5"


# ---------------------------------------------------------------------------
# Bulk action app
# ---------------------------------------------------------------------------


class I18nBulkWidget(SQLModel, table=True):
    __tablename__ = "test_i18n_bulk_widget"
    id: int | None = SQLField(default=None, primary_key=True)
    name: str


class _RecountParams(BaseModel):
    count: int = Field(gt=5)


class I18nBulkWidgetAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter

    @action(label="Recount", bulk=True, form=_RecountParams)
    async def recount(self, request: Request, item_id: int, *, params: Any = None) -> None:
        """Never reached in these tests: the submitted params are invalid."""


@pytest.fixture(autouse=True)
def _cleanup_registry() -> Iterator[None]:
    saved = site._registry
    site._registry = {}
    yield
    site._registry = saved


def _bulk_client() -> TestClient:
    app = FastAPI()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup_database() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(setup_database)
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(I18nBulkWidget, I18nBulkWidgetAdmin)
    admin.mount(path="/admin")
    return TestClient(app)
