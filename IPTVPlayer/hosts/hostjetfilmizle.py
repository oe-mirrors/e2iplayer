# -*- coding: utf-8 -*-
LAST_MODIFIED = "19.11.2026"
# 19.11.2026 - new host for jetfilmizle.app (Turkish films and series): lists, genres, years, languages, search;
#   streams per player button from POST /jetplayer (an iframe: videopark.top "Vip", vidmoly "Moly", the "Genel"
#   group is an aggregator page whose sources come from its api_sources.php)
import json
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getItemMeta, getMeta, getMetaByImdbId, metaArticle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.jetfilmizle_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.jetfilmizle_domain)]


def gettytul():
    return "https://jetfilmizle.app/"


def _jsonLoads(text):
    # stdlib json gives unicode on Python 2 - as UTF-8 str like the rest of the host's texts
    return ensure_str_deep(json.loads(text))


# the player groups of a title page (data-player-type)
TYPE_LABELS = {"dublaj": "Türkçe Dublaj", "altyazili": "Türkçe Altyazılı", "genel": "Genel"}


class JetFilmizle(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what a favourite needs to open the row again - nothing list/page specific (an episode row carries its
    # film_id and player sources, the series page is not read again for it)
    FAV_FIELDS = ("name", "category", "type", "title", "url", "icon", "desc", "s_title", "season", "episode", "film_id", "sources",
                  "meta_type", "meta_title", "meta_alt_title", "meta_year", "meta_season", "meta_episode", "good_for_fav")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "jetfilmizle", "cookie": "jetfilmizle.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.jetfilmizle_domain.value.strip()
        self.MAIN_URL = domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul()
        lists = ((_("Movies"), "filmler"), (_("Series"), "diziler"), ("Yerli Filmler", "yerli-filmler"), ("Yerli Diziler", "yerli-diziler"),
                 ("Yabancı Diziler", "yabanci-diziler"), ("Türkçe Dublaj", "turkce-dublaj"), ("Türkçe Altyazılı", "turkce-altyazili"),
                 ("IMDb Top", "imdb-top"))
        self.MENU = [{"category": "list_items", "good_for_fav": True, "title": title, "url": self.MAIN_URL + path} for title, path in lists]
        self.MENU += [{"category": "list_links", "title": _("Genres"), "url": self.MAIN_URL + "turler", "link_re": r"/tur/[^/\"#?]+"},
                      {"category": "list_links", "title": _("Year"), "url": self.MAIN_URL + "yillar", "link_re": r"/yil/\d{4}"},
                      {"category": "list_links", "title": _("Language"), "url": self.MAIN_URL + "diller", "link_re": r"/dil/[^/\"#?]+"}]
        self.MENU += self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("jetfilmizle")
        self.wfInitFolderCache()

    def _siteUrl(self, url):
        # favourites keep the domain of the day they were added; "#s<n>e<n>" marks an episode row of the series page
        return re.sub(r"^https?://[^/]+/", self.MAIN_URL, self.getFullUrl(str(url).split("#")[0]))

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(self._siteUrl(baseUrl), addParams, post_data)

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", str(url or "").strip()).rstrip("/")

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            category = cItem.get("category", "")
            if category in ("video", "episode"):
                return "video:%s" % path
            if category == "jf_series":
                return "series:%s" % path
            if category == "jf_season":
                return "season:%s|%s" % (path, cItem.get("season", ""))
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        if cItem.get("good_for_fav"):
            return self.getFavouriteFieldsData(cItem)
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def listLinks(self, cItem):
        # genre / year / language pages: their links to /tur/<x>, /yil/<yyyy>, /dil/<x>
        printDBG("JetFilmizle.listLinks |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        links = []
        for url, inner in re.findall(r'(?s)<a[^>]+href="([^"]*(?:%s))"[^>]*>(.*?)</a>' % cItem["link_re"], data):
            url = self.getFullUrl(url)
            title = self.cleanHtmlStr(inner)
            if url in seen or not title:
                continue
            seen.add(url)
            links.append((url, title))
        if "/yil/" in cItem["link_re"]:
            links.sort(key=lambda x: x[0], reverse=True)
        for url, title in links:
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": url})

    def _pageUrl(self, baseUrl, page):
        baseUrl = self._siteUrl(baseUrl).rstrip("/")
        return baseUrl if page <= 1 else "%s/sayfa-%d" % (baseUrl, page)

    def _addCard(self, card, cItem):
        url = self.getFullUrl(self.cm.ph.getSearchGroups(card, r'<a href="([^"]+/(?:film|dizi)/[^"]+)"')[0])
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="fc-title">(.*?)</h3>')[0])
        if not url or not title:
            return False
        origTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="fc-orig">(.*?)</span>')[0])
        if origTitle.lower() == title.lower():
            origTitle = ""
        year = self.cm.ph.getSearchGroups(card, r'class="fc-year">\s*(\d{4})')[0]
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="fc-sure">(.*?)</span>')[0])
        imdbRating = self.cm.ph.getSearchGroups(card, r'(?s)fc-rating--imdb".*?</i>\s*([\d.]+)')[0]
        chips = ", ".join(self.cleanHtmlStr(x) for x in re.findall(r'(?s)class="fc-chip [^"]*"[^>]*>(.*?)</span>\s*(?=<span class="fc-chip|</span>)', card))
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="fc-desc">(.*?)</span>')[0])
        icon = self.cm.ph.getSearchGroups(card, r'<img[^>]+src="([^"]+)"')[0]
        descLine = " | ".join(x for x in (year, duration, chips, "IMDb %s" % imdbRating if imdbRating else "") if x)
        desc = "[/br]".join(x for x in (origTitle and "%s: %s" % (_("Original title"), origTitle), descLine, plot) if x)
        isSeries = "/dizi/" in url
        if IsMediaNamingNormalized() and not isSeries:
            label = "%s (%s)" % (title, year) if year else title
        else:
            label = " - ".join(x for x in (title, origTitle) if x)
        params = stripPagerKeys(dict(cItem))
        params.pop("base_url", None)
        params.update({"name": "category", "good_for_fav": True, "title": label, "url": url, "icon": icon, "desc": desc,
                       "meta_title": origTitle or title, "meta_alt_title": title if origTitle else "", "meta_year": year})
        if isSeries:
            params.update({"category": "jf_series", "s_title": title, "meta_type": "tv"})
            self.addDir(params)
        else:
            params.update({"category": "video", "meta_type": "movie"})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        printDBG("JetFilmizle.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = baseUrl if "?" in baseUrl else self._pageUrl(baseUrl, page)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = 0
        for card in data.split('class="film-card-wrapper')[1:]:
            if self._addCard(card.split('<div class="col">')[0], cItem):
                count += 1
        if not count:
            return
        if "?" in baseUrl:
            return  # the search has a single page
        pager = self.cm.ph.getSearchGroups(data, r'(?s)class="pagination-modern"(.*?)</ul>')[0]
        pages = [int(p) for p in re.findall(r"/sayfa-(\d+)", pager)]
        lastPage = max(pages + [page])
        nextItem = stripPagerKeys(dict(cItem))
        nextItem["base_url"] = baseUrl
        # listItems() builds the page url from base_url + page itself; the template is the "Jump" target
        addPagingItems(self, nextItem, page, page < lastPage, lastPage, self._siteUrl(baseUrl).rstrip("/") + "/sayfa-{page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("JetFilmizle.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.MAIN_URL + "arama?q=" + urllib_quote_plus(searchPattern.strip())
        self.listItems(dict(cItem, category="list_items", url=url))

    ###################################################
    # series
    ###################################################
    def _episodes(self, data):
        # {(season, episode): {player_type: source_index}} from the episode buttons of all player groups
        episodes = {}
        for tag in re.findall(r'<button[^>]+class="[^"]*episode-btn[^"]*"[^>]*>', data):
            attrs = dict(re.findall(r'data-([a-z-]+)="([^"]*)"', tag))
            season, episode = attrs.get("season", ""), attrs.get("episode", "")
            if not season.isdigit() or not episode.isdigit() or not attrs.get("player-type") or attrs.get("source-index", "") == "":
                continue
            episodes.setdefault((int(season), int(episode)), {})[attrs["player-type"]] = attrs["source-index"]
        return episodes

    def listSeasons(self, cItem):
        printDBG("JetFilmizle.listSeasons |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        episodes = self._episodes(data)
        seasons = sorted(set(s for s, e in episodes))
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, season=str(seasons[0])), data)
            return
        for season in seasons:
            params = dict(cItem)
            params.update({"category": "jf_season", "title": "%s - %s %d" % (cItem.get("s_title", cItem["title"]), _("Season"), season), "season": str(season)})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("JetFilmizle.listEpisodes |%s|" % cItem)
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        filmId = self.cm.ph.getSearchGroups(data, r'name="film_id" value="(\d+)"')[0]
        sTitle = cItem.get("s_title", cItem["title"])
        normalize = IsMediaNamingNormalized()
        for (season, episode), sources in sorted(self._episodes(data).items()):
            if str(season) != str(cItem.get("season", season)):
                continue
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %d. Sezon %d. Bölüm" % (sTitle, season, episode)
            params = stripPagerKeys(dict(cItem))
            # one url per episode (download marker / favourites), the page itself is the series page
            params.update({"good_for_fav": True, "category": "episode", "title": title, "film_id": filmId, "sources": sources,
                           "url": "%s#s%de%d" % (self._siteUrl(cItem["url"]), season, episode),
                           "season": str(season), "episode": str(episode), "meta_season": str(season), "meta_episode": str(episode),
                           "desc": ", ".join(TYPE_LABELS.get(t, t) for t in sorted(sources)) + ("[/br]" + cItem["desc"] if cItem.get("desc") else "")})
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("JetFilmizle.getLinksForVideo [%s]" % cItem)
        pageUrl = self._siteUrl(cItem.get("url", ""))
        sources = []  # (player_type, source_index, label)
        sidecarTxt = cItem.get("desc", "")
        if cItem.get("category") == "episode":
            filmId = cItem.get("film_id", "")
            for playerType, index in sorted((cItem.get("sources") or {}).items()):
                sources.append((playerType, index, ""))
        else:
            sts, data = self.getPage(pageUrl)
            if not sts:
                return []
            filmId = self.cm.ph.getSearchGroups(data, r'name="film_id" value="(\d+)"')[0]
            for tag, label in re.findall(r'(?s)(<button[^>]+class="[^"]*player-source-btn[^"]*"[^>]*>)(.*?)</button>', data):
                if "episode-btn" in tag:
                    continue
                attrs = dict(re.findall(r'data-([a-z-]+)="([^"]*)"', tag))
                if attrs.get("player-type") and attrs.get("source-index", "") != "":
                    sources.append((attrs["player-type"], attrs["source-index"], self.cleanHtmlStr(label)))
            sidecarTxt = self._ldJson(data).get("description", "") or sidecarTxt
        urltab = []
        episodeTag = "s%se%s-" % (cItem.get("season", ""), cItem.get("episode", "")) if cItem.get("category") == "episode" else ""
        for playerType, index, label in sources:
            if not filmId:
                break
            name = " - ".join(x for x in (TYPE_LABELS.get(playerType, playerType), label) if x)
            meta = {"Referer": pageUrl, "film_id": filmId, "source_index": index, "player_type": playerType}
            urltab.append({"name": name, "url": strwithmeta("%s#%s%s-%s" % (pageUrl, episodeTag, playerType, index), meta), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        if cItem.get("category") == "episode":
            metaQuery = sidecarMetaQuery("tv", cItem.get("meta_title", "") or cItem.get("s_title", ""), season=cItem.get("meta_season", ""), episode=cItem.get("meta_episode", ""))
        else:
            altTitles = (cItem["meta_alt_title"],) if cItem.get("meta_alt_title") else ()
            metaQuery = sidecarMetaQuery("movie", cItem.get("meta_title", ""), cItem.get("meta_year", ""), "", altTitles=altTitles)
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt, metaQuery))

    def _jetEmbedSources(self, embedUrl):
        # the "Genel" player: an aggregator page (/jetembed/<imdb>) - its sources (vidfast, ...) from api_sources.php
        imdb = self.cm.ph.getSearchGroups(embedUrl, r"/jetembed/(tt\d+)")[0]
        if not imdb:
            return []
        args = []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=embedUrl)
        sts, data = self.cm.getPage(embedUrl, params)
        if sts:
            args = re.findall(r"player\.init\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*([^,]+?)\s*,\s*([^)]+?)\s*\)", data)
        kind, season, episode = "movie", "", ""
        if args:
            kind = args[0][1] or kind
            season = args[0][2].strip("'\" ") if args[0][2].strip() != "null" else ""
            episode = args[0][3].strip("'\" ") if args[0][3].strip() != "null" else ""
        apiUrl = re.sub(r"/jetembed/.*$", "/jetembed/backend/api_sources.php", embedUrl) + "?imdb=%s&type=%s" % (imdb, kind)
        if season and episode:
            apiUrl += "&season=%s&episode=%s" % (season, episode)
        sts, data = self.cm.getPage(apiUrl, params)
        if not sts:
            return []
        try:
            info = _jsonLoads(data)
        except Exception:
            printExc()
            return []
        def priority(source):
            try:
                return -float(source.get("priority_score") or 0)
            except (AttributeError, TypeError, ValueError):
                return 0

        urls = []
        for source in sorted(info.get("sources") or [], key=priority):
            url = source.get("url", "") if isinstance(source, dict) else ""
            if self.cm.isValidUrl(url) and self.up.checkHostSupport(url) == 1:
                urls.append(url)
        printDBG("JetFilmizle._jetEmbedSources %s" % urls)
        return urls

    def getVideoLinks(self, videoUrl):
        printDBG("JetFilmizle.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        meta = videoUrl.meta
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        pageUrl = meta.get("Referer") or self.MAIN_URL
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=pageUrl, Accept="*/*")
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        post = {"film_id": meta.get("film_id", ""), "source_index": meta.get("source_index", ""), "player_type": meta.get("player_type", "")}
        sts, data = self.getPage(self.MAIN_URL + "jetplayer", params, post)
        if not sts:
            return []
        embed = self.cm.ph.getSearchGroups(data, r"""<iframe[^>]+src=['"]([^'"]+)['"]""")[0]
        if embed.startswith("//"):
            embed = "https:" + embed
        if not self.cm.isValidUrl(embed):
            printDBG("JetFilmizle.getVideoLinks no player: %s" % data[:300])
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        embeds = self._jetEmbedSources(embed) if "/jetembed/" in embed else [embed]
        for url in embeds:
            if self.up.checkHostSupport(url) != 1:
                printDBG("JetFilmizle.getVideoLinks unsupported player [%s]" % url)
                continue
            links = self.up.getVideoLinkExt(strwithmeta(url, {"Referer": self.MAIN_URL}))
            if links:
                return decorateResolvedLinkItems(links, sidecar)
        if not embeds:
            # the "Genel" page without a source E2iPlayer can open
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
        elif self.up.checkHostSupport(embeds[0]) != 1:
            SetIPTVPlayerLastHostError(_("Hosting \"%s\" not supported.") % self.up.getHostName(embeds[0]))
        return []

    ###################################################
    # INFO
    ###################################################
    def _ldJson(self, data):
        # the Movie / TVSeries object of the page's ld+json
        for block in re.findall(r'(?s)<script type="application/ld\+json"[^>]*>(.*?)</script>', data):
            try:
                obj = _jsonLoads(block)
            except Exception:
                continue
            objs = obj.get("@graph", [obj]) if isinstance(obj, dict) else (obj if isinstance(obj, list) else [])
            for item in objs:
                if isinstance(item, dict) and item.get("@type") in ("Movie", "TVSeries"):
                    return item
        return {}

    def getArticleContent(self, cItem):
        printDBG("JetFilmizle.getArticleContent [%s]" % cItem)
        info = {}
        icon = ""
        mediaType = "tv" if cItem.get("category") in ("jf_series", "jf_season", "episode") else "movie"
        title = cItem.get("meta_title", "") or cItem.get("s_title", "")
        altTitle = cItem.get("meta_alt_title", "")
        year = cItem.get("meta_year", "")
        text = ""
        imdb = ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            ld = self._ldJson(data)
            text = self.cleanHtmlStr(ld.get("description", ""))
            imdb = self.cm.ph.getSearchGroups(" ".join(ld.get("sameAs") or []) if isinstance(ld.get("sameAs"), list) else str(ld.get("sameAs", "")), r"(tt\d{5,})")[0]
            for key, field in (("director", "director"), ("actors", "actor")):
                people = ld.get(field) or []
                people = people if isinstance(people, list) else [people]
                names = ", ".join(p.get("name", "") for p in people[:10] if isinstance(p, dict) and p.get("name"))
                if names:
                    info[key] = names
            genres = ld.get("genre") or []
            if genres:
                info["genres"] = ", ".join(genres) if isinstance(genres, list) else str(genres)
            minutes = self.cm.ph.getSearchGroups(str(ld.get("duration", "")), r"PT(\d+)M")[0]
            if minutes:
                info["duration"] = "%s min" % minutes
            if ld.get("numberOfSeasons"):
                info["seasons"] = str(ld["numberOfSeasons"])
            image = ld.get("image")
            icon = image.get("url", "") if isinstance(image, dict) else (image if isinstance(image, str) else "")
        if altTitle:
            info["original_title"] = title
        if year:
            info["year"] = year
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta:
                meta = getItemMeta(dict(cItem, meta_type=mediaType, meta_title=title, meta_year=year))
            if not meta and altTitle:
                meta = getMeta(mediaType, altTitle, year)
        except Exception:
            printExc()
        meta = meta or {}
        # the site's names only when the services have none (the INFO window shows them once)
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in meta.get("info", {}):
                info.pop(siteKey, None)
        # the site's poster first: Cinemeta's (metahub) answers 404 for new titles
        poster = cItem.get("icon", "") or icon
        return metaArticle(cItem, dict(meta, poster="") if poster else meta, story=text, poster=poster, info=info)

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
        elif category == "list_links":
            self.listLinks(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "jf_series":
            self.listSeasons(self.currItem)
        elif category == "jf_season":
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
        CHostBase.__init__(self, JetFilmizle(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("jetfilmizle")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("video", "episode", "jf_series", "jf_season")
