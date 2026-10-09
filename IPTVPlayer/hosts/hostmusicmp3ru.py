# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# musicmp3.ru - artists, top / new albums by genre -> album -> tracks (128 kbit/s MP3 previews of the site's player),
#   search for songs, albums and artists
# 08.10.2026 - host standard: the player key ("boo" of the site's scripts.js) computed in Python (no JS engine,
#   no extra request for scripts.js), First page / Jump / Next page, track rows keyed on their own page url
#   (watched flag album -> track, downloaded marker, favourites that reopen without the album page),
#   "Artist - Title" naming, INFO for tracks and albums, sidecar, current user agent, no JSON errors in the log
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
###################################################

PLAY_BASE = 'https://listen.musicmp3.ru'
PAGE_SIZE = {'artists': 80, 'albums': 40}  # rows of one "show more" page of the site
LOCAL_PAGE_SIZE = 100


def GetConfigList():
    return []


def gettytul():
    return 'https://musicmp3.ru/'


def _int32(x):
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


def playerKey(text):
    # port of "boo" in https://musicmp3.ru/js/scripts.js (JavaScript int32 / double arithmetic)
    a, c, b = 1234554321, 7, 305419896
    for ch in text:
        f = ord(ch) & 255
        a = _int32(a) ^ _int32(((a & 63) + c) * f + _int32(_int32(a) << 8))
        b = b + (_int32(_int32(b) << 8) ^ a)
        c += f
    ret = ''
    for value in (_int32(a) & 0x7FFFFFFF, _int32(b) & 0x7FFFFFFF):
        h = '%x' % value
        tmp = '0000' + h
        ret += tmp[len(h) - 4:] if len(h) >= 4 else tmp
    return ret


class MusicMp3Ru(GenericFolderWatchedScraperMixin, CBaseHostClass):

    TRACK_FIELDS = ('name', 'category', 'type', 'url', 'title', 'raw_title', 'icon', 'desc', 'artist', 'album', 'track', 'year',
                    'duration', 'rel', 'track_no', 'play_base')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'musicmp3.ru', 'cookie': 'musicmp3.ru.cookie'})
        self.MAIN_URL = 'https://musicmp3.ru/'
        self.DEFAULT_ICON_URL = 'https://musicmp3.ru/i/logo.png'
        self.HTTP_HEADER = {'User-Agent': self.cm.getDefaultUserAgent(), 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl()}
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('musicmp3ru')
        self.wfInitFolderCache()

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            url = cItem.get('url', '')
            if cItem.get('type') == 'audio' and '#' in url:
                return 'track:%s' % url
            if cItem.get('type') == 'category' and cItem.get('category') == 'list_songs' and url and '/search.html' not in url:
                return 'folder:%s' % url
        except Exception:
            printExc()
        return ''

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'audio':
                return json_dumps(dict((key, cItem[key]) for key in self.TRACK_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self.cm.iriToUri(baseUrl), addParams, post_data)

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("MusicMp3Ru.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'menu_main'), ('</ul', '>'))[1]
            for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>'):
                url = self.cm.ph.getSearchGroups(item, r'''\shref=['"]([^'^"]+?)['"]''')[0]
                fType = 'artists' if 'artist' in url else 'albums'
                title = self.cleanHtmlStr(item)
                if url and title:
                    self.addDir({'name': 'category', 'category': 'sub_menu', 'good_for_fav': True, 'url': self.getFullUrl(url), 'title': title, 'f_type': fType})
        self.listsTab(self.searchItems(), cItem)

    def listSubMenu(self, cItem):
        # /artists.html -> genres (/artists/rock.html) -> sub genres (/artists/rock/art-rock.html), each with "--All--"
        printDBG("MusicMp3Ru.listSubMenu [%s]" % cItem.get('url', ''))
        fType = cItem.get('f_type', 'albums')
        url = cItem['url']
        listCategory = 'list_%s' % fType
        self.addDir({'name': 'category', 'category': listCategory, 'good_for_fav': True, 'title': _('--All--'), 'url': url, 'f_type': fType})
        sts, data = self.getPage(url)
        if not sts:
            return
        path = re.sub(r'^https?://[^/]+', '', url)
        prefix = path[:-5] + '/' if path.endswith('.html') else path
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'menu_sub'), ('</ul', '>'))[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>'):
            href = self.cm.ph.getSearchGroups(item, r'''\shref=['"]([^'^"]+?)['"]''')[0]
            title = self.cleanHtmlStr(item)
            if not href.startswith(prefix) or not title:
                continue
            category = 'sub_menu' if href.count('/') <= 2 else listCategory
            self.addDir({'name': 'category', 'category': category, 'good_for_fav': True, 'title': title, 'url': self.getFullUrl(href), 'f_type': fType})

    ###################################################
    # artists / albums (pages of the site's "show more")
    ###################################################
    def _getListPage(self, cItem, fType):
        # -> (data, page, pageUrlTpl): page 1 is the html page, page N the ajax url of "show more" with &page=N
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return '', page, ''
        tpl = cItem.get('page_tpl', '')
        if not tpl:
            tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'show_more'), ('</div', '>'))[1]
            ajax = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tmp, r'''\sdata\-infiniteAjaxScroll=['"]([^'"]+?)['"]''')[0])
            query = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tmp, r'''\sdata\-query=['"]([^'"]+?)['"]''')[0])
            if ajax:
                try:
                    ajaxUrl = json_loads(ajax).get('url', '')
                    if ajaxUrl:
                        tpl = self.getFullUrl(ajaxUrl + '?' + (query + '&' if query else '') + 'page={page}')
                except Exception:
                    printExc()
            if page == 1:
                if fType == 'artists':
                    data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'small_list'), ('</ul', '>'))[1]
                else:
                    data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'content'), ('<script', '>'))[1] or data
        return data, page, tpl

    def _addPager(self, cItem, page, count, fType, tpl):
        if tpl:
            params = dict(cItem, page_tpl=tpl, desc='')
            addPagingItems(self, params, page, count >= PAGE_SIZE[fType], 0, tpl)

    def listArtists(self, cItem):
        printDBG("MusicMp3Ru.listArtists [%s]" % cItem.get('url', ''))
        data, page, tpl = self._getListPage(cItem, 'artists')
        count = 0
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>'):
            url = self.cm.ph.getSearchGroups(item, r'''\shref=['"]([^'^"]+?)['"]''')[0]
            title = self.cleanHtmlStr(item)
            if not url or not title:
                continue
            count += 1
            self.addDir({'name': 'category', 'category': 'list_albums', 'good_for_fav': True, 'url': self.getFullUrl(url), 'title': title, 'artist': title})
        self._addPager(cItem, page, count, 'artists', tpl)

    def _addAlbum(self, item, artist=''):
        url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'''\shref=['"]([^'^"]+?)['"]''')[0])
        name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'album_report__name'), ('</span', '>'), False)[1]) or \
            self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<h5', '</h5>')[1])
        if not url or not name:
            return False
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'''\ssrc=['"]([^'^"]+?)['"]''')[0])
        artist = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<a', '>', 'album_report__artist'), ('</a', '>'), False)[1]) or artist
        if not artist:
            # <img alt="Muse, Drones mp3">
            alt = re.sub(r'\s+mp3$', '', self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''\salt=['"]([^'"]+?)['"]''')[0]))
            if alt.endswith(', ' + name):
                artist = alt[:-len(', ' + name)]
        year = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'album_report__date'), ('</span', '>'), False)[1])
        genres = [self.cleanHtmlStr(x) for x in self.cm.ph.getAllItemsBeetwenMarkers(item, '<li', '</li>')]
        genres = ', '.join([x for x in genres if x])
        details = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'details_content'), ('</div', '>'), False)[1])
        title = '%s - %s' % (artist, name) if artist else name
        if year:
            title += ' (%s)' % year
        desc = ' | '.join([x for x in (artist, year, genres) if x])
        if details:
            desc += '[/br]' + details
        self.addDir({'name': 'category', 'category': 'list_songs', 'good_for_fav': True, 'url': url, 'title': title, 'album': name,
                     'artist': artist, 'year': year, 'icon': icon, 'desc': desc})
        return True

    def listAlbums(self, cItem):
        printDBG("MusicMp3Ru.listAlbums [%s]" % cItem.get('url', ''))
        data, page, tpl = self._getListPage(cItem, 'albums')
        count = 0
        for item in re.compile(r'''<div[^>]+?['"]album_report['"][^>]*?>''').split(data)[1:]:
            if self._addAlbum(item, cItem.get('artist', '') if '/artist_' in cItem.get('url', '') else ''):
                count += 1
        self._addPager(cItem, page, count, 'albums', tpl)

    ###################################################
    # tracks
    ###################################################
    @staticmethod
    def _isoDuration(value):
        m = re.match(r'PT(\d+)H(\d+)M(\d+)S', value or '')
        if not m:
            return ''
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return '%d:%02d:%02d' % (h, mi, s) if h else '%d:%02d' % (mi, s)

    def _addTrack(self, track, artist, album, year, url, icon, rel, trackNo, playBase, duration=''):
        rawTitle = track
        title = '%s - %s' % (artist, track) if artist and IsMediaNamingNormalized() else track
        desc = ' | '.join([x for x in (artist, '%s (%s)' % (album, year) if album and year else album, duration) if x])
        self.addAudio({'good_for_fav': True, 'title': title, 'raw_title': rawTitle, 'url': url, 'icon': icon, 'desc': desc, 'artist': artist,
                       'album': album, 'track': track, 'year': year, 'duration': duration, 'rel': rel, 'track_no': trackNo, 'play_base': playBase})

    def listSongsItems(self, cItem):
        printDBG("MusicMp3Ru.listSongsItems [%s]" % cItem.get('url', ''))
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenNodes(data, ('<table', '>', 'tracklist'), ('</table', '>'))[1]
        playBase = self.cm.ph.getSearchGroups(tmp, r'''\sdata\-url=['"]([^'^"]+?)['"]''')[0] or PLAY_BASE
        # album page: artist / album / year / cover of the page
        pageArtist = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'itemprop="byArtist"[^>]*>.*?<span itemprop="name">([^<]+)</span>', ignoreCase=True)[0])
        pageAlbum = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1[^>]+itemprop="name"[^>]*>([^<]+)</h1>')[0])
        pageYear = self.cm.ph.getSearchGroups(data, r'itemprop="dateCreated">(\d{4})<')[0]
        pageIcon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, r'<img[^>]+class="art_wrap__img"[^>]+src="([^"]+)"')[0]) or cItem.get('icon', '')
        tracks = []
        for item in self.cm.ph.getAllItemsBeetwenNodes(tmp, ('<tr', '>', 'song'), ('</tr', '>')):
            rel = self.cm.ph.getSearchGroups(item, r'''\srel=['"]([^'^"]+?)['"]''')[0]
            if not rel:
                continue
            trackId = self.cm.ph.getSearchGroups(item, r'''<tr[^>]+\sid=['"]([^'^"]+?)['"]''')[0]
            trackNo = trackId[5:]
            track = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span itemprop="name">([^<]+)</span>')[0])
            url = self.cm.ph.getSearchGroups(item, r'<meta content="([^"]+)" itemprop="url"')[0]
            artist = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<meta content="([^"]+)" itemprop="byArtist"')[0]) or pageArtist
            album = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<meta content="([^"]+)" itemprop="inAlbum"')[0]) or pageAlbum
            duration = self._isoDuration(self.cm.ph.getSearchGroups(item, r'<meta content="([^"]+)" itemprop="duration"')[0])
            if not track:
                # search result: <a class="song__link" href="album.html#3">title</a>, artist link, album link
                links = re.findall(r'<a class="song__link" href="([^"]+)">(.*?)</a>', item, re.S)
                if len(links) < 1:
                    continue
                url, track = links[0][0], self.cleanHtmlStr(links[0][1])
                if len(links) > 1:
                    artist = self.cleanHtmlStr(links[1][1])
                if len(links) > 2:
                    album = self.cleanHtmlStr(links[2][1])
            if not track:
                continue
            url = self.getFullUrl(url) if url else '%s#%s' % (cItem['url'], trackNo or rel)
            tracks.append((track, artist, album, pageYear if album == pageAlbum else '', url, pageIcon, rel, trackNo, playBase, duration))
        # the song search answers up to some hundred rows on one page -> local pages
        try:
            page = max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            page = 1
        lastPage = (len(tracks) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
        if lastPage > 1:
            tracks = tracks[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]
        for args in tracks:
            self._addTrack(*args)
        if lastPage > 1:
            addPagingItems(self, dict(cItem, desc=''), page, page < lastPage, lastPage, cItem['url'].replace('{', '%7B').replace('}', '%7D'))

    ###################################################
    # search
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MusicMp3Ru.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        pattern = (searchPattern or '').strip()
        if not pattern:
            return
        url = self.getFullUrl('/search.html?text=%s&all=%s' % (urllib_quote_plus(pattern), searchType or 'songs'))
        cItem = dict(cItem)
        cItem.update({'url': url, 'category': 'list_albums' if searchType == 'albums' else 'list_songs'})
        if searchType == 'albums':
            self.listAlbums(cItem)
        elif searchType == 'artists':
            sts, data = self.getPage(url)
            if not sts:
                return
            data = self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'content'), ('<script', '>'))[1] or data
            for item in re.compile(r'''<li[^>]+?artist_preview[^>]*?>''').split(data)[1:]:
                href = self.cm.ph.getSearchGroups(item, r'''\shref=['"]([^'^"]+?)['"]''')[0]
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a', '</a>')[1])
                if not href or not title:
                    continue
                desc = []
                for it in self.cm.ph.getAllItemsBeetwenMarkers(item, '<dl', '</dl>'):
                    header = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(it, '<dt', '</dt>')[1])
                    values = [self.cleanHtmlStr(t) for t in self.cm.ph.getAllItemsBeetwenMarkers(it, '<li', '</li>')]
                    values = [t for t in values if t]
                    if values:
                        desc.append('%s: %s' % (header, ', '.join(values)))
                self.addDir({'name': 'category', 'category': 'list_albums', 'good_for_fav': True, 'url': self.getFullUrl(href), 'title': title,
                             'artist': title, 'desc': '[/br]'.join(desc)})
        else:
            self.listSongsItems(cItem)
        if not self.currList:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))

    ###################################################
    # links / info
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("MusicMp3Ru.getLinksForVideo [%s]" % cItem.get('url', ''))
        rel = cItem.get('rel', '')
        if not rel:
            return []
        sessionId = self.cm.getCookieItem(self.COOKIE_FILE, 'SessionId')
        if not sessionId:
            self.getPage(self.getMainUrl())
            sessionId = self.cm.getCookieItem(self.COOKIE_FILE, 'SessionId')
        if not sessionId:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        # favourites of the old host version: 'id' = "track<N>", 'url' = the player's base url
        trackNo = cItem.get('track_no', '') or cItem.get('id', '')[5:]
        playBase = cItem.get('play_base', '') or (cItem.get('url', '') if '://listen.' in cItem.get('url', '') else PLAY_BASE)
        key = playerKey(trackNo + sessionId[8:])
        url = '%s/%s/%s' % (playBase, key, rel)
        meta = {'User-Agent': self.HTTP_HEADER['User-Agent'], 'Referer': self.getMainUrl(), 'Cookie': 'SessionId=%s;' % sessionId}
        return applySidecarToLinks([{'name': 'MP3 128 kbps', 'url': strwithmeta(url, meta), 'need_resolve': 0}], buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getArticleContent(self, cItem):
        printDBG("MusicMp3Ru.getArticleContent [%s]" % cItem.get('url', ''))
        otherInfo = {}
        icon = cItem.get('icon', '')
        if cItem.get('type') == 'audio':
            title = cItem.get('track', '') or cItem.get('title', '')
            text = cItem.get('desc', '')
            for key, src in (('creator', 'artist'), ('year', 'year'), ('duration', 'duration')):
                if cItem.get(src):
                    otherInfo[key] = cItem[src]
            return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]
        # album
        title = cItem.get('album', '') or cItem.get('title', '')
        text = cItem.get('desc', '').split('[/br]', 1)[-1] if '[/br]' in cItem.get('desc', '') else ''
        if cItem.get('artist'):
            otherInfo['creator'] = cItem['artist']
        if cItem.get('year'):
            otherInfo['year'] = cItem['year']
        sts, data = self.getPage(cItem.get('url', ''))
        if sts:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1[^>]+itemprop="name"[^>]*>([^<]+)</h1>')[0]) or title
            artist = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'itemprop="byArtist"[^>]*>.*?<span itemprop="name">([^<]+)</span>', ignoreCase=True)[0])
            if artist:
                otherInfo['creator'] = artist
            year = self.cm.ph.getSearchGroups(data, r'itemprop="dateCreated">(\d{4})<')[0]
            if year:
                otherInfo['year'] = year
            albumType = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<span class="page_title__additional">([^<]+?)\s+by\s')[0])
            if albumType:
                otherInfo['type'] = albumType
            genres = [self.cleanHtmlStr(x).replace(' albums', '') for x in re.findall(r'<a class="similar__link[^"]*"[^>]*>([^<]+)</a>', data)]
            if genres:
                otherInfo['genres'] = ', '.join(genres)
            tracks = len(re.findall(r'<tr class="song"', data))
            if tracks:
                otherInfo['episodes'] = str(tracks)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, r'<img[^>]+class="art_wrap__img"[^>]+src="([^"]+)"')[0]) or icon
            if not text:
                text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta content="([^"]+)" name="description"')[0])
        return [{'title': title, 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

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
        elif category == 'sub_menu':
            self.listSubMenu(self.currItem)
        elif category == 'list_artists':
            self.listArtists(self.currItem)
        elif category == 'list_albums':
            self.listAlbums(self.currItem)
        elif category == 'list_songs':
            self.listSongsItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MusicMp3Ru(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('musicmp3ru')

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("SONGS"), "songs"))
        searchTypesOptions.append((_("ALBUMS"), "albums"))
        searchTypesOptions.append((_("ARTISTS"), "artists"))
        return searchTypesOptions

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'audio' or cItem.get('category') == 'list_songs'
