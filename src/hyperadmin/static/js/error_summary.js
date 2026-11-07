/*
 * HyperAdmin form error summary (st-ux-erp-06).
 *
 * The summary rendered by components/error_summary.html takes focus when the
 * page loads with it, and after an htmx swap puts a fresh one on screen. A link
 * in it focuses the field it names instead of only scrolling to it.
 */
(function () {
  'use strict';
  var SUMMARY = '[data-testid="error-summary"]';

  function focusSummary() {
    var el = document.querySelector(SUMMARY);
    if (el) { el.focus(); }
  }

  document.addEventListener('click', function (e) {
    var link = e.target.closest && e.target.closest('a[data-ha-error-link]');
    if (!link) { return; }
    var field = document.getElementById((link.getAttribute('href') || '').slice(1));
    if (!field) { return; }
    e.preventDefault();
    field.focus();
    field.scrollIntoView({ block: 'center' });
  });
  // Only the form's own swap moves focus: a field's htmx validation, an
  // autocomplete or an inline-row add settling must not pull focus away.
  document.addEventListener('htmx:afterSettle', function (evt) {
    var t = (evt.detail && evt.detail.target) || evt.target;
    if (t && t.id && /-form-body$/.test(t.id)) { focusSummary(); }
  });
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', focusSummary);
  } else {
    focusSummary();
  }
})();
