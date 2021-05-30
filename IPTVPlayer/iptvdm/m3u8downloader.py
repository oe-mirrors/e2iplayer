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
from Plugins.Extensions.IPTVPlayer.libs import m3u8
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
###################################################

###################################################
# FOREIGN import
###################################################
from Tools.BoundFunction import boundFunction
from enigma import eConsoleAppContainer
from time import sleep, time
import re
import datetime
###################################################

###################################################
# One instance of this class can be used only for
# one download
###################################################


def DebugToFile(message, file="/home/sulge/tmp/m3u8.txt"):
    with open(file, "a") as myfile:
        myfile.write(message + "\n")


class M3U8Downloader(BaseDownloader):
    MIN_REFRESH_DELAY = 1
    MAX_RETRIES = 3
    WGET_TIMEOUT = 10
    LIVE_START_OFFSET = 120
    # wget status
    WGET_STS = enum(NONE='WGET_NONE',
                     CONNECTING='WGET_CONNECTING',
                     DOWNLOADING='WGET_DOWNLOADING',
                     ENDED='WGET_ENDED')
    # local status
    DOWNLOAD_TYPE = enum(M3U8='TYPE_M3U8',
                          SEGMENT='TYPE_SEGMENT',
                          WAITTING='TYPE_WAITTING')

    def __init__(self):
        printDBG('M3U8Downloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)

        self.wgetStatus = self.WGET_STS.NONE
        # instance of E2 console
        self.console = eConsoleAppContainer()
        self.iptv_sys = None

        # M3U8 list updater
        self.M3U8Updater = eConsoleAppContainer()
        self.M3U8Updater_appClosed_conn = eConnectCallback(self.M3U8Updater.appClosed, self._updateM3U8Finished)
        self.M3U8Updater_stdoutAvail_conn = eConnectCallback(self.M3U8Updater.stdoutAvail, self._updateM3U8DataAvail)

        self.M3U8ListData = ''
        self.M3U8UpdaterRefreshDelay = 0
        self.refreshDelay = M3U8Downloader.MIN_REFRESH_DELAY

        # get only last fragments from first list, to satisfy specified duration in seconds
        # -1 means, starts from beginning
        self.startLiveDuration = M3U8Downloader.LIVE_START_OFFSET

        # 0 means, starts from beginning
        self.skipFirstSegFromList = 0

        self.addStampToUrl = False
        self.totalDuration = -1
        self.downloadDuration = 0
        self.fragmentDurationList = []

        self.maxTriesAtStart = 0

    def __del__(self):
        printDBG("M3U8Downloader.__del__ ----------------------------------")

    def getName(self):
        return "wget m3u8"

    def isWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system(DMHelper.GET_WGET_PATH() + " -V 2>&1 ", boundFunction(self._checkWorkingCallBack, callBackFun))

    def isLiveStream(self):
        return self.liveStream

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
        self.filePath = filePath
        self.downloaderParams = params
        self.fileExtension = '' # should be implemented in future

        self.status = DMHelper.STS.DOWNLOADING
        self.updateThread = None
        self.fragmentList = []
        self.lastMediaSequence = -1
        self.currentFragment = -1
        self.tries = 0
        self.liveStream = False
        self.skipFirstSegFromList = strwithmeta(url).meta.get('iptv_m3u8_skip_seg', 0)
        self.m3u8Url = url
        self._startM3U8()

        self.onStart()
        return BaseDownloader.CODE_OK

    def _getTimeout(self):
        if self.liveStream:
            return self.WGET_TIMEOUT
        else:
            return 2 * self.WGET_TIMEOUT

    def _addTimeStampToUrl(self, m3u8Url):
        if self.addStampToUrl:
            if '?' in m3u8Url:
                m3u8Url += '&iptv_stamp='
            else:
                m3u8Url += '?iptv_stamp='
            m3u8Url += ('%s' % time())
        return m3u8Url

    def _updateM3U8Finished(self, code=0):
        printDBG('m3u8 _updateM3U8Finished update code[%d]--- ' % (code))
        if self.liveStream and self.M3U8Updater:
            if 0 < len(self.M3U8ListData) and 0 == code:
                try:
                    m3u8Obj = m3u8.inits(self.M3U8ListData, self.m3u8Url)
                    if self.liveStream and not m3u8Obj.is_variant:
                        self.refreshDelay = int(m3u8Obj.target_duration)
                        if self.refreshDelay < 5:
                            self.refreshDelay = 5
                        if 0 < len(m3u8Obj.segments):
                            newFragments = [self._segUri(seg.absolute_uri) for seg in m3u8Obj.segments]
                            #self.mergeFragmentsList(newFragments)
                            self.mergeFragmentsListWithChecking(newFragments, m3u8Obj.media_sequence + len(m3u8Obj.segments))
                            printDBG('m3u8 _updateM3U8Finished list updated ---')
                except Exception:
                    printDBG("m3u8 _updateM3U8Finished exception url[%s] data[%s]" % (self.m3u8Url, self.M3U8ListData))
            else:
                printDBG('m3u8 _updateM3U8Finished no data ---')
            # hardcode
            self.M3U8UpdaterRefreshDelay += 1
            if self.refreshDelay < self.M3U8UpdaterRefreshDelay or 0 != code:
                self.M3U8UpdaterRefreshDelay = 0
                self.M3U8ListData = ''
                m3u8Url = self._addTimeStampToUrl(self.m3u8Url)
                printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> [%s]" % m3u8Url)
                cmd = DMHelper.getBaseWgetCmd(self.downloaderParams) + (' --tries=0 --timeout=%d ' % self._getTimeout()) + '"' + m3u8Url + '" -O - 2> /dev/null'
                printDBG("m3u8 _updateM3U8Finished download cmd[%s]" % cmd)
                self.M3U8Updater.execute(E2PrioFix(cmd))
                return
            else:
                self.M3U8Updater.execute(E2PrioFix("sleep 1"))
                return
        printDBG("|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")
        printDBG("||||||||||||| m3u8 _updateM3U8Finished FINISHED |||||||||||||")
        printDBG("|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")

    def _updateM3U8DataAvail(self, data):
        if None != data and 0 < len(data):
            self.M3U8ListData += data

    def mergeFragmentsListWithChecking_OLD(self, newFragments, media_sequence=-1):
        #newFragments = self.fixFragmentsList(newFragments)
        try:
            idx = newFragments.index(self.fragmentList[-1])
            newFragments = newFragments[idx + 1:]
        except Exception:
            printDBG('m3u8 update thread - last fragment from last list not available in new list!')

        tmpList = []
        for item in reversed(newFragments):
            if item in self.fragmentList:
                break
            tmpList.insert(0, item)

        if 0 < len(tmpList):
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> DODANO[%d]" % len(tmpList))
            if 21 < self.currentFragment:
                idx = self.currentFragment - 20
                self.fragmentList = self.fragmentList[idx:]
                self.currentFragment = 20
            self.fragmentList.extend(tmpList)

    def mergeFragmentsListWithChecking(self, newFragments, media_sequence=-1):
        tmpList = []
        #DebugToFile('last[%s] new[%s] = %s' % (self.lastMediaSequence, media_sequence, newFragments))
        if self.lastMediaSequence > 0 and media_sequence > 0:
            if media_sequence > self.lastMediaSequence:
                toAdd = media_sequence - self.lastMediaSequence
                if toAdd > len(newFragments):
                    toAdd = len(newFragments)
                tmpList = newFragments[-toAdd:]
                self.lastMediaSequence = media_sequence
        else:
            try:
                tmpCurrFragmentList = [seg[seg.rfind('/') + 1:] for seg in self.fragmentList]
                tmpNewFragments = [seg[seg.rfind('/') + 1:] for seg in newFragments]

                idx = tmpNewFragments.index(tmpCurrFragmentList[-1])
                newFragments = newFragments[idx + 1:]
            except Exception:
                printDBG('m3u8 update thread - last fragment from last list not available in new list!')

            for item in reversed(newFragments):
                if item in self.fragmentList:
                    break
                tmpList.insert(0, item)

        if 0 < len(tmpList):
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> DODANO[%d]" % len(tmpList))
            if 21 < self.currentFragment:
                idx = self.currentFragment - 20
                self.fragmentList = self.fragmentList[idx:]
                self.currentFragment = 20
            self.fragmentList.extend(tmpList)
            #DebugToFile(">> %s" % self.fragmentList)

    '''
    def fixFragmentsList(self, newFragments):
        retList = []
        for idx in range(len(newFragments)):
            if 0 == idx:
                retList.append(newFragments[0])
                continue
            if newFragments[idx] != newFragments[idx-1]:
                retList.append(newFragments[idx])
        return retList

    def mergeFragmentsList(self, newFragments):
        try:
            # merge fragments list
            idx = -1
            if 0 < len(self.fragmentList):
                try: idx = newFragments.index(self.fragmentList[-1])
                except Exception: printDBG('m3u8 update thread - last fragment from last list not available in new list!')

            if 0 <= idx:
                if (idx+1) < len(newFragments):
                    self.fragmentList.extend(newFragments[idx+1:])
            else:
                self.fragmentList.extend(newFragments)
        except Exception: pass
        #printDBG("===========================================================")
        #printDBG("%r" % self.fragmentList)
        #printDBG("===========================================================")
    '''

    def _startM3U8(self, wait=0):
        self.outData = ''
        ##############################################################################
        # frist download m3u8 conntent
        ##############################################################################
        self.downloadType = self.DOWNLOAD_TYPE.M3U8
        m3u8Url = self._addTimeStampToUrl(self.m3u8Url)
        cmd = DMHelper.getBaseWgetCmd(self.downloaderParams) + (' --tries=0 --timeout=%d ' % self._getTimeout()) + '"' + m3u8Url + '" -O - 2> /dev/null'
        if wait > 0:
            cmd = (' sleep %s && ' % wait) + cmd
        printDBG("Download cmd[%s]" % cmd)
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stdoutAvail_conn = eConnectCallback(self.console.stdoutAvail, self._dataAvail)
        self.console.execute(E2PrioFix(cmd))
        ##############################################################################

    def _startFragment(self, tryAgain=False):
        printDBG("_startFragment tryAgain[%r]" % tryAgain)
        self.outData = ''
        self.remoteFragmentSize = -1
        self.remoteFragmentType = 'unknown'

        if 0 > self.localFileSize:
            self.m3u8_prevLocalFileSize = 0
        else:
            self.m3u8_prevLocalFileSize = self.localFileSize
        ##############################################################################
        # frist download nextFragment conntent
        ##############################################################################
        self.downloadType = self.DOWNLOAD_TYPE.SEGMENT

        if None != self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
        #self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._dataAvail)

        if tryAgain and self.tries >= self.MAX_RETRIES:
            if not self.liveStream:
                return DMHelper.STS.INTERRUPTED
            else:
                # even if fragment is lost this is not big problem, download next one,
                # this is a live stream this can happen :)
                tryAgain = False

        currentFragment = None
        if False == tryAgain:
            self.tries = 0
            if (self.currentFragment + 1) < len(self.fragmentList):
                self.currentFragment += 1
                currentFragment = self.fragmentList[self.currentFragment]
        else:
            self.tries += 1
            currentFragment = self.fragmentList[self.currentFragment]

        if None != currentFragment:
            self.wgetStatus = self.WGET_STS.CONNECTING
            cmd = DMHelper.getBaseWgetCmd(self.downloaderParams) + (' --tries=1 --timeout=%d ' % self._getTimeout()) + '"' + currentFragment + '" -O - >> "' + self.filePath + '"'
            printDBG("Download cmd[%s]" % cmd)
            self.console.execute(E2PrioFix(cmd))

            #DebugToFile(currentFragment)
            return DMHelper.STS.DOWNLOADING
        else:
            if self.liveStream:
                # we are in live so wait for new fragments
                printDBG("m3u8 downloader - wait for new fragments ----------------------------------------------------------------")
                self.downloadType = self.DOWNLOAD_TYPE.WAITTING
                self.console.execute(E2PrioFix("sleep 2"))
                return DMHelper.STS.DOWNLOADING
            else:
                return DMHelper.STS.DOWNLOADED
        ##############################################################################

    def _dataAvail(self, data):
        if None != data:
            self.outData += data
            if self.DOWNLOAD_TYPE.M3U8 == self.downloadType:
                return

            if self.WGET_STS.CONNECTING == self.wgetStatus:
                self.outData += data
                lines = self.outData.replace('\r', '\n').split('\n')
                for idx in range(len(lines)):
                    if lines[idx].startswith('Length:'):
                        match = re.search("Length: ([0-9]+?) \([^)]+?\) (\[[^]]+?\])", lines[idx])
                        if match:
                            self.remoteFragmentSize = int(match.group(1))
                            self.remoteFragmentType = match.group(2)
                    elif lines[idx].startswith('Saving to:'):
                        self.console_stderrAvail_conn = None
                        self.wgetStatus = self.WGET_STS.DOWNLOADING
                        break

    def _terminate(self):
        printDBG("M3U8Downloader._terminate")
        if None != self.iptv_sys:
            self.iptv_sys.kill()
            self.iptv_sys = None
        if DMHelper.STS.DOWNLOADING == self.status:
            if self.console:
                self.console.sendCtrlC() # kill # produce zombies
                self._cmdFinished(-1, True)
                return BaseDownloader.CODE_OK

        return BaseDownloader.CODE_NOT_DOWNLOADING

    def _segUri(self, uri):
        return uri.split('iptv_stamp')[0]

    def _cmdFinished(self, code, terminated=False):
        printDBG("M3U8Downloader._cmdFinished code[%r] terminated[%r] downloadType[%s]" % (code, terminated, self.downloadType))

        localStatus = DMHelper.STS.ERROR
        if terminated:
            BaseDownloader.updateStatistic(self)
            localStatus = DMHelper.STS.INTERRUPTED
        elif self.DOWNLOAD_TYPE.M3U8 == self.downloadType:
            self.console_appClosed_conn = None
            self.console_stdoutAvail_conn = None
            if 0 < len(self.outData):
                try:
                    m3u8Obj = m3u8.inits(self.outData, self.m3u8Url)
                    # uri given to m3u8 downloader should not be variant,
                    # format should be selected before starting downloader
                    # however if this was not done the firs one will be selected
                    if m3u8Obj.is_variant:
                        if 0 < len(m3u8Obj.playlists):
                            self.m3u8Url = self._segUri(m3u8Obj.playlists[-1].absolute_uri)
                            self._startM3U8()
                            localStatus = DMHelper.STS.DOWNLOADING
                    else:
                        if 0 < len(m3u8Obj.segments):
                            if not m3u8Obj.is_endlist:
                                self.liveStream = True
                                if -1 == self.startLiveDuration:
                                    self.fragmentList = [self._segUri(seg.absolute_uri) for seg in m3u8Obj.segments]
                                else:
                                    # some live streams only add new fragments not removing old,
                                    # in this case most probably we not want to download old fragments
                                    # but start from last N fragments/seconds
                                    # self.startLiveDuration
                                    self.fragmentList = []
                                    currentDuration = 0
                                    maxFragDuration = m3u8Obj.target_duration
                                    for seg in reversed(m3u8Obj.segments):
                                        if None != seg.duration:
                                            currentDuration += seg.duration
                                        else:
                                            currentDuration += maxFragDuration
                                        self.fragmentList.append(self._segUri(seg.absolute_uri))
                                        if currentDuration >= self.startLiveDuration:
                                            break

                                    self.fragmentList.reverse()
                                    if len(m3u8Obj.segments) == len(self.fragmentList) and len(self.fragmentList) > self.skipFirstSegFromList:
                                        self.fragmentList = self.fragmentList[self.skipFirstSegFromList:]

                                self.lastMediaSequence = m3u8Obj.media_sequence + len(m3u8Obj.segments)
                                # start update fragment list loop
                                #self.fragmentList = self.fixFragmentsList(self.fragmentList)
                                self._updateM3U8Finished(-1)
                            else:
                                self.fragmentList = [self._segUri(seg.absolute_uri) for seg in m3u8Obj.segments]
                                try:
                                    self.totalDuration = 0
                                    self.fragmentDurationList = []
                                    for seg in m3u8Obj.segments:
                                        self.totalDuration += seg.duration
                                        self.fragmentDurationList.append(seg.duration)
                                except Exception:
                                    printExc()
                                    self.totalDuration = -1
                                    self.fragmentDurationList = []
                            localStatus = self._startFragment()
                except Exception:
                    pass
            printDBG(">>>>>>>>>>>>>>>>>> localStatus [%s] tries[%d]" % (localStatus, self.tries))
            if localStatus == DMHelper.STS.ERROR and self.tries < self.maxTriesAtStart:
                self.console_appClosed_conn = None
                self.console_stdoutAvail_conn = None
                self.tries += 1
                self._startM3U8(self.MIN_REFRESH_DELAY)
                return
            else:
                self.tries = 0

        elif self.liveStream and self.DOWNLOAD_TYPE.WAITTING == self.downloadType:
            printDBG("m3u8 liveStream waitting finished--------------------------------")
            localStatus = self._startFragment()
        else:
            BaseDownloader.updateStatistic(self)
            printDBG("m3u8 nextFragment finished: live[%r]: r[%d], l[%d], p[%d]" % (self.liveStream, self.remoteFragmentSize, self.localFileSize, self.m3u8_prevLocalFileSize))
            if 0 >= self.localFileSize:
                if not self.liveStream:
                    localStatus = DMHelper.STS.ERROR
                else:
                    localStatus = self._startFragment()
            #elif not self.liveStream and self.remoteFragmentSize > 0 and self.remoteFragmentSize > (self.localFileSize - self.m3u8_prevLocalFileSize):
            #    localStatus = DMHelper.STS.INTERRUPTED
            elif 0 < (self.localFileSize - self.m3u8_prevLocalFileSize):
                if self.totalDuration > 0:
                    try:
                        self.downloadDuration += self.fragmentDurationList[self.currentFragment]
                    except Exception:
                        printExc()
                localStatus = self._startFragment()
            elif 0 == (self.localFileSize - self.m3u8_prevLocalFileSize):
                localStatus = self._startFragment(True) # retry
            else:
                localStatus = DMHelper.STS.INTERRUPTED

        self.status = localStatus
        if DMHelper.STS.DOWNLOADING == self.status:
            return

        # clean up at finish
        if self.M3U8Updater:
            self.M3U8Updater_appClosed_conn = None
            self.M3U8Updater_stdoutAvail_conn = None
            self.M3U8Updater = None

        self.liveStream = False
        if self.console:
            self.console_appClosed_conn = None
            self.console_stdoutAvail_conn = None
            self.console.sendCtrlC() # kill # produce zombies
            self.console = None

        '''
        if None != self.updateThread:
            if self.updateThread.Thread.isAlive():
                # give some time for update thread to finish
                sleep(self.MIN_REFRESH_DELAY)
                printDBG('m3u8 downloader killing update thread')
        '''

        if not terminated:
            self.onFinish()

    def hasDurationInfo(self):
        return True

    def getTotalFileDuration(self):
        # total duration in seconds
        return int(self.totalDuration)

    def getDownloadedFileDuration(self):
        # downloaded duration in seconds
        return int(self.downloadDuration)
