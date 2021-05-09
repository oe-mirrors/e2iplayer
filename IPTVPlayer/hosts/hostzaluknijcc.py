# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import unescapeHTML
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
import base64
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://zaluknij.cc/'


class Zaluknij(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'zaluknij.cc', 'cookie': 'zaluknij.cc.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://zaluknij.cc/'
        self.DEFAULT_ICON_URL = 'https://zaluknij.cc/wp-content/uploads/2020/03/88173970_182374586540508_6257495783784841216_n-1.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urlparse.urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, cItem):
        printDBG("Zaluknij.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Movies') + ' PL', 'url': self.getFullUrl('/quality/filmy-w-wersji-pl/')},
                        {'category': 'list_items', 'title': _('Movies') + ' ENG', 'url': self.getFullUrl('/quality/filmy-w-wersji-eng/')},
                        {'category': 'list_items', 'title': _('Children'), 'url': self.getFullUrl('/genre/anime-bajki/')},
                        {'category': 'list_items', 'title': _('Series'), 'url': self.getFullUrl('/tvshows/')},
                        {'category': 'list_years', 'title': _('Filter By Year'), 'url': self.MAIN_URL},
#                        {'category':'list_cats',       'title': _('Movies genres'),  'url':self.getFullUrl('/filmy-online-pl/')},
#                        {'category':'list_az',        'title': _('Alphabetically'),    'url':self.MAIN_URL},
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
#        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="filter-sort"', '</ul>', False)[1]
#        dat = re.compile('<li[^>]+?data-sort="([^"]+?)".*?<a[^>]*?>(.+?)</a>').findall(dat)
#        for item in dat:
#            self.cacheMovieFilters['sort'].append({'title': self.cleanHtmlStr(item[1]), 'sort': item[0]})

#        sts, data = self.getPage(self.MAIN_URL)
#        if not sts: return

        # fill cats
#        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="filter-category"', '</ul>', False)[1]
#        dat = re.compile('<li[^>]+?data-id="([^"]+?)".*?<a[^>]*?>(.+?)</a>').findall(dat)
#        for item in dat:
#            self.cacheMovieFilters['cats'].append({'title': self.cleanHtmlStr(item[1]), 'url': cItem['url']+'category:%s/' % item[0]})

        # fill years
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="releases falsescroll"', '</ul>', False)[1]
        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(dat)
        for item in dat:
            self.cacheMovieFilters['years'].append({'title': self.cleanHtmlStr(item[1]), 'url': self.getFullUrl(item[0])})

        # fill az
#        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="glossary"', '</ul>', False)[1]
#        dat = re.compile('<a[^>]+?data-type="([^"]+?)"\sdata-glossary="([^"]+?)"[^>]*?>(.+?)</a>').findall(dat)
#        nonce = self.cm.ph.getDataBeetwenNodes(data, ('<script', '>', 'live_search-js-extra'), ('</script', '>'))[1]
#        nonce = self.cm.ph.getSearchGroups(nonce, '''"nonce":['"]([^"^']+?)['"]''')[0]
#        for item in dat:
#            self.cacheMovieFilters['az'].append({'title': self.cleanHtmlStr(item[2]), 'url': self.getFullUrl('wp-json/dooplay/glossary/?term=%s&nonce=%s&type=%s' % (item[1], nonce, item[0]))})

    ###################################################
    def listMovieFilters(self, cItem, category):
        printDBG("Zaluknij.listMovieFilters")

        filter = cItem['category'].split('_')[-1]
        self._fillMovieFilters(cItem)
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = []
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)

    def listsTab(self, tab, cItem, category=None):
        printDBG("Zaluknij.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("Zaluknij.listItems %s" % cItem)
        page = cItem.get('page', 1)

        url = cItem['url']
        if page > 1:
            url = url + '/page/{0}'.format(page)
        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        if '' != self.cm.ph.getSearchGroups(nextPage, 'page/(%s)[^0-9]' % (page + 1))[0]:
            nextPage = True
        else:
            nextPage = False

        if 'tvshows' in cItem['url']:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'archive-content'), ('<div', '>', 'pagination'))[1]

        if '?s=' in cItem['url']:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>'), ('</article', '>'))
        else:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<article', '>', 'item'), ('</article', '>'))

        for item in data:
#            printDBG("Zaluknij.listItems item %s" % item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = unescapeHTML(self.cm.ph.getSearchGroups(item, '''alt=['"]([^"^']+?)['"]''')[0]).encode('UTF-8')
            desc = self.cleanHtmlStr(item)
            if '/tvshows/' in url:
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
        printDBG("Zaluknij.listSeriesSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        serieDesc = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'info'), ('</p', '>'))[1]
        serieDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(serieDesc, ('<p', '>'), ('</p', '>'))[1])
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'se-q'), ('</ul', '>'))

        for sItem in data:
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(sItem, ('<span', '>', 'title'), ('</span', '>'))[1])
            if not sTitle:
                continue
            sItem = self.cm.ph.getAllItemsBeetwenMarkers(sItem, '<a', '</a>')
            tabItems = []
            for item in sItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                tabItems.append({'title': '%s' % title, 'url': url, 'icon': cItem['icon'], 'desc': ''})
            if len(tabItems):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 'episodes': tabItems, 'icon': cItem['icon'], 'desc': serieDesc})
                self.addDir(params)

    def listSeriesEpisodes(self, cItem):
        printDBG("Zaluknij.listSeriesEpisodes [%s]" % cItem)
        episodes = cItem.get('episodes', [])
        cItem = dict(cItem)
        for item in episodes:
            self.addVideo(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Zaluknij.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/?s=%s') % urllib.quote_plus(searchPattern)
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("Zaluknij.getLinksForVideo [%s]" % cItem)

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
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<tr', '>', 'link'), ('</tr', '>'))

        for item in data:
#            printDBG("Zaluknij.getLinksForVideo item[%s]" % item)
            playerUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            params = dict(self.defaultParams)
            params['max_data_size'] = 0
            params['no_redirection'] = True
            sts, data = self.getPage(playerUrl, params)
            playerUrl = self.cm.meta.get('location', '')
            name = self.up.getHostName(playerUrl)
            if playerUrl == '':
                continue
            retTab.append({'name': name, 'url': strwithmeta(playerUrl, {'Referer': url}), 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("Zaluknij.getVideoLinks [%s]" % baseUrl)
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
        printDBG("Zaluknij.getArticleContent [%s]" % cItem)
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
        desc = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'info'), ('</p', '>'))[1]
#        itemsList.append((_('Duration'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<dt>Czas trwania:</dt>', '</dd>', False)[1])))
#        itemsList.append((_('Genres'), self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<ul class="genres">', '</ul>', True)[1])))

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
            self.listMainMenu({'name': 'category'})
        elif 'list_cats' == category:
            self.listMovieFilters(self.currItem, 'list_items')
        elif 'list_years' == category:
            self.listMovieFilters(self.currItem, 'list_items')
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
        CHostBase.__init__(self, Zaluknij(), True, [])

    def withArticleContent(self, cItem):
        return True
