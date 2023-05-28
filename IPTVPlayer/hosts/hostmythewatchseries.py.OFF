# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode
###################################################
# FOREIGN import
###################################################

###################################################


def gettytul():
    return 'https://gowatchseries.io/'


class MyTheWatchseries(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'mythewatchseries', 'cookie': 'mythewatchseries.cookie'})
        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.DEFAULT_ICON_URL = 'https://gowatchseries.io/img/icon/logo.png'
        self.MAIN_URL = None
        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

    def selectDomain(self):
        self.MAIN_URL = 'https://gowatchseries.io/'
        params = dict(self.defaultParams)
        params['with_metadata'] = True
        sts, data = self.getPage(self.getMainUrl(), params)
        if sts:
            self.MAIN_URL = self.cm.getBaseUrl(data.meta['url'])

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def listMain(self, cItem):
        printDBG("MyTheWatchseries.listMain")
        if self.MAIN_URL == None:
            self.selectDomain()
        MAIN_CAT_TAB = [{'category': 'list_filters', 'title': _("LIST"), 'url': self.getFullUrl('/list')},
                        {'category': 'list_items', 'title': _("MOVIES"), 'url': self.getFullUrl('/movies')},
                        {'category': 'list_items', 'title': _("CINEMA MOVIES"), 'url': self.getFullUrl('/cinema-movies')},
                        {'category': 'list_items', 'title': _("THIS WEEK'S SERIES POPULAR"), 'url': self.getFullUrl('/recommended-series')},
                        {'category': 'list_items', 'title': _("NEW RELEASE LIST"), 'url': self.getFullUrl('/new-release')},

                        #{'category':'list_categories', 'title': _('CATEGORIES'),  'url':self.getMainUrl()},

                        {'category': 'search', 'title': _('Search'), 'search_item': True, },
                        {'category': 'search_history', 'title': _('Search history'), }
                       ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def fillCacheFilters(self, cItem):
        printDBG("MyTheWatchseries.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        def addFilter(data, marker, baseKey, addAll=True, titleBase=''):
            key = 'f_' + baseKey
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, marker + '''="([^"]+?)"''')[0]
                if value == '':
                    continue
                title = self.cleanHtmlStr(item)
                if title.lower() in ['all', 'default', 'any']:
                    addAll = False
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if addAll:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                self.cacheFiltersKeys.append(key)

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'first-char'), ('</li', '>'))
        addFilter(tmp, 'rel', 'key')

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'class="text'), ('</', 'select>'))
        for tmp in data:
            key = self.cm.ph.getSearchGroups(tmp, '''name="([^"]+?)"''')[0]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<option', '</option>')
            addFilter(tmp, 'value', key)

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("MyTheWatchseries.listFilters")
        cItem = dict(cItem)

        f_idx = cItem.get('f_idx', 0)
        if f_idx == 0:
            self.fillCacheFilters(cItem)

        if f_idx >= len(self.cacheFiltersKeys):
            return

        filter = self.cacheFiltersKeys[f_idx]
        f_idx += 1
        cItem['f_idx'] = f_idx
        if f_idx == len(self.cacheFiltersKeys):
            cItem['category'] = nextCategory
        self.listsTab(self.cacheFilters.get(filter, []), cItem)

    def listItems2(self, cItem, nextCategory):
        printDBG("MyTheWatchseries.listItems2 [%s]" % cItem)
        page = cItem.get('page', 1)
        query = {}

        url = cItem['url']
        if page > 1:
            query['page'] = page

        keys = list(self.cacheFiltersKeys)
        for key in keys:
            baseKey = key[2:] # "f_"
            if key in cItem:
                query[baseKey] = cItem[key]
        query = urllib_urlencode(query)
        if query != '':
            url += '?' + query

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'pagination'), ('</nav', '>'), False)[1]
        if ('>%s<' % (page + 1)) in nextPage:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div ', '>', 'list_movies'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = url + '?fake=need_resolve.jpeg'
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>')[1])
            if title != '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span', '</span>')[1])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def listItems(self, cItem, nextCategory='', searchPattern=''):
        printDBG("MyTheWatchseries.listItems |%s|" % cItem)

        url = cItem['url']
        page = cItem.get('page', 1)

        query = {}
        if searchPattern != '':
            query['keyword'] = searchPattern
        if page > 1:
            query['page'] = page
        query = urllib_urlencode(query)
        if query != '':
            if url[-1] in ['&', '?']:
                sep = ''
            elif '?' in url:
                sep = '&'
            else:
                sep = '?'
            url += sep + query

        sts, data = self.getPage(url)
        if not sts:
            return []

        if '>Next<' in data:
            nextPage = True
        else:
            nextPage = False

        data = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="listing items"', '</ul>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="name"', '</div>')[1])
            if title != '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+)['"]''')[0])

            # prepare desc
            descTab = []
            tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(item, '<div class="season"', '</div>')
            tmpTab.extend(self.cm.ph.getAllItemsBeetwenMarkers(item, '<div class="date"', '</div>'))
            for tmp in tmpTab:
                tmp = self.cleanHtmlStr(tmp)
                if tmp != '':
                    descTab.append(tmp)
            desc = ' | '.join(descTab) + '[/br]' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="des"', '</div>')[1])

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addDir(params)

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("MyTheWatchseries.exploreItem")

        self.cacheLinks = {}

        url = cItem['url']
        if '/info/' not in url:
            sts, data = self.getPage(url)
            if sts:
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="content">', '</div>')[1]
                data = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''href=['"]([^'^"]*?/info/[^'^"]+?)['"]''')[0])
                if self.cm.isValidUrl(data):
                    url = data

        sts, data = self.getPage(url)
        if not sts:
            return

        tmp = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?id=['"]iframe-trailer['"][^>]+?>''')[0]
        trailerUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''['"](https?://[^'^"]+?)['"]''')[0])
        if not self.cm.isValidUrl(trailerUrl):
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '#iframe-trailer', ';')[1]
            trailerUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''['"](https?://[^'^"]+?)['"]''')[0])

        # prepare desc
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="info_movies"', '<div class="clr">')[1]
        descTab = []
        tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        for d in tmpTab:
            if 'Latest Episode' in d:
                continue
            d = self.cleanHtmlStr(d)
            if d != '':
                descTab.append(d)
        mainDesc = '[/br]'.join(descTab) + '[/br]' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<div class="des"', '</div>')[1])

        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(tmp, '''src=['"]([^'^"]+?)['"]''')[0])
        if icon == '':
            icon = cItem.get('icon', '')
        if mainDesc == '':
            mainDesc = cItem.get('desc', '')

        # add trailer item
        if self.cm.isValidUrl(trailerUrl):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'is_trailer': True, 'title': _('%s - trailer') % cItem['title'], 'url': trailerUrl, 'icon': icon, 'desc': mainDesc})
            self.addVideo(params)

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="child_episode"', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item.split('<span')[0])
            if title != '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+)['"]''')[0])

            # prepare desc
            descTab = []
            tmpTab = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span class="date"', '</span>')
            for tmp in tmpTab:
                tmp = self.cleanHtmlStr(tmp)
                if tmp != '':
                    descTab.append(tmp)
            desc = ' | '.join(descTab) + '[/br]' + mainDesc

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MyTheWatchseries.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/search.html')
        self.listItems(cItem, 'explore_item', searchPattern)

    def getLinksForVideo(self, cItem):
        printDBG("MyTheWatchseries.getLinksForVideo [%s]" % cItem)
        linksTab = []
        if cItem.get('is_trailer'):
            linksTab.append({'name': 'trailer', 'url': cItem['url'], 'need_resolve': 1})
        else:
            linksTab = self.cacheLinks.get(cItem['url'], [])
            if len(linksTab) > 0:
                return linksTab

            sts, data = self.getPage(cItem['url'], self.defaultParams)
            if not sts:
                return []

            data = self.cm.ph.getDataBeetwenMarkers(data, 'muti_link', '</ul>')[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''data-video=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</span>')[1])
                if title == '':
                    title = self.cleanHtmlStr(item)

                linksTab.append({'name': title, 'url': strwithmeta(url, {'links_key': cItem['url']}), 'need_resolve': 1})

        if len(linksTab):
            self.cacheLinks[cItem['url']] = linksTab

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("MyTheWatchseries.getVideoLinks [%s]" % videoUrl)
        linksTab = []

        videoUrl = strwithmeta(videoUrl)

        key = videoUrl.meta.get('links_key', '')
        if key != '':
            if key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if self.cacheLinks[key][idx]['url'] == videoUrl and not self.cacheLinks[key][idx]['name'].startswith('*'):
                        self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(urlParams['header'])
        urlParams['header']['Referer'] = videoUrl.meta.get('Referer', key)

        if self.up.getDomain(self.getMainUrl()) in videoUrl:
            sts, data = self.getPage(videoUrl, urlParams)
            printDBG(data)
            if sts:
                tmp = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>')[1]
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<source', '>')
                for item in tmp:
                    printDBG(item)
                    label = self.cm.ph.getSearchGroups(item, '''label=['"]([^'^"]+?)['"]''')[0]
                    type = self.cm.ph.getSearchGroups(item, '''type=['"]([^'^"]+?)['"]''')[0]
                    url = self.cm.ph.getSearchGroups(item, '''src=['"](https?://[^'^"]+?)['"]''')[0]
                    if self.cm.isValidUrl(url) and 'mp4' in type:
                        linksTab.append({'name': label, 'url': url})
                videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"](https?://[^"]+?)['"]''', 1, True)[0]

        if 0 == len(linksTab):
            videoUrl = strwithmeta(videoUrl, {'Referer': self.getMainUrl()})
            linksTab = self.up.getVideoLinkExt(videoUrl)

        return linksTab

    def getArticleContent(self, cItem):
        printDBG("MyTheWatchseries.getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}

        url = cItem['url']
        if '/info/' not in url:
            sts, data = self.getPage(url)
            if sts:
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="content">', '</div>')[1]
                data = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''href=['"]([^'^"]*?/info/[^'^"]+?)['"]''')[0])
                if self.cm.isValidUrl(data):
                    url = data

        sts, data = self.getPage(url)
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', '"content"'), ('<div', '>', '"clr"'), False)[1]

        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1', '</h1>')[1])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', '"des"'), ('</div', '>'), False)[1].split('</span>', 1)[-1])
        icon = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'picture'), ('</div', '>'), False)[1]
        icon = self.cm.ph.getSearchGroups(icon, '<img[^>]+?src="([^"]+?)"')[0]

        keysMap = {'release': 'released',
                   'country': 'country', }

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', '"three"'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            item = item.split('</span>', 1)
            if len(item) != 2:
                continue
            keyMarker = self.cleanHtmlStr(item[0]).replace(':', '').strip().lower()
            value = self.cleanHtmlStr(item[1]).replace(' , ', ', ')
            key = keysMap.get(keyMarker, '')
            if key != '' and value != '':
                otherInfo[key] = value

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

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
            self.listMain({'name': 'category'})
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items_2')
        elif category == 'list_items_2':
            self.listItems2(self.currItem, 'explore_item')
        elif 'list_items' == category:
            self.listItems(self.currItem, 'explore_item')
        elif 'explore_item' == category:
            self.exploreItem(self.currItem)
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
        CHostBase.__init__(self, MyTheWatchseries(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False
