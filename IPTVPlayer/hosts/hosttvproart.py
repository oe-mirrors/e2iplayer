# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# TV Proart (tvproart.pl) - local TV of southern Wielkopolska (Ostrow Wielkopolski): news, sport,
# magazines and reports as VOD.
# 03.10.2026 - revival + rewrite for the new WordPress site: JSON API under
#   /wp-json/rokezzz/ (wszystkie-kategorie, wszystkie-serie, wszystkie-materialy?category|name&page,
#   szukaj-materialu?search, vod?url) - streams are /wp-json/rokezzz/material/<slug>.mp4 or a YouTube id
#   + watched flag / downloaded flag / sidecar / favourites.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://tvproart.pl/'


class TVProart(GenericFolderWatchedScraperMixin, CBaseHostClass):
    API = 'https://tvproart.pl/wp-json/rokezzz/'
    SKIP_CATS = ('reklamy',)    # paid advertising spots
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'slug', 'title', 'icon', 'desc', 'cat', 'series', 'date', 'txt', 'show')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'tvproart', 'cookie': 'tvproart.cookie'})
        self.MAIN_URL = 'https://tvproart.pl/'
        self.DEFAULT_ICON_URL = 'https://tvproart.pl/wp-json/rokezzz/logo'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Referer': self.MAIN_URL})
        self.defaultParams = {'header': self.HEADER}
        self.watchedHelper = IPTVWatchedHelper('tvproart')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type', '') == 'video':
                slug = str(cItem.get('slug', '') or '').strip()
                return 'video:%s' % slug if slug else ''
            if cItem.get('category') == 'list_items' and cItem.get('series'):
                return 'series:%s' % cItem['series']
            return ''
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _json(self, url):
        sts, data = self.getPage(url)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _date(self, item):
        try:
            return str((item.get('publishedAt') or {}).get('date') or '')[:10]
        except Exception:
            return ''

    def _thumb(self, item):
        thumb = item.get('thumbnail') or ''
        if isinstance(thumb, int) or (thumb and str(thumb).isdigit()):
            thumb = '%sminiaturka/%s' % (self.API, thumb)
        return thumb or item.get('movieSeriesThumbnail') or ''

    def _addMaterial(self, cItem, item):
        slug = item.get('url') or ''
        title = self.cleanHtmlStr(item.get('title') or '')
        if not slug or not title:
            return False
        descTab = []
        date = self._date(item)
        series = self.cleanHtmlStr(item.get('movieSeries') or item.get('parentName') or '')
        if series:
            descTab.append(series)
        if date and date not in title:
            descTab.append(date)
        desc = ' | '.join(descTab)
        text = self.cleanHtmlStr(item.get('description') or '')
        if text:
            desc = '[/br]'.join([x for x in (desc, text) if x])
        params = {'name': 'category', 'good_for_fav': True, 'slug': slug, 'title': normalizeMediathekTitle(title, date=date),
                  'url': '%smaterial/%s' % (self.MAIN_URL, slug), 'icon': self._thumb(item), 'desc': desc,
                  'date': date, 'txt': text, 'show': series}
        self.addVideo(params)
        return True

    ###################################################
    # lists
    ###################################################
    def listCategories(self, cItem):
        data = self._json(self.API + 'wszystkie-kategorie')
        if not isinstance(data, list):
            return
        for item in data:
            slug = item.get('url') or ''
            title = self.cleanHtmlStr(item.get('name') or '')
            if not slug or not title or slug in self.SKIP_CATS:
                continue
            params = dict(cItem)
            params.update({'category': 'list_items', 'title': title, 'cat': slug, 'page': 1, 'good_for_fav': True,
                           'icon': item.get('thumbnail') or '', 'desc': self.cleanHtmlStr(item.get('description') or '')})
            self.addDir(params)

    def listSeries(self, cItem):
        data = self._json(self.API + 'wszystkie-serie')
        if not isinstance(data, list):
            return
        for item in data:
            title = self.cleanHtmlStr(item.get('name') or '')
            if not title:
                continue
            params = dict(cItem)
            params.update({'category': 'list_items', 'title': title, 'series': item.get('name'), 'page': 1, 'good_for_fav': True,
                           'desc': self.cleanHtmlStr(item.get('description') or '')})
            self.addDir(params)

    def listItems(self, cItem):
        page = int(cItem.get('page', 1) or 1)
        query = 'page=%d' % page
        if cItem.get('cat'):
            query += '&category=%s' % urllib_quote_plus(cItem['cat'])
        if cItem.get('series'):
            query += '&name=%s' % urllib_quote_plus(cItem['series'])
        data = self._json(self.API + 'wszystkie-materialy?' + query)
        if not isinstance(data, dict):
            return
        items = data.get('data') or []
        for item in items:
            self._addMaterial(cItem, item)
        try:
            limit = int(data.get('limit') or len(items) or 1)
            lastPage = (int(data.get('total') or 0) + limit - 1) // limit
        except Exception:
            lastPage = 0
        tpl = self.API + 'wszystkie-materialy?' + query.replace('page=%d' % page, 'page={page}', 1)
        addPagingItems(self, cItem, page, bool(items) and page < lastPage, lastPage, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        data = self._json(self.API + 'szukaj-materialu?search=' + urllib_quote_plus(searchPattern))
        if not isinstance(data, list):
            return
        for item in data:
            self._addMaterial(cItem, item)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('TVProart.getLinksForVideo [%s]' % cItem.get('slug', ''))
        slug = cItem.get('slug', '')
        if not slug:
            return []
        data = self._json(self.API + 'vod?url=' + urllib_quote_plus(slug))
        video = (data or {}).get('currentVideo') if isinstance(data, dict) else None
        if not isinstance(video, dict):
            SetIPTVPlayerLastHostError(_('Content not available'))
            return []
        urlTab = []
        ytId = video.get('youtubeUrl') or ''
        if ytId:
            urlTab.append({'name': 'YouTube', 'url': strwithmeta('https://www.youtube.com/watch?v=%s' % ytId, {'Referer': self.MAIN_URL}), 'need_resolve': 1})
        movie = video.get('movie') or ('%smaterial/%s.mp4' % (self.API, slug) if not ytId else '')
        if movie:
            # the server answers every request with a 1 MB "206 Partial Content" piece (Content-Range carries the
            # full size) - players fetch the rest with range requests
            urlTab.append({'name': 'MP4', 'url': strwithmeta(movie, {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.MAIN_URL}), 'need_resolve': 0})
        text = self.cleanHtmlStr(video.get('description') or '')
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), text))

    def getVideoLinks(self, videoUrl):
        printDBG('TVProart.getVideoLinks [%s]' % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO (the list API already carries everything - the vod API has no more text; most news
    # materials have no description at all)
    ###################################################
    def getArticleContent(self, cItem):
        other = {}
        if cItem.get('show'):
            other['station'] = cItem['show']
        if cItem.get('date'):
            other['released'] = cItem['date']
        text = cItem.get('txt') or cItem.get('desc', '')
        icon = cItem.get('icon', '')
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    # favourites
    ###################################################
    def getFavouriteData(self, cItem):
        try:
            if cItem.get('slug') or cItem.get('cat') or cItem.get('series'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('TVProart.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        printDBG('TVProart.handleService: name[%s] category[%s]' % (name, category))
        self.currList = []

        if name is None:
            tab = [{'category': 'list_items', 'title': _('Latest'), 'page': 1},
                   {'category': 'list_cats', 'title': _('Categories')},
                   {'category': 'list_series', 'title': _('Programmes')}] + self.searchItems()
            self.listsTab(tab, {'name': 'category'})
        elif category == 'list_cats':
            self.listCategories(self.currItem)
        elif category == 'list_series':
            self.listSeries(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, TVProart(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('tvproart')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
