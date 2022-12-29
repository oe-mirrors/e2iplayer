# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.egybest_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.egybest_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("login") + ":", config.plugins.iptvplayer.egybest_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.egybest_password))
    return optionList
###################################################


def gettytul():
    return 'http://egy.best/'


class EgyBest(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'egy.best', 'cookie': 'egy.best.cookie'})
        self.DEFAULT_ICON_URL = 'http://cdn.egy.best/static/img/egybest_logo.png'
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://egy.best/'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_CAT_TAB = [{'category': 'list_filters', 'title': _('Trending'), 'url': self.getFullUrl('/trending/')},
                             {'category': 'list_filters', 'title': _('Movies'), 'url': self.getFullUrl('/movies/')},
                             {'category': 'list_filters', 'title': _('Arabic movies'), 'url': self.getFullUrl('/movies/'), 'f_sort': 'arab'},
                             {'category': 'list_filters', 'title': _('With subtitles'), 'url': self.getFullUrl('/movies/'), 'f_sort': 'subbed'},
                             {'category': 'list_filters', 'title': _('TV series'), 'url': self.getFullUrl('/tv/')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')},
                            ]
        self.loggedIn = None
        self.login = ''
        self.password = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)
        addParams['cloudflare_params'] = {'domain': self.up.getDomain(baseUrl), 'cookie_file': self.COOKIE_FILE, 'User-Agent': self.USER_AGENT, 'full_url_handle': _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def fillCacheFilters(self, cItem):
        printDBG("EgyBest.listCategories")
        self.cacheFilters = {}
        self.cacheFiltersKeys = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        def addFilter(data, marker, baseKey, allTitle=None):
            key = 'f_' + baseKey
            self.cacheFilters[key] = []
            for item in data:
                value = self.cm.ph.getSearchGroups(item, marker + '''="([^"]+?)"''')[0].split('/')[-1]
                title = self.cleanHtmlStr(item)
                if value == '':
                    if allTitle == None:
                        allTitle = title
                    continue
                self.cacheFilters[key].append({'title': title.title(), key: value})

            if len(self.cacheFilters[key]):
                if allTitle != None:
                    self.cacheFilters[key].insert(0, {'title': _('All')})
                self.cacheFiltersKeys.append(key)

        if '' == cItem.get('f_sort', ''):
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'rs_scroll_parent'), ('</div', '>'), False)[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
            addFilter(tmp, 'href', 'sort')

        keyMap = {0: 'year', 1: 'language', 2: 'country', 3: 'genre', 4: 'category', 5: 'quality', 6: 'resolution'}
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'dropdown'), ('</div', '>'))
        for idx in range(len(data)):
            tmp = data[idx]
            key = keyMap.get(idx, '')
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')
            addFilter(tmp, 'href', key, _('--Any--'))

        printDBG(self.cacheFilters)

    def listFilters(self, cItem, nextCategory):
        printDBG("EgyBest.listFilters")
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

    def listMainMenu(self, cItem, nextCategory):
        printDBG("EgyBest.listMainMenu")

        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listItems(self, cItem, nextCategory):
        printDBG("EgyBest.listItems [%s]" % cItem)
        page = cItem.get('page', 1)

        url = cItem['url']
        if not url.endswith('/'):
            url += '/'

        if '' == cItem.get('f_search_query', ''):
            query = []
            filtersKeys = ['resolution', 'language', 'sort', 'category', 'genre', 'country', 'quality', 'year']
            for key in filtersKeys:
                key = 'f_' + key
                if key in cItem:
                    query.append(cItem[key])

            url += '-'.join(query) + ('?page=%s&output_format=json&output_mode=movies_list' % page)
        else:
            url += ('?page=%s&q=%s&output_format=json' % (page, urllib_quote(cItem['f_search_query'])))

        sts, data = self.getPage(url)
        if not sts:
            return

        nextPage = False
        try:
            data = byteify(json.loads(data), '', True)['html']
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
            if len(data) and '' != self.cm.ph.getSearchGroups(data[-1], '''[/\?&]page=(%s)[^0-9]''' % (page + 1))[0]:
                nextPage = True
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span', '</span>')
                if tmp == []:
                    continue
                title = self.cleanHtmlStr(tmp[1])
                desc = ''
                for d in tmp[1:]:
                    d = self.cleanHtmlStr(d)
                    if d != '':
                        desc = d + '[/br]'
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc})
                self.addDir(params)
        except Exception:
            printExc()

        if nextPage:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1})
            self.addDir(params)

    def exploreItem(self, cItem, nextCategory):
        printDBG("EgyBest.exploreItem")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        num = 1
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'trailer'), ('</div', '>'))
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''url=['"]([^'^"]+?)['"]''')[0])
            if not self.cm.isValidUrl(url):
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            title = '%s - %s' % (cItem['title'], _('Trailer'))
            if num > 1:
                title += ' %s' % num
            params = dict(cItem)
            params.update({'good_for_fav': False, 'url': url, 'title': title, 'icon': icon})
            self.addVideo(params)
            num += 1

        # embedded player
        frame_url = self.cm.ph.getSearchGroups(data, '''<iframe.*?src=['"]([^'^"]+?)['"]''')[0]
        params = dict(cItem)
        params.update({'good_for_fav': False, 'url': frame_url, 'title': (cItem['title'] + ' - embed player'), 'icon': cItem['icon'], 'need_resolve': 1})
        printDBG(str(params))
        self.addVideo(params)

        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''href=['"]([^'^"]+?/episodes)['"]''')[0])
        if self.cm.isValidUrl(url):
            sts, data = self.getPage(url)
            if not sts:
                return

        # list seasons
        seasonsItems = []
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '</div>', 'مشاهدة جميع مواسم'), ('</div', '>'), False)[1]
        seasonsItems = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<a', '</a>')

        if len(seasonsItems):
            for item in seasonsItems:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
                title = self.cleanHtmlStr(item)
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon})
                self.addDir(params)
        elif 'watch_video' in data or 'data-call' in data:
            params = dict(cItem)
            self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("EgyBest.listEpisodes")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<a', '>', 'tvep'), ('</a', '>'), True)
        for item in data:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"]+?)['"]''')[0])
            title = self.cleanHtmlStr(item)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'icon': icon})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EgyBest.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['f_search_query'] = searchPattern
        cItem['url'] = self.getFullUrl('/explore/')
        self.listItems(cItem, 'explore_item')

    def getLinksForVideo(self, cItem):
        printDBG("EgyBest.getLinksForVideo [%s]" % cItem)
        self.tryTologin()

        retTab = []
        playTab = []
        dwnTab = []
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

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<video', '</video>', False, False)[1]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<source', '>', caseSensitive=False)
        for item in tmp:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''')[0])
            type = self.cm.ph.getSearchGroups(item, '''\stype=['"]([^'^"]+?)['"]''')[0].lower()
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> ]]]]]]]]]]]]]]]]]]]]]]]] >>>>>>>>> " + url)
            printDBG(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> ]]]]]]]]]]]]]]]]]]]]]]]] >>>>>>>>> " + type)
            if url == '':
                continue
            if 'application/x-mpegurl' == type:
                name = '[HLS/m3u8]'
                meta = {'iptv_proto': 'm3u8'}
            elif 'video/mp4' == type:
                name = '[mp4]'
                meta = {'direct': True}
            else:
                continue
            meta.update({'Referer': cUrl})
            playTab.append({'name': name, 'url': strwithmeta(self.getFullUrl(url, cUrl), meta), 'need_resolve': 1})

        data = self.cm.ph.getDataBeetwenNodes(data, ('<table', '>', 'dls_table'), ('</table', '>'), False)[1]
        data = self.cm.ph.getDataBeetwenMarkers(data, '<tbody>', '</tbody>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in data:
            item = self.cm.ph.getAllItemsBeetwenMarkers(item, '<td', '</td>')[::-1]
            if len(item) < 2:
                continue

            name = '|'.join([self.cleanHtmlStr(t) for t in item[1:]])
            item = self.cm.ph.getAllItemsBeetwenMarkers(item[0], '<a', '</a>')
            for it in item:
                url = self.cm.ph.getSearchGroups(it, '''href=['"]([^'^"]+?)['"]''')[0]
                if url == '':
                    url = self.cm.ph.getSearchGroups(it, '''url=['"]([^'^"]+?)['"]''')[0]
                call = self.cm.ph.getSearchGroups(it, '''data\-call=['"]([^'^"]+?)['"]''')[0]
                if url != '' and '&v=1' in url:
                    retTab.append({'name': '%s: %s' % (self.cleanHtmlStr(it), name), 'url': strwithmeta(self.getFullUrl(url), {'Referer': cItem['url']}), 'need_resolve': 1})
                if call != '':
                    dwnTab.append({'name': '%s: %s' % (self.cleanHtmlStr(it), name), 'url': strwithmeta(call, {'priv_api_call': True, 'Referer': cItem['url']}), 'need_resolve': 1})

        retTab.extend(playTab)
        retTab.extend(dwnTab)
        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, videoUrl):
        printDBG("EgyBest.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        if videoUrl.meta.get('iptv_proto', '') == 'm3u8':
            return getDirectM3U8Playlist(videoUrl, False, checkContent=True, sortWithMaxBitrate=999999999)
        elif videoUrl.meta.get('direct', False):
            return [{'name': 'direct', 'url': videoUrl}]

        params = dict(self.defaultParams)
        params['header'] = dict(self.AJAX_HEADER)
        params['header']['Referer'] = videoUrl.meta.get('Referer', '')
        params['with_metadata'] = True

        if videoUrl.meta.get('priv_api_call', False):
            url = self.getFullUrl('/api?call=' + videoUrl)
        else:
            url = videoUrl

        if 'api?call=' in url:
            sts, data = self.getPage(url, params)
            if not sts:
                return []
            videoUrl = strwithmeta(data.meta['url'], videoUrl.meta)
            if 1 != self.up.checkHostSupport(videoUrl):
                try:
                    data = byteify(json.loads(data), '', True)
                    if data.get('status', '') == '200':
                        authUrl = data.get('auth_url', '')
                        url = data.get('url', '')
                        if self.cm.isValidUrl(url) and self.cm.isValidUrl(authUrl):
                            sts, tmp = self.getPage(authUrl)
                            if sts:
                                urlTab.append({'name': 'direct', 'url': url})
                    elif data.get('action', '') == 'message':
                        SetIPTVPlayerLastHostError(self.cleanHtmlStr(data['message']))
                        printDBG(self.cleanHtmlStr(data['message']))
                    printDBG(data)
                except Exception:
                    printExc()

        if 1 == self.up.checkHostSupport(videoUrl):
            urlTab = self.up.getVideoLinkExt(videoUrl)

        return urlTab

    def getArticleContent(self, cItem, data=None):
        printDBG("EgyBest.getArticleContent [%s]" % cItem)
        self.tryTologin()

        retTab = []

        otherInfo = {}

        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return []

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ('<strong', '</div>', 'القصة'), ('</div', '>'), False)[1])
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'full_movie'), ('</table', '>'), False)[1]
        icon = self.cm.ph.getDataBeetwenNodes(tmp, ('<div', '>', 'movie_img'), ('</div', '>'), False)[1]
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(icon, '''src=['"]([^'^"]+?)['"]''')[0])
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(tmp, ('<div', '>', 'movie_title'), ('</div', '>'), False)[1])

        keysMap = {'اللغة • البلد': 'country',
                   'التصنيف': 'type',
                   'النوع': 'genres',
                   'التقييم العالمي': 'rating',
                   'المدة': 'duration',
                   'الجودة': 'quality',
                   'الترجمة': 'translation'}

        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<tr>', '</tr>')
        for item in tmp:
            item = item.split('</td>', 1)
            if len(item) != 2:
                continue
            keyMarker = self.cleanHtmlStr(item[0]).replace(':', '').strip()
            printDBG("+++ keyMarker[%s]" % keyMarker)
            value = self.cleanHtmlStr(item[1]).replace(' , ', ', ')
            key = keysMap.get(keyMarker, '')
            if key != '' and value != '':
                otherInfo[key] = value

        # actors
        tTab = []
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'cast_item'), ('</span', '>'))
        for t in tmp:
            t = self.cleanHtmlStr(t)
            if t != '':
                tTab.append(t)
        if len(tTab):
            otherInfo['actors'] = ', '.join(tTab)

        if title == '':
            title = cItem['title']
        if desc == '':
            desc = cItem.get('desc', '')
        if icon == '':
            icon = cItem.get('icon', self.DEFAULT_ICON_URL)

        return [{'title': self.cleanHtmlStr(title), 'text': self.cleanHtmlStr(desc), 'images': [{'title': '', 'url': self.getFullUrl(icon)}], 'other_info': otherInfo}]

    def tryTologin(self):
        printDBG('tryTologin start')

        if None == self.loggedIn or self.login != config.plugins.iptvplayer.egybest_login.value or\
            self.password != config.plugins.iptvplayer.egybest_password.value:

            self.login = config.plugins.iptvplayer.egybest_login.value
            self.password = config.plugins.iptvplayer.egybest_password.value

            rm(self.COOKIE_FILE)

            self.loggedIn = False

            if '' == self.login.strip() or '' == self.password.strip():
                return False

            sts, data = self.getPage(self.getMainUrl())
            if not sts:
                return False

            url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<a[^>]+?href=['"]([^'^"]+?)['"][^>]*?>[^<]*?تسجيل الدخول[^<]*?</a>''')[0])

            sts, data = self.getPage(url)
            if not sts:
                return False

            sts, data = self.cm.ph.getDataBeetwenNodes(data, ('<form', '>', 'login_form'), ('</form', '>'))
            if not sts:
                return False
            actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''action=['"]([^'^"]+?)['"]''')[0])
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input', '>')
            post_data = {}
            for item in data:
                name = self.cm.ph.getSearchGroups(item, '''name=['"]([^'^"]+?)['"]''')[0]
                value = self.cm.ph.getSearchGroups(item, '''value=['"]([^'^"]+?)['"]''')[0]
                post_data[name] = value

            post_data.update({'username': self.login, 'password': self.password})

            httpParams = dict(self.defaultParams)
            httpParams['header'] = dict(httpParams['header'])
            httpParams['header']['Referer'] = url
            sts, data = self.cm.getPage(actionUrl, httpParams, post_data)
            if sts and '/logout' in data and 'تسجيل الدخول' not in data:
                printDBG('tryTologin OK')
                self.loggedIn = True
            else:
                self.sessionEx.open(MessageBox, _('Login failed.'), type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG('tryTologin failed')
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        self.tryTologin()

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'}, 'list_genres')
        elif category == 'list_filters':
            self.listFilters(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')
        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_episodes')
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
        CHostBase.__init__(self, EgyBest(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('good_for_fav', False)
