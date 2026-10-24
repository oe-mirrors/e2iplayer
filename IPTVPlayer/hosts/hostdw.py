# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# DW (Deutsche Welle) MediaCenter: live channels, latest videos, programmes, categories and search per language
# (German first, language selectable). Lists from the public DW search engine (webapi.dw.com/searchapi) and
# www.dw.com/graph-api, streams from api.dw.com/api/detail/video (MP4 + HLS, worldwide, no DRM)
from Components.config import config, ConfigSelection, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

# (www.dw.com language code, search engine, name of the language in that language)
LANGUAGES = [("de", "german", "Deutsch"), ("en", "english", "English"), ("es", "spanish", "Español"),
             ("fr", "french", "Français"), ("ar", "arabic", "العربية"), ("ru", "russian", "Русский"),
             ("tr", "turkish", "Türkçe"), ("pt-br", "portuguese-brazil", "Português do Brasil"),
             ("fa-ir", "persian", "فارسی"), ("uk", "ukranian", "Українська"), ("pl", "polish", "Polski"),
             ("hi", "hindi", "हिन्दी"), ("id", "indonesian", "Bahasa Indonesia"), ("sw", "kiswahili", "Kiswahili"),
             ("bn", "bengali", "বাংলা"), ("ur", "urdu", "اردو"), ("el", "greek", "Ελληνικά"),
             ("sr", "serbian", "Српски"), ("bs", "bosnian", "Bosanski"), ("hr", "croatian", "Hrvatski"),
             ("ro", "romanian", "Română"), ("bg", "bulgarian", "Български"), ("sq", "albanian", "Shqip"),
             ("mk", "macedonian", "Македонски"), ("ha", "hausa", "Hausa"), ("am", "amharic", "አማርኛ"),
             ("ps", "pashto", "پښتو"), ("fa-af", "dari", "دری")]
LANG_ENGINE = dict((code, engine) for code, engine, _name in LANGUAGES)
LANG_NAME = dict((code, name) for code, _engine, name in LANGUAGES)

config.plugins.iptvplayer.dw_language = ConfigSelection(default="de", choices=[(code, name) for code, _engine, name in LANGUAGES])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language:"), config.plugins.iptvplayer.dw_language))
    return optionList


def gettytul():
    return "https://www.dw.com/"


SEARCH_URL = "https://webapi.dw.com/searchapi/api/as/v1/engines/%s-nest/search"
GRAPH_URL = "https://www.dw.com/graph-api/%s/%s"
DETAIL_URL = "https://api.dw.com/api/detail/video/%s"
PAGE_SIZE = 30
MAX_PAGE = 100  # the search engine answers up to page 100
# live channels of the graph-api (DW Deutsch has no live stream any more: its old Akamai master lists dead variants)
LIVE_CHANNELS = ("english", "spanish", "arabic")


class DW(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "dw_id", "lang", "f_program", "f_category", "icon", "desc", "live")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "dw", "cookie": "dw.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept": "application/json", "Referer": "https://www.dw.com/", "Origin": "https://www.dw.com"})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/dw135.png")
        self.watchedHelper = IPTVWatchedHelper("dw")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            if cItem.get("type", "") == "video":
                url = cItem.get("url", "")
                return "video:%s" % url if url else ""
            if cItem.get("category", "") == "dw_list" and cItem.get("f_program"):
                return "folder:program-%s" % cItem["f_program"]
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _lang(self, cItem):
        lang = cItem.get("lang") or config.plugins.iptvplayer.dw_language.value
        return lang if lang in LANG_ENGINE else "de"

    def _json(self, url, postData=None):
        params = dict(self.defaultParams)
        if postData is not None:
            params["header"] = dict(self.HEADER, **{"Content-Type": "application/json"})
            params["raw_post_data"] = True
            postData = json_dumps(postData)
        sts, data = self.cm.getPage(url, params, postData)
        if not sts or not data:
            return {}
        try:
            data = json_loads(data)
            return data if isinstance(data, dict) else {}
        except Exception:
            printExc()
        return {}

    def _search(self, lang, query="", filters=None, page=1, byDate=True, facets=None):
        body = {"query": query, "page": {"size": PAGE_SIZE, "current": page},
                "filters": {"all": [{"modelType": ["VIDEO"]}] + (filters or [])}}
        if byDate:
            body["sort"] = {"contentDate": "desc"}
        if facets:
            body["facets"] = facets
        return self._json(SEARCH_URL % LANG_ENGINE.get(lang, "german"), body)

    @staticmethod
    def _raw(result, key):
        return (result.get(key) or {}).get("raw")

    @staticmethod
    def _imageUrl(staticUrl, formatId="603"):
        # static.dw.com/image/<id>_${formatId}.jpg: 603 = 700x394
        return (staticUrl or "").replace("${formatId}", formatId)

    @staticmethod
    def _duration(seconds):
        try:
            seconds = int(float(seconds))
        except Exception:
            return ""
        if seconds <= 0:
            return ""
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        lang = self._lang(cItem)
        base = {"name": "category", "lang": lang}
        menu = [{"category": "dw_live", "title": _("Live channels")},
                {"category": "dw_list", "title": _("Latest videos")},
                {"category": "dw_programs", "title": _("Programmes")},
                {"category": "dw_categories", "title": _("Categories")},
                {"category": "dw_languages", "title": "%s %s" % (_("Language:"), LANG_NAME.get(lang, lang))}]
        menu += self.searchItems()
        for item in menu:
            params = dict(base)
            params.update(item)
            params["good_for_fav"] = item["category"] in ("dw_list", "dw_programs", "dw_categories")
            self.addDir(params)

    def listLanguages(self, cItem):
        for code, _engine, name in LANGUAGES:
            params = {"name": "category", "category": "dw_menu", "lang": code, "title": name, "good_for_fav": True}
            self.addDir(params)

    def listLive(self, cItem):
        lang = self._lang(cItem)
        channels = []
        # the channel of the selected language first
        own = {"es": "spanish", "ar": "arabic"}.get(lang, "english")
        for key in [own] + [k for k in LIVE_CHANNELS if k != own]:
            data = self._json(GRAPH_URL % (lang, "livestream/%s" % key))
            for ch in ((data.get("data") or {}).get("livestreamChannels") or []):
                if not ch.get("hlsVideoSrc"):
                    continue
                desc = []
                for slot in (ch.get("nextTimeSlots") or [])[:2]:
                    prog = self.cleanHtmlStr(((slot.get("program") or {}).get("name")) or "")
                    elem = self.cleanHtmlStr(((slot.get("programElement") or {}).get("name")) or "")
                    start = str(slot.get("startDate") or "")
                    line = " - ".join([x for x in (prog, elem) if x])
                    if line:
                        desc.append("%s %s UTC  %s" % (start[:10], start[11:16], line) if len(start) >= 16 else line)
                icon = (((ch.get("nextTimeSlots") or [{}])[0].get("program") or {}).get("posterImageUrl")) or ""
                channels.append((self.cleanHtmlStr(ch.get("name") or key), ch["hlsVideoSrc"], "[/br]".join(desc), icon))
        for title, url, desc, icon in channels:
            params = {"name": "category", "category": "dw_live_video", "lang": lang, "title": title, "url": url,
                      "desc": desc, "icon": icon, "live": True, "good_for_fav": True}
            self.addVideo(params)

    def listPrograms(self, cItem):
        lang = self._lang(cItem)
        data = self._json(GRAPH_URL % (lang, "programs-overview"))
        overview = (data.get("data") or {}).get("programsOverview") or {}
        for prog in overview.get("videoPrograms") or []:
            if not prog.get("id"):
                continue
            params = stripPagerKeys(dict(cItem))
            params.update({"category": "dw_list", "title": self.cleanHtmlStr(prog.get("title") or prog.get("name") or ""),
                           "f_program": prog["id"], "url": "https://www.dw.com" + (prog.get("namedUrl") or "/program-%s" % prog["id"]),
                           "icon": self._imageUrl((prog.get("mainContentImage") or {}).get("staticUrl")),
                           "desc": self.cleanHtmlStr(prog.get("teaser") or ""), "good_for_fav": True})
            self.addDir(params)

    def listCategories(self, cItem):
        lang = self._lang(cItem)
        data = self._search(lang, facets={"categories.name": [{"type": "value", "size": 60}]})
        for facet in ((data.get("facets") or {}).get("categories.name") or []):
            for value in facet.get("data") or []:
                name = value.get("value") or ""
                if not name or name.startswith("["):
                    continue
                params = stripPagerKeys(dict(cItem))
                params.update({"category": "dw_list", "title": name, "f_category": name, "url": "",
                               "desc": "%s: %s" % (_("Videos"), value.get("count", "")), "good_for_fav": True})
                self.addDir(params)

    ###################################################
    # video lists
    ###################################################
    def listVideos(self, cItem, query=""):
        lang = self._lang(cItem)
        page = max(1, int(cItem.get("page", 1) or 1))
        filters = []
        if cItem.get("f_program"):
            filters.append({"unifiedPrograms.id": [cItem["f_program"]]})
        if cItem.get("f_category"):
            filters.append({"categories.name": [cItem["f_category"]]})
        data = self._search(lang, query, filters, page, byDate=not query)
        for result in data.get("results") or []:
            self._addResult(cItem, result, lang)
        pageInfo = (data.get("meta") or {}).get("page") or {}
        lastPage = min(int(pageInfo.get("total_pages") or 0), MAX_PAGE)
        # the page number drives the list, the constant template only lets "Jump" through
        addPagingItems(self, dict(cItem, desc=""), page, page < lastPage, lastPage, cItem.get("url") or self.MAIN_URL)

    def _addResult(self, cItem, result, lang):
        try:
            dwId = (result.get("_meta") or {}).get("id") or ""
            title = self.cleanHtmlStr(self._raw(result, "title") or "")
            namedUrl = self._raw(result, "namedUrl") or ""
            if not dwId or not title:
                return
            date = str(self._raw(result, "contentDate") or "")
            program = self._raw(result, "unifiedPrograms.name") or self._raw(result, "programs.name") or ""
            if isinstance(program, list):
                program = program[0] if program else ""
            descTab = []
            dur = self._duration(self._raw(result, "duration"))
            if dur:
                descTab.append(dur)
            if len(date) >= 10:
                descTab.append(date[:10])
            if program:
                descTab.append(self.cleanHtmlStr(program))
            teaser = self.cleanHtmlStr(self._raw(result, "teaser") or self._raw(result, "shortTeaser") or "")
            desc = " | ".join(descTab)
            if teaser:
                desc = "%s[/br]%s" % (desc, teaser) if desc else teaser
            icon = self._raw(result, "posterImageUrl") or self._imageUrl(self._raw(result, "mainContentImageLink.target.staticUrl"))
            params = stripPagerKeys(dict(cItem), ("f_program", "f_category", "search_pattern"))
            params.update({"category": "dw_video", "title": normalizeMediathekTitle(title, date=date), "dw_id": dwId, "lang": lang,
                           "url": "https://www.dw.com" + namedUrl if namedUrl.startswith("/") else "https://www.dw.com/%s/video-%s" % (lang, dwId),
                           "icon": icon or cItem.get("icon", ""), "desc": desc, "live": False, "good_for_fav": True})
            self.addVideo(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("DW.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem, category="dw_search", s_query=searchPattern, url="")
        self.listVideos(cItem, searchPattern)

    ###################################################
    # links
    ###################################################
    def _subtitles(self, lang, dwId):
        subTracks = []
        data = self._json(GRAPH_URL % (lang, "content/video/%s" % dwId))
        for sub in (((data.get("data") or {}).get("content") or {}).get("subtitles") or []):
            url = sub.get("subtitleUrl") or ""
            if url:
                code = sub.get("srcLanguage") or lang
                subTracks.append({"title": (sub.get("language") or code).capitalize(), "lang": code, "url": url, "format": "vtt"})
        return subTracks

    def getLinksForVideo(self, cItem):
        printDBG("DW.getLinksForVideo [%s]" % cItem.get("url", ""))
        if cItem.get("live"):
            meta = {"iptv_proto": "m3u8", "iptv_livestream": True, "User-Agent": self.HEADER.get("User-Agent")}
            return [{"name": "HLS live", "url": strwithmeta(cItem.get("url", ""), meta), "need_resolve": 0}]
        dwId = cItem.get("dw_id", "")
        if not dwId:
            dwId = cItem.get("url", "").rsplit("-", 1)[-1]
        data = self._json(DETAIL_URL % dwId)
        sources = ((data.get("mainContent") or {}).get("sources")) or []
        if not sources:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        subTracks = self._subtitles(self._lang(cItem), dwId)
        baseMeta = {"User-Agent": self.HEADER.get("User-Agent")}
        if subTracks:
            baseMeta["external_sub_tracks"] = subTracks
        mp4 = []
        hls = []
        for src in sources:
            url = src.get("url") or ""
            if not url.startswith("http"):
                continue
            if (src.get("format") or "").lower() == "hls" or ".m3u8" in url:
                hls.append({"name": "HLS (adaptive)", "url": strwithmeta(url, dict(baseMeta, iptv_proto="m3u8")), "need_resolve": 0})
                continue
            quality = src.get("quality") or ""
            height = quality.rsplit("x", 1)[-1] if "x" in quality else ""
            name = "%sp mp4" % height if height.isdigit() else "mp4 %s" % quality
            mp4.append((int(height) if height.isdigit() else int(src.get("bitrate") or 0), {"name": name, "url": strwithmeta(url, dict(baseMeta)), "need_resolve": 0}))
        mp4.sort(key=lambda x: x[0], reverse=True)
        # HLS first: the MP4 files carry their index (moov) at the end - slow start; they stay for downloads
        urlTab = hls + [x[1] for x in mp4]
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("DW.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        try:
            if cItem.get("category") == "dw_video" and cItem.get("dw_id"):
                data = self._json(GRAPH_URL % (self._lang(cItem), "content/video/%s" % cItem["dw_id"]))
                content = (data.get("data") or {}).get("content") or {}
                if content:
                    teaser = self.cleanHtmlStr(content.get("teaser") or "")
                    body = self.cleanHtmlStr(content.get("text") or "")
                    text = "[/br]".join([x for x in (teaser, body) if x]) or text
                    if content.get("formattedDuration"):
                        otherInfo["duration"] = content["formattedDuration"]
                    if content.get("localizedContentDate"):
                        otherInfo["released"] = content["localizedContentDate"]
                    progs = [self.cleanHtmlStr(p.get("name") or "") for p in content.get("unifiedPrograms") or [] if p.get("name")]
                    if progs:
                        otherInfo["station"] = "DW - %s" % ", ".join(progs)
                    if content.get("subtitles"):
                        otherInfo["subtitles"] = ", ".join([(s.get("srcLanguage") or "") for s in content["subtitles"] if s.get("srcLanguage")])
                    icon = content.get("posterImageUrl") or icon
            elif cItem.get("live"):
                otherInfo["status"] = _("On Air")
                text = text or "%s - %s" % (title, _("Live channels"))
        except Exception:
            printExc()
        return [{"title": title, "text": text or title, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("dw_"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("DW.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None or category == "dw_menu":
            self.listMainMenu(self.currItem)
        elif category == "dw_languages":
            self.listLanguages(self.currItem)
        elif category == "dw_live":
            self.listLive(self.currItem)
        elif category == "dw_programs":
            self.listPrograms(self.currItem)
        elif category == "dw_categories":
            self.listCategories(self.currItem)
        elif category == "dw_list":
            self.listVideos(self.currItem)
        elif category == "dw_search":
            self.listVideos(self.currItem, self.currItem.get("s_query", ""))
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search", "lang": self._lang(self.currItem)}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, DW(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("dw")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("dw_video", "dw_live_video")
