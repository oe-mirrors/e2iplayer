# -*- coding: utf-8 -*-
LAST_MODIFIED = "28.10.2026"
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - WiTv (witv.eu, was witv.football until 10.2026; French live TV; DLE site): the channel groups of the site menu, the
#     "Matchs du jour" schedule (today / tomorrow, each match opens its channel) and the search in the
#     site's channel catalog (/ajax_search.php, base64 + XOR mask)
#   - a channel page holds 1-6 sealed player tokens (data-v="wt1_..."), the page's XOR-sealed script maps
#     them to the player pages /player/source2/?id=... (decoys from /ajax_player.php without its signature);
#     the player page is loaded like the site's iframe (Sec-Fetch-Dest, _t, h_check cookie), its real HLS
#     playlist is _wtPayload (var m3u8Url is a decoy notice video); playlist and segments need
#     Referer = player page + Sec-Fetch-Site; DaddyLive players (short numeric ids, iframe to wideiptv /
#     matchora, MPEG-TS hidden in PNG images) are skipped; servers not answering right now are left out
#   - DADDY_ONLY: channels that only have DaddyLive players (survey 08.10.2026, 41 of 161) are not listed
#   - removed: the proxy option, the remote mohamed_os icon, cu.Cleantitlename, the broken search call
import base64
import time

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, requireDownloaderForDisguisedHls
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, GetIconDir, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.witv_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.witv_alt_domain)]


def gettytul():
    return "https://witv.eu/"


VIDEO_CATEGORIES = ("wt_channel", "wt_event")
# channel numbers (/chaines-live/<n>-...) with DaddyLive players only - nothing the box can play
DADDY_ONLY = frozenset((51, 137, 145, 151, 169, 171, 174, 176, 177, 179, 181, 182, 183, 187, 188, 189, 190, 191, 192, 193,
                        194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 212, 214, 215, 222, 223, 231, 245))
# the player page sends the stream only to an iframe of the site
IFRAME_HEADER = {"Sec-Fetch-Dest": "iframe", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "same-origin"}


class WiTV(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "witv", "cookie": "witv.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/witv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        # h_check: set by the site on the first real click, the player and the catalog need it
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE,
                              "cookie_items": {"h_check": "25"}}
        self.catalog = None

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

    def _xhrParams(self, referer):
        params = self._params(referer)
        params["header"].update({"Origin": self.getMainUrl()[:-1], "X-Requested-With": "XMLHttpRequest"})
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

    def _getCatalog(self):
        # every channel of the site: [{"t": title, "u": url, "l": logo, "c": group}], base64 + XOR mask "m"
        if self.catalog:
            return self.catalog
        sts, data = self.getPage(self.getFullUrl("/ajax_search.php"), self._xhrParams(self.getMainUrl()), {"t": "1"})
        if not sts:
            return []
        try:
            res = json_loads(data)
            mask = int(res.get("m", 0))
            raw = bytes(bytearray(b ^ mask for b in bytearray(base64.b64decode(res.get("d", "")))))
            self.catalog = [item for item in json_loads(raw.decode("utf-8")) if isinstance(item, dict)]
        except Exception:
            printExc()
            return []
        return self.catalog

    def listSearchResult(self, cItem, searchPattern, searchType):
        query = ensure_str(searchPattern).strip().lower()
        for item in self._getCatalog():
            title = ensure_str(item.get("t", ""))
            url = self.getFullUrl(ensure_str(item.get("u", "")))
            if not title or query not in title.lower() or "/chaines-live/" not in url or not self._isPlayable(url):
                continue
            icon = ensure_str(item.get("l", ""))
            group = ensure_str(item.get("c", ""))
            desc = "%s%s:%s %s" % (E2ColoR("yellow"), _("Category"), E2ColoR("white"), group) if group else ""
            self.addVideo({"name": "category", "category": "wt_channel", "good_for_fav": True, "title": title, "url": url,
                           "icon": self.getFullIconUrl(icon) if icon else self.DEFAULT_ICON_URL, "desc": desc})

    ###################################################
    # links
    ###################################################
    def _playerMap(self, data):
        # the channel page's sealed script: XOR(_m) of "key|salt|base64 JSON {token: player url}" (window._wt_vmap);
        # /ajax_player.php without the page's signature answers with decoy players
        nums = self.cm.ph.getSearchGroups(data, r"_a=\[([\d,]+)\],_m=(\d+)", 2)
        if not nums[0] or not nums[1]:
            return {}
        try:
            mask = int(nums[1])
            parts = "".join(chr(int(n) ^ mask) for n in nums[0].split(",")).split("|")
            vmap = parts[2] if len(parts) > 2 else ""
            return dict((ensure_str(k), ensure_str(v)) for k, v in json_loads(ensure_str(base64.b64decode(vmap + "=" * (-len(vmap) % 4)))).items()) if vmap else {}
        except Exception:
            printExc()
            return {}

    def _playerHls(self, playerUrl, referer):
        # the player page -> (HLS playlist behind the site's proxy, player page url = Referer of the stream);
        # "var m3u8Url" is a decoy (notice video), the real playlist is _wtPayload = reversed base64
        pageUrl = "%s%s_t=%d" % (playerUrl, "&" if "?" in playerUrl else "?", int(time.time() * 1000))
        params = self._params(referer)
        params["header"].update(IFRAME_HEADER)
        sts, data = self.getPage(pageUrl, params)
        if not sts or "temporairement inaccessible" in data:
            return "", pageUrl
        payload = self.cm.ph.getSearchGroups(data, r'''_wtPayload\s*=\s*["']([^"']+)["']''')[0]
        try:
            url = ensure_str(base64.b64decode(payload[::-1] + "=" * (-len(payload) % 4))) if payload else ""
        except Exception:
            url = ""
        if not url or "vc=notice" in url:
            return "", pageUrl
        return self.getFullUrl(url, playerUrl), pageUrl

    def _isLive(self, hlsUrl, pageUrl):
        # a live playlist; an expired / refused one comes as the site's notice video (vc=notice, #EXT-X-ENDLIST)
        params = self._params(pageUrl)
        params["header"]["Sec-Fetch-Site"] = "same-origin"
        sts, playlist = self.getPage(hlsUrl, params)
        return sts and "#EXTM3U" in playlist and "vc=notice" not in playlist and "#EXT-X-ENDLIST" not in playlist

    def _hlsMeta(self, url, referer):
        # playlist and segments answer with the notice video unless Referer = player page + Sec-Fetch-Site
        return strwithmeta(url, {"iptv_proto": "m3u8", "iptv_livestream": True, "User-Agent": self.HEADER["User-Agent"],
                                 "Referer": referer, "Sec-Fetch-Site": "same-origin"})

    def getLinksForVideo(self, cItem):
        printDBG("WiTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        if self.MAIN_URL is None:
            self.selectDomain()
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        urltab = []
        seen = set()
        players = self._playerMap(data)
        for token in self.cm.ph.getAllItemsBeetwenMarkers(data, 'data-v="', '"', False):
            token = token.replace("&amp;", "&")
            playerUrl = self.getFullUrl(players.get(token, "" if token.startswith("wt1_") else token))
            playerId = self.cm.ph.getSearchGroups(playerUrl, r"[?&]id=([^&]+)")[0]
            if "/player/source2/" not in playerUrl or not playerId or playerId in seen or (playerId.isdigit() and len(playerId) <= 5):
                continue  # foreign / DaddyLive player (short numeric id, iframe to wideiptv / matchora) or a server listed twice
            seen.add(playerId)
            hlsUrl, pageUrl = self._playerHls(playerUrl, cItem["url"])
            if not hlsUrl:
                printDBG("WiTV: server %s has no stream" % playerId)
                continue
            # the node behind the proxy is often down (404 / 503): only servers that answer now
            if not self._isLive(hlsUrl, pageUrl):
                printDBG("WiTV: server %s not answering" % playerId)
                continue
            # the playlist url rides along, getVideoLinks does not load the player page again
            urltab.append({"name": "%s %d" % (_("Server"), len(urltab) + 1), "url": strwithmeta(playerUrl, {"Referer": cItem["url"], "wt_hls": hlsUrl, "wt_page": pageUrl}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), ""))

    def getVideoLinks(self, videoUrl):
        printDBG("WiTV.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        meta = videoUrl.meta if hasattr(videoUrl, "meta") else {}
        referer = meta.get("Referer", self.getMainUrl())
        links = []
        hlsUrl, pageUrl = meta.get("wt_hls", ""), meta.get("wt_page", str(videoUrl))
        if not hlsUrl or not self._isLive(hlsUrl, pageUrl):
            # no stored playlist url or it expired meanwhile (the site then sends its notice video): ask the player page again
            hlsUrl, pageUrl = self._playerHls(str(videoUrl), referer)
            if hlsUrl and not self._isLive(hlsUrl, pageUrl):
                hlsUrl = ""
        if hlsUrl:
            links = getDirectM3U8Playlist(self._hlsMeta(hlsUrl, pageUrl), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        # segments /player/source2/?vp=... without media extension: exteplayer3's ffmpeg refuses them -> hlsdl
        return decorateResolvedLinkItems(requireDownloaderForDisguisedHls(links), sidecar)

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
