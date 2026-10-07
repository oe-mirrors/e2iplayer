# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - new host for uaserials.my (uaserials.pro), Ukrainian dubbed series, films,
#   cartoons, anime and dramas (DLE site): category / series genre / year lists with paging, search, title
#   page (IMDb id, year, genres, cast, description). Playback through the HDVB-UA player (hdvbua.pro/embed):
#   films = one HLS url, series = Playerjs JSON season -> translation -> episode, every translation of an
#   episode is one link (with its subtitles). The player refuses titles outside its licence area
#   ("Контент недоступний") - reported as a message. Watched flag, downloaded flag, name normalisation,
#   sidecar, moviemeta INFO (IMDb id from the page), favourites.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
import re
import time
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://uaserials.my/"


class UASerials(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a favourite and opens it again
    FAV_FIELDS = ("name", "category", "type", "url", "page_url", "season", "episode", "s_title", "icon", "meta_type", "meta_title", "meta_year", "ep_key")

    GENRES = (("action", "Бойовик"), ("biography", "Біографічний"), ("war", "Військовий"), ("western", "Вестерн"),
              ("detective", "Детектив"), ("documentary", "Документальний"), ("drama", "Драма"), ("horror", "Жахи"),
              ("history", "Історичний"), ("comedy", "Комедія"), ("crime", "Кримінал"), ("melodrama", "Мелодрама"),
              ("music", "Музичний"), ("adventure", "Пригоди"), ("reality-show", "Реаліті-шоу"), ("family", "Сімейний"),
              ("sport", "Спортивний"), ("subtitles", "Субтитровані"), ("thriller", "Трилер"), ("fantastic", "Фантастика"),
              ("fantasy", "Фентезі"))

    # a short-item label with one of these words marks a series
    SERIES_LABEL = re.compile("[Сс]езон|[Сс]ері[яйї]")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "UASerials", "cookie": "uaserials.cookie"})
        self.USER_AGENT = self.cm.getDefaultUserAgent('chrome')
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                       "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.6"}
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("templates/uaserials2020/images/favicon.png")
        self.MENU = [{"category": "list_items", "title": _("Series"), "url": self.getFullUrl("seriess/")},
                     {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("filmss/")},
                     {"category": "list_items", "title": _("Animated series"), "url": self.getFullUrl("cartoons/")},
                     {"category": "list_items", "title": _("Animated movies"), "url": self.getFullUrl("fcartoon/")},
                     {"category": "list_items", "title": _("Anime"), "url": self.getFullUrl("anime/")},
                     {"category": "list_items", "title": _("Dramas (Asian)"), "url": self.getFullUrl("doramy/")},
                     {"category": "genres", "title": _("Series genres")},
                     {"category": "years", "title": _("Year")}] + self.searchItems()
        self.pageCache = {}
        self.playerCache = {}

        self.watchedHelper = IPTVWatchedHelper("uaserials")
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
            if cItem.get("category", "") in ("series", "season"):
                return "folder:%s" % url
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "") in ("series", "season", "movie", "episode"):
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

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year and ("(%s)" % year) not in title:
            return "%s (%s)" % (title, year)
        return title

    def _episodeTitle(self, sTitle, season, episode, label):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (sTitle, formatSxxExx(season or 1, episode))
        return "%s - %s" % (sTitle, label)

    @staticmethod
    def _num(text):
        m = re.search(r"(\d+)", text or "")
        return int(m.group(1)) if m else 0

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("UASerials.listItems [%s]" % cItem.get("url", ""))
        page = int(cItem.get("page", 1) or 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        post = None
        if cItem.get("search"):
            post = {"do": "search", "subaction": "search", "story": cItem["search"], "search_start": str(page), "full_search": "0", "result_from": str((page - 1) * 18 + 1)}
            url = self.getFullUrl("index.php?do=search")
            # POST search: the template only serves "Jump" (the page goes in the POST data)
            tpl = baseUrl.split("#")[0] + "#page={page}"
        else:
            tpl = baseUrl + "page/{page}/"
            url = baseUrl if page <= 1 else tpl.format(page=page)
        sts, data = self.getPage(url, None, post)
        if not sts:
            return
        nav = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "navigation"), ("</div", ">"), False)[1]
        seen = set()
        for item in re.split(r'<div\s+class="short-item', data)[1:]:
            item = item.split('<div class="short-item')[0]
            url = self.cm.ph.getSearchGroups(item, r'href="(https?://[^"]+/\d+-[^"]+\.html)"')[0]
            if not url or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "th-title truncate"), ("</div", ">"), False)[1])
            oname = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "th-title-oname"), ("</div", ">"), False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            labels = [self.cleanHtmlStr(x) for x in re.findall(r'class="short-label[^"]*"[^>]*>(.*?)</div>', item, re.S)]
            labels = [x for x in labels if x]
            isSeries = bool(self.SERIES_LABEL.search(" ".join(labels)))
            desc = " | ".join([x for x in [oname] + labels if x])
            params = {"good_for_fav": True, "url": url, "page_url": url, "s_title": title, "icon": self.getFullIconUrl(icon), "desc": desc,
                      "meta_title": oname or title, "meta_year": ""}
            if isSeries:
                params.update({"category": "series", "title": title, "meta_type": "tv"})
                self.addDir(params)
            else:
                params.update({"category": "movie", "title": title, "meta_type": "movie"})
                self.addVideo(params)
        if seen:
            if cItem.get("search"):
                pages = [int(n) for n in re.findall(r"list_submit\((\d+)\)", data)]
            else:
                pages = [int(n) for n in re.findall(r'href="[^"]*/page/(\d+)/"', nav)]
            addPagingItems(self, dict(cItem, base_url=baseUrl), page, (page + 1) in pages, max(pages + [page]), tpl)

    def listGenres(self, cItem):
        for slug, title in self.GENRES:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl("seriess/%s/" % slug)})
            self.addDir(params)

    def listYears(self, cItem):
        for year in range(time.localtime()[0], 1969, -1):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": str(year), "url": self.getFullUrl("year/%d/" % year)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("UASerials.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("index.php?do=search&subaction=search&story=%s" % urllib_quote(searchPattern.strip())),
                      "search": searchPattern.strip()})
        self.listItems(cItem)

    ###################################################
    # title page + HDVB player
    ###################################################
    def _getTitlePage(self, url):
        if url in self.pageCache:
            return self.pageCache[url]
        sts, data = self.getPage(url)
        if not sts:
            return None
        ret = {"url": url}
        ret["title"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<h1", ">", "short-title"), ("</h1", ">"), False)[1])
        ret["oname"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", 'class="oname"'), ("</div", ">"), False)[1])
        ret["imdb"] = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
        ret["imdb_rating"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'short-rate-imdb[^>]*>\s*<span>([^<]+)</span>')[0])
        icon = self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "fimg"), ("</div", ">"), False)[1], r'src="([^"]+)"')[0]
        ret["icon"] = self.getFullIconUrl(icon) if icon else ""
        info = {}
        for name, value in re.findall(r"<li>\s*<span>([^<]+):</span>(.*?)</li>", data, re.S):
            info[self.cleanHtmlStr(name)] = self.cleanHtmlStr(value)
        ret["year"] = self.cm.ph.getSearchGroups(info.get("Рік", ""), r"(\d{4})")[0]
        ret["genres"] = info.get("Жанр", "")
        ret["country"] = info.get("Країна", "")
        ret["translation"] = info.get("Переклад", "")
        ret["director"] = info.get("Режисер", "")
        ret["actors"] = info.get("Актори", "")
        desc = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "full-text"), ("</div", ">"), False)[1]
        ret["desc"] = self.cleanHtmlStr(desc.replace("</p>", "[/br]")).replace("[/br]", "\n").strip()
        embed = ""
        for src in re.findall(r'<iframe[^>]+(?:data-src|src)="([^"]+)"', data):
            src = "https:" + src if src.startswith("//") else src
            if ("/embed/" in src or "/vid/" in src) and "youtube" not in src:
                embed = src
                break
        ret["embed"] = embed
        self.pageCache[url] = ret
        return ret

    def _getPlayer(self, page):
        # {"blocked": bool, "movie": {"hls", "subs"}, "serial": [season dicts]} for the HDVB player of a title page
        embed = page.get("embed", "")
        if not embed:
            return {}
        if embed in self.playerCache:
            return self.playerCache[embed]
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"]["Referer"] = page["url"]
        sts, data = self.getPage(embed, params)
        if not sts:
            return {}
        ret = {"embed": embed, "blocked": False}
        if "file:" not in data:
            ret["blocked"] = "недоступн" in data
            self.playerCache[embed] = ret
            return ret
        if re.search(r"file:\s*'\[", data):
            m = re.search(r"file:\s*'(\[.*?\])'\s*[,}\n]", data, re.S)
            raw = m.group(1) if m else "[]"
            try:
                items = json_loads(raw)
            except Exception:
                printExc()
                items = []
            if items and isinstance(items[0], dict) and "folder" not in items[0] and items[0].get("file"):
                # a film with several translations
                ret["movie_voices"] = [{"title": self.cleanHtmlStr(ensure_str(x.get("title", ""))), "file": ensure_str(x.get("file", "")),
                                        "subs": ensure_str(x.get("subtitle", "") or "")} for x in items if isinstance(x, dict) and x.get("file")]
            else:
                ret["serial"] = items
        else:
            hls = self.cm.ph.getSearchGroups(data, r'''file:\s*["'](https?://[^"']+)["']''')[0]
            if hls:
                ret["movie_voices"] = [{"title": "", "file": hls, "subs": self.cm.ph.getSearchGroups(data, r'''subtitle:\s*["']([^"']*)["']''')[0]}]
        self.playerCache[embed] = ret
        return ret

    def _seasons(self, player):
        # [(seasonNum, seasonTitle, {episodeNum: {"label", "voices": [(voice, file, subs)]}})]
        seasons = []
        for season in player.get("serial") or []:
            if not isinstance(season, dict):
                continue
            sTitle = self.cleanHtmlStr(ensure_str(season.get("title", "")))
            folder = season.get("folder") or []
            episodes = {}
            order = []
            # Playerjs: season -> translation -> episode (sometimes season -> episode directly)
            for voice in folder:
                if not isinstance(voice, dict):
                    continue
                vTitle = self.cleanHtmlStr(ensure_str(voice.get("title", "")))
                direct = not isinstance(voice.get("folder"), list)
                epList = [voice] if direct else voice["folder"]
                for ep in epList:
                    if not isinstance(ep, dict) or not ep.get("file"):
                        continue
                    label = self.cleanHtmlStr(ensure_str(ep.get("title", "")))
                    num = self._num(label)
                    key = num or label
                    if key not in episodes:
                        episodes[key] = {"label": label, "num": num, "voices": []}
                        order.append(key)
                    episodes[key]["voices"].append(("" if direct else vTitle, ensure_str(ep["file"]), ensure_str(ep.get("subtitle", "") or "")))
            if order:
                seasons.append((self._num(sTitle) or (len(seasons) + 1), sTitle, [episodes[k] for k in order]))
        return seasons

    def _reportUnavailable(self, player):
        if player.get("blocked"):
            SetIPTVPlayerLastHostError(_("The video player of this site (hdvbua.pro) does not offer this title in your country (licence area, mainly Ukraine)."))
        else:
            SetIPTVPlayerLastHostError(_("No stream available"))

    def listSeries(self, cItem):
        printDBG("UASerials.listSeries [%s]" % cItem.get("url", ""))
        page = self._getTitlePage(cItem.get("page_url", cItem["url"]))
        if page is None:
            return
        player = self._getPlayer(page)
        seasons = self._seasons(player)
        sTitle = page["title"] or cItem.get("s_title", "")
        if not seasons:
            if player.get("movie_voices"):
                params = dict(cItem)
                params.update({"category": "movie", "title": self._movieTitle(sTitle, page["year"]), "meta_type": "movie"})
                self.addVideo(params)
                return
            self._reportUnavailable(player)
            return
        if len(seasons) == 1:
            self._addEpisodes(cItem, page, seasons[0])
            return
        for season in seasons:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "season", "title": "%s - %s" % (sTitle, season[1]), "season": season[0],
                           "url": "%s#s%d" % (page["url"], season[0]), "page_url": page["url"], "meta_year": page["year"]})
            self.addDir(params)

    def listSeason(self, cItem):
        page = self._getTitlePage(cItem["page_url"])
        if page is None:
            return
        for season in self._seasons(self._getPlayer(page)):
            if season[0] == cItem.get("season"):
                self._addEpisodes(cItem, page, season)
                return

    def _addEpisodes(self, cItem, page, season):
        sTitle = page["title"] or cItem.get("s_title", "")
        for ep in season[2]:
            label = "%s - %s" % (season[1], ep["label"]) if season[1] else ep["label"]
            params = {"good_for_fav": True, "category": "episode", "url": "%s#s%de%s" % (page["url"], season[0], ep["num"] or ep["label"]), "page_url": page["url"],
                      "s_title": sTitle, "icon": page["icon"] or cItem.get("icon", ""), "season": season[0], "episode": ep["num"], "ep_key": str(ep["num"] or ep["label"]),
                      "title": self._episodeTitle(sTitle, season[0], ep["num"], label), "desc": " | ".join([x for x in (page["oname"], label) if x]),
                      "meta_type": "tv", "meta_title": page["oname"] or sTitle, "meta_year": page["year"]}
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def _subTracks(self, subs):
        tracks = []
        for label, url in re.findall(r"\[([^\]]+)\](https?://[^,\s]+)", subs or ""):
            lang = label.lower()
            if re.search("[Уу]кр|ukr", lang):
                code = "uk"
            elif re.search("[Аа]нгл|eng", lang):
                code = "en"
            elif re.search("[Рр]ос|rus", lang):
                code = "ru"
            else:
                code = re.sub("[^a-z]", "", lang)[:2] or "und"
            tracks.append({"title": label, "url": url, "lang": code, "format": "vtt" if ".vtt" in url else "srt"})
        return tracks

    def _link(self, name, url, subs, referer):
        meta = {"User-Agent": self.USER_AGENT, "Referer": referer}
        if ".m3u8" in url:
            meta["iptv_proto"] = "m3u8"
        tracks = self._subTracks(subs)
        if tracks:
            meta["external_sub_tracks"] = tracks
        return {"name": name or "HDVB", "url": strwithmeta(url, meta), "need_resolve": 0}

    def getLinksForVideo(self, cItem):
        printDBG("UASerials.getLinksForVideo [%s]" % cItem)
        page = self._getTitlePage(cItem.get("page_url", cItem.get("url", "")))
        if page is None:
            return []
        player = self._getPlayer(page)
        referer = player.get("embed", self.MAIN_URL)
        urltab = []
        if cItem.get("category") == "episode":
            for season in self._seasons(player):
                if season[0] != cItem.get("season"):
                    continue
                for ep in season[2]:
                    if str(ep["num"] or ep["label"]) == str(cItem.get("ep_key", "")):
                        for voice, url, subs in ep["voices"]:
                            urltab.append(self._link(voice, url, subs, referer))
        else:
            for voice in player.get("movie_voices") or []:
                urltab.append(self._link(voice["title"], voice["file"], voice["subs"], referer))
            if not urltab:
                seasons = self._seasons(player)
                if len(seasons) == 1 and len(seasons[0][2]) == 1:
                    for voice, url, subs in seasons[0][2][0]["voices"]:
                        urltab.append(self._link(voice, url, subs, referer))
        if not urltab:
            self._reportUnavailable(player)
            return []
        sidecarTxt = page["desc"] or cItem.get("desc", "")
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("UASerials.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("UASerials.getArticleContent [%s]" % cItem.get("url", ""))
        otherInfo = {}
        title = cItem.get("s_title", "") or cItem.get("title", "")
        text = ""
        icon = cItem.get("icon", "")
        page = self._getTitlePage(cItem.get("page_url", cItem.get("url", "")))
        imdb = ""
        if page:
            title = page["title"] or title
            text = page["desc"]
            icon = page["icon"] or icon
            imdb = page["imdb"]
            for key, field in (("original_title", "oname"), ("year", "year"), ("genres", "genres"), ("country", "country"), ("translation", "translation"),
                               ("director", "director"), ("actors", "actors"), ("imdb_rating", "imdb_rating")):
                if page.get(field):
                    otherInfo[key] = page[field]
        mediaType = cItem.get("meta_type", "movie")
        meta = getMetaByImdbId(mediaType, imdb) if imdb else {}
        if not meta and cItem.get("meta_title"):
            meta = getMeta(mediaType, cItem["meta_title"], (page or {}).get("year", "") or cItem.get("meta_year", ""))
        sameAs = {"genre": "genres", "cast": "actors", "directors": "director"}
        for key, value in meta.get("info", {}).items():
            if key not in otherInfo and sameAs.get(key) not in otherInfo:
                otherInfo[key] = value
        if not text:
            text = meta.get("plot", "") or cItem.get("desc", "")
        if not icon:
            icon = meta.get("poster", "")
        if cItem.get("category") == "episode":
            title = cItem.get("title", title)
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("UASerials.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "genres":
            self.listGenres(self.currItem)
        elif category == "years":
            self.listYears(self.currItem)
        elif category == "series":
            self.listSeries(self.currItem)
        elif category == "season":
            self.listSeason(self.currItem)
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
        CHostBase.__init__(self, UASerials(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("uaserials")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("series", "season", "movie", "episode")
