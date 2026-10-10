# -*- coding: utf-8 -*-
# Last Modified: 05.09.2026 - cmdFinished() now runs the downloader's reported
# fileName through downloaderhelpers.ensureText() (the same helper HLSDownloader/
# WgetDownloader/MergeDownloader already use internally) and falls back to
# DMItem.originalFileName if the downloader ever hands back an empty/invalid
# path, instead of trusting getFullFileName() as-is.
# 12.07.2026 - added preCheckOnly handling to show "Download already exists" instead of FAILED
# 20.09.2026 - DMItem.itemKey + getActiveItemKeys(), cmdFinished() writes the "downloaded" marker (tools/iptvdownloaded.py)
# 10.10.2026 - batch download: items without url (DMItem.batchSource) are looked up when their turn comes
#              (queueRS, startResolve/pollResolve, iptvdm/batchdownload.py), one summary notification per batch
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
from Components.config import config
from Tools.BoundFunction import boundFunction
from enigma import eTimer
from time import sleep
import datetime
import os
import time
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
        # batch download (iptvdm/batchdownload.py): what it takes to reopen the list row later - the url
        # is only looked up when the download manager starts the item (url '' until then); None = normal item
        self.batchSource = None
        self.batchId = 0
        # why the item could not be started (shown in the list), '' otherwise
        self.errorReason = ''


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
        # batch items whose links are looked up right now - at most one at a time (see processDQ),
        # it holds a download slot like a running download
        self.queueRS = []
        self.resolveThread = None
        # host name -> time the last link lookup of a batch item of that host ended (IPTVDMBatchPause)
        self.lastBatchLookup = {}

        self.onlistChanged = []

        # main Queue
        self.mainTimer = eTimer()
        self.mainTimer_conn = eConnectCallback(self.mainTimer.timeout, self.processDQ)
        # runs only while a batch item is looked up: checks the worker thread (pollResolve)
        self.resolveTimer = eTimer()
        self.resolveTimer_conn = eConnectCallback(self.resolveTimer.timeout, self.pollResolve)

        # batch id -> {downloadIdx: [title, state]}, state None (not finished yet) / 'ok' / 'failed' / 'removed'
        self.batchIdx = 0
        self.batches = {}

        self.finishNotifyCallback = finishNotifyCallback
        return

    def __del__(self):
        printDBG("IPTVDMApi.__del__ -------------------")
        if True is self.running:
            self.running = False
            self.mainTimer.stop()
        self.abortResolve()
        self.stopAllDownloadItem()
        self.mainTimer_conn = None
        self.mainTimer = None
        self.resolveTimer_conn = None
        self.resolveTimer = None
        return

    def setUpdateProgress(self, update=True):
        self.updateProgress = update
        return

    def isRunning(self):
        return self.running

    def stopDownloadItem(self, downloadIdx):
        if -1 < self.findIdxInQueueRS(downloadIdx):
            # a batch item whose links are looked up: give up the lookup, the item ends as ERROR
            self.abortResolve(_("Cancelled."))
            return
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
            # delete file - a batch item not looked up yet has no file, only its title as a name
            if not self.hasNoFile(item):
                try:
                    os.remove(item.fileName)
                except Exception:
                    printDBG("deleteDownloadItem removing file[%s] error" % item.fileName)
                # hlsdl's resume sidecar belongs to the file (no-op for the other downloaders)
                DMHelper.removeHlsdlResumeFiles(item.fileName)

            # remove item from self.queueDQ
            del self.queueDQ[listUDIdx]
            self._setBatchItemState(item, 'removed')
            bRet = True
        else:
            # a batch item that ended before it was looked up (ERROR): there is no file to remove
            listAAIdx = self.findIdxInQueueAA(downloadIdx)
            if -1 < listAAIdx and self.hasNoFile(self.queueAA[listAAIdx]):
                del self.queueAA[listAAIdx]
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

            # delete file - not for a batch item that never had one (the web interface offers "Delete" on ERROR)
            if not self.hasNoFile(item):
                try:
                    os.remove(item.fileName)
                except Exception:
                    printDBG("removeDownloadItem removing file[%s] error" % item.fileName)
                # hlsdl's resume sidecar belongs to the file (no-op for the other downloaders)
                DMHelper.removeHlsdlResumeFiles(item.fileName)

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
            self._setBatchItemState(item, None)

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
            item.errorReason = ''
            if item.batchSource is not None:
                # batch item: hoster links expire, its links are looked up again (startResolve)
                item.url = ''
            self.queueDQ.append(item)
            # remove processed item from self.queueAA
            del self.queueAA[listUDIdx]
            self._setBatchItemState(item, None)

    def stopWorkThread(self):
        ''' Can be called only from main thread'''
        if True is self.running:
            self.running = False
            self.mainTimer.stop()

        # a batch item being looked up goes back to the front of the queue
        self.abortResolve()
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
        # a batch item has no url before it is looked up - the list row it comes from tells it apart
        if not url and getattr(item, 'batchSource', None) is not None:
            return 'batch:' + item.itemKey
        try:
            if isinstance(url, str) and url.startswith('merge://'):
                meta = getattr(url, 'meta', {})
                keys = url.split('merge://', 1)[1].split('|')
                return 'merge://' + '|'.join(str(meta.get(k, k)) for k in keys)
        except Exception:
            pass
        return url

    def _appendToDQueue(self, newItem):
        # check if there is no Item with this same source already in
        # queue - see _dedupKey() for why this isn't a plain .url compare.
        newKey = self._dedupKey(newItem)
        for item in self.queueDQ:
            if self._dedupKey(item) == newKey:
                return False
        self.downloadIdx += 1
        newItem.downloadIdx = self.downloadIdx
        self.queueDQ.append(newItem)
        return True

    def addToDQueue(self, newItem):
        bRet = self._appendToDQueue(newItem)
        if bRet:
            self.listChanged()
        return bRet

    def addBatchToDQueue(self, newItems):
        # the rows of one batch download (items with batchSource, see batchdownload.py) - one list update for
        # all of them; the summary notification comes when the last of them has ended. Returns how many were added.
        self.batchIdx += 1
        record = {}
        for newItem in newItems:
            if self._appendToDQueue(newItem):
                newItem.batchId = self.batchIdx
                record[newItem.downloadIdx] = [newItem.batchSource.get('title', ''), None]
        if record:
            self.batches[self.batchIdx] = record
            self.listChanged()
        return len(record)

    def getActiveItemKeys(self):
        # item keys of the downloads that are waiting in the queue, looked up or running right now
        return {item.itemKey for item in list(self.queueDQ) + list(self.queueRS) + list(self.queueUD) if getattr(item, 'itemKey', '')}

    @staticmethod
    def needsResolve(item):
        # a batch item whose links were not looked up yet
        return getattr(item, 'batchSource', None) is not None and not item.url

    @staticmethod
    def hasNoFile(item):
        # a batch item that never got to a download: its file name is still the title without an extension -
        # removing "its file" would hit any file of exactly that name
        source = getattr(item, 'batchSource', None)
        return source is not None and item.fileName == source.get('file')

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
            if len(self.queueUD) + len(self.queueRS) < self.MAX_DOWNLOAD_ITEM and \
               0 < len(self.queueDQ):
                if self.needsResolve(self.queueDQ[0]):
                    # batch item: look up its links first - one at a time, the queue keeps its order, and not
                    # before the pause after the last lookup of the same host is over (this timer comes again)
                    if 0 == len(self.queueRS) and 0 == self._batchPauseLeft(self.queueDQ[0]):
                        self.startResolve(self.queueDQ.pop(0))
                        dListChanged = True
                else:
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

    ###################################################
    # batch download: looking up the links of an item
    ###################################################
    def _batchPauseLeft(self, item):
        # seconds until the links of this batch item may be looked up (config IPTVDMBatchPause per host)
        from Plugins.Extensions.IPTVPlayer.iptvdm.batchdownload import batchPauseLeft
        try:
            host = item.batchSource.get('host', '')
            return batchPauseLeft(self.lastBatchLookup.get(host, 0), time.time(), config.plugins.iptvplayer.IPTVDMBatchPause.value)
        except Exception:
            printExc()
        return 0

    def startResolve(self, item):
        # the item holds a download slot while its links are looked up in a worker thread
        # (batchdownload.BatchResolveThread); pollResolve() checks it from the main thread
        printDBG("startResolve for downloadIdx[%d] [%s]" % (item.downloadIdx, item.batchSource.get('title', '')))
        from Plugins.Extensions.IPTVPlayer.iptvdm.batchdownload import BatchResolveThread
        item.status = DMHelper.STS.RESOLVING
        item.errorReason = ''
        # nothing written yet: the file gets a free name like a new download; "Download again" of an item that
        # had a file (retryDownloadItem) writes it anew - the new url never continues a file of another one
        item.tries = DMHelper.DOWNLOAD_TYPE.INITIAL if self.hasNoFile(item) else DMHelper.DOWNLOAD_TYPE.RETRY
        self.queueRS.append(item)
        try:
            self.resolveThread = BatchResolveThread(item.batchSource, item.downloadIdx)
            self.resolveThread.start()
        except Exception:
            printExc()
            self.resolveThread = None
            self._endResolve(item, [], _("No valid links available."))
            return
        self.resolveTimer.start(200)

    def pollResolve(self):
        # timer in the main thread while a batch item is looked up
        thread = self.resolveThread
        if thread is None:
            self.resolveTimer.stop()
            return
        self._pumpMainQueue()
        if thread.finished:
            self.resolveThread = None
            self.resolveTimer.stop()
            listRSIdx = self.findIdxInQueueRS(thread.downloadIdx)
            if -1 < listRSIdx:
                self._endResolve(self.queueRS[listRSIdx], thread.candidates, thread.error)
        else:
            from Plugins.Extensions.IPTVPlayer.iptvdm.batchdownload import RESOLVE_TIMEOUT
            if thread.elapsed() > RESOLVE_TIMEOUT:
                printDBG("pollResolve downloadIdx[%d] timed out" % thread.downloadIdx)
                self.abortResolve(_("Operation timed out."))

    def abortResolve(self, reason=None):
        # gives up the running lookup; reason None: the item goes back to the front of the queue (download
        # manager stopped), otherwise it ends as ERROR with that reason
        thread = self.resolveThread
        self.resolveThread = None
        try:
            self.resolveTimer.stop()
        except Exception:
            printExc()
        if thread is not None:
            thread.cancel()
        while 0 < len(self.queueRS):
            item = self.queueRS.pop(0)
            if reason is None:
                item.status = DMHelper.STS.WAITING
                self.queueDQ.insert(0, item)
                self.listChanged()
            else:
                self._endResolve(item, [], reason, isInRS=False)

    def _endResolve(self, item, candidates, reason, isInRS=True):
        # main thread: the first candidate a downloader can be created for starts the normal download,
        # without one the item ends as ERROR and the queue goes on
        from Plugins.Extensions.IPTVPlayer.iptvdm.batchdownload import pickDownloadable
        from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdownloadercreator import IsUrlDownloadable
        if isInRS and item in self.queueRS:
            self.queueRS.remove(item)
        try:
            # the pause before the next lookup of this host counts from here
            self.lastBatchLookup[item.batchSource.get('host', '')] = time.time()
        except Exception:
            printExc()
        url, fileExt = None, ''
        if candidates:
            try:
                url, fileExt, why = pickDownloadable(candidates, item.batchSource.get('type', ''), IsUrlDownloadable)
                reason = reason or why
            except Exception:
                printExc()
                url = None
        if url is not None:
            printDBG("_endResolve downloadIdx[%d] url[%s]" % (item.downloadIdx, url))
            previousFileName = item.fileName
            item.url = url
            if self.hasNoFile(item):
                item.fileName = item.batchSource['file'] + fileExt
            item.status = DMHelper.STS.WAITING
            self.queueUD.append(item)
            try:
                self.runCMD(item)
                self.listChanged()
                return
            except Exception:
                printExc()
                if item in self.queueUD:
                    self.queueUD.remove(item)
                # the same check that kept it from the queue: no downloader for this url
                reason = _("File can not be downloaded. Protocol [%s] is unsupported") % url.meta.get('iptv_proto', '')
                item.url = ''
                item.fileName = previousFileName
                item.downloader = None
        printDBG("_endResolve downloadIdx[%d] failed [%s]" % (item.downloadIdx, reason))
        item.status = DMHelper.STS.ERROR
        item.errorReason = reason or _("No valid links available.")
        item.processed = True
        self.queueAA.append(item)
        self._setBatchItemState(item, 'failed')
        self.listChanged()

    @staticmethod
    def _pumpMainQueue():
        # Hosts hand some work to the main thread (asynccall.DelegateToMainThread: JS interpreters, external
        # programs). That queue is worked off by the E2iPlayer screen - with the screen closed the download
        # manager does it while a lookup runs (the web interface does the same for its threads).
        try:
            from Plugins.Extensions.IPTVPlayer.components import asynccall
            queue = asynccall.gMainFunctionsQueueTab[0]
            if queue is not None and queue.procFun is None:
                queue.processQueue()
        except Exception:
            printExc()

    def _setBatchItemState(self, item, state):
        # state of a batch item for the summary: None (in the queue again), 'ok', 'failed', 'removed'
        record = self.batches.get(getattr(item, 'batchId', 0))
        if record is None or item.downloadIdx not in record:
            return
        record[item.downloadIdx][1] = state
        if state is None:
            return
        for title, itemState in record.values():
            if itemState is None:
                return
        # the last item of the batch has ended: one notification for all of them
        del self.batches[item.batchId]
        try:
            from Plugins.Extensions.IPTVPlayer.iptvdm.batchdownload import batchSummary
            summary = batchSummary([record[idx] for idx in sorted(record)])
            if summary is None:
                # the user took all of them out of the queue
                return
            text, status, colour = summary
            printDBG("batch download [%d] finished: %s %s" % (item.batchId, text, status))
            if self.finishNotifyCallback is not None:
                self.finishNotifyCallback().showNotify(text, status, colour)
        except Exception:
            printExc()

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
        self._setBatchItemState(item, 'ok' if item.status == DMHelper.STS.DOWNLOADED else 'failed')
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

    def findIdxInQueueRS(self, downloadIdx):
        for listIdx in range(len(self.queueRS)):
            if self.queueRS[listIdx].downloadIdx == downloadIdx:
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
        # a download without a known size (no Content-Length, chunked) has no percentage at all -
        # there the downloader's own verdict counts
        finishedWithoutSize = dItem.downloadedProcent < 0 and dItem.downloadedSize > 0 and dItem.downloader.getStatus() == DMHelper.STS.DOWNLOADED
        if dItem.downloadedProcent > 99 or finishedWithoutSize:
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
        # batch items whose links are looked up
        tmpList.extend(self.queueRS)
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
