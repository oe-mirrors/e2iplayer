# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
###################################################

###################################################
# FOREIGN import
###################################################
import re
from urlparse import urlparse
###################################################


def gettytul():
    return 'https://watchcartoononline.com/'


class WatchCartoonOnline(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'watchcartoononline.com', 'cookie': 'watchcartoononline.com.cookie'})

        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        self.MAIN_URL = 'https://www.watchcartoononline.com/'
        self.DEFAULT_ICON_URL = 'https://mk0echouaawhk9ls0i7l.kinstacdn.com/wp-content/uploads/websites/website%20to%20watch%20cartoons/www.watchcartoononline.com.1280.jpg'

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheLinks = {}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("WatchCartoonOnline.listMainMenu")

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = data[data.find('<body'):]

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'nav-bar'), ('</ul', '>'), False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        tabItems = []
        for item in tmp:
            if 'active' in item:
                continue
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'category': 'list_abc', 'title': title, 'url': url})
            self.addDir(params)

        def _fillItems(data):
            data = data.split('</div>', 1)
            tabTitle = self.cleanHtmlStr(data[0].split(' - ', 1)[0])
            if 'genre' in tabTitle.lower():
                node = 'a'
                genre = True
            else:
                node = 'li'
                genre = False
            data = self.cm.ph.getAllItemsBeetwenMarkers(data[-1], '<' + node, '</%s>' % node)

            tabItems = []
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])

                params = dict(cItem)
                params.update({'title': title, 'url': url, 'icon': icon})
                if url.endswith('-list') or genre:
                    params.update({'category': 'list_abc'})
                else:
                    params.update({'good_for_fav': True, 'category': 'explore_item'})
                tabItems.append(params)

            if len(tabItems):
                params = dict(cItem)
                params.update({'category': 'sub_items', 'title': tabTitle, 'sub_items': tabItems})
                self.addDir(params)

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'recent-release-main'), ('<div', '>', 'sidebar-'), False)[1]
        tmp = re.compile('<div[^>]+?recent\-release\-main[^>]+?>').split(tmp)
        tmp.append(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'sidebar-all'), ('</ul', '>'), False)[1])
        for item in tmp:
            _fillItems(item)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listABC(self, cItem, nextCategory):
        printDBG("WatchCartoonOnline.listABC")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'ddmcc_container'), ('</div', '>'), False)[1]
        data = data.split('<p')
        for idx in range(len(data)):
            tabTitle = self.cleanHtmlStr(self.cm.ph.rgetDataBeetwenMarkers2(data[idx], '</p>', '>', False)[1])
            tabData = self.cm.ph.getAllItemsBeetwenMarkers(data[idx], '<li', '</li>')
            tabItems = []
            for item in tabData:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])

                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': 'explore_item', 'title': title, 'url': url, 'icon': icon})
                tabItems.append(params)

            if len(tabItems):
                params = dict(cItem)
                params.update({'category': 'sub_items', 'title': tabTitle + ' ({0}) '.format(len(tabItems)), 'sub_items': tabItems})
                self.addDir(params)

    def exploreItem(self, cItem):
        printDBG("WatchCartoonOnline.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        cItem = dict(cItem)
        cItem['prev_url'] = cItem['url']

        # desc
        descData = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'video-title'), ('<div', '>', 'sidebar-titles'), False)[1]
        icon = self.getFullUrl(self.cm.ph.getSearchGroups(descData, '''<img[^>]+?src=['"]([^'^"]+?)['"]''')[0])

        desc = []
        tmp = self.cm.ph.getDataBeetwenMarkers(descData, '<b', '</div>')[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for t in tmp:
            t = self.cleanHtmlStr(t)
            if t != '':
                desc.append(t)
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(descData, '<b', '</b>')[1]) + ' ' + ', '.join(desc)
        desc += '[/br]' + self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(descData, '<p', '</p>')[1])

        cItem.update({'desc': desc, 'icon': icon})

        # main item
        if '-video-0' in data or 'video too slow' in data:
            self.addVideo(cItem)

        # category
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'header-tag'), ('</div', '>'), False)[1]
        tmp = self.cm.ph.getDataBeetwenNodes(tmp, ('<a', '>'), ('</a', '>'))[1]
        catTitle = self.cleanHtmlStr(tmp)
        catUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''href=['"]([^"^']+?)['"]''', 1, True)[0])
        printDBG(">>>>>>>>>>>>>>>> " + catTitle)
        printDBG(">>>>>>>>>>>>>>>> " + catUrl)
        printDBG(">>>>>>>>>>>>>>>> " + self.cm.meta['url'])
        if '' not in [catTitle, catUrl] and catUrl != self.cm.meta['url']:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': catUrl, 'title': catTitle})
            self.addDir(params)

        # episodes
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'cat-eps'), ('<div', '>', 'sidebar'))[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'cat-eps'), ('</div', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)

            params = dict(cItem)
            params.update({'title': title, 'url': url})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("WatchCartoonOnline.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl('/search')
        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        url = self.getFullUrl('/search')
        sts, data = self.getPage(url, {}, {'catara': searchPattern, 'konuara': searchType})
        if not sts:
            return

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'items'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?src=['"]([^"^']+?)['"]''')[0])

            try:
                url = self.getFullUrl(urlparse(url).path)
            except Exception:
                printExc()

            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'explore_item', 'title': title, 'url': url, 'icon': icon})
            self.addDir(params)

    def _getPlayerData(self, data):
        printDBG(data)
        jscode = self.cm.ph.getDataBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)[1]
        jscode = 'var document={write:function(e){print(e)}};window=this,window.atob=function(e){e.length%4==3&&(e+="="),e.length%4==2&&(e+="=="),e=Duktape.dec("base64",e),decText="";for(var t=0;t<e.byteLength;t++)decText+=String.fromCharCode(e[t]);return decText};' + jscode
        ret = js_execute(jscode)
        if ret['sts'] and 0 == ret['code']:
            printDBG(ret['data'])
            return self.cm.ph.getSearchGroups(ret['data'], '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0].replace('&amp;', '&')
        return ''

    def getLinksForVideo(self, cItem):
        printDBG("WatchCartoonOnline.getLinksForVideo [%s]" % cItem)
        urlTab = []

        cacheKey = cItem['url']
        urlTab = self.cacheLinks.get(cacheKey, [])
        if len(urlTab):
            return urlTab

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        cUrl = self.cm.meta['url']

        # main player
        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', '-video-'), ('</script', '>'))[1]
        playerUrl = self._getPlayerData(data)
        if playerUrl != '':
            urlTab.append({'name': self.up.getDomain(self.cm.meta['url']).replace('www.', ''), 'url': self.cm.getFullUrl(playerUrl, self.cm.getBaseUrl(cUrl)), 'need_resolve': 1})

        # alternative player
        altUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<a[^>]+?href=['"]([^"^']+?)['"]''', 1, True)[0])

        sts, data = self.getPage(altUrl)
        if not sts:
            return urlTab
        cUrl = self.cm.meta['url']

        data = self.cm.ph.getDataBeetwenNodes(data, ('<meta', '>', 'embedURL'), ('</script', '>'))[1]
        playerUrl = self._getPlayerData(data)
        if playerUrl != '':
            urlTab.append({'cache_key': cacheKey, 'name': self.up.getDomain(self.cm.meta['url']).replace('www.', ''), 'url': self.cm.getFullUrl(playerUrl, self.cm.getBaseUrl(cUrl)), 'need_resolve': 1})

        if len(urlTab):
            self.cacheLinks = {cacheKey: urlTab}

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("WatchCartoonOnline.getVideoLinks [%s]" % videoUrl)

        key = strwithmeta(videoUrl).meta.get('cache_key', '')
        for key in self.cacheLinks:
            for idx in range(len(self.cacheLinks[key])):
                if videoUrl in self.cacheLinks[key][idx]['url']:
                    if not self.cacheLinks[key][idx]['name'].startswith('*'):
                        self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                    break

        referer = strwithmeta(videoUrl).meta.get('Referer', self.cm.getBaseUrl(videoUrl))
        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        params['header']['Referer'] = referer

        sts, data = self.getPage(videoUrl, params)
        if not sts:
            return
        cUrl = self.cm.meta['url']

        domain = self.up.getDomain(cUrl).replace('www.', '')

        uniqueUrls = []
        urlTab = []
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, '{', '}')
        printDBG(items)
        for item in items:
            item = item.replace('\/', '/')
            if 'video/mp4' not in item.lower():
                continue
            type = self.cm.ph.getSearchGroups(item, '''type['"]?\s*[=:]\s*['"]([^"^']+?)['"]''')[0]
            label = self.cm.ph.getSearchGroups(item, '''label['"]?\s*[=:]\s*['"]([^"^']+?)['"]''')[0]
            if label == '':
                label = self.cm.ph.getSearchGroups(item, '''format['"]?\s*[=:]\s*['"]([^"^']+?)['"]''')[0]
            url = self.cm.ph.getSearchGroups(item, '''src['"]?\s*[=:]\s*['"]([^"^']+?)['"]''')[0]
            if url not in uniqueUrls:
                uniqueUrls.append(url)
                url = self.cm.getFullUrl(url, self.cm.getBaseUrl(cUrl))
                urlTab.append({'name': '[{0}] {1} {2}'.format(type.split('/', 1)[0], label, domain), 'url': strwithmeta(url, {'Referer': referer})})

        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category', 'type': 'category'})
        elif category == 'list_abc':
            self.listABC(self.currItem, 'sub_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem)
        elif category == 'sub_items':
            self.currList = self.currItem.get('sub_items', [])
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
        CHostBase.__init__(self, WatchCartoonOnline(), True, favouriteTypes=[])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Anime Search"), "series"))
        searchTypesOptions.append((_("Episode Search"), "episodes"))
        return searchTypesOptions
