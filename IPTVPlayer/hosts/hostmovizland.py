# -*- coding: utf-8 -*-
LAST_MODIFIED = "12.10.2026"
# MovizLand (موفيز لاند) - WordPress site with Arabic / foreign / Turkish / Asian movies and series, plays,
# anime and TV programmes.
#   - "Latest" (/live/, the site has no further pages there), the site's movie / series / free sections,
#     "All movies" / "All series", genres, the archive filters (category / genre / quality / year) and search,
#     with First page / Jump / Next page (n/last) from the site's pager
#   - episode rows of a list -> one series folder per show; the episode page lists the seasons
#     (mita-single-season-card -> season folders, /series/<show>-<season>/ lists the episodes) or, for a
#     show with one season, the episodes itself; movies and plays are VIDEO rows on their page url
#   - links: the server buttons of <page>/watch/ plus the download links urlparser can resolve
#   - watched flag (series -> season -> episode), downloaded flag, favourites (urls re-based on the current
#     domain), name normalisation ("Title (Year)", "Show - SxxExx" from the Arabic labels), sidecar,
#     INFO via moviemeta + the site's story / rating / year / quality / country / genres / poster
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, E2ColoR, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.moviz.land/"


# Arabic ordinals of season / part labels ("الموسم الثاني", "الجزء الرابع")
SEASON_ORDINALS = [
    ("الحادية عشرة", 11), ("الحادية عشر", 11), ("الثانية عشرة", 12), ("الثانية عشر", 12), ("الثالثة عشرة", 13),
    ("الثالثة عشر", 13), ("الرابعة عشرة", 14), ("الرابعة عشر", 14), ("الخامسة عشرة", 15), ("الخامسة عشر", 15),
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولي", 1), ("الأولى", 1), ("الاولى", 1), ("الاولي", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5),
    ("السادسة", 6), ("السادس", 6), ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8),
    ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:الموسم|الجزء)\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d{2})(?=\s|\)|$)")
KIND_RE = re.compile(r"^\s*(?:مسلسل|برنامج|انمي|أنمي)\s+")
MOVIE_RE = re.compile(r"(?:^|\s)(?:فيلم|مسرحية)(?=\s|$)")
# not part of the show name for the moviemeta lookup ("المحقق كونان مدبلج" -> "المحقق كونان")
META_JUNK_RE = re.compile(r"(?:^|\s)(?:مدبلجة|مدبلج)(?=\s|$)")
EPISODES_PER_PAGE = 100
JUNK_RE = re.compile(r"(?:^|\s)(?:مشاهدة|فيلم|مسرحية|مترجمة|مترجم|كاملة|كامل|اون لاين|أون لاين|بجودة عالية|HD|FHD|"
                     r"جميع الحلقات|جميع المواسم|حصريا|حصرياً|والأخيرة|والاخيرة)(?=\s|$)")
CARD_RE = re.compile(r'(?s)<article\s+class="archive-card"(.*?)>')
SEARCH_CARD_RE = re.compile(r'(?s)<article class="search-card">(.*?)</article>')
EPISODE_CARD_RE = re.compile(r'<a\s+href="([^"]+)"\s+class="episode-card[^"]*"[^>]*>\s*<span class="episode-number">\s*(\d+)\s*</span>')
SEASON_CARD_RE = re.compile(r'(?s)<a class="mita-single-season-card[^"]*" href="([^"]+)">(.*?)</a>')
SERVER_RE = re.compile(r'(?s)<button[^>]+class="server-card[^"]*"\s+data-src="([^"]+)"[^>]*>(.*?)</button>')
DOWNLOAD_RE = re.compile(r'(?s)<a href="([^"]+)"[^>]*class="download-item"\s*>(.*?)</a>')
# card colours of the list desc (label coloured, value white)
CARD_FIELDS = (("Year", "data-year", "cyan"), ("Quality", "data-quality", "yellow"), ("Country", "data-country", "skyblue"),
               ("Duration", "data-duration", "lime"), ("Rating", "data-rating", "orange"), ("Genre", "data-genres", "red"))


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


class MovizLand(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "movizland", "cookie": "movizland.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/movizland135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["Referer"] = self.MAIN_URL
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("movizland")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def _rebase(self, url):
        # urls of favourites / older lists on a previous domain -> the current one; Arabic slugs -> one
        # percent-encoded form (the query - "?s=<search words>" - is left as it is)
        url = (url or "").replace("&amp;", "&").strip()
        m = re.match(r"https?://[^/]+/(.*)$", url)
        url = (self.MAIN_URL + m.group(1)) if m else self.getFullUrl(url)
        path, sep, query = url.partition("?")
        return urllib_quote(urllib_unquote(path), safe=":/%+,;@=&") + sep + query

    @staticmethod
    def _cleanSpaces(text):
        return re.sub(r"\s+", " ", text or "").strip(" -:|")

    @staticmethod
    def _attr(block, name):
        m = re.search(r'%s="([^"]*)"' % name, block)
        return m.group(1) if m else ""

    def _splitTitle(self, title, series=True):
        # "مشاهدة مسلسل The Walking Dead الموسم العاشر الحلقة 14 مترجمة HD" -> "The Walking Dead", 10, "14", ""
        # "مشاهدة فيلم Orion 2025 مترجم كامل HD" -> "Orion", 0, "", "2025"
        # movies keep "الجزء الثاني" (part 2) in the name - it is no season there
        episode = self.cm.ph.getSearchGroups(title, EPISODE_RE.pattern)[0] if series else ""
        season = _seasonNum(title) if series else 0
        show = title
        if episode:
            show = EPISODE_RE.split(show)[0]
        show = SEASON_RE.split(show)[0] if season else show
        show = JUNK_RE.sub(" ", KIND_RE.sub("", JUNK_RE.sub(" ", show)))
        years = YEAR_RE.findall(show)
        year = years[-1] if years else ""
        if year and not episode:
            show = re.sub(r"\(?%s\)?" % year, " ", show)
        show = re.sub(r"\(\s*\)", " ", show)
        return self._cleanSpaces(show), season, episode, year

    def _isSeries(self, title, url):
        if EPISODE_RE.search(title):
            return True
        if MOVIE_RE.search(title):
            # "فيلم انمي ..." / "مسرحية ...": an anime film or a play, not a show
            return False
        if KIND_RE.match(JUNK_RE.sub(" ", title)):
            return True
        try:
            path = urllib_unquote(url)
        except Exception:
            path = url
        return "مسلسل" in path or "/series/" in path

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("mz_video", "mz_series", "mz_season"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
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
            category = cItem.get("category", "")
            if category == "mz_video":
                # the url path without domain: favourites survive a domain change
                path = urllib_unquote(re.sub(r"^https?://[^/]+", "", cItem.get("url", ""))).strip("/")
                return "video:%s" % path if path else ""
            show = cItem.get("s_title", "").lower()
            if category == "mz_series" and show:
                return "series:%s" % show
            if category == "mz_season" and show:
                return "season:%s|%s" % (show, cItem.get("s_season", 0))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("/live/"), "single_page": True, "good_for_fav": True},
            {"category": "mz_sections", "title": _("Movies"), "url": self.getFullUrl("/movies/"), "all_url": self.getFullUrl("/category/movies/"),
             "all_title": _("All movies"), "good_for_fav": True},
            {"category": "mz_sections", "title": _("Series"), "url": self.getFullUrl("/series/"), "all_url": self.getFullUrl("/category/series/"),
             "all_title": _("All series"), "good_for_fav": True},
            {"category": "mz_sections", "title": _("Free"), "url": self.getFullUrl("/free/"), "good_for_fav": True},
            {"category": "mz_genres", "title": _("Genres"), "url": self.getFullUrl("/browse/"), "good_for_fav": True},
            {"category": "mz_filters", "title": _("Filter"), "url": self.getFullUrl("/category/movies/"), "good_for_fav": True},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listSections(self, cItem):
        # the section rows of /movies/, /series/, /free/ ("عرض الكل" of every <section class="movie-section">)
        if cItem.get("all_url"):
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": cItem["all_title"], "url": cItem["all_url"]})
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for block in data.split('class="movie-section"')[1:]:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"(?s)<h2[^>]*>(.*?)</h2>")[0])
            url = self.cm.ph.getSearchGroups(block, r'href="([^"]+)"[^>]*class="[^"]*movie-view-all')[0] or \
                self.cm.ph.getSearchGroups(block, r'href="([^"]*/category/[^"]+)"')[0]
            if not title or not url:
                continue
            url = self._rebase(url)
            if url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": url})

    def listGenres(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for url, inner in re.findall(r'(?s)<a\s+href="([^"]+)"\s+class="genre-card"[^>]*>(.*?)</a>', data):
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'(?s)class="genre-name"[^>]*>(.*?)</div>')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'<img[^>]+alt="([^"]*)"')[0])
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(inner, r'<img[^>]+src="([^"]+)"')[0]
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": self._rebase(url),
                         "icon": self.getFullIconUrl(icon) if icon else ""})

    def _filterGroups(self, data):
        # [(label, [(url, title)])] of <div class="archive-filters"> (one <select aria-label=...> per group)
        groups = []
        block = data[data.find("archive-filters"):] if "archive-filters" in data else ""
        for label, options in re.findall(r'(?s)<select\b[^>]*?aria-label="([^"]*)"[^>]*>(.*?)</select>', block):
            opts = [(url.strip(), self.cleanHtmlStr(title)) for url, title in re.findall(r'(?s)<option\b[^>]*?value="([^"]*)"[^>]*>(.*?)</option>', options)
                    if url.strip()]
            if opts:
                groups.append((self.cleanHtmlStr(label), opts))
        return groups

    def listFilters(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        wanted = cItem.get("filter_label")
        for label, opts in self._filterGroups(data):
            if wanted is None:
                params = dict(cItem)
                params.update({"good_for_fav": True, "title": "%s (%d)" % (label, len(opts)), "filter_label": label})
                self.addDir(params)
            elif label == wanted:
                for url, title in opts:
                    self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": self._rebase(url)})

    def _cardDesc(self, attrs):
        fields = []
        for label, attr, color in CARD_FIELDS:
            value = self.cleanHtmlStr(self._attr(attrs, attr))
            if value:
                fields.append("%s%s:%s %s" % (E2ColoR(color), _(label), E2ColoR("white"), value))
        desc = " | ".join(fields)
        story = self.cleanHtmlStr(self._attr(attrs, "data-story"))
        if story:
            desc = "%s[/br]%s" % (desc, story) if desc else story
        return desc

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        listUrl = self._rebase(cItem["url"])
        printDBG("MovizLand.listItems [%s]" % listUrl)
        sts, data = self.getPage(listUrl)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        cards = []
        # category / genre / filter pages: <article class="archive-card" data-title=... data-url=... data-image=...>
        for attrs in CARD_RE.findall(data):
            cards.append((self._attr(attrs, "data-title"), self._attr(attrs, "data-url"), self._attr(attrs, "data-image"), attrs))
        # search: <article class="search-card"> with the title in <h2 class="search-card-title">
        for item in SEARCH_CARD_RE.findall(data):
            href = self.cm.ph.getSearchGroups(item, r'<a\s+href="([^"]+)"')[0]
            title = self.cm.ph.getSearchGroups(item, r'(?s)class="search-card-title">(.*?)</h2>')[0] or \
                self.cm.ph.getSearchGroups(item, r'aria-label="([^"]+)"')[0]
            cards.append((title, href, self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0], ""))
        seen = set()
        for rawTitle, href, icon, attrs in cards:
            rawTitle = self.cleanHtmlStr(rawTitle)
            if not rawTitle or not href:
                continue
            url = self._rebase(href)
            icon = self.getFullIconUrl(icon) if icon else ""
            if self._isSeries(rawTitle, url):
                # one folder per show and season ("... الجزء الثامن" and "... الجزء السابع" are separate series pages on
                # the site, the one does not lead to the other) - its episode page lists the seasons / episodes
                show, season = self._splitTitle(rawTitle)[:2]
                key = "%s|%s" % (show.lower(), season)
                if not show or key in seen:
                    continue
                seen.add(key)
                if season:
                    title = "%s - %s" % (show, formatSxxExx(season) if normalize else "%s %d" % (_("Season"), season))
                else:
                    title = show
                self.addDir({"name": "category", "category": "mz_series", "good_for_fav": True, "title": title, "url": url, "icon": icon,
                             "desc": self._cardDesc(attrs), "s_title": show, "s_season": season, "meta_type": "tv",
                             "meta_title": self._cleanSpaces(META_JUNK_RE.sub(" ", show)) or show})
                continue
            if url in seen:
                continue
            seen.add(url)
            parts = self._splitTitle(rawTitle, False)
            show, year = parts[0], parts[3]
            year = self._attr(attrs, "data-year") or year
            title = rawTitle
            if normalize and show:
                title = "%s (%s)" % (show, year) if year else show
            self.addVideo({"name": "category", "category": "mz_video", "good_for_fav": True, "title": title, "url": url, "icon": icon,
                           "desc": self._cardDesc(attrs), "meta_type": "movie", "meta_title": show or rawTitle, "meta_year": year})

        if cItem.get("single_page"):
            return
        # WordPress pager: <base>/page/N/ (search: /page/N/?s=...)
        lastPage = max([int(n) for n in re.findall(r'class="(?:next )?page-numbers"[^>]*href="[^"]*/page/(\d+)/', data)] + [page])
        hasNext = bool(cards) and 'class="next page-numbers"' in data
        base = re.sub(r"/page/\d+/", "/", listUrl)
        if "?" in base:
            path, query = base.split("?", 1)
            pageTpl = "%spage/{page}/?%s" % (path if path.endswith("/") else path + "/", query.replace("{", "{{").replace("}", "}}"))
        else:
            pageTpl = "%spage/{page}/" % (base if base.endswith("/") else base + "/")
        listItem = dict(cItem)
        listItem.update({"category": "list_items"})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def _episodeTitle(self, show, season, num, normalize):
        if normalize and num:
            return "%s - %s" % (show, formatSxxExx(season or 1, num))
        return "%s - %s %s" % (show, _("Episode"), num)

    def _addEpisodes(self, cItem, data, season):
        show = cItem.get("s_title", "") or cItem.get("title", "")
        normalize = IsMediaNamingNormalized()
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="episodes-grid"', "</section>", False)[1] or data
        episodes = []
        seen = set()
        for href, num in EPISODE_CARD_RE.findall(block):
            url = self._rebase(href)
            if url in seen:
                continue
            seen.add(url)
            episodes.append((int(num), url))
        episodes.sort()
        # long shows (One Piece: 1100+ episodes on one page) -> local pages; the page number travels in cItem["page"]
        page = cItem.get("page", 1)
        lastPage = max(1, (len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE)
        for num, url in episodes[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]:
            self.addVideo({"name": "category", "category": "mz_video", "good_for_fav": True, "title": self._episodeTitle(show, season, num, normalize),
                           "url": url, "icon": cItem.get("icon", ""), "desc": cItem.get("desc", ""), "s_title": show, "s_season": season,
                           "s_episode": num, "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        if lastPage > 1:
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage, self._rebase(cItem["url"]))
        return len(episodes)

    def listSeries(self, cItem):
        # the folder url is an episode page: its season cards (shows with more seasons) or its episode grid
        printDBG("MovizLand.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        show = cItem.get("s_title", "")
        normalize = IsMediaNamingNormalized()
        seasons = []
        for href, inner in SEASON_CARD_RE.findall(data):
            badge = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'(?s)class="mita-single-season-badge">(.*?)</span>')[0])
            count = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r"(?s)<small>(.*?)</small>")[0])
            cover = self.cm.ph.getSearchGroups(inner, r"url\('([^']+)'\)")[0]
            seasons.append((_seasonNum(badge) or _seasonNum(urllib_unquote(href)), self._rebase(href), badge, count, cover))
        if len(seasons) > 1:
            for num, url, badge, count, cover in sorted(seasons):
                if normalize and num:
                    title = "%s - %s" % (show, formatSxxExx(num))
                else:
                    title = "%s - %s" % (show, badge or "%s %d" % (_("Season"), num))
                if count:
                    title = "%s (%s)" % (title, count)
                params = {"name": "category", "category": "mz_season", "good_for_fav": True, "title": title, "url": url,
                          "icon": self.getFullIconUrl(cover) if cover else cItem.get("icon", ""), "desc": cItem.get("desc", ""), "s_title": show,
                          "s_season": num, "meta_type": "tv", "meta_title": cItem.get("meta_title", show)}
                self.addDir(params)
            return
        # the season of the title first: a single season card's badge is often wrong ("... الجزء الثامن" -> "الموسم 1")
        season = cItem.get("s_season", 0) or (seasons[0][0] if seasons else 0) or 1
        if self._addEpisodes(cItem, data, season):
            return
        # no season / episode list: the page itself is the video, named after its own title ("... الحلقة 1")
        params = dict(cItem)
        params.update({"category": "mz_video", "good_for_fav": True})
        pageTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="detail-title">(.*?)</h2>')[0])
        episode = self.cm.ph.getSearchGroups(pageTitle, EPISODE_RE.pattern)[0]
        if episode:
            season = _seasonNum(pageTitle) or season
            params.update({"title": self._episodeTitle(cItem.get("s_title", "") or cItem.get("title", ""), season, int(episode), normalize),
                           "s_season": season, "s_episode": int(episode)})
        self.addVideo(params)

    def listSeason(self, cItem):
        printDBG("MovizLand.listSeason [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        if not self._addEpisodes(cItem, data, cItem.get("s_season", 0) or 1):
            SetIPTVPlayerLastHostError(_("No stream available"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MovizLand.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/?s=%s" % urllib_quote_plus(searchPattern.strip())), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("MovizLand.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = self._rebase(cItem.get("url", ""))
        sts, data = self.getPage(url.rstrip("/") + "/watch/")
        if not sts or "server-card" not in data:
            sts, data = self.getPage(url)
            if not sts:
                return []
        urltab = []
        seen = set()
        for href, inner in SERVER_RE.findall(data):
            href = href.replace("&amp;", "&").strip()
            if href.startswith("//"):
                href = "https:" + href
            if not self.cm.isValidUrl(href) or href in seen:
                continue
            seen.add(href)
            num = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'(?s)class="server-number">(.*?)</span>')[0])
            domain = self.cm.ph.getSearchGroups(href, r"https?://(?:www\.)?([^/:]+)")[0]
            name = "%s %s (%s)" % (_("Server"), num, domain) if num else domain
            urltab.append({"name": name, "url": strwithmeta(href, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        # download links: only the hosters urlparser knows (1fichier, mixdrop, mediafire, mp4upload ...)
        for href, inner in DOWNLOAD_RE.findall(data):
            href = href.replace("&amp;", "&").strip()
            if not self.cm.isValidUrl(href) or href in seen or self.up.checkHostSupport(href) != 1:
                continue
            seen.add(href)
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r"(?s)<strong>(.*?)</strong>")[0])
            domain = self.cm.ph.getSearchGroups(href, r"https?://(?:www\.)?([^/:]+)")[0]
            name = "%s %s (%s)" % (_("Download"), quality, domain) if quality else "%s (%s)" % (_("Download"), domain)
            urltab.append({"name": name, "url": strwithmeta(href, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("MovizLand.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        info = {}
        detail = self.cm.ph.getDataBeetwenMarkers(data, 'class="movie-detail"', "<!--", False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(detail, r'(?s)class="detail-story">(.*?)</div>')[0])
        meta = self.cm.ph.getSearchGroups(detail, r'(?s)class="detail-meta">(.*?)</div>')[0]
        for icon, key in (("fa-star", "rating"), ("fa-calendar", "year"), ("fa-film", "quality"), ("fa-earth", "country")):
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(meta, r'(?s)<i class="fas %s[^"]*"></i>(.*?)</span>' % icon)[0])
            if value:
                info[key] = value
        genres = [self.cleanHtmlStr(g) for g in re.findall(r"(?s)<a[^>]*>(.*?)</a>", self.cm.ph.getSearchGroups(detail, r'(?s)class="detail-genres">(.*?)</div>')[0])]
        genres = [g for g in genres if g]
        if genres:
            info["genres"] = ", ".join(genres)
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]+)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getArticleContent(self, cItem):
        printDBG("MovizLand.getArticleContent [%s]" % cItem.get("url", ""))
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
        printDBG("MovizLand.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "mz_sections":
            self.listSections(self.currItem)
        elif category == "mz_genres":
            self.listGenres(self.currItem)
        elif category == "mz_filters":
            self.listFilters(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "mz_series":
            self.listSeries(self.currItem)
        elif category == "mz_season":
            self.listSeason(self.currItem)
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
        CHostBase.__init__(self, MovizLand(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("movizland")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("mz_video", "mz_series", "mz_season")
