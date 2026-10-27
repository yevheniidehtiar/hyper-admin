/*
 * HyperAdmin FK/M2M autocomplete — behaviour for widgets/autocomplete.html
 * (H6, v0.5.5; design: components/AutocompleteStates).
 *
 * Everything is delegated on `document`, so widgets swapped in by HTMX need
 * no initialisation. Without this script the widget still works: the native
 * select carries the value and the search input swaps the choices fragment
 * into it. This adds:
 *
 *  - the dependent-field waiting state: while the parent field is empty the
 *    search input, the select and the "+" button are disabled and the select
 *    lists nothing; when the parent changes the field clears itself, says so
 *    in its help text and `role="status"`, and htmx fetches again;
 *  - the clear button (shown while the input has text) and the status
 *    announcements ("Searching", "3 results", "No results");
 *  - the inline-create popup: the "+" button loads the popup into
 *    #ha-popup-root. A successful popup POST answers with an empty body and
 *    `HX-Trigger: {"hyperadminPopupCreated": {"target", "id", "label"}}`;
 *    this inserts the new row into the target field's select, selects it,
 *    fires `change` (so dependent widgets re-fetch) and closes the popup.
 *    Escape, the backdrop and any [data-ha-popup-close] element close it too;
 *    focus moves into the dialog when it opens and back to the "+" on close.
 */

(function () {
  "use strict";

  var WIDGET = ".ha-autocomplete";
  var BLANK_OPTION = '<option value="">---------</option>';
  var lastTrigger = null;

  function popupRoot() {
    return document.getElementById("ha-popup-root");
  }

  function closePopup() {
    var root = popupRoot();
    if (!root || !root.firstElementChild) return;
    root.innerHTML = "";
    if (lastTrigger && document.contains(lastTrigger)) lastTrigger.focus();
    lastTrigger = null;
  }

  function targetSelect(name) {
    var selects = document.querySelectorAll("select[data-ha-autocomplete-select]");
    for (var i = 0; i < selects.length; i++) {
      if (selects[i].name === name) return selects[i];
    }
    return null;
  }

  function parts(widget) {
    return {
      widget: widget,
      combobox: widget.querySelector(".ha-combobox"),
      input: widget.querySelector(".ha-autocomplete__search"),
      select: widget.querySelector("select[data-ha-autocomplete-select]"),
      add: widget.querySelector(".ha-autocomplete__add"),
      clear: widget.querySelector("[data-ha-autocomplete-clear]"),
      status: widget.querySelector('[role="status"]'),
      help: widget.parentNode ? widget.parentNode.querySelector("[data-ha-autocomplete-help]") : null
    };
  }

  function parentField(widget) {
    var name = widget.getAttribute("data-depends-on");
    if (!name) return null;
    var form = widget.closest("form") || document;
    return form.querySelector("[name='" + name + "']");
  }

  function parentValue(widget) {
    var parent = parentField(widget);
    return parent ? parent.value : "";
  }

  function setStatus(w, text) {
    if (w.status) w.status.textContent = text;
  }

  function setHelp(w, key) {
    if (!w.help) return;
    w.help.textContent = w.help.getAttribute("data-text-" + key) || "";
  }

  function setWaiting(w, waiting) {
    if (!w.combobox) return;
    w.combobox.classList.toggle("is-waiting", waiting);
    if (w.input) w.input.disabled = waiting;
    if (w.add) w.add.disabled = waiting;
    if (w.select) {
      w.select.disabled = waiting;
      if (waiting && !w.select.multiple) w.select.innerHTML = BLANK_OPTION;
      if (waiting && w.select.multiple) w.select.innerHTML = "";
    }
  }

  function syncClear(w) {
    if (w.clear && w.input) w.clear.hidden = !w.input.value;
  }

  function resultCount(w) {
    if (!w.select) return 0;
    var n = 0;
    for (var i = 0; i < w.select.options.length; i++) {
      if (w.select.options[i].value !== "") n++;
    }
    return n;
  }

  function announceResults(w) {
    var n = resultCount(w);
    if (n === 0) {
      setStatus(w, w.widget.getAttribute("data-text-no-results") || "No results");
      return;
    }
    var template = w.widget.getAttribute("data-text-results") || "{count} results";
    setStatus(w, template.replace("{count}", String(n)));
  }

  function init(widget) {
    if (widget.hasAttribute("data-ha-autocomplete-ready")) return;
    widget.setAttribute("data-ha-autocomplete-ready", "");
    var w = parts(widget);
    syncClear(w);
    if (widget.hasAttribute("data-depends-on")) {
      setWaiting(w, parentValue(widget) === "");
      setHelp(w, "waiting");
    }
  }

  function initAll(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var widgets = scope.querySelectorAll(WIDGET);
    for (var i = 0; i < widgets.length; i++) init(widgets[i]);
  }

  function dependents(parent) {
    var form = parent.closest("form") || document;
    var found = [];
    var widgets = form.querySelectorAll(WIDGET + "[data-depends-on='" + parent.name + "']");
    for (var i = 0; i < widgets.length; i++) found.push(widgets[i]);
    return found;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initAll(document);
    });
  } else {
    initAll(document);
  }

  document.addEventListener("htmx:load", function (event) {
    initAll(event.target);
  });

  // Capture phase: runs before htmx's own `change from:[name=parent]` listener,
  // so the dependent input is enabled (or blanked) before the re-fetch fires.
  document.addEventListener(
    "change",
    function (event) {
      var parent = event.target;
      if (!parent || !parent.name) return;
      var children = dependents(parent);
      for (var i = 0; i < children.length; i++) {
        var w = parts(children[i]);
        if (w.input) w.input.value = "";
        if (w.select && !w.select.multiple) w.select.value = "";
        setWaiting(w, parent.value === "");
        syncClear(w);
        setHelp(w, "cleared");
        if (w.help) setStatus(w, w.help.getAttribute("data-text-cleared-status") || "");
      }
    },
    true
  );

  document.addEventListener("input", function (event) {
    var input = event.target;
    if (!input.closest || !input.classList.contains("ha-autocomplete__search")) return;
    var widget = input.closest(WIDGET);
    if (widget) syncClear(parts(widget));
  });

  document.addEventListener("htmx:beforeRequest", function (event) {
    var input = event.target;
    if (!input.closest || !input.classList.contains("ha-autocomplete__search")) return;
    var widget = input.closest(WIDGET);
    if (!widget) return;
    setStatus(parts(widget), widget.getAttribute("data-text-searching") || "Searching");
  });

  // The choices fragment replaces every <option>; remember the chosen one so a search
  // that no longer lists it does not silently change the submitted value.
  document.addEventListener("htmx:beforeSwap", function (event) {
    var select = event.target;
    if (!select.hasAttribute || !select.hasAttribute("data-ha-autocomplete-select")) return;
    var chosen = select.selectedOptions && select.selectedOptions[0];
    select.haChosen =
      chosen && chosen.value !== "" ? { value: chosen.value, label: chosen.textContent } : null;
  });

  document.addEventListener("htmx:afterSwap", function (event) {
    var select = event.target;
    if (!select.closest || !select.hasAttribute("data-ha-autocomplete-select")) return;
    var widget = select.closest(WIDGET);
    if (!widget) return;
    announceResults(parts(widget));
    var chosen = select.haChosen;
    select.haChosen = null;
    if (select.multiple) return;
    var found = null;
    for (var i = 0; chosen && i < select.options.length; i++) {
      if (select.options[i].value === chosen.value) found = select.options[i];
    }
    select.insertAdjacentHTML("afterbegin", BLANK_OPTION);
    if (found) {
      found.selected = true;
    } else if (chosen) {
      var kept = document.createElement("option");
      kept.value = chosen.value;
      kept.textContent = chosen.label;
      kept.selected = true;
      select.options[0].after(kept);
    } else {
      select.selectedIndex = 0;
    }
  });

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
    var target = event.target;
    if (!target.closest) return;

    var clear = target.closest("[data-ha-autocomplete-clear]");
    if (clear) {
      var widget = clear.closest(WIDGET);
      var w = parts(widget);
      if (w.input) {
        w.input.value = "";
        w.input.focus();
        w.input.dispatchEvent(new Event("search", { bubbles: true }));
      }
      syncClear(w);
      return;
    }

    var add = target.closest(".ha-autocomplete__add");
    if (add) lastTrigger = add;

    var root = popupRoot();
    if (!root) return;
    if (target === root || target.closest("[data-ha-popup-close]")) {
      closePopup();
    }
  });

  // The popup dialog takes focus when it is swapped in (WCAG: focus moves into a modal).
  document.addEventListener("htmx:afterSwap", function (event) {
    var root = popupRoot();
    if (!root || event.target !== root) return;
    var dialog = root.querySelector('[role="dialog"]');
    if (!dialog) return;
    var first = dialog.querySelector("input:not([type=hidden]), select, textarea, button");
    (first || dialog).focus();
  });

  document.addEventListener("keydown", function (event) {
    var root = popupRoot();
    if (event.key === "Escape" && root && root.firstElementChild) closePopup();
  });
})();
