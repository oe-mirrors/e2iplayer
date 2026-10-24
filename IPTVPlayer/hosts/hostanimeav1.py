# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
#   AnimeAV1 (anime with Spanish subtitles, some Latino dubs; SvelteKit site): latest episodes, latest anime,
#   the catalogue (airing / TV / movies / OVA / specials / ONA / genres / year / A-Z, First / Jump / Next page)
#   and search, all read from the pages' __data.json; anime -> episodes, films are VIDEO rows
#   links: the episode's embeds (SUB / DUB lists: voe, mp4upload, byse, ...) handed to urlparser
import re
from datetime import date

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.animeav1_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.animeav1_alt_domain)]


def gettytul():
    return "https://animeav1.com/"


CDN_URL = "https://cdn.animeav1.com/"
LOCAL_PAGE_SIZE = 100
# "Black Clover 2nd Season" / "... Season 2" -> season 2
SEASON_RE = re.compile(r"(?i)\s*\b(?:(\d+)(?:st|nd|rd|th)\s+season|season\s*(\d+))\b")
ROMAN_RE = re.compile(r"\s+(II|III|IV|V|VI)$")
ROMAN = {"II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
# media.status of the site
STATUS = {0: "Finalizado", 1: "Próximamente", 2: "En emisión"}
VIDEO_CATEGORIES = ("av1_video",)
FOLDER_CATEGORIES = ("av1_series",)


def _splitSeason(title):
    # -> (name without the season tag, season number or 0)
    title = (title or "").strip()
    match = SEASON_RE.search(title)
    if match:
        name = (title[:match.start()] + title[match.end():]).strip(" -:")
        return (name or title), int(match.group(1) or match.group(2))
    match = ROMAN_RE.search(title)
    if match:
        return title[:match.start()].strip(), ROMAN[match.group(1)]
    return title, 0


def _metaTitle(name):
    return re.sub(r"\s*\((?:TV|\d{4})\)\s*$", "", name or "").strip()


def _isFilm(category):
    # the category of a media: {"id": 2, "slug": "pelicula"} (the start page's lists carry the id only)
    return category.get("slug") == "pelicula" or category.get("id") == 2


def _num(value):
    # 3 / 3.0 -> "3"; 12.5 -> "12.5"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return str(int(number)) if number == int(number) else str(number)


def _hydrate(values):
    # SvelteKit "devalue" payload: one flat array, objects and arrays hold indexes into it, values[0] is the root;
    # negative indexes are undefined / NaN / ... and lists starting with a type name ("Date", "Set") typed values
    cache = {}

    def get(index):
        if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= len(values):
            return None
        if index in cache:
            return cache[index]
        value = values[index]
        if isinstance(value, dict):
            out = {}
            cache[index] = out
            for key, child in value.items():
                out[key] = get(child)
            return out
        if isinstance(value, list):
            if value and not isinstance(value[0], int):
                return get(value[1]) if len(value) > 1 and isinstance(value[1], int) else (value[1] if len(value) > 1 else None)
            out = []
            cache[index] = out
            out.extend(get(child) for child in value)
            return out
        return value
    return get(0)


class AnimeAV1(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "series_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "animeav1", "cookie": "animeav1.cookie"})
        self.selectDomain()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/animeav1135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("animeav1")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def selectDomain(self):
        domain = config.plugins.iptvplayer.animeav1_alt_domain.value.strip()
        if not self.cm.isValidUrl(domain):
            domain = gettytul()
        self.MAIN_URL = domain.rstrip("/") + "/"

    def _rebase(self, url):
        # urls of favourites / lists of a previous domain -> the current one
        url = (url or "").replace("&amp;", "&").strip()
        match = re.match(r"^https?://[^/]+/(.*)$", url)
        if match:
            return self.MAIN_URL + match.group(1)
        return self.getFullUrl(url)

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def _getData(self, url):
        # the page's own data: <page url>/__data.json (SvelteKit) -> the hydrated object of its last data node
        url = self._rebase(url)
        path, _sep, query = url.partition("?")
        sts, data = self.getPage("%s/__data.json%s" % (path.rstrip("/"), "?" + query if query else ""))
        if not sts:
            return {}
        try:
            # the page's node is the last one ({"type": "error", "status": 404} for an episode without video)
            node = (json_loads(data).get("nodes") or [None])[-1]
            # ensure_str_deep: the texts as UTF-8 str on Python 2 (json gives unicode there)
            result = _hydrate(ensure_str_deep(node.get("data") or [])) if isinstance(node, dict) and node.get("type") == "data" else {}
            return result if isinstance(result, dict) else {}
        except Exception:
            printExc()
        return {}

    @staticmethod
    def _path(url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", url or "").split("#")[0].rstrip("/")

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES:
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                return "video:%s" % path
            if category in FOLDER_CATEGORIES:
                return "folder:%s" % path
        except Exception:
            printExc()
        return ""

    @staticmethod
    def _episodeTitle(show, season, episode):
        if IsMediaNamingNormalized() and re.match(r"^\d+$", episode):
            return "%s - %s" % (show, formatSxxExx(season or 1, episode))
        return "%s - %s %s" % (show, _("Episode"), episode)

    @staticmethod
    def _filmTitle(title, year):
        if year and IsMediaNamingNormalized() and not title.endswith("(%s)" % year):
            return "%s (%s)" % (title, year)
        return title

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        catalogue = self.getFullUrl("catalogo")
        menu = [
            {"category": "av1_latest", "title": _("Latest episodes"), "url": self.MAIN_URL},
            {"category": "av1_new", "title": _("Latest added"), "url": self.MAIN_URL},
            {"category": "av1_list", "title": _("Airing now"), "url": catalogue + "?status=emision"},
            {"category": "av1_list", "title": _("Anime list"), "url": catalogue},
            {"category": "av1_list", "title": _("TV series"), "url": catalogue + "?category=tv-anime"},
            {"category": "av1_list", "title": _("Anime Movies"), "url": catalogue + "?category=pelicula"},
            {"category": "av1_list", "title": "OVA", "url": catalogue + "?category=ova"},
            {"category": "av1_list", "title": "ONA", "url": catalogue + "?category=ona"},
            {"category": "av1_list", "title": _("Specials"), "url": catalogue + "?category=especial"},
            {"category": "av1_filter", "title": _("Genres"), "url": catalogue, "filter": "genre"},
            {"category": "av1_filter", "title": _("Year"), "url": catalogue, "filter": "year"},
            {"category": "av1_filter", "title": _("A-Z"), "url": catalogue, "filter": "letter"},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listFilter(self, cItem):
        which = cItem.get("filter", "")
        catalogue = self.getFullUrl("catalogo")
        rows = []
        if which == "letter":
            rows = [(letter, "letter=%s" % letter) for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
        else:
            data = self._getData(cItem["url"])
            if which == "genre":
                genres = [g for g in (data.get("genresIdsMap") or {}).values() if isinstance(g, dict) and g.get("slug")]
                rows = [(g.get("name", ""), "genre=%s" % g["slug"]) for g in sorted(genres, key=lambda g: g.get("name", ""))]
            elif which == "year":
                years = data.get("years") or []
                try:
                    first, last = int(years[0]), int(years[1])
                except (IndexError, TypeError, ValueError):
                    first, last = 1990, date.today().year
                rows = [(str(year), "minYear=%d&maxYear=%d" % (year, year)) for year in range(last, first - 1, -1)]
        for title, query in rows:
            self.addDir({"name": "category", "category": "av1_list", "good_for_fav": True, "title": title, "url": "%s?%s" % (catalogue, query)})

    def _cover(self, mediaId):
        return "%scovers/%s.jpg" % (CDN_URL, mediaId) if mediaId else ""

    def _addMedia(self, media):
        slug = media.get("slug", "")
        title = (media.get("title") or "").strip()
        if not slug or not title:
            return False
        category = media.get("category") or {}
        name, season = _splitSeason(title)
        desc = " | ".join(x for x in (category.get("name", ""), (media.get("startDate") or "")[:4]) if x)
        synopsis = (media.get("synopsis") or "").strip()
        if synopsis:
            desc = "%s[/br]%s" % (desc, synopsis) if desc else synopsis
        params = {"name": "category", "good_for_fav": True, "url": self.getFullUrl("media/%s" % slug), "icon": self._cover(media.get("id")),
                  "desc": desc, "meta_title": _metaTitle(name)}
        if _isFilm(category):
            year = (media.get("startDate") or "")[:4]
            params.update({"category": "av1_video", "title": self._filmTitle(title, year), "meta_type": "movie", "meta_year": year})
            self.addVideo(params)
        else:
            params.update({"category": "av1_series", "title": title, "s_title": name, "s_season": season or 1, "meta_type": "tv"})
            self.addDir(params)
        return True

    def listLatest(self, cItem):
        data = self._getData(cItem["url"])
        for episode in data.get("latestEpisodes") or []:
            if not isinstance(episode, dict):
                continue
            media = episode.get("media") or {}
            number = _num(episode.get("number"))
            if not media.get("slug") or not number:
                continue
            name, season = _splitSeason(media.get("title", ""))
            self.addVideo({"name": "category", "category": "av1_video", "good_for_fav": True,
                           "url": self.getFullUrl("media/%s/%s" % (media["slug"], number)),
                           "icon": "%sthumbnails/%s.jpg" % (CDN_URL, media.get("id")) if media.get("id") else "",
                           "title": self._episodeTitle(name, season, number), "s_title": name, "s_season": season or 1,
                           "s_episode": number, "meta_type": "tv", "meta_title": _metaTitle(name),
                           "series_url": self.getFullUrl("media/%s" % media["slug"])})

    def listNew(self, cItem):
        data = self._getData(cItem["url"])
        for media in data.get("latestMedia") or []:
            if isinstance(media, dict):
                self._addMedia(media)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        pageTpl = "%s%spage={page}" % (baseUrl.replace("{", "{{").replace("}", "}}"), "&" if "?" in baseUrl else "?")
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("AnimeAV1.listItems [%s]" % url)
        data = self._getData(url)
        count = 0
        for media in data.get("results") or []:
            if isinstance(media, dict) and self._addMedia(media):
                count += 1
        try:
            lastPage = int((data.get("pagination") or {}).get("totalPages") or 0)
        except (TypeError, ValueError):
            lastPage = 0
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, bool(count) and lastPage > page, lastPage, pageTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        cItem = dict(cItem)
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        base = self.getFullUrl("catalogo?search=%s" % urllib_quote_plus(pattern))
        if cItem.get("category") != "search_next_page":
            cItem.update({"page": 1, "base_url": base})
        cItem.update({"category": "search_next_page", "url": base, "base_url": cItem.get("base_url") or base, "s_pattern": pattern})
        self.listItems(cItem)

    def listEpisodes(self, cItem):
        printDBG("AnimeAV1.listEpisodes [%s]" % cItem.get("url", ""))
        media = self._getData(cItem["url"]).get("media") or {}
        slug = media.get("slug") or self.cm.ph.getSearchGroups(cItem["url"], r"/media/([^/?#]+)")[0]
        numbers = sorted(set(_num((e or {}).get("number")) for e in media.get("episodes") or [] if _num((e or {}).get("number"))), key=float)
        if not numbers:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for number in numbers[start:start + LOCAL_PAGE_SIZE]:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "av1_video", "good_for_fav": True,
                           "url": self.getFullUrl("media/%s/%s" % (slug, number)), "title": self._episodeTitle(show, season, number),
                           "icon": "%sscreenshots/%s/%s.jpg" % (CDN_URL, media["id"], number) if media.get("id") else cItem.get("icon", ""),
                           "series_url": cItem["url"], "s_title": show, "s_season": season, "s_episode": number, "meta_type": "tv"})
            self.addVideo(params)
        if len(numbers) > LOCAL_PAGE_SIZE:
            lastPage = (len(numbers) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            # the page lives in cItem["page"] - the template keeps the media url unchanged (Jump row)
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        if re.search(r"/media/[^/?#]+/?$", url):
            # a film row is the media page: its video is episode 1
            url = url.rstrip("/") + "/1"
        printDBG("AnimeAV1.getLinksForVideo [%s]" % url)
        embeds = self._getData(url).get("embeds") or {}
        urltab, seen = [], set()
        # subtitled first, then the dubs
        for variant in sorted(embeds.keys(), key=lambda v: (v != "SUB", v)):
            for embed in embeds.get(variant) or []:
                playerUrl = ((embed or {}).get("url") or "").strip()
                if not self.cm.isValidUrl(playerUrl) or playerUrl in seen:
                    continue
                seen.add(playerUrl)
                if self.up.checkHostSupport(playerUrl) != 1:
                    printDBG("AnimeAV1.getLinksForVideo unsupported hoster [%s]" % playerUrl)
                    continue
                name = embed.get("server") or self.up.getHostName(playerUrl)
                if "zilla-networks." in playerUrl or "mp4upload." in playerUrl:
                    # the site's own encodes ("HLS" server, MP4Upload files) are AV1 - most receivers play them with
                    # sound only (box log 24.10.2026); Voe / Byse / UPNShare serve H.264
                    name += " AV1"
                urltab.append({"name": "%s [%s]" % (name, variant), "url": strwithmeta(playerUrl, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        # AV1 last: an automatic pick of the first link must not land on it
        urltab.sort(key=lambda item: " AV1 [" in item["name"])
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        mediaType, metaTitle, year = self._metaArgs(cItem)
        metaQuery = sidecarMetaQuery(mediaType, metaTitle, year, skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), "", metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("AnimeAV1.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    @staticmethod
    def _metaArgs(cItem, siteYear=""):
        # moviemeta query of INFO (type, title, year): no year for an episode (the show's lookup)
        year = "" if cItem.get("s_episode") else (cItem.get("meta_year") or siteYear)
        return cItem.get("meta_type") or "tv", cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", ""), year

    def _siteInfo(self, media):
        # (story, poster, {INFO fields}, [other titles]) of a media object
        info = {}
        aka = [(v or "").strip() for k, v in sorted((media.get("aka") or {}).items()) if v]
        if aka:
            info["alternate_title"] = ", ".join(aka)
        category = media.get("category") or {}
        if category.get("name"):
            info["type"] = category["name"]
        year = (media.get("startDate") or "")[:4]
        if year.isdigit():
            info["year"] = year
            info["released"] = media.get("startDate")
        status = STATUS.get(media.get("status"))
        if status:
            info["status"] = status
        genres = ", ".join(g.get("name", "") for g in media.get("genres") or [] if isinstance(g, dict) and g.get("name"))
        if genres:
            info["genres"] = genres
        if media.get("episodesCount") and not _isFilm(category):
            info["episodes"] = str(media["episodesCount"])
        if media.get("score"):
            info["rating"] = str(media["score"])
        if media.get("runtime"):
            info["duration"] = "%s min" % media["runtime"]
        # the English / romaji names first: the movie databases know these
        others = [v for k, v in sorted((media.get("aka") or {}).items(), key=lambda kv: kv[0] != "en-us") if v and not k.startswith(("ja", "zh", "ko"))]
        return (media.get("synopsis") or "").strip(), self._cover(media.get("id")), info, others

    def getArticleContent(self, cItem):
        url = cItem.get("series_url") or cItem.get("url", "")
        if re.search(r"/media/[^/?#]+/[^/?#]+$", url):
            url = url.rsplit("/", 1)[0]
        printDBG("AnimeAV1.getArticleContent [%s]" % url)
        media = self._getData(url).get("media") or {}
        story, poster, info, others = self._siteInfo(media) if media else ("", "", {}, [])
        mediaType, metaTitle, year = self._metaArgs(cItem, info.get("year", ""))
        meta = {}
        try:
            for title in [t for t in [metaTitle] + [x for x in others if x != metaTitle][:2] if t]:
                meta = getMeta(mediaType, _metaTitle(_splitSeason(title)[0]) if title != metaTitle else title, year)
                if meta:
                    break
        except Exception:
            printExc()
        meta = meta or {}
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        info.update(dict((key, siteInfo[key]) for key in ("type", "status", "episodes") if key in siteInfo))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("AnimeAV1.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "av1_latest":
            self.listLatest(self.currItem)
        elif category == "av1_new":
            self.listNew(self.currItem)
        elif category == "av1_filter":
            self.listFilter(self.currItem)
        elif category == "av1_list":
            self.listItems(self.currItem)
        elif category == "av1_series":
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
        CHostBase.__init__(self, AnimeAV1(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("animeav1")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
