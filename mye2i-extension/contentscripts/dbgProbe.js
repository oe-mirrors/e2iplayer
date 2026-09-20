// Debug snapshot probe. Injected into the probe tab by background.js after
// every finished page load of that tab (the Cloudflare challenge may reload
// the page and drop the "#e2itdbg" fragment, so this cannot rely on being a
// static content script). Waits until the real page is rendered and quiet,
// then sends several sections to the box via the still-open e2it.html tab
// (background.js relays them, e2it.js POSTs them to mye2iserver.py).
(function () {
    'use strict';

    if (window.__e2iProbeRunning) {
        return;
    }
    window.__e2iProbeRunning = true;

    var START = Date.now();
    var MIN_WAIT_MS = 4000;      // give late JS at least this long after load
    var QUIET_MS = 2500;         // DOM must not change for this long
    var MAX_WAIT_MS = 30000;     // settle limit once the challenge is gone
    var CHALLENGE_LIMIT_MS = 300000; // how long to wait for a challenge to be solved

    var lastMutation = Date.now();
    var challengeSince = 0;      // first time the challenge page was seen
    var challengeSeenAt = 0;     // last time it was still there

    function log(msg) {
        try { chrome.runtime.sendMessage({action: 'DEBUG_LOG', msg: '[probe] ' + msg}); } catch (e) {}
    }

    function looksLikeChallengePage() {
        try {
            if (document.getElementById('challenge-form')) return true;
            if (document.title && document.title.indexOf('Just a moment') !== -1) return true;
            var scripts = document.getElementsByTagName('script');
            for (var i = 0; i < scripts.length; i++) {
                if (scripts[i].text && scripts[i].text.indexOf('window._cf_chl_opt') !== -1) return true;
            }
        } catch (e) {}
        return false;
    }

    try {
        new MutationObserver(function () { lastMutation = Date.now(); })
            .observe(document.documentElement, {childList: true, subtree: true, attributes: true, characterData: true});
    } catch (e) {}

    function send(name, data) {
        return new Promise(function (resolve) {
            try {
                chrome.runtime.sendMessage({action: 'DEBUG_DUMP', name: name, data: data}, function () { resolve(); });
            } catch (e) {
                resolve();
            }
        });
    }

    function getNetLog() {
        return new Promise(function (resolve) {
            var id = Math.random().toString(36).slice(2);
            var timer = setTimeout(function () {
                window.removeEventListener('message', onMsg);
                resolve(null);
            }, 2000);
            function onMsg(event) {
                if (event.source !== window || !event.data || event.data.__E2IDBG !== 'NETLOG' || event.data.id !== id) {
                    return;
                }
                clearTimeout(timer);
                window.removeEventListener('message', onMsg);
                resolve(event.data.log);
            }
            window.addEventListener('message', onMsg);
            window.postMessage({__E2IDBG: 'GET_NETLOG', id: id}, '*');
        });
    }

    function getCookies() {
        return new Promise(function (resolve) {
            try {
                chrome.runtime.sendMessage({
                    action: 'GET_COOKIE',
                    data: {idx: 0, type: 'url', url: document.location.href, partition_key: {}, with_partition_key: false}
                }, function (resp) { resolve(resp && resp.cookies ? resp.cookies : []); });
            } catch (e) {
                resolve([]);
            }
        });
    }

    function snapshot() {
        var pieces = [];

        var meta = {
            href: document.location.href,
            title: document.title,
            readyState: document.readyState,
            userAgent: navigator.userAgent,
            viewport: window.innerWidth + 'x' + window.innerHeight,
            referrer: document.referrer,
            waitedMs: Date.now() - START,
            time: new Date().toISOString()
        };
        pieces.push(send('meta', JSON.stringify(meta, null, 2)));

        pieces.push(send('dom', '<!-- rendered DOM of ' + document.location.href + ' -->\n' + document.documentElement.outerHTML));

        var resources = [];
        try {
            performance.getEntriesByType('resource').forEach(function (r) {
                resources.push(r.initiatorType + '\t' + Math.round(r.duration) + 'ms\t' + r.name);
            });
        } catch (e) {}
        pieces.push(send('resources', resources.join('\n')));

        pieces.push(getNetLog().then(function (netlog) {
            if (netlog === null) {
                return send('netlog', '(no fetch/XHR log - the page-world hook did not answer)');
            }
            var lines = netlog.map(function (e) {
                return JSON.stringify(e);
            });
            return send('netlog', lines.join('\n'));
        }));

        pieces.push(getCookies().then(function (cookies) {
            // values are cut short on purpose: names/flags are what matters
            // when working out how a site tracks a session, and the log gets
            // shared around.
            var lines = cookies.map(function (c) {
                return [c.name, c.domain, c.path, 'httpOnly=' + c.httpOnly, 'secure=' + c.secure,
                    'sameSite=' + c.sameSite, 'value=' + String(c.value).slice(0, 40)].join('\t');
            });
            return send('cookies', lines.join('\n'));
        }));

        return Promise.all(pieces);
    }

    function finish() {
        log('snapshot sent (' + (Date.now() - START) + ' ms)');
        try { chrome.runtime.sendMessage({action: 'DBG_DONE'}); } catch (e) {}
    }

    var poll = setInterval(function () {
        var now = Date.now();
        if (document.readyState !== 'complete' || !document.body) {
            return;
        }
        if (looksLikeChallengePage()) {
            challengeSeenAt = now;
            if (!challengeSince) {
                challengeSince = now;
                log('Cloudflare challenge detected - solve it in this tab, the snapshot follows automatically');
            }
            if (now - challengeSince > CHALLENGE_LIMIT_MS) {
                clearInterval(poll);
                log('gave up waiting for the challenge to be solved');
                finish();
            }
            return;
        }
        var settledFor = now - Math.max(START, challengeSeenAt);
        if ((now - lastMutation >= QUIET_MS && settledFor >= MIN_WAIT_MS) || settledFor >= MAX_WAIT_MS) {
            clearInterval(poll);
            log('taking snapshot');
            snapshot().then(finish);
        }
    }, 500);
})();
