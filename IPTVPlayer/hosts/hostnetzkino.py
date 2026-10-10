# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# Netzkino (netzkino.de) - legal, free (ad-funded) German film and series portal.
# 10.10.2026 - new host
#   - data from the site's GraphQL API (data.netzkino.de): its category tree (Home page sections, genres,
#     series, channels, HD-Kino ...), search; 50 titles per page with First / Jump / Next page
#   - plays the plain MP4 of the site (pmd.netzkino-seite.netzkino.de/<pmdUrl>, no token, AVC); the DASH
#     stream of the site is Widevine-protected and not used. The smaller 1000k file is offered too where
#     the server has it. Titles without an MP4 (DRM / not encoded yet) and NetzkinoPlus titles (paid
#     subscription) are left out of the lists.
#   - series -> season -> episode, watched flag on all three levels, favourites reopen without state,
#     downloaded marker on the site's details url (episodes: ?s=..&e=..), "Title (Year)" / "Show - SxxExx"
#     names, sidecar on the links
#   - INFO: the site's synopsis, cast, director, FSK, country merged with moviemeta
#   - the films are licensed for Germany, Austria and Switzerland: a refused MP4 (HTTP 403) gives a
#     geo-blocking message
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import b64Encode, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://www.netzkino.de/"


API_URL = "https://data.netzkino.de/netzkino/graphql"
PMD_URL = "https://pmd.netzkino-seite.netzkino.de/"
PAGE_SIZE = 50
EPISODES_PER_PAGE = 100
# root categories that are feeds for partner portals (Roku, Joyn, Zattoo ...) or the paid NetzkinoPlus
SKIP_ROOTS = ("fremdportale", "roku", "netzkinoplus")
# hero rows of the site and the NetzkinoPlus advertising rows
SKIP_SLUG_RE = re.compile(r"(?:^featured)|netzkinoplus|plus-only", re.IGNORECASE)
PMD_RATE_RE = re.compile(r"_(\d{6,8})(\.mp4)$", re.IGNORECASE)

MOVIE_FIELDS = "id title slug originalTitle productionYear fskRating flags shortSynopsis coverImage { masterUrl } videoSource { pmdUrl }"
SERIES_FIELDS = "id title slug originalTitle productionYear fskRating flags shortSynopsis coverImage { masterUrl }"
DETAIL_FIELDS = ("title originalTitle productionYear productionCountry fskRating flags runtimeInSeconds longSynopsis shortSynopsis "
                 "coverImage { masterUrl }")

ROOTS_QUERY = ("query { roots: allCmsCategories(filter: { parentId: { isNull: true } }, orderBy: [SORT_ORDER_ASC]) { nodes { "
               "title slug kids: cmsCategoriesByParentId { totalCount } content: cmsMovieContentCategoriesByCategoryId { totalCount } } } }")
CATEGORY_QUERY = ("query($slug: String!, $first: Int, $offset: Int, $kids: Boolean!) { category: cmsCategoryBySlug(slug: $slug) { "
                  "title seoDescription "
                  "subcategories: cmsCategoriesByParentId(orderBy: [SORT_ORDER_ASC]) @include(if: $kids) { nodes { title slug "
                  "coverImage { masterUrl } kids: cmsCategoriesByParentId { totalCount } "
                  "content: cmsMovieContentCategoriesByCategoryId { totalCount } } } "
                  "content: cmsMovieContentCategoriesByCategoryId(first: $first, offset: $offset, orderBy: [SORT_ORDER_ASC, CREATED_DATE_DESC]) { "
                  "totalCount nodes { contentMovie { %s } contentSeries { %s } } } } }") % (MOVIE_FIELDS, SERIES_FIELDS)
SEARCH_QUERY = "query($text: String!, $first: Int, $offset: Int) { search(text: $text, first: $first, offset: $offset) { totalCount nodes { id } } }"
SEARCH_DATA_QUERY = ("query($ids: [Guid!]!) { movies: allCmsMovies(filter: { id: { in: $ids } }, first: 50) { nodes { %s } } "
                     "series: allCmsSeries(filter: { id: { in: $ids } }, first: 50) { nodes { %s } } }") % (MOVIE_FIELDS, SERIES_FIELDS)
SEASONS_QUERY = ("query($id: Guid!) { series: cmsSeryById(id: $id) { title slug productionYear longSynopsis coverImage { masterUrl } "
                 "seasons: cmsSeasonsBySeriesId(orderBy: SEASON_IN_SERIES_ASC) { nodes { id title seasonInSeries productionYear "
                 "shortSynopsis coverImage { masterUrl } episodes: cmsEpisodesBySeasonId { totalCount } } } } }")
EPISODES_QUERY = ("query($id: Guid!) { episodes: allCmsEpisodes(filter: { seasonId: { equalTo: $id } }, orderBy: EPISODE_IN_SEASON_ASC) { "
                  "nodes { id title episodeInSeason flags shortSynopsis coverImage { masterUrl } widescreenImage { masterUrl } "
                  "videoSource { pmdUrl } } } }")
MOVIE_SOURCE_QUERY = "query($id: Guid!) { item: cmsMovieById(id: $id) { flags videoSource { pmdUrl } } }"
EPISODE_SOURCE_QUERY = "query($id: Guid!) { item: cmsEpisodeById(id: $id) { flags videoSource { pmdUrl } } }"
PEOPLE_FIELDS = ('cast: %(conn)s(condition: { connectionType: "actor" }) { nodes { person { name } } } '
                 'directors: %(conn)s(condition: { connectionType: "director" }) { nodes { person { name } } } '
                 'writers: %(conn)s(condition: { connectionType: "writer" }) { nodes { person { name } } }')
MOVIE_INFO_QUERY = "query($id: Guid!) { item: cmsMovieById(id: $id) { %s %s } }" % (DETAIL_FIELDS, PEOPLE_FIELDS % {"conn": "cmsMovieContentPeopleByContentMovieId"})
SERIES_INFO_QUERY = ("query($id: Guid!) { item: cmsSeryById(id: $id) { %s %s seasons: cmsSeasonsBySeriesId { totalCount } } }"
                     % (DETAIL_FIELDS, PEOPLE_FIELDS % {"conn": "cmsMovieContentPeopleByContentSeriesId"}))
EPISODE_INFO_QUERY = "query($id: Guid!) { item: cmsEpisodeById(id: $id) { title fskRating runtimeInSeconds longSynopsis shortSynopsis coverImage { masterUrl } } }"


class Netzkino(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "netzkino", "cookie": "netzkino.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Referer": gettytul(), "Origin": gettytul().rstrip("/")})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://www.netzkino.de/static/netzkino/apple-touch-icon.png"
        self.watchedHelper = IPTVWatchedHelper("netzkino")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if url == "":
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % url
            category = cItem.get("category", "")
            if category == "nk_series":
                return "series:%s" % url
            if category == "nk_season":
                return "season:%s" % url
        except Exception:
            printExc()
        return ""

    ###################################################
    # API helpers
    ###################################################
    def _gql(self, query, variables=None):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Content-Type": "application/json", "Accept": "application/json"})
        params["raw_post_data"] = True
        sts, data = self.cm.getPage(API_URL, params, json.dumps({"query": query, "variables": variables or {}}))
        if not sts:
            return {}
        try:
            data = json_loads(data)
            if data.get("errors"):
                printDBG("Netzkino._gql errors: %s" % data["errors"])
            return data.get("data") or {}
        except Exception:
            printExc()
        return {}

    def _image(self, image, width=300, height=400):
        # the image CDN scales on request ("edits" = base64 JSON, as the site does) - the originals have up to 1 MB
        url = ensure_str((image or {}).get("masterUrl") or "") if isinstance(image, dict) else ""
        if not url.startswith("http"):
            return ""
        edits = b64Encode(json.dumps({"resize": {"width": width, "height": height, "fit": "inside"}}, separators=(",", ":")))
        return "%s%sedits=%s" % (urllib_quote(url, safe=":/%?=&"), "&" if "?" in url else "?", urllib_quote(edits, safe=""))

    @staticmethod
    def _isFree(flags):
        # NetzkinoPlus titles (paid subscription) carry plus-exclusive / only svod
        flags = flags or []
        if "properties:plus-exclusive" in flags:
            return False
        return not ("properties:svod" in flags and "properties:avod" not in flags)

    @staticmethod
    def _genres(flags):
        return ", ".join(f.split(":", 1)[1] for f in flags or [] if f.startswith("genres:"))

    def _detailsUrl(self, slug):
        return "%sdetails/%s" % (self.MAIN_URL, slug)

    def _listDesc(self, node):
        parts = []
        if node.get("productionYear"):
            parts.append("%s: %s" % (_("Year"), node["productionYear"]))
        if node.get("fskRating") is not None:
            parts.append("FSK %s" % node["fskRating"])
        genres = self._genres(node.get("flags"))
        if genres:
            parts.append("%s: %s" % (_("Genres"), genres))
        synopsis = self.cleanHtmlStr(node.get("shortSynopsis") or "")
        return "\n".join(x for x in (" | ".join(parts), synopsis) if x)

    ###################################################
    # lists
    ###################################################
    def listMain(self, cItem):
        printDBG("Netzkino.listMain")
        roots = (self._gql(ROOTS_QUERY).get("roots") or {}).get("nodes") or []
        menu = []
        for node in roots:
            slug = node.get("slug") or ""
            if not slug or slug in SKIP_ROOTS or SKIP_SLUG_RE.search(slug):
                continue
            if not ((node.get("kids") or {}).get("totalCount") or (node.get("content") or {}).get("totalCount")):
                continue
            title = _("Home page") if slug == "frontpage" else self.cleanHtmlStr(node.get("title") or slug)
            menu.append({"category": "nk_cat", "title": title, "slug": slug})
        if not menu:
            # API not reachable: the fixed entries still open (and fail with a clear empty list)
            menu = [{"category": "nk_cat", "title": _("Home page"), "slug": "frontpage"},
                    {"category": "nk_cat", "title": _("Genres"), "slug": "netzkino-genre"},
                    {"category": "nk_cat", "title": _("Series"), "slug": "serien"}]
        for item in menu:
            item.update({"url": "%skategorie/%s/" % (self.MAIN_URL, item["slug"]), "good_for_fav": True})
        self.listsTab(menu + self.searchItems(), cItem)

    def _addTitles(self, cItem, nodes):
        # nodes: [(kind, node)] kind "movie" / "series"; returns how many were left out
        normalize = IsMediaNamingNormalized()
        skipped = 0
        for kind, node in nodes:
            if not isinstance(node, dict) or not node.get("id") or not node.get("slug"):
                continue
            if not self._isFree(node.get("flags")):
                skipped += 1
                continue
            title = self.cleanHtmlStr(node.get("title") or "")
            year = str(node.get("productionYear") or "")
            params = stripPagerKeys(dict(cItem), ("slug", "search_text"))
            params.update({"good_for_fav": True, "nk_id": node["id"], "nk_slug": node["slug"], "url": self._detailsUrl(node["slug"]),
                           "s_title": title, "s_year": year, "icon": self._image(node.get("coverImage")), "desc": self._listDesc(node),
                           "meta_title": self.cleanHtmlStr(node.get("originalTitle") or "") or title, "meta_year": year})
            if kind == "series":
                params.update({"category": "nk_series", "title": title, "meta_type": "tv"})
                self.addDir(params)
                continue
            pmd = ((node.get("videoSource") or {}).get("pmdUrl") or "").strip()
            if not pmd:
                # only the DRM (Widevine) stream or nothing encoded yet
                skipped += 1
                continue
            params.update({"category": "nk_movie", "title": "%s (%s)" % (title, year) if (normalize and year) else title,
                           "pmd": pmd, "meta_type": "movie"})
            self.addVideo(params)
        return skipped

    def listCategory(self, cItem):
        printDBG("Netzkino.listCategory [%s]" % cItem.get("slug", ""))
        page = max(1, int(cItem.get("page", 1) or 1))
        data = self._gql(CATEGORY_QUERY, {"slug": cItem.get("slug", ""), "first": PAGE_SIZE, "offset": (page - 1) * PAGE_SIZE, "kids": page == 1})
        category = data.get("category") or {}
        for node in (category.get("subcategories") or {}).get("nodes") or []:
            slug = node.get("slug") or ""
            if not slug or SKIP_SLUG_RE.search(slug):
                continue
            if not ((node.get("kids") or {}).get("totalCount") or (node.get("content") or {}).get("totalCount")):
                continue
            params = stripPagerKeys(dict(cItem), ("search_text",))
            params.update({"good_for_fav": True, "category": "nk_cat", "title": self.cleanHtmlStr(node.get("title") or slug), "slug": slug,
                           "url": "%skategorie/%s/" % (self.MAIN_URL, slug), "icon": self._image(node.get("coverImage")), "desc": ""})
            self.addDir(params)
        content = category.get("content") or {}
        nodes = []
        for row in content.get("nodes") or []:
            if row.get("contentSeries"):
                nodes.append(("series", row["contentSeries"]))
            elif row.get("contentMovie"):
                nodes.append(("movie", row["contentMovie"]))
        skipped = self._addTitles(cItem, nodes)
        if skipped:
            printDBG("Netzkino.listCategory: %d titles without a free MP4 left out" % skipped)
        total = int(content.get("totalCount") or 0)
        lastPage = (total + PAGE_SIZE - 1) // PAGE_SIZE
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage, "%skategorie/%s/?page={page}" % (self.MAIN_URL, cItem.get("slug", "")))

    def listSearch(self, cItem):
        text = cItem.get("search_text", "")
        printDBG("Netzkino.listSearch [%s]" % text)
        page = max(1, int(cItem.get("page", 1) or 1))
        found = self._gql(SEARCH_QUERY, {"text": text, "first": PAGE_SIZE, "offset": (page - 1) * PAGE_SIZE}).get("search") or {}
        ids = [n.get("id") for n in found.get("nodes") or [] if isinstance(n, dict) and n.get("id")]
        if ids:
            data = self._gql(SEARCH_DATA_QUERY, {"ids": ids})
            # every series is a CmsMovie (without a video) too - the series list wins
            series = dict((n["id"], n) for n in (data.get("series") or {}).get("nodes") or [] if isinstance(n, dict) and n.get("id"))
            movies = dict((n["id"], n) for n in (data.get("movies") or {}).get("nodes") or [] if isinstance(n, dict) and n.get("id"))
            nodes = [("series", series[i]) if i in series else ("movie", movies[i]) for i in ids if i in series or i in movies]
            self._addTitles(cItem, nodes)
        total = int(found.get("totalCount") or 0)
        lastPage = (total + PAGE_SIZE - 1) // PAGE_SIZE
        if lastPage > 1:
            # quote_plus also encodes "{" / "}", so the text can not break the {page} template
            addPagingItems(self, cItem, page, page < lastPage, lastPage, "%ssearch?q=%s&page={page}" % (self.MAIN_URL, urllib_quote_plus(ensure_str(text))))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Netzkino.listSearchResult [%s]" % searchPattern)
        self.listSearch(dict(cItem, category="nk_search", search_text=searchPattern, page=1))

    def listSeasons(self, cItem):
        printDBG("Netzkino.listSeasons [%s]" % cItem.get("nk_id", ""))
        series = self._gql(SEASONS_QUERY, {"id": cItem.get("nk_id", "")}).get("series") or {}
        seasons = [s for s in (series.get("seasons") or {}).get("nodes") or [] if isinstance(s, dict) and s.get("id")]
        seasons = [s for s in seasons if ((s.get("episodes") or {}).get("totalCount") or 0) > 0]
        if not seasons:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
            return
        sTitle = cItem.get("s_title", "") or self.cleanHtmlStr(series.get("title") or "")
        rows = []
        for idx, season in enumerate(seasons):
            num = season.get("seasonInSeries") or (idx + 1)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "nk_season", "season_id": season["id"], "season": str(num), "s_title": sTitle,
                           "url": "%s?s=%s" % (cItem["url"].split("?")[0], num),
                           "icon": self._image(season.get("coverImage")) or cItem.get("icon", ""),
                           "desc": "%s: %d\n%s" % (_("Episodes"), season["episodes"]["totalCount"], self.cleanHtmlStr(season.get("shortSynopsis") or "") or cItem.get("desc", ""))})
            seasonTag = formatSxxExx(num) if IsMediaNamingNormalized() else "%s %s" % (_("Season"), num)
            params["title"] = "%s - %s" % (sTitle, seasonTag)
            rows.append(params)
        if len(rows) == 1:
            self.listEpisodes(rows[0])
            return
        for params in rows:
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Netzkino.listEpisodes [%s]" % cItem.get("season_id", ""))
        episodes = [e for e in (self._gql(EPISODES_QUERY, {"id": cItem.get("season_id", "")}).get("episodes") or {}).get("nodes") or []
                    if isinstance(e, dict) and e.get("id")]
        normalize = IsMediaNamingNormalized()
        sTitle = cItem.get("s_title", "")
        season = cItem.get("season", "1")
        baseUrl = cItem["url"].split("?")[0]
        page = max(1, int(cItem.get("page", 1) or 1))
        lastPage = (len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
        skipped = 0
        for idx, ep in enumerate(episodes[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]):
            pmd = ((ep.get("videoSource") or {}).get("pmdUrl") or "").strip()
            if not pmd or not self._isFree(ep.get("flags")):
                skipped += 1
                continue
            num = ep.get("episodeInSeason") or ((page - 1) * EPISODES_PER_PAGE + idx + 1)
            epTitle = self.cleanHtmlStr(ep.get("title") or "")
            title = "%s - %s" % (sTitle, formatSxxExx(season, num)) if normalize else (epTitle or "%s - %s %s" % (sTitle, _("Episode"), num))
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "nk_episode", "title": title, "nk_ep_id": ep["id"], "ep_num": str(num), "pmd": pmd,
                           "url": "%s?s=%s&e=%s" % (baseUrl, season, num), "ep_title": epTitle,
                           "icon": self._image(ep.get("coverImage")) or cItem.get("icon", ""),
                           "desc": "\n".join(x for x in (epTitle, self.cleanHtmlStr(ep.get("shortSynopsis") or "")) if x)})
            self.addVideo(params)
        if skipped:
            printDBG("Netzkino.listEpisodes: %d episodes without a free MP4 left out" % skipped)
        if lastPage > 1:
            addPagingItems(self, dict(cItem, category="nk_season"), page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def _probe(self, url):
        # HTTP status of the MP4 (one byte); 0 when the server did not answer
        params = {"header": dict(self.HEADER, Range="bytes=0-0"), "max_data_size": 1024, "with_metadata": True,
                  "ignore_http_code_ranges": [(206, 206)]}
        sts, data = self.cm.getPage(url, params)
        try:
            return int((getattr(data, "meta", None) or {}).get("status_code") or (206 if sts else 0))
        except Exception:
            printExc()
        return 200 if sts else 0

    def _link(self, pmd):
        url = PMD_URL + urllib_quote(ensure_str(pmd).lstrip("/"), safe="/")
        rate = PMD_RATE_RE.search(pmd)
        name = "MP4 %dk" % (int(rate.group(1)) // 1000) if rate else "MP4"
        return {"name": name, "url": strwithmeta(url, {"User-Agent": self.HEADER["User-Agent"], "Referer": self.MAIN_URL}), "need_resolve": 0}

    def getLinksForVideo(self, cItem):
        printDBG("Netzkino.getLinksForVideo [%s]" % cItem.get("url", ""))
        pmd = cItem.get("pmd", "")
        if cItem.get("category") == "nk_episode":
            item = self._gql(EPISODE_SOURCE_QUERY, {"id": cItem.get("nk_ep_id", "")}).get("item")
        else:
            item = self._gql(MOVIE_SOURCE_QUERY, {"id": cItem.get("nk_id", "")}).get("item")
        if isinstance(item, dict):
            # the current file name (a favourite may be older than a re-encode)
            pmd = ((item.get("videoSource") or {}).get("pmdUrl") or "").strip()
            if not self._isFree(item.get("flags")):
                pmd = ""
        if not pmd:
            SetIPTVPlayerLastHostError(_("No free player available for this title."))
            return []
        links = [self._link(pmd)]
        status = self._probe(str(links[0]["url"]))
        if status in (403, 451):
            SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking)."))
            return []
        rate = PMD_RATE_RE.search(pmd)
        if rate and int(rate.group(1)) > 1000000:
            # most titles also have a 1000k file (SD, a quarter of the size) - only listed when it is there
            link = self._link(PMD_RATE_RE.sub(r"_1000000\2", pmd))
            if self._probe(str(link["url"])) in (200, 206):
                links.append(link)
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    ###################################################
    # INFO
    ###################################################
    @staticmethod
    def _names(conn, limit=6):
        return ", ".join(n["person"]["name"] for n in ((conn or {}).get("nodes") or [])[:limit] if (n.get("person") or {}).get("name"))

    def getArticleContent(self, cItem):
        printDBG("Netzkino.getArticleContent [%s]" % cItem.get("url", ""))
        category = cItem.get("category", "")
        isMovie = category == "nk_movie"
        site = self._gql(MOVIE_INFO_QUERY if isMovie else SERIES_INFO_QUERY, {"id": cItem.get("nk_id", "")}).get("item") or {}
        episode = {}
        if category == "nk_episode" and cItem.get("nk_ep_id"):
            episode = self._gql(EPISODE_INFO_QUERY, {"id": cItem["nk_ep_id"]}).get("item") or {}
        title = self.cleanHtmlStr(site.get("title") or "") or cItem.get("s_title", "")
        year = str(site.get("productionYear") or cItem.get("s_year", "") or "")
        meta = {}
        try:
            metaTitle = self.cleanHtmlStr(site.get("originalTitle") or "") or cItem.get("meta_title", "") or title
            if metaTitle:
                meta = getMeta("movie" if isMovie else "tv", metaTitle, year, maxYearDiff=1)
                if not meta and title and title != metaTitle:
                    meta = getMeta("movie" if isMovie else "tv", title, year, maxYearDiff=1)
        except Exception:
            printExc()
        info = dict(meta.get("info", {}))
        if year:
            info["year"] = year
        original = self.cleanHtmlStr(site.get("originalTitle") or "")
        if original and original != title:
            info["original_title"] = original
        fsk = episode.get("fskRating", site.get("fskRating"))
        if fsk is not None:
            info["rated"] = "FSK %s" % fsk
        runtime = episode.get("runtimeInSeconds") or site.get("runtimeInSeconds")
        if runtime:
            info["duration"] = "%d min" % max(1, int(runtime) // 60)
        if site.get("productionCountry"):
            info["country"] = site["productionCountry"]
        genres = self._genres(site.get("flags"))
        if genres and "genres" not in info:
            info["genres"] = genres
        for key, conn in (("actors", "cast"), ("directors", "directors"), ("writers", "writers")):
            names = self._names(site.get(conn))
            if names:
                info[key] = names
        if not isMovie and (site.get("seasons") or {}).get("totalCount"):
            info["seasons"] = str(site["seasons"]["totalCount"])
        story = self.cleanHtmlStr(episode.get("longSynopsis") or episode.get("shortSynopsis") or "")
        seriesText = self.cleanHtmlStr(site.get("longSynopsis") or site.get("shortSynopsis") or "") or meta.get("plot", "")
        text = "[/br][/br]".join(x for x in (story, seriesText) if x) or cItem.get("desc", "")
        icon = self._image(episode.get("coverImage") or site.get("coverImage"), 600, 800) or cItem.get("icon", "") or meta.get("poster", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Netzkino.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({"name": "category"})
        elif category == "nk_cat":
            self.listCategory(self.currItem)
        elif category == "nk_series":
            self.listSeasons(self.currItem)
        elif category == "nk_season":
            self.listEpisodes(self.currItem)
        elif category == "nk_search":
            self.listSearch(self.currItem)
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
        CHostBase.__init__(self, Netzkino(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("netzkino")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("nk_series", "nk_season")
