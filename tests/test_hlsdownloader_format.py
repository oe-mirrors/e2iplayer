# Offline tests for the file format of IPTVPlayer/iptvdm/hlsdownloader.py downloads: the container hlsdl wrote
# (detected from the first bytes), the rename to its extension ("Automatic") and the remux to a fixed format.
# The enigma2 / E2iPlayer imports are stubbed; strwithmeta is the real one.
import importlib.util
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")

TS = (b"\x47" + b"\x00" * 187) * 4
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 600
AAC = b"\xff\xf1\x50\x80" + b"\x00" * 600


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
        self.localFileSize = self.remoteFileSize = -1

    def onStart(self):
        pass

    def onFinish(self):
        pass


class _Sidecar(object):
    sidecarEnabled = False
    sidecarImg = ''

    def _initSidecarState(self):
        pass

    def _writeTxtSidecar(self, path):
        pass

    def _finishDownloadFlow(self):
        self.finished = True


class _Console(object):
    def __init__(self):
        self.appClosed = self.stderrAvail = None


def _unique(path, withTmp=False, addDate=False):
    base, ext = os.path.splitext(path)
    return base + " 2" + ext


@pytest.fixture
def hls():
    saved = dict(sys.modules)
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(hls_out_container=_Value("auto"))))
    commands = []
    for pkg in ("Components", "Plugins", "Plugins.Extensions", "Plugins.Extensions.IPTVPlayer",
                "Plugins.Extensions.IPTVPlayer.tools", "Plugins.Extensions.IPTVPlayer.iptvdm"):
        _stubModule(pkg)
    types_mod = _load("Plugins.Extensions.IPTVPlayer.tools.iptvtypes", os.path.join(ROOT, "tools", "iptvtypes.py"))
    sys.modules["Plugins.Extensions.IPTVPlayer.tools.iptvtypes"] = types_mod
    _stubModule("Plugins.Extensions.IPTVPlayer.tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a: None,
                eConnectCallback=lambda *a: None, rm=os.remove)
    _stubModule("Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader", BaseDownloader=_Base)
    sts = types.SimpleNamespace(DOWNLOADING=1, DOWNLOADED=2, INTERRUPTED=3, ERROR=4, POSTPROCESSING=5)
    helper = types.SimpleNamespace(GET_FFMPEG_PATH=lambda: "ffmpeg", STS=sts, makeUnikalFileName=_unique,
                                   getFileSize=lambda p: os.path.getsize(p) if os.path.isfile(p) else -1)
    _stubModule("Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh", DMHelper=helper)
    _stubModule("Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers", ensureText=lambda t: t, fsPath=lambda p: p,
                shellQuote=lambda t: t, executeConsoleCmd=lambda console, cmd: commands.append(cmd),
                terminateToolsOfFile=lambda p: None, SidecarMixin=_Sidecar)
    _stubModule("Components.config", config=cfg)
    _stubModule("enigma", eConsoleAppContainer=_Console)
    module = _load("hlsdownloader_under_test", os.path.join(ROOT, "iptvdm", "hlsdownloader.py"))
    module.cfg = cfg.plugins.iptvplayer
    module.commands = commands
    module.sts = sts
    yield module
    sys.modules.clear()
    sys.modules.update(saved)


def _finished(hls, path, content, download=True):
    # a hlsdl run that ended with code 0 on a file holding <content>
    with open(path, "wb") as f:
        f.write(content)
    dl = hls.HLSDownloader()
    dl.allowFinalRename = download
    dl.url = "https://cdn/x/index.m3u8"
    dl.filePath = path
    dl.localFileSize = len(content)
    dl.status = hls.sts.DOWNLOADING
    dl._clearPostData()
    dl._cmdFinished(0)
    return dl


def test_detect_container(hls, tmp_path):
    for content, found in ((TS, "mpegts"), (MP4, "mp4"), (AAC, "adts"), (b"ID3" + b"\x00" * 600, "")):
        path = str(tmp_path / "x.mp4")
        with open(path, "wb") as f:
            f.write(content)
        dl = hls.HLSDownloader()
        dl.filePath = path
        assert dl._detectContainer() == found


def test_auto_renames_to_the_real_container(hls, tmp_path):
    dl = _finished(hls, str(tmp_path / "Film.mp4"), TS)
    assert dl.filePath == str(tmp_path / "Film.ts") and os.path.isfile(dl.filePath)
    assert dl.status == hls.sts.DOWNLOADED and not os.path.exists(str(tmp_path / "Film.mp4"))
    # fMP4 segments stay .mp4, radio (ADTS) becomes .aac, unknown keeps its name; no ffmpeg run
    assert _finished(hls, str(tmp_path / "Clip.mp4"), MP4).filePath == str(tmp_path / "Clip.mp4")
    assert _finished(hls, str(tmp_path / "Radio.mp4"), AAC).filePath == str(tmp_path / "Radio.aac")
    assert _finished(hls, str(tmp_path / "Odd.mp4"), b"ID3" + b"\x00" * 600).filePath == str(tmp_path / "Odd.mp4")
    assert hls.commands == []


def test_auto_rename_keeps_an_existing_file(hls, tmp_path):
    open(str(tmp_path / "Film.ts"), "wb").close()
    assert _finished(hls, str(tmp_path / "Film.mp4"), TS).filePath == str(tmp_path / "Film 2.ts")


def test_buffered_playback_keeps_the_file(hls, tmp_path):
    dl = _finished(hls, str(tmp_path / ".iptv_buffering.flv"), TS, download=False)
    assert dl.filePath == str(tmp_path / ".iptv_buffering.flv") and hls.commands == []


def test_fixed_format_remuxes_only_when_needed(hls, tmp_path):
    hls.cfg.hls_out_container.value = "mpegts"
    dl = _finished(hls, str(tmp_path / "Film.mp4"), TS)
    assert hls.commands == [] and dl.filePath == str(tmp_path / "Film.ts")
    hls.cfg.hls_out_container.value = "mp4"
    dl = _finished(hls, str(tmp_path / "Show.mp4"), TS)
    assert dl.status == hls.sts.POSTPROCESSING
    cmd = hls.commands[-1]
    assert "-movflags +faststart" in cmd and "-f mp4" in cmd and dl.tempRemuxPath.endswith(".iptv.remux.tmp.mp4")
    # ffmpeg done: the remuxed file takes the name of the downloaded one (same name, not removed afterwards)
    with open(dl.tempRemuxPath, "wb") as f:
        f.write(MP4)
    dl._cmdFinished(0)
    assert dl.filePath == str(tmp_path / "Show.mp4") and dl.status == hls.sts.DOWNLOADED
    with open(dl.filePath, "rb") as f:
        assert f.read()[4:8] == b"ftyp"
    assert not os.path.exists(str(tmp_path / "Show.iptv.remux.tmp.mp4"))


def test_fixed_matroska_and_host_meta(hls, tmp_path):
    hls.cfg.hls_out_container.value = "matroska"
    dl = _finished(hls, str(tmp_path / "Film.mp4"), TS)
    assert "-f matroska" in hls.commands[-1] and dl.tempRemuxPath.endswith(".iptv.remux.tmp.mkv")
    with open(dl.tempRemuxPath, "wb") as f:
        f.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 100)
    dl._cmdFinished(0)
    assert dl.filePath == str(tmp_path / "Film.mkv") and not os.path.exists(str(tmp_path / "Film.mp4"))
    # a host's own remux meta (SerienStream MKV) wins over the setting
    hls.cfg.hls_out_container.value = "mp4"
    dl = hls.HLSDownloader()
    dl._preparePostData({"e2i_postprocess_ffmpeg": "1", "e2i_postprocess_container": "mkv"})
    assert dl._getRemuxFormat() == ("matroska", ".mkv")


def _stopped(hls, path, content, live, download=True):
    # "stop" in the download manager on a hlsdl run that wrote <content>
    with open(path, "wb") as f:
        f.write(content)
    dl = hls.HLSDownloader()
    dl.allowFinalRename = download
    dl.url = "https://cdn/x/index.m3u8"
    dl.filePath = path
    dl.localFileSize = len(content)
    dl.liveStream = live
    dl.status = hls.sts.DOWNLOADING
    dl._clearPostData()
    dl._cmdFinished(-1, True)
    return dl


def test_stopping_a_live_recording_finishes_it(hls, tmp_path):
    # live: a finished file named after what hlsdl wrote
    dl = _stopped(hls, str(tmp_path / "Das Erste.mp4"), TS, live=True)
    assert dl.status == hls.sts.DOWNLOADED and dl.filePath == str(tmp_path / "Das Erste.ts")
    # a fixed file format: no remux after a stop (terminate() reports the finish at once), only the real name
    hls.cfg.hls_out_container.value = "matroska"
    del hls.commands[:]
    dl = _stopped(hls, str(tmp_path / "Live2.mp4"), TS, live=True)
    assert dl.status == hls.sts.DOWNLOADED and not hls.commands and dl.filePath == str(tmp_path / "Live2.ts")
    assert not getattr(dl, "finished", False)
    hls.cfg.hls_out_container.value = "auto"
    # a stopped video download stays interrupted, keeps its name (resume)
    dl = _stopped(hls, str(tmp_path / "Film.mp4"), TS, live=False)
    assert dl.status == hls.sts.INTERRUPTED and dl.filePath == str(tmp_path / "Film.mp4")
    # buffered playback of a live stream: nothing renamed
    dl = _stopped(hls, str(tmp_path / ".iptv_buffering.mp4"), TS, live=True, download=False)
    assert dl.status == hls.sts.INTERRUPTED
