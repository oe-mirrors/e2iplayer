# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# Radiostacja.pl: Polish radio stations (Radio ZET group, local stations), music channels by mood and the
#   RMF ON station list, search by station name
# 10.10.2026 - host standard: station rows are audio rows with INFO and sidecar, mood / RMF ON folders reopen
#   from favourites, RMF ON streams from the station list (AAC + MP3), long lists paged, search by station
#   name, English labels, current user agent; removed the dead weszlo.fm row (domain now a casino page)
#   and the empty "Sety Muzyczne" list
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'http://radiostacja.pl/'


class RadiostacjaPl(CBaseHostClass):

    LIVE_URL = 'http://www.radiostacja.pl/data/mobile/live.json'
    CHANNELS_URL = 'http://www.radiostacja.pl/data/mobile/muzyczne_android.json'
    RMF_URL = 'https://www.rmfon.pl/json/app.txt'
    RMF_ICON = 'https://www.rmfon.pl/img/z/p1-512.jpg'
    # stable identity of a station row
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'rmf_id', 'group', 'genre')
    PAGE_SIZE = 100

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'radiostacja.pl', 'cookie': 'radiostacja.pl.cookie'})
        self.MAIN_URL = 'http://www.radiostacja.pl/'
        self.DEFAULT_ICON_URL = 'http://is3.mzstatic.com/image/thumb/Purple122/v4/82/c4/6f/82c46f38-3532-e414-530e-33e5d0be2614/source/392x696bb.jpg'
        self.HTTP_HEADER = {'User-Agent': self.cm.getDefaultUserAgent(), 'Accept': 'application/json, text/html, */*', 'Accept-Encoding': 'gzip, deflate',
                            'Referer': self.getMainUrl()}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cache = {}

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _getJson(self, url):
        # the station lists change rarely - one download per session
        if url not in self.cache:
            sts, data = self.getPage(url)
            if not sts or not data.strip():
                return {}
            try:
                data = ensure_str_deep(json_loads(data))
                if isinstance(data, dict):
                    self.cache[url] = data
            except Exception:
                printExc()
        return self.cache.get(url, {})

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'audio':
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("RadiostacjaPl.listMainMenu")
        MAIN_CAT_TAB = [{'category': 'live', 'title': _('Radio stations')},
                        {'category': 'channels', 'title': 'Music channels'}] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listLive(self, cItem):
        printDBG("RadiostacjaPl.listLive")
        CAT_TAB = [{'category': 'list_items', 'title': 'Radio ZET', 'f_key': 'eurozet', 'good_for_fav': True},
                   {'category': 'list_items', 'title': 'Local radio stations', 'f_key': 'lokalne', 'good_for_fav': True},
                   {'category': 'list_rmf', 'title': 'RMF ON', 'icon': self.RMF_ICON, 'good_for_fav': True}]
        self.listsTab(CAT_TAB, {'name': 'category'})

    def listChannels(self, cItem):
        printDBG("RadiostacjaPl.listChannels")
        self.addDir({'name': 'category', 'category': 'list_channel_items', 'title': _('All'), 'f_key': 'muzyczne', 'good_for_fav': True})
        for genre in self._getJson(self.CHANNELS_URL).get('kategorie', []):
            try:
                title = self.cleanHtmlStr(genre.get('name', ''))
                if title and genre.get('channels'):
                    self.addDir({'name': 'category', 'category': 'list_channel_items', 'title': title, 'icon': genre.get('logo', ''),
                                 'f_genre': str(genre.get('id', '')), 'good_for_fav': True})
            except Exception:
                printExc()

    def _stationParams(self, item, group, genre=''):
        title = self.cleanHtmlStr(item.get('name', ''))
        url = (item.get('stream') or '').strip()
        if not title or not self.cm.isValidUrl(url):
            return None
        params = {'name': 'category', 'good_for_fav': True, 'title': title, 'url': url, 'icon': item.get('image', ''), 'group': group}
        if genre:
            params['genre'] = genre
        return params

    def _addRows(self, cItem, rows):
        # local paging for long lists
        try:
            page = max(1, int(cItem.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        seen = set()
        rows = [params for params in rows if not (params['url'] in seen or seen.add(params['url']))]
        lastPage = (len(rows) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        for params in rows[(page - 1) * self.PAGE_SIZE:page * self.PAGE_SIZE]:
            self.addAudio(params)
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage)

    def listItems(self, cItem):
        printDBG("RadiostacjaPl.listItems [%s]" % cItem.get('f_key', ''))
        if cItem.get('f_key') == 'muzyczne':
            # "Wszystkie" music channels folder saved as favourite by the old version
            return self.listChannelItems({'name': 'category', 'category': 'list_channel_items', 'page': cItem.get('page', 1)})
        group = {'eurozet': 'Radio ZET', 'lokalne': 'Local radio stations'}.get(cItem.get('f_key', ''), '')
        rows = []
        for item in self._getJson(self.LIVE_URL).get(cItem.get('f_key', ''), []):
            params = self._stationParams(item, group)
            if params:
                rows.append(params)
        self._addRows(cItem, rows)

    def listChannelItems(self, cItem):
        printDBG("RadiostacjaPl.listChannelItems [%s]" % cItem.get('f_genre', ''))
        data = self._getJson(self.CHANNELS_URL)
        rows = []
        if cItem.get('f_genre'):
            for genre in data.get('kategorie', []):
                if str(genre.get('id', '')) != cItem['f_genre']:
                    continue
                genreName = self.cleanHtmlStr(genre.get('name', ''))
                for item in genre.get('channels', []):
                    params = self._stationParams(item, 'Music channels', genreName)
                    if params:
                        rows.append(params)
                break
        else:
            for item in data.get('muzyczne', []):
                params = self._stationParams(item, 'Music channels')
                if params:
                    rows.append(params)
        self._addRows(cItem, rows)

    def listRMF(self, cItem):
        printDBG("RadiostacjaPl.listRMF")
        self.addDir({'name': 'category', 'category': 'list_rmf_items', 'title': _('All'), 'icon': self.RMF_ICON, 'good_for_fav': True})
        for item in self._getJson(self.RMF_URL).get('categories', []):
            try:
                title = self.cleanHtmlStr(item.get('name', ''))
                if title and item.get('ids'):
                    self.addDir({'name': 'category', 'category': 'list_rmf_items', 'title': title, 'icon': self.RMF_ICON,
                                 'f_id': str(item.get('id', '')), 'good_for_fav': True})
            except Exception:
                printExc()

    def _rmfStationParams(self, item):
        title = self.cleanHtmlStr(item.get('name', ''))
        if not title or not item.get('id'):
            return None
        params = {'name': 'category', 'good_for_fav': True, 'title': title, 'url': 'http://www.rmfon.pl/play,%s' % item['id'],
                  'rmf_id': str(item['id']), 'icon': item.get('defaultart', '') or self.RMF_ICON, 'group': 'RMF ON'}
        genre = ', '.join([tag.strip() for tag in item.get('search', '').split(',')[1:] if tag.strip()])
        if genre:
            params['genre'] = genre
        return params

    def listRMFItems(self, cItem):
        printDBG("RadiostacjaPl.listRMFItems [%s]" % cItem.get('f_id', ''))
        data = self._getJson(self.RMF_URL)
        ids = None
        if cItem.get('f_id'):
            for item in data.get('categories', []):
                if str(item.get('id', '')) == cItem['f_id']:
                    ids = item.get('ids', [])
                    break
            if ids is None:
                return
        rows = []
        for item in data.get('stations', []):
            if ids is not None and item.get('id') not in ids:
                continue
            params = self._rmfStationParams(item)
            if params:
                rows.append(params)
        self._addRows(cItem, rows)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("RadiostacjaPl.listSearchResult [%s]" % searchPattern)
        pattern = (searchPattern or '').strip().lower()
        if not pattern:
            return
        rows = []
        seen = set()

        def _add(params):
            if params and params['url'] not in seen and pattern in params['title'].lower():
                seen.add(params['url'])
                rows.append(params)

        live = self._getJson(self.LIVE_URL)
        for key, group in (('eurozet', 'Radio ZET'), ('lokalne', 'Local radio stations')):
            for item in live.get(key, []):
                _add(self._stationParams(item, group))
        channels = self._getJson(self.CHANNELS_URL)
        for item in channels.get('muzyczne', []):
            _add(self._stationParams(item, 'Music channels'))
        for genre in channels.get('kategorie', []):
            for item in genre.get('channels', []):
                _add(self._stationParams(item, 'Music channels', self.cleanHtmlStr(genre.get('name', ''))))
        for item in self._getJson(self.RMF_URL).get('stations', []):
            _add(self._rmfStationParams(item))
        self._addRows(cItem, rows)
        if not self.currList:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))

    ###################################################
    # links / info
    ###################################################
    def _rmfLinks(self, stationId):
        linksTab = []
        for item in self._getJson(self.RMF_URL).get('stations', []):
            if str(item.get('id', '')) != stationId:
                continue
            for key, name in (('aac', 'AAC'), ('mp3', 'MP3')):
                if self.cm.isValidUrl(item.get(key, '')):
                    linksTab.append({'name': name, 'url': item[key]})
            break
        if not linksTab:
            # station missing in the app list - the old per-station playlist
            sts, data = self.getPage('https://www.rmfon.pl/stacje/flash_aac_%s.xml.txt' % stationId)
            if sts:
                for playlistItem in self.cm.ph.getAllItemsBeetwenMarkers(data, '<playlist', '</playlist'):
                    name = 'MP3' if 'playlistMp3' in playlistItem else 'AAC'
                    for url in self.cm.ph.getAllItemsBeetwenNodes(playlistItem, ('<item', '>'), ('</item', '>'), False):
                        url = url.strip()
                        if self.cm.isValidUrl(url):
                            linksTab.append({'name': name, 'url': url})
                            break
        return linksTab

    def getLinksForVideo(self, cItem):
        printDBG("RadiostacjaPl.getLinksForVideo [%s]" % cItem.get('url', ''))
        url = cItem.get('url', '')
        if 'rmfon.pl/play,' in url:
            linksTab = self._rmfLinks(cItem.get('rmf_id', '') or url.split(',')[-1])
        elif self.cm.isValidUrl(url) and 'weszlo.fm' not in url:
            linksTab = [{'name': cItem.get('group', '') or 'stream', 'url': url}]
        else:
            linksTab = []
        if not linksTab:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        for item in linksTab:
            item['url'] = strwithmeta(item['url'], {'User-Agent': self.HTTP_HEADER['User-Agent'], 'iptv_livestream': True})
            item['need_resolve'] = 0
        return applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getArticleContent(self, cItem):
        printDBG("RadiostacjaPl.getArticleContent [%s]" % cItem.get('url', ''))
        otherInfo = {}
        if cItem.get('genre'):
            otherInfo['genre'] = cItem['genre']
        if cItem.get('group'):
            otherInfo['station'] = cItem['group']
        icon = cItem.get('icon', '') or self.DEFAULT_ICON_URL
        title = cItem.get('title', '')
        group = cItem.get('group', '')
        text = ['%s - %s' % (title, group) if group and group != title else title]
        if cItem.get('genre'):
            text.append(_('Genre: %s') % cItem['genre'])
        url = cItem.get('url', '')
        if 'rmfon.pl/play,' in url:
            text.append('Stream: AAC / MP3')
        elif self.cm.isValidUrl(url):
            text.append('Stream: %s' % self.cm.getBaseUrl(url, True))
        text = '[/br]'.join(text)
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': icon}], 'other_info': otherInfo}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'live':
            self.listLive(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'channels':
            self.listChannels(self.currItem)
        elif category == 'list_genres':
            # "Nastroje" folder saved as favourite by the old version
            self.listChannels(self.currItem)
        elif category == 'list_channel_items':
            self.listChannelItems(self.currItem)
        elif category == 'list_rmf':
            self.listRMF(self.currItem)
        elif category == 'list_rmf_items':
            self.listRMFItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            searchPattern = self.currItem.get('search_pattern', searchPattern)
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page', 'search_pattern': searchPattern})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, RadiostacjaPl(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('type', '') == 'audio'
