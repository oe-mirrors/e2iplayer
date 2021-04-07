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
class RtmpDownloader(BaseDownloader):
    URI_TAB = ['rtmp://', 'rtmpt://', 'rtmpe://', 'rtmpte://', 'rtmps://']
    # rtmp status
    RTMP_STS = enum(NONE='RTMP_NONE',
                     CONNECTING='RTMP_CONNECTING',
                     DOWNLOADING='RTMP_DOWNLOADING',
                     ENDED='RTMP_ENDED')
    # rtmp status
    INFO = enum(FROM_FILE='INFO_FROM_FILE',
                 FROM_DOTS='INFO_FROM_DOTS')
                     
    def __init__(self):
        printDBG('RtmpDownloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)
        
        self.rtmpStatus = self.RTMP_STS.NONE
        # instance of E2 console
        self.console = None
        self.iptv_sys = None
        
    def __del__(self):
        printDBG("RtmpDownloader.__del__ ----------------------------------")

    def getName(self):
        return "rtmpdump"

    def isWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system(DMHelper.GET_RTMPDUMP_PATH() + " -h 2>&1 ", boundFunction(self._checkWorkingCallBack, callBackFun))

    def _checkWorkingCallBack(self, callBackFun, code, data):
        reason = ''
        sts = True
        if code != 0:
            sts = False
            reason = data
        self.iptv_sys = None
        callBackFun(sts, reason)
        
    def _getCMD(self, url):
        paramsL = ['help', 'url', 'rtmp', 'host', 'port', 'socks', 'protocol', 'playpath', 'playlist', 'swfUrl', 'tcUrl', 'pageUrl', 'app', 'swfhash', 'swfsize', 'swfVfy', 'swfAge', 'auth', 'conn', 'flashVer', 'live', 'subscribe', 'realtime', 'flv', 'resume', 'timeout', 'start', 'stop', 'token', 'jtv', 'weeb', 'hashes', 'buffer', 'skip', 'quiet', 'verbose', 'debug']
        paramsS = ['h', 'i', 'r', 'n', 'c', 'S', 'l', 'y', 'Y', 's', 't', 'p', 'a', 'w', 'x', 'W', 'X', 'u', 'C', 'f', 'v', 'd', 'R', 'o', 'e', 'e', 'A', 'B', 'T', 'j', 'J', '#', 'b', 'k', 'q', 'V', 'z']
        paramsRequireValue = ['pageUrl']
        
        
        url = 'rtmp ' + url
        tmpTab = url.split(' ')
        parameter = None
        value = ''
        cmd = ''
        
        def _processItem(item, parameter, value, cmd):
            printDBG(item)
            if (item in paramsL and (parameter not in paramsRequireValue or '' != value)) or '##fake##' == item:                
                if None != parameter:
                    cmd += ' --' + parameter.strip()
                    if '' != value:
                        cmd += "='%s'" % value.strip()
                        value = ''
                elif '' != value:
                    printDBG('_getCMD.RtmpDownloader no parameters for value[%s]' % value.strip())
                    if 0 < len(cmd): 
                        cmd = cmd[:-1] + ' %s"' % value.strip().replce('\\', '\\\\')
                        value = ''
                parameter = item
            else:
                if '' != value:
                    value += ' '
                value += item
                
            return item, parameter, value, cmd
         
        # pre-processing
        params = []
        for item in tmpTab:
            tmp = item.find('=')
            if -1 < tmp and item[:tmp] in paramsL:
                params.append(item[:tmp])
                if 'live' != item[:tmp]:
                    params.append(item[tmp + 1:])
            else:
                params.append(item)
            
        for item in params:
            item, parameter, value, cmd = _processItem(item, parameter, value, cmd)
        item, parameter, value, cmd = _processItem('##fake##', parameter, value, cmd) 
        return cmd
            
    def start(self, url, filePath, params={}, info_from=None, retries=0):
        '''
            Owervrite start from BaseDownloader
        '''
        self.url = url
        self.filePath = filePath
        self.downloaderParams = params
        self.fileExtension = '' # should be implemented in future
        
        rtmpdump_url = self._getCMD(url)
        
        if 0:
            #rtmpdump -r rtmp://5.79.71.195/stream/ --playpath=3001_goldvod --swfUrl=http://goldvod.tv:81/j/jwplayer/jwplayer.flash.swf --pageUrl=http://goldvod.tv/tv-online/tvp1.html -o tvp1.flv
            tmpTab = url.split(' ')
            rtmpdump_url = '"' + tmpTab[0].strip() + '"'
            del tmpTab[0]
            
            prevflashVer = ''
            for item in tmpTab:
                item = item.strip()
                # ignore empty and live params
                if '' != prevflashVer:
                    rtmpdump_url += ' --' + prevflashVer[0:-1] + ' ' + item + '"'
                    prevflashVer = ''
                    continue
                idx = item.find('=')
                if -1 == idx:
                    continue
                argName = item[:idx] 
                argValue = item[idx + 1:]
                if 'live' in argName:
                    item = 'live'
                else:
                    item = '%s="%s"' % (argName, argValue)
                    
                if 'flashVer' == argName:
                    prevflashVer = item
                    continue
                rtmpdump_url += ' --' + item
        cmd = DMHelper.GET_RTMPDUMP_PATH() + " " + rtmpdump_url + ' --realtime -o "' + self.filePath + '" > /dev/null 2>&1'
        printDBG("rtmpdump cmd[%s]" % cmd)
        
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        #self.console.stderrAvail.append( self._dataAvail )
        self.console.execute(E2PrioFix(cmd))

        self.rtmpStatus = self.RTMP_STS.CONNECTING
        self.status = DMHelper.STS.DOWNLOADING
        
        self.onStart()
        return BaseDownloader.CODE_OK
                        
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
        printDBG("RtmpDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))
        
        # break circular references
        self.console_appClosed_conn = None
        self.console = None
        
        self.rtmpStatus = self.RTMP_STS.ENDED
        
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

    def updateStatistic(self):
        BaseDownloader.updateStatistic(self)
        return
        
        
        
