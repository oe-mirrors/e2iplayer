// Runs in the page's own JS world (manifest "world": "MAIN", plus a dynamic
// registration from background.js so it survives a Cloudflare redirect that
// drops the "#e2itdbg" fragment). Records fetch()/XMLHttpRequest calls of the
// top-level page - method, URL, request body and a text snippet of the
// response - so the debug snapshot can show which API a site really calls.
(function () {
    'use strict';

    if (window !== window.top || window.__e2iNetHook) {
        return;
    }
    window.__e2iNetHook = true;

    var MAX_ENTRIES = 400;
    var MAX_TEXT = 3000;
    var LOG = [];

    function cut(value) {
        var s;
        try {
            s = (typeof value === 'string') ? value : (value == null ? '' : String(value));
        } catch (e) {
            s = '';
        }
        return s.length > MAX_TEXT ? s.slice(0, MAX_TEXT) + '...[+' + (s.length - MAX_TEXT) + ' chars]' : s;
    }

    function bodyToText(body) {
        if (body == null) {
            return '';
        }
        try {
            if (typeof body === 'string') {
                return cut(body);
            }
            if (typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams) {
                return cut(body.toString());
            }
            if (typeof FormData !== 'undefined' && body instanceof FormData) {
                var parts = [];
                body.forEach(function (v, k) {
                    parts.push(k + '=' + (typeof v === 'string' ? v : '[file]'));
                });
                return cut(parts.join('&'));
            }
        } catch (e) {}
        return '[' + Object.prototype.toString.call(body) + ']';
    }

    function isTextual(contentType) {
        return /json|text|xml|javascript|mpegurl/i.test(contentType || '');
    }

    function push(entry) {
        if (LOG.length < MAX_ENTRIES) {
            LOG.push(entry);
        }
        return entry;
    }

    var origFetch = window.fetch;
    if (typeof origFetch === 'function') {
        window.fetch = function (input, init) {
            var entry = push({
                t: Date.now(),
                kind: 'fetch',
                method: ((init && init.method) || (input && input.method) || 'GET').toUpperCase(),
                url: cut(typeof input === 'string' ? input : (input && input.url) || input),
                reqBody: bodyToText(init && init.body)
            });
            var promise = origFetch.apply(this, arguments);
            promise.then(function (resp) {
                entry.status = resp.status;
                entry.contentType = resp.headers.get('content-type') || '';
                if (isTextual(entry.contentType)) {
                    try {
                        resp.clone().text().then(function (text) {
                            entry.response = cut(text);
                        }, function () {});
                    } catch (e) {}
                }
            }, function (err) {
                entry.error = cut(err);
            });
            return promise;
        };
    }

    var XHR = window.XMLHttpRequest;
    if (XHR && XHR.prototype) {
        var origOpen = XHR.prototype.open;
        var origSend = XHR.prototype.send;
        XHR.prototype.open = function (method, url) {
            this.__e2iEntry = {
                t: Date.now(),
                kind: 'xhr',
                method: String(method || 'GET').toUpperCase(),
                url: cut(url)
            };
            return origOpen.apply(this, arguments);
        };
        XHR.prototype.send = function (body) {
            var entry = this.__e2iEntry;
            if (entry) {
                push(entry);
                entry.reqBody = bodyToText(body);
                this.addEventListener('loadend', function () {
                    entry.status = this.status;
                    entry.contentType = this.getResponseHeader('content-type') || '';
                    try {
                        if (isTextual(entry.contentType) && (this.responseType === '' || this.responseType === 'text')) {
                            entry.response = cut(this.responseText);
                        }
                    } catch (e) {}
                });
            }
            return origSend.apply(this, arguments);
        };
    }

    // The isolated-world probe (dbgProbe.js) cannot read this world's
    // variables, so it asks for the log through window.postMessage.
    window.addEventListener('message', function (event) {
        if (event.source !== window || !event.data || event.data.__E2IDBG !== 'GET_NETLOG') {
            return;
        }
        window.postMessage({__E2IDBG: 'NETLOG', id: event.data.id, log: LOG}, '*');
    });
})();
