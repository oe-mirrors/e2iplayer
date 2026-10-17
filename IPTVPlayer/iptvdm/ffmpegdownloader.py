# -*- coding: utf-8 -*-
#
#  IPTV download manager API
#
#  $Id$
#
#  Last Modified: 17.10.2026
#   - a DM download whose link names iptv_master_url takes that master playlist (program of the variant), the
#     variant again when the master gives nothing (masterFallback, without a second sidecar / live check);
#     ffmpeg's "[hls @ ...] Skip ('#EXT-X-...')" lines are left out of the log
#  12.10.2026
#   - a stopped live recording in MP4 / MOV keeps its name (ffmpeg still reopens the file by name for the index);
#     the live check also sends Authorization and cannot stop a download from starting
#   - stopping a live recording is its normal end: DOWNLOADED, renamed to its container and its .txt written (no
#     cover / subtitles: terminate() reports the finish at once) - live = the link says so, or its playlist (DASH
#     type "dynamic", HLS without #EXT-X-ENDLIST, read in a work thread at the start), else no duration from
#     ffmpeg; a single file (by its extension) is never live
#     (was INTERRUPTED and kept the requested .mp4 name over MPEG-TS); speed from the growing file when
#     ffmpeg's progress line has no bitrate (bitrate=N/A, live MPEG-TS: the list showed no B/s)
#  Earlier: 10.10.2026
#   - _dataAvail(): ffmpeg's lines before the stream mapping and its error lines go to the debug log
#     (each distinct error line once, capped, per-packet warnings left out).
#  Earlier: 31.08.2026
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
#     :v) so a stray track in one playlist can't shadow the intended stream; a DM
#     download whose link names iptv_master_url takes that master playlist instead.
#   - _fixFileExtension(): rename the output to the container ffmpeg actually
#     wrote (-f matroska -> .mkv etc.) instead of leaving it under the .mp4 name
#     the DM requested; the DM re-reads the path via getFullFileName().
#   Applies to every FFMPEGDownloader user (DASH, iptv_use_ffmpeg, kinoger, all
#   merge:// hosts), not only Arte.
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, eConnectCallback, rm, WriteTextFile, GetNice, KeepDebugArtifact
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import SidecarMixin, shellQuote
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import strDecode
###################################################
# FOREIGN import
###################################################
from Tools.BoundFunction import boundFunction
from Components.config import config
from enigma import eConsoleAppContainer
import re
import datetime
###################################################


def manifestIsLive(url, getPage=None):
    # whether an HLS / DASH source is live, from its own playlist: a DASH manifest of type "dynamic", an HLS media
    # playlist without #EXT-X-ENDLIST (a master playlist: its first variant); None when it cannot be read.
    # getPage: pCommon's (the tests hand in their own)
    if getPage is None:
        from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
        getPage = common().getPage
    from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
    meta = getattr(url, 'meta', None) or {}
    header = dict((key, meta[key]) for key in ('User-Agent', 'Referer', 'Origin', 'Cookie', 'Authorization') if meta.get(key))
    url = str(url)
    for _step in range(2):
        try:
            sts, data = getPage(url, {'header': header, 'return_data': True, 'timeout': 15})
        except Exception:
            printExc()
            return None
        data = strDecode(data) if sts and data else ''
        if '<MPD' in data[:4096]:
            return re.search(r'<MPD\b[^>]*\btype\s*=\s*["\']dynamic', data) is not None
        if '#EXTM3U' not in data[:1024]:
            return None
        if '#EXT-X-STREAM-INF' not in data:
            return '#EXT-X-ENDLIST' not in data and '#EXT-X-PLAYLIST-TYPE:VOD' not in data
        variants = [line.strip() for line in data.splitlines() if line.strip() and not line.strip().startswith('#')]
        if not variants:
            return None
        url = urljoin(url, variants[0])
    return None


###################################################
# One instance of this class can be used only for
# one download
###################################################


class FFMPEGDownloader(BaseDownloader, SidecarMixin):

    # a download counts as complete once this fraction of the known duration is
    # reached - ffmpeg's segment-summed duration and its final time= often differ
    # by a segment, so an exact match must not be required
    DURATION_COMPLETE_RATIO = 0.97

    # ffmpeg output lines written to the debug log after the stream mapping (before it every line is logged);
    # ERROR_SPAM lines repeat per packet or per retry and are never logged, each distinct error line is logged
    # once and at most MAX_ERROR_LINES per download
    ERROR_LINE = re.compile(r'(?i)\b(?:error|failed|invalid|forbidden|denied|not found|server returned|unauthorized|timed out|refused|unable to|reset by peer)\b')
    ERROR_SPAM = re.compile(r'(?i)invalid dts|non-monotonous|will reconnect at|\[hls @ [^\]]+\] skip \(')
    MAX_ERROR_LINES = 20

    # extra input options for HTTP(S) sources: recover from dropped connections
    # and give up on a stalled socket instead of hanging forever (rw_timeout is in
    # microseconds)
    HTTP_INPUT_OPTS = ('-reconnect', '1', '-reconnect_streamed', '1',
                       '-reconnect_delay_max', '30', '-rw_timeout', '60000000')

    # -f <container> -> the extension the finished file should actually carry
    CONTAINER_EXT = {'matroska': '.mkv', 'webm': '.webm', 'mpegts': '.ts',
                     'mp4': '.mp4', 'mov': '.mp4', 'flv': '.flv'}
    KNOWN_EXT = ('.mp4', '.mkv', '.ts', '.webm', '.mov', '.flv', '.avi', '.m4v')
    # file extension of a source -> its container (the "auto" output format)
    SOURCE_CONTAINER = (('.mp4', 'mp4'), ('.m4v', 'mp4'), ('.mov', 'mp4'), ('.webm', 'webm'),
                        ('.flv', 'flv'), ('.ts', 'mpegts'), ('.mkv', 'matroska'))

    def __init__(self):
        printDBG('FFMPEGDownloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)

        # instance of E2 console
        self.console = None
        self.iptv_sys = None
        self._initSidecarState()
        self.totalDuration = 0
        self.downloadDuration = 0
        self.liveStream = False
        self.headerReceived = False
        self.loggedErrors = set()
        self.speedFromProgress = False  # ffmpeg's progress line gave a speed (bitrate x speed)
        self.sizeSample = None  # (time, file size) of the last statistic update, for the speed without it
        self.liveState = {}  # {'live': True / False / None} from the source's own playlist (_startLiveCheck)
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
        # the merge:// link to run again when a master playlist gave nothing (start())
        self.masterFallback = None
        self.fallbackRun = False  # start() of the variant after a master that gave nothing

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
        self.speedFromProgress = False
        self.sizeSample = None

        cmdTab = [DMHelper.GET_FFMPEG_PATH(), '-y']
        tmpUri = strwithmeta(url)
        fallbackRun, self.fallbackRun = getattr(self, 'fallbackRun', False), False
        if not fallbackRun:
            # (the variant after a master that gave nothing keeps the sidecar lookup and live check already running)
            self._prepareSidecarData(tmpUri.meta)
            try:
                self._startLiveCheck(tmpUri.meta)  # optional: the download must not depend on it
            except Exception:
                printExc()
                self.liveState = {}

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
        self.masterFallback = None
        masterUrl = '%s' % tmpUri.meta.get('iptv_master_url', '')
        if self.allowFinalRename and masterUrl.lower().startswith(('http://', 'https://')):
            # DM download of a merge:// HLS variant: some ffmpeg builds (5.1.x) stop after a second on the separate
            # video/audio media playlists of a low-latency stream, the master runs. iptv_master_program = the
            # variant's program in the master (its streams optional: "?"; without it ffmpeg picks the best one);
            # iptv_master_<header> = the headers the master needs. The master link can be used once only: when it
            # gives nothing (a restart in the download manager), the download runs again with the variant
            fallbackMeta = dict(tmpUri.meta)
            fallbackMeta.pop('iptv_master_url', None)
            self.masterFallback = strwithmeta('%s' % tmpUri, fallbackMeta)
            masterMeta = dict(tmpUri.meta)
            for headerName in ('User-Agent', 'Referer', 'Origin', 'Cookie'):
                headerValue = masterMeta.get('iptv_master_' + headerName.lower().replace('-', '_'))
                if headerValue:
                    masterMeta[headerName] = headerValue
            program = '%s' % tmpUri.meta.get('iptv_master_program', '')
            if program.isdigit():
                mapOpts = ['-map', '0:p:%s:v:0?' % program, '-map', '0:p:%s:a:0?' % program]
            printDBG("FFMPEGDownloader::start master playlist instead of the variant, program[%s]%s" % (program, '' if mapOpts else ' (ffmpeg picks the streams)'))
            tmpUri = strwithmeta(masterUrl, masterMeta)
            self.url = tmpUri
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
        outContainer = self._outContainer()
        cmdTab.extend(['-c:v', 'copy', '-c:a', 'copy'])
        if outContainer in ('mp4', 'mov'):
            # index at the start of the finished file, so players can seek in it right away
            cmdTab.extend(['-movflags', '+faststart'])
        cmdTab.extend(['-f', outContainer, self.filePath])

        self.fileCmdPath = self.filePath + '.iptv.cmd'
        rm(self.fileCmdPath)
        WriteTextFile(self.fileCmdPath, '|'.join(cmdTab))

        cmd = '/usr/bin/cmdwrap' + (' "%s" "|" %s ' % (shellQuote(self.fileCmdPath), GetNice() + 2))

        printDBG("FFMPEGDownloader::start cmd[%s]" % cmd)

        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._dataAvail)
        self.console.execute(cmd)

        self.status = DMHelper.STS.DOWNLOADING

        if not fallbackRun:
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
            return int(float(bitrateObj.group(1)) * float(speedObj.group(1)) * 1000 / 8)
        except Exception:
            printExc()
        return 0

    def _logOutputLine(self, item):
        if self.ERROR_SPAM.search(item):
            return
        if self.ERROR_LINE.search(item):
            # error lines often start with a long signed URL - keep head and tail so the reason at the end survives
            if item in self.loggedErrors or len(self.loggedErrors) >= self.MAX_ERROR_LINES:
                return
            self.loggedErrors.add(item)
            if len(item) > 400:
                item = item[:150] + ' ... ' + item[-150:]
        elif self.headerReceived:
            return
        else:
            item = item[:300]
        printDBG('FFMPEGDownloader ffmpeg: %s' % item)

    def _dataAvail(self, data):
        if None is data:
            return

        data = self.outData + strDecode(data).replace('\n', '\r')

        # ffmpeg separates progress updates with a bare CR; the text after the last
        # CR is always the still-incomplete chunk - hold it for the next call
        data = data.split('\r')
        self.outData = data.pop()

        for item in data:
            # what ffmpeg says before the stream mapping and every error line go to the log (the progress lines stay
            # silent) - without them a failed download left no reason behind
            if item.strip() and 'frame=' not in item and not item.lstrip().startswith('size='):
                self._logOutputLine(item)
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

                # ffmpeg's speed when this line has one, else the growing file's (updateStatistic)
                speed = self._getDownloadSpeed(item)
                self.speedFromProgress = bool(speed)
                if speed:
                    self.downloadSpeed = speed

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
        self._terminateSidecar()
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

        if not KeepDebugArtifact('debug_keep_ffmpeg_cmd'):
            rm(self.fileCmdPath)

        # break circular references
        if None is not self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
            self.console = None

        self._refreshLocalFileSize()

        fallback = getattr(self, 'masterFallback', None)
        if not terminated and fallback is not None and 0 >= self.localFileSize:
            # the master link gave nothing (used up already, e.g. a restart in the download manager): the variant
            printDBG("FFMPEGDownloader master playlist gave nothing -> again with the variant")
            self.fallbackRun = True
            self.start(fallback, self.filePath, self.downloaderParams)
            return

        # a live recording has no end of its own: stopping it in the download manager is how it ends
        liveStop = terminated and self.allowFinalRename and 0 < self.localFileSize and self._isLiveRecording()
        if liveStop:
            printDBG("FFMPEGDownloader live recording stopped -> kept as finished file")
            self.status = DMHelper.STS.DOWNLOADED
        elif terminated:
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

        if liveStop:
            # stopped in the download manager: terminate() reports the finish itself (onFinish), so only what runs
            # at once - the real file name and the .txt; no cover or subtitles, they would finish after that report.
            # MP4 / MOV keep their name: ffmpeg, stopped just now, still reopens the file by name for the index
            # (+faststart)
            if self._outContainer() not in ('mp4', 'mov'):
                self._fixFileExtension()
            if self.sidecarEnabled:
                self._writeTxtSidecar(self.filePath)
            return

        if not terminated:
            # ffmpeg has stopped writing -> name the file after its real container,
            # even for a partial (an incomplete .mkv is still an .mkv)
            self._fixFileExtension()
            # sidecar (.txt/.jpg) only for a real, complete DM download -
            # allowFinalRename is unset for buffered playback, which must not
            # wait on an image download before the player can proceed
            if self.allowFinalRename and self.sidecarEnabled and DMHelper.STS.DOWNLOADED == self.status:
                self._writeTxtSidecar(self.filePath)
                if self.sidecarImg:
                    self._startImgSidecarDownload(self.filePath)
                    return
                self._finishDownloadFlow()
                return
            # onFinish(), after the subtitles of a download (_cleanUp() has nothing to do here)
            self._finishDownloadFlow()

    def _cleanUp(self):
        # required by SidecarMixin._finishDownloadFlow(); the .iptv.cmd temp
        # file is already removed at the top of _cmdFinished, nothing else
        # to do here
        pass

    def _outContainer(self):
        # the container passed to ffmpeg's -f; it also drives the final file
        # extension (_fixFileExtension), so both must read it the same way.
        # A host's ff_out_container wins; a download in the download manager
        # uses the setting of its source (DASH, HLS or a single file; "auto" =
        # the container of the source); buffered playback, whose file the
        # player holds under its name, Matroska
        meta = strwithmeta(self.url).meta
        if 'ff_out_container' in meta:
            return str(meta['ff_out_container']).lower()
        if not self.allowFinalRename:
            return self.ffmpegOutputContener
        if self._isDashSource(meta):
            try:
                return str(config.plugins.iptvplayer.dash_out_container.value).lower()
            except Exception:
                printExc()
            return self.ffmpegOutputContener
        try:
            setting = config.plugins.iptvplayer.hls_out_container if self._isHlsSource(meta) else config.plugins.iptvplayer.file_out_container
            choice = str(setting.value).lower()
        except Exception:
            printExc()
            choice = 'auto'
        return self._sourceContainer(meta) if choice == 'auto' else choice

    def _sourceContainer(self, meta):
        # "auto": the container the site delivers - one MP4/WebM/FLV file stays
        # one, HLS (MPEG-TS segments) becomes .ts, also as a live recording. A
        # merge:// of separate audio/video parts, a live recording of a single
        # file (an MP4 stopped without its index does not play) and anything
        # unknown stay Matroska
        url = str(self.url)
        if url.startswith('merge://'):
            return self.ffmpegOutputContener
        if str(meta.get('iptv_proto', '')).lower() == 'm3u8' or '.m3u8' in url.lower():
            return 'mpegts'
        if meta.get('iptv_livestream'):
            return self.ffmpegOutputContener
        path = url.split('?', 1)[0].split('#', 1)[0].rstrip('/').lower()
        for ext, container in self.SOURCE_CONTAINER:
            if path.endswith(ext):
                return container
        return self.ffmpegOutputContener

    def _isHlsSource(self, meta):
        # M3U8 by proto or URL, also a merge:// whose audio/video parts are M3U8s
        if str(meta.get('iptv_proto', '')).lower() == 'm3u8' or '.m3u8' in str(self.url).lower():
            return True
        if str(self.url).startswith('merge://'):
            for key in str(self.url).split('merge://', 1)[1].split('|'):
                if '.m3u8' in str(meta.get(key, '')).lower():
                    return True
        return False

    def _isDashSource(self, meta):
        # MPD by proto or URL, also a merge:// whose audio/video parts are MPDs
        if str(meta.get('iptv_proto', '')).lower() in ('mpd', 'dash'):
            return True
        url = str(self.url).lower()
        if url.startswith('mpd://') or '.mpd' in url:
            return True
        if url.startswith('merge://'):
            for key in str(self.url).split('merge://', 1)[1].split('|'):
                if '.mpd' in str(meta.get(key, '')).lower():
                    return True
        return False

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

    def _startLiveCheck(self, meta):
        # a real download only: is the source live? Read from its playlist in a work thread while ffmpeg runs (an
        # E2iPlayer work thread - pCommon's requests need its kill state). A single file (by its extension) is no
        # live stream; anything else not known as HLS / DASH stays unknown (ffmpeg's missing duration decides)
        self.liveState = {}
        if not self.allowFinalRename or meta.get('iptv_livestream'):
            return
        if not (self._isHlsSource(meta) or self._isDashSource(meta)):
            path = str(self.url).split('?', 1)[0].split('#', 1)[0].lower()
            if path.endswith(('.mp4', '.mkv', '.webm', '.mov', '.m4v', '.avi', '.flv', '.wmv', '.mp3', '.m4a', '.aac')):
                self.liveState = {'live': False}
            return
        url = self.url
        if str(url).startswith('merge://'):
            keys = str(url).split('merge://', 1)[1].split('|')
            parts = [meta.get(key) for key in sorted(keys, key=lambda key: key != 'video_url') if meta.get(key)]
            if not parts:
                return
            url = parts[0]
            if not getattr(url, 'meta', None):
                # a plain part url: the headers of the whole link
                url = strwithmeta(url, dict((key, meta[key]) for key in ('User-Agent', 'Referer', 'Origin', 'Cookie', 'Authorization') if meta.get(key)))
        state = self.liveState = {'live': None}

        def liveCheck():
            state['live'] = manifestIsLive(url)
            printDBG("FFMPEGDownloader live check [%s]: %r" % (str(url)[:120], state['live']))

        from Plugins.Extensions.IPTVPlayer.components.asynccall import AsyncMethod
        AsyncMethod(liveCheck)()

    def _isLiveRecording(self):
        # stopping ends a live recording: the link says live, or the source's playlist does (DASH "dynamic", HLS
        # without end mark); without that answer (not read yet / unreadable) ffmpeg's missing duration decides
        if strwithmeta(self.url).meta.get('iptv_livestream'):
            return True
        live = self.liveState.get('live')
        if live is not None:
            return live
        return self.isLiveStream()

    def isLiveStream(self):
        return self.liveStream

    def updateStatistic(self):
        self._refreshLocalFileSize()
        now = datetime.datetime.now()
        if not self.speedFromProgress and self.sizeSample is not None:
            # no bitrate in ffmpeg's progress line (bitrate=N/A): the speed from the growing file
            secs = (now - self.sizeSample[0]).total_seconds()
            if secs > 0 and self.localFileSize >= self.sizeSample[1]:
                self.downloadSpeed = int((self.localFileSize - self.sizeSample[1]) / secs)
        self.sizeSample = (now, self.localFileSize)
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
