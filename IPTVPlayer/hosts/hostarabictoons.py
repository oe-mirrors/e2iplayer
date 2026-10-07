# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 framework / host standard
#   - arabic-toons.com (Arabic cartoons): series and movies (?next=N, First page / Jump / Next page),
#     A-Z letter lists and search (one long page each -> local paging over 100)
#   - series -> episodes; movies and episodes are VIDEO rows keyed on their page url; the page's player
#     gives a direct, tokenised MP4 (stream.foupix.com) that is bound to the User-Agent the page was
#     loaded with - the link carries that UA + Referer
#   - watched flag (series:/video: page-url keys), downloaded flag, favourites, name normalisation
#     ("Show - SxxExx"), sidecar, INFO via moviemeta + the page's story / rating
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.arabic-toons.com/"


LOCAL_PAGE_SIZE = 100
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثانى", 2), ("الثالث", 3),
    ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"\s*الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
MOVIE_WORD_RE = re.compile(r"^(?:\s*(?:فيلم|الفيلم)\s+)+")
# list rows: <a href="...-anime-streaming.html" title=".."> (series) / "...-movies-streaming.html" (movies)
ROW_RE = re.compile(r'(?s)<a href="([^"]+-(anime|movies)-streaming\.html)"[^>]*>(.*?)</a>')


def _splitSeason(title):
    # "سبونج بوب الموسم 11" -> ("سبونج بوب", 11)
    m = SEASON_RE.search(title or "")
    if not m:
        return title, 0
    val = m.group(1)
    num = int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)
    return (title[:m.start()] + title[m.end():]).strip(" -"), num


class ArabicToons(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "series_url", "meta_type", "meta_title")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "arabictoons", "cookie": "arabictoons.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/arabictoons135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/cartoon.php")},
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/movies.php")},
            {"category": "at_letters", "title": _("A-Z"), "url": self.getFullUrl("/cartoon.php")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("arabictoons")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _url(self, url):
        return self.getFullUrl((url or "").split("#")[0].strip())

    def _path(self, url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", self._url(url)).rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("at_video", "at_series"):
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
            prefix = {"at_video": "video", "at_series": "series"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listLetters(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for href, label in re.findall(r'href="(\d+-tri\.html)"[^>]*>([^<]+)<', data):
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": self.cleanHtmlStr(label),
                         "url": self._url(href), "local_paging": True})

    def _rows(self, data):
        normalize = IsMediaNamingNormalized()
        rows = []
        seen = set()
        for href, kind, item in ROW_RE.findall(data):
            url = self._url(href)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="(?:cinema-title|result-title)">(.*?)</')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
            if not title or url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon.strip()) if icon else "", "desc": ""}
            if kind == "movies":
                name = MOVIE_WORD_RE.sub("", title)
                params.update({"category": "at_video", "title": name if normalize else title, "meta_type": "movie", "meta_title": name})
            else:
                show, season = _splitSeason(title)
                params.update({"category": "at_series", "title": title, "s_title": show, "s_season": season or 1,
                               "meta_type": "tv", "meta_title": show})
            rows.append(params)
        return rows

    def _addRows(self, rows):
        for params in rows:
            if params["category"] == "at_series":
                self.addDir(params)
            else:
                self.addVideo(params)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._url(cItem.get("url", ""))
        if cItem.get("local_paging"):
            # letter lists and search: everything on one page
            sts, data = self.getPage(baseUrl)
            if not sts:
                return
            rows = self._rows(data)
            start = (page - 1) * LOCAL_PAGE_SIZE
            self._addRows(rows[start:start + LOCAL_PAGE_SIZE])
            if len(rows) > LOCAL_PAGE_SIZE:
                lastPage = (len(rows) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
                addPagingItems(self, dict(cItem, base_url=baseUrl), page, page < lastPage, lastPage)
            return
        pageTpl = baseUrl.split("?")[0] + "?next={page}"
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("ArabicToons.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        rows = self._rows(data)
        self._addRows(rows)
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination-pages', "</div>", False)[1]
        lastPage = max([int(n) for n in re.findall(r"next=(\d+)", pager)] + [page])
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, bool(rows) and lastPage > page, lastPage, pageTpl)

    def listEpisodes(self, cItem):
        printDBG("ArabicToons.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="episodes-grid"', "<footer", False)[1]
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        # fix 071026: the pager rows carry the title "Next page" - keep the folder's own title for page 2+
        folderTitle = cItem.get("folder_title") or cItem.get("title", show)
        normalize = IsMediaNamingNormalized()
        episodes = []
        seen = set()
        for href, item in re.findall(r'(?s)<a href="([^"]+)"[^>]*>(.*?)</a>', block):
            url = self._url(href)
            num = self.cm.ph.getSearchGroups(item, r'class="episode-number">\s*(\d+)')[0]
            if not num or url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="cinema-title">(.*?)</div>')[0])
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            title = "%s - %s" % (show, formatSxxExx(season, num)) if normalize else "%s - %s" % (folderTitle, label or num)
            episodes.append({"name": "category", "good_for_fav": True, "category": "at_video", "url": url, "title": title,
                             "icon": self.getFullIconUrl(icon.strip()) if icon else cItem.get("icon", ""), "desc": cItem.get("desc", ""),
                             "series_url": cItem["url"], "s_title": show, "s_season": season, "s_episode": str(int(num)),
                             "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, folder_title=folderTitle), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ArabicToons.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/search_results.php?q=%s" % urllib_quote_plus(searchPattern.strip()))
        cItem.update({"category": "list_items", "page": 1, "url": base, "base_url": base, "local_paging": True})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _videoUrl(self, data):
        url = self.cm.ph.getSearchGroups(data, r'videoSrc\s*=\s*"([^"]+)"')[0]
        if not url:
            url = self.cm.ph.getSearchGroups(data, r'<source[^>]+src="([^"]+)"')[0] or \
                self.cm.ph.getSearchGroups(data, r'<video[^>]+src="([^"]+)"')[0]
        return url.replace("&amp;", "&").strip()

    def getLinksForVideo(self, cItem):
        printDBG("ArabicToons.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._url(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        videoUrl = self._videoUrl(data)
        if not videoUrl:
            # the second player of the page shows the file as <source>
            sts, data = self.getPage(pageUrl, post_data={"player_choice": "plyr"})
            videoUrl = self._videoUrl(data) if sts else ""
        if not self.cm.isValidUrl(videoUrl):
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        # the file token is bound to the User-Agent the page was loaded with
        meta = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.getMainUrl(), "Origin": self.getMainUrl().rstrip("/")}
        urltab = [{"name": "MP4", "url": strwithmeta(videoUrl, meta), "need_resolve": 0}]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("ArabicToons.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                # fix 071026: Arabic titles -> no IMDb/Cinemeta/OMDb (they answer with unrelated English hits)
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], "", skip)
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(self._url(cItem.get("series_url") or cItem.get("url", "")))
        if sts:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)id="descriptionText">(.*?)</div>')[0])
            poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
            rating = self.cm.ph.getSearchGroups(data, r'(?s)id="score"[^>]*>\s*([\d.]+)')[0]
            votes = self.cm.ph.getSearchGroups(data, r'id="cnt"[^>]*>\s*(\d+)')[0]
            if rating:
                info["rating"] = "%s/5 (%s)" % (rating, votes) if votes else "%s/5" % rating
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "") or cItem.get("title", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
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
        printDBG("ArabicToons.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "at_letters":
            self.listLetters(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "at_series":
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
        CHostBase.__init__(self, ArabicToons(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("arabictoons")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("at_video", "at_series")
