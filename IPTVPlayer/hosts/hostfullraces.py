# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# FullRaces (fullraces.com) - Formula 1 (sessions, archive 2000-2018), NASCAR, IndyCar, WSBK, WRC, F2, F3,
#   Formula E, F1 Academy and MotoGP ("Other") full race replays
# Site: uCoz catalogue like basketball-video.com / nfl-video.com (navigation groups, "?pageN" paging, /search/),
#   behind Cloudflare that only lets Chrome's TLS fingerprint through -> every page via curl-impersonate
# Race page: a player block with one button per source (ok.ru, Dailymotion parts, filemoon/byse) and/or
#   headings with hoster <iframe>s and "Part N" buttons (Dailymotion, vidara, ...). Resolved lazily in getVideoLinks.
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
from Plugins.Extensions.IPTVPlayer.tools.ucozcatalog import UcozCatalogMixin, parseDate, MONTHS, DATE_RE, DATE_NUM_RE, YEAR_RE
###################################################
# FOREIGN import
###################################################
import re
###################################################

# "May 29-31, 2026", "July 30 - August 2, 2026" (rallies, race weekends): the first day counts
DATE_RANGE_RE = r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\s*-\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?\d{1,2},?\s+(\d{4})\b'
LABEL_RE = r'\bFull (?:Race|Show)?\s*Replays?\b|\bFull Race\b|\bOnline Free\b'
# series: (pattern, name) - the first one found names the race, all of them are cut from the event name
SERIES = ((r'\bF1\s+Academy\b', 'F1 Academy'),
          (r'\bFormula\s*E\b', 'Formula E'),
          (r'\bFormula\s*2\b(?:\s+Championship)?|\bF2(?:\s+Championship)?\b', 'Formula 2'),
          (r'\bFormula\s*3\b(?:\s+Championship)?|\bF3(?:\s+Championship)?\b', 'Formula 3'),
          (r'\bFormula\s*(?:1|One)\b|\bF1\b', 'Formula 1'),
          (r'\bMotoGP\b', 'MotoGP'),
          (r'\bMoto2\b', 'Moto2'),
          (r'\bMoto3\b', 'Moto3'),
          (r'\bWSBK\b|\bWorldSBK\b|\bSuperbike World Championship\b', 'WorldSBK'),
          (r'\bWRC\b|\bWorld Rally Championship\b', 'WRC'),
          (r'\bNASCAR(?:\s+Cup\s+Series)?\b', 'NASCAR'),
          (r'\bIndy\s*Car\b', 'IndyCar'),
          (r'\bFormula\s*4\b', ''))
# a session at the start of the title or as its own " - " part ("RACE - F1 2026 - ...", "Qualifying Formula 1 ...")
SESSION_RE = (r'(?:Sprint\s+Qualifying|Sprint\s+Shootout|Sprint\s+Race|Feature\s+Race|Sprint|Qualifying|Race|'
              r'(?:1st|2nd|3rd|First|Second|Third)\s+Practice|Free\s+Practice\s*\d?|FP\d|Practice\s*\d?|Warm[- ]?Up|'
              r'Pre[- ]Race(?:\s+Show)?|Post[- ]Race(?:\s+Show)?|F1\s+Show|(?:Drivers\s+)?Press\s+Conference|Season\s+Review|Shakedown)')


def GetConfigList():
    return []


def gettytul():
    return 'https://fullraces.com/'


class FullRaces(UcozCatalogMixin, GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'fullraces.com', 'cookie': 'fullraces.cookie'})
        self.MAIN_URL = 'https://fullraces.com/'
        self.DEFAULT_ICON_URL = ''
        self.HEADER = self.cm.getDefaultHeader(browser='chrome')
        # Cloudflare there blocks every non-Chrome TLS fingerprint: curl-impersonate, no cookie needed
        self.defaultParams = {'header': self.HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True,
                              'cookiefile': self.COOKIE_FILE, 'impersonate': True}
        self.watchedHelper = IPTVWatchedHelper('fullraces')
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(url, addParams, post_data)

    def _mainLinks(self, links):
        # MotoGP is only reachable through the "Other" category of its posts, not in the navigation
        if not [u for u, t in links if u.rstrip('/').endswith('/other')]:
            links.append((self.getFullUrl('/other'), 'MotoGP & Other'))
        return links

    ###################################################
    # naming
    ###################################################
    def _parseDate(self, text):
        m = re.search(DATE_RANGE_RE, text or '', re.I)
        if m:
            return '%s-%02d-%02d' % (m.group(3), MONTHS[m.group(1).lower()[:3]], int(m.group(2)))
        return parseDate(text)

    def _normTitle(self, title):
        # "RACE - F1 2026 - Azerbaijan Grand Prix - Full Race Replay - September 26, 2026 - Formula 1"
        #   -> "Formula 1 - Azerbaijan Grand Prix - Race (2026-09-26)"
        # "WRC Rally Japan - Full Race Replay - May 29-31, 2026 - World Rally Championship" -> "WRC - Rally Japan (2026-05-29)"
        # "2014 F1 Abu Dhabi Grand Prix Full Race Replay" -> "Formula 1 - Abu Dhabi Grand Prix (2014)"
        if not IsMediaNamingNormalized():
            return title
        try:
            date = self._parseDate(title)
            out = re.sub(r'\s*\|\s*', ' - ', title)
            out = re.sub(DATE_RANGE_RE, ' - ', out, flags=re.I)
            out = re.sub(DATE_RE, ' - ', out, flags=re.I)
            out = re.sub(DATE_NUM_RE, ' - ', out)
            out = re.sub(LABEL_RE, ' - ', out, flags=re.I)
            series = ''
            for pattern, name in SERIES:
                if name and re.search(pattern, re.sub(r'\bF1\s+Show\b', '', title, flags=re.I), re.I):
                    series = name
                    break
            # the session: at the very start or a " - " part of its own (never inside an event name like "Night Race")
            session = ''
            m = re.match(r'\s*(%s)(?=\s|$)' % SESSION_RE, out, re.I)
            if m:
                session = m.group(1)
                out = ' - ' + out[m.end():]
            parts = []
            for p in out.split(' - '):
                if not session and re.match(r'^\s*(%s)\s*$' % SESSION_RE, p, re.I):
                    session = p.strip()
                    continue
                parts.append(p)
            out = ' - '.join(parts)
            for pattern, name in SERIES:
                out = re.sub(pattern, ' ', out, flags=re.I)
            if not date:
                date = self.cm.ph.getSearchGroups(out, YEAR_RE)[0]
            out = re.sub(YEAR_RE, ' ', out)
            keep = []
            for p in out.split(' - '):
                p = re.sub(r'\s+', ' ', p).strip(' ,:-&')
                p = re.sub(r'^(?:of|the)\s+', '', p, flags=re.I)
                if p and p.lower() not in [k.lower() for k in keep]:
                    keep.append(p)
            if session.isupper():
                session = session.title()
            out = ' - '.join([x for x in [series] + keep + [re.sub(r'\s+', ' ', session)] if x]) or title
            if date:
                out = '%s (%s)' % (out, date)
            return out
        except Exception:
            printExc()
        return title


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FullRaces(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('fullraces')

    def withArticleContent(self, cItem):
        return cItem.get('type') == 'video'
