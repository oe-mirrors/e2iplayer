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
class MergeDownloader(BaseDownloader):

    def __init__(self):
        printDBG('MergeDownloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)
        
        # instance of E2 console
        self.console = None
        self.iptv_sys = None
        
        self.multi = {'urls':[], 'files':[], 'remote_size':[], 'remote_content_type':[], 'local_size':[]}
        self.currIdx = 0
        
    def __del__(self):
        printDBG("MergeDownloader.__del__ ----------------------------------")
        
    def _cleanUp(self):
        for item in self.multi['files']:
            rm(item)
        
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
        else:
            # Need wget for correct working, so check also if wget working correctly
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
        self.downloaderParams = params
        self.fileExtension = '' # should be implemented in future
        self.url = url
        self.filePath = filePath
        
        try:
            urlsKeys = self.url.split('merge://')[1].split('|')
            idx = 0
            for item in urlsKeys:
                self.multi['urls'].append(self.url.meta[item])
                filePath = self.filePath + '.iptv.tmp.{0}.dash'.format(idx)
                self.multi['files'].append(filePath)
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
        
        cmd = DMHelper.getBaseWgetCmd(self.downloaderParams) + (' %s -t %d ' % (info, retries)) + '"' + url + '" -O "' + filePath + '" > /dev/null'
        printDBG("doStartDownload cmd[%s]" % cmd)
        
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._dataAvail)
        self.console.execute(E2PrioFix(cmd))
        
        self.status = DMHelper.STS.DOWNLOADING
        
        self.onStart()
        return BaseDownloader.CODE_OK
        
    def doStartPostProcess(self):
        cmd = DMHelper.GET_FFMPEG_PATH() + ' '
        for item in self.multi['files']:
            cmd += ' -i "{0}" '.format(item)
        cmd += ' -map 0:0 -map 1:0 -vcodec copy -acodec copy "{0}" >/dev/null 2>&1 '.format(self.filePath)
        printDBG("doStartPostProcess cmd[%s]" % cmd)
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console.execute(E2PrioFix(cmd))

    def _dataAvail(self, data):
        if None == data:
            return
        self.outData += data
        if 'Saving to:' in self.outData:
            self.console_stderrAvail_conn = None
            lines = self.outData.replace('\r', '\n').split('\n')
            for idx in range(len(lines)):
                if 'Length:' in lines[idx]:
                    match = re.search(" ([0-9]+?) ", lines[idx])
                    if match:
                        self.multi['remote_size'][self.currIdx] = int(match.group(1))
                    match = re.search("(\[[^]]+?\])", lines[idx])
                    if match:
                        self.multi['remote_content_type'][self.currIdx] = match.group(1)
            self.outData = ''
                        
    def _terminate(self):
        printDBG("MergeDownloader._terminate")
        if None != self.iptv_sys:
            self.iptv_sys.kill()
            self.iptv_sys = None
        if self.status in [DMHelper.STS.DOWNLOADING, DMHelper.STS.POSTPROCESSING]:
            if self.console:
                self.console.sendCtrlC() # kill # produce zombies
                self._cmdFinished(-1, True)
                return BaseDownloader.CODE_OK
        return BaseDownloader.CODE_NOT_DOWNLOADING

    def _cmdFinished(self, code, terminated=False):
        printDBG("MergeDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))
        
        # break circular references
        if None != self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
            self.console = None

        if terminated:
            self.status = DMHelper.STS.INTERRUPTED
            self._cleanUp()
            return
        
        if self.status == DMHelper.STS.POSTPROCESSING:
            self.localFileSize = DMHelper.getFileSize(self.filePath)
            printDBG("POSTPROCESSING_cmdFinished localFileSize[%r] code[%r]" % (self.localFileSize, code))
            if self.localFileSize > 0 and code == 0:
                self.remoteFileSize = self.localFileSize
                self.status = DMHelper.STS.DOWNLOADED
            else:
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
        if not terminated:
            self.onFinish()
        self._cleanUp()
        
    def _localFileSize(self, update=True):
        printDBG(">>>>>>>>>>>>>>>>>>>>> _localFileSize [%r] loacalSize[%r] = %r" % (self.localFileSize, self.currIdx, self.multi['local_size']))
        if self.localFileSize > 0:
            return self.localFileSize
        else:
            if update:
                self.multi['local_size'][self.currIdx] = DMHelper.getFileSize(self.multi['files'][self.currIdx])
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
                self.prevLocalFileSize = localFileSize
        else:
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
        
