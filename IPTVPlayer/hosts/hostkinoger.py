# -*- coding: utf-8 -*-
import re
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
try:
    from itertools import zip_longest
except ImportError:
    from itertools import izip_longest as zip_longest


def GetConfigList():
    return []


def gettytul():
    return 'https://kinoger.to/'


class KinoGer(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kinoger', 'cookie': 'kinoger.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = 'https://kinoger.to//templates/kinoger/images/logo.png'
        self.MAIN_URL = None

    def menu(self):
        self.MAIN_URL = 'https://kinoger.to/'
        self.MENU = [
            {'category': 'list_items', 'title': 'Neues', 'link': self.MAIN_URL},
            {'category': 'list_items', 'title': _("Series"), 'link': self.getFullUrl('/stream/serie/')},
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
        printDBG("KinoGer.listItems |%s|" % cItem)
        url = cItem['link']
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, '<a[^>]href="([^"]+)">vorw')[0]
        data = re.compile('class="title".*?href="([^"]+)">([^<]+).*?src="([^"]+)(.*?)"footercontrol">', re.DOTALL).findall(data)

        for url, title, icon, dummy in data:
            desc = re.compile('<div style="text-align:right;">(.*?)<div[^>]class', re.DOTALL).findall(dummy)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': self.cleanHtmlStr(title), 'link': url, 'icon': icon, 'desc': self.cleanHtmlStr(desc[0]) if desc else ''})
            if 'taffel' in title or 'serie' in cItem['link'] or '>S0' in dummy:
                params.update({'category': 'list_seasons'})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'link': self.getFullUrl(nextPage)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("KinoGer.listSeasons")
        url = cItem['link']
        icon = cItem['icon']
        sts, data = self.getPage(url)
        if not sts:
            return
        season_lists = {}
        total = 0
        for key in ['sst', 'ollhd', 'pw', 'go']:
            container = re.compile(r'%s.show.*?</script>' % key, re.DOTALL).findall(data)
            if container:
                container = container[0]
                container = container.replace('[', '<').replace(']', '>')
                season_lists[key] = re.compile(r"<'([^>]+)", re.DOTALL).findall(container)
                if container:
                    total = len(season_lists[key])
        for i in range(total):
            params = dict(cItem)
            title = '%s - Staffel %s' % (cItem.get('title'), i + 1)
            for key in ['sst', 'ollhd', 'pw', 'go']:
                if key in season_lists and i < len(season_lists[key]):
                    params.update({key: season_lists[key][i]})
            params.update({'good_for_fav': True, 'category': 'list_episodes', 'title': title, 'link': url, 'icon': icon, 'desc': cItem.get('desc', '')})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("KinoGer.listEpisodes")
        icon = cItem['icon']
        episode_lists = {}
        for key in ['sst', 'ollhd', 'pw', 'go']:
            if cItem.get(key):
                episode_lists[key] = re.compile("(http[^']+)", re.DOTALL).findall(cItem[key])
        liste = zip_longest(*[episode_lists[key] for key in ['sst', 'ollhd', 'pw', 'go'] if key in episode_lists])
        for i, url in enumerate(liste, start=1):
            title = '%s - Episode %s' % (cItem.get('title'), i)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'Episode': url, 'icon': icon, 'desc': cItem.get('desc', '')})
            self.addVideo(params)

    def listGenres(self, cItem):
        printDBG("KinoGer.Value")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="sidelinks', '</ul>')[0]
        data = re.compile('href="([^"]+).*?/>([^<]+)', re.DOTALL).findall(data)
        for url, title in data:
            if 'erie' in title or url == '/':
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'link': self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KinoGer.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['link'] = self.getFullUrl('?do=search&subaction=search&titleonly=3&story=%s&x=0&y=0&submit=submit' % urllib_quote(searchPattern))
        self.listItems(cItem, 'video')

    def getLinksForVideo(self, cItem):
        printDBG("KinoGer.getLinksForVideo [%s]" % cItem)
        linksTab = []
        if cItem.get('Episode'):
            data = re.compile("(http[^']+)", re.DOTALL).findall(str(cItem['Episode']))
        else:
            sts, data = self.getPage(cItem['link'], self.defaultParams)
            if not sts:
                return []
            data = re.compile(r"show[^>]\d,[^>][^>]'([^']+)", re.DOTALL).findall(data)
        for url in data:
            title = urlparse(url).netloc.split('/')[0]
            linksTab.append({'name': title.capitalize(), 'url': strwithmeta(url, {'Referer': self.MAIN_URL}), 'need_resolve': 1})
        if linksTab:
            cItem['url'] = linksTab
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("KinoGer.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("KinoGer.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem['link'])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, 'description" content="([^"]+)')[0])
        desc = desc if desc else cItem.get('desc', '')
        actors = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, ">Schauspieler:([^<]+)")[0])
        if actors:
            otherInfo['actors'] = actors
        d = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '>Regie:([^<]+)')[0])
        if d:
            otherInfo['director'] = d
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '>Spielzeit:([^<]+)')[0])
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
        elif 'list_seasons' == category:
            self.listSeasons(self.currItem)
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
        CHostBase.__init__(self, KinoGer(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
