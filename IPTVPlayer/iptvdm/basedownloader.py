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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
###################################################

###################################################
# FOREIGN import
###################################################
import datetime
from os import rename as os_rename
###################################################

###################################################
# One instance of this class can be used only for
# one download
###################################################


class BaseDownloader:
    # errors code
    CODE_OK = 0
    CODE_NOT_DOWNLOADING = 1 # user what terminate not started downloading
    CODE_WRONG_LINK = 2      # wrong link

    # posible fileds
    DOWNLOAD_PARAMS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36',
                        'Cookie': ''
                      }

    def __init__(self):
        self.status = DMHelper.STS.WAITING
        self.tries = DMHelper.DOWNLOAD_TYPE.INITIAL
        self.subscribersFor_Finish = []
        self.subscribersFor_Start = []

        self.remoteFileSize = -1
        self.localFileSize = -1
        self.downloadSpeed = -1

        self.downloaderParams = {}
        self.url = ''
        self.filePath = ''
        self.fileExtension = ''

        # temporary data to calculate download speed
        self.lastUpadateTime = None
        self.prevLocalFileSize = 0

    def getName(self):
        return "Base"

    def getMimeType(self):
        return None

    def getStatus(self):
        return self.status

    def getLastError(self):
        return None, ''

    def isDownloading(self):
        if DMHelper.STS.DOWNLOADING == self.status:
            return True
        return False

    def isWorkingCorrectly(self, callBackFun):
        ''' Check if this downloader has all needed components
            and can be used for download, this method can be
            called only from main thread
        '''
        sts = False
        reason = 'This is base class. Download cannot be done with it.'
        callBackFun(sts, reason)

    def isLiveStream(self):
        # True - if it downloading live stream,
        # False - if it downloading vod,
        # None - no information
        return None

    def hasDurationInfo(self):
        return False

    def getFullFileName(self):
        return self.filePath

    def moveFullFileName(self, newPath):
        bRet = False
        msg = ''
        try:
            os_rename(self.filePath, newPath)
            self.filePath = newPath
            bRet = True
        except Exception, e:
            printExc()
            msg = str(e)
        return bRet, msg

    def getUrl(self):
        return self.url

    def start(self, url, filePath, params={}):
        self.url = url
        self.filePath = filePath
        self.downloaderParams = params
        self.fileExtension = '' # should be implemented in future

        sts, remoteInfo = DMHelper.getRemoteContentInfoByUrllib(url, params)
        if False == sts:
            return BaseDownloader.CODE_WRONG_LINK
        else:
            self.remoteFileSize = int(remoteInfo.get('Content-Length', '-1'))

        sts = self._start()
        if sts == BaseDownloader.CODE_OK:
            self.onStart()
        return sts

    def terminate(self):
        '''
           terminate downloading
           return True,CODE_NO_ERROR if success
        '''
        sts = self._terminate()
        if sts == BaseDownloader.CODE_OK:
            self.onFinish()
        return sts

    def updateStatistic(self):
        self.localFileSize = DMHelper.getFileSize(self.filePath)
        self._updateStatistic()

    def _updateStatistic(self):
        prevUpdateTime = self.lastUpadateTime
        newTime = datetime.datetime.now()
        # calculate downloaded Speed
        if prevUpdateTime:
            deltaSize = self.localFileSize - self.prevLocalFileSize
            deltaTime = (newTime - prevUpdateTime).seconds
            if deltaTime > 0:
                self.downloadSpeed = deltaSize / deltaTime
                self.lastUpadateTime = newTime
                self.prevLocalFileSize = self.localFileSize
        else:
            self.lastUpadateTime = newTime
            self.prevLocalFileSize = self.localFileSize

    def getRemoteFileSize(self):
        return self.remoteFileSize

    def getLocalFileSize(self, update=False):
        if update:
            self.updateStatistic()
        return self.localFileSize

    def getDownloadSpeed(self):
        return self.downloadSpeed

    def getPlayableFileSize(self):
        return self.getLocalFileSize()

    def onStart(self):
        for SubscriberFunction in self.subscribersFor_Start:
            SubscriberFunction()

    def onFinish(self):
        for SubscriberFunction in self.subscribersFor_Finish:
            SubscriberFunction(self.status)

    def subscribeFor_Finish(self, function):
        if function not in self.subscribersFor_Finish:
            self.subscribersFor_Finish.append(function)

    def unsubscribeFor_Finish(self, function):
        if function in self.subscribersFor_Finish:
            self.subscribersFor_Finish.remove(function)

    def subscribeFor_Start(self, function):
        if function not in self.subscribersFor_Start:
            self.subscribersFor_Start.append(function)

    def unsubscribeFor_Start(self, function):
        if function in self.subscribersFor_Start:
            subscribersFor_Start.remove(function)

    def _start(self):
        raise BaseException("_start not implemented")

    def _terminate(self):
        raise BaseException("_terminate not implemented")
