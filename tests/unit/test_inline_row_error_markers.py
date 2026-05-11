"""Template rendering tests for inline_row.html row-level error markers (H2 polish).

The BDD scenarios from
``.meta/epics/epic-v050-h2-inline-row-errors/stories/fixinlines-row-level-error-highlighting.md``
are exercised here at the template-rendering level. A full E2E suite will be
added when an example app exposes inline formsets end-to-end; this template
test pins the contract that downstream UI tests can rely on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlmodel import Field, SQLModel

from hyperadmin.core.inlines import InlineModelSpec
from hyperadmin.views.forms import InlineFormset


class _Child(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    parent_id: int


def _render_inline_row(row, fs) -> str:
    """Render ``components/inline_row.html`` standalone for assertion-level testing."""
    templates_dir = Path(__file__).resolve().parents[2] / "src" / "hyperadmin" / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["_"] = lambda s: s  # identity gettext for tests
    tpl = env.get_template("components/inline_row.html")
    return tpl.render(row=row, inline=fs)


@pytest.fixture
def _formset() -> InlineFormset:
    spec = InlineModelSpec(model=_Child, fk_field="parent_id")
    return InlineFormset(spec=spec)


def test_row_with_field_error_emits_row_level_error_markers(_formset: InlineFormset) -> None:
    # Given a row whose first field carries a validation error
    row = _formset._build_row(1)
    row.fields[0].errors = ["Required"]

    # When the inline_row template renders
    html = _render_inline_row(row, _formset)

    # Then the row exposes a row-level error testid, aria-invalid, and CSS class
    expected_testid = f'data-testid="inline-{_formset.prefix}-row-1-error"'
    assert expected_testid in html
    assert 'aria-invalid="true"' in html
    assert "ha-inline-row-error" in html


def test_all_valid_row_renders_no_row_level_error_marker(_formset: InlineFormset) -> None:
    # Given a row with no field errors
    row = _formset._build_row(2)
    for field in row.fields:
        field.errors = None

    # When the inline_row template renders
    html = _render_inline_row(row, _formset)

    # Then no row-level error markers appear
    assert "-row-2-error" not in html
    assert 'aria-invalid="true"' not in html
    assert "ha-inline-row-error" not in html


def test_existing_row_testid_is_unchanged(_formset: InlineFormset) -> None:
    """The legacy row-finding testid must keep working for current selectors."""
    row = _formset._build_row(0)
    row.fields[0].errors = ["bad"]

    html = _render_inline_row(row, _formset)

    expected = f'data-testid="inline-{_formset.prefix}-row-0"'
    assert expected in html
