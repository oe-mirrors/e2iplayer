# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
###################################################

###################################################


def gettytul():
    return 'http://interia.tv/'


class InteriaTv(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'interia.tv', 'cookie': 'interia.tv.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://interia.tv/'
        self.DEFAULT_ICON_URL = 'http://static.wirtualnemedia.pl/media/top/interia-2015logohaslo-655.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.searchFiltersData = []

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem, nextCategory1, nextCategory2):
        printDBG("InteriaTv.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>'), ('</nav', '>'))[1]
            data = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(data)
            if len(data) > 1:
                try:
                    cTree = self.listToDir(data[1:-1], 0)[0]
                    params = dict(cItem)
                    params['c_tree'] = cTree['list'][0]
                    params['category'] = nextCategory1
                    self.listCategories(params, nextCategory2)
                except Exception:
                    printExc()

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]

        params = dict(cItem)
        params.update({'type': 'category', 'good_for_fav': False, 'category': nextCategory2, 'title': 'TOP TYGODNIA', 'url': self.getFullUrl('/top-tygodnia')})
        if len(self.currList):
            self.currList[0] = params
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory):
        printDBG("InteriaTv.listCategories")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(item['dat']) #self.cm.ph.getDataBeetwenNodes(item['dat'], ('<div', '>', 'title'), ('</div', '>'))[1]
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                if 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                        self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'c_tree': item['list'][0], 'title': title, 'url': url})
                    self.addDir(params)
        except Exception:
            printExc()

    def listSort(self, cItem, nextCategory):
        printDBG("InteriaTv.listSort")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'list-has-switch'), ('</div', '>'), False)[1]
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<strong', '</strong>')[1])
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for item in tmp:
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                url = cItem['url']
            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'desc': desc}
            self.addDir(params)

        if len(self.currList) < 2:
            self.currList = []
            params = dict(cItem)
            params['category'] = 'list_items'
            self.listItems(params, 'list_playlist_items', data)

    def listItems(self, cItem, nextCategory, data=None):
        printDBG("InteriaTv.listItems [%s]" % cItem)
        page = cItem.get('page', 1)

        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(nextPage, ('<li', '>', 'next'), ('</li', '>'), False)[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^"^']+?)['"]''')[0])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'list-items'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<section', '>'), ('</section', '>'), False)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            # title
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<strong', '</strong>')[1])
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'stat'), ('</p', '>'))[1])
            if tmp != '':
                title += ' (%s)' % tmp
            # desc
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'datetime'), ('</div', '>'))[1])
            if '' != desc:
                desc += '[/br]'
            desc += self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'description'), ('</p', '>'))[1])

            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            if 'stat count' in item:
                self.addDir(params)
            else:
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1, 'url': nextPage})
            self.addDir(params)

    def listSearchItems(self, cItem, nextCategory, data=None):
        printDBG("InteriaTv.listSearchItems [%s]" % cItem)
        page = cItem.get('page', 1)

        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(nextPage, ('<li', '>', 'next'), ('</li', '>'), False)[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^"^']+?)['"]''')[0])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'search-results'), ('<div', '>', 'content'))[1]
        data = re.compile('''<div[^>]+?thumbnail[^>]+?>''').split(data)
        if len(data):
            del data[0]
        if len(data) and nextPage != '':
            data[-1] = re.compile('''<div[^>]+?pagination[^>]+?>''').split(data[-1], 1)[0]

        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            # title
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h', '>', 'title'), ('</h', '>'), False)[1])
            tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'stat'), ('</p', '>'), False)[1])
            if tmp != '':
                title += ' (%s)' % tmp
            # desc
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<li', '>', 'date'), ('</li', '>'), False)[1])
            if '' != desc:
                desc += '[/br]'
            desc += self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', 'description'), ('</', '>'), False)[1])

            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            if 'stat count' in item:
                self.addDir(params)
            else:
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1, 'url': nextPage})
            self.addDir(params)

    def listPlaylistItems(self, cItem):
        printDBG("InteriaTv.listPlaylistItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'pack links'), ('</ul', '>'))
        for section in data:
            section = self.cm.ph.getAllItemsBeetwenNodes(section, ('<li', '>'), ('</li', '>'), False)
            for item in section:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
                desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'video-desc'), ('</span', '>'))[1])
                params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("InteriaTv.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/szukaj?q=') + urllib.quote_plus(searchPattern)

        sts, data = self.getPage(url)
        if not sts:
            return
        cUrl = data.meta['url']

        self.searchFiltersData = []
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul', '>', 'search-filters'), ('</ul', '>'), False)
        for idx in range(len(data)):
            tab = []
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(data[idx], '<li', '</li>')
            for item in tmp:
                title = self.cleanHtmlStr(item)
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                if url == '' and 'active' in item:
                    url = cUrl
                if url == '':
                    continue
                tab.append({'title': title, 'url': url})

            if len(tab):
                self.searchFiltersData.append(tab)
        if len(self.searchFiltersData):
            self.listSearchFilters({'name': 'category', 'type': 'category', 'category': 'search_filters', 'f_idx': 0}, 'list_search_items')

    def listSearchFilters(self, cItem, nextCategory):
        for idx in range(len(self.searchFiltersData[cItem['f_idx']])):
            item = self.searchFiltersData[cItem['f_idx']][idx]
            params = dict(cItem)
            params.update(item)
            params.update({'category': nextCategory, 'f_idx': cItem['f_idx'] + 1})
            if idx == 0 and cItem['f_idx'] + 1 < len(self.searchFiltersData):
                params['category'] = cItem['category']
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("InteriaTv.getLinksForVideo [%s]" % cItem)
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
        if name == None:
            self.listMainMenu({'name': 'category'}, 'list_categories', 'list_sort')
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_sort')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_playlist_items')
        elif category == 'list_playlist_items':
            self.listPlaylistItems(self.currItem)
    #SEARCH ITEMS
        elif category == 'search_filters':
            self.listSearchFilters(self.currItem, 'list_search_items')
        elif category == 'list_search_items':
            self.listSearchItems(self.currItem, 'list_playlist_items')
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
        CHostBase.__init__(self, InteriaTv(), True, [])
