"""Unit tests for PanelDef, @panel, collect_panels and resolve_panels.

Spec: ``docs/specs/detail-panels.md``; story ``st-v056-dp-01``.
"""

from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

import pytest
from starlette.responses import HTMLResponse, Response

from hyperadmin.core import panels as panels_module
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions
from hyperadmin.core.panels import (
    PanelDef,
    collect_panels,
    panel,
    panel_permission_codename,
    resolve_panels,
)
from hyperadmin.core.registry import SiteRegistry


class Order:
    """Stand-in model; only ``__name__`` matters for codename derivation."""


async def _invoice_handler(request: Any, obj: Any) -> Response:
    return HTMLResponse(f"invoice for {obj}")


def _is_paid(obj: Any) -> bool:
    return bool(getattr(obj, "paid", False))


@pytest.fixture
def registry(mocker) -> SiteRegistry:
    mocker.patch(
        "hyperadmin.core.registry.adapter_registry.find_adapter_for_model",
        return_value=object,
    )
    return SiteRegistry()


# ---------------------------------------------------------------------------
# PanelDef construction
# ---------------------------------------------------------------------------


def test_paneldef_construction_and_defaults():
    pd = PanelDef(slug="invoice", label="Invoice", handler=_invoice_handler)
    assert pd.slug == "invoice"
    assert pd.label == "Invoice"
    assert pd.handler is _invoice_handler
    assert pd.icon is None
    assert pd.permission is None
    assert pd.enabled is None


def test_paneldef_accepts_all_fields():
    pd = PanelDef(
        slug="invoice",
        label="Invoice",
        handler=_invoice_handler,
        icon="file-text",
        permission="invoice.view",
        enabled=_is_paid,
    )
    assert pd.icon == "file-text"
    assert pd.permission == "invoice.view"
    assert pd.enabled is _is_paid


def test_paneldef_is_frozen():
    pd = PanelDef(slug="invoice", label="Invoice", handler=_invoice_handler)
    with pytest.raises(dataclasses.FrozenInstanceError):
        pd.slug = "other"  # type: ignore[misc]


def test_paneldef_is_keyword_only():
    with pytest.raises(TypeError):
        PanelDef("invoice", "Invoice", _invoice_handler)  # type: ignore[misc]


@pytest.mark.parametrize("slug", ["", "Invoice", "has space", "-leading", "a/b", "ünïcode"])
def test_paneldef_rejects_non_url_safe_slug(slug: str):
    with pytest.raises(ValueError, match="invalid panel slug"):
        PanelDef(slug=slug, label="X", handler=_invoice_handler)


@pytest.mark.parametrize("slug", ["a", "invoice", "order-history", "state_machine", "v2"])
def test_paneldef_accepts_url_safe_slug(slug: str):
    assert PanelDef(slug=slug, label="X", handler=_invoice_handler).slug == slug


def test_paneldef_rejects_non_callable_handler():
    with pytest.raises(TypeError, match="handler must be callable"):
        PanelDef(slug="x", label="X", handler="not-a-callable")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# panel_permission_codename
# ---------------------------------------------------------------------------


def test_permission_codename_derived_from_model_and_slug():
    assert panel_permission_codename(Order, "invoice") == "view_order_panel_invoice"


# ---------------------------------------------------------------------------
# @panel decorator
# ---------------------------------------------------------------------------


def test_panel_decorator_attaches_paneldef_with_slug_from_method_name():
    @panel(label="History")
    async def history(self, request, obj):
        return HTMLResponse("")

    pd = history._panel_def
    assert isinstance(pd, PanelDef)
    assert pd.slug == "history"
    assert pd.label == "History"
    assert pd.handler is history
    assert pd.icon is None
    assert pd.permission is None
    assert pd.enabled is None


def test_panel_decorator_passes_through_all_options():
    @panel(label="Invoice", slug="pdf", icon="file", permission="invoice.view", enabled=_is_paid)
    async def render_invoice(self, request, obj):
        return HTMLResponse("")

    pd = render_invoice._panel_def
    assert pd.slug == "pdf"
    assert pd.icon == "file"
    assert pd.permission == "invoice.view"
    assert pd.enabled is _is_paid


def test_panel_decorator_returns_the_original_function():
    async def transitions(self, request, obj):
        return HTMLResponse("")

    assert panel(label="Transitions")(transitions) is transitions


def test_panel_decorator_allows_extra_keyword_only_params():
    @panel(label="X")
    async def handler(self, request, obj, *, fmt: str = "html"):
        return HTMLResponse(fmt)

    assert handler._panel_def.slug == "handler"


def test_panel_decorator_rejects_sync_handler():
    with pytest.raises(TypeError, match="must be an async function"):

        @panel(label="X")
        def not_async(self, request, obj):
            return HTMLResponse("")


def test_panel_decorator_rejects_missing_obj_parameter():
    with pytest.raises(
        TypeError, match=r"must accept \(self, request, obj\); got \(self, request\)"
    ):

        @panel(label="X")
        async def too_few(self, request):
            return HTMLResponse("")


def test_panel_decorator_rejects_invalid_explicit_slug():
    with pytest.raises(ValueError, match="invalid panel slug"):

        @panel(label="X", slug="Bad Slug")
        async def handler(self, request, obj):
            return HTMLResponse("")


# ---------------------------------------------------------------------------
# collect_panels
# ---------------------------------------------------------------------------


class _BaseAdmin(ModelAdmin):
    @panel(label="History")
    async def history(self, request, obj):
        return HTMLResponse("base history")

    @panel(label="Transitions")
    async def transitions(self, request, obj):
        return HTMLResponse("transitions")

    async def not_a_panel(self, request, obj):
        return HTMLResponse("")


class _ChildAdmin(_BaseAdmin):
    @panel(label="History (child)")
    async def history(self, request, obj):
        return HTMLResponse("child history")

    @panel(label="Invoice")
    async def invoice(self, request, obj):
        return HTMLResponse("invoice")


def test_collect_panels_returns_definitions_in_declaration_order():
    slugs = [pd.slug for pd in collect_panels(_BaseAdmin)]
    assert slugs == ["history", "transitions"]


def test_collect_panels_subclass_overrides_in_place_and_appends_new():
    found = collect_panels(_ChildAdmin)
    assert [pd.slug for pd in found] == ["history", "transitions", "invoice"]
    assert found[0].label == "History (child)"
    assert found[0].handler is _ChildAdmin.__dict__["history"]


def test_collect_panels_ignores_undecorated_methods_and_plain_classes():
    assert "not_a_panel" not in {pd.slug for pd in collect_panels(_BaseAdmin)}
    assert collect_panels(ModelAdmin) == []
    assert collect_panels(Order) == []


# ---------------------------------------------------------------------------
# AdminOptions.panels
# ---------------------------------------------------------------------------


def test_admin_options_panels_defaults_to_none():
    assert AdminOptions().panels is None


def test_admin_options_panels_keeps_paneldef_instances():
    pd = PanelDef(slug="invoice", label="Invoice", handler=_invoice_handler)
    opts = AdminOptions(panels=[pd])
    assert opts.panels == [pd]
    assert opts.panels[0] is pd


def test_admin_options_rejects_duplicate_panel_slugs():
    """Scenario: duplicate panel slug raises at registration.

    Given AdminOptions(panels=[PanelDef(slug="x", ...), PanelDef(slug="x", ...)])
    Then  ValueError("duplicate panel slug 'x'") is raised
    """
    with pytest.raises(ValueError, match="duplicate panel slug 'x'"):
        AdminOptions(
            panels=[
                PanelDef(slug="x", label="A", handler=_invoice_handler),
                PanelDef(slug="x", label="B", handler=_invoice_handler),
            ]
        )


# ---------------------------------------------------------------------------
# resolve_panels
# ---------------------------------------------------------------------------


def test_resolve_panels_derives_default_permission_codename(registry: SiteRegistry):
    """Scenario: default permission codename is derived from model and slug.

    Given PanelDef(slug="invoice", label="Invoice", handler=...) on the Order admin
    When  the panel is registered
    Then  the resolved permission is "view_order_panel_invoice"
    """
    options = AdminOptions(
        panels=[PanelDef(slug="invoice", label="Invoice", handler=_invoice_handler)]
    )
    registry.register(Order, options=options)
    admin_class = registry._registry[Order]

    (resolved,) = resolve_panels(admin_class(Order), Order)

    assert resolved.permission == "view_order_panel_invoice"
    assert resolved.slug == "invoice"
    assert resolved.handler is _invoice_handler


def test_resolve_panels_keeps_explicit_permission():
    """Scenario: explicit permission overrides the default.

    Given PanelDef(slug="invoice", ..., permission="invoice.view")
    Then  the resolved permission is "invoice.view"
    """

    class OrderAdmin(ModelAdmin):
        options = AdminOptions(
            panels=[
                PanelDef(
                    slug="invoice",
                    label="Invoice",
                    handler=_invoice_handler,
                    permission="invoice.view",
                )
            ]
        )

    (resolved,) = resolve_panels(OrderAdmin(Order), Order)
    assert resolved.permission == "invoice.view"


def test_resolve_panels_raises_on_slug_collision_between_options_and_class():
    class OrderAdmin(ModelAdmin):
        options = AdminOptions(panels=[PanelDef(slug="x", label="A", handler=_invoice_handler)])

        @panel(label="B", slug="x")
        async def other(self, request, obj):
            return HTMLResponse("")

    with pytest.raises(ValueError, match="duplicate panel slug 'x'"):
        resolve_panels(OrderAdmin(Order), Order)


def test_resolve_panels_raises_on_slug_collision_between_class_panels():
    class OrderAdmin(ModelAdmin):
        @panel(label="A", slug="x")
        async def first(self, request, obj):
            return HTMLResponse("")

        @panel(label="B", slug="x")
        async def second(self, request, obj):
            return HTMLResponse("")

    with pytest.raises(ValueError, match="duplicate panel slug 'x'"):
        resolve_panels(OrderAdmin, Order)


def test_resolve_panels_orders_options_before_class_panels_and_fills_permissions():
    class OrderAdmin(_BaseAdmin):
        options = AdminOptions(
            panels=[PanelDef(slug="invoice", label="Invoice", handler=_invoice_handler)]
        )

    resolved = resolve_panels(OrderAdmin(Order), Order)

    assert [pd.slug for pd in resolved] == ["invoice", "history", "transitions"]
    assert [pd.permission for pd in resolved] == [
        "view_order_panel_invoice",
        "view_order_panel_history",
        "view_order_panel_transitions",
    ]
    assert all(isinstance(pd, PanelDef) for pd in resolved)


def test_resolve_panels_binds_class_handlers_to_admin_instance():
    admin = _BaseAdmin(Order)
    history, _ = resolve_panels(admin, Order)

    assert history.handler.__self__ is admin  # type: ignore[attr-defined]
    response = asyncio.run(history.handler("request", "obj"))
    assert response.body == b"base history"


def test_resolve_panels_leaves_handlers_unbound_when_given_a_class():
    history, _ = resolve_panels(_BaseAdmin, Order)
    assert history.handler is _BaseAdmin.__dict__["history"]


def test_resolve_panels_preserves_enabled_and_icon():
    pd = PanelDef(
        slug="invoice", label="Invoice", handler=_invoice_handler, icon="file", enabled=_is_paid
    )

    class OrderAdmin(ModelAdmin):
        options = AdminOptions(panels=[pd])

    (resolved,) = resolve_panels(OrderAdmin(Order), Order)
    assert resolved.icon == "file"
    assert resolved.enabled is _is_paid


@pytest.mark.parametrize("options", [None, AdminOptions(), AdminOptions(panels=[])])
def test_resolve_panels_returns_empty_without_panels(options: AdminOptions | None):
    class OrderAdmin(ModelAdmin):
        pass

    OrderAdmin.options = options  # type: ignore[attr-defined]
    assert resolve_panels(OrderAdmin(Order), Order) == []


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


def test_core_package_exports_panel_api():
    from hyperadmin import core

    assert core.PanelDef is PanelDef
    assert core.panel is panel
    assert core.collect_panels is collect_panels
    assert core.resolve_panels is resolve_panels
    assert core.panel_permission_codename is panel_permission_codename
    for name in ("PanelDef", "panel", "collect_panels", "resolve_panels"):
        assert name in core.__all__


def test_panel_def_attribute_name_is_private():
    assert panels_module._PANEL_DEF_ATTR == "_panel_def"
