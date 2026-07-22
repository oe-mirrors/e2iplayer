# -*- coding: utf-8 -*-
# IPTV download manager API
# Last Modified: 19.07.2026 - MKV FFmpeg postprocess + fsPath/shellQuote handling + robust wget working check - Kamikaze24
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, eConnectCallback, GetNice, rm, E2PrioFix
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import enum, strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
###################################################

###################################################
# FOREIGN import
###################################################
from Tools.Directories import fileExists
from Tools.BoundFunction import boundFunction
from enigma import eConsoleAppContainer
from time import sleep
import re
import datetime
import os
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


class WgetDownloader(BaseDownloader):
    # wget status
    WGET_STS = enum(NONE='WGET_NONE',
                    CONNECTING='WGET_CONNECTING',
                    DOWNLOADING='WGET_DOWNLOADING',
                    ENDED='WGET_ENDED')
    # wget status
    INFO = enum(FROM_FILE='INFO_FROM_FILE',
                FROM_DOTS='INFO_FROM_DOTS')

    def __init__(self):
        printDBG('WgetDownloader.__init__ ')
        BaseDownloader.__init__(self)

        self.wgetStatus = self.WGET_STS.NONE
        # instance of E2 console
        self.console = None
        self.console_appClosed_conn = None
        self.console_stderrAvail_conn = None
        self.iptv_sys = None
        self.curContinueRetry = 0
        self.maxContinueRetry = 0
        self.downloadCmd = ''
        self.remoteContentType = None
        self.lastErrorCode = None
        self.lastErrorDesc = ''

        # sidecar console instance
        self.sidecarConsole = None
        self.sidecarConsole_appClosed_conn = None
        self.sidecarConsole_stderrAvail_conn = None

        # sidecar support
        self.sidecarEnabled = False
        self.sidecarTxt = ''
        self.sidecarImg = ''
        self.waitingForSidecar = False

        # ffmpeg postprocess support
        self.ffmpegPostEnabled = False
        self.ffmpegContainer = 'mkv'
        self.postProcessMode = ''
        self.tempRemuxPath = ''
        self.finalizedPath = ''

    def __del__(self):
        printDBG("WgetDownloader.__del__ ")

    def getName(self):
        return "wget"

    def getLastError(self):
        return self.lastErrorCode, self.lastErrorDesc

    def _setLastError(self, code):
        # map Exit Status to message - https://www.gnu.org/software/wget/manual/html_node/Exit-Status.html
        self.lastErrorCode = code
        if code == 0:
            self.lastErrorDesc = "No problems occurred."
        elif code == 1:
            self.lastErrorDesc = "Generic error code."
        elif code == 2:
            self.lastErrorDesc = "Parse error."
        elif code == 3:
            self.lastErrorDesc = "File I/O error."
        elif code == 4:
            self.lastErrorDesc = "Network failure."
        elif code == 5:
            self.lastErrorDesc = "SSL verification failure."
        elif code == 6:
            self.lastErrorDesc = "Username/password authentication failure."
        elif code == 7:
            self.lastErrorDesc = "Protocol errors."
        elif code == 8:
            self.lastErrorDesc = "Server issued an error response."
        else:
            self.lastErrorDesc = 'Unknown error code.'

    def isWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system(DMHelper.GET_WGET_PATH() + " --help 2>&1 ", boundFunction(self._checkWorkingCallBack, callBackFun))

    def getMimeType(self):
        return self.remoteContentType

    def _checkWorkingCallBack(self, callBackFun, code, data):
        reason = ''
        sts = True
        data = ensureText(data)
        low = data.lower()
        if code != 0 and not low.strip():
            sts = False
            reason = data
        self.iptv_sys = None
        callBackFun(sts, reason)

    def _clearSidecarData(self):
        self.sidecarEnabled = False
        self.sidecarTxt = ''
        self.sidecarImg = ''
        self.waitingForSidecar = False

    def _clearPostData(self):
        self.ffmpegPostEnabled = False
        self.ffmpegContainer = 'mkv'
        self.postProcessMode = ''
        self.tempRemuxPath = ''
        self.finalizedPath = ''

    def _prepareSidecarData(self, meta):
        self._clearSidecarData()
        try:
            if meta.get('e2i_sidecar_enabled', False):
                self.sidecarEnabled = True
                self.sidecarTxt = meta.get('e2i_sidecar_txt', '')
                self.sidecarImg = meta.get('e2i_sidecar_img', '')
                printDBG("WgetDownloader sidecar enabled")
        except Exception:
            printExc()

    def _preparePostData(self, meta):
        self._clearPostData()
        try:
            if meta.get('e2i_postprocess_ffmpeg', False) or str(meta.get('e2i_postprocess_ffmpeg', '')) == '1':
                self.ffmpegPostEnabled = True
                self.ffmpegContainer = ensureText(meta.get('e2i_postprocess_container', 'mkv')).strip().lower()
                if not self.ffmpegContainer:
                    self.ffmpegContainer = 'mkv'
                printDBG("WgetDownloader ffmpeg postprocess enabled container[%s]" % self.ffmpegContainer)
        except Exception:
            printExc()

    def _getBasePath(self, filePath):
        return ensureText(filePath).rsplit('.', 1)[0]

    def _getMkvPath(self):
        return self._getBasePath(self.filePath) + '.mkv'

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

    def _removeSourceFile(self):
        try:
            if self.filePath and os.path.isfile(fsPath(self.filePath)):
                rm(fsPath(self.filePath))
                printDBG("WgetDownloader source file removed [%s]" % self.filePath)
                return True
        except Exception:
            printExc()
        return False

    def _cleanUp(self):
        try:
            if self.tempRemuxPath and os.path.isfile(fsPath(self.tempRemuxPath)):
                rm(fsPath(self.tempRemuxPath))
        except Exception:
            printExc()

    def _writeTxtSidecar(self, filePath):
        try:
            if not self.sidecarTxt:
                printDBG("WgetDownloader sidecar TXT skipped: empty content")
                return

            basePath = ensureText(filePath).rsplit('.', 1)[0]
            txtPath = basePath + '.txt'

            if os.path.isfile(fsPath(txtPath)):
                printDBG("WgetDownloader sidecar TXT already exists [%s]" % txtPath)
                return

            if writeUtf8TextFile(txtPath, self.sidecarTxt):
                printDBG("WgetDownloader sidecar TXT saved [%s]" % txtPath)
            else:
                printDBG("WgetDownloader sidecar TXT save failed [%s]" % txtPath)
        except Exception:
            printExc("WgetDownloader sidecar TXT save failed")

    def _imgSidecarDataAvail(self, data):
        return

    def _imgSidecarFinished(self, jpgPath, code):
        printDBG("WgetDownloader._imgSidecarFinished code[%r]" % code)

        try:
            # break circular references
            self.sidecarConsole_appClosed_conn = None
            self.sidecarConsole_stderrAvail_conn = None
            self.sidecarConsole = None
            self.waitingForSidecar = False

            if os.path.isfile(fsPath(jpgPath)):
                printDBG("WgetDownloader sidecar JPG saved [%s]" % jpgPath)
            else:
                printDBG("WgetDownloader sidecar JPG failed [%s]" % jpgPath)
        except Exception:
            printExc()

        self._finishDownloadFlow()

    def _startImgSidecarDownload(self, filePath):
        try:
            if not self.sidecarImg:
                printDBG("WgetDownloader sidecar JPG skipped: empty URL")
                self._finishDownloadFlow()
                return

            basePath = ensureText(filePath).rsplit('.', 1)[0]
            jpgPath = basePath + '.jpg'

            if os.path.isfile(fsPath(jpgPath)):
                printDBG("WgetDownloader sidecar JPG already exists [%s]" % jpgPath)
                self._finishDownloadFlow()
                return

            cmd = 'wget --header "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36" --no-check-certificate "%s" -O "%s" > /dev/null 2>&1' % (shellQuote(self.sidecarImg), shellQuote(jpgPath))
            printDBG("WgetDownloader sidecar JPG cmd[%s]" % cmd)

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
            printExc("WgetDownloader sidecar JPG start failed")
            self._finishDownloadFlow()

    def _finishDownloadFlow(self):
        try:
            self.onFinish()
        except Exception:
            printExc()
        self._cleanUp()

    def doStartPostProcess(self):
        self.postProcessMode = 'remux'
        self.tempRemuxPath = self._getBasePath(self.filePath) + '.iptv.remux.tmp.mkv'

        cmd = DMHelper.GET_FFMPEG_PATH() + ' '
        cmd += ' -i "%s" ' % shellQuote(self.filePath)
        cmd += ' -map 0:v -map 0:a? -vcodec copy -acodec copy "%s" >/dev/null 2>&1 ' % shellQuote(self.tempRemuxPath)

        printDBG("WgetDownloader doStartPostProcess cmd[%s]" % cmd)

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

            if self.sidecarEnabled and self.sidecarImg:
                self._startImgSidecarDownload(finalPath)
                return
        else:
            self.status = DMHelper.STS.INTERRUPTED

        self._finishDownloadFlow()

    def _finalizeOriginalFallback(self):
        self.localFileSize = DMHelper.getFileSize(fsPath(self.filePath))
        if self.localFileSize > 0:
            self.remoteFileSize = self.localFileSize
            self.status = DMHelper.STS.DOWNLOADED

            self._writeTxtSidecar(self.filePath)

            if self.sidecarEnabled and self.sidecarImg:
                self._startImgSidecarDownload(self.filePath)
                return True

            self._finishDownloadFlow()
            return True
        return False

    def start(self, url, filePath, params={}, info_from=None, retries=0):
        '''
            Owervrite start from BaseDownloader
        '''
        self.url = url
        self.filePath = filePath
        self.downloaderParams = params
        self.fileExtension = ''  # should be implemented in future

        self.outData = ''
        self.contentType = 'unknown'
        self.postProcessMode = ''
        self.tempRemuxPath = ''
        self.finalizedPath = ''
        if None is info_from:
            info_from = WgetDownloader.INFO.FROM_FILE
        self.infoFrom = info_from

        meta = strwithmeta(url).meta
        self._prepareSidecarData(meta)
        self._preparePostData(meta)

        if self.infoFrom == WgetDownloader.INFO.FROM_DOTS:
            info = "--progress=dot:default"
        else:
            info = ""

        # remove file if exists
        if fileExists(self.filePath):
            rm(self.filePath)

        self.downloadCmd = DMHelper.getBaseWgetCmd(self.downloaderParams) + (' %s -t %d ' % (info, retries)) + '"' + self.url + '" -O "' + self.filePath + '" > /dev/null'
        printDBG("Download cmd[%s]" % self.downloadCmd)

        if self.downloaderParams.get('iptv_wget_continue', False):
            self.maxContinueRetry = 3

        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._dataAvail)
        if hasattr(self.console, "setNice"):
            self.console.setNice(GetNice() + 2)
            self.console.execute(self.downloadCmd)
        else:
            self.console.execute(E2PrioFix(self.downloadCmd))

        self.wgetStatus = self.WGET_STS.CONNECTING
        self.status = DMHelper.STS.DOWNLOADING

        self.onStart()
        return BaseDownloader.CODE_OK

    def _dataAvail(self, data):
        if data is None:
            return

        text = ensureText(data)
        if not text:
            return

        self.outData += text
        if self.infoFrom == WgetDownloader.INFO.FROM_FILE:
            if 'Saving to:' in self.outData:
                self.console_stderrAvail_conn = None
                lines = self.outData.replace('\r', '\n').split('\n')
                for idx in range(len(lines)):
                    if 'Length:' in lines[idx]:
                        match = re.search(r" ([0-9]+?) ", lines[idx])
                        if match:
                            self.remoteFileSize = int(match.group(1))
                        match = re.search(r"(\[[^]]+?\])", lines[idx])
                        if match:
                            self.remoteContentType = match.group(1)
                self.outData = ''
        elif self.WGET_STS.CONNECTING == self.wgetStatus:
            lines = self.outData.replace('\r', '\n').split('\n')
            for idx in range(len(lines)):
                if lines[idx].startswith('Length:'):
                    match = re.search(r"Length: ([0-9]+?) \([^)]+?\) (\[[^]]+?\])", lines[idx])
                    if match:
                        self.remoteFileSize = int(match.group(1))
                        self.remoteContentType = match.group(2)
                elif lines[idx].startswith('Saving to:'):
                    if len(lines) > idx:
                        self.outData = '\n'.join(lines[idx + 1:])
                    else:
                        self.outData = ''
                    self.wgetStatus = self.WGET_STS.DOWNLOADING
                    if self.infoFrom != WgetDownloader.INFO.FROM_DOTS:
                        self.console_stderrAvail_conn = None
                    break

    def _terminate(self):
        printDBG("WgetDownloader._terminate")
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

        if DMHelper.STS.DOWNLOADING == self.status or DMHelper.STS.POSTPROCESSING == self.status:
            if self.console:
                if hasattr(self.console, "sendCtrlC"):
                    self.console.sendCtrlC()  # kill produce zombies
                elif hasattr(self.console, "kill"):
                    self.console.kill()  # kill produce zombies
                self._cmdFinished(-1, True)
                return BaseDownloader.CODE_OK

        return BaseDownloader.CODE_NOT_DOWNLOADING

    def _cmdFinished(self, code, terminated=False):
        printDBG("WgetDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))

        # When finished updateStatistic based on file size on disk
        BaseDownloader.updateStatistic(self)

        printDBG("WgetDownloader._cmdFinished remoteFileSize[%r] localFileSize[%r]" % (self.remoteFileSize, self.localFileSize))

        if not terminated and self.status != DMHelper.STS.POSTPROCESSING \
           and self.remoteFileSize > 0 \
           and self.remoteFileSize > self.localFileSize \
           and self.curContinueRetry < self.maxContinueRetry:
            self.curContinueRetry += 1
            if hasattr(self.console, "setNice"):
                self.console.setNice(GetNice() + 2)
                self.console.execute(self.downloadCmd)
            else:
                self.console.execute(E2PrioFix(self.downloadCmd))
            return

        self._setLastError(code)

        # break circular references
        self.console_appClosed_conn = None
        self.console_stderrAvail_conn = None
        self.console = None

        self.wgetStatus = self.WGET_STS.ENDED

        if terminated:
            self.status = DMHelper.STS.INTERRUPTED
        elif self.status == DMHelper.STS.POSTPROCESSING:
            mkvPath = self._getMkvPath()
            mkvSize = DMHelper.getFileSize(fsPath(self.tempRemuxPath))
            printDBG("POSTPROCESSING remux finished mkvPath[%s] localFileSize[%r] code[%r]" % (self.tempRemuxPath, mkvSize, code))

            if mkvSize > 0 and code == 0:
                if self._moveFile(self.tempRemuxPath, mkvPath):
                    self._removeSourceFile()
                    self._finalizeSuccess(mkvPath)
                    return

            printDBG("WgetDownloader remux failed -> fallback to original target")
            if self._finalizeOriginalFallback():
                return
            self.status = DMHelper.STS.INTERRUPTED
        elif 0 >= self.localFileSize:
            self.status = DMHelper.STS.ERROR
        elif self.remoteFileSize > 0 and self.remoteFileSize > self.localFileSize:
            self.status = DMHelper.STS.INTERRUPTED
        else:
            if self.ffmpegPostEnabled:
                self.status = DMHelper.STS.POSTPROCESSING
                self.doStartPostProcess()
                return

            self.status = DMHelper.STS.DOWNLOADED
            self._writeTxtSidecar(self.filePath)

            if self.sidecarEnabled and self.sidecarImg:
                self._startImgSidecarDownload(self.filePath)
                return

        printDBG("WgetDownloader._cmdFinished status [%s]" % (self.status))
        if not terminated:
            self._finishDownloadFlow()

    def updateStatistic(self):
        if self.infoFrom == WgetDownloader.INFO.FROM_FILE:
            BaseDownloader.updateStatistic(self)
            return

        if self.WGET_STS.DOWNLOADING == self.wgetStatus:
            print(self.outData)
            dataLen = len(self.outData)
            for idx in range(dataLen):
                if idx + 1 < dataLen:
                    # default style - one dot = 1K
                    if '.' == self.outData[idx] and self.outData[idx + 1] in ['.', ' ']:
                        self.localFileSize += 1024
                else:
                    self.outData = self.outData[idx:]
                    break
        BaseDownloader._updateStatistic(self)
