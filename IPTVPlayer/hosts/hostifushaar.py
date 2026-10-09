# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# iFushaar (موقع فشار) - films with Arabic subtitles (plus older episodes of a few US series); the site
# moves between sub-domains of ifushaar.com, t.ifushaar.com redirects to the current one (e.ifushaar.com
# on 09.10.2026)
#   - menu: latest, trending, foreign films, genres and search, First page / Jump / Next page (n/last) from
#     the site's pager; films and episodes are VIDEO rows keyed on their /video/<slug>/ page
#   - links: the video page carries a base64 "hash" ("name => url" lines). Newer posts point to an
#     albaplayer page (w.aflamy.pro): every ?serv=N tab is one link (MP4Plus, AnaFast, Vidoba, VidSpeed,
#     OK ...) whose hoster iframe goes to urlparser; older posts list hoster embeds directly - only the
#     ones urlparser supports are offered (most old hosters are parked domains now)
#   - watched flag, downloaded flag, favourites (urls re-based on the current sub-domain), name
#     normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the page's story,
#     duration and category
import base64
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://e.ifushaar.com/"


# redirects to the current sub-domain
REDIRECTOR_URL = "https://t.ifushaar.com/"
CARD_RE = re.compile(r'(?s)<li class="video-grid"(.*?)</li>')
HASH_RE = re.compile(r"[?&]hash=([A-Za-z0-9+/=_-]+)")
# "watch-the-blacklist-2013-s05-e11-movie-translated" -> show year, season, episode
SLUG_EPISODE_RE = re.compile(r"-((?:19|20)\d{2})-s(\d+)-e(\d+)-")
YEAR_RE = re.compile(r"\s((?:19|20)\d{2})(?=\s|$)")
PREFIX_RE = re.compile(r"^\s*(?:فيلم|فلم|مسلسل|انمي|عرض)\s+")
TAIL_RE = re.compile(r"\s+(?:مترجم|مترجمة|مدبلج|مدبلجة|اون لاين|كامل)(?:\s.*)?$")
EPISODE_RE = re.compile(r"الحلقة\s*(\d+)")
SEASON_ORDINALS = [
    ("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثانى", 2), ("الثالث", 3), ("الرابع", 4), ("الخامس", 5),
    ("السادس", 6), ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
VIDEO_CATEGORIES = ("fu_video",)


def _parseTitle(title, url=""):
    # "فيلم Parasomnia 2026 مترجم" -> ("Parasomnia", "2026", 0, "")
    # "مسلسل Friends الموسم الرابع الحلقة 22 مترجم" -> ("Friends", "1994" (from the slug), 4, "22")
    title = re.sub(r"\s+", " ", title or "").strip()
    slug = SLUG_EPISODE_RE.search(url or "")
    episode = EPISODE_RE.search(title)
    season = SEASON_RE.search(title)
    name = PREFIX_RE.sub("", title)
    name = SEASON_RE.split(EPISODE_RE.split(name)[0])[0]
    name = TAIL_RE.sub("", name)
    # the last year is the release year ("Blade Runner 2049 2017")
    years = list(YEAR_RE.finditer(" " + name))
    year = years[-1] if years else None
    if year:
        name = (" " + name)[:year.start()]
    name = name.strip(" -:|")
    seasonNum = 0
    if slug:
        seasonNum = int(slug.group(2))
    elif season:
        val = season.group(1)
        seasonNum = int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)
    if slug:
        episodeNum = str(int(slug.group(3)))
    else:
        episodeNum = str(int(episode.group(1))) if episode else ""
    yearValue = year.group(1) if year else (slug.group(1) if slug else "")
    return (name or title), yearValue, seasonNum, episodeNum


class IFushaar(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "ifushaar", "cookie": "ifushaar.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/ifushaar135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("ifushaar")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def selectDomain(self):
        # t.ifushaar.com -> 301 chain -> https://<current>.ifushaar.com/home/
        if IFushaar.DOMAIN_CACHE:
            self.MAIN_URL = IFushaar.DOMAIN_CACHE
            return
        self.MAIN_URL = gettytul()
        sts, _data = self.cm.getPageCFProtection(REDIRECTOR_URL, dict(self.defaultParams))
        if sts:
            final = self.cm.meta.get("url", "")
            if re.match(r"https?://[^/]*ifushaar\.com/", final):
                self.MAIN_URL = self.cm.getBaseUrl(final)
        IFushaar.DOMAIN_CACHE = self.MAIN_URL

    def getMainUrl(self):
        if self.MAIN_URL is None:
            self.selectDomain()
        return self.MAIN_URL

    def _rebase(self, url):
        # every sub-domain of ifushaar.com (favourites, menu links on v./w.) -> the current one;
        # Arabic slugs come raw or percent-encoded -> one percent-encoded form
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if not url or re.match(r"^(?!https?:)[a-z]+:", url):
            return url  # empty, file://, data: ...
        if url.startswith("//"):
            url = "https:" + url
        match = re.match(r"https?://[^/]*ifushaar\.com/(.*)$", url)
        if match:
            url = self.getMainUrl() + match.group(1)
        elif not url.startswith("http"):
            url = self.getMainUrl() + url.lstrip("/")
        return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")

    def getFullUrl(self, url, currUrl=None):
        return self._rebase(url)

    def getFullIconUrl(self, url, currUrl=None):
        return self._rebase(url)

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    @staticmethod
    def _path(url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", urllib_unquote(url or "")).split("?")[0].rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + ("fu_list",):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("category", "") in VIDEO_CATEGORIES:
                path = self._path(cItem.get("url", ""))
                return "video:%s" % path if path else ""
        except Exception:
            printExc()
        return ""

    @staticmethod
    def _pageUrl(baseUrl, page):
        # https://site/latest/page/2/ ; search: https://site/page/2/?s=x
        if page <= 1:
            return baseUrl
        base, sep, query = baseUrl.partition("?")
        return "%spage/%d/%s%s" % (base if base.endswith("/") else base + "/", page, sep, query)

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "fu_list", "good_for_fav": True, "title": _("Latest added"), "url": self.getFullUrl("latest/")},
            {"category": "fu_list", "good_for_fav": True, "title": _("Trending"), "url": self.getFullUrl("trending/")},
            {"category": "fu_list", "good_for_fav": True, "title": _("Foreign movies"), "url": self.getFullUrl("packs/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a%d8%a9/")},
            {"category": "fu_genres", "title": _("Genres")},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listGenres(self, cItem):
        # genre links of the site menu (/archive/<genre>/)
        sts, data = self.getPage("latest/")
        if not sts:
            return
        seen = set()
        for href, label in re.findall(r'href="(https?://[^"]*ifushaar\.com/archive/[^"]+)"[^>]*>\s*([^<]+?)\s*<', data):
            url = self.getFullUrl(href)
            path = self._path(url)
            label = self.cleanHtmlStr(label)
            if label and path not in seen:
                seen.add(path)
                self.addDir({"name": "category", "category": "fu_list", "good_for_fav": True, "title": label, "url": url})

    def _addCard(self, block):
        href = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+/video/[^"]+)"')[0]
        label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<a href="[^"]+" title="([^"]+)"')[0])
        if not href or not label:
            return False
        url = self.getFullUrl(href)
        icon = self.cm.ph.getSearchGroups(block, r'data-src="([^"]+)"')[0]
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<div class="duration">([^<]*)</div>')[0])
        ago = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<div class="ago">([^<]*)</div>')[0])
        name, year, season, episode = _parseTitle(label, url)
        params = {"name": "category", "category": "fu_video", "good_for_fav": True, "url": url,
                  "icon": self.getFullIconUrl(icon) if icon else "", "desc": " | ".join(x for x in (duration, ago) if x),
                  "meta_title": name, "meta_year": year}
        if episode:
            title = "%s - %s" % (name, formatSxxExx(season or 1, episode)) if IsMediaNamingNormalized() else label
            params.update({"title": title, "s_title": name, "s_season": season or 1, "s_episode": episode, "meta_type": "tv"})
        else:
            title = ("%s (%s)" % (name, year) if year else name) if IsMediaNamingNormalized() else label
            params.update({"title": title, "meta_type": "movie"})
        self.addVideo(params)
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self.getFullUrl(cItem["url"])
        url = self._pageUrl(baseUrl, page)
        printDBG("IFushaar.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = 0
        for block in CARD_RE.findall(data):
            if self._addCard(block):
                count += 1
        pages = [int(n) for n in re.findall(r'href="[^"]*/page/(\d+)/[^"]*"', data)]
        lastPage = max(pages + [page])
        listItem = stripPagerKeys(dict(cItem), ("base_url",))
        listItem.update({"category": "fu_list", "base_url": baseUrl, "url": baseUrl})
        pageTpl = self._pageUrl(baseUrl.replace("{", "{{").replace("}", "}}"), 2).replace("/page/2/", "/page/{page}/")
        addPagingItems(self, listItem, page, bool(count) and lastPage > page, lastPage, pageTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        printDBG("IFushaar.listSearchResult [%s]" % pattern)
        cItem = dict(cItem)
        base = self.getFullUrl("?s=%s" % urllib_quote_plus(pattern))
        cItem.update({"category": "fu_list", "s_pattern": pattern, "url": base, "base_url": base})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    @staticmethod
    def _decodeHash(value):
        # base64 with "+" written as "__": "name => url" lines
        value = value.replace("__", "+")
        value += "=" * (-len(value) % 4)
        try:
            text = base64.b64decode(value)
        except Exception:
            try:
                text = base64.urlsafe_b64decode(value)
            except Exception:
                printExc()
                return []
        if not isinstance(text, str):
            text = text.decode("utf-8", "ignore")
        servers = []
        for line in text.splitlines():
            name, _sep, link = line.partition("=>")
            link = link.strip()
            if link.startswith("//"):
                link = "https:" + link
            if link.startswith("http"):
                servers.append((name.strip(), link))
        return servers

    def _albaTabs(self, playerUrl, referer):
        # the ?serv=N tabs of an albaplayer page -> [(name, tab url)]
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=referer)
        sts, data = self.cm.getPage(playerUrl, params)
        if not sts:
            return []
        tabs, seen = [], set()
        for href, name in re.findall(r"""<a[^>]+href=["']([^"']*\?serv=\d+)["'][^>]*>([^<]*)</a>""", data):
            href = href.replace("&amp;", "&")
            if href not in seen:
                seen.add(href)
                tabs.append((self.cleanHtmlStr(name), href))
        return tabs

    def getLinksForVideo(self, cItem):
        url = self.getFullUrl(cItem.get("url", ""))
        printDBG("IFushaar.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab = []
        for name, link in self._decodeHash(self.cm.ph.getSearchGroups(data, HASH_RE.pattern)[0]):
            if "/albaplayer/" in link:
                for tabName, tab in self._albaTabs(link, url):
                    urltab.append({"name": tabName or "AlbaPlayer", "url": strwithmeta(tab, {"Referer": url}), "need_resolve": 1})
            elif self.up.checkHostSupport(link) == 1:
                urltab.append({"name": name or self.up.getHostName(link, True), "url": strwithmeta(link, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("IFushaar.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        link = videoUrl
        if "/albaplayer/" in videoUrl:
            # albaplayer tab -> the hoster iframe (the embed-code textarea repeats the player itself)
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=strwithmeta(videoUrl).meta.get("Referer", self.getMainUrl()))
            sts, data = self.cm.getPage(str(videoUrl), params)
            if not sts:
                return []
            data = re.sub(r"(?is)<textarea.*?</textarea>", "", data)
            link = ""
            for frame in re.findall(r"""<iframe[^>]+src=["']([^"']+)["']""", data):
                frame = frame.replace("&amp;", "&")
                frame = "https:" + frame if frame.startswith("//") else frame
                if "/albaplayer/" not in frame and self.cm.isValidUrl(frame):
                    link = strwithmeta(frame, {"Referer": self.cm.getBaseUrl(str(videoUrl))})
                    break
            if not link:
                SetIPTVPlayerLastHostError(_("No stream available"))
                return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(link), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        info = {}
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="details[^"]*">\s*<p[^>]*>(.*?)</p>')[0])
        minutes = self.cm.ph.getSearchGroups(data, r'itemprop="duration" content="PT(\d+)M')[0]
        if minutes:
            info["duration"] = "%s min" % minutes
        categories = ", ".join(self.cleanHtmlStr(c) for c in re.findall(r'rel="category tag">([^<]+)<', data))
        if categories:
            info["category"] = categories
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0] or \
            self.cm.ph.getSearchGroups(data, r"""background: url\('([^']+)'\)""")[0]
        return story, poster, info

    def getArticleContent(self, cItem):
        printDBG("IFushaar.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        meta = {}
        if cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem.get("meta_type") or "movie", cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        category = info.get("category")
        info.update(meta.get("info", {}))
        if category:
            info["category"] = category
        if cItem.get("meta_year") and not info.get("year"):
            info["year"] = cItem["meta_year"]
        plot = meta.get("plot", "")
        # the site's own text is a stock sentence ("مشاهدة فيلم .. مترجم كامل ..."): the plot comes first
        text = plot or story or cItem.get("desc", "")
        if plot and story and plot != story:
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
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("IFushaar.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "fu_list":
            self.listItems(self.currItem)
        elif category == "fu_genres":
            self.listGenres(self.currItem)
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
        CHostBase.__init__(self, IFushaar(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("ifushaar")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES
