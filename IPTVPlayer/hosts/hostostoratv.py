# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# Ported to the python3 framework (08.10.2026):
#   - Ostora TV (Android app): its API (/api/v6.2/main | category/<id>?page=<n>) on hashed *.sa0xx.shop hosts
#     answers AES-256-CBC encrypted base64 (key/iv of the app); the second host is the fallback
#   - main categories -> sub categories (channel groups, series, ...) -> streams; the API pages hold 400 rows,
#     shown as pages of 100 (First page / Jump / Next page over the whole list)
#   - a stream row's "source": "<n><F>url" or hoster embeds "url<<R>>referer" joined by "!"; hoster embeds
#     (player 10: vidara, playmate, savefiles, filemoon, vidmoly, ...) go to urlparser, stream addresses
#     (HLS / DASH / radio) are played directly with the app's User-Agent
#   - left out: "url###kid:key" sources (ClearKey-encrypted DASH of Shahid / STC / StarzPlay / ART - no
#     enigma2 player decrypts them); rows with only such sources are not listed. HLS whose AES key is a
#     "data:...ENC:" blob (www.manar3.skin channel groups: beIN, Al Kass, ON Sport, ...) is wrapped with a key only
#     the app knows and segments disguised as PNG -> a clear message instead of a dead player
#   - watched flag (series folder -> episodes), favourites (re-open fetches fresh tokens), name normalisation
#     ("Show - SxxExx" for "الحلقة N" rows), sidecar, INFO via moviemeta (series / films) + the app's data
# 09.10.2026 (box log): the MBC group (MBC 1-5, Drama, Masr, Iraq, ... on *-prod-dub-ak.akamaized.net /
#     mbc1-enc.edgenextcdn.net) answers the master playlist but every variant playlist with 404 outside the
#     broadcaster's region (hlsdl "error_code 404"): the first variant is checked before the player starts,
#     a dead one gives a clear message instead of a buffering error
import base64
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs import pyaes
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta, requireDownloaderForDisguisedHls
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

try:
    # pycryptodome (when the image has it) is faster than pyaes for the 400-row pages
    from Crypto.Cipher import AES as CryptoAES
except Exception:
    CryptoAES = None


def GetConfigList():
    return []


def gettytul():
    return "https://ostora.tv/"


# the app's API hosts (both answer the same)
API_HOSTS = ("oneivlwrcoa03n5t94fg2i6xncl9j4rblmqb08w27w71jt8hdb.sa036.shop",
             "5h2jwmzah7ba862raxx0o3kv6in0bytn3soqpkdzre5fn7mc1u.sa003.shop")
KEY = base64.b16decode("4E5C6D1A8B3FE8137A3B9DF26A9C4DE195267B8E6F6C0B4E1C3AE1D27F2B4E6F")
IV = base64.b16decode("A9C21F8D7E6B4A9DB12E4F9D5C1A7B8E")
PAGE_SIZE = 100
API_PAGE_SIZE = 400
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")
SEASON_RE = re.compile(r"(?:الموسم|موسم)\s*(\d+)")


def _domain(url):
    m = re.match(r"^https?://(?:www\.)?([^/:?#]+)", url or "")
    return m.group(1).lower() if m else ""


def _decrypt(data):
    # base64 (url-safe) AES-256-CBC, PKCS#7 -> text, "" on failure
    try:
        data = data.strip().replace("-", "+").replace("_", "/")
        raw = base64.b64decode(data + "=" * (-len(data) % 4))
        if CryptoAES is not None:
            plain = CryptoAES.new(KEY, CryptoAES.MODE_CBC, IV).decrypt(raw)
        else:
            decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(KEY, IV), padding=pyaes.PADDING_NONE)
            plain = decrypter.feed(raw) + decrypter.feed()
        pad = plain[-1] if isinstance(plain[-1], int) else ord(plain[-1])
        return ensure_str(plain[:-pad])
    except Exception:
        printExc()
    return ""


def _parseSource(source):
    # "413<F>url!url<<R>>referer!..." -> [(url, referer, headers)], DRM count
    links, drm = [], 0
    for part in (source or "").split("!"):
        part = part.replace("\r", "").strip()
        if "<F>" in part:
            part = part.split("<F>", 1)[1].strip()
        url, _sep, referer = part.partition("<<R>>")
        url, referer = url.strip(), referer.strip()
        if "###" in url:
            drm += 1
            continue
        headers = {}
        if "|" in url:
            url, extra = url.split("|", 1)
            for pair in extra.split("&"):
                key, sep, value = pair.partition("=")
                if sep and key.strip() in ("Referer", "User-Agent", "Origin"):
                    headers[key.strip()] = value.strip()
        if url.startswith("http"):
            links.append((url, referer, headers))
    return links, drm


class OstoraTV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "cat_id", "cat_title", "item_id", "api_page",
                  "kind", "player", "agent", "source", "s_title", "s_episode", "meta_type", "meta_title")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "ostoratv", "cookie": "ostoratv.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/ostoratv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="mobile")
        self.apiHost = API_HOSTS[0]
        self.cache = {}
        self.watchedHelper = IPTVWatchedHelper("ostoratv")
        self.wfInitFolderCache()

    ###################################################
    # API
    ###################################################
    def _api(self, path):
        if path in self.cache:
            return self.cache[path]
        for host in [self.apiHost] + [h for h in API_HOSTS if h != self.apiHost]:
            sts, data = self.cm.getPage("https://%s/api/v6.2/%s" % (host, path), {"header": self.HEADER})
            plain = _decrypt(data) if sts and data else ""
            if not plain:
                continue
            try:
                js = json_loads(plain)
            except Exception:
                printExc()
                continue
            self.apiHost = host
            self.cache[path] = js
            return js
        return {}

    def _category(self, catId, apiPage=1):
        data = self._api("category/%s?page=%d" % (catId, apiPage)).get("data")
        return data if isinstance(data, dict) else {}

    def _icon(self, url):
        url = (url or "").strip()
        if not url.startswith("http"):
            return ""
        return strwithmeta(url, {"User-Agent": self.HEADER.get("User-Agent")})

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("os_top", "os_cat", "os_stream"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag (series folders -> episodes, films; live channels have none)
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        if not isinstance(cItem, dict):
            return ""
        if cItem.get("category") == "os_cat" and cItem.get("cat_id") and cItem.get("level", 0) > 0:
            return "folder:%s" % cItem["cat_id"]
        if cItem.get("category") == "os_stream" and cItem.get("kind") != "live" and cItem.get("item_id"):
            return "video:%s" % cItem["item_id"]
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        for entry in self._api("main").get("data") or []:
            if isinstance(entry, dict) and entry.get("id") and entry.get("name"):
                self.addDir({"name": "category", "category": "os_top", "good_for_fav": True, "title": entry["name"].strip(),
                             "cat_id": str(entry["id"]), "level": 0, "icon": self._icon(entry.get("image")) or self.DEFAULT_ICON_URL})

    def _streamRow(self, cItem, entry, apiPage, normalize):
        name = (entry.get("name") or "").replace("\r", "").strip()
        links, drm = _parseSource(entry.get("source"))
        if not name or (drm and not links):
            return None
        kind = entry.get("type") or "live"
        row = {"name": "category", "category": "os_stream", "good_for_fav": True, "title": name, "item_id": str(entry.get("id", "")),
               "cat_id": cItem["cat_id"], "cat_title": cItem.get("title", ""), "api_page": apiPage, "kind": kind,
               "player": str(entry.get("player") or ""), "agent": (entry.get("agent") or "").strip(), "source": entry.get("source", ""),
               "url": "%s%s/%s" % (self.MAIN_URL, cItem["cat_id"], entry.get("id", "")), "icon": self._icon(entry.get("image")),
               "desc": cItem.get("title", "")}
        if kind == "series":
            show = cItem.get("title", "")
            episode = self.cm.ph.getSearchGroups(name, EPISODE_RE.pattern)[0]
            season = self.cm.ph.getSearchGroups(name, SEASON_RE.pattern)[0] or "1"
            if episode:
                row.update({"s_title": show, "s_episode": episode, "meta_type": "tv", "meta_title": show})
                if normalize:
                    row["title"] = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                row.update({"meta_type": "tv", "meta_title": show})
        elif kind == "movie":
            row.update({"meta_type": "movie", "meta_title": name})
        return row

    def listCategory(self, cItem):
        page = cItem.get("page", 1)
        apiPage = (page - 1) * PAGE_SIZE // API_PAGE_SIZE + 1
        offset = (page - 1) * PAGE_SIZE % API_PAGE_SIZE
        data = self._category(cItem["cat_id"], apiPage)
        entries = [e for e in data.get("items") or [] if isinstance(e, dict)]
        normalize = IsMediaNamingNormalized()
        titles = {}
        for entry in entries[offset:offset + PAGE_SIZE]:
            if "source" in entry:
                row = self._streamRow(cItem, entry, apiPage, normalize)
                if row:
                    # the same channel twice (another source): "Name (2)"
                    titles[row["title"]] = titles.get(row["title"], 0) + 1
                    if titles[row["title"]] > 1:
                        row["title"] = "%s (%d)" % (row["title"], titles[row["title"]])
                    self.addVideo(row)
            elif entry.get("id") and entry.get("name"):
                self.addDir({"name": "category", "category": "os_cat", "good_for_fav": True, "title": entry["name"].strip(),
                             "cat_id": str(entry["id"]), "level": cItem.get("level", 0) + 1, "icon": self._icon(entry.get("image")) or cItem.get("icon", "")})
        pagination = data.get("pagination") or {}
        try:
            total = int(pagination.get("total") or 0)
        except ValueError:
            total = 0
        lastPage = max(1, (max(total, len(entries)) + PAGE_SIZE - 1) // PAGE_SIZE)
        # the template only switches the Jump row on (the API is paged by the "page" field, not by the url)
        addPagingItems(self, dict(cItem), page, page < lastPage, lastPage, "%scategory/%s#page={page}" % (self.MAIN_URL, cItem["cat_id"]))

    ###################################################
    # links
    ###################################################
    def _freshSource(self, cItem):
        # the tokenised addresses of a row expire: the row again from the API, the stored one as fallback
        if cItem.get("cat_id") and cItem.get("item_id"):
            self.cache.pop("category/%s?page=%d" % (cItem["cat_id"], cItem.get("api_page", 1)), None)
            for entry in self._category(cItem["cat_id"], cItem.get("api_page", 1)).get("items") or []:
                if isinstance(entry, dict) and str(entry.get("id")) == cItem["item_id"]:
                    return entry.get("source", "")
        return cItem.get("source", "")

    def getLinksForVideo(self, cItem):
        printDBG("OstoraTV.getLinksForVideo [%s/%s]" % (cItem.get("cat_id", ""), cItem.get("item_id", "")))
        links, drm = _parseSource(self._freshSource(cItem))
        agent = cItem.get("agent") or self.HEADER.get("User-Agent")
        live = cItem.get("kind") == "live"
        urltab = []
        for url, referer, headers in links:
            meta = dict(headers)
            meta.setdefault("User-Agent", agent)
            if referer:
                meta["Referer"] = referer
            if live:
                meta["iptv_livestream"] = True
            name = self.up.getHostName(url) if cItem.get("player") == "10" else _domain(url)
            urltab.append({"name": "%d. %s" % (len(urltab) + 1, name) if len(links) > 1 else name, "url": strwithmeta(url, meta), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available") if not drm else _("Video with DRM protection."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), ""))

    def _hlsLinks(self, url, meta):
        header = dict((key, meta[key]) for key in ("User-Agent", "Referer", "Origin") if meta.get(key))
        sts, data = self.cm.getPage(url, {"header": header})
        if not sts or "#EXTM3U" not in data:
            return []
        keyUri = self.cm.ph.getSearchGroups(data, r'#EXT-X-KEY:[^\n]*URI="data:[^,"]*;base64,([^"]+)"')[0]
        if keyUri:
            try:
                wrapped = base64.b64decode(keyUri).startswith(b"ENC:")
            except Exception:
                wrapped = False
            if wrapped:
                # the AES key of the segments is itself encrypted with a key inside the app
                SetIPTVPlayerLastHostError(_("DRM protection detected."))
                return None
        url = self.cm.meta.get("url") or url
        meta = dict(meta, iptv_proto="m3u8")
        links = getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)
        if links and "#EXT-X-STREAM-INF" in data and str(links[0]["url"]) != url:
            # a master whose variant playlists are gone (MBC outside its region: 404) never plays
            sts, variant = self.cm.getPage(links[0]["url"], {"header": header})
            if not sts or "#EXTM3U" not in (variant or ""):
                printDBG("OstoraTV: variant playlist not answering (HTTP %s) [%s]" % (self.cm.meta.get("status_code", 0), links[0]["url"]))
                SetIPTVPlayerLastHostError(_("This content is not available in your region."))
                return None
        return requireDownloaderForDisguisedHls(links)

    def getVideoLinks(self, videoUrl):
        printDBG("OstoraTV.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        meta = dict(getattr(videoUrl, "meta", {}))
        url = str(videoUrl)
        path = url.split("?", 1)[0].lower()
        if self.up.checkHostSupport(url) == 1:
            links = self.up.getVideoLinkExt(videoUrl)
        elif ".m3u8" in path or ".json" in path:
            links = self._hlsLinks(url, meta)
            if links is None:
                return []
        elif ".mpd" in path:
            links = getMPDLinksWithMeta(strwithmeta(url, meta), False, sortWithMaxBandwidth=99999999)
        else:
            links = [{"name": _domain(url), "url": strwithmeta(url, meta)}]
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], "", skip)
            except Exception:
                printExc()
        links = _parseSource(cItem.get("source", ""))[0]
        info = dict(meta.get("info", {}))
        if cItem.get("cat_title"):
            info.setdefault("genre", cItem["cat_title"])
        if links:
            info["source"] = ", ".join(sorted(set(_domain(link[0]) for link in links)))
        text = meta.get("plot", "") or "[/br]".join([cItem.get("title", "")] + (["%s: %s" % (_("Category"), cItem["cat_title"])] if cItem.get("cat_title") else []))
        icon = meta.get("poster") or cItem.get("icon", "")
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
        printDBG("OstoraTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if refresh or name is None:
            self.cache = {}  # live data and expiring tokens: fresh on every refresh / new start
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category in ("os_top", "os_cat"):
            self.listCategory(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, OstoraTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("ostoratv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "os_stream"
