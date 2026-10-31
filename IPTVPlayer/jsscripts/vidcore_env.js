// E2iPlayer: environment for the vidcore/vidup/vidfast player chunks under QuickJS-ng (qjs --std).
// Loaded first (-I), then the site's own webpack chunks (-I each), then vidcore_run.js.
// Network goes through the parent process: "@@F <json>" on stdout, one JSON answer line on stdin.
"use strict";
(function () {
var G = globalThis, std = G.std, os = G.os;
var __out = function (s) { std.out.puts(s + "\n"); std.out.flush(); };

// ---------- anything we do not model: a callable, chainable dummy ----------
function anyProxy() {
  var cache = {};
  return new Proxy(function () {}, {
    get: function (t, k) {
      if (k === Symbol.toPrimitive) return function () { return ""; };
      if (k === "then") return undefined;
      if (k === Symbol.iterator) return function* () {};
      if (k === "toString" || k === "valueOf") return function () { return ""; };
      if (k === "length") return 0;
      if (!(k in cache)) cache[k] = anyProxy();
      return cache[k];
    },
    set: function (t, k, v) { cache[k] = v; return true; },
    apply: function () { return anyProxy(); },
    construct: function () { return anyProxy(); },
    has: function () { return true; },
  });
}
G.__anyProxy = anyProxy;

// ---------- timers ----------
G.setTimeout = function (fn, ms) { var a = Array.prototype.slice.call(arguments, 2); return os.setTimeout(function () { fn.apply(null, a); }, ms || 0); };
G.clearTimeout = function (h) { if (h) os.clearTimeout(h); };
G.setInterval = function () { return 0; };
G.clearInterval = function () {};
G.requestAnimationFrame = function (cb) { return os.setTimeout(function () { cb(performance.now()); }, 16); };
G.cancelAnimationFrame = function (h) { if (h) os.clearTimeout(h); };

// ---------- text / url ----------
G.TextEncoder = function TextEncoder() {};
G.TextEncoder.prototype.encoding = "utf-8";
G.TextEncoder.prototype.encode = function (s) {
  s = String(s === undefined ? "" : s);
  var out = [];
  for (var i = 0; i < s.length; i++) {
    var c = s.charCodeAt(i);
    if (c >= 0xd800 && c < 0xdc00 && i + 1 < s.length) { var d = s.charCodeAt(i + 1); if (d >= 0xdc00 && d < 0xe000) { c = 0x10000 + ((c - 0xd800) << 10) + (d - 0xdc00); i++; } }
    if (c < 0x80) out.push(c);
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
    else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    else out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
  }
  return new Uint8Array(out);
};
G.TextDecoder = function TextDecoder(enc) { this.encoding = enc || "utf-8"; };
G.TextDecoder.prototype.decode = function (b) {
  if (b === undefined) return "";
  var u = b instanceof Uint8Array ? b : ArrayBuffer.isView(b) ? new Uint8Array(b.buffer, b.byteOffset, b.byteLength) : new Uint8Array(b);
  var s = "", i = 0;
  if (!/utf-?8/i.test(this.encoding)) { for (; i < u.length; i++) s += String.fromCharCode(u[i]); return s; }
  while (i < u.length) {
    var c = u[i++];
    if (c >= 0xf0) { c = ((c & 7) << 18) | ((u[i++] & 63) << 12) | ((u[i++] & 63) << 6) | (u[i++] & 63); }
    else if (c >= 0xe0) { c = ((c & 15) << 12) | ((u[i++] & 63) << 6) | (u[i++] & 63); }
    else if (c >= 0xc0) { c = ((c & 31) << 6) | (u[i++] & 63); }
    if (c >= 0x10000) { c -= 0x10000; s += String.fromCharCode(0xd800 + (c >> 10), 0xdc00 + (c & 1023)); } else s += String.fromCharCode(c);
  }
  return s;
};

function URLSearchParams(init) {
  this._l = [];
  if (typeof init === "string") {
    init = init.replace(/^\?/, "");
    if (init) init.split("&").forEach(function (p) { var i = p.indexOf("="); var k = i < 0 ? p : p.slice(0, i), v = i < 0 ? "" : p.slice(i + 1); this._l.push([decodeURIComponent(k.replace(/\+/g, " ")), decodeURIComponent(v.replace(/\+/g, " "))]); }, this);
  } else if (init && typeof init === "object") { for (var k in init) this._l.push([k, String(init[k])]); }
}
URLSearchParams.prototype.get = function (k) { for (var i = 0; i < this._l.length; i++) if (this._l[i][0] === k) return this._l[i][1]; return null; };
URLSearchParams.prototype.getAll = function (k) { return this._l.filter(function (p) { return p[0] === k; }).map(function (p) { return p[1]; }); };
URLSearchParams.prototype.has = function (k) { return this.get(k) !== null; };
URLSearchParams.prototype.set = function (k, v) { this.delete(k); this._l.push([k, String(v)]); };
URLSearchParams.prototype.append = function (k, v) { this._l.push([k, String(v)]); };
URLSearchParams.prototype.delete = function (k) { this._l = this._l.filter(function (p) { return p[0] !== k; }); };
URLSearchParams.prototype.forEach = function (f) { this._l.forEach(function (p) { f(p[1], p[0]); }); };
URLSearchParams.prototype.toString = function () { return this._l.map(function (p) { return encodeURIComponent(p[0]) + "=" + encodeURIComponent(p[1]); }).join("&"); };
G.URLSearchParams = URLSearchParams;

function URL(u, base) {
  u = String(u);
  var m = /^([a-z][a-z0-9+.-]*:)\/\/([^\/?#]*)([^?#]*)(\?[^#]*)?(#.*)?$/i.exec(u);
  if (!m) {
    if (base === undefined) throw new TypeError("Invalid URL: " + u);
    var b = new URL(base);
    if (u.slice(0, 2) === "//") return new URL(b.protocol + u);
    if (u.charAt(0) === "/") return new URL(b.origin + u);
    if (u.charAt(0) === "?") return new URL(b.origin + b.pathname + u);
    if (u.charAt(0) === "#") return new URL(b.origin + b.pathname + b.search + u);
    return new URL(b.origin + b.pathname.replace(/[^\/]*$/, "") + u);
  }
  this.protocol = m[1].toLowerCase();
  this.host = m[2];
  var hp = m[2].split(":");
  this.hostname = hp[0];
  this.port = hp[1] || "";
  this.pathname = m[3] || "/";
  this.search = m[4] && m[4] !== "?" ? m[4] : "";
  this.hash = m[5] || "";
  this.origin = this.protocol + "//" + this.host;
  this.username = "";
  this.password = "";
  this.searchParams = new URLSearchParams(this.search);
}
Object.defineProperty(URL.prototype, "href", { get: function () { return this.origin + this.pathname + this.search + this.hash; } });
URL.prototype.toString = function () { return this.href; };
URL.prototype.toJSON = function () { return this.href; };
URL.createObjectURL = function () { return "blob:null"; };
URL.revokeObjectURL = function () {};
G.URL = URL;

// ---------- abort ----------
function AbortSignal() { this.aborted = false; this.reason = undefined; this.onabort = null; }
AbortSignal.prototype.addEventListener = function () {};
AbortSignal.prototype.removeEventListener = function () {};
AbortSignal.prototype.throwIfAborted = function () {};
AbortSignal.timeout = function () { return new AbortSignal(); };
AbortSignal.abort = function () { var s = new AbortSignal(); s.aborted = true; return s; };
function AbortController() { this.signal = new AbortSignal(); }
AbortController.prototype.abort = function () { this.signal.aborted = true; };
G.AbortSignal = AbortSignal;
G.AbortController = AbortController;

// ---------- crypto: only random bytes are needed (crypto-browserify does the rest) ----------
var __urand = null;
try { __urand = std.open("/dev/urandom", "rb"); } catch (e) {}
G.crypto = {
  getRandomValues: function (a) {
    var u = new Uint8Array(a.buffer, a.byteOffset, a.byteLength);
    if (__urand) __urand.read(u.buffer, u.byteOffset, u.byteLength);
    else for (var i = 0; i < u.length; i++) u[i] = (Math.random() * 256) | 0;
    return a;
  },
  randomUUID: function () { return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, function (c) { return (c ^ ((Math.random() * 16) | 0) & (15 >> (c / 4))).toString(16); }); },
  subtle: anyProxy(),
};

// ---------- browser objects ----------
var store = {};
var ls = { getItem: function (k) { return k in store ? store[k] : null; }, setItem: function (k, v) { store[k] = String(v); }, removeItem: function (k) { delete store[k]; }, clear: function () { store = {}; }, key: function () { return null; }, length: 0 };
function defG(n, v) { Object.defineProperty(G, n, { value: v, configurable: true, writable: true, enumerable: true }); }
defG("localStorage", ls);
defG("sessionStorage", ls);
defG("navigator", { userAgent: G.__UA, platform: "Linux armv7l", language: "en-US", languages: ["en-US", "en"], maxTouchPoints: 0, hardwareConcurrency: 4, webdriver: false, cookieEnabled: true, onLine: true, vendor: "" });
defG("screen", { width: 1920, height: 1080, availWidth: 1920, availHeight: 1040, colorDepth: 24, pixelDepth: 24 });
defG("location", new URL(G.__PAGE));
defG("document", anyProxy());
defG("window", G);
defG("self", G);
defG("top", G);
defG("parent", { postMessage: function () {} });
G.name = "";
G.innerWidth = 1280;
G.innerHeight = 720;
G.devicePixelRatio = 1;
G.addEventListener = function () {};
G.removeEventListener = function () {};
G.dispatchEvent = function () { return true; };
G.postMessage = function () {};
G.getComputedStyle = function () { return anyProxy(); };
G.matchMedia = function () { return { matches: false, addListener: function () {}, removeListener: function () {}, addEventListener: function () {}, removeEventListener: function () {} }; };
G.Blob = function Blob() {};
G.FileReader = function FileReader() {};
G.Image = function Image() {};
G.MediaSource = function MediaSource() {};
G.MediaSource.isTypeSupported = function () { return true; };
G.HTMLElement = function HTMLElement() {};
G.Element = G.HTMLElement;
G.Node = G.HTMLElement;
G.Event = function Event(t) { this.type = t; };
G.CustomEvent = G.Event;
G.EventTarget = function EventTarget() {};
G.EventTarget.prototype.addEventListener = function () {};
G.EventTarget.prototype.removeEventListener = function () {};
G.EventTarget.prototype.dispatchEvent = function () { return true; };
G.MutationObserver = function () { this.observe = function () {}; this.disconnect = function () {}; };
G.ResizeObserver = G.MutationObserver;
G.IntersectionObserver = G.MutationObserver;
G.XMLHttpRequest = function () {};
G.Headers = function Headers(h) { this._h = {}; if (h) for (var k in h) this._h[k.toLowerCase()] = h[k]; };
G.Headers.prototype.get = function (k) { k = k.toLowerCase(); return k in this._h ? this._h[k] : null; };
G.Headers.prototype.has = function (k) { return k.toLowerCase() in this._h; };
G.Headers.prototype.set = function (k, v) { this._h[k.toLowerCase()] = String(v); };
G.Headers.prototype.forEach = function (f) { for (var k in this._h) f(this._h[k], k); };
G.structuredClone = function (v) { return JSON.parse(JSON.stringify(v)); };

// ---------- fetch through the parent process ----------
var fetchId = 0;
G.fetch = function (url, opt) {
  opt = opt || {};
  var u = new URL(String(url), G.__PAGE).href;
  var h = {};
  var oh = opt.headers || {};
  if (oh instanceof G.Headers) oh.forEach(function (v, k) { h[k] = v; });
  else for (var k in oh) h[k] = String(oh[k]);
  var req = { id: ++fetchId, url: u, method: (opt.method || "GET").toUpperCase(), headers: h, body: typeof opt.body === "string" ? opt.body : null };
  __out("@@F " + JSON.stringify(req));
  var line = std.in.getline();
  var ans;
  try { ans = JSON.parse(line || "{}"); } catch (e) { ans = {}; }
  var status = ans.status || 0, body = ans.body || "";
  var resp = {
    status: status, ok: status >= 200 && status < 300, statusText: "", url: u, redirected: false, type: "basic",
    headers: new G.Headers(ans.headers || {}),
    text: function () { return Promise.resolve(body); },
    json: function () { return Promise.resolve(JSON.parse(body)); },
    arrayBuffer: function () { return Promise.resolve(new G.TextEncoder().encode(body).buffer); },
    clone: function () { return resp; },
  };
  return status ? Promise.resolve(resp) : Promise.reject(new TypeError("Failed to fetch"));
};

// ---------- webpack chunk registry: the chunks push their modules here ----------
G.__modules = {};
G.webpackChunk_N_E = [];
G.webpackChunk_N_E.push = function () { for (var i = 0; i < arguments.length; i++) { var m = arguments[i][1]; for (var id in m) G.__modules[id] = m[id]; } return 0; };

// ---------- the site's code that follows does not need file and process access: keep it out of its reach ----------
G.__out = __out;
G.__exit = function () { std.exit(0); };
delete G.std;
delete G.os;
delete G.bjson;
})();
