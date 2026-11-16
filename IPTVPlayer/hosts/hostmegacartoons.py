# -*- coding: utf-8 -*-
LAST_MODIFIED = "16.11.2026"
# 16.11.2026 - new host for megacartoons.net (classic cartoon series, English): lists from the site's WordPress
#   REST API (its HTML lists come in a new random order on every request), the episode page holds a direct MP4
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetLocalPageSize, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://www.megacartoons.net/"


class MegaCartoons(GenericFolderWatchedScraperMixin, CBaseHostClass):
    PER_PAGE = 50
    POST_FIELDS = "id,date,link,title,excerpt,video-series,_links,_embedded"
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "post_id", "series_id", "s_title", "search_pattern")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "megacartoons", "cookie": "megacartoons.cookie"})
        self.MAIN_URL = gettytul()
        self.API = self.MAIN_URL + "wp-json/wp/v2/"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER["Referer"] = self.MAIN_URL
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.series = None
        self.MENU = [{"category": "list_series", "title": _("All series")},
                     {"category": "list_items", "title": _("Latest episodes"), "good_for_fav": True}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("megacartoons")
        self.wfInitFolderCache()

    def _json(self, url):
        # (json, X-WP-TotalPages)
        params = dict(self.defaultParams)
        params.update({"with_metadata": True, "collect_all_headers": True})
        sts, data = self.getPage(url, params)
        if not sts:
            return None, 0
        try:
            total = int((getattr(data, "meta", None) or {}).get("x-wp-totalpages", 0) or 0)
        except (TypeError, ValueError):
            total = 0
        try:
            return json_loads(data), total
        except Exception:
            printExc()
        return None, 0

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if not url:
                return ""
            if cItem.get("type") == "video":
                return "video:%s" % url
            if cItem.get("category") == "list_items" and cItem.get("series_id"):
                return "series:%s" % url
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        return self.getFavouriteFieldsData(cItem)

    ###################################################
    # helpers
    ###################################################
    def _seriesList(self):
        # {id: {"name", "slug", "count", "desc"}} of all series (31 on 16.11.2026, the site menu lists 30)
        if self.series is None:
            series = {}
            data, _total = self._json(self.API + "video-series?per_page=100&hide_empty=true&_fields=id,name,slug,count,description")
            for row in data if isinstance(data, list) else []:
                if isinstance(row, dict) and row.get("id"):
                    series[row["id"]] = {"name": self.cleanHtmlStr(row.get("name", "")), "slug": row.get("slug", ""),
                                         "count": row.get("count", 0), "desc": self.cleanHtmlStr(row.get("description", ""))}
            if series:
                self.series = series
            return series
        return self.series

    @staticmethod
    def _icon(post):
        try:
            media = (post.get("_embedded") or {}).get("wp:featuredmedia") or []
            media = media[0] if media and isinstance(media[0], dict) else {}
            sizes = (media.get("media_details") or {}).get("sizes") or {}
            for size in ("medium_large", "medium", "full"):
                if isinstance(sizes.get(size), dict) and sizes[size].get("source_url"):
                    return sizes[size]["source_url"]
            return media.get("source_url", "") or ""
        except Exception:
            printExc()
        return ""

    def _pageSize(self):
        # the "rows per page" setting; the REST API takes 1..100
        try:
            return min(100, max(1, int(GetLocalPageSize(self.PER_PAGE))))
        except Exception:
            return self.PER_PAGE

    def _plot(self, html):
        # the excerpts start with the player's "Loading the player..." text
        text = self.cleanHtmlStr(html or "")
        return re.sub(r"^Loading the player\W*", "", text).strip()

    def _postsUrl(self, cItem):
        url = "%sposts?per_page=%d&_embed=wp:featuredmedia&_fields=%s" % (self.API, self._pageSize(), self.POST_FIELDS)
        if cItem.get("series_id"):
            # the episodes of a series: A-Z (the site has no episode numbers)
            url += "&video-series=%s&orderby=title&order=asc" % cItem["series_id"]
        if cItem.get("search_pattern"):
            url += "&search=%s" % urllib_quote_plus(cItem["search_pattern"])
        return url

    ###################################################
    # lists
    ###################################################
    def _addSeries(self, sid, row):
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": row["name"], "s_title": row["name"],
                     "series_id": sid, "url": "%svideo-serie/%s/" % (self.MAIN_URL, row["slug"]),
                     "desc": "%s: %s" % (_("Episodes"), row["count"]) + ("[/br]" + row["desc"] if row["desc"] else "")})

    def listSeries(self, cItem):
        printDBG("MegaCartoons.listSeries")
        for sid, row in sorted(self._seriesList().items(), key=lambda s: s[1]["name"].lower()):
            if row["count"]:
                self._addSeries(sid, row)

    def listItems(self, cItem):
        printDBG("MegaCartoons.listItems [%s]" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        url = self._postsUrl(cItem)
        if page == 1 and cItem.get("search_pattern"):
            # series whose name matches come first
            pattern = cItem["search_pattern"].lower()
            for sid, row in sorted(self._seriesList().items(), key=lambda s: s[1]["name"].lower()):
                if row["count"] and pattern in row["name"].lower():
                    self._addSeries(sid, row)
        data, totalPages = self._json(url + "&page=%d" % page)
        if not isinstance(data, list):
            data = []
        series = self._seriesList()
        for post in data:
            try:
                link = post.get("link", "")
                name = self.cleanHtmlStr((post.get("title") or {}).get("rendered", ""))
                if not link or not name:
                    continue
                show = ""
                for sid in post.get("video-series") or []:
                    if sid in series:
                        show = series[sid]["name"]
                        break
                # "Show - Episode", as the site's own page titles (and the download file name)
                title = "%s - %s" % (show, name) if show and not name.lower().startswith(show.lower()) else name
                params = stripPagerKeys(dict(cItem))
                params.pop("search_pattern", None)
                params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": show, "url": link, "post_id": post.get("id", ""),
                               "icon": self._icon(post), "desc": self._plot((post.get("excerpt") or {}).get("rendered", ""))})
                self.addVideo(params)
            except Exception:
                printExc()
        if cItem.get("search_pattern") and not data and not self.currList and page == 1:
            SetIPTVPlayerLastHostError(_("No matching entries found."))
        hasNext = page < totalPages if totalPages else len(data) >= self._pageSize()
        # the page number drives the request; the template (the same API url) only gives Jump its target
        addPagingItems(self, cItem, page, bool(data) and hasNext, totalPages, url.replace("{", "{{").replace("}", "}}") + "&page={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MegaCartoons.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "search_pattern": searchPattern, "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("MegaCartoons.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        # <input type="hidden" name="main_video_url" value="https://ww.megacartoons.net/cartoons/<series>/<episode>.mp4"/>
        url = (self.cm.ph.getSearchGroups(data, r'''name=["']main_video_url["'][^>]*?value=["']([^"']+\.mp4[^"']*)["']''')[0]
               or self.cm.ph.getSearchGroups(data, r'''itemprop=["']contentUrl["'][^>]*?content=["']([^"']+)["']''')[0]
               or self.cm.ph.getSearchGroups(data, r'''file\s*:\s*["']([^"']+\.mp4[^"']*)["']''')[0])
        if not self.cm.isValidUrl(url):
            SetIPTVPlayerLastHostError(_("The video has been removed."))
            return []
        urltab = [{"name": "MegaCartoons MP4", "url": strwithmeta(url, {"Referer": cItem["url"], "User-Agent": self.HEADER["User-Agent"]}), "need_resolve": 0}]
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''og:description["']\s+content=["']([^"']+)["']''')[0]) or cItem.get("desc", "")
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), plot))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("MegaCartoons.getArticleContent [%s]" % cItem.get("url", ""))
        text, otherInfo = cItem.get("desc", ""), {}
        if cItem.get("post_id"):
            post, _total = self._json("%sposts/%s?_fields=id,date,content,video-series" % (self.API, cItem["post_id"]))
            if isinstance(post, dict):
                content = (post.get("content") or {}).get("rendered", "") or ""
                text = self._plot(content.replace("</p>", "[/br]")) or text
                if post.get("date"):
                    otherInfo["released"] = post["date"][:10]
        if cItem.get("s_title"):
            otherInfo["category"] = cItem["s_title"]
        icon = cItem.get("icon", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("MegaCartoons.handleService name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_series":
            self.listSeries(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, MegaCartoons(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("megacartoons")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video"
