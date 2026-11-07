"""``date`` fields render with a native date input (st-ux-erp-07)."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from hyperadmin import Admin
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views.forms import DateInput, DateTimeInput, PydanticForm


class _Schedule(BaseModel):
    due: date
    reminder: date | None = None
    starts_at: datetime | None = None


@pytest.mark.parametrize(
    ("name", "widget_cls"),
    [("due", DateInput), ("reminder", DateInput), ("starts_at", DateTimeInput)],
)
def test_date_annotations_map_to_the_date_widget(name: str, widget_cls: type) -> None:
    """
    Scenario: date field uses the native date picker
      Given a model with a date field
      When  its form is built
      Then  the field uses the date widget, and datetime keeps its own
    """
    form = PydanticForm(_Schedule)

    widget = next(f.widget for f in form.fields if f.name == name)

    assert type(widget) is widget_cls


def test_date_widget_renders_type_date_and_round_trips_iso() -> None:
    """
    Scenario: date field uses the native date picker
      Given a model with a date field holding 2026-03-04
      When  its create form renders and the ISO value is submitted
      Then  the input has type=date and the value validates unchanged
    """
    admin = Admin(app=FastAPI(), settings=HyperAdminSettings(create_tables=False))
    form = PydanticForm(_Schedule, initial={"due": date(2026, 3, 4)})
    field = next(f for f in form.fields if f.name == "due")
    field.value = date(2026, 3, 4)

    html = str(field.widget.render(admin.templates, field, None))

    assert 'type="date"' in html
    assert 'value="2026-03-04"' in html
    instance, errors = form.validate({"due": "2026-03-04"})
    assert errors == {}
    assert instance is not None
    assert instance.due == date(2026, 3, 4)
