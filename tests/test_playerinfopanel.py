# Offline test of the INFO panel of the movie player (components/iptvplayerinfopanel.py): Enigma2 is stubbed, the
# texts, the layout in real pixels and the background request are the real ones.
import importlib.util
import json
import os
import re
import sys
import types
import xml.etree.ElementTree as ET

import pytest

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
    stub("enigma", ePoint=_Point, eSize=_Size, eTimer=_Timer)

    spec = importlib.util.spec_from_file_location("iptvplayerinfopanel_test", os.path.join(ROOT, "components", "iptvplayerinfopanel.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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
    assert panelModule.streamLine(" H264 1920x1080p ", {'encode': 'MPEG/L3', 'name': 'und'}) == "Video: H264 1920x1080p  ·  Audio: L3"
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
