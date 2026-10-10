# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 09.10.2026 - new host: u.3seq.cam ("قصة عشق", Turkish series with Arabic subtitles / dubbing, WordPress behind
#   Cloudflare that lets normal requests through)
#   - menus: latest episodes, series, dubbed (the site's search for "مدبلج"), movies, search - with First page /
#     Jump / Next page (the site's "/page/N/", last page from its pager)
#   - series -> seasons (the site's season tabs, loaded like its seasons.php ajax) -> episodes (ascending, local
#     paging over 100); a series with one season lists its episodes directly
#   - episodes and movies are VIDEO rows keyed on their page url; the servers of the "?do=watch" page (iframe2.php,
#     one per hoster) are resolved through urlparser only when chosen (vidsp.net: parserVIDSP)
#   - watched flag (series -> season -> episode, keys on the url path, domain independent), downloaded flag,
#     favourites, name normalisation ("Title (Year)", "Show - SxxExx", dubbed episodes "Show مدبلج - SxxExx"),
#     sidecar, INFO via moviemeta + the site's story/poster/cast; no colour codes in titles
#   - pages go through getPageCFProtection (curl-impersonate / MyE2i when Cloudflare starts asking); covers then carry
#     the cf_clearance cookie + User-Agent (getFullIconUrl); the site's ajax links point to u.3seq.com - mapped to
#     the main domain
# 10.10.2026 - a search without hits says so (the site only finds Arabic titles)
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://u.3seq.cam/"


LOCAL_PAGE_SIZE = 100
DUB_WORD = "مدبلج"
# Arabic ordinals used in season labels ("الموسم الثاني")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6), ("السادس", 6),
    ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_WORD_RE = re.compile(r"الموسم\s*(\d+|%s)?" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"^(.*?)\s*(?:الحلقة|حلقة)\s*(\d+)")
# slugs like modablaj-sevdigim-sensin-episode-s02e20
SLUG_SXE_RE = re.compile(r"[-/]s(\d{1,2})e(\d{1,4})(?:[-/]|$)", re.I)
YEAR_RE = re.compile(r"(?:^|\s)((?:19|20)\d{2})(?=\s|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|مدبلج|مدبلجة|والاخيرة|والأخيرة|الاخيرة|الأخيرة|اون لاين|أون لاين|مشاهدة|وتحميل|فيلم|مسلسل|كامل|كاملة|HD)(?=\s|$)")
# the series cards' title attribute ends with the site name
SITE_SUFFIX_RE = re.compile(r"\s*-\s*قصة عشق\s*$")
# /video/series/<slug>/ = series, /video/movies/<slug>/ = movie, /video/<slug>/ = episode (or a movie)
KIND_RE = re.compile(r"^/video/(?:(series|movies)/)?(?!(?:series|movies|author)$)[^/]+$")
# the site's own domains (its ajax answers link to u.3seq.com)
SITE_DOMAIN_RE = re.compile(r"^https?://(?:[a-z0-9-]+\.)*3seq\.(?:cam|com)(?=/|$)", re.I)


def _seasonNum(text):
    m = SEASON_WORD_RE.search(text or "")
    if not m or not m.group(1):
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


def _clean(text):
    text = JUNK_RE.sub(" ", JUNK_RE.sub(" ", SITE_SUFFIX_RE.sub("", text or "")))
    # the en dash as a whole sequence (py2 str.strip would take its single utf-8 bytes)
    return re.sub(r"\s+", " ", text.replace("–", " ")).strip(" -:|")


def _showName(text, season=0):
    # "انت من احببت 2 الموسم الثاني" -> "انت من احببت" (the season number repeated before the season word goes too)
    show = _clean(SEASON_WORD_RE.sub(" ", _clean(text)))
    if season > 1 and show.endswith(" %d" % season):
        show = show[:-len(" %d" % season)].strip()
    return show


class Seq3(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "s_dub",
                  "season_id", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "3seq", "cookie": "3seq.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/3seq135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.AJAX_URL = self.MAIN_URL + "wp-content/themes/vo2025/temp/ajax/"
        self.MENU = [
            {"category": "list_items", "title": _("Latest episodes"), "url": self.MAIN_URL + "episodes/"},
            {"category": "list_items", "title": _("Series"), "url": self.MAIN_URL + "video/series/"},
            {"category": "list_items", "title": _("Dubbed"), "url": self._searchUrl(DUB_WORD)},
            {"category": "list_items", "title": _("Movies"), "url": self.MAIN_URL + "video/movies/"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("3seq")
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
        # one form for every page url: main domain (also for u.3seq.com links), percent-encoded Arabic slugs
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

    def _kind(self, url):
        # "series" / "movies" / "video" (an episode or a movie page) / "" for anything else
        m = KIND_RE.search(self._path(url))
        if not m:
            return ""
        return m.group(1) or "video"

    def _searchUrl(self, pattern):
        return "%ssearch/%s/" % (self.MAIN_URL, urllib_quote(pattern.strip(), safe=""))

    def _icon(self, url):
        url = (url or "").strip()
        return self.getFullIconUrl(url) if url else ""

    def getFullIconUrl(self, url, currUrl=None):
        # once MyE2i stored a cf_clearance cookie (a later Cloudflare check) the cover download needs it + the
        # User-Agent that passed the check. The meta is attached here because the host base runs every icon through
        # getFullIconUrl again; covers on foreign domains stay plain
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
            if cItem.get("category") in ("3s_video", "3s_series", "3s_season"):
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
            prefix = {"3s_video": "video", "3s_series": "series", "3s_season": "season"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            if not path:
                return ""
            if prefix == "season":
                # the season tab's own id (a series post id of the site)
                return "season:%s#%s" % (path, cItem.get("season_id", ""))
            return "%s:%s" % (prefix, path)
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _episodeParams(self, label, url, icon, desc, normalize, show="", season=0, episode="", dub=None):
        m = EPISODE_RE.search(label)
        slug = SLUG_SXE_RE.search(self._path(url))
        episode = episode or (m.group(2) if m else "") or (slug.group(2) if slug else "")
        if not season:
            season = _seasonNum(label) or (int(slug.group(1)) if slug else 0) or 1
        if not show:
            show = _showName(m.group(1) if m else label, season) or _clean(label)
        if dub is None:
            dub = DUB_WORD in label or "modablaj" in self._path(url)
        title = label
        if normalize and episode:
            title = "%s - %s" % ("%s %s" % (show, DUB_WORD) if dub else show, formatSxxExx(season, episode))
        return {"name": "category", "good_for_fav": True, "category": "3s_video", "title": title, "url": url, "icon": icon, "desc": desc,
                "s_title": show, "s_season": season, "s_episode": str(int(episode)) if episode else "", "s_dub": dub,
                "meta_type": "tv", "meta_title": show}

    def _movieParams(self, label, url, icon, desc, normalize):
        title = _clean(label) or label
        year = YEAR_RE.search(title)
        year = year.group(1) if year else ""
        metaTitle = _clean(YEAR_RE.sub(" ", title)) or title
        dispTitle = label
        if normalize:
            dispTitle = "%s (%s)" % (metaTitle, year) if year else metaTitle
        return {"name": "category", "good_for_fav": True, "category": "3s_video", "title": dispTitle, "url": url, "icon": icon, "desc": desc,
                "meta_type": "movie", "meta_title": metaTitle, "meta_year": year}

    def _seriesParams(self, label, url, icon, normalize):
        season = _seasonNum(label)
        show = _showName(label, season) or _clean(label)
        # folders keep the site's label (season, subtitled / dubbed) without "مسلسل" and the site name
        title = re.sub(r"^مسلسل\s+", "", SITE_SUFFIX_RE.sub("", label)) if normalize else label
        return {"name": "category", "good_for_fav": True, "category": "3s_series", "title": title or label, "url": url, "icon": icon,
                "s_title": show, "meta_type": "tv", "meta_title": show}

    def _cards(self, data):
        # (url, label, icon, episode number) of the <article class="post"> / "postEp" cards
        out = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenNodes(data, ("<article", ">"), ("</article", ">")):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            url = self._canonUrl(href) if href else ""
            if not url or url in seen or not self._kind(url):
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="title">(.*?)</div>')[0])
            if not label:
                label = SITE_SUFFIX_RE.sub("", self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0]))
            if not label:
                continue
            number = self.cm.ph.getSearchGroups(item, r'(?s)class="episodeNum">.*?<span>[^<]*</span>\s*<span>\s*(\d+)\s*</span>')[0]
            icon = self.cm.ph.getSearchGroups(item, r'data-img="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r"background-image:\s*url\(([^)]+)\)")[0]
            out.append((url, label, self._icon(icon.strip("'\" ")), number))
        return out

    @staticmethod
    def _pageTpl(baseUrl):
        return baseUrl.split("?")[0].rstrip("/") + "/page/{page}/"

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem["url"])
        pageTpl = self._pageTpl(baseUrl)
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("Seq3.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        for url, label, icon, number in self._cards(data):
            kind = self._kind(url)
            if kind == "series":
                self.addDir(self._seriesParams(label, url, icon, normalize))
            elif kind == "video" and (number or EPISODE_RE.search(label)):
                self.addVideo(self._episodeParams(label, url, icon, "", normalize, episode=number))
            else:
                self.addVideo(self._movieParams(label, url, icon, "", normalize))

        # pager: <a href='.../page/2/'>2</a> ... <a href='.../page/N/'>&raquo;</a> (last page)
        pager = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "pagination"), ("</div", ">"), False)[1]
        pages = [int(p) for p in re.findall(r"/page/(\d+)/?['\"]", pager)]
        lastPage = max(pages) if pages else 0
        hasNext = page < lastPage
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage if hasNext or page > 1 else 0, pageTpl)

    def _episodeLinks(self, data):
        # (url, episode number) of the <a class="epNum"> links of a season (series page or seasons.php)
        out = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenNodes(data, ("<a", ">", "epNum"), ("</a", ">")):
            url = self._canonUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
            if not url or url in seen:
                continue
            seen.add(url)
            number = self.cm.ph.getSearchGroups(item, r"<span>\s*(\d+)\s*</span>")[0] or self.cm.ph.getSearchGroups(item, r'title="[^"\d]*(\d+)')[0]
            out.append((url, number))
        return out

    def _seriesPage(self, url):
        # (seasons [(season id, label)], episode links of the open season, story, poster)
        sts, data = self.getPage(url)
        if not sts:
            return None
        seasons = []
        block = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "listSeasons"), ("</ul", ">"), False)[1]
        for seasonId, label in re.findall(r'(?s)<li[^>]+data-season="(\d+)"[^>]*>(.*?)</li>', block):
            seasons.append((seasonId, self.cleanHtmlStr(label)))
        episodes = self._episodeLinks(self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "eplist"), ("</ul", ">"), False)[1])
        story, poster, _info = self._siteInfo(data)
        return seasons, episodes, story, poster

    def _addEpisodes(self, cItem, links, season, dub):
        page = cItem.get("page", 1)
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or _clean(cItem.get("title", ""))
        episodes = []
        for url, number in links:
            # raw label (naming off): "<show> - الحلقة <n>"
            label = "%s - %s %s" % (show, "الحلقة", number) if number else show
            params = self._episodeParams(label, url, cItem.get("icon", ""), cItem.get("desc", ""), normalize, show, season, number, dub)
            params["meta_title"] = cItem.get("meta_title") or show
            episodes.append(params)
        episodes.sort(key=lambda p: int(p["s_episode"]) if p["s_episode"] else 0)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSeries(self, cItem):
        printDBG("Seq3.listSeries [%s]" % cItem.get("url", ""))
        ret = self._seriesPage(cItem.get("url", ""))
        if ret is None:
            return
        seasons, episodes, story, poster = ret
        base = dict(cItem)
        base.update({"icon": cItem.get("icon") or self._icon(poster), "desc": story or cItem.get("desc", "")})
        if len(seasons) > 1:
            for seasonId, label in seasons:
                params = dict(base)
                params.update({"category": "3s_season", "title": label or seasonId, "season_id": seasonId, "page": 1,
                               "s_season": _seasonNum(label) or 1, "s_dub": DUB_WORD in label})
                self.addDir(params)
            return
        label = seasons[0][1] if seasons else cItem.get("title", "")
        dub = DUB_WORD in label or DUB_WORD in cItem.get("title", "") or "modablaj" in self._path(cItem.get("url", ""))
        self._addEpisodes(base, episodes, _seasonNum(label) or 1, dub)

    def listSeason(self, cItem):
        printDBG("Seq3.listSeason [%s] id[%s]" % (cItem.get("url", ""), cItem.get("season_id", "")))
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, **{"Referer": self._canonUrl(cItem.get("url", "")), "X-Requested-With": "XMLHttpRequest"})
        sts, data = self.getPage(self.AJAX_URL + "seasons.php?seriesID=%s" % cItem.get("season_id", ""), params)
        if not sts:
            return
        self._addEpisodes(cItem, self._episodeLinks(data), cItem.get("s_season") or 1, cItem.get("s_dub", False))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Seq3.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        baseUrl = self._searchUrl(searchPattern)
        cItem.update({"category": "list_items", "url": baseUrl, "base_url": baseUrl, "page": 1})
        self.listItems(cItem)
        if not self.currList:
            # the site only knows the Arabic titles - a Latin search term finds nothing
            SetIPTVPlayerLastHostError(_("No results found for: %s") % searchPattern)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # story, poster and the cast / genre / year ... links of a series, episode or movie page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h3 class="story">(.*?)</h3>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'(?s)<div class="poster">\s*<img[^>]+src="([^"]+)"')[0]
        info = {}
        for key, path in (("actors", "actor"), ("genres", "genre"), ("writers", "writer"), ("directors", "director"), ("year", "years"), ("country", "country")):
            names = []
            for name in re.findall(r'href="[^"]+/%s/[^"]*"[^>]*title="([^"]+)"' % path, data):
                name = self.cleanHtmlStr(name)
                if name and name not in names:
                    names.append(name)
            if names:
                info[key] = ", ".join(names[:6])
        return story, poster, info

    def getLinksForVideo(self, cItem):
        pageUrl = self._canonUrl(cItem.get("url", ""))
        printDBG("Seq3.getLinksForVideo [%s]" % pageUrl)
        if not pageUrl:
            return []
        watchUrl = pageUrl.split("?")[0] + "?do=watch"
        sts, data = self.getPage(watchUrl)
        if not sts:
            return []
        postId = self.cm.ph.getSearchGroups(data, r'vo_postID\s*=\s*"(\d+)"')[0]
        inline = self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "getEmbed"), ("</iframe", ">"))[1], r'<iframe[^>]+src="([^"]+)"')[0]
        urltab = []
        block = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "serversList"), ("</ul", ">"), False)[1]
        for item in self.cm.ph.getAllItemsBeetwenNodes(block, ("<li", ">"), ("</li", ">")):
            m = re.search(r"getServer2\(\s*this\.id\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", item)
            if not m:
                continue
            name = self.cleanHtmlStr(item) or m.group(1)
            if 'class="active"' in item and inline:
                # the open server's player is already in the page (its label is just "v" for vidsp.net)
                url = self._embedUrl(inline)
                if len(name) < 3:
                    name = self.up.getHostName(url, True)
            elif postId:
                url = strwithmeta(self.AJAX_URL + "iframe2.php?id=%s&video=%s&serverId=%s" % (postId, m.group(1), m.group(2)), {"Referer": watchUrl})
            else:
                continue
            urltab.append({"name": name, "url": url, "need_resolve": 1})
        if not urltab and inline:
            urltab.append({"name": self.up.getHostName(inline, True), "url": self._embedUrl(inline), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = self._siteInfo(data)[0]
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    def _embedUrl(self, url):
        url = url.replace("&amp;", "&").strip()
        if url.startswith("//"):
            url = "https:" + url
        return strwithmeta(url, {"Referer": self.MAIN_URL})

    def getVideoLinks(self, videoUrl):
        printDBG("Seq3.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if "/temp/ajax/iframe2.php" in videoUrl:
            # the server's player iframe, asked for only now (one request per chosen server)
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, **{"Referer": strwithmeta(videoUrl).meta.get("Referer", self.MAIN_URL), "X-Requested-With": "XMLHttpRequest"})
            sts, data = self.getPage(videoUrl, params)
            frame = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0] if sts else ""
            if not frame:
                SetIPTVPlayerLastHostError(_("No stream available"))
                return []
            videoUrl = self._embedUrl(frame)
            if not self.cm.isValidUrl(videoUrl):
                return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Seq3.getArticleContent [%s]" % cItem.get("url", ""))
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
        icon = meta.get("poster") or (self._icon(poster) if poster else "") or cItem.get("icon", "")
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
        printDBG("Seq3.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "3s_series":
            self.listSeries(self.currItem)
        elif category == "3s_season":
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
        CHostBase.__init__(self, Seq3(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("3seq")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("3s_video", "3s_series", "3s_season")
