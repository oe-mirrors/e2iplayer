'use strict';

function e2ilog(...args) {
    console.log("[MyE2i-DEBUG bg]", ...args);
}

// Match pattern of the local relay page (e2it.html) that mye2iserver.py serves on the box, in the
// LAN over plain http - it is not a link to any website.
const E2IT_TAB_URL = "http://*/e2it.html*"; // NOSONAR

// Failures worth seeing on the box (not just in the extension's own console):
// forwarded to the open e2it.html tab, which posts them to mye2iserver.py.
function e2iBoxLog(msg) {
    e2ilog(msg);
    chrome.tabs.query({url: [E2IT_TAB_URL]}, function (tabs) {
        if (tabs !== undefined && tabs.length > 0) {
            chrome.tabs.sendMessage(tabs[0].id, {action: "DEBUG_LOG", msg: '[bg] ' + msg}, function () {
                if (chrome.runtime.lastError) {
                    // reading it is what keeps Chrome from logging "Unchecked runtime.lastError"
                }
            });
        }
    });
}

function E2iSendMsgTo(to, tabId, payload, cb) {
    chrome.tabs.sendMessage(tabId, {
        __MYE2I: true,
        to,
        from: 'FROM_BACKGROUND',
        payload
    }, cb);

}

function E2iSendMsgToProxy(tabId, payload, cb) {
    E2iSendMsgTo('TO_PROXY', tabId, payload, cb);
}

function E2iSendMsgToPage(tabId, payload, cb) {
    E2iSendMsgTo('TO_PAGE', tabId, payload, cb);
}

const readyTabs = new Set();
const lastStatus = new Map();

chrome.tabs.onRemoved.addListener((tabId) => {
  readyTabs.delete(tabId);
  lastStatus.delete(tabId);
  dbgRemoveTab(tabId);
  navTakeJob(tabId);
});

// A result for the receiver goes to the open local e2it.html tab, which passes it on to mye2iserver.py
// (/response). The token is sent as it is - e2it.js percent-encodes it.
function e2iRelayResponse(captchaId, token, cb) {
    chrome.tabs.query({
        url: [E2IT_TAB_URL]
    }, function (tabs) {
        if (tabs !== undefined && tabs.length > 0) {
            for (const tab of tabs) {
                chrome.tabs.sendMessage(tab.id, {
                    action: "SEND_RESPONSE",
                    data: {captchaId: captchaId, token: token}
                });
            }
        }
        if (cb) {
            cb('DONE');
        }
    });
}

// ---- NAV jobs ------------------------------------------------------------
// A tab opened with "#e2itnv" (contentscripts/rc2ContentscriptProxy.js -> NAV_REGISTER) is followed across the
// site's own redirects, which drop the fragment: contentscripts/navProbe.js is injected into every finished page
// of the tab and reports the first link that matches the job's pattern (NAV_FOUND); a top-level navigation to
// such an address (a click, a script redirect) counts too. The link goes to the receiver as the usual base64
// JSON result {url, user_agent, cookie, links} and the tab is closed, before the page could use a one-time
// token itself. Jobs live in chrome.storage.session - the service worker is suspended after ~30 s idle.
async function navGetJobs() {
    const stored = await chrome.storage.session.get('navJobs');
    return stored.navJobs || {};
}

async function navSetJob(tabId, job) {
    const jobs = await navGetJobs();
    jobs[tabId] = job;
    await chrome.storage.session.set({navJobs: jobs});
}

async function navTakeJob(tabId) {
    try {
        const jobs = await navGetJobs();
        const job = jobs[tabId];
        if (job) {
            delete jobs[tabId];
            await chrome.storage.session.set({navJobs: jobs});
        }
        return job;
    } catch (e) {
        e2ilog('nav job cleanup failed: ' + e);
        return undefined;
    }
}

function navInjectProbe(tabId, job) {
    chrome.scripting.executeScript({
        target: {tabId},
        func: (j) => { window.__e2iNavJob = j; },
        args: [{selector: job.selector || '', attr: job.attr || 'href', pattern: job.pattern || ''}]
    }).then(() => chrome.scripting.executeScript({
        target: {tabId},
        files: ['contentscripts/navProbe.js']
    })).catch((e) => e2iBoxLog('nav probe injection failed: ' + e));
}

function navMatches(job, url) {
    try {
        return !!job && !!job.pattern && new RegExp(job.pattern).test(url);
    } catch (e) {
        return false;
    }
}

async function navFinish(tabId, url) {
    const job = await navTakeJob(tabId);
    if (!job) {
        return;
    }
    e2iBoxLog('nav job ' + job.captchaId + ': link found');
    const result = {user_agent: navigator.userAgent, cookie: [], url: url, links: [url]};
    // UTF-8 first: btoa() throws on anything outside Latin-1
    const token = btoa(unescape(encodeURIComponent(JSON.stringify(result))));
    e2iRelayResponse(job.captchaId, token, () => {
        chrome.tabs.remove(tabId).catch(() => {});
    });
}

chrome.webNavigation.onBeforeNavigate.addListener(async (details) => {
    if (details.frameId !== 0) {
        return;
    }
    const jobs = await navGetJobs();
    if (navMatches(jobs[details.tabId], details.url)) {
        navFinish(details.tabId, details.url);
    }
});

// ---- Firefox: inject the fragment-triggered content scripts ------------
// Chrome runs contentscripts/rc2ContentscriptProxy.js (and, for the debug
// snapshot, dbgHook.js) via manifest "include_globs": ["*#e2it*"]. Firefox
// matches globs without the URL fragment, so those manifest entries never
// fire there - the Firefox build (build_release.py --firefox) leaves them
// out and this listener injects the same files as soon as a top-level
// navigation with an "#e2it" fragment commits.
const IS_FIREFOX = typeof navigator !== 'undefined' && navigator.userAgent.includes('Firefox');

if (IS_FIREFOX) {
    chrome.webNavigation.onCommitted.addListener(async (details) => {
        if (details.frameId !== 0 || !details.url.includes('#e2it')) {
            return;
        }
        const target = {tabId: details.tabId};
        try {
            if (details.url.includes('#e2itdbg')) {
                await chrome.scripting.executeScript({
                    target,
                    files: ['contentscripts/dbgHook.js'],
                    world: 'MAIN',
                    injectImmediately: true
                });
            }
            await chrome.scripting.executeScript({
                target,
                files: ['contentscripts/rc2ContentscriptProxy.js'],
                injectImmediately: true
            });
        } catch (e) {
            e2iBoxLog('fragment script injection failed: ' + e);
        }
    });
}

// ---- Debug snapshot support -------------------------------------------
// A tab opened with "#e2itdbg" registers itself here (DBG_REGISTER). The
// probe script is injected after every finished load of such a tab, because
// a Cloudflare challenge can reload the page and drop the fragment. The tab
// list lives in chrome.storage.session: a MV3 service worker is suspended
// after ~30 s idle and would otherwise forget the tab while the user is
// still solving the challenge.
const DBG_HOOK_ID = 'e2i-dbg-hook';

async function dbgGetTabs() {
    const stored = await chrome.storage.session.get('dbgTabs');
    return stored.dbgTabs || [];
}

async function dbgAddTab(tabId) {
    const tabs = await dbgGetTabs();
    if (!tabs.includes(tabId)) {
        tabs.push(tabId);
        await chrome.storage.session.set({dbgTabs: tabs});
    }
    // fetch()/XHR recorder, also for pages reached after a redirect (the
    // static manifest entry only covers URLs that still carry the fragment)
    try { await chrome.scripting.unregisterContentScripts({ids: [DBG_HOOK_ID]}); } catch (e) {}
    try {
        await chrome.scripting.registerContentScripts([{
            id: DBG_HOOK_ID,
            js: ['contentscripts/dbgHook.js'],
            matches: ['<all_urls>'],
            runAt: 'document_start',
            world: 'MAIN',
            allFrames: false,
            persistAcrossSessions: false
        }]);
    } catch (e) {
        e2iBoxLog('debug hook registration failed: ' + e);
    }
}

async function dbgRemoveTab(tabId) {
    try {
        const tabs = await dbgGetTabs();
        if (!tabs.includes(tabId)) {
            return;
        }
        const left = tabs.filter((id) => id !== tabId);
        await chrome.storage.session.set({dbgTabs: left});
        if (left.length === 0) {
            try { await chrome.scripting.unregisterContentScripts({ids: [DBG_HOOK_ID]}); } catch (e) {}
        }
    } catch (e) {
        e2ilog('debug tab cleanup failed: ' + e);
    }
}

function dbgInjectProbe(tabId) {
    chrome.scripting.executeScript({
        target: {tabId},
        files: ['contentscripts/dbgProbe.js']
    }).catch((e) => e2iBoxLog('probe injection failed: ' + e));
}

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo) => {
    if (changeInfo.status !== 'complete') {
        return;
    }
    const tabs = await dbgGetTabs();
    if (tabs.includes(tabId)) {
        dbgInjectProbe(tabId);
    }
    const jobs = await navGetJobs();
    if (jobs[tabId]) {
        navInjectProbe(tabId, jobs[tabId]);
    }
});

/*
chrome.webNavigation.onCommitted.addListener((details) => {
  if (details.frameId === 0) {
    readyTabs.delete(details.tabId);
    lastStatus.delete(details.tabId);
  }
});
*/

function SendHttpStatus(tabId) {
    if (readyTabs.has(tabId)) {
        const data = lastStatus.get(tabId);
        if (data) {
            E2iSendMsgToProxy(tabId, {
                action: "HTTP_STATUS",
                ...data
            });
        }
    }
}

chrome.webRequest.onCompleted.addListener(
    (details) => {
    if (details.tabId >= 0 && details.type === "main_frame" && details.url.includes("#e2itco")) {
      lastStatus.set(details.tabId, {
        status: details.statusCode,
        url: details.url
      });
      //SendHttpStatus(details.tabId);
    }
}, {
    urls: ["<all_urls>"]
});


chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {

    // debug snapshot sections can be megabytes - only log the start
    e2ilog('MESSAGE IN BACGROUND chrome.runtime.onMessag(): ' + JSON.stringify(msg).slice(0, 500));

    const tabId = sender.tab.id;

    if (msg.action === "PROXY_READY") {
        readyTabs.add(tabId);
        SendHttpStatus(tabId);
        sendResponse('OK');
    }
    
    if (msg.action === "runMainScript") {
            chrome.scripting.executeScript({
            target: { tabId },
            world: 'MAIN',
            files: ["contentscripts/rc2Contentscript.js"]
        }).then(sendResponse);
    }

    if (msg.action === "CLOSE_ME" && sender.tab?.id) {
        chrome.tabs.remove(sender.tab.id);
        sendResponse('OK');
    }

    if (msg.action === "GET_COOKIE") {

        let request = msg.data;

        //chrome.cookies.getAll
        let cookieParams =  {};
        if (request.name) {
            cookieParams.name = request.name;
        }

        if (request.type === 'domain') {
            e2ilog("MyE2i get base on domain " + request.domain);
            cookieParams.domain = request.domain;
        }

        if (request.type === 'url') {
            e2ilog("MyE2i get base on url " + request.url);
            cookieParams.url = request.url;
        }

        if (request.with_partition_key === true) {
            e2ilog("MyE2i with partition key " + JSON.stringify(request.partition_key));
            cookieParams.partitionKey = request.partition_key;
        }

        try {
            chrome.cookies.getAll(cookieParams, function(cookies){
                if (chrome.runtime.lastError) {
                    e2ilog("MyE2i cookie query failed: " + chrome.runtime.lastError.message);
                }
                e2ilog("MyE2i cookie callback!");
                e2ilog("MyE2i get cookies: " + JSON.stringify(cookies));
                sendResponse({cookies: cookies || [], idx:request.idx})
             });
        } catch(e) {
            e2ilog("MyE2i cookie getAll error! Remove partitionKey!");
            if (request.with_partition_key === true) {
                delete cookieParams.partitionKey;

                chrome.cookies.getAll(cookieParams, function(cookies){
                    e2ilog("MyE2i cookie callback after removing partitionKey!");
                    e2ilog("MyE2i get cookies: " + JSON.stringify(cookies));
                    sendResponse({cookies: cookies || [], idx:request.idx})
                 });
            }
        }

        //chrome.cookies.getAll({url: request.url, name: request.name}, sendResponse);
        //chrome.cookies.getAll({url: request.url}, sendResponse);
        // keep sendResponse channel open
        return true;

    }

    if (msg.action === "DEBUG_LOG") {
        // Debug lines from the challenge tab go to the local e2it.html tab (same relay
        // pattern as SEND_RESPONSE), which passes them on to mye2iserver.py.
        chrome.tabs.query({
            url: [E2IT_TAB_URL]
        }, function (tabs) {
            if (tabs !== undefined && tabs.length > 0) {
                for (const tab of tabs) {
                    chrome.tabs.sendMessage(tab.id, {
                        action: "DEBUG_LOG",
                        msg: msg.msg
                    });
                }
            }
            sendResponse('DONE');
        });
        return true;
    }

    if (msg.action === "DBG_REGISTER") {
        dbgAddTab(tabId).then(() => {
            sendResponse('OK');
            // a small page can already be "complete" before the tab was
            // stored above (the onUpdated listener then found nothing to
            // do) - inject right away in that case. The probe guards itself
            // against running twice.
            chrome.tabs.get(tabId, (tab) => {
                if (tab?.status === 'complete') {
                    dbgInjectProbe(tabId);
                }
            });
        });
        return true;
    }

    if (msg.action === "NAV_REGISTER") {
        navSetJob(tabId, msg.job || {}).then(() => {
            sendResponse('OK');
            // the start page may already be loaded (same as DBG_REGISTER) - its probe finds nothing and waits
            chrome.tabs.get(tabId, (tab) => {
                if (tab?.status === 'complete') {
                    navInjectProbe(tabId, msg.job || {});
                }
            });
        });
        return true;
    }

    if (msg.action === "NAV_FOUND") {
        navFinish(tabId, msg.url).then(() => sendResponse('OK'));
        return true;
    }

    if (msg.action === "DBG_DONE") {
        dbgRemoveTab(tabId).then(() => sendResponse('OK'));
        return true;
    }

    if (msg.action === "DEBUG_DUMP") {
        // one section of the debug snapshot: hand it to the still-open local
        // e2it.html tab, which POSTs it to mye2iserver.py (/debugdump).
        chrome.tabs.query({
            url: [E2IT_TAB_URL]
        }, function (tabs) {
            if (tabs === undefined || tabs.length === 0) {
                sendResponse('NO_E2IT_TAB');
                return;
            }
            chrome.tabs.sendMessage(tabs[0].id, {
                action: "DEBUG_DUMP",
                name: msg.name,
                data: msg.data
            }, function (resp) {
                sendResponse(resp || 'DONE');
            });
        });
        return true;
    }

    if (msg.action === "SEND_RESPONSE") {
        let response = msg.response;

        let callbackUrl = "" + response.callbackUrl + "";
        if (callbackUrl.includes("://") && callbackUrl.endsWith('/')) {
            callbackUrl += "response?" + "c=" + response.captchaId + "&token=" + response.token;
            const xhr = new XMLHttpRequest();
            xhr.onload = function () {
                e2ilog(Date.now() + " | response send OK");
                sendResponse('OK');
            };
            xhr.onerror = function () {
                e2ilog(Date.now() + " | response send FAILED");
                sendResponse('ERROR');
            };
            xhr.open("GET", callbackUrl);
            xhr.responseType = "text";
            xhr.send();
        } else {
            e2iRelayResponse(response.captchaId, response.token, sendResponse);
        }
        
    }

  return true;
});
