"""Unit tests for the AutocompleteStates / Combobox design port (#664, v0.5.5).

The autocomplete widget, the create popup and their CSS and script follow
``docs/design/system/components/AutocompleteStates`` (built on Combobox).
Reuses the fixture app of :mod:`tests.unit.test_autocomplete_widget`.
"""

from __future__ import annotations

import pytest

from hyperadmin.core.options import RelationDependency
from hyperadmin.core.registry import site
from tests.unit.test_autocomplete_widget import STATIC_JS, _client

STATIC_CSS = STATIC_JS.parent.parent / "css"


@pytest.fixture(autouse=True)
def _cleanup_registry():
    site._registry = {}
    yield
    site._registry = {}


def test_widget_carries_the_combobox_design_markup():
    """
    Scenario: the autocomplete widget follows the AutocompleteStates design
      When  the create form renders a FK field
      Then  the search input sits in a combobox control with a status region
      And   the "+" is an icon button named "Add <field>" that opens a dialog
    """
    body = _client().get("/admin/acproduct/create").text
    widget = body.split('data-field="supplier_id"', 1)[1].split("</select>", 1)[0]

    assert 'class="ha-combobox"' in widget
    assert 'role="status"' in widget
    assert 'aria-describedby="supplier_id-status"' in widget
    assert 'placeholder="Search supplier id"' in widget
    assert 'aria-label="Clear supplier id"' in widget
    # The label points at the search input; the select keeps the field's name.
    assert 'for="supplier_id"' in body
    assert 'id="supplier_id-select"' in widget
    assert 'aria-label="Supplier id"' in widget

    add = body.split('data-testid="autocomplete-add-supplier_id"', 1)[0].rsplit("<button", 1)[1]
    assert 'aria-label="Add supplier id"' in add
    assert 'aria-haspopup="dialog"' in add
    assert "ha-btn--icon" in add


def test_dependent_widget_renders_waiting_copy_for_the_script():
    """A dependent field explains itself and carries the cleared/waiting copy as data."""
    client = _client(relation_filters={"variant_id": RelationDependency(depends_on="supplier_id")})
    body = client.get("/admin/acproduct/create").text
    group = body.split('data-field="variant_id"', 1)[1].split("</p>", 1)[0]

    assert 'data-depends-on="supplier_id"' in group
    assert 'placeholder="Choose a supplier first"' in group
    assert 'data-text-waiting="Pick the supplier above to list its variant id options."' in group
    assert 'data-text-cleared="Cleared because the supplier changed."' in group
    assert 'aria-describedby="variant_id-status variant_id-help"' in group


def test_popup_form_is_the_design_system_dialog():
    """The create popup is a labelled dialog with head, body and foot, and "Save and select"."""
    body = _client().get("/admin/acsupplier/create-popup?target=supplier_id").text

    assert 'role="dialog"' in body
    assert 'aria-labelledby="popup-form-title"' in body
    assert ">Add acsupplier</h2>" in body
    assert "Saving selects it in the supplier field." in body
    assert 'aria-label="Close"' in body
    assert "data-ha-popup-close" in body
    assert 'data-testid="popup-form-submit">Save and select</button>' in body
    assert 'hx-target="closest .ha-dialog"' in body


def test_forms_css_ports_the_autocomplete_and_dialog_classes():
    """The design's classes ship in _forms.css; the slot stylesheet only keeps the slot."""
    forms = (STATIC_CSS / "_forms.css").read_text()
    slot = (STATIC_CSS / "_autocomplete.css").read_text()

    for selector in (
        ".ha-autocomplete {",
        ".ha-combobox__control",
        ".ha-combobox__tools",
        ".ha-combobox.is-waiting",
        ".ha-dialog {",
        ".ha-dialog__head",
        ".ha-dialog__foot",
    ):
        assert selector in forms, selector
    assert ".ha-popup-root > .ha-dialog" in slot
    assert ".ha-autocomplete {" not in slot
    assert ".ha-autocomplete__" not in slot


def test_script_drives_the_waiting_state_and_announcements():
    """autocomplete.js owns the dependent waiting state, the clear button and the status text."""
    source = STATIC_JS.read_text()

    assert 'classList.toggle("is-waiting", waiting)' in source
    assert "data-ha-autocomplete-clear" in source
    assert "data-text-searching" in source
    assert 'addEventListener("htmx:afterSwap"' in source
    assert "data-text-cleared-status" in source
