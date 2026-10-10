# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# MovizHome plugin for oe-mirrors IPTVPlayer
# Author : MohamedOS (Modified By Mohamed Elsafty)
# Description: A plugin to access MovizHome website content
# 10.10.2026 - host standard: films are VIDEO rows keyed on their page url (watched / downloaded flag,
#   favourites incl. the old ones), name normalisation "Title (Year)", sidecar, INFO via moviemeta + the site's
#   story / genre / language / country / quality / age rating / IMDb rating; First page / Jump / Next page with
#   the site's own pager (genre and tag pages "?page=N/", "recent" "?paged=N", search "&page=N"); servers of the
#   "/watch/" page resolved through urlparser only when chosen; no colour codes; py2 load fix (no "import html");
#   covers carry the cf_clearance cookie + User-Agent once MyE2i solved a Cloudflare check
# 10.10.2026 - review: a sub-menu saved as favourite by the previous version (its sub-lists as {"title", "url"}) lists
#   them again instead of rows named "title" / "url"
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://movizhome.click/"


# (label, path, [(sub label, sub path)]) - labels as the site's menu writes them
MENU_TREE = [
    ("افلام اجنبيه", "category/افلام-movis/افلام-اجنبية/", [
        ("الأكشن", "genre/اكشن/"), ("الرعب", "genre/رعب/"), ("الخيال العلمي", "genre/خيال-علمي/"), ("الفانتازيا", "genre/fantasy-movies/"),
        ("رومانسية", "genre/رومانسية/"), ("الكوميديا", "genre/كوميديا/"), ("الإثارة والتشويق", "genre/إثارة/"), ("الجريمة", "genre/جريمة/"),
        ("المغامرات", "genre/مغامرات/"), ("الدراما", "genre/دراما/"), ("كلاسيكية", "tag/افلام-كلاسيكية/"), ("الغموض", "genre/غموض/"),
        ("عائلية", "genre/عائلي/"), ("تاريخية", "genre/تاريخي/"), ("الويسترن", "genre/ويسترن/"),
    ]),
    ("افلام هندية", "category/افلام-movis/افلام-هنديه/", [
        ("التيلجو", "tag/telugu/"), ("تاميلية", "tag/افلام-تاميلية/"), ("ماليالامية", "tag/افلام-ماليالامية/"), ("كنادية", "tag/افلام-كنادية/"),
        ("بنجابية", "tag/punjabi/"), ("ماراثية", "tag/افلام-ماراثية/"), ("بنغالية", "tag/افلام-بنغالية/"), ("كجراتية", "tag/افلام-كجراتية/"),
    ]),
    ("افلام آسيوية", "category/افلام-movis/افلام-اسيويه/", [
        ("كورية", "language/الكورية/"), ("يابانية", "language/اليابانية/"), ("صينية", "language/الصينية/"), ("تايلاندية", "language/التايلاندية/"),
        ("إندونيسية", "language/الاندونيسية/"), ("فلبينية", "language/الفلبينية/"), ("منغولية", "language/المغولية/"),
    ]),
    ("افلام فرنسية", "category/افلام-movis/افلام-فرنسية/", []),
    ("افلام تركية", "category/افلام-movis/افلام-تركية/", []),
    ("افلام مدبلجة", "category/افلام-movis/افلام-مدبلجة/", []),
    ("انيميشن", "category/افلام-كارتون/", []),
]
YEAR_RE = re.compile(r"(?:^|\s)\(?((?:19|20)\d{2})\)?(?=\s|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:فيلم|افلام|مترجم|مترجمة|مدبلج|مدبلجة|اون لاين|أون لاين|مشاهدة|وتحميل|كامل|كاملة|HD)(?=\s|$)")
# the longest run of Latin words in a mixed Arabic / English title ("الحارس Keeper" -> "Keeper")
LATIN_RUN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'&.,:!?\- ]*[A-Za-z0-9!?]|[A-Za-z]")
SITE_DOMAIN_RE = re.compile(r"^https?://(?:www\.)?movizhome\.[a-z]+(?=/|$)", re.I)
# site INFO rows: <span>label : </span> <a>value</a>...
SITE_FIELDS = (("genres", "نوع الفيلم"), ("released", "تاريخ اصدار الفيلم"), ("language", "لغة الفيلم"), ("quality", "جودة الفيلم"),
               ("country", "دولة"), ("age_limit", "التصنيف العمرى الفيلم"))


def _clean(text):
    text = JUNK_RE.sub(" ", JUNK_RE.sub(" ", text or ""))
    # the en dash as a whole sequence (py2 str.strip would take its single utf-8 bytes)
    return re.sub(r"\s+", " ", text.replace("–", " ")).strip(" -:|")


def _titleYear(label):
    # "فيلم Keeper 2025 مترجم" -> ("Keeper", "2025")
    title = _clean(label)
    years = YEAR_RE.findall(title)
    year = years[-1] if years else ""
    if year:
        stripped = _clean(re.sub(r"(?:^|\s)\(?%s\)?(?=\s|$)" % year, " ", title))
        title = stripped or title
    return title or label, year


def _metaTitle(title):
    # the English title for the meta services when the site writes both
    runs = [r.strip() for r in LATIN_RUN_RE.findall(title or "") if re.search(r"[A-Za-z]", r)]
    return max(runs, key=len) if runs else title


class MovizHome(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "movizhome", "cookie": "movizhome.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/movizhome135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("movizhome")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        # one form for every page url: main domain, percent-encoded Arabic slugs
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        elif not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        url = SITE_DOMAIN_RE.sub(self.MAIN_URL.rstrip("/"), url)
        try:
            return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", urllib_unquote(self._canonUrl(url))).split("?")[0].rstrip("/").lower()

    def getFullIconUrl(self, url, currUrl=None):
        # once MyE2i stored a cf_clearance cookie (a later Cloudflare check) the cover download needs it + the
        # User-Agent that passed the check; covers on foreign domains stay plain
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http") or self.up.getDomain(url).lower() != self.up.getDomain(self.MAIN_URL).lower():
            return url
        meta = {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") == "video":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("category") == "video":
                path = self._path(cItem.get("url", ""))
                return "video:%s" % path if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        self.addDir(dict(cItem, category="list_items", title=_("Recently added"), url=self.MAIN_URL + "recent/"))
        for label, path, subs in MENU_TREE:
            params = dict(cItem, title=label, url=self._canonUrl(self.MAIN_URL + path), good_for_fav=True)
            if subs:
                params.update({"category": "list_sub_menu", "subs": [(s[0], self._canonUrl(self.MAIN_URL + s[1])) for s in subs]})
            else:
                params["category"] = "list_items"
            self.addDir(params)
        self.listsTab(self.searchItems(), cItem)

    def listSubMenu(self, cItem):
        self.addDir(dict(cItem, category="list_items", title=_("All"), subs=None))
        for sub in cItem.get("subs") or []:
            if isinstance(sub, dict):
                # favourites of the previous version: {"title": "افلام <name>", "url": ...}
                title, url = sub.get("title", ""), sub.get("url", "")
            else:
                title, url = "افلام %s" % sub[0], sub[1]
            if title and url:
                self.addDir(dict(cItem, category="list_items", title=title, url=self._canonUrl(url), subs=None, good_for_fav=True))

    def _filmParams(self, label, url, icon, desc, normalize):
        title, year = _titleYear(label)
        raw = re.sub(r"^فيلم\s+", "", label).strip() or label
        dispTitle = ("%s (%s)" % (title, year) if year else title) if normalize else raw
        return {"name": "category", "good_for_fav": True, "category": "video", "title": dispTitle, "url": url, "icon": icon, "desc": desc,
                "meta_title": _metaTitle(title), "meta_year": year}

    def _cards(self, data):
        out = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="Small--Box">', "</a>"):
            url = self._canonUrl(self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0])
            if not url or url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3 class="title">(.*?)</h3>')[0])
            if not label:
                label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not label:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            info = []
            for cls in ("genre", "quality"):
                value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<li[^>]*class="%s"[^>]*>(.*?)</li>' % cls)[0])
                if value:
                    info.append(value)
            imdb = self.cm.ph.getSearchGroups(item, r'(?s)class="imdbRating"[^>]*>.*?([\d.]+)\s*</li>')[0]
            if imdb:
                info.append("IMDb %s" % imdb)
            out.append((url, label, self.getFullIconUrl(icon) if icon else "", " | ".join(info)))
        return out

    def _pager(self, data):
        # (last page, page url template) from the site's <ul class='page-numbers'>
        block = self.cm.ph.getDataBeetwenMarkers(data, "class='page-numbers'", "</ul>", False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, 'class="page-numbers"', "</ul>", False)[1]
        lastPage, tpl = 0, ""
        for href, num in re.findall(r'<a class="page-numbers" href="([^"]+)">\s*(\d+)\s*</a>', block):
            num = int(num)
            if num > lastPage:
                lastPage = num
            if not tpl:
                # "...?page=2/", "...?paged=2", "/?s=x&#038;page=2" -> "{page}" in place of the number
                href = self._canonUrl(href)
                tpl = re.sub(r"([?&/]page[d]?[=/])%d(?=[/&]|$)" % num, lambda m: m.group(1) + "{page}", href, count=1)
                if "{page}" not in tpl:
                    tpl = ""
        return lastPage, tpl

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem["url"])
        pageTpl = cItem.get("page_tpl", "")
        url = pageTpl.format(page=page) if page > 1 and pageTpl else baseUrl
        printDBG("MovizHome.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        for url, label, icon, desc in self._cards(data):
            self.addVideo(self._filmParams(label, url, icon, desc, normalize))
        lastPage, tpl = self._pager(data)
        pageTpl = pageTpl or tpl
        lastPage = max(lastPage, cItem.get("last_page", 0) or 0)
        hasNext = bool(pageTpl) and page < lastPage
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "page_tpl": pageTpl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage if hasNext or page > 1 else 0, pageTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MovizHome.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        baseUrl = "%s?s=%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern.strip()))
        cItem.update({"category": "list_items", "url": baseUrl, "base_url": baseUrl, "page": 1})
        self.listItems(cItem)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No results found for: %s") % searchPattern)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        pageUrl = self._canonUrl(cItem.get("url", ""))
        printDBG("MovizHome.getLinksForVideo [%s]" % pageUrl)
        if not pageUrl:
            return []
        watchUrl = pageUrl.split("?")[0].rstrip("/") + "/watch/"
        sts, data = self.getPage(watchUrl)
        if not sts:
            return []
        urltab = []
        for link, item in re.findall(r'(?s)<li[^>]+data-watch="([^"]+)"[^>]*>(.*?)</li>', data):
            link = link.replace("&amp;", "&").strip()
            if link.startswith("//"):
                link = "https:" + link
            if not self.cm.isValidUrl(link):
                continue
            name = self.cleanHtmlStr(re.sub(r"(?s)<noscript>.*?</noscript>", "", item)) or self.up.getHostName(link, True)
            urltab.append({"name": name, "url": strwithmeta(link, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("MovizHome.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="StoryArea">\s*<p>(.*?)</p>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'(?s)<div class="image">\s*<img[^>]+src="([^"]+)"')[0]
        info = {}
        for key, label in SITE_FIELDS:
            row = self.cm.ph.getSearchGroups(data, r"(?s)<span>%s\s*:\s*</span>(.*?)</li>" % label)[0]
            values = [self.cleanHtmlStr(v) for v in re.findall(r"(?s)<a[^>]*>(.*?)</a>", row)]
            values = [v for v in values if v]
            if values:
                info[key] = ", ".join(values)
        imdb = self.cm.ph.getSearchGroups(data, r'(?s)<div class="imdbR">.*?<span>([\d.]+)</span>')[0]
        if imdb:
            info["imdb_rating"] = imdb
        return story, poster, info

    def getArticleContent(self, cItem):
        printDBG("MovizHome.getArticleContent [%s]" % cItem.get("url", ""))
        # rows saved by the old version (favourites) have no meta fields - taken from their title then
        title, year = _titleYear(cItem.get("title", ""))
        title = cItem.get("meta_title") or _metaTitle(title)
        year = cItem.get("meta_year") or year
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
            if not year:
                year = self.cm.ph.getSearchGroups(info.get("released", ""), r"((?:19|20)\d{2})")[0]
        meta = {}
        if title:
            try:
                meta = getMeta("movie", title, year, () if isLatinTitle(title) else LATIN_ONLY)
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
        printDBG("MovizHome.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_sub_menu":
            self.listSubMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, MovizHome(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("movizhome")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "video"
