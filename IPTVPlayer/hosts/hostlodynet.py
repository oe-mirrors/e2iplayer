# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - brought to the current host standard
#   Lodynet host originally by Mohamed Elsafty (angel_heart)
#   - lodynet.watch redirects to lodynet.top: the main menu follows the redirect and takes the
#     live domain; the "load more" API (RequestExpansion.php) is read from the page's own
#     GetExpansion() code (lodynet.watch answers it with "null") - fallback lodynet.top
#   - one list function for every listing (sections, series, seasons, tags, years, actors):
#     page 1 = the HTML page, page n = the expansion API (indicator n); "Recently added" pages
#     with /page/n/; pager rows via iptvpaging (First page / Jump / Next page)
#   - main menu read live from the site's navigation (static fallback)
#   - network only through self.cm (no requests module), Python 2.7 + 3 (no f-strings)
#   - movies / episodes / clips are VIDEO rows keyed on their page url; the hoster embeds
#     (PostData.ServersWatch) are read in getLinksForVideo; "Lody Plus" premium servers
#     (no embed, subscription only) are hidden, ViD LO (vidlo.us, 404 for every signed embed)
#     dropped; every other server incl. "Megamx" (megamax) goes to urlparser
#   - watched flag (post:/cat: slugs, series -> season -> episode), downloaded flag,
#     favourites, sidecar, name normalisation ("Title (Year)", "Show - SxxExx"), INFO via
#     moviemeta + the site's story/poster/cast/genres
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://lodynet.watch/"


# lodynet.watch only redirects - the site itself lives here (updated from the redirect)
SITE_URL = "https://lodynet.top/"
API_PATH = "wp-content/themes/Lodynet2020/Api/"
DOMAIN_RE = re.compile(r"^https?://(?:www\.)?lodynet\.[a-z]+/", re.I)
# Enigma2 colour codes ("\c00RRGGBB") - only for the list description, never in sidecar / INFO text
COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")
EXPANSION_RE = re.compile(r"GetExpansion\(\s*(\d+)\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*\)")
ITEM_RE = re.compile(r'(?s)<div class="ItemNewly">\s*<a title="([^"]*)" href="([^"]+)"[^>]*>(.*?)</a>')

# Arabic ordinals used in season labels ("الموسم الثاني"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6), ("السادس", 6),
    ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
ORDINAL_ALT = "|".join(o[0] for o in SEASON_ORDINALS)
# "الموسم 2" / "الموسم الثاني" anywhere; "الموسم الأول لمسلسل X" (season folders) at the start
SEASON_RE = re.compile(r"(?:^|\s)(?:ال)?موسم\s*(\d+|%s)(?=\s|$)" % ORDINAL_ALT)
SEASON_HEAD_RE = re.compile(r"^(?:ال)?موسم\s*(\d+|%s)\s+(?:ل|من\s+)?(?:ال)?مسلسل\s+" % ORDINAL_ALT)
EPISODE_RE = re.compile(r"(?:^|\s)(?:ال)?حلقة\s*(?:رقم\s*)?(\d+)")
YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d\d)(?=\s|\)|$)")
# leading "مشاهدة فيلم / الفيلم الهندي / مسلسل ..." and site words that do not belong into a title / file name
LEAD_RE = re.compile(r"^(?:مشاهدة\s+)?(?:ال)?(?:فيلم|مسلسل|برنامج|انمي|أنمي)\s+(?:ال(?:هندي|تركي|كوري|صيني|باكستاني|تايلندي|اجنبي|أجنبي|ياباني|اسيوي|آسيوي)\s+)?")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|مترجم للعربية|اون لاين|أون لاين|مشاهدة|كامل|كاملة|كاملا|بجودة عالية|عربي|والأخيرة|الأخيرة|الاخيرة|والاخيرة|HD|hd|Hd)(?=\s|$)")
JUNK_TAIL_RE = re.compile(r"\s+(?:بجودة\s+\S+.*|مترجم\s+عربي.*)$")
MOVIE_WORDS = ("فيلم",)
SERIES_WORDS = ("مسلسل", "موسم", "برنامج")
# hoster ids of the site: 116413 = ViD LO (vidlo.us, dead); "Lody Plus" (subscription) has no embed and is skipped in _servers
DEAD_SERVER_IDS = ("116413",)
DEAD_SERVER_HOSTS = ("vidlo.us", "viidshar.com", "govad.xyz", "vadbam.net")


def _staticMenu():
    # used when the live navigation can not be read
    return [
        (_("Indian TV series"), "category/مسلسلات-هنديه/"),
        (_("Indian series (dubbed)"), "dubbed-indian-series-p5/"),
        (_("Indian Movies"), "category/افلام-هندية/"),
        (_("Turkish Series"), "category/مسلسلات-تركي/"),
        (_("Turkish series (dubbed)"), "dubbed-turkish-series-g/"),
        (_("Korean TV series"), "korean-series-b/"),
        (_("Foreign movies"), "category/افلام-اجنبية-مترجمة-a/"),
        (_("Shows and concerts"), "category/البرامج-و-حفلات-tv/"),
    ]


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


def _seasonNum(val):
    if not val:
        return 0
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


class Lodynet(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "lodynet.history", "cookie": "lodynet.cookie"})
        self.MAIN_URL = SITE_URL
        self.DEFAULT_ICON_URL = SITE_URL + "wp-content/themes/Lodynet2020/Img/Logo.webp"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept-Language": "ar,en-US;q=0.7,en;q=0.3"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.apiBase = ""
        self.watchedHelper = IPTVWatchedHelper("lodynet")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        # one form for requests, the downloaded marker and favourites: the live domain, percent-encoded,
        # with the trailing slash the site redirects to
        url = ensure_str(url or "").replace("&amp;", "&").replace("\\/", "/").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = self.MAIN_URL + url.lstrip("/")
        url = DOMAIN_RE.sub(self.MAIN_URL, url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        if "?" not in url and "#" not in url and not url.endswith("/") and not re.search(r"\.(?:php|jpe?g|png|webp|gif)$", url, re.I):
            url += "/"
        return url

    def _iconUrl(self, url):
        url = ensure_str(url or "").replace("\\/", "/").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = self.MAIN_URL + url.lstrip("/")
        url = DOMAIN_RE.sub(self.MAIN_URL, url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    @staticmethod
    def _slug(url):
        # last path element of a content url, decoded - stable across domains, encodings and pages
        path = re.sub(r"^https?://[^/]+", "", ensure_str(url or "")).split("?")[0].split("#")[0].strip("/")
        return urllib_unquote(path).lower()

    def _setDomain(self, finalUrl):
        m = DOMAIN_RE.match(ensure_str(finalUrl or ""))
        if m and m.group(0).lower() != "https://lodynet.watch/" and m.group(0) != self.MAIN_URL:
            printDBG("Lodynet: live domain %s" % m.group(0))
            self.MAIN_URL = m.group(0)
            self.apiBase = ""

    def _readApiBase(self, data):
        base = self.cm.ph.getSearchGroups(data, r"""['"](https?://[^'"]+/Api/)RequestExpansion\.php['"]""")[0]
        if base:
            self.apiBase = base

    def _api(self, name):
        return (self.apiBase or (self.MAIN_URL + API_PATH)) + name

    def _clean(self, text):
        text = re.sub(r"\s+", " ", self.cleanHtmlStr(text or "")).strip()
        text = LEAD_RE.sub("", text)
        text = JUNK_TAIL_RE.sub("", text)
        text = JUNK_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip(" -:|")

    def _parseTitle(self, title, epHint=""):
        # site label -> {"kind": movie|episode|series|other, "show", "season", "episode", "year", "name"}
        raw = re.sub(r"\s+", " ", self.cleanHtmlStr(title or "")).strip()
        info = {"kind": "other", "show": "", "season": 0, "episode": "", "year": "", "name": raw}
        work = raw
        m = SEASON_HEAD_RE.match(work)
        season = 0
        if m:
            season = _seasonNum(m.group(1))
            work = work[m.end():]
        isSeries = any(w in raw for w in SERIES_WORDS)
        isMovie = not isSeries and any(w in raw for w in MOVIE_WORDS)
        m = EPISODE_RE.search(work)
        # the cover's episode badge also sits on movies (part number) - only trusted for non-movies
        hint = str(epHint) if epHint and str(epHint) != "0" and not isMovie else ""
        episode = m.group(1) if m else hint
        if m:
            work = work[:m.start()]
        m = SEASON_RE.search(work)
        if m:
            season = season or _seasonNum(m.group(1))
            work = (work[:m.start()] + " " + work[m.end():]).strip()
        work = self._clean(work)
        year = ""
        m = None
        for m in YEAR_RE.finditer(work):
            pass
        if m:
            year = m.group(1)
            if isMovie and m.start() > 0:
                work = work[:m.start()].strip(" -(") or work
            elif isMovie:
                work = work[m.end():].strip(" -)") or work
            elif isSeries or episode:
                work = (work[:m.start()] + " " + work[m.end():]).strip(" -()")
        work = re.sub(r"\s+", " ", work).strip(" -:|")
        info.update({"show": work, "season": season or 1, "episode": episode, "year": year, "name": work})
        if episode:
            info["kind"] = "episode"
        elif isSeries:
            info["kind"] = "series"
        elif isMovie:
            info["kind"] = "movie"
        return info

    @staticmethod
    def _metaTitle(show):
        # the Latin part of a mixed Arabic/Latin name finds more on TMDb/IMDb ("حياة الآخرين Baskaların Hayatı")
        latin = re.findall(r"[A-Za-z0-9][\w'.:&!?-]*(?:\s+[A-Za-z0-9][\w'.:&!?-]*)*", show or "")
        latin = [x for x in latin if re.search(r"[A-Za-z]{2}", x)]
        best = max(latin, key=len) if latin else ""
        return best if len(best) >= 3 else (show or "")

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category == "lody_video":
                slug = self._slug(cItem.get("url", ""))
                return "post:%s" % slug if slug else ""
            if category == "list_items" and cItem.get("lody_kind", "") == "series":
                slug = self._slug(cItem.get("url", ""))
                return "cat:%s" % slug if slug else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("Lodynet.listMainMenu")
        params = dict(self.defaultParams)
        sts, data = self.cm.getPage(gettytul(), params)
        if sts:
            self._setDomain(self.cm.meta.get("url", ""))
        else:
            sts, data = self.getPage(self.MAIN_URL)
        sections = self._parseNavigation(data) if sts else []
        self.addDir({"name": "category", "category": "list_items", "title": _("Recently added"), "url": self.MAIN_URL,
                     "lody_mode": "newly", "good_for_fav": True})
        if sections:
            for title, url, children in sections:
                if children:
                    self.addDir({"name": "category", "category": "lody_menu", "title": title, "url": url, "lody_children": children, "good_for_fav": False})
                else:
                    self.addDir({"name": "category", "category": "list_items", "title": title, "url": url, "good_for_fav": True})
        else:
            for title, url in _staticMenu():
                self.addDir({"name": "category", "category": "list_items", "title": title, "url": self._canonUrl(url), "good_for_fav": True})
        self.addDir({"name": "category", "category": "list_items", "title": _("Actors"), "url": self._canonUrl("all_actors/"), "good_for_fav": True})
        for item in self.searchItems():
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

    def _parseNavigation(self, data):
        # [(title, url, [(title, url), ...]), ...] from <ul class="FirstFormMenu">
        nav = self.cm.ph.getDataBeetwenMarkers(data, 'class="FirstFormMenu"', 'class="IndexContainer"', False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, 'class="FirstFormMenu"', '</nav>', False)[1]
        sections = []
        for chunk in nav.split('class="FirstItemsMenu"')[1:]:
            links = []
            for href, title in re.findall(r'<a[^>]+href="([^"]*)"[^>]*>(.*?)</a>', chunk, re.S):
                title = self.cleanHtmlStr(title).replace("⌵", "").replace("〱", "").strip()
                if not title:
                    continue
                if href.strip() in ("", "#") or "contact" in href:
                    links.append((title, ""))
                else:
                    links.append((title, self._canonUrl(href)))
            if not links:
                continue
            topTitle, topUrl = links[0]
            if topUrl and self._slug(topUrl) == "":
                continue  # "الرئيسية" (home)
            children = [(t, u) for t, u in links[1:] if u]
            if not topUrl and not children:
                continue
            if topUrl and children:
                children.insert(0, (_("All"), topUrl))
            sections.append((topTitle, topUrl, children))
        return sections

    def listMenuSection(self, cItem):
        for title, url in cItem.get("lody_children", []):
            self.addDir({"name": "category", "category": "list_items", "title": title, "url": url, "good_for_fav": True})

    ###################################################
    # lists
    ###################################################
    def _itemFromEntry(self, title, url, icon, ribbon="", date="", epHint=""):
        url = self._canonUrl(url)
        title = re.sub(r"\s+", " ", self.cleanHtmlStr(title)).strip()
        if not title or not url:
            return None
        fields = ((_("Type"), self.cleanHtmlStr(ribbon), "yellow"), (_("Added"), (date or "")[:10], "cyan"))
        desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": self._iconUrl(icon), "desc": desc}
        path = self._slug(url)
        if "/" in path:
            # a listing (category/ = series, season or section; actor/, tag/, release-year/ ...) - posts are one path element
            info = self._parseTitle(title)
            kind = "actor" if path.startswith("actor/") else ("series" if info["kind"] in ("series", "episode") else "section")
            params.update({"category": "list_items", "title": title, "lody_kind": kind})
            if kind == "series":
                params.update({"s_title": info["show"], "s_season": info["season"], "meta_type": "tv",
                               "meta_title": self._metaTitle(info["show"]), "meta_year": info["year"]})
            return params
        info = self._parseTitle(title, epHint)
        normalize = IsMediaNamingNormalized()
        dispTitle = title
        if info["kind"] == "episode":
            if normalize and info["show"]:
                dispTitle = "%s - %s" % (info["show"], formatSxxExx(info["season"], info["episode"]))
            params.update({"s_title": info["show"], "s_season": info["season"], "s_episode": info["episode"], "meta_type": "tv",
                           "meta_title": self._metaTitle(info["show"]), "meta_year": info["year"]})
        elif info["kind"] == "movie":
            if normalize and info["name"]:
                dispTitle = "%s (%s)" % (info["name"], info["year"]) if info["year"] else info["name"]
                if "مدبلج" in title and "مدبلج" not in dispTitle:
                    dispTitle += " مدبلج"  # the dubbed release next to the subtitled one
            params.update({"meta_type": "movie", "meta_title": self._metaTitle(info["name"]), "meta_year": info["year"]})
        elif normalize:
            dispTitle = self._clean(title) or title
        params.update({"category": "lody_video", "title": dispTitle, "raw_title": title})
        return params

    def _addEntry(self, params):
        if params is None:
            return False
        if params["category"] == "lody_video":
            self.addVideo(params)
        else:
            self.addDir(params)
        return True

    def _expansionPage(self, cItem, page):
        # page >= 2 of a listing through the site's "load more" API; returns (items added, has next)
        expType, expId, first = cItem.get("exp_type", ""), cItem.get("exp_id", ""), int(cItem.get("exp_first", 2) or 2)
        if not expType or not self.apiBase:
            # a jump / favourite without the page-1 data: read it once
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return 0, False
            self._readApiBase(data)
            m = EXPANSION_RE.search(data)
            if not m:
                return 0, False
            first, expType, expId = int(m.group(1)), m.group(2), m.group(3)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self._canonUrl(cItem["url"]), Origin=self.MAIN_URL.rstrip("/"))
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        postData = {"indicator": str(first + page - 2), "type": expType, "id": expId}
        sts, data = self.cm.getPage(self._api("RequestExpansion.php"), params, postData)
        if not sts:
            return 0, False
        try:
            js = json_loads(data)
        except Exception:
            printExc()
            js = None
        if not isinstance(js, dict):
            printDBG("Lodynet: expansion API answered %r" % (data or "")[:100])
            return 0, False
        count = 0
        for item in js.get("Items") or []:
            if not isinstance(item, dict):
                continue
            entry = self._itemFromEntry(ensure_str(item.get("name", "")), ensure_str(item.get("url", "")), ensure_str(item.get("cover", "")),
                                        ensure_str(item.get("ribbon", "")), ensure_str(item.get("Date", "")), item.get("episode", ""))
            count += 1 if self._addEntry(entry) else 0
        return count, bool(js.get("Recall")) and count > 0

    def listItems(self, cItem):
        url = re.sub(r"[?&]page=\d+$", "", cItem.get("url", "") or self.MAIN_URL)
        page = int(cItem.get("page", 1) or 1)
        printDBG("Lodynet.listItems [%s] page %d" % (url, page))
        cItem = dict(cItem, url=url, category="list_items")
        if cItem.get("lody_mode") == "newly":
            tpl = self.MAIN_URL + "page/{page}/"
            sts, data = self.getPage(tpl.format(page=page) if page > 1 else self.MAIN_URL)
            if not sts:
                return
            area = self.cm.ph.getDataBeetwenMarkers(data, 'id="AreaNewly"', 'id="PaginationNewly"', False)[1] or data
            count = 0
            for title, href, body in ITEM_RE.findall(area):
                count += 1 if self._addEntryFromHtml(title, href, body) else 0
            addPagingItems(self, cItem, page, count > 0 and "NextPaginationNewly" in data, 0, tpl)
            return
        tpl = url + ("&" if "?" in url else "?") + "page={page}"
        if page > 1:
            hasNext = self._expansionPage(cItem, page)[1]
            addPagingItems(self, cItem, page, hasNext, 0 if hasNext else page, tpl)
            return
        sts, data = self.getPage(url)
        if not sts:
            return
        self._readApiBase(data)
        count = 0
        for title, href, body in ITEM_RE.findall(data):
            count += 1 if self._addEntryFromHtml(title, href, body) else 0
        m = EXPANSION_RE.search(data)
        if m and count:
            cItem.update({"exp_first": int(m.group(1)), "exp_type": m.group(2), "exp_id": m.group(3)})
        addPagingItems(self, cItem, 1, bool(m) and count > 0, 0, tpl)

    def _addEntryFromHtml(self, title, href, body):
        if "CategoryItem" in href or "CategoryItem" in title:
            return False  # the JS template of the "load more" code
        icon = self.cm.ph.getSearchGroups(body, r'data-src="([^"]*)"')[0]
        ribbon = self.cm.ph.getSearchGroups(body, r'NewlyRibbon">([^<]+)<')[0]
        date = self.cm.ph.getSearchGroups(body, r'data-date="([^"]+)"')[0]
        epHint = self.cm.ph.getSearchGroups(body, r'(?s)NewlyEpNumber[^>]*>.*?(\d+)\s*</div>')[0]
        return self._addEntry(self._itemFromEntry(title, href, icon, ribbon, date, epHint))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Lodynet.listSearchResult [%s]" % searchPattern)
        if not searchPattern:
            return
        if not self.apiBase:
            sts, data = self.getPage(self.MAIN_URL)
            if sts:
                self._readApiBase(data)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self.MAIN_URL, Accept="application/json, text/javascript, */*; q=0.01")
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        sts, data = self.cm.getPage(self._api("RequestSearch.php?value=%s" % urllib_quote_plus(searchPattern)), params)
        if not sts:
            return
        try:
            js = json_loads(data)
        except Exception:
            printExc()
            return
        results = js[1] if isinstance(js, list) and len(js) > 1 and isinstance(js[1], list) else []
        for item in results:
            if not isinstance(item, dict):
                continue
            entry = self._itemFromEntry(ensure_str(item.get("Title", "")), ensure_str(item.get("Url", "")), ensure_str(item.get("Cover", "")),
                                        ensure_str(item.get("Category", "")))
            if entry is not None and entry["category"] == "list_items" and self._slug(entry["url"]).startswith("actor/"):
                entry["lody_kind"] = "actor"
            self._addEntry(entry)

    ###################################################
    # links
    ###################################################
    def _servers(self, data):
        # [(name, id, embed url)] of the free servers in "PostData.ServersWatch"
        servers = []
        block = self.cm.ph.getSearchGroups(data, r"(?s)ServersWatch\s*:\s*(\[.*?\])\s*,\s*\n")[0] or data
        for obj in re.findall(r'\{[^{}]*"Name"[^{}]*\}', block):
            try:
                js = json_loads(obj)
            except Exception:
                continue
            name = ensure_str(js.get("Name", "")).strip()
            sid = str(js.get("Id", ""))
            embed = ensure_str(js.get("Embed", "") or "")
            if not embed or js.get("Encrypted"):
                printDBG("Lodynet: skip subscription server %s" % name)
                continue
            try:
                url = b64Decode(embed).strip().replace("&amp;", "&")
            except Exception:
                printExc()
                continue
            if not url.startswith("http"):
                continue
            if sid in DEAD_SERVER_IDS or any(h in url for h in DEAD_SERVER_HOSTS):
                printDBG("Lodynet: skip dead server %s [%s]" % (name, url))
                continue
            servers.append((name, sid, url))
        return servers

    def _siteInfo(self, data):
        details = self.cm.ph.getDataBeetwenMarkers(data, 'id="ContentDetails"', '</p>', False)[1]
        cast = [self.cleanHtmlStr(a) for a in re.findall(r'class="ActorsDetails"[^>]*>([^<]+)<', details)]
        genres = [self.cleanHtmlStr(g) for g in re.findall(r'class="GenresDetails"[^>]*>([^<]+)<', details)]
        story = details.split('class="TitleDetails"')[0]
        story = re.sub(r"<br\s*/?>", "\n", story)
        lines = [self.cleanHtmlStr(x) for x in story.split("\n")]
        story = " ".join([x for x in lines if x and x not in ("قصة الفيلم", "قصة المسلسل", "القصة")]).strip()
        story = story.split("قراءة المزيد")[0].strip()
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta (?:property="og:description"|name="description") content="([^"]*)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, poster, cast, genres

    def getLinksForVideo(self, cItem):
        printDBG("Lodynet.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        urltab = []
        names = {}
        for name, _sid, url in self._servers(data):
            # the site's server names hide the hoster ("Upnshare" = voe.sx, "Playersb" = mixdrop)
            host = re.sub(r"^www\.", "", self.up.getDomain(url) or "")
            if host and host.split(".")[0].lower() not in name.lower().replace(" ", ""):
                name = "%s [%s]" % (name, host)
            names[name] = names.get(name, 0) + 1
            label = name if names[name] == 1 else "%s (%d)" % (name, names[name])
            urltab.append({"name": label, "url": strwithmeta(url, {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}), "need_resolve": 1})
        if not urltab:
            printDBG("Lodynet: no free server on [%s]" % pageUrl)
            if "ServersWatch" in data:
                SetIPTVPlayerLastHostError(_("Lodynet offers this video only on its subscription servers (Lody Plus / VIP) for now - the free servers usually follow later."))
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("Lodynet.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Lodynet.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, cast, genres = self._siteInfo(data)
            if cast:
                info["actors"] = ", ".join(cast[:8])
            if genres:
                info["genres"] = ", ".join(genres[:6])
        if cItem.get("meta_year"):
            info["year"] = cItem["meta_year"]
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", "")) or {}
            except Exception:
                printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or _stripColors(cItem.get("desc", ""))
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
        printDBG("Lodynet.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "lody_menu":
            self.listMenuSection(self.currItem)
        elif category in ("list_items", "list_episodes", "list_actors", "list_actor_movies"):
            # the last three: favourites of the old host version
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, Lodynet(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("lodynet")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "lody_video" or (cItem.get("category", "") == "list_items" and cItem.get("lody_kind", "") == "series")
