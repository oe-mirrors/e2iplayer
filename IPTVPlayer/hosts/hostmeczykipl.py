# -*- coding: utf-8 -*-
# Meczyki.pl (meczyki.pl/skroty-meczow) - Polish sport portal, section "Skroty meczow": the latest football
#   match highlights (all leagues or per country / competition category), every match links to its official
#   YouTube highlight video(s)
# Site: Nuxt 3 app, the server-rendered pages carry the data in the __NUXT_DATA__ payload (devalue format),
#   the JSON API behind it (api.meczyki.pl) needs a login token - so only the 32 newest matches per category
#   are reachable (no paging); the highlight page of a match carries the YouTube ids (resolved via urlparser)
# Last Modified: 03.10.2026 - rewritten for the new site: watched flag, name normalisation, sidecar, INFO
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################
# FOREIGN import
###################################################
import re
###################################################

IMG_URL = 'https://pliki.meczyki.pl/'
DEVALUE_WRAPPERS = ('ShallowReactive', 'Reactive', 'Ref', 'ShallowRef')


def GetConfigList():
    return []


def gettytul():
    return 'https://www.meczyki.pl/skroty-meczow'


class MeczykiPL(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ('name', 'category', 'type', 'url', 'match_id', 'title', 'raw_title', 'icon', 'desc', 'date', 'competition', 'info')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'meczykipl', 'cookie': 'meczykipl.cookie'})
        self.MAIN_URL = 'https://www.meczyki.pl/'
        self.DEFAULT_ICON_URL = 'https://www.meczyki.pl/apple-touch-icon.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True}
        self.watchedHelper = IPTVWatchedHelper('meczykipl')
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type') == 'video' or cItem.get('category') == 'video':
                return 'video:%s' % cItem['match_id'] if cItem.get('match_id') else ''
            if cItem.get('category') == 'list_matches':
                return 'folder:%s' % cItem.get('f_cat', '0')
        except Exception:
            printExc()
        return ''

    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('type') == 'video':
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # __NUXT_DATA__ (devalue format: flat array, objects reference other entries by index)
    ###################################################
    def _nuxtData(self, html):
        # returns {key: index} of the page data entries plus the flat array
        try:
            raw = self.cm.ph.getDataBeetwenMarkers(html, 'id="__NUXT_DATA__">', '</script>', False)[1]
            arr = json_loads(raw)
            root = self._nuxtNode(arr, 0)
            if isinstance(root, dict) and isinstance(self._nuxtNode(arr, root.get('data', -1)), dict):
                return arr, self._nuxtNode(arr, root['data'])
        except Exception:
            printExc()
        return [], {}

    @staticmethod
    def _nuxtNode(arr, idx):
        # unwrap the reactive wrappers of one entry (no deep resolution)
        try:
            node = arr[idx]
            while isinstance(node, list) and len(node) == 2 and node[0] in DEVALUE_WRAPPERS:
                node = arr[node[1]]
            return node
        except Exception:
            return None

    def _nuxtResolve(self, arr, idx, depth=0):
        if not isinstance(idx, int) or idx < 0 or depth > 16:
            return None
        node = arr[idx]
        if isinstance(node, list):
            if node and node[0] in DEVALUE_WRAPPERS and len(node) == 2:
                return self._nuxtResolve(arr, node[1], depth + 1)
            if node and node[0] in ('EmptyArray', 'Set'):
                return [self._nuxtResolve(arr, i, depth + 1) for i in node[1:] if isinstance(i, int)]
            if node and node[0] in ('Map', 'Date', 'NaN', 'undefined', 'BigInt', 'RegExp'):
                return node[1] if node[0] == 'Date' and len(node) > 1 else None
            return [self._nuxtResolve(arr, i, depth + 1) for i in node]
        if isinstance(node, dict):
            return dict((k, self._nuxtResolve(arr, v, depth + 1)) for k, v in node.items())
        return node

    def _nuxtEntry(self, html, keyPrefix):
        arr, data = self._nuxtData(html)
        for key in data:
            if key.startswith(keyPrefix):
                entry = self._nuxtResolve(arr, data[key])
                if isinstance(entry, dict):
                    return entry
        return {}

    ###################################################
    # helpers
    ###################################################
    def _matchTitle(self, item):
        home = self.cleanHtmlStr((item.get('homeParticipant') or {}).get('displayName') or '')
        away = self.cleanHtmlStr((item.get('awayParticipant') or {}).get('displayName') or '')
        title = '%s - %s' % (home, away) if home and away else (home or away)
        if item.get('homeScore') is not None and item.get('awayScore') is not None and item.get('statusGroup') != 'scheduled':
            title = '%s %s:%s' % (title, item['homeScore'], item['awayScore'])
        return title

    def _addMatch(self, cItem, item):
        if not isinstance(item, dict) or not item.get('id') or not item.get('slug'):
            return False
        raw = self._matchTitle(item)
        if not raw:
            return False
        start = item.get('startTime') or ''
        date = start[:10] if len(start) >= 10 else ''
        clock = start[11:16] if len(start) >= 16 else ''
        competition = item.get('competition') or {}
        compName = self.cleanHtmlStr(competition.get('displayName') or '')
        country = self.cleanHtmlStr((competition.get('country') or {}).get('displayName') or '')
        stage = self.cleanHtmlStr((item.get('stage') or {}).get('displayName') or '')
        info = []
        if compName:
            info.append(compName if not country or country in compName else '%s (%s)' % (compName, country))
        if item.get('round') and stage:
            info.append('%s %s' % (stage, item['round']))
        elif item.get('round'):
            info.append('%s %s' % (_('Round'), item['round']))
        if date:
            info.append('%s %s' % (date, clock) if clock else date)
        title = '%s (%s)' % (raw, date) if IsMediaNamingNormalized() and date else raw
        # every match has a generated match graphic; competition logos exist only for leagues
        icon = '%slive-score/soccer/match/%s/original.png' % (IMG_URL, item['id'])
        params = dict(cItem)
        params.update({'good_for_fav': True, 'category': 'video', 'type': 'video', 'title': title, 'raw_title': raw, 'match_id': item['id'],
                       'url': '%swyniki-na-zywo/%s/%s/skrot' % (self.getMainUrl(), item['slug'], item['id']), 'icon': icon, 'date': date,
                       'competition': compName, 'info': ' | '.join(info), 'desc': ' | '.join(info)})
        self.addVideo(params)
        return True

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        sts, data = self.getPage(self.getFullUrl('/skroty-meczow'))
        if not sts:
            return
        params = dict(cItem)
        params.update({'good_for_fav': True, 'category': 'list_matches', 'title': _('Latest highlights'), 'f_cat': '0', 'url': self.getFullUrl('/skroty-meczow')})
        self.addDir(params)
        seen = set()
        for cid, body in re.findall(r'<a href="/skroty-meczow/[^"/]+/(\d+)/1"[^>]*>(.*?)</a>', data, re.S):
            title = self.cleanHtmlStr(body) or self.cm.ph.getSearchGroups(body, r'alt="([^"]+)"')[0]
            if not title or cid in seen:
                continue
            seen.add(cid)
            icon = self.cm.ph.getSearchGroups(body, r'src="(https?://[^"]+)"')[0]
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'list_matches', 'title': title, 'f_cat': cid, 'icon': icon,
                           'url': self.getFullUrl('/skroty-meczow/kategoria/%s/1' % cid)})
            self.addDir(params)

    def listMatches(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        entry = self._nuxtEntry(data, 'shortcut-matches')
        count = 0
        for item in (entry.get('data') or []):
            if self._addMatch(cItem, item):
                count += 1
        if not count:
            SetIPTVPlayerLastHostError(_("No stream available"))

    ###################################################
    # links
    ###################################################
    def _highlightVideos(self, data):
        # the highlight entry of the match page: {"data": {"videos": [{"type": "youtube", "linkId": ...}]}}
        arr, nuxt = self._nuxtData(data)
        for key in nuxt:
            entry = self._nuxtResolve(arr, nuxt[key])
            if not isinstance(entry, dict):
                continue
            payload = entry.get('data') if isinstance(entry.get('data'), dict) else {}
            if 'highlights' in ((entry.get('info') or {}).get('route') or '') or isinstance(payload.get('videos'), list):
                return [v for v in (payload.get('videos') or []) if isinstance(v, dict)]
        return []

    def getLinksForVideo(self, cItem):
        printDBG("MeczykiPL.getLinksForVideo [%s]" % cItem.get('url'))
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        urlTab = []
        skipped = []
        videos = self._highlightVideos(data)
        for idx, v in enumerate(videos):
            vtype = (v.get('type') or (v.get('additionalData') or {}).get('type') or '').lower()
            vid = v.get('linkId') or ((v.get('additionalData') or {}).get('data') or {}).get('id') or ''
            url = ''
            if vtype == 'youtube' and vid:
                url = 'https://www.youtube.com/watch?v=%s' % vid
            elif v.get('html'):
                # embed code or just a link to an external site (polsatsport.pl, ...)
                url = self.cm.ph.getSearchGroups(v['html'], r'''<iframe[^>]+src=['"]([^'"]+)['"]''')[0]
                if not url:
                    url = self.cm.ph.getSearchGroups(v['html'], r'''<a[^>]+href=['"](https?://[^'"]+)['"]''')[0]
            if not self.cm.isValidUrl(url):
                continue
            if 1 != self.up.checkHostSupport(url):
                skipped.append(self.up.getHostName(url) or vtype)
                continue
            name = self.cleanHtmlStr(v.get('title') or '') or self.up.getHostName(url)
            if len(videos) > 1:
                name = '%d. %s' % (idx + 1, name)
            urlTab.append({'name': name, 'url': url, 'need_resolve': 1})
        if not urlTab:
            if skipped:
                SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ', '.join(skipped))
            else:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get('raw_title', '')))

    def getVideoLinks(self, videoUrl):
        printDBG("MeczykiPL.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        links = self.up.getVideoLinkExt(videoUrl)
        if links and self._geoBlocked(videoUrl, links[0].get('url', '')):
            SetIPTVPlayerLastHostError(_("This content is not available in your region."))
            return []
        return decorateResolvedLinkItems(links, sidecar)

    def _geoBlocked(self, pageUrl, videoUrl):
        # polsatsport.pl highlights are "regionsAllowed": "PL": outside Poland the CDN (redirector.redefine.pl
        # -> ipla.pluscdn.pl) answers the mp4 with 403 - check the first bytes instead of handing a dead link
        # to the player
        if 'polsatsport.pl' not in self.up.getDomain(pageUrl) or not self.cm.isValidUrl(videoUrl):
            return False
        meta = strwithmeta(videoUrl).meta
        header = dict((key, meta[key]) for key in ('User-Agent', 'Referer', 'Origin') if meta.get(key))
        header['Range'] = 'bytes=0-1023'
        _sts, data = self.cm.getPage(videoUrl, {'header': header, 'max_data_size': 1024, 'with_metadata': True, 'timeout': 15})
        status = (getattr(data, 'meta', None) or self.cm.meta or {}).get('status_code')
        printDBG("MeczykiPL._geoBlocked HTTP %s" % status)
        return status == 403

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        other = {}
        if cItem.get('date'):
            other['released'] = cItem['date']
        if cItem.get('competition'):
            other['category'] = cItem['competition']
        lines = [cItem.get('raw_title', '') or cItem.get('title', ''), cItem.get('info', '')]
        sts, data = self.getPage(cItem.get('url', '')) if cItem.get('type') == 'video' and cItem.get('url') else (False, '')
        if sts:
            match = self._nuxtEntry(data, 'soccer-match-')
            if isinstance(match.get('match'), dict):
                match = match['match'].get('data') or {}
            ref = match.get('referee') or {}
            if ref.get('displayName'):
                lines.append('%s: %s' % (_('Referee'), self.cleanHtmlStr(ref['displayName'])))
            if match.get('homeFormation') and match.get('awayFormation'):
                lines.append('%s: %s / %s' % (_('Formations'), match['homeFormation'], match['awayFormation']))
            venue = (match.get('venue') or {}).get('displayName') if isinstance(match.get('venue'), dict) else ''
            if venue:
                lines.append('%s: %s' % (_('Venue'), self.cleanHtmlStr(venue)))
            videos = self._highlightVideos(data)
            if videos:
                lines.append('%s: %s' % (_('Videos'), ', '.join([self.cleanHtmlStr(v.get('title') or v.get('type') or '') for v in videos])))
        icon = cItem.get('icon', '')
        return [{'title': cItem.get('title', ''), 'text': '[/br]'.join([x for x in lines if x]), 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("MeczykiPL.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_matches':
            self.listMatches(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MeczykiPL(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('meczykipl')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
