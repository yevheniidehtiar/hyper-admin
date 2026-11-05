/*
 * HyperAdmin unsaved-changes guard and Cmd/Ctrl+S (st-v059-kbd-01).
 *
 * A form carrying data-ha-guard="<leave prompt>" (the model form, unless
 * AdminOptions(warn_unsaved_changes=False), and the popup create form) turns
 * dirty on its first input or change event, inline formset rows included.
 * While any guarded form on the page is dirty:
 *   - leaving the page (link, reload, closing the tab) asks via beforeunload;
 *   - an htmx request whose target would replace the form (a boosted link,
 *     an hx-get on an ancestor) asks with the form's prompt first.
 * Saving never asks: a form's own request is not guarded, and a 2xx answer
 * (the server's HX-Redirect after a save) marks that form clean before htmx
 * navigates. A 422 re-render keeps it dirty.
 * Delete from the edit page asks once: the delete dialog is the confirmation.
 * Its successful DELETE marks every form clean, so the redirect that follows
 * does not ask again; Cancel or a refused delete (403/404/409) keeps the edits
 * guarded.
 * mod+s submits the open popup form, else the model form, with requestSubmit()
 * (validation and htmx run as for Save); it does nothing while a modal
 * <dialog> is open and leaves the browser's Save alone on pages without one.
 */
(function () {
  'use strict';
  var GUARD = 'form[data-ha-guard]';

  function forms() { return [].slice.call(document.querySelectorAll(GUARD)); }
  function dirty() { return forms().filter(function (f) { return f.haDirty; })[0]; }
  function clean(f) { f.haDirty = false; }

  function touch(e) {
    var f = e.target.closest && e.target.closest(GUARD);
    if (f) f.haDirty = true;
  }
  document.addEventListener('input', touch);
  document.addEventListener('change', touch);
  // A plain (non-htmx) submit leaves the page on purpose; htmx cancels its own.
  document.addEventListener('submit', function (e) {
    if (!e.defaultPrevented && e.target.matches(GUARD)) clean(e.target);
  });

  window.addEventListener('beforeunload', function (e) {
    if (!dirty()) return;
    e.preventDefault();
    e.returnValue = '';
  });

  document.addEventListener('htmx:confirm', function (e) {
    var d = e.detail;
    var f = dirty();
    if (!f || !d.target || !d.target.contains(f) || f.contains(d.elt)) return;
    e.preventDefault();
    if (window.confirm(f.getAttribute('data-ha-guard'))) {
      forms().forEach(clean);
      d.issueRequest(true);
    }
  });

  document.addEventListener('htmx:beforeOnLoad', function (e) {
    var s = e.detail.elt;
    if (e.detail.xhr.status > 299) return;
    if (s.matches(GUARD)) clean(s);
    else if (s.closest('#ha-confirm-delete')) forms().forEach(clean);
  });

  if (window.haShortcuts) {
    window.haShortcuts.register({
      keys: 'mod+s',
      scope: 'form',
      description: 'Save',
      handler: function () {
        var f = document.querySelector('#ha-popup-root form') || document.querySelector('[data-testid="model-form"]');
        if (!f) return false;
        if (!document.querySelector('dialog[open]')) f.requestSubmit();
      }
    });
  }
})();
