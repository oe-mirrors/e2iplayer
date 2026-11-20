# -*- coding: utf-8 -*-
LAST_MODIFIED = "20.11.2026"
# Coding: BY MOHAMED_OS
# 09.10.2026 - ported to the python3 framework / host standard as a host of its own for wecima.cx (hostwecima
#   stays on wecima.gripe, a different site of the WeCima family)
#   - WeCima on wecima.cx (own CMS v2.8, "Wecima-Card" grid, English slugs /watch/<slug>, /series/<slug>):
#     movies (latest, top rated, most popular, classic, per category), series (latest, newest episodes, top
#     rated, most popular, per category, Ramadan), anime & cartoons, TV shows, wrestling, trends; First page /
#     Jump / Next page (n/last) from the site's pager (/page/N)
#   - search: the site's live search (POST /search q=, JSON, at most ~20 results and no paging on the site;
#     "?s=" only returns the home page)
#   - /series/ pages are show folders: several seasons -> season folders (their episodes through POST
#     ajax/Episode like the page does), one season -> its episodes (local paging over 100); movies and episodes
#     are VIDEO rows keyed on their page url, season / episode numbers from the "-sNN-eNN" slug
#   - links: watch servers and downloads are hoster embeds (data-url / data-href = base64 without its "aHR0c"
#     head, "+" fillers inside) -> urlparser; the YouTube trailer when the page has one
#   - a Cloudflare managed challenge guards every request (curl-impersonate too, 09.10.2026): getPageCFProtection
#     (MyE2i solve on the box); covers get the same cf_clearance cookie + the User-Agent that passed the check
#   - alternative domain + proxy options, favourites re-based on the current domain
#   - watched flag (show -> season -> episode), downloaded flag (page url), favourites, sidecar, INFO via
#     moviemeta + the site's story / fields, name normalisation ("Title (Year)", "Show - SxxExx"; raw site
#     labels when off), no colour codes in titles
# 20.11.2026 - wecima.tips; server / download links AES-GCM encrypted (key from mains.js, read again when it changes)
import base64
import hashlib
import os
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized, GetLocalPageSize
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import strDecode
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.wecimacx_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.wecimacx_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.wecimacx_proxy))
    if config.plugins.iptvplayer.wecimacx_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.wecimacx_alt_domain))
    return optionList
###################################################


def gettytul():
    return "WeCima (wecima.cx)"


DEFAULT_DOMAIN = "https://wecima.tips/"
LOCAL_PAGE_SIZE = 100
# Arabic ordinals used in season labels ("الموسم الثاني"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6), ("السادس", 6),
    ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:^|\s)(?:ال)?موسم\s*(\d+|%s)(?=\s|$)" % "|".join(o[0] for o in SEASON_ORDINALS))
# "حلقة 6 مترجمة" / "الحلقة 29 <guest>" - everything from the episode word on is the episode label
EPISODE_RE = re.compile(r"(?:^|\s)(?:ال)?(?:حلقة|حلقه)\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s)\(?((?:19|20)\d\d)\)?((?:\s+(?:مدبلج|مدبلجة))*)\s*$")
SUBDUB_RE = re.compile(r"مترجم(?:ة)?\s+و\s*(مدبلج(?:ة)?)")
# site words that do not belong into a title / file name (only removed when normalising)
JUNK_RE = re.compile(r"(?:^|\s)(?:مشاهدة|فيلم|مسلسل|انمي|أنمي|كرتون|برنامج|عرض|مترجم|مترجمة|اون لاين|أون لاين|اونلاين|"
                     r"بجودة|كامل|كاملة|والاخيرة|والأخيرة|HD)(?=\s|$)")
# season / episode of an episode page slug: /watch/red-queen-s02-e06
SLUG_EPISODE_RE = re.compile(r"-s(\d+)-e(\d+)$")
SLUG_YEAR_RE = re.compile(r"-((?:19|20)\d\d)-(?:dubbed-)?(?:movie|series)$")
# "<li><span>السنة</span><p>2024</p></li>" fields of a title page -> INFO keys
INFO_FIELDS = (("original_title", "الاسم"), ("category", "التصنيف"), ("country", "البلد"), ("genres", "النوع"),
               ("year", "السنة"), ("duration", "المدة"), ("rating", "التقييم"))
VIDEO_CATEGORIES = ("wx_video",)
FOLDER_CATEGORIES = ("wx_show", "wx_season")


# since 11.2026 data-url / data-href = base64(iv[12] + AES-256-GCM(link) + tag[16]) with the key sha256(LINK_KEY of
# /static/js/mains.js); this is the LINK_KEY of mains.js v12.4 - a newer mains.js is read when it no longer opens the links
LINK_KEY = "9ajT3vqphrtyQ3ZfdeBSepU7iUNSC4Z7SXjS9Dg9"


def _validLink(link):
    if link.startswith("//"):
        link = "https:" + link
    return link if re.match(r"https?://[^/\s]+", link) else ""


def _b64(value):
    value = value.strip()
    return base64.b64decode(value + "=" * (-len(value) % 4))


def _oldLink(value):
    # until 11.2026: the page ran atob("aHR0c" + value without "+")
    try:
        return _validLink(strDecode(_b64("aHR0c" + value.replace("+", "")), "ignore"))
    except Exception:
        return ""


def _aesGcmOpen(key, iv, data):
    # AES-GCM (ciphertext + tag) -> text; the image's "cryptography" (C) first, the pure Python libs/aesgcm otherwise
    # (that one does not check the tag: a wrong key gives garbage, the caller checks the text)
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return strDecode(AESGCM(key).decrypt(iv, data, None), "ignore")
    except ImportError:
        pass
    except Exception as e:
        printDBG("WeCimaCx._aesGcmOpen: %s" % type(e).__name__)
        return ""
    from Plugins.Extensions.IPTVPlayer.libs.aesgcm import python_aesgcm
    # py2: its rijndael / CTR take str only, py3 bytearray
    conv = str if str is bytes else bytearray
    plain = python_aesgcm.new(conv(key)).open(conv(iv), conv(data))
    return strDecode(bytes(plain), "ignore") if plain is not None else ""


def _decodeLink(value, linkKey):
    # data-url / data-href of a server or download -> hoster url, "" when it does not open
    value = (value or "").strip()
    if not value:
        return ""
    try:
        raw = _b64(value)
    except Exception:
        return ""
    if len(raw) > 28:
        link = _validLink(_aesGcmOpen(hashlib.sha256(linkKey.encode("utf-8")).digest(), raw[:12], raw[12:]))
        if link:
            return link
    return _oldLink(value)


def _jsString(value):
    # one string of the obfuscator table: base64 with swapped letter case, then UTF-8
    try:
        return strDecode(_b64(value.swapcase()), "ignore")
    except Exception:
        return ""


def _calc(tokens, pick):
    # + - * / ( ) and P(n) of the obfuscator's checksum line (pick(n) = parseInt of table string n)
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else ""

    def take():
        pos[0] += 1
        return tokens[pos[0] - 1]

    def factor():
        tok = take()
        if tok in ("-", "+"):
            val = factor()
            return -val if tok == "-" else val
        if tok == "(":
            val = expr()
            take()
            return val
        if tok.startswith("P"):
            return pick(int(tok[1:], 16))
        return float(int(tok, 0))

    def term():
        val = factor()
        while peek() in ("*", "/"):
            if take() == "*":
                val *= factor()
            else:
                val /= factor()
        return val

    def expr():
        val = term()
        while peek() in ("+", "-"):
            val = val + term() if take() == "+" else val - term()
        return val
    return expr()


def _jsLinkKey(src):
    # LINK_KEY of mains.js without running it: the string table, its rotation (the checksum loop of the
    # obfuscator), then the table strings LINK_KEY is joined from
    table = re.search(r"function _0x[0-9a-f]+\(\)\{var _0x[0-9a-f]+=\[('.*?')\];", src, re.S)
    offset = re.search(r"function _0x[0-9a-f]+\(_0x[0-9a-f]+,_0x[0-9a-f]+\)\{_0x[0-9a-f]+=_0x[0-9a-f]+-(0x[0-9a-f]+);", src)
    check = re.search(r"var _0x[0-9a-f]+=(parseInt\(.*?);if\(_0x[0-9a-f]+===_0x[0-9a-f]+\)break;.*?\}\(_0x[0-9a-f]+,(0x[0-9a-f]+)\)", src, re.S)
    parts = re.search(r"var LINK_KEY=([^;]+);", src)
    if not (table and offset and check and parts):
        return ""
    arr = re.findall(r"'([^']*)'", table.group(1))
    offset = int(offset.group(1), 16)
    expr = re.sub(r"parseInt\(_0x[0-9a-f]+\((0x[0-9a-f]+)\)\)", r"P\1", check.group(1))
    tokens = re.findall(r"P0x[0-9a-f]+|0x[0-9a-f]+|\d+|[-+*/()]", expr)
    if "".join(tokens) != expr.replace(" ", ""):
        return ""
    target = int(check.group(2), 16)

    def pick(idx):
        m = re.match(r"\s*([+-]?\d+)", _jsString(arr[idx - offset]))
        if not m:
            raise ValueError("NaN")
        return float(m.group(1))
    for _turn in range(len(arr)):
        try:
            if _calc(tokens, pick) == target:
                return "".join(_jsString(arr[int(h, 16) - offset]) for h in re.findall(r"\((0x[0-9a-f]+)\)", parts.group(1)))
        except (ValueError, IndexError, ZeroDivisionError):
            pass
        arr.append(arr.pop(0))
    return ""


class WeCimaCx(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    LINK_KEY_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "kind", "post_id", "season_key",
                  "s_title", "s_season", "s_episode", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "wecimacx", "cookie": "wecimacx.cookie"})
        self.MAIN_URL = None
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("wecimacx")
        self.wfInitFolderCache()
        self.MENU = [
            {"category": "wx_section", "title": _("Movies"), "section": "movies"},
            {"category": "wx_section", "title": _("Series"), "section": "series"},
            {"category": "wx_list", "title": _("Anime"), "path": "anime"},
            {"category": "wx_list", "title": _("TV Shows"), "path": "category/tv-shows"},
            {"category": "wx_list", "title": _("Wrestling"), "path": "category/wwe-shows"},
            {"category": "wx_list", "title": _("Trending"), "path": "trends"},
        ]
        self.SECTIONS = {
            "movies": [
                ("%s - %s" % (_("Movies"), _("Latest")), "movies"),
                (_("Top rated"), "movies/best"),
                (_("Most popular"), "movies/top"),
                (_("Classic movies"), "movies/old"),
                (_("Foreign movies"), "category/foreign-movies"),
                (_("Arabic movies"), "category/arabic-movies"),
                (_("Indian movies"), "category/indian-movies"),
                (_("Asian movies"), "category/asian-movies"),
                (_("Turkish Movies"), "category/turkish-movies"),
                (_("Dubbed movies"), "category/dubbed-movies"),
                (_("Anime movies"), "category/anime-movies"),
            ],
            "series": [
                ("%s - %s" % (_("Series"), _("Latest")), "seriestv"),
                (_("Newest Episodes"), "seriestv/episodes"),
                (_("Top rated"), "seriestv/best"),
                (_("Most popular"), "seriestv/top"),
                (_("Arabic Series"), "category/arabic-series"),
                (_("Foreign series"), "category/foreign-series"),
                (_("Turkish TV series"), "category/turkish-series"),
                (_("Indian TV series"), "category/indian-series"),
                (_("Asian TV series"), "category/asian-series"),
                (_("Korean TV series"), "category/korean-series"),
                (_("Anime TV series"), "category/anime-series"),
            ] + [("%s %d" % (_("Ramadan"), year), "category/ramadan-series-%d" % year) for year in range(2026, 2020, -1)],
        }

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.wecimacx_proxy.value) or None

    def _params(self, addParams=None):
        params = dict(self.defaultParams if addParams is None else addParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in params:
            params["http_proxy"] = proxy
        return params

    def getPage(self, baseUrl, addParams=None, post_data=None):
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), self._params(addParams), post_data)

    def selectDomain(self):
        if WeCimaCx.DOMAIN_CACHE:
            self.MAIN_URL = WeCimaCx.DOMAIN_CACHE
            return
        domains = [DEFAULT_DOMAIN]
        domain = config.plugins.iptvplayer.wecimacx_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        self.MAIN_URL = domains[-1]
        for domain in domains:
            sts, data = self.cm.getPageCFProtection(domain, self._params())
            if sts and "Wecima-Card" in data:
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", "") or domain)
                # only a domain that answered: after a failed check the next start probes again
                WeCimaCx.DOMAIN_CACHE = self.MAIN_URL
                break

    def _canonUrl(self, url):
        # site urls of favourites / old lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        m = re.match(r"https?://[^/]+/(.*)$", url)
        return (self.MAIN_URL + m.group(1)) if m else self.getFullUrl(url)

    def _cfMeta(self):
        # cf_clearance + the User-Agent that passed the check, for downloads outside getPage (covers)
        meta = {"Referer": self.getMainUrl()}
        proxy = self.getProxy()
        if proxy:
            meta["iptv_http_proxy"] = proxy
        try:
            # getCookieHeader logs a traceback for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return meta

    def getFullIconUrl(self, url, currUrl=None):
        # the covers (<domain>/upload/...) sit behind the same Cloudflare check as the pages
        url = (url or "").strip()
        if not url or ("://" in url and not url.startswith("http")):
            return url  # the local logo (file://)
        url = self._canonUrl(url)
        return strwithmeta(url, self._cfMeta())

    @staticmethod
    def _path(url):
        # domain-independent part of a page url (watched keys survive domain changes)
        path = re.sub(r"^https?://[^/]+", "", url or "").split("?")[0].split("#")[0]
        return "/" + path.strip("/").lower()

    @staticmethod
    def _clean(text):
        text = re.sub(r"(مسلسل|فيلم|انمي)(?=[A-Za-z0-9])", r"\1 ", text or "")  # "مسلسلBatman ..."
        text = re.sub(r"([A-Za-z])((?:19|20)\d\d)(?=\s|$)", r"\1 \2", text)  # "Elite Force2026"
        text = JUNK_RE.sub(" ", SUBDUB_RE.sub(r"\1", text))
        return re.sub(r"\s+", " ", text).strip(" -:|")

    @staticmethod
    def _metaTitle(title):
        return re.sub(r"\s+", " ", re.sub(r"(?:^|\s)(?:مدبلج|مدبلجة)(?=\s|$)", " ", title or "")).strip()

    @staticmethod
    def _seasonNum(val):
        return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)

    def _parseTitle(self, title):
        # -> (name, year, season, episode) of a site label
        name = self._clean(title)
        season, episode, year = 0, 0, ""
        m = EPISODE_RE.search(name)
        if m:
            episode = int(m.group(1))
            name = name[:m.start()].strip()
        m = SEASON_RE.search(name)
        if m:
            season = self._seasonNum(m.group(1))
            name = (name[:m.start()] + " " + name[m.end():]).strip()
        name = re.sub(r"\s+", " ", name).strip(" -:|")
        m = YEAR_RE.search(name)
        if m and m.start() > 0:
            year = m.group(1)
            name = (name[:m.start()] + " " + m.group(2).strip()).strip(" -:|")
        return name, year, season, episode

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or not cItem.get("url"):
                return ""
            category = cItem.get("category", "")
            path = self._path(cItem["url"])
            if category in VIDEO_CATEGORIES:
                return "video:%s" % path
            if category == "wx_show":
                return "folder:%s" % path
            if category == "wx_season" and cItem.get("season_key"):
                return "folder:%s#%s" % (path, cItem["season_key"])
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES:
            return self.getFavouriteFieldsData(cItem)
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        for item in self.MENU:
            params = dict(item, name="category")
            if "path" in params:
                params.update({"good_for_fav": True, "url": self._canonUrl(params.pop("path"))})
            self.addDir(params)
        self.listsTab(self.searchItems(), {"name": "category"})

    def listSection(self, cItem):
        for title, path in self.SECTIONS.get(cItem.get("section", ""), []):
            self.addDir({"name": "category", "category": "wx_list", "good_for_fav": True, "title": title, "url": self._canonUrl(path)})

    def _addEntry(self, url, raw, icon, desc="", siteYear=""):
        # one card / search result -> show folder (/series/), episode or movie VIDEO row (/watch/)
        url = self._canonUrl(url)
        path = self._path(url)
        if not raw or not path.startswith(("/series/", "/watch/")):
            return False
        name, year, _season, _episode = self._parseTitle(raw)
        name = name or raw
        year = year or siteYear or self.cm.ph.getSearchGroups(path, SLUG_YEAR_RE.pattern)[0]
        normalize = IsMediaNamingNormalized()
        withYear = "%s (%s)" % (name, year) if year else name
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon), "desc": desc or raw}
        episode = SLUG_EPISODE_RE.search(path)
        if path.startswith("/series/"):
            params.update({"category": "wx_show", "kind": "show", "title": withYear if normalize else raw,
                           "s_title": name, "meta_type": "tv", "meta_title": self._metaTitle(name), "meta_year": year})
            self.addDir(params)
        elif episode:
            season, epNum = int(episode.group(1)), int(episode.group(2))
            title = "%s - %s" % (name, formatSxxExx(season, epNum))
            params.update({"category": "wx_video", "kind": "episode", "title": title if normalize else raw,
                           "s_title": name, "s_season": season, "s_episode": epNum, "meta_type": "tv", "meta_title": self._metaTitle(name)})
            self.addVideo(params)
        elif path.endswith("-movie"):
            params.update({"category": "wx_video", "kind": "movie", "title": withYear if normalize else raw,
                           "meta_type": "movie", "meta_title": self._metaTitle(name), "meta_year": year})
            self.addVideo(params)
        else:
            # single shows (wrestling events): no film / series lookup, the site's info only
            params.update({"category": "wx_video", "kind": "video", "title": name if normalize else raw, "meta_year": year})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        printDBG("WeCimaCx.listItems [%s]" % cItem.get("url", ""))
        page = int(cItem.get("page", 1) or 1)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        grid = data[data.find("Grid--WecimaPosts"):] if "Grid--WecimaPosts" in data else ""
        pager = self.cm.ph.getDataBeetwenMarkers(grid, '<div class="pagination">', "</ul>", False)[1]
        count = 0
        for card in grid.split('<div class="pagination">')[0].split('<div class="Wecima-Card"')[1:]:
            url = self.cm.ph.getSearchGroups(card, r'Wecima-Card__link"\s+href="([^"]+)"')[0]
            raw = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'Wecima-Card__link"[^>]+title="([^"]+)"')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)Wecima-Card__title"[^>]*>(.*?)</')[0])
            icon = self.cm.ph.getSearchGroups(card, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(card, r"--image:url\(([^)]+)\)")[0]
            extras = [self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)Wecima-Card__%s">(.*?)</span>' % key)[0]) for key in ("rating", "quality", "genre")]
            if extras[0]:
                extras[0] = "IMDb %s" % extras[0]
            desc = " | ".join(x for x in extras if x)
            if self._addEntry(url, raw, icon.strip("'\" "), "%s[/br]%s" % (desc, raw) if desc else raw):
                count += 1
        lastPage = max([int(n) for n in re.findall(r"/page/(\d+)", pager)] + [page])
        tpl = self.cm.ph.getSearchGroups(pager, r'href="([^"]*/page/)\d+"')[0]
        addPagingItems(self, dict(cItem, category="wx_list"), page, bool(count) and page < lastPage, lastPage,
                       (self._canonUrl(tpl) + "{page}") if tpl else "")

    def _seasonFolders(self, data):
        # [(number, data-id, data-season, label)] of the show page's season switch
        seasons = []
        block = self.cm.ph.getDataBeetwenMarkers(data, "List--Seasons--Episodes", "</div>", False)[1]
        for attrs, label in re.findall(r"(?s)<a([^>]*SeasonsEpisodes[^>]*)>(.*?)</a>", block):
            postId = self.cm.ph.getSearchGroups(attrs, r'data-id="(\d+)"')[0]
            key = self.cm.ph.getSearchGroups(attrs, r'data-season="([^"]+)"')[0]
            label = self.cleanHtmlStr(label)
            num = int(self.cm.ph.getSearchGroups(key, r"(\d+)")[0] or 0) or self._parseTitle(label)[2]
            if postId and key:
                seasons.append((num, postId, key, label))
        seasons.sort(key=lambda s: s[0])
        return seasons

    def listShow(self, cItem):
        printDBG("WeCimaCx.listShow [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        show = cItem.get("s_title") or self._parseTitle(cItem.get("title", ""))[0]
        seasons = self._seasonFolders(data)
        if len(seasons) > 1:
            normalize = IsMediaNamingNormalized()
            for num, postId, key, label in seasons:
                title = ("%s %s" % (show, label)).strip()
                if normalize and num:
                    title = "%s - %s %d" % (show, _("Season"), num)
                self.addDir({"name": "category", "category": "wx_season", "kind": "season", "good_for_fav": True, "url": cItem["url"],
                             "icon": cItem.get("icon", ""), "title": title, "desc": cItem.get("desc", ""), "post_id": postId, "season_key": key, "s_title": show, "s_season": num or 1,
                             "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
            return
        block = data[data.find("Seasons--Episodes"):] if "Seasons--Episodes" in data else ""
        self._listEpisodes(dict(cItem, s_title=show), block.split("</singlesection>")[0], seasons[0][0] if seasons else 1)

    def listSeason(self, cItem):
        printDBG("WeCimaCx.listSeason [%s %s]" % (cItem.get("url", ""), cItem.get("season_key", "")))
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self._canonUrl(cItem["url"]))
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        sts, data = self.getPage("ajax/Episode", params, {"season": cItem.get("season_key", ""), "post_id": cItem.get("post_id", "")})
        if not sts:
            return
        self._listEpisodes(cItem, data, cItem.get("s_season", 1))

    def _listEpisodes(self, cItem, block, season):
        pageSize = GetLocalPageSize(LOCAL_PAGE_SIZE)
        show = cItem.get("s_title", "")
        normalize = IsMediaNamingNormalized()
        episodes, seen = [], set()
        for href, inner in re.findall(r'(?s)<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block):
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(inner, "<episodetitle>", "</episodetitle>", False)[1])
            url = self._canonUrl(href)
            if not label or url in seen:
                continue
            seen.add(url)
            m = SLUG_EPISODE_RE.search(self._path(url))
            sNum = int(m.group(1)) if m else (season or 1)
            epNum = int(m.group(2)) if m else int(self.cm.ph.getSearchGroups(label, r"(\d+)")[0] or 0)
            title = "%s - %s" % (show, label) if show else label
            if normalize and show and epNum:
                title = "%s - %s" % (show, formatSxxExx(sNum, epNum))
            episodes.append((sNum, epNum, {"name": "category", "category": "wx_video", "kind": "episode", "good_for_fav": True, "url": url,
                                           "icon": cItem.get("icon", ""), "desc": cItem.get("desc", ""), "title": title, "s_title": show, "s_season": sNum, "s_episode": epNum,
                                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")}))
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        episodes.sort(key=lambda e: (e[0], e[1]))
        page = int(cItem.get("page", 1) or 1)
        start = (page - 1) * pageSize
        for _sNum, _epNum, params in episodes[start:start + pageSize]:
            self.addVideo(params)
        if len(episodes) > pageSize:
            lastPage = (len(episodes) + pageSize - 1) // pageSize
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = searchPattern.strip()
        printDBG("WeCimaCx.listSearchResult [%s]" % pattern)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self.getMainUrl())
        params["header"]["X-Requested-With"] = "XMLHttpRequest"
        sts, data = self.getPage("search", params, {"q": pattern})
        if not sts:
            return
        try:
            results = json_loads(data).get("results") or []
        except Exception:
            printExc()
            return
        entries = []
        for idx, item in enumerate(results):
            slug = str(item.get("slug") or "").strip("/")
            if not slug:
                continue
            # istv: 0 film, 1 series, 2 episode; films and shows first in the site's order, then the episodes
            # (the site returns them unsorted) by show, season and episode
            url = self.getFullUrl(("series/%s" if str(item.get("istv")) == "1" else "watch/%s") % slug)
            episode = SLUG_EPISODE_RE.search(slug)
            order = (1, slug[:episode.start()], int(episode.group(1)), int(episode.group(2))) if episode else (0, "", 0, idx)
            entries.append((order, url, item))
        entries.sort(key=lambda e: e[0])
        for _order, url, item in entries:
            extras = ["IMDb %s" % item["rating"] if item.get("rating") else "", item.get("quality", ""), item.get("genre", "")]
            desc = " | ".join(x for x in extras if x)
            raw = self.cleanHtmlStr(item.get("title", ""))
            self._addEntry(url, raw, item.get("image", ""), "%s[/br]%s" % (desc, raw) if desc else raw, str(item.get("year") or ""))

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="StoryMovieContent">', "</div>", False)[1])
        info = {}
        terms = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="Terms--Content--Single-begin">', "</ul>", False)[1]
        for li in re.findall(r"(?s)<li[^>]*>(.*?)</li>", terms):
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(li, "<span>", "</span>", False)[1])
            values = [self.cleanHtmlStr(v) for v in re.findall(r"(?s)<a[^>]*>(.*?)</a>", li)] or \
                [self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(li, "<p", "</p>", True)[1])]
            values = [v for v in values if v]
            for key, word in INFO_FIELDS:
                if label == word and values:
                    info[key] = ", ".join(values)
        return story, info

    def _linkKey(self, data, values):
        # the built-in / last read LINK_KEY while it opens the links, else the one of the page's current mains.js
        key = WeCimaCx.LINK_KEY_CACHE or LINK_KEY
        if not values or _decodeLink(values[0], key):
            return key
        src = self.cm.ph.getSearchGroups(data, r'<script[^>]+src="([^"]*/js/mains\.js[^"]*)"')[0]
        if not src:
            return key
        sts, js = self.getPage(self.getFullUrl(src))
        newKey = _jsLinkKey(js) if sts else ""
        printDBG("WeCimaCx._linkKey mains.js [%s] -> %s" % (src, "found" if newKey else "not found"))
        if newKey and _decodeLink(values[0], newKey):
            WeCimaCx.LINK_KEY_CACHE = newKey
            return newKey
        return key

    def getLinksForVideo(self, cItem):
        printDBG("WeCimaCx.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        urltab = []

        def add(name, url):
            if not self.cm.isValidUrl(url) or url in [u["url"] for u in urltab]:
                return
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.getMainUrl()}), "need_resolve": 1})

        servers = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="WatchServersList">', "</ul>", False)[1]
        downloads = self.cm.ph.getDataBeetwenMarkers(data, "List--Download--Wecima--Single", "</ul>", False)[1]
        servers = [(self.cm.ph.getSearchGroups(attrs + inner, r'data-url="([^"]+)"')[0], inner) for attrs, inner in re.findall(r"(?s)<li([^>]*)>(.*?)</li>", servers)]
        downloads = [(self.cm.ph.getSearchGroups(attrs + inner, r'data-href="([^"]+)"')[0], inner) for attrs, inner in re.findall(r"(?s)<li([^>]*)>(.*?)</li>", downloads)]
        linkKey = self._linkKey(data, [v for v, _i in servers + downloads if v])
        for value, inner in servers:
            link = _decodeLink(value, linkKey)
            domain = self.up.getDomain(link, onlyDomain=True) if link else ""
            label = self.cleanHtmlStr(inner)
            add("%s (%s)" % (label, domain) if label else domain, link)
        for value, inner in downloads:
            link = _decodeLink(value, linkKey)
            if not link or 1 != self.up.checkHostSupport(link):
                continue
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'(?s)class="resolution">(.*?)</span>')[0])
            add("%s %s (%s)" % (_("Download"), quality, self.up.getDomain(link, onlyDomain=True)), link)
        trailer = self.cm.ph.getSearchGroups(data, r"""LinkTriler\s*=\s*['"]([^'"]+)['"]""")[0].replace("&amp;", "&")
        if self.cm.isValidUrl(trailer):
            add(_("Trailer"), trailer)
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
        story, info = self._siteInfo(data)
        # the moviemeta query of INFO: the page's year, +-1 year
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", ""), self._infoMetaTitle(cItem, info), cItem.get("meta_year") or info.get("year", ""), maxYearDiff=1)
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story, metaQuery))

    ###################################################
    # INFO
    ###################################################
    @staticmethod
    def _infoMetaTitle(cItem, info):
        # the moviemeta title of INFO and the download sidecar: the site's original name of an Arabic-titled film / series
        metaTitle = cItem.get("meta_title", "")
        original = info.get("original_title", "")
        if original and isLatinTitle(original) and not isLatinTitle(metaTitle):
            metaTitle = original
        return metaTitle

    def getArticleContent(self, cItem):
        printDBG("WeCimaCx.getArticleContent [%s]" % cItem.get("url", ""))
        story, info = "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, info = self._siteInfo(data)
            # episode pages have no story: their full site title instead
            story = story or self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, "<h1", "</h1>", True)[1])
        meta = {}
        metaTitle = self._infoMetaTitle(cItem, info)
        if cItem.get("meta_type") and metaTitle:
            try:
                skip = () if isLatinTitle(metaTitle) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], metaTitle, cItem.get("meta_year") or info.get("year", ""), skip, maxYearDiff=1)
            except Exception:
                printExc()
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        # the site knows its own title: its category / country / running time stay
        info.update({key: value for key, value in siteInfo.items() if key in ("category", "country", "duration")})
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("WeCimaCx.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "wx_section":
            self.listSection(self.currItem)
        elif category == "wx_list":
            self.listItems(self.currItem)
        elif category == "wx_show":
            self.listShow(self.currItem)
        elif category == "wx_season":
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
        CHostBase.__init__(self, WeCimaCx(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("wecimacx")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
