# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Original File from: 08/04/2026 - Mohamed Elsafty (angel_heart)
# RadioE.ct.ws Host for IPTVPlayer - STABLE GIST VERSION
# Uses separate maps for reliability + improved RSS parsing
# 03.10.2026 - host standard
#   - radioe.ct.ws sits behind a JS cookie challenge and its icons / jingles are gone (404):
#     default icon is the repo's PlayerSelector logo (raw GitHub), radioe.ct.ws images fall back to it,
#     episodes whose audio lives there are left out, dead station-cover host ignored
#   - no colour codes in titles (they become download file names), messages are marker rows
#   - podcast episodes (RSS / JSON / archive.org): watched flag, downloaded flag (audio url),
#     name normalisation ("Programme - Episode"), sidecar, INFO, favourites; the same audio
#     twice in a JSON list is listed once
#   - live stations: favourites only; .m3u8 expanded, .pls/.m3u/.asx playlists resolved in
#     getVideoLinks; an archive.org programme without readable metadata shows a message instead
#     of a "playable" HTML page; moved station streams are swapped via STREAM_FIXES
###################################################
import re

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# GitHub Gist Base URL
GIST_BASE = "https://gist.githubusercontent.com/angelheart150"
# Main JSON endpoints
API_STATIONS_URL = GIST_BASE + "/60a2efd068b384bfb507c431b6246f50/raw/d7310b0f62ca7d2840c5a0b06a7218aed438971d/stations.json"
API_CATEGORIES_URL = GIST_BASE + "/756be2b9006bb51528616e3cec43ee8d/raw/9b0fe4e78fd1fd1c36a41e9da38e67c8e115701a/categories.json"
API_DRAMA_URL = GIST_BASE + "/b293923999e3001598f28972f388a5dd/raw/0fc8c9b8a3839524d28a78633db11de4b7229cdf/drama-programs.json"
API_RADIO_URL = GIST_BASE + "/bbe627291c95ce3773c4e318cd682864/raw/a58dfc969da96ad1beca1d5edd9de2b0df137961/radio-programs.json"
API_BOOKS_URL = GIST_BASE + "/13139a6852591b220bbb14f200f3bca1/raw/59c755cf54fdd2b7a193203f70abd09f00932753/books-programs.json"
# RSS/XML feeds on Gist
RSS_FEEDS_MAP = {
    "https://radioe.ct.ws/app/akt-drama.xml": GIST_BASE + "/06dfe5e3e67f12ac1fc611eccd18e65c/raw/bdb4ceae770a09ba8647e2cd3011aaa47d214428/akt-drama.xml",
    # Add more RSS feeds here as needed
}
# Data source files (JSON) on Gist - INCLUDING individual program files
DATA_SOURCE_MAP = {
    # Main category files
    "drama-programs.json": API_DRAMA_URL,
    "radio-programs.json": API_RADIO_URL,
    "books-programs.json": API_BOOKS_URL,
    # Individual program data files (JSON)
    "akt-drama2.json": GIST_BASE + "/aff01e4529f92dc53a537a434ff803f0/raw/1aa2cec3d4c58125375434b94ea09ffab4be9cdf/akt-drama2.json",
    "radiojingels.json": GIST_BASE + "/bada4d8f29c85eef74966f93c2cf0604/raw/91420caeff7da952149ed0424c82f6b841085d0a/radiojingels.json",
    "ketabarabi.json": GIST_BASE + "/349a8e34fb95049b48d34078253f1c5c/raw/f75a6a8b8c8ed03e9f9c24433b5f9c884535f38b/ketabarabi.json",
    # Add more JSON data files here as needed
}
# hosts whose files are unreachable: radioe.ct.ws answers every request with a JS cookie
# challenge (and the icons / jingles behind it are 404), images.radiovolna.net is gone
DEAD_HOSTS = ("radioe.ct.ws", "images.radiovolna.net")
# station streams of the (commit-pinned) Gist list that moved: old url -> working url (checked 04.10.2026)
STREAM_FIXES = {
    # nrpstream.com answers 403 (CloudFront "Request blocked"); the station's zeno.fm stream plays
    "https://audio.nrpstream.com/listen/nogoumfm/radio.mp3": "https://stream.zeno.fm/qb1zvsykm98uv",
}
PLAYLIST_RE = re.compile(r"\.(pls|m3u|asx)(?:$|\?)", re.I)


def GetConfigList():
    return []


def gettytul():
    return "https://radioe.ct.ws/app/"


class RadioECtWs(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "radioe.ct.ws", "cookie": "radioe.ct.ws.cookie"})
        self.USER_AGENT = self.cm.getDefaultUserAgent('chrome')
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/python3/IPTVPlayer/icons/PlayerSelector/radioe135.png"
        self.DEFAULT_ICON = self.DEFAULT_ICON_URL
        self.API_STATIONS = API_STATIONS_URL
        self.API_CATEGORIES = API_CATEGORIES_URL
        self.HTTP_HEADER = {"User-Agent": self.USER_AGENT, "Accept": "*/*", "Accept-Language": "ar-SA,ar;q=0.9"}
        self.defaultParams = {"header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("radioe")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getJson(self, url):
        """Fetch JSON from Gist or other URL"""
        if not url or self._isDead(url):
            return None
        sts, data = self.getPage(url)
        if not sts or not data or data.strip().startswith(("<!DOCTYPE", "<html", "<script")):
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    @staticmethod
    def _isDead(url):
        return any(("://%s/" % host) in (url or "") for host in DEAD_HOSTS)

    def getFullUrl(self, url, currUrl=None):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        return self.MAIN_URL + url.lstrip("/")

    @staticmethod
    def cleanTitle(title):
        return re.sub(r"\s+", " ", title or "").strip()

    def getSafeIcon(self, iconUrl):
        """Return a loadable icon - images on the dead hosts fall back to the logo"""
        if not iconUrl or self._isDead(self.getFullUrl(iconUrl)):
            return self.DEFAULT_ICON
        return self.getFullUrl(iconUrl)

    @staticmethod
    def getFeedUrl(originalUrl):
        """Map protected RSS URLs to Gist URLs"""
        return RSS_FEEDS_MAP.get(originalUrl, originalUrl)

    @staticmethod
    def _cleanHtml(text, limit=300):
        """Remove HTML tags and clean text"""
        if not text:
            return ""
        text = re.sub(r"<!\[CDATA\[|\]\]>", "", text)
        for tag in ("&lt;br&gt;", "&lt;BR&gt;", "&lt;br /&gt;", "&lt;p&gt;", "&lt;/p&gt;"):
            text = text.replace(tag, " ")
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
        text = re.sub(r"\s+", " ", text).strip()
        if limit and len(text) > limit:
            text = text[:limit] + "..."
        return text

    def _message(self, cItem, msg):
        self.addMarker({"title": msg, "desc": "", "icon": cItem.get("icon", self.DEFAULT_ICON)})

    ###################################################
    # watched flag - podcast episodes and their programme folders, never live stations
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category == "rd_episode" and cItem.get("url"):
                return "ep:%s" % cItem["url"]
            if category in ("episodes_rss", "episodes_json", "episodes_archive"):
                key = cItem.get("prog_id", "") or cItem.get("url", "")
                return ("prog:%s" % key) if key else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("RadioECtWs.listMainMenu")
        tabs = [
            {"category": "radio_list", "title": _("Radio"), "url": self.API_STATIONS, "icon": self.DEFAULT_ICON},
            {"category": "cats_list", "title": _("Programmes"), "url": self.API_CATEGORIES, "icon": self.DEFAULT_ICON},
        ] + self.searchItems()
        self.listsTab(tabs, cItem)

    def _stationParams(self, item):
        title = self._cleanHtml(item.get("title", ""))
        stream = item.get("src", "")
        stream = STREAM_FIXES.get(stream, stream)
        if not title or not stream:
            return None
        country = item.get("country", "") or _("Radio")
        return {"category": "rd_station", "good_for_fav": True, "title": title, "item_id": item.get("id", title), "stream_url": stream, "url": stream,
                "icon": self.getSafeIcon(item.get("cover")), "desc": country}

    def listRadioStations(self, cItem):
        printDBG("RadioECtWs.listRadioStations")
        data = self.getJson(cItem["url"])
        if not data or not isinstance(data, list):
            self._message(cItem, _("Loading failed."))
            return
        for item in data:
            params = self._stationParams(item) if isinstance(item, dict) else None
            if params:
                self.addAudio(params)

    def listCategories(self, cItem):
        printDBG("RadioECtWs.listCategories")
        data = self.getJson(cItem["url"])
        if not data or not isinstance(data, list):
            self._message(cItem, _("Loading failed."))
            return
        for cat in data:
            if not isinstance(cat, dict):
                continue
            cid, title = cat.get("id", ""), self._cleanHtml(cat.get("title", ""))
            source = cat.get("dataSource", "")
            if not cid or not title:
                continue
            url = DATA_SOURCE_MAP.get(source, self.getFullUrl(source) if source else "")
            self.addDir({"category": "progs_list", "title": title, "cat_id": cid, "data_source": source, "url": url, "good_for_fav": True,
                         "icon": self.getSafeIcon(cat.get("image"))})

    def _programParams(self, prog, fallbackDesc=""):
        pid = prog.get("id", "")
        title = self._cleanHtml(prog.get("title", ""))
        if not pid or not title:
            return None
        ptype = prog.get("type", "")
        feed, dfile, archive = prog.get("feedUrl", ""), prog.get("dataFile", ""), prog.get("archiveUrl", "")
        if ptype == "rss" and feed:
            nextCat, actionUrl = "episodes_rss", self.getFeedUrl(feed)
        elif ptype == "json" and dfile:
            nextCat, actionUrl = "episodes_json", DATA_SOURCE_MAP.get(dfile, self.getFullUrl(dfile))
        elif ptype == "archive" and archive:
            nextCat, actionUrl = "episodes_archive", archive
        else:
            return None
        return {"category": nextCat, "good_for_fav": True, "title": title, "prog_title": title, "prog_id": pid, "prog_type": ptype, "feed_url": feed,
                "archive_url": archive, "url": actionUrl, "icon": self.getSafeIcon(prog.get("image")),
                "desc": self._cleanHtml(prog.get("description", ""), 0) or fallbackDesc or _("Audio programme")}

    def listPrograms(self, cItem):
        printDBG("RadioECtWs.listPrograms [%s]" % cItem.get("cat_id"))
        data = self.getJson(cItem.get("url", ""))
        if not data or not isinstance(data, list):
            self._message(cItem, _("Loading failed."))
            return
        for prog in data:
            params = self._programParams(prog) if isinstance(prog, dict) else None
            if params:
                self.addDir(params)

    ###################################################
    # episodes
    ###################################################
    def _addEpisode(self, cItem, title, audioUrl, icon, desc, duration=""):
        if not title or not audioUrl or not audioUrl.startswith("http") or self._isDead(audioUrl):
            return False
        program = cItem.get("prog_title", "") or cItem.get("title", "")
        dispTitle = title
        if IsMediaNamingNormalized() and program and not title.startswith(program):
            dispTitle = "%s - %s" % (program, title)
        params = {"category": "rd_episode", "good_for_fav": True, "title": dispTitle, "ep_title": title, "prog_title": program, "prog_id": cItem.get("prog_id", ""),
                  "url": audioUrl, "icon": icon or cItem.get("icon", self.DEFAULT_ICON), "desc": desc, "duration": duration}
        self.addAudio(params)
        return True

    def listEpisodesJSON(self, cItem):
        printDBG("RadioECtWs.listEpisodesJSON [%s]" % cItem.get("prog_id"))
        data = self.getJson(cItem.get("url", ""))
        if not data or not isinstance(data, list):
            self._message(cItem, _("Loading failed."))
            return
        seen = set()
        count = 0
        for ep in data:
            if not isinstance(ep, dict):
                continue
            audio = self.getFullUrl(ep.get("src") or ep.get("url") or ep.get("audio", ""))
            if not audio or audio in seen:
                continue
            seen.add(audio)
            icon = ep.get("image") or ep.get("cover")
            if self._addEpisode(cItem, self._cleanHtml(ep.get("title", "")), audio, self.getSafeIcon(icon) if icon else "",
                                self._cleanHtml(ep.get("description", ""), 0)):
                count += 1
        if not count:
            self._message(cItem, _("No episodes available yet."))

    def listEpisodesArchive(self, cItem):
        """
        archive.org metadata API: https://archive.org/metadata/IDENTIFIER
        files: https://archive.org/download/IDENTIFIER/FILENAME
        """
        printDBG("RadioECtWs.listEpisodesArchive [%s]" % cItem.get("prog_id"))
        archiveUrl = cItem.get("archive_url", "") or cItem.get("url", "")
        m = re.search(r"archive\.org/(?:details|download)/([^/\?#]+)", archiveUrl, re.I)
        metadata = self.getJson("https://archive.org/metadata/" + m.group(1)) if m else None
        files = metadata.get("files", []) if isinstance(metadata, dict) else []
        if not files:
            self._message(cItem, _("Content not available"))
            return
        identifier = m.group(1)
        validFormats = ["MP3", "MPEG4", "OGG VIDEO", "MATROSKA", "H.264 MPEG4", "WINDOWS MEDIA", "FLASH VIDEO", "512KB MPEG4", "OGG AUDIO", "VBR MP3"]
        mediaExt = [".mp3", ".m4a", ".ogg", ".wav", ".flac", ".aac", ".mp4", ".mkv", ".avi", ".wmv", ".flv", ".mov", ".webm"]
        episodes, seenBases = [], {}
        for f in files:
            if not isinstance(f, dict):
                continue
            fname = f.get("name", "")
            fformat = f.get("format", "").upper()
            fsource = f.get("source", "")
            if fsource == "metadata" or "thumb" in fname.lower() or ".thumbs/" in fname:
                continue
            ext = [e for e in sorted(mediaExt, key=len, reverse=True) if fname.lower().endswith(e)]
            if not ext and fformat not in validFormats:
                continue
            baseName = fname[:-len(ext[0])] if ext else fname
            if fsource == "derivative" and seenBases.get(baseName, {}).get("source") == "original":
                continue
            num = re.search(r"(\d{4})", baseName) or re.search(r"[A-Za-z_\-]+?(\d+)", baseName) or re.match(r"^(\d+)", baseName)
            descParts = []
            if fformat and fformat != "UNKNOWN":
                descParts.append(fformat)
            try:
                descParts.append("%.1f MB" % (float(f.get("size", "0")) / (1024 * 1024)))
            except Exception:
                pass
            episode = {"title": self.cleanTitle(baseName.replace("_", " ").replace("-", " ")) or fname.split("/")[-1],
                       "url": "https://archive.org/download/%s/%s" % (identifier, fname), "format": fformat, "size": f.get("size", "0"),
                       "source": fsource, "base": baseName, "num": int(num.group(1)) if num else None, "desc": " | ".join(descParts)}
            if baseName not in seenBases:
                seenBases[baseName] = episode
                episodes.append(episode)
            elif fsource == "original" and seenBases[baseName].get("source") != "original":
                episodes[episodes.index(seenBases[baseName])] = episode
                seenBases[baseName] = episode

        def sortKey(ep):
            try:
                size = float(ep["size"])
            except Exception:
                size = 999999999
            isMp3 = "MP3" in ep["format"] or ep["url"].lower().endswith(".mp3")
            return (ep["num"] if ep["num"] is not None else 999999, not isMp3, ep["source"] != "original", size)

        episodes.sort(key=sortKey)
        count = 0
        for ep in episodes:
            if self._addEpisode(cItem, ep["title"], ep["url"], "", ep["desc"]):
                count += 1
        if not count:
            self._message(cItem, _("No episodes available yet."))

    def listEpisodesRSS(self, cItem):
        printDBG("RadioECtWs.listEpisodesRSS [%s]" % cItem.get("prog_id"))
        feedUrl = cItem.get("url", "")
        sts, data = self.getPage(feedUrl) if feedUrl and not self._isDead(feedUrl) else (False, "")
        if not sts or not data:
            self._message(cItem, _("Loading failed."))
            return
        if data.strip().startswith(("<!DOCTYPE", "<html", "<script")):
            self._message(cItem, _("Content not available"))
            return
        items = re.findall(r"<item>(.*?)</item>", data, re.S | re.I)
        seen = set()
        count = 0
        for item in items:
            title, audioUrl, duration, summary, imageUrl = self._extractEpisodeSimple(item)
            if not audioUrl or audioUrl in seen:
                continue
            seen.add(audioUrl)
            desc = []
            if duration:
                desc.append("%s %s" % (_("Duration:"), duration))
            if summary:
                desc.append(summary)
            if self._addEpisode(cItem, title, audioUrl, self.getSafeIcon(imageUrl) if imageUrl else "", "\n".join(desc), duration):
                count += 1
        printDBG("Added %d/%d episodes" % (count, len(items)))
        if not count:
            self._message(cItem, _("No episodes available yet."))

    def _extractEpisodeSimple(self, itemXml):
        """(title, audio_url, duration, summary, image_url) of one RSS <item>"""
        title, audioUrl, duration, summary, imageUrl = "", "", "", "", ""
        try:
            item = re.sub(r"<!\[CDATA\[|\]\]>", "", itemXml)
            m = re.search(r"<title>\s*([^<]+?)\s*</title>", item, re.I)
            if m:
                title = self._cleanHtml(m.group(1), 0)
            m = re.search(r"<itunes:duration>([^<]+)</itunes:duration>", item, re.I)
            if m:
                duration = m.group(1).strip()
            m = re.search(r"<itunes:summary>(.*?)</itunes:summary>", item, re.S | re.I) or re.search(r"<description>(.*?)</description>", item, re.S | re.I)
            if m:
                summary = self._cleanHtml(m.group(1))
            m = re.search(r'<itunes:image[^>]+href=["\']([^"\']+)["\']', item, re.I) or re.search(r'<media:thumbnail[^>]+url=["\']([^"\']+)["\']', item, re.I)
            if m:
                imageUrl = m.group(1).strip()
            for pat in (r'<enclosure[^>]+url=["\']([^"\']+\.(?:mp3|m4a|aac|m3u8)[^"\']*)["\']', r'<enclosure[^>]+url=["\']([^"\']+)["\']'):
                m = re.search(pat, item, re.I)
                if m:
                    audioUrl = m.group(1).strip()
                    break
            if not audioUrl:
                m = re.search(r"<description>(.*?)</description>", item, re.S | re.I)
                m = re.search(r'(https?://[^\s<>"\']+\.mp3[^\s<>"\']*)', m.group(1), re.I) if m else None
                if m:
                    audioUrl = m.group(1).strip()
            # the query string only carries tracking data - a stable url for the watched / downloaded flag
            audioUrl = audioUrl.replace("&amp;", "&").split("?")[0]
            if not audioUrl.startswith("http"):
                audioUrl = ""
        except Exception:
            printExc()
        return title, audioUrl, duration, summary, imageUrl

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("RadioECtWs.getLinksForVideo [%s]" % cItem.get("url", ""))
        stream = cItem.get("stream_url", "")
        url = stream if stream.startswith("http") else cItem.get("url", "")
        url = STREAM_FIXES.get(url, url)  # favourites saved with the old stream url
        if not url.startswith("http"):
            return []
        meta = {"User-Agent": self.USER_AGENT}
        if cItem.get("category") != "rd_episode":
            meta["need_buffering"] = True
        if ".m3u8" in url.lower():
            links = [{"name": item.get("name", "HLS"), "url": item["url"], "need_resolve": 0} for item in getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False)]
            if not links:
                links = [{"name": "HLS", "url": strwithmeta(url, meta), "need_resolve": 0}]
        elif PLAYLIST_RE.search(url):
            # station playlist (.pls / .m3u / .asx) - read in getVideoLinks
            links = [{"name": "Stream", "url": strwithmeta(url, meta), "need_resolve": 1}]
        else:
            links = [{"name": "Stream", "url": strwithmeta(url, meta), "need_resolve": 0}]
        if cItem.get("category") == "rd_episode":
            links = applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled()))
        return links

    def getVideoLinks(self, videoUrl):
        printDBG("RadioECtWs.getVideoLinks [%s]" % videoUrl)
        if not PLAYLIST_RE.search(videoUrl or ""):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        sts, data = self.getPage(videoUrl)
        if not sts or not data:
            return []
        urls = re.findall(r"(?im)^\s*File\d+\s*=\s*(https?://\S+)", data)
        urls += re.findall(r'(?i)<ref[^>]+href\s*=\s*["\'](https?://[^"\']+)["\']', data)
        urls += re.findall(r"(?m)^\s*(https?://\S+)\s*$", data)
        links, seen = [], set()
        for url in urls:
            url = url.replace("&amp;", "&")
            if url in seen:
                continue
            seen.add(url)
            links.append({"name": "Stream %d" % (len(links) + 1), "url": strwithmeta(url, {"User-Agent": self.USER_AGENT, "need_buffering": True}), "need_resolve": 0})
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("RadioECtWs.getArticleContent [%s]" % cItem.get("title", ""))
        info = {}
        if cItem.get("duration"):
            info["duration"] = cItem["duration"]
        if cItem.get("prog_title") and cItem.get("category") == "rd_episode":
            info["station"] = cItem["prog_title"]
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("ep_title") or cItem.get("title", ""), "text": cItem.get("desc", "") or cItem.get("title", ""),
                 "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # search
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("RadioECtWs.listSearchResult [%s]" % searchPattern)
        pattern = searchPattern.lower()
        for station in self.getJson(self.API_STATIONS) or []:
            if isinstance(station, dict) and pattern in station.get("title", "").lower():
                params = self._stationParams(station)
                if params:
                    self.addAudio(params)
        for cat in self.getJson(self.API_CATEGORIES) or []:
            gistUrl = DATA_SOURCE_MAP.get(cat.get("dataSource", "")) if isinstance(cat, dict) else None
            if not gistUrl:
                continue
            for prog in self.getJson(gistUrl) or []:
                if isinstance(prog, dict) and pattern in prog.get("title", "").lower():
                    params = self._programParams(prog, cat.get("title", ""))
                    if params:
                        self.addDir(params)

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("RadioECtWs.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "radio_list":
            self.listRadioStations(self.currItem)
        elif category == "cats_list":
            self.listCategories(self.currItem)
        elif category == "progs_list":
            self.listPrograms(self.currItem)
        elif category == "episodes_rss":
            self.listEpisodesRSS(self.currItem)
        elif category == "episodes_json":
            self.listEpisodesJSON(self.currItem)
        elif category == "episodes_archive":
            self.listEpisodesArchive(self.currItem)
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
        CHostBase.__init__(self, RadioECtWs(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("radioe")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("rd_episode", "episodes_rss", "episodes_json", "episodes_archive")
