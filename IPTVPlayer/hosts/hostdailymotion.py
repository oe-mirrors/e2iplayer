# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# Dailymotion - public REST API (api.dailymotion.com): categories -> sort -> videos, live streams, channels ->
#   playlists -> videos, search (videos / channels). Playback through urlparser (dailymotion parser).
# 27.09.2026 - the site's GraphQL search answers only empty lists and the REST playlist search needs a
# logged-in user: search types are now Videos + Channels (REST users?search, channel -> its videos).
# 08.10.2026 - host standard: watched flag (channel -> playlist -> video), favourites, INFO from the API (video,
#   channel, playlist), sidecar, First/Jump/Next page with the last page from the API total; categories now
#   ask for the sort order (the old "what-to-watch" list only had videos from 2019, "rated"/"ranking" are gone),
#   live streams menu, a channel shows its playlists, readable localisation names on Python 3, fixed the
#   query arguments piling up between requests (mutable default argument), date in the video name (naming option)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
###################################################
# FOREIGN import
###################################################
import time
from datetime import timedelta
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################

LOCALES = [("ar_AA", "العربية"), ("es_AR", "Argentina"), ("en_AU", "Australia"), ("de_AT", "Österreich"), ("nl_BE", "België"),
           ("fr_BE", "Belgique"), ("pt_BR", "Brasil"), ("en_CA", "Canada"), ("fr_CA", "Canada"), ("zh_CN", "中国"), ("fr_FR", "France"),
           ("de_DE", "Deutschland"), ("el_GR", "Ελλάδα"), ("en_IN", "India"), ("id_ID", "Indonesia"), ("en_EN", "International"),
           ("en_IE", "Ireland"), ("it_IT", "Italia"), ("ja_JP", "日本"), ("ms_MY", "Malaysia"), ("es_MX", "México"), ("fr_MA", "Maroc"),
           ("nl_NL", "Nederland"), ("en_PK", "Pakistan"), ("en_PH", "Pilipinas"), ("pl_PL", "Polska"), ("pt_PT", "Portugal"),
           ("ro_RO", "România"), ("ru_RU", "Россия"), ("en_SG", "Singapore"), ("ko_KR", "대한민국"), ("es_ES", "España"),
           ("fr_CH", "Suisse"), ("it_CH", "Svizzera"), ("de_CH", "Schweiz"), ("fr_TN", "Tunisie"), ("tr_TR", "Türkiye"),
           ("en_GB", "United Kingdom"), ("en_US", "United States"), ("vi_VN", "Việt Nam")]

PER_PAGE = 20
MAX_RESULTS = 1000  # the API answers nothing beyond page * limit = 1000
VIDEO_FIELDS = 'id,mode,title,duration,views_total,created_time,thumbnail_240_url,url,owner.id,owner.screenname'

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.dailymotion_localization = ConfigSelection(default="auto", choices=[("auto", _("auto"))] + LOCALES)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Localization"), config.plugins.iptvplayer.dailymotion_localization))
    return optionList
###################################################


def gettytul():
    return 'https://dailymotion.com/'


class Dailymotion(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'Dailymotion', 'cookie': 'dailymotion.cookie'})
        self.HTTP_HEADER = {'User-Agent': self.cm.getDefaultUserAgent(), 'X-Requested-With': 'XMLHttpRequest'}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.SITE_URL = 'https://www.dailymotion.com/'
        self.MAIN_URL = 'https://api.dailymotion.com/'
        self.DEFAULT_ICON_URL = 'https://static1.dmcdn.net/images/dailymotion-logo-ogtag.png'

        self.SORT_TAB = [{'title': _('Trending'), 'sort': 'trending'},
                         {'title': _('Most recent'), 'sort': 'recent'},
                         {'title': _('Most viewed'), 'sort': 'visited'},
                         {'title': _('Random'), 'sort': 'random'}]
        self.apiData = {'client_type': 'androidapp', 'client_version': '4775', 'family_filter': 'false'}
        self.watchedHelper = IPTVWatchedHelper('dailymotion')
        self.wfInitFolderCache()

    def getLocale(self):
        locale = config.plugins.iptvplayer.dailymotion_localization.value
        if 'auto' != locale:
            return locale
        tmp = GetDefaultLang(True)
        printDBG("GetDefaultLang [%s]" % tmp)
        if tmp in [code for code, _title in LOCALES]:
            return tmp
        return 'en_EN'

    def getApiUrl(self, fun, page=None, args=None):
        args = list(args or [])
        if page is not None:
            args.append('page={0}'.format(page))
        args.append('localization={0}'.format(self.getLocale()))
        for key in self.apiData:
            args.append('{0}={1}'.format(key, self.apiData[key]))
        url = self.MAIN_URL + fun + '?' + '&'.join(args)
        printDBG("Dailymotion.getApiUrl [%s]" % url)
        return url

    def getApi(self, fun, page=None, args=None):
        sts, data = self.cm.getPage(self.getApiUrl(fun, page, args), dict(self.defaultParams))
        if not sts:
            return {}
        try:
            data = json_loads(data)
            if isinstance(data, dict):
                if data.get('error'):
                    printDBG("Dailymotion.getApi error: %s" % data['error'])
                return data
        except Exception:
            printExc()
        return {}

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            return 1

    def _addPaging(self, cItem, data, page):
        total = data.get('total') or 0
        lastPage = (min(int(total), MAX_RESULTS) + PER_PAGE - 1) // PER_PAGE if total else 0
        addPagingItems(self, cItem, page, bool(data.get('has_more')) and (not lastPage or page < lastPage), lastPage)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('search_item') or cItem.get('name') == 'history':
                return ''
            if cItem.get('type') == 'video':
                return 'video:%s' % cItem['xid'] if cItem.get('xid') and not cItem.get('is_live') else ''
            if cItem.get('category') == 'list_channel' and cItem.get('f_xid'):
                return 'folder:channel:%s' % cItem['f_xid']
            if cItem.get('category') == 'list_playlists' and cItem.get('f_xid'):
                return 'folder:playlists:%s' % cItem['f_xid']
            if cItem.get('category') == 'list_playlist' and cItem.get('f_xid'):
                return 'folder:playlist:%s' % cItem['f_xid']
        except Exception:
            printExc()
        return ''

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        MAIN_CAT_TAB = [{'category': 'categories', 'title': _('Categories')},
                        {'category': 'list_videos', 'title': _('Live'), 'live': True, 'good_for_fav': True}]
        self.listsTab(MAIN_CAT_TAB + self.searchItems(), cItem)

    def listCategories(self, cItem):
        printDBG("Dailymotion.listCategories [%s]" % cItem)
        params = dict(cItem)
        params.update({'good_for_fav': True, 'title': _('All'), 'category': 'sort'})
        self.addDir(params)
        data = self.getApi('channels', None, ['limit=100'])
        for item in data.get('list') or []:
            if not item.get('id'):
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': item.get('name') or item['id'], 'cat_id': item['id'], 'desc': item.get('description') or '', 'category': 'sort'})
            self.addDir(params)

    def listSort(self, cItem):
        params = dict(cItem)
        params.update({'category': 'list_videos', 'good_for_fav': True})
        self.listsTab(self.SORT_TAB, params)

    def _addVideoItem(self, cItem, item):
        if not item.get('url'):
            return
        live = item.get('mode') == 'live'
        descTab = []
        if live:
            descTab.append(_('Live'))
        elif item.get('duration'):
            descTab.append(str(timedelta(seconds=int(item['duration']))))
        if item.get('views_total') is not None and not live:
            descTab.append(_('%s views') % item['views_total'])
        date = time.strftime('%Y-%m-%d', time.gmtime(int(item['created_time']))) if item.get('created_time') else ''
        if date and not live:
            descTab.append(date)
        desc = ' | '.join(descTab)
        if item.get('owner.screenname'):
            desc += '[/br]' + _('Channel: %s') % item['owner.screenname']
        title = item.get('title') or item.get('id', '')
        params = stripPagerKeys(dict(cItem), ('cat_id', 'sort', 'search', 'live'))
        params.update({'good_for_fav': True, 'title': title if live else normalizeMediathekTitle(title, date=date), 'raw_title': title, 'url': item['url'], 'xid': item.get('id', ''),
                       'icon': item.get('thumbnail_240_url', ''), 'desc': desc, 'date': date, 'is_live': live,
                       'owner_xid': item.get('owner.id', ''), 'owner_name': item.get('owner.screenname', '')})
        self.addVideo(params)

    def listVideos(self, cItem):
        printDBG("Dailymotion.listVideos [%s]" % cItem)
        page = self._page(cItem)
        args = ['thumbnail_ratio=widescreen', 'limit=%d' % PER_PAGE, 'fields=%s' % urllib_quote(VIDEO_FIELDS)]
        category = cItem.get('category')
        if category == 'list_playlist':
            fun = 'playlist/%s/videos' % cItem['f_xid']
        elif category == 'list_channel':
            fun = 'user/%s/videos' % cItem['f_xid']
            args.append('sort=recent')
        else:
            fun = 'videos'
            if cItem.get('live'):
                args.extend(['flags=live_onair', 'sort=visited'])
            if cItem.get('cat_id'):
                args.append('channel=%s' % cItem['cat_id'])
            if cItem.get('sort'):
                args.append('sort=%s' % cItem['sort'])
            if cItem.get('search'):
                args.append('search=%s' % urllib_quote(cItem['search']))
        data = self.getApi(fun, page, args)
        if category == 'list_channel' and page == 1:
            self._addChannelPlaylists(cItem)
        for item in data.get('list') or []:
            self._addVideoItem(cItem, item)
        self._addPaging(cItem, data, page)

    def _addChannelPlaylists(self, cItem):
        data = self.getApi('user/%s' % cItem['f_xid'], None, ['fields=playlists_total'])
        if data.get('playlists_total'):
            params = stripPagerKeys(dict(cItem))
            params.update({'good_for_fav': True, 'category': 'list_playlists', 'title': '%s (%s)' % (_('Playlists'), data['playlists_total']), 'desc': ''})
            self.addDir(params)

    def listPlaylists(self, cItem):
        printDBG("Dailymotion.listPlaylists [%s]" % cItem)
        page = self._page(cItem)
        args = ['limit=%d' % PER_PAGE, 'fields=%s' % urllib_quote('id,name,description,thumbnail_240_url,videos_total')]
        data = self.getApi('user/%s/playlists' % cItem['f_xid'], page, args)
        for item in data.get('list') or []:
            if not item.get('id') or not item.get('videos_total'):
                continue
            params = stripPagerKeys(dict(cItem))
            params.update({'good_for_fav': True, 'category': 'list_playlist', 'title': '%s (%s)' % (item.get('name') or item['id'], item['videos_total']),
                           'f_xid': item['id'], 'owner_xid': cItem['f_xid'], 'icon': item.get('thumbnail_240_url', ''), 'desc': self.cleanHtmlStr(item.get('description') or '')})
            self.addDir(params)
        self._addPaging(cItem, data, page)

    def listChannels(self, cItem):
        printDBG("Dailymotion.listChannels [%s]" % cItem)
        page = self._page(cItem)
        args = ['search=%s' % urllib_quote(cItem['f_query']), 'limit=%d' % PER_PAGE, 'fields=%s' % urllib_quote('id,screenname,description,avatar_240_url,videos_total')]
        data = self.getApi('users', page, args)
        for item in data.get('list') or []:
            if not item.get('videos_total'):
                continue
            params = {'good_for_fav': True, 'name': 'category', 'category': 'list_channel', 'title': '%s (%s)' % (item.get('screenname', ''), item['videos_total']),
                      'f_xid': item['id'], 'icon': item.get('avatar_240_url', ''), 'desc': self.cleanHtmlStr(item.get('description') or '')}
            self.addDir(params)
        self._addPaging(cItem, data, page)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Dailymotion.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        currItem = dict(cItem)
        if searchType == 'videos':
            currItem.update({'category': 'list_videos', 'search': searchPattern, 'sort': 'relevance'})
            self.listVideos(currItem)
        else:
            # "channels" - also what a "playlists" search from the search history lands on now
            currItem.update({'category': 'list_channels', 'f_query': searchPattern})
            self.listChannels(currItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Dailymotion.getLinksForVideo [%s]" % cItem)
        url = cItem.get('url', '')
        if not self.cm.isValidUrl(url):
            return []
        # resolved by the dailymotion parser of urlparser (qualities) when the link is played
        urlTab = [{'name': 'Dailymotion', 'url': url, 'need_resolve': 1}]
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, url):
        printDBG("Dailymotion.getVideoLinks [%s]" % url)
        urlTab = self.up.getVideoLinkExt(url)
        if not urlTab:
            SetIPTVPlayerLastHostError(_("Content not available"))
        return decorateResolvedLinkItems(urlTab, sidecarFromUrlMeta(url, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Dailymotion.getArticleContent [%s]" % cItem)
        title = cItem.get('title', '')
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        other = {}
        if cItem.get('type') == 'video' and cItem.get('xid'):
            data = self.getApi('video/%s' % cItem['xid'], None, ['fields=%s' % urllib_quote('title,description,duration,views_total,created_time,owner.screenname,channel.name,tags,thumbnail_480_url,language,mode')])
            if data.get('title'):
                title = data['title']
                text = self.cleanHtmlStr((data.get('description') or '').replace('<br />', '[/br]').replace('<br>', '[/br]')) or text
                icon = data.get('thumbnail_480_url') or icon
                if data.get('mode') == 'live':
                    other['status'] = _('Live')
                elif data.get('duration'):
                    other['duration'] = str(timedelta(seconds=int(data['duration'])))
                if data.get('views_total') is not None:
                    other['views'] = str(data['views_total'])
                if data.get('created_time'):
                    other['released'] = time.strftime('%Y-%m-%d %H:%M', time.gmtime(int(data['created_time'])))
                if data.get('owner.screenname'):
                    other['station'] = data['owner.screenname']
                if data.get('channel.name'):
                    other['category'] = data['channel.name']
                if data.get('language'):
                    other['language'] = data['language']
        elif cItem.get('category') in ('list_channel', 'list_playlists') and cItem.get('f_xid'):
            data = self.getApi('user/%s' % cItem['f_xid'], None, ['fields=%s' % urllib_quote('screenname,description,avatar_720_url,videos_total,playlists_total,country')])
            if data.get('screenname'):
                title = data['screenname']
                counts = '%s: %s | %s: %s' % (_('Videos'), data.get('videos_total') or 0, _('Playlists'), data.get('playlists_total') or 0)
                text = '[/br]'.join([x for x in (counts, self.cleanHtmlStr(data.get('description') or '')) if x])
                icon = data.get('avatar_720_url') or icon
                if data.get('country'):
                    other['country'] = data['country']
        elif cItem.get('category') == 'list_playlist' and cItem.get('f_xid'):
            data = self.getApi('playlist/%s' % cItem['f_xid'], None, ['fields=%s' % urllib_quote('name,description,videos_total,owner.screenname,thumbnail_480_url')])
            if data.get('name'):
                title = data['name']
                counts = '%s: %s' % (_('Videos'), data.get('videos_total') or 0)
                text = '[/br]'.join([x for x in (counts, self.cleanHtmlStr(data.get('description') or '')) if x])
                icon = data.get('thumbnail_480_url') or icon
                if data.get('owner.screenname'):
                    other['station'] = data['owner.screenname']
        return [{'title': self.cleanHtmlStr(title), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []

        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'categories':
            self.listCategories(self.currItem)
        elif category == 'sort':
            self.listSort(self.currItem)
        # "category" = a category opened from an older favourite
        elif category in ('list_videos', 'category', 'list_channel', 'list_playlist'):
            self.listVideos(self.currItem)
        elif category == 'list_playlists':
            self.listPlaylists(self.currItem)
        elif category == 'list_channels':
            self.listChannels(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Dailymotion(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('dailymotion')

    def withArticleContent(self, cItem):
        return (cItem.get('type') == 'video' and bool(cItem.get('xid'))) or (cItem.get('category') in ('list_channel', 'list_playlists', 'list_playlist') and bool(cItem.get('f_xid')))

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Videos"), "videos"))
        searchTypesOptions.append((_("Channels"), "channels"))
        return searchTypesOptions
