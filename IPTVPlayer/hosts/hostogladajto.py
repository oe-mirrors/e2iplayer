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
from Components.config import config, ConfigText, ConfigSelection, getConfigListEntry
###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.ogladajto_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.ogladajto_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("ogladaj.to login:", config.plugins.iptvplayer.ogladajto_login))
    optionList.append(getConfigListEntry("ogladaj.to hasło:", config.plugins.iptvplayer.ogladajto_password))
    return optionList
###################################################


def gettytul():
    return 'https://ogladaj.to/'


class ogladajto(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'ogladaj.to', 'cookie': 'ogladaj.to.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36'
        self.MAIN_URL = 'https://ogladaj.to/'
        self.DEFAULT_ICON_URL = 'https://www.ogladaj.to/templates/oto/images/logo.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl(), 'Upgrade-Insecure-Requests': '1', 'Connection': 'keep-alive'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheMovieFilters = {'cats': [], 'sort': [], 'years': [], 'az': []}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.ajaxParams = {'header': self.AJAX_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.loggedIn = None
        self.login = ''
        self.password = ''
        self.postLogin = ''

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
        printDBG("ogladajto.listMainMenu")

        MAIN_CAT_TAB = [{'category': 'list_sort', 'title': _('Movies'), 'url': self.getFullUrl('/filmy/')},
                        {'category': 'list_sort', 'title': _('Series'), 'url': self.getFullUrl('/seriale/')},
                        {'category': 'list_sort', 'title': _('Children'), 'url': self.getFullUrl('/gatunek/dla-dzieci/')},
                        {'category': 'list_items', 'title': _('Highlights'), 'url': self.getFullUrl('/polecane/')},
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
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<div class="sorting__dropdown-list">', '</ul>', False)[1]
        dat = re.compile('<a[^>]+?href="([^"]+?)"[^>]*?>(.+?)</a>').findall(re.sub('\s+', ' ', dat))
        for item in dat:
            self.cacheMovieFilters['sort'].append({'title': self.cleanHtmlStr(item[1]), 'url': self.getFullUrl(item[0])})

#        sts, data = self.getPage(self.MAIN_URL)
#        if not sts: return

        # fill cats
        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="nav__dropdown-menu sub-menu">', '</ul>', False)[1]
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
        printDBG("ogladajto.listMovieFilters")

        filter = cItem['category'].split('_')[-1]
        if 0 == len(self.cacheMovieFilters[filter]) or filter == 'sort':
            self._fillMovieFilters(cItem)
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = []
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)

    def listsTab(self, tab, cItem, category=None):
        printDBG("ogladajto.listsTab")
        for item in tab:
            params = dict(cItem)
            if None != category:
                params['category'] = category
            params.update(item)
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("ogladajto.listItems %s" % cItem)
        page = cItem.get('page', 1)

        url = cUrl = cItem['url']
        if page > 1:
            url = url + '/strona{0}'.format(page)
        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</div', '>'))[1]
        if '' != self.cm.ph.getSearchGroups(nextPage, 'strona(%s)[^0-9]' % (page + 1))[0]:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'item-col'), ('</a', '>'))

        for item in data:
#            printDBG("ogladajto.listItems item %s" % item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            if url == '':
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''data-src=['"]([^"^']+?)['"]''')[0])
            if icon == '':
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<h2', '>'), ('</h2', '>'), False)[1])
            desc = self.cm.ph.getSearchGroups(item, '''data-tooltip="([^>]+?)"''')[0]
            desc = self.cleanHtmlStr(item) + '[/br]' + desc
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
        printDBG("ogladajto.listSeriesSeasons")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.getBaseUrl(data.meta['url'])
        serieTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'title-col video__title-col serials__title-col'), ('</div', '>'))[1])
        serieDesc = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'video__info-description'), ('</div', '>'))[1]
        serieDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(serieDesc, ('<p', '>'), ('</p', '>'))[1])
        serieIcon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''data-src=['"]([^'^"]+?)['"]''')[0])
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<section', '>', 'content-sec -six'), ('</section', '>'))

        for sItem in data:
            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(sItem, '<h1', '</h1>')[1])
            if not sTitle:
                continue
            sItem = self.cm.ph.getAllItemsBeetwenMarkers(sItem, '<a', '</a>')
            tabItems = []
            for item in sItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                title = self.cm.ph.getSearchGroups(item, '''\salt=['"]([^'^"]+?)['"]''')[0]
                tabItems.append({'title': '%s - %s' % (serieTitle, title), 'url': url, 'icon': serieIcon, 'desc': ''})
            if len(tabItems):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'category': nextCategory, 'title': sTitle, 'episodes': tabItems, 'icon': serieIcon, 'desc': serieDesc})
                self.addDir(params)

    def listSeriesEpisodes(self, cItem):
        printDBG("ogladajto.listSeriesEpisodes [%s]" % cItem)
        episodes = cItem.get('episodes', [])
        cItem = dict(cItem)
        for item in episodes:
            self.addVideo(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ogladajto.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/wyszukaj/%s/') % urllib.quote_plus(searchPattern)
        params = {'name': 'category', 'category': 'list_items', 'good_for_fav': False, 'url': url}
        self.listItems(params)

    def getLinksForVideo(self, cItem):
        printDBG("ogladajto.getLinksForVideo [%s]" % cItem)

        params = dict(self.defaultParams)
        params['no_redirection'] = True
        sts, data = self.getPage(cItem['url'], params)
        if not sts:
            return []

        url = self.cm.meta.get('location', '')
        if "zaloguj" in url and self.loggedIn:
            httpParams = dict(self.ajaxParams)
            httpParams['header'] = dict(httpParams['header'])
            sts, data = self.getPage(url, httpParams, self.postLogin)

        urlTab = []
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<iframe', '>'), ('</iframe', '>'))
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0]
            urlTab.append({'name': self.up.getHostName(url), 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})

        return urlTab

    def getVideoLinks(self, baseUrl):
        printDBG("ogladajto.getVideoLinks [%s]" % baseUrl)
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

    def tryTologin(self):
        printDBG('tryTologin start')

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.ogladajto_login.value or\
            self.password != config.plugins.iptvplayer.ogladajto_password.value:

            self.login = config.plugins.iptvplayer.ogladajto_login.value
            self.password = config.plugins.iptvplayer.ogladajto_password.value

            rm(self.COOKIE_FILE)
            self.cm.clearCookie(self.COOKIE_FILE, ['__cfduid', 'cf_clearance'])

            self.loggedIn = False

            if '' == self.login.strip() or '' == self.password.strip():
                return False

            sts, data = self.getPage(self.MAIN_URL)
            if not sts:
                return False

            post_data = {'submit': '', 'ahd_username': self.login, 'ahd_password': self.password}
            data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'zaloguj'), ('</form', '>'))[1]
            url = self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0]
            inputData = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input type="hidden"', '>')
            for item in inputData:
                name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                post_data[name] = value
            self.postLogin = post_data

            httpParams = dict(self.ajaxParams)
            httpParams['header'] = dict(httpParams['header'])
#            httpParams['raw_post_data'] = True
            sts, data = self.getPage(url, httpParams, post_data)
            if sts and 'notification error' not in data:
                printDBG('tryTologin ok')
                self.loggedIn = True
            else:
                if sts:
                    message = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'notification error'), ('</div', '>'))[1])
                else:
                    message = ''
                self.sessionEx.open(MessageBox, _('Login failed.') + '\n' + message, type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')

        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        self.tryTologin()

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
            self.listMovieFilters(self.currItem, 'list_sort')
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
        CHostBase.__init__(self, ogladajto(), True, [])
