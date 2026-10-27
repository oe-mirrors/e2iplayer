# -*- coding: utf-8 -*-
LAST_MODIFIED = "26.10.2026"
# Created By angel_heart (Mohamed elsafty) 26.10.2026
# french-stream.net (films / series) + french-manga.net (anime), both DataLife Engine sites
import base64
import datetime
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://french-stream.net/"


MAIN_URL = "https://french-stream.net"
ANIME_URL = "https://w16.french-manga.net"
PAGING_KEYS = ("base_url", "page_tpl")
VIDEO_CATEGORIES = ("fs_video", "fs_anime_video")
SERIES_CATEGORIES = ("fs_series", "fs_season", "fs_anime_series", "fs_anime_season")
LIST_CATEGORIES = ("fs_list", "fs_anime_list")
# version keys of the film players / episode JSON in the order the links are offered
FILM_VERSIONS = (("default", ""), ("vostfr", "VOSTFR"), ("vfq", "VFQ"), ("vff", "VFF"), ("vf", "VF"), ("vo", "VO"), ("vosteng", "VOSTENG"))
EPISODE_VERSIONS = (("vf", "VF"), ("vostfr", "VOSTFR"), ("vo", "VO"))
# trakx.lol/<hoster>/newPlayer.php and kokoflix.lol/<name>_go.php only redirect to the hoster (dood, voe mirror, byse, vidara)
REDIRECTORS = ("trakx.", "kokoflix.")
# fsvid.lol ("PREMIUM") plays an ad clip instead of the film
SKIP_HOSTS = ("fsvid.lol",)
SEASON_RE = r"Saison\s*(\d+)"
ALT_TITLE_LANGS = (("jp", "Japanese"), ("fr", "French"), ("us", "American"), ("uk", "British"), ("kr", "Korean"),
                   ("ar", "Arabic"), ("es", "Spanish"), ("de", "German"), ("ru", "Russian"), ("br", "Brazilian"))


def _isAnime(url):
    return "french-manga" in (url or "")


def _isText(value):
    return hasattr(value, "startswith")


def _str(value):
    # a JSON string as native str (unicode on Py2 would not mix with the utf-8 page texts), anything else ""
    return ensure_str(value) if _isText(value) else ""


class FrenchStream(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "frenchstream", "cookie": "frenchstream.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/frenchstream135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.cacheEpisodes = {}
        self.gateCookies = {}
        self.MENU = [
            {"category": "fs_list", "title": "Films", "url": MAIN_URL + "/films/"},
            {"category": "fs_list", "title": "Séries", "url": MAIN_URL + "/s-tv/"},
            {"category": "fs_list", "title": "Films Netflix", "url": MAIN_URL + "/films/films-netflix/"},
            {"category": "fs_anime_home", "title": "ANIMES", "url": ANIME_URL + "/"},
            {"category": "fs_filter", "title": "Genres Films", "filter": "genre"},
            {"category": "fs_filter", "title": "Genres Séries", "filter": "series-genre"},
            {"category": "fs_filter", "title": "Plateformes", "filter": "platforms"},
            {"category": "fs_filter", "title": "Langues", "filter": "languages"},
            {"category": "fs_filter", "title": "Thèmes", "filter": "themes"},
            {"category": "fs_filter", "title": "Années", "filter": "date-de-sortie"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("frenchstream")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def _absUrl(self, url, base=MAIN_URL):
        url = (url or "").strip().replace("&amp;", "&").replace("\\/", "/")
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return base + url
        if url and not url.startswith("http"):
            return base + "/" + url
        return url

    def getPage(self, url, addParams=None, post_data=None):
        addParams = dict(self.defaultParams if addParams is None else addParams)
        url = self.cm.iriToUri(self._absUrl(url, ANIME_URL if _isAnime(url) else MAIN_URL))
        if self.gateCookies:
            addParams["cookie_items"] = dict(addParams.get("cookie_items") or {}, **self.gateCookies)
        sts, data = self.cm.getPage(url, addParams, post_data)
        # anti-bot page "Verification de votre navigateur": its script only sets a cookie (fsschal=...) and reloads
        cookie = re.search(r'document\.cookie="(\w+)=([^;"]+)', data or "") if sts and "<title>Verification" in (data or "")[:1000] else None
        if cookie and self.gateCookies.get(cookie.group(1)) != cookie.group(2):
            printDBG("FrenchStream.getPage anti-bot cookie %s=%s" % (cookie.group(1), cookie.group(2)))
            self.gateCookies[cookie.group(1)] = cookie.group(2)
            addParams["cookie_items"] = dict(addParams.get("cookie_items") or {}, **self.gateCookies)
            sts, data = self.cm.getPage(url, addParams, post_data)
        return sts, data

    def _ajax(self, url, referer, post_data=None):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, **{"X-Requested-With": "XMLHttpRequest", "Referer": referer, "Accept": "*/*"})
        if post_data:
            params["header"]["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        sts, data = self.getPage(url, params, post_data)
        return data if sts and data else ""

    def _ajaxJson(self, url, referer):
        data = self._ajax(url, referer).strip()
        if not data.startswith(("{", "[")):
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").split("#")[0].rstrip("/").lower()

    def _newsId(self, url):
        url = (url or "").split("#")[0]
        return self.cm.ph.getSearchGroups(url, r"[?&]newsid=(\d+)")[0] or self.cm.ph.getSearchGroups(url, r"/(\d{4,})-[^/]+\.html")[0]

    def _showTitle(self, title):
        return re.sub(r"\s*-\s*Saison.*$", "", title or "", flags=re.I).strip() or title

    def _episodeTitle(self, show, season, episode, epTitle=""):
        title = "%s - %s" % (show, formatSxxExx(season, episode)) if IsMediaNamingNormalized() else "%s - S%02dE%02d" % (show, season, episode)
        return "%s - %s" % (title, epTitle) if epTitle else title

    def _getWatchedKeyForItem(self, cItem):
        try:
            url = cItem.get("url", "")
            keyId = self._newsId(url) or self._path(url)
            if not keyId:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                m = re.search(r"#s(\d+)e(\d+)", url)
                if m:
                    return "episode:%s#s%se%s" % (keyId, m.group(1), m.group(2))
                return "video:%s" % keyId
            if category in ("fs_series", "fs_anime_series"):
                return "series:%s" % keyId
            if category in ("fs_season", "fs_anime_season"):
                return "season:%s#s%s" % (keyId, cItem.get("s_season", ""))
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + SERIES_CATEGORIES:
                return json_dumps({k: cItem[k] for k in self.FAV_FIELDS if k in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # filters
    ###################################################
    def _addFilterItem(self, cItem, url, label, seen):
        label = self.cleanHtmlStr(label)
        if not label or len(label) > 40 or url in seen:
            return
        seen.add(url)
        params = stripPagerKeys(dict(cItem), PAGING_KEYS)
        params.pop("filter", None)
        params.update({"name": "category", "category": "fs_list", "title": label, "url": self._absUrl(url), "good_for_fav": True})
        self.addDir(params)

    def listFilter(self, cItem):
        sts, data = self.getPage(MAIN_URL + "/")
        data = data if sts else ""
        kind = cItem.get("filter", "genre")
        seen = set()
        fallback = []
        if kind == "genre":
            for section in re.findall(r'(?s)<div class="menu-section">.*?</div>\s*</div>', data)[:10]:
                if "Par Genre" in section or "fa-tags" in section:
                    data = section
                    break
            pattern = (r'href="(/films/(?!vf/|vostfr/|top-film/|cultes/|films-netflix/)[a-z0-9\-]+/|/art-martiaux/|/xfsearch/genre[^"]+)"'
                       r'[^>]*>(?:<[^>]+>)*([^<]+)</a>')
            fallback = [("/films/actions/", "Action"), ("/films/aventures/", "Aventure"), ("/films/animations/", "Animation"),
                        ("/art-martiaux/", "Arts Martiaux"), ("/films/biopics/", "Biopic"), ("/films/comedies/", "Comédie"),
                        ("/films/drames/", "Drame"), ("/films/documentaires/", "Documentaire"), ("/films/epouvante-horreurs/", "Horreur"),
                        ("/films/historiques/", "Historique"), ("/films/espionnages/", "Espionnage"), ("/films/familles/", "Famille"),
                        ("/films/fantastiques/", "Fantastique"), ("/films/guerres/", "Guerre"), ("/films/policiers/", "Policier"),
                        ("/films/romances/", "Romance"), ("/films/science-fictions/", "Science fiction"),
                        ("/xfsearch/genre-1/spectacle/", "Spectacle"), ("/films/thrillers/", "Thriller"), ("/films/westerns/", "Western")]
        elif kind == "series-genre":
            pattern = (r'href="(/(?:action-serie-|aventure-series-|animation-serie-|serie-biopic-|comedie-serie-|drame-serie-|documentaire-serie-|'
                       r'familles-series-|fantastique-series-|thriller-series-|romance-series-|judiciare-series-|science-fiction-series-|'
                       r'serie-historiques-|medical-series-|policier-series-|horreur-serie-|western-series-|k-drama-)[^"]*)"[^>]*>(?:<[^>]+>)*([^<]+)</a>')
            fallback = [("/action-serie-/", "Action"), ("/aventure-series-/", "Aventure"), ("/animation-serie-//", "Animation"),
                        ("/serie-biopic-/", "Biopic"), ("/comedie-serie-/", "Comédie"), ("/drame-serie-/", "Drame"),
                        ("/documentaire-serie-/", "Documentaire"), ("/familles-series-/", "Famille"), ("/fantastique-series-/", "Fantastique"),
                        ("/thriller-series-/", "Thriller"), ("/romance-series-/", "Romance"), ("/judiciare-series-/", "Judiciaire"),
                        ("/science-fiction-series-/", "Science-Fiction"), ("/serie-historiques-/", "Historique"), ("/medical-series-/", "Médical"),
                        ("/policier-series-//", "Policier"), ("/horreur-serie-/", "Horreur"), ("/western-series-/", "Western"), ("/k-drama-//", "K-DRAMA")]
        elif kind == "platforms":
            pattern = (r'href="(/s-tv/(?:serie-amazon-prime-videos|netflix-series-|series-disney-plus|series-apple-tv|s-vf|s-vostfr|s-vo|sries-du-moment)/)"'
                       r'[^>]*>(?:<[^>]+>)*([^<]+)</a>')
            fallback = [("/s-tv/s-vf/", "Séries VF"), ("/s-tv/s-vostfr/", "Séries VOSTFR"), ("/s-tv/s-vo/", "Séries VOSTENG"),
                        ("/s-tv/serie-amazon-prime-videos/", "Amazon Prime Video"), ("/s-tv/netflix-series-/", "Netflix"),
                        ("/s-tv/series-disney-plus/", "Disney+"), ("/s-tv/series-apple-tv/", "Apple TV+"), ("/s-tv/sries-du-moment/", "Séries du moment")]
        elif kind == "languages":
            pattern = r'href="(/xfsearch/lang/[^"]+)"[^>]*>(?:<[^>]+>)*([^<]+)</a>'
        elif kind == "themes":
            pattern = r'href="(/xfsearch/(?:ftagz|xx89)/[^"]+)"[^>]*>(?:<[^>]+>)*([^<]+)</a>'
        else:
            # years: the ones the menu links first, then every year back to 1980
            years = sorted({int(y) for y in re.findall(r"/xfsearch/date-de-sortie/(\d{4})/", data)}, reverse=True)
            years += [y for y in range(datetime.date.today().year + 1, 1979, -1) if y not in years]
            for year in years:
                self._addFilterItem(cItem, "/xfsearch/date-de-sortie/%d/" % year, "Année %d" % year, seen)
            return
        for url, label in re.findall(pattern, data, re.I):
            self._addFilterItem(cItem, url, label, seen)
        if not seen:
            for url, label in fallback:
                self._addFilterItem(cItem, url, label, seen)

    ###################################################
    # lists
    ###################################################
    def _pageTpl(self, data, base):
        # the page navigation links "/index.php?cstart=N&do=cat&category=..." (or ".../page/N/")
        nav = self.cm.ph.getSearchGroups(data, r'(?s)(<span class="navigation">.*?</span>)\s*(?:</span>|<span class="pnext">)')[0] or \
            self.cm.ph.getSearchGroups(data, r'(?s)(<span class="pnext">.*?</span>)')[0]
        href = self.cm.ph.getSearchGroups(nav, r'href="([^"]*(?:cstart=\d+|/page/\d+/)[^"]*)"')[0]
        if not href:
            return "", 0
        href = self._absUrl(href, base)
        tpl = re.sub(r"cstart=\d+", "cstart={page}", href) if "cstart=" in href else re.sub(r"/page/\d+/", "/page/{page}/", href)
        pages = [int(x) for x in re.findall(r"(?:cstart=|/page/)(\d+)", nav)]
        return tpl, max(pages) if pages else 0

    def listItems(self, cItem):
        anime = cItem.get("category") == "fs_anime_list"
        base = ANIME_URL if anime else MAIN_URL
        page = max(1, int(cItem.get("page", 1) or 1))
        baseUrl = self._absUrl(cItem.get("base_url") or cItem.get("url"), base)
        tpl = cItem.get("page_tpl", "")
        url = tpl.format(page=page) if page > 1 and tpl else baseUrl
        printDBG("FrenchStream.listItems page[%s] url[%s]" % (page, url))
        sts, data = self.getPage(url)
        if not sts:
            return
        seen = set()
        for block in data.split('<div class="short">')[1:]:
            itemUrl = self.cm.ph.getSearchGroups(block, r'<a class="short-poster[^"]*" href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<div class="short-title">([^<]+)</div>')[0])
            if not itemUrl or not title or itemUrl in seen:
                continue
            seen.add(itemUrl)
            icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
            version = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="film-version"[^>]*>.*?>([^<]+)</a>')[0])
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="film-quality"[^>]*>.*?>([^<]+)</a>')[0]) if anime else ""
            eps = self.cm.ph.getSearchGroups(block, r'class="mli-eps">([^<]+)<')[0].strip()
            year = self.cm.ph.getSearchGroups(block, r'(?s)class="short-year"[^>]*>.*?((?:19|20)\d{2})')[0]
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<span id="desc-\d+"[^>]*>(.*?)</span>')[0])
            if anime:
                isSeries = ("Saison" in title or eps not in ("", "1 / 1")) and quality.lower() != "film"
            else:
                isSeries = "Saison" in title or eps != ""
            showTitle = self._showTitle(title)
            info = " | ".join(x for x in (year, version, quality, "Ep %s" % eps if eps else "") if x)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "url": self._absUrl(itemUrl, base), "icon": self._absUrl(icon, base), "title": title,
                           "desc": "%s[/br]%s" % (info, story) if info and story else (info or story),
                           "meta_title": showTitle, "meta_year": year})
            if isSeries:
                params.update({"category": "fs_anime_series" if anime else "fs_series", "s_title": showTitle, "meta_type": "tv"})
                self.addDir(params)
            else:
                if year and IsMediaNamingNormalized() and year not in title:
                    params["title"] = "%s (%s)" % (title, year)
                params.update({"category": "fs_anime_video" if anime else "fs_video", "meta_type": "movie"})
                self.addVideo(params)
        lastPage = int(cItem.get("last_page", 0) or 0)
        if not tpl:
            tpl, lastPage = self._pageTpl(data, base)
        listItem = dict(cItem)
        listItem.update({"base_url": baseUrl, "url": baseUrl, "page_tpl": tpl, "last_page": lastPage})
        addPagingItems(self, listItem, page, bool(tpl and seen and page < lastPage), lastPage, tpl)

    def listAnimeHome(self, cItem):
        for title, path in (("Récemment mises à jour", "/manga-streaming-1/"), ("Films D'Animation", "/manga-streaming-1/film-danimation/"),
                            ("Vos Demandes", "/manga-streaming/manga-demand/"), ("Coups de Cœur", "/manga-streaming-1/coups-de-cur/")):
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "category": "fs_anime_list", "title": title, "url": ANIME_URL + path, "good_for_fav": True})
            self.addDir(params)
        sts, data = self.getPage(ANIME_URL + "/")
        if not sts:
            return
        seen = set()
        # genres, VF / VOSTFR, status, tags
        for pattern in (r'/xfsearch/manga_genre/[^"]+', r'/(?:mangas-vf|mangas-vostfr)/|/xfsearch/version-serie/[^"]+',
                        r'/xfsearch/serie-statut/[^"]+', r'/xfsearch/tagz/[^"]+'):
            for url, label in re.findall(r'href="(%s)"[^>]*>(?:<[^>]+>)*([^<]+)</a>' % pattern, data, re.I):
                label = self.cleanHtmlStr(label)
                if url in seen or not label:
                    continue
                seen.add(url)
                params = stripPagerKeys(dict(cItem), PAGING_KEYS)
                params.update({"name": "category", "category": "fs_anime_list", "title": label, "url": ANIME_URL + url, "good_for_fav": True})
                self.addDir(params)

    ###################################################
    # search
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = (searchPattern or "").strip()
        if not pattern:
            return
        # the ajax search of each site answers with one list (no further pages)
        seen = set()
        for base in (MAIN_URL, ANIME_URL):
            data = self._ajax(base + "/engine/ajax/search.php", base + "/", {"query": pattern, "page": "1"})
            for block in re.split(r"<div\s+class=['\"]search-item", data)[1:]:
                self._addSearchItem(cItem, block, base, seen)
        if not seen:
            SetIPTVPlayerLastHostError(_("No results found for: %s") % pattern)

    def _addSearchItem(self, cItem, block, base, seen):
        anime = base == ANIME_URL
        icon = self.cm.ph.getSearchGroups(block, r"<img[^>]+src=['\"]([^'\"]+)['\"]")[0]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"(?s)<div\s+class=['\"]search-title['\"][^>]*>(.*?)</div>")[0])
        url = self.cm.ph.getSearchGroups(block, r"location\.href=['\"]([^'\"]+)['\"]")[0]
        seasons = self.cm.ph.getSearchGroups(block, r"data-seasons='([^']+)'")[0]
        if seasons:
            # a french-stream series: data-seasons='[{"n":1,"l":"/..-saison-1.html","p":"poster"}, ...]' -> its last season
            try:
                last = sorted(json_loads(seasons.replace("&quot;", '"')), key=lambda x: int(x.get("n", 0) or 0))[-1]
                url, icon = _str(last.get("l")) or url, _str(last.get("p")) or icon
            except Exception:
                printExc()
        url = self._absUrl(url, base)
        if not url or url in seen:
            return
        seen.add(url)
        if not title:
            title = re.sub(r"^\d+-", "", url.rsplit("/", 1)[-1]).replace(".html", "").replace("-", " ").title()
        title = re.sub(r"\s*-\s*s.rie$", "", title)
        if anime:
            isSeries = not ("Film" in title and "Saison" not in title)
        else:
            isSeries = bool(seasons) or "Saison" in title or re.search(r"\bS\d+", title) is not None
        # "Title (2023)" / "Show - Saison 2 (2008)": the year goes to meta_year
        year = self.cm.ph.getSearchGroups(title, r"\(((?:19|20)\d{2})\)\s*$")[0]
        showTitle = self._showTitle(re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", title))
        params = stripPagerKeys(dict(cItem), PAGING_KEYS)
        params.update({"name": "category", "good_for_fav": True, "url": url, "icon": self._absUrl(icon, base), "title": title,
                       "meta_title": showTitle, "meta_year": year})
        if isSeries:
            params.update({"category": "fs_anime_series" if anime else "fs_series", "s_title": showTitle, "meta_type": "tv"})
            self.addDir(params)
        else:
            params.update({"category": "fs_anime_video" if anime else "fs_video", "meta_type": "movie"})
            self.addVideo(params)

    ###################################################
    # series: the other seasons as folders, then the episodes of the opened season
    ###################################################
    def _episodesJson(self, url):
        # french-stream: static/series/<id>.js, french-manga: manga_episodes_api.php?id=<id>
        # {"vf": {"1": {"vidzy": url, ...}}, "vostfr": {...}, "vo": {...}, "info": {"1": {"title", "poster", "synopsis"}}}
        newsId = self._newsId(url)
        if not newsId:
            return {}
        if newsId not in self.cacheEpisodes:
            if _isAnime(url):
                js = self._ajaxJson(ANIME_URL + "/engine/ajax/manga_episodes_api.php?id=%s" % newsId, url.split("#")[0])
            else:
                js = self._ajaxJson(MAIN_URL + "/static/series/%s.js" % newsId, MAIN_URL + "/index.php?newsid=%s" % newsId)
            if not isinstance(js, dict):
                return {}
            self.cacheEpisodes[newsId] = js
        return self.cacheEpisodes[newsId]

    def _seasonFolders(self, cItem, data, show):
        url = cItem["url"].split("#")[0]
        anime = _isAnime(url)
        base = ANIME_URL if anime else MAIN_URL
        newsId = self._newsId(url) or self.cm.ph.getSearchGroups(data, r'id="serie-data"[^>]*data-newsid="(\d+)"')[0]
        tag = self.cm.ph.getSearchGroups(data, r'xfname=tagz&(?:amp;)?xf=([^"&]+)')[0]
        seasons = {}
        for sUrl, inner in re.findall(r'(?s)<div[^>]*class="season-card"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', data):
            num = self.cm.ph.getSearchGroups(inner, SEASON_RE, ignoreCase=True)[0] or self.cm.ph.getSearchGroups(sUrl, r"saison[-_]?(\d+)", ignoreCase=True)[0]
            if num and int(num) > 0:
                seasons.setdefault(int(num), (self._absUrl(sUrl, base), self.cm.ph.getSearchGroups(inner, r'<img[^>]+src="([^"]+)"')[0]))
        if not seasons and newsId and (tag or anime):
            # get_seasons.php lists the other seasons of the show (not the one of the page); french-stream finds them
            # by the series tag (s-NNN), french-manga by the show title
            if anime:
                api = "%s/engine/ajax/get_seasons.php?news_id=%s&title_base=%s" % (base, newsId, urllib_quote_plus(show))
            else:
                api = "%s/engine/ajax/get_seasons.php?serie_tag=%s&news_id=%s" % (base, urllib_quote_plus(tag), newsId)
            for season in self._ajaxJson(api, url) or []:
                sUrl = _str(season.get("full_url")) if isinstance(season, dict) else ""
                if not sUrl:
                    continue
                num = str(season.get("season_number", "") or "") or self.cm.ph.getSearchGroups(_str(season.get("title")), SEASON_RE, ignoreCase=True)[0] or \
                    self.cm.ph.getSearchGroups(sUrl, r"saison[-_]?(\d+)", ignoreCase=True)[0]
                if num.isdigit() and int(num) > 0:
                    seasons.setdefault(int(num), (self._absUrl(sUrl, base), _str(season.get("affiche"))))
        for num in sorted(seasons):
            sUrl, icon = seasons[num]
            if sUrl == url:
                continue
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "good_for_fav": True, "category": "fs_anime_season" if anime else "fs_season",
                           "s_season": num, "url": sUrl, "title": "%s %d" % (_("Season"), num), "s_title": show,
                           "icon": self._absUrl(icon, base) or cItem.get("icon", ""), "desc": ""})
            self.addDir(params)

    def listSeries(self, cItem, withSeasons):
        url = cItem["url"].split("#")[0]
        printDBG("FrenchStream.listSeries [%s] seasons[%s]" % (url, withSeasons))
        sts, data = self.getPage(url)
        if not sts:
            return
        season = self.cm.ph.getSearchGroups(data, r'data-title="[^"]*Saison\s*(\d+)', ignoreCase=True)[0] or \
            self.cm.ph.getSearchGroups(data, r'(?s)<h1[^>]*id="s-title"[^>]*>.*?Saison\s*(\d+)', ignoreCase=True)[0] or cItem.get("s_season") or "1"
        season = int(season)
        show = self._showTitle(self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<div[^>]*id="serie-data"[^>]*data-title="([^"]+)"')[0]) or
                               cItem.get("s_title", "") or cItem.get("title", ""))
        if withSeasons:
            self._seasonFolders(cItem, data, show)
        category = "fs_anime_video" if _isAnime(url) else "fs_video"
        episodes = set()
        js = self._episodesJson(url)
        for key, _label in EPISODE_VERSIONS:
            if isinstance(js.get(key), dict):
                episodes.update(int(k) for k in js[key] if str(k).isdigit())
        info = js.get("info") if isinstance(js.get("info"), dict) else {}
        if not episodes:
            # the episode list of the page itself (french-stream rows / french-manga elink blocks)
            episodes.update(int(n) for n in re.findall(r'class="[^"]*episode-row[^"]*"[^>]*data-num="(\d+)"', data))
            episodes.update(int(n) for n in re.findall(r'<div id="episode(\d+)" class="fullsfeature">', data))
            if not episodes:
                episodes.update(range(1, len(re.findall(r'<div class="elink"', data)) + 1))
        if not episodes:
            if not self.currList:
                params = dict(cItem)
                params.update({"category": category, "meta_type": "movie"})
                self.addVideo(params)
            return
        for num in sorted(episodes):
            epInfo = info.get(str(num)) if isinstance(info.get(str(num)), dict) else {}
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "good_for_fav": True, "category": category, "url": "%s#s%de%d" % (url, season, num),
                           "title": self._episodeTitle(show, season, num, self.cleanHtmlStr(_str(epInfo.get("title")))),
                           "s_title": show, "s_season": season, "s_episode": num, "meta_type": "tv", "meta_title": show,
                           "meta_year": cItem.get("meta_year", ""), "icon": self._absUrl(_str(epInfo.get("poster"))) or cItem.get("icon", ""),
                           "desc": self.cleanHtmlStr(_str(epInfo.get("synopsis")))})
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def _addPlayer(self, players, label, url):
        label, url = _str(label), self._absUrl(_str(url))
        if url.startswith("http") and not any(x in url for x in SKIP_HOSTS) and url not in [x[1] for x in players]:
            players.append((label, url))

    def _filmPlayers(self, url, data):
        players = []
        newsId = self._newsId(url) or self.cm.ph.getSearchGroups(data, r"newsid=(\d+)")[0]
        js = self._ajaxJson(MAIN_URL + "/engine/ajax/film_api.php?id=%s" % newsId, url) if newsId and not _isAnime(url) else None
        if isinstance(js, dict) and isinstance(js.get("players"), dict):
            for provider, versions in js["players"].items():
                if isinstance(versions, dict):
                    for key, version in FILM_VERSIONS:
                        self._addPlayer(players, provider.upper() + (" (%s)" % version if version else ""), versions.get(key))
        if not players:
            for href, label in re.findall(r'(?s)<a href="(https://[^"]+)"[^>]*target="seriePlayer"[^>]*>(.*?)</a>', data):
                self._addPlayer(players, self.cleanHtmlStr(label).upper() or self.up.getHostName(href).upper(), href)
        if not players:
            for b64 in re.findall(r"atob\([\"']([A-Za-z0-9+/=]{30,})[\"']\)", data):
                try:
                    href = base64.b64decode(b64).decode("utf-8", "ignore")
                except Exception:
                    continue
                self._addPlayer(players, self.up.getHostName(href).upper(), href)
        return players

    def _episodePlayers(self, cItem):
        js = self._episodesJson(cItem["url"])
        episode = str(cItem.get("s_episode", "") or "")
        keys = [episode] if episode else ["0", "movie", "film", "1"]
        if not episode:
            # an anime film: its players sit under "0" / "1" or the only key there is
            for version, _label in EPISODE_VERSIONS:
                keys += list(js[version]) if isinstance(js.get(version), dict) else []
        players = []
        for key in keys:
            for version, label in EPISODE_VERSIONS:
                episodeData = js[version].get(key) if isinstance(js.get(version), dict) else None
                if isinstance(episodeData, dict):
                    for provider, url in episodeData.items():
                        self._addPlayer(players, "%s (%s)" % (provider.upper(), label), url)
            if players:
                break
        return players

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("FrenchStream.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        pageUrl = url.split("#")[0]
        data = ""
        players = self._episodePlayers(cItem) if cItem.get("s_episode") or _isAnime(pageUrl) else []
        if not players:
            sts, data = self.getPage(pageUrl)
            if not sts:
                return []
            players = self._filmPlayers(pageUrl, data)
        referer = (ANIME_URL if _isAnime(pageUrl) else MAIN_URL) + "/"
        urltab, unsupported = [], []
        for label, embed in players:
            if not any(x in embed for x in REDIRECTORS) and self.up.checkHostSupport(embed) != 1:
                unsupported.append(label)
                continue
            urltab.append({"name": label, "url": strwithmeta(embed, {"Referer": referer}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported) if unsupported else _("No stream available"))
            return []
        story = cItem.get("desc", "") if cItem.get("s_episode") else self._story(data)
        # the same moviemeta query as INFO, so a download answers from its cache
        metaQuery = sidecarMetaQuery(cItem.get("meta_type") or "movie", cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", ""),
                                     cItem.get("meta_year", ""), "", skip=())
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story, metaQuery))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("FrenchStream.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if any(x in videoUrl for x in REDIRECTORS):
            # 302 / 303 to the real hoster
            referer = videoUrl.meta.get("Referer", "") if hasattr(videoUrl, "meta") else ""
            referer = referer or MAIN_URL + "/"
            params = dict(self.defaultParams, header=dict(self.HEADER, Referer=referer), no_redirection=True)
            sts, _data = self.getPage(videoUrl, params)
            target = self.cm.meta.get("location", "") if sts else ""
            if not self.cm.isValidUrl(target) or target == videoUrl:
                SetIPTVPlayerLastHostError(_("No stream available"))
                return []
            videoUrl = strwithmeta(target, {"Referer": referer})
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _story(self, data):
        for pattern in (r'(?s)<div[^>]*id="s-desc"[^>]*>(.*?)</div>', r'(?s)<div class="fdesc[^"]*">(.*?)</div>',
                        r'(?s)<div class="fullstory[^"]*">(.*?)</div>'):
            story = self.cleanHtmlStr(re.sub(r'(?s)<p[^>]*class="desc-text"[^>]*>.*?</p>', "", self.cm.ph.getSearchGroups(data or "", pattern)[0]))
            if story:
                return story
        return ""

    def _altTitles(self, url):
        js = self._episodesJson(url)
        altTitles = js.get("alt_titles") if isinstance(js.get("alt_titles"), dict) else {}
        parts = []
        for code, name in ALT_TITLE_LANGS:
            titles = [t.strip() for t in re.split(r"[|~]", _str(altTitles.get(code))) if t.strip()]
            if titles:
                parts.append("%s: %s" % (name, ", ".join(titles)))
        return " | ".join(parts)

    def getArticleContent(self, cItem):
        url = cItem.get("url", "").split("#")[0]
        printDBG("FrenchStream.getArticleContent [%s]" % url)
        sts, data = self.getPage(url) if self.cm.isValidUrl(url) else (False, "")
        data = data if sts else ""
        title, year = cItem.get("title", ""), ""
        titleBlock = self.cm.ph.getSearchGroups(data, r'(?s)<h1[^>]*id="s-title"[^>]*>(.*?)</h1>')[0]
        if titleBlock:
            year = self.cm.ph.getSearchGroups(titleBlock, r'(?s)class="tag release_date"[^>]*>.*?(\d{4})')[0] or \
                self.cm.ph.getSearchGroups(data, r'(?s)<span[^>]*class="release"[^>]*>.*?(\d{4})')[0] or self.cm.ph.getSearchGroups(titleBlock, r"(\d{4})")[0]
            titleBlock = re.sub(r'(?s)<span[^>]*(?:class="tag release_date"|id="fav-\d+")[^>]*>.*?</span>', "", titleBlock)
            title = re.sub(r"\s*-\s*\d{4}\s*$", "", self.cleanHtmlStr(titleBlock)) or title
        facts = self.cm.ph.getSearchGroups(data, r'(?s)<div[^>]*class="facts"[^>]*>(.*?)</div>')[0]
        genres = []
        for block in re.findall(r'(?s)<span[^>]*class="genres"[^>]*>(.*?)</span>', facts):
            for genre in re.findall(r"(?s)<a[^>]*>(.*?)</a>", block):
                genre = self.cleanHtmlStr(genre)
                if genre and genre not in genres:
                    genres.append(genre)
        # <ul id="s-list"> / <ul class="flist-col"><li><span>Label:</span> value or <a>values</a></li>
        fields = {}
        lists = self.cm.ph.getSearchGroups(data, r'(?s)<ul[^>]*id="s-list"[^>]*>(.*?)</ul>')[0]
        for block in re.findall(r'(?s)<ul[^>]*class="flist-col"[^>]*>(.*?)</ul>', data):
            if any(k in block for k in ("Version:", "Qualité:", "Quality:", "Langue", "Titre")):
                lists += block
        for li in re.findall(r"(?s)<li[^>]*>(.*?)</li>", lists):
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(li, r"(?s)<span[^>]*>(.*?)</span>")[0]).rstrip(":").strip().lower()
            if not label:
                continue
            values = []
            for value in re.findall(r"(?s)<a[^>]*>(.*?)</a>", li):
                value = self.cleanHtmlStr(value)
                if value and value not in values:
                    values.append(value)
            fields[label] = ", ".join(values) if values else self.cleanHtmlStr(li.split("</span>", 1)[-1])

        def field(*names):
            for label, value in fields.items():
                if value and any(n in label for n in names):
                    return value
            return ""

        other = {"original_title": field("original title", "titre original") or title,
                 "alternate_title": self._altTitles(url) if _isAnime(url) else "",
                 "genres": ", ".join(genres), "director": field("director", "réalisateur"), "quality": field("quality", "qualité"),
                 "year": field("release date", "date de sortie") or year, "language": field("original language", "langue"),
                 "version": field("version"), "cast": field("cast", "acteurs", "avec", "casting"),
                 "age_limit": self.cleanHtmlStr(self.cm.ph.getSearchGroups(facts, r'(?s)<span[^>]*class="certification"[^>]*>(.*?)</span>')[0]),
                 "duration": self.cleanHtmlStr(self.cm.ph.getSearchGroups(facts, r'(?s)<span[^>]*class="runtime"[^>]*>(.*?)</span>')[0])}
        other = {k: v for k, v in other.items() if v}
        story = self._story(data)
        poster = self.cm.ph.getSearchGroups(data, r'<img[^>]*class="dvd-thumbnail"[^>]*src="([^"]+)"')[0] or \
            self.cm.ph.getSearchGroups(data, r'<img[^>]*src="([^"]+)"[^>]*class="dvd-thumbnail"')[0]
        # moviemeta fills what the page does not have (rating, plot, poster ...), the page's own fields win
        meta = {}
        try:
            meta = getMeta(cItem.get("meta_type") or "movie", cItem.get("meta_title") or cItem.get("s_title") or title,
                           cItem.get("meta_year") or self.cm.ph.getSearchGroups(other.get("year", ""), r"((?:19|20)\d{2})")[0])
        except Exception:
            printExc()
        other = dict(meta.get("info", {}), **other)
        story = story or meta.get("plot", "")
        images = [self._absUrl(poster, ANIME_URL if _isAnime(url) else MAIN_URL), cItem.get("icon", ""), meta.get("poster", "")]
        if cItem.get("s_episode"):
            # an episode: its own title, synopsis and still first, the fields of its season below
            title, story = cItem.get("title", ""), cItem.get("desc", "") or story
            images.insert(0, cItem.get("icon", ""))
        unique = []
        for image in images:
            if image and image not in unique:
                unique.append(image)
        return [{"title": title, "text": story or cItem.get("desc", ""), "images": [{"title": "", "url": x} for x in unique], "other_info": other}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name")
        category = self.currItem.get("category", "")
        printDBG("FrenchStream.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "fs_filter":
            self.listFilter(self.currItem)
        elif category in LIST_CATEGORIES:
            self.listItems(self.currItem)
        elif category == "fs_anime_home":
            self.listAnimeHome(self.currItem)
        elif category in ("fs_series", "fs_anime_series"):
            self.listSeries(self.currItem, True)
        elif category in ("fs_season", "fs_anime_season"):
            self.listSeries(self.currItem, False)
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
        CHostBase.__init__(self, FrenchStream(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("frenchstream")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + SERIES_CATEGORIES
