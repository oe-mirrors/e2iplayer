# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.10.2026 - new host for streamkinos.lat (German films and series, DataLife Engine)
#   - Movies / Series / Cinema movies / Upcoming / Latest / Genres / Search, First / Jump / Next page (the site's
#     pager only links the next page; the search pager gives the number of results -> last page)
#   - films: the player sources of the page (data-stream: devideosrc.co, voe, vidara, veev, firestream ...); the
#     devideosrc.co player expands into its hosters through libs/meinecloud.py, all hosters resolve via urlparser
#   - series: one page per season ("Show - Staffel N"); the episodes come from the DeVideoSRC API by the IMDb id
#     of the page (libs/meinecloud.py), an episode plays devideosrc.co/serial/<imdb>/<season>/<episode>. Pages
#     without an IMDb id (many older seasons) look the show up in the IMDb suggestion API (exact title only)
#   - watched flag (series -> season -> episode), favourites reopen without state, downloaded marker on the page
#     url / page url + "#s<season>e<episode>", "Title (Year)" / "Show - SxxExx" names, sidecar on the links
#   - INFO via moviemeta (IMDb id of the page where it has one) merged with the site's fields
#   - the domain hops (CUII blocks): alternative domain in the host options, favourites follow it
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.meinecloud import CAPTCHA_HOSTERS, MeineCloud, isPlayerUrl
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

config.plugins.iptvplayer.streamkinos_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.streamkinos_domain)]


def gettytul():
    return "https://www.streamkinos.lat/"


IMDB_SUGGEST_URL = "https://v3.sg.media-imdb.com/suggestion/%s/%s.json"
# "Show - Staffel 2" / "Show 2. Staffel"
SEASON_RE = re.compile(r"\s*[-:]?\s*(?:(\d+)\.?\s*Staffel|Staffel\s*(\d+))\b", re.I)
# "*English*" / "*Subbed*" marks of the site in the titles
TAG_RE = re.compile(r"\s*\*[^*]+\*")
# genres of the menu that are lists of their own
SKIP_GENRES = ("Serien", "Kinofilme", "Demnächst im kino", "Kinofilme im kino")


class StreamKinos(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "streamkinos", "cookie": "streamkinos.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.streamkinos_domain.value.strip()
        self.MAIN_URL = (domain.rstrip("/") + "/") if self.cm.isValidUrl(domain) else gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("/templates/streamkiste/images/icon/android-chrome-192x192.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/kinofilme-online/"), "kind": "movie"},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/serienstream-deutsch/"), "kind": "tv"},
                     {"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("/aktuelle-kinofilme-im-kino/"), "kind": "movie"},
                     {"category": "list_items", "title": _("Upcoming"), "url": self.getFullUrl("/demnachst/"), "kind": "movie"},
                     {"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("/lastnews/")},
                     {"category": "list_genres", "title": _("Genres")}] + self.searchItems()
        self.cacheImdb = {}
        self.watchedHelper = IPTVWatchedHelper("streamkinos")
        self.wfInitFolderCache()

    def _rebase(self, url):
        # urls of favourites saved on an older domain -> the current one
        url = (url or "").replace("&amp;", "&").split("#", 1)[0].strip()
        m = re.match(r"https?://[^/]*streamkinos[^/]*/(.*)$", url)
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
            printDBG("StreamKinos: no JSON from %s" % url)
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
            if cItem.get("category", "") == "list_episodes":
                return "%s:%s" % ("season" if "#s" in url else "series", url)
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _splitSeason(title):
        # "Show - Staffel 2 *Subbed*" -> ("Show", "2"); no season -> (title without the marks, "")
        title = TAG_RE.sub("", title or "").strip()
        m = SEASON_RE.search(title)
        if not m:
            return title, ""
        return title[:m.start()].strip(" -:") or title, m.group(1) or m.group(2)

    @staticmethod
    def _imdbOfPage(data):
        # IMDb id of the DeVideoSRC player of a page ("" when the page has none)
        m = re.search(r"(?:devideosrc\.co|meinecloud\.click)/(?:custom/)?(?:movie|serial|embed/download)/(tt\d+)", data or "")
        return m.group(1) if m else ""

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

    def _imdbId(self, title, kind="tv"):
        # IMDb id of a page without one: the German title, else the original title moviemeta knows for it
        key = "%s|%s" % (kind, self._plain(title))
        if key in self.cacheImdb:
            return self.cacheImdb[key]
        mid = self._suggest(title, "", kind)
        if not mid:
            try:
                info = getMeta(kind, title).get("info", {})
            except Exception:
                printExc()
                info = {}
            original = info.get("original_title", "")
            year = self.cm.ph.getSearchGroups(str(info.get("year", "")), r"((?:19|20)\d\d)")[0]
            if original and self._plain(original) != self._plain(title):
                mid = self._suggest(original, year, kind)
        self.cacheImdb[key] = mid
        return mid

    def _mc(self):
        return MeineCloud(self.cm, {"header": self.HEADER}, self.MAIN_URL)

    def _seriesData(self, cItem):
        # (imdb, [(season, [episodes])]) of a series page
        imdb = cItem.get("imdb", "")
        if not imdb:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return "", []
            imdb = self._imdbOfPage(data)
        if not imdb:
            imdb = self._imdbId(cItem.get("s_title", "") or self._splitSeason(cItem.get("title", ""))[0])
        if not imdb:
            return "", []
        return imdb, self._mc().seriesEpisodes(imdb)

    ###################################################
    # lists
    ###################################################
    def listGenres(self, cItem):
        printDBG("StreamKinos.listGenres")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        seen = set()
        for name, url in re.findall(r'<a title="Alle ([^"]+?) Filme" href="([^"]+)"', data):
            name = self.cleanHtmlStr(name)
            if name in SKIP_GENRES or url in seen or url.endswith("#"):
                continue
            seen.add(url)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": name, "url": self.getFullUrl(url)})

    def listItems(self, cItem):
        printDBG("StreamKinos.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        query = cItem.get("query", "")
        if query:
            pageUrlTpl = self.getFullUrl("/index.php?do=search&subaction=search&story=%s&search_start={page}" % urllib_quote_plus(query))
        else:
            base = re.sub(r"page/\d+/?$", "", self._rebase(cItem["url"]))
            pageUrlTpl = base + "page/{page}/"
        url = pageUrlTpl.format(page=page) if (query or page > 1) else cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="movie-preview', '<div class="movie-cast">'):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'class="movie-title">\s*<a href="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="movie-title">\s*<a href="[^"]+" title="([^"]+)')[0])
            if not url or not title or url in seen:
                continue
            seen.add(url)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+?(?:data-src|src)="([^"]+)')[0])
            year = self.cm.ph.getSearchGroups(item, r'movie-release">\s*((?:19|20)\d\d)')[0]
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="icon-hd[^>]*>([^<]+)')[0])
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="story">(.*?)</p>')[0])
            desc = " | ".join(x for x in (year, quality) if x)
            if story:
                desc = "%s[/br]%s" % (desc, story) if desc else story
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc}
            show, season = self._splitSeason(title)
            if season or cItem.get("kind") == "tv":
                params.update({"category": "list_episodes", "title": title, "s_title": show, "s_season": season,
                               "meta_type": "tv", "meta_title": show})
                self.addDir(params)
            else:
                dispTitle = "%s (%s)" % (show, year) if (normalize and year) else title
                params.update({"category": "video", "title": dispTitle, "meta_type": "movie", "meta_title": show, "meta_year": year})
                self.addVideo(params)

        lastPage = 0
        if query:
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
            hasNext = bool(re.search(r'href="[^"]*/page/%d/"' % (page + 1), data))
        addPagingItems(self, cItem, page, bool(seen) and hasNext, lastPage, pageUrlTpl)

    def listEpisodes(self, cItem):
        printDBG("StreamKinos.listEpisodes |%s|" % cItem)
        pageUrl = cItem["url"].split("#", 1)[0]
        imdb, seasons = self._seriesData(cItem)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or self._splitSeason(cItem.get("title", ""))[0]
        byNum = dict((str(num), eps) for num, eps in seasons)
        season = str(cItem.get("season", "") or cItem.get("s_season", "") or self._splitSeason(cItem.get("title", ""))[1])
        if season not in byNum:
            season = next(iter(byNum)) if len(byNum) == 1 else ""
        base = {"name": "category", "good_for_fav": True, "icon": cItem.get("icon", ""), "s_title": show, "imdb": imdb,
                "meta_type": "tv", "meta_title": cItem.get("meta_title", show)}
        if not season:
            # a page without a (known) season: the seasons of the show first
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
        printDBG("StreamKinos.listSearchResult [%s]" % searchPattern)
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
        printDBG("StreamKinos.getLinksForVideo [%s]" % cItem)
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
            trailer = ""
            for link in re.findall(r'data-(?:stream|link)="([^"]+)"', data):
                link = link.replace("&amp;", "&").strip()
                link = "https:" + link if link.startswith("//") else link
                if not self.cm.isValidUrl(link) or re.search(r"/(?:e|embed|movie)/?$", link):
                    continue  # the template of a source without an id
                if "youtube." in link or "youtu.be" in link:
                    trailer = trailer or link
                elif isPlayerUrl(link):
                    imdb = MeineCloud.imdbFromUrl(link)
                    if "/movie/" not in link or not imdb:
                        continue
                    embeds = mc.movieLinks(imdb)
                    self._addHosters(urltab, embeds)
                    if not embeds:
                        self._addLink(urltab, "DeVideoSRC", link)
                elif self.up.checkHostSupport(link) == 1:
                    self._addLink(urltab, self.up.getHostName(link).split(".")[0].capitalize(), link)
            # hosters that only show a Turnstile page to a box after the others, the trailer last
            urltab.sort(key=lambda x: any(c in str(x["url"]) for c in CAPTCHA_HOSTERS))
            if trailer:
                self._addLink(urltab, _("Trailer"), trailer)
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("StreamKinos.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        content = self.cm.ph.getDataBeetwenMarkers(data, '<div class="single-content', '<div class="single-content tabs', False)[1]
        info = {}
        genres = [self.cleanHtmlStr(g) for g in re.findall(r"<a[^>]+>([^<]+)</a>", self.cm.ph.getDataBeetwenMarkers(content, 'class="categories"', "</div>", False)[1])]
        genres = [g for g in genres if g and g not in SKIP_GENRES]
        if genres:
            info["genres"] = ", ".join(genres)
        for key, label in (("directors", "Regisseur"), ("cast", "Schauspieler")):
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(content, r"(?s)<h4>\s*%s:\s*</h4>(.*?)</div>" % label)[0])
            if value:
                info[key] = value
        year = self.cm.ph.getSearchGroups(content, r'class="release">\s*\(?((?:19|20)\d\d)')[0]
        if year:
            info["year"] = year
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(content, r'(?s)class="excerpt[^"]*">(.*?)</div>')[0])
        return info, plot

    def getArticleContent(self, cItem):
        printDBG("StreamKinos.getArticleContent [%s]" % cItem)
        info, plot, imdb = {}, "", cItem.get("imdb", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot = self._siteInfo(data)
            imdb = imdb or self._imdbOfPage(data)
        mediaType = cItem.get("meta_type", "") or "movie"
        title = cItem.get("meta_title", "") or self._splitSeason(cItem.get("title", ""))[0]
        year = cItem.get("meta_year", "") or info.get("year", "")
        if mediaType == "tv":
            # the page of one season: its year is the season's
            year = ""
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
        text = cItem.get("desc", "") if cItem.get("category") == "episode" and cItem.get("desc") else plot
        text = text or cItem.get("desc", "")
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
        elif category == "list_genres":
            self.listGenres(self.currItem)
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
        CHostBase.__init__(self, StreamKinos(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("streamkinos")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") == "list_episodes"
