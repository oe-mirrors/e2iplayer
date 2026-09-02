# -*- coding: utf-8 -*-
# ORF ON (on.orf.at, ehemals ORF TVthek)
# API: https://api-tvthek.orf.at/api/v4.3/  (HTTP-Basic-Auth, oeffentliche Credentials)
# Last Modified: 28.08.2026
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigYesNo, getConfigListEntry
from datetime import datetime, timedelta
###################################################

config.plugins.iptvplayer.orfon_bestonly = ConfigYesNo(default=True)


def GetConfigList():
    return [getConfigListEntry(_("Show only best quality of streams:"), config.plugins.iptvplayer.orfon_bestonly)]


def gettytul():
    return 'https://on.orf.at/'


class ORFON(GenericFolderWatchedScraperMixin, CBaseHostClass):

    API = 'https://api-tvthek.orf.at/api/v4.3'
    API_AUTH = 'Basic b3JmX29uX3Y0MzpqRlJzYk5QRmlQU3h1d25MYllEZkNMVU41WU5aMjhtdA=='
    LIMIT = 50
    # ORF quality keys: Q1A..Q8C progressive, QXA/QXB adaptive
    QUALITY_ORDER = ['QXB', 'QXA', 'Q8C', 'Q6A', 'Q4A', 'Q1A']

    def __init__(self):
        printDBG("ORFON.__init__")
        CBaseHostClass.__init__(self, {'history': 'ORFON', 'cookie': 'orfon.cookie'})
        self.MAIN_URL = 'https://on.orf.at/'
        self.DEFAULT_ICON_URL = 'https://on.orf.at/img/OON-Share-Image.jpg'
        self.HTTP_HEADER = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
            'Authorization': self.API_AUTH,
            'Accept': 'application/json',
        }

        self.watchedHelper = IPTVWatchedHelper('orfon')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('live'):
                return ''
            itemType = cItem.get('type', '')
            if itemType == 'video':
                eid = str(cItem.get('ep_id', '') or '').strip()
                if eid:
                    return 'video:%s' % eid
                url = self.wfNormalizeUrlKey(cItem.get('ep_url', '') or cItem.get('url', ''))
                return 'video:%s' % url if url else ''
            if itemType in ('audio', 'more', 'marker'):
                return ''
            if cItem.get('search_item') or cItem.get('name') == 'history':
                return ''
            if cItem.get('category', '') in ('list_start', 'list_az', 'list_dates', 'list_live',
                                             'search', 'search_next_page', 'search_history'):
                return ''
            url = self.wfNormalizeUrlKey(cItem.get('url', ''))
            return 'folder:%s' % url if url else ''
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, params=None, post_data=None):
        if params is None:
            params = {}
        params['header'] = dict(self.HTTP_HEADER)
        return self.cm.getPage(url, params, post_data)

    def _abs(self, url):
        if not url:
            return ''
        if url.startswith('http'):
            return url
        return self.API + ('' if url.startswith('/') else '/') + url

    def _json(self, url):
        sts, data = self.getPage(self._abs(url))
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
            return None

    @staticmethod
    def _link(item, name):
        try:
            lk = (item.get('_links') or {}).get(name)
            if isinstance(lk, dict):
                return lk.get('href') or ''
            if isinstance(lk, str):
                return lk
        except Exception:
            pass
        return ''

    def _img(self, item):
        try:
            emb = item.get('_embedded') or {}
            for key in ('image', 'image16x9_with_logo', 'image2x3'):
                pu = ((emb.get(key) or {}).get('public_urls')) or {}
                for size in ('highlight_teaser', 'reference', 'player'):
                    u = (pu.get(size) or {}).get('url') or ''
                    if u and '_default_' not in u:
                        return u
        except Exception:
            pass
        return ''

    def _desc(self, item):
        parts = []
        try:
            secs = int(item.get('duration_seconds') or 0) or int(item.get('exact_duration') or 0) // 1000
            if secs > 0:
                parts.append(str(timedelta(seconds=secs)))
        except Exception:
            pass
        d = item.get('date') or item.get('episode_date') or ''
        if isinstance(d, str) and len(d) >= 10:
            parts.append(d[:10])
        for key in ('description', 'teaser_text', 'share_subject', 'episode_title'):
            v = item.get(key)
            if isinstance(v, str) and v.strip():
                parts.append(self.cleanHtmlStr(v))
                break
        return '[/br]'.join(parts)

    ###################################################
    def _items(self, data):
        if not isinstance(data, dict):
            return data if isinstance(data, list) else []
        emb = data.get('_embedded') or {}
        for key in ('items', 'items_list'):
            if isinstance(emb.get(key), list):
                return emb[key]
        for key in ('_items', 'items', 'children', 'history_items'):
            if isinstance(data.get(key), list):
                return data[key]
        return []

    def _nextHref(self, data):
        try:
            nx = (data.get('_links') or {}).get('next')
            if isinstance(nx, dict):
                return nx.get('href') or ''
            if isinstance(nx, str):
                return nx
            if isinstance(data.get('next'), str):
                return data['next']
        except Exception:
            pass
        return ''

    def _isVideo(self, item):
        if item.get('video_type') in ('episode', 'segment', 'live', 'timeshift', 'livestream'):
            return True
        if 'sources' in item:
            return True
        if isinstance(item.get('_embedded'), dict) and 'segments' in item['_embedded']:
            return True
        if '/livestream/' in (self._link(item, 'self') or ''):
            return True
        return False

    def _addItem(self, cItem, item):
        try:
            if not isinstance(item, dict):
                return
            title = self.cleanHtmlStr(item.get('title') or item.get('headline') or '')
            if not title:
                return
            params = dict(cItem)
            params.pop('page', None)
            params.update({'title': title, 'icon': self._img(item), 'desc': self._desc(item), 'good_for_fav': True})

            episodesHref = self._link(item, 'episodes')
            selfHref = self._link(item, 'self') or self._link(item, '_self')

            if self._isVideo(item):
                eid = item.get('id') or ''
                params.update({'category': 'play', 'ep_id': eid, 'ep_url': self._abs(selfHref) if selfHref else ''})
                if not params.get('live'):
                    profile = self.cleanHtmlStr(((item.get('_embedded') or {}).get('profile') or {}).get('title') or '')
                    base = '%s - %s' % (profile, title) if profile and profile.lower() not in title.lower() else title
                    params['title'] = normalizeMediathekTitle(base, date=item.get('date') or item.get('episode_date') or '', sxeHint=title)
                self.addVideo(params)
            elif episodesHref:
                params.update({'category': 'list_url', 'url': self._abs(episodesHref)})
                self.addDir(params)
            elif selfHref:
                itype = item.get('type') or ''
                url = self._abs(selfHref)
                if itype == 'genre' and '/profiles' not in url:
                    url = url.rstrip('/') + '/profiles?limit=%d' % self.LIMIT
                params.update({'category': 'list_url', 'url': url})
                self.addDir(params)
        except Exception:
            printExc()

    ###################################################
    def listUrl(self, cItem):
        data = self._json(cItem['url'])
        if data is None:
            return
        for it in self._items(data):
            self._addItem(cItem, it)
        nxt = self._nextHref(data)
        if nxt:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': self._abs(nxt), 'good_for_fav': False})
            self.addDir(params)

    def listStart(self, cItem):
        data = self._json('/page/start')
        lanes = data if isinstance(data, list) else []
        count = 0
        for lane in lanes:
            try:
                if not isinstance(lane, dict):
                    continue
                lid = lane.get('id') or ''
                if lid in ('continue_watching', 'watchlist', 'orflive', 'recommendations'):
                    continue
                title = self.cleanHtmlStr(lane.get('title') or lane.get('sub_headline') or '')
                if lid == 'genres':
                    title = title or _('Categories')
                elif lid == 'highlights':
                    title = title or _('Highlights')
                href = self._link(lane, 'self')
                if not title or not href:
                    continue
                params = dict(cItem)
                params.update({'category': 'list_url', 'title': title, 'url': self._abs(href), 'good_for_fav': False, 'icon': self._img(lane)})
                self.addDir(params)
                count += 1
            except Exception:
                printExc()
        if count == 0:
            printDBG('ORFON.listStart: /page/start empty -> genres fallback')
            self.listUrl(dict(cItem, url=self._abs('/page/start/genres')))

    def listAZ(self, cItem):
        for letter in list('ABCDEFGHIJKLMNOPQRSTUVWXYZ') + ['0-9']:
            params = dict(cItem)
            params.update({'category': 'list_url', 'title': letter,
                           'url': '%s/profiles/lettergroup/%s' % (self.API, '0-9' if letter == '0-9' else letter)})
            self.addDir(params)

    def listDates(self, cItem):
        today = datetime.now()
        for i in range(14):
            d = today - timedelta(days=i)
            params = dict(cItem)
            params.update({'category': 'list_url', 'title': d.strftime('%d.%m.%Y'),
                           'url': '%s/schedule/%s' % (self.API, d.strftime('%Y-%m-%d'))})
            self.addDir(params)

    CHANNEL_NAMES = {'orf1': 'ORF 1', 'orf2': 'ORF 2', 'orf3': 'ORF III', 'orfs': 'ORF Sport +'}

    def listLive(self, cItem):
        data = self._json('/livestreams')
        if not isinstance(data, dict):
            return
        for channel, val in data.items():
            items = (val.get('items') if isinstance(val, dict) else None) or []
            if not items:
                continue
            it = items[0]
            selfHref = self._link(it, 'self')
            if not selfHref:
                continue
            chName = self.CHANNEL_NAMES.get(channel, channel.upper())
            prog = self.cleanHtmlStr(it.get('title') or it.get('headline') or '')
            params = dict(cItem)
            params.pop('page', None)
            params.update({'category': 'play', 'live': True, 'ep_id': it.get('id') or '',
                           'ep_url': self._abs(selfHref), 'icon': self._img(it), 'good_for_fav': True,
                           'title': '%s - %s' % (chName, prog) if prog else chName,
                           'desc': self._desc(it)})
            self.addVideo(params)

    def listSearch(self, cItem, searchPattern, searchType):
        page = cItem.get('page', 1)
        if page > 1 and cItem.get('url'):
            data = self._json(cItem['url'])
            if data:
                for it in self._items(data):
                    self._addItem(cItem, it)
                nxt = self._nextHref(data)
                if nxt:
                    params = dict(cItem)
                    params.update({'title': _('Next page'), 'url': self._abs(nxt), 'page': page + 1})
                    self.addDir(params)
            return
        data = self._json('/search/%s' % urllib_quote_plus(searchPattern))
        if not isinstance(data, dict):
            return
        sug = data.get('suggestions') or {}
        for key in ('episodes', 'segments'):
            for it in (sug.get(key) or []):
                self._addItem(cItem, it)
        search = data.get('search') or {}
        for key in ('episodes', 'segments'):
            info = search.get(key) or {}
            if info.get('total', 0) > 0:
                params = dict(cItem)
                params.update({'title': _('All results') + ' (%s)' % info['total'],
                               'url': '%s/search-partial/%s/%s?limit=%d' % (self.API, key, urllib_quote_plus(searchPattern), self.LIMIT),
                               'page': 2, 'good_for_fav': False})
                self.addDir(params)

    ###################################################
    def _pickSources(self, node):
        src = node.get('sources')
        if isinstance(src, dict) and (src.get('hls') or src.get('dash')):
            return src
        for key in ('gapless_sources_austria', 'gapless_sources_worldwide'):
            gs = node.get(key)
            if isinstance(gs, dict) and gs.get('hls'):
                return gs
        return None

    def _subtitle(self, node):
        href = self._link(node, 'subtitle')
        if not href:
            return []
        data = self._json(href)
        if not isinstance(data, dict):
            return []
        for key, fmt in (('vtt_url', 'vtt'), ('srt_url', 'srt'), ('ttml_url', 'ttml')):
            if data.get(key):
                return [{'title': _('German'), 'url': data[key], 'lang': 'de', 'format': fmt}]
        return []

    def getLinksForVideo(self, cItem):
        printDBG("ORFON.getLinksForVideo [%s]" % cItem.get('ep_id', ''))
        url = cItem.get('ep_url') or ''
        if not url and cItem.get('ep_id'):
            url = '%s/episode/%s' % (self.API, cItem['ep_id'])
        if not url:
            return []
        data = self._json(url)
        if not isinstance(data, dict):
            return []

        node = data
        src = self._pickSources(node)
        if src is None:
            for seg in ((data.get('_embedded') or {}).get('segments') or []):
                src = self._pickSources(seg)
                if src:
                    node = seg
                    break
        if src is None:
            for it in self._items(data):
                src = self._pickSources(it)
                if src:
                    node = it
                    break
        if src is None:
            return []

        subTracks = self._subtitle(node) or self._subtitle(data)
        live = bool(cItem.get('live')) or data.get('video_type') == 'live'
        synopsis = self.cleanHtmlStr(data.get('description') or node.get('description') or data.get('teaser_text') or '')
        bestOnly = config.plugins.iptvplayer.orfon_bestonly.value

        hlsList = [s for s in (src.get('hls') or []) if not s.get('is_drm_protected')]
        drmList = [s for s in (src.get('hls') or []) if s.get('is_drm_protected')]
        entries = hlsList or drmList

        def qrank(s):
            key = (s.get('quality_key') or '').replace('DRM', '')
            return self.QUALITY_ORDER.index(key) if key in self.QUALITY_ORDER else 99

        entries = sorted(entries, key=qrank)
        urlTab = []
        for s in entries:
            surl = s.get('src') or ''
            if not surl:
                continue
            name = s.get('quality_key') or 'HLS'
            meta = {'iptv_livestream': live, 'iptv_proto': 'm3u8'}
            if subTracks:
                meta['external_sub_tracks'] = subTracks
            if 'QX' in name.upper() and not live:
                for it in getDirectM3U8Playlist(strwithmeta(surl, {'iptv_proto': 'm3u8'}), checkExt=False, checkContent=True):
                    it['need_resolve'] = 0
                    it['url'] = self.up.decorateUrl(it['url'], meta)
                    urlTab.append(it)
                continue
            urlTab.append({'need_resolve': 0, 'name': name, 'url': self.up.decorateUrl(surl, meta)})

        if bestOnly and urlTab:
            def res(u):
                try:
                    return int(u.get('with', 0) or 0)
                except Exception:
                    return 0
            mx = max(res(u) for u in urlTab)
            if mx > 0:
                urlTab = [u for u in urlTab if res(u) == mx] or urlTab[:1]
        if not live:
            urlTab = applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis))
        return urlTab

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ORFON.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("ORFON.handleService: name[%s] category[%s]" % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []

        if name is None:
            tab = [
                {'category': 'list_start', 'title': _('Home page')},
                {'category': 'list_az', 'title': _('Program A-Z')},
                {'category': 'list_url', 'title': _('All shows'), 'url': '%s/profiles?limit=%d' % (self.API, self.LIMIT)},
                {'category': 'list_dates', 'title': _('List by day')},
                {'category': 'list_live', 'title': _('Live')},
            ] + self.searchItems()
            self.listsTab(tab, {'name': 'category'})
        elif category == 'list_start':
            self.listStart(self.currItem)
        elif category == 'list_az':
            self.listAZ(self.currItem)
        elif category == 'list_dates':
            self.listDates(self.currItem)
        elif category == 'list_live':
            self.listLive(self.currItem)
        elif category == 'list_url':
            self.listUrl(self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page'})
            self.listSearch(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ORFON(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('orfon')
