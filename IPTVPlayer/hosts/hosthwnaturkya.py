# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - brought to the current host standard
#   (HwnaTurkya, Turkish series/movies with Arabic subtitles/dubbing - originally by Mohamed Elsafty)
#   - no sleeping 3x retry wrapper, no start-up domain probe; the AJAX header is a copy (the
#     X-Requested-With header no longer leaks into every request), the caller's params are not mutated
#   - movies are VIDEO rows keyed on their page; the latest-episode cards of a category become one
#     show folder per series -> seasons (from the season carousel) -> episodes (ascending)
#   - the servers of the watch page are fetched in getLinksForVideo (POST /ajax/getPlayer), every
#     iframe goes to urlparser (need_resolve=1); hosters urlparser cannot resolve and dead domains
#     are not offered (message with their names when nothing else is left)
#   - paging (First page / Jump / Next page with the last page), search + history, watched flag,
#     favourites, sidecar, INFO (site story/fields + moviemeta by the IMDb id of the page),
#     name normalisation ("Title", "Show - SxxExx"), no colour codes in titles
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Components.config import ConfigText, config, getConfigListEntry

config.plugins.iptvplayer.hwnaturkya_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.hwnaturkya_alt_domain))
    return optionList


def gettytul():
    return "HwnaTurkya"


DEFAULT_DOMAIN = "https://www.hwnaturkya.com/"
# server domains the site still links that urlparser knows but that are gone (checked 04.10.2026)
DEAD_HOSTS = ("mivalyo.com", "listeamed.net")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالث", 3), ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8),
    ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"\s*(?:الموسم|الجزء)\s*(\d+|%s)(?=\s|$)" % "|".join(o[0] for o in SEASON_ORDINALS))
JUNK_RE = re.compile(r"(?:^|\s)(?:فيلم|مسلسل|مترجم|مترجمة|للعربية|اون لاين|أون لاين|كامل|كاملة|بجودة|HD)(?=\s|$)")
INFO_FIELDS = (("سنة", "year"), ("الممثلين", "actors"), ("النوع", "genres"), ("اللغة", "language"), ("الجودة", "quality"),
               ("الوقت", "duration"), ("القسم", "category"), ("المواسم", "seasons"))


class HwnaTurkya(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "hwnaturkya", "cookie": "hwnaturkya.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "https://www.hwnaturkya.com/assets/themes/3arbserv/images/logo.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("hwnaturkya")
        self.wfInitFolderCache()

    def selectDomain(self):
        domain = config.plugins.iptvplayer.hwnaturkya_alt_domain.value.strip()
        if not self.cm.isValidUrl(domain):
            domain = DEFAULT_DOMAIN
        if not domain.endswith("/"):
            domain += "/"
        self.MAIN_URL = domain

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        params = dict(self.defaultParams if addParams is None else addParams)
        params["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), params, post_data)

    def _canonUrl(self, url):
        # the site links raw-Arabic paths - one ASCII form for requests, favourites and the downloaded marker
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        if self.MAIN_URL is None:
            self.selectDomain()  # INFO / links of a favourite before the first list
        if url.startswith("//"):
            url = "https:" + url
        url = self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    @staticmethod
    def _path(url):
        # stable key part: the decoded path of a page, whatever domain / encoding
        try:
            return urllib_unquote(re.sub(r"^https?://[^/]+", "", url or "")).strip("/")
        except Exception:
            return url or ""

    @staticmethod
    def _clean(text):
        text = JUNK_RE.sub(" ", text or "")
        return re.sub(r"\s+", " ", text).strip(" -:|")

    def _showName(self, title):
        # "مسلسل الخليفة الحلقة 37 السابعة والثلاثون مترجمة" -> "الخليفة"
        title = re.split(r"\s+الحلقة\s*", title or "", 1)[0]
        return SEASON_RE.split(self._clean(title))[0].strip()

    @staticmethod
    def _seasonNum(title):
        m = SEASON_RE.search(title or "")
        if not m:
            return 1
        val = m.group(1)
        return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 1)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category == "hw_series":
                return "show:%s" % cItem["s_title"] if cItem.get("s_title") else ""
            if category in ("hw_season", "hw_video"):
                path = self._path(cItem.get("url", ""))
                return ("%s:%s" % ("season" if category == "hw_season" else "video", path)) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        for kind, audio, path in ((_("Turkish Movies"), _("With subtitles"), "category/افلام-تركية-مترجمة.html"),
                                  (_("Turkish Movies"), _("Dubbed"), "category/افلام-تركية-مدبلجة.html"),
                                  (_("Turkish Series"), _("With subtitles"), "category/مسلسلات-تركية-مترجمة.html"),
                                  (_("Turkish Series"), _("Dubbed"), "category/مسلسلات-تركية-مدبلجة.html")):
            self.addDir({"name": "category", "category": "hw_list", "good_for_fav": True, "title": "%s - %s" % (kind, audio), "url": self._canonUrl(path)})
        self.listsTab(self.searchItems(), cItem)

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        base = re.sub(r"/page\d+/?$", "", cItem["url"]).rstrip("/")
        tpl = base + "/page{page}"
        sts, data = self.getPage(tpl.format(page=page) if page > 1 else base)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seenShows = set()
        count = 0
        for item in re.findall(r'<article class="post">(.*?)</article>', data, re.S):
            m = re.search(r'<a href="([^"]+)" title="([^"]*)"', item)
            if not m:
                continue
            url = self._canonUrl(m.group(1))
            title = self.cleanHtmlStr(m.group(2))
            icon = self._canonUrl(self.cm.ph.getSearchGroups(item, r'data-original="([^"]+)"')[0])
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)imdb-rating">(.*?)</div>')[0])
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="quality">(.*?)</div>')[0])
            epInfo = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="numberEpisodes">(.*?)</div>')[0])
            seasonLabel = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="seasonNum">(.*?)</div>')[0])
            desc = " | ".join([x for x in (seasonLabel, epInfo, quality, ("IMDb %s" % rating) if rating else "") if x])
            count += 1
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc}
            if "/movies/" in url:
                clean = self._clean(title)
                params.update({"category": "hw_video", "title": clean if normalize else title, "meta_type": "movie", "meta_title": clean})
                self.addVideo(params)
            elif "/episodes/" in url or "/seasons/" in url or "/series/" in url:
                # latest-episode / season cards -> one show folder per series
                show = self._showName(seasonLabel or title)
                if not show or show in seenShows:
                    continue
                seenShows.add(show)
                params.update({"category": "hw_series", "title": show, "s_title": show, "meta_type": "tv", "meta_title": show})
                self.addDir(params)
        lastPage = self.cm.ph.getSearchGroups(data, r'data-ci-pagination-page="(\d+)">الاخيرة<')[0]
        lastPage = int(lastPage) if lastPage.isdigit() else 0
        hasNext = count > 0 and ('rel="next"' in data)
        addPagingItems(self, dict(cItem, url=base), page, hasNext, lastPage if lastPage >= page else 0, tpl)

    def _seasons(self, data):
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="getSeasonsBySeries"', '<div class="container">', False)[1]
        seasons = []
        for label, url in re.findall(r'<div class="seasonNum">([^<]*)</div>\s*<a href="([^"]+)"', block):
            url = self._canonUrl(url)
            if url not in [s[1] for s in seasons]:
                seasons.append((self.cleanHtmlStr(label), url))
        seasons.sort(key=lambda s: self._seasonNum(s[0]))
        return seasons

    def listSeries(self, cItem):
        # show folder (an episode / seasons page): seasons, or the episodes when there is only one
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._seasons(data)
        show = cItem.get("s_title", "")
        normalize = IsMediaNamingNormalized()
        if len(seasons) > 1:
            used = {}
            for label, url in seasons:
                season = self._seasonNum(label)
                title = "%s - %s" % (show, formatSxxExx(season)) if normalize else label
                used[title] = used.get(title, 0) + 1
                if used[title] > 1:
                    title = "%s (%d)" % (title, used[title])  # the site splits some seasons into parts
                self.addDir(dict(cItem, category="hw_season", good_for_fav=True, url=url, s_season=season, title=title))
            return
        if seasons and "/series/" not in cItem["url"]:
            sts, data = self.getPage(seasons[0][1])
            if not sts:
                return
        self._listEpisodes(dict(cItem, s_season=self._seasonNum(seasons[0][0]) if seasons else 1), data)

    def listSeason(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if sts:
            self._listEpisodes(cItem, data)

    def _listEpisodes(self, cItem, data):
        show = cItem.get("s_title", "")
        season = cItem.get("s_season", 1)
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h3 class="story">(.*?)</h3>')[0])
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="list-episodes">', "</ul>", False)[1]
        normalize = IsMediaNamingNormalized()
        episodes = []
        seen = set()
        for url, title, num in re.findall(r'<a[^>]+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?class="numEp">\s*(\d+)', block, re.S):
            url = self._canonUrl(url)
            if url in seen:
                continue
            seen.add(url)
            episodes.append((int(num), url, self.cleanHtmlStr(title)))
        episodes.sort(key=lambda e: e[0])
        for num, url, title in episodes:
            self.addVideo({"name": "category", "category": "hw_video", "good_for_fav": True, "url": url, "icon": cItem.get("icon", ""), "desc": story,
                           "title": "%s - %s" % (show, formatSxxExx(season, num)) if normalize and show else (title or _("Episode %d") % num),
                           "s_title": show, "s_season": season, "s_episode": num, "meta_type": "tv", "meta_title": show})
        if not episodes:
            self.addMarker({"title": _("No episodes available yet."), "desc": story})

    def listSearchResult(self, cItem, searchPattern, searchType):
        cItem = dict(cItem)
        cItem.update({"category": "hw_list", "url": self._canonUrl("search/%s.html" % searchPattern.strip())})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("HwnaTurkya.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = self._canonUrl(cItem.get("url", ""))
        watchUrl = url.replace("/movies/", "/watch_movies/").replace("/episodes/", "/watch_episodes/")
        sts, data = self.getPage(watchUrl)
        if not sts:
            return []
        postId = self.cm.ph.getSearchGroups(data, r"postID\s*=\s*['\"]([^'\"]+)['\"]")[0]
        if not postId:
            return []
        params = dict(self.defaultParams)
        params["header"] = dict(self.AJAX_HEADER, Referer=watchUrl)
        links = []
        skipped = []
        for server in re.findall(r"getPlayer\('([^']+)'\)", data):
            sts, pdata = self.getPage(self.getFullUrl("ajax/getPlayer"), params, {"server": server, "postID": postId, "Ajax": "1"})
            if not sts:
                continue
            src = self._canonUrl(self.cm.ph.getSearchGroups(pdata, r"src=['\"]([^'\"]+)['\"]", ignoreCase=True)[0])
            if not self.cm.isValidUrl(src) or src.rstrip("/") == self.MAIN_URL.rstrip("/") or src in [x["url"] for x in links]:
                continue
            hostName = self.up.getHostName(src, True)
            domain = self.up.getHostName(src).split(":", 1)[0]
            if self.up.checkHostSupport(src) != 1 or any(domain == d or domain.endswith("." + d) for d in DEAD_HOSTS):
                # no urlparser resolver or a dead domain (parked, NXDOMAIN, closed) - offering it only fails
                printDBG("HwnaTurkya: skip hoster [%s]" % src)
                if hostName not in skipped:
                    skipped.append(hostName)
                continue
            links.append({"name": "%s - %s" % (server, hostName), "url": src, "need_resolve": 1})
        if not links and skipped:
            SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(skipped))
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h3 class="story">(.*?)</h3>')[0])
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("HwnaTurkya.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("HwnaTurkya.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info, imdbId = "", "", {}, ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h3 class="story">(.*?)</h3>')[0])
            poster = self.cm.ph.getSearchGroups(data, r'(?s)class="postThumbnail">\s*<img[^>]+src="([^"]+)"')[0]
            imdbId = self.cm.ph.getSearchGroups(data, r'imdb\.com/title/(tt\d+)')[0]
            rating = self.cm.ph.getSearchGroups(data, r'class="imdb"[^>]*>.*?IMDB\s*([0-9.]+)')[0]
            if rating:
                info["imdb_rating"] = rating
            for section in re.findall(r'<ul[^>]*class="single-info[^"]*"[^>]*>(.*?)</ul>', data, re.S):
                label = self.cleanHtmlStr(section.split(":", 1)[0])
                values = [self.cleanHtmlStr(x) for x in re.findall(r"<a[^>]*>(.*?)</a>", section, re.S)]
                values = [x for x in values if x and x != ","]
                for word, key in INFO_FIELDS:
                    if word in label and values:
                        info[key] = ", ".join(values[:8])
        meta = {}
        mediaType = cItem.get("meta_type", "")
        try:
            if imdbId and mediaType:
                meta = getMetaByImdbId(mediaType, imdbId)
            if not meta and mediaType and cItem.get("meta_title"):
                meta = getMeta(mediaType, cItem["meta_title"], info.get("year", "")[:4])
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or (self._canonUrl(poster) if poster else "") or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("HwnaTurkya.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "hw_list":
            self.listItems(self.currItem)
        elif category == "hw_series":
            self.listSeries(self.currItem)
        elif category == "hw_season":
            self.listSeason(self.currItem)
        elif category in ("search", "search_next_page"):
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
        CHostBase.__init__(self, HwnaTurkya(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("hwnaturkya")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("hw_video", "hw_series", "hw_season")
