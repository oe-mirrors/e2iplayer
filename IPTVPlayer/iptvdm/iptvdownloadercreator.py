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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, IsExecutable
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.iptvdm.wgetdownloader import WgetDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.hlsdownloader import HLSDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.ehlsdownloader import EHLSDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.rtmpdownloader import RtmpDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.f4mdownloader import F4mDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.mergedownloader import MergeDownloader
from Plugins.Extensions.IPTVPlayer.iptvdm.ffmpegdownloader import FFMPEGDownloader
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config
###################################################


def IsUrlDownloadable(url):
    return DownloaderCreator(url) is not None


def DownloaderCreator(url):
    printDBG("DownloaderCreator url[%r]" % url)
    downloader = None

    url = urlparser.decorateUrl(url)
    iptv_proto = url.meta.get('iptv_proto', '')
    if 'm3u8' == iptv_proto:
        downloader = HLSDownloader()
    elif 'em3u8' == iptv_proto:
        downloader = EHLSDownloader()
    elif 'f4m' == iptv_proto:
        downloader = F4mDownloader()
    elif 'rtmp' == iptv_proto:
        downloader = RtmpDownloader()
    elif iptv_proto in ['https', 'http']:
        downloader = WgetDownloader()
    elif 'merge' == iptv_proto:
        if url.meta.get('prefered_merger') == 'hlsdl' and config.plugins.iptvplayer.prefer_hlsdl_for_pls_with_alt_media.value:
            downloader = HLSDownloader()
        elif IsExecutable('ffmpeg'):
            downloader = FFMPEGDownloader()
        else:
            downloader = MergeDownloader()
    elif 'mpd' == iptv_proto and IsExecutable('ffmpeg'):
        downloader = FFMPEGDownloader()

    return downloader
