# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - myTuner Radio (mytuner-radio.com), new host
#   Internet radio stations worldwide: top stations, continents -> countries -> all stations / genres,
#   search. The station page carries its stream list AES-256-CFB encrypted (key = the page's
#   "last-update" timestamp, see formatPlaylist()/d() in radio.min.js) - decrypted here with pyaes.
#   Live radio: audio rows, no watched flag. INFO = the station's "About" text, slogan, genres, location.
#   Station lists paged with First / Jump / Next (the paginator links the last page).
import re
from binascii import a2b_base64, unhexlify

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs import pyaes
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc


def GetConfigList():
    return []


def gettytul():
    return "https://mytuner-radio.com/"


STATION_RE = re.compile(r'<a[^>]+href="(/radio/[^"/]+-\d+/)"[^>]*>(.*?)</a>', re.S)


class MyTuner(CBaseHostClass):
    # what identifies a station row and is needed to open it again
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "live")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "mytuner", "cookie": "mytuner.cookie"})
        self.MAIN_URL = "https://mytuner-radio.com/"
        self.DEFAULT_ICON_URL = "https://static2.mytuner.mobi/static/icons/apple-touch-icon-144x144-precomposed.png"
        self.HEADER = {"User-Agent": self.cm.getDefaultUserAgent('chrome'),
                       "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                       "Accept-Language": "en-US,en;q=0.9"}
        self.defaultParams = {"header": self.HEADER}
        self.cacheContinents = []
        self.MENU = [{"category": "list_stations", "title": _("Top stations"), "url": self.getFullUrl("/radio/")},
                     {"category": "list_continents", "title": _("Countries")}] + self.searchItems()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    ###################################################
    # lists
    ###################################################
    def _parseStations(self, data):
        # the first "radio-list" block is the page's own list (the rest: "our radios", sidebar)
        start = data.find('class="radio-list"')
        if start < 0:
            return []
        end = data.find("</ul>", start)
        block = data[start:end if end > start else len(data)]
        items = []
        seen = set()
        for href, inner in STATION_RE.findall(block):
            if href in seen:
                continue
            seen.add(href)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'<span[^>]*>(.*?)</span>')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'alt="([^"]*)"')[0])
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(inner, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(inner, r'src="(http[^"]+)"')[0]
            items.append({"title": title, "url": self.getFullUrl(href), "icon": icon})
        return items

    def listStations(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        base = cItem.get("base_url") or re.sub(r"[?&]page=\d+$", "", cItem["url"])
        tpl = base + ("&" if "?" in base else "?") + "page={page}"
        sts, data = self.getPage(tpl.format(page=page) if page > 1 else base)
        if not sts:
            return
        items = self._parseStations(data)
        for it in items:
            params = {"good_for_fav": True, "live": True}
            params.update(it)
            self.addAudio(params)
        # the paginator links the last page ("Last page" arrow)
        pages = [int(p) for p in re.findall(r'href="[^"]*[?&]page=(\d+)"', data)]
        lastPage = max(pages + [page]) if pages else 0
        addPagingItems(self, dict(cItem, base_url=base), page, bool(items) and page < lastPage, lastPage, tpl)

    def _loadContinents(self):
        if self.cacheContinents:
            return self.cacheContinents
        sts, data = self.getPage(self.getFullUrl("/radio/"))
        if not sts:
            return []
        result = []
        for cid, block in re.findall(r'<div id="([^"]+)" class="tabcontent[^"]*">(.*?)</div>', data, re.S):
            countries = []
            for href, inner in re.findall(r'<a href="(/radio/country/[^"]+)">(.*?)</a>', block, re.S):
                name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'<span>(.*?)</span>')[0])
                if name:
                    countries.append({"title": name, "url": self.getFullUrl(href),
                                      "icon": self.cm.ph.getSearchGroups(inner, r'data-src="([^"]+)"')[0]})
            if countries:
                result.append((self.cleanHtmlStr(cid), countries))
        self.cacheContinents = result
        return result

    def listContinents(self, cItem):
        for name, countries in self._loadContinents():
            params = dict(cItem)
            params.update({"category": "list_countries", "title": name, "continent": name, "good_for_fav": False})
            self.addDir(params)

    def listCountries(self, cItem):
        for name, countries in self._loadContinents():
            if name != cItem.get("continent"):
                continue
            for it in countries:
                params = dict(cItem)
                params.update({"category": "list_country", "title": it["title"], "url": it["url"], "icon": it["icon"], "good_for_fav": True})
                self.addDir(params)

    def listCountry(self, cItem):
        for cat, title in (("list_stations", _("All stations")), ("list_genres", _("Genres"))):
            params = dict(cItem)
            params.update({"category": cat, "title": title, "page": 1, "good_for_fav": False})
            self.addDir(params)

    def listGenres(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="genres_div"', '</div>', False)[1]
        for href, inner in re.findall(r'<a href="([^"]+/genre/[^"]+)"[^>]*>(.*?)</a>', block, re.S):
            title = self.cleanHtmlStr(inner)
            if not title:
                continue
            params = dict(cItem)
            params.update({"category": "list_stations", "title": title, "url": self.getFullUrl(href), "page": 1, "good_for_fav": True})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        url = self.getFullUrl("/search/?q=%s" % urllib_quote_plus(searchPattern))
        sts, data = self.getPage(url)
        if not sts:
            return
        for it in self._parseStations(data):
            params = {"good_for_fav": True, "live": True}
            params.update(it)
            self.addAudio(params)

    ###################################################
    # links
    ###################################################
    @staticmethod
    def _decrypt(timestamp, ivHex, cipherB64):
        # CryptoJS.AES.decrypt(ct, Hex(genk(ts)), {iv, mode: CFB}) - genk: hex of the timestamp chars
        # repeated to 32 bytes; CryptoJS CFB = 128-bit segments + PKCS#7 padding
        ts = str(timestamp)
        key = unhexlify("".join("%02x" % ord(ts[i % len(ts)]) for i in range(32)))
        data = a2b_base64(cipherB64)
        pad = (16 - len(data) % 16) % 16
        aes = pyaes.AESModeOfOperationCFB(key, unhexlify(ivHex), segment_size=16)
        out = bytearray(aes.decrypt(data + b"\0" * pad)[:len(data)])
        if out and 0 < out[-1] <= 16:
            out = out[:-out[-1]]
        return ensure_str(bytes(out), errors="ignore").strip()

    def _expandPlaylist(self, url):
        # .pls / .m3u station playlists -> the stream urls inside
        sts, data = self.getPage(url)
        if not sts or not data:
            return []
        urls = re.findall(r'(?im)^\s*File\d+\s*=\s*(https?://\S+)', data)
        if not urls:
            urls = re.findall(r'(?m)^\s*(https?://\S+)', data)
        return urls

    def getLinksForVideo(self, cItem):
        printDBG("MyTuner.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        timestamp = self.cm.ph.getSearchGroups(data, r'id="last-update"\s+data-timestamp="([^"]+)"')[0]
        playlist = self.cm.ph.getSearchGroups(data, r'formatPlaylist\((\[.*?\])\)', ignoreCase=True)[0]
        try:
            entries = json_loads(playlist) if playlist else []
        except Exception:
            printExc()
            entries = []
        direct, hls = [], []
        for entry in entries:
            try:
                sType = (entry.get("type") or "").lower()
                if sType == "mms" or not timestamp:
                    continue
                url = self._decrypt(timestamp, entry["iv"], entry["cipher"])
                if not self.cm.isValidUrl(url):
                    continue
                low = url.lower().split("?")[0]
                if sType == "hls" or low.endswith(".m3u8"):
                    hls.append(("HLS", self.up.decorateUrl(url, {"iptv_proto": "m3u8", "iptv_livestream": True})))
                elif sType in ("pls", "m3u") or low.endswith(".pls") or low.endswith(".m3u"):
                    for sub in self._expandPlaylist(url):
                        direct.append((sType.upper() or "STREAM", self.up.decorateUrl(sub, {"iptv_livestream": True})))
                else:
                    if re.match(r"^https?://[^/]+:\d+/?$", url):
                        # SHOUTcast v1 answers a browser User-Agent with its status page - "/;" always gives the stream
                        url = url.rstrip("/") + "/;"
                    direct.append(((sType or "stream").upper(), self.up.decorateUrl(url, {"iptv_livestream": True})))
            except Exception:
                printExc()
        urlTab = []
        seen = set()
        for name, url in direct + hls:
            if url in seen:
                continue
            seen.add(url)
            urlTab.append({"name": "%s (%d)" % (name, len(urlTab) + 1), "url": url, "need_resolve": 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return urlTab

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("MyTuner.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            text = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="description">', '</div>', False)[1]) or text
            slogan = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<div class="slogan">(.*?)</div>')[0])
            if slogan:
                text = slogan + ("[/br][/br]" + text if text else "")
            genresBlock = self.cm.ph.getDataBeetwenMarkers(data, '<div class="genres">', '</div>', False)[1]
            genres = [self.cleanHtmlStr(g) for g in re.findall(r'<a[^>]*>(.*?)</a>', genresBlock, re.S)]
            if genres:
                otherInfo["genres"] = ", ".join([g for g in genres if g])
            crumbs = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="breadcrumbs">', '</ul>', False)[1]
            place = [self.cleanHtmlStr(c) for c in re.findall(r'<a[^>]*>(.*?)</a>', crumbs, re.S)]
            if place:
                otherInfo["country"] = ", ".join([p for p in place if p])
            icon = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0] or icon
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("type") == "audio":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("MyTuner.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_stations":
            self.listStations(self.currItem)
        elif category == "list_continents":
            self.listContinents(self.currItem)
        elif category == "list_countries":
            self.listCountries(self.currItem)
        elif category == "list_country":
            self.listCountry(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, MyTuner(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get("type") == "audio"
