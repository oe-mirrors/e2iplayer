# -*- coding: utf-8 -*-
# WP Wideo (wideo.wp.pl, formerly wp.tv) - video programmes of Wirtualna Polska
# Programmes: the "/<slug>-<id>vc" cycles of the site navigation; their episodes come from
#   /frontendparts/video-cycle-episodes-load-more?cycleId=<id>&offset=N&limit=24 (HTML teasers + hasMore).
# Episode page (kobieta.wp.pl/..., wiadomosci.wp.pl/... "-<id>v"): WPP_VIDEO_EMBED -> get.wp.tv/?mid=<mid>
#   -> https://wideo.wp.pl/player/mid,<mid>,embed.json -> MP4 HQ/LQ + HLS.
# Search: /szukaj?q=<words>&s=newest&p=<page>.
# Last Modified: 03.10.2026 - rewrite for wideo.wp.pl: programmes, search, watched flag, naming, sidecar, INFO
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigYesNo, getConfigListEntry
import re
###################################################

config.plugins.iptvplayer.wptv_mp4_first = ConfigYesNo(default=True)


def GetConfigList():
    return [getConfigListEntry(_("Prefer MP4 over HLS:"), config.plugins.iptvplayer.wptv_mp4_first)]


def gettytul():
    return 'https://wideo.wp.pl/'


class WpTV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'raw_title', 'icon', 'desc', 'mid', 'series', 'cycle_id')
    PAGE_SIZE = 24

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'wptv', 'cookie': 'wptv.cookie'})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = 'https://wideo.wp.pl/staticfiles/icons/icon.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('wptv')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type') == 'video':
                vid = self._videoId(cItem.get('url', ''))
                if vid:
                    return 'video:%s' % vid
                return 'video:mid:%s' % cItem['mid'] if cItem.get('mid') else ''
            if cItem.get('category') == 'list_episodes' and cItem.get('cycle_id'):
                return 'folder:%s' % cItem['cycle_id']
        except Exception:
            printExc()
        return ''

    def _videoId(self, url):
        return self.cm.ph.getSearchGroups(str(url or ''), r'-(\d{12,})v$')[0]

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video' or cItem.get('category') == 'list_episodes':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _episodeTitle(self, series, title):
        if IsMediaNamingNormalized() and series and series.lower() not in title.lower():
            return '%s - %s' % (series, title)
        return title

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            seen = set()
            for url, title in re.findall(r'<a [^>]*href="(/[a-z0-9-]+-\d+vc)"[^>]*>(.*?)</a>', data, re.S):
                title = self.cleanHtmlStr(title)
                if not title or url in seen:
                    continue
                seen.add(url)
                params = dict(cItem)
                params.update({'category': 'list_episodes', 'title': title, 'url': self.getFullUrl(url),
                               'cycle_id': self.cm.ph.getSearchGroups(url, r'-(\d+)vc$')[0], 'series': title, 'good_for_fav': True})
                self.addDir(params)
        self.listsTab(self.searchItems(), cItem)

    def _addTeaser(self, cItem, html, series=''):
        url = self.cm.ph.getSearchGroups(html, r'''href="(https?://[^"]+-\d{12,}v)"''')[0]
        if not url:
            return False
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(html, ('<a', '>', 'wp-video-episode-link'), ('</a', '>'), False)[1])
        if not title:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(html, ('<h2', '>'), ('</h2', '>'), False)[1])
        if not title:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(html, r'''alt="([^"]+)"''')[0])
        if not title:
            return False
        icon = self.cm.ph.getSearchGroups(html, r'''<img[^>]+src="(https?://[^"]+)"''')[0]
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(html, r'''duration[^"]*"[^>]*>(?:\s*<[^>]+>)*\s*<span>([^<]+)</span>''')[0])
        desc = (_('Duration: %s') % duration) if duration else ''
        params = {'name': 'category', 'type': 'video', 'title': self._episodeTitle(series, title), 'raw_title': title,
                  'url': url, 'icon': icon, 'desc': desc, 'series': series, 'good_for_fav': True}
        self.addVideo(params)
        return True

    def listEpisodes(self, cItem):
        cycleId = cItem.get('cycle_id') or self.cm.ph.getSearchGroups(cItem.get('url', ''), r'-(\d+)vc$')[0]
        if not cycleId:
            return
        page = int(cItem.get('page', 1) or 1)
        url = self.getFullUrl('/frontendparts/video-cycle-episodes-load-more?cycleId=%s&offset=%d&limit=%d' % (cycleId, (page - 1) * self.PAGE_SIZE, self.PAGE_SIZE))
        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return
        series = cItem.get('series', '')
        episodes = data.get('episodes') or []
        for html in episodes:
            self._addTeaser(cItem, html, series)
        try:
            lastPage = (int(data.get('totalCount') or 0) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        except (TypeError, ValueError):
            lastPage = 0
        # offset paging: the list is read by 'page', the template only enables "Jump" (the url stays the programme page)
        listItem = dict(cItem, cycle_id=cycleId, base_url=cItem.get('base_url') or cItem.get('url', ''))
        addPagingItems(self, listItem, page, bool(episodes) and bool(data.get('hasMore')), lastPage, listItem['base_url'] + '#page={page}')

    def listSearchResult(self, cItem, searchPattern, searchType):
        page = int(cItem.get('page', 1) or 1)
        base = self.getFullUrl('/szukaj?q=%s&s=newest' % urllib_quote_plus(searchPattern))
        tpl = base + '&p={page}'
        sts, data = self.getPage(base if page <= 1 else tpl.format(page=page))
        if not sts:
            return
        count = 0
        for html in re.findall(r'<a id="\d+" href="[^"]+" class="wp-teaserlisting-link">.*?</a>', data, re.S):
            if self._addTeaser(cItem, html):
                count += 1
        pages = [int(n) for n in re.findall(r'[?&;]p=(\d+)&amp;q=', data)]
        if count:
            addPagingItems(self, cItem, page, (page + 1) in pages, max(pages + [page]), tpl)

    ###################################################
    # links
    ###################################################
    def _getClip(self, cItem):
        mid = cItem.get('mid', '')
        data = ''
        if not mid:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return None, ''
            mid = self.cm.ph.getSearchGroups(data, r'get\.wp\.tv/\?mid=(\d+)')[0]
            if not mid:
                mid = self.cm.ph.getSearchGroups(data, r'"mid"\s*:\s*"?(\d{4,9})"?[,}]')[0]
        if not mid:
            return None, data
        sts, raw = self.getPage(self.getFullUrl('/player/mid,%s,embed.json' % mid))
        if not sts:
            return None, data
        try:
            return json_loads(raw).get('clip'), data
        except Exception:
            printExc()
        return None, data

    def getLinksForVideo(self, cItem):
        printDBG("WpTV.getLinksForVideo [%s]" % cItem.get('url', ''))
        clip, data = self._getClip(cItem)
        if not isinstance(clip, dict):
            if data:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        meta = {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.getMainUrl()}
        mp4Tab = []
        hlsTab = []
        for item in clip.get('url') or []:
            url = item.get('url') or ''
            vtype = item.get('type') or ''
            if not self.cm.isValidUrl(url):
                continue
            if vtype.startswith('mp4'):
                name = 'MP4 %s %s' % (item.get('quality', ''), item.get('resolution', ''))
                mp4Tab.append({'name': name.strip(), 'url': strwithmeta(url, meta), 'need_resolve': 0, 'q': 2 if item.get('quality') == 'HQ' else 1})
            elif vtype.startswith('hls'):
                for it in getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999):
                    it['need_resolve'] = 0
                    it['name'] = 'HLS %s' % it.get('name', '')
                    hlsTab.append(it)
        mp4Tab.sort(key=lambda x: -x.pop('q'))
        urlTab = (mp4Tab + hlsTab) if config.plugins.iptvplayer.wptv_mp4_first.value else (hlsTab + mp4Tab)
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        synopsis = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta property="og:description" content="([^"]*)"''')[0]) if data else ''
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis or cItem.get('desc', '')))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("WpTV.getArticleContent [%s]" % cItem.get('url', ''))
        title = self.cleanHtmlStr(cItem.get('raw_title') or cItem.get('title', ''))
        icon = cItem.get('icon', '')
        text = ''
        other = {}
        if cItem.get('type') == 'video':
            clip, data = self._getClip(cItem)
            if data:
                text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta property="og:description" content="([^"]*)"''')[0])
                icon = self.cm.ph.getSearchGroups(data, r'''<meta property="og:image" content="([^"]+)"''')[0] or icon
            if isinstance(clip, dict):
                try:
                    secs = int(clip.get('duration') or 0)
                    if secs:
                        other['duration'] = '%d:%02d:%02d' % (secs // 3600, (secs % 3600) // 60, secs % 60)
                except Exception:
                    pass
                created = (clip.get('media') or {}).get('createDate') or ''
                if created:
                    other['released'] = created
                if clip.get('tags'):
                    other['genre'] = self.cleanHtmlStr(clip['tags'])
        else:
            sts, data = self.getPage(cItem['url'])
            if sts:
                text = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'wp-video-series-banner-description'), ('</p', '>'), False)[1])
                if not text:
                    text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta property="og:description" content="([^"]*)"''')[0])
        if cItem.get('series'):
            other['station'] = cItem['series']
        return [{'title': title, 'text': text or cItem.get('desc', ''), 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("WpTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, WpTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('wptv')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video' or cItem.get('category') == 'list_episodes'
