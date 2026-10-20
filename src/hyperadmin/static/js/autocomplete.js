/*
 * HyperAdmin FK/M2M autocomplete — inline-create popup listener (H6, v0.5.5).
 *
 * The "+" button of an autocomplete widget loads the create popup into
 * #ha-popup-root. A successful popup POST answers with an empty body and
 * `HX-Trigger: {"hyperadminPopupCreated": {"target", "id", "label"}}`: this
 * listener inserts the new row into the target field's select, selects it,
 * fires `change` (so dependent widgets re-fetch) and closes the popup.
 * Escape, the backdrop and any [data-ha-popup-close] element close it too.
 */

(function () {
  "use strict";

  function popupRoot() {
    return document.getElementById("ha-popup-root");
  }

  function closePopup() {
    var root = popupRoot();
    if (root) root.innerHTML = "";
  }

  function targetSelect(name) {
    var selects = document.querySelectorAll("select[data-ha-autocomplete-select]");
    for (var i = 0; i < selects.length; i++) {
      if (selects[i].name === name) return selects[i];
    }
    return null;
  }

  document.addEventListener("hyperadminPopupCreated", function (event) {
    var detail = event.detail || {};
    var select = targetSelect(String(detail.target));
    if (select && detail.id !== null && detail.id !== undefined) {
      var value = String(detail.id);
      var option = null;
      for (var i = 0; i < select.options.length; i++) {
        if (select.options[i].value === value) option = select.options[i];
      }
      if (!option) {
        option = document.createElement("option");
        option.value = value;
        select.appendChild(option);
      }
      option.textContent = String(detail.label);
      option.selected = true;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    closePopup();
  });

  document.addEventListener("click", function (event) {
    var root = popupRoot();
    if (!root || !event.target.closest) return;
    if (event.target === root || event.target.closest("[data-ha-popup-close]")) {
      closePopup();
    }
  });

  document.addEventListener("keydown", function (event) {
    var root = popupRoot();
    if (event.key === "Escape" && root && root.firstElementChild) closePopup();
  });
})();
