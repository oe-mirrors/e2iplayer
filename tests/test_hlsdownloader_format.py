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

    def _prepareSidecarData(self, meta):
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
    cfg = types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(
        hls_out_container=_Value("auto"), hlsdlLiveStartOffset=_Value("30"))))
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
                                   getFileSize=lambda p: os.path.getsize(p) if os.path.isfile(p) else -1,
                                   getBaseHLSDLCmd=lambda params: '/bin/hlsdl -q -f -b  -u "UA"  -h "Referer: https://r/" ',
                                   hlsdlSupportsResume=lambda: True, hasHlsdlResumeFile=lambda p: False,
                                   removeHlsdlResumeFiles=lambda p: None)
    _stubModule("Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh", DMHelper=helper)
    _stubModule("Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers", ensureText=lambda t: t.decode("utf-8") if isinstance(t, bytes) else t, fsPath=lambda p: p,
                shellQuote=lambda t: t, executeConsoleCmd=lambda console, cmd: commands.append(cmd),
                terminateToolsOfFile=lambda p: None, SidecarMixin=_Sidecar,
                H264_FIX_OPTS=("-bsf:v", "h264_metadata=zero_new_constraint_set_flags=1"),
                h264FixRefused=lambda t: "bitstream filter" in t or "zero_new_constraint_set_flags" in t)
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


def test_remux_log(hls, tmp_path):
    # ffmpeg writes to <name>.iptv.remux.log: removed after the remux, its text in the debug log when it failed
    logged = []
    hls.printDBG = logged.append
    hls.cfg.hls_out_container.value = "matroska"
    for ok in (True, False):
        dl = _finished(hls, str(tmp_path / "Film.mp4"), TS)
        log = str(tmp_path / "Film.iptv.remux.log")
        assert '>"%s" 2>&1' % log in hls.commands[-1]
        with open(log, "w") as f:
            f.write("Packet corrupt")
        if ok:
            with open(dl.tempRemuxPath, "wb") as f:
                f.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 100)
        dl._cmdFinished(0 if ok else 1)
        assert not os.path.exists(log) and dl.status == hls.sts.DOWNLOADED
        assert any("Packet corrupt" in m for m in logged) != ok
    # stopped during the remux: temp file and log removed
    dl = _finished(hls, str(tmp_path / "Show.mp4"), TS)
    for path in (dl.tempRemuxPath, str(tmp_path / "Show.iptv.remux.log")):
        open(path, "w").close()
    dl._cmdFinished(-1, True)
    assert not os.path.exists(dl.tempRemuxPath) and not os.path.exists(str(tmp_path / "Show.iptv.remux.log"))
    hls.cfg.hls_out_container.value = "auto"


def _tsPacket(pid, payload, start=True):
    head = bytes([0x47, (0x40 if start else 0) | (pid >> 8), pid & 0xff, 0x10])
    return head + payload + b"\xff" * (184 - len(payload))


def _ptsBytes(value, marker):
    return bytes([(marker << 4) | ((value >> 29) & 0x0e) | 1, (value >> 22) & 0xff, ((value >> 14) & 0xfe) | 1,
                  (value >> 7) & 0xff, ((value << 1) & 0xfe) | 1])


def _videoTs(steps, frames=120):
    # PAT -> PMT 0x1000 -> H.264 on 0x100, one PES per frame with PTS + DTS spaced by <steps> (repeated)
    pat = b"\x00" + b"\x00\xb0\x0d\x00\x01\xc1\x00\x00" + b"\x00\x01\xf0\x00" + b"\x00" * 4
    pmt = b"\x00" + b"\x02\xb0\x12\x00\x01\xc1\x00\x00" + b"\xe1\x00\xf0\x00" + b"\x1b\xe1\x00\xf0\x00" + b"\x00" * 4
    out = _tsPacket(0, pat) + _tsPacket(0x1000, pmt)
    dts = 900000
    for i in range(frames):
        pes = b"\x00\x00\x01\xe0\x00\x00\x80\xc0\x0a" + _ptsBytes(dts + 3000, 3) + _ptsBytes(dts, 1) + b"\x00\x00\x00\x01\x09"
        out += _tsPacket(0x100, pes) + _tsPacket(0x100, b"\x00" * 184, start=False)
        dts += steps[i % len(steps)]
    return out


def test_irregular_frame_times_keep_ts(hls, tmp_path):
    # 24 fps film on a 30 fps raster (VOE): remuxed to MKV it is black on the box -> stays TS, no ffmpeg run
    hls.cfg.hls_out_container.value = "matroska"
    dl = _finished(hls, str(tmp_path / "Film.mp4"), _videoTs([3000, 3000, 3000, 6000]))
    assert dl.status == hls.sts.DOWNLOADED and hls.commands == [] and dl.filePath == str(tmp_path / "Film.ts")
    # evenly spaced (25 fps, 23.976 fps alternating 3753 / 3754, a jump between two segments): remuxed
    for name, steps in (("A", [3600]), ("B", [3753, 3754]), ("C", [3600] * 59 + [450000])):
        dl = _finished(hls, str(tmp_path / ("%s.mp4" % name)), _videoTs(steps))
        assert dl.status == hls.sts.POSTPROCESSING and "-f matroska" in hls.commands[-1]
    # too few frames to tell: remuxed as before
    del hls.commands[:]
    dl = _finished(hls, str(tmp_path / "Short.mp4"), _videoTs([3000, 3000, 3000, 6000], frames=20))
    assert dl.status == hls.sts.POSTPROCESSING and len(hls.commands) == 1
    hls.cfg.hls_out_container.value = "auto"


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


def _exited(hls, path, content, code, done, total, reported=None):
    # a hlsdl run that ended with <code> after reporting <done>/<total> seconds and <reported> bytes
    with open(path, "wb") as f:
        f.write(content)
    dl = hls.HLSDownloader()
    dl.allowFinalRename = True
    dl.url = "https://cdn/x/index.m3u8"
    dl.filePath = path
    dl.localFileSize = len(content) if reported is None else reported
    dl.downloadDuration, dl.totalDuration = done, total
    dl.status = hls.sts.DOWNLOADING
    dl._clearPostData()
    dl._cmdFinished(code)
    return dl


def test_exit_code_after_the_whole_duration(hls, tmp_path):
    # some hlsdl builds exit 1 after the last segment: the whole duration and every reported byte -> complete
    assert _exited(hls, str(tmp_path / "Film.mp4"), TS, 1, 7808, 7808).status == hls.sts.DOWNLOADED
    # stopped early, or the file shorter than reported (full disk) -> interrupted
    assert _exited(hls, str(tmp_path / "Early.mp4"), TS, 1, 7000, 7808).status == hls.sts.INTERRUPTED
    assert _exited(hls, str(tmp_path / "Disk.mp4"), TS, 1, 7808, 7808, len(TS) + 1).status == hls.sts.INTERRUPTED
    # an HTTP error reported by hlsdl stays interrupted
    dl = hls.HLSDownloader()
    dl.lastErrorCode, dl.liveStream = 403, False
    assert dl._isIncompleteDownload(1)


HLSDL_OPTSTRING = "bH:W:A:vqbfRFK:ctdo:u:h:s:i:r:w:Ie:p:k:n:a:C:"  # hlsdl misc.c parse_argv


def _posixGetopt(args):
    # getopt() of musl (the static feed hlsdl): stops at the first argument that is no option, no permutation
    opts, i = [], 0
    while i < len(args) and args[i].startswith("-") and args[i] != "-":
        flag = args[i][1]
        pos = HLSDL_OPTSTRING.index(flag)
        if HLSDL_OPTSTRING[pos + 1:pos + 2] == ":":
            value = args[i][2:] or args[i + 1]
            i += 1 if args[i][2:] else 2
        else:
            value, i = None, i + 1
        opts.append((flag, value))
    return opts, args[i:]


def test_hlsdl_options_before_the_url(hls, tmp_path):
    # an option after the url ends the musl getopt early: hlsdl prints its help and exits 0 without a download
    import shlex
    url = "https://cdn/hls2/v_,n,.urlset/index-v1-a1.m3u8?t=a+b=&s=1"
    meta = {"iptv_m3u8_seg_download_retry": "3", "iptv_m3u8_key_uri_replace_old": "k1", "iptv_m3u8_key_uri_replace_new": "k2"}
    for download in (True, False):
        hls.commands[:] = []
        dl = hls.HLSDownloader()
        dl.allowFinalRename = download
        dl.start(hls.strwithmeta(url, meta), str(tmp_path / "Film (DE).mp4"))
        args = shlex.split(hls.commands[-1].rsplit(" > /dev/null", 1)[0])[1:]
        opts, rest = _posixGetopt(args)
        assert rest == [url]
        flags = dict(opts)
        assert flags["o"] == str(tmp_path / "Film (DE).mp4") and flags["w"] == "3" and flags["k"] == "k1"
        assert ("R" in flags) == download and ("s" in flags) == (not download)


H264_FIX = "-bsf:v h264_metadata=zero_new_constraint_set_flags=1"


def test_remux_fixes_constrained_high_h264(hls, tmp_path):
    # BongaCams "Constrained High": the MKV remux sets constraint_set4/5 to 0 (no re-encoding); HEVC or an old ffmpeg
    # refuse the filter -> the remux again without it
    hls.cfg.hls_out_container.value = "matroska"
    dl = _finished(hls, str(tmp_path / "Bonga.mp4"), TS)
    assert H264_FIX in hls.commands[-1]
    log = str(tmp_path / "Bonga.iptv.remux.log")
    with open(log, "w") as f:
        f.write("[vost#0:0/copy @ 0x1] Codec 'hevc' (173) is not supported by the bitstream filter 'h264_metadata'.\n"
                "Error initializing bitstream filter: Invalid argument\n")
    count = len(hls.commands)
    dl._cmdFinished(234)
    assert len(hls.commands) == count + 1 and H264_FIX not in hls.commands[-1]
    assert dl.status == hls.sts.POSTPROCESSING and not dl.h264Fix
    # the second remux works
    with open(dl.tempRemuxPath, "wb") as f:
        f.write(b"\x1a\x45\xdf\xa3" + b"\x00" * 100)
    dl._cmdFinished(0)
    assert dl.status == hls.sts.DOWNLOADED and os.path.isfile(str(tmp_path / "Bonga.mkv"))
    # an other failure: no second remux
    dl = _finished(hls, str(tmp_path / "Other.mp4"), TS)
    count = len(hls.commands)
    dl._cmdFinished(1)
    assert len(hls.commands) == count and dl.status == hls.sts.DOWNLOADED
    hls.cfg.hls_out_container.value = "auto"
