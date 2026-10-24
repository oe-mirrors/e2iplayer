# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
#   - Yle Areena (Finland): the Swedish catalogue of Yle Arenan first, the Finnish one second
#   - start page lists, all TV programmes, live channels, series -> seasons -> episodes, search
#   - streams: player.api.yle.fi preview -> HLS (no DRM); many titles play in Finland only ("geo FI")
#   - the public app keys are read from the site (page settings / player script), built-in ones as fallback
import base64
import re

from Components.config import config, ConfigYesNo, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.yleareena_hide_geo = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Hide titles only available in Finland:", config.plugins.iptvplayer.yleareena_hide_geo))
    return optionList


def gettytul():
    return "https://areena.yle.fi/"


API_URL = "https://areena.api.yle.fi"
PREVIEW_URL = "https://player.api.yle.fi/v1/preview/%s.json"
PLAYER_SCRIPT_URL = "https://player-v2.yle.fi/embed.js"
IMAGE_URL = "https://images.cdn.yle.fi/image/upload/ar_16:9,c_fill,w_%d,f_jpg/v%s/%s.jpg"
# public keys of the web front end (window.envVariables of every page) and of the web player (player-v2.yle.fi chunk);
# only used when they can not be read from the site
FRONTEND_KEYS = ("areena-web-items", "wlTs5D9OjIdeS9krPzRQR4I1PYVzoazN")
PLAYER_KEYS = ("player_static_prod", "8930d72170e48303cf5f3867780d549b")
PAGE_SIZE = 40

# Swedish front end first, Finnish second
SITES = {
    "sv": {"title": "Yle Arenan (svenska)", "base": "https://arenan.yle.fi", "all": "/tv/program/57-RyyJnwb9b", "live": "/direkt"},
    "fi": {"title": "Yle Areena (suomi)", "base": "https://areena.yle.fi", "all": "/tv/ohjelmat/57-RyyJnwb9b", "live": "/suorat"},
}
LANGS = ("sv", "fi")

ITEM_ID_RE = re.compile(r'yleareena://items/([0-9]+-[0-9]+)')
PACKAGE_ID_RE = re.compile(r'yleareena://packages/([0-9A-Za-z]+-[0-9A-Za-z]+)')
PLAYER_ID_RE = re.compile(r'/players/([^/?#]+)\.json')
URL_ID_RE = re.compile(r'yle\.fi/(?:[a-z]+/)?(1-[0-9]+)')
NEXT_DATA_RE = re.compile(r'(?s)<script id="__NEXT_DATA__"[^>]*>(.*?)</script>')
FRONTEND_KEY_RE = re.compile(r'"appIdFrontend"\s*:\s*"([^"]+)"\s*,\s*"appKeyFrontend"\s*:\s*"([^"]+)"')
PLAYER_KEY_RE = re.compile(r'app_id=([A-Za-z0-9_-]+)&app_key=([0-9A-Za-z]+)')
CHUNK_MAP_RE = re.compile(r'\.u=function\(\w+\)\{return \w+\+"\."\+\{([^}]+)\}\[\w+\]\+"\.js"\}')
EPISODE_RE = re.compile(r'^(\d+)\.\s+(.+)$')
YEAR_RE = re.compile(r'\((?:[^()]*\s)?((?:19|20)\d\d)\)')
INFO_PAIR_RE = re.compile(r'^([^:\n]+):\s*(.+)$')


class YleAreena(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "lang", "item_id", "source", "geo_filter", "season", "episode",
                  "view_url", "tab", "icon", "desc", "geo", "live", "series_id", "season_id")
    # app keys read from the site, kept for the plugin session
    KEYS = {}

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "yleareena", "cookie": "yleareena.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Referer": "https://areena.yle.fi/", "Origin": "https://areena.yle.fi"})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "yle_lang", "title": SITES[lang]["title"], "lang": lang} for lang in LANGS] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("yleareena")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            itemId = str(cItem.get("item_id", "") or "").strip()
            category = cItem.get("category", "")
            if not itemId:
                return ""
            if cItem.get("type", "") in ("video", "audio") and category == "yle_video":
                return "video:%s" % itemId
            if category == "yle_series":
                return "series:%s" % itemId
            if category == "yle_season":
                season = str(cItem.get("season_id", "") or "").strip()
                return "season:%s|%s" % (itemId, season) if season else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _lang(self, cItem):
        lang = (cItem or {}).get("lang", "")
        return lang if lang in SITES else LANGS[0]

    def _siteUrl(self, lang, path=""):
        return SITES[lang]["base"] + path

    def _imageUrl(self, image, width=400):
        try:
            if isinstance(image, dict) and image.get("id"):
                return IMAGE_URL % (width, ensure_str(str(image.get("version") or "1")), ensure_str(image["id"]))
        except Exception:
            printExc()
        return ""

    def _hideGeo(self):
        try:
            return config.plugins.iptvplayer.yleareena_hide_geo.value
        except Exception:
            return False

    def _frontendKeys(self, html=""):
        match = FRONTEND_KEY_RE.search(html or "")
        if match:
            YleAreena.KEYS["frontend"] = (match.group(1), match.group(2))
        if "frontend" not in YleAreena.KEYS:
            sts, data = self.cm.getPage(self._siteUrl(LANGS[0], "/tv"), self.defaultParams)
            match = FRONTEND_KEY_RE.search(data) if sts else None
            YleAreena.KEYS["frontend"] = (match.group(1), match.group(2)) if match else FRONTEND_KEYS
        return YleAreena.KEYS["frontend"]

    def _playerKeys(self):
        # the web player loads its API client as a webpack chunk: embed.js -> chunk names -> app_id / app_key
        if "player" not in YleAreena.KEYS:
            keys = None
            sts, data = self.cm.getPage(PLAYER_SCRIPT_URL, self.defaultParams)
            if sts:
                match = PLAYER_KEY_RE.search(data)
                if match:
                    keys = (match.group(1), match.group(2))
                chunkMap = CHUNK_MAP_RE.search(data)
                for chunkId, chunkHash in re.findall(r'(\d+):"([0-9a-f]+)"', chunkMap.group(1) if chunkMap and not keys else ""):
                    sts, chunk = self.cm.getPage("https://player-v2.yle.fi/%s.%s.js" % (chunkId, chunkHash), self.defaultParams)
                    match = PLAYER_KEY_RE.search(chunk) if sts else None
                    if match:
                        keys = (match.group(1), match.group(2))
                        break
            printDBG("YleAreena player keys from the site: %s" % (keys is not None))
            YleAreena.KEYS["player"] = keys or PLAYER_KEYS
        return YleAreena.KEYS["player"]

    def _withKeys(self, url, keys):
        return "%s%sapp_id=%s&app_key=%s" % (url, "&" if "?" in url else "?", keys[0], keys[1])

    def _getJson(self, url, keys=None):
        sts, data = self.cm.getPage(self._withKeys(url, keys or self._frontendKeys()), self.defaultParams)
        if not sts:
            return {}
        try:
            return json_loads(data) or {}
        except Exception:
            printExc()
        return {}

    def _getHtmlView(self, url):
        # the site pages carry their view (tabs -> lists) as Next.js page data
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return {}
        self._frontendKeys(data)
        match = NEXT_DATA_RE.search(data)
        if not match:
            return {}
        try:
            return ((json_loads(match.group(1)).get("props") or {}).get("pageProps") or {}).get("view") or {}
        except Exception:
            printExc()
        return {}

    def _getView(self, cItem):
        viewUrl = cItem.get("view_url", "")
        if viewUrl.startswith(API_URL):
            return self._getJson(viewUrl).get("data") or {}
        return self._getHtmlView(viewUrl)

    def _itemsUrl(self, lang, itemId):
        return "%s/v1/ui/views/items/%s.json?language=%s&v=10&client=yle-areena-web" % (API_URL, itemId, lang)

    @staticmethod
    def _labels(card):
        ret = {}
        for label in card.get("labels") or []:
            ret.setdefault(label.get("type", ""), []).append(label)
        return ret

    @staticmethod
    def _isGeo(region):
        return ensure_str(region or "").lower() in ("finland", "fi")

    def _setParam(self, url, key, value):
        if re.search(r'[?&]%s=' % re.escape(key), url):
            return re.sub(r'([?&]%s=)[^&]*' % re.escape(key), lambda m: m.group(1) + value, url)
        return "%s%s%s=%s" % (url, "&" if "?" in url else "?", key, value)

    ###################################################
    # rows
    ###################################################
    def _cardDesc(self, card, labels, geo):
        parts = []
        for label in labels.get("generic", []) + labels.get("duration", []):
            text = self.cleanHtmlStr(ensure_str(label.get("formatted") or ""))
            if text and text not in parts and "\n" not in text:
                parts.append(text)
        for label in labels.get("broadcastService", []):
            text = ensure_str(label.get("formatted") or "")
            if text and text not in parts:
                parts.append(text)
        if geo:
            parts.append("(geo FI)")
        line = " | ".join(parts)
        text = self.cleanHtmlStr(ensure_str(card.get("description") or ""))
        if text:
            return "%s[/br]%s" % (line, text) if line else text
        return line

    def _addCard(self, cItem, card, show="", season="", seriesGeo=False):
        pointer = card.get("pointer") or {}
        ptype = pointer.get("type", "")
        uri = ensure_str(pointer.get("uri") or "")
        labels = self._labels(card)
        title = self.cleanHtmlStr(ensure_str(card.get("title") or ""))
        region = ((labels.get("region") or [{}])[0]).get("raw", "")
        geo = self._isGeo(region) or (seriesGeo and not region)
        if geo and self._hideGeo():
            return False
        lang = self._lang(cItem)
        params = stripPagerKeys(dict(cItem), ("source", "geo_filter", "view_url", "tab", "season", "episode", "season_id", "item_id", "series_id"))
        params.update({"good_for_fav": True, "lang": lang, "icon": self._imageUrl(card.get("image")) or cItem.get("icon", ""),
                       "desc": self._cardDesc(card, labels, geo), "geo": geo, "live": False})
        if ptype == "series":
            match = ITEM_ID_RE.search(uri)
            if not match or not title:
                return False
            params.update({"category": "yle_series", "title": title, "s_title": title, "item_id": match.group(1),
                           "url": self._siteUrl(lang, "/" + match.group(1))})
            self.addDir(params)
            return True
        if ptype == "package":
            match = PACKAGE_ID_RE.search(uri)
            if not match or not title:
                return False
            params.update({"category": "yle_view", "title": title, "view_url": "%s/v1/ui/views/packages/%s.json?language=%s&v=10&client=yle-areena-web" % (API_URL, match.group(1), lang),
                           "url": self._siteUrl(lang, "/" + match.group(1))})
            self.addDir(params)
            return True
        if ptype == "player":
            # live channels of the schedules: the channel name is the row, the programme on air the description
            match = PLAYER_ID_RE.search(uri)
            if not match:
                return False
            channel = ensure_str(((card.get("overlayLogoImage") or {}).get("alt")) or ((labels.get("broadcastService") or [{}])[0]).get("formatted") or match.group(1))
            now = " ".join(x for x in (ensure_str(((labels.get("generic") or [{}])[0]).get("formatted") or ""), title) if x)
            params.update({"category": "yle_video", "title": channel, "item_id": match.group(1), "live": True,
                           "url": self._siteUrl(lang, "/" + match.group(1)), "desc": now})
            self.addVideo(params)
            return True
        if ptype not in ("program", "clip"):
            return False
        match = ITEM_ID_RE.search(uri)
        if not match or not title:
            return False
        itemId = match.group(1)
        episode = ""
        epName = title
        epMatch = EPISODE_RE.match(title)
        if show and epMatch:
            episode, epName = epMatch.group(1), epMatch.group(2)
        label = title
        if IsMediaNamingNormalized() and show and season and episode:
            label = "%s - %s - %s" % (show, formatSxxExx(season, episode), epName)
        params.update({"category": "yle_video", "title": label, "s_title": show or title, "item_id": itemId, "season": season, "episode": episode,
                       "url": self._siteUrl(lang, "/" + itemId)})
        self.addVideo(params)
        return True

    ###################################################
    # lists
    ###################################################
    def listLang(self, cItem):
        lang = self._lang(cItem)
        site = SITES[lang]
        base = {"good_for_fav": True, "lang": lang, "desc": ""}
        for category, title, path in (("yle_view", _("Home page"), "/tv"), ("yle_view", _("All programmes"), site["all"]),
                                      ("yle_view", _("Live channels"), site["live"])):
            params = dict(cItem)
            params.update(base)
            params.update({"category": category, "title": title, "view_url": self._siteUrl(lang, path), "url": self._siteUrl(lang, path)})
            self.addDir(params)

    def _viewLists(self, tab):
        lists = []
        for content in tab.get("content") or []:
            uri = ensure_str((content.get("source") or {}).get("uri") or "")
            if content.get("type") != "list" or not uri.startswith(API_URL) or "/profile/" in uri:
                continue
            geoFilter = False
            for flt in content.get("filters") or []:
                for option in flt.get("options") or []:
                    if "filter.geo_restricted" in (option.get("parameters") or {}):
                        geoFilter = True
            lists.append({"title": self.cleanHtmlStr(ensure_str(content.get("title") or "")), "source": uri, "geo_filter": geoFilter})
        return lists

    def _addList(self, cItem, lst, title):
        params = stripPagerKeys(dict(cItem), ("tab",))
        params.update({"good_for_fav": True, "category": "yle_list", "title": title, "source": lst["source"], "geo_filter": lst["geo_filter"], "desc": ""})
        self.addDir(params)

    def listView(self, cItem):
        printDBG("YleAreena.listView [%s]" % cItem.get("view_url", ""))
        view = self._getView(cItem)
        tabs = view.get("tabs") or []
        viewTitle = self.cleanHtmlStr(ensure_str(view.get("title") or ((view.get("header") or {}).get("title")) or "")) or cItem.get("title", "")
        if len(tabs) == 1 or cItem.get("tab") is not None:
            index = cItem.get("tab") or 0
            lists = self._viewLists(tabs[index]) if index < len(tabs) else []
            if len(lists) == 1 and not cItem.get("source"):
                # a package of one list: its items straight away
                item = dict(cItem, source=lists[0]["source"], geo_filter=lists[0]["geo_filter"])
                self.listItems(item)
                return
            seen = set()
            for lst in lists:
                title = lst["title"] or (_("Highlights") if not seen else viewTitle)
                if title in seen:
                    continue
                seen.add(title)
                self._addList(cItem, lst, title)
            return
        for index, tab in enumerate(tabs):
            lists = self._viewLists(tab)
            title = self.cleanHtmlStr(ensure_str(tab.get("title") or "")) or viewTitle
            if len(lists) == 1:
                self._addList(cItem, lists[0], title)
            elif lists:
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "yle_view", "title": title, "tab": index, "desc": ""})
                self.addDir(params)

    def _listUrl(self, cItem, page):
        url = cItem.get("source", "")
        if cItem.get("geo_filter") and self._hideGeo():
            url = self._setParam(url, "filter.geo_restricted", "false")
        return "%s&offset=%d&limit=%d" % (url, (page - 1) * PAGE_SIZE, PAGE_SIZE)

    def listItems(self, cItem, show="", season="", seriesGeo=False):
        page = max(1, int(cItem.get("page", 1) or 1))
        printDBG("YleAreena.listItems page %d [%s]" % (page, cItem.get("source", "")))
        data = self._getJson(self._listUrl(cItem, page))
        cards = data.get("data") or []
        for card in cards if isinstance(cards, list) else []:
            self._addCard(cItem, card, show, season, seriesGeo)
        total = int((data.get("meta") or {}).get("count", 0) or 0)
        lastPage = (total + PAGE_SIZE - 1) // PAGE_SIZE
        # API offset paging: the constant template only lets "Jump" through
        addPagingItems(self, dict(cItem, desc=""), page, bool(cards) and page < lastPage, lastPage, cItem.get("url") or self.MAIN_URL)

    def _seriesView(self, cItem):
        lang = self._lang(cItem)
        itemId = cItem.get("series_id") or cItem.get("item_id", "")
        data = self._getJson(self._itemsUrl(lang, itemId))
        return data.get("data") or {}, data.get("meta") or {}

    def _seriesGeo(self, view):
        for label in (view.get("header") or {}).get("labels") or []:
            if label.get("type") == "region":
                return self._isGeo(label.get("raw"))
        return False

    def listSeries(self, cItem):
        printDBG("YleAreena.listSeries [%s]" % cItem.get("item_id", ""))
        view = self._seriesView(cItem)[0]
        show = cItem.get("s_title", "") or self.cleanHtmlStr(ensure_str(view.get("title") or ""))
        seriesGeo = self._seriesGeo(view)
        episodes = None
        extras = []
        seen = set()
        for tabIndex, tab in enumerate(view.get("tabs") or []):
            for index, content in enumerate(tab.get("content") or []):
                uri = ensure_str((content.get("source") or {}).get("uri") or "")
                if content.get("type") != "list" or not uri.startswith(API_URL) or "/profile/" in uri:
                    continue
                if episodes is None:
                    # the first list: the episodes, with the seasons as a filter
                    seasons = []
                    for flt in content.get("filters") or []:
                        for option in flt.get("options") or []:
                            seasonId = ensure_str((option.get("parameters") or {}).get("path.season") or "")
                            if seasonId:
                                seasons.append((self.cleanHtmlStr(ensure_str(option.get("title") or "")), seasonId))
                    episodes = (uri, seasons)
                    continue
                # clips, extras, "see also": the tab name for its first list
                title = self.cleanHtmlStr(ensure_str(tab.get("title") if index == 0 and tab.get("title") else content.get("title") or tab.get("title") or ""))
                if self._isRecommendations(uri):
                    # "Se mer" / "Katso myös": other series Yle recommends (they recommend this one back) - not more episodes
                    title = _("Recommended")
                if title and title not in seen:
                    seen.add(title)
                    extras.append((title, uri))
        # the recommendations last
        extras.sort(key=lambda extra: extra[0] == _("Recommended"))
        if episodes is None:
            return
        uri, seasons = episodes
        page = max(1, int(cItem.get("page", 1) or 1))
        if page == 1 and len(seasons) <= 1:
            # one season: the extras before the episodes and their paging rows
            self._addSeriesExtras(cItem, show, extras)
        if len(seasons) > 1:
            for title, seasonId in seasons:
                number = re.search(r'(\d+)', title)
                params = stripPagerKeys(dict(cItem))
                params.update({"good_for_fav": True, "category": "yle_season", "title": "%s - %s" % (show, title), "s_title": show,
                               "series_id": cItem.get("item_id", ""), "season_id": seasonId, "season": number.group(1) if number else "",
                               "source": self._setParam(uri, "path.season", seasonId), "geo": seriesGeo, "desc": cItem.get("desc", "")})
                self.addDir(params)
            self._addSeriesExtras(cItem, show, extras)
            return
        # one season: the episodes in the series folder (its paging rows open the series folder again on the next page)
        number = re.search(r'(\d+)', seasons[0][0]) if seasons else None
        self.listItems(dict(cItem, source=uri), show, number.group(1) if number else "", seriesGeo)

    @staticmethod
    def _isRecommendations(uri):
        # a content list url carries its source in the JWT "token": areena-recommendations.api.yle.fi = "see also" rail
        token = re.search(r"[?&]token=[^.&]+\.([^.&]+)", uri)
        if not token:
            return False
        payload = token.group(1)
        try:
            payload = ensure_str(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        except Exception:
            return False
        return "recommendations" in payload

    def _addSeriesExtras(self, cItem, show, extras):
        for title, uri in extras:
            params = stripPagerKeys(dict(cItem), ("item_id",))
            params.update({"good_for_fav": True, "category": "yle_list", "title": "%s - %s" % (show, title), "source": uri, "geo_filter": False, "desc": ""})
            self.addDir(params)

    def listSeason(self, cItem):
        self.listItems(cItem, cItem.get("s_title", ""), cItem.get("season", ""), bool(cItem.get("geo")))

    def listSearchResult(self, cItem, searchPattern, searchType):
        searchPattern = searchPattern or cItem.get("search_pattern", "")
        lang = searchType if searchType in SITES else cItem.get("search_lang", LANGS[0])
        page = max(1, int(cItem.get("page", 1) or 1))
        printDBG("YleAreena.listSearchResult [%s] %s page %d" % (searchPattern, lang, page))
        url = "%s/v1/ui/search?query=%s&language=%s&v=10&client=yle-areena-web&service=tv&offset=%d&limit=%d" % (
            API_URL, urllib_quote_plus(searchPattern), lang, (page - 1) * PAGE_SIZE, PAGE_SIZE)
        data = self._getJson(url)
        cards = data.get("data") or []
        base = stripPagerKeys(dict(cItem))
        base.update({"lang": lang, "search_lang": lang, "search_pattern": searchPattern})
        for card in cards if isinstance(cards, list) else []:
            self._addCard(base, card)
        total = int((data.get("meta") or {}).get("count", 0) or 0)
        lastPage = (total + PAGE_SIZE - 1) // PAGE_SIZE
        nextItem = dict(base, category="search_next_page", desc="")
        addPagingItems(self, nextItem, page, bool(cards) and page < lastPage, lastPage, self._siteUrl(lang, "/haku"))

    ###################################################
    # links
    ###################################################
    def _itemId(self, cItem):
        itemId = cItem.get("item_id", "")
        if not itemId:
            match = URL_ID_RE.search(cItem.get("url", ""))
            itemId = match.group(1) if match else ""
        return itemId

    def getLinksForVideo(self, cItem):
        printDBG("YleAreena.getLinksForVideo [%s]" % cItem.get("item_id", ""))
        itemId = self._itemId(cItem)
        if not itemId:
            return []
        data = self._getJson(PREVIEW_URL % itemId, self._playerKeys()).get("data") or {}
        info = data.get("ongoing_ondemand") or data.get("ongoing_event") or data.get("ongoing_channel") or {}
        live = bool(cItem.get("live")) or "ongoing_ondemand" not in data
        if not info:
            if data.get("pending_event") or data.get("upcoming_event"):
                SetIPTVPlayerLastHostError(_("Not available yet"))
            elif data.get("gone"):
                SetIPTVPlayerLastHostError(_("Content not available"))
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        geo = self._isGeo(info.get("region"))
        geoMsg = _("This content is not available in your region.")
        if info.get("drm") or info.get("drm_type"):
            SetIPTVPlayerLastHostError(_("Video with DRM protection."))
            return []
        # films: the moviemeta lookup of their INFO (if opened) goes into the sidecar by itself
        sidecar = buildSidecarFromItem(cItem, IsSidecarEnabled(), self._preferredText(info.get("description"), self._lang(cItem)))
        mediaUrl = ensure_str(info.get("media_url") or "")
        if mediaUrl and not info.get("manifest_url"):
            return applySidecarToLinks([{"name": "MP3" if ".mp3" in mediaUrl else "Audio", "url": strwithmeta(mediaUrl, {"User-Agent": self.HEADER["User-Agent"]}), "need_resolve": 0}], sidecar)
        master = ensure_str(info.get("manifest_url") or "")
        if not master:
            SetIPTVPlayerLastHostError(geoMsg if geo else _("No stream available"))
            return []
        baseMeta = {"iptv_proto": "m3u8", "iptv_livestream": live, "User-Agent": self.HEADER["User-Agent"], "Referer": self.HEADER["Referer"]}
        subTracks = []
        for sub in info.get("subtitles") or []:
            subUrl = ensure_str(sub.get("uri") or "")
            if subUrl.startswith("http"):
                lang = ensure_str(sub.get("language") or "")
                subTracks.append({"title": " ".join(x for x in (lang, ensure_str(sub.get("kind") or "")) if x) or "Yle", "lang": lang[:2],
                                  "url": subUrl, "format": "vtt" if ".vtt" in subUrl else "srt"})
        if subTracks:
            baseMeta["external_sub_tracks"] = subTracks

        if live:
            # live channels carry several audio renditions (Finnish / Swedish ...): the master straight to the player
            if not self.cm.getPage(master, self.defaultParams)[0]:
                SetIPTVPlayerLastHostError(geoMsg if geo else _("No stream available"))
                return []
            return applySidecarToLinks([{"name": "HLS live", "url": strwithmeta(master, baseMeta), "need_resolve": 0}], sidecar)

        urlTab = []
        for item in getDirectM3U8Playlist(strwithmeta(master, dict(baseMeta)), checkExt=False, checkContent=True):
            if not item.get("height"):
                # the audio-only variant
                continue
            # the variant urls carry the master's meta (headers, subtitles of the preview + the HLS subtitle renditions)
            url = item["url"]
            fps = re.search(r'\s([\d.]+)fps', item.get("name", ""))
            # "[swe] ..." when the master has separate audio renditions (merged per language)
            audio = re.match(r'^(\[[^\]]+\])\s', item.get("name", ""))
            name = "%s %sp" % (audio.group(1), item["height"]) if audio else "%sp" % item["height"]
            urlTab.append({"name": name, "url": url, "need_resolve": 0, "bitrate": item.get("bitrate", 0),
                           "fps": fps.group(1) if fps else ""})
        names = [x["name"] for x in urlTab]
        for item in urlTab:
            # 720p at 25 and at 50 frames (sport): the frame rate (else the bitrate) tells them apart
            fps = item.pop("fps", "")
            if names.count(item["name"]) > 1:
                item["name"] = "%s %sfps" % (item["name"], fps) if fps else "%s %dk" % (item["name"], int(item.get("bitrate") or 0) // 1000)
        if not urlTab:
            SetIPTVPlayerLastHostError(geoMsg if geo else _("No stream available"))
            return []
        urlTab.sort(key=lambda x: int(x.get("bitrate") or 0), reverse=True)
        return applySidecarToLinks(urlTab, sidecar)

    def getVideoLinks(self, videoUrl):
        return []

    ###################################################
    # info / favourites
    ###################################################
    @staticmethod
    def _preferredText(value, lang):
        if isinstance(value, dict):
            return ensure_str(value.get({"sv": "swe", "fi": "fin"}.get(lang, "fin")) or value.get("fin") or value.get("swe") or "")
        return ensure_str(value or "")

    def getArticleContent(self, cItem):
        printDBG("YleAreena.getArticleContent [%s]" % cItem.get("item_id", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "").replace("[/br]", "\n")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("live"):
            otherInfo["status"] = _("Live")
            return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]
        try:
            view, meta = self._seriesView(cItem)
            header = view.get("header") or {}
            text = self.cleanHtmlStr(ensure_str(header.get("description") or meta.get("description") or "")) or text
            icon = self._imageUrl(meta.get("image"), 800) or icon
            genres = []
            for label in header.get("labels") or []:
                ltype = label.get("type", "")
                formatted = ensure_str(label.get("formatted") or "").strip()
                if ltype == "duration" and formatted:
                    otherInfo["duration"] = formatted
                elif ltype == "contentRating.ageRestriction" and formatted:
                    otherInfo["age_limit"] = formatted
                elif ltype == "region":
                    otherInfo["status"] = (_("Only available in %s") % "Finland") if self._isGeo(label.get("raw")) else _("Available worldwide")
                elif ltype == "generic" and formatted:
                    if "\n" in formatted:
                        head, value = formatted.split("\n", 1)
                        if label.get("raw") and re.match(r'^\d{4}-\d\d-\d\d', ensure_str(label["raw"])):
                            otherInfo["released"] = value
                        elif re.match(r'^[\d\s]+$', value):
                            otherInfo["views"] = re.sub(r"\s", "", value)
                        else:
                            otherInfo["remaining"] = "%s %s" % (head, value)
                        continue
                    pair = INFO_PAIR_RE.match(formatted)
                    if pair:
                        key = pair.group(1).strip().lower()
                        if key.startswith(("bild", "kuva")):
                            otherInfo["quality"] = pair.group(2)
                        elif key.startswith(("ljud", "ääni")):
                            otherInfo["language"] = pair.group(2)
                        elif key.startswith(("textning", "tekstitys")):
                            otherInfo["subtitles"] = pair.group(2)
                        continue
                    if re.search(r'(?i)finland|utomlands|suomessa|ulkomailla', formatted) or re.search(r'\d', formatted):
                        continue
                    genres.append(formatted)
            if genres:
                otherInfo["genres"] = ", ".join(genres)
            if cItem.get("category") == "yle_season" and cItem.get("season"):
                otherInfo["seasons"] = cItem["season"]
            year = YEAR_RE.findall(text) if meta.get("ogType") == "video.movie" else []
            if year:
                # films with a year: Yle's text and fields stay, moviemeta adds rating / cast / director
                metaTitle = self.cleanHtmlStr(ensure_str(meta.get("title") or view.get("title") or cItem.get("s_title", "")))
                otherInfo.setdefault("year", year[-1])
                try:
                    movie = getMeta("movie", metaTitle, year[-1])
                except Exception:
                    printExc()
                    movie = {}
                for key, value in (movie.get("info", {}) or {}).items():
                    if value:
                        otherInfo.setdefault(key, value)
        except Exception:
            printExc()
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("yle_"):
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
        printDBG("YleAreena.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "yle_lang":
            self.listLang(self.currItem)
        elif category == "yle_view":
            self.listView(self.currItem)
        elif category == "yle_list":
            self.listItems(self.currItem)
        elif category == "yle_series":
            self.listSeries(self.currItem)
        elif category == "yle_season":
            self.listSeason(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, YleAreena(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("yleareena")

    def getSearchTypes(self):
        return [("Svenska", "sv"), ("Suomi", "fi")]

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("yle_series", "yle_season", "yle_video")
