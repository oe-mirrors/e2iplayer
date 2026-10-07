# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - new host for ihavenotv.com (I Have No TV - free documentaries, English)
#   Lists: latest / recommended / random picks / categories / series A-Z / documentaries A-Z + search.
#   The site sends a whole category (hundreds of cards) in one page and has no pager, so the cards
#   are cached in memory and paged here (only a real rest gives a "Next page").
#   Series index: the site has none - it is built from the A-Z page, where episodes carry "(Series)";
#   the series slug is the site's own slug rule (cards link /series/<slug> the same way).
#   Videos: mostly Abyss player embeds (abyssplayer.com -> urlparser parserABYSS), some YouTube,
#   Streamtape and Google Drive; the site's own .srt (when offered) goes along as external subtitle.
#   Watched flag / downloaded flag / name normalisation "Title (Year)", "Show - SxxExx - Title" /
#   sidecar / INFO (site data + moviemeta for single documentaries and series) / favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://ihavenotv.com/"


class IHaveNoTV(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # stable identity of a row (desc / icon can change)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "year", "genre", "icon", "series", "series_url", "sxe", "letter", "kind")
    ITEMS_PER_PAGE = 50
    CACHE_SIZE = 8
    RANDOM_MARKER = "Random! Documentaries"

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "ihavenotv", "cookie": "ihavenotv.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("/img/rocket32.png")
        self.MENU = [{"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("/latest")},
                     {"category": "list_items", "title": _("Recommended"), "url": self.getFullUrl("/recommended")},
                     {"category": "list_items", "title": _("Random selection"), "url": self.MAIN_URL, "section": self.RANDOM_MARKER},
                     {"category": "list_categories", "title": _("Categories"), "url": self.MAIN_URL},
                     {"category": "list_letters", "title": _("Series A-Z"), "url": self.getFullUrl("/listofalldocumentaries"), "kind": "series"},
                     {"category": "list_letters", "title": _("Documentaries A-Z"), "url": self.getFullUrl("/listofalldocumentaries"), "kind": "videos"}] + self.searchItems()
        self.cardCache = {}
        self.cardCacheOrder = []
        self.azCache = None

        self.watchedHelper = IPTVWatchedHelper("ihavenotv")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = self.wfNormalizeUrlKey(cItem.get("url", ""))
            if cItem.get("type", "") == "video":
                return "video:%s" % url if url else ""
            if cItem.get("category", "") == "list_items" and "/series/" in url:
                return "series:%s" % url
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _normUrl(self, url, currUrl=None):
        url = self.getFullUrl(url.replace("&amp;", "&").strip(), currUrl)
        return re.sub(r"^https?://(?:www\.)?ihavenotv\.com/", self.MAIN_URL, url)

    @staticmethod
    def _seriesSlug(name):
        # same rule as the site's /series/<slug> links: lower case, punctuation dropped, blanks/dashes -> one dash
        slug = re.sub(r"[^a-z0-9 \-]", "", name.lower())
        return re.sub(r"[\s\-]+", "-", slug.strip()).strip("-")

    def _videoTitle(self, title, year, series="", sxe=""):
        if not IsMediaNamingNormalized():
            return title
        if series:
            # "Part 2" / "Mongolia" alone says nothing - the show goes in front, the normaliser inserts SxxExx
            if title.lower().startswith(series.lower()):
                return normalizeMediathekTitle(title, sxeHint=sxe)
            return normalizeMediathekTitle("%s - %s" % (series, title), sxeHint=sxe)
        return normalizeMediathekTitle(title, year=year, isMovie=True)

    ###################################################
    # card lists (one site page = whole list, paged here)
    ###################################################
    def _parseCards(self, data, currUrl):
        items = []
        seen = set()
        listSeries = ""
        if "/series/" in currUrl:
            listSeries = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<h1>(.*?)<small", ignoreCase=True)[0])
        for block in data.split('<div class="episode">')[1:]:
            link = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<span class="episodeTitle">(.*?)</span>', ignoreCase=True)[0])
            if not link or not title:
                continue
            url = self._normUrl(link, currUrl)
            if url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="episodeTime">(.*?)</div>')[0])
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<p class="episodeSynopsis">(.*?)</p>', ignoreCase=True)[0])
            metaHtml = self.cm.ph.getSearchGroups(block, r'(?s)<p class="episodeMeta">(.*?)</p>', ignoreCase=True)[0]
            sxe = self.cleanHtmlStr(self.cm.ph.getSearchGroups(metaHtml, r"<strong>(S\d+E\d+)</strong>", ignoreCase=True)[0]).upper()
            seriesUrl, seriesName = self.cm.ph.getSearchGroups(metaHtml, r'(?s)<a href="(/series/[^"]+)"[^>]*>(.*?)</a>', 2)
            seriesName = self.cleanHtmlStr(seriesName)
            if not seriesUrl and listSeries:
                seriesUrl, seriesName = currUrl, listSeries
            genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(metaHtml, r'(?s)class="category">(.*?)</a>')[0])
            year = self.cm.ph.getSearchGroups(re.sub(r"<a[^>]*>.*?</a>", "", metaHtml), r"\b((?:19|20)\d{2})\b")[0]
            items.append({"url": url, "title": title, "icon": self.getFullIconUrl(icon, currUrl) if icon else "", "duration": duration, "plot": plot,
                          "sxe": sxe, "series": seriesName, "series_url": self._normUrl(seriesUrl) if seriesUrl else "", "genre": genre, "year": year})
        return items

    def _getCards(self, url, section=""):
        key = "%s|%s" % (url, section)
        if key in self.cardCache:
            return self.cardCache[key]
        sts, data = self.getPage(url)
        if not sts:
            return None
        currUrl = data.meta.get("url", url) if hasattr(data, "meta") else url
        if section:
            data = data.split(section, 1)[-1] if section in data else ""
            data = data.split('<div class="col-md-10">', 1)[0]
        items = self._parseCards(data, currUrl)
        if section == self.RANDOM_MARKER:
            return items  # changes with every load
        self.cardCache[key] = items
        self.cardCacheOrder.append(key)
        while len(self.cardCacheOrder) > self.CACHE_SIZE:
            self.cardCache.pop(self.cardCacheOrder.pop(0), None)
        return items

    def listItems(self, cItem):
        printDBG("IHaveNoTV.listItems |%s| page[%s]" % (cItem.get("url", ""), cItem.get("page", 1)))
        page = max(1, int(cItem.get("page", 1) or 1))
        items = self._getCards(cItem["url"], cItem.get("section", ""))
        if items is None:
            return
        if not items:
            if "/series/" in cItem["url"] or "/search/" in cItem["url"]:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return
        start = (page - 1) * self.ITEMS_PER_PAGE
        for item in items[start:start + self.ITEMS_PER_PAGE]:
            descTab = [x for x in (item["year"], item["duration"], item["genre"]) if x]
            if item["series"]:
                descTab.insert(0, "%s %s" % (item["series"], item["sxe"]) if item["sxe"] else item["series"])
            desc = " | ".join(descTab)
            if item["plot"]:
                desc = "%s[/br]%s" % (desc, item["plot"]) if desc else item["plot"]
            params = stripPagerKeys(dict(cItem), ("search_pattern", "section", "letter", "kind"))
            params.update({"good_for_fav": True, "category": "video", "url": item["url"], "icon": item["icon"], "desc": desc,
                           "title": self._videoTitle(item["title"], item["year"], item["series"], item["sxe"]), "s_title": item["title"],
                           "year": item["year"], "genre": item["genre"], "series": item["series"], "series_url": item["series_url"], "sxe": item["sxe"]})
            self.addVideo(params)
        self._addPaging(cItem, page, len(items))

    def _addPaging(self, cItem, page, total):
        # the whole list is cached, paged here; the folder url stays the same ("Jump" template)
        lastPage = (total + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
        addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem.get("url", "").replace("{", "%7B").replace("}", "%7D"))

    def listCategories(self, cItem):
        printDBG("IHaveNoTV.listCategories")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for url in re.findall(r'href="(/category/[^"]+)"', data):
            url = self._normUrl(url)
            if url in seen:
                continue
            seen.add(url)
            title = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url, "page": 1})
            self.addDir(params)

    ###################################################
    # A-Z page: every documentary as "Title (Series)" - no icons
    ###################################################
    def _getAZ(self, url):
        if self.azCache is not None:
            return self.azCache
        sts, data = self.getPage(url)
        if not sts:
            return None
        videos, seriesCount = [], {}
        for link, title in re.findall(r'<li><a href=\s*"(/[^"]+)"\s*>(.*?)</a></li>', data, re.DOTALL):
            title = self.cleanHtmlStr(title)
            if not title:
                continue
            videos.append((self._normUrl(link), title))
            series = self.cm.ph.getSearchGroups(title, r"\(((?:[^()]|\([^()]*\))+)\)\s*$")[0].strip()
            if series:
                seriesCount[series] = seriesCount.get(series, 0) + 1
        # a "(...)" tail seen only once is usually a remark, not a show
        series = sorted([name for name, cnt in seriesCount.items() if cnt > 1], key=lambda x: x.lower())
        videos.sort(key=lambda x: x[1].lower())
        self.azCache = {"videos": videos, "series": series}
        return self.azCache

    @staticmethod
    def _letterOf(title):
        first = re.sub(r"^[^0-9A-Za-z]+", "", title)[:1].upper()
        return first if first.isalpha() else "#"

    def listLetters(self, cItem):
        printDBG("IHaveNoTV.listLetters [%s]" % cItem.get("kind", ""))
        az = self._getAZ(cItem["url"])
        if not az:
            return
        entries = az["series"] if cItem.get("kind") == "series" else [x[1] for x in az["videos"]]
        counts = {}
        for title in entries:
            letter = self._letterOf(title)
            counts[letter] = counts.get(letter, 0) + 1
        for letter in sorted(counts.keys()):
            params = dict(cItem)
            params.update({"good_for_fav": False, "category": "list_az", "title": "%s (%d)" % (letter, counts[letter]), "letter": letter, "page": 1})
            self.addDir(params)

    def listAZ(self, cItem):
        printDBG("IHaveNoTV.listAZ [%s] [%s]" % (cItem.get("kind", ""), cItem.get("letter", "")))
        az = self._getAZ(cItem["url"])
        if not az:
            return
        letter = cItem.get("letter", "")
        page = max(1, int(cItem.get("page", 1) or 1))
        start = (page - 1) * self.ITEMS_PER_PAGE
        if cItem.get("kind") == "series":
            rows = [name for name in az["series"] if self._letterOf(name) == letter]
            for name in rows[start:start + self.ITEMS_PER_PAGE]:
                params = stripPagerKeys(dict(cItem), ("letter", "kind"))
                params.update({"good_for_fav": True, "category": "list_items", "title": name, "s_title": name,
                               "url": self.getFullUrl("/series/%s" % self._seriesSlug(name)), "desc": ""})
                self.addDir(params)
        else:
            seriesSet = set(az["series"])
            rows = [x for x in az["videos"] if self._letterOf(x[1]) == letter]
            for url, title in rows[start:start + self.ITEMS_PER_PAGE]:
                params = stripPagerKeys(dict(cItem), ("letter", "kind"))
                params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": title, "url": url, "desc": ""})
                series = self.cm.ph.getSearchGroups(title, r"\(((?:[^()]|\([^()]*\))+)\)\s*$")[0].strip()
                if series in seriesSet:
                    # "Episode (Show)" - same row label as the site, but known as an episode (no film lookup in INFO)
                    params.update({"series": series, "series_url": self.getFullUrl("/series/%s" % self._seriesSlug(series)), "desc": series})
                self.addVideo(params)
        self._addPaging(cItem, page, len(rows))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("IHaveNoTV.listSearchResult [%s]" % searchPattern)
        pattern = re.sub(r"[/\\?#%]+", " ", searchPattern).strip()
        if not pattern:
            return
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/search/%s" % urllib_quote(pattern)), "page": 1})
        self.listItems(cItem)

    ###################################################
    # video page
    ###################################################
    def _parseVideoPage(self, data):
        info = {"title": "", "year": "", "desc": "", "poster": "", "duration": "", "genre": "", "tags": "", "embeds": [], "subs": []}
        details = self.cm.ph.getDataBeetwenMarkers(data, '<div class="videoDetails">', "</p>", False)[1]
        info["title"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(details, r"(?s)<h1>\s*<strong>(.*?)</strong>", ignoreCase=True)[0]) or \
            self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:title" content="([^"]*)"')[0])
        info["year"] = self.cm.ph.getSearchGroups(self.cm.ph.getSearchGroups(details, r"(?s)<h1>(.*?)</h1>", ignoreCase=True)[0], r"<small>[^<]*?\b((?:19|20)\d{2})\b")[0]
        info["genre"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(details, r'(?s)href="/category/[^"]+"[^>]*>(.*?)</a>', ignoreCase=True)[0])
        info["desc"] = self.cleanHtmlStr(details.rsplit("<p>", 1)[-1]) if "<p>" in details else ""
        if not info["desc"]:
            info["desc"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        info["poster"] = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        seconds = self.cm.ph.getSearchGroups(data, r'<meta property="video:duration" content="(\d+)"')[0]
        if seconds and int(seconds) > 0:
            info["duration"] = "%dh %02dmin" % (int(seconds) // 3600, (int(seconds) % 3600) // 60) if int(seconds) >= 3600 else "%dmin" % (int(seconds) // 60)
        info["tags"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="keywords" content="([^"]*)"')[0]).replace(",", ", ")
        player = self.cm.ph.getDataBeetwenMarkers(data, '<div id="videoWrap">', '<div class="videoDetails">', False)[1]
        for src in re.findall(r'<iframe[^>]+src="([^"]+)"', player, re.IGNORECASE):
            src = src.replace("&amp;", "&").strip()
            if src.startswith("//"):
                src = "https:" + src
            if self.cm.isValidUrl(src) and src not in info["embeds"]:
                info["embeds"].append(src)
        for path in re.findall(r'href="(/File/Get\?virtualFilePath=[^"]*Srt[^"]+)"', details):
            path = path.replace("&amp;", "&")
            fileName = urllib_unquote(path.rsplit("%2F", 1)[-1].rsplit("/", 1)[-1])
            lang = self.cm.ph.getSearchGroups(fileName.lower(), r"[._-]([a-z]{2,3})\.(?:srt|vtt)$")[0] or "en"
            lang = {"eng": "en", "ger": "de", "deu": "de", "fre": "fr", "fra": "fr", "spa": "es", "ita": "it"}.get(lang, lang)
            info["subs"].append({"title": lang, "url": self.getFullUrl(path), "lang": lang, "format": "vtt" if fileName.lower().endswith(".vtt") else "srt"})
        return info

    def getLinksForVideo(self, cItem):
        printDBG("IHaveNoTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        info = self._parseVideoPage(data)
        if not info["embeds"]:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        urltab = []
        unsupported = []
        for embed in info["embeds"]:
            if self.up.checkHostSupport(embed) != 1:
                unsupported.append(self.up.getHostName(embed))
                continue
            meta = {"Referer": pageUrl}
            if info["subs"]:
                meta["ihavenotv_subs"] = json_dumps(info["subs"])
            domain = self.cm.ph.getSearchGroups(embed, r"^https?://(?:www\.)?([^/:?#]+)")[0].lower().split(".")
            name = (domain[-2] if len(domain) > 1 else domain[0]).capitalize() or "Video"
            urltab.append({"name": name, "url": strwithmeta(embed, meta), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info["desc"]))

    def getVideoLinks(self, videoUrl):
        printDBG("IHaveNoTV.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        videoUrl = strwithmeta(videoUrl)
        siteSubs = []
        try:
            if videoUrl.meta.get("ihavenotv_subs"):
                siteSubs = json_loads(videoUrl.meta["ihavenotv_subs"])
        except Exception:
            printExc()
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        links = decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        if siteSubs:
            for item in links:
                url = strwithmeta(item["url"])
                if url.meta.get("external_sub_tracks"):
                    continue  # the hoster brings its own (Abyss: the same English .srt) - no duplicate entries
                item["url"] = strwithmeta(url, {"external_sub_tracks": siteSubs})
        return links

    ###################################################
    # info / favourites
    ###################################################
    def _lookupMeta(self, mediaType, title, year):
        try:
            return getMeta(mediaType, title, year) or {}
        except Exception:
            printExc()
        return {}

    def getArticleContent(self, cItem):
        printDBG("IHaveNoTV.getArticleContent [%s]" % cItem.get("url", ""))
        otherInfo = {}
        title = cItem.get("s_title", cItem.get("title", ""))
        text = re.sub(r"^.*?\[/br\]", "", cItem.get("desc", "")) if "[/br]" in cItem.get("desc", "") else cItem.get("desc", "")
        icon = cItem.get("icon", "")
        year = cItem.get("year", "")
        meta = {}
        url = cItem.get("url", "")
        if cItem.get("type") == "video" and self.cm.isValidUrl(url):
            sts, data = self.getPage(url)
            if sts:
                info = self._parseVideoPage(data)
                title = info["title"] or title
                text = info["desc"] or text
                icon = info["poster"] or icon
                year = info["year"] or year
                if info["duration"]:
                    otherInfo["duration"] = info["duration"]
                if info["genre"]:
                    otherInfo["category"] = info["genre"]
                if info["tags"]:
                    otherInfo["genres"] = info["tags"]
                if cItem.get("series"):
                    # "Show - S01E02 - Part 2" says more than the bare episode title
                    title = cItem.get("title", "") or title
            # metadata services only for a real single film - an episode title ("Part 2") would find rubbish
            if not cItem.get("series") and not re.search(r"\([^()]+\)\s*$", title):
                meta = self._lookupMeta("movie", title, year)
        elif "/series/" in url and self.cm.isValidUrl(url):
            sts, data = self.getPage(url)
            if sts:
                head = self.cm.ph.getSearchGroups(data, r"(?s)<h1>(.*?)</h1>", ignoreCase=True)[0]
                title = self.cleanHtmlStr(head.split("<small", 1)[0]) or title
                # <small> &bull; 2024 - 2026 &bull; 8 episodes &bull; 7h:48m</small>
                small = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r"(?s)<small>(.*?)</small>", ignoreCase=True)[0])
                runtime = self.cm.ph.getSearchGroups(small, r"\b(\d+h:\d+m)\b")[0]
                if runtime:
                    otherInfo["duration"] = runtime.replace(":", " ")
                years = self.cm.ph.getSearchGroups(small, r"\b((?:19|20)\d{2}(?:\s*-\s*(?:19|20)\d{2})?)\b")[0]
                year = years[:4] or year
                if years:
                    otherInfo["year"] = years
                text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)</h1>\s*<p>(.*?)</p>", ignoreCase=True)[0]) or text
                # the series backdrop is often a dead link ("s3758..jpg") - the first episode picture is not
                cards = self._parseCards(data, url)
                icon = (cards[0]["icon"] if cards and cards[0]["icon"] else "") or icon or \
                    self.cm.ph.getSearchGroups(data, r"background-image:\s*url\('([^']+)'\)")[0]
                if cards:
                    otherInfo["episodes"] = str(len(cards))
            meta = self._lookupMeta("tv", title, year)
        if year and "year" not in otherInfo:
            otherInfo["year"] = year
        if meta:
            for key, value in meta.get("info", {}).items():
                otherInfo.setdefault(key, value)
            if not text:
                text = meta.get("plot", "")
            icon = icon or meta.get("poster", "")
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("IHaveNoTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_categories":
            self.listCategories(self.currItem)
        elif category == "list_letters":
            self.listLetters(self.currItem)
        elif category == "list_az":
            self.listAZ(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, IHaveNoTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("ihavenotv")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or "/series/" in cItem.get("url", "")
