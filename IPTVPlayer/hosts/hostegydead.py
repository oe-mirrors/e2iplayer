# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# 09.10.2026 - INFO: Arabic-only titles skip IMDb/Cinemeta/OMDb; season folders "Show - Sxx" when normalising
# 09.10.2026 - the site's Megamax server on throw-away domains (q7v3k8m2p1.top/iframe/<id>, the only server of
#   the newest titles) goes to megamax.me/iframe/<id> when urlparser does not know the domain
# 08.10.2026 - server list hardened (the site sits behind a Cloudflare challenge since ~05.10, not
#   reachable from the PC): <ul ... serversList ...> with any extra classes / quotes, relative data-link
#   urls, the whole POST answer when the list markup changes, one more page load + POST when the answer
#   has no player; plus the download servers (ser-link) urlparser knows
# 03.10.2026 - revived for tv10.egydead.live (c4u1r.sbs only redirects there)
#   Rewrite against the current site:
#   - one list parser for all sections; the kind of a row comes from its url: /serie/ = series
#     (-> seasons), /season/ = season (-> episodes), /assembly/ = film collection (-> films),
#     /episode/ and everything else = VIDEO row keyed on the page url
#   - hoster links (POST View=1 on the title page) fetched in getLinksForVideo and handed to
#     urlparser (need_resolve): megamax.me (most recent titles), hgcloud, mixdrop, playmogo, ...
#   - paging via tools/iptvpaging (First page / Jump / Next page (n/last)); search pages by
#     /page/N/?s=..
#   - watched flag (series -> season -> episode, keys from the url path), downloaded flag (page
#     url), favourites, sidecar, INFO via moviemeta + the site's story/poster/fields,
#     name normalisation ("Title (Year)", "Show - SxxExx"; raw site labels when off)
#   - no colour codes in titles, no retry/sleep loops
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://tv10.egydead.live/"


# Arabic ordinals used in season labels ("الموسم الثاني"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالث", 3), ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8),
    ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:^|\s)(?:ال)?موسم\s*(\d+|%s)(?=\s|$)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"(?:^|\s)(?:ال)?(?:حلقة|حلقه)\s*(\d+)(?=\s|$)")
YEAR_RE = re.compile(r"(?:^|\s)\(?((?:19|20)\d\d)\)?((?:\s+(?:مدبلج|مدبلجة|بالمصري))*)\s*$")
# "مترجم و مدبلج" (subbed and dubbed) -> keep only the dub word
SUBDUB_RE = re.compile(r"مترجم(?:ة)?\s+و\s*(مدبلج(?:ة)?)")
# site words that do not belong into a title / file name (only removed when normalising)
JUNK_RE = re.compile(r"(?:^|\s)(?:مشاهدة|فيلم|مسلسل|انمي|أنمي|كرتون|برنامج|عرض|سلسلة افلام|سلسلة أفلام|سلسلة|جميع مواسم|"
                     r"مترجم|مترجمة|اون لاين|أون لاين|كامل|كاملة|كامله)(?=\s|$)")
# "<li><span>السنه : </span><a>2024</a></li>" fields of a title page -> INFO keys
INFO_FIELDS = (("category", "القسم"), ("genres", "النوع"), ("language", "اللغه"), ("country", "البلد"),
               ("year", "السنه"), ("duration", "مده العرض"), ("quality", "الجوده"), ("station", "القناه"))
PAGE_SIZE = 48


class EgyDead(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a row and is needed to open it again
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "kind", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "egydead", "cookie": "egydead.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/egydead.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("egydead")
        self.wfInitFolderCache()
        self.MENU = [
            {"category": "eg_section", "title": _("Movies"), "section": "movies"},
            {"category": "eg_section", "title": _("Series"), "section": "series"},
            {"category": "eg_section", "title": _("Anime") + " / " + _("Cartoons"), "section": "anime"},
            {"category": "eg_section", "title": _("Others"), "section": "other"},
            {"category": "eg_types", "title": _("Genres"), "url": self.getFullUrl("/type/")},
        ] + self.searchItems()
        self.SECTIONS = {
            "movies": [
                (_("English movies"), "/category/english-movies/"),
                (_("Arabic movies"), "/category/افلام-عربي/"),
                (_("Asian movies"), "/category/افلام-اسيوية/"),
                (_("Turkish Movies"), "/category/افلام-تركية/"),
                (_("Indian movies"), "/category/افلام-هندية/"),
                (_("English movies (dubbed)"), "/category/افلام-اجنبية-مدبلجة/"),
                (_("Turkish movies (dubbed)"), "/category/افلام-تركية-مدبلجة/"),
                (_("Indian movies (dubbed)"), "/category/افلام-هندية-مدبلجة/"),
                (_("Subtitles by Islam El-Gizawy"), "/category/ترجمات-اسلام-الجيزاوي/"),
                (_("Documentary Movies"), "/category/افلام-وثائقية/"),
                (_("Animated movies"), "/category/افلام-كرتون/"),
                (_("Disney cartoon movies (Egyptian dub)"), "/category/افلام-كرتون/افلام-كرتون-ديزني-باللهجة-المصرية/"),
                (_("Movie collections"), "/assembly/"),
            ],
            "series": [
                (_("English TV series"), "/series-category/english-series/"),
                (_("Arabic Series"), "/series-category/arabic-series/"),
                (_("Turkish TV series"), "/series-category/turkish-series/"),
                (_("Latin American series"), "/series-category/latino-series/"),
                (_("Asian TV series"), "/series-category/asian-series/"),
                (_("African series"), "/series-category/african-series/"),
                (_("Documentary series"), "/series-category/documentary-series/"),
                (_("English series (dubbed)"), "/series-category/english-series-dubbed/"),
                (_("Turkish series (dubbed)"), "/series-category/turkish-series-dubbed/"),
                (_("Latin American series (dubbed)"), "/series-category/latino-series-dubbed/"),
                (_("Asian series (dubbed)"), "/series-category/asian-series-dubbed/"),
                (_("All series"), "/serie/"),
                (_("All seasons"), "/season/"),
                (_("Newest Episodes"), "/episode/"),
            ],
            "anime": [
                (_("Anime movies"), "/category/افلام-انمي/"),
                (_("Anime movies") + " 2", "/series-category/anime-movies/"),
                (_("Chinese anime"), "/series-category/chinese-anime/"),
                (_("Korean anime"), "/series-category/korean-anime/"),
                (_("Anime TV series"), "/series-category/anime-series/"),
                (_("Anime series (dubbed)"), "/series-category/anime-series-dubbed/"),
                (_("Animated series"), "/series-category/cartoon-series/"),
                (_("Cartoon series (dubbed)"), "/series-category/cartoon-series-dubbed/"),
            ],
            "other": [
                (_("Shows and concerts"), "/category/عروض-وحفلات/"),
                (_("Sport"), "/category/رياضة/"),
                (_("TV Shows"), "/series-category/tv-shows/"),
            ],
        }

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        # the site links the same page raw-Arabic or percent-encoded - one ASCII form for
        # requests, the downloaded marker and favourites
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        url = self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    @staticmethod
    def _path(url):
        # domain-independent part of a page url (watched keys survive domain changes)
        path = re.sub(r"^https?://[^/]+", "", url or "").split("?")[0].split("#")[0]
        try:
            path = urllib_unquote(path)
        except Exception:
            printExc()
        return path.rstrip("/") + "/"

    def _kind(self, url):
        m = re.match(r"/(serie|season|episode|assembly)/[^/]+/$", self._path(url))
        return m.group(1) if m else "movie"

    @staticmethod
    def _clean(text):
        text = JUNK_RE.sub(" ", SUBDUB_RE.sub(r"\1", text or ""))
        return re.sub(r"\s+", " ", text).strip(" -:|")

    @staticmethod
    def _metaTitle(title):
        # the dub / dialect words are part of the label, not of the title the metadata providers know
        return re.sub(r"\s+", " ", re.sub(r"(?:^|\s)(?:مدبلج|مدبلجة|بالمصري)(?=\s|$)", " ", title or "")).strip()

    @staticmethod
    def _seasonNum(val):
        return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)

    def _parseTitle(self, title, url=""):
        # -> (name, year, season, episode) from a site label + the slug ("...-s02e10/", "...-e10/", "...-s03/")
        name = self._clean(title)
        season, episode, year = 0, 0, ""
        m = EPISODE_RE.search(name)
        if m:
            episode = int(m.group(1))
            name = (name[:m.start()] + " " + name[m.end():]).strip()
        m = SEASON_RE.search(name)
        if m:
            season = self._seasonNum(m.group(1))
            name = (name[:m.start()] + " " + name[m.end():]).strip()
        name = re.sub(r"\s+", " ", name).strip(" -:|")
        m = YEAR_RE.search(name)
        if m and m.start() > 0:
            year = m.group(1)
            name = (name[:m.start()] + " " + m.group(2).strip()).strip(" -:|")
        slug = self._path(url).rstrip("/").split("/")[-1]
        m = re.search(r"-s(\d+)(?:e(\d+))?$", slug)
        if m:
            season = season or int(m.group(1))
            episode = episode or int(m.group(2) or 0)
        m = re.search(r"-e(\d+)$", slug)
        if m:
            episode = episode or int(m.group(1))
        return name, year, season, episode

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or not cItem.get("kind"):
                return ""
            url = cItem.get("url", "")
            if not url:
                return ""
            category = cItem.get("category", "")
            if category == "eg_video":
                return "video:%s" % self._path(url)
            if category == "eg_series":
                return "series:%s" % self._path(url)
            if category == "eg_season":
                return "season:%s" % self._path(url)
            if category == "eg_assembly":
                return "folder:%s" % self._path(url)
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("kind"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # menus
    ###################################################
    def listSection(self, cItem):
        for title, path in self.SECTIONS.get(cItem.get("section", ""), []):
            self.addDir({"name": "category", "category": "eg_list", "good_for_fav": True, "title": title, "url": self._canonUrl(path)})

    def listTypes(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="genresList">', "</ul>", False)[1]
        for url, title in re.findall(r'<a href="([^"]+)"[^>]*>.*?<em>([^<]+)</em>', block, re.S):
            self.addDir({"name": "category", "category": "eg_list", "good_for_fav": True, "title": self.cleanHtmlStr(title), "url": self._canonUrl(url)})

    ###################################################
    # lists
    ###################################################
    def _addEntry(self, cItem, url, title, icon, desc=""):
        url = self._canonUrl(url)
        kind = self._kind(url)
        raw = self.cleanHtmlStr(title)
        name, year, season, episode = self._parseTitle(raw, url)
        normalize = IsMediaNamingNormalized()
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": self._canonUrl(icon) if icon else cItem.get("icon", ""),
                  "desc": desc, "kind": kind}
        if kind == "movie":
            title = ("%s (%s)" % (name, year) if year else name) if normalize else raw
            params.update({"category": "eg_video", "title": title or raw, "meta_type": "movie", "meta_title": self._metaTitle(name), "meta_year": year})
            self.addVideo(params)
        elif kind == "episode":
            season = season or cItem.get("s_season", 0) or 1
            show = name or cItem.get("s_title", "")
            if normalize and episode:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = raw
            params.update({"category": "eg_video", "title": title or raw, "s_title": show, "s_season": season, "s_episode": episode,
                           "meta_type": "tv", "meta_title": self._metaTitle(show), "meta_year": year or cItem.get("meta_year", "")})
            self.addVideo(params)
        elif kind == "season":
            season = season or 1
            title = ("%s - %s" % (name, formatSxxExx(season))) if normalize else raw
            params.update({"category": "eg_season", "title": title or raw, "s_title": name, "s_season": season,
                           "meta_type": "tv", "meta_title": self._metaTitle(name), "meta_year": year or cItem.get("meta_year", "")})
            self.addDir(params)
        elif kind == "serie":
            title = ("%s (%s)" % (name, year) if year else name) if normalize else raw
            params.update({"category": "eg_series", "title": title or raw, "s_title": name,
                           "meta_type": "tv", "meta_title": self._metaTitle(name), "meta_year": year})
            self.addDir(params)
        else:
            params.update({"category": "eg_assembly", "title": (name if normalize else raw) or raw})
            self.addDir(params)

    def _cards(self, html):
        # (url, title, icon, category label) of the <li class="movieItem"> cards
        ret = []
        for item in self.cm.ph.getAllItemsBeetwenMarkers(html, "<li", "</li>"):
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            title = self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0]
            if not title:
                title = self.cm.ph.getDataBeetwenMarkers(item, "<h1", "</h1>", False)[1]
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="cat_name">', "</span>", False)[1])
            ret.append((url, title, icon, label))
        return ret

    def _pageBase(self, url):
        # list url without "/page/N/" and "?page=N"
        url = re.sub(r"[?&]page=\d+/?", "", url)
        return re.sub(r"/page/\d+/?", "/", url)

    def listItems(self, cItem):
        printDBG("EgyDead.listItems [%s]" % cItem.get("url", ""))
        page = int(cItem.get("page", 1) or 1)
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        # the first "posts-list" of a category page holds the pinned posts - the last one the page
        block = ""
        for part in data.split('<ul class="posts-list">')[1:]:
            part = part.split("</ul>")[0]
            if "<li" in part:
                block = part
        seen = set()
        for url, title, icon, label in self._cards(block):
            key = self._path(url)
            if key in seen:
                continue
            seen.add(key)
            self._addEntry(cItem, url, title, icon, label)
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', "</div>", False)[1]
        hasNext = bool(seen) and 'class="next page-numbers"' in pagination
        nums = [int(n.replace(",", "")) for n in re.findall(r'class="page-numbers[^"]*"[^>]*>([\d,]+)<', pagination)]
        lastPage = max(nums + [page]) if hasNext else page
        base = cItem.get("page_base") or self._pageBase(cItem["url"])
        if "?s=" in base:
            # search: no pager on the page - a full page means there may be more
            hasNext = len(seen) >= PAGE_SIZE
            lastPage = 0 if hasNext else page
            tpl = base.replace("?s=", "page/{page}/?s=", 1)
        else:
            tpl = base.rstrip("/") + "/page/{page}/"
        addPagingItems(self, dict(cItem, category="eg_list", page_base=base), page, hasNext, lastPage, tpl)

    def listSeries(self, cItem):
        printDBG("EgyDead.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="seasons-list">', "</ul>", False)[1]
        seasons = []
        for url, title, icon, label in self._cards(block):
            if self._kind(url) != "season":
                continue
            seasons.append((self._parseTitle(self.cleanHtmlStr(title), self._canonUrl(url))[2], url, title, icon))
        if not seasons:
            # a series without season pages: its episodes are on the page itself
            self._listEpisodes(cItem, data)
            return
        seasons.sort(key=lambda s: s[0])
        for _num, url, title, icon in seasons:
            self._addEntry(cItem, url, title, icon, cItem.get("desc", ""))

    def listSeason(self, cItem):
        printDBG("EgyDead.listSeason [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        self._listEpisodes(cItem, data)

    def _listEpisodes(self, cItem, data):
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="EpsList">', "</div>", False)[1]
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or self._parseTitle(cItem.get("title", ""))[0]
        season = cItem.get("s_season", 0) or 1
        episodes = []
        seen = set()
        for url, label in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S):
            url = self._canonUrl(url)
            if self._kind(url) != "episode" or url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(label)
            epNum = self._parseTitle(label, url)[3]
            if normalize and epNum:
                title = "%s - %s" % (show, formatSxxExx(season, epNum))
            else:
                title = label
            episodes.append((epNum, {"name": "category", "good_for_fav": True, "category": "eg_video", "kind": "episode", "title": title, "url": url,
                                     "icon": cItem.get("icon", ""), "desc": cItem.get("desc", ""), "s_title": show, "s_season": season, "s_episode": epNum,
                                     "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")}))
        episodes.sort(key=lambda e: e[0])
        for _num, params in episodes:
            self.addVideo(params)

    def listAssembly(self, cItem):
        printDBG("EgyDead.listAssembly [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="salery-list">', "</ul>", False)[1]
        for url, title, icon, label in self._cards(block):
            self._addEntry(cItem, url, title, icon, label)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EgyDead.listSearchResult [%s]" % searchPattern)
        base = self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern))
        self.listItems(dict(cItem, url=base, page_base=base, page=1))

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cm.ph.getDataBeetwenMarkers(data, '<div class="extra-content">', "</div>", False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(story, "<p>", "</p>", False)[1])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<div class="single-thumbnail">.*?<img[^>]+src="([^"]+)"')[0]
        if not poster:
            poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self._canonUrl(poster) if poster else ""

    def _megamaxMirror(self, url):
        # the site's own Megamax server sits on throw-away domains (q7v3k8m2p1.top/iframe/<id>, /download/<id>)
        # urlparser does not know -> the same id on megamax.me (parserMEGAMAX); the download page is the same
        # mirror page, so it collapses into the watch link
        match = re.match(r"https?://[^/]+/(?:iframe|download)/([A-Za-z0-9]{8,20})/?$", url)
        if match and self.up.checkHostSupport(url) != 1:
            return "https://megamax.me/iframe/%s" % match.group(1)
        return url

    def getLinksForVideo(self, cItem):
        printDBG("EgyDead.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem.get("url", ""))
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=pageUrl)
        params["header"]["Content-Type"] = "application/x-www-form-urlencoded"
        sts, data = self.getPage(pageUrl, params, {"View": "1"})
        if sts and "data-link=" not in data:
            # the POST answer came back without the player (fresh Cloudflare cookie, redirect) - load the
            # page once like the browser does and send the form again
            self.getPage(pageUrl)
            sts, data = self.getPage(pageUrl, params, {"View": "1"})
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        urltab = []
        names = {}
        seen = set()

        def addLink(url, name):
            url = self.getFullUrl(url.replace("&amp;", "&").strip())
            url = self._megamaxMirror(url)
            if not self.cm.isValidUrl(url) or url in seen:
                return
            seen.add(url)
            name = name or self.up.getDomain(url, onlyDomain=True)
            names[name] = names.get(name, 0) + 1
            if names[name] > 1:
                name = "%s %d" % (name, names[name])
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})

        # watch servers: <ul class="serversList ..."><li data-link="..."><p>name</p></li>; the whole answer when
        # the list markup changes
        block = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "serversList"), ("</ul", ">"), False)[1] or data
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            url = self.cm.ph.getSearchGroups(item, r"""data-link=['"]([^'"]+)['"]""")[0]
            if url:
                name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<p", ">"), ("</p", ">"), False)[1]) or self.cleanHtmlStr(item)
                addLink(url, name)
        # download servers (<a class="ser-link" href="...">) of hosters urlparser knows
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, "<li", "</li>"):
            url = self.cm.ph.getSearchGroups(item, r"""class=['"]ser-link['"][^>]+href=['"]([^'"]+)['"]""")[0] or \
                self.cm.ph.getSearchGroups(item, r"""href=['"]([^'"]+)['"][^>]+class=['"]ser-link['"]""")[0]
            if url and self.up.checkHostSupport(self._megamaxMirror(self.getFullUrl(url))) == 1:
                name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "ser-name"), ("</span", ">"), False)[1])
                addLink(url, "%s (%s)" % (name or self.up.getDomain(self.getFullUrl(url), onlyDomain=True), _("Download")))
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("EgyDead.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("EgyDead.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                # Arabic-only titles -> no IMDb/Cinemeta/OMDb (they answer with unrelated English hits)
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        story, poster, info, title = "", "", {}, ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster = self._siteInfo(data)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="singleTitle">', "</div>", False)[1])
            box = self.cm.ph.getDataBeetwenMarkers(data, '<div class="LeftBox">', "</div>", False)[1]
            for item in re.findall(r"<li>(.*?)</li>", box, re.S):
                label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<span>", "</span>", False)[1]).replace(":", "").strip()
                values = [self.cleanHtmlStr(v) for v in re.findall(r"<a[^>]*>(.*?)</a>", item, re.S)]
                value = ", ".join([v for v in values if v])
                for key, word in INFO_FIELDS:
                    if value and label == word:
                        info[key] = value
            views = self.cm.ph.getSearchGroups(data, r'<i class="fa fa-eye"></i>\s*<em>([^<]+)</em>')[0]
            if views:
                info["views"] = views
            date = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="postDate">', "</div>", False)[1])
            date = re.sub(r"^نشر فى\s*", "", date)
            if date:
                info["released"] = date
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", "") or title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("EgyDead.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "eg_section":
            self.listSection(self.currItem)
        elif category == "eg_types":
            self.listTypes(self.currItem)
        elif category == "eg_list":
            self.listItems(self.currItem)
        elif category == "eg_series":
            self.listSeries(self.currItem)
        elif category == "eg_season":
            self.listSeason(self.currItem)
        elif category == "eg_assembly":
            self.listAssembly(self.currItem)
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
        CHostBase.__init__(self, EgyDead(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("egydead")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("eg_video", "eg_series", "eg_season", "eg_assembly")
