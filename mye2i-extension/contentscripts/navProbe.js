'use strict';

// NAV job probe: injected by scripts/background.js into every finished page of a tab that started with an
// "#e2itnv" fragment (the site's own redirects drop that fragment, the background script keeps the job).
// It waits until a link matching the job's pattern shows up - the element of the job's CSS selector first, then
// any <a href> of the page - and hands it to the background script, which sends it to the receiver. The job
// (selector, attribute, pattern) was put into window.__e2iNavJob by the background script right before.
(function () {
    const job = window.__e2iNavJob || {};
    if (window.__e2iNavProbeRunning || !job.pattern) {
        return;
    }
    window.__e2iNavProbeRunning = true;

    const POLL_MS = 500;
    const MAX_MS = 180000; // a countdown page plus a slow phone - the background script ends the job anyway
    // anti-scraper decoys some gateways plant (hidden link sinks the page removes again after its own check)
    const DECOY_IDS = ['cs-link-sink', 'cs-payload'];
    let pattern;
    try {
        pattern = new RegExp(job.pattern);
    } catch (e) {
        console.log('[MyE2i-DEBUG nav] bad pattern', job.pattern, e);
        return;
    }
    const attr = job.attr || 'href';
    const started = Date.now();

    function valueOf(el) {
        if (!el || DECOY_IDS.includes(el.id) || el.hasAttribute('data-qs')) {
            return '';
        }
        // .href is the absolute address; getAttribute() for any other attribute (data-url, src, ...)
        const value = attr === 'href' && el.href ? el.href : el.getAttribute(attr);
        return value && pattern.test(value) ? value : '';
    }

    function find() {
        if (job.selector) {
            for (const el of document.querySelectorAll(job.selector)) {
                const value = valueOf(el);
                if (value) {
                    return value;
                }
            }
        }
        for (const el of document.querySelectorAll('a[href]')) {
            const value = valueOf(el);
            if (value) {
                return value;
            }
        }
        return '';
    }

    const timer = setInterval(function () {
        const value = find();
        if (value) {
            clearInterval(timer);
            chrome.runtime.sendMessage({action: 'NAV_FOUND', url: value}, function () {
                if (chrome.runtime.lastError) {
                    // the tab is being closed by the background script
                }
            });
        } else if (Date.now() - started > MAX_MS) {
            clearInterval(timer);
        }
    }, POLL_MS);
})();
