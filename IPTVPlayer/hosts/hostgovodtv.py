# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'https://govod.tv/'


class govodtv(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'govod.tv', 'cookie': 'govod.tv.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://govod.tv/'
        self.DEFAULT_ICON_URL = 'https://govod.tv/images/logo-dark.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getFullIconUrl(self, icon, baseUrl=None):
        return CBaseHostClass.getFullIconUrl(self, icon.replace('.webp', '.jpg').replace('/pictures/posters/t', '/posters/'), baseUrl)

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
        printDBG("govodtv.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'list_sort', 'title': _('Movies'), 'url': self.getFullUrl('/filmy-online')},
                        {'category': 'list_sort', 'title': _('Series'), 'url': self.getFullUrl('/seriale-online')},
                        {'category': 'list_items', 'title': _('News'), 'url': self.getFullUrl('/najnowsze')},
#                        {'category':'list_items',     'title': _('Highlights'),     'url':self.getFullUrl('/polecane/')},
#                        {'category':'list_years',     'title': _('Movies by year'), 'url':self.MAIN_URL},
                        {'category': 'list_cats', 'title': _('Categories'), 'url': self.MAIN_URL},
#                        {'category':'list_az',        'title': _('Alphabetically'), 'url':self.MAIN_URL},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    ###################################################
    def _fillMovieFilters(self, cItem):
        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}

        sts, data = self.getPage(self.getFullUrl(cItem['url']))
        if not sts:
            return

        # fill sort
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="fc-main-list">', '</ul>', False)[1]
        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(re.sub('\s+', ' ', dat))
        for item in dat:
            self.cacheMovieFilters['sort'].append({'title': self.cleanHtmlStr(item[1]).replace('ych', 'e'), 'url': self.getFullUrl(item[0])})

#        sts, data = self.getPage(self.MAIN_URL)
#        if not sts: return

        # fill cats
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="sub-menu">', '</ul>', False)[1]
        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(re.sub('\s+', ' ', dat))
        for item in dat:
            self.cacheMovieFilters['cats'].append({'title': self.cleanHtmlStr(item[1]), 'url': self.getFullUrl(item[0])})

        # fill years
#        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="dropdown-menu year-dropdown"', '</ul>', False)[1]
#        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(dat)
#        for item in dat:
#            self.cacheMovieFilters['years'].append({'title': self.cleanHtmlStr(item[1]), 'url': self.getFullUrl(item[0])})

        # fill az
#        dat = self.cm.ph.getDataBeetwenMarkers(data, '<div class="filters-links">', '</div>', False)[1]
#        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(dat)
#        for item in dat:
#            self.cacheMovieFilters['az'].append({'title': self.cleanHtmlStr(item[1]), 'url': self.getFullUrl(item[0])})

    ###################################################
    def listMovieFilters(self, cItem, category):
        printDBG("govodtv.listMovieFilters")

        filter = cItem['category'].split('_')[-1]
        if 0 == len(self.cacheMovieFilters[filter]) or filter == 'sort':
            self._fillMovieFilters(cItem)
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = []
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)

    def listsTab(self, tab, cItem, category=None):
        printDBG("govodtv.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("govodtv.listItems %s" % cItem)
        page = cItem.get('page', 1)

        url = cUrl = cItem['url']
        if '?' in url:
            url += '&'
        else:
            url += '?'
        if page > 1:
            url = url + 'page={0}'.format(page)
        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        nextPage = self.cm.ph.getDataBeetwenNodes(nextPage, ('<a', '>', 'next'), ('</a', '>'))[1]
        if '' != self.cm.ph.getSearchGroups(nextPage, 'page=(%s)[^0-9]' % (page + 1))[0]:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'ml-item'), ('</i', '>'))

        for item in data:
#            printDBG("govodtv.listItems item %s" % item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h3', '>'), ('</h3', '>'), False)[1])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>'), ('</i', '>'), False)[1])
            if '/serial/' in url:
                params = {'good_for_fav': True, 'category': 'list_seasons', 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addDir(params)
            else:
                params = {'good_for_fav': True, 'url': url, 'title': title, 'desc': desc, 'icon': icon}
                self.addVideo(params)

        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': cUrl, 'page': page + 1})
            self.addDir(params)

    def listSeriesSeasons(self, cItem, nextCategory):
        printDBG("govodtv.listSeriesSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        serieTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<h1', '>', 'itemprop="name"'), ('</h1', '>'))[1])
        serieDesc = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'description'), ('</div', '>'))[1]
        serieDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(serieDesc, ('<p', '>'), ('</p', '>'))[1])
        serieIcon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''<img itemprop="image".*src=['"]([^'^"]+?)['"]''')[0])
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'season-'), ('</table', '>'))

        for sItem in data:
            sTitle = self.cm.ph.getSearchGroups(sItem, '''<div id=['"]([^'^"]+?)['"]''')[0].replace('season', _('Season')).replace('-', ' ')
            if not sTitle:
                continue
            sItem = self.cm.ph.getDataBeetwenNodes(sItem, ('<tbody', '>'), ('</tbody', '>'))[1]
            sItem = self.cm.ph.getAllItemsBeetwenMarkers(sItem, '<tr', '</tr>')
            tabItems = []
            for item in sItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\sdata-href=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<td', '>'), ('</td', '>'), False)[1])
                tabItems.append({'title': '%s' % title, 'url': url, 'icon': serieIcon, 'desc': ''})
            if len(tabItems):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 'episodes': tabItems, 'icon': serieIcon, 'desc': serieDesc})
                self.addDir(params)

    def listSeriesEpisodes(self, cItem):
        printDBG("govodtv.listSeriesEpisodes [%s]" % cItem)
        episodes = cItem.get('episodes', [])
        cItem = dict(cItem)
        for item in episodes:
            self.addVideo(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("govodtv.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        url = self.getFullUrl('/szukaj?s=%s') % urllib.quote_plus(searchPattern)
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("govodtv.getLinksForVideo [%s]" % cItem)

        urlTab = []

        if '/player/' in cItem['url']:
            urlTab.append({'name': cItem['url'], 'url': strwithmeta(cItem['url'], {'Referer': cItem['url']}), 'need_resolve': 1})
        else:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return

            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<iframe', '>'), ('</iframe', '>'))
            for item in tmp:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
                urlTab.append({'name': self.up.getHostName(url), 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})

        return urlTab

    def getVideoLinks(self, baseUrl):
        printDBG("govodtv.getVideoLinks [%s]" % baseUrl)
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
        printDBG("govodtv.getArticleContent [%s]" % cItem)
        itemsList = []

        sts, data = self.cm.getPage(cItem['url'])
        if not sts:
            return []

        title = cItem['title']
        icon = cItem.get('icon', '')
        desc = cItem.get('desc', '')

        title = self.cm.ph.getDataBeetwenMarkers(data, '<h1 itemprop="name">', '</h1>', True)[1]
        desc = self.cm.ph.getDataBeetwenMarkers(data, '<p class="f-desc">', '</p>', False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<strong', '>'), ('</p', '>'))
        for item in tmp:
            list = ['Kategorie: ', 'Czas trwania:', 'Kraj produkcji: ', 'Rok produkcji: ']
            l = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<strong>', '</strong>', False)[1])
            if l in list:
                itemsList.append((l, self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '</strong>', '</p>', False)[1])))

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
            self.listMovieFilters(self.currItem, 'list_sort')
        elif 'list_az' == category:
            self.listMovieFilters(self.currItem, 'list_sort')
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
        CHostBase.__init__(self, govodtv(), True, [])

    def withArticleContent(self, cItem):
        return True
