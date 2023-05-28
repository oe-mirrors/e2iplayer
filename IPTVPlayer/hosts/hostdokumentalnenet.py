# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.plusdede_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.plusdede_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.plusdede_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.plusdede_password))
    return optionList
###################################################


def gettytul():
    return 'https://dokumentalne.net/'


class DokumentalneNET(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'dokumentalne.net', 'cookie': 'dokumentalne.net.cookie'})
        self.DEFAULT_ICON_URL = 'https://dokumentalne.net/wp-content/uploads/2016/11/dokumentalne_logo_1.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://dokumentalne.net/'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.MAIN_CAT_TAB = [{'category': 'list_categories', 'title': 'Kategorie', 'url': self.getMainUrl()},

                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]

    def getFullUrl(self, url):
        return CBaseHostClass.getFullUrl(self, url).replace('&#038;', '&')

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(url)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listCategories(self, cItem, nextCategory):
        printDBG("KinoPodAniolemPL.listCategories [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<aside', '>', 'categories'), ('</aside', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '</div>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

        if len(self.currList):
            item = self.currList[-1]
            del self.currList[-1]
            self.currList.insert(0, item)

    def listSort(self, cItem, nextCategory):
        printDBG("KinoPodAniolemPL.listSort [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'view-sortby'), ('</div', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listMainMenu(self, cItem, nextCategory):
        printDBG("DokumentalneNET.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("DokumentalneNET.listItems [%s]" % cItem)
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'rel="next"'), ('</a', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^'^"]+?)['"]''')[0])

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>', 'post-item'), ('</article', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''[\s'"](https?://[^'^"^\s]+?)\s*300w''')[0].strip())
            if icon == '':
                icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
            desc = []
            tmp = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'posted-on '), ('</div', '>'), False)[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)
            desc = ' | '.join(desc)
            desc += '[/br]' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'excerpt '), ('</div', '>'), False)[1])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addVideo(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("DokumentalneNET.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        if 1 == cItem.get('page', 1):
            cItem['url'] = self.getFullUrl('/?s=') + urllib_quote_plus(searchPattern)
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("DokumentalneNET.getLinksForVideo [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'player-embed'), ('</div', '>'))[1]
        videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        retTab = self.up.getVideoLinkExt(videoUrl)

        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<source', '>', False, False)
        for item in tmp:
            if 'video/mp4' in item:
                url = self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0]
                retTab.append({'name': self.up.getDomain(url), 'url': url})

        if len(retTab) == 0:
            tmp = re.compile('''['">\s](https?://[^'^"^<^\s]+?\.mp4)''').findall(data)
            for url in tmp:
                retTab.append({'name': self.up.getDomain(url), 'url': url})

        return retTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'}, 'list_genres')
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_sort')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, DokumentalneNET(), True, [])
