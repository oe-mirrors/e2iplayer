# -*- coding: utf-8 -*-
LAST_MODIFIED = "20.11.2026"
# Euronews: live channels and the videos of the public MRSS feeds, language selectable. Video streams from the og:video
# MP4 of the video page. Only the feeds below hold videos; too many requests at once are answered with 406, some
# networks get 406 always: then the listing pages, Dailymotion's public API and the YouTube live are the fallbacks.
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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
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


# fallback when euronews.com answers 406: the same videos and the live streams are on Dailymotion's public API
DM_API = "https://api.dailymotion.com/user/%s/videos?fields=id,title,description,created_time,thumbnail_720_url,onair,mode&sort=recent&limit=%d"
DM_USER = {"www": "euronews-en", "pt": "euronews-pt", "fr": "euronews-fr", "es": "euronews-es", "de": "euronews-de",
           "it": "euronews-it", "pl": "euronews-pl", "ru": "euronews-ru", "tr": "euronews-tr", "gr": "euronews-gr",
           "hu": "euronews-hu", "parsi": "euronews-fa", "arabic": "euronews-ar"}


# YouTube channels of the language editions: <handle>/live redirects to the running broadcast
YT_HANDLE = {"www": "euronews", "fr": "euronewsfr", "de": "euronewsde", "it": "euronewsit", "es": "euronewses",
             "pt": "euronewspt", "ru": "euronewsru", "pl": "euronewspl", "hu": "euronewshu", "tr": "euronewstr"}
DM_LIVE = "https://api.dailymotion.com/videos?owners=%s&live_onair=1&fields=id,title,onair,mode&limit=20"


def parseDmVideos(text):
    """Items of Dailymotion's /user/<name>/videos answer, in the same shape as parseRss."""
    items = []
    try:
        j = json_loads(text) if (text or "").strip().startswith("{") else {}
    except Exception:
        printExc()
        return items
    for v in j.get("list") or []:
        if not v.get("id"):
            continue
        t = v.get("created_time") or 0
        tm = time.gmtime(t) if t else None
        items.append({"title": ensure_str(v.get("title") or "").strip(), "url": "https://www.dailymotion.com/video/%s" % v["id"],
                      "desc": re.sub(r"<[^>]+>", "", ensure_str(v.get("description") or "")).strip(),
                      "date": time.strftime("%Y-%m-%d", tm) if tm else "", "ts": time.strftime("%Y%m%d%H%M%S", tm) if tm else "",
                      "icon": v.get("thumbnail_720_url") or "", "onair": bool(v.get("onair")), "mode": v.get("mode") or "", "id": v["id"]})
    return items


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


HTML_PATHS = {"theme:news": "/video", "program:top-news-stories-today": "/programs/top-news-stories-today",
              "program:nocomment": "/nocomment"}


def parseHtmlVideos(html, base):
    """Fallback when the RSS is blocked: the video cards of a listing page (same data as the MRSS items)."""
    items, seen = [], set()
    for m in re.finditer(r"<article\b[^>]*the-media-object[^>]*>.*?</article>", html or "", re.S):
        block = m.group(0)
        hm = re.search(r"""<a[^>]+href=["'](/(?:video/)?(\d{4})/(\d{2})/(\d{2})/[^"'#?]+)""", block)
        if not hm:
            continue
        if "the-media-object--has-video" not in block and not hm.group(1).startswith("/video/"):
            continue
        url = urljoin(base, hm.group(1))
        if url in seen:
            continue
        seen.add(url)
        t = re.search(r"""the-media-object__title[^>]*>\s*(.*?)\s*</""", block, re.S)
        title = t.group(1) if t else ""
        if not title.strip():
            t = re.search(r"""aria-label=["']([^"']+)""", block)
            title = t.group(1) if t else ""
        d = re.search(r"""the-media-object__description[^>]*>\s*(.*?)\s*</div>""", block, re.S)
        i = re.search(r"""<img[^>]+class=["']the-media-object__image["'][^>]+src=["']([^"']+)""", block)
        icon = re.sub(r"/\d+x\d+_cmsv2_", "/1536x864_cmsv2_", i.group(1)) if i else ""
        date = "%s-%s-%s" % (hm.group(2), hm.group(3), hm.group(4))
        items.append({"title": re.sub(r"<[^>]+>", "", ensure_str(title)).strip(), "url": url,
                      "desc": re.sub(r"<[^>]+>", "", ensure_str(d.group(1))).strip() if d else "",
                      "date": date, "ts": date.replace("-", "") + "000000", "icon": icon})
    return items


_JSON_SPECIAL = re.compile(r'["\\{}]')


def _isStr(v):
    return hasattr(v, "lower")


def _balancedObject(text, start):
    """Return the JSON object that starts with '{' at text[start] (string/escape aware)."""
    depth, inStr, skip = 0, False, 0
    for m in _JSON_SPECIAL.finditer(text, start):
        if m.start() < skip:
            continue
        c = m.group(0)
        if inStr:
            if c == "\\":
                skip = m.end() + 1
            elif c == '"':
                inStr = False
        elif c == '"':
            inStr = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:m.end()]
    return ""


def serverData(html):
    """The page's window.getInitialServerData = () => ({...}) as a dict (the site no longer relies on og:video only)."""
    m = re.search(r"getInitialServerData\s*=\s*\(\s*\)\s*=>\s*\(\s*\{", html or "")
    if not m:
        return {}
    try:
        d = json_loads(_balancedObject(html, m.end() - 1))
        return d if isinstance(d, dict) else {}
    except Exception:
        printExc()
        return {}


def _walk(obj, key="", depth=0):
    if depth > 12:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            for r in _walk(v, k, depth + 1):
                yield r
    elif isinstance(obj, list):
        for v in obj:
            for r in _walk(v, key, depth + 1):
                yield r
    else:
        yield key, obj


def _byPlayer(player, vid):
    player, vid = (player or "").lower(), (vid or "")
    if not vid or not _isStr(vid):
        return "", ""
    if "dailymotion" in player:
        return "dailymotion", "https://www.dailymotion.com/embed/video/%s" % vid
    if "jw" in player:
        return "jw", vid
    if "pfp" in player or "youtube" in player:
        return "youtube", "https://www.youtube.com/watch?v=%s" % vid
    return "", ""


def vodFromData(data):
    entities = data.get("entities") if isinstance(data, dict) else None
    entities = entities if isinstance(entities, dict) else {}
    video = entities.get("video") if isinstance(entities.get("video"), dict) else {}
    scope = video or entities
    # 1) direct media files
    mp4 = hls = ""
    for k, v in _walk(scope):
        if _isStr(v) and v.startswith("http"):
            path = v.split("?")[0].lower()
            if path.endswith(".mp4") and not mp4:
                mp4 = v
            elif path.endswith(".m3u8") and not hls:
                hls = v
    if mp4:
        return "mp4", mp4
    # 2) player + id declared by the page
    pd = video.get("playerData") if isinstance(video.get("playerData"), dict) else {}
    for c in (pd.get("desktopPlayerData"), pd.get("mobilePlayerData"), pd, video):
        if isinstance(c, dict):
            kind, url = _byPlayer(c.get("player"), c.get("videoId") or c.get("mediaId") or c.get("id"))
            if kind:
                return kind, url
    if hls:
        return "hls", hls
    # 3) specific key names anywhere under the video entity
    ids = {}
    player = ""
    for k, v in _walk(scope):
        lk = k.lower() if _isStr(k) else ""
        if _isStr(v) and v:
            if lk == "player" and not player:
                player = v
            elif lk in ("dailymotionvideoid", "dailymotionid", "jwplayermediaid", "jwmediaid", "youtubevideoid", "youtubeid", "videoid"):
                ids.setdefault(lk, v)
    if ids.get("dailymotionvideoid") or ids.get("dailymotionid"):
        return _byPlayer("dailymotion", ids.get("dailymotionvideoid") or ids.get("dailymotionid"))
    if ids.get("jwplayermediaid") or ids.get("jwmediaid"):
        return "jw", ids.get("jwplayermediaid") or ids.get("jwmediaid")
    if ids.get("youtubevideoid") or ids.get("youtubeid"):
        return _byPlayer("youtube", ids.get("youtubevideoid") or ids.get("youtubeid"))
    if ids.get("videoid"):
        return _byPlayer(player, ids["videoid"])
    return "", ""


def findVod(html):
    """Find the stream of a video page: ('mp4'|'hls'|'jw'|'youtube'|'dailymotion'|'', url-or-id)."""
    html = html or ""
    for rx in (r"""<meta[^>]+property=["']og:video(?::secure_url|:url)?["'][^>]+content=["']([^"']+)""",
               r"""<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:video(?::secure_url|:url)?["']""",
               r"""<meta[^>]+(?:name|property)=["']nli:video["'][^>]+content=["']([^"']+)"""):
        m = re.search(rx, html)
        if m and m.group(1).startswith("http"):
            url = m.group(1).replace("&amp;", "&")
            path = url.split("?")[0].lower()
            if path.endswith(".mp4"):
                return "mp4", url
            if path.endswith(".m3u8"):
                return "hls", url
    kind, url = vodFromData(serverData(html))
    if kind:
        return kind, url
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
            kind, url = _byPlayer(d.get("player"), d.get("videoId") or d.get("id"))
            if kind:
                return kind, url
        except Exception:
            printExc()
    # last resorts: ids / files referenced anywhere in the page
    m = re.search(r"""dailymotion\.com/(?:embed/)?video/([a-z0-9]+)""", html) or \
        re.search(r"""geo\.dailymotion\.com/player[^"'\s]*?[?&]video=([a-z0-9]+)""", html)
    if m:
        return "dailymotion", "https://www.dailymotion.com/embed/video/%s" % m.group(1)
    m = re.search(r"""cdn\.jwplayer\.com/(?:v2/media|previews|manifests)/([A-Za-z0-9]{8})""", html)
    if m:
        return "jw", m.group(1)
    m = re.search(r"""youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=)([\w-]{11})""", html)
    if m:
        return "youtube", "https://www.youtube.com/watch?v=%s" % m.group(1)
    m = re.search(r"""https?:\\?/\\?/[^"'\s<>]+?\.mp4[^"'\s<>]*""", html)
    if m:
        return "mp4", m.group(0).replace("\\/", "/").replace("&amp;", "&")
    return "", ""


class Euronews(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "lang", "f_feeds", "icon", "desc", "live")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "euronews", "cookie": "euronews.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept": "*/*", "Accept-Encoding": "identity", "Referer": "https://www.euronews.com/"})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.feedCache = {}
        self.blockedAt = 0
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

    def _text(self, url, accept=None, extra=None, cookies=True, identity=True):
        params = dict(self.defaultParams)
        header = dict(self.HEADER)
        if not identity:
            header.pop("Accept-Encoding", None)
        # the site answers 406 to clients that do not look like a browser: send the headers Chrome sends
        ver = re.search(r"Chrome/(\d+)", header.get("User-Agent", ""))
        ver = ver.group(1) if ver else "130"
        xhr = bool(accept and accept.startswith("application/json"))
        header.update({"Accept-Language": "en-GB,en;q=0.9",
                       "sec-ch-ua": '"Chromium";v="%s", "Google Chrome";v="%s", "Not?A_Brand";v="99"' % (ver, ver),
                       "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
                       "Sec-Fetch-Site": "same-origin"})
        if xhr:
            header.update({"Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors"})
        else:
            header.update({"Upgrade-Insecure-Requests": "1", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-User": "?1"})
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
        if time.time() - self.blockedAt < FEED_CACHE_SECONDS:
            return []
        data = self._text(url, "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5")
        printDBG("Euronews._feed [%s] len[%s]" % (url, len(data)))
        items = parseRss(data)
        if not items:
            # RSS blocked (406): read the video cards of the listing page instead
            page = "https://%s.euronews.com%s" % (lang, HTML_PATHS.get("%s:%s" % (level, name), "/video"))
            html = self._text(page, "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", identity=False)
            items = parseHtmlVideos(html, page)
            printDBG("Euronews._feed html [%s] len[%s] -> %s items" % (page, len(html), len(items)))
            if not data and not html:
                # both refused: the other feeds would be too, use the Dailymotion fallback for a while
                self.blockedAt = time.time()
        if items:
            self.feedCache[url] = (time.time(), items)
        return items

    def _dmVideos(self, lang, limit=50):
        for user in (DM_USER.get(lang), DM_USER["www"]):
            if not user:
                continue
            url = DM_API % (user, limit)
            cached = self.feedCache.get(url)
            if cached and time.time() - cached[0] < FEED_CACHE_SECONDS:
                return cached[1]
            data = self._text(url, "application/json, text/plain, */*", {"Referer": "https://www.dailymotion.com/"}, cookies=False)
            items = parseDmVideos(data)
            printDBG("Euronews._dmVideos [%s] len[%s] -> %s items" % (url, len(data), len(items)))
            if items:
                self.feedCache[url] = (time.time(), items)
                return items
        return []

    def _dmLive(self, lang):
        """Id of the Dailymotion live that is on air for the language."""
        user = DM_USER.get(lang)
        if not user:
            return ""
        url = DM_LIVE % user
        data = self._text(url, "application/json, text/plain, */*", {"Referer": "https://www.dailymotion.com/"}, cookies=False)
        onair = [it["id"] for it in parseDmVideos(data) if it.get("onair")]
        printDBG("Euronews._dmLive [%s] len[%s] -> onair %s" % (url, len(data), onair))
        return onair[0] if onair else ""

    def _ytLive(self, lang):
        """Video id of the running YouTube live of the language edition."""
        handle = YT_HANDLE.get(lang)
        if not handle:
            return ""
        url = "https://www.youtube.com/@%s/live" % handle
        html = self._text(url, "text/html,application/xhtml+xml,*/*;q=0.8", {"Referer": "https://www.youtube.com/", "Cookie": "CONSENT=YES+1; SOCS=CAI"}, cookies=False, identity=False)
        m = re.search(r"""<link rel=["']canonical["'] href=["']https://www\.youtube\.com/watch\?v=([\w-]{11})""", html)
        printDBG("Euronews._ytLive [%s] len[%s] -> %s" % (url, len(html), m.group(1) if m else ""))
        return m.group(1) if m else ""

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
        if not items:
            items = self._dmVideos(lang)
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
            desc = self.cleanHtmlStr(it["desc"])
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
            if not links:
                kind, url = findVod(pageHtml)
                if kind == "dailymotion":
                    links.append({"name": "Dailymotion live", "url": strwithmeta(url, {"iptv_livestream": True}), "need_resolve": 1})
                elif kind == "youtube":
                    links.append({"name": "YouTube live", "url": strwithmeta(url, {"iptv_livestream": True}), "need_resolve": 1})
            if links:
                return links
        # euronews.com refused: YouTube first (the Dailymotion live master answered 403 in tests)
        links = []
        ytId = self._ytLive(lang)
        if ytId:
            links.append({"name": "YouTube live", "url": strwithmeta("https://www.youtube.com/watch?v=%s" % ytId, {"iptv_livestream": True}), "need_resolve": 1})
        dmId = self._dmLive(lang)
        if dmId:
            links.append({"name": "Dailymotion live", "url": strwithmeta("https://www.dailymotion.com/embed/video/%s" % dmId, {"iptv_livestream": True}), "need_resolve": 1})
        return links

    def _hlsLinks(self, master):
        """The player starts the master playlist on its lowest variant (428x240): list the variants, best first."""
        meta = {"iptv_proto": "m3u8", "iptv_livestream": True, "User-Agent": self.HEADER.get("User-Agent")}
        links = []
        text = self._text(master, "*/*", cookies=False, identity=False)
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

    def _jwLinks(self, mediaId):
        """JW Player media: mp4 files best first, then HLS."""
        links = []
        data = self._text("https://cdn.jwplayer.com/v2/media/%s" % mediaId, "application/json, */*", cookies=False, identity=False)
        try:
            j = json_loads(data) if data.strip().startswith("{") else {}
            sources = (j.get("playlist") or [{}])[0].get("sources") or []
        except Exception:
            printExc()
            sources = []
        ua = {"User-Agent": self.HEADER.get("User-Agent")}
        mp4 = sorted([x for x in sources if x.get("file") and "mp4" in (x.get("type") or "")], key=lambda x: x.get("height") or 0, reverse=True)
        for x in mp4:
            links.append({"name": "mp4 %sp" % (x.get("height") or "?"), "url": strwithmeta(x["file"], ua), "need_resolve": 0})
        for x in sources:
            if x.get("file") and "mpegurl" in (x.get("type") or ""):
                links.append({"name": "hls", "url": strwithmeta(x["file"], dict(ua, iptv_proto="m3u8")), "need_resolve": 0})
        return links

    def getLinksForVideo(self, cItem):
        printDBG("Euronews.getLinksForVideo [%s]" % cItem.get("url", ""))
        live = bool(cItem.get("live"))
        if live:
            urlTab = self._liveLinks(self._lang(cItem))
        else:
            if "dailymotion.com/video/" in cItem.get("url", ""):
                kind, url = "dailymotion", cItem["url"].replace("/video/", "/embed/video/")
            else:
                kind, url = findVod(self._text(cItem.get("url", ""), "text/html", identity=False))
            printDBG("Euronews.getLinksForVideo kind[%s] url[%s]" % (kind, url))
            ua = {"User-Agent": self.HEADER.get("User-Agent")}
            if kind == "mp4":
                urlTab = [{"name": "mp4", "url": strwithmeta(url, ua), "need_resolve": 0}]
            elif kind == "hls":
                urlTab = [{"name": "hls", "url": strwithmeta(url, dict(ua, iptv_proto="m3u8")), "need_resolve": 0}]
            elif kind == "jw":
                urlTab = self._jwLinks(url)
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
