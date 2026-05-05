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
        h.onopen = cb.onOpen;
        h.onclose = cb.onClose;
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
    this.sse.dispose();
    this.ws.dispose();
    this.state = STATES.DISCONNECTED;
    setDot(this.state);
  };

  function bootstrap() {
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
