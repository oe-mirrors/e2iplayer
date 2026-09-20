function e2ilog(...args) {
    console.log("[MyE2i-DEBUG]", ...args);
    // Every log line is also passed on to the local relay tab (e2it.html), which sends it
    // to mye2iserver.py, so it ends up in the receiver's debug log without keeping the
    // DevTools of this (self-closing) tab open.
    try {
        var msg = args.map(function (a) {
            return (typeof a === 'string') ? a : JSON.stringify(a);
        }).join(' ');
        chrome.runtime.sendMessage({action: "DEBUG_LOG", msg: msg});
    } catch (e) {
        // logging must never break the caller (no relay tab / extension context gone)
    }
}

// The page script and the extension's proxy script talk through window.postMessage of the very
// same window. A message only counts when this window sent it (e.source) and it carries the
// page's own origin; messages are posted to that origin ("/") only, never to '*'.
function E2iIsOwnMessage(e) {
    return e.source === window && e.origin === window.location.origin;
}

function _E2iSendMsgToPage(from, payload, cb) {
    const id = Math.random().toString(36).slice(2); // NOSONAR - only pairs a reply with its request, not a secret
    if (cb !== undefined)
    {
        function onResp(e) {
            if (!E2iIsOwnMessage(e))
                return;
            const m = e.data;
            if (m?.__MYE2I !== true || m.to !== 'TO_' + from  + '_RESPONSE' || m.id !== id)
                return;
            window.removeEventListener('message', onResp);
            cb?.(m.response);
        }

        window.addEventListener('message', onResp);
    }

    window.postMessage({
        __MYE2I: true,
        to: 'TO_PAGE',
        from: 'FROM_' + from,
        id,
        payload
    }, '/');
}



function E2iSendMsgToPage(payload, cb) {
    _E2iSendMsgToPage("PROXY", payload, cb);
}

function E2iSendMsgToBackground(payload, cb) {
    chrome.runtime.sendMessage(payload, cb);
}


chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    e2ilog('MESSAGE IN PROXY chrome.runtime.onMessage.addListener(): ' + JSON.stringify(msg));

    if (msg.to === 'TO_PAGE' && msg.from === 'FROM_BACKGROUND' ) {
        _E2iSendMsgToPage('BACKGROUND', msg.payload, sendResponse)
    }

    if (msg.to === 'TO_PROXY' && msg.from === 'FROM_BACKGROUND' ) {
        E2iHandleMessage(msg.payload, sendResponse);
    }

    return true;
});


function E2iHandleMessage(msg, cb)
{
    e2ilog('MESSAGE IN PROXY E2iHandleMessage(): ' + JSON.stringify(msg));

    if (msg.action == 'CAPTCHA_RESPONSE')
    {
        let token = msg.response;
        let e2i_job = window.e2i_job;
  
        var response = {
            action: "SEND_RESPONSE",
            response: {
                token: token,
                callbackUrl: e2i_job.callbackUrl,
                captchaId: e2i_job.captchaId
            }
        };
            
        E2iSendMsgToBackground(response, (resp) => {
            E2iSendMsgToBackground({'action':'CLOSE_ME'}, (resp2) => {
                cb('OK');
            });
        });
    }
    if (msg.action == 'HTTP_STATUS')
    {
        HandleStatusCode(msg);
        cb('OK');
    }
    if (msg.action == 'CAPTCHA_ERROR')
    {
        // goes to the box debug log (e2ilog relays it) and onto the page, so
        // a failing widget is no longer a silent blank box
        e2ilog(Date.now() + " | captcha widget reported an error: " + msg.error);
        var box = document.getElementById("captchaContainer");
        if (box) {
            var note = document.createElement('div');
            note.style.cssText = 'color:#c0392b;font-weight:bold;margin-top:12px;text-align:center';
            note.textContent = e2iText('captcha_error', 'Captcha error:') + ' ' + msg.error;
            box.appendChild(note);
        }
        cb('OK');
    }
}

function E2iSetupEventListener() {
    window.addEventListener('message', (e) => {
        if (!E2iIsOwnMessage(e))
            return;
        const msg = e.data;
        if (msg?.__MYE2I !== true)
            return;

        if (msg.to === 'TO_BACKGROUND' && msg.from === 'FROM_PAGE' ) {

            chrome.runtime.sendMessage(msg.payload, (resp) => {
                window.postMessage({
                    __MYE2I: true,
                    from: 'FROM_BACKGROUND',
                    to: 'TO_PAGE_RESPONSE',
                    id: msg.id,
                    response: resp
                }, '/');
            });
        }

        if (msg.to === 'TO_PROXY' && msg.from === 'FROM_PAGE' ) {
            E2iHandleMessage(msg.payload, (resp) => {
                window.postMessage({
                    __MYE2I: true,
                    from: 'FROM_PROXY',
                    to: 'TO_PAGE_RESPONSE',
                    id: msg.id,
                    response: resp
                }, '/');
            });
        }

    });
}

function loadSolverTemplate(callback, error, templateUrl) {
    var xhr = new XMLHttpRequest();
    xhr.onload = function () {
        e2ilog(Date.now() + " | solver template loaded");
        if (callback !== undefined && typeof callback === "function") {
            callback(this.response);
        }
    };
    xhr.onerror = function () {
        e2ilog(Date.now() + " | failed to load solver template");
        if (error !== undefined && typeof error === "function") {
            error(this.response);
        }
    };
    xhr.open("GET", templateUrl === undefined ? chrome.runtime.getURL("./res/browser_solver_template.html") : templateUrl);
    xhr.responseType = "text";
    xhr.send();
}

function insertJSCode(jscode) {
    E2iSendMsgToPage({action: 'INSERT_JS_CODE', 'jscode':jscode}, (resp) => {
        e2ilog("INSERT_IS_CODE response: " + resp);
    });
}

function insertJSSrc(jssrc) {
    E2iSendMsgToPage({action: 'INSERT_JS_SRC', 'jssrc':jssrc}, (resp) => {
        e2ilog("INSERT_JS_SRC response: " + resp);
    });
}


var insertRc2ScriptIntoDOM = function (job) {
    e2ilog(Date.now() + " | inserting rc2 script into DOM for job " + JSON.stringify(job));
    var captchaContainer = document.getElementById("captchaContainer");
    var captchaClass = "g-recaptcha";
    if (job.siteKeyType === "h1" || job.siteKeyType === "h1_invisible") {
        captchaClass = "h-captcha";
    } else if (job.siteKeyType === "cf_re") {
        captchaClass = "cf-turnstile";
    }

    captchaContainer.innerHTML = `<div id="recaptcha_container"><form action="" method="post"> <div class="placeholder"> <div id="recaptcha_widget">
            <form action="?" method="POST">
            <div class="${captchaClass}" data-callback="onResponse" data-error-callback="onCaptchaError"></div>
            </form></div>`;

    captchaContainer.querySelector("." + captchaClass).dataset.sitekey = job.siteKey;
    if (job.siteKeyType === "cf_re") {
        // Turnstile: optional action name and customer data (a=... / d=... in the address)
        if (job.siteKeyAction !== undefined && job.siteKeyAction !== "undefined") {
            captchaContainer.querySelector("." + captchaClass).dataset.action = job.siteKeyAction;
        }
        if (job.cdata !== undefined && job.cdata !== "undefined") {
            captchaContainer.querySelector("." + captchaClass).dataset.cdata = job.cdata;
        }
    }
    if (job.siteKeyType === "INVISIBLE") {
        captchaContainer.querySelector("." + captchaClass).dataset.size = "invisible";
        captchaContainer.innerHTML += "<button class='invisible-captcha-button' id='submit' onclick='grecaptcha.execute();'>" + e2iText('button_i_am_no_robot', 'I am no robot')
            + "</button>";
    }
    
    if (job.siteKeyType === "h1_invisible") {
        // hCaptcha invisible: no checkbox, the challenge (if any) starts when
        // hcaptcha.execute() runs - same button pattern as reCAPTCHA invisible
        captchaContainer.querySelector("." + captchaClass).dataset.size = "invisible";
        captchaContainer.innerHTML += "<button class='invisible-captcha-button' id='submit' onclick='hcaptcha.execute();'>" + e2iText('button_i_am_no_robot', 'I am no robot')
            + "</button>";
    }

    insertJSCode(`
        const ids = ['captcha-response', 'g-recaptcha-response', 'h-captcha-response'];

        for (const id of ids) {
          const el = document.getElementById(id);
          if (!el) continue;

          const descriptor = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
          if (!descriptor || !descriptor.set) continue;
            Object.defineProperty(el, 'value', {
              set(v) {
                if (v && v.trim() !== "") {
                    E2iSendMsgToProxy({ action: "CAPTCHA_RESPONSE", response:v }, (resp) => {
                        e2ilog("CAPTCHA_RESPONSE: " + resp);
                    });
                }
                descriptor.set.call(this, v);
              },
              get() {
                return descriptor.get.call(this);
              }
            });
        }
    `);



    // Turnstile / hCaptcha / reCAPTCHA call this when the widget itself fails
    // (bad site key, blocked, browser rejected, ...). Return true = handled.
    insertJSCode(`var onCaptchaError = function (err) {
        E2iSendMsgToProxy({ action: "CAPTCHA_ERROR", error: (err === undefined || err === null || err === "") ? "no details (invalid site key / action?)" : String(err) });
        return true;
    }`);

    var callbackUrl = "" + job.callbackUrl + "";
    if (job.siteKeyType === "INVISIBLE" && callbackUrl.includes("://") && callbackUrl.endsWith('/')) {
        insertJSCode('var onResponse = function (response) {\n' +
            '            document.getElementById(\'captcha-response\').value = response;\n' +
            '        }');

        insertJSCode('function onloadCallback() {\n' +
            'grecaptcha.ready(function(){ grecaptcha.execute(); });' +
        '};');

        insertJSSrc("https://www.google.com/recaptcha/api.js?onload=onloadCallback");

    } else if (job.siteKeyAction !== undefined && job.siteKeyAction !== "undefined" && !["h1", "h1_invisible", "cf_re"].includes(job.siteKeyType)) {
        // score based reCAPTCHA (v3 / Enterprise score key): no widget, the
        // token comes from execute(siteKey, {action}). Enterprise uses its own
        // script and the grecaptcha.enterprise namespace.
        var grc = job.siteKeyType === "ENTERPRISE" ? "grecaptcha.enterprise" : "grecaptcha";
        var grcScript = job.siteKeyType === "ENTERPRISE" ? "https://www.google.com/recaptcha/enterprise.js" : "https://www.google.com/recaptcha/api.js";
        captchaContainer.querySelector("." + captchaClass).dataset.size = "invisible";
        captchaContainer.innerHTML += "<button class='invisible-captcha-button'>" + e2iText('button_please_wait', 'Please wait...')
            + "</button>";


        insertJSCode('var onResponse = function (response) {\n' +
            '            document.getElementById(\'captcha-response\').value = response;\n' +
            '        }');

        // JSON.stringify: key and action come from the address, never paste
        // them into code as raw text. A rejected execute() (bad key, action
        // refused, ...) is reported like a widget error.
        insertJSCode('function onloadCallback() {\n' +
            grc + '.ready(function() {\n' +
            '     ' + grc + '.execute(' + JSON.stringify(job.siteKey) + ', {action: ' + JSON.stringify(job.siteKeyAction) + '}).then(onResponse, onCaptchaError);\n' +
            '});\n' +
        '};');

        insertJSSrc(grcScript + "?onload=onloadCallback&render=" + encodeURIComponent(job.siteKey));

    }
    else
    {
        insertJSCode(`var onResponse = function (response) {
                        document.getElementById('captcha-response').value = response;
                    }`);


        if (job.siteKeyType === "cf_re") {
            insertJSSrc("https://challenges.cloudflare.com/turnstile/v0/api.js?compat=recaptcha");
        }
        else if (job.siteKeyType === "h1" || job.siteKeyType === "h1_invisible") {
            insertJSSrc("https://js.hcaptcha.com/1/api.js");
        } else if (job.siteKeyType === "ENTERPRISE") {
            // reCAPTCHA Enterprise (checkbox keys) ships as enterprise.js, an
            // Enterprise site key is not accepted by the classic api.js
            insertJSSrc("https://www.google.com/recaptcha/enterprise.js");
        } else {
            insertJSSrc("https://www.google.com/recaptcha/api.js");
        }

    }
};

var insertHosterName = function (hosterName) {
    if (hosterName != null && hosterName != "" && hosterName != "undefined") {
        e2ilog(Date.now() + " | inserting hostername into DOM for job " + JSON.stringify(hosterName));
        for (const container of document.getElementsByClassName("hosterName")) {
            container.textContent = hosterName.replace(/^(https?):\/\//, "");
        }
    } else {
        for (const container of document.getElementsByClassName("hideIfNoHoster")) {
            container.style.visibility = "hidden";
        }
    }
};

// Empties the page. Chrome: the classic document.open()/write()/close().
// Firefox: document.open() from a content script breaks the extension
// context there (messages to the background stop working), so the DOM is
// emptied directly and a fresh <head>/<body> is put back (that is what
// document.open() leaves behind too).
function e2iWipeDocument() {
    if (navigator.userAgent.includes('Firefox')) {
        var root = document.documentElement;
        while (root.firstChild) {
            root.firstChild.remove();
        }
        root.appendChild(document.createElement('head'));
        root.appendChild(document.createElement('body'));
    } else {
        document.open();
        document.write(""); // NOSONAR - deliberate: this classic document.open()/write()/close() is what empties the page in Chrome
        document.close();
    }
}

function E2iClearDocument() {
    e2iWipeDocument();

    // Remember that above clear all window context we need add listeners again
    E2iSetupEventListener();
}

var Params = function (url) {
    this.params = url.split("?")[1].split("&");
};

Params.prototype.get = function (name) {
    var ret;
    this.params.forEach(function (param) {
        if (param.split("=")[0] === name) {
            ret = param.split("=")[1];
        }
    });
    return ret;
};

var ParamsExt = function (url) {
    // FIX (2026-09-15): a Cloudflare "Managed Challenge" can complete via a
    // full page navigation to the plain target URL, which drops the
    // "#e2itXX_sep_..." fragment entirely - "".split("_sep_")[1] is then
    // undefined and the original code crashed here
    // ("Cannot read properties of undefined (reading 'split')") before any
    // of the callers' own fallback logic (e.g. the domain-from-hostname
    // fallback right below this constructor's call sites) ever got a
    // chance to run. Degrade to an empty param set instead of throwing -
    // every caller already tolerates missing individual params.
    try {
        this.params = (url || "").split("_sep_")[1].split("&");
    } catch (e) {
        this.params = [];
    }
};

ParamsExt.prototype.get = function (name) {
    var ret;
    this.params.forEach(function (param) {
        if (param.split("=")[0] === name) {
            ret = param.split("=")[1];
        }
    });
    return ret;
};


if (document.location.hash.startsWith("#e2itco")) {
    main_e2itco();

} else if (document.location.hash.startsWith("#e2itcf")) {
    main_e2itcf();

} else if (document.location.hash.startsWith("#e2itck")) {
    main_e2itck();

} else if (document.location.hash.startsWith("#e2itdbg")) {
    // Debug snapshot: only tell the background script to watch this tab -
    // it injects the probe (contentscripts/dbgProbe.js) after every finished
    // page load, so a Cloudflare redirect that drops this fragment does not
    // end the probe.
    E2iSendMsgToBackground({action: 'DBG_REGISTER', origin: document.location.origin}, function () {});

} else if (document.location.hash.startsWith("#e2i")) {
    E2iClearDocument();

    E2iSendMsgToBackground({action:'runMainScript'} , (resp) => {
        loadSolverTemplate(main_e2i);
    });
}


// The template ships English texts. The plugin translates them (E2iPlayer's own
// language) and mye2iserver.py hands the translated ones over in the address
// fragment (parameter "l", a JSON object), so this extension carries no
// translations of its own: a text that did not come along stays English.
window.e2i_texts = {};

function e2iText(id, english) {
    var text = window.e2i_texts[id];
    return (typeof text === 'string' && text) ? text : english;
}

function e2i_readTexts(encoded) {
    try {
        if (encoded && encoded !== 'undefined') {
            var parsed = JSON.parse(decodeURIComponent(encoded));
            if (parsed && typeof parsed === 'object') {
                window.e2i_texts = parsed;
            }
        }
    } catch (e) {
        e2ilog(Date.now() + " | ignoring the translated texts: " + e);
    }
}

function e2i_localizeTemplate() {
    ['header_please_solve', 'help_whats_happening_header', 'help_whats_happening_description', 'help_whats_happening_link'].forEach(function (id) {
        var elem = document.getElementById(id);
        var text = window.e2i_texts[id];
        if (elem && typeof text === 'string' && text) {
            elem.textContent = text;
        }
    });
}

function main_e2i(template){
    document.body.innerHTML = template;

    var params = new Params(document.location.hash);
    e2i_readTexts(params.get("l"));
    e2i_localizeTemplate();
    var siteKey = decodeURIComponent(params.get("k"));
    var siteKeyType = decodeURIComponent(params.get("st"));
    var siteKeyAction = decodeURIComponent(params.get("a"));
    var callbackUrl = decodeURIComponent(params.get("u"));
    var captchaId = decodeURIComponent(params.get("c"));
    var hoster = decodeURIComponent(params.get("h"));
    var cdata = decodeURIComponent(params.get("d"));

    e2ilog(Date.now() + " | [params] sitekey: " + siteKey + " callbackUrl: " + callbackUrl + " captchaId: " + captchaId + " hoster: " + hoster);
    window.e2i_job = {
        siteKey: siteKey,
        siteKeyType: siteKeyType,
        siteKeyAction: siteKeyAction,
        callbackUrl: callbackUrl,
        captchaId: captchaId,
        hoster: hoster,
        cdata: cdata
    };
    insertRc2ScriptIntoDOM(window.e2i_job);
    insertHosterName(window.e2i_job.hoster);
}

function e2i_checkCookiesPre(resParams) {
    if (resParams.cookies.length === 0 || Array.isArray(window.e2i_all_cookies)) {
        if (resParams.cookies.length === 0) {
            e2ilog("MyE2i cookies is an empty array.");
        }
        else
        {
            function isEqual(a, b) {
              return JSON.stringify(a) === JSON.stringify(b);
            }

            const allowed = new Set(window.e2i_cookie_names);

            window.e2i_all_cookies.push(
              ...resParams.cookies
                .filter(c => allowed.has(c.name))
                .filter(c =>
                  !window.e2i_all_cookies.some(e => isEqual(e, c))
                )
            );
        }

        
        let idx = resParams.idx;
        let cookieParams = {idx: idx+1, partition_key: {}, with_partition_key: false};
        if (window.e2i_cookie_names.length == 1) {
            cookieParams.name = window.e2i_cookie_names[0];
        }

        if (idx === 0 || idx === 2) {
            cookieParams.type = 'domain';

            let params = new ParamsExt(document.location.hash);
            let domain = decodeURIComponent(params.get("domain"));
            if (domain === undefined || domain + '' == 'undefined' || domain === null || domain === '') {
                let url = new URL(document.location.href);
                domain = url.hostname;
                let parts = domain.split('.');
                let baseDomain = parts.length > 2 ? parts.slice(-2).join('.') : domain;
                domain = '.' + baseDomain;
            }

            cookieParams.domain = domain;
            if (idx === 0) {
                cookieParams.with_partition_key = true;
            }

        } else if (idx === 1 || idx === 3) {
            cookieParams.type = 'url';
            cookieParams.url = document.location.href;

            if (idx === 1) {
                cookieParams.with_partition_key = true;
            }
        } else {
            let resCookies = [];
            if (Array.isArray(window.e2i_all_cookies)) {
                resCookies = window.e2i_all_cookies;
            } else {
                resCookies = resParams.cookies;
            }
            
            e2ilog("MyE2i cookies found2:", resCookies);
            e2i_checkCookies(resCookies);
            return;
        }

        e2ilog("MyE2i sending GET_COOKIE query:", JSON.stringify(cookieParams));
        chrome.runtime.sendMessage({
            action: "GET_COOKIE",
            data: cookieParams
        }, e2i_checkCookiesPre);

    } else {
        e2ilog("MyE2i cookies found:", resParams.cookies);
        e2i_checkCookies(resParams.cookies);
    }
}

function e2i_checkCookies(cookie) {
    let url = new URL(document.location.href);
    let domain = '.' + url.hostname;
    let result = {user_agent:navigator.userAgent,
                  cookie:cookie,
                  url:document.location.href,
                  domain:domain}
    e2ilog("MyE2i FINAL result being sent:", JSON.stringify(result));
    let params = new ParamsExt(document.location.hash);
    window.e2i_job = {callbackUrl: decodeURIComponent(params.get("u")),
                      captchaId: decodeURIComponent(params.get("c"))};
    let token = window.btoa(JSON.stringify(result));

    var response = {
        action: "SEND_RESPONSE",
        response: {
            token: token,
            callbackUrl: e2i_job.callbackUrl,
            captchaId: e2i_job.captchaId
        }
    };

    E2iSendMsgToBackground(response, (resp) => {
        E2iSendMsgToBackground({'action':'CLOSE_ME'}, (resp2) => {
            cb('OK');
        });
    });
}
    
// Substrings of the interstitial pages of the common bot-protection systems
// (kept in step with libs/botprotection.py on the box).
var E2I_CHALLENGE_MARKERS = ['just a moment', 'cf-chl', '_cf_chl_opt', '/cdn-cgi/challenge-platform', 'ddos-guard', 'sucuri_cloudproxy_js',
    '_incapsula_resource', "making sure you", 'anubis', 'px-captcha', 'captcha-delivery.com', 'awswafintegration', 'vercel security checkpoint',
    'checking your browser', 'verifying you are human', 'press & hold', 'press &amp; hold'];

// Interstitials are small pages. A big page that merely mentions one of the
// words (a "protected by DDoS-Guard" footer) is a normal page.
function e2iLooksLikeAnyChallenge() {
    try {
        var html = document.documentElement.innerHTML;
        if (html.length > 60000) {
            return false;
        }
        html = (document.title + ' ' + html).toLowerCase();
        for (const marker of E2I_CHALLENGE_MARKERS) {
            if (html.includes(marker)) {
                return true;
            }
        }
    } catch (e) {
        // a page that cannot be read is not treated as a check page
    }
    return false;
}

// Generic "cookie mode" (#e2itck): open the page, wait until no known check is
// showing any more and the page stopped changing, then send back EVERY cookie
// of the site plus the User-Agent (DDoS-Guard, Sucuri, Imperva, Anubis,
// DataDome, ... - whatever ends in cookies).
function main_e2itck() {
    e2ilog(Date.now() + " | cookie mode started on " + document.location.href);
    window.e2i_cookie_names = [];   // no name filter, take everything

    var startTs = Date.now();
    var lastChange = Date.now();
    var CHALLENGE_LIMIT_MS = 600000;
    var done = false;

    try {
        new MutationObserver(function () { lastChange = Date.now(); })
            .observe(document.documentElement || document, {childList: true, subtree: true, characterData: true});
    } catch (e) {}

    var timer = setInterval(function () {
        if (done || document.readyState !== "complete" || !document.body) {
            return;
        }
        var now = Date.now();
        if (e2iLooksLikeAnyChallenge()) {
            lastChange = now;
            if (now - startTs < CHALLENGE_LIMIT_MS) {
                return;
            }
            e2ilog(now + " | cookie mode: still a check page after 10 min, sending what there is");
        }
        if (now - lastChange < 2500 || now - startTs < 3000) {
            return;
        }
        done = true;
        clearInterval(timer);
        e2ilog(now + " | cookie mode: page settled, collecting cookies");
        e2iWipeDocument();
        e2i_checkCookiesPre({cookies: [], idx: 0});
    }, 500);
}

function main_e2itcf(){
    window.e2i_cookie_names = ['cf_clearance'];

    // FIX (2026-09-15): the previous implementation decided "challenge is
    // done" on the very first readystatechange event where #challenge-form
    // happened to be absent, using a one-shot "_kanikulye2ikaramba" flag
    // that (a) could fire true before Cloudflare had even inserted its
    // challenge-form/link/script markers into the DOM yet (race on fast
    // "Managed Challenge" pages -> false "done" with an empty/invalid
    // cf_clearance cookie sent back immediately), and (b) relied entirely
    // on readystatechange firing again later, which it does NOT do for an
    // in-place DOM removal of the challenge widget without a full page
    // navigation. Rewritten to only ever conclude "done" once
    // document.readyState is "complete" (real content, not a half-parsed
    // shell), to check ALL <link>/<script> tags (not just index 0) plus a
    // document.title fallback ("Just a moment...") as extra markers, and
    // to also watch for in-place DOM mutations via MutationObserver so a
    // challenge widget removed without a full reload is still detected.
    var e2i_cfDone = false;

    function e2i_looksLikeChallengePage() {
        try {
            if (document.getElementById("challenge-form")) return true;
        } catch (e) {}
        try {
            for (const link of document.getElementsByTagName("link")) {
                const href = link.getAttribute("href");
                if (href?.includes('/challenges')) return true;
            }
        } catch (e) {
            // not readable: this check finds nothing
        }
        try {
            for (const script of document.getElementsByTagName('script')) {
                if (script.text?.includes("window._cf_chl_opt")) return true;
            }
        } catch (e) {
            // not readable: this check finds nothing
        }
        try {
            if (document.title?.includes("Just a moment")) return true;
        } catch (e) {
            // not readable: this check finds nothing
        }
        return false;
    }

    function e2i_reportChallengeDoneIfReady() {
        if (e2i_cfDone) return;
        if (document.readyState !== "complete") return;
        if (!document.body) return;
        if (e2i_looksLikeChallengePage()) return;

        e2i_cfDone = true;
        try { document.removeEventListener('readystatechange', e2i_reportChallengeDoneIfReady); } catch (e) {}
        try { e2i_cfObserver.disconnect(); } catch (e) {}

        e2iWipeDocument();

        e2i_checkCookiesPre({cookies:[], idx:0});
    }

    document.addEventListener('readystatechange', e2i_reportChallengeDoneIfReady);

    var e2i_cfObserver = new MutationObserver(function () {
        e2i_reportChallengeDoneIfReady();
    });
    try {
        e2i_cfObserver.observe(document.documentElement || document, {childList: true, subtree: true});
    } catch (e) {}

    // covers the case where this script runs after the document already
    // finished loading (readystatechange for "complete" already fired)
    e2i_reportChallengeDoneIfReady();
}

function HandleStatusCode(data)
{
    if (data.url.includes("#e2itco") && data.status == 200)
    {
        if (!window.e2i_challenge_id || document.getElementById(window.e2i_challenge_id) == null)
        {
            e2iWipeDocument();
            e2i_checkCookiesPre({cookies:[], idx:0});
        }
    }
}

function main_e2itco()
{
    let params = new ParamsExt(document.location.hash);
    let cn = decodeURIComponent(params.get("cn"));
    let ceid = params.get("ceid");
    if (ceid)
    {
        window.e2i_challenge_id = decodeURIComponent(ceid);
    }

    window.e2i_all_cookies = []; //;
    window.e2i_cookie_names = JSON.parse(window.atob(cn));
    
    
    
    function e2i_checkChallengeForm(event) {
        if (document.readyState == "complete")
        {
            E2iSendMsgToBackground({
                action: 'PROXY_READY'
            }, (resp2) => {
                //
            });
        }
    }
    document.addEventListener('readystatechange', e2i_checkChallengeForm);
}

// Firefox hands the script's completion value back to scripting.executeScript()
// and fails if it is not structured-cloneable - end with a plain undefined.
undefined; // NOSONAR - deliberate, see above
