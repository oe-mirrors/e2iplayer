# -*- coding: utf-8 -*-
# IPTV download manager API
# add 071026: HLS (VOD and live) through curl-impersonate, for buffered playback and Download Manager downloads.
# For CDNs that answer HTTP 403 to every OpenSSL TLS client (urllib, pycurl, hlsdl and the players' ffmpeg),
# e.g. vidzy.cc. One helper process (scripts/impersonatehls.py, run by the box's python) fetches the
# playlist and all segments with the curl-impersonate binary and writes them as one MPEG-TS file; the
# player plays the growing file like with hlsdl buffering. Chosen by iptvdownloadercreator.py for urls
# with the meta 'iptv_impersonate_hls': True (set by urlparserhelper.getImpersonateM3U8Playlist, and by
# requireDownloaderForDisguisedHls for segments with a fake image header in front of the MPEG-TS data).
# The helper reports progress / duration / errors as JSON lines on stderr (same keys as hlsdl).
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback, GetPluginDir, GetTmpDir, Which
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import ensureText, fsPath, shellQuote, executeConsoleCmd, terminateToolsOfFile, SidecarMixin
from Plugins.Extensions.IPTVPlayer.libs import curlimpersonate
###################################################

###################################################
# FOREIGN import
###################################################
from enigma import eConsoleAppContainer
from Components.config import config
import json
import os
import shutil
###################################################

HELPER_NAME = 'impersonatehls'
# the helper names the output file in its command line, curl-impersonate its -K list "<output>.parts/..."
HELPER_TOOLS = (HELPER_NAME, 'curl-impersonate')


def getHelperScript():
    base = GetPluginDir('scripts/' + HELPER_NAME)
    for ext in ('.py', '.pyc'):
        if os.path.isfile(base + ext):
            return base + ext
    return ''


def getHelperPython():
    # the box's python3 (OE-A 8.x), else "python" like GetPyScriptCmd; the helper runs on 2.7 too
    for name in ('python3', 'python'):
        path = Which(name)
        if path:
            return path
    return ''


class ImpersonateHLSDownloader(BaseDownloader, SidecarMixin):

    def __init__(self):
        printDBG('ImpersonateHLSDownloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)
        self.console = None
        self.console_appClosed_conn = None
        self.console_stderrAvail_conn = None
        self._initSidecarState()
        self.outData = ''
        self.totalDuration = 0
        self.downloadDuration = 0
        self.lastErrorCode = None
        self.lastErrorDesc = ''
        self.liveStream = False
        # set by the download manager (see HLSDownloader); a "Continue downloading" starts over here
        self.allowFinalRename = False
        self.resumeExisting = False

    def __del__(self):
        printDBG("ImpersonateHLSDownloader.__del__ ----------------------------------")

    def getName(self):
        return "curl-impersonate hls"

    def getLastError(self):
        return self.lastErrorCode, self.lastErrorDesc

    def _checkPrerequisites(self):
        # '' when everything needed is there, else the reason (shown to the user)
        if not curlimpersonate.getImpersonateBinary():
            return _("curl-impersonate is not installed on the receiver (%s). This stream only plays with it.") % curlimpersonate.BINARY_CANDIDATES[0]
        if not getHelperScript():
            return _("The helper script %s is missing.") % ('scripts/%s.py' % HELPER_NAME)
        if not getHelperPython():
            return _("Python was not found on the receiver.")
        return ''

    def isWorkingCorrectly(self, callBackFun):
        # only file system checks, nothing that blocks
        reason = self._checkPrerequisites()
        callBackFun(reason == '', reason)

    def _cleanUp(self):
        # the helper removes its segment folder itself; this is for a killed one
        try:
            partsDir = fsPath(ensureText(self.filePath) + '.parts')
            if self.filePath and os.path.isdir(partsDir):
                shutil.rmtree(partsDir, True)
        except Exception:
            printExc()

    def start(self, url, filePath, params={}):
        self.url = url
        self.filePath = ensureText(filePath)
        self.downloaderParams = params
        self.fileExtension = ''
        self.outData = ''
        self.totalDuration = 0
        self.downloadDuration = 0
        self.localFileSize = 0
        self.lastErrorCode = None
        self.lastErrorDesc = ''
        self.liveStream = False
        meta = getattr(url, 'meta', {}) or {}
        self._prepareSidecarData(meta)

        reason = self._checkPrerequisites()
        if reason:
            # the download manager does not ask isWorkingCorrectly() first
            printDBG("ImpersonateHLSDownloader::start not possible: %s" % reason)
            self.lastErrorCode, self.lastErrorDesc = 3, reason
            self.status = DMHelper.STS.ERROR
            self.onFinish()
            return BaseDownloader.CODE_WRONG_LINK

        # Referer / Origin / Cookie ... from the url meta; the helper drops the headers the impersonated browser
        # sends itself (User-Agent, Accept*, sec-ch-*: they belong to the TLS fingerprint, see libs/curlimpersonate)
        headerOptions = ''
        for key, value in list(params.items()):
            if key in DMHelper.HANDLED_HTTP_HEADER_PARAMS and value != '':
                headerOptions += ' -H "%s: %s"' % (key, shellQuote(value))

        # a live stream: buffered playback starts behind the live edge like hlsdl -s (Download Manager: at the edge)
        if not self.allowFinalRename:
            try:
                offset = str(config.plugins.iptvplayer.hlsdlLiveStartOffset.value)
                if offset.isdigit():
                    headerOptions += ' --live-start %s' % offset
            except Exception:
                printExc()

        cmd = '%s "%s" --binary "%s" --tmp "%s" -k%s -o "%s" "%s"' % (getHelperPython(), shellQuote(getHelperScript()),
                                                                     shellQuote(curlimpersonate.getImpersonateBinary()), shellQuote(GetTmpDir()),
                                                                     headerOptions, shellQuote(self.filePath), shellQuote(str(url)))
        printDBG("ImpersonateHLSDownloader::start cmd[%s]" % cmd)

        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._dataAvail)
        executeConsoleCmd(self.console, cmd)

        self.status = DMHelper.STS.DOWNLOADING
        self.onStart()
        return BaseDownloader.CODE_OK

    def _dataAvail(self, data):
        if None is data:
            return
        data = self.outData + ensureText(data)
        lines = data.split('\n')
        self.outData = lines.pop()  # '' or a line not complete yet
        for item in lines:
            item = item.strip()
            if not item:
                continue
            printDBG(item)
            if not item.startswith('{'):
                continue
            try:
                obj = json.loads(item)
            except Exception:
                printExc()
                continue
            updateStatistic = False
            if obj.get("d_t") == "live":
                self.liveStream = True
            if "d_s" in obj:
                self.localFileSize = obj["d_s"]
                updateStatistic = True
            # fix 071026: whole seconds like hlsdl - the helper sums EXTINF values (200.032), and the player
            # hands the duration to eSlider.setRange(), which only takes int (GUI crash, box crash log 07.10.)
            if "t_d" in obj:
                self.totalDuration = int(obj["t_d"])
                updateStatistic = True
            if "d_d" in obj:
                self.downloadDuration = int(obj["d_d"])
                updateStatistic = True
            if obj.get("error_code"):
                self.lastErrorCode = obj["error_code"]
                self.lastErrorDesc = ensureText(obj.get("error_msg", ""))
                printDBG("ImpersonateHLSDownloader error_code[%r] error_msg[%r]" % (self.lastErrorCode, self.lastErrorDesc))
            if updateStatistic:
                BaseDownloader._updateStatistic(self)

    def _terminate(self):
        printDBG("ImpersonateHLSDownloader._terminate")
        self._terminateSidecar()
        if DMHelper.STS.DOWNLOADING == self.status:
            if self.console:
                if hasattr(self.console, "sendCtrlC"):
                    self.console.sendCtrlC()
                elif hasattr(self.console, "kill"):
                    self.console.kill()
            # the signal may only reach the shell around the helper
            terminateToolsOfFile(self.filePath, HELPER_TOOLS)
            self._cmdFinished(-1, True)
            return BaseDownloader.CODE_OK
        return BaseDownloader.CODE_NOT_DOWNLOADING

    def _cmdFinished(self, code, terminated=False):
        printDBG("ImpersonateHLSDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))
        if None is not self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
            self.console = None
        if self.outData:
            self._dataAvail('\n')
        self.localFileSize = DMHelper.getFileSize(fsPath(self.filePath))

        if terminated:
            self.status = DMHelper.STS.INTERRUPTED
            self._cleanUp()
            return
        if code == 0 and 0 < self.localFileSize:
            self.remoteFileSize = self.localFileSize
            self.status = DMHelper.STS.DOWNLOADED
            if self.allowFinalRename:
                self._writeTxtSidecar(self.filePath)
                if self.sidecarEnabled and self.sidecarImg:
                    self._startImgSidecarDownload(self.filePath)
                    return
        else:
            if self.lastErrorCode is None:
                self.lastErrorCode = code
                self.lastErrorDesc = _("The helper process ended unexpectedly.")
            self.status = DMHelper.STS.INTERRUPTED if 0 < self.localFileSize else DMHelper.STS.ERROR
        self._finishDownloadFlow()

    def updateStatistic(self):
        # the file itself is the best measure (the helper appends whole segments)
        size = DMHelper.getFileSize(fsPath(self.filePath))
        if size > 0:
            self.localFileSize = size
        BaseDownloader._updateStatistic(self)

    def isLiveStream(self):
        return self.liveStream

    def hasDurationInfo(self):
        return True

    def getTotalFileDuration(self):
        if self.liveStream:
            return self.downloadDuration
        return self.totalDuration

    def getDownloadedFileDuration(self):
        return self.downloadDuration
