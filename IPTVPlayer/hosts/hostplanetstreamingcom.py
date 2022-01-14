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
from Components.config import config, ConfigSelection, ConfigText, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.planetstreaming_proxy = ConfigSelection(default="None", choices=[("None", _("None")),
                                                                                               ("proxy_1", _("Alternative proxy server (1)")),
                                                                                               ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.planetstreaming_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.planetstreaming_proxy))
    if config.plugins.iptvplayer.planetstreaming_proxy.value == 'None':
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.planetstreaming_alt_domain))
    return optionList
###################################################


def gettytul():
    return 'http://ww4.planet-streaming.com/'


class PlanetStreaming(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'planet-streaming.com', 'cookie': 'planet-streaming.com.cookie'})

        self.DEFAULT_ICON_URL = 'http://cdn-thumbshot.pearltrees.com/4d/72/4d725324089e9adab59eee4aa32f548f-pearlsquare.jpg'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0', 'DNT': '1', 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.MAIN_URL = None
        self.MAIN_MOVIES_URL = None
        self.MAIN_SERIES_URL = None
        self.cacheFilters = {}
        self.cacheLinks = {}
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE, 'with_metadata': True}

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        proxy = config.plugins.iptvplayer.planetstreaming_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            addParams = dict(addParams)
            addParams.update({'http_proxy': proxy})

        return self.cm.getPage(url, addParams, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        proxy = config.plugins.iptvplayer.planetstreaming_proxy.value
        if proxy != 'None':
            if proxy == 'proxy_1':
                proxy = config.plugins.iptvplayer.alternative_proxy1.value
            else:
                proxy = config.plugins.iptvplayer.alternative_proxy2.value
            url = strwithmeta(url, {'iptv_http_proxy': proxy})
        return url

    def selectDomain(self):
        domains = ['http://ww4.planet-streaming.com/']
        domain = config.plugins.iptvplayer.planetstreaming_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            if domain[-1] != '/':
                domain += '/'
            domains.insert(0, domain)

        for domain in domains:
            sts, data = self.getPage(domain)
            if sts and '-film/' in data:
                self.MAIN_MOVIES_URL = self.cm.getBaseUrl(strwithmeta(data).meta.get('url', domain))
                data = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', '-series/'), ('</a', '>'))[1]
                self.MAIN_SERIES_URL = self.cm.getBaseUrl(self.getFullUrl(self.cm.ph.getSearchGroups(data, '''\shref=['"]([^'^"]+?)['"]''')[0]))
                self.MAIN_URL = self.MAIN_MOVIES_URL
                break

            if self.MAIN_URL != None:
                break

        if self.MAIN_URL == None:
            self.MAIN_MOVIES_URL = 'http://ww4.planet-streaming.com/'
            self.MAIN_SERIES_URL = 'http://ww4.serie-streaminghd.com/'
            self.MAIN_URL = self.MAIN_MOVIES_URL

    def listMainMenu(self, cItem):
        printDBG("PlanetStreaming.listMainMenu")
        MAIN_CAT_TAB = [
                        {'category': 'search', 'title': _('Search'), 'search_item': True, },
                        {'category': 'search_history', 'title': _('Search history'), }
                       ]

        sts, data = self.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'menu'), ('<li', '>', 'right'))[1]
            data = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(data)
            if len(data) > 1:
                try:
                    cTree = self.listToDir(data[1:-1], 0)[0]
                    printDBG(cTree)
                    params = dict(cItem)
                    params['c_tree'] = cTree['list'][0]
                    params['category'] = 'list_categories'
                    self.listCategories(params, 'list_sort_filter')
                except Exception:
                    printExc()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory):
        printDBG("PlanetStreaming.listCategories")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item['dat'], '<a', '</a>')[1])
                url = self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0]
                if url == '#':
                    continue
                url = self.getFullUrl(url)
                if 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                        self.addDir(params)
                elif (len(item['list']) == 1 or 'Genre' in title) and title != '':
                    myItem = item['list'][0]
                    for idx in range(1, len(item['list']), 1):
                        myItem['list'].extend(item['list'][idx].get('list', []))
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'c_tree': myItem, 'title': title, 'url': url})
                    self.addDir(params)
        except Exception:
            printExc()

    def listSortFilters(self, cItem, nextCategory):
        printDBG("PlanetStreaming.listSortFilters")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        pageUrl = data.meta['url']
        self.MAIN_URL = self.cm.getBaseUrl(pageUrl)

        directionsTitle = {'asc': '\xe2\x86\x91', 'desc': '\xe2\x86\x93'}

        items = [[], []]
        data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'news_set_sort'), ('<input', '>'), False)[1]
        data = re.compile('''dle_change_sort\(\s*['"]([^'^"]+?)['"]\s*,\s*['"]([^'^"]+?)['"]\s*\)[^>]*?>([^<]+?)<''').findall(data)
        for item in data:
            for idx in range(len(items)):
                direction = item[1].lower()
                if idx == 1:
                    if direction == 'asc':
                        direction = 'desc'
                    else:
                        direction = 'asc'

                title = '%s %s' % (directionsTitle.get(direction, ''), item[2])
                post_data = {'dlenewssortby': item[0], 'dledirection': direction, 'set_new_sort': 'dle_sort_cat', 'set_direction_sort': 'dle_direction_cat'}
                params = {'url': pageUrl, 'title': title, 'post_data': post_data}
                items[idx].append(params)

        for idx in range(len(items)):
            for item in items[idx]:
                params = dict(cItem)
                params.update(item)
                params.update({'good_for_fav': False, 'category': nextCategory})
                self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("LibreStream.listItems")
        pageUrl = cItem['url']
        page = cItem.get('page', 1)

        params = dict(self.defaultParams)
        params['header']['Referer'] = self.cm.getBaseUrl(pageUrl)
        sts, data = self.getPage(pageUrl, params, cItem.get('post_data', None))
        if not sts:
            return

        printDBG(data)

        pageUrl = data.meta['url']
        self.MAIN_URL = self.cm.getBaseUrl(pageUrl)

        nextPage = self.cm.ph.getDataBeetwenMarkers(data, 'class="navigation', '</div>')[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>\s*%s\s*</a>''' % (page + 1))[0])

        reDescObj = re.compile('''<div[^>]+?fullmask[^>]+?>''')
        reDescObj2 = re.compile('''<hr\s*/\s*>''')

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'fullstreaming'), ('<div', '>', 'clr'))[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', 'fullstreaming'))
        for item in data:
            tmp = self.cm.ph.getDataBeetwenMarkers(item, '<h3', '</h3>')[1]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''\shref=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(tmp)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])

            desc = []
            tmp = reDescObj2.split(reDescObj.split(item)[-1])
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t.replace(' , ', ', ').replace(' : ', ': '))

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)})
            if '-saison-' not in url and ' Saison ' not in title:
                self.addVideo(params)
            else:
                params['category'] = nextCategory
                self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1, 'url': nextPage})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("PlanetStreaming.listEpisodes")

        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        episodeKeys = []
        episodeLinks = {}

        sNum = self.cm.ph.getSearchGroups(data.meta['url'] + ' ', '''\-saison\-([0-9]+?)[^0-9]''', 1, True)[0]

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', '-tab'), ('<script', '>'))[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', '-tab'))
        for langItem in data:
            langTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(langItem, '<div', '</div>')[1])
            langItem = self.cm.ph.getAllItemsBeetwenMarkers(langItem, '<a', '</a>')
            for item in langItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                if url == '':
                    continue
                title = self.cleanHtmlStr(item)
                eNum = self.cm.ph.getSearchGroups(item, '''EPS\s+?([0-9]+?)\s+?''', 1, True)[0]
                if eNum not in episodeKeys:
                    episodeKeys.append(eNum)
                    episodeLinks[eNum] = []
                episodeLinks[eNum].append({'name': '[%s] %s' % (langTitle, self.up.getHostName(url)), 'url': url, 'need_resolve': 1})

        for eNum in episodeKeys:
            title = '%s - s%se%s' % (cItem['title'], sNum.zfill(2), eNum.zfill(2))
            url = cItem['url'] + '#EPS=' + eNum
            self.cacheLinks[url] = episodeLinks.get(eNum, [])
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': title, 'url': url})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("PlanetStreaming.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        post_data = {'do': 'search', 'subaction': 'search', 'search_start': '0', 'full_search': '0', 'result_from': '1', 'story': searchPattern}

        if searchType == 'movies':
            url = self.MAIN_MOVIES_URL
        else:
            url = self.MAIN_SERIES_URL

        sts, data = self.getPage(url)
        if not sts:
            return

        self.MAIN_URL = data.meta['url']
        url = self.getFullUrl('/index.php?do=search')

        cItem = dict(cItem)
        cItem.update({'url': url, 'post_data': post_data})
        self.listItems(cItem, 'list_episodes')

    def getLinksForVideo(self, cItem, forEpisodes=False):
        printDBG("PlanetStreaming.getLinksForVideo [%s]" % cItem)

        if cItem['url'] in self.cacheLinks:
            return self.cacheLinks.get(cItem['url'], [])

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        linksTab = []
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', '-tab'), ('<script', '>'))[1]
        data = self.cm.ph.rgetAllItemsBeetwenNodes(data, ('</div', '>'), ('<div', '>', '-tab'))
        for langItem in data:
            langTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(langItem, '<div', '</div>')[1])
            langItem = self.cm.ph.getAllItemsBeetwenMarkers(langItem, '<a', '</a>')
            for item in langItem:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''')[0])
                if url == '':
                    continue
                title = self.cleanHtmlStr(item)
                linksTab.append({'name': '[%s] %s' % (langTitle, title), 'url': url, 'need_resolve': 1})

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("PlanetStreaming.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        return self.up.getVideoLinkExt(videoUrl)

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
            self.listMainMenu({'name': 'category'})
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_sort_filter')
        elif category.startswith('list_sort_filter'):
            self.listSortFilters(self.currItem, 'list_items')
        if category == 'list_items':
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
        CHostBase.__init__(self, PlanetStreaming(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Movies"), "movies"))
        searchTypesOptions.append((_("Series"), "series"))
        return searchTypesOptions
