# -*- coding: utf-8 -*-
# Added: 26.10.2026 - segmented DASH subtitles to one WebVTT text (libs/dashmpd.py serves it on 127.0.0.1 as an
# ordinary .vtt subtitle file)
#
# The segments of a DASH text track are fragmented MP4 (ISO/IEC 14496-30): "stpp" carries one TTML document per
# sample, "wvtt" WebVTT cue boxes (vttc / payl / sttg); some MPDs list plain WebVTT or TTML files as segments. This
# module reads the boxes (moof / traf / tfhd / tfdt / trun, mdat), the TTML times and the WebVTT cues and writes
# the cues of all segments as one WebVTT text. No enigma2 / plugin imports (tests/test_dashsubs.py).
###################################################
# FOREIGN import
###################################################
import re
import struct
import xml.etree.ElementTree as ET
###################################################

MAX_SAMPLE_SIZE = 4 * 1024 * 1024


###################################################
# ISO base media file format
###################################################
def boxesAt(data, start=0, end=None):
    # (type, box start, payload start, box end) of the boxes between start and end
    end = len(data) if end is None else end
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack('>I4s', data[pos:pos + 8])
        head = 8
        if size == 1:
            if pos + 16 > end:
                return
            size = struct.unpack('>Q', data[pos + 8:pos + 16])[0]
            head = 16
        elif size == 0:
            size = end - pos
        if size < head or pos + size > end:
            return
        yield kind.decode('latin-1'), pos, pos + head, pos + size
        pos += size


def boxes(data, start=0, end=None):
    # (type, payload start, box end) of the boxes between start and end
    for kind, _bstart, pstart, pend in boxesAt(data, start, end):
        yield kind, pstart, pend


def _find(data, path, start=0, end=None):
    # the first box along path ('moov/trak/mdia/mdhd') -> (payload start, end) or None
    first, _sep, rest = path.partition('/')
    for kind, pstart, pend in boxes(data, start, end):
        if kind == first:
            return _find(data, rest, pstart, pend) if rest else (pstart, pend)
    return None


def mdhdTimescale(init, default=0):
    # the media timescale of the (first) track of an init segment
    try:
        box = _find(init, 'moov/trak/mdia/mdhd')
        if not box:
            return default
        pos = box[0]
        version = init[pos]
        return struct.unpack('>I', init[pos + (20 if version == 1 else 12):pos + (24 if version == 1 else 16)])[0] or default
    except Exception:
        return default


def trexDefaultDuration(init):
    # default_sample_duration of the (first) trex box of an init segment (moov/mvex/trex), 0 when there is none -
    # fragments that give no duration in tfhd or trun use it
    try:
        box = _find(init, 'moov/mvex/trex')
        if not box:
            return 0
        # version / flags, track_ID, default_sample_description_index, default_sample_duration
        return struct.unpack('>I', init[box[0] + 12:box[0] + 16])[0]
    except Exception:
        return 0


def fragmentSamples(data, defaultDuration=0):
    # the samples of a media segment: [(decode time in timescale units, duration, sample bytes)]; defaultDuration
    # from the init segment's trex
    samples = []
    nextTime = 0
    for kind, moofStart, mstart, mend in boxesAt(data):
        if kind != 'moof':
            continue
        # without data_offset the sample data follows the moof in its mdat, one traf after the other
        nextData = None
        for tkind, tstart, tend in boxes(data, mstart, mend):
            if tkind != 'traf':
                continue
            baseOffset = moofStart
            # a fragment without tfdt goes on where the one before ended
            baseTime = nextTime
            duration = defaultDuration
            size = 0
            runs = []
            for bkind, bstart, _bend in boxes(data, tstart, tend):
                version = data[bstart]
                flags = struct.unpack('>I', b'\x00' + data[bstart + 1:bstart + 4])[0]
                pos = bstart + 4
                if bkind == 'tfhd':
                    pos += 4  # track_ID
                    if flags & 0x01:
                        baseOffset = struct.unpack('>Q', data[pos:pos + 8])[0]
                        pos += 8
                    if flags & 0x02:
                        pos += 4
                    if flags & 0x08:
                        duration = struct.unpack('>I', data[pos:pos + 4])[0]
                        pos += 4
                    if flags & 0x10:
                        size = struct.unpack('>I', data[pos:pos + 4])[0]
                        pos += 4
                elif bkind == 'tfdt':
                    baseTime = struct.unpack('>Q' if version == 1 else '>I', data[pos:pos + (8 if version == 1 else 4)])[0]
                elif bkind == 'trun':
                    count = struct.unpack('>I', data[pos:pos + 4])[0]
                    pos += 4
                    dataOffset = None
                    if flags & 0x01:
                        dataOffset = struct.unpack('>i', data[pos:pos + 4])[0]
                        pos += 4
                    if flags & 0x04:
                        pos += 4
                    entries = []
                    for _idx in range(count):
                        entry = [None, None]
                        if flags & 0x100:
                            entry[0] = struct.unpack('>I', data[pos:pos + 4])[0]
                            pos += 4
                        if flags & 0x200:
                            entry[1] = struct.unpack('>I', data[pos:pos + 4])[0]
                            pos += 4
                        if flags & 0x400:
                            pos += 4
                        if flags & 0x800:
                            pos += 4
                        entries.append(entry)
                    runs.append((dataOffset, entries))
            # the sample data: at moof (or base_data_offset) + data_offset, else right after the moof in the mdat
            mdat = None
            for kind2, pstart2, pend2 in boxes(data, mend):
                if kind2 == 'mdat':
                    mdat = (pstart2, pend2)
                    break
            sampleTime = baseTime
            dataPos = None
            for dataOffset, entries in runs:
                if dataOffset is not None:
                    dataPos = baseOffset + dataOffset
                elif dataPos is None:
                    dataPos = nextData if nextData is not None else (mdat[0] if mdat else mend)
                for sampleDuration, sampleSize in entries:
                    sampleDuration = duration if sampleDuration is None else sampleDuration
                    sampleSize = size if sampleSize is None else sampleSize
                    if not sampleSize and len(entries) == 1 and mdat:
                        sampleSize = mdat[1] - dataPos
                    if sampleSize < 0 or sampleSize > MAX_SAMPLE_SIZE or dataPos + sampleSize > len(data):
                        # a broken size: the rest of this run is not read (it would be cut or another sample's data)
                        break
                    samples.append((sampleTime, sampleDuration, data[dataPos:dataPos + sampleSize]))
                    dataPos += sampleSize
                    sampleTime += sampleDuration
            nextData = dataPos
            nextTime = sampleTime
    return samples


###################################################
# cues
###################################################
def wvttCues(sample, start, end):
    # the cues of one wvtt sample (vttc boxes; vtte = an empty sample): [(start, end, text, settings)]
    cues = []
    for kind, pstart, pend in boxes(sample):
        if kind != 'vttc':
            continue
        text = settings = ''
        for ckind, cstart, cend in boxes(sample, pstart, pend):
            if ckind == 'payl':
                text = sample[cstart:cend].decode('utf-8', 'replace')
            elif ckind == 'sttg':
                settings = sample[cstart:cend].decode('utf-8', 'replace')
        if text.strip():
            cues.append((start, end, text.strip('\n'), settings.strip()))
    return cues


def _local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _ttmlAttr(root, name):
    for key, value in root.attrib.items():
        if _local(key) == name:
            return value
    return None


def _ttmlParam(root, name, default):
    try:
        return float(_ttmlAttr(root, name))
    except (TypeError, ValueError):
        return default


def ttmlRates(root):
    # (frames per second, ticks per second) of a TTML document: frameRate x frameRateMultiplier ("1000 1001" for
    # 29.97); without tickRate the ticks are frameRate x subFrameRate when a frameRate is given (TTML 1, ttp:tickRate)
    frameRate = _ttmlParam(root, 'frameRate', 0)
    multiplier = (_ttmlAttr(root, 'frameRateMultiplier') or '').split()
    if frameRate and len(multiplier) == 2:
        try:
            frameRate = frameRate * float(multiplier[0]) / float(multiplier[1])
        except (ValueError, ZeroDivisionError):
            pass
    tickRate = _ttmlParam(root, 'tickRate', 0)
    if not tickRate:
        tickRate = frameRate * _ttmlParam(root, 'subFrameRate', 1) if frameRate else 1.0
    return frameRate or 30.0, tickRate


def ttmlTime(value, frameRate=30.0, tickRate=1.0):
    # TTML time expression -> seconds (None when there is none)
    value = (value or '').strip()
    if not value:
        return None
    m = re.match(r'^(\d+):(\d\d):(\d\d(?:\.\d+)?)$', value)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.match(r'^(\d+):(\d\d):(\d\d):(\d+(?:\.\d+)?)$', value)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + float(m.group(4)) / (frameRate or 30.0)
    m = re.match(r'^(\d+(?:\.\d+)?)(h|ms|m|s|f|t)$', value)
    if m:
        number = float(m.group(1))
        return {'h': number * 3600, 'm': number * 60, 's': number, 'ms': number / 1000.0,
                'f': number / (frameRate or 30.0), 't': number / (tickRate or 1.0)}[m.group(2)]
    return None


# a <br/> of TTML text: the only line break - line breaks of the XML source are whitespace (xml:space="default")
_BR = '\x1e'


def _cleanText(text):
    # TTML text is plain text: "<" / ">" in it would read as WebVTT tags (the player's parser drops "<...>" with the
    # text between) - the look-alike angle quotes instead; the player does not decode &lt; either
    lines = [re.sub(r'\s+', ' ', line).strip().replace('<', u'\u2039').replace('>', u'\u203a') for line in text.split(_BR)]
    return '\n'.join(line for line in lines if line)


def ttmlCues(document):
    # the cues of one TTML document: [(start, end, text, '')] in seconds of the document's own timeline
    if isinstance(document, bytes):
        document = document.decode('utf-8', 'replace')
    document = document.lstrip(u'\ufeff').strip()
    if not document:
        return []
    root = ET.fromstring(document.encode('utf-8'))
    frameRate, tickRate = ttmlRates(root)
    cues = []

    def times(elem, offset, parentEnd):
        # (begin, end) of an element: its begin / end / dur count from its parent's begin (offset); without a begin
        # it starts with its parent, without end and dur it ends with it (TTML's "par" timing)
        begin = ttmlTime(elem.get('begin'), frameRate, tickRate)
        end = ttmlTime(elem.get('end'), frameRate, tickRate)
        dur = ttmlTime(elem.get('dur'), frameRate, tickRate)
        begin = offset + (begin or 0)
        if end is not None:
            end = offset + end
        elif dur is not None:
            end = begin + dur
        else:
            end = parentEnd
        if parentEnd is not None and end is not None:
            end = min(end, parentEnd)
        return begin, end

    def paragraphCues(para, offset, parentEnd):
        # a <p> whose <span>s have times of their own shows a line that grows ("C", "C, D", ...): one cue per stretch
        # of time with the text of the pieces visible then, in document order (span times count from their parent and
        # stay inside it)
        begin, end = times(para, offset, parentEnd)
        pieces = []

        def collect(node, nbegin, nend):
            if node.text:
                pieces.append((node.text, nbegin, nend))
            for child in node:
                if _local(child.tag) == 'br':
                    pieces.append((_BR, nbegin, nend))
                else:
                    cbegin, cend = times(child, nbegin, nend)
                    collect(child, max(cbegin, nbegin), cend)
                if child.tail:
                    pieces.append((child.tail, nbegin, nend))
        collect(para, begin, end)
        ends = [e for _t, _b, e in pieces if e is not None]
        if not ends:
            # neither the paragraph, its parents nor a span says when it ends
            return
        last = end if end is not None else max(ends)
        pieces = [(t, b, last if e is None else e) for t, b, e in pieces]
        points = sorted(set([b for _t, b, _e in pieces] + [e for _t, _b, e in pieces]))
        for start, stop in zip(points, points[1:]):
            text = _cleanText(''.join(t for t, b, e in pieces if b <= start and e >= stop))
            if not text:
                continue
            if cues and cues[-1][2] == text and abs(cues[-1][1] - start) < 0.001:
                cues[-1] = (cues[-1][0], stop, text, '')
            else:
                cues.append((start, stop, text, ''))

    def walk(elem, offset, parentEnd):
        if _local(elem.tag) == 'p':
            paragraphCues(elem, offset, parentEnd)
            return
        begin, end = times(elem, offset, parentEnd)
        for child in elem:
            walk(child, begin, end)
    walk(root, 0.0, None)
    return cues


_VTT_TIME = r'(?:(\d+):)?(\d\d):(\d\d)[.,](\d{1,3})'


def _vttSeconds(groups):
    hours, minutes, seconds, millis = groups
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis.ljust(3, '0')) / 1000.0


def vttTextCues(text):
    # the cues of a WebVTT (or SRT) text: [(start, end, text, settings)]
    if isinstance(text, bytes):
        text = text.decode('utf-8', 'replace')
    text = text.replace(u'\ufeff', '').replace('\r\n', '\n').replace('\r', '\n')
    cues = []
    for block in re.split(r'\n[ \t]*\n', text):
        lines = block.strip('\n').split('\n')
        for idx, line in enumerate(lines):
            m = re.match(r'^\s*' + _VTT_TIME + r'\s*-->\s*' + _VTT_TIME + r'(.*)$', line)
            if m:
                body = '\n'.join(lines[idx + 1:]).strip('\n')
                if body.strip():
                    cues.append((_vttSeconds(m.groups()[0:4]), _vttSeconds(m.groups()[4:8]), body, m.group(9).strip()))
                break
    return cues


def segmentCues(data, kind, timescale, ptoSeconds=0.0, defaultDuration=0):
    # the cues of one media segment in presentation seconds; kind 'stpp' / 'wvtt' (fragmented MP4) or 'vtt' / 'ttml'
    # (a plain text segment, its times are presentation times already); defaultDuration: trex of the init segment
    if kind == 'vtt':
        return vttTextCues(data)
    if kind == 'ttml':
        return ttmlCues(data)
    timescale = float(timescale or 1000)
    cues = []
    for sampleTime, duration, sample in fragmentSamples(data, defaultDuration):
        start = sampleTime / timescale
        end = (sampleTime + duration) / timescale
        if kind == 'wvtt':
            cues.extend((s - ptoSeconds, e - ptoSeconds, text, settings) for s, e, text, settings in wvttCues(sample, start, end))
            continue
        if not sample.strip():
            continue
        try:
            sampleCues = ttmlCues(sample)
        except Exception:
            continue
        # TTML times count from the start of the media timeline (ISO/IEC 14496-30), some packagers count from the
        # sample: cues that only fit into the sample when shifted by its start are shifted - not when one of them
        # already lies in the sample as it is (the repeated tail of a line from the segment before)
        relative = (start >= 1 and sampleCues and all(e <= (end - start) + 0.5 for _s, e, _t, _x in sampleCues)
                    and not any(s < end and e > start for s, e, _t, _x in sampleCues))
        shift = start if relative else 0.0
        for s, e, text, settings in sampleCues:
            # a TTML document holds for its sample only: a line that runs on is in the next segment again (CueJoiner
            # joins the two), without the cut both would show at once
            s, e = max(s + shift, start), min(e + shift, end) if duration else e + shift
            if e > s:
                cues.append((s - ptoSeconds, e - ptoSeconds, text, settings))
    return cues


###################################################
# WebVTT output
###################################################
def vttTime(seconds):
    millis = int(round(max(seconds, 0) * 1000))
    return '%02d:%02d:%02d.%03d' % (millis // 3600000, millis // 60000 % 60, millis // 1000 % 60, millis % 1000)


def vttCue(cue):
    start, end, text, settings = cue
    head = '%s --> %s' % (vttTime(start), vttTime(end))
    if settings:
        head += ' ' + settings
    # a blank line inside the text would end the cue there (a wvtt payload may hold one)
    text = '\n'.join(line for line in text.replace('-->', '->').split('\n') if line.strip())
    return '%s\n%s\n\n' % (head, text)


class CueJoiner(object):
    # the cues of the segments in order: one that runs on in the next segment (same text, touching) becomes one
    # cue, repeated ones go; feed() returns the WebVTT text of the cues that are complete
    def __init__(self):
        self.pending = []
        self.seen = set()
        self.count = 0

    def feed(self, cues):
        out = []
        for cue in sorted(cues, key=lambda c: (c[0], c[1])):
            start, end, text, settings = cue
            if end <= start:
                continue
            key = (round(start, 2), round(end, 2), text)
            if key in self.seen:
                continue
            self.seen.add(key)
            merged = False
            for idx, (pstart, pend, ptext, psettings) in enumerate(self.pending):
                if ptext == text and psettings == settings and pstart <= start <= pend + 0.05:
                    self.pending[idx] = (pstart, max(pend, end), ptext, psettings)
                    merged = True
                    break
            if not merged:
                self.pending.append(cue)
        # cues that ended before the last start of this segment cannot grow any more - written in start order, so
        # only up to the first one that still can
        if cues:
            last = max(c[0] for c in cues)
            self.pending.sort(key=lambda c: (c[0], c[1]))
            while self.pending and self.pending[0][1] < last:
                out.append(self.pending.pop(0))
        self.count += len(out)
        return ''.join(vttCue(c) for c in out)

    def close(self):
        out = sorted(self.pending, key=lambda c: (c[0], c[1]))
        self.pending = []
        self.count += len(out)
        return ''.join(vttCue(c) for c in out)
