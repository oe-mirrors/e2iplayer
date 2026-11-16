# -*- coding: utf-8 -*-
LAST_MODIFIED = "16.11.2026"
# streamcloud.date (German films and series, same platform as topstreamfilm.best): the devideosrc.co player by
# the IMDb id of the page (libs/meinecloud.py); alternative domain in the host options, favourites follow it.
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.meinecloud import MeineCloud
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.streamcloud_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.streamcloud_domain)]


def gettytul():
    return "https://streamcloud.date/"


IMDB_SUGGEST_URL = "https://v3.sg.media-imdb.com/suggestion/%s/%s.json"
MC_URL_RE = re.compile(r"devideosrc\.co/(?:custom/)?(movie|serial|embed/download)/(tt\d+)")
# the IMDb id of a title page sits in the (escaped) Next.js data: \"imdb\":\"tt0096697\"
PAGE_IMDB_RE = re.compile(r'\\?"imdb\\?"\s*:\s*\\?"(tt\d+)')
LD_JSON_RE = r'<script type="application/ld\+json">(\{"@context":"https://schema.org","@type":"(?:Movie|TVSeries)".*?\})</script>'


class StreamCloud(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "streamcloud", "cookie": "streamcloud.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.streamcloud_domain.value.strip()
        self.MAIN_URL = (domain.rstrip("/") + "/") if self.cm.isValidUrl(domain) else gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("/brand/streamcloud/apple-touch.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/filme")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/serien")},
                     {"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("/kinofilme")},
                     {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("/discover?sort=beliebt")},
                     {"category": "list_filter", "title": _("Genres"), "filter": "Genre"},
                     {"category": "list_filter", "title": _("Year"), "filter": "Jahr"},
                     {"category": "list_filter", "title": _("Country"), "filter": "Land"}] + self.searchItems()
        self.cacheImdb = {}
        self.watchedHelper = IPTVWatchedHelper("streamcloud")
        self.wfInitFolderCache()

    def _rebase(self, url):
        # urls of favourites saved on an older domain -> the current one
        url = (url or "").replace("&amp;", "&").split("#", 1)[0].strip()
        m = re.match(r"https?://[^/]*streamcloud[^/]*/(.*)$", url)
        return (self.MAIN_URL + m.group(1)) if m else self.getFullUrl(url)

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self._rebase(baseUrl), addParams, post_data)

    def _getJson(self, url):
        sts, data = self.cm.getPage(url, {"header": self.HEADER})
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG("StreamCloud: no JSON from %s" % url)
        return None

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if not url:
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % url
            category = cItem.get("category", "")
            if category == "list_episodes":
                return "%s:%s" % ("season" if "#s" in url else "series", url)
            if category == "list_title":
                return "title:%s" % url
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _plain(title):
        # on Python 2 as unicode - on UTF-8 bytes [^\w] split umlauts into broken bytes ("Sch\xc3 ne")
        text = ensure_str(title or "")
        if not isinstance(text, type(u"")):
            text = text.decode("utf-8", "ignore")
        return ensure_str(re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower(), flags=re.U)).strip())

    def _suggest(self, title, year, kind):
        # IMDb id from the IMDb suggestion API (keyless) - only an exact title match (and year, when known) counts
        query = self._plain(title)
        data = self._getJson(IMDB_SUGGEST_URL % (urllib_quote(query[:1] or "x"), urllib_quote(query))) if query else None
        kinds = ("tvSeries", "tvMiniSeries") if kind == "tv" else ("movie", "tvMovie", "video")
        for row in (data or {}).get("d", []) if isinstance(data, dict) else []:
            # ensure_str: the JSON strings are unicode on py2
            if not isinstance(row, dict) or not ensure_str(row.get("id") or "").startswith("tt") or row.get("qid") not in kinds:
                continue
            if self._plain(row.get("l")) != query:
                continue
            if year and str(row.get("y") or "") not in (str(year), str(int(year) - 1), str(int(year) + 1)):
                continue
            return ensure_str(row["id"])
        return ""

    def _imdbId(self, title, year="", kind="tv"):
        # IMDb id of a page without one: its German title, else the original title moviemeta knows for it
        key = "%s|%s|%s" % (kind, self._plain(title), year)
        if key in self.cacheImdb:
            return self.cacheImdb[key]
        mid = self._suggest(title, year, kind)
        if not mid:
            try:
                info = getMeta(kind, title, year).get("info", {})
            except Exception:
                printExc()
                info = {}
            original = info.get("original_title", "")
            origYear = self.cm.ph.getSearchGroups(str(info.get("year", "")), r"((?:19|20)\d\d)")[0] or year
            if original and self._plain(original) != self._plain(title):
                mid = self._suggest(original, origYear, kind)
        self.cacheImdb[key] = mid
        return mid

    @staticmethod
    def _urlKind(url):
        # /filme/<id>-<slug> = film, /serie/<id>-<slug> = series
        m = re.search(r"/(filme|serie)/\d+", url or "")
        return ({"filme": "movie", "serie": "tv"}[m.group(1)]) if m else ""

    def _ld(self, data):
        # the schema.org Movie / TVSeries block of a title page
        raw = self.cm.ph.getSearchGroups(data or "", LD_JSON_RE)[0]
        try:
            ld = json_loads(raw) if raw else {}
        except Exception:
            printDBG("StreamCloud: broken ld+json")
            ld = {}
        return ld if isinstance(ld, dict) else {}

    def _pageKind(self, data):
        # ("tv" | "movie" | "", imdb) of an item page
        data = data or ""
        m = MC_URL_RE.search(data)
        if m:
            return ("tv" if m.group(1) == "serial" else "movie"), m.group(2)
        m = PAGE_IMDB_RE.search(data)
        imdb = m.group(1) if m else ""
        return {"Movie": "movie", "TVSeries": "tv"}.get(self._ld(data).get("@type"), ""), imdb

    def _mc(self):
        return MeineCloud(self.cm, {"header": self.HEADER}, self.MAIN_URL)

    def _seriesData(self, cItem):
        # (imdb, [(season, [episodes])]) of a series page
        imdb = cItem.get("imdb", "")
        if not imdb:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return "", []
            imdb = self._pageKind(data)[1]
        if not imdb:
            imdb = self._imdbId(cItem.get("s_title", "") or cItem.get("title", ""), cItem.get("meta_year", ""))
        if not imdb:
            return "", []
        return imdb, self._mc().seriesEpisodes(imdb)

    ###################################################
    # lists
    ###################################################
    def listFilter(self, cItem):
        printDBG("StreamCloud.listFilter |%s|" % cItem)
        prefix = {"Genre": "/genre/", "Jahr": "/jahr/", "Land": "/land/"}.get(cItem.get("filter", ""))
        if not prefix:
            return
        # the root is a landing page, the home page with the filter links is /streamcloud
        sts, data = self.getPage(self.MAIN_URL + "streamcloud")
        if not sts:
            return
        rows = []
        seen = set()
        for url, title in re.findall(r'<a href="(%s[^"]+)"[^>]*>([^<]+)</a>' % re.escape(prefix), data):
            title = self.cleanHtmlStr(title)
            if not title or url in seen:
                continue
            seen.add(url)
            rows.append((title, url))
        if prefix == "/jahr/":
            rows.sort(reverse=True)
        for title, url in rows:
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})

    def _addRow(self, params, title, year, kind, normalize):
        if kind == "tv":
            params.update({"category": "list_episodes", "title": title, "s_title": title, "meta_type": "tv", "meta_title": title, "meta_year": year})
            self.addDir(params)
        elif kind == "movie":
            dispTitle = "%s (%s)" % (title, year) if (normalize and year) else title
            params.update({"category": "video", "title": dispTitle, "meta_type": "movie", "meta_title": title, "meta_year": year})
            self.addVideo(params)
        else:
            # film or series - known when the page is opened
            params.update({"category": "list_title", "title": title, "s_title": title, "meta_title": title, "meta_year": year})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("StreamCloud.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        query = cItem.get("query", "")
        if query:
            # one page (up to 60 titles), the site has no paging for it
            base = self.getFullUrl("/suche?q=%s" % urllib_quote_plus(query))
        else:
            base = re.sub(r"([?&])page=\d+&?", r"\1", self._rebase(cItem["url"])).rstrip("?&")
        pageUrlTpl = base.replace("{", "{{").replace("}", "}}") + ("&" if "?" in base else "?") + "page={page}"
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else base)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        count = 0
        seen = set()
        for item in data.split('<a class="cv" ')[1:]:
            item = item.split("</a>", 1)[0]
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="cv-t">([^<]+)')[0] or self.cm.ph.getSearchGroups(item, 'title="([^"]+)')[0])
            if not url or not title or url in seen:
                continue
            seen.add(url)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+?src="([^"]+)')[0])
            # "2026 · ★ 5,3"
            meta = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="cv-m">(.*?)</div>')[0])
            year = self.cm.ph.getSearchGroups(meta, r"\b((?:19|20)\d\d)\b")[0]
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": meta}
            self._addRow(params, title, year, self._urlKind(url), normalize)
            count += 1
        # no last page on the site: only a "more titles" link to the next one
        hasNext = bool(re.search(r"[?&;]page=%d(?!\d)" % (page + 1), data))
        addPagingItems(self, cItem, page, bool(count) and hasNext, 0, pageUrlTpl)

    def listTitle(self, cItem):
        # a row of a mixed list: film -> its video row, series -> its seasons
        printDBG("StreamCloud.listTitle |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        kind, imdb = self._pageKind(data)
        params = dict(cItem)
        params["imdb"] = imdb
        if kind == "tv":
            params.update({"category": "list_episodes", "meta_type": "tv"})
            self.listEpisodes(params)
        else:
            params["desc"] = self._sitePlot(data) or cItem.get("desc", "")
            params["meta_type"] = "movie"
            self._addRow(params, cItem.get("meta_title", "") or cItem.get("title", ""), cItem.get("meta_year", ""), "movie", IsMediaNamingNormalized())

    def listEpisodes(self, cItem):
        printDBG("StreamCloud.listEpisodes |%s|" % cItem)
        pageUrl = cItem["url"].split("#", 1)[0]
        imdb, seasons = self._seriesData(cItem)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        byNum = dict((str(num), eps) for num, eps in seasons)
        season = str(cItem.get("season", "") or "")
        if season not in byNum:
            season = next(iter(byNum)) if len(byNum) == 1 else ""
        base = {"name": "category", "good_for_fav": True, "icon": cItem.get("icon", ""), "s_title": show, "imdb": imdb,
                "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")}
        if not season:
            for num, eps in seasons:
                params = dict(base)
                title = "%s - %s" % (show, formatSxxExx(num)) if normalize else "%s - %s %s" % (show, _("Season"), num)
                params.update({"category": "list_episodes", "title": title, "season": str(num), "url": "%s#s%s" % (pageUrl, num),
                               "desc": "%s: %d" % (_("Episodes"), len(eps))})
                self.addDir(params)
            return
        for ep in byNum[season]:
            epNum = str(ep["episode"])
            epTitle = self.cleanHtmlStr(ep.get("title", ""))
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, epNum))
            else:
                title = "%s - %s %s, %s %s" % (show, _("Season"), season, _("Episode"), epNum)
                if epTitle and not re.match(r"^(?:Episode|Folge)\s*\d+$", epTitle, re.I):
                    title = "%s - %s" % (title, epTitle)
            params = dict(base)
            params.update({"category": "episode", "title": title, "season": season, "episode": epNum,
                           "url": "%s#s%se%s" % (pageUrl, season, epNum), "desc": self.cleanHtmlStr(ep.get("desc", ""))})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("StreamCloud.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "query": searchPattern.strip(), "url": "", "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _addLink(self, urltab, name, url):
        if url in [str(x["url"]) for x in urltab]:
            return
        urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})

    def _addHosters(self, urltab, embeds):
        for url in embeds:
            if self.up.checkHostSupport(url) == 1:
                self._addLink(urltab, self.up.getHostName(url).split(".")[0].capitalize(), url)

    def getLinksForVideo(self, cItem):
        printDBG("StreamCloud.getLinksForVideo [%s]" % cItem)
        urltab = []
        mc = self._mc()
        url = cItem.get("url", "")
        episode = re.search(r"#s(\d+)e(\d+)$", url)
        if episode:
            imdb = cItem.get("imdb", "") or self._seriesData(dict(cItem, imdb=""))[0]
            if imdb:
                season, ep = episode.group(1), episode.group(2)
                self._addHosters(urltab, mc.episodeLinks(imdb, season, ep))
                if not urltab:
                    # the API answered no hosters now: the player page tries again when it is played
                    self._addLink(urltab, "DeVideoSRC", "https://devideosrc.co/serial/%s/%s/%s" % (imdb, season, ep))
        else:
            sts, data = self.getPage(url)
            if not sts:
                return []
            kind, imdb = self._pageKind(data)
            # a video row is a film: a page without ld+json / player iframe still plays by its IMDb id
            if kind != "tv" and imdb:
                embeds = mc.movieLinks(imdb)
                self._addHosters(urltab, embeds)
                if not embeds:
                    self._addLink(urltab, "DeVideoSRC", "https://devideosrc.co/movie/%s" % imdb)
            for link in re.findall(r'<iframe[^>]+src="([^"]+)"', data):
                link = "https:" + link if link.startswith("//") else link
                if not self.cm.isValidUrl(link) or "devideosrc." in link or "/player/player.php" in link:
                    continue
                if "youtube." in link:
                    self._addLink(urltab, _("Trailer"), link)
                elif self.up.checkHostSupport(link) == 1:
                    self._addLink(urltab, self.up.getHostName(link).split(".")[0].capitalize(), link)
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        # the moviemeta query of INFO: the IMDb id of the page, its type and year
        if episode:
            mediaType, year = cItem.get("meta_type", "") or "tv", cItem.get("meta_year", "")
        else:
            mediaType, year = cItem.get("meta_type", "") or kind or "movie", cItem.get("meta_year", "") or self._siteInfo(data)[0].get("year", "")
        title = cItem.get("meta_title", "") or cItem.get("s_title", "") or cItem.get("title", "")
        metaQuery = sidecarMetaQuery(mediaType, title, year, imdb, skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", ""), metaQuery))

    ###################################################
    # INFO
    ###################################################
    def _sitePlot(self, data):
        return self.cleanHtmlStr(ensure_str(self._ld(data).get("description") or ""))

    def _siteInfo(self, data):
        ld = self._ld(data)
        info = {}
        year = self.cm.ph.getSearchGroups(ensure_str(ld.get("datePublished") or ""), r"^((?:19|20)\d\d)")[0]
        if year:
            info["year"] = year
        rating = ld.get("aggregateRating")
        rating = rating.get("ratingValue") if isinstance(rating, dict) else ""
        try:
            if rating and float(rating) > 0:
                # the site's ratings are TMDB ones
                info["tmdb_rating"] = "%.1f/10" % float(rating)
        except (TypeError, ValueError):
            pass
        return info, self.cleanHtmlStr(ensure_str(ld.get("description") or ""))

    def getArticleContent(self, cItem):
        printDBG("StreamCloud.getArticleContent [%s]" % cItem)
        info, plot, imdb, kind = {}, "", cItem.get("imdb", ""), ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot = self._siteInfo(data)
            kind, pageImdb = self._pageKind(data)
            imdb = imdb or pageImdb
        mediaType = cItem.get("meta_type", "") or kind or "movie"
        title = cItem.get("meta_title", "") or cItem.get("s_title", "") or cItem.get("title", "")
        year = cItem.get("meta_year", "") or info.get("year", "")
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and title:
                meta = getMeta(mediaType, title, year)
        except Exception:
            printExc()
        metaInfo = dict(meta.get("info", {}))
        for key, value in info.items():
            # the services' fields first, the site's fill the gaps
            metaInfo.setdefault(key, value)
        metaPlot = meta.get("plot", "")
        # list rows carry only "year · rating" as desc, episodes their own plot
        text = cItem.get("desc", "") if cItem.get("category") == "episode" and cItem.get("desc") else plot
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": metaInfo}]

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
        elif category == "list_filter":
            self.listFilter(self.currItem)
        elif category == "list_title":
            self.listTitle(self.currItem)
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
        CHostBase.__init__(self, StreamCloud(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("streamcloud")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_episodes", "list_title")
