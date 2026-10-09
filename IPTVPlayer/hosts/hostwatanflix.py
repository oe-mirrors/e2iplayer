# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - watanflix.com (Syrian series, films, programmes, plays), Arabic or English site language
#   - the site plays everything from YouTube: every episode of a title page is a YouTube link
#     (protocol-relative "//www.youtube.com/watch?v=" hrefs)
#   - series / programmes / plays / genres / search -> title folder -> episodes (VIDEO rows keyed on the
#     YouTube id); films are VIDEO rows keyed on their page (in the search a film is a folder with its one
#     video: the search answer does not tell films from series)
#   - paging First page / Jump / Next page, watched flag (folder -> episode), downloaded flag, favourites,
#     name normalisation ("Show - SxxExx" from "الجزء" / "الموسم", "Title (Year)"), sidecar,
#     INFO via moviemeta + the page's year / genre / story / director / cast
import re

from Components.config import ConfigSelection, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

config.plugins.iptvplayer.watanflix_lang = ConfigSelection(default="ar", choices=[("ar", _("Arabic")), ("en", _("English"))])


def GetConfigList():
    return [getConfigListEntry(_("Language:"), config.plugins.iptvplayer.watanflix_lang)]


def gettytul():
    return "https://watanflix.com/"


SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثانى", 2), ("الثالث", 3),
    ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"\s*(?:الجزء|الموسم)\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
YOUTUBE_RE = re.compile(r"""href=["']((?:https?:)?//(?:www\.)?youtube\.com/watch\?v=[\w-]+)""")


def _splitSeason(title):
    # "حارة القبة الجزء الثالث" -> ("حارة القبة", 3)
    m = SEASON_RE.search(title or "")
    if not m:
        return title, 0
    val = m.group(1)
    num = int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)
    return (title[:m.start()] + title[m.end():]).strip(" -"), num


class WatanFlix(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "watanflix", "cookie": "watanflix.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/watanflix135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("watanflix")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _lang(self):
        return config.plugins.iptvplayer.watanflix_lang.value

    def _langUrl(self, path):
        return self.getFullUrl("/%s/%s" % (self._lang(), path))

    def _slug(self, url):
        # language independent identity of a title page: /ar/series/<slug> == /en/series/<slug>
        return re.sub(r"^https?://[^/]+/(?:ar/|en/)?", "", (url or "").split("?")[0].split("#")[0]).rstrip("/").lower()

    def _icon(self, url):
        # some cover file names contain spaces ("/images/series/taht al ard.png")
        return self.getFullIconUrl(url.strip().replace(" ", "%20")) if url else ""

    def _ytId(self, url):
        return self.cm.ph.getSearchGroups(url or "", r"[?&]v=([\w-]+)")[0]

    def _ytUrl(self, href):
        return "https://www.youtube.com/watch?v=%s" % self._ytId(href)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category == "wf_series":
                slug = self._slug(cItem.get("url", ""))
                return ("series:%s" % slug) if slug else ""
            if category == "wf_video":
                ytId = self._ytId(cItem.get("url", ""))
                if ytId:
                    return "video:yt:%s" % ytId
                slug = self._slug(cItem.get("url", ""))
                return ("video:%s" % slug) if slug else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "wf_list", "title": _("Series"), "url": self._langUrl("category/مسلسلات")},
            {"category": "wf_list", "title": _("Movies"), "url": self._langUrl("category/الأفلام"), "films": True},
            {"category": "wf_list", "title": _("Programmes"), "url": self._langUrl("category/برامج")},
            {"category": "wf_list", "title": _("Plays"), "url": self._langUrl("category/مسرحيات")},
            {"category": "wf_genres", "title": _("Genres"), "url": self._langUrl("category/مسلسلات")},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listGenres(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for href, label in re.findall(r'href="(https?://[^"]+/type/[^"]+)"[^>]*>([^<]+)<', data):
            url = self.getFullUrl(href)
            if url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "wf_list", "good_for_fav": True, "title": self.cleanHtmlStr(label), "url": url})

    def _rowParams(self, url, title, year, icon, desc, films):
        normalize = IsMediaNamingNormalized()
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc, "year": year}
        if films:
            name = "%s (%s)" % (title, year) if normalize and year else title
            params.update({"category": "wf_video", "title": name, "meta_type": "movie", "meta_title": title})
        else:
            show, season = _splitSeason(title)
            params.update({"category": "wf_series", "title": title, "s_title": show, "s_season": season or 1,
                           "meta_type": "tv", "meta_title": show})
        return params

    def _addRow(self, params):
        if params["category"] == "wf_series":
            self.addDir(params)
        else:
            self.addVideo(params)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"].split("?")[0]
        pageTpl = baseUrl + "?page={page}"
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("WatanFlix.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        films = cItem.get("films", False)
        count = 0
        for item in data.split('class="video-grid1"')[1:]:
            href = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)" class="v-link"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"<h4>(.*?)</h4>")[0])
            if not href or not title:
                continue
            year = self.cm.ph.getSearchGroups(item, r"</h4><br>\s*<span>\s*(\d{4})")[0]
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)data-content="\s*<div>(.*?)<br/>')[0].split("&lt;a ")[0])
            episodes = self.cm.ph.getSearchGroups(item, r":\s*(\d+)</i>")[0]
            icon = self.cm.ph.getSearchGroups(item, r'(?s)class="video_img">\s*<img[^>]+src="([^"]+)"')[0]
            desc = " | ".join([x for x in (year, ("%s: %s" % (_("Episodes"), episodes)) if episodes and not films else "") if x])
            desc = "%s[/br]%s" % (desc, plot) if desc and plot else (desc or plot)
            self._addRow(self._rowParams(self.getFullUrl(href), title, year, self._icon(icon), desc, films))
            count += 1
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', "</ul>", False)[1]
        lastPage = max([int(n) for n in re.findall(r"[?&]page=(\d+)", pager)] + [page])
        listItem = dict(cItem)
        listItem.update({"category": "wf_list", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, count > 0 and lastPage > page, lastPage, pageTpl)

    def _episodes(self, data):
        # [(youtube url, icon, label)] of a title page, in page order
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="slidingSeries"', 'class=" content_indent"', False)[1]
        rows = []
        seen = set()
        for item in block.split('class="item ')[1:]:
            href = YOUTUBE_RE.search(item)
            if not href:
                continue
            ytUrl = self._ytUrl(href.group(1))
            if ytUrl in seen:
                continue
            seen.add(ytUrl)
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<br/>(.*?)</p>")[0])
            rows.append((ytUrl, icon.replace("http://", "https://"), label))
        return rows

    def listEpisodes(self, cItem):
        printDBG("WatanFlix.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        normalize = IsMediaNamingNormalized()
        rows = self._episodes(data)
        if not rows:
            SetIPTVPlayerLastHostError(_("No stream available"))
        for idx, (ytUrl, icon, label) in enumerate(rows):
            num = self.cm.ph.getSearchGroups(label, r"(\d+)\s*$")[0] or str(idx + 1)
            title = "%s - %s" % (show, formatSxxExx(season, num)) if normalize else "%s - %s" % (cItem.get("title", show), label or num)
            self.addVideo({"name": "category", "category": "wf_video", "good_for_fav": True, "url": ytUrl, "title": title,
                           "icon": icon or cItem.get("icon", ""), "desc": cItem.get("desc", ""), "series_url": cItem["url"],
                           "s_title": show, "s_season": season, "s_episode": str(int(num)), "year": cItem.get("year", ""),
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("WatanFlix.listSearchResult [%s]" % searchPattern)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, **{"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"})
        sts, data = self.getPage(self._langUrl("search?q=%s" % urllib_quote_plus(searchPattern.strip())), params)
        if not sts:
            return
        try:
            rows = json_loads(data).get("data", [])
        except Exception:
            printExc()
            return
        for row in rows:
            url = row.get("url", "")
            title = self.cleanHtmlStr(row.get("title_en") if self._lang() == "en" and row.get("title_en") else row.get("title", ""))
            if url and title:
                self._addRow(self._rowParams(self.getFullUrl(url), title, "", "", "", False))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("WatanFlix.getLinksForVideo [%s]" % url)
        if self._ytId(url):
            urls = [url]
        else:
            # film page: the YouTube video(s) of its "episodes" row
            sts, data = self.getPage(url)
            urls = [row[0] for row in self._episodes(data)] if sts else []
            if not urls and sts:
                href = YOUTUBE_RE.search(self.cm.ph.getDataBeetwenMarkers(data, 'class="series_info"', 'class="clearfix"', False)[1])
                urls = [self._ytUrl(href.group(1))] if href else []
        if not urls:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        urltab = [{"name": "YouTube" if len(urls) == 1 else "YouTube %d" % (idx + 1), "url": u, "need_resolve": 1} for idx, u in enumerate(urls)]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("WatanFlix.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("WatanFlix.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("year", ""), skip)
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        pageUrl = cItem.get("series_url") or ("" if self._ytId(cItem.get("url", "")) else cItem.get("url", ""))
        sts, data = self.getPage(pageUrl) if pageUrl else (False, "")
        if sts:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, 'class="series_info"', 'class="actions"', False)[1]
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tmp, r'(?s)class="description">(.*?)</div>')[0])
            poster = self.cm.ph.getSearchGroups(tmp, r'<img src="([^"]+)"[^>]*series-img')[0]
            year = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tmp, r'(?s)class="year">(.*?)</div>')[0])
            genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(tmp, r'(?s)class="genre">(.*?)</div>')[0])
            staff = self.cm.ph.getSearchGroups(tmp, r'(?s)class=" staff">(.*?)</div>')[0]
            actors = self.cm.ph.getSearchGroups(tmp, r'(?s)class=" staff actors">(.*?)</div>')[0]
            if year:
                info["year"] = year
            if genre:
                info["genre"] = genre
            if staff:
                info["director"] = ", ".join(self.cleanHtmlStr(x) for x in re.findall(r"(?s)<a [^>]+>(.*?)</a>", staff))
            if actors:
                info["actors"] = ", ".join(self.cleanHtmlStr(x) for x in re.findall(r"(?s)<a [^>]+>(.*?)</a>", actors))
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "") or cItem.get("title", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or self._icon(poster) or cItem.get("icon", "")
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
        printDBG("WatanFlix.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "wf_genres":
            self.listGenres(self.currItem)
        elif category == "wf_list":
            self.listItems(self.currItem)
        elif category == "wf_series":
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
        CHostBase.__init__(self, WatanFlix(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("watanflix")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("wf_video", "wf_series")
