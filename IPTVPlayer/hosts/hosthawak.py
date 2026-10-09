# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Hawak (فيديو هواك, www.hawak.net): PHP Melody site (Laroza template) with Arabic, Indian, Turkish, Asian and
# foreign films, dubbed Indian/Turkish series, Arabic and Ramadan series, anime; the catalogue was last
# extended in December 2025
#   - "Latest", Movies / Series / Other (the site categories) and search, with First page / Jump / Next page
#     (n/last) from the site's pager
#   - the watch page has no episode list: an episode row of a list -> one series folder per show, filled
#     from the site search for the show name (all result pages, only the episodes of that show, sorted,
#     local paging above 100 episodes); films are VIDEO rows on their watch.php page url
#   - links: view.php?vid=<id> holds the player iframe - films: liiivideo; series: an AlbaPlayer page
#     (qvid.cc/albaplayer/<slug>/) whose "?serv=N" tabs (liiivideo, hdup, vudeo, uqload ...) are read when the
#     link list is built: one link per tab with its hoster in the name, its iframe or AlbaPlayerControl('<base64>')
#     source (hoster page, or the file itself when its server answers) handed to urlparser; tabs urlparser has
#     no parser for (vudeo.ws parked, uupbom.com seized) are left out
#   - watched flag (series -> episode), downloaded flag, favourites (urls re-based on the current domain),
#     name normalisation ("Title (Year)", "Show - SxxExx" from the Arabic labels), sidecar, INFO via moviemeta +
#     the site's description/genre/poster
#   - the site's "adults only" film category is left out
import re
from base64 import b64decode

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, E2ColoR, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.hawak_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.hawak_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.hawak_proxy))
    if config.plugins.iptvplayer.hawak_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.hawak_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://www.hawak.net/"


SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5),
    ("السادسة", 6), ("السادس", 6), ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8),
    ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d{2})(?=\s|\)|$)")
KIND_RE = re.compile(r"^\s*(?:مسلسل|برنامج|انمي|أنمي|كرتون)\s+")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجمه|مترجم|مدبلجة|مدبلجه|مدبلج|اون لاين|أون لاين|مشاهدة|فيلم|كامل|كاملة|بجودة عالية|HD|FHD|"
                     r"جميع الحلقات|كل الحلقات|حصريا|حصرياً|والأخيرة|والاخيرة|الاخيرة|الأخيرة)(?=\s|$)")
MENU_GROUPS = (("movies", ("افلام", "أفلام")), ("series", ("مسلسلات",)))
# left out: "أفلام للكبار فقط" (adults only)
SKIP_CATEGORIES = ("r-rated-movies",)
TAG_A_RE = re.compile(r"<a\s([^>]*)>([^<]*)</a>")
TAG_IFRAME_RE = re.compile(r"<iframe\s([^>]*)>")
HREF_RE = re.compile(r'href="([^"]*)"')
SRC_RE = re.compile(r"""src=["']([^"']+)["']""")
MEDIA_RE = re.compile(r"(?i)\.(?:mp4|m3u8|mkv)(?:[?#]|$)")
CAT_KEY = "category.php?cat="
EPISODES_PER_PAGE = 100
MAX_SEARCH_PAGES = 10
MAX_SEARCH_PASSES = 3
MAX_NEIGHBOUR_PAGES = 15


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


class Hawak(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year", "src_tpl", "src_page")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "hawak", "cookie": "hawak.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/hawak135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("hawak")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.hawak_proxy.value) or None

    def _params(self, addParams=None):
        params = dict(addParams if addParams is not None else self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in params:
            params = MergeDicts(params, {"http_proxy": proxy})
        return params

    def getPage(self, baseUrl, addParams=None, post_data=None):
        return self.cm.getPageCFProtection(self._rebase(baseUrl), self._params(addParams), post_data)

    def selectDomain(self):
        if Hawak.DOMAIN_CACHE:
            self.MAIN_URL = Hawak.DOMAIN_CACHE
            return
        domains = [gettytul()]
        domain = config.plugins.iptvplayer.hawak_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.cm.getPageCFProtection(domain, self._params())
            if sts and "MELODYURL" in data:
                self.MAIN_URL = self.cm.getBaseUrl(data.meta.get("url", domain))
                break
        else:
            self.MAIN_URL = domains[-1]
        Hawak.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / old lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
        m = re.match(r"https?://[^/]+/(.*)$", url)
        url = (self.MAIN_URL + m.group(1)) if m else self.getFullUrl(url)
        # Arabic search words in the pager links ("search.php?keywords=أنت محبوبي&page=2") -> percent-encoded
        return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    @staticmethod
    def _vid(url):
        m = re.search(r"[?&]vid=([^&#]+)", url or "")
        return m.group(1) if m else ""

    @staticmethod
    def _cleanSpaces(text):
        return re.sub(r"\s+", " ", text or "").strip(" -:|")

    def _splitTitle(self, title):
        # "مسلسل أنت محبوبي الحلقة 156 مدبلجة" -> show "أنت محبوبي", episode 156
        # "مشاهدة فيلم المهراجا 2018 HD" -> "المهراجا", year 2018
        episode = self.cm.ph.getSearchGroups(title, EPISODE_RE.pattern)[0]
        season = _seasonNum(title)
        show = title
        if episode:
            show = EPISODE_RE.split(show)[0]
        show = SEASON_RE.split(show)[0] if season else show
        show = JUNK_RE.sub(" ", show)
        show = KIND_RE.sub("", show)
        years = YEAR_RE.findall(show)
        year = years[-1] if years else ""
        if year and not episode:
            show = re.sub(r"\(?%s\)?" % year, " ", show)
        return self._cleanSpaces(show), season, episode, year

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("hw_video", "hw_series"):
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
            if category == "hw_video":
                vid = self._vid(cItem.get("url", ""))
                return "video:%s" % vid if vid else ""
            show = cItem.get("s_title", "").lower()
            if category == "hw_series" and show:
                return "series:%s|%s" % (show, cItem.get("s_season", 0))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("/newvideos.php"), "good_for_fav": True},
            {"category": "hw_menu", "title": _("Movies"), "group": "movies"},
            {"category": "hw_menu", "title": _("Series"), "group": "series"},
            {"category": "hw_menu", "title": _("Other"), "group": "other"},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listSiteMenu(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        group = cItem.get("group", "")
        seen = set()
        for attrs, label in TAG_A_RE.findall(data):
            href = self.cm.ph.getSearchGroups(attrs, HREF_RE.pattern)[0]
            title = self.cleanHtmlStr(label)
            if CAT_KEY not in href or "&" in href or not href.split(CAT_KEY, 1)[1] or not title:
                continue
            url = self._rebase(href)
            if url in seen or any(word in url for word in SKIP_CATEGORIES):
                continue
            itemGroup = "other"
            for name, words in MENU_GROUPS:
                if title.startswith(words):
                    itemGroup = name
            if itemGroup != group:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": url})

    def _gridRows(self, data):
        # [(raw title, page url, icon, duration)] of the pm-grid list
        rows = []
        grid = self.cm.ph.getDataBeetwenMarkers(data, 'id="pm-grid"', "</ul>", False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(grid, "<li", "</li>"):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]*watch\.php\?vid=[^"]+)"')[0]
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="caption">(.*?)</h3>')[0])
            if not rawTitle:
                rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not href or not rawTitle:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'data-echo="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="pm-label-duration">(.*?)</span>')[0])
            rows.append((rawTitle, self._rebase(href), self.getFullIconUrl(icon), duration))
        return rows

    def _pager(self, data, page):
        # (last page, url template) of the site's pager
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', "</ul>", False)[1]
        nums = [int(n) for n in re.findall(r"<a[^>]*>\s*(\d+)\s*</a>", pager)]
        pageTpl = ""
        for href in re.findall(r'<a[^>]+href="([^"#]+)"', pager):
            tpl = re.sub(r"([?&]page=)\d+", r"\1{page}", self._rebase(href), 1)
            if "{page}" in tpl:
                pageTpl = tpl
        return max(nums + [page]), pageTpl

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = self._rebase(cItem["url"])
        printDBG("Hawak.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        rows = self._gridRows(data)
        lastPage, pageTpl = self._pager(data, page)
        # where the folder's episodes are: this list page (and its neighbours, see _showEpisodes)
        source = {"src_tpl": pageTpl or url, "src_page": page if pageTpl else 0}
        for rawTitle, url, icon, duration in rows:
            show, season, episode, year = self._splitTitle(rawTitle)
            if episode or KIND_RE.match(rawTitle):
                key = (show.lower(), season)
                if not show or key in seen:
                    continue
                seen.add(key)
                title = show
                if season:
                    title = ("%s - %s" % (show, formatSxxExx(season))) if normalize else "%s - %s %d" % (show, _("Season"), season)
                params = {"name": "category", "category": "hw_series", "good_for_fav": True, "title": title, "url": url, "icon": icon,
                          "desc": "", "s_title": show, "s_season": season, "meta_type": "tv", "meta_title": show}
                params.update(source)
                self.addDir(params)
                continue
            if url in seen:
                continue
            seen.add(url)
            fields = ((_("Year"), year, "cyan"), (_("Duration"), duration, "green"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
            title = rawTitle
            if normalize and show:
                title = "%s (%s)" % (show, year) if year else show
            self.addVideo({"name": "category", "category": "hw_video", "good_for_fav": True, "title": title, "url": url, "icon": icon,
                           "desc": desc, "meta_type": "movie", "meta_title": show or rawTitle, "meta_year": year})
        hasNext = bool(rows) and lastPage > page and bool(pageTpl)
        listItem = dict(cItem)
        listItem.update({"category": "list_items"})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def _collect(self, url, show, season, episodes):
        # adds the show's episodes of one list page to episodes {number: (page url, icon, raw title)};
        # returns (episodes found on the page, the page's data or None)
        sts, data = self.getPage(url)
        if not sts:
            return 0, None
        found = 0
        for rawTitle, pageUrl, icon, _duration in self._gridRows(data):
            rowShow, rowSeason, episode, _year = self._splitTitle(rawTitle)
            if episode and rowShow.lower() == show and rowSeason == season:
                found += 1
                episodes.setdefault(int(episode), (pageUrl, icon, rawTitle))
        return found, data

    def _showEpisodes(self, cItem):
        # the watch page has no episode list. Category and "Latest" lists are sorted by upload date, so the
        # episodes of a show sit together: the list page the folder came from and its neighbours until a page
        # without them. The site search returns its hits in a varying order (pages overlap, some hits never
        # show up), so a folder from the search reads all result pages up to MAX_SEARCH_PASSES times.
        show = (cItem.get("s_title", "") or cItem.get("title", "")).lower()
        season = cItem.get("s_season", 0)
        episodes = {}
        tpl = cItem.get("src_tpl", "")
        start = cItem.get("src_page", 0)
        if tpl and "search.php" not in tpl:
            if not start:
                self._collect(tpl, show, season, episodes)
            else:
                startFound, data = self._collect(tpl.format(page=start), show, season, episodes)
                lastPage = self._pager(data, start)[0] if data else start
                for step in (1, -1):
                    found, page = startFound, start + step
                    while found and 1 <= page <= lastPage and abs(page - start) <= MAX_NEIGHBOUR_PAGES:
                        found = self._collect(tpl.format(page=page), show, season, episodes)[0]
                        page += step
            if episodes and min(episodes) == 1:
                return episodes
            # the list has moved on (an old favourite) or the first episodes sit in another category
            # (e.g. Ramadan series) - completed from the search below
        url = self.getFullUrl("/search.php?keywords=%s" % urllib_quote_plus(cItem.get("s_title", "")))
        for _pass in range(MAX_SEARCH_PASSES):
            before = len(episodes)
            pageUrl, page = url, 1
            while page <= MAX_SEARCH_PAGES:
                data = self._collect(pageUrl, show, season, episodes)[1]
                if data is None:
                    break
                lastPage, pageTpl = self._pager(data, page)
                if lastPage <= page or not pageTpl:
                    break
                page += 1
                pageUrl = pageTpl.format(page=page)
            if len(episodes) == before or page == 1:
                break
        return episodes

    def listEpisodes(self, cItem):
        printDBG("Hawak.listEpisodes [%s]" % cItem.get("s_title", ""))
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 0)
        episodes = self._showEpisodes(cItem)
        if not episodes:
            # the search does not find the show - the clicked episode itself
            params = dict(cItem)
            params.update({"category": "hw_video", "good_for_fav": True})
            self.addVideo(params)
            return
        normalize = IsMediaNamingNormalized()
        numbers = sorted(episodes)
        page = cItem.get("page", 1)
        lastPage = (len(numbers) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
        for num in numbers[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]:
            url, icon, rawTitle = episodes[num]
            title = "%s - %s" % (show, formatSxxExx(season or 1, num)) if normalize else rawTitle
            self.addVideo({"name": "category", "category": "hw_video", "good_for_fav": True, "title": title, "url": url,
                           "icon": icon or cItem.get("icon", ""), "desc": "", "s_title": show, "s_season": season or 1, "s_episode": num,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        addPagingItems(self, cItem, page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Hawak.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/search.php?keywords=%s" % urllib_quote_plus(searchPattern.strip())), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="VidDesc">(.*?)</div>')[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]+)"')[0])
        info = {}
        genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta itemprop="genre" content="([^"]+)"')[0])
        if genre:
            info["genre"] = genre
        duration = self.cm.ph.getSearchGroups(data, r'<meta itemprop="duration" content="PT(?:(\d+)H)?(?:(\d+)M)?', 2)
        if any(duration):
            info["duration"] = "%d:%02d" % (int(duration[0] or 0), int(duration[1] or 0))
        poster = self.cm.ph.getSearchGroups(data, r'<meta itemprop="thumbnailUrl" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("Hawak.getLinksForVideo [%s]" % cItem.get("url", ""))
        vid = self._vid(cItem.get("url", ""))
        if not vid:
            return []
        params = self._params()
        params["header"] = dict(self.HEADER, Referer=self._rebase(cItem["url"]))
        sts, data = self.getPage(self.getFullUrl("/view.php?vid=%s" % vid), params)
        if not sts:
            return []
        holder = self.cm.ph.getDataBeetwenMarkers(data, 'id="Playerholder"', "</div>", False)[1]
        if not holder:
            sts, holder = self.getPage(self.getFullUrl("/embed.php?vid=%s" % vid), params)
            if not sts:
                return []
        urltab = []
        for attrs in TAG_IFRAME_RE.findall(holder):
            url = self.cm.ph.getSearchGroups(attrs, SRC_RE.pattern)[0].replace("&amp;", "&").strip()
            url = "https:" + url if url.startswith("//") else url
            if not self.cm.isValidUrl(url):
                continue
            if "/albaplayer/" in url:
                urltab.extend(self._albaTabs(url))
                continue
            domain = self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]
            urltab.append({"name": domain, "url": strwithmeta(url, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def _albaSource(self, data):
        # the source of an AlbaPlayer page: its iframe, or AlbaPlayerControl('<base64 url>', ...) - a hoster page
        # (uupbom ...) or the file itself (vid1.s-amm-7.store/.../01.mp4)
        frame = self.cm.ph.getSearchGroups(data, r"""<iframe[^>]+src=["']([^"']+)["']""")[0]
        if not frame:
            encoded = self.cm.ph.getSearchGroups(data, r"""AlbaPlayerControl\(\s*['"]([A-Za-z0-9+/=_-]+)['"]""")[0]
            if encoded:
                try:
                    frame = b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8", "ignore")
                except Exception:
                    printExc()
        frame = frame.replace("&amp;", "&").strip()
        return "https:" + frame if frame.startswith("//") else frame

    def _albaLink(self, name, frame, referer):
        # -> link of one AlbaPlayer source, None when it can never play (hoster urlparser has no parser for:
        # vudeo.ws parked, uupbom.com seized ...; a file whose server does not answer)
        if not self.cm.isValidUrl(frame):
            return None
        if MEDIA_RE.search(frame):
            params = self._params({"header": {"User-Agent": self.HEADER.get("User-Agent"), "Referer": referer, "Range": "bytes=0-0"}, "max_data_size": 65536, "timeout": 10})
            sts, _data = self.cm.getPage(frame, params)
            if not sts or self.cm.meta.get("status_code") not in (200, 206):
                printDBG("Hawak._albaLink file does not answer [%s] %s" % (frame, self.cm.meta.get("status_code")))
                return None
            meta = {"Referer": referer, "User-Agent": self.HEADER.get("User-Agent")}
            if self.getProxy():
                meta["iptv_http_proxy"] = self.getProxy()
            return {"name": "%s (mp4)" % name, "url": strwithmeta(frame, meta), "need_resolve": 0}
        if self.up.checkHostSupport(frame) != 1:
            printDBG("Hawak._albaLink skip unsupported [%s]" % frame)
            return None
        domain = self.cm.ph.getSearchGroups(frame, r"https?://(?:www\.)?([^/:]+)")[0]
        return {"name": "%s (%s)" % (name, domain), "url": strwithmeta(frame, {"Referer": referer}), "need_resolve": 1}

    def _albaTabs(self, url):
        # AlbaPlayer server picker: every "?serv=N" tab is read here (a few small pages), so the list shows the
        # hoster of each tab and leaves out the ones that can never play
        pageUrl = url.split("?", 1)[0]
        referer = self.cm.getBaseUrl(pageUrl)
        params = self._params()
        params["header"] = dict(self.HEADER, Referer=self.getMainUrl())
        sts, data = self.cm.getPage(pageUrl, params)
        if not sts:
            return []
        tabs = []
        seen = set()
        for attrs, label in TAG_A_RE.findall(data):
            tab = self.cm.ph.getSearchGroups(attrs, HREF_RE.pattern)[0].replace("&amp;", "&")
            if "?serv=" not in tab or not self.cm.isValidUrl(tab) or tab in seen:
                continue
            seen.add(tab)
            sts, tabData = self.cm.getPage(tab, params)
            link = self._albaLink("%s %s" % (_("Server"), self.cleanHtmlStr(label) or len(seen)), self._albaSource(tabData) if sts else "", referer)
            if link:
                tabs.append(link)
        if not seen:
            # a player page with a single source
            link = self._albaLink(_("Server"), self._albaSource(data), referer)
            if link:
                tabs.append(link)
        return tabs

    def getVideoLinks(self, videoUrl):
        printDBG("Hawak.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Hawak.getArticleContent [%s]" % cItem.get("url", ""))
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
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Hawak.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "hw_menu":
            self.listSiteMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "hw_series":
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
        CHostBase.__init__(self, Hawak(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("hawak")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("hw_video", "hw_series")
