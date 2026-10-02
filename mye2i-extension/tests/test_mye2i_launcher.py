"""MyE2i launcher: the start page's "open in" link (libs/mye2i_launcher.py) and the start page's
"close when done" marker that the extension's e2it.js looks for (scripts/mye2iserver.py)."""
import os
import sys
import threading
import urllib.request

sys.path.insert(0, os.path.join("IPTVPlayer", "scripts"))
sys.path.insert(0, os.path.join("IPTVPlayer", "libs"))

import mye2i_launcher  # noqa: E402
import mye2iserver as server  # noqa: E402

BOX = "http://192.168.178.22:9001/?t=0123456789abcdef"


def test_default_browser_keeps_the_plain_address():
    assert mye2i_launcher.getLauncherUrl(BOX) == BOX
    assert mye2i_launcher.getLauncherUrl(BOX, "unknown") == BOX


def test_known_browsers_get_an_android_intent():
    assert mye2i_launcher.getLauncherUrl(BOX, "kiwi") == \
        "intent://192.168.178.22:9001/?t=0123456789abcdef#Intent;scheme=http;package=com.kiwibrowser.browser;end"
    assert mye2i_launcher.getLauncherUrl("http://10.0.0.5:9001/", "edge") == \
        "intent://10.0.0.5:9001/#Intent;scheme=http;package=com.microsoft.emmx;end"
    assert mye2i_launcher.getLauncherUrl("http://10.0.0.5:9001/", "edge_canary") == \
        "intent://10.0.0.5:9001/#Intent;scheme=http;package=com.microsoft.emmx.canary;end"
    assert "package=com.microsoft.emmx.beta;" in mye2i_launcher.getLauncherUrl(BOX, "edge_beta")
    assert "package=com.microsoft.emmx.dev;" in mye2i_launcher.getLauncherUrl(BOX, "edge_dev")
    assert "package=com.yandex.browser;" in mye2i_launcher.getLauncherUrl(BOX, "yandex")


def test_own_launcher_uri():
    assert mye2i_launcher.getLauncherUrl(BOX, "custom", " mybrowser://open?u={url} ") == "mybrowser://open?u=" + BOX
    assert mye2i_launcher.getLauncherUrl(BOX, "custom", "intent://{address}#Intent;scheme=http;package=x.y;end") == \
        "intent://192.168.178.22:9001/?t=0123456789abcdef#Intent;scheme=http;package=x.y;end"
    # nothing to put the address into, or empty: the plain address
    assert mye2i_launcher.getLauncherUrl(BOX, "custom", "mybrowser://") == BOX
    assert mye2i_launcher.getLauncherUrl(BOX, "custom", "") == BOX


def _startPage(closeStartPage, launcherUrl="", launcherName=""):
    handler = server.redirect_handler_factory("https://site.example/#e2it?k=key&st=", "", "", close_start_page=closeStartPage,
                                              launcher_url=launcherUrl, launcher_name=launcherName)
    httpd = server.ThreadedServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()
    try:
        url = "http://127.0.0.1:%d%s" % (httpd.server_address[1], server.RELAY_PAGE_PATH)
        return urllib.request.urlopen(url, timeout=10).read().decode("utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_start_page_close_marker():
    page = _startPage(True)
    assert '<div id="e2i-close-on-success" style="display:none"></div>' in page
    assert "https://site.example/#e2it?k=key&amp;st=" in page
    assert "e2i-close-on-success" not in _startPage(False)


def test_start_page_open_in_link():
    intent = mye2i_launcher.getLauncherUrl(BOX, "edge_canary")
    page = _startPage(False, intent, "Microsoft Edge Canary")
    # inside the red bar that the extension hides: only visible in a browser without MyE2i
    bar = page.split('<div id="mye2i_%s"' % server.MIN_EXTENSION_VERSION_STR, 1)[1].split("</div>", 1)[0]
    assert '<a href="%s"' % intent in bar
    assert "Open this page in Microsoft Edge Canary</a>" in bar
    # own launcher URI: no browser name, "&" escaped in the attribute
    page = _startPage(False, "mybrowser://open?u=x&v=y", "")
    assert '<a href="mybrowser://open?u=x&amp;v=y"' in page
    assert "Open this page in the chosen browser</a>" in page
    # default browser: no link
    assert "Open this page in" not in _startPage(False)


def test_extension_closes_the_start_page_on_the_marker():
    with open(os.path.join("mye2i-extension", "contentscripts", "e2it.js"), encoding="utf-8") as f:
        script = f.read()
    assert 'document.querySelector("#e2i-close-on-success")' in script
    assert "{'action':'CLOSE_ME'}" in script
