# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
#   Latanime (anime with Latino / Castellano / Catalan dubs and Spanish subtitles): latest episodes, the
#   directory (all / airing / by language / movies / categories / genres / year / A-Z, First / Jump / Next
#   page) and search; anime -> episodes (season from "S3" / "Temporada 3"), films are VIDEO rows
#   links: the base64 "data-player" servers of the episode page (voe, mixdrop, savefiles, ...) -> urlparser,
#   the language of the title shown in the link name
import base64
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.latanime_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.latanime_alt_domain)]


def gettytul():
    return "https://latanime.org/"


LOCAL_PAGE_SIZE = 100
CARD_START = '<div class="col-md-4 col-lg-3 col-xl-2 col-6 my-3">'
LATEST_START = '<div class="col-6 col-md-6 col-lg-3 mb-3">'
# "... S3 ..." / "... Temporada 3" / "... Season 3" -> season 3
SEASON_RE = re.compile(r"(?i)\s*\b(?:S(\d{1,2})|temporada\s*(\d+)|season\s*(\d+)|(\d+)(?:st|nd|rd|th)\s+season)\b")
# the dub of a title, as the site names it
LANG_RE = re.compile(r"(?i)\b(latino|castellano|catal(?:a|á)n)\b")
LANG_NAMES = {"latino": "Latino", "castellano": "Castellano", "catalan": "Catalán"}
# words of the site's titles that are no part of the anime's name
NOISE_RE = re.compile(r"(?i)\s*\b(?:audio\s+)?(?:latino|castellano|catal(?:a|á)n)\b|\s*\bAMZ\b|\s*\(\d{4}\)")
# "Assassination Classroom. La Película: ..." -> the movie databases know it without the word
FILM_WORD_RE = re.compile(r"(?i)[.,]?\s*\b(?:la\s+)?pel(?:i|í)cula\b")
FILMS_RE = re.compile(r"(?i)\bpel(?:i|í)culas\b")
EPISODE_RE = re.compile(r"/ver/(.+)-episodio-(\d+(?:[.-]\d+)?)$")
VIDEO_CATEGORIES = ("lat_video",)
FOLDER_CATEGORIES = ("lat_series",)


def _lang(text):
    # "... Latino AMZ" -> "Latino"; "" for the subtitled versions
    match = LANG_RE.search(text or "")
    if not match:
        return ""
    word = match.group(1).lower().replace("á", "a")
    return LANG_NAMES.get(word, match.group(1).capitalize())


def _splitSeason(title):
    # -> (name without season tag / dub / site words, season number or 0)
    title = (title or "").strip()
    season = 0
    match = SEASON_RE.search(title)
    if match:
        season = int(match.group(1) or match.group(2) or match.group(3) or match.group(4))
        title = title[:match.start()] + " " + title[match.end():]
    name = re.sub(r"\s+", " ", NOISE_RE.sub("", title)).strip(" -:,")
    return (name or title.strip()), season


def _metaTitle(name):
    return re.sub(r"\s+", " ", FILM_WORD_RE.sub("", name)).strip(" -:,.") or name


class LatAnime(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "s_lang",
                  "series_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "latanime", "cookie": "latanime.cookie"})
        self.selectDomain()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/latanime135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("latanime")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def selectDomain(self):
        domain = config.plugins.iptvplayer.latanime_alt_domain.value.strip()
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
    def _episodeTitle(show, season, episode, lang, label):
        # the dub stays in the name: Latino and Castellano versions of the same episode are listed side by side
        if IsMediaNamingNormalized() and re.match(r"^\d+$", episode):
            title = "%s - %s" % (show, formatSxxExx(season or 1, episode))
            return "%s (%s)" % (title, lang) if lang else title
        return label

    @staticmethod
    def _filmTitle(name, year, lang, label):
        if not IsMediaNamingNormalized():
            return label
        title = "%s (%s)" % (name, year) if year else name
        return "%s (%s)" % (title, lang) if lang else title

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "lat_latest", "title": _("Latest episodes"), "url": self.MAIN_URL},
            {"category": "lat_list", "title": _("Anime list"), "url": self.getFullUrl("animes")},
            {"category": "lat_list", "title": _("Airing now"), "url": self.getFullUrl("emision")},
            {"category": "lat_filter", "title": _("Language"), "url": self.getFullUrl("animes"), "filter": "lang"},
            {"category": "lat_filter", "title": _("Anime Movies"), "url": self.getFullUrl("animes"), "filter": "film"},
            {"category": "lat_filter", "title": _("Categories"), "url": self.getFullUrl("animes"), "filter": "categoria"},
            {"category": "lat_filter", "title": _("Genres"), "url": self.getFullUrl("animes"), "filter": "genero"},
            {"category": "lat_filter", "title": _("Year"), "url": self.getFullUrl("animes"), "filter": "fecha"},
            {"category": "lat_filter", "title": _("A-Z"), "url": self.getFullUrl("animes"), "filter": "letra"},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listFilter(self, cItem):
        # the options of the directory's filter form: categoria (split into languages / films / the rest), genero,
        # fecha, letra
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        which = cItem.get("filter", "")
        field = "categoria" if which in ("lang", "film") else which
        block = self.cm.ph.getSearchGroups(data, r'(?s)<select[^>]+name="%s"[^>]*>(.*?)</select>' % field)[0]
        for value, label in re.findall(r'<option\s+value="([^"]*)"\s*>([^<]+)</option>', block):
            label = self.cleanHtmlStr(label)
            if value in ("", "false") or value == "preestreno":
                continue
            if field == "categoria":
                isFilm = "pel" in value.lower()
                isLang = value.lower() in ("latino", "castellano", "catalan")
                if (which == "film") != isFilm or (which == "lang") != isLang:
                    continue
            params = {"fecha": "false", "genero": "false", "letra": "false", "categoria": "false"}
            params[field] = value
            query = "&".join("%s=%s" % (key, urllib_quote_plus(params[key])) for key in ("fecha", "genero", "letra", "categoria"))
            self.addDir({"name": "category", "category": "lat_list", "good_for_fav": True, "title": label,
                         "url": self.getFullUrl("animes?%s" % query), "films": which == "film"})

    def _cards(self, data):
        # [(url, title, icon, category label, year)] of the poster cards
        rows, seen = [], set()
        for item in data.split(CARD_START)[1:]:
            item = item.split("</a></div>")[0]
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3[^>]*class="my-1">(.*?)</h3>')[0])
            if not url or not title or url in seen or "/anime/" not in url:
                continue
            seen.add(url)
            # the directory loads its posters lazily (data-src), the airing list directly (src)
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'<img src="([^"]+)"')[0]
            kind = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span class="opacity-75">([^<]+)</span>')[0])
            year = self.cm.ph.getSearchGroups(item, r"</svg>\s*(\d{4})\s*</span>")[0]
            rows.append((url, title, self.getFullIconUrl(icon) if icon else "", kind, year))
        return rows

    def _addCard(self, url, title, icon, kind, year, film=False):
        name, season = _splitSeason(title)
        lang = _lang(title) or _lang(kind)
        desc = " | ".join(x for x in (kind, year) if x)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc, "s_lang": lang,
                  "meta_title": _metaTitle(name), "meta_year": year}
        # "... Películas" is a collection of films: a folder like a series
        if (film or "pel" in kind.lower()) and not FILMS_RE.search(title):
            params.update({"category": "lat_video", "title": self._filmTitle(name, year, lang, title), "meta_type": "movie"})
            self.addVideo(params)
        else:
            params.update({"category": "lat_series", "title": title, "s_title": name, "s_season": season or 1, "meta_type": "tv"})
            self.addDir(params)

    def listLatest(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for item in data.split(LATEST_START)[1:]:
            item = item.split("</a>")[0]
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            match = EPISODE_RE.search(url)
            if not match or url in seen:
                continue
            seen.add(url)
            episode = match.group(2)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
            show = re.sub(r"(?i)\s*cap(?:i|í)tulo\s+[\d.-]+\s*$", "", label)
            name, season = _splitSeason(show)
            lang = _lang(show)
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            self.addVideo({"name": "category", "category": "lat_video", "good_for_fav": True, "url": url,
                           "icon": self.getFullIconUrl(icon) if icon else "", "desc": lang,
                           "title": self._episodeTitle(name, season, episode, lang, "%s - %s %s" % (show, _("Episode"), episode)),
                           "s_title": name, "s_season": season or 1, "s_episode": episode, "s_lang": lang, "meta_type": "tv",
                           "meta_title": _metaTitle(name), "series_url": self.getFullUrl("anime/%s" % match.group(1))})

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        pageTpl = "%s%sp={page}" % (baseUrl.replace("{", "{{").replace("}", "}}"), "&" if "?" in baseUrl else "?")
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("LatAnime.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        cards = self._cards(data)
        for card in cards:
            self._addCard(*card, film=cItem.get("films", False))
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', "</ul>", False)[1].replace("&amp;", "&")
        lastPage = max([int(n) for n in re.findall(r"[?&]p=(\d+)", pager)] + [page])
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, bool(cards) and lastPage > page, lastPage, pageTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        cItem = dict(cItem)
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        base = self.getFullUrl("buscar?q=%s" % urllib_quote_plus(pattern))
        if cItem.get("category") != "search_next_page":
            cItem.update({"page": 1, "base_url": base})
        cItem.update({"category": "search_next_page", "url": base, "base_url": cItem.get("base_url") or base, "s_pattern": pattern})
        self.listItems(cItem)

    def _episodes(self, data):
        # [(episode, url)] of an anime page, in the site's order
        block = data[data.find(">Capítulos<"):] if ">Capítulos<" in data else data
        rows, seen = [], set()
        for url in re.findall(r'<a href="([^"]+/ver/[^"]+)"', block):
            match = EPISODE_RE.search(url)
            if match and url not in seen:
                seen.add(url)
                rows.append((match.group(2), url))
        return rows

    def listEpisodes(self, cItem):
        printDBG("LatAnime.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        episodes = self._episodes(data)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        lang = cItem.get("s_lang", "")
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for episode, url in episodes[start:start + LOCAL_PAGE_SIZE]:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "lat_video", "good_for_fav": True, "url": url,
                           "title": self._episodeTitle(show, season, episode, lang, "%s - %s %s" % (cItem.get("title", show), _("Episode"), episode)),
                           "series_url": cItem["url"], "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            # the page lives in cItem["page"] - the template keeps the anime url unchanged (Jump row)
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def _watchUrl(self, url):
        # a film row is the anime page: its video is the first episode page listed there
        if "/anime/" not in url:
            return url
        sts, data = self.getPage(url)
        episodes = self._episodes(data) if sts else []
        return episodes[0][1] if episodes else ""

    def getLinksForVideo(self, cItem):
        url = self._watchUrl(cItem.get("url", ""))
        printDBG("LatAnime.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url) if url else (False, "")
        lang = cItem.get("s_lang") or _lang(cItem.get("title", "")) or "SUB"
        urltab, seen = [], set()
        for encoded, label in re.findall(r'data-player="([^"]+)"[^>]*>([^<]*)<', data if sts else ""):
            try:
                playerUrl = ensure_str(base64.b64decode(encoded)).strip()
            except Exception:
                printExc()
                continue
            if not self.cm.isValidUrl(playerUrl) or playerUrl in seen:
                continue
            seen.add(playerUrl)
            if self.up.checkHostSupport(playerUrl) != 1:
                printDBG("LatAnime.getLinksForVideo unsupported hoster [%s]" % playerUrl)
                continue
            # the site's button names do not always fit the hoster ("ok" = voe.sx): its name from the url then
            name = self.cleanHtmlStr(label)
            if not name or name.lower() not in self.cm.ph.getSearchGroups(playerUrl.lower(), r"^https?://([^/?#:]+)")[0]:
                name = self.up.getHostName(playerUrl, True)
            urltab.append({"name": "%s [%s]" % (name, lang), "url": strwithmeta(playerUrl, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        mediaType, metaTitle, year = self._metaArgs(cItem)
        metaQuery = sidecarMetaQuery(mediaType, metaTitle, year, skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), "", metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("LatAnime.getVideoLinks [%s]" % videoUrl)
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
        # (story, poster, {INFO fields}, [other titles]) of an anime page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="my-2 opacity-75">(.*?)</p>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'(?s)<div class="serieimgficha">\s*<img[^>]+src="([^"]+)"')[0]
        info = {}
        others = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h3 class="fs-6 text-light opacity-75">(.*?)</h3>')[0])
        if others:
            info["alternate_title"] = others
        premiere = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"Estreno:\s*([^<]+)<")[0])
        if premiere:
            info["released"] = premiere
            year = self.cm.ph.getSearchGroups(premiere, r"((?:19|20)\d{2})")[0]
            if year:
                info["year"] = year
        episodes = self.cm.ph.getSearchGroups(data, r"<p>Episodios:\s*(\d+)</p>")[0]
        if episodes:
            info["episodes"] = episodes
        genres = ", ".join(self.cleanHtmlStr(x) for x in re.findall(r'/genero/[^"]+"><div class="btn">([^<]+)</div>', data))
        if genres:
            info["genres"] = genres
        lang = _lang(self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<h2>(.*?)</h2>")[0]))
        if lang:
            info["language"] = lang
        # "Kusuriya no Hitorigoto / The Apothecary Diaries S3 Audio Latino" -> the single names
        titles = []
        for title in re.split(r"\s*[/,]\s*", others):
            title = _metaTitle(_splitSeason(title)[0])
            if title and title not in titles:
                titles.append(title)
        return story, poster, info, titles

    def getArticleContent(self, cItem):
        url = cItem.get("series_url") or cItem.get("url", "")
        printDBG("LatAnime.getArticleContent [%s]" % url)
        story, poster, info, titles = "", "", {}, []
        sts, data = self.getPage(url) if "/anime/" in url else (False, "")
        if sts:
            story, poster, info, titles = self._siteInfo(data)
        mediaType, metaTitle, year = self._metaArgs(cItem, info.get("year", ""))
        meta = {}
        try:
            for title in [t for t in [metaTitle] + [x for x in titles if x != metaTitle][:2] if t]:
                meta = getMeta(mediaType, title, year)
                if meta:
                    break
        except Exception:
            printExc()
        meta = meta or {}
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        info.update(dict((key, siteInfo[key]) for key in ("language", "episodes") if key in siteInfo))
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
        printDBG("LatAnime.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "lat_latest":
            self.listLatest(self.currItem)
        elif category == "lat_filter":
            self.listFilter(self.currItem)
        elif category == "lat_list":
            self.listItems(self.currItem)
        elif category == "lat_series":
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
        CHostBase.__init__(self, LatAnime(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("latanime")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
