/*
 * HyperAdmin reports dashboard: reordering the cards (docs/specs/dashboard-builder.md).
 *
 * Loaded only when the page renders reorder controls. Two ways to reorder:
 *
 * - Drag a card by its handle (SortableJS, vendored next to this file). On drop the
 *   keys are posted in DOM order to the grid's data-layout-url; if the server refuses,
 *   the cards go back where they were and an error toast says so.
 * - "Move up" / "Move down" buttons: plain POST forms the server answers with the new
 *   grid (hx-post). After the swap this script puts the focus back on the same button
 *   of the moved card and announces the new position in the live region. Without this
 *   script the buttons still work as form posts.
 *
 * The strings are translated server side and passed on this script tag: data-title,
 * data-save-error, data-move-error, data-close and data-moved (with __title__,
 * __position__ and __total__ placeholders).
 */
(function () {
  'use strict';
  var script = document.currentScript;
  var text = function (key, fallback) {
    return (script && script.getAttribute('data-' + key)) || fallback;
  };

  function grid() {
    return document.querySelector('[data-dashboard-grid]');
  }

  function cards(el) {
    return Array.prototype.slice.call(el.querySelectorAll(':scope > [data-widget-key]'));
  }

  function keys(el) {
    return cards(el).map(function (card) { return card.getAttribute('data-widget-key'); });
  }

  function card(el, key) {
    return cards(el).filter(function (c) { return c.getAttribute('data-widget-key') === key; })[0];
  }

  function announce(message) {
    var live = document.querySelector('[data-dashboard-live]');
    if (live && message) live.textContent = message;
  }

  // The error toast, in the admin's toast region (as request_errors.js builds its own).
  function toast(message) {
    var box = document.querySelector('.ha-toast-container');
    if (!box) {
      box = document.createElement('div');
      box.className = 'ha-toast-container';
      box.setAttribute('aria-live', 'polite');
      box.setAttribute('aria-atomic', 'true');
      document.body.appendChild(box);
    }
    var old = document.querySelector('[data-testid="dashboard-error-toast"]');
    if (old) old.remove();
    var el = document.createElement('div');
    el.className = 'ha-toast ha-alert-error';
    el.setAttribute('role', 'alert');
    el.setAttribute('tabindex', '-1');
    el.setAttribute('data-testid', 'dashboard-error-toast');
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
    close.addEventListener('click', function () { el.remove(); });
    el.appendChild(body);
    el.appendChild(close);
    box.appendChild(el);
    el.focus();
  }

  // The first card cannot move up and the last cannot move down.
  function markEdges(el) {
    var all = cards(el);
    all.forEach(function (c, index) {
      var up = c.querySelector('button[name="direction"][value="up"]');
      var down = c.querySelector('button[name="direction"][value="down"]');
      if (up) index === 0 ? up.setAttribute('aria-disabled', 'true') : up.removeAttribute('aria-disabled');
      if (down) index === all.length - 1 ? down.setAttribute('aria-disabled', 'true') : down.removeAttribute('aria-disabled');
    });
  }

  function restore(el, order) {
    order.forEach(function (key) {
      var c = card(el, key);
      if (c) el.appendChild(c);
    });
    markEdges(el);
  }

  // Order to go back to if the save in flight is refused.
  var pending = null;

  function save(el, previous, movedKey) {
    pending = previous;
    markEdges(el);
    var order = keys(el);
    var moved = card(el, movedKey);
    var heading = moved && moved.querySelector('h2');
    announce(text('moved', '')
      .replace('__title__', heading ? heading.textContent : movedKey)
      .replace('__position__', String(order.indexOf(movedKey) + 1))
      .replace('__total__', String(order.length)));
    window.htmx.ajax('POST', el.getAttribute('data-layout-url'), {
      source: el,
      swap: 'none',
      values: { widgets: order }
    });
  }

  function init() {
    var el = grid();
    if (!el || !window.Sortable || window.Sortable.get(el)) return;
    el.querySelectorAll('[data-drag-handle]').forEach(function (handle) {
      handle.removeAttribute('hidden');
    });
    var before = keys(el);
    window.Sortable.create(el, {
      draggable: '[data-widget-key]',
      handle: '[data-drag-handle]',
      animation: 150,
      ghostClass: 'ha-dash-card--ghost',
      chosenClass: 'ha-dash-card--chosen',
      onStart: function () { before = keys(el); },
      onEnd: function (event) {
        if (keys(el).join('\n') === before.join('\n')) return;
        save(el, before, event.item.getAttribute('data-widget-key'));
      }
    });
  }

  // After a move button swapped the grid: same button focused again, position announced.
  function afterSwap() {
    var el = grid();
    if (!el) return;
    init();
    var key = el.getAttribute('data-moved-key');
    if (!key) return;
    var moved = card(el, key);
    var direction = el.getAttribute('data-moved-direction');
    var button = moved && moved.querySelector('button[name="direction"][value="' + direction + '"]');
    if (button) button.focus();
    announce(el.getAttribute('data-announce'));
    el.removeAttribute('data-moved-key');
  }

  document.addEventListener('htmx:afterSettle', afterSwap);

  // A refused or failed write from the grid: undo a drag, and say what happened.
  document.addEventListener('htmx:afterRequest', function (e) {
    var detail = e.detail || {};
    var el = grid();
    var verb = String((detail.requestConfig && detail.requestConfig.verb) || 'get').toLowerCase();
    if (!el || verb === 'get' || !detail.elt || !el.contains(detail.elt)) return;
    var previous = detail.elt === el ? pending : null;
    if (detail.elt === el) pending = null;
    if (detail.successful) return;
    if (previous) {
      restore(el, previous);
      toast(text('save-error', 'The order could not be saved. The cards are back where they were.'));
    } else {
      toast(text('move-error', 'The card could not be moved.'));
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
