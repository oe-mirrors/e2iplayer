# -*- coding: utf-8 -*-
# Last Modified: 05.09.2026
#
# hoofoot.com moved to a new site generation (React/Astro, Cloudflare
# challenge on the .com apex). The .net mirror serves the same content
# without a challenge and exposes clean JSON:
#   - /matches-manifest.json           -> every match + hasHighlights flag
#   - /full-matches/<league>/<slug>/   -> SSG match page carrying the player
#   - /api/resolve?v=<token>           -> {"url": <m3u8|mp4>, "type": ...}
# The highlight stream is a plain, CORS-open m3u8/mp4 - no hoster needed.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import re
###################################################

MONTHS = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
          'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12}

PER_PAGE = 50


def GetConfigList():
    return []


def gettytul():
    return 'https://hoofoot.net/'


class HoofootCom(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'hoofoot.net', 'cookie': 'hoofootcom.cookie'})
        self.MAIN_URL = 'https://hoofoot.net/'
        self.DEFAULT_ICON_URL = 'https://hoofoot.net/favicon.svg'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.manifest = None

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    # ---------------------------------------------------------------- helpers
    def _getManifest(self):
        if self.manifest is not None:
            return self.manifest
        self.manifest = []
        sts, data = self.getPage(self.getFullUrl('matches-manifest.json'))
        if not sts:
            return self.manifest
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return self.manifest
        for mid, item in data.items():
            url = item.get('url', '')
            if not item.get('hasHighlights') or not url:
                continue
            parts = url.strip('/').split('/')
            if len(parts) < 3:
                continue
            league = parts[1]
            slug = parts[2]
            teams, _sep, datePart = slug.rpartition('-highlights-')
            if not teams:
                teams = slug
            title = teams.replace('-vs-', ' vs ').replace('-', ' ').strip()
            title = re.sub(r'\bvs\b', 'vs', title, flags=re.I)
            title = ' '.join(w if w == 'vs' else w.capitalize() for w in title.split())
            self.manifest.append({
                'id': mid,
                'league': league,
                'title': title,
                'date': datePart.replace('-', ' ').title(),
                'sortKey': self._dateSortKey(datePart),
                'url': self.getFullUrl(url),
                'icon': self.getFullUrl('/og/%s/%s.png' % (league, slug)),
            })
        self.manifest.sort(key=lambda x: x['sortKey'], reverse=True)
        return self.manifest

    @staticmethod
    def _dateSortKey(datePart):
        m = re.match(r'([a-z]+)-(\d+)-(\d+)', datePart or '')
        if not m:
            return (0, 0, 0)
        return (int(m.group(3)), MONTHS.get(m.group(1), 0), int(m.group(2)))

    @staticmethod
    def _prettyLeague(league):
        return league.replace('-', ' ').title().replace('Fifa', 'FIFA').replace('Uefa', 'UEFA').replace('Caf', 'CAF').replace('Afc', 'AFC').replace('Efl', 'EFL')

    def _addMatches(self, cItem, items):
        page = cItem.get('page', 0)
        chunk = items[page * PER_PAGE:(page + 1) * PER_PAGE]
        for it in chunk:
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': it['title'],
                           'url': it['url'], 'icon': it['icon'],
                           'desc': '%s | %s' % (self._prettyLeague(it['league']), it['date'])})
            self.addVideo(params)
        if len(items) > (page + 1) * PER_PAGE:
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    # ---------------------------------------------------------------- listings
    def listMainMenu(self, cItem):
        MENU = [{'category': 'latest', 'title': _('Latest highlights')},
                {'category': 'leagues', 'title': _('Competitions')}]
        self.listsTab(MENU + self.searchItems(), cItem)

    def listLatest(self, cItem):
        self._addMatches(cItem, self._getManifest())

    def listLeagues(self, cItem):
        counts = {}
        for it in self._getManifest():
            counts[it['league']] = counts.get(it['league'], 0) + 1
        for league in sorted(counts):
            params = dict(cItem)
            params.update({'category': 'league_items', 'league': league, 'page': 0,
                           'title': '%s (%d)' % (self._prettyLeague(league), counts[league])})
            self.addDir(params)

    def listLeagueItems(self, cItem):
        items = [it for it in self._getManifest() if it['league'] == cItem['league']]
        self._addMatches(cItem, items)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HoofootCom.listSearchResult [%s]" % searchPattern)
        words = [w for w in re.split(r'\s+', searchPattern.lower().strip()) if w]
        items = []
        for it in self._getManifest():
            hay = it['title'].lower()
            if all(w in hay for w in words):
                items.append(it)
        self._addMatches(cItem, items)

    # ---------------------------------------------------------------- playback
    def getLinksForVideo(self, cItem):
        printDBG("HoofootCom.getLinksForVideo [%s]" % cItem)
        urlTab = []
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return urlTab
        section = self.cm.ph.getDataBeetwenMarkers(data, 'id="in-page-player"', '</section>', False)[1] or data
        for attrs, label in re.findall(r'<button\b([^>]*hf-tab[^>]*)>([^<]*)</button>', section):
            m = re.search(r'data-token="([^"]+)"', attrs)
            if not m:
                continue
            name = self.cleanHtmlStr(label) or _('Highlights')
            urlTab.append({'name': name, 'url': m.group(1), 'need_resolve': 1})
        return urlTab

    def getVideoLinks(self, videoUrl):
        printDBG("HoofootCom.getVideoLinks [%s]" % videoUrl)
        urlTab = []
        if not videoUrl.startswith('http'):
            sts, data = self.getPage(self.getFullUrl('/api/resolve?v=%s' % videoUrl))
            if not sts:
                return urlTab
            try:
                js = json_loads(data)
            except Exception:
                printExc()
                return urlTab
            streamUrl = js.get('url', '')
            streamType = js.get('type', '')
        else:
            streamUrl, streamType = videoUrl, ''

        if not streamUrl:
            return urlTab
        streamUrl = strwithmeta(streamUrl, {'User-Agent': self.HEADER['User-Agent'], 'Referer': self.getMainUrl()})
        if streamType == 'm3u8' or '.m3u8' in streamUrl:
            urlTab.extend(getDirectM3U8Playlist(streamUrl, checkExt=False, sortWithMaxBitrate=99999999))
        else:
            urlTab.append({'name': 'MP4', 'url': streamUrl})
        return urlTab

    # ---------------------------------------------------------------- favourites
    def getFavouriteData(self, cItem):
        return cItem['url']

    def getLinksForFavourite(self, fav_data):
        return self.getLinksForVideo({'url': fav_data})

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
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


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, HoofootCom(), True, favouriteTypes=[CDisplayListItem.TYPE_VIDEO])
