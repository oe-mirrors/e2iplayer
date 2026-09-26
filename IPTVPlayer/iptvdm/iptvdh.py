# -*- coding: utf-8 -*-
#
#  IPTV download helper
#
#  $Id$
#
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, IsExecutable
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import enum
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Tools.Directories import fileExists
import datetime
import os
import re
###################################################


class DMItemBase:
    def __init__(self, url, fileName):
        self.url = url

        self.fileName = fileName
        self.tmpFileName = ""

        self.fileSize = -1
        self.downloadedSize = 0
        self.downloadedProcent = -1
        self.downloadedSpeed = 0
        self.totalFileDuration = -1
        self.downloadedFileDuration = -1

        self.status = DMHelper.STS.WAITING
        self.tries = DMHelper.DOWNLOAD_TYPE.INITIAL

        # instance of downloader
        self.downloader = None
        self.callback = None
        # downloader.getName() at the moment it was created - kept
        # separately from self.downloader (which is cleared once the
        # download finishes) so the UI can still show which downloader was
        # used for an already-finished/aborted item
        self.downloaderName = ""

    def __del__(self):
        printDBG("DMItemBase.__del__  ---------------------")


class DMHelper:
    STATUS_FILE_PATH = '/tmp/iptvdownload'
    STATUS_FILE_EXT = '.txt'

    STS = enum(WAITING='STS_WAITING',
                DOWNLOADING='STS_DOWNLOADING',
                DOWNLOADED='STS_DOWNLOADED',
                INTERRUPTED='STS_INTERRUPTED',
                ERROR='STS_ERROR',
                POSTPROCESSING='STS_POSTPROCESSING')
    DOWNLOAD_TYPE = enum(INITIAL='INIT_DOWNLOAD',
                          CONTINUE='CONTINUE_DOWNLOAD',
                          RETRY='RETRY_DOWNLOAD')
    #
    DOWNLOADER_TYPE = enum(WGET='WGET_DOWNLOADER',
                            F4F='F4F_DOWNLOADER')

    HEADER_PARAMS = [{'marker': 'Host=', 'name': 'Host'},
                     {'marker': 'Accept=', 'name': 'Accept'},
                     {'marker': 'Cookie=', 'name': 'Cookie'},
                     {'marker': 'Referer=', 'name': 'Referer'},
                     {'marker': 'User-Agent=', 'name': 'User-Agent'},
                     {'marker': 'Range=', 'name': 'Range'},
                     {'marker': 'Orgin=', 'name': 'Orgin'},
                     {'marker': 'Origin=', 'name': 'Origin'},
                     {'marker': 'X-Playback-Session-Id=', 'name': 'X-Playback-Session-Id'},
                     {'marker': 'If-Modified-Since=', 'name': 'If-Modified-Since'},
                     {'marker': 'If-None-Match=', 'name': 'If-None-Match'},
                     {'marker': 'X-Forwarded-For=', 'name': 'X-Forwarded-For'},
                     {'marker': 'Authorization=', 'name': 'Authorization'},
                     ]

    HANDLED_HTTP_HEADER_PARAMS = ['Host', 'Accept', 'Cookie', 'Referer', 'User-Agent', 'Range', 'Orgin', 'Origin', 'X-Playback-Session-Id', 'If-Modified-Since', 'If-None-Match', 'X-Forwarded-For', 'Authorization', 'Accept-Language']
    IPTV_DOWNLOADER_PARAMS = ['iptv_wget_continue', 'iptv_wget_timeout', 'iptv_wget_waitretry', 'iptv_wget_retry_on_http_error', 'iptv_wget_tries']

    @staticmethod
    def GET_WGET_PATH():
        return '/usr/bin/wget'

    @staticmethod
    def GET_CURL_PATH():
        return '/usr/bin/curl'

    @staticmethod
    def GET_F4M_PATH():
        return '/usr/bin/f4mdump'

    @staticmethod
    def GET_HLSDL_PATH():
        return '/usr/bin/hlsdl'

    # hlsdl -R keeps "<output>.hlsdl.resume" next to the output while a VOD download runs,
    # so an interrupted run can be continued instead of started over
    HLSDL_RESUME_SUFFIX = '.hlsdl.resume'
    _hlsdlResumeSupported = None

    @staticmethod
    def hlsdlResumeInHelp(helpText):
        # the usage text of an hlsdl that can resume: version 0.31+ (the sidecar format the
        # plugin relies on) and the -R option listed
        try:
            text = helpText or ''
            match = re.search(r'hlsdl v(\d+)\.(\d+)', text)
            if match is None or (int(match.group(1)), int(match.group(2))) < (0, 31):
                return False
            return re.search(r'^-R \.\.\. ', text, re.MULTILINE) is not None
        except Exception:
            printExc()
            return False

    @staticmethod
    def hlsdlSupportsResume():
        # Probed once per run: hlsdl without arguments only prints its usage text and exits.
        # A build without -R must never be handed the option (it aborts with the usage text),
        # so any doubt means "not supported" and the old behaviour (start over) stays.
        if DMHelper._hlsdlResumeSupported is None:
            supported = False
            try:
                path = DMHelper.GET_HLSDL_PATH()
                if os.path.isfile(path):
                    pipe = os.popen(path + ' 2>&1 </dev/null')
                    try:
                        supported = DMHelper.hlsdlResumeInHelp(pipe.read())
                    finally:
                        pipe.close()
            except Exception:
                printExc()
            DMHelper._hlsdlResumeSupported = supported
            printDBG("DMHelper.hlsdlSupportsResume [%r]" % supported)
        return DMHelper._hlsdlResumeSupported

    @staticmethod
    def _hlsdlResumeFiles(filePath):
        from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import fsPath
        sidecar = fsPath(filePath) + DMHelper.HLSDL_RESUME_SUFFIX
        return [sidecar, sidecar + '.tmp']

    @staticmethod
    def hasHlsdlResumeFile(filePath):
        try:
            return bool(filePath) and os.path.isfile(DMHelper._hlsdlResumeFiles(filePath)[0])
        except Exception:
            printExc()
            return False

    @staticmethod
    def removeHlsdlResumeFiles(filePath):
        try:
            if filePath:
                for path in DMHelper._hlsdlResumeFiles(filePath):
                    if os.path.isfile(path):
                        os.remove(path)
        except Exception:
            printExc()

    @staticmethod
    def GET_FFMPEG_PATH():
        # altFFMPEGPath = '/iptvplayer_rootfs/usr/bin/ffmpeg'
        # if IsExecutable(altFFMPEGPath):
        #    return altFFMPEGPath
        return '/usr/bin/ffmpeg'

    @staticmethod
    def GET_RTMPDUMP_PATH():
        return '/usr/bin/rtmpdump'

    @staticmethod
    def getDownloaderType(url):
        if url.endswith(".f4m"):
            return DMHelper.DOWNLOADER_TYPE.F4F
        else:
            return DMHelper.DOWNLOADER_TYPE.WGET

    @staticmethod
    def getDownloaderCMD(downItem):
        if downItem.downloaderType == DMHelper.DOWNLOADER_TYPE.F4F:
            return DMHelper.getF4fCMD(downItem)
        else:
            return DMHelper.getWgetCMD(downItem)

    @staticmethod
    def makeUnikalFileName(fileName, withTmpFileName=True, addDateToFileName=False):
        baseName = os.path.basename(fileName).replace('\\', '')

        printDBG("DMHelper::makeUnikalFileName(%s, %s, %s) baseName: %s" % (fileName, withTmpFileName, addDateToFileName, baseName))

        if not addDateToFileName:
            tries = 10
            for idx in range(tries):
                if idx > 0:
                    uniqueID = str(idx + 1) + '. '
                else:
                    uniqueID = ''
                newFileName = os.path.dirname(fileName) + os.sep + uniqueID + baseName
                if fileExists(newFileName):
                    continue
                if withTmpFileName:
                    tmpFileName = os.path.dirname(fileName) + os.sep + "." + uniqueID + baseName
                    if fileExists(tmpFileName):
                        continue
                    return newFileName, tmpFileName
                else:
                    return newFileName

        # if this function is called
        # no more than once per second
        # date and time (with second)
        # is sufficient to provide a unique name
        from time import gmtime, strftime
        date = strftime("%Y-%m-%d_%H.%M.%S_", gmtime()).replace(':', '.')

        newFileName = os.path.dirname(fileName) + os.sep + date + baseName
        if withTmpFileName:
            tmpFileName = os.path.dirname(fileName) + os.sep + "." + date + baseName
            return newFileName, tmpFileName
        else:
            return newFileName

    @staticmethod
    def getFileSize(filename):
        try:
            st = os.stat(filename)
            ret = st.st_size
        except Exception:
            ret = -1
        return ret

    @staticmethod
    def getRemoteContentInfoByUrllib(url, addParams={}):
        remoteContentInfo = {}
        addParams = DMHelper.downloaderParams2UrllibParams(addParams)
        addParams['max_data_size'] = 0

        cm = common()
        # only request
        sts = cm.getPage(url, addParams)[0]
        if sts:
            remoteContentInfo = {'Content-Length': cm.meta.get('content-length', -1), 'Content-Type': cm.meta.get('content-type', '')}
        printDBG("getRemoteContentInfoByUrllib: [%r]" % remoteContentInfo)
        return sts, remoteContentInfo

    @staticmethod
    def downloaderParams2UrllibParams(params):
        tmpParams = {}
        userAgent = params.get('User-Agent', '')
        if '' != userAgent:
            tmpParams['User-Agent'] = userAgent
        cookie = params.get('Cookie', '')
        if '' != cookie:
            tmpParams['Cookie'] = cookie

        if len(tmpParams) > 0:
            return {'header': tmpParams}
        else:
            return {}

    @staticmethod
    def getDownloaderParamFromUrlWithMeta(url, httpHeadersOnly=False):
        printDBG("DMHelper.getDownloaderParamFromUrlWithMeta url[%s], url.meta[%r]" % (url, url.meta))
        downloaderParams = {}
        for key in url.meta:
            if key in DMHelper.HANDLED_HTTP_HEADER_PARAMS:
                downloaderParams[key] = url.meta[key]
            elif key == 'http_proxy':
                downloaderParams[key] = url.meta[key]
        if not httpHeadersOnly:
            for key in DMHelper.IPTV_DOWNLOADER_PARAMS:
                if key in url.meta:
                    downloaderParams[key] = url.meta[key]
        return url, downloaderParams

    @staticmethod
    def getDownloaderParamFromUrl(url):
        if isinstance(url, strwithmeta):
            return DMHelper.getDownloaderParamFromUrlWithMeta(url)

        downloaderParams = {}
        paramsTab = url.split('|')
        url = paramsTab[0]
        del paramsTab[0]

        for param in DMHelper.HEADER_PARAMS:
            for item in paramsTab:
                if item.startswith(param['marker']):
                    downloaderParams[param['name']] = item[len(param['marker']):]

        # ugly workaround the User-Agent param should be passed in url
        if -1 < url.find('apple.com'):
            downloaderParams['User-Agent'] = 'QuickTime/7.6.2'

        return url, downloaderParams

    @staticmethod
    def getBaseWgetCmd(downloaderParams={}):
        printDBG("getBaseWgetCmd downloaderParams[%r]" % downloaderParams)
        from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import shellQuote
        headerOptions = ''
        proxyOptions = ''

        # same default UA as pCommon's page requests, so it stays current
        defaultHeader = ' --header "User-Agent: %s" ' % common.HOST
        for key, value in list(downloaderParams.items()):
            if value != '':
                if key in DMHelper.HANDLED_HTTP_HEADER_PARAMS:
                    if 'Cookie' == key:
                        headerOptions += ' --cookies=off '
                    # values (cookies, referer, ...) partly come from web servers - always escaped
                    headerOptions += ' --header "%s: %s" ' % (key, shellQuote(value))
                    if key == 'User-Agent':
                        defaultHeader = ''
                elif key == 'http_proxy':
                    proxyOptions += ' -e use_proxy=yes -e http_proxy="%s" -e https_proxy="%s" ' % (shellQuote(value), shellQuote(value))

        wgetContinue = ''
        if downloaderParams.get('iptv_wget_continue', False):
            wgetContinue = ' -c --timeout="%s" --waitretry="%s" ' % (shellQuote(downloaderParams.get('iptv_wget_timeout', 30)), shellQuote(downloaderParams.get('iptv_wget_waitretry', 1)))
        else:
            if 'iptv_wget_timeout' in downloaderParams:
               wgetContinue += ' --timeout="%s" ' % shellQuote(downloaderParams['iptv_wget_timeout'])
            if 'iptv_wget_waitretry' in downloaderParams:
               wgetContinue += ' --waitretry="%s" ' % shellQuote(downloaderParams['iptv_wget_waitretry'])
            if 'iptv_wget_retry_on_http_error' in downloaderParams:
               wgetContinue += ' --retry-on-http-error="%s" ' % shellQuote(downloaderParams['iptv_wget_retry_on_http_error'])
            if 'iptv_wget_tries' in downloaderParams:
               wgetContinue += ' --tries="%s" ' % shellQuote(downloaderParams['iptv_wget_tries'])

        if 'start_pos' in downloaderParams:
            wgetContinue = ' --start-pos="%s" ' % shellQuote(downloaderParams['start_pos'])

        cmd = DMHelper.GET_WGET_PATH() + wgetContinue + defaultHeader + ' --no-check-certificate ' + headerOptions + proxyOptions
        printDBG("getBaseWgetCmd return cmd[%s]" % cmd)
        return cmd

    @staticmethod
    def getBaseCurlCmd(downloaderParams={}, retries=0):
        # counterpart of getBaseWgetCmd for CurlDownloader, takes the same iptv_wget_* params
        from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import shellQuote
        printDBG("getBaseCurlCmd downloaderParams[%r]" % downloaderParams)
        headerOptions = ''
        proxyOptions = ''
        userAgent = ' -A "%s" ' % common.HOST
        for key, value in list(downloaderParams.items()):
            if value != '':
                if key in DMHelper.HANDLED_HTTP_HEADER_PARAMS:
                    headerOptions += ' -H "%s: %s" ' % (key, shellQuote(value))
                    if key == 'User-Agent':
                        userAgent = ''
                elif key == 'http_proxy':
                    proxyOptions += ' -x "%s" ' % shellQuote(value)

        # -sS: no progress meter, errors only / -f: HTTP 4xx/5xx -> exit 22 instead of saving the error page
        # -g: no globbing of [] {} in the url / -k: like wget --no-check-certificate
        timeout = downloaderParams.get('iptv_wget_timeout', '') or 30
        options = ' -sS -f -L -k -g --connect-timeout %s --speed-limit 1 --speed-time %s ' % (timeout, max(int(timeout), 60))
        try:
            tries = int(downloaderParams.get('iptv_wget_tries', retries) or 0)
        except Exception:
            tries = 0
        # wget -t 0 means "retry forever", curl has no such mode - keep a few retries
        options += ' --retry %d ' % (tries - 1 if tries > 0 else 5)
        if 'iptv_wget_waitretry' in downloaderParams:
            options += ' --retry-delay "%s" ' % shellQuote(downloaderParams['iptv_wget_waitretry'])
        if 'start_pos' in downloaderParams:
            options += ' -C "%s" ' % shellQuote(downloaderParams['start_pos'])
        elif downloaderParams.get('iptv_wget_continue', False):
            options += ' -C - '

        cmd = DMHelper.GET_CURL_PATH() + options + userAgent + headerOptions + proxyOptions
        printDBG("getBaseCurlCmd return cmd[%s]" % cmd)
        return cmd

    @staticmethod
    def getBaseHLSDLCmd(downloaderParams={}):
        from Plugins.Extensions.IPTVPlayer.iptvdm.downloaderhelpers import shellQuote
        printDBG("getBaseHLSDLCmd downloaderParams[%r]" % downloaderParams)
        headerOptions = ''
        proxyOptions = ''

        userAgent = ' -u "%s" ' % common.HOST
        for key, value in list(downloaderParams.items()):
            if value != '':
                if key in DMHelper.HANDLED_HTTP_HEADER_PARAMS:
                    if key == 'User-Agent':
                        userAgent = ' -u "%s" ' % shellQuote(value)
                    else:
                        headerOptions += ' -h "%s: %s" ' % (key, shellQuote(value))
                elif key == 'http_proxy':
                    # hlsdl takes the proxy with -p; the wget "-e use_proxy=..." form it used to get
                    # set the live playlist refresh delay to 0 (-e) and never used the proxy
                    proxyOptions += ' -p "%s" ' % shellQuote(value)

        cmd = DMHelper.GET_HLSDL_PATH() + ' -q -f -b ' + userAgent + headerOptions + proxyOptions
        printDBG("getBaseHLSDLCmd return cmd[%s]" % cmd)
        return cmd
