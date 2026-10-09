# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard (AlDrama app API, dwapp.arabypros.com/api):
#   - movies / series / Netflix / Ramadan / TV shows / genres from the app's filter ids and search,
#     with First page / Jump / Next page (30 rows per API page, no page count)
#   - series -> seasons (only when there are more than one) -> episodes; movies and episodes are VIDEO
#     rows on their key-less API url (stable for the downloaded flag and favourites)
#   - links: the sources of movie|episode/source/by/<id> (base64 answer) handed to urlparser, the
#     app's url.php?url= wrapper unwrapped, the YouTube trailer as the last link
#   - watched flag (series -> season -> episode), favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx"), sidecar, INFO via moviemeta + the app's story/genres/rating/cover;
#     no colour codes in titles
import re

from Components.config import ConfigSelection, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, E2ColoR, StripColorCodes, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.aldrama_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.aldrama_proxy))
    return optionList
###################################################


def gettytul():
    return "AlDrama"


PAGE_SIZE = 30
# Arabic ordinals of season labels ("الموسم الثاني")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5),
    ("السادسة", 6), ("السادس", 6), ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8),
    ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")

# (title, filter id) of the app's lists
MOVIES_TAB = (("الأفلام الرائجة", 25), ("أفلام أجنبية", 22), ("أفلام مدبلجة", 83), ("أفلام عربية", 19), ("أفلام أسيوية", 27),
              ("أفلام تركية", 65), ("أفلام هندية", 20), ("أفلام انيميشن", 61), ("أفلام كلاسيكية", 29))
SERIES_TAB = (("جديد المسلسلات", 24), ("مسلسلات أجنبية", 18), ("مسلسلات مدبلجة", 82), ("مسلسلات عربية", 16),
              ("مسلسلات أسيوية", 23), ("مسلسلات تركية", 17), ("مسلسلات انمي", 87))
RAMADAN_TAB = (("رمضان 2026", 90), ("رمضان 2025", 88), ("رمضان 2024", 79), ("رمضان 2023", 78), ("رمضان 2022", 66), ("رمضان 2021", 60))
GENRES_TAB = (("كوميديا", 37), ("دراما", 38), ("رومنسية", 39), ("اثارة", 40), ("أكشن", 41), ("مغامرة", 42), ("جريمة", 43), ("رعب", 44),
              ("فانتازيا", 45), ("غموض", 46), ("غربي", 47), ("موسيقى", 48), ("وثائقي", 49), ("حرب", 51), ("تاريخ", 52), ("خيال علمي", 53),
              ("عائلي", 54), ("رسوم متحركة", 55), ("خيال علمي وفنتازيا", 56), ("حركة ومغامرة", 57), ("حرب وسياسة", 58), ("واقع", 59),
              ("كوري", 84), ("صيني", 85), ("ياباني", 86))
SUB_MENUS = {"ad_movies": MOVIES_TAB, "ad_series": SERIES_TAB, "ad_ramadan": RAMADAN_TAB, "ad_genres": GENRES_TAB}


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


class AlDrama(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # the API base and its access key are stored base64 + reversed, like in the app
    sHost = b64Decode("L2lwYS9tb2Muc29ycHliYXJhLnBwYXdkLy86c3B0dGg=")
    mHost = b64Decode("LzMxZGFjYjEyZmZlZi05NzliLTE3YjQtMmVmOS1kZmJhNjA1ZC81ODE1MzZERERFQ0FFNDVBRjY4QTlEM0M5QTVGNC8=")
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "item_id", "s_title", "s_season", "s_episode", "season_id",
                  "site_plot", "site_genre", "site_rating", "site_duration", "trailer", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "aldrama", "cookie": "aldrama.cookie"})
        self.MAIN_URL = self.sHost[::-1]
        self.API_KEY = self.mHost[::-1].rstrip("/")
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/aldrama135.png")
        # the app's own client (the API answers the app's okhttp user agent)
        self.HEADER = {"User-Agent": "okhttp/4.12.0", "Accept-Encoding": "gzip", "Connection": "Keep-Alive"}
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("aldrama")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.aldrama_proxy.value) or None

    def getApi(self, path):
        # path: "poster/by/filtres/22/created/0" -> parsed JSON or None
        params = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy:
            params = MergeDicts(params, {"http_proxy": proxy})
        url = self.getFullUrl(path).split("#")[0].rstrip("/") + self.API_KEY + "/"
        sts, data = self.cm.getPage(url, params)
        if not sts or not data:
            return None
        data = data.strip()
        if data[:1] in ("[", "{"):
            candidates = [data]
        else:
            # the source answers: a few random characters + the base64 of the JSON list
            candidates = [data[m.start():] for m in re.finditer(r"W3s|eyJ|W10", data)]
        for text in candidates:
            try:
                if text[:1] not in ("[", "{"):
                    text = b64Decode(text)
                return json_loads(text)
            except Exception:
                continue
        printDBG("AlDrama.getApi: no JSON in the answer of [%s]" % path)
        return None

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("ad_video", "ad_series", "ad_season"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    @staticmethod
    def _text(value):
        return ("%s" % value).strip() if value not in (None, "", 0, "0") else ""

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            itemId = cItem.get("item_id", "")
            if not itemId:
                return ""
            if category == "ad_video":
                # movies and episodes are numbered separately by the API: the same id can be both
                if "/episode/" in cItem.get("url", ""):
                    return "episode:%s" % itemId
                return "video:%s" % itemId
            if category == "ad_series":
                return "series:%s" % itemId
            if category == "ad_season":
                return "season:%s|%s" % (itemId, cItem.get("season_id", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "ad_menu", "title": _("Movies"), "menu": "ad_movies"},
            {"category": "ad_menu", "title": _("Series"), "menu": "ad_series"},
            {"category": "list_items", "title": "Netflix", "url": self.getFullUrl("poster/by/filtres/81/created/"), "good_for_fav": True},
            {"category": "ad_menu", "title": _("Ramadan"), "menu": "ad_ramadan"},
            {"category": "list_items", "title": _("TV Shows"), "url": self.getFullUrl("poster/by/filtres/28/created/"), "good_for_fav": True},
            {"category": "ad_menu", "title": _("Genres"), "menu": "ad_genres"},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listSubMenu(self, cItem):
        for title, filterId in SUB_MENUS.get(cItem.get("menu", ""), ()):
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title,
                         "url": self.getFullUrl("poster/by/filtres/%d/created/" % filterId)})

    def _addPoster(self, item, normalize):
        mediaType = item.get("type", "")
        itemId = item.get("id")
        title = self.cleanHtmlStr(item.get("title", ""))
        if not itemId or not title:
            return
        year = self._text(item.get("year"))
        rating = self._text(item.get("imdb"))
        duration = self._text(item.get("duration"))
        genre = self._text(item.get("classification"))
        label = " ".join([self._text(item.get(k)) for k in ("label", "sublabel") if self._text(item.get(k))])
        plot = self.cleanHtmlStr(item.get("description") or "")
        fields = ((_("Year"), year, "cyan"), (_("Rating"), rating, "yellow"), (_("Duration"), duration, "green"), (_("Genre"), genre, "orange"))
        desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), name, E2ColoR("white"), value) for name, value, color in fields if value])
        if label:
            desc = "%s | %s" % (desc, label) if desc else label
        if plot:
            desc = "%s[/br]%s" % (desc, plot) if desc else plot
        trailer = (item.get("trailer") or {}).get("url", "") if isinstance(item.get("trailer"), dict) else ""
        icon = self.getFullIconUrl(item.get("image") or item.get("cover") or "")
        params = {"name": "category", "good_for_fav": True, "icon": icon, "desc": desc, "item_id": "%s" % itemId, "trailer": trailer,
                  "site_plot": plot, "site_genre": genre, "site_rating": rating, "site_duration": duration, "meta_title": title, "meta_year": year}
        if mediaType in ("serie", "series"):
            params.update({"category": "ad_series", "title": title, "url": self.getFullUrl("season/by/serie/%s" % itemId),
                           "s_title": title, "meta_type": "tv"})
            self.addDir(params)
        elif mediaType in ("movie", "movies"):
            params.update({"category": "ad_video", "title": ("%s (%s)" % (title, year)) if normalize and year else title,
                           "url": self.getFullUrl("movie/source/by/%s" % itemId), "meta_type": "movie"})
            self.addVideo(params)

    def listItems(self, cItem):
        # cItem["url"]: the list path without the page ("poster/by/filtres/22/created/", "search/<q>/"); the
        # API pages are 0-based, our pages 1-based. The path itself is the pager template (no "{page}").
        page = int(cItem.get("page", 1) or 1)
        base = cItem["url"]
        printDBG("AlDrama.listItems [%s] page %d" % (base, page))
        data = self.getApi("%s%d" % (base, page - 1))
        if isinstance(data, dict):
            data = data.get("posters") or []
        if not isinstance(data, list):
            return
        normalize = IsMediaNamingNormalized()
        for item in data:
            if isinstance(item, dict):
                self._addPoster(item, normalize)
        listItem = dict(cItem)
        listItem["category"] = "list_items"
        addPagingItems(self, listItem, page, len(data) >= PAGE_SIZE, 0, base)

    def _seasons(self, cItem):
        data = self.getApi("season/by/serie/%s" % cItem.get("item_id", ""))
        return [s for s in data if isinstance(s, dict)] if isinstance(data, list) else []

    def listSeries(self, cItem):
        printDBG("AlDrama.listSeries [%s]" % cItem.get("item_id", ""))
        seasons = self._seasons(cItem)
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, season_id="%s" % seasons[0].get("id", ""), s_season=_seasonNum(seasons[0].get("title", "")) or 1), seasons)
            return
        normalize = IsMediaNamingNormalized()
        for season in seasons:
            label = self.cleanHtmlStr(season.get("title", ""))
            num = _seasonNum(label)
            title = ("%s - %s" % (cItem.get("s_title", ""), formatSxxExx(num))) if normalize and num else label
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "ad_season", "title": title, "season_id": "%s" % season.get("id", ""), "s_season": num})
            self.addDir(params)

    def listEpisodes(self, cItem, seasons=None):
        printDBG("AlDrama.listEpisodes [%s|%s]" % (cItem.get("item_id", ""), cItem.get("season_id", "")))
        if seasons is None:
            seasons = self._seasons(cItem)
        show = cItem.get("s_title", "") or cItem.get("title", "")
        seasonNum = cItem.get("s_season", 0) or 1
        normalize = IsMediaNamingNormalized()
        for season in seasons:
            if "%s" % season.get("id", "") != cItem.get("season_id", ""):
                continue
            for episode in season.get("episodes") or []:
                epId = episode.get("id")
                if not epId:
                    continue
                label = self.cleanHtmlStr(episode.get("title", ""))
                num = self.cm.ph.getSearchGroups(label, EPISODE_RE.pattern)[0]
                if normalize and num:
                    title = "%s - %s" % (show, formatSxxExx(seasonNum, num))
                else:
                    title = "%s - %s" % (show, label) if label else show
                note = self.cleanHtmlStr(episode.get("description") or "")
                params = dict(cItem)
                params.update({"category": "ad_video", "good_for_fav": True, "title": title, "url": self.getFullUrl("episode/source/by/%s" % epId),
                               "item_id": "%s" % epId, "s_season": seasonNum, "s_episode": num,
                               "desc": ("%s[/br]%s" % (note, cItem.get("desc", ""))) if note else cItem.get("desc", "")})
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AlDrama.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("search/%s/" % urllib_quote(searchPattern.strip(), safe="")), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("AlDrama.getLinksForVideo [%s]" % cItem.get("url", ""))
        data = self.getApi(cItem.get("url", ""))
        urltab = []
        seen = set()
        names = []
        for source in data if isinstance(data, list) else []:
            url = ("%s" % (source.get("url") or "")).strip() if isinstance(source, dict) else ""
            if "/url.php?url=" in url:
                # the app's redirect wrapper
                url = urllib_unquote(url.split("/url.php?url=", 1)[1])
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            if re.search(r"https?://(?:www\.)?akwam\.[^/]+/(?:watch|movies?)/", url):
                # akwam site pages, not embeds
                continue
            seen.add(url)
            domain = self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]
            quality = self._text(source.get("quality"))
            name = "%s [%s]" % (domain, quality) if quality else domain
            names.append(name)
            if names.count(name) > 1:
                name = "%s (%d)" % (name, names.count(name))
            urltab.append({"name": name, "url": url, "need_resolve": 1})
        trailer = cItem.get("trailer", "")
        if self.cm.isValidUrl(trailer):
            urltab.append({"name": "%s (YouTube)" % _("Trailer"), "url": trailer, "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("AlDrama.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("AlDrama.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        info = {}
        for key, field in (("year", "meta_year"), ("genres", "site_genre"), ("imdb_rating", "site_rating"), ("duration", "site_duration")):
            if cItem.get(field):
                info[key] = cItem[field]
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        story = cItem.get("site_plot", "")
        text = plot or story or StripColorCodes(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("AlDrama.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "ad_menu":
            self.listSubMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "ad_series":
            self.listSeries(self.currItem)
        elif category == "ad_season":
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
        CHostBase.__init__(self, AlDrama(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("aldrama")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("ad_video", "ad_series", "ad_season")
