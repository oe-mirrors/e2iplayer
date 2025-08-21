# -*- coding: utf-8 -*-
# Last Modified: 29.06.2025
import base64
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return 'https://9anime.com.ro'


class AnimeRo(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'AnimeRo'})
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER}
        self.MAIN_URL = 'https://9anime.com.ro'
        self.DEFAULT_ICON_URL = self.getFullUrl('/wp-content/uploads/2024/07/9anime-logo.png')
        self.MENU = [
            {'category': 'list_AZ', 'title': "A-Z", 'url': self.getFullUrl('anime-tv/')},
            {'category': 'search', 'title': _('Search'), 'search_item': True, }] + self.serchHistorItems()

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listItems(self, cItem, nextCategory):
        printDBG("AnimeRo.listItems |%s|" % cItem)
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'href="([^"]+)">Next')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="bsx"', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'epx">([^<]+)')[0])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_episodes', 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': self.getFullUrl(nextPage)})
            self.addDir(params)

    def listAZ(self, cItem):
        printDBG("AnimeRo.AZ")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'footer-az"', '</div>')[0]
        data = re.compile(' href="([^"]+)">([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'url': self.getFullUrl(url)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("AnimeRo.listEpisodes")
        url = cItem['url']
        icon = cItem['icon']
        sts, data = self.getPage(url)
        if not sts:
            return

        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="episodes-container"', 'div class')
        data = re.compile(r'href="([^"]+)">([^<]+)', re.DOTALL).findall(data[0])
        for url, ep in data:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': cItem['title'] + " - Episode " + ep, 'url': url, 'icon': icon, 'desc': desc})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AnimeRo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/?s=%s' % urllib_quote(searchPattern))
        self.listItems(cItem, 'video')

    def getLinksForVideo(self, cItem):
        printDBG("AnimeRo.getLinksForVideo [%s]" % cItem)
        urlTab = []
        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="mirror"', '</select>')[0]
        data = re.compile('value="([^"]+)', re.DOTALL).findall(data)
        for url in data:
            url = base64.b64decode(url)
            url = self.cleanHtmlStr(self.cm.ph.getSearchGroups(url, 'src="([^"]+)')[0])
            urlTab.append({'name': self.up.getHostName(url).capitalize(), 'url': strwithmeta("https:" + url if url.startswith('//') else url, {'Referer': self.MAIN_URL}), 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, url):
        printDBG("AnimeRo.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("AnimeRo.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        desc = self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0]
        desc = desc if desc else cItem.get('desc', '')
        title = cItem['title']
        icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        return [{'title': title, 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.menu()
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {'name': 'category'})
        elif 'list_items' == category:
            self.listItems(self.currItem, 'video')
        elif 'list_episodes' == category:
            self.listEpisodes(self.currItem)
        elif 'list_AZ' == category:
            self.listAZ(self.currItem)
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
        CHostBase.__init__(self, AnimeRo(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
