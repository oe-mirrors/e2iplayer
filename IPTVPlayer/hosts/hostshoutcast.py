# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# SHOUTcast radio directory (directory.shoutcast.com): top stations, genres -> sub genres -> stations,
#   search by station name, artist or song that is playing now
# 08.10.2026 - host standard: top stations, genre folders that reopen from favourites, artist / song search,
#   own tunein playlist parsing (no urlparser), INFO with the station data, sidecar, current user agent,
#   station lists paged (100 a page), streams marked as live
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://shoutcast.com/'


class ShoutcastCom(CBaseHostClass):

    # stable identity of a station row (listeners / current track in desc change)
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'station_id', 'genre', 'bitrate', 'format', 'website', 'icon')
    SEARCH_TYPES = [(_('Radio stations'), 'station'), (_('Artist'), 'artist'), (_('Titles'), 'song')]
    PAGE_SIZE = 100

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'shoutcast.com', 'cookie': 'shoutcast.com.cookie'})
        self.MAIN_URL = 'https://directory.shoutcast.com/'
        self.DEFAULT_ICON_URL = 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Shoutcast_2018_logo.svg/1280px-Shoutcast_2018_logo.svg.png'
        self.HTTP_HEADER = {'User-Agent': self.cm.getDefaultUserAgent(), 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate',
                            'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()[:-1]}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, */*'})
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _postJson(self, path, post_data):
        params = dict(self.defaultParams)
        params['header'] = self.AJAX_HEADER
        sts, data = self.getPage(self.getFullUrl(path), params, post_data)
        if not sts:
            return None
        try:
            data = ensure_str_deep(json_loads(data))
            return data if isinstance(data, list) else None
        except Exception:
            printExc()
        return None

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
        printDBG("ShoutcastCom.listMainMenu")
        MAIN_CAT_TAB = [{'category': 'list_top', 'title': _('Top stations'), 'url': self.getFullUrl('/Home/Top'), 'good_for_fav': True},
                        {'category': 'genres', 'title': _('Genres'), 'url': self.getMainUrl()}] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def _genreTree(self):
        # [(main genre title, url, [(sub genre title, url), ...]), ...] from the genre menu of the start page
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return []
        tree = []
        for genreItem in self.cm.ph.getAllItemsBeetwenNodes(data, ('<li', '>', 'main-genre'), ('</ul', '>')):
            tmp = self.cm.ph.getDataBeetwenMarkers(genreItem, '<a', '</a>')[1]
            title = self.cleanHtmlStr(tmp)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, r'''\shref=['"]([^'^"]+?)['"]''')[0])
            subs = []
            for item in self.cm.ph.getAllItemsBeetwenMarkers(genreItem.split('<ul', 1)[-1] if '<ul' in genreItem else '', '<a', '</a>'):
                subUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'''\shref=['"]([^'^"]+?)['"]''')[0])
                subTitle = self.cleanHtmlStr(item)
                if subTitle and subUrl:
                    subs.append((subTitle, subUrl))
            if title and url:
                tree.append((title, url, subs))
        return tree

    def listGenres(self, cItem):
        printDBG("ShoutcastCom.listGenres")
        for title, url, subs in self._genreTree():
            category = 'list_sub_genres' if subs else 'list_items'
            self.addDir({'name': 'category', 'category': category, 'good_for_fav': True, 'title': title, 'url': url, 'genre': title})

    def listSubGenres(self, cItem):
        printDBG("ShoutcastCom.listSubGenres [%s]" % cItem.get('url', ''))
        for title, url, subs in self._genreTree():
            if url != cItem.get('url'):
                continue
            self.addDir({'name': 'category', 'category': 'list_items', 'good_for_fav': True, 'title': _('All'), 'url': url, 'genre': title})
            for subTitle, subUrl in subs:
                self.addDir({'name': 'category', 'category': 'list_items', 'good_for_fav': True, 'title': subTitle, 'url': subUrl, 'genre': subTitle})
            break

    def _addStations(self, cItem, stations):
        # the site answers with the whole list (up to 200 stations) - paged here
        stations = stations or []
        try:
            page = max(1, int(cItem.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        lastPage = (len(stations) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        for item in stations[(page - 1) * self.PAGE_SIZE:page * self.PAGE_SIZE]:
            try:
                stationId = str(item.get('ID', ''))
                title = self.cleanHtmlStr(item.get('Name', ''))
                if not stationId or not title:
                    continue
                fmt = 'AAC' if item.get('IsAACEnabled') or 'aac' in str(item.get('Format', '')) else 'MP3'
                bitrate = '%s kbps' % item['Bitrate'] if item.get('Bitrate') else ''
                genre = self.cleanHtmlStr(item.get('Genre', ''))
                track = self.cleanHtmlStr(item.get('CurrentTrack', ''))
                desc = []
                if genre:
                    desc.append(_('Genre: %s') % genre)
                desc.append(_('Listeners: %s') % item.get('Listeners', 0))
                if bitrate:
                    desc.append(_('Bitrate: %s') % bitrate)
                desc.append(_('Type: %s') % fmt)
                desc = ' | '.join(desc)
                if track:
                    desc += '[/br]' + _('Now playing: %s') % track
                self.addAudio({'good_for_fav': True, 'station_id': stationId, 'title': title, 'url': self.getFullUrl('?station_id=' + stationId),
                               'genre': genre, 'bitrate': bitrate, 'format': fmt, 'website': item.get('IceUrl') or '', 'desc': desc})
            except Exception:
                printExc()
        if lastPage > 1:
            # the url of a list names the whole list ("Jump" template without a page in it)
            addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem.get('url', ''))

    def listTop(self, cItem):
        printDBG("ShoutcastCom.listTop")
        self._addStations(cItem, self._postJson('/Home/Top', {}))

    def listItems(self, cItem):
        printDBG("ShoutcastCom.listItems [%s]" % cItem.get('url', ''))
        genre = cItem.get('genre', '')
        if not genre:
            genre = urllib_unquote(self.cm.ph.getSearchGroups(cItem.get('url', ''), r'[?&]name=([^&]+)')[0])
        if genre:
            self._addStations(cItem, self._postJson('/Home/BrowseByGenre', {'genrename': genre}))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ShoutcastCom.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        pattern = (searchPattern or '').strip()
        if not pattern:
            return
        if searchType in ('artist', 'song'):
            post = {'genre': '', 'station': '', 'type': '', 'artist': '', 'song': ''}
            post[searchType] = pattern
            stations = self._postJson('/Search/UpdateAdvancedSearch', post)
        else:
            stations = self._postJson('/Search/UpdateSearch', {'query': pattern})
        self._addStations(cItem, stations)
        if not self.currList:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))

    ###################################################
    # links / info
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("ShoutcastCom.getLinksForVideo [%s]" % cItem)
        stationId = cItem.get('station_id', '') or self.cm.ph.getSearchGroups(cItem.get('url', ''), r'station_id=(\d+)')[0]
        if not stationId:
            return []
        sts, data = self.getPage('https://yp.shoutcast.com/sbin/tunein-station.m3u?id=%s' % urllib_quote(stationId))
        if not sts:
            return []
        quality = ('%s %s' % (cItem.get('format', ''), cItem.get('bitrate', ''))).strip() or cItem.get('title', '')
        linksTab = []
        for line in data.splitlines():
            line = line.strip()
            if line.startswith('#') or not self.cm.isValidUrl(line):
                continue
            # SHOUTcast DNAS v2 answers "http://ip:port" and "/stream/N" with a redirect to its HTML status
            # page - the stream itself is "http://ip:port/;" and "/stream/N/"
            m = re.match(r'^(https?://[^/?#]+)(/?|/stream/\d+)$', line)
            if m:
                line = m.group(1) + (m.group(2) + '/' if m.group(2).startswith('/stream') else '/;')
            linksTab.append({'name': '%s #%d' % (quality, len(linksTab) + 1), 'url': strwithmeta(line, {'User-Agent': self.HTTP_HEADER['User-Agent'], 'iptv_livestream': True}),
                             'need_resolve': 0})
        if not linksTab:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        return applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getArticleContent(self, cItem):
        printDBG("ShoutcastCom.getArticleContent [%s]" % cItem.get('url', ''))
        otherInfo = {}
        if cItem.get('genre'):
            otherInfo['genre'] = cItem['genre']
        quality = ('%s %s' % (cItem.get('bitrate', ''), cItem.get('format', ''))).strip()
        if quality:
            otherInfo['quality'] = quality
        if cItem.get('website'):
            otherInfo['source'] = cItem['website']
        icon = cItem.get('icon', '') or self.DEFAULT_ICON_URL
        # a favourite keeps no desc (listeners / current track change)
        return [{'title': cItem.get('title', ''), 'text': cItem.get('desc', '') or cItem.get('title', ''),'images': [{'title': '', 'url': icon}], 'other_info': otherInfo}]

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
        elif category == 'list_top':
            self.listTop(self.currItem)
        elif category == 'genres':
            self.listGenres(self.currItem)
        elif category == 'list_sub_genres':
            self.listSubGenres(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            # a pager row of the results carries the search it belongs to
            searchPattern = self.currItem.get('search_pattern', searchPattern)
            searchType = self.currItem.get('search_type', searchType)
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page',
                          'search_pattern': searchPattern, 'search_type': searchType})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ShoutcastCom(), True, [])

    def getSearchTypes(self):
        return self.host.SEARCH_TYPES

    def withArticleContent(self, cItem):
        return cItem.get('type', '') == 'audio'
