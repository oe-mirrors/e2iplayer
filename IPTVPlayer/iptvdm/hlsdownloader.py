# -*- coding: utf-8 -*-
# IPTV download manager API
# Last Modified: 07.08.2026 - Extracted shared helpers (ensureText/fsPath/shellQuote/writeUtf8TextFile) and sidecar logic into downloaderhelpers.SidecarMixin, shared with wgetdownloader.py and mergedownloader.py, instead of duplicating them here - Kamikaze24
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, eConnectCallback, GetNice, rm, E2PrioFix
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import enum, strwithmeta
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import ensureText, fsPath, shellQuote, SidecarMixin
###################################################

###################################################
# FOREIGN import
###################################################
from Tools.BoundFunction import boundFunction
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
        self.iptv_sys = iptv_system(DMHelper.GET_FFMPEG_PATH() + ' -version ' + " 2>&1 ", boundFunction(self._checkWorkingCallBack, callBackFun))

    def _checkWorkingCallBack(self, callBackFun, code, data):
        reason = ''
        sts = True
        if code != 0:
            sts = False
            reason = data
            self.iptv_sys = None
            callBackFun(sts, reason)
        else:
            self._isHlsDlWorkingCorrectly(callBackFun)

    def _isHlsDlWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system(DMHelper.GET_HLSDL_PATH() + " 2>&1 ", boundFunction(self._checkHlsDlWorkingCallBack, callBackFun))

    def _checkHlsDlWorkingCallBack(self, callBackFun, code, data):
        reason = ''
        sts = True
        if code != 0:
            sts = False
            reason = data
        self.iptv_sys = None
        callBackFun(sts, reason)

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

    def _getMkvPath(self):
        return self._getBasePath(self.filePath) + '.mkv'

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

    def doStartPostProcess(self):
        self.postProcessMode = 'remux'
        self.tempRemuxPath = self._getBasePath(self.filePath) + '.iptv.remux.tmp.mkv'

        cmd = DMHelper.GET_FFMPEG_PATH() + ' '
        cmd += ' -i "%s" ' % shellQuote(self.filePath)
        cmd += ' -map 0:v -map 0:a? -vcodec copy -acodec copy "%s" >/dev/null 2>&1 ' % shellQuote(self.tempRemuxPath)

        printDBG("HLSDownloader doStartPostProcess cmd[%s]" % cmd)

        self.console = eConsoleAppContainer()
        self.console_appClosed_conn = eConnectCallback(self.console.appClosed, self._cmdFinished)
        if hasattr(self.console, "setNice"):
            self.console.setNice(GetNice() + 2)
            self.console.execute(cmd)
        else:
            self.console.execute(E2PrioFix(cmd))

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
        if hasattr(self.console, "setNice"):
            self.console.setNice(GetNice() + 2)
            self.console.execute(cmd)
        else:
            self.console.execute(E2PrioFix(cmd))

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
                        printDBG("HLSDownloader hlsdl error_code[%r] error_msg[%r]" % (obj.get("error_code"), obj.get("error_msg")))
                    if updateStatistic:
                        BaseDownloader._updateStatistic(self)
                except Exception:
                    printExc()
                continue

    def _terminate(self):
        printDBG("HLSDownloader._terminate")
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

        if terminated:
            self.status = DMHelper.STS.INTERRUPTED
        elif self.status == DMHelper.STS.POSTPROCESSING:
            mkvPath = self._getMkvPath()
            mkvSize = DMHelper.getFileSize(fsPath(self.tempRemuxPath))
            printDBG("POSTPROCESSING remux finished mkvPath[%s] localFileSize[%r] code[%r]" % (self.tempRemuxPath, mkvSize, code))

            if mkvSize > 0 and code == 0:
                if self._moveFile(self.tempRemuxPath, mkvPath):
                    self._removeSourceFile()
                    self._finalizeSuccess(mkvPath)
                    return

            printDBG("HLSDownloader remux failed -> fallback to original target")
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
        if code != 0 or self.lastErrorCode:
            return True
        # hlsdl exited 0 but the downloaded duration is far short of the playlist
        # duration -> it stopped early (rejected segment, throttled CDN, ...)
        if self.totalDuration > 0 and self.downloadDuration < self.totalDuration * 0.90:
            return True
        return False

    def isLiveStream(self):
        return self.liveStream

    def updateStatistic(self):
        # BaseDownloader.updateStatistic(self)
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
