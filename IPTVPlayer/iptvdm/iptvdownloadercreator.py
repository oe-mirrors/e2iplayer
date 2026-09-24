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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, IsExecutable
from Plugins.Extensions.IPTVPlayer.iptvdm.wgetdownloader import WgetDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.curldownloader import CurlDownloader
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


def HttpDownloaderCreator(urlMeta, forDownload=False):
    # plain HTTP(S)/FTP file: wget by default, curl for real Download Manager
    # downloads when the host asks for it (iptv_downloader meta) or the user
    # picked it in the settings. Buffered playback, covers, subtitles etc.
    # always stay on wget. No curl binary on the box -> wget.
    wanted = ''
    try:
        wanted = str(urlMeta.get('iptv_downloader', '')).lower()
        if not wanted:
            wanted = config.plugins.iptvplayer.http_downloader.value
    except Exception:
        printExc()
    if forDownload and wanted == 'curl':
        if IsExecutable(DMHelper.GET_CURL_PATH()):
            printDBG("DownloaderCreator: HTTP/HTTPS/FTP -> CurlDownloader")
            return CurlDownloader()
        printDBG("DownloaderCreator: curl wanted but %s not found -> WgetDownloader" % DMHelper.GET_CURL_PATH())
    printDBG("DownloaderCreator: HTTP/HTTPS/FTP -> WgetDownloader")
    return WgetDownloader()


def DownloaderCreator(url, forDownload=False):
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
    printDBG("DownloaderCreator iptv_proto[%s] iptv_use_ffmpeg[%s] iptv_ffmpeg_case[%s] forDownload[%s]" % (proto, useFFmpeg, ffmpegCase, forDownload))
    printDBG("DownloaderCreator downloaderParams[%s]" % downloaderParams)

    #################################################
    # merge:// with HLS/DASH components (separate
    # audio+video renditions, e.g. Arte CMAF, Apple
    # bipbop) must be muxed with ffmpeg regardless of
    # caller. HLSDownloader's "-a" alt-audio path only
    # naively interleaves TS packets and yields an
    # unplayable file for fMP4, and MergeDownloader wgets
    # each component whole (fine for progressive URLs,
    # wrong for .m3u8/.mpd playlists).
    #################################################
    mergeNeedsFFmpeg = False
    try:
        if isinstance(url, str) and url.startswith('merge://'):
            compUrls = []
            try:
                for key in url.split('merge://', 1)[1].split('|'):
                    compUrls.append(str(urlMeta.get(key, key)))
            except Exception:
                printExc()
            mergeNeedsFFmpeg = any((IsHlsLikeUrl(u) or '.mpd' in u.lower()) for u in compUrls)
    except Exception:
        printExc()

    #################################################
    # A real Download Manager download of a YouTube merge://
    # (progressive audio+video, identified by the youtube_id
    # meta key youtubeparser.py/urlparser.py always stamp on
    # these URLs) prefers MergeDownloader over the
    # iptv_use_ffmpeg force below: it has sidecar (.txt/.jpg)
    # and MKV-chapter support FFMPEGDownloader lacks, plus its
    # own hardened completeness check for exactly this case.
    # iptv_use_ffmpeg on these URLs exists only to speed up
    # buffered *playback* (progressive muxing instead of
    # download-then-play) and must not steer a real download
    # away from MergeDownloader too. Scoped to youtube_id (not
    # merge:// in general) so other iptv_use_ffmpeg merge://
    # users - e.g. ARTE's split CMAF/fMP4 renditions, which
    # genuinely need ffmpeg for both playback and download -
    # are untouched.
    #################################################
    if forDownload and proto == 'merge' and urlMeta.get('youtube_id') and not mergeNeedsFFmpeg:
        printDBG("DownloaderCreator: real download of YouTube merge:// -> MergeDownloader")
        try:
            return MergeDownloader()
        except Exception:
            printExc()

    #################################################
    # IMPORTANT: If iptv_use_ffmpeg=True is set,
    # then ALWAYS prefer FFMPEGDownloader,
    # even for m3u8/HLS.
    #################################################
    if useFFmpeg or ffmpegCase in ['kinoger']:
        printDBG("DownloaderCreator: force FFMPEGDownloader by iptv_use_ffmpeg=True or iptv_ffmpeg_case[%s]" % ffmpegCase)
        try:
            return FFMPEGDownloader()
        except Exception:
            printExc()
            downloader = None

    if mergeNeedsFFmpeg:
        printDBG("DownloaderCreator: merge:// with HLS/DASH components -> FFMPEGDownloader")
        try:
            return FFMPEGDownloader()
        except Exception:
            printExc()

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
                downloader = HttpDownloaderCreator(urlMeta, forDownload)

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
                printDBG("DownloaderCreator: fallback default -> HTTP downloader")
                downloader = HttpDownloaderCreator(urlMeta, forDownload)

    except Exception:
        printExc()
        downloader = None

    return downloader
