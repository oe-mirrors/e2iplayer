# -*- coding: utf-8 -*-
# Added: 01.11.2026 - INFO key in the movie player (components/iptvextmovieplayer.py): a panel over the running
# video with the title, where the video comes from (host, link, server), the video / audio formats and the texts
# of the host's INFO page. The page is asked for in the background on the first INFO, until then the panel shows
# the description of the list row. Without the list (download manager, web interface) only the player's own data.
# A local file (download, buffer file) is read with ffprobe for the container, profile, bit depth, channels and
# bitrates; a stream is not: a second connection could disturb the playback (one connection per token on some CDNs),
# it only shows the bitrate of its link list. Without ffprobe that row just stays short.
# INFO a second time: "Playback info", the formats of the playing video / audio / subtitle track in a table - what a
# newer exteplayer3 reports of its tracks, else ffprobe's values for a local file. The same helpers make the format
# badges of a player skin's infobar (playerskins/modern).
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
from Components.config import config
from Components.Label import Label
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap
from enigma import ePoint, eSize, eTimer
import os
from urllib.parse import urlsplit
import json
import re
###################################################

SEPARATOR = '  ·  '
LOOPBACK_NAMES = ('localhost', '127.0.0.1', '::1')
FFPROBE = '/usr/bin/ffprobe'
PROBE_CMD = FFPROBE + ' -v quiet -print_format json -show_format -show_streams "%s"'
# the chapters of a local file (the player, without a chapter list in the description)
CHAPTERS_PROBE_CMD = FFPROBE + ' -v quiet -print_format json -show_chapters "%s"'
PROBE_TIMEOUT = 20000  # ms
# first name of ffprobe's format_name ("matroska,webm", "mov,mp4,m4a,3gp,3g2,mj2")
CONTAINER_NAMES = {'matroska': 'MKV', 'mov': 'MP4', 'mpegts': 'TS', 'mpeg': 'MPG', 'avi': 'AVI', 'flv': 'FLV', 'asf': 'WMV', 'ogg': 'OGG', 'wav': 'WAV', 'hls': 'HLS'}
CODEC_NAMES = {'h264': 'H.264', 'hevc': 'H.265', 'mpeg2video': 'MPEG-2', 'mpeg4': 'MPEG-4', 'vc1': 'VC-1', 'eac3': 'E-AC3', 'truehd': 'TrueHD', 'opus': 'Opus', 'vorbis': 'Vorbis'}
HDR_TRANSFERS = {'smpte2084': 'HDR10', 'arib-std-b67': 'HLG'}


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
    encode = audioCodecName(track)
    language = str((track or {}).get('name', ''))
    if language and language != 'und':
        return '%s (%s)' % (encode, language) if encode else language
    return encode


###################################################
# the tracks the player reports. exteplayer3: "e" codec id (the "A_"/"V_"/"S_" cut off by the player), "n" language,
# since v186 "c" channels, "d" codec name for display, "t" title; its track info for front ends adds "sr" sample
# rate, "br" bit rate, "cl" channel layout, "bps" bits per sample to the audio tracks and "hdr", "pr" profile@level,
# "bd" bit depth, "br", "dv" Dolby Vision profile, "cr" colour primaries to the video track. 0 or "" is unknown, an
# older player sends none of them. gstplayer names the codec by its caps ("video/x-h264", "audio/mpeg").
###################################################
# (parts of the upper-case codec id, short name, name of the INFO page) - AVC before MPEG4: "MPEG4/ISO/AVC"
VIDEO_CODECS = ((('HEVC', 'H265'), 'HEVC', 'H.265 (HEVC)'),
                (('AVC', 'H264'), 'H.264', 'H.264 (AVC)'),
                (('VP9',), 'VP9', 'VP9'),
                (('VP8',), 'VP8', 'VP8'),
                (('AV1',), 'AV1', 'AV1'),
                (('AVS2',), 'AVS2', 'AVS2'),
                (('MPEG2', 'MPEG-2'), 'MPEG-2', 'MPEG-2'),
                (('MPEG1',), 'MPEG-1', 'MPEG-1'),
                (('MPEG4', 'DIVX', 'XVID'), 'MPEG-4', 'MPEG-4 Part 2'),
                (('VC1',), 'VC-1', 'VC-1'),
                (('WMV',), 'WMV', 'WMV'),
                (('MJPEG',), 'MJPEG', 'Motion JPEG'))
# exteplayer3: MP2 is "A_MPEG/L3". "IPCM" is the PCM the player decoded itself (software decoding): not the codec of
# the stream, an older player names no other one then
AUDIO_CODECS = {'MPEG/L3': 'MP2', 'MP3': 'MP3', 'AAC': 'AAC', 'AAC_LATM': 'AAC LATM', 'AC3': 'AC3', 'EAC3': 'E-AC3',
                'DTS': 'DTS', 'WMA': 'WMA', 'WMA/PRO': 'WMA Pro', 'PCM': 'PCM', 'LPCM': 'LPCM', 'AMR': 'AMR',
                'VORBIS': 'Vorbis', 'OPUS': 'Opus', 'IPCM': '',
                'AUDIO/MPEG': '', 'AUDIO/X-AC3': 'AC3', 'AUDIO/X-EAC3': 'E-AC3', 'AUDIO/X-DTS': 'DTS', 'AUDIO/X-FLAC': 'FLAC',
                'AUDIO/X-OPUS': 'Opus', 'AUDIO/X-VORBIS': 'Vorbis', 'AUDIO/X-WMA': 'WMA', 'AUDIO/X-RAW': 'PCM'}
# FFmpeg's channel layouts ("5.1(side)" without the brackets)
CHANNEL_NAMES = {'mono': '1.0', 'stereo': '2.0', 'downmix': '2.0', 'quad': '4.0', 'hexagonal': '6.0', 'octagonal': '8.0'}
# FFmpeg's default layout of a channel count (a track that reports only the count)
CHANNEL_COUNTS = {1: '1.0', 2: '2.0', 3: '2.1', 4: '4.0', 5: '5.0', 6: '5.1', 7: '6.1', 8: '7.1'}
COLOUR_NAMES = {'bt709': 'BT.709', 'bt2020': 'BT.2020', 'bt470bg': 'BT.601', 'smpte170m': 'BT.601', 'bt470m': 'BT.470 M',
                'smpte240m': 'SMPTE 240M', 'smpte431': 'DCI-P3', 'smpte432': 'Display P3'}
HDR_NAMES = {1: 'HDR10', 2: 'HLG'}
# subtitle codec ids ("S_" cut off) and the extensions of subtitle files
SUBTITLE_FORMATS = {'TEXT/ASS': 'ASS', 'TEXT/SSA': 'SSA', 'TEXT/SRT': 'SRT', 'TEXT/SUBRIP': 'SRT', 'TEXT/UTF-8': 'Text',
                    'TEXT/WEBVTT': 'WebVTT', 'TEXT/MOV': 'MOV Text', 'TEXT/EIA608': 'CEA-608', 'GRAPHIC/PGS': 'PGS',
                    'GRAPHIC/DVB': 'DVB', 'GRAPHIC/XSUB': 'XSUB', 'VTT': 'WebVTT', 'SUB': 'MicroDVD', 'MPL': 'MPL2',
                    # gstplayer: the caps of the track
                    'TEXT/X-RAW': 'Text', 'TEXT/X-PANGO-MARKUP': 'Text', 'APPLICATION/X-SSA': 'SSA', 'APPLICATION/X-ASS': 'ASS',
                    'SUBPICTURE/X-PGS': 'PGS', 'SUBPICTURE/X-DVB': 'DVB', 'SUBPICTURE/X-DVD': 'VobSub', 'APPLICATION/X-SUBTITLE-VTT': 'WebVTT'}
# gstplayer2 names an audio track by GStreamer's description ("MPEG-4 AAC audio", "MPEG-1 Layer 3 (MP3)"): the short
# name from it, the first match wins
GST_AUDIO_NAMES = ((r'E-?AC-?3', 'E-AC3'), (r'\bAC-?3\b', 'AC3'), (r'TrueHD', 'TrueHD'), (r'\bDTS\b', 'DTS'), (r'\bAAC\b', 'AAC'),
                   (r'Layer 3|\bMP3\b', 'MP3'), (r'Layer 2|\bMP2\b', 'MP2'), (r'FLAC', 'FLAC'), (r'Opus', 'Opus'),
                   (r'Vorbis', 'Vorbis'), (r'Windows Media|\bWMA\b', 'WMA'), (r'\bPCM\b|\braw\b', 'PCM'))
VALUE_MAX = 23  # characters of a value on the "Playback info" page: its row has no room for more (noWrap cuts the rest)


def intValue(track, key):
    try:
        return int((track or {}).get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def textValue(track, key):
    return str((track or {}).get(key, '') or '').strip()


def videoCodecNames(encode):
    # (short name, name of the INFO page); an unknown codec by its own id
    name = str(encode or '').upper()
    for parts, short, full in VIDEO_CODECS:
        if any(part in name for part in parts):
            return short, full
    name = str(encode or '').split('/')[-1].replace('x-', '').upper()
    return name, name


def audioCodecName(track):
    # exteplayer3's display name ("DTS-HD MA", "Dolby Atmos"), else the codec id; "" when only the decoded PCM is known
    name = textValue(track, 'd')
    if name:
        return name
    return audioCodecFamily(textValue(track, 'encode'))


def audioCodecFamily(encode):
    # the codec id of the player as a short name: "AC3", "MP2" for exteplayer3's "MPEG/L3", "AAC" for gstplayer's
    # "MPEG-4 AAC audio"; "" for the decoded PCM of exteplayer3 and an unclear "audio/mpeg"
    encode = str(encode or '').strip()
    if encode.upper() in AUDIO_CODECS:
        return AUDIO_CODECS[encode.upper()]
    if ' ' in encode:
        for pattern, name in GST_AUDIO_NAMES:
            if re.search(pattern, encode, re.IGNORECASE):
                return name
        return encode
    return encode.split('/')[-1]


def channelsText(track):
    # "5.1" from the layout, else from the number of channels
    layout = re.sub(r'\(.*\)$', '', textValue(track, 'cl')).strip()
    if layout:
        return CHANNEL_NAMES.get(layout, layout)
    count = intValue(track, 'c')
    if count > 0:
        return CHANNEL_COUNTS.get(count, '%d ch' % count)
    return ''


def resolutionClass(width, height):
    # a cinemascope 1920x800 is still Full HD: the width counts as much as the height
    if width <= 0 or height <= 0:
        return ''
    for minW, minH, name in ((7000, 4000, '8K'), (3500, 2000, '4K'), (2500, 1400, 'QHD'), (1800, 1000, 'FHD'), (1200, 700, 'HD')):
        if width >= minW or height >= minH:
            return name
    return 'SD'


def frameRateText(fps):
    # 25 -> "25", 23.976 -> "23.976", 29.97 -> "29.97"
    try:
        fps = float(fps)
    except (TypeError, ValueError):
        return ''
    if not 0 < fps <= 240:
        return ''
    if abs(fps - round(fps)) < 0.005:
        return '%d' % round(fps)
    return ('%.3f' % fps).rstrip('0').rstrip('.')


def hdrNames(track):
    # ["HDR10", "Dolby Vision 8"]: what the player detected, nothing for SDR or an older player
    names = []
    if intValue(track, 'hdr') in HDR_NAMES:
        names.append(HDR_NAMES[intValue(track, 'hdr')])
    if intValue(track, 'dv') > 0:
        names.append('Dolby Vision %d' % intValue(track, 'dv'))
    return names


def sampleRateText(rate):
    try:
        rate = int(rate)
    except (TypeError, ValueError):
        return ''
    return '%g kHz' % (rate / 1000.0) if rate > 0 else ''


def subtitleFormatName(encode):
    encode = str(encode or '').upper()
    return SUBTITLE_FORMATS.get(encode, encode.split('/')[-1])


# the line count a resolution class stands for ("2160p"); SD names its own height
RESOLUTION_LINES = {'8K': 4320, '4K': 2160, 'QHD': 1440, 'FHD': 1080, 'HD': 720}
# the second name of a video codec under its badge
VIDEO_CODEC_SUBS = {'HEVC': 'H.265', 'H.264': 'AVC'}


def bitrateBadge(value):
    # ("2.5", "Mbit/s") - the number on the badge, the unit under it; None below 1 kbit/s
    text = bitrateText(value)
    if not text:
        return None
    number, unit = text.split(' ', 1)
    return number, unit


def badgeList(videoTrack, audioTrack, fps=0, subtitle=None, bitrate=0):
    # the badges of the infobar, [(kind, text, sub)]: kind 'res' is the resolution class, the badge that stands out;
    # sub the small line under a badge ("H.265" under "HEVC", "FPS", "Channels"), "" for none. subtitle: as
    # techSections() takes it, the shown subtitles get a badge of their language and format. bitrate: of the video
    # track, else of the whole stream (the HLS variant), in bit/s - the last badge, the first to go without room.
    badges = []
    video = videoTrack or {}
    if video:
        width, height = intValue(video, 'width'), intValue(video, 'height')
        res = resolutionClass(width, height)
        if res:
            badges.append(('res', res, ''))
            scan = 'i' if video.get('progressive') is False else 'p'
            badges.append(('video', '%d%s' % (RESOLUTION_LINES.get(res, height), scan), ''))
        codec = videoCodecNames(video.get('encode', ''))[0]
        if codec:
            badges.append(('video', codec, VIDEO_CODEC_SUBS.get(codec, '')))
        if intValue(video, 'bd') > 8:
            badges.append(('video', '%dbit' % intValue(video, 'bd'), ''))
        for name in hdrNames(video):
            badges.append(('video', 'DV' if name.startswith('Dolby Vision') else name, ''))
        rate = frameRateText(fps)
        if rate:
            badges.append(('video', rate, 'FPS'))
    audio = audioTrack or {}
    if audio:
        channels = channelsText(audio)
        if channels:
            badges.append(('audio', channels, _('Channels').strip()))
        codec = audioCodecName(audio)
        if codec:
            badges.append(('audio', codec, ''))
    subtitle = subtitle or {}
    if subtitle.get('kind'):
        language = str(subtitle.get('lang', '') or '').strip()
        language = '' if language.lower() in ('und', 'unknown') else language
        badges.append(('sub', (language[:3] or 'SUB').upper(), subtitle.get('format', '') or ''))
    rate = bitrateBadge(bitrate) if video else None
    if rate:
        badges.append(('video', rate[0], rate[1]))
    return badges


def stripTexts(videoTrack, audioTrack, subtitle=None, langName=None):
    # the info row under the infobar of a player skin that has one: [(label, value)] for video, video codec, audio,
    # audio codec and subtitles - "" where nothing is known
    langName = langName or (lambda name: name)
    video = videoTrack or {}
    audio = audioTrack or {}
    width, height = intValue(video, 'width'), intValue(video, 'height')
    resolution = ''
    if width > 0 and height > 0:
        resolution = '%d×%d' % (width, height)
        aspect = textValue(video, 'aspect_ratio')
        if aspect and aspect != 'unknown':
            resolution += ' (%s)' % aspect.replace('_', ':')
    videoCodec = videoCodecNames(video.get('encode', ''))[1] if video.get('encode') else ''
    audioValue = ' '.join(part for part in (audioCodecName(audio), channelsText(audio)) if part)
    encode = textValue(audio, 'encode')
    # the codec family of the stream ("DTS" under "DTS-HD MA"), the decoded PCM names none - then ffprobe's
    audioCodec = audioCodecFamily(encode) or textValue(audio, 'family')
    subtitle = subtitle or {}
    if subtitle.get('kind'):
        language = str(subtitle.get('lang', '') or '')
        language = '' if language.lower() in ('und', 'unknown') else langName(language)
        fileFormat = subtitle.get('format', '') or ''
        subtitleText = '%s (%s)' % (language, fileFormat) if language and fileFormat else (language or fileFormat or subtitle.get('title', ''))
    else:
        subtitleText = _('Off')
    return [(_('Video').strip(), resolution), (_('Video codec'), videoCodec), (_('Audio').strip(), audioValue),
            (_('Audio codec'), audioCodec), (_('Subtitles').strip(), subtitleText)]


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


def probeProfile(stream):
    # "Main 10@5.0" - ffprobe's level: 41 for H.264 level 4.1, 150 for H.265 level 5.0
    codec = str(stream.get('codec_name', ''))
    profile = str(stream.get('profile', '') or '')
    if not profile or profile == 'unknown':
        return ''
    divisor = {'h264': 10.0, 'hevc': 30.0}.get(codec)
    try:
        level = int(stream.get('level', 0) or 0)
    except (TypeError, ValueError):
        level = 0
    if divisor and level > 0:
        return '%s@%.1f' % (profile, level / divisor)
    return profile


def probeBitDepth(stream):
    depth = re.search(r'p(9|1[0246])(?:le|be)$', str(stream.get('pix_fmt', '')))
    return int(depth.group(1)) if depth else 0


def videoDetail(stream):
    codec = str(stream.get('codec_name', ''))
    name = CODEC_NAMES.get(codec, codec.upper())
    profile = probeProfile(stream)
    if profile:
        name += ' %s' % profile
    parts = [name]
    bitDepth = probeBitDepth(stream)
    if bitDepth:
        parts.append('%s Bit' % bitDepth)
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
        parts.append(CHANNEL_NAMES.get(layout, layout))
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


def probeStreams(probe, codecType):
    # the tracks of one kind in file order, without the cover picture of an MKV / MP4
    return [stream for stream in probe.get('streams', []) if stream.get('codec_type') == codecType and not stream.get('disposition', {}).get('attached_pic')]


def probeVideoTrack(stream):
    # an ffprobe stream in the keys of the player's video track
    transfer = {'smpte2084': 1, 'arib-std-b67': 2}.get(stream.get('color_transfer'), 0)
    return {'pr': probeProfile(stream), 'bd': probeBitDepth(stream), 'hdr': transfer, 'cr': str(stream.get('color_primaries', '') or ''),
            'pf': str(stream.get('pix_fmt', '') or ''),
            'br': stream.get('bit_rate', 0)}


def probeAudioTrack(stream):
    codec = str(stream.get('codec_name', ''))
    name = str(stream.get('profile', '')) if codec == 'dts' and stream.get('profile') else CODEC_NAMES.get(codec, codec.upper())
    # 'family': the codec without its profile ("DTS" of "DTS-HD MA") for an older player that only reports "IPCM"
    return {'d': name, 'family': CODEC_NAMES.get(codec, codec.upper()), 'cl': str(stream.get('channel_layout', '') or ''),
            'c': stream.get('channels', 0), 'sr': stream.get('sample_rate', 0), 'br': stream.get('bit_rate', 0),
            'bps': stream.get('bits_per_raw_sample', 0)}


def mergedTrack(track, probeTrack):
    # the player's values first, ffprobe's where the player has none (an older player, a value it doesn't know)
    merged = dict(probeTrack or {})
    for key, value in (track or {}).items():
        if value not in (None, '', 0, '0') or key not in merged:
            merged[key] = value
    return merged


def trackPosition(tracks, current):
    # (1-based number of the current track, number of tracks); (0, n) when it is not in the list
    currentId = (current or {}).get('id', -1)
    for idx, track in enumerate(tracks or []):
        if track.get('id', -2) == currentId:
            return idx + 1, len(tracks)
    return 0, len(tracks or [])


def probedTracks(video, audio, audioTracks, probe):
    # (video, audio): the player's current tracks with ffprobe's values where the player has none - an older
    # exteplayer3 names a software-decoded AAC only "IPCM", without its channels. {} for a missing track.
    probe = probe or {}
    videoStreams = probeStreams(probe, 'video')
    videoTrack = {}
    if video or videoStreams:
        videoTrack = mergedTrack(video, probeVideoTrack(videoStreams[0]) if videoStreams else {})
        if not videoTrack.get('encode') and videoStreams:
            videoTrack['encode'] = videoStreams[0].get('codec_name', '')
    audioStreams = probeStreams(probe, 'audio')
    audioTrack = {}
    if audio or audioStreams:
        number, count = trackPosition(audioTracks, audio)
        probeTrack = {}
        if len(audioStreams) == 1:
            probeTrack = probeAudioTrack(audioStreams[0])
        elif 0 < number <= len(audioStreams) and count == len(audioStreams):
            probeTrack = probeAudioTrack(audioStreams[number - 1])
        audioTrack = mergedTrack(audio, probeTrack)
    return videoTrack, audioTrack


def cutValue(text):
    # a capital letter counts 15 % more: a song title in capitals ("ASHE - STOP THE WEDDING!") ran out of the
    # row (box 23.11.) where a mixed-case text of the same length fits
    text = str(text or '').strip()

    def width(part):
        return len(part) + 0.15 * sum(1 for char in part if char.isupper())

    if width(text) <= VALUE_MAX:
        return text
    length = VALUE_MAX - 1
    while length > 0 and width(text[:length]) > VALUE_MAX - 0.5:
        length -= 1
    return text[:length].rstrip() + '…'


def techSections(video, audio, audioTracks, subtitle, probe=None, streamType='', linkBitrate=0, fps=0, langName=None, nowPlaying=''):
    # the rows of the "Playback info" page: [(section, [(label, value)])] for 'video', 'audio' and 'subtitle', a row
    # only with a value. video / audio: the player's current tracks; subtitle: {'kind': 'embedded' | 'file' | '',
    # 'index', 'count', 'lang', 'title', 'format', 'forced'}; probe: ffprobe's answer for a local file;
    # nowPlaying: the song a radio stream names ("Artist - Title").
    probe = probe or {}
    langName = langName or (lambda name: name)
    sections = []

    rows = []
    videoStreams = probeStreams(probe, 'video')
    videoTrack, audioTrack = probedTracks(video, audio, audioTracks, probe)
    if videoTrack:
        track = videoTrack
        encode = track.get('encode', '')
        rows.append((_('Codec'), videoCodecNames(encode)[1] if encode else ''))
        rows.append((_('Profile'), textValue(track, 'pr')))
        width, height = intValue(track, 'width'), intValue(track, 'height')
        if width > 0 and height > 0:
            scan = {True: 'p', False: 'i'}.get(track.get('progressive'), '')
            res = resolutionClass(width, height)
            rows.append((_('Resolution'), '%d×%d%s%s' % (width, height, scan, (SEPARATOR + res) if res else '')))
        aspect = textValue(track, 'aspect_ratio')
        if aspect and aspect != 'unknown':
            rows.append((_('Aspect ratio'), aspect.replace('_', ':')))
        rate = frameRateText(fps)
        rows.append((_('Frame rate'), ('%s fps' % rate) if rate else ''))
        rows.append((_('Bit depth'), ('%d bit' % intValue(track, 'bd')) if intValue(track, 'bd') > 0 else ''))
        # FFmpeg's name of it ("yuv420p10le"): ffprobe of a local file, or a player that reports it ("pf")
        rows.append((_('Pixel format'), textValue(track, 'pf')))
        rows.append(('HDR', ' + '.join(hdrNames(track))))
        primaries = textValue(track, 'cr')
        rows.append((_('Colour space'), COLOUR_NAMES.get(primaries, primaries.upper())))
        videoBitrate = bitrateText(track.get('br'))
        rows.append((_('Bitrate'), videoBitrate))
        if not videoBitrate:
            # video and audio together: the BANDWIDTH of the HLS variant, else what detailLine() takes of a local file
            audioStreams = probeStreams(probe, 'audio')
            rows.append((_('Total bitrate'), bitrateText(linkBitrate) or bitrateText(tracksBitrate(videoStreams + audioStreams))
                         or bitrateText(probe.get('format', {}).get('bit_rate'))))
    # radio: the video column only names the stream
    fileFormat = str(probe.get('format', {}).get('format_name', '')).split(',')[0]
    container = CONTAINER_NAMES.get(fileFormat, fileFormat.upper()) if fileFormat else ''
    rows.append((_('Stream'), SEPARATOR.join(part for part in (streamType, container if container != streamType else '') if part)))
    sections.append(('video', [(label, cutValue(value)) for label, value in rows if value]))

    rows = []
    if audioTrack:
        number, count = trackPosition(audioTracks, audio)
        track = audioTrack
        # not "Now playing": its German translation is the cinema one ("Jetzt im Kino")
        rows.append((_('Current song'), plainText(nowPlaying)))
        if count > 1 and number:
            rows.append((_('Track'), '%d / %d' % (number, count)))
        language = textValue(track, 'name')
        if language and language.lower() not in ('und', 'unknown'):
            rows.append((_('Language'), langName(language)))
        rows.append((_('Title'), textValue(track, 't')))
        codec = audioCodecName(track)
        if textValue(track, 'encode').upper() == 'IPCM':
            # decoded by the player itself
            codec = '%s (%s)' % (codec, _('software')) if codec else 'PCM (%s)' % _('software')
        rows.append((_('Codec'), codec))
        channels = channelsText(track)
        if channels and intValue(track, 'c') > 0 and channels != '%d ch' % intValue(track, 'c'):
            channels += ' (%d ch)' % intValue(track, 'c')
        rows.append((_('Channels'), channels))
        rows.append((_('Sample rate'), sampleRateText(track.get('sr'))))
        rows.append((_('Bit depth'), ('%d bit' % intValue(track, 'bps')) if intValue(track, 'bps') > 0 else ''))
        rows.append((_('Bitrate'), bitrateText(track.get('br'))))
    sections.append(('audio', [(label, cutValue(value)) for label, value in rows if value]))

    rows = []
    subtitle = subtitle or {}
    if subtitle.get('kind'):
        # index 0: the player's track is not in the list of tracks - no "0 / 3"
        if subtitle.get('kind') == 'embedded' and subtitle.get('count', 0) > 1 and subtitle.get('index'):
            rows.append((_('Track'), '%d / %d' % (subtitle.get('index', 0), subtitle['count'])))
        language = str(subtitle.get('lang', '') or '')
        if language and language.lower() not in ('und', 'unknown'):
            rows.append((_('Language'), langName(language)))
        rows.append((_('Title'), subtitle.get('title', '')))
        rows.append((_('Type'), subtitle.get('format', '')))
        if subtitle.get('forced'):
            rows.append((_('Forced'), _('Yes')))
        if subtitle.get('kind') == 'file':
            rows.append((_('Source'), _('File')))
    else:
        rows.append((_('Track'), _('Off')))
    sections.append(('subtitle', [(label, cutValue(value)) for label, value in rows if value]))
    return sections


def nowPlayingText(message):
    # exteplayer3's "m_t" ({"rt": "Artist - Title", "t": title, "a": artist}) as one line, "" without a song
    if not isinstance(message, dict):
        return ''
    text = plainText(message.get('rt', ''))
    if not text:
        text = ' - '.join(part for part in (plainText(message.get('a', '')), plainText(message.get('t', ''))) if part)
    return text


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


# the infobar's meta line: these values without their labels ("2026  ·  Action, Comedy  ·  USA")
INFOBAR_META_KEYS = ('year', 'genre', 'genres', 'country')
# the rating beside the title, by the key of the host's rich description
RATING_KEYS = (('imdb_rating', 'IMDb'), ('tmdb_rating', 'TMDb'))


def shortMetaLine(params):
    # a host with its own rows (custom_items_list) keeps them as the INFO page shows them
    if not isinstance(params, dict):
        return ''
    if 'custom_items_list' in params:
        return metaLine(params)
    parts = []
    for key in INFOBAR_META_KEYS:
        text = plainText(params.get(key, ''))
        if text and text.upper() != 'N/A' and text not in parts:
            parts.append(text)
    return SEPARATOR.join(parts)


def ratingValue(text):
    # "7.2" of "7.2/10", "7,2" or "IMDb: 7.2"; "" for none or 0
    match = re.search(r'\d+(?:[.,]\d+)?', plainText(text))
    if not match:
        return ''
    value = match.group(0).replace(',', '.')
    try:
        return value if 0 < float(value) <= 10 else ''
    except ValueError:
        return ''


def articleRating(params):
    # "IMDb 7.2" from the host's rich description (or its own rows), "" without a rating
    if not isinstance(params, dict):
        return ''
    if 'custom_items_list' in params:
        for item in params['custom_items_list']:
            if isinstance(item, tuple) and len(item) == 2:
                label = plainText(item[0]).lower()
                for name in [entry[1] for entry in RATING_KEYS]:
                    if name.lower() in label and ratingValue(item[1]):
                        return '%s %s' % (name, ratingValue(item[1]))
        return ''
    for key, name in RATING_KEYS:
        value = ratingValue(params.get(key, ''))
        if value:
            return '%s %s' % (name, value)
    return ''


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


# the rounded panels (forum 27.11.): a picture in the panel's size made with PIL - its corners transparent, a thin
# frame, inside the panel colour or the title's backdrop / poster blurred and darkened (Enigma2 can't round or blur
# a widget itself). Opaque inside: a colour with alpha would show the video, not the picture behind the panel.
PANEL_RGB = (16, 16, 16)
FRAME_RGB = (72, 80, 94)
# on the 1280x720 canvas
PANEL_RADIUS = 16
# how much of the picture stays in the mix with the panel colour: the backdrop is darkened already, a poster not
BACKDROP_SHARE, POSTER_SHARE = 0.55, 0.3
PANEL_PICTURE = '/tmp/e2i_infopanel_%s.png'


def infoPanelBackground():
    # 'picture' (the backdrop, else the poster, blurred) or 'dark'
    try:
        return config.plugins.iptvplayer.infopanel_background.value
    except Exception:
        return 'picture'


def roundedMask(width, height, radius):
    # 'L' mask, 255 inside, its four corners cut round with a smooth edge (drawn four times larger, then scaled down)
    from PIL import Image, ImageDraw
    mask = Image.new('L', (width, height), 255)
    radius = max(0, min(radius, width // 2, height // 2))
    if radius:
        big = Image.new('L', (radius * 4, radius * 4), 0)
        ImageDraw.Draw(big).pieslice((0, 0, radius * 8 - 1, radius * 8 - 1), 180, 270, fill=255)
        corner = big.resize((radius, radius), Image.LANCZOS)
        mask.paste(corner, (0, 0))
        mask.paste(corner.transpose(Image.FLIP_LEFT_RIGHT), (width - radius, 0))
        mask.paste(corner.transpose(Image.FLIP_TOP_BOTTOM), (0, height - radius))
        mask.paste(corner.transpose(Image.ROTATE_180), (width - radius, height - radius))
    return mask


def _blurred(img, width, height, factor):
    # a strong blur at little cost on the box: scaled down, blurred, scaled up again
    from PIL import Image, ImageFilter
    small = img.resize((max(1, width // factor), max(1, height // factor)), Image.BILINEAR)
    return small.filter(ImageFilter.GaussianBlur(2)).resize((width, height), Image.BILINEAR)


def _filled(img, width, height):
    # scaled to fill width x height, the middle cut out
    from PIL import Image
    srcW, srcH = img.size
    scale = max(width / float(srcW), height / float(srcH))
    cropW, cropH = min(srcW, max(1, int(round(width / scale)))), min(srcH, max(1, int(round(height / scale))))
    left, top = (srcW - cropW) // 2, (srcH - cropH) // 2
    return img.crop((left, top, left + cropW, top + cropH)).resize((width, height), Image.BILINEAR)


def panelInside(width, height, backdrop='', position=(0, 0), poster=''):
    # the inside of the panel: the piece of the screen's backdrop under it (position: the panel's place on the
    # screen), else the poster filling it; both blurred and mixed with the panel colour. None: the plain colour.
    from PIL import Image
    try:
        if backdrop:
            with Image.open(backdrop) as src:
                x, y = position
                piece = src.convert('RGB').crop((x, y, x + width, y + height))
            return Image.blend(Image.new('RGB', (width, height), PANEL_RGB), _blurred(piece, width, height, 8), BACKDROP_SHARE)
        if poster:
            with Image.open(poster) as src:
                piece = _filled(src.convert('RGB'), width, height)
            return Image.blend(Image.new('RGB', (width, height), PANEL_RGB), _blurred(piece, width, height, 16), POSTER_SHARE)
    except Exception:
        printExc()
    return None


def makePanelPicture(target, width, height, scale, backdrop='', position=(0, 0), poster=''):
    # the panel's background as PNG; scale: real pixels per pixel of the 1280x720 canvas
    from PIL import Image
    if width < 8 or height < 8:
        return False
    line = max(1, int(round(scale)))
    radius = max(2, int(round(PANEL_RADIUS * scale)))
    inside = panelInside(width, height, backdrop, position, poster)
    if inside is None:
        inside = Image.new('RGB', (width, height), PANEL_RGB)
    picture = Image.new('RGBA', (width, height), FRAME_RGB + (255,))
    picture.putalpha(roundedMask(width, height, radius))
    picture.paste(inside.crop((line, line, width - line, height - line)), (line, line),
                  roundedMask(width - 2 * line, height - 2 * line, max(1, radius - line)))
    picture.save(target + '.part', format='PNG', compress_level=1)
    os.replace(target + '.part', target)
    return True


class PlayerInfoPanel(object):
    # INFO in the player: page 1 where the video comes from and the texts of the host, INFO again page 2 ("Playback
    # info") with the formats of the playing tracks in three columns, INFO once more (or EXIT) closes it
    LABELS = ('infoPanelTitle', 'infoPanelSource', 'infoPanelStream', 'infoPanelDetail', 'infoPanelMeta', 'infoPanelText')
    # *PanelBg: the plain panel colour, *PanelFrame: the rounded picture in front of it once made (makePanelPicture);
    # only one of the two is shown
    WIDGETS = ('infoPanelBg', 'infoPanelFrame', 'infoPanelCover') + LABELS
    SECTIONS = ('video', 'audio', 'subtitle')
    TECH_LABELS = ('techPanelTitle',) + tuple('techPanel%s%s' % (section.capitalize(), part) for section in SECTIONS for part in ('Head', 'Keys', 'Values'))
    # the lines between the columns of "Playback info" (forum 25.11.)
    TECH_SEPARATORS = ('techPanelSep1', 'techPanelSep2')
    TECH_WIDGETS = ('techPanelBg', 'techPanelFrame') + TECH_LABELS + TECH_SEPARATORS
    # opaque: a background with alpha lets the VIDEO through, Enigma2 writes its alpha straight into the OSD (forum
    # 25.11.: the film shone through the panels, also over the backdrop) - the labels in front have the same colour
    PANEL_COLOUR = '#00101010'
    SEPARATOR_COLOUR = '#00505866'

    # (name, y, height, font size, colour) on the 1280x720 canvas of the player skins. The player's infobar lies at
    # the bottom, from y=543 in the skins with the highest bar
    PANEL_X, PANEL_Y, PANEL_W = 30, 20, 1220
    PANEL_H = 411
    PADDING = 15
    COVER_W, COVER_H = 135, 200
    ROWS = (('infoPanelTitle', 30, 36, 28, '#ffffff'),
            ('infoPanelSource', 68, 56, 21, '#66ccff'),
            ('infoPanelStream', 124, 28, 21, '#66ccff'),
            ('infoPanelDetail', 156, 56, 21, '#66ccff'),
            ('infoPanelMeta', 216, 56, 21, '#cccccc'),
            ('infoPanelText', 276, 140, 21, '#ffffff'))
    # page 2: a column per section, its label beside the value
    TECH_COLUMN_X = (45, 455, 865)
    TECH_HEAD_Y, TECH_ROWS_Y = 76, 110
    TECH_KEY_W, TECH_VALUE_W = 175, 205
    TECH_FONT = 19

    @classmethod
    def skinWidgets(cls, scale=1.0):
        # scale: 1 on a skin with resolution="1280,720" (Enigma2 scales it), else the real pixels of the "sd" skin
        def px(value):
            return int(value * scale)

        def label(name, x, y, w, h, font, colour, extra=''):
            return '<widget name="%s"%s position="%d,%d" size="%d,%d" zPosition="11" transparent="1" foregroundColor="%s" backgroundColor="%s" font="Regular;%d" halign="left" valign="top" />' % (name, extra, px(x), px(y), px(w), px(h), colour, cls.PANEL_COLOUR, max(px(font), 16))

        textX = cls.PANEL_X + cls.COVER_W + 2 * cls.PADDING
        textW = cls.PANEL_W - cls.COVER_W - 3 * cls.PADDING
        def frame(name):
            return '<widget name="%sBg" position="%d,%d" size="%d,%d" zPosition="10" backgroundColor="%s" />' % (name, px(cls.PANEL_X), px(cls.PANEL_Y), px(cls.PANEL_W), px(cls.PANEL_H), cls.PANEL_COLOUR) + \
                '<widget name="%sFrame" position="%d,%d" size="%d,%d" zPosition="10" transparent="1" alphatest="blend" />' % (name, px(cls.PANEL_X), px(cls.PANEL_Y), px(cls.PANEL_W), px(cls.PANEL_H))

        skin = frame('infoPanel')
        skin += '<widget name="infoPanelCover" position="%d,%d" size="%d,%d" zPosition="11" transparent="1" alphatest="blend" />' % (px(cls.PANEL_X + cls.PADDING), px(cls.PANEL_Y + cls.PADDING), px(cls.COVER_W), px(cls.COVER_H))
        for name, y, height, font, colour in cls.ROWS:
            skin += label(name, textX, y, textW, height, font, colour, ' noWrap="1"' if name in ('infoPanelTitle', 'infoPanelStream') else '')

        skin += frame('techPanel')
        skin += label('techPanelTitle', cls.PANEL_X + cls.PADDING, 30, cls.PANEL_W - 2 * cls.PADDING, 36, 28, '#ffffff', ' noWrap="1"')
        rowsH = cls.PANEL_Y + cls.PANEL_H - cls.PADDING - cls.TECH_ROWS_Y
        for section, x in zip(cls.SECTIONS, cls.TECH_COLUMN_X):
            name = 'techPanel' + section.capitalize()
            skin += label(name + 'Head', x, cls.TECH_HEAD_Y, cls.TECH_KEY_W + cls.TECH_VALUE_W, 30, 22, '#66ccff', ' noWrap="1"')
            skin += label(name + 'Keys', x, cls.TECH_ROWS_Y, cls.TECH_KEY_W, rowsH, cls.TECH_FONT, '#999999', ' noWrap="1"')
            skin += label(name + 'Values', x + cls.TECH_KEY_W, cls.TECH_ROWS_Y, cls.TECH_VALUE_W, rowsH, cls.TECH_FONT, '#ffffff', ' noWrap="1"')
        # a line in the middle of the gap before the 2nd and 3rd column; _layoutTech() makes it as high as the rows
        gap = cls.TECH_COLUMN_X[1] - cls.TECH_COLUMN_X[0] - cls.TECH_KEY_W - cls.TECH_VALUE_W
        for name, x in zip(cls.TECH_SEPARATORS, cls.TECH_COLUMN_X[1:]):
            skin += '<widget name="%s" position="%d,%d" size="%d,%d" zPosition="11" backgroundColor="%s" />' % (
                name, px(x - gap // 2), px(cls.TECH_HEAD_Y), max(1, px(1)), px(cls.PANEL_Y + cls.PANEL_H - cls.PADDING - cls.TECH_HEAD_Y), cls.SEPARATOR_COLOUR)
        return skin

    def __init__(self, owner, additionalParams):
        self.owner = owner
        self.hostTitle = additionalParams.get('host_title', '') or owner.hostName
        self.linkName = additionalParams.get('link_name', '')
        self.coverPath = additionalParams.get('cover_path', '')
        self.provider = additionalParams.get('info_provider', None)
        self.text = plainText(additionalParams.get('info_description', ''))
        self.meta = ''
        # for the infobar of a skin like "modern": year / genre / country, the rating beside the title
        self.shortMeta = ''
        self.rating = ''
        # url of the title's backdrop from the host's page (components/iptvbackdrop.py)
        self.backdrop = ''
        self.visible = False
        # 1 the page of the source and texts, 2 "Playback info"
        self.page = 0
        self.closed = False
        self.geometry = None
        self.techGeometry = None
        self.articleRet = None
        self.articleThread = None
        # the host's whole INFO page (ArticleContent) once loaded, and who waits for it (getArticle)
        self.article = None
        self.articleCallbacks = []
        # None: not asked yet, True: the answer is on its way, False: done
        self.articlePending = None
        self.timer = eTimer()
        self.timer_conn = eConnectCallback(self.timer.timeout, self._checkArticle)
        self.probe = {}
        self.probeHandle = None
        self.probeTimer = eTimer()
        self.probeTimer_conn = eConnectCallback(self.probeTimer.timeout, self._stopProbe)
        # per panel ('info', 'tech'): what its rounded picture was made of, None: none there
        self.frameKeys = {}
        self.framesFailed = False
        owner['infoPanelBg'] = Label(' ')
        owner['infoPanelFrame'] = Pixmap()
        owner['techPanelFrame'] = Pixmap()
        owner['infoPanelCover'] = Cover()
        for name in self.LABELS + self.TECH_WIDGETS:
            if name != 'techPanelFrame':
                owner[name] = Label(' ')
        self._setWidgetsVisible(False)
        self._setWidgetsVisible(False, self.TECH_WIDGETS)

    def _setWidgetsVisible(self, visible, names=None):
        for name in names or self.WIDGETS:
            if visible:
                self.owner[name].show()
            else:
                self.owner[name].hide()

    def show(self):
        self._setWidgetsVisible(False, self.TECH_WIDGETS)
        self._requestArticle()
        self._startProbe()
        self._fill()
        self._setWidgetsVisible(True)
        self._showBackground('info')
        if not self._hasCover():
            self.owner['infoPanelCover'].hide()
        self.visible = True
        self.page = 1
        self._showCover()
        self._updateBackdrop()

    def showTech(self):
        # page 2: the formats of the playing tracks
        self._setWidgetsVisible(False)
        self._startProbe()
        self.visible = True
        self.page = 2
        self._fillTech()
        self._updateBackdrop()

    def hide(self):
        self.visible = False
        self.page = 0
        self._setWidgetsVisible(False)
        self._setWidgetsVisible(False, self.TECH_WIDGETS)
        self._updateBackdrop()

    def backgroundChanged(self):
        # the backdrop came in: an open panel gets it under its texts
        if self.page:
            self._refresh()

    def _panelSources(self):
        # (backdrop file, poster file) for the inside of the rounded panels; both '' with the setting "Dark"
        if infoPanelBackground() != 'picture':
            return '', ''
        backdropFile = getattr(self.owner, 'backdropFile', None)
        try:
            backdrop = backdropFile() if backdropFile is not None else ''
        except Exception:
            printExc()
            backdrop = ''
        return backdrop or '', '' if backdrop or not self._hasCover() else self.coverPath

    def _paintFrame(self, kind, x, y, width, height):
        # the rounded picture of panel kind ('info', 'tech') in real pixels; True when it is in its widget
        if self.framesFailed:
            return False
        backdrop, poster = self._panelSources()
        key = (x, y, width, height, backdrop, poster)
        if self.frameKeys.get(kind) == key:
            return True
        self.frameKeys[kind] = None
        target = PANEL_PICTURE % kind
        try:
            if not makePanelPicture(target, width, height, width / float(self.PANEL_W), backdrop, (x, y), poster):
                return False
            pixmap = LoadPixmap(target, cached=False)
            if pixmap is None:
                return False
            instance = self.owner[kind + 'PanelFrame'].instance
            instance.move(ePoint(x, y))
            instance.resize(eSize(width, height))
            instance.setPixmap(pixmap)
        except ImportError:
            # no PIL: the plain panels for the rest of the playback
            printDBG("PlayerInfoPanel: no PIL, plain panels")
            self.framesFailed = True
            return False
        except Exception:
            printExc()
            return False
        self.frameKeys[kind] = key
        return True

    def _showBackground(self, kind):
        # the rounded picture when it is there, else the plain colour
        hasFrame = self.frameKeys.get(kind) is not None
        self._setWidgetsVisible(hasFrame, (kind + 'PanelFrame',))
        self._setWidgetsVisible(not hasFrame, (kind + 'PanelBg',))

    def _updateBackdrop(self):
        # the player shows the backdrop behind the panel while it is open
        update = getattr(self.owner, 'updateBackdrop', None)
        if update is not None:
            try:
                update()
            except Exception:
                printExc()

    def close(self):
        self.hide()
        self.closed = True
        self.provider = None
        self.articleCallbacks = []
        self.timer.stop()
        self.timer_conn = None
        self._stopProbe()
        self.probeTimer_conn = None
        # the pictures of the panels are as large as the screen: not left in the RAM of /tmp
        for kind in ('info', 'tech'):
            try:
                os.remove(PANEL_PICTURE % kind)
            except OSError:
                pass

    def requestArticle(self):
        # the host's page in the background before the first INFO: the infobar of a skin like "modern" shows its year,
        # genre and rating
        self._requestArticle()

    def startProbe(self):
        # also before the first INFO: the badges and the info row of a skin like "modern" take ffprobe's values
        self._startProbe()

    def probedTracks(self):
        # (video, audio) of the player with ffprobe's values of a local file where the player has none
        playback = self.owner.playback
        return probedTracks(playback.get('VideoTrack') or {}, playback.get('AudioTrack') or {}, playback.get('AudioTracks') or [], self.probe)

    def _startProbe(self):
        # once it read the file; a buffer file with too little in it yet gets another try on the next INFO / track report
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
        self._refresh()
        # the badges and the info row of the infobar take its values too
        refresh = getattr(self.owner, 'refreshInfoBarFormats', None)
        if refresh is not None and self.probe:
            refresh()

    def _stopProbe(self):
        self.probeTimer.stop()
        if self.probeHandle is not None:
            self.probeHandle.kill()
            self.probeHandle = None

    def updateStream(self):
        # the player reports the tracks a moment after it starts, an audio change later
        if self.page == 1:
            self.owner['infoPanelStream'].setText(self._streamText())
        elif self.page == 2:
            self._fillTech()

    def _refresh(self):
        if self.page == 1:
            self._fill()
        elif self.page == 2:
            self._fillTech()

    def _techSections(self):
        owner = self.owner
        playback = owner.playback
        video = playback.get('VideoTrack') or {}
        frameRate = getattr(owner, 'currentFrameRate', None)
        subtitleInfo = getattr(owner, 'currentSubtitleInfo', None)
        streamType = getattr(owner, '_getStreamTypeLabel', None)
        return techSections(video, playback.get('AudioTrack') or {}, playback.get('AudioTracks') or [],
                            subtitleInfo() if subtitleInfo else {}, self.probe, streamType() if streamType else '',
                            streamBitrate(owner.getStreamSourceUrl()), frameRate() if frameRate else video.get('frame_rate', 0),
                            getattr(owner, 'trackLanguageName', None), playback.get('NowPlaying', ''))

    def _fillTech(self):
        try:
            sections = self._techSections()
        except Exception:
            printExc()
            sections = []
        owner = self.owner
        owner['techPanelTitle'].setText(StripColorCodes(owner.title))
        heads = {'video': _('Video'), 'audio': _('Audio'), 'subtitle': _('Subtitles')}
        # a section without rows leaves its column free, the next ones move up into it
        shown = [(section, rows) for section, rows in sections if rows]
        names = ['techPanelTitle']
        for section, rows in shown:
            name = 'techPanel' + section.capitalize()
            owner[name + 'Head'].setText(heads[section].strip())
            owner[name + 'Keys'].setText('\n'.join(label.strip() for label, value in rows))
            owner[name + 'Values'].setText('\n'.join(value for label, value in rows))
            names += [name + 'Head', name + 'Keys', name + 'Values']
        # a line between each two shown columns
        names += list(self.TECH_SEPARATORS[:max(0, len(shown) - 1)])
        try:
            self._layoutTech([section for section, rows in shown])
        except Exception:
            printExc()
        self._setWidgetsVisible(False, self.TECH_WIDGETS)
        self._setWidgetsVisible(True, names)
        self._showBackground('tech')

    def _layoutTech(self, shown):
        # real pixels as in _layout(): the columns in the order of the shown sections, the panel as high as its
        # longest column
        owner = self.owner
        if self.techGeometry is None:
            self.techGeometry = {}
            for name in self.TECH_WIDGETS:
                instance = owner[name].instance
                self.techGeometry[name] = (instance.position().x(), instance.position().y(), instance.size().width(), instance.size().height())
        bgX, bgY, bgW, bgH = self.techGeometry['techPanelBg']
        bottom = self.techGeometry['techPanelTitle'][1] + self.techGeometry['techPanelTitle'][3]
        padding = self.techGeometry['techPanelTitle'][1] - bgY
        for column, section in enumerate(shown):
            name = 'techPanel' + section.capitalize()
            target = 'techPanel' + self.SECTIONS[column].capitalize()
            for part in ('Head', 'Keys', 'Values'):
                x, y, w, h = self.techGeometry[target + part]
                instance = owner[name + part].instance
                instance.move(ePoint(x, y))
                if part == 'Head':
                    instance.resize(eSize(w, h))
                    continue
                instance.resize(eSize(w, self.techGeometry[name + part][3]))
                height = min(instance.calculateSize().height(), self.techGeometry[name + part][3])
                instance.resize(eSize(w, height))
                bottom = max(bottom, y + height)
        height = min(bottom + padding - bgY, bgH)
        owner['techPanelBg'].instance.resize(eSize(bgW, height))
        self._paintFrame('tech', bgX, bgY, bgW, height)
        # the column lines reach from the headings to the last row
        for name in self.TECH_SEPARATORS:
            x, y, w, h = self.techGeometry[name]
            owner[name].instance.resize(eSize(w, max(1, min(bottom - y, h))))

    def _sourceText(self):
        return sourceLine(self.hostTitle, self.linkName, serverName(self.owner.getStreamSourceUrl()))

    def _streamText(self):
        playback = self.owner.playback
        return streamLine(self.owner['videoInfo'].getText(), playback.get('AudioTrack'), bool(playback.get('VideoTrack')))

    def _hasCover(self):
        try:
            return bool(self.coverPath) and os.path.getsize(self.coverPath) > 0
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

    def getArticle(self, callback):
        # the host's INFO page for the player's "Description": callback(ArticleContent or None), at once when it is
        # loaded already (or there is no host to ask), else when the answer comes
        if self.closed or (self.provider is None and self.articlePending is None) or self.articlePending is False:
            callback(self.article)
            return
        self.articleCallbacks.append(callback)
        self._requestArticle()
        if self.articlePending is False:
            # the request could not start
            self._runArticleCallbacks()

    def _runArticleCallbacks(self):
        callbacks, self.articleCallbacks = self.articleCallbacks, []
        for callback in callbacks:
            try:
                callback(self.article)
            except Exception:
                printExc()

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
                self.article = value[0]
                # a page without a text of its own keeps the description of the list row
                self.text = plainText(value[0].text) or self.text
                self.meta = metaLine(value[0].richDescParams)
                self.shortMeta = shortMetaLine(value[0].richDescParams)
                self.rating = articleRating(value[0].richDescParams)
                self.backdrop = getattr(value[0], 'backdrop', '') or ''
        except Exception:
            printExc()
        printDBG("PlayerInfoPanel article loaded meta[%s] rating[%s] backdrop[%s]" % (self.meta, self.rating, self.backdrop))
        setBackdrop = getattr(self.owner, 'setBackdropUrl', None)
        if setBackdrop is not None and self.backdrop:
            try:
                setBackdrop(self.backdrop)
            except Exception:
                printExc()
        if self.page == 1:
            self._fill()
        self._runArticleCallbacks()
        # a player skin with a meta line in its infobar shows year / genre from now on
        updateMeta = getattr(self.owner, 'updateInfoBarMeta', None)
        if updateMeta is not None:
            try:
                updateMeta()
            except Exception:
                printExc()

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
        height = bottom + (coverY - bgY) - bgY
        owner['infoPanelBg'].instance.resize(eSize(bgW, height))
        self._paintFrame('info', self.geometry['infoPanelBg'][0], bgY, bgW, height)
        if self.page == 1:
            self._showBackground('info')
