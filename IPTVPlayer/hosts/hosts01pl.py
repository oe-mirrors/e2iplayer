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
# FOREIGN import
###################################################
import urlparse
import re
import urllib
import base64
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://s01.pl/'


class S01pl(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 's01.pl', 'cookie': 's01.pl.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://s01.pl/'
        self.API_URL = self.getFullUrl('secure/titles')
        self.DEFAULT_ICON_URL = 'http://s01.pl/storage/branding_media/OLh3Gg0Bv1jRmDjeHBDibsQNXx5GllOHjOAAEkJh.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl(), 'Upgrade-Insecure-Requests': '1', 'Connection': 'keep-alive'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.itemsPerPage = 30
        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, cItem):
        printDBG("S01pl.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'list_sort', 'title': _('Movies'), 'url': self.API_URL + '?type=movie&onlyStreamable=true&perPage=%d' % self.itemsPerPage},
                        {'category': 'list_sort', 'title': _('Series'), 'url': self.API_URL + '?type=series&onlyStreamable=true&perPage=%d' % self.itemsPerPage},
#                        {'category':'list_years',     'title': _('Filter By Year'),    'url':self.MAIN_URL},
                        {'category': 'list_cats', 'title': _('Movies genres'), 'url': self.API_URL + '?onlyStreamable=true&perPage=%d' % self.itemsPerPage},
#                        {'category':'list_az',        'title': _('Alphabetically'),    'url':self.MAIN_URL},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    ###################################################
    def _fillMovieFilters(self, cItem):
        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}

        # fill sort
        dat = [('&order=created_at:desc', 'Data dodania'),
               ('&order=popularity:desc', 'Popularność'),
               ('&order=release_date:desc', 'Data wydania'),
               ('&order=user_score:desc', 'Ocena użytkowników'),
               ('&order=revenue:desc', 'Dochód'),
               ('&order=budget:desc', 'Budżet')
            ]
        for item in dat:
            self.cacheMovieFilters['sort'].append({'title': item[1], 'sort': item[0]})

        # fill cats
        dat = [('&genre=Akcja', 'Akcja'),
               ('&genre=Animacja', 'Animacja'),
               ('&genre=Dokumentalny', 'Data wydania'),
               ('&genre=Dramat', 'Dramat'),
               ('&genre=Familijny', 'Familijny'),
               ('&genre=Fantasy', 'Fantasy'),
               ('&genre=Historyczny', 'Historyczny'),
               ('&genre=Horror', 'Horror'),
               ('&genre=Komedia', 'Komedia'),
               ('&genre=Krymina%C5%82', 'Kryminał'),
               ('&genre=Muzyczny', 'Muzyczny'),
               ('&genre=Przygodowy', 'Przygodowy'),
               ('&genre=Romans', 'Romans'),
               ('&genre=Sci-Fi', 'Sci-Fi'),
               ('&genre=Tajemnica', 'Tajemnica'),
               ('&genre=Thriller', 'Thriller'),
               ('&genre=Western', 'Western'),
               ('&genre=Wojenny', 'Wojenny'),
               ('&genre=film%20TV', 'Film TV'),
               ('&genre=Sport%20LIVE', 'Sport LIVE')
            ]
        for item in dat:
            self.cacheMovieFilters['cats'].append({'title': item[1], 'url': cItem['url'] + item[0]})

    ###################################################
    def listMovieFilters(self, cItem, category):
        printDBG("S01pl.listMovieFilters")

        filter = cItem['category'].split('_')[-1]
        self._fillMovieFilters(cItem)
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = []
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)

    def listsTab(self, tab, cItem, category=None):
        printDBG("S01pl.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("S01pl.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        url = cItem['url']

        sort = cItem.get('sort', '')
        if sort not in url:
            url = url + sort

        if page > 1:
            url = url + '&page={0}'.format(page)

        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])
#        printDBG("S01pl.listItems data [%s]" % data)

        try:
            if '/search/' in url:
                data = json_loads(data)['results']
                nextPage = False
            else:
                data = json_loads(data)['pagination']
                nextPage = data['next_page_url']
                data = data['data']
        except Exception:
            printExc()

        for item in data:
#            printDBG("S01pl.listItems item %s" % item)
            url = self.getFullUrl(self.API_URL + '/%d' % item['id'])
            icon = self.getFullIconUrl(item.get('poster', ''))
            if 'original' in icon:
                icon = icon.replace('/original/', '/w500/')
            title = item.get('name', '')
            desc = item.get('description', '')
            if item['is_series']:
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
        printDBG("S01pl.listSeriesSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        try:
            data = json_loads(data)['title']
        except Exception:
            printExc()

        for sItem in data['seasons']:
#            printDBG("S01pl.listSeriesSeasons sItem [%s]" % sItem)
            sts, sdata = self.getPage(self.getFullUrl(cItem['url'] + '?seasonNumber=%d' % sItem['number']))
            if not sts:
                return
            sTitle = 'Sezon %d' % sItem['number']
            sdata = json_loads(sdata)['title']['season']['episodes']
            tabItems = []
            for item in sdata:
#                printDBG("S01pl.listSeriesSeasons item [%s]" % item)
                if item['stream_videos_count'] == 0:
                    continue
                url = self.getFullUrl(cItem['url'] + '?seasonNumber=%d&episodeNumber=%d' % (item['season_number'], item['episode_number']))
                icon = self.getFullIconUrl(item.get('poster', ' '))
                if 'original' in icon:
                    icon = icon.replace('/original/', '/w500/')
                title = item.get('name', '')
                desc = item.get('description', '')
                tabItems.append({'url': url, 'title': title, 'desc': desc, 'icon': icon})
            if len(tabItems):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 'episodes': tabItems, 'icon': cItem['icon'], 'desc': ''})
                self.addDir(params)

    def listSeriesEpisodes(self, cItem):
        printDBG("S01pl.listSeriesEpisodes [%s]" % cItem)
        episodes = cItem.get('episodes', [])
        cItem = dict(cItem)
        for item in episodes:
            self.addVideo(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("S01pl.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/secure/search/%s?limit=20') % urllib.quote_plus(searchPattern)
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("S01pl.getLinksForVideo [%s]" % cItem)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        cUrl = cItem['url']
        url = cItem['url']

        retTab = []

        sts, data = self.getPage(url)
        if not sts:
            return []

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)
        try:
            data = json_loads(data)['title']
        except Exception:
            printExc()

        for item in data['videos']:
#            printDBG("S01pl.getLinksForVideo item[%s]" % item)
            playerUrl = self.getFullUrl(item.get('url', '')).replace(' ', '%20')
            if playerUrl == '':
                continue
            name = self.cm.ph.getDataBeetwenMarkers(item.get('name', ''), '[', ']', True)[1] + ' ' + self.up.getHostName(playerUrl)
            if item['category'] == 'trailer':
                name = '[trailer] ' + name
            retTab.append({'name': name, 'url': strwithmeta(playerUrl, {'Referer': url}), 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("S01pl.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if baseUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        return self.up.getVideoLinkExt(baseUrl)

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
            self.listMovieFilters(self.currItem, 'list_sort')
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
        CHostBase.__init__(self, S01pl(), True, [])
