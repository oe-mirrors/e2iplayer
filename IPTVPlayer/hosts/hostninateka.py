# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Ninateka (ninateka.pl) - Polish films, documentaries, theatre, concerts, talks and animation
# of the Narodowy Instytut Audiowizualny / Filmoteka Narodowa.
# 03.10.2026 - revival + rewrite for the Redge (RGP) platform the site runs on now:
#   JSON API under /api (sections of the home page, categories, vods, serials -> seasons -> episodes,
#   search), streams from /api/products/<id>/videos/playlist (plain HLS from redcdn, DRM-only titles
#   such as the audiobooks -> message) + watched flag / downloaded flag / name normalisation /
#   sidecar / moviemeta INFO for feature films / favourites / paging (First / Jump / Next from totalCount).
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://ninateka.pl/'


SUB_LANGS = {'pol': 'pl', 'eng': 'en', 'ukr': 'uk', 'deu': 'de', 'ger': 'de', 'fra': 'fr', 'fre': 'fr'}


class Ninateka(GenericFolderWatchedScraperMixin, CBaseHostClass):
    API = 'https://ninateka.pl/api/'
    PAGE_SIZE = 40
    FEATURE_FILM_CAT = 85554    # "FABULA"
    VIDEO_ROOT_CAT = 1          # "video" - parent of all browsable categories
    # audio side of the site (radio "Kronika Polska", audiobooks): Widevine/PlayReady only, no plain source
    AUDIO_CATS = (153683, 153684, 85666)
    FAV_FIELDS = ('name', 'category', 'type', 'prod_id', 'prod_type', 'serial_id', 'season_id', 'url', 'title', 's_title',
                  'icon', 'desc', 'meta_type', 'meta_title', 'meta_year', 'season', 'episode')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'ninateka', 'cookie': 'ninateka.cookie'})
        self.MAIN_URL = 'https://ninateka.pl/'
        self.DEFAULT_ICON_URL = 'https://ninateka.pl/static/images/logo.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Accept': 'application/json, text/plain, */*', 'Referer': self.MAIN_URL})
        self.defaultParams = {'header': self.HEADER}
        self.watchedHelper = IPTVWatchedHelper('ninateka')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type', '') in ('video', 'audio'):
                pid = str(cItem.get('prod_id', '') or '').strip()
                return 'video:%s' % pid if pid else ''
            category = cItem.get('category', '')
            if category == 'list_serial' and cItem.get('serial_id'):
                return 'serial:%s' % cItem['serial_id']
            if category == 'list_episodes' and cItem.get('season_id'):
                return 'season:%s' % cItem['season_id']
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

    def _api(self, path, query=''):
        # NOTE: no "lang" parameter - with lang=pl the search hits a missing OpenSearch index
        url = self.API + path + '?platform=BROWSER'
        if query:
            url += '&' + query
        return url

    def _json(self, url):
        sts, data = self.getPage(url)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _img(self, item):
        try:
            images = item.get('images') or item.get('artworks') or {}
            for key in ('16x9', '4x3', '2x3', '1x1'):
                for img in (images.get(key) or []):
                    url = img.get('url') or ''
                    if url.startswith('//'):
                        url = 'https:' + url
                    if url:
                        return url
        except Exception:
            printExc()
        return ''

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

    def _desc(self, item):
        parts = []
        if item.get('year'):
            parts.append(str(item['year']))
        dur = self._duration(item.get('duration'))
        if dur:
            parts.append(dur)
        head = ' | '.join(parts)
        lead = self.cleanHtmlStr(item.get('lead') or '')
        return '[/br]'.join([x for x in (head, lead) if x])

    def _isFeatureFilm(self, item):
        for cat in (item.get('categories') or []):
            try:
                if int(cat.get('id', 0)) == self.FEATURE_FILM_CAT:
                    return True
            except Exception:
                pass
        return False

    def _isDrmAudio(self, item):
        if item.get('audio') and not item.get('video'):
            return True
        cats = [(item.get('mainCategory') or {}).get('id')] + [c.get('id') for c in (item.get('categories') or []) if isinstance(c, dict)]
        for cid in cats:
            try:
                if int(cid or 0) in self.AUDIO_CATS:
                    return not item.get('video')
            except Exception:
                pass
        return False

    @staticmethod
    def _baseTitle(title):
        # the site writes "<title> | <director>" - the bare title is what moviemeta and the
        # normalised name need
        return title.split(' | ', 1)[0].strip() if ' | ' in title else title.strip()

    def _addProduct(self, cItem, item):
        try:
            if not isinstance(item, dict):
                return False
            ptype = (item.get('type') or item.get('type_') or '').upper()
            pid = item.get('id')
            title = self.cleanHtmlStr(item.get('title') or '')
            if not pid or not title or ptype not in ('VOD', 'EPISODE', 'SERIAL') or self._isDrmAudio(item):
                return False
            params = {'name': 'category', 'good_for_fav': True, 'prod_id': str(pid), 'prod_type': ptype,
                      'title': title, 'icon': self._img(item), 'desc': self._desc(item),
                      'url': item.get('webUrl') or '%sapi/products/vods/%s' % (self.MAIN_URL, pid)}
            if ptype == 'SERIAL':
                params.update({'category': 'list_serial', 'serial_id': str(pid), 's_title': title})
                self.addDir(params)
                return True
            if ptype == 'VOD' and self._isFeatureFilm(item):
                base = self._baseTitle(title)
                year = str(item.get('year') or '')
                params.update({'meta_type': 'movie', 'meta_title': base, 'meta_year': year})
                if IsMediaNamingNormalized() and year:
                    params['title'] = '%s (%s)' % (base, year)
            elif ptype == 'EPISODE':
                season = item.get('season') or {}
                serial = season.get('serial') or {}
                sTitle = self.cleanHtmlStr(serial.get('title') or cItem.get('s_title') or '')
                sNum = season.get('number') or cItem.get('season') or ''
                eNum = item.get('number') or ''
                if sTitle and sNum and eNum:
                    params.update({'s_title': sTitle, 'season': str(sNum), 'episode': str(eNum)})
                    if IsMediaNamingNormalized():
                        params['title'] = '%s - %s' % (sTitle, formatSxxExx(sNum, eNum))
            self.addVideo(params)
            return True
        except Exception:
            printExc()
        return False

    def _first(self, cItem):
        # firstResult of the page to list
        return (max(1, int(cItem.get('page', 1) or 1)) - 1) * self.PAGE_SIZE

    def _addPaging(self, cItem, meta, count):
        # the API pages with firstResult/maxResults + totalCount; the page number drives the request, the
        # template (the site's own "?page=N" form) only gives Jump its target
        page = max(1, int(cItem.get('page', 1) or 1))
        try:
            total = int(meta.get('totalCount', 0) or 0)
        except Exception:
            total = 0
        lastPage = (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE if total else 0
        addPagingItems(self, cItem, page, bool(count) and page < lastPage, lastPage, self.MAIN_URL + '?page={page}')

    ###################################################
    # lists
    ###################################################
    def listHome(self, cItem):
        data = self._json(self._api('products/sections/main', 'elementsLimit=1'))
        if not isinstance(data, list):
            return
        for section in data:
            try:
                if not isinstance(section, dict) or section.get('layout') == 'BANNER':
                    continue
                title = self.cleanHtmlStr(section.get('title') or '')
                if not title or not section.get('id'):
                    continue
                first = ((section.get('elements') or [{}])[0] or {}).get('item') or {}
                # skip article/teaser rows and the audiobook shelf (serials of DRM-only audio)
                ftype = (first.get('type') or '').upper()
                if first and (ftype not in ('VOD', 'EPISODE', 'SERIAL') or (ftype == 'SERIAL' and self._isDrmAudio(first))):
                    continue
                params = dict(cItem)
                params.update({'category': 'list_section', 'title': title, 'section_id': str(section['id']),
                               'good_for_fav': True, 'page': 1})
                self.addDir(params)
            except Exception:
                printExc()

    def listSection(self, cItem):
        first = self._first(cItem)
        data = self._json(self._api('products/sections/%s' % cItem['section_id'],
                                    'firstResult=%d&maxResults=%d' % (first, self.PAGE_SIZE)))
        if not isinstance(data, dict):
            return
        elements = data.get('elements') or []
        for el in elements:
            self._addProduct(cItem, (el or {}).get('item'))
        self._addPaging(cItem, data.get('meta') or {}, len(elements))

    def listCategories(self, cItem):
        data = self._json(self._api('items/categories', 'mainCategoryId=%d' % self.VIDEO_ROOT_CAT))
        if not isinstance(data, list):
            return
        for cat in data:
            try:
                title = self.cleanHtmlStr(cat.get('name') or '')
                if not title or not cat.get('id') or cat.get('adult') or int(cat['id']) in self.AUDIO_CATS:
                    continue
                params = dict(cItem)
                params.update({'category': 'list_vods', 'title': title[:1] + title[1:].lower(),
                               'cat_id': str(cat['id']), 'good_for_fav': True, 'page': 1})
                self.addDir(params)
            except Exception:
                printExc()

    def listVods(self, cItem):
        first = self._first(cItem)
        query = 'firstResult=%d&maxResults=%d' % (first, self.PAGE_SIZE)
        if cItem.get('cat_id'):
            query += '&categoryId%%5B%%5D=%s' % cItem['cat_id']
        data = self._json(self._api('products/vods', query))
        if not isinstance(data, dict):
            return
        items = data.get('items') or []
        for item in items:
            self._addProduct(cItem, item)
        self._addPaging(cItem, data.get('meta') or {}, len(items))

    def listSerial(self, cItem):
        data = self._json(self._api('products/vods/serials/%s/seasons' % cItem['serial_id']))
        if not isinstance(data, list) or not data:
            return
        sTitle = cItem.get('s_title') or cItem.get('title', '')
        if len(data) == 1:
            params = dict(cItem)
            params.update({'season_id': str(data[0].get('id', '')), 'season': str(data[0].get('number') or '1')})
            self.listEpisodes(params)
            return
        for season in data:
            sid = season.get('id')
            if not sid:
                continue
            num = str(season.get('number') or '')
            title = self.cleanHtmlStr(season.get('title') or '') or ('%s %s' % (_('Season'), num)).strip()
            params = dict(cItem)
            params.update({'category': 'list_episodes', 'title': '%s - %s' % (sTitle, title), 's_title': sTitle,
                           'season_id': str(sid), 'season': num, 'icon': self._img(season) or cItem.get('icon', ''),
                           'good_for_fav': True})
            self.addDir(params)

    def listEpisodes(self, cItem):
        data = self._json(self._api('products/vods/serials/%s/seasons/%s/episodes' % (cItem['serial_id'], cItem['season_id'])))
        if not isinstance(data, list):
            return
        for item in data:
            self._addProduct(cItem, item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        first = self._first(cItem)
        data = self._json(self._api('products/vods/search', 'keyword=%s&firstResult=%d&maxResults=%d'
                                    % (urllib_quote_plus(searchPattern), first, self.PAGE_SIZE)))
        if not isinstance(data, dict):
            return
        items = data.get('items') or []
        for item in items:
            self._addProduct(cItem, item)
        self._addPaging(cItem, data.get('meta') or {}, len(items))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('Ninateka.getLinksForVideo [%s]' % cItem.get('prod_id', ''))
        pid = cItem.get('prod_id', '')
        if not pid:
            return []
        data = self._json(self._api('products/%s/videos/playlist' % pid, 'videoType=MOVIE'))
        if not isinstance(data, dict):
            return []
        sources = data.get('sources') or {}
        hls = [s.get('src') for s in (sources.get('HLS') or []) if s.get('src')]
        if not hls:
            if data.get('drm'):
                SetIPTVPlayerLastHostError(_('Video with DRM protection.'))
            else:
                SetIPTVPlayerLastHostError(_('No stream available'))
            return []

        subTracks = []
        for sub in (data.get('subtitles') or []):
            surl = sub.get('url') or sub.get('src') or ''
            if not surl:
                continue
            if surl.startswith('//'):
                surl = 'https:' + surl
            lang = (sub.get('language') or '').lower()
            lang = SUB_LANGS.get(lang, lang[:2])
            fmt = 'srt' if surl.lower().split('?', 1)[0].endswith('.srt') else 'vtt'
            subTracks.append({'title': sub.get('label') or lang.upper() or 'PL', 'url': surl, 'lang': lang, 'format': fmt})

        meta = {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.MAIN_URL, 'iptv_proto': 'm3u8'}
        if subTracks:
            meta['external_sub_tracks'] = subTracks
        urlTab = []
        for src in hls:
            if src.startswith('//'):
                src = 'https:' + src
            # audio is muxed into the TS segments - the AUDIO group is only an alternative copy
            links = getDirectM3U8Playlist(strwithmeta(src, meta), checkExt=False, checkContent=True,
                                          sortWithMaxBitrate=999999999, mergeAltAudio=False)
            for link in links:
                link['need_resolve'] = 0
                link.pop('alt_audio_streams', None)
                if link.get('height'):
                    link['name'] = '%sp (%s kbps)' % (link['height'], int(link.get('bitrate', 0) or 0) // 1000)
                urlTab.append(link)
            if not links:
                urlTab.append({'name': 'HLS', 'url': strwithmeta(src, meta), 'need_resolve': 0})
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(cItem.get('desc', ''))))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('Ninateka.getArticleContent [%s]' % cItem.get('prod_id', ''))
        pid = cItem.get('prod_id', '') or cItem.get('serial_id', '')
        isSerial = cItem.get('prod_type') == 'SERIAL' or not cItem.get('prod_id')
        item = self._json(self._api(('products/vods/serials/%s' if isSerial else 'products/vods/%s') % pid)) if pid else None
        if not isinstance(item, dict):
            item = {}
        otherInfo = {}
        if item.get('year'):
            otherInfo['year'] = str(item['year'])
        dur = self._duration(item.get('duration'))
        if dur:
            otherInfo['duration'] = dur
        if item.get('originalTitle'):
            otherInfo['original_title'] = self.cleanHtmlStr(item['originalTitle'])
        persons = item.get('persons') or {}
        for key, field in (('DIRECTING', 'director'), ('SCRIPT', 'writers'), ('CAST', 'actors')):
            names = [p.get('name') for p in (persons.get(key) or []) if isinstance(p, dict) and p.get('name')]
            if names:
                otherInfo[field] = ', '.join(names[:8])
        genres = [g.get('name') for g in (item.get('genres') or []) if isinstance(g, dict) and g.get('name')]
        if genres:
            otherInfo['genres'] = ', '.join(genres)
        text = self.cleanHtmlStr(item.get('description') or item.get('lead') or '') or self.cleanHtmlStr(cItem.get('desc', ''))
        icon = self._img(item) or cItem.get('icon', '')
        if cItem.get('meta_type'):
            try:
                meta = getMeta(cItem['meta_type'], cItem.get('meta_title', ''), cItem.get('meta_year', ''))
            except Exception:
                printExc()
                meta = {}
            for key, val in (meta.get('info', {}) or {}).items():
                otherInfo.setdefault(key, val)
            text = text or meta.get('plot', '')
            icon = icon or meta.get('poster', '')
        return [{'title': cItem.get('title', ''), 'text': text,
                 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('prod_id') or cItem.get('serial_id'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('Ninateka.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        searchPattern = self.currItem.get('search_pattern', searchPattern)
        printDBG('Ninateka.handleService: name[%s] category[%s]' % (name, category))
        self.currList = []

        if name is None:
            tab = [{'category': 'list_home', 'title': _('Home page')},
                   {'category': 'list_cats', 'title': _('Categories')},
                   {'category': 'list_vods', 'title': _('All')}] + self.searchItems()
            self.listsTab(tab, {'name': 'category'})
        elif category == 'list_home':
            self.listHome(self.currItem)
        elif category == 'list_section':
            self.listSection(self.currItem)
        elif category == 'list_cats':
            self.listCategories(self.currItem)
        elif category == 'list_vods':
            self.listVods(self.currItem)
        elif category == 'list_serial':
            self.listSerial(self.currItem)
        elif category == 'list_episodes':
            self.listEpisodes(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page', 'search_pattern': searchPattern})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Ninateka(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('ninateka')

    def withArticleContent(self, cItem):
        return bool(cItem.get('prod_id') or cItem.get('serial_id'))
