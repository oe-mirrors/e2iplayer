# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Laczy nas pilka - Biblioteka Pilkarstwa Polskiego (laczynaspilka.pl/biblioteka) - the PZPN football library:
#   matches of the Polish national teams (and cup finals, league classics) with highlights, full halves and
#   goal clips, the "Wideoteka" collections and the PZPN TV programmes ("Kulisy spotkania", ...)
# Site: Angular app on top of the public BPP REST API (bus20-api-bpp.laczynaspilka.pl/api/bpp/v1/), clips are
#   CUTV videos, HLS on cdn.laczynaspilka.pl/pz/<subpath>; search through search-prod.laczynaspilka.pl
# 03.10.2026 - new host: watched flag, name normalisation, sidecar, INFO
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
###################################################
# FOREIGN import
###################################################
import re
from datetime import timedelta
###################################################

API_URL = 'https://bus20-api-bpp.laczynaspilka.pl/api/bpp/v1/'
SEARCH_URL = 'https://search-prod.laczynaspilka.pl/GlobalSearch?query=%s&allowedService=1&service=1&material=3&page=%d&count=%d'
CMS_IMG_URL = 'https://cdn.laczynaspilka.pl/cms2/prod/'
FREEZE_IMG_URL = 'https://cdn.laczynaspilka.pl/freeze-frames/'
VIDEO_CDN_URL = 'https://cdn.laczynaspilka.pl/pz/'
SITE_URL = 'https://www.laczynaspilka.pl/biblioteka'


def GetConfigList():
    return []


def gettytul():
    return 'https://www.laczynaspilka.pl/biblioteka'


class LaczyNasPilka(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'vid', 'title', 'raw_title', 'icon', 'desc', 'date', 'match_title', 'competition', 'duration')
    PAGE_SIZE = 30

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'laczynaspilka', 'cookie': 'laczynaspilka.cookie'})
        self.MAIN_URL = 'https://www.laczynaspilka.pl/'
        self.DEFAULT_ICON_URL = CMS_IMG_URL + 'sites/default/files/styles/bpp_thumbnail_large/public/2020-11/bpp_baner_wideoteka_2160x450_0.png?h=a02e64c2'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.HEADER.update({'Accept': 'application/json, text/plain, */*', 'Origin': 'https://www.laczynaspilka.pl', 'Referer': SITE_URL + '/'})
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True}
        self.watchedHelper = IPTVWatchedHelper('laczynaspilka')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type') == 'video' or cItem.get('category') == 'video':
                return 'video:%s' % cItem['vid'] if cItem.get('vid') else ''
            category = cItem.get('category', '')
            if category == 'list_match' and cItem.get('url'):
                return 'folder:%s' % cItem['url']
            if category in ('list_playlist', 'list_program', 'list_section') and cItem.get('f_id'):
                return 'folder:%s:%s' % (cItem['f_id'], cItem.get('f_section', ''))
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _api(self, path):
        url = path if path.startswith('http') else API_URL + path
        sts, data = self.getPage(url)
        if not sts or not data:
            return None
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return None
        if isinstance(data, dict) and data.get('status') not in (None, 200):
            printDBG("LaczyNasPilka._api status %s for %s" % (data.get('status'), url))
            return None
        return data

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _styleUrl(node, styles=('bpp_thumbnail_large', 'bpp_medium', 'lnp_thumbnail_large', 'bpp_small')):
        if not isinstance(node, dict):
            return ''
        for key in styles:
            url = (node.get('styles') or {}).get(key) or ''
            if url:
                return url
        return node.get('url') or ''

    def _img(self, node):
        # CMS responsive image ({desktop: {url, styles}}), a plain CMS image ({url, styles}) or a CUTV frame
        try:
            if not node:
                return ''
            if isinstance(node, list):
                node = node[0] if node else {}
            if not isinstance(node, dict):
                return ''
            if node.get('locationType') == 'REMOTE' and node.get('url'):
                return FREEZE_IMG_URL + urllib_quote(node['url'].replace('\\', '/').lstrip('/'), safe='/%')
            for key in ('thumbnail', 'desktop', 'mobile'):
                if isinstance(node.get(key), dict):
                    node = node[key]
                    break
            url = self._styleUrl(node)
            if url:
                return CMS_IMG_URL + url.lstrip('/')
        except Exception:
            printExc()
        return ''

    def _bannerImg(self, item):
        return self._img(((item or {}).get('banner') or {}).get('background_images'))

    @staticmethod
    def _isoFromMatchTitle(title):
        m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})\s*\)?\s*$', title or '')
        return '%s-%s-%s' % (m.group(3), m.group(2), m.group(1)) if m else ''

    @staticmethod
    def _duration(seconds):
        try:
            seconds = int(float(seconds or 0))
            return str(timedelta(seconds=seconds)) if seconds > 0 else ''
        except Exception:
            return ''

    def _videoTitle(self, matchTitle, clipTitle, date):
        clipTitle = clipTitle or _('Video')
        if not matchTitle:
            return clipTitle, clipTitle
        raw = '%s - %s' % (matchTitle, clipTitle)
        if not IsMediaNamingNormalized():
            return raw, raw
        base = re.sub(r',?\s*\(?\d{2}\.\d{2}\.\d{4}\)?\s*$', '', matchTitle).strip(' ,')
        out = '%s - %s' % (base, clipTitle)
        if date:
            out = '%s (%s)' % (out, date)
        return out, raw

    def _addVideo(self, cItem, vid, header, matchTitle='', description='', competition='', icon=''):
        if not vid:
            return
        header = header or {}
        clipTitle = self.cleanHtmlStr(header.get('title') or description or '')
        if description and clipTitle != description and len(description) > len(clipTitle):
            clipTitle = self.cleanHtmlStr(description)
        date = self._isoFromMatchTitle(matchTitle)
        title, raw = self._videoTitle(self.cleanHtmlStr(matchTitle), clipTitle, date)
        duration = self._duration(header.get('duration'))
        icon = self._img(header.get('thumbnailOverwrite')) or self._img(header.get('images')) or icon
        desc = [x for x in (duration, date, competition) if x]
        params = stripPagerKeys(dict(cItem), ('f_ids', 'f_section', 'search_pattern'))
        params.update({'good_for_fav': True, 'category': 'video', 'type': 'video', 'title': title, 'raw_title': raw, 'vid': vid,
                       'url': '%s/v/%s' % (SITE_URL, vid), 'icon': icon, 'date': date, 'duration': duration,
                       'match_title': self.cleanHtmlStr(matchTitle), 'competition': competition,
                       'desc': ' | '.join(desc)})
        self.addVideo(params)

    def _listVideoIds(self, cItem, entries, matchTitle='', competition='', icon=''):
        # entries: [(cutv id, description)], the API returns the headers in its own order
        ids = [e[0] for e in entries if e[0]]
        if not ids:
            return 0
        headers = {}
        for idx in range(0, len(ids), 40):
            chunk = ids[idx:idx + 40]
            data = self._api('video/list?' + '&'.join('ids=%s' % i for i in chunk))
            for it in ((data or {}).get('items') or []):
                if isinstance(it, dict) and it.get('cutvVideoId'):
                    headers[it['cutvVideoId']] = it
        count = 0
        for vid, description in entries:
            it = headers.get(vid)
            if not it:
                continue
            mTitle = matchTitle or it.get('title') or ''
            comp = competition or self._competition(it)
            self._addVideo(cItem, vid, it.get('cutvVideoHeader'), mTitle, description, comp, icon or self._img(it.get('images')))
            count += 1
        return count

    def _competition(self, it):
        try:
            sub = ((it.get('footballMatchHeader') or {}).get('footballSubcompetition') or {})
            return self.cleanHtmlStr(sub.get('nazwa') or '')
        except Exception:
            return ''

    @staticmethod
    def _entries(videoList):
        ret = []
        for v in videoList or []:
            try:
                f = v.get('file') or {}
                if f.get('source', 'cutvVideo') == 'cutvVideo' and f.get('id'):
                    ret.append((f['id'], (v.get('description') or '').strip()))
            except Exception:
                pass
        return ret

    ###################################################
    # main menu
    ###################################################
    def listMain(self, cItem):
        for category, title in (('list_competitions', _('Matches of the national teams')),
                                ('list_leagues', _('League and cup matches')),
                                ('list_library', _('Video library')),
                                ('list_programs', _('Programmes'))):
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': category, 'title': title})
            self.addDir(params)
        for item in self.searchItems():
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

    ###################################################
    # matches
    ###################################################
    def listCompetitions(self, cItem):
        data = self._api('competition/list')
        for it in ((data or {}).get('items') or []):
            if not it.get('id') or not it.get('nazwa'):
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_subcompetitions', 'title': self.cleanHtmlStr(it['nazwa']), 'f_id': it['id']})
            self.addDir(params)

    def listSubcompetitions(self, cItem):
        data = self._api('subcompetition/filter?competitionId=%s&limit=9999&skip=0' % cItem['f_id'])
        for it in ((data or {}).get('items') or []):
            if not it.get('id') or not it.get('nazwa'):
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_matches', 'title': self.cleanHtmlStr(it['nazwa']), 'f_id': it['id'],
                           'f_kind': 'by-subcompetition', 'icon': self._img(it.get('logo'))})
            self.addDir(params)

    def listLeagues(self, cItem):
        data = self._api('league/list')
        for it in ((data or {}).get('items') or []):
            if not it.get('id') or not it.get('nazwa'):
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_plays', 'title': self.cleanHtmlStr(it['nazwa']), 'f_id': it['id']})
            self.addDir(params)

    def listPlays(self, cItem):
        data = self._api('play/filter?leagueId=%s&limit=9999&skip=0' % cItem['f_id'])
        for it in ((data or {}).get('items') or []):
            if not it.get('id') or not it.get('nazwa'):
                continue
            title = self.cleanHtmlStr(it['nazwa'])
            if it.get('sezon') and it['sezon'] not in title:
                title = '%s %s' % (title, it['sezon'])
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_matches', 'title': title, 'f_id': it['id'],
                           'f_kind': 'by-play', 'icon': self._img(it.get('logo'))})
            self.addDir(params)

    def listMatches(self, cItem):
        page = cItem.get('page', 1)
        path = 'match/list/%s/DateDesc/%s' % (cItem.get('f_kind', 'by-subcompetition'), cItem['f_id'])
        data = self._api('%s?getSummary=false&pageNo=%d&pageSize=%d' % (path, page, self.PAGE_SIZE))
        items = (data or {}).get('items') or []
        for it in items:
            if not it.get('url') or not it.get('title'):
                continue
            params = stripPagerKeys(dict(cItem))
            params.update({'good_for_fav': True, 'category': 'list_match', 'title': self.cleanHtmlStr(it['title']), 'url': it['url'],
                           'icon': self._img(it.get('images')), 'desc': self._competition(it)})
            self.addDir(params)
        # no total in the answer; the list is read from f_kind / f_id + page, the url only carries the page for "Jump"
        addPagingItems(self, cItem, page, len(items) >= self.PAGE_SIZE, 0, API_URL + path + '#page={page}')

    def listMatch(self, cItem):
        data = self._api('page/%s' % urllib_quote(cItem['url'], safe=''))
        item = (data or {}).get('item') or {}
        if not item:
            return
        title = self.cleanHtmlStr(item.get('title') or cItem.get('title', ''))
        icon = self._img(item.get('images')) or cItem.get('icon', '')
        competition = cItem.get('desc', '')
        if not self._listVideoIds(cItem, self._entries(item.get('playlist')), title, competition, icon):
            SetIPTVPlayerLastHostError(_("No stream available"))

    ###################################################
    # Wideoteka / TV programmes
    ###################################################
    def _pageContent(self, path, contentType):
        data = self._api('page/%s' % urllib_quote(path, safe=''))
        for c in (((data or {}).get('item') or {}).get('content') or []):
            if isinstance(c, dict) and c.get('type') == contentType:
                return c
        return {}

    def listLibrary(self, cItem):
        ids = self._pageContent('/wideoteka', 'bpp_listing_video_library_groups').get('group_pages') or []
        if not ids:
            return
        data = self._api('video-library-group/list?' + '&'.join('ids=%s' % i for i in ids))
        groups = dict((g.get('id'), g) for g in ((data or {}).get('items') or []) if isinstance(g, dict))
        for gid in ids:
            g = groups.get(gid)
            if not g or not g.get('title'):
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_group', 'title': self.cleanHtmlStr(g['title']), 'f_id': gid,
                           'icon': self._bannerImg(g)})
            self.addDir(params)

    def listGroup(self, cItem):
        data = self._api('video-library-group/list?ids=%s' % cItem['f_id'])
        groups = (data or {}).get('items') or []
        if not groups:
            return
        for p in (groups[0].get('playlistItems') or []):
            if not p.get('id') or not p.get('title'):
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_playlist', 'title': self.cleanHtmlStr(p['title']), 'f_id': p['id'],
                           'icon': self._bannerImg(p) or cItem.get('icon', '')})
            self.addDir(params)

    def listPlaylist(self, cItem):
        # a playlist has one or more headed sections ("Skroty meczow", "Bramki", ...) of videos
        data = self._api('video-library-playlist/list?ids=%s' % cItem['f_id'])
        items = (data or {}).get('items') or []
        if not items:
            return
        sections = [c for c in (items[0].get('content') or []) if isinstance(c, dict) and self._entries(c.get('video'))]
        if len(sections) == 1:
            self._pagedVideos(cItem, self._entries(sections[0].get('video')))
            return
        for idx, c in enumerate(sections):
            title = self.cleanHtmlStr((c.get('headline') or {}).get('text') or '') or '%s %d' % (_('Part'), idx + 1)
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_section', 'title': '%s (%d)' % (title, len(self._entries(c.get('video')))), 'f_section': idx})
            self.addDir(params)

    def listSection(self, cItem):
        data = self._api('video-library-playlist/list?ids=%s' % cItem['f_id'])
        items = (data or {}).get('items') or []
        if not items:
            return
        sections = [c for c in (items[0].get('content') or []) if isinstance(c, dict) and self._entries(c.get('video'))]
        idx = cItem.get('f_section', 0)
        if idx < len(sections):
            self._pagedVideos(cItem, self._entries(sections[idx].get('video')))

    def listPrograms(self, cItem):
        ids = self._pageContent('/programy-tv', 'bpp_listing_tv_programs_playlist').get('programs') or []
        if not ids:
            return
        data = self._api('program-playlist/list?' + '&'.join('ids=%s' % i for i in ids))
        progs = dict((p.get('id'), p) for p in ((data or {}).get('items') or []) if isinstance(p, dict))
        for pid in ids:
            p = progs.get(pid)
            if not p or not p.get('title') or not p.get('video'):
                continue
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_program', 'title': '%s (%d)' % (self.cleanHtmlStr(p['title']), len(p['video'])),
                           'f_id': pid, 'icon': self._bannerImg(p)})
            self.addDir(params)

    def listProgram(self, cItem):
        data = self._api('program-playlist/list?ids=%s' % cItem['f_id'])
        items = (data or {}).get('items') or []
        if items:
            self._pagedVideos(cItem, self._entries(items[0].get('video')))

    def _pagedVideos(self, cItem, entries):
        page = cItem.get('page', 1)
        start = (page - 1) * self.PAGE_SIZE
        self._listVideoIds(cItem, entries[start:start + self.PAGE_SIZE])
        lastPage = (len(entries) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        tpl = '%s#%s:%s:{page}' % (SITE_URL, cItem.get('f_id', ''), cItem.get('f_section', ''))
        addPagingItems(self, cItem, page, len(entries) > start + self.PAGE_SIZE, lastPage, tpl)

    ###################################################
    # search
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        page = cItem.get('page', 1)
        cItem = dict(cItem, search_pattern=searchPattern)
        sts, data = self.getPage(SEARCH_URL % (urllib_quote_plus(searchPattern), page, self.PAGE_SIZE))
        if not sts:
            return
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return
        count = 0
        for r in (data.get('results') or []):
            v = r.get('independentVideo') if isinstance(r, dict) else None
            if not isinstance(v, dict) or not v.get('cutvVideoId'):
                continue
            self._addVideo(cItem, v['cutvVideoId'], v.get('cutvVideoHeader'), v.get('title') or '', '', self._competition(v), self._img(v.get('images')))
            count += 1
        try:
            total = int(data.get('total') or 0)
        except Exception:
            total = 0
        lastPage = (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE
        tpl = SEARCH_URL.replace('%d', '{page}', 1).replace('%d', str(self.PAGE_SIZE), 1) % urllib_quote_plus(searchPattern)
        addPagingItems(self, cItem, page, bool(count) and total > page * self.PAGE_SIZE, lastPage, tpl)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("LaczyNasPilka.getLinksForVideo [%s]" % cItem.get('vid'))
        vid = cItem.get('vid') or self.cm.ph.getSearchGroups(cItem.get('url', ''), r'/v/([0-9a-f\-]{36})')[0]
        if not vid:
            return []
        data = self._api('video/%s' % vid)
        item = (data or {}).get('item') or {}
        urlTab = []
        for media in (item.get('videoMedia') or []):
            if media.get('state', 'READY') != 'READY':
                continue
            for m in (media.get('media') or []):
                sub = m.get('subpath') or ''
                if not sub:
                    continue
                url = VIDEO_CDN_URL + sub.lstrip('/')
                meta = {'Referer': SITE_URL + '/', 'Origin': 'https://www.laczynaspilka.pl', 'User-Agent': self.HEADER['User-Agent']}
                if '.m3u8' in sub:
                    tab = getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)
                    for it in tab:
                        it['need_resolve'] = 0
                    urlTab.extend(tab or [{'name': 'HLS', 'url': self.up.decorateUrl(url, dict(meta, iptv_proto='m3u8')), 'need_resolve': 0}])
                else:
                    urlTab.append({'name': sub.rsplit('.', 1)[-1].upper(), 'url': self.up.decorateUrl(url, meta), 'need_resolve': 0})
            if urlTab:
                break
        if not urlTab:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get('raw_title', '')))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        other = {}
        if cItem.get('date'):
            other['released'] = cItem['date']
        if cItem.get('duration'):
            other['duration'] = cItem['duration']
        if cItem.get('competition'):
            other['category'] = cItem['competition']
        text = cItem.get('raw_title', '') or cItem.get('title', '')
        icon = cItem.get('icon', '')
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("LaczyNasPilka.handleService name[%s] category[%s]" % (name, category))
        searchPattern = self.currItem.get("search_pattern", searchPattern)
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_competitions':
            self.listCompetitions(self.currItem)
        elif category == 'list_subcompetitions':
            self.listSubcompetitions(self.currItem)
        elif category == 'list_leagues':
            self.listLeagues(self.currItem)
        elif category == 'list_plays':
            self.listPlays(self.currItem)
        elif category == 'list_matches':
            self.listMatches(self.currItem)
        elif category == 'list_match':
            self.listMatch(self.currItem)
        elif category == 'list_library':
            self.listLibrary(self.currItem)
        elif category == 'list_group':
            self.listGroup(self.currItem)
        elif category == 'list_playlist':
            self.listPlaylist(self.currItem)
        elif category == 'list_section':
            self.listSection(self.currItem)
        elif category == 'list_programs':
            self.listPrograms(self.currItem)
        elif category == 'list_program':
            self.listProgram(self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category', 'category': 'search_next_page'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, LaczyNasPilka(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('laczynaspilka')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
