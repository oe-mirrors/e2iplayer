# -*- coding: utf-8 -*-
LAST_MODIFIED = "25.10.2026"
# Rakuten TV - free live channels (FAST) of the country the box is in (or the one set in the host config):
# site categories with now / next, all channels, local search. JSON API of the web app (gizmo.rakuten.tv), plain HLS.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
# FOREIGN import
###################################################
import re
import time
import calendar
import uuid
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################

# market code: (classification id, locale, default audio language, name) - read from /v3/me/start of every market
MARKETS = [('de', '307', 'de', 'DEU', 'Germany'), ('at', '300', 'de-AT', 'DEU', 'Austria'), ('ch', '319', 'de-CH', 'DEU', 'Switzerland'),
           ('uk', '18', 'en', 'ENG', 'United Kingdom'), ('ie', '41', 'en-IE', 'ENG', 'Ireland'), ('fr', '23', 'fr', 'FRA', 'France'),
           ('be', '308', 'fr-BE', 'FRA', 'Belgium'), ('lu', '74', 'fr-LU', 'FRA', 'Luxembourg'), ('nl', '323', 'nl', 'NLD', 'Netherlands'),
           ('es', '5', 'es', 'SPA', 'Spain'), ('pt', '64', 'pt', 'POR', 'Portugal'), ('it', '36', 'it', 'ITA', 'Italy'),
           ('pl', '277', 'pl', 'POL', 'Poland'), ('cz', '272', 'cs', 'CES', 'Czechia'), ('sk', '273', 'en-SK', 'ENG', 'Slovakia'),
           ('hu', '274', 'hu', 'HUN', 'Hungary'), ('ro', '268', 'ro', 'RON', 'Romania'), ('bg', '269', 'bg', 'BUL', 'Bulgaria'),
           ('hr', '302', 'en-HR', 'ENG', 'Croatia'), ('si', '271', 'en-SI', 'ENG', 'Slovenia'), ('rs', '266', 'en-RS', 'ENG', 'Serbia'),
           ('ba', '245', 'en-BA', 'ENG', 'Bosnia and Herzegovina'), ('me', '259', 'en-ME', 'ENG', 'Montenegro'),
           ('mk', '275', 'en-MK', 'ENG', 'North Macedonia'), ('al', '270', 'en-AL', 'ENG', 'Albania'), ('gr', '279', 'en-GR', 'ENG', 'Greece'),
           ('cy', '281', 'en-CY', 'ENG', 'Cyprus'), ('mt', '278', 'en-MT', 'ENG', 'Malta'), ('ua', '276', 'uk', 'UKR', 'Ukraine'),
           ('se', '282', 'sv', 'SWE', 'Sweden'), ('dk', '283', 'da', 'DAN', 'Denmark'), ('no', '286', 'nb', 'NOR', 'Norway'),
           ('fi', '284', 'fi', 'FIN', 'Finland'), ('is', '287', 'en-IS', 'ENG', 'Iceland'), ('ee', '288', 'en-EE', 'ENG', 'Estonia'),
           ('lv', '289', 'en-LV', 'ENG', 'Latvia'), ('lt', '290', 'en-LT', 'ENG', 'Lithuania')]

config.plugins.iptvplayer.rakutentv_market = ConfigSelection(default='auto', choices=[('auto', _('Auto'))] + [(m[0], '%s (%s)' % (m[4], m[0])) for m in MARKETS])


def GetConfigList():
    return [getConfigListEntry(_('Country:'), config.plugins.iptvplayer.rakutentv_market)]


def gettytul():
    return 'https://www.rakuten.tv/'


class RakutenTV(CBaseHostClass):
    API = 'https://gizmo.rakuten.tv/v3'
    SITE = 'https://www.rakuten.tv'
    PAGE_SIZE = 50
    CACHE_TIME = 900            # channel list (with the programme of this and the next hour) is kept 15 minutes
    FAV_FIELDS = ('name', 'category', 'type', 'title', 'icon', 'desc', 'url', 'cat_id', 'channel_id', 'langs', 'live')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'rakutentv', 'cookie': 'rakutentv.cookie'})
        self.MAIN_URL = self.SITE + '/'
        self.DEFAULT_ICON_URL = 'https://images-2.rakuten.tv/storage/market/logo_png/80275a7c-9dde-4330-a419-7a5fa57469c2-germany-1543577968.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Accept': 'application/json, text/plain, */*', 'Origin': self.SITE, 'Referer': self.SITE + '/'})
        self.defaultParams = {'header': self.HEADER}
        self.uid = str(uuid.uuid4())
        self.geoMarket = None
        self.emptyAnswer = False
        self.cache = {}

    ###################################################
    # market / API
    ###################################################
    def _detectMarket(self):
        # /v3/me/start without market_code answers with the market of the IP (code, locale, classification)
        if self.geoMarket is not None:
            return self.geoMarket
        body = {'device_identifier': 'web', 'ifa_id': '',
                'device_metadata': {'app_version': 'v5.5.22', 'audio_quality': '2.0', 'brand': 'chrome', 'firmware': 'XX.XX.XX', 'hdr': False,
                                    'model': 'GENERIC', 'os': 'Windows', 'sdk': '130.0.0', 'serial_number': 'not implemented',
                                    'trusted_uid': False, 'uid': self.uid, 'video_quality': 'FHD', 'year': 1970}}
        data = self._api('/me/start?device_identifier=web', body)
        market = {}
        try:
            data = data['data']
            profile = data['user']['profile']
            code = str(data['market']['code'])
            market = {'code': code, 'classification': str(profile['classification']['id']), 'locale': str(data['market'].get('locale') or code),
                      'audio': str((data['market'].get('default_audio_language') or {}).get('id') or 'ENG')}
        except Exception:
            printDBG('RakutenTV._detectMarket failed: %s' % str(data)[:300])
        self.geoMarket = market
        return market

    def _market(self):
        code = config.plugins.iptvplayer.rakutentv_market.value
        if code == 'auto':
            market = self._detectMarket()
            if market:
                return market
            code = 'de'
        for m in MARKETS:
            if m[0] == code:
                return {'code': m[0], 'classification': m[1], 'locale': m[2], 'audio': m[3]}
        return {'code': 'de', 'classification': '307', 'locale': 'de', 'audio': 'DEU'}

    @staticmethod
    def _query(market):
        return 'classification_id=%s&device_identifier=web&locale=%s&market_code=%s' % (market['classification'], market['locale'], market['code'])

    def _api(self, path, post=None):
        params = dict(self.defaultParams)
        params['header'] = dict(self.HEADER)
        params['ignore_http_code_ranges'] = [(400, 499)]
        if post is None:
            sts, data = self.cm.getPage(self.API + path, params)
        else:
            params['header']['Content-Type'] = 'application/json'
            params['raw_post_data'] = True
            sts, data = self.cm.getPage(self.API + path, params, json_dumps(post))
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    @staticmethod
    def _errorCode(data):
        try:
            return str(data['errors'][0].get('code') or '')
        except Exception:
            return ''

    def _channels(self):
        market = self._market()
        # the guide window must start / end on full hours (cached by the API, other values are refused)
        hour = int(time.time()) // 3600 * 3600
        key = 'channels_%s_%d' % (market['code'], hour)
        entry = self.cache.get(key)
        if entry and time.time() - entry[0] < self.CACHE_TIME:
            return entry[1]
        epg = '&epg_starts_at=%s&epg_ends_at=%s' % (time.strftime('%Y-%m-%dT%H:00:00.000Z', time.gmtime(hour)),
                                                    time.strftime('%Y-%m-%dT%H:00:00.000Z', time.gmtime(hour + 7200)))
        channels = []
        self.emptyAnswer = False
        page = 1
        while page <= 10:
            path = '/live_channels?%s&per_page=%d&page=%d' % (self._query(market), self.PAGE_SIZE, page)
            data = self._api(path + epg)
            if epg and not (isinstance(data, dict) and isinstance(data.get('data'), list)):
                # no guide: the channels without it
                epg = ''
                data = self._api(path)
            if not isinstance(data, dict) or not isinstance(data.get('data'), list):
                break
            channels.extend([c for c in data['data'] if isinstance(c, dict) and c.get('id')])
            try:
                lastPage = int(((data.get('meta') or {}).get('pagination') or {}).get('total_pages') or 1)
            except Exception:
                lastPage = 1
            if not data['data'] and page == 1:
                # a valid answer without channels: no live channels in this market
                self.emptyAnswer = True
            if page >= lastPage or not data['data']:
                break
            page += 1
        if channels:
            for old in [k for k in self.cache if k.startswith('channels_')]:
                del self.cache[old]
            self.cache[key] = (time.time(), channels)
        return channels

    def _categories(self):
        market = self._market()
        key = 'cats_%s' % market['code']
        entry = self.cache.get(key)
        if entry and time.time() - entry[0] < self.CACHE_TIME * 4:
            return entry[1]
        data = self._api('/live_channel_categories?%s' % self._query(market))
        cats = [c for c in ((data or {}).get('data') or []) if isinstance(c, dict) and c.get('id') and c.get('live_channels')]
        if cats:
            self.cache[key] = (time.time(), cats)
        return cats

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _parseTime(value):
        # "2026-10-25T20:15:00.000+01:00"
        try:
            value = str(value)
            ts = calendar.timegm(time.strptime(value[:19], '%Y-%m-%dT%H:%M:%S'))
            match = re.search(r'([+-])(\d\d):?(\d\d)$', value)
            if match:
                offset = int(match.group(2)) * 3600 + int(match.group(3)) * 60
                ts = ts - offset if match.group(1) == '+' else ts + offset
            return ts
        except Exception:
            return 0

    def _nowNext(self, channel):
        current = nextLine = None
        now = time.time()
        progs = []
        for prog in channel.get('live_programs') or []:
            if isinstance(prog, dict):
                begin, end = self._parseTime(prog.get('starts_at')), self._parseTime(prog.get('ends_at'))
                title = self.cleanHtmlStr(prog.get('title') or '')
                if title and begin and end > now:
                    progs.append((begin, end, title, prog))
        for begin, end, title, prog in sorted(progs, key=lambda x: x[0]):
            if begin <= now and current is None:
                current = ['%s: %s (%s - %s)' % (_('Now'), title, time.strftime('%H:%M', time.localtime(begin)), time.strftime('%H:%M', time.localtime(end)))]
                text = self.cleanHtmlStr(prog.get('description') or '')
                if text:
                    current.append(text)
            elif begin > now:
                # also without a current programme (a gap in the guide)
                nextLine = '%s: %s (%s)' % (_('Next'), title, time.strftime('%H:%M', time.localtime(begin)))
                break
        lines = list(current or [])
        if nextLine:
            lines.insert(1 if current else 0, nextLine)
        return lines

    @staticmethod
    def _channelNumber(channel):
        try:
            return int(channel.get('channel_number') or 0)
        except Exception:
            return 0

    def _addChannel(self, channel):
        title = self.cleanHtmlStr(channel.get('title') or '')
        if not title:
            return
        labels = channel.get('labels') or {}
        langs = [str(x['id']) for x in labels.get('languages') or [] if isinstance(x, dict) and x.get('id')]
        info = []
        if self._channelNumber(channel):
            info.append(str(self._channelNumber(channel)))
        info.extend([self.cleanHtmlStr(x.get('name') or '') for x in labels.get('tags') or [] if isinstance(x, dict) and x.get('name')])
        info.extend([self.cleanHtmlStr(x.get('name') or '') for x in labels.get('languages') or [] if isinstance(x, dict) and x.get('name')])
        rating = self.cleanHtmlStr((channel.get('classification') or {}).get('name') or '')
        if rating:
            info.append(rating)
        images = channel.get('images') or {}
        desc = self._nowNext(channel) + [' | '.join([x for x in info if x])]
        self.addVideo({'name': 'category', 'good_for_fav': True, 'live': True, 'title': title, 'channel_id': channel['id'], 'langs': langs,
                       'url': '%s/%s/live_channels/%s' % (self.SITE, self._market()['code'], channel['id']),
                       'icon': images.get('artwork') or images.get('artwork_negative') or images.get('snapshot') or '',
                       'desc': '[/br]'.join([x for x in desc if x])})

    def _setEmptyError(self):
        # an empty catalogue (a failed request is no geo-blocking)
        if self.emptyAnswer:
            SetIPTVPlayerLastHostError(_('Not available in your country (geo-blocking).') + ' [%s]' % self._market()['code'])

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get('page', 1) or 1))
        except Exception:
            return 1

    ###################################################
    # lists
    ###################################################
    def listMain(self, cItem):
        for cat in self._categories():
            title = self.cleanHtmlStr(cat.get('name') or '')
            if title:
                self.addDir({'name': 'category', 'category': 'list_live', 'title': title, 'cat_id': str(cat['id']), 'good_for_fav': True,
                             'icon': cat.get('icon_img') or '', 'desc': ''})
        self.addDir({'name': 'category', 'category': 'list_live', 'title': _('All stations'), 'cat_id': '', 'good_for_fav': True, 'desc': ''})
        self.listsTab(self.searchItems(), {'name': 'category'})

    def listLive(self, cItem):
        channels = self._channels()
        if not channels:
            self._setEmptyError()
            return
        catId = cItem.get('cat_id', '')
        if catId:
            ids = []
            for cat in self._categories():
                if str(cat.get('id')) == catId:
                    ids = [str(x) for x in cat.get('live_channels') or []]
                    break
            byId = dict((c['id'], c) for c in channels)
            channels = [byId[x] for x in ids if x in byId]
        else:
            channels = sorted(channels, key=self._channelNumber)
        page = self._page(cItem)
        lastPage = max(1, (len(channels) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        if len(channels) > self.PAGE_SIZE:
            channels = channels[(page - 1) * self.PAGE_SIZE:page * self.PAGE_SIZE]
        else:
            page = lastPage = 1
        for channel in channels:
            self._addChannel(channel)
        if lastPage > 1:
            addPagingItems(self, dict(cItem, desc=''), page, page < lastPage, lastPage, self.SITE + '/live')

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = searchPattern.strip().lower()
        if not pattern:
            return
        for channel in sorted(self._channels(), key=self._channelNumber):
            tags = ' '.join([self.cleanHtmlStr(x.get('name') or '') for x in (channel.get('labels') or {}).get('tags') or [] if isinstance(x, dict)])
            if pattern in (self.cleanHtmlStr(channel.get('title') or '') + ' ' + tags).lower():
                self._addChannel(channel)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG('RakutenTV.getLinksForVideo [%s]' % cItem.get('channel_id', ''))
        channelId = cItem.get('channel_id', '')
        if not channelId:
            return []
        market = self._market()
        query = '%s&device_stream_audio_quality=2.0&device_stream_hdr_type=NONE&device_stream_video_quality=FHD&disable_dash_legacy_packages=false' % self._query(market)
        # the audio language must be one of the channel's languages (else "invalid subtitle_language")
        langs = []
        for lang in list(cItem.get('langs') or []) + [market['audio'], 'ENG']:
            if lang and lang not in langs:
                langs.append(lang)
        url = ''
        for lang in langs:
            body = {'audio_language': lang, 'audio_quality': '2.0', 'classification_id': int(market['classification']), 'content_id': channelId,
                    'content_type': 'live_channels', 'device_serial': 'not implemented', 'player': 'web:HLS-NONE:NONE',
                    'strict_video_quality': False, 'subtitle_language': 'MIS', 'video_type': 'stream'}
            data = self._api('/avod/streamings?%s' % query, body)
            try:
                url = data['data']['stream_infos'][0]['url']
            except Exception:
                url = ''
            if url:
                break
            code = self._errorCode(data)
            printDBG('RakutenTV.getLinksForVideo [%s] error[%s]' % (lang, code))
            if 'geo_market' in code:
                SetIPTVPlayerLastHostError(_('This channel is not available in your country (geo-blocking).'))
                return []
            if 'language' not in code:
                break
        if not url:
            SetIPTVPlayerLastHostError(_('No stream available'))
            return []
        meta = {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.SITE + '/', 'Origin': self.SITE, 'iptv_proto': 'm3u8', 'iptv_livestream': True}
        urlTab = []
        for link in getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999):
            link['need_resolve'] = 0
            urlTab.append(link)
        if not urlTab:
            urlTab = [{'name': 'HLS', 'url': strwithmeta(url, meta), 'need_resolve': 0}]
        return urlTab

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        icon = cItem.get('icon', '')
        return [{'title': cItem.get('title', ''), 'text': cItem.get('desc', ''), 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': {}}]

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('RakutenTV.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', None)
        category = self.currItem.get('category', '')
        printDBG('RakutenTV.handleService: name[%s] category[%s]' % (name, category))
        self.currList = []

        if name is None:
            self.listMain(self.currItem)
        elif category == 'list_live':
            self.listLive(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _('Type: '))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, RakutenTV(), True, [])

    def withArticleContent(self, cItem):
        return bool(cItem.get('channel_id'))
