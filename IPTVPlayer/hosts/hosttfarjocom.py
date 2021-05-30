# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
###################################################

###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://tfarjo.ws/'


class TfarjoCom(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'tfarjo.com', 'cookie': 'tfarjo.com.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://www1.tfarjo.ws/'
        self.DEFAULT_ICON_URL = 'https://www1.tfarjo.ws/assets/theme/img/tfarjo-logo.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.cacheSeriesLetter = []
        self.cacheSetiesByLetter = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        addParams['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def getFullIconUrl(self, url):
        url = CBaseHostClass.getFullIconUrl(self, url.strip())
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['PHPSESSID', 'cf_clearance'])
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def getDefaulIcon(self, cItem=None):
        return self.getFullIconUrl(self.DEFAULT_ICON_URL)

    def listMainMenu(self, cItem):
        printDBG("InteriaTv.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return

        self.setMainUrl(data.meta['url'])
        MAIN_CAT_TAB = [{'category': 'movies', 'title': 'Films', 'url': self.getFullUrl('/films')},
                        {'category': 'series', 'title': 'Series', 'url': self.getFullUrl('/series')},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listMovies(self, cItem, nextCategory1, nextCategory2):
        printDBG("TfarjoCom.listMovies")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        params = dict(cItem)
        params.update({'category': nextCategory2, 'title': _('--All--')})
        self.addDir(params)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'buttons_filtre'), ('<div', '>', 'row'))[1]
        filters = self.cm.ph.getAllItemsBeetwenMarkers(data, '<button', '</button>')
        for filter in filters:
            fTitle = self.cleanHtmlStr(filter)
            fMarker = self.cm.ph.getSearchGroups(filter, '''onclick=['"]([^"^']+?)['"]''')[0].replace('()', '')
            subItems = []
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', fMarker), ('</p', '>'))[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
            for item in tmp:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                if title == '':
                    continue
                params = {'category': nextCategory2, 'title': title, 'url': url}
                subItems.append(params)

            if len(subItems):
                self.addDir({'category': nextCategory1, 'title': fTitle, 'sub_items': subItems})

    def listSeries(self, cItem, nextCategory):
        printDBG("TfarjoCom.listSeries [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(data.meta['url'])

        params = dict(cItem)
        params.update({'category': nextCategory, 'title': _('--All--')})
        self.addDir(params)

        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<h4', '</h4>', 'Voir Séries'), ('<li', '>', 'genre'))[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            if title == '':
                continue
            params = dict(cItem)
            params.update({'category': nextCategory, 'title': title, 'url': url})
            self.addDir(params)

    def listSubItems(self, cItem):
        printDBG("TfarjoCom.listSubItems")
        subList = cItem['sub_items']
        for item in subList:
            params = {'name': 'category', 'type': 'category'}
            params.update(item)
            if item.get('type', 'category') == 'category':
                self.addDir(params)
            else:
                self.currList.append(params)

    def listItems(self, cItem, nextCategory, data=None):
        printDBG("InteriaTv.listItems")
        page = cItem.get('page', 1)
        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            self.setMainUrl(data.meta['url'])

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'pagination'), ('</ul', '>'))[1]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''<a[^>]+?href=['"]([^"^']+?)['"][^>]*?>\s*?{0}\s*?<'''.format(page + 1))[0])

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'icon'), ('</ul', '>'))[1]
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>'), ('</li', '>'))
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^"^']+?)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<p', '</p>')[1])
            desc = []
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
            for t in item:
                if 'VO' in t:
                    desc.append('VO')
                if 'VF' in t:
                    desc.append('VF')
                t = self.cleanHtmlStr(t)
                if t != '':
                    desc.append(t)
            params = {'good_for_fav': True, 'priv_has_art': True, 'category': nextCategory, 'url': url, 'title': title, 'desc': ' | '.join(desc), 'icon': icon}
            self.addDir(params)

        if nextPage != '':
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': nextPage, 'page': page + 1})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TfarjoCom.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'form-user'), ('</form', '>'))
        if not sts:
            return False
        actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
        post_data = {}
        for item in data:
            name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
            value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
            post_data[name] = value
        post_data.update({'search': searchPattern, 'view': 'list'})

        paramsUrl = dict(self.defaultParams)
        paramsUrl['header'] = dict(self.AJAX_HEADER)
        paramsUrl['header']['Referer'] = cUrl

        sts, data = self.getPage(actionUrl, paramsUrl, post_data)
        if not sts:
            return
        printDBG(data)

        try:
            data = byteify(json.loads(data), '', True)
            for item in data['data']['user']:
                if not isinstance(item, dict):
                    continue
                url = self.getFullUrl(item['url'])
                icon = self.getFullIconUrl(item.get('avatar', ''))
                title = '%s %s' % (item['name'], item['year'])
                params = {'good_for_fav': True, 'priv_has_art': True, 'category': 'explore_item', 'url': url, 'title': title, 'desc': '', 'icon': icon}
                self.addDir(params)
        except Exception:
            printExc()

    def exploreItem(self, cItem, nextCategory):
        printDBG("InteriaTv.listItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = data.meta['url']
        if '/serie/' in cUrl and '/saison' in cUrl:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'vlink'), ('</div', '>'))[1]
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            if len(data) < 3:
                return
            cUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data[2], '''href=['"]([^"^']+?)['"]''')[0])
            sts, data = self.getPage(cUrl)
            if not sts:
                return
            cUrl = data.meta['url']
        self.setMainUrl(cUrl)
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'bdetail'), ('<div', '>', 'row'))[1]
        iTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(tmp, '<h1', '</h1>')[1])
        tmp = self.cm.ph.getDataBeetwenNodes(tmp, ('<div', '>', 'dmovie'), ('</div', '>'))[1]
        iIcon = self.getFullIconUrl(self.cm.ph.getSearchGroups(tmp, '''<img[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        iTrailer = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''<iframe[^>]+?src=['"]([^"^']+?youtube[^"^']+?)['"]''', 1, True)[0])

        if '/film/' in cUrl:
            if '"players' in data or "'players" in data:
                params = dict(cItem)
                params.update({'priv_has_art': True})
                self.addVideo(params)
        else:
            data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'panel-heading'), ('<div', '>', 'row'))
            for season in data:
                sTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(season, ('<h', '>', 'panel-title'), ('</h', '>'))[1])
                sUrl = self.getFullUrl(self.cm.ph.getSearchGroups(season, '''href=['"]([^"^']+?)['"]''')[0])
                season = self.cm.ph.getAllItemsBeetwenNodes(season, ('<div', '>', 'panel-body'), ('</div', '>'))
                episodesTab = []
                for item in season:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^"^']+?)['"]''')[0])
                    title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>')[1])
                    desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'ddcheck'), ('</span', '>'))[1])
                    params = {'good_for_fav': True, 'priv_has_art': True, 'url': url, 'title': '%s - %s' % (iTitle, title), 'desc': desc, 'icon': iIcon}
                    if 'glyphicon-time' in item:
                        params['type'] = 'article'
                    else:
                        params['type'] = 'video'
                    episodesTab.append(params)
                if len(episodesTab):
                    params = {'good_for_fav': False, 'priv_has_art': True, 'category': nextCategory, 'title': sTitle, 'url': sUrl, 'sub_items': episodesTab, 'desc': '', 'icon': iIcon}
                    self.addDir(params)

        if iTrailer != '':
            params = {'good_for_fav': False, 'url': iTrailer, 'title': '%s - %s' % (iTitle, _('trailer')), 'icon': iIcon}
            self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("TfarjoCom.getLinksForVideo [%s]" % cItem)

        if 1 == self.up.checkHostSupport(cItem.get('url', '')):
            videoUrl = cItem['url'].replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'function getIframe', '</script>')[1]
        linkUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''['"]?url['"]?\s*?:\s*?['"]([^'^"]+?)['"]''')[0])
        if '/film/' in cUrl:
            itemType = 'movie'
        else:
            itemType = 'episode'
        linkTest = self.cm.ph.getSearchGroups(data, '''['"]?csrf_test_name['"]?\s*?:\s*?['"]([^'^"]+?)['"]''')[0]

        retTab = []
        data = re.sub("<!--[\s\S]*?-->", "", data)
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<button', '>', 'getIframe'), ('</button', '>'))
        for item in data:
            name = self.cleanHtmlStr(item)
            verType = self.cm.ph.getSearchGroups(item, '''class=['"]players([^'^"]+?)['"]''')[0].upper()
            linkData = self.cm.ph.getDataBeetwenMarkers(item, 'getIframe(', ')', False)[1].strip()[1:-1]
            url = linkUrl + '#' + linkData
            retTab.append({'name': '[%s] %s' % (verType, name), 'url': strwithmeta(url, {'Referer': cUrl, 'iptv_link_data': linkData, 'iptv_link_test': linkTest, 'iptv_link_type': itemType}), 'need_resolve': 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("TfarjoCom.getVideoLinks [%s]" % baseUrl)
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

        paramsUrl = dict(self.defaultParams)
        paramsUrl['header'] = dict(self.AJAX_HEADER)
        paramsUrl['header']['Referer'] = baseUrl.meta['Referer']
        post_data = {'csrf_test_name': baseUrl.meta['iptv_link_test'], baseUrl.meta['iptv_link_type']: baseUrl.meta['iptv_link_data']}
        sts, data = self.getPage(baseUrl.split('#', 1)[0], paramsUrl, post_data)
        if not sts:
            return
        printDBG(data)
        try:
            data = byteify(json.loads(data), '', True)
            data = data['iframe']
            videoUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
            urlTab = self.up.getVideoLinkExt(videoUrl)
        except Exception:
            printExc()

        return urlTab

    def getArticleContent(self, cItem):
        printDBG("TfarjoCom.getArticleContent [%s]" % cItem)

        retTab = []

        otherInfo = {}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'bdetail'), ('<div', '>', 'row'))[1]
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1', '</h1>')[1])
        icon = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'dmovie'), ('</div', '>'))[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''<img[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<p', '>', 'vtext'), ('</p', '>'))[1])

        keysMap = {'genre:': 'genre',
                   'imdb:': 'imdb_rating',
                   'durée:': 'duration',
                   'créée par:': 'writer',
                   'acteurs:': 'actors',
                   'année de production:': 'year',
                   'date de production:': 'production',
                   'qualité:': 'quality',
                   'langue:': 'language'}

        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<h5', '>'), ('</h5', '>'))
        reObj = re.compile('<span[^>]*?>')
        printDBG(tmp)
        for item in tmp:
            item = reObj.split(item, 1)
            val = self.cleanHtmlStr(item[-1]).replace(' ,', ',')
            if val == '' or val.lower() == 'n/a':
                continue
            key = self.cleanHtmlStr(item[0]).decode('utf-8').lower().encode('utf-8')
            if key not in keysMap:
                continue
            otherInfo[keysMap[key]] = val

        if title == '':
            title = cItem['title']
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

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
            self.cm.clearCookie(self.COOKIE_FILE, ['PHPSESSID', '__cfduid', 'cf_clearance'])
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
        CHostBase.__init__(self, TfarjoCom(), True, [])

    def withArticleContent(self, cItem):
        if cItem.get('priv_has_art', False):
            return True
        else:
            return False
