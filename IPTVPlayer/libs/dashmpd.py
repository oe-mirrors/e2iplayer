# -*- coding: utf-8 -*-
# Added: 25.10.2026 - MPEG-DASH manifests (ISO/IEC 23009-1, DASH-IF guidelines) for getMPDLinksWithMeta and the players
#
# parseMpd() reads the MPD with a real XML parser: the period that gets played, the video / audio representations
# with codec, resolution, frame rate, HDR, language, role, label and channels, subtitle files, DRM; trick-mode and
# thumbnail sets are left out. buildLinks() turns that into the "Select link" items.
#
# filterMpd() cuts the MPD down to the chosen video + audio representation. ffmpeg's dashdec (exteplayer3, the
# downloader) opens every representation of a manifest (init + first segment of each: 35 s for the 39 track BBC
# test card, under 2 s filtered), has no option to pick one (-video_rep_index came from an ffmpeg patch OE-A no
# longer carries - ffmpeg 9 stops with "Unrecognized option") and gets some live manifests wrong:
#  - availabilityStartTime 1970-01-01T00:00:00Z reads as "unset", the live position is then taken from
#    publishTime (BBC: the segment of the day the MPD was written -> 404),
#  - without suggestedPresentationDelay it asks for the segment at the live edge that is not there yet,
#  - with presentationTimeOffset / a period start it ignores the period start (HTTP 425 "Too Early").
#
# localManifestUrl() serves the filtered MPD on 127.0.0.1: exteplayer3 / gstplayer / the ffmpeg downloader read it
# over HTTP (dashdec passes the http headers of the manifest request on to the segments - a local file would lose
# them) and a live MPD is fetched again for every refresh.
#
# 26.10.2026 - segmented subtitles of a VOD MPD (stpp / wvtt in fragmented MP4, plain WebVTT / TTML segments):
# localSubtitleUrl() offers them as http://127.0.0.1:<port>/dash/<token>.vtt in external_sub_tracks; the server
# fetches the segments (subtitleSegments) and writes one WebVTT text (libs/dashsubs.py) while they come in - the
# player and the download manager load it as any subtitle file.
#
# 27.10.2026 - downloadPlan() lists the segments of the chosen representations for the own DASH downloader
# (iptvdm/dashdownloader.py, fetched with openUrl / readRange); filterMpd(startDelay) starts a live MPD further
# behind the edge for the player buffer; a VOD $Number$ template gets startNumber="1" written (dashdec counts from 0).
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
# FOREIGN import
###################################################
import gzip
import hashlib
import io
import math
import re
import ssl
import threading
import time
import xml.etree.ElementTree as ET
from calendar import timegm
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urljoin
from urllib.request import Request, urlopen
###################################################

MPD_NS = 'urn:mpeg:dash:schema:mpd:2011'

# the http headers a link meta may carry (DMHelper.HANDLED_HTTP_HEADER_PARAMS without Range / Host)
HTTP_HEADERS = ('Accept', 'Cookie', 'Referer', 'User-Agent', 'Origin', 'X-Playback-Session-Id', 'X-Forwarded-For',
                'Authorization', 'Accept-Language', 'Sec-Fetch-Site')

VIDEO_CODECS = (('avc', 'H.264'), ('hev1', 'HEVC'), ('hvc1', 'HEVC'), ('dvh1', 'HEVC DV'), ('dvhe', 'HEVC DV'),
                ('dva1', 'H.264 DV'), ('dvav', 'H.264 DV'), ('vp09', 'VP9'), ('vp9', 'VP9'), ('av01', 'AV1'),
                ('mp4v', 'MPEG-4'))
AUDIO_CODECS = (('mp4a.40.5', 'HE-AAC'), ('mp4a.40.29', 'HE-AACv2'), ('mp4a.6b', 'MP3'), ('mp4a.69', 'MP3'),
                ('mp4a', 'AAC'), ('ac-3', 'AC-3'), ('ec-3', 'E-AC-3'), ('ac-4', 'AC-4'), ('opus', 'Opus'),
                ('flac', 'FLAC'), ('dtsc', 'DTS'), ('dtse', 'DTS'), ('dtsx', 'DTS:X'), ('mhm1', 'MPEG-H'),
                ('mha1', 'MPEG-H'), ('mp3', 'MP3'))
TEXT_CODECS = ('stpp', 'wvtt', 'tx3g', 'c608')
# many set-top boxes do not decode these (a VU+ Uno 4K SE plays VP9, 28.10.) - the links stay in the list (to be
# chosen by hand) but go to its end, so an automatic pick lands on a codec every box plays
UNDECODABLE = ('VP9', 'AV1', 'HEVC DV', 'H.264 DV')
SUB_EXTENSIONS = {'vtt': 'vtt', 'webvtt': 'vtt', 'srt': 'srt', 'ttml': 'ttml', 'dfxp': 'ttml', 'xml': 'ttml'}


###################################################
# XML helpers
###################################################
def _local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _kids(elem, name):
    return [c for c in elem if _local(c.tag) == name]


def _kid(elem, name):
    for c in elem:
        if _local(c.tag) == name:
            return c
    return None


def parseDuration(value, default=0.0):
    # xs:duration "PT1H2M3.5S", "P1DT2H", "-PT5S" -> seconds
    m = re.match(r'^\s*(-)?P(?:(\d+(?:\.\d+)?)Y)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)D)?'
                 r'(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?\s*$', value or '')
    if not m or value.strip() in ('P', 'PT'):
        return default
    parts = [float(x) if x else 0.0 for x in m.groups()[1:]]
    secs = parts[0] * 31536000 + parts[1] * 2592000 + parts[2] * 86400 + parts[3] * 3600 + parts[4] * 60 + parts[5]
    return -secs if m.group(1) else secs


def parseDateTime(value, default=None):
    # xs:dateTime "2026-10-25T18:00:00Z", "...+01:00", with or without fraction -> epoch seconds
    m = re.match(r'^\s*(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(\.\d+)?\s*(Z|[+-]\d\d:?\d\d)?\s*$', value or '')
    if not m:
        return default
    secs = timegm((int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)), 0, 0, 0))
    if m.group(7):
        secs += float(m.group(7))
    tz = m.group(8)
    if tz and tz != 'Z':
        sign = -1 if tz[0] == '+' else 1
        tz = tz[1:].replace(':', '')
        secs += sign * (int(tz[:2]) * 3600 + int(tz[2:]) * 60)
    return secs


def _frameRate(value):
    # "25", "30000/1001" -> 25, 29.97
    try:
        if '/' in value:
            num, den = value.split('/', 1)
            value = float(num) / float(den)
        else:
            value = float(value)
        return round(value, 3)
    except Exception:
        return 0


def _toInt(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


###################################################
# reading the MPD
###################################################
def _setType(aset, reps):
    # contentType of an AdaptationSet: the attribute, else mimeType / codecs / ContentComponent
    ctype = (aset.get('contentType') or '').lower()
    mime = (aset.get('mimeType') or (reps[0].get('mimeType') if reps else '') or '').lower()
    codecs = ((aset.get('codecs') or '') + ',' + ','.join(r.get('codecs') or '' for r in reps)).lower()
    if not ctype:
        comp = _kid(aset, 'ContentComponent')
        if comp is not None:
            ctype = (comp.get('contentType') or '').lower()
    if not ctype:
        if mime.startswith('video/'):
            ctype = 'video'
        elif mime.startswith('audio/'):
            ctype = 'audio'
        elif mime.startswith('image/'):
            ctype = 'image'
        elif mime.startswith('text/') or 'ttml' in mime or 'vtt' in mime:
            ctype = 'text'
    if ctype in ('video', 'application', '') and any(c in codecs for c in TEXT_CODECS):
        ctype = 'text'
    if ctype == 'application':
        ctype = 'text'
    if not ctype:
        if re.search(r'(?:^|,)(?:avc|hev|hvc|vp0?9|av01|dv)', codecs):
            ctype = 'video'
        elif re.search(r'(?:^|,)(?:mp4a|ac-|ec-|opus|flac)', codecs):
            ctype = 'audio'
    for prop in _kids(aset, 'EssentialProperty'):
        if 'trickmode' in (prop.get('schemeIdUri') or '').lower():
            return 'trick'
    return ctype


def _codecLabel(codecs, table):
    codecs = (codecs or '').lower()
    for prefix, label in table:
        if codecs.startswith(prefix):
            return label
    return codecs.split('.')[0]


def _channels(elems):
    # AudioChannelConfiguration (MPEG-DASH count, CICP index, Dolby channel mask) -> '5.1', '7.1', 'Nch' or ''
    for e in elems:
        scheme = (e.get('schemeIdUri') or '').lower()
        value = (e.get('value') or '').strip()
        count = 0
        if 'dolby' in scheme:
            try:
                count = bin(int(value, 16)).count('1')
            except Exception:
                count = 0
        elif 'cicp' in scheme:
            count = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 8, 12: 8, 13: 24, 14: 8, 16: 10, 17: 12, 19: 12}.get(_toInt(value), 0)
        else:
            count = _toInt(value)
        if count:
            return {1: 'mono', 6: '5.1', 8: '7.1'}.get(count, '%dch' % count if count > 2 else '')
    return ''


def _accessTags(aset, forText=False):
    # Role / Accessibility -> tags like the HLS parser shows them ('AD', 'SDH', 'forced', 'commentary', ...)
    tags = []
    for e in _kids(aset, 'Role') + _kids(aset, 'Accessibility'):
        scheme = (e.get('schemeIdUri') or '').lower()
        value = (e.get('value') or '').lower()
        tag = ''
        if 'audiopurposecs' in scheme:
            # 2 = for the hard of hearing: on a subtitle track that is SDH, as the HLS list calls it
            tag = {'1': 'AD', '2': 'SDH' if forText else 'HoH'}.get(value, '')
        elif value == 'description':
            tag = 'AD'
        elif value in ('caption', 'captions') or (forText and value == 'enhanced-audio-intelligibility'):
            tag = 'SDH' if forText else ''
        elif value == 'forced-subtitle':
            tag = 'forced'
        elif value in ('commentary', 'dub', 'emergency', 'sign', 'enhanced-audio-intelligibility'):
            tag = value
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def _language(value):
    # "und" (undetermined), "zxx" (no linguistic content) and "mis" name no language
    value = (value or '').strip()
    return '' if value.lower() in ('und', 'zxx', 'mis', 'mul') else value


def _labelText(elem):
    # a Label that only repeats a code without language ("und": TV Trwam) is no label
    for lab in _kids(elem, 'Label'):
        text = _language(lab.text)
        if text:
            return text
    return ''


def _hdrTag(aset, rep, codecs):
    if _codecLabel(codecs, VIDEO_CODECS).endswith('DV'):
        return 'DV'
    for e in _kids(aset, 'EssentialProperty') + _kids(aset, 'SupplementalProperty') + _kids(rep, 'EssentialProperty') + _kids(rep, 'SupplementalProperty'):
        if 'transfercharacteristics' in (e.get('schemeIdUri') or '').lower():
            return {'16': 'HDR', '18': 'HLG'}.get((e.get('value') or '').strip(), '')
    return ''


def _segmentInfo(period, aset, rep):
    # how the segments are addressed (the innermost element wins, as the MPD inherits them)
    for elem in (rep, aset, period):
        for name in ('SegmentTemplate', 'SegmentList', 'SegmentBase'):
            if _kid(elem, name) is not None:
                return name
    return ''


def _baseUrl(baseUrl, elem):
    b = _kid(elem, 'BaseURL')
    if b is not None and (b.text or '').strip():
        return urljoin(baseUrl, b.text.strip())
    return baseUrl


def _periodTimes(root, periods):
    # (start, duration) of every period in seconds; a missing start follows the previous period
    mpdDuration = parseDuration(root.get('mediaPresentationDuration'), 0)
    times = []
    prevEnd = 0.0
    for p in periods:
        start = parseDuration(p.get('start'), prevEnd) if p.get('start') else prevEnd
        times.append([start, parseDuration(p.get('duration'), 0)])
        prevEnd = start + times[-1][1] if times[-1][1] else start
    for idx, t in enumerate(times):
        if not t[1]:
            if idx + 1 < len(times):
                t[1] = max(times[idx + 1][0] - t[0], 0)
            elif mpdDuration:
                t[1] = max(mpdDuration - t[0], 0)
    return times


def choosePeriod(root, periods, now=None):
    # the period to play: a live MPD the one running now, a static one the longest (the programme, not an ad break)
    if not periods:
        return -1
    times = _periodTimes(root, periods)
    if root.get('type') == 'dynamic':
        ast = parseDateTime(root.get('availabilityStartTime'), 0) or 0
        now = time.time() if now is None else now
        # none started yet ("starting soon"): the first one, it starts next
        best = 0
        for idx, (start, _duration) in enumerate(times):
            if ast + start <= now:
                best = idx
        return best
    best = 0
    for idx, (_start, duration) in enumerate(times):
        if duration > times[best][1]:
            best = idx
    return best


def subtitleKind(aset, rep):
    # how the segments of a text representation carry the subtitles: 'stpp' / 'wvtt' (fragmented MP4), 'vtt' /
    # 'ttml' (plain text segments), '' for none the player can show (image subtitles, CEA-608 ...)
    codecs = ((rep.get('codecs') or aset.get('codecs') or '')).lower()
    mime = (rep.get('mimeType') or aset.get('mimeType') or '').lower()
    if re.search(r'im[12]i', codecs):
        return ''
    if codecs.startswith('stpp'):
        return 'stpp'
    if codecs.startswith('wvtt'):
        return 'wvtt'
    if 'vtt' in mime:
        return 'vtt'
    if 'ttml' in mime:
        return 'ttml'
    return ''


def _segmentParams(period, aset, rep):
    # the SegmentTemplate / SegmentList of a representation, inherited Period -> AdaptationSet -> Representation:
    # (kind, attributes, SegmentTimeline element or None, [SegmentURL elements])
    kind, attrs, timeline, urls = '', {}, None, []
    for elem in (period, aset, rep):
        for name in ('SegmentTemplate', 'SegmentList'):
            seg = _kid(elem, name)
            if seg is None:
                continue
            kind = name
            attrs.update(seg.attrib)
            if _kid(seg, 'SegmentTimeline') is not None:
                timeline = _kid(seg, 'SegmentTimeline')
            if name == 'SegmentList':
                urls = _kids(seg, 'SegmentURL') or urls
            init = _kid(seg, 'Initialization')
            if init is not None:
                if init.get('sourceURL'):
                    attrs['initialization'] = init.get('sourceURL')
                if init.get('range'):
                    # the init bytes of the BaseURL file (or of its sourceURL)
                    attrs['initRange'] = init.get('range')
    return kind, attrs, timeline, urls


def _fillTemplate(template, rep, number=0, mediaTime=0):
    def repl(m):
        name, fmt = m.group(1), m.group(2)
        if not name:
            return '$'
        bandwidth = _toInt(rep.get('bandwidth'), None) if rep.get('bandwidth') else ''
        value = {'RepresentationID': rep.get('id') or '', 'Bandwidth': bandwidth, 'Number': number, 'Time': mediaTime}.get(name, '')
        if fmt and isinstance(value, int):
            try:
                return fmt % value
            except Exception:
                return str(value)
        return str(value)
    return re.sub(r'\$(RepresentationID|Bandwidth|Number|Time|)(%0\d+[dxX])?\$', repl, template)


MAX_SUBTITLE_SEGMENTS = 20000
# a download: 200000 segments of 2 s = 4.6 days
MAX_MEDIA_SEGMENTS = 200000


def _mpdBytes(data):
    # the MPD as bytes for ElementTree: bytes keep their own XML encoding declaration; a text already decoded loses
    # it (an ISO-8859-1 declaration on an encoded-again UTF-8 text would turn "Français" into "Fran?ais")
    if isinstance(data, bytes):
        return data.strip()
    data = re.sub(r'''^(\s*<\?xml[^>]*?)\s+encoding\s*=\s*["'][^"']*["']''', r'\1', data.lstrip(u'\ufeff'), count=1)
    return data.strip().encode('utf-8')


def _parseRoot(data):
    return ET.fromstring(_mpdBytes(data))


def _repBase(manifestUrl, root, period, aset, rep):
    # the BaseURL chain MPD -> Period -> AdaptationSet -> Representation
    return _baseUrl(_baseUrl(_baseUrl(_baseUrl(manifestUrl, root), period), aset), rep)


def _ceilDiv(value, step):
    # segments needed for a length: rounded up, a float rounding rest (8.0000001) is no extra segment
    return int(math.ceil(value / float(step) - 1e-9))


def _repSegments(root, periods, periodIdx, aset, rep, manifestUrl, limit):
    # the segments of one representation of a SegmentTemplate / SegmentList:
    # {'init': url, 'init_range', 'segments': [(url, byte range)], 'pto': seconds, 'timescale', 'counted'}
    # counted: the number of segments comes from the period length (rounded up - the last one may not exist)
    period = periods[periodIdx]
    base = _repBase(manifestUrl, root, period, aset, rep)
    kind, attrs, timeline, segUrls = _segmentParams(period, aset, rep)
    timescale = _toInt(attrs.get('timescale'), 1) or 1
    # presentationTimeOffset in ticks: as seconds and back a $Time$ could lose one (the first url a 404)
    ptoTicks = _toInt(attrs.get('presentationTimeOffset'))
    periodTicks = _periodTimes(root, periods)[periodIdx][1] * timescale
    init = urljoin(base, _fillTemplate(attrs['initialization'], rep)) if attrs.get('initialization') else ''
    ret = {'init': init or (base if attrs.get('initRange') else ''), 'init_range': attrs.get('initRange', ''), 'segments': [],
           'pto': ptoTicks / float(timescale), 'timescale': timescale, 'counted': False}
    segments = ret['segments']
    if kind == 'SegmentList':
        for seg in segUrls[:limit]:
            segments.append((urljoin(base, seg.get('media') or ''), seg.get('mediaRange') or ''))
        return ret
    media = attrs.get('media') or ''
    number = _toInt(attrs.get('startNumber'), 1)
    # endNumber (DASH 5th edition): the last segment of the period
    last = _toInt(attrs.get('endNumber')) or 0
    if timeline is not None:
        mediaTime = 0
        entries = _kids(timeline, 'S')
        for idx, s in enumerate(entries):
            if s.get('t'):
                mediaTime = _toInt(s.get('t'))
            duration = _toInt(s.get('d'))
            if duration <= 0:
                break
            repeat = _toInt(s.get('r'))
            if repeat < 0:
                # up to the next S (or the end of the period)
                nextT = entries[idx + 1].get('t') if idx + 1 < len(entries) else None
                end = _toInt(nextT) if nextT else ptoTicks + periodTicks
                repeat = max(_ceilDiv(end - mediaTime, duration) - 1, 0)
            for _r in range(repeat + 1):
                if last and number > last:
                    return ret
                segments.append((urljoin(base, _fillTemplate(media, rep, number, mediaTime)), ''))
                number += 1
                mediaTime += duration
                if len(segments) >= limit:
                    return ret
        return ret
    duration = _toInt(attrs.get('duration'))
    if duration <= 0 or periodTicks <= 0:
        return ret
    count = min(_ceilDiv(periodTicks, duration), limit)
    if last:
        count = min(count, max(last - number + 1, 0))
    else:
        ret['counted'] = True
    for idx in range(count):
        segments.append((urljoin(base, _fillTemplate(media, rep, number + idx, ptoTicks + idx * duration)), ''))
    return ret


def subtitleSegments(data, manifestUrl, periodIdx, setIdx, repIdx, repId=''):
    # the segments of a text representation (_repSegments: init url + byte range, [(url, byte range)], pto seconds,
    # timescale)
    root = _parseRoot(data)
    periods = _kids(root, 'Period')
    period = periods[periodIdx]
    sets = _kids(period, 'AdaptationSet')
    aset, rep = None, None
    for candidate in sets:
        for r in _kids(candidate, 'Representation'):
            if repId and r.get('id') == repId:
                aset, rep = candidate, r
    if rep is None:
        aset = sets[setIdx]
        rep = _kids(aset, 'Representation')[repIdx]
    return _repSegments(root, periods, periodIdx, aset, rep, manifestUrl, MAX_SUBTITLE_SEGMENTS)


def _selectReps(period, sel):
    # [(type, AdaptationSet, Representation)] of a selection (iptv_dash_sel); (type, None, None) for one not found
    sets = []
    for aset in _kids(period, 'AdaptationSet'):
        reps = _kids(aset, 'Representation')
        sets.append((aset, _setType(aset, reps), reps))
    chosen = []
    for ctype, idKey, idxKey in (('video', 'v', 'vi'), ('audio', 'a', 'ai')):
        if sel.get(idKey) or sel.get(idxKey):
            aset, rep = _findRep(sets, ctype, sel.get(idKey), sel.get(idxKey, ''), _toInt(sel.get('vh')) if ctype == 'video' else 0)
            chosen.append((ctype, aset, rep))
    return chosen


def downloadPlan(data, manifestUrl, sel):
    # what the DASH downloader (iptvdm/dashdownloader.py) loads for a VOD link with iptv_dash_sel:
    # {'duration': seconds, 'tracks': [{'type': 'video' / 'audio', 'id', 'lang', 'init': (url, byte range) or None,
    #   'segments': [(url, byte range)], 'single': a SegmentBase / plain BaseURL file, 'counted'}]}
    # ValueError for a live MPD, a missing or DRM representation
    root = _parseRoot(data)
    if root.get('type') == 'dynamic':
        raise ValueError('live MPD')
    periods = _kids(root, 'Period')
    pIdx = choosePeriod(root, periods)
    if pIdx < 0:
        raise ValueError('no period')
    period = periods[pIdx]
    tracks = []
    for ctype, aset, rep in _selectReps(period, _parseSel(sel)):
        if rep is None:
            raise ValueError('no %s representation' % ctype)
        if _kids(aset, 'ContentProtection') or _kids(rep, 'ContentProtection'):
            raise ValueError('DRM')
        track = {'type': ctype, 'id': rep.get('id') or '', 'lang': _language(rep.get('lang')) or _language(aset.get('lang')),
                 'init': None, 'single': False, 'counted': False}
        if _segmentInfo(period, aset, rep) in ('SegmentTemplate', 'SegmentList'):
            seg = _repSegments(root, periods, pIdx, aset, rep, manifestUrl, MAX_MEDIA_SEGMENTS)
            if not seg['segments']:
                raise ValueError('no %s segments' % ctype)
            if seg['init']:
                track['init'] = (seg['init'], seg['init_range'])
            track['segments'] = seg['segments']
            track['counted'] = seg['counted']
        else:
            # SegmentBase or a BaseURL only: one file (init and index inside)
            track['segments'] = [(_repBase(manifestUrl, root, period, aset, rep), '')]
            track['single'] = True
        tracks.append(track)
    if not tracks:
        raise ValueError('nothing selected')
    return {'duration': _periodTimes(root, periods)[pIdx][1], 'tracks': tracks}


def parseMpd(data, manifestUrl, now=None):
    # -> {'dynamic', 'period', 'video': [...], 'audio': [...], 'text': [...], 'drm_only'}
    root = _parseRoot(data)
    if _local(root.tag) != 'MPD':
        raise ValueError('not an MPD')
    periods = _kids(root, 'Period')
    pIdx = choosePeriod(root, periods, now)
    ret = {'dynamic': root.get('type') == 'dynamic', 'period': pIdx, 'periods': len(periods), 'video': [], 'audio': [], 'text': [], 'drm_only': False}
    if pIdx < 0:
        return ret
    period = periods[pIdx]
    rootBase = _baseUrl(manifestUrl, root)
    periodBase = _baseUrl(rootBase, period)
    drmSkipped = 0
    for aIdx, aset in enumerate(_kids(period, 'AdaptationSet')):
        reps = _kids(aset, 'Representation')
        ctype = _setType(aset, reps)
        if ctype not in ('video', 'audio', 'text'):
            continue
        setBase = _baseUrl(periodBase, aset)
        setDrm = bool(_kids(aset, 'ContentProtection'))
        lang = _language(aset.get('lang'))
        label = _labelText(aset)
        tags = _accessTags(aset, ctype == 'text')
        for rIdx, rep in enumerate(reps):
            drm = setDrm or bool(_kids(rep, 'ContentProtection'))
            codecs = rep.get('codecs') or aset.get('codecs') or ''
            item = {'id': rep.get('id') or '', 'sel': '%d.%d' % (aIdx, rIdx), 'set': aIdx, 'bandwidth': _toInt(rep.get('bandwidth')),
                    'codecs': codecs, 'lang': _language(rep.get('lang')) or lang, 'label': _labelText(rep) or label, 'tags': list(tags), 'drm': drm}
            if ctype == 'video':
                item['codec'] = _codecLabel(codecs, VIDEO_CODECS)
                item['width'] = _toInt(rep.get('width') or aset.get('width') or aset.get('maxWidth'))
                item['height'] = _toInt(rep.get('height') or aset.get('height') or aset.get('maxHeight'))
                item['frame_rate'] = _frameRate(rep.get('frameRate') or aset.get('frameRate') or '')
                item['hdr'] = _hdrTag(aset, rep, codecs)
            elif ctype == 'audio':
                item['codec'] = _codecLabel(codecs, AUDIO_CODECS)
                item['channels'] = _channels(_kids(rep, 'AudioChannelConfiguration') or _kids(aset, 'AudioChannelConfiguration'))
                for prop in _kids(aset, 'SupplementalProperty') + _kids(rep, 'SupplementalProperty'):
                    if 'ec3_extensiontype' in (prop.get('schemeIdUri') or '').lower() and (prop.get('value') or '').upper() == 'JOC':
                        item['channels'] = 'Atmos'
            else:
                if _segmentInfo(period, aset, rep) in ('SegmentTemplate', 'SegmentList'):
                    # segmented subtitles (VOD): the local server joins the segments to one WebVTT (subtitleKind);
                    # image subtitles (IMSC1 im1i / im2i) and live tracks are left out
                    kind = subtitleKind(aset, rep)
                    if not kind or drm or ret['dynamic']:
                        continue
                    item.update({'segmented': kind, 'format': 'vtt', 'rep': rIdx})
                    ret[ctype].append(item)
                    continue
                if _kid(rep, 'BaseURL') is None and _kid(aset, 'BaseURL') is None:
                    continue
                url = _baseUrl(setBase, rep)
                ext = url.split('?', 1)[0].rsplit('.', 1)[-1].lower()
                mime = (rep.get('mimeType') or aset.get('mimeType') or '').lower()
                fmt = SUB_EXTENSIONS.get(ext) or ('vtt' if 'vtt' in mime else 'ttml' if 'ttml' in mime else '')
                if not fmt or drm:
                    continue
                item.update({'url': url, 'format': fmt})
            if drm and ctype != 'text':
                drmSkipped += 1
                continue
            ret[ctype].append(item)
    ret['drm_only'] = bool(drmSkipped) and not ret['video'] and not ret['audio']
    return ret


###################################################
# the "Select link" items
###################################################
def _audioName(audio):
    # label / language, codec, channels, AD ...; a track without language and label shows its codec only
    name = audio['label'] or audio['lang'] or ''
    for tag in [audio['lang'] if audio['label'] and audio['lang'] and audio['lang'].lower() not in audio['label'].lower().split() else '',
                audio['codec'], audio.get('channels', '')] + audio['tags']:
        if tag and tag.lower() not in name.lower().split():
            name = (name + ' ' + tag).strip()
    return name or 'audio'


def _videoName(video, bandwidth):
    name = 'bitrate: %s res: %dx%d %s' % (bandwidth, video['width'], video['height'], video['codec'])
    if video['hdr'] and video['hdr'] != 'DV':
        name += ' ' + video['hdr']
    if video['frame_rate']:
        name += ' %gfps' % video['frame_rate']
    if video['label']:
        name += ' ' + video['label']
    return name


def _audioTracks(audios):
    # one entry per audio AdaptationSet (its best representation) - the other bitrates of a track are the same audio
    best = {}
    order = []
    for a in audios:
        if a['set'] not in best:
            order.append(a['set'])
            best[a['set']] = a
        elif a['bandwidth'] > best[a['set']]['bandwidth']:
            best[a['set']] = a

    def isMain(a):
        return 0 if not (set(a['tags']) & set(('AD', 'commentary', 'dub'))) else 1
    return sorted((best[s] for s in order), key=isMain)


def buildLinks(mpd, manifestUrl):
    # list of dicts like the old getMPDLinksWithMeta: name, url, bandwidth, bitrate, codecs, width, height,
    # frame_rate, lang, livestream (+ the subtitle files of the period in the url meta)
    live = mpd['dynamic']
    subs = []
    for s in mpd['text']:
        # a segmented track: the WebVTT the local server joins from its segments
        url = localSubtitleUrl(manifestUrl, mpd['period'], s) if s.get('segmented') else s['url']
        if url:
            subs.append({'title': ' '.join([s['label'] or s['lang'] or 'subtitle'] + [t for t in s['tags'] if t]), 'url': url, 'lang': s['lang'], 'format': s['format']})
    meta = {'iptv_proto': 'mpd', 'iptv_livestream': live}
    if subs:
        meta['external_sub_tracks'] = list(strwithmeta(manifestUrl).meta.get('external_sub_tracks', [])) + subs
    videos = sorted(mpd['video'], key=lambda v: (v['codec'] in UNDECODABLE, -v['height'], -v['bandwidth']))
    links = []
    if videos:
        audios = _audioTracks(mpd['audio']) or [None]
        for audio in audios:
            for video in videos:
                bandwidth = video['bandwidth'] + (audio['bandwidth'] if audio else 0)
                name = _videoName(video, bandwidth)
                sel = 'v=%s|vi=%s|vh=%d' % (quote(video['id'], safe=''), video['sel'], video['height'])
                codecs = video['codec']
                lang = ''
                if audio:
                    name = '[%s] %s' % (_audioName(audio), name)
                    sel += '|a=%s|ai=%s' % (quote(audio['id'], safe=''), audio['sel'])
                    codecs = audio['codec'] + ',' + codecs
                    lang = audio['lang']
                linkMeta = dict(meta, iptv_dash_sel=sel)
                if video['frame_rate']:
                    # the player info bar takes it when exteplayer3 reports nonsense (200 fps for a 1/200 time base)
                    linkMeta['iptv_frame_rate'] = video['frame_rate']
                links.append({'name': name, 'url': strwithmeta(manifestUrl, linkMeta), 'bandwidth': bandwidth, 'bitrate': bandwidth,
                              'codecs': codecs, 'width': video['width'], 'height': video['height'], 'frame_rate': video['frame_rate'],
                              'lang': lang, 'livestream': live, 'undecodable': video['codec'] in UNDECODABLE})
    else:
        for audio in sorted(mpd['audio'], key=lambda a: -a['bandwidth']):
            name = '[%s] bitrate: %s audio only' % (_audioName(audio), audio['bandwidth'])
            sel = 'a=%s|ai=%s' % (quote(audio['id'], safe=''), audio['sel'])
            links.append({'name': name, 'url': strwithmeta(manifestUrl, dict(meta, iptv_dash_sel=sel)), 'bandwidth': audio['bandwidth'],
                          'bitrate': audio['bandwidth'], 'codecs': audio['codec'], 'lang': audio['lang'], 'livestream': live})
    return links


###################################################
# the filtered MPD
###################################################
def _parseSel(sel):
    ret = {}
    for part in (sel or '').split('|'):
        if '=' in part:
            key, value = part.split('=', 1)
            ret[key] = unquote(value)
    return ret


_etLock = threading.Lock()


def _register_namespaces(data):
    # keep the prefixes of the document (ElementTree would write ns0:, ns1:) - the MPD namespace stays the default one
    # (dashdec does not know "ns0:MPD"; ElementTree's default_namespace option refuses the MPD's plain attributes)
    ET.register_namespace('', MPD_NS)
    for _event, (prefix, uri) in ET.iterparse(io.BytesIO(data), events=('start-ns',)):
        if uri == MPD_NS:
            continue
        if not prefix or re.match(r'^ns\d+$', prefix):
            prefix = 'x' + hashlib.md5(uri.encode('utf-8')).hexdigest()[:6]
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass


def _repHeight(aset, rep):
    return _toInt(rep.get('height') or aset.get('height'))


def _findRep(sets, ctype, wantId, wantIdx, wantHeight=0):
    # (set, representation) of a selection: by Representation@id, else by position (when that one still has the
    # chosen height); a live MPD that moved on to another period (ad break) has other ids - the video closest to the
    # chosen height then (one every box decodes before VP9 / AV1 / DV of the same height), else the first one
    if wantId:
        for aset, setType, reps in sets:
            for rep in reps:
                if setType == ctype and rep.get('id') == wantId:
                    return aset, rep
    candidates = [(aset, rep) for aset, setType, reps in sets if setType == ctype for rep in reps]
    try:
        aIdx, rIdx = [int(x) for x in wantIdx.split('.', 1)]
        aset, setType, reps = sets[aIdx]
        if setType == ctype and rIdx < len(reps) and (not wantHeight or _repHeight(aset, reps[rIdx]) == wantHeight):
            return aset, reps[rIdx]
    except (ValueError, IndexError):
        pass
    if wantHeight and candidates:
        def closest(c):
            undecodable = _codecLabel(c[1].get('codecs') or c[0].get('codecs'), VIDEO_CODECS) in UNDECODABLE
            return (abs(_repHeight(c[0], c[1]) - wantHeight), undecodable, -_toInt(c[1].get('bandwidth')))
        return min(candidates, key=closest)
    if candidates and wantIdx:
        return candidates[0]
    return None, None


def _normaliseLiveNumbers(period, periodStart):
    # dashdec counts the live segment number from availabilityStartTime only: a period start (its own @start or the
    # one that follows from the periods before, _periodTimes) and a presentationTimeOffset are moved into
    # startNumber (SegmentTemplate with @duration and $Number$, its attributes inherited Period -> AdaptationSet ->
    # Representation); the numbers are worked out first and set after, an inherited template is changed once
    top = _kid(period, 'SegmentTemplate')
    updates = {}
    for aset in _kids(period, 'AdaptationSet'):
        setTmpl = _kid(aset, 'SegmentTemplate')
        for rep in _kids(aset, 'Representation') or [None]:
            chain = [t for t in (top, setTmpl, _kid(rep, 'SegmentTemplate') if rep is not None else None) if t is not None]
            if not chain or any(_kid(t, 'SegmentTimeline') is not None for t in chain):
                continue
            attrs = {}
            for t in chain:
                attrs.update(t.attrib)
            if '$Number' not in attrs.get('media', ''):
                continue
            try:
                duration = float(attrs.get('duration') or 0)
            except ValueError:
                # a broken @duration ("PT2S"): this template stays as it is, not the whole MPD a 502
                continue
            if duration <= 0 or (not periodStart and not attrs.get('presentationTimeOffset')):
                continue
            timescale = _toInt(attrs.get('timescale'), 1) or 1
            # rounded down: a number too low is a segment that exists, one too high is "425 Too Early"
            number = int(math.floor(_toInt(attrs.get('startNumber'), 1) - periodStart * timescale / duration))
            updates[id(chain[-1])] = (chain[-1], number, chain)
    for tmpl, number, chain in updates.values():
        tmpl.set('startNumber', str(number))
        for t in chain:
            if 'presentationTimeOffset' in t.attrib:
                del t.attrib['presentationTimeOffset']
    if updates and periodStart:
        period.set('start', 'PT0S')


def _defaultStartNumber(period):
    # a $Number$ SegmentTemplate without startNumber starts at 1 (ISO/IEC 23009-1), dashdec counts from 0 and asks
    # for a segment that does not exist first (BBC test card: 000000.m4s 404 on every start) - set it on the
    # highest template of the chain Period -> AdaptationSet -> Representation, so the lower ones inherit it
    top = _kid(period, 'SegmentTemplate')
    for aset in _kids(period, 'AdaptationSet'):
        setTmpl = _kid(aset, 'SegmentTemplate')
        for rep in _kids(aset, 'Representation') or [None]:
            chain = [t for t in (top, setTmpl, _kid(rep, 'SegmentTemplate') if rep is not None else None) if t is not None]
            if not chain or any(t.get('startNumber') for t in chain):
                continue
            if '$Number' in ''.join(t.get('media') or '' for t in chain):
                chain[0].set('startNumber', '1')


def filterMpd(data, manifestUrl, sel, now=None, clockOffset=0, startDelay=0):
    # the MPD with only the chosen period and representations, an absolute BaseURL and the dashdec workarounds;
    # clockOffset = server time - receiver time (from the Date header of the MPD response); startDelay = seconds
    # a live start moves further behind the edge (buffering)
    # ElementTree's namespace prefixes are one map for the whole process: two MPD requests at once (player and
    # downloader) must not change it under each other
    with _etLock:
        return _filterMpd(_mpdBytes(data), manifestUrl, sel, (time.time() if now is None else now) + clockOffset, clockOffset, startDelay)


def _filterMpd(data, manifestUrl, sel, now, clockOffset, startDelay):
    _register_namespaces(data)
    root = ET.fromstring(data)
    ns = root.tag.split('}', 1)[0] + '}' if root.tag.startswith('{') else ''
    periods = _kids(root, 'Period')
    pIdx = choosePeriod(root, periods, now)
    times = _periodTimes(root, periods)
    for idx, p in enumerate(periods):
        if idx != pIdx:
            root.remove(p)
    period = periods[pIdx]
    keep = dict((id(aset), rep) for _ctype, aset, rep in _selectReps(period, _parseSel(sel)) if aset is not None)
    for aset in _kids(period, 'AdaptationSet'):
        rep = keep.get(id(aset))
        if rep is None:
            period.remove(aset)
            continue
        for other in _kids(aset, 'Representation'):
            if other is not rep:
                aset.remove(other)
    for elem in _kids(period, 'EventStream'):
        period.remove(elem)
    if root.get('type') != 'dynamic':
        # (live: counting from 0 only keeps the start one segment further from the edge - left as it is)
        _defaultStartNumber(period)
    # one absolute BaseURL on the MPD level (the period / set / representation ones stay relative to it)
    bases = _kids(root, 'BaseURL')
    base = urljoin(manifestUrl, bases[0].text.strip()) if bases and (bases[0].text or '').strip() else urljoin(manifestUrl, './')
    for elem in bases + _kids(root, 'Location') + _kids(root, 'PatchLocation'):
        root.remove(elem)
    pos = 0
    for idx, child in enumerate(list(root)):
        if _local(child.tag) == 'ProgramInformation':
            pos = idx + 1
    baseElem = ET.Element(ns + 'BaseURL')
    baseElem.text = base
    root.insert(pos, baseElem)
    if root.get('type') == 'dynamic':
        ast = parseDateTime(root.get('availabilityStartTime'), 0) or 0
        if ast == 0 and 'publishTime' in root.attrib:
            del root.attrib['publishTime']
        maxSegment = parseDuration(root.get('maxSegmentDuration'), 0) or 2
        if not root.get('suggestedPresentationDelay'):
            root.set('suggestedPresentationDelay', 'PT%dS' % max(10, int(3 * maxSegment + 0.999)))
        _normaliseLiveNumbers(period, times[pIdx][0])
        # dashdec takes the receiver clock (no UTCTiming) and reads up to the segment that is still being written
        # (livesim: 425 "Too Early", after 100 of them it gives up): the start one segment + 1 s later, a
        # receiver clock that is wrong corrected
        newAst = int(round(ast - clockOffset + int(maxSegment + 0.999) + 1))
        if startDelay:
            # buffering: so many seconds more behind the live edge, read at once by ffmpeg (-readrate_initial_burst) -
            # within what the server keeps (timeShiftBufferDepth, two segments to spare)
            depth = parseDuration(root.get('timeShiftBufferDepth'), 0)
            if depth:
                startDelay = min(startDelay, max(0, int(depth - 3 * maxSegment - 1)))
            newAst += startDelay
        root.set('availabilityStartTime', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(newAst)))
    elif len(periods) > 1:
        # a static MPD keeps one period: its own length is the length of the programme now
        period.set('start', 'PT0S')
        if times[pIdx][1]:
            period.set('duration', 'PT%.3fS' % times[pIdx][1])
            root.set('mediaPresentationDuration', 'PT%.3fS' % times[pIdx][1])
    return ET.tostring(root, encoding='unicode')


###################################################
# local MPD server
###################################################
_lock = threading.Lock()
_server = None
_entries = {}
MAX_ENTRIES = 128
# MPDs read by getMPDLinksWithMeta: url -> (time, final url, data); a static one is served from here
_manifests = {}
MANIFEST_CACHE_SIZE = 16
MANIFEST_CACHE_TIME = 4 * 3600
# subtitle segments fetched at the same time; a blank line after so many seconds without data (wget of the subtitle
# download gives up after 20 s); a run stops after so many failed segments in a row
SUBTITLE_WORKERS = 6
SUBTITLE_KEEPALIVE = 5
SUBTITLE_MAX_FAILED_IN_ROW = 10


def rememberManifest(url, finalUrl, data, dynamic):
    with _lock:
        _manifests[str(url)] = (time.time(), finalUrl, data, dynamic)
        if len(_manifests) > MANIFEST_CACHE_SIZE:
            oldest = sorted(_manifests, key=lambda k: _manifests[k][0])[:len(_manifests) - MANIFEST_CACHE_SIZE]
            for key in oldest:
                _manifests.pop(key, None)


def _headersFromMeta(meta):
    return dict((k, meta[k]) for k in HTTP_HEADERS if meta.get(k))


def openUrl(url, headers, byteRange='', timeout=15, gzipOk=False):
    # a GET with the link's headers (+ Range "first-last"), as the DASH downloader asks too
    hdr = {'User-Agent': 'Mozilla/5.0'}
    if gzipOk:
        hdr['Accept-Encoding'] = 'gzip'
    hdr.update(headers)
    if byteRange:
        hdr['Range'] = 'bytes=' + byteRange
    # like pCommon on the box: no certificate check (many images ship no CA bundle)
    ctx = ssl._create_unverified_context()  # NOSONAR - same as the plugin's other requests, receivers lack CA certificates
    return urlopen(Request(url, headers=hdr), timeout=timeout, context=ctx)


READ_BLOCK = 64 * 1024


def readRange(resp, byteRange):
    # the body of an answer to openUrl(byteRange): a 206 must hold the whole range (a short one is an error, not a
    # segment); a server that ignores Range (200) sends the file from its start - only up to the range is read
    if not byteRange:
        return resp.read()
    first, last = byteRange.split('-', 1)
    first = int(first)
    wanted = int(last) - first + 1 if last else None
    if resp.status == 206:
        data = resp.read()
        if wanted is not None and len(data) != wanted:
            raise IOError('short range answer: %d of %d bytes' % (len(data), wanted))
        return data
    skipped = 0
    while skipped < first:
        block = resp.read(min(READ_BLOCK, first - skipped))
        if not block:
            raise IOError('file shorter than the range %s' % byteRange)
        skipped += len(block)
    return resp.read(wanted) if wanted is not None else resp.read()


def _fetch(url, headers, byteRange=''):
    resp = openUrl(url, headers, byteRange, gzipOk=not byteRange)
    try:
        data = readRange(resp, byteRange)
        if resp.headers.get('Content-Encoding', '').lower() == 'gzip':
            data = gzip.decompress(data)
        return resp.geturl(), data, _clockOffset(resp.headers.get('Date'))
    finally:
        resp.close()


def _clockOffset(dateHeader):
    # server time - receiver time from an HTTP Date header (1 s resolution: smaller differences count as 0)
    try:
        offset = parsedate_to_datetime(dateHeader).timestamp() - time.time()
        return offset if abs(offset) >= 2 else 0
    except Exception:
        return 0


def _manifestFor(entry):
    url = entry['url']
    with _lock:
        cached = _manifests.get(url)
    if cached and not cached[3] and time.time() - cached[0] < MANIFEST_CACHE_TIME:
        return cached[1], cached[2]
    if entry.get('last') and time.time() - entry.get('lastTime', 0) < 1:
        # dashdec asks again after every segment it could not open: not more than once a second to the site
        return entry['last']
    try:
        finalUrl, data, offset = _fetch(url, entry['headers'])
        # the first offset stays: the Date header has 1 s steps, a new one each refresh moved the live start back and
        # forth by up to 2 s
        entry.setdefault('offset', offset)
        entry['last'] = (finalUrl, data)
        entry['lastTime'] = time.time()
        return finalUrl, data
    except Exception:
        printExc()
        # a live refresh that failed: the last copy (dashdec asks again), else the one of the link list
        if entry.get('last'):
            return entry['last']
        if cached:
            return cached[1], cached[2]
        raise


def linkHeaders(url):
    # the http headers of a link's meta, for requests of its own (the DASH downloader)
    return _headersFromMeta(getattr(url, 'meta', {}) or {})


def fetchManifest(url):
    # (final url, MPD) of a link: the copy getMPDLinksWithMeta read (static MPD), else fetched again
    return _manifestFor({'url': str(url), 'headers': linkHeaders(url)})


class _Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def log_message(self, *args):
        pass

    def do_GET(self):
        token = self.path.split('?', 1)[0].rsplit('/', 1)[-1].split('.', 1)[0]
        with _lock:
            entry = _entries.get(token)
        if not entry:
            self.send_error(404)
            return
        if entry.get('kind') == 'sub':
            self._serveSubtitle(entry)
            return
        try:
            finalUrl, data = _manifestFor(entry)
            body = filterMpd(data, finalUrl, entry['sel'], clockOffset=entry.get('offset', 0), startDelay=entry.get('delay', 0)).encode('utf-8')
        except Exception:
            printExc()
            self.send_error(502)
            return
        try:
            self.send_response(200)
            self.send_header('Content-Type', 'application/dash+xml')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            printDBG('dashmpd: MPD request closed by the player')

    def _write(self, text):
        self.wfile.write(text.encode('utf-8'))
        self.wfile.flush()

    def _startVtt(self, length=None):
        self.send_response(200)
        self.send_header('Content-Type', 'text/vtt; charset=utf-8')
        if length is not None:
            self.send_header('Content-Length', str(length))
        self.end_headers()

    def _serveSubtitle(self, entry):
        # the WebVTT of a segmented text track: the cues are written while the segments come in; a finished text is
        # kept for the next request, a second request while the first still loads waits for that one (no second run)
        try:
            with _lock:
                job = entry.get('job')
                own = not entry.get('vtt') and job is None
                if own:
                    job = entry['job'] = threading.Event()
                    # a run before with failed segments left its numbers: not shown as "done" for this one
                    entry['progress'] = None
            if entry.get('vtt'):
                body = entry['vtt'].encode('utf-8')
                self._startVtt(len(body))
                self.wfile.write(body)
                return
            if not own:
                self._startVtt()
                self._write('WEBVTT\n\n')
                while not job.wait(SUBTITLE_KEEPALIVE):
                    self._write('\n')
                if entry.get('vtt'):
                    self._write(entry['vtt'][len('WEBVTT\n\n'):])
                return
            try:
                self._loadSubtitle(entry)
            finally:
                with _lock:
                    entry['job'] = None
                job.set()
        except OSError:
            printDBG('dashmpd: subtitle request closed by the player')

    def _loadSubtitle(self, entry):
        try:
            finalUrl, data = _manifestFor(entry)
            seg = subtitleSegments(data, finalUrl, entry['period'], entry['set'], entry['rep'], entry['id'])
        except Exception:
            printExc()
            self.send_error(502)
            return
        segments = seg['segments']
        if not segments:
            self.send_error(404)
            return
        from Plugins.Extensions.IPTVPlayer.libs import dashsubs
        kind, timescale, defaultDuration = entry['sub'], seg['timescale'], 0
        if kind in ('stpp', 'wvtt') and seg['init']:
            try:
                initData = _fetch(seg['init'], entry['headers'], seg['init_range'])[1]
                timescale = dashsubs.mdhdTimescale(initData, timescale)
                # sample durations of fragments that give none of their own (tfhd / trun) come from the init's trex
                defaultDuration = dashsubs.trexDefaultDuration(initData)
            except Exception:
                printExc()
        printDBG('dashmpd: subtitles %s [%s]: %d segments, timescale %s' % (kind, entry['url'], len(segments), timescale))
        self._startVtt()
        parts = ['WEBVTT\n\n']
        self._write(parts[0])
        joiner = dashsubs.CueJoiner()

        def fetch(item):
            try:
                return _fetch(item[0], entry['headers'], item[1])[1]
            except Exception:
                printDBG('dashmpd: subtitle segment failed [%s]' % item[0])
                return None
        executor = ThreadPoolExecutor(max_workers=SUBTITLE_WORKERS)
        # segments done / all of them, for the progress of the subtitle download window (subtitleProgress)
        progress = entry['progress'] = [0, len(segments)]
        pending = deque()
        nextIdx = failed = failedInRow = 0
        try:
            while nextIdx < len(segments) or pending:
                while nextIdx < len(segments) and len(pending) < 2 * SUBTITLE_WORKERS:
                    pending.append(executor.submit(fetch, segments[nextIdx]))
                    nextIdx += 1
                future = pending.popleft()
                while True:
                    try:
                        segment = future.result(timeout=SUBTITLE_KEEPALIVE)
                        break
                    except FutureTimeout:
                        # a slow segment or a long stretch without cues: a blank line, wget gives up after 20 s
                        # without any data
                        self._write('\n')
                progress[0] += 1
                if segment is None:
                    failed += 1
                    failedInRow += 1
                    if failedInRow >= SUBTITLE_MAX_FAILED_IN_ROW:
                        # the token expired / the site refuses: not all the other segments too
                        printDBG('dashmpd: subtitles stopped after %d failed segments in a row' % failedInRow)
                        break
                    continue
                failedInRow = 0
                try:
                    text = joiner.feed(dashsubs.segmentCues(segment, kind, timescale, seg['pto'], defaultDuration))
                except Exception:
                    printExc()
                    continue
                if text:
                    parts.append(text)
                    self._write(text)
            text = joiner.close()
            parts.append(text)
            self._write(text)
            printDBG('dashmpd: subtitles done, %d cues, %d segments failed' % (joiner.count, failed))
            if joiner.count and not failed:
                entry['vtt'] = ''.join(parts)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


def _startServer():
    global _server
    if _server is None:
        server = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, name='E2iDashMpd')
        thread.daemon = True
        thread.start()
        _server = server
        printDBG('dashmpd: local MPD server on 127.0.0.1:%d' % server.server_address[1])
    return _server


def _register(token, entry):
    with _lock:
        # registered again: its runtime state (last MPD, clock offset, loaded text) stays, and it moves to the end of
        # the order - the entries dropped first are the ones not used for longest, not a running live MPD
        old = _entries.pop(token, None)
        if old is not None:
            old.update(entry)
            entry = old
        _entries[token] = entry
        if len(_entries) > MAX_ENTRIES:
            for key in list(_entries)[:len(_entries) - MAX_ENTRIES]:
                _entries.pop(key, None)
        return _startServer()


def localSubtitleUrl(manifestUrl, periodIdx, track):
    # http://127.0.0.1:<port>/dash/<token>.vtt: the WebVTT of a segmented text track of a VOD MPD, None if the local
    # server cannot be started
    if not str(manifestUrl).startswith(('http://', 'https://')):
        return None
    meta = getattr(manifestUrl, 'meta', {}) or {}
    token = hashlib.md5(('%s\n%s\n%s\n%s' % (manifestUrl, periodIdx, track['sel'], track['id'])).encode('utf-8')).hexdigest()[:20]
    try:
        server = _register(token, {'kind': 'sub', 'url': str(manifestUrl), 'headers': _headersFromMeta(meta), 'period': periodIdx,
                                   'set': track['set'], 'rep': track['rep'], 'id': track['id'], 'sub': track['segmented']})
        return 'http://127.0.0.1:%d/dash/%s.vtt' % (server.server_address[1], token)
    except Exception:
        printExc()
        return None


def isLocalSubtitleUrl(url):
    url = str(url).split('?', 1)[0]
    return url.startswith('http://127.0.0.1:') and '/dash/' in url and url.endswith('.vtt')


def subtitleProgress(url):
    # (segments done, all segments) of a local .vtt of localSubtitleUrl being written, None for any other url or
    # before its segment list is known
    if not isLocalSubtitleUrl(url):
        return None
    token = str(url).split('?', 1)[0].rsplit('/', 1)[-1].split('.', 1)[0]
    with _lock:
        entry = _entries.get(token)
    if not entry:
        return None
    if entry.get('vtt'):
        return (1, 1)
    progress = entry.get('progress')
    return (progress[0], progress[1]) if progress and progress[1] else None


def localManifestUrl(url, startDelay=0):
    # http://127.0.0.1:<port>/dash/<token>.mpd serving the filtered MPD of a link with iptv_dash_sel, None if it
    # cannot be served (the caller plays the original url then); startDelay: a live start that many seconds further
    # behind the edge (filterMpd)
    meta = getattr(url, 'meta', {}) or {}
    sel = meta.get('iptv_dash_sel')
    if not sel or not str(url).startswith(('http://', 'https://')):
        return None
    token = hashlib.md5(('%s\n%s%s' % (url, sel, '\n%d' % startDelay if startDelay else '')).encode('utf-8')).hexdigest()[:20]
    try:
        server = _register(token, {'url': str(url), 'sel': sel, 'headers': _headersFromMeta(meta), 'delay': startDelay})
        local = 'http://127.0.0.1:%d/dash/%s.mpd' % (server.server_address[1], token)
        printDBG('dashmpd: %s -> %s [%s]' % (url, local, sel))
        return local
    except Exception:
        printExc()
        return None
