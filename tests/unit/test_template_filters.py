"""Unit tests for ``hyperadmin.views.template_filters``."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from jinja2 import Environment

from hyperadmin.views.template_filters import ha_dom_token, ha_pk, register_template_filters

UTC = timezone.utc
TOKYO = ZoneInfo("Asia/Tokyo")


def _env(*, default_timezone=UTC) -> Environment:
    env = Environment()
    register_template_filters(env, default_timezone=default_timezone)
    return env


def _render(template: str, *, request: SimpleNamespace, **extra) -> str:
    return _env().from_string(template).render(request=request, **extra)


def _request(timezone_override: object = None) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(hyperadmin_timezone=timezone_override))


# ---------------------------------------------------------------------------
# Story scenarios (st-v058-byoa-33)
# ---------------------------------------------------------------------------


def test_ha_pk_on_dict_and_instance() -> None:
    """
    Scenario: ha_pk on dict and instance
      Given a row dict with _pk and a model instance
      When  ha_pk runs
      Then  the pk is returned for both
    """
    row = {"_pk": 7, "id": 99}
    instance = SimpleNamespace(id=7)

    assert ha_pk(row) == 7
    assert ha_pk(instance) == 7


def test_ha_pk_falls_back_to_pk_attr_without_pk_key() -> None:
    """A dict row without ``_pk`` still resolves through ``pk_attr``."""
    row = {"code": "sku-1"}

    assert ha_pk(row, pk_attr="code") == "sku-1"


def test_ha_dom_token() -> None:
    """
    Scenario: ha_dom_token
      Given values 'a b?c' and 7
      When  ha_dom_token runs
      Then  a stable 'h...' token and '7' are returned
    """
    token = ha_dom_token("a b?c")

    assert token.startswith("h")
    assert token == ha_dom_token("a b?c")  # stable
    assert ha_dom_token(7) == "7"


def test_ha_dom_token_leaves_uuid_and_int_keys_unchanged() -> None:
    """Tokens for int and UUID keys are unchanged (A.9)."""
    uuid_text = "3fa85f64-5717-4562-b3fc-2c963f66afa6"

    assert ha_dom_token(uuid_text) == uuid_text
    assert ha_dom_token(42) == "42"


def test_per_request_tz() -> None:
    """
    Scenario: per-request tz
      Given request.state.hyperadmin_timezone=Asia/Tokyo
      When  ha_display(aware dt) runs
      Then  Tokyo time inside <time datetime=UTC-ISO> is rendered
    """
    value = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    request = _request("Asia/Tokyo")

    rendered = _render("{{ value|ha_display }}", request=request, value=value)

    assert '<time datetime="2026-01-01T00:00:00+00:00">' in rendered
    assert "2026-01-01 09:00:00" in rendered  # UTC+9


def test_per_request_tz_accepts_a_tzinfo_object() -> None:
    """The per-request override may already be a ``tzinfo``, not just a name."""
    value = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    request = _request(TOKYO)

    rendered = _render("{{ value|ha_display }}", request=request, value=value)

    assert "2026-01-01 09:00:00" in rendered


def test_default_timezone_applies_without_a_request_override() -> None:
    """With no per-request override, the admin's configured timezone is used."""
    value = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    request = _request(None)
    env = _env(default_timezone=TOKYO)

    rendered = env.from_string("{{ value|ha_display }}").render(request=request, value=value)

    assert "2026-01-01 09:00:00" in rendered


def test_naive_passthrough() -> None:
    """
    Scenario: naive passthrough
      Given a naive datetime
      When  ha_display runs
      Then  the output is unchanged
    """
    value = datetime(2026, 1, 1, 0, 0)
    request = _request("Asia/Tokyo")

    rendered = _render("{{ value|ha_display }}", request=request, value=value)

    assert rendered == str(value)


def test_ha_display_passes_through_non_datetime_values() -> None:
    """Every non-datetime value passes through unchanged (A.9)."""
    request = _request(None)

    assert _render("{{ value|ha_display }}", request=request, value=None) == "None"
    assert _render("{{ value|ha_display }}", request=request, value=42) == "42"


def test_ha_datetime_input_uses_the_resolved_timezone() -> None:
    """``ha_datetime_input`` localises an aware value for a datetime-local input."""
    value = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    request = _request("Asia/Tokyo")

    rendered = _render("{{ value|ha_datetime_input }}", request=request, value=value)

    assert rendered == "2026-01-01T09:00:00"
