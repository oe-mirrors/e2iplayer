# -*- coding: utf-8 -*-
#
#  IPTV download manager API
#
#  $Id$
#
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, eConnectCallback, E2PrioFix, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import enum
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
###################################################

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
        self.iptv_sys = None
        self.curContinueRetry = 0
        self.maxContinueRetry = 0
        self.downloadCmd = ''
        self.remoteContentType = None
        self.lastErrorCode = None
        self.lastErrorDesc = ''

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
        self.iptv_sys = iptv_system(DMHelper.GET_WGET_PATH() + " -V 2>&1 ", boundFunction(self._checkWorkingCallBack, callBackFun))

    def getMimeType(self):
        return self.remoteContentType

    def _checkWorkingCallBack(self, callBackFun, code, data):
        reason = ''
        sts = True
        if code != 0:
            sts = False
            reason = data
        self.iptv_sys = None
        callBackFun(sts, reason)

    def start(self, url, filePath, params={}, info_from=None, retries=0):
        '''
            Owervrite start from BaseDownloader
        '''
        self.url = url
        self.filePath = filePath
        self.downloaderParams = params
        self.fileExtension = '' # should be implemented in future

        self.outData = ''
        self.contentType = 'unknown'
        if None == info_from:
            info_from = WgetDownloader.INFO.FROM_FILE
        self.infoFrom = info_from

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
        self.console.execute(E2PrioFix(self.downloadCmd))

        self.wgetStatus = self.WGET_STS.CONNECTING
        self.status = DMHelper.STS.DOWNLOADING

        self.onStart()
        return BaseDownloader.CODE_OK

    def _dataAvail(self, data):
        if None != data:
            self.outData += data
            if self.infoFrom == WgetDownloader.INFO.FROM_FILE:
                if 'Saving to:' in self.outData:
                    self.console_stderrAvail_conn = None
                    lines = self.outData.replace('\r', '\n').split('\n')
                    for idx in range(len(lines)):
                        if 'Length:' in lines[idx]:
                            match = re.search(" ([0-9]+?) ", lines[idx])
                            if match:
                                self.remoteFileSize = int(match.group(1))
                            match = re.search("(\[[^]]+?\])", lines[idx])
                            if match:
                                self.remoteContentType = match.group(1)
                    self.outData = ''
            elif self.WGET_STS.CONNECTING == self.wgetStatus:
                self.outData += data
                lines = self.outData.replace('\r', '\n').split('\n')
                for idx in range(len(lines)):
                    if lines[idx].startswith('Length:'):
                        match = re.search("Length: ([0-9]+?) \([^)]+?\) (\[[^]]+?\])", lines[idx])
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
        if None != self.iptv_sys:
            self.iptv_sys.kill()
            self.iptv_sys = None
        if DMHelper.STS.DOWNLOADING == self.status:
            if self.console:
                self.console.sendCtrlC() # kill # produce zombies
                self._cmdFinished(-1, True)
                return BaseDownloader.CODE_OK

        return BaseDownloader.CODE_NOT_DOWNLOADING

    def _cmdFinished(self, code, terminated=False):
        printDBG("WgetDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))

        # When finished updateStatistic based on file size on disk
        BaseDownloader.updateStatistic(self)

        printDBG("WgetDownloader._cmdFinished remoteFileSize[%r] localFileSize[%r]" % (self.remoteFileSize, self.localFileSize))

        if not terminated and self.remoteFileSize > 0 \
           and self.remoteFileSize > self.localFileSize \
           and self.curContinueRetry < self.maxContinueRetry:
            self.curContinueRetry += 1
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
        elif 0 >= self.localFileSize:
            self.status = DMHelper.STS.ERROR
        elif self.remoteFileSize > 0 and self.remoteFileSize > self.localFileSize:
            self.status = DMHelper.STS.INTERRUPTED
        else:
            self.status = DMHelper.STS.DOWNLOADED

        printDBG("WgetDownloader._cmdFinished status [%s]" % (self.status))
        if not terminated:
            self.onFinish()

    def updateStatistic(self):
        if self.infoFrom == WgetDownloader.INFO.FROM_FILE:
            BaseDownloader.updateStatistic(self)
            return

        if self.WGET_STS.DOWNLOADING == self.wgetStatus:
            print self.outData
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
