# -*- coding: utf-8 -*-
# Added: 01.11.2026 - INFO key in the movie player (components/iptvextmovieplayer.py): a panel over the running
# video with the title, where the video comes from (host, link, server), the video / audio formats and the texts
# of the host's INFO page. The page is asked for in the background on the first INFO, until then the panel shows
# the description of the list row. Without the list (download manager, web interface) only the player's own data.
# A local file (download, buffer file) is read with ffprobe for the container, profile, bit depth, channels and
# bitrates; a stream is not: a second connection could disturb the playback (one connection per token on some CDNs),
# it only shows the bitrate of its link list. Without ffprobe that row just stays short.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.cover import Cover
from Plugins.Extensions.IPTVPlayer.components.ihost import ArticleContent
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import shellQuote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback, StripColorCodes, ShortHostTitle, iptv_system

###################################################
# FOREIGN import
###################################################
from Components.Label import Label
from enigma import ePoint, eSize, eTimer
from os import path as os_path
from urllib.parse import urlsplit
import json
import re
###################################################

SEPARATOR = '  ·  '
LOOPBACK_NAMES = ('localhost', '127.0.0.1', '::1')
PROBE_CMD = '/usr/bin/ffprobe -v quiet -print_format json -show_format -show_streams "%s"'
PROBE_TIMEOUT = 20000  # ms
# first name of ffprobe's format_name ("matroska,webm", "mov,mp4,m4a,3gp,3g2,mj2")
CONTAINER_NAMES = {'matroska': 'MKV', 'mov': 'MP4', 'mpegts': 'TS', 'mpeg': 'MPG', 'avi': 'AVI', 'flv': 'FLV', 'asf': 'WMV', 'ogg': 'OGG', 'wav': 'WAV', 'hls': 'HLS'}
CODEC_NAMES = {'h264': 'H.264', 'hevc': 'H.265', 'mpeg2video': 'MPEG-2', 'mpeg4': 'MPEG-4', 'vc1': 'VC-1', 'eac3': 'E-AC3', 'truehd': 'TrueHD', 'opus': 'Opus', 'vorbis': 'Vorbis'}
HDR_TRANSFERS = {'smpte2084': 'HDR10', 'arib-std-b67': 'HLG'}
CHANNEL_LAYOUTS = {'mono': '1.0', 'stereo': '2.0'}


def serverName(url):
    # the server the player or downloader talks to. A local relay or file names no server.
    try:
        if getattr(url, 'meta', {}).get('iptv_proto', '') == 'merge' or url.lower().startswith('merge://'):
            url = url.meta.get('video_url', '')
        name = urlsplit(str(url).split('|', 1)[0]).hostname or ''
    except Exception:
        printExc(WarnOnly=True)
        return ''
    if name in LOOPBACK_NAMES:
        return ''
    return name[4:] if name.startswith('www.') else name


def hostDisplayName(title, site=''):
    # the short title of the host list, behind it the site of a host with many sites (hostxxx)
    title = ShortHostTitle(title)
    return '%s / %s' % (title, site) if title and site else title or site


def linkDisplayName(mirror, name):
    # the name of a played link: a mirror, behind it the quality chosen from its list. A resolver without
    # names hands out the url as the name.
    mirror = StripColorCodes(mirror).strip()
    name = StripColorCodes(name).strip()
    if '://' in name:
        name = ''
    # the technical name of getDirectM3U8Playlist ("bitrate: 1207970 res: 1280x640 mp4a,avc1 24fps"): the panel
    # shows all of it in its own rows
    technical = re.match(r'(\[[^\]]*\]\s*)?bitrate: \d+(?: res: (\d+x\d+))?', name)
    if technical:
        name = ('%s%s' % (technical.group(1) or '', technical.group(2) or '')).strip()
    if not mirror or name.startswith(mirror):
        return name
    if not name or mirror.startswith(name):
        return mirror
    return '%s / %s' % (mirror, name)


def sourceLine(hostName, linkName, server):
    parts = []
    for label, value in ((_('Host'), hostName), (_('Link'), linkName), (_('Server'), server)):
        if value:
            parts.append('%s: %s' % (label.strip(), value))
    return SEPARATOR.join(parts)


def audioText(track):
    # {'encode': 'AAC', 'name': 'eng'}, players name a track of unknown language 'und'
    encode = str((track or {}).get('encode', '')).split('/')[-1]
    language = str((track or {}).get('name', ''))
    if language and language != 'und':
        return '%s (%s)' % (encode, language) if encode else language
    return encode


def streamLine(videoInfo, audioTrack, hasVideoTrack=True):
    # without a video track (radio, before the player reports it) the infobar's text is only the stream type
    parts = []
    video = (videoInfo or '').strip()
    if video:
        parts.append('%s: %s' % (_('Video').strip(), video) if hasVideoTrack else video)
    audio = audioText(audioTrack)
    if audio:
        parts.append('%s: %s' % (_('Audio').strip(), audio))
    return SEPARATOR.join(parts)


def bitrateText(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return ''
    # from 999.5 kbit/s on: it would round to "1000 kbit/s"
    if value >= 999500:
        return '%.1f Mbit/s' % (value / 1000000.0)
    return '%d kbit/s' % round(value / 1000.0) if value >= 1000 else ''


def streamBitrate(url):
    # the BANDWIDTH of the chosen HLS variant in the link list, in bit/s (for f4m the same key names the variant)
    meta = getattr(url, 'meta', {})
    if meta.get('iptv_proto', '') == 'f4m':
        return 0
    try:
        return int(meta.get('iptv_bitrate', 0))
    except (TypeError, ValueError):
        return 0


def videoDetail(stream):
    codec = str(stream.get('codec_name', ''))
    name = CODEC_NAMES.get(codec, codec.upper())
    profile = stream.get('profile', '')
    if profile and profile != 'unknown':
        name += ' %s' % profile
        # ffprobe's level: 41 for H.264 level 4.1, 150 for H.265 level 5.0
        divisor = {'h264': 10.0, 'hevc': 30.0}.get(codec)
        if divisor and int(stream.get('level', 0) or 0) > 0:
            name += '@%.1f' % (int(stream['level']) / divisor)
    parts = [name]
    depth = re.search(r'p(9|1[0246])(?:le|be)$', str(stream.get('pix_fmt', '')))
    if depth:
        parts.append('%s Bit' % depth.group(1))
    if stream.get('color_transfer') in HDR_TRANSFERS:
        parts.append(HDR_TRANSFERS[stream['color_transfer']])
    parts.append(bitrateText(stream.get('bit_rate')))
    return ', '.join(part for part in parts if part)


def audioDetail(stream):
    codec = str(stream.get('codec_name', ''))
    # "DTS-HD MA": only there the profile is what counts, an AAC is plain "LC"
    name = str(stream.get('profile', '')) if codec == 'dts' and stream.get('profile') else CODEC_NAMES.get(codec, codec.upper())
    layout = re.sub(r'\(.*\)$', '', str(stream.get('channel_layout', '')))
    parts = [name]
    if layout:
        parts.append(CHANNEL_LAYOUTS.get(layout, layout))
    elif int(stream.get('channels', 0) or 0) > 0:
        parts.append('%d ch' % int(stream['channels']))
    try:
        if int(stream.get('sample_rate', 0)) > 0:
            parts.append('%g kHz' % (int(stream['sample_rate']) / 1000.0))
    except (TypeError, ValueError):
        pass
    parts.append(bitrateText(stream.get('bit_rate')))
    text = ', '.join(part for part in parts if part)
    language = str(stream.get('tags', {}).get('language', ''))
    return '%s (%s)' % (text, language) if language and language != 'und' else text


def parseProbe(data):
    # the JSON of PROBE_CMD; a file ffprobe can't read gives nothing
    try:
        probe = json.loads(data)
        return probe if isinstance(probe, dict) else {}
    except (TypeError, ValueError):
        return {}


def tracksBitrate(streams):
    # the sum only when every track names its bitrate, a part of them would be too low
    try:
        return sum(int(stream['bit_rate']) for stream in streams)
    except (KeyError, TypeError, ValueError):
        return 0


def detailLine(probe, linkBitrate=0):
    parts = []
    streams = probe.get('streams', [])
    fileFormat = probe.get('format', {})
    formatName = str(fileFormat.get('format_name', '')).split(',')[0]
    if formatName:
        parts.append(CONTAINER_NAMES.get(formatName, formatName.upper()))
    videoStreams = [stream for stream in streams if stream.get('codec_type') == 'video' and not stream.get('disposition', {}).get('attached_pic')]
    audioStreams = [stream for stream in streams if stream.get('codec_type') == 'audio']
    # the link's value first, then the tracks': format.bit_rate of a buffer file still being written is its size so
    # far through the full length of an MP4 (234 kbit/s for a video of 5.5 Mbit/s)
    bitrate = bitrateText(linkBitrate) or bitrateText(tracksBitrate(videoStreams + audioStreams)) or bitrateText(fileFormat.get('bit_rate'))
    if bitrate:
        parts.append(_('Bitrate: %s') % bitrate)
    if videoStreams:
        parts.append('%s: %s' % (_('Video').strip(), videoDetail(videoStreams[0])))
    if audioStreams:
        parts.append('%s: %s' % (_('Audio').strip(), ' / '.join(audioDetail(stream) for stream in audioStreams)))
    return SEPARATOR.join(parts)


def plainText(text):
    # one running text: the INFO page breaks its lines with [/br] and |
    text = StripColorCodes(str(text or '')).replace('[/br]', ' ').replace('|', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def metaLine(params):
    # the rows of the INFO page (iptvarticleview.py setText) in one text
    if not isinstance(params, dict):
        return ''
    if 'custom_items_list' in params:
        rows = [item for item in params['custom_items_list'] if isinstance(item, tuple) and len(item) == 2]
    else:
        rows = [(_(ArticleContent.RICH_DESC_LABELS.get(key, key)), params[key]) for key in ArticleContent.RICH_DESC_PARAMS if key in params]
    parts = []
    for label, value in rows:
        text = plainText(value)
        if text:
            parts.append('%s: %s' % (plainText(label).rstrip(':'), text))
    return SEPARATOR.join(parts)


def fitLabelText(label, text, maxHeight):
    # text for a wrapping eLabel: only whole lines fit, a cut text ends with "…" at a word boundary. Measured a
    # little narrower than the label: the drawing wraps a few pixels earlier than calculateSize(), the "…" would
    # land in a hidden line.
    def cut(length):
        part = text[:length]
        if length < len(text) and ' ' in part:
            part = part.rsplit(' ', 1)[0]
        return part.rstrip() + '…'

    size = label.size()
    label.resize(eSize(size.width() * 97 // 100, size.height()))
    try:
        label.setText(text)
        if label.calculateSize().height() <= maxHeight:
            return text
        shortest, longest = 0, len(text)
        while shortest < longest:
            middle = (shortest + longest + 1) // 2
            label.setText(cut(middle))
            if label.calculateSize().height() <= maxHeight:
                shortest = middle
            else:
                longest = middle - 1
        return cut(shortest)
    finally:
        label.resize(size)


class PlayerInfoPanel(object):
    LABELS = ('infoPanelTitle', 'infoPanelSource', 'infoPanelStream', 'infoPanelDetail', 'infoPanelMeta', 'infoPanelText')
    WIDGETS = ('infoPanelBg', 'infoPanelCover') + LABELS

    # (name, y, height, font size, colour) on the 1280x720 canvas of the player skins. The player's infobar lies at
    # the bottom, from y=543 in the skins with the highest bar
    PANEL_X, PANEL_Y, PANEL_W = 30, 20, 1220
    PADDING = 15
    COVER_W, COVER_H = 135, 200
    ROWS = (('infoPanelTitle', 30, 36, 28, '#ffffff'),
            ('infoPanelSource', 68, 56, 21, '#66ccff'),
            ('infoPanelStream', 124, 28, 21, '#66ccff'),
            ('infoPanelDetail', 156, 56, 21, '#66ccff'),
            ('infoPanelMeta', 216, 56, 21, '#cccccc'),
            ('infoPanelText', 276, 140, 21, '#ffffff'))

    @classmethod
    def skinWidgets(cls, scale=1.0):
        # scale: 1 on a skin with resolution="1280,720" (Enigma2 scales it), else the real pixels of the "sd" skin
        def px(value):
            return int(value * scale)

        textX = cls.PANEL_X + cls.COVER_W + 2 * cls.PADDING
        textW = cls.PANEL_W - cls.COVER_W - 3 * cls.PADDING
        skin = '<widget name="infoPanelBg" position="%d,%d" size="%d,%d" zPosition="10" backgroundColor="#20101010" />' % (px(cls.PANEL_X), px(cls.PANEL_Y), px(cls.PANEL_W), px(411))
        skin += '<widget name="infoPanelCover" position="%d,%d" size="%d,%d" zPosition="11" transparent="1" alphatest="blend" />' % (px(cls.PANEL_X + cls.PADDING), px(cls.PANEL_Y + cls.PADDING), px(cls.COVER_W), px(cls.COVER_H))
        for name, y, height, font, colour in cls.ROWS:
            noWrap = ' noWrap="1"' if name in ('infoPanelTitle', 'infoPanelStream') else ''
            skin += '<widget name="%s"%s position="%d,%d" size="%d,%d" zPosition="11" transparent="1" foregroundColor="%s" backgroundColor="#20101010" font="Regular;%d" halign="left" valign="top" />' % (name, noWrap, px(textX), px(y), px(textW), px(height), colour, max(px(font), 16))
        return skin

    def __init__(self, owner, additionalParams):
        self.owner = owner
        self.hostTitle = additionalParams.get('host_title', '') or owner.hostName
        self.linkName = additionalParams.get('link_name', '')
        self.coverPath = additionalParams.get('cover_path', '')
        self.provider = additionalParams.get('info_provider', None)
        self.text = plainText(additionalParams.get('info_description', ''))
        self.meta = ''
        self.visible = False
        self.closed = False
        self.geometry = None
        self.articleRet = None
        self.articleThread = None
        # None: not asked yet, True: the answer is on its way, False: done
        self.articlePending = None
        self.timer = eTimer()
        self.timer_conn = eConnectCallback(self.timer.timeout, self._checkArticle)
        self.probe = {}
        self.probeHandle = None
        self.probeTimer = eTimer()
        self.probeTimer_conn = eConnectCallback(self.probeTimer.timeout, self._stopProbe)
        owner['infoPanelBg'] = Label(' ')
        owner['infoPanelCover'] = Cover()
        for name in self.LABELS:
            owner[name] = Label(' ')
        self._setWidgetsVisible(False)

    def _setWidgetsVisible(self, visible):
        for name in self.WIDGETS:
            if visible:
                self.owner[name].show()
            else:
                self.owner[name].hide()

    def show(self):
        self._requestArticle()
        self._startProbe()
        self._fill()
        self._setWidgetsVisible(True)
        if not self._hasCover():
            self.owner['infoPanelCover'].hide()
        self.visible = True
        self._showCover()

    def hide(self):
        self.visible = False
        self._setWidgetsVisible(False)

    def close(self):
        self.hide()
        self.closed = True
        self.provider = None
        self.timer.stop()
        self.timer_conn = None
        self._stopProbe()
        self.probeTimer_conn = None

    def _startProbe(self):
        # once it read the file; a buffer file with too little in it yet gets another try on the next INFO
        if self.closed or self.probe or self.probeHandle is not None:
            return
        path = self.owner.getLocalFilePath()
        if path:
            try:
                self.probeHandle = iptv_system(PROBE_CMD % shellQuote(path), self._probeDone)
                self.probeTimer.start(PROBE_TIMEOUT, True)
            except Exception:
                printExc()
                self.probeHandle = None

    def _probeDone(self, code, data):
        self.probeTimer.stop()
        self.probeHandle = None
        probe = parseProbe(data)
        try:
            printDBG("PlayerInfoPanel ffprobe code[%r] detail[%s]" % (code, detailLine(probe)))
            self.probe = probe
        except Exception:
            # an answer that detailLine() can't read must not reach _layout()
            printExc()
        if self.visible:
            self._fill()

    def _stopProbe(self):
        self.probeTimer.stop()
        if self.probeHandle is not None:
            self.probeHandle.kill()
            self.probeHandle = None

    def updateStream(self):
        # the player reports the tracks a moment after it starts, an audio change later
        if self.visible:
            self.owner['infoPanelStream'].setText(self._streamText())

    def _sourceText(self):
        return sourceLine(self.hostTitle, self.linkName, serverName(self.owner.getStreamSourceUrl()))

    def _streamText(self):
        playback = self.owner.playback
        return streamLine(self.owner['videoInfo'].getText(), playback.get('AudioTrack'), bool(playback.get('VideoTrack')))

    def _hasCover(self):
        try:
            return bool(self.coverPath) and os_path.getsize(self.coverPath) > 0
        except OSError:
            return False

    def _showCover(self):
        if self._hasCover():
            try:
                self.owner['infoPanelCover'].decodeCover(self.coverPath, self._coverDecoded, 'infoPanelCover')
            except Exception:
                printExc()

    def _coverDecoded(self, ret):
        if not self.closed:
            self.owner['infoPanelCover'].updatePixmap(ret.get('Pixmap', None), ret.get('FileName', self.coverPath))

    def _requestArticle(self):
        if self.provider is None or self.articlePending is not None:
            return
        self.articlePending = True
        try:
            self.articleThread = self.provider(self._articleDone)
            self.timer.start(200)
        except Exception:
            printExc()
            self.articlePending = False

    def _articleDone(self, ret):
        # in the worker thread: the timer takes it over into the main thread
        self.articleRet = ret

    def _checkArticle(self):
        if self.articleRet is None and self.articleThread is not None and self.articleThread.isAlive():
            return
        self.timer.stop()
        self.articlePending = False
        self.articleThread = None
        try:
            value = getattr(self.articleRet, 'value', None)
            if value:
                # a page without a text of its own keeps the description of the list row
                self.text = plainText(value[0].text) or self.text
                self.meta = metaLine(value[0].richDescParams)
        except Exception:
            printExc()
        printDBG("PlayerInfoPanel article loaded meta[%s]" % self.meta)
        if self.visible:
            self._fill()

    def _fill(self):
        owner = self.owner
        owner['infoPanelTitle'].setText(StripColorCodes(owner.title))
        owner['infoPanelStream'].setText(self._streamText())
        try:
            self._layout()
        except Exception:
            printExc()

    def _layout(self):
        # the panel is as high as its content: the rows under the formats move up when there is no meta line or a
        # short text. Everything here in real pixels, instance.move() is not scaled by the skin engine.
        owner = self.owner
        if self.geometry is None:
            self.geometry = {}
            for name in self.WIDGETS:
                instance = owner[name].instance
                self.geometry[name] = (instance.position().x(), instance.position().y(), instance.size().width(), instance.size().height())
        bgY, bgW = self.geometry['infoPanelBg'][1], self.geometry['infoPanelBg'][2]
        coverX, coverY, coverH = self.geometry['infoPanelCover'][0], self.geometry['infoPanelCover'][1], self.geometry['infoPanelCover'][3]

        hasCover = self._hasCover()
        for name in self.LABELS:
            x, y, w, h = self.geometry[name]
            if not hasCover:
                # the text takes the place of the missing picture
                w += x - coverX
                x = coverX
            owner[name].instance.move(ePoint(x, y))
            owner[name].instance.resize(eSize(w, h))

        streamGeometry = self.geometry['infoPanelStream']
        bottom = self.geometry['infoPanelSource'][1]
        gap = self.geometry['infoPanelDetail'][1] - streamGeometry[1] - streamGeometry[3]
        # the source wraps, a long link name must not cut off the server; a file of the download manager has none
        source = self._sourceText()
        if source:
            instance = owner['infoPanelSource'].instance
            maxHeight = self.geometry['infoPanelSource'][3]
            owner['infoPanelSource'].setText(fitLabelText(instance, source, maxHeight))
            height = min(instance.calculateSize().height(), maxHeight)
            instance.resize(eSize(instance.size().width(), height))
            bottom += height
        else:
            owner['infoPanelSource'].setText('')
        instance = owner['infoPanelStream'].instance
        instance.move(ePoint(instance.position().x(), bottom))
        # on the "sd" skin the smallest font is higher than the scaled row
        height = max(instance.calculateSize().height(), streamGeometry[3])
        instance.resize(eSize(instance.size().width(), height))
        bottom += height

        meta = self.meta or (_('Loading...') if self.articlePending else '')
        detail = detailLine(self.probe, streamBitrate(owner.getStreamSourceUrl()))
        for name, text in (('infoPanelDetail', detail), ('infoPanelMeta', meta), ('infoPanelText', self.text)):
            label = owner[name]
            if not text:
                label.setText('')
                continue
            instance = label.instance
            maxHeight = self.geometry[name][3]
            label.setText(fitLabelText(instance, text, maxHeight))
            height = min(instance.calculateSize().height(), maxHeight)
            instance.move(ePoint(instance.position().x(), bottom + gap))
            instance.resize(eSize(instance.size().width(), height))
            bottom += gap + height

        if hasCover:
            bottom = max(bottom, coverY + coverH)
        owner['infoPanelBg'].instance.resize(eSize(bgW, bottom + (coverY - bgY) - bgY))
