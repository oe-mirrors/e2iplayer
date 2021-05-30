# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://wgrane.pl/'


class WgranePL(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'wgrane.pl.online', 'cookie': 'wgrane.pl.cookie'})

        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.MAIN_URL = 'http://www.wgrane.pl/'
        self.DEFAULT_ICON_URL = 'https://i.ytimg.com/vi/HpTrVOZVNhA/maxresdefault.jpg'

        self.defaultParams = {'with_metadata': True, 'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}
        self.cacheLinks = {}

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def getFullUrl(self, url, baseUrl=None):
        url = url.replace('&amp;', '&')
        return CBaseHostClass.getFullUrl(self, url, baseUrl)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("WgranePL.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'list_sort', 'title': 'Przeglądaj pliki', 'url': self.getFullUrl('/watch.html')},
                        {'category': 'categories', 'title': 'Kategorie', 'url': self.getFullUrl('/categories.html')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory):
        printDBG("WgranePL.listCategories")
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'window_title'), ('<div', '>', 'footer'), False)[1]

        data = re.compile('''<div[^>]+?class=['"]list['"][^>]*?>''').split(data)
        if len(data):
            del data[0]

        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<div', '</div>')
            if len(tmp):
                title = self.cleanHtmlStr(tmp[0])
                desc = []
                for it in tmp[1:]:
                    it = self.cleanHtmlStr(it)
                    if it != '':
                        desc.append(it)
                desc = '[/br]'.join(desc)
            else:
                if title == '':
                    title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''\stitle=['"]([^"^']+?)['"]''')[0])
                desc = self.cleanHtmlStr(item)
            if title == '':
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''\salt=['"]([^"^']+?)['"]''')[0])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

    def listSort(self, cItem, nextCategory):
        printDBG("WgranePL.listSort")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'window_menu'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        for item in data:
            title = self.cleanHtmlStr(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("WgranePL.listItems")
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'window_title'), ('<div', '>', 'footer'), False)[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pages'), ('</div', '>'), False)[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>\s*&raquo;\s*<''')[0]

        descObj = re.compile('''<br\s*?/>''', re.I)
        data = re.compile('''<div[^>]+?class=['"]list['"][^>]*?>''').split(data)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^"^'^\:]+?)['"]''')[0])
            if url == '':
                continue
            if 'playlist=' in url:
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])
                continue # playlists not supported now
            else:
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']*?video_picture[^"^']+?)['"]''')[0])
                if icon == '':
                    continue

            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'list_title'), ('</div', '>'), False)[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''\stitle=['"]([^"^']+?)['"]''')[0])
            if title == '':
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''\salt=['"]([^"^']+?)['"]''')[0])

            desc = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'list_detail'), ('</div', '>'), False)[1]
            desc = self.cleanHtmlStr(descObj.sub('[/br]', desc))

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            if 'playlist=' in url:
                params.update({'category': nextCategory})
                self.addDir(params)
            elif 'PlaylistItemAdd' in item:
                self.addVideo(params) # how to know if this is audio or video item?
            else:
                self.addPicture(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _("Next page"), 'url': self.getFullUrl(nextPage), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("WgranePL.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/watch.html?search=') + urllib.quote_plus(searchPattern)
        cItem['category'] = 'list_items'
        self.listItems(cItem, 'list_playlist')

    def getLinksForVideo(self, cItem):
        printDBG("WgranePL.getLinksForVideo [%s]" % cItem)
        urlTab = []

        if 'picture' == cItem['type']:
            icon = ''
            sts, data = self.getPage(cItem['url'])
            if sts:
                data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'FileContent'), ('<div', '>', 'ajaxWaitLinks'), False)[1]
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]+?src=['"]([^"^']*?download.php[^"^']+?)['"]''')[0])
            if icon == '':
                icon = cItem.get('icon', '')
            if icon != '':
                urlTab = [{'name': 'link', 'url': icon, 'need_resolve': 0}]
        else:
            urlTab = self.up.getVideoLinkExt(cItem['url'])
        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'main':
            self.listMainItems(self.currItem, 'list_items')
        elif category == 'categories':
            self.listCategories(self.currItem, 'list_sort')
        elif category == 'list_sort':
            self.listSort(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_playlist')
        elif category == 'list_playlist':
            self.listPlaylist(self.currItem)
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
        CHostBase.__init__(self, WgranePL(), True, favouriteTypes=[])
