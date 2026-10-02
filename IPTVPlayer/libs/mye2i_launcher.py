# -*- coding: utf-8 -*-
#
# The "open in" link of the MyE2i start page. A phone's camera opens the scanned
# address in the default browser, on Android mostly Chrome, which has no
# extensions. A tap on an Android intent:// address there opens the page in the
# chosen browser (one that can run the MyE2i extension); "custom" takes the user's
# own launcher URI with {url} (the whole http address) or {address} (the same
# without "http://") in it. Not in the QR code itself: camera apps and Google Lens
# do not pass an intent:// address on.

# browser -> Android package
BROWSER_PACKAGES = {
    'kiwi': 'com.kiwibrowser.browser',
    'yandex': 'com.yandex.browser',
    'edge': 'com.microsoft.emmx',
    # separate apps with their own package; Edge on Android runs extensions only in Canary so far
    'edge_canary': 'com.microsoft.emmx.canary',
    'edge_beta': 'com.microsoft.emmx.beta',
    'edge_dev': 'com.microsoft.emmx.dev',
}


def getLauncherUrl(url, browser='', template=''):
    # url: the box's http address ("http://192.168.1.2:9001/?t=..."); browser: '' (default
    # browser), a key of BROWSER_PACKAGES or 'custom'; template: the own launcher URI
    address = url.split('://', 1)[-1]
    if browser in BROWSER_PACKAGES:
        return 'intent://%s#Intent;scheme=http;package=%s;end' % (address, BROWSER_PACKAGES[browser])
    if browser == 'custom':
        template = (template or '').strip()
        if '{url}' in template or '{address}' in template:
            return template.replace('{url}', url).replace('{address}', address)
    return url
