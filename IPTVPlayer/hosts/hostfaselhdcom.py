# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.10.2026 - links are no longer renamed to "*name*" after use - that broke the link list's own used mark (tick + colour)
# 10.10.2026 - rewrite for www.fasel-hd.co (FaselHD moved there; faselhd.co, faselhds.* and the other old domains
#   answer 301/302 to it), the whole site sits behind a Cloudflare check
#   - pages go through getPageCFProtection (curl-impersonate / MyE2i when Cloudflare asks); covers on the site's own
#     domain then carry the cf_clearance cookie + the User-Agent that passed the check (getFullIconUrl), covers on
#     static.faselhdcdn.com get the site as Referer; a domain the site redirects to is taken over for the session
#   - menu: movies, series, TV shows, Asian, anime (their sub-lists read live from the site's own menu), recently
#     added, search; lists with First page / Jump / Next page (the site's "/page/N", last page from its pager)
#   - films are VIDEO rows; series / shows / anime open their seasons (the site's season tiles, "/?p=<id>") and the
#     episodes of a season (ascending, local paging over 100); a page without seasons or episodes is one VIDEO row
#   - links: the page's watch servers (video_player?player_token=...) - resolved only when chosen: the player page's
#     scripts run in the box's JS engine (QuickJS / duktape, stubbed DOM) and give the HLS qualities; download
#     servers are listed only when urlparser knows the hoster
#   - watched flag (series -> season -> episode, keys on the url path / the season's post id, domain independent),
#     downloaded flag, favourites (rows of the old version reopen too), name normalisation ("Title (Year)",
#     "Show - SxxExx"), sidecar, INFO via moviemeta + the page's story/poster/fields; no colour codes in titles
# 10.10.2026 - review: an error of the JS engine call no longer ends the link resolving (the page's plain m3u8 urls
#   are still tried)
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import decorateUrl
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.fasel-hd.co/"


LOCAL_PAGE_SIZE = 100
# the site's own domains (it moves often; the old ones redirect) - not static.faselhdcdn.com / faselhdstream.com
SITE_DOMAIN_RE = re.compile(r"^https?://(?:[a-z0-9-]+\.)*(?:fasel-hd|faselhds?)\.[a-z]{2,10}(?=[/?#]|$)", re.I)
CDN_DOMAIN_RE = re.compile(r"^https?://(?:[a-z0-9-]+\.)*faselhdcdn\.com/", re.I)
# first path segment of a card link -> row kind
MOVIE_SEGS = ("movies", "dubbed-movies", "hindi", "asian-movies", "anime-movies")
EPISODE_SEGS = ("episodes", "anime-episodes", "asian-episodes", "tvepisodes")
LIST_SEGS = ("collections",)
# menu groups: the site's dropdown that holds this path
MENU_GROUPS = (("movies", "/movies"), ("series", "/series"), ("tvshows", "/tvshows"), ("asian", "/asian-series"), ("anime", "/anime"))
# Arabic ordinals of season labels ("الموسم الثاني"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("السادس عشر", 16), ("السابع عشر", 17), ("الثامن عشر", 18), ("التاسع عشر", 19), ("العشرون", 20),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6), ("السادس", 6),
    ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:الموسم|موسم)\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s)\(?((?:19|20)\d{2})\)?(?=\s|$)")
# leading kind word of a title ("فيلم", "مسلسل", "انمي", "برنامج") and site words that are no part of a name
KIND_RE = re.compile(r"^\s*(?:الفيلم|فيلم|الفلم|فلم|مسلسل|المسلسل|انمي|أنمي|الانمي|برنامج|عرض)\s+")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|مدبلج|مدبلجة|والاخيرة|والأخيرة|الاخيرة|الأخيرة|اون لاين|أون لاين|مشاهدة|وتحميل|كامل|كاملة|HD)(?=\s|$)")
DUB_RE = re.compile(r"(?:^|\s)مدبلجة?(?=\s|$)")
DUB_WORD = "مدبلج"
# the site's labels end with " - فاصل اعلاني FaselHD" (page titles of its lists)
SITE_SUFFIX_RE = re.compile(r"\s*(?:(?:-|–|&#8211;)\s*)?فاصل\s+(?:اعلاني|إعلاني)\s*FaselHD\s*$", re.I)
# fields of the page's "singleList" ("تصنيف الفيلم : ...") -> INFO keys
INFO_KEYS = (("تصنيف", "genres"), ("جودة", "quality"), ("مستوى المشاهدة", "age_limit"), ("سنة", "year"), ("دول", "country"),
             ("مدة", "duration"), ("توقيت", "duration"), ("إخراج", "director"), ("اخراج", "director"), ("بطولة", "actors"),
             ("حالة", "status"), ("اللغة", "language"), ("عدد الحلقات", "episodes"), ("المواسم", "seasons"))
# minimal DOM for the player page's scripts: they write the quality buttons (document.write) and set up jwplayer
PLAYER_JS_STUB = """var window = this; var self = this; var top = this; var parent = this;
var navigator = {userAgent: 'Mozilla/5.0', platform: 'Win32', language: 'ar'};
var location = {href: '', hostname: '', protocol: 'https:', search: ''};
var __el = {setAttribute: function () {}, getAttribute: function () { return ''; }, appendChild: function () {}, insertBefore: function () {},
    addEventListener: function () {}, removeEventListener: function () {}, style: {}, children: [], classList: {add: function () {}, remove: function () {}}};
var document = {write: function (s) { print('WRITE:' + s); }, writeln: function (s) { print('WRITE:' + s); },
    createElement: function () { return __el; }, querySelector: function () { return __el; }, querySelectorAll: function () { return [__el]; },
    getElementById: function () { return __el; }, getElementsByTagName: function () { return [__el]; }, addEventListener: function () {},
    cookie: '', referrer: '', body: __el, head: __el, documentElement: __el, location: location};
window.addEventListener = function () {}; window.removeEventListener = function () {};
var __player = {setup: function (c) { print('SETUP:' + JSON.stringify(c)); return __player; }, on: function () { return __player; },
    load: function () {}, play: function () {}, pause: function () {}, seek: function () {}, getPosition: function () { return 0; }};
var jwplayer = function () { return __player; };
var __q = {on: function () { return __q; }, fadeIn: function () { return __q; }, fadeOut: function () { return __q; }, attr: function () { return ''; },
    removeClass: function () { return __q; }, addClass: function () { return __q; }, html: function (s) { print('WRITE:' + s); return __q; },
    append: function (s) { print('WRITE:' + s); return __q; }, click: function () { return __q; }, show: function () { return __q; }, hide: function () { return __q; }};
var $ = function () { return __q; }; var jQuery = $;
var setTimeout = function () {}; var setInterval = function () {}; var clearTimeout = function () {}; var clearInterval = function () {};
"""


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


def _episodeNum(text):
    m = EPISODE_RE.search(text or "")
    return str(int(m.group(1))) if m else ""


def _clean(text):
    text = SITE_SUFFIX_RE.sub("", text or "")
    # the en dash as a whole sequence (py2 str.strip would take its single utf-8 bytes)
    text = text.replace("–", " ")
    text = JUNK_RE.sub(" ", JUNK_RE.sub(" ", KIND_RE.sub("", text)))
    return re.sub(r"\s+", " ", text).strip(" -:|")


def _showName(text):
    # "مسلسل Dark Matter الموسم الثاني – الحلقة 2" -> "Dark Matter"
    text = SITE_SUFFIX_RE.sub("", text or "").replace("–", " ")
    for regex in (EPISODE_RE, SEASON_RE):
        m = regex.search(text)
        if m:
            text = text[:m.start()]
    return _clean(text)


def _splitYear(text):
    # "فيلم The Baltimorons 2025 مترجم" -> ("The Baltimorons", "2025")
    title = _clean(text)
    years = list(YEAR_RE.finditer(title))
    m = years[-1] if years else None
    if m and m.start() > 0:
        return re.sub(r"\s+", " ", title[:m.start()] + " " + title[m.end():]).strip(" -:|"), m.group(1)
    return title, ""


class FaselhdCOM(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "season_id", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "faselhd.com", "cookie": "faselhd.com.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/faselhdcom135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "fh_menu", "title": _("Movies"), "group": "movies"},
            {"category": "fh_menu", "title": _("Series"), "group": "series"},
            {"category": "fh_menu", "title": _("TV Shows"), "group": "tvshows"},
            {"category": "fh_menu", "title": _("Asian"), "group": "asian"},
            {"category": "fh_menu", "title": _("Anime"), "group": "anime"},
            {"category": "fh_list", "title": _("Recently added"), "url": self.MAIN_URL + "most_recent"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("faselhdcom")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        sts, data = self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)
        if sts:
            # the site moved: take over the domain it redirected to for this session
            m = SITE_DOMAIN_RE.match(self.cm.meta.get("url", "") or "")
            if m and m.group(0).lower().rstrip("/") + "/" != self.MAIN_URL.lower():
                printDBG("FaselhdCOM: site moved to %s" % m.group(0))
                self.MAIN_URL = m.group(0).rstrip("/") + "/"
        return sts, data

    def _canonUrl(self, url):
        # one form for every page url: the current domain (also for links / favourites of old domains),
        # percent-encoded Arabic slugs
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        elif not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        url = SITE_DOMAIN_RE.sub(self.MAIN_URL.rstrip("/"), url)
        # only the path: a query (player_token, search words) stays exactly as given
        path, sep, query = url.partition("?")
        try:
            return urllib_quote(urllib_unquote(path), safe=":/#+,;@%") + sep + query
        except Exception:
            printExc()
        return url

    def getFullUrl(self, url, currUrl=None):
        return self._canonUrl(url)

    def _path(self, url):
        # domain independent key part: the unquoted path (and the "?p=<id>" of a season link), lower case
        url = urllib_unquote(self._canonUrl(url))
        path = re.sub(r"^https?://[^/]+", "", url)
        pid = re.search(r"[?&]p=(\d+)", path)
        if pid:
            return "/?p=%s" % pid.group(1)
        return path.split("?")[0].split("#")[0].rstrip("/").lower()

    def _segment(self, url):
        path = self._path(url).strip("/")
        return path.split("/")[0] if "/" in path else ""

    def _isSite(self, url):
        return bool(SITE_DOMAIN_RE.match(url or ""))

    def getFullIconUrl(self, url, currUrl=None):
        # covers on the site's own domain need the cf_clearance cookie + the User-Agent that passed the check once
        # MyE2i stored them; the meta is attached here because the host base runs every icon through
        # getFullIconUrl again. Covers on the site's CDN only get the site as Referer, foreign covers stay plain
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http") or "blank.gif" in url:
            return "" if "blank.gif" in url else url
        if CDN_DOMAIN_RE.match(url):
            return strwithmeta(url, {"Referer": self.MAIN_URL})
        if not self._isSite(url):
            return url
        url = SITE_DOMAIN_RE.sub(self.MAIN_URL.rstrip("/"), url)
        meta = {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    def _userAgent(self):
        return remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent")

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("fh_video", "fh_series", "fh_season"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category == "fh_season":
                return ("season:%s" % cItem["season_id"]) if cItem.get("season_id") else ""
            prefix = {"fh_video": "video", "fh_series": "series"}.get(category, "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return ("%s:%s" % (prefix, path)) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # rows
    ###################################################
    def _movieParams(self, label, url, icon, desc, normalize):
        name, year = _splitYear(label)
        dub = bool(DUB_RE.search(label))
        title = label
        if normalize and name:
            title = ("%s (%s)" % (name, year)) if year else name
            if dub:
                title = "%s %s" % (title, DUB_WORD)
        return {"name": "category", "good_for_fav": True, "category": "fh_video", "title": title, "url": url, "icon": icon, "desc": desc,
                "meta_type": "movie", "meta_title": name or label, "meta_year": year}

    def _episodeParams(self, label, url, icon, desc, normalize, show="", season=0, episode=""):
        episode = episode or _episodeNum(label)
        season = season or _seasonNum(label) or 1
        show = show or _showName(label) or _clean(label)
        title = label
        if normalize and episode:
            title = "%s - %s" % (show, formatSxxExx(season, episode))
        return {"name": "category", "good_for_fav": True, "category": "fh_video", "title": title, "url": url, "icon": icon, "desc": desc,
                "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv", "meta_title": show}

    def _seriesParams(self, label, url, icon, desc, normalize):
        show = _showName(label) or _clean(label)
        # folders keep the site's label (season, dubbed) - without the kind word ("مسلسل") when names are normalised
        title = SITE_SUFFIX_RE.sub("", label)
        if normalize:
            title = KIND_RE.sub("", title)
        return {"name": "category", "good_for_fav": True, "category": "fh_series", "title": title.strip() or label, "url": url,
                "icon": icon, "desc": desc, "s_title": show, "meta_type": "tv", "meta_title": show}

    def _cards(self, data):
        # (url, label, icon, desc) of the "postDiv" cards of a list / search page
        out = []
        seen = set()
        for block in data.split('class="postDiv')[1:]:
            href = self.cm.ph.getSearchGroups(block, r'<a[^>]+href="([^"]+)"')[0]
            url = self._canonUrl(href) if href else ""
            if not url or not self._isSite(url) or url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="h1">(.*?)</div>')[0])
            if not label:
                label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0])
            if not label:
                continue
            icon = self.cm.ph.getSearchGroups(block, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
            desc = []
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<span class="quality">(.*?)</span>')[0])
            if quality:
                desc.append(quality)
            cats = [self.cleanHtmlStr(c) for c in re.findall(r'(?s)<span class="cat">(.*?)</span>', block)]
            if cats:
                desc.append(", ".join(c for c in cats if c))
            views = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<span class="pViews">(.*?)</span>')[0])
            if views:
                desc.append("%s %s" % (_("Views:"), views))
            out.append((url, label, self.getFullIconUrl(icon.strip()) if icon else "", " | ".join(desc)))
        return out

    ###################################################
    # lists
    ###################################################
    def listMenu(self, cItem):
        # the sub-lists of one dropdown of the site's menu (labels as the site writes them)
        printDBG("FaselhdCOM.listMenu [%s]" % cItem.get("group", ""))
        key = dict(MENU_GROUPS).get(cItem.get("group", ""), "")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        menu = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "menu-primary"), ("</ul", ">"), False)[1]
        # one chunk per top-level entry; its dropdown links sit in a <div role="menu">, the toggle has data-toggle
        for group in menu.split("<li")[1:]:
            links = []
            for attrs, label in re.findall(r"(?s)<a([^>]*)>(.*?)</a>", group):
                href = self.cm.ph.getSearchGroups(attrs, r'href="([^"#]+)"')[0]
                if href and "data-toggle" not in attrs and "_blank" not in attrs:
                    links.append((self._canonUrl(href), self.cleanHtmlStr(label)))
            if not key or not any(self._path(url) == key for url, _label in links):
                continue
            seen = set()
            for url, label in links:
                # outside links (the reviews site) and the "coming soon" page (no list) are left out
                if not self._isSite(url) or "page_id=" in url or url in seen:
                    continue
                seen.add(url)
                label = SITE_SUFFIX_RE.sub("", label).strip()
                if label:
                    self.addDir({"name": "category", "good_for_fav": True, "category": "fh_list", "title": label, "url": url})
            break
        if not self.currList and key:
            # the menu could not be read: the group's main list
            self.addDir({"name": "category", "good_for_fav": True, "category": "fh_list", "title": _("All"), "url": self.MAIN_URL + key.strip("/")})

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = self._canonUrl(cItem.get("url", ""))
        printDBG("FaselhdCOM.listItems [%s] page[%s]" % (url, page))
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        for itemUrl, label, icon, desc in self._cards(data):
            seg = self._segment(itemUrl)
            if seg in MOVIE_SEGS:
                self.addVideo(self._movieParams(label, itemUrl, icon, desc, normalize))
            elif seg in EPISODE_SEGS:
                self.addVideo(self._episodeParams(label, itemUrl, icon, desc, normalize))
            elif seg in LIST_SEGS:
                self.addDir({"name": "category", "good_for_fav": True, "category": "fh_list", "title": _clean(label) or label, "url": itemUrl, "icon": icon, "desc": desc})
            else:
                self.addDir(self._seriesParams(label, itemUrl, icon, desc, normalize))
        if not self.currList:
            self.addMarker({"title": _("No items found"), "desc": ""})
            return
        # pager: <a class="page-link" href='.../page/3'>3</a> ... <a href='.../page/62'>&raquo;</a> (last page)
        pager = self.cm.ph.getDataBeetwenNodes(data, ("<", ">", "pagination"), ("</div", ">"), False)[1]
        hrefs = re.findall(r"href=['\"]([^'\"]*/page/\d+[^'\"]*)['\"]", pager)
        pages = [int(p) for p in re.findall(r"/page/(\d+)", " ".join(hrefs))]
        lastPage = max(pages + [page]) if pages else 0
        pageTpl = re.sub(r"/page/\d+", "/page/{page}", self._canonUrl(hrefs[0]).replace("&amp;", "&")) if hrefs else ""
        hasNext = page < lastPage
        listItem = dict(cItem)
        listItem.update({"category": "fh_list"})
        addPagingItems(self, listItem, page, hasNext, lastPage if (hasNext or page > 1) else 0, pageTpl)

    def _seriesPage(self, url):
        # (title, seasons [(post id, label, icon)], episodes [(url, number)], poster, story, page) of a series /
        # season / episode page
        sts, data = self.getPage(url)
        if not sts:
            return None
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="h1 title">(.*?)</(?:h1|div)>')[0].split('<span class="singleStar"')[0])
        seasons = []
        block = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", 'id="seasonList"'), ("<div", ">", "container"), False)[1] or data
        for item in block.split('class="seasonDiv')[1:]:
            pid = self.cm.ph.getSearchGroups(item, r"[?&]p=(\d+)")[0]
            if not pid:
                continue
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="title">(.*?)</div>')[0]) or pid
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            seasons.append((pid, label, self.getFullIconUrl(icon) if icon else ""))
        episodes = []
        seen = set()
        epBlock = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", 'id="epAll"'), ("</div", ">"), False)[1]
        for href, label in re.findall(r'(?s)<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', epBlock):
            epUrl = self._canonUrl(href)
            if epUrl in seen:
                continue
            seen.add(epUrl)
            episodes.append((epUrl, _episodeNum(self.cleanHtmlStr(label)) or str(len(episodes) + 1)))
        story, poster, _info = self._siteInfo(data)
        return title, seasons, episodes, poster, story, data

    def _addEpisodes(self, cItem, episodes, season):
        page = cItem.get("page", 1)
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or _showName(cItem.get("title", ""))
        rows = []
        for url, number in episodes:
            # raw label (naming off): "<show> - الحلقة <n>"
            label = "%s - %s %s" % (show, "الحلقة", number)
            params = self._episodeParams(label, url, cItem.get("icon", ""), cItem.get("desc", ""), normalize, show, season, number)
            params["meta_title"] = cItem.get("meta_title") or show
            rows.append(params)
        rows.sort(key=lambda p: int(p["s_episode"]) if p["s_episode"].isdigit() else 0)
        if not rows:
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in rows[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(rows) > LOCAL_PAGE_SIZE:
            lastPage = (len(rows) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSeries(self, cItem):
        url = self._canonUrl(cItem.get("url", ""))
        printDBG("FaselhdCOM.listSeries [%s]" % url)
        ret = self._seriesPage(url)
        if ret is None:
            return
        title, seasons, episodes, poster, story, data = ret
        show = cItem.get("s_title") or _showName(title) or _showName(cItem.get("title", ""))
        base = dict(cItem)
        base.update({"s_title": show, "meta_type": "tv", "meta_title": cItem.get("meta_title") or show,
                     "icon": cItem.get("icon") or poster, "desc": story or cItem.get("desc", "")})
        if len(seasons) > 1:
            for pid, label, icon in seasons:
                params = dict(base)
                params.update({"category": "fh_season", "title": label, "url": self.MAIN_URL + "?p=" + pid, "season_id": pid,
                               "s_season": _seasonNum(label) or 1, "icon": icon or base["icon"], "page": 1})
                self.addDir(params)
            return
        if episodes:
            season = _seasonNum(seasons[0][1]) if seasons else 0
            self._addEpisodes(base, episodes, season or _seasonNum(title) or _seasonNum(cItem.get("title", "")) or 1)
            return
        if self._serverLinks(data)[0]:
            # a page without seasons and episodes (a special, a single show): the page itself
            params = self._movieParams(cItem.get("title", "") or title, url, base["icon"], base["desc"], IsMediaNamingNormalized())
            params.update({"title": cItem.get("title", "") or title, "meta_type": "tv", "meta_title": show})
            self.addVideo(params)
            return
        SetIPTVPlayerLastHostError(_("No episodes found."))

    def listSeason(self, cItem):
        printDBG("FaselhdCOM.listSeason [%s]" % cItem.get("season_id", ""))
        ret = self._seriesPage(cItem.get("url", ""))
        if ret is None:
            return
        self._addEpisodes(cItem, ret[2], cItem.get("s_season") or 1)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FaselhdCOM.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "fh_list", "url": self.MAIN_URL + "?s=" + urllib_quote_plus(searchPattern.strip()), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # story, poster and the "singleList" fields of a film / series / episode page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="singleDesc">(.*?)</div>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'(?s)class="posterImg">.*?<img[^>]+src="([^"]+)"')[0]
        info = {}
        block = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", 'id="singleList"'), ("<div", ">", "singleBtns"), False)[1]
        for item in re.findall(r"(?s)<span>(.*?)</span>", block):
            text = self.cleanHtmlStr(item)
            if ":" not in text:
                continue
            label, value = text.split(":", 1)
            value = value.strip().replace(" ,", ",")
            for word, key in INFO_KEYS:
                if word in label and value and key not in info:
                    info[key] = value
                    break
        rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="singleStar">.*?<strong>([^<]+)</strong>')[0])
        if rating:
            info["imdb_rating"] = "%s/10" % rating
        return story, self.getFullIconUrl(poster) if poster else "", info

    def _serverLinks(self, data):
        # the watch servers (tabs) and the download servers urlparser knows of a page
        watch = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenNodes(self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "tabs-ul"), ("</ul", ">"))[1], ("<li", ">"), ("</li", ">")):
            url = self.cm.ph.getSearchGroups(item, r"""location\.href\s*=\s*['"]([^'"]+)['"]""")[0] or self.cm.ph.getSearchGroups(item, r'data-url="([^"]+)"')[0]
            url = url.replace("&amp;", "&")
            if not url or url in seen:
                continue
            seen.add(url)
            watch.append((self.cleanHtmlStr(item) or "%s %d" % (_("Server"), len(watch) + 1), url))
        if not watch:
            frame = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+name="player_iframe"[^>]+data-src="([^"]+)"')[0] or \
                self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]*video_player[^"]+)"')[0]
            if frame:
                watch.append(("%s 1" % _("Server"), frame.replace("&amp;", "&")))
        download = []
        block = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "downloadLinks"), ("</div", ">"), False)[1]
        for href, label in re.findall(r'(?s)<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', block):
            if 1 == self.up.checkHostSupport(href):
                download.append((self.cleanHtmlStr(label) or self.up.getHostName(href, True), href))
        return watch, download

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("FaselhdCOM.getLinksForVideo [%s]" % url)
        if url and not self._isSite(url) and 1 == self.up.checkHostSupport(url):
            # trailer rows of the old version (YouTube)
            return [{"name": self.up.getHostName(url, True), "url": url, "need_resolve": 1}]
        pageUrl = self._canonUrl(url)
        if not pageUrl:
            return []
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        watch, download = self._serverLinks(data)
        urltab = []
        for name, link in watch:
            urltab.append({"name": name, "url": strwithmeta(self._canonUrl(link), {"Referer": pageUrl}), "need_resolve": 1})
        for name, link in download:
            urltab.append({"name": name, "url": link, "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = self._siteInfo(data)[0]
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    def _runPlayerScripts(self, data):
        # the player page builds its HLS links in obfuscated scripts: run them with a stubbed DOM; each script in its
        # own function + try, so an ad script that fails does not stop the player's
        body = data[data.find("<body"):] if "<body" in data else data
        scripts = [s for s in re.findall(r"(?s)<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", body) if s.strip()]
        if not scripts:
            return ""
        code = PLAYER_JS_STUB + "\n".join("try { (function () {\n%s\n})(); } catch (e) {}" % s for s in scripts)
        try:
            # runs in the host's worker thread; the engine is killed after timeout_sec (busybox timeout / duk -t),
            # a missing engine gives no data (the page's plain m3u8 urls are the fallback)
            ret = js_execute(code, {"timeout_sec": 30})
        except Exception:
            printExc()
            return ""
        if not ret.get("sts") or ret.get("code") != 0:
            printDBG("FaselhdCOM: player scripts failed [%s]" % ret.get("code"))
        return ret.get("data", "") or ""

    def _playerLinks(self, data):
        # [(label, url)] from the player page: the quality buttons, the jwplayer setup source (auto), plain urls
        out = self._runPlayerScripts(data) + "\n" + data
        links = []
        for url, label in re.findall(r'data-url="(https?://[^"]+)"[^>]*>([^<]*)<', out):
            if url not in [u for _l, u in links]:
                links.append((self.cleanHtmlStr(label) or "auto", url))
        for line in out.split("\n"):
            if not line.startswith("SETUP:"):
                continue
            try:
                for src in (json_loads(line[6:]) or {}).get("sources", []):
                    url = src.get("file", "")
                    if url.startswith("http") and url not in [u for _l, u in links]:
                        links.append((src.get("label") or "auto", url))
            except Exception:
                printExc()
        if not links:
            for url in re.findall(r"""['"](https?://[^'"\s]+\.m3u8[^'"\s]*)['"]""", out):
                if url not in [u for _l, u in links]:
                    links.append(("auto", url))

        def _quality(item):
            num = re.search(r"(\d{3,4})", item[0])
            return int(num.group(1)) if num else 0
        links.sort(key=_quality, reverse=True)
        return links

    def getVideoLinks(self, videoUrl):
        printDBG("FaselhdCOM.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if not (self._isSite(videoUrl) and "video_player" in videoUrl):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=strwithmeta(videoUrl).meta.get("Referer", self.MAIN_URL))
        sts, data = self.getPage(self._canonUrl(videoUrl), params)
        if not sts:
            return []
        if len(data) < 200 and "expired" in data.lower():
            # the player token of the page is only valid for a while - the links have to be opened again
            SetIPTVPlayerLastHostError(_("The link has expired. Please open the video again."))
            return []
        meta = {"User-Agent": self._userAgent(), "Referer": self.MAIN_URL, "Origin": self.MAIN_URL.rstrip("/")}
        urltab = [{"name": label, "url": decorateUrl(url, dict(meta))} for label, url in self._playerLinks(data)]
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(urltab, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("FaselhdCOM.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or StripColorCodes(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", "")
        printDBG("FaselhdCOM.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "fh_menu":
            self.listMenu(self.currItem)
        elif category in ("fh_list", "list_items"):
            # "list_items": favourites of the old version
            self.listItems(self.currItem)
        elif category in ("fh_series", "explore_item"):
            self.listSeries(self.currItem)
        elif category == "fh_season":
            self.listSeason(self.currItem)
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
        CHostBase.__init__(self, FaselhdCOM(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("faselhdcom")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("fh_video", "fh_series", "fh_season", "explore_item")
