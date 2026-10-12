# -*- coding: utf-8 -*-
# Last Modified: 12.10.2026
# 12.10.2026 - watching page loader changed again: its key variables are pushed into the array (_arrX['p'+'ush'](...))
#   and rounded with Math.round under an alias instead of Math.floor - both read now
# 11.10.2026 - the token API (cimaleech.vercel.app) answers 404: when it gives no link, MyE2i (NAV job, extension
#   v1.21) opens the watch button's ad gateway in the user's browser and sends back the tokenised watching link
#   the gateway's scripts build there (obfuscated, with decoys against scrapers - not doable without a browser);
#   the link is kept for 10 minutes per page; the watching page has a new loader (key = sum of the "_arrX" variables:
#   hex sums, floor(x / 2), a CSS z-index, a div width; _part1/2/3 are decoys now), the old one stays as fallback;
#   the own "Cima Now" server moved to <x>.worldcdn.online/e/<id> (same Playerjs file list) and is resolved by urlparser
#   (parserCIMANOWTV) like every other server - the host's own copy of that code is gone
# 08.10.2026 - server list fixed: the "ffQualities" forafile object is gone; the page's watch button now leads
#   through an ad gateway (rm.freex2line.online) to <page>/watching/?token=... (without a valid token the site
#   redirects home). The token is fetched from the cimaleech.vercel.app API (same as MOHAMED_OS's host), the
#   watching page is XOR/base64 obfuscated (key = sum of the page's JS constants) and decoded here; its server
#   list (<ul id="watch">, data-index/data-id + "var tk") is resolved through core.php?action=switch -> iframe,
#   plus the forafile links of its download box
# 03.10.2026 - revived for cimanow.cc (the site dropped its "hide_my_HTML_" obfuscation)
#   Rewrite against the plain-HTML site (same markup as before: <section aria-label="posts">,
#   <article aria-label="post">, aria-label="title|year|ribbon|tab", <ul aria-label="pagination">):
#   - categories, "Latest" (/الاحدث/) and search (/search/<q>/) with First page / Jump / Next page
#   - movies and episodes are VIDEO rows keyed on their page url (links: see 08.10.2026)
#   - series -> seasons (when the show has more than one) -> episodes (ascending)
#   - watched flag (stable series:/season:/video: page-url keys), downloaded flag, favourites,
#     name normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the site's
#     story/poster/fields; no blocking retry loops, no colour codes in titles
import ast
import math
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import strDecode
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, StripColorCodes, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://cimanow.cc/"


# Arabic ordinals used in season labels ("الموسم الثاني")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالث", 3), ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8),
    ("التاسع", 9), ("العاشر", 10),
]
SEASON_WORD_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|اون لاين|أون لاين|مشاهدة|فيلم|مسلسل|برنامج|كامل|كاملة|بجودة عالية|HD)(?=\s|$)")
# "<strong>..مدة العرض : </strong>" rows of the details tab -> INFO keys
INFO_FIELDS = (("language", "المحتوي"), ("duration", "مدة العرض"), ("quality", "الجودة"), ("actors", "بطولة"),
               ("director", "اخراج"), ("writer", "تأليف"))
# the watch button's ad gateway is a per-request obfuscated anti-bot page; this API returns the tokenised
# <page>/watching/?token=... url for the gateway link ("upcloud" first, "test" as the fallback endpoint)
TOKEN_APIS = ("https://cimaleech.vercel.app/api/upcloud", "https://cimaleech.vercel.app/api/test")
# MyE2i NAV job for the same gateway: the countdown page's watch button, once its scripts put the token in
WATCH_LINK_JOB = {"selector": "a#downloadbtn", "attr": "href", "pattern": r"/watching/\?token=[^&#\s]+"}
WATCH_LINK_TTL = 600  # seconds a link from MyE2i is reused for the same page
NUM_RE = re.compile(r"0x[0-9a-fA-F]+|\d+")


def _numSum(expr):
    # the obfuscator's constants are plain sums of hex/decimal literals - add them up instead of eval()
    return sum(int(n, 16) if n.lower().startswith("0x") else int(n) for n in NUM_RE.findall(expr or ""))


# bit operators (<< >> | ^ &) since the loader of 12.10.2026; Python and JS rank them alike, the operands are small ints
_JS_NUM_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.USub, ast.UAdd, ast.Call, ast.Name, ast.Load,
                 ast.LShift, ast.RShift, ast.BitOr, ast.BitXor, ast.BitAnd)


def _jsRound(value):
    # JS Math.round: halves go up (Python's round() rounds them to even)
    return math.floor(value + 0.5)


def _jsNum(expr, floorName="", roundName=""):
    # a JS arithmetic expression of number literals (hex too), + - * / % and Math.floor / Math.round (under their
    # aliases) -> int; anything else (a name, a string, a call of something else) is refused - no eval() of page code
    if floorName:
        expr = re.sub(r"\b%s\s*\(" % re.escape(floorName), "floor(", expr)
    if roundName:
        expr = re.sub(r"\b%s\s*\(" % re.escape(roundName), "jsround(", expr)
    tree = ast.parse(expr.strip(), mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _JS_NUM_NODES) or (isinstance(node, ast.Name) and node.id not in ("floor", "jsround")) or (isinstance(node, ast.Constant) and not isinstance(node.value, (int, float))):
            raise ValueError("not a plain number expression: %r" % expr)
    return int(eval(compile(tree, "js", "eval"), {"__builtins__": {}}, {"floor": math.floor, "jsround": _jsRound}))


def _seasonNum(text):
    m = SEASON_WORD_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


class CimaNow(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cimanow", "cookie": "cimanow.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/cimanow.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchLinks = {}  # gateway link -> (time, tokenised watching link from MyE2i)

        def cat(slug):
            return self.getFullUrl("/category/%s/" % slug)

        self.MOVIES_TAB = [
            {"title": _("Foreign movies"), "url": cat("افلام-اجنبية")},
            {"title": _("Arabic Movies"), "url": cat("افلام-عربية")},
            {"title": _("Turkish Movies"), "url": cat("افلام-تركية")},
            {"title": _("Indian Movies"), "url": cat("افلام-هندية")},
            {"title": _("Korean movies"), "url": cat("افلام-كورية")},
            {"title": _("Anime Movies"), "url": cat("افلام-انيميشن")},
            {"title": _("Documentary Movies"), "url": cat("افلام-وثائقية")},
            {"title": _("Short Movies"), "url": cat("افلام-قصيرة")},
            {"title": _("Plays"), "url": cat("مسرحيات")},
        ]
        self.SERIES_TAB = [
            {"title": _("Foreign series"), "url": cat("مسلسلات-اجنبية")},
            {"title": _("Arabic Series"), "url": cat("مسلسلات-عربية")},
            {"title": _("Turkish Series"), "url": cat("مسلسلات-تركية")},
            {"title": _("Korean TV series"), "url": cat("مسلسلات-كورية")},
            {"title": _("Anime Series"), "url": cat("مسلسلات-انيميشن")},
            {"title": _("TV Shows"), "url": cat("البرامج-التلفزيونية")},
            {"title": "%s 2026" % _("Ramadan"), "url": cat("رمضان-2026")},
            {"title": "%s 2025" % _("Ramadan"), "url": cat("رمضان-2025")},
        ]
        self.MENU = [
            {"category": "cn_tab", "title": _("Movies"), "tab": "movies"},
            {"category": "cn_tab", "title": _("Series"), "tab": "series"},
            {"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("/الاحدث/")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("cimanow")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def getFullUrl(self, url, currUrl=None):
        # menu urls are written in Arabic - one ASCII (percent-encoded) form for everything
        return self._quote(CBaseHostClass.getFullUrl(self, url, currUrl))

    @staticmethod
    def _quote(url):
        try:
            return urllib_quote(urllib_unquote(url.replace("&amp;", "&").replace("&#038;", "&")), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _canonUrl(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return self._quote(url)

    def _path(self, url):
        # domain independent identity of a page
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def _kind(self, url):
        path = self._path(url)
        if "/selary/" in path:
            return "series"
        if re.search(r"-ح\d+(?:-|$)|الحلقة-\d+", path):
            return "episode"
        return "movie"

    def _episodeNumbers(self, url, fallbackSeason=0):
        path = self._path(url)
        season = self.cm.ph.getSearchGroups(path, r"-ج(\d+)(?:-|$)")[0]
        episode = self.cm.ph.getSearchGroups(path, r"-ح(\d+)(?:-|$)")[0] or self.cm.ph.getSearchGroups(path, r"الحلقة-(\d+)")[0]
        return int(season) if season else (fallbackSeason or 1), episode

    @staticmethod
    def _clean(text):
        text = JUNK_RE.sub(" ", text or "")
        return re.sub(r"\s+", " ", text).strip(" -:|")

    def _icon(self, url):
        url = (url or "").replace("?quality=10", "").strip()
        return self.getFullIconUrl(self._quote(url)) if url else ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("cn_video", "cn_series", "cn_season"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"cn_video": "video", "cn_series": "series", "cn_season": "season"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listTab(self, cItem):
        tab = self.MOVIES_TAB if cItem.get("tab") == "movies" else self.SERIES_TAB
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params.update({"good_for_fav": True, "category": "list_items"})
            params.pop("tab", None)
            self.addDir(params)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem["url"])
        url = baseUrl if page <= 1 else "%spage/%d/" % (baseUrl, page)
        printDBG("CimaNow.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        posts = self.cm.ph.getDataBeetwenMarkers(data, '<section aria-label="posts">', "</section>", False)[1]
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(posts, '<article aria-label="post">', "</article>"):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            if not href:
                continue
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            rawTitle = self.cm.ph.getSearchGroups(item, r'(?s)<li aria-label="title">(.*?)</li>')[0]
            genres = self.cleanHtmlStr(self.cm.ph.getSearchGroups(rawTitle, r"(?s)<em>(.*?)</em>")[0])
            title = self.cleanHtmlStr(re.sub(r"(?s)<em>.*?</em>", "", rawTitle))
            if not title:
                continue
            year = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<li aria-label="year">([^<]*)<')[0])
            ribbons = [self.cleanHtmlStr(r) for r in re.findall(r'<li aria-label="ribbon">([^<]*)<', item)]
            tabs = [self.cleanHtmlStr(t) for t in re.findall(r'<li aria-label="tab">([^<]*)<', item)]
            seasonLabel = ""
            for t in tabs:
                if _seasonNum(t):
                    seasonLabel = t
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            fields = ((_("Quality"), " ".join(r for r in ribbons if r), "yellow"), (_("Year"), year, "cyan"),
                      (_("Section"), ", ".join(t for t in tabs if t != seasonLabel), "green"), (_("Genres"), genres, "magenta"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self._icon(icon), "desc": desc}
            kind = self._kind(url)
            if kind == "series":
                season = self._episodeNumbers(url, _seasonNum(seasonLabel))[0]
                params.update({"category": "cn_series", "title": ("%s - %s" % (title, seasonLabel)) if seasonLabel else title,
                               "s_title": title, "s_season": season, "meta_type": "tv", "meta_title": title, "meta_year": year})
                self.addDir(params)
            elif kind == "episode":
                season, episode = self._episodeNumbers(url, _seasonNum(seasonLabel))
                if normalize and episode:
                    dispTitle = "%s - %s" % (title, formatSxxExx(season, episode))
                else:
                    dispTitle = " - ".join(x for x in (title, seasonLabel, ("%s %s" % (_("Episode"), episode)) if episode else "") if x)
                params.update({"category": "cn_video", "title": dispTitle, "s_title": title, "s_season": season, "s_episode": episode,
                               "meta_type": "tv", "meta_title": title, "meta_year": year})
                self.addVideo(params)
            else:
                dispTitle = title
                if normalize:
                    dispTitle = self._clean(title) or title
                    if year and year not in dispTitle:
                        dispTitle = "%s (%s)" % (dispTitle, year)
                params.update({"category": "cn_video", "title": dispTitle, "meta_type": "movie", "meta_title": self._clean(title) or title, "meta_year": year})
                self.addVideo(params)

        # pager: <li class="active"> = this page, the highest number = last page
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'aria-label="pagination"', "</ul>", False)[1]
        lastPage = max([int(n) for n in re.findall(r'<a[^>]+href="[^"]+"[^>]*>\s*(\d+)\s*</a>', pager)] + [page])
        hasNext = bool(seen) and lastPage > page
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, baseUrl + "page/{page}/")

    def listSeries(self, cItem):
        # the series row is one season page; more seasons -> season folders, else the episodes
        printDBG("CimaNow.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<section aria-label="seasons">', "</section>", False)[1]
        seasons = []
        for href, label in re.findall(r'(?s)<a href="([^"]+)"[^>]*>(.*?)</a>', block):
            url = self._canonUrl(href)
            label = self.cleanHtmlStr(label)
            num = self._episodeNumbers(url, _seasonNum(label))[0]
            if url and url not in [s[1] for s in seasons]:
                seasons.append((num, url, label))
        if len(seasons) <= 1:
            self.listEpisodes(cItem, data)
            return
        seasons.sort(key=lambda s: s[0])
        for num, url, label in seasons:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "cn_season", "title": label, "url": url, "s_season": num})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("CimaNow.listEpisodes [%s]" % cItem.get("url", ""))
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="eps">', "</ul>", False)[1]
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        episodes = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not href:
                continue
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'aria-label="([^"]+)"')[0])
            season, episode = self._episodeNumbers(url, cItem.get("s_season", 0) or _seasonNum(label))
            num = self.cm.ph.getSearchGroups(item, r"<em>\s*(\d+)\s*</em>")[0]
            if num:
                episode = str(int(num))
            imgs = re.findall(r'<img[^>]+src="([^"]+)"', item)
            if normalize and episode:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = label or ("%s - %s %s" % (show, _("Episode"), episode))
            episodes.append({"name": "category", "good_for_fav": True, "category": "cn_video", "title": title, "url": url,
                             "icon": self._icon(imgs[-1]) if imgs else cItem.get("icon", ""), "desc": cItem.get("desc", ""),
                             "s_title": show, "s_season": season, "s_episode": episode,
                             "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        episodes.reverse()  # the site lists the newest first
        for params in episodes:
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CimaNow.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/search/%s/" % urllib_quote(searchPattern.strip(), safe=""))
        cItem.update({"category": "list_items", "url": base, "base_url": base, "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        details = self.cm.ph.getDataBeetwenMarkers(data, 'id="details">', "</ul>", False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(details, r"(?s)عن المحتوى[^<]*</strong>\s*<p>(.*?)</p>")[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<li aria-label="story">(.*?)</li>')[0])
        story = re.sub(r"\s*مشاهدة وتحميل.*$", "", story).strip()
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        info = {}
        for key, word in INFO_FIELDS:
            val = self.cm.ph.getSearchGroups(details, r"(?s)%s\s*:\s*</strong>(.*?)</li>" % word)[0]
            val = re.sub(r"\s*،\s*", ", ", self.cleanHtmlStr(val)).strip(" ,")
            if val:
                info[key] = val
        return story, self._icon(poster) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("CimaNow.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        shineUrl = self.cm.ph.getSearchGroups(data, r'<a[^>]+class="shine"[^>]+href="([^"]+)"')[0]
        watchUrl = self._watchingUrl(shineUrl)
        if not watchUrl:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=pageUrl)
        sts, data = self.getPage(watchUrl, params)
        if not sts:
            return []
        if 'id="watch"' not in data:
            data = self._decodeWatching(data)
        if 'id="watch"' not in data:
            # the token is no longer accepted (the site sent the start page): ask again next time
            self.watchLinks.pop(self._gatewayKey(shineUrl), None)
        urltab = []
        token = self.cm.ph.getSearchGroups(data, r"""var\s+tk\s*=\s*['"]([^'"]+)['"]""")[0]
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="watch">', "</ul>", False)[1]
        coreUrl = self.getFullUrl("/wp-content/themes/Cima%20Now%20New/core.php")
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=watchUrl)
        seen = set()
        for index, serverId, label in re.findall(r'(?s)<li[^>]+data-index="([^"]+)"[^>]+data-id="([^"]+)"[^>]*>(.*?)</li>', block):
            sts, frame = self.getPage("%s?%s" % (coreUrl, urllib_urlencode([("action", "switch"), ("index", index), ("id", serverId), ("token", token)])), params)
            url = self.cm.ph.getSearchGroups(frame, r"""<iframe[^>]+src=['"]([^'"]+)['"]""", ignoreCase=True)[0] if sts else ""
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            name = "%s - %s" % (self.cleanHtmlStr(label), self.up.getDomain(url, onlyDomain=True))
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        # download box: forafile per quality (the site's player adds them as the "Forafile" server)
        for code, rest in re.findall(r'forafile\.[a-z]+/([a-z0-9]{12})([^"\']*)', data):
            quality = self.cm.ph.getSearchGroups(rest, r"(\d{3,4}p)")[0]
            url = "https://forafile.com/embed-%s.html" % code
            if url in seen:
                continue
            seen.add(url)
            urltab.append({"name": ("Forafile %s" % quality).strip(), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    @staticmethod
    def _gatewayKey(shineUrl):
        return (shineUrl or "").replace("&amp;", "&").strip()

    def _watchingUrl(self, shineUrl):
        # direct <page>/watching/?token= link, or the ad gateway link -> tokenised url from the API, else from the
        # user's browser through MyE2i
        shineUrl = self._gatewayKey(shineUrl)
        if not shineUrl:
            return ""
        if "/watching/" in shineUrl and "token=" in shineUrl:
            return self._canonUrl(shineUrl)
        cached = self.watchLinks.get(shineUrl)
        if cached and time.time() - cached[0] < WATCH_LINK_TTL:
            return cached[1]
        url = self._tokenApiUrl(shineUrl) or self._myE2iWatchingUrl(shineUrl)
        if url:
            self.watchLinks[shineUrl] = (time.time(), url)
        return url

    def _myE2iWatchingUrl(self, shineUrl):
        # the gateway's countdown page gets its tokenised watch link only from its own (obfuscated) scripts:
        # MyE2i's NAV job opens the gateway in the user's browser, follows its redirects and sends that link back
        try:
            from Plugins.Extensions.IPTVPlayer.libs.recaptcha_mye2i import UnCaptchaReCaptcha
            answer = UnCaptchaReCaptcha().processCaptcha(time.time(), shineUrl, captchaType="NAV", captchaData=json_dumps(WATCH_LINK_JOB))
            url = (json_loads(b64Decode(answer)) or {}).get("url", "") if answer else ""
        except Exception:
            printExc()
            url = ""
        # the browser's absolute, already encoded address as it is - re-quoting could turn a %2B of the token into "+"
        if url.startswith("http") and "/watching/" in url and "token=" in url:
            return url
        printDBG("CimaNow._myE2iWatchingUrl no link for [%s]" % shineUrl)
        return ""

    def _tokenApiUrl(self, shineUrl):
        params = {"header": {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL, "Accept": "application/json"}}
        for api in TOKEN_APIS:
            sts, data = self.cm.getPage(api, params, {"id": shineUrl})
            if not sts:
                continue
            try:
                url = (json_loads(data) or {}).get("downloadLink") or ""
            except Exception:
                # no JSON (the API answers 404 since 11.10.2026): MyE2i takes over, no traceback in the log
                url = ""
            if "/watching/" in url:
                return self._canonUrl(url)
        printDBG("CimaNow._tokenApiUrl no token for [%s]" % shineUrl)
        return ""

    def _decodeWatching(self, data):
        # the current loader first, then the one of 08.10.2026
        decoded = self._decodeWatchingSum(data)
        return decoded if decoded else self._decodeWatchingParts(data)

    def _decodeWatchingSum(self, data):
        # loader of 11.10.2026: window["<arr>"] = new (window["Arr"+"ay"])("b64", ...); an atob('...') loader XORs
        # it with String(sum of the variables of its "_arrX = [a, b, c, ...]") + String.fromCharCode(n) and cuts
        # .substring(n) off the start. The variables are hex sums, Math.floor(x / 2), a CSS z-index and a div width
        # set from String(...) expressions, an environment check (1 in a browser); _part1/2/3 are decoys now.
        # "" when the page is not of this kind
        try:
            arr = re.search(r"""window\[['"](\w+)['"]\]\s*=\s*new\s*\(\s*window\[['"]Arr['"]\s*\+\s*['"]ay['"]\]\s*\)\s*\((.*?)\)\s*;""", data, re.S)
            loader = re.search(r"""\]\(\s*['"]([A-Za-z0-9+/=]{200,})['"]\s*\)""", data)
            if not arr or not loader:
                return ""
            code = b64Decode(loader.group(1))
            floor = re.search(r"""var\s+(\w+)\s*=\s*\w+\[\s*['"]f['"]\s*\+\s*['"]loor['"]\s*\]""", code) or re.search(r"var\s+(\w+)\s*=\s*Math\.floor\b", code)
            floorName = floor.group(1) if floor else ""
            rounder = re.search(r"""var\s+(\w+)\s*=\s*\w+\[\s*['"]r['"]\s*\+\s*['"]ound['"]\s*\]""", code) or re.search(r"var\s+(\w+)\s*=\s*Math\.round\b", code)
            roundName = rounder.group(1) if rounder else ""
            defs = dict(re.findall(r"var\s+(\w+)\s*=\s*([^;]+);", code))
            zindex = re.search(r"""\.style\[\s*['"]z-i['"]\s*\+\s*['"]ndex['"]\s*\]\s*=\s*String\((.*?)\)\s*;""", code)
            width = re.search(r"""idth:['"]\s*\+\s*String\((.*?)\)\s*\+\s*['"]px""", code)
            # the key variables: "_arrX = [a, b, ...]; for" (11.10.) or "_arrX['p'+'ush'](a, b, ...); for" (12.10.)
            arrVars = re.search(r"=\s*\[([\w\s,$]+)\]\s*;\s*for", code) or \
                re.search(r"""\[\s*['"]p['"]\s*\+\s*['"]ush['"]\s*\]\s*\(([\w\s,$]+)\)\s*;\s*for""", code) or \
                re.search(r"\.push\(([\w\s,$]+)\)\s*;\s*for", code)
            if not arrVars:
                printDBG("CimaNow._decodeWatchingSum: no key variables")
                return ""

            def value(name, depth=0):
                expr = defs[name].strip()
                if "getComputedStyle" in expr and zindex:
                    return _jsNum(zindex.group(1), floorName, roundName)
                if "offsetWidth" in expr and width:
                    return _jsNum(width.group(1), floorName, roundName)
                if "?" in expr:  # the environment check: 1 in a browser
                    return 1
                if depth < 5:
                    for other in set(re.findall(r"\b[A-Za-z_$][\w$]*\b", expr)):
                        if other not in (floorName, roundName) and other in defs and other != name:
                            expr = re.sub(r"\b%s\b" % re.escape(other), str(value(other, depth + 1)), expr)
                return _jsNum(expr, floorName, roundName)

            key = str(sum(value(v.strip()) for v in arrVars.group(1).split(",") if v.strip()))
            key += "".join(chr(int(n)) for n in re.findall(r"toString\(\)\s*\+\s*String\.fromCharCode\((\d+)\)", code)[:1])
            raw = bytearray(b64Decode("".join(re.findall(r"""['"]([A-Za-z0-9+/=]+)['"]""", arr.group(2))), binary=True))
            out = strDecode(bytes(bytearray(b ^ ord(key[i % len(key)]) for i, b in enumerate(raw))), "ignore")
            # the first .substring() whose argument is a plain number (other code may use substring too)
            for arg in re.findall(r"\.substring\(([^;]+?)\)\s*;", code):
                try:
                    out = out[_jsNum(arg, floorName, roundName):]
                    break
                except (ValueError, SyntaxError):
                    continue
            if 'id="watch"' not in out:
                printDBG("CimaNow._decodeWatchingSum: key %s gave no server list" % key)
                return ""
            return out
        except Exception:
            printExc()
        return ""

    def _decodeWatchingParts(self, data):
        # loader of 08.10.2026: window['<arr>'] = new Array("b64", ...) XORed with String(_part1 + _part2 + _part3 +
        # _tVal + _dVal) + suffix; the constants sit in an atob("...") loader script
        code = data
        for b64 in re.findall(r"""\(\s*['"]([A-Za-z0-9+/=]{200,})['"]\s*\)""", data):
            try:
                code += "\n" + b64Decode(b64)
            except Exception:
                continue
        try:
            m1 = re.search(r"_part1\s*=\s*\w+\(\s*\((.*?)\)\s*/\s*(\d+)\s*\)", code)
            m2 = re.search(r"_part2\s*=\s*\((.*?)\)\s*\*", code)
            m3 = re.search(r"_part3\s*=\s*\((.*?)\)\s*;", code)
            mt = re.search(r"ndex'\]\s*=\s*String\(\(?([^)]+)\)?\)", code)
            md = re.search(r"idth:'\s*\+\s*String\(([^)]+)\)", code)
            mk = re.search(r"=\s*String\(\s*_part1[^)]*\)\s*\+\s*'([^']*)'", code)
            ma = re.search(r"""=\s*window\[['"](\w+)['"]\]\.join\(""", code)
            if not (m1 and m2 and m3 and ma):
                printDBG("CimaNow._decodeWatching: decoder constants not found")
                return data
            total = _numSum(m1.group(1)) // (int(m1.group(2)) or 1) + _numSum(m2.group(1)) + _numSum(m3.group(1))
            total += _numSum(mt.group(1)) if mt else 0
            total += _numSum(md.group(1)) if md else 0
            key = str(total) + (mk.group(1) if mk else "")
            arr = re.search(r"""window\[['"]%s['"]\]\s*=\s*(?:\[|new\s*\(?\s*window\[[^\]]*\]\s*\)?\s*\()(.*?)[\])]\s*;""" % ma.group(1), code, re.S)
            if not arr:
                return data
            raw = bytearray(b64Decode("".join(re.findall(r"""['"]([A-Za-z0-9+/=]+)['"]""", arr.group(1))), binary=True))
            out = bytearray(b ^ ord(key[i % len(key)]) for i, b in enumerate(raw))
            return strDecode(bytes(out), "ignore")
        except Exception:
            printExc()
        return data

    def getVideoLinks(self, videoUrl):
        printDBG("CimaNow.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        # every server through urlparser - also the site's own "Cima Now" player (cimanowtv.com / worldcdn.online:
        # parserCIMANOWTV)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("CimaNow.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or StripColorCodes(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("CimaNow.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "cn_tab":
            self.listTab(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "cn_series":
            self.listSeries(self.currItem)
        elif category == "cn_season":
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
        CHostBase.__init__(self, CimaNow(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cimanow")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("cn_video", "cn_series", "cn_season")
