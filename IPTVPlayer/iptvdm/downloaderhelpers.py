# -*- coding: utf-8 -*-
# IPTV download manager API
# # added: 07.08.2026 - Shared helpers for Downloader: Py2/Py3 safe text & path handling, shell quoting, and the sidecar, (.txt description + .jpg poster). - Kamikaze24
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
import threading
import time
###################################################

try:
    text_type = unicode
    binary_type = str
    string_types = (basestring,)
except NameError:
    text_type = str
    binary_type = bytes
    string_types = (str, bytes)


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
        cmd = DMHelper.GET_FFMPEG_PATH() + ' -y '
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
        cmd += ' -f matroska "%s" >/dev/null 2>&1 ' % shellQuote(self.subEmbedTmp)
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

    def _subtitleEmbedFinished(self, code=None):
        from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
        self.subConsole_appClosed_conn = None
        self.subConsole = None
        tmp = self.subEmbedTmp
        self.subEmbedTmp = ''
        video = ensureText(self.filePath)
        size = DMHelper.getFileSize(fsPath(tmp))
        printDBG("%s subtitle mux finished code[%r] size[%r]" % (self.__class__.__name__, code, size))
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
            printDBG("%s subtitle mux failed, the subtitles stay next to the file" % self.__class__.__name__)
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

        tmpPath = self.sidecarImgTmpPath
        try:
            # break circular references
            self.sidecarConsole_appClosed_conn = None
            self.sidecarConsole_stderrAvail_conn = None
            self.sidecarConsole = None
            self.waitingForSidecar = False
            self.sidecarImgTmpPath = ''

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
