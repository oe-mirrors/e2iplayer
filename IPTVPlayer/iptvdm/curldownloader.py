# -*- coding: utf-8 -*-
# IPTV download manager API
# Last Modified: 24.09.2026 - curl variant of WgetDownloader for plain HTTP(S)/FTP
# downloads. Opt-in (config "HTTP downloader" or the url meta iptv_downloader='curl'),
# only for real Download Manager downloads. The curl binary uses the same libcurl as
# pycurl, so the download goes out with the same TLS/HTTP2 client as the page requests.
# Everything that is not tied to the wget binary (progress from the file size, retry,
# ffmpeg postprocess, sidecar files) is inherited from WgetDownloader.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, iptv_system, GetTmpDir, rm
from Plugins.Extensions.IPTVPlayer.iptvdm.basedownloader import BaseDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.wgetdownloader import WgetDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import ensureText, fsPath, shellQuote
###################################################

###################################################
# FOREIGN import
###################################################
from Tools.BoundFunction import boundFunction
import re
import os
###################################################


class CurlDownloader(WgetDownloader):
    # https://curl.se/libcurl/c/libcurl-errors.html
    @staticmethod
    def _curlErrorText(code):
        texts = {
            0: _("No problems occurred."),
            1: _("Unsupported protocol."),
            2: _("Failed to initialize (unknown option or old curl version?)."),
            3: _("URL malformed."),
            5: _("Could not resolve proxy."),
            6: _("Could not resolve host."),
            7: _("Failed to connect to host."),
            16: _("HTTP/2 framing layer error."),
            18: _("Partial file - transfer ended early."),
            22: _("Server issued an error response (HTTP 4xx/5xx)."),
            23: _("File I/O error (write)."),
            26: _("Read error."),
            27: _("Out of memory."),
            28: _("Operation timed out."),
            33: _("Range request not supported (resume failed)."),
            35: _("SSL connect error."),
            47: _("Too many redirects."),
            52: _("Server returned nothing."),
            55: _("Network failure (send)."),
            56: _("Network failure (receive)."),
            60: _("SSL verification failure."),
            92: _("HTTP/2 stream error."),
        }
        return texts.get(code, _("Unknown error code."))

    def __init__(self):
        printDBG('CurlDownloader.__init__ ')
        WgetDownloader.__init__(self)
        # curl dumps the response headers here (-D) - source of the remote size / mime type
        self.headersPath = GetTmpDir('.e2i_curl_%x.hdr' % id(self))
        self.headersParsed = False

    def __del__(self):
        printDBG("CurlDownloader.__del__ ")

    def getName(self):
        return "curl"

    def _setLastError(self, code):
        self.lastErrorCode = code
        self.lastErrorDesc = self._curlErrorText(code)

    def isWorkingCorrectly(self, callBackFun):
        self.iptv_sys = iptv_system(DMHelper.GET_CURL_PATH() + " --version 2>&1 ", boundFunction(self._checkWorkingCallBack, callBackFun))

    def _removeHeadersFile(self):
        try:
            if os.path.isfile(self.headersPath):
                rm(self.headersPath)
        except Exception:
            printExc()

    def _parseHeadersFile(self):
        # -D holds one header block per response (redirects included) - only the last one counts
        if self.headersParsed or not os.path.isfile(self.headersPath):
            return
        try:
            with open(self.headersPath, 'rb') as f:
                data = ensureText(f.read())
        except Exception:
            printExc()
            return
        data = data.replace('\r', '')
        if data and not data.startswith('HTTP/'):
            # FTP: -D holds server replies, no HTTP headers - nothing to read, don't retry every tick
            self.headersParsed = True
            return
        blocks = re.split(r'(?m)^(?=HTTP/)', data)
        last = blocks[-1] if blocks else ''
        if not last.startswith('HTTP/') or '\n\n' not in last:
            return  # headers of the final response not complete yet
        self.headersParsed = True
        if not re.match(r'HTTP/\S+\s+2\d\d', last):
            # -f error response: its Content-Length is the error page, not the file
            return
        headers = {}
        for line in last.split('\n')[1:]:
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()
        size = -1
        # a resumed download (206) gives only the remaining bytes in Content-Length
        match = re.search(r'/(\d+)\s*$', headers.get('content-range', ''))
        if match:
            size = int(match.group(1))
        elif headers.get('content-length', '').isdigit():
            size = int(headers['content-length'])
        if size > 0:
            self.remoteFileSize = size
        contentType = headers.get('content-type', '')
        if contentType:
            self.remoteContentType = contentType.split(';', 1)[0].strip()
        printDBG("CurlDownloader headers remoteFileSize[%r] remoteContentType[%r]" % (self.remoteFileSize, self.remoteContentType))

    def start(self, url, filePath, params={}, info_from=None, retries=0):
        # the wget command line is built in WgetDownloader.start(), swap it for the curl one
        self._removeHeadersFile()
        self.headersParsed = False
        return WgetDownloader.start(self, url, filePath, params, WgetDownloader.INFO.FROM_FILE, retries)

    def _buildDownloadCmd(self, info, retries):
        return DMHelper.getBaseCurlCmd(self.downloaderParams, retries) + ' -D "%s" -o "%s" "%s" > /dev/null' % (shellQuote(self.headersPath), shellQuote(self.filePath), shellQuote(self.url))

    def _dataAvail(self, data):
        # curl runs with -sS: stderr carries only the error message, keep it for the debug log
        if data is None:
            return
        text = ensureText(data).strip()
        if text:
            printDBG("CurlDownloader stderr: %s" % text)

    def updateStatistic(self):
        if not self.headersParsed:
            self._parseHeadersFile()
        self.localFileSize = DMHelper.getFileSize(fsPath(self.filePath))
        BaseDownloader._updateStatistic(self)

    def _terminate(self):
        ret = WgetDownloader._terminate(self)
        self._removeHeadersFile()
        return ret

    def _cmdFinished(self, code, terminated=False):
        printDBG("CurlDownloader._cmdFinished code[%r] terminated[%r]" % (code, terminated))
        if self.status == DMHelper.STS.DOWNLOADING:
            self._parseHeadersFile()
            self._removeHeadersFile()
            # a retry run (-C -) writes a fresh header dump
            self.headersParsed = False

            # WgetDownloader treats "size unknown + file not empty" as finished. curl
            # reports a cut chunked transfer only through its exit code, so a failed
            # run with an unknown size must not end up as DOWNLOADED.
            if not terminated and code != 0 and self.remoteFileSize <= 0:
                BaseDownloader.updateStatistic(self)
                self._setLastError(code)
                self.console_appClosed_conn = None
                self.console_stderrAvail_conn = None
                self.console = None
                self.wgetStatus = self.WGET_STS.ENDED
                self.status = DMHelper.STS.ERROR if self.localFileSize <= 0 else DMHelper.STS.INTERRUPTED
                printDBG("CurlDownloader._cmdFinished curl error [%s] status [%s]" % (self.lastErrorDesc, self.status))
                self._finishDownloadFlow()
                return
        WgetDownloader._cmdFinished(self, code, terminated)
