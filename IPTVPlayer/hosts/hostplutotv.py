# -*- coding: utf-8 -*-
LAST_MODIFIED = "25.10.2026"
# Pluto TV - free ad-supported streaming (catalogue of the country the box is in, Germany: ~200 channels):
# live channels by category with now / next, on-demand categories -> films / series -> seasons -> episodes,
# search. JSON API of the web app (boot.pluto.tv v4 session token), plain HLS from the stitcher.
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
# FOREIGN import
###################################################
import re
import time
import calendar
import uuid
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://pluto.tv/'


class PlutoTV(GenericFolderWatchedScraperMixin, CBaseHostClass):
    BOOT_URL = 'https://boot.pluto.tv/v4/start'
    SERVERS = {'channels': 'https://service-channels.clusters.pluto.tv', 'vod': 'https://service-vod.clusters.pluto.tv',
               'search': 'https://service-media-search.clusters.pluto.tv', 'stitcher': 'https://service-stitcher.clusters.pluto.tv'}
    SITE = 'https://pluto.tv'
    VOD_PAGE_SIZE = 50
    LIVE_PAGE_SIZE = 50
    CACHE_TIME = 1800           # channel list / categories are kept 30 minutes
    EPG_MINUTES = 90            # the guide window read for now / next
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 'icon', 'desc', 'cat_id', 'item_id', 'kind', 'slug', 'stitched',
                  'live', 's_title', 'series_id', 'series_slug', 'season', 'episode', 'meta_type', 'meta_title', 'meta_year')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'plutotv', 'cookie': 'plutotv.cookie'})
        self.MAIN_URL = self.SITE + '/'
        self.DEFAULT_ICON_URL = 'https://images.pluto.tv/assets/images/default/vodcategory.id-imageFeatured.jpg'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Accept': 'application/json, text/plain, */*', 'Origin': self.SITE, 'Referer': self.SITE + '/'})
        self.defaultParams = {'header': self.HEADER}
        self.clientId = str(uuid.uuid4())
        self.session = {}
        self.sessionExpires = 0
        self.cache = {}
        self.seriesCache = {}
        self.watchedHelper = IPTVWatchedHelper('plutotv')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            iid = str(cItem.get('item_id', '') or '').strip()
            if not iid:
                return ''
            if cItem.get('type', '') == 'video':
                return 'item:%s' % iid
            if cItem.get('category') == 'list_series':
                return 'series:%s' % iid
            if cItem.get('category') == 'list_season':
                return 'season:%s:%s' % (iid, cItem.get('season', ''))
        except Exception:
            printExc()
        return ''

    ###################################################
    # session / API
    ###################################################
    def _boot(self, force=False):
        if self.session and not force and time.time() < self.sessionExpires:
            return self.session
        query = {'appName': 'web', 'appVersion': '9.12.0', 'deviceVersion': '130.0.0', 'deviceModel': 'web', 'deviceMake': 'chrome',
                 'deviceType': 'web', 'clientID': self.clientId, 'clientModelNumber': '1.0.0', 'serverSideAds': 'false',
                 'drmCapabilities': ''}
        url = self.BOOT_URL + '?' + '&'.join('%s=%s' % (k, urllib_quote_plus(v)) for k, v in sorted(query.items()))
        sts, data = self.cm.getPage(url, dict(self.defaultParams))
        session = {}
        if sts:
            try:
                data = json_loads(data)
                if data.get('sessionToken'):
                    session = data
            except Exception:
                printExc()
        if session:
            self.session = session
            try:
                lifetime = int(session.get('refreshInSec') or 0)
            except Exception:
                lifetime = 0
            # the token is valid for 24 hours, the app renews it after refreshInSec (8 hours)
            self.sessionExpires = time.time() + min(max(lifetime, 600), 4 * 3600)
        return self.session

    def _server(self, name):
        servers = (self.session or {}).get('servers') or {}
        return (servers.get(name) or self.SERVERS[name]).rstrip('/')

    def _api(self, server, path, retry=True):
        session = self._boot()
        if not session:
            return None
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER)
        params['header']['Authorization'] = 'Bearer ' + session['sessionToken']
        params['ignore_http_code_ranges'] = [(400, 499)]
        sts, data = self.cm.getPage(self._server(server) + path, params)
        if not sts or not data:
            return None
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return None
        if isinstance(data, dict) and retry and str(data.get('statusCode', data.get('code', ''))) in ('401', '403'):
            # an expired / rejected session token: a new session once
            self._boot(True)
            return self._api(server, path, False)
        return data

    def _cached(self, key, server, path):
        entry = self.cache.get(key)
        if entry and time.time() - entry[0] < self.CACHE_TIME:
            return entry[1]
        data = self._api(server, path)
        if data:
            self.cache[key] = (time.time(), data)
        return data

    def _channels(self):
        data = self._cached('channels', 'channels', '/v2/guide/channels?channelIds=&offset=0&limit=1000&sort=number%3Aasc')
        return [c for c in ((data or {}).get('data') or []) if isinstance(c, dict) and c.get('id') and not c.get('plutoOfficeOnly')]

    def _liveCategories(self):
        data = self._cached('live_cats', 'channels', '/v2/guide/categories')
        return [c for c in ((data or {}).get('data') or []) if isinstance(c, dict) and c.get('id') and c.get('channelIDs')]

    def _setGeoError(self, cacheKey):
        # countries without Pluto TV get a valid session but empty channel / on-demand lists; a failed request
        # (no answer, nothing cached) is no geo-blocking
        if not self.session or not self.cache.get(cacheKey):
            return
        session = (self.session or {}).get('session') or {}
        country = session.get('countryCode') or session.get('activeRegion') or ''
        printDBG('PlutoTV empty catalogue, country[%s] region[%s]' % (session.get('countryCode', ''), session.get('activeRegion', '')))
        SetIPTVPlayerLastHostError(_('Not available in your country (geo-blocking).') + (' [%s]' % country if country else ''))

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _image(images, types):
        for wanted in types:
            for img in images or []:
                if isinstance(img, dict) and img.get('type') == wanted and img.get('url'):
                    return img['url']
        return ''

    @staticmethod
    def _cover(item, ratio='347:500'):
        for cover in item.get('covers') or []:
            if isinstance(cover, dict) and cover.get('aspectRatio') == ratio and cover.get('url'):
                return cover['url']
        for key in ('featuredImage', 'poster16_9'):
            if (item.get(key) or {}).get('path'):
                return item[key]['path']
        return ''

    @staticmethod
    def _duration(ms):
        try:
            secs = int(ms or 0) // 1000
        except Exception:
            return ''
        if secs <= 0:
            return ''
        if secs >= 3600:
            return '%d:%02d:%02d' % (secs // 3600, (secs % 3600) // 60, secs % 60)
        return '%d:%02d' % (secs // 60, secs % 60)

    @staticmethod
    def _rating(value):
        value = str(value or '').strip()
        if not value or value.lower() == 'not rated':
            return ''
        value = value.replace('FSK-', '')
        return 'FSK %s' % value if value.isdigit() else value

    @staticmethod
    def _year(item):
        # the slug ends in "-<year>-1-1" (films) / "-<year>-<season>-<nr>" (episodes) - the original release year
        match = re.search(r'-((?:19|20)\d\d)-\d+-\d+(?:-ptv\d+)?$', str(item.get('slug') or ''))
        if match:
            return match.group(1)
        date = str((item.get('clip') or {}).get('originalReleaseDate') or '')
        return date[:4] if re.match(r'(?:19|20)\d\d', date) else ''

    @staticmethod
    def _episodeNum(item, season):
        # episode "number" is 101 for S01E01 on many series
        try:
            num = int(item.get('number') or 0)
            season = int(season or 0)
        except Exception:
            return ''
        if num >= 100 and season and num // 100 == season:
            num = num % 100
        return str(num) if num > 0 else ''

    def _vodDesc(self, item, extra=''):
        parts = [extra] if extra else []
        year = self._year(item)
        if year and item.get('type') != 'series':
            parts.append(year)
        dur = self._duration(item.get('originalContentDuration') or item.get('duration'))
        if dur:
            parts.append(dur)
        if item.get('genre'):
            parts.append(self.cleanHtmlStr(item['genre']))
        rating = self._rating(item.get('rating'))
        if rating:
            parts.append(rating)
        if item.get('type') == 'series' and item.get('seasonsNumbers'):
            parts.append('%s: %d' % (_('Seasons'), len(item['seasonsNumbers'])))
        text = self.cleanHtmlStr(item.get('description') or item.get('summary') or '')
        return '[/br]'.join([x for x in (' | '.join(parts), text) if x])

    def _addVodItem(self, cItem, item):
        try:
            if not isinstance(item, dict):
                return False
            iid = str(item.get('_id') or item.get('id') or '')
            title = self.cleanHtmlStr(item.get('name') or '')
            kind = str(item.get('type') or '').lower()
            if not iid or not title:
                return False
            slug = str(item.get('slug') or iid)
            params = {'name': 'category', 'good_for_fav': True, 'item_id': iid, 'kind': kind, 'slug': slug, 'title': title,
                      'icon': self._cover(item), 'desc': self._vodDesc(item)}
            if kind == 'series':
                params.update({'category': 'list_series', 'url': '%s/on-demand/series/%s' % (self.SITE, slug), 's_title': title,
                               'series_id': iid, 'series_slug': slug, 'meta_type': 'tv', 'meta_title': title, 'meta_year': ''})
                self.addDir(params)
                return True
            if kind != 'movie':
                return False
            year = self._year(item)
            params.update({'url': '%s/on-demand/movies/%s' % (self.SITE, slug), 'stitched': (item.get('stitched') or {}).get('path', ''),
                           'meta_type': 'movie', 'meta_title': title, 'meta_year': year})
            if IsMediaNamingNormalized() and year:
                params['title'] = '%s (%s)' % (title, year)
            self.addVideo(params)
            return True
        except Exception:
            printExc()
        return False

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get('page', 1) or 1))
        except Exception:
            return 1

    ###################################################
    # live
    ###################################################
    def listLiveCategories(self, cItem):
        for cat in self._liveCategories():
            params = dict(cItem)
            params.update({'category': 'list_live', 'title': self.cleanHtmlStr(cat.get('name') or ''), 'cat_id': cat['id'],
                           'good_for_fav': True, 'icon': self._image(cat.get('images'), ('pngImage',)), 'desc': ''})
            if params['title']:
                self.addDir(params)
        if self.currList:
            params = dict(cItem)
            params.update({'category': 'list_live', 'title': _('All stations'), 'cat_id': '', 'good_for_fav': True, 'icon': '', 'desc': ''})
            self.addDir(params)
        else:
            self._setGeoError('live_cats')

    def listLive(self, cItem):
        channels = self._channels()
        catId = cItem.get('cat_id', '')
        if catId:
            channels = [c for c in channels if catId in (c.get('categoryIDs') or [])]
        page = self._page(cItem)
        lastPage = max(1, (len(channels) + self.LIVE_PAGE_SIZE - 1) // self.LIVE_PAGE_SIZE)
        if len(channels) > self.LIVE_PAGE_SIZE:
            channels = channels[(page - 1) * self.LIVE_PAGE_SIZE:page * self.LIVE_PAGE_SIZE]
        else:
            page = lastPage = 1
        nowNext = self._nowNext([c['id'] for c in channels])
        for channel in channels:
            self._addChannel(cItem, channel, nowNext.get(channel['id'], ''))
        if lastPage > 1:
            # local paging: the constant template only lets "Jump" through, the page number drives the list
            addPagingItems(self, dict(cItem, desc=''), page, page < lastPage, lastPage, self.SITE + '/live-tv')

    def _addChannel(self, cItem, channel, epg=''):
        title = self.cleanHtmlStr(channel.get('name') or '')
        if not title:
            return
        summary = self.cleanHtmlStr(channel.get('summary') or '')
        params = {'name': 'category', 'good_for_fav': True, 'live': True, 'kind': 'channel', 'item_id': channel['id'],
                  'slug': channel.get('slug', ''), 'title': title, 'url': '%s/live-tv/%s' % (self.SITE, channel.get('slug') or channel['id']),
                  'stitched': (channel.get('stitched') or {}).get('path', ''),
                  'icon': self._image(channel.get('images'), ('colorLogoPNG', 'logo', 'solidLogoPNG')),
                  'desc': '[/br]'.join([x for x in (epg, summary) if x])}
        self.addVideo(params)

    @staticmethod
    def _parseTime(value):
        try:
            return calendar.timegm(time.strptime(str(value)[:19], '%Y-%m-%dT%H:%M:%S'))
        except Exception:
            return 0

    def _nowNext(self, channelIds):
        ret = {}
        if not channelIds:
            return ret
        try:
            now = time.time()
            start = time.strftime('%Y-%m-%dT%H:%M:00.000Z', time.gmtime(now))
            data = self._api('channels', '/v2/guide/timelines?start=%s&channelIds=%s&duration=%d' % (start, ','.join(channelIds), self.EPG_MINUTES))
            for channel in (data or {}).get('data') or []:
                lines = []
                for entry in channel.get('timelines') or []:
                    begin, end = self._parseTime(entry.get('start')), self._parseTime(entry.get('stop'))
                    title = self.cleanHtmlStr(entry.get('title') or '')
                    if not title or not begin:
                        continue
                    if begin <= now < end:
                        lines.append('%s: %s (%s - %s)' % (_('Now'), title, time.strftime('%H:%M', time.localtime(begin)), time.strftime('%H:%M', time.localtime(end))))
                    elif begin >= now and len(lines) == 1:
                        lines.append('%s: %s (%s)' % (_('Next'), title, time.strftime('%H:%M', time.localtime(begin))))
                        break
                if lines:
                    ret[str(channel.get('channelId'))] = '[/br]'.join(lines)
        except Exception:
            printExc()
        return ret

    ###################################################
    # on demand
    ###################################################
    def listVodCategories(self, cItem):
        data = self._cached('vod_cats', 'vod', '/v4/vod/categories?includeItems=false&includeCategoryFields=iconPng&offset=1000&page=1&sort=number%3Aasc')
        seen = set()
        for cat in (data or {}).get('categories') or []:
            if not isinstance(cat, dict) or not cat.get('_id') or cat.get('hero_carousel') or cat.get('plutoOfficeOnly'):
                continue
            title = self.cleanHtmlStr(cat.get('name') or '')
            if not title or cat['_id'] in seen:
                continue
            seen.add(cat['_id'])
            params = dict(cItem)
            params.update({'category': 'list_vod', 'title': title, 'cat_id': cat['_id'], 'good_for_fav': True, 'icon': '', 'desc': ''})
            self.addDir(params)
        if not self.currList:
            self._setGeoError('vod_cats')

    def listVod(self, cItem):
        page = self._page(cItem)
        data = self._api('vod', '/v4/vod/categories/%s/items?offset=%d&page=%d' % (cItem['cat_id'], self.VOD_PAGE_SIZE, page))
        if not isinstance(data, dict):
            return
        count = 0
        for item in data.get('items') or []:
            if self._addVodItem(cItem, item):
                count += 1
        try:
            lastPage = (int(data.get('totalItemsCount') or 0) + self.VOD_PAGE_SIZE - 1) // self.VOD_PAGE_SIZE
        except Exception:
            lastPage = 0
        addPagingItems(self, dict(cItem, desc=''), page, bool(count) and page < lastPage, lastPage, self.SITE + '/on-demand')

    def _seasons(self, seriesId):
        if seriesId not in self.seriesCache:
            data = self._api('vod', '/v4/vod/series/%s/seasons?offset=1000&page=1' % seriesId)
            if not isinstance(data, dict) or not data.get('seasons'):
                return None
            if len(self.seriesCache) > 20:
                self.seriesCache = {}
            self.seriesCache[seriesId] = data
        return self.seriesCache[seriesId]

    def listSeries(self, cItem):
        data = self._seasons(cItem['series_id'])
        if not data:
            return
        sTitle = self.cleanHtmlStr(data.get('name') or '') or cItem.get('s_title', '')
        seasons = [s for s in data.get('seasons') or [] if isinstance(s, dict) and s.get('episodes')]
        if len(seasons) == 1:
            params = dict(cItem)
            params.update({'category': 'list_season', 'season': str(seasons[0].get('number') or ''), 's_title': sTitle})
            self.listSeason(params)
            return
        for season in seasons:
            num = str(season.get('number') or '')
            params = dict(cItem)
            params.update({'category': 'list_season', 'title': '%s - %s %s' % (sTitle, _('Season'), num), 's_title': sTitle, 'season': num,
                           'desc': '%s: %d' % (_('Episodes'), len(season['episodes'])), 'good_for_fav': True})
            self.addDir(params)

    def listSeason(self, cItem):
        data = self._seasons(cItem['series_id'])
        if not data:
            return
        sTitle = cItem.get('s_title') or self.cleanHtmlStr(data.get('name') or '')
        for season in data.get('seasons') or []:
            if str(season.get('number') or '') != str(cItem.get('season', '')):
                continue
            for item in season.get('episodes') or []:
                try:
                    iid = str(item.get('_id') or '')
                    name = self.cleanHtmlStr(item.get('name') or '')
                    if not iid or not name:
                        continue
                    sNum = str(item.get('season') or cItem.get('season') or '')
                    eNum = self._episodeNum(item, sNum)
                    title = name
                    if IsMediaNamingNormalized() and sNum and eNum:
                        title = '%s - %s - %s' % (sTitle, formatSxxExx(sNum, eNum), name)
                    slug = str(item.get('slug') or iid)
                    extra = formatSxxExx(sNum, eNum) if sNum and eNum else ''
                    params = {'name': 'category', 'good_for_fav': True, 'item_id': iid, 'kind': 'episode', 'slug': slug, 'title': title,
                              'url': '%s/on-demand/series/%s/season/%s/episode/%s' % (self.SITE, cItem.get('series_slug') or cItem['series_id'], sNum, slug),
                              'stitched': (item.get('stitched') or {}).get('path', ''), 'icon': self._cover(item, '16:9') or cItem.get('icon', ''),
                              'desc': self._vodDesc(item, extra), 's_title': sTitle, 'series_id': cItem['series_id'],
                              'series_slug': cItem.get('series_slug', ''), 'season': sNum, 'episode': eNum,
                              'meta_type': 'tv', 'meta_title': sTitle, 'meta_year': ''}
                    self.addVideo(params)
                except Exception:
                    printExc()
            break

    ###################################################
    # search
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        data = self._api('search', '/v1/search?q=%s&limit=100' % urllib_quote_plus(searchPattern))
        if not isinstance(data, dict):
            return
        results = [x for x in data.get('data') or [] if isinstance(x, dict) and x.get('id')]
        channels = dict((c['id'], c) for c in self._channels())
        vodIds = [x['id'] for x in results if x.get('type') in ('movie', 'series')]
        details = {}
        for idx in range(0, len(vodIds), 40):
            items = self._api('vod', '/v4/vod/items?ids=%s' % ','.join(vodIds[idx:idx + 40]))
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict) and item.get('_id'):
                    details[item['_id']] = item
        for result in results:
            kind = result.get('type')
            if kind == 'channel' and result['id'] in channels:
                self._addChannel(cItem, channels[result['id']])
            elif kind in ('movie', 'series'):
                self._addVodItem(cItem, details.get(result['id']) or {'_id': result['id'], 'name': result.get('name'), 'type': kind,
                                                                      'slug': result.get('slug'), 'rating': result.get('rating')})

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('PlutoTV.getLinksForVideo [%s]' % cItem.get('item_id', ''))
        iid = cItem.get('item_id', '')
        if not iid:
            return []
        session = self._boot()
        if not session:
            SetIPTVPlayerLastHostError(_('Get token failed!'))
            return []
        live = bool(cItem.get('live'))
        path = cItem.get('stitched') or ('/stitch/hls/%s/%s/master.m3u8' % ('channel' if live else 'episode', iid))
        url = '%s/v2%s?%s&jwt=%s&masterJWTPassthrough=true&includeExtendedEvents=true' % (
            self._server('stitcher'), path, session.get('stitcherParams', ''), session['sessionToken'])
        meta = {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.SITE + '/', 'Origin': self.SITE, 'iptv_proto': 'm3u8'}
        if live:
            meta['iptv_livestream'] = True
        urlTab = []
        for link in getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999):
            link['need_resolve'] = 0
            # the variants carry no RESOLUTION
            link['name'] = link.get('name', '').replace(' res: 0x0', '')
            urlTab.append(link)
        if not urlTab:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        if live:
            return urlTab
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(cItem.get('desc', '')).split('[/br]')[-1]))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('PlutoTV.getArticleContent [%s]' % cItem.get('item_id', ''))
        otherInfo = {}
        text = ''
        icon = cItem.get('icon', '')
        if cItem.get('live'):
            desc = cItem.get('desc', '')
            return [{'title': cItem.get('title', ''), 'text': desc, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]
        item = {}
        if cItem.get('kind') in ('movie', 'series', 'episode') and cItem.get('item_id'):
            data = self._api('vod', '/v4/vod/items?ids=%s' % cItem['item_id'])
            if isinstance(data, list) and data and isinstance(data[0], dict):
                item = data[0]
        if item:
            clip = item.get('clip') or {}
            year = self._year(item)
            if year and item.get('type') != 'series':
                otherInfo['year'] = year
            dur = self._duration(item.get('originalContentDuration') or item.get('duration'))
            if dur:
                otherInfo['duration'] = dur
            if item.get('genre'):
                otherInfo['genres'] = self.cleanHtmlStr(item['genre'])
            rating = self._rating(item.get('rating'))
            if rating:
                otherInfo['rated'] = rating
            if item.get('seasonsNumbers'):
                otherInfo['seasons'] = str(len(item['seasonsNumbers']))
            if clip.get('directors'):
                otherInfo['director'] = ', '.join(clip['directors'][:5])
            if clip.get('actors'):
                otherInfo['actors'] = ', '.join(clip['actors'][:8])
            text = self.cleanHtmlStr(item.get('description') or item.get('summary') or '')
            icon = self._cover(item) if cItem.get('kind') != 'episode' else icon
        if cItem.get('season') and cItem.get('episode'):
            otherInfo['season'] = cItem['season']
            otherInfo['episode'] = cItem['episode']
        text = text or self.cleanHtmlStr(cItem.get('desc', '')).split('[/br]')[-1]
        if cItem.get('meta_type') and cItem.get('meta_year'):
            # moviemeta only for films with their release year (series / episodes carry no year here)
            try:
                meta = getMeta(cItem['meta_type'], cItem.get('meta_title', ''), cItem.get('meta_year', ''))
            except Exception:
                printExc()
                meta = {}
            for key, val in (meta.get('info', {}) or {}).items():
                if val:
                    otherInfo.setdefault(key, val)
            text = text or meta.get('plot', '')
            icon = icon or meta.get('poster', '')
        return [{'title': cItem.get('title', ''), 'text': text.replace('\n', '[/br]'),
                 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('item_id') or cItem.get('cat_id') or cItem.get('category') in ('list_live', 'list_vod'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('PlutoTV.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        printDBG('PlutoTV.handleService: name[%s] category[%s]' % (name, category))
        self.currList = []

        if name is None:
            tab = [{'category': 'list_live_cats', 'title': _('Live channels')},
                   {'category': 'list_vod_cats', 'title': 'On Demand'}] + self.searchItems()
            self.listsTab(tab, {'name': 'category'})
        elif category == 'list_live_cats':
            self.listLiveCategories(self.currItem)
        elif category == 'list_live':
            self.listLive(self.currItem)
        elif category == 'list_vod_cats':
            self.listVodCategories(self.currItem)
        elif category == 'list_vod':
            self.listVod(self.currItem)
        elif category == 'list_series':
            self.listSeries(self.currItem)
        elif category == 'list_season':
            self.listSeason(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, PlutoTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('plutotv')

    def withArticleContent(self, cItem):
        return bool(cItem.get('item_id'))
