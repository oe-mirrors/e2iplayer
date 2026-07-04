# -*- coding: utf-8 -*-
# Last Modified: 30.06.2026 - damagic
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
from Components.config import config, ConfigText
###################################################


def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return 'https://premiumsmart.eu/'


class Premiumsmarteu(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'premiumsmart.eu', 'cookie': 'premiumsmart.eu.cookie'})
        config.plugins.iptvplayer.cloudflare_user = ConfigText(default='Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', fixed_size=False)
        self.USER_AGENT = config.plugins.iptvplayer.cloudflare_user.value
        self.MAIN_URL = 'https://premiumsmart.eu/'
        self.API_URL = self.getFullUrl('api/v1/')
        self.DEFAULT_ICON_URL = 'https://premiumsmart.eu/storage/branding_media/9a5b1890-53ce-4052-9a83-862d97a6b285.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl(), 'Upgrade-Insecure-Requests': '1', 'Connection': 'keep-alive'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.itemsPerPage = 50
        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        if data.meta.get('cf_user', self.USER_AGENT) != self.USER_AGENT:
            self.__init__()
        return sts, data

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, cItem):
        printDBG("Premiumsmarteu.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'list_sort', 'title': _('Filmy'), 'url': self.API_URL + 'channel/filmy?perPage=%d' % self.itemsPerPage},
                        {'category': 'list_sort', 'title': _('Seriale'), 'url': self.API_URL + 'channel/seriale?perPage=%d' % self.itemsPerPage},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')},
                        ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    ###################################################
    def _fillMovieFilters(self, cItem):
        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}

        # fill sort
        dat = [('&order=created_at:desc', 'Data dodania'),
               ('&order=popularity:desc', 'Popularność'),
               ('&order=release_date:desc', 'Data wydania'),
               ('&order=rating:desc', 'Ocena użytkowników'),
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
        printDBG("Premiumsmarteu.listMovieFilters")

        filter = cItem['category'].split('_')[-1]
        self._fillMovieFilters(cItem)
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = []
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)

    def listsTab(self, tab, cItem, category=None):
        printDBG("Premiumsmarteu.listsTab")
        for item in tab:
            params = dict(cItem)
            if category is not None:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("Premiumsmarteu.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        url = cItem['url']

        sort = cItem.get('sort', '')
        if sort not in url:
            url = url + sort

        if page > 1:
            url = url + '&page={0}'.format(page)

        urlParams = dict(self.defaultParams)
        sts, data = self.getPage(self.MAIN_URL, urlParams)
        urlParams['header']['x-xsrf-token'] = self.cm.getCookieItem(self.COOKIE_FILE, 'XSRF-TOKEN').replace('%3D', '=')
        sts, data = self.getPage(url, urlParams)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        try:
            if '/search/' in url:
                data = json_loads(data)['results']
                nextPage = False
            else:
                data = json_loads(data)['channel']['content']
                nextPage = data['next_page']
                data = data['data']
        except Exception:
            printExc()
            return

        for item in data:
            try:
                if item['is_series']:
                    video_id = item['id']
                else:
                    video_id = item['primary_video']['id']
            except Exception:
                url = self.getFullUrl(self.API_URL + 'titles/%d?load=primaryVideo' % item['id'])
                sts, data = self.getPage(url)
                if not sts:
                    continue
                try:
                    data = json_loads(data)['title']
                    video_id = data['primary_video']['id']
                except Exception:
                    continue
            icon = self.getFullIconUrl(item.get('poster', ''))
            if 'original' in icon:
                icon = icon.replace('/original/', '/w500/')
            title = item.get('name', '')
            desc = item.get('description', '')
            if item['is_series']:
                url = self.getFullUrl(self.API_URL + 'titles/%d/seasons' % video_id)
                params = {'good_for_fav': True, 'category': 'list_seasons', 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addDir(params)
            else:
                url = self.getFullUrl(self.API_URL + 'watch/%d' % video_id)
                params = {'good_for_fav': True, 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSeriesSeasons(self, cItem, nextCategory):
        printDBG("Premiumsmarteu.listSeriesSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        if not data or not data.strip():
            printDBG("Premiumsmarteu.listSeriesSeasons: empty response")
            return

        if '<!DOCTYPE' in data or '<html' in data:
            printDBG("Premiumsmarteu.listSeriesSeasons: got HTML instead of JSON (probably 404)")
            return

        try:
            data = json_loads(data)
        except Exception:
            printDBG("Premiumsmarteu.listSeriesSeasons: invalid JSON response")
            return

        if 'pagination' not in data or 'data' not in data['pagination']:
            printDBG("Premiumsmarteu.listSeriesSeasons: no pagination data")
            return

        for sItem in data['pagination']['data']:
            sts, sdata = self.getPage(self.getFullUrl(cItem['url'] + '/%d/episodes' % sItem['number']))
            if not sts:
                return
            sTitle = 'Sezon %d' % sItem['number']
            try:
                sdata = json_loads(sdata)
            except Exception:
                printDBG("Premiumsmarteu.listSeriesSeasons: invalid episodes JSON")
                continue

            if 'pagination' not in sdata or 'data' not in sdata['pagination']:
                printDBG("Premiumsmarteu.listSeriesSeasons: no episodes data")
                continue

            sdata = sdata['pagination']['data']
            tabItems = []
            for item in sdata:
                try:
                    url = self.getFullUrl(self.API_URL + 'watch/%d' % item['primary_video']['id'])
                except Exception:
                    continue
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
        printDBG("Premiumsmarteu.listSeriesEpisodes [%s]" % cItem)
        episodes = cItem.get('episodes', [])
        cItem = dict(cItem)
        for item in episodes:
            self.addVideo(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Premiumsmarteu.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl(self.API_URL + 'search/%s?limit=20') % urllib_quote_plus(searchPattern)
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("Premiumsmarteu.getLinksForVideo [%s]" % cItem)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            printDBG("Premiumsmarteu.getLinksForVideo using cache [%d] items" % len(cacheTab))
            return cacheTab

        self.cacheLinks = {}

        cUrl = cItem['url']
        url = cItem['url']

        retTab = []

        sts, data = self.getPage(url)
        if not sts:
            printDBG("Premiumsmarteu.getLinksForVideo failed to get page")
            return []

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)
        try:
            data = json_loads(data)
            printDBG("Premiumsmarteu.getLinksForVideo alternative_videos count[%d]" % len(data.get('alternative_videos', [])))
        except Exception:
            printExc()
            return []

        SKIP_HOSTS = ['drakkar.st', 'bysetayico.com', 'byse']

        for item in data['alternative_videos']:
            playerUrl = self.getFullUrl(item.get('src', '')).replace(' ', '%20')
            if playerUrl == '':
                printDBG("Premiumsmarteu.getLinksForVideo empty playerUrl for item[%s]" % item.get('name', 'unknown'))
                continue

            host = self.up.getHostName(playerUrl)

            skip = False
            for skip_host in SKIP_HOSTS:
                if skip_host in host:
                    printDBG("Premiumsmarteu.getLinksForVideo SKIPPING host[%s] playerUrl[%s]" % (host, playerUrl))
                    skip = True
                    break
            if skip:
                continue

            name = item.get('name', '') + ' - ' + self.up.getHostName(playerUrl)
            if item['category'] == 'trailer':
                name = '[trailer] ' + name

            meta = {'Referer': self.MAIN_URL, 'User-Agent': self.USER_AGENT}
            printDBG("Premiumsmarteu.getLinksForVideo host[%s] playerUrl[%s]" % (host, playerUrl))

            retTab.append({'name': name, 'url': strwithmeta(playerUrl, meta), 'need_resolve': 1})

        printDBG("Premiumsmarteu.getLinksForVideo total links[%d]" % len(retTab))
        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("Premiumsmarteu.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        urlTab = []

        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if baseUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        if 'User-Agent' not in baseUrl.meta:
            baseUrl.meta['User-Agent'] = self.USER_AGENT

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

        if name is None and category == '':
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
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Premiumsmarteu(), True, [])
