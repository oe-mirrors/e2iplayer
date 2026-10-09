# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Qfilm (كيو فيلم) - PHP Melody site with movies with Arabic subtitles (new releases, Arabic/Egyptian,
# foreign, Indian, Asian, Turkish, animation, dubbed, genres). The domain rotates: qfilm.tv redirects
# to the current one. Its Ramadan series live on the sister site q-drama (not part of this host).
#   - "Latest", the site categories (sub-categories as folders) and search, with First page / Jump /
#     Next page (n/last) from the site's pager
#   - movies are VIDEO rows on their page url; links: the server list of play.php?vid=<id> handed to urlparser
#   - watched flag, downloaded flag, favourites (urls re-based on the current domain), name normalisation
#     ("Title (Year)"), sidecar, INFO via moviemeta + the site's description/categories/poster
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
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
config.plugins.iptvplayer.qfilm_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.qfilm_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.qfilm_proxy))
    if config.plugins.iptvplayer.qfilm_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.qfilm_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://www.qfilm.tv/"


YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d{2})(?=\s|\)|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجم|اون لاين|أون لاين|مشاهدة|فيلم|كامل|كاملة|بجودة عالية|HD|FHD|حصريا|حصرياً)(?=\s|$)")
# the side menu "التصنيفات": top level items, one level of sub-categories
MENU_RE = re.compile(r"(?s)<li class=\"dropdown-submenu\"><a href=\"([^\"]+)\"[^>]*>(.*?)</a>\s*<ul class='dropdown-menu'>(.*?)</ul>"
                     r"|<li[^>]*><a href=\"([^\"]+)\"[^>]*>(.*?)</a>")


class QFilm(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "qfilm", "cookie": "qfilm.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/qfilm135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("qfilm")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.qfilm_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        if QFilm.DOMAIN_CACHE:
            self.MAIN_URL = QFilm.DOMAIN_CACHE
            return
        domains = [gettytul()]
        domain = config.plugins.iptvplayer.qfilm_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            # www.qfilm.tv -> 301 -> https://<current sub domain>.qfilm.tv/
            sts, data = self.getPage(domain)
            if sts and "pm-video-thumb" in data:
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", domain))
                QFilm.DOMAIN_CACHE = self.MAIN_URL
                return
        self.MAIN_URL = domains[-1]

    def _rebase(self, url):
        # urls of favourites / older lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
        if url.startswith("./"):
            url = url[2:]
        m = re.match(r"https?://[^/]+/(.*)$", url)
        url = (self.MAIN_URL + m.group(1)) if m else self.getFullUrl(url)
        # Arabic search words in the pager links -> one percent-encoded form
        return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    def _cardIcon(self, item):
        # the list cards carry a lazy-load placeholder in src; the real cover is in data-echo
        for attr in ("data-echo", "data-original", "src"):
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+%s="([^"]+)"' % attr)[0]
            if icon and "/img/" not in icon:
                return self.getFullIconUrl(icon)
        return ""

    @staticmethod
    def _vid(url):
        m = re.search(r"[?&]vid=([^&#]+)", url or "")
        return m.group(1) if m else ""

    @staticmethod
    def _splitTitle(title):
        # "مشاهدة فيلم Heart of the Beast 2026 مترجم HD اون لاين" -> "Heart of the Beast", 2026
        # "فيلم شيش دو (2026)" -> "شيش دو", 2026
        show = JUNK_RE.sub(" ", JUNK_RE.sub(" ", title))
        years = YEAR_RE.findall(show)
        year = years[-1] if years else ""
        if year:
            show = re.sub(r"\(?%s\)?" % year, " ", show)
        show = re.sub(r"\(\s*\)", " ", show)
        return re.sub(r"\s+", " ", show).strip(" -:|"), year

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") == "qf_video":
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("category", "") == "qf_video":
                vid = self._vid(cItem.get("url", ""))
                return "video:%s" % vid if vid else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("/newvideos.php"), "good_for_fav": True},
            {"category": "qf_categories", "title": _("Categories")},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listCategories(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        block = self.cm.ph.getSearchGroups(data, r'(?s)<div class="navslide-header"><a href="[^"]*category\.php">.*?</div>(.*?)<div class="navslide-divider">')[0]
        parent = self._rebase(cItem["parent_url"]) if cItem.get("parent_url") else ""
        for m in MENU_RE.finditer(block):
            href, label, sub = m.group(1), m.group(2), m.group(3)
            if not href:
                href, label, sub = m.group(4), m.group(5), ""
            url = self._rebase(href)
            title = self.cleanHtmlStr(label)
            if "category.php?cat=" not in url or not title:
                continue
            if not parent:
                if sub:
                    self.addDir({"name": "category", "category": "qf_categories", "good_for_fav": True, "title": title, "parent_url": url})
                else:
                    self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": url})
            elif url == parent:
                self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": _("All"), "url": url})
                for subHref, subLabel in re.findall(r'(?s)<a href="([^"]+)"[^>]*>(.*?)</a>', sub):
                    subTitle = self.cleanHtmlStr(subLabel)
                    if subTitle:
                        self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": subTitle, "url": self._rebase(subHref)})

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = self._rebase(cItem["url"])
        printDBG("QFilm.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        grid = self.cm.ph.getDataBeetwenMarkers(data, 'id="pm-grid"', "</ul>", False)[1]
        seen = set()
        count = 0
        for item in grid.split('<div class="thumbnail">')[1:]:
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]*watch\.php\?vid=[^"]+)"')[0]
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3 class="caption">(.*?)</h3>')[0])
            if not rawTitle:
                rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            if not href or not rawTitle:
                continue
            count += 1
            url = self._rebase(href)
            if url in seen:
                continue
            seen.add(url)
            show, year = self._splitTitle(rawTitle)
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="pm-label-duration">(.*?)</span>')[0])
            fields = ((_("Year"), year, "cyan"), (_("Duration"), duration, "green"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
            title = rawTitle
            if normalize and show:
                title = "%s (%s)" % (show, year) if year else show
            self.addVideo({"name": "category", "category": "qf_video", "good_for_fav": True, "title": title, "url": url, "icon": self._cardIcon(item),
                           "desc": desc, "meta_type": "movie", "meta_title": show or rawTitle, "meta_year": year})

        # pager links: category.php?cat=x&page=N, newvideos.php?&page=N, search.php?keywords=x&page=N
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', "</ul>", False)[1]
        nums = [int(n) for n in re.findall(r"<a[^>]*>\s*(\d+)\s*</a>", pager)]
        lastPage = max(nums + [page])
        pageTpl = ""
        for href in re.findall(r'<a[^>]+href="([^"#]+)"', pager):
            tpl = re.sub(r"([?&]page=)\d+", r"\1{page}", self._rebase(href), 1)
            if "{page}" in tpl:
                pageTpl = tpl
        hasNext = count > 0 and lastPage > page and bool(pageTpl)
        listItem = dict(cItem)
        listItem.update({"category": "list_items"})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("QFilm.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/search.php?keywords=%s" % urllib_quote_plus(searchPattern.strip())), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        info = {}
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div itemprop="description" class="MetaDesc">(.*?)</div>')[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta itemprop="description" content="([^"]+)"')[0])
        cats = self.cm.ph.getSearchGroups(data, r'(?s)<div class="CatsDesc">(.*?)</div>')[0]
        genres = [self.cleanHtmlStr(c) for c in re.findall(r"(?s)<a[^>]*>(.*?)</a>", cats)]
        genres = [g for g in genres if g]
        if genres:
            info["genres"] = ", ".join(genres)
        duration = self.cm.ph.getSearchGroups(data, r'<meta itemprop="duration" content="PT(?:(\d+)H)?(?:(\d+)M)?', 2)
        if any(duration):
            info["duration"] = "%d:%02d" % (int(duration[0] or 0), int(duration[1] or 0))
        poster = self.cm.ph.getSearchGroups(data, r'<meta itemprop="image" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("QFilm.getLinksForVideo [%s]" % cItem.get("url", ""))
        vid = self._vid(cItem.get("url", ""))
        if not vid:
            return []
        sts, data = self.getPage(self.getFullUrl("/play.php?vid=%s" % vid))
        if not sts:
            return []
        # var servers = ["<iframe src=\"...\">", ...]; the buttons server-btn-<n> carry the names
        servers = []
        try:
            servers = json_loads(self.cm.ph.getSearchGroups(data, r"(?s)var servers\s*=\s*(\[.*?\]);")[0] or "[]")
        except Exception:
            printExc()
        labels = dict(re.findall(r'(?s)<button id="server-btn-(\d+)"[^>]*>.*?</div>(.*?)</button>', data))
        urltab = []
        for idx, frame in enumerate(servers):
            url = self.cm.ph.getSearchGroups(frame, r"""src=['"]([^'"]+)['"]""")[0].replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in [link["url"] for link in urltab]:
                continue
            label = self.cleanHtmlStr(labels.get(str(idx), ""))
            domain = self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]
            urltab.append({"name": "%s (%s)" % (label, domain) if label else domain, "url": strwithmeta(url, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("QFilm.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("QFilm.getArticleContent [%s]" % cItem.get("url", ""))
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
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("QFilm.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "qf_categories":
            self.listCategories(self.currItem)
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
        CHostBase.__init__(self, QFilm(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("qfilm")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "qf_video"
