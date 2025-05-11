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
    return 'https://streamcloud.my'


class StreamCloud(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'streamcloud', 'cookie': 'streamcloud.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = 'https://streamcloud.my/templates/streamcloud/images/192x192.png'
        self.MAIN_URL = None

    def menu(self):
        self.MAIN_URL = 'https://streamcloud.my'
        self.MENU = [
            {'category': 'list_items', 'title': 'Kinofilme', 'link': self.getFullUrl('/kinofilme/')},
            {'category': 'list_items', 'title': _("Film"), 'link': self.getFullUrl('/filme-stream/')},
            {'category': 'list_items', 'title': _("Series"), 'link': self.getFullUrl('/serien/')},
            {'category': 'list_items', 'title': "Top", 'link': self.getFullUrl('/beliebte-filme/')},
            {'category': 'list_genres', 'title': 'Genres'},
            {'category': 'list_year', 'title': 'Jahr'},
            {'category': 'list_country', 'title': 'Land'},
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
        printDBG("StreamCloud.listItems |%s|" % cItem)
        url = cItem['link']
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, 'href="([^"]+)">Next')[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="thumb', '</div>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+)')[0])
            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0]
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_seasons', 'title': self.cleanHtmlStr(title), 'link': url, 'icon': icon})
            self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'link': self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("StreamCloud.listSeasons")
        url = cItem['link']
        icon = cItem['icon']
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="tt_season">', '</ul>')
        if not data:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'video', 'title': cItem['title'], 'link': self.getFullUrl(url), 'icon': icon, 'desc': desc})
            self.addVideo(params)
        else:
            data = re.compile(r'"#season-(\d+)', re.DOTALL).findall(data[0])
            for seasons in data:
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'list_episodes', 'title': cItem['title'] + " - Staffel " + seasons, 'link': url, 'icon': icon, 'desc': desc, 'seasons': seasons})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("StreamCloud.listEpisodes")
        url = cItem['link']
        seasons = cItem['seasons']
        icon = cItem['icon']
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="season-%s' % seasons, '</ul>')[0]
        data = re.compile('data-title=".*?">([^<]+)', re.DOTALL).findall(data)
        for episode in data:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': cItem['title'] + " - Episode " + episode, 'link': url, 'icon': icon, 'desc': desc, 'seasons': seasons, 'episode': episode})
            self.addVideo(params)

    def listValue(self, cItem, v):
        printDBG("StreamCloud.Value")
        sts, data = self.getPage(self.MAIN_URL + "/streamcloud")
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, v, '</style>')[0]
        data = re.compile('href="([^"]+).*?>([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            if 'ino' in title or 'erien' in title or 'chst' in title:
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'link': self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("StreamCloud.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['link'] = self.getFullUrl('index.php?do=search&subaction=search&story=%s' % urllib_quote(searchPattern))
        self.listItems(cItem, 'video')

    def getLinksForVideo(self, cItem):
        printDBG("StreamCloud.getLinksForVideo [%s]" % cItem)
        linksTab = []
        sts, data = self.getPage(cItem['link'], self.defaultParams)
        if not sts:
            return []
        if cItem.get('seasons') and cItem.get('episode'):
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="season-%s">' % cItem.get('seasons'), '</ul>')[0]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '>%s</a>' % cItem.get('episode'), '</li>')[0]
        link = re.compile('data-link="([^"]+)', re.DOTALL).findall(data)
        if not link:
            url2 = re.compile('src="([^"]+)" frameborder', re.DOTALL).findall(data)
            if url2:
                sts, data = self.getPage(url2[0], self.defaultParams)
                if not sts:
                    return []
                link = re.compile('data-link="([^"]+)', re.DOTALL).findall(data)
        for url in link:
            if "meinecloud" in url or "player.php" in url or "youtube" in url:
                continue
            if url.startswith('//'):
                url = "https:" + url
            title = urlparse(url).netloc.split('.')[0]
            linksTab.append({'name': title.capitalize(), 'url': strwithmeta(url, {'Referer': self.MAIN_URL}), 'need_resolve': 1})
        if linksTab:
            cItem['url'] = linksTab
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("StreamCloud.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("StreamCloud.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem['link'])
        if not sts:
            return []
        desc = self.cm.ph.getSearchGroups(data, 'itemprop="description" content="([^"]+)')[0]
        desc = desc if desc else cItem.get('desc', '')
        actors = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, "Schauspieler: </strong>(.*?)</div>")[0])
        if actors:
            otherInfo['actors'] = actors
        d = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'Regie: </strong>(.*?)</div>')[0])
        if d:
            otherInfo['director'] = d
        released = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'Veröffentlicht: </strong>(.*?)</div>')[0])
        if released:
            otherInfo['released'] = released
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'Spielzeit: </strong>(.*?)</div>')[0])
        if duration:
            otherInfo['duration'] = duration
        title = cItem['title']
        icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        return [{'title': title, 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

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
        elif 'list_seasons' == category:
            self.listSeasons(self.currItem)
        elif 'list_episodes' == category:
            self.listEpisodes(self.currItem)
        elif 'list_genres' == category:
            self.listValue(self.currItem, '>Genres')
        elif 'list_year' == category:
            self.listValue(self.currItem, '>Erscheinungsjahr')
        elif 'list_country' == category:
            self.listValue(self.currItem, '>Land')
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
        CHostBase.__init__(self, StreamCloud(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
