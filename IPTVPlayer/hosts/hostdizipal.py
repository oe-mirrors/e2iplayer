# -*- coding: utf-8 -*-
LAST_MODIFIED = "13.11.2026"
# 13.11.2026 - new host
#   dizipal: Turkish film / series / anime site (WordPress theme "filmvedizi"). Lists /filmler/, /diziler/,
#   /animeler/, genres, platforms, search (?s=), all paged as /page/<n>/. Series -> ?sezon=<n> -> episodes.
#   The site hops domains (dizipal<number>.com, the old one redirects to the new one): the redirect is followed
#   and a dead domain makes the host try the next numbers. Streams: the site's own player iframe
#   (embed-<id>.html), resolved by urlparser parserDIZIPAL (host_name "dizipal" - the player domain changes).
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.dizipal_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.dizipal_domain)]


def gettytul():
    return "https://dizipal3009.com/"


# how many following domain numbers are tried when the known one does not answer
DOMAIN_PROBES = 5
SITE_MARKER = "filmvedizi"
EPISODES_PER_PAGE = 100


def _episodeNums(url):
    # (season, episode) from /bolum/<show>-<s>-sezon-<e>-bolum-izle/ (anime: /anime-bolum/...), else None
    nums = re.search(r"-(\d+)-sezon-(\d+)-bolum", url)
    return nums.groups() if nums else None


class Dizipal(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "dizipal", "cookie": "dizipal.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.dizipal_domain.value.strip()
        self.userDomain = self.cm.isValidUrl(domain)
        self.MAIN_URL = domain.rstrip("/") + "/" if self.userDomain else gettytul()
        self.domainChecked = False
        self.MENU = [{"category": "dp_menu", "title": _("Movies"), "kind": "film"},
                     {"category": "dp_menu", "title": _("Series"), "kind": "dizi"},
                     {"category": "dp_menu", "title": _("Anime"), "kind": "anime"},
                     {"category": "dp_tags", "title": "Platformlar", "tag": "platform"}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("dizipal")
        self.wfInitFolderCache()

    ###################################################
    # pages / domain
    ###################################################
    def _checkDomain(self):
        # once per session: follow the redirect of the known domain, a dead one -> the next numbers
        if self.domainChecked or self.userDomain:
            return
        self.domainChecked = True
        candidates = [self.MAIN_URL]
        num = self.cm.ph.getSearchGroups(self.MAIN_URL, r"dizipal(\d+)\.")[0]
        if num:
            candidates += [re.sub(r"dizipal\d+\.", "dizipal%d." % (int(num) + i), self.MAIN_URL) for i in range(1, DOMAIN_PROBES + 1)]
        for url in candidates:
            params = dict(self.defaultParams, with_metadata=True)
            try:
                sts, data = self.cm.getPage(url, params)
            except Exception:
                printExc()
                continue
            if not sts or SITE_MARKER not in data:
                continue
            final = getattr(data, "meta", {}).get("url", "") or url
            base = self.cm.ph.getSearchGroups(final, r"^(https?://[^/]+)")[0]
            if base:
                self.MAIN_URL = base + "/"
            printDBG("Dizipal domain: %s" % self.MAIN_URL)
            return

    def _siteUrl(self, url):
        # favourites keep the domain of the day they were added - the site hops domains
        return re.sub(r"^https?://[^/]+/", self.MAIN_URL, self.getFullUrl(url))

    def getPage(self, baseUrl, addParams=None, post_data=None):
        self._checkDomain()
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._siteUrl(baseUrl), addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if not path:
                return ""
            category = cItem.get("category", "")
            if category in ("video", "episode"):
                return "video:%s" % path
            if category == "dp_series":
                return "series:%s" % path
            if category == "dp_season":
                return "season:%s|%s" % (path.split("?")[0], cItem.get("season", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # menus
    ###################################################
    def listMenu(self, cItem):
        kind = cItem["kind"]
        listPath = {"film": "filmler/", "dizi": "diziler/", "anime": "animeler/"}[kind]
        genres = {"film": _("Genres"), "dizi": _("Series genres"), "anime": _("Anime genres")}[kind]
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": _("Latest added"), "url": self.MAIN_URL + listPath})
        self.addDir({"name": "category", "good_for_fav": True, "category": "dp_tags", "title": genres, "tag": {"film": "kategori", "dizi": "dizi-kategori", "anime": "anime-kategori"}[kind]})

    def listTags(self, cItem):
        # genres / platforms: the links of the site menu
        printDBG("Dizipal.listTags |%s|" % cItem)
        sts, data = self.getPage(self.MAIN_URL + ("filmler/" if cItem["tag"] == "kategori" else ""))
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'(?s)<a[^>]+href="([^"]*/%s/[^"/]+/?)"[^>]*>(.*?)</a>' % re.escape(cItem["tag"]), data):
            url = self._siteUrl(url if url.endswith("/") else url + "/")
            title = self.cleanHtmlStr(title)
            if not title:
                title = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
            if url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": url})

    ###################################################
    # lists
    ###################################################
    def _addTitle(self, url, title, icon):
        url = self._siteUrl(url)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "meta_title": title}
        nums = _episodeNums(url) if re.search(r"/(?:anime-)?bolum/", url) else None
        if nums:
            # an episode card ("<show> 1. Sezon 2. Bölüm"): the show's title, season / episode from the url
            season, epNum = nums
            show = re.sub(r"\s*\d+\.\s*Sezon\s+\d+\.\s*Bölüm.*$", "", title).strip() or title
            if IsMediaNamingNormalized():
                title = "%s - %s" % (show, formatSxxExx(season, epNum))
            # the show's page: /bolum/<slug>-1-sezon-2-bolum-izle/ -> /dizi/<slug>/ (anime-bolum -> /anime/<slug>/)
            slug = self.cm.ph.getSearchGroups(url, r"/(anime-)?bolum/(.+?)-\d+-sezon-\d+-bolum", 2)
            seriesUrl = "%s%s/%s/" % (self.MAIN_URL, "anime" if slug[0] else "dizi", slug[1]) if slug[1] else ""
            params.update({"category": "episode", "title": title, "s_title": show, "meta_title": show, "meta_type": "tv", "season": season, "ep_num": epNum,
                           "meta_season": season, "meta_episode": epNum, "series_url": seriesUrl})
            self.addVideo(params)
        elif re.search(r"/(?:dizi|anime)/", url):
            params.update({"category": "dp_series", "title": title, "s_title": title, "meta_type": "tv"})
            self.addDir(params)
        else:
            params.update({"category": "video", "title": title, "meta_type": "movie"})
            self.addVideo(params)

    def _addCards(self, data):
        count = 0
        for url, title, inner in re.findall(r'(?s)<div class="post-item">\s*<a href="([^"]+)"[^>]*?title="([^"]*)"[^>]*>(.*?)</a>', data):
            title = self.cleanHtmlStr(title)
            if not title or not url:
                continue
            icon = self.cm.ph.getSearchGroups(inner, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(inner, r'\ssrc="([^"]+)"')[0]
            if "no-thumbnail" in icon:
                icon = ""
            self._addTitle(url, title, icon)
            count += 1
        return count

    def _lastPage(self, data):
        pages = [int(x) for x in re.findall(r'href="[^"]*/page/(\d+)/', data)]
        return max(pages) if pages else 0

    def listItems(self, cItem):
        printDBG("Dizipal.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        # list / search urls: /<list>/page/<n>/ and /page/<n>/?s=<pattern>
        path, _sep, query = self._siteUrl(cItem["url"]).partition("?")
        url = path + ("page/%d/" % page if page > 1 else "") + ("?" + query if query else "")
        sts, data = self.getPage(url)
        if not sts:
            return
        lastPage = max(self._lastPage(data), page)
        count = self._addCards(data)
        addPagingItems(self, dict(cItem), page, bool(count) and page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Dizipal.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        self.listItems(dict(cItem, category="list_items", url=self.MAIN_URL + "?s=" + urllib_quote_plus(searchPattern.strip())))

    def listSeasons(self, cItem):
        printDBG("Dizipal.listSeasons |%s|" % cItem)
        seriesUrl = self._siteUrl(cItem["url"]).split("?")[0]
        sts, data = self.getPage(seriesUrl)
        if not sts:
            return
        seasons = []
        for num, label in re.findall(r'href="[^"]*\?sezon=(\d+)"[^>]*>\s*([^<]+)', data):
            if num not in [s[0] for s in seasons]:
                seasons.append((num, self.cleanHtmlStr(label)))
        sTitle = cItem.get("s_title", cItem["title"])
        desc = self._description(data)
        fields = {"s_title": sTitle, "series_url": seriesUrl, "meta_type": "tv", "meta_title": cItem.get("meta_title", sTitle)}
        if len(seasons) <= 1:
            num = seasons[0][0] if seasons else "1"
            self.listEpisodes(dict(cItem, category="dp_season", season=num, **fields), data)
            return
        for num, label in seasons:
            title = "%s - %s" % (sTitle, formatSxxExx(num) if IsMediaNamingNormalized() else label)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "dp_season", "title": title, "season": num, "url": "%s?sezon=%s" % (seriesUrl, num), "desc": desc})
            params.update(fields)
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("Dizipal.listEpisodes |%s|" % cItem)
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        season = str(cItem.get("season", ""))
        sTitle = cItem.get("s_title", cItem["title"])
        normalize = IsMediaNamingNormalized()
        episodes = []
        seen = set()
        for item in data.split('<div class="episode-item">')[1:]:
            # series: /bolum/<slug>/, anime: /anime-bolum/<slug>/
            url = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+/(?:anime-)?bolum/[^"]+)"')[0]
            nums = _episodeNums(url)
            if not nums or url in seen or (season and nums[0] != season):
                continue
            seen.add(url)
            episodes.append((url, nums, item))
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        lastPage = (len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
        for url, (epSeason, epNum), item in episodes[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]:
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h4[^>]*>\s*<a[^>]*>(.*?)</a>')[0])
            aired = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<span[^>]*>(.*?)</span>')[0])
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+\ssrc="([^"]+)"')[0]
            if "no-thumbnail" in icon:
                icon = ""
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(epSeason, epNum))
            else:
                title = "%s - %s. Sezon %s. Bölüm" % (sTitle, epSeason, epNum)
            if name and not re.match(r"^\d+\.\s*Bölüm$", name):
                title = "%s - %s" % (title, name)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "episode", "title": title, "url": self._siteUrl(url), "season": epSeason, "ep_num": epNum,
                           "meta_season": epSeason, "meta_episode": epNum, "ep_name": name, "icon": icon or cItem.get("icon", ""),
                           "desc": " | ".join(x for x in (name, aired) if x)})
            self.addVideo(params)
        if lastPage > 1:
            # the season's own url (?sezon=<n>) - a single-season show keeps the show url
            addPagingItems(self, dict(cItem, category="dp_season"), page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Dizipal.getLinksForVideo [%s]" % cItem)
        pageUrl = self._siteUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        urltab = []
        player = data.split('class="video-player-area"', 1)[-1] if 'class="video-player-area"' in data else data
        for url in re.findall(r'<iframe[^>]+src="([^"]+)"', player):
            url = self.getFullUrl(url.strip())
            if not self.cm.isValidUrl(url) or "youtube" in url or url in [u["url"] for u in urltab]:
                continue
            name = "Dizipal" if "/embed-" in url else self.up.getHostName(url)
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": pageUrl}), "need_resolve": 1})
        if not urltab:
            # the trailer alone is no stream of the title: say so instead of offering only the trailer
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        trailer = self.cm.ph.getSearchGroups(data, r'(https?://www\.youtube\.com/embed/[\w-]+)')[0]
        if trailer:
            urltab.append({"name": "%s (YouTube)" % _("Trailer"), "url": trailer.replace("/embed/", "/watch?v="), "need_resolve": 1})
        if cItem.get("category") == "episode":
            metaQuery = sidecarMetaQuery("tv", cItem.get("meta_title", "") or cItem.get("s_title", ""), skip=(),
                                         season=cItem.get("meta_season", ""), episode=cItem.get("meta_episode", ""))
        else:
            metaQuery = sidecarMetaQuery("movie", cItem.get("meta_title", ""), self._field(data, "Yapım Yılı"), "", skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self._description(data) or cItem.get("desc", ""), metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("Dizipal.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        meta = {"Referer": strwithmeta(videoUrl).meta.get("Referer", "") or self.MAIN_URL}
        if "/embed-" in videoUrl:
            # the site's own player (urlparser parserDIZIPAL): its domain changes, the name picks the parser
            meta["host_name"] = "dizipal"
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(videoUrl, meta)), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _field(self, data, label):
        # "Tür", "Yapım Yılı", "Ülke", "Yönetmen", "Oyuncular", "Süre", "IMDB Puanı" boxes of a title page
        block = self.cm.ph.getSearchGroups(data, r'(?s)<span[^>]*>\s*%s\s*</span>(.*?)</div>\s*</div>' % re.escape(label))[0]
        return self.cleanHtmlStr(block)

    def _description(self, data):
        text = self.cm.ph.getSearchGroups(data, r'(?s)<p class="summary-text[^"]*">(.*?)</p>')[0]
        text = text or self.cm.ph.getSearchGroups(data, r'(?s)<p class="text-sm text-white/\[70%\] font-normal">(.*?)</p>')[0]
        text = text or self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]*)"')[0]
        return self.cleanHtmlStr(text)

    def getArticleContent(self, cItem):
        printDBG("Dizipal.getArticleContent [%s]" % cItem)
        category = cItem.get("category", "")
        mediaType = "movie" if category == "video" else "tv"
        info = {}
        desc = ""
        year = ""
        icon = cItem.get("icon", "")
        # seasons and episodes: the show's page (an episode page has neither description nor details)
        url = cItem.get("series_url", "") if category in ("dp_season", "episode") else ""
        sts, data = self.getPage(url or cItem.get("url", ""))
        if sts:
            desc = self._description(data)
            for key, label in (("genres", "Tür"), ("country", "Ülke"), ("director", "Yönetmen"), ("actors", "Oyuncular")):
                value = self._field(data, label)
                if value:
                    info[key] = value
            # "2s 45dk" = 2 hours (saat) 45 minutes (dakika)
            duration = self._field(data, "Süre")
            hours = self.cm.ph.getSearchGroups(duration, r"(\d+)\s*s\b")[0]
            minutes = self.cm.ph.getSearchGroups(duration, r"(\d+)\s*dk")[0]
            if hours or minutes:
                info["duration"] = "%d min" % (int(hours or 0) * 60 + int(minutes or 0))
            year = self._field(data, "Yapım Yılı")
            rating = self.cm.ph.getSearchGroups(self._field(data, "IMDB Puanı"), r"(\d+(?:\.\d)?)")[0]
            if rating and rating not in ("0", "0.0"):
                info["rating"] = "%s/10" % rating
            icon = icon or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        meta = {}
        try:
            title = cItem.get("meta_title", "") or cItem.get("s_title", "")
            if title:
                meta = getMeta(mediaType, title, year) or {}
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in info:
                info.pop(siteKey, None)
        if year and "year" not in info:
            info["year"] = year
        plot = meta.get("plot", "")
        text = desc or cItem.get("desc", "")
        if plot and text and plot != text:
            text = "%s[/br][/br]%s" % (text, plot)
        else:
            text = text or plot
        icon = icon or meta.get("poster", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

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
        elif category == "dp_menu":
            self.listMenu(self.currItem)
        elif category == "dp_tags":
            self.listTags(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "dp_series":
            self.listSeasons(self.currItem)
        elif category == "dp_season":
            self.listEpisodes(self.currItem)
        elif category == "search":
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
        CHostBase.__init__(self, Dizipal(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("dizipal")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("video", "episode", "dp_series", "dp_season")
