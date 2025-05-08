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
    return 'https://kinokiste.cloud'


class KinoKiste(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kinokiste', 'cookie': 'kinokiste.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = 'https://kinokiste.cloud/templates/kkiste-de/images/logo12.png'
        self.MAIN_URL = None

    def menu(self):
        self.MAIN_URL = 'https://kinokiste.cloud'
        self.MENU = [
                    {'category': 'list_items', 'title': _("Movies"), 'link': self.getFullUrl('/aktuelle-kinofilme-im-kino')},
                    {'category': 'list_items', 'title': _("Series"), 'link': self.getFullUrl('/serienstream-deutsch')},
                    {'category': 'list_items', 'title': _("Animation"), 'link': self.getFullUrl('/animation')},
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
        printDBG("KinoKiste.listItems |%s|" % cItem)
        url = cItem['link']
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'<span\s+class="swchItem">\s*<a\s+href="([^"]+)">&raquo;</a>\s*</span>')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<section class="fl-item', '</section>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'st-desc">([^<]+)')[0])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'link': url, 'icon': icon, 'desc': desc})
            if 'taffel' in title or 'serie' in title:
                params.update({'category': 'list_episodes'})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage.startswith('https'):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'link': self.getFullUrl(nextPage)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("KinoKiste.listEpisodes")
        url = cItem['link']
        icon = cItem['icon']
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li id="serie', '</ul>')
        for item in data:
            episode = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '><a href="#">([^<]+)')[0])
            title = cItem['title'] + " - " + episode
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'link': url, 'icon': icon, 'desc': desc, 'episode': episode})
            self.addVideo(params)

    def listGenres(self, cItem):
        printDBG("KinoKiste.Genres")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'href="#">Kategorien', '</ul>')[0]
        data = re.compile('href="([^"]+)">([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            if 'ino' in title or 'rien' in title or 'chst' in title:
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title.replace(' stream', ''), 'link': self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KinoKiste.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['link'] = self.getFullUrl('index.php?do=search&subaction=search&story=%s' % urllib_quote(searchPattern))
        self.listItems(cItem, 'video')

    def getLinksForVideo(self, cItem):
        printDBG("KinoKiste.getLinksForVideo [%s]" % cItem)
        linksTab = []
        sts, data = self.getPage(cItem['link'], self.defaultParams)
        if not sts:
            return []
        if cItem.get('episode'):
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem.get('episode'), '</ul>')[0]
        data = re.compile('link="([^"]+)', re.DOTALL).findall(data)
        for url in data:
            if "vod/online" in url or "youtube" in url:
                continue
            if url.startswith('//'):
                url = "https:" + url
            title = urlparse(url).netloc.split('.')[0]
            linksTab.append({'name': title.capitalize(), 'url': url, 'need_resolve': 1})
        if linksTab:
            cItem['url'] = linksTab
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("KinoKiste.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("KinoKiste.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem['link'])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'description" content="([^"]+)')[0])
        desc = desc if desc else cItem.get('desc', '')
        actors = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, "Darsteller:(.*?)</span></p>")[0])
        if actors:
            otherInfo['actors'] = actors
        d = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, "Regisseur:(.*?)</span></p>")[0])
        if d:
            otherInfo['director'] = d
        released = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, "Jahr:(.*?)</span></p>")[0])
        if released:
            otherInfo['released'] = released
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, "Zeit:(.*?)</span></p>")[0])
        if duration:
            otherInfo['duration'] = duration
        title = cItem['title']
        icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

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
        CHostBase.__init__(self, KinoKiste(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
