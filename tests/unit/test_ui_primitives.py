"""Rendering tests for the core UI primitives seam (design system port).

The design system (``docs/design/system/components/{Menu,Popover,Banner,Progress}``
and the generic pieces of ``bundle.css``) ships as CSS partials registered in
``hyperadmin.css``, one Jinja macro per primitive in ``templates/components/``
and ``static/js/primitives.js`` for the behaviour. Features (reports, the
permission matrix, the filter sidebar, bulk actions) use these and never copy
the CSS.
"""

from __future__ import annotations

import re
from pathlib import Path

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "hyperadmin"
TEMPLATES = PACKAGE / "templates"
CSS = PACKAGE / "static" / "css"
JS = PACKAGE / "static" / "js"

NEW_PARTIALS = (
    "_popup.css",
    "_menu.css",
    "_popover.css",
    "_banner.css",
    "_progress.css",
    "_seg.css",
    "_sticky.css",
    "_pill.css",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def env() -> Environment:
    """The shipped templates with the same extensions the admin installs."""
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
        extensions=["jinja2.ext.i18n"],
    )
    environment.install_null_translations(newstyle=True)
    environment.globals["csrf_input"] = lambda: Markup(
        '<input type="hidden" name="csrf" value="t">'
    )
    return environment


def _render(env: Environment, source: str, **context: object) -> str:
    return env.from_string(source).render(**context)


def _one_line(html: str) -> str:
    return re.sub(r"\s+", " ", html)


# ---------------------------------------------------------------------------
# CSS: the partials ship, are registered and only use defined tokens
# ---------------------------------------------------------------------------


def test_css_index_registers_every_new_partial_in_the_components_layer() -> None:
    """
    Scenario: the seam registers each primitive partial
      Given hyperadmin.css, the single CSS index
      Then  each new partial is imported into the components layer
      And   every import in the index resolves to a shipped file
    """
    index = (CSS / "hyperadmin.css").read_text()
    imports = re.findall(r'@import "([^"]+)"(?:\s+layer\((\w+)\))?;', index)

    layers = dict(imports)
    for partial in NEW_PARTIALS:
        assert layers.get(partial) == "components", partial
    for name, _layer in imports:
        assert (CSS / name).is_file(), name


def test_new_partials_use_only_defined_tokens() -> None:
    """
    Scenario: the port maps design tokens to shipped names
      Given the token files (_tokens.css, _dark-mode.css, _layout.css derived values)
      Then  every var(--ha-*) a new partial reads is defined
    """
    defined: set[str] = set()
    for source in ("_tokens.css", "_dark-mode.css", "_layout.css", "_accessibility.css"):
        defined.update(re.findall(r"(--ha-[\w-]+)\s*:", (CSS / source).read_text()))

    for partial in NEW_PARTIALS:
        used = set(re.findall(r"var\((--ha-[\w-]+)", (CSS / partial).read_text()))
        missing = used - defined
        assert not missing, f"{partial} reads undefined tokens: {sorted(missing)}"


def test_partials_carry_the_design_system_classes() -> None:
    """Each partial defines the class family the design system names."""
    expectations = {
        "_popup.css": (
            ".ha-layer",
            ".ha-popup--end",
            ".ha-popup--up",
            "details.ha-layer:not([open]) > .ha-popup",
        ),
        "_menu.css": (
            ".ha-menu__item",
            ".ha-menu__item--danger",
            '[aria-disabled="true"]',
            ".ha-kbd",
            ".ha-menu__check",
        ),
        "_popover.css": (
            ".ha-tip",
            ".ha-tooltip",
            ".ha-popover__title",
            ".ha-info-btn",
            ".is-dismissed",
        ),
        "_banner.css": (
            ".ha-banners",
            ".ha-banner--context",
            ".ha-banner--danger",
            ".ha-countdown",
        ),
        "_progress.css": (
            ".ha-progress__bar",
            ".ha-progress--indeterminate",
            ".ha-progress__segments",
            ".is-failed",
        ),
        "_seg.css": (
            '.ha-seg button[aria-pressed="true"]',
            '.ha-seg a[aria-current="true"]',
            ".ha-seg--radio",
        ),
        "_sticky.css": (
            ".ha-sticky-first",
            ".ha-col-check",
            '[dir="rtl"] .ha-table .ha-sticky-first',
        ),
        "_pill.css": (
            ".ha-pill--success",
            ".ha-pill--danger",
            ".ha-pill::before",
            ".ha-count",
            ".ha-chip",
        ),
    }
    for partial, selectors in expectations.items():
        text = (CSS / partial).read_text()
        for selector in selectors:
            assert selector in text, f"{partial} lacks {selector}"


def test_truncation_unfolds_on_keyboard_focus() -> None:
    """``.ha-trunc`` unfolds for keyboard users (tabindex="0"), as in the design."""
    utilities = (CSS / "_utilities.css").read_text()

    assert ".ha-trunc:focus-visible" in utilities


# ---------------------------------------------------------------------------
# Icons
# ---------------------------------------------------------------------------


def test_bar_chart_icon_is_in_the_generated_macro(env: Environment) -> None:
    """
    Scenario: the reports plugin can name its icon
      Given static/icons/bar-chart-3.svg from the pinned Lucide release
      When  icon('bar-chart-3') renders
      Then  the inlined SVG carries the Lucide paths, aria-hidden
    """
    assert (PACKAGE / "static" / "icons" / "bar-chart-3.svg").is_file()

    html = _render(env, "{% from 'components/_icons.html' import icon %}{{ icon('bar-chart-3') }}")

    assert 'class="ha-icon"' in html
    assert 'aria-hidden="true"' in html
    assert '<path d="M3 3v18h18"/>' in html


# ---------------------------------------------------------------------------
# seg
# ---------------------------------------------------------------------------


SEG_OPTIONS = [
    {"value": "6m", "label": "6M"},
    {"value": "12m", "label": "12M", "selected": True, "attrs": {"hx-get": "/r?period=12m"}},
]


def test_seg_renders_links_with_aria_current(env: Environment) -> None:
    """
    Scenario: a period switch of links
      When  seg(options, label='Period', testid='chart-period') renders without a name
      Then  each option is a link to ?period=<value>, the selected one aria-current="true"
      And   extra attrs (hx-get) upgrade the link; each option has <testid>-<value>
    """
    html = _render(
        env,
        "{% from 'components/seg.html' import seg %}{{ seg(options, label='Period', testid='chart-period') }}",
        options=SEG_OPTIONS,
    )

    assert (
        '<div class="ha-seg" role="group" aria-label="Period" data-testid="chart-period">' in html
    )
    assert '<a href="?period=6m" data-testid="chart-period-6m">6M</a>' in html
    assert (
        'href="?period=12m" aria-current="true" data-testid="chart-period-12m" hx-get="/r?period=12m">12M</a>'
        in html
    )
    assert "aria-pressed" not in html


def test_seg_renders_submit_buttons_with_aria_pressed(env: Environment) -> None:
    """
    Scenario: the report group-by control in a GET form
      When  seg(options, name='period', labelledby='p-l', describedby='p-auto') renders
      Then  each option is a submit button carrying name/value and aria-pressed
    """
    html = _render(
        env,
        "{% from 'components/seg.html' import seg %}"
        "{{ seg(options, name='period', labelledby='p-l', describedby='p-auto', testid='report-period') }}",
        options=SEG_OPTIONS,
    )

    assert 'aria-labelledby="p-l" aria-describedby="p-auto"' in html
    assert (
        '<button type="submit" name="period" value="6m" aria-pressed="false" data-testid="report-period-6m">6M</button>'
        in html
    )
    assert (
        'value="12m" aria-pressed="true" data-testid="report-period-12m" hx-get="/r?period=12m">12M</button>'
        in html
    )
    assert "<a " not in html


def test_seg_option_without_value_uses_its_label_and_href(env: Environment) -> None:
    html = _render(
        env,
        "{% from 'components/seg.html' import seg %}{{ seg(options, param='view', class='ha-x') }}",
        options=[{"label": "Day", "href": "/day"}, {"label": "Week"}],
    )

    assert 'class="ha-seg ha-x"' in html
    assert '<a href="/day">Day</a>' in html
    assert '<a href="?view=Week">Week</a>' in html
    assert "data-testid" not in html


# ---------------------------------------------------------------------------
# menu
# ---------------------------------------------------------------------------


MENU_ITEMS = [
    {"heading": "Invoice INV-1"},
    {
        "label": "Edit",
        "href": "/edit",
        "icon": "pencil",
        "shortcut": "E",
        "testid": "row-edit-link",
    },
    {
        "label": "Duplicate",
        "post_url": "/dup",
        "description": "Copies the lines",
        "attrs": {"hx-boost": "true"},
    },
    {"divider": True},
    {
        "label": "Send reminder",
        "disabled_reason": "Only unpaid invoices can get a reminder",
        "icon": "mail",
    },
    {"label": "Number", "pressed": True},
    {"label": "Due date", "pressed": False},
    {"divider": True},
    {"label": "Delete…", "href": "/delete", "danger": True, "testid": "row-delete-btn"},
]


def test_menu_is_a_details_disclosure_with_real_links_and_forms(env: Environment) -> None:
    """
    Scenario: row actions menu
      When  menu('Actions', items, testid='row-actions') renders
      Then  the trigger is a <summary class="ha-btn"> with a chevron
      And   the popup holds a heading, a link, a POST form (with the CSRF input),
            dividers, a disabled item with its reason, toggle items and a danger link
    """
    html = _render(
        env,
        "{% from 'components/menu.html' import menu %}{{ menu('Actions', items, testid='row-actions') }}",
        items=MENU_ITEMS,
    )
    flat = _one_line(html)

    assert '<details class="ha-layer" data-testid="row-actions">' in html
    assert (
        '<summary class="ha-btn" id="ha-menu-actions-trigger">Actions<svg class="ha-icon ha-icon--sm"'
        in flat
    )
    assert '<div class="ha-popup ha-menu" aria-label="Actions" data-ha-align="start">' in html
    assert '<div class="ha-menu__label">Invoice INV-1</div>' in html
    # link with icon, shortcut and its view test id
    assert '<a class="ha-menu__item" href="/edit" data-testid="row-edit-link">' in html
    assert (
        '<span class="ha-menu__text"><span>Edit</span></span><span class="ha-menu__end"><kbd class="ha-kbd">E</kbd></span></a>'
        in html
    )
    # POST item: form + submit button, csrf input, description linked by aria-describedby
    assert '<form method="post" action="/dup"><input type="hidden" name="csrf" value="t">' in flat
    assert (
        '<button type="submit" class="ha-menu__item" aria-describedby="ha-menu-actions-desc-3" hx-boost="true">'
        in flat
    )
    assert '<span class="ha-menu__desc" id="ha-menu-actions-desc-3">Copies the lines</span>' in html
    assert flat.count("<hr>") == 2
    # disabled with a reason stays a focusable button
    assert (
        '<button type="button" class="ha-menu__item" aria-disabled="true" aria-describedby="ha-menu-actions-desc-5">'
        in flat
    )
    assert "Only unpaid invoices can get a reminder</span>" in html
    # toggle items
    assert 'aria-pressed="true"' in html
    assert 'aria-pressed="false"' in html
    assert flat.count('class="ha-icon ha-menu__check"') == 2
    # danger last
    assert (
        '<a class="ha-menu__item ha-menu__item--danger" href="/delete" data-testid="row-delete-btn">'
        in html
    )


def test_menu_icon_only_trigger_and_end_alignment(env: Environment) -> None:
    """
    Scenario: icon-only trigger naming the object
      When  menu('More actions for INV-1', items, icon_only=True, align='end') renders
      Then  the summary is an icon button with that aria-label and the popup opens to the end
    """
    html = _render(
        env,
        "{% from 'components/menu.html' import menu %}"
        "{{ menu('More actions for INV-1', items, icon_only=True, align='end', id='m1', aria_label='Actions for INV-1') }}",
        items=[{"label": "Edit", "href": "/edit"}],
    )
    flat = _one_line(html)

    assert (
        '<summary class="ha-btn ha-btn--icon" id="m1-trigger" aria-label="More actions for INV-1"><svg class="ha-icon"'
        in flat
    )
    assert "chevron" not in html
    assert (
        '<div class="ha-popup ha-menu ha-popup--end" aria-label="Actions for INV-1" data-ha-align="end">'
        in html
    )


def test_menu_without_csrf_global_omits_the_hidden_input(env: Environment) -> None:
    del env.globals["csrf_input"]

    html = _render(
        env,
        "{% from 'components/menu.html' import menu %}{{ menu('Actions', items) }}",
        items=[{"label": "Archive", "post_url": "/archive", "icon": "trash-2"}],
    )
    flat = _one_line(html)

    assert (
        '<form method="post" action="/archive"><button type="submit" class="ha-menu__item">' in flat
    )
    assert "csrf" not in html


# ---------------------------------------------------------------------------
# popover and tooltip
# ---------------------------------------------------------------------------


def test_popover_is_a_labelled_non_modal_dialog(env: Environment) -> None:
    """
    Scenario: field help popover
      When  popover('What is a journal entry?', title=..., id='help-je', body=...) renders
      Then  the trigger is a .ha-info-btn with the aria-label
      And   the popup is role="dialog" labelled by its title, with a close button
    """
    html = _render(
        env,
        "{% from 'components/popover.html' import popover %}"
        "{{ popover('What is a journal entry?', title='Journal entry', id='help-je', body='A dated record.', testid='popover-help') }}",
    )
    flat = _one_line(html)

    assert (
        '<summary class="ha-info-btn" aria-label="What is a journal entry?" data-testid="popover-help">'
        in flat
    )
    assert (
        '<div class="ha-popup ha-popover" role="dialog" aria-labelledby="help-je-title" tabindex="-1" data-ha-align="start">'
        in html
    )
    assert '<h3 class="ha-popover__title" id="help-je-title">Journal entry</h3>' in html
    assert 'class="ha-btn ha-btn--icon" aria-label="Close" data-ha-popup-close>' in html
    assert "<p>A dated record.</p>" in html
    assert "ha-popover__actions" not in html


def test_popover_with_caller_body_text_trigger_and_actions(env: Environment) -> None:
    """
    Scenario: AI provenance popover with Accept / Discard
      When  popover is called with a body block, a text trigger and two actions
      Then  the block replaces the body, the trigger shows its text and the actions render
    """
    html = _render(
        env,
        "{% from 'components/popover.html' import popover %}"
        "{% call popover('AI-generated', title='Suggested category', id='ai', trigger_icon='sparkles',"
        " trigger_class='ha-btn ha-btn--sm', trigger_text=True, align='end', closable=False,"
        " actions=[{'label': 'Accept', 'primary': True, 'testid': 'ai-accept', 'attrs': {'hx-post': '/accept'}},"
        " {'label': 'Guide', 'href': '/guide'}]) %}<dl class='ha-popover__meta'><dt>Generated</dt><dd>Today</dd></dl>{% endcall %}",
    )
    flat = _one_line(html)

    assert '<summary class="ha-btn ha-btn--sm"><svg class="ha-icon ha-icon--sm"' in flat
    assert "</svg>AI-generated</summary>" in flat
    assert "ha-popover ha-popup--end" in html
    assert "data-ha-popup-close" not in html
    assert "<dl class='ha-popover__meta'>" in html
    assert (
        '<button type="button" class="ha-btn ha-btn--sm ha-btn--primary" data-testid="ai-accept" hx-post="/accept">Accept</button>'
        in html
    )
    assert '<a class="ha-btn ha-btn--sm" href="/guide">Guide</a>' in html


def test_tooltip_repeats_the_label_or_describes_the_trigger(env: Environment) -> None:
    """
    Scenario: tooltip on an icon button, and a disabled reason
      When  tip('Edit') wraps a button
      Then  the tooltip is aria-hidden (the button keeps its own label)
      When  tip(reason, id='tip-r', describes=True, placement='below') wraps it
      Then  it has role="tooltip" and the id the trigger points at
    """
    label = _render(
        env,
        "{% from 'components/tooltip.html' import tip %}{% call tip('Edit') %}<button aria-label='Edit'>e</button>{% endcall %}",
    )
    reason = _render(
        env,
        "{% from 'components/tooltip.html' import tip %}"
        "{% call tip('Only unpaid', id='tip-r', describes=True, placement='below', class='x') %}"
        "<button aria-disabled='true' aria-describedby='tip-r'>s</button>{% endcall %}",
    )

    assert _one_line(label) == (
        "<span class=\"ha-tip\"><button aria-label='Edit'>e</button>"
        '<span class="ha-tooltip" aria-hidden="true">Edit</span></span>'
    )
    assert '<span class="ha-tip x">' in reason
    assert (
        '<span class="ha-tooltip ha-tooltip--below" role="tooltip" id="tip-r">Only unpaid</span>'
        in reason
    )


# ---------------------------------------------------------------------------
# banner
# ---------------------------------------------------------------------------


def test_banner_kinds_roles_icons_and_actions(env: Environment) -> None:
    """
    Scenario: one banner per kind
      Then  danger and warning are role="alert", the rest role="status"
      And   each kind has its icon (context has none), a bold sentence and a detail span
      And   actions render as small buttons or links; a dismiss button only when asked
    """
    source = (
        "{% from 'components/banner.html' import banner %}"
        "{{ banner('Too many requests.', kind='danger', detail='Try again in 23 s.',"
        " actions=[{'label': 'Retry', 'disabled': True, 'testid': 'retry'}], testid='banner-rate-limit') }}"
        "{{ banner('Record changed.', kind='warning', actions=[{'label': 'Compare', 'attrs': {'hx-get': '/diff'}}, {'label': 'Reload', 'href': '/r', 'primary': True}]) }}"
        "{{ banner('Working in Acme.', kind='context', dismissible=True, prefix='<b>NE</b> ') }}"
        "{{ banner('Read-only until 18:00.', kind='info', dismissible=True, id='maint') }}"
        "{{ banner('Back online.', kind='success', live=False, icon_name='sparkles') }}"
    )
    html = _render(env, source)
    flat = _one_line(html)

    assert (
        '<div class="ha-banner ha-banner--danger" role="alert" data-testid="banner-rate-limit">'
        in html
    )
    assert (
        '<p class="ha-banner__text">Too many requests. <span>Try again in 23 s.</span></p>' in html
    )
    assert (
        '<button type="button" class="ha-btn ha-btn--sm" disabled data-testid="retry">Retry</button>'
        in html
    )
    assert '<div class="ha-banner ha-banner--warning" role="alert">' in html
    assert '<button type="button" class="ha-btn ha-btn--sm" hx-get="/diff">Compare</button>' in html
    assert '<a class="ha-btn ha-btn--sm ha-btn--primary" href="/r">Reload</a>' in html
    # context: status, no icon, never dismissible, prefix is escaped
    assert '<div class="ha-banner ha-banner--context" role="status">' in html
    assert "&lt;b&gt;NE&lt;/b&gt; Working in Acme." in html
    assert flat.count("data-ha-dismiss") == 1
    assert '<div class="ha-banner ha-banner--info" role="status" id="maint">' in html
    assert 'aria-label="Dismiss" data-ha-dismiss>' in html
    # live=False: no role at all; icon override
    assert '<div class="ha-banner ha-banner--success">' in html
    # icons: circle-x, triangle-alert, info, and the sparkles override
    assert flat.count("<svg") == 5  # 4 banner icons + the dismiss ✕


def test_banners_region_orders_by_severity_and_collapses_the_rest(env: Environment) -> None:
    """
    Scenario: the sticky region under the navbar
      Given four banners in arbitrary order
      When  banners(items) renders
      Then  the region is role="region" aria-label="Notices", most severe first
      And   only two show, the rest collapse into "+N more notices"
    """
    items = [
        {"message": "Maintenance", "kind": "info"},
        {"message": "Stale", "kind": "warning", "testid": "banner-stale"},
        {"message": "Rate limit", "kind": "danger"},
        {"message": "Tenant", "kind": "context"},
    ]
    html = _render(
        env,
        "{% from 'components/banner.html' import banners %}{{ banners(items, more_href='/notices') }}",
        items=items,
    )

    assert (
        '<div class="ha-banners" role="region" aria-label="Notices" data-testid="banners">' in html
    )
    assert html.index("Rate limit") < html.index("Stale")
    assert "Tenant" not in html
    assert "Maintenance" not in html
    assert '<a class="ha-banner__more" href="/notices">+2 more notices</a>' in html


def test_banners_region_shows_everything_under_the_limit(env: Environment) -> None:
    html = _render(
        env,
        "{% from 'components/banner.html' import banners %}{{ banners(items, limit=3, testid=none) }}",
        items=[{"message": "A"}, {"message": "B", "kind": "success"}],
    )

    assert "data-testid" not in html
    assert html.index(">A<") < html.index(">B<")
    assert "more notice" not in html

    one_more = _render(
        env,
        "{% from 'components/banner.html' import banners %}{{ banners(items, limit=1) }}",
        items=[{"message": "A"}, {"message": "B"}],
    )
    assert '<span class="ha-banner__more">+1 more notice</span>' in one_more


# ---------------------------------------------------------------------------
# progress
# ---------------------------------------------------------------------------


def test_progress_determinate_bar_and_foot(env: Environment) -> None:
    """
    Scenario: determinate export progress
      When  progress('Exporting', value=12, max=25, value_text='48% · 12 of 25 pages') renders with a foot block
      Then  the track is role="progressbar" with aria-valuenow 48 and aria-valuetext in words
      And   the bar width comes from --value: 48%; the value text is a polite live region
    """
    html = _render(
        env,
        "{% from 'components/progress.html' import progress %}"
        "{% call progress('Exporting', value=12, max=25, value_text='48% · 12 of 25 pages', testid='progress-export',"
        " actions=[{'label': 'Cancel', 'attrs': {'hx-delete': '/job'}}]) %}<span>About 20 s left</span>{% endcall %}",
    )
    flat = _one_line(html)

    assert '<div class="ha-progress" data-testid="progress-export">' in html
    assert '<span class="ha-progress__label">Exporting</span>' in html
    assert '<span class="ha-progress__value" aria-live="polite">48% · 12 of 25 pages</span>' in html
    assert (
        '<div class="ha-progress__track" role="progressbar" aria-label="Exporting" aria-valuemin="0" aria-valuemax="100"'
        ' aria-valuenow="48" aria-valuetext="48% · 12 of 25 pages">'
    ) in html
    assert '<span class="ha-progress__bar" style="--value: 48%"></span>' in html
    assert '<div class="ha-progress__foot"><span>About 20 s left</span>' in flat
    assert (
        '<button type="button" class="ha-btn ha-btn--sm" hx-delete="/job">Cancel</button>' in html
    )


def test_progress_indeterminate_has_no_valuenow(env: Environment) -> None:
    html = _render(
        env,
        "{% from 'components/progress.html' import progress %}{{ progress('Preparing export…', size='sm', id='p1') }}",
    )

    assert '<div class="ha-progress ha-progress--sm ha-progress--indeterminate" id="p1">' in html
    assert "aria-valuenow" not in html
    assert "aria-valuetext" not in html
    assert '<span class="ha-progress__bar"></span>' in html
    assert "ha-progress__foot" not in html


def test_progress_states_show_a_word_and_an_icon(env: Environment) -> None:
    """
    Scenario: done, partly failed and failed
      Then  each state adds its modifier, the status text and the matching icon,
            and the final action (Download CSV / Retry) sits in the foot
    """
    source = (
        "{% from 'components/progress.html' import progress %}"
        "{{ progress('Export ready', value=100, state='success', status='Finished in 14 s',"
        " actions=[{'label': 'Download CSV', 'href': '/csv', 'primary': True, 'testid': 'dl'}]) }}"
        "{{ progress('Mark as paid', value=20, max=20, state='warning', status='2 failed', value_text='18 of 20 done') }}"
        "{{ progress('Export', value=62, state='danger', status='The server timed out.') }}"
    )
    html = _render(env, source)
    flat = _one_line(html)

    assert '<div class="ha-progress ha-progress--success">' in html
    assert 'aria-valuenow="100" aria-valuetext="100%"' in html
    assert (
        '<a class="ha-btn ha-btn--sm ha-btn--primary" href="/csv" data-testid="dl">Download CSV</a>'
        in html
    )
    assert '<div class="ha-progress ha-progress--warning">' in html
    assert 'aria-valuetext="18 of 20 done"' in html
    assert '<div class="ha-progress ha-progress--danger">' in html
    assert 'style="--value: 62%"' in html
    assert flat.count('<span class="ha-progress__status"><svg class="ha-icon ha-icon--sm"') == 3
    assert "The server timed out.</span>" in html


def test_progress_steps_render_segments(env: Environment) -> None:
    """
    Scenario: multi-stage import
      When  progress('Importing', steps=5, step=3, failed_steps=1, value_text='Step 3 of 5') renders
      Then  the progressbar counts steps (max 5, now 3) and five segments show done / failed / pending
    """
    html = _render(
        env,
        "{% from 'components/progress.html' import progress %}"
        "{{ progress('Importing', steps=5, step=3, failed_steps=1, value_text='Step 3 of 5') }}",
    )
    flat = _one_line(html)

    assert "ha-progress--indeterminate" not in html
    assert (
        '<div role="progressbar" aria-label="Importing" aria-valuemin="0" aria-valuemax="5" aria-valuenow="3" aria-valuetext="Step 3 of 5">'
        in html
    )
    assert (
        '<div class="ha-progress__segments" aria-hidden="true"><span class="is-done"></span><span class="is-done"></span>'
        '<span class="is-done"></span><span class="is-failed"></span><span class=""></span></div>'
    ) in flat
    assert "ha-progress__track" not in html


# ---------------------------------------------------------------------------
# pill
# ---------------------------------------------------------------------------


def test_pill_is_a_word_on_its_tint(env: Environment) -> None:
    html = _render(
        env,
        "{% from 'components/pill.html' import pill %}{{ pill('Paid', 'success', testid='row-status') }}{{ pill('Draft') }}{{ pill('New', 'new', class='x') }}",
    )

    assert '<span class="ha-pill ha-pill--success" data-testid="row-status">Paid</span>' in html
    assert '<span class="ha-pill">Draft</span>' in html
    assert '<span class="ha-pill ha-pill--new x">New</span>' in html


# ---------------------------------------------------------------------------
# Behaviour script and the page that loads it
# ---------------------------------------------------------------------------


class PrimProduct(SQLModel, table=True):
    __tablename__ = "test_prim_product"
    id: int | None = Field(default=None, primary_key=True)
    name: str


class PrimProductAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


@pytest.fixture
def client() -> TestClient:
    site._registry = {}
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    anyio.run(setup)
    app = FastAPI()
    admin = Admin(app=app, engine=engine, settings=HyperAdminSettings(create_tables=False))
    site.register(PrimProduct, PrimProductAdmin)
    admin.mount(path="/admin")
    yield TestClient(app)
    site._registry = {}


def test_primitives_script_and_partials_are_served_and_loaded(client: TestClient) -> None:
    """
    Scenario: the behaviour ships as a static file loaded by base.html
      When  a page extending base.html renders
      Then  it loads /static/js/primitives.js once, after autocomplete.js, deferred
      And   the script and every new CSS partial are served under the admin static mount
    """
    body = client.get("/admin/primproduct/").text

    assert body.count("/static/js/primitives.js") == 1
    assert body.index("/static/js/autocomplete.js") < body.index("/static/js/primitives.js")
    assert re.search(r'<script src="[^"]*/static/js/primitives\.js" defer></script>', body)

    js = client.get("/admin/static/js/primitives.js")
    assert js.status_code == 200
    assert "window.hyperadminPrimitives" in js.text  # loads once, whatever includes it
    for hook in (
        "details.ha-layer",
        "data-ha-popup-close",
        "data-ha-dismiss",
        "ha-popup--up",
        "ha-popup--end",
        "is-dismissed",
        "Escape",
    ):
        assert hook in js.text, hook
    for partial in NEW_PARTIALS:
        assert client.get(f"/admin/static/css/{partial}").status_code == 200, partial


def test_primitives_script_has_no_hover_only_or_alpine_dependency() -> None:
    """Keyboard and touch work: nothing is wired to hover alone, and nothing waits for Alpine."""
    script = (JS / "primitives.js").read_text()

    assert "mouseover" not in script
    assert "mouseenter" not in script
    assert "Alpine.data" not in script  # nothing waits for alpine:init
    assert "Alpine.store" not in script
    assert "alpine:init" not in script
    assert "keydown" in script
    assert '"toggle"' in script  # <details> toggle, listened in the capture phase
