/*
 * Command palette (st-v059-nav-04): Cmd/Ctrl+K, or the navbar trigger, opens
 * components/command_palette.html. Matching is client-side over the
 * permission-filtered #ha-nav-data island, so no request per keystroke.
 * Recent visits live in localStorage "ha-recent" (newest first, max 8); a page
 * records data.current, or <body data-ha-recent='{"label","url","kind"}'>.
 */
(function () {
  'use strict';
  var dlg = document.getElementById('ha-palette');
  var island = document.getElementById('ha-nav-data');
  if (!dlg || !island || !dlg.showModal) return;
  var data = JSON.parse(island.textContent);
  var L = JSON.parse(dlg.getAttribute('data-labels'));
  var input = dlg.querySelector('[role="combobox"]');
  var list = dlg.querySelector('[role="listbox"]');
  var empty = dlg.querySelector('.ha-palette__empty');
  var status = dlg.querySelector('[data-palette-status]');
  var RECENT = 'ha-recent';
  var SVG = 'http://www.w3.org/2000/svg';
  var items = [];
  var byKey = {};
  var options = [];
  var active = -1;
  var opener = null;

  data.groups.forEach(function (g) {
    g.items.forEach(function (it) { items.push(it); byKey[it.key] = it; });
  });

  function recents() {
    try {
      var r = JSON.parse(localStorage.getItem(RECENT));
      return Array.isArray(r) ? r : [];
    } catch (e) { return []; }
  }

  // Only pages under an item this user may open (the store is per browser, not per user).
  function allowed(r) {
    return r && r.url && items.some(function (it) {
      return r.url === it.url || r.url.indexOf(it.url + '/') === 0;
    });
  }

  (function record() {
    var cur = data.current;
    try {
      if (document.body.dataset.haRecent) cur = JSON.parse(document.body.dataset.haRecent);
      if (!cur || !cur.url) return;
      var rest = recents().filter(function (r) { return r && r.url !== cur.url; });
      localStorage.setItem(RECENT, JSON.stringify([cur].concat(rest).slice(0, 8)));
    } catch (e) { /* private mode: no recents */ }
  })();

  // Case- and accent-insensitive, one char per char so indices map back to the label.
  function fold(s) {
    return String(s).split('').map(function (c) {
      return c.normalize('NFD').charAt(0).toLowerCase().charAt(0);
    }).join('');
  }

  function subseq(s, q) {
    var marks = [];
    for (var i = 0, j = 0; i < s.length && j < q.length; i++) {
      if (s.charAt(i) === q.charAt(j)) { marks.push(i); j++; }
    }
    return marks.length === q.length ? marks : null;
  }

  function run(from, n) {
    var r = [];
    for (var i = from; i < from + n; i++) r.push(i);
    return r;
  }

  // [score, label marks] or null; lower scores rank first, a label prefix best.
  function match(it, q) {
    var label = fold(it.label);
    var at = label.indexOf(q);
    if (at === 0) return [0, run(0, q.length)];
    if (at > 0) return [label.charAt(at - 1) === ' ' ? 1 : 2, run(at, q.length)];
    var marks = subseq(label, q);
    if (marks) return [3, marks];
    var hay = fold(it.label + ' ' + it.group);
    if (hay.indexOf(q) > -1) return [4, []];
    return subseq(hay, q) ? [5, []] : null;
  }

  function el(tag, cls, attrs) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    for (var k in attrs || {}) e.setAttribute(k, attrs[k]);
    return e;
  }

  function icon(name) {
    var s = document.createElementNS(SVG, 'svg');
    var a = { 'class': 'ha-icon', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.5',
      'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' };
    for (var k in a) s.setAttribute(k, a[k]);
    var u = document.createElementNS(SVG, 'use');
    u.setAttribute('href', '#ha-pi-' + String(name).replace(/[^a-z0-9-]/g, ''));
    s.appendChild(u);
    return s;
  }

  function highlight(node, text, marks) {
    var on = {};
    marks.forEach(function (m) { on[m] = true; });
    for (var i = 0; i < text.length;) {
      var j = i;
      while (j < text.length && !!on[j] === !!on[i]) j++;
      var part = on[i] ? el('mark', 'ha-match') : document.createElement('span');
      part.textContent = text.slice(i, j);
      node.appendChild(part);
      i = j;
    }
  }

  function option(it, marks) {
    var o = el('div', 'ha-option', { role: 'option', id: 'ha-po-' + options.length,
      'aria-selected': 'false', 'data-testid': 'palette-result' });
    o.appendChild(icon(it.icon || 'clock'));
    var main = o.appendChild(el('span', 'ha-option__main'));
    highlight(main.appendChild(el('span', 'ha-option__label')), it.label, marks || []);
    if (it.group) main.appendChild(el('span', 'ha-option__meta')).textContent = it.group;
    if (local(it.create_url)) {
      o.appendChild(el('a', 'ha-palette__new', { href: local(it.create_url), tabindex: '-1' })).textContent = it.create_label;
    }
    o.haItem = it;
    options.push(o);
    return o;
  }

  function section(title, rows) {
    if (!rows.length) return;
    var g = list.appendChild(el('div', 'ha-palette__group', { role: 'group' }));
    var h = g.appendChild(el('div', 'ha-listbox__group', { role: 'presentation', id: 'ha-pg-' + list.children.length }));
    h.textContent = title;
    g.setAttribute('aria-labelledby', h.id);
    rows.forEach(function (r) { g.appendChild(option(r.it, r.marks)); });
  }

  function rows(its) { return its.map(function (it) { return { it: it }; }); }
  function kind(k) { return function (r) { return (r.it.kind === 'page') === (k === 'page'); }; }

  function move(i) {
    var old = options[active];
    if (old) { old.classList.remove('is-active'); old.setAttribute('aria-selected', 'false'); }
    active = i;
    var o = options[i];
    if (!o) return input.removeAttribute('aria-activedescendant');
    o.classList.add('is-active');
    o.setAttribute('aria-selected', 'true');
    input.setAttribute('aria-activedescendant', o.id);
    o.scrollIntoView({ block: 'nearest' });
  }

  function render() {
    var q = fold(input.value.trim());
    list.textContent = '';
    options = [];
    active = -1;
    if (!q) {
      section(L.pinned, rows(data.pins.map(function (k) { return byKey[k]; }).filter(Boolean)));
      section(L.recent, rows(recents().filter(allowed).map(function (r) {
        return { label: r.label, group: r.group || '', url: r.url, icon: 'clock' };
      })));
      var all = rows(items);
      section(L.models, all.filter(kind('model')));
      section(L.pages, all.filter(kind('page')));
    } else {
      var hits = [];
      items.forEach(function (it, i) {
        var m = match(it, q);
        if (m) hits.push({ it: it, score: m[0], marks: m[1], i: i });
      });
      hits.sort(function (a, b) { return a.score - b.score || a.i - b.i; });
      hits = hits.slice(0, 20);
      section(L.models, hits.filter(kind('model')));
      section(L.pages, hits.filter(kind('page')));
    }
    empty.hidden = options.length > 0;
    status.textContent = options.length ? L.results.replace('{n}', options.length) : L.none;
    move(options.length ? 0 : -1);
  }

  // Same-origin paths only, so a stored or injected url can never be javascript: or off-site.
  function local(url) {
    return typeof url === 'string' && /^\/(?![/\\])/.test(url) ? url : null;
  }

  function go(o, create) {
    if (!o) return;
    var it = o.haItem;
    var url = local(create && it.create_url ? it.create_url : it.url);
    if (url) window.location.assign(url);
  }

  function open(from) {
    if (dlg.open) return input.select();
    opener = from || document.activeElement;
    input.value = '';
    render();
    dlg.showModal();
    input.focus();
  }

  input.addEventListener('input', render);
  input.addEventListener('keydown', function (e) {
    var n = options.length;
    if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && n) {
      e.preventDefault();
      move((active + (e.key === 'ArrowDown' ? 1 : n - 1) + n) % n);
    } else if (e.key === 'Enter' && !e.isComposing) {
      e.preventDefault();
      go(options[active], e.shiftKey);
    }
  });
  list.addEventListener('click', function (e) {
    if (!e.target.closest('a')) go(e.target.closest('[role="option"]'));
  });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
  dlg.addEventListener('close', function () {
    if (opener && opener.focus) opener.focus();
    opener = null;
  });

  var mac = window.haShortcuts ? window.haShortcuts.isMac : /Mac/.test(navigator.platform);
  document.querySelectorAll('[data-ha-palette-open]').forEach(function (b) {
    b.hidden = false;
    b.setAttribute('aria-keyshortcuts', mac ? 'Meta+K' : 'Control+K');
    b.addEventListener('click', function () { open(b); });
  });
  if (mac) document.querySelectorAll('[data-ha-mod-k]').forEach(function (k) { k.textContent = '⌘K'; });
  if (window.haShortcuts) {
    window.haShortcuts.register({ keys: 'mod+k', description: 'Search', handler: function () {
      if (dlg.open) dlg.close(); else open();
    } });
  }
})();
