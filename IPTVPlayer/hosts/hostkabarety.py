# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
###################################################
# FOREIGN import
###################################################
from copy import deepcopy
try:
    import json
except Exception:
    import simplejson as json
###################################################


def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return 'http://kabaret.tworzymyhistorie.pl/'


class Kabarety(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kabaret.tworzymyhistorie.pl', 'cookie': 'kabarettworzymyhistoriepl.cookie'})
        self.DEFAULT_ICON_URL = 'http://m.ocdn.eu/_m/3db4aef7dfc39ec1230c837335a6ddfe,10,19,0.jpg'
        self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = 'http://kabaret.tworzymyhistorie.pl/'
        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_filters', 'title': _('Main'), 'url': self.getFullUrl('kabarety/')},
                             {'category': 'list_popular', 'title': _('Popular'), 'url': self.getFullUrl('kabarety/')},
                             {'category': 'list_all', 'title': _('All'), 'url': self.getFullUrl('kabarety/')},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)

        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data

    def getFullIconUrl(self, url):
        url = url.replace('&amp;', '&')
        return CBaseHostClass.getFullIconUrl(self, url)

    def getFullUrl(self, url):
        url = url.replace('&amp;', '&')
        return CBaseHostClass.getFullUrl(self, url)

    def fillCacheFilters(self, cItem):
        printDBG("Kabarety.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        def addFilter(data, marker, baseKey, addAll=True, titleBase=''):
            key = 'f_' + baseKey
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, marker + '''="([^"]+?)"''')[0]
                if value == '':
                    continue
                title = self.cleanHtmlStr(item)
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if addAll:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                self.cacheFiltersKeys.append(key)

        # type
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Rodzaj:', '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        addFilter(tmp, 'value', 'type', False)

        # sort
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Sortuj według:', '</select>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
        addFilter(tmp, 'value', 'sort', False)

        # add order to f_sort filter
        orderLen = len(self.cacheFilters['f_sort'])
        for idx in range(orderLen):
            item = deepcopy(self.cacheFilters['f_sort'][idx])
            # desc
            self.cacheFilters['f_sort'][idx].update({'title': '\xe2\x86\x93 ' + self.cacheFilters['f_sort'][idx]['title'], 'f_order': 'desc'})
            # asc
            item.update({'title': '\xe2\x86\x91 ' + item['title'], 'f_order': 'asc'})
            self.cacheFilters['f_sort'].append(item)

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("Kabarety.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters(cItem)

        if 0 == len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listCategory(self, cItem, idx, nextCategory):
        printDBG("Kabarety.listCategory")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        m1 = '<div class="rborder">'
        if idx == 0:
            data = self.cm.ph.getDataBeetwenMarkers(data, m1, m1)[1]
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, 'WSZYSTKIE</p>', '<div class="fright', False)[1]

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url})
            params['category'] = nextCategory
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("Kabarety.listItems")
        perPage = 99
        page = cItem.get('page', 0)
        baseUrl = 'index/exec/load.php?tod=skecze_lista&title='

        baseUrl += '&typ={0}'.format(cItem.get('f_type', ''))
        baseUrl += '&sort={0}'.format(cItem.get('f_sort', ''))
        baseUrl += '&order={0}'.format(cItem.get('f_order', ''))
        baseUrl += '&limit={0}'.format(page * perPage)
        baseUrl += '&count={0}'.format(perPage)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        cat = self.cm.ph.getSearchGroups(data, '<div class="load"[^>]+?name="([^"]+?)"')[0]
        baseUrl += '&cat={0}'.format(cat)

        HEADER = dict(self.AJAX_HEADER)
        HEADER['Referer'] = cItem['url']

        sts, data = self.getPage(self.getFullUrl(baseUrl), {'header': HEADER})
        if not sts:
            return

        printDBG(data)

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="video', 'class="ico_play">')
        num = 0
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                continue

            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            title = self.cleanHtmlStr(item)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'desc': '', 'icon': icon})
            self.addVideo(params)
            num += 1

        if num >= perPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Kabarety.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        sts, data = self.getPage(self.getFullUrl('szukaj'), post_data={'szukaj': searchPattern})
        if not sts:
            return

        if searchType == 'sketches':
            m = '<div class="div_szukaj_video div_szukaj', '<input type="hidden"'
        elif searchType == 'interviews':
            m = '<div class="div_szukaj_wywiady div_szukaj', '<input type="hidden"'
        else:
            m = '<div class="div_szukaj_kabarety div_szukaj', '<input type="hidden"'

        data = self.cm.ph.getDataBeetwenMarkers(data, m[0], m[1])[1]

        if searchType in ['sketches', 'interviews']:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="video', 'class="ico_play">')
        else:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<h1', '</h1>')

        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            if not self.cm.isValidUrl(url):
                continue

            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            title = self.cleanHtmlStr(item)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'desc': '', 'icon': icon})
            if searchType in ['sketches', 'interviews']:
                self.addVideo(params)
            else:
                params['category'] = 'list_filters'
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("Kabarety.getLinksForVideo [%s]" % cItem)
        urlTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"](https?://[^"^']+?)['"]''', 1, True)[0]
        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(self.getFullUrl(videoUrl))

        if 0 == len(urlTab):
            videoUrl = self.cm.ph.getSearchGroups(data, '''<div class="fb-video"[^>]+?data-href=['"](https?://[^"^']+?)['"]''', 1, True)[0]
            if self.cm.isValidUrl(videoUrl):
                urlTab = self.up.getVideoLinkExt(self.getFullUrl(videoUrl))

        if 0 == len(urlTab):
            videoId = self.cm.ph.getSearchGroups(cItem['url'], '''\.pl/([0-9]+?)_''', 1, True)[0]
            if videoId != '':
                HEADER = dict(self.AJAX_HEADER)
                HEADER['Referer'] = cItem['url']

                url = self.getFullUrl('index/exec/load.php?tod=vidplay&name=' + videoId)
                sts, data = self.getPage(url, {'header': HEADER})
                if sts:
                    videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"](https?://[^"^']+?)['"]''', 1, True)[0]
                    if self.cm.isValidUrl(videoUrl):
                        urlTab = self.up.getVideoLinkExt(self.getFullUrl(videoUrl))

        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('Kabarety.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('Kabarety.getLinksForFavourite')
        if self.MAIN_URL == None:
            self.selectDomain()
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('Kabarety.setInitListFromFavouriteItem')
        if self.MAIN_URL == None:
            self.selectDomain()
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.cacheLinks = {}
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_popular':
            self.listCategory(self.currItem, 0, 'list_filters')
        elif category == 'list_all':
            self.listCategory(self.currItem, 1, 'list_filters')
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, Kabarety(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append(('Skecze', "sketches"))
        searchTypesOptions.append(('Kabarety', "cabarets"))
        searchTypesOptions.append(('Wywiady', "interviews"))
        return searchTypesOptions
