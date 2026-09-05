# -*- coding: utf-8 -*-
# Last Modified: 05.09.2026
#
# trailers.apple.com is gone (the whole domain 301s to tv.apple.com and
# every /trailers/*.json feed with it). This rebuild targets the Apple TV
# web backend instead:
#   https://uts-api.itunes.apple.com/uts/v3/...   (token-less, utsk=0)
#   - /uts/v2/browse/movies                       -> editorial shelves
#   - /uts/v2/browse/collection/<id>              -> a shelf, paged
#   - /uts/v2/browse/genre/<genreId>             -> per-genre charts
#   - /uts/v3/mcp/genres                          -> genre list
#   - /uts/v3/movies/<id>?includePreviewAssets=1  -> the "Trailers" shelf
# The iTunes-store previews resolve to a plain (DRM-free) HLS playlist on
# play-edge.itunes.apple.com; Apple TV+ channel previews do not and are
# skipped.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################

###################################################
# FOREIGN import
###################################################
import re
###################################################

# code -> (storefront id, locale, tv.apple.com country path)
STOREFRONTS = [
    ('us', ('143441', 'en-US', 'us')),
    ('gb', ('143444', 'en-GB', 'gb')),
    ('de', ('143443', 'de-DE', 'de')),
    ('fr', ('143442', 'fr-FR', 'fr')),
    ('it', ('143450', 'it-IT', 'it')),
    ('es', ('143454', 'es-ES', 'es')),
    ('ca', ('143455', 'en-CA', 'ca')),
    ('au', ('143460', 'en-AU', 'au')),
]
STOREFRONT_MAP = dict(STOREFRONTS)

config.plugins.iptvplayer.appletrailers_storefront = ConfigSelection(default='us', choices=[(c, c.upper()) for c, _v in STOREFRONTS])


def GetConfigList():
    return [getConfigListEntry(_('Country / store:'), config.plugins.iptvplayer.appletrailers_storefront)]


def gettytul():
    return 'https://tv.apple.com/'


class TrailersApple(CBaseHostClass):

    API_URL = 'https://uts-api.itunes.apple.com/'

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'TrailersApple', 'cookie': 'TrailersApple.cookie'})
        self.MAIN_URL = 'https://tv.apple.com/'
        self.DEFAULT_ICON_URL = 'https://tv.apple.com/assets/favicon/favicon-180.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER['Origin'] = 'https://tv.apple.com'
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheLinks = {}
        self._catalog = None

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    # ---------------------------------------------------------------- helpers
    def _sf(self):
        return STOREFRONT_MAP.get(config.plugins.iptvplayer.appletrailers_storefront.value, STOREFRONT_MAP['us'])

    def _apiUrl(self, path, extra=''):
        sf, locale, _cc = self._sf()
        q = 'caller=web&v=58&pfm=web&mfr=Apple&utsk=0&sf=%s&locale=%s' % (sf, locale)
        if extra:
            q += '&' + extra
        return '%s%s?%s' % (self.API_URL, path.lstrip('/'), q)

    def _getJson(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
            return None

    @staticmethod
    def _img(images, keys):
        if not isinstance(images, dict):
            return ''
        for k in keys:
            node = images.get(k)
            if isinstance(node, dict) and node.get('url'):
                url = node['url']
                url = url.replace('{w}', '600').replace('{h}', '900').replace('{f}', 'jpg').replace('{c}', 'bb')
                return re.sub(r'\{[^}]+\}', '600', url)
        return ''

    def _addMovie(self, cItem, item):
        # only single movies expose /uts/v3/movies/<id>; bundles 404 there
        if item.get('type') != 'Movie':
            return
        mid = item.get('id')
        if not mid:
            return
        desc = []
        rd = item.get('releaseDate')
        if isinstance(rd, (int, float)):
            try:
                from datetime import datetime
                desc.append(datetime.utcfromtimestamp(rd / 1000).strftime('%Y-%m-%d'))
            except Exception:
                pass
        if item.get('rating', {}).get('displayName'):
            desc.append(item['rating']['displayName'])
        if item.get('tomatometerPercentage'):
            desc.append('RT %s%%' % item['tomatometerPercentage'])
        if item.get('description'):
            desc.append('\n' + item['description'])
        params = dict(cItem)
        params.update({'good_for_fav': True, 'name': 'category', 'category': 'movie',
                       'movie_id': mid, 'title': item.get('title', ''),
                       'icon': self._img(item.get('images'), ('coverArt', 'coverArt16X9', 'shelfImage', 'previewFrame')),
                       'desc': ' | '.join(desc)})
        self.addDir(params)

    # ---------------------------------------------------------------- listings
    def listMainMenu(self, cItem):
        printDBG("TrailersApple.listMainMenu")
        js = self._getJson(self._apiUrl('uts/v2/browse/movies'))
        shelves = (js or {}).get('data', {}).get('canvas', {}).get('shelves', [])
        for shelf in shelves:
            title = shelf.get('title')
            coll = shelf.get('id', '')
            if not title or not coll:
                continue
            if not any(i.get('type') == 'Movie' for i in shelf.get('items', [])):
                continue
            params = dict(cItem)
            params.update({'category': 'collection', 'coll_id': coll, 'title': title})
            self.addDir(params)
        params = dict(cItem)
        params.update({'category': 'genres', 'title': _('Browse by genre')})
        self.addDir(params)
        self.listsTab(self.searchItems(), cItem)

    def listCollection(self, cItem):
        printDBG("TrailersApple.listCollection")
        extra = ''
        if cItem.get('next_token'):
            extra = 'nextToken=' + urllib_quote_plus(cItem['next_token'])
        js = self._getJson(self._apiUrl('uts/v2/browse/collection/%s' % cItem['coll_id'], extra))
        data = (js or {}).get('data', {})
        for item in data.get('items', []):
            self._addMovie(cItem, item)
        nextToken = data.get('nextToken')
        if nextToken:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'next_token': nextToken})
            self.addDir(params)

    def listGenres(self, cItem):
        printDBG("TrailersApple.listGenres")
        js = self._getJson(self._apiUrl('uts/v3/mcp/genres'))
        for genre in (js or {}).get('data', {}).get('genres', []):
            ident = genre.get('identifier')
            if not ident:
                continue
            params = dict(cItem)
            params.update({'category': 'genre_items', 'genre_id': 'umc.gnr.mov.%s' % ident, 'title': genre.get('name', ident)})
            self.addDir(params)

    def listGenreItems(self, cItem):
        printDBG("TrailersApple.listGenreItems")
        js = self._getJson(self._apiUrl('uts/v2/browse/genre/%s' % cItem['genre_id']))
        seen = set()
        for shelf in (js or {}).get('data', {}).get('canvas', {}).get('shelves', []):
            for item in shelf.get('items', []):
                if item.get('id') in seen:
                    continue
                seen.add(item.get('id'))
                self._addMovie(cItem, item)

    @staticmethod
    def _norm(s):
        return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()

    def _getCatalog(self):
        # Apple's own /uts/v3/search is scoped to Apple TV+ originals only and
        # returns unrelated titles for anything from the iTunes movie store
        # (Toy Story, Gladiator, ...). Build a local index from the store
        # charts instead - the Top Chart plus every genre chart - and filter
        # that. ~1300 titles, fetched once per host session.
        if self._catalog is not None:
            return self._catalog
        catalog = {}

        def collect(shelves):
            for shelf in shelves:
                for item in shelf.get('items', []):
                    if item.get('type') == 'Movie' and item.get('id', '').startswith('umc.cmc.'):
                        catalog.setdefault(item['id'], item)

        js = self._getJson(self._apiUrl('uts/v2/browse/collection/uts.col.ItunesCharts.chart.allMovies33'))
        collect([(js or {}).get('data', {})])
        gj = self._getJson(self._apiUrl('uts/v3/mcp/genres'))
        for genre in (gj or {}).get('data', {}).get('genres', []):
            ident = genre.get('identifier')
            if not ident:
                continue
            g = self._getJson(self._apiUrl('uts/v2/browse/genre/umc.gnr.mov.%s' % ident))
            collect((g or {}).get('data', {}).get('canvas', {}).get('shelves', []))

        self._catalog = list(catalog.values())
        printDBG("TrailersApple: catalog indexed, %d movies" % len(self._catalog))
        return self._catalog

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TrailersApple.listSearchResult [%s]" % searchPattern)
        nq = self._norm(searchPattern)
        if not nq:
            return
        qwords = set(nq.split())
        scored = []
        for item in self._getCatalog():
            nt = self._norm(item.get('title', ''))
            if nq in nt:
                scored.append((0, item))
            elif qwords and qwords <= set(nt.split()):
                scored.append((1, item))
        scored.sort(key=lambda x: (x[0], len(x[1].get('title', ''))))
        for _rank, item in scored:
            self._addMovie(cItem, item)

    # ---------------------------------------------------------------- playback
    def exploreItem(self, cItem):
        printDBG("TrailersApple.exploreItem [%s]" % cItem)
        self.cacheLinks = {}
        js = self._getJson(self._apiUrl('uts/v3/movies/%s' % cItem['movie_id'], 'includePreviewAssets=true'))
        data = (js or {}).get('data', {})
        movieTitle = data.get('content', {}).get('title') or cItem.get('title', '')
        shelves = data.get('canvas', {}).get('shelves', [])
        key = 0
        for shelf in shelves:
            if shelf.get('id') != 'uts.col.Trailers':
                continue
            for item in shelf.get('items', []):
                label = item.get('title') or _('Trailer')
                icon = self._img(item.get('images'), ('shelfImage', 'previewFrame', 'coverArt'))
                streams = []
                for pl in item.get('playables', []):
                    hlsUrl = pl.get('assets', {}).get('hlsUrl', '')
                    # only the DRM-free iTunes-store preview playlist
                    if '/hls/playlist.m3u8' not in hlsUrl or '/hls/subscription/' in hlsUrl:
                        continue
                    streams.append(hlsUrl)
                if not streams:
                    continue
                key += 1
                vkey = 'apl_%s_%d' % (cItem['movie_id'], key)
                self.cacheLinks[vkey] = streams
                name = movieTitle if label == movieTitle else '%s - %s' % (movieTitle, label)
                params = dict(cItem)
                params.update({'good_for_fav': True, 'name': 'category', 'title': name,
                               'url': vkey, 'icon': icon or cItem.get('icon', ''), 'desc': cItem.get('desc', '')})
                self.addVideo(params)
        if not self.currList:
            printDBG("TrailersApple.exploreItem: no DRM-free trailer for %s" % cItem['movie_id'])

    def getLinksForVideo(self, cItem):
        printDBG("TrailersApple.getLinksForVideo [%s]" % cItem)
        urlTab = []
        for streamUrl in self.cacheLinks.get(cItem.get('url', ''), []):
            urlTab.append({'name': 'HLS', 'url': strwithmeta(streamUrl, {'User-Agent': self.HEADER['User-Agent']}), 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("TrailersApple.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl, {'User-Agent': self.HEADER['User-Agent']})
        return getDirectM3U8Playlist(videoUrl, checkExt=False, sortWithMaxBitrate=99999999)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        printDBG("handleService: name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'collection':
            self.listCollection(self.currItem)
        elif category == 'genres':
            self.listGenres(self.currItem)
        elif category == 'genre_items':
            self.listGenreItems(self.currItem)
        elif category == 'movie':
            self.exploreItem(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, TrailersApple(), True, [])
