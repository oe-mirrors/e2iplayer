# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# ARTE
# Rewritten for the api-cdn.arte.tv "emac v4" JSON API + player v2 config
# 07.10.2026 - INFO (programme/collection details, moviemeta for
# films and series), First/Jump/Next paging, own url per video (download marker),
# SxxExx from the episode info, all pages of a series, default user agent.
# 05.09.2026 - stamp iptv_format='mkv' alongside iptv_use_ffmpeg/
# ff_out_container on split audio/video HLS renditions, so the download manager
# shows .mkv immediately instead of .mp4 needing a rename.
# 31.08.2026 - split audio/video HLS renditions (merge://) are muxed
# with ffmpeg (iptv_use_ffmpeg, matroska container) instead of hlsdl, which only
# re-packages segments and produced unplayable files.
# 08.10.2026 - episode titles without the doubled "Staffel 1 (1/8)", a message for youth-protected
# (night slot only) and geo-blocked videos instead of an empty link list.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
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
import re
###################################################

###################################################
# Config options for HOST
###################################################
ARTE_LANGS = [("de", "Deutsch"), ("fr", u"Français"), ("en", "English"), ("es", u"Español"), ("pl", "Polski"), ("it", "Italiano")]
config.plugins.iptvplayer.artetv_lang = ConfigSelection(default="de", choices=ARTE_LANGS)
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
        self.DEFAULT_ICON_URL = 'https://static-cdn.arte.tv/replay/favicons/favicon-194x194.png'
        self.USER_AGENT = self.cm.getDefaultUserAgent()
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
        else:
            season, episode = self._seasonEpisode(item)
            if season and episode:
                parts.append('%s %s, %s %s' % (_('Season'), season, _('Episode'), episode))
        for key in ('teaserText', 'shortDescription'):
            val = item.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(self.cleanHtmlStr(val))
                break
        avail = (item.get('availability') or {}).get('label') or ''
        if avail:
            parts.append(self.cleanHtmlStr(avail))
        return '[/br]'.join(parts)

    @staticmethod
    def _seasonEpisode(item):
        # episodeInfo is {"season": 1, "episode": 3, ...} for series episodes (a text on old data)
        ei = item.get('episodeInfo')
        if isinstance(ei, dict):
            try:
                return int(ei.get('season') or 0), int(ei.get('episode') or 0)
            except (TypeError, ValueError):
                pass
        return 0, 0

    @staticmethod
    def _isFilm(item):
        genre = item.get('genre') or {}
        return not item.get('episodeInfo') and (genre.get('deeplink') == 'arte://emac/CIN' or str(genre.get('id', '')) == '2')

    @staticmethod
    def _pageTpl(link):
        # a zone content url with "page=N" -> template for iptvpaging ("page={page}")
        if not link or not re.search(r'[?&]page=\d+', link):
            return ''
        return re.sub(r'([?&]page=)\d+', r'\g<1>{page}', link)

    def _addPaging(self, cItem, pag, nextUrl=''):
        links = pag.get('links') or {}
        nextUrl = links.get('next') or nextUrl
        tpl = self._pageTpl(links.get('first') or links.get('next') or nextUrl)
        try:
            page = int(pag.get('page') or 1)
            lastPage = int(pag.get('pages') or 0)
        except (TypeError, ValueError):
            page, lastPage = 1, 0
        if not tpl and nextUrl:
            # no page number in the url: plain "Next page"
            params = stripPagerKeys(dict(cItem))
            params.update({'title': _('Next page'), 'url': nextUrl, 'page': page + 1, 'good_for_fav': False})
            self.addDir(params)
            return
        if tpl:
            addPagingItems(self, cItem, page, bool(nextUrl), lastPage, tpl)

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
            params = stripPagerKeys(dict(cItem), ('zone_url', 'zone_items', 'zone_next', 'season_code',
                                                  'meta_type', 'meta_title', 'live', 'program_id', 'f_url'))
            params.update({'title': title, 'icon': self._img(item), 'desc': self._desc(item), 'good_for_fav': True})
            if kind.get('isCollection') or code in ('TV_SERIES', 'TOPIC', 'COLLECTION') or str(pid).startswith('RC-'):
                if pid == cItem.get('col_id'):
                    return  # a collection lists itself in its "collection_content" zone
                params.update({'category': 'list_collection', 'col_id': pid, 'url': self._api('collections/%s' % pid)})
                if code == 'TV_SERIES':
                    params.update({'meta_type': 'tv', 'meta_title': self.cleanHtmlStr(item.get('title') or '')})
                self.addDir(params)
            else:
                # the programme page as the row's own url: the download marker is keyed on it
                # (the watched key stays the programme id)
                pageUrl = item.get('url') or 'https://www.arte.tv/%s/videos/%s/' % (self._lang(), pid)
                params.update({'program_id': pid, 'f_url': item.get('url', ''), 'url': pageUrl})
                if code in ('LIVESTREAM',) or item.get('livestreamRights'):
                    params['live'] = True
                else:
                    epInfo = item.get('episodeInfo') or ''
                    season, episode = self._seasonEpisode(item)
                    if season and episode:
                        # "Red Light (3/10)" -> "Red Light - S01E03", "Twin Peaks - Staffel 1 (1/8) - Das Geheimnis
                        # von Twin Peaks" -> "Twin Peaks - S01E01 - Das Geheimnis von Twin Peaks"
                        plain = re.sub(r'\s*(?:-\s*)?(?:\b(?:Staffel|Saison|Season)\s+\d+\s*)?\(\d+/\d+\)', '', title).strip(' -') or title
                        named = normalizeMediathekTitle(plain, sxeHint='S%02dE%02d' % (season, episode))
                        params['title'] = named if named != plain else title
                    else:
                        params['title'] = normalizeMediathekTitle(
                            title, sxeHint=epInfo if isinstance(epInfo, str) else '',
                            date=item.get('firstBroadcastDate') or item.get('availableFrom') or '',
                            isMovie=not epInfo)
                    if self._isFilm(item):
                        params.update({'meta_type': 'movie', 'meta_title': self.cleanHtmlStr(item.get('title') or '')})
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
                       'url': 'https://www.arte.tv/%s/live/' % self._lang(),
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
            params = stripPagerKeys(dict(cItem))
            params.update({'title': title, 'good_for_fav': False, 'icon': self._img(items[0]) if items else ''})
            links = pag.get('links') or {}
            link = links.get('first') or links.get('self') or ''
            if link:
                params.update({'category': 'list_zone', 'url': link})
            else:
                # inline zone without an own endpoint: the items travel with the row, no url of its own
                params.pop('url', None)
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
        # the pager rows open zone content urls - list_zone, also below a page / inline zone
        pagerItem = dict(cItem, category='list_zone')
        pagerItem.pop('zone_items', None)
        pagerItem.pop('zone_next', None)
        self._addPaging(pagerItem, pag)

    def listZoneInline(self, cItem):
        for it in cItem.get('zone_items', []):
            self._addItem(cItem, it)
        nextUrl = cItem.get('zone_next') or ''
        if nextUrl:
            pagerItem = dict(cItem, category='list_zone')
            pagerItem.pop('zone_items', None)
            pagerItem.pop('zone_next', None)
            self._addPaging(pagerItem, {}, nextUrl)

    def listCollection(self, cItem):
        printDBG('ArteTV.listCollection [%s]' % cItem['url'])
        data = self._json(cItem['url'])
        if not data:
            return
        # "collection_content" holds only the collection itself (its INFO data)
        zones = [z for z in (data.get('zones') or []) if isinstance(z, dict) and self._zoneData(z)[0]
                 and not (z.get('code') or '').startswith('collection_content')]
        seasons = [z for z in zones if 'subcollection' in (z.get('code') or '')]
        videos = [z for z in zones if 'subcollection' not in (z.get('code') or '')]

        if len(seasons) > 1:
            for z in seasons:
                items, pag = self._zoneData(z)
                params = stripPagerKeys(dict(cItem), ('meta_type', 'meta_title'))
                params.update({'title': self.cleanHtmlStr(z.get('title') or _('Season')), 'good_for_fav': False, 'icon': self._img(items[0]) if items else '',
                               'col_id': cItem.get('col_id', ''), 'season_code': z.get('code') or self.cleanHtmlStr(z.get('title') or '')})
                links = pag.get('links') or {}
                if links.get('next') and links.get('first'):
                    # a season with more than one page: list it from its endpoint (paging)
                    params.update({'category': 'list_zone', 'url': links['first']})
                else:
                    params.update({'category': 'list_zone_inline', 'zone_items': items, 'zone_next': ''})
                self.addDir(params)
            return

        zones = seasons + videos
        if len(zones) == 1:
            self._listZoneItems(cItem, zones[0])
            return
        for z in zones:
            for it in self._zoneData(z)[0]:
                self._addItem(cItem, it)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ArteTV.listSearchResult [%s]" % searchPattern)
        if cItem.get('url'):
            # a pager row: the url of the result page
            zone = self._json(cItem['url'])
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
        self._addPaging(cItem, pag)

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
            # youth protection (e.g. Twin Peaks season 2): the streams only come inside the night slot
            restr = attrs.get('restriction') or {}
            slot = restr.get('timeSlot') or {}
            if len(slot.get('startDate') or '') >= 16 and len(slot.get('endDate') or '') >= 16:
                SetIPTVPlayerLastHostError(_('Youth protection: only available between %s and %s.') % (slot['startDate'][11:16], slot['endDate'][11:16]))
            elif (restr.get('geoblocking') or {}).get('restrictedArea'):
                SetIPTVPlayerLastHostError(_('Not available in your country (geo-blocking).'))
            return []
        live = bool(attrs.get('live'))
        _md = attrs.get('metadata') or {}
        _mdDesc = _md.get('description')
        if isinstance(_mdDesc, dict):
            _mdDesc = _mdDesc.get('text') or ''
        synopsis = self.cleanHtmlStr(_mdDesc or _md.get('subtitle') or '')
        onlyLang = config.plugins.iptvplayer.artetv_audio.value
        bestOnly = config.plugins.iptvplayer.artetv_quality.value
        # not dict(ConfigSelection.choices): iterating Enigma2's choicesList gives the keys only
        langName = dict(ARTE_LANGS).get(self._lang(), '')

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
    # INFO
    ###################################################
    CREDIT_KEYS = {'REA': 'director', 'SCE': 'writer', 'ACT': 'actors', 'PRD': 'production', 'COUNTRY': 'country'}
    INFO_TWINS = {'directors': 'director', 'writers': 'writer', 'cast': 'actors'}

    def _contentItem(self, data, codePrefix):
        for z in ((data or {}).get('zones') or []):
            if isinstance(z, dict) and (z.get('code') or '').startswith(codePrefix):
                items = self._zoneData(z)[0]
                if items and isinstance(items[0], dict):
                    return items[0]
        return {}

    def _siteInfo(self, prog):
        info = {}
        year = ''
        for credit in (prog.get('credits') or []):
            if not isinstance(credit, dict):
                continue
            values = [self.cleanHtmlStr(v) for v in (credit.get('values') or []) if v]
            if not values:
                continue
            code = credit.get('code') or ''
            if code == 'PRODUCTION_YEAR':
                year = values[0][:4]
                info['year'] = year
            elif code in self.CREDIT_KEYS:
                info[self.CREDIT_KEYS[code]] = ', '.join(values[:6])
        if prog.get('durationLabel'):
            info['duration'] = self.cleanHtmlStr(prog['durationLabel'])
        genre = (prog.get('genre') or {}).get('label') or ''
        if genre:
            info['genre'] = self.cleanHtmlStr(genre)
        try:
            if int(prog.get('ageRating') or 0) > 0:
                info['age_limit'] = '%s+' % int(prog['ageRating'])
        except (TypeError, ValueError):
            pass
        bcast = prog.get('firstBroadcastDate') or ''
        if isinstance(bcast, str) and len(bcast) >= 10:
            info['broadcast'] = bcast[:10]
        end = (prog.get('availability') or {}).get('end') or ''
        if isinstance(end, str) and len(end) >= 10:
            info['remaining'] = _('available until %s') % end[:10]
        return info, year

    def getArticleContent(self, cItem):
        printDBG('ArteTV.getArticleContent [%s]' % cItem.get('program_id', cItem.get('col_id', '')))
        text, icon, info, year = cItem.get('desc', ''), cItem.get('icon', ''), {}, ''
        prog = {}
        pid = cItem.get('program_id', '')
        if cItem.get('type') == 'video' and pid and pid != 'LIVE':
            prog = self._contentItem(self._json(self._api('programs/%s' % pid)), 'program_content')
        elif cItem.get('category') == 'list_collection' and cItem.get('url'):
            prog = self._contentItem(self._json(cItem['url']), 'collection_content')
        if prog:
            desc = prog.get('fullDescription') or prog.get('description') or prog.get('shortDescription') or ''
            if desc:
                parts = [self.cleanHtmlStr(x) for x in re.split(r'<br\s*/?>', desc, flags=re.I)]
                text = '[/br]'.join([x for x in parts if x])
            info, year = self._siteInfo(prog)
        meta = {}
        if cItem.get('meta_type') and cItem.get('meta_title'):
            try:
                # a film's year must match (the title search also finds other films of the same name)
                meta = getMeta(cItem['meta_type'], cItem['meta_title'], year,
                               maxYearDiff=1 if cItem['meta_type'] == 'movie' else None)
            except Exception:
                printExc()
        # the site's German/French texts first, the service adds ratings, poster and missing fields
        # (not the plural twin of a field the site already has); the site's genre is only the
        # ARTE section ("Filme"), the service's genres are the real ones
        metaInfo = meta.get('info') or {}
        if metaInfo.get('genres'):
            info.pop('genre', None)
        for key, value in metaInfo.items():
            if key not in info and self.INFO_TWINS.get(key, '') not in info:
                info[key] = value
        text = text or meta.get('plot', '')
        icon = meta.get('poster') or icon
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': info}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ArteTV.handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
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

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video' or cItem.get('category') == 'list_collection'
