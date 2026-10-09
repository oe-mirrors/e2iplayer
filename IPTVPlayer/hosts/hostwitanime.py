# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - witanime.site (Arabic-subtitled anime, Laravel / Livewire site): latest episodes, seasonal anime,
#     anime list and films (First page / Jump / Next page) and search
#   - anime -> episodes (ascending, local paging over 100); films and episodes are VIDEO rows keyed on
#     their page url
#   - links: the watch page's sources manifest (POST .../sources, X-CSRF-TOKEN); a server is only opened
#     when it is played (POST /watch/stream-source/<token>, then /watch/stream-gate/<token> redirects to the
#     hoster) - the site rate limits these calls hard (HTTP 429)
#   - watched flag (series:/video: keys), downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx", the season from "2nd Season" / "Season 2"), sidecar, INFO via moviemeta + the page's
#     story / info rows
# 09.10.2026 - server list fixed: the site answers 404 to the sources / stream-source / stream-gate calls of a
#   Chrome User-Agent without the matching "sec-ch-ua" client hint (bot check) - the requests send it now; the
#   gate is called like the page's player iframe; HTTP 429 shows "Too many requests" instead of "No stream";
#   watch servers only (the download servers are .zip archives or hosters without a resolver); the videas
#   server (app.videas.fr) is played from its HLS master
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
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
    return "https://witanime.site/"


LOCAL_PAGE_SIZE = 100
# "Black Clover 2nd Season" / "Aoashi Season 2" / "Tantei wa Mou, Shindeiru. Season2" -> season 2
SEASON_RE = re.compile(r"(?i)\s*\b(?:(\d+)(?:st|nd|rd|th)\s+season|season\s*(\d+))\b")
WATCH_RE = re.compile(r"/watch/(?!movie/)([^/\"']+)/(\d+)")
# "<span ...>الاستوديو</span><p ...>studio Pierrot</p>" rows of the page -> INFO keys
INFO_KEYS = (("production", "الاستوديو"), ("country", "البلد"), ("source", "المصدر"), ("episodes", "الحلقات"),
             ("year", "السنة"), ("broadcast", "الموسم"), ("duration", "المدة"), ("age_limit", "التصنيف العمري"))
# watch servers without a resolver in urlparser (mega.nz embed, 4shared, yonaplay = a second server picker
# behind its own API); the download servers are left out: mediafire hands out .zip archives, workupload / gofile
# have no resolver
UNSUPPORTED = ("mega", "4shared", "yonaplay")
# the "videas" server (app.videas.fr embed) is played by the host itself
VIDEAS_RE = re.compile(r"^https?://app\.videas\.fr/embed/")


def _clientHints(userAgent):
    # the site answers 404 to a Chrome User-Agent without the "sec-ch-ua" client hint every Chrome sends
    # (a bot check on the sources / stream-source / stream-gate calls); presence matters, not the version
    match = re.search(r"Chrome/(\d+)", userAgent or "")
    if not match or re.search(r"Edg/|OPR/", userAgent):
        return {}
    version = match.group(1)
    return {"sec-ch-ua": '"Chromium";v="%s", "Google Chrome";v="%s", "Not?A_Brand";v="99"' % (version, version),
            "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"'}


def _splitSeason(title):
    # -> (name without the season tag, season number or 0)
    match = SEASON_RE.search(title or "")
    if not match:
        return (title or "").strip(), 0
    name = (title[:match.start()] + title[match.end():]).strip(" -:")
    return (name or title.strip()), int(match.group(1) or match.group(2))


class WitAnime(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "series_url", "meta_type", "meta_title")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "witanime", "cookie": "witanime.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/witanime135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update(_clientHints(self.HEADER["User-Agent"]))
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "wa_latest", "title": _("Latest episodes"), "url": self.getMainUrl()},
            {"category": "list_items", "title": _("Airing now"), "url": self.getFullUrl("/seasonal")},
            {"category": "list_items", "title": _("Anime list"), "url": self.getFullUrl("/browse"), "page_tpl": self.getFullUrl("/browse/page/{page}")},
            {"category": "list_items", "title": _("Anime Movies"), "url": self.getFullUrl("/movies"), "page_tpl": self.getFullUrl("/movies/page/{page}")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("witanime")
        self.wfInitFolderCache()
        self.sourcesCache = {}

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        try:
            return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _path(self, url):
        # domain independent identity of a page
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("wa_video", "wa_series"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    @staticmethod
    def _episodeTitle(show, season, episode, label):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (show, formatSxxExx(season or 1, episode))
        return label

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"wa_video": "video", "wa_series": "series"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _cards(self, data):
        # [(url, title, icon, desc)] of the poster cards
        rows, seen = [], set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<a class="@container group', "</a>"):
            url = self._canonUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<h3", "</h3>")[1]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
            if not url or not title or url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]
            badges = [self.cleanHtmlStr(x) for x in re.findall(r"text-xs font-bold[^>]*>([^<]+)<", item)]
            rating = self.cm.ph.getSearchGroups(item, r"</svg>\s*([\d.]+)\s*</span>")[0]
            desc = " | ".join(x for x in badges + ([rating] if rating else []) if x)
            rows.append((url, title, self.getFullIconUrl(icon) if icon else "", desc))
        return rows

    def _addCard(self, url, title, icon, desc):
        name, season = _splitSeason(title)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc, "meta_title": name}
        watch = WATCH_RE.search(url)
        if "/anime/" in url:
            params.update({"category": "wa_series", "title": title, "s_title": name, "s_season": season or 1, "meta_type": "tv"})
            self.addDir(params)
        elif watch:
            episode = watch.group(2)
            params.update({"category": "wa_video", "title": self._episodeTitle(name, season, episode, "%s - %s" % (title, episode)),
                           "s_title": name, "s_season": season or 1, "s_episode": episode, "meta_type": "tv",
                           "series_url": self.getFullUrl("/anime/%s" % watch.group(1))})
            self.addVideo(params)
        elif "/movie/" in url:
            params.update({"category": "wa_video", "title": title, "meta_type": "movie"})
            self.addVideo(params)

    def listLatest(self, cItem):
        printDBG("WitAnime.listLatest")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, "أحدث الحلقات", "<h2", False)[1]
        for card in self._cards(block):
            self._addCard(*card)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem.get("url", ""))
        pageTpl = cItem.get("page_tpl", "")
        url = baseUrl if page <= 1 or not pageTpl else pageTpl.format(page=page)
        printDBG("WitAnime.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        main = self.cm.ph.getDataBeetwenMarkers(data, "<main", "</main>", False)[1] or data
        cards = self._cards(main)
        for card in cards:
            self._addCard(*card)
        if not pageTpl:
            return
        # pager: links ".../page/N" (films) or Livewire gotoPage(N) buttons (anime list)
        lastPage = max([int(n) for n in re.findall(r"(?:/page/|gotoPage\()(\d+)", data)] + [page])
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "page_tpl": pageTpl, "url": baseUrl})
        addPagingItems(self, listItem, page, bool(cards) and lastPage > page, lastPage, pageTpl)

    def listEpisodes(self, cItem):
        printDBG("WitAnime.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        slug = self.cm.ph.getSearchGroups(cItem["url"], r"/anime/([^/?#]+)")[0]
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        episodes = sorted(set(int(num) for name, num in WATCH_RE.findall(data) if name == slug))
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for num in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo({"name": "category", "good_for_fav": True, "category": "wa_video",
                           "url": self.getFullUrl("/watch/%s/%d" % (slug, num)), "icon": cItem.get("icon", ""),
                           "title": self._episodeTitle(show, season, num, "%s - %s %d" % (cItem.get("title", show), _("Episode"), num)),
                           "desc": cItem.get("desc", ""), "series_url": cItem["url"], "s_title": show, "s_season": season,
                           "s_episode": str(num), "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("WitAnime.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/search?q=%s" % urllib_quote_plus(searchPattern.strip()))
        cItem.update({"category": "list_items", "page": 1, "url": base, "base_url": base})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _watchUrl(self, url):
        url = self._canonUrl(url)
        return url.replace("/movie/", "/watch/movie/") if "/watch/" not in url else url

    def _header(self):
        # the User-Agent of the pages (the one that passed a browser check, if any) + its client hints
        header = dict(self.HEADER)
        userAgent = remembered_user_agent(self.COOKIE_FILE)
        if userAgent:
            header["User-Agent"] = userAgent
        header.update(_clientHints(header["User-Agent"]))
        return header

    def _apiParams(self, referer, csrf):
        params = dict(self.defaultParams)
        params["header"] = dict(self._header(), Referer=referer, Origin=self.MAIN_URL.rstrip("/"))
        params["header"].update({"Accept": "application/json", "Content-Type": "application/json", "X-CSRF-TOKEN": csrf})
        params.update({"raw_post_data": True, "ignore_http_code_ranges": []})
        return params

    def _noStream(self):
        # the watch pages and their source / gate calls are rate limited hard (HTTP 429 for some minutes)
        if self.cm.meta.get("status_code") == 429:
            SetIPTVPlayerLastHostError(_("Too many requests. Please try again later."))
        else:
            SetIPTVPlayerLastHostError(_("No stream available"))

    def _sources(self, watchUrl):
        # watch page (csrf + session cookie) -> sources manifest {key: (kind, token)}; cached per watch page
        sts, data = self.getPage(watchUrl)
        if not sts:
            return {}
        csrf = self.cm.ph.getSearchGroups(data, r'name="csrf-token" content="([^"]+)"')[0]
        sourcesUrl = self.cm.ph.getSearchGroups(data, r"sourcesUrl:\s*'([^']+)'")[0].replace("\\/", "/")
        if not csrf or not sourcesUrl:
            return {}
        sts, data = self.cm.getPage(self._canonUrl(sourcesUrl), self._apiParams(watchUrl, csrf), "{}")
        try:
            manifest = json_loads(data) if sts else {}
        except Exception:
            printExc()
            manifest = {}
        result = {"csrf": csrf, "links": []}
        for quality, items in (manifest.get("players") or {}).items():
            for item in items or []:
                label = item.get("label", "")
                key = "stream:%s:%s:%s:%s" % (label, quality, item.get("version", ""), item.get("lang", ""))
                if label and item.get("token") and key not in [k for k, _t, _i in result["links"]]:
                    result["links"].append((key, item["token"], item))
        if result["links"]:
            self.sourcesCache[watchUrl] = result
        return result

    def getLinksForVideo(self, cItem):
        printDBG("WitAnime.getLinksForVideo [%s]" % cItem.get("url", ""))
        watchUrl = self._watchUrl(cItem.get("url", ""))
        urltab = []
        for key, _token, item in self._sources(watchUrl).get("links", []):
            label, quality = key.split(":")[1:3]
            if label.lower() in UNSUPPORTED:
                continue
            name = "%s %s" % (label, quality)
            if item.get("version") == "dub":
                name += " (%s)" % _("Dubbed")
            urltab.append({"name": name, "url": "%s#source=%s" % (watchUrl, urllib_quote(key)), "need_resolve": 1})
        if not urltab:
            self._noStream()
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def _gate(self, watchUrl, key, sources):
        # POST /watch/<kind>-source/<token> opens the server, /watch/<kind>-gate/<token> redirects to the hoster;
        # -> (hoster url, True when the token has expired)
        token = [t for k, t, _i in sources.get("links", []) if k == key]
        if not token:
            return "", True
        kind = key.split(":")[0]
        sts, _data = self.cm.getPage(self.getFullUrl("/watch/%s-source/%s" % (kind, token[0])), self._apiParams(watchUrl, sources["csrf"]), "{}")
        if not sts:
            return "", self.cm.meta.get("status_code") in (404, 419)
        params = dict(self.defaultParams)
        # the page loads the gate as its player iframe
        header = dict(self._header(), Referer=self.MAIN_URL)
        header.update({"Sec-Fetch-Dest": "iframe", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "same-origin"})
        params.update({"header": header, "no_redirection": True})
        sts, _data = self.cm.getPage(self.getFullUrl("/watch/%s-gate/%s" % (kind, token[0])), params)
        return (self.cm.meta.get("location", "") if sts else ""), False

    def getVideoLinks(self, videoUrl):
        printDBG("WitAnime.getVideoLinks [%s]" % videoUrl)
        watchUrl, _sep, fragment = videoUrl.partition("#source=")
        key = urllib_unquote(fragment)
        link, expired = self._gate(watchUrl, key, self.sourcesCache.get(watchUrl, {})) if key else ("", False)
        if not link and expired:
            # no manifest from getLinksForVideo (e.g. a link list from the cache) or the session has expired
            link = self._gate(watchUrl, key, self._sources(watchUrl))[0]
        printDBG("WitAnime.getVideoLinks hoster [%s]" % link)
        if not self.cm.isValidUrl(link):
            self._noStream()
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if VIDEAS_RE.search(link):
            return decorateResolvedLinkItems(self._videas(link), sidecar)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(link, {"Referer": self.MAIN_URL})), sidecar)

    def _videas(self, embedUrl):
        # app.videas.fr embed (no resolver in urlparser): its page names the HLS master on cdn.videas.fr
        header = {"User-Agent": self.HEADER["User-Agent"], "Referer": self.MAIN_URL}
        sts, data = self.cm.getPage(embedUrl, {"header": header})
        playlist = self.cm.ph.getSearchGroups(data, r'(https://cdn\.videas\.fr/[^"\s]+?/playlist\.m3u8)')[0] if sts else ""
        if not playlist:
            return []
        meta = {"User-Agent": header["User-Agent"], "Referer": "https://app.videas.fr/", "Origin": "https://app.videas.fr"}
        return getDirectM3U8Playlist(strwithmeta(playlist, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        info = {}
        for key, word in INFO_KEYS:
            val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<span[^>]*>\s*%s\s*</span>\s*<p[^>]*>([^\n]+?)</p>" % word)[0])
            if val:
                info[key] = val
        head = self.cm.ph.getDataBeetwenMarkers(data, "<h1", 'max-md:order-2">', False)[1]
        badges = [self.cleanHtmlStr(x) for x in re.findall(r"<span[^>]*rounded-md[^>]*>([^<]+)</span>", head)]
        if badges:
            info["type"] = ", ".join(x for x in badges if x and not re.match(r"^[\d.]+$", x))
        rating = self.cm.ph.getSearchGroups(head, r">\s*(\d+\.\d+)\s*<")[0]
        if rating:
            info["rating"] = rating
        alt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<p class="mb-4 text-lg[^"]*">(.*?)</p>')[0])
        if alt:
            info["alternate_title"] = alt
        genres = self.cm.ph.getDataBeetwenMarkers(data, '<div class="mb-6 flex flex-wrap gap-2', "</div>", False)[1]
        genres = ", ".join(x for x in [self.cleanHtmlStr(g) for g in re.findall(r"<span[^>]*>([^<]+)</span>", genres)] if x)
        if genres:
            info["genres"] = genres
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<p class="mb-6 text-sm[^"]*">(.*?)</p>')[0])
        return story, info

    def getArticleContent(self, cItem):
        printDBG("WitAnime.getArticleContent [%s]" % cItem.get("url", ""))
        story, info = "", {}
        sts, data = self.getPage(cItem.get("series_url") or cItem.get("url", ""))
        if sts:
            story, info = self._siteInfo(data)
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], info.get("year", ""))
            except Exception:
                printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or cItem.get("icon", "")
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
        printDBG("WitAnime.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "wa_latest":
            self.listLatest(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "wa_series":
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
        CHostBase.__init__(self, WitAnime(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("witanime")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("wa_video", "wa_series")
