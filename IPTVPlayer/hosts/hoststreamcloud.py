# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.10.2026 - new host for streamcloud.date (German films and series, DataLife Engine)
#   - Movies / Series / Cinema movies / Popular / Upcoming / Genres / Year / Country / Search, First / Jump /
#     Next page with the last page from the pager (search: from the number of results); "Popular" is one long
#     page -> paged locally
#   - the lists of the site do not tell films from series: rows of Movies / Cinema movies are films, rows of
#     Series are series, the rows of the mixed lists (genres, years, countries, popular, upcoming, search) open
#     the page first - a film shows its video row, a series its seasons
#   - films: the devideosrc.co player of the page, expanded into its hosters through libs/meinecloud.py and
#     resolved via urlparser (the site's own /player/player.php only holds an ad redirect - ignored)
#   - series: one page per show; seasons + episodes from the DeVideoSRC API by the IMDb id of the page
#     (libs/meinecloud.py), an episode plays devideosrc.co/serial/<imdb>/<season>/<episode>. Pages without an
#     IMDb id look the show up in the IMDb suggestion API (exact title only)
#   - watched flag (series -> season -> episode), favourites reopen without state, downloaded marker on the page
#     url / page url + "#s<season>e<episode>", "Title (Year)" / "Show - SxxExx" names, sidecar on the links
#   - INFO via moviemeta (IMDb id of the page) merged with the site's fields
#   - the domain hops: alternative domain in the host options, favourites follow it
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.meinecloud import MeineCloud
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
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
# genres of the filter menu that are lists of their own
SKIP_GENRES = ("Serien", "kinofilme", "Kinofilme", "Demnächst")
LOCAL_PAGE_SIZE = 50


class StreamCloud(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "streamcloud", "cookie": "streamcloud.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.streamcloud_domain.value.strip()
        self.MAIN_URL = (domain.rstrip("/") + "/") if self.cm.isValidUrl(domain) else gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("/templates/streamcloud/images/192x192.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/filme-stream/"), "kind": "movie"},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/serien/"), "kind": "tv"},
                     {"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("/kinofilme/"), "kind": "movie"},
                     {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("/beliebte-filme/")},
                     {"category": "list_items", "title": _("Upcoming"), "url": self.getFullUrl("/demnachst/")},
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
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", ensure_str(title or "").lower(), flags=re.U)).strip()

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
    def _pageKind(data):
        # ("tv" | "movie" | "", imdb) of an item page
        m = re.search(r"var\s+imdb\s*=\s*'(tt\d+)?'", data or "")
        if m or 'id="serial_iframe"' in (data or ""):
            imdb = (m.group(1) if m else "") or ""
            if not imdb:
                emb = MC_URL_RE.search(data) or re.search(r"imdb\.com/title/(tt\d+)", data)
                imdb = emb.group(emb.lastindex) if emb else ""
            return "tv", imdb
        m = MC_URL_RE.search(data or "")
        if m:
            return "movie", m.group(2)
        return "", ""

    def _siteTitle(self, data):
        # "Titel:" row of the page, else its <title> without the site suffix
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<strong[^>]*>\s*Titel:\s*</strong>\s*<div>(.*?)</div>")[0])
        return title or self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'itemprop="name">\s*(?:Serien\s+)?([^<]+?)\s+stream<')[0])

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
        sts, data = self.getPage(self.MAIN_URL + "streamcloud/")
        if not sts:
            return
        block = ""
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<details class="sc-f"', "</details>"):
            if re.search(r'class="sc-f-in">\s*%s\b' % re.escape(cItem.get("filter", "")), item):
                block = item
                break
        seen = set()
        for url, title in re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', block):
            title = self.cleanHtmlStr(title)
            url = self.getFullUrl(url)
            if not title or title in SKIP_GENRES or url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": url.rstrip("/") + "/"})

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
        local = "beliebte-filme" in cItem.get("url", "")
        if query:
            pageUrlTpl = self.getFullUrl("/index.php?do=search&subaction=search&story=%s&search_start={page}" % urllib_quote_plus(query))
        elif local:
            # one long page: "#p<page>" only tells the pages apart (dropped before the request)
            pageUrlTpl = self._rebase(cItem["url"]) + "#p{page}"
        else:
            base = re.sub(r"page/\d+/?(?:\?.*)?$", "", self._rebase(cItem["url"]))
            pageUrlTpl = base.rstrip("/") + "/page/{page}/"
        url = pageUrlTpl.format(page=page) if (query or page > 1) else cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        rows = []
        seen = set()
        for item in data.split('<div class="item cf')[1:]:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'class="f_title"><a href="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="f_title"><a href="[^"]+">([^<]+)')[0])
            if not url or not title or url in seen:
                continue
            seen.add(url)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+?src="([^"]+)')[0])
            year = self.cm.ph.getSearchGroups(item, r'class="f_year">\s*((?:19|20)\d\d)')[0]
            rows.append((url, title, icon, year))
        lastPage = 0
        if local:
            lastPage = max(1, (len(rows) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE)
            rows = rows[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]
            hasNext = page < lastPage
        elif query:
            hasNext = "list_submit(%d)" % (page + 1) in data
            total = self.cm.ph.getSearchGroups(data, r'search_result_num[^>]*>\D*(\d+)')[0]
            first, last = self.cm.ph.getSearchGroups(data, r"(\d+)\s*-\s*(\d+)\)", 2)
            try:
                perPage = int(last) - int(first) + 1
                if hasNext and perPage > 0:
                    lastPage = (int(total) + perPage - 1) // perPage
                elif not hasNext:
                    lastPage = page
            except (TypeError, ValueError):
                lastPage = 0
        else:
            pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="wp-pagenavi"', "</div>\n", False)[1] or data
            nums = [int(n) for n in re.findall(r'/page/(\d+)/[^"]*">\s*\d+\s*<', pager)]
            lastPage = max(nums + [page]) if nums else page
            hasNext = bool(re.search(r'/page/%d/' % (page + 1), pager))
        for url, title, icon, year in rows:
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": year}
            self._addRow(params, title, year, cItem.get("kind", ""), normalize)
        addPagingItems(self, cItem, page, bool(rows) and hasNext, lastPage, pageUrlTpl)

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
            if kind == "movie" and imdb:
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
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("StreamCloud.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _sitePlot(self, data):
        content = self.cm.ph.getDataBeetwenMarkers(data, 'id="longInfo"', 'class="rightSide"', False)[1]
        return self.cleanHtmlStr(self.cm.ph.getSearchGroups(content, r'(?s)id="storyline"[^>]*>\s*<span>(.*?)</span>')[0])

    def _siteInfo(self, data):
        content = self.cm.ph.getDataBeetwenMarkers(data, 'id="longInfo"', 'class="rightSide"', False)[1]
        info = {}
        for key, label in (("duration", "Spielzeit"), ("genres", "Genres"), ("year", "Veröffentlicht"), ("cast", "Schauspieler"), ("directors", "Regie")):
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(content, r"(?s)<strong[^>]*>\s*%s:\s*</strong>\s*<div>(.*?)</div>" % label)[0])
            if key == "genres":
                value = ", ".join(g.strip() for g in value.split("/") if g.strip() and g.strip() != "Serien")
            if value and "{" not in value:
                info[key] = value
        rating = self.cm.ph.getSearchGroups(data, r'itemprop="ratingValue">\s*([\d.]+)')[0]
        if rating and rating != "0":
            info["imdb_rating"] = "%s/10" % rating
        quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'id="subHeadLeft"[^>]*>\s*<span[^>]*>([^<]+)</span>')[0])
        if quality:
            # "HD | Deutsch"
            info["quality"] = re.sub(r"\s+", " ", quality)
        return info, self._sitePlot(data)

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
            # the services' fields first, the site's fill the gaps (its rating is the IMDb one)
            if key == "imdb_rating" and metaInfo.get("imdb_rating"):
                continue
            metaInfo.setdefault(key, value)
        metaPlot = meta.get("plot", "")
        text = cItem.get("desc", "") if cItem.get("category") == "episode" and cItem.get("desc") else plot
        text = text or (cItem.get("desc", "") if not re.match(r"^\d{4}$", cItem.get("desc", "")) else "")
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
