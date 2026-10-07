# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# DR TV (dr.dk/drtv) - the streaming service of Danmarks Radio: live channels (DR1, DR2, DR Ramasjang,
# TV Avisen), series, films, documentaries, the "Gensyn" archive, live sport, search.
# 03.10.2026 - revival + rewrite for the Massive "AXIS" platform the site runs on now:
#   JSON API production.dr-massive.com/api (page?path=..., lists/<id>, items/<id>, items/<id>/children,
#   search with an anonymous token from authorization/anonymous-sso), streams from
#   account/items/<id>/videos (plain HLS, geo-restricted titles are only playable from Denmark -> message,
#   DRM-only -> message) + watched flag / downloaded flag / name normalisation / sidecar / moviemeta INFO
#   for films and series / favourites.
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
from random import randint
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://www.dr.dk/drtv/'


class DRDK(GenericFolderWatchedScraperMixin, CBaseHostClass):
    API = 'https://production.dr-massive.com/api/'
    QUERY = 'device=web_browser&ff=idp%2Cldp%2Crpt&lang=da&sub=Anonymous&segments=drtv%2Coptedout'
    PAGE_SIZE = 40
    LIVE_LIST = '155156'            # "DR's kanaler" - the DR channels with a live stream
    CATEGORY_LISTS = ('376779', '509291')   # "Kategorier" of DRTV and of the "Gensyn" archive
    PLAYABLE = ('episode', 'program', 'event')
    SUB_LANGS = {'danish': 'da', 'foreign': 'da', 'english': 'en', 'german': 'de', 'swedish': 'sv', 'norwegian': 'no'}
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'item_id', 'item_type', 'path', 'list_id', 'title', 's_title', 'icon',
                  'desc', 'geo', 'live', 'meta_type', 'meta_title', 'meta_year', 'season', 'episode', 'page')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'drdk', 'cookie': 'drdk.cookie'})
        self.MAIN_URL = 'https://www.dr.dk/drtv'
        # the DR1 channel logo of the image service (the site's own icon files answer 403 to a plain download)
        self.DEFAULT_ICON_URL = "https://prod95-static.dr-massive.com/api/shain/v1/dataservice/ResizeImage/$value?Format='jpg'&Quality=85&EntityType='Item'&EntityId='20875'&Width=400&Height=400&ImageId='2344194'"
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Accept': 'application/json, text/plain, */*', 'Origin': 'https://www.dr.dk', 'Referer': 'https://www.dr.dk/'})
        self.defaultParams = {'header': self.HEADER}
        self.tokens = {}
        self.deviceId = ''
        self.watchedHelper = IPTVWatchedHelper('drdk')
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
            if cItem.get('category') in ('list_show', 'list_season'):
                return '%s:%s' % (cItem.get('item_type', 'show'), iid)
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

    def _api(self, path, query='', token=''):
        url = self.API + path + ('&' if '?' in path else '?') + self.QUERY
        if query:
            url += '&' + query
        params = dict(self.defaultParams)
        if token:
            params['header'] = dict(self.HEADER)
            params['header']['X-Authorization'] = 'Bearer ' + token
            params['ignore_http_code_ranges'] = [(400, 499)]
        sts, data = self.getPage(url, params)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _token(self, kind='UserAccount'):
        # anonymous session: "UserAccount" unlocks the stream list, "UserProfile" the search
        if not self.tokens:
            if not self.deviceId:
                self.deviceId = '%08x-%04x-4%03x-%04x-%012x' % (randint(0, 0xffffffff), randint(0, 0xffff), randint(0, 0xfff), randint(0x8000, 0xbfff), randint(0, 0xffffffffffff))
            params = dict(self.defaultParams)
            params['header'] = dict(self.HEADER)
            params['header']['Content-Type'] = 'application/json'
            params['raw_post_data'] = True
            url = self.API + 'authorization/anonymous-sso?device=web_browser&ff=idp%2Cldp%2Crpt&lang=da&supportFallbackToken=true'
            sts, data = self.getPage(url, params, json_dumps({'deviceId': self.deviceId, 'scopes': ['Catalog'], 'optout': True}))
            if sts:
                try:
                    for item in json_loads(data):
                        if isinstance(item, dict) and item.get('type') and item.get('value'):
                            self.tokens[item['type']] = item['value']
                except Exception:
                    printExc()
        return self.tokens.get(kind, '')

    @staticmethod
    def _img(item, key='tile'):
        images = item.get('images') or {}
        url = images.get(key) or images.get('tile') or images.get('wallpaper') or images.get('square') or images.get('logo') or ''
        if url:
            # the API hands out 1920x1080 PNGs (3 MB) - the same service also scales and delivers JPEG
            url = re.sub(r"Format='[a-z]+'", "Format='jpg'", url)
            if key == 'poster':
                url = re.sub(r'Width=\d+&Height=\d+', 'Width=400&Height=600', url)
            else:
                url = re.sub(r'Width=\d+&Height=\d+', 'Width=640&Height=360', url)
        return url

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
    def _isGeo(item):
        return str((item.get('customFields') or {}).get('IsGeoRestricted', '')).lower() == 'true'

    @staticmethod
    def _isFilm(item):
        cats = [str(x).lower() for x in (item.get('categories') or [])]
        display = str((item.get('customFields') or {}).get('DisplayCategory', '')).lower()
        return 'film' in cats or display == 'film'

    @staticmethod
    def _sxxexx(item, cItem):
        # season / episode numbers: the season context, else "S3:E1 ..." of the play button
        sNum = item.get('seasonNumber') or cItem.get('season') or ''
        eNum = item.get('episodeNumber') or ''
        match = re.search(r'S(\d+):E(\d+)', str((item.get('customFields') or {}).get('PlayButtonExtraDetails', '')))
        if match:
            sNum = sNum or match.group(1)
            eNum = eNum or match.group(2)
        return str(sNum or ''), str(eNum or '')

    def _showTitle(self, item, cItem):
        if cItem.get('s_title'):
            return cItem['s_title']
        page = str((item.get('customFields') or {}).get('PageTitle', ''))
        if ': Sæson' in page:
            return self.cleanHtmlStr(page.split(': Sæson', 1)[0])
        title = self.cleanHtmlStr(item.get('title') or '')
        return title.split(':', 1)[0].strip() if ':' in title else title

    def _desc(self, item, extra=''):
        parts = []
        if extra:
            parts.append(extra)
        if item.get('releaseYear'):
            parts.append(str(item['releaseYear']))
        dur = self._duration(item.get('duration'))
        if dur:
            parts.append(dur)
        details = str((item.get('customFields') or {}).get('ExtraDetails', '') or (item.get('customFields') or {}).get('ContextualTitleExtraDetails', ''))
        if details and not dur:
            parts.append(self.cleanHtmlStr(details))
        if self._isGeo(item):
            parts.append(_('Only available in %s') % _('Denmark'))
        head = ' | '.join(parts)
        text = self.cleanHtmlStr(item.get('shortDescription') or item.get('description') or '')
        return '[/br]'.join([x for x in (head, text) if x])

    def _addItem(self, cItem, item):
        try:
            if not isinstance(item, dict):
                return False
            itype = (item.get('type') or '').lower()
            iid = str(item.get('id') or '')
            title = self.cleanHtmlStr(item.get('title') or '')
            path = item.get('path') or ''
            if not iid or not title:
                return False
            params = {'name': 'category', 'good_for_fav': True, 'item_id': iid, 'item_type': itype, 'path': path,
                      'title': title, 'icon': self._img(item), 'desc': self._desc(item), 'url': self.MAIN_URL + path}
            if itype == 'channel':
                if not (item.get('customFields') or {}).get('hlsURL'):
                    return False
                params.update({'live': True, 'good_for_fav': True, 'desc': self.cleanHtmlStr(item.get('shortDescription') or '')})
                self.addVideo(params)
                return True
            if itype == 'link':
                if not path or path.startswith('/kanal/'):
                    return False
                params.update({'category': 'list_page', 'icon': self._img(item, 'square')})
                self.addDir(params)
                return True
            if itype == 'show':
                params.update({'category': 'list_show', 's_title': title, 'meta_type': 'tv', 'meta_title': title,
                               'meta_year': str(item.get('releaseYear') or '')})
                self.addDir(params)
                return True
            if itype == 'season':
                sTitle = self.cleanHtmlStr(item.get('showTitle') or '') or cItem.get('s_title') or title
                sNum = str(item.get('seasonNumber') or '')
                label = title
                if sNum and sNum not in title:
                    label = '%s - %s %s' % (title, _('Season'), sNum)
                params.update({'category': 'list_season', 'title': label, 's_title': sTitle, 'season': sNum,
                               # the show's year (first air date), not the season's
                               'meta_type': 'tv', 'meta_title': sTitle, 'meta_year': cItem.get('meta_year', '')})
                self.addDir(params)
                return True
            if itype not in self.PLAYABLE:
                return False
            params['geo'] = self._isGeo(item)
            if itype == 'episode':
                sNum, eNum = self._sxxexx(item, cItem)
                sTitle = self._showTitle(item, cItem)
                # contextualTitle = "1. episode" (nothing to add) or "1. Den første kæmpe" (the episode name)
                context = self.cleanHtmlStr(item.get('contextualTitle') or '')
                epName = re.sub(r'^\d+\.\s*', '', context)
                if not epName or epName.lower() == 'episode' or epName in title:
                    epName = ''
                if epName:
                    params['title'] = '%s - %s' % (title, epName)
                if sTitle and sNum and eNum:
                    params.update({'s_title': sTitle, 'season': sNum, 'episode': eNum})
                    if IsMediaNamingNormalized():
                        params['title'] = '%s - %s' % (sTitle, formatSxxExx(sNum, eNum))
                        name = epName or (title.split(':', 1)[1].strip() if title.startswith(sTitle + ':') else '')
                        if name:
                            params['title'] += ' - ' + name
            elif itype == 'program' and self._isFilm(item):
                year = str(item.get('releaseYear') or '')
                params.update({'meta_type': 'movie', 'meta_title': title, 'meta_year': year})
                if IsMediaNamingNormalized() and year:
                    params['title'] = '%s (%s)' % (title, year)
            self.addVideo(params)
            return True
        except Exception:
            printExc()
        return False

    def _addList(self, cItem, listObj, title=''):
        if not isinstance(listObj, dict) or not listObj.get('id'):
            return
        title = self.cleanHtmlStr(title or listObj.get('title') or '')
        if not title or not int(listObj.get('size', 0) or 0):
            return
        params = dict(cItem)
        params.update({'category': 'list_items', 'title': title, 'list_id': str(listObj['id']), 'page': 1, 'good_for_fav': True,
                       'icon': '', 'desc': ''})
        self.addDir(params)

    ###################################################
    # lists
    ###################################################
    def listPage(self, cItem):
        data = self._api('page', 'path=%s&max_list_prefetch=1&list_page_size=1&item_detail_expand=all' % urllib_quote_plus(cItem.get('path') or '/'))
        if not isinstance(data, dict):
            return
        seen = set()
        for entry in data.get('entries') or []:
            try:
                if not isinstance(entry, dict) or entry.get('type') not in ('ListEntry', 'ChannelListEntry'):
                    continue
                listObj = entry.get('list') or {}
                lid = str(listObj.get('id') or '')
                if not lid or lid in seen:
                    continue
                # the A-Z letter rows share one list id (the API cannot filter it) and the hero / text-link rows are no content
                lTitle = self.cleanHtmlStr(entry.get('title') or listObj.get('title') or '')
                if not lTitle or len(lTitle) == 1 or lTitle == '0-9' or 'text links' in lTitle.lower() or 'hero' in lTitle.lower():
                    continue
                seen.add(lid)
                self._addList(cItem, listObj, lTitle)
            except Exception:
                printExc()

    def _addPager(self, cItem, page, data, count, apiPath):
        # paging.total = number of pages; the list is read from list_id / item_id + page,
        # the url only carries the page for "Jump"
        try:
            total = int((data.get('paging') or {}).get('total', 0) or 0)
        except Exception:
            total = 0
        addPagingItems(self, cItem, page, bool(count) and page < total, total, self.API + apiPath + '#page={page}')

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get('page', 1) or 1))
        except Exception:
            return 1

    def listItems(self, cItem):
        page = self._page(cItem)
        apiPath = 'lists/%s' % cItem['list_id']
        data = self._api(apiPath, 'page=%d&page_size=%d' % (page, self.PAGE_SIZE))
        if not isinstance(data, dict):
            return
        count = 0
        for item in data.get('items') or []:
            if self._addItem(cItem, item):
                count += 1
        self._addPager(cItem, page, data, count, apiPath)

    def listCategories(self, cItem):
        seen = set()
        for lid in self.CATEGORY_LISTS:
            data = self._api('lists/%s' % lid, 'page=1&page_size=%d' % self.PAGE_SIZE)
            if not isinstance(data, dict):
                continue
            prefix = ''
            if lid != self.CATEGORY_LISTS[0]:
                prefix = self.cleanHtmlStr(data.get('title') or '')
                prefix = prefix.split(' ')[-1] + ': ' if prefix else ''
            for item in data.get('items') or []:
                path = (item or {}).get('path') or ''
                if path in seen or path.endswith('/a-aa'):
                    continue
                seen.add(path)
                params = dict(cItem)
                if prefix and item.get('title'):
                    item = dict(item)
                    item['title'] = prefix + item['title']
                self._addItem(params, item)

    def listLive(self, cItem):
        data = self._api('lists/%s' % self.LIVE_LIST, 'page=1&page_size=%d' % self.PAGE_SIZE)
        if not isinstance(data, dict):
            return
        channels = [item for item in (data.get('items') or []) if isinstance(item, dict) and item.get('id')]
        nowNext = self._nowNext([str(c['id']) for c in channels])
        for item in channels:
            if self._addItem(cItem, item) and str(item['id']) in nowNext:
                self.currList[-1]['desc'] = nowNext[str(item['id'])]

    def _nowNext(self, channelIds):
        ret = {}
        if not channelIds:
            return ret
        try:
            now = time.time()
            day = time.strftime('%Y-%m-%d', time.gmtime(now))
            data = self._api('schedules', 'channels=%s&date=%s&duration=24&hour=0&intersect=true' % (','.join(channelIds), day))
            for channel in data or []:
                lines = []
                for sched in (channel.get('schedules') or []):
                    try:
                        start = calendar.timegm(time.strptime(sched['startDate'][:19], '%Y-%m-%dT%H:%M:%S'))
                        end = calendar.timegm(time.strptime(sched['endDate'][:19], '%Y-%m-%dT%H:%M:%S'))
                    except Exception:
                        continue
                    title = self.cleanHtmlStr((sched.get('item') or {}).get('title') or '')
                    if not title:
                        continue
                    if start <= now < end:
                        lines.append('%s: %s (%s - %s)' % (_('Now'), title, time.strftime('%H:%M', time.localtime(start)), time.strftime('%H:%M', time.localtime(end))))
                    elif start >= now and len(lines) == 1:
                        lines.append('%s: %s (%s)' % (_('Next'), title, time.strftime('%H:%M', time.localtime(start))))
                        break
                if lines:
                    ret[str(channel.get('channelId'))] = '[/br]'.join(lines)
        except Exception:
            printExc()
        return ret

    def listShow(self, cItem):
        data = self._api('items/%s' % cItem['item_id'], 'expand=all')
        if not isinstance(data, dict):
            return
        seasons = [s for s in ((data.get('seasons') or {}).get('items') or []) if isinstance(s, dict) and s.get('id')]
        sTitle = self.cleanHtmlStr(data.get('title') or '') or cItem.get('s_title') or cItem.get('title', '')
        if len(seasons) == 1:
            # the season is listed in place of the show (its pager rows must list the season again)
            params = dict(cItem)
            params.update({'category': 'list_season', 'item_id': str(seasons[0]['id']), 'item_type': 'season', 's_title': sTitle,
                           'season': str(seasons[0].get('seasonNumber') or '')})
            self.listSeason(params)
            return
        for season in seasons:
            season = dict(season)
            season['showTitle'] = sTitle
            params = dict(cItem)
            params['s_title'] = sTitle
            self._addItem(params, season)

    def listSeason(self, cItem):
        page = self._page(cItem)
        apiPath = 'items/%s/children' % cItem['item_id']
        data = self._api(apiPath, 'page=%d&page_size=100' % page)
        if not isinstance(data, dict):
            return
        count = 0
        for item in data.get('items') or []:
            if self._addItem(cItem, item):
                count += 1
        self._addPager(cItem, page, data, count, apiPath)

    def listSearchResult(self, cItem, searchPattern, searchType):
        token = self._token('UserProfile')
        if not token:
            SetIPTVPlayerLastHostError(_('Get token failed!'))
            return
        data = self._api('search', 'term=%s&group=true&max_rating=&page_size=%d' % (urllib_quote_plus(searchPattern), self.PAGE_SIZE), token)
        if not isinstance(data, dict):
            return
        if data.get('message') and not data.get('total'):
            SetIPTVPlayerLastHostError('DR TV: %s' % self.cleanHtmlStr(data['message']))
            return
        for group in ('series', 'movies', 'playable', 'tv'):
            for item in ((data.get(group) or {}).get('items') or []):
                self._addItem(cItem, item)

    ###################################################
    # links
    ###################################################
    def _streamList(self, iid):
        token = self._token('UserAccount')
        if not token:
            return None
        return self._api('account/items/%s/videos' % iid, 'delivery=stream&resolution=HD-1080', token)

    def getLinksForVideo(self, cItem):
        printDBG('DRDK.getLinksForVideo [%s]' % cItem.get('item_id', ''))
        iid = cItem.get('item_id', '')
        if not iid:
            return []
        meta = {'User-Agent': self.HEADER['User-Agent'], 'Referer': 'https://www.dr.dk/', 'Origin': 'https://www.dr.dk', 'iptv_proto': 'm3u8'}
        urlTab = []
        geo = bool(cItem.get('geo'))

        if cItem.get('live'):
            item = self._api('items/%s' % iid)
            fields = (item or {}).get('customFields') or {}
            for key, name in (('hlsURL', 'HLS'), ('hlsWithSubtitlesURL', _('HLS with subtitles'))):
                url = fields.get(key) or ''
                if not self.cm.isValidUrl(url):
                    continue
                links = getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
                for link in links:
                    link['need_resolve'] = 0
                    link['name'] = '%s %s' % (name, link.get('name', ''))
                    urlTab.append(link)
            if not urlTab:
                SetIPTVPlayerLastHostError(_('This content is not available in your region.'))
            return urlTab

        data = self._streamList(iid)
        if isinstance(data, dict):
            # {"code": 8009, "message": "Ingen filer"} - nothing playable (for us)
            data = []
        if not isinstance(data, list):
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        drm = False
        subTracks = []
        hls = []
        for video in data:
            if not isinstance(video, dict) or not video.get('url'):
                continue
            if str(video.get('drm') or 'None') != 'None':
                drm = True
                continue
            if 'hls' not in str(video.get('format') or '').lower():
                continue
            hls.append(video)
        # the plain picture first, then audio description / spoken subtitles
        hls.sort(key=lambda v: 0 if v.get('accessService') == 'StandardVideo' else 1)
        for video in hls:
            for sub in (video.get('subtitles') or []):
                link = sub.get('link') or ''
                if not self.cm.isValidUrl(link) or any(t['url'] == link for t in subTracks):
                    continue
                lang = str(sub.get('language') or '').lower()
                code = 'da'
                for key, val in self.SUB_LANGS.items():
                    if lang.startswith(key):
                        code = val
                        break
                label = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', str(sub.get('language') or 'Subtitles'))
                subTracks.append({'title': label, 'url': link, 'lang': code, 'format': 'vtt'})
        for video in hls:
            service = str(video.get('accessService') or 'StandardVideo')
            label = {'StandardVideo': '', 'AudioDescription': _('Audio description'), 'SpokenSubtitles': _('Spoken subtitles')}.get(service, service)
            linkMeta = dict(meta)
            if subTracks:
                linkMeta['external_sub_tracks'] = subTracks
            links = getDirectM3U8Playlist(strwithmeta(video['url'], linkMeta), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
            for link in links:
                link['need_resolve'] = 0
                if label:
                    link['name'] = '%s %s' % (label, link.get('name', ''))
                urlTab.append(link)
            if not links and not geo and not urlTab:
                # the playlist could not be read - leave the master playlist to the player
                urlTab.append({'name': label or 'HLS', 'url': strwithmeta(video['url'], linkMeta), 'need_resolve': 0})
        if not urlTab:
            if hls and geo:
                SetIPTVPlayerLastHostError(_('This content is not available in your region.'))
            elif drm:
                SetIPTVPlayerLastHostError(_('Video with DRM protection.'))
            else:
                SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(cItem.get('desc', '')).split('[/br]')[-1]))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG('DRDK.getArticleContent [%s]' % cItem.get('item_id', ''))
        item = self._api('items/%s' % cItem['item_id']) if cItem.get('item_id') else None
        if not isinstance(item, dict):
            item = {}
        fields = item.get('customFields') or {}
        otherInfo = {}
        if item.get('releaseYear'):
            otherInfo['year'] = str(item['releaseYear'])
        dur = self._duration(item.get('duration'))
        if dur:
            otherInfo['duration'] = dur
        if fields.get('ProductionCountry'):
            otherInfo['country'] = self.cleanHtmlStr(str(fields['ProductionCountry'])).title()
        cats = self.cleanHtmlStr(str(fields.get('DisplayCategory') or ''))
        if cats:
            otherInfo['categories'] = cats.replace(',', ', ')
        rating = (item.get('classification') or {}).get('name')
        if rating:
            otherInfo['rated'] = self.cleanHtmlStr(rating)
        if item.get('type') == 'show' and (item.get('availableSeasonCount') or item.get('seasons')):
            otherInfo['seasons'] = str(item.get('availableSeasonCount') or (item.get('seasons') or {}).get('size') or '')
        if item.get('type') == 'season' and item.get('availableEpisodeCount'):
            otherInfo['episodes'] = str(item['availableEpisodeCount'])
        credits = {}
        for credit in (item.get('credits') or []):
            if isinstance(credit, dict) and credit.get('name'):
                credits.setdefault(str(credit.get('role') or '').lower(), []).append(self.cleanHtmlStr(credit['name']))
        for role, field in (('director', 'director'), ('actor', 'actors'), ('writer', 'writers')):
            if credits.get(role):
                otherInfo[field] = ', '.join(credits[role][:8])
        text = self.cleanHtmlStr(item.get('description') or item.get('shortDescription') or '') or self.cleanHtmlStr(cItem.get('desc', '')).split('[/br]')[-1]
        # the text carries the cast / director lines of DR itself
        match = re.search(r'(?:Medvirkende|Medv\.):\s*([^\n]+)', text)
        if match and 'actors' not in otherInfo:
            otherInfo['actors'] = match.group(1).strip().rstrip('.').replace(' m.fl', '')
        match = re.search(r'Instrukt\S*:\s*([^\n.]+)', text)
        if match and 'director' not in otherInfo:
            otherInfo['director'] = match.group(1).strip()
        icon = self._img(item, 'poster') or cItem.get('icon', '')
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
        return [{'title': cItem.get('title', ''), 'text': text.replace('\n', '[/br]'),
                 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('item_id') or cItem.get('list_id') or cItem.get('path'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('DRDK.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        printDBG('DRDK.handleService: name[%s] category[%s]' % (name, category))
        self.currList = []

        if name is None:
            tab = [{'category': 'list_live', 'title': _('Live channels')},
                   {'category': 'list_page', 'title': _('Home page'), 'path': '/'},
                   {'category': 'list_cats', 'title': _('Categories')},
                   {'category': 'list_page', 'title': 'Gensyn (%s)' % _('Archive'), 'path': '/gensyn'}] + self.searchItems()
            self.listsTab(tab, {'name': 'category'})
        elif category == 'list_live':
            self.listLive(self.currItem)
        elif category == 'list_page':
            self.listPage(self.currItem)
        elif category == 'list_cats':
            self.listCategories(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'list_show':
            self.listShow(self.currItem)
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
        CHostBase.__init__(self, DRDK(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('drdk')

    def withArticleContent(self, cItem):
        return bool(cItem.get('item_id')) and not cItem.get('live') and cItem.get('item_type') != 'link'
