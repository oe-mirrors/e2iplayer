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
import urlparse
import re
import base64
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://kinogo.cc/'


class KinogoCC(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'kinogo.cc', 'cookie': 'kinogo.cc.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36'
        self.MAIN_URL = 'http://kinogo.cc/'
        self.DEFAULT_ICON_URL = 'https://image.winudf.com/v2/image/Y29tLndQbGVlcmRseWFraW5vZ29fc2NyZWVuc2hvdHNfMF9iMzUzZjkyNw/screen-0.jpg?h=355&fakeurl=1&type=.jpg'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'search_charset': True, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.cacheSeriesLetter = []
        self.cacheSetiesByLetter = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

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

    def listMainMenu(self, cItem):
        printDBG("KinogoCC.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<table', '>', 'menu'), ('</table', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            if not url.endswith('/'):
                continue
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'url': url})
            self.addDir(params)

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', '"mini"'), ('</div', '>'), False)
        for item in data:

            sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<i', '</i>')[1])
            printDBG("> sTitle[%s]" % sTitle)
            subItems = []
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<a', '</a>')
            for it in item:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(it, '''href=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(it)
                printDBG("\t> title[%s]" % title)
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'list_items', 'title': title, 'url': url})
                subItems.append(params)

            if len(subItems):
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'sub_items', 'title': sTitle, 'sub_items': subItems})
                self.addDir(params)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listSubItems(self, cItem):
        printDBG("KinogoCC.listSubItems")
        subList = cItem['sub_items']
        for item in subList:
            params = {'name': 'category', 'type': 'category'}
            params.update(item)
            if item.get('type', 'category') == 'category':
                self.addDir(params)
            else:
                self.currList.append(params)

    def listItems(self, cItem, nextCategory):
        printDBG("KinogoCC.listItems")
        page = cItem.get('page', 1)
        post_data = cItem.get('post_data', None)

        sts, data = self.getPage(cItem['url'], post_data=post_data)
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'bot-navigation'), ('</div', '>'))[1]
        nextPage = self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>\s*?{0}\s*?<'''.format(page + 1))[0]

        commentReObj = re.compile('<!--[\s\S]*?-->')
        brReObj = re.compile('<[\s/]*?br\s[\s/]*>', re.I)
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'shortstorytitle'), ('<div', '>', 'pomoshnik'), False)[1]
        data = re.compile('<div[^>]+?shortstorytitle[^>]+?>').split(data)
        for item in data:
            rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', 'current-rating'), ('</', '>'), False)[1])
            date = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<', '>', 'dateicon'), ('</', '>'), False)[1])

            url = self.cm.ph.getDataBeetwenNodes(item, ('<h', '>', 'zagolovki'), ('</h', '>'), False)[1]
            title = self.cleanHtmlStr(url)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(url, '''href=['"]([^"^']+?)['"]''')[0])

            item = self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'shortimg'), ('<div', '>', 'icons'), False)[1]
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])

            descTab = []
            item = commentReObj.sub("", item)
            item = brReObj.split(item)
            for idx in range(len(item)):
                t = self.cleanHtmlStr(item[idx])
                if t == '':
                    continue
                if len(descTab) == 0:
                    descTab.append(t)
                else:
                    descTab.insert(1, t)
            descTab.append('Дата: %s, %s/5' % (date, rating))
            params = {'good_for_fav': True, 'category': nextCategory, 'url': url, 'title': title, 'desc': '[/br]'.join(descTab[::-1]), 'icon': icon}
            self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            if nextPage != '#':
                params.update({'title': _('Next page'), 'url': self.getFullUrl(nextPage), 'page': page + 1})
                self.addDir(params)
            elif post_data != None:
                params['post_data'].update({'search_start': page + 1, 'result_from': (page) * 30 + 1})
                params.update({'title': _('Next page'), 'page': page + 1})
                self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        #searchPattern = 'Охота на воров'
        printDBG("KinogoCC.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/index.php?do=search')
        sts, data = self.getPage(url)
        if not sts:
            return
        if 'orig_charset' in data.meta:
            try:
                searchPattern = searchPattern.decode('UTF-8').encode(data.meta['orig_charset'])
            except Exception:
                printExc()

        searchPattern = self.cm.urlEncodeNonAscii(searchPattern)
        post_data = {'do': 'search', 'subaction': 'search', 'search_start': 1, 'full_search': 0, 'result_from': 1, 'story': searchPattern}
        cItem = {'name': 'category', 'type': 'category', 'category': 'list_items', 'post_data': post_data, 'url': url}
        self.listItems(cItem, 'explore_item')

    def exploreItem(self, cItem, nextCategory):
        printDBG("KinogoCC.listItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'section'), ('<', '>', 'social'))[1]
        printDBG(data)

        titles = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'tabs'), ('</ul', '>'))[1]
        titles = self.cm.ph.getAllItemsBeetwenMarkers(titles, '<li', '</li>')
        if len(titles) == 0:
            titles.append(_('watch'))
        if len(titles) < 2:
            titles.append(_('trailer'))

        # trailer
        iTrailer = self.cm.ph.getSearchGroups(data, '''['"](https?://[^'^"]*?youtube[^'^"]*?watch[^'^"]*?)['"]''')[0]
        if iTrailer != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': iTrailer, 'title': '%s - %s' % (cItem['title'], self.cleanHtmlStr(titles[-1]))})
            self.addVideo(params)

        # watch online
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'Base64.decode(', ')', False)[1].strip()
        if tmp != '':
            try:
                data = base64.b64decode(tmp[1:-1])
                data = self.cm.ph.getSearchGroups(data, '''(<param[^>]+?flashvars[^>]+?>)''', ignoreCase=True)[0]
                data = self.cm.ph.getSearchGroups(data, '''value=['"]([^'^"]+?)['"]''')[0]
                data = data.split('&amp;')
                fileMarker = 'file='
                playlistMarker = 'pl='
                for item in data:
                    item = item.strip()

                    if item.startswith(fileMarker):
                        url = item[len(fileMarker):]
                        printDBG(">> url[%s]" % url)
                        tmp = url.lower().split('?', 1)[0]
                        if self.cm.isValidUrl(url) and \
                           tmp.split('.')[-1] in ['flv', 'mp4']:
                            params = dict(cItem)
                            params.update({'good_for_fav': False, 'url': url})
                            self.addVideo(params)

                    if item.startswith(playlistMarker):
                        url = item[len(playlistMarker):]
                        printDBG(">> url[%s]" % url)
                        tmp = url.lower().split('?', 1)[0]
                        if self.cm.isValidUrl(url) and \
                           tmp.endswith('.txt'):
                            urlParams = dict(self.defaultParams)
                            urlParams['convert_charset'] = False
                            sts, tmp = self.getPage(url, urlParams)
                            if not sts:
                                continue
                            printDBG(">>\n%s\n<<" % tmp)
                            tmp = tmp.split('},')
                            for item in tmp:
                                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''['"]comment['"]\s*?:\s*?['"]([^'^"]+?)['"]''')[0])
                                url = self.cm.ph.getSearchGroups(item, '''['"]file['"]\s*?:\s*?['"](https?://[^'^"]+?)['"]''')[0]
                                if url == '':
                                    continue
                                params = dict(cItem)
                                params.update({'good_for_fav': False, 'title': '%s %s' % (cItem['title'], title), 'url': url})
                                self.addVideo(params)
            except Exception:
                printExc()
        else:
            urlsTab = []

            iframes = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '</iframe>')
            for iframe in iframes:
                url = self.cm.ph.getSearchGroups(iframe, '''src=["']([^"^']+?)["']''')[0]
                if self.cm.isValidUrl(url):
                    params = self.up.getVideoLinkExt(url)
                    printDBG(str(params))
                    urlsTab.extend(params)

            data = re.compile('''['"]?file['"]?\s*?:\s*?['"](https?://[^'^"]+?(?:\.flv|\.mp4)(?:\?[^'^"]*?)?)['"]''', re.I).findall(data)
            for item in data:
                name = item.split('?', 1)[0].split('.')[-1]
                params = {'name': name, 'url': strwithmeta(item, {'Referer': self.getMainUrl()}), 'need_resolve': 0}
                if name == 'flv':
                    urlsTab.insert(0, params)
                else:
                    urlsTab.append(params)

            if len(urlsTab):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'urls_tab': urlsTab})
                self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("KinogoCC.getLinksForVideo [%s]" % cItem)

        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)
        if 'urls_tab' in cItem:
            return cItem['urls_tab']
        return [{'name': 'direct', 'url': strwithmeta(cItem['url'], {'Referer': self.getMainUrl()}), 'need_resolve': 0}]

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
        elif category == 'movies':
            self.listMovies(self.currItem, 'sub_items', 'list_items')
        elif category == 'series':
            self.listSeries(self.currItem, 'list_items')
        elif category == 'sub_items':
            self.listSubItems(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'sub_items')
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
        CHostBase.__init__(self, KinogoCC(), True, [])
