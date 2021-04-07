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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, eConnectCallback, E2PrioFix, rm, GetCmdwrapPath, WriteTextFile, GetNice, getDebugMode
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
###################################################

###################################################
# One instance of this class can be used only for 
# one download
###################################################
class FFMPEGDownloader(BaseDownloader):

    def __init__(self):
        printDBG('FFMPEGDownloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)
        
        # instance of E2 console
        self.console = None
        self.iptv_sys = None
        self.totalDuration = 0
        self.downloadDuration = 0
        self.liveStream = False
        self.headerReceived = False
        self.parseReObj = {}
        self.parseReObj['start_time'] = re.compile('\sstart\:\s*?([0-9]+?)\.')
        self.parseReObj['duration'] = re.compile('[\s=]([0-9]+?)\:([0-9]+?)\:([0-9]+?)\.')
        self.parseReObj['size'] = re.compile('size=\s*?([0-9]+?)kB')
        self.parseReObj['bitrate'] = re.compile('bitrate=\s*?([0-9]+?(?:\.[0-9]+?)?)kbits')
        self.parseReObj['speed'] = re.compile('speed=\s*?([0-9]+?(?:\.[0-9]+?)?)x')
        
        self.ffmpegOutputContener = 'matroska'
        self.fileCmdPath = ''
        
    def __del__(self):
        printDBG("FFMPEGDownloader.__del__ ----------------------------------")
        
    def getName(self):
        return "ffmpeg"

    def isWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system(DMHelper.GET_FFMPEG_PATH() + " -version 2>&1 ", boundFunction(self._checkWorkingCallBack, callBackFun))
        
    def _checkWorkingCallBack(self, callBackFun, code, data):
        reason = ''
        sts = True
        if code != 0:
            ffmpegBinaryName = DMHelper.GET_FFMPEG_PATH()
            if ffmpegBinaryName == '':
                ffmpegBinaryName = 'ffmpeg'
            sts = False
            if code == 127:
                reason = _('Utility "%s" can not be found.' % ffmpegBinaryName)
            else:
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
        
        cmdTab = [DMHelper.GET_FFMPEG_PATH(), '-y']
        tmpUri = strwithmeta(url)
        
        if 'iptv_video_rep_idx' in tmpUri.meta:
            cmdTab.extend(['-video_rep_index', str(tmpUri.meta['iptv_video_rep_idx'])])
        
        if 'iptv_audio_rep_idx' in tmpUri.meta:
            cmdTab.extend(['-audio_rep_index', str(tmpUri.meta['iptv_audio_rep_idx'])])
            
        if 'iptv_m3u8_live_start_index' in tmpUri.meta:
            cmdTab.extend(['-live_start_index', str(tmpUri.meta['iptv_m3u8_live_start_index'])])
            
        if 'iptv_m3u8_key_uri_replace_old' in tmpUri.meta and 'iptv_m3u8_key_uri_replace_new' in tmpUri.meta:
            cmdTab.extend(['-key_uri_old', str(tmpUri.meta['iptv_m3u8_key_uri_replace_old']), '-key_uri_new', str(tmpUri.meta['iptv_m3u8_key_uri_replace_new'])])
        
        if "://" in self.url: 
            url, httpParams = DMHelper.getDownloaderParamFromUrlWithMeta(tmpUri, True)
            headers = []
            for key in httpParams:
                if key == 'Range': #Range is always used by ffmpeg
                    continue
                elif key == 'User-Agent':
                    cmdTab.extend(['-user-agent', httpParams[key]])
                else:
                    headers.append('%s: %s' % (key, httpParams[key]))
            
            if len(headers):
                cmdTab.extend(['-headers', '\r\n'.join(headers)])
        
        if self.url.startswith("merge://"):
            try:
                urlsKeys = self.url.split('merge://', 1)[1].split('|')
                for item in urlsKeys:
                    cmdTab.extend(['-reconnect', '1', '-i', self.url.meta[item]])
            except Exception:
                printExc()
        else:
            cmdTab.extend(['-reconnect', '1', '-i', url])
        
        cmdTab.extend(['-c:v', 'copy', '-c:a', 'copy', '-f', tmpUri.meta.get('ff_out_container', self.ffmpegOutputContener), self.filePath])
        
        self.fileCmdPath = self.filePath + '.iptv.cmd'
        rm(self.fileCmdPath)
        WriteTextFile(self.fileCmdPath, '|'.join(cmdTab))
        
        cmd = GetCmdwrapPath() + (' "%s" "|" %s ' % (self.fileCmdPath, GetNice() + 2))

        printDBG("FFMPEGDownloader::start cmd[%s]" % cmd)
        
        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._dataAvail)
        self.console.execute(cmd)
        
        self.status = DMHelper.STS.DOWNLOADING
        
        self.onStart()
        return BaseDownloader.CODE_OK
        
    def _getDuration(self, data):
        try:
            obj = self.parseReObj['duration'].search(data)
            return 3600 * int(obj.group(1)) + 60 * int(obj.group(2)) + int(obj.group(3))
        except Exception:
            printExc()
        return 0

    def _getStartTime(self, data):
        try:
            obj = self.parseReObj['start_time'].search(data)
            return int(obj.group(1))
        except Exception:
            printExc()
        return 0
        
    def _getFileSize(self, data):
        try:
            return int(self.parseReObj['size'].search(data).group(1)) * 1024
        except Exception:
            printExc()
        return 0
        
    def _getDownloadSpeed(self, data):
        try:
            return int(float(self.parseReObj['bitrate'].search(data).group(1)) * float(self.parseReObj['speed'].search(data).group(1)) * 1024 / 8)
        except Exception:
            printExc()
        return 0
    
    def _dataAvail(self, data):
        if None == data:
            return
        
        data = self.outData + data.replace('\n', '\r')
        
        data = data.split('\r')
        if data[-1].endswith('\r'): 
            self.outData = '' # data not truncated
        else: # data truncated
            self.outData = data[-1]
            del data[-1]
        
        for item in data:
            printDBG("---")
            printDBG(item)
            if not self.headerReceived:
                if 'Duration:' in item:
                    duration = self._getDuration(item) - self._getStartTime(item)
                    if duration > 0 and (duration < self.totalDuration or 0 == self.totalDuration):
                        self.totalDuration = duration
                elif 'Stream mapping:' in item:
                    self.headerReceived = True
                    if self.totalDuration == 0:
                        self.liveStream = True
            
            if 'frame=' in item: 
                self.lastUpadateTime = datetime.datetime.now()
                
                self.downloadSpeed = self._getDownloadSpeed(item)
                
                fileSize = self._getFileSize(item)
                if fileSize > self.localFileSize:
                    self.localFileSize = fileSize
                    
                    # update duration only when file size changed
                    # to make sure that this duration is ready to 
                    # for reading
                    duration = self._getDuration(item)
                    if duration > self.downloadDuration:
                        self.downloadDuration = duration
        
    def _terminate(self):
        printDBG("FFMPEGDownloader._terminate")
        if None != self.iptv_sys:
            self.iptv_sys.kill()
            self.iptv_sys = None
        if DMHelper.STS.DOWNLOADING == self.status:
            if self.console:
                #self.console.sendCtrlC()
                self.console.sendCtrlC() # kill # produce zombies
                self._cmdFinished(-1, True)
                return BaseDownloader.CODE_OK
        return BaseDownloader.CODE_NOT_DOWNLOADING

    def _cmdFinished(self, code, terminated=False):
        printDBG("FFMPEGDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))
        
        if '' == getDebugMode():
            rm(self.fileCmdPath)
        
        # break circular references
        if None != self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
            self.console = None

        if terminated:
            self.status = DMHelper.STS.INTERRUPTED
        elif 0 >= self.localFileSize:
            self.status = DMHelper.STS.ERROR
        elif self.totalDuration > 0 and self.totalDuration > self.downloadDuration:
            self.status = DMHelper.STS.INTERRUPTED
        else:
            self.status = DMHelper.STS.DOWNLOADED
        if not terminated:
            self.onFinish()
            
    def isLiveStream(self):
        return self.liveStream

    def updateStatistic(self):
        if self.lastUpadateTime != None: 
            d = datetime.datetime.now() - self.lastUpadateTime
            if d.seconds > 3:
                # if we not get new stats update this mean that we do not download any data
                self.downloadSpeed = 0
        
    def hasDurationInfo(self):
        return True
    
    def getTotalFileDuration(self):
        # total duration in seconds
        if self.isLiveStream():
            return self.downloadDuration
        return self.totalDuration

    def getDownloadedFileDuration(self):
        # downloaded duration in seconds
        return self.downloadDuration
        
