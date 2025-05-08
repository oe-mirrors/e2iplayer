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
    return 'https://megakino.world'


class MegaKino(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'megakino', 'cookie': 'megakino.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.MAIN_URL = None

    def menu(self):
        self.MAIN_URL = 'https://megakino.world'
        self.MENU = [
                    {'category': 'list_items', 'title': _("Movies"), 'link': self.getFullUrl('/films')},
                    {'category': 'list_items', 'title': "Kino Filme", 'link': self.getFullUrl('/kinofilme')},
                    {'category': 'list_items', 'title': _("Series"), 'link': self.getFullUrl('/serials')},
                    {'category': 'list_items', 'title': _("Animation"), 'link': self.getFullUrl('/multfilm')},
                    {'category': 'list_items', 'title': "Dokumentationen", 'link': self.getFullUrl('/documentary')},
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
        printDBG("MegaKino.listItems |%s|" % cItem)
        url = cItem['link']
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'class="pagination.*?href="([^"]+)">\D')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="poster grid-item', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            # icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'src="([^"]+)')[0]) webp
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'line-clamp">([^<]+)')[0])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'link': url, 'desc': desc})
            if 'taffel' in title or 'documentary' in url:
                params.update({'category': 'list_episodes'})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage.startswith('https'):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'link': self.getFullUrl(nextPage)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("MegaKino.listEpisodes")
        url = cItem['link']
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<option value="e', '</option>')
        for item in data:
            episode = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'value="[^"]+">([^<]+)')[0])
            ep = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'value="([^"]+)')[0])
            title = cItem['title'] + " - " + episode
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'link': url, 'desc': desc, 'episode': ep})
            self.addVideo(params)

    def listGenres(self, cItem):
        printDBG("MegaKino.Genres")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'side-block__title">Genres</div>', '</ul>')[0]
        data = re.compile('href="([^"]+)">([^<]+)</a>', re.DOTALL).findall(data)
        for url, title in data:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'link': self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MegaKino.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['link'] = self.getFullUrl('index.php?do=search&subaction=search&story=%s' % urllib_quote(searchPattern))
        self.listItems(cItem, 'video')

    def getLinksForVideo(self, cItem):
        printDBG("MegaKino.getLinksForVideo [%s]" % cItem)
        linksTab = []
        sts, data = self.getPage(cItem['link'], self.defaultParams)
        if not sts:
            return []
        if cItem.get('episode'):
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="%s' % cItem.get('episode'), '</select>')[0]
            data = re.compile('value="([^"]+)', re.DOTALL).findall(data)
        else:
            data = re.compile('film_main" data-src="([^"]+)', re.DOTALL).findall(data)
        for url in data:
            if url.startswith('//'):
                url = "https:" + url
            title = urlparse(url).netloc.split('.')[0]
            linksTab.append({'name': title.capitalize(), 'url': url, 'need_resolve': 1})
        if linksTab:
            cItem['url'] = linksTab
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("MegaKino.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("Movie4K.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem['link'])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'description" content="([^"]+)')[0])
        desc = desc if desc else cItem.get('desc', '')
        title = cItem['title']
        return [{'title': self.cleanHtmlStr(title), 'text': desc}]

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
        CHostBase.__init__(self, MegaKino(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
