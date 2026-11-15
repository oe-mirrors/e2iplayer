# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host: Cuevana3 (Spanish films and series, Latino / Castellano / Subtitulado; own domain in the
#   settings). Players: the ?trembed= pages of the site -> hoster -> urlparser.
import re
from datetime import date

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.cuevana3_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.cuevana3_alt_domain)]


def gettytul():
    return "https://ver.cuevana3.one/"


# site paths: urls of an older address (favourites, history) are moved to the current one
SITE_PATH_RE = re.compile(r"^https?://[^/]+/((?:movies|series|episode|season|peliculas|estrenos|episodios|category|release|explorar|page)/.*|\?.*)$")
CARD_RE = re.compile(r'(?s)<article class="c3-card[^"]*">(.*?)</article>')
EPISODE_RE = re.compile(r'(?s)<article class="c3-ep">(.*?)</article>')
# <iframe [src=..] data-src="https://<site>/?trembed=2&#038;trid=71269&#038;trtype=1" title="Reproductor Voe Latino"
PLAYER_RE = re.compile(r'<iframe[^>]+data-src="([^"]*\?trembed=[^"]+)"[^>]*title="Reproductor\s+([^"]*)"')
LANGUAGES = ("Latino", "Castellano", "Subtitulado")
# player tabs left out: "Links" = the links.cuevana.ac list page (down since 10.2026), "Servidor" = fembed /
# streamplay (dead), the others are hosters urlparser does not know or that are gone
SKIP_PLAYERS = ("links", "servidor", "listeamed", "viewsb", "jawcloud", "cloudvideo", "upstream", "fembed", "streamplay")
VIDEO_CATEGORIES = ("video",)
FOLDER_CATEGORIES = ("list_seasons", "list_episodes")


class Cuevana3(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cuevana3", "cookie": "cuevana3.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.cuevana3_alt_domain.value.strip()
        if not self.setMainUrl(domain if domain.endswith("/") else domain + "/"):
            self.MAIN_URL = gettytul()
        self.cacheLinks = {}
        self.cacheHosters = {}
        self.watchedHelper = IPTVWatchedHelper("cuevana3")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        baseUrl = self._onMain(baseUrl)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _onMain(self, url):
        match = SITE_PATH_RE.match(url or "")
        return self.getMainUrl() + match.group(1) if match else (url or "")

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
        # WordPress lists: <path>page/<n>/[?query]; the "explorar" filter: ?...&pg=<n>
        if "/explorar/" in url:
            url = re.sub(r"&pg=\d+", "", url)
            return "%s&pg=%s" % (url, page) if page > 1 else url
        path, sep, query = url.partition("?")
        path = re.sub(r"page/\d+/?$", "", path)
        if not path.endswith("/"):
            path += "/"
        if page > 1:
            path += "page/%s/" % page
        return path + sep + query

    def _episodeTitle(self, show, season, episode, name=""):
        if IsMediaNamingNormalized():
            return "%s - %s" % (show, formatSxxExx(season, episode))
        title = "%s - %dx%02d" % (show, season, episode)
        return "%s - %s" % (title, name) if name else title

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("peliculas/")},
                {"category": "list_items", "title": _("Cinema movies"), "url": self.getFullUrl("estrenos/")},
                {"category": "list_items", "title": "Latino", "url": self.getFullUrl("peliculas/latino/")},
                {"category": "list_items", "title": "Castellano", "url": self.getFullUrl("peliculas/castellano/")},
                {"category": "list_items", "title": "Subtitulado", "url": self.getFullUrl("peliculas/subtitulado/")},
                {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("series/")},
                {"category": "list_items", "title": _("Latest episodes"), "url": self.getFullUrl("episodios/")},
                {"category": "list_genres", "title": _("Genres")},
                {"category": "list_years", "title": _("Year")}]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listGenres(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'<a href="([^"]+/explorar/\?tipo=peliculas&(?:#038;|amp;)?genero=[^"]+)">([^<]+)</a>', data):
            url = url.replace("&#038;", "&").replace("&amp;", "&")
            if url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)})

    def listYears(self, cItem):
        for year in range(date.today().year, 1949, -1):
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": str(year), "url": self.getFullUrl("release/%d/" % year)})

    def _addCard(self, block, normalize):
        url = self.cm.ph.getSearchGroups(block, r'class="c3-card__link" href="([^"]+)"')[0]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<h3 class="c3-card__title">(.*?)</h3>')[0])
        if not url or not title:
            return False
        icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
        meta = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<p class="c3-card__meta">(.*?)</p>')[0])
        year = self.cm.ph.getSearchGroups(meta, r"\b((?:19|20)\d{2})\b")[0]
        langs = [lang for lang in LANGUAGES if 'title="%s"' % lang in block]
        quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<span class="c3-q">([^<]+)</span>')[0])
        score = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<span class="c3-card__score[^"]*"[^>]*>([^<]+)</span>')[0])
        desc = " | ".join(x for x in (meta, " / ".join(langs), quality, "TMDB %s" % score if score else "") if x)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc}
        if "/series/" in url:
            params.update({"category": "list_seasons", "title": title, "s_title": title, "meta_type": "tv", "meta_title": title, "meta_year": year})
            self.addDir(params)
        else:
            params.update({"category": "video", "title": "%s (%s)" % (title, year) if (year and normalize) else title,
                           "meta_type": "movie", "meta_title": title, "meta_year": year})
            self.addVideo(params)
        return True

    def _addEpisodeCard(self, block, cItem, show=""):
        url = self.cm.ph.getSearchGroups(block, r'class="c3-ep__link" href="([^"]+)"')[0]
        numbers = re.search(r"-(\d+)x(\d+)/?$", url)
        if not url or not numbers:
            return False
        season, episode = int(numbers.group(1)), int(numbers.group(2))
        heading = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<h3 class="c3-ep__show">(.*?)</h3>')[0])
        # the "Episodios" list: show in <h3>, episode name in <p class="c3-ep__name">; a season of a series: name in <h3>
        name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<p class="c3-ep__name">(.*?)</p>')[0])
        if not show:
            show = heading
        elif not name:
            name = heading
        if re.match(r"^Episodio\s+\d+$", name):
            name = ""
        aired = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<p class="c3-ep__time">(.*?)</p>')[0])
        icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0] or cItem.get("icon", "")
        params = stripPagerKeys(dict(cItem))
        params.update({"name": "category", "category": "video", "good_for_fav": True, "url": url, "icon": icon,
                       "title": self._episodeTitle(show, season, episode, name),
                       "desc": " | ".join(x for x in ("%dx%02d" % (season, episode), name, aired) if x),
                       "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv", "meta_title": show})
        params.pop("meta_year", None)
        self.addVideo(params)
        return True

    def listItems(self, cItem):
        page = self._page(cItem)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = self._pageUrl(baseUrl, page)
        printDBG("Cuevana3.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        count = 0
        # the "Si te gustó" / slider rows of a page are no part of the list
        listData = self.cm.ph.getDataBeetwenMarkers(data, "<main", "</main>", False)[1] or data
        for block in CARD_RE.findall(listData):
            if self._addCard(block, normalize):
                count += 1
        for block in EPISODE_RE.findall(listData):
            if self._addEpisodeCard(block, {"name": "category"}):
                count += 1
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="c3-pagination"', "</nav>", False)[1]
        pages = [int(p) for p in re.findall(r'class="page-numbers[^"]*"[^>]*>(\d+)<', pager)]
        lastPage = max(pages) if pages else 0
        hasNext = bool(count) and 'class="next page-numbers"' in pager
        nextItem = dict(cItem, base_url=baseUrl)
        addPagingItems(self, nextItem, page, hasNext, lastPage, self._pageUrl(baseUrl, 987654).replace("987654", "{page}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        item = dict(cItem, category="search_next_page", s_pattern=pattern, base_url=self.getFullUrl("?s=%s" % urllib_quote_plus(pattern)))
        self.listItems(item)

    def _seasons(self, data):
        # [(season, label, pane html)] of a series page; season 0 = "Especiales"
        labels = dict(re.findall(r'data-c3-tab="s(\d+)"[^>]*>\s*([^<]+?)\s*<', data))
        seasons = []
        section = self.cm.ph.getDataBeetwenMarkers(data, 'id="episodios"', "</section>", False)[1]
        for pane in section.split('data-c3-pane="s')[1:]:
            number = self.cm.ph.getSearchGroups(pane, r"^(\d+)")[0]
            if number and EPISODE_RE.search(pane):
                seasons.append((int(number), self.cleanHtmlStr(labels.get(number, "")) or "%s %s" % (_("Season"), number), pane))
        # regular seasons first, the specials last
        seasons.sort(key=lambda s: (s[0] == 0, s[0]))
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
            self._addEpisodes(cItem, show, seasons[0][2])
            return
        base = cItem["url"].split("#")[0]
        for season, label, pane in seasons:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "list_episodes", "good_for_fav": True, "url": "%s#s%d" % (base, season),
                           "title": "%s - %s" % (show, formatSxxExx(season) if (season and IsMediaNamingNormalized()) else label),
                           "s_title": show, "s_season": season, "desc": "%s: %d" % (_("Episodes"), len(EPISODE_RE.findall(pane)))})
            self.addDir(params)

    def listEpisodes(self, cItem):
        sts, data = self.getPage(cItem["url"].split("#")[0])
        if not sts:
            return
        season = cItem.get("s_season", 1)
        for number, _label, pane in self._seasons(data):
            if number == season:
                self._addEpisodes(cItem, cItem.get("s_title") or cItem.get("title", ""), pane)
                return
        SetIPTVPlayerLastHostError(_("No stream available"))

    def _addEpisodes(self, cItem, show, pane):
        for block in EPISODE_RE.findall(pane):
            self._addEpisodeCard(block, cItem, show)

    ###################################################
    # links
    ###################################################
    def _players(self, data):
        # [(label, ?trembed= url)] of the player tabs ("Reproductor <server> <language>"); the trembed page holds
        # the hoster iframe - it is read when the link is opened (the site takes 5-15 s per trembed page)
        players, seen = [], set()
        for embed, title in PLAYER_RE.findall(data):
            parts = self.cleanHtmlStr(title).split()
            if not parts or parts[0].lower() in SKIP_PLAYERS:
                continue
            lang = parts[-1] if len(parts) > 1 else ""
            server = " ".join(parts[:-1]) if len(parts) > 1 else parts[0]
            embed = self.getFullUrl(embed.replace("&#038;", "&").replace("&amp;", "&"))
            if embed in seen:
                continue
            seen.add(embed)
            players.append(("%s - %s" % (server, lang) if lang else server, embed))
        # an episode can have two "Player - Latino" tabs: number the repeated names
        names = [label for label, _embed in players]
        for idx, (label, embed) in enumerate(players):
            if names.count(label) > 1:
                players[idx] = ("%s %d" % (label, names[:idx + 1].count(label)), embed)
        return players

    def _hosterUrl(self, embedUrl):
        # the hoster url of a ?trembed= page ("" when there is none / urlparser does not know the hoster)
        if str(embedUrl) in self.cacheHosters:
            return self.cacheHosters[str(embedUrl)]
        referer = getattr(embedUrl, "meta", {}).get("Referer", self.getMainUrl())
        sts, html = self.getPage(embedUrl, dict(self.defaultParams, header=dict(self.HEADER, Referer=referer)))
        if not sts:
            return ""
        url = self.cm.ph.getSearchGroups(html, r'(?s)<div class="Video">.*?<iframe[^>]+src="([^"]+)"')[0]
        # "https://voe.sx/e/<id>#idioma=lat#lang=LAT"
        url = url.replace("&amp;", "&").split("#")[0].strip()
        if url.startswith("//"):
            url = "https:" + url
        if not self.cm.isValidUrl(url) or self.up.checkHostSupport(url) != 1:
            printDBG("Cuevana3._hosterUrl no / unsupported hoster [%s]" % url)
            url = ""
        self.cacheHosters[str(embedUrl)] = url
        return url

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("Cuevana3.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab = [{"name": label, "url": strwithmeta(embed, {"Referer": url}), "need_resolve": 1} for label, embed in self._players(data)]
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        info = self._siteInfo(data)
        mediaType, metaTitle, year = self._metaArgs(cItem, info)
        metaQuery = sidecarMetaQuery(mediaType, metaTitle, year, imdbId="" if cItem.get("s_episode") else info.get("_imdb", ""), skip=(),
                                     altTitles=[info.get("_original", "")])
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info.get("_story", ""), metaQuery))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("Cuevana3.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if "trembed=" in videoUrl:
            hosterUrl = self._hosterUrl(videoUrl)
            if not hosterUrl:
                SetIPTVPlayerLastHostError(_("No stream available"))
                return []
            videoUrl = strwithmeta(hosterUrl, {"Referer": self.getMainUrl()})
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # INFO fields of a film / series / episode page; "_" keys are no INFO fields
        hero = self.cm.ph.getDataBeetwenMarkers(data, '<header class="c3-detail__hero', "</header>", False)[1]
        info = {}
        info["_story"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(hero, r'(?s)<p class="c3-detail__lead">(.*?)</p>')[0]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="c3-prose">(.*?)</div>')[0])
        info["_poster"] = self.cm.ph.getSearchGroups(hero, r'(?s)<figure class="c3-detail__poster[^"]*">.*?<img[^>]+src="([^"]+)"')[0]
        info["_original"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(hero, r'(?s)<p class="c3-detail__alt">(.*?)</p>')[0])
        info["_imdb"] = self.cm.ph.getSearchGroups(hero, r"imdb\.com/title/(tt\d+)")[0]
        meta = self.cm.ph.getSearchGroups(hero, r'(?s)<p class="c3-detail__meta">(.*?)</p>')[0]
        spans = [self.cleanHtmlStr(x) for x in re.findall(r"(?s)<(?:span|a)[^>]*>(.*?)</(?:span|a)>", meta)]
        for value in spans:
            if re.match(r"^(?:19|20)\d{2}$", value):
                info["year"] = value
            elif re.match(r"^(?:\d+h\s*)?\d+m(?:in)?$|^\d+ min$", value):
                info["duration"] = value
            elif re.match(r"^\d+ temporadas?$", value):
                info["seasons"] = value.split()[0]
            elif re.match(r"^\d+ episodios?$", value):
                info["episodes"] = value.split()[0]
            elif re.match(r"^\d{1,2} \w{3} \d{4}$", value):
                info["released"] = value
        score = self.cleanHtmlStr(self.cm.ph.getSearchGroups(meta, r'(?s)<span class="c3-score[^"]*"[^>]*>(.*?)</span>')[0])
        if score:
            info["rating"] = score
        status = self.cleanHtmlStr(self.cm.ph.getSearchGroups(meta, r'(?s)<span class="c3-status[^"]*">(.*?)</span>')[0])
        if status:
            info["status"] = status
        genres = [self.cleanHtmlStr(x) for x in re.findall(r'class="c3-chip" href="[^"]+">([^<]+)</a>', hero)]
        if genres:
            info["genres"] = ", ".join(sorted(set(genres), key=genres.index))
        langs = [lang for lang in LANGUAGES if 'title="%s"' % lang in self.cm.ph.getDataBeetwenMarkers(hero, "c3-detail__badges", "</p>", False)[1]]
        if langs:
            info["language"] = " / ".join(langs)
        quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(hero, r'<span class="c3-q[^"]*">([^<]+)</span>')[0])
        if quality:
            info["quality"] = quality
        for label, value in re.findall(r"(?s)<dt>(.*?)</dt><dd>(.*?)</dd>", hero):
            key = {"dirección": "director", "reparto": "actors", "país": "country"}.get(self.cleanHtmlStr(label).lower())
            if key:
                info[key] = self.cleanHtmlStr(value)
        return info

    @staticmethod
    def _metaArgs(cItem, info):
        # moviemeta query of INFO (type, title, year): no year for an episode (the show's lookup)
        year = "" if cItem.get("s_episode") else (cItem.get("meta_year") or info.get("year", ""))
        return cItem.get("meta_type") or "movie", cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", ""), year

    def getArticleContent(self, cItem):
        printDBG("Cuevana3.getArticleContent [%s]" % cItem.get("url", ""))
        info = {}
        sts, data = self.getPage(cItem.get("url", "").split("#")[0])
        if sts:
            info = self._siteInfo(data)
        story, poster, imdb, original = info.pop("_story", ""), info.pop("_poster", ""), info.pop("_imdb", ""), info.pop("_original", "")
        mediaType, metaTitle, year = self._metaArgs(cItem, info)
        meta = {}
        try:
            if imdb and not cItem.get("s_episode"):
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and metaTitle:
                meta = getMeta(mediaType, metaTitle, year)
            if not meta and original:
                meta = getMeta(mediaType, original, year)
        except Exception:
            printExc()
        meta = meta or {}
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in info:
                info.pop(siteKey, None)
        if cItem.get("s_episode"):
            # the episode page knows the episode, moviemeta the show
            info.update(siteInfo)
        plot = meta.get("plot", "")
        text = story or cItem.get("desc", "")
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
        printDBG("Cuevana3.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_years":
            self.listYears(self.currItem)
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
        CHostBase.__init__(self, Cuevana3(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cuevana3")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
