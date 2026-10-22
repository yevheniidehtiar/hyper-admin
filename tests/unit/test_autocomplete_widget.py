"""Unit tests for the FK/M2M autocomplete widget and the popup slot (H6, v0.5.5).

Mirrors the BDD scenarios in
``.meta/epics/epic-v055-htmx-autocomplete/stories/feattemplates-autocomplete-widget-and-popup-modal.md``.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

from hyperadmin import Admin
from hyperadmin.adapters.sqlmodel import SQLModelAdapter
from hyperadmin.core.choices import SelectFieldMeta
from hyperadmin.core.model import ModelAdmin
from hyperadmin.core.options import AdminOptions, RelationDependency
from hyperadmin.core.registry import site
from hyperadmin.core.settings import HyperAdminSettings
from hyperadmin.views import dynamic as dynamic_module
from hyperadmin.views.dynamic import base as base_module
from hyperadmin.views.dynamic import relations as relations_module
from hyperadmin.views.forms import (
    AutocompleteMultiWidget,
    AutocompleteWidget,
    RelationMultiSelectWidget,
    RelationSelectWidget,
    relation_widget,
)

STATIC_JS = Path(dynamic_module.__file__).parent.parent.parent / "static" / "js" / "autocomplete.js"


class AcSupplier(SQLModel, table=True):
    __tablename__ = "test_ac_supplier"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    city: str | None = None


class AcVariant(SQLModel, table=True):
    __tablename__ = "test_ac_variant"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    supplier_id: int | None = Field(default=None, foreign_key="test_ac_supplier.id")

    supplier: Mapped[AcSupplier | None] = Relationship()


class AcProduct(SQLModel, table=True):
    __tablename__ = "test_ac_product"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    supplier_id: int | None = Field(default=None, foreign_key="test_ac_supplier.id")
    variant_id: int | None = Field(default=None, foreign_key="test_ac_variant.id")

    supplier: Mapped[AcSupplier | None] = Relationship()
    variant: Mapped[AcVariant | None] = Relationship()


class AcSupplierAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


class AcVariantAdmin(ModelAdmin):
    adapter_class = SQLModelAdapter


def _product_admin(**options: Any) -> type[ModelAdmin]:
    return type(
        "AcProductAdmin",
        (ModelAdmin,),
        {"adapter_class": SQLModelAdapter, "options": AdminOptions(**options)},
    )


@pytest.fixture(autouse=True)
def _cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


def _engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(engine) as session:
            session.add(AcSupplier(id=1, name="Acme", city="Paris"))
            session.add(AcVariant(id=7, name="Blue", supplier_id=1))
            await session.commit()

    anyio.run(setup)
    return engine


def _client(
    *,
    register_supplier: bool = True,
    supplier_admin: type[ModelAdmin] = AcSupplierAdmin,
    **options: Any,
) -> TestClient:
    app = FastAPI()
    admin = Admin(app=app, engine=_engine(), settings=HyperAdminSettings(create_tables=False))
    site.register(AcProduct, _product_admin(**options))
    site.register(AcVariant, AcVariantAdmin)
    if register_supplier:
        site.register(AcSupplier, supplier_admin)
    admin.mount(path="/admin")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Story scenarios
# ---------------------------------------------------------------------------


def test_fk_field_renders_as_autocomplete_by_default():
    """
    Scenario: FK field renders as autocomplete by default
      When  the user opens /admin/acproduct/create
      Then  the supplier_id field is rendered with data-testid="autocomplete-supplier_id"
    """
    body = _client().get("/admin/acproduct/create").text

    assert 'data-testid="autocomplete-supplier_id"' in body
    assert 'data-testid="autocomplete-select-supplier_id"' in body
    # The search input GETs the namespaced choices endpoint for the relation.
    assert '/admin/acproduct/choices/supplier"' in body
    assert 'hx-trigger="input changed delay:200ms, search"' in body
    # Preloaded choices keep the select usable before any search.
    assert '<option value="1">Acme</option>' in body


def test_dependent_fk_widget_includes_parent_field_in_hx_include():
    """
    Scenario: dependent FK widget includes parent field in hx-include
      Given relation_filters has variant_id depends_on supplier_id
      When  the widget for variant_id is rendered
      Then  its hx-include attribute is "[name='supplier_id']"
    """
    client = _client(
        relation_filters={
            "variant_id": RelationDependency(
                depends_on="supplier_id", placeholder="Pick a supplier first"
            )
        }
    )
    body = client.get("/admin/acproduct/create").text

    widget = body.split('data-field="variant_id"', 1)[1].split("</select>", 1)[0]
    assert "hx-include=\"[name='supplier_id']\"" in widget
    assert "change from:[name='supplier_id']" in widget
    assert 'placeholder="Pick a supplier first"' in widget


def test_add_button_omitted_when_related_model_unregistered():
    """
    Scenario: "+" button omitted when related model unregistered
      Given Supplier is NOT registered with the Admin
      When  the supplier_id widget renders
      Then  no element with data-testid="autocomplete-add-supplier_id" is present
    """
    body = _client(register_supplier=False).get("/admin/acproduct/create").text

    assert 'data-testid="autocomplete-supplier_id"' in body
    assert 'data-testid="autocomplete-add-supplier_id"' not in body


def test_add_button_rendered_when_related_model_registered():
    """The "+" button loads the target's create popup into #ha-popup-root."""
    body = _client().get("/admin/acproduct/create").text

    assert 'data-testid="autocomplete-add-supplier_id"' in body
    assert '/admin/acsupplier/create-popup?target=supplier_id&amp;source=acproduct"' in body
    assert 'hx-target="#ha-popup-root"' in body


def test_display_template_renders_custom_option_label():
    """
    Scenario: display_template renders custom option label
      Given relation_display has supplier_id = "{name} — {city}"
      And   the dataset has one Supplier(name="Acme", city="Paris")
      When  choices_view returns a fragment
      Then  the rendered option label is "Acme — Paris"
    """
    client = _client(relation_display={"supplier_id": "{name} — {city}"})

    response = client.get("/admin/acproduct/choices/supplier?q=ac")

    assert response.status_code == 200
    assert '<option value="1">Acme — Paris</option>' in response.text


def test_display_template_keyed_by_relationship_name():
    """relation_display may also be keyed by the relationship name; a callable is applied."""
    client = _client(relation_display={"supplier": lambda s: s.name.upper()})

    response = client.get("/admin/acproduct/choices/supplier")

    assert '<option value="1">ACME</option>' in response.text


def test_choices_without_display_template_use_display_name():
    """Without relation_display the adapter's default label is unchanged."""
    response = _client().get("/admin/acproduct/choices/supplier")

    assert '<option value="1">Acme</option>' in response.text


# ---------------------------------------------------------------------------
# Opt-out, popup gating and slot
# ---------------------------------------------------------------------------


def test_use_autocomplete_widget_false_keeps_legacy_select():
    """Admins that set use_autocomplete_widget=False keep the plain relation select."""
    body = _client(use_autocomplete_widget=False).get("/admin/acproduct/create").text

    assert 'data-testid="supplier_id-relation-select"' in body
    assert 'data-testid="autocomplete-supplier_id"' not in body


def test_add_button_omitted_when_target_cannot_create():
    """A registered target whose admin disables create exposes no popup route."""
    no_create = type(
        "NoCreateSupplierAdmin",
        (ModelAdmin,),
        {"adapter_class": SQLModelAdapter, "options": AdminOptions(can_create=False)},
    )
    body = _client(supplier_admin=no_create).get("/admin/acproduct/create").text

    assert 'data-testid="autocomplete-supplier_id"' in body
    assert 'data-testid="autocomplete-add-supplier_id"' not in body


def test_popup_root_slot_rendered_once_with_script():
    """base.html carries the single popup slot plus the widget's static JS and CSS."""
    body = _client().get("/admin/acproduct/create").text

    assert body.count('id="ha-popup-root"') == 1
    assert 'data-testid="popup-root"' in body
    assert "/static/js/autocomplete.js" in body
    assert "/static/css/_autocomplete.css" in body


def test_autocomplete_static_assets_are_served():
    """The listener is a static file under the admin static mount (no inline script)."""
    client = _client()

    js = client.get("/admin/static/js/autocomplete.js")
    css = client.get("/admin/static/css/_autocomplete.css")

    assert js.status_code == 200
    assert "hyperadminPopupCreated" in js.text
    assert css.status_code == 200
    assert ".ha-popup-root" in css.text


def test_popup_listener_inserts_option_and_closes_modal():
    """The listener selects the created row, fires change and empties the popup root."""
    source = STATIC_JS.read_text()

    assert 'addEventListener("hyperadminPopupCreated"' in source
    assert "select[data-ha-autocomplete-select]" in source
    assert "option.selected = true" in source
    assert 'new Event("change", { bubbles: true })' in source
    assert 'root.innerHTML = ""' in source


def test_update_form_preselects_current_value():
    """The edit form keeps the stored key selected in the autocomplete select."""
    client = _client()
    created = client.post("/admin/acproduct", data={"name": "Lamp", "supplier_id": "1"})
    assert created.status_code in (200, 303)

    body = client.get("/admin/acproduct/1/edit").text

    assert '<option value="1" selected>Acme</option>' in body


# ---------------------------------------------------------------------------
# Widget factory and lazy (non-preload) fields
# ---------------------------------------------------------------------------


def test_relation_widget_factory_picks_class():
    """relation_widget() returns the autocomplete subclass only when enabled."""
    single = relation_widget(choices_url="/u", choices=[], preload=True, multiple=False)
    multi = relation_widget(choices_url="/u", choices=[], preload=True, multiple=True)
    ac_single = relation_widget(
        choices_url="/u",
        choices=[],
        preload=True,
        multiple=False,
        autocomplete=True,
        popup_url="/p",
    )
    ac_multi = relation_widget(
        choices_url="/u", choices=[], preload=False, multiple=True, autocomplete=True
    )

    assert type(single) is RelationSelectWidget
    assert type(multi) is RelationMultiSelectWidget
    assert isinstance(ac_single, AutocompleteWidget)
    assert ac_single.template_path == "widgets/autocomplete.html"
    assert ac_single.popup_url == "/p"
    assert ac_single.multiple is False
    # Subclassing keeps the multi-value form extraction working for M2M.
    assert isinstance(ac_multi, AutocompleteMultiWidget)
    assert isinstance(ac_multi, RelationMultiSelectWidget)
    assert ac_multi.multiple is True
    assert ac_multi.popup_url is None


def test_multi_autocomplete_template_renders_multiple_select():
    """The shared template renders a multi-select (no blank option) for M2M."""
    admin = Admin(app=FastAPI(), settings=HyperAdminSettings(create_tables=False))
    widget = AutocompleteMultiWidget(
        choices_url="/admin/x/choices/tags",
        choices=[{"value": "3", "label": "Red", "selected": True}],
    )
    field = SimpleNamespace(name="tags", label="Tags", required=False, help_text=None, errors=None)

    html = admin.templates.get_template("widgets/autocomplete.html").render(
        field=field, widget=widget
    )

    assert 'multiple aria-multiselectable="true"' in html
    assert '<option value="">' not in html
    assert '<option value="3" selected>Red</option>' in html
    assert 'data-testid="autocomplete-add-tags"' not in html


def test_lazy_autocomplete_keeps_stored_key_selectable(monkeypatch: pytest.MonkeyPatch):
    """A non-preloaded autocomplete still carries the stored key until the user searches."""
    real_classify = relations_module.classify_field

    def lazy_classify(field_info: Any, model: Any) -> Any:
        meta = real_classify(field_info, model)
        if isinstance(meta, SelectFieldMeta) and meta.choices_source == "relation":
            return SelectFieldMeta(choices_source="relation", preload=False, multiple=False)
        return meta

    monkeypatch.setattr(relations_module, "classify_field", lazy_classify)
    monkeypatch.setattr(base_module, "classify_field", lazy_classify)
    client = _client()
    client.post("/admin/acproduct", data={"name": "Lamp", "supplier_id": "1"})

    body = client.get("/admin/acproduct/1/edit").text

    assert '<option value="1" selected>AcSupplier (1)</option>' in body


def test_popup_payload_matches_listener_contract():
    """The popup POST's HX-Trigger carries the target/id/label the listener reads."""
    client = _client()

    response = client.post(
        "/admin/acsupplier/create-popup", data={"target": "supplier_id", "name": "Beta"}
    )

    payload = json.loads(response.headers["HX-Trigger"])["hyperadminPopupCreated"]
    assert payload["target"] == "supplier_id"
    assert isinstance(payload["id"], int)
    assert payload["label"] == "Beta"


def test_add_button_omitted_without_add_permission(monkeypatch: pytest.MonkeyPatch):
    """The "+" button needs the user's add permission on the related model."""

    async def deny_add(self: Any, request: Any, codename: str) -> bool:
        return not codename.startswith("add_acsupplier")

    client = _client()
    monkeypatch.setattr(dynamic_module.DynamicModelView, "_has_permission", deny_add)

    body = client.get("/admin/acproduct/create").text

    assert 'data-testid="autocomplete-supplier_id"' in body
    assert 'data-testid="autocomplete-add-supplier_id"' not in body


# ---------------------------------------------------------------------------
# Label consistency (ac-fix): preload == search results == popup-created option
# ---------------------------------------------------------------------------

_DEPENDENT = {
    "variant_id": RelationDependency(depends_on="supplier_id", placeholder="Pick a supplier first")
}


def _widget_select(body: str, field: str) -> str:
    """The rendered ``<select>`` of the autocomplete widget for ``field``."""
    return body.split(f'data-field="{field}"', 1)[1].split("</select>", 1)[0]


def _popup_label(response: Any) -> str:
    return json.loads(response.headers["HX-Trigger"])["hyperadminPopupCreated"]["label"]


def test_preloaded_options_use_relation_display():
    """
    Scenario: preloaded options use the relation display template
      Given relation_display has supplier_id = "{name} — {city}"
      When  the create form renders the supplier_id widget
      Then  its preloaded option reads "Acme — Paris", exactly like a search result
    """
    client = _client(relation_display={"supplier_id": "{name} — {city}"})

    body = client.get("/admin/acproduct/create").text
    searched = client.get("/admin/acproduct/choices/supplier?q=ac").text

    assert '<option value="1">Acme — Paris</option>' in _widget_select(body, "supplier_id")
    assert '<option value="1">Acme — Paris</option>' in searched


def test_preloaded_options_use_relation_display_keyed_by_relationship():
    """relation_display keyed by the relationship name labels the preload too."""
    client = _client(relation_display={"supplier": lambda s: s.name.upper()})

    body = client.get("/admin/acproduct/create").text

    assert '<option value="1">ACME</option>' in _widget_select(body, "supplier_id")


def test_dependent_preload_is_empty_while_parent_unset():
    """
    Scenario: dependent FK with no parent value preloads nothing
      Given relation_filters has variant_id depends_on supplier_id
      When  the create form renders before a supplier is chosen
      Then  the variant_id select holds only the blank option
      And   the search input shows the configured placeholder
    """
    client = _client(relation_filters=_DEPENDENT)

    body = client.get("/admin/acproduct/create").text

    select = _widget_select(body, "variant_id")
    assert '<option value="">---------</option>' in select
    assert '<option value="7"' not in select
    assert 'placeholder="Pick a supplier first"' in select
    # The independent supplier widget still preloads.
    assert '<option value="1">Acme</option>' in _widget_select(body, "supplier_id")


def test_dependent_preload_filters_by_parent_value():
    """
    Scenario: dependent FK preloads only the parent's rows
      Given variants "Blue" (supplier 1) and "Red" (supplier 2)
      And   a product with supplier_id=1 and variant_id=7
      When  the edit form renders
      Then  the variant_id select lists "Blue" selected and not "Red"
    """
    client = _client(relation_filters=_DEPENDENT)
    client.post("/admin/acsupplier", data={"name": "Other", "city": "Lyon"})
    client.post("/admin/acvariant", data={"name": "Red", "supplier_id": "2"})
    client.post("/admin/acproduct", data={"name": "Lamp", "supplier_id": "1", "variant_id": "7"})

    body = client.get("/admin/acproduct/1/edit").text

    select = _widget_select(body, "variant_id")
    assert '<option value="7" selected>Blue</option>' in select
    assert "Red" not in select


def test_dependent_preload_after_validation_error_uses_submitted_parent():
    """A re-rendered create form filters the dependent preload by the submitted parent value."""
    client = _client(relation_filters=_DEPENDENT)
    client.post("/admin/acsupplier", data={"name": "Other", "city": "Lyon"})
    client.post("/admin/acvariant", data={"name": "Red", "supplier_id": "2"})

    # ``name`` is required: the form re-renders with the posted values.
    body = client.post("/admin/acproduct", data={"supplier_id": "2"}).text

    select = _widget_select(body, "variant_id")
    assert "Red" in select
    assert "Blue" not in select


def test_popup_label_follows_source_form_relation_display():
    """
    Scenario: popup-created option uses the parent form's display template
      Given the Product admin has relation_display supplier_id = "{name} — {city}"
      And   the Supplier admin has no relation_display
      When  the popup opened from the product form creates supplier "Zed" in "Utrecht"
      Then  the HX-Trigger label is "Zed — Utrecht", matching the widget's other options
    """
    client = _client(relation_display={"supplier_id": "{name} — {city}"})

    response = client.post(
        "/admin/acsupplier/create-popup?source=acproduct",
        data={"target": "supplier_id", "name": "Zed", "city": "Utrecht"},
    )

    assert response.status_code == 200
    assert _popup_label(response) == "Zed — Utrecht"


@pytest.mark.parametrize("target", ["supplier_id", "supplier"])
def test_popup_label_follows_source_relationship_key(target: str):
    """The source's relation_display may be keyed by the relationship name; callables work."""
    client = _client(relation_display={"supplier": lambda s: s.name.upper()})

    response = client.post(
        "/admin/acsupplier/create-popup?source=acproduct", data={"target": target, "name": "Zed"}
    )

    assert _popup_label(response) == "ZED"


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("", "supplier_id"),  # no source: nothing to borrow a template from
        ("nosuchmodel", "supplier_id"),  # unknown source slug
        ("acproduct", "variant_id"),  # the source field does not point at this model
        ("acvariant", "supplier_id"),  # the source admin has no relation_display
    ],
)
def test_popup_label_falls_back_to_display_name(source: str, target: str):
    """Without a usable source template the popup label is the plain display name."""
    client = _client(relation_display={"supplier_id": "{name} — {city}"})

    response = client.post(
        f"/admin/acsupplier/create-popup?source={source}",
        data={"target": target, "name": "Zed", "city": "Utrecht"},
    )

    assert _popup_label(response) == "Zed"


def test_popup_label_ignores_unmapped_source_model():
    """A registered source that SQLAlchemy cannot inspect falls back to the display name."""

    class Plain:
        pass

    client = _client(relation_display={"supplier_id": "{name} — {city}"})
    site._registry[Plain] = AcSupplierAdmin

    response = client.post(
        "/admin/acsupplier/create-popup?source=plain",
        data={"target": "supplier_id", "name": "Zed", "city": "Utrecht"},
    )

    assert _popup_label(response) == "Zed"


def test_popup_form_posts_back_with_source():
    """The popup form keeps ``source`` on its POST URL, including after a validation error."""
    client = _client()

    opened = client.get("/admin/acsupplier/create-popup?target=supplier_id&source=acproduct").text
    # ``name`` is required: the fragment re-renders with errors.
    rerendered = client.post(
        "/admin/acsupplier/create-popup?source=acproduct", data={"target": "supplier_id"}
    ).text

    assert "/admin/acsupplier/create-popup?source=acproduct" in opened
    assert "/admin/acsupplier/create-popup?source=acproduct" in rerendered
    assert 'name="target" value="supplier_id"' in rerendered


def test_popup_form_keeps_source_after_integrity_error(monkeypatch: pytest.MonkeyPatch):
    """A database constraint failure re-renders the popup without losing ``source``."""
    from sqlalchemy.exc import IntegrityError

    async def failing_create(self: Any, data: dict[str, Any]) -> Any:
        raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed: name"))

    client = _client()
    monkeypatch.setattr(SQLModelAdapter, "create", failing_create)

    response = client.post(
        "/admin/acsupplier/create-popup?source=acproduct",
        data={"target": "supplier_id", "name": "Zed"},
    )

    assert response.status_code == 200
    assert "HX-Trigger" not in response.headers
    assert "/admin/acsupplier/create-popup?source=acproduct" in response.text
    assert 'data-testid="popup-form"' in response.text
