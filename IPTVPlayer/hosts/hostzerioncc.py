# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
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


def gettytul():
    return 'https://zerion.cc/'


class Zerioncc(CBaseHostClass, CaptchaHelper):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'zerion.cc', 'cookie': 'zerion.cc.cookie'})
        config.plugins.iptvplayer.cloudflare_user = ConfigText(default='Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', fixed_size=False)
        self.USER_AGENT = config.plugins.iptvplayer.cloudflare_user.value
        self.MAIN_URL = 'https://zeriun.cc/'
        self.MAIN_API_URL = 'https://zeriun.cc/api/series/get-embed'
        self.DEFAULT_ICON_URL = 'https://zerion.cc/assets/img/logo.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

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

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, cItem):
        printDBG("Zerioncc.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'list_sort', 'title': _('Series'), 'url': self.getFullUrl('/seriale')},
#                        {'category': 'list_items', 'title': _('Children'), 'url': self.getFullUrl('/dla-dzieci/')},
#                        {'category':'list_years',     'title': _('Movies by year'), 'url':self.MAIN_URL},
                        {'category': 'list_cats', 'title': _('Genres'), 'url': self.getFullUrl('/seriale')},
#                        {'category':'list_az',        'title': _('Alphabetically'), 'url':self.MAIN_URL},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    ###################################################
    def _fillMovieFilters(self, cItem):
        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        # fill sort
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<select class="sort"', '</select>', False)[1]
        dat = re.compile('<option[^>]+?value="([^"]+?)".*?>(.+?)<').findall(dat)
        for item in dat:
            self.cacheMovieFilters['sort'].append({'title': self.cleanHtmlStr(item[1]), 'sort': item[0]})

#        sts, data = self.getPage(self.MAIN_URL)
#        if not sts: return

        # fill cats
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<div class="genres"', '</ul>', False)[1]
        dat = re.compile('<li[^>]+?data-num="([^"]+?)".*?>(.+?)</li>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['cats'].append({'title': self.cleanHtmlStr(item[1]), 'genres': item[0]})

        # fill years
#        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="dropdown-menu year-dropdown"', '</ul>', False)[1]
#        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(dat)
#        for item in dat:
#            self.cacheMovieFilters['years'].append({'title': self.cleanHtmlStr(item[1]), 'url': self.getFullUrl(item[0])})

        # fill az
#        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class=starting-letter>', '</ul>', False)[1]
#        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(dat)
#        for item in dat:
#            self.cacheMovieFilters['az'].append({'title': self.cleanHtmlStr(item[1]), 'url': self.getFullUrl(item[0])})

    ###################################################
    def listMovieFilters(self, cItem, category):
        printDBG("Zerioncc.listMovieFilters")

        filter = cItem['category'].split('_')[-1]
        self._fillMovieFilters(cItem)
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = []
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)

    def listsTab(self, tab, cItem, category=None):
        printDBG("Zerioncc.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("Zerioncc.listItems %s" % cItem)
        page = cItem.get('page', 1)

        url = cItem['url']
        sort = cItem.get('sort', '')
        genres = cItem.get('genres', '')
        if sort != '':
            url = url + '?sort=' + sort
        if genres != '':
            url = url + '&gen=' + genres

        if '?' in url:
            url += '&'
        else:
            url += '?'
        if page > 1:
            url = url + 'page={0}'.format(page)

        sts, data = self.getPage(url)
        if not sts:
            return
#        printDBG("Zerioncc.listItems data %s" % data)
        self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('<footer', '>'))[1]
        if '' != self.cm.ph.getSearchGroups(nextPage, 'page=(%s)[^0-9]' % (page + 1))[0]:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'poster'), ('</li', '>'))

        for item in data:
#            printDBG("Zerioncc.listItems item %s" % item)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h2', '>', 'title'), ('</h2', '>'))[1])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            # title = ensure_str(self.cm.ph.getSearchGroups(item, '''title=['"]([^"^']+?)['"]''')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'desc'), ('</p', '>'))[1])
            # if desc == '':
                # desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'description'), ('</div', '>'), False)[1])
# #            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'quality-version'), ('</div', '>'), False)[1])
            # year = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'rate'), ('</div', '>'), False)[1])
            # if year != '':
                # desc = _('Year: ') + year + '[/br]' + desc
            params = {'good_for_fav': True, 'category': 'list_seasons', 'url': url, 'title': title, 'desc': desc, 'icon': icon}
            self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSeriesSeasons(self, cItem, nextCategory):
        printDBG("Zerioncc.listSeriesSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        serieDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h2', '>', 'title'), ('</h2', '>'))[1])
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'seasons'), ('<footer', '>'))[1]
        data = data.split('<div class="season"')

        for sItem in data:
#            printDBG("Zerioncc.listSeriesSeasons item %s" % sItem)
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(sItem, ('<div', '>', 'title-text'), ('</div', '>'))[1])
            if not sTitle:
                continue
            sItem = self.cm.ph.getAllItemsBeetwenNodes(sItem, ('<li', '>'), ('</li', '>'))
            tabItems = []
            for item in sItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                if not url:
                    continue
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h4', '>', 'title'), ('</h4', '>'))[1])
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
                desc = self.cleanHtmlStr(item)
                tabItems.append({'title': '%s' % title, 'url': url, 'icon': icon, 'desc': desc})
            if len(tabItems):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 'episodes': tabItems, 'icon': cItem['icon'], 'desc': serieDesc})
                self.addDir(params)

    def listSeriesEpisodes(self, cItem):
        printDBG("Zerioncc.listSeriesEpisodes [%s]" % cItem)
        episodes = cItem.get('episodes', [])
        cItem = dict(cItem)
        for item in episodes:
            self.addVideo(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Zerioncc.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/szukaj?query=%s') % urllib_quote_plus(searchPattern)
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("Zerioncc.getLinksForVideo [%s]" % cItem)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])

        cUrl = cItem['url']
        url = cItem['url']

        retTab = []

        params['header']['Referer'] = cUrl
        sts, data = self.getPage(url, params)
#        printDBG("Zerioncc.getLinksForVideo data[%s]" % data)
        if not sts:
            return []

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)
        csrfToken = self.cm.ph.getSearchGroups(data, '''var\s_csrf\s=\s['"]([^"^']+?)['"]''')[0]
        sithc = self.cm.ph.getSearchGroups(data, '''var\ssithc\s=\s['"]([^"^']+?)['"]''')[0]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<table', '>'), ('</table', '>'))

        for tItem in data:
#            printDBG("Zerioncc.getLinksForVideo tItem[%s]" % tItem)
            tmp = self.cm.ph.getAllItemsBeetwenNodes(tItem, ('<tr', '>'), ('</tr', '>'))
            lang = self.cm.ph.getSearchGroups(tItem, '''data-key=['"]([^"^']+?)['"]''')[0]
            for item in tmp:
#                printDBG("Zerioncc.getLinksForVideo item[%s]" % item)
                if 'data-id' not in item:
                    continue
                data_id = self.cm.ph.getSearchGroups(item, '''data-id=['"]([^"^']+?)['"]''')[0]
                name = self.cleanHtmlStr(item).replace('Oglądaj', '') + '[%s]' % lang
                post_data = {'id': data_id}
                params['header']['X-CSRF-Token'] = csrfToken
                sts, data = self.getPage(self.MAIN_API_URL, params, post_data)
                printDBG("Zerioncc.getLinksForVideo data[%s]" % data)
                if not sts:
                    continue
                if '"captcha":true' in data:
                    token, errorMsgTab = self.processCaptcha(sithc, cUrl, captchaType="cf_re")
                    if token != '':
                        post_data_cf = {'hres': token}
                        sts, data = self.getPage('https://zeriun.cc/api/link/validate-captcha', params, post_data_cf)
                        printDBG("Zerioncc.getLinksForVideo data cf[%s]" % data)
                        sts, data = self.getPage(self.MAIN_API_URL, params, post_data)
                        printDBG("Zerioncc.getLinksForVideo data[%s]" % data)

                playerUrl = self.cm.ph.getSearchGroups(data, '''['"]url['"]:['"]([^"^']+?)['"]''')[0]
                if playerUrl == '':
                    continue
                retTab.append({'name': name, 'url': strwithmeta(playerUrl, {'Referer': url}), 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("Zerioncc.getVideoLinks [%s]" % baseUrl)
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
#            rm(self.COOKIE_FILE)
            self.listMainMenu({'name': 'category'})
        elif 'list_cats' == category:
            self.listMovieFilters(self.currItem, 'list_sort')
        elif 'list_years' == category:
            self.listMovieFilters(self.currItem, 'list_sort')
        elif 'list_az' == category:
            self.listMovieFilters(self.currItem, 'list_sort')
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
        CHostBase.__init__(self, Zerioncc(), True, [])
