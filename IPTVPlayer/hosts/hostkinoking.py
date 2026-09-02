# -*- coding: utf-8 -*-
# Last Modified: 02.09.2026 - rewrite for the redesigned kinoking.cc
#   (Tailwind "fav-data-source" cards; movie.php server picker via ?id=..&link=<key>
#    -> per-server <iframe> embed; series.php?id=..&season=.. -> inline
#    allEpisodesData JSON with video_links) + watched flag / sidecar / name norm.
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized


def GetConfigList():
    return []


def gettytul():
    return "https://kinoking.cc/"


class KinoKing(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "KinoKing", "cookie": "KinoKing.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "max_data_size": 1024 * 1024, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("index.php?genre=current-movies&filter=movies&view=grid&page=")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("index.php?genre=recently-added&filter=series&view=grid&page=")}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("kinoking")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if cItem.get("type", "") in ("video", "audio"):
                if category == "episode":
                    sid = str(cItem.get("s_id", "") or "").strip()
                    season = str(cItem.get("season", "") or "").strip()
                    epnum = str(cItem.get("ep_num", "") or "").strip()
                    if sid and epnum:
                        return "episode:%s|%s|%s" % (sid, season, epnum)
                    vl = str(cItem.get("video_links", "") or "").strip()
                    return "episode:%s" % vl if vl else ""
                url = str(cItem.get("url", "") or "").strip()
                return "video:%s" % url if url else ""
            if category == "kk_series":
                url = str(cItem.get("url", "") or "").strip()
                return "series:%s" % url if url else ""
            if category == "kk_season":
                url = str(cItem.get("url", "") or "").strip()
                return "season:%s" % url if url else ""
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listItems(self, cItem):
        printDBG("KinoKing.listItems |%s|" % cItem)
        url = cItem["url"]
        page = cItem.get("page", 1)
        isSearch = "search=" in url
        sts, data = self.getPage(url if isSearch else url + str(page))
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        cards = re.findall(r'<div class="[^"]*fav-data-source[^"]*"([^>]+)>', data)
        cnt = 0
        for attrs in cards:
            cid = self.cm.ph.getSearchGroups(attrs, r'data-id="(\d+)"')[0]
            ctype = self.cm.ph.getSearchGroups(attrs, r'data-type="([^"]+)"')[0]
            if cid == "" or ctype == "":
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(attrs, r'data-title="([^"]*)"')[0])
            icon = self.cm.ph.getSearchGroups(attrs, r'data-img="([^"]*)"')[0]
            quality = self.cm.ph.getSearchGroups(attrs, r'data-quality="([^"]*)"')[0]
            cnt += 1
            params = dict(cItem)
            params.pop("page", None)
            if ctype == "series":
                params.update({"good_for_fav": True, "category": "kk_series", "title": title, "s_id": cid,
                               "url": "%sseries.php?id=%s" % (self.MAIN_URL, cid), "icon": icon, "desc": ""})
                self.addDir(params)
            else:
                dispTitle = title if (normalize or not quality) else "%s [%s]" % (title, quality)
                params.update({"good_for_fav": True, "category": "movie", "title": dispTitle, "s_title": title,
                               "url": "%smovie.php?id=%s" % (self.MAIN_URL, cid), "icon": icon, "desc": ""})
                self.addVideo(params)
        if not isSearch and cnt >= 24:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": page + 1})
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("KinoKing.listSeasons")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)')[0])
        seasons = []
        for snum in re.findall(r'[?&]season=(\d+)', data):
            if snum not in seasons:
                seasons.append(snum)
        if not seasons:
            seasons = ["1"]
        for snum in seasons:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "kk_season", "title": "%s - %s %s" % (cItem["title"], _("Season"), snum),
                           "s_title": cItem["title"], "season": snum, "url": "%s&season=%s" % (cItem["url"], snum), "desc": desc})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("KinoKing.listEpisodes")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        m = re.search(r'allEpisodesData\s*=\s*(\[.*?\])\s*;', data, re.DOTALL)
        if not m:
            return
        try:
            episodes = json.loads(m.group(1))
        except Exception:
            printExc()
            return
        normalize = IsMediaNamingNormalized()
        sTitle = cItem.get("s_title", cItem["title"])
        wantSeason = str(cItem.get("season", "") or "").strip()
        for ep in episodes:
            if wantSeason and str(ep.get("season_number", "")).strip() != wantSeason:
                continue
            if not ep.get("video_links"):
                continue
            epName = self.cleanHtmlStr(ep.get("name", "") or "")
            tag = ""
            if normalize and ep.get("season_number") and ep.get("episode_number"):
                tag = formatSxxExx(ep["season_number"], ep["episode_number"])
            if tag and epName:
                title = "%s - %s - %s" % (sTitle, tag, epName)
            elif tag:
                title = "%s - %s" % (sTitle, tag)
            elif epName:
                title = "%s - %s" % (sTitle, epName)
            else:
                title = sTitle
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "episode", "title": title, "url": "",
                           "s_id": cItem.get("s_id", ""), "ep_num": ep.get("episode_number", ""),
                           "video_links": ep.get("video_links"), "desc": self.cleanHtmlStr(ep.get("overview", "") or "")})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KinoKing.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("index.php?search=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def _appendHosterLinks(self, urltab, raw, referer):
        for url in raw:
            url = url.strip()
            if url == "":
                continue
            url = "https:" + url if url.startswith("//") else url
            if not self.cm.isValidUrl(url):
                continue
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": referer}), "need_resolve": 1})

    def getLinksForVideo(self, cItem):
        printDBG("KinoKing.getLinksForVideo [%s]" % cItem)
        urltab = []
        sidecarTxt = cItem.get("desc", "")

        videoLinks = cItem.get("video_links")
        if videoLinks:
            # series episode - video_links is a hoster url (or a json list / separated list)
            raw = []
            try:
                parsed = json.loads(videoLinks)
                raw = parsed if isinstance(parsed, list) else [str(parsed)]
            except Exception:
                raw = re.split(r"[\s,;|]+", str(videoLinks))
            self._appendHosterLinks(urltab, raw, self.MAIN_URL)
        else:
            # movie - movie.php renders a server picker; each "?id=<id>&link=<key>"
            # variant swaps the player <iframe> to a different mirror. Collect them all.
            sts, data = self.getPage(cItem["url"], self.defaultParams)
            if not sts:
                return []
            if not sidecarTxt:
                sidecarTxt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)')[0])

            pages = [data]
            seenQs = set()
            for qs in re.findall(r'href="\?(id=\d+&(?:amp;)?link=[^"#]+)"', data):
                qs = qs.replace("&amp;", "&")
                if qs in seenQs:
                    continue
                seenQs.add(qs)
                if len(seenQs) > 10:
                    break
                sts2, data2 = self.getPage("%smovie.php?%s" % (self.MAIN_URL, qs), self.defaultParams)
                if sts2 and data2:
                    pages.append(data2)

            embeds = []
            for pg in pages:
                for frame in re.findall(r'<iframe[^>]+src="([^"]+)"', pg):
                    frame = frame.replace("&amp;", "&")
                    frame = "https:" + frame if frame.startswith("//") else frame
                    if frame not in embeds and self.cm.isValidUrl(frame):
                        embeds.append(frame)

            for frame in embeds:
                if "meinecloud.click" in frame and "/movie/" in frame:
                    mts, mdata = self.cm.getPage(frame, {"header": self.HEADER})
                    if mts and mdata:
                        subs = []
                        for sub in re.findall(r'data-link="([^"]+)"', mdata):
                            if "meinecloud" in sub or "/vod/" in sub:
                                continue
                            subs.append(sub)
                        self._appendHosterLinks(urltab, subs, "https://meinecloud.click/")
                elif re.search(r'(?:vidsync|cinesrc)\.', frame):
                    printDBG("KinoKing: aggregator embed uebersprungen [%s]" % frame)
                else:
                    self._appendHosterLinks(urltab, [frame], self.MAIN_URL)

        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("KinoKing.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("KinoKing.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "kk_series":
            self.listSeasons(self.currItem)
        elif category == "kk_season":
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
        CHostBase.__init__(self, KinoKing(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("kinoking")
