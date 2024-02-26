# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, CSelOneLink
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
###################################################
# FOREIGN import
###################################################
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.kisscartoon_defaultformat = ConfigSelection(default="999999", choices=[("0", _("the worst")), ("360", "360p"), ("480", "480p"), ("720", "720p"), ("1080", "1080p"), ("999999", "the best")])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Default video quality:"), config.plugins.iptvplayer.kisscartoon_defaultformat))
    return optionList
###################################################


def gettytul():
    return 'https://kisscartoon.ac/'


class KissCartoonMe(CBaseHostClass):
    USER_AGENT = 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36'
    HEADER = {'User-Agent': USER_AGENT, 'Accept': 'text/html'}
    AJAX_HEADER = dict(HEADER)
    AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

    MAIN_URL = 'https://kisscartoon.ac/'
    DEFAULT_ICON_URL = "http://kisscartoon.bz/image/logo.png"

    MAIN_CAT_TAB = [{'category': 'home', 'title': _('Home'), 'url': MAIN_URL, },
                    {'category': 'list_cats', 'title': _('Catrtoon list'), 'url': MAIN_URL + 'CartoonList', },
                    {'category': 'search', 'title': _('Search'), 'search_item': True, },
                    {'category': 'search_history', 'title': _('Search history'), }]
    SORT_BY_TAB = [{'title': _('Sort by alphabet')},
                   {'title': _('Sort by popularity'), 'sort_by': 'MostPopular'},
                   {'title': _('Latest update'), 'sort_by': 'LatestUpdate'},
                   {'title': _('New cartoon'), 'sort_by': 'Newest'}]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kisscartoon.io', 'cookie': 'kisscartoonme.cookie'})
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheHome = {}
        self.cache = {}

    def _getFullUrl(self, url):
        if url == '':
            return url

        if url.startswith('.'):
            url = url[1:]

        if url.startswith('//'):
            url = 'https:' + url
        else:
            if url.startswith('/'):
                url = url[1:]
            if not url.startswith('http'):
                url = self.MAIN_URL + url

        url = self.cleanHtmlStr(url)
        url = self.replacewhitespace(url)
        newUrl = ''
        idx = 0
        while idx < len(url):
            if 128 < ord(url[idx]):
                newUrl += urllib_quote(url[idx])
            else:
                newUrl += url[idx]
            idx += 1
        return newUrl #.replace('¡', '%C2%A1')

    def getPage(self, baseUrl, params={}, post_data=None):
        params['cloudflare_params'] = {'domain': 'kisscartoon.es', 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': self._getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, params, post_data)

    def _urlWithCookie(self, url):
        url = self._getFullUrl(url)
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def cleanHtmlStr(self, data):
        data = data.replace('&nbsp;', ' ')
        data = data.replace('&nbsp', ' ')
        return CBaseHostClass.cleanHtmlStr(data).strip()

    def replacewhitespace(self, data):
        data = data.replace(' ', '%20')
        return CBaseHostClass.cleanHtmlStr(data)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("KissCartoonMe.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if type == 'dir' and 'video' != item.get('category', ''):
                self.addDir(params)
            else:
                self.addVideo(params)

    def _getItems(self, data, sp='', forceIcon=''):
        printDBG("listHome._getItems")
        if '' == sp:
            sp = '<div class="item_film_list">'
        data = data.split(sp)
        if len(data):
            del data[0]
        tab = []
        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=["']([^"^']+?)["']''')[0]
            if '' == url:
                continue
            title = self.cm.ph.getDataBeetwenMarkers(item, '<span class="title">', '</span>', False)[1]
            if '' == title:
                title = self.cm.ph.getDataBeetwenMarkers(item, '<a ', '</a>')[1]
            if forceIcon == '':
                icon = self.cm.ph.getSearchGroups(item, '''src=["']([^"^']+?)["']''')[0]
            else:
                icon = forceIcon
            desc = self.cm.ph.getDataBeetwenMarkers(item, '<p>', '</p>', False)[1]
            if '' == desc:
                desc = '<' + item
            tab.append({'good_for_fav': True, 'title': self.cleanHtmlStr(title), 'url': self._getFullUrl(url), 'icon': self._urlWithCookie(icon), 'desc': self.cleanHtmlStr(desc)})
        return tab

    def listHome(self, cItem, category):
        printDBG("listHome.listHome [%s]" % cItem)

        #http://kisscartoon.io/Home/GetNextUpdatedCartoon
        #POSTDATA {id:50, page:10}

        self.cacheHome = {}
        self.sortTab = []
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="tabmenucontainer"', '</div>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li>', '</li>')

        tabs = []
        for item in tmp:
            tabId = self.cm.ph.getSearchGroups(item, '''showTabData\('([^']+?)'\)''')[0]
            tabTitle = self.cleanHtmlStr(item)
            tabs.append({'id': tabId, 'title': tabTitle})

        printDBG(tabs)

        tmp2 = self.cm.ph.getDataBeetwenMarkers(data, '<div id="subcontent"', '<div class="clear">', False)[1]
        tmp2 = tmp2.split('<div id="tab-')
        if len(tmp2):
            del tmp2[0]
        for item in tmp2:
            # find tab id and title
            tabId = item[:item.find('"')].replace('-', '')
            cTab = None
            for tab in tabs:
                if tabId == tab['id']:
                    cTab = tab
                    break
            if cTab == None:
                printDBG('>>>>>>>>>>>>>>>>>> continue tabId[%s]' % tabId)
                continue
            # check for more item
            moreUrl = self.cm.ph.getSearchGroups(item, '''<a href="([^"]+?)">More\.\.\.</a>''')[0]
            if moreUrl != '':
                params = dict(cItem)
                params.update({'category': category, 'title': tab['title'], 'url': self._getFullUrl(moreUrl)})
                self.addDir(params)
                continue
            itemsTab = self._getItems(item)
            if len(itemsTab):
                self.cacheHome[tab['id']] = itemsTab
                params = dict(cItem)
                params.update({'category': 'list_cached_items', 'tab_id': tab['id'], 'title': tab['title']})
                self.addDir(params)

    def listCats(self, cItem, category):
        printDBG("KissCartoonMe.listCats [%s]" % cItem)
        self.cache = {}
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        # alphabet
        cacheKey = 'alphabet'
        self.cache[cacheKey] = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="alphabet', '</div>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a ', '</a>')
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, '''href="([^"]+?)"''')[0]
            if '://' not in url and not url.startswith('/'):
                url = 'CartoonList/' + url
            title = self.cleanHtmlStr(item)
            self.cache[cacheKey].append({'title': title, 'url': self._getFullUrl(url)})
        if len(self.cache[cacheKey]) > 0:
            params = dict(cItem)
            params.update({'category': category, 'title': _('Alphabetically'), 'cache_key': cacheKey})
            self.addDir(params)

        # left tab
        m1 = '<div class="rightBox'
        tmp = self.cm.ph.getDataBeetwenMarkers(data, m1, '<div style="clear', False)[1]
        tmp = tmp.split(m1)
        for item in tmp:
            catTitle = self.cm.ph.getDataBeetwenMarkers(item, '<div class="barTitle', '</div>', True)[1]
            if catTitle == '':
                continue
            self.cache[catTitle] = []
            tmp2 = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a ', '</a>')
            for item2 in tmp2:
                url = self.cm.ph.getSearchGroups(item2, '''href="([^"]+?)"''')[0]
                title = self.cleanHtmlStr(item2)
                desc = self.cm.ph.getSearchGroups(item2, '''title="([^"]+?)"''')[0]
                self.cache[catTitle].append({'title': title, 'desc': desc, 'url': self._getFullUrl(url)})

            if len(self.cache[catTitle]) > 0:
                params = dict(cItem)
                params.update({'category': category, 'title': self.cleanHtmlStr(catTitle), 'cache_key': catTitle})
                self.addDir(params)

    def listSubCats(self, cItem, category):
        printDBG("KissCartoonMe.listSubCats [%s]" % cItem)
        tab = self.cache[cItem['cache_key']]
        cItem = dict(cItem)
        cItem['category'] = category
        self.listsTab(tab, cItem)

    def _urlAppendPage(self, url, page, sortBy):
        if sortBy != '':
            if not url.endswith('/'):
                url += '/'
            url += sortBy + '/'
        if page > 1:
            if '?' in url:
                url += '&'
            else:
                url += '?'
            url += 'page=%d' % page
        return url

    def listItems(self, cItem, category):
        printDBG("KissCartoonMe.listItems [%s]" % cItem)
        page = cItem.get('page', 1)
        sort_by = cItem.get('sort_by', '')
        url = self._urlAppendPage(cItem['url'], page, sort_by)
        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = False
        if ('page=%d"' % (page + 1)) in data:
            nextPage = True

        #if '/Search/' in cItem['url']:
        #    m1 = '<div class="list-cartoon"'
        #else:
        m1 = '<div class="listing full"'

        data = self.cm.ph.getDataBeetwenMarkers(data, m1, '<script type', False)[1]
        data = self._getItems(data, '<div class="item_movies')

        params = dict(cItem)
        params.update({'category': category})
        self.listsTab(data, params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("KissCartoonMe.listEpisodes [%s]" % cItem)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        printDBG(data)

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="listing', '<div class="bigBarContainer', False)[1]
        data = self._getItems(data, '<h3>', cItem.get('icon', ''))
        data.reverse()
        params = dict(cItem)
        params.update({'category': 'video'})
        self.listsTab(data, params, 'video')

    def getLinksForVideo(self, cItem):
        printDBG("KissCartoonMe.getLinksForVideo [%s]" % cItem)
        urlTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return urlTab

        episodeId = self.cm.ph.getSearchGroups(data, r'''var\s*['"]?episode_id['"]?\s*=\s*['"]([0-9]+)['"]''')[0]
        url = self._getFullUrl('/ajax/anime/load_episodes')

        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = cItem['url']
        sts, data = self.getPage(url, params, post_data={'episode_id': episodeId})
        if not sts:
            return urlTab

        try:
            data = byteify(json.loads(data))
            if not data['status']:
                return urlTab
            url = data['value']
            if url.startswith('//'):
                url = 'https:' + url
            if not self.cm.isValidUrl(url):
                url = self.cm.ph.getSearchGroups(url, '''<iframe[^>]+?src=['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
                url = self._getFullUrl(url)
            url = strwithmeta(url, {'Referer': cItem['url']})
            urlTab.append({'name': 'default', 'url': url, 'need_resolve': 1})
        except Exception:
            printExc()

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("KissCartoonMe.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        referer = strwithmeta(videoUrl).meta.get('Referer', videoUrl)
        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        params['header']['Referer'] = referer

        sts, data = self.getPage(videoUrl, params)
        videoUrl = self.cm.meta.get('url', videoUrl)

        if 'kisscartoon' not in self.up.getDomain(videoUrl):
            return self.up.getVideoLinkExt(videoUrl)

        if not sts:
            return urlTab

        try:
            data = byteify(json.loads(data))
            printDBG(data)
            for item in data['playlist'][0].get('sources', []):
                if 'mp4' not in item['type']:
                    continue
                url = item['file']
                name = item['label']
                urlTab.append({'name': name, 'url': url, 'need_resolve': 0})

            for item in data['playlist']:
                url = item.get('file', '')
                type = url.split('?', 1)[0].rsplit('.', 1)[-1].lower()
                if self.cm.isValidUrl(url):
                    if type == 'mp4':
                        name = item.get('label', 'mp4')
                        urlTab.append({'name': name, 'url': url, 'need_resolve': 0})
                    else:
                        urlTab.extend(getDirectM3U8Playlist(url, checkContent=True))
        except Exception:
            printExc()

        if 0 < len(urlTab):
            max_bitrate = int(config.plugins.iptvplayer.kisscartoon_defaultformat.value)

            def __getLinkQuality(itemLink):
                try:
                    return int(self.cm.ph.getSearchGroups('|' + itemLink['name'] + '|', '[^0-9]([0-9]+?)[^0-9]')[0])
                except Exception:
                    return 0
            urlTab = CSelOneLink(urlTab, __getLinkQuality, max_bitrate).getBestSortedList()
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KissCartoonMe.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        url = self._getFullUrl('/Search/') + '?s=' + urllib_quote_plus(searchPattern)
        cItem['url'] = url
        self.listItems(cItem, 'list_episodes')

    def getFavouriteData(self, cItem):
        printDBG('CartoonME.getFavouriteData')
        params = dict(cItem)
        return json.dumps(params)

    def getLinksForFavourite(self, fav_data):
        printDBG('CartoonME.getLinksForFavourite')
        links = []
        try:
            try:
                cItem = byteify(json.loads(fav_data))
            except Exception:
                cItem = {'url': fav_data}
                pass
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('CartoonME.setInitListFromFavouriteItem')
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
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'home':
            self.listHome(self.currItem, 'list_items')
        elif category == 'list_cached_items':
            cItem = dict(self.currItem)
            cItem['category'] = 'list_episodes'
            self.listsTab(self.cacheHome.get(cItem.get('tab_id'), []), cItem)
        elif category == 'list_cats':
            self.listCats(self.currItem, 'list_sub_cats')
        elif category == 'list_sub_cats':
            if self.currItem.get('cache_key', '') == 'alphabet':
                self.listSubCats(self.currItem, 'list_items')
            else:
                self.listSubCats(self.currItem, 'list_sort_tab')
        elif category == 'list_sort_tab':
            cItem = dict(self.currItem)
            cItem['category'] = 'list_items'
            self.listsTab(self.SORT_BY_TAB, cItem)
        elif category == 'list_items':
            self.listItems(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, KissCartoonMe(), True, favouriteTypes=[]) #[CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
