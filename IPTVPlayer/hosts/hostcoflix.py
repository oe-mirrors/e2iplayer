# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# ADD: 20.04.2026 - Mr.X
# 09.10.2026 - host standard, coflix.wales -> coflix.esq (redirect chain coflix.wales -> .click -> .date -> .esq):
#   - the apiflix JSON API answers HTTP 500 - films / series / animes / dramas / genres / search are read from the
#     site's pages now (md-manga cards, First / Jump / Next page with the last page from the pager)
#   - seasons + episodes from the panels of the series page (all seasons inline); episodes keep their own page
#     url (watched key + downloaded marker), seasons the series url + "#s<season>"; an "anime" that is a film
#     plays directly
#   - links: the page's cfServers list; lecteurvideo.com gets the page's player token and lists its hosters
#     (base64 showVideo entries, language + server label); trakx.lol / kokoflix.lol redirects are followed (voe
#     mirrors -> voe.sx); emmmmbed.com (Turnstile check) and the dead kakaflix.lol are left out
#   - watched flag (series -> season -> episode), favourites reopen without state (also the old rows: other coflix
#     domains, the API season rows via ?p=<post id>), "Title (Year)" / "Show - SxxExx" names, sidecar on the
#     links, INFO via moviemeta merged with the site's fields (synopsis, genres, rating, year, version)
#   - English menu labels (the season label was a hard-coded "Staffel"), default user agent, Cloudflare:
#     getPageCFProtection with the remembered UA
# 10.10.2026 - the year of a film / series page is read again (INFO, "Title (Year)" of animes that are films);
#   episodes show their own title + the series synopsis instead of the season's "Episodes: n" line
import base64
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
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
    return "https://coflix.esq/"


# the site moves its domain often (coflix.wales / .click / .date / .esq): urls of older favourites
OLD_DOMAIN_RE = re.compile(r"^https?://(?:www\.)?coflix\.[a-z]+/")
# season rows of the old API version: wp-json/apiflix/v1/series/<post id>/<season>
OLD_SEASON_RE = re.compile(r"apiflix/v1/series/(\d+)/(\d+)")
# emmmmbed.com: player with a Cloudflare Turnstile check - no resolver can get past it
# kakaflix.lol: its newPlayer.php redirects fail (TLS handshake dropped, also for xalaflix)
SKIP_HOSTERS = ("emmmmbed.com", "kakaflix.lol")
# hoster links that only redirect (302) to a mirror domain of the hoster:
# trakx.lol/<hoster>/newPlayer.php, kokoflix.lol/<name>_go.php (tokyo = dood, osaka = voe, grandline = filemoon)
REDIRECTORS = ("trakx.", "kokoflix.")


class Coflix(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Coflix", "cookie": "Coflix.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("wp-content/uploads/2022/10/cropped-coflix-180x180-1.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("films/")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("series/")},
                     {"category": "list_items", "title": _("Anime"), "url": self.getFullUrl("animes/")},
                     {"category": "list_items", "title": _("Dramas (Asian)"), "url": self.getFullUrl("drames/")},
                     {"category": "list_genres", "title": _("Genres")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("coflix")
        self.wfInitFolderCache()

    def _fixUrl(self, url):
        url = str(url or "")
        m = OLD_SEASON_RE.search(url)
        if m:
            return "%s?p=%s#s%s" % (self.MAIN_URL, m.group(1), m.group(2))
        return OLD_DOMAIN_RE.sub(self.MAIN_URL, url)

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._fixUrl(baseUrl).split("#", 1)[0], addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = re.sub(r"^https?://[^/]+", "", self._fixUrl(str(cItem.get("url", "") or "").strip()))
            if cItem.get("type", "") == "video":
                prefix = "video"
            else:
                prefix = {"list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _pageUrlTpl(url):
        # https://coflix.esq/films/page/{page}/ , https://coflix.esq/genres/page/{page}/?genre=action , .../page/{page}/?s=..
        base, query = (url.split("?", 1) + [""])[:2]
        base = re.sub(r"/page/\d+/?$", "/", base).rstrip("/").replace("{", "{{").replace("}", "}}")
        query = query.replace("{", "{{").replace("}", "}}")
        return base + "/page/{page}/" + ("?" + query if query else "")

    def _title(self, data):
        return self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1 class="cf-movie-title">([^<]+)<')[0])

    def _siteInfo(self, data):
        # the fields of a film / series / episode page: (info dict, synopsis, year)
        info = {}
        genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'class="cf-genre-tag">([^<]+)<', data))
        if genres:
            info["genres"] = genres
        rating = self.cm.ph.getSearchGroups(data, r'class="cf-stat-primary">\s*([0-9.]+)\s*<')[0]
        if rating and rating not in ("0", "0.0"):
            info["rating"] = rating
        # <span class="cf-stat-item" title="Année"><svg ...>...</svg> 2019 </span>
        year = self.cm.ph.getSearchGroups(data, r'(?s)title="Ann[^"]*">\s*(?:<svg.*?</svg>)?\s*((?:19|20)\d\d)\s*<')[0]
        if year:
            info["year"] = year
        version = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'class="cf-movie-quality-badge">([^<]+)<')[0])
        if version:
            info["translation"] = version
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)id="cfSynopsis">(.*?)</div>')[0])
        return info, plot, year

    def _seasons(self, data):
        # [(season, [(episode, url, title, icon), ...]), ...] from the season tabs + episode panels
        labels = {}
        for idx, label in re.findall(r'(?s)data-season="(\d+)"[^>]*>\s*([^<]+?)\s*<span', data):
            labels[idx] = self.cm.ph.getSearchGroups(label, r"(\d+)")[0] or str(int(idx) + 1)
        seasons = []
        for panel in data.split('class="cf-episodes-panel')[1:]:
            idx = self.cm.ph.getSearchGroups(panel, r'^[^>]*data-panel="(\d+)"')[0]
            if not idx:
                continue
            panel = panel.split('class="cf-episodes-panel', 1)[0]
            episodes = []
            for item in panel.split('class="cf-episode-item"')[1:]:
                url = self.cm.ph.getSearchGroups(item, r"location\.href='([^']+)'")[0]
                if not url:
                    continue
                num = self.cm.ph.getSearchGroups(item, r'cf-episode-num-badge">\s*(\d+)')[0] or self.cm.ph.getSearchGroups(url, r"-\d+x0*(\d+)")[0]
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="cf-episode-title">([^<]*)<')[0])
                icon = self.cm.ph.getSearchGroups(item, r'<img src="([^"]+)"')[0]
                episodes.append((num, url, title, icon))
            if episodes:
                seasons.append((labels.get(idx, str(int(idx) + 1)), episodes))
        return seasons

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("Coflix.listItems |%s|" % cItem)
        url = cItem.get("url", "")
        if not url:
            # list rows of the old API version (favourites): post type in "typ"
            url = self.getFullUrl("series/" if cItem.get("typ") == "series" else "films/")
        url = self._fixUrl(url)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        pageUrlTpl = self._pageUrlTpl(url)
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for block in data.split('<div class="md-manga-card ')[1:]:
            itemUrl = self.cm.ph.getSearchGroups(block, r'href="(https?://[^"]+/(?:film|serie|anime|drames)/[^"]+)"')[0]
            if not itemUrl or itemUrl in seen:
                continue
            seen.add(itemUrl)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'class="md-manga-card-name">([^<]+)<')[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0])
            icon = self.cm.ph.getSearchGroups(block, r'<img src="([^"]+)"')[0]
            year = self.cm.ph.getSearchGroups(block, r'class="md-card-badge year">\s*(\d{4})')[0]
            version = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'class="md-card-badge quality">([^<]+)<')[0])
            rating = self.cm.ph.getSearchGroups(block, r'md-card-overlay-rating[^>]*>(?:\s*<[^>]+>)*\s*([0-9.]+)')[0]
            synopsis = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'class="md-card-overlay-synopsis">([^<]+)<')[0])
            desc = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Rating"), rating), (_("Version"), version)) if value)
            params = stripPagerKeys(dict(cItem), ("typ", "id"))
            params.update({"good_for_fav": True, "url": itemUrl, "icon": self.getFullIconUrl(icon), "desc": "\n".join(x for x in (desc, synopsis) if x),
                           "s_title": title, "s_year": year})
            if "/film/" in itemUrl:
                params.update({"category": "video", "meta_type": "movie", "title": "%s (%s)" % (title, year) if (normalize and year) else title})
                self.addVideo(params)
            else:
                params.update({"category": "list_seasons", "meta_type": "tv", "title": title})
                self.addDir(params)
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="md-page-container"', "</nav>", False)[1] or data
        pages = [int(n) for n in re.findall(r'href="[^"]*/page/(\d+)/[^"]*"\s*class="md-page-btn', pager)]
        hasNext = "md-page-next" in pager
        addPagingItems(self, dict(cItem, url=url), page, hasNext, max(pages + [page]) if hasNext else page, pageUrlTpl)

    def listGenres(self, cItem):
        printDBG("Coflix.listGenres")
        sts, data = self.getPage(self.getFullUrl("genres/"))
        if not sts:
            return
        for url, title, count in re.findall(r'(?s)<a href="([^"]+\?genre=[^"]+)" class="cfg-genre-card">.*?cfg-genre-name">([^<]+)<.*?cfg-genre-count">([^<]*)<', data):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url), "desc": self.cleanHtmlStr(count)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("Coflix.listSeasons |%s|" % cItem)
        url = self._fixUrl(cItem["url"]).split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        _info, plot, year = self._siteInfo(data)
        sTitle = cItem.get("s_title", "") or self._title(data) or cItem["title"]
        seasons = self._seasons(data)
        if not seasons:
            if "var cfServers" in data:
                # an "anime" / "drama" that is a film
                params = stripPagerKeys(dict(cItem))
                params.update({"good_for_fav": True, "category": "video", "url": url, "meta_type": "movie", "desc": plot,
                               "title": "%s (%s)" % (sTitle, year) if (IsMediaNamingNormalized() and year) else sTitle})
                self.addVideo(params)
                return
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        fields = {"s_title": sTitle, "s_year": year or cItem.get("s_year", ""), "meta_type": "tv", "desc": plot, "s_plot": plot}
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category="list_episodes", season=seasons[0][0], url="%s#s%s" % (url, seasons[0][0]), **fields), seasons)
            return
        normalize = IsMediaNamingNormalized()
        for season, episodes in seasons:
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            params.update({"good_for_fav": True, "category": "list_episodes", "season": season, "url": "%s#s%s" % (url, season),
                           "title": "%s - %s" % (sTitle, formatSxxExx(season) if normalize else "%s %s" % (_("Season"), season)),
                           "desc": "%s: %d\n%s" % (_("Episodes"), len(episodes), plot)})
            self.addDir(params)

    def listEpisodes(self, cItem, seasons=None):
        printDBG("Coflix.listEpisodes |%s|" % cItem)
        url = self._fixUrl(cItem["url"])
        season = str(cItem.get("season", "") or "") or self.cm.ph.getSearchGroups(url, r"#s(\d+)$")[0]
        url = url.split("#", 1)[0]
        if seasons is None:
            sts, data = self.getPage(url)
            if not sts:
                return
            seasons = self._seasons(data)
            if not cItem.get("s_title"):
                # old season rows ("Show - Staffel 2") have no show name field
                cItem = dict(cItem, s_title=self._title(data))
            if "s_plot" not in cItem:
                cItem = dict(cItem, s_plot=self._siteInfo(data)[1])
        episodes = dict(seasons).get(season, [])
        if not episodes and len(seasons) == 1:
            # an old API season row whose number is not the label of the page's only season
            season, episodes = seasons[0]
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or cItem["title"]
        normalize = IsMediaNamingNormalized()
        for episode, epUrl, name, icon in episodes:
            if normalize and episode:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %s" % (sTitle, _("Season"), season, _("Episode"), episode or name)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": epUrl, "season": season, "episode": episode,
                           "meta_type": "tv", "icon": self.getFullIconUrl(icon) or cItem.get("icon", ""),
                           "desc": "\n".join(x for x in (name, cItem.get("s_plot", "")) if x)})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Coflix.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _addLink(self, urltab, url, label, referer):
        url = url.strip()
        if url.startswith("//"):
            url = "https:" + url
        if not self.cm.isValidUrl(url) or any(h in url for h in SKIP_HOSTERS) or url in [str(x["url"]) for x in urltab]:
            return
        name = self.up.getHostName(url).capitalize()
        meta = {"Referer": referer}
        if any(r in url for r in REDIRECTORS) and "voe" in label.lower():
            # the redirect goes to a random voe mirror domain that urlparser does not know
            meta["coflix_voe"] = "1"
        urltab.append({"name": "%s [%s]" % (name, label) if label else name, "url": strwithmeta(url, meta), "need_resolve": 1})

    def getLinksForVideo(self, cItem):
        printDBG("Coflix.getLinksForVideo [%s]" % cItem)
        url = self._fixUrl(cItem["url"])
        sts, data = self.getPage(url)
        if not sts:
            return []
        token = self.cm.ph.getSearchGroups(data, r'cfPlayerToken\s*=\s*"([^"]+)"')[0]
        try:
            servers = json.loads(self.cm.ph.getSearchGroups(data, r"var cfServers\s*=\s*(\[.*?\]);")[0] or "[]")
        except Exception:
            printExc()
            servers = []
        urltab = []
        for server in servers:
            if not isinstance(server, dict):
                continue
            embed = (server.get("embed_url") or "").strip()
            lang = self.cleanHtmlStr(server.get("idioma", "") or "")
            if "lecteurvideo.com" not in embed:
                self._addLink(urltab, embed, " | ".join(x for x in (lang, self.cleanHtmlStr(server.get("nombre", "") or "")) if x), self.MAIN_URL)
                continue
            # the coflix player: a list of hosters as base64 showVideo('..') entries, needs the page's token
            if token:
                embed += ("&" if "?" in embed else "?") + "t=" + urllib_quote_plus(token)
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=url)
            sts, player = self.cm.getPage(embed, params)
            if not sts:
                continue
            referer = self.up.getDomain(embed, False)
            for b64, label, info in re.findall(r"(?s)showVideo\('([^']+)'[^>]*>.*?<span>([^<]*)</span>\s*(?:<p>([^<]*)</p>)?", player):
                try:
                    link = base64.b64decode(b64).decode("latin1")
                except Exception:
                    printExc()
                    continue
                lang = self.cleanHtmlStr(info).split(" - ", 1)[0] if info else ""
                self._addLink(urltab, link, " | ".join(x for x in (lang, self.cleanHtmlStr(label).split(" / ", 1)[0]) if x), referer)
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self._siteInfo(data)[1]))

    def getVideoLinks(self, videoUrl):
        printDBG("Coflix.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if any(r in videoUrl for r in REDIRECTORS):
            # trakx / kokoflix only redirect to a mirror domain of the hoster (voe: random domains)
            meta = dict(strwithmeta(videoUrl).meta)
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=self.MAIN_URL)
            params["no_redirection"] = True
            sts, _data = self.cm.getPage(videoUrl, params)
            location = self.cm.meta.get("location", "") if sts else ""
            if not self.cm.isValidUrl(location):
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
                return []
            if ("/voe" in videoUrl or meta.pop("coflix_voe", "")) and self.up.checkHostSupport(location) != 1:
                location = re.sub(r"^https?://[^/]+/e/", "https://voe.sx/e/", location)
            videoUrl = strwithmeta(location, meta)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Coflix.getArticleContent [%s]" % cItem)
        info, plot, year = {}, "", cItem.get("s_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, siteYear = self._siteInfo(data)
            year = year or siteYear
        mediaType = cItem.get("meta_type", "") or ("movie" if "/film/" in cItem.get("url", "") else "tv")
        title = cItem.get("s_title", "") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(mediaType, title, year, maxYearDiff=1)
        except Exception:
            printExc()
        for key, value in meta.get("info", {}).items():
            info.setdefault(key, value)
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

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
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_value":
            # genre / year rows of the old API version (favourites) - the site has no id filter any more
            self.listGenres(self.currItem)
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
        CHostBase.__init__(self, Coflix(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("coflix")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
