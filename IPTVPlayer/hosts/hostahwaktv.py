# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# AhwakTV (اهواك تي في) - PHP Melody site with Egyptian / Arabic / Gulf / Turkish / foreign series
# (Ramadan series of several years), classic and new Arabic films, foreign / Indian / Asian films, cartoons.
# The domain rotates: ahwaktv.net redirects to the current one.
#   - "Latest", "Most viewed", the series index (one card per show), the site categories (sub-categories
#     as folders) and search, with First page / Jump / Next page (n/last) from the site's pager
#   - episode rows of a list -> one series folder per show/season (view-serie.php lists the episodes,
#     more season tabs -> season folders); movies are VIDEO rows on their page url
#   - links: the servers of see.php?vid=<id> handed to urlparser
#   - watched flag (series -> season -> episode), downloaded flag, favourites (urls re-based on the current
#     domain), name normalisation ("Title (Year)", "Show - SxxExx" from the Arabic labels), sidecar,
#     INFO via moviemeta + the site's description/section/poster
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, E2ColoR, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.ahwaktv_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.ahwaktv_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.ahwaktv_proxy))
    if config.plugins.iptvplayer.ahwaktv_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.ahwaktv_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://ahwaktv.net/"


# Arabic ordinals of season labels ("الموسم الثاني")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5),
    ("السادسة", 6), ("السادس", 6), ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8),
    ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d{2})(?=\s|\)|$)")
KIND_RE = re.compile(r"^\s*(?:مسلسل|برنامج|انمي|أنمي)\s+")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجم|اون لاين|أون لاين|مشاهدة|فيلم|كامل|كاملة|بجودة عالية|HD|FHD|"
                     r"جميع الحلقات|جميع حلقات|كل الحلقات|جميع المواسم|كل المواسم|حصريا|حصرياً|والأخيرة|والاخيرة)(?=\s|$)")
# the side menu "Categories": top level items, one level of sub-categories
MENU_RE = re.compile(r"(?s)<li class=\"dropdown-submenu\"><a href=\"([^\"]+)\"[^>]*>(.*?)</a>\s*<ul class='dropdown-menu'>(.*?)</ul>"
                     r"|<li[^>]*><a href=\"([^\"]+)\"[^>]*>(.*?)</a>")
EPISODES_PER_PAGE = 100
SERIE_KEY = "view-serie.php?name="


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


class AhwakTV(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "season_id",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "ahwaktv", "cookie": "ahwaktv.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/ahwaktv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("ahwaktv")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.ahwaktv_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        if AhwakTV.DOMAIN_CACHE:
            self.MAIN_URL = AhwakTV.DOMAIN_CACHE
            return
        domains = [gettytul()]
        domain = config.plugins.iptvplayer.ahwaktv_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            # ahwaktv.net -> 301 -> https://<current sub domain>.ahwaktv.net/
            sts, data = self.getPage(domain)
            if sts and "pm-video-thumb" in data:
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", domain))
                AhwakTV.DOMAIN_CACHE = self.MAIN_URL
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
        for attr in ("data-echo", "src"):
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+%s="([^"]+)"' % attr)[0]
            if icon and "/img/" not in icon:
                return self.getFullIconUrl(icon)
        return ""

    @staticmethod
    def _vid(url):
        m = re.search(r"[?&]vid=([^&#]+)", url or "")
        return m.group(1) if m else ""

    @staticmethod
    def _cleanSpaces(text):
        return re.sub(r"\s+", " ", text or "").strip(" -:|")

    def _splitTitle(self, title):
        # "مسلسل breaking bad الموسم الرابع الحلقة 6 مترجمة" -> show "breaking bad", season 4, episode 6
        # "فيلم الأقمر 1978 كامل HD" -> "الأقمر", year 1978
        episode = self.cm.ph.getSearchGroups(title, EPISODE_RE.pattern)[0]
        season = _seasonNum(title)
        show = title
        if episode:
            show = EPISODE_RE.split(show)[0]
        show = SEASON_RE.split(show)[0] if season else show
        show = JUNK_RE.sub(" ", KIND_RE.sub("", JUNK_RE.sub(" ", show)))
        years = YEAR_RE.findall(show)
        year = years[-1] if years else ""
        if year and not episode:
            show = re.sub(r"\(?%s\)?" % year, " ", show)
        show = re.sub(r"\(\s*\)", " ", show)
        return self._cleanSpaces(show), season, episode, year

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("ah_video", "ah_series", "ah_season"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
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
            if category == "ah_video":
                vid = self._vid(cItem.get("url", ""))
                return "video:%s" % vid if vid else ""
            show = cItem.get("s_title", "").lower()
            if category == "ah_series" and show:
                return "series:%s|%s" % (show, cItem.get("s_season", 0))
            if category == "ah_season" and show:
                return "season:%s|%s" % (show, cItem.get("s_season", 0))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("/newvideos.php"), "good_for_fav": True},
            {"category": "list_items", "title": _("Most viewed"), "url": self.getFullUrl("/topvideos.php"), "good_for_fav": True},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/moslslat.php"), "good_for_fav": True},
            {"category": "ah_categories", "title": _("Categories")},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listCategories(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        block = self.cm.ph.getSearchGroups(data, r'(?s)<div class="navslide-header"><a href="[^"]*category\.php">.*?</div>(.*?)<div class="navslide-divider">')[0]
        parent = cItem.get("parent_url", "")
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
                    self.addDir({"name": "category", "category": "ah_categories", "title": title, "parent_url": url})
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
        printDBG("AhwakTV.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        grid = self.cm.ph.getDataBeetwenMarkers(data, 'id="pm-grid"', "</ul>", False)[1]
        seen = set()
        count = 0
        for item in grid.split('<div class="thumbnail">')[1:]:
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]*(?:watch\.php\?vid=|view-serie\.php\?name=)[^"]+)"')[0]
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="ellipsis"[^>]*>(.*?)</a>')[0])
            if not rawTitle:
                rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            if not href or not rawTitle:
                continue
            count += 1
            url = self._rebase(href)
            icon = self._cardIcon(item)
            show, season, episode, year = self._splitTitle(rawTitle)
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="pm-label-duration">(.*?)</span>')[0])
            if SERIE_KEY in url or episode or KIND_RE.match(rawTitle):
                # one folder per show / season - its series page lists all episodes
                key = (show.lower(), season)
                if not show or key in seen:
                    continue
                seen.add(key)
                title = show
                if season:
                    title = ("%s - %s" % (show, formatSxxExx(season))) if normalize else "%s - %s %d" % (show, _("Season"), season)
                self.addDir({"name": "category", "category": "ah_series", "good_for_fav": True, "title": title, "url": url, "icon": icon,
                             "desc": "", "s_title": show, "s_season": season, "meta_type": "tv", "meta_title": show})
            else:
                if url in seen:
                    continue
                seen.add(url)
                fields = ((_("Year"), year, "cyan"), (_("Duration"), duration, "green"))
                desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
                title = rawTitle
                if normalize and show:
                    title = "%s (%s)" % (show, year) if year else show
                self.addVideo({"name": "category", "category": "ah_video", "good_for_fav": True, "title": title, "url": url, "icon": icon,
                               "desc": desc, "meta_type": "movie", "meta_title": show or rawTitle, "meta_year": year})

        # pager links: category.php?cat=x&page=N&order=DESC, newvideos.php?&page=N, moslslat.php?&page=N,
        # search.php?keywords=x&page=N
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

    def _seasonTabs(self, data):
        # [(tab id, season number, label)] of the "المواسم والحلقات" box
        box = self.cm.ph.getDataBeetwenMarkers(data, 'class="SeasonsBoxUL', '<div class="SeasonsEpisodesMains', False)[1]
        tabs = []
        for tabId, label in re.findall(r"openCity\(event,\s*'([^']+)'\)\"?[^>]*>([^<]+)<", box):
            label = self.cleanHtmlStr(label)
            tabs.append((tabId, _seasonNum(label) or int(self.cm.ph.getSearchGroups(tabId, r"(\d+)")[0] or 0), label))
        return tabs

    def listSeries(self, cItem):
        printDBG("AhwakTV.listSeries [%s]" % cItem.get("url", ""))
        url = self._rebase(cItem["url"])
        sts, data = self.getPage(url)
        if not sts:
            return
        if SERIE_KEY not in url:
            # a folder made of an episode row -> its series page
            serie = self.cm.ph.getSearchGroups(data, r'href="([^"]*view-serie\.php\?name=[^"]+)"')[0]
            if serie:
                url = self._rebase(serie)
                sts, data = self.getPage(url)
                if not sts:
                    return
        tabs = self._seasonTabs(data)
        if not tabs:
            # an episode / programme without a series page - the page itself is the video
            params = dict(cItem)
            params.update({"category": "ah_video", "good_for_fav": True})
            self.addVideo(params)
            return
        cItem = dict(cItem, url=url)
        wanted = cItem.get("s_season", 0)
        selected = [t for t in tabs if wanted and t[1] == wanted]
        if not selected and len(tabs) > 1:
            normalize = IsMediaNamingNormalized()
            show = cItem.get("s_title", "")
            for tabId, num, label in sorted(tabs, key=lambda t: t[1]):
                title = ("%s - %s" % (show, formatSxxExx(num))) if normalize and num else label
                params = stripPagerKeys(dict(cItem))
                params.update({"good_for_fav": True, "category": "ah_season", "title": title, "season_id": tabId, "s_season": num})
                self.addDir(params)
            return
        tabId, num, _label = (selected or tabs)[0]
        self.listEpisodes(dict(cItem, season_id=tabId, s_season=num or wanted), data)

    def listEpisodes(self, cItem, data=None):
        printDBG("AhwakTV.listEpisodes [%s]" % cItem.get("url", ""))
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 0) or 1
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="%s"' % cItem.get("season_id", "Season1"), "</ul>", False)[1]
        normalize = IsMediaNamingNormalized()
        episodes = []
        seen = set()
        for item in block.split('<div class="thumbnail">')[1:]:
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]*watch\.php\?vid=[^"]+)"')[0]
            if not href:
                continue
            url = self._rebase(href)
            if url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            num = self.cm.ph.getSearchGroups(label, EPISODE_RE.pattern)[0]
            episodes.append((url, num, label, self._cardIcon(item)))
        page = cItem.get("page", 1)
        lastPage = max(1, (len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE)
        for url, num, label, icon in episodes[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]:
            if normalize and num:
                title = "%s - %s" % (show, formatSxxExx(season, num))
            else:
                title = label or "%s - %s %s" % (show, _("Episode"), num)
            self.addVideo({"name": "category", "category": "ah_video", "good_for_fav": True, "title": title, "url": url,
                           "icon": icon or cItem.get("icon", ""), "desc": "", "s_title": show, "s_season": season, "s_episode": num,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        if lastPage > 1:
            # local pages of a long show: the "template" is the series page itself, the page number
            # travels in cItem["page"]
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage, self._rebase(cItem["url"]))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AhwakTV.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/search.php?keywords=%s" % urllib_quote_plus(searchPattern.strip())), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        info = {}
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta itemprop="description" content="([^"]+)"')[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]+)"')[0])
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<span>مدة العرض\s*:\s*</span>\s*<span>(.*?)</span>")[0])
        if duration:
            info["duration"] = duration
        section = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<ul class="breadcrumbNav">.*?<a href="[^"]*category\.php\?cat=[^"]*"[^>]*>(.*?)</a>')[0])
        if section:
            info["category"] = section
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("AhwakTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        vid = self._vid(cItem.get("url", ""))
        if not vid:
            return []
        sts, data = self.getPage(self.getFullUrl("/see.php?vid=%s" % vid))
        if not sts:
            return []
        urltab = []
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="WatchList', "</ul>", False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            url = self.cm.ph.getSearchGroups(item, r'data-embed-url="([^"]+)"')[0].replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in [link["url"] for link in urltab]:
                continue
            # hosters urlparser cannot resolve (listeamed/VidGuard only redirects to ads, vidhd.vip is gone) are left out
            if self.up.checkHostSupport(url) != 1:
                printDBG("AhwakTV.getLinksForVideo unsupported hoster [%s]" % url)
                continue
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<strong>(.*?)</strong>")[0])
            domain = self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]
            urltab.append({"name": "%s (%s)" % (label, domain) if label else domain, "url": strwithmeta(url, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("AhwakTV.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("AhwakTV.getArticleContent [%s]" % cItem.get("url", ""))
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
        printDBG("AhwakTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "ah_categories":
            self.listCategories(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "ah_series":
            self.listSeries(self.currItem)
        elif category == "ah_season":
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, AhwakTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("ahwaktv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("ah_video", "ah_series", "ah_season")
