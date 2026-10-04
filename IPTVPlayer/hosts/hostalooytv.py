# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - revived for the current alooytvNN domain (AlooyTV host created by Dr HYTHAM MAHMOUD)
#   - the old domains redirect to the link hub fitnur.com/alooytv: the site domain is read from the hub
#     (never the hub itself), an own "Alternative domain" first; config keys renamed to alooytv_*
#   - categories read live from the site menu; "Latest series", search; First Page / Jump / Next page
#     (n/last) for the offset pagination (/genre/x/50.html, ?per_page=24)
#   - a title page is one season: series -> episode list (VIDEO rows on the stable ?key= url),
#     movies / plays are VIDEO rows on their page url
#   - links: the page's own direct MP4 (<video><source>, plus the download_video mirror when it is
#     another server), Referer of the site needed (without it the CDN redirects to a promo clip)
#   - watched flag, downloaded flag, favourites (urls re-based on the current domain), name
#     normalisation ("Show - SxxExx"), sidecar, INFO via moviemeta + the site's story/fields/poster
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

config.plugins.iptvplayer.alooytv_proxy = ConfigSelection(default="None", choices=[("None", _("None")), ("proxy_1", _("Alternative proxy server (1)")), ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.alooytv_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.alooytv_proxy))
    if config.plugins.iptvplayer.alooytv_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.alooytv_alt_domain))
    return optionList


def gettytul():
    return "AlooyTV"


# link hub the old domains redirect to - lists the current site domain, is never the site itself
HUB_URL = "https://fitnur.com/alooytv"
DEFAULT_DOMAIN = "https://eh.alooytv16.xyz/"
SITE_DOMAIN_RE = re.compile(r"https?://(?:[a-z0-9-]+\.)*alooytv\d+\.[a-z]+", re.I)

# Arabic ordinals of the season headings ("الموسم الثاني")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1),
    ("الثانية", 2), ("الثاني", 2), ("الثانى", 2), ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4),
    ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6), ("السادس", 6), ("السابعة", 7), ("السابع", 7),
    ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_HEAD_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
# season suffixes of the title ("Stranger Things S04", "آل التنين ج3", "Avatar-The-Last-Airbender-2")
TITLE_SEASON_RE = re.compile(r"(?:\s+(?:S|s)\d{1,2}|\s*(?:ج|الجزء|الموسم)\s*\d{1,2})$")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجم|اون لاين|أون لاين|مشاهدة|مسلسل|فيلم|كامل|كاملة)(?=\s|$)")
MOVIE_GENRES = ("movies", "masrahiyat")


class AlooyTV(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "alooytv", "cookie": "alooytv.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/alooytv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept-Language": "ar,en-US;q=0.9,en;q=0.8"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("alooytv")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        proxy = config.plugins.iptvplayer.alooytv_proxy.value
        try:
            if proxy == "proxy_1":
                return config.plugins.iptvplayer.alternativeproxy1.value
            if proxy == "proxy_2":
                return config.plugins.iptvplayer.alternativeproxy2.value
        except Exception:
            printExc()
        return None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _isSite(self, url, data):
        return bool(SITE_DOMAIN_RE.match(url or "")) and ("movie-container" in data or "tv-series.html" in data)

    def selectDomain(self):
        if AlooyTV.DOMAIN_CACHE:
            self.MAIN_URL = AlooyTV.DOMAIN_CACHE
            return
        candidates = []
        altDomain = config.plugins.iptvplayer.alooytv_alt_domain.value.strip()
        if self.cm.isValidUrl(altDomain):
            candidates.append(altDomain.rstrip("/") + "/")
        candidates.append(DEFAULT_DOMAIN)
        for domain in candidates:
            sts, data = self.getPage(domain)
            finalUrl = self.cm.meta.get("url", domain) if sts else ""
            if sts and self._isSite(finalUrl, data):
                self.MAIN_URL = self.cm.getBaseUrl(finalUrl)
                break
            printDBG("AlooyTV.selectDomain: %s -> %s is not the site" % (domain, finalUrl))
        if not self.MAIN_URL:
            # the hub lists the current domain - count the alooytvNN links, the most frequent one wins
            sts, data = self.getPage(HUB_URL)
            found = SITE_DOMAIN_RE.findall(data) if sts else []
            if found:
                best = max(set(found), key=found.count)
                self.MAIN_URL = best.rstrip("/") + "/"
                printDBG("AlooyTV.selectDomain: domain from the hub %s" % self.MAIN_URL)
        if not self.MAIN_URL:
            self.MAIN_URL = DEFAULT_DOMAIN
        AlooyTV.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / old lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()  # INFO / links of a favourite before any list was opened
        url = (url or "").replace("&amp;", "&").strip()
        if url.startswith("//"):
            url = "https:" + url
        m = re.match(r"https?://[^/]+/(.*)$", url)
        if m and SITE_DOMAIN_RE.match(url):
            return self.MAIN_URL + m.group(1)
        return self.getFullUrl(url)

    @staticmethod
    def _pathKey(url):
        # domain-free identity of a title / episode page: "watch/<slug>.html[?key=..]"
        m = re.search(r"/(watch/[^?#]+)(?:\?(?:[^#]*&)?key=([^&#]+))?", url or "")
        if not m:
            return ""
        return m.group(1) + ("?key=" + m.group(2) if m.group(2) else "")

    @staticmethod
    def _clean(title):
        title = JUNK_RE.sub(" ", title or "")
        return re.sub(r"\s+", " ", title).strip(" -:|")

    def _showTitle(self, title):
        return TITLE_SEASON_RE.sub("", self._clean(title)).strip(" -:|")

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip())
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category in ("al_movie", "al_episode"):
                key = self._pathKey(cItem.get("url", ""))
                return "video:%s" % key if key else ""
            if category == "al_series":
                key = self._pathKey(cItem.get("url", ""))
                return "season:%s" % key if key else ""
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "") in ("al_movie", "al_episode", "al_series"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "list_items", "title": "%s - %s" % (_("Series"), _("Latest")), "url": self.getFullUrl("tv-series.html"), "good_for_fav": True},
            {"category": "al_genres", "title": _("Categories")},
        ] + self.searchItems()
        self.listsTab(tab, cItem)

    def listGenres(self, cItem):
        sts, data = self.getPage(self.getFullUrl("tv-series.html"))
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'<a[^>]+href="([^"]+/genre/[^"]+\.html)"[^>]*>([^<]+)<', data):
            title = self.cleanHtmlStr(title).replace("★", "").strip()
            url = self._rebase(url)
            if not title or url in seen:
                continue
            seen.add(url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url})
            self.addDir(params)

    def _pagination(self, data):
        # (per page, last page, url template with {offset}) of the CodeIgniter pager
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class ="pagination">', "</ul>", False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination', "</ul>", False)[1]
        per, last, tpl = 0, 0, ""
        for href, num in re.findall(r'href="([^"]+)"[^>]*data-ci-pagination-page="(\d+)"', block):
            href = href.replace("&amp;", "&")
            num = int(num)
            last = max(last, num)
            m = re.search(r"(?:/(\d+)\.html|[?&]per_page=(\d+))", href)
            if m and num > 1:
                offset = int(m.group(1) or m.group(2))
                if not per and offset:
                    per = offset // (num - 1)
                if not tpl:
                    tpl = href[:m.start()] + m.group(0).replace(str(offset), "{offset}")
        return per, last, tpl

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        url = self._rebase(cItem.get("al_base") or cItem.get("url", ""))
        if page > 1 and cItem.get("al_tpl") and cItem.get("al_per"):
            url = self._rebase(cItem["al_tpl"].replace("{offset}", str((page - 1) * int(cItem["al_per"]))))
        printDBG("AlooyTV.listItems page[%d] [%s]" % (page, url))
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        movieList = any(word in url for word in MOVIE_GENRES)
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="movie-container">', '<div class="pagination-container', False)[1] or data
        seen = set()
        for item in block.split('<div class="latest-movie-img-container">')[1:]:
            m = re.search(r'(?s)class="movie-title">\s*<h3>\s*<a href="([^"]+)">(.*?)</a>', item)
            if not m:
                continue
            itemUrl = self._rebase(m.group(1))
            rawTitle = self.cleanHtmlStr(m.group(2))
            if not rawTitle or itemUrl in seen:
                continue
            seen.add(itemUrl)
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<span class="label label-primary">(.*?)</span>')[0])
            params = {"name": "category", "good_for_fav": True, "url": itemUrl, "icon": self.getFullIconUrl(icon), "desc": label}
            if "الحلقات" in label and not movieList:
                if re.match(r"0\s", label):
                    continue  # announced, no episode online yet
                show = self._showTitle(rawTitle)
                params.update({"category": "al_series", "title": self._clean(rawTitle) if normalize else rawTitle, "s_title": show,
                               "meta_type": "tv", "meta_title": show, "meta_year": ""})
                self.addDir(params)
            else:
                title = self._clean(rawTitle) if normalize else rawTitle
                params.update({"category": "al_movie", "title": title, "meta_type": "movie", "meta_title": self._clean(rawTitle), "meta_year": ""})
                self.addVideo(params)

        if not seen:
            return
        per, last, tpl = self._pagination(data)
        hasNext = bool(re.search(r'rel="next"', self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination', "</ul>", False)[1]))
        cItem = dict(cItem)
        if cItem.get("category") != "list_items":
            cItem.update({"category": "list_items", "search_item": False})
        if not cItem.get("al_base"):
            cItem["al_base"] = url
        # the last page links only the earlier ones: keep what page 1 told
        per = cItem.get("al_per") or per
        tpl = cItem.get("al_tpl") or tpl
        last = max(last, page) if last else 0
        if per and tpl:
            cItem.update({"al_tpl": tpl, "al_per": per})
            # the real url is built from the page number in listItems; the fragment only makes the rows distinct
            addPagingItems(self, cItem, page, hasNext, last, cItem["al_base"].split("#")[0] + "#page={page}")
        else:
            addPagingItems(self, cItem, page, hasNext, last)

    def listEpisodes(self, cItem):
        url = self._rebase(cItem.get("url", ""))
        printDBG("AlooyTV.listEpisodes [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="season"', "</div>\n</div>", False)[1] or data
        head = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'class="movie-heading[^"]*"[^>]*>\s*<span>([^<]*)</span>')[0])
        m = SEASON_HEAD_RE.search(head)
        season = (int(m.group(1)) if m.group(1).isdigit() else dict(SEASON_ORDINALS).get(m.group(1), 1)) if m else 1
        show = cItem.get("s_title") or self._showTitle(cItem.get("title", ""))
        seen = set()
        for href, label in re.findall(r'<a href="([^"]+)" class="btn btn-inline btn-ep[^"]*"[^>]*>([^<]*)<', block):
            epUrl = self._rebase(href)
            if epUrl in seen:
                continue
            seen.add(epUrl)
            label = self.cleanHtmlStr(label)
            epNum = self.cm.ph.getSearchGroups(label, r"(\d+)")[0]
            if normalize and epNum:
                title = "%s - %s" % (show, formatSxxExx(season, epNum))
            else:
                title = "%s - %s" % (cItem.get("title", ""), label)
            self.addVideo({"name": "category", "good_for_fav": True, "category": "al_episode", "title": title, "url": epUrl,
                           "icon": cItem.get("icon", ""), "desc": cItem.get("desc", ""), "s_title": show, "s_season": season,
                           "s_episode": epNum, "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": ""})

    def listSearchResult(self, cItem, searchPattern, searchType):
        params = dict(cItem)
        params.update({"name": "category", "category": "list_items", "url": self.getFullUrl("search?q=%s" % urllib_quote_plus(searchPattern)),
                       "good_for_fav": False, "page": 1})
        self.listItems(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = self._rebase(cItem.get("url", ""))
        printDBG("AlooyTV.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        sources = []
        video = self.cm.ph.getDataBeetwenMarkers(data, "<video", "</video>", False)[1]
        for src in re.findall(r'<source[^>]+src="([^"]+)"', video):
            sources.append(src.replace("&amp;", "&").strip())
        for enc in re.findall(r'download_video\.php\?video_url=([^"&]+)', data):
            try:
                sources.append(b64Decode(urllib_unquote(enc)).strip())
            except Exception:
                printExc()
        # newer episodes: <iframe src="/m3u8/?src=<embed>"> - the site's own player page carries the HLS url
        for frame in re.findall(r'<iframe[^>]+src="([^"]*/m3u8/\?src=[^"]+)"', data):
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=url)
            sts, page = self.getPage(self.getFullUrl(frame.replace("&amp;", "&").replace("#", "%23")), params)
            hls = self.cm.ph.getSearchGroups(page, r'''(?:const|var|let)\s+url\s*=\s*["'](https?://[^"']+)["']''')[0] if sts else ""
            if hls:
                sources.append(hls.replace("\\/", "/"))
        meta = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL, "Origin": self.MAIN_URL.rstrip("/")}
        proxy = self.getProxy()
        if proxy:
            meta["iptv_http_proxy"] = proxy
        urltab = []
        seen = set()
        for src in sources:
            if not self.cm.isValidUrl(src):
                continue
            # vid1..vid10.<cdn> urls are the same file on another server: mirrors, kept
            if src in seen:
                continue
            seen.add(src)
            urltab.append({"name": "AlooyTV %d - %s" % (len(urltab) + 1, self.up.getDomain(src)), "url": strwithmeta(src, dict(meta)), "need_resolve": 0})
        story = self._siteInfo(data)[0]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("AlooyTV.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)</h1>.*?<p>(.*?)</p>\s*</div>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, poster

    def getArticleContent(self, cItem):
        url = self._rebase(cItem.get("url", ""))
        printDBG("AlooyTV.getArticleContent [%s]" % url)
        meta = {}
        story, poster, info = "", "", {}
        sts, data = self.getPage(url)
        year = ""
        if sts:
            story, poster = self._siteInfo(data)
            genres = [self.cleanHtmlStr(g) for g in re.findall(r'<a href="[^"]+/genre/[^"]+"[^>]*>([^<]+)<', self.cm.ph.getDataBeetwenMarkers(data, "<strong>Genre: </strong>", "</p>", False)[1])]
            if genres:
                info["genres"] = ", ".join(genres)
            release = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<strong>Release: </strong>([^<]*)<")[0])
            if release:
                info["released"] = release
                year = release[:4]
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<strong>Quality:</strong>\s*<span[^>]*>([^<]*)<')[0])
            if quality:
                info["quality"] = quality
            head = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'class="movie-heading[^"]*"[^>]*>\s*<span>([^<]*)</span>')[0])
            if head and cItem.get("meta_type") == "tv":
                info["seasons"] = head
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year") or year)
            except Exception:
                printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
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
        printDBG("AlooyTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "al_genres":
            self.listGenres(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "al_series":
            self.listEpisodes(self.currItem)
        elif category in ("search", "search_next_page"):
            params = dict(self.currItem)
            params.update({"search_item": False, "name": "category"})
            self.listSearchResult(params, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, AlooyTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("alooytv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("al_movie", "al_episode", "al_series")
