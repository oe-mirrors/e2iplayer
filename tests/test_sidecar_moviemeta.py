# Offline tests for the moviemeta details in download sidecars: the query hosts put into the link meta
# (IPTVPlayer/libs/urlmetahelper.py) and its lookup in a thread when a download starts
# (IPTVPlayer/iptvdm/downloaderhelpers.py SidecarMixin). The enigma2 / E2iPlayer imports and moviemeta are
# stubbed; strwithmeta is the real one.
import importlib.util
import os
import sys
import threading
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")

META = {"title": "The Wolf and the Lamb", "plot": "A wolf meets a lamb.", "poster": "https://img/poster.jpg",
        "info": {"year": "2026", "imdb_rating": "6.5/10", "genres": "Thriller, Western", "duration": "1h 36min",
                 "directors": "Michael Schiff", "cast": "A, B", "source": "TMDb (themoviedb.org)"}}


def _stubModule(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def env():
    saved = dict(sys.modules)
    calls = []

    def getMeta(mediaType, title, year="", skip=(), maxYearDiff=None):
        calls.append(("title", mediaType, title, year, tuple(skip), maxYearDiff))
        return dict(META) if title == "The Wolf and the Lamb" else {}

    def getMetaByImdbId(mediaType, imdbId):
        calls.append(("imdb", mediaType, imdbId))
        return dict(META) if imdbId == "tt1234567" else {}

    def isLatinTitle(title):
        # as moviemeta's: no letters at all counts as Latin
        letters = [c for c in title if c.isalpha()]
        return not letters or any("a" <= c.lower() <= "z" for c in letters)

    for pkg in ("Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer", "Plugins.Extensions.IPTVPlayer.tools",
                "Plugins.Extensions.IPTVPlayer.libs", "Plugins.Extensions.IPTVPlayer.components", "Plugins.Extensions.IPTVPlayer.iptvdm",
                "Tools"):
        _stubModule(pkg)
    _stubModule("Plugins.Extensions.IPTVPlayer.tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None,
                eConnectCallback=lambda *a: None, GetNice=lambda *a: 0, E2PrioFix=lambda cmd, *a: cmd)
    _load("Plugins.Extensions.IPTVPlayer.tools.iptvtypes", os.path.join(ROOT, "tools", "iptvtypes.py"))
    infoQueries = {}
    _stubModule("Plugins.Extensions.IPTVPlayer.libs.moviemeta", getMeta=getMeta, getMetaByImdbId=getMetaByImdbId,
                LATIN_ONLY=("IMDb", "Cinemeta", "OMDb"), isLatinTitle=isLatinTitle,
                getInfoQuery=lambda cItem: infoQueries.get(cItem.get("url")))
    labels = {"imdb_rating": "IMDb Rating:", "genres": "Genres:", "duration": "Duration:", "directors": "Directors:", "cast": "Cast:"}
    _stubModule("Plugins.Extensions.IPTVPlayer.components.ihost", ArticleContent=types.SimpleNamespace(RICH_DESC_LABELS=labels))
    _stubModule("Plugins.Extensions.IPTVPlayer.components.iptvplayerinit", TranslateTXT=lambda text: text)
    _stubModule("Plugins.Extensions.IPTVPlayer.libs.pCommon", common=types.SimpleNamespace(HOST="UA"))
    _stubModule("Tools.BoundFunction", boundFunction=lambda f, *a: f)
    _stubModule("enigma", eConsoleAppContainer=object)

    def AsyncMethod(fnc):
        # as components/asynccall: a work thread named after the function (pCommon needs its kill state)
        def start(*args):
            thread = threading.Thread(target=fnc, name=fnc.__name__, args=args)
            thread._iptvplayer_ext = {"kill_lock": threading.Lock(), "killable": True, "terminated": False}
            thread.start()
        return start
    _stubModule("Plugins.Extensions.IPTVPlayer.components.asynccall", AsyncMethod=AsyncMethod)
    umh = _load("Plugins.Extensions.IPTVPlayer.libs.urlmetahelper", os.path.join(ROOT, "libs", "urlmetahelper.py"))
    dh = _load("Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers", os.path.join(ROOT, "iptvdm", "downloaderhelpers.py"))
    yield types.SimpleNamespace(umh=umh, dh=dh, calls=calls, infoQueries=infoQueries)
    sys.modules.clear()
    sys.modules.update(saved)


def test_query_from_item(env):
    item = {"title": "The Wolf (2026)", "desc": "site text", "icon": "https://img/site.jpg",
            "meta_type": "movie", "meta_title": "The Wolf and the Lamb", "meta_year": "2026"}
    sidecar = env.umh.buildSidecarFromItem(item, True, "")
    assert sidecar["meta"] == {"type": "movie", "title": "The Wolf and the Lamb", "year": "2026"}
    assert sidecar["txt"] == "site text"
    assert sidecar["img"] == "https://img/site.jpg"
    # disabled sidecar / item without meta keys / explicit {} -> no query
    assert "meta" not in env.umh.buildSidecarFromItem(item, False, "")
    assert "meta" not in env.umh.buildSidecarFromItem({"desc": "x"}, True, "")
    assert "meta" not in env.umh.buildSidecarFromItem(item, True, "", {})


def test_info_query_goes_first(env):
    # the lookup that answered on the item's INFO beats the host's own query and the item's meta keys
    item = {"url": "https://site/wolf", "title": "Wolf", "meta_type": "movie", "meta_title": "Wolf"}
    env.infoQueries["https://site/wolf"] = {"type": "movie", "title": "", "year": "", "imdb": "tt1234567"}
    assert env.umh.buildSidecarFromItem(item, True, "")["meta"] == {"type": "movie", "title": "", "year": "", "imdb": "tt1234567"}
    assert env.umh.buildSidecarFromItem(item, True, "", {"type": "movie", "title": "Wolf", "year": ""})["meta"]["imdb"] == "tt1234567"
    assert "meta" not in env.umh.buildSidecarFromItem(item, False, "")
    assert env.umh.infoSidecarMetaQuery({"url": "https://site/other"}, {"x": 1}) == {"x": 1}


def test_query_rules(env):
    q = env.umh.sidecarMetaQuery
    assert q("tv", u"المداح", "2021") == {"type": "tv", "title": u"المداح", "year": "2021", "skip": ["IMDb", "Cinemeta", "OMDb"]}
    assert q("movie", "Heat", "1995 HD", "tt0113277", skip=(), maxYearDiff=1) == {"type": "movie", "title": "Heat", "year": "1995", "imdb": "tt0113277", "maxYearDiff": 1}
    assert q("movie", "", "", "tt0113277") == {"type": "movie", "title": "", "year": "", "imdb": "tt0113277"}
    assert q("movie", "Heat", imdbId="12345") == {"type": "movie", "title": "Heat", "year": ""}
    assert q("episode", "Heat") == {}
    assert q("movie", "") == {}


def test_query_travels_through_url_meta(env):
    umh = env.umh
    sidecar = umh.buildSidecar(True, "site text", "https://img/site.jpg", umh.sidecarMetaQuery("movie", "The Wolf and the Lamb"))
    links = umh.applySidecarToLinks([{"name": "a", "url": "https://host/video/1"}], sidecar)
    meta = umh.getUrlMeta(links[0]["url"])
    assert meta["e2i_sidecar_meta"] == {"type": "movie", "title": "The Wolf and the Lamb", "year": ""}
    # getVideoLinks reads it back and hands it on to the resolved links
    again = umh.sidecarFromUrlMeta(links[0]["url"])
    resolved = umh.decorateResolvedLinkItems([{"name": "b", "url": "https://cdn/file.mp4"}], again)
    assert umh.getUrlMeta(resolved[0]["url"])["e2i_sidecar_meta"]["title"] == "The Wolf and the Lamb"
    # a sidecar without a query clears an old one
    plain = umh.decorateUrl(links[0]["url"], sidecar=umh.buildSidecar(True, "t", ""))
    assert "e2i_sidecar_meta" not in umh.getUrlMeta(plain)
    assert umh.mergeSidecar(sidecar, txt="new")["meta"]["title"] == "The Wolf and the Lamb"
    assert "meta" not in umh.mergeSidecar(sidecar, meta={})


def test_lookup_formats_text_and_poster(env):
    txt, img = env.umh.lookupSidecarMeta({"type": "movie", "title": "The Wolf and the Lamb", "year": "2026"}, "site text", "https://img/site.jpg")
    assert txt == ("The Wolf and the Lamb (2026)\nIMDb Rating: 6.5/10\nGenres: Thriller, Western\nDuration: 1h 36min\n"
                   "Directors: Michael Schiff\nCast: A, B\n\nA wolf meets a lamb.")
    assert img == "https://img/poster.jpg"
    # the IMDb id first, the title when the id is unknown; nothing found -> the site's sidecar stays
    assert env.umh.lookupSidecarMeta({"type": "movie", "title": "Nope", "imdb": "tt1234567"}, "s", "i")[1] == "https://img/poster.jpg"
    assert env.umh.lookupSidecarMeta({"type": "movie", "title": "Nope", "imdb": "tt7654321"}, "s", "i") == ("s", "i")
    assert env.calls[-2:] == [("imdb", "movie", "tt7654321"), ("title", "movie", "Nope", "", (), None)]


def test_alt_titles(env):
    q = env.umh.sidecarMetaQuery
    arabic = u"الذئب"
    # each alternative title gets its own automatic skip; the main title and doubles are left out
    query = q("movie", arabic, "2026", altTitles=["The Wolf and the Lamb", arabic, "", "The Wolf and the Lamb"])
    assert query["skip"] == ["IMDb", "Cinemeta", "OMDb"]
    assert query["alt"] == [["The Wolf and the Lamb", []]]
    # an explicit skip holds for all titles
    assert q("movie", "Der Wolf", altTitles=["The Wolf"], skip=())["alt"] == [["The Wolf", []]]
    txt, img = env.umh.lookupSidecarMeta(query, "s", "i")
    assert img == "https://img/poster.jpg"
    assert env.calls == [("title", "movie", arabic, "2026", ("IMDb", "Cinemeta", "OMDb"), None),
                         ("title", "movie", "The Wolf and the Lamb", "2026", (), None)]


class _Downloader(object):
    def onFinish(self):
        pass

    def _cleanUp(self):
        pass


def _downloader(env, query):
    dl = type("Dl", (_Downloader, env.dh.SidecarMixin), {})()
    dl._initSidecarState()
    meta = {"e2i_sidecar_enabled": True, "e2i_sidecar_txt": "site text", "e2i_sidecar_img": "https://img/site.jpg"}
    if query:
        meta["e2i_sidecar_meta"] = query
    return dl, meta


def _join():
    for thread in threading.enumerate():
        if thread.name == "sidecarMetaLookup":
            thread.join(5)


def test_download_writes_moviemeta_sidecar(env, tmp_path):
    dl, meta = _downloader(env, {"type": "movie", "title": "The Wolf and the Lamb", "year": "2026"})
    dl._prepareSidecarData(meta)
    _join()
    dl._writeTxtSidecar(str(tmp_path / "film.mp4"))
    text = (tmp_path / "film.txt").read_text(encoding="utf-8")
    assert text.startswith("The Wolf and the Lamb (2026)\nIMDb Rating: 6.5/10")
    assert text.endswith("A wolf meets a lamb.")
    assert dl.sidecarImg == "https://img/poster.jpg"


def test_lookup_runs_in_a_work_thread(env, tmp_path):
    # pCommon's pycurl requests read the kill state of an E2iPlayer work thread
    seen = []
    lookup = env.umh.lookupSidecarMeta

    def checkingLookup(*args):
        seen.append(hasattr(threading.current_thread(), "_iptvplayer_ext"))
        return lookup(*args)
    env.umh.lookupSidecarMeta = checkingLookup
    dl, meta = _downloader(env, {"type": "movie", "title": "The Wolf and the Lamb", "year": ""})
    dl._prepareSidecarData(meta)
    _join()
    assert seen == [True]


def test_series_keeps_the_episode_text(env):
    # moviemeta knows the show's plot only: an episode keeps the site's text under the show's details
    txt = env.umh.lookupSidecarMeta({"type": "tv", "title": "The Wolf and the Lamb", "year": ""}, "Episode 2: the lamb runs.", "i")[0]
    assert txt.startswith("The Wolf and the Lamb (2026)\n")
    assert txt.endswith("\n\nEpisode 2: the lamb runs.")
    # no site text: the show's plot
    assert env.umh.lookupSidecarMeta({"type": "tv", "title": "The Wolf and the Lamb", "year": ""}, "", "i")[0].endswith("A wolf meets a lamb.")


def test_poster_gets_the_download_time(env, tmp_path):
    # wget keeps the server's date of the picture: the saved .jpg gets the time of the download
    dl, meta = _downloader(env, None)
    tmp = tmp_path / "film.jpg.new"
    tmp.write_bytes(b"\xff\xd8poster")
    os.utime(str(tmp), (1600000000, 1600000000))
    dl.sidecarImgTmpPath = str(tmp)
    dl._imgSidecarFinished(str(tmp_path / "film.jpg"), 0)
    assert (tmp_path / "film.jpg").read_bytes() == b"\xff\xd8poster"
    assert os.path.getmtime(str(tmp_path / "film.jpg")) > 1700000000


def test_download_without_query_keeps_site_sidecar(env, tmp_path):
    dl, meta = _downloader(env, None)
    dl._prepareSidecarData(meta)
    dl._writeTxtSidecar(str(tmp_path / "film.mp4"))
    assert (tmp_path / "film.txt").read_text(encoding="utf-8") == "site text"
    assert dl.sidecarImg == "https://img/site.jpg"
    assert env.calls == []


def test_late_answer_rewrites_txt(env, tmp_path):
    gate = threading.Event()
    lookup = env.umh.lookupSidecarMeta

    def slowLookup(*args):
        gate.wait(5)
        return lookup(*args)
    env.umh.lookupSidecarMeta = slowLookup
    dl, meta = _downloader(env, {"type": "movie", "title": "The Wolf and the Lamb", "year": ""})
    dl._prepareSidecarData(meta)
    dl._writeTxtSidecar(str(tmp_path / "film.mp4"))
    assert (tmp_path / "film.txt").read_text(encoding="utf-8") == "site text"
    gate.set()
    _join()
    assert (tmp_path / "film.txt").read_text(encoding="utf-8").startswith("The Wolf and the Lamb (2026)")
