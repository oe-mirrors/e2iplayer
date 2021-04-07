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
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import enum, strwithmeta
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
class F4mDownloader(BaseDownloader):

    def __init__(self):
        printDBG('F4mDownloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)
        
        # instance of E2 console
        self.console = None
        self.iptv_sys = None
        
    def __del__(self):
        printDBG("F4mDownloader.__del__ ----------------------------------")
        
    def getName(self):
        return "F4Mdump"

    def isWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system(DMHelper.GET_F4M_PATH() + " 2>&1 ", boundFunction(self._checkWorkingCallBack, callBackFun))
        
    def _checkWorkingCallBack(self, callBackFun, code, data):
        reason = ''
        sts = True
        if code != 0:
            sts = False
            reason = data
            self.iptv_sys = None
            callBackFun(sts, reason)
        else:
            # F4MDump need wget for correct working, so check also if wget working correctly
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
    
    def start(self, url, filePath, params={}):
        '''
            Owervrite start from BaseDownloader
        '''
        self.url = url
        self.filePath = filePath
        self.downloaderParams = params
        self.fileExtension = '' # should be implemented in future
        if 'ustream.tv' in url:
            self.streamSelector = strwithmeta(url).meta.get('iptv_chank_url', '')
        else:
            self.streamSelector = strwithmeta(url).meta.get('iptv_bitrate', 0)
        
        self.outData = ''
        self.contentType = 'unknown'
        
        baseWgetCmd = DMHelper.getBaseWgetCmd(self.downloaderParams) 
        
        cmd = DMHelper.GET_F4M_PATH() + (" '%s'" % baseWgetCmd) + (' "%s"' % self.url) + (' "%s"' % self.filePath) + (' %s' % self.streamSelector) + ' > /dev/null'

        printDBG("F4mDownloader::start cmd[%s]" % cmd)
        
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._dataAvail)
        self.console.execute(E2PrioFix(cmd))
        
        self.status = DMHelper.STS.DOWNLOADING
        
        self.onStart()
        return BaseDownloader.CODE_OK

    def _dataAvail(self, data):
        if None == data:
            return
        data = self.outData + data
        if '\n' != data[-1]:
            truncated = True
        else:
            truncated = False
        data = data.split('\n')
        if truncated: 
            self.outData = data[-1]
            del data[-1]
        for item in data:
            printDBG(item)
            if item.startswith('{'): 
                try:
                    obj = json.loads(item.strip())
                    printDBG("Status object [%r]" % obj)
                    if "total_download_size" in obj:
                        self.localFileSize = obj["total_download_size"]
                        BaseDownloader._updateStatistic(self)
                except Exception: 
                    printExc()
                    continue
                        
    def _terminate(self):
        printDBG("F4mDownloader._terminate")
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
        printDBG("F4mDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))
        
        # break circular references
        if None != self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
            self.console = None

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

    def updateStatistic(self):
        #BaseDownloader.updateStatistic(self)
        return
        
        
        
