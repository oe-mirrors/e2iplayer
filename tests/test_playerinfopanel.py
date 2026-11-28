# Offline test of the INFO panel of the movie player (components/iptvplayerinfopanel.py): Enigma2 is stubbed, the
# texts, the layout in real pixels and the background request are the real ones.
import importlib.util
import json
import os
import re
import sys
import tempfile
import types
import xml.etree.ElementTree as ET

import pytest

# Pillow is on every box; a PC / CI without it skips the tests that draw pictures
needsPil = pytest.mark.skipif(importlib.util.find_spec("PIL") is None, reason="Pillow not installed")

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "IPTVPlayer")
LINE_H = 25
CHARS_PER_LINE = 40


class _Point(object):
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class _Size(object):
    def __init__(self, w, h):
        self.w, self.h = w, h

    def width(self):
        return self.w

    def height(self):
        return self.h


class _Instance(object):
    # eLabel / ePixmap in real pixels: a line break every CHARS_PER_LINE characters
    def __init__(self, x, y, w, h):
        self.pos = _Point(x, y)
        self.dim = _Size(w, h)
        self.text = ''

    def position(self):
        return self.pos

    def size(self):
        return self.dim

    def move(self, point):
        self.pos = point

    def resize(self, size):
        self.dim = size

    def setText(self, text):
        self.text = text

    def calculateSize(self):
        lines = max(1, (len(self.text) + CHARS_PER_LINE - 1) // CHARS_PER_LINE)
        return _Size(self.dim.w, lines * LINE_H)

    def setPixmap(self, pixmap):
        self.pixmap = pixmap


class _Widget(object):
    def __init__(self, text=''):
        self.text = text
        self.visible = True
        self.instance = None

    def setText(self, text):
        self.text = text
        if self.instance:
            self.instance.setText(text)

    def getText(self):
        return self.text

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False


class _Cover(_Widget):
    def __init__(self):
        _Widget.__init__(self)
        self.decoded = []
        self.pixmaps = []

    def decodeCover(self, path, callback, ident):
        self.decoded.append(path)
        callback({'Pixmap': 'pixmap', 'FileName': path})
        return True

    def updatePixmap(self, pixmap, path):
        self.pixmaps.append((pixmap, path))


class _Timer(object):
    def __init__(self):
        self.timeout = 'timeout'
        self.running = False

    def start(self, ms, singleShot=False):
        self.running = True

    def stop(self):
        self.running = False


class _System(object):
    # iptv_system: the command is only remembered, the test finishes it
    started = []

    def __init__(self, cmd, callback):
        self.cmd = cmd
        self.callback = callback
        self.killed = False
        _System.started.append(self)

    def kill(self):
        self.killed = True


class _Article(object):
    RICH_DESC_PARAMS = ['year', 'genre', 'language']
    RICH_DESC_LABELS = {'year': 'Year:', 'genre': 'Genre:', 'language': 'Language'}

    def __init__(self, text='', richDescParams=None):
        self.text = text
        self.richDescParams = richDescParams if richDescParams is not None else {}


@pytest.fixture(scope="module")
def panelModule():
    saved = {}

    def stub(name, **attrs):
        saved[name] = sys.modules.get(name)
        mod = types.ModuleType(name)
        mod.__dict__.update(attrs)
        sys.modules[name] = mod

    base = "Plugins.Extensions.IPTVPlayer"
    for package in ("Plugins", "Plugins.Extensions", base, base + ".components", base + ".tools", "Components"):
        stub(package)
    stub(base + ".components.cover", Cover=_Cover)
    stub(base + ".components.ihost", ArticleContent=_Article)
    stub(base + ".components.iptvplayerinit", TranslateTXT=lambda text: text)
    stub(base + ".iptvdm")
    stub(base + ".iptvdm.downloaderhelpers", shellQuote=lambda text: text.replace('"', '\\"'))
    stub(base + ".tools.iptvtools", printDBG=lambda *a: None, printExc=lambda *a, **k: None, iptv_system=_System,
         eConnectCallback=lambda signal, fnc: fnc, StripColorCodes=lambda text: re.sub(r'\\c[0-9a-fA-F]{8}', '', text or ''),
         ShortHostTitle=lambda title: re.sub(r'^https?://(?:www\.)?([^\s?#]+?)/?$', r'\1', title.strip()))
    stub("Components.Label", Label=_Widget)
    stub("Components.Pixmap", Pixmap=_Widget)
    stub("Components.config", config=types.SimpleNamespace(plugins=types.SimpleNamespace(iptvplayer=types.SimpleNamespace(
        infopanel_background=types.SimpleNamespace(value='picture')))))
    stub("Tools")
    # no pixmap: the plain panels (the rounded pictures have tests of their own)
    stub("Tools.LoadPixmap", LoadPixmap=lambda path, cached=True: None)
    stub("enigma", ePoint=_Point, eSize=_Size, eTimer=_Timer)

    spec = importlib.util.spec_from_file_location("iptvplayerinfopanel_test", os.path.join(ROOT, "components", "iptvplayerinfopanel.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PANEL_PICTURE = os.path.join(tempfile.mkdtemp(), 'panel_%s.png')
    yield module
    for name, mod in saved.items():
        if mod is None:
            del sys.modules[name]
        else:
            sys.modules[name] = mod


class _Url(str):
    meta = {}


def _meta(url, **meta):
    url = _Url(url)
    url.meta = meta
    return url


class _Thread(object):
    alive = True

    def isAlive(self):
        return self.alive


class _Owner(dict):
    title = 'The title'
    hostName = 'Some host'
    streamUrl = 'https://www.cdn.example.com/x/index.m3u8'

    def __init__(self):
        dict.__init__(self)
        self.playback = {'AudioTrack': {'encode': 'AAC', 'name': 'eng'}, 'VideoTrack': {'encode': 'H264'}}
        self['videoInfo'] = _Widget('H264 1920x1080p, 25fps, 16:9, HLS')

    localFile = ''

    def getStreamSourceUrl(self):
        return self.streamUrl

    def getLocalFilePath(self):
        return self.localFile


def _panel(module, params=None, hasCover=False, tmp_path=None):
    owner = _Owner()
    params = dict(params or {})
    if hasCover:
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"picture")
        params['cover_path'] = str(cover)
    panel = module.PlayerInfoPanel(owner, params)
    # the skin at 1920x1080: the instances the skin engine would make
    root = ET.fromstring('<screen>%s</screen>' % module.PlayerInfoPanel.skinWidgets(1.5))
    for widget in root:
        x, y = [int(v) for v in widget.get('position').split(',')]
        w, h = [int(v) for v in widget.get('size').split(',')]
        owner[widget.get('name')].instance = _Instance(x, y, w, h)
    return owner, panel


def _rect(owner, name):
    instance = owner[name].instance
    return instance.position().x(), instance.position().y(), instance.size().width(), instance.size().height()


@pytest.mark.parametrize("url,expected", [
    ("https://www.cdn.example.com/x/index.m3u8", "cdn.example.com"),
    ("https://s12.CDN.example.com:8443/x.mp4?a=b|Referer=https://other.org/", "s12.cdn.example.com"),
    ("http://127.0.0.1:8080/relay.m3u8", ""),
    ("/hdd/movie/file.mp4", ""),
    ("file:///hdd/movie/file.mp4", ""),
    ("", ""),
])
def test_server_name(panelModule, url, expected):
    assert panelModule.serverName(url) == expected


def test_server_name_of_merged_streams_is_the_video_server(panelModule):
    url = _meta("merge://audio_url|video_url", iptv_proto="merge", video_url="https://video.example.com/v.mp4")
    assert panelModule.serverName(url) == "video.example.com"


@pytest.mark.parametrize("mirror,name,expected", [
    ("", "Vidoza", "Vidoza"),
    ("Vidoza", "720p", "Vidoza / 720p"),
    ("Vidoza", "Vidoza 720p", "Vidoza 720p"),
    ("Vidoza", "https://cdn.example.com/x.mp4", "Vidoza"),
    ("", "https://cdn.example.com/x.mp4", ""),
    ("\\c00ff0000Vidoza", "720p", "Vidoza / 720p"),
    ("VOE (Ger-Sub)", "bitrate: 1207970 res: 1280x640 mp4a,avc1 24fps", "VOE (Ger-Sub) / 1280x640"),
    ("Vidara.to (1080p)", "[German] bitrate: 560000 res: 1720x720 mp4a,avc1 30fps", "Vidara.to (1080p) / [German] 1720x720"),
    ("VOE", "[Deutsch] bitrate: 1207970", "VOE / [Deutsch]"),
    ("VOE", "bitrate: 1207970", "VOE"),
    ("", "bitrate: 1207970", ""),
])
def test_link_display_name(panelModule, mirror, name, expected):
    assert panelModule.linkDisplayName(mirror, name) == expected


@pytest.mark.parametrize("title,site,expected", [
    ("https://filmpalast.to/", "", "filmpalast.to"),
    ("https://www.arte.tv/", "", "arte.tv"),
    ("http://dr.dk/drtv/", "", "dr.dk/drtv"),
    ("ARADrama", "", "ARADrama"),
    ("XXX", "AMATEUR8", "XXX / AMATEUR8"),
    ("", "", ""),
])
def test_host_display_name(panelModule, title, site, expected):
    assert panelModule.hostDisplayName(title, site) == expected


def test_stream_without_a_video_track_is_no_video(panelModule):
    # radio: the infobar's text is only the stream type, not a video format
    assert panelModule.streamLine("HLS", {'encode': 'AAC'}, False) == "HLS  ·  Audio: AAC"
    assert panelModule.streamLine("AVC 1920x1080p, HLS", {'encode': 'AAC'}, True) == "Video: AVC 1920x1080p, HLS  ·  Audio: AAC"


def test_bitrate_round_up_changes_the_unit(panelModule):
    assert panelModule.bitrateText(999499) == "999 kbit/s"
    assert panelModule.bitrateText(999500) == "1.0 Mbit/s"


def test_unreadable_probe_answer_keeps_the_panel_working(panelModule, monkeypatch):
    monkeypatch.setattr(_Owner, "localFile", '/hdd/a.mkv')
    del _System.started[:]
    owner, panel = _panel(panelModule)
    panel.show()
    _System.started[0].callback(0, '{"streams": 5}')
    assert panel.probe == {} and panel.visible
    assert owner['infoPanelTitle'].text == 'The title'


def test_translated_labels_with_a_space(panelModule, monkeypatch):
    # de.po: msgid "Video" -> msgstr "Video " made "Video : AVC" on the box
    monkeypatch.setattr(panelModule, "_", lambda text: "Video " if text == "Video" else text)
    assert panelModule.streamLine("AVC", {}) == "Video: AVC"


def test_host_title_replaces_the_module_name(panelModule):
    owner, panel = _panel(panelModule, {'host_title': 'XXX / AMATEUR8'})
    panel.show()
    assert owner['infoPanelSource'].text.startswith('Host: XXX / AMATEUR8')


# what ffprobe 7/8 print for a Matroska file with HEVC HDR and two audio tracks, shortened
PROBE_MKV = json.dumps({
    "streams": [
        {"index": 0, "codec_name": "hevc", "profile": "Main 10", "codec_type": "video", "level": 150, "pix_fmt": "yuv420p10le", "color_transfer": "smpte2084", "disposition": {"attached_pic": 0}},
        {"index": 1, "codec_name": "eac3", "codec_type": "audio", "sample_rate": "48000", "channels": 6, "channel_layout": "5.1(side)", "bit_rate": "640000", "tags": {"language": "deu"}},
        {"index": 2, "codec_name": "aac", "profile": "LC", "codec_type": "audio", "sample_rate": "44100", "channels": 2, "channel_layout": "stereo", "tags": {"language": "und"}},
        {"index": 3, "codec_name": "subrip", "codec_type": "subtitle"},
        {"index": 4, "codec_name": "mjpeg", "codec_type": "video", "disposition": {"attached_pic": 1}},
    ],
    "format": {"format_name": "matroska,webm", "bit_rate": "4200000"},
})
PROBE_MP4 = json.dumps({
    "streams": [
        {"codec_name": "h264", "profile": "High", "codec_type": "video", "level": 41, "pix_fmt": "yuv420p", "color_transfer": "bt709", "bit_rate": "850000"},
        {"codec_name": "aac", "profile": "LC", "codec_type": "audio", "sample_rate": "48000", "channels": 2, "bit_rate": "128000"},
    ],
    "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "bit_rate": "980000"},
})


def test_detail_line(panelModule):
    assert panelModule.detailLine(json.loads(PROBE_MKV)) == ("MKV  ·  Bitrate: 4.2 Mbit/s  ·  Video: H.265 Main 10@5.0, 10 Bit, HDR10  ·  "
                                                             "Audio: E-AC3, 5.1, 48 kHz, 640 kbit/s (deu) / AAC, 2.0, 44.1 kHz")
    assert panelModule.detailLine(json.loads(PROBE_MP4)) == ("MP4  ·  Bitrate: 978 kbit/s  ·  Video: H.264 High@4.1, 850 kbit/s  ·  "
                                                             "Audio: AAC, 2 ch, 48 kHz, 128 kbit/s")
    assert panelModule.detailLine({}) == ""
    assert panelModule.detailLine({}, 3500000) == "Bitrate: 3.5 Mbit/s"


def test_bitrate_of_a_buffer_file_still_being_written(panelModule):
    # box 01.11.: an MP4 of 5.5 Mbit/s, format.bit_rate = its size so far through the full length
    probe = {"streams": [{"codec_name": "h264", "codec_type": "video", "bit_rate": "5500000"}, {"codec_name": "aac", "codec_type": "audio", "bit_rate": "126000"}],
             "format": {"format_name": "mov,mp4", "bit_rate": "234000"}}
    assert "Bitrate: 5.6 Mbit/s" in panelModule.detailLine(probe)
    # the link list knows it better still
    assert "Bitrate: 8.5 Mbit/s" in panelModule.detailLine(probe, 8519000)
    # a track without a bitrate (TS, most of MKV): the sum would be too low, the file's value then
    del probe["streams"][0]["bit_rate"]
    assert "Bitrate: 234 kbit/s" in panelModule.detailLine(probe)


@pytest.mark.parametrize("data,expected", [("", {}), ("not json", {}), (None, {}), ("[]", {}), ('{"format": {}}', {"format": {}})])
def test_parse_probe_never_fails(panelModule, data, expected):
    assert panelModule.parseProbe(data) == expected


@pytest.mark.parametrize("value,expected", [(4200000, "4.2 Mbit/s"), ("128000", "128 kbit/s"), (999, ""), (0, ""), (None, ""), ("N/A", "")])
def test_bitrate_text(panelModule, value, expected):
    assert panelModule.bitrateText(value) == expected


def test_stream_bitrate_of_the_link_list(panelModule):
    assert panelModule.streamBitrate(_meta("https://a/b.m3u8", iptv_proto="m3u8", iptv_bitrate=2500000)) == 2500000
    assert panelModule.streamBitrate(_meta("https://a/b.f4m", iptv_proto="f4m", iptv_bitrate=7)) == 0
    assert panelModule.streamBitrate(_meta("https://a/b.m3u8", iptv_bitrate="x")) == 0
    assert panelModule.streamBitrate("https://a/b.mp4") == 0


def test_stream_shows_the_link_bitrate_without_ffprobe(panelModule, monkeypatch):
    # no second connection to the server
    monkeypatch.setattr(_Owner, "streamUrl", _meta("https://cdn.example.com/a.m3u8", iptv_proto="m3u8", iptv_bitrate=2500000))
    del _System.started[:]
    owner, panel = _panel(panelModule)
    panel.show()
    assert _System.started == []
    assert owner['infoPanelDetail'].text == "Bitrate: 2.5 Mbit/s"


def test_local_file_is_read_with_ffprobe_once(panelModule, monkeypatch):
    monkeypatch.setattr(_Owner, "localFile", '/hdd/movie/a "b".mkv')
    monkeypatch.setattr(_Owner, "streamUrl", '/hdd/movie/a "b".mkv')
    del _System.started[:]
    owner, panel = _panel(panelModule)
    panel.show()
    assert len(_System.started) == 1 and panel.probeTimer.running
    assert _System.started[0].cmd == '/usr/bin/ffprobe -v quiet -print_format json -show_format -show_streams "/hdd/movie/a \\"b\\".mkv"'
    assert owner['infoPanelDetail'].text == ''

    # still running: not a second one
    panel.hide()
    panel.show()
    assert len(_System.started) == 1

    _System.started[0].callback(0, PROBE_MKV)
    assert not panel.probeTimer.running
    assert owner['infoPanelDetail'].text.startswith("MKV  ·  Bitrate: 4.2 Mbit/s")

    panel.hide()
    panel.show()
    assert len(_System.started) == 1
    assert owner['infoPanelDetail'].text.startswith("MKV")


def test_unreadable_file_or_missing_ffprobe_tries_again_on_the_next_info(panelModule, monkeypatch):
    monkeypatch.setattr(_Owner, "localFile", '/tmp/.iptv_buffering.flv')
    del _System.started[:]
    owner, panel = _panel(panelModule)
    panel.show()
    _System.started[0].callback(127, '')
    assert panel.visible and owner['infoPanelDetail'].text == ''
    panel.hide()
    panel.show()
    assert len(_System.started) == 2


def test_probe_stops_at_timeout_and_with_the_player(panelModule, monkeypatch):
    monkeypatch.setattr(_Owner, "localFile", '/hdd/a.mkv')
    del _System.started[:]
    owner, panel = _panel(panelModule)
    panel.show()
    panel._stopProbe()
    assert _System.started[0].killed and panel.probeHandle is None and not panel.probeTimer.running
    panel.hide()
    panel.show()
    assert len(_System.started) == 2
    panel.close()
    assert _System.started[1].killed
    panel.show()  # no start after the close
    assert len(_System.started) == 2


def test_long_source_wraps_and_moves_the_rows_down(panelModule):
    # a long link name cut off the server (serienstream, 01.11.)
    owner, panel = _panel(panelModule, {'link_name': 'A long mirror name'})
    sourceY = _rect(owner, 'infoPanelSource')[1]
    panel.show()
    assert owner['infoPanelSource'].text.endswith('Server: cdn.example.com')
    assert _rect(owner, 'infoPanelSource')[3] == 2 * LINE_H
    assert _rect(owner, 'infoPanelStream')[1] == sourceY + 2 * LINE_H


def test_short_source_keeps_the_rows_up(panelModule, monkeypatch):
    monkeypatch.setattr(_Owner, "streamUrl", "")
    owner, panel = _panel(panelModule)
    sourceY = _rect(owner, 'infoPanelSource')[1]
    panel.show()
    assert owner['infoPanelSource'].text == 'Host: Some host'
    assert _rect(owner, 'infoPanelSource')[3] == LINE_H
    assert _rect(owner, 'infoPanelStream')[1] == sourceY + LINE_H


def test_no_source_leaves_no_gap(panelModule, monkeypatch):
    # a file of the download manager: no host, no server
    monkeypatch.setattr(_Owner, "hostName", "")
    monkeypatch.setattr(_Owner, "streamUrl", "/hdd/movie/file.mkv")
    owner, panel = _panel(panelModule)
    sourceY = _rect(owner, 'infoPanelSource')[1]
    panel.show()
    assert owner['infoPanelSource'].text == ''
    assert _rect(owner, 'infoPanelStream')[1] == sourceY
    streamBottom = sourceY + _rect(owner, 'infoPanelStream')[3]
    assert _rect(owner, 'infoPanelBg')[1] + _rect(owner, 'infoPanelBg')[3] < streamBottom + 40


def test_lines(panelModule):
    assert panelModule.sourceLine("Host", "Vidoza", "cdn.org") == "Host: Host  ·  Link: Vidoza  ·  Server: cdn.org"
    assert panelModule.sourceLine("Host", "", "") == "Host: Host"
    assert panelModule.sourceLine("", "", "") == ""
    # exteplayer3 names MP2 "A_MPEG/L3"
    assert panelModule.streamLine(" H264 1920x1080p ", {'encode': 'MPEG/L3', 'name': 'und'}) == "Video: H264 1920x1080p  ·  Audio: MP2"
    assert panelModule.streamLine(" ", {'encode': 'AAC', 'name': 'deu'}) == "Audio: AAC (deu)"
    assert panelModule.streamLine(" ", {}) == ""
    assert panelModule.streamLine("", None) == ""


def test_meta_line(panelModule):
    params = {'genre': 'Drama|Action', 'year': '2020', 'language': 'de', 'unknown': 'x'}
    assert panelModule.metaLine(params) == "Year: 2020  ·  Genre: Drama Action  ·  Language: de"
    assert panelModule.metaLine({'custom_items_list': [('Label:', 'value'), 'broken', ('Empty', '')]}) == "Label: value"
    assert panelModule.metaLine('') == ""


def test_plain_text(panelModule):
    assert panelModule.plainText("\\c00ffffffA[/br]B|C \n\n D") == "A B C D"


def test_skin_stays_above_every_infobar(panelModule):
    # the infobar is placed at the bottom of the screen with its own height
    root = ET.fromstring('<screen>%s</screen>' % panelModule.PlayerInfoPanel.skinWidgets())
    bottom = 0
    for widget in root:
        x, y = [int(v) for v in widget.get('position').split(',')]
        w, h = [int(v) for v in widget.get('size').split(',')]
        assert x + w <= 1280
        bottom = max(bottom, y + h)
    skins = os.path.join(ROOT, "playerskins")
    for skin in os.listdir(skins):
        path = os.path.join(skins, skin, "playerskin.xml")
        if skin != "sd" and os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            size = re.search(r'name="playbackInfoBaner"[^>]*?size="\d+,(\d+)"', text)
            assert 720 - int(size.group(1)) >= bottom, skin


def test_every_player_skin_can_take_the_panel(panelModule):
    # __prepareSkin puts the widgets in front of the end of the screen
    skins = os.path.join(ROOT, "playerskins")
    for skin in os.listdir(skins):
        path = os.path.join(skins, skin, "playerskin.xml")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                assert f.read().count('</screen>') == 1, skin


def test_panel_without_list_shows_the_players_data(panelModule):
    owner, panel = _panel(panelModule)
    panel.show()
    assert panel.visible and owner['infoPanelBg'].visible
    assert owner['infoPanelTitle'].text == 'The title'
    assert owner['infoPanelSource'].text == 'Host: Some host  ·  Server: cdn.example.com'
    assert owner['infoPanelStream'].text == 'Video: H264 1920x1080p, 25fps, 16:9, HLS  ·  Audio: AAC (eng)'
    assert owner['infoPanelMeta'].text == ''
    assert not panel.timer.running
    # no cover: the text takes its place
    assert _rect(owner, 'infoPanelTitle')[0] == _rect(owner, 'infoPanelCover')[0]
    assert not owner['infoPanelCover'].visible
    panel.hide()
    assert not panel.visible and not owner['infoPanelTitle'].visible


def test_article_is_asked_once_in_the_background(panelModule):
    calls = []
    thread = _Thread()

    def provider(callback):
        calls.append(callback)
        return thread

    owner, panel = _panel(panelModule, {'info_provider': provider, 'info_description': 'From the list', 'link_name': 'Vidoza'})
    panel.show()
    assert len(calls) == 1 and panel.timer.running
    assert owner['infoPanelText'].text == 'From the list'
    assert owner['infoPanelMeta'].text == 'Loading...'
    assert 'Link: Vidoza' in owner['infoPanelSource'].text

    panel._checkArticle()
    assert panel.timer.running  # still on its way

    calls[0](types.SimpleNamespace(value=[_Article('From the page', {'year': '2020'})]))
    panel._checkArticle()
    assert not panel.timer.running
    assert owner['infoPanelText'].text == 'From the page'
    assert owner['infoPanelMeta'].text == 'Year: 2020'

    panel.hide()
    panel.show()
    assert len(calls) == 1
    assert owner['infoPanelText'].text == 'From the page'


@pytest.mark.parametrize("answer", [
    types.SimpleNamespace(value=[]),
    types.SimpleNamespace(value=[_Article('', {})]),
    None,
])
def test_no_article_keeps_the_description(panelModule, answer):
    thread = _Thread()
    calls = []

    def provider(callback):
        calls.append(callback)
        return thread

    owner, panel = _panel(panelModule, {'info_provider': provider, 'info_description': 'From the list'})
    panel.show()
    if answer is not None:
        calls[0](answer)
    thread.alive = False  # also a host that crashed: no answer at all
    panel._checkArticle()
    assert owner['infoPanelText'].text == 'From the list'
    assert owner['infoPanelMeta'].text == ''
    assert not panel.timer.running


def test_crashing_provider_does_not_break_the_panel(panelModule):
    def provider(callback):
        raise RuntimeError("host")

    owner, panel = _panel(panelModule, {'info_provider': provider, 'info_description': 'From the list'})
    panel.show()
    assert panel.visible
    assert owner['infoPanelText'].text == 'From the list'


def test_answer_after_the_panel_was_closed_is_ignored(panelModule):
    calls = []
    owner, panel = _panel(panelModule, {'info_provider': lambda cb: calls.append(cb) or _Thread()})
    panel.show()
    panel.close()
    assert not panel.timer.running and panel.timer_conn is None
    calls[0](types.SimpleNamespace(value=[_Article('Late')]))
    assert owner['infoPanelText'].text != 'Late'


def test_layout_follows_the_content(panelModule, tmp_path):
    longText = ' '.join(['word'] * 400)
    owner, panel = _panel(panelModule, {'info_description': longText}, True, tmp_path)
    fullHeight = owner['infoPanelText'].instance.size().height()
    panel.show()
    # cover shown and decoded, text beside it
    assert owner['infoPanelCover'].visible and owner['infoPanelCover'].decoded
    assert owner['infoPanelCover'].pixmaps[0][0] == 'pixmap'
    assert _rect(owner, 'infoPanelTitle')[0] > _rect(owner, 'infoPanelCover')[0] + _rect(owner, 'infoPanelCover')[2] - 1
    # a long text is cut to the height of its row at a word boundary, the row follows the formats directly
    text = owner['infoPanelText'].text
    assert text.endswith('…') and text[:-1].endswith('word')
    x, y, w, h = _rect(owner, 'infoPanelText')
    assert h <= fullHeight
    bgX, bgY, bgW, bgH = _rect(owner, 'infoPanelBg')
    assert y < 276 * 1.5  # moved up: no detail and no meta line
    assert y + h < bgY + bgH

    # the short text of the page: the panel gets lower, but stays as high as the cover
    panel.text = 'Short'
    panel._fill()
    assert _rect(owner, 'infoPanelText')[3] == LINE_H
    coverBottom = _rect(owner, 'infoPanelCover')[1] + _rect(owner, 'infoPanelCover')[3]
    assert _rect(owner, 'infoPanelBg')[1] + _rect(owner, 'infoPanelBg')[3] > coverBottom

    # a second layout starts from the full height again
    panel.text = longText
    panel._fill()
    assert _rect(owner, 'infoPanelText')[3] == h


def test_update_stream_only_while_visible(panelModule):
    owner, panel = _panel(panelModule)
    owner['videoInfo'].setText('H265 3840x2160p')
    panel.updateStream()
    assert owner['infoPanelStream'].text == ' ' or owner['infoPanelStream'].text == ''
    panel.show()
    owner.playback['AudioTrack'] = {'encode': 'AC3', 'name': 'deu'}
    panel.updateStream()
    assert owner['infoPanelStream'].text == 'Video: H265 3840x2160p  ·  Audio: AC3 (deu)'


# ---- the tracks of a newer exteplayer3: infobar badges and the "Playback info" page (INFO twice) ----
# v_c / a_c of exteplayer3 with its track info for front ends, as _mapTrack keeps them
EP3_VIDEO = {'id': 256, 'encode': 'HEVC', 'name': 'und', 'width': 3840, 'height': 1608, 'frame_rate': 23.976, 'progressive': True,
             'aspect_ratio': '2.35', 'hdr': 1, 'pr': 'Main 10@5.1', 'bd': 10, 'br': 0, 'dv': 8, 'cr': 'bt2020'}
EP3_AUDIO = {'id': 1, 'encode': 'DTS', 'name': 'eng', 'c': 8, 'd': 'DTS-HD MA', 't': 'Main', 'sr': 48000, 'br': 0, 'cl': '7.1', 'bps': 24}
OLD_VIDEO = {'id': 0, 'encode': 'MPEG4/ISO/AVC', 'name': 'und', 'width': 1920, 'height': 800, 'frame_rate': 25.0, 'progressive': True, 'aspect_ratio': '2.35'}


@pytest.mark.parametrize("track,expected", [
    ({'encode': 'AAC'}, 'AAC'),
    ({'encode': 'EAC3', 'd': 'Dolby Atmos'}, 'Dolby Atmos'),
    # the player decoded it itself: an older player names no codec, a newer one its display name
    ({'encode': 'IPCM'}, ''),
    ({'encode': 'IPCM', 'd': 'MP3'}, 'MP3'),
    ({'encode': 'MPEG/L3'}, 'MP2'),
    ({'encode': 'audio/x-ac3'}, 'AC3'),
    ({'encode': 'audio/mpeg'}, ''),
    ({'encode': 'AAC_LATM'}, 'AAC LATM'),
    ({}, ''),
])
def test_audio_codec_name(panelModule, track, expected):
    assert panelModule.audioCodecName(track) == expected


def test_screensaver_shows_no_decoder_output_as_format(panelModule):
    # box 20.11.: a podcast showed "IPCM" (the PCM of software decoding) as its format
    assert panelModule.audioText({'encode': 'IPCM', 'name': 'und'}) == ''
    assert panelModule.audioText({'encode': 'IPCM', 'name': 'ara', 'd': 'MP3'}) == 'MP3 (ara)'


@pytest.mark.parametrize("encode,expected", [
    ('MPEG4/ISO/AVC', ('H.264', 'H.264 (AVC)')),
    ('HEVC', ('HEVC', 'H.265 (HEVC)')),
    ('video/x-h265', ('HEVC', 'H.265 (HEVC)')),
    ('video/x-h264', ('H.264', 'H.264 (AVC)')),
    ('MPEG2', ('MPEG-2', 'MPEG-2')),
    ('MPEG4', ('MPEG-4', 'MPEG-4 Part 2')),
    ('VP9', ('VP9', 'VP9')),
    ('THEORA', ('THEORA', 'THEORA')),
])
def test_video_codec_names(panelModule, encode, expected):
    assert panelModule.videoCodecNames(encode) == expected


@pytest.mark.parametrize("track,expected", [
    ({'cl': '5.1(side)', 'c': 6}, '5.1'),
    ({'cl': 'stereo'}, '2.0'),
    ({'cl': '', 'c': 8}, '7.1'),
    ({'c': 5}, '5.0'),
    ({'c': 9}, '9 ch'),
    ({'c': 0}, ''),
    ({}, ''),
])
def test_channels_text(panelModule, track, expected):
    assert panelModule.channelsText(track) == expected


@pytest.mark.parametrize("size,expected", [
    ((3840, 2160), '4K'), ((3840, 1600), '4K'), ((1920, 800), 'FHD'), ((1440, 1080), 'FHD'), ((1280, 534), 'HD'),
    ((2560, 1440), 'QHD'), ((720, 576), 'SD'), ((0, 0), ''), ((1920, 0), ''),
])
def test_resolution_class(panelModule, size, expected):
    assert panelModule.resolutionClass(*size) == expected


@pytest.mark.parametrize("fps,expected", [(25.0, '25'), (23.976, '23.976'), (29.97, '29.97'), (59.94, '59.94'), (24.0005, '24'),
                                          (0, ''), (200, '200'), (None, '')])
def test_frame_rate_text(panelModule, fps, expected):
    assert panelModule.frameRateText(fps) == expected


def test_badges_of_a_newer_player(panelModule):
    assert panelModule.badgeList(EP3_VIDEO, EP3_AUDIO, 23.976) == [
        ('res', '4K', ''), ('video', '2160p', ''), ('video', 'HEVC', 'H.265'), ('video', '10bit', ''), ('video', 'HDR10', ''),
        ('video', 'DV', ''), ('video', '23.976', 'FPS'), ('audio', '7.1', 'Channels'), ('audio', 'DTS-HD MA', '')]


def test_badges_of_an_older_player_and_of_radio(panelModule):
    # a cinemascope 1920x800 is "1080p", an interlaced picture "i"
    assert panelModule.badgeList(OLD_VIDEO, {'encode': 'AC3', 'name': 'deu'}, 25) == [
        ('res', 'FHD', ''), ('video', '1080p', ''), ('video', 'H.264', 'AVC'), ('video', '25', 'FPS'), ('audio', 'AC3', '')]
    interlaced = dict(OLD_VIDEO, width=720, height=576, progressive=False)
    assert panelModule.badgeList(interlaced, {})[:2] == [('res', 'SD', ''), ('video', '576i', '')]
    # radio, software decoded by an older player: nothing that is not known
    assert panelModule.badgeList({}, {'encode': 'IPCM'}) == []
    assert panelModule.badgeList(None, {'encode': 'AAC', 'c': 2}) == [('audio', '2.0', 'Channels'), ('audio', 'AAC', '')]


def test_subtitle_badge(panelModule):
    subtitle = {'kind': 'embedded', 'lang': 'ger', 'format': 'SRT'}
    assert panelModule.badgeList({}, {}, 0, subtitle) == [('sub', 'GER', 'SRT')]
    assert panelModule.badgeList({}, {}, 0, {'kind': 'file', 'lang': '', 'format': 'SRT'}) == [('sub', 'SUB', 'SRT')]
    assert panelModule.badgeList({}, {}, 0, {}) == []


def test_info_row_texts(panelModule):
    subtitle = {'kind': 'embedded', 'lang': 'eng', 'format': 'PGS'}
    assert panelModule.stripTexts(EP3_VIDEO, EP3_AUDIO, subtitle, _langName) == [
        ('Video', '3840×1608 (2.35)'), ('Video codec', 'H.265 (HEVC)'), ('Audio', 'DTS-HD MA 7.1'), ('Audio codec', 'DTS'),
        ('Subtitles', 'English (PGS)')]
    # nothing known: empty values, subtitles off
    assert panelModule.stripTexts({}, {}, {}) == [('Video', ''), ('Video codec', ''), ('Audio', ''), ('Audio codec', ''), ('Subtitles', 'Off')]
    # software decoded by an older player: no codec family to name
    assert panelModule.stripTexts({}, {'encode': 'IPCM', 'c': 2})[2:4] == [('Audio', '2.0'), ('Audio codec', '')]


def _rows(sections):
    return dict((section, dict(rows)) for section, rows in sections)


def _langName(name):
    return {'eng': 'English', 'ger': 'German', 'de': 'German'}.get(name, name)


def test_tech_sections_of_a_newer_player(panelModule):
    subtitle = {'kind': 'embedded', 'index': 2, 'count': 3, 'lang': 'ger', 'title': 'Forced', 'format': 'PGS', 'forced': True}
    sections = panelModule.techSections(EP3_VIDEO, EP3_AUDIO, [{'id': 1}, {'id': 2}], subtitle, None, 'MKV', 0, 23.976, _langName)
    assert [section for section, rows in sections] == ['video', 'audio', 'subtitle']
    rows = _rows(sections)
    assert rows['video'] == {'Codec': 'H.265 (HEVC)', 'Profile': 'Main 10@5.1', 'Resolution': '3840×1608p  ·  4K', 'Aspect ratio': '2.35',
                             'Frame rate': '23.976 fps', 'Bit depth': '10 bit', 'HDR': 'HDR10 + Dolby Vision 8', 'Colour space': 'BT.2020',
                             'Stream': 'MKV'}
    assert rows['audio'] == {'Track': '1 / 2', 'Language': 'English', 'Title': 'Main', 'Codec': 'DTS-HD MA', 'Channels': '7.1 (8 ch)',
                             'Sample rate': '48 kHz', 'Bit depth': '24 bit'}
    assert rows['subtitle'] == {'Track': '2 / 3', 'Language': 'German', 'Title': 'Forced', 'Type': 'PGS', 'Forced': 'Yes'}
    # the order of the rows is fixed
    assert [label for label, value in sections[0][1]][:3] == ['Codec', 'Profile', 'Resolution']


def test_tech_sections_of_an_older_player_with_a_local_file(panelModule):
    # ffprobe fills in what the player does not say; the link's bitrate only when the video has none of its own
    audio = {'id': 1, 'encode': 'EAC3', 'name': 'deu'}
    sections = panelModule.techSections(OLD_VIDEO, audio, [{'id': 1}, {'id': 2}], {}, json.loads(PROBE_MKV), 'MKV', 3500000, 25)
    rows = _rows(sections)
    assert rows['video']['Codec'] == 'H.264 (AVC)'  # the player's codec wins
    assert rows['video']['Profile'] == 'Main 10@5.0' and rows['video']['Bit depth'] == '10 bit' and rows['video']['HDR'] == 'HDR10'
    assert rows['video']['Total bitrate'] == '3.5 Mbit/s'
    # no link bitrate (a download): the file's, as on page 1 (box 22.11.: missing on page 2)
    noLink = _rows(panelModule.techSections(OLD_VIDEO, audio, [], {}, json.loads(PROBE_MKV), 'MKV', 0, 25))
    assert noLink['video']['Total bitrate'] == '4.2 Mbit/s'
    assert rows['video']['Stream'] == 'MKV'
    assert rows['audio']['Codec'] == 'E-AC3' and rows['audio']['Channels'] == '5.1 (6 ch)' and rows['audio']['Sample rate'] == '48 kHz'
    assert rows['audio']['Bitrate'] == '640 kbit/s'
    assert rows['subtitle'] == {'Track': 'Off'}


def test_tech_sections_of_radio(panelModule):
    sections = panelModule.techSections({}, {'id': 0, 'encode': 'IPCM', 'name': 'und'}, [], {}, None, 'HLS', 128000, 0)
    rows = _rows(sections)
    assert rows['video'] == {'Stream': 'HLS'}
    assert rows['audio'] == {'Codec': 'PCM (software)'}
    sections = panelModule.techSections({}, {}, [], {}, None, '', 0, 0)
    assert _rows(sections)['video'] == {} and _rows(sections)['audio'] == {}


def test_tech_values_are_cut(panelModule):
    audio = {'id': 1, 'encode': 'AAC', 't': 'A very long track title that does not fit at all'}
    title = _rows(panelModule.techSections({}, audio, [], {}, None, '', 0, 0))['audio']['Title']
    assert len(title) == panelModule.VALUE_MAX and title.endswith('…')
    # capitals are wider: a song title in capitals is cut earlier (box 23.11.: "...WEDDIN" ran out of the row)
    assert panelModule.cutValue('ASHE - STOP THE WEDDING!') == 'ASHE - STOP THE WEDD…'
    assert panelModule.cutValue('HDR10 + Dolby Vision 8') == 'HDR10 + Dolby Vision 8'


class _TechOwner(_Owner):
    def __init__(self):
        _Owner.__init__(self)
        self.playback = {'VideoTrack': dict(EP3_VIDEO), 'AudioTrack': dict(EP3_AUDIO), 'AudioTracks': [dict(EP3_AUDIO)]}
        self.streamType = 'HLS'

    def currentFrameRate(self):
        return 23.976

    def currentSubtitleInfo(self):
        return {'kind': 'file', 'lang': 'de', 'title': 'movie.de.srt', 'format': 'SRT'}

    def _getStreamTypeLabel(self):
        return self.streamType

    def trackLanguageName(self, name):
        return _langName(name)


def _techPanel(module, owner):
    panel = module.PlayerInfoPanel(owner, {})
    root = ET.fromstring('<screen>%s</screen>' % module.PlayerInfoPanel.skinWidgets(1.5))
    for widget in root:
        x, y = [int(v) for v in widget.get('position').split(',')]
        w, h = [int(v) for v in widget.get('size').split(',')]
        owner[widget.get('name')].instance = _Instance(x, y, w, h)
    return panel


def test_info_twice_shows_the_playback_info(panelModule):
    owner = _TechOwner()
    panel = _techPanel(panelModule, owner)
    panel.show()
    assert panel.page == 1 and owner['infoPanelBg'].visible and not owner['techPanelBg'].visible
    panel.showTech()
    assert panel.page == 2 and panel.visible
    assert not owner['infoPanelBg'].visible and not owner['infoPanelTitle'].visible
    assert owner['techPanelBg'].visible and owner['techPanelTitle'].text == 'The title'
    assert owner['techPanelVideoHead'].text == 'Video' and owner['techPanelAudioHead'].text == 'Audio'
    keys = owner['techPanelVideoKeys'].text.split('\n')
    values = owner['techPanelVideoValues'].text.split('\n')
    assert len(keys) == len(values) and keys[0] == 'Codec' and values[0] == 'H.265 (HEVC)'
    assert 'Stream' in keys and values[keys.index('Stream')] == 'HLS'
    assert owner['techPanelAudioValues'].text.split('\n')[:2] == ['English', 'Main']
    assert owner['techPanelSubtitleValues'].text == 'German\nmovie.de.srt\nSRT\nFile'
    # the columns as high as their rows, the panel as high as the longest one
    bg = _rect(owner, 'techPanelBg')
    videoKeys = _rect(owner, 'techPanelVideoKeys')
    assert videoKeys[1] + videoKeys[3] <= bg[1] + bg[3]
    assert bg[3] <= panelModule.PlayerInfoPanel.PANEL_H * 1.5
    panel.hide()
    assert not panel.visible and panel.page == 0 and not owner['techPanelBg'].visible


def test_playback_info_follows_a_track_change(panelModule):
    owner = _TechOwner()
    panel = _techPanel(panelModule, owner)
    panel.showTech()
    owner.playback['AudioTrack'] = {'id': 2, 'encode': 'AC3', 'name': 'ger', 'c': 6}
    panel.updateStream()
    assert 'AC3' in owner['techPanelAudioValues'].text and '5.1 (6 ch)' in owner['techPanelAudioValues'].text
    # page 1 is not touched while page 2 is open
    assert owner['infoPanelStream'].text in (' ', '')


def test_empty_section_frees_its_column(panelModule):
    # radio without a stream type: the audio column takes the first place
    owner = _TechOwner()
    owner.playback = {'VideoTrack': {}, 'AudioTrack': {'id': 0, 'encode': 'AAC', 'c': 2}, 'AudioTracks': []}
    owner.streamType = ''
    panel = _techPanel(panelModule, owner)
    firstColumnX = _rect(owner, 'techPanelVideoHead')[0]
    panel.showTech()
    assert not owner['techPanelVideoHead'].visible and not owner['techPanelVideoKeys'].visible
    assert owner['techPanelAudioHead'].visible and _rect(owner, 'techPanelAudioHead')[0] == firstColumnX
    assert _rect(owner, 'techPanelSubtitleKeys')[0] < 455 * 1.5
    # two columns shown: one line between them
    assert owner['techPanelSep1'].visible and not owner['techPanelSep2'].visible


def test_playback_info_column_lines_and_opaque_panels(panelModule):
    # forum 25.11.: lines between Video / Audio / Subtitles; the film shone through the panels (alpha in the colour)
    owner = _TechOwner()
    panel = _techPanel(panelModule, owner)
    panel.showTech()
    assert owner['techPanelSep1'].visible and owner['techPanelSep2'].visible
    sep1, sep2 = _rect(owner, 'techPanelSep1'), _rect(owner, 'techPanelSep2')
    audioX, subtitleX = _rect(owner, 'techPanelAudioHead')[0], _rect(owner, 'techPanelSubtitleHead')[0]
    videoValues = _rect(owner, 'techPanelVideoValues')
    # in the gap between the columns, from the headings down to the rows' end
    assert videoValues[0] + videoValues[2] <= sep1[0] < audioX and sep1[0] < sep2[0] < subtitleX
    assert sep1[3] > 0 and sep1[1] + sep1[3] <= _rect(owner, 'techPanelBg')[1] + _rect(owner, 'techPanelBg')[3]
    skin = panelModule.PlayerInfoPanel.skinWidgets(1.0)
    colours = set(re.findall(r'backgroundColor="#([0-9a-fA-F]{2})', skin))
    assert colours == {'00'}, colours


def test_owner_without_the_new_methods(panelModule):
    # an owner like the tests' plain one has none of the helpers
    owner, panel = _panel(panelModule)
    panel.showTech()
    assert owner['techPanelBg'].visible
    assert owner['techPanelVideoKeys'].text.split('\n')[0] == 'Codec'


@needsPil
def test_rounded_panel_picture(panelModule, tmp_path):
    # forum 27.11.: round corners and a thin frame; the corners transparent, inside opaque
    from PIL import Image
    target = str(tmp_path / "panel.png")
    assert panelModule.makePanelPicture(target, 600, 300, 1.5)
    with Image.open(target) as img:
        assert img.mode == 'RGBA' and img.size == (600, 300)
        for corner in ((0, 0), (599, 0), (0, 299), (599, 299)):
            assert img.getpixel(corner)[3] == 0
        assert img.getpixel((300, 150)) == panelModule.PANEL_RGB + (255,)
        assert img.getpixel((300, 0)) == panelModule.FRAME_RGB + (255,)
    assert not panelModule.makePanelPicture(target, 4, 4, 1.0)


@needsPil
def test_panel_inside_from_backdrop_and_poster(panelModule, tmp_path):
    from PIL import Image
    backdrop = str(tmp_path / "backdrop.jpg")
    # left half red, right half blue: the piece under the panel at the right is blue, darkened
    img = Image.new('RGB', (1920, 1080), (200, 0, 0))
    img.paste(Image.new('RGB', (960, 1080), (0, 0, 200)), (960, 0))
    img.save(backdrop)
    inside = panelModule.panelInside(400, 200, backdrop, (1400, 100))
    r, g, b = inside.getpixel((200, 100))
    assert b > r and 60 < b < 160
    poster = str(tmp_path / "poster.png")
    Image.new('RGB', (200, 300), (0, 200, 0)).save(poster)
    r, g, b = panelModule.panelInside(400, 200, '', (0, 0), poster).getpixel((200, 100))
    assert g > r and 40 < g < 100
    assert panelModule.panelInside(400, 200) is None
    # a picture PIL can't read: the plain colour
    assert panelModule.panelInside(400, 200, str(tmp_path / "missing.jpg")) is None


@needsPil
def test_banner_picture_over_the_backdrop(panelModule, tmp_path):
    # forum 28.11.: over the backdrop the infobar is opaque (its transparent corners showed the film), the
    # backdrop shows in the corners and through its dark inside; its light lines stay as they are
    from PIL import Image
    backdrop = str(tmp_path / "backdrop.png")
    Image.new('RGB', (1920, 1080), (0, 0, 200)).save(backdrop)
    banner = Image.new('RGBA', (1280, 236), (17, 19, 23, 250))
    for corner in ((0, 0), (1279, 0), (0, 235), (1279, 235)):
        banner.putpixel(corner, (0, 0, 0, 0))
    for x in range(1280):
        for y in (99, 100, 101):
            banner.putpixel((x, y), (200, 200, 200, 255))
    source = str(tmp_path / "banner.png")
    banner.save(source)
    target = str(tmp_path / "out.png")
    assert panelModule.makeBannerPicture(target, source, 1920, 354, backdrop, (0, 726))
    with Image.open(target) as img:
        assert img.size == (1920, 354)
        rgba = img.convert('RGBA')
        assert rgba.getpixel((0, 0)) == (0, 0, 200, 255)
        r, g, b, a = rgba.getpixel((960, 50))
        assert a == 255 and b > r and 40 < b < 120
        r, g, b, a = rgba.getpixel((960, 150))
        assert a == 255 and abs(r - g) < 4 and r > 150


class _BackdropOwner(_TechOwner):
    backdrop = ''

    def backdropFile(self):
        return self.backdrop


@needsPil
def test_panels_take_the_rounded_picture(panelModule, monkeypatch, tmp_path):
    from PIL import Image
    loaded = []
    monkeypatch.setattr(panelModule, 'LoadPixmap', lambda path, cached=True: loaded.append(path) or 'pixmap')
    owner = _BackdropOwner()
    panel = _techPanel(panelModule, owner)
    panel.show()
    assert owner['infoPanelFrame'].visible and not owner['infoPanelBg'].visible
    assert _rect(owner, 'infoPanelFrame') == _rect(owner, 'infoPanelBg')
    assert owner['infoPanelFrame'].instance.pixmap == 'pixmap'
    count = len(loaded)
    panel.show()
    # the same panel again: the picture is not made a second time
    assert len(loaded) == count
    # the backdrop comes in: the open panel gets it
    owner.backdrop = str(tmp_path / "backdrop.jpg")
    Image.new('RGB', (1920, 1080), (0, 0, 200)).save(owner.backdrop)
    panel.backgroundChanged()
    assert len(loaded) == count + 1 and panel.frameKeys['info'][4] == owner.backdrop
    panel.showTech()
    assert owner['techPanelFrame'].visible and not owner['techPanelBg'].visible
    assert _rect(owner, 'techPanelFrame') == _rect(owner, 'techPanelBg')
    panel.hide()
    assert not owner['techPanelFrame'].visible and not owner['infoPanelFrame'].visible


@needsPil
def test_dark_setting_and_no_pil(panelModule, monkeypatch, tmp_path):
    monkeypatch.setattr(panelModule, 'LoadPixmap', lambda path, cached=True: 'pixmap')
    monkeypatch.setattr(panelModule.config.plugins.iptvplayer.infopanel_background, 'value', 'dark')
    owner = _BackdropOwner()
    owner.backdrop = str(tmp_path / "backdrop.jpg")
    panel = _techPanel(panelModule, owner)
    panel.show()
    # rounded, but without the picture
    assert owner['infoPanelFrame'].visible and panel.frameKeys['info'][4:] == ('', '')

    def noPil(*args):
        raise ImportError('PIL')
    monkeypatch.setattr(panelModule, 'makePanelPicture', noPil)
    panel = _techPanel(panelModule, _BackdropOwner())
    panel.show()
    assert panel.framesFailed and panel.owner['infoPanelBg'].visible and not panel.owner['infoPanelFrame'].visible


def _skinText(name):
    with open(os.path.join(ROOT, "playerskins", name, "playerskin.xml"), encoding="utf-8") as f:
        return f.read()


@needsPil
def test_modern_skin_has_the_widgets_of_every_skin_and_its_own(panelModule):
    default = _skinText("default")
    modern = _skinText("modern")
    names = set(re.findall(r'name="([^"]+)"', modern))
    assert set(re.findall(r'name="([^"]+)"', default)) <= names
    assert {'infoBarPoster'} | {'infoBarBadge%d' % idx for idx in range(1, 9)} <= names
    # the same placeholders as every skin (size, banner, bars, pointer, clock, subtitles)
    assert re.findall(r'%[sd]', modern) == re.findall(r'%[sd]', default)
    # the badges stand in one row, each right of the one before
    pattern = r'name="infoBarBadge%d"[^>]*?position="(\d+),(\d+)"[^>]*?size="(\d+),(\d+)"'
    badges = [[int(v) for v in re.search(pattern % idx, modern).groups()] for idx in range(1, 9)]
    assert len(set(badge[1] for badge in badges)) == 1
    for prev, nxt in zip(badges, badges[1:]):
        assert prev[0] + prev[2] < nxt[0]
    # every badge has its frame (1 px around it, the badge label inside) and its line under it
    for idx in range(1, 10):
        badge = re.search(pattern % idx, modern).groups()
        frame = re.search(r'name="infoBarBadge%dFrame"[^>]*?position="(\d+),(\d+)"[^>]*?size="(\d+),(\d+)"' % idx, modern).groups()
        assert int(badge[0]) - int(frame[0]) == 1 and int(frame[2]) == int(badge[2]) + 2, idx
        assert 'infoBarBadge%dSub' % idx in names
    # the inner badge labels have the panel colour as background, or the frame would show through them
    assert set(re.findall(r'name="infoBarBadge\d"[^>]*?backgroundColor="(#[0-9a-f]+)"', modern)) == {'#05111317'}
    # the bars have pictures as wide as the widgets (no pre-scaled copies for this skin)
    bar = re.search(r'name="progressBar"[^>]*?size="(\d+),(\d+)"', modern).groups()
    from PIL import Image
    for fileName in ("playback_progress.png", "playback_cbuff_progress.png", "playback_buff_progress.png"):
        with Image.open(os.path.join(ROOT, "playerskins", "modern", fileName)) as img:
            assert img.size == (int(bar[0]), int(bar[1])), fileName
    for idx in range(1, 6):
        assert {'infoBarStrip%dKey' % idx, 'infoBarStrip%dValue' % idx} <= names
    for fileName in ("playerclock.xml", "settings.json", "playback_banner.png", "infobar_poster_mask.png", "playback_knob.png"):
        assert os.path.isfile(os.path.join(ROOT, "playerskins", "modern", fileName)), fileName


@pytest.mark.parametrize("encode,expected", [
    # gstplayer2 on the box 22.11.: "MPEG-4 AAC audio" for an AAC-LC track
    ('MPEG-4 AAC audio', 'AAC'), ('MPEG-1 Layer 3 (MP3)', 'MP3'), ('E-AC-3 audio', 'E-AC3'), ('AC-3 (ATSC A/52)', 'AC3'),
    ('DTS audio', 'DTS'), ('Some new codec', 'Some new codec'), ('AC3', 'AC3'), ('IPCM', ''), ('audio/mpeg', ''), ('', ''),
])
def test_audio_codec_family(panelModule, encode, expected):
    assert panelModule.audioCodecFamily(encode) == expected


def test_gstplayer_tracks(panelModule):
    # what gstplayer2 reported on the box: plain caps / descriptions, no keys of exteplayer3
    audio = {'id': 0, 'encode': 'MPEG-4 AAC audio', 'name': 'und'}
    assert panelModule.audioCodecName(audio) == 'AAC'
    assert panelModule.subtitleFormatName('text/x-raw') == 'Text'
    subtitle = {'kind': 'embedded', 'lang': 'de', 'format': panelModule.subtitleFormatName('text/x-raw')}
    assert panelModule.stripTexts({}, audio, subtitle, _langName)[2:] == [('Audio', 'AAC'), ('Audio codec', 'AAC'), ('Subtitles', 'German (Text)')]


@needsPil
def test_modern_skin_pictures_for_every_osd_resolution(panelModule):
    # name_1920.png / name_2560.png: drawn natively for FHD / WQHD, as big as Enigma2 makes the widget of the
    # resolution="1280,720" skin (the player takes them instead of a PIL copy of the 1280 picture)
    from PIL import Image
    folder = os.path.join(ROOT, "playerskins", "modern")
    bases = [name for name in os.listdir(folder) if name.endswith('.png') and not re.search(r'_(1920|2560)\.png$', name) and name != 'sub_synchro.png']
    assert len(bases) >= 14
    for name in bases:
        with Image.open(os.path.join(folder, name)) as img:
            baseW, baseH = img.size
        for width, scale in ((1920, 1.5), (2560, 2.0)):
            variant = os.path.join(folder, name[:-4] + '_%d.png' % width)
            assert os.path.isfile(variant), variant
            with Image.open(variant) as img:
                assert img.size == (int(baseW * scale), int(baseH * scale)), variant


def test_older_player_gets_the_audio_of_ffprobe_in_badges_and_info_row(panelModule):
    # forum 22.11.: an older exteplayer3 names a software-decoded AAC only "IPCM" - badges and info row stayed empty
    # for the audio while "Playback info" showed ffprobe's AAC 2.0
    video, audio = panelModule.probedTracks(OLD_VIDEO, {'id': 1, 'encode': 'IPCM', 'name': 'eng'}, [{'id': 1}], json.loads(PROBE_MP4))
    assert audio['encode'] == 'IPCM' and audio['d'] == 'AAC' and audio['family'] == 'AAC'
    assert video['encode'] == 'MPEG4/ISO/AVC' and video['br'] == '850000'
    badges = panelModule.badgeList(video, audio, 25, None, video['br'])
    assert badges[-3:] == [('audio', '2.0', 'Channels'), ('audio', 'AAC', ''), ('video', '850', 'kbit/s')]
    assert panelModule.stripTexts(video, audio)[2:4] == [('Audio', 'AAC 2.0'), ('Audio codec', 'AAC')]
    # the "Playback info" page as before
    rows = _rows(panelModule.techSections(OLD_VIDEO, {'id': 1, 'encode': 'IPCM'}, [{'id': 1}], {}, json.loads(PROBE_MP4), 'MP4', 0, 25))
    assert rows['audio']['Codec'] == 'AAC (software)' and rows['audio']['Channels'] == '2.0 (2 ch)'
    # without ffprobe (a stream): the player's tracks as they are
    assert panelModule.probedTracks(OLD_VIDEO, {'encode': 'IPCM'}, [], {}) == (OLD_VIDEO, {'encode': 'IPCM'})
    assert panelModule.probedTracks({}, {}, [], None) == ({}, {})


@pytest.mark.parametrize("value,expected", [(2500000, ('2.5', 'Mbit/s')), (850000, ('850', 'kbit/s')), ('128000', ('128', 'kbit/s')),
                                            (0, None), (None, None), ('', None)])
def test_bitrate_badge(panelModule, value, expected):
    assert panelModule.bitrateBadge(value) == expected


def test_bitrate_badge_is_the_last_and_only_with_video(panelModule):
    assert panelModule.badgeList(OLD_VIDEO, {'encode': 'AC3'}, 25, None, 2500000)[-1] == ('video', '2.5', 'Mbit/s')
    # radio: the link's bitrate is no video bitrate
    assert panelModule.badgeList({}, {'encode': 'AAC', 'c': 2}, 0, None, 128000) == [('audio', '2.0', 'Channels'), ('audio', 'AAC', '')]


@pytest.mark.parametrize("text,expected", [('7.2', '7.2'), ('7.2/10', '7.2'), ('7,4', '7.4'), ('IMDb: 8.1 (1234 votes)', '8.1'),
                                           ('N/A', ''), ('0', ''), ('', ''), (None, ''), ('85', '')])
def test_rating_value(panelModule, text, expected):
    assert panelModule.ratingValue(text) == expected


def test_article_rating_and_short_meta_line(panelModule):
    # forum 22.11.: the IMDb rating beside the title, the meta line was cut off at "Country:"
    params = {'type': 'Movie', 'country': 'United States', 'year': '2026', 'genre': 'Adventure, Animation', 'imdb_rating': '6.8/10'}
    assert panelModule.articleRating(params) == 'IMDb 6.8'
    assert panelModule.shortMetaLine(params) == '2026  ·  Adventure, Animation  ·  United States'
    assert panelModule.articleRating({'tmdb_rating': '7.0'}) == 'TMDb 7.0'
    assert panelModule.articleRating({'imdb_rating': 'N/A', 'tmdb_rating': '6.1'}) == 'TMDb 6.1'
    assert panelModule.articleRating({'year': '2020'}) == '' and panelModule.articleRating(None) == ''
    assert panelModule.shortMetaLine({'year': '2020', 'country': 'N/A'}) == '2020'
    # a host with its own rows: they stay, the rating is found by its label
    custom = {'custom_items_list': [('Year:', '2019'), ('IMDb Rating:', '7.9')]}
    assert panelModule.articleRating(custom) == 'IMDb 7.9'
    assert panelModule.shortMetaLine(custom) == panelModule.metaLine(custom)


def test_modern_skin_rating_strip_icons_and_12h_clock(panelModule):
    modern = _skinText("modern")
    names = set(re.findall(r'name="([^"]+)"', modern))
    assert 'infoBarRating' in names
    folder = os.path.join(ROOT, "playerskins", "modern")
    for idx in range(1, 6):
        assert 'infoBarStrip%dIcon' % idx in names
        assert os.path.isfile(os.path.join(folder, 'infobar_strip%d.png' % idx))
        # the symbol lies left of its label
        icon = re.search(r'name="infoBarStrip%dIcon"[^>]*?position="(\d+),(\d+)"[^>]*?size="(\d+),(\d+)"' % idx, modern).groups()
        key = re.search(r'name="infoBarStrip%dKey"[^>]*?position="(\d+),(\d+)"' % idx, modern).groups()
        assert int(icon[0]) + int(icon[2]) < int(key[0])
    with open(os.path.join(folder, "settings.json")) as f:
        assert json.load(f)["clockFormat_12H"] == "%I:%M %p"


@pytest.mark.parametrize("message,expected", [
    # exteplayer3 v187 "m_t": ICY StreamTitle (rt = whole title) or the title / artist tags of the stream
    ({'rt': 'Queen - Bohemian Rhapsody', 't': 'Bohemian Rhapsody', 'a': 'Queen'}, 'Queen - Bohemian Rhapsody'),
    ({'rt': '', 't': 'News', 'a': ''}, 'News'),
    ({'rt': '', 't': 'Song', 'a': 'Band'}, 'Band - Song'),
    ({'rt': '  ', 't': '', 'a': ''}, ''),
    ({}, ''), (None, ''), ('text', ''),
])
def test_now_playing_text(panelModule, message, expected):
    assert panelModule.nowPlayingText(message) == expected


def test_playback_info_now_playing_and_pixel_format(panelModule):
    # radio with a song: first row of the audio column
    rows = _rows(panelModule.techSections({}, {'id': 0, 'encode': 'MP3', 'name': 'und'}, [], {}, None, 'HTTP', 0, 0,
                                          None, 'Queen - Bohemian Rhapsody'))
    # cut to the column like every value (the whole title is above the poster and in the meta line)
    assert list(rows['audio'].items())[0] == ('Current song', 'Queen - Bohemian Rhaps…')
    # no song, no row
    assert 'Current song' not in _rows(panelModule.techSections({}, {'id': 0, 'encode': 'MP3'}, [], {}, None, '', 0, 0))['audio']
    # ffprobe's pixel format of a local file, after the bit depth
    sections = panelModule.techSections(OLD_VIDEO, {'id': 1, 'encode': 'EAC3'}, [], {}, json.loads(PROBE_MKV), 'MKV', 0, 25)
    labels = [label for label, value in sections[0][1]]
    assert dict(sections[0][1])['Pixel format'] == 'yuv420p10le'
    assert labels.index('Pixel format') == labels.index('Bit depth') + 1
