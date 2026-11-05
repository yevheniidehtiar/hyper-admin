/*
 * HyperAdmin keyboard shortcut registry: window.haShortcuts (st-v059-nav-04).
 *
 *   haShortcuts.register({keys, description, handler, scope, single}) -> unregister()
 *     keys        "mod+k", "mod+s", "shift+enter", "/", "j", "?". "mod" is Cmd on
 *                 macOS and Ctrl elsewhere; modifiers in any order.
 *     description shown by the "?" overlay; scope groups it there ("global", "list").
 *     handler(event) runs on keydown; return false to pass the key on (no
 *                 preventDefault, the next match is tried).
 *     single      true for a single-key shortcut (WCAG 2.1.4): ignored while focus
 *                 is in an input, textarea, select or contenteditable, while a
 *                 modifier is held, and while localStorage "ha-shortcuts" is "off".
 *                 Modifier shortcuts are always on.
 *   haShortcuts.list()          registered entries, in registration order.
 *   haShortcuts.enabled()       whether single-key shortcuts are on.
 *   haShortcuts.setEnabled(on)  the off switch (stored in localStorage "ha-shortcuts").
 *   haShortcuts.isMac           true when "mod" is Cmd.
 * The last registered match wins. Loaded with defer, before palette.js and
 * form_guard.js (mod+s). Also holds the "?" overlay and the list keys (kbd-02).
 */
(function () {
  'use strict';
  var STORE = 'ha-shortcuts';
  var isMac = /Mac|iP(hone|ad|od)/.test(navigator.platform || navigator.userAgent);
  var entries = [];

  function combo(mod, alt, shift, key) {
    // "?" or "/" depend on the layout's shift state, so shift only counts for letters and named keys.
    if (key.length === 1 && !/[a-z]/.test(key)) shift = false;
    return (mod ? 'mod+' : '') + (alt ? 'alt+' : '') + (shift ? 'shift+' : '') + key;
  }

  function parse(keys) {
    var parts = keys.toLowerCase().split('+');
    var key = parts.pop();
    return combo(parts.indexOf('mod') > -1, parts.indexOf('alt') > -1, parts.indexOf('shift') > -1, key);
  }

  function enabled() {
    try { return localStorage.getItem(STORE) !== 'off'; } catch (e) { return true; }
  }

  function setEnabled(on) {
    try { localStorage.setItem(STORE, on ? 'on' : 'off'); } catch (e) { /* private mode */ }
  }

  function editable(el) {
    return !!(el && el.closest && el.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"])'));
  }

  function register(entry) {
    var item = Object.assign({ scope: 'global', single: false }, entry, { combo: parse(entry.keys) });
    entries.push(item);
    return function () { entries.splice(entries.indexOf(item), 1); };
  }

  document.addEventListener('keydown', function (event) {
    if (event.defaultPrevented || event.isComposing || !event.key) return;
    var mod = isMac ? event.metaKey : event.ctrlKey;
    var pressed = combo(mod, event.altKey, event.shiftKey, event.key.toLowerCase());
    var held = event.ctrlKey || event.metaKey || event.altKey;
    for (var i = entries.length - 1; i >= 0; i--) {
      var item = entries[i];
      if (item.combo !== pressed) continue;
      if (item.single && (held || editable(event.target) || !enabled())) continue;
      if (item.handler(event) !== false) {
        event.preventDefault();
        return;
      }
    }
  });

  window.haShortcuts = {
    register: register,
    list: function () { return entries.slice(); },
    enabled: enabled,
    setEnabled: setEnabled,
    isMac: isMac
  };

  // "?" (single key) and mod+/ (always on, the way back after turning single
  // keys off) open components/shortcuts_overlay.html (st-v059-kbd-02). It lists
  // every entry by scope and holds the off switch; focus returns on close.
  var dlg = document.getElementById('ha-shortcuts');
  if (dlg && dlg.showModal) {
    var L = JSON.parse(dlg.dataset.labels);
    var body = dlg.querySelector('[data-ha-shortcuts-list]');
    var sw = dlg.querySelector('[role="switch"]');
    var NAMES = isMac ? { mod: '\u2318', alt: '\u2325', shift: '\u21e7' } : { mod: 'Ctrl', alt: 'Alt', shift: 'Shift' };
    var opener;
    var add = function (tag, parent, text) {
      var e = parent.appendChild(document.createElement(tag));
      if (text) e.textContent = L[text] || text;
      return e;
    };
    var overlay = function () {
      if (dlg.open) return dlg.close();
      if (document.querySelector('dialog[open]')) return false;
      opener = document.activeElement;
      body.textContent = '';
      var lists = {};
      entries.forEach(function (it) {
        var dl = lists[it.scope];
        if (!dl) {
          var sec = add('section', body);
          add('h3', sec, it.scope);
          dl = lists[it.scope] = add('dl', sec);
        }
        // Alternatives for one action share a row: "? or Cmd /".
        var same = dl.haDesc === it.description;
        var dt = same ? dl.lastChild.previousSibling : add('dt', dl);
        if (same) add('span', dt, 'or');
        it.keys.split('+').forEach(function (k, i, all) {
          add('kbd', dt, NAMES[k] || (all[1] ? k.toUpperCase() : k)).className = 'ha-kbd';
        });
        if (!same) add('dd', dl, it.description);
        dl.haDesc = it.description;
      });
      sw.checked = enabled();
      dlg.showModal();
    };
    sw.addEventListener('change', function () { setEnabled(sw.checked); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
    dlg.addEventListener('close', function () { if (opener && opener.focus) opener.focus(); });
    register({ keys: '?', single: true, description: 'Show keyboard shortcuts', handler: overlay });
    register({ keys: 'mod+/', description: 'Show keyboard shortcuts', handler: overlay });
  }

  // "/" focuses the list search (moved from the inline handler in _base.html).
  register({
    keys: '/',
    single: true,
    scope: 'list',
    description: 'Focus search',
    handler: function () {
      var search = document.querySelector('[name="search"]');
      if (!search) return false;
      search.focus();
    }
  });

  // List pages: j/k move between row links (rows without one are skipped), Enter
  // opens the focused one natively, x toggles its bulk checkbox, c creates.
  if (document.getElementById('list-container')) {
    var LINK = '[data-testid="row-link"]';
    var row = function () {
      var a = document.activeElement;
      return a && a.closest && a.closest('[data-testid="list-row"]');
    };
    // find() returns the element to act on, or nothing to pass the key on. A
    // modal <dialog> (delete confirmation, palette, overlay) keeps the keys.
    var listKey = function (keys, description, find, act) {
      register({ keys: keys, single: true, scope: 'list', description: description, handler: function () {
        var t = !document.querySelector('dialog[open]') && find();
        if (!t) return false;
        t[act || 'click']();
      } });
    };
    var step = function (d) {
      return function () {
        var links = [].slice.call(document.querySelectorAll(LINK));
        var r = row();
        var i = r ? links.indexOf(r.querySelector(LINK)) : -1;
        return links[i < 0 ? (d > 0 ? 0 : links.length - 1) : Math.max(0, Math.min(links.length - 1, i + d))];
      };
    };
    listKey('j', 'Next row', step(1), 'focus');
    listKey('k', 'Previous row', step(-1), 'focus');
    listKey('x', 'Select row', function () {
      var r = row();
      return r && r.querySelector('input[name="ids"][data-testid="bulk-checkbox"]');
    });
    listKey('c', 'Create new', function () { return document.querySelector('[data-testid="create-link"]'); });
  }
})();
