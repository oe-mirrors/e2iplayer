# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 framework / host standard
#   - asia4arabs.com (WordPress "DramaLand" theme, Arabic-subtitled Asian series, movies and anime):
#     per section latest / A-Z / top rated and the site's genre / country filters, search (?s=, article
#     cards skipped), all with First page / Jump / Next page
#   - series / anime -> episodes (<slug>/?episode=N, local paging over 100); movies and episodes are VIDEO
#     rows keyed on their page url; the page's server buttons (data-server-url) are handed to urlparser
#   - watched flag (series:/video: page-url keys), downloaded flag, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the page's detail rows
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://asia4arabs.com/"


LOCAL_PAGE_SIZE = 100
# "المسلسل الصيني حب لأجلك / Love for You 2026 مترجم" -> prefix, Arabic name, English name, year
PREFIX_RE = re.compile(r"^\s*(?:مشاهدة\s+(?:وتحميل\s+)?)?(?:(?:الفيلم|المسلسل)\s+ال\S+|فيلم|مسلسل|أنمي|انمي)\s+")
# the title is cut before the first of these words (and the spaces in front of it)
TAIL_WORD_RE = re.compile(r"(?:مترجمة|مترجم|مدبلج)(?=\s|$)")
YEAR_RE = re.compile(r"\(?\b((?:19|20)\d\d)\b\)?")
TITLE_SPLIT_RE = re.compile(r"\s[/–]\s+|[{}]")
LIST_SEP_RE = re.compile(r",\s*")
LATIN_RE = re.compile(r"[A-Za-z]")
SEASON_RE = re.compile(r"(?:Season\s*(\d+)|الموسم\s*(\d+))", re.I)
# "<span class="detail-key">🗣️ اللغة:</span><span class="detail-val">..." -> INFO keys
DETAIL_KEYS = (("language", "اللغة"), ("subtitles", "الترجمة"), ("translation", "المترجم"), ("genres", "النوع"),
               ("country", "الدولة"), ("director", "المخرج"), ("production", "المنتج"), ("writer", "كاتب العمل"),
               ("duration", "المدة"))


def _splitTitle(raw):
    # -> (display name, year): the English name when the site gives one, else the Arabic one
    title = raw or ""
    m = TAIL_WORD_RE.search(title)
    if m:
        title = title[:m.start()].rstrip()
    title = PREFIX_RE.sub("", title)
    year = ""
    m = YEAR_RE.search(title)
    if m:
        year = m.group(1)
        title = title[:m.start()].rstrip() + " " + title[m.end():]
    parts = [p.strip(" -–{}") for p in TITLE_SPLIT_RE.split(title)]
    parts = [re.sub(r"\s+", " ", p) for p in parts if p]
    if not parts:
        return raw, year
    english = [p for p in parts if LATIN_RE.search(p)]
    return (english[-1] if english else parts[0]), year


def _joinList(text):
    # "a ,b , c" -> "a, b, c": the spaces around each comma are dropped
    parts = LIST_SEP_RE.split(text)
    return ", ".join([p.rstrip() for p in parts[:-1]] + parts[-1:])


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    return int(m.group(1) or m.group(2)) if m else 0


class Asia4Arabs(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "series_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "asia4arabs", "cookie": "asia4arabs.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/asia4arabs135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "a4_section", "title": _("Series"), "url": self.getFullUrl("/series/")},
            {"category": "a4_section", "title": _("Movies"), "url": self.getFullUrl("/movies/")},
            {"category": "a4_section", "title": _("Anime"), "url": self.getFullUrl("/anime/")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("asia4arabs")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self._canonUrl(baseUrl), addParams, post_data)

    @staticmethod
    def _quote(url):
        try:
            return urllib_quote(urllib_unquote(url.replace("&amp;", "&").replace("&#038;", "&")), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _canonUrl(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return self._quote(url)

    def _path(self, url):
        # domain independent identity of a page (the ?episode=N query stays)
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def _icon(self, item):
        # fix 071026: lazy-loaded posters (src = data: placeholder, the image in data-src) - the old
        # pattern stopped at the placeholder src and left every card without a cover
        tag = self.cm.ph.getSearchGroups(item, r"(<img[^>]+>)")[0]
        for attr in ("data-src", "data-lazy-src", "src"):
            url = self.cm.ph.getSearchGroups(tag, r'\s%s="([^"]+)"' % attr)[0]
            if url and not url.startswith("data:"):
                return self.getFullIconUrl(self._quote(url))
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("a4_video", "a4_series"):
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
            prefix = {"a4_video": "video", "a4_series": "series"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listSection(self, cItem):
        base = cItem["url"]
        for title, url in ((_("Recently added"), base), (_("Alphabetically"), base + "?orderby=title"),
                           (_("Top rated"), base + "?orderby=meta_value_num")):
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": url})
        # only the filters the section really offers (anime has no country filter)
        sts, data = self.getPage(base)
        if not sts:
            return
        for key, title in (("genre", _("Genres")), ("country", _("Countries"))):
            if self._filterLinks(data, key):
                self.addDir({"name": "category", "category": "a4_filters", "title": title, "url": base, "filter_key": key})

    def _filterLinks(self, data, key):
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="%sFilter"' % key, "</div>", False)[1]
        # "all" (no query) = the plain section
        return [(href, label) for href, label in re.findall(r'(?s)<a href="([^"]+)"[^>]*>(.*?)</a>', block) if "?" in href]

    def listFilters(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for href, label in self._filterLinks(data, cItem.get("filter_key", "")):
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": self.cleanHtmlStr(label),
                         "url": self._canonUrl(href)})

    def _pageTpl(self, url):
        # /series/?genre=x -> /series/page/{page}/?genre=x ; /?s=q -> /page/{page}/?s=q
        base, sep, query = url.partition("?")
        if not base.endswith("/"):
            base += "/"
        return base + "page/{page}/" + sep + query

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem.get("url", ""))
        pageTpl = self._pageTpl(baseUrl)
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("Asia4Arabs.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, "<article", "</article>"):
            cls = self.cm.ph.getSearchGroups(item, r'<article class="([^"]+)"')[0]
            if not re.search(r"\b(?:movie|series|anime)-card\b", cls):
                continue  # blog articles in the search results
            href = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0]
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3 class="card-title">(.*?)</h3>')[0])
            if not href or not rawTitle:
                continue
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            name, year = _splitTitle(rawTitle)
            year = year or self.cm.ph.getSearchGroups(item, r"📅\s*(\d{4})")[0]
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="(?:quality-tag|badge quality-badge)">([^<]+)<')[0])
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="(?:rating-tag|badge rating-badge)">([^<]+)<')[0])
            genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="meta-(?:genre|item)">([^<]+)<')[0])
            country = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="meta-country">([^<]+)<')[0])
            desc = " | ".join(x for x in (year, quality, rating, genre, country) if x)
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self._icon(item), "desc": desc,
                      "meta_title": name, "meta_year": year}
            if "/movies/" in url:
                videoTitle = rawTitle
                if normalize:
                    videoTitle = "%s (%s)" % (name, year) if year else name
                params.update({"category": "a4_video", "meta_type": "movie", "title": videoTitle})
                self.addVideo(params)
            else:
                params.update({"category": "a4_series", "meta_type": "tv", "title": name if normalize else rawTitle,
                               "s_title": name, "s_season": _seasonNum(rawTitle) or 1})
                self.addDir(params)

        pager = self.cm.ph.getDataBeetwenMarkers(data, '<div class="archive-pagination">', "</div>", False)[1]
        if not pager:
            pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="page-numbers', "</div>", True)[1]
        lastPage = max([int(n) for n in re.findall(r'class="page-numbers"[^>]*>(\d+)<', pager)] + [page])
        hasNext = bool(seen) and ('class="next page-numbers"' in pager or lastPage > page)
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def listEpisodes(self, cItem):
        printDBG("Asia4Arabs.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="episodes-buttons-grid">', "</section>", False)[1]
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        # fix 071026: the pager rows carry the title "Next page" - keep the folder's own title for page 2+
        folderTitle = cItem.get("folder_title") or cItem.get("title", show)
        normalize = IsMediaNamingNormalized()
        episodes = []
        seen = set()
        for href, cls, num in re.findall(r'(?s)<a href="([^"]+)"\s*class="episode-number-btn([^"]*)".*?<span class="ep-number">\s*(\d+)\s*<', block):
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            title = "%s - %s" % (show, formatSxxExx(season, num)) if normalize else "%s - %s %s" % (folderTitle, _("Episode"), num)
            desc = cItem.get("desc", "")
            if "premium" in cls:
                desc = "%s | %s" % (_("Premium"), desc) if desc else _("Premium")
            episodes.append({"name": "category", "good_for_fav": True, "category": "a4_video", "url": url, "title": title,
                             "icon": cItem.get("icon", ""), "desc": desc, "series_url": cItem["url"],
                             "s_title": show, "s_season": season, "s_episode": str(int(num)),
                             "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, folder_title=folderTitle), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Asia4Arabs.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/?s=%s" % urllib_quote_plus(searchPattern.strip()))
        cItem.update({"category": "list_items", "page": 1, "url": base, "base_url": base})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        info = {}
        for key, word in DETAIL_KEYS:
            val = self.cm.ph.getSearchGroups(data, r'(?s)<span class="detail-key">[^<]*?%s\s*:\s*</span>\s*<span class="detail-val">(.*?)</span>' % word)[0]
            val = _joinList(self.cleanHtmlStr(val)).strip(" ,")
            if val:
                info[key] = val
        rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'class="[^"]*rating[^"]*">\s*⭐\s*([\d.]+)')[0])
        if rating:
            info["rating"] = rating
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="story-text-content">(.*?)</div>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(self._quote(poster)) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("Asia4Arabs.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        urltab = []
        seen = set()
        servers = re.findall(r'(?s)data-server-url="([^"]+)"\s*data-server-name="([^"]*)"', data)
        if not servers:
            servers = [(u, "") for u in re.findall(r'id="episodePlayer"[^>]*?(?:data-litespeed-src|data-src)="([^"]+)"', data)]
        for url, label in servers:
            url = url.replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            hostName = self.up.getHostName(url)
            label = self.cleanHtmlStr(label)
            urltab.append({"name": "%s - %s" % (label, hostName) if label else hostName,
                           "url": strwithmeta(url, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("This video is Premium-only content.") if "premium-lock-section" in data else _("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("Asia4Arabs.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Asia4Arabs.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                # fix 071026: Arabic-only titles -> no IMDb/Cinemeta/OMDb (they answer with unrelated English hits)
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("series_url") or cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
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
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Asia4Arabs.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "a4_section":
            self.listSection(self.currItem)
        elif category == "a4_filters":
            self.listFilters(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "a4_series":
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
        CHostBase.__init__(self, Asia4Arabs(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("asia4arabs")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("a4_video", "a4_series")
