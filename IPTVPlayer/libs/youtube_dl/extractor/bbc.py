# -*- coding: utf-8 -*-

import urllib
import urllib2
import re
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir, GetCookieDir, byteify, rm
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.base import InfoExtractor
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads

from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry

config.plugins.iptvplayer.bbc_default_quality = ConfigSelection(default="900", choices=[
("0", _("the worst")),
("500", "360p"),
("600", "480p"),
("900", "720p"),
("99999999", _("the best"))
])
config.plugins.iptvplayer.bbc_use_default_quality = ConfigYesNo(default=False)
config.plugins.iptvplayer.bbc_prefered_format = ConfigSelection(default="hls", choices=[
("hls", _("HLS/m3u8")),
("dash", _("DASH/mpd")),
])
config.plugins.iptvplayer.bbc_use_web_proxy = ConfigYesNo(default=False)


def int_or_none(data):
    ret = 0
    try:
        ret = int(data)
    except Exception:
        pass
    return ret


class BBCCoUkIE(InfoExtractor):

    class MediaSelectionError(Exception):
        def __init__(self, id):
            self.id = id

    def __init__(self):
        self.IE_NAME = 'bbc.co.uk'
        self._ID_REGEX = r'[pb][\da-z]{7}'
        self._VALID_URL = r'''(?x)
                        https?://
                            (?:www\.)?bbc\.co\.uk/
                            (?:
                                programmes/(?!articles/)|
                                iplayer(?:/[^/]+)?/(?:episode/|playlist/)|
                                music/clips[/#]|
                                radio/player/
                            )
                            (?P<id>%s)(?!/(?:episodes|broadcasts|clips))
                        ''' % self._ID_REGEX

        self._MEDIASELECTOR_URLS = [
                'http://open.live.bbc.co.uk/mediaselector/5/select/version/2.0/mediaset/iptv-all/vpid/%s',
                'http://open.live.bbc.co.uk/mediaselector/5/select/version/2.0/mediaset/pc/vpid/%s',
                'http://open.live.bbc.co.uk/mediaselector/4/mtis/stream/%s',
                'http://open.live.bbc.co.uk/mediaselector/5/select/version/2.0/mediaset/journalism-pc/vpid/%s',
            ]

        self._MEDIASELECTOR_URLS_2 = self._MEDIASELECTOR_URLS

        InfoExtractor.__init__(self)
        self.COOKIE_FILE = GetCookieDir('bbciplayer.cookie')
        self.HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Encoding': 'gzip, deflate'}
        self.cm.HEADER = self.HEADER # default header
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getFullUrl(self, url):
        if config.plugins.iptvplayer.bbc_use_web_proxy.value and 'englandproxy.co.uk' not in url:
            try:
                url = 'https://www.englandproxy.co.uk/' + url[url.find('://') + 3:]
            except Exception:
                pass
        return url

    def getPage(self, url, params={}, post_data=None):
        HTTP_HEADER = dict(self.HEADER)
        params.update({'header': HTTP_HEADER})
        return self.cm.getPage(self.getFullUrl(url), params, post_data)

    def _extract_asx_playlist(self, connection, programme_id):
        url = self.xmlGetArg(connection, 'href')
        sts, asx = self.getPage(url, self.defaultParams)
        if not sts:
            return []
        a = FixMe
        return [ref.get('href') for ref in asx.findall('./Entry/ref')]

    def _extract_medias(self, mediaData):
        error = self.xmlGetAllNodes(mediaData, 'error')

        if len(error):
            raise BBCCoUkIE.MediaSelectionError(self.xmlGetArg(error[0], 'id'))

        return self.xmlGetAllNodes(mediaData, 'media')

    def _get_subtitles(self, media, programme_id):
        subtitles = []
        for connection in self.xmlGetAllNodes(media, 'connection'):
            subUrl = self.xmlGetArg(connection, 'href')
            if not self.cm.isValidUrl(subUrl):
                continue
            sts, captions = self.getPage(subUrl, self.defaultParams)
            if not sts:
                continue
            lang = self.cm.ph.getSearchGroups(captions, '''[\:\s]lang="([^"]+?)"''')[0]
            if lang == '':
                lang = 'en'
            subtitles.append({'lang': lang, 'url': subUrl, 'ext': 'ttml'})
        return subtitles

    def _raise_extractor_error(self, media_selection_error):
        raise Exception(
            '%s returned error: %s' % (self.IE_NAME, media_selection_error.id))

    def _download_media_selector(self, programme_id):
        last_exception = None

        formatsTab = []
        subtitlesTab = []
        withSubtitles = True

        if config.plugins.iptvplayer.bbc_prefered_format.value == 'hls':
            mediaselectorUrls = self._MEDIASELECTOR_URLS
        else:
            mediaselectorUrls = self._MEDIASELECTOR_URLS_2

        hasDASH = False
        hasHLS = False
        for mediaselector_url in mediaselectorUrls:
            try:
                if len(subtitlesTab):
                    withSubtitles = False
                formats, subtitles = self._download_media_selector_url(mediaselector_url % programme_id, programme_id, withSubtitles)
                formatsTab.extend(formats)
                subtitlesTab.extend(subtitles)
                for item in formatsTab:
                    if item.get('ext', '') == 'dash':
                        hasDASH = True
                    if item.get('ext', '') == 'hls':
                        hasHLS = True
                if hasDASH and hasHLS:
                    break
            except Exception:
                printExc()
        if len(formatsTab):
            return formatsTab, subtitlesTab
        self._raise_extractor_error(last_exception)

    def _download_media_selector_url(self, url, programme_id=None, withSubtitles=False):
        sts, media_selection = self.getPage(url, self.defaultParams)
        if not sts:
            return [], []
        return self._process_media_selector(media_selection, programme_id, withSubtitles)

    def _process_media_selector(self, media_selection, programme_id, withSubtitles=False):
        formats = []
        subtitles = []
        urls = []

        for media in self._extract_medias(media_selection):
            kind = self.xmlGetArg(media, 'kind')
            if kind in ('video', 'audio'):
                bitrate = int_or_none(self.xmlGetArg(media, 'bitrate'))
                encoding = self.xmlGetArg(media, 'encoding')
                service = self.xmlGetArg(media, 'service')
                width = int_or_none(self.xmlGetArg(media, 'width'))
                height = int_or_none(self.xmlGetArg(media, 'height'))
                file_size = int_or_none(self.xmlGetArg(media, 'media_file_size'))
                for connection in self.xmlGetAllNodes(media, 'connection'):
                    href = self.xmlGetArg(connection, 'href')
                    if href in urls:
                        continue
                    if href:
                        urls.append(href)
                    conn_kind = self.xmlGetArg(connection, 'kind')
                    protocol = self.xmlGetArg(connection, 'protocol')
                    supplier = self.xmlGetArg(connection, 'supplier')
                    transfer_format = self.xmlGetArg(connection, 'transferFormat')
                    for format_id in [supplier, conn_kind, protocol]:
                        if format_id != '':
                            break
                    if service != '':
                        format_id = '%s_%s' % (service, format_id)
                    # ASX playlist
                    if supplier == 'asx':
                        for i, ref in enumerate(self._extract_asx_playlist(connection, programme_id)):
                            formats.append({
                                'url': ref,
                                'format_id': 'ref%s_%s' % (i, format_id),
                            })
                    elif transfer_format == 'dash':
                        formats.append({'url': href, 'ext': 'mpd', 'format_id': format_id})
                    elif transfer_format == 'hls':
                        formats.append({'url': href, 'ext': 'hls', 'format_id': format_id})
                    elif transfer_format == 'hds':
                        formats.append({'url': href, 'ext': 'hds', 'format_id': format_id})
                    else:
                        if not service and not supplier and bitrate:
                            format_id += '-%d' % bitrate
                        fmt = {
                            'format_id': format_id,
                            'filesize': file_size,
                        }
                        if kind == 'video':
                            fmt.update({
                                'width': width,
                                'height': height,
                                'vbr': bitrate,
                                'vcodec': encoding,
                            })
                        else:
                            fmt.update({
                                'abr': bitrate,
                                'acodec': encoding,
                                'vcodec': 'none',
                            })
                        if protocol == 'http':
                            # Direct link
                            fmt.update({
                                'url': href,
                            })
                        elif protocol == 'rtmp':
                            application = self.xmlGetArg(connection, 'application')
                            if application == '':
                                application = 'ondemand'
                            auth_string = self.xmlGetArg(connection, 'authString')
                            identifier = self.xmlGetArg(connection, 'identifier')
                            server = self.xmlGetArg(connection, 'server')
                            fmt.update({
                                'url': '%s://%s/%s?%s' % (protocol, server, application, auth_string),
                                'play_path': identifier,
                                'app': '%s?%s' % (application, auth_string),
                                'page_url': 'http://www.bbc.co.uk',
                                'player_url': 'http://www.bbc.co.uk/emp/releases/iplayer/revisions/617463_618125_4/617463_618125_4_emp.swf',
                                'rtmp_live': False,
                                'ext': 'flv',
                            })
                        formats.append(fmt)
            elif kind == 'captions' and withSubtitles:
                subtitles.extend(self._get_subtitles(media, programme_id))
        return formats, subtitles

    def _real_extract(self, url):

        sts, webpage = self.getPage(url, self.defaultParams)
        if not sts:
            return None

        programme_id = None
        duration = None

        tviplayer = self.cm.ph.getSearchGroups(webpage, r'mediator\.bind\(({.+?})\s*,\s*document\.getElementById')[0]

        player = None
        if tviplayer != '':
            printDBG(tviplayer)
            tmp = json_loads(tviplayer)
            player = tmp.get('player', {})
            duration = int_or_none(player.get('duration'))
            programme_id = player.get('vpid')
            if not programme_id:
                try:
                    #programme_id = tmp['episode']['master_brand'].get('ident_id')
                    programme_id = tmp['episode']['versions'][0]['id']
                except Exception:
                    printExc()

        if not programme_id:
            programme_id = self.cm.ph.getSearchGroups(webpage, r'"vpid"\s*:\s*"(%s)"' % self._ID_REGEX)[0]

        if not programme_id and player:
            programme_id = player.get('pid')

        if programme_id and programme_id != '':
            formats, subtitles = self._download_media_selector(programme_id)

            return {
                'id': programme_id,
                'duration': duration,
                'formats': formats,
                'subtitles': subtitles,
            }
        return {}
