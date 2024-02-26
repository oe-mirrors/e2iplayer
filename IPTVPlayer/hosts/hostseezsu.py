# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_binary
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
import base64
try:
    import json
except Exception:
    import simplejson as json
###################################################

def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return 'http://seez.su/'


class Seezsu(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'seez.su', 'cookie': 'seez.su.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://seez.su/'
        self.API_URL = 'https://api.themoviedb.org/3/'
        self.API_KEY = '?api_key=d0e6107be30f2a3cb0a34ad2a90ceb6f'
        self.VIDEO_URL = 'https://vidsrc.pro/embed/%s/%s'
#        self.DEFAULT_ICON_URL = 'https://seez.su/storage/branding_media/cbd06244-e15a-4f95-9df0-9c6be3fb83c8.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl(), 'Upgrade-Insecure-Requests': '1', 'Connection': 'keep-alive'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(url)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, cItem):
        printDBG("Seezsu.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'list_sort', 'title': _('Movies'), 'url': self.API_URL, 'media_type': 'movie'},
                        {'category': 'list_sort', 'title': _('Series'), 'url': self.API_URL, 'media_type': 'tv'},
#                        {'category':'list_years',     'title': _('Filter By Year'),    'url':self.MAIN_URL},
                        {'category': 'list_cats', 'title': _('Movies genres'), 'url': self.API_URL, 'media_type': 'discover/movie'},
#                        {'category':'list_az',        'title': _('Alphabetically'),    'url':self.MAIN_URL},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, 
                        ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    ###################################################
    def _fillMovieFilters(self, cItem):
        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}

        # fill sort
        if cItem.get('media_type', '') == 'tv':
            dat = [('/popular', _('Popular')),
                   ('/top_rated', _('Top')),
                   ('/airing_today', _('Airing'))
                ]
        else:
            dat = [('/popular', _('Popular')),
                   ('/top_rated', _('Top')),
                   ('/upcoming', _('Upcoming'))
                ]

        for item in dat:
            self.cacheMovieFilters['sort'].append({'title': item[1], 'sort': item[0]})

        sts, data = self.getPage(self.API_URL + 'genre/movie/list' + self.API_KEY)
        if sts:
            if '"genres":' in data:
                data = json_loads(data)
        # fill cats
                for item in data['genres']:
                    self.cacheMovieFilters['cats'].append({'title': item['name'], 'cats': item['id']})

    ###################################################
    def listMovieFilters(self, cItem, category):
        printDBG("Seezsu.listMovieFilters")

        filter = cItem['category'].split('_')[-1]
        self._fillMovieFilters(cItem)
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = []
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)

    def listsTab(self, tab, cItem, category=None):
        printDBG("Seezsu.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("Seezsu.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        media_type = cItem.get('media_type', '')

        url = cItem['url']
        if '&query=' not in url:
            url = url + media_type
            sort = cItem.get('sort', '')
            if sort not in url:
                url = url + sort
            if self.API_KEY not in url:
                url = url + self.API_KEY

        if 'discover' in media_type:
            url = url + '&with_genres=%s' % cItem.get('cats', '')

        url = url + '&page={0}'.format(page)

        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])
        printDBG("Seezsu.listItems data [%s]" % data)

        data = json_loads(data)
        nextPage = True
        data = data.get('results', '')

        for item in data:
            printDBG("Seezsu.listItems item %s" % item)
            id = item.get('id', '')
            if id == '':
                continue
            imedia_type = item.get('media_type', '')
            if imedia_type != '':
                media_type = imedia_type
            url = self.VIDEO_URL % (media_type.replace('discover/', ''), id)
            icon = item.get('poster_path', '')
            if isinstance(icon, str) and icon != '':
                icon = self.getFullIconUrl('https://image.tmdb.org/t/p/w300/' + icon)
            else:
                icon = ''
            title = item.get('title', '')
            if title == '':
                title = item.get('name', '')
            desc = item.get('overview', '')
            if media_type == 'tv':
                url = self.API_URL + 'tv/%s%s' % (id, self.API_KEY)
                params = {'good_for_fav': True, 'category': 'list_seasons', 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addDir(params)
            else:
                params = {'good_for_fav': True, 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSeriesSeasons(self, cItem, nextCategory):
        printDBG("Seezsu.listSeriesSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = json_loads(data)

        s_id = data.get('id', '')
        for item in data['seasons']:
            printDBG("Seezsu.listSeriesSeasons item [%s]" % item)
            id = item.get('id', '')
            if id == '':
                continue
            s_number = item.get('season_number', '')
            url = self.API_URL + 'tv/%s/season/%s%s' % (s_id, s_number, self.API_KEY)
            icon = item.get('poster_path', '')
            if isinstance(icon, str) and icon != '':
                icon = self.getFullIconUrl('https://image.tmdb.org/t/p/w300/' + icon)
            else:
                icon = cItem['icon']
            desc = item.get('overview', '')
            title = item.get('name', '')
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 's_num': s_number, 'series_title': cItem['title'], 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

    def listSeriesEpisodes(self, cItem):
        printDBG("Seezsu.listSeriesEpisodes [%s]" % cItem)
        self.cacheLinks = {}
        sNum = cItem['s_num']

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        data = json_loads(data)

        for item in data['episodes']:
            printDBG("Seezsu.listSeriesEpisodes item [%s]" % item)
            id = item.get('show_id', '')
            if id == '':
                continue
            url = url = self.VIDEO_URL % ('tv', id) + '/%s/%s' % (sNum, item.get('episode_number', ''))
            icon = item.get('still_path', '')
            if isinstance(icon, str) and icon != '':
                icon = self.getFullIconUrl('https://image.tmdb.org/t/p/w300/' + icon)
            else:
                icon = cItem['icon']
            desc = item.get('overview', '')
            title = item.get('name', '')
            params = {'good_for_fav': True, 'url': url, 'title': title, 'desc': desc, 'icon': icon}
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Seezsu.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.API_URL + 'search/multi%s&query=%s' % (self.API_KEY, urllib_quote_plus(searchPattern))
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("Seezsu.getLinksForVideo [%s]" % cItem)
        return self.up.getVideoLinkExt(cItem['url'])

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

    #MAIN MENU
        if name == None and category == '':
            rm(self.COOKIE_FILE)
            self.listMainMenu({'name': 'category'})
        elif 'list_cats' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif 'list_years' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif 'list_az' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif 'list_sort' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_seasons':
            self.listSeriesSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listSeriesEpisodes(self.currItem)

    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Seezsu(), True, [])
