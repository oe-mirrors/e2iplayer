# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - Fajer Show (fajer.show, mirror show.alfajertv.com; Arabic movies, series, plays, Ramadan series):
#     WordPress with its own "fshow" theme on top of DooPlay (post types movies / tvshows / episodes,
#     servers through admin-ajax doo_player_ajax)
#   - the whole site sits behind a Cloudflare managed challenge (curl-impersonate does not get through
#     either): pages go through getPageCFProtection -> MyE2i solve on the box; the posters on the site's
#     own domain get the cf_clearance cookie + the solving User-Agent
#   - movies, series, Ramadan by year, plays, genres, years and search, First page / Jump / Next page
#     from the site's pager
#   - series -> seasons (season tabs) -> episodes; movies and episodes are VIDEO rows keyed on their page
#     path; the servers of a page (doo_player_ajax) go to urlparser, the series trailer is a VIDEO row
#   - watched flag (series -> season -> episode), downloaded flag, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the site's info section
# 09.10.2026 - the site's own mp4 server (vstream*.hadara.ps, region locked) is probed once per session and
#   left out when it answers 403
import os
import re
import time

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.alfajertv_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.alfajertv_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.alfajertv_proxy))
    if config.plugins.iptvplayer.alfajertv_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.alfajertv_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://fajer.show/"


# fajershow.com redirects to the mirror show.alfajertv.com
DOMAINS = ["https://fajer.show/", "https://show.alfajertv.com/"]
SITE_URL_RE = re.compile(r"^https?://(?:www\.)?(?:fajer\.show|show\.alfajertv\.com|fajershow\.com)/", re.I)
SITE_MARKER = "فجر شو"
FIRST_RAMADAN = 2023
SEASON_ORDINALS = [
    ("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثانى", 2), ("الثالث", 3), ("الرابع", 4), ("الخامس", 5),
    ("السادس", 6), ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:الموسم\s*(\d+|%s)|Season\s*(\d+))" % "|".join(o[0] for o in SEASON_ORDINALS), re.I)
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة|Episode)\s*(\d+)", re.I)
# episode slugs: ".../episodes/<show>-1x5/" (DooPlay) or ".../episodes/<show>_s01_ep05/" (2026 imports)
SLUG_SXE_RE = re.compile(r"(?:-(\d+)x(\d+)|_s(\d+)_ep(\d+))/?$", re.I)
# <span class="episode-number">1x4</span> on the episode tiles
EPISODE_NUM_RE = r'class="episode-number"[^>]*>\s*(\d+)x(\d+)'
YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d{2})(?=\s|\)|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجم|اون لاين|أون لاين|مشاهدة|فيلم|مسلسل|مسرحية|كامل|كاملة|HD)(?=\s|$)")
# separators around the labels (alternation: the dashes are multi-byte in py2)
EDGE_RE = re.compile(r"(?:^(?:\s|-|:|\||–|—)+)|(?:(?:\s|-|:|\||–|—)+$)")
LATIN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 :;,.!?'&()\-]*[A-Za-z0-9)!?]|[A-Za-z]")
CARD_HREF_RE = r'href="([^"]*/(?:movies|tvshows|episodes|seasons)/[^"#]+)"'
PAGE_HREF_RE = re.compile(r'href="([^"]*/page/(\d+)/[^"]*)"')
LOCAL_PAGE_SIZE = 100


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1) or m.group(2)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


def _clean(text):
    text = JUNK_RE.sub(" ", JUNK_RE.sub(" ", text or ""))
    return EDGE_RE.sub("", re.sub(r"\s+", " ", text))


def _latinTitle(title):
    # "الهيبة El Hayba" -> "El Hayba" (the metadata services know the original title)
    parts = [p.strip() for p in LATIN_RE.findall(title or "") if re.search(r"[A-Za-z]", p)]
    return max(parts, key=len) if parts else ""


def _sxe(url):
    # (season, episode) from the episode slug
    m = SLUG_SXE_RE.search(urllib_unquote((url or "").split("?")[0]))
    if not m:
        return 0, ""
    return int(m.group(1) or m.group(3)), str(int(m.group(2) or m.group(4)))


def _block(data, cls, end):
    # from the element whose class list holds <cls> up to <end> (the theme's inline css names the same
    # classes further up, a plain marker search would start there)
    m = re.search(r'<[a-zA-Z]+[^>]+class="(?:[^"]* )?%s(?: [^"]*)?"' % re.escape(cls), data)
    if not m:
        return ""
    stop = data.find(end, m.end())
    return data[m.start():stop if stop >= 0 else len(data)]


def _kind(url):
    m = re.search(r"/(movies|tvshows|episodes|seasons)/", url or "")
    return m.group(1) if m else ""


class FajerShow(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    DIRECT_REFUSED = {}  # streaming server of the site's own player -> True when it refused us (403, region)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "season_id", "series_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "alfajertv", "cookie": "alfajertv.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/alfajertv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("alfajertv")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.alfajertv_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        if FajerShow.DOMAIN_CACHE:
            self.MAIN_URL = FajerShow.DOMAIN_CACHE
            return
        domains = list(DOMAINS)
        domain = config.plugins.iptvplayer.alfajertv_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.getPage(domain)
            if sts and SITE_MARKER in data:
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", domain))
                FajerShow.DOMAIN_CACHE = self.MAIN_URL
                return
            if not sts and self.cm.meta.get("status_code") == 403:
                # the Cloudflare check was not solved - the mirror sits behind the same kind of check
                break
        self.MAIN_URL = domains[0]

    def _rebase(self, url):
        # urls of favourites / older lists on the other domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        url = SITE_URL_RE.sub(self.MAIN_URL, url)
        # Arabic slugs -> one percent-encoded form
        return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")

    @staticmethod
    def _path(url):
        # domain independent identity of a page
        url = urllib_unquote((url or "").split("?")[0])
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        return self._withCFMeta(url) if url.startswith("http") else url

    def _withCFMeta(self, url):
        # files on the site's own domain (posters, trailers) sit behind the same Cloudflare check as the
        # pages: the download needs the cf_clearance cookie and the User-Agent that passed the check
        meta = {}
        if SITE_URL_RE.match(url):
            meta["Referer"] = self.MAIN_URL or gettytul()
            try:
                # getCookieHeader logs tracebacks for a cookie file that does not exist yet
                cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
                if cookieHeader:
                    meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
            except Exception:
                printExc()
        proxy = self.getProxy()
        if proxy:
            meta["iptv_http_proxy"] = proxy
        return strwithmeta(url, meta) if meta else url

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("fj_video", "fj_series", "fj_season"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    @staticmethod
    def _episodeTitle(show, season, episode, label):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (show, formatSxxExx(season or 1, episode))
        return label or "%s - %s %s" % (show, _("Episode"), episode)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            if category == "fj_video":
                return "video:%s" % path
            if category == "fj_series":
                return "series:%s" % path
            if category == "fj_season":
                return "season:%s#%s" % (path, cItem.get("season_id", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        def lst(title, path, kind=""):
            return {"category": "list_items", "good_for_fav": True, "title": title, "url": self.getFullUrl(path), "list_kind": kind}

        menu = [
            lst(_("Movies"), "/movies/", "movies"),
            lst(_("Series"), "/tvshows/", "tvshows"),
            {"category": "fj_ramadan", "title": _("Ramadan")},
            lst(_("Plays"), "/genre/plays/", "movies"),
            {"category": "fj_genres", "title": _("Genres")},
            {"category": "fj_years", "title": _("Year")},
        ]
        self.listsTab(menu + self.searchItems(), cItem)

    def listRamadan(self, cItem):
        # Ramadan series of a year: /genre/ramadan<year>/
        for year in range(max(time.localtime().tm_year, 2026), FIRST_RAMADAN - 1, -1):
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": "%s %d" % (_("Ramadan"), year),
                         "url": self.getFullUrl("/genre/ramadan%d/" % year), "list_kind": "tvshows"})

    def listGenres(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        # the mobile menu lists the genres: <span class="mobile-nav-title">..</span> .. <a href=".../genre/<slug>/">
        block = self.cm.ph.getDataBeetwenMarkers(data, "mobile-nav-title", "</nav>", False)[1] or data
        seen = set()
        for href, label in re.findall(r'(?s)<a[^>]+href="([^"]*/genre/[^"]+)"[^>]*>(.*?)</a>', block):
            title = self.cleanHtmlStr(label)
            path = self._path(href)
            if not title or path in seen:
                continue
            seen.add(path)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": self._rebase(href)})

    def listYears(self, cItem):
        sts, data = self.getPage(self.getFullUrl("/movies/"))
        if not sts:
            return
        # the archive filter: <select ..><option value="">جميع السنوات</option><option value="2026">2026</option>
        block = self.cm.ph.getDataBeetwenMarkers(data, "جميع السنوات", "</select>", False)[1]
        for value, label in re.findall(r'(?s)<option[^>]+value="([^"]+)"[^>]*>(.*?)</option>', block):
            title = self.cleanHtmlStr(label)
            url = value if value.startswith(("http", "/")) else "/release/%s/" % value
            if title:
                self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": self._rebase(url)})

    def _cards(self, data):
        # (url, block) of every content card: <a class="item-card" href=".."> (archive grid) and <article> cards
        cards = []
        seen = set()
        blocks = [b for b in self.cm.ph.getAllItemsBeetwenMarkers(data, "<a ", "</a>") if "card" in self.cm.ph.getSearchGroups(b, r'class="([^"]*)"')[0]]
        blocks += self.cm.ph.getAllItemsBeetwenMarkers(data, "<article", "</article>")
        for block in blocks:
            href = self.cm.ph.getSearchGroups(block, CARD_HREF_RE)[0]
            if not href:
                continue
            path = self._path(href)
            if path in seen:
                continue
            seen.add(path)
            cards.append((self._rebase(href), block))
        return cards

    def _cardTitle(self, block):
        for pattern in (r"(?s)<h[234][^>]*>(.*?)</h[234]>", r'(?s)class="[^"]*title[^"]*"[^>]*>(.*?)</', r'\balt="([^"]+)"', r'\btitle="([^"]+)"'):
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, pattern)[0])
            if title:
                return title
        return ""

    def _icon(self, block):
        icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+?(?:data-src|data-lazy-src)="([^"]+)"')[0] or self.cm.ph.getSearchGroups(block, r'<img[^>]+?src="([^"]+)"')[0]
        if not icon or icon.startswith("data:"):
            icon = self.cm.ph.getSearchGroups(block, r"""url\(['"]?([^'")]+)""")[0]
        return self.getFullIconUrl(icon) if icon else ""

    def _addCard(self, url, block, listKind, normalize):
        kind = _kind(url) or listKind
        label = self._cardTitle(block)
        if not label:
            return False
        icon = self._icon(block)
        year = self.cm.ph.getSearchGroups(block, r'class="[^"]*year[^"]*"[^>]*>\s*((?:19|20)\d{2})')[0] or self.cm.ph.getSearchGroups(label, YEAR_RE.pattern)[0]
        seasons = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="[^"]*seasons-badge[^"]*"[^>]*>(.*?)</')[0])
        desc = "[/br]".join(x for x in ("%s: %s" % (_("Year"), year) if year else "", seasons) if x)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc}
        if kind == "episodes":
            m = EPISODE_RE.search(label)
            show = _clean(SEASON_RE.sub(" ", label[:m.start()] if m else label)) or label
            slugSeason, slugEpisode = _sxe(url)
            episode = (m.group(1) if m else "") or slugEpisode
            season = slugSeason or _seasonNum(label) or 1
            params.update({"category": "fj_video", "title": self._episodeTitle(show, season, episode, label), "s_title": show, "s_season": season,
                           "s_episode": str(int(episode)) if episode else "", "meta_type": "tv", "meta_title": _latinTitle(show) or show})
            self.addVideo(params)
        elif kind == "movies":
            clean = _clean(re.sub(r"\(?\b%s\b\)?" % year, " ", label) if year else label) or label
            params.update({"category": "fj_video", "title": ("%s (%s)" % (clean, year) if year else clean) if normalize else label,
                           "meta_type": "movie", "meta_title": _latinTitle(clean) or clean, "meta_year": year})
            self.addVideo(params)
        else:
            show = _clean(SEASON_RE.sub(" ", label)) or label
            params.update({"category": "fj_series", "title": label, "s_title": show, "meta_type": "tv",
                           "meta_title": _latinTitle(show) or show, "meta_year": year})
            self.addDir(params)
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = cItem["url"]
        printDBG("FajerShow.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        grid = _block(data, "archive-grid", "<footer") or data
        normalize = IsMediaNamingNormalized()
        found = 0
        for cardUrl, block in self._cards(grid):
            if self._addCard(cardUrl, block, cItem.get("list_kind", ""), normalize):
                found += 1

        # pager: <nav class="archive-pagination"> <a href="<list>/page/3/">3</a>
        pager = _block(data, "archive-pagination", "</nav>") or grid
        firstUrl = cItem.get("first_url") or cItem["url"]
        pages = [int(num) for _href, num in PAGE_HREF_RE.findall(pager)]
        lastPage = max(pages + [page])
        base, sep, query = firstUrl.partition("?")
        pageTpl = re.sub(r"page/\d+/?$", "", base).rstrip("/") + "/page/{page}/" + (sep + query.replace("{", "{{").replace("}", "}}") if sep else "")
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "first_url": firstUrl, "url": firstUrl})
        addPagingItems(self, listItem, page, bool(found) and (page + 1) in pages, lastPage, pageTpl)

    def _episodeCards(self, data):
        return self.cm.ph.getAllItemsBeetwenMarkers(_block(data, "seasons-section", "</section>"), ("<a", ">", "episode-card"), ("</a", ">"))

    def listSeries(self, cItem):
        printDBG("FajerShow.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        # <video class="hero-promo-video"><source src=".../<show>_s04_promo.mp4"></video>
        trailer = self.cm.ph.getSearchGroups(_block(data, "hero-promo-video", "</video>"), r'src="([^"]+)"')[0]
        if self.cm.isValidUrl(trailer):
            self.addVideo({"name": "category", "good_for_fav": False, "category": "fj_trailer", "title": "%s - %s" % (show, _("Trailer")),
                           "url": trailer, "icon": cItem.get("icon", "")})
        tabs = _block(data, "season-tabs", "</div>")
        seasons = []
        for seasonId, label in re.findall(r'(?s)<button[^>]+data-season="([^"]+)"[^>]*>(.*?)</button>', tabs):
            label = self.cleanHtmlStr(label)
            if seasonId not in [s[0] for s in seasons]:
                seasons.append((seasonId, label))
        if len(seasons) > 1:
            for idx, (seasonId, label) in enumerate(seasons):
                num = _seasonNum(label) or (int(seasonId) if seasonId.isdigit() and int(seasonId) < 100 else idx + 1)
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "fj_season", "season_id": seasonId, "s_season": num,
                               "title": "%s - %s" % (show, formatSxxExx(num)) if IsMediaNamingNormalized() else label or "%s %d" % (_("Season"), num)})
                self.addDir(params)
            return
        if seasons:
            self.listEpisodes(dict(cItem, season_id=seasons[0][0], s_season=_seasonNum(seasons[0][1]) or 1), data)
        elif self._episodeCards(data):
            self.listEpisodes(dict(cItem, season_id="", s_season=_seasonNum(show) or 1), data)
        else:
            # a show page without episodes is played itself (single-part plays / specials)
            self.addVideo(dict(cItem, category="fj_video", title=show))

    def listEpisodes(self, cItem, data=None):
        printDBG("FajerShow.listEpisodes [%s] [%s]" % (cItem.get("url", ""), cItem.get("season_id", "")))
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        message = self.cleanHtmlStr(_block(data, "no-episodes", "</div>"))
        block = _block(data, "seasons-section", "</section>")
        seasonId = cItem.get("season_id", "")
        if seasonId:
            # one panel per season: <div class="season-episodes" id="season-<id>"> .. up to the next panel
            panel = block.split('id="season-%s"' % seasonId, 1)
            if len(panel) == 2:
                block = panel[1].split('class="season-episodes"')[0]
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        episodes = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, ("<a", ">", "episode-card"), ("</a", ">")):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            path = self._path(href)
            if not href or path in seen:
                continue
            seen.add(path)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h4[^>]*>(.*?)</h4>")[0]) or self.cleanHtmlStr(item)
            # "1x4" tile badge, else "الحلقة 4 | <show>", else the slug
            episode = self.cm.ph.getSearchGroups(item, EPISODE_NUM_RE, 2)[1] or self.cm.ph.getSearchGroups(label, EPISODE_RE.pattern)[0] or _sxe(href)[1]
            episodes.append({"name": "category", "good_for_fav": True, "category": "fj_video", "url": self._rebase(href), "icon": cItem.get("icon", ""),
                             "title": self._episodeTitle(show, season, episode, "%s - %s" % (show, label) if label else show),
                             "desc": cItem.get("desc", ""), "series_url": cItem["url"], "s_title": show, "s_season": season,
                             "s_episode": str(int(episode)) if episode else "", "meta_type": "tv",
                             "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        if not episodes:
            SetIPTVPlayerLastHostError(message or _("No stream available"))
            return
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, category="fj_season"), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FajerShow.listSearchResult [%s]" % searchPattern)
        url = self.getFullUrl("/?s=%s" % urllib_quote_plus(searchPattern.strip()))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "page": 1, "url": url, "first_url": url})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _ajaxEmbed(self, pageUrl, post, nume, postType):
        header = dict(self.HEADER)
        header.update({"Referer": pageUrl, "Accept": "*/*", "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        params = dict(self.defaultParams)
        params["header"] = header
        sts, data = self.getPage(self.getFullUrl("/wp-admin/admin-ajax.php"), params, {"action": "doo_player_ajax", "post": post, "nume": nume, "type": postType})
        if not sts:
            return ""
        # {"embed_url": "<iframe src=..>" or "https://..", "type": "iframe"}
        embed = data
        try:
            answer = json_loads(data)
            if isinstance(answer, dict):
                embed = answer.get("embed_url", "") or ""
        except Exception:
            pass
        embed = embed.replace("\\/", "/").strip()
        url = self.cm.ph.getSearchGroups(embed, r"""src=['"]([^'"]+)['"]""", ignoreCase=True)[0] or embed
        url = url.replace("&amp;", "&").strip()
        return "https:" + url if url.startswith("//") else url

    def _directRefused(self, url):
        # one Range 0-0 request per streaming server and session (through the host's proxy, like the player):
        # 403 -> the server does not serve this region
        server = self.cm.ph.getSearchGroups(url, r"^https?://([^/?#]+)")[0].lower()
        if server not in FajerShow.DIRECT_REFUSED:
            params = {"header": {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL, "Range": "bytes=0-0"}, "max_data_size": 65536, "timeout": 10}
            if self.getProxy():
                params["http_proxy"] = self.getProxy()
            self.cm.getPage(url, params)
            FajerShow.DIRECT_REFUSED[server] = self.cm.meta.get("status_code") == 403
            printDBG("FajerShow._directRefused [%s] status %s" % (server, self.cm.meta.get("status_code")))
        return FajerShow.DIRECT_REFUSED[server]

    def getLinksForVideo(self, cItem):
        printDBG("FajerShow.getLinksForVideo [%s]" % cItem.get("url", ""))
        if cItem.get("category") == "fj_trailer":
            return [{"name": _("Trailer"), "url": self._withCFMeta(cItem["url"]), "need_resolve": 0}]
        pageUrl = self._rebase(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        postId = self.cm.ph.getSearchGroups(data, r"postId\s*=\s*['\"]?(\d+)")[0]
        postType = self.cm.ph.getSearchGroups(data, r"""postType\s*=\s*['"]([^'"]+)['"]""")[0]
        servers = _block(data, "servers-section", "</section>")
        urltab = []
        direct = []
        refused = False
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(servers, "<button", "</button>"):
            nume = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="[^"]*server-num[^"]*"[^>]*>(.*?)</span>')[0]) or self.cm.ph.getSearchGroups(item, r'data-nume="([^"]+)"')[0]
            post = self.cm.ph.getSearchGroups(item, r'data-post="(\d+)"')[0] or postId
            itemType = self.cm.ph.getSearchGroups(item, r'data-type="([^"]+)"')[0] or postType
            if not nume or not post:
                continue
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="[^"]*server-name[^"]*"[^>]*>(.*?)</span>')[0])
            url = self._ajaxEmbed(pageUrl, post, nume, itemType)
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            source = urllib_unquote(self.cm.ph.getSearchGroups(url, r"/jwplayer/\?(?:[^#]*&)?source=([^&#]+)")[0])
            if self.cm.isValidUrl(source):
                # the site's own player: jwplayer/?source=<mp4 on vstream*.hadara.ps> -> the file is played directly.
                # That Palestinian server (Nimble Streamer) refuses (403) requests from outside its region whatever
                # Referer/Origin -> only offered when it answers here, listed after the hosters
                if self._directRefused(source):
                    refused = True
                    continue
                meta = {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
                if self.getProxy():
                    meta["iptv_http_proxy"] = self.getProxy()
                direct.append({"name": "%s - mp4" % name if name else "mp4", "url": strwithmeta(source, meta), "need_resolve": 0})
                continue
            hostName = self.up.getHostName(url)
            urltab.append({"name": "%s - %s" % (name, hostName) if name else hostName, "url": strwithmeta(url, {"Referer": pageUrl}), "need_resolve": 1})
        urltab.extend(direct)
        if not urltab:
            if refused:
                SetIPTVPlayerLastHostError(_("The video file of this title is not available on the server (HTTP 403)."))
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="[^"]*synopsis-text[^"]*"[^>]*>(.*?)</p>')[0])
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("FajerShow.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        section = _block(data, "info-section", "</section>") or data
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(section, r'(?s)class="[^"]*synopsis-text[^"]*"[^>]*>(.*?)</div>')[0])
        if not story:
            story = self.cleanHtmlStr(_block(data, "single-description", "</div>"))
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta (?:property="og:description"|name="description") content="([^"]+)"')[0])
        info = {}
        original = self.cleanHtmlStr(self.cm.ph.getSearchGroups(section, r"(?s)العنوان الأصلي.*?<span[^>]*>(.*?)</span>")[0])
        if original:
            info["original_title"] = original
        for key, cls in (("year", "year"), ("seasons", "seasons"), ("duration", "runtime")):
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<span[^>]+class="[^"]*\b%s\b[^"]*"[^>]*>(.*?)</span>' % cls)[0])
            if value:
                info[key] = value
        genres = [self.cleanHtmlStr(g) for g in re.findall(r"(?s)<a[^>]*>(.*?)</a>", _block(data, "single-genres", "</div>"))]
        if any(genres):
            info["genres"] = ", ".join(g for g in genres if g)
        # <div class="person">..<div class="name"><a ..>name</a></div><div class="caracter">اخراج|role</div>
        directors, cast = [], []
        for name, role in re.findall(r'(?s)class="name"[^>]*>(.*?)</div>\s*<div class="caracter"[^>]*>(.*?)</div>', section):
            name = self.cleanHtmlStr(name)
            if name:
                (directors if "اخراج" in role or "إخراج" in role else cast).append(name)
        if directors:
            info["directors"] = ", ".join(directors[:4])
        if cast:
            info["cast"] = ", ".join(cast[:8])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getArticleContent(self, cItem):
        printDBG("FajerShow.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                # Arabic-only titles -> no IMDb/Cinemeta/OMDb (they answer with unrelated English hits)
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("series_url") or cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("FajerShow.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "fj_ramadan":
            self.listRamadan(self.currItem)
        elif category == "fj_genres":
            self.listGenres(self.currItem)
        elif category == "fj_years":
            self.listYears(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "fj_series":
            self.listSeries(self.currItem)
        elif category == "fj_season":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FajerShow(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("alfajertv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("fj_video", "fj_series", "fj_season")
