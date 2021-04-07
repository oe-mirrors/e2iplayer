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


class HLSDownloader(BaseDownloader):

    def __init__(self):
        printDBG('HLSDownloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)

        # instance of E2 console
        self.console = None
        self.iptv_sys = None
        self.totalDuration = 0
        self.downloadDuration = 0
        self.liveStream = False

    def __del__(self):
        printDBG("HLSDownloader.__del__ ----------------------------------")

    def getName(self):
        return "hlsdl m3u8"

    def isWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system(DMHelper.GET_HLSDL_PATH() + " 2>&1 ", boundFunction(self._checkWorkingCallBack, callBackFun))

    def _checkWorkingCallBack(self, callBackFun, code, data):
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
        self.outData = ''
        self.contentType = 'unknown'

        # baseWgetCmd = DMHelper.getBaseWgetCmd(self.downloaderParams)
        # TODO: add all HTTP parameters
        addParams = ''
        meta = strwithmeta(url).meta
        if 'iptv_m3u8_key_uri_replace_old' in meta and 'iptv_m3u8_key_uri_replace_new' in meta:
            addParams = ' -k "%s" -n "%s" ' % (meta['iptv_m3u8_key_uri_replace_old'], meta['iptv_m3u8_key_uri_replace_new'])

        if 'iptv_m3u8_seg_download_retry' in meta:
            addParams += ' -w %s ' % meta['iptv_m3u8_seg_download_retry']

        if self.url.startswith("merge://"):
            try:
                urlsKeys = self.url.split('merge://', 1)[1].split('|')
                url = meta[urlsKeys[-1]]
                addParams += ' -a "%s" ' % meta[urlsKeys[0]]
            except Exception:
                printExc()
        else:
            url = self.url

        cmd = DMHelper.getBaseHLSDLCmd(self.downloaderParams) + (' "%s"' % url) + addParams + (' -o "%s"' % self.filePath) + ' > /dev/null'

        printDBG("HLSDownloader::start cmd[%s]" % cmd)

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
                    updateStatistic = False
                    obj = json.loads(item.strip())
                    printDBG("Status object [%r]" % obj)
                    if "d_s" in obj:
                        self.localFileSize = obj["d_s"]
                        updateStatistic = True
                    if "t_d" in obj:
                        self.totalDuration = obj["t_d"]
                        updateStatistic = True
                    if "d_d" in obj:
                        self.downloadDuration = obj["d_d"]
                        updateStatistic = True

                    if "d_t" in obj and obj['d_t'] == 'live':
                        self.liveStream = True
                    if updateStatistic:
                        BaseDownloader._updateStatistic(self)
                except Exception:
                    printExc()
                    continue

    def _terminate(self):
        printDBG("HLSDownloader._terminate")
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
        printDBG("HLSDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))

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

    def isLiveStream(self):
        return self.liveStream

    def updateStatistic(self):
        #BaseDownloader.updateStatistic(self)
        return

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
