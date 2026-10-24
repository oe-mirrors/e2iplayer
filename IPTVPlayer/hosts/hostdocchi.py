# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host: docchi.pl (anime with Polish subtitles) through its public JSON API
#   latest episodes, trending, airing now, latest / A-Z / movies (First / Jump / Next page), genres, seasons,
#   search; series -> episodes, movies as one video; links = the players of the episode (hoster + fansub group),
#   hosters urlparser does not know are left out; adult titles are not listed
###################################################
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://docchi.pl/"


API_URL = "https://api.docchi.pl/v1/"
# rows are keyed on the site's own page urls (watched flag, downloaded marker, favourites)
SERIES_URL = "https://docchi.pl/production/as/"
SERIES_URL_RE = re.compile(r"/production/as/([^/?#]+)(?:/([^/?#]+))?/?$")
# genres of the site's filter; Hentai / Erotica are the adult part and stay out
GENRES = ("Action", "Adventure", "Avant Garde", "Award Winning", "Boys Love", "Comedy", "Cyberpunk", "Drama", "Ecchi",
          "Fantasy", "Girls Love", "Gourmet", "Harem", "Historical", "Horror", "Isekai", "Josei", "Magic", "Mahou Shoujo",
          "Mecha", "Military", "Music", "Mystery", "Parody", "Psychological", "Romance", "Sci-Fi", "Seinen", "Shoujo",
          "Shounen", "Slice of Life", "Sports", "Steampunk", "Supernatural", "Suspense", "Thriller")
ADULT_GENRES = ("Hentai", "Erotica")
# the lists without the adult flag (latest episodes, trending, season) are checked against the flagged titles of these
# genres - the flag is also set on some Ecchi titles (all 177 flagged titles of the catalogue are in one of the three)
ADULT_LOOKUP_GENRES = ADULT_GENRES + ("Ecchi",)
SEASONS = (("WINTER", 1), ("SPRING", 4), ("SUMMER", 7), ("FALL", 10))
LIST_LIMIT = 50
LOCAL_PAGE_SIZE = 100
# a movie with up to this many parts is one video (one link list), more is a folder
MAX_MOVIE_PARTS = 3
# hosters of the API without a urlparser parser (the check below skips them anyway; this saves the lookup)
UNSUPPORTED = ("mega.nz", "sibnet.ru")


def _s(value):
    # API values as text: numbers (episode numbers, years) included, None -> ""
    if value is None:
        return ""
    if isinstance(value, bool):
        # adult_content comes as "true" / "false"; a real boolean the same way
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return ensure_str(value)


def _isAdult(item):
    # the API flag, or an adult genre (a few Hentai titles have no flag)
    if _s(item.get("adult_content", "") or "").lower() == "true":
        return True
    return bool([g for g in (item.get("genres") or []) if _s(g) in ADULT_GENRES])


def _isMovie(item):
    return _s(item.get("series_type", "") or "").lower() == "movie"


def _seasonNum(title):
    for pattern in (r"(\d+)(?:st|nd|rd|th)\s+Season", r"Season\s+(\d+)", r"\bS(\d+)\b"):
        m = re.search(pattern, title, re.I)
        if m:
            return int(m.group(1))
    # "Mushoku Tensei III: ..." / "Overlord IV"
    m = re.search(r"\s(II|III|IV|V|VI)(?::|$)", title)
    if m:
        return ("II", "III", "IV", "V", "VI").index(m.group(1)) + 2
    return 1


def _metaTitle(title):
    title = re.sub(r"\s*(?:\(\d{4}\)|\(TV\)|:?\s*\d+(?:st|nd|rd|th)\s+Season|:?\s*Season\s+\d+|Part\s+\d+)\s*$", "", title, flags=re.I)
    return title.strip(" -:")


def _epSort(num):
    try:
        return float(num)
    except Exception:
        return 0.0


def _epLabel(num):
    # 12.0 -> "12", 12.5 stays
    num = _s(num)
    return num[:-2] if num.endswith(".0") else num


class Docchi(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "icon", "slug", "ep_num", "season",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "docchi", "cookie": "docchi.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://docchi.pl/logo192.png"
        self.HEADER = self.cm.getDefaultHeader()
        self.HEADER.update({"Accept": "application/json, text/plain, */*", "Referer": self.MAIN_URL, "Origin": self.MAIN_URL.rstrip("/")})
        self.defaultParams = {"header": self.HEADER}
        self.MENU = [{"category": "latest", "title": _("Latest episodes")},
                     {"category": "trending", "title": _("Trending")},
                     {"category": "season_list", "title": _("Airing now"), "f_season": "", "f_year": 0},
                     {"category": "api_list", "title": _("Latest"), "f_sort": "DESC"},
                     {"category": "api_list", "title": _("Anime A-Z"), "f_sort": "ALFABET"},
                     {"category": "api_list", "title": _("Anime movies"), "f_sort": "DESC", "f_movies": True},
                     {"category": "genres", "title": _("Genres")},
                     {"category": "season_years", "title": _("Seasons")}] + self.searchItems()
        self.adultSlugs = None
        self.seriesCache = {}
        self.watchedHelper = IPTVWatchedHelper("docchi")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getApi(self, path, url=None):
        url = url or API_URL + path
        sts, data = self.cm.getPage(url, dict(self.defaultParams))
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    @staticmethod
    def _q(value):
        return urllib_quote(_s(value), safe="")

    def _getAdultSlugs(self):
        # the lists without an adult flag (latest episodes, trending, season) are checked against these slugs
        if self.adultSlugs is None:
            slugs = set()
            for genre in ADULT_LOOKUP_GENRES:
                for item in self.getApi("series/category?name=%s&sort=DESC" % genre) or []:
                    if isinstance(item, dict) and _isAdult(item):
                        slugs.add(_s(item.get("slug", "")))
            self.adultSlugs = slugs
        return self.adultSlugs

    def _getSeries(self, slug):
        if slug not in self.seriesCache:
            data = self.getApi("series/find/%s" % self._q(slug))
            self.seriesCache[slug] = data if isinstance(data, dict) and data.get("slug") else None
        return self.seriesCache[slug]

    def _slugFromItem(self, cItem):
        slug = _s(cItem.get("slug", "") or "")
        epNum = _s(cItem.get("ep_num", "") or "")
        m = SERIES_URL_RE.search(_s(cItem.get("url", "")))
        if m:
            slug = slug or m.group(1)
            epNum = epNum or (m.group(2) or "")
        return slug, epNum

    def _icon(self, url):
        return _s(url or "").strip() or self.DEFAULT_ICON_URL

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year and ("(%s)" % year) not in title:
            return "%s (%s)" % (title, year)
        return title

    def _episodeTitle(self, sTitle, epNum):
        if IsMediaNamingNormalized() and re.match(r"^\d+$", _epLabel(epNum)):
            return "%s - %s" % (sTitle, formatSxxExx(_seasonNum(sTitle), int(_epLabel(epNum))))
        return "%s - %s %s" % (sTitle, _("Episode"), _epLabel(epNum))

    def _desc(self, item):
        desc = []
        kind = _s(item.get("series_type", "") or "")
        if kind and kind != "Nieznany":
            desc.append("%s: %s" % (_("Type"), kind))
        year = _s(item.get("season_year", "") or "")
        if year:
            desc.append("%s: %s" % (_("Year"), year))
        if item.get("episodes"):
            desc.append("%s: %s" % (_("Episodes"), item["episodes"]))
        genres = ", ".join(_s(g) for g in (item.get("genres") or []))
        if genres:
            desc.append("%s: %s" % (_("Genres"), genres))
        return " | ".join(desc)

    def _addSeriesItem(self, item, forceFolder=False):
        # one entry of an API series list -> series folder or movie video
        if not isinstance(item, dict) or _isAdult(item):
            return False
        slug = _s(item.get("slug", "") or "")
        title = self.cleanHtmlStr(_s(item.get("title", "") or ""))
        if not slug or not title:
            return False
        year = _s(item.get("season_year", "") or "")
        titleEn = _s(item.get("title_en", "") or "")
        params = {"name": "category", "good_for_fav": True, "url": SERIES_URL + slug, "slug": slug, "s_title": title,
                  "icon": self._icon(item.get("cover")), "desc": self._desc(item), "meta_title": _metaTitle(titleEn or title), "meta_year": year}
        episodes = item.get("episodes") or 0
        if not forceFolder and _isMovie(item) and episodes <= MAX_MOVIE_PARTS:
            params.update({"category": "movie", "title": self._movieTitle(title, year), "meta_type": "movie"})
            self.addVideo(params)
        else:
            params.update({"category": "series", "title": title, "meta_type": "tv"})
            self.addDir(params)
        return True

    def _addLocalPage(self, cItem, items, forceFolder=False):
        page = max(1, int(cItem.get("page", 1) or 1))
        items = [x for x in items if isinstance(x, dict) and not _isAdult(x) and _s(x.get("slug", "")) not in self._getAdultSlugs()]
        for item in items[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]:
            self._addSeriesItem(item, forceFolder)
        lastPage = (len(items) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage, SERIES_URL)

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = _s(cItem.get("url", "") or "").strip()
            if not url.startswith(SERIES_URL):
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % url
            if cItem.get("category", "") == "series":
                return "series:%s" % url
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "") in ("series", "movie", "episode"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def listLatest(self, cItem):
        printDBG("Docchi.listLatest")
        data = self.getApi("episodes/latest")
        if not isinstance(data, list):
            return
        adult = self._getAdultSlugs()
        seen = set()
        for item in data:
            slug = _s(item.get("anime_id", "") or "")
            epNum = _epLabel(item.get("anime_episode_number", ""))
            title = self.cleanHtmlStr(_s(item.get("title", "") or ""))
            if not slug or not epNum or not title or slug in adult or (slug, epNum) in seen:
                continue
            seen.add((slug, epNum))
            titleEn = _s(item.get("title_en", "") or "")
            group = _s(item.get("translator_title", "") or "")
            self.addVideo({"name": "category", "good_for_fav": True, "category": "episode", "url": "%s%s/%s" % (SERIES_URL, slug, epNum),
                           "slug": slug, "ep_num": epNum, "s_title": title, "title": self._episodeTitle(title, epNum),
                           "season": _seasonNum(title), "icon": self._icon(item.get("cover")),
                           "desc": _("Translator: %s") % group if group else "",
                           "meta_type": "tv", "meta_title": _metaTitle(titleEn or title), "meta_year": ""})

    def listTrending(self, cItem):
        printDBG("Docchi.listTrending")
        data = self.getApi("homepage/trending")
        if isinstance(data, list):
            self._addLocalPage(cItem, data, True)

    def listApi(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        path = "series/list?limit=%d&before=%d&sort=%s" % (LIST_LIMIT, (page - 1) * LIST_LIMIT, cItem.get("f_sort", "DESC"))
        if cItem.get("f_movies"):
            path += "&movies=true"
        printDBG("Docchi.listApi [%s]" % path)
        data = self.getApi(path)
        if not isinstance(data, list):
            return
        for item in data:
            self._addSeriesItem(item)
        # the API tells no total: Next page while a page comes back full
        addPagingItems(self, cItem, page, len(data) >= LIST_LIMIT, 0, SERIES_URL)

    def listGenres(self, cItem):
        for genre in GENRES:
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "genre", "title": genre, "f_genre": genre})
            self.addDir(params)

    def listGenre(self, cItem):
        printDBG("Docchi.listGenre [%s]" % cItem.get("f_genre", ""))
        data = self.getApi("series/category?name=%s&sort=DESC" % self._q(cItem.get("f_genre", "")))
        if isinstance(data, list):
            self._addLocalPage(cItem, data)

    def listSeasonYears(self, cItem):
        for year in range(time.localtime()[0], 1999, -1):
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": False, "category": "seasons", "title": str(year), "f_year": year})
            self.addDir(params)

    def listSeasons(self, cItem):
        year = cItem.get("f_year", 0)
        now = time.localtime()
        labels = {"WINTER": _("Winter"), "SPRING": _("Spring"), "SUMMER": _("Summer"), "FALL": _("Autumn")}
        for season, month in SEASONS:
            if year == now[0] and month > now[1]:
                continue
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "season_list", "title": "%s %s" % (labels[season], year), "f_season": season})
            self.addDir(params)

    def listSeason(self, cItem):
        season, year = cItem.get("f_season", ""), cItem.get("f_year", 0)
        if not season or not year:
            # "Airing now": the anime season of today like the site counts it
            now = time.localtime()
            year = now[0]
            season = [s for s, month in SEASONS if month <= now[1]][-1]
        printDBG("Docchi.listSeason [%s %s]" % (season, year))
        data = self.getApi("homepage/season?season=%s&season_year=%s" % (season, year))
        if isinstance(data, list):
            self._addLocalPage(cItem, data, True)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Docchi.listSearchResult [%s]" % searchPattern)
        data = self.getApi("", "https://docchi.pl/api/search/search?string=%s" % self._q(searchPattern.strip().lower()))
        if isinstance(data, dict):
            for item in data.get("series") or []:
                self._addSeriesItem(item)

    ###################################################
    # series -> episodes
    ###################################################
    def _getEpisodeNumbers(self, slug):
        data = self.getApi("episodes/count/%s" % self._q(slug))
        nums = []
        if isinstance(data, list):
            for item in data:
                num = _epLabel(item.get("anime_episode_number", ""))
                if num and num not in nums:
                    nums.append(num)
        nums.sort(key=_epSort)
        return nums

    def listEpisodes(self, cItem):
        slug, _epNum = self._slugFromItem(cItem)
        printDBG("Docchi.listEpisodes [%s]" % slug)
        series = self._getSeries(slug)
        if series and _isAdult(series):
            return
        sTitle = self.cleanHtmlStr(_s((series or {}).get("title", "") or "")) or cItem.get("s_title", "") or cItem.get("title", "")
        icon = self._icon((series or {}).get("cover") or cItem.get("icon"))
        year = _s((series or {}).get("season_year", "") or "") or cItem.get("meta_year", "")
        titleEn = _s((series or {}).get("title_en", "") or "")
        nums = self._getEpisodeNumbers(slug)
        if not nums:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
            return
        metaTitle = _metaTitle(titleEn or sTitle) if titleEn else cItem.get("meta_title", "") or _metaTitle(sTitle)
        if series and _isMovie(series) and len(nums) <= MAX_MOVIE_PARTS:
            self.addVideo({"name": "category", "good_for_fav": True, "category": "movie", "url": SERIES_URL + slug, "slug": slug,
                           "s_title": sTitle, "title": self._movieTitle(sTitle, year), "icon": icon, "desc": self._desc(series),
                           "meta_type": "movie", "meta_title": metaTitle, "meta_year": year})
            return
        page = max(1, int(cItem.get("page", 1) or 1))
        season = _seasonNum(sTitle)
        for num in nums[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]:
            self.addVideo({"name": "category", "good_for_fav": True, "category": "episode", "url": "%s%s/%s" % (SERIES_URL, slug, num),
                           "slug": slug, "ep_num": num, "s_title": sTitle, "title": self._episodeTitle(sTitle, num), "season": season,
                           "icon": icon, "desc": cItem.get("desc", ""), "meta_type": "tv", "meta_title": metaTitle, "meta_year": year})
        lastPage = (len(nums) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage, SERIES_URL + slug)

    ###################################################
    # links
    ###################################################
    def _getEpisodeLinks(self, slug, epNum, prefix=""):
        data = self.getApi("episodes/find/%s/%s" % (self._q(slug), self._q(epNum)))
        urltab = []
        if not isinstance(data, list):
            return urltab
        seen = set()
        for item in data:
            url = _s(item.get("player", "") or "").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            domain = self.up.getDomain(url)
            if [x for x in UNSUPPORTED if domain == x or domain.endswith("." + x)]:
                continue
            link = strwithmeta(url, {"Referer": self.MAIN_URL})
            if self.up.checkHostSupport(link) != 1:
                printDBG("Docchi: hoster not supported by urlparser [%s]" % url)
                continue
            hosting = _s(item.get("player_hosting", "") or "").strip()
            if not hosting or hosting.lower() == "default":
                hosting = domain
            name = hosting.upper() if hosting == hosting.lower() and "." not in hosting else hosting
            group = _s(item.get("translator_title", "") or "").strip()
            if group:
                name = "%s [%s]" % (name, group)
            if prefix:
                name = "%s - %s" % (prefix, name)
            urltab.append({"name": name, "url": link, "need_resolve": 1})
        return urltab

    def getLinksForVideo(self, cItem):
        printDBG("Docchi.getLinksForVideo [%s]" % cItem.get("url", ""))
        slug, epNum = self._slugFromItem(cItem)
        series = self._getSeries(slug) if slug else None
        if not slug or slug in self._getAdultSlugs() or (series and _isAdult(series)):
            return []
        series = series or {}
        urltab = []
        if epNum:
            urltab = self._getEpisodeLinks(slug, epNum)
        else:
            # a movie row is its title page: the players are on its episode (parts)
            nums = self._getEpisodeNumbers(slug)[:MAX_MOVIE_PARTS]
            for num in nums:
                urltab.extend(self._getEpisodeLinks(slug, num, "%s %s" % (_("Episode"), num) if len(nums) > 1 else ""))
        if not urltab:
            SetIPTVPlayerLastHostError(_("This video is only on hosters E2iPlayer cannot play."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), _s(series.get("description", "") or "")))

    def getVideoLinks(self, videoUrl):
        printDBG("Docchi.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Docchi.getArticleContent [%s]" % cItem.get("url", ""))
        slug, _epNum = self._slugFromItem(cItem)
        series = self._getSeries(slug) if slug else None
        otherInfo = {}
        title = cItem.get("title", "")
        text = ""
        icon = cItem.get("icon", "")
        if series and not _isAdult(series):
            text = _s(series.get("description", "") or "").strip()
            icon = _s(series.get("cover", "") or "") or icon
            titleEn = _s(series.get("title_en", "") or "")
            if titleEn and titleEn != series.get("title"):
                otherInfo["alternate_title"] = titleEn
            if series.get("season_year"):
                otherInfo["year"] = str(series["season_year"])
            if series.get("genres"):
                otherInfo["genres"] = ", ".join(_s(g) for g in series["genres"])
            if series.get("episodes"):
                otherInfo["episodes"] = str(series["episodes"])
            if series.get("aired_from"):
                otherInfo["first_air_date"] = _s(series["aired_from"])[:10]
            if series.get("series_type") and series["series_type"] != "Nieznany":
                otherInfo["type"] = _s(series["series_type"])
        meta = {}
        if cItem.get("meta_title"):
            try:
                meta = getMeta(cItem.get("meta_type", "tv"), cItem["meta_title"], cItem.get("meta_year", "") or otherInfo.get("year", ""))
            except Exception:
                printExc()
        sameAs = {"genre": "genres"}
        for key, value in meta.get("info", {}).items():
            if key not in otherInfo and sameAs.get(key) not in otherInfo:
                otherInfo[key] = value
        plot = meta.get("plot", "")
        if not text:
            text = plot or cItem.get("desc", "")
        elif plot and plot != text:
            text = "%s[/br][/br]%s" % (text, plot)
        if not icon:
            icon = meta.get("poster", "")
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Docchi.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "latest":
            self.listLatest(self.currItem)
        elif category == "trending":
            self.listTrending(self.currItem)
        elif category == "api_list":
            self.listApi(self.currItem)
        elif category == "genres":
            self.listGenres(self.currItem)
        elif category == "genre":
            self.listGenre(self.currItem)
        elif category == "season_years":
            self.listSeasonYears(self.currItem)
        elif category == "seasons":
            self.listSeasons(self.currItem)
        elif category == "season_list":
            self.listSeason(self.currItem)
        elif category == "series":
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
        CHostBase.__init__(self, Docchi(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("docchi")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("series", "movie", "episode")
