'use strict';

function e2ilog(txt) {
    console.log("[MyE2i-DEBUG e2it]", txt);
}

// The box puts a random per-session token into the address it shows
// (http://<box>:<port>/?t=<token>) and into the page it serves (meta tag). The
// server only accepts pages, results, debug lines and dumps for whoever has it,
// so another device in the LAN cannot inject any. Read lazily: this script runs
// at document_start, before the meta tag is parsed.
function e2iToken() {
    try {
        var meta = document.querySelector('meta[name="mye2i-token"]');
        if (meta?.content) {
            return meta.content;
        }
        return new URLSearchParams(window.location.search).get('t') || '';
    } catch (e) {
        // no readable address/meta tag: no token
        return '';
    }
}

function e2iUrl(path, query = '') {
    var u = window.location;
    var q = query;
    var token = e2iToken();
    if (token) {
        q += (q ? '&' : '') + 't=' + encodeURIComponent(token);
    }
    return u.protocol + '//' + u.host + path + (q ? '?' + q : '');
}

// Texts of this page (relay page): the plugin translates them and mye2iserver.py
// puts them into the page as JSON (id "mye2i-i18n"); without them (older
// server / plugin) the English texts given here are used.
function e2iText(key, english, arg) {
    var text = english;
    try {
        var elem = document.getElementById('mye2i-i18n');
        var texts = elem ? JSON.parse(elem.textContent) : {};
        if (typeof texts[key] === 'string' && texts[key]) {
            text = texts[key];
        }
    } catch (e) {
        // no texts of the box: the English ones given by the caller stay
    }
    return arg === undefined ? text : text.replace('%s', arg);
}

// one-line status on the page (element is part of the page the box serves)
function e2iStatus(text) {
    try {
        var elem = document.getElementById('mye2i-status-text');
        if (elem) {
            elem.textContent = text;
        }
    } catch (e) {
        // the status line is optional
    }
}

// What this extension can do. Other builds of MyE2i use the same version
// numbers, so a job that needs a feature asks for its name (the page attribute
// is read by the relay page's own script, "f=" by mye2iserver.py's /version).
// 1.23: "navhold" - the NAV job's tab does not load the found link itself; "navload" - with l=1 it loads it and
// sends back the answer of one of that page's requests (x=)
var E2I_FEATURES = ['nav', 'referer', 'navhold', 'navload'];
try {
    document.documentElement.setAttribute('data-mye2i-features', E2I_FEATURES.join(' '));
} catch (e) {
    // no document element yet: the relay page shows its outdated hint for feature jobs
}

// Reports the own version to mye2iserver.py right away, so its version check
// can show an "outdated" hint on the receiver screen.
(function reportExtensionVersion() {
    try {
        var v = chrome.runtime.getManifest().version;
        var xhr = new XMLHttpRequest();
        xhr.open("GET", e2iUrl("/version", "v=" + encodeURIComponent(v) + "&f=" + E2I_FEATURES.join(','))); // NOSONAR - the address is built from this relay page's own origin (the box)
        xhr.send();
    } catch (e) {
        // an old server without /version simply never learns the version
    }
})();

// A job whose page has to be opened with a given Referer ("ref=" in the
// fragment of the solve button's address, an embed page): the background
// script opens the tab and sets the Referer for it. Every other job keeps the
// page's own window.open() - without any Referer (the page says no-referrer).
function e2iJobHasReferer(url) {
    var sep = url.indexOf('_sep_');
    if (sep < 0 || !/#e2it/.test(url)) {
        return false;
    }
    return url.slice(sep + 5).split('&').some(function (part) {
        return part.indexOf('ref=') === 0 && part.length > 4;
    });
}

document.addEventListener('click', function (event) {
    var button = event.target && event.target.closest ? event.target.closest('#mye2i-solve') : null;
    if (!button) {
        return;
    }
    var url = button.getAttribute('data-url') || '';
    if (!e2iJobHasReferer(url)) {
        return;
    }
    // (capture phase on the document: runs before the button's own onclick)
    event.preventDefault();
    event.stopImmediatePropagation();
    chrome.runtime.sendMessage({action: 'OPEN_SOLVER', url: url}, function (resp) {
        if (chrome.runtime.lastError || !resp || !resp.ok) {
            // the page still opens, only without the Referer
            window.open(url, '_blank');
        }
    });
}, true);

chrome.runtime.onMessage.addListener(
    function (request, sender, sendResponse) {
        try {
            if (request.action === "DEBUG_LOG") {
                // A debug line from the challenge tab (forwarded by background.js):
                // handed to mye2iserver.py, which prints it into the receiver's debug log.
                var dbgXhr = new XMLHttpRequest();
                dbgXhr.open("GET", e2iUrl("/debug", "msg=" + encodeURIComponent('' + request.msg)));
                dbgXhr.responseType = "text";
                dbgXhr.onload = function () { sendResponse('OK'); };
                dbgXhr.onerror = function () { sendResponse('ERR'); };
                dbgXhr.send();
                return;
            }

            if (request.action === "DEBUG_DUMP") {
                // Debug snapshot section (rendered DOM, network log, ...) from
                // the probe tab: too big for a GET query string, so it goes to
                // mye2iserver.py as a POST body (/debugdump).
                var dumpXhr = new XMLHttpRequest();
                dumpXhr.open("POST", e2iUrl("/debugdump", "name=" + encodeURIComponent('' + request.name)));
                dumpXhr.setRequestHeader("Content-Type", "text/plain;charset=UTF-8");
                dumpXhr.onload = function () { e2iStatus(e2iText('x_dump_ok', 'Debug snapshot: "%s" received by the box', request.name)); sendResponse('OK'); };
                dumpXhr.onerror = function () { e2iStatus(e2iText('x_dump_failed', 'Debug snapshot: sending "%s" failed', request.name)); sendResponse('ERR'); };
                dumpXhr.send('' + request.data);
                return true;
            }

            if (request.action === "SEND_RESPONSE" && request.data?.token && request.data.captchaId) {
                var xhr = new XMLHttpRequest();
                var responseUrl = e2iUrl("/response", "c=" + encodeURIComponent(request.data.captchaId) + "&token=" + encodeURIComponent(request.data.token));
                xhr.open("GET", responseUrl);
                xhr.responseType = "text";

                xhr.onload = function () {
                    e2ilog(Date.now() + " | response send OK");
                    e2iStatus(e2iText('x_done', 'Done - the result was sent to the box, you can close this page.'));
                    tryCloseTabIfElementExists();
                    
                    sendResponse('OK');
                };

                xhr.onerror = function () {
                    console.log(Date.now() + " | response send FAILED");
                    e2iStatus(e2iText('x_send_failed', 'Sending the result to the box failed.'));
                    showError('' + xhr.status);
                    sendResponse('ERR');
                };

                xhr.send();

            }
        } catch (e) {
            showError('' + e);
        }
    }
);

function showError(sts) {
    var elem = document.querySelector("[id^='mye2i_1']");
    if (elem) {
        elem.style.display = "block";
        elem.textContent = '';
        var strong = document.createElement('strong');
        strong.textContent = e2iText('x_error', 'Error occurs:') + ' ' + sts;
        elem.appendChild(strong);
    }
}

function tryCloseTabIfElementExists() {
    if (document.querySelector("#e2i-close-on-success")) {
        chrome.runtime.sendMessage({'action':'CLOSE_ME'});
    }
}

function compareVersions(v1, v2) {
  const a1 = v1.split('.').map(Number);
  const a2 = v2.split('.').map(Number);
  for (let i = 0; i < Math.max(a1.length, a2.length); i++) {
    const n1 = a1[i] || 0;
    const n2 = a2[i] || 0;
    if (n1 > n2) return 1;
    if (n1 < n2) return -1;
  }
  return 0;
}


function e2i_checkBanner(event) {
    var elem = document.querySelector("[id^='mye2i_1']");
    if (elem) {
        var currentVersion = chrome.runtime.getManifest().version;
        var expectedVersion = elem.id.replace("mye2i_", ""); 
        
        if (compareVersions(currentVersion, expectedVersion) >= 0) {
            elem.style.display = "none";
        }
    }
}

document.addEventListener('readystatechange', e2i_checkBanner);

// Shows the installed extension version in the top right corner, so it is obvious
// which version the browser really runs.
function e2i_showExtensionVersion() {
    try {
        if (!document.body) return;
        if (document.getElementById('mye2i-version-badge')) return;
        var badge = document.createElement('div');
        badge.id = 'mye2i-version-badge';
        badge.style.cssText = 'position:fixed;top:8px;right:8px;background:#222;color:#fff;padding:6px 12px;border-radius:8px;font-family:sans-serif;font-size:14px;z-index:2147483647;box-shadow:0 2px 6px rgba(0,0,0,0.4);';
        badge.textContent = 'MyE2i Extension v' + chrome.runtime.getManifest().version;
        document.body.appendChild(badge);
    } catch (e) {
        // the badge is only a hint
    }
}

document.addEventListener('readystatechange', function () {
    if (document.readyState !== 'loading') {
        e2i_showExtensionVersion();
    }
});

