# -*- coding: utf-8 -*-
LAST_MODIFIED = "04.11.2026"
# NPR Music (npr.org/music): Tiny Desk concerts and other music videos, music podcasts, shows and live music streams.
# Lists: public NPR RSS feeds + the video playlist of npr.org/music. Video: every story page embeds a JW Player
# (cdn.jwplayer.com manifest) which is played as mp4 (JW media API) or HLS; podcasts play from the RSS enclosure.
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

import re
try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin
from email.utils import parsedate
from xml.etree import ElementTree as ET


def GetConfigList():
    return []


def gettytul():
    return "https://www.npr.org/music"


PODCAST_FEED = "https://feeds.npr.org/%s/podcast.xml"
STORY_FEED = "https://feeds.npr.org/%s/rss.xml"
MUSIC_PAGE = "https://www.npr.org/music"
ARCHIVE_URL = "https://www.npr.org/series/tiny-desk-concerts/archive"
JW_MEDIA = "https://cdn.jwplayer.com/v2/media/%s"

# feed ids from the links of npr.org/music; only series/shows that are still published: the Tiny Desk feeds (1110,
# podcast 510306) make "Tiny Desk Concerts", Live Sessions (2022), Piano Jazz (2018), From the Top (2021),
# Thistle & Shamrock (2024) and Fresh Air Interviews (2019) ended
STORY_LISTS = [("Field Recordings", "144918893"), ("Music stories", "1039")]
PODCASTS = [("NPR Music / All Songs Considered", "510019"), ("Alt.Latino", "510305"),
            ("World Cafe", "510008"), ("It's Been a Minute", "510317"), ("Wild Card with Rachel Martin", "510379")]
SHOWS = [("Jazz Night in America", "347139849")]

# live music streams: well-known public radio streams (the npr.org 'Listen Live' block is loaded by JavaScript)
LIVE = [("KEXP 90.3 Seattle", "https://kexp.streamguys1.com/kexp160.aac"),
        ("KCRW Eclectic24", "https://streams.kcrw.com/e24_mp3"),
        ("The Current (MPR)", "https://current.stream.publicradio.org/current.aac")]

YT_RX = (re.compile(r"youtube(?:-nocookie)?\.com/embed/([\w-]{11})"),
         re.compile(r"youtube\.com/watch\?v=([\w-]{11})"),
         re.compile(r"youtu\.be/([\w-]{11})"))
FILE_RX = re.compile(r"""https?://[^"'\s<>\\]+?\.(?:mp4|m3u8|mp3|m4a)(?:\?[^"'\s<>\\]*)?""", re.I)
JW_RX = re.compile(r"cdn\.jwplayer\.com/(?:manifests|v2/media|videos)/([A-Za-z0-9]{8})")


def _local(tag):
    return tag.split("}")[-1]


def _txt(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def _slug(url):
    return (url or "").split("?")[0].rstrip("/").split("/")[-1].lower()


def _tsFromUrl(url):
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url or "")
    return ("%s%s%s000000" % m.groups(), "%s-%s-%s" % m.groups()) if m else ("", "")


def _duration(value):
    """itunes:duration in seconds ("1589") -> "26:29" / "1:02:05"; "hh:mm:ss" stays as it is"""
    value = (value or "").strip()
    if not value.isdigit():
        return value
    minutes, seconds = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)
    return "%d:%02d:%02d" % (hours, minutes, seconds) if hours else "%d:%02d" % (minutes, seconds)


def parseFeed(text):
    """Generic RSS/podcast parser -> (channel image, [items])."""
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text or "").strip()
    items, chanIcon = [], ""
    if not text:
        return chanIcon, items
    try:
        root = ET.fromstring(text)
    except Exception:
        printExc()
        return chanIcon, items
    chan = root.find("channel")
    if chan is not None:
        for el in chan:
            if _local(el.tag) == "image":
                chanIcon = el.get("href") or (el.findtext("url") or "") or chanIcon
    for item in root.iter("item"):
        d = {"title": "", "url": "", "desc": "", "date": "", "ts": "", "icon": "", "audio": "", "duration": "", "video": False}
        for el in item:
            ln = _local(el.tag)
            if ln == "title":
                d["title"] = (el.text or "").strip()
            elif ln == "link":
                d["url"] = (el.text or "").strip()
            elif ln in ("description", "summary", "subtitle") and not d["desc"]:
                d["desc"] = (el.text or "").strip()
            elif ln == "pubDate":
                pd = parsedate(el.text or "")
                if pd:
                    d["date"] = "%04d-%02d-%02d" % (pd[0], pd[1], pd[2])
                    d["ts"] = "%04d%02d%02d%02d%02d%02d" % tuple(pd[:6])
            elif ln == "enclosure":
                url, typ = el.get("url") or "", (el.get("type") or "").lower()
                if url and ("audio" in typ or "video" in typ or re.search(r"\.(mp3|m4a|mp4)(\?|$)", url, re.I)):
                    d["audio"] = url
                    d["video"] = "video" in typ or bool(re.search(r"\.(mp4|m4v|mov)(\?|$)", url, re.I))
            elif ln == "image" and el.get("href"):
                d["icon"] = el.get("href")
            elif ln in ("thumbnail", "content") and el.get("url") and not d["icon"] and \
                    ("image" in (el.get("type") or el.get("medium") or "image") or ln == "thumbnail"):
                d["icon"] = el.get("url")
            elif ln == "duration":
                d["duration"] = _duration(el.text)
        d["icon"] = d["icon"] or chanIcon
        if d["title"]:
            items.append(d)
    return chanIcon, items


def findMedia(html):
    """Media of a story page: [('jw', mediaId), ('youtube', url), ('file', url), ...]."""
    html = (html or "").replace("\\/", "/").replace("\\u0026", "&").replace("&amp;", "&")
    media = []
    for m in JW_RX.finditer(html):
        if ("jw", m.group(1)) not in media:
            media.append(("jw", m.group(1)))
    for rx in YT_RX:
        for m in rx.finditer(html):
            item = ("youtube", "https://www.youtube.com/watch?v=%s" % m.group(1))
            if item not in media:
                media.append(item)
    if not media:
        for m in FILE_RX.finditer(html):
            item = ("file", m.group(0))
            if item not in media and "sponsor" not in m.group(0).lower():
                media.append(item)
    return media


def parseMusicPage(html):
    """Video playlist of npr.org/music ('More Videos'): [(title, url, icon)]; entries use data-mediaid, not href."""
    out, seen = [], set()
    for m in re.finditer(r"""<li class="playlist-item"[^>]*>\s*<a[^>]*data-mediaid=["']([^"']+)["'][^>]*>(.*?)</a>""", html or "", re.S | re.I):
        path, inner = m.groups()
        url = path if path.startswith("http") else "https://www.npr.org" + path
        # entities stay: the row title goes through cleanHtmlStr()
        p = re.search(r"<p>(.*?)</p>", inner, re.S)
        title = _txt(p.group(1)) if p else ""
        img = re.search(r"""<img[^>]+src=["']([^"']+)["']""", inner)
        if url not in seen and title:
            seen.add(url)
            out.append((title, url, (img.group(1).replace("&amp;", "&") if img else "")))
    return out


def parseArchive(html):
    """Concerts of the Tiny Desk archive page: [(title, url, icon, desc)]."""
    out, seen = [], set()
    blocks = re.findall(r"<article\b.*?</article>", html or "", re.S | re.I) or [html or ""]
    for blk in blocks:
        for m in re.finditer(r"""<a\b[^>]*href=["']((?:https://www\.npr\.org)?/\d{4}/\d{2}/\d{2}/[^"'#?]+)[^"']*["'][^>]*>(.*?)</a>""", blk, re.S | re.I):
            href, inner = m.groups()
            url = href if href.startswith("http") else "https://www.npr.org" + href
            if url in seen:
                continue
            t = re.search(r"""class=["'][^"']*title[^"']*["'][^>]*>(.*?)</""", blk, re.S | re.I)
            title = (_txt(t.group(1)) if t else "") or _txt(inner) or _slug(url).replace("-", " ").capitalize()
            d = re.search(r"""class=["'][^"']*teaser[^"']*["'][^>]*>(.*?)</""", blk, re.S | re.I)
            img = re.search(r"""<img[^>]+(?:data-original|data-src|src)=["']([^"']+)["']""", blk)
            seen.add(url)
            out.append((title, url, img.group(1) if img else "", _txt(d.group(1)) if d else ""))
            break
    return out


class NPRMusic(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "f_feed", "icon", "desc", "date", "duration", "live", "direct",
                  "audio", "fallback")
    PAGE_SIZE = 50

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "nprmusic", "cookie": "nprmusic.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept": "*/*", "Referer": "https://www.npr.org/"})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/nprmusic135.png")
        self.feedCache = {}
        self.watchedHelper = IPTVWatchedHelper("nprmusic")
        self.wfInitFolderCache()

    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and not cItem.get("live") and cItem.get("type", "") in ("video", "audio"):
                url = cItem.get("url") or cItem.get("audio", "")
                return "item:%s" % url if url else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _text(self, url, accept=None):
        params = dict(self.defaultParams)
        if accept:
            params["header"] = dict(self.HEADER, Accept=accept)
        sts, data = self.cm.getPage(url, params)
        if not sts or not data:
            return ""
        if not isinstance(data, str):
            try:
                data = data.decode("utf-8")
            except Exception:
                data = data.decode("latin-1")
        return data

    # the lists are kept for the host session (paging, search); a failed request is not kept, Refresh (YELLOW) drops them
    def _feed(self, url):
        if url not in self.feedCache:
            data = self._text(url, "application/rss+xml, application/xml, text/xml, */*")
            items = parseFeed(data)[1]
            printDBG("NPRMusic._feed [%s] len[%s] items[%s]" % (url, len(data), len(items)))
            if not items:
                return items
            self.feedCache[url] = items
        return self.feedCache[url]

    def _musicPageItems(self):
        if "music_page" not in self.feedCache:
            html = self._text(MUSIC_PAGE, "text/html,application/xhtml+xml,*/*;q=0.8")
            entries = parseMusicPage(html)
            printDBG("NPRMusic._musicPageItems len[%s] entries[%s]" % (len(html), len(entries)))
            items = []
            for title, url, icon in entries:
                ts, date = _tsFromUrl(url)
                items.append({"title": title, "url": url, "desc": "", "date": date, "ts": ts, "icon": icon,
                              "audio": "", "duration": "", "video": True})
            if not items:
                return items
            self.feedCache["music_page"] = items
        return self.feedCache["music_page"]

    def _allConcerts(self):
        """Every Tiny Desk concert we can reach, newest first: site playlist + series feed + audio podcast (300 episodes)."""
        if "all_concerts" in self.feedCache:
            return self.feedCache["all_concerts"]
        seen, items = set(), []
        sources = [self._musicPageItems(), self._feed(STORY_FEED % "1110"), self._feed(PODCAST_FEED % "510306")]
        complete = all(sources)
        for src in sources:
            for it in src:
                key = _slug(it["url"]) or it["title"].lower()
                if key in seen:
                    continue
                seen.add(key)
                d = dict(it)
                d["page_first"] = True               # play the video from the story page; keep the podcast audio as fallback
                d["fallback"], d["audio"] = d.get("audio", ""), ""
                if not d["ts"]:
                    d["ts"], d["date"] = _tsFromUrl(d["url"])
                items.append(d)
        items.sort(key=lambda x: x.get("ts", ""), reverse=True)
        if complete:
            self.feedCache["all_concerts"] = items
        return items

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        menu = [{"category": "nm_all", "title": "Tiny Desk Concerts"},
                {"category": "nm_archive", "title": "Tiny Desk - " + _("Archive"), "url": ARCHIVE_URL}]
        menu += [{"category": "nm_list", "title": title, "f_feed": STORY_FEED % fid} for title, fid in STORY_LISTS]
        menu += [{"category": "nm_podcasts", "title": _("Podcasts")},
                 {"category": "nm_live", "title": _("Live radio")}]
        menu += self.searchItems()
        for item in menu:
            params = {"name": "category"}
            params.update(item)
            # our own lists only: the search rows are no favourites ("Delete search history" has a function as desc)
            params["good_for_fav"] = item["category"].startswith("nm_") and item["category"] != "nm_live"
            self.addDir(params)

    def listLive(self, cItem):
        for title, url in LIVE:
            self.addAudio({"name": "category", "category": "nm_play", "title": title, "url": url, "direct": True,
                           "live": True, "desc": _("Live radio"), "good_for_fav": True})

    def _paged(self, cItem, items):
        # a list that is in memory, cut into pages: Main menu, First page, Jump and Next page (CH+/CH-) of
        # tools/iptvpaging; the "url" of the pager rows only carries the page for the Jump (the lists use f_feed)
        lastPage = max(1, (len(items) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        page = min(max(1, int(cItem.get("page", 1) or 1)), lastPage)
        start = (page - 1) * self.PAGE_SIZE
        for it in items[start:start + self.PAGE_SIZE]:
            self._addItem(cItem, it)
        pageUrlTpl = (cItem.get("f_feed") or MUSIC_PAGE).replace("{", "{{").replace("}", "}}") + "#page={page}"
        addPagingItems(self, cItem, page, page < lastPage, lastPage, pageUrlTpl)

    def listAll(self, cItem):
        items = self._allConcerts()
        if not items:
            SetIPTVPlayerLastHostError(_("No items found"))
        self._paged(cItem, items)

    def _listFeeds(self, cItem, table, template):
        for title, fid in table:
            params = dict(cItem)
            params.update({"category": "nm_list", "title": title, "f_feed": template % fid, "good_for_fav": True})
            self.addDir(params)

    def listPodcasts(self, cItem):
        self._listFeeds(cItem, PODCASTS, PODCAST_FEED)
        self._listFeeds(cItem, SHOWS, STORY_FEED)

    def listItems(self, cItem):
        items = self._feed(cItem.get("f_feed", ""))
        if not items:
            SetIPTVPlayerLastHostError(_("No items found"))
        self._paged(cItem, items)

    def listArchive(self, cItem):
        """Tiny Desk archive page by page: next page = same URL with ?date=MM-DD-YYYY of the last concert shown
        (that page starts with this concert again, it is left out there). No page count: no Jump."""
        page = max(1, int(cItem.get("page", 1) or 1))
        url = cItem.get("url") if page > 1 and cItem.get("url") else ARCHIVE_URL
        prevFirst, prevLast = (cItem.get("prev_first", ""), cItem.get("prev_last", "")) if page > 1 else ("", "")
        html = self._text(url, "text/html,application/xhtml+xml,*/*;q=0.8")
        entries = [e for e in parseArchive(html) if e[1] != prevLast]
        printDBG("NPRMusic.listArchive [%s] len[%s] entries[%s]" % (url, len(html), len(entries)))
        if not entries or entries[0][1] == prevFirst:
            SetIPTVPlayerLastHostError(_("No items found"))
            return
        for title, link, icon, desc in entries:
            ts, date = _tsFromUrl(link)
            self._addItem(cItem, {"title": title, "url": link, "desc": desc, "date": date, "ts": ts, "icon": icon,
                                  "audio": "", "duration": "", "video": True})
        m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", entries[-1][1])
        nextParams = None
        if m:
            nextParams = {"desc": "<= %s-%s-%s" % m.groups(), "prev_first": entries[0][1], "prev_last": entries[-1][1],
                          "url": "%s?date=%s-%s-%s" % (ARCHIVE_URL, m.group(2), m.group(3), m.group(1))}
        addPagingItems(self, cItem, page, bool(m), 0, "", nextParams)

    def _addItem(self, cItem, it):
        try:
            desc = self.cleanHtmlStr(it["desc"])
            meta = " | ".join([x for x in (it["date"], it["duration"]) if x])
            desc = "%s[/br]%s" % (meta, desc) if meta and desc else (meta or desc)
            # a row listed from a pager row: its page / last_page / image_type must not reach the videos
            params = stripPagerKeys(dict(cItem), ("f_feed", "prev_first", "prev_last"))
            isVideo = bool(it.get("video")) or bool(it.get("page_first"))
            params.update({"category": "nm_play", "title": normalizeMediathekTitle(self.cleanHtmlStr(it["title"]), date=it["date"]),
                           "url": it["url"], "audio": it["audio"], "fallback": it.get("fallback", ""),
                           "icon": it["icon"] or cItem.get("icon", ""), "desc": desc, "date": it["date"],
                           "duration": it["duration"], "live": False, "direct": bool(it["audio"]), "good_for_fav": True})
            (self.addVideo if isVideo or not it["audio"] else self.addAudio)(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("NPRMusic.listSearchResult [%s]" % searchPattern)
        pattern = searchPattern.lower().strip()
        for table, template in ((STORY_LISTS, STORY_FEED), (PODCASTS, PODCAST_FEED), (SHOWS, STORY_FEED)):
            for title, fid in table:
                if pattern in title.lower():
                    self.addDir({"name": "category", "category": "nm_list", "title": title,
                                 "f_feed": template % fid, "good_for_fav": True})
        seen = set()
        pool = list(self._allConcerts()) + self._feed(STORY_FEED % "1039")
        for it in pool:
            key = _slug(it["url"]) or it["title"]
            if key not in seen and (pattern in it["title"].lower() or pattern in it["desc"].lower()):
                seen.add(key)
                self._addItem({"name": "category"}, it)

    ###################################################
    # links
    ###################################################
    def _hlsVariants(self, master, meta):
        """HLS variants best first (the player would otherwise start on the lowest one)."""
        links = []
        try:
            text = self._text(master, "*/*")
            if "#EXT-X-STREAM-INF" not in text:
                return []
            lines = text.splitlines()
            variants = []
            for i, line in enumerate(lines):
                if not line.startswith("#EXT-X-STREAM-INF"):
                    continue
                res = re.search(r"RESOLUTION=(\d+)x(\d+)", line)
                bw = re.search(r"BANDWIDTH=(\d+)", line)
                uri = next((n.strip() for n in lines[i + 1:] if n.strip() and not n.startswith("#")), "")
                if uri:
                    w, h = (int(res.group(1)), int(res.group(2))) if res else (0, 0)
                    variants.append((h, int(bw.group(1)) if bw else 0, w, urljoin(master, uri)))
            variants.sort(reverse=True)
            for h, bw, w, url in variants:
                name = "HLS %sx%s  %s kbps" % (w, h, bw // 1000) if h else "HLS %s kbps" % (bw // 1000)
                links.append({"name": name, "url": strwithmeta(url, dict(meta)), "need_resolve": 0})
        except Exception:
            printExc()
        return links

    def _jwLinks(self, mediaId, meta):
        """JW Platform media API: progressive mp4 files (best first), then the HLS variants."""
        links = []
        try:
            data = self._text(JW_MEDIA % mediaId, "application/json, */*")
            j = json_loads(data)
            sources = j["playlist"][0]["sources"]
            # video/mp4 only: JW also lists an AAC rendition as audio/mp4
            mp4 = [(int(s.get("height") or 0), s.get("file", "")) for s in sources
                   if (s.get("type") or "") == "video/mp4" and s.get("file")]
            mp4.sort(reverse=True)
            for h, f in mp4[:3]:
                links.append({"name": "mp4 %sp" % h if h else "mp4", "url": strwithmeta(f, dict(meta)), "need_resolve": 0})
        except Exception:
            printExc()
        master = "https://cdn.jwplayer.com/manifests/%s.m3u8" % mediaId
        m2 = dict(meta)
        m2["iptv_proto"] = "m3u8"
        links += self._hlsVariants(master, m2)
        links.append({"name": "HLS (auto)", "url": strwithmeta(master, m2), "need_resolve": 0})
        return links

    def _linkFor(self, url, live=False):
        meta = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": "https://www.npr.org/"}
        if ".m3u8" in url:
            meta["iptv_proto"] = "m3u8"
        if live:
            meta["iptv_livestream"] = True
        ext = "HLS" if ".m3u8" in url else ("mp4" if re.search(r"\.mp4(\?|$)", url) else _("Audio"))
        return {"name": ext, "url": strwithmeta(url, meta), "need_resolve": 0}

    def _fromPage(self, url):
        html = self._text(url, "text/html,application/xhtml+xml,*/*;q=0.8")
        printDBG("NPRMusic._fromPage [%s] len[%s]" % (url, len(html)))
        return findMedia(html)

    def getLinksForVideo(self, cItem):
        printDBG("NPRMusic.getLinksForVideo [%s]" % cItem.get("url", ""))
        meta = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": "https://www.npr.org/"}
        urlTab = []
        if cItem.get("audio") or (cItem.get("direct") and cItem.get("url")):
            urlTab = [self._linkFor(cItem.get("audio") or cItem.get("url"), cItem.get("live", False))]
        else:
            for kind, val in self._fromPage(cItem.get("url", ""))[:3]:
                if kind == "jw":
                    urlTab += self._jwLinks(val, meta)
                elif kind == "youtube":
                    urlTab.append({"name": "YouTube", "url": val, "need_resolve": 1})
                else:
                    urlTab.append(self._linkFor(val))
            if cItem.get("fallback"):
                urlTab.append(dict(self._linkFor(cItem["fallback"]), name=_("Audio")))
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No items found"))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("NPRMusic.getVideoLinks [%s]" % videoUrl)
        if "youtube.com" in videoUrl or "youtu.be" in videoUrl:
            return self.up.getVideoLinkExt(videoUrl)
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        title = cItem.get("title", "")
        otherInfo = {"station": "NPR Music"}
        if cItem.get("live"):
            otherInfo["status"] = _("On Air")
        for key, field in (("released", "date"), ("duration", "duration")):
            if cItem.get(field):
                otherInfo[key] = cItem[field]
        icon = cItem.get("icon", "")
        text = cItem.get("desc", "")
        url = cItem.get("url", "")
        if "[/br]" not in text and not cItem.get("live") and "npr.org/" in url:
            # rows of the npr.org/music video list carry only the date: take the teaser of the story page
            html = self._text(url, "text/html,application/xhtml+xml,*/*;q=0.8")
            m = re.search(r"""<meta[^>]+(?:property|name)=["'](?:og:)?description["'][^>]+content=(["'])(.+?)\1""", html)
            if m:
                teaser = self.cleanHtmlStr(m.group(2))
                text = "%s[/br]%s" % (text, teaser) if text else teaser
        return [{"title": title, "text": text or title,
                 "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("nm_"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if refresh:
            self.feedCache = {}
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("NPRMusic.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu(self.currItem)
        elif category == "nm_all":
            self.listAll(self.currItem)
        elif category == "nm_podcasts":
            self.listPodcasts(self.currItem)
        elif category == "nm_archive":
            self.listArchive(self.currItem)
        elif category == "nm_live":
            self.listLive(self.currItem)
        elif category == "nm_list":
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, NPRMusic(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("nprmusic")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "nm_play"
