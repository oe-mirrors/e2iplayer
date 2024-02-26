# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem, ArticleContent
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
###################################################

def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return 'http://www.filma24hd.com/'


class Filma24hdCom(CBaseHostClass):
    MAIN_URL = 'http://www.filma24hd.com/'
    SRCH_URL = MAIN_URL + '?s='
    DEFAULT_ICON_URL = 'http://www.filma24hd.com/wp-content/uploads/2015/12/f24hd.png'

    MAIN_TV_SERIES_URL = 'http://seriale.filma24hd.com/'
    DEFAULT_TV_SERIES_ICON_URL = 'http://seriale.filma24hd.com/wp-content/uploads/2015/12/f24hdserie.png'

    MAIN_CAT_TAB = [{'category': 'movies', 'title': _('Movies'), 'url': MAIN_URL, 'icon': DEFAULT_ICON_URL},
                    {'category': 'series', 'title': _('TV Series'), 'url': MAIN_TV_SERIES_URL, 'icon': DEFAULT_TV_SERIES_ICON_URL},
                    {'category': 'search', 'title': _('Search'), 'search_item': True, 'icon': DEFAULT_ICON_URL},
                    {'category': 'search_history', 'title': _('Search history'), 'icon': DEFAULT_ICON_URL}
                   ]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Filma24hdCom', 'cookie': 'Filma24hdCom.cookie'})
        self.seriesSubCategoryCache = []

    def _getFullUrl(self, url, series=False):
        if not series:
            mainUrl = self.MAIN_URL
        else:
            mainUrl = self.S_MAIN_URL
        if url.startswith('/'):
            url = url[1:]
        if 0 < len(url) and not url.startswith('http'):
            url = mainUrl + url
        if not mainUrl.startswith('https://'):
            url = url.replace('https://', 'http://')
        m1 = 'www.seriale.'
        if m1 in url:
            url = url.replace(m1, 'seriale.')
        return url

    def listMoviesCategory(self, cItem, nextCategory):
        printDBG("Filma24hdCom.listMoviesCategory")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<!-- Menu Starts -->', '<!-- Menu Ends -->', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self._getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''', 1, True)[0])
            if url == '' or 'seriale' in url:
                continue
            params = dict(cItem)
            params.update({'category': nextCategory, 'url': self._getFullUrl(url), 'title': title})
            self.addDir(params)

    def listSeriesCategory(self, cItem, nextCategory):
        printDBG("Filma24hdCom.listSeriesCategory")
        self.seriesSubCategoryCache = []
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        marker = '<ul class="sub-menu">'
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="main-nav">', '<!-- end #main-nav -->', False)[1]
        data = data.split('</ul>')
        for item in data:
            if marker not in item:
                continue
            tmp = item.split(marker)
            subCategoryTitle = self.cm.ph.rgetDataBeetwenMarkers(tmp[0], '<a', '</a>')[1]
            subCategoryUrl = self.cm.ph.getSearchGroups(subCategoryTitle, '''href=['"]([^"^']+?)["']''', 1, True)[0]
            subCategoryUrl = self._getFullUrl(subCategoryUrl)
            subCategoryTitle = self.cleanHtmlStr(subCategoryTitle)

            subItemsTab = []
            subItems = self.cm.ph.getAllItemsBeetwenMarkers(tmp[1], '<a ', '</a>')
            for subItem in subItems:
                title = self.cleanHtmlStr(subItem)
                url = self.cm.ph.getSearchGroups(subItem, '''href=['"]([^"^']+?)["']''', 1, True)[0]
                subItemsTab.append({'title': title, 'url': self._getFullUrl(url)})

            if len(subItemsTab):
                params = dict(cItem)
                params.update({'category': nextCategory, 'sub_idx': len(self.seriesSubCategoryCache), 'url': self._getFullUrl(subCategoryUrl), 'title': subCategoryTitle})
                self.addDir(params)
                self.seriesSubCategoryCache.append(subItemsTab)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("Filma24hdCom.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if type == 'dir':
                self.addDir(params)
            else:
                self.addVideo(params)

    def listItems(self, cItem, category=''):
        printDBG("Filma24hdCom.listItems")
        url = cItem['url']
        if '?' in url:
            post = url.split('?')
            url = post[0]
            post = post[1]
        else:
            post = ''
        page = cItem.get('page', 1)
        if page > 1:
            url += '/page/%d/' % page
        if post != '':
            url += '?' + post

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        nextPage = False
        if ("/page/%d/" % (page + 1)) in data:
            nextPage = True

        if 'seriale.' in url:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div id="post-', '<!-- end')
            serieItem = True
        else:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<!-- Post Starts -->', '<!-- Post Ends -->')
            serieItem = False
        for item in data:
            if serieItem:
                item = item.split('<!-- end')[0]

            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            if url == '':
                continue
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            title = self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1]
            desc = self.cleanHtmlStr(item.split('<p class="entry-meta">')[-1])

            params = dict(cItem)
            params.update({'title': self.cleanHtmlStr(title), 'url': self._getFullUrl(url), 'desc': desc, 'icon': self._getFullUrl(icon)})
            self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSeasons(self, cItem, nextCategory):
        printDBG("Filma24hdCom.listSeasons [%s]" % cItem)
        idx = cItem.get('sub_idx', -1)
        if idx < 0 or idx >= len(self.seriesSubCategoryCache):
            return

        tab = self.seriesSubCategoryCache[idx]
        params = dict(cItem)
        params['category'] = nextCategory
        self.listsTab(tab, params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib_quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['url'] = self.SRCH_URL + urllib_quote_plus(searchPattern)
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("Filma24hdCom.getLinksForVideo [%s]" % cItem)
        urlTab = []
        url = cItem['url']

        sts, data = self.cm.getPage(url)
        if not sts:
            return []

        videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"](http[^"^']+?)['"]''', 1, True)[0]
        if 1 == self.up.checkHostSupport(videoUrl):
            urlTab.append({'name': self.up.getHostName(videoUrl), 'url': videoUrl, 'need_resolve': 1})

        videoUrlTab = self.cm.ph.getDataBeetwenMarkers(data, '<video ', '</video>', caseSensitive=False)[1]
        videoUrlTab = re.compile('''<source[^>]*?src=['"](http[^"]+?)['"][^>]*?mp4[^>]*?''', re.IGNORECASE).findall(videoUrlTab)
        for idx in range(len(videoUrlTab)):
            urlTab.append({'name': 'direct %d' % (idx + 1), 'url': videoUrlTab[idx], 'need_resolve': 0})

        videoUrlTab = self.cm.ph.getDataBeetwenMarkers(data, '<tbody>', '</tbody>', caseSensitive=False)[1]
        videoUrlTab += self.cm.ph.getDataBeetwenMarkers(data, '<map ', '</map>', caseSensitive=False)[1]
        videoUrlTab = re.compile('''<a[^>]*?href=['"](http[^"]+?)['"]''', re.IGNORECASE).findall(videoUrlTab)
        for item in videoUrlTab:
            if 1 != self.up.checkHostSupport(item):
                continue
            urlTab.append({'name': self.up.getHostName(item), 'url': item, 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("Filma24hdCom.getVideoLinks [%s]" % videoUrl)
        return self.up.getVideoLinkExt(videoUrl)

    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

    def getArticleContent(self, cItem):
        printDBG("Filma24hdCom.getArticleContent [%s]" % cItem)
        retTab = []

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return retTab

        m1 = '<span style="color: #00'
        if m1 not in data:
            m1 = '<div class="entry-content'
        m2 = '<p>&nbsp;</p>'
        if m2 not in data:
            m2 = '<tbody>'
        desc = self.cm.ph.getDataBeetwenMarkers(data, m1, m2)[1]
        desc = self.cleanHtmlStr(desc)

        icon = cItem.get('icon', '')
        title = cItem.get('title', '')
        otherInfo = {}

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self._getFullUrl(icon)}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
    #MOVIES
        elif category == 'movies':
            self.listMoviesCategory(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
    #TVSERIES
        elif category == 'series':
            params = dict(self.currItem)
            params.update({'category': 'list_items', 'title': _('--All--')})
            self.addDir(params)
            self.listSeriesCategory(self.currItem, 'list_seasons')
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_items')
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
        CHostBase.__init__(self, Filma24hdCom(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('filma24hdcomlogo.png')])

    def getLinksForVideo(self, Index=0, selItem=None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)

        urlList = self.host.getLinksForVideo(self.host.currList[Index])
        for item in urlList:
            retlist.append(CUrlItem(item["name"], item["url"], item['need_resolve']))

        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo

    def getResolvedURL(self, url):
        # resolve url to get direct url to video file
        retlist = []
        urlList = self.host.getVideoLinks(url)
        for item in urlList:
            need_resolve = 0
            retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value=retlist)

    def getArticleContent(self, Index=0):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)
        cItem = self.host.currList[Index]

        if cItem['type'] != 'video':
            return RetHost(retCode, value=retlist)
        hList = self.host.getArticleContent(cItem)
        for item in hList:
            title = item.get('title', '')
            text = item.get('text', '')
            images = item.get("images", [])
            othersInfo = item.get('other_info', '')
            retlist.append(ArticleContent(title=title, text=text, images=images, richDescParams=othersInfo))
        return RetHost(RetHost.OK, value=retlist)

    def converItem(self, cItem):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie

        hostLinks = []
        type = CDisplayListItem.TYPE_UNKNOWN
        possibleTypesOfSearch = None

        if 'category' == cItem['type']:
            if cItem.get('search_item', False):
                type = CDisplayListItem.TYPE_SEARCH
                possibleTypesOfSearch = searchTypesOptions
            else:
                type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'video':
            type = CDisplayListItem.TYPE_VIDEO
        elif 'more' == cItem['type']:
            type = CDisplayListItem.TYPE_MORE
        elif 'audio' == cItem['type']:
            type = CDisplayListItem.TYPE_AUDIO

        if type in [CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_VIDEO]:
            url = cItem.get('url', '')
            if '' != url:
                hostLinks.append(CUrlItem("Link", url, 1))

        title = cItem.get('title', '')
        description = cItem.get('desc', '')
        icon = cItem.get('icon', '')

        return CDisplayListItem(name=title,
                                    description=description,
                                    type=type,
                                    urlItems=hostLinks,
                                    urlSeparateRequest=1,
                                    iconimage=icon,
                                    possibleTypesOfSearch=possibleTypesOfSearch)
    # end converItem

    def getSearchItemInx(self):
        try:
            list = self.host.getCurrList()
            for i in range(len(list)):
                if list[i]['category'] == 'search':
                    return i
        except Exception:
            printDBG('getSearchItemInx EXCEPTION')
            return -1

    def setSearchPattern(self):
        try:
            list = self.host.getCurrList()
            if 'history' == list[self.currIndex]['name']:
                pattern = list[self.currIndex]['title']
                search_type = list[self.currIndex]['search_type']
                self.host.history.addHistoryItem(pattern, search_type)
                self.searchPattern = pattern
                self.searchType = search_type
        except Exception:
            printDBG('setSearchPattern EXCEPTION')
            self.searchPattern = ''
            self.searchType = ''
        return
