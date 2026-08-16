# -*- coding: utf-8 -*-
# Original File from: 08/04/2026 - Mohamed Elsafty (angel_heart)
# RadioE.ct.ws Host for IPTVPlayer - STABLE GIST VERSION
# Uses separate maps for reliability + improved RSS parsing
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, E2ColoR, byteify

###################################################
import json
import re

try:
    import xml.etree.ElementTree as ET
except Exception:
    ET = None
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

# Constants
C = E2ColoR("cyan")
L = E2ColoR("lime")
O = E2ColoR("orange")
R = E2ColoR("red")
W = E2ColoR("white")
Y = E2ColoR("yellow")


def GetConfigList():
    return []


def gettytul():
    return "https://radioe.ct.ws/app/"


class RadioECtWs(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "radioe.ct.ws", "cookie": "radioe.ct.ws.cookie"})
        self.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON = self.MAIN_URL + "icons/icon500.png"
        self.API_STATIONS = API_STATIONS_URL
        self.API_CATEGORIES = API_CATEGORIES_URL
        self.HTTP_HEADER = {
            "User-Agent": self.USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "ar-SA,ar;q=0.9",
            "Referer": self.MAIN_URL,
        }
        self.defaultParams = {"header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE, "return_data": True}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if not addParams:
            addParams = dict(self.defaultParams)
        try:
            return self.cm.getPage(baseUrl, addParams, post_data)
        except Exception:
            printExc()
            return False, None

    def getJson(self, url):
        """Fetch JSON from Gist or other URL"""
        try:
            sts, data = self.getPage(url)
            if not sts or not data:
                return None
            if data.strip().startswith(("<!DOCTYPE", "<html", "<script")):
                return None
            return byteify(json.loads(data))
        except Exception:
            printExc()
            return None

    def getFullUrl(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        return self.MAIN_URL + url.lstrip("/")

    def cleanTitle(self, title):
        if not title:
            return ""
        return re.sub(r"\s+", " ", title).strip()

    def getSafeIcon(self, icon_url):
        """Return safe icon - skip protected domain images"""
        if not icon_url or "radioe.ct.ws/app/icons" in icon_url:
            return self.DEFAULT_ICON
        return self.getFullUrl(icon_url)

    def getFeedUrl(self, original_url):
        """Map protected RSS URLs to Gist URLs"""
        return RSS_FEEDS_MAP.get(original_url, original_url)

    def _cleanHtml(self, text):
        """Remove HTML tags and clean text"""
        if not text:
            return ""
        text = re.sub(r"<!\[CDATA\[|\]\]>", "", text)
        text = text.replace("&lt;br&gt;", " ").replace("&lt;BR&gt;", " ")
        text = text.replace("&lt;br /&gt;", " ").replace("&lt;p&gt;", " ").replace("&lt;/p&gt;", " ")
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:300] + ("..." if len(text) > 300 else "")

    # ================== Main Menu ==================
    def listMainMenu(self, cItem):
        printDBG("RadioECtWs.listMainMenu")
        search_items = self.searchItems()
        for item in search_items:
            if not item.get("icon"):
                item["icon"] = self.DEFAULT_ICON
        tabs = [
            {"category": "radio_list", "title": "الراديو", "url": self.API_STATIONS, "icon": self.DEFAULT_ICON},
            {"category": "cats_list", "title": "البرامج", "url": self.API_CATEGORIES, "icon": self.DEFAULT_ICON},
        ] + search_items
        self.listsTab(tabs, cItem)

    # ================== Radio Stations ==================
    def listRadioStations(self, cItem):
        printDBG("RadioECtWs.listRadioStations")
        data = self.getJson(cItem["url"])
        if not data or not isinstance(data, list):
            self.addVideo({"title": "تعذر تحميل الإذاعات", "desc": "تحقق من الإنترنت", "icon": self.DEFAULT_ICON})
            return
        for item in data:
            try:
                title = self._cleanHtml(item.get("title", ""))
                if not title:
                    continue
                stream = item.get("src", "")
                icon = self.getSafeIcon(item.get("cover"))
                country = item.get("country", "")
                country = country if country else "محطة إذاعية"
                params = {"good_for_fav": True, "title": title, "item_id": item.get("id", title), "stream_url": stream, "url": stream or "", "icon": icon, "desc": Y + country + W}
                self.addAudio(params)
            except Exception:
                printExc()
                continue

    # ================== Program Categories ==================
    def listCategories(self, cItem):
        printDBG("RadioECtWs.listCategories")
        data = self.getJson(cItem["url"])
        if not data or not isinstance(data, list):
            self.addVideo({"title": "تعذر تحميل الفئات", "desc": "حاول لاحقاً", "good_for_fav": True, "icon": self.DEFAULT_ICON})
            return
        for cat in data:
            try:
                cid, title = cat.get("id", ""), cat.get("title", "")
                source = cat.get("dataSource", "")
                if not cid or not title:
                    continue
                # Use DATA_SOURCE_MAP for category JSON files
                gist_url = DATA_SOURCE_MAP.get(source, self.MAIN_URL + source if source else "")
                params = {"category": "progs_list", "title": title, "cat_id": cid, "data_source": source, "url": gist_url, "good_for_fav": True, "icon": self.getSafeIcon(cat.get("image"))}
                self.addDir(params)
            except Exception:
                printExc()
                continue

    # ================== Programs List ==================
    def listPrograms(self, cItem):
        printDBG("RadioECtWs.listPrograms [%s]" % cItem.get("cat_id"))
        url = cItem.get("url", "")
        if not url:
            return
        data = self.getJson(url)
        if not data or not isinstance(data, list):
            self.addVideo({"title": "تعذر تحميل البرامج", "desc": "الفئة فارغة", "icon": cItem.get("icon", self.DEFAULT_ICON)})
            return
        for prog in data:
            try:
                pid = prog.get("id", "")
                title = self._cleanHtml(prog.get("title", ""))
                if not pid or not title:
                    continue
                ptype = prog.get("type", "")
                feed = prog.get("feedUrl", "")
                dfile = prog.get("dataFile", "")
                archive = prog.get("archiveUrl", "")
                if ptype == "rss" and feed:
                    next_cat, action_url = "episodes_rss", self.getFeedUrl(feed)
                elif ptype == "json" and dfile:
                    # Use DATA_SOURCE_MAP for individual JSON data files
                    next_cat, action_url = "episodes_json", DATA_SOURCE_MAP.get(dfile, self.MAIN_URL + dfile)
                elif ptype == "archive" and archive:
                    next_cat, action_url = "episodes_archive", archive
                else:
                    continue
                params = {"category": next_cat, "good_for_fav": True, "title": Y + title + W, "prog_id": pid, "prog_type": ptype, "feed_url": feed, "archive_url": archive, "url": action_url, "icon": self.getSafeIcon(prog.get("image")), "desc": prog.get("description", "برنامج صوتي")}
                self.addDir(params)
            except Exception:
                printExc()
                continue

    def _showEmpty(self, cItem, msg):
        self.addVideo({"title": "ℹ️ %s" % msg, "desc": "جرب برنامجاً آخر", "icon": cItem.get("icon", self.DEFAULT_ICON)})

    # ================== Episodes from JSON ==================
    def listEpisodesJSON(self, cItem):
        printDBG("RadioECtWs.listEpisodesJSON [%s]" % cItem.get("prog_id"))
        url = cItem.get("url", "")
        if not url:
            return
        data = self.getJson(url)
        if not data or not isinstance(data, list):
            self._showEmpty(cItem, "تعذر التحميل")
            return
        printDBG("JSON episodes: %d items" % len(data))
        for ep in data:
            try:
                title = self._cleanHtml(ep.get("title", ""))
                if not title:
                    continue
                audio = ep.get("src") or ep.get("url") or ep.get("audio", "")
                icon = ep.get("image") or ep.get("cover") or cItem.get("icon")
                params = {"good_for_fav": True, "title": L + title + W, "url": self.getFullUrl(audio) if audio else "", "icon": self.getSafeIcon(icon), "desc": ep.get("description", "حلقة صوتية")}
                self.addAudio(params)
            except Exception:
                printExc()
                continue
        if not self.currList:
            self._showEmpty(cItem, "لا توجد حلقات")

    # # ================== Episodes from Archive.org ==================
    def listEpisodesArchive(self, cItem):
        """
        List episodes from archive.org using the official Metadata API
        API: https://archive.org/metadata/IDENTIFIER
        Download: https://archive.org/download/IDENTIFIER/FILENAME
        """
        printDBG("RadioECtWs.listEpisodesArchive [%s]" % cItem.get("prog_id"))
        archive_url = cItem.get("archive_url", "")
        if not archive_url:
            return
        try:
            # Extract identifier from archive.org URL
            # Format: https://archive.org/details/IDENTIFIER
            identifier_match = re.search(r"archive\.org/(?:details|download)/([^/\?#]+)", archive_url, re.I)
            if not identifier_match:
                # Fallback: add as single item for external resolver
                self._addArchiveItem(cItem, archive_url)
                return
            identifier = identifier_match.group(1)
            metadata_url = "https://archive.org/metadata/" + identifier
            printDBG("Fetching archive metadata: %s" % metadata_url)
            # Fetch metadata JSON
            sts, data = self.cm.getPage(metadata_url, {"header": self.HTTP_HEADER, "return_data": True})
            if not sts or not data:
                printDBG("Failed to fetch metadata, adding fallback")
                self._addArchiveItem(cItem, archive_url)
                return
            metadata = byteify(json.loads(data))
            files = metadata.get("files", [])
            if not files:
                printDBG("No files in metadata")
                self._addArchiveItem(cItem, archive_url)
                return
            # Valid media formats for archive.org
            valid_formats = ["MP3", "MPEG4", "Ogg Video", "Matroska", "h.264 MPEG4", "Windows Media", "Flash Video", "512Kb MPEG4", "Ogg Audio", "VBR MP3"]
            audio_ext = [".mp3", ".m4a", ".ogg", ".wav", ".flac", ".aac"]
            video_ext = [".mp4", ".mkv", ".avi", ".wmv", ".flv", ".mov", ".webm"]
            episodes = []
            seen_bases = {}
            for f in files:
                fname = f.get("name", "")
                fformat = f.get("format", "").upper()
                fsize = f.get("size", "0")
                fsource = f.get("source", "")
                if fname.endswith((".txt", ".xml", ".json", ".torrent", ".zip", ".pdf", ".afpk", ".png", ".jpg", ".gif", ".jpeg")):
                    continue
                if fsource == "metadata" or "thumb" in fname.lower() or ".thumbs/" in fname:
                    continue
                is_media = any(fname.lower().endswith(ext) for ext in audio_ext + video_ext) or fformat in valid_formats
                if not is_media:
                    continue
                base_name = fname
                for ext in sorted(audio_ext + video_ext, key=len, reverse=True):
                    if base_name.lower().endswith(ext):
                        base_name = base_name[: -len(ext)]
                        break
                if fsource == "derivative":
                    if base_name in seen_bases and seen_bases[base_name].get("source") == "original":
                        continue
                download_url = "https://archive.org/download/%s/%s" % (identifier, fname)
                episode_num = None
                num_match = re.search(r"(\d{4})", base_name)
                if num_match:
                    episode_num = int(num_match.group(1))
                else:
                    num_match = re.search(r"[A-Za-z_\-]+?(\d+)", base_name)
                    if num_match:
                        episode_num = int(num_match.group(1))
                    else:
                        num_match = re.match(r"^(\d+)", base_name)
                        if num_match:
                            episode_num = int(num_match.group(1))
                title = base_name
                title = self.cleanTitle(title.replace("_", " ").replace("-", " ").strip())
                if not title:
                    title = fname.split("/")[-1]
                desc_parts = []
                if fformat and fformat != "UNKNOWN":
                    desc_parts.append(fformat)
                if fsize and fsize != "0":
                    try:
                        size_mb = float(fsize) / (1024 * 1024)
                        desc_parts.append("%.1f MB" % size_mb)
                    except:
                        pass
                desc = " | ".join(desc_parts) if desc_parts else "ملف أرشيفي"
                episode_data = {"title": title, "url": download_url, "icon": cItem.get("icon"), "desc": Y + desc + W, "format": fformat, "size": fsize, "source": fsource, "base_name": base_name, "episode_num": episode_num}
                if base_name not in seen_bases:
                    seen_bases[base_name] = episode_data
                    episodes.append(episode_data)
                elif fsource == "original" and seen_bases[base_name].get("source") != "original":
                    for i, ep in enumerate(episodes):
                        if ep["base_name"] == base_name:
                            episodes[i] = episode_data
                            seen_bases[base_name] = episode_data
                            break

            def sort_key(ep):
                ep_num = ep.get("episode_num")
                if ep_num is None:
                    ep_num = 999999
                is_mp3 = "MP3" in ep["format"] or ep["url"].lower().endswith(".mp3")
                is_original = ep.get("source") == "original"
                try:
                    size = float(ep["size"])
                except:
                    size = 999999999
                return (ep_num, not is_mp3, not is_original, size)

            episodes.sort(key=sort_key)
            count = 0
            for ep in episodes:
                params = {"good_for_fav": True, "title": ep["title"], "url": ep["url"], "icon": ep["icon"], "desc": ep["desc"]}
                self.addAudio(params)
                count += 1
            printDBG("Added %d unique files from %d total (after deduplication)" % (count, len(files)))
            if count == 0:
                self._addArchiveItem(cItem, archive_url)
        except Exception as e:
            printExc()
            printDBG("Archive error: %s" % str(e))
            self._addArchiveItem(cItem, archive_url)

    def _addArchiveItem(self, cItem, url):
        """Fallback: add archive URL as single item with resolve flag"""
        params = {"good_for_fav": True, "title": cItem.get("title", "") + " - أرشيف", "url": url, "icon": cItem.get("icon"), "desc": "رابط الأرشيف - اضغط للتشغيل", "need_resolve": 1}
        self.addAudio(params)

    # ================== Episodes from RSS ==================
    def listEpisodesRSS(self, cItem):
        printDBG("RadioECtWs.listEpisodesRSS [%s]" % cItem.get("prog_id"))
        feed_url = cItem.get("url", "")
        if not feed_url:
            return
        try:
            sts, data = self.cm.getPage(feed_url, {"header": self.HTTP_HEADER, "return_data": True})
            if not sts or not data:
                self._showEmpty(cItem, "تعذر تحميل البودكاست")
                return
            if data.strip().startswith(("<!DOCTYPE", "<html", "<script")):
                self._showEmpty(cItem, "الرابط محمي أو غير متاح")
                return
            # Remove namespaces
            data_clean = re.sub(r'\s*xmlns(:[^=]+)?=["\'][^"\']*["\']', "", data)
            items = re.findall(r"<item>(.*?)</item>", data_clean, re.S | re.I)
            printDBG("Found %d items in RSS" % len(items))
            if not items:
                self._showEmpty(cItem, "لا توجد حلقات")
                return
            count = 0
            for idx, item in enumerate(items):
                try:
                    # ✅ Now returns 5 values including image_url
                    ep_title, audio_url, duration, summary, image_url = self._extractEpisodeSimple(item)
                    duration = duration or ""
                    summary = summary or ""
                    # ✅ Use episode image if available, else fallback to parent icon
                    icon = self.getSafeIcon(image_url) if image_url else cItem.get("icon")
                    if idx < 3:
                        printDBG("✓ Extracted: title='%s' | img='%s'" % (ep_title[:40] if ep_title else "EMPTY", image_url[:60] if image_url else "USING_PARENT_ICON"))
                    if ep_title and audio_url and audio_url.startswith("http"):
                        # Build enhanced description with colors
                        desc_parts = []
                        if duration:
                            desc_parts.append(Y + _("Duration:") + " " + W + duration)
                        if summary:
                            desc_parts.append(Y + _("Summary:") + " " + W + summary)
                        desc = "\n".join(desc_parts) if desc_parts else W + "حلقة صوتية"
                        params = {"good_for_fav": True, "title": L + ep_title + W, "url": audio_url, "icon": icon, "desc": desc}
                        self.addAudio(params)
                        count += 1
                    elif idx < 3:
                        printDBG("✗ Skipped: no valid audio_url for '%s'" % ep_title)
                except Exception as e:
                    printDBG("Item error: %s" % str(e))
                    continue
            printDBG("Added %d/%d episodes" % (count, len(items)))
            if count == 0:
                self._showEmpty(cItem, "لا توجد حلقات")
        except Exception as e:
            printExc()
            self._showEmpty(cItem, "حدث خطأ: %s" % str(e))

    def _extractEpisodeSimple(self, item_xml_string):
        """
        Extract title, audio URL, duration, summary, and image
        Returns: (title, audio_url, duration, summary, image_url)
        """
        ep_title, audio_url, duration, summary, image_url = "", "", "", "", ""
        try:
            # Clean CDATA
            item_clean = re.sub(r"<!\[CDATA\[", "", item_xml_string)
            item_clean = re.sub(r"\]\]>", "", item_clean)
            # === Title ===
            tm = re.search(r"<title>\s*([^<]+?)\s*</title>", item_clean, re.I)
            if tm:
                ep_title = self.cleanTitle(tm.group(1))
            # === Duration ===
            dm = re.search(r"<itunes:duration>([^<]+)</itunes:duration>", item_clean, re.I)
            if dm:
                duration = dm.group(1).strip()
            # === Summary ===
            sm = re.search(r"<itunes:summary>(.*?)</itunes:summary>", item_clean, re.S | re.I)
            if sm:
                summary = self._cleanHtml(sm.group(1))
            else:
                desc_m = re.search(r"<description>(.*?)</description>", item_clean, re.S | re.I)
                if desc_m:
                    summary = self._cleanHtml(desc_m.group(1))
            # === Image URL - Try itunes:image first, then media:thumbnail ===
            # Pattern 1: <itunes:image href="URL"/>
            img_match = re.search(r'<itunes:image[^>]+href=["\']([^"\']+)["\']', item_clean, re.I)
            if img_match:
                image_url = img_match.group(1).strip()
            else:
                # Pattern 2: <media:thumbnail url="URL"/>
                thumb_match = re.search(r'<media:thumbnail[^>]+url=["\']([^"\']+)["\']', item_clean, re.I)
                if thumb_match:
                    image_url = thumb_match.group(1).strip()
            # === Audio URL ===
            enc_patterns = [
                r'<enclosure[^>]+url=["\']([^"\']+\.mp3[^"\']*)["\']',
                r'<enclosure[^>]+url=["\']([^"\']+\.m3u8[^"\']*)["\']',
                r'<enclosure[^>]+url=["\']([^"\']+\.aac[^"\']*)["\']',
                r'<enclosure[^>]+type=["\'][^"\']+["\'][^>]+url=["\']([^"\']+\.mp3[^"\']*)["\']',
            ]
            for pat in enc_patterns:
                em = re.search(pat, item_clean, re.I)
                if em:
                    audio_url = em.group(1).strip()
                    break
            # Fallback: search in description
            if not audio_url:
                desc_m = re.search(r"<description>(.*?)</description>", item_clean, re.S | re.I)
                if desc_m:
                    url_m = re.search(r'(https?://[^\s<>"\']+\.mp3[^\s<>"\']*)', desc_m.group(1), re.I)
                    if url_m:
                        audio_url = url_m.group(1).strip()
            # Clean URL
            if audio_url:
                audio_url = audio_url.replace("&amp;", "&").split("?")[0]
                if not audio_url.startswith("http"):
                    audio_url = ""
        except Exception as e:
            printDBG("Extract error: %s" % str(e))
        return ep_title, audio_url, duration, summary, image_url

    # ================== Get Links ==================
    def getLinksForVideo(self, cItem):
        printDBG("RadioECtWs.getLinksForVideo [%s]" % cItem)
        linksTab = []
        url = cItem.get("url", "")
        stream = cItem.get("stream_url", "")
        final_url = stream if stream and stream.startswith("http") else url
        if not final_url or not final_url.startswith("http"):
            return linksTab
        need_resolve = 1 if any(e in final_url.lower() for e in [".m3u8", ".pls", ".asx", ".m3u"]) else 0
        linksTab.append({"name": "تشغيل", "url": final_url, "need_resolve": need_resolve, "meta": {"need_buffering": True}})
        return linksTab

    # ================== Search ==================
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("RadioECtWs.listSearchResult [%s]" % searchPattern)
        pattern = searchPattern.lower()
        stations = self.getJson(self.API_STATIONS)
        if stations:
            for s in stations:
                title = s.get("title", "")
                if title and pattern in title.lower():
                    params = {"good_for_fav": True, "title": self._cleanHtml(title) + " ", "item_id": s.get("id", ""), "stream_url": s.get("src", ""), "url": s.get("src", ""), "icon": self.getSafeIcon(s.get("cover")), "desc": s.get("country", "")}
                    self.addAudio(params)
        cats = self.getJson(self.API_CATEGORIES)
        if cats:
            for cat in cats:
                source = cat.get("dataSource", "")
                if not source:
                    continue
                gist_url = DATA_SOURCE_MAP.get(source)
                if not gist_url:
                    continue
                progs = self.getJson(gist_url)
                if progs:
                    for p in progs:
                        ptitle = p.get("title", "")
                        if ptitle and pattern in ptitle.lower():
                            ptype = p.get("type", "")
                            if ptype == "rss":
                                next_cat, action_url = "episodes_rss", self.getFeedUrl(p.get("feedUrl", ""))
                            elif ptype == "json":
                                next_cat, action_url = "episodes_json", DATA_SOURCE_MAP.get(p.get("dataFile", ""), "")
                            elif ptype == "archive":
                                next_cat, action_url = "episodes_archive", p.get("archiveUrl", "")
                            else:
                                continue
                            params = {"category": next_cat, "good_for_fav": True, "title": self._cleanHtml(ptitle) + " ", "prog_id": p.get("id", ""), "feed_url": p.get("feedUrl", ""), "archive_url": p.get("archiveUrl", ""), "url": action_url, "icon": self.getSafeIcon(p.get("image")), "desc": p.get("description", cat.get("title", ""))}
                            self.addDir(params)

    # ================== Main Handler ==================
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("RadioECtWs.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: name[%s], category[%s]" % (name, category))
        self.currList = []
        # MAIN MENU
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
        # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        # HISTORY SEARCH
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, RadioECtWs(), True, [])
