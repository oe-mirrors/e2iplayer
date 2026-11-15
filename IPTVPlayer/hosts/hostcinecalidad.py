# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host: Cinecalidad (Spanish / Latino films and series; own domain in the settings).
#   Films: the "VER ONLINE" hoster buttons (base64 data-src) -> urlparser. Episodes have no online player on the
#   site (empty data-src), only the download links: magnets (TorrServer) and hosters urlparser knows.
import base64
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.cinecalidad_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.cinecalidad_alt_domain)]


def gettytul():
    return "https://www.cinecalidad.vg/"


# site paths: urls of an older address (favourites, history) are moved to the current one
SITE_PATH_RE = re.compile(r"^https?://[^/]+/((?:pelicula|serie|episodio|estrenos|peliculas-populares|series-populares|4k|categoria|release|page|wp-admin)/.*|\?.*)$")
CARD_RE = re.compile(r'(?s)<article class="relative group">(.*?)</article>')
VIDEO_CATEGORIES = ("video",)
FOLDER_CATEGORIES = ("list_seasons", "list_episodes")


def _b64(text):
    try:
        return ensure_str(base64.b64decode(text + "=" * (-len(text) % 4)))
    except Exception:
        return ""


def languageLabel(text):
    # "Audio Latino" -> Latino; "Audio latino y original con subtítulos" -> Latino + VOSE
    low = (text or "").lower()
    lang = "Latino" if "latino" in low else ("Castellano" if ("castellano" in low or "espa" in low) else "")
    if "original" in low or "subt" in low:
        lang = "%s + VOSE" % lang if lang else "Subtitulado"
    return lang


class Cinecalidad(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "c_serie",
                  "s_original", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cinecalidad", "cookie": "cinecalidad.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.cinecalidad_alt_domain.value.strip()
        if not self.setMainUrl(domain if domain.endswith("/") else domain + "/"):
            self.MAIN_URL = gettytul()
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("cinecalidad")
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

    def _isSiteUrl(self, url):
        # the lists carry ad tiles linking to other domains
        return bool(re.match(r"^https?://[^/]+/(?:pelicula|serie)/", url or "")) and \
            re.sub(r"^https?://(?:www\.)?", "", url).split("/")[0] == re.sub(r"^https?://(?:www\.)?", "", self.getMainUrl()).split("/")[0]

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
        # <path>page/<n>/[?query]
        path, sep, query = url.partition("?")
        path = re.sub(r"page/\d+/?$", "", path)
        if not path.endswith("/"):
            path += "/"
        if page > 1:
            path += "page/%s/" % page
        return path + sep + query

    def _episodeTitle(self, show, season, episode):
        if IsMediaNamingNormalized():
            return "%s - %s" % (show, formatSxxExx(season, episode))
        return "%s %dx%d" % (show, season, episode)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [{"category": "list_items", "title": _("Latest added"), "url": self.getMainUrl()},
                {"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("estrenos/")},
                {"category": "list_items", "title": _("Popular movies"), "url": self.getFullUrl("peliculas-populares/")},
                {"category": "list_items", "title": "4K", "url": self.getFullUrl("4k/")},
                {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("serie/")},
                {"category": "list_items", "title": _("Popular series"), "url": self.getFullUrl("series-populares/")},
                {"category": "list_filters", "title": _("Genres"), "filter": "categoria"},
                {"category": "list_filters", "title": _("Year"), "filter": "release"}]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listFilters(self, cItem):
        # genres / years of the site menu
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        kind = cItem.get("filter", "categoria")
        items, seen = [], set()
        for url, title in re.findall(r'<a (?:aria-label="[^"]*" )?href="(https?://[^"]+/%s/[^"/]+/)">([^<]+)</a>' % kind, data):
            if url not in seen:
                seen.add(url)
                items.append((url, self.cleanHtmlStr(title)))
        items.sort(key=lambda x: x[1], reverse=(kind == "release"))
        for url, title in items:
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": url})

    def _addCard(self, block, normalize):
        url = self.cm.ph.getSearchGroups(block, r'<a class="absolute top-0 left-0[^"]*" href="([^"]+)"')[0]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<span class="sr-only">(.*?)</span>')[0])
        if not self._isSiteUrl(url) or not title:
            return False
        badges = [self.cleanHtmlStr(x) for x in re.findall(r'(?s)<div style="[^"]*">(.*?)</div>', block)]
        year = ([b for b in badges if re.match(r"^(?:19|20)\d{2}$", b)] or [""])[0]
        rating = ([b for b in badges if re.match(r"^\d+(?:\.\d+)?$", b) and b != year] or [""])[0]
        icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+data-src="([^"]+)"')[0]
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<p class="text-sm[^"]*">(.*?)</p>')[0])
        genres = " / ".join(self.cleanHtmlStr(x) for x in re.findall(r'href="[^"]+/categoria/[^"]+">([^<]+)</a>', block))
        line = " | ".join(x for x in (year, genres, "TMDB %s" % rating if rating else "") if x)
        desc = "%s[/br]%s" % (line, plot) if (line and plot) else (line or plot)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc}
        if "/serie/" in url:
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
        printDBG("Cinecalidad.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        count, seen = 0, set()
        for block in CARD_RE.findall(data):
            itemUrl = self.cm.ph.getSearchGroups(block, r'href="([^"]+)"')[0]
            if itemUrl in seen:
                continue
            seen.add(itemUrl)
            if self._addCard(block, normalize):
                count += 1
        pages = [int(p) for p in re.findall(r'class="page-numbers"[^>]*>(\d+)<', data)]
        lastPage = max(pages) if pages else 0
        # a page of ad tiles only still has a next page
        hasNext = 'class="next page-numbers"' in data
        nextItem = dict(cItem, base_url=baseUrl)
        addPagingItems(self, nextItem, page, hasNext, max(lastPage, page + 1) if (hasNext and lastPage) else lastPage, self._pageUrl(baseUrl, 987654).replace("987654", "{page}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        item = dict(cItem, category="search_next_page", s_pattern=pattern, base_url=self.getFullUrl("?s=%s" % urllib_quote_plus(pattern)))
        self.listItems(item)

    def _seasons(self, data):
        # (serie id, [(season, label)]) of a series page
        serie, seasons = "", []
        for serieId, season, label in re.findall(r'<span data-serie="(\d+)" data-season="(\d+)"[^>]*>([^<]*)</span>', data):
            serie = serieId
            if int(season) not in [s for s, _l in seasons]:
                seasons.append((int(season), self.cleanHtmlStr(label)))
        return serie, seasons

    def _episodes(self, cItem, serie, season):
        # [(episode, url, icon)] of a season (the site's admin-ajax call of its season tabs)
        params = dict(self.defaultParams, header=dict(self.HEADER, Referer=cItem["url"].split("#")[0], **{"X-Requested-With": "XMLHttpRequest"}))
        sts, data = self.getPage(self.getFullUrl("wp-admin/admin-ajax.php"), params, {"action": "action_change_episode", "season": str(season), "serie": str(serie)})
        if not sts:
            return []
        try:
            items = json_loads(data).get("d") or []
        except Exception:
            printExc()
            return []
        episodes = []
        for item in items:
            try:
                number = int(item.get("episode", 0))
            except (TypeError, ValueError):
                continue
            url = ensure_str(item.get("url", ""))
            if self.cm.isValidUrl(url):
                icon = self.cm.ph.getSearchGroups(ensure_str(item.get("image", "")), r'src="([^"]+)"')[0]
                episodes.append((number, url, icon))
        episodes.sort()
        return episodes

    def listSeasons(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        serie, seasons = self._seasons(data)
        if not serie or not seasons:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        # the original title of the show: moviemeta of its episodes (the episode pages carry none, the Spanish
        # title is often not found)
        cItem = dict(cItem, s_original=self._siteInfo(data).get("_original", ""))
        if len(seasons) == 1:
            self._addEpisodes(cItem, show, seasons[0][0], self._episodes(cItem, serie, seasons[0][0]))
            return
        base = cItem["url"].split("#")[0]
        for season, label in seasons:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "list_episodes", "good_for_fav": True, "url": "%s#s%d" % (base, season),
                           "title": "%s - %s" % (show, formatSxxExx(season) if IsMediaNamingNormalized() else (label or "%s %d" % (_("Season"), season))),
                           "s_title": show, "s_season": season, "c_serie": serie})
            self.addDir(params)

    def listEpisodes(self, cItem):
        serie = cItem.get("c_serie", "")
        if not serie:
            sts, data = self.getPage(cItem["url"].split("#")[0])
            serie = self._seasons(data)[0] if sts else ""
        season = cItem.get("s_season", 1)
        episodes = self._episodes(cItem, serie, season) if serie else []
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        self._addEpisodes(cItem, cItem.get("s_title") or cItem.get("title", ""), season, episodes)

    def _addEpisodes(self, cItem, show, season, episodes):
        for episode, url, icon in episodes:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "video", "good_for_fav": True, "url": url, "icon": icon or cItem.get("icon", ""),
                           "title": self._episodeTitle(show, season, episode), "desc": "%dx%d" % (season, episode),
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv", "meta_title": show})
            params.pop("meta_year", None)
            params.pop("c_serie", None)
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def _players(self, data):
        # [(name, hoster url)] of the "VER ONLINE" and download boxes of a page
        players = []
        for aside in re.findall(r"(?s)<aside>(.*?)</aside>", data):
            head = self.cm.ph.getSearchGroups(aside, r'(?s)<p[^>]*>(.*?)</p>')[0]
            box = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r"(?s)<span[^>]*>(.*?)</span>")[0]).lower()
            lang = languageLabel(self.cleanHtmlStr(re.sub(r"(?s)^.*?</span>", "", head, 1)))
            if box == "ver online":
                for src, label in re.findall(r'(?s)data-src="([^"]*)"[^>]*data-option[^>]*>(.*?)</a>', aside):
                    url = _b64(src) if src else ""
                    players.append(("%s - %s" % (self.cleanHtmlStr(label), lang) if lang else self.cleanHtmlStr(label), url))
            elif box == "descargar":
                # films: base64 data-url (the site's /links/ pages, broken since 10.2026); episodes: plain hrefs
                for li in re.findall(r"(?s)<li[^>]*>(.*?)</li>", aside):
                    url = self.cm.ph.getSearchGroups(li, r'data-url="([^"]+)"')[0]
                    url = _b64(url) if url else self.cm.ph.getSearchGroups(li, r'<a\s[^>]*href="([^"#][^"]*)"')[0].replace("&amp;", "&")
                    label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(li, r"(?s)<a\s[^>]*>(.*?)</a>")[0])
                    quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(li, r'(?s)class="txtmf">(.*?)</span>')[0])
                    if url.startswith("magnet:"):
                        release = urllib_unquote_plus(self.cm.ph.getSearchGroups(url, r"[?&]dn=([^&]+)")[0])
                        label = "%s - %s" % (_("Torrent"), quality or release or lang)
                    elif "contrase" in quality.lower():
                        continue  # password protected archives
                    players.append((label, url))
        return players

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("Cinecalidad.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab, seen = [], set()
        for name, playerUrl in self._players(data):
            if not (self.cm.isValidUrl(playerUrl) or playerUrl.startswith("magnet:")) or playerUrl in seen:
                continue
            seen.add(playerUrl)
            if self.up.checkHostSupport(playerUrl) != 1:
                printDBG("Cinecalidad.getLinksForVideo unsupported hoster [%s]" % playerUrl[:120])
                continue
            urltab.append({"name": name[:1].upper() + name[1:] if name else self.up.getHostName(playerUrl), "url": strwithmeta(playerUrl, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        info = self._siteInfo(data)
        mediaType, metaTitle, year = self._metaArgs(cItem, info)
        metaQuery = sidecarMetaQuery(mediaType, metaTitle, year, imdbId="" if cItem.get("s_episode") else info.get("_imdb", ""), skip=(),
                                     altTitles=[info.get("_original", "") or cItem.get("s_original", "")])
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info.get("_story", ""), metaQuery))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("Cinecalidad.getVideoLinks [%s]" % videoUrl[:200])
        if not (self.cm.isValidUrl(videoUrl) or videoUrl.startswith("magnet:")):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # INFO fields of a film / series / episode page; "_" keys are no INFO fields
        info = {}
        widget = self.cm.ph.getDataBeetwenMarkers(data, '<div class="textwidget', "</aside>", False)[1]
        info["_story"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(widget, r"(?s)<p>(.*?)</p>")[0])
        info["_poster"] = self.cm.ph.getSearchGroups(data, r'(?s)<figure class="md:col-span-2">\s*<img[^>]+data-src="([^"]+)"')[0]
        info["_imdb"] = self.cm.ph.getSearchGroups(widget, r"imdb\.com/title/(tt\d+)")[0]
        info["_original"] = ""
        for label, value in re.findall(r'(?s)<li><span class="font-bold">([^<]+)</span>(.*?)</li>', widget):
            label = self.cleanHtmlStr(label).lower()
            value = self.cleanHtmlStr(value)
            if label.startswith("t") and "original" in label:
                info["_original"] = value
                info["original_title"] = value
            elif label in ("director", "creador"):
                info["director"] = value
            elif label in ("genres", "géneros", "generos"):
                info["genres"] = value.replace(" / ", ", ")
            elif label in ("cast", "reparto", "elenco"):
                info["actors"] = value
            elif label == "rating" and value:
                info["rating"] = value
        year = self.cm.ph.getSearchGroups(data, r'<h1 class="mb-2[^"]*">[^<]*\(((?:19|20)\d{2})\)</h1>')[0]
        if year:
            info["year"] = year
        return info

    @staticmethod
    def _metaArgs(cItem, info):
        # moviemeta query of INFO (type, title, year): no year for an episode (the show's lookup)
        year = "" if cItem.get("s_episode") else (cItem.get("meta_year") or info.get("year", ""))
        return cItem.get("meta_type") or "movie", cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", ""), year

    def getArticleContent(self, cItem):
        printDBG("Cinecalidad.getArticleContent [%s]" % cItem.get("url", ""))
        info = {}
        sts, data = self.getPage(cItem.get("url", "").split("#")[0])
        if sts:
            info = self._siteInfo(data)
        story, poster, imdb, original = info.pop("_story", ""), info.pop("_poster", ""), info.pop("_imdb", ""), info.pop("_original", "")
        mediaType, metaTitle, year = self._metaArgs(cItem, info)
        meta = {}
        try:
            if cItem.get("s_episode"):
                imdb, original = "", original or cItem.get("s_original", "")
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and metaTitle:
                meta = getMeta(mediaType, metaTitle, year)
            if not meta and original:
                meta = getMeta(mediaType, original, year)
        except Exception:
            printExc()
        meta = meta or {}
        info.update(meta.get("info", {}))
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in info:
                info.pop(siteKey, None)
        plot = meta.get("plot", "")
        # an episode row's desc is only "1x1": the show's plot before that
        text = story or (plot if cItem.get("s_episode") else "") or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        else:
            text = text or plot
        icon = poster or meta.get("poster", "") or cItem.get("icon", "")
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
        printDBG("Cinecalidad.handleService name[%s] category[%s]" % (name, category))
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
        CHostBase.__init__(self, Cinecalidad(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cinecalidad")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
