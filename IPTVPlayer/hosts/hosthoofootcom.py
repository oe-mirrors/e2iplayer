# -*- coding: utf-8 -*-
LAST_MODIFIED = "13.11.2026"
# hoofoot.net (mirror of hoofoot.com, which sits behind a Cloudflare challenge):
#   - /matches-manifest.json -> every match + hasHighlights flag
#   - match page -> one player tab per source (EXT, SH, ...) with a token and
#     an encoded fallback url (data-fb)
#   - token "r2:<id>" -> cdn.dailyvid.click/videos/<id>/index.json (HLS master
#     or MP4 qualities), any other token -> /api/resolve?v=<token> (needs the
#     match page as Referer)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError, TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

###################################################
# FOREIGN import
###################################################
import base64
import re
import time
###################################################

MONTHS = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
          'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12}

PER_PAGE = 50


def GetConfigList():
    return []


def gettytul():
    return 'https://hoofoot.net/'


class HoofootCom(GenericFolderWatchedScraperMixin, CBaseHostClass):
    R2_BASE = 'https://cdn.dailyvid.click/videos/'
    FB_KEY = b'hf.v1.fallback'
    # what a favourite keeps: the match page plus what the sidecar of a download needs
    FAV_FIELDS = ('url', 'title', 'icon', 'desc')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'hoofoot.net'})
        self.MAIN_URL = 'https://hoofoot.net/'
        # the site's favicon is the Astro framework logo - the host's own tile instead
        self.DEFAULT_ICON_URL = 'file://' + GetIconDir('PlayerSelector/hoofootcom135.png')
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER}
        self.manifest = None
        self.manifestFailed = False
        self.watchedHelper = IPTVWatchedHelper('hoofoot')
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _getJson(self, url, referer, extraHeaders=None):
        header = dict(self.HEADER)
        header.update({'Referer': referer, 'Accept': 'application/json, text/plain, */*'})
        if extraHeaders:
            header.update(extraHeaders)
        sts, data = self.getPage(url, {'header': header})
        if not sts:
            printDBG("HoofootCom._getJson failed [%s]" % url)
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
            return None

    # ---------------------------------------------------------------- helpers
    def _getManifest(self):
        if self.manifest is not None:
            return self.manifest
        self.manifestFailed = True
        sts, data = self.getPage(self.getFullUrl('matches-manifest.json'))
        if not sts:
            return []
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []
        self.manifestFailed = False
        manifest = []
        for mid, item in data.items():
            url = item.get('url', '')
            if not item.get('hasHighlights') or not url:
                continue
            parts = url.strip('/').split('/')
            if len(parts) < 3:
                continue
            league = parts[1]
            slug = parts[2]
            teams, sep, datePart = slug.rpartition('-highlights-')
            if not sep:
                teams, datePart = slug, ''
            title = teams.replace('-vs-', ' vs ').replace('-', ' ').strip()
            title = ' '.join(w if w.lower() == 'vs' else w.capitalize() for w in title.split())
            sortKey = self._dateSortKey(datePart)
            manifest.append({
                'id': mid,
                'league': league,
                'title': title,
                'date': datePart.replace('-', ' ').title(),
                'isoDate': '%04d-%02d-%02d' % sortKey if sortKey[0] else '',
                'sortKey': sortKey,
                'url': self.getFullUrl(url),
                'icon': self.getFullUrl('/og/%s/%s.png' % (league, slug)),
            })
        manifest.sort(key=lambda x: x['sortKey'], reverse=True)
        # only a list with matches is kept for the session: a failed load or an empty list (the site switches its
        # highlights off from time to time) is fetched again next time
        self.manifest = manifest or None
        return manifest

    def _noHighlights(self):
        if self.manifestFailed:
            SetIPTVPlayerLastHostError('hoofoot.net could not be loaded - check the connection and try again.')
        else:
            SetIPTVPlayerLastHostError('hoofoot.net has no highlights at the moment - the site switches them off from time to time, try again later.')

    @staticmethod
    def _dateSortKey(datePart):
        m = re.match(r'([a-z]+)-(\d+)-(\d+)', datePart or '')
        if not m:
            return (0, 0, 0)
        return (int(m.group(3)), MONTHS.get(m.group(1), 0), int(m.group(2)))

    @staticmethod
    def _prettyLeague(league):
        return league.replace('-', ' ').title().replace('Fifa', 'FIFA').replace('Uefa', 'UEFA').replace('Caf', 'CAF').replace('Afc', 'AFC').replace('Efl', 'EFL')

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get('search_item') or cItem.get('name') == 'history':
                return ''
            if cItem.get('type') == 'video':
                return 'video:%s' % cItem['url'] if cItem.get('url') else ''
            if cItem.get('category') == 'league_items' and cItem.get('league'):
                return 'folder:league:%s' % cItem['league']
        except Exception:
            printExc()
        return ''

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get('page', 1) or 1))
        except (TypeError, ValueError):
            return 1

    def _addMatches(self, cItem, items):
        page = self._page(cItem)
        chunk = items[(page - 1) * PER_PAGE:page * PER_PAGE]
        for it in chunk:
            params = stripPagerKeys(dict(cItem))
            params.update({'good_for_fav': True, 'title': normalizeMediathekTitle(it['title'], date=it['isoDate']),
                           'url': it['url'], 'icon': it['icon'],
                           'desc': '%s | %s' % (self._prettyLeague(it['league']), it['date'])})
            self.addVideo(params)
        lastPage = (len(items) + PER_PAGE - 1) // PER_PAGE
        # the lists are cut from the manifest by cItem['page']; the template only enables "Jump"
        addPagingItems(self, cItem, page, len(items) > page * PER_PAGE, lastPage, self.getFullUrl('matches-manifest.json?page={page}'))

    # ---------------------------------------------------------------- listings
    def listMainMenu(self, cItem):
        MENU = [{'category': 'latest', 'title': _('Latest highlights')},
                {'category': 'leagues', 'title': _('Competitions')}]
        self.listsTab(MENU + self.searchItems(), cItem)

    def listLatest(self, cItem):
        items = self._getManifest()
        if not items:
            self._noHighlights()
        self._addMatches(cItem, items)

    def listLeagues(self, cItem):
        counts = {}
        items = self._getManifest()
        if not items:
            self._noHighlights()
        for it in items:
            counts[it['league']] = counts.get(it['league'], 0) + 1
        for league in sorted(counts):
            params = dict(cItem)
            params.update({'category': 'league_items', 'league': league, 'page': 1,
                           'title': '%s (%d)' % (self._prettyLeague(league), counts[league])})
            self.addDir(params)

    def listLeagueItems(self, cItem):
        items = [it for it in self._getManifest() if it['league'] == cItem['league']]
        if not items:
            self._noHighlights()
        self._addMatches(cItem, items)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HoofootCom.listSearchResult [%s]" % searchPattern)
        words = [w for w in re.split(r'\s+', searchPattern.lower().strip()) if w]
        manifest = self._getManifest()
        items = [it for it in manifest if all(w in it['title'].lower() for w in words)]
        if not manifest:
            self._noHighlights()
        elif not items:
            SetIPTVPlayerLastHostError(_('No items found'))
        self._addMatches(cItem, items)

    # ---------------------------------------------------------------- playback
    def _unfb(self, s):
        # data-fb: url-safe base64 of the fallback url, XOR'ed with FB_KEY
        try:
            s = (s or '').replace('-', '+').replace('_', '/')
            s += '=' * (-len(s) % 4)
            raw = bytearray(base64.b64decode(s))
            key = bytearray(self.FB_KEY)
            url = bytes(bytearray([b ^ key[i % len(key)] for i, b in enumerate(raw)])).decode('utf-8', 'ignore')
            return url if url.startswith('https://') else ''
        except Exception:
            printExc()
            return ''

    def _resolveToken(self, token, referer):
        js = self._getJson(self.getFullUrl('/api/resolve?v=%s' % urllib_quote(token, safe='')), referer,
                           {'X-Requested-With': 'XMLHttpRequest', 'Origin': self.getMainUrl().rstrip('/')})
        if not js or not js.get('url'):
            return []
        return [(js['url'], js.get('type', ''), '')]

    def _resolveR2(self, vid, referer):
        # returns [(url, type, name)] - [] when the video is gone, None when it is encrypted (v >= 2)
        base = self.R2_BASE + vid + '/'
        d = self._getJson(base + 'index.json?t=%d' % int(time.time() // 600), referer)
        if not d:
            return []
        printDBG("HoofootCom._resolveR2 vid[%s] type[%s] v[%s]" % (vid, d.get('type'), d.get('v')))
        if d.get('type') == 'hls':
            return [(base + (d.get('master') or 'master.m3u8'), 'm3u8', '')]
        if d.get('v', 0) >= 2:
            return None
        quals = [q for q in (d.get('qualities') or []) if q.get('name') and q.get('height')]
        if not quals:
            return [(base + '720p.mp4', 'mp4', '720p')]
        quals.sort(key=lambda q: q['height'], reverse=True)
        return [(base + q['name'] + '.mp4', 'mp4', '%sp' % q['height']) for q in quals]

    def _expandStreams(self, streams, referer):
        urlTab = []
        for streamUrl, streamType, name in streams:
            streamUrl = strwithmeta(streamUrl, {'User-Agent': self.HEADER['User-Agent'], 'Referer': referer})
            if streamType == 'm3u8' or '.m3u8' in streamUrl:
                urlTab.extend(getDirectM3U8Playlist(streamUrl, checkExt=False, sortWithMaxBitrate=99999999))
            else:
                urlTab.append({'name': name or 'MP4', 'url': streamUrl})
        return urlTab

    def getLinksForVideo(self, cItem):
        # one row per player tab (EXT, SH, ...); the qualities come with getVideoLinks()
        printDBG("HoofootCom.getLinksForVideo [%s]" % cItem)
        urlTab = []
        matchUrl = cItem['url']
        sts, data = self.getPage(matchUrl)
        if not sts:
            return urlTab
        section = self.cm.ph.getDataBeetwenMarkers(data, 'id="in-page-player"', '</section>', False)[1] or data
        for attrs, label in re.findall(r'<button\b([^>]*hf-tab[^>]*)>([^<]*)</button>', section):
            m = re.search(r'data-token="([^"]+)"', attrs)
            if not m:
                continue
            name = self.cleanHtmlStr(label) or _('Highlights')
            fb = re.search(r'data-fb="([^"]+)"', attrs)
            fbUrl = self._unfb(fb.group(1)) if fb else ''
            # token|match page (Referer for the resolver)|fallback url
            urlTab.append({'name': name, 'url': '%s|%s|%s' % (m.group(1), matchUrl, fbUrl), 'need_resolve': 1})
        if not urlTab:
            SetIPTVPlayerLastHostError(_('No streams are available for this title yet.'))
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("HoofootCom.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        # the rows of getLinksForVideo: token|match page (Referer)|fallback url
        token, referer, fbUrl = (str(videoUrl).split('|') + ['', ''])[:3]
        referer = referer or self.getMainUrl()
        if token.startswith('r2:'):
            streams = self._resolveR2(token[3:], referer)
        else:
            streams = self._resolveToken(token, referer)
        if not streams and fbUrl:
            # encrypted R2 video (needs Turnstile in the browser) or the resolver failed
            streams = [(fbUrl, 'm3u8' if '.m3u8' in fbUrl else 'mp4', '')]
        return decorateResolvedLinkItems(self._expandStreams(streams or [], referer), sidecar)

    # ---------------------------------------------------------------- INFO
    def getArticleContent(self, cItem):
        printDBG("HoofootCom.getArticleContent [%s]" % cItem)
        desc = cItem.get('desc', '')
        other = {}
        parts = [p.strip() for p in desc.split('|')]
        if len(parts) >= 2:
            other['genre'] = parts[0]
            other['released'] = parts[-1]
        icon = cItem.get('icon', '')
        return [{'title': self.cleanHtmlStr(cItem.get('title', '')), 'text': desc,
                 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    # ---------------------------------------------------------------- favourites
    def getFavouriteData(self, cItem):
        if not cItem.get('url'):
            return ''   # pager rows
        return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))

    def getLinksForFavourite(self, fav_data):
        if not fav_data:
            return []
        try:
            cItem = json_loads(fav_data)
        except Exception:
            cItem = None
        if not isinstance(cItem, dict):
            cItem = {'url': fav_data}   # a favourite of the first version: the bare match page url
        return self.getLinksForVideo(cItem)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if refresh:
            self.manifest = None   # "refresh" loads the list of matches again
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        printDBG("handleService: name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({'name': 'category'})
        elif category == 'latest':
            self.listLatest(self.currItem)
        elif category == 'leagues':
            self.listLeagues(self.currItem)
        elif category == 'league_items':
            self.listLeagueItems(self.currItem)
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
        CHostBase.__init__(self, HoofootCom(), True, favouriteTypes=[CDisplayListItem.TYPE_VIDEO])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('hoofoot')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
