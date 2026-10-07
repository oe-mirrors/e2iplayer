# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Basketball-Video (basketball-video.com) - NBA / WNBA / EuroLeague / College full game replays
# Site: uCoz catalogue like nfl-video.com (navigation groups, "?pageN" / "/<cat>-N" paging, /search/ needs the cookie)
# Game page: "Server #N XX" buttons -> link pages (nbaontv.com, nhlgamestoday.com, ...) with one hoster <iframe>
#   (ok.ru, vidara, ...), older games embed the hoster <iframe> directly. Resolved lazily in getVideoLinks.
#   Listing, search, link pages and INFO: tools/ucozcatalog.py
# 03.10.2026 - rebuild: basketball-video.com only (NFL-Video has its own host, MLBLive and
#   FullRaces are behind a Cloudflare challenge), watched flag, name normalisation, sidecar, search, INFO
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.ucozcatalog import UcozCatalogMixin, DATE_RE, DATE_NUM_RE
###################################################
# FOREIGN import
###################################################
import re
###################################################

LABEL_RE = r'\bFull (?:Game|Show)(?: Replays?)?(?:\s*(?:&amp;|&|and)\s*Highlights)?\b'


def GetConfigList():
    return []


def gettytul():
    return 'https://basketball-video.com/'


class BasketballVideo(UcozCatalogMixin, GenericFolderWatchedScraperMixin, CBaseHostClass):
    # navigation entries that answer 404 on the site
    UCOZ_DEAD_NAV = ('/wnba-video', '/videos/nba_news_tv_show/nba_tv_show/46', '/content-policy-dcma')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'basketball-video.com', 'cookie': 'basketball-video.cookie'})
        self.MAIN_URL = 'https://basketball-video.com/'
        self.DEFAULT_ICON_URL = self.MAIN_URL + '_pu/75/37346371.png'
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper('basketballvideocom')
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _normTitle(self, title):
        # "Knicks vs. Spurs - NBA Finals - Game 5 - Full Game Replay - June 13, 2026" -> "Knicks vs. Spurs - NBA Finals - Game 5 (2026-06-13)"
        # "Pistons vs Heat Full Game Replay March 19, 2025 NBA" -> "Pistons vs. Heat - NBA (2025-03-19)"
        if not IsMediaNamingNormalized():
            return title
        try:
            date = self._parseDate(title)
            out = re.sub(r'\s*\|\s*', ' - ', title)
            out = re.sub(DATE_RE, ' - ', out, flags=re.I)
            out = re.sub(DATE_NUM_RE, ' - ', out)
            out = re.sub(LABEL_RE, ' - ', out, flags=re.I)
            out = re.sub(r'\bvs\.?(?=\s)', 'vs.', out)
            keep = []
            for p in out.split(' - '):
                p = p.strip(' ,:-')
                if p and p.lower() not in [k.lower() for k in keep]:
                    keep.append(p)
            out = ' - '.join(keep) or title
            if date:
                out = '%s (%s)' % (out, date)
            return out
        except Exception:
            printExc()
        return title

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("BasketballVideo.getLinksForVideo [%s]" % cItem['url'])
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []
        body = self._gameBody(data)
        urlTab = []
        seen = set()

        def addLink(url, name):
            url = url.replace('&amp;', '&')
            if url.startswith('//'):
                url = 'https:' + url
            url = self.getFullUrl(url)
            if not self.cm.isValidUrl(url) or url in seen:
                return
            seen.add(url)
            urlTab.append({'name': name or self.up.getHostName(url), 'url': strwithmeta(url, {'Referer': cItem['url']}), 'need_resolve': 1})

        # day pages (Summer League, ...): a table "Matchup | OK | Filemoon" with one "Watch" button per hoster column
        for table in re.findall(r'<table[^>]+class="nhl-box".*?</table>', body, re.S):
            columns = []
            for row in re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.S):
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
                if 'nhl-game' not in row:
                    if 'href=' not in row and len(cells) > 1:
                        columns = [self.cleanHtmlStr(c) for c in cells]
                    continue
                game = self.cleanHtmlStr(cells[0]) if cells else ''
                for idx, cell in enumerate(cells[1:], 1):
                    column = columns[idx] if idx < len(columns) else ''
                    for url in re.findall(r'<a[^>]+href="([^"]+)"', cell):
                        addLink(url, ' - '.join([x for x in (game, column) if x]))
        body = re.sub(r'<table[^>]+class="nhl-box".*?</table>', '', body, flags=re.S)

        label = ''
        # walk the page in order: a short paragraph ("Server #2 (FM)", "Baskonia vs Olimpia Milan") names
        # the following buttons / players
        # (no zero-width re.split - Python 2.7 does not split on empty matches)
        for chunk in re.sub(r'(<p[\s>])', r'<!--split-->\1', body).split('<!--split-->'):
            para = self.cm.ph.getDataBeetwenNodes(chunk, ('<p', '>'), ('</p', '>'), False)[1]
            if para and '<br' not in para:
                heading = self.cleanHtmlStr(re.sub(r'<a[^>]+>.*?</a>', '', para, flags=re.S))
                if self._isLabel(heading):
                    label = heading
            anchors = re.findall(r'<a[^>]+class="su-button[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', chunk, re.S)
            frames = re.findall(r'<iframe[^>]+src="([^"]+)"', chunk, re.I)
            for url, text in anchors:
                text = self.cleanHtmlStr(text)
                if text.lower() == 'watch':
                    text = ''
                addLink(url, ' - '.join([x for x in (label, text) if x]))
            for url in frames:
                host = self.up.getHostName('https:' + url if url.startswith('//') else url)
                addLink(url, ' - '.join([x for x in (label, host) if x]))
        return self._finishLinks(cItem, urlTab)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, BasketballVideo(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('basketballvideocom')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
