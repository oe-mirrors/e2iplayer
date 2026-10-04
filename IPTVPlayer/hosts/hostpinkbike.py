# -*- coding: utf-8 -*-
# Pinkbike (pinkbike.com) - mountain bike videos: newest, best of today/week/month/all time,
#   the site's video categories (produced videos, quick clips, non-biking, ...) and the video search.
# The site sits behind Cloudflare that only lets Chrome's TLS fingerprint through -> pages via
#   curl-impersonate (no cookie needed). The MP4 files on ev1.pinkbike.org are open to every client.
# Last Modified: 03.10.2026 - revived from Backup and rewritten for the current site: categories from
#   the site, real next page, watched flag, downloaded marker, name normalisation, sidecar, INFO,
#   favourites, search + history, curl-impersonate for the Cloudflare check
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
###################################################

MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}


def GetConfigList():
    return []


def gettytul():
    return 'https://www.pinkbike.com/'


class Pinkbike(GenericFolderWatchedScraperMixin, CBaseHostClass):

    # stable identity of a row (views / favs in desc change)
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'raw_title', 'icon', 'duration', 'date')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Pinkbike.tv', 'cookie': 'pinkbike.cookie'})
        self.MAIN_URL = gettytul()
        self.VIDEO_URL = self.MAIN_URL + 'video/'
        self.DEFAULT_ICON_URL = 'https://es.pinkbike.org/246/sprt/i/pb-icon180x180.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        # Cloudflare blocks every non-Chrome TLS fingerprint: curl-impersonate, no cookie needed
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True,
                              'cookiefile': self.COOKIE_FILE, 'impersonate': True}
        self.cacheMenu = None
        self.watchedHelper = IPTVWatchedHelper('pinkbike')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type', '') == 'video':
                vid = self._videoId(cItem.get('url', ''))
                return 'video:%s' % vid if vid else ''
        except Exception:
            printExc()
        return ''

    @staticmethod
    def _videoId(url):
        m = re.search(r'pinkbike\.com/video/(\d+)', url or '')
        return m.group(1) if m else ''

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        sts, data = self.cm.getPageCFProtection(url, addParams, post_data)
        if not sts:
            meta = getattr(data, 'meta', None) or {}
            if meta.get('status_code') in (403, 503):
                SetIPTVPlayerLastHostError(_('%s refused the request (Cloudflare check, HTTP %s). This host needs curl-impersonate on the receiver.') % ('Pinkbike', meta.get('status_code')))
        return sts, data

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def _fillMenu(self):
        if self.cacheMenu is not None:
            return self.cacheMenu
        sts, data = self.getPage(self.VIDEO_URL)
        if not sts:
            return {'best': [], 'groups': []}
        best = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Best Pinkbike Videos', '</div>', False)[1]
        for url, title in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', tmp):
            title = self.cleanHtmlStr(title)
            if title:
                best.append({'title': title, 'url': self.getFullUrl(url.replace('&amp;', '&'))})
        groups = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<table id="videocats"', '<div class="foot', False)[1] or data
        for block in tmp.split('<td valign="top" width="25%">')[1:]:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(block, '<h3>', '</h3>', False)[1])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(block, '<h5>', '</h5>', False)[1])
            items = []
            for url, name, count in re.findall(r'<a href="(https?://www\.pinkbike\.com/video/[a-z0-9-]+/)">([^<]+)</a>(?:<span class="video_count">\(([0-9]+)\)</span>)?', block):
                if url.rstrip('/').endswith('/uploadcategory'):
                    continue
                items.append({'title': self.cleanHtmlStr(name), 'url': url, 'desc': _('videos: %s') % count if count else ''})
            if title and items:
                groups.append({'title': title, 'desc': desc, 'items': items})
        self.cacheMenu = {'best': best, 'groups': groups}
        return self.cacheMenu

    def listMainMenu(self, cItem):
        menu = self._fillMenu()
        self.addDir({'name': 'category', 'category': 'list_videos', 'good_for_fav': True, 'title': _('Latest'), 'url': self.VIDEO_URL + 'all/'})
        if menu['best']:
            self.addDir({'name': 'category', 'category': 'list_best', 'title': _('Best Pinkbike videos')})
        for idx, group in enumerate(menu['groups']):
            self.addDir({'name': 'category', 'category': 'list_group', 'title': group['title'], 'desc': group['desc'], 'group_idx': idx})
        self.listsTab(self.searchItems(), {'name': 'category'})

    def listBest(self, cItem):
        for item in self._fillMenu()['best']:
            if '/video/all/' in item['url']:
                continue  # "Newest" has its own entry in the main menu
            self.addDir({'name': 'category', 'category': 'list_videos', 'good_for_fav': True, 'title': item['title'], 'url': item['url']})

    def listGroup(self, cItem):
        groups = self._fillMenu()['groups']
        idx = cItem.get('group_idx', -1)
        if idx < 0 or idx >= len(groups):
            return
        for item in groups[idx]['items']:
            self.addDir({'name': 'category', 'category': 'list_videos', 'good_for_fav': True, 'title': item['title'], 'url': item['url'], 'desc': item['desc']})

    def listVideos(self, cItem):
        printDBG('Pinkbike.listVideos |%s|' % cItem.get('url', ''))
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'<a rel="next" class="next" href="([^"]+)"')[0].replace('&amp;', '&')
        # pager: "<list>?...&page=N" links, the highest number is the last page
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        numbers = [int(n) for n in re.findall(r'[?&](?:amp;)?page=(\d+)"', self.cm.ph.getDataBeetwenMarkers(data, '<table class="paging-container">', '</table>', False)[1])]
        lastPage = max(numbers + [page]) if numbers else 0
        m = re.match(r'^(.*[?&]page=)\d+$', nextPage or cItem['url'])
        tpl = (m.group(1).replace('{', '%7B').replace('}', '%7D') + '{page}') if m else ''
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="inList"', '<table class="paging-container">', False)[1] or data
        seen = set()
        for block in data.split('<div class="inElm"')[1:]:
            url = self.cm.ph.getSearchGroups(block, r'href="(https?://www\.pinkbike\.com/video/\d+/)"')[0]
            if not url or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<p><img[^>]*>\s*<a href="[^"]+">(.*?)</a>', ignoreCase=True)[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<li>([^<]+)</li>')[0])
            if not title:
                # quick clips may be uploaded without a title
                title = '%s %s' % (_('Video'), self._videoId(url))
            date = ''
            m = re.search(r'<p class="fgrey f10" style="[^"]*">\s*([A-Z][a-z]{2})[a-z]*,?\s+(\d{1,2}),?\s+(\d{4})\s*</p>', block)
            if m and m.group(1).lower() in MONTHS:
                date = '%s-%02d-%02d' % (m.group(3), MONTHS[m.group(1).lower()], int(m.group(2)))
            icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+class="thimg"[^>]+src="([^"]+)"')[0] or \
                self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+/svt-[^"]+)"')[0]
            stats = [self.cleanHtmlStr(x) for x in re.findall(r'<p class="fgrey f10">(.*?)</p>', block, re.S)]
            duration = self.cm.ph.getSearchGroups(block, r'<span class="fblack">([0-9:]+)</span>')[0]
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<p class="uFullInfo f10 fgrey3"[^>]*>(.*?)</p>', ignoreCase=True)[0])
            desc = ' | '.join([x for x in [date] + stats if x])
            if plot:
                desc = '%s[/br]%s' % (desc, plot) if desc else plot
            # "Title (YYYY-MM-DD)" when the list shows the upload date (newest / search)
            self.addVideo({'good_for_fav': True, 'title': normalizeMediathekTitle(title, date=date), 'raw_title': title, 'url': url,
                           'icon': icon, 'duration': duration, 'date': date, 'desc': desc})
        hasNext = bool(seen) and bool(nextPage) and nextPage != cItem['url']
        addPagingItems(self, dict(cItem, desc=''), page, hasNext, lastPage, tpl, {'url': self.getFullUrl(nextPage)} if hasNext else None)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG('Pinkbike.listSearchResult [%s]' % searchPattern)
        cItem = dict(cItem)
        cItem.update({'category': 'list_videos', 'url': self.VIDEO_URL + 'search/?q=%s' % urllib_quote_plus(searchPattern)})
        self.listVideos(cItem)

    ###################################################
    # video page
    ###################################################
    def _parseVideoPage(self, data):
        info = {'sources': [], 'title': '', 'desc': '', 'icon': '', 'date': '', 'category': '', 'author': '', 'duration': '',
                'views': '', 'location': ''}
        video = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>', False)[1]
        for tag in re.findall(r'<source[^>]+>', video):
            src = self.cm.ph.getSearchGroups(tag, r'src="([^"]+)"')[0]
            res = self.cm.ph.getSearchGroups(tag, r'''res=['"]([0-9]+)['"]''')[0]
            label = self.cm.ph.getSearchGroups(tag, r'data-quality="([^"]+)"')[0] or ('%sp' % res if res else '')
            if src:
                info['sources'].append((int(res) if res else 0, label, self.getFullUrl(src)))
        info['sources'].sort(key=lambda x: -x[0])
        seconds = self.cm.ph.getSearchGroups(video, r'duration="([0-9.]+)"')[0]
        if seconds:
            seconds = int(float(seconds))
            if seconds >= 3600:
                info['duration'] = '%d:%02d:%02d' % (seconds // 3600, (seconds // 60) % 60, seconds % 60)
            elif seconds:
                info['duration'] = '%d:%02d' % (seconds // 60, seconds % 60)
        info['title'] = re.sub(r'\s+Video - Pinkbike$', '', self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:title" content="([^"]*)"')[0]))
        info['desc'] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        info['icon'] = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        info['date'] = self.cm.ph.getSearchGroups(data, r'class="fullTime" title="(\d{4}-\d{2}-\d{2})"')[0]
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Video info</span>', '</dl>', False)[1]
        info['category'] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tmp, r'<dt>Category</dt>\s*<dd>(.*?)</dd>', ignoreCase=True)[0])
        info['location'] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tmp, r'<dt>Location</dt>\s*<dd>(.*?)</dd>', ignoreCase=True)[0]).strip(' ,')
        info['author'] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<a rel="author" href="https?://www\.pinkbike\.com/u/[^"]+">([^<]+)</a>')[0])
        info['views'] = self.cm.ph.getSearchGroups(data, r'id="view-count-video-\d+">\s*<span class="stat-num">([0-9,]+)</span>')[0]
        return info

    def getLinksForVideo(self, cItem):
        printDBG('Pinkbike.getLinksForVideo [%s]' % cItem.get('url', ''))
        url = cItem.get('url', '')
        if not self.cm.isValidUrl(url):
            return []
        sts, data = self.getPage(url)
        if not sts:
            return []
        info = self._parseVideoPage(data)
        if not info['sources']:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        meta = {'User-Agent': self.HEADER['User-Agent'], 'Referer': url}
        urlTab = []
        for res, label, src in info['sources']:
            urlTab.append({'name': 'MP4 %s' % label if label else 'MP4', 'url': strwithmeta(src, meta), 'need_resolve': 0})
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info['desc']))

    def getArticleContent(self, cItem):
        printDBG('Pinkbike.getArticleContent [%s]' % cItem.get('url', ''))
        title = cItem.get('raw_title', cItem.get('title', ''))
        text = cItem.get('desc', '')
        text = re.sub(r'^.*?\[/br\]', '', text) if '[/br]' in text else text
        icon = cItem.get('icon', '')
        otherInfo = {}
        if cItem.get('duration'):
            otherInfo['duration'] = cItem['duration']
        sts, data = self.getPage(cItem.get('url', ''))
        if sts:
            info = self._parseVideoPage(data)
            title = info['title'] or title
            text = info['desc'] or text
            icon = info['icon'] or icon
            for key, src in (('released', 'date'), ('genres', 'category'), ('duration', 'duration'), ('views', 'views')):
                if info[src]:
                    otherInfo[key] = info[src]
            if info['author']:
                otherInfo['creator'] = info['author']
            if info['location']:
                otherInfo['country'] = info['location']
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Pinkbike.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        searchPattern = self.currItem.get('search_pattern', searchPattern)
        printDBG('Pinkbike.handleService: name[%s], category[%s]' % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu(self.currItem)
        elif category == 'list_best':
            self.listBest(self.currItem)
        elif category == 'list_group':
            self.listGroup(self.currItem)
        elif category == 'list_videos':
            self.listVideos(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Pinkbike(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('pinkbike')

    def withArticleContent(self, cItem):
        return cItem.get('type', '') == 'video'
