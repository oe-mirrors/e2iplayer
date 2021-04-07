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
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.wgetdownloader import WgetDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
###################################################

###################################################
# FOREIGN import
###################################################
from Tools.BoundFunction import boundFunction
from enigma import eConsoleAppContainer

###################################################

###################################################
# One instance of this class can be used only for 
# one download
###################################################


class BuxyboxWgetDownloader(WgetDownloader):
                     
    def __init__(self):
        printDBG('BuxyboxWgetDownloader.__init__ ----------------------------------')
        WgetDownloader.__init__(self)
        self.iptv_sys = None
        
    def __del__(self):
        printDBG("BuxyboxWgetDownloader.__del__ ----------------------------------")
        
    def getName(self):
        return "busybox wget"

    def isWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system("wget 2>&1 ", boundFunction(self._checkWorkingCallBack, callBackFun))
        
    def _checkWorkingCallBack(self, callBackFun, code, data):
        reason = ''
        sts = True
        if 'Usage: wget' not in data:
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
        
        cmd = 'wget ' + '"' + self.url + '" -O "' + self.filePath + '" > /dev/null'
        printDBG("Download cmd[%s]" % cmd)
        
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console.execute(E2PrioFix(cmd))

        self.wgetStatus = self.WGET_STS.CONNECTING
        self.status = DMHelper.STS.DOWNLOADING
        
        self.onStart()
        return BaseDownloader.CODE_OK

    def _terminate(self):
        printDBG("BuxyboxWgetDownloader._terminate")
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
        printDBG("BuxyboxWgetDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))
        
        # break circular references
        self.console_appClosed_conn = None
        self.console = None
    
        self.wgetStatus = self.WGET_STS.ENDED
        
        # When finished updateStatistic based on file sie on disk
        BaseDownloader.updateStatistic(self)

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
        
        
        
