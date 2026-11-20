# -*- coding: utf-8 -*-
LAST_MODIFIED = "19.11.2026"
# 19.11.2026 - new host for setfilmizle.ltd (Turkish films and series, WordPress theme "setfilm"): lists, genres,
#   years, search (?s=), series -> seasons -> episodes. Streams: admin-ajax get_video_url -> the "SetPlay" bridge
#   page (setplay.sbs -> fastplay.mom, urlparser parserSETPLAY / parserFASTPLAY)
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

config.plugins.iptvplayer.setfilmizle_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.setfilmizle_domain)]


def gettytul():
    return "https://www.setfilmizle.ltd/"


def _jsonLoads(text):
    # stdlib json gives unicode on Python 2 - as UTF-8 str like the rest of the host's texts
    return ensure_str_deep(json.loads(text))


class SetFilmizle(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what a favourite needs to open the row again - nothing list/page specific
    FAV_FIELDS = ("name", "category", "type", "title", "url", "icon", "desc", "s_title", "season", "episode",
                  "meta_type", "meta_title", "meta_year", "meta_season", "meta_episode", "good_for_fav")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "setfilmizle", "cookie": "setfilmizle.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.setfilmizle_domain.value.strip()
        self.MAIN_URL = domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul()
        lists = ((_("Movies"), "film/"), (_("Series"), "dizi/"), ("Yerli Filmler", "yerli-filmler/"), ("Yerli Diziler", "yerli-diziler-izle/"),
                 ("Türkçe Dublaj", "turkce-dublaj-filmler/"), ("Türkçe Altyazılı", "turkce-altyazili-filmler/"), (_("Trending"), "trend/"),
                 ("IMDb Top 250", "imdb-en-iyiler/"))
        self.MENU = [{"category": "list_items", "good_for_fav": True, "title": title, "url": self.MAIN_URL + path} for title, path in lists]
        self.MENU += [{"category": "list_links", "title": _("Genres"), "link_re": r"/tur/[^/\"#?]+/"},
                      {"category": "list_links", "title": _("Year"), "link_re": r"/yil/\d{4}/"}]
        self.MENU += self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("setfilmizle")
        self.wfInitFolderCache()

    def _siteUrl(self, url):
        # favourites keep the domain of the day they were added
        return re.sub(r"^https?://[^/]+/", self.MAIN_URL, self.getFullUrl(url))

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
            if category == "sf_series":
                return "series:%s" % path
            if category == "sf_season":
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
        # the genre / year links of the main page
        printDBG("SetFilmizle.listLinks |%s|" % cItem)
        sts, data = self.getPage(self.MAIN_URL)
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
        baseUrl = self._siteUrl(baseUrl)
        if page <= 1:
            return baseUrl
        base, sep, query = baseUrl.partition("?")
        return "%s/page/%d/%s%s" % (base.rstrip("/"), page, sep, query)

    def _kunye(self, card, label):
        # <dl class="hcard-kunye"><div><dt>Yıl</dt><dd>2026</dd></div>...
        return self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r"(?s)<dt>%s</dt>\s*<dd[^>]*>(.*?)</dd>" % re.escape(label))[0])

    def _addCard(self, card, cItem):
        url = self.getFullUrl(self.cm.ph.getSearchGroups(card, r'href="([^"]+)"')[0])
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="card-ad">(.*?)</h\d>')[0])
        if not url or not title or not re.search(r"/(?:film|dizi)/", url):
            return False
        year = self.cm.ph.getSearchGroups(self._kunye(card, "Yıl"), r"(\d{4})")[0]
        duration = self._kunye(card, "Süre")
        genres = self._kunye(card, "Tür")
        lang = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="badge-lang[^"]*">(.*?)</span>')[0])
        imdbRating = self.cm.ph.getSearchGroups(card, r'class="badge-imdb">\s*([\d.]+)')[0]
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="hcard-ozet">(.*?)</p>')[0])
        icon = self.cm.ph.getSearchGroups(card, r'<img[^>]+src="([^"]+)"')[0]
        descLine = " | ".join(x for x in (year, duration, lang, "IMDb %s" % imdbRating if imdbRating else "", genres) if x)
        desc = "[/br]".join(x for x in (descLine, plot) if x)
        isSeries = "/dizi/" in url
        label = "%s (%s)" % (title, year) if IsMediaNamingNormalized() and year and not isSeries else title
        params = stripPagerKeys(dict(cItem))
        params.pop("base_url", None)
        params.update({"name": "category", "good_for_fav": True, "title": label, "url": url, "icon": icon, "desc": desc,
                       "meta_title": title, "meta_year": year})
        if isSeries:
            params.update({"category": "sf_series", "s_title": title, "meta_type": "tv"})
            self.addDir(params)
        else:
            params.update({"category": "video", "meta_type": "movie"})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        printDBG("SetFilmizle.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        baseUrl = cItem.get("base_url") or cItem["url"]
        sts, data = self.getPage(self._pageUrl(baseUrl, page))
        if not sts:
            return
        count = 0
        for card in data.split('class="card-link"')[1:]:
            if self._addCard(card.split("</article>")[0], cItem):
                count += 1
        if not count:
            return
        pager = self.cm.ph.getSearchGroups(data, r'(?s)class="pagination"(.*?)</nav>')[0]
        pages = [int(p) for p in re.findall(r"/page/(\d+)/", pager)]
        lastPage = max(pages + [page])
        nextItem = stripPagerKeys(dict(cItem))
        nextItem["base_url"] = baseUrl
        # listItems() builds the page url from base_url + page itself; the template is the "Jump" target
        base, sep, query = self._siteUrl(baseUrl).partition("?")
        addPagingItems(self, nextItem, page, page < lastPage, lastPage, "%s/page/{page}/%s%s" % (base.rstrip("/"), sep, query))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SetFilmizle.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.MAIN_URL + "?s=" + urllib_quote_plus(searchPattern.strip())
        self.listItems(dict(cItem, category="list_items", url=url))

    ###################################################
    # series
    ###################################################
    def _seasons(self, data):
        # [(season, panel html)] of the season tabs
        seasons = []
        for season, panel in re.findall(r'(?s)id="sezon-panel-(\d+)"(.*?)(?=id="sezon-panel-\d+"|</section>|$)', data):
            if 'class="fep"' in panel:
                seasons.append((season, panel))
        return seasons

    def listSeasons(self, cItem):
        printDBG("SetFilmizle.listSeasons |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._seasons(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, season=seasons[0][0]), data)
            return
        for season, panel in seasons:
            params = dict(cItem)
            params.update({"category": "sf_season", "title": "%s - %s %s" % (cItem.get("s_title", cItem["title"]), _("Season"), season), "season": season})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("SetFilmizle.listEpisodes |%s|" % cItem)
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        sTitle = cItem.get("s_title", cItem["title"])
        normalize = IsMediaNamingNormalized()
        for season, panel in self._seasons(data):
            if season != str(cItem.get("season", season)):
                continue
            for item in panel.split('class="fep"')[1:]:
                item = item.split("</a>")[0]
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
                episode = self.cm.ph.getSearchGroups(url, r"-(\d+)-bolum")[0] or self.cm.ph.getSearchGroups(self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="fep-title">(.*?)</div>')[0]), r"(\d+)")[0]
                if not url or not episode:
                    continue
                sub = self.cm.ph.getSearchGroups(item, r'(?s)class="fep-sub">(.*?)</div>')[0]
                name = self.cleanHtmlStr(sub.split('class="sep"')[0].rsplit("<span", 1)[0] if 'class="sep"' in sub else sub)
                aired = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="fep-date">(.*?)</span>')[0])
                if normalize:
                    title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
                else:
                    title = "%s - %s. Sezon %s. Bölüm" % (sTitle, season, episode)
                if name and not re.match(r"^(?:Episode|Bölüm)\s*\d+$", name):
                    title = "%s - %s" % (title, name)
                params = stripPagerKeys(dict(cItem))
                params.update({"good_for_fav": True, "category": "episode", "title": title, "url": url, "season": season, "episode": episode,
                               "meta_season": season, "meta_episode": episode, "desc": " | ".join(x for x in (self.cleanHtmlStr(sub), aired) if x)})
                self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("SetFilmizle.getLinksForVideo [%s]" % cItem)
        pageUrl = self._siteUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        urltab = []
        for tag, label in re.findall(r'(?s)(<button[^>]+data-player-name="[^"]*"[^>]*>)(.*?)</button>', data):
            playerName = self.cm.ph.getSearchGroups(tag, r'data-player-name="([^"]*)"')[0]
            partKey = self.cm.ph.getSearchGroups(tag, r'data-part-key="([^"]*)"')[0]
            name = " - ".join(x for x in (self.cleanHtmlStr(label) or playerName, partKey) if x)
            meta = {"Referer": pageUrl, "player_name": playerName, "part_key": partKey}
            urltab.append({"name": name, "url": strwithmeta(pageUrl + "#%s-%s" % (playerName, partKey), meta), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        ld = self._ldJson(data)
        if cItem.get("category") == "episode":
            metaQuery = sidecarMetaQuery("tv", cItem.get("meta_title", "") or cItem.get("s_title", ""), season=cItem.get("meta_season", ""), episode=cItem.get("meta_episode", ""))
        else:
            metaQuery = sidecarMetaQuery("movie", cItem.get("meta_title", ""), cItem.get("meta_year", ""), self._imdbId(data))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(ld.get("description", "")) or cItem.get("desc", ""), metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("SetFilmizle.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        meta = videoUrl.meta
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        pageUrl = meta.get("Referer") or videoUrl.split("#")[0]
        # the page again: the nonce of the ajax call belongs to this session
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        nonce = self.cm.ph.getSearchGroups(data, r'video:\s*"([0-9a-f]+)"')[0]
        postId = self.cm.ph.getSearchGroups(data, r'data-post-id="(\d+)"')[0]
        ajaxUrl = self.cm.ph.getSearchGroups(data, r'STF_AJAX\s*=\s*\{url:\s*"([^"]+)"')[0] or self.MAIN_URL + "wp-admin/admin-ajax.php"
        if not nonce or not postId:
            printDBG("SetFilmizle.getVideoLinks no nonce / post id")
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=pageUrl, Accept="application/json, */*")
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        post = {"action": "get_video_url", "nonce": nonce, "post_id": postId, "player_name": meta.get("player_name", ""), "part_key": meta.get("part_key", "")}
        sts, data = self.getPage(ajaxUrl.replace("\\/", "/"), params, post)
        if not sts:
            return []
        try:
            stream = (_jsonLoads(data).get("data") or {}).get("stream") or {}
        except Exception:
            printExc()
            stream = {}
        url = stream.get("url", "")
        printDBG("SetFilmizle.getVideoLinks stream type[%s] provider[%s] url[%s]" % (stream.get("type"), stream.get("provider"), url))
        if not self.cm.isValidUrl(url):
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        if self.up.checkHostSupport(url) != 1:
            SetIPTVPlayerLastHostError(_("Hosting \"%s\" not supported.") % self.up.getHostName(url))
            return []
        # "bridge" = the SetPlay page (setplay.sbs -> fastplay.mom, urlparser): it wants the title page as Referer
        referer = pageUrl if stream.get("type") == "bridge" else self.MAIN_URL
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(url, {"Referer": referer})), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _ldJson(self, data):
        # the Movie / TVSeries / TVEpisode object of the page's ld+json
        for block in re.findall(r'(?s)<script type="application/ld\+json"[^>]*>(.*?)</script>', data):
            try:
                obj = _jsonLoads(block)
            except Exception:
                continue
            objs = obj.get("@graph", [obj]) if isinstance(obj, dict) else (obj if isinstance(obj, list) else [])
            for item in objs:
                if isinstance(item, dict) and item.get("@type") in ("Movie", "TVSeries", "TVEpisode"):
                    return item
        return {}

    def _imdbId(self, data):
        return self.cm.ph.getSearchGroups(data, r'class="fbox-imdb" href="https?://(?:www\.)?imdb\.com/title/(tt\d+)')[0]

    def getArticleContent(self, cItem):
        printDBG("SetFilmizle.getArticleContent [%s]" % cItem)
        info = {}
        icon = ""
        mediaType = "tv" if cItem.get("category") in ("sf_series", "sf_season", "episode") else "movie"
        title = cItem.get("meta_title", "") or cItem.get("s_title", "")
        year = cItem.get("meta_year", "")
        text = ""
        imdb = ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            ld = self._ldJson(data)
            text = self.cleanHtmlStr(ld.get("description", ""))
            imdb = self._imdbId(data)
            altTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="fbox-alt">(.*?)</span>')[0])
            if altTitle and altTitle.lower() != title.lower():
                info["original_title"] = altTitle
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
            year = year or self.cm.ph.getSearchGroups(str(ld.get("datePublished", "")), r"(\d{4})")[0]
            if isinstance(ld.get("image"), str):
                icon = ld["image"]
        if year:
            info["year"] = year
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and info.get("original_title"):
                meta = getMeta(mediaType, info["original_title"], year)
            if not meta:
                meta = getItemMeta(dict(cItem, meta_type=mediaType, meta_title=title, meta_year=year))
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
        elif category == "sf_series":
            self.listSeasons(self.currItem)
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
        CHostBase.__init__(self, SetFilmizle(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("setfilmizle")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("video", "episode", "sf_series", "sf_season")
