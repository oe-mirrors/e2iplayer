# -*- coding: utf-8 -*-
# ARTE
# Rewritten for the api-cdn.arte.tv "emac v4" JSON API + player v2 config
# Last Modified: 05.09.2026 - stamp iptv_format='mkv' alongside iptv_use_ffmpeg/
# ff_out_container on split audio/video HLS renditions, so the download manager
# shows .mkv immediately instead of .mp4 needing a rename.
# 31.08.2026 - split audio/video HLS renditions (merge://) are muxed
# with ffmpeg (iptv_use_ffmpeg, matroska container) instead of hlsdl, which only
# re-packages segments and produced unplayable files.
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
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigYesNo, ConfigSelection, getConfigListEntry
from datetime import timedelta
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.artetv_lang = ConfigSelection(default="de", choices=[("de", "Deutsch"), ("fr", u"Français"), ("en", "English"), ("es", u"Español"), ("pl", "Polski"), ("it", "Italiano")])
config.plugins.iptvplayer.artetv_quality = ConfigYesNo(default=True)
config.plugins.iptvplayer.artetv_audio = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language") + ":", config.plugins.iptvplayer.artetv_lang))
    optionList.append(getConfigListEntry(_("Show only best quality of streams:"), config.plugins.iptvplayer.artetv_quality))
    optionList.append(getConfigListEntry(_("Show only audio in selected language:"), config.plugins.iptvplayer.artetv_audio))
    return optionList

###################################################


def gettytul():
    return 'https://www.arte.tv/'


class ArteTV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    IMG_SIZE = '400x225'

    MENU = [
        ('ACT', _('News') + ' & ' + _('Society')),
        ('DOR', _('Documentaries')),
        ('CIN', _('Movies')),
        ('SER', _('Series')),
        ('ARTE_CONCERT', 'ARTE Concert'),
        ('SCI', _('Science')),
        ('HIS', _('History')),
        ('DEC', _('Discovery')),
        ('CPO', _('Culture and pop')),
        ('JUN', _('Children')),
        ('EMI', _('Shows')),
    ]

    def __init__(self):
        printDBG("ArteTV.__init__")
        CBaseHostClass.__init__(self, {'history': 'arte.tv', 'cookie': 'arte.tv.cookie'})
        self.MAIN_URL = 'https://www.arte.tv/'
        self.DEFAULT_ICON_URL = 'https://www.arte.tv/static/livewebapp/images/apple-touch-icon.png'
        self.USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'application/json'}

        self.watchedHelper = IPTVWatchedHelper('artetv')
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
                pid = str(cItem.get('program_id', '') or '').strip()
                return 'video:%s' % pid if pid else ''
            if itemType in ('audio', 'more', 'marker'):
                return ''
            if cItem.get('search_item') or cItem.get('name') == 'history':
                return ''
            category = cItem.get('category', '')
            if category in ('list_menu', 'list_live', 'search', 'search_next_page', 'search_history'):
                return ''
            colId = str(cItem.get('col_id', '') or '').strip()
            seasonCode = str(cItem.get('season_code', '') or '').strip()
            if seasonCode:
                return 'folder:arte-season:%s#%s' % (colId, seasonCode)
            if category == 'list_collection' and colId:
                return 'folder:arte-col:%s' % colId
            url = self.wfNormalizeUrlKey(cItem.get('url', ''))
            # an inline zone (no own endpoint) carries the enclosing page's url via
            # dict(cItem); "/web/pages/..." are only the HOME / SEARCH / genre nav
            # pages anyway - never a real content container
            if not url or '/web/pages/' in url:
                return ''
            return 'folder:%s' % url
        except Exception:
            printExc()
        return ''

    ###################################################
    def _lang(self):
        return config.plugins.iptvplayer.artetv_lang.value or 'de'

    def _api(self, path):
        return 'https://api-cdn.arte.tv/api/emac/v4/%s/web/%s' % (self._lang(), path)

    def getPage(self, url, params=None, post_data=None):
        if params is None:
            params = {}
        params['header'] = dict(self.HTTP_HEADER)
        return self.cm.getPage(url, params, post_data)

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
            src = ((item.get('mainImage') or {}).get('url')) or ''
            if not src:
                return ''
            return src.replace('__SIZE__', self.IMG_SIZE)
        except Exception:
            return ''

    def _title(self, item):
        title = self.cleanHtmlStr(item.get('title') or '')
        sub = self.cleanHtmlStr(item.get('subtitle') or '')
        if sub and sub.lower() not in title.lower():
            title = '%s - %s' % (title, sub) if title else sub
        return title

    def _desc(self, item):
        parts = []
        dl = item.get('durationLabel') or ''
        if not dl:
            dur = item.get('duration') or 0
            try:
                dur = int(dur)
                if dur:
                    dl = str(timedelta(seconds=dur))
            except Exception:
                dl = ''
        if dl:
            parts.append('%s: %s' % (_('Duration'), dl))
        ei = item.get('episodeInfo')
        if isinstance(ei, str) and ei.strip():
            parts.append(self.cleanHtmlStr(ei))
        for key in ('teaserText', 'shortDescription'):
            val = item.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(self.cleanHtmlStr(val))
                break
        avail = (item.get('availability') or {}).get('label') or ''
        if avail:
            parts.append(self.cleanHtmlStr(avail))
        return '[/br]'.join(parts)

    ###################################################
    def _zoneData(self, zoneOrContent):
        if not isinstance(zoneOrContent, dict):
            return [], {}
        content = zoneOrContent.get('content') if 'content' in zoneOrContent else zoneOrContent
        content = content or {}
        data = content.get('data')
        return (data if isinstance(data, list) else []), (content.get('pagination') or {})

    def _addItem(self, cItem, item):
        try:
            if not isinstance(item, dict):
                return
            kind = item.get('kind') or {}
            code = (kind.get('code') or '').upper()
            pid = item.get('programId') or ''
            title = self._title(item)
            if not title:
                return
            if code in ('EXTERNAL', 'PAGE') or not pid:
                return
            params = dict(cItem)
            params.pop('page', None)
            params.pop('zone_url', None)
            params.pop('season_code', None)
            params.update({'title': title, 'icon': self._img(item), 'desc': self._desc(item), 'good_for_fav': True})
            if kind.get('isCollection') or code in ('TV_SERIES', 'TOPIC', 'COLLECTION') or str(pid).startswith('RC-'):
                params.update({'category': 'list_collection', 'col_id': pid, 'url': self._api('collections/%s' % pid)})
                self.addDir(params)
            else:
                params.update({'program_id': pid, 'f_url': item.get('url', '')})
                if code in ('LIVESTREAM',) or item.get('livestreamRights'):
                    params['live'] = True
                else:
                    epInfo = item.get('episodeInfo') or ''
                    params['title'] = normalizeMediathekTitle(
                        title, sxeHint=epInfo if isinstance(epInfo, str) else '',
                        date=item.get('firstBroadcastDate') or item.get('availableFrom') or '',
                        isMovie=not epInfo)
                self.addVideo(params)
        except Exception:
            printExc()

    ###################################################
    def listLive(self, cItem):
        # ARTE linear livestream
        cfg = self._json('https://api.arte.tv/api/player/v2/config/%s/LIVE' % self._lang())
        attrs = (cfg or {}).get('data', {}).get('attributes') or {}
        meta = attrs.get('metadata') or {}
        prog = self.cleanHtmlStr(meta.get('title') or '')
        sub = self.cleanHtmlStr(meta.get('subtitle') or '')
        params = dict(cItem)
        params.update({'title': 'ARTE Live' + (' - %s' % prog if prog else ''), 'program_id': 'LIVE', 'live': True,
                       'desc': '[/br]'.join([x for x in (prog, sub) if x]), 'good_for_fav': True, 'icon': ''})
        self.addVideo(params)
        # today's schedule + live concert zones
        data = self._json(self._api('pages/LIVE'))
        for z in ((data or {}).get('zones') or []):
            items, _pag = self._zoneData(z)
            if not items:
                continue
            code = (z.get('code') or '').lower()
            ztitle = self.cleanHtmlStr(z.get('title') or '')
            if ztitle == z.get('code') or '_' in ztitle:
                ztitle = ''
            if code.startswith('program_content'):
                title = ztitle or _('Now')
            elif 'guide' in code:
                title = ztitle or _('Today')
            elif code.endswith('_live') or 'concert' in code:
                title = ztitle or _('Concert')
            else:
                continue
            params = dict(cItem)
            params.update({'category': 'list_zone_inline', 'title': title, 'zone_items': items, 'good_for_fav': False, 'icon': ''})
            self.addDir(params)

    def listMenu(self, cItem):
        for code, title in self.MENU:
            params = dict(cItem)
            params.update({'category': 'list_page', 'title': title, 'url': self._api('pages/%s' % code), 'good_for_fav': True, 'icon': ''})
            self.addDir(params)

    def listPage(self, cItem):
        printDBG('ArteTV.listPage [%s]' % cItem['url'])
        data = self._json(cItem['url'])
        if not data:
            return
        zones = data.get('zones')
        if not isinstance(zones, list):
            return
        contentZones = []
        for z in zones:
            if not isinstance(z, dict):
                continue
            items, _pag = self._zoneData(z)
            if not items:
                continue
            if all((it.get('kind') or {}).get('code', '').upper() in ('EXTERNAL', 'PAGE') for it in items):
                continue
            contentZones.append(z)

        if len(contentZones) == 1:
            self._listZoneItems(cItem, contentZones[0])
            return

        for z in contentZones:
            title = self.cleanHtmlStr(z.get('title') or '') or _('Section')
            items, pag = self._zoneData(z)
            params = dict(cItem)
            params.pop('page', None)
            params.update({'title': title, 'good_for_fav': False, 'icon': self._img(items[0]) if items else ''})
            links = pag.get('links') or {}
            link = links.get('first') or links.get('self') or ''
            if link:
                params.update({'category': 'list_zone', 'url': link})
            else:
                params.update({'category': 'list_zone_inline', 'zone_items': items, 'zone_next': links.get('next') or ''})
            self.addDir(params)

    def listZone(self, cItem):
        printDBG('ArteTV.listZone [%s]' % cItem['url'])
        data = self._json(cItem['url'])
        if not data:
            return
        self._listZoneItems(cItem, data)

    def _listZoneItems(self, cItem, zoneOrContent):
        items, pag = self._zoneData(zoneOrContent)
        for it in items:
            self._addItem(cItem, it)
        nextUrl = (pag.get('links') or {}).get('next') or ''
        if nextUrl:
            params = dict(cItem)
            params.update({'category': 'list_zone', 'title': _('Next page'), 'url': nextUrl, 'good_for_fav': False})
            self.addDir(params)

    def listZoneInline(self, cItem):
        for it in cItem.get('zone_items', []):
            self._addItem(cItem, it)
        nextUrl = cItem.get('zone_next') or ''
        if nextUrl:
            params = dict(cItem)
            params.pop('zone_items', None)
            params.pop('zone_next', None)
            params.update({'category': 'list_zone', 'title': _('Next page'), 'url': nextUrl, 'good_for_fav': False})
            self.addDir(params)

    def listCollection(self, cItem):
        printDBG('ArteTV.listCollection [%s]' % cItem['url'])
        data = self._json(cItem['url'])
        if not data:
            return
        zones = [z for z in (data.get('zones') or []) if isinstance(z, dict) and self._zoneData(z)[0]]
        seasons = [z for z in zones if 'subcollection' in (z.get('code') or '')]
        videos = [z for z in zones if 'subcollection' not in (z.get('code') or '')]

        if len(seasons) > 1:
            for z in seasons:
                items = self._zoneData(z)[0]
                params = dict(cItem)
                params.pop('page', None)
                params.update({'category': 'list_zone_inline', 'title': self.cleanHtmlStr(z.get('title') or _('Season')), 'zone_items': items, 'good_for_fav': False, 'icon': self._img(items[0]) if items else '',
                               'col_id': cItem.get('col_id', ''), 'season_code': z.get('code') or self.cleanHtmlStr(z.get('title') or '')})
                self.addDir(params)
            return

        for z in (seasons + videos):
            for it in self._zoneData(z)[0]:
                self._addItem(cItem, it)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ArteTV.listSearchResult [%s]" % searchPattern)
        page = cItem.get('page', 1)
        if page > 1 and cItem.get('url'):
            data = self._json(cItem['url'])
            zone = data
        else:
            data = self._json(self._api('pages/SEARCH?query=%s' % urllib_quote(searchPattern)))
            zone = None
            for z in ((data or {}).get('zones') or []):
                if 'SEARCH' in (z.get('code') or '').upper() and self._zoneData(z)[0]:
                    zone = z
                    break
        if not zone:
            return
        items, pag = self._zoneData(zone)
        for it in items:
            self._addItem(cItem, it)
        nextUrl = (pag.get('links') or {}).get('next') or ''
        if nextUrl:
            params = dict(cItem)
            params.update({'title': _('Next page'), 'url': nextUrl, 'page': page + 1})
            self.addDir(params)

    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("ArteTV.getLinksForVideo [%s]" % cItem.get('program_id', ''))
        pid = cItem.get('program_id', '')
        if not pid:
            return []
        data = self._json('https://api.arte.tv/api/player/v2/config/%s/%s' % (self._lang(), pid))
        if not data:
            return []
        attrs = (data.get('data') or {}).get('attributes') or data.get('attributes') or {}
        streams = attrs.get('streams') or []
        if not streams:
            return []
        live = bool(attrs.get('live'))
        _md = attrs.get('metadata') or {}
        _mdDesc = _md.get('description')
        if isinstance(_mdDesc, dict):
            _mdDesc = _mdDesc.get('text') or ''
        synopsis = self.cleanHtmlStr(_mdDesc or _md.get('subtitle') or '')
        onlyLang = config.plugins.iptvplayer.artetv_audio.value
        bestOnly = config.plugins.iptvplayer.artetv_quality.value
        langName = dict(config.plugins.iptvplayer.artetv_lang.choices).get(self._lang(), '')

        urlTab = []
        for stream in streams:
            surl = stream.get('url') or ''
            if not surl:
                continue
            versions = stream.get('versions') or [{}]
            label = self.cleanHtmlStr(versions[0].get('label') or versions[0].get('shortLabel') or stream.get('versionLabel') or '')
            if onlyLang and langName and label and langName.lower() not in label.lower() and 'omu' not in label.lower():
                continue
            if '.m3u8' in surl.lower() or 'manifest' in surl.lower():
                if live:
                    # live masters carry separate audio rendition groups - give the
                    # master straight to the player (a resolved variant = video only)
                    urlTab.append({'need_resolve': 0, 'name': label or 'HLS',
                                   'url': self.up.decorateUrl(surl, {'iptv_proto': 'm3u8', 'iptv_livestream': True})})
                    continue
                hls = getDirectM3U8Playlist(strwithmeta(surl, {'iptv_proto': 'm3u8'}), checkExt=False, checkContent=True)
                for it in hls:
                    it['name'] = ('%s %s' % (label, it.get('name', ''))).strip()
                    extraMeta = {'iptv_livestream': live}
                    # ARTE now serves CMAF/fMP4 with separate audio+video renditions.
                    # The generic hlsdl alt-audio merge just concatenates the fragments
                    # and yields an unplayable file, so mux those split streams with
                    # ffmpeg instead (both for buffered playback and for downloads).
                    if strwithmeta(it['url']).meta.get('audio_url'):
                        extraMeta['iptv_use_ffmpeg'] = True
                        extraMeta['ff_out_container'] = 'matroska'
                        extraMeta['iptv_format'] = 'mkv'
                    it['url'] = self.up.decorateUrl(it['url'], extraMeta)
                    it['need_resolve'] = 0
                    urlTab.append(it)
                if not hls:
                    urlTab.append({'need_resolve': 0, 'name': label or 'HLS', 'url': self.up.decorateUrl(surl, {'iptv_proto': 'm3u8', 'iptv_livestream': live})})
            else:
                urlTab.append({'need_resolve': 0, 'name': label or 'stream', 'url': self.up.decorateUrl(surl, {'iptv_livestream': live})})

        if bestOnly and urlTab:
            def _res(u):
                try:
                    return int(u.get('with', 0) or 0)
                except Exception:
                    return 0
            mx = max(_res(u) for u in urlTab)
            if mx > 0:
                urlTab = [u for u in urlTab if _res(u) == mx] or urlTab
        if not live:
            urlTab = applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), synopsis))
        return urlTab

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ArteTV.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", '')
        printDBG("ArteTV.handleService: name[%s] category[%s]" % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []

        if name is None:
            tab = [
                {'category': 'list_page', 'title': _('Home page'), 'url': self._api('pages/HOME')},
                {'category': 'list_menu', 'title': _('Categories')},
                {'category': 'list_live', 'title': _('Live')},
            ] + self.searchItems()
            self.listsTab(tab, {'name': 'category'})
        elif category == 'list_menu':
            self.listMenu(self.currItem)
        elif category == 'list_live':
            self.listLive(self.currItem)
        elif category == 'list_page':
            self.listPage(self.currItem)
        elif category == 'list_zone':
            self.listZone(self.currItem)
        elif category == 'list_zone_inline':
            self.listZoneInline(self.currItem)
        elif category == 'list_collection':
            self.listCollection(self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc')
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ArteTV(), True)
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('artetv')
