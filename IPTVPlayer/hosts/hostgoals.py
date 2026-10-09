# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# 27.02.2026 - by Mr.X
# Goals.Zone - football goal clips and highlights (JSON API of gogz.meneses.pt): latest matches, teams, search
#   (matches of the last week). A match lists its clips (goals, red cards ...), every clip has mirrors on
#   v.redd.it, streamin, streamain/streama.in, streamusk (expires after about a day) or streamff.
# 08.10.2026 - host standard: watched flag (team -> match -> clip), favourites, INFO, sidecar, download marker
#   per clip, date in the match name (naming option), First/Next page, team logos as covers; fixed the crash on
#   an empty search / team page, streamff via its share API, streamusk tells when a clip has expired, kick-off
#   times in the box's time zone (the API gives UTC), Jump on the paged lists
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError, TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
###################################################
# FOREIGN import
###################################################
import calendar
import time
###################################################

PER_PAGE = 50


def GetConfigList():
    return []


def gettytul():
    return "Goals.Zone"


class GoalsZoneAPI(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "GoalsZoneAPI", "cookie": "GoalsZoneAPI.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = "https://gogz.meneses.pt/"
        self.DEFAULT_ICON_URL = "https://h.top4top.io/p_3650w3uf91.png"
        self.watchedHelper = IPTVWatchedHelper("goals")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getJson(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("search_item") or cItem.get("name") == "history":
                return ""
            if cItem.get("type") == "video":
                return "video:%s" % cItem["url"] if cItem.get("url") else ""
            if cItem.get("category") == "list_clips" and cItem.get("match_slug"):
                return "folder:match:%s" % cItem["match_slug"]
            if cItem.get("category") == "list_matches" and cItem.get("team_slug"):
                return "folder:team:%s" % cItem["team_slug"]
        except Exception:
            printExc()
        return ""

    ###################################################
    # listing
    ###################################################
    def listMain(self, cItem):
        MENU = [{"category": "list_matches", "title": _("Latest"), "good_for_fav": True},
                {"category": "list_teams", "title": _("Teams"), "good_for_fav": True}]
        self.listsTab(MENU + self.searchItems(), cItem)

    def _page(self, cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _localTime(utcDate):
        # "2026-10-08T00:30:00Z" (UTC) -> "2026-10-08 02:30" in the box's time zone
        try:
            t = calendar.timegm(time.strptime(utcDate[:16].replace("T", " "), "%Y-%m-%d %H:%M"))
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(t))
        except Exception:
            return utcDate.replace("T", " ").replace("Z", "")[:16]

    def _matchTitle(self, item):
        home = (item.get("home_team") or {}).get("name") or ""
        away = (item.get("away_team") or {}).get("name") or ""
        return item.get("name") or ("%s %s %s" % (home, item.get("score") or "-", away)).strip()

    def listMatches(self, cItem):
        printDBG("GoalsZoneAPI.listMatches |%s|" % cItem)
        page = self._page(cItem)
        offset = (page - 1) * PER_PAGE
        if cItem.get("search_pattern"):
            listUrl = ""
            url = self.getFullUrl("api/matches-search-week/?filter=%s&format=json" % urllib_quote(cItem["search_pattern"]))
        elif cItem.get("team_slug"):
            listUrl = self.getFullUrl("api/teams/%s?format=json" % cItem["team_slug"])
            url = self.getFullUrl("api/teams/%s?limit=%d&offset=%d&format=json" % (cItem["team_slug"], PER_PAGE, offset))
        else:
            listUrl = self.getFullUrl("api/matches/?format=json")
            url = self.getFullUrl("api/matches/?limit=%d&offset=%d&format=json" % (PER_PAGE, offset))
        data = self.getJson(url)
        if isinstance(data, dict):
            data = data.get("matches")
        if not isinstance(data, list):
            data = []
        for item in data:
            slug = item.get("slug") or ""
            if not slug:
                continue
            title = self._matchTitle(item)
            date = self._localTime(item.get("datetime") or "")
            icon = (item.get("home_team") or {}).get("logo_file") or ""
            params = stripPagerKeys(dict(cItem), ("search_pattern", "team_slug"))
            params.update({"good_for_fav": True, "category": "list_clips", "title": normalizeMediathekTitle(title, date=date[:10]), "raw_title": title,
                           "match_slug": slug, "date": date, "url": self.getFullUrl("api/matches/%s?format=json" % slug), "icon": icon,
                           "desc": " | ".join([x for x in (date, title) if x])})
            self.addDir(params)
        if listUrl:
            # offset paging: listMatches builds the request from "page", the template only enables "Jump"
            addPagingItems(self, cItem, page, len(data) >= PER_PAGE, 0, listUrl)

    def listTeams(self, cItem):
        printDBG("GoalsZoneAPI.listTeams |%s|" % cItem)
        page = self._page(cItem)
        data = self.getJson(self.getFullUrl("api/teams/?limit=%d&offset=%d&format=json" % (PER_PAGE, (page - 1) * PER_PAGE)))
        if not isinstance(data, list):
            data = []
        for item in data:
            if not item.get("slug"):
                continue
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "list_matches", "title": item.get("name") or item["slug"], "team_slug": item["slug"],
                           "url": self.getFullUrl("api/teams/%s?format=json" % item["slug"]), "icon": item.get("logo_file") or "", "desc": ""})
            self.addDir(params)
        addPagingItems(self, cItem, page, len(data) >= PER_PAGE, 0, self.getFullUrl("api/teams/?format=json"))

    def listClips(self, cItem):
        printDBG("GoalsZoneAPI.listClips")
        data = self.getJson(self.getFullUrl("api/matches/%s?format=json" % cItem["match_slug"]))
        if not isinstance(data, dict):
            return
        matchTitle = cItem.get("raw_title") or self._matchTitle(data)
        for idx, item in enumerate(data.get("videos") or []):
            urls = [m.get("url") for m in item.get("mirrors") or [] if m.get("url")]
            if not urls:
                continue
            # a stable per-clip key (watched / downloaded): the reddit post, else the match + the clip's position
            key = item.get("reddit_link") or "%s#%d" % (cItem["match_slug"], idx)
            title = self.cleanHtmlStr(item.get("title") or "") or matchTitle
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "title": title, "raw_title": title, "match_title": matchTitle, "url": key, "urls": urls,
                           "desc": "[/br]".join([x for x in (cItem.get("date", ""), matchTitle, ", ".join(self.up.getHostName(u) for u in urls)) if x])})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GoalsZoneAPI.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_matches", "search_pattern": searchPattern})
        self.listMatches(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("GoalsZoneAPI.getLinksForVideo [%s]" % cItem)
        urltab = []
        for url in cItem.get("urls", []):
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": url}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, url):
        printDBG("GoalsZoneAPI.getVideoLinks [%s]" % url)
        sidecar = sidecarFromUrlMeta(url, IsSidecarEnabled())
        return decorateResolvedLinkItems(self._getVideoLinks(strwithmeta(url)), sidecar)

    def _getVideoLinks(self, url):
        urltab = []
        host = self.up.getDomain(url, False)
        streamHeaders = {"User-Agent": self.HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]}
        videoId = url.split("?")[0].rstrip("/").split("/")[-1]
        if "streamusk" in url:
            # the clips expire after about a day, the CDN answers 403 then
            data = self.getJson("https://api.streamusk.com/videos/%s" % videoId)
            if isinstance(data, dict) and data.get("status") in ("EXPIRED", "FAILED", "ERROR"):
                SetIPTVPlayerLastHostError(_("Content not available"))
                return []
            url = self.up.decorateUrl("https://d3ctycp5ce1kgh.cloudfront.net/videos/%s/video.m3u8" % videoId, streamHeaders)
            return getDirectM3U8Playlist(url, checkExt=False)
        if "streamff" in url:
            data = self.getJson("https://ffedge.streamff.com/share/" + videoId)
            item = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
            link = item.get("external_url") or ("https://ffedge.streamff.com/uploads/%s.mp4" % item["path"] if item.get("path") else "")
            if not link:
                SetIPTVPlayerLastHostError(_("Content not available"))
                return []
            return [{"name": "MP4", "url": self.up.decorateUrl(link, {"User-Agent": self.HEADER["User-Agent"], "Referer": "https://streamff.com/"})}]
        sts, data = self.getPage(url)
        if not sts:
            return []
        if "streamain" in url or "streama.in" in url:
            # the watch page lists other clips as well - the player is in the <iframe>
            frame = self.cm.ph.getSearchGroups(data, r'iframe\s*src="([^"]+)')[0]
            if frame:
                sts, data = self.getPage(frame)
                if not sts:
                    return []
        url = self.cm.ph.getSearchGroups(data, r"""["']((?:https?:)?//[^'^"]+?\.(?:mp4|m3u8|mkv)(?:\?[^"^']+?)?)["']""")[0]
        if not url:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        url = self.up.decorateUrl(self.getFullUrl(url.replace("amp;", "")), streamHeaders)
        if ".m3u8" in url:
            urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
        else:
            urltab.append({"name": "MP4", "url": url})
        return urltab

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("GoalsZoneAPI.getArticleContent [%s]" % cItem)
        title = cItem.get("raw_title") or cItem.get("title", "")
        other = {}
        if cItem.get("date"):
            other["released"] = cItem["date"]
        lines = []
        if cItem.get("type") == "video":
            if cItem.get("match_title"):
                lines.append(cItem["match_title"])
            other["source"] = ", ".join(self.up.getHostName(u) for u in cItem.get("urls", []))
        else:
            # a match: its clips (goals, cards ...) as the text
            data = self.getJson(self.getFullUrl("api/matches/%s?format=json" % cItem.get("match_slug", "")))
            if isinstance(data, dict):
                for item in data.get("videos") or []:
                    if item.get("title"):
                        lines.append(self.cleanHtmlStr(item["title"]))
        icon = cItem.get("icon", "")
        return [{"title": self.cleanHtmlStr(title), "text": "[/br]".join(lines) or cItem.get("desc", ""), "images": [{"title": "", "url": icon}] if icon else [], "other_info": other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listMain({"name": "category"})
        elif category == "list_matches":
            self.listMatches(self.currItem)
        elif category == "list_teams":
            self.listTeams(self.currItem)
        elif category == "list_clips":
            self.listClips(self.currItem)
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
        CHostBase.__init__(self, GoalsZoneAPI(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("goals")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category") == "list_clips"
