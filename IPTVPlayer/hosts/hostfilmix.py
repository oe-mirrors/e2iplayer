# -*- coding: utf-8 -*-
LAST_MODIFIED = "25.10.2026"
# 25.10.2026 - new host for filmix.gg (Russian / Ukrainian dubbed films, series, cartoons, anime): direct MP4
#   links up to 4K per translation (PlayerJS "#2" data), series from the per-translation playlists.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
###################################################
# FOREIGN import
###################################################
import base64
import re
import time
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://filmix.gg/"


class Filmix(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a favourite and opens it again
    FAV_FIELDS = ("name", "category", "type", "url", "page_url", "season", "episode", "s_title", "icon", "meta_type", "meta_title", "meta_year", "ep_key")

    GENRES = (("animes", "Аниме"), ("biografia", "Биография"), ("boevik", "Боевики"), ("vesterny", "Вестерн"), ("voennyj", "Военный"),
              ("detektivy", "Детектив"), ("detskij", "Детский"), ("for_adults", "Для взрослых"), ("dokumentalenyj", "Документальные"),
              ("drama", "Драмы"), ("istoricheskie", "Исторический"), ("komedia", "Комедии"), ("korotkometragka", "Короткометражка"),
              ("kriminaly", "Криминал"), ("melodrama", "Мелодрамы"), ("mistika", "Мистика"), ("music", "Музыка"), ("muzkl", "Мюзикл"),
              ("engl", "На английском"), ("ukraine", "На украинском"), ("original", "Оригинал"), ("otechestvennye", "Отечественные"),
              ("tvs", "Передачи с ТВ"), ("prikluchenija", "Приключения"), ("realnoe_tv", "Реальное ТВ"), ("semejnye", "Семейный"),
              ("sports", "Спорт"), ("tok_show", "Ток-шоу"), ("triller", "Триллеры"), ("uzhasu", "Ужасы"), ("fantastiks", "Фантастика"),
              ("film_noir", "Фильм-нуар"), ("fjuntezia", "Фэнтези"))

    # the five filler strings PlayerJS puts into the "#2" base64 data (":<:" + one of them, also nested)
    PJS_TRASH = ("bE5qSTlWNVUxZ01uc3h0NFFy", "SURhQnQwOEM5V2Y3bFlyMGVI", "Mm93S0RVb0d6c3VMTkV5aE54",
                 "bzl3UHQwaWk0MkdXZVM3TDdB", "MTluMWlLQnI4OXVic2tTNXpU")

    # quality / picture words of a translation tag ("[4K, SDR, ru, WinMedia]", "[4К SDR, Ukr]", "[BD1080+, Ukr]"; К can
    # be Cyrillic): the quality list after the choice names them, in the link name they would make "Default video
    # quality" read the translation as 4K / 1080p
    QUALITY_WORD = re.compile(r"^(?:(?:BD|WEB|HD)?\d{3,4}[pi]?\+?|4(?:K|К)|UHD|SDR|HDR(?:10\+?)?|DV|Dolby|Vision)$", re.I)
    # player data / playlists hold signed stream urls: fetched again after this many seconds
    PLAYER_TTL = 1800
    YEARS_PER_PAGE = 50

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Filmix", "cookie": "filmix.cookie"})
        self.USER_AGENT = self.cm.getDefaultUserAgent('chrome')
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                       "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.6"}
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("templates/Filmix/media/img/filmix.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("film/")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("seria/")},
                     {"category": "list_items", "title": _("Animated movies"), "url": self.getFullUrl("mults/")},
                     {"category": "list_items", "title": _("Animated series"), "url": self.getFullUrl("multser/")},
                     {"category": "genres", "title": _("Genres"), "section": "film"},
                     {"category": "genres", "title": _("Series genres"), "section": "seria"},
                     {"category": "years", "title": _("Year")},
                     {"category": "list_items", "title": "4K", "url": self.getFullUrl("film/q4/")}] + self.searchItems()
        self.pageCache = {}
        self.playerCache = {}
        self.qualityCache = {}

        self.watchedHelper = IPTVWatchedHelper("filmix")
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
        sts, data = self.cm.getPage(baseUrl, addParams, post_data)
        # pCommon decodes the windows-1251 pages to unicode: utf-8 str on Python 2 like the rest of the host
        return sts, ensure_str(data) if sts else data

    def _cacheGet(self, key):
        item = self.playerCache.get(key)
        if item and time.time() - item[0] < self.PLAYER_TTL:
            return item[1]
        return None

    def _cacheSet(self, key, value):
        self.playerCache[key] = (time.time(), value)

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

    def _decode(self, value):
        # PlayerJS "#2": base64 with filler strings inserted (one filler can sit inside another one)
        value = ensure_str(value or "").strip()
        if not value.startswith("#2"):
            return value
        data = value[2:]
        while True:
            clean = data
            for trash in self.PJS_TRASH:
                clean = clean.replace(":<:" + trash, "")
            if clean == data:
                break
            data = clean
        try:
            return ensure_str(base64.b64decode(data + "=" * (-len(data) % 4)))
        except Exception:
            printExc()
            return ""

    def _qualities(self, files):
        # "[480p]url,[720p]url or url2,[4K UHD]url" -> [(label, url)]
        ret = []
        for label, urls in re.findall(r"\[([^\]]+)\]([^\[]+)", files or ""):
            url = urls.strip().rstrip(",").split(" or ")[0].strip()
            if url.startswith("http"):
                ret.append((label.strip(), url))
        return ret

    def _voiceName(self, name):
        name = self.cleanHtmlStr(ensure_str(name))
        m = re.search(r"\[([^\]]*)\]", name)
        if not m:
            return name
        tags = [x.strip() for x in m.group(1).split(",") if x.strip() and not all(self.QUALITY_WORD.match(w) for w in x.split())]
        base = name[:m.start()].strip()
        return ("%s [%s]" % (base, ", ".join(tags))) if tags else base

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("Filmix.listItems [%s]" % cItem.get("url", ""))
        page = int(cItem.get("page", 1) or 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        if cItem.get("search"):
            post = {"scf": "fx", "story": cItem["search"], "search_start": str(page), "do": "search", "subaction": "search"}
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, **{"X-Requested-With": "XMLHttpRequest", "Referer": baseUrl})
            # the search answers by POST, the template only serves "Jump" (the page goes in the POST data)
            tpl = baseUrl.split("#")[0] + "#page={page}"
            sts, data = self.getPage(self.getFullUrl("engine/ajax/sphinx_search.php"), params, post)
        else:
            tpl = baseUrl + "pages/{page}/"
            sts, data = self.getPage(baseUrl if page <= 1 else tpl.format(page=page))
        if not sts:
            return
        seen = set()
        for item in re.split(r"<article\s+class=\"shortstory", data)[1:]:
            item = item.split("</article>")[0]
            url = self.cm.ph.getSearchGroups(item, r'href="(https?://[^"]+/\d+-[^"]+\.html)"')[0]
            if not url or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h2[^>]+class="name"[^>]+content="([^"]+)"')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<img[^>]+title="([^"]+)"')[0])
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            year = self.cm.ph.getSearchGroups(item, r'itemprop="copyrightYear"[^>]*>(\d{4})<')[0]
            genres = ", ".join([self.cleanHtmlStr(x) for x in re.findall(r'itemprop="genre"[^>]*>([^<]+)<', item)])
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", 'class="quality"'), ("</div", ">"), False)[1])
            plot = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<p", ">", "description"), ("</p", ">"), False)[1])
            desc = " | ".join([x for x in (year, genres, quality) if x])
            if plot:
                desc = "%s\n%s" % (desc, plot) if desc else plot
            isSeries = re.search(r"/(?:seria|multser)/", url) is not None
            params = {"good_for_fav": True, "url": url, "page_url": url, "s_title": title, "icon": self.getFullIconUrl(icon), "desc": desc,
                      "meta_title": title, "meta_year": year}
            if isSeries:
                params.update({"category": "series", "title": title, "meta_type": "tv"})
                self.addDir(params)
            else:
                params.update({"category": "movie", "title": self._movieTitle(title, year), "meta_type": "movie"})
                self.addVideo(params)
        if seen:
            if cItem.get("search"):
                pages = [int(n) for n in re.findall(r"list_submit2\((\d+)\)", data)]
            else:
                pages = [int(n) for n in re.findall(r'data-number="(\d+)"', data)]
            addPagingItems(self, dict(cItem, base_url=baseUrl), page, (page + 1) in pages, max(pages + [page]), tpl)

    def listGenres(self, cItem):
        section = cItem.get("section", "film")
        for slug, title in self.GENRES:
            params = dict(cItem)
            url = "film/%s/" % slug if section == "film" else "%s/%s/s7/" % (section, slug)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})
            self.addDir(params)

    def listYears(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        years = list(range(time.localtime()[0], 1919, -1))
        lastPage = (len(years) + self.YEARS_PER_PAGE - 1) // self.YEARS_PER_PAGE
        for year in years[(page - 1) * self.YEARS_PER_PAGE:page * self.YEARS_PER_PAGE]:
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "list_items", "title": str(year), "url": self.getFullUrl("film/y%d/" % year)})
            self.addDir(params)
        addPagingItems(self, cItem, page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Filmix.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("search/%s" % urllib_quote(searchPattern.strip())), "search": searchPattern.strip()})
        self.listItems(cItem)

    ###################################################
    # title page + player data
    ###################################################
    def _getTitlePage(self, url):
        if url in self.pageCache:
            return self.pageCache[url]
        sts, data = self.getPage(url)
        if not sts:
            return None
        ret = {"url": url, "post_id": self.cm.ph.getSearchGroups(url, r"/(\d+)-[^/]+\.html")[0]}
        ret["title"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<h1", ">", "name"), ("</h1", ">"), False)[1])
        icon = self.cm.ph.getSearchGroups(data, r'<img[^>]+src="(https?://[^"]+)"[^>]+class="poster')[0] or self.cm.ph.getSearchGroups(data, r'og:image"\s+content="([^"]+)"')[0]
        ret["icon"] = self.getFullIconUrl(icon) if icon else ""
        info = {}
        for name, value in re.findall(r'<div class="item [^"]+"><span class="label">([^<]+):</span>(.*?)</div>', data, re.S):
            info[self.cleanHtmlStr(name)] = self.cleanHtmlStr(value)
        years = re.findall(r"(\d{4})", info.get("Год", ""))
        ret["year"] = years[0] if years else ""
        ret["years"] = info.get("Год", "")
        ret["alt_title"] = info.get("Название", "")
        ret["genres"] = info.get("Жанр", "")
        ret["country"] = info.get("Страна", "")
        ret["translation"] = info.get("Перевод", "")
        ret["director"] = info.get("Режиссер", "")
        ret["actors"] = info.get("В ролях", "")
        ret["mpaa"] = info.get("MPAA", "")
        ret["imdb_rating"] = self.cm.ph.getSearchGroups(data, r"icon-imdb[^>]*>\s*<p>([\d.]+)</p>")[0]
        desc = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "full-story"), ("</div", ">"), False)[1]
        ret["desc"] = self.cleanHtmlStr(desc.replace("<br>", "[/br]").replace("<br />", "[/br]")).replace("[/br]", "\n").strip()
        self.pageCache[url] = ret
        return ret

    def _getPlayer(self, page):
        # {"voices": [(name, files or playlist url)], "pl": bool, "trailers": [(name, files)]}
        postId = page.get("post_id", "")
        if not postId:
            return {}
        cached = self._cacheGet(postId)
        if cached is not None:
            return cached
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, **{"X-Requested-With": "XMLHttpRequest", "Referer": page["url"], "Accept": "application/json, text/javascript, */*; q=0.01"})
        url = self.getFullUrl("api/movies/player-data?t=%d" % int(time.time() * 1000))
        post = {"post_id": postId, "showfull": "true"}
        sts, data = self.getPage(url, params, post)
        if not sts or not data.lstrip().startswith("{"):
            # the API answers 403 without the cookies the page sets: load the page again, then retry once
            self.getPage(page["url"])
            sts, data = self.getPage(url, params, post)
        try:
            msg = json_loads(data)["message"]
            trans = msg.get("translations") or {}
        except Exception:
            printExc()
            return {}
        ret = {"pl": ensure_str(trans.get("pl", "")) == "yes", "voices": [], "trailers": []}
        for key, field in (("video", "voices"), ("trailers", "trailers")):
            items = trans.get(key) or {}
            if isinstance(items, dict):
                for name, value in items.items():
                    ret[field].append((self._voiceName(name), self._decode(value)))
        self._cacheSet(postId, ret)
        return ret

    def _getPlaylist(self, url):
        # one translation of a series: [(seasonNum, seasonTitle, [{"num", "label", "files"}])]
        cached = self._cacheGet(url)
        if cached is not None:
            return cached
        sts, data = self.getPage(url)
        seasons = []
        try:
            items = json_loads(self._decode(data)) if sts else []
        except Exception:
            printExc()
            items = []
        if items and isinstance(items[0], dict) and not isinstance(items[0].get("folder"), list):
            # a playlist without seasons
            items = [{"title": "", "folder": items}]
        for season in items:
            if not isinstance(season, dict) or not isinstance(season.get("folder"), list):
                continue
            sTitle = self.cleanHtmlStr(ensure_str(season.get("title", "")))
            episodes = []
            for ep in season["folder"]:
                if not isinstance(ep, dict) or not ep.get("file"):
                    continue
                epId = ensure_str(ep.get("id", ""))
                label = self.cleanHtmlStr(re.sub(r"\s*\([^)]*\)\s*$", "", ensure_str(ep.get("title", ""))))
                num = self._num(self.cm.ph.getSearchGroups(epId, r"e(\d+)")[0]) or self._num(label)
                episodes.append({"num": num, "label": label, "files": ensure_str(ep["file"])})
            sNum = self._num(self.cm.ph.getSearchGroups(ensure_str(season["folder"][0].get("id", "") if season["folder"] and isinstance(season["folder"][0], dict) else ""), r"s(\d+)")[0])
            if episodes:
                seasons.append((sNum or self._num(sTitle) or (len(seasons) + 1), sTitle, episodes))
        if seasons:
            # a failed / empty answer is asked again next time
            self._cacheSet(url, seasons)
        return seasons

    def _seasons(self, player):
        # all translations merged: [(seasonNum, seasonTitle, [{"num", "label", "voices": [(voice, files)]}])]
        merged = {}
        order = []
        for voice, plUrl in player.get("voices") or []:
            if not plUrl.startswith("http"):
                continue
            for sNum, sTitle, episodes in self._getPlaylist(plUrl):
                if sNum not in merged:
                    merged[sNum] = (sTitle, {}, [])
                    order.append(sNum)
                eps, epOrder = merged[sNum][1], merged[sNum][2]
                for ep in episodes:
                    key = ep["num"] or ep["label"]
                    if key not in eps:
                        eps[key] = {"num": ep["num"], "label": ep["label"], "voices": []}
                        epOrder.append(key)
                    eps[key]["voices"].append((voice, ep["files"]))
        return [(sNum, merged[sNum][0], [merged[sNum][1][k] for k in merged[sNum][2]]) for sNum in sorted(order)]

    def listSeries(self, cItem):
        printDBG("Filmix.listSeries [%s]" % cItem.get("url", ""))
        page = self._getTitlePage(cItem.get("page_url", cItem["url"]))
        if page is None:
            return
        player = self._getPlayer(page)
        sTitle = page["title"] or cItem.get("s_title", "")
        if not player.get("pl"):
            if player.get("voices"):
                # a "series" page with a film player (one part)
                params = dict(cItem)
                params.update({"category": "movie", "title": self._movieTitle(sTitle, page["year"]), "meta_type": "movie"})
                self.addVideo(params)
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return
        seasons = self._seasons(player)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        if len(seasons) == 1:
            self._addEpisodes(cItem, page, seasons[0])
            return
        for season in seasons:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "season", "title": "%s - %s" % (sTitle, season[1] or (_("Season") + " %d" % season[0])),
                           "season": season[0], "url": "%s#s%d" % (page["url"], season[0]), "page_url": page["url"], "meta_year": page["year"]})
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
                      "title": self._episodeTitle(sTitle, season[0], ep["num"], label), "desc": " | ".join([x for x in (page["alt_title"], label) if x]),
                      "meta_type": "tv", "meta_title": sTitle, "meta_year": page["year"]}
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def _link(self, name, files):
        # one link per translation, its qualities come with getVideoLinks ("Default video quality" picks there)
        qualities = self._qualities(files)
        if not qualities:
            return None
        url = qualities[-1][1]
        self.qualityCache[url] = qualities
        return {"name": name or "Filmix", "url": strwithmeta(url, {"filmix_files": files}), "need_resolve": 1}

    def getLinksForVideo(self, cItem):
        printDBG("Filmix.getLinksForVideo [%s]" % cItem)
        page = self._getTitlePage(cItem.get("page_url", cItem.get("url", "")))
        if page is None:
            return []
        player = self._getPlayer(page)
        urltab = []
        if cItem.get("category") == "episode":
            for season in self._seasons(player):
                if season[0] != cItem.get("season"):
                    continue
                for ep in season[2]:
                    if str(ep["num"] or ep["label"]) == str(cItem.get("ep_key", "")):
                        for voice, files in ep["voices"]:
                            urltab.append(self._link(voice, files))
        elif not player.get("pl"):
            for voice, files in player.get("voices") or []:
                urltab.append(self._link(voice, files))
            for name, files in player.get("trailers") or []:
                urltab.append(self._link("%s - %s" % (_("Trailer"), name) if name else _("Trailer"), files))
        urltab = [x for x in urltab if x]
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        sidecarTxt = page["desc"] or cItem.get("desc", "")
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", "movie"), cItem.get("meta_title", ""), page.get("year", "") or cItem.get("meta_year", ""), "", skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt, metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("Filmix.getVideoLinks [%s]" % videoUrl)
        qualities = self.qualityCache.get(str(videoUrl))
        if not qualities:
            qualities = self._qualities(getattr(videoUrl, "meta", {}).get("filmix_files", "")) or [("", str(videoUrl))]
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        linksTab = []
        for label, url in qualities:
            if self.cm.isValidUrl(url):
                linksTab.append({"name": label or "MP4", "url": strwithmeta(url, {"User-Agent": self.USER_AGENT}), "need_resolve": 0})
        return decorateResolvedLinkItems(linksTab, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Filmix.getArticleContent [%s]" % cItem.get("url", ""))
        otherInfo = {}
        title = cItem.get("s_title", "") or cItem.get("title", "")
        text = ""
        icon = cItem.get("icon", "")
        page = self._getTitlePage(cItem.get("page_url", cItem.get("url", "")))
        if page:
            title = page["title"] or title
            text = page["desc"]
            icon = page["icon"] or icon
            for key, field in (("alternate_title", "alt_title"), ("year", "years"), ("genres", "genres"), ("country", "country"), ("translation", "translation"),
                               ("director", "director"), ("actors", "actors"), ("age_limit", "mpaa"), ("imdb_rating", "imdb_rating")):
                if page.get(field):
                    otherInfo[key] = page[field]
        mediaType = cItem.get("meta_type", "movie")
        meta = getMeta(mediaType, cItem["meta_title"], (page or {}).get("year", "") or cItem.get("meta_year", "")) if cItem.get("meta_title") else {}
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
        printDBG("Filmix.handleService name[%s] category[%s]" % (name, category))
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
        CHostBase.__init__(self, Filmix(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("filmix")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("series", "season", "movie", "episode")
