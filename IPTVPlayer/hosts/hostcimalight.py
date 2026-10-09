# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# CimaLight (سيما لايت, cimalight.co -> e.cimalight.co): PHP Melody site with new and classic films, Arabic,
# Turkish, Asian, Indian and foreign series, anime, plays and TV shows
#   - "Latest", "Most viewed", Movies / Series / Other (the site categories; "All movies", "Latest episodes"
#     and "All series" on top) and search, with First page / Jump / Next page (n/last) from the site's pager
#   - episode rows of a list -> one series folder per show/season (the episode page lists all its episodes,
#     more season tabs -> season folders); films and plays are VIDEO rows on their watch.php page url
#   - links: the watch page's server page (elif.news, opened with the watch page as Referer) lists the
#     hosters (vfaststream, uqload, anafast ...) - handed to urlparser
#   - search.php sits behind a Cloudflare managed challenge (also for curl-impersonate); without a cleared
#     cookie the search uses the site's live search (ajax-search.php, up to 10 hits, no pager)
#   - watched flag (series -> season -> episode), downloaded flag, favourites (urls re-based on the current
#     domain), name normalisation ("Title (Year)", "Show - SxxExx" from the Arabic labels), sidecar, INFO via
#     moviemeta + the site's story/actors/categories/poster
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
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, E2ColoR, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.cimalight_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.cimalight_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.cimalight_proxy))
    if config.plugins.iptvplayer.cimalight_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.cimalight_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://e.cimalight.co/"


# the entry domain that redirects to the current sub-domain (e.cimalight.co -> /main31 today)
ENTRY_DOMAIN = "https://cimalight.co/"

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
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجم|مدبلجة|مدبلج|اون لاين|أون لاين|مشاهدة|فيلم|كامل|كاملة|بجودة عالية|HD|FHD|"
                     r"جميع الحلقات|جميع حلقات|كل الحلقات|جميع المواسم|كل المواسم|حصريا|حصرياً|والأخيرة|والاخيرة|الاخيرة|الأخيرة)(?=\s|$)")
MENU_GROUPS = (("movies", ("افلام", "أفلام")), ("series", ("مسلسلات",)))
# "download full series in one link" - download pages, nothing to play
SKIP_CATEGORIES = ("download-full-series",)
TAG_A_RE = re.compile(r"<a\s([^>]*)>([^<]*)</a>")
LINK_A_RE = re.compile(r'<a href="([^"]*)"([^>]*)>([^<]*)</a>')
TAG_LI_RE = re.compile(r"<li\s([^>]*)>([^<]*)</li>")
HREF_RE = re.compile(r'href="([^"]*)"')
DATA_EMBED_RE = re.compile(r'data-embed="([^"]*)"')
CAT_KEY = "category.php?cat="
WATCH_KEY = "watch.php?vid="


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


class CimaLight(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "season_id",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cimalight", "cookie": "cimalight.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/cimalight135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("cimalight")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.cimalight_proxy.value) or None

    def _params(self, addParams=None):
        params = dict(addParams if addParams is not None else self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in params:
            params = MergeDicts(params, {"http_proxy": proxy})
        return params

    def getPage(self, baseUrl, addParams=None, post_data=None):
        return self.cm.getPageCFProtection(self._rebase(baseUrl), self._params(addParams), post_data)

    def selectDomain(self):
        if CimaLight.DOMAIN_CACHE:
            self.MAIN_URL = CimaLight.DOMAIN_CACHE
            return
        domains = [gettytul(), ENTRY_DOMAIN]
        domain = config.plugins.iptvplayer.cimalight_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.cm.getPageCFProtection(domain, self._params())
            if sts and "pm-grid" in data and "MELODYURL" in data:
                self.MAIN_URL = self.cm.getBaseUrl(data.meta.get("url", domain))
                break
        else:
            self.MAIN_URL = domains[0]
        CimaLight.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / old lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
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

    @staticmethod
    def _vid(url):
        m = re.search(r"[?&]vid=([^&#]+)", url or "")
        return m.group(1) if m else ""

    @staticmethod
    def _cleanSpaces(text):
        return re.sub(r"\s+", " ", text or "").strip(" -:|")

    def _splitTitle(self, title):
        # "مسلسل خمسين خمسين الحلقة 10 العاشرة" -> show "خمسين خمسين", episode 10
        # "فيلم Practical Magic 2 2026 مترجم" -> "Practical Magic 2", year 2026
        episode = self.cm.ph.getSearchGroups(title, EPISODE_RE.pattern)[0]
        season = _seasonNum(title)
        show = title
        if episode:
            show = EPISODE_RE.split(show)[0]
        show = SEASON_RE.split(show)[0] if season else show
        show = KIND_RE.sub("", show)
        show = JUNK_RE.sub(" ", show)
        years = YEAR_RE.findall(show)
        year = years[-1] if years else ""
        if year and not episode:
            show = re.sub(r"\(?%s\)?" % year, " ", show)
        return self._cleanSpaces(show), season, episode, year

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("cl_video", "cl_series", "cl_season"):
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
            if category == "cl_video":
                vid = self._vid(cItem.get("url", ""))
                return "video:%s" % vid if vid else ""
            show = cItem.get("s_title", "").lower()
            if category == "cl_series" and show:
                return "series:%s|%s" % (show, cItem.get("s_season", 0))
            if category == "cl_season" and show:
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
            {"category": "cl_menu", "title": _("Movies"), "group": "movies"},
            {"category": "cl_menu", "title": _("Series"), "group": "series"},
            {"category": "cl_menu", "title": _("Other"), "group": "other"},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listSiteMenu(self, cItem):
        group = cItem.get("group", "")
        if group == "movies":
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": _("All movies"), "url": self.getFullUrl("/movies.php")})
        elif group == "series":
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": _("Latest episodes"), "url": self.getFullUrl("/episodes.php")})
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": _("All series"), "url": self.getFullUrl("/all-series.php")})
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        seen = set()
        for attrs, label in TAG_A_RE.findall(data):
            href = self.cm.ph.getSearchGroups(attrs, HREF_RE.pattern)[0]
            title = self.cleanHtmlStr(label)
            if CAT_KEY not in href or "&" in href or not href.split(CAT_KEY, 1)[1] or not title:
                continue
            url = self._rebase(href)
            if url in seen or any(word in url for word in SKIP_CATEGORIES):
                continue
            itemGroup = "other"
            for name, words in MENU_GROUPS:
                if title.startswith(words):
                    itemGroup = name
            if itemGroup != group:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": url})

    def _addRow(self, rawTitle, url, icon, duration, normalize, seen):
        show, season, episode, year = self._splitTitle(rawTitle)
        if episode or KIND_RE.match(rawTitle):
            # one folder per show / season - the episode page lists all episodes of it
            key = (show.lower(), season)
            if not show or key in seen:
                return False
            seen.add(key)
            title = show
            if season:
                title = ("%s - %s" % (show, formatSxxExx(season))) if normalize else "%s - %s %d" % (show, _("Season"), season)
            self.addDir({"name": "category", "category": "cl_series", "good_for_fav": True, "title": title, "url": url, "icon": icon,
                         "desc": "", "s_title": show, "s_season": season, "meta_type": "tv", "meta_title": show})
            return True
        if url in seen:
            return False
        seen.add(url)
        fields = ((_("Year"), year, "cyan"), (_("Duration"), duration, "green"))
        desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
        title = rawTitle
        if normalize and show:
            title = "%s (%s)" % (show, year) if year else show
        self.addVideo({"name": "category", "category": "cl_video", "good_for_fav": True, "title": title, "url": url, "icon": icon,
                       "desc": desc, "meta_type": "movie", "meta_title": show or rawTitle, "meta_year": year})
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = self._rebase(cItem["url"])
        printDBG("CimaLight.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        self._listGrid(cItem, data, page)

    def _listGrid(self, cItem, data, page):
        normalize = IsMediaNamingNormalized()
        grid = self.cm.ph.getDataBeetwenMarkers(data, 'id="pm-grid"', "</ul>", False)[1]
        seen = set()
        count = 0
        for item in self.cm.ph.getAllItemsBeetwenMarkers(grid, "<li", "</li>"):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]*watch\.php\?vid=[^"]+)"')[0]
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="ellipsis"[^>]*>(.*?)</a>')[0])
            if not rawTitle:
                rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            if not href or not rawTitle:
                continue
            count += 1
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="pm-label-duration">(.*?)</span>')[0])
            self._addRow(rawTitle, self._rebase(href), icon, duration, normalize, seen)

        # pager links: category.php?cat=x&page=N&order=DESC, newvideos.php?&page=N, search.php?keywords=x&page=N
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
        # [(tab id, season number, label)] of the "المواسم و الحلقات" box
        box = self.cm.ph.getDataBeetwenMarkers(data, 'class="SeasonsBox"', 'class="SeasonsEpisodesMain"', False)[1]
        tabs = []
        for tabId, label in re.findall(r"openCity\(event,\s*'([^']+)'\)\"?[^>]*>([^<]+)<", box):
            label = self.cleanHtmlStr(label)
            tabs.append((tabId, _seasonNum(label) or int(self.cm.ph.getSearchGroups(label, r"(\d+)")[0] or 0), label))
        return tabs

    def listSeries(self, cItem):
        printDBG("CimaLight.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        tabs = self._seasonTabs(data)
        if len(tabs) > 1:
            normalize = IsMediaNamingNormalized()
            for tabId, num, label in sorted(tabs, key=lambda t: t[1]):
                num = num or cItem.get("s_season", 0)
                title = ("%s - %s" % (cItem.get("s_title", ""), formatSxxExx(num))) if normalize and num else label
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "cl_season", "title": title, "season_id": tabId, "s_season": num})
                self.addDir(params)
            return
        if tabs:
            cItem = dict(cItem, season_id=tabs[0][0], s_season=cItem.get("s_season", 0) or tabs[0][1])
        self.listEpisodes(cItem, data)

    def listEpisodes(self, cItem, data=None):
        printDBG("CimaLight.listEpisodes [%s]" % cItem.get("url", ""))
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
        for href, attrs, inner in LINK_A_RE.findall(block):
            if WATCH_KEY not in href:
                continue
            url = self._rebase(href)
            if url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(attrs, r'title="([^"]+)"')[0])
            episode = self.cm.ph.getSearchGroups(self.cleanHtmlStr(inner), EPISODE_RE.pattern)[0] or self.cm.ph.getSearchGroups(label, EPISODE_RE.pattern)[0]
            episodes.append((int(episode) if episode else 0, episode, label, url))
        # the site lists the newest episode first
        for _num, episode, label, url in sorted(episodes, key=lambda e: e[0]):
            if normalize and episode:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = label or ("%s - %s %s" % (show, _("Episode"), episode))
            self.addVideo({"name": "category", "category": "cl_video", "good_for_fav": True, "title": title, "url": url,
                           "icon": cItem.get("icon", ""), "desc": "", "s_title": show, "s_season": season, "s_episode": episode,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        if not episodes:
            # a series page without an episode box - the page itself is the video
            params = dict(cItem)
            params.update({"category": "cl_video", "good_for_fav": True})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CimaLight.listSearchResult [%s]" % searchPattern)
        pattern = searchPattern.strip()
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/search.php?keywords=%s" % urllib_quote_plus(pattern)), "page": 1})
        # search.php is behind a Cloudflare managed challenge: plain request first (works with a cleared cookie),
        # no MyE2i window for every search
        sts, data = self.cm.getPage(self._rebase(cItem["url"]), self._params())
        if sts and 'id="pm-grid"' in data:
            self._listGrid(cItem, data, 1)
            return
        printDBG("CimaLight.listSearchResult search.php blocked -> live search")
        params = self._params()
        params["header"] = dict(self.HEADER, Referer=self.getMainUrl(), **{"X-Requested-With": "XMLHttpRequest"})
        sts, data = self.cm.getPage(self.getFullUrl("/ajax-search.php"), params, {"queryString": pattern})
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for href, _attrs, label in LINK_A_RE.findall(data):
            rawTitle = self.cleanHtmlStr(label)
            if WATCH_KEY in href and rawTitle:
                self._addRow(rawTitle, self._rebase(href), "", "", normalize, seen)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # "مشاهدة وتحميل فيلم X ... ، من بطولة : a، b، c، تدور احداث القصة حول : story"
        text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div itemprop="description">(.*?)</div>')[0])
        if not text:
            text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]+)"')[0])
        info = {}
        story = self.cm.ph.getSearchGroups(text, r"(?:القصة|قصة الفيلم|احداث الفيلم)\s*حول\s*:\s*(.+)$")[0] or text
        actors = self.cm.ph.getSearchGroups(text, r"بطولة\s*:\s*(.+?)(?:،\s*(?:تدور|وتدور|و?القصة)|$)")[0].strip(" ،,")
        if actors:
            info["actors"] = ", ".join([a.strip() for a in actors.split("،") if a.strip()])
        dl = self.cm.ph.getDataBeetwenMarkers(data, '<dl class="dl-horizontal">', "</dd>", False)[1]
        genres = [self.cleanHtmlStr(g) for g in re.findall(r"(?s)<a[^>]*>(.*?)</a>", dl)]
        if genres:
            info["category"] = ", ".join([g for g in genres if g])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("CimaLight.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._rebase(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        urltab = []
        seen = set()
        # the "servers" page on elif.news only answers with the watch page as Referer (else -> google.com)
        serversUrl = self.cm.ph.getSearchGroups(data, r'class="xtgo"[^>]+href="([^"]+)"')[0].replace("&amp;", "&")
        if self.cm.isValidUrl(serversUrl):
            params = self._params()
            params["header"] = dict(self.HEADER, Referer=pageUrl)
            sts, servers = self.cm.getPage(serversUrl, params)
            if sts:
                for attrs, label in TAG_LI_RE.findall(servers):
                    url = self.cm.ph.getSearchGroups(attrs, DATA_EMBED_RE.pattern)[0].strip()
                    # typos in the site's server lists: "hhttps://", "ttps://", "//host/..."
                    url = re.sub(r"^h*t+ps?:", lambda m: "https:" if "s" in m.group(0) else "http:", url)
                    url = "https:" + url if url.startswith("//") else url
                    if not self.cm.isValidUrl(url) or url in seen:
                        continue
                    seen.add(url)
                    domain = self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]
                    label = self.cleanHtmlStr(label)
                    urltab.append({"name": "%s (%s)" % (label, domain) if label else domain, "url": strwithmeta(url, {"Referer": self.cm.getBaseUrl(serversUrl)}), "need_resolve": 1})
        embedUrl = self.cm.ph.getSearchGroups(data, r'itemprop="embedUrl"[^>]+href="([^"]+)"')[0]
        if self.cm.isValidUrl(embedUrl) and embedUrl not in seen:
            domain = self.cm.ph.getSearchGroups(embedUrl, r"https?://(?:www\.)?([^/:]+)")[0]
            urltab.append({"name": domain, "url": strwithmeta(embedUrl, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("CimaLight.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("CimaLight.getArticleContent [%s]" % cItem.get("url", ""))
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
        printDBG("CimaLight.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "cl_menu":
            self.listSiteMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "cl_series":
            self.listSeries(self.currItem)
        elif category == "cl_season":
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
        CHostBase.__init__(self, CimaLight(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cimalight")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("cl_video", "cl_series", "cl_season")
