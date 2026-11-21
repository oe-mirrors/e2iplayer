# -*- coding: utf-8 -*-
# IPTV download manager API
# # added: 07.08.2026 - Shared helpers for Downloader: Py2/Py3 safe text & path handling, shell quoting, and the sidecar, (.txt description + .jpg poster). - Kamikaze24
# 21.11.2026 - H264_FIX_OPTS / h264FixRefused(): downloads of "Constrained High" H.264 play on the boxes;
#   fixMkvH264Header(): an MKV with each SPS / PPS twice in its H.264 header plays in the Enigma2 media player.
# 15.11.2026 - ffmpeg's output of the subtitle mux goes to <name>.iptv.subs.log, printed to the debug log when the mux
#   fails and always removed.
# 12.10.2026 - subtitles of the link saved with a download (name.de.srt) or put into its MKV (setting "Subtitles").
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback, GetNice, E2PrioFix, GetTmpDir, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
###################################################
# FOREIGN import
###################################################
from Tools.BoundFunction import boundFunction
from Components.config import config
from enigma import eConsoleAppContainer
import os
import re
import signal
import struct
import threading
import time
import zlib
###################################################

try:
    text_type = unicode
    binary_type = str
    string_types = (basestring,)
except NameError:
    text_type = str
    binary_type = bytes
    string_types = (str, bytes)

# H.264 whose SPS sets constraint_set4 + constraint_set5 ("Constrained High", BongaCams rooms ...): the Broadcom
# decoders of the boxes give sound without a picture. ffmpeg's h264_metadata filter (ffmpeg 5.0+) sets both flags to 0
# in the copy - a rewrite of the stream headers, no re-encoding. ffmpeg stops at once on other video codecs (HEVC ...)
# and older builds do not know the option: the run goes again without it (h264FixRefused)
H264_FIX_OPTS = ('-bsf:v', 'h264_metadata=zero_new_constraint_set_flags=1')


def h264FixRefused(text):
    # ffmpeg's output: "... is not supported by the bitstream filter 'h264_metadata'", "Error initializing bitstream
    # filter", "Option zero_new_constraint_set_flags not found"
    text = ensureText(text or '')
    return 'bitstream filter' in text or 'zero_new_constraint_set_flags' in text


# Matroska element ids read by fixMkvH264Header()
_MKV_SEGMENT, _MKV_TRACKS, _MKV_CLUSTER = 0x18538067, 0x1654AE6B, 0x1F43B675
_MKV_TRACKENTRY, _MKV_CODECID, _MKV_CODECPRIVATE, _MKV_CRC32, _MKV_VOID = 0xAE, 0x86, 0x63A2, 0xBF, 0xEC
_MKV_HEAD_BYTES = 1048576


def _ebmlVint(buf, pos, maxLen):
    # (value without the length marker, length, all value bits set = unknown size)
    first = buf[pos]
    length = 1
    mask = 0x80
    while length <= maxLen and not first & mask:
        mask >>= 1
        length += 1
    if length > maxLen or pos + length > len(buf):
        raise ValueError('bad EBML number at %d' % pos)
    value = first & (mask - 1)
    for i in range(1, length):
        value = (value << 8) | buf[pos + i]
    return value, length, value == (1 << (7 * length)) - 1


def _ebmlElement(buf, pos):
    # (id with its marker, start of the data, size of the data or -1 when unknown)
    _unused, idLen, _unused = _ebmlVint(buf, pos, 4)
    elementId = 0
    for i in range(idLen):
        elementId = (elementId << 8) | buf[pos + i]
    size, sizeLen, unknown = _ebmlVint(buf, pos + idLen, 8)
    return elementId, pos + idLen + sizeLen, -1 if unknown else size


def _ebmlSizeField(value, length):
    # the EBML size field of the given length
    out = bytearray(length)
    value |= 1 << (7 * length)
    for i in range(length - 1, -1, -1):
        out[i] = value & 0xFF
        value >>= 8
    return out


def _dedupeAvcC(data):
    # AVCDecoderConfigurationRecord with each SPS / PPS once, None when it has no duplicates or is not one
    if len(data) < 7 or data[0] != 1:
        return None
    pos = 6
    groups = []
    for count in (data[5] & 0x1F, None):
        if count is None:
            if pos >= len(data):
                return None
            count = data[pos]
            pos += 1
        units = []
        for _unused in range(count):
            if pos + 2 > len(data):
                return None
            length = (data[pos] << 8) | data[pos + 1]
            unit = bytes(data[pos + 2:pos + 2 + length])
            if len(unit) != length:
                return None
            if unit not in units:
                units.append(unit)
            pos += 2 + length
        groups.append((count, units))
    if all(count == len(units) for count, units in groups):
        return None
    out = bytearray(data[:5])
    out.append(0xE0 | len(groups[0][1]))
    for unit in groups[0][1]:
        out += bytearray(((len(unit) >> 8) & 0xFF, len(unit) & 0xFF)) + bytearray(unit)
    out.append(len(groups[1][1]))
    for unit in groups[1][1]:
        out += bytearray(((len(unit) >> 8) & 0xFF, len(unit) & 0xFF)) + bytearray(unit)
    # the extension of the High profiles (chroma format, bit depth, SPS ext) stays as it is
    out += data[pos:]
    return out


def fixMkvH264Header(filePath):
    # An encoder that sends every SPS / PPS twice in front of a key frame (BongaCams rooms ...): ffmpeg puts both
    # copies into the H.264 header of an MKV (CodecPrivate), and the dvbvideosink of the boxes rejects it ("codec_data
    # too short", Enigma2 media player without a picture, box test 21.11.2026). Each SPS / PPS once again, in place:
    # the bytes set free become an EBML Void element, so no size or offset in the file changes; a CRC-32 of the
    # Tracks element is written again. Only touches the file when there are duplicates. Returns True when it did.
    try:
        path = fsPath(filePath)
        if not str(path).lower().endswith('.mkv') or not os.path.isfile(path):
            return False
        with open(path, 'rb') as f:
            buf = bytearray(f.read(_MKV_HEAD_BYTES))
        elementId, pos, size = _ebmlElement(buf, 0)
        pos += size  # EBML header
        elementId, pos, size = _ebmlElement(buf, pos)
        if elementId != _MKV_SEGMENT:
            return False
        segmentEnd = len(buf) if size < 0 else min(len(buf), pos + size)
        tracks = None
        while pos < segmentEnd:
            elementId, dataPos, size = _ebmlElement(buf, pos)
            if elementId == _MKV_CLUSTER or size < 0:
                break
            if elementId == _MKV_TRACKS:
                tracks = (dataPos, size)
                break
            pos = dataPos + size
        if tracks is None or tracks[0] + tracks[1] > len(buf):
            return False
        tracksPos, tracksSize = tracks
        tracksEnd = tracksPos + tracksSize
        changed = False
        crcPos = None
        pos = tracksPos
        while pos < tracksEnd:
            elementId, dataPos, size = _ebmlElement(buf, pos)
            if elementId == _MKV_CRC32 and size == 4:
                crcPos = dataPos
            elif elementId == _MKV_TRACKENTRY:
                codecId = b''
                private = None
                entryPos = dataPos
                while entryPos < dataPos + size:
                    childId, childData, childSize = _ebmlElement(buf, entryPos)
                    if childId == _MKV_CODECID:
                        codecId = bytes(buf[childData:childData + childSize])
                    elif childId == _MKV_CODECPRIVATE:
                        private = (entryPos, childData, childSize)
                    entryPos = childData + childSize
                if codecId.rstrip(b'\x00') == b'V_MPEG4/ISO/AVC' and private:
                    elementPos, privateData, privateSize = private
                    newData = _dedupeAvcC(buf[privateData:privateData + privateSize])
                    if newData is not None:
                        sizeLen = privateData - elementPos - 2
                        total = privateData + privateSize - elementPos
                        block = bytearray(b'\x63\xa2') + _ebmlSizeField(len(newData), sizeLen) + newData
                        free = total - len(block)
                        voidLen = 1
                        while voidLen < 8 and free - 1 - voidLen >= (1 << (7 * voidLen)) - 1:
                            voidLen += 1
                        if len(newData) >= (1 << (7 * sizeLen)) - 1 or free - 1 - voidLen < 0:
                            printDBG('fixMkvH264Header: no room for the Void element in %s' % filePath)
                        else:
                            block += bytearray((_MKV_VOID,)) + _ebmlSizeField(free - 1 - voidLen, voidLen) + bytearray(free - 1 - voidLen)
                            buf[elementPos:elementPos + total] = block
                            changed = True
            pos = dataPos + size
        if not changed:
            return False
        if crcPos is not None:
            buf[crcPos:crcPos + 4] = bytearray(struct.pack('<I', zlib.crc32(bytes(buf[crcPos + 4:tracksEnd])) & 0xFFFFFFFF))
        with open(path, 'r+b') as f:
            f.seek(tracksPos)
            f.write(bytes(buf[tracksPos:tracksEnd]))
        printDBG('fixMkvH264Header: SPS / PPS duplicates removed from the H.264 header of %s' % filePath)
        return True
    except Exception:
        printExc()
        return False


def fixMkvH264HeaderWhenDone(filePath, quietSecs=3, maxSecs=60):
    # A live recording stopped in the download manager: ffmpeg still writes the end of its MKV after that, the H.264
    # header included (box test 21.11.2026: a fix right away was gone again). The fix runs once the file has not
    # changed for quietSecs, in a thread of its own (only file access there).
    def _wait():
        try:
            path = fsPath(filePath)
            last = None
            quietSince = time.time()
            end = time.time() + maxSecs
            while time.time() < end:
                try:
                    st = os.stat(path)
                    state = (st.st_size, st.st_mtime)
                except OSError:
                    return
                if state != last:
                    last = state
                    quietSince = time.time()
                elif time.time() - quietSince >= quietSecs:
                    fixMkvH264Header(filePath)
                    return
                time.sleep(0.5)
            printDBG('fixMkvH264HeaderWhenDone: %s still changing after %d s, left as it is' % (filePath, maxSecs))
        except Exception:
            printExc()
    worker = threading.Thread(target=_wait, name='fixMkvH264Header')
    worker.daemon = True
    worker.start()
    return worker


def ensureText(data, encoding='utf-8'):
    if data is None:
        return u''

    if isinstance(data, text_type):
        return data

    if isinstance(data, binary_type):
        try:
            return data.decode(encoding)
        except Exception:
            try:
                return data.decode(encoding, 'replace')
            except Exception:
                try:
                    return data.decode('latin-1', 'replace')
                except Exception:
                    return u''

    try:
        return text_type(data)
    except Exception:
        try:
            return text_type(str(data))
        except Exception:
            return u''


def fsPath(path):
    path = ensureText(path)
    try:
        if text_type is not str:
            return path.encode('utf-8')
    except Exception:
        pass
    return path


def executeConsoleCmd(console, cmd):
    # start a command line on an eConsoleAppContainer, niced
    if hasattr(console, "setNice"):
        console.setNice(GetNice() + 2)
        console.execute(cmd)
    else:
        console.execute(E2PrioFix(cmd))


def terminateToolsOfFile(filePath, tools=('hlsdl', 'wget', 'curl', 'ffmpeg')):
    # Safety net for "Stop downloading". The download commands end in a redirect, so the console
    # runs them through a shell and its sendCtrlC() only reaches that shell: hlsdl / wget / curl /
    # ffmpeg can keep running and writing the file after the item shows "interrupted". So look
    # for the tool by its command line - it names the output file - and end it directly.
    killed = []
    try:
        needle = fsPath(filePath)
        if not isinstance(needle, binary_type):
            needle = needle.encode('utf-8', 'replace')
        toolNames = [t if isinstance(t, binary_type) else t.encode('utf-8') for t in tools]
        if not needle:
            return killed
        myPid = os.getpid()
        for entry in os.listdir('/proc'):
            if not entry.isdigit() or int(entry) == myPid:
                continue
            try:
                with open('/proc/%s/cmdline' % entry, 'rb') as f:
                    cmdline = f.read()
            except Exception:
                continue  # gone already, or not readable
            if needle in cmdline and any(name in cmdline for name in toolNames):
                try:
                    os.kill(int(entry), signal.SIGTERM)
                    killed.append(int(entry))
                except Exception:
                    pass
    except Exception:
        printExc()
    if killed:
        printDBG("terminateToolsOfFile ended pids %r for [%s]" % (killed, filePath))
    return killed


def shellQuote(value):
    value = ensureText(value)
    value = value.replace('\\', '\\\\')
    value = value.replace('"', '\\"')
    value = value.replace('`', '\\`')
    value = value.replace('$', '\\$')
    return value


def shellSingleQuote(value):
    # the whole value as one '...' shell word - nothing inside is interpreted by the shell
    return "'" + ensureText(value).replace("'", "'\\''") + "'"


def writeUtf8TextFile(path, data):
    try:
        txt = ensureText(data)
        f = open(fsPath(path), 'wb')
        try:
            f.write(txt.encode('utf-8'))
        finally:
            f.close()
        return True
    except Exception:
        printExc()
        return False


def readUtf8TextFile(path):
    try:
        f = open(fsPath(path), 'rb')
        try:
            data = f.read()
        finally:
            f.close()
        return ensureText(data)
    except Exception:
        return None


def filesAreIdentical(pathA, pathB):
    try:
        pathA = fsPath(pathA)
        pathB = fsPath(pathB)
        if not os.path.isfile(pathA) or not os.path.isfile(pathB):
            return False
        if os.path.getsize(pathA) != os.path.getsize(pathB):
            return False
        fa = open(pathA, 'rb')
        try:
            fb = open(pathB, 'rb')
            try:
                while True:
                    chunkA = fa.read(65536)
                    chunkB = fb.read(65536)
                    if chunkA != chunkB:
                        return False
                    if not chunkA:
                        return True
            finally:
                fb.close()
        finally:
            fa.close()
    except Exception:
        return False


def safeRemoveFile(path):
    try:
        path = fsPath(path)
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        printExc()


# language names and ISO 639-2 codes the hosts give their subtitle tracks -> ISO 639-1 (file name "name.de.srt")
SUBTITLE_LANG_NAMES = {'ger': 'de', 'deu': 'de', 'german': 'de', 'deutsch': 'de', 'eng': 'en', 'english': 'en',
                       'fre': 'fr', 'fra': 'fr', 'french': 'fr', u'fran\xe7ais': 'fr', 'francais': 'fr',
                       'spa': 'es', 'spanish': 'es', u'espa\xf1ol': 'es', 'espanol': 'es',
                       'ita': 'it', 'italian': 'it', 'italiano': 'it', 'pol': 'pl', 'polish': 'pl', 'polski': 'pl',
                       'ara': 'ar', 'arabic': 'ar', 'tur': 'tr', 'turkish': 'tr', u't\xfcrk\xe7e': 'tr', 'rus': 'ru',
                       'russian': 'ru', 'por': 'pt', 'portuguese': 'pt', u'portugu\xeas': 'pt', 'dut': 'nl', 'nld': 'nl',
                       'dutch': 'nl', 'cze': 'cs', 'ces': 'cs', 'czech': 'cs', 'hun': 'hu', 'hungarian': 'hu',
                       'gre': 'el', 'ell': 'el', 'greek': 'el', 'ukr': 'uk', 'ukrainian': 'uk', 'swe': 'sv',
                       'swedish': 'sv', 'nor': 'no', 'norwegian': 'no', 'dan': 'da', 'danish': 'da', 'fin': 'fi',
                       'finnish': 'fi', 'rum': 'ro', 'ron': 'ro', 'romanian': 'ro', 'bul': 'bg', 'bulgarian': 'bg',
                       'hrv': 'hr', 'croatian': 'hr', 'srp': 'sr', 'serbian': 'sr', 'heb': 'he', 'hebrew': 'he',
                       'jpn': 'ja', 'japanese': 'ja', 'kor': 'ko', 'korean': 'ko', 'chi': 'zh', 'zho': 'zh',
                       'chinese': 'zh', 'hin': 'hi', 'hindi': 'hi', 'per': 'fa', 'fas': 'fa', 'persian': 'fa'}
# ISO 639-1 -> the ISO 639-2 code Matroska expects in a track's language tag; also the 2-letter codes taken as a
# language at all ("CC", "HI" or "No subtitles" are none)
MKV_LANG_CODES = {'de': 'ger', 'en': 'eng', 'fr': 'fre', 'es': 'spa', 'it': 'ita', 'pl': 'pol', 'ar': 'ara',
                  'tr': 'tur', 'ru': 'rus', 'pt': 'por', 'nl': 'dut', 'cs': 'cze', 'hu': 'hun', 'el': 'gre',
                  'uk': 'ukr', 'sv': 'swe', 'no': 'nor', 'da': 'dan', 'fi': 'fin', 'ro': 'rum', 'bg': 'bul',
                  'hr': 'hrv', 'sr': 'srp', 'he': 'heb', 'ja': 'jpn', 'ko': 'kor', 'zh': 'chi', 'hi': 'hin',
                  'fa': 'per'}
# the extensions of the subtitles saved next to a download (the download manager removes / renames them with it)
SUBTITLE_SIDECAR_EXT = ('srt', 'ass')
_CUE_TIME = re.compile(r'(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})')
# every tag but <i> <b> <u> and their ends; <i.class> becomes <i>
_CUE_TAG = re.compile(r'<(?!/?[ibu]>)[^>]*>')
_CUE_CLASS = re.compile(r'<([ibu])\.[^>]*>')
_CUE_ENTITIES = (('&lt;', '<'), ('&gt;', '>'), ('&nbsp;', ' '), ('&lrm;', u'\u200e'), ('&rlm;', u'\u200f'), ('&amp;', '&'))


def subtitleLangCode(lang):
    # 'de' for "de", "de-DE", "ger", "German", "Deutsch (forced)", "Francais" ...; '' when unknown
    words = re.findall(r'[^\W\d_]+', ensureText(lang).lower(), re.U)
    if not words:
        return ''
    if len(words[0]) == 2:
        return words[0] if words[0] in MKV_LANG_CODES else ''
    return SUBTITLE_LANG_NAMES.get(words[0], '')


def pickSubtitleTracks(tracks, allLangs, wanted):
    # the external_sub_tracks ([{'title', 'lang', 'url'}]) to save: all of them, or those in the wanted languages
    # (in that order); when no track names a known language, all of them (mostly a single untitled track)
    usable = [t for t in (tracks or []) if isinstance(t, dict) and ensureText(t.get('url', '')).startswith(('http://', 'https://'))]
    if allLangs:
        return usable
    codes = [subtitleLangCode(t.get('lang', '')) or subtitleLangCode(t.get('title', '')) for t in usable]
    if not any(codes):
        return usable
    picked = []
    for want in wanted:
        for track, code in zip(usable, codes):
            if code == want and track not in picked:
                picked.append(track)
    return picked


# HLS subtitle tracks: getDirectM3U8Playlist() lists the SUBTITLES renditions of a master with the url of their
# media playlist (marked 'hls'), hosts sometimes as a plain .m3u8 link. The playlist names the .vtt segments; they
# are fetched where the track is used (player "Download suggested", subtitles of a download), in one wget run
# (-i list: one connection for all of them) and joined to one WebVTT text
_VTT_HEADER = re.compile(r'^WEBVTT(?:[ \t].*)?$')
_BOM = chr(0xFEFF)


def isHlsSubtitleTrack(track):
    # the playlist url of an HLS subtitle rendition, not a subtitle file
    try:
        if track.get('hls'):
            return True
        return ensureText(track.get('url', '')).split('?', 1)[0].split('#', 1)[0].lower().endswith('.m3u8')
    except Exception:
        return False


def hlsSubtitleSegmentUrls(data, playlistUrl):
    # the segment urls of an HLS subtitle media playlist (data: its text), absolute - relative ones against
    # playlistUrl - in order and each once (some playlists list one whole .vtt for every segment, or byte ranges
    # of one file: that file once). [] when data is no media playlist (a .vtt, an error page, a master)
    text = ensureText(data).lstrip(_BOM + u' \t\r\n')
    if not text.startswith(u'#EXTM3U'):
        return []
    try:
        from Plugins.Extensions.IPTVPlayer.libs import m3u8
        playlist = m3u8.inits(text, str(ensureText(playlistUrl)))
        if playlist.is_variant:
            return []
        urls = []
        seen = set()
        for segment in playlist.segments:
            url = segment.absolute_uri
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        return urls
    except Exception:
        printExc()
        return []


def joinWebVttSegments(parts):
    # one WebVTT text of the segments of an HLS subtitle playlist (a list of texts, or the file wget -O wrote them
    # all into): the first WEBVTT header block stays, the WEBVTT / X-TIMESTAMP-MAP headers and STYLE / REGION
    # blocks of the later segments go, the cues keep their order and one that spans a segment boundary (in both
    # segments) is kept once. X-TIMESTAMP-MAP is not applied: in VOD playlists it maps the cues to the MPEG-TS
    # time of the stream start (e.g. MPEGTS:900000,LOCAL:00:00:00.000 with the video PTS from 10 s), so the cue
    # times already count from the start of the video as the player does; a map that differs per segment (live
    # windows) stays unshifted
    if isinstance(parts, (list, tuple)):
        text = u'\n\n'.join(ensureText(part) for part in parts)
    else:
        text = ensureText(parts)
    text = text.replace(_BOM, u'').replace('\r\n', '\n').replace('\r', '\n')
    # a segment without a trailing blank line (or newline: "last cueWEBVTT"): the header of the next one still
    # starts a block of its own
    text = re.sub(r'(?<=[^\n])(?=WEBVTT\n)', '\n', text)
    text = re.sub(r'(?m)^(?=WEBVTT(?:[ \t]|$))', '\n', text)
    header = None
    blocks = []
    seen = set()
    for block in re.split(r'\n[ \t]*\n', text):
        block = block.strip('\n')
        if not block.strip():
            continue
        lines = block.split('\n')
        if _VTT_HEADER.match(lines[0]):
            if header is None:
                header = block
            continue
        if lines[0].split(' ', 1)[0] in ('STYLE', 'REGION') and '-->' not in block:
            if header is not None and not blocks:
                header += '\n\n' + block  # belongs between the header and the first cue
            continue
        timing = [idx for idx, line in enumerate(lines) if '-->' in line]
        key = '\n'.join(lines[timing[0]:] if timing else lines)  # timing and text, not the cue id (counted per segment)
        if key in seen:
            continue
        seen.add(key)
        blocks.append(block)
    out = ([header] if header is not None else []) + blocks
    return u'\n\n'.join(out) + u'\n' if out else u''


def hlsSubtitleWgetCmd(downloaderParams, listFile, outFile):
    # wget of all segment urls in listFile into the one file outFile (with -O wget appends them one after the other)
    from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
    return DMHelper.getBaseWgetCmd(downloaderParams) + ' -T 20 -t 2 -i "%s" -O "%s"' % (shellQuote(listFile), shellQuote(outFile))


def _srtTime(match):
    hours, minutes, seconds, millis = match.groups()
    return '%02d:%02d:%02d,%03d' % (int(hours or 0), int(minutes), int(seconds), int(millis.ljust(3, '0')))


def _cueLine(line):
    line = _CUE_TAG.sub('', _CUE_CLASS.sub(r'<\1>', line))
    for entity, char in _CUE_ENTITIES:  # &amp; last: "&amp;lt;" stays "&lt;"
        line = line.replace(entity, char)
    return line.strip()


def subtitleToSrt(text):
    # (text, ext) to save of a downloaded subtitle: WebVTT and SubRip become clean SubRip (numbered cues, comma
    # times, only <i>/<b>/<u> tags), ASS/SSA stays as it is; ('', '') for anything else (an error page)
    text = ensureText(text).lstrip(u'\ufeff').replace('\r\n', '\n').replace('\r', '\n')
    if '[Script Info]' in text[:300]:
        return text, 'ass'
    cues = []
    for block in re.split(r'\n[ \t]*\n', text):
        lines = block.strip('\n').split('\n')
        for idx, line in enumerate(lines):
            if '-->' in line:
                break
        else:
            continue  # WEBVTT header, NOTE / STYLE / REGION blocks
        times = list(_CUE_TIME.finditer(lines[idx]))
        cueText = [line for line in (_cueLine(line) for line in lines[idx + 1:]) if line]
        if len(times) < 2 or not cueText:
            continue
        cues.append('%d\n%s --> %s\n%s' % (len(cues) + 1, _srtTime(times[0]), _srtTime(times[1]), '\n'.join(cueText)))
    if not cues:
        return '', ''
    return '\n\n'.join(cues) + '\n', 'srt'


def decodeSubtitle(data, lang=''):
    # the bytes of a subtitle file as text: UTF-16 by its BOM, UTF-8, else the usual 8-bit code page of the language
    if data[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return data.decode('utf-16', 'replace')
    try:
        return data.decode('utf-8')
    except Exception:
        pass
    codePage = 'cp1250' if lang in ('pl', 'cs', 'hu', 'hr', 'ro') else 'cp1256' if lang in ('ar', 'fa') else 'cp1251' if lang in ('ru', 'uk', 'bg', 'sr') else 'cp1252'
    return data.decode(codePage, 'replace')


def subtitleSidecarFiles(basePath):
    # the subtitle files saved next to the download basePath (without extension), as _writeSubtitleFiles names
    # them: name.srt, name.2.srt, name.de.srt, name.de.2.srt - not "name.2023.srt" or "name.HD.srt" of another video
    found = []
    try:
        folder, name = os.path.split(ensureText(basePath))
        pattern = re.compile(r'^%s(?:\.[a-z]{2})?(?:\.(?:[2-9]|[1-9]\d))?\.(?:%s)$' % (re.escape(name), '|'.join(SUBTITLE_SIDECAR_EXT)))
        for entry in os.listdir(fsPath(folder or '.')):
            entry = ensureText(entry)
            if pattern.match(entry):
                found.append(os.path.join(folder, entry))
    except Exception:
        printExc()
    return sorted(found)


class SidecarMixin(object):
    """
    Shared .txt / .jpg sidecar handling plus the generic "finish download"
    flow, used identically by WgetDownloader, HLSDownloader and
    MergeDownloader.

    The including class must also inherit from BaseDownloader (for
    self.filePath, self.onFinish()) and must implement self._cleanUp()
    itself, since temp-file cleanup differs per downloader.

    Usage in each downloader's __init__:
        self._initSidecarState()

    Usage in each downloader's _terminate():
        self._terminateSidecar()
    """

    def _initSidecarState(self):
        self.sidecarConsole = None
        self.sidecarConsole_appClosed_conn = None
        self.sidecarConsole_stderrAvail_conn = None
        self.sidecarEnabled = False
        self.sidecarTxt = ''
        self.sidecarImg = ''
        self.waitingForSidecar = False
        self.sidecarImgTmpPath = ''
        self.sidecarMetaLock = threading.Lock()
        self.sidecarMetaState = {}
        # subtitles of the link (setting "Subtitles"): fetched to temp files while the file downloads
        self.subConsole = None
        self.subConsole_appClosed_conn = None
        self.subJobs = []  # [{'lang', 'title', 'tmp', 'url', 'params', 'hls'}]
        self.subFetching = False
        self.subHlsChecked = False  # the fetched files were checked for HLS subtitle playlists
        self.subWaiting = False  # the download is done and waits for the fetch
        self.subHandled = False
        self.subEmbedTmp = ''
        self.subEmbedFiles = []

    def _clearSidecarData(self):
        self.sidecarEnabled = False
        self.sidecarTxt = ''
        self.sidecarImg = ''
        self.waitingForSidecar = False
        self.sidecarMetaState = {}
        self._clearSubtitleData()

    def _prepareSidecarData(self, meta):
        self._clearSidecarData()
        try:
            if meta.get('e2i_sidecar_enabled', False):
                self.sidecarEnabled = True
                self.sidecarTxt = meta.get('e2i_sidecar_txt', '')
                self.sidecarImg = meta.get('e2i_sidecar_img', '')
                printDBG("%s sidecar enabled" % self.__class__.__name__)
                self._startSidecarMetaLookup(meta.get('e2i_sidecar_meta'))
        except Exception:
            printExc()
        self._startSubtitleFetch(meta)

    def _clearSubtitleData(self):
        # ends a running fetch / mux and removes its temp files. The console's Ctrl+C only reaches the shell around
        # wget / ffmpeg, so the tools are ended by their output file as well (terminateToolsOfFile)
        if self.subConsole is not None:
            try:
                self.subConsole_appClosed_conn = None
                if hasattr(self.subConsole, "sendCtrlC"):
                    self.subConsole.sendCtrlC()
                elif hasattr(self.subConsole, "kill"):
                    self.subConsole.kill()
            except Exception:
                printExc()
            self.subConsole = None
            for job in self.subJobs:
                terminateToolsOfFile(job['tmp'], ('wget',))
            if self.subEmbedTmp:
                terminateToolsOfFile(self.subEmbedTmp, ('ffmpeg',))
        for job in self.subJobs:
            safeRemoveFile(job['tmp'])
            safeRemoveFile(job['tmp'] + '.list')  # an HLS track's segment list (also one written only partly)
        if self.subEmbedTmp:
            safeRemoveFile(self.subEmbedTmp)
            safeRemoveFile(self._subEmbedLogPath(self.subEmbedTmp))
        self.subJobs = []
        self.subFetching = False
        self.subHlsChecked = False
        self.subWaiting = False
        self.subHandled = False
        self.subEmbedTmp = ''
        self.subEmbedFiles = []

    def _startSubtitleFetch(self, meta):
        # a real download only (the download manager sets allowFinalRename, buffered playback not): the tracks of the
        # wanted languages are fetched now with wget, in one console run while the file downloads - the links of a
        # site's subtitles often expire as the video link does. The video's User-Agent / Referer / Origin go along
        # (not its Host, Range, Cookie ...: the subtitles mostly sit on another server); the track's own headers win
        try:
            mode = config.plugins.iptvplayer.download_subtitles.value
            if mode == 'off' or not getattr(self, 'allowFinalRename', False):
                return
            tracks = pickSubtitleTracks(meta.get('external_sub_tracks'), config.plugins.iptvplayer.download_subtitles_lang.value == 'all', (GetDefaultLang(), 'en'))
            if not tracks:
                return
            from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
            videoHeaders = dict((key, meta[key]) for key in ('User-Agent', 'Referer', 'Origin') if meta.get(key))
            stamp = '%d_%d' % (int(time.time() * 1000), id(self) % 100000)
            cmds = []
            jobs = []
            for idx, track in enumerate(tracks):
                url, params = DMHelper.getDownloaderParamFromUrl(track['url'])
                params = dict(videoHeaders, **params)
                tmp = GetTmpDir('.e2i_dlsub_%s_%d' % (stamp, idx))
                cmds.append(DMHelper.getBaseWgetCmd(params) + ' -T 20 -t 2 "%s" -O "%s" > /dev/null 2>&1' % (shellQuote(url), shellQuote(tmp)))
                lang = subtitleLangCode(track.get('lang', '')) or subtitleLangCode(track.get('title', ''))
                # an HLS track's playlist lands in tmp first, its segments follow (_startHlsSubtitleSegments)
                jobs.append({'lang': lang, 'title': ensureText(track.get('title', '') or track.get('lang', '')), 'tmp': tmp,
                             'url': url, 'params': params, 'hls': False})
            printDBG("%s subtitles to fetch: %r" % (self.__class__.__name__, [(job['lang'], job['title']) for job in jobs]))
            console = eConsoleAppContainer()
            self.subConsole_appClosed_conn = eConnectCallback(console.appClosed, self._subtitleFetchFinished)
            self.subConsole = console
            executeConsoleCmd(console, ' ; '.join(cmds))
            # only a started fetch is waited for at the end of the download
            self.subJobs = jobs
            self.subFetching = True
        except Exception:
            printExc()
            self._clearSubtitleData()

    def _subtitleFetchFinished(self, code=None):
        printDBG("%s subtitle fetch finished code[%r]" % (self.__class__.__name__, code))
        self.subConsole_appClosed_conn = None
        self.subConsole = None
        if not self.subHlsChecked:
            self.subHlsChecked = True
            if self._startHlsSubtitleSegments():
                return
        self.subFetching = False
        if self.subWaiting:
            self.subWaiting = False
            self._finishDownloadFlow()

    def _startHlsSubtitleSegments(self):
        # a fetched file that is an HLS subtitle playlist (getDirectM3U8Playlist's SUBTITLES renditions, a host's
        # .m3u8 link): its segments are fetched into the same temp file in a second console run, joined in
        # _writeSubtitleFiles. True while that run goes
        try:
            cmds = []
            for job in self.subJobs:
                try:
                    with open(fsPath(job['tmp']), 'rb') as f:
                        head = f.read(16)
                        if b'#EXTM3U' not in head:
                            continue
                        data = head + f.read()
                except Exception:
                    continue
                urls = hlsSubtitleSegmentUrls(decodeSubtitle(data), job['url'])
                if not urls:
                    continue
                listFile = job['tmp'] + '.list'
                if writeUtf8TextFile(listFile, '\n'.join(urls) + '\n'):
                    job['hls'] = True
                    cmds.append(hlsSubtitleWgetCmd(job['params'], listFile, job['tmp']) + ' > /dev/null 2>&1')
                    printDBG("%s subtitle [%s]: HLS playlist, %d segments" % (self.__class__.__name__, job['title'], len(urls)))
            if not cmds:
                return False
            console = eConsoleAppContainer()
            self.subConsole_appClosed_conn = eConnectCallback(console.appClosed, self._subtitleFetchFinished)
            self.subConsole = console
            executeConsoleCmd(console, ' ; '.join(cmds))
            return True
        except Exception:
            printExc()
            return False

    def _subtitleStep(self):
        # True while the finish waits (for the fetch, or the MKV mux); it calls _finishDownloadFlow() again then
        if not self.subJobs or self.subHandled:
            return False
        from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
        if self.status != DMHelper.STS.DOWNLOADED:
            return False
        if self.subFetching:
            printDBG("%s download done, waiting for the subtitles" % self.__class__.__name__)
            self.subWaiting = True
            return True
        self.subHandled = True
        files = self._writeSubtitleFiles(self.filePath)
        if files and config.plugins.iptvplayer.download_subtitles.value == 'mkv' and ensureText(self.filePath).lower().endswith('.mkv'):
            return self._startSubtitleEmbed(files)
        return False

    def _writeSubtitleFiles(self, filePath):
        # name.de.srt next to the video (name.srt without a known language, name.de.2.srt for a second German track)
        base = ensureText(filePath).rsplit('.', 1)[0]
        written = []
        used = set()
        for job in self.subJobs:
            try:
                with open(fsPath(job['tmp']), 'rb') as f:
                    data = f.read()
            except Exception:
                data = b''
            text = decodeSubtitle(data, job['lang']) if data else ''
            if text and job.get('hls'):
                text = joinWebVttSegments(text)
            text, ext = subtitleToSrt(text) if text else ('', '')
            if not text:
                printDBG("%s subtitle [%s] skipped: no subtitle data (%d bytes)" % (self.__class__.__name__, job['title'], len(data)))
                continue
            name = base + ('.' + job['lang'] if job['lang'] else '')
            path = name + '.' + ext
            number = 2
            while path in used:
                path = '%s.%d.%s' % (name, number, ext)
                number += 1
            if writeUtf8TextFile(path, text):
                used.add(path)
                written.append({'path': path, 'lang': job['lang'], 'title': job['title']})
                printDBG("%s subtitle saved [%s]" % (self.__class__.__name__, path))
        return written

    def _startSubtitleEmbed(self, files):
        # the subtitles into the MKV (copy, no re-encoding): its own video / audio first, the new subtitles before
        # the ones it has already, so their numbers for the language tags are known. The status stays DOWNLOADED:
        # the video is complete, a stop now only ends the mux (_clearSubtitleData) and keeps the .srt files
        from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
        video = ensureText(self.filePath)
        self.subEmbedTmp = video.rsplit('.', 1)[0] + '.iptv.remux.tmp.mkv'
        self.subEmbedFiles = files
        count = len(files)
        cmd = DMHelper.GET_FFMPEG_PATH() + ' -y -nostdin -hide_banner -loglevel warning '
        for item in files:
            cmd += ' -i "%s" ' % shellQuote(item['path'])
        cmd += ' -i "%s" -map %d:v? -map %d:a? ' % (shellQuote(video), count, count)
        for idx in range(count):
            cmd += ' -map %d:0 ' % idx
        cmd += ' -map %d:s? -map %d:t? -map_metadata %d -map_chapters %d -c copy ' % (count, count, count, count)
        for idx, item in enumerate(files):
            if item['lang'] in MKV_LANG_CODES:  # Matroska wants ISO 639-2, an unknown code would read as "und"
                cmd += ' -metadata:s:s:%d language=%s ' % (idx, MKV_LANG_CODES[item['lang']])
            if item['title']:
                cmd += ' -metadata:s:s:%d title="%s" ' % (idx, shellQuote(item['title']))
        # ffmpeg's warnings / errors go to the debug log when the mux fails (_subtitleEmbedFinished)
        cmd += ' -f matroska "%s" >"%s" 2>&1 ' % (shellQuote(self.subEmbedTmp), shellQuote(self._subEmbedLogPath(self.subEmbedTmp)))
        printDBG("%s subtitle mux cmd[%s]" % (self.__class__.__name__, cmd))
        try:
            self.subConsole = eConsoleAppContainer()
            self.subConsole_appClosed_conn = eConnectCallback(self.subConsole.appClosed, self._subtitleEmbedFinished)
            executeConsoleCmd(self.subConsole, cmd)
        except Exception:
            printExc()
            self.subConsole = None
            self.subEmbedTmp = ''
            return False
        return True

    @staticmethod
    def _subEmbedLogPath(tmp):
        # ffmpeg's output of the subtitle mux, next to its temp file
        return ensureText(tmp).rsplit('.iptv.remux.tmp', 1)[0] + '.iptv.subs.log'

    def _subtitleEmbedFinished(self, code=None):
        from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
        self.subConsole_appClosed_conn = None
        self.subConsole = None
        tmp = self.subEmbedTmp
        self.subEmbedTmp = ''
        video = ensureText(self.filePath)
        size = DMHelper.getFileSize(fsPath(tmp))
        printDBG("%s subtitle mux finished code[%r] size[%r]" % (self.__class__.__name__, code, size))
        # the end of ffmpeg's output; the file is removed, it would stay next to the video otherwise
        muxLog = ''
        logPath = fsPath(self._subEmbedLogPath(tmp))
        try:
            if os.path.isfile(logPath):
                with open(logPath, 'rb') as f:
                    muxLog = ensureText(f.read())[-1500:].strip()
        except Exception:
            printExc()
        safeRemoveFile(logPath)
        # the muxed file holds the whole video: not (much) smaller than the downloaded one
        if code == 0 and size > 0 and size >= DMHelper.getFileSize(fsPath(video)) * 0.98:
            try:
                # over the video in one step (os.replace; Python 2 has os.rename, which replaces on POSIX too): a
                # failure leaves the downloaded video as it was
                getattr(os, 'replace', os.rename)(fsPath(tmp), fsPath(video))
                for item in self.subEmbedFiles:
                    safeRemoveFile(item['path'])
                self.localFileSize = size
                self.remoteFileSize = size
            except Exception:
                printExc()
        else:
            printDBG("%s subtitle mux failed, the subtitles stay next to the file, ffmpeg:\n%s" % (self.__class__.__name__, muxLog))
        safeRemoveFile(tmp)
        self.subEmbedFiles = []
        self._finishDownloadFlow()

    def _startSidecarMetaLookup(self, query):
        # e2i_sidecar_meta (urlmetahelper.sidecarMetaQuery): the moviemeta details (rating, genres, cast, plot,
        # poster) are looked up now, in a thread while the file downloads - not when the links are listed, so
        # playing costs no lookup. _writeTxtSidecar() takes the answer; one that comes after the download is done
        # rewrites the .txt itself. Each download gets its own state dict (a restart starts a new one).
        if not isinstance(query, dict) or not query:
            return
        state = {'result': None, 'txtPath': ''}
        self.sidecarMetaState = state
        siteTxt, siteImg, name, lock = self.sidecarTxt, self.sidecarImg, self.__class__.__name__, self.sidecarMetaLock

        def sidecarMetaLookup():
            from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import lookupSidecarMeta
            result = lookupSidecarMeta(query, siteTxt, siteImg)
            with lock:
                state['result'] = result
                txtPath = state['txtPath']
            if txtPath and result[0] and result[0] != siteTxt:
                # the download finished first: its .txt has the site text only
                if writeUtf8TextFile(txtPath, ensureText(result[0])):
                    printDBG("%s sidecar TXT rewritten with the moviemeta details [%s]" % (name, txtPath))

        printDBG("%s sidecar moviemeta lookup %r" % (name, query))
        # an E2iPlayer work thread (asynccall): pCommon's pycurl requests need its kill state, a plain thread's fail
        from Plugins.Extensions.IPTVPlayer.components.asynccall import AsyncMethod
        AsyncMethod(sidecarMetaLookup)()

    def _takeSidecarMetaResult(self, txtPath):
        # the moviemeta answer when it is there; else txtPath is noted for the thread's own rewrite
        state = self.sidecarMetaState
        if not state:
            return
        with self.sidecarMetaLock:
            result = state.get('result')
            if result is None:
                state['txtPath'] = txtPath
        if result is None:
            printDBG("%s sidecar moviemeta lookup still running, site text first" % self.__class__.__name__)
        else:
            self.sidecarTxt, self.sidecarImg = result

    def _writeTxtSidecar(self, filePath):
        # no sidecar for this download (covers, buffered playback): nothing to write and nothing to log
        if not self.sidecarEnabled:
            return
        try:
            self._takeSidecarMetaResult(ensureText(filePath).rsplit('.', 1)[0] + '.txt')
            if not self.sidecarTxt:
                printDBG("%s sidecar TXT skipped: empty content" % self.__class__.__name__)
                return

            basePath = ensureText(filePath).rsplit('.', 1)[0]
            txtPath = basePath + '.txt'
            newContent = ensureText(self.sidecarTxt)

            if os.path.isfile(fsPath(txtPath)):
                if readUtf8TextFile(txtPath) == newContent:
                    printDBG("%s sidecar TXT unchanged, skipping rewrite [%s]" % (self.__class__.__name__, txtPath))
                    return
                printDBG("%s sidecar TXT content changed, rewriting [%s]" % (self.__class__.__name__, txtPath))

            if writeUtf8TextFile(txtPath, newContent):
                printDBG("%s sidecar TXT saved [%s]" % (self.__class__.__name__, txtPath))
            else:
                printDBG("%s sidecar TXT save failed [%s]" % (self.__class__.__name__, txtPath))
        except Exception:
            printExc("%s sidecar TXT save failed" % self.__class__.__name__)

    def _imgSidecarDataAvail(self, data):
        return

    def _imgSidecarFinished(self, jpgPath, code):
        printDBG("%s._imgSidecarFinished code[%r]" % (self.__class__.__name__, code))

        # break circular references
        self.sidecarConsole_appClosed_conn = None
        self.sidecarConsole_stderrAvail_conn = None
        self.sidecarConsole = None
        tmpPath = self.sidecarImgTmpPath
        try:
            if code not in (0, None):
                # wget's exit code (1 generic, 4 network, 8 server error ...): what it left is a part of the
                # picture or an error page, not a poster
                printDBG("%s sidecar JPG download failed code[%r]" % (self.__class__.__name__, code))
                safeRemoveFile(tmpPath)
            elif os.path.isfile(fsPath(tmpPath)) and os.path.getsize(fsPath(tmpPath)) > 0 and self._startImgSidecarConversion(jpgPath, tmpPath):
                return  # ffmpeg makes a JPEG of it first, _imgSidecarConverted saves the picture then
        except Exception:
            printExc()
            self.sidecarConsole_appClosed_conn = None
            self.sidecarConsole = None
        self._saveImgSidecar(jpgPath, tmpPath)

    def _startImgSidecarConversion(self, jpgPath, tmpPath):
        # the picture as the server sent it: still gzip-encoded (some image CDNs compress unasked), or WebP / AVIF
        # under the .jpg name (the thumbnails of FYXXR and other sites) - the Enigma2 picture loader of VTi and
        # older images shows neither. gzip is undone here; WebP / AVIF go through ffmpeg (one frame as JPEG) in a
        # console run like the subtitle mux, which needs no open plugin window (convertWebp of the list icons needs
        # one for its ffmpeg fallback). True while ffmpeg runs. A conversion that fails keeps the file as it came.
        from Plugins.Extensions.IPTVPlayer.libs.pCommon import IsConvertibleImage, UngzipFile, common
        from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
        from Plugins.Extensions.IPTVPlayer.tools.iptvtools import IsExecutable
        name = self.__class__.__name__
        path = fsPath(tmpPath)
        if UngzipFile(path):
            printDBG("%s sidecar JPG came gzip-encoded, decoded" % name)
        if not IsConvertibleImage(path):
            return False
        ffmpeg = DMHelper.GET_FFMPEG_PATH()
        if not IsExecutable(ffmpeg):
            # without ffmpeg only Pillow can read it (in place, here in the main thread: convertWebp's own
            # ffmpeg fallback does not run without the executable)
            printDBG("%s sidecar JPG is WebP/AVIF and there is no ffmpeg, trying Pillow" % name)
            common().convertWebp(path)
            if IsConvertibleImage(path):
                printDBG("%s sidecar JPG not converted, saved as it came" % name)
            return False
        convPath = tmpPath + '.jpg'
        safeRemoveFile(convPath)
        cmd = '%s -y -i "%s" -frames:v 1 -update 1 -q:v 2 "%s" > /dev/null 2>&1' % (ffmpeg, shellQuote(tmpPath), shellQuote(convPath))
        printDBG("%s sidecar JPG is WebP/AVIF, convert cmd[%s]" % (name, cmd))
        self.sidecarConsole = eConsoleAppContainer()
        self.sidecarConsole_appClosed_conn = eConnectCallback(self.sidecarConsole.appClosed, boundFunction(self._imgSidecarConverted, jpgPath, convPath))
        executeConsoleCmd(self.sidecarConsole, cmd)
        return True

    def _imgSidecarConverted(self, jpgPath, convPath, code):
        printDBG("%s._imgSidecarConverted code[%r]" % (self.__class__.__name__, code))
        self.sidecarConsole_appClosed_conn = None
        self.sidecarConsole = None
        tmpPath = self.sidecarImgTmpPath
        try:
            if code == 0 and os.path.isfile(fsPath(convPath)) and os.path.getsize(fsPath(convPath)) > 0:
                safeRemoveFile(tmpPath)
                os.rename(fsPath(convPath), fsPath(tmpPath))
                printDBG("%s sidecar JPG converted to JPEG" % self.__class__.__name__)
            else:
                printDBG("%s sidecar JPG conversion failed code[%r], the picture is saved as it came" % (self.__class__.__name__, code))
                safeRemoveFile(convPath)
        except Exception:
            printExc()
        self._saveImgSidecar(jpgPath, tmpPath)

    def _saveImgSidecar(self, jpgPath, tmpPath):
        self.waitingForSidecar = False
        self.sidecarImgTmpPath = ''
        try:
            if os.path.isfile(fsPath(tmpPath)) and os.path.getsize(fsPath(tmpPath)) > 0:
                if filesAreIdentical(tmpPath, jpgPath):
                    printDBG("%s sidecar JPG unchanged, discarding re-download [%s]" % (self.__class__.__name__, jpgPath))
                    safeRemoveFile(tmpPath)
                else:
                    safeRemoveFile(jpgPath)
                    os.rename(fsPath(tmpPath), fsPath(jpgPath))
                    try:
                        # wget gives the file the server's date (the poster's upload, years ago): the
                        # download's time instead, so the picture sorts next to its video
                        os.utime(fsPath(jpgPath), None)
                    except Exception:
                        printExc()
                    printDBG("%s sidecar JPG saved [%s]" % (self.__class__.__name__, jpgPath))
            else:
                printDBG("%s sidecar JPG failed [%s]" % (self.__class__.__name__, jpgPath))
                safeRemoveFile(tmpPath)
        except Exception:
            printExc()

        self._finishDownloadFlow()

    def _startImgSidecarDownload(self, filePath):
        try:
            if not self.sidecarImg:
                printDBG("%s sidecar JPG skipped: empty URL" % self.__class__.__name__)
                self._finishDownloadFlow()
                return
            if ensureText(self.sidecarImg).startswith(('file://', '/')):
                # a host's own icon from the plugin folder (wget can not read file://): no cover of the video
                printDBG("%s sidecar JPG skipped: local host icon [%s]" % (self.__class__.__name__, self.sidecarImg))
                self._finishDownloadFlow()
                return

            basePath = ensureText(filePath).rsplit('.', 1)[0]
            jpgPath = basePath + '.jpg'
            tmpPath = jpgPath + '.new'
            self.sidecarImgTmpPath = tmpPath

            cmd = 'wget --header "User-Agent: %s" --no-check-certificate "%s" -O "%s" > /dev/null 2>&1' % (common.HOST, shellQuote(self.sidecarImg), shellQuote(tmpPath))
            printDBG("%s sidecar JPG cmd[%s]" % (self.__class__.__name__, cmd))

            self.waitingForSidecar = True
            self.sidecarConsole = eConsoleAppContainer()
            self.sidecarConsole_appClosed_conn = eConnectCallback(self.sidecarConsole.appClosed, boundFunction(self._imgSidecarFinished, jpgPath))
            self.sidecarConsole_stderrAvail_conn = eConnectCallback(self.sidecarConsole.stderrAvail, self._imgSidecarDataAvail)
            executeConsoleCmd(self.sidecarConsole, cmd)
        except Exception:
            printExc("%s sidecar JPG start failed" % self.__class__.__name__)
            self._finishDownloadFlow()

    def _terminateSidecar(self):
        # Call from each downloader's _terminate() to kill an in-flight
        # sidecar JPG download and avoid leaving a zombie process behind.
        if self.sidecarConsole is not None:
            try:
                if hasattr(self.sidecarConsole, "sendCtrlC"):
                    self.sidecarConsole.sendCtrlC()
                elif hasattr(self.sidecarConsole, "kill"):
                    self.sidecarConsole.kill()
            except Exception:
                printExc()
            self.sidecarConsole = None
            self.sidecarConsole_appClosed_conn = None
            self.sidecarConsole_stderrAvail_conn = None
            if self.sidecarImgTmpPath:
                # the Ctrl+C reaches the shell around wget / ffmpeg only; both name the temp file on their
                # command line (ffmpeg as its input)
                terminateToolsOfFile(self.sidecarImgTmpPath, ('wget', 'ffmpeg'))
                safeRemoveFile(self.sidecarImgTmpPath + '.jpg')
                safeRemoveFile(self.sidecarImgTmpPath)
                self.sidecarImgTmpPath = ''
        self._clearSubtitleData()

    def _finishDownloadFlow(self):
        # Generic finish-flow used by all three downloaders. Relies on
        # self._cleanUp() being implemented by the downloader subclass
        # (temp-file cleanup differs per downloader). A finished download
        # first gets its subtitles (setting "Subtitles"), which may wait
        # for their fetch or the MKV mux and come back here then.
        if self._subtitleStep():
            return
        try:
            self.onFinish()
        except Exception:
            printExc()
        self._cleanUp()
        self._clearSubtitleData()
