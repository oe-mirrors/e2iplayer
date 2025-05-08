# -*- coding: utf-8 -*-
import re
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return 'https://einschalten.in'


class Einschalten(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'einschalten', 'cookie': 'einschalten.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.MAIN_URL = None

    def menu(self):
        self.MAIN_URL = 'https://einschalten.in'
        self.MENU = [
                    {'category': 'list_items', 'title': _("Movies"), 'link': self.getFullUrl('/movies')},
                    {'category': 'list_items', 'title': "Zuletzt hinzugefügte Filme", 'link': self.getFullUrl('/movies?order=added')},
                    {'category': 'list_items', 'title': "Sammlungen", 'link': self.getFullUrl('/collections')},
                    {'category': 'list_genres', 'title': 'Genres'},
                    {'category': 'search', 'title': _('Search'), 'search_item': True, },
                    {'category': 'search_history', 'title': _('Search history'), }]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def listItems(self, cItem, nextCategory):
        printDBG("Einschalten.listItems |%s|" % cItem)
        url = cItem['link']
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'items-center" href="([^"]+)"><span>Weiter')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="group', '</a>')
        for item in data:
            link = self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0]
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'img src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'link': link, 'icon': icon})
            if '/collections' in link:
                params.update({'category': 'list_items', 'link': self.getFullUrl(link)})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            nextPage = url.split("?")[0] + "?" + nextPage.split("?")[1]
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'link': self.getFullUrl(nextPage)})
            self.addDir(params)

    def listGenres(self, cItem):
        printDBG("Einschalten.Genres")
        url = self.getFullUrl('/movies')
        sts, data = self.getPage(url)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<select id="genre', '</select>')[0]
        data = re.compile('value="([^"]+).*?>([^<]+)', re.DOTALL).findall(data)
        for link, title in data:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'link': url + "?genre=%s" % link})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Einschalten.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['link'] = self.getFullUrl('/search?query=%s' % urllib_quote(searchPattern))
        self.listItems(cItem, 'video')

    def getLinksForVideo(self, cItem):
        printDBG("Einschalten.getLinksForVideo [%s]" % cItem)
        linksTab = []
        url = self.getFullUrl("/api%s/watch" % cItem['link'])
        sts, data = self.getPage(url, self.defaultParams)
        if not sts:
            return []
        data = re.compile('streamUrl":"([^"]+)', re.DOTALL).findall(data)
        for url in data:
            if url.startswith('//'):
                url = "https:" + url
            title = urlparse(url).netloc.split('.')[0]
            linksTab.append({'name': title.capitalize(), 'url': url, 'need_resolve': 1})
        if linksTab:
            cItem['url'] = linksTab
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("Einschalten.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("Einschalten.getArticleContent [%s]" % cItem)
        sts, data = self.getPage(self.getFullUrl(cItem['link']))
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'description" content="([^"]+)')[0])
        desc = desc if desc else cItem.get('desc', '')
        title = cItem['title']
        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc)}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.menu()
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {'name': 'category'})
        elif 'list_items' == category:
            self.listItems(self.currItem, 'video')
        elif 'list_episodes' == category:
            self.listEpisodes(self.currItem)
        elif 'list_genres' == category:
            self.listGenres(self.currItem)
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
        CHostBase.__init__(self, Einschalten(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
