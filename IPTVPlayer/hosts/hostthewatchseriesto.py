# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
###################################################
# FOREIGN import
###################################################
import re
import base64
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.swatchseries_web_proxy_gateway = ConfigSelection(default="auto", choices=[("auto", _("Auto")), ("always", _("Always")), ("never", _("Never"))])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use web proxy gateway"), config.plugins.iptvplayer.swatchseries_web_proxy_gateway))
    return optionList
###################################################


def gettytul():
    return 'https://swatchseries.to/'


class TheWatchseriesTo(CBaseHostClass):
    DOMAIN = 'www1.swatchseries.to'
    MAIN_URL = 'https://%s/' % DOMAIN
    SEARCH_URL = MAIN_URL + 'search/'
    DEFAULT_ICON = "https://%s/templates/default/images/apple-touch-icon.png" % DOMAIN

    HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': MAIN_URL}
    AJAX_HEADER = dict(HEADER)
    AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

    MAIN_CAT_TAB = [{'icon': DEFAULT_ICON, 'category': 'list_series', 'title': _('Series list'), 'url': MAIN_URL + 'series'},
                    {'icon': DEFAULT_ICON, 'category': 'episodes', 'title': _('Popular Episodes'), 'url': MAIN_URL + 'new'},
                    {'icon': DEFAULT_ICON, 'category': 'episodes', 'title': _('Newest Episodes'), 'url': MAIN_URL + 'latest'},
                    {'icon': DEFAULT_ICON, 'category': 'categories', 'title': _('All A-Z'), 'url': MAIN_URL + 'letters/A'},
                    {'icon': DEFAULT_ICON, 'category': 'categories', 'title': _('Genres'), 'url': MAIN_URL + 'genres/action'},
                    {'icon': DEFAULT_ICON, 'category': 'search', 'title': _('Search'), 'search_item': True},
                    {'icon': DEFAULT_ICON, 'category': 'search_history', 'title': _('Search history')}]

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'TheWatchseriesTo.tv', 'cookie': 'thewatchseriesto.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.seasonCache = {}
        self.cacheLinks = {}
        self.needProxy = None

    def isNeedProxy(self):
        val = config.plugins.iptvplayer.swatchseries_web_proxy_gateway.value
        if val == 'always':
            return True
        elif val == 'never':
            return False

        if self.needProxy == None:
            sts, data = self.cm.getPage(self.MAIN_URL)
            if sts and '/series"' in data:
                self.needProxy = False
            else:
                self.needProxy = True
        return self.needProxy

    def getPage(self, url, params={}, post_data=None):
        HTTP_HEADER = dict(self.HEADER)
        params.update({'header': HTTP_HEADER})

        if self.isNeedProxy() and ('thewatchseries.to' in url or 'watch-series.to' in url or 'the-watch-series.to' in url or self.DOMAIN in url):
            proxy = 'http:/securefor.com/browse.php?u={0}&b=4'.format(urllib_quote(url, ''))
            params['header']['Referer'] = proxy + '&f=norefer'
            params['header']['Cookie'] = 'flags=2e5;'
            url = proxy
        sts, data = self.cm.getPage(url, params, post_data)
        if sts and None == data:
            sts = False
        return sts, data

    def getIconUrl(self, url):
        url = self.getFullUrl(url)
        if self.isNeedProxy() and ('thewatchseries.to' in url or 'watch-series.to' in url or 'the-watch-series.to' in url or self.DOMAIN in url):
            proxy = 'http://securefor.com/browse.php?u={0}&b=4&f=norefer'.format(urllib_quote(url, ''))
            params = {}
            params['User-Agent'] = self.HEADER['User-Agent'],
            params['Referer'] = proxy
            params['Cookie'] = 'flags=2e5;'
            url = strwithmeta(proxy, params)
        return url

    def getFullUrl(self, url):
        if self.isNeedProxy() and ('securefor.com' in url or '/browse.php' in url):
            url2 = urllib_unquote(self.cm.ph.getSearchGroups(url + '&', '''\?u=(http[^&]+?)&''')[0]).replace('&amp;', '&')
            printDBG("[%s] --> [%s]" % (url, url2))
            url = url2
        return CBaseHostClass.getFullUrl(self, url)

    def cleanHtmlStr(self, data):
        data = data.replace('&nbsp;', ' ')
        data = data.replace('&nbsp', ' ')
        return CBaseHostClass.cleanHtmlStr(data)

    def replacewhitespace(self, data):
        data = data.replace(' ', '%20')
        return CBaseHostClass.cleanHtmlStr(data)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("TheWatchseriesTo.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if type == 'dir':
                self.addDir(params)
            else:
                self.addVideo(params)

    def listCategories(self, cItem, nextCategory):
        printDBG("TheWatchseriesTo.listCategories")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination"', '</ul>', False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')

        for item in data:
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''', 1)[0]
            url = self.getFullUrl(url)
            if not url.startswith('http') or 'latest' in url:
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url, 'page': 0})
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("TheWatchseriesTo.listItems")
        page = cItem.get('page', 1)
        post_data = cItem.get('post_data', None)
        url = cItem['url']

        if cItem.get('page', 0) > 0:
            if not url.endswith('/'):
                url += '/'
            if '/search/' in url:
                url += 'page/'
            url += '%d' % page

        sts, data = self.getPage(url, {}, post_data)
        if not sts:
            return

        nextPage = self.cm.ph.getAllItemsBeetwenMarkers(data, '<ul class="pagination"', '</ul>', False)
        if len(nextPage):
            nextPage = nextPage[-1]
        else:
            nextPage = ''
        if '>{0}<'.format(page + 1) in nextPage:
            nextPage = True
        else:
            nextPage = False

        mainMarker = '<ul class="listings">'
        if mainMarker in data:
            data = self.cm.ph.getDataBeetwenMarkers(data, mainMarker, '<br class="clear"')[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
            ta = False
        else:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div style="float:left; margin-right:10px;">', 'Latest Episode:', False)
            ta = True
        for item in data:
            icon = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
            icon = self.getFullUrl(icon)
            if icon == '':
                icon = cItem['icon']
            if ta:
                item = item.split('<div valign="top" style="padding-left: 10px;">')[-1]
            if 'category-item-ad' in item or 'Latest Episode' in item:
                continue
            url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
            if url == '':
                continue
            title = self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0]
            if title == '':
                title = item.split('<span class="epnum"')[0]
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="info">', '</div>', False)[1])
            if desc == '':
                desc = self.cleanHtmlStr(item)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': self.cleanHtmlStr(title), 'url': self.getFullUrl(url), 'icon': icon, 'desc': desc})

            if nextCategory == 'video' or '/episode/' in url:
                self.addVideo(params)
            else:
                self.addDir(params)
        if nextPage:
                params = dict(cItem)
                params.update({'title': _('Next page'), 'page': page + 1})
                self.addDir(params)

    def listSeasons(self, cItem, nextCateogry):
        printDBG("TheWatchseriesTo.listSeasons")
        self.seasonCache = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        seasons = self.cm.ph.getAllItemsBeetwenMarkers(data, '<h2 class="lists"', '</ul>')
        for season in seasons:
            seasonName = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(season, 'itemprop="name">', '</span>', False)[1])
            seasonNum = self.cm.ph.getSearchGroups(seasonName + '|', '''Season\s+?([0-9]+?)[^0-9]''', 1, True)[0]

            episodesTab = []
            data = self.cm.ph.getAllItemsBeetwenMarkers(season, '<li ', '</li>')
            for item in data:
                if '(0 links)' in item:
                    continue
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(item, re.compile('itemprop="name"[^>]*?>'), re.compile('</span>'), False)[1])
                url = self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0]
                episodeNum = self.cm.ph.getSearchGroups(title + '|', '''Episode\s+?([0-9]+?)[^0-9]''', 1, True)[0]
                printDBG(">> e[%s] s[%s]" % (episodeNum, seasonNum))
                if '' != episodeNum and '' != seasonNum:
                    title = 's%se%s' % (seasonNum.zfill(2), episodeNum.zfill(2)) + ' - ' + title.replace('Episode %s' % episodeNum, '')
                params = dict(cItem)
                params.update({'good_for_fav': True, 'title': '{0}: {1}'.format(cItem['title'], title), 'url': self.getFullUrl(url), 'desc': self.cleanHtmlStr(item)})
                episodesTab.append(params)

            if len(episodesTab):
                self.seasonCache[seasonName] = episodesTab
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCateogry, 'title': seasonName, 'season_key': seasonName})
                self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("TheWatchseriesTo.listEpisodes")
        tab = self.seasonCache.get(cItem['season_key'], [])
        self.listsTab(tab, cItem, 'video')

    def getLinksForVideo(self, cItem):
        printDBG("TheWatchseriesTo.getLinksForVideo [%s]" % cItem)
        urlTab = []

        if len(self.cacheLinks.get(cItem['url'], [])):
            return self.cacheLinks[cItem['url']]

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        data = ph.findall(data, ('<tr', '>', 'download_link_'), '</tr>')
        for item in data:
            host = ph.search(item, '''"download_link_([^'^"]+?)['"]''')[0]
            #if self.up.checkHostSupport('http://'+host+'/') != 1: continue
#            printDBG(item)
#            printDBG('------')
            url = ''
            tmp = ph.findall(item, '<a', '</a>')
            for it in tmp:
                if self.isNeedProxy():
                    url = urllib_unquote(ph.search(it, '''href=['"][^'^"]*?%3Fr%3D([^'^"^&]+?)['"&]''')[0])
                else:
                    url = ph.search(it, '''href=['"][^'^"]*?\?r=([^'^"]+?)['"]''')[0]
                if url == '':
                    continue
                try:
                    url = base64.b64decode(url)
                except Exception:
                    continue
                break
#            if url == '': continue
            if 'http' not in url:
                url = self.cm.ph.getSearchGroups(item, '''['"]Delete\slink\s(http.+?)['"]''')[0]
            if self.up.checkHostSupport(url) != 1:
                continue
            url = strwithmeta(self.getFullUrl(url), {'Referer': self.cm.meta['url']})
            urlTab.append({'name': host, 'url': url, 'need_resolve': 1})
        if len(urlTab):
            self.cacheLinks[cItem['url']] = urlTab
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("TheWatchseriesTo.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        for key in self.cacheLinks:
            for idx in range(len(self.cacheLinks[key])):
                if self.cacheLinks[key][idx]['url'] == videoUrl:
                    self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        if videoUrl.startswith('http'):
            urlTab = self.up.getVideoLinkExt(videoUrl)
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TheWatchseriesTo.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.SEARCH_URL + urllib_quote(searchPattern)
        self.listItems(cItem, 'list_seasons')

    def getFavouriteData(self, cItem):
        printDBG('TheWatchseriesTo.getFavouriteData')
        params = {'type': cItem['type'], 'category': cItem.get('category', ''), 'title': cItem['title'], 'url': cItem['url'], 'desc': cItem['desc'], 'icon': cItem['icon']}
        return json_dumps(params)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'categories':
            self.listCategories(self.currItem, 'list_series')
        elif category == 'list_series':
            self.listItems(self.currItem, 'list_seasons')
        elif category == 'list_seasons':
            self.listSeasons(self.currItem, 'list_episodes')
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        elif category == 'episodes':
            self.listItems(self.currItem, 'video')
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
        CHostBase.__init__(self, TheWatchseriesTo(), True)
