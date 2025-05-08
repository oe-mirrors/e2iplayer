# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_unquote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################
# FOREIGN import
###################################################
import re
import base64
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, ConfigSelection, getConfigListEntry
###################################################

def gettytul():
    return 'https://playz.cc/'


class Playz(CBaseHostClass, CaptchaHelper):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Playz.online', 'cookie': 'playz.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://playz.cc/'
        self.DEFAULT_ICON_URL = 'https://playz.cc/wp-content/uploads/2022/10/playz_logo_whiteoff.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(url)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, cItem):
        printDBG("Playz.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Movies'), 'url': self.getFullUrl('/movies/')},
                        {'category': 'list_items', 'title': _('Series'), 'url': self.getFullUrl('/tvshows/')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listsTab(self, tab, cItem, category=None):
        printDBG("Playz.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("Playz.listItems %s" % cItem)

        url = cItem['url']

        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'current'), ('</a', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]+?>''')[0], self.MAIN_URL)

        if '?s=' in cItem['url']:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>'), ('</article', '>'))
        else:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'archive-content'), ('<footer', '>'))[1] # exclude header and footer
            data = data.split('<div class="poster">')[1:]

        for item in data:
#            printDBG("Playz.listItems item %s" % item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''')[0].replace('&quot;', '"'.replace('&amp;', '&')).replace('&#8211;', '-')
            desc = self.cleanHtmlStr(item)
            if 'tvshows' in url:
                params = {'good_for_fav': True, 'category': 'list_seasons', 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addDir(params)
            else:
                params = {'good_for_fav': True, 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addVideo(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': nextPage})
            self.addDir(params)

    def listSeriesSeasons(self, cItem, nextCategory):
        printDBG("Playz.listSeriesSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'se-c'), ('</ul', '>'))

        for sItem in data:
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(sItem, ('<span', '>', 'title'), ('</span', '>'))[1])
            if not sTitle:
                continue
            sItem = self.cm.ph.getAllItemsBeetwenMarkers(sItem, ('<li', '>'), ('</li', '>'))
            tabItems = []
            for item in sItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<a', '>'), ('</a', '>'))[1])
                tabItems.append({'title': '%s' % title, 'url': url, 'icon': icon, 'desc': ''})
            if len(tabItems):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 'episodes': tabItems, 'icon': cItem['icon'], 'desc': ''})
                self.addDir(params)

    def listSeriesEpisodes(self, cItem):
        printDBG("Playz.listSeriesEpisodes [%s]" % cItem)
        episodes = cItem.get('episodes', [])
        cItem = dict(cItem)
        for item in episodes:
            self.addVideo(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Playz.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/?s=%s') % urllib_quote_plus(searchPattern)
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("Playz.getLinksForVideo [%s]" % cItem)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])

        cUrl = cItem['url']
        url = cItem['url']

        retTab = []

        params['header']['Referer'] = cUrl
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'player-option'), ('</li', '>'))

        for item in data:
#            printDBG("Playz.getLinksForVideo item[%s]" % item)
            datanume = self.cm.ph.getSearchGroups(item, '''data-nume=['"]([^"^']+?)['"]''')[0]
            datapost = self.cm.ph.getSearchGroups(item, '''data-post=['"]([^"^']+?)['"]''')[0]
            url = 'https://playz.cc/wp-admin/admin-ajax.php'
            post_data = {'action': 'doo_player_ajax', 'post': datapost, 'nume': datanume, 'type': 'movie'}
            sts, data = self.getPage(url, params, post_data)
            if not sts:
                continue
            data = json_loads(data)
            printDBG("Playz.getLinksForVideo data[%s]" % data)
            playerUrl = data.get('embed_url', '')
            if '<iframe' in playerUrl:
                playerUrl = self.cm.ph.getSearchGroups(playerUrl, '''src=['"]([^"^']+?)['"]''')[0]
            name = self.up.getHostName(playerUrl)
            if playerUrl == '':
                continue
            if 'playz.cc' in playerUrl:
                playerUrl = self.cm.ph.getSearchGroups(playerUrl + '&', '''source=([^&]+?)&''')[0]
                playerUrl = urllib_unquote(playerUrl)
                retTab.append({'name': name, 'url': strwithmeta(playerUrl, {'Referer': cUrl}), 'need_resolve': 0})
            else:
                retTab.append({'name': name, 'url': strwithmeta(playerUrl, {'Referer': cUrl}), 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("Playz.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if baseUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        return self.up.getVideoLinkExt(baseUrl)

    def getArticleContent(self, cItem):
        printDBG("Playz.getArticleContent [%s]" % cItem)
        itemsList = []

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return []

        title = cItem['title']
        icon = cItem.get('icon', '')
        desc = cItem.get('desc', '')

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sheader'), ('<footer', '>'))[1]
        desc = self.cm.ph.getDataBeetwenNodes(data, ('<p', '>'), ('</p', '>'))[1]
        itemsList.append((_('Duration'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'duration'), ('</span', '>'))[1])))
        itemsList.append((_('Country'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<span', '>', 'country'), ('</span', '>'))[1])))
        itemsList.append((_('Genres'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sgeneros'), ('</div', '>'))[1])))

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', '')
        if desc == '':
            desc = cItem.get('desc', '')

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': {'custom_items_list': itemsList}}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

    #MAIN MENU
        if name == None and category == '':
#            rm(self.COOKIE_FILE)
            self.listMainMenu({'name': 'category'})
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_seasons':
            self.listSeriesSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listSeriesEpisodes(self.currItem)

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
        CHostBase.__init__(self, Playz(), True, [])

    def withArticleContent(self, cItem):
        return True
