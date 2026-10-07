# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - rework for we.3isq.cam (b.3isq.cam redirects there; Cloudflare, cleared via
#   pCommon getPageCFProtection / MyE2i)
#   - menus from the site's current navigation: latest episodes, recently added, most viewed, all series,
#     movies, search - all with First page / Jump / Next page (the site's "page/N/" and "?offset=N" pagers)
#   - movies and episodes are VIDEO rows keyed on their page url; the server list of "<page>/see/"
#     (ul#watch, data-watch) is read in getLinksForVideo and handed to urlparser
#   - series -> episodes (ascending); watched flag (series:/video: page-path keys), downloaded flag,
#     favourites, name normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta +
#     the site's story/poster/fields; no blocking retry loops, no colour codes in titles
#   - posters carry the cf_clearance cookie + User-Agent (getFullIconUrl); default icon = bundled logo
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://we.3isq.cam/"


COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")
# Arabic ordinals used in season labels ("الموسم الثاني")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالث", 3), ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8),
    ("التاسع", 9), ("العاشر", 10),
]
SEASON_WORD_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"^(.*?)\s*الحلقة\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s)((?:19|20)\d{2})(?=\s|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|مدبلج|مدبلجة|اون لاين|أون لاين|مشاهدة|وتحميل|فيلم|مسلسل|كامل|كاملة|HD)(?=\s|$)")
# "<div class="tax"><span>الأنواع : </span><a>..</a>" blocks -> INFO keys
TAX_FIELDS = {"الأنواع": "genres", "الممثلين": "actors", "السنة": "year", "اللغة": "language", "الحالة": "status", "التصنيفات": "category"}


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


def _seasonNum(text):
    m = SEASON_WORD_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


def _clean(text):
    text = JUNK_RE.sub(" ", JUNK_RE.sub(" ", text or ""))
    return re.sub(r"\s+", " ", text).strip(" -:|")


class Q3isk(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "q3isk", "cookie": "q3isk.cookie"})
        self.MAIN_URL = gettytul()
        # the site's logo sits behind the Cloudflare check too: the main menu is drawn before any page
        # request has stored a cf_clearance cookie, so its download got a 403 - the bundled logo instead
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/q3isk135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "list_items", "title": _("Latest episodes"), "url": self.getFullUrl("/آخر-الحلقات-hfgrtjf/")},
            {"category": "list_items", "title": _("Recently added"), "url": self.getFullUrl("/last/")},
            {"category": "list_items", "title": _("Most viewed"), "url": self.getFullUrl("/views/")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/series/"), "pager": "offset"},
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/movies/")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("q3isk")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def getFullUrl(self, url, currUrl=None):
        # menu urls are written in Arabic - one ASCII (percent-encoded) form for everything
        return self._quote(CBaseHostClass.getFullUrl(self, url, currUrl))

    @staticmethod
    def _quote(url):
        try:
            return urllib_quote(urllib_unquote(url.replace("&amp;", "&").replace("&#038;", "&")), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _canonUrl(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return self._quote(url)

    def _path(self, url):
        # domain independent identity of a page (the site moves between *.3isq.cam sub-domains)
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def _icon(self, url):
        url = (url or "").strip()
        return self.getFullIconUrl(url) if url else ""

    def getFullIconUrl(self, url, currUrl=None):
        # the posters sit behind the same Cloudflare check as the pages: the icon download needs the
        # site's cf_clearance cookie and the User-Agent that passed the check, otherwise it gets a 403.
        # The meta is attached here because the host base runs every icon through getFullIconUrl again
        # (getFullUrl returns a plain str); covers on foreign domains stay plain
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http"):
            return url
        domain = self.up.getDomain(url).lower()
        if domain != "3isq.cam" and not domain.endswith(".3isq.cam"):
            return url
        meta = {"Referer": self.MAIN_URL}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("q3_video", "q3_series"):
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
            prefix = {"q3_video": "video", "q3_series": "series"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _episodeParams(self, label, url, icon, desc, normalize, fallbackShow="", episode=""):
        m = EPISODE_RE.search(label)
        show = _clean(m.group(1)) if m else ""
        episode = episode or (m.group(2) if m else "")
        season = _seasonNum(show) or 1
        show = _clean(SEASON_WORD_RE.sub(" ", show)) or fallbackShow or _clean(label)
        if normalize and episode:
            title = "%s - %s" % (show, formatSxxExx(season, episode))
        else:
            title = label
        return {"name": "category", "good_for_fav": True, "category": "q3_video", "title": title, "url": url, "icon": icon, "desc": desc,
                "s_title": show, "s_season": season, "s_episode": str(int(episode)) if episode else "", "meta_type": "tv", "meta_title": show}

    def _movieParams(self, label, url, icon, desc, normalize):
        title = _clean(label) or label
        year = YEAR_RE.search(title)
        year = year.group(1) if year else ""
        metaTitle = _clean(YEAR_RE.sub(" ", title)) or title
        dispTitle = label
        if normalize:
            dispTitle = "%s (%s)" % (metaTitle, year) if year else metaTitle
        return {"name": "category", "good_for_fav": True, "category": "q3_video", "title": dispTitle, "url": url, "icon": icon, "desc": desc,
                "meta_type": "movie", "meta_title": metaTitle, "meta_year": year}

    def _boxes(self, data):
        # (url, label, icon, episode number) of the <div class="Small--Box"> cards
        out = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenNodes(data, ("<div", ">", "Small--Box"), ("</a", ">")):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            if not href:
                continue
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="title">(.*?)</div>')[0])
            if not label:
                label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            label = re.sub(r"\s*(?:اون لاين|أون لاين)\s*$", "", label).strip()
            if not label:
                continue
            number = self.cm.ph.getSearchGroups(item, r'<div class="number">.*?<em>\s*(\d+)\s*</em>')[0]
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+?(?:data-src|src)="([^"]+)"')[0]
            out.append((url, label, self._icon(icon), number))
        return out

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem["url"])
        pageTpl = cItem.get("page_tpl") or self._pageTpl(baseUrl, cItem.get("pager", ""))
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("Q3isk.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", 'id="MainFiltar"'), ("<div", ">", 'class="pagination"'), False)[1] or data
        normalize = IsMediaNamingNormalized()
        boxes = self._boxes(block)
        for url, label, icon, number in boxes:
            path = self._path(url)
            if path.startswith("/series/"):
                show = _clean(label) or label
                self.addDir({"name": "category", "good_for_fav": True, "category": "q3_series", "title": show if normalize else label, "url": url,
                             "icon": icon, "s_title": show, "meta_type": "tv", "meta_title": show})
            elif number or "الحلقة" in label:
                self.addVideo(self._episodeParams(label, url, icon, "", normalize, episode=number))
            else:
                self.addVideo(self._movieParams(label, url, icon, "", normalize))

        pager = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", 'class="pagination"'), ("</ul", ">"), False)[1]
        lastPage = max([int(n) for n in re.findall(r'class="page-numbers"[^>]*>\s*(\d+)\s*<', pager)] + [page])
        hasNext = bool(boxes) and ("next page-numbers" in pager or lastPage > page)
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl, "page_tpl": pageTpl})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    @staticmethod
    def _pageTpl(baseUrl, pager):
        if pager == "offset":
            return baseUrl.split("?", 1)[0] + "?offset={page}"
        base, sep, query = baseUrl.partition("?")
        if not base.endswith("/"):
            base += "/"
        return base + "page/{page}/" + sep + query

    def listEpisodes(self, cItem):
        printDBG("Q3isk.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", 'id="MainFiltar"'), ("<footer", ">"), False)[1] or data
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        episodes = []
        for url, label, icon, number in self._boxes(block):
            if self._path(url).startswith("/series/"):
                continue
            params = self._episodeParams(label, url, icon or cItem.get("icon", ""), cItem.get("desc", ""), normalize, show, number)
            params.update({"s_title": show, "meta_title": cItem.get("meta_title", show)})
            if normalize and params["s_episode"]:
                params["title"] = "%s - %s" % (show, formatSxxExx(params["s_season"], params["s_episode"]))
            episodes.append(params)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No episodes found."))
        # the site lists the newest first
        episodes.sort(key=lambda p: int(p["s_episode"]) if p["s_episode"] else 0)
        for params in episodes:
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Q3isk.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        query = urllib_quote(searchPattern.strip(), safe="")
        baseUrl = self.getFullUrl("/?s=%s" % query)
        cItem.update({"category": "list_items", "url": baseUrl, "base_url": baseUrl, "page_tpl": self.MAIN_URL + "page/{page}/?s=" + query, "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="story">(.*?)</div>')[0])
        story = re.sub(r"^.*?(?:الاصلي|الأصلي)\s*3isq\.\s*", "", story).strip()
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        info = {}
        for block in self.cm.ph.getAllItemsBeetwenNodes(data, ("<div", ">", 'class="tax"'), ("</div", ">"), False):
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"<span>([^<]+)</span>")[0]).replace(":", "").strip()
            values = [self.cleanHtmlStr(v) for v in re.findall(r"(?s)<a[^>]*>(.*?)</a>", block)]
            values = ", ".join(v for v in values if v)
            if label in TAX_FIELDS and values:
                info[TAX_FIELDS[label]] = values
        return story, self._icon(poster) if poster else "", info

    def getLinksForVideo(self, cItem):
        pageUrl = self._canonUrl(cItem.get("url", ""))
        printDBG("Q3isk.getLinksForVideo [%s]" % pageUrl)
        if not pageUrl:
            return []
        watchUrl = pageUrl if pageUrl.rstrip("/").endswith("/see") else pageUrl.rstrip("/") + "/see/"
        sts, data = self.getPage(watchUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="watch">', "</ul>", False)[1]
        urltab = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            url = self.cm.ph.getSearchGroups(item, r'data-watch="([^"]+)"')[0].replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<em>", "</em>", False)[1]) or self.up.getHostName(url)
            urltab.append({"name": name, "url": url, "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("Q3isk.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Q3isk.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        year = cItem.get("meta_year", "") or info.get("year", "")
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], year)
            except Exception:
                printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or _stripColors(cItem.get("desc", ""))
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
        printDBG("Q3isk.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "q3_series":
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
        CHostBase.__init__(self, Q3isk(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("q3isk")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("q3_video", "q3_series")
