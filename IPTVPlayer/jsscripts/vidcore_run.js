// E2iPlayer: render the player component with fake React hooks and run its two VM effects.
// Output lines: "@@S <servers json>", "@@R <stream json>" (one per server), "@@E <message>", "@@D".
"use strict";
(function () {
  var G = globalThis, modules = G.__modules, anyProxy = G.__anyProxy;
  var out = function (s) { G.__out(s); if (s === "@@D") G.__exit(); };
  var VM_RE = /\^\w+\[\w+%256\]\^\w+\[\w+%256\]/;

  // ---------- webpack require ----------
  var cache = {};
  var overrides = {};
  function failed(id) { return new Proxy({}, { get: function (t, k) { return k === "__esModule" ? true : anyProxy(); } }); }
  function req(id) {
    if (overrides[id]) return overrides[id];
    if (cache[id]) return cache[id].exports;
    var f = modules[id];
    var module = (cache[id] = { exports: {} });
    if (!f) { module.exports = failed(id); return module.exports; }
    try { f.call(module.exports, module, module.exports, req); }
    catch (e) { module.exports = failed(id); }
    return module.exports;
  }
  req.d = function (e, defs) { for (var k in defs) if (!Object.prototype.hasOwnProperty.call(e, k)) Object.defineProperty(e, k, { enumerable: true, get: defs[k] }); };
  req.o = function (o, k) { return Object.prototype.hasOwnProperty.call(o, k); };
  req.r = function (e) { Object.defineProperty(e, "__esModule", { value: true }); };
  req.n = function (m) { var g = m && m.__esModule ? function () { return m.default; } : function () { return m; }; req.d(g, { a: g }); return g; };
  req.t = function (v) { return v; };
  req.g = G; req.p = "/_next/"; req.nc = undefined;
  req.e = function () { return Promise.resolve(); };

  // ---------- fake React: state survives re-renders, effects are collected ----------
  var hookIdx = 0, hookState = [], effects = [], elemRefs = false;
  var servers = null, result = null, failedSeen = false;
  function onSet(v) {
    if (Array.isArray(v) && v.length && v[0] && typeof v[0] === "object" && v[0].data !== undefined && "name" in v[0]) {
      if (!servers) servers = v;
      if (v.some(function (s) { return s.failed; })) failedSeen = true;
    }
  }
  function onRef(v) { if (v && typeof v === "object" && typeof v.url === "string" && /^https?:/.test(v.url)) result = v; }
  var fakeReact = {
    useState: function (init) {
      var i = hookIdx++;
      if (!(i in hookState)) hookState[i] = typeof init === "function" ? init() : init;
      return [hookState[i], function (v) { hookState[i] = typeof v === "function" ? v(hookState[i]) : v; onSet(hookState[i]); }];
    },
    useRef: function (init) {
      var i = hookIdx++;
      if (elemRefs && i in hookState && hookState[i]._v === undefined) hookState[i]._v = anyProxy();
      if (!(i in hookState)) {
        var box = { _v: init };
        Object.defineProperty(box, "current", { get: function () { return this._v; }, set: function (v) { this._v = v; onRef(v); } });
        hookState[i] = box;
      }
      return hookState[i];
    },
    useEffect: function (fn) { effects.push(fn); hookIdx++; },
    useLayoutEffect: function () { hookIdx++; },
    useInsertionEffect: function () { hookIdx++; },
    useCallback: function (fn) { hookIdx++; return fn; },
    useMemo: function (fn) { hookIdx++; return fn(); },
    useContext: function () { return anyProxy(); },
    useReducer: function (r, i) { return [i, function () {}]; },
    useId: function () { return "id"; },
    useSyncExternalStore: function (s, g) { return g(); },
    useTransition: function () { return [false, function (f) { f(); }]; },
    useDeferredValue: function (v) { return v; },
    useImperativeHandle: function () {},
    createContext: function () { return anyProxy(); },
    forwardRef: function (f) { return f; }, memo: function (f) { return f; }, lazy: function () { return anyProxy(); },
    Fragment: "frag", createElement: function () { return null; }, Children: anyProxy(),
    isValidElement: function () { return false; }, cloneElement: function () { return null; },
    startTransition: function (f) { f(); },
  };

  // React = the module whose source defines useState/useEffect on its exports (next.js: 2115)
  var playerId = null, ids = Object.keys(modules);
  for (var j = 0; j < ids.length; j++) {
    var src = modules[ids[j]].toString();
    if (VM_RE.test(src)) playerId = ids[j];
    if (src.length < 20000 && /\.useState=function/.test(src) && /\.useEffect=function/.test(src)) overrides[ids[j]] = fakeReact;
  }
  if (!playerId) { out("@@E no player module"); return out("@@D"); }
  if (!Object.keys(overrides).length) { out("@@E no react module"); return out("@@D"); }
  // Buffer polyfill (feross/buffer): every string operand of the VMs goes through alloc + toString,
  // both slow in qjs (alloc = new Uint8Array + Object.setPrototypeOf) - about a quarter of the run time
  function fastBuffer(B) {
    var alloc = B.alloc, toStr = B.prototype.toString, NT = function () {};
    NT.prototype = B.prototype;
    B.alloc = function (n, fill) {
      if (fill === undefined && typeof n === "number" && n >= 0) return Reflect.construct(Uint8Array, [n], NT);
      return alloc.apply(this, arguments);
    };
    B.prototype.toString = function (enc, s, e) {
      if ((enc === undefined || enc === "utf8" || enc === "utf-8") && s === undefined && e === undefined && this.length < 4096) {
        for (var i = 0; i < this.length; i++) if (this[i] > 127) return toStr.apply(this, arguments);
        return String.fromCharCode.apply(null, this);
      }
      return toStr.apply(this, arguments);
    };
  }
  for (var bi = 0; bi < ids.length; bi++) {
    var bsrc = modules[ids[bi]].toString();
    if (bsrc.indexOf("INSPECT_MAX_BYTES") < 0 || bsrc.indexOf("kMaxLength") < 0) continue;
    var B = req(ids[bi]).Buffer;
    if (B && B.prototype) { fastBuffer(B); break; }
  }
  var player = req(playerId);
  var Comp = player.default;
  if (typeof Comp !== "function") for (var k in player) if (typeof player[k] === "function" && VM_RE.test(player[k].toString())) Comp = player[k];
  if (typeof Comp !== "function") { out("@@E no component"); return out("@@D"); }

  var props = { en: G.__EN, id: G.__TMDB, season: G.__SEASON || undefined, episode: G.__EPISODE || undefined, server: undefined, autoPlay: false };
  function render() { hookIdx = 0; effects = []; try { Comp(props); } catch (e) {} return effects; }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  async function runEffects(list, pred) {
    for (var i = 0; i < list.length; i++) {
      var s = list[i].toString();
      if (!pred(s)) continue;
      try { var r = list[i](); if (r && r.then) await r; } catch (e) {}
    }
  }

  (async function () {
    // VM1: server list
    await runEffects(render(), function (s) { return /Uint8Array\(256\)/.test(s) && !/method:"POST"/.test(s); });
    // the upper limit of the whole run is the parent's: a box needs 30 s here, slower ones much more
    for (var t = 0; t < 2000 && !servers; t++) await sleep(100);
    if (!servers) { out("@@E no servers"); return out("@@D"); }
    out("@@S " + JSON.stringify(servers.map(function (s) { return { name: s.name, description: s.description }; })));
    // VM2: one stream per server
    var max = G.__MAXSRV || 5, names = servers.map(function (s) { return s.name; });
    elemRefs = true;
    for (var n = 0; n < names.length && n < max; n++) {
      var stateIdx = hookState.indexOf(servers);
      if (stateIdx < 0) for (var q = 0; q < hookState.length; q++) if (Array.isArray(hookState[q]) && hookState[q].length && hookState[q][0] && hookState[q][0].data !== undefined) stateIdx = q;
      servers = servers.map(function (s) { return Object.assign({}, s, { selected: s.name === names[n], failed: false }); });
      hookState[stateIdx] = servers;
      result = null; failedSeen = false;
      await runEffects(render(), function (s) { return /method:"POST"/.test(s) && /\.concat\(\w+\.data\)/.test(s); });
      for (var w = 0; w < 600 && !result && !failedSeen; w++) await sleep(100);
      if (result) out("@@R " + JSON.stringify({ server: names[n], url: result.url, noReferrer: !!result.noReferrer, mp4: !!result.mp4, tracks: result.tracks || [] }));
      else out("@@E server " + names[n] + " failed");
    }
    out("@@D");
  })().catch(function (e) { out("@@E " + e); out("@@D"); });
})();
