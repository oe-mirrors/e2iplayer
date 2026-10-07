# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 04.10.2026 - new host for moviesjoytv.org (Moviesjoy - movies and TV series, English)
#   - WordPress "fmovie" theme (assets and player on ghostplayer.store); lists: movies, TV series,
#     top IMDb, genres, countries, search - First page / Jump / Next page from the site's pager
#   - movies: the page's Servers config holds the embed urls (vidsrc); series: the seasons and
#     episodes come from TMDb (the API key and TMDb id from the page's Episodes config, like the
#     site's own script), the player per episode from the site's player page (getPlayTV.php)
#   - links -> urlparser (vidsrc); servers that end on the same resolver (the site's "VidSrc" and
#     "VidPlay" both land on vidsrc) are listed once, "Filemoon" (streamingnow captcha page) is not
#     supported and left out
#   - watched flag (series -> season -> episode), downloaded flag, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta (IMDb id) + the site's fields
###################################################
import base64
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://moviesjoytv.org/"


TMDB_API = "https://api.themoviedb.org/3/tv/"
EPISODE_FRAGMENT_RE = re.compile(r"#s(\d+)e(\d+)$")
PAGING_KEYS = ("base_url", "page_tpl")
VIDEO_CATEGORIES = ("mj_video",)
SERIES_CATEGORIES = ("mj_series", "mj_season")


def _str(value):
    if value is None:
        return ""
    if not isinstance(value, (type(u""), bytes)):
        value = str(value)
    return ensure_str(value).strip()


class MoviesJoy(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")
    EPISODES_PER_PAGE = 100

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "moviesjoytv", "cookie": "moviesjoytv.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["User-Agent"] = self.cm.getDefaultUserAgent("chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.cacheConfig = {}
        self.MENU = [
            {"category": "mj_list", "title": _("Movies"), "url": self.getFullUrl("category/movies/")},
            {"category": "mj_list", "title": _("TV series"), "url": self.getFullUrl("category/tv-series/")},
            {"category": "mj_list", "title": _("Top IMDb"), "url": self.getFullUrl("top-imdb/")},
            {"category": "mj_filter", "title": _("Genres"), "url": self.MAIN_URL, "filter": "genre"},
            {"category": "mj_filter", "title": _("Countries"), "url": self.MAIN_URL, "filter": "country"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("moviesjoytv")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self.cm.iriToUri(baseUrl), addParams, post_data)

    def getDefaulIcon(self, cItem=None):
        return self.getFullIconUrl("img/icon.png")

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").split("?")[0].rstrip("/").lower()

    def _pageConfig(self, data, name):
        # var <name>={...} from the base64 data: scripts of a page (Servers / Episodes)
        for b64 in re.findall(r"data:text/javascript;base64,([A-Za-z0-9+/=]+)", data):
            try:
                script = ensure_str(base64.b64decode(b64))
            except Exception:
                continue
            m = re.search(r"var\s+%s\s*=\s*(\{.*?\})\s*;?\s*$" % name, script, re.S)
            if m:
                try:
                    return json_loads(m.group(1))
                except Exception:
                    printExc()
        return {}

    def _desc(self, fields, plot=""):
        desc = " | ".join("%s: %s" % (label, value) for label, value in fields if value)
        if plot:
            desc = "%s[/br]%s" % (desc, plot) if desc else plot
        return desc

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + SERIES_CATEGORIES:
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = cItem.get("url", "")
            path = self._path(url.split("#")[0])
            category = cItem.get("category", "")
            if not path:
                return ""
            if cItem.get("type") == "video":
                m = EPISODE_FRAGMENT_RE.search(url)
                return "episode:%s#s%se%s" % (path, m.group(1), m.group(2)) if m else "video:%s" % path
            if category == "mj_series":
                return "series:%s" % path
            if category == "mj_season":
                return "season:%s#s%s" % (path, cItem.get("s_season", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listFilter(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        kind = cItem.get("filter", "genre")
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="%s">' % kind, "</ul>", False)[1]
        path = "category" if kind == "genre" else "country"
        for url, label in re.findall(r'<a href="([^"]+/%s/[^"]+)"[^>]*>([^<]+)</a>' % path, block):
            label = self.cleanHtmlStr(label)
            if not label:
                continue
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "category": "mj_list", "title": label, "url": self.getFullUrl(url), "good_for_fav": True})
            params.pop("filter", None)
            self.addDir(params)

    def _paging(self, data, baseUrl, page):
        # (url template with "{page}", last page, has a next page) from the WordPress pager
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination">', "</ul>", False)[1]
        pages = [int(p) for p in re.findall(r"/page/(\d+)/", pager)]
        lastPage = max(pages) if pages else 0
        hasNext = 'class="page-link next"' in pager or lastPage > page
        base, sep, query = baseUrl.partition("?")
        base = re.sub(r"page/\d+/?$", "", base)
        if not base.endswith("/"):
            base += "/"
        tpl = base.replace("{", "%7B").replace("}", "%7D") + "page/{page}/" + (sep + query.replace("{", "%7B").replace("}", "%7D") if sep else "")
        return tpl, lastPage, hasNext

    def _addTile(self, cItem, block, normalize):
        url = self.cm.ph.getSearchGroups(block, r'<div class="poster">\s*<a href="([^"]+)"')[0]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="meta">.*?</div>\s*<a href="[^"]+">(.*?)</a>')[0])
        if not url or not title:
            return False
        icon = self.cm.ph.getSearchGroups(block, r'data-src="([^"]+)"')[0]
        metaSpans = [self.cleanHtmlStr(s) for s in re.findall(r"(?s)<span[^>]*>(.*?)</span>", self.cm.ph.getSearchGroups(block, r'(?s)<div class="meta"><div>(.*?)</div>')[0])]
        year = next((s for s in metaSpans if re.match(r"^(?:19|20)\d{2}$", s)), "")
        kind = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<span class="type">([^<]*)</span>')[0])
        rating = self.cm.ph.getSearchGroups(block, r'bi-star-fill"></i>\s*([\d.]+)')[0]
        genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'/category/[^"]+/">([^<]+)</a>', block))
        country = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'/country/[^"]+/"[^>]*>([^<]+)</a>', block))
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="desc">(.*?)</div>')[0])
        isMovie = kind.lower() == "movie"
        fields = ((_("Year"), year), (_("Rating"), rating), (_("Genres"), genres), (_("Country"), country),
                  (_("Duration") if isMovie else _("Seasons"), " | ".join(metaSpans[2:]) if isMovie else " ".join(metaSpans[1:])))
        params = stripPagerKeys(dict(cItem), PAGING_KEYS)
        params.update({"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": self._desc(fields, plot),
                       "meta_title": title, "meta_year": year})
        params.pop("filter", None)
        if isMovie:
            params.update({"category": "mj_video", "title": "%s (%s)" % (title, year) if normalize and year else title, "meta_type": "movie"})
            self.addVideo(params)
        else:
            params.update({"category": "mj_series", "title": title, "s_title": title, "meta_type": "tv"})
            self.addDir(params)
        return True

    def listItems(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        baseUrl = cItem.get("base_url") or cItem["url"]
        tpl = cItem.get("page_tpl", "")
        url = baseUrl if page <= 1 or not tpl else tpl.format(page=page)
        printDBG("MoviesJoy.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for block in data.split('<div id="post-')[1:]:
            block = block.split('<div class="action">')[0]
            itemUrl = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)"')[0]
            if itemUrl and itemUrl not in seen and self._addTile(cItem, block, normalize):
                seen.add(itemUrl)
        if not seen and page == 1 and cItem.get("search_pattern"):
            SetIPTVPlayerLastHostError(_("No results found for: %s") % cItem["search_pattern"])
        pageTpl, lastPage, hasNext = self._paging(data, baseUrl, page)
        listItem = dict(cItem)
        listItem.update({"base_url": baseUrl, "url": baseUrl, "page_tpl": pageTpl})
        addPagingItems(self, listItem, page, hasNext and bool(seen), lastPage, pageTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MoviesJoy.listSearchResult [%s]" % searchPattern)
        pattern = (searchPattern or "").strip()
        if not pattern:
            return
        params = dict(cItem)
        params.update({"category": "mj_list", "url": self.MAIN_URL + "?s=" + urllib_quote_plus(pattern), "search_pattern": pattern, "page": 1})
        self.listItems(params)

    ###################################################
    # series -> seasons -> episodes (TMDb, like the site's script)
    ###################################################
    def _seriesConfig(self, url):
        # the page's Episodes config: tvapikey, tvid (TMDb), tvimdbid, post_id, tvplayer, language
        url = url.split("#")[0]
        if url in self.cacheConfig:
            return self.cacheConfig[url]
        sts, data = self.getPage(url)
        if not sts:
            return {}
        cfg = self._pageConfig(data, "Episodes")
        if cfg.get("tvid"):
            self.cacheConfig[url] = cfg
        return cfg

    def _tmdb(self, cfg, path):
        url = "%s%s%s?api_key=%s&language=%s" % (TMDB_API, _str(cfg.get("tvid")), path, _str(cfg.get("tvapikey")), _str(cfg.get("language")) or "en-US")
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Accept="application/json", Referer=self.MAIN_URL)
        sts, data = self.getPage(url, params)
        if not sts:
            return {}
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return {}
        return data if isinstance(data, dict) else {}

    def listSeries(self, cItem):
        printDBG("MoviesJoy.listSeries [%s]" % cItem.get("url", ""))
        cfg = self._seriesConfig(cItem["url"])
        if not cfg.get("tvid") or not cfg.get("tvapikey"):
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        info = self._tmdb(cfg, "")
        # the site hides "Specials" (season 0) too
        seasons = [s for s in info.get("seasons") or [] if isinstance(s, dict) and int(s.get("season_number") or 0) > 0]
        if not seasons:
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, s_season=int(seasons[0]["season_number"])))
            return
        for season in seasons:
            num = int(season["season_number"])
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            desc = self._desc(((_("Episodes"), _str(season.get("episode_count"))), (_("First aired"), _str(season.get("air_date")))),
                              self.cleanHtmlStr(_str(season.get("overview"))))
            params.update({"name": "category", "good_for_fav": True, "category": "mj_season", "s_season": num,
                           "title": "%s %d" % (_("Season"), num), "desc": desc})
            if season.get("poster_path"):
                params["icon"] = "https://image.tmdb.org/t/p/w342" + _str(season["poster_path"])
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("MoviesJoy.listEpisodes [%s] s%s" % (cItem.get("url", ""), cItem.get("s_season", "")))
        season = int(cItem.get("s_season", 1) or 1)
        cfg = self._seriesConfig(cItem["url"])
        if not cfg.get("tvid"):
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        today = time.strftime("%Y-%m-%d")
        episodes = []
        for ep in self._tmdb(cfg, "/season/%d" % season).get("episodes") or []:
            if not isinstance(ep, dict) or not ep.get("episode_number"):
                continue
            aired = _str(ep.get("air_date"))
            if aired and aired > today:
                continue  # not out yet - the players have nothing for it
            episodes.append(ep)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        page = max(1, int(cItem.get("page", 1) or 1))
        lastPage = (len(episodes) + self.EPISODES_PER_PAGE - 1) // self.EPISODES_PER_PAGE
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        showUrl = cItem["url"].split("#")[0]
        for ep in episodes[(page - 1) * self.EPISODES_PER_PAGE:page * self.EPISODES_PER_PAGE]:
            num = int(ep["episode_number"])
            name = self.cleanHtmlStr(_str(ep.get("name")))
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, num))
            else:
                title = " - ".join(x for x in (show, "S%02d E%02d" % (season, num), name) if x)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "good_for_fav": True, "category": "mj_video", "title": title,
                           "url": "%s#s%de%d" % (showUrl, season, num), "s_title": show, "s_season": season, "s_episode": num,
                           "meta_type": "tv", "desc": self._desc(((_("Episode"), name), (_("First aired"), _str(ep.get("air_date")))),
                                                                 self.cleanHtmlStr(_str(ep.get("overview"))))})
            if ep.get("still_path"):
                params["icon"] = "https://image.tmdb.org/t/p/w300" + _str(ep["still_path"])
            self.addVideo(params)
        if lastPage > 1:
            listItem = dict(cItem, s_season=season, category="mj_season")
            addPagingItems(self, listItem, page, page < lastPage, lastPage, showUrl.replace("{", "%7B").replace("}", "%7D"))

    ###################################################
    # links
    ###################################################
    def _serverNames(self, data):
        # {player key: label} of the server buttons ("embedru": "VidSrc", ...)
        names = {}
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="servers">', "</ul>", False)[1]
        for li in re.findall(r"(?s)<li[^>]+>.*?</li>", block):
            key = self.cm.ph.getSearchGroups(li, r"""(?:loadServer\(|data-load-embed-host=")([a-z0-9_]+)""")[0]
            if key:
                names[key] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(li, r"<span>([^<]+)</span>")[0]) or key
        return names

    def _episodePlayer(self, cfg, key, season, episode):
        # the site's player page for an episode -> its iframe (getPlayTV.php) -> the embed url
        url = "%s%s&s=%d&e=%d&sv=%s&tv=true" % (_str(cfg.get("tvplayer")), _str(cfg.get("post_id")), season, episode, key)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self.MAIN_URL)
        for _hop in range(2):
            sts, data = self.getPage(url, params)
            if not sts:
                return ""
            href = self.cm.ph.getSearchGroups(data, r"""href=["'](https?://[^"']+)""")[0]
            if href and "getPlay" not in href:
                return href.replace("&amp;", "&")
            frame = self.cm.ph.getSearchGroups(data, r"""<iframe[^>]+src=["']([^"']+)""")[0]
            if not frame:
                return ""
            params["header"] = dict(self.HEADER, Referer=url)
            url = self.cm.getFullUrl(frame.replace("&amp;", "&"), url)
        return ""

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("MoviesJoy.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url.split("#")[0])
        if not sts:
            return []
        names = self._serverNames(data)
        embeds = []
        m = EPISODE_FRAGMENT_RE.search(url)
        if m:
            cfg = self._pageConfig(data, "Episodes")
            for key in names:
                embeds.append((key, self._episodePlayer(cfg, key, int(m.group(1)), int(m.group(2)))))
        else:
            cfg = self._pageConfig(data, "Servers")
            for key in names:
                embeds.append((key, _str(cfg.get(key))))
        urltab, parsers, unsupported = [], [], []
        for key, embed in embeds:
            if not self.cm.isValidUrl(embed):
                continue
            host = self.up.getHostName(embed)
            if self.up.checkHostSupport(embed) != 1:
                unsupported.append(names.get(key, host))
                continue
            try:
                parser = self.up.getParser(embed).__name__
            except Exception:
                parser = host
            if parser in parsers:
                continue  # the same resolver behind another button - the same streams
            parsers.append(parser)
            urltab.append({"name": "%s - %s" % (names.get(key, key), host), "url": strwithmeta(embed, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported) if unsupported else _("No stream available"))
            return []
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="description[^"]*">(.*?)</div>')[0])
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("MoviesJoy.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        info = {}
        detail = self.cm.ph.getDataBeetwenMarkers(data, '<div class="detail">', '<div class="clearfix', False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, '<div class="detail">', "</section>", False)[1]
        for label, key in (("Country", "country"), ("Genre", "genres"), ("Year", "year"), ("Director", "director"),
                           ("Creator", "creator"), ("Stars", "stars"), ("Duration", "duration"), ("Quality", "quality")):
            value = self.cm.ph.getSearchGroups(detail, r"(?s)<div>%s:</div>\s*<span>(.*?)</span>" % label)[0]
            value = self.cleanHtmlStr(value.replace("</a>", "</a>|")).replace(" | ", "|").strip("| ")
            value = ", ".join(v.strip() for v in value.split("|") if v.strip() and v.strip().lower() != "trending")
            if value:
                info[key] = value
        rating = self.cm.ph.getSearchGroups(data, r'itemprop="ratingValue">([\d.]+)<')[0]
        if rating:
            info["rating"] = "%s/10" % rating
        rated = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<span class="rating">([^<]+)</span>')[0])
        if rated:
            info["rated"] = rated
        return info

    def getArticleContent(self, cItem):
        url = cItem.get("url", "")
        printDBG("MoviesJoy.getArticleContent [%s]" % url)
        sts, data = self.getPage(url.split("#")[0]) if self.cm.isValidUrl(url) else (False, "")
        data = data if sts else ""
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="description[^"]*">(.*?)</div>')[0])
        info = self._siteInfo(data)
        episodesCfg = self._pageConfig(data, "Episodes") if data else {}
        isTv = cItem.get("meta_type") == "tv" or bool(episodesCfg)
        imdbId = _str(episodesCfg.get("tvimdbid") if isTv else self._pageConfig(data, "Servers").get("imdb_id")) if data else ""
        if EPISODE_FRAGMENT_RE.search(url) and cItem.get("desc"):
            story = "%s[/br][/br]%s" % (cItem["desc"], story) if story else cItem["desc"]
        meta = {}
        try:
            if imdbId:
                meta = getMetaByImdbId("tv" if isTv else "movie", imdbId)
            if not meta and cItem.get("meta_title"):
                meta = getMeta("tv" if isTv else "movie", cItem["meta_title"], cItem.get("meta_year", "") or info.get("year", ""))
        except Exception:
            printExc()
        for key, value in meta.get("info", {}).items():
            info.setdefault(key, value)
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot not in story:
            text = "%s[/br][/br]%s" % (story, plot)
        poster = self.cm.ph.getSearchGroups(data, r'(?s)<div class="poster">\s*<img[^>]+data-src="([^"]+)"')[0]
        icon = meta.get("poster") or poster or cItem.get("icon", "")
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
        printDBG("MoviesJoy.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "mj_filter":
            self.listFilter(self.currItem)
        elif category == "mj_list":
            self.listItems(self.currItem)
        elif category == "mj_series":
            self.listSeries(self.currItem)
        elif category == "mj_season":
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, MoviesJoy(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("moviesjoytv")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in SERIES_CATEGORIES
