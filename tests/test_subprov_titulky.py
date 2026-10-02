# Offline tests for IPTVPlayer/subproviders/subprov_titulky.py (titulky.com): the captcha answer of the
# input box is posted as the typed text.
import importlib.util
import os
import shutil
import sys
import types
import urllib.parse

import pytest

from test_isubprovider_files import _Ph
from test_isubprovider_imdb import _stub

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
P = "Plugins.Extensions.IPTVPlayer"


class _Val(object):
    def __init__(self, value=""):
        self.value = value


class _FakeCommon(object):
    """pCommon stand-in: getPage answers by URL part, saveWebFile gives the captcha picture"""
    ph = _Ph

    def __init__(self, pages):
        self.pages, self.requests, self.meta = pages, [], {}

    def getPage(self, url, params={}, post=None):
        self.requests.append(("page", url, post))
        for part, answer in self.pages.items():
            if part in url:
                return answer
        raise AssertionError("unexpected url %s" % url)

    def saveWebFile(self, filePath, url, params={}, post=None):
        self.requests.append(("download", url, post))
        self.meta = {"url": url, "status_code": 200}
        with open(filePath, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0JFIF")
        return {"sts": True, "fsize": 8}


class _Session(object):
    """sessionEx stand-in: waitForFinishOpen gives the callback arguments of the screen"""

    def __init__(self, ret):
        self.ret, self.opened = ret, []

    def waitForFinishOpen(self, screen, params):
        self.opened.append(params)
        return self.ret


@pytest.fixture
def prov(tmp_path):
    saved = dict(sys.modules)
    errors = []
    cfg = types.SimpleNamespace(titulky_login=_Val(), titulky_password=_Val())
    for name in ("Plugins", "Plugins.Extensions", P, P + ".components", P + ".libs", P + ".tools", P + ".p2p3", P + ".iptvdm",
                 P + ".subproviders", P + ".components.asynccall", P + ".libs.pCommon", P + ".components.ihost",
                 P + ".iptvdm.downloaderhelpers", P + ".tools.iptvsubtitles", "Components"):
        _stub(name)
    _stub("Components.config", config=types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=cfg)))
    _stub(P + ".components.iptvplayerinit", TranslateTXT=lambda s: s, SetIPTVPlayerLastHostError=errors.append)
    _stub(P + ".components.iptvmultipleinputbox", IPTVMultipleInputBox=type("Box", (), {"DEF_PARAMS": {}, "DEF_INPUT_PARAMS": {}}))
    _stub(P + ".tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None, GetDefaultLang=lambda: "cs",
          GetTmpDir=lambda f="": str(tmp_path / ("tmp_" + f.strip("/"))), GetCookieDir=lambda f: str(tmp_path / f),
          rm=lambda f: os.path.isfile(f) and os.remove(f), rmtree=lambda d, ignore_errors=False: shutil.rmtree(d, ignore_errors=True))
    _stub(P + ".p2p3.manipulateStrings", ensure_binary=lambda x: x if isinstance(x, bytes) else x.encode("utf-8"))
    _stub(P + ".p2p3.UrlLib", urllib_urlencode=urllib.parse.urlencode)
    for name, path in ((P + ".libs.subtitlesmatch", ("libs", "subtitlesmatch.py")), (P + ".components.isubprovider", ("components", "isubprovider.py")),
                       (P + ".subproviders.subprov_titulky", ("subproviders", "subprov_titulky.py"))):
        spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, *path))
        sys.modules[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sys.modules[name])
    module = sys.modules[P + ".subproviders.subprov_titulky"]

    def make(pages, ret):
        p = module.TitulkyProvider({"discover_info": {}, "confirmed_title": "Inception 2010", "movie_title": "Inception 2010"})
        p.cm = _FakeCommon(pages)
        p.sessionEx = _Session(ret)
        return p
    make.errors = errors
    yield make
    sys.modules.clear()
    sys.modules.update(saved)


DOWNLOAD_PAGE = (True, '<a id="downlink" href="/idown.php?id=1">x</a>')


def test_captcha_answer_posted_as_text(prov):
    # IPTVMultipleInputBox closes with the list of its inputs, the callback gets it as the first argument
    p = prov({"idown.php": DOWNLOAD_PAGE}, (["  abcd "],))
    assert p.solveCaptcha("123") == DOWNLOAD_PAGE[1]
    kind, url, post = p.cm.requests[-1]
    assert (kind, url) == ("page", "https://www.titulky.com/idown.php")
    assert post["downkod"] == "abcd" and post["titulky"] == "123"
    assert urllib.parse.urlencode(post).startswith("downkod=abcd&")
    assert p.sessionEx.opened[0]["list"][0]["icon_path"].endswith(".iptvplayer_captcha.jpg")


@pytest.mark.parametrize("ret", [([""],), (["   "],), (None,), None, ()])
def test_captcha_not_entered(prov, ret):
    p = prov({}, ret)
    assert p.solveCaptcha("123") == ""
    # only the captcha picture was fetched, nothing posted
    assert [r[0] for r in p.cm.requests] == ["download"]
    assert prov.errors[-1] == "Captcha was not entered."


def test_wrong_captcha(prov):
    p = prov({"idown.php": (True, '<img src="/captcha/captcha.php">')}, (["abcd"],))
    assert p.solveCaptcha("123") == "" and prov.errors[-1] == "Wrong captcha code."
