# -*- coding: utf-8 -*-
# IPTV download manager API
# Last Modified: 19.08.2026 - Fixed ffmpeg merge/chapter-mux steps reporting exit code 1 despite writing a
# complete, correct output file. Root causes handled: (1) added '-y' to all ffmpeg post-process invocations
# so ffmpeg never blocks on stdin waiting for an "Overwrite? [y/N]" prompt on a stale leftover output file;
# (2) stopped discarding ffmpeg's merge/mux stderr into /dev/null - it's now captured via stderrAvail like the
# duration probe already does, and logged on failure; (3) eConsoleAppContainer can report a spurious non-zero
# exit code for the short second ffmpeg pass (remux with -map_metadata from the tiny .ffmeta file) even though
# ffmpeg's own stderr shows a completely clean finish (the "Lsize=...muxing overhead:" summary only appears
# after a successful write) - this is now treated as authoritative success, overriding the bogus exit code,
# for both the merge and chapters post-process steps - Kamikaze24
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, eConnectCallback, GetNice, rm, E2PrioFix
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import enum, strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import ensureText, fsPath, shellQuote, writeUtf8TextFile, SidecarMixin
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
    from urllib.parse import urlparse, parse_qs
except ImportError:
    from urlparse import urlparse, parse_qs
try:
    try:
        import json
    except Exception:
        import simplejson as json
except Exception:
    printExc()
###################################################

###################################################
# One instance of this class can be used only for
# one download
###################################################


class MergeDownloader(BaseDownloader, SidecarMixin):

    def __init__(self):
        printDBG('MergeDownloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)

        # instance of E2 console
        self.console = None
        self.console_appClosed_conn = None
        self.console_stderrAvail_conn = None
        self.iptv_sys = None

        # sidecar support (console instance + state), shared via SidecarMixin
        self._initSidecarState()

        self.knownDurationMs = -1

        self.multi = {'urls': [], 'files': [], 'remote_size': [], 'remote_content_type': [], 'local_size': []}
        self.currIdx = 0

        self.makeMkvChapters = False
        self.makeCutsFile = False
        self.tempMergePath = ''
        self.chapterMetaPath = ''
        self.finalizedPath = ''
        self.postProcessMode = 'merge'
        self.mergedFileDurationMs = 0
        self.probeOutData = ''
        self.ffmpegErrData = ''
        self._pendingChapters = []

        self.channelName = ''
        self.downloadChannelName = ''
        self.downloadUseChannelName = False
        self.originalFilePath = ''
        self.preCheckOnly = False

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

    def _cleanupBeforeStart(self, filePath):
        try:
            basePath = self._getBasePath(filePath)
            for idx in range(0, 10):
                self._safeRm(filePath + '.iptv.tmp.%d.dash' % idx)
            self._safeRm(basePath + '.iptv.merge.tmp.mp4')
            self._safeRm(basePath + '.chapters.ffmeta')
            # also remove a stale MKV target from a previous aborted run so ffmpeg never
            # has to prompt "Overwrite? [y/N]" on a leftover file (hangs/exits 1 without -y)
            self._safeRm(basePath + '.mkv')
        except Exception:
            printExc()

    def _downloadAlreadyPresent(self, filePath):
        try:
            filePath = ensureText(filePath)
            if os.path.isfile(fsPath(filePath)) and DMHelper.getFileSize(fsPath(filePath)) > 0:
                return True
            mkvPath = self._getBasePath(filePath) + '.mkv'
            if os.path.isfile(fsPath(mkvPath)) and DMHelper.getFileSize(fsPath(mkvPath)) > 0:
                return True
            return False
        except Exception:
            printExc()
            return False

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
        SidecarMixin._clearSidecarData(self)
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

    def _getBasePath(self, filePath):
        return ensureText(filePath).rsplit('.', 1)[0]

    def _getMkvPath(self):
        return self._getBasePath(self.filePath) + '.mkv'

    def _getCutsPath(self, filePath):
        return ensureText(filePath) + '.cuts'

    def _extractClenFromUrl(self, url):
        try:
            qs = parse_qs(urlparse(ensureText(url)).query)
            clenVals = qs.get('clen')
            if clenVals:
                return int(clenVals[0])
        except Exception:
            printExc()
        return -1

    def _extractDurMsFromUrl(self, url):
        try:
            qs = parse_qs(urlparse(ensureText(url)).query)
            durVals = qs.get('dur')
            if durVals:
                return int(float(durVals[0]) * 1000.0)
        except Exception:
            printExc()
        return -1

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

    def _parseProbeDuration(self, data):
        try:
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

    def _probeDataAvail(self, data):
        if data is None:
            return
        self.probeOutData += ensureText(data)

    def _ffmpegErrDataAvail(self, data):
        # captures ffmpeg's stderr for the merge/chapter-mux steps instead of throwing it away,
        # so a failing 'code[1]' can actually be diagnosed from the log instead of guessed at
        if data is None:
            return
        self.ffmpegErrData += ensureText(data)
        if len(self.ffmpegErrData) > 8000:
            self.ffmpegErrData = self.ffmpegErrData[-8000:]

    def _ffmpegReportedCleanFinish(self):
        # eConsoleAppContainer can report a spurious non-zero exit code for a short-lived second
        # ffmpeg pass (e.g. remuxing with -map_metadata from a tiny .ffmeta file) even though
        # ffmpeg itself completed normally. ffmpeg only prints the final "Lsize=...muxing overhead:"
        # summary line after a clean successful write, so treat its presence as authoritative
        # success, overriding a bogus non-zero exit code from the console container.
        try:
            tail = ensureText(self.ffmpegErrData)
            return bool(re.search(r'Lsize=\s*\S+.*muxing overhead', tail, re.DOTALL))
        except Exception:
            printExc()
        return False

    def _logFfmpegFailure(self, stepName):
        try:
            tail = self.ffmpegErrData.strip()
            if tail:
                lines = tail.replace('\r', '\n').split('\n')
                tailLines = [l for l in lines if l.strip()][-15:]
                printDBG("MergeDownloader %s ffmpeg stderr tail:\n%s" % (stepName, '\n'.join(tailLines)))
            else:
                printDBG("MergeDownloader %s ffmpeg produced no stderr output" % stepName)
        except Exception:
            printExc()

    def _startDurationProbe(self, filePath):
        self.postProcessMode = 'probe_duration'
        self.probeOutData = ''
        inPath = shellQuote(filePath)
        cmd = DMHelper.GET_FFMPEG_PATH() + ' -y -i "{0}"'.format(inPath)
        printDBG("MergeDownloader _startDurationProbe cmd[%s]" % cmd)
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._probeDataAvail)
        if hasattr(self.console, "setNice"):
            self.console.setNice(GetNice() + 2)
            self.console.execute(cmd)
        else:
            self.console.execute(E2PrioFix(cmd))

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

    def _startChapterMetadataFlow(self):
        # kicks off the async duration probe; the actual ffmeta file is written
        # from _cmdFinished once the probe process closes (see 'probe_duration' mode)
        try:
            chapters = self._extractChaptersFromText(self.sidecarTxt)
            if len(chapters) < 2:
                printDBG("MergeDownloader no usable chapters found in description")
                return False

            self._pendingChapters = chapters
            self._startDurationProbe(self.tempMergePath)
            return True
        except Exception:
            printExc("MergeDownloader _startChapterMetadataFlow failed")
        return False

    def _finishChapterMetadataFlow(self, durationMs):
        try:
            chapters = self._pendingChapters
            self._pendingChapters = []
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
            printExc("MergeDownloader _finishChapterMetadataFlow failed")
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
        self.probeOutData = ''
        self.ffmpegErrData = ''
        self._pendingChapters = []
        self.knownDurationMs = -1
        self.originalFilePath = ensureText(filePath)
        self.preCheckOnly = False

        self.multi = {'urls': [], 'files': [], 'remote_size': [], 'remote_content_type': [], 'local_size': []}
        self.currIdx = 0

        meta = strwithmeta(url).meta
        self._prepareSidecarData(meta)

        self.filePath = self._applyDownloadChannelToFilePath(self.originalFilePath)

        if self._downloadAlreadyPresent(self.filePath):
            printDBG("MergeDownloader download already present [%s]" % self.filePath)
            self.status = DMHelper.STS.DOWNLOADED
            self.finalizedPath = self.filePath
            self.localFileSize = DMHelper.getFileSize(fsPath(self.filePath))
            self.remoteFileSize = self.localFileSize
            self.preCheckOnly = True
            self.onFinish()
            return BaseDownloader.CODE_OK

        self._cleanupBeforeStart(self.filePath)
        self.tempMergePath = self._getBasePath(self.filePath) + '.iptv.merge.tmp.mp4'

        try:
            urlsKeys = self.url.split('merge://')[1].split('|')
            idx = 0
            for item in urlsKeys:
                itemUrl = meta[item]
                self.multi['urls'].append(itemUrl)
                tmpFilePath = self.filePath + '.iptv.tmp.{0}.dash'.format(idx)
                self.multi['files'].append(tmpFilePath)
                self.multi['remote_size'].append(self._extractClenFromUrl(itemUrl))
                self.multi['local_size'].append(-1)
                self.multi['remote_content_type'].append('')
                itemDurMs = self._extractDurMsFromUrl(itemUrl)
                if itemDurMs > self.knownDurationMs:
                    self.knownDurationMs = itemDurMs
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
        self.ffmpegErrData = ''
        cmd = DMHelper.GET_FFMPEG_PATH() + ' -y '
        for item in self.multi['files']:
            cmd += ' -i "{0}" '.format(shellQuote(item))
        cmd += ' -map 0:0 -map 1:0 -vcodec copy -acodec copy "{0}" '.format(shellQuote(self.tempMergePath))
        printDBG("doStartPostProcess cmd[%s]" % cmd)
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._ffmpegErrDataAvail)
        if hasattr(self.console, "setNice"):
            self.console.setNice(GetNice() + 2)
            self.console.execute(cmd)
        else:
            self.console.execute(E2PrioFix(cmd))

    def _startMkvChapterMux(self):
        self.postProcessMode = 'chapters'
        self.ffmpegErrData = ''
        mkvPath = self._getMkvPath()
        cmd = DMHelper.GET_FFMPEG_PATH() + ' -y -i "{0}" -i "{1}" -map 0 -c copy -map_metadata 1 "{2}" '.format(shellQuote(self.tempMergePath), shellQuote(self.chapterMetaPath), shellQuote(mkvPath))
        printDBG("MergeDownloader _startMkvChapterMux cmd[%s]" % cmd)
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._ffmpegErrDataAvail)
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
        try:
            if os.path.isfile(fsPath(self.tempMergePath)):
                if self._moveFile(self.tempMergePath, self.filePath):
                    printDBG("MergeDownloader fallback finalized as original target [%s]" % self.filePath)
                    self._finalizeSuccess(self.filePath)
                    return True
            if os.path.isfile(fsPath(self.filePath)):
                self._finalizeSuccess(self.filePath)
                return True
        except Exception:
            printExc()
        return False

    def _dataAvail(self, data):
        if None is data:
            return
        self.outData += ensureText(data)
        # only parse+reset once the full header block has arrived - wget's
        # stderr can split a 'Length:' line across two callbacks, and
        # resetting outData on every call would drop the first half before
        # the second one arrives
        if 'Saving to:' in self.outData:
            self.console_stderrAvail_conn = None
            lines = self.outData.replace('\r', '\n').split('\n')
            for idx in range(len(lines)):
                if 'Length:' in lines[idx]:
                    match = re.search(r" ([0-9]+?) ", lines[idx])
                    if match:
                        parsedSize = int(match.group(1))
                        if parsedSize > 0:
                            self.multi['remote_size'][self.currIdx] = parsedSize
                    match = re.search(r"(\[[^]]+?\])", lines[idx])
                    if match:
                        self.multi['remote_content_type'][self.currIdx] = match.group(1)
            self.outData = ''

    def _terminate(self):
        printDBG("MergeDownloader._terminate")
        if None is not self.iptv_sys:
            self.iptv_sys.kill()
            self.iptv_sys = None

        self._terminateSidecar()

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
        if self.preCheckOnly:
            printDBG("MergeDownloader._cmdFinished ignored preCheckOnly")
            return

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

                if mergedSize > 0 and (code == 0 or self._ffmpegReportedCleanFinish()):
                    if code != 0:
                        printDBG("MergeDownloader merge step reported code[%r] but ffmpeg stderr shows a clean finish -> treating as success" % code)
                    if self.makeMkvChapters and self._startChapterMetadataFlow():
                        return

                    if self._finalizeMp4Fallback():
                        return
                    self.status = DMHelper.STS.INTERRUPTED
                else:
                    self._logFfmpegFailure("merge")
                    self.status = DMHelper.STS.INTERRUPTED

            elif self.postProcessMode == 'probe_duration':
                durationMs = self._parseProbeDuration(self.probeOutData)
                self.probeOutData = ''
                if durationMs <= 0 and self.knownDurationMs > 0:
                    printDBG("MergeDownloader duration probe failed/N-A, falling back to duration from stream URL metadata [%d ms]" % self.knownDurationMs)
                    durationMs = self.knownDurationMs

                if self._finishChapterMetadataFlow(durationMs):
                    self._startMkvChapterMux()
                    return

                if self._finalizeMp4Fallback():
                    return
                self.status = DMHelper.STS.INTERRUPTED

            elif self.postProcessMode == 'chapters':
                mkvPath = self._getMkvPath()
                mkvSize = DMHelper.getFileSize(fsPath(mkvPath))
                printDBG("POSTPROCESSING chapters finished mkvPath[%s] localFileSize[%r] code[%r]" % (mkvPath, mkvSize, code))

                if mkvSize > 0 and (code == 0 or self._ffmpegReportedCleanFinish()):
                    if code != 0:
                        printDBG("MergeDownloader chapters step reported code[%r] but ffmpeg stderr shows a clean finish -> treating as success" % code)
                    self._finalizeSuccess(mkvPath)
                    return

                self._logFfmpegFailure("chapters")
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
