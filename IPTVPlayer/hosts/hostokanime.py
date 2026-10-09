# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# OkAnime (اوك انمي) - Arabic-subtitled anime (okanime.tv is gone; okanime.xyz is the landing page that
# links the current mirror, ww3.okanime.xyz on 09.10.2026)
#   - menu: latest episodes, airing now, most popular, anime list, movies, genres, types, years and search,
#     First page / Jump / Next page over the site's ?page=N
#   - anime -> episodes (VIDEO rows keyed on the episode page url, local paging over 100); every season is
#     its own anime on the site, its number ("2nd Season", "Season 2") goes into the episode names; a movie
#     is one VIDEO row on its anime page
#   - links: the episode page's server list (mp4upload, vkvideo, share4max, streamruby, uqload, videa ...)
#     handed to urlparser, servers without a parser (mega) are left out
#   - watched flag (anime -> episode), downloaded flag, favourites (urls re-based on the current mirror),
#     name normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the anime page
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://ww3.okanime.xyz/"


# landing page that always links the current mirror
LANDING_URL = "https://okanime.xyz/"
LOCAL_PAGE_SIZE = 100
EPISODE_RE = re.compile(r"الحلقة\s*(\d+)")
# "Kami no Shizuku 2nd Season" / "Ao no Hako Season 2": the season number for the episode names
SEASON_RE = re.compile(r"(?i)[\s:-]*(?:(\d+)(?:st|nd|rd|th) season|season ?(\d+))\b")
# "... Sekai wo Suberu II": a trailing roman number is the season
ROMAN_NUMBERS = ("II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")
ROMAN_SEASON_RE = re.compile(r"\s(%s)$" % "|".join(ROMAN_NUMBERS))
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")
EPISODE_CARD_RE = re.compile(r'(?s)<div class="anime-card episode-card">(.*?)</h5>')
EPISODE_LINK_RE = re.compile(r'<a href="([^"]+/episode/[^"]+)"\s+class="ep-compact-btn[^"]*"\s+title="([^"]*)"')
SERVER_RE = re.compile(r'(?s)<a href="javascript:void\(0\);"(.*?)</a>')
INFO_ROW_RE = re.compile(r"(?s)<dt>([^<]+)</dt>\s*<dd>(.*?)</dd>")
INFO_KEYS = {"النوع": "type", "الحالة": "status", "الموسم": "broadcast", "سنة العرض": "year", "عدد الحلقات": "episodes",
             "مدة الحلقة": "duration", "الاستوديو": "production", "التقييم": "rating"}
MOVIE_TYPE = "فيلم"
VIDEO_CATEGORIES = ("ok_video",)
FOLDER_CATEGORIES = ("ok_anime",)


def _splitSeason(name):
    # "Kami no Shizuku 2nd Season" -> ("Kami no Shizuku", 2), "Hyouken no Majutsushi ... II" -> (.., 2);
    # no season word -> (name, 1)
    match = SEASON_RE.search(name or "")
    if not match:
        roman = ROMAN_SEASON_RE.search(name or "")
        if roman:
            return name[:roman.start()].strip(" :-"), ROMAN_NUMBERS.index(roman.group(1)) + 2
        return name, 1
    base = (name[:match.start()] + name[match.end():]).strip(" :-")
    return (base or name), int(match.group(1) or match.group(2))


class OkAnime(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "show_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "okanime", "cookie": "okanime.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/okanime135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("okanime")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def selectDomain(self):
        # the landing page links the current mirror ("https://ww3.okanime.xyz/anime-list")
        if OkAnime.DOMAIN_CACHE:
            self.MAIN_URL = OkAnime.DOMAIN_CACHE
            return
        self.MAIN_URL = gettytul()
        sts, data = self.cm.getPageCFProtection(LANDING_URL, dict(self.defaultParams))
        if sts:
            mirror = self.cm.ph.getSearchGroups(data, r'href="(https?://[^"/]*okanime\.[a-z]+/)anime-list"')[0]
            if mirror:
                self.MAIN_URL = mirror
        OkAnime.DOMAIN_CACHE = self.MAIN_URL

    def getMainUrl(self):
        if self.MAIN_URL is None:
            self.selectDomain()
        return self.MAIN_URL

    def _rebase(self, url):
        # pages of an older mirror (favourites, lists) -> the current one; one percent-encoded form
        url = (url or "").replace("&amp;", "&").strip()
        if not url or re.match(r"^(?!https?:)[a-z]+:", url):
            return url  # empty, file://, data: ...
        if url.startswith("//"):
            url = "https:" + url
        match = re.match(r"https?://[^/]*okanime\.[a-z]+/(.*)$", url)
        if match:
            url = self.getMainUrl() + match.group(1)
        elif not url.startswith("http"):
            url = self.getMainUrl() + url.lstrip("/")
        return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%[]")

    def getFullUrl(self, url, currUrl=None):
        return self._rebase(url)

    def getFullIconUrl(self, url, currUrl=None):
        return self._rebase(url)

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    @staticmethod
    def _path(url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", urllib_unquote(url or "")).split("?")[0].rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("ok_list",):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                return "video:%s" % path
            if category in FOLDER_CATEGORIES:
                return "folder:%s" % path
        except Exception:
            printExc()
        return ""

    @staticmethod
    def _episodeTitle(show, season, episode, label):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (show, formatSxxExx(season or 1, episode))
        return label

    @staticmethod
    def _movieTitle(name, year, label):
        if IsMediaNamingNormalized():
            return "%s (%s)" % (name, year) if year else name
        return label

    @staticmethod
    def _pageTpl(baseUrl):
        return baseUrl.replace("{", "{{").replace("}", "}}") + ("&" if "?" in baseUrl else "?") + "page={page}"

    @staticmethod
    def _pageUrl(baseUrl, page):
        return baseUrl if page <= 1 else "%s%spage=%d" % (baseUrl, "&" if "?" in baseUrl else "?", page)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "ok_latest", "good_for_fav": True, "title": _("Latest episodes"), "url": self.getFullUrl("recently-uploaded-episodes")},
            {"category": "ok_list", "good_for_fav": True, "title": _("Airing now"), "url": self.getFullUrl("state/currently-airing")},
            {"category": "ok_list", "good_for_fav": True, "title": _("Most popular"), "url": self.getFullUrl("top-anime")},
            {"category": "ok_list", "good_for_fav": True, "title": _("Anime list"), "url": self.getFullUrl("anime-list?sort=latest")},
            {"category": "ok_list", "good_for_fav": True, "title": _("Movies"), "url": self.getFullUrl("anime-movies")},
            {"category": "ok_filters", "title": _("Genres"), "filter": "genre"},
            {"category": "ok_filters", "title": _("Types"), "filter": "type"},
            {"category": "ok_filters", "title": _("Year"), "filter": "year"},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listFilters(self, cItem):
        # genre chips / type and year links of the anime list page
        sts, data = self.getPage("anime-list")
        if not sts:
            return
        kind = cItem.get("filter", "")
        if kind == "genre":
            rows = re.findall(r'(?s)href="([^"]*anime-list\?genre%5B0%5D=[^"]+)"[^>]*>.*?<span class="genre-chip-name">([^<]+)</span>', data)
        else:
            rows = re.findall(r'href="([^"]*anime-list\?%s=[^"]+)"[^>]*>\s*([^<]+?)\s*<' % kind, data)
        seen = set()
        for href, label in rows:
            label = self.cleanHtmlStr(label)
            if not label or href in seen:
                continue
            seen.add(href)
            self.addDir({"name": "category", "category": "ok_list", "good_for_fav": True, "title": label, "url": self.getFullUrl(href)})

    def _addAnimeCard(self, block):
        # one anime card -> anime folder, or a VIDEO row for a movie
        href = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)" class="clickable"')[0]
        name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<h4>\s*<a[^>]*>(.*?)</a>')[0])
        if not href or not name:
            return False
        icon = self.cm.ph.getSearchGroups(block, r'(?s)<img[^>]+src="([^"]+)"')[0]
        kind = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<small class="text-muted">([^<]*)</small>')[0])
        episodes = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<h5>\s*<a[^>]*>(.*?)</a>')[0])
        genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r"<li>([^<]+)</li>", block))
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<p class="text-muted">(.*?)</p>')[0])
        fields = " | ".join(x for x in (kind, episodes, genres) if x)
        desc = "%s[/br]%s" % (fields, story) if fields and story else (fields or story)
        url = self.getFullUrl(href)
        show, season = _splitSeason(name)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon) if icon else "", "desc": desc,
                  "s_title": show, "s_season": season, "meta_title": show}
        if kind == MOVIE_TYPE:
            params.update({"category": "ok_video", "title": name, "meta_type": "movie"})
            self.addVideo(params)
        else:
            params.update({"category": "ok_anime", "title": name, "meta_type": "tv"})
            self.addDir(params)
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self.getFullUrl(cItem["url"])
        url = self._pageUrl(baseUrl, page)
        printDBG("OkAnime.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = 0
        for block in data.split('<div class="anime-card anime-hover">')[1:]:
            if self._addAnimeCard(block.split('<div class="col-')[0]):
                count += 1
        hasNext = bool(count) and ("page=%d" % (page + 1)) in data
        listItem = stripPagerKeys(dict(cItem), ("base_url",))
        listItem.update({"category": "ok_list", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, 0, self._pageTpl(baseUrl))

    def listLatest(self, cItem):
        # episode cards: show, episode number, episode page
        page = cItem.get("page", 1)
        baseUrl = self.getFullUrl("recently-uploaded-episodes")
        url = self._pageUrl(baseUrl, page)
        printDBG("OkAnime.listLatest [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        seen = set()
        for block in EPISODE_CARD_RE.findall(data):
            href = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+/episode/[^"]+)"')[0]
            showUrl = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+/anime/[^"]+)"')[0]
            showName = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<h4>\s*<a[^>]*>(.*?)</a>')[0])
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<h5>\s*<a[^>]*>(.*?)</a>')[0])
            if not href or not showName or href in seen:
                continue
            seen.add(href)
            number = EPISODE_RE.search(label)
            episode = number.group(1) if number else self.cm.ph.getSearchGroups(block, r'ep-number-badge">(\d+)<')[0]
            show, season = _splitSeason(showName)
            icon = self.cm.ph.getSearchGroups(block, r'(?s)<img[^>]+src="([^"]+)"')[0]
            self.addVideo({"name": "category", "category": "ok_video", "good_for_fav": True, "url": self.getFullUrl(href),
                           "title": self._episodeTitle(show, season, episode, "%s - %s" % (showName, label) if label else showName),
                           "icon": self.getFullIconUrl(icon) if icon else "", "desc": label, "s_title": show, "s_season": season,
                           "s_episode": episode, "meta_type": "tv", "meta_title": show, "show_url": self.getFullUrl(showUrl) if showUrl else ""})
        hasNext = bool(seen) and ("page=%d" % (page + 1)) in data
        addPagingItems(self, stripPagerKeys(dict(cItem)), page, hasNext, 0, self._pageTpl(baseUrl))

    def _episodeLinks(self, data):
        # [(number, episode page url, label)] of an anime page, by number
        episodes, seen = [], set()
        for href, label in EPISODE_LINK_RE.findall(data):
            if href in seen:
                continue
            seen.add(href)
            number = EPISODE_RE.search(label) or re.search(r"-episode-(\d+)/?$", href)
            episodes.append((int(number.group(1)) if number else len(episodes) + 1, self.getFullUrl(href), self.cleanHtmlStr(label)))
        episodes.sort(key=lambda e: e[0])
        return episodes

    def listAnime(self, cItem):
        printDBG("OkAnime.listAnime [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        episodes = self._episodeLinks(data)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        show = cItem.get("s_title") or _splitSeason(cItem.get("title", ""))[0]
        season = cItem.get("s_season", 1)
        year = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<dt>سنة العرض</dt>\s*<dd>(.*?)</dd>")[0])
        kind = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<dt>النوع</dt>\s*<dd>(.*?)</dd>")[0])
        if kind == MOVIE_TYPE and len(episodes) == 1:
            params = stripPagerKeys(dict(cItem))
            params.update({"category": "ok_video", "title": self._movieTitle(show, year, cItem.get("title", show)), "meta_type": "movie",
                           "meta_year": year})
            self.addVideo(params)
            return
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for number, href, label in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo({"name": "category", "category": "ok_video", "good_for_fav": True, "url": href,
                           "title": self._episodeTitle(show, season, number, "%s - %s" % (cItem.get("title", show), label or number)),
                           "icon": cItem.get("icon", ""), "desc": cItem.get("desc", ""), "show_url": cItem["url"], "s_title": show,
                           "s_season": season, "s_episode": str(number), "meta_type": "tv", "meta_title": cItem.get("meta_title", show),
                           "meta_year": year})
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        printDBG("OkAnime.listSearchResult [%s]" % pattern)
        cItem = dict(cItem)
        base = self.getFullUrl("anime-list?q=%s" % urllib_quote_plus(pattern))
        cItem.update({"category": "ok_list", "s_pattern": pattern, "url": base, "base_url": base})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = self.getFullUrl(cItem.get("url", ""))
        printDBG("OkAnime.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        if "/anime/" in url:
            # a movie row sits on its anime page: its one episode holds the servers
            episodes = self._episodeLinks(data)
            sts, data = self.getPage(episodes[0][1]) if episodes else (False, "")
            if not sts:
                SetIPTVPlayerLastHostError(_("No stream available"))
                return []
        urltab, seen = [], set()
        for block in SERVER_RE.findall(data):
            link = self.cm.ph.getSearchGroups(block, r"""setServer\('([^']+)'\)""")[0].replace("&amp;", "&")
            if not self.cm.isValidUrl(link) or link in seen or self.up.checkHostSupport(link) != 1:
                continue
            seen.add(link)
            server = self.cm.ph.getSearchGroups(block, r'data-server="([^"]*)"')[0].replace("_", " ")
            quality = self.cm.ph.getSearchGroups(block, r'data-umami-event-quality="([^"]*)"')[0]
            name = " ".join(x for x in (server or self.up.getHostName(link, True), quality) if x)
            height = self.cm.ph.getSearchGroups(quality, r"(\d+)")[0]
            urltab.append((-int(height or 0), len(urltab), {"name": name, "url": strwithmeta(link, {"Referer": self.getMainUrl()}), "need_resolve": 1}))
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        # best quality first, the site's order within one quality
        urltab = [link for _height, _idx, link in sorted(urltab, key=lambda x: x[:2])]
        # the same hoster twice in one quality (two mp4upload 720p): numbered to tell them apart
        names = [link["name"] for link in urltab]
        counter = {}
        for link in urltab:
            if names.count(link["name"]) > 1:
                counter[link["name"]] = counter.get(link["name"], 0) + 1
                link["name"] = "%s (%d)" % (link["name"], counter[link["name"]])
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("OkAnime.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of an anime page
        info = {}
        for key, value in INFO_ROW_RE.findall(data):
            key, value = INFO_KEYS.get(self.cleanHtmlStr(key), ""), self.cleanHtmlStr(value)
            if key and value:
                info[key] = value
        genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'class="genre-tag">([^<]+)<', data))
        if genres:
            info["genres"] = genres
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="synopsis-text"[^>]*>(.*?)</div>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, poster, info

    def getArticleContent(self, cItem):
        printDBG("OkAnime.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        url = cItem.get("show_url") or cItem.get("url", "")
        sts, data = self.getPage(url) if "/anime/" in url else (False, "")
        if sts:
            story, poster, info = self._siteInfo(data)
        mediaType = cItem.get("meta_type") or "tv"
        title = cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
        year = cItem.get("meta_year") or self.cm.ph.getSearchGroups(info.get("year", ""), YEAR_RE.pattern)[0]
        meta = {}
        try:
            meta = getMeta(mediaType, title, year, () if isLatinTitle(title) else LATIN_ONLY)
        except Exception:
            printExc()
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        info.update(dict((k, v) for k, v in siteInfo.items() if k in ("episodes", "status", "broadcast", "type")))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = (self.getFullIconUrl(poster) if poster else "") or meta.get("poster") or cItem.get("icon", "")
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
        printDBG("OkAnime.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "ok_list":
            self.listItems(self.currItem)
        elif category == "ok_latest":
            self.listLatest(self.currItem)
        elif category == "ok_filters":
            self.listFilters(self.currItem)
        elif category == "ok_anime":
            self.listAnime(self.currItem)
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
        CHostBase.__init__(self, OkAnime(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("okanime")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
