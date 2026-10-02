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
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(dash_out_container=_Value("matroska"))))
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
    _stubModule("Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings", strDecode=lambda t: t)
    _stubModule("Tools.BoundFunction", boundFunction=lambda *a: None)
    _stubModule("Components.config", config=cfg)
    _stubModule("enigma", eConsoleAppContainer=_Console)
    module = _load("ffmpegdownloader_under_test", os.path.join(ROOT, "iptvdm", "ffmpegdownloader.py"))
    module.cfg = cfg.plugins.iptvplayer
    module.strwithmeta = types_mod.strwithmeta
    module.written = written
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


def test_host_container_wins_and_others_stay_matroska(ff):
    ff.cfg.dash_out_container.value = "mp4"
    assert _dl(ff, "https://cdn/x/manifest.mpd", {"ff_out_container": "mpegts"})._outContainer() == "mpegts"
    # buffered playback keeps Matroska: the player holds the file under its name
    assert _dl(ff, "https://cdn/x/manifest.mpd", download=False)._outContainer() == "matroska"
    # not DASH: HLS via ffmpeg, merge of HLS parts
    assert _dl(ff, "https://cdn/x/index.m3u8")._outContainer() == "matroska"
    assert _dl(ff, "merge://audio_url|video_url", {"audio_url": "https://cdn/a.m3u8", "video_url": "https://cdn/v.m3u8"})._outContainer() == "matroska"


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
