# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - brought to the current host standard (same "O2 CMS" as akwam)
#   - lists /movies, /series, /search?q=.. and the section / genre / year filters of the home page
#     (guarded: no IndexError on a page without the block); paging via iptvpaging (First page /
#     Jump / Next page with the last page from the pager), search pages keep the query
#   - movies and episodes are VIDEO rows keyed on their page url; the direct downet.net MP4s
#     (signed, short-lived) are fetched in getLinksForVideo from the /watch/ page - all
#     qualities, need_resolve 0; files the CDN answers 403 for (new uploads on af3.downet.net, site
#     side) are dropped after a headers-only check, with a message when none is left
#   - series -> episodes; the season is the number the site appends to the show ("Teen Wolf 6")
#   - watched flag (movie:/series:/episode: ids), downloaded flag, favourites, sidecar,
#     name normalisation ("Show - SxxExx", the episode name in the description), INFO via moviemeta (IMDb id of the page)
#     + the site's story/poster/fields
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://aflaam.com/"


# "Teen Wolf 6" / "1 The Witcher" (the number lands in front in RTL markup) -> season
SEASON_TAIL_RE = re.compile(r"^(.*\S)\s+(\d{1,2})$")
SEASON_HEAD_RE = re.compile(r"^(\d{1,2})\s+(\D.*)$")
# "<span>مدة الفيلم : </span> <span>133 دقيقة</span>" fields of a title page -> INFO keys
INFO_FIELDS = (("duration", "مدة"), ("quality", "جودة"), ("country", "انتاج"), ("language", "اللغة"), ("subtitles", "الترجمة"))
# home page filter blocks (menu category "list_value", key "s")
FILTER_BLOCKS = ("القسم", "التصنيف", "سنة الإنتاج")


class Aflaam(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Aflaam", "cookie": "aflaam.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("style/assets/images/logo.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("series")},
            {"category": "list_value", "title": _("Sections"), "s": "القسم"},
            {"category": "list_value", "title": _("Genres"), "s": "التصنيف"},
            {"category": "list_value", "title": _("Year"), "s": "سنة الإنتاج"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("aflaam")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        # one ASCII form (percent-encoded, no &amp;) for requests, the downloaded marker and favourites
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        url = self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    @staticmethod
    def _pageId(url):
        # ("movie"|"series"|"episode", "<id>") from a content url
        m = re.search(r"/(movie|series|episode)/(\d+)", url or "")
        return (m.group(1), m.group(2)) if m else ("", "")

    @staticmethod
    def _pageNum(url):
        m = re.search(r"[?&]page=(\d+)", url or "")
        return int(m.group(1)) if m else 1

    @staticmethod
    def _pageTpl(url):
        # the url of any page of the list: "...?q=x&page={page}"
        base = re.sub(r"([?&])page=\d+&?", r"\1", url or "").rstrip("?&")
        return "%s%spage={page}" % (base, "&" if "?" in base else "?")

    @staticmethod
    def _splitSeason(title):
        # "Teen Wolf 6" -> ("Teen Wolf", 6); "1 The Witcher" -> ("The Witcher", 1); "Chernobyl" -> ("Chernobyl", 1)
        title = re.sub(r"\s+", " ", title or "").strip()
        m = SEASON_TAIL_RE.match(title)
        if m:
            return m.group(1).strip(" -:"), int(m.group(2))
        m = SEASON_HEAD_RE.match(title)
        if m:
            return m.group(2).strip(" -:"), int(m.group(1))
        return title, 1

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("category", "") not in ("af_video", "af_series"):
                return ""
            kind, pid = self._pageId(cItem.get("url", ""))
            return "%s:%s" % (kind, pid) if pid else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # menus
    ###################################################
    def listValue(self, cItem):
        printDBG("Aflaam.listValue [%s]" % cItem.get("s", ""))
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<span class="text">%s</span>' % cItem.get("s", ""), "</ul>", False)[1]
        if not block:
            printDBG("Aflaam.listValue: filter block [%s] not found" % cItem.get("s", ""))
            return
        isYear = cItem.get("s", "") == FILTER_BLOCKS[2]
        for url, title in re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', block):
            title = self.cleanHtmlStr(title)
            if not title or (isYear and not re.match(r"^(19|20)\d\d$", title)):
                continue  # the site lists a broken "22023"
            params = {"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": self._canonUrl(url)}
            self.addDir(params)

    def listItems(self, cItem):
        url = cItem.get("url", "")
        printDBG("Aflaam.listItems [%s]" % url)
        if self._pageId(url)[0] == "series":
            # a series favourite of the old host version (category list_items)
            return self.listEpisodes(dict(cItem, category="af_series"))
        sts, data = self.getPage(url)
        if not sts:
            return
        seen = set()
        for item in data.split('class="entry-box')[1:]:
            href = self._canonUrl(self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0])
            kind, pid = self._pageId(href)
            if kind not in ("movie", "series") or (kind, pid) in seen:
                continue
            seen.add((kind, pid))
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3[^>]*>(.*?)</h3>')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<span class="label rating">(.*?)</span>')[0])
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<span class="label quality">(.*?)</span>')[0])
            desc = " | ".join(["%s: %s" % (label, value) for label, value in ((_("Rating"), rating), (_("Quality"), quality)) if value])
            params = {"name": "category", "good_for_fav": True, "url": href, "icon": self.getFullIconUrl(icon), "desc": desc}
            if kind == "series":
                show, season = self._splitSeason(title)
                params.update({"category": "af_series", "title": title, "s_title": show, "s_season": season,
                               "meta_type": "tv", "meta_title": show, "meta_year": ""})
                self.addDir(params)
            else:
                # the list carries no year ("Title (Year)" would cost a request per movie)
                params.update({"category": "af_video", "title": title, "meta_type": "movie", "meta_title": title, "meta_year": ""})
                self.addVideo(params)

        page = int(cItem.get("page", 0) or 0) or self._pageNum(url)
        hasNext = bool(seen) and 'rel="next"' in data
        pages = [int(p) for p in re.findall(r'class="page-link"[^>]+href="[^"]*[?&](?:amp;)?page=(\d+)"', data)]
        lastPage = max(pages) if pages else 0
        if lastPage < page:
            lastPage = page if not hasNext else 0
        listItem = dict(cItem, category="list_items")
        addPagingItems(self, listItem, page, hasNext, lastPage, self._pageTpl(url))

    def listEpisodes(self, cItem):
        printDBG("Aflaam.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        h1 = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h1[^>]*>(.*?)</h1>')[0])
        siteShow = h1 or cItem.get("title", "")
        show, season = self._splitSeason(siteShow)
        show = cItem.get("s_title", "") or show
        season = cItem.get("s_season", 0) or season
        imdb = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
        year = self.cm.ph.getSearchGroups(data, r"سنة الإنتاج\s*:\s*(\d{4})")[0]
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in data.split('class="entry-box-3')[1:]:
            href = self._canonUrl(self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0])
            kind, pid = self._pageId(href)
            if kind != "episode" or pid in seen:
                continue
            seen.add(pid)
            label = self.cm.ph.getSearchGroups(item, r'(?s)<h3[^>]*>(.*?)</h3>')[0]
            epNum = self.cm.ph.getSearchGroups(label, r'<span[^>]*>\s*(\d+)\s*</span>')[0] or self.cm.ph.getSearchGroups(urllib_unquote(href), r"(\d+)/?$")[0]
            label = self.cleanHtmlStr(label)
            epName = self.cleanHtmlStr(re.sub(r"^\s*%s\s*" % re.escape(epNum), "", label)) if epNum else label
            if normalize and epNum:
                title = "%s - %s" % (show, formatSxxExx(season, epNum))
            else:
                title = "%s - %s" % (siteShow, label) if label else siteShow
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            # the episode name goes into the description, the normalised title stays "Show - SxxExx"
            desc = cItem.get("desc", "")
            if epName and not re.match(r"^(?:الحلقة\s*)?\d+$", epName):
                desc = "%s[/br]%s" % (epName, desc) if desc else epName
            self.addVideo({"name": "category", "good_for_fav": True, "category": "af_video", "title": title, "url": href,
                           "icon": self.getFullIconUrl(icon) if icon else cItem.get("icon", ""), "desc": desc,
                           "s_title": show, "s_season": season, "s_episode": epNum, "e_title": epName,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", "") or show, "meta_year": year, "meta_imdb": imdb})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Aflaam.listSearchResult [%s]" % searchPattern)
        # list_items: the pager rows must not rebuild page 1 from the search pattern
        cItem = dict(cItem, category="list_items", page=1, url=self.getFullUrl("search?q=%s" % urllib_quote_plus(searchPattern)))
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Aflaam.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        # one quality bar per size: <span ..>1080p</span> ... <a href=".../watch/<id>/...">
        watch = []
        for block in data.split('alt="Quality"')[1:]:
            href = self.cm.ph.getSearchGroups(block, r'href="([^"]+/watch/[^"]+)"')[0]
            if href:
                watch.append((self.cm.ph.getSearchGroups(block, r">\s*(\d{3,4})p\s*<")[0], self._canonUrl(href)))
        # one /watch/ page usually carries the <source> of every quality; the others only when missing
        sources = {}
        subtitles = []
        for size, href in watch:
            if size and size in sources:
                continue
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=pageUrl)
            sts, page = self.getPage(href, params)
            if not sts:
                continue
            video = self.cm.ph.getDataBeetwenMarkers(page, "<video", "</video>", False)[1]
            for src in re.findall(r"<source[^>]+>", video):
                url = self.cm.ph.getSearchGroups(src, r'src="([^"]+)"')[0].strip()
                if not self.cm.isValidUrl(url):
                    continue
                key = self.cm.ph.getSearchGroups(src, r'size="(\d+)"')[0] or size or "#%d" % (len(sources) + 1)
                if key not in sources:
                    sources[key] = url
            for trk in re.findall(r"<track[^>]+>", video):
                sub = self.getFullUrl(self.cm.ph.getSearchGroups(trk, r'src="([^"]+)"')[0])
                if self.cm.isValidUrl(sub) and sub not in [s["url"] for s in subtitles]:
                    lang = self.cm.ph.getSearchGroups(trk, r'srclang="([^"]+)"')[0] or "ar"
                    subtitles.append({"title": self.cm.ph.getSearchGroups(trk, r'label="([^"]+)"')[0] or lang, "url": sub, "lang": lang,
                                      "format": "vtt" if ".vtt" in sub else "srt"})
        urltab = []
        meta = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL}
        if subtitles:
            meta["external_sub_tracks"] = subtitles
        forbidden = 0
        for key in sorted(sources, key=lambda k: int(k) if k.isdigit() else 0, reverse=True):
            if self._isForbidden(sources[key]):
                forbidden += 1
                continue
            name = ("Aflaam %sp" % key) if key.isdigit() else ("Aflaam %s" % key)
            urltab.append({"name": name, "url": strwithmeta(sources[key], dict(meta)), "need_resolve": 0})
        if not urltab and forbidden:
            SetIPTVPlayerLastHostError(_("The video file of this title is not available on the server (HTTP 403)."))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def _isForbidden(self, url):
        # some uploads on af3.downet.net answer 403 for everybody (the origin's file permissions, whatever
        # Referer/cookies/token): headers only, so the player is not started on a dead file
        # Range 0-0 -> 1 byte (or the small 403 page); the size cap only matters if the server ignores Range
        # (max_data_size 0 aborted every transfer and logged a pycurl exception each time)
        params = {"header": {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL, "Range": "bytes=0-0"}, "max_data_size": 65536}
        self.cm.getPage(url, params)
        return self.cm.meta.get("status_code") == 403

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        story = self.cm.ph.getSearchGroups(data, r'(?s)قصة\s*(?:الفيلم|المسلسل|الحلقة)?\s*</a>\s*</h2>.*?<div class="widget-body">(.*?)</div>')[0]
        story = self.cleanHtmlStr(story)
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, poster

    def getArticleContent(self, cItem):
        printDBG("Aflaam.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info, imdb, year = "", "", {}, cItem.get("meta_imdb", ""), cItem.get("meta_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster = self._siteInfo(data)
            imdb = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0] or imdb
            year = self.cm.ph.getSearchGroups(data, r"سنة الإنتاج\s*:\s*(\d{4})")[0] or year
            if year:
                info["year"] = year
            rating = self.cm.ph.getSearchGroups(data, r'(?s)تقييم IMDb.*?<span class="font-size-24">([^<]+)<')[0].strip()
            if rating:
                info["rating"] = rating
            for key, word in INFO_FIELDS:
                val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<span>\s*%s[^:<]*:\s*</span>\s*<span>([^<]+)<" % word)[0])
                if val:
                    info[key] = val
            genres = [self.cleanHtmlStr(g) for g in re.findall(r'class="movie-category[^"]*"[^>]*>([^<]+)<', data)]
            if genres:
                info["genres"] = ", ".join(genres[:6])
        meta = {}
        mediaType = cItem.get("meta_type", "")
        try:
            if mediaType and imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and mediaType and cItem.get("meta_title"):
                meta = getMeta(mediaType, cItem["meta_title"], year)
        except Exception:
            printExc()
        meta = meta or {}
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
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Aflaam.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
        elif category == "af_series":
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
        CHostBase.__init__(self, Aflaam(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("aflaam")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("af_video", "af_series")
