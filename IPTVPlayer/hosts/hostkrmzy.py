# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# original file from: 14/11/2025 - popking (odem2014)
# 24.09.2026 - Mohamed Elsafty (angel_heart)
# Modified for new domain: https://w1.qrmzi.cyou/ with Movies & Series sections
# 10.10.2026 - domain moved to www.qrmzi.tv (old w1.qrmzi.cyou links of favourites are mapped there); host standard:
#   - menus: latest episodes (the home page), series, movies, search - with First page / Jump / Next page
#     (the site's "/page/N/", last page from its pager)
#   - series -> episodes (ascending, local paging over 100); episodes and movies are VIDEO rows keyed on their page
#     url (watched flag series -> episode, downloaded flag, favourites incl. the old series / episode folders)
#   - the servers of the albaplayer frame (CDNPlus, Vidoba, VidSpeed, OK, MP4Plus, AnaFast ...) are links resolved
#     through urlparser only when chosen; the old anafast m3u8 shortcut and the dead qesen.net fallback are gone
#   - name normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta (the Turkish title from the
#     player's slug or the story) + the site's story / poster; no colour codes in titles; py2 load fix (no f-strings)
#   - covers carry the cf_clearance cookie + User-Agent once MyE2i solved a Cloudflare check
# 10.10.2026 - review: an albaplayer server without a name is "Server <n>" through the shared msgid
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.qrmzi.tv/"


LOCAL_PAGE_SIZE = 100
EPISODE_RE = re.compile(r"^(.*?)\s*(?:الحلقة|حلقة)\s*(\d+)")
SEASON_RE = re.compile(r"الموسم\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s)((?:19|20)\d{2})(?=\s|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مسلسل|فيلم|مترجم|مترجمة|مدبلج|مدبلجة|والاخيرة|والأخيرة|الاخيرة|الأخيرة|اون لاين|أون لاين|مشاهدة|وتحميل|كامل|كاملة|HD|قرمزي)(?=\s|$)")
# /series/<slug>, /movies/<slug>, /episode/<slug>
KIND_RE = re.compile(r"^/(series|movies|episode)/[^/]+$")
# the site's domains, also the old w1.qrmzi.cyou of favourites saved by the previous version
SITE_DOMAIN_RE = re.compile(r"^https?://(?:[a-z0-9-]+\.)*qrmzi\.[a-z]+(?=/|$)", re.I)
# albaplayer slug: <turkish-title>[-<year>][-sNNeNN]
SLUG_RE = re.compile(r"/albaplayer/([a-z0-9-]+?)(?:-((?:19|20)\d{2}))?(?:-s(\d+)e(\d+))?/?(?:[?#]|$)", re.I)
# the first run of Latin words in the site's story ("... نصف الأم Anne Yarısı حول ...")
LATIN_RUN_RE = re.compile(u"[A-Za-z\u00c0-\u024f][A-Za-z0-9\u00c0-\u024f'!&.:\\- ]*[A-Za-z0-9\u00c0-\u024f!]", re.U)


def _clean(text):
    text = JUNK_RE.sub(" ", JUNK_RE.sub(" ", text or ""))
    # the en dash as a whole sequence (py2 str.strip would take its single utf-8 bytes)
    return re.sub(r"\s+", " ", text.replace("–", " ")).strip(" -:|")


def _noColors(text):
    # titles of rows saved by the previous version carry \cAARRGGBB colour codes
    return re.sub(r"\\c[0-9A-Fa-f]{8}", "", text or "").strip()


def _latinRun(text):
    # py2: the page is a utf-8 str - the Latin letters with accents (ı, ş, ğ ...) need unicode
    try:
        utext = text if isinstance(text, type(u"")) else text.decode("utf-8", "ignore")
        m = LATIN_RUN_RE.search(utext)
        if not m or len(m.group(0)) < 3:
            return ""
        run = m.group(0).strip()
        return run if isinstance(run, str) else run.encode("utf-8")
    except Exception:
        printExc()
    return ""


class Krmzy(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "krmzy", "cookie": "krmzy.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/krmzy135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "list_items", "title": _("Latest episodes"), "url": self.MAIN_URL},
            {"category": "list_items", "title": _("Series"), "url": self.MAIN_URL + "all-turkish-series/"},
            {"category": "list_items", "title": _("Movies"), "url": self.MAIN_URL + "all-turkish-movies/"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("krmzy")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        # one form for every page url: current domain, percent-encoded Arabic slugs
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        elif not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        url = SITE_DOMAIN_RE.sub(self.MAIN_URL.rstrip("/"), url)
        try:
            return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", urllib_unquote(self._canonUrl(url))).split("?")[0].rstrip("/").lower()

    def _kind(self, url):
        # "series" / "movies" / "episode" / "" for anything else
        m = KIND_RE.search(self._path(url))
        return m.group(1) if m else ""

    def _isSiteUrl(self, url):
        return bool(SITE_DOMAIN_RE.search(url or ""))

    def getFullIconUrl(self, url, currUrl=None):
        # once MyE2i stored a cf_clearance cookie (a later Cloudflare check) the cover download needs it + the
        # User-Agent that passed the check; covers on foreign domains stay plain
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http") or self.up.getDomain(url).lower() != self.up.getDomain(self.MAIN_URL).lower():
            return url
        meta = {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    def _icon(self, url):
        url = (url or "").strip().strip("'\"")
        if not url or url.startswith("data:"):
            return ""
        return self.getFullIconUrl(self._canonUrl(url))

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("kz_video", "kz_series"):
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
            prefix = {"kz_video": "video", "kz_series": "series"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _episodeParams(self, label, url, icon, desc, normalize, show="", episode=""):
        m = EPISODE_RE.search(label)
        episode = episode or (m.group(2) if m else "")
        season = SEASON_RE.search(label)
        season = int(season.group(1)) if season else 1
        if not show:
            show = _clean(SEASON_RE.sub(" ", m.group(1) if m else label)) or _clean(label)
        title = label
        if normalize and episode:
            title = "%s - %s" % (show, formatSxxExx(season, episode))
        return {"name": "category", "good_for_fav": True, "category": "kz_video", "title": title, "url": url, "icon": icon, "desc": desc,
                "s_title": show, "s_season": season, "s_episode": str(int(episode)) if episode else "", "meta_type": "tv", "meta_title": show}

    def _movieParams(self, label, url, icon, desc, normalize):
        title = _clean(label) or label
        year = YEAR_RE.search(title)
        year = year.group(1) if year else ""
        metaTitle = _clean(YEAR_RE.sub(" ", title)) or title
        dispTitle = label
        if normalize:
            dispTitle = "%s (%s)" % (metaTitle, year) if year else metaTitle
        return {"name": "category", "good_for_fav": True, "category": "kz_video", "title": dispTitle, "url": url, "icon": icon, "desc": desc,
                "meta_type": "movie", "meta_title": metaTitle, "meta_year": year}

    def _seriesParams(self, label, url, icon, normalize):
        show = _clean(label) or label
        return {"name": "category", "good_for_fav": True, "category": "kz_series", "title": show if normalize else label, "url": url, "icon": icon,
                "s_title": show, "meta_type": "tv", "meta_title": show}

    def _cards(self, data):
        # (url, label, icon, episode number) of the <article class="post"> / "postEp" cards
        out = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenNodes(data, ("<article", ">"), ("</article", ">")):
            url = self._canonUrl(self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0])
            if not url or url in seen or not self._kind(url):
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="title">(.*?)</div>')[0])
            if not label:
                label = _clean(self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0]))
            if not label:
                continue
            number = self.cm.ph.getSearchGroups(item, r'(?s)class="episodeNum">.*?<span>[^<]*</span>\s*<span>\s*(\d+)\s*</span>')[0]
            icon = self.cm.ph.getSearchGroups(item, r'data-src=["\']?([^"\'\s>]+)')[0] or self.cm.ph.getSearchGroups(item, r"background-image:\s*url\(([^)]+)\)")[0]
            out.append((url, label, self._icon(icon), number))
        return out

    @staticmethod
    def _pageTpl(baseUrl):
        return baseUrl.split("?")[0].rstrip("/") + "/page/{page}/"

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem["url"])
        pageTpl = self._pageTpl(baseUrl)
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("Krmzy.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        for url, label, icon, number in self._cards(data):
            kind = self._kind(url)
            if kind == "series":
                self.addDir(self._seriesParams(label, url, icon, normalize))
            elif kind == "episode":
                self.addVideo(self._episodeParams(label, url, icon, "", normalize, episode=number))
            else:
                self.addVideo(self._movieParams(label, url, icon, "", normalize))

        # pager: <div class='pagination'> ... <a href='.../page/N/'>&raquo;</a> (last page)
        pager = self.cm.ph.getDataBeetwenMarkers(data, "class='pagination'", "</div>", False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', "</div>", False)[1]
        pages = [int(p) for p in re.findall(r"/page/(\d+)/?['\"]", pager)]
        lastPage = max(pages) if pages else 0
        hasNext = page < lastPage
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage if hasNext or page > 1 else 0, pageTpl)

    def listSeries(self, cItem):
        page = cItem.get("page", 1)
        printDBG("Krmzy.listSeries [%s] page[%s]" % (cItem.get("url", ""), page))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        story = self._siteInfo(data)[0]
        # series folders saved by the previous version have a coloured title and no s_title
        show = cItem.get("s_title", "") or _clean(_noColors(cItem.get("title", "")))
        metaTitle = _latinRun(story) or cItem.get("meta_title") or show
        episodes = []
        for url, label, icon, number in self._cards(data):
            if self._kind(url) != "episode":
                continue
            params = self._episodeParams(label, url, icon or cItem.get("icon", ""), story, normalize, show, number)
            params["meta_title"] = metaTitle
            episodes.append(params)
        episodes.sort(key=lambda p: int(p["s_episode"]) if p["s_episode"] else 0)
        if not episodes:
            # the site lists series before their first episode ("يعرض قريباً")
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listOldFolder(self, cItem):
        # favourites of the previous version: an episode / movie was a folder ("explore_item") - one row to play
        url = self._canonUrl(cItem.get("url", ""))
        # its episode titles were "حلقة <n> - <site title>"
        label = re.sub(r"^حلقة\s*\d+\s*-\s*", "", _noColors(cItem.get("title", "")))
        if self._kind(url) == "episode":
            self.addVideo(self._episodeParams(label, url, cItem.get("icon", ""), "", IsMediaNamingNormalized()))
        else:
            self.addVideo(self._movieParams(label, url, cItem.get("icon", ""), "", IsMediaNamingNormalized()))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Krmzy.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        baseUrl = "%ssearch/%s/" % (self.MAIN_URL, urllib_quote(searchPattern.strip(), safe=""))
        cItem.update({"category": "list_items", "url": baseUrl, "base_url": baseUrl, "page": 1})
        self.listItems(cItem)
        if not self.currList:
            # the site only knows the Arabic titles
            SetIPTVPlayerLastHostError(_("No results found for: %s") % searchPattern)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # story and poster of a series, episode or movie page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="story">(.*?)</div>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"')[0]
        return story, poster

    def _playerFrame(self, data):
        # the page's player iframe (the albaplayer page that lists the servers); the textarea holds embed code only
        data = re.sub(r"(?is)<textarea[^>]*>.*?</textarea>", "", data)
        frame = self.cm.ph.getSearchGroups(data, r'(?is)<div[^>]+class=["\'][^"\']*video-con[^"\']*["\'][^>]*>.*?<iframe[^>]+src=["\']([^"\']+)["\']')[0]
        if not frame:
            for src in re.findall(r'(?i)<iframe[^>]+src=["\']([^"\']+)["\']', data):
                if "albaplayer" in src or not self._isSiteUrl(src):
                    frame = src
                    break
        frame = frame.replace("&amp;", "&").strip()
        return "https:" + frame if frame.startswith("//") else frame

    def getLinksForVideo(self, cItem):
        pageUrl = cItem.get("url", "")
        printDBG("Krmzy.getLinksForVideo [%s]" % pageUrl)
        if not self.cm.isValidUrl(pageUrl):
            return []
        sidecar = buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled())
        if not self._isSiteUrl(pageUrl):
            # a server row saved as favourite by the previous version (albaplayer "?serv=N" or a hoster url)
            return applySidecarToLinks([{"name": self.up.getHostName(pageUrl, True), "url": pageUrl, "need_resolve": 1}], sidecar)
        pageUrl = self._canonUrl(pageUrl)
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        frame = self._playerFrame(data)
        if not self.cm.isValidUrl(frame):
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        urltab = []
        if "albaplayer" in frame:
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=pageUrl)
            sts, data = self.getPage(frame, params)
            seen = set()
            for url, name in re.findall(r'(?i)<a[^>]+href=["\']([^"\']*albaplayer[^"\']*serv=\d+[^"\']*)["\'][^>]*>(.*?)</a>', data if sts else ""):
                url = url.replace("&amp;", "&").strip()
                if url in seen:
                    continue
                seen.add(url)
                name = self.cleanHtmlStr(name) or "%s %s" % (_("Server"), self.cm.ph.getSearchGroups(url, r"serv=(\d+)")[0])
                urltab.append({"name": name, "url": strwithmeta(url, {"Referer": pageUrl}), "need_resolve": 1})
        if not urltab:
            urltab.append({"name": self.up.getHostName(frame, True), "url": strwithmeta(frame, {"Referer": pageUrl}), "need_resolve": 1})
        return applySidecarToLinks(urltab, sidecar)

    def getVideoLinks(self, videoUrl):
        printDBG("Krmzy.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if "albaplayer" in videoUrl:
            # the chosen server's page of the albaplayer: its player iframe goes to urlparser
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=strwithmeta(videoUrl).meta.get("Referer", self.MAIN_URL))
            sts, data = self.getPage(videoUrl, params)
            frame = self._playerFrame(data) if sts else ""
            if not self.cm.isValidUrl(frame) or "albaplayer" in frame:
                SetIPTVPlayerLastHostError(_("No stream available"))
                return []
            videoUrl = strwithmeta(frame, {"Referer": "%s://%s/" % (videoUrl.split("://")[0], self.up.getDomain(videoUrl))})
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Krmzy.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        metaType = cItem.get("meta_type") or ("tv" if self._kind(cItem.get("url", "")) != "movies" else "movie")
        metaTitle = cItem.get("meta_title") or _clean(_noColors(cItem.get("title", "")))
        year = cItem.get("meta_year", "")
        sts, data = self.getPage(cItem.get("url", "")) if self._isSiteUrl(cItem.get("url", "")) else (False, "")
        if sts:
            story, poster = self._siteInfo(data)
            # the player's slug carries the Turkish title, the year and SxxExx: anne-yarisi-2026-s01e03
            slug = SLUG_RE.search(self._playerFrame(data))
            if slug:
                metaTitle = slug.group(1).replace("-", " ").strip() or metaTitle
                year = slug.group(2) or year
                if slug.group(3):
                    info["seasons"] = str(int(slug.group(3)))
                    info["episodes"] = str(int(slug.group(4)))
            elif not isLatinTitle(metaTitle):
                metaTitle = _latinRun(story) or metaTitle
        meta = {}
        if metaTitle:
            try:
                meta = getMeta(metaType, metaTitle, year, () if isLatinTitle(metaTitle) else LATIN_ONLY)
            except Exception:
                printExc()
        if year:
            info.setdefault("year", year)
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or StripColorCodes(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or (self._icon(poster) if poster else "") or cItem.get("icon", "")
        return [{"title": _noColors(cItem.get("title", "")), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", "")
        printDBG("Krmzy.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category in ("list_items", "list_series", "list_movies"):
            self.listItems(self.currItem)
        elif category in ("kz_series", "series_details"):
            self.listSeries(self.currItem)
        elif category == "explore_item":
            self.listOldFolder(self.currItem)
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
        CHostBase.__init__(self, Krmzy(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("krmzy")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("kz_video", "kz_series")
