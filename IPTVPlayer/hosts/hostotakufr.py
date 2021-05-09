# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
###################################################


def gettytul():
    return 'http://otakufr.com/'


class OtakuFR(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'otakufr.com', 'cookie': 'otakufr.cookie'})
        self.USER_AGENT = 'User-Agent=Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.DEFAULT_ICON_URL = 'https://rocketdock.com/images/screenshots/thumbnails/21.png'
        self.MAIN_URL = None

        self.cacheABC = {}
        self.cacheSeries = []
        self.cachePrograms = []
        self.cacheLast = {}

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self._getHeaders = None

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullUrl(self, url):
        url = CBaseHostClass.getFullUrl(self, url)
        try:
            url.encode('ascii')
        except Exception:
            url = urllib.quote(url, safe="/:&?%@[]()*$!+-=|<>;")
        url = url.replace(' ', '%20')
        return url

    def selectDomain(self):
        self.MAIN_URL = 'http://www.otakufr.com/'
        self.MAIN_CAT_TAB = [{'category': 'list_abc', 'title': 'Toute La Liste', 'url': self.getFullUrl('/anime-list-all/')},
                             {'category': 'list_abc', 'title': 'En Cours', 'url': self.getFullUrl('/anime-en-cours/')},
                             {'category': 'list_rank_items', 'title': 'Populaire', 'url': self.getFullUrl('/anime-list/all/any/most-popular/')},
                             {'category': 'list_abc', 'title': 'Terminé', 'url': self.getFullUrl('/anime-termine/')},
                             {'category': 'list_rank_items', 'title': 'Film', 'url': self.getFullUrl('/anime-list/tag/Film/')},

                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

    def listABC(self, cItem, nextCategory):
        printDBG("OtakuFR.listABC")

        self.cacheABC = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="fl"', '<div id="sct_sidebar', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a name', '</ul>')
        for section in data:
            sectionTitle = self.cm.ph.getSearchGroups(section, '''<a[^>]+?name=['"]([^'^"]+?)['"]''')[0]
            section = self.cm.ph.getAllItemsBeetwenMarkers(section, '<li', '</li>')

            itemsTab = []
            for item in section:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                if not self.cm.isValidUrl(url):
                    continue
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
                if title == '':
                    title = self.cleanHtmlStr(item)
                itemsTab.append({'title': title, 'url': url})

            if len(itemsTab):
                self.cacheABC[sectionTitle] = itemsTab
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sectionTitle + (' [%s]' % len(itemsTab)), 'abc_key': sectionTitle})
                self.addDir(params)

    def listABCItems(self, cItem, nextCategory):
        printDBG("OtakuFR.listABCItems")
        abcKey = cItem.get('abc_key', '')
        tab = self.cacheABC.get(abcKey, [])
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params.update({'good_for_fav': True, 'category': nextCategory})
            self.addDir(params)

    def listRankItems(self, cItem, nextCategory, post_data=None):
        printDBG("OtakuFR.listRankItems")

        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'], post_data=post_data)
        if not sts:
            return

        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>Suivant</a>''')[0])

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<span class="rnk">', '<div class="clear">')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h2>', '</h2>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0])

            descTab = []
            tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(item, '<p', '</p>')
            for idx in range(len(tmpTab)):
                tmpDesc = self.cleanHtmlStr(tmpTab[idx])
                if tmpDesc != '':
                    descTab.append(tmpDesc)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(descTab)})
            self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("OtakuFR.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<input class=', '<div class="clr">')[1]
        printDBG(tmp)
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0])

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="lst">', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])

            descTab = []
            tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(item, '<b', '</b>')
            for idx in range(len(tmpTab)):
                tmpDesc = self.cleanHtmlStr(tmpTab[idx])
                if tmpDesc != '':
                    descTab.append(tmpDesc)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(descTab)})
            self.addVideo(params)

    def listSortFilters(self, cItem, nextCategory):
        printDBG("OtakuFR.listSortFilters")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, 'video-listing-filter', '</div>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</a>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'url': url, 'category': nextCategory})
            self.addDir(params)

    def listLast(self, cItem, nextCategory):
        printDBG("OtakuFR.listLast")
        self.cacheLast = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<article', '</article>')[1]
        data = data.split('<div class="smart-box-head">')
        if len(data):
            del data[0]
        for section in data:
            sectionTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(section, '<h2', '</h2>')[1])
            if sectionTitle == '':
                sectionTitle = 'Inne'
            section = section.split('<div class="video-item format-video">')
            if len(section):
                del section[0]
            itemsTab = []
            for item in section:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                if not self.cm.isValidUrl(url):
                    continue
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h3>', '</h3>')[1])
                if title == '':
                    title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
                icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data-lazy-src=['"]([^'^"]+?)['"]''')[0])
                desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>')[1])
                itemsTab.append({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc})

            if len(itemsTab):
                self.cacheLast[sectionTitle] = itemsTab
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sectionTitle, 'cache_key': sectionTitle})
                self.addDir(params)

    def listLastItems(self, cItem):
        printDBG("OtakuFR.listLastItems")
        cacheKey = cItem.get('cache_key', '')
        tab = self.cacheLast.get(cacheKey, [])
        for item in tab:
            params = dict(cItem)
            params.update(item)
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("OtakuFR.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        page = cItem.get('page', 1)

        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/anime-list/search/')
        post_data = {'txt_wpa_wgt_anm_sch_nme': searchPattern, 'cmd_wpa_wgt_anm_sch_sbm': 'Search'}
        self.listRankItems(cItem, 'explore_item', post_data)

    def getLinksForVideo(self, cItem):
        printDBG("OtakuFR.getLinksForVideo [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        urlTab = []
        data = self.cm.ph.getDataBeetwenMarkers(data, '<h3 style="text-align:', '</div>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            playerUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(playerUrl):
                continue
            urlTab.append({'name': self.cleanHtmlStr(item), 'url': playerUrl, 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("OtakuFR.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        sts, data = self.getPage(videoUrl)
        if not sts:
            return []

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="vdo_wrp">', '</div>')[1]
        videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])

        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL == None:
            #rm(self.COOKIE_FILE)
            self.selectDomain()

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'list_abc':
            self.listABC(self.currItem, 'list_abc_items')
        elif category == 'list_abc_items':
            self.listABCItems(self.currItem, 'explore_item')
        elif category == 'list_rank_items':
            self.listRankItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)

        elif category == 'list_programs':
            self.listPrograms(self.currItem, 'list_sort_filter')
        elif category == 'list_sort_filter':
            self.listSortFilters(self.currItem, 'list_items')

        elif category == 'list_last':
            self.listLast(self.currItem, 'list_last_items')
        elif category == 'list_last_items':
            self.listLastItems(self.currItem)
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
        CHostBase.__init__(self, OtakuFR(), True, [])
