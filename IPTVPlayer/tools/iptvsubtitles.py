###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetSubtitlesDir, byteify, IsSubtitlesParserExtensionCanBeUsed
from Plugins.Extensions.IPTVPlayer.libs.pCommon import CParsingHelper

# INFO about subtitles format
# https://wiki.videolan.org/Subtitles#Subtitles_support_in_VLC

#def printDBG(data):
#    print("%s" % data)

###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
import codecs
import time
try:
    import json
except Exception:
    import simplejson as json
from os import remove as os_remove, path as os_path
###################################################


class IPTVSubtitlesHandler:
    SUPPORTED_FORMATS = ['srt', 'vtt', 'mpl']

    @staticmethod
    def getSupportedFormats():
        printDBG("getSupportedFormats")
        if IsSubtitlesParserExtensionCanBeUsed():
            printDBG("getSupportedFormats after import")
            return ['srt', 'vtt', 'mpl', 'ssa', 'smi', 'rt', 'txt', 'sub', 'dks', 'jss', 'psb', 'ttml']
        printDBG("getSupportedFormats end")
        return IPTVSubtitlesHandler.SUPPORTED_FORMATS

    def __init__(self):
        printDBG("IPTVSubtitlesHandler.__init__")
        self.subAtoms = []
        self.pailsOfAtoms = {}
        self.CAPACITY = 10 * 1000 # 10s
        printDBG("IPTVSubtitlesHandler.__init__ self.CAPACITY = %s" % self.CAPACITY )

    def _srtClearText(self, text):
        return re.sub('<[^>]*>', '', text)
        #<b></b> : bold
        #<i></i> : italic
        #<u></u> : underline
        #<font color=”#rrggbb”></font>

    def _srtTc2ms2(self, tc):
        sign = 1
        if tc[0] in "+-":
            sign = -1 if tc[0] == "-" else 1
            tc = tc[1:]

        match = self.TIMECODE_RE.match(tc)
        hh, mm, ss, ms = [0 if x == None else int(x) for x in match.groups()]
        return ((hh * 3600 + mm * 60 + ss) * 1000 + ms) * sign

    def _srtTc2ms(self, time):
        if ',' in time:
            split_time = time.split(',')
        else:
            split_time = time.split('.')
        minor = split_time[1]
        major = split_time[0].split(':')
        if len(major) == 2: #sometimes 00 hour missing at the begging of subs
            return (int(major[0]) * 60 + int(major[1])) * 1000 + int(minor)
        else:
            return (int(major[0]) * 3600 + int(major[1]) * 60 + int(major[2])) * 1000 + int(minor)

    def _srtToAtoms(self, srtText):
        subAtoms = []
        srtText = srtText.replace('\r\n', '\n') #win EOL > linux EOL
        srtText = srtText.split('\n\n')

        line = 0
        for idx in range(len(srtText)):
            line += 1
            try:
                st = srtText[idx].strip('\n \t') #remove empty leading lines
                st = st.split('\n')
                if len(st) < 2: continue #less than two items are for sure garbage, so let's skip
                while st[0] ==  '': st.pop(0)
                while not ' --> ' in st[0]: st.pop(0) #remove line numbers and other unused lines existing before time
                if 1: #tests only
                    printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                    printDBG(st)
                    printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                if len(st) >= 2:
                    subtimes = st[0].split(' --> ')
                    subStartTime = subtimes[0].strip()
                    subEndTime = subtimes[1].strip()
                    subText = st[1:]
                    subAtoms.append({'start': self._srtTc2ms(subStartTime), 'end': self._srtTc2ms(subEndTime), 'text': self._srtClearText('\n'.join(j for j in subText))})
            except Exception:
                printExc("Sub line number: %d, content:\n>>>>>\n%s\n<<<<<" % (line, st))
        return subAtoms

    def _mplClearText(self, text):
        text = text.split('|')
        for idx in range(len(text)):
            if text[idx].startswith('/'):
                text[idx] = text[idx][1:]
        return re.sub('\{[^}]*\}', '', '\n'.join(text))

    def _mplTc2ms(self, time):
        return int(time) * 100

    def _mplToAtoms(self, mplData):
        # Timings          : Sequential Time
        # Timing Precision : 100 Milliseconds (1/10th sec)
        subAtoms = []
        mplData = mplData.replace('\r\n', '\n').split('\n')
        reObj = re.compile('^\[([0-9]+?)\]\[([0-9]+?)\](.+?)$')

        for s in mplData:
            tmp = reObj.search(s)
            if None != tmp:
                subAtoms.append({'start': self._mplTc2ms(tmp.group(1)), 'end': self._mplTc2ms(tmp.group(2)), 'text': self._mplClearText(tmp.group(3))})
        return subAtoms

    #def _preparPails(self, scope):

    def getSubtitlesFromSubAtoms(self, currTimeMS):
        #time1 = time.time()
        subsText = []
        for item in self.subAtoms:
            if currTimeMS >= item['start'] and currTimeMS < item['end']:
                subsText.append(item['text'])
        ret = '\n'.join(subsText)
        #time2 = time.time()
        #printDBG('>>>>>>>>>>getSubtitlesFromSubAtoms function took %0.3f ms' % ((time2-time1)*1000.0))
        printDBG("OpenSubOrg.getSubtitlesFromSubAtoms(%s) returns [%s]" % (currTimeMS,ret))
        return ret

    def getSubtitles(self, currTimeMS, prevMarker):
        printDBG("OpenSubOrg.getSubtitles(currTimeMS = %s, prevMarker = %s)" % (currTimeMS, prevMarker))
        #time1 = time.time()
        subsText = []
        tmp = currTimeMS / self.CAPACITY
        tmpList = self.pailsOfAtoms.get(tmp, [])
        
        if len(tmpList) == 0:
            return [], self.getSubtitlesFromSubAtoms(currTimeMS)
        else:
            printDBG("OpenSubOrg.getSubtitles tmp = %s, len(tmpList) = %s" % (tmp,len(tmpList)))
            ret = None
            validAtomsIdexes = []
            for idx in tmpList:
                item = self.subAtoms[idx]
                if currTimeMS >= item['start'] and currTimeMS < item['end']:
                    validAtomsIdexes.append(idx)
                
            marker = validAtomsIdexes
            printDBG("OpenSubOrg.getSubtitles marker[%s] prevMarker[%s] %.1fs" % (marker, prevMarker, currTimeMS/1000.0))
            if prevMarker != marker:
                for idx in validAtomsIdexes:
                    item = self.subAtoms[idx]
                    subsText.append(item['text'])
                ret = '\n'.join(subsText)
            #time2 = time.time()
            #printDBG('>>>>>>>>>>getSubtitles function took %0.3f ms' % ((time2-time1)*1000.0))
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
        return GetSubtitlesDir(tmp + '.iptv')

    def _loadFromCache(self, orgFilePath, encoding='utf-8'):
        sts = False
        try:
            filePath = self._getCacheFileName(orgFilePath)
            if os_path.exists(filePath):
                with codecs.open(filePath, 'r', encoding, 'replace') as fp:
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
                with codecs.open(filePath, 'w', encoding) as fp:
                    fp.write(json.dumps(self.subAtoms))
                printDBG("IPTVSubtitlesHandler._saveToCache orgFilePath[%s] --> cacheFile[%s]" % (orgFilePath, filePath))
            else:
                printDBG("IPTVSubtitlesHandler._saveToCache subtitles list empty - nothing to save")
                removeCacheFile(orgFilePath) #just in case we have garbage cached
                    
        except Exception:
            printExc('EXCEPTION in OpenSubOrg._saveToCache')

    def _fillPailsOfAtoms(self):
        self.pailsOfAtoms = {}
        for idx in range(len(self.subAtoms)):
            tmp = self.subAtoms[idx]['start'] / self.CAPACITY
            if tmp not in self.pailsOfAtoms:
                self.pailsOfAtoms[tmp] = [idx]
            elif idx not in self.pailsOfAtoms[tmp]:
                self.pailsOfAtoms[tmp].append(idx)

            tmp = self.subAtoms[idx]['end'] / self.CAPACITY
            if tmp not in self.pailsOfAtoms:
                self.pailsOfAtoms[tmp] = [idx]
            elif idx not in self.pailsOfAtoms[tmp]:
                self.pailsOfAtoms[tmp].append(idx)
        self.pailsOfAtoms = dict(sorted( self.pailsOfAtoms.items()))
        if 1: #for tests
            with codecs.open('/tmp/pailsOfAtoms.json', 'w', 'utf-8') as fp:
                  fp.write(json.dumps(self.pailsOfAtoms))
            with codecs.open('/tmp/subAtoms.json', 'w', 'utf-8') as fp:
                  fp.write(json.dumps(self.subAtoms))

    def loadSubtitles(self, filePath, encoding='utf-8', fps=0):
        printDBG("OpenSubOrg.loadSubtitles filePath[%s]" % filePath)
        # try load subtitles using C-library
        try:
            if IsSubtitlesParserExtensionCanBeUsed():
                try:
                    if fps <= 0:
                        filename, file_extension = os_path.splitext(filePath)
                        tmp = CParsingHelper.getSearchGroups(filename.upper() + '_', '_FPS([0-9.]+)_')[0]
                        if '' != tmp:
                            fps = float(tmp)
                except Exception:
                    printExc()

                from Plugins.Extensions.IPTVPlayer.libs.iptvsubparser import _subparser as subparser
                with codecs.open(filePath, 'r', encoding, 'replace') as fp:
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
                    if 1: #for tests
                        if saveCache and len(self.subAtoms):
                            self._saveToCache(filePath)
                    return True
                else:
                    return False
        except Exception:
            printExc()
        return self._loadSubtitles(filePath, encoding)

    def _loadSubtitles(self, filePath, encoding):
        #printDBG("OpenSubOrg._loadSubtitles filePath[%s]" % filePath)
        saveCache = True
        self.subAtoms = []
        #time1 = time.time()
        sts = self._loadFromCache(filePath)
        if not sts:
            try:
                with codecs.open(filePath, 'r', encoding, 'replace') as fp:
                    subText = ensure_str(fp.read())
                    if filePath.endswith('.srt'):
                        self.subAtoms = self._srtToAtoms(subText)
                        sts = True
                    elif filePath.endswith('.vtt'):
                        self.subAtoms = self._srtToAtoms(subText)
                        sts = True
                    elif filePath.endswith('.mpl'):
                        self.subAtoms = self._mplToAtoms(subText)
                        sts = True
                    printDBG("OpenSubOrg._loadSubtitles loaded %s subs" % len(self.subAtoms))
            except Exception:
                printExc('EXCEPTION in OpenSubOrg._loadSubtitles')
        else:
            saveCache = False

        self._fillPailsOfAtoms()

        if saveCache and len(self.subAtoms):
            self._saveToCache(filePath)

        #time2 = time.time()
        #printDBG('>>>>>>>>>>loadSubtitles function took %0.3f ms' % ((time2-time1)*1000.0))

        return sts


class IPTVEmbeddedSubtitlesHandler:
    def __init__(self):
        printDBG("IPTVEmbeddedSubtitlesHandler.__init__")
        self.subAtoms = []
        self.pailsOfAtoms = {}
        self.CAPACITY = 10 * 1000 # 10s

    def _srtClearText(self, text):
        return re.sub('<[^>]*>', '', text)
        #<b></b> : bold
        #<i></i> : italic
        #<u></u> : underline
        #<font color=”#rrggbb”></font>

    def addSubAtom(self, inAtom):
        try:
            inAtom = byteify(inAtom)
            textTab = inAtom['text'].split('\n')
            for text in textTab:
                text = self._srtClearText(text).strip()
                if text != '':
                    idx = len(self.subAtoms)
                    self.subAtoms.append({'start': inAtom['start'], 'end': inAtom['end'], 'text': text})

                    tmp = self.subAtoms[idx]['start'] / self.CAPACITY
                    if tmp not in self.pailsOfAtoms:
                        self.pailsOfAtoms[tmp] = [idx]
                    elif idx not in self.pailsOfAtoms[tmp]:
                        self.pailsOfAtoms[tmp].append(idx)

                    tmp = self.subAtoms[idx]['end'] / self.CAPACITY
                    if tmp not in self.pailsOfAtoms:
                        self.pailsOfAtoms[tmp] = [idx]
                    elif idx not in self.pailsOfAtoms[tmp]:
                        self.pailsOfAtoms[tmp].append(idx)
        except Exception:
            pass

    def getSubtitles(self, currTimeMS, prevMarker):
        subsText = []
        tmp = currTimeMS / self.CAPACITY
        tmp = self.pailsOfAtoms.get(tmp, [])

        ret = None
        validAtomsIdexes = []
        for idx in tmp:
            item = self.subAtoms[idx]
            if currTimeMS >= item['start'] and currTimeMS < item['end']:
                validAtomsIdexes.append(idx)

        marker = validAtomsIdexes
        printDBG("OpenSubOrg.getSubtitles marker[%s] prevMarker[%s] %.1fs" % (marker, prevMarker, currTimeMS/1000.0))
        if prevMarker != marker:
            for idx in validAtomsIdexes:
                item = self.subAtoms[idx]
                subsText.append(item['text'])
            ret = '\n'.join(subsText)
        return marker, ret

    def flushSubtitles(self):
        self.subAtoms = []
        self.pailsOfAtoms = {}


if __name__ == "__main__":
    obj = IPTVSubtitlesHandler()
    obj.loadSubtitles('/hdd/_Back.To.The.Future[1985]DvDrip-aXXo.pl.srt')
    obj.getSubtitles(10000)
