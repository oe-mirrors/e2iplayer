# Offline tests for the output container of IPTVPlayer/iptvdm/ffmpegdownloader.py: which -f a
# download gets (host meta, DASH setting, default Matroska) and the ffmpeg command it writes.
# The enigma2 / E2iPlayer imports are stubbed; strwithmeta is the real one.
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")


class _Value(object):
    def __init__(self, value):
        self.value = value


def _stubModule(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Base(object):
    CODE_OK = 0

    def __init__(self):
        pass

    def onStart(self):
        pass


class _Sidecar(object):
    def _initSidecarState(self):
        pass

    def _prepareSidecarData(self, meta):
        pass


class _Console(object):
    def __init__(self):
        self.appClosed = self.stderrAvail = None

    def execute(self, cmd):
        self.cmd = cmd


@pytest.fixture
def ff():
    saved = dict(sys.modules)
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(dash_out_container=_Value("matroska"), hls_out_container=_Value("auto"), file_out_container=_Value("auto"))))
    written = {}
    for pkg in ("Components", "Tools", "Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer",
                "Plugins.Extensions.IPTVPlayer.tools", "Plugins.Extensions.IPTVPlayer.iptvdm",
                "Plugins.Extensions.IPTVPlayer.components", "Plugins.Extensions.IPTVPlayer.p2p3"):
        _stubModule(pkg)
    types_mod = _load("Plugins.Extensions.IPTVPlayer.tools.iptvtypes", os.path.join(ROOT, "tools", "iptvtypes.py"))
    sys.modules["Plugins.Extensions.IPTVPlayer.tools.iptvtypes"] = types_mod
    _stubModule("Plugins.Extensions.IPTVPlayer.tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None,
                iptv_system=None, eConnectCallback=lambda *a: None, rm=lambda p: None,
                WriteTextFile=written.__setitem__, GetNice=lambda: 0, KeepDebugArtifact=lambda *a: False)
    _stubModule("Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader", BaseDownloader=_Base)
    helper = types.SimpleNamespace(GET_FFMPEG_PATH=lambda: "ffmpeg", STS=types.SimpleNamespace(DOWNLOADING=1),
                                   getDownloaderParamFromUrlWithMeta=lambda url, b=False: (str(url), {}))
    _stubModule("Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh", DMHelper=helper)
    _stubModule("Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers", SidecarMixin=_Sidecar)
    _stubModule("Plugins.Extensions.IPTVPlayer.components.iptvplayerinit", TranslateTXT=lambda t: t)
    started = []
    _stubModule("Plugins.Extensions.IPTVPlayer.components.asynccall", AsyncMethod=lambda fnc: (lambda *a: started.append(fnc)))
    _stubModule("Plugins.Extensions.IPTVPlayer.p2p3.UrlParse", urljoin=__import__("urllib.parse").parse.urljoin)
    _stubModule("Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings", strDecode=lambda t: t)
    _stubModule("Tools.BoundFunction", boundFunction=lambda *a: None)
    _stubModule("Components.config", config=cfg)
    _stubModule("enigma", eConsoleAppContainer=_Console)
    module = _load("ffmpegdownloader_under_test", os.path.join(ROOT, "iptvdm", "ffmpegdownloader.py"))
    module.cfg = cfg.plugins.iptvplayer
    module.strwithmeta = types_mod.strwithmeta
    module.written = written
    module.started = started
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


def _dl(ff, url, meta=None, download=True):
    dl = ff.FFMPEGDownloader()
    dl.allowFinalRename = download
    dl.url = ff.strwithmeta(url, meta or {})
    return dl


def test_dash_download_uses_setting(ff):
    for value in ("matroska", "mp4", "mpegts"):
        ff.cfg.dash_out_container.value = value
        assert _dl(ff, "https://cdn/x/manifest.mpd")._outContainer() == value
        assert _dl(ff, "https://cdn/x/play", {"iptv_proto": "mpd"})._outContainer() == value
        assert _dl(ff, "merge://audio_url|video_url", {"audio_url": "https://cdn/a.mpd", "video_url": "https://cdn/v.mpd"})._outContainer() == value


def test_host_container_wins_and_playback_stays_matroska(ff):
    ff.cfg.dash_out_container.value = "mp4"
    ff.cfg.file_out_container.value = "mp4"
    assert _dl(ff, "https://cdn/x/manifest.mpd", {"ff_out_container": "mpegts"})._outContainer() == "mpegts"
    assert _dl(ff, "https://cdn/x/video.mp4", {"ff_out_container": "matroska"})._outContainer() == "matroska"
    # buffered playback keeps Matroska: the player holds the file under its name
    assert _dl(ff, "https://cdn/x/manifest.mpd", download=False)._outContainer() == "matroska"
    assert _dl(ff, "https://cdn/x/video.mp4", download=False)._outContainer() == "matroska"


def test_auto_follows_the_source(ff):
    assert _dl(ff, "https://www.porntrex.com/get_file/19/ab/3359675_1080p.mp4/")._outContainer() == "mp4"
    assert _dl(ff, "https://cdn/x/clip.webm?token=1")._outContainer() == "webm"
    assert _dl(ff, "https://cdn/x/index.m3u8")._outContainer() == "mpegts"
    assert _dl(ff, "https://cdn/x/play", {"iptv_proto": "m3u8", "iptv_livestream": True})._outContainer() == "mpegts"
    # separate audio/video parts, a live single file and unknown sources stay Matroska
    assert _dl(ff, "merge://audio_url|video_url", {"audio_url": "https://cdn/a.m3u8", "video_url": "https://cdn/v.m3u8"})._outContainer() == "matroska"
    assert _dl(ff, "https://cdn/x/live.mp4", {"iptv_livestream": True})._outContainer() == "matroska"
    assert _dl(ff, "https://cdn/x/play?id=5")._outContainer() == "matroska"


def test_fixed_settings_per_source(ff):
    hlsMerge = {"audio_url": "https://cdn/a.m3u8", "video_url": "https://cdn/v.m3u8"}
    for value in ("matroska", "mp4", "mpegts"):
        # single files follow the file setting, HLS (also a merge of HLS parts) the HLS setting
        ff.cfg.file_out_container.value = value
        ff.cfg.hls_out_container.value = "auto"
        assert _dl(ff, "https://cdn/x/video.mp4")._outContainer() == value
        assert _dl(ff, "https://cdn/x/index.m3u8")._outContainer() == "mpegts"
        assert _dl(ff, "merge://audio_url|video_url", hlsMerge)._outContainer() == "matroska"
        ff.cfg.file_out_container.value = "auto"
        ff.cfg.hls_out_container.value = value
        assert _dl(ff, "https://cdn/x/video.mp4")._outContainer() == "mp4"
        assert _dl(ff, "https://cdn/x/index.m3u8")._outContainer() == value
        assert _dl(ff, "https://cdn/x/play", {"iptv_proto": "m3u8"})._outContainer() == value
        assert _dl(ff, "merge://audio_url|video_url", hlsMerge)._outContainer() == value
    # DASH keeps its own setting
    ff.cfg.dash_out_container.value = "matroska"
    assert _dl(ff, "https://cdn/x/manifest.mpd")._outContainer() == "matroska"


def test_command_line(ff):
    ff.cfg.dash_out_container.value = "mp4"
    dl = _dl(ff, "https://cdn/x/manifest.mpd")
    dl.start(dl.url, "/hdd/movie/Film.mp4")
    cmd = ff.written["/hdd/movie/Film.mp4.iptv.cmd"].split("|")
    assert cmd[-5:] == ["-movflags", "+faststart", "-f", "mp4", "/hdd/movie/Film.mp4"]
    assert cmd[cmd.index("-c:v"):cmd.index("-c:v") + 4] == ["-c:v", "copy", "-c:a", "copy"]
    ff.cfg.dash_out_container.value = "matroska"
    dl = _dl(ff, "https://cdn/x/manifest.mpd")
    dl.start(dl.url, "/hdd/movie/Film2.mp4")
    cmd = ff.written["/hdd/movie/Film2.mp4.iptv.cmd"].split("|")
    assert "-movflags" not in cmd and cmd[-3:] == ["-f", "matroska", "/hdd/movie/Film2.mp4"]
    assert ff.FFMPEGDownloader.CONTAINER_EXT["mpegts"] == ".ts"


def _finished(ff, live, terminated, size=5000, url="https://cdn/x/live.m3u8", meta=None):
    # _cmdFinished of a download with `size` bytes on disk; which steps it takes
    ff.DMHelper.STS.DOWNLOADED, ff.DMHelper.STS.INTERRUPTED, ff.DMHelper.STS.ERROR = "DOWNLOADED", "INTERRUPTED", "ERROR"
    ff.DMHelper.getFileSize = lambda path: size
    dl = _dl(ff, url, {"iptv_proto": "m3u8"} if meta is None else meta)
    dl.filePath, dl.fileCmdPath, dl.console, dl.localFileSize, dl.sidecarEnabled = "/hdd/rec/Cam.mp4", "", None, 0, False
    dl.liveStream = live
    steps = []
    dl._fixFileExtension = lambda: steps.append("rename")
    dl._finishDownloadFlow = lambda: steps.append("finish")
    dl._cmdFinished(-1 if terminated else 0, terminated)
    return dl.status, steps


def test_stopping_a_live_recording_finishes_it(ff):
    # stopping is how a live recording ends: a finished file, named after its container (MPEG-TS -> .ts)
    # (terminate() reports the finish itself: no finish flow of its own)
    assert _finished(ff, live=True, terminated=True) == ("DOWNLOADED", ["rename"])
    # a stopped video download stays interrupted (resume / download again), nothing renamed
    assert _finished(ff, live=False, terminated=True) == ("INTERRUPTED", [])
    # a live stop without any data is no recording
    assert _finished(ff, live=True, terminated=True, size=0)[0] == "INTERRUPTED"


def test_speed_from_the_file_without_bitrate(ff):
    import datetime
    dl = _dl(ff, "https://cdn/x/live.m3u8")
    dl.filePath, dl.localFileSize, dl.lastUpadateTime, dl.downloadSpeed = "/hdd/rec/Cam.ts", 0, None, 0
    sizes = [1000000, 3000000]
    ff.DMHelper.getFileSize = lambda path: sizes[0]
    dl.updateStatistic()
    dl.sizeSample = (dl.sizeSample[0] - datetime.timedelta(seconds=2), dl.sizeSample[1])
    ff.DMHelper.getFileSize = lambda path: sizes[1]
    dl.updateStatistic()
    assert 900000 <= dl.downloadSpeed <= 1100000  # 2 MB in 2 s
    # ffmpeg's own speed (bitrate x speed) wins when its progress line has it
    dl.speedFromProgress, dl.downloadSpeed = True, 123
    dl.updateStatistic()
    assert dl.downloadSpeed == 123


def _pages(answers):
    # getPage stand-in: url -> playlist text
    return lambda url, params: (url in answers, answers.get(url, ''))


def test_manifest_live_check(ff):
    live = "#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXTINF:2,\nseg1.ts\n"
    vod = live + "#EXT-X-ENDLIST\n"
    master = "#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nvideo/720.m3u8\n"
    assert ff.manifestIsLive("https://c/live.m3u8", _pages({"https://c/live.m3u8": live})) is True
    assert ff.manifestIsLive("https://c/vod.m3u8", _pages({"https://c/vod.m3u8": vod})) is False
    assert ff.manifestIsLive("https://c/x.m3u8", _pages({"https://c/x.m3u8": "#EXTM3U\n#EXT-X-PLAYLIST-TYPE:VOD\n"})) is False
    # master playlist: its first variant decides
    assert ff.manifestIsLive("https://c/m.m3u8", _pages({"https://c/m.m3u8": master, "https://c/video/720.m3u8": vod})) is False
    assert ff.manifestIsLive("https://c/m.m3u8", _pages({"https://c/m.m3u8": master, "https://c/video/720.m3u8": live})) is True
    mpd = '<?xml version="1.0"?>\n<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="%s" profiles="x">'
    assert ff.manifestIsLive("https://c/a.mpd", _pages({"https://c/a.mpd": mpd % "dynamic"})) is True
    assert ff.manifestIsLive("https://c/a.mpd", _pages({"https://c/a.mpd": mpd % "static"})) is False
    # unreadable / an error page: no answer
    assert ff.manifestIsLive("https://c/gone.m3u8", _pages({})) is None
    assert ff.manifestIsLive("https://c/x.m3u8", _pages({"https://c/x.m3u8": "<html>403</html>"})) is None


def test_live_decision(ff):
    # a single file is never live, also without a duration from ffmpeg
    dl = _dl(ff, "https://cdn/x/video.mp4")
    dl._startLiveCheck(dl.url.meta)
    dl.liveStream = True
    assert dl.liveState == {"live": False} and dl._isLiveRecording() is False
    # HLS: checked in a work thread; until it answers ffmpeg's missing duration decides, then the playlist
    dl = _dl(ff, "https://cdn/x/play.m3u8", {"iptv_proto": "m3u8"})
    dl._startLiveCheck(dl.url.meta)
    assert dl.liveState == {"live": None} and ff.started
    dl.liveStream = True
    assert dl._isLiveRecording() is True
    dl.liveState["live"] = False  # a VOD whose duration ffmpeg could not read
    assert dl._isLiveRecording() is False
    # merge:// checks its video part; the link's own live mark always wins
    dl = _dl(ff, "merge://audio_url|video_url", {"audio_url": "https://c/a.m3u8", "video_url": "https://c/v.m3u8"})
    del ff.started[:]
    dl._startLiveCheck(dl.url.meta)
    assert dl.liveState == {"live": None} and len(ff.started) == 1
    dl = _dl(ff, "https://cdn/x/video.mp4", {"iptv_livestream": True})
    dl._startLiveCheck(dl.url.meta)
    assert dl._isLiveRecording() is True
    # buffered playback: no check at all
    dl = _dl(ff, "https://cdn/x/play.m3u8", {"iptv_proto": "m3u8"}, download=False)
    dl._startLiveCheck(dl.url.meta)
    assert dl.liveState == {}


def test_live_stop_keeps_the_name_of_mp4(ff):
    # MP4 / MOV: ffmpeg, stopped just now, still reopens the file by name for the index (+faststart) - no rename
    assert _finished(ff, live=True, terminated=True, url="https://cdn/x/live.mp4", meta={}) == ("DOWNLOADED", [])
    ff.cfg.hls_out_container.value = "mp4"
    assert _finished(ff, live=True, terminated=True) == ("DOWNLOADED", [])
    ff.cfg.hls_out_container.value = "auto"


def test_live_check_failure_does_not_stop_the_download(ff):
    dl = _dl(ff, "https://cdn/x/manifest.mpd")

    def broken(meta):
        raise ValueError("unexpected")
    dl._startLiveCheck = broken
    dl.start(dl.url, "/hdd/movie/Live.mkv")
    assert "/hdd/movie/Live.mkv.iptv.cmd" in ff.written and dl.liveState == {}
