'use strict';

function e2ilog(...args) {
    console.log("[MyE2i-DEBUG bg]", ...args);
}

// Failures worth seeing on the box (not just in the extension's own console):
// forwarded to the open e2it.html tab, which posts them to mye2iserver.py.
function e2iBoxLog(msg) {
    e2ilog(msg);
    chrome.tabs.query({url: ["http://*/e2it.html*"]}, function (tabs) {
        if (tabs !== undefined && tabs.length > 0) {
            chrome.tabs.sendMessage(tabs[0].id, {action: "DEBUG_LOG", msg: '[bg] ' + msg}, function () {
                void chrome.runtime.lastError;
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
});

// ---- Firefox: inject the fragment-triggered content scripts ------------
// Chrome runs contentscripts/rc2ContentscriptProxy.js (and, for the debug
// snapshot, dbgHook.js) via manifest "include_globs": ["*#e2it*"]. Firefox
// matches globs without the URL fragment, so those manifest entries never
// fire there - the Firefox build (build_release.py --firefox) leaves them
// out and this listener injects the same files as soon as a top-level
// navigation with an "#e2it" fragment commits.
const IS_FIREFOX = typeof navigator !== 'undefined' && navigator.userAgent.indexOf('Firefox') !== -1;

if (IS_FIREFOX) {
    chrome.webNavigation.onCommitted.addListener(async (details) => {
        if (details.frameId !== 0 || details.url.indexOf('#e2it') === -1) {
            return;
        }
        const target = {tabId: details.tabId};
        try {
            if (details.url.indexOf('#e2itdbg') !== -1) {
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

    if (msg.action === "CLOSE_ME" && sender.tab && sender.tab.id) {
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
            url: ["http://*/e2it.html*"]
        }, function (tabs) {
            if (tabs !== undefined && tabs.length > 0) {
                for (var i = 0; i < tabs.length; i++) {
                    chrome.tabs.sendMessage(tabs[i].id, {
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
                if (tab && tab.status === 'complete') {
                    dbgInjectProbe(tabId);
                }
            });
        });
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
            url: ["http://*/e2it.html*"]
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
            var xhr = new XMLHttpRequest();
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
            chrome.tabs.query({
                url: [
                    "http://*/e2it.html*"
                ]
            }, function (tabs) {
                if (tabs !== undefined && tabs.length > 0) {
                    for (var i = 0; i < tabs.length; i++) {
                        chrome.tabs.sendMessage(tabs[i].id, {
                            action: "SEND_RESPONSE",
                            data: {captchaId: response.captchaId, token: response.token}
                        });
                    }
                }
                sendResponse('DONE');
            })
        }
        
    }

  return true;
});
