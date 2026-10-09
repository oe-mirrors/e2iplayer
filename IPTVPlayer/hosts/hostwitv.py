# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - WiTv (witv.football, French live TV; DLE site): the channel groups of the site menu, the
#     "Matchs du jour" schedule (today / tomorrow, each match opens its channel) and the site search
#     (POST, 20 per page, First page / Next page)
#   - a channel page holds 1-6 player pages (/player/source2/?id=...): Vavoo players carry the HLS
#     playlist behind the site's own proxy (var m3u8Url) -> playable; DaddyLive players (short numeric
#     ids, dlive.sx -> dembed.top) send PNG images with the MPEG-TS hidden in the pixel data, which no
#     player on the box can open -> skipped; the servers whose playlist does not answer right now
#     (Vavoo node down: 503 / "temporairement inaccessible") are left out of the link list
#   - DADDY_ONLY: channels that only have DaddyLive players (survey 08.10.2026, 41 of 161) are not listed
#   - removed: the proxy option, the remote mohamed_os icon, cu.Cleantitlename, the broken search call
from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, GetIconDir, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.witv_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.witv_alt_domain)]


def gettytul():
    return "https://witv.football/"


SEARCH_PAGE_SIZE = 20
VIDEO_CATEGORIES = ("wt_channel", "wt_event")
# channel numbers (/chaines-live/<n>-...) with DaddyLive players only - nothing the box can play
DADDY_ONLY = frozenset((51, 137, 145, 151, 169, 171, 174, 176, 177, 179, 181, 182, 183, 187, 188, 189, 190, 191, 192, 193,
                        194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 212, 214, 215, 222, 223, 231, 245))


class WiTV(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "witv", "cookie": "witv.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/witv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _params(self, referer):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=referer)
        return params

    def selectDomain(self):
        domains = [gettytul()]
        domain = config.plugins.iptvplayer.witv_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain if domain.endswith("/") else domain + "/")
        for domain in domains:
            sts, data = self.getPage(domain)
            if sts and "WiTv" in data:
                self.setMainUrl(self.cm.meta.get("url", domain))
                return
        self.MAIN_URL = domains[-1]

    def _channelNumber(self, url):
        num = self.cm.ph.getSearchGroups(url, r"/chaines-live/(\d+)-")[0]
        return int(num) if num else 0

    def _isPlayable(self, url):
        return self._channelNumber(url) not in DADDY_ONLY

    def _channelRow(self, item, group):
        url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+/chaines-live/[^"]+\.html)"')[0])
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="ann-short_price">(.*?)</div>')[0]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
        if not url or not title or not self._isPlayable(url):
            return None
        icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
        desc = "%s%s:%s %s" % (E2ColoR("yellow"), _("Category"), E2ColoR("white"), group) if group else ""
        return {"name": "category", "category": "wt_channel", "good_for_fav": True, "title": title, "url": url,
                "icon": self.getFullIconUrl(icon) if icon else self.DEFAULT_ICON_URL, "desc": desc}

    def _listChannels(self, data, group=""):
        count = 0
        for item in data.split('<div class="holographic-card">')[1:]:
            row = self._channelRow(item, group)
            if row:
                self.addVideo(row)
                count += 1
        return count

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        menu = self.cm.ph.getDataBeetwenMarkers(data, '<div class="catalog">', "</div>", False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(menu, "<a", "</a>"):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            label = self.cleanHtmlStr(item)
            if not href or not label:
                continue
            category = "wt_schedule" if "matchs-du-jour" in href else "wt_list"
            self.addDir({"name": "category", "category": category, "title": label, "url": self.getFullUrl(href), "good_for_fav": True})
        self.listsTab(self.searchItems(), cItem)

    def listChannels(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        if not self._listChannels(data, cItem.get("title", "")):
            SetIPTVPlayerLastHostError(_("No stream available"))

    def listSchedule(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for day, label in (("today", _("Today")), ("tomorrow", _("Tomorrow"))):
            section = self.cm.ph.getDataBeetwenMarkers(data, 'id="section-%s"' % day, "<!-- Section", False)[1] or \
                self.cm.ph.getDataBeetwenMarkers(data, 'id="section-%s"' % day, "<script", False)[1]
            for card in section.split('<div class="match-card"')[1:]:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(card, r'<a href="([^"]+)" class="match-watch-btn"')[0])
                teams = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<div class="match-teams">(.*?)</div>')[0]).replace(" VS ", " - ")
                if not url or not teams or not self._isPlayable(url):
                    continue
                start = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<span class="match-time">(.*?)</span>')[0])
                channel = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'data-channel="([^"]+)"')[0])
                title = "%s %s - %s" % (label, start, teams) if day == "tomorrow" else "%s - %s" % (start, teams)
                desc = " | ".join("%s%s:%s %s" % (E2ColoR("yellow"), k, E2ColoR("white"), v) for k, v in
                                  ((_("Date"), label), (_("Time"), start), (_("Channel"), channel)) if v)
                self.addVideo({"name": "category", "category": "wt_event", "good_for_fav": True, "title": title, "url": url,
                               "icon": self.DEFAULT_ICON_URL, "desc": desc})
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No stream available"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        cItem = dict(cItem)
        cItem.update({"category": "wt_search", "query": searchPattern.strip(), "page": 1})
        self.listSearch(cItem)

    def listSearch(self, cItem):
        page = cItem.get("page", 1)
        post = {"do": "search", "subaction": "search", "story": cItem.get("query", "")}
        if page > 1:
            post.update({"search_start": str(page), "full_search": "0", "result_from": str((page - 1) * SEARCH_PAGE_SIZE + 1)})
        sts, data = self.getPage(self.getMainUrl(), self._params(self.getMainUrl()), post)
        if not sts:
            return
        self._listChannels(data)
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="navigation"', "</div>", False)[1]
        pages = [int(n) for n in self.cm.ph.getAllItemsBeetwenMarkers(pager, "list_submit(", ")", False) if n.isdigit()]
        lastPage = max(pages + [page])
        addPagingItems(self, dict(cItem), page, lastPage > page, lastPage)

    ###################################################
    # links
    ###################################################
    def _playerHls(self, playerUrl, referer):
        # the Vavoo player page -> its HLS playlist behind the site's proxy ("" for DaddyLive / "no stream")
        sts, data = self.getPage(playerUrl, self._params(referer))
        if not sts:
            return ""
        url = self.cm.ph.getSearchGroups(data, r'var\s+m3u8Url\s*=\s*"([^"]+)"')[0].replace("\\/", "/")
        return self.getFullUrl(url, playerUrl) if url else ""

    def _hlsMeta(self, url, referer):
        return strwithmeta(url, {"iptv_proto": "m3u8", "iptv_livestream": True, "User-Agent": self.HEADER["User-Agent"],
                                 "Referer": referer, "Origin": self.getMainUrl()[:-1]})

    def getLinksForVideo(self, cItem):
        printDBG("WiTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        if self.MAIN_URL is None:
            self.selectDomain()
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        urltab = []
        seen = set()
        for playerId in self.cm.ph.getAllItemsBeetwenMarkers(data, 'data-src="/player/source2/?id=', '"', False):
            playerId = playerId.replace("&amp;", "&")
            if not playerId or playerId in seen or (playerId.isdigit() and len(playerId) <= 5):
                continue  # DaddyLive player (short numeric id)
            seen.add(playerId)
            playerUrl = self.getFullUrl("/player/source2/?id=" + playerId)
            hlsUrl = self._playerHls(playerUrl, cItem["url"])
            if not hlsUrl:
                continue
            # the Vavoo node behind the proxy is often down (503): only servers that answer now
            sts, playlist = self.getPage(hlsUrl, self._params(playerUrl))
            if not sts or "#EXTM3U" not in playlist:
                printDBG("WiTV: server %s not answering" % playerId)
                continue
            urltab.append({"name": "%s %d" % (_("Server"), len(urltab) + 1), "url": strwithmeta(playerUrl, {"Referer": cItem["url"]}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), ""))

    def getVideoLinks(self, videoUrl):
        printDBG("WiTV.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        referer = videoUrl.meta.get("Referer", self.getMainUrl()) if hasattr(videoUrl, "meta") else self.getMainUrl()
        hlsUrl = self._playerHls(str(videoUrl), referer)
        links = getDirectM3U8Playlist(self._hlsMeta(hlsUrl, str(videoUrl)), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999) if hlsUrl else []
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        text = StripColorCodes(cItem.get("desc", "")).replace(" | ", "[/br]") or cItem.get("title", "")
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": {}}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("WiTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "wt_list":
            self.listChannels(self.currItem)
        elif category == "wt_schedule":
            self.listSchedule(self.currItem)
        elif category == "wt_search":
            self.listSearch(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, WiTV(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES
