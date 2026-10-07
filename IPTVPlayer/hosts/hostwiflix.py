# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 host standard
#   - Wiflix / Flemmix (French movies and series, DLE site); the current address comes from
#     wiflix-nouvelle-adresse.site (flemmix.eu in 10.2026), favourites of an older address are moved over
#   - movies, series, exclusives, movie genres, search (needs the site's "h_check" cookie)
#   - First page / Jump / Next page on every list (/page/N/) and the search (20 per page, last page known)
#   - the site lists a series per season page: season -> episodes (VF and VOSTFR links of an episode
#     on one row, keyed on "<season page>#ep<N>")
#   - links: the player buttons of the page (data-v / loadVideo()) -> urlparser
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)", "Show - SxxExx"),
#     sidecar, INFO via moviemeta + the site's fields
###################################################
import codecs
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://flemmix.eu/"


ADDRESS_FINDER = "https://www.wiflix-nouvelle-adresse.site/"
# paths of the site: urls of an older address (favourites) are moved to the current one
SITE_PATH_RE = re.compile(r"^https?://[^/]+/((?:film-en-streaming|serie-en-streaming|film-ancien|vf|vostfr|checkimg\.php)\b.*)$")
SERIES_URL_RE = re.compile(r"/serie-en-streaming/|-saison-\d+\.html", re.I)
# "Show - Saison 2": used on the title without trailing spaces
SEASON_RE = re.compile(r"-\s*Saison\s+(\d+)$", re.I)
# a player button: loadVideo('<url>') (old pages) or data-v="<base64 of the rot13 url>" (playSafe(), 10.2026)
PLAYER_RE = re.compile(r"""(?s)(?:loadVideo\(['"]([^'"]+)['"][^)]*\)"?\s*|data-v=['"]([^'"]+)['"][^>]*)>\s*<span[^>]*>(.*?)</span>""")
TILE_LABEL_RE = re.compile(r'<div class="ml-label">')
TILE_DESC_RE = re.compile(r'</div>\s*<div class="ml-desc">')
FIELD_LABEL_RE = re.compile(r'<div class="mov-label">')
FIELD_DESC_RE = re.compile(r'</div>\s*<div class="mov-desc"[^>]*>')
FIELD_END_RE = re.compile(r"</div>\s*</li>")
DIV_END_RE = re.compile(r"</div>")
SEARCH_PAGE_SIZE = 20
VIDEO_CATEGORIES = ("wfx_video",)
FOLDER_CATEGORIES = ("wfx_series",)


def _findPairs(data, headRe, midRe, tailRe):
    # re.findall(r'(?s)<head>(.*?)<mid>(.*?)<tail>') in steps: [(text between head and mid, text between mid and tail)]
    rows, pos = [], 0
    while True:
        head = headRe.search(data, pos)
        mid = head and midRe.search(data, head.end())
        tail = mid and tailRe.search(data, mid.end())
        if not tail:
            return rows
        rows.append((data[head.end():mid.start()], data[mid.end():tail.start()]))
        pos = tail.end()


def _joinCommas(text):
    # "a , b ,c" -> "a, b, c", like re.sub(r"\s*,\s*", ", ", text)
    parts = text.split(",")
    for idx in range(len(parts)):
        if idx:
            parts[idx] = parts[idx].lstrip()
        if idx < len(parts) - 1:
            parts[idx] = parts[idx].rstrip()
    return ", ".join(parts)


def _splitSeason(title):
    # "Show - Saison 2" -> ("Show", "2"), ("Show", "") without a season suffix
    match = SEASON_RE.search(title.rstrip())
    if not match:
        return title, ""
    return title[:match.start()].rstrip(), match.group(1)


class WiFlix(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "wiflix", "cookie": "wiflix.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/wiflix135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.hCheck = ""
        self.watchedHelper = IPTVWatchedHelper("wiflix")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def selectDomain(self):
        # the address finder page sends the browser on with location.href='https://<current address>'
        url = ""
        sts, data = self.cm.getPage(ADDRESS_FINDER, dict(self.defaultParams))
        if sts:
            url = self.cm.ph.getSearchGroups(data, r"""location\.href\s*=\s*['"](https?://[^'"]+)['"]""")[0]
        if not self.setMainUrl(url):
            self.MAIN_URL = gettytul()
        printDBG("WiFlix.selectDomain [%s]" % self.MAIN_URL)

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
        return re.sub(r"^https?://[^/]+", "", url or "").rstrip("/")

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("wfx_list",):
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
                return "season:%s" % key
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "wfx_list", "title": _("Movies"), "url": self.getFullUrl("film-en-streaming/")},
            {"category": "wfx_list", "title": _("Series"), "url": self.getFullUrl("serie-en-streaming/")},
            {"category": "wfx_list", "title": _("Exclusive"), "url": self.getFullUrl("film-en-streaming/exclue/")},
            {"category": "wfx_genres", "title": _("Genres")},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listGenres(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        seen = set()
        for url, label in re.findall(r'<a href="(https?://[^"]+/film-en-streaming/[a-z0-9-]+/)"[^>]*>([^<]+)</a>', data):
            label = self.cleanHtmlStr(label)
            if not label or url in seen or url.endswith("/exclue/"):
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "wfx_list", "title": label, "url": url, "good_for_fav": True})

    def _addTiles(self, data):
        normalize = IsMediaNamingNormalized()
        seen = set()
        for block in data.split('<div class="mov clearfix">')[1:]:
            url = self.cm.ph.getSearchGroups(block, r'class="mov-t nowrap" href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="mov-t nowrap" href="[^"]+">(.*?)</a>')[0])
            if not url or not title or url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
            fields = {self.cleanHtmlStr(label).rstrip(":").strip().lower(): self.cleanHtmlStr(value) for label, value in
                      _findPairs(block, TILE_LABEL_RE, TILE_DESC_RE, DIV_END_RE)}
            year = self.cm.ph.getSearchGroups(fields.get("date de sortie", ""), r"((?:19|20)\d{2})")[0]
            version = " / ".join(self.cleanHtmlStr(x) for x in re.findall(r'<span class="nbloc[12]">([^<]*)</span>', block) if x.strip())
            desc = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Version"), version)) if value)
            plot = fields.get("synopsis", "")
            if plot:
                desc = "%s[/br]%s" % (desc, plot) if desc else plot
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon) if icon else "", "desc": desc}
            if SERIES_URL_RE.search(url):
                show, season = _splitSeason(title)
                season = season or self.cm.ph.getSearchGroups(url, r"-saison-(\d+)\.html")[0] or "1"
                params.update({"category": "wfx_series", "title": title, "s_title": show, "s_season": int(season),
                               "meta_type": "tv", "meta_title": show, "meta_year": ""})
                self.addDir(params)
            else:
                withYear = year and normalize and not title.endswith("(%s)" % year)
                params.update({"category": "wfx_video", "title": "%s (%s)" % (title, year) if withYear else title,
                               "meta_type": "movie", "meta_title": title, "meta_year": year})
                self.addVideo(params)
        return len(seen)

    def _lastPage(self, data):
        nav = self.cm.ph.getDataBeetwenMarkers(data, "pagi-nav", "</div>", False)[1]
        pages = [int(x) for x in re.findall(r"(?:/page/|list_submit\()(\d+)", nav)]
        return max(pages) if pages else 0

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = baseUrl if page <= 1 else "%spage/%d/" % (baseUrl, page)
        printDBG("WiFlix.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = self._addTiles(data)
        lastPage = self._lastPage(data)
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, bool(count) and lastPage > page, lastPage, baseUrl.replace("{", "{{").replace("}", "}}") + "page/{page}/")

    def _searchCookie(self):
        # the search answers "Bot shield active." without the cookie the home page sets by script
        if not self.hCheck:
            sts, data = self.getPage(self.getMainUrl())
            numbers = re.search(r'h_check="\s*\+\s*\((\d+)\s*\+\s*(\d+)\)', data) if sts else None
            # "25" = the sum the home page used in 10.2026, when the script cannot be read
            self.hCheck = str(int(numbers.group(1)) + int(numbers.group(2))) if numbers else "25"
        return self.hCheck

    def listSearchResult(self, cItem, searchPattern, searchType):
        page = cItem.get("page", 1)
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        pageTpl = self.getFullUrl("index.php?do=search&subaction=search&search_start={page}&full_search=0&story=%s" % urllib_quote_plus(pattern))
        url = pageTpl.format(page=page)
        printDBG("WiFlix.listSearchResult [%s]" % url)
        params = dict(self.defaultParams, cookie_items={"h_check": self._searchCookie()})
        sts, data = self.getPage(url, params)
        if not sts:
            return
        found = self.cm.ph.getSearchGroups(data, r"Trouv\S*\s+(\d+)\s+r")[0]
        if found == "0":
            return
        # the result list follows a block of recommended titles, in the last "search-page" box
        start = data.rfind("search-page")
        count = self._addTiles(data[start:] if start > -1 else data)
        lastPage = (int(found or 0) + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE
        listItem = dict(cItem, category="search_next_page", s_pattern=pattern)
        addPagingItems(self, listItem, page, bool(count) and lastPage > page, lastPage, pageTpl)

    def _players(self, block):
        # [(position, player url, label)] of the player buttons in a block
        players = []
        for match in PLAYER_RE.finditer(block):
            url = match.group(1) or match.group(2)
            if match.group(2) and not re.match(r"(?:https?:)?//", url):
                # fix 071026: the site's decodeStream(): base64 -> rot13 (new player buttons, no links on any title)
                try:
                    url = codecs.encode(b64Decode(url), "rot13")
                except Exception:
                    printExc()
                    continue
            if "up4fun.top" in url:
                continue  # skipped by the site's player as well
            players.append((match.start(), url.strip(), self.cleanHtmlStr(match.group(3))))
        return players

    def _episodeBlocks(self, data):
        # {episode: [(language, player url, label)]} from the VF / VOSTFR episode tabs of a season page
        episodes = {}
        for epNum, lang, block in re.findall(r'(?s)<div class="ep(\d+)(vf|vs)"[^>]*>(.*?)</div>', data):
            for _pos, url, label in self._players(block):
                episodes.setdefault(int(epNum), []).append(("VF" if lang == "vf" else "VOSTFR", url, label))
        return episodes

    def listEpisodes(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        episodes = self._episodeBlocks(data)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        base = cItem["url"].split("#")[0]
        for episode in sorted(episodes):
            langs = []
            for lang, _url, _label in episodes[episode]:
                if lang not in langs:
                    langs.append(lang)
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - %s %d - %s %d" % (show, _("Season"), season, _("Episode"), episode)
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "wfx_video", "good_for_fav": True, "title": title, "url": "%s#ep%d" % (base, episode),
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv",
                           "desc": "%s: %s" % (_("Version"), " / ".join(langs))})
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of a movie / season page
        data = re.sub(r"(?s)<!--.*?-->", "", data)
        fields = {self.cleanHtmlStr(label).rstrip(":").strip().lower(): value for label, value in
                  _findPairs(data, FIELD_LABEL_RE, FIELD_DESC_RE, FIELD_END_RE)}
        story = self.cleanHtmlStr(fields.get("synopsis", "")) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p itemprop="description"[^>]*>(.*?)</p>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'id="posterimg" src="([^"]+)"')[0]
        info = {}
        # ASCII parts of the labels ("Durée", "Qualité", "RÉALISATEUR" lower-case differently on py2)
        for key, label in (("original_title", "titre original"), ("year", "date de sortie"), ("duration", "dur"), ("genres", "genre"),
                           ("country", "origine"), ("quality", "qualit"), ("translation", "version"), ("director", "alisateur"),
                           ("actors", "acteurs")):
            for name, value in fields.items():
                value = _joinCommas(self.cleanHtmlStr(value)).strip(" ,")
                if label in name and value:
                    info[key] = value
        return story, poster, info

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("WiFlix.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        links = []
        episode = cItem.get("s_episode")
        if episode:
            links = self._episodeBlocks(data).get(episode, [])
        else:
            block = self.cm.ph.getDataBeetwenMarkers(data, "tabs-sel linkstab", "video-box", False)[1]
            vostfr = block.find("vostfr-links")
            for pos, playerUrl, label in self._players(block):
                links.append(("VOSTFR" if -1 < vostfr < pos else "", playerUrl, label))
        urltab, seen = [], set()
        for lang, playerUrl, label in links:
            playerUrl = self.getFullUrl(playerUrl)
            if playerUrl in seen or not self.cm.isValidUrl(playerUrl):
                continue
            seen.add(playerUrl)
            name = " ".join(x for x in (self.up.getHostName(playerUrl), "[%s]" % lang if lang else "") if x)
            same = len([x for x in urltab if x["name"] == name or x["name"].startswith(name + " #")])
            if same:
                name = "%s #%d" % (name, same + 1)
            urltab.append({"name": name, "url": strwithmeta(playerUrl, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = self._siteInfo(data)[0]
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("WiFlix.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("WiFlix.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        mediaType = cItem.get("meta_type") or ("tv" if SERIES_URL_RE.search(cItem.get("url", "")) else "movie")
        metaTitle = info.get("original_title") or cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
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
        printDBG("WiFlix.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "wfx_genres":
            self.listGenres(self.currItem)
        elif category == "wfx_list":
            self.listItems(self.currItem)
        elif category == "wfx_series":
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
        CHostBase.__init__(self, WiFlix(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("wiflix")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in FOLDER_CATEGORIES
