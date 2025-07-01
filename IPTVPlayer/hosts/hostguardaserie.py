# -*- coding: utf-8 -*-
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return 'https://guardaserie.kaufen'


class GuardaSerie(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'GuardaSerie'})
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER}
        self.MAIN_URL = 'https://guardaserie.kaufen'
        self.DEFAULT_ICON_URL = self.getFullUrl('/templates/guardaseriecool/images/logo5.png')
        self.MENU = [
            {'category': 'list_items', 'title': _('Series'), 'url': self.getFullUrl('/serie-tv-archive/')},
            {'category': 'list_genres', 'title': _('Genres')},
            {'category': 'search', 'title': _('Search'), 'search_item': True, },
            {'category': 'search_history', 'title': _('Search history'), }]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listItems(self, cItem, nextCategory='video'):
        printDBG("GuardaSerie.listItems |%s|" % cItem)
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'href="([^"]+)">Avanti')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="list', '</div>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_seasons', 'title': title.replace(' streaming guardaserie', ''), 'url': url, 'icon': icon, 'desc': ''})
            self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("GuardaSerie.listSeasons |%s|" % cItem)
        url = cItem['url']
        icon = cItem['icon']
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0])
        data = re.findall(r'href="#[^"]+" data-toggle="tab">([^<]+)', data, re.DOTALL)
        if not data:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'video', 'title': cItem['title'], 'url': self.getFullUrl(url), 'icon': icon, 'desc': desc})
            self.addVideo(params)
        else:
            for seasons in data:
                title = '%s - %s %s' % (cItem['title'], _('Season'), seasons)
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'list_episodes', 'title': title, 'url': url, 'icon': icon, 'desc': desc, 'seasons': seasons})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("GuardaSerie.listEpisodes |%s|" % cItem)
        url = cItem['url']
        seasons = cItem['seasons']
        icon = cItem['icon']
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="season-%s' % seasons, '</ul>')[0]
        data = re.findall(r'>(\d+)<', data, re.DOTALL)
        for episode in data:
            title = '%s - %s %s' % (cItem['title'], _('episodes'), episode)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc, 'seasons': seasons, 'episode': episode})
            self.addVideo(params)

    def listValue(self, cItem, v):
        printDBG("GuardaSerie.Value |%s|" % cItem)
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '>%s<' % v, '</ul>')
        data = re.findall('href="([^"]+).*?>([^<]+)', data[0], re.DOTALL)
        for url, title in data:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'url': self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GuardaSerie.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem['url'] = self.getFullUrl('index.php?do=search&subaction=search&story=%s' % urllib_quote(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("GuardaSerie.getLinksForVideo [%s]" % cItem)
        urlTab = []
        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'data-num="%sx%s' % (cItem.get('seasons'), cItem.get('episode')), '</div>')[0]
        data = re.findall('data-link="([^"]+)', data, re.DOTALL)
        for url in data:
            urlTab.append({'name': self.up.getHostName(url).capitalize(), 'url': strwithmeta("https:" + url if url.startswith('//') else url, {'Referer': self.MAIN_URL}), 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, url):
        printDBG("GuardaSerie.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("GuardaSerie.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        desc = self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+')[0]
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
            self.listItems(self.currItem)
        elif 'list_seasons' == category:
            self.listSeasons(self.currItem)
        elif 'list_episodes' == category:
            self.listEpisodes(self.currItem)
        elif 'list_genres' == category:
            self.listValue(self.currItem, 'GENERI')
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
        CHostBase.__init__(self, GuardaSerie(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
