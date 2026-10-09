# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - Anime Blkom (animeblkom.net, Arabic-subtitled anime): latest episodes, anime list, series, movies, OVA,
#     ONA, specials and search, each with First page / Jump / Next page from the site's ?page=N pager
#   - Cloudflare challenges every request there (curl-impersonate included, 08.10.2026; the Wayback Machine has
#     no page of the site after 03.2025 either): pages go through getPageCFProtection (MyE2i solve on the box),
#     covers on the site's domain get the same cf_clearance cookie and the User-Agent that passed the check
#   - anime -> episodes (VIDEO rows keyed on the /watch/ page url, local paging over 100) + its trailer; a movie
#     with one episode is one VIDEO row; the episode page's server list (data-src): the site's own player
#     (bkvideo.site, MP4 qualities played directly), the rest goes to urlparser, hosters urlparser does not know
#     are left out
#   - watched flag (anime -> episode), downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx", the season taken from "2nd Season" / "Season 2" in the name), sidecar, INFO via moviemeta
#     + the anime page's info table
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://animeblkom.net/"


LOCAL_PAGE_SIZE = 100
EPISODE_RE = re.compile(r"الحلقة\s*:?\s*(\d+)")
# "Kingdom 6th Season" / "Spy x Family Season 3": the season number for the episode names
SEASON_RE = re.compile(r"(?i)[\s:-]*(?:(\d+)(?:st|nd|rd|th) season|season ?(\d+))\b")
# <li class="episode-link ..."><a href=".../watch/<slug>/<n>"><span>الحلقة</span> .. <span>N</span></a>
EPISODE_LINK_RE = re.compile(r'(?s)<li class="episode-link[^"]*">\s*<a href="([^"]+)"[^>]*>(.*?)</a>')
# "<span class="head">label</span> <span class="info">value</span>" rows of the anime page -> INFO keys
INFO_KEYS = (("episodes", "عدد الحلقات"), ("age_limit", "التصنيف العمري"), ("released", "تاريخ الانتاج"), ("status", "حالة الأنمي"),
             ("production", "الاستديو"), ("duration", "مدة الحلقة"))
# the site's own player (08.10.2026: bkvideo.site, earlier videos.vid4up.xyz)
OWN_PLAYER_RE = re.compile(r"https?://(?:[\w-]+\.)*(?:bkvideo\.site|vid4up\.xyz)/embedvideo/")
VIDEO_CATEGORIES = ("bk_video",)
FOLDER_CATEGORIES = ("bk_show",)


def _splitSeason(name):
    # "Kage no Jitsuryokusha ni Naritakute! 2nd Season" -> ("Kage no Jitsuryokusha ni Naritakute!", 2)
    match = SEASON_RE.search(name or "")
    if not match:
        return name, 1
    base = (name[:match.start()] + name[match.end():]).strip(" :-")
    return (base or name), int(match.group(1) or match.group(2))


class AnimeBlkom(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "show_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "animeblkom", "cookie": "animeblkom.net.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/animeblkom135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("animeblkom")
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

    def getFullIconUrl(self, url, currUrl=None):
        # the covers (/uploads/...) sit behind the same Cloudflare check as the pages: their download needs the
        # cf_clearance cookie and the User-Agent that passed the check
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http") or "animeblkom" not in self.up.getDomain(url):
            return url
        meta = {"Referer": self.MAIN_URL}
        try:
            # getCookieHeader logs a traceback for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("bk_list",):
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

    @staticmethod
    def _episodeTitle(show, season, episode, label):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (show, formatSxxExx(season or 1, episode))
        return label

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "bk_latest", "title": _("Latest episodes"), "url": self.getMainUrl()},
            {"category": "bk_list", "title": _("Anime list"), "url": self.getFullUrl("/anime-list")},
            {"category": "bk_list", "title": _("Series"), "url": self.getFullUrl("/series-list")},
            {"category": "bk_list", "title": _("Movies"), "url": self.getFullUrl("/movie-list")},
            {"category": "bk_list", "title": "OVA", "url": self.getFullUrl("/ova-list")},
            {"category": "bk_list", "title": "ONA", "url": self.getFullUrl("/ona-list")},
            {"category": "bk_list", "title": _("Specials"), "url": self.getFullUrl("/special-list")},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    @staticmethod
    def _pageTpl(baseUrl):
        return baseUrl.replace("{", "{{").replace("}", "}}") + ("&" if "?" in baseUrl else "?") + "page={page}"

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        pageTpl = self._pageTpl(baseUrl)
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("AnimeBlkom.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        # lists: class="list-section grid-view", search: class="search-page-results list-section grid-view"
        start = re.search(r'<section class="[^"]*list-section', data)
        section = data[start.end():].split("</section>", 1)[0] if start else ""
        seen = set()
        for block in section.split('<div class="content">')[1:]:
            href = self.cm.ph.getSearchGroups(block, r'<div class="poster">\s*<a href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="name">(.*?)</div>')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0]).replace(" poster", "")
            if not href or not title or href in seen:
                continue
            seen.add(href)
            icon = self.cm.ph.getSearchGroups(block, r'data-original="([^"]+)"')[0]
            badges = dict((self.cleanHtmlStr(t), self.cleanHtmlStr(v)) for t, v in re.findall(r'(?s)<div class="badge [^"]*"\s*title="([^"]*)">(.*?)</div>', block))
            year = next((v for t, v in badges.items() if "سنة الانتاج" in t), "")
            episodes = next((v for t, v in badges.items() if "عدد الحلقات" in t and v != "-"), "")
            rating = self.cm.ph.getSearchGroups(block, r'(?s)fa-star-o"></i>\s*([\d.]+)')[0]
            genres = ", ".join(x for x in (self.cleanHtmlStr(g) for g in re.findall(r"(?s)<a[^>]*>(.*?)</a>",
                               self.cm.ph.getDataBeetwenMarkers(block, '<div class="genres">', "</div>", False)[1])) if x)
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="story-text">\s*<p>(.*?)</p>')[0])
            fields = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Rating"), rating), (_("Episodes"), episodes), (_("Genre"), genres)) if value)
            show, season = _splitSeason(title)
            self.addDir({"name": "category", "category": "bk_show", "good_for_fav": True, "url": href, "title": title,
                         "icon": self.getFullIconUrl(icon) if icon else "", "desc": "%s[/br]%s" % (fields, story) if fields and story else (fields or story),
                         "s_title": show, "s_season": season, "meta_type": "movie" if "/movie/" in href else "tv", "meta_title": show,
                         "meta_year": self.cm.ph.getSearchGroups(year, r"((?:19|20)\d{2})")[0]})
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination', "</ul>", False)[1]
        lastPage = max([int(n) for n in re.findall(r">\s*(\d+)\s*<", pager)] + [page])
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, bool(seen) and lastPage > page, lastPage, pageTpl)

    def listLatest(self, cItem):
        # "item episode" tiles of the home page: show, episode number, /watch/ page
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for block in data.split('<div class="item episode">')[1:]:
            href = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)"')[0]
            show = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="name">(.*?)</div>')[0])
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="episode-number">(.*?)</div>')[0])
            if not href or not show or href in seen:
                continue
            seen.add(href)
            number = EPISODE_RE.search(label) or re.search(r"/(\d+)$", href)
            episode = number.group(1) if number else ""
            name, season = _splitSeason(show)
            icon = self.cm.ph.getSearchGroups(block, r'data-src="([^"]+)"')[0]
            slug = re.search(r"/watch/([^/]+)/", href)
            self.addVideo({"name": "category", "category": "bk_video", "good_for_fav": True, "url": href,
                           "title": self._episodeTitle(name, season, episode, "%s - %s" % (show, label) if label else show),
                           "icon": self.getFullIconUrl(icon) if icon else "", "desc": label, "s_title": name, "s_season": season,
                           "s_episode": episode, "meta_type": "tv", "meta_title": name,
                           "show_url": self.getFullUrl("/anime/%s" % slug.group(1)) if slug else ""})

    def listShow(self, cItem):
        # anime page: trailer + the episode list (a movie with one episode -> one VIDEO row "Title (Year)")
        printDBG("AnimeBlkom.listShow [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        show = cItem.get("s_title") or _splitSeason(cItem.get("title", ""))[0]
        season = cItem.get("s_season", 1)
        page = cItem.get("page", 1)
        if page <= 1:
            trailer = self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenMarkers(data, 'class="modal-header"', "</iframe>", False)[1],
                                                 r"""(?:data-src|src)=['"]([^'"]+)['"]""")[0].replace("&amp;", "&")
            if self.cm.isValidUrl(trailer) and self.up.checkHostSupport(trailer) == 1:
                self.addVideo({"name": "category", "category": "bk_trailer", "good_for_fav": False, "url": trailer,
                               "title": "%s - %s" % (cItem.get("title", show), _("Trailer")), "icon": cItem.get("icon", ""), "desc": cItem.get("desc", "")})
        episodes, seen = [], set()
        for href, body in EPISODE_LINK_RE.findall(data):
            if href in seen:
                continue
            seen.add(href)
            label = re.sub(r"\s*:\s*", " ", self.cleanHtmlStr(body)).strip()
            number = EPISODE_RE.search(label) or re.search(r"/(\d+)$", href)
            episodes.append((int(number.group(1)) if number else len(episodes) + 1, href, label))
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        episodes.sort(key=lambda e: e[0])
        heading = self.cm.ph.getSearchGroups(data, r"(?s)<h1>(.*?)</h1>")[0]
        isMovie = cItem.get("meta_type") == "movie" or "(movie)" in heading.lower()
        if isMovie and len(episodes) == 1:
            year = cItem.get("meta_year") or self.cm.ph.getSearchGroups(self._infoValue(data, "تاريخ الانتاج"), r"((?:19|20)\d{2})")[0]
            withYear = year and IsMediaNamingNormalized()
            params = stripPagerKeys(dict(cItem))
            params.update({"category": "bk_video", "url": episodes[0][1], "title": "%s (%s)" % (show, year) if withYear else cItem.get("title", show),
                           "show_url": cItem["url"], "meta_type": "movie", "meta_year": year})
            self.addVideo(params)
            return
        start = (page - 1) * LOCAL_PAGE_SIZE
        for episode, href, label in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo({"name": "category", "category": "bk_video", "good_for_fav": True, "url": href, "icon": cItem.get("icon", ""),
                           "title": self._episodeTitle(show, season, episode, "%s - %s" % (cItem.get("title", show), label)),
                           "desc": cItem.get("desc", ""), "show_url": cItem["url"], "s_title": show, "s_season": season,
                           "s_episode": str(episode), "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        printDBG("AnimeBlkom.listSearchResult [%s]" % pattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/search?query=%s" % urllib_quote_plus(pattern))
        cItem.update({"category": "bk_list", "s_pattern": pattern, "url": base, "base_url": base})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("AnimeBlkom.getLinksForVideo [%s]" % url)
        if cItem.get("category") == "bk_trailer":
            return [{"name": self.up.getHostName(url), "url": url, "need_resolve": 1}]
        sts, data = self.getPage(url)
        if not sts:
            return []
        servers = self.cm.ph.getDataBeetwenMarkers(data, 'class="servers-container', 'class="video-container', False)[1] or data
        urltab, seen = [], set()
        for link, label in re.findall(r'(?s)<a\s+data-src="([^"]+)"[^>]*>(.*?)</a>', servers):
            link = link.replace("&amp;", "&").strip()
            if link.startswith("//"):
                link = "https:" + link
            if not self.cm.isValidUrl(link) or link in seen:
                continue
            seen.add(link)
            if OWN_PLAYER_RE.match(link):
                # the site's own player ("Blkom"), read in getVideoLinks
                urltab.append({"name": "Blkom", "url": strwithmeta(link, {"Referer": self.MAIN_URL}), "need_resolve": 1})
                continue
            if self.up.checkHostSupport(link) != 1:
                printDBG("AnimeBlkom.getLinksForVideo unsupported hoster [%s]" % link)
                continue
            label = self.cleanHtmlStr(label)
            hostName = self.up.getHostName(link)
            urltab.append({"name": "%s - %s" % (hostName, label) if label and label.lower() not in hostName.lower() else hostName,
                           "url": strwithmeta(link, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("AnimeBlkom.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if OWN_PLAYER_RE.match(videoUrl):
            return decorateResolvedLinkItems(self._ownPlayer(videoUrl), sidecar)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    def _ownPlayer(self, playerUrl):
        # bkvideo.site/embedvideo/<id>?s=<signed>: a video.js page with one <source> per quality (MP4), best first
        sts, data = self.cm.getPage(playerUrl, {"header": dict(self.HEADER, Referer=self.MAIN_URL)})
        if not sts:
            return []
        referer = "https://%s/" % self.up.getDomain(playerUrl)
        links = []
        for tag in re.findall(r"<source\s[^>]+>", data):
            src = self.cm.ph.getSearchGroups(tag, r'src="([^"]+)"')[0].replace("&amp;", "&")
            if not self.cm.isValidUrl(src):
                continue
            res = self.cm.ph.getSearchGroups(tag, r'res="(\d+)"')[0]
            label = self.cm.ph.getSearchGroups(tag, r'label="([^"]+)"')[0] or res
            links.append((int(res) if res else 0, {"name": label, "url": strwithmeta(src, {"Referer": referer, "User-Agent": self.HEADER.get("User-Agent")})}))
        links.sort(key=lambda x: -x[0])
        return [link for _res, link in links]

    ###################################################
    # INFO
    ###################################################
    def _infoValue(self, data, label):
        return self.cm.ph.getSearchGroups(data, r'(?s)<span class="head[^"]*">\s*%s\s*</span>\s*<span class="info[^"]*"[^>]*>(.*?)</span>' % label)[0]

    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of an anime page
        info = {}
        for key, label in INFO_KEYS:
            value = self.cleanHtmlStr(self._infoValue(data, label))
            if value and value != "-":
                info[key] = value
        year = self.cm.ph.getSearchGroups(info.get("released", ""), r"((?:19|20)\d{2})")[0]
        if year:
            info["year"] = year
        genres = ", ".join(x for x in (self.cleanHtmlStr(g) for g in re.findall(r"(?s)<a[^>]*>(.*?)</a>",
                           self.cm.ph.getDataBeetwenMarkers(data, '<p class="genres">', "</p>", False)[1])) if x)
        if genres:
            info["genres"] = genres
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="story">\s*<p>(.*?)</p>')[0]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="story">(.*?)</div>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, poster, info

    def getArticleContent(self, cItem):
        printDBG("AnimeBlkom.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("show_url") or cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        mediaType = cItem.get("meta_type") or "tv"
        title = cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(mediaType, title, cItem.get("meta_year") or info.get("year", ""), () if isLatinTitle(title) else LATIN_ONLY)
        except Exception:
            printExc()
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        info.update(dict((k, v) for k, v in siteInfo.items() if k in ("episodes", "status", "production")))
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
        printDBG("AnimeBlkom.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "bk_list":
            self.listItems(self.currItem)
        elif category == "bk_latest":
            self.listLatest(self.currItem)
        elif category == "bk_show":
            self.listShow(self.currItem)
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
        CHostBase.__init__(self, AnimeBlkom(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("animeblkom")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
