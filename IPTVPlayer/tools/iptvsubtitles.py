###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetSubtitlesDir, byteify, IsSubtitlesParserExtensionCanBeUsed
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper

# INFO about subtitles format
# https://wiki.videolan.org/Subtitles#Subtitles_support_in_VLC

# def printDBG(data):
#    print("%s" % data)

###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
import io
import json
from os import remove as os_remove, path as os_path
###################################################


class IPTVSubtitlesHandler:
    # srt/vtt/mpl plus the formats the Python fallback below reads (ASS/SSA, MicroDVD, SubViewer,
    # TMPlayer, MPL2 in .sub/.txt) - the content decides, not the extension
    SUPPORTED_FORMATS = ['srt', 'vtt', 'mpl', 'ass', 'ssa', 'sub', 'txt']

    @staticmethod
    def getSupportedFormats():
        printDBG("getSupportedFormats")
        if IsSubtitlesParserExtensionCanBeUsed():
            printDBG("getSupportedFormats after import")
            return ['srt', 'vtt', 'mpl', 'ssa', 'ass', 'smi', 'rt', 'txt', 'sub', 'dks', 'jss', 'psb', 'ttml']
        printDBG("getSupportedFormats end")
        return IPTVSubtitlesHandler.SUPPORTED_FORMATS

    def __init__(self):
        printDBG("IPTVSubtitlesHandler.__init__")
        self.subAtoms = []
        self.pailsOfAtoms = {}
        self.CAPACITY = 10 * 1000  # 10s
        self.saveCache = False
        printDBG("IPTVSubtitlesHandler.__init__ self.CAPACITY = %s" % self.CAPACITY)

    def _srtClearText(self, text):
        return re.sub('<[^>]*>', '', text)
        # <b></b> : bold
        # <i></i> : italic
        # <u></u> : underline
        # <font color=”#rrggbb”></font>

    def _srtTc2ms(self, time):
        try:
            time = time.strip()
            # WebVTT keeps the cue settings (e.g. "align:middle line:83%")
            # on the same line as the end timestamp - drop everything past
            # the first whitespace so only the HH:MM:SS.mmm token is parsed.
            time = time.split()[0]
            if ',' in time:
                split_time = time.split(',')
            else:
                split_time = time.split('.')
            msMatch = re.match(r'\d+', split_time[1])
            minor = int(msMatch.group(0)) if msMatch else 0  # milliseconds
            major = split_time[0].split(':')
            if len(major) == 2:  # format: mm:ss,mmm
                minutes = int(major[0])
                seconds = int(major[1])
                return (minutes * 60 + seconds) * 1000 + minor
            elif len(major) == 3:  # format: hh:mm:ss,mmm
                hours = int(major[0])
                minutes = int(major[1])
                seconds = int(major[2])
                return (hours * 3600 + minutes * 60 + seconds) * 1000 + minor
        except Exception as e:
            printDBG("Error in _srtTc2ms: %s" % str(e))
        return 0

    def _srtToAtoms(self, srtText):
        subAtoms = []
        srtText = srtText.replace('\r\n', '\n')  # win EOL > linux EOL
        srtText = srtText.split('\n\n')

        line = 0
        for idx in range(len(srtText)):
            line += 1
            try:
                st = srtText[idx].strip('\n \t')  # remove empty leading lines
                st = st.split('\n')
                if len(st) < 2:
                    continue  # less than two items are for sure garbage, so let's skip
                # WebVTT header / metadata blocks (WEBVTT, NOTE, STYLE, REGION,
                # X-TIMESTAMP-MAP) carry no cue and no ' --> ' - skip them
                # instead of popping the whole block away line by line.
                if re.match(r'^(WEBVTT|NOTE|STYLE|REGION|X-TIMESTAMP-MAP)\b', st[0]):
                    continue
                while st and (st[0] == '' or ' --> ' not in st[0]):
                    st.pop(0)  # remove line numbers and other unused lines existing before time
                if len(st) >= 2:
                    subtimes = st[0].split(' --> ')
                    subStartTime = subtimes[0].strip()
                    subEndTime = subtimes[1].strip()
                    start = self._srtTc2ms(subStartTime)
                    end = self._srtTc2ms(subEndTime)
                    if end <= start:
                        continue  # unparsable timing - a cue with end <= start never shows
                    # strip markup first (WebVTT <c.foo> spans sit on their own
                    # lines), then drop the blank lines they leave behind
                    subText = self._srtClearText('\n'.join(st[1:]))
                    subText = '\n'.join(j.strip() for j in subText.split('\n') if j.strip())
                    subAtoms.append({'start': start, 'end': end, 'text': subText})
            except Exception:
                printExc("Sub line number: %d, content:\n>>>>>\n%s\n<<<<<" % (line, st))
        # Some broadcasters (e.g. Das Erste / ARD) anchor their subtitle files
        # at a 10h wall-clock base - shift everything back so the cues line up
        # with playback time. Mirrors the workaround in the C-parser path.
        try:
            if subAtoms and min(a['start'] for a in subAtoms) >= 36000000:
                for a in subAtoms:
                    a['start'] -= 36000000
                    a['end'] -= 36000000
        except Exception:
            printExc()
        return subAtoms

    def _mplClearText(self, text):
        text = text.split('|')
        for idx in range(len(text)):
            if text[idx].startswith('/'):
                text[idx] = text[idx][1:]
        return re.sub(r'\{[^}]*\}', '', '\n'.join(text))

    def _mplTc2ms(self, time):
        return int(time) * 100

    def _mplToAtoms(self, mplData):
        # Timings          : Sequential Time
        # Timing Precision : 100 Milliseconds (1/10th sec)
        # an empty end ([10][]text) lasts until the next line, 5s at most - like MicroDVD
        subAtoms = []
        mplData = mplData.replace('\r\n', '\n').split('\n')
        reObj = re.compile(r'^\s*\[([0-9]+)\]\[([0-9]*)\](.+)$')

        for s in mplData:
            tmp = reObj.search(s)
            if None is not tmp:
                end = self._mplTc2ms(tmp.group(2)) if tmp.group(2) else -1
                subAtoms.append({'start': self._mplTc2ms(tmp.group(1)), 'end': end, 'text': self._mplClearText(tmp.group(3))})
        return self._fillOpenEnds(subAtoms)

    @staticmethod
    def _fillOpenEnds(subAtoms, maxDuration=5000):
        # cues without an end time (-1) last until the next cue starts, maxDuration at most
        for idx, atom in enumerate(subAtoms):
            if atom['end'] < 0:
                nextStart = subAtoms[idx + 1]['start'] if idx + 1 < len(subAtoms) else atom['start'] + maxDuration
                atom['end'] = min(nextStart, atom['start'] + maxDuration)
        return [a for a in subAtoms if a['end'] > a['start']]

    @staticmethod
    def _detectFormat(subText, ext):
        # the content decides: a MicroDVD file saved as .srt is common enough
        head = subText[:20000]
        if re.search(r'(?im)^\s*\[script info\]|^dialogue:\s*[^,\n]*,\s*\d+:\d{2}:\d{2}', head):
            return 'ass'
        if re.search(r'(?m)^\s*\{\d+\}\{\d*\}', head):
            return 'microdvd'
        if re.search(r'(?m)^\s*\[\d+\]\[\d*\]', head):
            return 'mpl'
        if ' --> ' in head:
            return 'srt'
        if re.search(r'(?m)^\s*\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}\s*,\s*\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}\s*$', head):
            return 'subviewer'
        if re.search(r'(?m)^\s*\d{1,2}:\d{2}:\d{2}[:=]', head):
            return 'tmplayer'
        return 'srt' if ext in ('srt', 'vtt') else ''

    @staticmethod
    def _assTc2ms(time):
        # H:MM:SS.cc
        h, m, s = time.strip().split(':')
        return int(round((int(h) * 3600 + int(m) * 60 + float(s)) * 1000))

    def _assToAtoms(self, assText):
        subAtoms = []
        fields = ['layer', 'start', 'end', 'style', 'name', 'marginl', 'marginr', 'marginv', 'effect', 'text']
        inEvents = False
        for line in assText.replace('\r\n', '\n').split('\n'):
            line = line.strip()
            if line.startswith('['):
                inEvents = line.lower() == '[events]'
                continue
            if not inEvents:
                continue
            if line.lower().startswith('format:'):
                fields = [f.strip().lower() for f in line.split(':', 1)[1].split(',')]
                continue
            if not line.lower().startswith('dialogue:'):
                continue
            try:
                values = line.split(':', 1)[1].split(',', len(fields) - 1)
                item = dict(zip(fields, values))
                text = item.get('text', '')
                if re.search(r'\{[^}]*\\p[1-9]', text):
                    continue  # vector drawing, no text
                text = re.sub(r'\{[^}]*\}', '', text).replace('\\N', '\n').replace('\\n', '\n').replace('\\h', ' ')
                text = '\n'.join(j.strip() for j in self._srtClearText(text).split('\n') if j.strip())
                start, end = self._assTc2ms(item['start']), self._assTc2ms(item['end'])
                if text and end > start:
                    subAtoms.append({'start': start, 'end': end, 'text': text})
            except Exception:
                printExc("ASS line: %s" % line)
        subAtoms.sort(key=lambda a: a['start'])
        return subAtoms

    def _microDvdToAtoms(self, subText, fps):
        # {start frame}{end frame}text|second line - an empty end frame lasts until the next line (max 5s).
        # Like the C parser: a known fps (argument / file name) wins, else {1}{1}23.976 in the first line, else 23.976
        subAtoms = []
        fileFps = 0
        reObj = re.compile(r'^\s*\{(\d+)\}\{(\d*)\}(.*)$')
        for line in subText.replace('\r\n', '\n').split('\n'):
            tmp = reObj.search(line)
            if tmp is None:
                continue
            start, end, text = int(tmp.group(1)), tmp.group(2), tmp.group(3)
            if not subAtoms and start <= 1 and re.match(r'^\d+(?:\.\d+)?$', text.strip()):
                fileFps = float(text.strip())
                continue
            text = '\n'.join(j.strip() for j in self._mplClearText(text).split('\n') if j.strip())
            if text:
                subAtoms.append({'start': start, 'end': int(end) if end else -1, 'text': text})
        fps = fps if fps > 0 else (fileFps or 23.976)
        for atom in subAtoms:
            atom['start'] = int(atom['start'] * 1000 / fps)
            if atom['end'] >= 0:
                atom['end'] = int(atom['end'] * 1000 / fps)
        return self._fillOpenEnds(subAtoms)

    def _subViewerToAtoms(self, subText):
        # 00:00:01.00,00:00:04.00 then the text ([br] = new line) up to an empty line
        subAtoms = []
        reTime = re.compile(r'^\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s*,\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3})\s*$')
        lines = subText.replace('\r\n', '\n').split('\n')
        idx = 0
        while idx < len(lines):
            tmp = reTime.search(lines[idx])
            idx += 1
            if tmp is None:
                continue
            textLines = []
            while idx < len(lines) and lines[idx].strip() != '' and reTime.search(lines[idx]) is None:
                textLines.append(lines[idx])
                idx += 1
            text = self._srtClearText('\n'.join(textLines).replace('[br]', '\n').replace('[BR]', '\n'))
            text = '\n'.join(j.strip() for j in text.split('\n') if j.strip())
            # .50 are hundredths here, not milliseconds like in SRT
            start, end = self._assTc2ms(tmp.group(1).replace(',', '.')), self._assTc2ms(tmp.group(2).replace(',', '.'))
            if text and end > start:
                subAtoms.append({'start': start, 'end': end, 'text': text})
        return subAtoms

    def _tmPlayerToAtoms(self, subText):
        # hh:mm:ss:text or hh:mm:ss=text, no end time: until the next line, at most 5s
        subAtoms = []
        reObj = re.compile(r'^\s*(\d{1,2}):(\d{2}):(\d{2})[:=](.*)$')
        for line in subText.replace('\r\n', '\n').split('\n'):
            tmp = reObj.search(line)
            if tmp is None:
                continue
            text = '\n'.join(j.strip() for j in self._mplClearText(tmp.group(4)).split('\n') if j.strip())
            start = (int(tmp.group(1)) * 3600 + int(tmp.group(2)) * 60 + int(tmp.group(3))) * 1000
            if subAtoms and subAtoms[-1]['end'] > start:
                subAtoms[-1]['end'] = max(subAtoms[-1]['start'] + 1, start)
            if text:
                subAtoms.append({'start': start, 'end': start + 5000, 'text': text})
        return subAtoms

    @staticmethod
    def _fpsFromPath(filePath, fps=0):
        # fps given by the caller, else _fps25.0 of the downloaded file name, else 0 (unknown)
        if fps <= 0:
            tmp = CParsingHelper.getSearchGroups(os_path.splitext(filePath)[0].upper() + '_', '_FPS([0-9.]+)_')[0]
            try:
                fps = float(tmp) if tmp else 0
            except ValueError:
                fps = 0
        return fps

    # def _preparPails(self, scope):

    def getSubtitlesFromSubAtoms(self, currTimeMS):
        # time1 = time.time()
        subsText = []
        for item in self.subAtoms:
            if currTimeMS >= item['start'] and currTimeMS < item['end']:
                subsText.append(item['text'])
        ret = '\n'.join(subsText)
        # time2 = time.time()
        # printDBG('>>>>>>>>>>getSubtitlesFromSubAtoms function took %0.3f ms' % ((time2-time1)*1000.0))
        printDBG("OpenSubOrg.getSubtitlesFromSubAtoms(%s) returns [%s]" % (currTimeMS, ret))
        return ret

    def getSubtitles(self, currTimeMS, prevMarker):
        printDBG("OpenSubOrg.getSubtitles(currTimeMS = %s, prevMarker = %s)" % (currTimeMS, prevMarker))
        # time1 = time.time()
        subsText = []
        tmp = currTimeMS // self.CAPACITY
        tmpList = self.pailsOfAtoms.get(tmp, [])

        if len(tmpList) == 0:
            return [], self.getSubtitlesFromSubAtoms(currTimeMS)
        else:
            printDBG("OpenSubOrg.getSubtitles tmp = %s, len(tmpList) = %s" % (tmp, len(tmpList)))
            ret = None
            validAtomsIdexes = []
            for idx in tmpList:
                item = self.subAtoms[idx]
                if currTimeMS >= item['start'] and currTimeMS < item['end']:
                    validAtomsIdexes.append(idx)

            marker = validAtomsIdexes
            printDBG("OpenSubOrg.getSubtitles marker[%s] prevMarker[%s] %.1fs" % (marker, prevMarker, currTimeMS / 1000.0))
            if prevMarker != marker:
                for idx in validAtomsIdexes:
                    item = self.subAtoms[idx]
                    subsText.append(item['text'])
                ret = '\n'.join(subsText)
            # time2 = time.time()
            # printDBG('>>>>>>>>>>getSubtitles function took %0.3f ms' % ((time2-time1)*1000.0))
            return marker, ret

    def removeCacheFile(self, filePath):
        cacheFile = self._getCacheFileName(filePath)
        try:
            if os_path.exists(cacheFile):
                os_remove(cacheFile)
        except Exception:
            printExc()

    def _getCacheFileName(self, filePath):
        tmp = filePath.split('/')[-1]
        # ".iptv2" - bumped from ".iptv" so caches written by the old parser
        # (WebVTT cue settings broke every end timestamp -> unusable atoms)
        # are ignored and the subtitles are re-parsed once with the fix.
        return GetSubtitlesDir(tmp + '.iptv2')

    def _loadFromCache(self, orgFilePath, encoding='utf-8'):
        sts = False
        try:
            filePath = self._getCacheFileName(orgFilePath)
            if os_path.exists(filePath):
                with io.open(filePath, 'r', encoding=encoding, errors='replace', newline='') as fp:
                    self.subAtoms = byteify(json.loads(fp.read()))
                if len(self.subAtoms):
                    sts = True
                    printDBG("IPTVSubtitlesHandler._loadFromCache orgFilePath[%s] --> cacheFile[%s], loaded %s subs" % (orgFilePath, filePath, len(self.subAtoms)))
        except Exception:
            printExc('EXCEPTION in OpenSubOrg._loadFromCache')
        return sts

    def _saveToCache(self, orgFilePath, encoding='utf-8'):
        try:
            if len(self.subAtoms):
                filePath = self._getCacheFileName(orgFilePath)
                with io.open(filePath, 'w', encoding=encoding, newline='') as fp:
                    fp.write(json.dumps(self.subAtoms))
                printDBG("IPTVSubtitlesHandler._saveToCache orgFilePath[%s] --> cacheFile[%s]" % (orgFilePath, filePath))
            else:
                printDBG("IPTVSubtitlesHandler._saveToCache subtitles list empty - nothing to save")
                self.removeCacheFile(orgFilePath)  # just in case we have garbage cached

        except Exception:
            printExc('EXCEPTION in OpenSubOrg._saveToCache')

    def _fillPailsOfAtoms(self):
        self.pailsOfAtoms = {}
        for idx in range(len(self.subAtoms)):
            startBucket = self.subAtoms[idx]['start'] // self.CAPACITY
            endBucket = self.subAtoms[idx]['end'] // self.CAPACITY
            for tmp in range(startBucket, endBucket + 1):
                if tmp not in self.pailsOfAtoms:
                    self.pailsOfAtoms[tmp] = [idx]
                elif idx not in self.pailsOfAtoms[tmp]:
                    self.pailsOfAtoms[tmp].append(idx)
        self.pailsOfAtoms = dict(sorted(self.pailsOfAtoms.items()))

    def loadSubtitles(self, filePath, encoding='utf-8', fps=0):
        printDBG("OpenSubOrg.loadSubtitles filePath[%s]" % filePath)
        # try load subtitles using C-library
        try:
            if IsSubtitlesParserExtensionCanBeUsed():
                fps = self._fpsFromPath(filePath, fps)

                from Plugins.Extensions.IPTVPlayer.libs.iptvsubparser import _subparser as subparser
                with io.open(filePath, 'r', encoding=encoding, errors='replace', newline='') as fp:
                    subText = ensure_str(fp.read())
                # if in subtitles will be line {1}{1}f_fps
                # for example {1}{1}23.976 and we set microsecperframe = 0
                # then microsecperframe will be calculated as follow: llroundf(1000000.f / f_fps)
                if fps > 0:
                    microsecperframe = int(1000000.0 / fps)
                else:
                    microsecperframe = 0
                # calc end time if needed - optional, default True
                setEndTime = True
                # characters per second - optional, default 12, can not be set to 0
                CPS = 12
                # words per minute - optional, default 138, can not be set to 0
                WPM = 138
                # remove format tags, like <i> - optional, default True
                removeTags = True
                subsObj = subparser.parse(subText, microsecperframe, removeTags, setEndTime, CPS, WPM)
                if 'type' in subsObj:
                    self.subAtoms = subsObj['list']
                    # Workaround start
                    try:
                        if len(self.subAtoms) and self.subAtoms[0]['start'] >= 36000000:
                            printDBG('Workaround for subtitles from Das Erste: %s' % self.subAtoms[0]['start'])
                            for idx in range(len(self.subAtoms)):
                                for key in ['start', 'end']:
                                    if key not in self.subAtoms[idx]:
                                        continue
                                    if self.subAtoms[idx][key] >= 36000000:
                                        self.subAtoms[idx][key] -= 36000000
                    except Exception:
                        printExc()
                    # workaround end
                    self._fillPailsOfAtoms()
                    if 1:  # for tests
                        if self.saveCache and len(self.subAtoms):
                            self._saveToCache(filePath)
                    return True
                printDBG("OpenSubOrg.loadSubtitles C-parser failed, trying the Python parsers")
        except Exception:
            printExc()
        return self._loadSubtitles(filePath, encoding, fps)

    def _loadSubtitles(self, filePath, encoding, fps=0):
        # printDBG("OpenSubOrg._loadSubtitles filePath[%s]" % filePath)
        self.saveCache = True
        self.subAtoms = []
        # time1 = time.time()
        sts = self._loadFromCache(filePath)
        if not sts:
            try:
                with io.open(filePath, 'r', encoding=encoding, errors='replace', newline='') as fp:
                    subText = ensure_str(fp.read().lstrip(u'\ufeff'))
                fmt = self._detectFormat(subText, os_path.splitext(filePath)[1].lower().lstrip('.'))
                if fmt == 'srt':
                    self.subAtoms = self._srtToAtoms(subText)
                elif fmt == 'mpl':
                    self.subAtoms = self._mplToAtoms(subText)
                elif fmt == 'ass':
                    self.subAtoms = self._assToAtoms(subText)
                elif fmt == 'microdvd':
                    self.subAtoms = self._microDvdToAtoms(subText, self._fpsFromPath(filePath, fps))
                elif fmt == 'subviewer':
                    self.subAtoms = self._subViewerToAtoms(subText)
                elif fmt == 'tmplayer':
                    self.subAtoms = self._tmPlayerToAtoms(subText)
                # a format we know but no usable cue in it is a failed load, not an empty track
                sts = fmt != '' and len(self.subAtoms) > 0
                printDBG("OpenSubOrg._loadSubtitles format[%s] loaded %s subs" % (fmt, len(self.subAtoms)))
            except Exception:
                printExc('EXCEPTION in OpenSubOrg._loadSubtitles')
        else:
            self.saveCache = False

        self._fillPailsOfAtoms()

        if self.saveCache and len(self.subAtoms):
            self._saveToCache(filePath)

        # time2 = time.time()
        # printDBG('>>>>>>>>>>loadSubtitles function took %0.3f ms' % ((time2-time1)*1000.0))

        return sts


class IPTVEmbeddedSubtitlesHandler:
    def __init__(self):
        printDBG("IPTVEmbeddedSubtitlesHandler.__init__")
        self.subAtoms = []
        self.pailsOfAtoms = {}
        self.CAPACITY = 10 * 1000  # 10s

    def _srtClearText(self, text):
        return re.sub('<[^>]*>', '', text)
        # <b></b> : bold
        # <i></i> : italic
        # <u></u> : underline
        # <font color=”#rrggbb”></font>

    def addSubAtom(self, inAtom):
        try:
            inAtom = byteify(inAtom)
            textTab = inAtom['text'].split('\n')
            for text in textTab:
                text = self._srtClearText(text).strip()
                if text != '':
                    idx = len(self.subAtoms)
                    self.subAtoms.append({'start': inAtom['start'], 'end': inAtom['end'], 'text': text})

                    startBucket = self.subAtoms[idx]['start'] // self.CAPACITY
                    endBucket = self.subAtoms[idx]['end'] // self.CAPACITY
                    for tmp in range(startBucket, endBucket + 1):
                        if tmp not in self.pailsOfAtoms:
                            self.pailsOfAtoms[tmp] = [idx]
                        elif idx not in self.pailsOfAtoms[tmp]:
                            self.pailsOfAtoms[tmp].append(idx)
        except Exception:
            pass

    def getSubtitles(self, currTimeMS, prevMarker=None):
        if prevMarker is None:
            prevMarker = []
        subsText = []
        tmp = currTimeMS // self.CAPACITY
        tmp = self.pailsOfAtoms.get(tmp, [])

        ret = None
        validAtomsIdexes = []
        for idx in tmp:
            item = self.subAtoms[idx]
            if currTimeMS >= item['start'] and currTimeMS < item['end']:
                validAtomsIdexes.append(idx)

        marker = validAtomsIdexes
        printDBG("OpenSubOrg.getSubtitles marker[%s] prevMarker[%s] %.1fs" % (marker, prevMarker, currTimeMS / 1000.0))
        if prevMarker != marker:
            for idx in validAtomsIdexes:
                item = self.subAtoms[idx]
                subsText.append(item['text'])
            ret = '\n'.join(subsText)
        return marker, ret

    def flushSubtitles(self):
        self.subAtoms = []
        self.pailsOfAtoms = {}
