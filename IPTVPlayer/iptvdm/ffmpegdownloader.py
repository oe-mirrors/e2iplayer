# -*- coding: utf-8 -*-
#
#  IPTV download manager API
#
#  $Id$
#
#  Last Modified: 31.08.2026
#   - _getDownloadSpeed()/_getDuration()/_getStartTime() null-guard their regex
#     matches (ffmpeg emits "N/A" progress fields that used to raise -> printExc
#     spam on nearly every line).
#   - _checkWorkingCallBack() always clears self.iptv_sys.
#   - _terminate() resolves the download even when self.console is already gone.
#   - _cmdFinished() honours ffmpeg's exit code and uses a completeness tolerance
#     (>=97% of the known duration) so segment rounding no longer marks a finished
#     download INTERRUPTED.
#   - updateStatistic() cross-checks the real on-disk file size so size/percent
#     never stalls at 0 when ffmpeg's own "size=" line is missing/lagging.
#   - HTTP inputs get -reconnect_streamed / -reconnect_delay_max / -rw_timeout so a
#     dropped or stalled connection recovers or fails instead of hanging.
#   - merge:// inputs are stream-mapped explicitly (audio_url -> :a, video_url ->
#     :v) so a stray track in one playlist can't shadow the intended stream.
#   - _fixFileExtension(): rename the output to the container ffmpeg actually
#     wrote (-f matroska -> .mkv etc.) instead of leaving it under the .mp4 name
#     the DM requested; the DM re-reads the path via getFullFileName().
#   Applies to every FFMPEGDownloader user (DASH, iptv_use_ffmpeg, kinoger, all
#   merge:// hosts), not only Arte.
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, eConnectCallback, rm, WriteTextFile, GetNice, getDebugMode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import strDecode
###################################################
# FOREIGN import
###################################################
from Tools.BoundFunction import boundFunction
from enigma import eConsoleAppContainer
import re
import datetime
###################################################

###################################################
# One instance of this class can be used only for
# one download
###################################################


class FFMPEGDownloader(BaseDownloader):

    # a download counts as complete once this fraction of the known duration is
    # reached - ffmpeg's segment-summed duration and its final time= often differ
    # by a segment, so an exact match must not be required
    DURATION_COMPLETE_RATIO = 0.97

    # extra input options for HTTP(S) sources: recover from dropped connections
    # and give up on a stalled socket instead of hanging forever (rw_timeout is in
    # microseconds)
    HTTP_INPUT_OPTS = ('-reconnect', '1', '-reconnect_streamed', '1',
                       '-reconnect_delay_max', '30', '-rw_timeout', '60000000')

    # -f <container> -> the extension the finished file should actually carry
    CONTAINER_EXT = {'matroska': '.mkv', 'webm': '.webm', 'mpegts': '.ts',
                     'mp4': '.mp4', 'mov': '.mp4', 'flv': '.flv'}
    KNOWN_EXT = ('.mp4', '.mkv', '.ts', '.webm', '.mov', '.flv', '.avi', '.m4v')

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
        self.parseReObj['start_time'] = re.compile(r'\sstart\:\s*?([0-9]+?)\.')
        self.parseReObj['duration'] = re.compile(r'[\s=]([0-9]+?)\:([0-9]+?)\:([0-9]+?)\.')
        self.parseReObj['size'] = re.compile(r'size=\s*?([0-9]+?)([kK][iI]?[bB])', re.IGNORECASE)
        self.parseReObj['bitrate'] = re.compile(r'bitrate=\s*?([0-9]+?(?:\.[0-9]+?)?)kbits')
        self.parseReObj['speed'] = re.compile(r'speed=\s*?([0-9]+?(?:\.[0-9]+?)?)x')

        self.ffmpegOutputContener = 'matroska'
        self.fileCmdPath = ''
        # the DM download path sets this so the finished file may be renamed to
        # its real container extension; stays False for buffered playback, where
        # the player already holds the file open under the requested name
        self.allowFinalRename = False

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
                reason = _('Utility "%s" can not be found.') % ffmpegBinaryName
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
        self.fileExtension = ''  # should be implemented in future
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

        def _addHttpOpts(cmdTab, meta):
            headers = []
            try:
                for key in meta:
                    if key == 'Range':
                        continue
                    elif key == 'User-Agent':
                        cmdTab.extend(['-user_agent', meta[key]])
                    elif key == 'Referer':
                        cmdTab.extend(['-referer', meta[key]])
                    elif key == 'Origin':
                        headers.append('%s: %s' % (key, meta[key]))
                    elif key in ['Cookie', 'Authorization']:
                        headers.append('%s: %s' % (key, meta[key]))
            except Exception:
                printExc()

            if len(headers):
                cmdTab.extend(['-headers', '\r\n'.join(headers) + '\r\n'])

        mapOpts = []
        if self.url.startswith("merge://"):
            try:
                urlsKeys = self.url.split('merge://', 1)[1].split('|')
                for idx, item in enumerate(urlsKeys):
                    oneUrl = tmpUri.meta[item]
                    oneMeta = dict(tmpUri.meta)
                    _addHttpOpts(cmdTab, oneMeta)
                    if str(oneUrl).lower().startswith(('http://', 'https://')):
                        cmdTab.extend(self.HTTP_INPUT_OPTS)
                    cmdTab.extend(['-i', oneUrl])
                    if 'audio' in item:
                        mapOpts += ['-map', '%d:a' % idx]
                    elif 'video' in item:
                        mapOpts += ['-map', '%d:v' % idx]
                    else:
                        mapOpts += ['-map', str(idx)]
            except Exception:
                printExc()
                mapOpts = []
        else:
            if "://" in self.url:
                url, httpParams = DMHelper.getDownloaderParamFromUrlWithMeta(tmpUri, True)
                _addHttpOpts(cmdTab, httpParams)
                if self.url.lower().startswith(('http://', 'https://')):
                    cmdTab.extend(self.HTTP_INPUT_OPTS)
            else:
                url = self.url
            cmdTab.extend(['-i', url])

        cmdTab.extend(mapOpts)
        cmdTab.extend(['-c:v', 'copy', '-c:a', 'copy', '-f', self._outContainer(), self.filePath])

        self.fileCmdPath = self.filePath + '.iptv.cmd'
        rm(self.fileCmdPath)
        WriteTextFile(self.fileCmdPath, '|'.join(cmdTab))

        cmd = '/usr/bin/cmdwrap' + (' "%s" "|" %s ' % (self.fileCmdPath, GetNice() + 2))

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
            if obj:
                return 3600 * int(obj.group(1)) + 60 * int(obj.group(2)) + int(obj.group(3))
        except Exception:
            printExc()
        return 0

    def _getStartTime(self, data):
        try:
            obj = self.parseReObj['start_time'].search(data)
            if obj:
                return int(obj.group(1))
        except Exception:
            printExc()
        return 0

    def _getFileSize(self, data):
        try:
            match = self.parseReObj['size'].search(data)
            if match:
                return int(match.group(1)) * 1024
        except Exception:
            printExc()
        return 0

    def _getDownloadSpeed(self, data):
        try:
            bitrateObj = self.parseReObj['bitrate'].search(data)
            speedObj = self.parseReObj['speed'].search(data)
            if bitrateObj is None or speedObj is None:
                return 0
            return int(float(bitrateObj.group(1)) * float(speedObj.group(1)) * 1024 / 8)
        except Exception:
            printExc()
        return 0

    def _dataAvail(self, data):
        if None is data:
            return

        data = self.outData + strDecode(data).replace('\n', '\r')

        # ffmpeg separates progress updates with a bare CR; the text after the last
        # CR is always the still-incomplete chunk - hold it for the next call
        data = data.split('\r')
        self.outData = data.pop()

        for item in data:
            # printDBG("---")
            # printDBG(item)
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

                # downloaded duration is a plain progress counter - keep it
                # advancing from every progress line, not only when the parsed
                # size grows (updateStatistic() now also bumps localFileSize from
                # disk, which would otherwise freeze this)
                duration = self._getDuration(item)
                if duration > self.downloadDuration:
                    self.downloadDuration = duration

    def _terminate(self):
        printDBG("FFMPEGDownloader._terminate")
        if None is not self.iptv_sys:
            self.iptv_sys.kill()
            self.iptv_sys = None
        if DMHelper.STS.DOWNLOADING == self.status:
            if self.console:
                # self.console.sendCtrlC()
                self.console.sendCtrlC()  # kill # produce zombies
            self._cmdFinished(-1, True)
            return BaseDownloader.CODE_OK
        return BaseDownloader.CODE_NOT_DOWNLOADING

    def _cmdFinished(self, code, terminated=False):
        printDBG("FFMPEGDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))

        if '' == getDebugMode():
            rm(self.fileCmdPath)

        # break circular references
        if None is not self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
            self.console = None

        self._refreshLocalFileSize()

        if terminated:
            self.status = DMHelper.STS.INTERRUPTED
        elif 0 >= self.localFileSize:
            self.status = DMHelper.STS.ERROR
        elif not self._looksComplete():
            # short file: a clean ffmpeg exit here is odd, a non-zero one is a real
            # failure - either way it is not a finished download
            self.status = DMHelper.STS.INTERRUPTED if code in (0, None) else DMHelper.STS.ERROR
        else:
            # whole timeline present -> keep it even if ffmpeg exited non-zero on a
            # trailing segment glitch (common with -c copy of HLS)
            self.status = DMHelper.STS.DOWNLOADED

        if not terminated:
            # ffmpeg has stopped writing -> name the file after its real container,
            # even for a partial (an incomplete .mkv is still an .mkv)
            self._fixFileExtension()
            self.onFinish()

    def _outContainer(self):
        # the container passed to ffmpeg's -f; it also drives the final file
        # extension (_fixFileExtension), so both must read it the same way
        return str(strwithmeta(self.url).meta.get('ff_out_container', self.ffmpegOutputContener)).lower()

    def _looksComplete(self):
        # unknown duration (livestream / no header) -> nothing to compare against
        if self.totalDuration <= 0:
            return True
        return self.downloadDuration >= self.totalDuration * self.DURATION_COMPLETE_RATIO

    def _fixFileExtension(self):
        # ffmpeg writes the container chosen by -f, which need not match the name
        # the DM requested (host asks for .mp4, we mux Matroska). Rename the
        # output to the real extension so players that trust the suffix (gstplayer,
        # DLNA, file managers) don't choke. The DM re-reads the path via
        # getFullFileName() after the download.
        try:
            if not self.allowFinalRename:
                return
            if DMHelper.getFileSize(self.filePath) <= 0:
                return
            wantExt = self.CONTAINER_EXT.get(self._outContainer())
            if not wantExt:
                return
            low = str(self.filePath).lower()
            curExt = ''
            for ext in self.KNOWN_EXT:
                if low.endswith(ext):
                    curExt = ext
                    break
            if curExt == wantExt:
                return
            base = self.filePath[:-len(curExt)] if curExt else self.filePath
            newPath = DMHelper.makeUnikalFileName(base + wantExt, False, False)
            bRet, msg = self.moveFullFileName(newPath)
            if bRet:
                self.fileExtension = wantExt
                printDBG("FFMPEGDownloader renamed output to match container -> %s" % self.filePath)
            else:
                printDBG("FFMPEGDownloader could not rename output: %s" % msg)
        except Exception:
            printExc()

    def _refreshLocalFileSize(self):
        # ffmpeg's own "size=" progress line can be missing or lag behind; the file
        # on disk is the ground truth (getFileSize returns -1 on a missing file)
        diskSize = DMHelper.getFileSize(self.filePath)
        if diskSize > self.localFileSize:
            self.localFileSize = diskSize

    def isLiveStream(self):
        return self.liveStream

    def updateStatistic(self):
        self._refreshLocalFileSize()
        if self.lastUpadateTime is not None:
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
