# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host: PelisPlusHD (Spanish films, series, anime and doramas, Latino / Castellano /
#   Subtitulado; own domain in the settings). The hoster links are in the page (data-url / span url) -> urlparser.
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.pelisplushd_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.pelisplushd_alt_domain)]


def gettytul():
    return "https://pelisplushd.la/"


# site paths: urls of an older address (favourites, history) are moved to the current one
SITE_PATH_RE = re.compile(r"^https?://[^/]+/((?:pelicula|peliculas|serie|series|anime|animes|generos|year|search|poster)(?:[/?].*)?)$")
CARD_RE = re.compile(r'(?s)<a href="([^"]+)" class="Posters-link"(.*?)</a>')
EPISODE_URL_RE = re.compile(r"""href=["']\s*((?:https?://[^/"']+)?/(?:serie|anime)/[^/"']+/temporada/(\d+)/capitulo/(\d+))\s*["']""")
# some texts of the site are UTF-8 that was read as cp1252 and stored again (e.g. "Pel" + U+00C3 U+00AD + "cula"):
# a lead char of a UTF-8 sequence (U+00C2-U+00F4) followed by 1-3 continuation bytes as cp1252 shows them
CP1252_HIGH = (0x20AC, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0x017D,
               0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0x017E, 0x0178)
MOJIBAKE_RE = re.compile(u"[%c-%c][%c-%c%s]{1,3}" % (0xC2, 0xF4, 0xA0, 0xBF, u"".join(u"%c" % c for c in CP1252_HIGH)))
VIDEO_CATEGORIES = ("video",)
FOLDER_CATEGORIES = ("list_seasons", "list_episodes")


def _fixRun(match):
    run = match.group(0)
    try:
        return run.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return run


def fixText(text):
    # undoes the double encoding of the site (text of str type in, same type out)
    if not text:
        return text
    try:
        isBytes = isinstance(text, bytes)
        utext = text.decode("utf-8") if isBytes else text
        fixed = MOJIBAKE_RE.sub(_fixRun, utext)
        return fixed.encode("utf-8") if isBytes else fixed
    except Exception:
        printExc()
    return text


def languageLabel(name):
    # "Español Latino" -> Latino, "Español" -> Castellano, "Subtitulado" -> Subtitulado
    low = (name or "").lower()
    if "latino" in low:
        return "Latino"
    if "sub" in low:
        return "Subtitulado"
    if "espa" in low or "castellano" in low:
        return "Castellano"
    return name


class PelisPlusHD(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "pelisplushd", "cookie": "pelisplushd.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.pelisplushd_alt_domain.value.strip()
        if not self.setMainUrl(domain if domain.endswith("/") else domain + "/"):
            self.MAIN_URL = gettytul()
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("pelisplushd")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        match = SITE_PATH_RE.match(baseUrl or "")
        if match:
            baseUrl = self.getMainUrl() + match.group(1)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def clean(self, text):
        return fixText(self.cleanHtmlStr(text))

    @staticmethod
    def _key(url):
        return re.sub(r"^https?://[^/]+", "", url or "").rstrip("/")

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("list_items",):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            key = self._key(cItem.get("url", ""))
            if not key:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                return "video:%s" % key
            if category in FOLDER_CATEGORIES:
                return "folder:%s" % key
        except Exception:
            printExc()
        return ""

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _pageUrl(url, page):
        # <list>?page=<n> (search: ?s=..&page=<n>)
        url = re.sub(r"[?&]page=\d+", "", url)
        if page <= 1 and "?s=" not in url:
            return url
        return "%s%spage=%s" % (url, "&" if "?" in url else "?", page)

    def _episodeTitle(self, show, season, episode):
        if IsMediaNamingNormalized():
            return "%s - %s" % (show, formatSxxExx(season, episode))
        return "%s %dx%d" % (show, season, episode)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("peliculas")},
                {"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("peliculas/estrenos")},
                {"category": "list_items", "title": _("Popular movies"), "url": self.getFullUrl("peliculas/populares")},
                {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("series")},
                {"category": "list_items", "title": _("Popular series"), "url": self.getFullUrl("series/populares")},
                {"category": "list_items", "title": _("Anime"), "url": self.getFullUrl("animes")},
                {"category": "list_items", "title": "Doramas", "url": self.getFullUrl("generos/dorama")},
                {"category": "list_filters", "title": _("Genres"), "filter": "generos"},
                {"category": "list_filters", "title": _("Year"), "filter": "year"}]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listFilters(self, cItem):
        # genres / years of the site menu
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        kind = cItem.get("filter", "generos")
        seen = set()
        items = re.findall(r'<a href="(/%s/[^"/]+)">([^<]+)</a>' % kind, data)
        if kind == "year":
            items.sort(key=lambda x: x[1], reverse=True)
        for url, title in items:
            if url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": self.clean(title), "url": self.getFullUrl(url)})

    def _addCard(self, url, block, normalize):
        title = self.clean(self.cm.ph.getSearchGroups(block, r'(?s)<div class="listing-content">\s*<p>(.*?)</p>')[0])
        if not url or not title:
            return False
        url = self.getFullUrl(url)
        year = self.cm.ph.getSearchGroups(title, r"\s\(((?:19|20)\d{2})\)$")[0]
        if year:
            title = title[:-7].strip()
        icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
        rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="stars">.*?<span>([^<]+)</span>')[0])
        kind = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="series centrado">(.*?)</div>')[0])
        desc = " | ".join(x for x in (kind, year, rating if rating not in ("0.0/10", "") else "") if x)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon) if icon else "", "desc": desc}
        if re.search(r"/(?:serie|anime)/", url):
            params.update({"category": "list_seasons", "title": title, "s_title": title, "meta_type": "tv", "meta_title": title, "meta_year": year})
            self.addDir(params)
        else:
            params.update({"category": "video", "title": "%s (%s)" % (title, year) if (year and normalize) else title,
                           "meta_type": "movie", "meta_title": title, "meta_year": year})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        page = self._page(cItem)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = self._pageUrl(baseUrl, page)
        printDBG("PelisPlusHD.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        count, seen = 0, set()
        for itemUrl, block in CARD_RE.findall(data):
            if itemUrl in seen:
                continue
            seen.add(itemUrl)
            if self._addCard(itemUrl, block, normalize):
                count += 1
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', "</ul>", False)[1]
        pages = [int(p) for p in re.findall(r'class="page-link"[^>]*>(\d+)<', pager)]
        lastPage = max(pages) if pages else 0
        hasNext = bool(count) and lastPage > page
        nextItem = dict(cItem, base_url=baseUrl)
        addPagingItems(self, nextItem, page, hasNext, lastPage, self._pageUrl(baseUrl, 987654).replace("987654", "{page}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        item = dict(cItem, category="search_next_page", s_pattern=pattern, base_url=self.getFullUrl("search?s=%s" % urllib_quote_plus(pattern)))
        self.listItems(item)

    @staticmethod
    def _seasons(data):
        # {season: [(episode, url)]} of a series / anime page
        seasons = {}
        for url, season, episode in EPISODE_URL_RE.findall(data):
            episodes = seasons.setdefault(int(season), [])
            if int(episode) not in [e for e, _u in episodes]:
                episodes.append((int(episode), url))
        for episodes in seasons.values():
            episodes.sort()
        return seasons

    def listSeasons(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._seasons(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        if len(seasons) == 1:
            season = list(seasons.keys())[0]
            self._addEpisodes(cItem, show, season, seasons[season])
            return
        base = cItem["url"].split("#")[0]
        for season in sorted(seasons):
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "list_episodes", "good_for_fav": True, "url": "%s#s%d" % (base, season),
                           "title": "%s - %s" % (show, formatSxxExx(season)) if IsMediaNamingNormalized() else "%s - %s %d" % (show, _("Season"), season),
                           "s_title": show, "s_season": season, "desc": "%s: %d" % (_("Episodes"), len(seasons[season]))})
            self.addDir(params)

    def listEpisodes(self, cItem):
        sts, data = self.getPage(cItem["url"].split("#")[0])
        if not sts:
            return
        season = cItem.get("s_season", 1)
        episodes = self._seasons(data).get(season)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        self._addEpisodes(cItem, cItem.get("s_title") or cItem.get("title", ""), season, episodes)

    def _addEpisodes(self, cItem, show, season, episodes):
        for episode, url in episodes:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "video", "good_for_fav": True, "url": self.getFullUrl(url),
                           "title": self._episodeTitle(show, season, episode), "desc": "%dx%d" % (season, episode),
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv", "meta_title": show})
            params.pop("meta_year", None)
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def _players(self, data):
        # [(label, language, hoster url)] of a film / episode page
        players = []
        # films: <li data-url="https://voe.sx/e/.." data-name="Español Latino" class="playurl"> <a href="#option3">voesx</a>
        for url, lang, label in re.findall(r'(?s)<li[^>]+data-url="([^"]+)"[^>]+data-name="([^"]*)"[^>]*>(.*?)</li>', data):
            players.append((self.cleanHtmlStr(label), languageLabel(self.cleanHtmlStr(lang)), url))
        # episodes: <li data-id="3"><a href="#option3">voesx</a></li> .. <span lid="3" url="https://voe.sx/e/.."></span>,
        # one language for the page (<a class="divseason">.. Español Latino</a>)
        lang = languageLabel(self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<a class="divseason"[^>]*>(.*?)</a>')[0]))
        labels = dict(re.findall(r'(?s)<li[^>]+data-id="(\d+)"[^>]*>(.*?)</li>', data))
        for lid, url in re.findall(r'<span lid="(\d+)" url="([^"]+)"', data):
            players.append((self.cleanHtmlStr(labels.get(lid, "")), lang, url))
        # older pages: var video = []; video[1] = 'https://..';
        for url in re.findall(r"""video\[\d+\]\s*=\s*['"](https?://[^'"]+)['"]""", data):
            players.append(("", lang, url))
        return players

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("PelisPlusHD.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab, seen = [], set()
        for label, lang, playerUrl in self._players(data):
            playerUrl = self.getFullUrl(playerUrl.replace("&amp;", "&").strip())
            if not self.cm.isValidUrl(playerUrl) or playerUrl in seen:
                continue
            seen.add(playerUrl)
            if self.up.checkHostSupport(playerUrl) != 1:
                printDBG("PelisPlusHD.getLinksForVideo unsupported hoster [%s]" % playerUrl)
                continue
            name = label[:1].upper() + label[1:] if label else self.up.getHostName(playerUrl)
            urltab.append({"name": "%s - %s" % (name, lang) if lang else name, "url": strwithmeta(playerUrl, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        # an episode can have two "Netu - Latino" servers: number the repeated names
        names = [item["name"] for item in urltab]
        for idx, item in enumerate(urltab):
            if names.count(item["name"]) > 1:
                item["name"] = "%s %d" % (item["name"], names[:idx + 1].count(item["name"]))
        info = self._siteInfo(data)
        mediaType, metaTitle, year = self._metaArgs(cItem, info)
        metaQuery = sidecarMetaQuery(mediaType, metaTitle, year, skip=())
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info.get("_story", ""), metaQuery))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("PelisPlusHD.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # INFO fields of a film / series / episode page; "_" keys are no INFO fields
        info = {}
        story = self.clean(self.cm.ph.getSearchGroups(data, r'(?s)<b>Sinopsis:</b>\s*</p>\s*<div class="text-large">(.*?)</div>')[0])
        # series / episode pages start with "Ver <show> Temporada 1 Episodio 1 en Latino, ... Online Gratis | Cuevana3."
        info["_story"] = re.sub(r"^Ver\s.{0,200}?\sOnline Gratis(?:\s*\|[^.]*)?\.\s*", "", story)
        info["_poster"] = self.cm.ph.getSearchGroups(data, r'<img class="img-fluid[^"]*" src="([^"]+)"')[0]
        for label, value in re.findall(r'(?s)<div class="sectionDetail[^"]*">\s*<span[^>]*>([^<]+):</span>(.*?)</div>', data):
            key = {"actores": "actors", "director": "director", "escritor": "writer", "pais": "country", "fecha de estreno": "year"}.get(self.cleanHtmlStr(label).lower())
            value = ", ".join(x for x in (self.clean(v) for v in re.findall(r"(?s)<a[^>]*>(.*?)</a>", value)) if x) or self.clean(value)
            if key and value:
                if key == "actors":
                    value = ", ".join(sorted(set(value.split(", ")), key=value.split(", ").index))
                info[key] = value
        genres = [self.clean(x) for x in re.findall(r'<a title="[^"]*" href="/generos/[^"]+">([^<]+)</a>', data)]
        if genres:
            info["genres"] = ", ".join(genres)
        rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)ion-md-star">\s*([\d.]+/10)\s*</span>\s*<small class="d-block">Rating')[0])
        if rating and rating != "0.0/10":
            info["rating"] = rating
        others = self.clean(self.cm.ph.getSearchGroups(data, r'(?s)<b>Otros Titulos:</b></p>\s*<div class="text-large">(.*?)</div>')[0])
        if others:
            info["alternate_title"] = others
        return info

    @staticmethod
    def _metaArgs(cItem, info):
        # moviemeta query of INFO (type, title, year): no year for an episode (the show's lookup)
        year = "" if cItem.get("s_episode") else (cItem.get("meta_year") or info.get("year", ""))
        return cItem.get("meta_type") or "movie", cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", ""), year

    def getArticleContent(self, cItem):
        printDBG("PelisPlusHD.getArticleContent [%s]" % cItem.get("url", ""))
        info = {}
        sts, data = self.getPage(cItem.get("url", "").split("#")[0])
        if sts:
            info = self._siteInfo(data)
        story, poster = info.pop("_story", ""), info.pop("_poster", "")
        mediaType, metaTitle, year = self._metaArgs(cItem, info)
        meta = {}
        try:
            if metaTitle:
                meta = getMeta(mediaType, metaTitle, year)
        except Exception:
            printExc()
        meta = meta or {}
        info.update(meta.get("info", {}))
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in info:
                info.pop(siteKey, None)
        plot = meta.get("plot", "")
        text = story or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        else:
            text = text or plot
        icon = meta.get("poster", "") or (self.getFullIconUrl(poster) if poster else "") or cItem.get("icon", "")
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
        printDBG("PelisPlusHD.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "list_filters":
            self.listFilters(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
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
        CHostBase.__init__(self, PelisPlusHD(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("pelisplushd")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
