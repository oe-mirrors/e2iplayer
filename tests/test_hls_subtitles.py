# -*- coding: utf-8 -*-
# Offline tests for HLS subtitle renditions: getDirectM3U8Playlist (IPTVPlayer/libs/urlparserhelper.py) lists them
# with their media playlist url marked 'hls' (no request per track), the helpers of
# IPTVPlayer/iptvdm/downloaderhelpers.py turn such a playlist into its segment urls and the fetched segments into
# one WebVTT text, and a download's subtitle fetch runs the segments as a second wget step. The enigma2 /
# E2iPlayer imports are stubbed; strwithmeta and the vendored m3u8 parser are the real ones.
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
PKG = "Plugins.Extensions.IPTVPlayer"

MASTER = """#EXTM3U
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="sub1",LANGUAGE="fi",NAME="Suomi",AUTOSELECT=YES,DEFAULT=YES,URI="subs/fi/index.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="sub1",LANGUAGE="sv",NAME="Svenska",URI="https://cdn.example/subs/sv.m3u8?t=1"
#EXT-X-STREAM-INF:BANDWIDTH=1000000,RESOLUTION=1280x720,CODECS="avc1.64001f,mp4a.40.2",SUBTITLES="sub1"
v720/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=500000,RESOLUTION=640x360,CODECS="avc1.64001e,mp4a.40.2",SUBTITLES="sub1"
v360/index.m3u8
"""

SUB_PLAYLIST = """#EXTM3U
#EXT-X-TARGETDURATION:6
#EXT-X-VERSION:3
#EXT-X-MEDIA-SEQUENCE:0
#EXT-X-PLAYLIST-TYPE:VOD
#EXTINF:6.00000,
seg0.vtt
#EXTINF:6.00000,
seg1.vtt?tok=a
#EXTINF:6.00000,
https://other.example/seg2.vtt
#EXT-X-ENDLIST
"""

SEG0 = "WEBVTT\nX-TIMESTAMP-MAP=MPEGTS:900000,LOCAL:00:00:00.000\n\nSTYLE\n::cue { color: yellow }\n\n1\n00:00:01.000 --> 00:00:02.000\nHello\n\n2\n00:00:05.500 --> 00:00:06.500\nacross the boundary\n"
SEG1 = "﻿WEBVTT\nX-TIMESTAMP-MAP=MPEGTS:900000,LOCAL:00:00:00.000\n\nSTYLE\n::cue { color: red }\n\n1\n00:00:05.500 --> 00:00:06.500\nacross the boundary\n\n2\n00:00:07.000 --> 00:00:08.000\nWorld"
SEG2 = "WEBVTT\r\nX-TIMESTAMP-MAP=MPEGTS:900000,LOCAL:00:00:00.000\r\n\r\n1\r\n00:00:13.000 --> 00:00:14.000\r\nBye\r\n"


def _stubModule(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


def _load(name, path, package=False):
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[os.path.dirname(path)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _FakeCommon(object):
    pages = {}
    requests = []

    @staticmethod
    def getParamsFromUrlWithMeta(url, baseHeaderOutParams=None):
        meta = getattr(url, "meta", {})
        return {"header": dict((k, v) for k, v in meta.items() if k in ("User-Agent", "Referer", "Origin", "Cookie"))}, None

    def getPage(self, url, params={}, post_data=None):
        _FakeCommon.requests.append(url)
        if url not in _FakeCommon.pages:
            return False, ""
        return True, sys.modules[PKG + ".tools.iptvtypes"].strwithmeta(_FakeCommon.pages[url], {"url": url})


class _Config(object):
    def __init__(self, mode="srt", lang="all"):
        self.plugins = types.SimpleNamespace(iptvplayer=types.SimpleNamespace(
            download_subtitles=types.SimpleNamespace(value=mode), download_subtitles_lang=types.SimpleNamespace(value=lang)))


class _Console(object):
    instances = []

    def __init__(self):
        self.appClosed = object()
        self.cmds = []
        _Console.instances.append(self)

    def execute(self, cmd):
        self.cmds.append(cmd)


@pytest.fixture
def env(tmp_path):
    saved = dict(sys.modules)
    for pkg in ("Plugins", "Plugins.Extensions", PKG, PKG + ".tools", PKG + ".libs", PKG + ".components", PKG + ".iptvdm",
                "Tools", "Components"):
        _stubModule(pkg)
    _stubModule(PKG + ".tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None, CSelOneLink=object,
                eConnectCallback=lambda *a: a, GetNice=lambda *a: 0, E2PrioFix=lambda cmd, *a: cmd,
                GetTmpDir=lambda name="": str(tmp_path / name), GetDefaultLang=lambda *a: "en")
    _stubModule("Components.config", config=_Config())
    _stubModule("Tools.BoundFunction", boundFunction=lambda f, *a: f)
    _stubModule("enigma", eConsoleAppContainer=_Console)
    _stubModule(PKG + ".components.iptvplayerinit", TranslateTXT=lambda text: text)
    _stubModule(PKG + ".libs.pCommon", common=_FakeCommon, CParsingHelper=object)
    _stubModule(PKG + ".libs.curlimpersonate")
    try:
        import six  # noqa: F401 - urlparserhelper imports it; the CI runner has no six installed
    except ImportError:
        _stubModule("six", ensure_binary=lambda s, *a: s.encode("utf-8") if isinstance(s, str) else s,
                    ensure_str=lambda s, *a: s.decode("utf-8") if isinstance(s, bytes) else s)
    _load(PKG + ".tools.iptvtypes", os.path.join(ROOT, "tools", "iptvtypes.py"))
    m3u8 = _load(PKG + ".libs.m3u8", os.path.join(ROOT, "libs", "m3u8", "__init__.py"), package=True)
    sys.modules[PKG + ".libs"].m3u8 = m3u8
    _stubModule(PKG + ".iptvdm.iptvdh", DMHelper=types.SimpleNamespace(
        getDownloaderParamFromUrl=lambda url: (url, dict(getattr(url, "meta", {}))),
        getBaseWgetCmd=lambda params: "wget" + "".join(' --header "%s: %s"' % kv for kv in sorted(params.items()) if kv[0] in ("User-Agent", "Referer")),
        STS=types.SimpleNamespace(DOWNLOADED="DOWNLOADED")))
    dh = _load(PKG + ".iptvdm.downloaderhelpers", os.path.join(ROOT, "iptvdm", "downloaderhelpers.py"))
    uph = _load(PKG + ".libs.urlparserhelper", os.path.join(ROOT, "libs", "urlparserhelper.py"))
    _FakeCommon.pages = {}
    _FakeCommon.requests = []
    _Console.instances = []
    yield types.SimpleNamespace(dh=dh, uph=uph, strwithmeta=sys.modules[PKG + ".tools.iptvtypes"].strwithmeta, tmp=tmp_path)
    sys.modules.clear()
    sys.modules.update(saved)


def test_master_lists_hls_tracks_without_fetching_them(env):
    master = "https://vod.example/a/master.m3u8"
    _FakeCommon.pages[master] = MASTER
    links = env.uph.getDirectM3U8Playlist(env.strwithmeta(master, {"User-Agent": "UA", "Referer": "https://site/"}), checkExt=False)
    assert links
    tracks = links[0]["url"].meta["external_sub_tracks"]
    assert [(t["lang"], t["format"], t["hls"]) for t in tracks] == [("fi", "vtt", True), ("sv", "vtt", True)]
    assert tracks[0]["url"] == "https://vod.example/a/subs/fi/index.m3u8"
    assert tracks[0]["url"].meta["Referer"] == "https://site/"
    assert _FakeCommon.requests == [master]  # the master only, no subtitle playlist


def test_is_hls_track(env):
    dh = env.dh
    assert dh.isHlsSubtitleTrack({"url": "https://x/sub.vtt", "hls": True})
    assert dh.isHlsSubtitleTrack({"url": "https://x/subs/en.M3U8?token=1"})
    assert not dh.isHlsSubtitleTrack({"url": "https://x/sub.vtt?f=.m3u8"})
    assert not dh.isHlsSubtitleTrack({"url": "https://x/sub.srt"})


def test_segment_urls_resolved_and_deduplicated(env):
    dh = env.dh
    base = "https://vod.example/a/subs/fi/index.m3u8?sig=1"
    assert dh.hlsSubtitleSegmentUrls(SUB_PLAYLIST, base) == ["https://vod.example/a/subs/fi/seg0.vtt", "https://vod.example/a/subs/fi/seg1.vtt?tok=a",
                                                               "https://other.example/seg2.vtt"]
    same = "#EXTM3U\n#EXT-X-TARGETDURATION:6\n" + "#EXTINF:6,\nfull.vtt\n" * 50 + "#EXT-X-ENDLIST\n"
    assert dh.hlsSubtitleSegmentUrls(same.encode("utf-8"), base) == ["https://vod.example/a/subs/fi/full.vtt"]
    assert dh.hlsSubtitleSegmentUrls(SEG0, base) == []
    assert dh.hlsSubtitleSegmentUrls("<html>403</html>", base) == []
    assert dh.hlsSubtitleSegmentUrls(MASTER, base) == []


def test_join_keeps_one_header_and_cue_order(env):
    dh = env.dh
    for parts in ([SEG0, SEG1, SEG2], SEG0 + SEG1 + SEG2):  # list of texts, or wget's -O file
        text = dh.joinWebVttSegments(parts)
        assert text.startswith("WEBVTT\nX-TIMESTAMP-MAP=MPEGTS:900000,LOCAL:00:00:00.000\n\nSTYLE\n::cue { color: yellow }\n\n1\n")
        assert text.count("WEBVTT") == 1 and text.count("X-TIMESTAMP-MAP") == 1 and "color: red" not in text
        assert text.count("across the boundary") == 1
        cues = [line for line in text.split("\n") if "-->" in line]
        assert cues == ["00:00:01.000 --> 00:00:02.000", "00:00:05.500 --> 00:00:06.500", "00:00:07.000 --> 00:00:08.000",
                        "00:00:13.000 --> 00:00:14.000"]
        assert "\r" not in text and "﻿" not in text and text.endswith("Bye\n")
        srt, ext = dh.subtitleToSrt(text)
        assert ext == "srt" and srt.count("-->") == 4
    assert dh.joinWebVttSegments([]) == ""


def test_download_subtitle_fetch_follows_hls_playlist(env):
    dh = env.dh

    class Downloader(dh.SidecarMixin):
        allowFinalRename = True

        def __init__(self):
            self._initSidecarState()
            self.finished = 0

        def _finishDownloadFlow(self):
            self.finished += 1

    d = Downloader()
    playlist = env.strwithmeta("https://vod.example/a/subs/fi/index.m3u8", {"Referer": "https://site/"})
    d._startSubtitleFetch({"User-Agent": "UA", "external_sub_tracks": [{"title": "Suomi", "lang": "fi", "url": playlist, "format": "vtt", "hls": True}]})
    assert d.subFetching and len(_Console.instances) == 1
    job = d.subJobs[0]
    assert "index.m3u8" in _Console.instances[0].cmds[0]
    # wget wrote the playlist: a second run fetches its segments into the same file
    with open(job["tmp"], "w") as f:
        f.write(SUB_PLAYLIST)
    d.subWaiting = True
    d._subtitleFetchFinished(0)
    assert d.subFetching and d.finished == 0 and len(_Console.instances) == 2 and job["hls"]
    cmd = _Console.instances[1].cmds[0]
    tmpQuoted = dh.shellQuote(job["tmp"])  # the temp path of Windows test runs has backslashes
    assert '-i "%s.list"' % tmpQuoted in cmd and '-O "%s"' % tmpQuoted in cmd and 'Referer: https://site/' in cmd and 'User-Agent: UA' in cmd
    with open(job["tmp"] + ".list") as f:
        assert f.read().split() == dh.hlsSubtitleSegmentUrls(SUB_PLAYLIST, playlist)
    with open(job["tmp"], "w", encoding="utf-8", newline="") as f:  # the bytes as wget wrote them (SEG2: CRLF)
        f.write(SEG0 + SEG1 + SEG2)
    d._subtitleFetchFinished(0)
    assert not d.subFetching and d.finished == 1 and len(_Console.instances) == 2
    video = str(env.tmp / "Movie.mp4")
    files = d._writeSubtitleFiles(video)
    assert [f["path"] for f in files] == [str(env.tmp / "Movie.fi.srt")]
    with open(files[0]["path"], encoding="utf-8") as f:
        srt = f.read()
    assert srt.count("-->") == 4 and srt.startswith("1\n00:00:01,000 --> 00:00:02,000\nHello\n")
    d._clearSubtitleData()
    assert not os.path.exists(job["tmp"] + ".list")


def test_plain_vtt_track_needs_no_second_run(env):
    dh = env.dh

    class Downloader(dh.SidecarMixin):
        allowFinalRename = True

        def _finishDownloadFlow(self):
            pass

    d = Downloader()
    d._initSidecarState()
    d._startSubtitleFetch({"external_sub_tracks": [{"title": "English", "lang": "en", "url": "https://x/en.vtt"}]})
    with open(d.subJobs[0]["tmp"], "w") as f:
        f.write(SEG0)
    d._subtitleFetchFinished(0)
    assert not d.subFetching and len(_Console.instances) == 1 and not d.subJobs[0]["hls"]
