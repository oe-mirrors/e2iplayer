# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 07.12.2025 - Mr.X
# 09.10.2026 - host standard, filmaon.bz -> filmaon.live (new "film24" card theme on DooPlay):
#   - cards parsed from the film24 grid (title, year, quality, genre), First / Jump / Next page with the last page
#     from the pager (also on search and year pages, which have no rel="next"), genres + countries from the site
#     menu, the years that have titles from the site's REST API, opened via release/<year>/ (the old "releases"
#     box is gone), search
#   - seasons / episodes read from the series page on every call (the old season rows carried the season HTML);
#     episodes keep their own page url (watched key + downloaded marker), seasons the series url + "#s<season>"
#   - watched flag (series -> season -> episode), favourites reopen without state (also the old rows - their
#     filmaon.bz urls are moved to the current domain), "Title (Year)" / "Show - SxxExx" names, sidecar on the
#     links, INFO via moviemeta merged with the site's fields (synopsis, genres, ratings, original title,
#     air dates, seasons / episodes)
#   - links: doo_player_ajax "embed_url" (vk / byse / abyss / dood / turbovid), default user agent
# 10.10.2026 - "Annem (2019) aKa My Mother": year no longer doubled; links of unsupported hosters are skipped;
#   the old "Year" favourite opens the year list; the year list asks the API for the newest years first
import datetime
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://filmaon.live/"


# the site moved filmaon.bz -> filmaon.live: urls of older favourites
OLD_DOMAIN_RE = re.compile(r"^https?://(?:www\.)?filmaon\.[a-z]+/")
# "Title (2026)" / "Title (2019) HD" -> ("Title", "2026")
TITLE_YEAR_RE = re.compile(r"^(.*?)\s*\(((?:19|20)\d\d)\)(?:\s*(?:HD|FHD|4K|SD|CAM))?\s*$")
FIRST_YEAR = 1950


class Filmaon(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Filmaon", "cookie": "Filmaon.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("wp-content/themes/dooplay-filmaon-cinema-v41/assets/icons/filmaon-192.png")
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("filma/")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("seriale/")},
                     {"category": "list_value", "title": _("Genres"), "s": "ZHANRET"},
                     {"category": "list_value", "title": _("Country"), "s": "SHTETET"},
                     {"category": "list_years", "title": _("Year")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("filmaon")
        self.wfInitFolderCache()

    def _fixUrl(self, url):
        return OLD_DOMAIN_RE.sub(self.MAIN_URL, str(url or ""))

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._fixUrl(baseUrl).split("#", 1)[0], addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if cItem.get("type", "") == "video":
                prefix = "video"
            else:
                prefix = {"list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
                season = self._season(cItem)
                if prefix == "season" and "#s" not in url and season:
                    # season rows from before 09.10.2026 carried the plain series url
                    url = "%s#s%s" % (url, season)
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _season(self, cItem):
        season = str(cItem.get("season", "") or "")
        if not season:
            # season rows of the old version: the season HTML in "se", the number in the title
            season = self.cm.ph.getSearchGroups(cItem.get("se", ""), r"se-t[^>]*>(\d+)<")[0] or self.cm.ph.getSearchGroups(cItem.get("title", ""), r" - \D*(\d+)\s*$")[0]
        return season

    @staticmethod
    def _pageUrlTpl(url):
        # https://filmaon.live/genre/action/page/{page}/ and https://filmaon.live/page/{page}/?s=..
        base, query = (url.split("?", 1) + [""])[:2]
        base = re.sub(r"/page/\d+/?$", "/", base).rstrip("/").replace("{", "{{").replace("}", "}}")
        query = query.replace("{", "{{").replace("}", "}}")
        return base + "/page/{page}/" + ("?" + query if query else "")

    def _splitTitle(self, title):
        m = TITLE_YEAR_RE.match(title)
        if m:
            return m.group(1), m.group(2)
        # the year inside the title: "Annem (2019) aKa My Mother" -> ("Annem aKa My Mother", "2019")
        m = re.match(r"^(.*?)\s*\(((?:19|20)\d\d)\)\s*(.+)$", title)
        if m:
            return ("%s %s" % (m.group(1), m.group(3))).strip(), m.group(2)
        return title, ""

    def _siteInfo(self, data):
        # the fields of a movie / series / episode page: (info dict, synopsis, year)
        info = {}
        for label, value in re.findall(r'(?s)<b class="variante">([^<]+)</b>\s*<span class="valor">(.*?)</span>\s*</div>', data):
            label, value = self.cleanHtmlStr(label), self.cleanHtmlStr(value)
            # Albanian labels: original title, seasons, episodes, first / last air date
            key = {"Titulli": "original_title", "Sezone": "seasons", "Episode": "episodes"}.get(label.split(" ")[0], "")
            if "transmetimit" in label:
                key = "last_air_date" if "fundit" in label else "first_air_date"
            elif "IMDb" in label:
                key, value = "imdb_rating", value.split(" ")[0]
            elif "TMDb" in label:
                key, value = "tmdb_rating", value.split(" ")[0]
            if key and value:
                info[key] = value
        genres = self.cm.ph.getDataBeetwenMarkers(data, '<div class="sgeneros">', "</div>", False)[1]
        genres = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r">([^<]+)</a>", genres))
        if genres:
            info["genres"] = genres
        cast = []
        for name in re.findall(r'itemprop="actor"[^>]*>.*?itemprop="name" content="([^"]+)"', data[:300000], re.S)[:6]:
            if name not in cast:
                cast.append(name)
        if cast:
            info["cast"] = ", ".join(cast)
        director = self.cm.ph.getSearchGroups(data, r'(?s)itemprop="director"[^>]*>.*?itemprop="name" content="([^"]+)"')[0]
        if director:
            info["director"] = director
        released = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<span class=.date. itemprop=.dateCreated.>([^<]+)<")[0])
        year = self.cm.ph.getSearchGroups(released, r"((?:19|20)\d\d)")[0] or self._splitTitle(self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<h1[^>]*>([^<]+)<")[0]))[1]
        if released:
            info["released"] = released
        if year:
            info["year"] = year
        plot = self.cm.ph.getSearchGroups(data, r'(?s)class="wp-content[^"]*"[^>]*>(.*?)<div')[0]
        plot = self.cleanHtmlStr(re.sub(r"(?s)<h3[^>]*>.*?</h3>", "", plot))
        return info, plot, year

    def _seasonBlocks(self, data):
        # {season: [(episode, url, name, icon), ...]} in page order
        seasons = []
        for block in data.split("<div class='se-c'>")[1:]:
            season = self.cm.ph.getSearchGroups(block, r"<span class='se-t[^']*'>(\d+)<")[0]
            if not season:
                continue
            episodes = []
            for li in block.split("<li class='mark-")[1:]:
                url = self.cm.ph.getSearchGroups(li, r"href='([^']+)'")[0]
                num = self.cm.ph.getSearchGroups(li, r"class='numerando'>\s*\d+\s*-\s*(\d+)")[0]
                if not url or not num:
                    continue
                name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(li, r"href='[^']+'>([^<]*)</a>")[0])
                icon = self.cm.ph.getSearchGroups(li, r"data-src='([^']+)'")[0]
                episodes.append((num, url, name, icon))
            if episodes:
                seasons.append((season, episodes))
        return seasons

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("Filmaon.listItems |%s|" % cItem)
        url = self._fixUrl(cItem["url"])
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        pageUrlTpl = self._pageUrlTpl(url)
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for block in data.split('<article class="film24-card')[1:]:
            itemUrl = self.cm.ph.getSearchGroups(block, r'<h3><a href="([^"]+)"')[0] or self.cm.ph.getSearchGroups(block, r'href="([^"]+)"')[0]
            if not itemUrl or itemUrl in seen:
                continue
            seen.add(itemUrl)
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"<h3><a[^>]*>(.*?)</a>")[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0])
            title, titleYear = self._splitTitle(rawTitle)
            year = self.cm.ph.getSearchGroups(block, r'class="film24-year">(\d{4})<')[0] or titleYear
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'class="film24-quality">([^<]+)<')[0])
            genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'class="film24-card-meta"><span>[^<]*</span><span>([^<]+)<')[0])
            desc = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Quality"), quality), (_("Genre"), genre)) if value)
            icon = self.cm.ph.getSearchGroups(block, r'data-src="([^"]+)"')[0]
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "url": self.getFullUrl(itemUrl), "icon": self.getFullIconUrl(icon), "desc": desc, "s_title": title, "s_year": year})
            if "/seriale/" in itemUrl:
                params.update({"category": "list_seasons", "meta_type": "tv", "title": title})
                self.addDir(params)
            else:
                if normalize:
                    dispTitle = "%s (%s)" % (title, year) if year else title
                else:
                    dispTitle = rawTitle
                params.update({"category": "video", "meta_type": "movie", "title": dispTitle})
                self.addVideo(params)
        listBase = re.sub(r"/page/\d+/?$", "", url.split("?", 1)[0].rstrip("/"))
        pages = [int(n) for n in re.findall(r'href="%s/page/(\d+)/' % re.escape(listBase), data)]
        # the pager's "next" link; rel="next" (Yoast) is missing on search and release/<year>/ pages
        hasNext = 'class="next page-numbers"' in data or 'rel="next"' in data
        addPagingItems(self, cItem, page, hasNext, max(pages + [page]) if hasNext else page, pageUrlTpl)

    def listValue(self, cItem):
        printDBG("Filmaon.listValue")
        sts, data = self.getPage(self.getFullUrl("filma/"))
        if not sts:
            return
        menu = self.cm.ph.getDataBeetwenMarkers(data, cItem.get("s", ""), "</ul>", False)[1]
        for url, title in re.findall(r'href="([^"]+)">([^<]+)</a>', menu):
            params = stripPagerKeys(dict(cItem), ("s",))
            params.update({"good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)})
            self.addDir(params)

    def listYears(self, cItem):
        printDBG("Filmaon.listYears")
        # the years that have titles (WordPress REST API of the "dtyear" taxonomy - release/<year>/ of an empty year
        # answers 404, and the site has titles from before 1950); a local list when the API does not answer
        years = []
        sts, data = self.getPage(self.getFullUrl("wp-json/wp/v2/dtyear?per_page=100&hide_empty=true&orderby=name&order=desc&_fields=name,slug"))
        if sts:
            try:
                for term in json_loads(data):
                    name = (term.get("name") or "").strip()
                    if re.match(r"^(?:19|20)\d\d$", name) and term.get("slug"):
                        years.append((str(name), str(term["slug"])))
            except Exception:
                printExc()
        if years:
            years.sort(reverse=True)
        else:
            years = [(str(year), str(year)) for year in range(datetime.date.today().year, FIRST_YEAR - 1, -1)]
        for year, slug in years:
            params = stripPagerKeys(dict(cItem), ("s",))
            params.update({"good_for_fav": True, "category": "list_items", "title": year, "url": self.getFullUrl("release/%s/" % slug)})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("Filmaon.listSeasons |%s|" % cItem)
        url = self._fixUrl(cItem["url"]).split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        _info, plot, year = self._siteInfo(data)
        sTitle = cItem.get("s_title", "") or self._splitTitle(self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<h1[^>]*>([^<]+)<")[0]))[0] or cItem["title"]
        seasons = self._seasonBlocks(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        fields = {"s_title": sTitle, "s_year": year or cItem.get("s_year", ""), "meta_type": "tv", "desc": plot}
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category="list_episodes", season=seasons[0][0], url="%s#s%s" % (url, seasons[0][0]), **fields), seasons)
            return
        normalize = IsMediaNamingNormalized()
        for season, episodes in seasons:
            params = stripPagerKeys(dict(cItem))
            params.pop("se", None)
            params.update(fields)
            params.update({"good_for_fav": True, "category": "list_episodes", "season": season, "url": "%s#s%s" % (url, season),
                           "title": "%s - %s" % (sTitle, formatSxxExx(season) if normalize else "%s %s" % (_("Season"), season)),
                           "desc": "%s: %d\n%s" % (_("Episodes"), len(episodes), plot)})
            self.addDir(params)

    def listEpisodes(self, cItem, seasons=None):
        printDBG("Filmaon.listEpisodes |%s|" % cItem)
        url = self._fixUrl(cItem["url"]).split("#", 1)[0]
        season = self._season(cItem)
        if seasons is None:
            sts, data = self.getPage(url)
            if not sts:
                return
            seasons = self._seasonBlocks(data)
            if not cItem.get("s_title"):
                # old season rows ("Show - Season 2") have no show name field
                cItem = dict(cItem, s_title=self._splitTitle(self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<h1[^>]*>([^<]+)<")[0]))[0])
        episodes = dict(seasons).get(season, [])
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", "") or cItem["title"]
        normalize = IsMediaNamingNormalized()
        for episode, epUrl, name, icon in episodes:
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %s" % (sTitle, _("Season"), season, _("Episode"), episode)
                if name:
                    title += " - " + name
            params = stripPagerKeys(dict(cItem))
            params.pop("se", None)
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": epUrl, "season": season, "episode": episode,
                           "meta_type": "tv", "icon": self.getFullIconUrl(icon) or cItem.get("icon", ""), "desc": name})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Filmaon.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Filmaon.getLinksForVideo [%s]" % cItem)
        url = self._fixUrl(cItem["url"])
        sts, data = self.getPage(url)
        if not sts:
            return []
        plot = self._siteInfo(data)[1]
        urltab = []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=url, Origin=self.MAIN_URL.rstrip("/"), Accept="*/*")
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        for dtype, post, nume in re.findall(r"data-type='([^']+)'\s*data-post='(\d+)'\s*data-nume='(\d+)'", data):
            sts, answer = self.getPage(self.getFullUrl("wp-admin/admin-ajax.php"), dict(params), {"action": "doo_player_ajax", "post": post, "nume": nume, "type": dtype})
            if not sts:
                continue
            link = self.cm.ph.getSearchGroups(answer, r'"embed_url"\s*:\s*"([^"]+)"')[0].replace("\\/", "/")
            if link.startswith("//"):
                link = "https:" + link
            if not self.cm.isValidUrl(link) or "youtube." in link or link in [str(x["url"]) for x in urltab]:
                continue
            if self.up.checkHostSupport(link) != 1:
                # dead or unknown hosters of old posts (vivo.sx, albavide, broken i.ibb.co urls) only fail silently
                printDBG("Filmaon: unsupported link skipped [%s]" % link)
                continue
            urltab.append({"name": "%s [%s]" % (self.up.getHostName(link).capitalize(), nume), "url": strwithmeta(link, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), plot))

    def getVideoLinks(self, videoUrl):
        printDBG("Filmaon.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Filmaon.getArticleContent [%s]" % cItem)
        info, plot, year = {}, "", cItem.get("s_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, siteYear = self._siteInfo(data)
            year = year or siteYear
        mediaType = cItem.get("meta_type", "") or ("movie" if "/filma/" in cItem.get("url", "") else "tv")
        title = cItem.get("s_title", "") or self._splitTitle(cItem.get("title", ""))[0]
        meta = {}
        try:
            meta = getMeta(mediaType, info.get("original_title", "") or title, year, maxYearDiff=1)
        except Exception:
            printExc()
        for key, value in meta.get("info", {}).items():
            info.setdefault(key, value)
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_value" and "releases" in self.currItem.get("s", ""):
            # the "Year" row of the old version (favourite): its "releases scrolling" box is gone
            self.listYears(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
        elif category == "list_years":
            self.listYears(self.currItem)
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
        CHostBase.__init__(self, Filmaon(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("filmaon")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
