# Offline tests for IPTVPlayer/subproviders/subprov_prijevodi.py (prijevodi-online.org JSON API): the translation
# list and the download path incl. the account login, with hand-made API answers.
import importlib.util
import json
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
API = "https://www.prijevodi-online.org/api/v1/"
SRT = u"1\n00:00:01,000 --> 00:00:02,000\nŽivjeli, čovječe!\n".encode("cp1250")


class _Val(object):
    def __init__(self, value=""):
        self.value = value


class _FakeCommon(object):
    """pCommon stand-in. getPage: {url part: (sts, body)}; downloads: list of (status, body) for saveWebFile"""
    ph = _Ph

    def __init__(self, pages, downloads, cookieFile):
        self.pages, self.downloads, self.cookieFile = pages, list(downloads), cookieFile
        self.requests, self.meta = [], {}

    def getPage(self, url, params={}, post=None):
        self.requests.append(("page", url, dict(params), post))
        for part, answer in self.pages.items():
            if part in url:
                if part == "auth/login" and answer[0]:
                    with open(self.cookieFile, "w") as f:
                        f.write("session")
                return answer
        raise AssertionError("unexpected url %s" % url)

    def getCookieItems(self, cookiefile):
        return {"sid": "abc"} if os.path.isfile(cookiefile) else {}

    def saveWebFile(self, filePath, url, params={}, post=None):
        # like the urllib path: the body of an error page is stored too, the status is in meta
        self.requests.append(("download", url, dict(params), post))
        status, body = self.downloads.pop(0)
        self.meta = {"url": url, "status_code": status}
        with open(filePath, "wb") as f:
            f.write(body)
        return {"sts": True, "fsize": len(body)}


@pytest.fixture
def prov(tmp_path):
    saved = dict(sys.modules)
    errors = []
    cfg = types.SimpleNamespace(prijevodi_login=_Val(), prijevodi_password=_Val())
    for name in ("Plugins", "Plugins.Extensions", P, P + ".components", P + ".libs", P + ".tools", P + ".p2p3", P + ".iptvdm",
                 P + ".subproviders", P + ".components.asynccall", P + ".libs.pCommon", P + ".components.ihost",
                 P + ".iptvdm.downloaderhelpers", "Components"):
        _stub(name)
    _stub("Components.config", config=types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=cfg)))
    _stub(P + ".components.iptvplayerinit", TranslateTXT=lambda s: s, SetIPTVPlayerLastHostError=errors.append)

    def _mkdirs(d):
        os.makedirs(d, exist_ok=True)
        return True
    _stub(P + ".tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None, GetDefaultLang=lambda: "hr",
          GetTmpDir=lambda f="": str(tmp_path / ("tmp_" + f.strip("/"))), GetSubtitlesDir=lambda f="": str(tmp_path / ("subs_" + f)),
          GetCookieDir=lambda f: str(tmp_path / f), RemoveDisallowedFilenameChars=lambda s: s.replace("/", "_"),
          rm=lambda f: os.path.isfile(f) and os.remove(f), rmtree=lambda d, ignore_errors=False: shutil.rmtree(d, ignore_errors=True), mkdirs=_mkdirs)
    _stub(P + ".p2p3.manipulateStrings", ensure_binary=lambda x: x if isinstance(x, bytes) else x.encode("utf-8"))
    _stub(P + ".p2p3.UrlLib", urllib_urlencode=urllib.parse.urlencode)
    # the real player format detection (subtitleType of the base class uses it), its imports are stubbed
    for name, path in ((P + ".tools.iptvsubtitles", ("tools", "iptvsubtitles.py")), (P + ".libs.subtitlesmatch", ("libs", "subtitlesmatch.py")),
                       (P + ".components.isubprovider", ("components", "isubprovider.py")),
                       (P + ".subproviders.subprov_prijevodi", ("subproviders", "subprov_prijevodi.py"))):
        spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, *path))
        sys.modules[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sys.modules[name])
    module = sys.modules[P + ".subproviders.subprov_prijevodi"]
    module.SESSION.clear()
    sys.modules[P + ".tools.iptvsubtitles"].IPTVSubtitlesHandler.getSupportedFormats = staticmethod(lambda: ["srt", "sub"])

    def make(pages=None, downloads=(), login="", password=""):
        cfg.prijevodi_login.value, cfg.prijevodi_password.value = login, password
        p = module.PrijevodiOnline({"discover_info": {}, "confirmed_title": "Inception 2010", "movie_title": "Inception.2010.720p.BluRay.x264-CROSSBOW"})
        p.cm = _FakeCommon(pages or {}, downloads, p.COOKIE_FILE)
        return p
    make.errors, make.module = errors, module
    yield make
    sys.modules.clear()
    sys.modules.update(saved)


MOVIE_ITEM = {"category": "list_subtitles", "kind": "movies", "sub_id": "578", "title": "[hr] Inception.720p.BluRay", "lang": "hr", "imdbid": "", "fps": 0}
LOGIN_OK = (True, json.dumps({"auth": {"id": 7, "name": "user", "displayName": "User"}}))


def _download(p, item=MOVIE_ITEM):
    p.currList = []
    p.getSubtitlesList(dict(item))
    return p.currList


def test_translation_list_sorted(prov):
    p = prov({"translations/movies": (True, json.dumps({"movieTranslations": {"total": 3, "items": [
        {"id": 1, "title": "Inception.1080p.WEB-DL.zip", "languageCode": "sr", "downloadCount": 50, "username": "a"},
        {"id": 2, "title": "Inception.DVDRip", "languageCode": "hr", "downloadCount": 1, "fps": 23.976},
        {"id": 3, "title": "Inception.720p.BluRay.x264-CROSSBOW", "languageCode": "hr", "downloadCount": 0, "hearingImpaired": True},
        {"id": 4, "title": "hidden", "languageCode": "hr", "isPublished": False}]}}))})
    p.listTranslations({"movie_id": 324}, "list_subtitles")
    assert [(x["sub_id"], x["lang"], x["kind"]) for x in p.currList] == [("3", "hr", "movies"), ("2", "hr", "movies"), ("1", "sr", "movies")]
    assert p.currList[2]["title"] == "[sr] Inception.1080p.WEB-DL"
    # the frame rate is not cut to an int
    assert p.currList[1]["fps"] == 23.976 and p.currList[0]["fps"] == 0
    assert "hearing impaired" in p.currList[0]["desc"] and "Uploader: a" in p.currList[2]["desc"]
    assert p.cm.requests[0][1] == API + "translations/movies?movieId=324&perPage=100"


def test_movie_without_account(prov):
    p = prov(downloads=[(401, b'{"error":{"code":"Auth/Unauthorized"}}')])
    assert _download(p) == []
    assert prov.errors[-1] == "Downloading from prijevodi-online.org needs a free account. Enter login and password in the E2iPlayer settings."
    assert [r[0] for r in p.cm.requests] == ["download"]


def test_series_without_account(prov):
    p = prov(downloads=[(200, SRT)])
    items = _download(p, dict(MOVIE_ITEM, kind="series", sub_id="95490"))
    params = p.cm.requests[0][2]
    assert p.cm.requests[0][1] == API + "translations/series/95490/download" and "Cookie" not in params["header"]
    assert not params.get("use_cookie") and "cookiefile" not in params
    assert [x["type"] for x in items] == ["subtitle"]


def test_login_download_and_convert(prov):
    p = prov({"auth/login": LOGIN_OK}, downloads=[(200, SRT), (200, SRT)], login="user", password="secret")
    items = _download(p)
    kind, url, params, post = p.cm.requests[0]
    assert (kind, url) == ("page", API + "auth/login")
    assert json.loads(post) == {"username": "user", "password": "secret", "rememberMe": False}
    assert params["raw_post_data"] and params["header"]["Content-Type"] == "application/json" and params["save_cookie"]
    kind, url, params, post = p.cm.requests[1]
    assert (kind, url) == ("download", API + "translations/movies/578/download")
    # the session cookies come from the cookie file of the login
    assert params["use_cookie"] and params["load_cookie"] and params["cookiefile"] == p.COOKIE_FILE and "Cookie" not in params["header"]
    assert len(items) == 1 and items[0]["type"] == "subtitle"
    ret = p.downloadSubtitleFile(items[0])
    assert set(ret) >= {"title", "path", "lang", "imdbid", "sub_id"}
    assert os.path.basename(ret["path"]).endswith("_hr_0_578_.srt")
    with open(ret["path"], "rb") as f:
        assert u"Živjeli, čovječe!".encode("utf-8") in f.read()
    # one login per session: a new provider instance uses the cached cookie
    p2 = prov({}, downloads=[(200, SRT)], login="user", password="secret")
    assert len(_download(p2)) == 1 and [r[0] for r in p2.cm.requests] == ["download"]


def test_expired_session_relogin_once(prov):
    prov.module.SESSION.update({"key": ("user", "secret"), "logged_in": True, "expires": 9e18})
    p = prov({"auth/login": LOGIN_OK}, downloads=[(401, b""), (200, SRT)], login="user", password="secret")
    assert len(_download(p)) == 1
    assert [r[0] for r in p.cm.requests] == ["download", "page", "download"]
    assert all(p.cm.requests[i][2]["load_cookie"] and p.cm.requests[i][2]["cookiefile"] == p.COOKIE_FILE for i in (0, 2))
    assert prov.module.SESSION["logged_in"] and prov.module.SESSION["expires"] < 9e18
    # still 401 after a fresh login: no endless loop
    prov.module.SESSION.update({"logged_in": True, "expires": 9e18})
    p = prov({"auth/login": LOGIN_OK}, downloads=[(401, b""), (401, b"")], login="user", password="secret")
    assert _download(p) == [] and "refused" in prov.errors[-1]


def test_wrong_credentials(prov):
    bad = (True, json.dumps({"error": {"code": "Auth/InvalidCredentials", "message": "Invalid username or password"}}))
    p = prov({"auth/login": bad}, login="user", password="wrong")
    assert _download(p) == []
    assert prov.errors[-1] == "Login to prijevodi-online.org failed: Invalid username or password"
    # not repeated at once
    p = prov({"auth/login": bad}, login="user", password="wrong")
    assert _download(p) == [] and p.cm.requests == [] and "Invalid username" in prov.errors[-1]
    # the harness / pycurl style failure (sts False with the error body) and the captcha answer
    prov.module.SESSION.clear()
    p = prov({"auth/login": (False, json.dumps({"error": {"code": "Auth/CaptchaFailed", "message": "CAPTCHA verification failed"}}))}, login="u", password="p")
    assert _download(p) == [] and "captcha" in prov.errors[-1]
    prov.module.SESSION.clear()
    p = prov({"auth/login": (False, None)}, login="u", password="p")
    assert _download(p) == [] and 'Failed to log in user "u"' in prov.errors[-1]
