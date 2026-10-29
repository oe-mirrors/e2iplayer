# -*- coding: utf-8 -*-
LAST_MODIFIED = "29.10.2026"
# 29.10.2026 - rewritten for altadefinizionex.vip (alta-definizione.beer is gone; Next.js site, ~30000 movies and
#   ~6400 series in Italian):
#   - lists from the site's archive api (/api/v1/web/archive: tipo / genere / sort / q, 30 per page, the total
#     count gives the last page): Movies, Series, Recently added, Most viewed, Top rated, genres, search
#   - seasons and episodes (with their plot) from the series page's Next.js data
#   - links: VixSrc by the IMDb id and the site's own player vidxgo
#   - watched flag (series -> season -> episode), favourites, downloaded marker, "Title (Year)" / "Show - SxxExx"
#     names, sidecar, INFO via moviemeta merged with the site's fields
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://altadefinizionex.vip/"


VIXSRC_URL = "https://vixsrc.to/"
VIDXGO_URL = "https://v.vidxgo.co/"
PAGE_SIZE = 30


class Altadefinizione(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        # named after the host, not the domain: search history and cookies survive the next domain move
        CBaseHostClass.__init__(self, {"history": "altadefinizione01", "cookie": "altadefinizione01.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/altadefinizione01135.png")
        # filters of the archive api: the site's labels
        self.MENU = [{"category": "list_items", "title": _("Movies"), "filters": {"tipo": "Film"}},
                     {"category": "list_items", "title": _("Series"), "filters": {"tipo": "Serie TV"}},
                     {"category": "list_items", "title": _("Recently added"), "filters": {"sort": "Data di aggiunta"}},
                     {"category": "list_items", "title": _("Most viewed"), "filters": {"sort": "Views"}},
                     {"category": "list_items", "title": _("Top rated"), "filters": {"sort": "Valutazione"}},
                     {"category": "list_genres", "title": _("Genres")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("altadefinizione01")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl.split("#", 1)[0], addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            if cItem.get("type", "") == "video":
                prefix = "video"
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _jsonArray(text, start):
        # the JSON array that begins at text[start] ("[") - brackets inside strings do not count
        depth, inString, escape = 0, False, False
        for pos in range(start, len(text)):
            char = text[pos]
            if inString:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    inString = False
            elif char == '"':
                inString = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    return text[start:pos + 1]
        return ""

    def _pageData(self, url):
        # the Next.js data of a title page (self.__next_f.push chunks, JSON-escaped strings)
        sts, data = self.getPage(url)
        if not sts:
            return ""
        chunks = []
        for raw in re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', data, re.S):
            try:
                chunks.append(ensure_str(json.loads('"%s"' % raw)))
            except Exception:
                continue
        return "".join(chunks)

    def _titleInfo(self, text):
        # (imdb id, vidxgo token, seasons [{number, episodes: [{number, title, plot}]}], info dict) of a title page
        imdb = self.cm.ph.getSearchGroups(text, r'"imdbId":"(tt\d+)"')[0]
        token = self.cm.ph.getSearchGroups(text, r'"token":"(\d+)"')[0] or imdb[2:]
        seasons = []
        pos = text.find('"seasons":[')
        if pos > -1:
            try:
                seasons = json_loads(self._jsonArray(text, pos + len('"seasons":'))) or []
            except Exception:
                printExc()
        info = {}
        for key, field in (("rating", "rating"), ("duration", "durationMin"), ("country", "country"), ("director", "director"), ("cast", "cast")):
            # a JSON string ("Robert Carlyle (Ray), Ray Winstone (Dave)") or a number
            value = self.cm.ph.getSearchGroups(text, r'"%s":(?:"((?:[^"\\]|\\.)*)"|(\d+))' % field, 2)
            value = value[0] or value[1]
            if key == "cast":
                value = ", ".join(value.split(", ")[:6])
            if value:
                info[key] = value + (" min" if key == "duration" else "")
        return imdb, token, [s for s in seasons if isinstance(s, dict) and s.get("number")], info

    ###################################################
    # lists
    ###################################################
    def _archiveUrl(self, filters):
        return self.getFullUrl("api/v1/web/archive?" + urllib_urlencode(filters))

    def _archive(self, filters, page):
        # one page of the archive api: (items, total count)
        sts, data = self.getPage("%s&offset=%d&limit=%d&count=1" % (self._archiveUrl(filters), (page - 1) * PAGE_SIZE, PAGE_SIZE))
        if not sts:
            return [], 0
        try:
            res = json_loads(data)
            return res.get("items") or [], int(res.get("count") or 0)
        except Exception:
            printExc()
            return [], 0

    def listItems(self, cItem):
        printDBG("Altadefinizione.listItems |%s|" % cItem)
        page = max(1, int(cItem.get("page", 1) or 1))
        items, count = self._archive(cItem.get("filters", {}), page)
        normalize = IsMediaNamingNormalized()
        for item in items:
            title, slug, itemId = ensure_str(item.get("title", "")), ensure_str(item.get("slug", "")), item.get("id")
            if not title or not itemId:
                continue
            series = item.get("kind") == "series"
            year = str(item.get("year") or "")
            plot = ensure_str(item.get("plot") or "")
            genres = ", ".join(ensure_str(g) for g in item.get("genres") or [])
            desc = " | ".join("%s: %s" % (k, v) for k, v in ((_("Year"), year), (_("Genre"), genres), (_("Rating"), item.get("rating") or "")) if v)
            params = stripPagerKeys(dict(cItem))
            params.pop("filters", None)
            params.update({"good_for_fav": True, "url": self.getFullUrl("%s/%s-%s-streaming.html" % ("serie-tv" if series else "film", itemId, urllib_quote(slug))),
                           "icon": ensure_str(item.get("posterUrl") or "") or self.DEFAULT_ICON_URL, "desc": "%s[/br]%s" % (desc, plot) if plot else desc,
                           "imdb": ensure_str(item.get("imdbId") or ""), "s_year": year, "plot": plot, "s_title": title})
            if series:
                params.update({"category": "list_seasons", "title": title, "meta_type": "tv"})
                self.addDir(params)
            else:
                withYear = year and normalize and not title.endswith("(%s)" % year)
                params.update({"category": "video", "title": "%s (%s)" % (title, year) if withYear else title, "meta_type": "movie"})
                self.addVideo(params)
        lastPage = (count + PAGE_SIZE - 1) // PAGE_SIZE
        # the list reads its page from cItem["page"]; the template only gives the pager rows a url and the Jump row
        url = self._archiveUrl(cItem.get("filters", {}))
        addPagingItems(self, dict(cItem, url=url), page, lastPage > page, lastPage, url.replace("{", "{{").replace("}", "}}") + "&page={page}")

    def listGenres(self, cItem):
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        menu = self.cm.ph.getDataBeetwenMarkers(data, '<div class="dropdown-menu p-3">', "</nav>", False)[1]
        for title in re.findall(r'class="nav-link">([^<]+)</a>', menu):
            title = self.cleanHtmlStr(title)
            self.addDir(dict(cItem, good_for_fav=True, category="list_items", title=title, filters={"genere": title}))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Altadefinizione.listSearchResult [%s]" % searchPattern)
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        self.listItems(dict(cItem, category="search_next_page", s_pattern=pattern, filters={"q": pattern}))

    def listSeasons(self, cItem):
        printDBG("Altadefinizione.listSeasons |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        imdb, token, seasons, _info = self._titleInfo(self._pageData(url))
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or cItem["title"]
        fields = {"s_title": sTitle, "imdb": imdb or cItem.get("imdb", ""), "token": token}
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category="list_episodes", season=str(seasons[0]["number"]), url="%s#s%s" % (url, seasons[0]["number"]), **fields), seasons)
            return
        normalize = IsMediaNamingNormalized()
        for season in seasons:
            number = season["number"]
            seasonTag = formatSxxExx(number) if normalize else "%s %s" % (_("Season"), number)
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (sTitle, seasonTag), "season": str(number),
                           "url": "%s#s%s" % (url, number), "desc": "%s: %d[/br]%s" % (_("Episodes"), len(season.get("episodes") or []), cItem.get("plot", ""))})
            self.addDir(params)

    def listEpisodes(self, cItem, seasons=None):
        printDBG("Altadefinizione.listEpisodes |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        season = str(cItem.get("season", "") or self.cm.ph.getSearchGroups(cItem["url"], r"#s(\d+)")[0])
        if seasons is None:
            imdb, token, seasons, _info = self._titleInfo(self._pageData(url))
            cItem = dict(cItem, imdb=imdb or cItem.get("imdb", ""), token=token)
        episodes = []
        for item in seasons:
            if str(item["number"]) == season:
                episodes = [e for e in item.get("episodes") or [] if isinstance(e, dict) and e.get("number")]
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or cItem["title"]
        normalize = IsMediaNamingNormalized()
        for item in episodes:
            episode, name = item["number"], ensure_str(item.get("title") or "")
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %s" % (sTitle, _("Season"), season, _("Episode"), episode)
            if name and not re.match(r"^Episodio\s*\d+$", name, re.I):
                title = "%s - %s" % (title, name)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": "%s#s%se%s" % (url, season, episode),
                           "season": season, "episode": str(episode), "desc": ensure_str(item.get("plot") or "") or cItem.get("plot", ""), "meta_type": "tv"})
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Altadefinizione.getLinksForVideo [%s]" % cItem.get("url", ""))
        imdb, token = cItem.get("imdb", ""), cItem.get("token", "")
        if not imdb:
            imdb, token, _seasons, _info = self._titleInfo(self._pageData(cItem["url"]))
        token = token or imdb[2:]
        if not token:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        season, episode = str(cItem.get("season", "") or ""), str(cItem.get("episode", "") or "")
        path = "/%s/%s" % (season, episode) if (season and episode) else ""
        urltab = []
        if imdb:
            vixsrc = "%stv/%s%s?lang=it" % (VIXSRC_URL, imdb, path) if path else "%smovie/%s?lang=it" % (VIXSRC_URL, imdb)
            urltab.append({"name": "VixSrc", "url": strwithmeta(vixsrc, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        urltab.append({"name": "vidxgo", "url": strwithmeta(VIDXGO_URL + token + path, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("plot", ""), metaQuery=self._metaQuery(cItem, imdb)))

    def getVideoLinks(self, videoUrl):
        printDBG("Altadefinizione.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    @staticmethod
    def _metaQuery(cItem, imdb):
        # the lookup of the INFO view (getMetaByImdbId, else getMeta by title) for the download sidecar
        return sidecarMetaQuery(cItem.get("meta_type", "") or "movie", cItem.get("s_title", "") or cItem.get("title", ""), cItem.get("s_year", ""), imdbId=imdb, skip=())

    def getArticleContent(self, cItem):
        printDBG("Altadefinizione.getArticleContent [%s]" % cItem.get("url", ""))
        imdb, _token, _seasons, info = self._titleInfo(self._pageData(cItem.get("url", "")))
        imdb = imdb or cItem.get("imdb", "")
        mediaType = cItem.get("meta_type", "") or "movie"
        year = cItem.get("s_year", "")
        if year:
            info["year"] = year
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta:
                meta = getMeta(mediaType, cItem.get("s_title", "") or cItem.get("title", ""), year)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        if "directors" in info:
            info.pop("director", None)
        text = cItem.get("desc", "") if cItem.get("episode") else cItem.get("plot", "")
        metaPlot = meta.get("plot", "")
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
        printDBG("Altadefinizione.handleService name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category in ("list_items", "search_next_page"):
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "search":
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
        CHostBase.__init__(self, Altadefinizione(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("altadefinizione01")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
