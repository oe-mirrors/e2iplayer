# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
###################################################


def gettytul():
    return 'https://www.worldfree4u.ws/'


class WorldFree4u(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'worldfree4u.ws', 'cookie': 'worldfree4u.ws.cookie'})
        self.defaultParams = {'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'https://www.worldfree4u.ws/themes/logo.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'pl,en-US;q=0.7,en;q=0.3', 'Accept-Encoding': 'gzip, deflate'}

        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = None
        self.cacheFilters = {}
        self.cacheFiltersKey = []
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('LATEST'), 'url': self.getFullUrl('/seeAll/latestMovies/')},
                             {'category': 'list_items', 'title': _('RECENT'), 'url': self.getFullUrl('/seeAll/recentAdded/')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

        return self.cm.getPage(baseUrl, addParams, post_data)

    def selectDomain(self):
        self.MAIN_URL = 'https://www.worldfree4u.ws/'

    def listMainMenu(self, cItem, nextCategory):
        printDBG("WorldFree4u.listMainMenu")
        self.fillCacheFilters()

        for item in self.cacheFiltersKey:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': item, 'category': nextCategory, 'f_key': item})
            self.addDir(params)

        self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})

    def fillCacheFilters(self):
        self.cacheFilters = {}
        self.cacheFiltersKey = []

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'dropdown'), ('</ul', '>'))
        for item in data:
            tabItems = []
            item = item.split('<ul', 1)
            if len(item) != 2:
                continue
            filterName = self.cleanHtmlStr(item[0])
            item = self.cm.ph.getAllItemsBeetwenMarkers(item[1], '<li', '</li>')
            for it in item:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(it, '''href=['"]([^'^"]+?)['"]''')[0])
                if url.endswith('/1'):
                    url = url[:-1]
                title = self.cleanHtmlStr(it)
                tabItems.append({'title': title, 'url': url})
            if len(tabItems):
                self.cacheFilters[filterName] = tabItems
                self.cacheFiltersKey.append(filterName)

    def listFilters(self, cItem, nextCategory):
        printDBG("WorldFree4u.listFilters")
        key = cItem.get('f_key', '')
        tab = self.cacheFilters.get(key, [])

        for item in tab:
            params = dict(cItem)
            params.update(item)
            params.update({'good_for_fav': False, 'category': nextCategory})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("WorldFree4u.listItems")
        url = cItem['url']
        page = cItem.get('page', 1)
        if page > 1 or url[-1] == '/':
            if url[-1] != '/':
                url += '/'
            url += str(page)

        sts, data = self.getPage(url)
        if not sts:
            return

        if '>View More</a>' in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'item'), ('</div', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)

            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon}
            self.addVideo(params)

        if nextPage and len(self.currList) > 0:
            params = dict(cItem)
            params.update({'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("WorldFree4u.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/search/' + urllib.quote(searchPattern))
        self.listItems(cItem)

    def getLinksForVideo(self, cItem, forEpisodes=False):
        printDBG("WorldFree4u.getLinksForVideo [%s]" % cItem)
        urlTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        url = ''
        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        params['header']['Referer'] = cItem['url']

        data = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<div[^>]+?movieFrame[^>]+?>'''), re.compile('''</div>'''))[1]
        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        if self.cm.isValidUrl(url):
            sts, data = self.getPage(url, params)
            if not sts:
                return []

            url = self.cm.meta['url']
            if 1 != self.up.checkHostSupport(url):
                printDBG(data)
                linksCandidates = []
                tmp = self.cm.ph.getDataBeetwenMarkers(data, 'sources:', ']')[1]
                linksCandidates = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '{', '}', False, False)
                linksCandidates.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, 'sources:', '}', False, False))
                linksCandidates.extend(self.cm.ph.getAllItemsBeetwenMarkers(data, 'file:', '}'))
                printDBG(">>")
                printDBG(linksCandidates)
                uniqueLinks = []
                for item in linksCandidates:
                    url = self.cm.ph.getSearchGroups(item, '''file['"]?\s*[=:]\s*['"]([^"^']+?)['"]''')[0]
                    if url.startswith('//'):
                        url = 'http:' + url
                    if not url.startswith('http'):
                        continue
                    if url in uniqueLinks or 'error' in url:
                        continue
                    uniqueLinks.append(url)

                    if 'mp4' in item:
                        type = self.cm.ph.getSearchGroups(item, '''[\s'"]type['"]?\s*[=:]\s*['"]([^"^']+?)['"]''')[0]
                        res = self.cm.ph.getSearchGroups(item, '''[\s'"]res['"]?\s*[=:]\s*['"]([^"^']+?)['"]''')[0]
                        label = self.cm.ph.getSearchGroups(item, '''[\s'"]label['"]?\s*[=:]\s*['"]([^"^']+?)['"]''')[0]
                        if label == '':
                            label = res
                        url = strwithmeta(url, {'Referer': cItem['url'], 'User-Agent': self.USER_AGENT})
                        urlTab.append({'name': '[{1}] {0}'.format(type, label), 'url': url})
                    elif 'mpegurl' in item:
                        url = strwithmeta(url, {'iptv_proto': 'm3u8', 'Referer': cItem['url'], 'Origin': urlparser.getDomain(cItem['url'], False), 'User-Agent': self.USER_AGENT})
                        tmpTab = getDirectM3U8Playlist(url, checkExt=True, checkContent=True)
                        urlTab.extend(tmpTab)

        if 1 == self.up.checkHostSupport(url) and 0 == len(urlTab):
            urlTab = self.up.getVideoLinkExt(url)
        else:
            tmpUrlTab = []
            params['max_data_size'] = 0
            for item in urlTab:
                tmp = []
                if 1 == self.up.checkHostSupport(item['url']):
                    sts = self.getPage(item['url'], params)[0]
                    if not sts:
                        continue
                    contentType = self.cm.meta.get('content-type', '').lower()
                    if 'video' not in contentType and 'mpegurl' not in contentType and 'application' not in contentType:
                        tmp = self.up.getVideoLinkExt(item['url'])
                        tmpUrlTab.extend(tmp)
                        continue
                tmpUrlTab.append(item)
            urlTab = tmpUrlTab

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("WorldFree4u.getArticleContent [%s]" % cItem)
        retTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return retTab

        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h3>', '</h3>')[1])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''<div[^>]+?class=['"]desc['"][^>]*?>'''), re.compile('''</div>'''))[1])
        icon = self.cm.ph.getDataBeetwenMarkers(data, 'mvic-thumb', '>')[1]
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(icon, '''url\(\s*['"]([^'^"]+?\.jpg[^'^"]*?)['"]''', 1, True)[0])

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', '')

        descData = self.cm.ph.getDataBeetwenMarkers(data, '<div class="mvic-info">', '<div class="clearfix">', False)[1]
        descData = self.cm.ph.getAllItemsBeetwenMarkers(descData, '<p', '</p>')
        descTabMap = {"director": "director",
                      "actor": "actors",
                      "genre": "genre",
                      "country": "country",
                      "release": "released",
                      "duration": "duration",
                      "quality": "quality",
                      "imdbratings": "imdb_rating"}

        otherInfo = {}
        for item in descData:
            item = item.split('</strong>')
            if len(item) < 2:
                continue
            key = self.cleanHtmlStr(item[0]).replace(':', '').replace(' ', '').strip().lower()
            val = self.cleanHtmlStr(item[1])
            if key == 'IMDb':
                val += ' IMDb'
            if key in descTabMap:
                try:
                    otherInfo[descTabMap[key]] = val
                except Exception:
                    continue

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

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
            self.listMainMenu({'name': 'category'}, 'list_filter')
        elif category.startswith('list_filter'):
            self.listFilters(self.currItem, 'list_items')
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
        CHostBase.__init__(self, WorldFree4u(), True, [])

    def withArticleContent(self, cItem):
        if cItem['type'] != 'video':
            return False
        return True
