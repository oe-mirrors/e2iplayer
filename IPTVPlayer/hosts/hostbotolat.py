# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - revived for the redesigned btolat.com (football clips / highlights)
#   - one card parser for all video lists (/videos "card xrow video" + LoadMore API, league/team pages
#     "categoryNewsCard", player pages "vcard xrow video"); relative "video/<id>" links; date from
#     data-date or the image path; "?p=" paging (First page / Jump / Next page) and LoadMore paging
#   - /leagues: new panel / tcard / acard layout -> league (all videos, top scorers, teams) -> team
#     (videos, squad) -> player videos; professionals without one request per player
#   - search: POST /api/data/search JSON through self.cm (the old /news/Search is gone; no "requests")
#   - links: YouTube (urlparser), Twitter/X syndication JSON (direct MP4/HLS), vortexvisionworks
#     /player/ embeds (HLS with Referer/Origin as strwithmeta meta); "blockedvideos" iframes are read
#     through the video's /embed/ page (still plays), only when that has no stream either -> "removed"
#     message instead of an empty list; no more botolat_<title>.iptv junk files
#   - watched flag (video:<id>), downloaded flag (stable /video/<id> page url), favourites, sidecar,
#     name normalisation "Title (YYYY-MM-DD)", INFO from the video / player / team page
import re
import time

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

# start of one video card in any of the site's list layouts
CARD_RE = re.compile(r'<(?:div|article)\s+class="(?:card xrow video|vcard xrow video|categoryNewsCard)[^"]*"[^>]*>')
VIDEO_CATS = ("bt_video",)


def GetConfigList():
    return []


def gettytul():
    return "https://www.btolat.com/"


class BtolatCom(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "raw_title", "icon", "desc", "date", "league", "duration")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "btolat.com", "cookie": "btolat.com.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://i.ibb.co/RkbWVvBZ/botolat.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept-Language": "ar,en-US;q=0.7,en;q=0.3", "Referer": self.MAIN_URL})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "bt_loadmore", "title": _("Latest videos"), "url": self.getFullUrl("/videos")},
            {"category": "bt_leagues", "title": _("Leagues"), "url": self.getFullUrl("/leagues")},
            {"category": "bt_professionals", "title": _("Professionals"), "url": self.getFullUrl("/professionals/video")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("botolat")
        self.wfInitFolderCache()
        self._twitterBlocked = False

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self.cm.iriToUri(baseUrl), addParams, post_data)

    def getFullIconUrl(self, url, currUrl=None):
        url = (url or "").strip()
        if url.startswith("//"):
            url = "https:" + url
        return CBaseHostClass.getFullIconUrl(self, url, currUrl) if url else ""

    def _videoUrl(self, vid):
        return self.MAIN_URL + "video/" + vid

    @staticmethod
    def _videoId(url):
        m = re.search(r"(?:^|/)video/(\d+)", url or "")
        return m.group(1) if m else ""

    @staticmethod
    def _date(rawDate, icon):
        # data-date "9/16/2026 12:12:00 AM" (M/D/Y, "1/1/0001" = unset) or the image path /2026/9/16/video/
        m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", rawDate or "")
        if m and m.group(3) != "0001":
            return "%s-%02d-%02d" % (m.group(3), int(m.group(1)), int(m.group(2)))
        m = re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})/(?:video|news)/", icon or "")
        if m:
            return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
        return ""

    def _title(self, title, date):
        if IsMediaNamingNormalized() and date and date not in title:
            return "%s (%s)" % (title, date)
        return title

    def _addVideoRow(self, title, vid, icon, date, league="", duration=""):
        desc = " | ".join(x for x in (league, date, duration) if x)
        self.addVideo({"name": "category", "good_for_fav": True, "category": "bt_video", "title": self._title(title, date), "raw_title": title,
                       "url": self._videoUrl(vid), "icon": self.getFullIconUrl(icon), "desc": desc, "date": date, "league": league, "duration": duration})

    def _parseCards(self, data):
        # -> number of video rows added, last card's (data-val, data-date) for the LoadMore API
        starts = [m.start() for m in CARD_RE.finditer(data)] + [len(data)]
        seen = set()
        last = ("", "")
        for idx in range(len(starts) - 1):
            block = data[starts[idx]:starts[idx + 1]]
            vid = self.cm.ph.getSearchGroups(block, r"""href=['"](?:https?://[^/'"]+)?/?video/(\d+)""")[0]
            if not vid:
                continue
            head = self.cm.ph.getSearchGroups(block, r"^(<[^>]+>)")[0]
            last = (self.cm.ph.getSearchGroups(head, r'data-val="(\d+)"')[0] or vid, self.cm.ph.getSearchGroups(head, r'data-date="([^"]*)"')[0])
            if vid in seen:
                continue
            seen.add(vid)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"(?s)<h3[^>]*>(.*?)</h3>")[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="info">\s*<b>(.*?)</b>')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0])
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(block, r'data-(?:src|original)="([^"]+)"')[0]
            league = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<a[^>]+class="(?:category|categoryTag|badge)"[^>]*>(.*?)</a>')[0])
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<span class="dur num">\s*(\d+:\d+(?::\d+)?)\s*</span>')[0])
            self._addVideoRow(title, vid, icon, self._date(last[1], icon), league, duration)
        return len(seen), last

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATS:
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("category", "") in VIDEO_CATS:
                vid = self._videoId(cItem.get("url", ""))
                return ("video:%s" % vid) if vid else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listLoadMore(self, cItem):
        # /videos (+ POST /api/video/LoadMore/0 with the last card's id for the next pages)
        page = cItem.get("page", 1)
        printDBG("BtolatCom.listLoadMore page[%s]" % page)
        if page <= 1:
            sts, data = self.getPage(cItem["url"])
        else:
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, **{"X-Requested-With": "XMLHttpRequest"})
            sts, data = self.getPage(self.getFullUrl("/api/video/LoadMore/0"), params, {"lastRowId": cItem.get("last_row_id", ""), "lasRowDate": cItem.get("last_row_date", "")})
            if sts:
                try:
                    data = (json_loads(data) or {}).get("html", "") or ""
                except Exception:
                    printExc()
                    data = ""
        if not sts:
            return
        count, last = self._parseCards(data)
        listItem = dict(cItem)
        listItem.update({"category": "bt_loadmore"})
        addPagingItems(self, listItem, page, bool(count and last[0]), 0, "", {"last_row_id": last[0], "last_row_date": last[1]})

    def listPaged(self, cItem):
        # league / team / player video pages with "?p=N"
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"].split("?")[0]
        url = baseUrl if page <= 1 else "%s?p=%d" % (baseUrl, page)
        printDBG("BtolatCom.listPaged [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = self._parseCards(data)[0]
        hasNext = bool(count) and 'class="next-page"' in data
        listItem = dict(cItem)
        listItem.update({"category": "bt_paged", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, 0, baseUrl + "?p={page}")

    def listLeagues(self, cItem):
        printDBG("BtolatCom.listLeagues")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for panel in data.split('<div class="panel')[1:]:
            head = self.cleanHtmlStr(self.cm.ph.getSearchGroups(panel, r'(?s)<h2 class="panel-title"[^>]*>(.*?)</h2>')[0])
            cards = re.findall(r'(?s)<a\s+[^>]*class="[tea]card"[^>]*>.*?</a>', panel)
            if not cards:
                continue
            if head:
                self.addMarker({"title": head, "desc": ""})
            for card in cards:
                href = self.cm.ph.getSearchGroups(card, r'href="(/league/\d+/[^"]+)"')[0]
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<span class="label">(.*?)</span>')[0])
                if not href or not title or href in seen:
                    continue
                seen.add(href)
                icon = self.cm.ph.getSearchGroups(card, r'<img[^>]+src="([^"]+)"')[0]
                self.addDir({"name": "category", "good_for_fav": True, "category": "bt_league", "title": title,
                             "url": self.getFullUrl(href), "icon": self.getFullIconUrl(icon)})

    def listLeague(self, cItem):
        # /league/<id>/<slug> -> all videos, top scorers, the league's teams
        url = cItem["url"]
        m = re.search(r"/league/(?:[a-z]+/)?(\d+)/([^/?#]+)", url)
        if not m:
            return
        lid, slug = m.group(1), m.group(2)
        videos = self.getFullUrl("/league/videos/%s/%s" % (lid, slug))
        base = {"name": "category", "good_for_fav": True, "icon": cItem.get("icon", "")}
        self.addDir(dict(base, category="bt_paged", title=_("All videos"), url=videos, base_url=videos))
        self.addDir(dict(base, category="bt_scorers", title=_("Top scorers"), url=self.getFullUrl("/league/topscores/%s/%s" % (lid, slug)), league_id=lid))
        sts, data = self.getPage(videos)
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="importantTeams', '<div class="clearfix', False)[1]
        teams = re.findall(r'(?s)<a href="(/team/\d+/[^"]+)" class="importantTeam">.*?<img[^>]+src="([^"]+)".*?<h3>(.*?)</h3>', block)
        if teams:
            self.addMarker({"title": _("Teams"), "desc": ""})
        for href, icon, name in teams:
            self.addDir({"name": "category", "good_for_fav": True, "category": "bt_team", "title": self.cleanHtmlStr(name),
                         "url": self.getFullUrl(href), "icon": self.getFullIconUrl(icon)})

    def listTeam(self, cItem):
        m = re.search(r"/team/(?:[a-z]+/)?(\d+)/([^/?#]+)", cItem["url"])
        if not m:
            return
        base = {"name": "category", "good_for_fav": True, "icon": cItem.get("icon", ""), "team_url": cItem["url"]}
        videos = self.getFullUrl("/team/videos/%s/%s" % m.groups())
        self.addDir(dict(base, category="bt_paged", title="%s - %s" % (cItem.get("title", ""), _("Videos")), url=videos, base_url=videos))
        self.addDir(dict(base, category="bt_squad", title="%s - %s" % (cItem.get("title", ""), _("Squad")), url=self.getFullUrl("/team/squad/%s/%s" % m.groups())))

    def _playerDir(self, href, name, icon, desc=""):
        m = re.search(r"/player/(?:[a-z]+/)?(\d+)/([^/?#\"]+)", href)
        if not m:
            return
        videos = self.getFullUrl("/player/videos/%s/%s" % m.groups())
        self.addDir({"name": "category", "good_for_fav": True, "category": "bt_paged", "title": name, "url": videos, "base_url": videos,
                     "player_url": self.getFullUrl("/player/%s/%s" % m.groups()), "icon": self.getFullIconUrl(icon), "desc": desc})

    def listSquad(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getSearchGroups(data, r"(?s)<table[^>]+squadTable[^>]*>(.*?)</table>")[0]
        for row in re.findall(r"(?s)<tr>(.*?)</tr>", block):
            m = re.search(r'(?s)<a href="([^"]+/player/[^"]+)"[^>]*>\s*<img[^>]+src="([^"]+)"[^>]*>(.*?)</a>', row)
            if not m:
                continue
            name = self.cleanHtmlStr(m.group(3))
            number = self.cleanHtmlStr(self.cm.ph.getSearchGroups(row, r"(?s)<i[^>]*>(.*?)</i>")[0])
            cols = [self.cleanHtmlStr(c) for c in re.findall(r"(?s)<span>(.*?)</span>", row)]
            desc = " | ".join(x for x in ([("#" + number) if number else ""] + cols) if x)
            self._playerDir(m.group(1), name, m.group(2), desc)

    def listScorers(self, cItem):
        page = cItem.get("page", 1)
        lid = cItem.get("league_id", "")
        if page <= 1:
            sts, data = self.getPage(cItem["url"])
        else:
            sts, data = self.getPage(self.getFullUrl("/league/TopScoresLoadMore/%s/aa" % lid), None, {"Id": lid, "lastPosition": cItem.get("last_position", 0)})
            if sts:
                try:
                    js = json_loads(data) or {}
                    data = js.get("html", "") if js.get("success") else ""
                except Exception:
                    printExc()
                    data = ""
        if not sts:
            return
        last = 0
        for pos, row in re.findall(r'(?s)<tr data-position="(\d+)">(.*?)</tr>', data):
            m = re.search(r'(?s)<a href="(/player/[^"]+)">\s*<img[^>]+src="([^"]+)".*?<b>(.*?)</b>', row)
            if not m:
                continue
            team = self.cleanHtmlStr(self.cm.ph.getSearchGroups(row, r'(?s)<a href="/team/[^"]+">.*?<b>(.*?)</b>')[0])
            goals = self.cm.ph.getSearchGroups(row, r"<span>\s*(\d+)\s*</span>")[0]
            name = self.cleanHtmlStr(m.group(3))
            title = "%s. %s" % (pos, name) + (" - %s" % team if team else "") + (" (%s %s)" % (goals, _("goals")) if goals else "")
            self._playerDir(m.group(1), title, m.group(2), team)
            last = int(pos)
        total = int(self.cm.ph.getSearchGroups(data, r'data-total="(\d+)"')[0] or cItem.get("total", 0) or 0)
        if last and (not total or last < total):
            listItem = dict(cItem)
            addPagingItems(self, listItem, page, True, 0, "", {"last_position": last, "total": total})

    def listProfessionals(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="carouselContainer"', "</section>", False)[1] or data
        for href, icon, name in re.findall(r'(?s)<a href="(/player/\d+/[^"]+)" class="importantTeam">\s*<img[^>]+src="([^"]+)"[^>]*>\s*<h3>(.*?)</h3>', block):
            self._playerDir(href, self.cleanHtmlStr(name), icon)
        # the site's "more" button for this list loads the general video feed - only the first page here
        self._parseCards(data)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("BtolatCom.listSearchResult [%s]" % searchPattern)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, **{"Content-Type": "application/json; charset=utf-8", "Accept": "application/json, */*", "X-Requested-With": "XMLHttpRequest"})
        params["raw_post_data"] = True
        sts, data = self.getPage(self.getFullUrl("/api/data/search"), params, json_dumps({"word": searchPattern.strip()}))
        if not sts:
            return
        try:
            items = json_loads(data) or []
        except Exception:
            printExc()
            return
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            vid = self.cm.ph.getSearchGroups(item.get("SeName", "") or "", r"^video/(\d+)")[0]
            title = self.cleanHtmlStr(item.get("Title", "") or "")
            if not vid or not title:
                continue
            icon = item.get("FullSizeImageUrl", "") or ""
            date = self._date("", icon)
            ms = self.cm.ph.getSearchGroups(str(item.get("CreatedOn", "")), r"Date\((\d+)\)")[0]
            if ms:
                try:
                    date = time.strftime("%Y-%m-%d", time.gmtime(int(ms) // 1000 + 3 * 3600))
                except Exception:
                    printExc()
            self._addVideoRow(title, vid, icon, date)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("BtolatCom.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "").strip()
        sts, data = self.getPage(url)
        if not sts:
            return []
        links = []
        blocked = False
        self._twitterBlocked = False
        # YouTube
        for ytid in re.findall(r"youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{11})", data):
            link = "https://www.youtube.com/watch?v=%s" % ytid
            if link not in [x["url"] for x in links]:
                links.append({"name": "YouTube", "url": link, "need_resolve": 1})
        # Twitter / X (blockquote + widgets.js) -> syndication JSON
        tweet = self.cm.ph.getSearchGroups(data, r"(?:twitter|x)\.com/[^/\"'\s]+/status/(\d+)")[0]
        if tweet:
            links.extend(self._twitterLinks(tweet))
        # vortexvisionworks embeds: the page often shows "/player/blockedvideos/<id>" ("Video Removed")
        # while the same video's "/embed/<id>" page (the JSON-LD embedURL) still plays - only when that
        # one has no stream either the video is really gone
        for embed in re.findall(r"""<iframe[^>]+src=["']((?:https?:)?//[^"']*vortexvisionworks\.com/[^"']+)["']""", data):
            embed = embed if embed.startswith("http") else "https:" + embed
            isBlocked = "/blockedvideos/" in embed
            if isBlocked:
                embed = embed.replace("/player/blockedvideos/", "/embed/")
            found = self._vortexLinks(embed)
            blocked = blocked or (isBlocked and not found)
            links.extend(found)
        # any other hoster iframe urlparser knows
        if not links:
            for embed in re.findall(r"""<iframe[^>]+src=["']((?:https?:)?//[^"']+)["']""", data):
                embed = embed if embed.startswith("http") else "https:" + embed
                if "googletagmanager" in embed or "vortexvisionworks" in embed:
                    continue
                if self.up.checkHostSupport(embed) == 1:
                    links.append({"name": self.up.getDomain(embed), "url": strwithmeta(embed, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not links:
            if blocked:
                msg = _("This video has been deleted.")
            elif self._twitterBlocked:
                msg = _("This content is not available in your region.")
            else:
                msg = _("No stream available")
            SetIPTVPlayerLastHostError(msg)
            return []
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def _twitterLinks(self, tweetId):
        jsonUrl = "https://cdn.syndication.twimg.com/tweet-result?id=%s&lang=ar&token=4ufmaqlvqaj" % tweetId
        sts, data = self.getPage(jsonUrl)
        if not sts:
            return []
        try:
            js = json_loads(data) or {}
        except Exception:
            printExc()
            return []
        mp4, hls = [], []
        for media in js.get("mediaDetails", []) or []:
            if media.get("type") not in ("video", "animated_gif"):
                continue
            for var in (media.get("video_info", {}) or {}).get("variants", []) or []:
                vurl = var.get("url", "") or ""
                if not vurl or vurl in [x["url"] for x in mp4 + hls]:
                    continue
                if "mpegURL" in (var.get("content_type", "") or "") or ".m3u8" in vurl:
                    hls.append({"name": "Twitter HLS", "url": vurl, "need_resolve": 0})
                else:
                    height = self.cm.ph.getSearchGroups(vurl, r"/\d+x(\d+)/")[0]
                    name = ("Twitter %sp" % height) if height else ("Twitter %dk" % ((var.get("bitrate", 0) or 0) // 1000))
                    mp4.append({"name": name, "url": vurl, "need_resolve": 0, "_br": var.get("bitrate", 0) or 0})
        mp4.sort(key=lambda x: x.get("_br", 0), reverse=True)
        for item in mp4:
            item.pop("_br", None)
        # region-locked media (beIN, FIFA ...) answers 403 outside the rights region - one look at the
        # small HLS playlist tells it from the box's own location
        if hls:
            sts, _data = self.getPage(hls[0]["url"])
            if not sts:
                self._twitterBlocked = True
                return []
        return mp4 + hls

    def _vortexLinks(self, embed):
        origin = re.sub(r"^(https?://[^/]+).*$", r"\1", embed)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self.MAIN_URL)
        sts, data = self.getPage(embed, params)
        if not sts:
            return []
        links = []
        for src in re.findall(r"""["']((?:https?:)?//[^"']+\.m3u8[^"']*)["']""", data):
            src = src if src.startswith("http") else "https:" + src
            if re.match(r"https?://(?:localhost|127\.)", src) or src in [str(x["url"]) for x in links]:
                # the player's commented-out debug source points to localhost
                continue
            links.append({"name": "Vortex HLS" if not links else "Vortex HLS %d" % (len(links) + 1),
                          "url": strwithmeta(src, {"User-Agent": self.HEADER.get("User-Agent"), "Referer": embed, "Origin": origin}), "need_resolve": 0})
        return links

    def getVideoLinks(self, videoUrl):
        printDBG("BtolatCom.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("BtolatCom.getArticleContent [%s]" % cItem.get("url", ""))
        category = cItem.get("category", "")
        title = cItem.get("raw_title") or cItem.get("title", "")
        icon = cItem.get("icon", "")
        info = {}
        text = ""
        if category in VIDEO_CATS:
            sts, data = self.getPage(cItem.get("url", ""))
            if sts:
                text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
                icon = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0] or icon
                published = self.cm.ph.getSearchGroups(data, r'datePublished"\s+content="(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})', 2)
                if published[0]:
                    info["released"] = "%s %s" % (published[0], published[1])
            if cItem.get("league"):
                info["genre"] = cItem["league"]
            if cItem.get("duration"):
                info["duration"] = cItem["duration"]
            if "released" not in info and cItem.get("date"):
                info["released"] = cItem["date"]
        elif category == "bt_team":
            sts, data = self.getPage(cItem.get("url", ""))
            if sts:
                card = self.cm.ph.getDataBeetwenMarkers(data, 'class="teamCard"', "</h2>\n", False)[1] or data
                # only ArticleContent.RICH_DESC_PARAMS keys are shown: founding year -> "year", the stadium goes into the text
                for key, rx in (("year", r'itemprop="foundingDate"[^>]*>([^<]+)<'), ("director", r'(?s)itemprop="coach".*?itemprop="name">([^<]+)<'),
                                ("country", r'itemprop="addressCountry">([^<]+)<')):
                    val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, rx)[0])
                    if val:
                        info[key] = val
                lines = []
                stadium = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)الملعب\s*<span itemprop="name">([^<]+)<')[0])
                if stadium:
                    lines.append("%s %s" % (_("Stadium:"), stadium))
                leagues = [self.cleanHtmlStr(x) for x in re.findall(r'(?s)<h3><a href="/league/[^"]+"><i[^>]*></i><span>(.*?)</span>', data)]
                if leagues:
                    lines.append("%s: %s" % (_("Competitions"), "، ".join(leagues)))
                text = "[/br]".join(lines)
        else:
            sts, data = self.getPage(cItem.get("player_url") or cItem.get("url", ""))
            if sts:
                block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="player-info', "</ul>", False)[1]
                lines = []
                for label, value in re.findall(r"(?s)<li>\s*([^<:]+?)\s*:\s*<span>(.*?)</span>", block):
                    value = self.cleanHtmlStr(value)
                    if value:
                        lines.append("%s: %s" % (self.cleanHtmlStr(label), value))
                text = "[/br]".join(lines)
                pic = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
                if pic and "logo" not in pic:
                    icon = pic
        if not text:
            text = cItem.get("desc", "")
        return [{"title": self.cleanHtmlStr(title), "text": text, "images": [{"title": "", "url": self.getFullIconUrl(icon)}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("BtolatCom.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "bt_loadmore":
            self.listLoadMore(self.currItem)
        elif category == "bt_paged":
            self.listPaged(self.currItem)
        elif category == "bt_leagues":
            self.listLeagues(self.currItem)
        elif category == "bt_league":
            self.listLeague(self.currItem)
        elif category == "bt_team":
            self.listTeam(self.currItem)
        elif category == "bt_squad":
            self.listSquad(self.currItem)
        elif category == "bt_scorers":
            self.listScorers(self.currItem)
        elif category == "bt_professionals":
            self.listProfessionals(self.currItem)
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
        CHostBase.__init__(self, BtolatCom(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("botolat")

    def withArticleContent(self, cItem):
        category = cItem.get("category", "")
        if category in VIDEO_CATS or category == "bt_team":
            return True
        return category == "bt_paged" and bool(cItem.get("player_url"))
