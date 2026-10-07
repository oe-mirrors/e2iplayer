# -*- coding: utf-8 -*-
# Last Modified: 27.09.2026
# 27.09.2026 - the site's GraphQL search answers only empty lists and the REST playlist search needs a
# logged-in user: search types are now Videos + Channels (REST users?search, channel -> its videos).
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
from datetime import timedelta
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
    return 'https://dailymotion.com/'


class Dailymotion(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Dailymotion', 'cookie': 'dailymotion.cookie'})
        self.HTTP_HEADER = {'User-Agent': self.cm.getDefaultHeader(browser='chrome')['User-Agent'], 'X-Requested-With': 'XMLHttpRequest'}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.SITE_URL = 'https://www.dailymotion.com/'
        self.MAIN_URL = 'https://api.dailymotion.com/'
        self.DEFAULT_ICON_URL = 'https://static1.dmcdn.net/images/dailymotion-logo-ogtag.png'
        self.MAIN_CAT_TAB = [{'category': 'categories', 'title': _('Categories')}] + self.searchItems()

        self.SORT_TAB = [{'title': _('Most viewed'), 'sort': 'visited'},
                         {'title': _('Most recent'), 'sort': 'recent'},
                         {'title': _('Most rated'), 'sort': 'rated'},
                         {'title': _('Ranking'), 'sort': 'ranking'},
                         {'title': _('Trending'), 'sort': 'trending'},
                         {'title': _('Random'), 'sort': 'random'}, ]
                         # {'title':_('Most relevant'), 'sort':'relevance'}
                         # recent, visited, visited-hour, visited-today, visited-week, visited-month, commented, commented-hour, commented-today, commented-week, commented-month, rated, rated-hour, rated-today, rated-week, rated-month, relevance, random, ranking, trending, old, live-audience

        self.filterCache = {}
        self.apiData = {'client_type': 'androidapp', 'client_version': '4775', 'family_filter': 'false'}

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
            elif type == 'channel':
                type = 'user/%s/videos' % cItem['f_xid']
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

    def listChannels(self, cItem):
        printDBG("Dailymotion.listChannels [%s]" % cItem)
        page = cItem.get('page', 1)
        args = ['search={0}'.format(urllib_quote(cItem['f_query'])), 'limit={0}'.format(20), 'fields={0}'.format(urllib_quote('id,screenname,description,avatar_240_url,videos_total'))]
        sts, data = self.cm.getPage(self.getApiUrl('users', page, args))
        if not sts:
            return
        nextPage = False
        try:
            data = json_loads(data)
            nextPage = data.get('has_more', False)
            for item in data.get('list') or []:
                if not item.get('videos_total'):
                    continue
                params = {'good_for_fav': True, 'name': 'category', 'category': 'list_channel', 'title': '%s (%s)' % (item.get('screenname', ''), item['videos_total']),
                          'f_xid': item['id'], 'icon': item.get('avatar_240_url', ''), 'desc': self.cleanHtmlStr(item.get('description') or '')}
                self.addDir(params)
        except Exception:
            printExc()
        self.addNextPage(cItem, nextPage, page)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Dailymotion.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))

        currItem = dict(cItem)
        if searchType == 'videos':
            currItem['search'] = urllib_quote(searchPattern)
            currItem['sort'] = 'relevance'
            self.listVideos(currItem, 'tiles')
        else:
            # "channels" - also what a "playlists" search from the search history lands on now
            currItem['category'] = 'list_channels'
            currItem['f_query'] = searchPattern
            self.listChannels(currItem)

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

    # MAIN MENU
        if name is None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
    # CATEGORIES
        elif category == 'categories':
            self.listCategories(self.currItem, 'category')
    # SORT
        elif category == 'sort':
            self.listSort(self.currItem, 'category')
    # CATEGORY
        elif category == 'category':
            self.listVideos(self.currItem)

        elif category == 'list_channels':
            self.listChannels(self.currItem)
        elif category == 'list_playlist':
            self.listVideos(self.currItem, 'playlist')
        elif category == 'list_channel':
            self.listVideos(self.currItem, 'channel')

    # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    # HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Dailymotion(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Videos"), "videos"))
        # searchTypesOptions.append((_("Lives"),     "lives"))
        # searchTypesOptions.append((_("Topics"),    "topics"))
        searchTypesOptions.append((_("Channels"), "channels"))
        return searchTypesOptions
