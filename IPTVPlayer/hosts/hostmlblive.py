# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# MLBLive (mlblive.net) - MLB full game replays, World Series, World Baseball Classic, MLB TV shows
# Site: uCoz catalogue like basketball-video.com / nfl-video.com (navigation groups, "?pageN" paging, /search/),
#   behind Cloudflare that only lets Chrome's TLS fingerprint through -> every page via curl-impersonate
# Game page: "Server #N" headings with the hoster <iframe> (ok.ru, vidara, filemoon, ...) or "Watch" buttons
#   to link pages of the site (mlblive.net/01-NNN) with one hoster <iframe>. Resolved lazily in getVideoLinks.
#   Listing, search, links and INFO: tools/ucozcatalog.py
# 03.10.2026 - new host (was a sub-menu of basketball-video.com): watched flag, name
#   normalisation, sidecar, search, INFO, curl-impersonate for the Cloudflare check
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.ucozcatalog import UcozCatalogMixin, DATE_RE, DATE_NUM_RE, YEAR_RE
###################################################
# FOREIGN import
###################################################
import re
###################################################

LABEL_RE = r'\bFull (?:Game|Show)(?: Replays?)?(?:\s*(?:&amp;|&|and)\s*Highlights)?(?:\s+Online)?(?:\s+Free)?\b|\bOnline Free\b'


def GetConfigList():
    return []


def gettytul():
    return 'https://mlblive.net/'


class MLBLive(UcozCatalogMixin, GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'mlblive.net', 'cookie': 'mlblive.cookie'})
        self.MAIN_URL = 'https://mlblive.net/'
        self.DEFAULT_ICON_URL = ''
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        # Cloudflare there blocks every non-Chrome TLS fingerprint: curl-impersonate, no cookie needed
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True,
                              'cookiefile': self.COOKIE_FILE, 'impersonate': True}
        self.watchedHelper = IPTVWatchedHelper('mlblive')
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(url, addParams, post_data)

    def _normTitle(self, title):
        # "Seattle Mariners @ Boston Red Sox - MLB Full Game Replay - September 2, 2026" -> "Seattle Mariners vs. Boston Red Sox - MLB (2026-09-02)"
        # "Milwaukee Brewers vs Chicago Cubs Game 3 Full Game Replay October 8, 2025 MLB Divisional Series"
        #   -> "Milwaukee Brewers vs. Chicago Cubs - MLB Divisional Series - Game 3 (2025-10-08)"
        if not IsMediaNamingNormalized():
            return title
        try:
            date = self._parseDate(title)
            out = re.sub(r'\s*\|\s*', ' - ', title)
            out = re.sub(DATE_RE, ' - ', out, flags=re.I)
            out = re.sub(DATE_NUM_RE, ' - ', out)
            if not date:
                date = self.cm.ph.getSearchGroups(out, YEAR_RE)[0]
            out = re.sub(YEAR_RE, ' - ', out)
            out = re.sub(LABEL_RE, ' - ', out, flags=re.I)
            game = ''
            m = re.search(r'\bGame\s+(\d+)\b', out)
            if m:
                game = 'Game %s' % m.group(1)
                out = out[:m.start()] + ' - ' + out[m.end():]
            out = re.sub(r'\s+@\s+', ' vs. ', out)
            out = re.sub(r'\bvs\.?(?=\s)', 'vs.', out)
            # "Dodgers vs. Blue Jays MLB World Series" -> "Dodgers vs. Blue Jays - MLB World Series"
            out = re.sub(r'(?<!MLB)\s+(?=(?:MLB|World Series|World Baseball Classic|[AN]L[CD]S)\b)', ' - ', out)
            keep = []
            for p in out.split(' - '):
                p = re.sub(r'\s+', ' ', p).strip(' ,:-')
                if p and p.lower() not in [k.lower() for k in keep]:
                    keep.append(p)
            # "... - MLB - MLB Wild Card" -> "... - MLB Wild Card"
            if 'MLB' in keep and len([k for k in keep if 'MLB' in k]) > 1:
                keep.remove('MLB')
            if game:
                keep.append(game)
            out = ' - '.join(keep) or title
            if date:
                out = '%s (%s)' % (out, date)
            return out
        except Exception:
            printExc()
        return title


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MLBLive(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('mlblive')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
