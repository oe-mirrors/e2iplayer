# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 host standard
#   - 4khdhub.one (4K / 1080p WEB-DL and BluRay releases): the menus of the site (movies, series, streaming
#     platforms), anime, 4K HDR, top IMDb, search; First page / Jump / Next page with the last page
#   - movies are VIDEO rows (one link per release file); series -> seasons -> episodes, one VIDEO row per
#     episode with the files of every release (2160p / 1080p ...) as links; season packs (.zip) are left out
#   - links: greenmotors.* ad gate -> HubCloud / HubDrive -> gamerxyt "generate" page -> direct file urls
#     (FSL / FSLv2 / 10Gbps / PixelDrain), resolved here; the trailer (YouTube) and the site's VidEasy
#     player go to urlparser
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)", "Show - SxxExx"),
#     sidecar, INFO via moviemeta + the site's fields
###################################################
import codecs
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsExternalResolveAllowed, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, b64Decode, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.uhdhub_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.uhdhub_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.uhdhub_proxy))
    if config.plugins.iptvplayer.uhdhub_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.uhdhub_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://4khdhub.one/"


CARD_RE = re.compile(r'(?s)<a href="([^"]+)" class="movie-card"[^>]*>(.*?)</a>')
NAV_RE = re.compile(r'(?s)nav-link\s*dropdown-toggle">([^<]+)<.*?</ul>')
# blocks: from the start tag up to the next stop marker or the end
SEASON_RE = re.compile(r'<div class="season-item episode-item[^"]*">')
SEASON_STOPS = ('<div class="season-item episode-item', "<script")
EP_FILE_RE = re.compile(r'<div class="episode-download-item">')
EP_FILE_STOPS = ('<div class="episode-download-item">',)
FILE_RE = re.compile(r'<div class="download-item[^"]*">')
FILE_STOPS = ('<div class="download-item', '<div class="series-tab-content')
LINK_RE = re.compile(r'(?s)<a target="_blank" href="([^"]+)"[^>]*>(?:\s*<span[^>]*>)?\s*Download\s([^<&]+)')
# server links of the gamerxyt "generate direct download link" page
SERVER_TAG_RE = re.compile(r"<a([^>]*)>")
SERVER_HREF_RE = re.compile(r'href="(https?://[^"]+)"')
SERVER_LABEL_RE = re.compile(r"(?:\s*<i[^>]*>\s*</i>)?\s*(Download \[[^\]]+\]|Download File)\s*</a>")
VIDEO_CATEGORIES = ("uhd_video",)
SERIES_CATEGORIES = ("uhd_series", "uhd_season")


def _blocks(data, startRe, stops):
    # html after each start tag up to the first stop marker or the end of the data (the end without a final line
    # break, as the former lookahead regexes r'(?s)<start>(.*?)(?=stop|...|$)' did)
    blocks, pos = [], 0
    while True:
        start = startRe.search(data, pos)
        if not start:
            return blocks
        end = len(data) - 1 if data.endswith("\n") else len(data)
        for stop in stops:
            idx = data.find(stop, start.end())
            if -1 < idx < end:
                end = idx
        blocks.append(data[start.end():end])
        pos = end


def _serverLinks(data):
    # [(url, label)] of the <a ... href="http(s)://..."> Download [Server] / Download File </a> buttons
    rows, pos = [], 0
    while True:
        tag = SERVER_TAG_RE.search(data, pos)
        if not tag:
            return rows
        url, attrPos = "", 1
        while True:
            href = SERVER_HREF_RE.search(tag.group(1), attrPos)
            if not href:
                break
            url, attrPos = href.group(1), href.start() + 1
        label = SERVER_LABEL_RE.match(data, tag.end()) if url else None
        if label:
            rows.append((url, label.group(1)))
            pos = label.end()
        else:
            pos = tag.start() + 1


class UltrahdHub(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "uhdhub", "cookie": "uhdhub.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/uhdhub135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "with_metadata": True, "use_cookie": True, "load_cookie": True,
                              "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("uhdhub")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = GetAlternativeProxyUrl(config.plugins.iptvplayer.uhdhub_proxy.value)
        if proxy:
            addParams = dict(addParams, http_proxy=proxy)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def selectDomain(self):
        domains = [gettytul()]
        domain = config.plugins.iptvplayer.uhdhub_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain if domain.endswith("/") else domain + "/")
        for domain in domains:
            sts, data = self.getPage(domain)
            if sts and "4KHDHub" in data:
                self.setMainUrl(self.cm.getBaseUrl(data.meta.get("url", domain)))
                break
        if self.MAIN_URL is None:
            # fix 071026: none answered - the default address, not an alternative domain that did not answer
            self.MAIN_URL = domains[-1]

    def onMain(self, url):
        # page url without the episode marker, on the current domain (favourites survive a domain move)
        return re.sub(r"^https?://[^/]+/", self.getMainUrl(), (url or "").split("#")[0])

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + SERIES_CATEGORIES:
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
            path = self._path(cItem.get("url", ""))
            category = cItem.get("category", "")
            if not path:
                return ""
            if category == "uhd_video" and cItem.get("type") == "video":
                return "video:%s" % path
            if category == "uhd_series":
                return "series:%s" % path
            if category == "uhd_season":
                return "season:%s#s%s" % (path, cItem.get("s_season", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [{"category": "uhd_nav", "title": _("Movies"), "nav": "Movies"},
                {"category": "uhd_nav", "title": _("Series"), "nav": "Web Series"},
                {"category": "uhd_nav", "title": _("Streaming platforms"), "nav": "OTT"},
                {"category": "uhd_list", "title": _("Anime"), "url": self.getFullUrl("category/anime/")},
                {"category": "uhd_list", "title": "4K HDR", "url": self.getFullUrl("category/2160p-HDR/")},
                {"category": "uhd_list", "title": _("Top IMDb"), "url": self.getFullUrl("category/imdb/")}]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listNav(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        for match in NAV_RE.finditer(data):
            if match.group(1).strip() != cItem.get("nav"):
                continue
            for url, title in re.findall(r'href="([^"]+)" class="dropdown-item">([^<]+)<', match.group(0)):
                self.addDir({"name": "category", "category": "uhd_list", "title": self.cleanHtmlStr(title),
                             "url": self.getFullUrl(url), "good_for_fav": True})

    def _addCard(self, url, block, normalize):
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<h3 class="movie-card-title">(.*?)</h3>')[0])
        if not title:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0])
        if not title:
            return False
        year = self.cm.ph.getSearchGroups(block, r'class="movie-card-meta">\s*(\d{4})')[0]
        icon = self.cm.ph.getSearchGroups(block, r'<img src="([^"]+)"')[0]
        formats = ", ".join(self.cleanHtmlStr(f) for f in re.findall(r'class="movie-card-format">([^<]+)<', block))
        badges = " ".join(self.cleanHtmlStr(b) for b in re.findall(r'class="quality-badge[^"]*"[^>]*>([^<]+)<', block))
        desc = " | ".join(x for x in (("%s: %s" % (_("Year"), year)) if year else "", badges, formats) if x)
        params = {"name": "category", "good_for_fav": True, "url": self.getFullUrl(url), "desc": desc,
                  "icon": self.getFullIconUrl(icon) if icon else self.DEFAULT_ICON_URL, "meta_title": title, "meta_year": year}
        if "-series-" in url:
            params.update({"category": "uhd_series", "title": title, "s_title": title, "meta_type": "tv"})
            self.addDir(params)
        else:
            params.update({"category": "uhd_video", "title": "%s (%s)" % (title, year) if normalize and year else title, "meta_type": "movie"})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        url = self.onMain(cItem["url"])
        page = cItem.get("page", 1)
        printDBG("UltrahdHub.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        main = self.cm.ph.getDataBeetwenNodes(data, ("<main", ">"), ("</main", ">"), False)[1] or data
        seen = set()
        for cardUrl, block in CARD_RE.findall(main):
            if cardUrl not in seen and self._addCard(cardUrl, block, normalize):
                seen.add(cardUrl)
        pagination = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', "</div>", False)[1]
        # fix 071026: the numbered items give the last page; the search pager has only the previous / next
        # arrows (their /page/N/ is not the last page)
        hasNext = "pagination-next" in pagination
        lastPage = max([int(p) for p in re.findall(r">\s*(\d+)\s*</a>", pagination)] + [page])
        if hasNext and lastPage <= page:
            lastPage = 0
        tpl = ""
        href = self.cm.ph.getSearchGroups(pagination, r"""href=['"]([^'"]*/page/\d+/[^'"]*)['"]""")[0]
        if href:
            tpl = re.sub(r"/page/\d+/", "/page/{page}/", self.getFullUrl(href.replace("&amp;", "&")).replace("{", "{{").replace("}", "}}"), 1)
        addPagingItems(self, dict(cItem, url=url), page, bool(seen) and bool(tpl) and hasNext, lastPage, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("UltrahdHub.listSearchResult [%s]" % searchPattern)
        self.listItems(dict(cItem, category="uhd_list", url=self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern.strip()))))

    def _files(self, blocks):
        # [(label, size, file name, [(server, gate url)])] of the release files in a block
        files = []
        for item in blocks:
            links = [(server.strip(), url) for url, server in LINK_RE.findall(item)]
            if not links:
                continue
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="flex-1 text-left font-semibold">(.*?)<br')[0])
            size = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span class="badge(?:-size)?"[^>]*>\s*([\d.,]+\s*[KMGT]B)\s*<')[0])
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="(?:episode-)?file-title">(.*?)</div>')[0])
            files.append((label, size, name, links))
        return files

    def _seasons(self, data):
        # {season: {episode: [(release, size, file name, links)]}} from "Single EP's"
        seasons = {}
        block = data[data.find('id="episodes"'):] if 'id="episodes"' in data else ""
        for item in _blocks(block, SEASON_RE, SEASON_STOPS):
            header = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h3 class="episode-title">([^<]+)<')[0])
            season = int(self.cm.ph.getSearchGroups(header, r"^S(\d+)")[0] or 1)
            release = re.sub(r"^S\d+\s*", "", header)
            for epItem in _blocks(item, EP_FILE_RE, EP_FILE_STOPS):
                episode = int(self.cm.ph.getSearchGroups(epItem, r'class="badge-psa">\s*Episode-?\s*(\d+)')[0] or 0)
                links = [(server.strip(), url) for url, server in LINK_RE.findall(epItem)]
                if not episode or not links:
                    continue
                size = self.cleanHtmlStr(self.cm.ph.getSearchGroups(epItem, r'class="badge-size">([^<]+)<')[0])
                name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(epItem, r'(?s)<div class="episode-file-title">(.*?)</div>')[0])
                seasons.setdefault(season, {}).setdefault(episode, []).append((release, size, name, links))
        return seasons

    def listSeasons(self, cItem):
        printDBG("UltrahdHub.listSeasons [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(self.onMain(cItem["url"]))
        if not sts:
            return
        seasons = self._seasons(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        if len(seasons) == 1:
            season = next(iter(seasons))
            self.listEpisodes(dict(cItem, s_season=season), seasons[season])
            return
        for season in sorted(seasons):
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "good_for_fav": True, "category": "uhd_season", "s_season": season,
                           "title": "%s %d" % (_("Season"), season), "desc": "%s: %d" % (_("Episodes"), len(seasons[season]))})
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        printDBG("UltrahdHub.listEpisodes [%s]" % cItem.get("url", ""))
        season = cItem.get("s_season", 1)
        if episodes is None:
            sts, data = self.getPage(self.onMain(cItem["url"]))
            if not sts:
                return
            episodes = self._seasons(data).get(season, {})
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        pageUrl = self.onMain(cItem["url"])
        for episode in sorted(episodes):
            files = episodes[episode]
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - S%02d - %s %d" % (show, season, _("Episode"), episode)
            desc = "\n".join("%s [%s]" % (release, size) if size else release for release, size, _name, _links in files)
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "good_for_fav": True, "category": "uhd_video", "title": title, "desc": desc,
                           "url": "%s#S%02dE%02d" % (pageUrl, season, episode), "s_title": show, "s_season": season,
                           "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("UltrahdHub.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        pageUrl = self.onMain(url)
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        season, episode = cItem.get("s_season"), cItem.get("s_episode")
        if not season:
            numbers = re.search(r"#S(\d+)E(\d+)$", url)
            if numbers:
                season, episode = int(numbers.group(1)), int(numbers.group(2))
        if season and episode:
            files = self._seasons(data).get(season, {}).get(episode, [])
        else:
            block = self.cm.ph.getDataBeetwenMarkers(data, "Download Links", "</main", False)[1]
            files = self._files(_blocks(block, FILE_RE, FILE_STOPS))
        urltab = []
        for label, size, name, links in files:
            # HubDrive only wraps the same HubCloud file: offered when HubCloud is missing
            servers = dict(links)
            server = "HubCloud" if "HubCloud" in servers else links[0][0]
            title = label or name
            urltab.append({"name": "%s [%s] - %s" % (title, size, server) if size else "%s - %s" % (title, server),
                           "url": strwithmeta(servers[server], {"Referer": pageUrl}), "need_resolve": 1})
        if not (season and episode):
            tmdbId = self.cm.ph.getSearchGroups(data, r"defaultVideoId\s*=\s*'(\d+)'")[0]
            # the VidEasy player only resolves with the (opt-in) external link decryption
            if tmdbId and "videasy" in data and IsExternalResolveAllowed():
                embed = "https://player.videasy.net/movie/%s?title=%s&year=%s" % (tmdbId, urllib_quote(cItem.get("meta_title", "")), cItem.get("meta_year", ""))
                urltab.append({"name": "%s - VidEasy" % _("Watch online"), "url": embed, "need_resolve": 1})
            trailer = self.cm.ph.getSearchGroups(data, r'data-trailer-url="[^"]*youtube\.com/embed/([^"?&]+)')[0]
            if trailer:
                urltab.append({"name": "%s - YouTube" % _("Trailer"), "url": "https://www.youtube.com/watch?v=%s" % trailer, "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="mt-4">(.*?)</p>')[0])
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def _gateTarget(self, url):
        # greenmotors.* (an ad gate) -> the HubCloud / HubDrive url: s('o', ...) / ck('_wp_http_N', ...) parts
        # -> base64 -> base64 -> rot13 -> base64 -> JSON, "o" = the url in base64
        sts, data = self.getPage(url, dict(self.defaultParams, header=dict(self.HEADER, Referer=self.getMainUrl())))
        if not sts:
            return ""
        parts = "".join(a or b for a, b in re.findall(r"s\('o','([A-Za-z0-9+/=]+)'|ck\('_wp_http_\d+','([^']+)'", data))
        if not parts:
            return ""
        try:
            step = codecs.encode(b64Decode(b64Decode(parts)), "rot13")
            return b64Decode(json_loads(b64Decode(step)).get("o", "")).strip()
        except Exception:
            printExc()
        return ""

    def _followTo(self, url, referer, marker):
        # follows redirects one by one until the location carries "marker=" (the 10Gbps server)
        for _i in range(4):
            sts, data = self.getPage(url, {"header": dict(self.HEADER, Referer=referer), "no_redirection": True, "with_metadata": True})
            location = data.meta.get("location", "") if sts else ""
            if not location:
                return url
            if (marker + "=") in location:
                return urllib_unquote(location.split(marker + "=", 1)[1])
            referer, url = url, self.getFullUrl(location, url)
        return ""

    def _resolveHub(self, url):
        target = self._gateTarget(url) if "/drive/" not in url and "/file/" not in url else url
        printDBG("UltrahdHub._resolveHub gate -> [%s]" % target)
        if not self.cm.isValidUrl(target):
            return []
        sts, data = self.getPage(target)
        if not sts:
            return []
        if "/file/" in target:
            # HubDrive: the [HubCloud Server] button
            target = self.cm.ph.getSearchGroups(data, r'href="(https?://[^"]+/drive/[^"]+)"')[0]
            if not target:
                return []
            sts, data = self.getPage(target)
            if not sts:
                return []
        generate = self.cm.ph.getSearchGroups(data, r"var url = '([^']+)'")[0] or self.cm.ph.getSearchGroups(data, r'id="download" href="([^"]+)"')[0]
        if not generate:
            return []
        sts, data = self.getPage(generate, dict(self.defaultParams, header=dict(self.HEADER, Referer=target)))
        if not sts:
            return []
        urltab = []
        for link, label in _serverLinks(data):
            link = link.replace("&amp;", "&")
            server = self.cm.ph.getSearchGroups(label, r"\[(?:Server\s*:\s*)?([^\]]+)\]")[0] or label
            if "Buzz" in label:
                continue  # fuckingfast.net behind a Cloudflare check
            if "10Gbps" in label:
                link = self._followTo(link, generate, "link")
            elif "pixeldra" in link:
                # the button holds a dummy id, a script sets the real one: var pxl = "https://pixeldrain.dev/u/<id>"
                link = self.cm.ph.getSearchGroups(data, r'var pxl\s*=\s*"([^"]+)"')[0] or link
                fileId = self.cm.ph.getSearchGroups(link, r"/(?:u|file)/([A-Za-z0-9]+)")[0]
                link = "https://pixeldrain.com/api/file/%s" % fileId if fileId else ""
            if self.cm.isValidUrl(link):
                urltab.append({"name": server.strip(), "url": strwithmeta(link, {"User-Agent": self.HEADER["User-Agent"]})})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("UltrahdHub.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if "youtube.com" in videoUrl or "videasy" in videoUrl:
            urltab = self.up.getVideoLinkExt(videoUrl)
        else:
            urltab = self._resolveHub(str(videoUrl))
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(urltab, sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of a movie / series page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="mt-4">(.*?)</p>')[0])
        tagline = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="movie-tagline">(.*?)</p>')[0])
        if tagline:
            story = "%s[/br]%s" % (tagline, story) if story else tagline
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        info = {}
        for label, key in (("Director", "director"), ("Stars", "stars"), ("Release", "released"), ("Last Air", "last_air_date"),
                           ("Prints?", "quality"), ("Audios", "language"), ("Seasons", "seasons")):
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<span class="metadata-label">%s:</span>\s*<span class="metadata-value"[^>]*>(.*?)</span>' % label)[0])
            if value:
                info[key] = value
        rating = self.cm.ph.getSearchGroups(data, r'class="imdb-score">([\d.]+)<')[0]
        if rating:
            info["imdb_rating"] = rating
        genres = [self.cleanHtmlStr(g) for g in re.findall(r'<span class="badge badge-outline"><a href="/category/[^"]+">([^<]+)</a>', data)]
        genres = [g for g in genres if not re.search(r"\d{3,4}p|^(?:Movies|Series|WEB-DL|BluRay|HEVC|SDR|DV HDR|HDR|Multi Audios|Dual Audio|English|Hindi|Tamil|Telugu)$", g)]
        if genres:
            info["genres"] = ", ".join(genres)
        return story, poster, info

    def getArticleContent(self, cItem):
        printDBG("UltrahdHub.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(self.onMain(cItem.get("url", "")))
        if sts:
            story, poster, info = self._siteInfo(data)
        mediaType = cItem.get("meta_type", "") or ("tv" if "-series-" in cItem.get("url", "") else "movie")
        meta = {}
        try:
            title = cItem.get("meta_title", "") or cItem.get("s_title", "")
            if title:
                year = cItem.get("meta_year", "") or self.cm.ph.getSearchGroups(info.get("released", ""), r"\b(\d{4})\b")[0]
                meta = getMeta(mediaType, title, year)
        except Exception:
            printExc()
        meta = meta or {}
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot not in story:
            text = "%s[/br][/br]%s" % (story, plot)
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
        printDBG("UltrahdHub.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "uhd_nav":
            self.listNav(self.currItem)
        elif category == "uhd_list":
            self.listItems(self.currItem)
        elif category == "uhd_series":
            self.listSeasons(self.currItem)
        elif category == "uhd_season":
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
        CHostBase.__init__(self, UltrahdHub(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("uhdhub")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + SERIES_CATEGORIES
