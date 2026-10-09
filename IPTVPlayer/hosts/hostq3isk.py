# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# 09.10.2026 - moved to 3isq.qist3ishq.site ("قصة عشق الأصلي", the 3isq brand on its own PHP site, no Cloudflare);
#   we.3isq.cam / b.3isq.cam answer a Cloudflare challenge (MyE2i only) and use other urls + markup
#   - menus: latest episodes, series, movies, search - all with First page / Jump / Next page (the site's "?page=N")
#   - movies and episodes are VIDEO rows keyed on their page url; the server list (ul.servers-list, data-link) comes
#     from POSTing the page's play button (token=play) and is handed to urlparser
#   - series -> episodes (ascending, local paging over 100); watched flag (series:/video: keys on the site's numeric
#     ids, domain independent), downloaded flag, favourites, name normalisation ("Title (Year)", "Show - SxxExx"),
#     sidecar, INFO via moviemeta + the site's story/poster; no blocking retry loops, no colour codes in titles
#   - favourites of the old *.3isq.cam site are looked up by title on this site (search -> series/movie -> episode)
#   - pages still go through getPageCFProtection, so a later Cloudflare check gets MyE2i; covers then carry the
#     cf_clearance cookie + User-Agent (getFullIconUrl); default icon = bundled logo
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://3isq.qist3ishq.site/"


LOCAL_PAGE_SIZE = 100
# cards on a full page of the site's smallest list (search)
MIN_PAGE_SIZE = 20
COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")
# Arabic ordinals used in season labels ("الموسم الثاني")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالث", 3), ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8),
    ("التاسع", 9), ("العاشر", 10),
]
SEASON_WORD_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"^(.*?)\s*الحلقة\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s)((?:19|20)\d{2})(?=\s|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|مدبلج|مدبلجة|اون لاين|أون لاين|مشاهدة|وتحميل|فيلم|مسلسل|كامل|كاملة|HD)(?=\s|$)")
# numeric ids in the site's urls: /serie/<id>/.., /movie/<id>/.., /watch/<serie id>/episode/<id>/..
ID_RE = re.compile(r"/(serie|movie|episode)/(\d+)(?:/|$)")
# old site (we.3isq.cam, b.3isq.cam): other urls + markup, Cloudflare - its favourites are looked up by title
LEGACY_DOMAIN = "3isq.cam"
# spelling variants that differ between the old and the new site's titles
ARABIC_FOLD = (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي"))


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


def _seasonNum(text):
    m = SEASON_WORD_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


def _clean(text):
    text = JUNK_RE.sub(" ", JUNK_RE.sub(" ", text or ""))
    # the en dash as a whole sequence (py2 str.strip would take its single utf-8 bytes)
    return re.sub(r"\s+", " ", text.replace("–", " ")).strip(" -:|")


def _fold(text):
    text = _clean(text).lower()
    for src, dst in ARABIC_FOLD:
        text = text.replace(src, dst)
    return text


class Q3isk(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "q3isk", "cookie": "q3isk.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/q3isk135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "list_items", "title": _("Latest episodes"), "url": self.getFullUrl("/episodes")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/series")},
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/movies")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("q3isk")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def getFullUrl(self, url, currUrl=None):
        # the site's urls carry Arabic slugs - one ASCII (percent-encoded) form for everything
        return self._quote(CBaseHostClass.getFullUrl(self, url, currUrl))

    @staticmethod
    def _quote(url):
        try:
            return urllib_quote(urllib_unquote(url.replace("&amp;", "&").replace("&#038;", "&")), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _canonUrl(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return self._quote(url)

    def _path(self, url):
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def _kind(self, url):
        # "serie" / "movie" / "episode" from the site's url, "" for anything else
        m = ID_RE.search(self._path(url))
        return m.group(1) if m else ""

    def _isLegacy(self, url):
        domain = self.up.getDomain(url or "").lower()
        return domain == LEGACY_DOMAIN or domain.endswith("." + LEGACY_DOMAIN)

    def _icon(self, url):
        url = (url or "").strip()
        return self.getFullIconUrl(url) if url else ""

    def getFullIconUrl(self, url, currUrl=None):
        # covers need a browser User-Agent; once MyE2i stored a cf_clearance cookie (a later Cloudflare check)
        # the cover download needs it + the User-Agent that passed the check. The meta is attached here because the
        # host base runs every icon through getFullIconUrl again; covers on foreign domains stay plain
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http") or self.up.getDomain(url).lower() != self.up.getDomain(self.MAIN_URL).lower():
            return url
        # the CDN answers a 403 to library User-Agents (Python-urllib)
        meta = {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("q3_video", "q3_series"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
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
            prefix = {"q3_video": "video", "q3_series": "series"}.get(cItem.get("category", ""), "")
            if not prefix:
                return ""
            path = self._path(cItem.get("url", ""))
            m = ID_RE.search(path)
            if m:
                # the slug and the domain may change, the numeric id stays
                return "%s:%s/%s" % (prefix, m.group(1), m.group(2))
            # rows of the old *.3isq.cam site keep their old keys
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _episodeParams(self, label, url, icon, desc, normalize, fallbackShow="", episode=""):
        m = EPISODE_RE.search(label)
        show = _clean(m.group(1)) if m else ""
        episode = episode or (m.group(2) if m else "")
        season = _seasonNum(show) or 1
        show = _clean(SEASON_WORD_RE.sub(" ", show)) or fallbackShow or _clean(label)
        if normalize and episode:
            title = "%s - %s" % (show, formatSxxExx(season, episode))
        else:
            title = label
        return {"name": "category", "good_for_fav": True, "category": "q3_video", "title": title, "url": url, "icon": icon, "desc": desc,
                "s_title": show, "s_season": season, "s_episode": str(int(episode)) if episode else "", "meta_type": "tv", "meta_title": show}

    def _movieParams(self, label, url, icon, desc, normalize):
        title = _clean(label) or label
        year = YEAR_RE.search(title)
        year = year.group(1) if year else ""
        metaTitle = _clean(YEAR_RE.sub(" ", title)) or title
        dispTitle = label
        if normalize:
            dispTitle = "%s (%s)" % (metaTitle, year) if year else metaTitle
        return {"name": "category", "good_for_fav": True, "category": "q3_video", "title": dispTitle, "url": url, "icon": icon, "desc": desc,
                "meta_type": "movie", "meta_title": metaTitle, "meta_year": year}

    def _boxes(self, data):
        # (url, label, icon, episode number) of the <li class="EpisodeBlock"> / "EpisodeBlock_serie" cards
        block = self.cm.ph.getDataBeetwenNodes(data, ("<main", ">", "SiteInner"), ("</main", ">"), False)[1] or data
        out = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenNodes(block, ("<li", ">", "EpisodeBlock"), ("</li", ">")):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            if not href:
                continue
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="EpisodeBlockTitle">(.*?)</div>')[0])
            if not label:
                label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not label:
                continue
            number = self.cm.ph.getSearchGroups(item, r'(?s)class="EPNumber(?:Card)?">.*?<span>\s*(\d+)\s*</span>')[0]
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+?(?:data-image|data-src|src)="([^"]+)"')[0]
            out.append((url, label, self._icon(icon), number))
        return out

    @staticmethod
    def _pageTpl(baseUrl):
        return baseUrl + ("&" if "?" in baseUrl else "?") + "page={page}"

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem["url"])
        pageTpl = self._pageTpl(baseUrl)
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("Q3isk.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        boxes = self._boxes(data)
        for url, label, icon, number in boxes:
            kind = self._kind(url)
            if kind == "serie":
                show = _clean(label) or label
                self.addDir({"name": "category", "good_for_fav": True, "category": "q3_series", "title": show if normalize else label, "url": url,
                             "icon": icon, "s_title": show, "meta_type": "tv", "meta_title": show})
            elif kind == "episode" or number or "الحلقة" in label:
                self.addVideo(self._episodeParams(label, url, icon, "", normalize, episode=number))
            else:
                self.addVideo(self._movieParams(label, url, icon, "", normalize))

        # the site only links the next page ("?page=N+1"), it never names the last one - and it links it on the
        # last page too, so a short page (fewer cards than a full one: 40 in the lists, 20 in search) ends the list
        pageSize = max(cItem.get("page_size", 0), len(boxes))
        hasNext = len(boxes) >= max(MIN_PAGE_SIZE, pageSize) and bool(re.search(r'href="[^"]*[?&]page=%d(?:[&"])' % (page + 1), data))
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl, "page_size": pageSize})
        addPagingItems(self, listItem, page, hasNext, 0, pageTpl)

    def _seriesEpisodes(self, url, show, icon, desc, metaTitle, normalize):
        sts, data = self.getPage(url)
        if not sts:
            return []
        episodes = []
        for epUrl, label, epIcon, number in self._boxes(data):
            if self._kind(epUrl) != "episode":
                continue
            params = self._episodeParams(label, epUrl, epIcon or icon, desc, normalize, show, number)
            params.update({"s_title": show, "meta_title": metaTitle or show})
            if normalize and params["s_episode"]:
                params["title"] = "%s - %s" % (show, formatSxxExx(params["s_season"], params["s_episode"]))
            episodes.append(params)
        episodes.sort(key=lambda p: int(p["s_episode"]) if p["s_episode"] else 0)
        return episodes

    def listEpisodes(self, cItem):
        page = cItem.get("page", 1)
        url = self._relocate(cItem)
        printDBG("Q3isk.listEpisodes [%s]" % url)
        if not url:
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        episodes = self._seriesEpisodes(url, show, cItem.get("icon", ""), cItem.get("desc", ""), cItem.get("meta_title", ""), IsMediaNamingNormalized())
        if not episodes:
            SetIPTVPlayerLastHostError(_("No episodes found."))
            return
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Q3isk.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        baseUrl = self.getFullUrl("/search?query=%s" % urllib_quote(searchPattern.strip(), safe=""))
        cItem.update({"category": "list_items", "url": baseUrl, "base_url": baseUrl, "page": 1})
        self.listItems(cItem)

    def _relocate(self, cItem):
        # page url of a row; rows of the old *.3isq.cam site (favourites, history) -> the same title on this site
        url = self._canonUrl(cItem.get("url", ""))
        if not self._isLegacy(url):
            return url
        isEpisode = cItem.get("category") == "q3_video" and bool(cItem.get("s_episode"))
        wanted = "serie" if cItem.get("category") == "q3_series" or isEpisode else "movie"
        title = cItem.get("s_title") or cItem.get("meta_title") or cItem.get("title", "")
        printDBG("Q3isk._relocate [%s] -> %s [%s]" % (url, wanted, title))
        sts, data = self.getPage(self.getFullUrl("/search?query=%s" % urllib_quote(_clean(title), safe="")))
        target = ""
        for hitUrl, label, _icon, _number in self._boxes(data) if sts else []:
            if self._kind(hitUrl) == wanted and _fold(label) == _fold(title):
                target = hitUrl
                break
        if not target or not isEpisode:
            return target
        for params in self._seriesEpisodes(target, title, "", "", "", False):
            if params["s_episode"] == cItem["s_episode"]:
                return params["url"]
        return ""

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="hero-story">(.*?)</p>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'(?s)class="hero-poster">.*?data-image="([^"]+)"')[0]
        return story, self._icon(poster) if poster else ""

    def getLinksForVideo(self, cItem):
        pageUrl = self._relocate(cItem)
        printDBG("Q3isk.getLinksForVideo [%s]" % pageUrl)
        if not pageUrl:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        # the servers are only listed after the page's play button posted token=play
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=pageUrl)
        sts, data = self.getPage(pageUrl, params, {"token": "play"})
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        block = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "servers-list"), ("</ul", ">"), False)[1]
        urltab = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenNodes(block, ("<li", ">", "server-item"), ("</li", ">")):
            url = self.cm.ph.getSearchGroups(item, r'data-link="([^"]+)"')[0].replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            name = self.cleanHtmlStr(item) or self.up.getHostName(url)
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("Q3isk.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Q3isk.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster = "", ""
        url = cItem.get("url", "")
        if not self._isLegacy(url):
            sts, data = self.getPage(url)
            if sts:
                story, poster = self._siteInfo(data)
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        plot = meta.get("plot", "")
        text = plot or story or _stripColors(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": meta.get("info", {})}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Q3isk.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "q3_series":
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
        CHostBase.__init__(self, Q3isk(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("q3isk")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("q3_video", "q3_series")
