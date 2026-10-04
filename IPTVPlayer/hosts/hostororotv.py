# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - revival + rewrite for today's ororo.tv
#   Without an account ororo.tv only offers its "Channels": ~60 YouTube channels (TED, Kurzgesagt, BBC Learning
#   English ...) with ororo's own English subtitles. TV shows / movies need a paid subscription and are left out.
#   /en/channels (JSON with Accept: application/json), /en/channels/<slug>?page=N&sort=published_at|views|title
#   (20 videos per page), /en/channels/<slug>/videos/<id> = player fragment with the YouTube url + VTT <track>s.
#   Search = /api/frontend/search?query= (matches channel names). The YouTube url goes to urlparser, ororo's
#   subtitles are attached to every resolved link. + watched flag / downloaded flag / sidecar / favourites /
#   paging (First / Jump / Next from total_count).
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://ororo.tv/"


PAGE_SIZE = 20
CHANNEL_RE = re.compile(r'/channels/([^/?#]+)')


class OroroTV(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "slug", "sort", "page", "ch_title", "icon")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "ororo.tv", "cookie": "ororo.tv.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.JSON_HEADER = dict(self.HEADER)
        self.JSON_HEADER.update({"Accept": "application/json, text/plain, */*", "X-Requested-With": "XMLHttpRequest"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_channels", "title": _("Channels"), "url": self.getFullUrl("en/channels")}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("ororotv")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                url = str(cItem.get("url", "") or "").strip()
                return "video:%s" % url if url else ""
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _getJson(self, url):
        params = dict(self.defaultParams)
        params["header"] = dict(self.JSON_HEADER)
        params["header"]["Referer"] = self.MAIN_URL
        sts, data = self.getPage(url, params)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG("OroroTV._getJson: no JSON from %s" % url)
        return None

    ###################################################
    # lists
    ###################################################
    def _addChannel(self, cItem, item):
        slug = item.get("slug", "")
        if not slug:
            m = CHANNEL_RE.search(item.get("url", "") or "")
            slug = m.group(1) if m else ""
        title = self.cleanHtmlStr(item.get("title", ""))
        if not slug or not title:
            return
        desc = []
        if item.get("videos_count"):
            desc.append("%s: %s" % (_("Videos"), item["videos_count"]))
        tags = ", ".join(item.get("parsed_tags") or [])
        if tags:
            desc.append(tags)
        if item.get("description"):
            desc.append(self.cleanHtmlStr(item["description"]))
        params = dict(cItem)
        params.update({"good_for_fav": True, "category": "list_sort", "title": title, "slug": slug,
                       "url": self.getFullUrl("en/channels/%s" % slug), "desc": "[/br]".join(desc),
                       "icon": item.get("image", "") or item.get("banner", "")})
        self.addDir(params)

    def listChannels(self, cItem):
        printDBG("OroroTV.listChannels")
        data = self._getJson(cItem["url"])
        if not isinstance(data, dict):
            return
        for item in data.get("items") or []:
            if isinstance(item, dict):
                self._addChannel(cItem, item)

    def listSort(self, cItem):
        tab = [{"title": _("Latest"), "sort": "published_at"},
               {"title": _("Most popular"), "sort": "views"},
               {"title": _("Alphabetically"), "sort": "title"}]
        for t in tab:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_videos", "title": t["title"], "sort": t["sort"], "page": 1,
                           "ch_title": cItem.get("title", "")})
            self.addDir(params)

    def listVideos(self, cItem):
        printDBG("OroroTV.listVideos |%s| page %s" % (cItem.get("slug", ""), cItem.get("page", 1)))
        page = int(cItem.get("page", 1) or 1)
        slug = cItem["slug"]
        tpl = self.getFullUrl("en/channels/%s?page={page}&sort=%s" % (slug, cItem.get("sort", "published_at")))
        data = self._getJson(tpl.format(page=page))
        if not isinstance(data, dict):
            return
        items = data.get("items") or []
        chTitle = cItem.get("ch_title", "")
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            title = self.cleanHtmlStr(item.get("title", ""))
            if not title:
                continue
            desc = [t for t in (item.get("airdate", ""), chTitle) if t]
            desc = " | ".join(desc)
            if item.get("description"):
                desc += "[/br]" + self.cleanHtmlStr(item["description"])
            ytId = item.get("youtube_id", "")
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "ororo_video", "title": title, "desc": desc,
                           "url": self.getFullUrl("en/channels/%s/videos/%s" % (slug, item["id"])),
                           "icon": "https://i.ytimg.com/vi/%s/hqdefault.jpg" % ytId if ytId else cItem.get("icon", "")})
            self.addVideo(params)
        try:
            total = int(data.get("total_count") or 0)
        except (TypeError, ValueError):
            total = 0
        lastPage = (total + PAGE_SIZE - 1) // PAGE_SIZE if total > 0 else 0
        addPagingItems(self, cItem, page, bool(items) and page < lastPage, lastPage, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("OroroTV.listSearchResult [%s]" % searchPattern)
        params = dict(self.defaultParams)
        params["header"] = dict(self.JSON_HEADER)
        sts, data = self.getPage(self.getFullUrl("api/frontend/search?query=%s" % urllib_quote_plus(searchPattern)), params)
        if not sts:
            return
        # JSON (channel objects) when asked with Accept: application/json, an HTML snippet otherwise
        if data.lstrip().startswith("["):
            try:
                for item in json_loads(data):
                    if isinstance(item, dict):
                        self._addChannel(cItem, item)
            except Exception:
                printExc()
            return
        for item in re.findall(r"<a class='search-results-item'(.*?)</a>", data, re.DOTALL):
            href = self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]+)['"]''')[0]
            slug = CHANNEL_RE.search(href)
            if not slug or "/videos/" in href:
                continue
            texts = [self.cleanHtmlStr(t) for t in re.findall(r'<p[^>]*>(.*?)</p>', item, re.DOTALL)]
            title = texts[0] if texts else ""
            icon = self.cm.ph.getSearchGroups(item, r'''src=['"]([^'"]+)['"]''')[0]
            self._addChannel(cItem, {"slug": slug.group(1), "title": title, "image": icon, "description": " ".join(texts[1:])})

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("OroroTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        if not self.cm.isValidUrl(url):
            return []
        params = dict(self.defaultParams)
        params["header"] = dict(self.JSON_HEADER)
        params["header"]["Referer"] = self.getFullUrl("en/channels/%s" % cItem.get("slug", ""))
        sts, data = self.getPage(url, params)
        if not sts:
            return []
        if "paid_access" in data and "<source" not in data:
            SetIPTVPlayerLastHostError(_("This video needs a paid ororo.tv subscription."))
            return []
        video = self.cm.ph.getDataBeetwenMarkers(data, "<video", "</video>")[1]
        subs = []
        seen = set()
        for track in re.findall(r'<track[^>]+>', data):
            src = self.cm.ph.getSearchGroups(track, r'''src=['"]([^'"]+)['"]''')[0]
            if not src or src in seen:
                continue
            seen.add(src)
            lang = self.cm.ph.getSearchGroups(track, r'''srclang=['"]([^'"]+)['"]''')[0]
            label = self.cm.ph.getSearchGroups(track, r'''label=['"]([^'"]+)['"]''')[0] or lang
            subs.append({"title": label, "url": self.getFullUrl(src), "lang": lang, "format": "vtt" if src.lower().endswith(".vtt") else "srt"})
        urltab = []
        for src, mime in re.findall(r'''<source[^>]+src=['"]([^'"]+)['"][^>]*type=['"]([^'"]+)['"]''', video):
            src = src.replace("&amp;", "&")
            if not self.cm.isValidUrl(src):
                continue
            meta = {"Referer": self.MAIN_URL}
            if subs:
                meta["external_sub_tracks"] = subs
            if "youtube" in mime or "youtu" in src:
                urltab.append({"name": "YouTube", "url": strwithmeta(src, meta), "need_resolve": 1})
            else:
                meta["User-Agent"] = self.HEADER["User-Agent"]
                if ".m3u8" in src:
                    meta["iptv_proto"] = "m3u8"
                urltab.append({"name": mime.split("/")[-1].upper() or "Video", "url": strwithmeta(src, meta), "need_resolve": 0})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("OroroTV.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        subs = videoUrl.meta.get("external_sub_tracks", []) if isinstance(videoUrl, strwithmeta) else []
        links = decorateResolvedLinkItems(self.up.getVideoLinkExt(str(videoUrl)), sidecar)
        if subs:
            for item in links:
                url = item.get("url", "")
                meta = dict(getattr(url, "meta", {}) or {})
                tracks = list(subs)
                tracks.extend(meta.get("external_sub_tracks", []) or [])
                meta["external_sub_tracks"] = tracks
                item["url"] = strwithmeta(str(url), meta)
        return links

    ###################################################
    # info
    ###################################################
    def getArticleContent(self, cItem):
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": cItem.get("desc", "").replace("[/br]", "\n"),
                 "images": [{"title": "", "url": icon}] if icon else [], "other_info": {}}]

    def getFavouriteData(self, cItem):
        # desc carries "4 years ago" / video counts, which change: keep only what identifies and reopens the row
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("OroroTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_channels":
            self.listChannels(self.currItem)
        elif category == "list_sort":
            self.listSort(self.currItem)
        elif category == "list_videos":
            self.listVideos(self.currItem)
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
        CHostBase.__init__(self, OroroTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("ororotv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "ororo_video"
