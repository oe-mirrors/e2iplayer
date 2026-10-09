# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# Ported to the python3 framework (08.10.2026):
#   - Yacine TV (Android app): its JSON API (def11.ycnapi.com/api/...) answers XOR-encrypted base64, the key is
#     the app key + the "t" response header; the API domain comes from the app's Firebase remote config
#     ("defaults") - looked up only when the known domain stops answering
#   - categories -> sub categories (ARABIC CHANNELS: countries) -> channels; the category ids are 19-digit
#     strings now (the old hard-coded ids 9 / 89 were gone, that was the empty list)
#   - links: every source of the channel; HLS / DASH directly with the User-Agent / Referer the API sends
#     (segments disguised as .js / .pdf -> requireDownloaderForDisguisedHls), YouTube / ok.ru / Twitch through
#     urlparser, the app's web-view sources (a site with its own player) through urlparser or the first
#     .m3u8 / .mpd address of the page; DRM sources are left out
#   - favourites re-open from the API, INFO with the channel's category and sources, local paging
# 09.10.2026 (box log): not listed any more - "ALKASS" (every channel points to the closed Google Cloud bucket
#     livealkass-eu: 403 AccessDenied for anyone), "SHAHID VIP" (Shahid's paid tier: Akamai 403 outside
#     the subscription region, 20 of 21 channels) and "WEYYAK" (all 5 fixed weyyak-live.akamaized.net
#     addresses 404 "Not found"); a channel's HLS sources are checked when its link list is
#     built and only the ones that answer with a playlist are offered (about a third of them is 404 at a time);
#     Wikipedia channel logos ("thumb/.../280px-...") are moved to the nearest thumbnail width Wikimedia still
#     renders (others answer HTTP 400) and fetched with a descriptive User-Agent
import base64
import os
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta, requireDownloaderForDisguisedHls
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta


def GetConfigList():
    return []


def gettytul():
    return "https://yacineapp.tv/"


API_DOMAIN = "def11.ycnapi.com"
PAGE_SIZE = 100
# the app's XOR key (base64, reversed)
XOR_KEY = bytearray(base64.b64decode("d3ZAdkVARyY5TitqWnghYw==")[::-1])
# the app talks to its API with okhttp
API_HEADER = {"User-Agent": "okhttp/4.12.0", "Accept": "application/json"}
# Firebase project of the app: remote config "defaults" = API domain
FB_PROJECT_ID = "ycntv-7a08e"
FB_PROJECT_NUMBER = "692330584196"
FB_APP_ID = "1:692330584196:android:68ea9f0c920aa17904cad1"
FB_API_KEY = "AIzaSyDRKL14PPiXzk7qNUNLgV2IsjasxNpWLeU"
FB_PKG = "ver3.ycntivi.off"
FB_CERT = "5972C7A84F75BED23F633A0404BA95AE5764F29B"
FB_HEADER = {"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11)", "Content-Type": "application/json",
             "X-Android-Package": FB_PKG, "X-Android-Cert": FB_CERT, "x-goog-api-key": FB_API_KEY}
# url_type of a source: 1/2/3 stream address, 4 YouTube, 5/6 a web page the app opens in a web view
WEB_TYPES = (5, 6)
# categories that never play (see the header), compared in upper case
SKIP_CATEGORIES = ("ALKASS", "SHAHID VIP", "WEYYAK")
# sources that never play: the closed Alkass bucket
DEAD_SOURCES = re.compile(r"storage\.googleapis\.com/livealkass")
CHECK_TIMEOUT = 10  # seconds for the playlist check of a source
# upload.wikimedia.org only renders these thumbnail widths (any other width: HTTP 400 "Use thumbnail sizes
# listed on https://w.wiki/GHai", 09.10.2026) and wants a descriptive User-Agent from tools
WIKIMEDIA_THUMB_RE = re.compile(r"^(https?://upload\.wikimedia\.org/.+/thumb/.+/)(\d+)(px-[^/]+)$")
WIKIMEDIA_WIDTHS = (20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840)
WIKIMEDIA_UA = "E2iPlayer/1.0 (https://github.com/oe-mirrors/e2iplayer)"


def _domain(url):
    m = re.match(r"^https?://(?:www\.)?([^/:?#]+)", url or "")
    return m.group(1).lower() if m else ""


class YacineTV(CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "cat_id", "cat_title", "channel_id", "child_count")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "yacinetv", "cookie": "yacinetv.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/yacinetv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.apiDomain = API_DOMAIN
        self.cache = {}

    ###################################################
    # API
    ###################################################
    def _decrypt(self, data, stamp):
        key = XOR_KEY + bytearray(stamp.encode("ascii"))
        raw = bytearray(base64.b64decode(data.strip()))
        return bytes(bytearray(b ^ key[i % len(key)] for i, b in enumerate(raw))).decode("utf-8")

    def _apiCall(self, path):
        params = {"header": API_HEADER, "collect_all_headers": True}
        sts, data = self.cm.getPage("https://%s/api/%s" % (self.apiDomain, path), params)
        if not sts or not data:
            return None
        try:
            return json_loads(self._decrypt(data, str(self.cm.meta.get("t") or int(time.time()))))
        except Exception:
            printExc()
        return None

    def _firebaseDomain(self):
        # the API domain from the app's Firebase remote config (anonymous installation token first)
        raw = bytearray(os.urandom(17))
        raw[0] = (raw[0] & 0x0F) | 0x70
        fid = base64.urlsafe_b64encode(bytes(raw)).decode("ascii").rstrip("=")[:22]
        params = {"header": FB_HEADER, "raw_post_data": True}
        sts, data = self.cm.getPage("https://firebaseinstallations.googleapis.com/v1/projects/%s/installations" % FB_PROJECT_ID, params,
                                    json_dumps({"fid": fid, "appId": FB_APP_ID, "authVersion": "FIS_v2", "sdkVersion": "a:18.0.0"}))
        try:
            token = json_loads(data)["authToken"]["token"] if sts else ""
        except Exception:
            printExc()
            token = ""
        if not token:
            return ""
        payload = {"appVersion": "3.1", "firstOpenTime": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()), "timeZone": "Asia/Bahrain",
                   "appInstanceIdToken": token, "languageCode": "en-US", "appBuild": "4", "appInstanceId": fid, "countryCode": "US",
                   "analyticsUserProperties": {}, "appId": FB_APP_ID, "platformVersion": "30", "sdkVersion": "22.0.0", "packageName": FB_PKG}
        params = {"header": dict(FB_HEADER, **{"X-Goog-Firebase-Installations-Auth": token, "X-Firebase-RC-Fetch-Type": "BASE/1"}), "raw_post_data": True}
        sts, data = self.cm.getPage("https://firebaseremoteconfig.googleapis.com/v1/projects/%s/namespaces/firebase:fetch" % FB_PROJECT_NUMBER, params, json_dumps(payload))
        try:
            return (json_loads(data).get("entries") or {}).get("defaults", "") if sts else ""
        except Exception:
            printExc()
        return ""

    def _api(self, path):
        # {"data": [...]} of the API, cached per session level; on failure the domain is looked up again once
        if path in self.cache:
            return self.cache[path]
        data = self._apiCall(path)
        if data is None:
            domain = self._firebaseDomain()
            if domain and domain != self.apiDomain:
                printDBG("YacineTV: API domain %s -> %s" % (self.apiDomain, domain))
                self.apiDomain = domain
                data = self._apiCall(path)
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            return []
        self.cache[path] = data["data"]
        return data["data"]

    def _icon(self, url):
        url = (url or "").strip()
        if not url.startswith("http"):
            return ""
        thumb = WIKIMEDIA_THUMB_RE.match(url)
        if thumb:
            # logos from Wikipedia: ".../thumb/.../280px-Name.png" -> the nearest width Wikimedia still renders
            width = int(thumb.group(2))
            width = min(WIKIMEDIA_WIDTHS, key=lambda w: (abs(w - width), -w))
            return strwithmeta("%s%d%s" % (thumb.group(1), width, thumb.group(3)), {"User-Agent": WIKIMEDIA_UA})
        if _domain(url) == "upload.wikimedia.org":
            return strwithmeta(url, {"User-Agent": WIKIMEDIA_UA})
        return strwithmeta(url, {"User-Agent": self.HEADER.get("User-Agent")})

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("yc_channel", "yc_cat"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def _addCategories(self, entries):
        for entry in entries:
            if isinstance(entry, dict) and entry.get("id") and entry.get("name") and entry["name"].strip().upper() not in SKIP_CATEGORIES:
                self.addDir({"name": "category", "category": "yc_cat", "good_for_fav": True, "title": entry["name"].strip(), "cat_id": str(entry["id"]),
                             "child_count": int(entry.get("child_count") or 0), "icon": self._icon(entry.get("logo")) or self.DEFAULT_ICON_URL})

    def listMainMenu(self, cItem):
        self._addCategories(self._api("categories"))

    def listCategory(self, cItem):
        if cItem.get("child_count"):
            self._addCategories(self._api("categories/%s" % cItem["cat_id"]))
            if self.currList:
                return
        page = cItem.get("page", 1)
        channels = [c for c in self._api("categories/%s/channels" % cItem["cat_id"]) if isinstance(c, dict) and c.get("id") and not c.get("is_hide")]
        lastPage = max(1, (len(channels) + PAGE_SIZE - 1) // PAGE_SIZE)
        for channel in channels[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]:
            name = (channel.get("name") or "").strip()
            self.addVideo({"name": "category", "category": "yc_channel", "good_for_fav": True, "title": name, "channel_id": str(channel["id"]),
                           "url": "%schannel/%s" % (self.MAIN_URL, channel["id"]), "icon": self._icon(channel.get("logo")),
                           "desc": cItem.get("title", ""), "cat_title": cItem.get("title", "")})
        addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    ###################################################
    # links
    ###################################################
    def _sources(self, cItem):
        sources = []
        for src in self._api("channel/%s" % cItem.get("channel_id", "")):
            if not isinstance(src, dict) or src.get("drm") or not self.cm.isValidUrl(src.get("url", "")) or DEAD_SOURCES.search(src["url"]):
                continue
            headers = src.get("headers") or {}
            sources.append({"name": (src.get("name") or "").strip(), "url": src["url"].replace("www.elahmad.coo", "www.elahmad.com"),
                            "type": int(src.get("url_type") or 0), "ua": (headers.get("User-Agent") or src.get("user_agent") or "").strip(),
                            "referer": headers.get("Referer") or src.get("referer") or ""})
        return sources

    def getLinksForVideo(self, cItem):
        printDBG("YacineTV.getLinksForVideo [%s]" % cItem.get("channel_id", ""))
        self.cache.pop("channel/%s" % cItem.get("channel_id", ""), None)  # tokenised addresses: always fresh
        urltab = []
        for src in self._sources(cItem):
            meta = {"User-Agent": src["ua"] or self.HEADER.get("User-Agent"), "yc_type": src["type"]}
            if src["referer"]:
                meta["Referer"] = src["referer"]
            if not self._answers(src["url"], meta):
                printDBG("YacineTV: source not answering [%s]" % src["url"])
                continue
            name = src["name"] or "%s %d" % (_("Server"), len(urltab) + 1)
            urltab.append({"name": "%s - %s" % (name, _domain(src["url"])), "url": strwithmeta(src["url"], meta), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), ""))

    def _answers(self, url, meta):
        # an HLS source of the app: offered only when its playlist answers now (dead sources: 404 / 403 / timeout);
        # web pages, urlparser hosters, DASH / MP4 are not checked here
        path = url.split("?", 1)[0].lower()
        if meta.get("yc_type") in WEB_TYPES or self.up.checkHostSupport(url) == 1 or ".mpd" in path or path.endswith(".mp4"):
            return True
        if ".m3u8" not in url and meta.get("yc_type") not in (2, 3):
            return True
        header = dict((key, meta[key]) for key in ("User-Agent", "Referer") if meta.get(key))
        sts, data = self.cm.getPage(url, {"header": header, "timeout": CHECK_TIMEOUT})
        return bool(sts and "#EXTM3U" in (data or ""))

    def _streamLinks(self, url, meta):
        meta = dict(meta, iptv_livestream=True)
        path = url.split("?", 1)[0].lower()
        if ".mpd" in path:
            return getMPDLinksWithMeta(strwithmeta(url, meta), False, sortWithMaxBandwidth=99999999)
        if ".m3u8" in path or ".m3u8" in url or meta.get("yc_type") in (2, 3):
            meta["iptv_proto"] = "m3u8"
            # re.new-redirect.online sends the playlist on to a random edge host whose segments are
            # relative to it: the player gets the edge address (same token)
            header = dict((key, meta[key]) for key in ("User-Agent", "Referer", "Origin") if meta.get(key))
            sts, data = self.cm.getPage(url, {"header": header})
            if not sts or "#EXTM3U" not in data:
                return []
            url = self.cm.meta.get("url") or url
            return requireDownloaderForDisguisedHls(getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999))
        return [{"name": _domain(url), "url": strwithmeta(url, meta)}]

    def _webSource(self, url, meta):
        # a page with its own player: the first stream address in it
        params = {"header": dict(self.HEADER, **{"User-Agent": meta.get("User-Agent"), "Referer": meta.get("Referer") or url})}
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return []
        stream = self.cm.ph.getSearchGroups(data, r"""(https?:)?(//[^"'\s<>\\]+?\.(?:m3u8|mpd)(?:\?[^"'\s<>\\]*)?)["'\s]""", 2)
        stream = stream[1] if stream[1] else ""
        if not stream:
            return []
        return self._streamLinks("https:" + stream, {"User-Agent": meta.get("User-Agent"), "Referer": self.cm.meta.get("url", url), "Origin": "https://%s" % _domain(url)})

    def getVideoLinks(self, videoUrl):
        printDBG("YacineTV.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        meta = dict(getattr(videoUrl, "meta", {}))
        urlType = meta.pop("yc_type", 0)
        url = str(videoUrl)
        if self.up.checkHostSupport(url) == 1:
            links = self.up.getVideoLinkExt(strwithmeta(url, meta))
        elif urlType in WEB_TYPES:
            links = self._webSource(url, meta)
        else:
            links = self._streamLinks(url, dict(meta, yc_type=urlType))
        for link in links:
            linkMeta = dict(getattr(link["url"], "meta", {}))
            linkMeta.pop("yc_type", None)
            link["url"] = strwithmeta(link["url"], linkMeta)
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        sources = self._sources(cItem)
        info = {}
        if cItem.get("cat_title"):
            info["genre"] = cItem["cat_title"]
        if sources:
            info["source"] = ", ".join(sorted(set(_domain(s["url"]) for s in sources)))
        lines = [cItem.get("title", "")]
        lines.extend("%s: %s" % (s["name"] or _("Server"), _domain(s["url"])) for s in sources)
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": "[/br]".join(lines), "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("YacineTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if refresh or name is None:
            self.cache = {}  # live data: fresh on every refresh / new start
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "yc_cat":
            self.listCategory(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, YacineTV(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "yc_channel"
