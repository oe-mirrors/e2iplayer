# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# 07.10.2026 - domain hd-filme.vip (hd-filme.blog redirects there); list cards, genre/year/country menus
#   (new dropdown markup); series pages are one season each ("Show - Staffel 2"): seasons + episodes come
#   from the DeVideoSRC player API (IMDb id of the page, libs/meinecloud.py), the site's own episode list
#   is the fallback; every episode has its own url (page + "#s1e2"); First/Jump/Next paging (lists +
#   search); "Title (Year)" / "Show - SxxExx"; watched flag, favourites, sidecar, downloaded marker;
#   INFO via moviemeta merged with the site's fields.
# 01.10.2026 - domain hd-filme.blog; meinecloud/devideosrc player pages expand via its token API (libs/meinecloud.py)
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.meinecloud import MeineCloud, MAIN_URL as MC_URL, isPlayerUrl
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://hd-filme.vip/"


PAGING_KEYS = ("base_url", "page_tpl")
STAFFEL_RE = re.compile(r"\s*-\s*Staffel\s*(\d+).*$", re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def _pageUrl(url):
    # episode rows: the season page + "#s<season>e<episode>" (own download / favourite / watched key)
    return (url or "").split("#")[0]


class HDFilmeTV(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "HDFilmeTV", "cookie": "HDFilmeTV.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/StoneOffStones/plugin.video.xstream/c88b2a6953febf6e46cf77f891d550a3c2ee5eea/resources/art/sites/hdfilme.png"
        self.MENU = [{"category": "list_items", "title": _("New"), "url": self.getFullUrl("aktuelle-kinofilme-im-kino/")},
                     {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("kinofilme-online/")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serienstream-deutsch/")},
                     {"category": "list_value", "title": _("Genres"), "s": "KATEGORIE"},
                     {"category": "list_value", "title": _("Year"), "s": "JAHRE"},
                     {"category": "list_value", "title": _("Countries"), "s": "LÄNDER"}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("hdfilmetv")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        # /xfsearch/Vereinigte Staaten/ - spaces and umlauts in the menu links
        baseUrl = self.cm.iriToUri(baseUrl).replace(" ", "%20")
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if not url:
                return ""
            category = cItem.get("category", "")
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            if category == "list_seasons":
                return "series:%s" % url
            if category == "list_episodes":
                return "season:%s#s%s" % (url, cItem.get("s_num", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _lastPage(self, data):
        # pager: <a href=".../page/878/">878</a>; search: javascript:list_submit(5)
        nums = [int(a or b) for a, b in re.findall(r"/page/(\d+)/|list_submit\((\d+)\)", data)]
        return max(nums) if nums else 0

    def listItems(self, cItem):
        printDBG("HDFilmeTV.listItems |%s|" % cItem)
        page = int(cItem.get("page", 1) or 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        tpl = cItem.get("page_tpl", "") or (re.sub(r"/page/\d+/?$", "/", baseUrl).rstrip("/").replace("{", "{{").replace("}", "}}") + "/page/{page}/")
        sts, data = self.getPage(baseUrl if page <= 1 else tpl.format(page=page))
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="box-product clearfix', '<div class="clear">'):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, """href=['"]([^'"]+?)['"]""")[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, """title=['"]([^'"]+)['"]""")[0])
            title = re.sub(r"\s+stream$", "", title)
            if not title or url in seen or not self.cm.isValidUrl(url):
                continue
            seen.add(url)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r"""data-src=['"]([^'"]+?\.(?:jpe?g|png|webp))['"]""")[0])
            year = self.cm.ph.getSearchGroups(item, r"fa-calendar-o[^>]*></i>\s*(\d{4})")[0]
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="movie-quality">(.*?)</span>')[0])
            desc = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Quality"), quality)) if value)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "url": url, "icon": icon, "desc": desc, "meta_year": year})
            staffel = STAFFEL_RE.search(title)
            if staffel:
                show = STAFFEL_RE.sub("", title).strip()
                params.update({"category": "list_seasons", "title": title, "s_title": show, "s_num": int(staffel.group(1)), "meta_type": "tv", "meta_title": show})
                self.addDir(params)
            else:
                params.update({"category": "video", "title": "%s (%s)" % (title, year) if (normalize and year) else title,
                               "s_title": title, "meta_type": "movie", "meta_title": title})
                self.addVideo(params)
        lastPage = self._lastPage(data)
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl, page_tpl=tpl)
        addPagingItems(self, listItem, page, bool(seen) and page < lastPage, lastPage, tpl)

    def _imdb(self, data):
        imdb = self.cm.ph.getSearchGroups(data, r"rawImdb\s*=\s*'([^'\[]+)'")[0].strip()
        if imdb and not imdb.startswith("tt"):
            imdb = "tt" + imdb
        return imdb or MeineCloud.imdbFromUrl(self.cm.ph.getSearchGroups(data, r'data-link="(https?://[^"]*(?:devideosrc|meinecloud)[^"]*/movie/tt\d+)')[0])

    def _siteEpisodes(self, data):
        # the site's own (DLE) episode list: <li id="serie-1_3"><a href="#">Episoden 3</a> <ul> data-link ... </ul>
        episodes = {}
        for season, episode, block in re.findall(r'(?s)<li id="serie-(\d+)_(\d+)">(.*?)</ul>', COMMENT_RE.sub("", data)):
            links = [x for x in re.findall(r'data-link="([^"]+)"', block) if "/vod/" not in x]
            if links:
                episodes.setdefault(int(season), []).append({"episode": int(episode), "title": "", "desc": "", "url": links[0]})
        return sorted(episodes.items())

    def _seasons(self, cItem):
        # (imdb, [(season, [episode dicts])]) - DeVideoSRC first, the site's list as fallback
        sts, data = self.getPage(_pageUrl(cItem["url"]))
        if not sts:
            return "", []
        imdb = self._imdb(data)
        seasons = MeineCloud(self.cm, self.defaultParams, gettytul()).seriesEpisodes(imdb) if imdb else []
        return imdb, seasons or self._siteEpisodes(data)

    def listSeasons(self, cItem):
        printDBG("HDFilmeTV.listSeasons")
        imdb, seasons = self._seasons(cItem)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        # the page is one season ("Show - Staffel 2") - open it directly when the player knows it
        wanted = cItem.get("s_num")
        if len(seasons) == 1 or wanted in [s for s, _eps in seasons]:
            season = wanted if wanted in [s for s, _eps in seasons] else seasons[0][0]
            self.listEpisodes(dict(cItem, category="list_episodes", s_num=season, imdb=imdb), dict(seasons).get(season, []))
            return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        for season, episodes in seasons:
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            seasonTag = formatSxxExx(season) if IsMediaNamingNormalized() else "%s %d" % (_("Season"), season)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (show, seasonTag), "s_num": season, "imdb": imdb,
                           "desc": "%s: %d" % (_("Episodes"), len(episodes))})
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        printDBG("HDFilmeTV.listEpisodes")
        season = int(cItem.get("s_num", 1) or 1)
        imdb = cItem.get("imdb", "")
        if episodes is None:
            imdb, seasons = self._seasons(cItem)
            episodes = dict(seasons).get(season, [])
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or STAFFEL_RE.sub("", cItem.get("title", ""))
        for ep in sorted(episodes, key=lambda x: x["episode"]):
            name = self.cleanHtmlStr(ep["title"])
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, ep["episode"]))
            else:
                title = " - ".join(x for x in (show, "%s %d" % (_("Episode"), ep["episode"]), name) if x)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "episode", "title": title, "url": "%s#s%de%d" % (_pageUrl(cItem["url"]), season, ep["episode"]),
                           "desc": self.cleanHtmlStr(ep["desc"]) or cItem.get("desc", ""), "ep_desc": self.cleanHtmlStr(ep["desc"]), "s_num": season, "e_num": ep["episode"], "imdb": imdb,
                           "mc_url": ep["url"], "meta_type": "tv", "meta_title": show})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("HDFilmeTV.listValue")
        sts, data = self.getPage(gettytul())
        if not sts:
            return
        block = self.cm.ph.getSearchGroups(data, r'(?s)</i>\s*%s\s*</a>\s*<ul class="modern-dropdown">(.*?)</ul>' % re.escape(cItem["s"]))[0]
        for url, title in re.findall(r'href="([^"]+)"[^>]*>([^<]+)<', block):
            title = self.cleanHtmlStr(title)
            if not title or url.rstrip("/").endswith(("kinofilme-online", "serienstream-deutsch", "aktuelle-kinofilme-im-kino")):
                continue
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HDFilmeTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        story = urllib_quote_plus(searchPattern).replace("{", "{{").replace("}", "}}")
        tpl = self.getFullUrl("index.php?do=search&subaction=search&search_start={page}&story=%s" % story)
        self.listItems(dict(cItem, category="list_items", url=tpl.format(page=1), base_url=tpl.format(page=1), page_tpl=tpl))

    ###################################################
    # links
    ###################################################
    def _link(self, url, referer):
        title = _("Trailer") if "youtube" in url else self.up.getHostName(url).capitalize()
        return {"name": title, "url": strwithmeta(url, {"Referer": referer}), "need_resolve": 1}

    def getLinksForVideo(self, cItem):
        printDBG("HDFilmeTV.getLinksForVideo [%s]" % cItem)
        urltab = []
        mc = MeineCloud(self.cm, self.defaultParams, gettytul())
        if cItem.get("episode") and not cItem.get("e_num"):
            # favourites saved before 07.10.2026: {"title": "Show - Staffel 1 - Episoden 3", "episode": "Episoden 3"}
            num = re.search(r"(\d+)", cItem["episode"])
            staffel = STAFFEL_RE.search(cItem.get("title", ""))
            sts, data = self.getPage(_pageUrl(cItem["url"]))
            cItem = dict(cItem, e_num=int(num.group(1)) if num else 1, s_num=int(staffel.group(1)) if staffel else 1, imdb=self._imdb(data) if sts else "")
        if cItem.get("e_num"):
            imdb, season, episode = cItem.get("imdb", ""), cItem.get("s_num", 1), cItem["e_num"]
            links = (mc.episodeLinks(imdb, season, episode) if imdb else []) or [cItem.get("mc_url", "")]
            for url in links:
                if self.cm.isValidUrl(url) and not isPlayerUrl(url):
                    urltab.append(self._link(url, MC_URL if imdb else gettytul()))
        else:
            sts, data = self.getPage(_pageUrl(cItem["url"]))
            if not sts:
                return []
            for url in re.findall(r'data-link="([^"]+)', COMMENT_RE.sub("", data)):
                url = "https:" + url if url.startswith("//") else url
                if "/vod/" in url or not self.cm.isValidUrl(url):
                    continue
                if isPlayerUrl(url):
                    # the DeVideoSRC player is a mirror list, not a hoster - its hoster embeds
                    urltab.extend(self._link(sub, MC_URL) for sub in mc.movieLinks(MeineCloud.imdbFromUrl(url)) if "/vod/" not in sub)
                elif url not in [str(x["url"]) for x in urltab]:
                    urltab.append(self._link(url, gettytul()))
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, url):
        printDBG("HDFilmeTV.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecarFromUrlMeta(url, IsSidecarEnabled()))
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("HDFilmeTV.getArticleContent [%s]" % cItem)
        otherInfo = {}
        story = ""
        imdb = cItem.get("imdb", "")
        sts, data = self.getPage(_pageUrl(cItem.get("url", "")))
        if sts:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description"\s*content="([^"]+)')[0])
            genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, "(?s)Genres:(.*?)</p>")[0])
            if genre:
                otherInfo["genres"] = genre
            fields = {"country": "(?s)<p>Produktionsland:(.*?)</p>", "duration": 'datetime=".*?">([^<]+)</time>', "actors": "(?s)<p>Mit:(.*?)</p>"}
            for key, pattern in fields.items():
                value = ", ".join(self.cleanHtmlStr(x) for x in re.findall(pattern, data) if self.cleanHtmlStr(x))
                if value:
                    otherInfo[key] = value
            imdb = imdb or self._imdb(data)
        mediaType = cItem.get("meta_type", "") or "movie"
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and cItem.get("meta_title"):
                meta = getMeta(mediaType, cItem["meta_title"], cItem.get("meta_year", ""))
        except Exception:
            printExc()
        info = dict(meta.get("info", {}))
        info.update(otherInfo)
        plot = meta.get("plot", "")
        text = cItem.get("ep_desc", "") or story or plot
        if plot and text != plot and not cItem.get("e_num"):
            text = "%s[/br][/br]%s" % (text, plot) if text else plot
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
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
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
        CHostBase.__init__(self, HDFilmeTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("hdfilmetv")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
