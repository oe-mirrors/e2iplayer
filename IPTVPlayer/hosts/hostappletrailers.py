# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
#
# trailers.apple.com is gone (the whole domain 301s to tv.apple.com and
# every /trailers/*.json feed with it). This rebuild targets the Apple TV
# web backend instead:
#   https://uts-api.itunes.apple.com/uts/v3/...   (token-less, utsk=0)
#   - /uts/v2/browse/movies                       -> editorial shelves
#   - /uts/v2/browse/collection/<id>              -> a shelf, paged
#   - /uts/v2/browse/genre/<genreId>             -> per-genre shelves
#   - /uts/v3/mcp/genres                          -> genre list
#   - /uts/v3/movies/<id>?includePreviewAssets=1  -> the "Trailers" shelf
# The iTunes-store previews resolve to a plain (DRM-free) HLS playlist on
# play-edge.itunes.apple.com; Apple TV+ channel previews do not and are
# skipped.
# 09.10.2026 - host standard
#   - trailer rows are keyed on a stable url (movie id + trailer id) and find their stream again without the
#     list they came from: favourites / downloads / watched flag of trailers work (before they only worked
#     right after opening the film; rows saved by the old version reopen too)
#   - film folders "Title (Year)" and trailers "Title (Year) - <trailer>" (name normalisation), INFO for films
#     and trailers via moviemeta + Apple's fields (genre, cast, director, rating, runtime)
#   - watched flag (the film folder follows its trailers), sidecar on the links, Next page counts the pages,
#     a genre lists its shelves (each paged) instead of one long list, current default user agent
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################

###################################################
# FOREIGN import
###################################################
import re
from datetime import datetime, timedelta
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

# the stable url of a trailer row: tv.apple.com movie id + the trailer's own id
TRAILER_URL = 'https://tv.apple.com/movie/%s#trailer=%s'
TRAILER_URL_RE = re.compile(r'/movie/(umc\.[^#/?]+)#trailer=([^&#]+)')
# rows saved by the old version: "apl_<movie id>_<n-th trailer>"
OLD_KEY_RE = re.compile(r'^apl_(umc\..+)_(\d+)$')


def GetConfigList():
    return [getConfigListEntry(_('Country / store:'), config.plugins.iptvplayer.appletrailers_storefront)]


def gettytul():
    return 'https://tv.apple.com/'


class TrailersApple(GenericFolderWatchedScraperMixin, CBaseHostClass):

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
        self.watchedHelper = IPTVWatchedHelper('appletrailers')
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    # ---------------------------------------------------------------- watched flag
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            # rows saved by the old version: trailers with category "movie" and type "video"
            if cItem.get('type') == 'video' or cItem.get('category') == 'video':
                url = str(cItem.get('url', '') or '')
                return 'video:%s' % url if url else ''
            if cItem.get('category') == 'movie' and cItem.get('movie_id'):
                return 'movie:%s' % cItem['movie_id']
        except Exception:
            printExc()
        return ''

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
    def _img(images, keys, width=600, height=900):
        # posters 600x900; trailer stills are 16:9 - a "mw" still asked for in 2:3 answers 400
        if not isinstance(images, dict):
            return ''
        for k in keys:
            node = images.get(k)
            if isinstance(node, dict) and node.get('url'):
                url = node['url']
                url = url.replace('{w}', str(width)).replace('{h}', str(height)).replace('{f}', 'jpg').replace('{c}', 'bb')
                return re.sub(r'\{[^}]+\}', str(width), url)
        return ''

    @staticmethod
    def _year(item):
        rd = item.get('releaseDate')
        if isinstance(rd, (int, float)):
            try:
                # epoch milliseconds (UTC, negative before 1970) - py2 + py3, no platform limits of fromtimestamp
                day = datetime(1970, 1, 1) + timedelta(milliseconds=rd)
                return '%04d-%02d-%02d' % (day.year, day.month, day.day)
            except Exception:
                pass
        return ''

    @staticmethod
    def _names(value, limit=6):
        out = []
        for v in (value if isinstance(value, list) else [])[:limit]:
            name = v.get('name', '') if isinstance(v, dict) else v
            if name:
                out.append(name)
        return ', '.join(out)

    def _siteInfo(self, item):
        # Apple's own fields of a movie (browse item or /movies/<id> content) for the INFO screen
        info = {}
        date = self._year(item)
        if date:
            info['released'] = date
            info['year'] = date[:4]
        rating = (item.get('rating') or {}).get('displayName')
        if rating:
            info['rated'] = rating
        if item.get('tomatometerPercentage'):
            info['rating'] = 'Rotten Tomatoes %s%%' % item['tomatometerPercentage']
        genres = self._names(item.get('genres'))
        if genres:
            info['genres'] = genres
        roles = item.get('rolesSummary') or {}
        for key, metaKey in (('cast', 'cast'), ('directors', 'directors')):
            value = self._names(roles.get(key))
            if value:
                info[metaKey] = value
        try:
            minutes = int(item.get('duration') or 0) // 60
        except (TypeError, ValueError):
            minutes = 0
        if minutes:
            info['duration'] = '%dh %02dmin' % (minutes // 60, minutes % 60) if minutes >= 60 else '%dmin' % minutes
        if item.get('studio'):
            info['production'] = item['studio']
        return info

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year and '(%s)' % year not in title:
            return '%s (%s)' % (title, year)
        return title

    def _addMovie(self, cItem, item):
        # only single movies expose /uts/v3/movies/<id>; bundles 404 there
        if item.get('type') != 'Movie':
            return
        mid = item.get('id')
        if not mid:
            return
        siteInfo = self._siteInfo(item)
        year = siteInfo.get('year', '')
        title = item.get('title', '')
        desc = []
        for key in ('released', 'rated', 'rating'):
            if siteInfo.get(key):
                desc.append(siteInfo[key].replace('Rotten Tomatoes', 'RT'))
        if item.get('description'):
            desc.append('\n' + item['description'])
        self.addDir({'good_for_fav': True, 'name': 'category', 'category': 'movie', 'movie_id': mid,
                     'title': self._movieTitle(title, year), 'icon': self._img(item.get('images'), ('coverArt', 'coverArt16X9', 'shelfImage', 'previewFrame')),
                     'desc': ' | '.join(desc), 'site_info': siteInfo, 'plot': item.get('description', ''),
                     'meta_type': 'movie', 'meta_title': title, 'meta_year': year})

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
            params.update({'good_for_fav': True, 'category': 'collection', 'coll_id': coll, 'title': title})
            self.addDir(params)
        params = dict(cItem)
        params.update({'good_for_fav': True, 'category': 'genres', 'title': _('Browse by genre')})
        self.addDir(params)
        self.listsTab(self.searchItems(), cItem)

    def listCollection(self, cItem):
        printDBG("TrailersApple.listCollection")
        try:
            page = max(1, int(cItem.get('page', 1)))
        except (TypeError, ValueError):
            page = 1
        extra = ''
        if page > 1 and cItem.get('next_token'):
            extra = 'nextToken=' + urllib_quote_plus(cItem['next_token'])
        js = self._getJson(self._apiUrl('uts/v2/browse/collection/%s' % cItem['coll_id'], extra))
        data = (js or {}).get('data', {})
        items = data.get('items', [])
        for item in items:
            self._addMovie(cItem, item)
        # a page of only bundles / TV+ items adds no row but the shelf goes on
        nextToken = data.get('nextToken')
        addPagingItems(self, cItem, page, bool(nextToken) and bool(items), nextParams={'next_token': nextToken})

    def listGenres(self, cItem):
        printDBG("TrailersApple.listGenres")
        js = self._getJson(self._apiUrl('uts/v3/mcp/genres'))
        for genre in (js or {}).get('data', {}).get('genres', []):
            ident = genre.get('identifier')
            if not ident:
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'genre_items', 'genre_id': 'umc.gnr.mov.%s' % ident, 'title': genre.get('name', ident)})
            self.addDir(params)

    def listGenreItems(self, cItem):
        printDBG("TrailersApple.listGenreItems")
        # the genre page is a few shelves (charts, editors' picks ...) - each one a paged collection
        js = self._getJson(self._apiUrl('uts/v2/browse/genre/%s' % cItem['genre_id']))
        for shelf in (js or {}).get('data', {}).get('canvas', {}).get('shelves', []):
            if not shelf.get('id') or not any(i.get('type') == 'Movie' for i in shelf.get('items', [])):
                continue
            self.addDir({'good_for_fav': True, 'name': 'category', 'category': 'collection', 'coll_id': shelf['id'],
                         'title': '%s - %s' % (cItem.get('title', ''), shelf.get('title') or _('Movies'))})

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

    # ---------------------------------------------------------------- trailers
    def _getTrailers(self, movieId):
        # (movie content, [(trailer id, label, icon, [hls urls])]) of a movie, DRM-free previews only
        js = self._getJson(self._apiUrl('uts/v3/movies/%s' % movieId, 'includePreviewAssets=true'))
        data = (js or {}).get('data', {})
        trailers = []
        for shelf in data.get('canvas', {}).get('shelves', []):
            if shelf.get('id') != 'uts.col.Trailers':
                continue
            for idx, item in enumerate(shelf.get('items', [])):
                streams = []
                for pl in item.get('playables', []):
                    hlsUrl = pl.get('assets', {}).get('hlsUrl', '')
                    # only the DRM-free iTunes-store preview playlist
                    if '/hls/playlist.m3u8' not in hlsUrl or '/hls/subscription/' in hlsUrl:
                        continue
                    streams.append(hlsUrl)
                if streams:
                    trailers.append((item.get('id') or str(idx), item.get('title') or _('Trailer'),
                                     self._img(item.get('images'), ('shelfImage', 'previewFrame'), 640, 360), streams))
        return data.get('content', {}), trailers

    def exploreItem(self, cItem):
        printDBG("TrailersApple.exploreItem [%s]" % cItem)
        movieId = cItem['movie_id']
        content, trailers = self._getTrailers(movieId)
        movieTitle = content.get('title') or cItem.get('meta_title') or cItem.get('title', '')
        siteInfo = self._siteInfo(content) if content else cItem.get('site_info', {})
        year = siteInfo.get('year', '') or cItem.get('meta_year', '')
        dispTitle = self._movieTitle(movieTitle, year)
        for trailerId, label, icon, streams in trailers:
            url = TRAILER_URL % (movieId, trailerId)
            self.cacheLinks[url] = streams
            name = dispTitle if label == movieTitle else '%s - %s' % (dispTitle, label)
            self.addVideo({'good_for_fav': True, 'name': 'category', 'category': 'video', 'title': name, 'url': url,
                           'movie_id': movieId, 'trailer_id': trailerId, 'icon': icon or cItem.get('icon', ''),
                           'desc': cItem.get('desc', ''), 'site_info': siteInfo, 'plot': content.get('description') or cItem.get('plot', ''),
                           'meta_type': 'movie', 'meta_title': movieTitle, 'meta_year': year})
        if not trailers:
            printDBG("TrailersApple.exploreItem: no DRM-free trailer for %s" % movieId)

    def _streamsForItem(self, cItem):
        url = cItem.get('url', '')
        if url in self.cacheLinks:
            return self.cacheLinks[url]
        movieId, trailerId = cItem.get('movie_id', ''), cItem.get('trailer_id', '')
        position = 0
        found = TRAILER_URL_RE.search(url)
        if found:
            movieId, trailerId = found.group(1), found.group(2)
        else:
            old = OLD_KEY_RE.match(url)
            if old:
                movieId, position = old.group(1), int(old.group(2))
        if not movieId:
            return []
        _content, trailers = self._getTrailers(movieId)
        for idx, (tid, _label, _icon, streams) in enumerate(trailers):
            self.cacheLinks[TRAILER_URL % (movieId, tid)] = streams
            if (trailerId and tid == trailerId) or (position and idx + 1 == position):
                return streams
        return []

    def getLinksForVideo(self, cItem):
        printDBG("TrailersApple.getLinksForVideo [%s]" % cItem)
        urlTab = []
        for streamUrl in self._streamsForItem(cItem):
            urlTab.append({'name': 'HLS', 'url': strwithmeta(streamUrl, {'User-Agent': self.HEADER['User-Agent']}), 'need_resolve': 1})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get('plot', '')))

    def getVideoLinks(self, videoUrl):
        printDBG("TrailersApple.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        videoUrl = strwithmeta(videoUrl, {'User-Agent': self.HEADER['User-Agent']})
        return decorateResolvedLinkItems(getDirectM3U8Playlist(videoUrl, checkExt=False, sortWithMaxBitrate=99999999), sidecar)

    # ---------------------------------------------------------------- INFO
    def getArticleContent(self, cItem):
        printDBG("TrailersApple.getArticleContent [%s]" % cItem)
        info = dict(cItem.get('site_info') or {})
        title = cItem.get('meta_title', '')
        year = cItem.get('meta_year', '')
        if not title:
            # a row saved by the old version: Apple's own fields of the movie
            old = OLD_KEY_RE.match(cItem.get('url', ''))
            movieId = cItem.get('movie_id') or (old.group(1) if old else '')
            if movieId:
                content, _trailers = self._getTrailers(movieId)
                info = self._siteInfo(content)
                title, year = content.get('title', ''), info.get('year', '')
                cItem = dict(cItem, plot=content.get('description', ''))
        meta = {}
        if title:
            try:
                meta = getMeta('movie', title, year, maxYearDiff=1)
            except Exception:
                printExc()
        for siteKey in ('rating', 'production'):
            if siteKey in info and meta.get('info'):
                info.pop(siteKey)
        info.update(meta.get('info', {}))
        text = cItem.get('plot', '') or cItem.get('desc', '')
        plot = meta.get('plot', '')
        if plot and text and plot != text:
            text = '%s[/br][/br]%s' % (text, plot)
        else:
            text = text or plot
        icon = cItem.get('icon', '') or meta.get('poster', '') or self.DEFAULT_ICON_URL
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': icon}], 'other_info': info}]

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


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, TrailersApple(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('appletrailers')

    def withArticleContent(self, cItem):
        return cItem.get('category') == 'movie' or cItem.get('type') == 'video'
