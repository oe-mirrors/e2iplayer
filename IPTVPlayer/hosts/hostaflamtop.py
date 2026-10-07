# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 framework / host standard:
#   - "Recently added" (/last/ - the pager of /recent/ led back to page 1), the site's movie categories
#     and genres/tags (read from the site menu) and search, with First page / Jump / Next page (n/last);
#     the page url template is taken from the site's own pager links (?page=N/, ?paged=N, /page/N/)
#   - movies are VIDEO rows on their page url; links = the servers of <page>/watch/ handed to urlparser
#   - watched flag, downloaded flag, favourites (urls re-based on the current domain), name
#     normalisation ("Title (Year)"), sidecar, INFO via moviemeta + the site's story/fields/poster
#   - no colour codes in titles, alternative domain + proxy kept
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, E2ColoR, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.aflamtop_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.aflamtop_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.aflamtop_proxy))
    if config.plugins.iptvplayer.aflamtop_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.aflamtop_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://aflam.top/"


YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d{2})(?=\s|\)|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجم|اون لاين|أون لاين|مشاهدة|فيلم|كامل|كاملة|بجودة عالية|HD)(?=\s|$)")
DUBBED_RE = re.compile(r"(?:^|\s)(?:مدبلجة|مدبلج)(?=\s|$)")
# <li ...menu-item...><a ...href="..">label</a> - the attributes are checked in Python
MENU_LI_RE = re.compile(r"(?s)<li([^>]*)>\s*<a([^>]*)>(.*?)</a>")
HREF_RE = re.compile(r'href="([^"]+)"')
# the story is cut at the site's "مشاهدة فيلم/وتحميل ..." tail
STORY_TAIL_RE = re.compile(r"مشاهدة (?:فيلم|وتحميل)")
# site menu entries that are no lists
MENU_SKIP = ("t.me/", "/last", "/recent")
# "<span>نوع الفيلم : </span><a>..</a>" rows of the details box -> INFO keys
INFO_FIELDS = (("category", "تصنيف الفيلم"), ("genres", "نوع الفيلم"), ("year", "تاريخ اصدار الفيلم"), ("language", "لغة الفيلم"),
               ("quality", "جودة الفيلم"), ("country", "دولة"), ("age_limit", "التصنيف العمرى"), ("actors", "بطولة"))


class AflamTOP(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "aflamtop", "cookie": "aflamtop.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/aflamtop135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("aflamtop")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.aflamtop_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        if AflamTOP.DOMAIN_CACHE:
            self.MAIN_URL = AflamTOP.DOMAIN_CACHE
            return
        domains = [gettytul()]
        domain = config.plugins.iptvplayer.aflamtop_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.getPage(domain)
            if sts and "Small--Box" in data:
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", domain))
                break
        else:
            self.MAIN_URL = domains[-1]
        AflamTOP.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / old lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        m = re.match(r"https?://[^/]+/(.*)$", url)
        url = (self.MAIN_URL + m.group(1)) if m else self.getFullUrl(url)
        # Arabic slugs come raw or percent-encoded -> one percent-encoded form
        return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")

    @staticmethod
    def _path(url):
        # domain independent identity of a page
        url = urllib_unquote(url or "")
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    @staticmethod
    def _splitTitle(title):
        # "فيلم Man of Steel 2013 مترجم" -> ("Man of Steel", "2013", dubbed)
        dubbed = bool(DUBBED_RE.search(title))
        clean = DUBBED_RE.sub(" ", JUNK_RE.sub(" ", title))
        years = YEAR_RE.findall(clean)
        year = years[-1] if years else ""
        if year:
            clean = re.sub(r"\(?%s\)?" % year, " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip(" -:|")
        return clean, year, dubbed

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") == "at_video":
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("category") == "at_video":
                path = self._path(cItem.get("url", ""))
                return "video:%s" % path if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            # /last/ = the site's "المضاف حديثا"; the pager of /recent/ leads back to page 1
            {"category": "list_items", "title": _("Recently added"), "url": self.getFullUrl("/last/"), "good_for_fav": True},
            {"category": "at_menu", "title": _("Movies"), "kind": "categories"},
            {"category": "at_menu", "title": _("Genres"), "kind": "genres"},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listSiteMenu(self, cItem):
        # the site menu: /category/ links = movie sections, /genre/ + /tag/ links = genres
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        wantGenres = cItem.get("kind") == "genres"
        seen = set()
        for liAttrs, aAttrs, label in MENU_LI_RE.findall(data):
            hrefs = [m.group(1) for m in HREF_RE.finditer(aAttrs) if m.start() > 0]
            if "menu-item" not in liAttrs[1:] or not hrefs:
                continue
            url = self.getFullUrl(hrefs[-1])
            title = self.cleanHtmlStr(label)
            path = self._path(url)
            if not title or not path or path in seen or any(s in url for s in MENU_SKIP):
                continue
            isGenre = "/genre/" in path or "/tag/" in path
            if isGenre != wantGenres or not (isGenre or "/category/" in path):
                continue
            seen.add(path)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": url})

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = self._rebase(cItem["url"])
        baseUrl = cItem.get("base_url") or url
        printDBG("AflamTOP.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, 'class="Small--Box"', "</a>"):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            if not href:
                continue
            url = self._rebase(href)
            path = self._path(url)
            if path in seen:
                continue
            seen.add(path)
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3[^>]*class="title"[^>]*>(.*?)</h3>')[0])
            if not rawTitle:
                rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            if not rawTitle:
                continue
            clean, year, dubbed = self._splitTitle(rawTitle)
            genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<ul class="liList">\s*<li>(.*?)</li>')[0])
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<li class="imdbRating">(.*?)</li>')[0])
            fields = ((_("Year"), year, "cyan"), (_("Genre"), genre, "green"), ("IMDb", rating, "yellow"), (_("Dubbed"), _("Yes") if dubbed else "", "magenta"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
            title = rawTitle
            if normalize and clean:
                title = ("%s - %s" % (clean, _("Dubbed"))) if dubbed else clean
                if year:
                    title = "%s (%s)" % (title, year)
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            self.addVideo({"name": "category", "category": "at_video", "good_for_fav": True, "title": title, "url": url,
                           "icon": self.getFullIconUrl(icon), "desc": desc,
                           "meta_type": "movie", "meta_title": clean or rawTitle, "meta_year": year})

        # pager: the page parameter differs per section (?page=N/, ?paged=N, &page=N) - the template
        # is taken from the site's own pager links
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', "</ul>", False)[1]
        nums = [int(n) for n in re.findall(r'class="page-numbers[^"]*"[^>]*>\s*(\d+)\s*<', pager)]
        lastPage = max(nums + [page])
        pageTpl = ""
        for href in re.findall(r'<a[^>]+href="([^"]+)"', pager):
            tpl = re.sub(r"([?&]paged?=|/page/)\d+", r"\1{page}", self._rebase(href), 1)
            if "{page}" in tpl:
                pageTpl = tpl
        hasNext = bool(seen) and lastPage > page and bool(pageTpl)
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AflamTOP.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/?s=%s" % urllib_quote_plus(searchPattern.strip()))
        cItem.update({"category": "list_items", "url": base, "base_url": base, "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        box = self.cm.ph.getDataBeetwenMarkers(data, '<div class="infoAndWatch', '<div class="SingleContent', False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r'(?s)<div class="StoryArea">(.*?)</div>')[0])
        m = STORY_TAIL_RE.search(story)
        story = (story[:m.start()] if m else story).strip()
        info = {}
        for key, word in INFO_FIELDS:
            val = self.cm.ph.getSearchGroups(box, r"(?s)<span>%s[^<]*</span>(.*?)</li>" % word)[0]
            vals = []
            for v in re.findall(r"(?s)<a[^>]*>(.*?)</a>", val):
                v = self.cleanHtmlStr(v)
                if v and v not in vals:
                    vals.append(v)
            if vals:
                info[key] = ", ".join(vals)
        rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="imdbR">.*?<span>(.*?)</span>')[0])
        if rating:
            info["imdb_rating"] = rating
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("AflamTOP.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(self._rebase(cItem["url"]).rstrip("/") + "/watch/")
        if not sts:
            return []
        urltab = []
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="ServersList"', "</ul>", False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            url = self.cm.ph.getSearchGroups(item, r'data-watch="([^"]+)"')[0].replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url):
                continue
            label = self.cleanHtmlStr(re.sub(r"(?s)<noscript>.*?</noscript>", "", item))
            domain = self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]
            name = "%s (%s)" % (label, domain) if label else domain
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled(), self._siteInfo(data)[0]))

    def getVideoLinks(self, videoUrl):
        printDBG("AflamTOP.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("AflamTOP.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta("movie", cItem["meta_title"], cItem.get("meta_year", ""), skip)
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
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("AflamTOP.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "at_menu":
            self.listSiteMenu(self.currItem)
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
        CHostBase.__init__(self, AflamTOP(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("aflamtop")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "at_video"
