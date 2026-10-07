# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - DramaQueen.pl: Asian dramas and films with Polish subtitles (fansub group).
#   The site's pages sit behind a login wall, its WordPress REST API (wp-json/wp/v2) is public: title lists
#   per country (Korean / Japanese / other dramas and films) newest first, recently updated, A-Z, genres
#   (tags), title search; a drama page carries its episodes as toggle sections with "DQ-Player" links
#   (Bunny Stream iframe.mediadelivery.net, resolved here to its HLS playlist) and, on old pages, links to
#   third-party hosters (urlparser). Watched flag, downloaded flag, name normalisation, sidecar, moviemeta
#   INFO (combined with the site's Polish description and details), favourites.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://www.dramaqueen.pl/"


class DramaQueenPL(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a favourite and opens it again
    FAV_FIELDS = ("name", "category", "type", "url", "page_id", "s_title", "icon", "meta_type", "meta_title", "meta_year", "season", "ep_num")

    # WordPress page ids of the title lists (drama/koreanska, drama/japonska, drama/pozostale, film/...)
    DRAMA_PARENTS = ((108288, _("Korean dramas")), (19, _("Japanese dramas")), (94, _("Other dramas (Chinese, Thai, ...)")))
    FILM_PARENTS = ((29, _("Korean films")), (27, _("Japanese films")), (96, _("Other films")))
    PER_PAGE = 30
    # site field label -> INFO field
    INFO_FIELDS = (("Gatunki", "genres"), ("Liczba odcinków", "episodes"), ("Nadawca", "station"), ("Emisja", "broadcast"),
                   ("Czas trwania", "duration"), ("Produkcja", "country"), ("Projekt grupy", "source"), ("Tłumaczenie", "translation"))

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "DramaQueen.pl", "cookie": "dramaqueenpl.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.API_URL = self.getFullUrl("wp-json/wp/v2/")
        self.DEFAULT_ICON_URL = "https://www.dramaqueen.pl/wp-content/uploads/2021/03/logopng.png"
        self.FILM_IDS = set([x[0] for x in self.FILM_PARENTS])
        self.ALL_PARENTS = ",".join([str(x[0]) for x in self.DRAMA_PARENTS + self.FILM_PARENTS])
        self.MENU = [{"category": "list_titles", "title": _("Latest updates"), "f_parent": self.ALL_PARENTS, "f_order": "modified"},
                     {"category": "sub_menu", "title": _("Drama"), "f_kind": "drama"},
                     {"category": "sub_menu", "title": _("Films"), "f_kind": "film"},
                     {"category": "genres", "title": _("Genres")},
                     {"category": "list_titles", "title": _("All titles A-Z"), "f_parent": self.ALL_PARENTS, "f_order": "title"}] + self.searchItems()
        self.pageCache = {}
        self.genres = None

        self.watchedHelper = IPTVWatchedHelper("dramaqueen")
        self.wfInitFolderCache()

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if not url:
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            if cItem.get("category", "") == "series":
                return "series:%s" % url
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "") in ("series", "movie", "episode"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _api(self, path):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"]["Accept"] = "application/json"
        sts, data = self.getPage(self.API_URL + path, params)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _text(self, html):
        return self.cleanHtmlStr(ensure_str(html or ""))

    @staticmethod
    def _seasonNum(title):
        for pattern in (r"(\d+)(?:st|nd|rd|th)\s+Season", r"Season\s+(\d+)"):
            m = re.search(pattern, title, re.I)
            if m:
                return int(m.group(1))
        return 1

    @staticmethod
    def _metaTitle(title):
        title = re.sub(r"\s*(?:\(\d{4}\)|\(SP\)|\d+(?:st|nd|rd|th)\s+Season|Season\s+\d+)\s*$", "", title, flags=re.I)
        return title.strip(" -:")

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year and ("(%s)" % year) not in title:
            return "%s (%s)" % (title, year)
        return title

    def _titleParams(self, pageId, url, title, icon, isMovie, year="", desc=""):
        params = {"good_for_fav": True, "url": url, "page_id": pageId, "s_title": title, "icon": icon, "desc": desc,
                  "meta_type": "movie" if isMovie else "tv", "meta_title": self._metaTitle(title), "meta_year": year}
        if isMovie:
            params.update({"category": "movie", "title": self._movieTitle(title, year)})
        else:
            params.update({"category": "series", "title": title})
        return params

    def _icons(self, mediaIds):
        icons = {}
        mediaIds = [str(x) for x in mediaIds if x]
        if not mediaIds:
            return icons
        data = self._api("media?include=%s&per_page=%d&_fields=id,source_url" % (",".join(mediaIds), len(mediaIds)))
        for item in data if isinstance(data, list) else []:
            try:
                icons[item["id"]] = ensure_str(item.get("source_url", "") or "")
            except Exception:
                printExc()
        return icons

    ###################################################
    # lists
    ###################################################
    def listSubMenu(self, cItem):
        printDBG("DramaQueenPL.listSubMenu")
        parents = self.DRAMA_PARENTS if cItem.get("f_kind") == "drama" else self.FILM_PARENTS
        for parentId, title in parents:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_titles", "title": title, "f_parent": str(parentId), "f_order": "date"})
            self.addDir(params)

    def listGenres(self, cItem):
        printDBG("DramaQueenPL.listGenres")
        if self.genres is None:
            data = self._api("tags?per_page=100&orderby=name&order=asc&hide_empty=true&_fields=id,name,count")
            if not isinstance(data, list):
                return
            self.genres = []
            for item in data:
                try:
                    if int(item.get("count", 0) or 0) > 0:
                        self.genres.append((item["id"], self._text(item.get("name", ""))))
                except Exception:
                    printExc()
        for tagId, name in self.genres:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_titles", "title": name, "f_parent": self.ALL_PARENTS, "f_order": "date", "f_tag": tagId})
            self.addDir(params)

    def listTitles(self, cItem):
        printDBG("DramaQueenPL.listTitles [%s]" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except Exception:
            page = 1
        order = cItem.get("f_order", "date")
        query = "pages?_envelope&parent=%s&per_page=%d&page=%d&orderby=%s&order=%s&_fields=id,link,title,featured_media,parent" % (
            cItem.get("f_parent", self.ALL_PARENTS), self.PER_PAGE, page, order, "asc" if order == "title" else "desc")
        if cItem.get("f_tag"):
            query += "&tags=%s" % cItem["f_tag"]
        if cItem.get("f_search"):
            query += "&search=%s&search_columns=post_title" % urllib_quote(cItem["f_search"], safe="")
        data = self._api(query)
        if not isinstance(data, dict) or not isinstance(data.get("body"), list):
            return
        items = data["body"]
        try:
            totalPages = int((data.get("headers") or {}).get("X-WP-TotalPages", 0) or 0)
        except Exception:
            totalPages = 0
        icons = self._icons([item.get("featured_media", 0) for item in items])
        for item in items:
            try:
                url = ensure_str(item.get("link", ""))
                title = self._text(item.get("title", {}).get("rendered", ""))
                if not url or not title or title == "#":
                    continue
                isMovie = item.get("parent", 0) in self.FILM_IDS
                params = self._titleParams(item["id"], url, title, icons.get(item.get("featured_media", 0), ""), isMovie)
                if isMovie:
                    self.addVideo(params)
                else:
                    self.addDir(params)
            except Exception:
                printExc()
        # the list is read from the f_* filters + page; the url only carries the page for "Jump"
        addPagingItems(self, cItem, page, bool(items) and page < totalPages, totalPages, "%s#page={page}" % (self.API_URL + query.split("&page=", 1)[0]))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("DramaQueenPL.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_titles", "f_parent": self.ALL_PARENTS, "f_order": "title", "f_search": searchPattern.strip()})
        self.listTitles(cItem)

    ###################################################
    # title page
    ###################################################
    def _getTitlePage(self, cItem):
        # parsed title page (cached per session) or None
        pageId = cItem.get("page_id", "")
        url = cItem.get("url", "").split("#", 1)[0]
        key = pageId or url
        if key in self.pageCache:
            return self.pageCache[key]
        fields = "_fields=id,link,title,content,featured_media,parent"
        if pageId:
            data = self._api("pages/%s?%s" % (pageId, fields))
        else:
            slug = url.rstrip("/").rsplit("/", 1)[-1]
            data = self._api("pages?slug=%s&%s" % (urllib_quote(slug, safe=""), fields))
            if isinstance(data, list):
                data = ([x for x in data if ensure_str(x.get("link", "")) == url] or data or [None])[0]
        if not isinstance(data, dict) or "content" not in data:
            return None
        html = re.sub(r"<style.*?</style>", "", ensure_str(data["content"].get("rendered", "")), flags=re.S)
        ret = {"id": data.get("id", pageId), "url": ensure_str(data.get("link", "")) or url,
               "title": self._text(data.get("title", {}).get("rendered", "")), "is_movie": data.get("parent", 0) in self.FILM_IDS}
        ret["icon"] = self._icons([data.get("featured_media", 0)]).get(data.get("featured_media", 0), "")
        # description: the first text block that is not the details box
        ret["desc"] = ""
        info = {}
        for block in re.findall(r"class='avia_textblock[^']*'[^>]*>(.*?)</div></section>", html, re.S):
            if "<strong>" in block and ("Gatunki" in block or "Emisja" in block):
                for line in re.split(r"<br\s*/?>|</p>", block):
                    line = self._text(line)
                    for label, field in self.INFO_FIELDS:
                        if line.startswith(label + ":"):
                            value = line[len(label) + 1:].strip().replace(" ,", ",")
                            if value:
                                info[field] = value
                continue
            text = self._text(block.replace("</p>", "[/br]")).replace("[/br]", "\n").strip()
            if not ret["desc"] and len(text) > 60 and "login" not in text:
                ret["desc"] = text
        ret["info"] = info
        ret["year"] = self.cm.ph.getSearchGroups(info.get("broadcast", ""), r"((?:19|20)\d\d)")[0]
        # episodes / film: toggle sections with the player buttons
        episodes = []
        for label, body in re.findall(r'class="single_toggle"[^>]*>\s*<p[^>]+data-title="([^"]*)"(.*?)</section>', html, re.S):
            label = self._text(label)
            links = []
            for link, name in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', body, re.S) + re.findall(r'<iframe[^>]+src="([^"]+)"()', body):
                link = ensure_str(link).replace("&#038;", "&").replace("&amp;", "&").strip()
                if link.startswith("//"):
                    link = "https:" + link
                if not self.cm.isValidUrl(link) or "dramaqueen.pl" in link or link in [x[0] for x in links]:
                    continue
                links.append((link, self._text(name)))
            if not links:
                continue
            num = self.cm.ph.getSearchGroups(label, r"(\d+)")[0]
            playable = len([x for x in links if "mediadelivery.net/" in x[0] or self.up.checkHostSupport(x[0]) == 1])
            episodes.append({"label": label, "num": num, "links": links, "playable": playable})
        ret["episodes"] = episodes
        if len(self.pageCache) > 20:
            self.pageCache = {}
        self.pageCache[key] = ret
        return ret

    def _episodeTitle(self, sTitle, ep):
        if IsMediaNamingNormalized() and ep["num"]:
            return "%s - %s" % (sTitle, formatSxxExx(self._seasonNum(sTitle), ep["num"]))
        return "%s - %s" % (sTitle, ep["label"])

    def listEpisodes(self, cItem):
        printDBG("DramaQueenPL.listEpisodes [%s]" % cItem.get("url", ""))
        page = self._getTitlePage(cItem)
        if page is None:
            return
        if not page["episodes"]:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
            return
        # episodes only linked on hosters that closed down years ago are left out
        episodes = [ep for ep in page["episodes"] if ep["playable"]]
        if not episodes:
            SetIPTVPlayerLastHostError(_("This video is only on hosters E2iPlayer cannot play."))
            return
        sTitle = page["title"] or cItem.get("s_title", "")
        icon = cItem.get("icon", "") or page["icon"]
        season = self._seasonNum(sTitle)
        for ep in episodes:
            epKey = ep["num"] or ep["label"]
            params = {"good_for_fav": True, "category": "episode", "url": "%s#ep%s" % (page["url"], urllib_quote(epKey, safe="")),
                      "page_id": page["id"], "s_title": sTitle, "icon": icon, "title": self._episodeTitle(sTitle, ep),
                      "season": season, "ep_num": epKey, "desc": page["desc"],
                      "meta_type": "tv", "meta_title": self._metaTitle(sTitle), "meta_year": page["year"]}
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("DramaQueenPL.getLinksForVideo [%s]" % cItem)
        page = self._getTitlePage(cItem)
        if page is None:
            return []
        episodes = page["episodes"]
        if cItem.get("category") == "episode":
            epKey = cItem.get("ep_num", "")
            episodes = [ep for ep in episodes if (ep["num"] or ep["label"]) == epKey]
        urltab = []
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        for ep in episodes:
            for link, name in ep["links"]:
                if "mediadelivery.net/" in link:
                    name = name or "DQ-Player"
                elif self.up.checkHostSupport(link) != 1:
                    printDBG("DramaQueenPL: hoster not supported by urlparser [%s]" % link)
                    continue
                else:
                    name = name or self.up.getHostName(link)
                if len(episodes) > 1:
                    name = "%s - %s" % (ep["label"], name)
                urltab.append({"name": name, "url": strwithmeta(link, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            # old pages only link to hosters that closed down years ago (openload, streamango, fembed, ...)
            SetIPTVPlayerLastHostError(_("This video is only on hosters E2iPlayer cannot play."))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), page["desc"]))

    def _getBunnyLinks(self, videoUrl):
        # DQ-Player = Bunny Stream embed; plays only with the site as referer, the HLS wants the embed host
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"]["Referer"] = strwithmeta(videoUrl).meta.get("Referer", self.MAIN_URL)
        sts, data = self.getPage(videoUrl.strip(), params)
        if not sts:
            return []
        hlsUrl = self.cm.ph.getSearchGroups(data, r'''(https?://[^"'\s<>]+/playlist\.m3u8[^"'\s<>]*)''')[0]
        if not hlsUrl:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        hlsUrl = strwithmeta(hlsUrl.replace("&amp;", "&"), {"User-Agent": self.HEADER["User-Agent"], "Referer": "https://iframe.mediadelivery.net/",
                                                            "Origin": "https://iframe.mediadelivery.net"})
        return getDirectM3U8Playlist(hlsUrl, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)

    def getVideoLinks(self, videoUrl):
        printDBG("DramaQueenPL.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if "mediadelivery.net/" in videoUrl:
            return decorateResolvedLinkItems(self._getBunnyLinks(videoUrl), sidecar)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("DramaQueenPL.getArticleContent [%s]" % cItem.get("url", ""))
        otherInfo = {}
        title = cItem.get("s_title", "") or cItem.get("title", "")
        text = ""
        icon = cItem.get("icon", "")
        page = self._getTitlePage(cItem)
        year = cItem.get("meta_year", "")
        if page:
            title = page["title"] or title
            text = page["desc"]
            icon = icon or page["icon"]
            year = year or page["year"]
            otherInfo.update(page["info"])
            if year:
                otherInfo["year"] = year
        meta = {}
        if cItem.get("meta_title"):
            meta = getMeta(cItem.get("meta_type", "tv"), cItem["meta_title"], year)
        sameAs = {"genre": "genres"}
        for key, value in meta.get("info", {}).items():
            if key not in otherInfo and sameAs.get(key) not in otherInfo:
                otherInfo[key] = value
        if not text:
            text = meta.get("plot", "") or cItem.get("desc", "")
        if not icon:
            icon = meta.get("poster", "")
        if cItem.get("category") in ("episode", "movie"):
            title = cItem.get("title", title)
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("DramaQueenPL.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "sub_menu":
            self.listSubMenu(self.currItem)
        elif category == "genres":
            self.listGenres(self.currItem)
        elif category == "list_titles":
            self.listTitles(self.currItem)
        elif category == "series":
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
        CHostBase.__init__(self, DramaQueenPL(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("dramaqueen")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("series", "movie", "episode")
