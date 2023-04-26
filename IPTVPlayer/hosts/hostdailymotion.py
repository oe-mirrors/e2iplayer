# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, rm
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
import re
from datetime import timedelta
import time
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.dailymotion_localization = ConfigSelection(default="auto", choices=[("auto", _("auto")), ("ar_AA", "\xd8\xa7\xd9\x84\xd8\xb9\xd8\xb1\xd8\xa8\xd9\x8a\xd8\xa9"), ("es_AR", "Argentina"), ("en_AU", "Australia"), ("de_AT", "\xc3\x96sterreich"), ("nl_BE", "Belgi\xc3\xab"), ("fr_BE", "Belgique"), ("pt_BR", "Brasil"), ("en_CA", "Canada"), ("fr_CA", "Canada"), ("zh_CN", "\xe4\xb8\xad\xe5\x9b\xbd"), ("fr_FR", "France"), ("de_DE", "Deutschland"), ("el_GR", "\xce\x95\xce\xbb\xce\xbb\xce\xac\xce\xb4\xce\xb1"), ("en_IN", "India"), ("id_ID", "Indonesia"), ("en_EN", "International"), ("en_IE", "Ireland"), ("it_IT", "Italia"), ("ja_JP", "\xe6\x97\xa5\xe6\x9c\xac"), ("ms_MY", "Malaysia"), ("es_MX", "M\xc3\xa9xico"), ("fr_MA", "Maroc"), ("nl_NL", "Nederland"), ("en_PK", "Pakistan"), ("en_PH", "Pilipinas"), ("pl_PL", "Polska"), ("pt_PT", "Portugal"), ("ro_RO", "Rom\xc3\xa2nia"), ("ru_RU", "\xd0\xa0\xd0\xbe\xd1\x81\xd1\x81\xd0\xb8\xd1\x8f"), ("en_SG", "Singapore"), ("ko_KR", "\xeb\x8c\x80\xed\x95\x9c\xeb\xaf\xbc\xea\xb5\xad"), ("es_ES", "Espa\xc3\xb1a"), ("fr_CH", "Suisse"), ("it_CH", "Svizzera"), ("de_CH", "Schweiz"), ("fr_TN", "Tunisie"), ("tr_TR", "T\xc3\xbcrkiye"), ("en_GB", "United Kingdom"), ("en_US", "United States"), ("vi_VN", "Vi\xe1\xbb\x87t Nam")])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Localization"), config.plugins.iptvplayer.dailymotion_localization))
    return optionList
###################################################


def gettytul():
    return 'http://dailymotion.com/'


class Dailymotion(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Dailymotion', 'cookie': 'dailymotion.cookie'})
        self.HTTP_HEADER = {'User-Agent': self.cm.getDefaultHeader(browser='chrome')['User-Agent'], 'X-Requested-With': 'XMLHttpRequest'}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.SITE_URL = 'https://www.dailymotion.com/'
        self.MAIN_URL = 'https://api.dailymotion.com/'
        self.DEFAULT_ICON_URL = 'http://static1.dmcdn.net/images/dailymotion-logo-ogtag.png'
        self.MAIN_CAT_TAB = [{'category': 'categories', 'title': _('Categories')},
                             {'category': 'search', 'title': _('Search'), 'search_item': True},
                             {'category': 'search_history', 'title': _('Search history')}]

        self.SORT_TAB = [{'title': _('Most viewed'), 'sort': 'visited'},
                         {'title': _('Most recent'), 'sort': 'recent'},
                         {'title': _('Most rated'), 'sort': 'rated'},
                         {'title': _('Ranking'), 'sort': 'ranking'},
                         {'title': _('Trending'), 'sort': 'trending'},
                         {'title': _('Random'), 'sort': 'random'}, ]
                         #{'title':_('Most relevant'), 'sort':'relevance'}
                         #recent, visited, visited-hour, visited-today, visited-week, visited-month, commented, commented-hour, commented-today, commented-week, commented-month, rated, rated-hour, rated-today, rated-week, rated-month, relevance, random, ranking, trending, old, live-audience

        self.filterCache = {}
        self.apiData = {'client_type': 'androidapp', 'client_version': '4775', 'family_filter': 'false'}
        self.authData = {'client_id': '', 'client_secret': '', 'visitor_id': '', 'traffic_segment': '', 'url': '', 'auth_url': '', 'grant_type': 'client_credentials', 'expires': 0, 'token': ''}

    def getLocale(self):
        locale = config.plugins.iptvplayer.dailymotion_localization.value
        if 'auto' != locale:
            return locale
        all = [("ar_AA", "\xd8\xa7\xd9\x84\xd8\xb9\xd8\xb1\xd8\xa8\xd9\x8a\xd8\xa9"), ("es_AR", "Argentina"), ("en_AU", "Australia"), ("de_AT", "\xc3\x96sterreich"), ("nl_BE", "Belgi\xc3\xab"), ("fr_BE", "Belgique"), ("pt_BR", "Brasil"), ("en_CA", "Canada"), ("fr_CA", "Canada"), ("zh_CN", "\xe4\xb8\xad\xe5\x9b\xbd"), ("fr_FR", "France"), ("de_DE", "Deutschland"), ("el_GR", "\xce\x95\xce\xbb\xce\xbb\xce\xac\xce\xb4\xce\xb1"), ("en_IN", "India"), ("id_ID", "Indonesia"), ("en_EN", "International"), ("en_IE", "Ireland"), ("it_IT", "Italia"), ("ja_JP", "\xe6\x97\xa5\xe6\x9c\xac"), ("ms_MY", "Malaysia"), ("es_MX", "M\xc3\xa9xico"), ("fr_MA", "Maroc"), ("nl_NL", "Nederland"), ("en_PK", "Pakistan"), ("en_PH", "Pilipinas"), ("pl_PL", "Polska"), ("pt_PT", "Portugal"), ("ro_RO", "Rom\xc3\xa2nia"), ("ru_RU", "\xd0\xa0\xd0\xbe\xd1\x81\xd1\x81\xd0\xb8\xd1\x8f"), ("en_SG", "Singapore"), ("ko_KR", "\xeb\x8c\x80\xed\x95\x9c\xeb\xaf\xbc\xea\xb5\xad"), ("es_ES", "Espa\xc3\xb1a"), ("fr_CH", "Suisse"), ("it_CH", "Svizzera"), ("de_CH", "Schweiz"), ("fr_TN", "Tunisie"), ("tr_TR", "T\xc3\xbcrkiye"), ("en_GB", "United Kingdom"), ("en_US", "United States"), ("vi_VN", "Vi\xe1\xbb\x87t Nam")]
        tmp = GetDefaultLang(True)
        printDBG("GetDefaultLang [%s]" % tmp)
        for item in all:
            if item[0] == tmp:
                locale = tmp
                break
        if 'auto' == locale:
            locale = 'en_EN'
        return locale

    def getApiUrl(self, fun, page, args=[]):
        url = self.MAIN_URL + fun + '?'

        args.extend(['page={0}'.format(page), 'localization={0}'.format(self.getLocale())])
        for key in self.apiData:
            val = self.apiData[key]
            args.append('{0}={1}'.format(key, val))
        url += '&'.join(args)
        printDBG("Dailymotion.getApiUrl [%s]" % url)
        return url

    def addNextPage(self, cItem, nextPage, page):
        if nextPage:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listCategories(self, cItem, category):
        printDBG("Dailymotion.listCategories [%s]" % cItem)
        page = cItem.get('page', 1)
        url = self.getApiUrl('channels', page)
        sts, data = self.cm.getPage(url)
        if not sts:
            return
        nextPage = False
        params = dict(cItem)
        params.update({'title': _('All'), 'category': category})
        self.addDir(params)
        try:
            data = json_loads(data)
            nextPage = data['has_more']
            for item in data['list']:
                params = dict(cItem)
                params.update({'title': item['name'], 'cat_id': item['id'], 'desc': item['description'], 'category': category})
                self.addDir(params)
        except Exception:
            printExc()
        self.addNextPage(cItem, nextPage, page)

    def listSort(self, cItem, category):
        printDBG("Dailymotion.listSort [%s]" % cItem)
        params = dict(cItem)
        params['category'] = category
        self.listsTab(self.SORT_TAB, params)

    def listVideos(self, cItem, type='videos'):
        printDBG("Dailymotion.listVideos [%s]" % cItem)
        page = cItem.get('page', 1)
        if type in ('videos', 'playlist', 'channel'):
            args = ['thumbnail_ratio=widescreen', 'limit={0}'.format(20), 'fields={0}'.format(urllib_quote('id,mode,title,duration,views_total,created_time,channel,thumbnail_240_url,url,live_publish_url'))]
            icon_key = 'thumbnail_240_url'
            views_key = 'views_total'
            title_key = 'title'
            url_key = 'url'
            duration_key = 'duration'
            mode_key = 'mode'
            if type == 'playlist':
                type = 'playlist/%s/videos' % cItem['f_xid']
            else:
                args.insert(0, 'list=what-to-watch')
        elif 'tiles' == type:
            args = ['thumbnail_ratio=widescreen', 'limit={0}'.format(20), 'fields={0}'.format(urllib_quote('video.id,video.mode,video.title,video.duration,video.views_total,created_time,video.channel,video.thumbnail_240_url,video.url,video.live_publish_url'))]
            icon_key = 'video.thumbnail_240_url'
            views_key = 'video.views_total'
            title_key = 'video.title'
            url_key = 'video.url'
            duration_key = 'video.duration'
            mode_key = 'video.mode'

        if 'cat_id' in cItem:
            args.append('channel={0}'.format(cItem['cat_id']))
        if 'sort' in cItem:
            args.append('sort={0}'.format(cItem['sort']))
        if 'search' in cItem:
            args.append('search={0}'.format(cItem['search']))

        url = self.getApiUrl(type, page, args)
        sts, data = self.cm.getPage(url)
        if not sts:
            return
        nextPage = False
        try:
            data = json_loads(data)
            nextPage = data['has_more']
            for item in data['list']:
                printDBG(item)
                if item[mode_key] == 'vod':
                    params = dict(cItem)
                    desc = str(timedelta(seconds=item[duration_key])) + ' | '
                    desc += _('views') + ': {0}'.format(item[views_key])
                    params.update({'title': item[title_key], 'url': item[url_key], 'icon': item.get(icon_key, ''), 'desc': desc})
                    self.addVideo(params)
        except Exception:
            printExc()
        self.addNextPage(cItem, nextPage, page)

    def getAuthToken(self):
        if '' in (self.authData['client_id'], self.authData['client_secret'], self.authData['visitor_id'], self.authData['traffic_segment'], self.authData['url'], self.authData['auth_url'], self.authData['token']):
            rm(self.COOKIE_FILE)

            sts, data = self.cm.getPage(self.SITE_URL, self.defaultParams)
            if not sts:
                return ''

            data = re.compile('''return h.*;var r=['"]([^"^']+?)['"],o=['"]([^"^']+?)['"].*,v=.*__API_ENDPOINT__[^"^']+?['"]([^"^']+?)['"].*,h=.*__AUTH_ENDPOINT__[^"^']+?['"]([^"^']+?)['"]''').findall(data)
            for item in data:
                self.authData['auth_url'] = item[3]
                self.authData['url'] = item[2]
                self.authData['client_secret'] = item[1]
                self.authData['client_id'] = item[0]
            self.authData['grant_type'] = 'client_credentials'


        if self.authData.get('expires', 0) < int(time.time()):
            params = dict(self.defaultParams)
            params['header'] = dict(params['header'])
            params['header']['Origin'] = self.SITE_URL[:-1]
            params['header']['Referer'] = self.SITE_URL
            cj = self.cm.getCookieItems(self.COOKIE_FILE)
            self.authData['visitor_id'] = cj.get('v1st', '')
            self.authData['traffic_segment'] = cj.get('ts', '')
            post_data = {'client_id': self.authData['client_id'], 'client_secret': self.authData['client_secret'], 'grant_type': self.authData['grant_type'], 'visitor_id': self.authData['visitor_id'], 'traffic_segment': self.authData['traffic_segment']}
            sts, data = self.cm.getPage(self.authData['auth_url'], params, post_data)
            if not sts:
                return ''

            printDBG(data)
            try:
                data = json_loads(data)
                self.authData['token'] = str(data['access_token'])
                self.authData['expires'] = int(time.time()) + int(data['expires_in'])
                return self.authData['token']
            except Exception:
                printExc()

        return self.authData.get('token', '')

    def getApiHeaders(self, cItem):
        params = {}
        params['header'] = {'User-Agent': self.HTTP_HEADER['User-Agent'], 'Accept-Encoding': 'gzip, deflate, br', 'Accept-Language': 'en-US,en;q=0.9,pl;q=0.8', 'Content-Type': 'application/json', 'Accept': '*/*'}
        params['header']['Referer'] = self.SITE_URL
        params['header']['Origin'] = self.SITE_URL[:-1]
        params['header']['Authorization'] = 'Bearer %s' % self.getAuthToken()
        params['raw_post_data'] = True
        return params

    def listSiteSeach(self, cItem):
        printDBG("Dailymotion.listSiteSeach")
        token = self.getAuthToken()
        if token == '':
            return

        type = cItem['f_type']
        page = cItem.get('page', 1)

        limits = {type: 20}
        pages = {type: page}

        params = self.getApiHeaders(cItem)
        post_data = '{"operationName":"SEARCH_QUERY","variables":{"query":"%s","pageVideo":%d,"pageLive":%d,"pageChannel":%d,"pageCollection":%d,"limitVideo":%d,"limitLive":%d,"limitChannel":%d,"limitCollection":%d,"uri":"/search/%s/%s"},"query":"fragment METADATA_FRAGMENT on Neon { web(uri: $uri) { author description title metadatas { attributes { name content __typename } __typename } language { codeAlpha2 __typename } country { codeAlpha2 __typename } __typename } __typename } fragment LOCALIZATION_FRAGMENT on Localization { me { id country { codeAlpha2 name __typename } __typename } __typename } query SEARCH_QUERY($query: String!, $pageVideo: Int, $pageLive: Int, $pageChannel: Int, $pageCollection: Int, $limitVideo: Int, $limitLive: Int, $limitChannel: Int, $limitCollection: Int, $uri: String!) { views { id neon { id ...METADATA_FRAGMENT __typename } __typename } localization { ...LOCALIZATION_FRAGMENT __typename } search { lives(query: $query, first: $limitLive, page: $pageLive) { pageInfo { hasNextPage nextPage __typename } edges { node { id xid title thumbURLx240: thumbnailURL(size: \\"x240\\") thumbURLx360: thumbnailURL(size: \\"x360\\") __typename } __typename } __typename } videos(query: $query, first: $limitVideo, page: $pageVideo) { pageInfo { hasNextPage nextPage __typename } edges { node { id xid title channel { id displayName __typename } duration thumbURLx240: thumbnailURL(size: \\"x240\\") thumbURLx360: thumbnailURL(size: \\"x360\\") __typename } __typename } __typename } channels(query: $query, first: $limitChannel, page: $pageChannel) { pageInfo { hasNextPage nextPage __typename } edges { node { id xid name description displayName accountType logoURL(size: \\"x60\\") __typename } __typename } __typename } playlists: collections(query: $query, first: $limitCollection, page: $pageCollection) { pageInfo { hasNextPage nextPage __typename } edges { node { id xid name channel { id displayName __typename } description thumbURLx240: thumbnailURL(size: \\"x240\\") thumbURLx480: thumbnailURL(size: \\"x480\\") stats { videos { total __typename } __typename } __typename } __typename } __typename } topics(query: $query, first: 5, page: 1) { pageInfo { hasNextPage nextPage __typename } edges { node { id xid name isFollowed __typename } __typename } __typename } __typename } } "}'
        post_data = post_data % (cItem['f_query'], pages.get('videos', 1), pages.get('lives', 1), pages.get('channels', 1), pages.get('playlists', 1), limits.get('videos', 0), limits.get('lives', 0), limits.get('channels', 0), limits.get('playlists', 0), urllib_quote(cItem['f_query']), cItem['f_type'])

        sts, data = self.cm.getPage(self.authData['url'], params, post_data)
        if not sts:
            return

        try:
            data = json_loads(data)['data']['search'][type]
            for item in data['edges']:
                item = item['node']
                if item['__typename'] == 'Collection':
                    title = item['name'] + ' (%s)' % item['stats']['videos']['total']
                    desc = []
                    desc.append('%s: %s' % (item['channel']['__typename'], item['channel']['displayName']))
                    if item.get('description'):
                        desc.append(item['description'])
                    params = {'good_for_fav': True, 'name': 'category', 'category': 'list_playlist', 'title': title, 'f_xid': item['xid'], 'icon': item['thumbURLx480'], 'desc': '[/br]'.join(desc)}
                    self.addDir(params)
                elif item['__typename'] == 'Channel':
                    title = item['displayName']
                    desc = [item['accountType']]
                    if item.get('description'):
                        desc.append(item['description'])
                    params = {'good_for_fav': True, 'name': 'category', 'category': 'list_channel', 'title': item['displayName'], 'f_xid': item['xid'], 'f_name': item['name'], 'icon': item['logoURL'], 'desc': '[/br]'.join(desc)}
                    self.addDir(params)
            self.addNextPage(cItem, data['pageInfo']['hasNextPage'], data['pageInfo']['nextPage'])
        except Exception:
            printExc()

        printDBG(data)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Dailymotion.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        currItem = dict(cItem)
        if searchType == 'videos':
            currItem['search'] = urllib_quote(searchPattern)
            currItem['sort'] = 'relevance'
            self.listVideos(currItem, 'tiles')
        else:
            currItem['category'] = 'site_seach'
            currItem['f_type'] = searchType
            currItem['f_query'] = searchPattern
            self.listSiteSeach(currItem)

    def getLinksForVideo(self, cItem):
        printDBG("Dailymotion.getLinksForVideo [%s]" % cItem)
        urlTab = []

        tmpTab = self.up.getVideoLinkExt(cItem.get('url', ''))
        for item in tmpTab:
            item['need_resolve'] = 0
            urlTab.append(item)
        return urlTab

    def getLinksForFavourite(self, fav_data):
        try:
            item = json_loads(fav_data)
        except Exception:
            printExc(fav_data)
            item = {'url': fav_data}
        return self.getLinksForVideo(item)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
    #CATEGORIES
        elif category == 'categories':
            self.listCategories(self.currItem, 'category')
    #SORT
        elif category == 'sort':
            self.listSort(self.currItem, 'category')
    #CATEGORY
        elif category == 'category':
            self.listVideos(self.currItem)

        elif category == 'site_seach':
            self.listSiteSeach(self.currItem)
        elif category == 'list_playlist':
            self.listVideos(self.currItem, 'playlist')
        #elif category == 'list_channel':
        #    self.listVideos(self.currItem, 'channel')

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
        CHostBase.__init__(self, Dailymotion(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Videos"), "videos"))
        #searchTypesOptions.append((_("Lives"),     "lives"))
        #searchTypesOptions.append((_("Topics"),    "topics"))
        #searchTypesOptions.append((_("Channels"),  "channels"))
        searchTypesOptions.append((_("Playlists"), "playlists"))
        return searchTypesOptions
