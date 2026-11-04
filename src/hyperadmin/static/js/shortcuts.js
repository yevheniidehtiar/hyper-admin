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
 * The last registered match wins. Loaded with defer, before palette.js.
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
})();
