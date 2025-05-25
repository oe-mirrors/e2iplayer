# -*- coding: utf-8 -*-
####################
#  2025 Team Jogi  #
####################
import re
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return 'https://hdfilme.my'


class HDFilme(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'HDFilme', 'cookie': 'HDFilme.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = 'https://www.hdfilme.my/templates/hdfilme/images/apple-touch-icon.png'
        self.MAIN_URL = None

    def menu(self):
        self.MAIN_URL = 'https://hdfilme.my'
        self.MENU = [
            {'category': 'list_items', 'title': _("New"), 'url': self.getFullUrl('filme1/')},
            {'category': 'list_items', 'title': 'Kinofilme', 'url': self.getFullUrl('/kinofilme/')},
            {'category': 'list_items', 'title': _("Series"), 'url': self.getFullUrl('/serien/')},
            {'category': 'list_genres', 'title': 'Genres'},
            {'category': 'list_year', 'title': 'Jahr'},
            {'category': 'list_country', 'title': 'Land'},
            {'category': 'search', 'title': _('Search'), 'search_item': True},
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

    def listItems(self, cItem):
        printDBG("HDFilme.listItems |%s|" % cItem)
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = re.findall('nav_ext">.*?next">.*?href="([^"]+)', data, re.DOTALL)
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="item relative', 'class="absolute')
        if not items:
            items = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="pages">', '<svg')

        for item in items:
            desc = ''
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'data-src="([^"]+)')[0])
            duration = self.cm.ph.getSearchGroups(item, r'<span>(\d+ min)</span>')
            year = self.cm.ph.getSearchGroups(item, r'<span>(\d{4})</span>')
            if year:
                desc += "Jahr: %s \n" % year[0]
            if duration:
                desc += "Dauer: %s" % duration[0]
            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0]
            if not title:
                title = self.cm.ph.getSearchGroups(item, '<strong>(.*?)</strong>')[0]
            title = title.split(" &#8211;")[0]
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_seasons', 'title': self.cleanHtmlStr(title), 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': self.getFullUrl(nextPage[0])})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("HDFilme.listSeasons |%s|" % cItem)
        url = cItem['url']
        icon = cItem['icon']
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0])
        data = re.findall(r'#se-ac-(\d+)', data, re.DOTALL)
        if not data:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'video', 'title': cItem['title'], 'url': self.getFullUrl(url), 'icon': icon, 'desc': desc})
            self.addVideo(params)
        else:
            for seasons in data:
                title = cItem['title'] + " - Staffel " + seasons
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'list_episodes', 'title': title, 'url': url, 'icon': icon, 'desc': desc, 'seasons': seasons})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("HDFilme.listEpisodes |%s|" % cItem)
        url = cItem['url']
        seasons = cItem['seasons']
        icon = cItem['icon']
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data.replace('\n', ''), '#se-ac-%s' % seasons, '</div></div>')[0]
        data = re.findall(r'Episode\s(\d+)', data, re.DOTALL)
        for episode in data:
            title = cItem['title'] + " - Episode " + episode
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc, 'seasons': seasons, 'episode': episode})
            self.addVideo(params)

    def listValue(self, cItem, v):
        printDBG("HDFilme.Value |%s|" % cItem)
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '>%s<' % v, '<div class')
        data = re.findall('href="([^"]+).*?>([^<]+)', data[0], re.DOTALL)
        for url, title in data:
            if 'ino' in title or 'erien' in title or 'chst' in title:
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'url': self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HDFilme.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('index.php?do=search&subaction=search&story=%s' % urllib_quote(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("HDFilme.getLinksForVideo [%s]" % cItem)
        linksTab = []
        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []
        if cItem.get('seasons') and cItem.get('episode'):
            data = self.cm.ph.getAllItemsBeetwenMarkers(data.replace('\n', ''), '#se-ac-%s' % cItem.get('seasons'), '</div></div>')[0]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'x%s Episode' % cItem.get('episode'), '<br')[0]
            data = re.findall('href="([^"]+)', data, re.DOTALL)
        else:
            data = re.findall(r'<iframe\sw.*?src="([^"]+)', data, re.DOTALL)
            sts, data = self.getPage(data[0], self.defaultParams)
            if not sts:
                return []
            data = re.findall('data-link="([^"]+)', data, re.DOTALL)
        for url in data:
            if "meinecloud" in url or "player.php" in url:
                continue
            url = "https:" + url if url.startswith('//') else url
            linksTab.append({'name': self.up.getHostName(url).capitalize(), 'url': strwithmeta(url, {'Referer': self.MAIN_URL}), 'need_resolve': 1})
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("HDFilme.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("HDFilme.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'og:description" content="([^"]+)')[0]) or cItem.get('desc', '')
        actors = self.cm.ph.getAllItemsBeetwenMarkers(data, 'Schauspieler:', '</li>')
        if actors:
            names = re.findall('">([^<]+)', actors[0], re.DOTALL)
            if names:
                otherInfo['actors'] = ", ".join(names)
        released = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<span>(\d{4})</span>')[0])
        if released:
            otherInfo['released'] = released
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(\d+ min)')[0])
        if duration:
            otherInfo['duration'] = duration
        title = cItem['title']
        icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

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
            self.listItems(self.currItem)
        elif 'list_seasons' == category:
            self.listSeasons(self.currItem)
        elif 'list_episodes' == category:
            self.listEpisodes(self.currItem)
        elif 'list_genres' == category:
            self.listValue(self.currItem, 'Genre')
        elif 'list_year' == category:
            self.listValue(self.currItem, 'Jahres')
        elif 'list_country' == category:
            self.listValue(self.currItem, 'Land')
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
        CHostBase.__init__(self, HDFilme(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
