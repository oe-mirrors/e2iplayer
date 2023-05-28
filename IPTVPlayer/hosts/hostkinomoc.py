# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, checkWebSiteStatus
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
import base64
###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################


def gettytul():
    return 'https://kinomoc.com/'


class Kinomoc(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kinomoc.com', 'cookie': 'kinomoc.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://kinomoc.com'
        self.DEFAULT_ICON_URL = 'https://kinomoc.com/templates/111/icon/192x192.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}
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
        printDBG("Kinomoc.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Movies'), 'url': self.getFullUrl('/filmy/')},
#                       {'category': 'list_items', 'title': _('Movies') + ' ENG', 'url': self.getFullUrl('/quality/filmy-w-wersji-eng/')},
#                       {'category': 'list_items', 'title': _('Children'), 'url': self.getFullUrl('/genre/anime-bajki/')},
                        {'category': 'list_items', 'title': _('Series'), 'url': self.getFullUrl('/serials/')},
#                       {'category': 'list_years', 'title': _('Filter By Year'), 'url': self.getFullUrl('/filmy-online-pl/')},
                        {'category': 'list_cats',  'title': _('Movies genres'), 'url': self.getFullUrl('/filmy/')},
#                       {'category':'list_az',        'title': _('Alphabetically'),    'url':self.MAIN_URL},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    ###################################################
    def _fillMovieFilters(self, cItem):
        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        # fill sort
#        dat = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'aria-labelledby="filter-sorting"'), ('</div', '>'))[1]
#        dat = ' '.join(dat.split())
#        dat = re.compile('<li[^>]+?value="([^"]+?)".*?>(.+?)</li>').findall(dat)
#        for item in dat:
#            self.cacheMovieFilters['sort'].append({'title': self.cleanHtmlStr(item[1]), 'sort': item[0]})

#        sts, data = self.getPage(self.MAIN_URL)
#        if not sts: return

        # fill cats
        dat = re.compile('<li><a[^>]*?href="([^"]+?/filmy/[^"]+?)"[^>]*?>(.+?)</a>').findall(data)
        for item in dat:
            self.cacheMovieFilters['cats'].append({'title': self.cleanHtmlStr(item[1]), 'url': item[0]})

        # fill years
#        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="filter-year"', '</ul>', False)[1]
#        dat = re.compile('<li[^>]+?data-id="([^"]+?)".*?<a[^>]*?>(.+?)</a>').findall(dat)
#        for item in dat:
#            self.cacheMovieFilters['years'].append({'title': self.cleanHtmlStr(item[1]), 'url': cItem['url'] + 'year:%s/' % item[0]})

        # fill az
#        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class=starting-letter>', '</ul>', False)[1]
#        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(dat)
#        for item in dat:
#            self.cacheMovieFilters['az'].append({'title': self.cleanHtmlStr(item[1]), 'url': self.getFullUrl(item[0])})

    ###################################################
    def listMovieFilters(self, cItem, category):
        printDBG("Kinomoc.listMovieFilters")

        filter = cItem['category'].split('_')[-1]
        self._fillMovieFilters(cItem)
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = []
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)

    def listsTab(self, tab, cItem, category=None):
        printDBG("Kinomoc.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("Kinomoc.listItems %s" % cItem)
        page = cItem.get('page', 1)

        url = cItem['url']
#        sort = cItem.get('sort', '')
#        if sort == '':
#            sort = 'null'
#        else:
#            sort = '{"sorting":"%s"}' % sort
#        url = url + '?filter=' + sort
        if page > 1:
            if '?story=' in url:
                url = url + '&search_start={0}'.format(page)
            else:
                url = url + 'page/{0}/'.format(page)

        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'navigation'), ('</div', '>'))[1]
        if '' != self.cm.ph.getSearchGroups(nextPage, '>(%s)<' % (page + 1))[0]:
            nextPage = True
        else:
            nextPage = False

        if '?story=' in cItem['url']:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>', 'movie-box'), ('</article', '>'))
        else:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>', 'movie-box m-info'), ('</article', '>'))

        for item in data:
#            printDBG("Kinomoc.listItems item %s" % item)
            item = item.replace(',Online za darmo', '')
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''data-src=['"]([^"^']+?)['"]''')[0])
            tmp = ' [' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'icon-hd'), ('</span', '>'), False)[1]) + ']'
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'name'), ('</div', '>'), False)[1]) + tmp
            desc = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'dtinfo right'), ('</article', '>'), False)[1]
            desc = '[/br]'.join(desc.split('</div>'))
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(desc, ('<div', '>', 'title'), ('</div', '>'), False)[1]).replace(',Online za darmo', '')
            desc = self.cleanHtmlStr(desc)
            if 'icon-voicer' in item:
                params = {'good_for_fav': True, 'category': 'list_seasons', 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addDir(params)
            else:
                params = {'good_for_fav': True, 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSeriesSeasons(self, cItem, nextCategory):
        printDBG("Kinomoc.listSeriesSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        serieDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'description'), ('<div', '>', 'home'))[1])
        id = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'playlists-ajax'), ('</div', '>'))[1]
        id = self.cm.ph.getSearchGroups(id, '''\sdata-news_id=['"]([^'^"]+?)['"]''')[0]
        printDBG("Kinomoc.listSeriesSeasons id [%s]" % id)
        sts, data = self.getPage(self.getFullUrl('/engine/ajax/controller.php?mod=playlists&news_id=%s&xfield=pl') % id)
        if not sts:
            return
        data = json_loads(data)
        data = data.get('response', '')
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'playlists-lists'), ('</div', '>'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenNodes(tmp, ('<li', '>'), ('</li', '>'))

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'playlists-videos'), ('</div', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>'), ('</li', '>'))

        for sItem in tmp:
            sTitle = self.cleanHtmlStr(sItem)
            sId = self.cm.ph.getSearchGroups(sItem, '''\sdata-id=['"]([^'^"]+?)['"]''')[0]
            tabItems = []
            for item in data:
                if sId not in item:
                    continue
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\sdata-file=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                tabItems.append({'title': '%s' % title, 'url': url, 'icon': cItem['icon'], 'desc': ''})
            if len(tabItems):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 'episodes': tabItems, 'icon': cItem['icon'], 'desc': serieDesc})
                self.addDir(params)

    def listSeriesEpisodes(self, cItem):
        printDBG("Kinomoc.listSeriesEpisodes [%s]" % cItem)
        episodes = cItem.get('episodes', [])
        cItem = dict(cItem)
        for item in episodes:
            self.addVideo(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Kinomoc.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/index.php?story=%s&do=search&subaction=search') % urllib_quote_plus(searchPattern)
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("Kinomoc.getLinksForVideo [%s]" % cItem)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])

        url = cItem['url']

        retTab = []

        params['header']['Referer'] = url
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'film-content'), ('</div', '>'))

        for item in tmp:
            id = self.cm.ph.getSearchGroups(item, '''id=['"]([^"^']+?)['"]''')[0]
            playerUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            tmp =  self.cm.ph.getDataBeetwenNodes(data, ('<li', '>', id), ('</li', '>'))[1]
            name = self.cleanHtmlStr(tmp)
            if playerUrl == '' or name == '':
                continue
            if 'active' in tmp:
                retTab.insert(0, {'name': name, 'url': strwithmeta(playerUrl, {'Referer': url}), 'need_resolve': 1})
            else:
                retTab.append({'name': name, 'url': strwithmeta(playerUrl, {'Referer': url}), 'need_resolve': 1})

        if len(retTab) < 1:
            retTab.append({'name': self.up.getDomain(url), 'url': strwithmeta(url, {'Referer': url}), 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("Kinomoc.getVideoLinks [%s]" % baseUrl)
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
        printDBG("Kinomoc.getArticleContent [%s]" % cItem)
        itemsList = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        title = cItem['title']
        icon = cItem.get('icon', '')
        desc = cItem.get('desc', '')

#        title = self.cm.ph.getDataBeetwenMarkers(data, '<title>', '</title>', True)[1]
#        if title.endswith('Online</title>'): title = title.replace('Online', '')
#        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(title, '''this\.src=['"]([^"^']+?)['"]''', 1, True)[0])
        desc = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'description'), ('<div', '>', 'home'))[1]
        data = ' '.join(data.split())
#        itemsList.append((_('Duration'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<dt>Czas trwania:</dt>', '</dd>', False)[1])))
#        itemsList.append((_('Genres'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<ul class="categories">', '</ul>', True)[1]).replace('Kategoria:', '')))

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
            rm(self.COOKIE_FILE)
            webState, MSG, ERR = checkWebSiteStatus(self.MAIN_URL, self.HTTP_HEADER, 5)
            if webState:
                self.listMainMenu({'name': 'category'})
            else:
                self.sessionEx.open(MessageBox, "%s: %s" % (_(MSG), ERR), type=MessageBox.TYPE_INFO, timeout=10)
        elif 'list_cats' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif 'list_years' == category:
            self.listMovieFilters(self.currItem, 'list_sort')
        elif 'list_az' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif 'list_sort' == category:
            self.listMovieFilters(self.currItem, 'list_items')
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
        CHostBase.__init__(self, Kinomoc(), True, [])

    def withArticleContent(self, cItem):
        return True
