# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
#   TioAnime (anime in Japanese with Spanish subtitles): latest episodes, latest anime, airing now, the
#   directory (all / TV / movies / OVA / specials / genres, First / Jump / Next page) and search
#   anime -> episodes (season from "2nd Season" / "Season 2" / "II"), a film with one episode is a VIDEO row;
#   links: the page's "var videos" list (voe, yourupload, ...) handed to urlparser
import re

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

config.plugins.iptvplayer.tioanime_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.tioanime_alt_domain)]


def gettytul():
    return "https://tioanime.com/"


LOCAL_PAGE_SIZE = 100
# "Kikansha no Mahou wa Tokubetsu desu 2nd Season" / "... Season 2" -> season 2
SEASON_RE = re.compile(r"(?i)\s*\b(?:(\d+)(?:st|nd|rd|th)\s+season|season\s*(\d+))\b")
# "Tensei shitara Ken deshita II" -> season 2
ROMAN_RE = re.compile(r"\s+(II|III|IV|V|VI)$")
ROMAN = {"II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
ARTICLE_RE = re.compile(r'(?s)<article class="(anime|episode)[^"]*">(.*?)</article>')
VIDEO_CATEGORIES = ("tio_video",)
FOLDER_CATEGORIES = ("tio_series",)
# the site's own type names of a film
FILM_TYPES = ("película", "pelicula")


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
    # "Magic Knight Rayearth (2026)" / "Dorohedoro (TV)" -> the title the movie databases know
    return re.sub(r"\s*\((?:TV|\d{4})\)\s*$", "", name or "").strip()


def _num(value):
    # 3 / 3.0 / "12.5" -> "3" / "3" / "12.5"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return str(int(number)) if number == int(number) else str(number)


class TioAnime(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "series_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "tioanime", "cookie": "tioanime.cookie"})
        self.selectDomain()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/tioanime135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("tioanime")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def selectDomain(self):
        domain = config.plugins.iptvplayer.tioanime_alt_domain.value.strip()
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
        if IsMediaNamingNormalized():
            if re.match(r"^\d+$", episode):
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
        directory = self.getFullUrl("directorio")
        menu = [
            {"category": "tio_latest", "title": _("Latest episodes"), "url": self.MAIN_URL},
            {"category": "tio_new", "title": _("Latest added"), "url": self.MAIN_URL},
            {"category": "tio_list", "title": _("Airing now"), "url": directory + "?status=1&sort=recent"},
            {"category": "tio_list", "title": _("Anime list"), "url": directory},
            {"category": "tio_list", "title": _("TV series"), "url": directory + "?type%5B%5D=0"},
            {"category": "tio_list", "title": _("Anime Movies"), "url": directory + "?type%5B%5D=1", "films": True},
            {"category": "tio_list", "title": "OVA", "url": directory + "?type%5B%5D=2"},
            {"category": "tio_list", "title": _("Specials"), "url": directory + "?type%5B%5D=3"},
            {"category": "tio_genres", "title": _("Genres"), "url": directory},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listGenres(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'name="genero[]"', "</select>", False)[1]
        for value, label in re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)</option>', block):
            self.addDir({"name": "category", "category": "tio_list", "good_for_fav": True, "title": self.cleanHtmlStr(label),
                         "url": self.getFullUrl("directorio?genero%%5B%%5D=%s&sort=recent" % value)})

    def _cards(self, data):
        # [(kind, url, title, icon)] of the poster / episode cards
        rows, seen = [], set()
        for kind, item in ARTICLE_RE.findall(data):
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3 class="title">(.*?)</h3>')[0])
            if not url or not title or url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(item, r'<img src="([^"]+)"')[0]
            rows.append((kind, self.getFullUrl(url), title, self.getFullIconUrl(icon) if icon else ""))
        return rows

    def _addAnime(self, url, title, icon, film=False):
        name, season = _splitSeason(title)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "meta_title": _metaTitle(name)}
        if film:
            params.update({"category": "tio_video", "title": title, "meta_type": "movie"})
            self.addVideo(params)
        else:
            params.update({"category": "tio_series", "title": title, "s_title": name, "s_season": season or 1, "meta_type": "tv"})
            self.addDir(params)

    def listLatest(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="episodes', "</section>", False)[1]
        for _kind, url, label, icon in self._cards(block):
            match = re.search(r"/ver/(.+)-(\d+(?:\.\d+)?)$", url)
            if not match:
                continue
            episode = match.group(2)
            show = re.sub(r"\s+%s$" % re.escape(episode), "", label)
            name, season = _splitSeason(show)
            self.addVideo({"name": "category", "category": "tio_video", "good_for_fav": True, "url": url, "icon": icon,
                           "title": self._episodeTitle(name, season, episode) if IsMediaNamingNormalized() else label,
                           "s_title": name, "s_season": season or 1, "s_episode": episode, "meta_type": "tv",
                           "meta_title": _metaTitle(name), "series_url": self.getFullUrl("anime/%s" % match.group(1))})

    def listNew(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = data[data.rfind('<ul class="list-unstyled row">'):]
        for _kind, url, title, icon in self._cards(block):
            if "/anime/" in url:
                self._addAnime(url, title, icon)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        pageTpl = "%s%sp={page}" % (baseUrl.replace("{", "{{").replace("}", "}}"), "&" if "?" in baseUrl else "?")
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("TioAnime.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        main = self.cm.ph.getDataBeetwenMarkers(data, "<main", "</main>", False)[1] or data
        count = 0
        for _kind, itemUrl, title, icon in self._cards(main):
            if "/anime/" in itemUrl:
                self._addAnime(itemUrl, title, icon, cItem.get("films", False))
                count += 1
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', "</ul>", False)[1]
        lastPage = max([int(n) for n in re.findall(r"[?&]p=(\d+)", pager)] + [page])
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, bool(count) and lastPage > page, lastPage, pageTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        cItem = dict(cItem)
        base = self.getFullUrl("directorio?q=%s" % urllib_quote_plus(cItem.get("s_pattern") or searchPattern.strip()))
        if cItem.get("category") != "search_next_page":
            cItem.update({"page": 1, "base_url": base})
        cItem.update({"category": "search_next_page", "url": base, "base_url": cItem.get("base_url") or base,
                      "s_pattern": cItem.get("s_pattern") or searchPattern.strip()})
        self.listItems(cItem)

    def _animeData(self, data):
        # (slug, [episode numbers ascending], type, year) of an anime page
        info = []
        try:
            # ensure_str_deep: UTF-8 str on Python 2 (json gives unicode there)
            info = ensure_str_deep(json_loads(self.cm.ph.getSearchGroups(data, r"var anime_info = (\[.*?\]);")[0] or "[]"))
        except Exception:
            printExc()
        episodes = []
        try:
            episodes = json_loads(self.cm.ph.getSearchGroups(data, r"var episodes = (\[.*?\]);")[0] or "[]")
        except Exception:
            printExc()
        numbers = sorted(set(_num(x) for x in episodes if _num(x)), key=float)
        head = self.cm.ph.getDataBeetwenMarkers(data, '<article class="anime-single">', "</article>", False)[1]
        kind = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r'<span class="anime-type-peli">([^<]+)</span>')[0])
        year = self.cm.ph.getSearchGroups(head, r'<span class="year">(\d{4})</span>')[0]
        return (info[1] if len(info) > 1 else ""), numbers, kind, year

    def listEpisodes(self, cItem):
        printDBG("TioAnime.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        slug, numbers, kind, year = self._animeData(data)
        if not slug:
            slug = self.cm.ph.getSearchGroups(cItem["url"], r"/anime/([^/?#]+)")[0]
        if not numbers:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        if kind.lower() in FILM_TYPES and len(numbers) == 1:
            # a film: one VIDEO row on the anime page (the same key as in the movie list)
            params = stripPagerKeys(dict(cItem))
            params.update({"category": "tio_video", "title": self._filmTitle(cItem.get("title", show), year), "meta_type": "movie",
                           "meta_year": year})
            for key in ("s_title", "s_season"):
                params.pop(key, None)
            self.addVideo(params)
            return
        season = cItem.get("s_season", 1)
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for number in numbers[start:start + LOCAL_PAGE_SIZE]:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "tio_video", "good_for_fav": True,
                           "url": self.getFullUrl("ver/%s-%s" % (slug, number)), "title": self._episodeTitle(show, season, number),
                           "series_url": cItem["url"], "s_title": show, "s_season": season, "s_episode": number, "meta_type": "tv"})
            self.addVideo(params)
        if len(numbers) > LOCAL_PAGE_SIZE:
            lastPage = (len(numbers) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            # the page lives in cItem["page"] - the template keeps the anime url unchanged (Jump row)
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def _watchUrl(self, url):
        # the film row is the anime page; its video is episode 1
        match = re.search(r"/anime/([^/?#]+)", url)
        return self.getFullUrl("ver/%s-1" % match.group(1)) if match else url

    def getLinksForVideo(self, cItem):
        url = self._watchUrl(cItem.get("url", ""))
        printDBG("TioAnime.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        videos = []
        if sts:
            try:
                videos = ensure_str_deep(json_loads(self.cm.ph.getSearchGroups(data, r"var videos = (\[.*?\]);")[0] or "[]"))
            except Exception:
                printExc()
        urltab, seen = [], set()
        for video in videos:
            if not isinstance(video, list) or len(video) < 2:
                continue
            label, playerUrl = video[0], (video[1] or "").replace("\\/", "/")
            if not self.cm.isValidUrl(playerUrl) or playerUrl in seen:
                continue
            seen.add(playerUrl)
            if self.up.checkHostSupport(playerUrl) != 1:
                printDBG("TioAnime.getLinksForVideo unsupported hoster [%s]" % playerUrl)
                continue
            urltab.append({"name": label or self.up.getHostName(playerUrl), "url": strwithmeta(playerUrl, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        mediaType, metaTitle, year = self._metaArgs(cItem)
        metaQuery = sidecarMetaQuery(mediaType, metaTitle, year, skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), "", metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("TioAnime.getVideoLinks [%s]" % videoUrl)
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

    def _siteInfo(self, data):
        # (story, poster, {INFO fields}, original title) of an anime page
        head = self.cm.ph.getDataBeetwenMarkers(data, '<article class="anime-single">', "</article>", False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r'(?s)<p class="sinopsis">(.*?)</p>')[0])
        poster = self.cm.ph.getSearchGroups(head, r'<div class="thumb">\s*<figure><img src="([^"]+)"')[0]
        original = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r'(?s)<p class="original-title">(.*?)</p>')[0])
        info = {}
        kind = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r'<span class="anime-type-peli">([^<]+)</span>')[0])
        if kind:
            info["type"] = kind
        year = self.cm.ph.getSearchGroups(head, r'<span class="year">(\d{4})</span>')[0]
        if year:
            info["year"] = year
        broadcast = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r'(?s)<span class="season">\s*<span class="season">(.*?)</span>\s*</span>')[0])
        if broadcast:
            info["broadcast"] = broadcast
        status = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r'(?s)class="btn [^"]*status"[^>]*>(.*?)</a>')[0])
        if status:
            info["status"] = status
        genres = ", ".join(self.cleanHtmlStr(x) for x in re.findall(r'<a href="/directorio\?genero=[^"]+"[^>]*>([^<]+)</a>', head))
        if genres:
            info["genres"] = genres
        if original:
            info["original_title"] = original
        episodes = self._animeData(data)[1]
        if episodes and kind.lower() not in FILM_TYPES:
            info["episodes"] = str(len(episodes))
        return story, poster, info, original

    def getArticleContent(self, cItem):
        url = cItem.get("series_url") or cItem.get("url", "")
        printDBG("TioAnime.getArticleContent [%s]" % url)
        story, poster, info, original = "", "", {}, ""
        sts, data = self.getPage(url) if "/anime/" in url else (False, "")
        if sts:
            story, poster, info, original = self._siteInfo(data)
        mediaType, metaTitle, year = self._metaArgs(cItem, info.get("year", ""))
        meta = {}
        try:
            if metaTitle:
                meta = getMeta(mediaType, metaTitle, year)
            if not meta and original:
                meta = getMeta(mediaType, original, year)
        except Exception:
            printExc()
        meta = meta or {}
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        info.update(dict((key, siteInfo[key]) for key in ("type", "status", "broadcast") if key in siteInfo))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = meta.get("poster") or (self.getFullIconUrl(poster) if poster else cItem.get("icon", ""))
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
        printDBG("TioAnime.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "tio_latest":
            self.listLatest(self.currItem)
        elif category == "tio_new":
            self.listNew(self.currItem)
        elif category == "tio_genres":
            self.listGenres(self.currItem)
        elif category == "tio_list":
            self.listItems(self.currItem)
        elif category == "tio_series":
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
        CHostBase.__init__(self, TioAnime(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("tioanime")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
