# -*- coding: utf-8 -*-
#
#-*- Coded  by gorr
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
###################################################

###################################################
# FOREIGN import
###################################################
import re
###################################################


def gettytul():
    return 'http://sovdub.ru/'


class Sovdub(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Sovdub', 'cookie': 'Sovdub.cookie'})

        self.MAIN_URL = 'http://sovdub.ru/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/templates/simplefilms/images/logo.png')

        self.MAIN_CAT_TAB = [{'category': 'genres', 'title': _('Genres'), 'url': self.getMainUrl()},
                             {'category': 'countries', 'title': _('Countries'), 'url': self.getMainUrl()},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')}
                            ]
        self.encoding = ''

    def getPage(self, url, params={}, post_data=None):
        sts, data = self.cm.getPage(url, params, post_data)
        if sts and self.encoding == '':
            self.encoding = self.cm.ph.getSearchGroups(data, 'charset=([^"]+?)"')[0]
        return sts, data

    def getFullUrl(self, url):
        url = url.replace('&amp;', '&')
        return CBaseHostClass.getFullUrl(self, url)

    def listGenres(self, cItem, category):
        printDBG("Sovdub.listGenres")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        catData = self.cm.ph.getDataBeetwenMarkers(data, '<div class="right-menu">', '</div>', False)[1]
        catData = re.compile('href="([^"]+?)">([^<]+?)</a>').findall(catData)
        for item in catData:
            params = dict(cItem)
            params.update({'category': category, 'title': item[1], 'url': item[0]})
            self.addDir(params)

    def listCountries(self, cItem, category):
        printDBG("Sovdub.listCountries")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        canData = self.cm.ph.getDataBeetwenMarkers(data, 'Выбор страны', '</div>', False)[1]
        canData = re.compile('href="([^"]+?)">([^<]+?)</a>').findall(canData)
        for item in canData:
            params = dict(cItem)
            params.update({'category': category, 'title': item[1], 'url': item[0]})
            self.addDir(params)

    def listItems(self, cItem, category):
        printDBG("Sovdub.listItems")

        url = cItem['url']
        if '?' in url:
            post = url.split('?')
            url = post[0]
            post = post[1]
        else:
            post = ''
        page = cItem.get('page', 1)
        if page > 1:
            url += 'page/%d/' % page
        if post != '':
            url += '?' + post

        post_data = cItem.get('post_data', None)
        sts, data = self.getPage(url, {}, post_data)
        if not sts:
            return

        if ('/page/%d/' % (page + 1)) in data:
            nextPage = True
        else:
            nextPage = False

        m1 = '</div></div>'
        if ('<div class="navigation">') in data:
            m1 = '<div class="navigation">'
        data = self.cm.ph.getDataBeetwenMarkers(data, "<div id='dle-content'>", m1, False)[1]
        data = re.compile('src="(.*jpg)".*alt="(.*)" />*\s.*<a href="(.*?)"></a></div>').findall(data)
        for item in data:
            title = item[1]
            icon = self.getFullIconUrl(item[0])
            url = self.getFullUrl(item[2])
            printDBG(icon)
            params = dict(cItem)
            params.update({'category': category, 'title': title, 'icon': icon, 'desc': title, 'url': url})
            self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': cItem.get('page', 1) + 1})
            self.addDir(params)

    def listContent(self, cItem):
        printDBG("Sovdub.listContent")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<div class="full-news-content">', '</a></div>', False)[1]
        desc = self.cleanHtmlStr(desc).replace('  ', '')

        url = ''
        hasLinks = False
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<iframe', '>'), ('</iframe', '>'), caseSensitive=False)
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=["']([^"^']+?)['"]''', 1, True)[0]
            url = url.replace('amp;', '')
            url = self.getFullUrl(url)
            if 'money.' not in url and 1 == self.up.checkHostSupport(url):
                hasLinks = True

        if self.cm.isValidUrl(url):
            params = dict(cItem)
            params['desc'] = desc
            params.update({'desc': desc})
            if hasLinks:
                self.addVideo(params)
            else:
                self.addArticle(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        #searchPattern = 'Колонна'

        if self.encoding == '':
            sts, data = self.getPage(self.getMainUrl())
            if not sts:
                return

        try:
            searchPattern = searchPattern.decode('utf-8').encode(self.encoding, 'ignore')
        except Exception:
            searchPattern = ''

        post_data = {'do': 'search', 'subaction': 'search', 'story': searchPattern, 'x': 0, 'y': 0}

        sts, data = self.getPage(self.getMainUrl(), post_data=post_data)
        if not sts:
            return

        m1 = '<div class="main-news">'
        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '<div style="clear: both;">', False)[1]
        data = data.split(m1)
        for item in data:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2', '</h2>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '</h2>', '</div>')[1])
            if self.cm.isValidUrl(url):
                params = dict(cItem)
                params.update({'category': 'list_content', 'title': title, 'icon': icon, 'desc': desc, 'url': url})
                self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("Sovdub.getLinksForVideo [%s]" % cItem)
        urlTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<iframe', '>'), ('</iframe', '>'), caseSensitive=False)
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''<iframe[^>]+?src=["']([^"^']+?)['"]''', 1, True)[0]
            url = url.replace('amp;', '')
            url = self.getFullUrl(url)
            if 'money.' not in url:
                urlTab.append({'name': self.cleanHtmlStr(item), 'url': url, 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("Sovdub.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

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
        elif category == 'genres':
            self.listGenres(self.currItem, 'list_items')
        elif category == 'countries':
            self.listCountries(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_content')
        elif category == 'list_content':
            self.listContent(self.currItem)
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
        CHostBase.__init__(self, Sovdub(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
