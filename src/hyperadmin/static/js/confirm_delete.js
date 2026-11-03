/*
 * HyperAdmin shared delete confirmation (st-v059-list-03).
 *
 * One <dialog id="ha-confirm-delete"> (components/confirm_delete_dialog.html,
 * included once by base.html) serves every delete button on the list, detail
 * and edit pages. A trigger is any element with
 *
 *     data-ha-confirm-delete="<DELETE url>" data-ha-label="<object name>"
 *
 * Clicking it dispatches a bubbling `ha-confirm-delete` event with
 * {url, label}; other scripts may dispatch the same event to reuse the dialog.
 * The dialog opens with showModal() (focus trap, Esc and backdrop come from the
 * browser), says "Delete <label>?" and focuses Cancel. Confirm sends the DELETE
 * with htmx.ajax, sourced from the dialog so the CSRF header from
 * <body hx-headers> applies; the server's HX-Redirect then reloads the page and
 * a refusal (403 / 404 / 409) arrives as the existing error toast. Closing, by
 * Cancel, Esc or after the request, returns focus to the trigger.
 *
 * Delegated on document: rows swapped in by HTMX need no initialisation.
 */

(function () {
  "use strict";

  if (window.hyperadminConfirmDelete) return;
  window.hyperadminConfirmDelete = true;

  var DIALOG_ID = "ha-confirm-delete";
  var state = { url: null, opener: null };

  function dialog() {
    return document.getElementById(DIALOG_ID);
  }

  function setBusy(box, busy) {
    var ok = box.querySelector("[data-ha-confirm-ok]");
    if (!ok) return;
    ok.disabled = busy;
    if (busy) ok.setAttribute("aria-busy", "true");
    else ok.removeAttribute("aria-busy");
  }

  function open(url, label, opener) {
    var box = dialog();
    if (!box || box.open || !url) return;
    state.url = url;
    state.opener = opener;
    var title = box.querySelector("#" + DIALOG_ID + "-title");
    var template = box.getAttribute("data-title-template");
    if (title && template) title.textContent = template.replace("{name}", label || "");
    setBusy(box, false);
    box.showModal();
    var cancel = box.querySelector("[data-ha-confirm-cancel]");
    if (cancel) cancel.focus();
  }

  function close() {
    var box = dialog();
    if (box && box.open) box.close();
  }

  function confirm() {
    var box = dialog();
    if (!box || !state.url || !window.htmx) return;
    setBusy(box, true);
    var done = function () {
      close();
    };
    window.htmx.ajax("DELETE", state.url, { source: box, swap: "none" }).then(done, done);
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target || !target.closest) return;
    var trigger = target.closest("[data-ha-confirm-delete]");
    if (trigger) {
      event.preventDefault();
      trigger.dispatchEvent(
        new CustomEvent("ha-confirm-delete", {
          bubbles: true,
          detail: {
            url: trigger.getAttribute("data-ha-confirm-delete"),
            label: trigger.getAttribute("data-ha-label") || "",
          },
        })
      );
      return;
    }
    if (!target.closest("#" + DIALOG_ID)) return;
    if (target.closest("[data-ha-confirm-cancel]")) close();
    else if (target.closest("[data-ha-confirm-ok]")) confirm();
  });

  document.addEventListener("ha-confirm-delete", function (event) {
    var detail = event.detail || {};
    var opener = event.target instanceof HTMLElement ? event.target : document.activeElement;
    open(detail.url, detail.label, opener);
  });

  // "close" fires for Cancel, Esc and after the request alike.
  document.addEventListener(
    "close",
    function (event) {
      if (!event.target || event.target.id !== DIALOG_ID) return;
      var opener = state.opener;
      state.url = null;
      state.opener = null;
      setBusy(event.target, false);
      if (opener && opener.isConnected && typeof opener.focus === "function") opener.focus();
    },
    true
  );
})();
