# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Vimeo (vimeo.com) - Staff Picks, the categories with their curated channels and groups, the videos of
# a channel / group / user, search.
# 03.10.2026 - revival + rewrite: vimeo.com serves no browsable HTML any more. Lists come
#   from the "simple API" (vimeo.com/api/v2/channel|group|<user>/videos.json - 3 pages of 20) and from
#   api.vimeo.com (categories, channels and groups of a category, search) with the anonymous "jwt" of
#   vimeo.com/_rv/viewer. Search and the video lists of api.vimeo.com are "restricted in your region"
#   for anonymous users in the EU -> message. Streams via the urlparser (parserVIMEO: player config,
#   HLS / progressive, DRM titles -> message) + watched flag / downloaded flag / sidecar / INFO from the
#   video data / favourites.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://vimeo.com/'


class Vimeo(GenericFolderWatchedScraperMixin, CBaseHostClass):
    API_URL = 'https://api.vimeo.com'
    V2_URL = 'https://vimeo.com/api/v2/'
    V2_PAGES = 3            # the simple API stops after 3 pages of 20
    V2_PAGE_SIZE = 20
    API_PAGE_SIZE = 40
    REGION_ERROR = 5451     # "This resource is restricted in your region."
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'vid', 'v2_path', 'cat_uri', 'kind', 'title', 'icon', 'desc', 'page', 'subcategories')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'vimeo.com', 'cookie': 'vimeo.cookie'})
        self.MAIN_URL = 'https://vimeo.com/'
        self.DEFAULT_ICON_URL = 'https://f.vimeocdn.com/images_v6/logo.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Referer': self.MAIN_URL})
        self.defaultParams = {'header': self.HEADER}
        self.jwt = ''
        self.watchedHelper = IPTVWatchedHelper('vimeo')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type', '') == 'video':
                vid = str(cItem.get('vid', '') or '').strip()
                return 'video:%s' % vid if vid else ''
            if cItem.get('category') == 'list_v2' and cItem.get('v2_path'):
                return 'list:%s' % cItem['v2_path']
            return ''
        except Exception:
            printExc()
        return ''

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _getJwt(self):
        if not self.jwt:
            params = dict(self.defaultParams)
            params['header'] = dict(self.HEADER)
            params['header']['X-Requested-With'] = 'XMLHttpRequest'
            sts, data = self.getPage(self.MAIN_URL + '_rv/viewer', params)
            if sts:
                try:
                    data = json_loads(data)
                    self.jwt = data.get('jwt') or ''
                    if data.get('apiUrl'):
                        self.API_URL = 'https://%s' % data['apiUrl'].replace('https://', '').rstrip('/')
                except Exception:
                    printExc()
        return self.jwt

    def _api(self, path):
        # -> (data dict or None, error_code)
        jwt = self._getJwt()
        if not jwt:
            return None, 0
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER)
        params['header'].update({'Authorization': 'jwt ' + jwt, 'Accept': 'application/vnd.vimeo.*+json;version=3.4.2'})
        params['ignore_http_code_ranges'] = [(400, 499)]
        sts, data = self.getPage(self.API_URL + path, params)
        if not sts or not data:
            return None, 0
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return None, 0
        if not isinstance(data, dict):
            return None, 0
        if 'error_code' in data or 'error' in data:
            printDBG('Vimeo api error [%s]' % data.get('error', ''))
            code = data.get('error_code', 0)
            if code == self.REGION_ERROR:
                SetIPTVPlayerLastHostError(_('Vimeo does not offer this list to anonymous users in your region.'))
            elif data.get('error'):
                SetIPTVPlayerLastHostError('Vimeo: %s' % data['error'])
            return None, code
        return data, 0

    def _v2(self, path):
        sts, data = self.getPage(self.V2_URL + path)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    @staticmethod
    def _duration(secs):
        try:
            secs = int(secs or 0)
        except Exception:
            return ''
        if secs <= 0:
            return ''
        if secs >= 3600:
            return '%d:%02d:%02d' % (secs // 3600, (secs % 3600) // 60, secs % 60)
        return '%d:%02d' % (secs // 60, secs % 60)

    @staticmethod
    def _picture(item):
        try:
            sizes = (item.get('pictures') or {}).get('sizes') or []
            if sizes:
                return sizes[-1].get('link') or ''
        except Exception:
            printExc()
        return ''

    @staticmethod
    def _total(item, key):
        try:
            return int(((item.get('metadata') or {}).get('connections') or {}).get(key, {}).get('total', 0) or 0)
        except Exception:
            return 0

    @staticmethod
    def _v2PathFromUri(uri):
        # "/channels/927" -> "channel/927", "/groups/109" -> "group/109", "/users/123" -> "123"
        parts = [x for x in (uri or '').split('/') if x]
        if len(parts) < 2:
            return ''
        if parts[0] == 'channels':
            return 'channel/' + parts[1]
        if parts[0] == 'groups':
            return 'group/' + parts[1]
        if parts[0] == 'users':
            return parts[1]
        return ''

    def _addVideo(self, cItem, vid, title, icon='', desc='', **extra):
        if not vid or not title:
            return
        params = {'name': 'category', 'good_for_fav': True, 'vid': str(vid), 'title': self.cleanHtmlStr(title),
                  'url': self.MAIN_URL + str(vid), 'icon': icon, 'desc': desc}
        params.update(extra)
        self.addVideo(params)

    def _addV2Video(self, cItem, item):
        try:
            vid = item.get('id')
            title = item.get('title') or ''
            if not vid or not title:
                return
            head = [self.cleanHtmlStr(item.get('user_name') or ''), self._duration(item.get('duration')),
                    str(item.get('upload_date') or '')[:10]]
            head = ' | '.join([x for x in head if x])
            text = self.cleanHtmlStr(item.get('description') or '')
            desc = '[/br]'.join([x for x in (head, text) if x])
            self._addVideo(cItem, vid, title, item.get('thumbnail_large') or item.get('thumbnail_medium') or '', desc,
                           user_name=item.get('user_name') or '', upload_date=str(item.get('upload_date') or '')[:10],
                           duration=item.get('duration') or 0)
        except Exception:
            printExc()

    def _addCollection(self, cItem, item, kind):
        # a channel / group / user from api.vimeo.com -> folder listed through the simple API
        v2Path = self._v2PathFromUri(item.get('uri') or '')
        title = self.cleanHtmlStr(item.get('name') or '')
        if not v2Path or not title:
            return
        descTab = []
        videos = self._total(item, 'videos')
        if videos:
            descTab.append('%s: %d' % (_('Videos'), videos))
        users = self._total(item, 'users') or self._total(item, 'followers')
        if users:
            descTab.append('%s: %d' % (_('Followers') if kind != 'group' else _('Members'), users))
        owner = self.cleanHtmlStr((item.get('user') or {}).get('name') or '')
        if owner:
            descTab.append(owner)
        head = ' | '.join(descTab)
        text = self.cleanHtmlStr(item.get('description') or item.get('bio') or '')
        params = stripPagerKeys(dict(cItem))
        params.update({'category': 'list_v2', 'title': title, 'v2_path': v2Path, 'page': 1, 'good_for_fav': True,
                       'icon': self._picture(item), 'desc': '[/br]'.join([x for x in (head, text) if x]), 'kind': kind})
        self.addDir(params)

    ###################################################
    # lists
    ###################################################
    def listV2(self, cItem):
        page = int(cItem.get('page', 1) or 1)
        data = self._v2('%s/videos.json?page=%d' % (cItem['v2_path'], page))
        tpl = self.V2_URL + cItem['v2_path'] + '/videos.json?page={page}'
        if not isinstance(data, list):
            if page == 1:
                SetIPTVPlayerLastHostError(_('No stream available'))
            return
        for item in data:
            if isinstance(item, dict):
                self._addV2Video(cItem, item)
        full = len(data) >= self.V2_PAGE_SIZE
        # a short page is the last one; a full one may be followed by more, up to the API's limit
        addPagingItems(self, cItem, page, full and page < self.V2_PAGES, self.V2_PAGES if full else page, tpl)

    def listCategories(self, cItem):
        data, _code = self._api('/categories?per_page=50&fields=name,uri,link,pictures.sizes.link,subcategories.name,subcategories.uri,'
                                'metadata.connections.videos.total,metadata.connections.channels.total,metadata.connections.groups.total')
        for item in (data or {}).get('data') or []:
            title = self.cleanHtmlStr(item.get('name') or '')
            if not title or not item.get('uri'):
                continue
            descTab = []
            for key, label in (('channels', _('Channels')), ('groups', _('Groups')), ('videos', _('Videos'))):
                total = self._total(item, key)
                if total:
                    descTab.append('%s: %d' % (label, total))
            params = dict(cItem)
            params.update({'category': 'list_category', 'title': title, 'cat_uri': item['uri'], 'good_for_fav': True,
                           'icon': self._picture(item), 'desc': ' | '.join(descTab),
                           'subcategories': [(self.cleanHtmlStr(s.get('name') or ''), s.get('uri') or '') for s in (item.get('subcategories') or []) if isinstance(s, dict)]})
            self.addDir(params)

    def listCategory(self, cItem):
        for kind, title in (('channel', _('Channels')), ('group', _('Groups'))):
            params = dict(cItem)
            params.update({'category': 'list_collections', 'title': title, 'kind': kind, 'page': 1, 'good_for_fav': True, 'subcategories': []})
            self.addDir(params)
        for title, uri in cItem.get('subcategories') or []:
            if not title or not uri:
                continue
            params = dict(cItem)
            params.update({'category': 'list_category', 'title': title, 'cat_uri': uri, 'good_for_fav': True, 'subcategories': []})
            self.addDir(params)

    def listCollections(self, cItem):
        page = int(cItem.get('page', 1) or 1)
        kind = cItem.get('kind', 'channel')
        query = 'per_page=%d&page=%d&fields=name,uri,link,description,pictures.sizes.link,user.name,metadata.connections.videos.total,metadata.connections.users.total' % (self.API_PAGE_SIZE, page)
        if kind == 'channel':
            query += '&sort=followers&direction=desc'
        data, _code = self._api('%s/%ss?%s' % (cItem['cat_uri'], kind, query))
        if not data:
            return
        for item in data.get('data') or []:
            if isinstance(item, dict):
                self._addCollection(cItem, item, kind)
        tpl = self.API_URL + '%s/%ss?%s' % (cItem['cat_uri'], kind, query.replace('&page=%d' % page, '&page={page}', 1))
        hasNext = bool((data.get('paging') or {}).get('next') and data.get('data'))
        addPagingItems(self, cItem, page, hasNext, self._lastPage(data), tpl)

    def _lastPage(self, data):
        try:
            perPage = int(data.get('per_page') or self.API_PAGE_SIZE)
            return (int(data.get('total') or 0) + perPage - 1) // perPage
        except (TypeError, ValueError):
            return 0

    def listSearchResult(self, cItem, searchPattern, searchType):
        page = int(cItem.get('page', 1) or 1)
        searchType = searchType or 'clip'
        query = 'query=%s&filter_type=%s&page=%d&per_page=%d&c=b&fields=search_web' % (urllib_quote_plus(searchPattern), searchType, page, self.API_PAGE_SIZE)
        if searchType == 'clip':
            query += '&filter_price=free'
        data, _code = self._api('/search?' + query)
        if not data:
            return
        count = 0
        for entry in data.get('data') or []:
            try:
                itemType = entry.get('type') or searchType
                item = entry.get(itemType) or {}
                if not isinstance(item, dict):
                    continue
                if itemType == 'clip':
                    vid = str(item.get('uri') or '').rsplit('/', 1)[-1] or str(item.get('link') or '').rstrip('/').rsplit('/', 1)[-1]
                    head = [self.cleanHtmlStr((item.get('user') or {}).get('name') or ''), self._duration(item.get('duration')),
                            str(item.get('release_time') or item.get('created_time') or '')[:10]]
                    head = ' | '.join([x for x in head if x])
                    text = self.cleanHtmlStr(item.get('description') or '')
                    self._addVideo(cItem, vid, item.get('name') or '', self._picture(item), '[/br]'.join([x for x in (head, text) if x]),
                                   user_name=(item.get('user') or {}).get('name') or '', duration=item.get('duration') or 0)
                else:
                    self._addCollection(cItem, item, 'user' if itemType == 'people' else itemType)
                count += 1
            except Exception:
                printExc()
        lastPage = self._lastPage(data)
        tpl = self.API_URL + '/search?' + query.replace('&page=%d' % page, '&page={page}', 1)
        addPagingItems(self, cItem, page, bool(count) and page < lastPage, lastPage, tpl)

    ###################################################
    # links / info / favourites
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('Vimeo.getLinksForVideo [%s]' % cItem.get('vid', ''))
        url = cItem.get('url', '')
        if not self.cm.isValidUrl(url):
            return []
        urlTab = [{'name': 'vimeo.com', 'url': strwithmeta(url, {'Referer': self.MAIN_URL}), 'need_resolve': 1}]
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(cItem.get('desc', ''))))

    def getVideoLinks(self, videoUrl):
        printDBG('Vimeo.getVideoLinks [%s]' % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    def getArticleContent(self, cItem):
        printDBG('Vimeo.getArticleContent [%s]' % cItem.get('vid', ''))
        item = {}
        if cItem.get('vid'):
            data = self._v2('video/%s' % cItem['vid'])
            if isinstance(data, list) and data and isinstance(data[0], dict):
                item = data[0]
        otherInfo = {}
        creator = self.cleanHtmlStr(item.get('user_name') or cItem.get('user_name') or '')
        if creator:
            otherInfo['creator'] = creator
        dur = self._duration(item.get('duration') or cItem.get('duration'))
        if dur:
            otherInfo['duration'] = dur
        released = str(item.get('upload_date') or cItem.get('upload_date') or '')[:10]
        if released:
            otherInfo['released'] = released
        if item.get('stats_number_of_plays'):
            otherInfo['views'] = str(item['stats_number_of_plays'])
        if item.get('width') and item.get('height'):
            otherInfo['quality'] = '%sx%s' % (item['width'], item['height'])
        if item.get('tags'):
            otherInfo['categories'] = self.cleanHtmlStr(item['tags'])
        text = self.cleanHtmlStr(item.get('description') or '') or self.cleanHtmlStr(cItem.get('desc', '')).split('[/br]')[-1]
        icon = item.get('thumbnail_large') or cItem.get('icon', '')
        return [{'title': self.cleanHtmlStr(item.get('title') or '') or cItem.get('title', ''), 'text': text,
                 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('vid') or cItem.get('v2_path') or cItem.get('cat_uri'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Vimeo.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        searchPattern = self.currItem.get('search_pattern', searchPattern)
        searchType = self.currItem.get('search_type', searchType)
        printDBG('Vimeo.handleService: name[%s] category[%s]' % (name, category))
        self.currList = []

        if name is None:
            tab = [{'category': 'list_v2', 'title': 'Staff Picks', 'v2_path': 'channel/staffpicks', 'page': 1,
                    'desc': _('The best short films on the internet, handpicked by Vimeo staff')},
                   {'category': 'list_categories', 'title': _('Categories')}] + self.searchItems()
            self.listsTab(tab, {'name': 'category'})
        elif category == 'list_v2':
            self.listV2(self.currItem)
        elif category == 'list_categories':
            self.listCategories(self.currItem)
        elif category == 'list_category':
            self.listCategory(self.currItem)
        elif category == 'list_collections':
            self.listCollections(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page',
                          'search_pattern': searchPattern, 'search_type': searchType})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Vimeo(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('vimeo')

    def getSearchTypes(self):
        return [(_('Videos'), 'clip'), (_('Channels'), 'channel'), (_('Groups'), 'group'), (_('People'), 'people')]

    def withArticleContent(self, cItem):
        return bool(cItem.get('vid'))
