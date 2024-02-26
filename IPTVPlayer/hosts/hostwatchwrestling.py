# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
###################################################


###################################################
# Config options for HOST
###################################################

def GetConfigList():
    optionList = []
    return optionList
###################################################


def gettytul():
    return 'http://watchwrestling.nl/'


class Watchwrestling(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Watchwrestling', 'cookie': 'Watchwrestling.cookie'})
        self.serversCache = []

        self.MAIN_URL = 'http://watchwrestling.nl/'
        self.SRCH_URL = self.getFullUrl('index.php?s=')
        self.DEFAULT_ICON_URL = 'http://watchwrestling.to/wp-content/uploads/2014/11/ww_fb.png'

        self.MAIN_CAT_TAB = [{'category': 'categories', 'title': _('Categories'), 'url': self.getMainUrl(), 'm1': 'Categories</h3>'},
                             {'category': 'categories', 'title': _('Monthly'), 'url': self.getFullUrl('video/watch-wwe-raw-101915/'), 'm1': 'Monthly Posts</h3>'},
                             {'category': 'live', 'title': _('LIVE 24/7'), 'url': self.getFullUrl('watch-wwe-network-live/')},
                             {'category': 'categories', 'title': _('WWE'), 'url': self.getFullUrl('category/wwe/'), 'm1': '>WWE</a>'},
                             {'category': 'list_filters', 'title': _('WWE Network'), 'url': self.getFullUrl('category/wwenetwork/')},
                             {'category': 'categories', 'title': _('TNA'), 'url': self.getFullUrl('category/tna/'), 'm1': '>TNA</a>'},
                             {'category': 'categories', 'title': _('Weekly Indys'), 'url': self.getFullUrl('category/weekly-indys/'), 'm1': '>Weekly Indys</a>'},
                             {'category': 'list_filters', 'title': _('NJPW'), 'url': self.getFullUrl('category/njpw/')},
                             {'category': 'categories', 'title': _('Other Sports'), 'url': self.getFullUrl('category/other-sports/'), 'm1': '>Other Sports</a>'},
                             {'category': 'list_filters', 'title': _('RAW'), 'url': self.getFullUrl('category/wwe/raw/')},
                             {'category': 'list_filters', 'title': _('Smackdown'), 'url': self.getFullUrl('category/wwe/smackdown/')},
                             {'category': 'list_filters', 'title': _('Total Divas'), 'url': self.getFullUrl('category/wwe/totaldivas/')},
                             {'category': 'list_filters', 'title': _('NXT'), 'url': self.getFullUrl('category/wwe/nxt/')},
                             {'category': 'list_filters', 'title': _('Archives'), 'url': self.getFullUrl('category/archives/')},

                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')}
                            ]

        self.SORT_TAB = [{'sort': 'date', 'title': _('DATE')},
                         {'sort': 'views', 'title': _('VIEWS')},
                         {'sort': 'likes', 'title': _('LIKES')},
                         {'sort': 'comments', 'title': _('COMMENTS')}
                        ]

    def listCategories(self, cItem, nexCategory):
        printDBG("Watchwrestling.listCategories")
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, cItem['m1'], '</ul>', False)[1]

        if '"sub-menu"' in data:
            params = dict(cItem)
            params.update({'title': _('--All--'), 'category': nexCategory})
            self.addDir(params)

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)["']''')[0]
            if url == '':
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'title': title, 'url': self.getFullUrl(url), 'category': nexCategory})
            self.addDir(params)

    def listFilters(self, cItem, category):
        printDBG("Watchwrestling.listFilters")
        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(self.SORT_TAB, cItem)

    def listMovies(self, cItem, nextCategory):
        printDBG("Watchwrestling.listMovies")
        url = cItem['url']
        page = cItem.get('page', 1)
        if page > 1:
            url += 'page/%d/' % page
        if '?' in url:
            url += '&'
        else:
            url += '?'
        url += 'orderby=%s' % cItem['sort']

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        if ('/page/%d/' % (page + 1)) in data:
            nextPage = True
        else:
            nextPage = False

        if '<div class="loop-nav pag-nav">' in data:
            m2 = '<div class="loop-nav pag-nav">'
        else:
            m2 = '<div id="sidebar"'
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="nag cf">', m2, False)[1]

        data = data.split('<div id="post-')
        if len(data):
            del data[0]

        for item in data:
            tmp = item.split('<p class="stats">')
            url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0]
            title = self.cm.ph.getSearchGroups(item, 'title="([^"]+?)"')[0]
            desc = tmp[-1]
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': self.cleanHtmlStr(title), 'url': self.getFullUrl(url), 'desc': self.cleanHtmlStr(desc), 'icon': self.getFullUrl(icon)})
            self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listServers(self, cItem, nextCategory):
        printDBG("Watchwrestling.listServers [%s]" % cItem)
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        self.serversCache = []
        matchObj = re.compile('href="([^"]+?)"[^>]*?>([^>]+?)</a>')
        sp = '<div style="text-align: center;">'
        data = self.cm.ph.getDataBeetwenMarkers(data, sp, '<div id="extras">', False)[1]
        data = data.split(sp)
        if len(data):
            del data[0]
        for item in data:
            sts, serverName = self.cm.ph.getDataBeetwenMarkers(item, 'geneva;">', '</span>', False)
            if not sts:
                continue
            parts = matchObj.findall(item)
            partsTab = []
            for part in parts:
                partsTab.append({'title': cItem['title'] + '[%s]' % part[1], 'url': part[0], 'Referer': cItem['url']})
            if len(partsTab):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': serverName, 'part_idx': len(self.serversCache)})
                self.addDir(params)
                self.serversCache.append(partsTab)

    def listParts(self, cItem):
        printDBG("Watchwrestling.listServers [%s]" % cItem)
        partIdx = cItem['part_idx']
        self.listsTab(self.serversCache[partIdx], cItem, 'video')

    def listLiveStreams(self, cItem):
        printDBG("Watchwrestling.listLiveStreams [%s]" % cItem)
        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return
        sp = '<div style="text-align: center;">'
        data = self.cm.ph.getDataBeetwenMarkers(data, sp, '</div>', False)[1]
        data = re.compile('href="([^"]+?)"[^>]*?>([^>]+?)</a>').findall(data)
        for item in data:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': item[1], 'url': item[0], 'Referer': cItem['url'], 'live': True})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = urllib_quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem['url'] = self.SRCH_URL + searchPattern
        cItem['sort'] = searchType
        self.listMovies(cItem, 'list_server')

    def _clearData(self, data):
        data = re.sub("<!--[\s\S]*?-->", "", data)
        data = re.sub("/\*[\s\S]*?\*/", "", data)
        return data

    def getLinksForVideo(self, cItem):
        printDBG("Watchwrestling.getLinksForVideo [%s]" % cItem)
        urlTab = []
        url = cItem['url']
        Referer = cItem.get('Referer', '')
        if 1 != self.up.checkHostSupport(url):
            tries = 0
            while tries < 3:
                sts, data = self.cm.getPage(url, {'header': {'Referer': Referer, 'User-Agent': 'Mozilla/5.0'}})
                if not sts:
                    return urlTab
                data = data.replace('// -->', '')
                data = self._clearData(data)
                #printDBG(data)
                if 'eval(unescape' in data:
                    data = urllib_unquote(self.cm.ph.getSearchGroups(data, '''eval\(unescape\(['"]([^"^']+?)['"]''')[0])
                url = self.cm.ph.getSearchGroups(data, '''<iframe[^>]*?src=['"]([^"^']+?)['"]''', 1, True)[0]
                if 'protect.cgi' in url:
                    Referer = cItem['url']
                else:
                    break
                tries += 1
        url = strwithmeta(url)
        url.meta['Referer'] = Referer
        url.meta['live'] = cItem.get('live', False)

        urlTab.append({'name': cItem['title'], 'url': url, 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, baseUrl):
        printDBG("Watchwrestling.getVideoLinks [%s]" % baseUrl)
        urlTab = []

        url = strwithmeta(baseUrl)
        if url.meta.get('live'):
            urlTab = self.up.getAutoDetectedStreamLink(url)
        else:
            urlTab = self.up.getVideoLinkExt(url)
        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('Watchwrestling.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('Watchwrestling.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('Watchwrestling.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

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
        elif category == 'categories':
            self.listCategories(self.currItem, 'list_filters')
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_movies')
    #MOVIES
        elif category == 'list_movies':
            self.listMovies(self.currItem, 'list_server')
        elif category == 'list_server':
            self.listServers(self.currItem, 'list_parts')
        elif category == 'list_parts':
            self.listParts(self.currItem)
    #LIVE
        elif category == 'live':
            self.listLiveStreams(self.currItem)
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
        CHostBase.__init__(self, Watchwrestling(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("DATE"), "date"))
        searchTypesOptions.append((_("VIEWS"), "views"))
        searchTypesOptions.append((_("LIKES"), "likes"))
        searchTypesOptions.append((_("COMMENTS"), "comments"))
        return searchTypesOptions
