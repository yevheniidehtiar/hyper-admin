/*
 * HyperAdmin request failure alert (st-ux-erp-03).
 *
 * htmx swaps nothing on a 5xx answer or a network failure, so a form submit
 * that fails that way looked like it saved. This shows an error toast in the
 * toast region instead (role=alert, focused), and leaves the form and the
 * user's edits untouched. The strings are translated server side and passed
 * on this script tag: data-title, data-message, data-offline, data-close.
 * Refused requests (403 / 404 / 409) keep their server-rendered toast.
 */
(function () {
  'use strict';
  var script = document.currentScript;
  var text = function (key, fallback) {
    return (script && script.getAttribute('data-' + key)) || fallback;
  };

  function region() {
    var box = document.querySelector('.ha-toast-container');
    if (!box) {
      box = document.createElement('div');
      box.className = 'ha-toast-container';
      box.setAttribute('aria-live', 'polite');
      box.setAttribute('aria-atomic', 'true');
      document.body.appendChild(box);
    }
    return box;
  }

  function show(message) {
    var old = document.querySelector('[data-testid="request-error-toast"]');
    if (old) old.remove();
    var toast = document.createElement('div');
    toast.className = 'ha-toast ha-alert-error';
    toast.setAttribute('role', 'alert');
    toast.setAttribute('tabindex', '-1');
    toast.setAttribute('data-testid', 'request-error-toast');
    var body = document.createElement('div');
    body.className = 'ha-toast-body';
    var title = document.createElement('strong');
    title.className = 'ha-alert-title';
    title.textContent = text('title', 'Not saved');
    var detail = document.createElement('span');
    detail.textContent = message;
    body.appendChild(title);
    body.appendChild(detail);
    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'ha-toast-close';
    close.setAttribute('aria-label', text('close', 'Close'));
    close.textContent = '×';
    close.addEventListener('click', function () { toast.remove(); });
    toast.appendChild(body);
    toast.appendChild(close);
    region().appendChild(toast);
    toast.focus();
  }

  var unloading = false;
  window.addEventListener('beforeunload', function () { unloading = true; });

  // Only writes (post/put/patch/delete) can fail to "save". Reads (search,
  // sort, pagination, pickers, polling) and components that render their own
  // error (data-ha-own-errors, or a handler that called preventDefault) are
  // left alone.
  function isSave(e) {
    if (unloading || e.defaultPrevented) return false;
    var cfg = e.detail && e.detail.requestConfig;
    var verb = String((cfg && cfg.verb) || 'get').toLowerCase();
    if (verb === 'get') return false;
    var el = e.detail && e.detail.elt;
    return !(el && el.closest && el.closest('[data-ha-own-errors]'));
  }

  document.addEventListener('htmx:responseError', function (e) {
    var xhr = e.detail && e.detail.xhr;
    if (isSave(e) && xhr && xhr.status >= 500) show(text('message', 'The server could not save this record. Your edits are kept.'));
  });
  document.addEventListener('htmx:sendError', function (e) {
    if (isSave(e)) show(text('offline', 'Could not reach the server. Your edits are kept.'));
  });
  document.addEventListener('htmx:timeout', function (e) {
    if (isSave(e)) show(text('offline', 'Could not reach the server. Your edits are kept.'));
  });
})();
