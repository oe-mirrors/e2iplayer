# -*- coding: utf-8 -*-
# Last Modified: 05.09.2026 - cmdFinished() now runs the downloader's reported
# fileName through downloaderhelpers.ensureText() (the same helper HLSDownloader/
# WgetDownloader/MergeDownloader already use internally) and falls back to
# DMItem.originalFileName if the downloader ever hands back an empty/invalid
# path, instead of trusting getFullFileName() as-is.
# 12.07.2026 - added preCheckOnly handling to show "Download already exists" instead of FAILED
# 20.09.2026 - DMItem.itemKey + getActiveItemKeys(), cmdFinished() writes the "downloaded" marker (tools/iptvdownloaded.py)
#
# IPTV download manager API
#
# $Id$
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper, DMItemBase
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import DownloaderCreator
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import ensureText
from Plugins.Extensions.IPTVPlayer.tools import iptvdownloaded
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
###################################################

###################################################
# FOREIGN import
###################################################
from Tools.BoundFunction import boundFunction
from enigma import eTimer
from time import sleep
import datetime
import os
###################################################


class DMItem(DMItemBase):
    def __init__(self, url, fileName):
        DMItemBase.__init__(self, url, fileName)

        self.processed = False
        self.downloadIdx = -1
        # keep the originally requested path so we can fall back to it
        # if a downloader ever returns a bogus/empty renamed path
        self.originalFileName = fileName
        # key of the host item the download was started from (tools/iptvdownloaded.py), '' if unknown
        self.itemKey = ''


class IPTVDMApi():

    def __init__(self, refreshDelay=2, parallelDownloadNum=1, finishNotifyCallback=None):
        self.running = False
        self.downloadIdx = 0
        self.downloading = False

        self.updateProgress = False
        self.sleepDelay = refreshDelay

        # self.currDMItem = None
        # under download queue
        self.queueUD = []
        self.MAX_DOWNLOAD_ITEM = parallelDownloadNum
        # already downloaded
        self.queueAA = []
        # waiting for download queue
        self.queueDQ = []

        self.onlistChanged = []

        # main Queue
        self.mainTimer = eTimer()
        self.mainTimer_conn = eConnectCallback(self.mainTimer.timeout, self.processDQ)

        self.finishNotifyCallback = finishNotifyCallback
        return

    def __del__(self):
        printDBG("IPTVDMApi.__del__ -------------------")
        if True is self.running:
            self.running = False
            self.mainTimer.stop()
        self.stopAllDownloadItem()
        self.mainTimer_conn = None
        self.mainTimer = None
        return

    def setUpdateProgress(self, update=True):
        self.updateProgress = update
        return

    def isRunning(self):
        return self.running

    def stopDownloadItem(self, downloadIdx):
        listUDIdx = self.findIdxInQueueUD(downloadIdx)
        if -1 < listUDIdx and None is not self.queueUD[listUDIdx].downloader:
            self.queueUD[listUDIdx].downloader.terminate()
            # give some time to finish
            sleep(1)
            # manually run endCmd because when killed
            # appClosed is not called
            self.cmdFinished(downloadIdx, -1)

    def stopAllDownloadItem(self):
            while len(self.queueUD) > 0:
                downloadIdx = self.queueUD[0].downloadIdx
                self.queueUD[0].downloader.terminate()
                self.cmdFinished(downloadIdx, -1)

    def moveToTopDownloadItem(self, downloadIdx):
        printDBG("moveToTopDownloadItem for downloadIdx[%d]" % downloadIdx)
        bRet = False
        listUDIdx = self.findIdxInQueueDQ(downloadIdx)
        if -1 < listUDIdx and 1 < len(self.queueDQ):
            # get item from self.queueDQ
            item = self.queueDQ[listUDIdx]
            # remove item from self.queueDQ
            del self.queueDQ[listUDIdx]
            # add to top of list
            self.queueDQ.insert(0, item)
            bRet = True

        if bRet:
            self.listChanged()

    def moveQueueDQItem(self, downloadIdx, newQueueIdx):
        """Reorder a still-waiting item (identified by downloadIdx) to
        position newQueueIdx within queueDQ. Used by IPTVDMWidget's
        reordering mode - the UI is responsible for only offering this
        while the DM is inactive (nothing is popping items off the front
        of queueDQ concurrently) and for keeping newQueueIdx within the
        waiting segment of its own displayed list."""
        printDBG("moveQueueDQItem downloadIdx[%d] -> newQueueIdx[%d]" % (downloadIdx, newQueueIdx))
        curIdx = self.findIdxInQueueDQ(downloadIdx)
        if -1 == curIdx or newQueueIdx < 0 or newQueueIdx >= len(self.queueDQ):
            return False
        item = self.queueDQ.pop(curIdx)
        self.queueDQ.insert(newQueueIdx, item)
        self.listChanged()
        return True

    def deleteDownloadItem(self, downloadIdx):
        printDBG("deleteDownloadItem for downloadIdx[%d]" % downloadIdx)
        bRet = False

        listUDIdx = self.findIdxInQueueDQ(downloadIdx)
        if -1 < listUDIdx:
            # get processed item from self.queueDQ
            item = self.queueDQ[listUDIdx]

            # generaly the file should not exist but when it
            # tries == CONTINUE_DOWNLOAD it exist
            # delete file
            try:
                os.remove(item.fileName)
            except Exception:
                printDBG("deleteDownloadItem removing file[%s] error" % item.fileName)

            # remove item from self.queueDQ
            del self.queueDQ[listUDIdx]
            bRet = True

        if bRet:
            self.listChanged()

    def removeDownloadItem(self, downloadIdx):
        printDBG("removeDownloadItem for downloadIdx[%d]" % downloadIdx)
        bRet = False
        listUDIdx = self.findIdxInQueueAA(downloadIdx)
        if -1 < listUDIdx:
            # get processed item from self.queueAA
            item = self.queueAA[listUDIdx]

            # delete file
            try:
                os.remove(item.fileName)
            except Exception:
                printDBG("removeDownloadItem removing file[%s] error" % item.fileName)

            # remove item from self.queueAA
            del self.queueAA[listUDIdx]
            bRet = True

        if bRet:
            self.listChanged()

    def continueDownloadItem(self, downloadIdx):
        listUDIdx = self.findIdxInQueueAA(downloadIdx)
        if -1 < listUDIdx:
            # get processed item from self.queueAA
            item = self.queueAA[listUDIdx]

            item.status = DMHelper.STS.WAITING
            # item.fileSize = -1
            item.downloadedSize = 0
            item.downloadedProcent = -1
            item.totalFileDuration = -1
            item.downloadedFileDuration = -1
            item.downloadedSpeed = 0
            item.timeToFinish = -1

            item.processed = False
            item.tries = DMHelper.DOWNLOAD_TYPE.CONTINUE
            self.queueDQ.append(item)
            # remove processed item from self.queueAA
            del self.queueAA[listUDIdx]

    def retryDownloadItem(self, downloadIdx):
        listUDIdx = self.findIdxInQueueAA(downloadIdx)
        if -1 < listUDIdx:
            # get processed item from self.queueAA
            item = self.queueAA[listUDIdx]

            item.status = DMHelper.STS.WAITING
            item.fileSize = -1
            item.downloadedSize = 0
            item.downloadedProcent = -1
            item.totalFileDuration = -1
            item.downloadedFileDuration = -1
            item.downloadedSpeed = 0
            item.timeToFinish = -1

            item.processed = False
            item.tries = DMHelper.DOWNLOAD_TYPE.RETRY
            self.queueDQ.append(item)
            # remove processed item from self.queueAA
            del self.queueAA[listUDIdx]

    def stopWorkThread(self):
        ''' Can be called only from main thread'''
        if True is self.running:
            self.running = False
            self.mainTimer.stop()

        self.stopAllDownloadItem()

    def runWorkThread(self):
        ''' Can be called only from main thread'''
        if False is self.running:
            self.running = True
            self.mainTimer.start(self.sleepDelay * 1000)

    @staticmethod
    def _dedupKey(item):
        """Identity key for addToDQueue()'s "already queued" check. Plain
        .url works for a regular item, but merge:// sources (e.g. YouTube's
        audio+video merge scheme) use a generic literal string like
        "merge://audio_url|video_url" that's identical for every video of
        that kind - the real per-video URLs only live in .meta. Resolve
        those in so two different merge:// videos are correctly told
        apart, while dedup still keys on the actual source (not the
        destination filename) - two adds of the same title from two
        different mirrors/sources are legitimately different downloads,
        not a duplicate, and get to queue and race to makeUnikalFileName
        at start like before."""
        url = item.url
        try:
            if isinstance(url, str) and url.startswith('merge://'):
                meta = getattr(url, 'meta', {})
                keys = url.split('merge://', 1)[1].split('|')
                return 'merge://' + '|'.join(str(meta.get(k, k)) for k in keys)
        except Exception:
            pass
        return url

    def addToDQueue(self, newItem):
        bRet = False

        # check if there is no Item with this same source already in
        # queue - see _dedupKey() for why this isn't a plain .url compare.
        exist = False
        newKey = self._dedupKey(newItem)
        for item in self.queueDQ:
            if self._dedupKey(item) == newKey:
                exist = True
        if False is exist:
            self.downloadIdx += 1
            newItem.downloadIdx = self.downloadIdx
            self.queueDQ.append(newItem)
            bRet = True
        if bRet:
            self.listChanged()
        return bRet

    def getActiveItemKeys(self):
        # item keys of the downloads that are waiting in the queue or running right now
        return {item.itemKey for item in list(self.queueDQ) + list(self.queueUD) if getattr(item, 'itemKey', '')}

    def addBufferItem(self, downloader, fullFilesPaths=[]):
        if downloader.getStatus() == DMHelper.STS.DOWNLOADING:
            if len(self.queueUD) >= self.MAX_DOWNLOAD_ITEM:
                return False, _('Max number of parallel downloads has been reached.')

        bRet, msg = False, ''
        for newFilePath in fullFilesPaths:
            newFilePath = DMHelper.makeUnikalFileName(newFilePath, False, False)
            bRet, msg = downloader.moveFullFileName(newFilePath)
            if bRet:
                msg = newFilePath
                break

        if bRet:
            newItem = DMItem(downloader.getUrl(), downloader.getFullFileName())

            # at now we need to pack it to download item
            self.downloadIdx += 1
            newItem.downloadIdx = self.downloadIdx
            newItem.downloader = downloader
            newItem.downloaderName = downloader.getName()
            newItem.status = downloader.getStatus()

            self.updateItemSTS(newItem)
            if downloader.getStatus() == DMHelper.STS.DOWNLOADING:
                newItem.callback = boundFunction(self.cmdFinished, newItem.downloadIdx)
                newItem.downloader.subscribeFor_Finish(newItem.callback)
                self.queueUD.append(newItem)
                self.runWorkThread()
            else:
                self.queueAA.append(newItem)

            self.listChanged()

        return bRet, msg

    def processDQ(self):
            if False is self.running:
                return
            dListChanged = False
            if len(self.queueUD) < self.MAX_DOWNLOAD_ITEM and \
               0 < len(self.queueDQ):
                item = self.queueDQ.pop(0)
                self.queueUD.append(item)
                dListChanged = True

                # start downloading
                self.runCMD(item)

            if 0 < len(self.queueUD):
                self.downloading = True
            else:
                self.downloading = False

            if dListChanged:
                self.listChanged()

            if self.downloading and self.updateProgress:
                self.updateDownloadItemsStatus()

    def runCMD(self, item):
        printDBG("runCMD for downloadIdx[%d]" % item.downloadIdx)

        if DMHelper.DOWNLOAD_TYPE.INITIAL == item.tries:
           item.fileName = DMHelper.makeUnikalFileName(item.fileName, False, False)

        printDBG("Downloading started downloadIdx[%s] File[%s] URL[%s]" % (item.downloadIdx, item.fileName, item.url))

        listUDIdx = self.findIdxInQueueUD(item.downloadIdx)
        self.queueUD[listUDIdx].status = DMHelper.STS.DOWNLOADING
        self.queueUD[listUDIdx].fileName = item.fileName
        # remember the path we actually asked for, so cmdFinished() has a
        # safe value to fall back to if the downloader ever reports an
        # empty/invalid renamed path
        self.queueUD[listUDIdx].originalFileName = item.fileName

        url, downloaderParams = DMHelper.getDownloaderParamFromUrl(item.url)
        self.queueUD[listUDIdx].downloader = DownloaderCreator(url, forDownload=True)
        # this is a real download (not buffered playback) -> the downloader may
        # rename the finished file to its true container extension
        try:
            self.queueUD[listUDIdx].downloader.allowFinalRename = True
            if DMHelper.DOWNLOAD_TYPE.CONTINUE == item.tries:
                self.queueUD[listUDIdx].downloader.resumeExisting = True
            self.queueUD[listUDIdx].downloaderName = self.queueUD[listUDIdx].downloader.getName()
        except Exception:
            printExc()
        self.queueUD[listUDIdx].callback = boundFunction(self.cmdFinished, item.downloadIdx)
        self.queueUD[listUDIdx].downloader.subscribeFor_Finish(self.queueUD[listUDIdx].callback)
        self.queueUD[listUDIdx].downloader.start(url, item.fileName, downloaderParams)

    def cmdFinished(self, downloadIdx, retval=None):
        printDBG("cmdFinished downloadIdx[%d]" % downloadIdx)

        listUDIdx = self.findIdxInQueueUD(downloadIdx)

        # listUDIdx must be > -1
        if -1 >= listUDIdx:
            return

        # a downloader may have renamed the finished file (e.g. FFMPEGDownloader
        # fixing .mp4 -> .mkv to match the real container); pick up the real path
        # so notify / archive / delete all use it. No-op for downloaders that
        # never change it.
        #
        # getFullFileName() can come back wrapped in a str SUBCLASS (e.g.
        # e2iPlayer's own "strwithmeta") after a rename; ensureText() - the
        # same helper HLSDownloader/WgetDownloader/MergeDownloader already use
        # for their own path handling - normalizes that before we store it,
        # and we fall back to the originally requested path if the downloader
        # ever hands back an empty/invalid one instead of trusting it blindly.
        try:
            dl = self.queueUD[listUDIdx].downloader
            if dl is not None:
                realPath = ensureText(dl.getFullFileName()).strip()

                if realPath and realPath != self.queueUD[listUDIdx].fileName:
                    printDBG("cmdFinished: downloader renamed file -> %s" % realPath)
                    self.queueUD[listUDIdx].fileName = realPath
                elif not realPath:
                    printDBG("cmdFinished: downloader returned empty/invalid path, keeping previous fileName[%s]" %
                        self.queueUD[listUDIdx].fileName)
        except Exception:
            printExc()

        self.queueUD[listUDIdx].fileName = ensureText(self.queueUD[listUDIdx].fileName)
        if not self.queueUD[listUDIdx].fileName:
            fallback = ensureText(getattr(self.queueUD[listUDIdx], 'originalFileName', u''))
            if fallback:
                printDBG("cmdFinished: invalid fileName, falling back to originalFileName[%s]" % fallback)
                self.queueUD[listUDIdx].fileName = fallback

        self.updateDownloadedItemStatus(listUDIdx)
        try:
            # remember it for the "downloaded" marker at the end of the item's list row
            if self.queueUD[listUDIdx].status == DMHelper.STS.DOWNLOADED and self.queueUD[listUDIdx].itemKey:
                iptvdownloaded.markDownloaded(self.queueUD[listUDIdx].itemKey, self.queueUD[listUDIdx].fileName)
        except Exception:
            printExc()
        self.queueUD[listUDIdx].processed = True
        self.queueUD[listUDIdx].downloader.unsubscribeFor_Finish(self.queueUD[listUDIdx].callback)
        self.queueUD[listUDIdx].downloader = None
        self.queueUD[listUDIdx].callback = None

        item = self.queueUD[listUDIdx]
        printDBG("Downloading finished idx[%s] File[%s] URL[%s]" % (downloadIdx, item.fileName, item.url))

        item = self.queueUD[listUDIdx]
        # add processed item to self.queueAA
        self.queueAA.append(item)
        # remove processed item from self.queueUD
        del self.queueUD[listUDIdx]
        self.listChanged()

    def findIdxInQueueDQ(self, downloadIdx):
        # function should be called from locked area
        for listIdx in range(len(self.queueDQ)):
            if self.queueDQ[listIdx].downloadIdx == downloadIdx:
                return listIdx
        return -1

    def findIdxInQueueUD(self, downloadIdx):
        # function should be called from locked area
        for listIdx in range(len(self.queueUD)):
            if self.queueUD[listIdx].downloadIdx == downloadIdx:
                return listIdx
        return -1

    def findIdxInQueueAA(self, downloadIdx):
        # function should be called from locked area
        for listIdx in range(len(self.queueAA)):
            if self.queueAA[listIdx].downloadIdx == downloadIdx:
                return listIdx
        return -1

    def updateDownloadedItemStatus(self, listUDIdx):
        printDBG("updateDownloadedItemStatus listUDIdx[%d]" % listUDIdx)
        self.updateItemSTS(self.queueUD[listUDIdx])
        # dItem - copy only for reading filed
        dItem = self.queueUD[listUDIdx]
        # preCheckOnly - download already exists, show info instead of FAILED
        if getattr(dItem.downloader, 'preCheckOnly', False):
            self.queueUD[listUDIdx].status = DMHelper.STS.DOWNLOADED
            try:
                fileName = self.queueUD[listUDIdx].fileName.split('/')[-1]
                # the notification box sizes itself to the text, so this
                # cap is just a generous guard against pathological
                # filenames
                shortName = fileName[:100]
                if len(fileName) > len(shortName):
                    shortName += '...'
                # status gets its own line below the filename, colored
                # per outcome
                self.finishNotifyCallback().showNotify(shortName, _('Download already exists'), 'green')
            except Exception:
                printExc()
            return

        status = _('UNKNOWN')
        statusColor = 'white'
        if dItem.downloadedProcent > 99:
            self.queueUD[listUDIdx].status = DMHelper.STS.DOWNLOADED
            status = _('DOWNLOADED')
            statusColor = 'green'
        else:
            if dItem.downloadedSize > 0:
                self.queueUD[listUDIdx].status = DMHelper.STS.INTERRUPTED
                status = _('INTERRUPTED')
                statusColor = 'orange'
            else:
                self.queueUD[listUDIdx].status = DMHelper.STS.ERROR
                status = _('FAILED')
                statusColor = 'red'

        try:
            fileName = self.queueUD[listUDIdx].fileName.split('/')[-1]
            # the notification box sizes itself to the text, so this cap
            # is just a generous guard against pathological filenames
            shortName = fileName[:100]
            if len(fileName) > len(shortName):
                shortName += '...'
            self.finishNotifyCallback().showNotify(shortName, status, statusColor)
        except Exception:
            printExc()

        # dItem = self.queueUD[listUDIdx]
        # print( dItem.fileName + ": "+ " status: " + dItem.status + dItem.downloadedSize + " " + dItem.downloadedProcent + " " + dItem.downloadedSpeed + " " + dItem.timeToFinish )
    # end updateEndItemStatus

    def updateItemSTS(self, downloadItem):
        printDBG("updateItemSTS downloadIdx[%d]" % downloadItem.downloadIdx)
        downloadItem.downloader.updateStatistic()
        downloadItem.downloadedSize = downloadItem.downloader.getLocalFileSize()
        downloadItem.fileSize = downloadItem.downloader.getRemoteFileSize()
        downloadItem.downloadedSpeed = downloadItem.downloader.getDownloadSpeed()

        if downloadItem.downloader.hasDurationInfo():
            downloadItem.totalFileDuration = downloadItem.downloader.getTotalFileDuration()
            downloadItem.downloadedFileDuration = downloadItem.downloader.getDownloadedFileDuration()

        # calculate downloadedProcent
        if downloadItem.fileSize > 0 and downloadItem.downloadedSize > 0:
            downloadItem.downloadedProcent = int((100 * downloadItem.downloadedSize) / downloadItem.fileSize)
        elif downloadItem.totalFileDuration > 0 and downloadItem.downloadedFileDuration > 0:
            # round, don't truncate: ffmpeg's decoded end time often lands a hair
            # below the summed playlist duration on a complete file, and int()
            # would leave it at 99 -> the DM would flag a finished download as
            # INTERRUPTED
            downloadItem.downloadedProcent = int(round((100.0 * downloadItem.downloadedFileDuration) / downloadItem.totalFileDuration))
        return True

    def updateDownloadItemsStatus(self):
        stsChanged = False
        printDBG("updateDownloadItemsStatus")
        for listUDIdx in range(len(self.queueUD)):
            if self.updateItemSTS(self.queueUD[listUDIdx]):
                stsChanged = True
        if stsChanged:
            self.listChanged()
    # end updateDownloadItemsStatus

    def getList(self):
        list = []
        printDBG("getList")
        tmpList = []
        # under downloading
        tmpList.extend(self.queueUD)
        # waiting for dowlnoad
        tmpList.extend(self.queueDQ)
        # already processedupdateItemSTS
        tmpList.extend(self.queueAA)
        list = tmpList[:]
        return list

    def connectListChanged(self, fnc):
        if fnc not in self.onlistChanged:
            self.onlistChanged.append(fnc)

    def disconnectListChanged(self, fnc):
        if fnc in self.onlistChanged:
            self.onlistChanged.remove(fnc)

    def listChanged(self):
        printDBG("listChanged()")
        for x in self.onlistChanged:
            x()
