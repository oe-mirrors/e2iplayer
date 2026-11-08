'use strict';

// NAV job probe: injected by scripts/background.js into every finished page of a tab that started with an
// "#e2itnv" fragment (the site's own redirects drop that fragment, the background script keeps the job).
// It waits until a link matching the job's pattern shows up - the element of the job's CSS selector first, then
// any <a href> of the page - and hands it to the background script, which sends it to the receiver. The job
// (selector, attribute, pattern) was put into window.__e2iNavJob by the background script right before.
// v1.23, job.load (l=1): a found link is opened in this tab instead of being reported; on the loaded page (its
// address matches the pattern) the probe waits until the page made the request of job.fetch (a regex), asks
// that address once more from here - the site sees this browser - and reports the page with that answer.
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

    function report(url, data) {
        const msg = {action: 'NAV_FOUND', url: url};
        if (typeof data === 'string') {
            msg.data = data;
        }
        chrome.runtime.sendMessage(msg, function () {
            if (chrome.runtime.lastError) {
                // the tab is being closed by the background script
            }
        });
    }

    if (job.load && pattern.test(location.href)) {
        // the loaded target page: its own request first, then the same address once more from here
        let fetchPattern = null;
        try {
            fetchPattern = job.fetch ? new RegExp(job.fetch) : null;
        } catch (e) {
            console.log('[MyE2i-DEBUG nav] bad fetch pattern', job.fetch, e);
        }
        if (!fetchPattern) {
            report(location.href);
            return;
        }
        const waitTimer = setInterval(function () {
            const entry = performance.getEntriesByType('resource').find(function (e) {
                return fetchPattern.test(e.name);
            });
            if (entry) {
                clearInterval(waitTimer);
                fetch(entry.name, {credentials: 'include'}).then(function (r) {
                    return r.text();
                }).then(function (text) {
                    report(location.href, text);
                }).catch(function (e) {
                    report(location.href, '');
                    console.log('[MyE2i-DEBUG nav] fetch failed', e);
                });
            } else if (Date.now() - started > 30000) {
                clearInterval(waitTimer);
                report(location.href, '');
            }
        }, POLL_MS);
        return;
    }

    const timer = setInterval(function () {
        const value = find();
        if (value) {
            clearInterval(timer);
            if (job.load) {
                // the page would only get there on a click - open it here (once per page)
                location.href = value;
            } else {
                report(value);
            }
        } else if (Date.now() - started > MAX_MS) {
            clearInterval(timer);
        }
    }, POLL_MS);
})();
