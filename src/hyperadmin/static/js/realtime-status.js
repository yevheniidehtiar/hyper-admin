/*
 * HyperAdmin real-time status widget.
 *
 * Opens one SSE stream and one WebSocket on page load, exposes
 * `window.__rt = { state, restart }` for E2E assertions, and reconnects
 * with exponential backoff + jitter when either transport drops.
 *
 * The MVP carries no business payload — this file is responsible only for
 * lifecycle correctness and the navbar status dot.
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
        h.onopen = function () {
          cb.onOpen();
          if (presence) presence.attach(h);
        };
        h.onclose = function () {
          if (presence) presence.detach();
          cb.onClose();
        };
        h.onmessage = function (event) { if (presence) presence.onMessage(event); };
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
