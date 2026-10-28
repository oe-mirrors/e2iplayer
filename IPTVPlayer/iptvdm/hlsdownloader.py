# -*- coding: utf-8 -*-
# IPTV download manager API
# Last Modified: 18.10.2026 - hlsdl 0.37 "fmp4-alt-audio" (fMP4 video + separate audio it cannot mux): FFMPEGDownloader takes the download over, its state is passed on. Earlier: 12.10.2026 - stopping a live recording is its normal end: renamed to what hlsdl wrote (.ts), its .txt written (was kept as .mp4 over MPEG-TS); no remux / cover / subtitles there, terminate() reports the finish at once. Earlier: 11.10.2026 - file format setting (hls_out_container): Automatic renames the file to the container hlsdl wrote (.ts/.mp4/.aac), MKV/MP4/TS remux when needed. Earlier: 10.10.2026 - isWorkingCorrectly() checks only hlsdl (cached usage text, no ffmpeg/process start), remux maps 0:v? (audio-only streams). Earlier: 07.08.2026 - Extracted shared helpers (ensureText/fsPath/shellQuote/writeUtf8TextFile) and sidecar logic into downloaderhelpers.SidecarMixin, shared with wgetdownloader.py and mergedownloader.py, instead of duplicating them here - Kamikaze24
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import enum, strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import ensureText, fsPath, shellQuote, executeConsoleCmd, terminateToolsOfFile, SidecarMixin
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config
from enigma import eConsoleAppContainer
from time import sleep
import re
import datetime
import os
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


class HLSDownloader(BaseDownloader, SidecarMixin):

    # remux container (setting / host meta) -> (ffmpeg -f, file extension)
    REMUX_FORMATS = {'mkv': ('matroska', '.mkv'), 'matroska': ('matroska', '.mkv'), 'mp4': ('mp4', '.mp4'),
                     'mpegts': ('mpegts', '.ts'), 'ts': ('mpegts', '.ts')}
    # container hlsdl wrote (_detectContainer) -> file extension
    CONTAINER_EXT = {'mpegts': '.ts', 'mp4': '.mp4', 'adts': '.aac'}

    def __init__(self):
        printDBG('HLSDownloader.__init__ ----------------------------------')
        BaseDownloader.__init__(self)

        # instance of E2 console
        self.console = None
        self.console_appClosed_conn = None
        self.console_stderrAvail_conn = None

        # sidecar support (console instance + state), shared via SidecarMixin
        self._initSidecarState()

        self.iptv_sys = None
        self.totalDuration = 0
        self.downloadDuration = 0
        self.liveStream = False
        self.lastErrorCode = 0  # last non-zero "error_code" reported by hlsdl (e.g. expired/blocked CDN token)
        self.lastErrorMsg = ''  # its "error_msg"
        # FFMPEGDownloader that took the download over when hlsdl could not produce the file (fMP4 video with
        # a separate audio rendition it cannot mux, "fmp4-alt-audio"); the state is read from it from then on
        self.fallback = None

        # both are set by the download manager (allowFinalRename: a real download, not buffered
        # playback; resumeExisting: "Continue downloading" on an interrupted item)
        self.allowFinalRename = False
        self.resumeExisting = False

        # ffmpeg postprocess support
        self.ffmpegPostEnabled = False
        self.ffmpegContainer = 'mkv'
        self.postProcessMode = ''
        self.tempRemuxPath = ''
        self.finalizedPath = ''

    def __del__(self):
        printDBG("HLSDownloader.__del__ ----------------------------------")

    def _safeRm(self, path):
        try:
            fpath = fsPath(path)
            if fpath and os.path.exists(fpath):
                rm(fpath)
        except Exception:
            printExc()

    def _cleanUp(self):
        if self.tempRemuxPath:
            self._safeRm(self.tempRemuxPath)
            self._safeRm(self._getRemuxLogPath())

    def _removeSourceFile(self):
        try:
            if self.filePath and os.path.isfile(fsPath(self.filePath)):
                rm(fsPath(self.filePath))
                printDBG("HLSDownloader source file removed [%s]" % self.filePath)
            return True
        except Exception:
            printExc()
            return False

    def getName(self):
        return "hlsdl m3u8"

    def isWorkingCorrectly(self, callBackFun):
        # only hlsdl is needed (ffmpeg is just the optional remux after a download, which falls back to the
        # original file): its usage text is read once per run, so a buffered playback starts without two
        # process spawns
        helpText = DMHelper.hlsdlHelpText()
        if 'hlsdl' in helpText.lower() or 'usage' in helpText.lower():
            callBackFun(True, '')
        else:
            callBackFun(False, helpText or (DMHelper.GET_HLSDL_PATH() + ': ' + 'not found'))

    def _clearPostData(self):
        self.ffmpegPostEnabled = False
        self.ffmpegContainer = 'mkv'
        self.postProcessMode = ''
        self.tempRemuxPath = ''
        self.finalizedPath = ''

    def _preparePostData(self, meta):
        self._clearPostData()
        try:
            if meta.get('e2i_postprocess_ffmpeg', False) or str(meta.get('e2i_postprocess_ffmpeg', '')) == '1':
                self.ffmpegPostEnabled = True
                self.ffmpegContainer = ensureText(meta.get('e2i_postprocess_container', 'mkv')).strip().lower()
                if not self.ffmpegContainer:
                    self.ffmpegContainer = 'mkv'
                printDBG("HLSDownloader ffmpeg postprocess enabled container[%s]" % self.ffmpegContainer)
        except Exception:
            printExc()

    def _getBasePath(self, filePath):
        return ensureText(filePath).rsplit('.', 1)[0]

    def _getRemuxFormat(self):
        return self.REMUX_FORMATS.get(self.ffmpegContainer, self.REMUX_FORMATS['mkv'])

    def _getTargetPath(self, ext):
        # the file with the new extension; a number added when another file has that name already
        path = self._getBasePath(self.filePath) + ext
        if fsPath(path) != fsPath(self.filePath) and os.path.exists(fsPath(path)):
            path = DMHelper.makeUnikalFileName(path, False, False)
        return ensureText(path)

    def _detectContainer(self):
        # what hlsdl wrote, from the first bytes: MPEG-TS (sync byte every 188 bytes), MP4 (fMP4 segments),
        # ADTS AAC (packed audio); '' when unknown (e.g. audio behind an ID3 tag)
        try:
            with open(fsPath(self.filePath), 'rb') as f:
                head = f.read(1024)
        except Exception:
            printExc()
            return ''
        if len(head) > 376 and head[0:1] == b'\x47' and head[188:189] == b'\x47' and head[376:377] == b'\x47':
            return 'mpegts'
        if head[4:8] in (b'ftyp', b'styp', b'moof', b'moov'):
            return 'mp4'
        if head[:2] in (b'\xff\xf1', b'\xff\xf9'):
            return 'adts'
        return ''

    def _applyFormatSetting(self):
        # setting "File format of HLS (M3U8) downloads": hlsdl writes the segments as they come under the
        # name the download manager asked for (mostly .mp4, also for MPEG-TS). Automatic only gives the file the
        # extension of what it holds; MKV / MP4 / TS remux it with ffmpeg when it holds something else
        try:
            choice = str(config.plugins.iptvplayer.hls_out_container.value).lower()
        except Exception:
            printExc()
            choice = 'auto'
        found = self._detectContainer()
        printDBG("HLSDownloader file format setting[%s] found[%s]" % (choice, found))
        if choice != 'auto' and self.REMUX_FORMATS.get(choice, ('',))[0] != found:
            self.ffmpegPostEnabled = True
            self.ffmpegContainer = choice
            return
        self._renameToContainer(found)

    def _renameToContainer(self, found):
        # the file named after the container hlsdl wrote (_detectContainer)
        ext = self.CONTAINER_EXT.get(found)
        if ext and not self.filePath.lower().endswith(ext):
            target = self._getTargetPath(ext)
            if self._moveFile(self.filePath, target):
                printDBG("HLSDownloader renamed output to match container -> %s" % target)
                self.filePath = target

    def _keepTsForIrregularFrames(self):
        # a remux of MPEG-TS whose video frames are not evenly spaced (24 fps film on a 30 fps raster: 3,3,3,6
        # frame times of 1/30 s, the H.264 header says 30 fps - seen on VOE) gives a black picture on the box as
        # MKV, the TS itself plays: such a file stays TS. Read from the PES time stamps of the first 4 MB
        if self._getRemuxFormat()[0] == 'mpegts' or self._detectContainer() != 'mpegts':
            return False
        try:
            with open(fsPath(self.filePath), 'rb') as f:
                data = bytearray(f.read(4 * 1024 * 1024))
            pmtPid = videoPid = None
            stamps = []
            for pos in range(0, len(data) - 187, 188):
                if data[pos] != 0x47:
                    break
                if not data[pos + 1] & 0x40 or not data[pos + 3] & 0x10:
                    # only packets that start a section / PES and carry a payload
                    continue
                pid = ((data[pos + 1] & 0x1f) << 8) | data[pos + 2]
                off = pos + 4
                if data[pos + 3] & 0x20:
                    off += 1 + data[off]
                if pid == 0 and pmtPid is None:
                    off += 1 + data[off]  # pointer field
                    end = min(off + 3 + (((data[off + 1] & 0x0f) << 8) | data[off + 2]) - 4, pos + 188)
                    for p in range(off + 8, end - 3, 4):
                        if (data[p] << 8) | data[p + 1]:
                            pmtPid = ((data[p + 2] & 0x1f) << 8) | data[p + 3]
                            break
                elif pid == pmtPid and videoPid is None:
                    off += 1 + data[off]
                    end = min(off + 3 + (((data[off + 1] & 0x0f) << 8) | data[off + 2]) - 4, pos + 188)
                    p = off + 12 + (((data[off + 10] & 0x0f) << 8) | data[off + 11])
                    while p + 5 <= end:
                        # MPEG-2 / H.264 / HEVC video
                        if data[p] in (0x02, 0x1b, 0x24):
                            videoPid = ((data[p + 1] & 0x1f) << 8) | data[p + 2]
                            break
                        p += 5 + (((data[p + 3] & 0x0f) << 8) | data[p + 4])
                elif pid == videoPid and data[off:off + 3] == b'\x00\x00\x01' and data[off + 7] & 0x80:
                    # DTS when there is one (B-frames), else PTS
                    t = off + (14 if data[off + 7] & 0x40 else 9)
                    stamps.append(((data[t] & 0x0e) << 29) | (data[t + 1] << 22) | ((data[t + 2] & 0xfe) << 14) | (data[t + 3] << 7) | (data[t + 4] >> 1))
                    if len(stamps) > 300:
                        break
        except Exception:
            printExc()
            return False
        # a jump between two segments or the 33 bit wrap is no frame time
        steps = [b - a for a, b in zip(stamps, stamps[1:]) if 0 < b - a < 90000]
        if len(steps) < 50:
            return False
        common = max(set(steps), key=steps.count)
        # 23.976 / 59.94 fps alternate by one tick (3753 / 3754)
        odd = len([s for s in steps if abs(s - common) > 2])
        printDBG("HLSDownloader video frame times: %d of %d differ from %d" % (odd, len(steps), common))
        return odd * 10 > len(steps)

    def _moveFile(self, src, dst):
        try:
            srcPath = fsPath(src)
            dstPath = fsPath(dst)
            if srcPath == dstPath:
                return True
            if os.path.isfile(dstPath):
                rm(dstPath)
            os.rename(srcPath, dstPath)
            return os.path.isfile(dstPath)
        except Exception:
            printExc()
            return False

    def _getRemuxLogPath(self):
        return self._getBasePath(self.tempRemuxPath).rsplit('.iptv.remux.tmp', 1)[0] + '.iptv.remux.log'

    def _remuxLogText(self):
        # the end of ffmpeg's output of the remux; the file is removed, it would stay next to the video otherwise
        text = ''
        path = fsPath(self._getRemuxLogPath())
        try:
            if os.path.isfile(path):
                with open(path, 'rb') as f:
                    text = ensureText(f.read())[-1500:].strip()
        except Exception:
            printExc()
        self._safeRm(path)
        return text

    def doStartPostProcess(self):
        self.postProcessMode = 'remux'
        fmt, ext = self._getRemuxFormat()
        self.tempRemuxPath = self._getBasePath(self.filePath) + '.iptv.remux.tmp' + ext

        # -y: a leftover temp file from an aborted run must not make ffmpeg wait for an overwrite answer
        cmd = DMHelper.GET_FFMPEG_PATH() + ' -y -nostdin -hide_banner -loglevel warning '
        cmd += ' -i "%s" ' % shellQuote(self.filePath)
        # 0:v? too: an audio-only stream (radio) has no video, "-map 0:v" would abort the remux
        cmd += ' -map 0:v? -map 0:a? -vcodec copy -acodec copy '
        if fmt == 'mp4':
            # index at the start of the finished file, so players can seek in it right away
            cmd += ' -movflags +faststart '
        # ffmpeg's warnings / errors go to the debug log when the remux fails (_remuxLogText)
        cmd += ' -f %s "%s" >"%s" 2>&1 ' % (fmt, shellQuote(self.tempRemuxPath), shellQuote(self._getRemuxLogPath()))

        printDBG("HLSDownloader doStartPostProcess cmd[%s]" % cmd)

        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        executeConsoleCmd(self.console, cmd)

    def _finalizeSuccess(self, finalPath):
        self.filePath = ensureText(finalPath)
        self.finalizedPath = ensureText(finalPath)
        self.localFileSize = DMHelper.getFileSize(fsPath(finalPath))
        if self.localFileSize > 0:
            self.remoteFileSize = self.localFileSize
            self.status = DMHelper.STS.DOWNLOADED

            self._writeTxtSidecar(finalPath)

            if self.sidecarEnabled and self.sidecarImg:
                self._startImgSidecarDownload(finalPath)
                return
        else:
            # remuxed/finalized file is empty -> treat as interrupted, and
            # don't write a TXT/image sidecar for a video that isn't there
            self.status = DMHelper.STS.INTERRUPTED

        self._finishDownloadFlow()

    def _finalizeMp4Fallback(self):
        self.localFileSize = DMHelper.getFileSize(fsPath(self.filePath))
        if self.localFileSize > 0:
            self.remoteFileSize = self.localFileSize
        self.status = DMHelper.STS.DOWNLOADED

        self._writeTxtSidecar(self.filePath)

        if self.sidecarEnabled and self.sidecarImg:
            self._startImgSidecarDownload(self.filePath)
            return True

        self._finishDownloadFlow()
        return True

    def _getResumeParams(self):
        # Download manager downloads only. -R makes hlsdl keep a resume sidecar while it runs;
        # without it an interrupted run would have nothing to continue from.
        if not DMHelper.hlsdlSupportsResume():
            self.resumeExisting = False
            return ''
        if self.resumeExisting and DMHelper.hasHlsdlResumeFile(self.filePath) and os.path.isfile(fsPath(self.filePath)):
            printDBG("HLSDownloader resume existing file[%s]" % self.filePath)
        else:
            # a fresh start, also "Download again": a sidecar left by an earlier run must not
            # turn it into a resume
            self.resumeExisting = False
            DMHelper.removeHlsdlResumeFiles(self.filePath)
        return ' -R '

    def _getLiveStartParams(self):
        # Buffered playback: start a live stream this many seconds behind the live edge (hlsdl -s).
        # "default" leaves hlsdl's own value (2 minutes); it has no effect on a VOD. Download
        # manager recordings keep the default, the earlier part is wanted there.
        try:
            offset = str(config.plugins.iptvplayer.hlsdlLiveStartOffset.value)
            if offset.isdigit():
                return ' -s %s ' % offset
        except Exception:
            printExc()
        return ''

    def start(self, url, filePath, params={}):
        """
        Owervrite start from BaseDownloader
        """
        self.url = url
        self.filePath = ensureText(filePath)
        self.downloaderParams = params
        self.fileExtension = ''  # should be implemented in future
        self.outData = ''
        self.contentType = 'unknown'
        self.postProcessMode = ''
        self.tempRemuxPath = ''
        self.finalizedPath = ''

        # baseWgetCmd = DMHelper.getBaseWgetCmd(self.downloaderParams)
        # TODO: add all HTTP parameters
        addParams = ''
        meta = strwithmeta(url).meta

        # prepare sidecar meta data
        self._prepareSidecarData(meta)

        # prepare ffmpeg postprocess meta data
        self._preparePostData(meta)

        if 'iptv_m3u8_key_uri_replace_old' in meta and 'iptv_m3u8_key_uri_replace_new' in meta:
            addParams = ' -k "%s" -n "%s" ' % (shellQuote(meta['iptv_m3u8_key_uri_replace_old']), shellQuote(meta['iptv_m3u8_key_uri_replace_new']))

        if 'iptv_m3u8_seg_download_retry' in meta:
            addParams += ' -w %s ' % shellQuote(meta['iptv_m3u8_seg_download_retry'])

        if self.allowFinalRename:
            addParams += self._getResumeParams()
        else:
            addParams += self._getLiveStartParams()

        if self.url.startswith("merge://"):
            try:
                urlsKeys = self.url.split('merge://', 1)[1].split('|')
                url = meta[urlsKeys[-1]]
                addParams += ' -a "%s" ' % shellQuote(meta[urlsKeys[0]])
            except Exception:
                printExc()
        else:
            url = self.url

        cmd = DMHelper.getBaseHLSDLCmd(self.downloaderParams) + (' "%s"' % shellQuote(url)) + addParams + (' -o "%s"' % shellQuote(self.filePath)) + ' > /dev/null'

        printDBG("HLSDownloader::start cmd[%s]" % cmd)

        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        self.console_stderrAvail_conn = eConnectCallback(self.console.stderrAvail, self._dataAvail)
        executeConsoleCmd(self.console, cmd)

        self.status = DMHelper.STS.DOWNLOADING

        self.onStart()
        return BaseDownloader.CODE_OK

    def _dataAvail(self, data):
        if None is data:
            return
        data = self.outData + ensureText(data)
        if not data:
            self.outData = ''
            return
        if '\n' != data[-1]:
            truncated = True
        else:
            truncated = False
        data = data.split('\n')
        if truncated:
            self.outData = data[-1]
            del data[-1]
        else:
            self.outData = ''
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
                    if obj.get("error_code"):
                        self.lastErrorCode = obj["error_code"]
                        self.lastErrorMsg = ensureText(obj.get("error_msg") or '')
                        printDBG("HLSDownloader hlsdl error_code[%r] error_msg[%r]" % (obj.get("error_code"), obj.get("error_msg")))
                    if updateStatistic:
                        BaseDownloader._updateStatistic(self)
                except Exception:
                    printExc()
                continue

    def _startFfmpegFallback(self):
        # hlsdl 0.37+ reports "fmp4-alt-audio" (before writing any media) for fMP4 video with a separate audio
        # rendition it cannot mux into one file; ffmpeg can - it takes the download over under the same name
        try:
            from Plugins.Extensions.IPTVPlayer.iptvdm.ffmpegdownloader import FFMPEGDownloader
            fallback = FFMPEGDownloader()
            fallback.allowFinalRename = self.allowFinalRename
            fallback.subscribeFor_Finish(self._fallbackFinished)
            if fallback.start(self.url, self.filePath, self.downloaderParams) != BaseDownloader.CODE_OK:
                return False
            printDBG("HLSDownloader hlsdl cannot mux this fMP4 stream -> FFMPEGDownloader takes over")
            self.fallback = fallback
            return True
        except Exception:
            printExc()
            return False

    def _fallbackFinished(self, status):
        fallback = self.fallback
        if fallback is None:
            return
        self.status = status
        self.filePath = ensureText(fallback.getFullFileName())
        self.localFileSize = fallback.getLocalFileSize()
        self.remoteFileSize = fallback.getRemoteFileSize()
        self.onFinish()

    def _terminate(self):
        printDBG("HLSDownloader._terminate")
        if self.fallback is not None:
            # BaseDownloader.terminate() reports the finish once - not again through _fallbackFinished
            self.fallback.unsubscribeFor_Finish(self._fallbackFinished)
            sts = self.fallback._terminate()
            self.status = self.fallback.getStatus()
            return sts
        if None is not self.iptv_sys:
            self.iptv_sys.kill()
            self.iptv_sys = None

        self._terminateSidecar()

        if DMHelper.STS.DOWNLOADING == self.status or DMHelper.STS.POSTPROCESSING == self.status:
            if self.console:
                if hasattr(self.console, "sendCtrlC"):
                    self.console.sendCtrlC()  # kill # produce zombies
                elif hasattr(self.console, "kill"):
                    self.console.kill()  # kill produce zombies
            # the signal above only reaches the shell around hlsdl / ffmpeg
            terminateToolsOfFile(self.filePath)
            self._cmdFinished(-1, True)
            return BaseDownloader.CODE_OK
        return BaseDownloader.CODE_NOT_DOWNLOADING

    def _cmdFinished(self, code, terminated=False):
        printDBG("HLSDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))

        # break circular references
        if None is not self.console:
            self.console_appClosed_conn = None
            self.console_stderrAvail_conn = None
            self.console = None

        if not terminated and self.fallback is None and self.status == DMHelper.STS.DOWNLOADING \
                and self.lastErrorMsg == 'fmp4-alt-audio' and 0 >= self.downloadDuration:
            # nothing but at most the init segment is written yet - ffmpeg starts the file over
            if self._startFfmpegFallback():
                return

        if terminated and self.liveStream and self.allowFinalRename and self.status != DMHelper.STS.POSTPROCESSING \
                and DMHelper.getFileSize(fsPath(self.filePath)) > 0:
            # stopping is how a live recording ends (the download manager already counts it as finished). terminate()
            # reports the finish itself (onFinish), so only what runs at once: the file named after what hlsdl wrote
            # (.ts) and the .txt - no remux, cover or subtitles, they would finish after that report
            printDBG("HLSDownloader live recording stopped -> kept as finished file")
            self.status = DMHelper.STS.DOWNLOADED
            self._renameToContainer(self._detectContainer())
            if self.sidecarEnabled:
                self._writeTxtSidecar(self.filePath)
            return

        if terminated:
            self.status = DMHelper.STS.INTERRUPTED
            # an aborted remux leaves its half written temp file behind otherwise
            self._cleanUp()
        elif self.status == DMHelper.STS.POSTPROCESSING:
            targetPath = self._getTargetPath(self._getRemuxFormat()[1])
            remuxSize = DMHelper.getFileSize(fsPath(self.tempRemuxPath))
            printDBG("POSTPROCESSING remux finished tempPath[%s] localFileSize[%r] code[%r]" % (self.tempRemuxPath, remuxSize, code))
            remuxLog = self._remuxLogText()

            if remuxSize > 0 and code == 0:
                # the remuxed file may keep the name of the downloaded one (TS remuxed to a file asked for as .mp4)
                sameName = fsPath(targetPath) == fsPath(self.filePath)
                if self._moveFile(self.tempRemuxPath, targetPath):
                    if not sameName:
                        self._removeSourceFile()
                    self._finalizeSuccess(targetPath)
                    return

            printDBG("HLSDownloader remux failed -> fallback to original target, ffmpeg:\n%s" % remuxLog)
            if self._finalizeMp4Fallback():
                return
            self.status = DMHelper.STS.INTERRUPTED
        elif 0 >= self.localFileSize:
            self.status = DMHelper.STS.ERROR
        elif self._isIncompleteDownload(code):
            # hlsdl can exit 0 even after aborting mid-stream on an HTTP error
            # (expired / IP-locked CDN token); don't remux/finalize a truncated file
            printDBG("HLSDownloader incomplete (code[%r] errCode[%r] dur[%s/%s]) -> INTERRUPTED" % (code, self.lastErrorCode, self.downloadDuration, self.totalDuration))
            self.status = DMHelper.STS.INTERRUPTED
        elif self.remoteFileSize > 0 and self.remoteFileSize > self.localFileSize:
            self.status = DMHelper.STS.INTERRUPTED
        else:
            if not self.ffmpegPostEnabled and self.allowFinalRename:
                # a download in the download manager (a host's own remux container above wins)
                self._applyFormatSetting()
            if self.ffmpegPostEnabled and self.allowFinalRename and self._keepTsForIrregularFrames():
                printDBG("HLSDownloader irregular video frame times -> kept as TS, no remux")
                self.ffmpegPostEnabled = False
                self._renameToContainer('mpegts')
            if self.ffmpegPostEnabled:
                self.status = DMHelper.STS.POSTPROCESSING
                self.doStartPostProcess()
                return

            self.status = DMHelper.STS.DOWNLOADED
            self._writeTxtSidecar(self.filePath)

            if self.sidecarEnabled and self.sidecarImg:
                self._startImgSidecarDownload(self.filePath)
                return

        if not terminated:
            self._finishDownloadFlow()

    def _isIncompleteDownload(self, code):
        if self.liveStream:
            return False
        if self.lastErrorCode:
            return True
        if code != 0:
            # some hlsdl builds exit 1 after the last segment of a complete download
            if self._reportedComplete():
                printDBG("HLSDownloader hlsdl exit code[%r] after the whole duration -> counted as complete" % code)
                return False
            return True
        # hlsdl exited 0 but the downloaded duration is far short of the playlist
        # duration -> it stopped early (rejected segment, throttled CDN, ...)
        if self.totalDuration > 0 and self.downloadDuration < self.totalDuration * 0.90:
            return True
        return False

    def _reportedComplete(self):
        # hlsdl reported the whole playlist duration and the file holds every byte it reported
        # (a full disk fails only the final write, the file is shorter then)
        if self.totalDuration <= 0 or self.downloadDuration < self.totalDuration or self.localFileSize <= 0:
            return False
        return DMHelper.getFileSize(fsPath(self.filePath)) >= self.localFileSize

    # after a fallback (_startFfmpegFallback) the FFMPEGDownloader holds the state - the buffering screen and the
    # download manager keep talking to this object
    def getStatus(self):
        if self.fallback is not None:
            return self.fallback.getStatus()
        return self.status

    def isDownloading(self):
        return DMHelper.STS.DOWNLOADING == self.getStatus()

    def getLocalFileSize(self, update=False):
        if self.fallback is not None:
            return self.fallback.getLocalFileSize(update)
        return BaseDownloader.getLocalFileSize(self, update)

    def getPlayableFileSize(self):
        if self.fallback is not None:
            return self.fallback.getPlayableFileSize()
        return BaseDownloader.getPlayableFileSize(self)

    def getRemoteFileSize(self):
        if self.fallback is not None:
            return self.fallback.getRemoteFileSize()
        return self.remoteFileSize

    def getDownloadSpeed(self):
        if self.fallback is not None:
            return self.fallback.getDownloadSpeed()
        return self.downloadSpeed

    def getFullFileName(self):
        if self.fallback is not None:
            return self.fallback.getFullFileName()
        return self.filePath

    def moveFullFileName(self, newPath):
        if self.fallback is not None:
            return self.fallback.moveFullFileName(newPath)
        return BaseDownloader.moveFullFileName(self, newPath)

    def getLastError(self):
        if self.fallback is not None:
            return self.fallback.getLastError()
        return BaseDownloader.getLastError(self)

    def getMimeType(self):
        if self.fallback is not None:
            return self.fallback.getMimeType()
        return BaseDownloader.getMimeType(self)

    def isLiveStream(self):
        if self.fallback is not None:
            return self.fallback.isLiveStream()
        return self.liveStream

    def updateStatistic(self):
        # hlsdl reports its statistics itself (_dataAvail)
        if self.fallback is not None:
            self.fallback.updateStatistic()

    def hasDurationInfo(self):
        if self.fallback is not None:
            return self.fallback.hasDurationInfo()
        return True

    def getTotalFileDuration(self):
        # total duration in seconds
        if self.fallback is not None:
            return self.fallback.getTotalFileDuration()
        if self.isLiveStream():
            return self.downloadDuration
        return self.totalDuration

    def getDownloadedFileDuration(self):
        # downloaded duration in seconds
        if self.fallback is not None:
            return self.fallback.getDownloadedFileDuration()
        return self.downloadDuration
