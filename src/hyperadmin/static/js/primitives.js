/*
 * HyperAdmin UI primitives — behaviour for the design-system disclosures
 * (components/menu.html, popover.html), tooltips and banners.
 *
 * Everything is delegated on `document`, so markup swapped in by HTMX needs
 * no initialisation and the script may load before or after Alpine. Without
 * it a <details class="ha-layer"> still opens, closes and submits; this adds:
 *
 *  - one open layer at a time; a click or focus outside closes it;
 *  - Esc closes and returns focus to the trigger (<summary>);
 *  - menus: focus moves to the first item on open, Arrow keys / Home / End
 *    move between items, picking an item closes the menu; aria-disabled items
 *    stay focusable but do nothing;
 *  - popovers (role="dialog"): focus moves into the dialog, [data-ha-popup-close]
 *    closes it;
 *  - the popup flips up (.ha-popup--up) or to the end (.ha-popup--end) when it
 *    would leave the viewport;
 *  - tooltips: Esc hides an open .ha-tip without moving focus (WCAG 1.4.13);
 *  - [data-ha-dismiss] removes the closest .ha-banner.
 */

(function () {
  "use strict";

  if (window.hyperadminPrimitives) return;
  window.hyperadminPrimitives = true;

  var LAYER = "details.ha-layer";
  var ITEM = ".ha-menu__item";

  function openLayers() {
    return document.querySelectorAll(LAYER + "[open]");
  }

  function closeLayer(layer, restoreFocus) {
    if (!layer || !layer.open) return;
    layer.open = false;
    var summary = layer.querySelector(":scope > summary");
    if (restoreFocus && summary) summary.focus();
  }

  function closeOthers(except) {
    var layers = openLayers();
    for (var i = 0; i < layers.length; i++) {
      if (layers[i] !== except) closeLayer(layers[i], false);
    }
  }

  function popupOf(layer) {
    return layer.querySelector(":scope > .ha-popup");
  }

  function menuItems(popup) {
    var all = popup.querySelectorAll(ITEM);
    var items = [];
    for (var i = 0; i < all.length; i++) {
      if (!all[i].hidden) items.push(all[i]);
    }
    return items;
  }

  function placePopup(layer) {
    var popup = popupOf(layer);
    if (!popup || popup.classList.contains("ha-popup--static")) return;
    popup.classList.remove("ha-popup--up");
    var rect = popup.getBoundingClientRect();
    var viewportH = window.innerHeight || document.documentElement.clientHeight;
    var viewportW = window.innerWidth || document.documentElement.clientWidth;
    var trigger = layer.getBoundingClientRect();
    if (rect.bottom > viewportH && trigger.top > viewportH - trigger.bottom) {
      popup.classList.add("ha-popup--up");
    }
    if (!popup.hasAttribute("data-ha-align")) {
      var rtl = getComputedStyle(popup).direction === "rtl";
      var overflows = rtl ? rect.left < 0 : rect.right > viewportW;
      popup.classList.toggle("ha-popup--end", overflows);
    }
  }

  function focusInto(layer) {
    var popup = popupOf(layer);
    if (!popup) return;
    if (popup.classList.contains("ha-menu")) {
      var items = menuItems(popup);
      if (items.length) items[0].focus();
      return;
    }
    if (popup.getAttribute("role") === "dialog") {
      if (!popup.hasAttribute("tabindex")) popup.setAttribute("tabindex", "-1");
      popup.focus();
    }
  }

  // <details> fires "toggle" without bubbling: listen in the capture phase.
  document.addEventListener(
    "toggle",
    function (event) {
      var layer = event.target;
      if (!layer.matches || !layer.matches(LAYER)) return;
      if (!layer.open) return;
      closeOthers(layer);
      placePopup(layer);
      focusInto(layer);
    },
    true
  );

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target.closest) return;

    var dismiss = target.closest("[data-ha-dismiss]");
    if (dismiss) {
      var banner = dismiss.closest(".ha-banner");
      if (banner) banner.remove();
      return;
    }

    var layer = target.closest(LAYER);
    if (!layer) {
      closeOthers(null);
      return;
    }
    if (target.closest("[data-ha-popup-close]")) {
      event.preventDefault();
      closeLayer(layer, true);
      return;
    }
    var item = target.closest(ITEM);
    if (!item || !layer.contains(item)) return;
    if (item.getAttribute("aria-disabled") === "true") {
      event.preventDefault();
      return;
    }
    // a toggle item (aria-pressed) keeps the menu open; anything else closes it
    if (!item.hasAttribute("aria-pressed")) closeLayer(layer, false);
  });

  document.addEventListener("focusin", function (event) {
    var target = event.target;
    if (!target.closest) return;
    var layers = openLayers();
    for (var i = 0; i < layers.length; i++) {
      if (!layers[i].contains(target)) closeLayer(layers[i], false);
    }
  });

  document.addEventListener("keydown", function (event) {
    var target = event.target;
    if (!target.closest) return;

    if (event.key === "Escape") {
      var tip = target.closest(".ha-tip");
      if (tip) {
        tip.classList.add("is-dismissed");
        return;
      }
      var open = target.closest(LAYER + "[open]");
      if (open) {
        event.preventDefault();
        closeLayer(open, true);
      }
      return;
    }

    var layer = target.closest(LAYER);
    if (!layer) return;
    var popup = popupOf(layer);
    if (!popup || !popup.classList.contains("ha-menu")) return;

    var summary = layer.querySelector(":scope > summary");
    if (target === summary && !layer.open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      event.preventDefault();
      layer.open = true; // the toggle handler focuses the first item
      return;
    }

    var items = menuItems(popup);
    if (!items.length) return;
    var index = items.indexOf(target.closest(ITEM));
    var next = -1;
    if (event.key === "ArrowDown") next = index < items.length - 1 ? index + 1 : 0;
    else if (event.key === "ArrowUp") next = index > 0 ? index - 1 : items.length - 1;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = items.length - 1;
    if (next < 0) return;
    event.preventDefault();
    items[next].focus();
  });

  // a dismissed tooltip comes back the next time its trigger is left and re-entered
  document.addEventListener("focusout", function (event) {
    var tip = event.target.closest && event.target.closest(".ha-tip");
    if (tip) tip.classList.remove("is-dismissed");
  });
  document.addEventListener(
    "pointerleave",
    function (event) {
      if (event.target.classList && event.target.classList.contains("ha-tip")) {
        event.target.classList.remove("is-dismissed");
      }
    },
    true
  );
})();
