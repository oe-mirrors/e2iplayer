# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 framework / host standard
#   - asia2tv.pw (WordPress, Arabic-subtitled Asian drama): latest episodes, drama sections, status lists,
#     Asian movies, genre / country filter (the site's POST filter redirects to /genre|country/<slug>/)
#     and search, all with First page / Jump / Next page
#   - drama -> episodes (local paging over 100); movies and episodes are VIDEO rows keyed on their page
#     url; the episode page's server list (data-server) is handed to urlparser
#   - watched flag (series:/video: page-url keys), downloaded flag, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the drama page's fields
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
    return "https://ww1.asia2tv.pw/"


LOCAL_PAGE_SIZE = 100
SEASON_ORDINALS = [
    ("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثانى", 2), ("الثالث", 3), ("الرابع", 4), ("الخامس", 5),
    ("السادس", 6), ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:الموسم\s*(\d+|%s)|Season\s*(\d+))" % "|".join(o[0] for o in SEASON_ORDINALS), re.I)
EPISODE_RE = re.compile(r"الحلقة\s*(\d+)")
MOVIE_WORD_RE = re.compile(r"(?:^|\s)فيلم(?=\s|$)")
LATIN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 :;,.!?'&()\-]*[A-Za-z0-9)!?]|[A-Za-z]")
# "<span>يعرف ايضا بـ:</span>..." rows of the drama page -> INFO keys
INFO_FIELDS = (("alternate_title", "يعرف ايضا"), ("episodes", "عدد الحلقات"), ("country", "البلد"), ("released", "موعد البث"))


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1) or m.group(2)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


def _latinTitle(title):
    # "مصيدة فئران Mousetrap" -> "Mousetrap" (the metadata services know the original title)
    parts = [p.strip() for p in LATIN_RE.findall(title or "") if re.search(r"[A-Za-z]", p)]
    return max(parts, key=len) if parts else ""


GENRE_HREF_RE = re.compile(r'href="([^"]*)"')
LINK_TEXT_RE = re.compile(r"(?s)[^>]*>(.*?)</a>")
ROLE_WORD = "في دور"


def _genreLinks(block):
    # texts of the <a href="../genre/..">..</a> links, scanned like a regex findall
    out = []
    pos = 0
    while True:
        m = GENRE_HREF_RE.search(block, pos)
        if not m:
            break
        pos = m.start() + 1
        if "/genre/" in m.group(1)[1:-1]:
            t = LINK_TEXT_RE.match(block, m.end())
            if t:
                out.append(t.group(1))
                pos = t.end()
    return out


def _skipSpace(text, i):
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _actorNames(content):
    # "<p>Name : في دور Role" lines -> names, scanned line by line (whitespace may run over line ends)
    out = []
    pos = lineStart = 0
    n = len(content)
    while True:
        if lineStart >= pos:
            j = _skipSpace(content, lineStart)
            k = j + 3 if content.startswith("<p>", j) else j
            e = k
            while e < n and content[e] not in "<:\n":
                e += 1
            name = q = None
            if e > k:
                q = max(k + 1, len(content[:e].rstrip()))
                name = content[k:q]
                q = _skipSpace(content, q)
            elif k == j and j < n and content[j] == ":":
                # only whitespace before the colon: the name is its last char that is no newline
                ws = content[lineStart:j].replace("\n", "")
                if ws:
                    name, q = ws[-1], j
            if name is not None and q < n and content[q] == ":":
                r = _skipSpace(content, q + 1)
                if content.startswith(ROLE_WORD, r):
                    out.append(name)
                    pos = r + len(ROLE_WORD)
        nl = content.find("\n", lineStart)
        if nl < 0:
            return out
        lineStart = nl + 1


class Asia2TV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "series_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "asia2tv", "cookie": "asia2tv.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/asia2tv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

        def lst(title, path):
            return {"category": "list_items", "title": title, "url": self.getFullUrl(path)}

        self.MENU = [
            lst(_("Latest episodes"), "/category/new-episodes/"),
            lst(_("Asian TV series"), "/category/asian-drama/"),
            lst(_("Korean dramas"), "/category/asian-drama/korean/"),
            lst(_("Japanese dramas"), "/category/asian-drama/japanese/"),
            lst(_("Chinese"), "/category/asian-drama/chinese-taiwanese/"),
            lst(_("Thai"), "/category/asian-drama/thai/"),
            lst(_("TV Shows"), "/category/asian-drama/kshow/"),
            lst(_("Airing now"), "/status/ongoing-drama/"),
            lst(_("Completed"), "/completed-dramas/"),
            lst(_("Upcoming"), "/status/upcoming-drama/"),
            lst(_("Asian movies"), "/category/asian-movies/"),
            {"category": "a2_filters", "title": _("Genres"), "filter_key": "ofgenre"},
            {"category": "a2_filters", "title": _("Countries"), "filter_key": "ofcountry"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("asia2tv")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

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
        # domain independent identity of a page
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("a2_video", "a2_series"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    @staticmethod
    def _episodeTitle(show, season, episode, label):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (show, formatSxxExx(season or 1, episode))
        return label or ("%s - %s %s" % (show, _("Episode"), episode))

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"a2_video": "video", "a2_series": "series"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listFilters(self, cItem):
        key = cItem.get("filter_key", "ofgenre")
        sts, data = self.getPage(self.getFullUrl("/category/asian-drama/"))
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, "name='%s'" % key, "</select>", False)[1]
        for value, label in re.findall(r"""<option class="level-\d+" value="(\d+)">([^<]+)<""", block):
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": self.cleanHtmlStr(label),
                         "filter_key": key, "filter_value": value})

    def _filterUrl(self, cItem):
        # the site's filter form answers with a redirect to the taxonomy page (/genre/<slug>/)
        params = dict(self.defaultParams)
        params.update({"no_redirection": True, "header": dict(self.HEADER, Referer=self.getMainUrl())})
        post = {"ofcountry_operator": "and", "ofgenre_operator": "and", cItem["filter_key"]: cItem["filter_value"], "ofsubmitted": "1"}
        sts = self.getPage(self.getFullUrl("/category/asian-drama/"), params, post)[0]
        location = self.cm.meta.get("location", "") if sts else ""
        return self._canonUrl(location) if location else ""

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url", "")
        pageTpl = cItem.get("page_tpl", "")
        if not baseUrl:
            baseUrl = self._filterUrl(cItem) if cItem.get("filter_value") else self._canonUrl(cItem.get("url", ""))
            if not baseUrl:
                return
            pageTpl = baseUrl + "page/{page}/"
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("Asia2TV.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        isMovieList = "/asian-movies/" in baseUrl
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="box-item">', "</h3>"):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h3>(.*?)$")[0])
            if not href or not title:
                continue
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            year = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="post-date">([^<]*)<')[0])
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(self._quote(icon)) if icon else "",
                      "desc": "%s: %s" % (_("Year"), year) if year else ""}
            episode = EPISODE_RE.search(title)
            if episode:
                show = title[:episode.start()].strip(" -")
                season = _seasonNum(show) or 1
                params.update({"category": "a2_video", "title": self._episodeTitle(show, season, episode.group(1), title),
                               "s_title": show, "s_season": season, "s_episode": str(int(episode.group(1))),
                               "meta_type": "tv", "meta_title": _latinTitle(show) or show})
                self.addVideo(params)
            elif isMovieList or MOVIE_WORD_RE.search(title):
                clean = re.sub(r"\s+", " ", MOVIE_WORD_RE.sub(" ", " %s " % title)).strip()
                year = year or self.cm.ph.getSearchGroups(clean, r"\s\(?((?:19|20)\d\d)\)?$")[0]
                if year:
                    clean = re.sub(r"\s*\(?%s\)?\s*$" % year, "", clean)
                    params["desc"] = "%s: %s" % (_("Year"), year)
                videoTitle = title
                if normalize:
                    videoTitle = "%s (%s)" % (clean, year) if year else clean
                params.update({"category": "a2_video", "title": videoTitle,
                               "meta_type": "movie", "meta_title": _latinTitle(clean) or clean, "meta_year": year})
                self.addVideo(params)
            else:
                params.update({"category": "a2_series", "title": title, "s_title": title, "s_season": _seasonNum(title) or 1,
                               "meta_type": "tv", "meta_title": _latinTitle(title) or title, "meta_year": year})
                self.addDir(params)

        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="nav-links"', "</div>", False)[1]
        lastPage = max([int(n) for n in re.findall(r'class="page-numbers"[^>]*>(\d+)<', pager)] + [page])
        hasNext = bool(seen) and ('class="next page-numbers"' in pager or lastPage > page)
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "page_tpl": pageTpl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def listEpisodes(self, cItem):
        printDBG("Asia2TV.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="episode-list"', '<div class="clear', False)[1]
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        episodes = []
        seen = set()
        for href, label in re.findall(r'(?s)<a href="([^"]+)"[^>]*>\s*<div class="titlepisode">(.*?)</div>', block):
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(label)
            episode = EPISODE_RE.search(label)
            params = {"name": "category", "good_for_fav": True, "category": "a2_video", "url": url, "icon": cItem.get("icon", ""),
                      "desc": cItem.get("desc", ""), "series_url": cItem["url"], "meta_title": cItem.get("meta_title", show),
                      "meta_year": cItem.get("meta_year", "")}
            if episode:
                params.update({"title": self._episodeTitle(show, season, episode.group(1), label), "s_title": show, "s_season": season,
                               "s_episode": str(int(episode.group(1))), "meta_type": "tv"})
            else:
                # a movie page lists the movie itself as its only "episode"
                params.update({"title": label, "meta_type": "movie" if MOVIE_WORD_RE.search(label) else "tv"})
            episodes.append(params)
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Asia2TV.listSearchResult [%s]" % searchPattern)
        query = urllib_quote_plus(searchPattern.strip())
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "page": 1, "base_url": self.getFullUrl("/?s=%s" % query),
                      "page_tpl": self.getFullUrl("/page/{page}/?s=%s" % query)})
        cItem["url"] = cItem["base_url"]
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        block = self.cm.ph.getDataBeetwenMarkers(data, "info-detail-single", '<div class="clear', False)[1]
        info = {}
        for key, word in INFO_FIELDS:
            val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"(?s)<span>%s[^<]*</span>(.*?)</li>" % word)[0])
            if val and val != "فيلم":
                info[key] = val
        genres = [self.cleanHtmlStr(g) for g in _genreLinks(block)]
        if genres:
            info["genres"] = ", ".join(g for g in genres if g)
        content = self.cm.ph.getDataBeetwenMarkers(block, 'class="getcontent"', "</div>", False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(content, r"(?s)<p>(.*?)</p>")[0])
        actors = [self.cleanHtmlStr(a) for a in _actorNames(content)]
        if actors:
            info["actors"] = ", ".join(a.replace("-", " ") for a in actors[:8])
        poster = self.cm.ph.getSearchGroups(data, r'<div class="single-thumb-bg">\s*<img[^>]+src="([^"]+)"')[0]
        return story, self.getFullIconUrl(self._quote(poster)) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("Asia2TV.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        servers = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="server-list-menu">', "</ul>", False)[1]
        if "data-server" not in servers:
            # a movie row points at its drama page: the video page is its only "episode"
            block = self.cm.ph.getDataBeetwenMarkers(data, 'id="episode-list"', '<div class="clear', False)[1]
            href = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)"')[0]
            if href:
                sts, data = self.getPage(href)
                servers = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="server-list-menu">', "</ul>", False)[1] if sts else ""
        urltab = []
        for url, label in re.findall(r'data-server="([^"]+)"[^>]*>([^<]*)<', servers):
            url = url.replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url):
                continue
            label = self.cleanHtmlStr(label)
            hostName = self.up.getHostName(url)
            urltab.append({"name": "%s - %s" % (label, hostName) if label else hostName,
                           "url": strwithmeta(url, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        urltab.sort(key=self._linkRank)  # fix 071026: reliable servers first
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def _linkRank(self, item):
        # fix 071026: Byse/Filemoon and ok.ru first; the VidHide/FileLions/StreamWish family (LION, WISH) last:
        # its hls2 CDN (acek-cdn & co.) has edges that crawl at ~100 kbit/s and drop the connection
        parser = getattr(self.up.getParser(item["url"]), "__name__", "")
        if parser in ("parserBYSE", "parserOKRU"):
            return 0
        return 2 if parser == "parserJWPLAYER" else 1

    def getVideoLinks(self, videoUrl):
        printDBG("Asia2TV.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Asia2TV.getArticleContent [%s]" % cItem.get("url", ""))
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
        if sts and "info-detail-single" not in data:
            # an episode page: the drama page holds the information (some episodes have no drama link,
            # then the episode page's own text is all there is)
            href = self.cm.ph.getSearchGroups(data, r'class="drama-name" href="([^"]+)"')[0]
            if href:
                sts, data = self.getPage(href)
            else:
                story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="text">\s*<p>(.*?)</p>')[0])
        if sts and not story:
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
        printDBG("Asia2TV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "a2_filters":
            self.listFilters(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "a2_series":
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
        CHostBase.__init__(self, Asia2TV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("asia2tv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("a2_video", "a2_series")
