
function e2ilog(txt) {
    //console.log(txt);
}

// The page script and the extension's proxy script talk through window.postMessage of the very
// same window. A message only counts when this window sent it (e.source) and it carries the
// page's own origin; messages are posted to that origin ("/") only, never to '*'.
function E2iIsOwnMessage(e) {
    return e.source === window && e.origin === window.location.origin;
}

function E2iSendMsgTo(to, payload, cb) {
    const id = Math.random().toString(36).slice(2); // NOSONAR - only pairs a reply with its request, not a secret
    if (cb !== undefined)
    {
        function onResp(e) {
            if (!E2iIsOwnMessage(e))
                return;
            const m = e.data;
            if (m?.__MYE2I !== true || m.to !== 'TO_PAGE_RESPONSE' || m.id !== id)
                return;
            window.removeEventListener('message', onResp);
            cb?.(m.response);
        }

        window.addEventListener('message', onResp);
    }

    window.postMessage({
        __MYE2I: true,
        to,
        from: 'FROM_PAGE',
        id,
        payload
    }, '/');
}

function E2iSendMsgToProxy(payload, cb) {
    E2iSendMsgTo('TO_PROXY', payload, cb);
}

window.addEventListener('message', (e) => {
    if (!E2iIsOwnMessage(e))
        return;
    const msg = e.data;
    if (msg?.__MYE2I !== true)
        return;

    if (msg.to === 'TO_PAGE' && msg.from === 'FROM_PROXY' ) {
        E2iHandleMessage(msg.payload, (resp) => {
            window.postMessage({
                __MYE2I: true,
                from: 'FROM_PAGE',
                to: 'TO_PROXY_RESPONSE',
                id: msg.id,
                response: resp
            }, '/');
        });
    }

    if (msg.to === 'TO_PAGE' && msg.from === 'FROM_BACKGROUND' ) {
        E2iHandleMessage(msg.payload, (resp) => {
            window.postMessage({
                __MYE2I: true,
                from: 'FROM_PAGE',
                to: 'TO_BACKGROUND_RESPONSE',
                id: msg.id,
                response: resp
            }, '/');
        });
    }

});


function E2iHandleMessage(msg, cb)
{
    e2ilog('MESSAGE IN PAGE E2iHandleMessage(): ' + JSON.stringify(msg));

    if (msg.action == 'INSERT_JS_CODE') {
        insertJSCode(msg.jscode, cb);
    }

    if (msg.action == 'INSERT_JS_SRC') {
        insertJSSrc(msg.jssrc, cb);
    }

}


function insertJSCode(jscode, cb) {
    let elem = document.createElement('script');
    elem.type = 'text/javascript';
    elem.text = jscode;
    elem.onload = function () {
        cb('Done');
    };
    document.body.appendChild(elem);
}

// The only scripts the proxy ever asks for: the captcha widgets. Anything else is refused.
var E2I_ALLOWED_SCRIPT_SRC = /^https:\/\/(www\.google\.com\/recaptcha\/|challenges\.cloudflare\.com\/turnstile\/|js\.hcaptcha\.com\/)/;

function insertJSSrc(jssrc, cb) {
    if (!E2I_ALLOWED_SCRIPT_SRC.test(String(jssrc))) {
        e2ilog('INSERT_JS_SRC refused: ' + jssrc);
        cb('Refused');
        return;
    }
    let elem = document.createElement('script');
    elem.type = 'text/javascript';
    elem.src = jssrc; // NOSONAR - checked against the captcha script allow-list above
    elem.onload = function () {
        cb('Done');
    };
    document.body.appendChild(elem);
}


