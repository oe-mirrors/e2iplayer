# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - animezid.cam (animezid.net redirects there; Arabic anime, cartoons and animation films, subbed and
#     dubbed): latest, most viewed, films / series / anime sections (sub-sections as folders) and search,
#     with First page / Jump / Next page from the site's own pager
#   - series -> seasons (/series/<slug>/season/N/, skipped when there is only one) -> episodes (site
#     paging); films and episodes are VIDEO rows keyed on their watch.php?vid= page url
#   - links: the play page's web-playback API (session -> one resolve per source -> one-use launch url
#     that redirects to the hoster embed), unsupported hosters are left out
#   - watched flag (series:/season:/video: keys), downloaded flag, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the page's story / info rows
# 09.10.2026 - links on PyCurl boxes: the play page is loaded like the API calls (the session cookie got lost
#   between urllib and PyCurl -> every server answered 403); site rate limit (429) shown as such
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://animezid.cam/"


# "مشاهدة فيلم حكاية لعبة 5 | Toy Story 5 2026 مدبلج سعودي" -> "حكاية لعبة 5 | Toy Story 5", year 2026
PREFIX_RE = re.compile(r"^\s*(?:مشاهدة\s+|فتح\s+)?(?:مسلسل\s+)?(?:انمي|أنمي|فيلم|فلم|كرتون|مسلسل)\s+")
# the name ends before the first of these words (as a whole word)
TAIL_WORDS = ("مترجمة", "مترجم", "مدبلجة", "مدبلج", "اونلاين", "أونلاين", "اون", "أون", "كامل")
YEAR_RE = re.compile(r"\s(19\d\d|20\d\d)(?=\s|$)")
EPISODE_RE = re.compile(r"الحلقة\s*(\d+)")
SEASON_ORDINALS = [
    ("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثانى", 2), ("الثالث", 3), ("الرابع", 4), ("الخامس", 5),
    ("السادس", 6), ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
SEASON_URL_RE = re.compile(r"/season/(\d+)/?")
# servers without a resolver in urlparser (TeleBox = lbx.to, KoramaUP, ClicknUpload, FreeDL, BowFile, 1CloudFile)
UNSUPPORTED_RE = re.compile(r"(?i)telebox|koramaup|clicknupload|freedl|bowfile|1cloudfile|^mega$")
CARD_RE = re.compile(r'(?s)<article class="az-card[^"]*">(.*?)</article>')
# watch page info rows: <small>السنة</small><a ...>2026</a>
INFO_ROW_RE = re.compile(r"(?s)<small>([^<]+)</small>\s*(?:<a[^>]*>|<strong>|<span[^>]*>)?([^<]*)")
INFO_KEYS = {"السنة": "year", "اللغة": "language", "البلد": "country", "النوع": "genres", "الجودة": "quality",
             "الدقة": "quality", "الترجمة": "translation", "التقييم": "rating", "المدة": "duration",
             "الرقابة": "age_limit", "موسم": "seasons", "حلقة": "episodes", "مشاهدة": "views"}


def _cleanName(title):
    # -> (show / film name, year, season (0 = none), episode)
    title = title or ""
    episode = EPISODE_RE.search(title)
    season = SEASON_RE.search(title)
    name = PREFIX_RE.sub("", title)
    name = SEASON_RE.split(EPISODE_RE.split(name)[0])[0]
    words = name.split()
    for idx, word in enumerate(words):
        if idx and word in TAIL_WORDS:
            words = words[:idx]
            break
    name = " ".join(words)
    year = YEAR_RE.search(name)
    if year:
        name = name[:year.start()]
    name = re.sub(r"\s+", " ", name).strip(" -:|")
    seasonNum = 0
    if season:
        val = season.group(1)
        seasonNum = int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)
    return (name or title.strip()), (year.group(1) if year else ""), seasonNum, (str(int(episode.group(1))) if episode else "")


def _metaTitle(name):
    # "حكاية لعبة 5 | Toy Story 5" / "ون بيس One Piece" -> the Latin words for the metadata search
    for part in name.split("|"):
        latin = " ".join(word for word in part.split() if re.search(r"[A-Za-z]", word))
        if latin:
            return latin
    return name


class AnimeZid(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "series_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "animezid", "cookie": "animezid.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/animezid135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "list_items", "title": _("Latest added"), "url": self.getFullUrl("/newvideos.php")},
            {"category": "list_items", "title": _("Most viewed"), "url": self.getFullUrl("/topvideos.php")},
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/category.php?cat=movies")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/category.php?cat=series")},
            {"category": "list_items", "title": _("Anime"), "url": self.getFullUrl("/category.php?cat=anime")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("animezid")
        self.wfInitFolderCache()
        self.sessionCache = {}

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

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
        if url.startswith("//"):
            url = "https:" + url
        elif not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        # favourites / lists from animezid.net -> the current domain
        url = re.sub(r"^https?://(?:www\.)?animezid\.[a-z]+/", self.MAIN_URL, url)
        return self._quote(url)

    def _path(self, url):
        # domain independent identity of a page
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("az_video", "az_series", "az_season"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

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

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"az_video": "video", "az_series": "series", "az_season": "season"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _pager(self, data, page):
        # (url template with {page}, last page) from the numbered links of the site's pager
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination', "</ul>", False)[1]
        pageTpl = ""
        for href, num in re.findall(r"""href=['"]([^'"#]+)['"][^>]*>\s*(\d+)\s*<""", pager):
            tpl = re.sub(r"([?&](?:series_)?page=)%s(?=\D|$)" % num, r"\g<1>{page}", self._canonUrl(href), count=1)
            if "{page}" in tpl:
                pageTpl = tpl
                break
        lastPage = max([int(n) for n in re.findall(r">\s*(\d+)\s*</a>", pager)] + [page])
        return pageTpl, lastPage

    def _card(self, item):
        # (url, raw title, icon, desc) of one az-card
        href = self.cm.ph.getSearchGroups(item, r'class="az-card__link" href="([^"]+)"')[0]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<strong class="az-card__title">(.*?)</strong>')[0])
        icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
        # year / duration / seasons / episodes behind their icons, then the quality, dub and rating badges
        fields = [self.cleanHtmlStr(x) for x in re.findall(r"</svg>([^<]*)</span>", item)]
        fields += [self.cm.ph.getSearchGroups(item, pattern)[0].strip() for pattern in
                   (r'az-badge--quality">([^<]*)<', r'az-badge--ribbon"><span>([^<]*)<', r'az-badge--rating"><span[^>]*>[^<]*</span>\s*([\d.]+)')]
        return self._canonUrl(href), title, self.getFullIconUrl(self._quote(icon)) if icon else "", " | ".join(x for x in fields if x)

    def _listSubSections(self, data):
        # sub-sections of films / series ("ديزني بالمصري", "أفلام انيميشن مدبلجة" ...)
        grid = self.cm.ph.getDataBeetwenMarkers(data, 'class="az-category-grid"', "</section>", False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(grid, '<article class="az-category-card">', "</article>", False):
            href = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0]
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<strong>", "</strong>", False)[1])
            if href and label:
                self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "url": self._canonUrl(href),
                             "title": label, "icon": self.DEFAULT_ICON_URL})

    def _addCard(self, url, rawTitle, icon, desc):
        name, year, season, episode = _cleanName(rawTitle)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc, "meta_title": name, "meta_year": year}
        urlSeason = SEASON_URL_RE.search(url)
        if "/series/" in url:
            params.update({"category": "az_season" if urlSeason else "az_series", "title": name if IsMediaNamingNormalized() else rawTitle,
                           "s_title": name, "s_season": int(urlSeason.group(1)) if urlSeason else season or 1, "meta_type": "tv"})
            self.addDir(params)
        elif episode:
            params.update({"category": "az_video", "title": self._episodeTitle(name, season, episode, rawTitle), "s_title": name,
                           "s_season": season or 1, "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)
        else:
            params.update({"category": "az_video", "title": self._movieTitle(name, year, rawTitle), "meta_type": "movie"})
            self.addVideo(params)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem.get("url", ""))
        pageTpl = cItem.get("page_tpl", "")
        url = baseUrl if page <= 1 or not pageTpl else pageTpl.format(page=page)
        printDBG("AnimeZid.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        if page <= 1:
            self._listSubSections(data)
        seen = set()
        for item in CARD_RE.findall(data):
            card = self._card(item)
            if card[0] and card[1] and card[0] not in seen:
                seen.add(card[0])
                self._addCard(*card)

        pageTpl2, lastPage = self._pager(data, page)
        pageTpl = pageTpl or pageTpl2
        hasNext = bool(seen) and bool(pageTpl) and lastPage > page
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "page_tpl": pageTpl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def listSeries(self, cItem):
        # one season -> its episodes, more seasons -> season folders
        printDBG("AnimeZid.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        grid = self.cm.ph.getDataBeetwenMarkers(data, 'class="az-series-seasons-grid"', "</section>", False)[1]
        seasons = []
        for item in CARD_RE.findall(grid):
            url, label, icon, _desc = self._card(item)
            season = SEASON_URL_RE.search(url)
            if season and url not in [s[0] for s in seasons]:
                seasons.append((url, int(season.group(1)), label, icon))
        show = cItem.get("s_title", "") or cItem.get("title", "")
        if len(seasons) <= 1:
            season = seasons[0] if seasons else (self._canonUrl(cItem["url"]).split("?")[0].rstrip("/") + "/season/1/", 1)
            params = dict(cItem)
            params.update({"url": season[0], "s_season": season[1], "series_url": cItem["url"]})
            self.listEpisodes(params)
            return
        for url, num, label, icon in seasons:
            title = "%s - %s" % (show, formatSxxExx(num)) if IsMediaNamingNormalized() else "%s - %s" % (label, _("Season %d") % num)
            self.addDir({"name": "category", "good_for_fav": True, "category": "az_season", "url": url, "title": title,
                         "icon": icon or cItem.get("icon", ""), "desc": cItem.get("desc", ""), "series_url": cItem["url"],
                         "s_title": show, "s_season": num, "meta_type": "tv", "meta_title": cItem.get("meta_title", show),
                         "meta_year": cItem.get("meta_year", "")})

    def listEpisodes(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = self._canonUrl(cItem["url"]).split("?")[0]
        url = baseUrl if page <= 1 else "%s?page=%d" % (baseUrl, page)
        printDBG("AnimeZid.listEpisodes [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        seen = set()
        for num, item in re.findall(r'(?s)data-episode-number="(\d+)"[^>]*>(.*?)</article>', data):
            href, label, icon, desc = self._card(item)
            if not href or href in seen:
                continue
            seen.add(href)
            self.addVideo({"name": "category", "good_for_fav": True, "category": "az_video", "url": href,
                           "icon": icon or cItem.get("icon", ""), "title": self._episodeTitle(show, season, num, label),
                           "desc": desc or cItem.get("desc", ""), "series_url": cItem.get("series_url", cItem["url"]),
                           "s_title": show, "s_season": season, "s_episode": str(int(num)), "meta_type": "tv",
                           "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        _tpl, lastPage = self._pager(data, page)
        listItem = dict(cItem)
        listItem.update({"category": "az_season", "url": baseUrl})
        addPagingItems(self, listItem, page, bool(seen) and lastPage > page, lastPage, baseUrl + "?page={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AnimeZid.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/search.php?keywords=%s" % urllib_quote_plus(searchPattern.strip()))
        cItem.update({"category": "list_items", "page": 1, "url": base, "base_url": base})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _apiParams(self, referer, csrf):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=referer, Origin=self.MAIN_URL.rstrip("/"))
        params["header"].update({"Accept": "application/json", "Content-Type": "application/json", "X-Playback-CSRF": csrf})
        # the API answers 201 Created
        params.update({"raw_post_data": True, "ignore_http_code_ranges": [(201, 201)]})
        return params

    def _playbackSession(self, playUrl):
        # play page (csrf + session cookie) -> new playback session; {} when the site refuses.
        # The play page goes through the same HTTP backend as the API calls: getPageCFProtection uses urllib,
        # which saves the PHPSESSID session cookie with an empty expiry field, and PyCurl drops such a line
        # from the cookie file -> the session request went out without PHPSESSID and got 403 "forbidden"
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=playUrl)
        sts, data = self.cm.getPage(self._canonUrl(playUrl), params)
        if not sts:
            return {}
        createUrl = self.cm.ph.getSearchGroups(data, r'data-playback-create-url="([^"]+)"')[0]
        csrf = self.cm.ph.getSearchGroups(data, r'data-playback-csrf="([^"]+)"')[0]
        contentId = self.cm.ph.getSearchGroups(data, r'data-video-uniq="([^"]+)"')[0] or self.cm.ph.getSearchGroups(playUrl, r"vid=([^&#]+)")[0]
        if not (createUrl and csrf and contentId):
            return {}
        createUrl = self._canonUrl(createUrl)
        sts, data = self.cm.getPage(createUrl, self._apiParams(playUrl, csrf), json_dumps({"content_id": contentId}))
        try:
            session = json_loads(data) if sts else {}
        except Exception:
            printExc()
            session = {}
        if not session.get("session_id"):
            return {}
        session.update({"create_url": createUrl, "csrf": csrf})
        self.sessionCache[playUrl] = session
        return session

    @staticmethod
    def _sourceKey(source):
        return "%s:%s:%s" % (source.get("type", ""), source.get("provider", ""), source.get("quality", ""))

    def getLinksForVideo(self, cItem):
        printDBG("AnimeZid.getLinksForVideo [%s]" % cItem.get("url", ""))
        playUrl = self._canonUrl(cItem.get("url", "")).replace("/watch.php?", "/play.php?")
        session = self._playbackSession(playUrl)
        urltab = []
        seen = set()
        for source in session.get("sources", []) or []:
            key = self._sourceKey(source)
            provider = source.get("provider", "")
            if key in seen or not provider or UNSUPPORTED_RE.search(provider):
                continue
            seen.add(key)
            label = provider
            if source.get("type") == "download":
                label = "%s (%s)" % (label, _("Download"))
            if source.get("quality"):
                label = "%s %sp" % (label, source["quality"])
            # the hoster url is only known after a resolve call (rate limited by the site) - see getVideoLinks
            urltab.append({"name": label, "url": "%s#source=%s" % (playUrl, urllib_quote(key)), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def _launch(self, session, playUrl, key):
        # session source -> resolve -> one-use launch url (valid for minutes) -> 302 to the hoster page;
        # -> (hoster url, True when the session has expired)
        source = [s for s in session.get("sources", []) or [] if self._sourceKey(s) == key]
        if not source:
            return "", False
        url = "%s/%s/sources/%s/resolve" % (session["create_url"], session["session_id"], source[0].get("id", ""))
        sts, data = self.cm.getPage(url, self._apiParams(playUrl, session["csrf"]), "{}")
        launch = ""
        try:
            launch = json_loads(data).get("launch_url", "") if sts else ""
        except Exception:
            printExc()
        if not launch:
            return "", self.cm.meta.get("status_code") in (404, 410)
        params = dict(self.defaultParams)
        params.update({"header": dict(self.HEADER, Referer=playUrl), "no_redirection": True})
        sts, _data = self.cm.getPage(self._canonUrl(launch), params)
        link = self.cm.meta.get("location", "") if sts else ""
        return ("https:" + link if link.startswith("//") else link), False

    def _resolveSource(self, playUrl, key):
        session = self.sessionCache.get(playUrl)
        link, expired = self._launch(session, playUrl, key) if session else ("", True)
        if not link and expired:
            # no session from getLinksForVideo (e.g. a link list from the cache) or it has expired
            link = self._launch(self._playbackSession(playUrl), playUrl, key)[0]
        return link

    def getVideoLinks(self, videoUrl):
        printDBG("AnimeZid.getVideoLinks [%s]" % videoUrl)
        playUrl, _sep, fragment = videoUrl.partition("#source=")
        link = self._resolveSource(playUrl, urllib_unquote(fragment)) if fragment else ""
        printDBG("AnimeZid.getVideoLinks hoster [%s]" % link)
        if not self.cm.isValidUrl(link):
            if self.cm.meta.get("status_code") == 429:
                # the site allows only a few server requests per minute
                SetIPTVPlayerLastHostError(_("Too many requests. Please try again later."))
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(link, {"Referer": self.MAIN_URL})), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        info = {}
        head = self.cm.ph.getDataBeetwenMarkers(data, 'class="az-cinema-meta', "</ul>", False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, 'class="az-series-detail-hero__stats"', "</div>", False)[1]
        # watch page: <small>السنة</small><a>2026</a>, series stats: <strong><bdi>2007</bdi></strong><small>السنة</small>
        rows = INFO_ROW_RE.findall(head) + [(k, v) for v, k in re.findall(r"(?s)<strong>(.*?)</strong>\s*<small>([^<]+)</small>", head)]
        for key, val in rows:
            key, val = INFO_KEYS.get(self.cleanHtmlStr(key), ""), self.cleanHtmlStr(val)
            if key and val:
                # quality: "WEB-DL" + resolution "FHD - 1080p"
                info[key] = "%s, %s" % (info[key], val) if key in info and val != info[key] else val
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="az-rich-text az-story-text"[^>]*>(.*?)</div>')[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="az-cinema-summary">(.*?)</p>')[0] or
                                      self.cm.ph.getSearchGroups(data, r'(?s)az-series-detail-hero__stats">.*?</div>\s*<p>(.*?)</p>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(self._quote(poster)) if poster else "", info

    def getArticleContent(self, cItem):
        printDBG("AnimeZid.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        url = cItem.get("url", "")
        if cItem.get("category") == "az_season":
            url = cItem.get("series_url") or re.sub(r"season/\d+/?$", "", url)
        sts, data = self.getPage(url)
        if sts:
            story, poster, info = self._siteInfo(data)
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                title = _metaTitle(cItem["meta_title"])
                meta = getMeta(cItem["meta_type"], title, cItem.get("meta_year") or info.get("year", ""), () if isLatinTitle(title) else LATIN_ONLY)
            except Exception:
                printExc()
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
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("AnimeZid.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "az_series":
            self.listSeries(self.currItem)
        elif category == "az_season":
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
        CHostBase.__init__(self, AnimeZid(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("animezid")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("az_video", "az_series", "az_season")
