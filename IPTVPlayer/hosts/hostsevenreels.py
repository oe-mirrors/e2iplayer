# -*- coding: utf-8 -*-
# 7reels (7reels.cc) - TMDb-indexed movie/series aggregator
# based on a community host by "alawa m2"
import json
import re
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized


def GetConfigList():
    return []


def gettytul():
    return 'https://7reels.cc/'


class SevenReels(GenericFolderWatchedScraperMixin, CBaseHostClass):

    POSTER_URL = 'https://image.tmdb.org/t/p/w500'
    BACKDROP_URL = 'https://image.tmdb.org/t/p/w780'
    # TMDb genre ids (movie + tv), used only for the info panel
    GENRES = {
        28: 'Action', 12: 'Adventure', 16: 'Animation', 35: 'Comedy', 80: 'Crime',
        99: 'Documentary', 18: 'Drama', 10751: 'Family', 14: 'Fantasy', 36: 'History',
        27: 'Horror', 10402: 'Music', 9648: 'Mystery', 10749: 'Romance', 878: 'Science Fiction',
        10770: 'TV Movie', 53: 'Thriller', 10752: 'War', 37: 'Western',
        10759: 'Action & Adventure', 10762: 'Kids', 10763: 'News', 10764: 'Reality',
        10765: 'Sci-Fi & Fantasy', 10766: 'Soap', 10767: 'Talk', 10768: 'War & Politics',
    }

    # 7reels' watch page is a JS shell that just iframes one of a fixed set of
    # TMDb-keyed embed providers (server list + URL shapes lifted from the site's
    # own bundle). We hand every candidate to urlparser; whichever ones it knows
    # how to resolve show up as playable links. "tv" appends /<season>/<episode>.
    EMBEDS = (
        ('AdRock', 'https://vidrock.net/%(kind)s/%(id)s%(se)s'),
        ('VidEasy', 'https://player.videasy.to/%(kind)s/%(id)s%(se)s?title=%(title)s&year=%(year)s'),
        ('VidCore', 'https://vidcore.net/%(kind)s/%(id)s%(se)s'),
        ('VidNest', 'https://vidnest.fun/%(kind)s/%(id)s%(se)s'),
        ('VidUp', 'https://vidup.to/%(kind)s/%(id)s%(se)s'),
    )

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'SevenReels', 'cookie': 'SevenReels.cookie'})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        api = self.MAIN_URL + 'api/'
        self.MENU = [
            {'category': 'list_items', 'title': _('Trending this week'), 'url': api + 'recs/top-this-week'},
            {'category': 'list_items', 'title': _('Featured'), 'url': api + 'featured'},
            {'category': 'list_items', 'title': _('Top in your country'), 'url': api + 'top-reels'},
            {'category': 'list_items', 'title': _('Movies'), 'url': api + 'tmdb/discover/movie?sort_by=popularity.desc'},
            {'category': 'list_items', 'title': _('Series'), 'url': api + 'tmdb/discover/tv?sort_by=popularity.desc'},
            {'category': 'list_items', 'title': _('Comedy'), 'url': api + 'tmdb/discover/movie?with_genres=35'},
            {'category': 'list_items', 'title': _('Action & Thriller'), 'url': api + 'tmdb/discover/movie?with_genres=28'},
            {'category': 'list_items', 'title': _('Drama'), 'url': api + 'tmdb/discover/movie?with_genres=18'},
            {'category': 'list_items', 'title': _('Horror'), 'url': api + 'tmdb/discover/movie?with_genres=27'},
            {'category': 'list_items', 'title': _('Sci-Fi & Fantasy'), 'url': api + 'tmdb/discover/movie?with_genres=878'},
            {'category': 'list_items', 'title': _('Romance'), 'url': api + 'tmdb/discover/movie?with_genres=10749'},
            {'category': 'list_items', 'title': _('Documentary'), 'url': api + 'tmdb/discover/movie?with_genres=99'},
            {'category': 'list_items', 'title': _('Animation'), 'url': api + 'tmdb/discover/movie?with_genres=16'},
        ] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper('sevenreels')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('title', '') == _('Next page'):
                return ''
            if cItem.get('type', '') in ('video', 'audio'):
                url = str(cItem.get('url', '') or '').strip()
                return 'video:%s' % url if url else ''
            if cItem.get('search_item') or cItem.get('name') == 'history':
                return ''
            if cItem.get('category', '') in ('search', 'search_next_page', 'search_history'):
                return ''
            url = self.wfNormalizeUrlKey(cItem.get('url', ''))
            return 'folder:%s' % url if url else ''
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _genreNames(self, ids):
        return ', '.join(self.GENRES[g] for g in (ids or []) if g in self.GENRES)

    @staticmethod
    def _extractItems(parsed):
        # flatten the several shapes the 7reels API returns into a plain list of TMDb entries
        if not isinstance(parsed, dict):
            return []
        if isinstance(parsed.get('items'), list):
            return parsed['items']
        if isinstance(parsed.get('featured'), dict):
            out = []
            for key in ('movie', 'tv'):
                out.extend(parsed['featured'].get(key) or [])
            return out
        for key in ('results', 'topInCountry'):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        return []

    def listItems(self, cItem):
        printDBG("SevenReels.listItems |%s|" % cItem['url'])
        page = cItem.get('page', 1)
        url = cItem['url']
        if page > 1:
            url += ('&' if '?' in url else '?') + 'page=%d' % page

        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            parsed = json.loads(data)
        except Exception:
            printExc()
            return

        items = self._extractItems(parsed)
        ids = [item.get('id') for item in items if item.get('id')]
        if page > 1 and ids and ids == cItem.get('_prev_ids'):
            # some 7reels endpoints never report total_pages and just keep
            # re-serving the last real page once you page past the end of the
            # list, instead of an empty one - stop here instead of showing
            # (and re-offering "Next page" on) the same titles forever.
            return

        defType = 'tv' if 'discover/tv' in cItem['url'] else 'movie'
        normalize = IsMediaNamingNormalized()
        count = 0
        for item in items:
            mediaId = item.get('id')
            title = self.cleanHtmlStr(item.get('title') or item.get('name') or '')
            if not mediaId or not title:
                continue
            mediaType = item.get('media_type') or defType
            poster = item.get('poster_path') or ''
            backdrop = item.get('backdrop_path') or ''
            year = (item.get('release_date') or item.get('first_air_date') or '')[:4]
            vote = item.get('vote_average') or 0
            dispTitle = ('%s (%s)' % (title, year)) if (year and (normalize or mediaType == 'movie')) else title
            params = dict(cItem)
            params.pop('page', None)
            params.pop('_prev_ids', None)
            params.update({
                'good_for_fav': True,
                'category': 'video',
                'title': dispTitle,
                's_title': title,
                'orig_title': self.cleanHtmlStr(item.get('original_title') or item.get('original_name') or ''),
                'media_type': mediaType,
                'year': year,
                'rating': ('%.1f' % vote) if vote else '',
                'genres': self._genreNames(item.get('genre_ids')),
                'url': '%s%s/%s/watch' % (self.MAIN_URL, mediaType, mediaId),
                'icon': (self.POSTER_URL + poster) if poster else '',
                'backdrop': (self.BACKDROP_URL + backdrop) if backdrop else '',
                'desc': self.cleanHtmlStr(item.get('overview', '')),
            })
            self.addVideo(params)
            count += 1

        # only discover (total_pages) and search (totalPages) are paged; the
        # recs/featured/top-reels endpoints ignore ?page= and have no page count
        totalPages = parsed.get('total_pages') or parsed.get('totalPages') or 0
        if count and page < totalPages:
            params = dict(cItem)
            params.pop('isWatched', None)
            params.pop('isStarted', None)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1, 'last_page': totalPages, 'category': 'list_items', '_prev_ids': ids})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SevenReels.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem['url'] = self.MAIN_URL + 'api/search/smart?q=' + urllib_quote_plus(searchPattern)
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("SevenReels.getLinksForVideo [%s]" % cItem['url'])
        m = re.search(r'/(movie|tv)/(\d+)', cItem['url'])
        if not m:
            return []
        fields = {
            'kind': m.group(1), 'id': m.group(2), 'se': '/1/1' if m.group(1) == 'tv' else '',
            'title': urllib_quote(cItem.get('s_title') or cItem.get('title', '') or '', safe=''),
            'year': cItem.get('year', '') or '',
        }

        urlTab = []
        for label, tpl in self.EMBEDS:
            urlTab.append({'name': label, 'url': strwithmeta(tpl % fields, {'Referer': self.MAIN_URL}), 'need_resolve': 1})
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("SevenReels.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    def getArticleContent(self, cItem):
        printDBG("SevenReels.getArticleContent [%s]" % cItem.get('url', ''))
        title = cItem.get('s_title') or cItem.get('title', '')
        otherInfo = {}
        if cItem.get('media_type'):
            otherInfo['type'] = _('Series') if cItem['media_type'] == 'tv' else _('Movie')
        if cItem.get('year'):
            otherInfo['year'] = cItem['year']
        if cItem.get('rating'):
            otherInfo['tmdb_rating'] = cItem['rating']
        if cItem.get('genres'):
            otherInfo['genres'] = cItem['genres']
        if cItem.get('orig_title') and cItem['orig_title'] != title:
            otherInfo['original_title'] = cItem['orig_title']
        images = [{'title': '', 'url': u} for u in (cItem.get('backdrop'), cItem.get('icon')) if u]
        return [{'title': title, 'text': cItem.get('desc', ''), 'images': images, 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('SevenReels.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        self.currList = []

        if name is None:
            self.listsTab(self.MENU, {'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, SevenReels(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('sevenreels')

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
