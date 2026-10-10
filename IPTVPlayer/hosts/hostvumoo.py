# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# Host for vumoo.gd (English films and series, TMDb based, the players are vidsrc-style embeds)
# 10.10.2026 - new host
#   - Movies / TV Shows / Trending / New Releases / New Episodes / Top IMDb / Genres / Countries / Year / Search,
#     First / Jump / Next page (the site lists at most 50 pages, the last page from its pager where shown)
#   - series: show -> seasons -> episodes (the season pages of the site), not yet aired episodes left out
#   - links: the site's servers (/api/go?t=..&slug=..[&s=..&e=..]&x=N answers with the embed url of server N);
#     only servers urlparser knows are listed (vidcore / vidup / vidfast only with external link decryption on)
#   - the site's "Quick check" page (cookies + a small SHA-256 proof of work) is passed like the browser does
#   - watched flag (show -> season -> episode), favourites reopen without state, downloaded marker on the watch
#     page url (episodes: ?s=N&e=M), "Title (Year)" / "Show - SxxExx" names, sidecar on the links
#   - INFO: the page's schema.org data merged with moviemeta
import hashlib
import re
import struct
from datetime import date

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary, ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://vumoo.gd/"


# the site never lists more than 50 pages (a higher page shows page 50 again)
MAX_PAGES = 50
# servers of the site that urlparser resolves, best first: (label of the site's button, lowercase), needs enc-dec.app
SERVERS = (("vidsrc.mov", False), ("vidsrc-v1", False), ("vidrock", False), ("vixsrc", False), ("vidlink", False),
           ("vidsrc.fyi", False), ("vidnest", False), ("peachify", False),
           ("vidfast", True), ("vidup", True), ("vidcore-v2", True))
# their numbers on 10.10.2026, used when the page with the server list is not at hand
SERVER_FALLBACK = (("0", "vidsrc.mov"), ("15", "vidsrc-V1"), ("5", "vidrock"), ("25", "vixsrc"), ("7", "vidlink"), ("1", "vidsrc.fyi"))
WATCH_RE = re.compile(r"/watch/((movie|tv)-[^/?#]+)")
CARD_RE = re.compile(r'<a class="bf-card[^"]*" href="([^"]+)" title="([^"]*)"[^>]*>(.*?)</a>', re.S)
EPISODE_RE = re.compile(r'<a href="([^"]*[?&]s=(\d+)&(?:amp;)?e=(\d+))"\s+class="ep-card([^"]*)"(.*?)</a>', re.S)
SEASON_RE = re.compile(r'class="season-pill[^"]*"\s+href="[^"]*[?&]s=(\d+)[^"]*"\s+title="([^"]*)"')


class Vumoo(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Vumoo", "cookie": "Vumoo.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        # hv / hv2 are set by the script of the "Quick check" page, hv3 comes from the server
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True,
                              "cookiefile": self.COOKIE_FILE, "cookie_items": {"hv": "1", "hv2": "1"}}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("assets/brands/vumoo/favicon.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movie")},
                     {"category": "list_items", "title": _("TV Shows"), "url": self.getFullUrl("tv")},
                     {"category": "list_items", "title": _("Trending"), "url": self.getFullUrl("trending")},
                     {"category": "list_items", "title": "New Releases", "url": self.getFullUrl("new-releases")},
                     {"category": "list_items", "title": _("New episodes"), "url": self.getFullUrl("new-episodes")},
                     {"category": "list_items", "title": _("Top IMDb"), "url": self.getFullUrl("top-imdb")},
                     {"category": "list_cats", "title": _("Genres"), "cat_kind": "genre"},
                     {"category": "list_cats", "title": _("Countries"), "cat_kind": "country"},
                     {"category": "list_years", "title": _("Year")}] + self.searchItems()
        self.cacheCats = {}
        self.watchedHelper = IPTVWatchedHelper("vumoo")
        self.wfInitFolderCache()

    ###################################################
    # HTTP with the site's "Quick check"
    ###################################################
    @staticmethod
    def _isGate(data):
        return "<title>Quick check" in (data or "")[:2000]

    def _passGate(self, url):
        # what the script of the check page does: GET <path>?__hvtok=1&s=1 -> {"seed", "bits"}, find n with
        # sha256("seed:n") below 2^(32-bits), GET <path>?__hvtok=1&seed=..&n=.. -> sets the hv3 cookie
        path = url.split("#", 1)[0].split("?", 1)[0]
        sts, data = self.cm.getPage(path + "?__hvtok=1&s=1&r=0", dict(self.defaultParams))
        query = "nc=1"
        try:
            js = json_loads(data) if sts else {}
            seed, bits = ensure_str(js.get("seed") or ""), int(js.get("bits") or 0)
            if seed and 0 < bits <= 22:
                target = 2 ** (32 - bits)
                for n in range(1, 2 ** (bits + 4)):
                    digest = hashlib.sha256(ensure_binary("%s:%d" % (seed, n))).digest()
                    if struct.unpack(">I", digest[:4])[0] < target:
                        query = "seed=%s&n=%d" % (seed, n)
                        break
        except Exception:
            printExc()
        sts, data = self.cm.getPage("%s?__hvtok=1&%s&r=0" % (path, query), dict(self.defaultParams))
        ok = sts and re.match(r"^[0-9a-f]{32}", (data or "").strip()) is not None
        printDBG("Vumoo: quick check %s [%s]" % ("passed" if ok else "failed", path))
        return ok

    def getPage(self, url, addParams=None, post_data=None):
        url = url.split("#", 1)[0]
        params = dict(addParams or self.defaultParams)
        sts, data = self.cm.getPage(url, params, post_data)
        if sts and self._isGate(data):
            if self._passGate(url):
                sts, data = self.cm.getPage(url, dict(params), post_data)
            if sts and self._isGate(data):
                printDBG("Vumoo: still the quick check page [%s]" % url)
                return False, ""
        return sts, data

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if not url.startswith("/watch/"):
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % url
            category = cItem.get("category", "")
            if category == "list_episodes":
                return "season:%s" % url
            if category == "list_seasons":
                return "series:%s" % url
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _slugTitle(prefix, slug):
        # "Batman: Knightfall Part 1.." + "movie-batman-knightfall-part-1-knightfall-nh1ooi4u"
        # -> "Batman: Knightfall Part 1 Knightfall" (the site cuts long names in some lists)
        prefix = prefix.rstrip(". ").strip()
        base = re.sub(r"^(?:movie|tv)-", "", slug)
        base = re.sub(r"-[a-z0-9]{8}$", "", base)
        pslug = re.sub(r"[^a-z0-9]+", "-", prefix.lower()).strip("-")
        if not pslug or not base.startswith(pslug):
            return prefix
        rest = base[len(pslug):]
        if not rest:
            return prefix
        words = rest.split("-")
        if rest.startswith("-"):
            words = words[1:]
        else:
            prefix += words.pop(0)  # the cut went through a word
        words = [w.capitalize() for w in words if w]
        return ("%s %s" % (prefix, " ".join(words))).strip()

    def _parseCardTitle(self, label, slug):
        # (kind, name, year, season) of a card title: "Name (2026)" / "Show - Season 4" / "Long Na..Season 7"
        kind = "tv" if slug.startswith("tv-") else "movie"
        name, year, season = label, "", ""
        if kind == "tv":
            match = re.match(r"^(.*?)\s*(?:-\s*|\.\.)Season\s+(\d+)\s*$", label)
            if match:
                name, season = match.group(1), match.group(2)
            if label.find("..") > -1:
                name = self._slugTitle(name, slug)
        else:
            match = re.match(r"^(.*?)\s*\(((?:19|20)\d\d)\)\s*$", label)
            if match:
                name, year = match.group(1), match.group(2)
            if name.endswith(".."):
                name = self._slugTitle(name, slug)
        return kind, name.strip(), year, season

    def _pager(self, data, page):
        # (current page, hasNext, lastPage) from the pager; a page past the end shows the last one again
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination', "</ul>", False)[1]
        if not pager:
            return page, False, 0
        current = self.cm.ph.getSearchGroups(pager, r'aria-current="page"><span class="page-link">(\d+)<')[0]
        current = int(current) if current else page
        last = self.cm.ph.getSearchGroups(pager, r'[?&](?:amp;)?page=(\d+)"\s+rel="last"')[0]
        hasNext = 'rel="next"' in pager and current < MAX_PAGES
        lastPage = min(int(last), MAX_PAGES) if last else (MAX_PAGES if hasNext else current)
        return current, hasNext, max(lastPage, current)

    @staticmethod
    def _pageUrl(url, page):
        url = re.sub(r"[?&]page=\d+", "", url)
        if page <= 1:
            return url
        return "%s%spage=%d" % (url, "&" if "?" in url else "?", page)

    def _ldJson(self, data, kinds=("Movie", "TVSeries")):
        for block in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', data or "", re.S):
            try:
                js = json_loads(block)
            except Exception:
                continue
            if isinstance(js, dict) and js.get("@type") in kinds:
                return js
        return {}

    def _servers(self, data):
        # [(x, label)] of the urlparser-known servers on a watch page, in the order of SERVERS
        found = {}
        for x, label in re.findall(r'name="x" value="(\d+)"[^>]*>(?:\s*<i[^>]*></i>)?([^<]+)<', data or ""):
            found.setdefault(self.cleanHtmlStr(label).lower(), (x, self.cleanHtmlStr(label)))
        return [found[key] for key, _enc in SERVERS if key in found]

    ###################################################
    # lists
    ###################################################
    def listCats(self, cItem):
        printDBG("Vumoo.listCats |%s|" % cItem)
        kind = cItem.get("cat_kind", "genre")
        if not self.cacheCats:
            sts, data = self.getPage(self.getFullUrl("movie"))
            for what, slug, title in re.findall(r'<a href="/(genre|country)/([^"/?]+)" title="([^"]+)"', data if sts else ""):
                cats = self.cacheCats.setdefault(what, [])
                if slug not in [c[0] for c in cats]:
                    cats.append((slug, self.cleanHtmlStr(title)))
        for slug, title in sorted(self.cacheCats.get(kind, []), key=lambda c: c[1].lower()):
            params = stripPagerKeys(dict(cItem), ("cat_kind",))
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl("%s/%s" % (kind, slug))})
            self.addDir(params)

    def listYears(self, cItem):
        printDBG("Vumoo.listYears |%s|" % cItem)
        # the years of the site's filter (2016 and newer)
        for year in range(date.today().year, 2015, -1):
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "list_items", "title": str(year), "url": self.getFullUrl("browser?year%%5B%%5D=%d" % year)})
            self.addDir(params)

    def listItems(self, cItem, fullTitles=None):
        printDBG("Vumoo.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        baseUrl = re.sub(r"[?&]page=\d+", "", cItem["url"])
        sts, data = self.getPage(self._pageUrl(baseUrl, page))
        if not sts:
            return
        page, hasNext, lastPage = self._pager(data, page)
        normalize = IsMediaNamingNormalized()
        seen = set()
        for href, label, body in CARD_RE.findall(data):
            match = WATCH_RE.search(href)
            if not match:
                continue
            slug = match.group(1)
            url = self.getFullUrl("/watch/" + slug)
            if url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(label)
            kind, name, year, season = self._parseCardTitle(label, slug)
            if fullTitles and slug in fullTitles:
                name, year = fullTitles[slug][0], fullTitles[slug][1] or year
            if not name:
                continue
            icon = self.cm.ph.getSearchGroups(body, r'data-lsrc="([^"]+)"')[0] or self.cm.ph.getSearchGroups(body, r'<img[^>]+src="(https?://[^"]+)"')[0]
            desc = []
            stamp = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)class="bf-card__stamp">(.*?)</span>\s*</span>')[0])
            if stamp:
                desc.append(stamp)
            for cls in ("genre", "qual"):
                value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="bf-card__%s">(.*?)</span>' % cls)[0])
                if value:
                    desc.append(value)
            params = stripPagerKeys(dict(cItem), ("cat_kind",))
            params.update({"good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon), "desc": " | ".join(desc),
                           "s_title": name, "s_year": year, "meta_type": kind, "meta_title": name, "meta_year": year})
            # raw label of the site unless it was cut short
            cut = ".." in label or bool(fullTitles and slug in fullTitles)
            if kind == "tv":
                # the card's season is the newest one, the row opens the whole show
                title = name if normalize else label
                if not normalize and cut:
                    title = "%s - %s %s" % (name, _("Season"), season) if season else name
                params.update({"category": "list_seasons", "title": title})
                self.addDir(params)
            else:
                title = label
                if normalize or cut:
                    title = "%s (%s)" % (name, year) if year else name
                params.update({"category": "video", "title": title})
                self.addVideo(params)
        tplParams = dict(cItem)
        tplParams["url"] = baseUrl
        addPagingItems(self, tplParams, page, hasNext, lastPage, self._pageUrl(baseUrl, 2).replace("page=2", "page={page}"))

    def _showPage(self, cItem):
        # (data, show name, show url) of the page of a show / season
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return "", "", ""
        ld = self._ldJson(data, ("TVSeries",))
        name = ensure_str(ld.get("name") or "") or cItem.get("s_title", "") or cItem.get("title", "")
        match = WATCH_RE.search(cItem["url"])
        showUrl = self.getFullUrl("/watch/" + match.group(1)) if match else cItem["url"]
        return data, self.cleanHtmlStr(name), showUrl

    def listSeasons(self, cItem):
        printDBG("Vumoo.listSeasons |%s|" % cItem)
        data, name, showUrl = self._showPage(cItem)
        if not data:
            return
        seasons = []
        for snum, stitle in SEASON_RE.findall(data):
            if snum not in [s[0] for s in seasons]:
                seasons.append((snum, self.cleanHtmlStr(stitle)))
        if len(seasons) <= 1:
            # one season: its episodes are on this page already
            self._addEpisodes(cItem, data, name, showUrl)
            return
        normalize = IsMediaNamingNormalized()
        for snum, stitle in seasons:
            params = stripPagerKeys(dict(cItem))
            title = "%s - %s" % (name, formatSxxExx(snum)) if normalize else "%s - %s %s" % (name, _("Season"), snum)
            avail = self.cm.ph.getSearchGroups(stitle, r"(\d+)\s+available")[0]
            params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "url": "%s?s=%s" % (showUrl, snum),
                           "s_title": name, "season": snum, "desc": "%s: %s" % (_("Episodes"), avail) if avail else ""})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Vumoo.listEpisodes |%s|" % cItem)
        data, name, showUrl = self._showPage(cItem)
        if data:
            self._addEpisodes(cItem, data, name, showUrl)

    def _addEpisodes(self, cItem, data, name, showUrl):
        normalize = IsMediaNamingNormalized()
        servers = "|".join("%s:%s" % s for s in self._servers(data))
        seen = set()
        for _href, snum, enum, _cls, body in EPISODE_RE.findall(data):
            key = (snum, enum)
            if key in seen:
                continue
            seen.add(key)
            epTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="ep-card__t">(.*?)</span>')[0])
            epMeta = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="ep-card__m">(.*?)</span>')[0])
            if normalize:
                title = "%s - %s" % (name, formatSxxExx(snum, enum))
            else:
                title = "%s - %s %s, %s %s" % (name, _("Season"), snum, _("Episode"), enum)
                if epTitle and not re.match(r"^Episode\s+\d+$", epTitle):
                    title += " - " + epTitle
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "episode", "title": title, "url": "%s?s=%s&e=%s" % (showUrl, snum, enum),
                           "s_title": name, "season": snum, "episode": enum, "servers": servers, "meta_type": "tv", "meta_title": name,
                           "desc": " | ".join([x for x in (epTitle, epMeta) if x])})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Vumoo.listSearchResult [%s]" % searchPattern)
        query = urllib_quote_plus(searchPattern)
        # the result page cuts long names, the suggestions have them in full
        fullTitles = {}
        sts, data = self.getPage(self.getFullUrl("api/suggest?q=" + query))
        try:
            for row in json_loads(data) if sts else []:
                if isinstance(row, dict) and row.get("slug") and row.get("title"):
                    fullTitles[ensure_str(row["slug"])] = (self.cleanHtmlStr(ensure_str(row["title"])), ensure_str(row.get("year") or ""))
        except Exception:
            printDBG("Vumoo: no suggestions")
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("browser?keyword=" + query)})
        self.listItems(cItem, fullTitles)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Vumoo.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        match = WATCH_RE.search(url)
        if not match:
            return []
        slug, kind = match.group(1), match.group(2)
        season = self.cm.ph.getSearchGroups(url, r"[?&]s=(\d+)")[0]
        episode = self.cm.ph.getSearchGroups(url, r"[?&]e=(\d+)")[0]
        if kind == "tv" and not (season and episode):
            return []
        servers = [tuple(s.split(":", 1)) for s in (cItem.get("servers") or "").split("|") if ":" in s]
        if not servers:
            sts, data = self.getPage(url)
            servers = self._servers(data) if sts else []
        if not servers:
            servers = list(SERVER_FALLBACK)
        try:
            from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsExternalResolveAllowed
            external = IsExternalResolveAllowed()
        except Exception:
            external = False
        needsExternal = dict(SERVERS)
        urltab = []
        for x, label in servers:
            if needsExternal.get(label.lower()) and not external:
                continue
            goUrl = "%sapi/go?t=%s&slug=%s&x=%s" % (self.MAIN_URL, kind, slug, x)
            if kind == "tv":
                goUrl += "&s=%s&e=%s" % (season, episode)
            urltab.append({"name": label, "url": strwithmeta(goUrl, {"Referer": url}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("Vumoo.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        embed = str(videoUrl)
        if "/api/go?" in embed:
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=videoUrl.meta.get("Referer", self.MAIN_URL) if hasattr(videoUrl, "meta") else self.MAIN_URL)
            sts, data = self.getPage(embed, params)
            if not sts:
                return []
            embed = self.cm.ph.getSearchGroups(data, r'http-equiv="refresh" content="\d+;\s*url=([^"]+)"')[0] or self.cm.ph.getSearchGroups(data, r'<a href="(https?://[^"]+)"')[0]
            embed = embed.replace("&amp;", "&")
        if not self.cm.isValidUrl(embed):
            printDBG("Vumoo: no player url")
            return []
        if self.up.checkHostSupport(embed) != 1:
            printDBG("Vumoo: player not known to urlparser [%s]" % embed)
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(embed, {"Referer": self.MAIN_URL})), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Vumoo.getArticleContent [%s]" % cItem)
        url = cItem.get("url", "")
        mediaType = cItem.get("meta_type", "") or ("tv" if "/watch/tv-" in url else "movie")
        sts, data = self.getPage(url) if url else (False, "")
        ld = self._ldJson(data) if sts else {}
        info = {}

        def names(key):
            return ", ".join(ensure_str(p.get("name", "")) for p in (ld.get(key) or []) if isinstance(p, dict) and p.get("name"))

        if ld:
            genres = ld.get("genre") or []
            if isinstance(genres, list) and genres:
                info["genres"] = ", ".join(ensure_str(g) for g in genres)
            for key, field in (("directors", "director"), ("creators", "creator"), ("cast", "actor"), ("country", "countryOfOrigin"), ("production", "productionCompany")):
                value = names(field)
                if value:
                    info[key] = value
            minutes = self.cm.ph.getSearchGroups(ensure_str(ld.get("duration") or ""), r"PT(\d+)M")[0]
            if minutes:
                info["duration"] = "%d min" % int(minutes)
            released = ensure_str(ld.get("datePublished") or "")
            if released:
                info["first_air_date" if mediaType == "tv" else "released"] = released
            rating = (ld.get("aggregateRating") or {}).get("ratingValue") if isinstance(ld.get("aggregateRating"), dict) else ""
            if rating:
                info["tmdb_rating"] = "%s/10" % ensure_str(rating)
            if ld.get("numberOfSeasons"):
                info["seasons"] = str(ld["numberOfSeasons"])
            if ld.get("numberOfEpisodes"):
                info["episodes"] = str(ld["numberOfEpisodes"])
        title = ensure_str(ld.get("name") or "") or cItem.get("meta_title", "") or cItem.get("s_title", "") or cItem.get("title", "")
        year = cItem.get("meta_year", "") or cItem.get("s_year", "") or ensure_str(ld.get("datePublished") or "")[:4]
        meta = {}
        try:
            if title:
                meta = getMeta(mediaType, title, year, maxYearDiff=1)
        except Exception:
            printExc()
        metaInfo = dict(meta.get("info", {}))
        for key, value in info.items():
            # the services' fields first, the site's fill the gaps
            metaInfo.setdefault(key, value)
        if year and "year" not in metaInfo:
            metaInfo["year"] = year
        plot = self.cleanHtmlStr(ensure_str(ld.get("description") or ""))
        text = plot or meta.get("plot", "") or cItem.get("desc", "")
        if cItem.get("category") == "episode" and cItem.get("desc"):
            text = "%s[/br][/br]%s" % (cItem["desc"], text) if text else cItem["desc"]
        icon = cItem.get("icon", "") or meta.get("poster", "") or ensure_str(ld.get("image") or "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": metaInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_cats":
            self.listCats(self.currItem)
        elif category == "list_years":
            self.listYears(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
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
        CHostBase.__init__(self, Vumoo(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("vumoo")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
