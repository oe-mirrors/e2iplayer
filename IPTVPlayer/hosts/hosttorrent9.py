# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# 08.10.2026 - Torrent9 (French torrent site; torrent9.fo / torrent9.to, torrent9.wiki as fallback)
#   - films and series: latest, most seeded, the site's sub-categories (genres, quality, VF / VOSTFR,
#     series by letter); search (films and series rows of the results); First page / Jump / Next page
#   - every torrent is a VIDEO row keyed on its details page; the link is the magnet of the details
#     page (quality, size, seeders / leechers in its name), played through TorrServer
#     (urlparser parserTORRSERVER)
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx" from the release name), sidecar, INFO via moviemeta + the site's synopsis
###################################################
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
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
config.plugins.iptvplayer.torrent9_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.torrent9_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.torrent9_proxy))
    if config.plugins.iptvplayer.torrent9_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.torrent9_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://www.torrent9.fo/"


# torrent9.wiki was the main domain until its maintenance page (10.2026); .fo and .to serve the same site
DOMAINS = ("https://www.torrent9.fo/", "https://www7.torrent9.to/", "https://www.torrent9.wiki/")
SITE_MARKER = "Torrent9 Officiel"
# site category (url key) -> moviemeta type
CATEGORIES = (("films", "movie"), ("series", "tv"))
# row icon of a list row -> moviemeta type (other icons are games, music, software, ebooks)
ROW_TYPES = {"fa-video-camera": "movie", "fa-tv": "tv"}
TORRENT_PATH_RE = re.compile(r"(/torrent/\d+)")
YEAR_RE = re.compile(r"(?:^|[\s(\[])((?:19|20)\d{2})(?=$|[\s)\]])")
SXXEXX_RE = re.compile(r"\bS(\d{1,2})(?:\s?E(\d{1,3}))?(-E?\d{1,3})?\b", re.I)
QUALITY_RE = re.compile(r"\b(2160p|1080p|1040p|1024p|720p|576p|480p|4K|4KLight|UHD)\b", re.I)
SOURCE_RE = re.compile(r"\b(Remux|BluRay|Blu-Ray|BDRip|BRRip|HDLight|WEB-DL|WEBRip|WEB|HDTV|HDRip|DVDRip|DVD|HDCAM|CAM|TS|TC)\b", re.I)
CODEC_RE = re.compile(r"\b(x265|x264|HEVC|H\.?265|H\.?264|AVC|AV1|XviD|VP9)\b", re.I)
# language tags of French releases: the title ends before them
LANG_RE = re.compile(r"\b(TRUEFRENCH|FRENCH|SUBFRENCH|MULTI|VFF|VFQ|VFI|VF2|VF|VOF|VOSTFR|VO)\b", re.I)
ALT_TITLE_RE = re.compile(r"\(([^()]{2,})\)\s*$")
PAGE_RE = re.compile(r"""href=['"][^'"]*?[,/]page-(\d+)['"]""")
SPACE_RE = re.compile(r"\s+")
# add 091026: the site writes the same tag as "720P" / "720p", "WEBRIP" / "Web" / "WEBRip": one spelling in titles
TAG_NAMES = dict((name.lower().replace(".", ""), name) for name in (
    "2160p", "1080p", "1040p", "1024p", "720p", "576p", "480p", "4K", "4KLight", "UHD",
    "Remux", "BluRay", "BDRip", "BRRip", "HDLight", "WEB-DL", "WEBRip", "WEB", "HDTV", "HDRip", "DVDRip", "DVD", "HDCAM",
    "CAM", "TS", "TC", "x265", "x264", "HEVC", "H265", "H264", "AVC", "AV1", "XviD", "VP9"))
TAG_NAMES["blu-ray"] = "BluRay"
# add 091026: French size units ("1.3Go") as on the other torrent hosts ("1.3 GB")
SIZE_UNIT_RE = re.compile(r"\s?([KMGT])o\b")


def _categoryTitle(key):
    return {"films": _("Movies"), "series": _("Series")}.get(key, key)


def _size(text):
    return SIZE_UNIT_RE.sub(r" \1B", text or "")


def _releaseParts(name):
    # "La.Piscine.1969.1080p.FRENCH.x264-GRP (The Swimming Pool)" -> ("La Piscine", "1969", season, episode, isPack, "The Swimming Pool")
    text = (name or "").strip()
    altTitle = ""
    alt = ALT_TITLE_RE.search(text)
    if alt and alt.start() > 0:
        altTitle = alt.group(1).strip()
        text = text[:alt.start()].strip()
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
    for regex in (QUALITY_RE, SOURCE_RE, LANG_RE):
        match = regex.search(text)
        if match and 0 < match.start() < cut:
            cut = match.start()
    # fix 091026: the last year before SxxExx / the tags is the release year ("Blade Runner 2049 2017 1080p"),
    # a year at the start is the title ("1917 2019")
    years = [yr for yr in YEAR_RE.finditer(text, 1) if yr.start() < cut]
    if years:
        cut = years[-1].start()
        year = years[-1].group(1)
    elif not season:
        # "Title 1080p 2023": the year after the tags
        yr = YEAR_RE.search(text, cut)
        year = yr.group(1) if yr else ""
    title = text[:cut]
    while title and (title[-1].isspace() or title[-1] in "([-|:"):
        title = title[:-1]  # trailing separators (was a backtracking regex)
    title = title.strip()
    return title, year, season, episode, pack, altTitle


def _qualityLabel(name):
    # "1080p HDLight x264 MULTI VFF" from a release name; fix 091026: with the language tags (VF / VOSTFR / MULTI
    # releases of one film or episode had the same title and download file name)
    parts = []
    for regex in (QUALITY_RE, SOURCE_RE, CODEC_RE):
        match = regex.search(name or "")
        if match:
            parts.append(TAG_NAMES.get(match.group(1).lower().replace(".", ""), match.group(1)))
    for lang in LANG_RE.findall(name or ""):
        if lang.upper() not in parts:
            parts.append(lang.upper())
    return " ".join(parts)


class Torrent9(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "release", "meta_type", "meta_title",
                  "meta_alt_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "torrent9", "cookie": "torrent9.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/torrent9135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True,
                              "cookiefile": self.COOKIE_FILE}
        self.cacheLinks = {}
        self.watchedHelper = IPTVWatchedHelper("torrent9")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def _domains(self):
        domains = list(DOMAINS)
        alt = config.plugins.iptvplayer.torrent9_alt_domain.value.strip()
        if self.cm.isValidUrl(alt):
            domains.insert(0, alt.rstrip("/") + "/")
        if self.MAIN_URL in domains:
            domains.remove(self.MAIN_URL)
        return [self.MAIN_URL] + domains

    def getPage(self, url):
        # the path on the first domain that answers with a Torrent9 page (the mirrors share their paths)
        params = dict(self.defaultParams)
        proxy = GetAlternativeProxyUrl(config.plugins.iptvplayer.torrent9_proxy.value)
        if proxy:
            params["http_proxy"] = proxy
        path = re.sub(r"^https?://[^/]+/", "", url)
        domains = self._domains()
        for domain in domains:
            # add 091026: a mirror that hangs does not hold up the next one for the full default timeout
            sts, data = self.cm.getPageCFProtection(domain + path, dict(params, timeout=20) if domain != domains[-1] else dict(params))
            if sts and SITE_MARKER in data:
                if domain != self.MAIN_URL:
                    printDBG("Torrent9: domain [%s]" % domain)
                    self.MAIN_URL = domain
                return True, data
        return False, ""

    @staticmethod
    def _siteUrl(path):
        # fix 091026: item urls always on the first domain (getPage maps the path to the domain that answers), so a
        # mirror switch does not change download marker / favourite keys
        return gettytul() + re.sub(r"^(?:https?://[^/]+)?/", "", path)

    def getFullIconUrl(self, url):
        url = CBaseHostClass.getFullIconUrl(self, url)
        proxy = GetAlternativeProxyUrl(config.plugins.iptvplayer.torrent9_proxy.value)
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") == "t9_video":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("type") == "video":
                path = TORRENT_PATH_RE.search(cItem.get("url", ""))
                if path:
                    return "video:%s" % path.group(1)
        except Exception:
            printExc()
        return ""

    def _clean(self, text):
        return SPACE_RE.sub(" ", self.cleanHtmlStr(text or "")).strip()

    def _rowTitle(self, release, metaType, normalize):
        # normalised name plus the quality of the release ("The Batman (2022) - 1080p HDLight"): a site lists
        # several releases of one film; the raw release name already carries its quality
        title, year, season, episode, pack, _alt = _releaseParts(release)
        if not normalize or not title:
            return release
        if season and metaType == "tv":
            name = "%s - %s" % (title, formatSxxExx(season, None if pack else episode))
        elif year and metaType == "movie":
            name = "%s (%s)" % (title, year)
        else:
            return release
        quality = _qualityLabel(release)
        return "%s - %s" % (name, quality) if quality else name

    def _cover(self, url):
        # the site keeps the cover of every torrent at /pictures/<slug of the details page>.jpg
        slug = self.cm.ph.getSearchGroups(url, r"/torrent/\d+/([^/?#]+)")[0]
        return self.getFullIconUrl("/pictures/%s.jpg" % slug) if slug else self.DEFAULT_ICON_URL

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        for key, _metaType in CATEGORIES:
            self.addDir({"name": "category", "category": "t9_menu", "title": _categoryTitle(key), "t9_category": key,
                         "good_for_fav": True})
        self.listsTab(self.searchItems(), {"name": "category"})

    def listCategoryMenu(self, cItem):
        key = cItem["t9_category"]
        base = self._siteUrl("/torrents_%s.html" % key)
        for title, url in ((_("Latest"), base), (_("Popular"), base + ",trie-seeds-d")):
            self.addDir({"name": "category", "category": "t9_list", "title": title, "url": url, "t9_category": key, "good_for_fav": True})
        sts, data = self.getPage(base)
        if not sts:
            return
        hasLetters = False
        seen = set()
        for path, title in re.findall(r'''href=['"](/torrents_%s_[a-z0-9-]+\.html)['"][^>]*>([^<]+)<''' % key, data):
            if path in seen:
                continue
            seen.add(path)
            if re.search(r"_(?:[a-z]|09)\.html$", path):
                hasLetters = True
                continue
            self.addDir({"name": "category", "category": "t9_list", "title": self._clean(title), "url": self._siteUrl(path),
                         "t9_category": key, "good_for_fav": True})
        if hasLetters:
            self.addDir({"name": "category", "category": "t9_letters", "title": _("A-Z"), "t9_category": key, "good_for_fav": True})

    def listLetters(self, cItem):
        key = cItem["t9_category"]
        sts, data = self.getPage(self._siteUrl("/torrents_%s.html" % key))
        if not sts:
            return
        for path in re.findall(r'''href=['"](/torrents_%s_(?:[a-z]|09)\.html)['"]''' % key, data):
            letter = path.rsplit("_", 1)[-1].split(".")[0]
            self.addDir({"name": "category", "category": "t9_list", "title": "0-9" if letter == "09" else letter.upper(),
                         "url": self._siteUrl(path), "t9_category": key, "good_for_fav": True})

    def _parseRows(self, data):
        normalize = IsMediaNamingNormalized()
        count = 0
        tbody = self.cm.ph.getDataBeetwenMarkers(data, "<tbody>", "</tbody>", False)[1]
        for row in tbody.split("<tr")[1:]:
            count += 1
            metaType = ROW_TYPES.get(self.cm.ph.getSearchGroups(row, r'''<i class=['"]fa (fa-[a-z-]+)''')[0])
            url = self.cm.ph.getSearchGroups(row, r'''href=['"](/torrent/\d+/[^'"]+)['"]''')[0]
            release = self._clean(self.cm.ph.getSearchGroups(row, r'''<a title=['"]([^'"]+)['"]''')[0])
            if not metaType or not url or not release:
                continue
            cells = [self._clean(x) for x in re.findall(r"(?s)<td[^>]*>(.*?)</td>", row)]
            added, size, seeds, leechers = (cells + [""] * 5)[1:5]
            size = _size(size)
            title, year, _season, _episode, _pack, altTitle = _releaseParts(release)
            fields = [x for x in (size, "S:%s P:%s" % (seeds, leechers) if seeds else "") if x]
            descLines = [" | ".join(fields)] if fields else []
            if added:
                descLines.append("%s: %s" % (_("Added"), added))
            descLines.append(release)
            self.addVideo({"name": "category", "category": "t9_video", "good_for_fav": True, "url": self._siteUrl(url),
                           "title": self._rowTitle(release, metaType, normalize), "icon": self._cover(url),
                           "desc": "[/br]".join(descLines), "release": release, "meta_type": metaType,
                           "meta_title": title, "meta_alt_title": altTitle, "meta_year": year})
        return count

    def _lastPage(self, data):
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', "</ul>", False)[1]
        return max([int(x) for x in PAGE_RE.findall(pager)] or [0])

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        base = cItem.get("base_url") or re.sub(r",page-\d+$", "", cItem["url"])
        search = "/search_torrent/" in base
        if page <= 1:
            url = base
        elif search:
            url = re.sub(r"\.html$", "", base) + "/page-%d" % page
        else:
            url = base + ",page-%d" % page
        printDBG("Torrent9.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            SetIPTVPlayerLastHostError(_("Failed to connect to host."))
            return
        count = self._parseRows(data)
        lastPage = max(self._lastPage(data), page if count else 0)
        hasNext = count > 0 and page < lastPage
        tpl = base.replace("{", "{{").replace("}", "}}")
        tpl = re.sub(r"\.html$", "", tpl) + "/page-{page}" if search else tpl + ",page-{page}"
        listItem = stripPagerKeys(dict(cItem), ("base_url",))
        listItem.update({"base_url": base, "url": base})
        addPagingItems(self, listItem, page, hasNext, lastPage, tpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Torrent9.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        # the site's own search form redirects to /search_torrent/<lower-case words joined by "->.html
        slug = "-".join(searchPattern.strip().lower().split())
        url = self._siteUrl("/search_torrent/%s.html" % urllib_quote(slug, safe="-"))
        self.listItems(dict(cItem, category="t9_list", url=url, base_url=url, page=1))

    ###################################################
    # links
    ###################################################
    def _details(self, data):
        # {release, magnet, seeds, leechers, size, added, genre, story, poster} of a details page
        info = {"release": self._clean(self.cm.ph.getSearchGroups(data, r"(?s)<h1>(.*?)</h1>")[0])}
        info["magnet"] = ph.unescape(self.cm.ph.getSearchGroups(data, r'''href=['"](magnet:\?xt=urn:btih:[^'"]+)['"]''')[0])
        block = self.cm.ph.getDataBeetwenMarkers(data, "movie-information", "description_torrent", False)[1]
        for label, value in re.findall(r"(?s)<strong>([^<]+)</strong>\s*</li>\s*<li>:</li>\s*<li[^>]*>(.*?)</li>", block):
            label = self._clean(label)
            value = self._clean(value)
            if label == "Seed":
                info["seeds"] = value
            elif label == "Leech":
                info["leechers"] = value
            elif label.startswith("Poids"):
                info["size"] = _size(value)
            elif label.startswith("Date"):
                info["added"] = value
            elif label.startswith("Sous"):
                info["genre"] = value
        info["story"] = self._clean(self.cm.ph.getSearchGroups(data, r'''(?s)class=['"]maximum['"]>.*?</div>(.*?)</p>''')[0])
        info["poster"] = self.cm.ph.getSearchGroups(data, r'''(?s)class=['"]movie-img['"][^>]*>\s*<img[^>]+src=['"]([^'"]+)['"]''')[0]
        return info

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("Torrent9.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            SetIPTVPlayerLastHostError(_("Failed to connect to host."))
            return []
        info = self._details(data)
        magnet = info["magnet"]
        if not magnet:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        release = info["release"] or cItem.get("release", "") or cItem.get("title", "")
        if "&dn=" not in magnet:
            magnet += "&dn=" + urllib_quote(release, safe="")
        health = "S:%s P:%s" % (info["seeds"], info.get("leechers", "")) if info.get("seeds") else ""
        name = " - ".join(x for x in (_qualityLabel(release), info.get("size", ""), health) if x)
        icon = str(self.getFullIconUrl(info["poster"]) if info["poster"] else cItem.get("icon", ""))
        if not icon.startswith("http"):
            icon = ""  # fix 091026: not the file:// default icon of the row
        urltab = [{"name": name or release, "url": strwithmeta(magnet, {"title": release, "icon": icon}), "need_resolve": 1}]
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info["story"]))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("Torrent9.getVideoLinks [%s]" % videoUrl)
        if videoUrl.startswith("magnet:?") or self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Torrent9.getArticleContent [%s]" % cItem.get("url", ""))
        site = {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            site = self._details(data)
        info = {}
        for key, label in (("genres", "genre"), ("released", "added")):
            if site.get(label):
                info[key] = site[label]
        if site.get("size"):
            info["quality"] = " - ".join(x for x in (_qualityLabel(cItem.get("release", "")), site["size"]) if x)
        if cItem.get("meta_year"):
            info["year"] = cItem["meta_year"]
        metaType = cItem.get("meta_type", "movie")
        year = cItem.get("meta_year", "") if metaType == "movie" else ""
        meta = {}
        try:
            # the English title in brackets first: the French title often has no match in the English databases
            for title in (cItem.get("meta_alt_title", ""), cItem.get("meta_title", "")):
                if title:
                    meta = getMeta(metaType, title, year, maxYearDiff=1 if year else None)
                    if meta:
                        break
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        story = site.get("story", "")
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        if cItem.get("release") and cItem["release"] not in text:
            text = "%s[/br][/br]%s" % (text, cItem["release"]) if text else cItem["release"]
        poster = self.getFullIconUrl(site["poster"]) if site.get("poster") else ""
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
        printDBG("Torrent9.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "t9_menu":
            self.listCategoryMenu(self.currItem)
        elif category == "t9_letters":
            self.listLetters(self.currItem)
        elif category == "t9_list":
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
        CHostBase.__init__(self, Torrent9(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("torrent9")

    def withArticleContent(self, cItem):
        return cItem.get("category") == "t9_video"
