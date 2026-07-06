# -*- coding: utf-8 -*-
# IPTV download manager API
# Last Modified: 05.07.2026 - Channel name as download meta for MergeDownloader + absolute published date in info view + unified Py2/Py3 safe text/path handling
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, eConnectCallback, GetNice, rm, E2PrioFix
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import enum, strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
###################################################
# FOREIGN import
###################################################
from Tools.BoundFunction import boundFunction
from enigma import eConsoleAppContainer
from time import sleep
import re
import datetime
import os
import struct
try:
    try:
        import json
    except Exception:
        import simplejson as json
except Exception:
    printExc()
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


def shellQuote(value):
    value = ensureText(value)
    value = value.replace('\\', '\\\\')
    value = value.replace('"', '\\"')
    value = value.replace('`', '\\`')
    value = value.replace('$', '\\$')
    return value


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

###################################################
# One instance of this class can be used only for
# one download
###################################################


class MergeDownloader(BaseDownloader):

    def __init__(self):
        printDBG('MergeDownloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)

        # instance of E2 console
        self.console = None
        self.console_appClosed_conn = None
        self.console_stderrAvail_conn = None
        self.iptv_sys = None

        self.sidecarConsole = None
        self.sidecarConsole_appClosed_conn = None
        self.sidecarConsole_stderrAvail_conn = None

        self.multi = {'urls': [], 'files': [], 'remote_size': [], 'remote_content_type': [], 'local_size': []}
        self.currIdx = 0

        self.sidecarEnabled = False
        self.sidecarTxt = ''
        self.sidecarImg = ''
        self.waitingForSidecar = False

        self.makeMkvChapters = False
        self.makeCutsFile = False
        self.tempMergePath = ''
        self.chapterMetaPath = ''
        self.finalizedPath = ''
        self.postProcessMode = 'merge'
        self.mergedFileDurationMs = 0

        self.channelName = ''
        self.downloadChannelName = ''
        self.downloadUseChannelName = False
        self.originalFilePath = ''

    def __del__(self):
        printDBG("MergeDownloader.__del__ ----------------------------------")

    def _safeRm(self, path):
        try:
            fpath = fsPath(path)
            if fpath and os.path.exists(fpath):
                rm(fpath)
        except Exception:
            printExc()

    def _cleanUp(self):
        for item in self.multi['files']:
            self._safeRm(item)
        if self.tempMergePath:
            self._safeRm(self.tempMergePath)
        if self.chapterMetaPath:
            self._safeRm(self.chapterMetaPath)

    def getName(self):
        return "MergeDownloader"

    def isWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system(DMHelper.GET_FFMPEG_PATH() + ' -version ' + " 2>&1 ", boundFunction(self._checkWorkingCallBack, callBackFun))

    def _checkWorkingCallBack(self, callBackFun, code, data):
        reason = ''
        sts = True
        if code != 0:
            sts = False
            reason = data
            self.iptv_sys = None
            callBackFun(sts, reason)
        else:  # Need wget for correct working, so check also if wget working correctly
            self._isWgetWorkingCorrectly(callBackFun)

    def _isWgetWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system(DMHelper.GET_WGET_PATH() + " -V 2>&1 ", boundFunction(self._checkWgetWorkingCallBack, callBackFun))

    def _checkWgetWorkingCallBack(self, callBackFun, code, data):
        reason = ''
        sts = True
        if code != 0:
            sts = False
            reason = data
        self.iptv_sys = None
        callBackFun(sts, reason)

    def _clearSidecarData(self):
        self.sidecarEnabled = False
        self.sidecarTxt = ''
        self.sidecarImg = ''
        self.waitingForSidecar = False
        self.makeMkvChapters = False
        self.makeCutsFile = False

        self.channelName = ''
        self.downloadChannelName = ''
        self.downloadUseChannelName = False

    def _prepareSidecarData(self, meta):
        self._clearSidecarData()
        try:
            if meta.get('e2i_sidecar_enabled', False):
                self.sidecarEnabled = True
                self.sidecarTxt = meta.get('e2i_sidecar_txt', '')
                self.sidecarImg = meta.get('e2i_sidecar_img', '')
                printDBG("MergeDownloader sidecar enabled")

            if meta.get('e2i_mkv_chapters', False):
                self.makeMkvChapters = True
                if not self.sidecarTxt:
                    self.sidecarTxt = meta.get('e2i_sidecar_txt', '')
                printDBG("MergeDownloader MKV chapters enabled")

            if meta.get('e2i_cuts_chapters', False):
                self.makeCutsFile = True
                if not self.sidecarTxt:
                    self.sidecarTxt = meta.get('e2i_sidecar_txt', '')
                printDBG("MergeDownloader Enigma2 cuts enabled")

            self.channelName = ensureText(meta.get('e2i_channel_name', '')).strip()
            self.downloadChannelName = self.channelName
            self.downloadUseChannelName = bool(self.downloadChannelName)

            if self.downloadUseChannelName:
                printDBG("MergeDownloader channel name [%s]" % self.downloadChannelName)
        except Exception:
            printExc()

    def _sanitizeFileNamePart(self, value):
        value = ensureText(value)
        value = value.strip()
        value = re.sub(r'[\r\n\t]+', ' ', value)
        value = re.sub(r'\s+', ' ', value)
        value = re.sub(r'[\\/:\*\?"<>\|]', '_', value)
        value = value.strip(' ._-')
        return value

    def _applyDownloadChannelToFilePath(self, filePath):
        try:
            filePath = ensureText(filePath)

            if not self.downloadUseChannelName or not self.downloadChannelName:
                return filePath

            dirName = os.path.dirname(filePath)
            baseName = os.path.basename(filePath)
            titlePart, extPart = os.path.splitext(baseName)

            cleanChannel = self._sanitizeFileNamePart(self.downloadChannelName)
            cleanTitle = self._sanitizeFileNamePart(titlePart)

            if not cleanChannel or not cleanTitle:
                return filePath

            prefix = cleanChannel + ' - '
            if cleanTitle.startswith(prefix):
                newBaseName = cleanTitle + extPart
            else:
                newBaseName = prefix + cleanTitle + extPart

            if dirName:
                newPath = os.path.join(dirName, newBaseName)
            else:
                newPath = newBaseName

            printDBG("MergeDownloader filePath with channel [%s] -> [%s]" % (filePath, newPath))
            return newPath
        except Exception:
            printExc()
        return ensureText(filePath)

    def _writeTxtSidecar(self, filePath):
        try:
            if not self.sidecarTxt:
                printDBG("MergeDownloader sidecar TXT skipped: empty content")
                return

            basePath = ensureText(filePath).rsplit('.', 1)[0]
            txtPath = basePath + '.txt'

            if os.path.isfile(fsPath(txtPath)):
                printDBG("MergeDownloader sidecar TXT already exists [%s]" % txtPath)
                return

            if writeUtf8TextFile(txtPath, self.sidecarTxt):
                printDBG("MergeDownloader sidecar TXT saved [%s]" % txtPath)
            else:
                printDBG("MergeDownloader sidecar TXT save failed [%s]" % txtPath)
        except Exception:
            printExc("MergeDownloader sidecar TXT save failed")

    def _startImgSidecarDownload(self, filePath):
        try:
            if not self.sidecarImg:
                printDBG("MergeDownloader sidecar JPG skipped: empty URL")
                self._finishDownloadFlow()
                return

            basePath = ensureText(filePath).rsplit('.', 1)[0]
            jpgPath = basePath + '.jpg'

            if os.path.isfile(fsPath(jpgPath)):
                printDBG("MergeDownloader sidecar JPG already exists [%s]" % jpgPath)
                self._finishDownloadFlow()
                return

            imgUrl = shellQuote(self.sidecarImg)
            outPath = shellQuote(jpgPath)

            cmd = 'wget --header "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36" --no-check-certificate "{0}" -O "{1}" > /dev/null 2>&1'.format(imgUrl, outPath)
            printDBG("MergeDownloader sidecar JPG cmd[%s]" % cmd)

            self.waitingForSidecar = True
            self.sidecarConsole = eConsoleAppContainer()
            self.sidecarConsole_appClosed_conn = eConnectCallback(self.sidecarConsole.appClosed, boundFunction(self._imgSidecarFinished, jpgPath))
            self.sidecarConsole_stderrAvail_conn = eConnectCallback(self.sidecarConsole.stderrAvail, self._imgSidecarDataAvail)
            if hasattr(self.sidecarConsole, "setNice"):
                self.sidecarConsole.setNice(GetNice() + 2)
                self.sidecarConsole.execute(cmd)
            else:
                self.sidecarConsole.execute(E2PrioFix(cmd))
        except Exception:
            printExc("MergeDownloader sidecar JPG start failed")
            self._finishDownloadFlow()

    def _imgSidecarDataAvail(self, data):
        return

    def _imgSidecarFinished(self, jpgPath, code):
        printDBG("MergeDownloader._imgSidecarFinished code[%r]" % code)

        try:
            self.sidecarConsole_appClosed_conn = None
            self.sidecarConsole_stderrAvail_conn = None
            self.sidecarConsole = None
            self.waitingForSidecar = False

            if os.path.isfile(fsPath(jpgPath)):
                printDBG("MergeDownloader sidecar JPG saved [%s]" % jpgPath)
            else:
                printDBG("MergeDownloader sidecar JPG failed [%s]" % jpgPath)
        except Exception:
            printExc()

        self._finishDownloadFlow()

    def _finishDownloadFlow(self):
        try:
            self.onFinish()
        except Exception:
            printExc()
        self._cleanUp()

    def _getBasePath(self, filePath):
        return ensureText(filePath).rsplit('.', 1)[0]

    def _getMkvPath(self):
        return self._getBasePath(self.filePath) + '.mkv'

    def _getCutsPath(self, filePath):
        return ensureText(filePath) + '.cuts'

    def _moveFile(self, src, dst):
        try:
            srcPath = fsPath(src)
            dstPath = fsPath(dst)
            if srcPath == dstPath:
                return True
            if os.path.isfile(dstPath):
                rm(dstPath)
            os.rename(srcPath, dstPath)
            return os.path.isfile(dstPath)
        except Exception:
            printExc()
        return False

    def _normalizeChapterTitle(self, title):
        title = ensureText(title).strip()
        title = re.sub(r'\s+', ' ', title)
        if not title:
            title = 'Chapter'
        return title

    def _timeStrToMs(self, timeStr):
        parts = ensureText(timeStr).split(':')
        try:
            parts = [int(x) for x in parts]
        except Exception:
            return None

        if len(parts) == 2:
            hh = 0
            mm = parts[0]
            ss = parts[1]
        elif len(parts) == 3:
            hh = parts[0]
            mm = parts[1]
            ss = parts[2]
        else:
            return None

        return ((hh * 3600) + (mm * 60) + ss) * 1000

    def _msToPts(self, ms):
        return int(ms) * 90

    def _escapeFfmeta(self, txt):
        txt = ensureText(txt)
        txt = txt.replace('\\', '\\\\')
        txt = txt.replace('=', '\\=')
        txt = txt.replace(';', '\\;')
        txt = txt.replace('#', '\\#')
        txt = txt.replace('\n', ' ')
        txt = txt.replace('\r', ' ')
        return txt

    def _extractChaptersFromText(self, txt):
        chapters = []
        if not txt:
            return chapters

        workTxt = ensureText(txt)
        lines = workTxt.replace('\r', '\n').split('\n')
        seen = {}

        for line in lines:
            line = ensureText(line).strip()
            if not line:
                continue

            timeStr = ''
            title = ''

            m = re.match(r'^\[(?P<ts>(?:\d{1,2}:)?\d{1,2}:\d{2})\]\([^)]+\)\s*(?P<title>.+?)\s*$', line)
            if m:
                timeStr = m.group('ts')
                title = m.group('title').strip()
            else:
                m = re.match(r'^(?P<ts>(?:\d{1,2}:)?\d{1,2}:\d{2})\s+(?P<title>.+?)\s*$', line)
                if m:
                    timeStr = m.group('ts')
                    title = m.group('title').strip()
                else:
                    continue

            title = re.sub(r'^\-\s*', '', title)
            title = self._normalizeChapterTitle(title)

            startMs = self._timeStrToMs(timeStr)
            if startMs is None:
                continue
            if startMs in seen:
                continue

            seen[startMs] = True
            chapters.append({'start': startMs, 'title': title})

        chapters.sort(key=lambda item: item['start'])

        out = []
        prevStart = None
        for item in chapters:
            if prevStart is not None and item['start'] == prevStart:
                continue
            out.append(item)
            prevStart = item['start']

        if len(out) < 2:
            return []
        return out

    def _probeDurationMs(self, filePath):
        try:
            inPath = shellQuote(filePath)
            cmd = DMHelper.GET_FFMPEG_PATH() + ' -i "{0}" 2>&1 '.format(inPath)
            data = os.popen(cmd).read()
            data = ensureText(data)
            m = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', data)
            if m:
                hh = int(m.group(1))
                mm = int(m.group(2))
                ss = float(m.group(3))
                return int((((hh * 3600) + (mm * 60)) + ss) * 1000.0)
        except Exception:
            printExc()
        return 0

    def _buildFfmetadata(self, chapters, durationMs):
        lines = [';FFMETADATA1']
        idx = 0
        count = len(chapters)

        while idx < count:
            start = chapters[idx]['start']
            if idx + 1 < count:
                end = chapters[idx + 1]['start']
            else:
                end = durationMs

            if end <= start:
                end = start + 1000

            title = self._escapeFfmeta(chapters[idx]['title'])

            lines.append('[CHAPTER]')
            lines.append('TIMEBASE=1/1000')
            lines.append('START=%d' % start)
            lines.append('END=%d' % end)
            lines.append('title=%s' % title)
            idx += 1

        return '\n'.join(lines) + '\n'

    def _writeChapterMetadataFile(self):
        try:
            chapters = self._extractChaptersFromText(self.sidecarTxt)
            if len(chapters) < 2:
                printDBG("MergeDownloader no usable chapters found in description")
                return False

            durationMs = self._probeDurationMs(self.tempMergePath)
            self.mergedFileDurationMs = durationMs
            if durationMs <= 0:
                printDBG("MergeDownloader duration probe failed")
                return False

            lastStart = chapters[-1]['start']
            if durationMs <= lastStart:
                printDBG("MergeDownloader duration smaller/equal than last chapter start")
                return False

            self.chapterMetaPath = self._getBasePath(self.filePath) + '.chapters.ffmeta'
            ffmeta = self._buildFfmetadata(chapters, durationMs)

            if writeUtf8TextFile(self.chapterMetaPath, ffmeta):
                printDBG("MergeDownloader chapter metadata saved [%s]" % self.chapterMetaPath)
                return True
            else:
                printDBG("MergeDownloader chapter metadata save failed [%s]" % self.chapterMetaPath)
        except Exception:
            printExc("MergeDownloader _writeChapterMetadataFile failed")
        return False

    def _writeCutsFile(self, finalPath):
        try:
            chapters = self._extractChaptersFromText(self.sidecarTxt)
            if len(chapters) < 1:
                printDBG("MergeDownloader no usable cut markers found in description")
                return False

            cutsPath = self._getCutsPath(finalPath)

            f = open(fsPath(cutsPath), 'wb')
            try:
                for item in chapters:
                    pts = self._msToPts(item['start'])
                    if pts < 0:
                        continue
                    entry = struct.pack('>QI', pts, 2)
                    f.write(entry)
            finally:
                f.close()

            printDBG("MergeDownloader cuts saved [%s]" % cutsPath)
            return os.path.isfile(fsPath(cutsPath)) and os.path.getsize(fsPath(cutsPath)) > 0
        except Exception:
            printExc("MergeDownloader _writeCutsFile failed")
        return False

    def start(self, url, filePath, params={}):
        self.downloaderParams = params
        self.fileExtension = ''  # should be implemented in future
        self.url = url
        self.chapterMetaPath = ''
        self.finalizedPath = ''
        self.postProcessMode = 'merge'
        self.mergedFileDurationMs = 0
        self.originalFilePath = ensureText(filePath)

        self.multi = {'urls': [], 'files': [], 'remote_size': [], 'remote_content_type': [], 'local_size': []}
        self.currIdx = 0

        meta = strwithmeta(url).meta
        self._prepareSidecarData(meta)

        self.filePath = self._applyDownloadChannelToFilePath(self.originalFilePath)
        self.tempMergePath = self._getBasePath(self.filePath) + '.iptv.merge.tmp.mp4'

        try:
            urlsKeys = self.url.split('merge://')[1].split('|')
            idx = 0
            for item in urlsKeys:
                self.multi['urls'].append(meta[item])
                tmpFilePath = self.filePath + '.iptv.tmp.{0}.dash'.format(idx)
                self.multi['files'].append(tmpFilePath)
                self.multi['remote_size'].append(-1)
                self.multi['local_size'].append(-1)
                self.multi['remote_content_type'].append('')
                idx += 1
        except Exception:
            printExc()

        self.doStartDownload()
        return BaseDownloader.CODE_OK

    def doStartDownload(self):
        self.outData = ''
        self.contentType = 'unknown'
        filePath = self.multi['files'][self.currIdx]
        url = self.multi['urls'][self.currIdx]

        info = ""
        retries = 0

        cmd = DMHelper.getBaseWgetCmd(self.downloaderParams) + (' %s -t %d ' % (info, retries)) + '"' + shellQuote(url) + '" -O "' + shellQuote(filePath) + '" > /dev/null'
        printDBG("doStartDownload cmd[%s]" % cmd)

        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._dataAvail)
        if hasattr(self.console, "setNice"):
            self.console.setNice(GetNice() + 2)
            self.console.execute(cmd)
        else:
            self.console.execute(E2PrioFix(cmd))

        self.status = DMHelper.STS.DOWNLOADING
        self.onStart()
        return BaseDownloader.CODE_OK

    def doStartPostProcess(self):
        self.postProcessMode = 'merge'
        cmd = DMHelper.GET_FFMPEG_PATH() + ' '
        for item in self.multi['files']:
            cmd += ' -i "{0}" '.format(shellQuote(item))
        cmd += ' -map 0:0 -map 1:0 -vcodec copy -acodec copy "{0}" >/dev/null 2>&1 '.format(shellQuote(self.tempMergePath))
        printDBG("doStartPostProcess cmd[%s]" % cmd)
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        if hasattr(self.console, "setNice"):
            self.console.setNice(GetNice() + 2)
            self.console.execute(cmd)
        else:
            self.console.execute(E2PrioFix(cmd))

    def _startMkvChapterMux(self):
        self.postProcessMode = 'chapters'
        mkvPath = self._getMkvPath()
        cmd = DMHelper.GET_FFMPEG_PATH() + ' -i "{0}" -i "{1}" -map 0 -c copy -map_metadata 1 "{2}" >/dev/null 2>&1 '.format(shellQuote(self.tempMergePath), shellQuote(self.chapterMetaPath), shellQuote(mkvPath))
        printDBG("MergeDownloader _startMkvChapterMux cmd[%s]" % cmd)
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        if hasattr(self.console, "setNice"):
            self.console.setNice(GetNice() + 2)
            self.console.execute(cmd)
        else:
            self.console.execute(E2PrioFix(cmd))

    def _finalizeSuccess(self, finalPath):
        self.filePath = ensureText(finalPath)
        self.finalizedPath = ensureText(finalPath)
        self.localFileSize = DMHelper.getFileSize(fsPath(finalPath))
        if self.localFileSize > 0:
            self.remoteFileSize = self.localFileSize
            self.status = DMHelper.STS.DOWNLOADED

            self._writeTxtSidecar(finalPath)

            if self.makeCutsFile:
                self._writeCutsFile(finalPath)

            if self.sidecarEnabled and self.sidecarImg:
                self._startImgSidecarDownload(finalPath)
                return
        else:
            self.status = DMHelper.STS.INTERRUPTED

        self._finishDownloadFlow()

    def _finalizeMp4Fallback(self):
        if self._moveFile(self.tempMergePath, self.filePath):
            printDBG("MergeDownloader fallback finalized as original target [%s]" % self.filePath)
            self._finalizeSuccess(self.filePath)
            return True
        return False

    def _dataAvail(self, data):
        if None is data:
            return
        self.outData += ensureText(data)
        if 'Saving to:' in self.outData:
            self.console_stderrAvail_conn = None
            lines = self.outData.replace('\r', '\n').split('\n')
            for idx in range(len(lines)):
                if 'Length:' in lines[idx]:
                    match = re.search(r" ([0-9]+?) ", lines[idx])
                    if match:
                        self.multi['remote_size'][self.currIdx] = int(match.group(1))
                    match = re.search(r"(\[[^]]+?\])", lines[idx])
                    if match:
                        self.multi['remote_content_type'][self.currIdx] = match.group(1)
            self.outData = ''

    def _terminate(self):
        printDBG("MergeDownloader._terminate")
        if None is not self.iptv_sys:
            self.iptv_sys.kill()
            self.iptv_sys = None

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

        if self.status in [DMHelper.STS.DOWNLOADING, DMHelper.STS.POSTPROCESSING]:
            if self.console:
                if hasattr(self.console, "sendCtrlC"):
                    self.console.sendCtrlC()  # kill produce zombies
                elif hasattr(self.console, "kill"):
                    self.console.kill()  # kill produce zombies
                self._cmdFinished(-1, True)
            return BaseDownloader.CODE_OK
        return BaseDownloader.CODE_NOT_DOWNLOADING

    def _cmdFinished(self, code, terminated=False):
        printDBG("MergeDownloader._cmdFinished code[%r] terminated[%r] mode[%s]" % (code, terminated, self.postProcessMode))
        # break circular references
        if None is not self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
            self.console = None

        if terminated:
            self.status = DMHelper.STS.INTERRUPTED
            self._cleanUp()
            return

        if self.status == DMHelper.STS.POSTPROCESSING:
            if self.postProcessMode == 'merge':
                mergedSize = DMHelper.getFileSize(fsPath(self.tempMergePath))
                printDBG("POSTPROCESSING merge finished tempMergePath[%s] localFileSize[%r] code[%r]" % (self.tempMergePath, mergedSize, code))

                if mergedSize > 0 and code == 0:
                    if self.makeMkvChapters and self._writeChapterMetadataFile():
                        self._startMkvChapterMux()
                        return

                    if self._finalizeMp4Fallback():
                        return
                    self.status = DMHelper.STS.INTERRUPTED
                else:
                    self.status = DMHelper.STS.INTERRUPTED

            elif self.postProcessMode == 'chapters':
                mkvPath = self._getMkvPath()
                mkvSize = DMHelper.getFileSize(fsPath(mkvPath))
                printDBG("POSTPROCESSING chapters finished mkvPath[%s] localFileSize[%r] code[%r]" % (mkvPath, mkvSize, code))

                if mkvSize > 0 and code == 0:
                    self._finalizeSuccess(mkvPath)
                    return

                printDBG("MergeDownloader chapter mux failed -> fallback to original target name")
                if self._finalizeMp4Fallback():
                    return
                self.status = DMHelper.STS.INTERRUPTED

        elif code == 0:
            if (self.currIdx + 1) < len(self.multi['urls']):
                self.currIdx += 1
                self.doStartDownload()
                return
            else:
                self.status = DMHelper.STS.POSTPROCESSING
                self.doStartPostProcess()
                return
        else:
            self.status = DMHelper.STS.INTERRUPTED

        if not terminated:
            self._finishDownloadFlow()

    def _localFileSize(self, update=True):
        printDBG(">>>>>>>>>>>>>>>>>>>>> _localFileSize [%r] loacalSize[%r] = %r" % (self.localFileSize, self.currIdx, self.multi['local_size']))
        if self.localFileSize > 0:
            return self.localFileSize
        else:
            if update and self.currIdx < len(self.multi['files']):
                self.multi['local_size'][self.currIdx] = DMHelper.getFileSize(fsPath(self.multi['files'][self.currIdx]))
            localFileSize = 0
            for item in self.multi['local_size']:
                if item > 0:
                    localFileSize += item
            return localFileSize
        return 0

    def _remoteFileSize(self):
        printDBG(">>>>>>>>>>>>>>>>>>>>> _remoteFileSize [%r]" % (self.remoteFileSize))
        if self.remoteFileSize > 0:
            return self.remoteFileSize
        else:
            remoteFileSize = 0
            num = 0
            for item in self.multi['remote_size']:
                if item > 0:
                    remoteFileSize += item
                    num += 1
            if num == len(self.multi['remote_size']):
                return remoteFileSize
        return -1

    def updateStatistic(self):
        prevUpdateTime = self.lastUpadateTime
        newTime = datetime.datetime.now()
        # calculate downloaded Speed
        if prevUpdateTime:
            localFileSize = self._localFileSize()
            deltaSize = localFileSize - self.prevLocalFileSize
            deltaTime = (newTime - prevUpdateTime).seconds
            if deltaTime > 0:
                self.downloadSpeed = deltaSize / deltaTime
        self.lastUpadateTime = newTime
        self.prevLocalFileSize = self._localFileSize()

    def getRemoteFileSize(self):
        return self._remoteFileSize()

    def getLocalFileSize(self, update=False):
        return self._localFileSize(update)

    def getDownloadSpeed(self):
        return self.downloadSpeed

    def getPlayableFileSize(self):
        self.getLocalFileSize()
        return self.localFileSize
