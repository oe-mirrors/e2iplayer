# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - TorrentGalaxy (torrentgalaxy.info / torrentgalaxy.one)
#   - movies, TV, anime, documentaries: latest, most seeded, 4K / 1080p / 720p; search per category
#     (title or IMDb code); First page / Jump / Next page (50 torrents per page, the site stops at 1250)
#   - every torrent is a VIDEO row keyed on its post page; the link is the magnet of the post page
#     (quality, source, codec, size, seeders / leechers in its name), played through TorrServer
#     (urlparser parserTORRSERVER)
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx" from the release name), sidecar, INFO via moviemeta (IMDb code of the
#     post) + the site's IMDb block
###################################################
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVPlayerLastHostError, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.torrentgalaxy_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.torrentgalaxy_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.torrentgalaxy_proxy))
    if config.plugins.iptvplayer.torrentgalaxy_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.torrentgalaxy_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://torrentgalaxy.info/"


DOMAINS = ("https://torrentgalaxy.info/", "https://torrentgalaxy.one/")
PER_PAGE = 50
NO_POSTER = "/np.jpg"
# the site's categories (url key) with their moviemeta type
CATEGORIES = (("Movies", "movie"), ("TV", "tv"), ("Anime", "tv"), ("Docus", "movie"))
# category label in a list row -> moviemeta type
ROW_CATEGORIES = {"Movies": "movie", "TV": "tv", "Anime": "tv", "Documentaries": "movie", "Docus": "movie"}
POST_PATH_RE = re.compile(r"(/post-detail/[^/?#]+)")
YEAR_RE = re.compile(r"(?:^|[\s(\[])((?:19|20)\d{2})(?=$|[\s)\]])")
SXXEXX_RE = re.compile(r"\bS(\d{1,2})(?:\s?E(\d{1,3}))?(-E?\d{1,3})?\b", re.I)
QUALITY_RE = re.compile(r"\b(2160p|1080p|720p|576p|480p|4K|UHD)\b", re.I)
SOURCE_RE = re.compile(r"\b(Remux|BluRay|Blu-Ray|BDRip|BRRip|WEB-DL|WEBRip|WEB|HDTV|HDRip|DVDRip|DVD|HDCAM|CAM|TS|TC)\b", re.I)
CODEC_RE = re.compile(r"\b(x265|x264|HEVC|H\.?265|H\.?264|AVC|AV1|XviD|VP9)\b", re.I)
# add 091026: HDR / Dolby Vision / several audio languages - releases of one film otherwise got the same title
# and download file name (e.g. a MULTi and an English-only 2160p WEB-DL H265), like the language tags on Torrent9
EXTRA_RE = re.compile(r"(?<![A-Za-z0-9])(HDR10\+|HDR10|HDR|DV|MULTi|DUAL)(?![A-Za-z0-9])", re.I)
SPACE_RE = re.compile(r"\s+")
# add 091026: one spelling of the tags whatever the release writes (720P / WEBRIP / Web -> 720p / WEBRip / WEB), as on Torrent9
TAG_NAMES = dict((name.lower().replace(".", ""), name) for name in (
    "2160p", "1080p", "720p", "576p", "480p", "4K", "UHD", "Remux", "BluRay", "BDRip", "BRRip", "WEB-DL", "WEBRip", "WEB",
    "HDTV", "HDRip", "DVDRip", "DVD", "HDCAM", "CAM", "TS", "TC", "x265", "x264", "HEVC", "H265", "H264", "AVC", "AV1", "XviD", "VP9"))
TAG_NAMES["blu-ray"] = "BluRay"
# no-break / narrow no-break space as native strings: UTF-8 bytes on py2, where \s does not match them
# (a u"" class there would also hit the single byte 0xA0 inside other UTF-8 characters)
WIDE_SPACES = (" ", " ")


def _categoryTitle(key):
    return {"Movies": _("Movies"), "TV": _("TV Shows"), "Anime": _("Anime"), "Docus": _("Documentaries")}.get(key, key)


def _releaseParts(name):
    # "The.Matrix.1999.1080p.BluRay.x264-GRP" -> ("The Matrix", "1999", season, episode, isPack)
    text = re.sub(r"^\s*(?:\[[^\]]*\]\s*-?\s*)+", "", name or "")
    if text.count(".") > text.count(" "):
        text = re.sub(r"(?<=\w)[._](?=\w)", " ", text)
    cut = len(text)
    year = season = episode = ""
    pack = False
    sxe = SXXEXX_RE.search(text)
    if sxe and sxe.start() > 0:
        cut = sxe.start()
        season, episode = sxe.group(1), sxe.group(2) or ""
        pack = not episode or bool(sxe.group(3))
    quality = QUALITY_RE.search(text)
    if quality and 0 < quality.start() < cut:
        cut = quality.start()
    # fix 091026: the last year before SxxExx / quality is the release year ("Blade Runner 2049 2017 1080p")
    years = [yr for yr in YEAR_RE.finditer(text, 1) if yr.start() < cut]
    if years:
        cut = years[-1].start()
        year = years[-1].group(1)
    elif not season:
        # "Title 1080p 2023": the year after the quality
        yr = YEAR_RE.search(text, cut)
        year = yr.group(1) if yr else ""
    title = text[:cut]
    while title and (title[-1].isspace() or title[-1] in "([-|:"):
        title = title[:-1]  # trailing separators (was a backtracking regex)
    title = title.strip()
    return title, year, season, episode, pack


def _qualityLabel(name):
    # "1080p WEBRip x264" from a release name
    parts = []
    for regex in (QUALITY_RE, SOURCE_RE, CODEC_RE):
        match = regex.search(name or "")
        if match:
            parts.append(TAG_NAMES.get(match.group(1).lower().replace(".", ""), match.group(1)))
    for tag in EXTRA_RE.findall(name or ""):
        if tag.upper() not in parts:
            parts.append(tag.upper())
    return " ".join(parts)


class TorrentGalaxy(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "release", "imdb_code", "tgx_category",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "torrentgalaxy", "cookie": "torrentgalaxy.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/torrentgalaxy135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True,
                              "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("torrentgalaxy")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def _domains(self):
        domains = list(DOMAINS)
        alt = config.plugins.iptvplayer.torrentgalaxy_alt_domain.value.strip()
        if self.cm.isValidUrl(alt):
            domains.insert(0, alt.rstrip("/") + "/")
        if self.MAIN_URL in domains:
            domains.remove(self.MAIN_URL)
        return [self.MAIN_URL] + domains

    def getPage(self, url):
        # the path on the first domain that answers with a TorrentGalaxy page (the mirrors share their paths)
        params = dict(self.defaultParams)
        proxy = GetAlternativeProxyUrl(config.plugins.iptvplayer.torrentgalaxy_proxy.value)
        if proxy:
            params["http_proxy"] = proxy
        path = re.sub(r"^https?://[^/]+/", "", url)
        for domain in self._domains():
            # post urls carry the release name, also in CJK script
            sts, data = self.cm.getPageCFProtection(self.cm.iriToUri(domain + path), dict(params))
            if sts and ("torrentGalaxy" in data or "tgxtable" in data):
                if domain != self.MAIN_URL:
                    printDBG("TorrentGalaxy: domain [%s]" % domain)
                    self.MAIN_URL = domain
                return True, data
        return False, ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") == "tgx_video":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("type") == "video":
                path = POST_PATH_RE.search(cItem.get("url", ""))
                if path:
                    return "video:%s" % path.group(1).lower()
        except Exception:
            printExc()
        return ""

    def _clean(self, text):
        text = self.cleanHtmlStr(text or "")
        for space in WIDE_SPACES:
            text = text.replace(space, " ")
        return SPACE_RE.sub(" ", text).strip()

    def _rowTitle(self, release, metaType, normalize):
        # normalised name plus the quality of the release ("The Batman (2022) - 1080p WEBRip x264"), like the other
        # torrent hosts: a site lists several releases of one film; the raw release name already carries its quality
        title, year, season, episode, pack = _releaseParts(release)
        if not normalize or not title:
            return release
        if season and metaType == "tv":
            name = "%s - %s" % (title, formatSxxExx(season, None if pack else episode))
        elif year:
            name = "%s (%s)" % (title, year)
        else:
            return release
        quality = _qualityLabel(release)
        return "%s - %s" % (name, quality) if quality else name

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        for key, _metaType in CATEGORIES:
            self.addDir({"name": "category", "category": "tgx_menu", "title": _categoryTitle(key), "tgx_category": key,
                         "good_for_fav": True})
        self.listsTab(self.searchItems(), {"name": "category"})

    def listCategoryMenu(self, cItem):
        key = cItem["tgx_category"]
        base = "%sget-posts/category:%s" % (self.MAIN_URL, key)
        entries = [(_("Latest"), base + "/"), (_("Popular"), base + ":order:-se/")]
        entries += [(tag, "%s:tag:%s:order:-se/" % (base, tag)) for tag in ("4K", "1080p", "720p")]
        for title, url in entries:
            self.addDir({"name": "category", "category": "tgx_list", "title": title, "url": url, "tgx_category": key, "good_for_fav": True})

    def _parseRows(self, data):
        normalize = IsMediaNamingNormalized()
        count = 0
        for row in data.split('<div class="tgxtablerow')[1:]:
            url = self.cm.ph.getSearchGroups(row, r'''data-href=['"](/post-detail/[^'"]+)['"]''')[0]
            release = self._clean(self.cm.ph.getSearchGroups(row, r'''<a class=['"]txlight['"] title=['"]([^'"]+)['"]''')[0])
            if not url or not release:
                continue
            category = self._clean(self.cm.ph.getSearchGroups(row, r"<small>([^<]+)</small>")[0])
            title, year, season, _episode, _pack = _releaseParts(release)
            # documentary series are episodes too
            metaType = "tv" if season else ROW_CATEGORIES.get(category, "movie")
            imdb = self.cm.ph.getSearchGroups(row, r"/imdb-detail/(tt\d+)")[0]
            icon = self.cm.ph.getSearchGroups(row, r"hovercoverimg\\?'\s*src=\\?'([^'\\]+)")[0]
            if not icon or icon.endswith(NO_POSTER):
                icon = self.DEFAULT_ICON_URL
            size = self._clean(self.cm.ph.getSearchGroups(row, r'badge-secondary txlight"[^>]*>([^<]+)<')[0])
            seeds, leechers = self.cm.ph.getSearchGroups(row, r'Seeders/Leechers">\s*\[\s*<font[^>]*>\s*<b>(\d+)</b>\s*</font>\s*/\s*<font[^>]*>\s*<b>(\d+)</b>', 2)
            uploader = self._clean(self.cm.ph.getSearchGroups(row, r'class="username[^"]*">([^<]+)<')[0])
            added = self._clean(self.cm.ph.getSearchGroups(row, r"Added\s+([^<]+)</td>")[0])
            fields = [x for x in (size, "S:%s P:%s" % (seeds, leechers) if seeds else "", uploader) if x]
            descLines = [" | ".join(fields)]
            if added:
                descLines.append("%s: %s" % (_("Added"), added))
            if category:
                descLines.append("%s: %s" % (_("Category"), category))
            descLines.append(release)
            self.addVideo({"name": "category", "category": "tgx_video", "good_for_fav": True, "url": self.getFullUrl(url),
                           "title": self._rowTitle(release, metaType, normalize), "icon": icon, "desc": "[/br]".join(descLines),
                           "release": release, "imdb_code": imdb, "tgx_category": category,
                           "meta_type": metaType, "meta_title": title, "meta_year": year})
            count += 1
        return count

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        base = cItem.get("base_url") or cItem["url"].split("?")[0]
        url = base if page <= 1 else "%s?page=%d" % (base, page)
        printDBG("TorrentGalaxy.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            SetIPTVPlayerLastHostError(_("Failed to connect to host."))
            return
        count = self._parseRows(data)
        total = int(self.cm.ph.getSearchGroups(data, r"([\d,]+)\s+results")[0].replace(",", "") or 0)
        lastPage = (total + PER_PAGE - 1) // PER_PAGE
        hasNext = count > 0 and (page < lastPage or ("?page=%d" % (page + 1)) in data)
        listItem = stripPagerKeys(dict(cItem), ("base_url",))
        listItem.update({"base_url": base, "url": base})
        addPagingItems(self, listItem, page, hasNext, lastPage, base.replace("{", "{{").replace("}", "}}") + "?page={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TorrentGalaxy.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        keywords = urllib_quote(searchPattern.strip().replace(":", " "), safe="")
        category = searchType if searchType in [c[0] for c in CATEGORIES] else "Movies"
        url = "%sget-posts/keywords:%s:category:%s/" % (self.MAIN_URL, keywords, category)
        self.listItems(dict(cItem, category="tgx_list", url=url, base_url=url, page=1, tgx_category=category))

    ###################################################
    # links
    ###################################################
    def _postInfo(self, data):
        # {label: value} of the post table and the IMDb block of a post page
        info = {}
        for label, value in re.findall(r'(?s)<div class="tpcell"[^>]*>\s*<b>([^<]*)</b>\s*</div>\s*<div class="tpcell"[^>]*>(.*?)</div>', data):
            label = self._clean(label)
            if label.endswith(":"):
                label = label[:-1].rstrip()
            if label and ":" not in label:
                info[label] = self._clean(value)
        for label, value in re.findall(r'(?s)<div class="tpcell" id="imdb"><strong>([^<:]+):</strong></div>\s*<div class="tpcell" id="imdb">(.*?)</div>', data):
            info["imdb " + self._clean(label)] = self._clean(value).rstrip(", ")
        info["seeds"] = self.cm.ph.getSearchGroups(data, r"Seeds&nbsp;<span[^>]*>(\d+)<")[0]
        info["leechers"] = self.cm.ph.getSearchGroups(data, r"Leechers&nbsp;<span[^>]*>(\d+)<")[0]
        info["imdb_code"] = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
        info["poster"] = self.cm.ph.getSearchGroups(data, r'class="coverpic[^"]*"[^>]+data-src="([^"]+)"')[0]
        return info

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("TorrentGalaxy.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            # fix 091026: a message like the other torrent hosts - unless the Cloudflare check already left one
            if not GetIPTVPlayerLastHostError(clear=False):
                SetIPTVPlayerLastHostError(_("Failed to connect to host."))
            return []
        magnet = ph.unescape(self.cm.ph.getSearchGroups(data, r'''href=['"](magnet:\?xt=urn:btih:[^'"]+)['"]''')[0])
        if not magnet:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        info = self._postInfo(data)
        release = cItem.get("release", "") or cItem.get("title", "")
        health = "S:%s P:%s" % (info["seeds"], info["leechers"]) if info["seeds"] else ""
        name = " - ".join(x for x in (_qualityLabel(release), info.get("Total Size", ""), health) if x)
        icon = cItem.get("icon", "")
        if not icon.startswith("http"):
            icon = info["poster"] if info["poster"] and not info["poster"].endswith(NO_POSTER) else ""
        urltab = [{"name": name or release, "url": strwithmeta(magnet, {"title": release, "icon": icon}), "need_resolve": 1}]
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info.get("imdb Plot", "")))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("TorrentGalaxy.getVideoLinks [%s]" % videoUrl)
        if videoUrl.startswith("magnet:?") or self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("TorrentGalaxy.getArticleContent [%s]" % cItem.get("url", ""))
        site = {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            site = self._postInfo(data)
        info = {}
        for key, label in (("genres", "imdb Genre"), ("duration", "imdb Runtime"), ("language", "Language"),
                           ("category", "Category"), ("released", "Added")):
            if site.get(label):
                info[key] = site[label].split(" - ")[0].strip()
        if site.get("Total Size"):
            info["quality"] = " - ".join(x for x in (_qualityLabel(cItem.get("release", "")), site["Total Size"]) if x)
        if cItem.get("meta_year"):
            info["year"] = cItem["meta_year"]
        imdb = cItem.get("imdb_code") or site.get("imdb_code", "")
        metaType = cItem.get("meta_type", "movie")
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(metaType, imdb)
            if not meta and cItem.get("meta_title"):
                meta = getMeta(metaType, cItem["meta_title"], cItem.get("meta_year", ""))
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        story = site.get("imdb Plot", "")
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (plot, story)
        if cItem.get("release") and cItem["release"] not in text:
            text = "%s[/br][/br]%s" % (text, cItem["release"]) if text else cItem["release"]
        poster = site.get("poster", "")
        icon = meta.get("poster") or (poster if poster and not poster.endswith(NO_POSTER) else "") or cItem.get("icon", "")
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
        printDBG("TorrentGalaxy.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "tgx_menu":
            self.listCategoryMenu(self.currItem)
        elif category == "tgx_list":
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, TorrentGalaxy(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("torrentgalaxy")

    def getSearchTypes(self):
        return [(_categoryTitle(key), key) for key, _metaType in CATEGORIES]

    def withArticleContent(self, cItem):
        return cItem.get("category") == "tgx_video"
