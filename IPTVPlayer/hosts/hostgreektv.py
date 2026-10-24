# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
#   catch-up TV of three Greek channels: SKAI (skai.gr/tv), OPEN (tvopen.gr) and ALPHA (alphatv.gr);
#   shows -> seasons -> episodes, newest first, direct HLS / MP4 of the channels' own CDNs (no hosters);
#   search: the OPEN video search plus the show titles of SKAI and ALPHA
#   live channels: the public HLS streams of the national, Cypriot, regional, music and church stations
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://www.skai.gr/tv/"


SKAI = "https://www.skai.gr"
SKAI_VOD = "https://videostream.skai.gr/skaivod/_definst_/mp4:skai/%s/playlist.m3u8"
SKAI_CATS = (("seires", "Σειρές"), ("psuchagogia", "Ψυχαγωγία"), ("enimerosi", "Ενημέρωση"), ("ntokimanter", "Ντοκιμαντέρ"), ("athlitika", "Αθλητικά"))
OPEN = "https://www.tvopen.gr"
ALPHA = "https://www.alphatv.gr"
ALPHA_SECTIONS = (("/series/", "Σειρές"), ("/shows/", "Εκπομπές"))
LOCAL_PAGE = 50
CACHE_TTL = 600
OPEN_CAT_PAGE = 8  # templates/data/videos: 8 videos a page
OPEN_VIDS_PAGE = 10  # templates/data/showVideos: 11-12 videos a page (an ad slot takes one)
OPEN_SEARCH_MAX = 100
GEO_GR = "Greece / Cyprus"
# live channels: the stations' own public HLS streams (ERT, ANT1, Alpha, Open, Skai, Star, Mega, Cyprus, regional / music / church)
LIVE_CHANNELS = (
    ("Πανελλαδικά", (
        ("ERT1", "https://ert-live.siliconweb.com/bpk-tv/ERT1/default/index.m3u8"),
        ("ERT2 Sport", "https://ert-live.siliconweb.com/bpk-tv/ERT2/default/index.m3u8"),
        ("ERT3", "https://ert-live.ascdn.broadpeak.io/bpk-tv/ERT3/default/index.m3u8"),
        ("ERT World", "https://ert-ucdn.broadpeak-aas.com/bpk-tv/ERTCosmos/default/index.m3u8"),
        ("ANT1", "https://mcdn.antennaplus.gr/live/media0/Ant1/HLS/Ant1.m3u8"),
        ("ANT1 Drama", "https://mcdn.antennaplus.gr/live/media0/Drama/HLS/Drama.m3u8"),
        ("ANT1 Comedy", "https://mcdn.antennaplus.gr/live/media0/Comedy/HLS/Comedy.m3u8"),
        ("MAK", "https://mcdn.antennaplus.gr/live/media0/MAK/HLS/MAK.m3u8"),
        ("ALPHA", "https://alphatvlive2-ak.siliconweb.com/alphatvlive/live_abr/playlist.m3u8"),
        ("OPEN", "https://liveopen.siliconweb.com/openTvLive/liveopen/playlist.m3u8"),
        ("SKAI", "https://skai-live.siliconweb.com/media/cambria4/index.m3u8"),
        ("STAR", "https://livestar.siliconweb.com/starvod/star4/star4.m3u8"),
        ("STAR International", "https://livestar.siliconweb.com/starvod/star_int/star_int.m3u8"),
        ("MEGA", "https://c98db5952cb54b358365984178fb898a.msvdn.net/live/S65837586/neDzj4HuSpPr/playlist.m3u8"))),
    ("Ειδήσεις", (
        ("ERT News", "https://702e2e484b144c71ba38bca0d41f37cd.msvdn.net/bpk-tv/ERTNews/default/index.m3u8"),
        ("MEGA News", "https://c98db5952cb54b358365984178fb898a.msvdn.net/live/S99841657/NU0xOarAMJ5X/chunklist_b3200000.m3u8"))),
    ("Παιδικά", (
        ("ERT Kids", "https://ert-live.siliconweb.com/bpk-tv/ERTKids/default/index.m3u8"),)),
    ("Παγκύπρια", (
        ("SIGMA", "https://ottstream4.primetel.com.cy/streaming-web/SigmaLive/playlist_2000.m3u8"),)),
    ("Περιφερειακά", (
        ("Delta TV", "http://81.171.10.42:1935/liveD/DStream.sdp/playlist.m3u8"),  # NOSONAR - the Wowza server has no https
        ("Ionian Channel", "https://stream.ioniantv.gr/ionian/live_abr/ionian/live_1080p/chunks.m3u8"))),
    ("Ταινίες", (
        ("Cinema Classics", "https://tv.mediacp.eu:8081/cinemaclassics/index.m3u8"),
        ("Ellas World", "https://ellastvmax.ath.cx/freetv/promo/index.m3u8"),
        ("Village World", "https://ellastvmax.gotdns.com/freetv/village-world/index.m3u8"),
        ("Diavata TV", "https://183.bozztv.com/giatv/giatv-diavatatvonline/diavatatvonline/playlist.m3u8"),
        ("Lampsi TV", "https://neon.streams.gr:8081/lampsitv/tracks-v1a1/mono.m3u8"),
        ("Dipolo TV", "https://mcv3.streams.gr/stream/dipolotv/index.m3u8"),
        ("Net TV Toronto", "https://eu1.streams.gr:8081/netvtoronto/index.m3u8"))),
    ("Μουσική", (
        ("Real Music TV", "https://webtv.topwebhost.gr:3302/stream/play.m3u8"),
        # NOSONAR on the next line: the path part is the station's public stream id, not an (OVH) api key
        ("Xalastra TV", "https://alpha.streamhub.gr/tv/hls/MWAF31fK8gUQ74QsNYoZI1Ld9NPtyrzm/playlist.m3u8"),  # NOSONAR
        ("Baraza TV", "https://eco.streams.ovh:8081/barazatv/index.m3u8"),
        ("Baraza Laika", "https://gra1.crystalweb.net:1936/barazatv/barazatv/playlist.m3u8"),
        ("MAD World", "https://ellastvmax.gotdns.com/freetv/madworldtv/index.m3u8"),
        ("Panik TV", "https://livetv.streams.ovh:1936/paniktv/paniktv/playlist.m3u8"))),
    ("Εκκλησία", (
        ("4E", "http://eu2.tv4e.gr:1935/live/myStream.sdp/playlist.m3u8"),  # NOSONAR - the Wowza server has no https
        ("Open Ekklisia", "https://liveopen.siliconweb.com/openTvLive/openEcclessia/chunks.m3u8"))),
)
FOLDERS =("skai_show", "skai_season", "open_show", "open_cat", "open_vids", "alpha_show", "alpha_season")


class GreekTV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "greektv", "cookie": "greektv.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/greektv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER}
        self.cache = {}
        self.watchedHelper = IPTVWatchedHelper("greektv")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("type", "") == "video" and cItem.get("category") == "video":
                url = re.sub(r"^https?://(?:www\.)?", "", str(cItem.get("url", "") or "").strip())
                return "video:%s" % url if url else ""
            category = cItem.get("category", "")
            if category in FOLDERS and cItem.get("path"):
                return "%s:%s" % (category, cItem["path"])
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        if url.startswith(OPEN):
            # tvopen.gr is behind Cloudflare (no challenge so far)
            return self.cm.getPageCFProtection(url, addParams, post_data)
        return self.cm.getPage(url, addParams, post_data)

    def _cached(self, url):
        # the last few pages, for the local paging of long episode lists and the title search
        now = time.time()
        if url in self.cache and now - self.cache[url][0] < CACHE_TTL:
            return True, self.cache[url][1]
        sts, data = self.getPage(url)
        if sts and data:
            if len(self.cache) >= 10:
                self.cache.clear()
            self.cache[url] = (now, data)
        return sts, data

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except Exception:
            return 1

    @staticmethod
    def _base(cItem):
        # the folder url without the "#page=" of a Jump row
        return str(cItem.get("url", "")).split("#", 1)[0]

    def _child(self, cItem, params):
        item = stripPagerKeys(dict(cItem), ("seasons", "season", "season_id", "episode", "s_title", "cat", "cat_id", "showid", "section", "group",
                                            "letters", "cid", "parent_key", "search_item"))
        item.update({"good_for_fav": True, "desc": "", "icon": cItem.get("icon", "")})
        item.update(params)
        return item

    def _localPaging(self, cItem, items, addFunc):
        page = self._page(cItem)
        last = (len(items) + LOCAL_PAGE - 1) // LOCAL_PAGE
        for item in items[(page - 1) * LOCAL_PAGE:page * LOCAL_PAGE]:
            addFunc(item)
        if last > 1:
            addPagingItems(self, cItem, page, page < last, last, self._base(cItem) + "#page={page}")

    def _episodeTitle(self, sTitle, title, season, episode, extra=""):
        if IsMediaNamingNormalized() and sTitle and season and episode:
            title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            if extra:
                title += " - " + extra
        return title

    @staticmethod
    def _date(value):
        # "2026-10-23 21:00:00" -> "23/10/2026 21:00"
        match = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?", str(value or ""))
        if not match:
            return ""
        ret = "%s/%s/%s" % (match.group(3), match.group(2), match.group(1))
        if match.group(4) and match.group(4) + match.group(5) != "0000":
            ret += " %s:%s" % (match.group(4), match.group(5))
        return ret

    def _addVideo(self, cItem, params):
        item = self._child(cItem, params)
        item.update({"category": "video", "good_for_fav": True})
        self.addVideo(item)

    ###################################################
    # SKAI
    ###################################################
    def _skaiData(self, data, key):
        # the page JSON: "var data = {...};" (two of them, the second one is the page's)
        for raw in re.findall(r"(?m)var data\s*=\s*(\{.*?\});\s*$", data):
            try:
                obj = ensure_str_deep(json_loads(raw))
            except Exception:
                continue
            if isinstance(obj, dict) and key in obj:
                return obj
        return {}

    @staticmethod
    def _skaiSeasonLabel(caption):
        match = re.match(r"sezon-(\d{4})-(\d{4})$", caption)
        if match:
            return "Σεζόν %s-%s" % (match.group(1), match.group(2))
        match = re.match(r"(\d+)os-kuklos$", caption)
        if match:
            return "Κύκλος %s" % match.group(1)
        return caption.replace("-", " ")

    @staticmethod
    def _skaiSeasonNum(caption):
        match = re.match(r"(\d+)os-kuklos$", caption or "")
        return match.group(1) if match else ""

    def _skaiShows(self, cat):
        # one category page -> [{title, icon, desc, path (show), seasons [[url, caption], ...]}], current first, then the archive
        # cached: the search reads all five, and skai.gr answers 429 to quick bursts
        sts, data = self._cached("%s/tv/shows/%s" % (SKAI, cat))
        if not sts:
            return []
        # the list rows (on every category page, the tiles only on some): image link, then title + text link
        texts = {}
        for url, title, rest in re.findall(r'(?s)<a href="(/tv/show/[^"]+)">\s*<div class="h2">(.*?)</div>(.*?)</a>', data):
            desc = self.cm.ph.getSearchGroups(rest, r'(?s)<div class="h3[^"]*">(.*?)</div>')[0]
            texts.setdefault(url, (self.cleanHtmlStr(re.sub(r"(?s)<span.*?</span>", "", title)), self.cleanHtmlStr(re.sub(r"(?s)<b>.*?</b>", "", desc))))
        shows = []
        byPath = {}
        for url, icon, alt in re.findall(r'<a href="(/tv/show/[^"]+)"\s+class="resio">\s*<img src="([^"]+)" alt="([^"]*)"', data):
            match = re.search(r"(/tv/show/[^/]+/[^/]+)/([^/?#]+)$", url)
            if not match:
                continue
            path, caption = match.group(1), match.group(2)
            title, desc = texts.get(url, ("", ""))
            title = title or self.cleanHtmlStr(alt)
            if not title:
                continue
            show = byPath.get(path)
            if show is None:
                show = {"title": title, "icon": icon, "desc": desc, "path": path, "seasons": []}
                byPath[path] = show
                shows.append(show)
            if caption not in [s[1] for s in show["seasons"]]:
                show["seasons"].append([SKAI + path + "/" + caption, caption])
        for show in shows:
            # newest season first: by the numbers in "sezon-2025-2026" / "22os-kuklos"
            show["seasons"].sort(key=lambda s: [int(x) for x in re.findall(r"\d+", s[1])] or [0], reverse=True)
        return shows

    def _addSkaiShow(self, cItem, show, desc=""):
        params = {"title": show["title"], "icon": show["icon"], "desc": desc or show["desc"], "s_title": show["title"], "station": "skai"}
        if len(show["seasons"]) == 1:
            url, caption = show["seasons"][0]
            params.update({"category": "skai_season", "url": url, "path": url.replace(SKAI, ""), "season": self._skaiSeasonNum(caption)})
        else:
            params.update({"category": "skai_show", "url": SKAI + show["path"], "path": show["path"], "seasons": show["seasons"]})
        self.addDir(self._child(cItem, params))

    def listSkaiCats(self, cItem):
        for cat, title in SKAI_CATS:
            self.addDir(self._child(cItem, {"category": "skai_cat", "title": title, "url": "%s/tv/shows/%s" % (SKAI, cat), "cat": cat}))

    def listSkaiCat(self, cItem):
        for show in self._skaiShows(cItem.get("cat", "")):
            self._addSkaiShow(cItem, show)

    def listSkaiShow(self, cItem):
        for url, caption in cItem.get("seasons") or []:
            self.addDir(self._child(cItem, {"category": "skai_season", "title": "%s - %s" % (cItem.get("s_title", ""), self._skaiSeasonLabel(caption)),
                                            "url": url, "path": url.replace(SKAI, ""), "season": self._skaiSeasonNum(caption)}))

    def listSkaiSeason(self, cItem):
        url = self._base(cItem)
        sts, data = self._cached(url)
        if not sts:
            return
        page = self._skaiData(data, "show")
        show = page.get("show") or {}
        sTitle = cItem.get("s_title") or self.cleanHtmlStr(show.get("title", ""))
        episodes = [e for e in (page.get("episodes") or []) if isinstance(e, dict) and e.get("link")]
        if episodes:
            # the season page shows the newest 12, the page of the newest episode lists all of them
            sts, epData = self._cached(SKAI + "/tv" + episodes[0]["link"])
            full = self._skaiData(epData, "episodes").get("episodes") if sts else None
            if isinstance(full, list) and len(full) >= len(episodes):
                episodes = [e for e in full if isinstance(e, dict) and e.get("link")]
            season = cItem.get("season", "")
            # geolocation "2" / geoblock_id "GR,CY": the videos only play in Greece and Cyprus
            geo = str(show.get("geolocation", "0") or "0") != "0"

            def addEpisode(ep):
                title = self.cleanHtmlStr(ep.get("title", "")).replace(" | ", " - ")
                date = self._date(ep.get("start"))
                if not re.search(r"\d", title) and date:
                    title = "%s - %s" % (title, date.split(" ")[0])
                epNum = str(ep.get("episode_number") or "")
                desc = " | ".join([x for x in (date, _("Episode") + " " + epNum if epNum else "", _("Only available in %s") % GEO_GR if geo else "") if x])
                text = self.cleanHtmlStr(ep.get("short_descr", ""))
                self._addVideo(cItem, {"title": self._episodeTitle(sTitle, title, season, epNum), "url": SKAI + "/tv" + ep["link"],
                                       "icon": ep.get("img") or cItem.get("icon", ""), "desc": "[/br]".join([x for x in (desc, text) if x]),
                                       "s_title": sTitle, "season": season, "episode": epNum, "station": "skai", "geo": geo})
            self._localPaging(cItem, episodes, addEpisode)
            return
        # no episodes (archive seasons): the clips of the season
        for clip in page.get("clips") or []:
            if not isinstance(clip, dict) or not clip.get("link"):
                continue
            self._addVideo(cItem, {"title": self.cleanHtmlStr(clip.get("title", "")).replace(" | ", " - "), "url": SKAI + "/tv" + clip["link"],
                                   "icon": clip.get("img") or cItem.get("icon", ""), "desc": self._date(clip.get("start")), "station": "skai"})

    def _skaiLinks(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        page = self._skaiData(data, "episode")
        media = [m for m in (page.get("episode") or []) if isinstance(m, dict) and m.get("media_item_file")]
        # the full episode (media_type 1) first, then trailers / clips / news items
        media.sort(key=lambda m: 0 if str(m.get("media_type", "")) == "1" else 1)
        urlTab = []
        geo = bool(cItem.get("geo")) or str((page.get("episodemain") or {}).get("geolocation", "0") or "0") != "0"
        drm = False
        meta = {"User-Agent": self.HEADER["User-Agent"], "Referer": SKAI + "/", "Origin": SKAI}
        for idx, item in enumerate(media):
            mFile = item["media_item_file"].strip()
            label = "" if idx == 0 else self.cleanHtmlStr(item.get("media_item_title", ""))
            if str(item.get("drmflag", "0") or "0") != "0":
                drm = True
                continue
            if "youtube.com/" in mFile or "youtu.be/" in mFile:
                url = mFile if mFile.startswith("http") else "https://" + mFile.lstrip("/")
                urlTab.append({"name": label or "YouTube", "url": url, "need_resolve": 1})
                continue
            if str(item.get("geolocation", "0") or "0") != "0":
                geo = True
            hlsUrl = strwithmeta(SKAI_VOD % mFile.lstrip("/"), dict(meta, iptv_proto="m3u8"))
            links = getDirectM3U8Playlist(hlsUrl, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
            for link in links:
                link["need_resolve"] = 0
                if label:
                    link["name"] = "%s - %s" % (link.get("name", ""), label)
                urlTab.append(link)
        if not urlTab:
            if geo:
                SetIPTVPlayerLastHostError(_("This content is not available in your region.") + " (%s)" % GEO_GR)
            elif drm:
                SetIPTVPlayerLastHostError(_("Video with DRM protection."))
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))
        return urlTab

    def _skaiInfo(self, cItem):
        # a show with several seasons: the page of its newest season
        url = cItem["seasons"][0][0] if cItem.get("category") == "skai_show" and cItem.get("seasons") else self._base(cItem)
        sts, data = self.getPage(url)
        if not sts:
            return None
        info = {"station": "SKAI"}
        if cItem.get("type") == "video":
            page = self._skaiData(data, "episode")
            ep = page.get("episodemain") or {}
            if not ep and page.get("episode"):
                ep = page["episode"][0]
            title = self.cleanHtmlStr(ep.get("title") or ep.get("media_item_title") or "")
            text = self.cleanHtmlStr(ep.get("descr") or ep.get("short_descr") or "")
            icon = ep.get("img") or ep.get("img2") or cItem.get("icon", "")
            if ep.get("start"):
                info["broadcast"] = self._date(ep["start"])
            if cItem.get("geo") or str(ep.get("geolocation", "0") or "0") != "0":
                info["status"] = _("Only available in %s") % GEO_GR
        else:
            page = self._skaiData(data, "show")
            show = page.get("show") or {}
            title = self.cleanHtmlStr(show.get("title", ""))
            if show.get("subtitle"):
                info["type"] = self.cleanHtmlStr(show["subtitle"])
            text = self.cleanHtmlStr(show.get("descr") or show.get("short_descr") or "")
            plan = self.cleanHtmlStr(show.get("descr2") or "")
            if plan:
                text = "%s[/br][/br]%s" % (text, plan)
            icon = show.get("logo") or show.get("img") or cItem.get("icon", "")
            cast = []
            for person in page.get("persons") or []:
                name = self.cleanHtmlStr((person or {}).get("title2") or "")
                if name and person.get("subtitle"):
                    name = "%s (%s)" % (name, self.cleanHtmlStr(person["subtitle"]))
                if name:
                    cast.append(name)
            if cast:
                info["cast"] = ", ".join(cast[:12])
            if cItem.get("seasons"):
                info["seasons"] = str(len(cItem["seasons"]))
        return title, text, icon, info

    ###################################################
    # OPEN
    ###################################################
    def _openCards(self, data):
        ret = []
        for slug, img, title, airtime, details in re.findall(r'(?s)<a href="/([A-Za-z0-9_-]+)">(<img [^>]+>)\s*<div class="shadow">.*?<span class="movietitle">(.*?)</span><span class="airtime">(.*?)</span><span class="details">(.*?)</span>', data):
            # lazy images: src = a placeholder, alt-src = the picture
            icon = self.cm.ph.getSearchGroups(img, r'alt-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(img, r'\ssrc="([^"]+)"')[0]
            ret.append({"slug": slug, "icon": self.getFullIconUrl(icon, OPEN + "/"), "title": self.cleanHtmlStr(title),
                        "desc": " | ".join([x for x in (self.cleanHtmlStr(airtime), self.cleanHtmlStr(details)) if x])})
        return ret

    def _addOpenShow(self, cItem, card):
        self.addDir(self._child(cItem, {"category": "open_show", "title": card["title"], "url": "%s/%s" % (OPEN, card["slug"]), "path": card["slug"],
                                        "icon": card["icon"], "desc": card["desc"], "s_title": card["title"], "station": "open"}))

    def listOpenMain(self, cItem):
        sts, data = self.getPage(OPEN + "/shows")
        if not sts:
            return
        for sid, title in re.findall(r'<h2 class="catTitle" id="([^"]+)">(.*?)</h2>', data):
            self.addDir(self._child(cItem, {"category": "open_section", "title": self.cleanHtmlStr(title), "url": OPEN + "/shows", "section": sid}))
        letters = re.findall(r"'([^',]+)'", self.cm.ph.getSearchGroups(data, r"var L = \[([^\]]+)\]")[0])
        if letters:
            self.addDir(self._child(cItem, {"category": "open_letters", "title": _("A-Z"), "url": OPEN + "/shows", "letters": letters}))

    def listOpenSection(self, cItem):
        sts, data = self.getPage(OPEN + "/shows")
        if not sts:
            return
        block = self.cm.ph.getSearchGroups(data, r'(?s)<h2 class="catTitle" id="%s">.*?<div class="catArea">(.*?)</div>\s*(?:<h2|</div>)' % re.escape(cItem.get("section", "")))[0]
        for card in self._openCards(block):
            self._addOpenShow(cItem, card)

    def listOpenLetters(self, cItem):
        for letter in cItem.get("letters") or []:
            self.addDir(self._child(cItem, {"category": "open_letter", "title": letter, "url": "%s/shows/%s" % (OPEN, urllib_quote(letter)), "letters": []}))

    def listOpenLetter(self, cItem):
        sts, data = self.getPage(self._base(cItem))
        if not sts:
            return
        for card in self._openCards(data):
            self._addOpenShow(cItem, card)

    def listOpenShow(self, cItem):
        # the full episodes are a video category of their own (the one of the newest episode on the show page),
        # "Video" of the show lists every clip
        slug = cItem.get("path", "")
        sts, data = self.getPage("%s/%s" % (OPEN, slug))
        if not sts:
            return
        catId = ""
        catName = ""
        first = self.cm.ph.getSearchGroups(data, r'class="videosWrapper"><a href="(/watch/[^"]+)"')[0]
        if first:
            sts, wData = self.getPage(OPEN + first)
            if sts:
                catId, catName = self.cm.ph.getSearchGroups(wData, r'class="videoCategory" href="/videos/(\d+)/[^"]*">([^<]*)<', 2)
        sTitle = cItem.get("s_title") or cItem.get("title", "")
        if catId:
            self.addDir(self._child(cItem, {"category": "open_cat", "title": "%s - %s" % (_("Episodes"), self.cleanHtmlStr(catName)) if catName else _("Episodes"),
                                            "url": "%s/videos/%s" % (OPEN, catId), "path": catId, "cat_id": catId, "s_title": sTitle}))
        # every video of the show (clips too) - new shows have none yet
        sts, data = self.getPage("%s/%s/videos" % (OPEN, slug))
        showId = self.cm.ph.getSearchGroups(data, r"showVideos\?showid=(\d+)")[0] if sts else ""
        if showId and "/watch/" in data:
            self.addDir(self._child(cItem, {"category": "open_vids", "title": _("All videos"), "url": "%s/%s/videos" % (OPEN, slug), "path": slug,
                                            "showid": showId, "s_title": sTitle}))
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))

    def _openVideoRows(self, data):
        ret = []
        # the search answer writes the href as "&#xA;   /watch/..."
        for cid, slug, rest in re.findall(r'(?s)<a href="(?:&#xA;)?\s*/watch/(\d+)/([^"]+)">(.*?)</a>', data):
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(rest, r'<span class="title">(.*?)</span>')[0] or self.cm.ph.getSearchGroups(rest, r'<b>(.*?)</b>')[0])
            icon = self.cm.ph.getSearchGroups(rest, r'alt-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(rest, r'src="([^"]+)"')[0]
            if "LoadingBG" in icon or not icon:
                icon = ""
            desc = self.cleanHtmlStr(re.sub(r"(?s)<b>.*?</b>", "", self.cm.ph.getSearchGroups(rest, r'(?s)<span class="details">(.*?)</span>')[0]))
            if title and cid not in [r["cid"] for r in ret]:
                ret.append({"cid": cid, "slug": slug.strip(), "title": title, "icon": self.getFullIconUrl(icon, OPEN + "/") if icon else "", "desc": desc})
        return ret

    def _addOpenVideo(self, cItem, row):
        title = row["title"]
        season = ""
        episode = self.cm.ph.getSearchGroups(title, r"Επεισόδιο\s+(\d+)")[0]
        match = re.search(r"\b(\d+)ος\s+κύκλος", title)
        if match:
            season = match.group(1)
        self._addVideo(cItem, {"title": self._episodeTitle(cItem.get("s_title", ""), title, season, episode), "url": "%s/watch/%s/%s" % (OPEN, row["cid"], row["slug"]),
                               "cid": row["cid"], "icon": row["icon"] or cItem.get("icon", ""), "desc": row["desc"], "season": season, "episode": episode,
                               "station": "open"})

    def listOpenCat(self, cItem):
        page = self._page(cItem)
        catId = cItem.get("cat_id", "")
        tpl = OPEN + "/templates/data/videos?category=%s&p={page}" % catId
        sts, data = self.getPage(tpl.format(page=page))
        if not sts:
            return
        rows = self._openVideoRows(data)
        for row in rows:
            self._addOpenVideo(cItem, row)
        addPagingItems(self, cItem, page, len(rows) >= OPEN_CAT_PAGE, 0, tpl)

    def listOpenVids(self, cItem):
        page = self._page(cItem)
        showId = cItem.get("showid", "")
        if not showId:
            sts, data = self.getPage("%s/%s/videos" % (OPEN, cItem.get("path", "")))
            if not sts:
                return
            showId = self.cm.ph.getSearchGroups(data, r"showVideos\?showid=(\d+)")[0]
            if not showId:
                return
        tpl = OPEN + "/templates/data/showVideos?showid=%s&p={page}" % showId
        sts, data = self.getPage(tpl.format(page=page))
        if not sts:
            return
        rows = self._openVideoRows(data)
        for row in rows:
            self._addOpenVideo(cItem, row)
        addPagingItems(self, cItem, page, len(rows) >= OPEN_VIDS_PAGE, 0, tpl, {"showid": showId})

    def _openSearch(self, cItem, pattern):
        # the current shows by title, then the site's own video search
        sts, data = self.getPage(OPEN + "/shows")
        seen = set()
        for card in self._openCards(data) if sts else []:
            if card["slug"] not in seen and self._match(pattern, card["title"]):
                seen.add(card["slug"])
                card["desc"] = " | ".join([x for x in ("OPEN", card["desc"]) if x])
                self._addOpenShow(cItem, card)
        sts, data = self.getPage(OPEN + "/templates/data/search?q=" + urllib_quote_plus(pattern))
        if not sts:
            return
        # one answer with every hit (hundreds for a common word), newest first
        for row in self._openVideoRows(data)[:OPEN_SEARCH_MAX]:
            row["desc"] = " | ".join([x for x in ("OPEN", row["desc"]) if x])
            self._addOpenVideo(cItem, row)

    def _openLinks(self, cItem):
        cid = cItem.get("cid") or self.cm.ph.getSearchGroups(cItem.get("url", ""), r"/watch/(\d+)")[0]
        if not cid:
            return []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=cItem["url"], Accept="application/json, text/javascript, */*; q=0.01")
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        sts, data = self.getPage(OPEN + "/templates/data/player?cid=" + cid, params)
        if not sts:
            return []
        try:
            data = ensure_str_deep(json_loads(data))
        except Exception:
            printExc()
            return []
        meta = {"User-Agent": self.HEADER["User-Agent"], "Referer": OPEN + "/"}
        urlTab = []
        if self.cm.isValidUrl(data.get("stream", "")):
            links = getDirectM3U8Playlist(strwithmeta(data["stream"], dict(meta, iptv_proto="m3u8")), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
            for link in links:
                link["need_resolve"] = 0
                urlTab.append(link)
        if self.cm.isValidUrl(data.get("httpstream", "")):
            urlTab.append({"name": "MP4", "url": strwithmeta(data["httpstream"], meta), "need_resolve": 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return urlTab

    def _metaInfo(self, data):
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:title" content="([^"]*)"')[0])
        title = re.sub(r"\s*\|\s*(?:OPEN TV|AlphaTV)$", "", title)
        text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        icon = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]*)"')[0]
        return title, text, icon

    def _openInfo(self, cItem):
        url = cItem["url"] if cItem.get("type") == "video" else "%s/%s/about" % (OPEN, cItem.get("path", ""))
        sts, data = self.getPage(url)
        if not sts:
            return None
        title, text, icon = self._metaInfo(data)
        info = {"station": "OPEN"}
        about = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="(?:about|showAbout|text)[^"]*">(.*?)</div>')[0])
        if len(about) > len(text):
            text = about
        date = self.cm.ph.getSearchGroups(data, r'<meta name="publish-date" content="([^"]+)"')[0]
        if date:
            info["released"] = self._date(date)
        return title, text, icon, info

    ###################################################
    # ALPHA
    ###################################################
    def _alphaCards(self, data):
        ret = []
        for chunk in data.split('<div class="card has_fav ')[1:]:
            cls, body = chunk.split('"', 1) if '"' in chunk else (chunk, "")
            if "vod-unavailable" in cls:
                continue
            url, title = self.cm.ph.getSearchGroups(body, r'<a href="(https://www\.alphatv\.gr/[^"]+)" title="([^"]*)"', 2)
            if not url:
                continue
            ret.append({"url": url, "title": self.cleanHtmlStr(title), "cls": cls, "icon": self.cm.ph.getSearchGroups(body, r'data-src="([^"]+)"')[0],
                        "desc": self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)<div class="card__lead">(.*?)</div>')[0])})
        return ret

    def _alphaGroups(self, data):
        # "group__header_title" sections of /series/ and /shows/ -> [(title, html)]
        parts = re.split(r'<h2 class="group__header_title">', data)
        ret = []
        for part in parts[1:]:
            title = self.cleanHtmlStr(part.split("</h2>", 1)[0])
            if title:
                ret.append((title, part))
        return ret

    def _addAlphaShow(self, cItem, card):
        path = re.sub(r"^https?://[^/]+", "", card["url"])
        self.addDir(self._child(cItem, {"category": "alpha_show", "title": card["title"], "url": card["url"], "path": path, "icon": card["icon"],
                                        "desc": card["desc"], "s_title": card["title"], "station": "alpha"}))

    def listAlphaMain(self, cItem):
        for path, title in ALPHA_SECTIONS:
            self.addDir(self._child(cItem, {"category": "alpha_groups", "title": title, "url": ALPHA + path}))

    def listAlphaGroups(self, cItem):
        sts, data = self.getPage(self._base(cItem))
        if not sts:
            return
        for title, part in self._alphaGroups(data):
            if self._alphaCards(part):
                self.addDir(self._child(cItem, {"category": "alpha_group", "title": title, "group": title}))

    def listAlphaGroup(self, cItem):
        sts, data = self.getPage(self._base(cItem))
        if not sts:
            return
        seen = set()
        for title, part in self._alphaGroups(data):
            if title != cItem.get("group"):
                continue
            for card in self._alphaCards(part):
                if card["url"] not in seen and not self._isAlphaEpisode(card["url"]):
                    seen.add(card["url"])
                    self._addAlphaShow(cItem, card)

    @staticmethod
    def _isAlphaEpisode(url):
        return bool(re.search(r"/(?:show-)?episode/|/broadcast/", url))

    @staticmethod
    def _alphaEpisodesUrl(showUrl):
        return showUrl.rstrip("/") + ("/broadcasts/" if "/newscast/" in showUrl else "/episodes/")

    def _alphaPageUrl(self, base, season, page):
        url = base + ("paged/%d/" % page if page > 1 else "")
        return url + "?" + ("season=%s&" % season if season else "") + "order=desc"

    def listAlphaShow(self, cItem):
        base = self._alphaEpisodesUrl(self._base(cItem))
        url = self._alphaPageUrl(base, "", 1)
        sts, data = self._cached(url)
        if not sts:
            return
        seasons = re.findall(r'<a title="([^"]+)"\s*href="[^"]*[?&]season=(season-(\d+))"', data)
        if len(seasons) > 1:
            seasons.sort(key=lambda s: int(s[2]), reverse=True)
            for title, season, num in seasons:
                self.addDir(self._child(cItem, {"category": "alpha_season", "title": "%s - %s" % (cItem.get("s_title", ""), _("Season %s") % num),
                                                "path": "%s#%s" % (cItem.get("path", ""), season), "season_id": season, "season": num,
                                                "s_title": cItem.get("s_title", "")}))
            return
        # one season: its episodes in place of the show (the pager rows list the show again)
        params = dict(cItem)
        params.update({"season_id": seasons[0][1] if seasons else "", "season": seasons[0][2] if seasons else ""})
        self._listAlphaEpisodes(params, base)

    def listAlphaSeason(self, cItem):
        self._listAlphaEpisodes(cItem, self._alphaEpisodesUrl(self._base(cItem)))

    def _listAlphaEpisodes(self, cItem, base):
        page = self._page(cItem)
        season = cItem.get("season_id", "")
        sts, data = self._cached(self._alphaPageUrl(base, season, page))
        if not sts:
            return
        sTitle = cItem.get("s_title", "")
        for card in self._alphaCards(data):
            if not self._isAlphaEpisode(card["url"]):
                continue
            title = card["title"]
            sNum, eNum, extra = "", "", ""
            # "Σ1 – ΕΠΕΙΣΟΔΙΟ 70", "Σ4 Επ.17 Μπαρούτη", "10η Εντολή Σ.4 Επ.16 Αlert"
            match = re.search(r"Σ\.?\s*(\d+)\s*[-–]?\s*(?:ΕΠΕΙΣΟΔΙΟ|Επεισόδιο|ΕΠ\.?|Επ\.?)\s*(\d+)\s*(?:[-–]\s*)?(.*)$", title)
            if match:
                sNum, eNum, extra = match.group(1), match.group(2), (match.group(3) or "").strip()
            if sTitle and not title.startswith(sTitle) and (match or "/broadcast/" not in card["url"]):
                title = "%s - %s" % (sTitle, title)
            self._addVideo(cItem, {"title": self._episodeTitle(sTitle, title, sNum, eNum, extra), "url": card["url"], "icon": card["icon"] or cItem.get("icon", ""),
                                   "desc": card["desc"], "season": sNum, "episode": eNum, "station": "alpha"})
        last = 0
        for num in re.findall(r'class="page-numbers"[^>]*href="[^"]*/paged/(\d+)/', data):
            last = max(last, int(num))
        hasNext = 'class="next page-numbers"' in data
        pageTpl = self._base(cItem) + "#page={page}"
        addPagingItems(self, cItem, page, hasNext, max(last, page) if (last or page > 1) else 0, pageTpl)

    def _alphaSearch(self, cItem, pattern):
        for path, label in ALPHA_SECTIONS:
            sts, data = self.getPage(ALPHA + path)
            if not sts:
                continue
            seen = set()
            for title, part in self._alphaGroups(data):
                for card in self._alphaCards(part):
                    if card["url"] in seen or self._isAlphaEpisode(card["url"]) or not self._match(pattern, card["title"]):
                        continue
                    seen.add(card["url"])
                    card["desc"] = " | ".join([x for x in ("ALPHA", label, card["desc"]) if x])
                    self._addAlphaShow(cItem, card)

    def _alphaLinks(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return []
        meta = {"User-Agent": self.HEADER["User-Agent"], "Referer": ALPHA + "/"}
        urlTab = []
        for url in re.findall(r'data-video-url="([^"]+)"', data):
            url = url.replace("&amp;", "&")
            if not self.cm.isValidUrl(url) or url in [u["url"] for u in urlTab]:
                continue
            if ".m3u8" in url:
                for link in getDirectM3U8Playlist(strwithmeta(url, dict(meta, iptv_proto="m3u8")), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999):
                    link["need_resolve"] = 0
                    urlTab.append(link)
            elif "youtube.com/" in url or "youtu.be/" in url:
                urlTab.append({"name": "YouTube", "url": url, "need_resolve": 1})
            else:
                urlTab.append({"name": "MP4", "url": strwithmeta(url, meta), "need_resolve": 0})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return urlTab

    def _alphaInfo(self, cItem):
        sts, data = self.getPage(self._base(cItem))
        if not sts:
            return None
        title, text, icon = self._metaInfo(data)
        info = {"station": "ALPHA"}
        body = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="movie-watch__content">(.*?)</div>\s*</div>')[0])
        if len(body) > len(text):
            text = body
        date = self.cm.ph.getSearchGroups(data, r'"datePublished":"([^"]+)"')[0]
        if date and cItem.get("type") == "video":
            info["released"] = self._date(date)
        genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="card__caption[^"]*">\s*<span>(.*?)</span>')[0])
        if genre and cItem.get("type") != "video":
            info["genre"] = genre
        return title, text, icon, info

    ###################################################
    # search
    ###################################################
    @staticmethod
    def _norm(text):
        # lower case without the Greek accents, for the title search
        text = text.decode("utf-8") if isinstance(text, bytes) else text
        try:
            text = text.lower()
        except Exception:
            return text
        for src, dst in (("ά", "α"), ("έ", "ε"), ("ή", "η"), ("ί", "ι"), ("ϊ", "ι"), ("ΐ", "ι"), ("ό", "ο"), ("ύ", "υ"), ("ϋ", "υ"), ("ΰ", "υ"), ("ώ", "ω"), ("ς", "σ")):
            src = src.decode("utf-8") if isinstance(src, bytes) else src
            dst = dst.decode("utf-8") if isinstance(dst, bytes) else dst
            text = text.replace(src, dst)
        return text

    ###################################################
    # live channels
    ###################################################
    def listLiveGroups(self, cItem):
        for group, channels in LIVE_CHANNELS:
            self.addDir(self._child(cItem, {"category": "live_group", "title": group, "group": group, "desc": ", ".join(c[0] for c in channels)}))

    def listLiveGroup(self, cItem):
        for group, channels in LIVE_CHANNELS:
            if group == cItem.get("group"):
                for name, url in channels:
                    self.addVideo(self._child(cItem, {"category": "live", "title": name, "url": url, "desc": group}))

    def _liveLinks(self, cItem):
        meta = {"iptv_proto": "m3u8", "iptv_livestream": True, "User-Agent": self.HEADER["User-Agent"]}
        url = cItem.get("url", "")
        # ERT / ANT1: fMP4 variants with a separate audio playlist - getDirectM3U8Playlist merges them (ffmpeg)
        urlTab = getDirectM3U8Playlist(strwithmeta(url, dict(meta)), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
        for item in urlTab:
            item["need_resolve"] = 0
            # "[Greek, Modern (1453-)] 1920x1080 7451k" (ANT1 even tags its Greek audio "English") -> "1080p"
            if item.get("height"):
                item["name"] = "%sp" % item["height"]
            else:
                item["name"] = re.sub(r"^\[[^\]]*\]\s*", "", item.get("name", "")) or "HLS live"
        if not urlTab:
            # a media playlist (no variants) or a server that refuses the check: the url as it is
            urlTab = [{"name": "HLS live", "url": strwithmeta(url, meta), "need_resolve": 0}]
        return urlTab

    def _match(self, pattern, title):
        return self._norm(pattern).strip() in self._norm(title)

    def listSearchResult(self, cItem, searchPattern, searchType):
        cItem = dict(cItem)
        cItem.pop("search_item", None)
        for cat, label in SKAI_CATS:
            for show in self._skaiShows(cat):
                if self._match(searchPattern, show["title"]):
                    self._addSkaiShow(cItem, show, " | ".join([x for x in ("SKAI", label, show["desc"]) if x]))
        self._alphaSearch(cItem, searchPattern)
        self._openSearch(cItem, searchPattern)

    ###################################################
    # links / info
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("GreekTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        if cItem.get("category") == "live":
            return self._liveLinks(cItem)
        if url.startswith(SKAI):
            urlTab = self._skaiLinks(cItem)
        elif url.startswith(OPEN):
            urlTab = self._openLinks(cItem)
        elif url.startswith(ALPHA):
            urlTab = self._alphaLinks(cItem)
        else:
            urlTab = []
        if not urlTab:
            return []
        # the sidecar text is the row's desc (date / episode line + text); broadcaster shows: no moviemeta lookup
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), "", {}))

    def getVideoLinks(self, videoUrl):
        printDBG("GreekTV.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    def getArticleContent(self, cItem):
        printDBG("GreekTV.getArticleContent [%s]" % cItem.get("url", ""))
        station = cItem.get("station", "")
        ret = None
        try:
            if station == "skai":
                ret = self._skaiInfo(cItem)
            elif station == "open":
                ret = self._openInfo(cItem)
            elif station == "alpha":
                ret = self._alphaInfo(cItem)
        except Exception:
            printExc()
        if not ret:
            ret = (cItem.get("title", ""), self.cleanHtmlStr(cItem.get("desc", "")), cItem.get("icon", ""), {})
        title, text, icon, info = ret
        if cItem.get("type") == "video" or not title:
            title = cItem.get("title", "") or title
        text = text or self.cleanHtmlStr(cItem.get("desc", "").replace("[/br]", "\n")).replace("\n", "[/br]")
        icon = icon or cItem.get("icon", "")
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("GreekTV.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", "")
        printDBG("GreekTV.handleService: name[%s] category[%s]" % (name, category))
        self.currList = []

        if name is None:
            tab = [{"category": "skai_main", "title": "SKAI", "url": SKAI + "/tv/", "desc": "skai.gr/tv"},
                   {"category": "open_main", "title": "OPEN", "url": OPEN + "/shows", "desc": "tvopen.gr"},
                   {"category": "alpha_main", "title": "ALPHA", "url": ALPHA + "/", "desc": "alphatv.gr"},
                   {"category": "live_groups", "title": _("Live channels"), "desc": "ERT, ANT1, ALPHA, OPEN, SKAI, STAR, MEGA, SIGMA ..."}] + self.searchItems()
            self.listsTab(tab, {"name": "category"})
        elif category == "skai_main":
            self.listSkaiCats(self.currItem)
        elif category == "skai_cat":
            self.listSkaiCat(self.currItem)
        elif category == "skai_show":
            self.listSkaiShow(self.currItem)
        elif category == "skai_season":
            self.listSkaiSeason(self.currItem)
        elif category == "open_main":
            self.listOpenMain(self.currItem)
        elif category == "open_section":
            self.listOpenSection(self.currItem)
        elif category == "open_letters":
            self.listOpenLetters(self.currItem)
        elif category == "open_letter":
            self.listOpenLetter(self.currItem)
        elif category == "open_show":
            self.listOpenShow(self.currItem)
        elif category == "open_cat":
            self.listOpenCat(self.currItem)
        elif category == "open_vids":
            self.listOpenVids(self.currItem)
        elif category == "alpha_main":
            self.listAlphaMain(self.currItem)
        elif category == "alpha_groups":
            self.listAlphaGroups(self.currItem)
        elif category == "alpha_group":
            self.listAlphaGroup(self.currItem)
        elif category == "alpha_show":
            self.listAlphaShow(self.currItem)
        elif category == "alpha_season":
            self.listAlphaSeason(self.currItem)
        elif category == "live_groups":
            self.listLiveGroups(self.currItem)
        elif category == "live_group":
            self.listLiveGroup(self.currItem)
        elif category in ("search", "search_next_page"):
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
        CHostBase.__init__(self, GreekTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("greektv")

    def withArticleContent(self, cItem):
        return cItem.get("station", "") in ("skai", "open", "alpha") and cItem.get("category") in ("video", "skai_show", "skai_season", "open_show", "alpha_show", "alpha_season")
