# -*- coding: utf-8 -*-
# Offline tests for IPTVPlayer/iptvdm/dashdownloader.py and the download plan of libs/dashmpd.py: which segments a
# DASH VOD download loads (SegmentTemplate / Timeline / List with byte ranges / SegmentBase / endNumber), the part
# files it writes (tries again, a missing last segment, stop and continue) and the ffmpeg command that puts the parts
# together. dashmpd, ffmpegdownloader and strwithmeta are the real ones; the enigma2 parts are stubbed.
import importlib.util
import io
import os
import sys
import threading
import types
from urllib.error import HTTPError

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
PKG = "Plugins.Extensions.IPTVPlayer"
MPD_URL = "https://cdn.example/v/manifest.mpd"

TEMPLATE = """<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" mediaPresentationDuration="PT9S">
 <Period>
  <AdaptationSet contentType="video" mimeType="video/mp4" codecs="avc1.640028">
   <SegmentTemplate media="$RepresentationID$/$Number$.m4s" initialization="$RepresentationID$/init.mp4" duration="4"/>
   <Representation id="v1" bandwidth="3000000" width="1280" height="720"/>
  </AdaptationSet>
  <AdaptationSet contentType="audio" mimeType="audio/mp4" lang="de" codecs="mp4a.40.2">
   <SegmentTemplate media="a/$Time$.m4s" initialization="a/init.mp4" timescale="1000">
    <SegmentTimeline><S t="0" d="5000" r="1"/></SegmentTimeline>
   </SegmentTemplate>
   <Representation id="a1" bandwidth="128000"/>
  </AdaptationSet>
 </Period>
</MPD>"""

OTHERS = """<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" mediaPresentationDuration="PT1M">
 <Period>
  <AdaptationSet contentType="video" mimeType="video/mp4" codecs="avc1.640028">
   <Representation id="list" bandwidth="1" width="640" height="360"><BaseURL>list.mp4</BaseURL>
    <SegmentList duration="10"><Initialization range="0-99"/>
     <SegmentURL mediaRange="100-199"/><SegmentURL mediaRange="200-299"/></SegmentList>
   </Representation>
   <Representation id="tmpl" bandwidth="2" width="960" height="540">
    <SegmentTemplate media="t/$Number%03d$.m4s" duration="10" startNumber="5" endNumber="7"/>
   </Representation>
  </AdaptationSet>
  <AdaptationSet contentType="audio" mimeType="audio/mp4" codecs="mp4a.40.2">
   <Representation id="file" bandwidth="1"><BaseURL>audio.mp4</BaseURL><SegmentBase indexRange="0-50"/></Representation>
  </AdaptationSet>
  <AdaptationSet contentType="video" mimeType="video/mp4" codecs="avc1.640028">
   <ContentProtection schemeIdUri="urn:mpeg:dash:mp4protection:2011" value="cenc"/>
   <Representation id="drm" bandwidth="1" width="1920" height="1080"/>
  </AdaptationSet>
 </Period>
</MPD>"""


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


class _Base(object):
    CODE_OK = 0

    def __init__(self):
        self.localFileSize = -1
        self.downloadSpeed = -1

    def onStart(self):
        pass

    def getLocalFileSize(self, update=False):
        return self.localFileSize


class _Sidecar(object):
    def _initSidecarState(self):
        self.sidecarEnabled = False
        self.subJobs, self.subFetching, self.subHandled, self.subFiles = [], False, False, []

    def _writeSubtitleFiles(self, filePath):
        return self.subFiles

    def _prepareSidecarData(self, meta):
        pass


class _DMHelper(object):
    STS = types.SimpleNamespace(WAITING=0, DOWNLOADING=1, DOWNLOADED=2, INTERRUPTED=3, ERROR=4)

    @staticmethod
    def GET_FFMPEG_PATH():
        return "ffmpeg"

    @staticmethod
    def dashPartFiles(filePath):
        return [filePath + ".dash.resume", filePath + ".dash-v.part", filePath + ".dash-a.part"]

    @staticmethod
    def getFileSize(path):
        return os.path.getsize(path) if os.path.isfile(path) else -1

    removed = []

    @staticmethod
    def removeResumeFiles(filePath):
        _DMHelper.removed.append(filePath)


@pytest.fixture
def env():
    saved = dict(sys.modules)
    try:
        yield _setUp()
    finally:
        # also when the setup failed: the stubs must not reach the tests after this one
        sys.modules.clear()
        sys.modules.update(saved)


def _setUp():
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(
        dash_out_container=types.SimpleNamespace(value="matroska"), download_subtitles=types.SimpleNamespace(value="srt"))))
    for pkg in ("Components", "Tools", "Plugins", "Plugins.Extensions", PKG, PKG + ".tools", PKG + ".iptvdm",
                PKG + ".components", PKG + ".p2p3", PKG + ".libs"):
        _stubModule(pkg)
    _stubModule(PKG + ".tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None, iptv_system=None,
                eConnectCallback=lambda *a: None, rm=lambda p: None, WriteTextFile=lambda *a: None, GetNice=lambda: 0,
                KeepDebugArtifact=lambda *a: False)
    types_mod = _load(PKG + ".tools.iptvtypes", os.path.join(ROOT, "tools", "iptvtypes.py"))
    _stubModule(PKG + ".iptvdm.basedownloader", BaseDownloader=_Base)
    _stubModule(PKG + ".iptvdm.iptvdh", DMHelper=_DMHelper)
    _stubModule(PKG + ".iptvdm.downloaderhelpers", SidecarMixin=_Sidecar, shellQuote=lambda s: s,
                MKV_LANG_CODES={"de": "ger", "en": "eng"}, subtitleLangCode=lambda lang: (lang or "")[:2].lower(),
                safeRemoveFile=lambda p: os.path.isfile(p) and os.remove(p))
    _stubModule(PKG + ".components.iptvplayerinit", TranslateTXT=lambda t: t)
    _stubModule(PKG + ".p2p3.manipulateStrings", strDecode=lambda t: t)
    _stubModule("Tools.BoundFunction", boundFunction=lambda *a: None)
    _stubModule("Components.config", config=cfg)
    _stubModule("enigma", eConsoleAppContainer=object, eTimer=object)
    dashmpd = _load(PKG + ".libs.dashmpd", os.path.join(ROOT, "libs", "dashmpd.py"))
    _load(PKG + ".iptvdm.ffmpegdownloader", os.path.join(ROOT, "iptvdm", "ffmpegdownloader.py"))
    module = _load("dashdownloader_under_test", os.path.join(ROOT, "iptvdm", "dashdownloader.py"))
    module.DASHDownloader.RETRY_WAIT = 0
    module.mpd = dashmpd
    module.strwithmeta = types_mod.strwithmeta
    module.cfg = cfg.plugins.iptvplayer
    return module


class _Resp(object):
    def __init__(self, data, status=200, headers=None):
        self.stream = io.BytesIO(data)
        self.status = status
        self.headers = headers or {}

    def read(self, size=-1):
        return self.stream.read(size)

    def close(self):
        pass


def _server(dl, pages, fail=None, asked=None, onAsk=None):
    # dashmpd.openUrl answered from pages {url: bytes}; fail {url: number of 503 answers first}; Range honoured
    fail = dict(fail or {})

    def fakeOpen(url, headers, byteRange="", timeout=15, gzipOk=False):
        if asked is not None:
            asked.append((url, byteRange))
        if onAsk:
            onAsk(url)
        if fail.get(url):
            fail[url] -= 1
            raise HTTPError(url, 503, "busy", {}, None)
        if url not in pages:
            raise HTTPError(url, 404, "not found", {}, None)
        data = pages[url]
        if byteRange:
            first, last = byteRange.split("-")
            part = data[int(first):int(last) + 1]
            return _Resp(part, 206, {"Content-Range": "bytes %s/%d" % (byteRange, len(data))})
        return _Resp(data)
    sys.modules[type(dl).__module__].dashmpd.openUrl = fakeOpen


def _link(env, sel):
    return env.strwithmeta(MPD_URL, {"iptv_proto": "mpd", "iptv_dash_sel": sel, "Referer": "https://site/"})


def test_plan_template_and_timeline(env):
    plan = env.mpd.downloadPlan(TEMPLATE, MPD_URL, "v=v1|vi=0.0|vh=720|a=a1|ai=1.0")
    video, audio = plan["tracks"]
    assert plan["duration"] == 9
    assert video["init"] == ("https://cdn.example/v/v1/init.mp4", "")
    # 9 s / 4 s: 3 segments, the last one counted from the period length
    assert [u.rsplit("/", 1)[1] for u, _r in video["segments"]] == ["1.m4s", "2.m4s", "3.m4s"] and video["counted"]
    assert [u.rsplit("/", 1)[1] for u, _r in audio["segments"]] == ["0.m4s", "5000.m4s"] and not audio["counted"]


def test_plan_list_ranges_base_and_end_number(env):
    plan = env.mpd.downloadPlan(OTHERS, MPD_URL, "v=list|a=file")
    video, audio = plan["tracks"]
    assert video["init"] == ("https://cdn.example/v/list.mp4", "0-99")
    assert video["segments"] == [("https://cdn.example/v/list.mp4", "100-199"), ("https://cdn.example/v/list.mp4", "200-299")]
    assert audio["single"] and audio["segments"] == [("https://cdn.example/v/audio.mp4", "")]
    tmpl = env.mpd.downloadPlan(OTHERS, MPD_URL, "v=tmpl")["tracks"][0]
    # startNumber 5 .. endNumber 7 (the period would give 6)
    assert [u.rsplit("/", 1)[1] for u, _r in tmpl["segments"]] == ["005.m4s", "006.m4s", "007.m4s"] and not tmpl["counted"]
    with pytest.raises(ValueError):
        env.mpd.downloadPlan(OTHERS, MPD_URL, "v=drm")
    with pytest.raises(ValueError):
        env.mpd.downloadPlan(TEMPLATE.replace('type="static"', 'type="dynamic"'), MPD_URL, "v=v1")


def _pages():
    base = "https://cdn.example/v/"
    return {base + "v1/init.mp4": b"VI", base + "v1/1.m4s": b"V1", base + "v1/2.m4s": b"V2",
            base + "a/init.mp4": b"AI", base + "a/0.m4s": b"A0", base + "a/5000.m4s": b"A5"}


def test_load_writes_the_parts(env, tmp_path, monkeypatch):
    dl = env.DASHDownloader()
    path = str(tmp_path / "film.mkv")
    asked = []
    # v1/3.m4s is missing (9 s rounded up to 3 segments of 4 s); a/0.m4s answers 503 twice first
    _server(dl, _pages(), fail={"https://cdn.example/v/a/0.m4s": 2}, asked=asked)
    monkeypatch.setattr(env.mpd, "fetchManifest", lambda url: (MPD_URL, TEMPLATE))
    work = {"done": 0, "all": 0, "bytes": 0}
    dl._load(_link(env, "v=v1|a=a1"), path, False, work, threading.Event())
    assert work["result"] == "done", work
    assert open(path + ".dash-v.part", "rb").read() == b"VIV1V2"
    assert open(path + ".dash-a.part", "rb").read() == b"AIA0A5"
    assert work["done"] == work["all"] == 7 and work["bytes"] == 12
    assert [u for u, _r in asked].count("https://cdn.example/v/a/0.m4s") == 3


def test_failed_segment_stops_with_error(env, tmp_path, monkeypatch):
    dl = env.DASHDownloader()
    pages = _pages()
    del pages["https://cdn.example/v/v1/2.m4s"]
    _server(dl, pages)
    monkeypatch.setattr(env.mpd, "fetchManifest", lambda url: (MPD_URL, TEMPLATE))
    work = {"done": 0, "all": 0, "bytes": 0}
    dl._load(_link(env, "v=v1|a=a1"), str(tmp_path / "film.mkv"), False, work, threading.Event())
    assert work["result"] == "error" and "v1/2.m4s" in work["error"]


def test_stop_and_continue(env, tmp_path, monkeypatch):
    path = str(tmp_path / "film.mkv")
    monkeypatch.setattr(env.mpd, "fetchManifest", lambda url: (MPD_URL, TEMPLATE))
    stop = threading.Event()
    dl = env.DASHDownloader()
    dl.WORKERS, dl.QUEUED = 1, 1
    # stopped while the first audio segment is asked for
    _server(dl, _pages(), onAsk=lambda url: url.endswith("a/0.m4s") and stop.set())
    work = {"done": 0, "all": 0, "bytes": 0}
    dl._load(_link(env, "v=v1|a=a1"), path, False, work, stop)
    assert work["result"] == "stopped"
    assert open(path + ".dash-v.part", "rb").read() == b"VIV1V2"
    asked = []
    dl = env.DASHDownloader()
    _server(dl, _pages(), asked=asked)
    work = {"done": 0, "all": 0, "bytes": 0}
    dl._load(_link(env, "v=v1|a=a1"), path, True, work, threading.Event())
    assert work["result"] == "done"
    # only the audio after its init again
    assert [u.rsplit("/", 1)[1] for u, _r in asked] == ["0.m4s", "5000.m4s"]
    assert open(path + ".dash-v.part", "rb").read() == b"VIV1V2"
    assert open(path + ".dash-a.part", "rb").read() == b"AIA0A5"
    # a part file shorter than its state: started over
    open(path + ".dash-v.part", "wb").close()
    asked[:] = []
    dl._load(_link(env, "v=v1|a=a1"), path, True, {"done": 0, "all": 0, "bytes": 0}, threading.Event())
    assert len(asked) == 7 and open(path + ".dash-v.part", "rb").read() == b"VIV1V2"


def test_single_file_in_pieces(env, tmp_path, monkeypatch):
    dl = env.DASHDownloader()
    dl.CHUNK = 4
    body = b"0123456789"
    pages = {"https://cdn.example/v/audio.mp4": body, "https://cdn.example/v/t/005.m4s": b"T5",
             "https://cdn.example/v/t/006.m4s": b"T6", "https://cdn.example/v/t/007.m4s": b"T7"}
    asked = []
    _server(dl, pages, asked=asked)
    monkeypatch.setattr(env.mpd, "fetchManifest", lambda url: (MPD_URL, OTHERS))
    work = {"done": 0, "all": 0, "bytes": 0}
    path = str(tmp_path / "film.mkv")
    dl._load(_link(env, "v=tmpl|a=file"), path, False, work, threading.Event())
    assert work["result"] == "done"
    assert open(path + ".dash-a.part", "rb").read() == body
    # the size probe, then the pieces (asked for at the same time, written in order)
    ranges = [r for u, r in asked if u.endswith("audio.mp4")]
    assert ranges[0] == "0-0" and sorted(ranges[1:]) == ["0-3", "4-7", "8-9"]


def test_mux_command(env, tmp_path):
    dl = env.DASHDownloader()
    dl.allowFinalRename = True
    path = str(tmp_path / "film.mkv")
    dl.url = _link(env, "v=v1|a=a1")
    dl.filePath = path
    dl.work = {"parts": [(path + ".dash-v.part", "video", ""), (path + ".dash-a.part", "audio", "de")], "bytes": 12}
    run = []
    dl._execute = run.append
    dl._startMux()
    # the audio language of the MPD (the part files carry none)
    assert run[0] == ["ffmpeg", "-y", "-i", path + ".dash-v.part", "-i", path + ".dash-a.part", "-map", "0", "-map", "1",
                      "-c", "copy", "-metadata:s:a:0", "language=ger", "-f", "matroska", path]
    # every segment is there: a clean exit is a whole file, the list shows it loaded
    dl.totalDuration = 9
    assert dl._looksComplete(0) and not dl._looksComplete(1)
    assert dl.getDownloadedFileDuration() == 9 and dl.getLocalFileSize() == 12


def test_mux_takes_fetched_subtitles(env, tmp_path):
    # setting "MKV / .srt": the subtitles fetched by then go into this mux, no second copy of the file afterwards
    env.cfg.download_subtitles.value = "mkv"
    dl = env.DASHDownloader()
    dl.allowFinalRename = True
    path = str(tmp_path / "film.mp4")
    dl.url = _link(env, "v=v1|a=a1")
    dl.filePath = path
    dl.work = {"parts": [(path + ".dash-v.part", "video", ""), (path + ".dash-a.part", "audio", "en")], "bytes": 12}
    dl.subJobs = [{"lang": "en"}]
    dl.subFiles = [{"path": str(tmp_path / "film.en.srt"), "lang": "en", "title": "English | SDH"}]
    run = []
    dl._execute = run.append
    dl._startMux()
    cmd = run[0]
    assert cmd[cmd.index("-c") - 6:cmd.index("-c")] == ["-map", "0", "-map", "1", "-map", "2"]
    assert str(tmp_path / "film.en.srt") in cmd and "language=eng" in cmd and "title=English / SDH" in cmd
    assert dl.subHandled
    # still fetching when the segments are in: the step after the mux as before
    dl = env.DASHDownloader()
    dl.allowFinalRename = True
    dl.url, dl.filePath = _link(env, "v=v1"), path
    dl.work = {"parts": [(path + ".dash-v.part", "video", "")], "bytes": 1}
    dl.subJobs, dl.subFetching = [{"lang": "en"}], True
    run = []
    dl._execute = run.append
    dl._startMux()
    assert len([c for c in run[0] if c == "-i"]) == 1 and not dl.subHandled


def test_live_or_unselected_link_stays_with_ffmpeg(env, monkeypatch):
    called = []
    monkeypatch.setattr(sys.modules[PKG + ".iptvdm.ffmpegdownloader"].FFMPEGDownloader, "start", lambda self, *a: called.append(a) or 0)
    dl = env.DASHDownloader()
    dl.start(env.strwithmeta(MPD_URL, {"iptv_dash_sel": "v=1", "iptv_livestream": True}), "/tmp/x.mkv")
    dl.start(env.strwithmeta(MPD_URL, {}), "/tmp/x.mkv")
    assert len(called) == 2 and dl.phase == ""


def test_empty_answer_is_no_segment(env, tmp_path, monkeypatch):
    # an error page with Content-Length 0 would leave a gap in the file
    dl = env.DASHDownloader()
    pages = _pages()
    pages["https://cdn.example/v/v1/1.m4s"] = b""
    _server(dl, pages)
    monkeypatch.setattr(env.mpd, "fetchManifest", lambda url: (MPD_URL, TEMPLATE))
    work = {"done": 0, "all": 0, "bytes": 0}
    dl._load(_link(env, "v=v1|a=a1"), str(tmp_path / "film.mkv"), False, work, threading.Event())
    assert work["result"] == "error" and "empty answer" in work["error"]


def test_stream_starts_again_after_a_broken_connection(env, tmp_path):
    dl = env.DASHDownloader()
    dl.STREAM_BLOCK = 3
    answers = [_Resp(b"0123", headers={"Content-Length": "10"}), _Resp(b"0123456789", headers={"Content-Length": "10"})]
    sys.modules[type(dl).__module__].dashmpd.openUrl = lambda url, headers, byteRange="", timeout=15, gzipOk=False: answers.pop(0)
    work = {"bytes": 2}
    with open(str(tmp_path / "a.part"), "w+b") as fh:
        fh.write(b"AI")
        assert dl._stream("https://cdn.example/v/audio.mp4", {}, fh, work, threading.Event()) == b""
    # the cut first try is gone, the init before it stays
    assert open(str(tmp_path / "a.part"), "rb").read() == b"AI0123456789" and work["bytes"] == 12 and not answers


def test_remove_while_the_thread_finishes(env, tmp_path, monkeypatch):
    # "Remove file" of a stopped download whose thread still loads a segment: the thread removes its files at the end
    path = str(tmp_path / "film.mkv")
    monkeypatch.setattr(env.mpd, "fetchManifest", lambda url: (MPD_URL, TEMPLATE))
    asking, release = threading.Event(), threading.Event()

    def hold(url):
        if url.endswith("v1/1.m4s"):
            asking.set()
            release.wait(5)
    dl = env.DASHDownloader()
    _server(dl, _pages(), onAsk=hold)
    _DMHelper.removed[:] = []
    stop = threading.Event()
    work = {"done": 0, "all": 0, "bytes": 0}
    thread = threading.Thread(target=dl._load, args=(_link(env, "v=v1|a=a1"), path, False, work, stop))
    thread.start()
    assert asking.wait(5)
    assert env.discardLoader(path) and stop.is_set()
    release.set()
    thread.join(5)
    assert work["result"] == "stopped" and _DMHelper.removed == [path]
    # nothing running any more
    assert not env.discardLoader(path)


def test_failed_mux_keeps_the_requested_name(env, tmp_path):
    dl = env.DASHDownloader()
    path = str(tmp_path / "film.mkv")
    open(path, "wb").write(b"broken")
    dl.filePath, dl.phase, dl.status = path, "mux", _DMHelper.STS.ERROR
    dl._fixFileExtension()
    assert not os.path.exists(path)
