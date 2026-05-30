# -*- coding: utf-8 -*-
#
#  IPTV downloader creator
#
#  $Id$
#
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.iptvdm.wgetdownloader import WgetDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.hlsdownloader import HLSDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.ehlsdownloader import EHLSDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.rtmpdownloader import RtmpDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.f4mdownloader import F4mDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.mergedownloader import MergeDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.ffmpegdownloader import FFMPEGDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config
###################################################


def IsUrlDownloadable(url):
    return DownloaderCreator(url) is not None


def IsHlsLikeUrl(url):
    try:
        lowUrl = str(url).lower()
    except Exception:
        printExc()
        return False

    hlsMarkers = [
        '.m3u8',
        '/playlist/',
        'm3u8',
        'x-stream-inf'
    ]

    for marker in hlsMarkers:
        if marker in lowUrl:
            return True

    return False


def DownloaderCreator(url):
    printDBG("DownloaderCreator url[%r]" % url)
    downloader = None
    downloaderParams = {}
    orgUrl = url

    try:
        url, downloaderParams = DMHelper.getDownloaderParamFromUrlWithMeta(url)
    except Exception:
        printExc()
        url = orgUrl
        downloaderParams = {}

    # Get meta safa way
    urlMeta = {}
    try:
        urlMeta = getattr(orgUrl, 'meta', {})
        if not isinstance(urlMeta, dict):
            urlMeta = {}
    except Exception:
        printExc()
        urlMeta = {}

    # Fallback: via downloaderParams
    if not urlMeta and isinstance(downloaderParams, dict):
        urlMeta = downloaderParams

    try:
        proto = urlMeta.get('iptv_proto', '')
    except Exception:
        printExc()
        proto = ''

    # Host-/special case for downloader routing
    try:
        ffmpegCase = str(urlMeta.get('iptv_ffmpeg_case', ''))
    except Exception:
        printExc()
        ffmpegCase = ''

    # Fallback proto via URL
    if not proto:
        try:
            if isinstance(url, str):
                lowUrl = url.lower()
                if '.m3u8' in lowUrl:
                    proto = 'm3u8'
                elif lowUrl.startswith('merge://'):
                    proto = 'merge'
                elif lowUrl.startswith('mpd://') or '.mpd' in lowUrl:
                    proto = 'mpd'
                elif lowUrl.startswith('f4m://') or '.f4m' in lowUrl:
                    proto = 'f4m'
        except Exception:
            printExc()

    try:
        useFFmpeg = bool(urlMeta.get('iptv_use_ffmpeg', False))
    except Exception:
        printExc()
        useFFmpeg = False

    printDBG("DownloaderCreator url[%s]" % url)
    printDBG("DownloaderCreator iptv_proto[%s] iptv_use_ffmpeg[%s] iptv_ffmpeg_case[%s]" % (proto, useFFmpeg, ffmpegCase))
    printDBG("DownloaderCreator downloaderParams[%s]" % downloaderParams)

    #################################################
    # IMPORTANT: If iptv_use_ffmpeg=True is set,
    # then ALWAYS prefer FFMPEGDownloader,
    # even for m3u8/HLS.
    #################################################
    if useFFmpeg or ffmpegCase in ['kinoger', 'pornslash']:
        printDBG("DownloaderCreator: force FFMPEGDownloader by iptv_use_ffmpeg=True or iptv_ffmpeg_case[%s]" % ffmpegCase)
        try:
            return FFMPEGDownloader()
        except Exception:
            printExc()
            downloader = None

    #################################################
    # Default assignment by protocol
    #################################################
    try:
        if proto in ['m3u8', 'hls']:
            printDBG("DownloaderCreator: HLS/M3U8 -> HLSDownloader")
            downloader = HLSDownloader()

        elif proto in ['mpd', 'dash']:
            printDBG("DownloaderCreator: MPD/DASH -> FFMPEGDownloader")
            downloader = FFMPEGDownloader()

        elif proto in ['f4m']:
            printDBG("DownloaderCreator: F4M -> F4mDownloader")
            downloader = F4mDownloader()

        elif proto in ['merge']:
            printDBG("DownloaderCreator: MERGE -> MergeDownloader")
            downloader = MergeDownloader()

        elif proto in ['http', 'https', 'ftp', 'ftps']:
            if IsHlsLikeUrl(url):
                printDBG("DownloaderCreator: HTTP/HTTPS but HLS-like URL -> FFMPEGDownloader")
                downloader = FFMPEGDownloader()
            else:
                printDBG("DownloaderCreator: HTTP/HTTPS/FTP -> WgetDownloader")
                downloader = WgetDownloader()

        elif proto == 'em3u8':
            downloader = EHLSDownloader()
        elif proto == 'rtmp':
            downloader = RtmpDownloader()

        else:
            # Fallback nach URL-Endung
            lowUrl = ''
            try:
                lowUrl = url.lower()
            except Exception:
                printExc()
                lowUrl = ''

            if '.m3u8' in lowUrl:
                printDBG("DownloaderCreator: fallback .m3u8 -> HLSDownloader")
                downloader = HLSDownloader()
            elif '.f4m' in lowUrl:
                printDBG("DownloaderCreator: fallback .f4m -> F4mDownloader")
                downloader = F4mDownloader()
            elif '.mpd' in lowUrl:
                printDBG("DownloaderCreator: fallback .mpd -> FFMPEGDownloader")
                downloader = FFMPEGDownloader()
            elif IsHlsLikeUrl(lowUrl):
                printDBG("DownloaderCreator: fallback HLS-like URL -> FFMPEGDownloader")
                downloader = FFMPEGDownloader()
            else:
                printDBG("DownloaderCreator: fallback default -> WgetDownloader")
                downloader = WgetDownloader()

    except Exception:
        printExc()
        downloader = None

    return downloader
