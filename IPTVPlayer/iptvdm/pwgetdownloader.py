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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, eConnectCallback, E2PrioFix
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import enum
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
###################################################

###################################################
# FOREIGN import
###################################################
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


class PwgetDownloader(BaseDownloader):
    # wget status
    WGET_STS = enum(NONE='WGET_NONE',
                     CONNECTING='WGET_CONNECTING',
                     DOWNLOADING='WGET_DOWNLOADING',
                     ENDED='WGET_ENDED')
                     
    def __init__(self):
        printDBG('PwgetDownloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)
        
        self.wgetStatus = self.WGET_STS.NONE
        # instance of E2 console
        self.console = None
        self.iptv_sys = None
        
    def __del__(self):
        printDBG("PwgetDownloader.__del__ ----------------------------------")
        
    def getName(self):
        return "pwget"

    def isWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system("python " + DMHelper.GET_PWGET_PATH() + " 2>&1", boundFunction(self._checkWorkingCallBack, callBackFun))
        
    def _checkWorkingCallBack(self, callBackFun, code, data):
        reason = ''
        sts = True
        if 'Usage: python pwget url file' not in data:
            sts = False
            reason = data
        self.iptv_sys = None
        callBackFun(sts, reason)
    
    def start(self, url, filePath, params={}):
        '''
            Owervrite start from BaseDownloader
        '''
        self.url = url
        self.filePath = filePath
        self.downloaderParams = params
        self.fileExtension = '' # should be implemented in future
        
        self.outData = ''
        self.contentType = 'unknown'
        
        cmd = "python " + DMHelper.GET_PWGET_PATH() + ' "' + self.url + '" "' + self.filePath + '" > /dev/null'
        printDBG("Download cmd[%s]" % cmd)
        
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._dataAvail)

        self.console.execute(E2PrioFix(cmd))

        self.wgetStatus = self.WGET_STS.CONNECTING
        self.status = DMHelper.STS.DOWNLOADING
        
        self.onStart()
        return BaseDownloader.CODE_OK

    def _dataAvail(self, data):
        if None != data:
            self.outData += data
                        
    def _terminate(self):
        printDBG("PwgetDownloader._terminate")
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
        printDBG("PwgetDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))
        
        # break circular references
        self.console_appClosed_conn = None
        self.console_stderrAvail_conn = None
        self.console = None
    
        self.wgetStatus = self.WGET_STS.ENDED
        
        # When finished updateStatistic based on file sie on disk
        BaseDownloader.updateStatistic(self)
        
        if not terminated:
            printDBG("PwgetDownloader._cmdFinished [%s]" % self.outData)
            match = re.search("Content-Length: ([0-9]+?)[^0-9]", self.outData)
            if match: 
                self.remoteFileSize = int(match.group(1))

        if terminated:
            self.status = DMHelper.STS.INTERRUPTED
        elif 0 >= self.localFileSize:
            self.status = DMHelper.STS.ERROR
        elif self.remoteFileSize > 0 and self.remoteFileSize > self.localFileSize:
            self.status = DMHelper.STS.INTERRUPTED
        else:
            self.status = DMHelper.STS.DOWNLOADED
        if not terminated:
            self.onFinish()
