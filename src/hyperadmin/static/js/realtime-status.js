/*
 * HyperAdmin real-time status widget.
 *
 * Opens one SSE stream and one WebSocket on page load, exposes
 * `window.__rt = { state, restart }` for E2E assertions, and reconnects
 * with exponential backoff + jitter when either transport drops.
 *
 * Besides the lifecycle and the navbar status dot it carries two features
 * over the shared WebSocket: the presence banner on edit pages and live CRUD
 * notifications on list pages (see `Notifications` below).
 */

(function () {
  "use strict";

  var STATES = { CONNECTED: "connected", RECONNECTING: "reconnecting", DISCONNECTED: "disconnected" };
  var CLASS_MAP = {
    connected: "is-connected",
    reconnecting: "is-reconnecting",
    disconnected: "is-disconnected",
  };
  var BASE_DELAY_MS = 250;
  var MAX_DELAY_MS = 10000;

  function adminPrefix() {
    var brand = document.querySelector(".ha-navbar-brand");
    if (brand) {
      var href = brand.getAttribute("href") || "/";
      return href.replace(/\/+$/, "");
    }
    return "";
  }

  function backoffDelay(attempt) {
    var raw = Math.min(MAX_DELAY_MS, BASE_DELAY_MS * Math.pow(2, attempt));
    var jitter = 0.7 + Math.random() * 0.6; // ±30 %
    return Math.round(raw * jitter);
  }

  function setDot(state) {
    var dot = document.querySelector('[data-testid="realtime-status"]');
    if (!dot) return;
    dot.classList.remove("is-connected", "is-reconnecting", "is-disconnected");
    dot.classList.add(CLASS_MAP[state] || CLASS_MAP.disconnected);
  }

  /*
   * Presence banner on the edit page (components/presence_banner.html).
   * Sends {"type":"presence","model","pk","mode"} over the shared WebSocket on
   * open and every HEARTBEAT_MS, a "leave" frame on unload, and renders the
   * roster frames the server pushes back (own user dropped). With no banner
   * on the page every entry point is a no-op.
   */
  var PRESENCE_HEARTBEAT_MS = 8000;
  var PRESENCE_MAX_NAMES = 3;

  function Presence(el) {
    this.el = el;
    this.ws = null;
    this.timer = null;
  }
  Presence.prototype.frame = function (mode) {
    var d = this.el.dataset;
    return JSON.stringify({ type: "presence", model: d.presenceModel, pk: d.presencePk, mode: mode });
  };
  Presence.prototype.send = function (mode) {
    if (this.ws && this.ws.readyState === 1) this.ws.send(this.frame(mode));
  };
  Presence.prototype.attach = function (ws) {
    var self = this;
    self.ws = ws;
    self.send(self.el.dataset.presenceMode);
    if (self.timer) clearInterval(self.timer);
    self.timer = setInterval(function () { self.send(self.el.dataset.presenceMode); }, PRESENCE_HEARTBEAT_MS);
  };
  Presence.prototype.detach = function () {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.ws = null;
    this.render([]);
  };
  Presence.prototype.leave = function () {
    this.send("leave");
  };
  Presence.prototype.onMessage = function (event) {
    if (typeof event.data !== "string") return;
    var msg;
    try { msg = JSON.parse(event.data); } catch (e) { return; }
    var d = this.el.dataset;
    if (!msg || msg.type !== "presence" || msg.model !== d.presenceModel || String(msg.pk) !== d.presencePk) return;
    var others = (msg.users || []).filter(function (u) { return String(u.user_id) !== d.presenceSelf; });
    this.render(others);
  };
  Presence.prototype.render = function (others) {
    var el = this.el;
    var text = el.querySelector("[data-presence-text]");
    if (!others.length) {
      el.hidden = true;
      if (text) text.textContent = "";
      return;
    }
    var d = el.dataset;
    var editing = others.some(function (u) { return u.mode === "editing"; });
    var names = others.slice(0, PRESENCE_MAX_NAMES).map(function (u) { return u.display_name; });
    var extra = others.length - names.length;
    var joined = names.join(", ");
    if (extra > 0) joined += " " + d.msgMore.replace("{count}", extra);
    var key = (editing ? "msgEditing" : "msgViewing") + (others.length > 1 ? "Many" : "One");
    if (text) text.textContent = d[key].replace("{names}", joined);
    el.classList.toggle("ha-banner--warning", editing);
    el.classList.toggle("ha-banner--info", !editing);
    el.hidden = false;
  };

  /*
   * Live CRUD notifications on list pages (components/table.html root
   * `#model-list[data-realtime-model]`, strings in components/toast.html).
   *
   * On socket open (and every reconnect) it sends {"type":"subscribe","model"}
   * for each hook on the page and only those. `crud` frames are buffered per
   * model and settled after a 300 ms debounce, so a burst becomes one
   * re-fetch and one toast:
   *   - hidden tab: mark stale, flush once when the tab is visible again;
   *   - work in progress (inline cell editor open, bulk rows ticked): show a
   *     "List changed: refresh" pill that flushes on click;
   *   - otherwise re-fetch the current URL into #model-list through htmx.
   * With no hook on the page, or no socket, every entry point is a no-op.
   */
  var NOTIFY_DEBOUNCE_MS = 300;
  var TOAST_MS = 4000;
  var FLASH_MS = 1500;
  var NOTIFY_MAX_WAIT_MS = 2000;
  var NOTIFY_MAX_EVENTS = 100;
  var PLURAL_FALLBACK = "other";

  function Notifications() {
    this.ws = null;
    this.subscribed = {};
    this.buffers = {};
    this.pill = null;
  }
  Notifications.prototype.hooks = function () {
    var out = {};
    document.querySelectorAll("[data-realtime-model]").forEach(function (el) {
      out[el.getAttribute("data-realtime-model")] = el;
    });
    return out;
  };
  Notifications.prototype.sendFrame = function (type, model) {
    if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify({ type: type, model: model }));
  };
  Notifications.prototype.sync = function () {
    if (!this.ws) return;
    var hooks = this.hooks();
    for (var model in hooks) {
      if (!this.subscribed[model]) {
        this.subscribed[model] = true;
        this.sendFrame("subscribe", model);
      }
    }
    for (var known in this.subscribed) {
      if (!hooks[known]) {
        delete this.subscribed[known];
        this.sendFrame("unsubscribe", known);
      }
    }
  };
  Notifications.prototype.attach = function (ws) {
    this.ws = ws;
    this.subscribed = {};
    this.sync();
  };
  Notifications.prototype.detach = function () {
    this.ws = null;
    this.subscribed = {};
  };
  Notifications.prototype.onMessage = function (event) {
    if (typeof event.data !== "string") return;
    var msg;
    try { msg = JSON.parse(event.data); } catch (e) { return; }
    if (!msg || msg.type !== "crud" || typeof msg.model !== "string") return;
    if (!this.hooks()[msg.model]) return;
    document.body.dispatchEvent(new CustomEvent("ha:crud", { detail: msg }));
    var buf = this.buffers[msg.model] || (this.buffers[msg.model] = { events: [], timer: null, stale: false });
    buf.events.push(msg);
    if (buf.events.length > NOTIFY_MAX_EVENTS) buf.events.shift();
    var self = this;
    var now = Date.now();
    if (!buf.first) buf.first = now;
    if (buf.timer) clearTimeout(buf.timer);
    // Debounce, but never wait longer than NOTIFY_MAX_WAIT_MS from the first buffered event.
    var wait = Math.max(0, Math.min(NOTIFY_DEBOUNCE_MS, buf.first + NOTIFY_MAX_WAIT_MS - now));
    buf.timer = setTimeout(function () {
      buf.timer = null;
      self.settle(msg.model);
    }, wait);
  };
  Notifications.prototype.workInProgress = function () {
    return !!document.querySelector(".ha-inline-editor, input[name=ids][form=bulk-action-form]:checked");
  };
  Notifications.prototype.settle = function (model) {
    var buf = this.buffers[model];
    if (!buf || !buf.events.length) return;
    if (document.visibilityState === "hidden") {
      buf.stale = true;
      return;
    }
    if (this.workInProgress()) {
      buf.stale = true;
      this.showPill();
      return;
    }
    this.flush(model);
  };
  Notifications.prototype.onVisible = function () {
    if (document.visibilityState === "hidden") return;
    for (var model in this.buffers) {
      if (this.buffers[model].stale) this.settle(model);
    }
  };
  Notifications.prototype.flush = function (model) {
    var buf = this.buffers[model];
    var events = buf.events;
    buf.events = [];
    buf.first = 0;
    buf.stale = false;
    this.hidePillIfIdle();
    var self = this;
    var done = function () {
      self.sync();
      self.feedback(model, events);
    };
    if (!window.htmx) {
      done();
      return;
    }
    var req = window.htmx.ajax("GET", window.location.href, { target: "#model-list", swap: "outerHTML" });
    if (req && typeof req.then === "function") req.then(done, done);
    else done();
  };
  Notifications.prototype.flushAll = function () {
    for (var model in this.buffers) {
      if (this.buffers[model].events.length) this.flush(model);
    }
  };
  Notifications.prototype.strings = function () {
    var el = document.querySelector("[data-realtime-strings]");
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  };
  Notifications.prototype.feedback = function (model, events) {
    var strings = this.strings();
    var selfEl = document.querySelector("[data-realtime-self]");
    var me = selfEl ? selfEl.getAttribute("data-realtime-self") : "";
    var others = events.filter(function (e) {
      return me === "" || e.actor_id === null || e.actor_id === undefined || String(e.actor_id) !== me;
    });
    var root = this.hooks()[model];
    this.flashRows(others.filter(function (e) { return e.action === "updated"; }));
    if (!strings || !root) return;
    var toggled = others.filter(function (e) { return e.action === "created" || e.action === "deleted"; });
    if (!toggled.length) return;
    var label = root.getAttribute("data-realtime-label") || model;
    var labelPlural = root.getAttribute("data-realtime-label-plural") || label;
    var actors = {};
    toggled.forEach(function (e) {
      var key = e.actor_id === null || e.actor_id === undefined ? "" : String(e.actor_id);
      actors[key] = e.actor || strings.someone;
    });
    var keys = Object.keys(actors);
    var text;
    if (toggled.length === 1) {
      text = fill(strings[toggled[0].action], { actor: actors[keys[0]], model: label, pk: toggled[0].pk });
    } else {
      var who = keys.length === 1 ? actors[keys[0]] : fill(pluralForm(strings.people, keys.length), { count: keys.length });
      text = fill(pluralForm(strings.summary, toggled.length), { actor: who, count: toggled.length, model: labelPlural });
    }
    showToast(text);
  };
  Notifications.prototype.flashRows = function (updated) {
    if (!updated.length) return;
    var pks = {};
    updated.forEach(function (e) { pks[String(e.pk)] = true; });
    document.querySelectorAll("tr[data-pk]").forEach(function (row) {
      if (!pks[row.getAttribute("data-pk")]) return;
      row.classList.add("ha-row-flash");
      row.setAttribute("data-realtime-flash", "true");
      setTimeout(function () {
        row.classList.remove("ha-row-flash");
        row.removeAttribute("data-realtime-flash");
      }, FLASH_MS);
    });
  };
  Notifications.prototype.showPill = function () {
    if (this.pill && this.pill.isConnected) return;
    var strings = this.strings();
    if (!strings) return;
    var self = this;
    var pill = document.createElement("button");
    pill.type = "button";
    pill.className = "ha-rt-pill";
    pill.setAttribute("data-testid", "realtime-refresh-pill");
    pill.textContent = strings.pill;
    pill.addEventListener("click", function () {
      pill.remove();
      self.pill = null;
      self.flushAll();
    });
    toastContainer().appendChild(pill);
    this.pill = pill;
  };
  Notifications.prototype.hidePillIfIdle = function () {
    for (var model in this.buffers) {
      if (this.buffers[model].events.length) return;
    }
    if (this.pill) {
      this.pill.remove();
      this.pill = null;
    }
  };

  function fill(template, values) {
    return String(template).replace(/\{(\w+)\}/g, function (whole, key) {
      return Object.prototype.hasOwnProperty.call(values, key) ? String(values[key]) : whole;
    });
  }

  function pluralForm(forms, n) {
    var category = PLURAL_FALLBACK;
    try { category = new Intl.PluralRules(document.documentElement.lang || undefined).select(n); } catch (e) { /* keep fallback */ }
    return forms[category] || forms[PLURAL_FALLBACK];
  }

  function toastContainer() {
    var box = document.querySelector(".ha-toast-container");
    if (!box) {
      box = document.createElement("div");
      box.className = "ha-toast-container";
      box.setAttribute("aria-live", "polite");
      box.setAttribute("aria-atomic", "true");
      document.body.appendChild(box);
    }
    return box;
  }

  function showToast(text) {
    var tpl = document.querySelector("[data-realtime-toast-template]");
    if (!tpl) return;
    var toast = tpl.content.firstElementChild.cloneNode(true);
    toast.querySelector("[data-toast-text]").textContent = text;
    var close = toast.querySelector(".ha-toast-close");
    if (close) close.addEventListener("click", function () { toast.remove(); });
    toastContainer().appendChild(toast);
    setTimeout(function () { toast.remove(); }, TOAST_MS);
  }

  var notifications = new Notifications();

  var presence = null;

  function Channel(opts) {
    this.name = opts.name;
    this.open = opts.open;             // () => handle
    this.close = opts.close;           // (handle) => void
    this.bind = opts.bind;             // (handle, { onOpen, onClose }) => void
    this.handle = null;
    this.connected = false;
    this.attempt = 0;
    this.timer = null;
    this.disposed = false;
  }
  Channel.prototype.start = function (parent) {
    var self = this;
    if (self.disposed) return;
    try {
      self.handle = self.open();
    } catch (e) {
      self.scheduleReconnect(parent);
      return;
    }
    self.bind(self.handle, {
      onOpen: function () {
        self.connected = true;
        self.attempt = 0;
        parent.refreshState();
      },
      onClose: function () {
        self.connected = false;
        self.handle = null;
        if (self.disposed) return;
        parent.refreshState();
        self.scheduleReconnect(parent);
      },
    });
  };
  Channel.prototype.scheduleReconnect = function (parent) {
    var self = this;
    if (self.disposed) return;
    self.attempt += 1;
    var delay = backoffDelay(self.attempt);
    if (self.timer) clearTimeout(self.timer);
    self.timer = setTimeout(function () {
      self.timer = null;
      self.start(parent);
    }, delay);
  };
  Channel.prototype.dispose = function () {
    this.disposed = true;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.handle) {
      try { this.close(this.handle); } catch (e) { /* ignore */ }
      this.handle = null;
    }
  };

  function RealtimeClient() {
    var prefix = adminPrefix();
    var sseUrl = prefix + "/realtime/sse";
    var wsScheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    var wsUrl = wsScheme + "//" + window.location.host + prefix + "/realtime/ws";

    this.state = STATES.DISCONNECTED;
    this.sse = new Channel({
      name: "sse",
      open: function () { return new EventSource(sseUrl); },
      close: function (h) { h.close(); },
      bind: function (h, cb) {
        h.onopen = cb.onOpen;
        h.onerror = cb.onClose;
      },
    });
    this.ws = new Channel({
      name: "ws",
      open: function () { return new WebSocket(wsUrl); },
      close: function (h) { try { h.close(); } catch (e) { /* ignore */ } },
      bind: function (h, cb) {
        // A superseded socket (after restart()) must not detach or feed the new one.
        h.onopen = function () {
          cb.onOpen();
          if (presence) presence.attach(h);
          notifications.attach(h);
        };
        h.onclose = function () {
          if (presence && presence.ws === h) presence.detach();
          if (notifications.ws === h) notifications.detach();
          cb.onClose();
        };
        h.onmessage = function (event) {
          if (notifications.ws !== h) return;
          if (presence) presence.onMessage(event);
          notifications.onMessage(event);
        };
        h.onerror = function () { /* onclose follows */ };
      },
    });
  }
  RealtimeClient.prototype.start = function () {
    var self = this;
    self.sse.start(self);
    self.ws.start(self);
    window.addEventListener("beforeunload", function () { self.dispose(); });
    window.addEventListener("pagehide", function () { self.dispose(); });
  };
  RealtimeClient.prototype.refreshState = function () {
    if (this.sse.connected && this.ws.connected) {
      this.state = STATES.CONNECTED;
    } else if (this.sse.handle || this.ws.handle || this.sse.timer || this.ws.timer) {
      this.state = STATES.RECONNECTING;
    } else {
      this.state = STATES.DISCONNECTED;
    }
    setDot(this.state);
  };
  RealtimeClient.prototype.restart = function () {
    this.dispose();
    var fresh = new RealtimeClient();
    fresh.start();
    window.__rt = fresh;
  };
  RealtimeClient.prototype.dispose = function () {
    if (presence) {
      presence.leave();
      presence.detach();
    }
    this.sse.dispose();
    this.ws.dispose();
    this.state = STATES.DISCONNECTED;
    setDot(this.state);
  };

  function bootstrap() {
    var banner = document.querySelector('[data-testid="presence-banner"]');
    presence = banner ? new Presence(banner) : null;
    document.addEventListener("visibilitychange", function () { notifications.onVisible(); });
    document.body.addEventListener("htmx:load", function () { notifications.sync(); });
    var client = new RealtimeClient();
    window.__rt = client;
    setDot(STATES.RECONNECTING);
    client.refreshState = (function (orig) {
      return function () { orig.call(this); };
    })(RealtimeClient.prototype.refreshState);
    client.start();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
})();
