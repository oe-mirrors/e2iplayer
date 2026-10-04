# -*- coding: utf-8 -*-
# VAVOO.TO: IPTV live channels per country (logic of the Kodi "vavoo" addon).
# - signature: POST www.vavoo.tv/api/app/ping (anonymous app ping) -> addonSig, valid ~15 min
# - channel lists: POST vavoo.to/mediahubmx-catalog.json (filter group = country, paged by cursor)
# - play: POST vavoo.to/mediahubmx-resolve.json with the channel url -> HLS url
# The same channel comes in several variants (".b", ".c", ".s" sources, HD/HD+/backup): one row per channel,
# the variants are its links. Live TV only: no watched flag, no movie metadata.
# Last Modified: 03.10.2026
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from datetime import datetime
import random
import re
import time
###################################################


def GetConfigList():
    return []


def gettytul():
    return 'https://vavoo.to/'


class VavooTo(CBaseHostClass):

    PING_URL = 'https://www.vavoo.tv/api/app/ping'
    CATALOG_URL = 'https://vavoo.to/mediahubmx-catalog.json'
    RESOLVE_URL = 'https://vavoo.to/mediahubmx-resolve.json'
    API_UA = 'okhttp/4.11.0'
    STREAM_UA = 'VAVOO/2.6'
    CLIENT_VERSION = '3.0.2'
    APP_VERSION = '3.1.20'
    CACHE_TIME = 600
    LETTER_LIMIT = 150
    FALLBACK_GROUPS = ['Albania', 'Arabia', 'Balkans', 'Bulgaria', 'Croatia', 'France', 'Germany', 'Italy', 'Netherlands',
                       'Poland', 'Portugal', 'Romania', 'Russia', 'Spain', 'Turkey', 'United Kingdom']
    # variant markers that do not make a different channel
    VARIANT_RE = re.compile(r'\s*(\(BACK ?UP[^)]*\)|\bF?HD\+?|\bUHD\b|\bRAW\b|\bHEVC\b|\b(?:1080|720)P?\b|\[[^\]]*\])', re.I)
    SOURCE_RE = re.compile(r'\s+\.([a-z0-9])$', re.I)
    FAV_FIELDS = ('name', 'category', 'type', 'title', 'group', 'links', 'icon', 'url')

    def __init__(self):
        printDBG("VavooTo.__init__")
        CBaseHostClass.__init__(self, {'history': 'VavooTo', 'cookie': 'vavooto.cookie'})
        self.MAIN_URL = 'https://vavoo.to/'
        self.DEFAULT_ICON_URL = 'https://www.vavoo.tv/assets/wt1/img/logo-text-vavoo.png'
        self.sig = ''
        self.sigValidUntil = 0
        self.groups = []
        self.cache = {}
        self.deviceId = '%016x' % random.getrandbits(64)

    ###################################################
    # API
    ###################################################
    def _post(self, url, body, withSig=True):
        header = {'User-Agent': self.API_UA, 'Accept': 'application/json', 'Content-Type': 'application/json; charset=utf-8'}
        if withSig:
            sig = self._getSignature()
            if not sig:
                return None
            header['mediahubmx-signature'] = sig
        sts, data = self.cm.getPage(url, {'header': header, 'raw_post_data': True}, json_dumps(body))
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG('VavooTo._post: no JSON from %s' % url)
        return None

    def _getSignature(self):
        now = time.time()
        if self.sig and now < self.sigValidUntil - 30:
            return self.sig
        ts = int(now * 1000)
        body = {
            'token': '', 'reason': 'app-blur', 'locale': 'de', 'theme': 'dark',
            'metadata': {
                'device': {'type': 'Handset', 'brand': 'google', 'model': 'Nexus', 'name': 'Nexus', 'uniqueId': self.deviceId},
                'os': {'name': 'android', 'version': '7.1.2', 'abis': ['arm64-v8a', 'armeabi-v7a', 'armeabi'], 'host': 'android'},
                'app': {'platform': 'android', 'version': self.APP_VERSION, 'buildId': '289515000', 'engine': 'hbc85',
                        'signatures': [], 'installer': 'com.android.vending'},
                'version': {'package': 'tv.vavoo.app', 'binary': self.APP_VERSION, 'js': self.APP_VERSION},
            },
            'appFocusTime': 0, 'playerActive': False, 'playDuration': 0, 'devMode': False, 'hasAddon': True, 'castConnected': False,
            'package': 'tv.vavoo.app', 'version': self.APP_VERSION, 'process': 'app', 'firstAppStart': ts, 'lastAppStart': ts,
            'ipLocation': '', 'adblockEnabled': True,
            'proxy': {'supported': ['ss', 'openvpn'], 'engine': 'ss', 'ssVersion': 1, 'enabled': True, 'autoServer': True, 'id': 'pl-waw'},
            'iap': {'supported': False},
        }
        data = self._post(self.PING_URL, body, withSig=False)
        sig = (data or {}).get('addonSig') if isinstance(data, dict) else ''
        if not sig:
            printDBG('VavooTo._getSignature: no addonSig')
            SetIPTVPlayerLastHostError(_('VAVOO did not hand out a session signature. Try again later.'))
            return ''
        validUntil = now + 600
        try:
            # addonSig = base64(JSON {"data": "<JSON with validUntil in ms>", "signature": ...})
            info = json_loads(json_loads(b64Decode(sig))['data'])
            if info.get('validUntil'):
                validUntil = min(validUntil + 1800, float(info['validUntil']) / 1000.0)
        except Exception:
            printDBG('VavooTo._getSignature: validUntil not readable')
        self.sig = sig
        self.sigValidUntil = validUntil
        return sig

    def _catalogBody(self, group, search='', cursor=0):
        return {'language': 'de', 'region': 'AT', 'catalogId': 'iptv', 'id': 'iptv', 'adult': False, 'search': search,
                'sort': 'name', 'filter': {'group': group}, 'cursor': cursor, 'clientVersion': self.CLIENT_VERSION}

    def _fetchGroup(self, group, search=''):
        key = (group, search)
        hit = self.cache.get(key)
        if hit and time.time() - hit[0] < self.CACHE_TIME:
            return hit[1]
        items = []
        cursor = 0
        for _i in range(20):
            data = self._post(self.CATALOG_URL, self._catalogBody(group, search, cursor))
            if not isinstance(data, dict):
                break
            if not self.groups:
                try:
                    for flt in ((data.get('features') or {}).get('filter') or []):
                        if flt.get('id') == 'group':
                            self.groups = [g for g in (flt.get('values') or []) if g]
                except Exception:
                    printExc()
            items.extend([it for it in (data.get('items') or []) if isinstance(it, dict) and it.get('url')])
            cursor = data.get('nextCursor')
            if cursor in (None, '', 0):
                break
        channels = self._groupChannels(items)
        if items:
            self.cache[key] = (time.time(), channels)
        return channels

    def _channelKey(self, name):
        key = self.SOURCE_RE.sub('', name)
        key = self.VARIANT_RE.sub(' ', key)
        return re.sub(r'\s+', ' ', key).strip(' -|').upper()

    def _groupChannels(self, items):
        order = []
        byKey = {}
        for it in items:
            name = ensure_str(it.get('name') or '').strip()
            if not name:
                continue
            title = self._channelKey(name) or name.upper()
            # the search runs over all countries: the same name in two countries stays two channels
            key = (it.get('group') or '', title)
            ch = byKey.get(key)
            if ch is None:
                ch = {'title': title, 'group': it.get('group') or '', 'icon': '', 'links': [], 'epg': []}
                byKey[key] = ch
                order.append(key)
            m = self.SOURCE_RE.search(name)
            label = self.SOURCE_RE.sub('', name).strip()
            if m:
                label += ' (%s)' % m.group(1)
            ch['links'].append({'name': label, 'url': it['url']})
            # the catalog's channel logos (logo.huhu.to) are broken (TLS alert on https, empty body on http):
            # no icon instead of 200+ failing downloads per list
            if not ch['epg'] and it.get('epg'):
                ch['epg'] = it['epg']
        return [byKey[k] for k in order]

    def _epgDesc(self, epg):
        now = time.time()
        lines = []
        try:
            for e in epg:
                start, stop = float(e.get('start') or 0), float(e.get('stop') or 0)
                if stop and stop < now:
                    continue
                label = _('Now') if start <= now else _('Next')
                lines.append('%s %s - %s: %s' % (label, datetime.fromtimestamp(start).strftime('%H:%M'),
                                                  datetime.fromtimestamp(stop).strftime('%H:%M'), self.cleanHtmlStr(e.get('name') or '')))
                if len(lines) >= 2:
                    break
        except Exception:
            printExc()
        return '[/br]'.join(lines)

    def _addChannel(self, cItem, ch):
        desc = self._epgDesc(ch.get('epg') or [])
        info = '%s | %d %s' % (ch['group'], len(ch['links']), _('sources'))
        params = {'name': 'category', 'category': 'play', 'title': ch['title'], 'group': ch['group'],
                  'links': ch['links'], 'icon': ch['icon'], 'live': True, 'good_for_fav': True,
                  'url': ch['links'][0]['url'], 'desc': info + ('[/br]' + desc if desc else '')}
        self.addVideo(params)

    ###################################################
    # lists
    ###################################################
    def listGroups(self, cItem):
        if not self.groups:
            self._fetchGroup('Germany')
        groups = self.groups or list(self.FALLBACK_GROUPS)
        # the default country first, the rest alphabetical
        groups = sorted(groups, key=lambda g: (g != 'Germany', g))
        for g in groups:
            params = dict(cItem)
            params.update({'category': 'list_group', 'title': g, 'group': g, 'good_for_fav': True})
            self.addDir(params)

    def listGroup(self, cItem):
        channels = self._fetchGroup(cItem['group'])
        if not channels:
            if not self.currList:
                SetIPTVPlayerLastHostError(_('No matching entries found.'))
            return
        if len(channels) <= self.LETTER_LIMIT or cItem.get('letter'):
            letter = cItem.get('letter', '')
            for ch in channels:
                if not letter or self._letterOf(ch['title']) == letter:
                    self._addChannel(cItem, ch)
            return
        counts = {}
        for ch in channels:
            lt = self._letterOf(ch['title'])
            counts[lt] = counts.get(lt, 0) + 1
        for lt in sorted(counts, key=lambda x: (x == '#', x)):
            params = dict(cItem)
            params.update({'category': 'list_letter', 'title': '%s (%d)' % (lt, counts[lt]), 'letter': lt, 'good_for_fav': True})
            self.addDir(params)

    @staticmethod
    def _letterOf(title):
        c = title[:1].upper()
        if 'A' <= c <= 'Z':
            return c
        return '#'

    def listSearch(self, cItem, searchPattern, searchType):
        pattern = searchPattern.strip()
        if not pattern:
            return
        # an empty group filter searches all countries in one (cursor paged) list; Germany first
        channels = sorted(self._fetchGroup('', pattern), key=lambda ch: (ch['group'] != 'Germany', ch['group']))
        for ch in channels[:300]:
            params = dict(ch)
            if ch['group'] != 'Germany':
                params['title'] = '%s [%s]' % (ch['title'], ch['group'])
            self._addChannel(cItem, params)
        if not channels:
            SetIPTVPlayerLastHostError(_('No matching entries found.'))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("VavooTo.getLinksForVideo [%s]" % cItem.get('title', ''))
        links = cItem.get('links') or []
        if not links and cItem.get('url'):
            links = [{'name': cItem.get('title', 'VAVOO'), 'url': cItem['url']}]
        urlTab = []
        for idx, lk in enumerate(links):
            if not lk.get('url'):
                continue
            urlTab.append({'name': '%d. %s' % (idx + 1, lk.get('name') or 'VAVOO'), 'url': lk['url'], 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, url):
        printDBG("VavooTo.getVideoLinks [%s]" % url)
        data = self._post(self.RESOLVE_URL, {'language': 'de', 'region': 'AT', 'url': url, 'clientVersion': self.CLIENT_VERSION})
        urlTab = []
        for it in (data if isinstance(data, list) else []):
            u = (it or {}).get('url') if isinstance(it, dict) else ''
            if not u or not self.cm.isValidUrl(u):
                continue
            meta = {'User-Agent': self.STREAM_UA, 'iptv_livestream': True}
            if '.m3u8' in u or '/hls/' in u:
                meta['iptv_proto'] = 'm3u8'
            urlTab.append({'name': 'VAVOO', 'url': strwithmeta(u, meta), 'need_resolve': 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_('This source is offline at the moment. Try another source of the channel.'))
        return urlTab

    def getArticleContent(self, cItem):
        # country, number of sources and the EPG lines (now / next) of the catalog
        other = {}
        if cItem.get('group'):
            other['country'] = cItem['group']
        if cItem.get('links'):
            other['source'] = '%d %s' % (len(cItem['links']), _('sources'))
        text = cItem.get('desc', '').split('[/br]', 1)[1] if '[/br]' in cItem.get('desc', '') else ''
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [], 'other_info': other}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('links') or cItem.get('group'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('VavooTo.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("VavooTo.handleService: name[%s] category[%s]" % (name, category))
        self.currList = []

        if name is None:
            # main menu = the countries, then search
            self.listGroups({'name': 'category'})
            self.listsTab(self.searchItems(), {'name': 'category'})
        elif category in ('list_group', 'list_letter'):
            self.listGroup(self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearch(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, VavooTo(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
