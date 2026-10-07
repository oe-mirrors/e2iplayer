# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 framework / host standard:
#   - latest episodes, movies, series, Ramadan, anime, plays, wrestling, movie / series genres (the old
#     "&data=1" genre urls redirected to the unfiltered list) and search; First page / Jump / Next page
#     (the site pager shows no last page, the genre filter is kept on every page)
#   - movies, episodes, plays and wrestling shows are VIDEO rows on their page url; a series row is one
#     season page -> its episodes (more seasons -> season folders)
#   - links: the site's own player (/streem/watch/<kind>/<id> -> XOR/base64 page -> KEY -> the servers of
#     /streem/sources/...): the "online" servers become direct links (HLS / MP4) with the site Referer
#   - watched flag, downloaded flag, favourites (urls re-based on the current domain), name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the site's story/fields/poster
#   - trailer row and colour codes in titles removed
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, E2ColoR, StripColorCodes, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.shoffree_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.shoffree_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.shoffree_proxy))
    if config.plugins.iptvplayer.shoffree_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.shoffree_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://shoffree.cc/"


SR_ONLY_RE = re.compile(r"(?s)<span class=['\"]sr-only['\"]>.*?</span>")
YEAR_RE = re.compile(r"\(((?:19|20)\d{2})\)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مشاهدة وتحميل|مشاهدة|تحميل|مسلسل|فيلم|انمي|مترجمة|مترجم|مدبلجة|مدبلج)(?=\s|$)")
# the site player's servers - the player itself walks them one after the other until one is "online"
# or the API answers "Server not found" (10+ servers per title); a server that does not answer is skipped
LOCAL_PAGE_SIZE = 100
SEARCH_PAGE_SIZE = 40
MAX_SERVERS = 12
MAX_ONLINE = 3
SERVER_TIMEOUT = 15
SEASON_WORD_RE = re.compile(r"الموسم|الحلقة")
HREF_RE = re.compile(r'<a href="([^"]*)"')


def _cutAtSeason(text):
    # text before the first "الموسم ..." / "الحلقة ..." that has more text on its line (like the former
    # re.sub(r"(?:الموسم|الحلقة)\s*\S+.*$", "", text))
    pos = 0
    while True:
        match = SEASON_WORD_RE.search(text, pos)
        if not match:
            return text
        rest = text[match.end():].lstrip()
        if rest and "\n" not in (rest[:-1] if rest.endswith("\n") else rest):
            return text[:match.start()]
        pos = match.start() + 1


def _seasonLinks(data):
    # the ".../serie/..." hrefs of the <a href="..."> links
    links = []
    for href in HREF_RE.findall(data):
        pos = href.find("/serie/")
        if pos > -1 and pos + 7 < len(href):
            links.append(href)
    return links


class Shoffree(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "shoffree", "cookie": "shoffree.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/shoffree135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("shoffree")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.shoffree_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        if Shoffree.DOMAIN_CACHE:
            self.MAIN_URL = Shoffree.DOMAIN_CACHE
            return
        domains = [gettytul()]
        domain = config.plugins.iptvplayer.shoffree_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.getPage(domain)
            if sts and "shoffree" in data.lower():
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", domain))
                break
        else:
            self.MAIN_URL = domains[-1]
        Shoffree.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / old lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
        m = re.match(r"https?://[^/]+/(.*)$", url)
        url = (self.MAIN_URL + m.group(1)) if m else self.getFullUrl(url)
        # Arabic slugs (wrestling / plays) -> one percent-encoded form
        return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")

    @staticmethod
    def _path(url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", urllib_unquote(url or "")).rstrip("/").lower()

    def getFullIconUrl(self, url, currUrl=None):
        url = (url or "").strip()
        if url.startswith("data:"):
            return ""
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    @staticmethod
    def _kind(url):
        path = urllib_unquote(url or "")
        if "/serie/" in path:
            return "series"
        if re.search(r"/watch/[^/]+-episode-\d+", path):
            return "episode"
        if "/watch/theater/" in path or "/watch/wrestling/" in path:
            return "show"
        if "/movie/" in path:
            return "movie"
        return ""

    @staticmethod
    def _seasonEpisode(url):
        path = urllib_unquote(url or "")
        season = re.search(r"-s(\d+)-(?:19|20)\d{2}(?:-|$)", path)
        episode = re.search(r"-episode-(\d+)", path)
        return int(season.group(1)) if season else 1, episode.group(1) if episode else ""

    @staticmethod
    def _cleanTitle(text):
        text = JUNK_RE.sub(" ", YEAR_RE.sub(" ", text or ""))
        return re.sub(r"\s+", " ", _cutAtSeason(text)).strip(" -:|")

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("sf_video", "sf_series", "sf_season"):
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
            prefix = {"sf_video": "video", "sf_series": "series", "sf_season": "season"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        def item(title, path):
            return {"category": "list_items", "title": title, "url": self.getFullUrl(path), "good_for_fav": True}
        tab = [
            item(_("Latest episodes"), "/episodes"),
            item(_("Movies"), "/movies"),
            item(_("Series"), "/series"),
            item(_("Ramadan"), "/ramadan"),
            item(_("Anime"), "/anime"),
            item(_("Plays"), "/theater"),
            item(_("Wrestling"), "/wrestling"),
            {"category": "sf_genres", "title": "%s - %s" % (_("Movies"), _("Genres")), "url": self.getFullUrl("/movies")},
            {"category": "sf_genres", "title": "%s - %s" % (_("Series"), _("Genres")), "url": self.getFullUrl("/series")},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listGenres(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        box = self.cm.ph.getDataBeetwenMarkers(data, 'id="genreContainer"', "</div>", False)[1]
        base = self._rebase(cItem["url"]).split("?")[0]
        for genre, label in re.findall(r'<span data-genre="([^"]+)"[^>]*>([^<]+)<', box):
            url = "%s?genre=%s&sort_by=latest" % (base, genre)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": self.cleanHtmlStr(label), "url": url})

    def _addItem(self, href, rawTitle, showTitle, icon, extra, normalize):
        url = self._rebase(href)
        kind = self._kind(url)
        if not kind:
            return False
        year = self.cm.ph.getSearchGroups(rawTitle, YEAR_RE.pattern)[0]
        show = self._cleanTitle(showTitle or rawTitle) or rawTitle
        season, episode = self._seasonEpisode(url)
        fields = ((_("Year"), year, "cyan"), (_("Quality"), extra.get("quality", ""), "yellow"), (_("Rating"), extra.get("rating", ""), "green"))
        desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon), "desc": desc}
        if kind == "series":
            title = ("%s - %s" % (show, formatSxxExx(season))) if normalize else "%s - %s %d" % (show, _("Season"), season)
            params.update({"category": "sf_series", "title": title, "s_title": show, "s_season": season,
                           "meta_type": "tv", "meta_title": show, "meta_year": year})
            self.addDir(params)
        elif kind == "episode":
            title = ("%s - %s" % (show, formatSxxExx(season, episode))) if normalize else "%s - %s %d - %s %s" % (show, _("Season"), season, _("Episode"), episode)
            params.update({"category": "sf_video", "title": title, "s_title": show, "s_season": season, "s_episode": episode,
                           "meta_type": "tv", "meta_title": show, "meta_year": year})
            self.addVideo(params)
        elif kind == "movie":
            if not normalize:
                title = showTitle or rawTitle
            elif year:
                title = "%s (%s)" % (show, year)
            else:
                title = show
            params.update({"category": "sf_video", "title": title, "meta_type": "movie", "meta_title": show, "meta_year": year})
            self.addVideo(params)
        else:
            params.update({"category": "sf_video", "title": rawTitle})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._rebase(cItem["url"])
        path, query = (baseUrl.split("?", 1) + [""])[:2]
        pageTpl = path.rstrip("/") + "/page/{page}" + ("?" + query if query else "")
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("Shoffree.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        grid = self.cm.ph.getDataBeetwenMarkers(data, '<section class="video-grid', "</section>", False)[1]
        marker = '<div class="shoffree-item' if "shoffree-item" in grid else "<article"
        seen = set()
        for item in grid.split(marker)[1:]:
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            if not href or href in seen:
                continue
            seen.add(href)
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            showTitle = self.cleanHtmlStr(SR_ONLY_RE.sub("", self.cm.ph.getSearchGroups(item, r'(?s)<h2 class="video-title">(.*?)</h2>')[0]))
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            extra = {"quality": self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="badge-quality">([^<]*)<')[0]),
                     "rating": self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'fa-star"[^>]*></i>\s*([0-9.]+)')[0])}
            self._addItem(href, rawTitle or showTitle, showTitle, icon, extra, normalize)

        # the pager shows a window of pages and "التالي" (next) - no last page
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination-container"', "</div>", False)[1]
        nums = [int(n) for n in re.findall(r"/page/(\d+)", pager)]
        hasNext = bool(seen) and bool(nums) and max(nums) > page
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, 0, pageTpl)

    def listSeries(self, cItem):
        # a series row is one season page: more seasons -> season folders, else its episodes
        printDBG("Shoffree.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        box = self.cm.ph.getDataBeetwenMarkers(data, 'id="seasons-area"', 'id="related-area"', False)[1]
        seasons = []
        for href in _seasonLinks(box):
            url = self._rebase(href)
            if url not in [s[1] for s in seasons]:
                seasons.append((self._seasonEpisode(url)[0], url))
        if len(seasons) <= 1:
            self.listEpisodes(cItem, data)
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "")
        for num, url in sorted(seasons):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "sf_season", "url": url, "s_season": num,
                           "title": ("%s - %s" % (show, formatSxxExx(num))) if normalize else "%s - %s %d" % (show, _("Season"), num)})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("Shoffree.listEpisodes [%s]" % cItem.get("url", ""))
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="episodes-area"', 'id="seasons-area"', False)[1]
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 0) or self._seasonEpisode(cItem.get("url", ""))[0]
        episodes = []
        for item in block.split('<div class="shoffree-item')[1:]:
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            if not href:
                continue
            url = self._rebase(href)
            episode = self.cm.ph.getSearchGroups(item, r'data-num="(\d+)"')[0] or self._seasonEpisode(url)[1]
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            if normalize and episode:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = label or "%s - %s %s" % (show, _("Episode"), episode)
            episodes.append((int(episode) if episode.isdigit() else 0, {
                "name": "category", "good_for_fav": True, "category": "sf_video", "title": title, "url": url,
                "icon": self.getFullIconUrl(icon) or cItem.get("icon", ""), "desc": cItem.get("desc", ""),
                "s_title": show, "s_season": season, "s_episode": episode,
                "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")}))
        episodes.sort(key=lambda e: e[0])
        # add 071026: long anime seasons -> local paging
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for _num, params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        # fix 071026: the site pages the search with &page=N (40 results, the "show more" button) - the pager has
        # no last page, a full page means there may be more
        page = cItem.get("page", 1)
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        pageTpl = self.getFullUrl("/search?query=%s&page={page}" % urllib_quote_plus(pattern))
        printDBG("Shoffree.listSearchResult [%s] page %d" % (pattern, page))
        sts, data = self.getPage(pageTpl.format(page=page))
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        count = 0
        for item in data.split("<a ")[1:]:
            if "shoffree-row" not in item.split(">", 1)[0]:
                continue
            count += 1
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            showTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3 class="shoffree-title">(.*?)</h3>')[0])
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            extra = {"rating": self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'fa-star"[^>]*></i>\s*([0-9.]+)')[0])}
            self._addItem(href, rawTitle or showTitle, showTitle, icon, extra, normalize)
        listItem = dict(cItem, category="search_next_page", s_pattern=pattern)
        addPagingItems(self, listItem, page, count >= SEARCH_PAGE_SIZE, 0, pageTpl)

    ###################################################
    # links
    ###################################################
    def _playerUrl(self, cItem, data):
        # /streem/watch/<kind>/<id(s)> of the item's player
        url = self._rebase(cItem.get("url", ""))
        kind = self._kind(url)
        if kind == "episode":
            path = self.cm.ph.getSearchGroups(data, r"(/streem/watch/serie/\d+/\d+)")[0]
        elif kind == "show":
            ident = self.cm.ph.getSearchGroups(url, r"/watch/(?:theater|wrestling)/(\d+)/")[0]
            path = "/streem/watch/wrestling/%s" % ident if ident else ""
        else:
            ident = self.cm.ph.getSearchGroups(data, r"""data-id=['"](\d+)['"]""")[0] or self.cm.ph.getSearchGroups(data, r"""name="key_token" value="(\d+)\"""")[0]
            path = "/streem/watch/movie/%s" % ident if ident else ""
        return self.getFullUrl(path) if path else ""

    @staticmethod
    def _decodePayload(key, payload):
        # hex pairs XOR key -> base64 -> url-encoded html
        try:
            chars = [chr(int(payload[i:i + 2], 16) ^ ord(key[(i // 2) % len(key)])) for i in range(0, len(payload) - 1, 2)]
            return urllib_unquote(ensure_str(b64Decode("".join(chars))))
        except Exception:
            printExc()
        return ""

    def getLinksForVideo(self, cItem):
        printDBG("Shoffree.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        playerUrl = self._playerUrl(cItem, data)
        if not playerUrl:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self._rebase(cItem["url"]))
        sts, data = self.getPage(playerUrl, params)
        if not sts:
            return []
        key, payload = self.cm.ph.getSearchGroups(data, r"""\}\)\(['"]([^'"]+)['"],\s*['"]([^'"]+)['"]\);""", 2)
        apiKey = self.cm.ph.getSearchGroups(self._decodePayload(key, payload), r"""const\s*KEY\s*=\s*['"]([^'"]+)['"]""")[0] if key else ""
        urltab = []
        if apiKey:
            apiUrl = playerUrl.replace("/streem/watch/", "/streem/sources/")
            params["header"] = dict(self.HEADER, Referer=playerUrl, Accept="application/json, text/javascript, */*; q=0.01")
            params["header"]["X-Requested-With"] = "XMLHttpRequest"
            # plain requests: a server that times out or answers 5xx is skipped like the site player does,
            # it must not start the Cloudflare/MyE2i check of getPageCFProtection
            params["timeout"] = SERVER_TIMEOUT
            # fix 071026: the same urllib path as the player page (cm.getPage leaves out pycurl for CFProtection):
            # the key belongs to its PHPSESSID, and pycurl did not send the session cookie urllib had saved -
            # every server answered "Session expired" (63 bytes gzip, box log 07.10. #4)
            params["CFProtection"] = True
            proxy = self.getProxy()
            if proxy:
                params["http_proxy"] = proxy
            online = misses = 0
            for server in range(1, MAX_SERVERS + 1):
                sts, data = self.cm.getPage(apiUrl, params, {"key": apiKey, "server": str(server)})
                if not sts:
                    printDBG("Shoffree.getLinksForVideo server %d: no answer" % server)
                    misses += 1
                    if misses >= 2:
                        break  # the API itself is down, not one server
                    continue
                misses = 0
                try:
                    ret = json_loads(data)
                except Exception:
                    printDBG("Shoffree.getLinksForVideo server %d: no JSON answer" % server)
                    continue  # this server failed (HTTP 500 page), the next one may work
                if ret.get("status") == "error":
                    break  # no more servers
                if ret.get("server_status") != "online":
                    continue
                found = False
                sources = ret.get("sources") or []
                # fix 071026: a server whose list holds page junk (favicon webmanifest as "video/mp4") was scraped
                # from a file host's download page - its other entries are that page and ad redirects (bowfile.com,
                # sc4jwe.org; exteplayer3 "Input/output error", box log 07.10. #5): the whole server is left out
                if any(re.search(r"\.(?:webmanifest|json|ico|png)(?:\?|$)", (src.get("file") or "").strip()) for src in sources):
                    printDBG("Shoffree.getLinksForVideo server %d: scraped page junk, skipped" % server)
                    continue
                for src in sources:
                    url = (src.get("file") or "").strip()
                    if not self.cm.isValidUrl(url):
                        continue
                    srcType = (src.get("type") or "").lower()
                    meta = {"Referer": self.getMainUrl(), "User-Agent": self.HEADER.get("User-Agent")}
                    if "mpegurl" in srcType or srcType == "hls":
                        meta["iptv_proto"] = "m3u8"
                    domain = self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]
                    name = "%s %d - %s (%s)" % (_("Server"), server, src.get("label") or ret.get("server") or "", domain)
                    urltab.append({"name": name, "url": strwithmeta(url, meta), "need_resolve": 0})
                    found = True
                online += 1 if found else 0
                if online >= MAX_ONLINE:
                    break
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        box = self.cm.ph.getDataBeetwenMarkers(data, 'class="cinema-sidebar"', 'class="cinema-actions"', False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r'(?s)id="storyText"[^>]*>(.*?)</p>')[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]+)"')[0])
        info = {}
        for key, word in (("country", "الدولة"), ("language", "اللغة")):
            val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r'(?s)<span class="stat-label">%s</span>\s*<span class="stat-value">(.*?)</span>' % word)[0])
            if val:
                info[key] = val
        rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r'(?s)poster-rating-row">\s*<i[^>]*></i>\s*<span>(.*?)</span>')[0])
        if rating and rating != "0.0":
            info["rating"] = rating
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r'(?s)fa-clock"></i>(.*?)</span>')[0])
        if duration:
            info["duration"] = duration
        genres = [self.cleanHtmlStr(g) for g in re.findall(r'(?s)<div>(.*?)</div>', self.cm.ph.getSearchGroups(box, r'(?s)genres_type">(.*?)</span>')[0])]
        if genres:
            info["genres"] = ", ".join(g for g in genres if g)
        poster = self.cm.ph.getSearchGroups(box, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getArticleContent(self, cItem):
        printDBG("Shoffree.getArticleContent [%s]" % cItem.get("url", ""))
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
        printDBG("Shoffree.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "sf_genres":
            self.listGenres(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "sf_series":
            self.listSeries(self.currItem)
        elif category == "sf_season":
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
        CHostBase.__init__(self, Shoffree(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("shoffree")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("sf_video", "sf_series", "sf_season")
