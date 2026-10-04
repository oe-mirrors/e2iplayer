# -*- coding: utf-8 -*-
# TV Republika (tvrepublika.pl, formerly telewizjarepublika.pl) - Polish news channel
# Live: the YouTube live streams embedded on https://tvrepublika.pl/live (main channel + "Republika Plus").
# Programmes: the programme cards on the home page link to YouTube playlists ("Zobacz odcinki").
# Latest videos: the uploads of the channel's YouTube channel. Everything plays through the YouTube resolver.
# Last Modified: 03.10.2026 - rewrite for the new site (all video on YouTube): live, programmes, watched flag, sidecar, INFO
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_unquote
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://tvrepublika.pl/'


class TVRepublikaPL(GenericFolderWatchedScraperMixin, CBaseHostClass):

    YT_CHANNEL = 'https://www.youtube.com/channel/UCc282c_TN8xIba_Z6GaDnQw'
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc', 'live', 'video_id')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'tvrepublika', 'cookie': 'tvrepublika.cookie'})
        self.MAIN_URL = 'https://tvrepublika.pl/'
        self.DEFAULT_ICON_URL = ''  # the site logo is an SVG only
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.ytp = YouTubeParser()
        # Polish channel: ask YouTube for the original Polish titles (it auto-translates them to the UI language
        # otherwise) and skip the EU cookie consent page that would replace the playlist/channel pages
        self.ytp._getDefaultLangAndRegion = lambda: ('pl', 'PL')
        self.ytp.HTTP_HEADER['Cookie'] = 'SOCS=CAI; CONSENT=YES+'
        self.watchedHelper = IPTVWatchedHelper('tvrepublika')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            if cItem.get('type') == 'video':
                vid = cItem.get('video_id') or self._ytId(cItem.get('url', ''))
                return 'video:yt:%s' % vid if vid else ''
            if cItem.get('category') == 'list_playlist':
                plId = self.cm.ph.getSearchGroups(cItem.get('url', '') + '&', r'list=([^&]+)&')[0]
                return 'folder:yt:%s' % plId if plId else ''
        except Exception:
            printExc()
        return ''

    def _ytId(self, url):
        url = str(url or '')
        for pattern in (r'[?&]v=([\w-]{11})', r'youtu\.be/([\w-]{11})', r'/(?:live|embed|shorts)/([\w-]{11})'):
            vid = self.cm.ph.getSearchGroups(url, pattern)[0]
            if vid:
                return vid
        return ''

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video' or cItem.get('category') == 'list_playlist':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        for item in [{'category': 'list_live', 'title': _('Live')},
                     {'category': 'list_programs', 'title': _('Programmes')},
                     {'category': 'list_channel', 'title': _('Latest videos'), 'url': self.YT_CHANNEL + '/videos'}]:
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

    def listLive(self, cItem):
        sts, data = self.getPage(self.getFullUrl('/live'))
        if not sts:
            return
        seen = set()
        for tag in re.findall(r'<iframe[^>]+>', data):
            src = self.cm.ph.getSearchGroups(tag, r'''(?:data-src|src)=['"]([^'"]*oembed\?url=[^'"]+)['"]''')[0]
            if not src:
                continue
            ytUrl = urllib_unquote(self.cm.ph.getSearchGroups(src.replace('&amp;', '&'), r'url=([^&]+)')[0])
            vid = self._ytId(ytUrl)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tag, r'''title=['"]([^'"]+)['"]''')[0])
            if not vid or vid in seen:
                continue
            # the live page also carries a few recent clips - only the live streams belong here
            low = title.lower()
            if '/live/' not in ytUrl and 'ywo' not in low and 'live' not in low:
                continue
            seen.add(vid)
            # the YouTube titles change daily (and carry emoji) - stable station names, the YouTube title as description
            name = 'Telewizja Republika Plus' if 'plus' in low else 'Telewizja Republika'
            params = dict(cItem)
            params.update({'title': '%s - %s' % (name, _('Live')), 'url': 'https://www.youtube.com/watch?v=%s' % vid, 'video_id': vid,
                           'icon': 'https://i.ytimg.com/vi/%s/hqdefault.jpg' % vid, 'live': True, 'good_for_fav': True,
                           'desc': (_('Live stream on YouTube') + '[/br]' + title) if title else _('Live stream on YouTube')})
            self.addVideo(params)
        if not seen:
            SetIPTVPlayerLastHostError(_("The live stream is not available at the moment."))

    def listPrograms(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<article  class="tv-program"', '</article>'):
            url = self.cm.ph.getSearchGroups(item, r'''href=['"](https?://(?:www\.)?youtube\.com/playlist\?list=[^'"]+)['"]''')[0].replace('&amp;', '&')
            if not url or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>', 'tv-program__title'), ('</h3', '>'), False)[1])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'tv-program__description'), ('</div', '>'), False)[1])
            icon = self.cm.ph.getSearchGroups(item, r'''data-src=['"]([^'"]+)['"]''')[0].replace('&amp;', '&')
            params = dict(cItem)
            params.update({'category': 'list_playlist', 'title': title or url, 'url': url, 'desc': desc, 'icon': icon, 'good_for_fav': True})
            self.addDir(params)

    def _addYtItems(self, cItem, items, nextCategory):
        for item in items:
            if item.get('type') == 'more' or item.get('is_pagination'):
                params = dict(cItem)
                params.update({'title': _('Next page'), 'url': item.get('url', ''), 'page': item.get('page', '2'),
                               'category': nextCategory, 'good_for_fav': False})
                self.addDir(params)
                continue
            if item.get('type') != 'video':
                continue
            vid = item.get('video_id') or self._ytId(item.get('url', ''))
            if not vid:
                continue
            title = self.cleanHtmlStr(item.get('title', ''))
            live = '[LIVE' in title.upper() or 'TRANSMISJA NA' in title.upper()
            params = {'name': 'category', 'type': 'video', 'title': title, 'url': 'https://www.youtube.com/watch?v=%s' % vid, 'video_id': vid,
                      'icon': item.get('icon', ''), 'desc': self.cleanHtmlStr(item.get('desc', '')), 'good_for_fav': True}
            if live:
                params['live'] = True
            self.addVideo(params)

    def listPlaylist(self, cItem):
        try:
            items = self.ytp.getVideosFromPlaylist(cItem['url'], 'list_playlist', cItem.get('page', '1'), cItem)
        except Exception:
            printExc()
            items = []
        self._addYtItems(cItem, items, 'list_playlist')

    def listChannel(self, cItem):
        try:
            items = self.ytp.getVideosFromChannelList(cItem['url'], 'list_channel', cItem.get('page', '1'), cItem)
        except Exception:
            printExc()
            items = []
        self._addYtItems(cItem, items, 'list_channel')

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("TVRepublikaPL.getLinksForVideo [%s]" % cItem.get('url', ''))
        vid = cItem.get('video_id') or self._ytId(cItem.get('url', ''))
        if not vid:
            return []
        url = 'https://www.youtube.com/watch?v=%s' % vid
        urlTab = [{'name': 'YouTube', 'url': strwithmeta(url, {'iptv_livestream': bool(cItem.get('live'))}), 'need_resolve': 1}]
        if cItem.get('live'):
            return urlTab
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(cItem.get('desc', ''))))

    def getVideoLinks(self, videoUrl):
        printDBG("TVRepublikaPL.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        links = self.up.getVideoLinkExt(videoUrl)
        if not links:
            SetIPTVPlayerLastHostError(_("The video could not be resolved (it may be private, ended or not available in your country)."))
            return []
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        title = self.cleanHtmlStr(cItem.get('title', ''))
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': {}}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("TVRepublikaPL.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_live':
            self.listLive(self.currItem)
        elif category == 'list_programs':
            self.listPrograms(self.currItem)
        elif category == 'list_playlist':
            self.listPlaylist(self.currItem)
        elif category == 'list_channel':
            self.listChannel(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TVRepublikaPL(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('tvrepublika')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video' or cItem.get('category') == 'list_playlist'
