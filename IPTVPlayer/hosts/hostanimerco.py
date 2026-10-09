# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - AnimeRco (det.animerco.org, Arabic-subtitled anime, WordPress): anime, movies and search; First page /
#     Jump / Next page over /page/N/ (last page from the pagination)
#   - Cloudflare challenges every request there (curl-impersonate included, 08.10.2026): pages go through
#     getPageCFProtection (MyE2i solve on the box), covers get the same cf_clearance cookie and the User-Agent
#     that passed the check
#   - anime -> seasons -> episodes (one season: the episodes directly, local paging over 100), a movie is one
#     VIDEO row; links: the player servers of the page (data-embed-url = the site's signed /player/ page, its
#     iframe is read when a link is chosen), the hosters go to urlparser
#   - watched flag (anime -> season -> episode), downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx"), sidecar, INFO via moviemeta + the page's fields
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://det.animerco.org/"


LOCAL_PAGE_SIZE = 100
SEASON_RE = re.compile(r"(?:الموسم|season)\s*(\d+)", re.I)
EPISODE_RE = re.compile(r"(?:الحلقة|episode)\s*(\d+)", re.I)
# <li data-number='N'><a href='..' title='..'> .. <h3>الموسم 1 <span>Name</span></h3> .. </li>
LIST_ITEM_RE = re.compile(r"""(?s)<li[^>]*data-number=['"](\d+)['"][^>]*>(.*?)</li>""")
HREF_RE = r"""<a[^>]+href=['"]([^'"]+)['"]"""
# the player servers: <a .. class='btn small option' .. data-embed-url='<signed /player/ page>'> .. <span class='server'>name</span>
SERVER_RE = re.compile(r"""(?s)<a[^>]+class=['"][^'"]*\boption\b[^'"]*['"]([^>]*)>(.*?)</a>""")
# servers that can never play here: "mega" = mega.nz cloud player, "4meplayer" = JS-only app (no parser)
SKIP_SERVERS = ("mega", "4meplayer")
VIDEO_CATEGORIES = ("ar_video",)
FOLDER_CATEGORIES = ("ar_show", "ar_season")


class AnimErco(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "show_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "animerco", "cookie": "animerco.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/animerco135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("animerco")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self.getFullUrl((baseUrl or "").replace("&amp;", "&")), addParams, post_data)

    def _path(self, url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", url or "").split("?")[0].rstrip("/").lower()

    def _isSite(self, url):
        return "animerco" in self.up.getDomain(url)

    def _cfMeta(self):
        # cf_clearance + the User-Agent that passed the check, for downloads outside getPage (covers)
        meta = {"Referer": self.MAIN_URL}
        try:
            # getCookieHeader logs a traceback for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return meta

    def getFullIconUrl(self, url, currUrl=None):
        # the covers sit behind the same Cloudflare check as the pages
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        if not url.startswith("http") or not self._isSite(url):
            return url
        return strwithmeta(url, self._cfMeta())

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("ar_list",):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                return "video:%s" % path
            if category in FOLDER_CATEGORIES:
                return "folder:%s" % path
        except Exception:
            printExc()
        return ""

    def _image(self, html):
        icon = self.cm.ph.getSearchGroups(html, r"""data-src=['"]([^'"]+)['"]""")[0] or \
            self.cm.ph.getSearchGroups(html, r"""<img[^>]+src=['"]([^'"]+)['"]""")[0]
        return self.getFullIconUrl(icon) if icon and not icon.startswith("data:") else ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "ar_list", "title": _("Anime list"), "url": self.getFullUrl("/animes/")},
            {"category": "ar_list", "title": _("Movies"), "url": self.getFullUrl("/movies/")},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def _addCard(self, card):
        url = self.cm.ph.getSearchGroups(card, r'<a[^>]+href="([^"]+)"')[0]
        name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<h3[^>]*>(.*?)</h3>')[0]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'title="([^"]+)"')[0])
        # "Kimetsu no Yaiba Movie 1: Mugenjou-hen –": the dangling dash goes
        while name.endswith(("–", "-")):
            name = name[:-len("–")] if name.endswith("–") else name[:-1]
            name = name.rstrip()
        if not url or not name:
            return False
        year = self.cm.ph.getSearchGroups(self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="anime-aired"[^>]*>(.*?)</span>')[0]),
                                          r"((?:19|20)\d{2})")[0]
        kind = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="anime-type"[^>]*>(.*?)</span>')[0])
        desc = " | ".join(x for x in (kind, "%s: %s" % (_("Year"), year) if year else "") if x)
        params = {"name": "category", "good_for_fav": True, "url": url, "desc": desc, "icon": self._image(card),
                  "s_title": name, "meta_title": name, "meta_year": year}
        if "/movies/" in url:
            withYear = year and IsMediaNamingNormalized()
            params.update({"category": "ar_video", "title": "%s (%s)" % (name, year) if withYear else name, "meta_type": "movie"})
            self.addVideo(params)
        else:
            params.update({"category": "ar_show", "title": name, "meta_type": "tv"})
            self.addDir(params)
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        if "?" in baseUrl:
            base, query = baseUrl.split("?", 1)
            pageTpl = base.rstrip("/") + "/page/{page}/?" + query.replace("{", "{{").replace("}", "}}")
        else:
            pageTpl = baseUrl.replace("{", "{{").replace("}", "}}") + "page/{page}/"
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("AnimErco.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = 0
        for card in data.split("media-block")[1:]:
            if self._addCard(card.split("</article>", 1)[0]):
                count += 1
        # the pager shows only a window of page numbers (no last page): Next while it links page + 1
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', "</ul>", False)[1]
        hasNext = bool(count) and ("/page/%d/" % (page + 1)) in pager
        addPagingItems(self, dict(cItem, base_url=baseUrl, url=baseUrl), page, hasNext, 0, pageTpl)

    def _listEntries(self, data):
        # [(number, url, label, icon)] of the page's "episodes-lists" (seasons on an anime page, episodes on a season page)
        block = self.cm.ph.getDataBeetwenMarkers(data, "episodes-lists", "</ul>", False)[1]
        entries, seen = [], set()
        for number, item in LIST_ITEM_RE.findall(block):
            href = self.cm.ph.getSearchGroups(item, HREF_RE)[0]
            if not href or href in seen:
                continue
            seen.add(href)
            # "<h3>الحلقة 5 <span>One Piece</span></h3>": the label without the repeated show name
            heading = self.cm.ph.getSearchGroups(item, r"(?s)<h3[^>]*>(.*?)</h3>")[0]
            label = self.cleanHtmlStr(re.sub(r"(?s)<span.*?</span>", "", heading)) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"""title=['"]([^'"]+)['"]""")[0])
            entries.append((int(number), href, label, self._image(item)))
        entries.sort(key=lambda e: e[0])
        return entries

    @staticmethod
    def _seasonNum(entry):
        # "الموسم 2" in the label, else the list position
        match = SEASON_RE.search(entry[2])
        return int(match.group(1)) if match else entry[0]

    def listShow(self, cItem):
        # anime page: its seasons (a season page lists the episodes)
        printDBG("AnimErco.listShow [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        entries = self._listEntries(data)
        if not entries:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        seasons = [e for e in entries if "/episodes/" not in e[1]]
        if len(seasons) == 1:
            self.listSeason(dict(cItem, category="ar_season", url=seasons[0][1], show_url=cItem["url"], s_season=self._seasonNum(seasons[0])))
            return
        if not seasons:
            self._addEpisodes(cItem, entries)
            return
        for entry in seasons:
            _number, href, label, icon = entry
            season = self._seasonNum(entry)
            self.addDir({"name": "category", "category": "ar_season", "good_for_fav": True, "url": href,
                         "title": label or "%s - %s %d" % (show, _("Season"), season), "icon": icon or cItem.get("icon", ""),
                         "show_url": cItem["url"], "s_title": show, "s_season": season, "meta_type": "tv",
                         "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})

    def listSeason(self, cItem):
        printDBG("AnimErco.listSeason [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        entries = self._listEntries(data)
        if not entries:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        self._addEpisodes(cItem, entries)

    def _addEpisodes(self, cItem, entries):
        show = cItem.get("s_title") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        folderTitle = cItem.get("folder_title") or cItem.get("title", show)
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for number, href, label, icon in entries[start:start + LOCAL_PAGE_SIZE]:
            match = EPISODE_RE.search(label)
            episode = int(match.group(1)) if match else number
            if IsMediaNamingNormalized():
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - %s" % (folderTitle, label or episode)
            self.addVideo({"name": "category", "category": "ar_video", "good_for_fav": True, "url": href, "title": title,
                           "icon": icon or cItem.get("icon", ""), "desc": label, "show_url": cItem.get("show_url") or cItem["url"],
                           "s_title": show, "s_season": season, "s_episode": str(episode), "meta_type": "tv",
                           "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        if len(entries) > LOCAL_PAGE_SIZE:
            lastPage = (len(entries) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, folder_title=folderTitle), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        printDBG("AnimErco.listSearchResult [%s]" % pattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/?s=%s" % urllib_quote_plus(pattern))
        cItem.update({"category": "ar_list", "s_pattern": pattern, "url": base, "base_url": base})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("AnimErco.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        block = self.cm.ph.getDataBeetwenMarkers(data, "server-list", "</ul>", False)[1] or data
        urltab, seen = [], set()
        for attrs, body in SERVER_RE.findall(block):
            # the signed player page of the site (valid some hours), resolved in getVideoLinks
            embed = self.cm.ph.getSearchGroups(attrs, r"""data-embed-url=['"]([^'"]+)['"]""")[0].replace("&amp;", "&")
            if not self.cm.isValidUrl(embed) or embed in seen:
                continue
            seen.add(embed)
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r"""(?s)class=['"]server['"]>(.*?)</span>""")[0]) or self.cleanHtmlStr(body)
            name = name or self.up.getDomain(embed)
            if name.split(" ")[0].lower() in SKIP_SERVERS:
                continue
            # a server name can repeat ("Michi FHD" twice): number them
            same = len([1 for link in urltab if link["name"].split(" #")[0] == name])
            if same:
                name = "%s #%d" % (name, same + 1)
            urltab.append({"name": name, "url": strwithmeta(embed, {"Referer": url}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("AnimErco.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        link = videoUrl
        if self._isSite(videoUrl):
            # the site's /player/ page (Cloudflare) holds the hoster iframe
            referer = strwithmeta(videoUrl).meta.get("Referer", self.MAIN_URL)
            sts, data = self.getPage(str(videoUrl), dict(self.defaultParams, header=dict(self.HEADER, Referer=referer)))
            if not sts:
                return []
            # the site's own "Vidrco" player: <video src="https://video.vidrco.com/video/..?token=..&expires=.."> (MP4,
            # answers 403 without the site as Referer)
            video = self.cm.ph.getSearchGroups(data, r"""<video[^>]+src=['"]([^'"]+)['"]""")[0].replace("&#038;", "&").replace("&amp;", "&")
            if self.cm.isValidUrl(video):
                header = {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
                return decorateResolvedLinkItems([{"name": "mp4", "url": strwithmeta(video, header)}], sidecar)
            link = self.cm.ph.getSearchGroups(data, r"""<iframe[^>]+src=['"]([^'"]+)['"]""")[0].replace("&#038;", "&").replace("&amp;", "&")
            if link.startswith("//"):
                link = "https:" + link
            if not self.cm.isValidUrl(link):
                SetIPTVPlayerLastHostError(_("No stream available"))
                return []
            link = strwithmeta(link, {"Referer": self.MAIN_URL})
        if self.up.getDomain(link).endswith("videas.fr"):
            return decorateResolvedLinkItems(self._videas(link), sidecar)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(link), sidecar)

    def _videas(self, embedUrl):
        # app.videas.fr/embed/media/<uid>/ (not in urlparser's hostMap, 08.10.2026): the page's media JSON
        # carries "src": "https://cdn.videas.fr/../playlist.m3u8" (360p-1080p, plain HLS)
        sts, data = self.cm.getPage(embedUrl, {"header": dict(self.HEADER, Referer=self.MAIN_URL)})
        if not sts:
            return []
        hls = self.cm.ph.getSearchGroups(data, r'''"src":\s*"(https?://[^"]+\.m3u8[^"]*)"''')[0] or \
            self.cm.ph.getSearchGroups(data, r'''href="(https?://[^"]+\.m3u8[^"]*)"''')[0]
        if not hls:
            return []
        header = {"Referer": "https://app.videas.fr/", "User-Agent": self.HEADER.get("User-Agent")}
        return getDirectM3U8Playlist(strwithmeta(hls, header), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of an anime / movie page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="content"[^>]*>\s*<p>(.*?)</p>')[0])
        info = {}
        rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="score[^"]*"[^>]*>(.*?)</span>')[0])
        if rating:
            info["rating"] = rating
        genres = self.cm.ph.getSearchGroups(data, r'(?s)<div class="genres">(.*?)</div>')[0]
        genres = [self.cleanHtmlStr(g) for g in re.findall(r"(?s)<a[^>]*>(.*?)</a>", genres)]
        if genres:
            info["genres"] = ", ".join(g for g in genres if g)
        # <ul class="media-info"><li> label: <span>value</span> </li> ..
        fields = {}
        mediaInfo = self.cm.ph.getSearchGroups(data, r'(?s)<ul class="media-info">(.*?)</ul>')[0]
        for label, value in re.findall(r"(?s)<li>\s*([^<:]+?)\s*:(.*?)</li>", mediaInfo):
            fields[label.strip()] = self.cleanHtmlStr(value)
        for key, label in (("type", "النوع"), ("seasons", "المواسم"), ("episodes", "الحلقات"), ("released", "بداية العرض"),
                           ("duration", "مدة الحلقة"), ("age_limit", "التقييم"), ("quality", "الجودة")):
            if fields.get(label):
                info[key] = fields[label]
        year = self.cm.ph.getSearchGroups(info.get("released", ""), r"((?:19|20)\d{2})")[0]
        if year:
            info["year"] = year
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, poster, info

    def getArticleContent(self, cItem):
        printDBG("AnimErco.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("show_url") or cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        title = cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(cItem.get("meta_type") or "tv", title, cItem.get("meta_year") or info.get("year", ""),
                           () if isLatinTitle(title) else LATIN_ONLY)
        except Exception:
            printExc()
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        info.update(dict((k, v) for k, v in siteInfo.items() if k in ("age_limit", "seasons", "episodes", "quality")))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = (self.getFullIconUrl(poster) if poster else "") or meta.get("poster") or cItem.get("icon", "")
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
        printDBG("AnimErco.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "ar_list":
            self.listItems(self.currItem)
        elif category == "ar_show":
            self.listShow(self.currItem)
        elif category == "ar_season":
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
        CHostBase.__init__(self, AnimErco(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("animerco")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
