# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# Ported to the python3 framework (06.10.2026):
#   - moviz-time.cyou (moviz-time.club is the site's permanent redirect and the fallback mirror)
#   - movies / foreign series / anime / TV shows / latest and search (all, movies, series, anime) with
#     First page / Jump / Next page; series rows are one season each -> episodes (the episode buttons
#     of the season page); the series category moved to "...-e" (the old "...-d" list was empty)
#   - every link is the site's own vidhls.com player (FirePlayer): resolved here to the HLS master
#     (the "/cdn/down/" path, "/cdn/hls/" answers 404), other players go through urlparser
#   - watched flag (series -> episodes), downloaded flag on page-url keys, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the site's detail fields
#   - covers: sent with a browser User-Agent + Referer (urllib's default UA gets a 403)
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, requireDownloaderForDisguisedHls
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, GetIconDir, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://moviz-time.cyou/"


MIRROR_URL = "https://moviz-time.club/"
DOMAIN_RE = re.compile(r"^https?://(?:www\.)?moviz-time\.[a-z]+/")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5),
    ("السادسة", 6), ("السادس", 6), ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8),
    ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|مدبلج|مدبلجة|اون لاين|أون لاين|كامل|كاملة|فيلم|مسلسل|أنمي|انمي)(?=\s|$)")
YEAR_RE = re.compile(r"\s(19\d\d|20\d\d)(?=\s|$)")
# <p class="movie_details_section"> rows -> INFO keys
INFO_FIELDS = (("year", ("سنة الإنتاج",)), ("genres", ("نوع الفيلم", "نوع المسلسل", "نوع الأنمي")), ("rating", ("تقييم الفيلم",)),
               ("quality", ("جودة الفيلم", "جودة المسلسل", "جودة الأنمي")), ("status", ("حالة المسلسل", "حالة الأنمي")),
               ("episodes", ("عدد الحلقات",)))
PLOT_LABELS = ("قصة الفيلم", "قصة المسلسل", "قصة الأنمي", "قصة الانمي")
# the site's own player (embed.hamml.com answers with a 302 to vidhls.com)
OWN_PLAYERS = ("vidhls.com", "embed.hamml.com")
# second server of older posts: the domain is parked (parklogic redirect page, no player)
# fix 071026: the other servers of older posts (European/Indian films) are gone as well - ya.kooora.best and
# ok.hamml.com no longer resolve (NXDOMAIN), fembed.com and embed.mystream.to are parklogic pages, vidhid.co
# only redirects to an ad broker; skipped so the list shows the working servers (vidhls, ok.ru) only
PARKED_PLAYERS = ("play.imovietime.bond", "ya.kooora.best", "ok.hamml.com", "fembed.com", "embed.mystream.to", "vidhid.co")
VIDEO_CATEGORIES = ("mt_video", "mt_episode")
SERIES_CATEGORIES = ("mt_series",)


def _domain(url):
    m = re.match(r"^https?://(?:www\.)?([^/:?#]+)", url or "")
    return m.group(1).lower() if m else ""


BUTTON_TAG_RE = re.compile(r"<button([^>]*)>")
EP_ITEM_CLASS_RE = re.compile(r"""class=['"]ep-item['"]""")
LOCATION_RE = re.compile(r"""location\.href=['"]([^'"]+)['"]""")
DETAIL_HEAD_RE = re.compile(r'<p class="movie_details_section">\s*<span([^>]*)>')
DETAIL_VALUE_RE = re.compile(r"</span>\s*<span([^>]*)>")


def _buttonLink(attrs):
    # the (last) location.href url of an ep-item button's attributes, "" for other buttons
    cls = EP_ITEM_CLASS_RE.search(attrs, 1)
    if not cls:
        return ""
    link, pos = "", cls.end() + 1
    while True:
        match = LOCATION_RE.search(attrs, pos)
        if not match:
            return link
        link, pos = match.group(1), match.start() + 1


def _detailRows(data):
    # [(label, value)] of the <p class="movie_details_section"><span class="ttl">..</span><span class="cntt">..</span> rows
    rows, pos = [], 0
    while True:
        head = DETAIL_HEAD_RE.search(data, pos)
        if not head:
            return rows
        if 'class="ttl"' not in head.group(1):
            pos = head.start() + 1
            continue
        value = DETAIL_VALUE_RE.search(data, head.end())
        while value and 'class="cntt"' not in value.group(1):
            value = DETAIL_VALUE_RE.search(data, value.start() + 1)
        end = data.find("</span>", value.end()) if value else -1
        if end < 0:
            return rows
        rows.append((data[head.end():value.start()], data[value.end():end]))
        pos = end + 7


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


class MovizTime(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "moviztime", "cookie": "moviztime.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/moviztime135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.domainChecked = False
        self.watchedHelper = IPTVWatchedHelper("moviztime")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def selectDomain(self):
        # the current domain, else the old one (it redirects to wherever the site lives now)
        self.domainChecked = True
        for domain in (self.MAIN_URL, MIRROR_URL):
            params = dict(self.defaultParams)
            params["with_metadata"] = True
            sts, data = self.cm.getPageCFProtection(domain, params)
            if sts and "وقت الافلام" in data:
                self.setMainUrl(data.meta.get("url", "") or domain)
                printDBG("MovizTime.selectDomain [%s]" % self.MAIN_URL)
                return

    @staticmethod
    def _quote(url):
        try:
            return urllib_quote(urllib_unquote(url.replace("&amp;", "&").replace("&#038;", "&")), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _canonUrl(self, url):
        # absolute, percent-encoded, on the current domain (favourites keep working after a move)
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return self._quote(DOMAIN_RE.sub(self.MAIN_URL, url))

    def _path(self, url):
        # domain independent identity of a page (the episode number stays in the fragment)
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def _icon(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        return strwithmeta(self._canonUrl(url), {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL})

    @staticmethod
    def _clean(text):
        text = SEASON_RE.sub(" ", text or "")
        text = JUNK_RE.sub(" ", text)  # the lookahead leaves the space, "مترجم كامل" back to back go in one pass
        return re.sub(r"\s+", " ", text).strip(" -:|")

    def _splitTitle(self, rawTitle):
        # "فيلم Troy 2004 مترجم" -> ("Troy", "2004"); "مسلسل Doc مترجم الموسم الثاني كامل" -> ("Doc", "")
        title = self._clean(rawTitle)
        year = ""
        m = YEAR_RE.search(" " + title)
        if m:
            year = m.group(1)
            stripped = re.sub(r"\s+", " ", YEAR_RE.sub(" ", " " + title)).strip(" -:|")
            if stripped:
                title = stripped
        return title or rawTitle, year

    def _isSeries(self, url):
        return bool(re.match(r"^/(?:series|anime)/", self._path(url)))

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
            prefix = {"mt_video": "video", "mt_episode": "video", "mt_series": "series"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        def cat(path):
            return self.getFullUrl("/category/%s/" % path)

        movies = [
            (_("Foreign movies"), cat("أفلام-أجنبية")),
            (_("European movies"), cat("أفلام-أوروبية")),
            (_("Asian movies"), cat("أفلام-آسيوية-مترجمة")),
            (_("Indian Movies"), cat("أفلام-هندية")),
            (_("Turkish Movies"), cat("أفلام-تركية")),
            (_("Documentary Movies"), cat("أفلام-وثائقية")),
        ]
        anime = [
            (_("Anime Series"), cat("قائمة-الأنمي-b/مسلسلات-أنمي")),
            (_("Anime Movies"), cat("قائمة-الأنمي-b/أفلام-أنمي")),
        ]
        menu = [
            {"category": "mt_tab", "title": _("Movies"), "tab": movies},
            {"category": "list_items", "title": _("Foreign series"), "url": cat("مسلسلات-أجنبية-مترجمة-e"), "good_for_fav": True},
            {"category": "mt_tab", "title": _("Anime"), "tab": anime},
            {"category": "list_items", "title": _("TV Shows"), "url": cat("برامج-تلفزيونية"), "good_for_fav": True},
            {"category": "list_items", "title": _("Latest"), "url": self.MAIN_URL, "good_for_fav": True},
        ]
        self.listsTab(menu + self.searchItems(), cItem)

    def listTab(self, cItem):
        for title, url in cItem.get("tab", []):
            self.addDir({"name": "category", "category": "list_items", "title": title, "url": url, "good_for_fav": True})

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = self._canonUrl(cItem.get("base_url") or cItem["url"])
        query = cItem.get("query", "")
        if query:
            pageTpl = baseUrl + "page/{page}/?s=" + query
            url = pageTpl.format(page=page) if page > 1 else baseUrl + "?s=" + query
        else:
            pageTpl = baseUrl + "page/{page}/"
            url = pageTpl.format(page=page) if page > 1 else baseUrl
        printDBG("MovizTime.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<article class="pinbox">', "</article>"):
            href = self.cm.ph.getSearchGroups(item, r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            if not href:
                continue
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h2[^>]*>(.*?)</h2>')[0])
            if not rawTitle:
                rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not rawTitle:
                continue
            title, year = self._splitTitle(rawTitle)
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="_quality_tag"[^>]*>(.*?)</span>')[0])
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            fields = ((_("Quality"), quality, "yellow"), (_("Year"), year, "cyan"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self._icon(icon), "desc": desc}
            if self._isSeries(url):
                season = _seasonNum(rawTitle) or 1
                dispTitle = "%s - %s" % (title, formatSxxExx(season)) if normalize else rawTitle
                params.update({"category": "mt_series", "title": dispTitle, "s_title": title, "s_season": season,
                               "meta_type": "tv", "meta_title": title, "meta_year": year})
                self.addDir(params)
            else:
                dispTitle = rawTitle
                if normalize:
                    dispTitle = "%s (%s)" % (title, year) if year else title
                params.update({"category": "mt_video", "title": dispTitle, "meta_type": "movie", "meta_title": title, "meta_year": year})
                self.addVideo(params)

        pager = self.cm.ph.getSearchGroups(data, r'(?s)class="posts-navigation[^"]*">(.*?)</div>')[0]
        hasNext = bool(seen) and 'class="next"' in pager
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, 0, pageTpl)

    def listEpisodes(self, cItem):
        printDBG("MovizTime.listEpisodes [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem["url"])
        sts, data = self.getPage(pageUrl)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 0) or 1
        seen = set()
        for idx, (link, label) in enumerate(self._episodeButtons(data)):
            label = self.cleanHtmlStr(label)
            episode = self.cm.ph.getSearchGroups(label, r"(\d+)")[0] or str(idx + 1)
            if episode in seen:
                continue
            seen.add(episode)
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - %s" % (cItem.get("title", ""), label or "%s %s" % (_("Episode"), episode))
            self.addVideo({"name": "category", "good_for_fav": True, "category": "mt_episode", "title": title,
                           "url": "%s#episode-%s" % (pageUrl, episode), "icon": cItem.get("icon", ""), "desc": cItem.get("desc", ""),
                           "s_title": show, "s_season": season, "s_episode": episode,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})

    @staticmethod
    def _episodeButtons(data):
        # [(player url, label)] of the season page: <button class='ep-item' onclick="... location.href='<player>'; ...">الحلقة 1</button>
        rows, pos = [], 0
        while True:
            tag = BUTTON_TAG_RE.search(data, pos)
            if not tag:
                return rows
            end = data.find("</button>", tag.end())
            if end < 0:
                return rows
            link = _buttonLink(tag.group(1))
            if link:
                rows.append((link, data[tag.end():end]))
                pos = end + 9
            else:
                pos = tag.start() + 1

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MovizTime.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        pattern = ("%s %s" % (searchType, searchPattern)).strip()
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.MAIN_URL, "base_url": self.MAIN_URL, "page": 1,
                      "query": urllib_quote_plus(pattern)})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        rows = {}
        for label, value in _detailRows(data):
            rows[self.cleanHtmlStr(label).rstrip(": ")] = self.cleanHtmlStr(value)
        info = {}
        for key, labels in INFO_FIELDS:
            for label in labels:
                if rows.get(label):
                    info[key] = rows[label]
                    break
        story = ""
        for label in PLOT_LABELS:
            if rows.get(label):
                story = rows[label]
                break
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self._icon(poster), info

    def getLinksForVideo(self, cItem):
        printDBG("MovizTime.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl, _sep, fragment = self._canonUrl(cItem.get("url", "")).partition("#")
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        links = []
        if fragment.startswith("episode-"):
            episode = fragment[len("episode-"):]
            for idx, (link, label) in enumerate(self._episodeButtons(data)):
                if (self.cm.ph.getSearchGroups(self.cleanHtmlStr(label), r"(\d+)")[0] or str(idx + 1)) == episode:
                    links.append(link)
        else:
            for tab in self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="single_tab', "</div>"):
                links.append(self.cm.ph.getSearchGroups(tab, r'data-src="([^"]+)"')[0])
        urltab = []
        for link in links:
            link = self._linkUrl(link)
            domain = _domain(link)
            if not domain or domain in PARKED_PLAYERS:
                continue
            urltab.append({"name": "%s %d - %s" % (_("Server"), len(urltab) + 1, domain), "url": link, "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    def _linkUrl(self, link):
        link = link.replace("&amp;", "&").strip()
        if link.startswith("//"):
            link = "https:" + link
        return strwithmeta(link, {"Referer": self.MAIN_URL})

    def _resolveVidHls(self, videoUrl):
        # the site's own player: FirePlayer(vhash, {"hostList": {"17": ["cdn.host"]}, "videoServer": "17",
        # "videoUrl": "/cdn/hls/<id>/master.txt"}) - the playlist is served under /cdn/down/
        referer = videoUrl.meta.get("Referer", self.MAIN_URL) if hasattr(videoUrl, "meta") else self.MAIN_URL
        header = dict(self.HEADER)
        header["Referer"] = referer
        sts, data = self.cm.getPage(videoUrl, {"header": header})
        if not sts:
            return []
        raw = self.cm.ph.getSearchGroups(data, r"FirePlayer\(\s*vhash\s*,\s*(\{.*?\})\s*,\s*(?:false|true)\s*\)")[0]
        try:
            config = json_loads(raw) if raw else {}
        except Exception:
            printExc()
            config = {}
        path = config.get("videoUrl", "")
        hosts = (config.get("hostList") or {}).get(str(config.get("videoServer", ""))) or []
        cdn = hosts[0].split(" ")[0].strip() if hosts else ""
        if not path or not cdn:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        hlsUrl = "https://%s%s" % (cdn, path.replace("/cdn/hls/", "/cdn/down/"))
        meta = {"iptv_proto": "m3u8", "User-Agent": self.HEADER.get("User-Agent"), "Referer": "https://vidhls.com/", "Origin": "https://vidhls.com"}
        links = getDirectM3U8Playlist(strwithmeta(hlsUrl, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)
        # fix 071026: the variant playlists end in .txt, so they came back as iptv_proto "https" - exteplayer3 then
        # took them for a file and ended at once (box log) and the disguised-segment check below skipped them
        for item in links:
            item["url"] = strwithmeta(item["url"], dict(getattr(item["url"], "meta", {}), iptv_proto="m3u8"))
        # the segments are named *.jpg (TS inside) - exteplayer3's ffmpeg refuses them, hlsdl plays them
        return requireDownloaderForDisguisedHls(links)

    def getVideoLinks(self, videoUrl):
        printDBG("MovizTime.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if _domain(videoUrl) in OWN_PLAYERS:
            return decorateResolvedLinkItems(self._resolveVidHls(videoUrl), sidecar)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("MovizTime.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", "").split("#")[0])
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or StripColorCodes(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if not self.domainChecked:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("MovizTime.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "mt_tab":
            self.listTab(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "mt_series":
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
        CHostBase.__init__(self, MovizTime(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("moviztime")

    def getSearchTypes(self):
        return [(_("All"), ""), (_("Movies"), "فيلم"), (_("Series"), "مسلسل"), (_("Anime"), "أنمي")]

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + SERIES_CATEGORIES
