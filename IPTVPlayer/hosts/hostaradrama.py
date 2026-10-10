# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# Aradrama Host (Created By Dr HYTHAM MAHMOUD)
# 10.10.2026 - host standard on the site's markup (WordPress "T20" theme; lists: <article> with a.first_A, details
#   year / status / type, wp-pagenavi; item page: info block "b_block s-desc", trailer tabs, the "watch" button
#   (?cat=15&s=<post id>) lists the episode / film posts, whose servers are <li data-url> in "Servrs")
#   - menus: new episodes, series / movie categories (the site's names), shows, search - with First page / Jump /
#     Next page (the site's "/page/N/", last page from its pager); English menu labels
#   - series / films stay folders (trailer row + the posts of the watch list, sorted by episode, paging when the site
#     pages that list); episodes and film posts are VIDEO rows keyed on their page url (watched flag series ->
#     episode, downloaded flag, favourites incl. the old folders / rows), name normalisation ("Title (Year)",
#     "Show - SxxExx"), sidecar; servers resolved through urlparser only when chosen
#   - INFO via moviemeta (the English name of the site's info block) + the site's fields (names, genre, country,
#     episodes, network, air date, length, director, cast) and story; the bidi / line-wrap rework of the text and
#     the colour codes are gone
#   - getPageCFProtection (the old code called it under a misspelled name check); the site blocks some countries
#     (Cloudflare 403 "Attention Required" for German IPs): with the host's proxy option set the pages, covers and
#     the domain probe go through it, without it the host says the site is blocked in this country; the domain
#     probe stops at the first blocked domain (all four sit behind the same Cloudflare)
# 10.10.2026 - review: English titles with the site's typographic apostrophe ("Jinny’s Kitchen") reach moviemeta whole
import os
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.botprotection import KIND_BLOCK, detect as detectProtection, remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

# -------------------- config --------------------
config.plugins.iptvplayer.aradramtv_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.aradramtv_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    tab = []
    tab.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.aradramtv_proxy))
    if config.plugins.iptvplayer.aradramtv_proxy.value == "None":
        tab.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.aradramtv_alt_domain))
    return tab


def gettytul():
    return "ARADrama"


DOMAINS = ["https://aradramatv.cc/", "https://aradramatv.co/", "https://aradramtv.com/", "https://aradramatv.com/"]
SITE_URL_RE = re.compile(r"^https?://(?:www\.)?(?:aradramatv\.(?:cc|co|com)|aradramtv\.com)(?=/|$)", re.I)
LOCAL_PAGE_SIZE = 100
EPISODE_RE = re.compile(r"^(.*?)\s*(?:الحلقة|حلقة)\s*(\d+)")
SEASON_RE = re.compile(r"(?:الموسم|الجزء)\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d{2})(?=\s|\)|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:فيلم|مسلسل|مترجم|مترجمة|مدبلج|مدبلجة|والاخيرة|والأخيرة|الاخيرة|الأخيرة|اون لاين|أون لاين|مشاهدة|كامل|كاملة|HD)(?=\s|$)")
LATIN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 :;,.!?'&()\-]*[A-Za-z0-9)!?]|[A-Za-z]")
# the info block "<span>label : </span> value<br />" -> RICH_DESC key
INFO_FIELDS = (
    (("اسم المسلسل", "اسم الفيلم", "اسم البرنامج", "الاسم"), "original_title"),
    (("الاسم العربي",), "alternate_title"),
    (("النوع",), "genres"),
    (("البلد المنتج", "المنتج"), "country"),
    (("عدد الحلقات", "الحلقات"), "episodes"),
    (("شبكة العرض",), "station"),
    (("موعد البث", "موعد العرض", "موعد", "أيام العرض"), "broadcast"),
    (("طول الفيلم", "مدة الحلقة"), "duration"),
    (("المخرج",), "director"),
)


def _clean(text):
    text = JUNK_RE.sub(" ", JUNK_RE.sub(" ", text or ""))
    # the en dash as a whole sequence (py2 str.strip would take its single utf-8 bytes)
    return re.sub(r"\s+", " ", text.replace("–", " ")).strip(" -:|")


def _latinTitle(title):
    # "الربيع الأزرق Azure Spring" -> "Azure Spring" (the metadata services know the original title);
    # the site's typographic apostrophe as a plain one ("Jinny’s Kitchen" lost its "Jinny" otherwise)
    parts = [p.strip() for p in LATIN_RE.findall((title or "").replace("’", "'")) if re.search(r"[A-Za-z]", p)]
    return max(parts, key=len) if parts else ""


def _noColors(text):
    # rows saved by the previous version carry \cAARRGGBB colour codes ("[Trailer]")
    return re.sub(r"\\c[0-9A-Fa-f]{8}", "", text or "").strip()


class ARADrama(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "aradramtv", "cookie": "aradramtv.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/aradrama135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept-Language": "ar,en-US;q=0.9,en;q=0.8"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("aradrama")
        self.wfInitFolderCache()
        self.blocked = False

    # -------------------- net --------------------
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.aradramtv_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        sts, data = self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)
        self.blocked = not sts and not proxy and self._isBlocked(data)
        if self.blocked:
            # Cloudflare's country block ("Sorry, you have been blocked") - only a proxy gets through
            SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking)."))
        return sts, data

    @staticmethod
    def _isBlocked(data):
        # a hard block (nothing a browser check could solve), as pCommon's getPageCFProtection detects it
        try:
            meta = getattr(data, "meta", None) or {}
            found = detectProtection(meta.get("status_code", 0), meta, meta.get("body_head") or (data or ""), meta.get("url", ""))
            return bool(found) and found.kind == KIND_BLOCK
        except Exception:
            printExc()
        return False

    def selectDomain(self):
        if ARADrama.DOMAIN_CACHE:
            self.MAIN_URL = ARADrama.DOMAIN_CACHE
            return
        domains = list(DOMAINS)
        alt = config.plugins.iptvplayer.aradramtv_alt_domain.value.strip()
        if self.cm.isValidUrl(alt):
            domains.insert(0, alt.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.getPage(domain)
            if sts and ("T20_container" in data or "aradrama" in data.lower()):
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", domain))
                ARADrama.DOMAIN_CACHE = self.MAIN_URL
                return
            if not sts and (self._isBlocked(data) or (getattr(data, "meta", None) or {}).get("status_code") == 403):
                # blocked by Cloudflare (country block or a check MyE2i did not pass) - the other domains sit behind
                # the same Cloudflare
                break
        self.MAIN_URL = domains[0]

    def _rebase(self, url):
        # urls of favourites / older lists on another domain -> the current one, one percent-encoded form
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if url.startswith("//"):
            url = "https:" + url
        elif not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        url = SITE_URL_RE.sub(self.MAIN_URL.rstrip("/"), url)
        try:
            return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def getFullUrl(self, url, currUrl=None):
        return self._rebase(url) if url else ""

    @staticmethod
    def _path(url):
        # domain independent identity of a page
        url = urllib_unquote((url or "").split("#")[0])
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def _isSiteUrl(self, url):
        return bool(SITE_URL_RE.search(url or "")) or not (url or "").startswith("http")

    def getFullIconUrl(self, url, currUrl=None):
        # covers on the site's domain sit behind the same Cloudflare: the cf_clearance cookie + the User-Agent
        # that passed the check, and the host's proxy when one is set
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith("http") or SITE_URL_RE.search(url):
            url = self._rebase(url)
        meta = {}
        if SITE_URL_RE.search(url):
            meta = {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
            try:
                # getCookieHeader logs tracebacks for a cookie file that does not exist yet
                cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
                if cookieHeader:
                    meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
            except Exception:
                printExc()
            proxy = self.getProxy()
            if proxy:
                meta["iptv_http_proxy"] = proxy
        return strwithmeta(url, meta) if meta else url

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("ad_video", "ad_item"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    # -------------------- watched flag --------------------
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"ad_video": "video", "ad_item": "series"}.get(cItem.get("category", ""), "")
            if prefix == "video" and cItem.get("trailer"):
                return ""
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    # -------------------- rows --------------------
    def _episodeParams(self, label, url, icon, desc, normalize, show=""):
        m = EPISODE_RE.search(label)
        episode = m.group(2) if m else ""
        season = SEASON_RE.search(label)
        season = int(season.group(1)) if season else 1
        if not show:
            show = _clean(SEASON_RE.sub(" ", m.group(1) if m else label)) or _clean(label)
        title = label
        if normalize and episode:
            title = "%s - %s" % (show, formatSxxExx(season, episode))
        return {"name": "category", "good_for_fav": True, "category": "ad_video", "title": title, "url": url, "icon": icon, "desc": desc,
                "s_title": show, "s_season": season, "s_episode": str(int(episode)) if episode else "",
                "meta_type": "tv", "meta_title": _latinTitle(show) or show}

    def _movieParams(self, label, url, icon, desc, normalize, year=""):
        title = _clean(label) or label
        m = YEAR_RE.search(title)
        if m:
            year = year or m.group(1)
            title = _clean(YEAR_RE.sub(" ", title)) or title
        dispTitle = label
        if normalize:
            dispTitle = "%s (%s)" % (title, year) if year else title
        return {"name": "category", "good_for_fav": True, "category": "ad_video", "title": dispTitle, "url": url, "icon": icon, "desc": desc,
                "meta_type": "movie", "meta_title": _latinTitle(title) or title, "meta_year": year}

    def _cards(self, data):
        # (url, label, icon, year, desc) of the <article> cards
        main = self.cm.ph.getDataBeetwenMarkers(data, 'id="T20_container"', "<footer", False)[1] or data
        out = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(main, "<article", "</article>"):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+class=[\'"]first_A[\'"][^>]+href=[\'"]([^\'"]+)[\'"]')[0] or \
                self.cm.ph.getSearchGroups(item, r'<a[^>]+href=[\'"](http[^\'"]+)[\'"]')[0]
            url = self._rebase(href) if href and href != "#" else ""
            if not url or url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h[23][^>]*>(.*?)</h[23]>")[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+class=[\'"]first_A[\'"][^>]+title=[\'"]([^\'"]+)[\'"]')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt=[\'"]([^\'"]+)[\'"]')[0])
            if not label:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+(?:data-src|src)=[\'"]([^\'"]+)[\'"]')[0]
            # details: <a title="سنة الإنتاج"><i></i> 2026</a>, status, type / country
            details = [self.cleanHtmlStr(d) for d in re.findall(r'(?s)<a[^>]+href="#"[^>]*>(.*?)</a>', item)]
            details = [d for d in details if d]
            year = self.cm.ph.getSearchGroups(" ".join(details), r"\b((?:19|20)\d{2})\b")[0]
            out.append((url, label, self.getFullIconUrl(icon) if icon else "", year, " | ".join(details)))
        return out

    def _addCards(self, cards, cItem, show=""):
        # episode posts and film posts -> VIDEO, series / films / shows -> folders
        normalize = IsMediaNamingNormalized()
        isMovies = cItem.get("menu") == "movies"
        episodes = []
        for url, label, icon, year, desc in cards:
            if EPISODE_RE.search(label):
                episodes.append(self._episodeParams(label, url, icon or cItem.get("icon", ""), desc, normalize, show))
            elif cItem.get("category") == "ad_eplist":
                params = self._movieParams(label, url, icon or cItem.get("icon", ""), desc, normalize, year or cItem.get("meta_year", ""))
                if cItem.get("meta_title"):
                    params["meta_title"] = cItem["meta_title"]
                self.addVideo(params)
            else:
                movie = isMovies or label.startswith("فيلم")
                title = _clean(label) or label
                if year and movie and normalize and not YEAR_RE.search(title):
                    title = "%s (%s)" % (title, year)
                self.addDir({"name": "category", "good_for_fav": True, "category": "ad_item", "title": title if normalize else label, "url": url,
                             "icon": icon, "desc": desc, "s_title": _clean(label) or label, "meta_type": "movie" if movie else "tv",
                             "meta_title": _latinTitle(label) or _clean(label), "meta_year": year})
        episodes.sort(key=lambda p: int(p["s_episode"]) if p["s_episode"] else 0)
        for params in episodes:
            self.addVideo(params)

    def _pager(self, data):
        # (last page, page url template) from the site's wp-pagenavi
        block = self.cm.ph.getDataBeetwenMarkers(data, "wp-pagenavi", "</div>", False)[1]
        lastPage, tpl = 0, ""
        for href, num in re.findall(r'href=[\'"]([^\'"]*/page/(\d+)/[^\'"]*)[\'"]', block):
            lastPage = max(lastPage, int(num))
            if not tpl:
                tpl = self._rebase(href).replace("/page/%s/" % num, "/page/{page}/", 1)
        return lastPage, tpl

    # -------------------- menus --------------------
    def listMainMenu(self, cItem):
        printDBG("ARADrama.listMainMenu")
        tab = [{"category": "list_items", "title": _("New episodes"), "url": self.getFullUrl("/category/episodes/new/")},
               {"category": "series", "title": _("Series"), "menu": "series"},
               {"category": "movies", "title": _("Movies"), "menu": "movies"},
               {"category": "list_items", "title": _("Shows"), "url": self.getFullUrl("/category/k-shows/")}] + self.searchItems()
        self.listsTab(tab, cItem)

    def listCatItems(self, cItem):
        # the site's own category names
        if cItem.get("category") == "movies":
            tab = [("أفلام أسيوية", "/category/%d8%a7%d9%84%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%84%d8%a2%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/"),
                   ("أفلام كورية", "/type/k-movies/"), ("أفلام صينية", "/type/c-movies/"), ("أفلام يابانية", "/type/j-movie/"),
                   ("أفلام تايوانية", "/type/فيلم-تايواني/"), ("أفلام فيتنامية", "/type/فيلم-فيتنامي/")]
        else:
            tab = [("الدراما الكورية", "/category/serie/korea/"), ("الدراما اليابانية", "/category/serie/japanese/"),
                   ("الدراما الصينية والتايوانية", "/category/serie/chinese-taiwan/"), ("الدراما التايلاندية", "/category/serie/tailand/"),
                   ("الدراما الفلبينية", "/category/serie/f-drama/"), ("الدراما التي تبث حاليا", "/category/ongoing/"),
                   ("الدراما المنتهية مؤخرا", "/category/recent-completed/"), ("الدراما القادمة", "/category/drama-soon/")]
        for title, path in tab:
            self.addDir({"name": "category", "category": "list_items", "title": title, "url": self.getFullUrl(path), "menu": cItem.get("menu", ""), "good_for_fav": True})

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._rebase(cItem["url"])
        pageTpl = cItem.get("page_tpl", "")
        url = pageTpl.format(page=page) if page > 1 and pageTpl else baseUrl
        printDBG("ARADrama.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        self._addCards(self._cards(data), cItem, cItem.get("s_title", "") if cItem.get("category") == "ad_eplist" else "")
        lastPage, tpl = self._pager(data)
        pageTpl = pageTpl or tpl
        hasNext = bool(pageTpl) and page < lastPage
        listItem = dict(cItem)
        listItem.update({"base_url": baseUrl, "page_tpl": pageTpl, "url": baseUrl})
        listItem.pop("trailer", None)
        addPagingItems(self, listItem, page, hasNext, lastPage if hasNext or page > 1 else 0, pageTpl)

    # -------------------- explore --------------------
    def _extractTrailerUrl(self, data):
        block = ""
        for marker in ("tab-trailer-1", "tab-trailer", "trailer"):
            tmp = self.cm.ph.getDataBeetwenMarkers(data, 'id="%s' % marker if marker != "trailer" else marker, "</iframe", False)[1]
            if tmp:
                block = tmp + "</iframe>"
                break
        src = self.cm.ph.getSearchGroups(block, r'<iframe[^>]+src=[\'"]([^\'"]+)[\'"]')[0].strip()
        if not src or re.search(r"\.(?:jpe?g|png|webp|gif)(?:\?|$)", src, re.I):
            return ""
        return "https:" + src if src.startswith("//") else src

    def _servers(self, data):
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "Servrs", "</ul>", False)[1] or self.cm.ph.getDataBeetwenMarkers(data, "Servrs", "</div>", False)[1]
        found = re.findall(r'data-url=[\\\'"]+([^"\'\\]+)', tmp) or re.findall(r'data-url=[\'"]([^\'"]+)[\'"]', data, flags=re.I)
        out = []
        for u in found:
            u = u.replace("&amp;", "&").strip()
            u = "https:" + u if u.startswith("//") else u
            if self.cm.isValidUrl(u) and u not in out:
                out.append(u)
        return out

    def _playableIframe(self, data):
        for src in re.findall(r'<iframe[^>]+src=[\'"]([^\'"]+)[\'"]', data, flags=re.I):
            src = (src or "").strip()
            src = "https:" + src if src.startswith("//") else src
            low = src.lower()
            if not self.cm.isValidUrl(src) or any(x in low for x in ("youtube.com", "youtu.be", "vimeo.com")) or re.search(r"\.(?:jpe?g|png|webp|gif)(?:\?|$)", low):
                continue
            return src
        return ""

    def exploreItems(self, cItem):
        printDBG("ARADrama.exploreItems [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        label = _noColors(cItem.get("title", ""))
        show = cItem.get("s_title") or _clean(label) or label
        story = self._siteInfo(data)[0]
        base = {"icon": cItem.get("icon", ""), "desc": story or cItem.get("desc", ""), "meta_type": cItem.get("meta_type", "tv"),
                "meta_title": cItem.get("meta_title") or _latinTitle(label) or show, "meta_year": cItem.get("meta_year", "")}
        trailerUrl = self._extractTrailerUrl(data)
        if self.cm.isValidUrl(trailerUrl):
            self.addVideo(dict(base, name="category", category="ad_video", trailer=True, good_for_fav=False,
                               title="%s - %s" % (show, _("Trailer")), url=trailerUrl))
        if self._servers(data) or self._playableIframe(data):
            # the page itself plays (a film post or an episode opened as folder by the previous version)
            if EPISODE_RE.search(label):
                params = self._episodeParams(label, cItem["url"], base["icon"], base["desc"], normalize)
            else:
                params = self._movieParams(label, cItem["url"], base["icon"], base["desc"], normalize, base["meta_year"])
            self.addVideo(params)
        # the "watch" button: ?cat=15&s=<post id> lists the episode / film posts
        href = self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenMarkers(data, "vc_btn3-inline", "</div>", False)[1], r'href=[\'"]([^\'"]+?)[\'"]')[0]
        if not href:
            return
        href = href.replace("&amp;", "&").replace("&#038;", "&")
        url = self.getFullUrl("/?" + href.split("?", 1)[1]) if "?" in href else self.getFullUrl(href)
        listItem = dict(cItem, **base)
        listItem.update({"category": "ad_eplist", "url": url, "base_url": url, "page": 1, "s_title": show, "page_tpl": ""})
        self.listItems(listItem)

    # -------------------- search --------------------
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ARADrama.listSearchResult [%s]" % searchPattern)
        url = self.getFullUrl("/?s=%s" % urllib_quote_plus(searchPattern.strip()))
        self.listItems({"name": "category", "category": "list_items", "url": url, "base_url": url, "page": 1})
        if not self.currList and not self.blocked:
            SetIPTVPlayerLastHostError(_("No results found for: %s") % searchPattern)

    # -------------------- links --------------------
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("ARADrama.getLinksForVideo [%s]" % url)
        if not self.cm.isValidUrl(url):
            return []
        sidecar = buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled())
        if cItem.get("trailer") or "Trailer" in cItem.get("title", "") or not self._isSiteUrl(url):
            # the trailer (youtube) or a hoster url
            return [{"name": self.up.getHostName(url, True), "url": url, "need_resolve": 1}]
        pageUrl = self._rebase(url)
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        linksTab = []
        for u in self._servers(data):
            linksTab.append({"name": self.up.getHostName(u, True), "url": strwithmeta(u, {"Referer": pageUrl}), "need_resolve": 1})
        if not linksTab:
            iframe = self._playableIframe(data)
            if iframe:
                linksTab.append({"name": self.up.getHostName(iframe, True), "url": strwithmeta(iframe, {"Referer": pageUrl}), "need_resolve": 1})
        if not linksTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(linksTab, sidecar)

    def getVideoLinks(self, videoUrl):
        printDBG("ARADrama.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    # -------------------- INFO --------------------
    def _siteInfo(self, data):
        # (story, poster, info incl. the cast) of the item page's info block
        block = self.cm.ph.getDataBeetwenMarkers(data, "b_block s-desc", "</div>", False)[1]
        info = {}
        for raw in re.split(r"(?i)<br\s*/?>|</p>|</h3>", block):
            line = self.cleanHtmlStr(raw)
            if ":" not in line:
                continue
            key, value = [x.strip() for x in line.split(":", 1)]
            for labels, field in INFO_FIELDS:
                if key in labels and value and field not in info:
                    info[field] = value
        story = ""
        m = re.search(r"(?s)<h3>\s*القصة\s*:?\s*</h3>(.*?)(?:<h3|$)", block)
        if m:
            story = self.cleanHtmlStr(m.group(1))
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta[^>]+name=[\'"]description[\'"][^>]+content=[\'"]([^\'"]+)[\'"]')[0])
        cast = []
        m = re.search(r"(?s)<h3>\s*أبطال[^<]*</h3>(.*?)(?:<h3|$)", block)
        # "Lee-Soo-Hyuk : في دور <span>role</span><br />"
        for raw in re.split(r"(?i)<br\s*/?>", m.group(1) if m else ""):
            actor = self.cm.ph.getSearchGroups(self.cleanHtmlStr(raw), r"^(.+?)\s*:\s*في\s*دور")[0].replace("-", " ").strip()
            if actor and actor not in cast:
                cast.append(actor)
        if cast:
            info["cast"] = ", ".join(cast[:8])
        poster = self.cm.ph.getSearchGroups(data, r'<meta[^>]+property=[\'"]og:image[\'"][^>]+content=[\'"]([^\'"]+)[\'"]')[0]
        return story, poster, info

    def getArticleContent(self, cItem):
        printDBG("ARADrama.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        url = cItem.get("url", "")
        if self._isSiteUrl(url) and not cItem.get("trailer"):
            sts, data = self.getPage(url)
            if sts:
                story, poster, info = self._siteInfo(data)
        title = _noColors(cItem.get("title", ""))
        metaTitle = cItem.get("meta_title") or _latinTitle(title) or _clean(title)
        if info.get("original_title") and isLatinTitle(info["original_title"]):
            metaTitle = info["original_title"]
        metaType = cItem.get("meta_type") or ("movie" if title.startswith("فيلم") else "tv")
        year = cItem.get("meta_year") or self.cm.ph.getSearchGroups(info.get("broadcast", ""), r"((?:19|20)\d{2})")[0]
        meta = {}
        if metaTitle:
            try:
                meta = getMeta(metaType, metaTitle, year, () if isLatinTitle(metaTitle) else LATIN_ONLY)
            except Exception:
                printExc()
        if year:
            info.setdefault("year", year)
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or StripColorCodes(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or (self.getFullIconUrl(poster) if poster else "") or cItem.get("icon", "")
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    # -------------------- service --------------------
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", None)
        category = self.currItem.get("category", "")
        printDBG("ARADrama.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category in ("series", "movies"):
            self.listCatItems(self.currItem)
        elif category in ("list_items", "ad_eplist", "listItems", "tvshow"):
            # listItems / tvshow: folders saved as favourites by the previous version
            self.listItems(self.currItem)
        elif category in ("ad_item", "explore_item"):
            self.exploreItems(self.currItem)
        elif category in ("search", "search_next_page"):
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
        CHostBase.__init__(self, ARADrama(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("aradrama")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("ad_video", "ad_item", "explore_item") and not cItem.get("trailer")
