
function e2ilog(txt) {
    //console.log(txt);
}

function E2iSendMsgTo(to, payload, cb) {
    const id = Math.random().toString(36).slice(2);
    if (cb !== undefined)
    {
        function onResp(e) {
            if (e.source !== window)
                return;
            const m = e.data;
            if (!m || m.__MYE2I !== true || m.to !== 'TO_PAGE_RESPONSE' || m.id !== id)
                return;
            window.removeEventListener('message', onResp);
            cb && cb(m.response);
        }

        window.addEventListener('message', onResp);
    }

    window.postMessage({
        __MYE2I: true,
        to,
        from: 'FROM_PAGE',
        id,
        payload
    }, '*');
}

function E2iSendMsgToProxy(payload, cb) {
    E2iSendMsgTo('TO_PROXY', payload, cb);
}

window.addEventListener('message', (e) => {
    if (e.source !== window)
        return;
    const msg = e.data;
    if (!msg || msg.__MYE2I !== true)
        return;

    if (msg.to === 'TO_PAGE' && msg.from === 'FROM_PROXY' ) {
        E2iHandleMessage(msg.payload, (resp) => {
            window.postMessage({
                __MYE2I: true,
                from: 'FROM_PAGE',
                to: 'TO_PROXY_RESPONSE',
                id: msg.id,
                response: resp
            }, '*');
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
            }, '*');
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

function insertJSSrc(jssrc, cb) {
    let elem = document.createElement('script');
    elem.type = 'text/javascript';
    elem.src = jssrc;
    elem.onload = function () {
        cb('Done');
    };
    document.body.appendChild(elem);
}


