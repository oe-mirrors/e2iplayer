# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - revived from Backup, ported to the python3 host standard
#   - SkStream (French movies and series, DLE site wvw.skstream.rip; the bare domain skstream.rip
#     redirects to the current mirror, favourites of an older address are moved over)
#   - movies, series, movie genres, series genres, series by version (VF / VOSTFR), by year
#   - First page / Jump / Next page on every list (/page/N/, last page known)
#   - series -> seasons -> episodes (a series with one season opens its episodes directly)
#   - search: the site's quick search (the full search is closed for guests; at most 6 hits,
#     accents are dropped from the pattern because the site finds nothing with them)
#   - links: the player list of the page (getxfield.php for movies, Season.php for episodes, loaded
#     when a link is played); embed redirectors (d000d.xyz -> doply.net) are followed -> urlparser;
#     rows of dead hosters (fembed, uptostream, vidlox, upvid, gounlimited) are left out, a netu row
#     without a video id answers "No stream available"
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)", "Show - SxxExx"),
#     sidecar, INFO via moviemeta + the site's fields
###################################################
import re
import unicodedata

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://wvw.skstream.rip/"


# the bare domain answers with a redirect to the current mirror (wvw.skstream.rip in 10.2026)
ADDRESS_FINDER = "https://skstream.rip/"
# paths of the site: urls of an older address (favourites) are moved to the current one
SITE_PATH_RE = re.compile(r"^https?://[^/]+/((?:films-en-illimite|series-en-illimite|annee)/.*)$")
SERIES_URL_RE = re.compile(r"/series-en-illimite/")
SEASON_URL_RE = re.compile(r"/(\d+)-season\.html")
EPISODE_URL_RE = re.compile(r"/(\d+)-season/(\d+)-episode\.html")
# a player row: getxfield('<id>', '<xfield>') (movies) or playEpisode(this, '<id>', '<xfield>') (episodes)
PLAYER_RE = re.compile(r"""(?:getxfield|playEpisode)\((?:this,\s*)?['"](\d+)['"],\s*['"]([^'"]+)['"]""")
LINK_TAG = "#sk="
# player rows of hosters that are gone (10.2026: fembed.one / uptostream.com do not answer, vidlox.me / upvid.co /
# gounlimited.to are parked domains, none of them is in the urlparser) -> not listed
DEAD_SERVERS = ("fembed", "uptostream", "vidlox", "upvid", "gounlimited")
VIDEO_CATEGORIES = ("skm_video",)
FOLDER_CATEGORIES = ("skm_series", "skm_season")


def _foldAccents(text):
    # "fièvre" -> "fievre": the site's quick search finds nothing for accented letters
    try:
        if not isinstance(text, type(u"")):
            text = text.decode("utf-8")
        text = u"".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    except Exception:
        printExc()
    return ensure_str(text)


class SKStream(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "s_year",
                  "nav", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "skstream", "cookie": "skstream.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/skstream135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Accept": "text/html, */*; q=0.01"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("skstream")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def selectDomain(self):
        url = ""
        sts, data = self.cm.getPage(ADDRESS_FINDER, dict(self.defaultParams))
        if sts and "skstream" in data.lower():
            url = self.cm.meta.get("url", "")
        if not self.setMainUrl(self.cm.getBaseUrl(url) if url else ""):
            self.MAIN_URL = gettytul()
        printDBG("SKStream.selectDomain [%s]" % self.MAIN_URL)

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if self.MAIN_URL is None:
            self.selectDomain()
        if addParams is None:
            addParams = dict(self.defaultParams)
        match = SITE_PATH_RE.match(baseUrl or "")
        if match:
            baseUrl = self.getMainUrl() + match.group(1)
        return self.cm.getPage(baseUrl.split("#")[0], addParams, post_data)

    def _key(self, url):
        return re.sub(r"^https?://[^/]+", "", (url or "").split("#")[0]).rstrip("/")

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("skm_list",):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            key = self._key(cItem.get("url", ""))
            if not key:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                return "video:%s" % key
            if category in FOLDER_CATEGORIES:
                return "%s:%s" % (category[4:], key)
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        films = self.getFullUrl("films-en-illimite/")
        series = self.getFullUrl("series-en-illimite/")
        menu = [
            {"category": "skm_list", "title": _("Movies"), "url": films},
            {"category": "skm_list", "title": _("Series"), "url": series},
            {"category": "skm_cats", "title": _("Genres"), "url": films, "nav": "Films"},
            {"category": "skm_cats", "title": _("Series genres"), "url": series, "nav": "gories S"},
            {"category": "skm_cats", "title": _("Version"), "url": series, "nav": "Version"},
            {"category": "skm_cats", "title": _("Year"), "url": films, "nav": "Par Ann"},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listCategories(self, cItem):
        # one menu box of the side bar ("Catégories Films", "Catégories Séries", "Par Version", "Par Année")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        marker = cItem.get("nav", "")
        for navTitle, block in re.findall(r'(?s)<div class="nav-title">(.*?)</div>\s*<ul class="nav-menu">(.*?)</ul>', data):
            if marker not in self.cleanHtmlStr(navTitle):
                continue
            for url, label in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', block):
                label = self.cleanHtmlStr(label)
                if not label:
                    continue
                params = {"name": "category", "category": "skm_list", "title": label, "url": self.getFullUrl(url), "good_for_fav": True}
                if marker == "Par Ann":
                    params["s_year"] = label
                self.addDir(params)
            break

    def _addTiles(self, data, year=""):
        normalize = IsMediaNamingNormalized()
        seen = set()
        for block in data.split('<div class="th-item">')[1:]:
            url = self.cm.ph.getSearchGroups(block, r'class="th-in[^"]*" href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="th-title[^"]*">(.*?)</div>')[0])
            if not url or not title or url in seen:
                continue
            seen.add(url)
            url = self.getFullUrl(url)
            icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
            voice = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<div class="th-meta th-voice">(.*?)</div>')[0])
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<div class="th-meta th-quality">(.*?)</div>')[0])
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon) if icon else ""}
            if SERIES_URL_RE.search(url):
                # series tiles show "Séries" instead of a version on most lists
                desc = " | ".join("%s: %s" % (label, value) for label, value in ((_("Version"), voice if voice in ("VF", "VOSTFR") else ""), (_("Quality"), quality)) if value)
                params.update({"category": "skm_series", "title": title, "desc": desc, "s_title": title,
                               "meta_type": "tv", "meta_title": title, "meta_year": ""})
                self.addDir(params)
            else:
                desc = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Version"), voice), (_("Quality"), quality)) if value)
                withYear = year and normalize and not title.endswith("(%s)" % year)
                params.update({"category": "skm_video", "title": "%s (%s)" % (title, year) if withYear else title, "desc": desc,
                               "meta_type": "movie", "meta_title": title, "meta_year": year})
                self.addVideo(params)
        return len(seen)

    def _lastPage(self, data):
        nav = self.cm.ph.getDataBeetwenMarkers(data, '<div class="navigation">', "</div>", False)[1]
        pages = [int(x) for x in re.findall(r"/page/(\d+)/", nav)]
        return max(pages) if pages else 0

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = baseUrl if page <= 1 else "%spage/%d/" % (baseUrl, page)
        printDBG("SKStream.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        content = self.cm.ph.getDataBeetwenMarkers(data, "id='dle-content'", "</main", False)[1] or data
        count = self._addTiles(content, cItem.get("s_year", ""))
        lastPage = self._lastPage(data)
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, bool(count) and lastPage > page, lastPage, baseUrl.replace("{", "{{").replace("}", "}}") + "page/{page}/")

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = _foldAccents(searchPattern.strip())
        printDBG("SKStream.listSearchResult [%s]" % pattern)
        params = dict(self.defaultParams, header=dict(self.AJAX_HEADER, Referer=self.getMainUrl()))
        sts, data = self.getPage(self.getFullUrl("engine/ajax/controller.php?mod=search"), params, {"query": pattern})
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'(?s)<a href="([^"]+)"><span class="searchheading">(.*?)</span>', data):
            title = self.cleanHtmlStr(title)
            if not title or url in seen or "do=search" in url:
                continue
            seen.add(url)
            params = {"name": "category", "good_for_fav": True, "url": self.getFullUrl(url), "title": title, "desc": ""}
            if SERIES_URL_RE.search(url):
                params.update({"category": "skm_series", "s_title": title, "meta_type": "tv", "meta_title": title, "meta_year": ""})
                self.addDir(params)
            else:
                params.update({"category": "skm_video", "meta_type": "movie", "meta_title": title, "meta_year": ""})
                self.addVideo(params)

    def _seasons(self, data):
        # [(season, url, icon)] of a series page, ascending
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="seasontab">', '<div class="g-buttons">', False)[1]
        seasons, seen = [], set()
        for url, inner in re.findall(r'(?s)<a class="th-hover" href="([^"]+)">(.*?)</a>', block):
            match = SEASON_URL_RE.search(url)
            if not match or int(match.group(1)) in seen:
                continue
            seen.add(int(match.group(1)))
            icon = self.cm.ph.getSearchGroups(inner, r'<img[^>]+src="([^"]+)"')[0]
            seasons.append((int(match.group(1)), self.getFullUrl(url), self.getFullIconUrl(icon) if icon else ""))
        return sorted(seasons)

    def listSeasons(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._seasons(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        story = self._siteInfo(data)[0]
        if len(seasons) == 1:
            season, url, icon = seasons[0]
            self.listEpisodes(dict(cItem, url=url, s_title=show, s_season=season, icon=icon or cItem.get("icon", ""), category="skm_season"))
            return
        normalize = IsMediaNamingNormalized()
        for season, url, icon in seasons:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "skm_season", "good_for_fav": True, "url": url, "s_title": show, "s_season": season,
                           "title": "%s - %s" % (show, formatSxxExx(season)) if normalize else "%s - %s %d" % (show, _("Season"), season),
                           "icon": icon or cItem.get("icon", ""), "desc": story or cItem.get("desc", ""), "meta_type": "tv"})
            self.addDir(params)

    def listEpisodes(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="saisontab">', '<div class="g-buttons">', False)[1]
        episodes = {}
        for url in re.findall(r'<a href="([^"]+-episode\.html)"', block):
            match = EPISODE_URL_RE.search(url)
            if match:
                episodes.setdefault(int(match.group(2)), self.getFullUrl(url))
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or cItem.get("title", "")
        season = cItem.get("s_season") or int(self.cm.ph.getSearchGroups(cItem["url"], SEASON_URL_RE.pattern)[0] or 1)
        for episode in sorted(episodes):
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - %s %d - %s %d" % (show, _("Season"), season, _("Episode"), episode)
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "skm_video", "good_for_fav": True, "title": title, "url": episodes[episode],
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv", "meta_title": show})
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of a movie / series / season / episode page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="fdesc[^"]*">(.*?)</div>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'(?s)<div class="fposter[^"]*">\s*<img[^>]+src="([^"]+)"')[0]
        fields = {}
        flist = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="flist">', "</ul>", False)[1]
        for label, value in re.findall(r"(?s)<li><span>(.*?)</span>(.*?)</li>", flist):
            fields[self.cleanHtmlStr(label).rstrip(":").strip().lower()] = re.sub(r"\s*,\s*", ", ", self.cleanHtmlStr(value)).strip(" ,")
        info = {}
        # ASCII parts of the labels ("Année de production", "Durée", "Réalisé par")
        for key, label in (("year", "de production"), ("duration", "dur"), ("director", "par"), ("actors", "acteurs"), ("genres", "genre")):
            for name, value in fields.items():
                if label in name and value and value != "N/A":
                    info[key] = value
        rating = self.cm.ph.getSearchGroups(data, r'(?s)class="frate-in[^"]*"[^>]*>\s*<span>([^<]+)</span>')[0].strip()
        if rating:
            info["rating"] = "%s/5 (Allocine)" % rating
        return story, poster, info

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("SKStream.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        pageUrl = self.cm.meta.get("url") or url
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="player-list">', "</ul>", False)[1]
        urltab, seen = [], set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            match = PLAYER_RE.search(item)
            if not match or match.group(2) in seen or match.group(2).split("-")[0].lower() in DEAD_SERVERS:
                continue
            seen.add(match.group(2))
            server = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span class="serv">(.*?)</span>')[0]) or match.group(2)
            lang = self.cm.ph.getSearchGroups(item, r"images/(VF|VOSTFR)\.png")[0]
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span class="pl-5">(.*?)</span>')[0])
            name = " ".join(x for x in (server, "[%s]" % lang if lang else "", quality) if x)
            linkUrl = "%s%s%s:%s" % (pageUrl.split("#")[0], LINK_TAG, match.group(1), match.group(2))
            urltab.append({"name": name, "url": strwithmeta(linkUrl, {"Referer": pageUrl}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = self._siteInfo(data)[0]
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def _embedUrl(self, linkUrl):
        # the hoster embed url of a player row: the site's ajax answers with an iframe whose src is the url
        # or javascript:window.location.replace("https://'d000d.xyz'/e/<id>")
        pageUrl, _sep, tag = linkUrl.partition(LINK_TAG)
        videoId, _sep, xfield = tag.partition(":")
        params = dict(self.defaultParams, header=dict(self.AJAX_HEADER, Referer=pageUrl))
        if EPISODE_URL_RE.search(pageUrl):
            sts, data = self.getPage(self.getFullUrl("engine/ajax/Season.php"), params, {"id": videoId, "xfield": xfield, "action": "playEpisode"})
        else:
            sts, data = self.getPage(self.getFullUrl("engine/ajax/getxfield.php?id=%s&xfield=%s&token=undefined" % (videoId, urllib_quote_plus(xfield))), params)
        if not sts:
            return ""
        src = self.cm.ph.getSearchGroups(data, r"""location\.replace\("([^"]+)"\)""")[0] or \
            self.cm.ph.getSearchGroups(data, r"""<iframe[^>]+src=['"]((?:https?:)?//[^'"]+)""")[0]
        src = src.replace("'", "").strip()
        if src.startswith("//"):
            src = "https:" + src
        # some netu rows carry no video id (embed_player.php?vid=&autoplay=no) -> nothing to play
        if re.search(r"[?&]vid=(?:&|$)", src):
            printDBG("SKStream._embedUrl: player row without a video id [%s]" % src)
            return ""
        return src

    def getVideoLinks(self, videoUrl):
        printDBG("SKStream.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if self.MAIN_URL is None:
            self.selectDomain()
        url = self._embedUrl(videoUrl) if LINK_TAG in videoUrl else videoUrl
        if not self.cm.isValidUrl(url):
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        # redirector domains of a hoster (d000d.xyz -> 302 doply.net): follow the redirects up to a known hoster
        params = dict(self.defaultParams, header=dict(self.HEADER, Referer=self.getMainUrl()), no_redirection=True)
        for _hop in range(3):
            if 1 == self.up.checkHostSupport(url):
                break
            sts, _data = self.cm.getPage(url, params)
            location = self.cm.meta.get("location", "") if sts else ""
            if not location:
                break
            url = self.cm.getFullUrl(location, url)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(url, {"Referer": self.getMainUrl()})), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("SKStream.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        mediaType = cItem.get("meta_type") or ("tv" if SERIES_URL_RE.search(cItem.get("url", "")) else "movie")
        metaTitle = cItem.get("s_title") or cItem.get("meta_title") or cItem.get("title", "")
        year = self.cm.ph.getSearchGroups(info.get("year", ""), r"((?:19|20)\d{2})")[0]
        meta = {}
        try:
            meta = getMeta(mediaType, metaTitle, cItem.get("meta_year") or year)
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = meta.get("poster") or (self.getFullIconUrl(poster) if poster else cItem.get("icon", ""))
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
        printDBG("SKStream.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "skm_cats":
            self.listCategories(self.currItem)
        elif category == "skm_list":
            self.listItems(self.currItem)
        elif category == "skm_series":
            self.listSeasons(self.currItem)
        elif category == "skm_season":
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
        CHostBase.__init__(self, SKStream(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("skstream")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in FOLDER_CATEGORIES
