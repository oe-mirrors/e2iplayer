# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
import time
from binascii import hexlify
from hashlib import md5
###################################################


def gettytul():
    return 'https://andrija-i-andjelka.com/'


class AndrijaIAndjelka(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'andrija-i-andjelka.com', 'cookie': 'andrija-i-andjelka.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:56.0) Gecko/20100101 Firefox/56.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'pl,en-US;q=0.7,en;q=0.3', 'Accept-Encoding': 'gzip, deflate', 'Upgrade-Insecure-Requests': '1', 'Connection': 'keep-alive'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        self.MAIN_URL = 'https://andrija-i-andjelka.com/'
        #https://previews.123rf.com/images/yusufsangdes89/yusufsangdes891507/yusufsangdes89150700042/42557652-cinema-camera-icon-movie-lover-series-icon.jpg
        self.DEFAULT_ICON_URL = 'https://img00.deviantart.net/972b/i/2010/241/0/4/tv_series_icon_set_by_silentbang-d2xl0kj.jpg'

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'cookie_items': {}}
        self.timestam = 0

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        if 'cookie_items' in addParams:
            if self.timestam == 0:
                rm(self.COOKIE_FILE)
            timestamp = int(time.time())
            if timestamp > self.timestam:
                timestamp += 180
                hash = hexlify(md5(str(timestamp)).digest())
                addParams['cookie_items']['token'] = '%s,%s' % (timestamp, hash)

        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url, baseUrl=None):
        return CBaseHostClass.getFullIconUrl(self, url.replace('&amp;', '&'), baseUrl)

    def listMainMenu(self, cItem):
        printDBG("AndrijaIAndjelka.listMainMenu")

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        categories = []
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<li', '>', 'has-children'), ('</ul', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'name': 'category', 'category': 'list_items', 'title': title, 'url': url})
            categories.append(params)

        if len(categories):
            title = categories[0]['title']
            categories[0]['title'] = _('--All--')
            params = dict(cItem)
            params.update({'category': 'sub_items', 'title': title, 'sub_items': categories})
            self.addDir(params)

        MAIN_CAT_TAB = [{'category': 'list_items', 'title': 'NAJNOVIJE', 'url': self.getMainUrl()},
                        {'category': 'list_series', 'title': 'SERIJE', 'url': self.getFullUrl('serije/')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("AndrijaIAndjelka.listItems")
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>', 'pagination'), ('</nav', '>'), False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?/%s[^0-9][^'^"]*?)['"]''' % (page + 1))[0]

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>', 'post-'), ('</article', '>'), False)
        for item in data:
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g(?:\?[^'^"]*?)?)['"]''')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h', '>', 'title'), ('</h', '>'), False)[1])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon})
            self.addVideo(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listSeries(self, cItem, nextCategory):
        printDBG("AndrijaIAndjelka.listSeries")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<article', '>', 'post-'), ('</article', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<td', '</td>')
        for item in data:
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g(?:\?[^'^"]*?)?)['"]''')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AndrijaIAndjelka.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=') + urllib.quote_plus(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("AndrijaIAndjelka.getLinksForVideo [%s]" % cItem)
        urlTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return urlTab

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '</iframe>', caseSensitive=False)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''', 1, True)[0])
            if 1 == self.up.checkHostSupport(url):
                name = self.up.getHostName(url) #, nameOnly=True)
                url = strwithmeta(url, {'Referer': cItem['url']})
                urlTab.append({'name': name, 'url': url, 'need_resolve': 1})

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("AndrijaIAndjelka.getVideoLinks [%s]" % videoUrl)
        return self.up.getVideoLinkExt(videoUrl)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category', 'type': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_series':
            self.listSeries(self.currItem, 'list_items')
        elif category == 'sub_items':
            self.currList = self.currItem.get('sub_items', [])
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
        CHostBase.__init__(self, AndrijaIAndjelka(), True, favouriteTypes=[])
