# -*- coding: utf-8 -*-
LAST_MODIFIED = "31.10.2026"
# Euronews: live channels and the videos of the public MRSS feeds, language selectable. Video streams from the og:video
# MP4 of the video page. Only the feeds below hold videos; too many requests at once are answered with 406.
###################################################
# LOCAL import
###################################################
from Components.config import config, ConfigSelection, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
###################################################
# FOREIGN import
###################################################
from email.utils import parsedate
from xml.etree import ElementTree as ET
import re
import time

try:
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urljoin
###################################################

# (subdomain of euronews.com, name of the language in that language)
LANGUAGES = [("www", "English"), ("pt", "Português"), ("fr", "Français"), ("es", "Español"),
             ("de", "Deutsch"), ("it", "Italiano"), ("pl", "Polski"), ("ru", "Русский"),
             ("tr", "Türkçe"), ("gr", "Ελληνικά"), ("hu", "Magyar"), ("parsi", "فارسی"),
             ("arabic", "العربية")]
LANG_NAME = dict(LANGUAGES)

config.plugins.iptvplayer.euronews_language = ConfigSelection(default="www", choices=[(code, name) for code, name in LANGUAGES])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language:"), config.plugins.iptvplayer.euronews_language))
    return optionList


def gettytul():
    return "https://www.euronews.com/"


RSS_URL = "https://%s.euronews.com/rss?format=mrss&level=%s&name=%s"
LIVE_API = "https://%s.euronews.com/api/live/data?locale=%s"
FEED_NEWS = "theme:news"
FEED_TOP = "program:top-news-stories-today"
FEED_NOCOMMENT = "program:nocomment"
ALL_FEEDS = ",".join((FEED_NEWS, FEED_TOP, FEED_NOCOMMENT))
FEED_CACHE_SECONDS = 300
VIDEOS_PER_PAGE = 30

# live: languages whose API returns a stream; English is served through the Turkish endpoint (it returns euronews-en)
LIVE_LANGS = ["www", "pt", "fr", "es", "de", "it", "pl", "ru", "hu"]
LIVE_ALIAS = {"www": ["www", "tr"]}


def parseRss(text):
    """Return the video items of an MRSS feed: dicts with title, url, desc, date (yyyy-mm-dd), icon."""
    items = []
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text or "").strip()
    if not text.startswith("<rss"):
        return items
    try:
        root = ET.fromstring(text)
    except Exception:
        printExc()
        return items
    for item in root.iter("item"):
        link = ensure_str(item.findtext("link") or "").strip()
        if "/video/" not in link:
            continue
        icon = ""
        for el in item:
            if el.tag.endswith("}content") and el.get("url"):
                icon = ensure_str(el.get("url"))
                break
        date, ts = "", ""
        pd = parsedate(item.findtext("pubDate") or "")
        if pd:
            date = "%04d-%02d-%02d" % (pd[0], pd[1], pd[2])
            ts = "%04d%02d%02d%02d%02d%02d" % tuple(pd[:6])
        icon = re.sub(r"/\d+x\d+_cmsv2_", "/1536x864_cmsv2_", icon)   # larger poster instead of the 696x392 thumbnail
        items.append({"title": ensure_str(item.findtext("title") or "").strip(), "url": link,
                      "desc": ensure_str(item.findtext("description") or "").strip(), "date": date, "ts": ts, "icon": icon})
    return items


def findVod(html):
    """Find the stream of a video page: ('mp4'|'youtube'|'dailymotion'|'', url)."""
    for rx in (r"""<meta[^>]+property=["']og:video["'][^>]+content=["']([^"']+)""",
               r"""<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:video["']""",
               r"""<meta[^>]+(?:name|property)=["']nli:video["'][^>]+content=["']([^"']+)"""):
        m = re.search(rx, html)
        if m and m.group(1).startswith("http"):
            return "mp4", m.group(1).replace("&amp;", "&")
    m = re.search(r"""<iframe[^>]+id=["']pfpPlayer["'][^>]+src=["'](https://www\.youtube\.com/[^"']+)""", html) or \
        re.search(r"""<iframe[^>]+src=["'](https://www\.youtube\.com/[^"']+)["'][^>]+id=["']pfpPlayer["']""", html)
    if m:
        return "youtube", m.group(1)
    m = re.search(r"""data-video=(["'])(\{.*?\})\1""", html, re.S)
    if m:
        try:
            d = json_loads(m.group(2).replace("&quot;", '"').replace("&amp;", "&"))
            if d.get("url"):
                return "mp4", d["url"]
            if d.get("player") == "dailymotion" and d.get("id"):
                return "dailymotion", "https://www.dailymotion.com/embed/video/%s" % d["id"]
            vid = d.get("videoId") or d.get("id")
            if d.get("player") == "pfp" and vid:
                return "youtube", "https://www.youtube.com/watch?v=%s" % vid
        except Exception:
            printExc()
    return "", ""


class Euronews(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "lang", "f_feeds", "icon", "desc", "live")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "euronews", "cookie": "euronews.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept": "*/*", "Accept-Encoding": "identity", "Referer": "https://www.euronews.com/"})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/euronews135.png")
        self.feedCache = {}
        self.watchedHelper = IPTVWatchedHelper("euronews")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            if cItem.get("type", "") == "video":
                url = cItem.get("url", "")
                return "video:%s" % url if url else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _lang(self, cItem):
        lang = cItem.get("lang") or config.plugins.iptvplayer.euronews_language.value
        return lang if lang in LANG_NAME else "www"

    def _text(self, url, accept=None, extra=None, cookies=False, identity=True):
        params = dict(self.defaultParams)
        header = dict(self.HEADER)
        if not identity:
            header.pop("Accept-Encoding", None)
        if accept:
            header["Accept"] = accept
        if extra:
            header.update(extra)
        params["header"] = header
        if cookies:
            params.update({"use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE})
        sts, data = self.cm.getPage(url, params)
        if not sts or not data:
            return ""
        if not isinstance(data, str):
            try:
                data = data.decode("utf-8")
            except Exception:
                data = data.decode("latin-1")
        return data

    def _feed(self, lang, level, name):
        url = RSS_URL % (lang, level, name)
        cached = self.feedCache.get(url)
        if cached and time.time() - cached[0] < FEED_CACHE_SECONDS:
            return cached[1]
        data = self._text(url)
        printDBG("Euronews._feed [%s] len[%s]" % (url, len(data)))
        items = parseRss(data)
        if items:
            self.feedCache[url] = (time.time(), items)
        return items

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        lang = self._lang(cItem)
        menu = [{"category": "eu_live", "title": _("Live channels")},
                {"category": "eu_list", "title": _("Latest videos"), "f_feeds": ALL_FEEDS},
                {"category": "eu_list", "title": "No Comment", "f_feeds": FEED_NOCOMMENT},
                {"category": "eu_list", "title": "Top News Stories Today", "f_feeds": FEED_TOP}]
        menu += self.searchItems()
        for item in menu:
            params = {"name": "category", "lang": lang}
            params.update(item)
            params["good_for_fav"] = item["category"] in ("eu_list", "eu_live")
            self.addDir(params)

    def listLive(self, cItem):
        lang = self._lang(cItem)
        order = ([lang] if lang in LIVE_LANGS else []) + [code for code in LIVE_LANGS if code != lang]
        for code in order:
            self.addVideo({"name": "category", "category": "eu_live_video", "lang": code,
                           "title": "Euronews - %s" % LANG_NAME[code], "url": "https://%s.euronews.com/live" % code,
                           "desc": _("Live channels"), "live": True, "good_for_fav": True})

    ###################################################
    # video lists
    ###################################################
    def _feedsOf(self, spec):
        return [tuple(x.split(":", 1)) for x in (spec or ALL_FEEDS).split(",") if ":" in x]

    def _collect(self, lang, feeds):
        seen, items = set(), []
        for level, name in feeds:
            for it in self._feed(lang, level, name):
                if it["url"] not in seen:
                    seen.add(it["url"])
                    items.append(it)
        items.sort(key=lambda x: x.get("ts", ""), reverse=True)
        return items

    def listVideos(self, cItem, query=""):
        lang = self._lang(cItem)
        items = self._collect(lang, self._feedsOf(cItem.get("f_feeds")))
        if query:
            pattern = query.lower()
            items = [it for it in items if pattern in it["title"].lower() or pattern in it["desc"].lower()]
        printDBG("Euronews.listVideos feeds[%s] -> %s items" % (cItem.get("f_feeds"), len(items)))
        # the feeds hold everything at once, the pages are only cut from them
        lastPage = (len(items) + VIDEOS_PER_PAGE - 1) // VIDEOS_PER_PAGE
        page = min(int(cItem.get("page", 1) or 1), max(lastPage, 1))
        for it in items[(page - 1) * VIDEOS_PER_PAGE:page * VIDEOS_PER_PAGE]:
            self._addResult(cItem, it, lang)
        addPagingItems(self, cItem, page, page < lastPage, lastPage, self.MAIN_URL)

    def _addResult(self, cItem, it, lang):
        try:
            desc = it["desc"]
            if it["date"]:
                desc = "%s[/br]%s" % (it["date"], desc) if desc else it["date"]
            params = stripPagerKeys(dict(cItem), ("f_feeds", "s_query"))
            params.update({"category": "eu_video", "title": normalizeMediathekTitle(self.cleanHtmlStr(it["title"]), date=it["date"]),
                           "lang": lang, "url": it["url"], "icon": it["icon"] or cItem.get("icon", ""),
                           "desc": desc, "live": False, "good_for_fav": True})
            self.addVideo(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Euronews.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem, category="eu_search", s_query=searchPattern, url="")
        self.listVideos(cItem, searchPattern)

    ###################################################
    # links
    ###################################################
    def _liveApi(self, lang):
        """Live API, called with the cookies and the Referer of the /live page like the site's player."""
        page = "https://%s.euronews.com/live" % lang
        api = LIVE_API % (lang, lang)
        pageHtml = self._text(page, "text/html,application/xhtml+xml,*/*;q=0.8", cookies=True, identity=False)
        extra = {"Referer": page, "Accept-Language": "en-GB,en;q=0.9"}
        data = self._text(api, "application/json, text/plain, */*", extra, cookies=True, identity=False)
        printDBG("Euronews._liveApi [%s] data[%s]" % (lang, data[:200]))
        try:
            j = json_loads(data) if data.strip().startswith("{") else {}
        except Exception:
            printExc()
            j = {}
        return (j if isinstance(j, dict) else {}), pageHtml

    def _liveLinks(self, lang):
        for code in LIVE_ALIAS.get(lang, [lang]):
            j, pageHtml = self._liveApi(code)
            hls = j.get("videoPrimaryUrl") or ""
            if ".m3u8" not in hls:
                m = re.search(r"""https?:\\?/\\?/[^"'\s<>]+?\.m3u8[^"'\s<>]*""", pageHtml or "")
                hls = m.group(0).replace("\\/", "/").replace("&amp;", "&") if m else ""
            links = self._hlsLinks(hls) if hls else []
            # the site's main player; the API's cached HLS token can be hours old (403)
            if j.get("videoId") and j.get("player") == "dailymotion":
                links.append({"name": "Dailymotion live", "url": strwithmeta("https://www.dailymotion.com/embed/video/%s" % j["videoId"], {"iptv_livestream": True}), "need_resolve": 1})
            elif j.get("videoId") and j.get("player") == "pfp":
                links.append({"name": "YouTube live", "url": strwithmeta("https://www.youtube.com/watch?v=%s" % j["videoId"], {"iptv_livestream": True}), "need_resolve": 1})
            if links:
                return links
        return []

    def _hlsLinks(self, master):
        """The player starts the master playlist on its lowest variant (428x240): list the variants, best first."""
        meta = {"iptv_proto": "m3u8", "iptv_livestream": True, "User-Agent": self.HEADER.get("User-Agent")}
        links = []
        text = self._text(master, "*/*", identity=False)
        if "#EXTM3U" not in text:
            return links
        try:
            query = master.split("?", 1)[1] if "?" in master else ""
            lines = text.splitlines()
            variants = []
            for i, line in enumerate(lines):
                if not line.startswith("#EXT-X-STREAM-INF"):
                    continue
                res = re.search(r"RESOLUTION=(\d+)x(\d+)", line)
                bw = re.search(r"BANDWIDTH=(\d+)", line)
                uri = ""
                for nxt in lines[i + 1:]:
                    if nxt.strip() and not nxt.startswith("#"):
                        uri = nxt.strip()
                        break
                if not uri:
                    continue
                url = urljoin(master, uri)
                if query and "hdnea=" not in url:
                    url += ("&" if "?" in url else "?") + query
                width, height = (int(res.group(1)), int(res.group(2))) if res else (0, 0)
                variants.append((height, int(bw.group(1)) if bw else 0, width, url))
            variants.sort(reverse=True)
            printDBG("Euronews._hlsLinks variants %s" % [(v[2], v[0], v[1]) for v in variants])
            for height, bw, width, url in variants:
                name = "%sx%s  %s kbps" % (width, height, bw // 1000) if height else "%s kbps" % (bw // 1000)
                links.append({"name": name, "url": strwithmeta(url, dict(meta)), "need_resolve": 0})
        except Exception:
            printExc()
        links.append({"name": "HLS live (auto)", "url": strwithmeta(master, dict(meta)), "need_resolve": 0})
        return links

    def getLinksForVideo(self, cItem):
        printDBG("Euronews.getLinksForVideo [%s]" % cItem.get("url", ""))
        live = bool(cItem.get("live"))
        if live:
            urlTab = self._liveLinks(self._lang(cItem))
        else:
            kind, url = findVod(self._text(cItem.get("url", ""), "text/html"))
            if kind == "mp4":
                urlTab = [{"name": "mp4", "url": strwithmeta(url, {"User-Agent": self.HEADER.get("User-Agent")}), "need_resolve": 0}]
            elif kind in ("youtube", "dailymotion"):
                urlTab = [{"name": kind, "url": url, "need_resolve": 1}]
            else:
                urlTab = []
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return urlTab if live else applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("Euronews.getVideoLinks [%s]" % videoUrl)
        if "youtube.com" not in videoUrl and "youtu.be" not in videoUrl and "dailymotion.com" not in videoUrl:
            return []
        links = self.up.getVideoLinkExt(videoUrl)
        if strwithmeta(videoUrl).meta.get("iptv_livestream"):
            for link in links:
                link["url"] = self.up.decorateUrl(link["url"], {"iptv_livestream": True})
            return links
        return decorateResolvedLinkItems(links, sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Euronews.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("live"):
            otherInfo["status"] = _("On Air")
            text = text or "%s - %s" % (title, _("Live channels"))
        else:
            otherInfo["station"] = "Euronews"
        return [{"title": title, "text": text or title, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("eu_"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", "")
        printDBG("Euronews.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu(self.currItem)
        elif category == "eu_live":
            self.listLive(self.currItem)
        elif category == "eu_list":
            self.listVideos(self.currItem)
        elif category == "eu_search":
            self.listVideos(self.currItem, self.currItem.get("s_query", ""))
        elif category == "search":
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search", "lang": self._lang(self.currItem)}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Euronews(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("euronews")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("eu_video", "eu_live_video")
