# -*- coding: utf-8 -*-
######################
# (c) 2025 Team Jogi #
######################
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
    return 'https://hdfilme.auction'


class HDFilmeTV(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'hdfilme.tv', 'cookie': 'hdfilme.tv.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/StoneOffStones/plugin.video.xstream/c88b2a6953febf6e46cf77f891d550a3c2ee5eea/resources/art/sites/hdfilme.png"
        self.MAIN_URL = None

    def selectDomain(self):
        self.MAIN_URL = 'https://hdfilme.auction'
        self.MAIN_CAT_TAB = [
                            {'category': 'list_items', 'title': _("New"), 'link': self.getFullUrl('/aktuelle-kinofilme-im-kino/')},
                            {'category': 'list_items', 'title': _("Movies"), 'link': self.getFullUrl('/kinofilme-online/')},
                            {'category': 'list_items', 'title': _("Series"), 'link': self.getFullUrl('/serienstream-deutsch/')},
                            {'category': 'list_genres', 'title': 'Genres', 'link': self.MAIN_URL},
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
        printDBG("HDFilmeTV.listItems |%s|" % cItem)
        url = cItem['link']
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, """href="([^"]+)">›</a></div>""")[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="box-product clearfix" data-popover', '</li>')

        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, """href=['"]([^'^"]+?)['"]""")[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r"""data-src=['"]([^'^"]+?\.jpe?g)['"]""")[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, """title=['"]([^'^"]+)['"]""")[0])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title.replace(' stream', ''), 'link': url, 'icon': icon, 'desc': ''})
            if 'taffel' in title:
                params.update({'category': 'list_episodes'})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage.startswith('https'):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'link': self.getFullUrl(nextPage)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("HDFilmeTV.listEpisodes")
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
        printDBG("HDFilmeTV.Genres")
        url = cItem['link']
        sts, data = self.getPage(url)
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'Genre">Genre', '</ul>')[0]
        data = re.compile('href="([^"]+).*?>([^<]+)', re.DOTALL).findall(data)

        for url, title in data:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title.replace(' stream', ''), 'link': url, 'icon': '', 'desc': ''})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HDFilmeTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['link'] = self.getFullUrl('index.php?do=search&subaction=search&story=%s' % urllib_quote(searchPattern))
        self.listItems(cItem, 'video')

    def getLinksForVideo(self, cItem):
        printDBG("HDFilmeTV.getLinksForVideo [%s]" % cItem)
        linksTab = []
        sts, data = self.getPage(cItem['link'], self.defaultParams)
        if not sts:
            return []
        if cItem.get('episode'):
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, cItem.get('episode'), '</ul>')[0]
        data = re.compile('link="([^"]+)', re.DOTALL).findall(data)

        for url in data:
            if "vod/mega" in url or "youtube" in url:
                continue
            if url.startswith('//'):
                url = "https:" + url
            title = urlparse(url).netloc.split('.')[0]
            linksTab.append({'name': title, 'url': url, 'need_resolve': 1})
        if linksTab:
            cItem['url'] = linksTab
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("HDFilmeTV.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if self.cm.isValidUrl(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("HDFilmeTV.getArticleContent [%s]" % cItem)
        otherInfo = {}
        sts, data = self.getPage(cItem['link'])
        if not sts:
            return []
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        tmpTab = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'enres:', '</a></span>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for t in tmp:
            tmpTab.append(self.cleanHtmlStr(t))
        if len(tmpTab):
            otherInfo['genre'] = ', '.join(tmpTab)
        tmpTab = []
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<p>Mit:', '</p>')
        for t in tmp:
            tmpTab.append(self.cleanHtmlStr(t))
        if len(tmpTab):
            otherInfo['actors'] = ', '.join(tmpTab)
        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'datePublished" content="', '">', False)[1])
        if tmp != '':
            otherInfo['released'] = tmp
        tmp = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, """datetime=".*?">([^<]+)""")[0])
        if tmp != '':
            otherInfo['duration'] = tmp
        title = cItem['title']
        icon = cItem.get('icon', self.DEFAULT_ICON_URL)
        if desc == '':
            desc = cItem.get('desc', '')
        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.selectDomain()
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
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
        CHostBase.__init__(self, HDFilmeTV(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('category', '') == 'video'
