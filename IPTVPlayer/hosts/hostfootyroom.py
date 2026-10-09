# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# footyroom Host (Created By Dr HYTHAM MAHMOUD)
# FootyRoom (footyroom.co) - football highlights: latest, countries -> competitions -> matches, search.
#   Lists come from the site's own infinite-scroll endpoint /posts-pagelet?page=N (&stageTree=<competition id>,
#   &q=<search>), 24 matches a page, 404 after the last one. A match page carries its videos in DataStore.media
#   (YouTube, Dailymotion, ... -> urlparser) and the match data (venue, referee, round) in DataStore.match.
# 08.10.2026 - host standard: watched flag (country -> competition -> match), favourites (country/competition/
#   match rows reopen on their own), INFO from the match page, sidecar, download marker on the match url, date in
#   the name (naming option), search, First/Jump/Next page from the site instead of fetching up to 12 pages ahead,
#   kick-off times in the box's time zone (the site gives UTC)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError, TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
###################################################
# FOREIGN import
###################################################
import calendar
import re
import time
###################################################

PER_PAGE = 24


def GetConfigList():
    return []


def gettytul():
    return "FootyRoom"


class FootyRoom(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "footyroom.co", "cookie": "footyroom.co.cookie"})
        self.MAIN_URL = "https://footyroom.co/"
        self.DEFAULT_ICON_URL = "https://cdn.footyroom.co/pics/iphone/1024x1024.png"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HTTP_HEADER.update({"Referer": self.MAIN_URL})
        self.defaultParams = {"header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("footyroom")
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _absoluteUrl(self, url):
        url = (url or "").strip()
        if not url or url.startswith("javascript:"):
            return ""
        return self.getFullUrl(url)

    @staticmethod
    def _localTime(utcDate):
        # "2026-10-08T00:30" / "2026-10-08 00:30" in UTC -> "2026-10-08 02:30" in the box's time zone
        try:
            t = calendar.timegm(time.strptime(utcDate[:16].replace("T", " "), "%Y-%m-%d %H:%M"))
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(t))
        except Exception:
            return utcDate[:16]

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("search_item") or cItem.get("name") == "history":
                return ""
            if cItem.get("type") == "video":
                matchId = self.cm.ph.getSearchGroups(cItem.get("url", ""), r"/matches/(\d+)")[0]
                return "video:match:%s" % matchId if matchId else ""
            if cItem.get("category") == "list_matches" and cItem.get("stage_id"):
                return "folder:competition:%s" % cItem["stage_id"]
            if cItem.get("category") == "list_competitions" and cItem.get("title"):
                return "folder:country:%s" % cItem["title"]
        except Exception:
            printExc()
        return ""

    ###################################################
    # menus
    ###################################################
    def _parseCountries(self, data):
        """the "All leagues" menu of the main page: [(country, [(competition, url), ...]), ...]"""
        out = []
        try:
            nav = self.cm.ph.getDataBeetwenMarkers(data, '<nav class="dropdown-nav all-leagues', "</nav>")[1] or data
            for ul in self.cm.ph.getAllItemsBeetwenMarkers(nav, '<ul class="all-leagues-section', "</ul>"):
                country = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(ul, '<li class="all-leagues-header', "</li>")[1])
                comps = []
                for href, title in re.findall(r"""<a[^>]+href=['"]([^'"]+/competitions/\d+[^'"]*)['"][^>]*>(.*?)</a>""", ul, re.S):
                    title = self.cleanHtmlStr(title)
                    if title:
                        comps.append((title, self._absoluteUrl(href)))
                if country and comps:
                    out.append((country, comps))
        except Exception:
            printExc()
        return out

    def listMain(self, cItem):
        params = dict(cItem)
        params.update({"good_for_fav": True, "category": "list_matches", "title": _("Latest highlights")})
        self.addDir(params)
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            for country, comps in self._parseCountries(data):
                params = dict(cItem)
                # the competitions travel with the row, so a favourite reopens without the main page
                params.update({"good_for_fav": True, "category": "list_competitions", "title": country, "comps": comps})
                self.addDir(params)
        self.listsTab(self.searchItems(), cItem)

    def listCompetitions(self, cItem):
        for title, url in cItem.get("comps", []):
            stageId = self.cm.ph.getSearchGroups(url, r"/competitions/(\d+)")[0]
            if not stageId:
                continue
            params = stripPagerKeys(dict(cItem), ("comps",))
            params.update({"good_for_fav": True, "category": "list_matches", "title": title, "url": url, "stage_id": stageId})
            self.addDir(params)

    ###################################################
    # matches
    ###################################################
    def _pageletUrl(self, cItem, page):
        url = self.getFullUrl("/posts-pagelet?page=%s" % page)
        if cItem.get("stage_id"):
            url += "&stageTree=%s" % cItem["stage_id"]
        if cItem.get("search_pattern"):
            url += "&q=%s" % urllib_quote_plus(cItem["search_pattern"])
        return url

    def listMatches(self, cItem):
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        url = self._pageletUrl(cItem, page)
        printDBG("FootyRoom.listMatches [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = 0
        for card in data.split('class="col-xs-12 col-ms-6 col-md-4 card card--match"')[1:]:
            url = self._absoluteUrl(self.cm.ph.getSearchGroups(card, r"""href=['"]([^'"]*/matches/\d+/[^'"]*)['"]""")[0]).split("?")[0]
            if not url:
                continue
            count += 1
            # the title without the score (the site's "no spoilers" label), the score is in INFO
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'class="not-spoiler"[^>]*>(.*?)</a>')[0])
            title = title or self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'class="spoiler"[^>]*>(.*?)</a>')[0])
            title = title or url.split("/matches/")[-1].split("/")[1].replace("-", " ")
            icon = self._absoluteUrl(self.cm.ph.getSearchGroups(card, r'<img[^>]+src="([^"]+)"')[0])
            competition = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'class="card-category"[^>]*>(.*?)</a>')[0])
            date = self.cm.ph.getSearchGroups(card, r'date="(\d{4}-\d\d-\d\d)T(\d\d:\d\d)', 2)
            date = self._localTime("%s %s" % tuple(date)) if date[0] else ""
            views = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(card, ("<div", ">", "views-count"), ("</div", ">"), False)[1])
            descTab = [x for x in (date, competition) if x]
            if views:
                descTab.append(_("%s views") % views)
            params = stripPagerKeys(dict(cItem), ("comps", "search_pattern", "stage_id"))
            params.update({"good_for_fav": True, "category": "video", "title": normalizeMediathekTitle(title, date=date[:10]), "raw_title": title,
                           "url": url, "icon": icon or self.DEFAULT_ICON_URL, "date": date, "competition": competition, "desc": " | ".join(descTab)})
            self.addVideo(params)
        tpl = self._pageletUrl(cItem, "{page}")
        addPagingItems(self, cItem, page, count >= PER_PAGE, 0, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FootyRoom.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_matches", "search_pattern": searchPattern})
        self.listMatches(cItem)

    ###################################################
    # links
    ###################################################
    def _media(self, data):
        try:
            media = json_loads(self.cm.ph.getSearchGroups(data, r"DataStore\.media\s*=\s*(\[.*?\]);?[ \t]*\n")[0] or "[]")
            return media if isinstance(media, list) else []
        except Exception:
            printExc()
        return []

    def getLinksForVideo(self, cItem):
        printDBG("FootyRoom.getLinksForVideo [%s]" % cItem["url"])
        urlTab = []
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return urlTab
        for item in self._media(data):
            if not isinstance(item, dict):
                continue
            src = (item.get("source") or "").strip()
            if not src or "photo-resources" in src or re.search(r"\.(?:jpe?g|png|gif|webp)(?:\?|$)", src, re.I):
                continue
            vid = self.cm.ph.getSearchGroups(src, r"(?:youtu\.be/|youtube\.com/(?:embed/|watch\?v=|shorts/))([A-Za-z0-9_-]{11})")[0]
            if vid:
                src = "https://www.youtube.com/watch?v=" + vid
            name = "%s: %s" % ((item.get("provider") or self.up.getHostName(src)).strip(), (item.get("title") or "Video").strip()[:50])
            urlTab.append({"name": name, "url": self._absoluteUrl(src), "need_resolve": 1})
        if not urlTab:
            # older match pages: only the JSON-LD embed
            embed = self.cm.ph.getSearchGroups(data, r'"embedUrl"\s*:\s*"([^"]+)"')[0].replace("\\/", "/")
            if embed:
                urlTab.append({"name": self.up.getHostName(embed), "url": embed.replace("/embed/", "/watch?v=") if "youtube" in embed else embed, "need_resolve": 1})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, url):
        printDBG("FootyRoom.getVideoLinks [%s]" % url)
        sidecar = sidecarFromUrlMeta(url, IsSidecarEnabled())
        if 0 > self.up.checkHostSupport(url):
            SetIPTVPlayerLastHostError(_("Hosting \"%s\" not supported.") % self.up.getHostName(url))
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("FootyRoom.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("raw_title") or cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        other = {}
        if cItem.get("date"):
            other["released"] = cItem["date"]
        if cItem.get("competition"):
            other["category"] = cItem["competition"]
        sts, data = self.getPage(cItem["url"])
        if sts:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:title" content="([^"]+)"')[0]) or title
            text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]+)"')[0]) or text
            icon = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0] or icon
            try:
                match = json_loads(self.cm.ph.getSearchGroups(data, r"DataStore\.match\s*=\s*(\{.*?\});?[ \t]*\n")[0] or "{}")
            except Exception:
                printExc()
                match = {}
            if isinstance(match, dict) and match:
                lines = [text] if text else []
                home = (match.get("homeTeam") or {}).get("name", "")
                away = (match.get("awayTeam") or {}).get("name", "")
                if home and away and match.get("homeScore") is not None:
                    score = "%s %s - %s %s" % (home, match.get("homeScore"), match.get("awayScore"), away)
                    if match.get("homeScoreHT") is not None:
                        score += " (%s - %s)" % (match.get("homeScoreHT"), match.get("awayScoreHT"))
                    lines.append(score)
                for label, key in ((_("Venue"), "venueName"), (_("Referee"), "refereeName"), (_("Round"), "round")):
                    if match.get(key):
                        lines.append("%s: %s" % (label, match[key]))
                text = "[/br]".join(lines)
                if match.get("stage") and "category" in other:
                    other["category"] = "%s - %s" % (other["category"], match["stage"])
                dt = match.get("datetime") or {}
                date = (dt.get("date") or "")[:16]
                if date:
                    # {"date": "2026-10-08 00:30:00.000000", "timezone": "+00:00"}
                    other["released"] = self._localTime(date) if dt.get("timezone", "+00:00") in ("+00:00", "UTC", "Z") else date
        return [{"title": self.cleanHtmlStr(title), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("FootyRoom.handleService: name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({"name": "category"})
        elif category == "list_competitions":
            self.listCompetitions(self.currItem)
        elif category == "list_matches":
            self.listMatches(self.currItem)
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
        CHostBase.__init__(self, FootyRoom(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("footyroom")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video"
