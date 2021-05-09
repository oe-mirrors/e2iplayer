# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir, byteify
###################################################

###################################################
# FOREIGN import
###################################################
import copy
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://ustream.tv/'


class UstreamTV(CBaseHostClass):
    MAIN_URL = 'https://www.ustream.tv/'
    SRCH_URL = MAIN_URL + 'search?q='
    DEFAULT_ICON_URL = 'http://occopwatch-com.secure40.ezhostingserver.com/wp-content/uploads/2013/10/ustream-logo.jpg'

    MAIN_CAT_TAB = [{'category': 'items', 'title': _('Popular'), 'icon': DEFAULT_ICON_URL, 'cat_id': 'all', 'filters': {'subCategory': '', 'type': 'no-offline', 'location': 'anywhere'}},
                    {'category': 'categories', 'title': _('Categories'), 'icon': DEFAULT_ICON_URL, 'filters': {}},
                    {'category': 'search', 'title': _('Search'), 'icon': DEFAULT_ICON_URL, 'search_item': True},
                    {'category': 'search_history', 'title': _('Search history'), 'icon': DEFAULT_ICON_URL}
                   ]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'UstreamTV', 'cookie': 'UstreamTV.cookie'})
        self.cacheFilters = {}

    def _getFullUrl(self, url):
        mainUrl = self.MAIN_URL
        if 0 < len(url) and not url.startswith('http'):
            url = mainUrl + url
        if not mainUrl.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url

    def fillFilters(self, url):
        printDBG("UstreamTV.fillFilters")
        self.cacheFilters = {}
        sts, data = self.cm.getPage(url)
        if not sts:
            return
        filtersTab = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="control-select">', '</select>', False)
        for filterData in filtersTab:
            filterName = self.cm.ph.getSearchGroups(filterData, 'view-data-key="([^"]+?)"')[0]
            if '' == filterName:
                filterName = self.cm.ph.getSearchGroups(filterData, 'name="([^"]+?)"')[0]

            filterData = re.compile('<option value="([^"]*?)"[^>]*?>([^<]+?)</option>').findall(filterData)
            self.cacheFilters[filterName] = []
            for item in filterData:
                self.cacheFilters[filterName].append({'title': self.cleanHtmlStr(item[1]), 'value': item[0]})
        #printDBG("KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK [%s]" % )

    def listFilters(self, cItem, filterName, category):
        self.cacheFilters = {}
        if self.cacheFilters == {}:
            url = self.buildUrl(cItem)
            self.fillFilters(url)
        tab = self.cacheFilters.get(filterName, [])

        for item in tab:
            params = copy.deepcopy(cItem)
            params['category'] = category
            params['title'] = item['title']
            params['filters'][filterName] = item['value']
            self.addDir(params)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("UstreamTV.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if type == 'dir':
                self.addDir(params)
            else:
                self.addVideo(params)

    def buildUrl(self, cItem):
        if 'q' in cItem:
            return self.SRCH_URL + cItem['q']
        cat_id = cItem['cat_id']
        url = self.MAIN_URL + 'explore/%s/all' % (cat_id)
        return url.replace('/all/all', '/all')

    def buildJsonUrl(self, cItem):
        if 'q' in cItem:
            cat_id = cItem['q']
            url = self.MAIN_URL + 'ajax/search.json?q=%s&category=%s&type=%s&location=%s'
            catFilterName = 'category'
        else:
            cat_id = cItem['cat_id']
            url = self.MAIN_URL + 'ajax-alwayscache/explore/%s/all.json?subCategory=%s&type=%s&location=%s'
            catFilterName = 'subCategory'
        filters = cItem.get('filters', {})
        page = cItem.get('page', 1)
        url = url % (cat_id, filters.get(catFilterName, ''), filters.get('type', ''), filters.get('location', ''))
        if page > 1:
            url += '&page=%s' % page
        return url

    def listCategories(self, cItem, category):
        printDBG("UstreamTV.listCategories")
        sts, data = self.cm.getPage(self.MAIN_URL + 'explore/all')
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="submenu-column half-width-links">', '<form', False)[1]
        data = re.compile('<a href="[^"]*?/explore/([^"]+?)"[^>]*?>([^<]+?)<').findall(data)
        #data = re.compile('<a[^>]*?/([^/]+?)\.json[^>]*?>([^<]+?)<').findall(data)
        for item in data:
            if item[0] == 'all':
                continue
            params = dict(cItem)
            params.update({'category': category, 'title': self.cleanHtmlStr(item[1]), 'cat_id': item[0]})
            self.addDir(params)

    def listRegular(self, cItem):
        printDBG("UstreamTV.listItems")
        url = self.buildJsonUrl(cItem)
        self.listItems(cItem, url)

    def listItems(self, cItem, url):
        printDBG("UstreamTV.listItems")
        sts, data = self.cm.getPage(url)
        if not sts:
            return

        nextPage = False
        try:
            data = byteify(json.loads(data))
            if not data['success']:
                return
            nextPage = data['pageMeta']['infinite']
            data = data['pageContent']
            data = data.split('<div class="item media-item">')
            del data[0]
            for item in data:
                params = dict(cItem)
                url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
                title = self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0]
                icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
                desc = self.cleanHtmlStr(item)
                params.update({'title': self.cleanHtmlStr(title), 'icon': self._getFullUrl(icon), 'desc': desc, 'url': self._getFullUrl(url)})
                self.addVideo(params)
        except Exception:
            printExc()

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': cItem.get('page', 1) + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib.quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['q'] = urllib.quote_plus(searchPattern)
        cItem['filters'] = {}
        self.listFilters(cItem, 'category', 'filter_type')

    def getLinksForVideo(self, cItem):
        printDBG("UstreamTV.getLinksForVideo [%s]" % cItem)
        urlTab = []
        tmp = self.up.getVideoLinkExt(cItem['url'])
        for item in tmp:
            item['need_resolve'] = 0
            urlTab.append(item)
        return urlTab

    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'categories':
            self.listCategories(self.currItem, 'filter_subCategory')
    # FILTERS
        elif category == 'filter_subCategory':
            self.listFilters(self.currItem, 'subCategory', 'filter_type')
        elif category == 'filter_type':
            self.listFilters(self.currItem, 'type', 'filter_location')
        elif category == 'filter_location':
            self.listFilters(self.currItem, 'location', 'items')
    #ITEMS
        elif category == 'items':
            self.listRegular(self.currItem)
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
        CHostBase.__init__(self, UstreamTV(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('ustreamtvlogo.png')])

    def getLinksForVideo(self, Index=0, selItem=None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)

        urlList = self.host.getLinksForVideo(self.host.currList[Index])
        for item in urlList:
            retlist.append(CUrlItem(item["name"], item["url"], item['need_resolve']))

        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo

    def converItem(self, cItem):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie

        hostLinks = []
        type = CDisplayListItem.TYPE_UNKNOWN
        possibleTypesOfSearch = None

        if 'category' == cItem['type']:
            if cItem.get('search_item', False):
                type = CDisplayListItem.TYPE_SEARCH
                possibleTypesOfSearch = searchTypesOptions
            else:
                type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'video':
            type = CDisplayListItem.TYPE_VIDEO
        elif 'more' == cItem['type']:
            type = CDisplayListItem.TYPE_MORE
        elif 'audio' == cItem['type']:
            type = CDisplayListItem.TYPE_AUDIO

        if type in [CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_VIDEO]:
            url = cItem.get('url', '')
            if '' != url:
                hostLinks.append(CUrlItem("Link", url, 1))

        title = cItem.get('title', '')
        description = cItem.get('desc', '')
        icon = cItem.get('icon', '')

        return CDisplayListItem(name=title,
                                    description=description,
                                    type=type,
                                    urlItems=hostLinks,
                                    urlSeparateRequest=1,
                                    iconimage=icon,
                                    possibleTypesOfSearch=possibleTypesOfSearch)
    # end converItem

    def getSearchItemInx(self):
        try:
            list = self.host.getCurrList()
            for i in range(len(list)):
                if list[i]['category'] == 'search':
                    return i
        except Exception:
            printDBG('getSearchItemInx EXCEPTION')
            return -1

    def setSearchPattern(self):
        try:
            list = self.host.getCurrList()
            if 'history' == list[self.currIndex]['name']:
                pattern = list[self.currIndex]['title']
                search_type = list[self.currIndex]['search_type']
                self.host.history.addHistoryItem(pattern, search_type)
                self.searchPattern = pattern
                self.searchType = search_type
        except Exception:
            printDBG('setSearchPattern EXCEPTION')
            self.searchPattern = ''
            self.searchType = ''
        return
