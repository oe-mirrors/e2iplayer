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
import urlparse
import re
import urllib
try:
    import json
except Exception:
    import simplejson as json
###################################################


def gettytul():
    return 'http://hdpopcorns.co/'


class HDPopcornsCom(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'HDPopcornsCom.tv', 'cookie': 'HDPopcornsCom.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'http://hdpopcorns.co/'
        self.DEFAULT_ICON_URL = 'http://7428.net/wp-content/uploads/2014/07/Movie-Time-Ticket-Vector.jpg'

        self.MAIN_CAT_TAB = [{'category': 'list_items', 'title': _('Categories'), 'url': self.getMainUrl()},
                             {'category': 'search', 'title': _('Search'), 'search_item': True, },
                             {'category': 'search_history', 'title': _('Search history'), }
                            ]

        self.cacheFilters = {}

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

    def getFullUrl(self, url):
        if '://' not in url and ':/' in url:
            url = url.split(':/', 1)[-1]
        return CBaseHostClass.getFullUrl(self, url)

    def getFullIconUrl(self, url):
        url = self.getFullUrl(url)
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE)
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.USER_AGENT})

    def fillFilters(self, cItem):
        self.cacheFilters = {}
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        def addFilter(data, key, addAny, titleBase, marker):
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, '''%s=['"]([^'^"]+?)['"]''' % marker)[0]
                if value == '':
                    continue
                title = self.cleanHtmlStr(item)
                if titleBase == '':
                    title = title.title()
                self.cacheFilters[key].append({'title': titleBase + title, key: value})
            if addAny and len(self.cacheFilters[key]):
                self.cacheFilters[key].insert(0, {'title': 'Wszystkie'})

        # category
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, 'ofcategory', '</select>')[1]
        tmpData = self.cm.ph.getAllItemsBeetwenMarkers(tmpData, '<option', '</option>', withMarkers=True)
        addFilter(tmpData, 'ofcategory', False, '', 'value')
        if 0 == len(self.cacheFilters['ofcategory']):
            for item in [("46", "Action"), ("24", "Adventure"), ("25", "Animation"), ("26", "Biography"), ("27", "Comedy"), ("28", "Crime"), ("29", "Documentary"), ("30", "Drama"), ("31", "Family"), ("32", "Fantasy"), ("33", "Film-Noir"), ("35", "History"), ("36", "Horror"), ("37", "Music"), ("38", "Musical"), ("39", "Mystery"), ("40", "Romance"), ("41", "Sci-Fi"), ("42", "Sports"), ("43", "Thriller")]:
                self.cacheFilters['ofcategory'].append({'title': item[1], 'ofcategory': item[0]})

        # rating
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, 'ofrating', '</select>')[1]
        tmpData = self.cm.ph.getAllItemsBeetwenMarkers(tmpData, '<option', '</option>', withMarkers=True)
        addFilter(tmpData, 'ofrating', False, '', 'value')
        if 0 == len(self.cacheFilters['ofrating']):
            for i in range(10):
                i = str(i)
                if i == '0':
                    title = 'All Ratings'
                else:
                    title = i
                self.cacheFilters['ofrating'].append({'title': title, 'ofrating': i})

        # quality
        tmpData = self.cm.ph.getDataBeetwenMarkers(data, 'ofquality', '</select>')[1]
        tmpData = self.cm.ph.getAllItemsBeetwenMarkers(tmpData, '<option', '</option>', withMarkers=True)
        addFilter(tmpData, 'ofquality', False, '', 'value')
        if 0 == len(self.cacheFilters['ofquality']):
            for item in [("0", "All Qualities"), ("47", "1080p"), ("48", "720p")]:
                self.cacheFilters['ofquality'].append({'title': item[1], 'ofquality': item[0]})

        printDBG(self.cacheFilters)

    def listFilter(self, cItem, filters):
        params = dict(cItem)
        idx = params.get('f_idx', 0)
        params['f_idx'] = idx + 1

        if idx == 0:
            self.fillFilters(cItem)

        tab = self.cacheFilters.get(filters[idx], [])
        self.listsTab(tab, params)

    def listItems(self, cItem, nextCategory):
        printDBG("HDPopcornsCom.listItems")
        baseUrl = cItem['url']
        post_data = None
        page = cItem.get('page', 1)
        if page == 1 and '/?s=' not in baseUrl:
            hasFilters = False
            for key in ['ofcategory', 'ofrating', 'ofquality']:
                if cItem.get(key, '') not in ['-', '', '0']:
                    hasFilters = True

            if hasFilters:
                post_data = 'ofsearch=&'
                for key in ['ofcategory', 'ofrating', 'ofquality']:
                    if cItem.get(key, '') not in ['-', '']:
                        post_data += key + '={0}&ofcategory_operator=and&'.format(cItem[key])
                post_data += 'ofsubmitted=1'

        params = dict(self.defaultParams)
        params['header'] = dict(params['header'])
        params['raw_post_data'] = True

        sts, data = self.getPage(baseUrl, params, post_data)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        nextPage = self.cm.ph.getSearchGroups(data, 'var\s+?mts_ajax_loadposts\s*=\s*([^;]+?);')[0].strip()
        try:
            nextPage = self.getFullUrl(str(byteify(json.loads(nextPage)).get('nextLink', '')))
        except Exception:
            nextPage = ''
            printExc()

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<article', '</article>', withMarkers=True)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0].strip())
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0])
            if desc == '':
                desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''title=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            self.addDir(params)

        if self.cm.isValidUrl(nextPage):
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1, 'url': nextPage})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("HDPopcornsCom.listEpisodes")

        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h2>Synopsis</h2>', '</p>', False)[1])
        cItem = dict(cItem)
        cItem['desc'] = desc

        tmp = self.cm.ph.rgetAllItemsBeetwenMarkers(data, '</iframe>', '<h2', withMarkers=True, caseSensitive=False)
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, '''src=['"](https?://[^'^"]+?)['"]''')[0]
            if 1 != self.up.checkHostSupport(url):
                continue
            title = self.cleanHtmlStr(item)

            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url})
            self.addVideo(params)

        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a ', '>', withMarkers=True, caseSensitive=False)
        for item in tmp:
            if 'playTrailer' not in item:
                continue

            url = self.cm.ph.getSearchGroups(item, '''href=['"](https?://[^'^"]+?)['"]''')[0]
            if 1 != self.up.checkHostSupport(url):
                continue

            title = '%s - Trailer %s' % (cItem['title'], len(self.currList) + 1)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url})
            self.addVideo(params)

        if '<form action' in data:
            params = dict(cItem)
            params.update({'good_for_fav': True})
            self.addVideo(params)

        data = self.cm.ph.getDataBeetwenMarkers(data, '<table', '</table>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            if not self.cm.isValidUrl(url):
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'urls': [{'name': 'default', 'url': url, 'need_resolve': False}]})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HDPopcornsCom.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('?s=' + urllib.quote_plus(searchPattern))

        self.listItems(cItem, 'list_episodes')

    def getLinksForVideo(self, cItem):
        printDBG("HDPopcornsCom.getLinksForVideo [%s]" % cItem)
        if 'urls' in cItem:
            return cItem.get('urls', [])
        elif 1 == self.up.checkHostSupport(cItem.get('url', '')):
            return self.up.getVideoLinkExt(cItem['url'])

        urlTab = []

        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []

        data = self.cm.ph.getDataBeetwenMarkers(data, '<form action', '</form>')[1]
        try:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0])
            post_data = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', data))

            params = dict(self.defaultParams)
            params['header'] = dict(params['header'])
            params['header']['Referer'] = cItem['url']

            sts, data = self.getPage(url, params, post_data)
            if not sts:
                return []

            printDBG("+++++++++++++++++++++++++++++++++++++++")
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="subtitles">', '</form>')[1]
            popcornsubtitlesUrl = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''action=['"]([^'^"]+?)['"]''')[0])
            printDBG("+++++++++++++++++++++++++++++++++++++++")

            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div id="btn', '</a>', withMarkers=True)
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                if '///downloads/' in url:
                    continue
                if not self.cm.isValidUrl(url):
                    continue
                name = self.cleanHtmlStr(item)
                url = strwithmeta(url.replace('&#038;', '&'), {'popcornsubtitles_url': popcornsubtitlesUrl})
                urlTab.append({'name': name, 'url': url, 'need_resolve': 0})
        except Exception:
            printExc()

        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("HDPopcornsCom.getVideoLinks [%s]" % videoUrl)
        urlTab = []

        if self.cm.isValidUrl(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def getFavouriteData(self, cItem):
        printDBG('HDPopcornsCom.getFavouriteData')
        return json.dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('HDPopcornsCom.getLinksForFavourite')
        links = []
        try:
            cItem = byteify(json.loads(fav_data))
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('HDPopcornsCom.setInitListFromFavouriteItem')
        try:
            params = byteify(json.loads(fav_data))
        except Exception:
            params = {}
            printExc()
        self.addDir(params)
        return True

    def getArticleContent(self, cItem):
        printDBG("Movs4uCOM.getArticleContent [%s]" % cItem)
        retTab = []

        otherInfo = {}

        url = cItem.get('prev_url', '')
        if url == '':
            url = cItem.get('url', '')

        sts, data = self.getPage(url)
        if not sts:
            return retTab
        self.setMainUrl(self.cm.meta['url'])

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h2>Synopsis</h2>', '</p>', False)[1])

        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="single_post">', '</h2>')[1]
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<header', '</header>')[1])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]+?src=['"]([^"^']+?\.jpe?g[^"^']*?)["']''')[0])

        mapDesc = {'Year': 'year', 'Quality': 'quality', 'Language': 'language', 'Genre': 'genres', 'Cast:': 'cast', 'Episodes': 'episodes'}
        tmp = re.compile('''>\s*([^\:]+?)\:(.+?)<br''').findall(data)
        for item in tmp:
            key = self.cleanHtmlStr(item[0])
            key = mapDesc.get(key, '')
            if key == '':
                continue
            value = self.cleanHtmlStr(item[1]).replace(' , ', ', ')
            if value != '':
                otherInfo[key] = value

        tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<a[^>]+?alt="IMDb-Rating"[^>]*?>'), re.compile('</a>'))[1])
        if tmp != '':
            otherInfo['imdb_rating'] = tmp

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

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif 'list_items' == category:
            filtersTab = ['ofcategory', 'ofrating', 'ofquality']
            idx = self.currItem.get('f_idx', 0)
            if idx < len(filtersTab):
                self.listFilter(self.currItem, filtersTab)
            else:
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
        CHostBase.__init__(self, HDPopcornsCom(), True, [])

    def withArticleContent(self, cItem):
        try:
            if (cItem['type'] == 'video' or cItem['category'] == 'list_episodes') and self.host.up.getDomain(cItem['url']) in self.host.getMainUrl():
                return True
        except Exception:
            printExc()
        return False
