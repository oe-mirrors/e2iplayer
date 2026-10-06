# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - revived for akwam.ss (old ak.sv was down in Sept 2026)
#   Rewrite against the current site (same "O2 CMS" layout as before):
#   - lists /movies, /series, /shows (+ section/category filters read live from the page),
#     /recent and /search?q=..; First page / Jump / Next page (?page=N, last page from the pager,
#     "Next page" only with rel="next"); /mix (rar/zip albums) left out - nothing playable there;
#     the /old archive is its own host (hostakwamold)
#   - movies, TV shows and episodes are VIDEO rows keyed on their page url; the direct
#     downet.net MP4 links (signed, valid ~1 day) are fetched in getLinksForVideo from the
#     /watch/<id>/... page of each quality tab - no hoster embeds, need_resolve 0
#   - series -> episode list (ascending); season taken from the "الموسم X / الجزء X / جX" suffix
#   - watched flag (stable movie:/series:/episode:/shows: ids), downloaded flag (canonical
#     percent-encoded page url), name normalisation ("Title (Year)", "Show - SxxExx"),
#     sidecar, INFO via moviemeta + the site's own story/poster/fields, favourites
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://akwam.ss/"


# Enigma2 colour codes ("\c00RRGGBB") - only for the list description, never in sidecar / INFO text
COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


# Arabic ordinals used in season labels ("الموسم الثاني"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالث", 3), ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8),
    ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:^|\s)(?:الموسم|الجزء|ج)\s*(\d+|%s)\s*$" % "|".join(o[0] for o in SEASON_ORDINALS))
# site words that do not belong into a title / file name
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|اون لاين|أون لاين|مشاهدة|فيلم|مسلسل|كامل|كاملة|بجودة عالية)(?=\s|$)")
DUB_WORD = "مدبلج"
# "<span>السنة : 2025</span>" fields of a title page -> INFO keys
INFO_FIELDS = (("year", "السنة"), ("language", "اللغة"), ("subtitles", "الترجمة"), ("quality", "جودة"),
               ("duration", "مدة"), ("country", "انتاج"))


class Akoam(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "akoam", "cookie": "akoam.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/akoam.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "ak_section", "title": _("Movies"), "url": self.getFullUrl("movies")},
            {"category": "ak_section", "title": _("Series"), "url": self.getFullUrl("series")},
            {"category": "ak_section", "title": _("TV Shows"), "url": self.getFullUrl("shows")},
            {"category": "list_items", "title": _("Recently added"), "url": self.getFullUrl("recent")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("akoam")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        # the site links the same page raw-Arabic or percent-encoded - one ASCII form for
        # requests, the downloaded marker and favourites
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        url = self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    @staticmethod
    def _pageId(url):
        # ("movie"|"series"|"episode"|"shows"|"mix", "<id>") from a content url
        m = re.search(r"/(movie|series|episode|shows|mix)/(\d+)", url or "")
        return (m.group(1), m.group(2)) if m else ("", "")

    @staticmethod
    def _clean(text):
        text = JUNK_RE.sub(" ", text or "")
        return re.sub(r"\s+", " ", text).strip(" -:|")

    def _splitSeason(self, title):
        # "Reacher الموسم الرابع مدبلج" -> ("Reacher مدبلج", 4); no season label -> (title, 1)
        title = self._clean(title)
        dub = DUB_WORD in title
        if dub:
            title = re.sub(r"\s+", " ", title.replace(DUB_WORD, " ")).strip()
        season = 1
        m = SEASON_RE.search(title)
        if m:
            val = m.group(1)
            season = int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 1)
            title = title[:m.start()].strip()
        if dub:
            title = "%s %s" % (title, DUB_WORD)
        return title, season

    @staticmethod
    def _metaTitle(title):
        return re.sub(r"\s+", " ", (title or "").replace(DUB_WORD, " ")).strip()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("category", "") not in ("ak_video", "ak_series"):
                return ""
            kind, pid = self._pageId(cItem.get("url", ""))
            return "%s:%s" % (kind, pid) if pid else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # menus
    ###################################################
    def listSection(self, cItem):
        printDBG("Akoam.listSection [%s]" % cItem.get("url", ""))
        baseUrl = cItem["url"]
        params = dict(cItem)
        params.update({"good_for_fav": True, "category": "list_items", "title": _("All")})
        self.addDir(params)
        sts, data = self.getPage(baseUrl)
        if not sts:
            return
        for name, label in (("section", ""), ("category", _("Genre"))):
            block = self.cm.ph.getSearchGroups(data, r'(?s)<select[^>]+name="%s"[^>]*>(.*?)</select>' % name)[0]
            for value, title in re.findall(r'<option value="(\d+)"[^>]*>([^<]+)<', block):
                if value == "0":
                    continue
                title = self.cleanHtmlStr(title)
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "list_items", "title": ("%s: %s" % (label, title)) if label else title,
                               "url": "%s?%s=%s" % (baseUrl, name, value)})
                self.addDir(params)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or re.sub(r"[?&]page=\d+", "", self._canonUrl(cItem["url"]))
        pageUrlTpl = baseUrl + ("&" if "?" in baseUrl else "?") + "page={page}"
        url = baseUrl if page <= 1 else pageUrlTpl.format(page=page)
        printDBG("Akoam.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="entry-box entry-box-1">', '<div class="col-'):
            url = self._canonUrl(self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0])
            kind, pid = self._pageId(url)
            if kind not in ("movie", "series", "shows") or (kind, pid) in seen:
                continue
            seen.add((kind, pid))
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3[^>]*>(.*?)</h3>')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<span class="label rating">(.*?)</span>')[0])
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<span class="label quality">(.*?)</span>')[0])
            year = self.cm.ph.getSearchGroups(item, r'badge-secondary[^>]*>\s*(\d{4})\s*<')[0]
            genres = [self.cleanHtmlStr(g) for g in re.findall(r'badge-light[^>]*>([^<]+)<', item)]
            fields = ((_("Rating"), rating, "green"), (_("Quality"), quality, "yellow"), (_("Year"), year, "cyan"), (_("Genres"), ", ".join(genres), "magenta"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])

            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon), "desc": desc}
            if kind == "series":
                show, season = self._splitSeason(title)
                params.update({"category": "ak_series", "title": title, "s_title": show, "s_season": season,
                               "meta_type": "tv", "meta_title": self._metaTitle(show), "meta_year": year})
                self.addDir(params)
                continue
            if normalize:
                dispTitle = self._clean(title)
                if kind == "movie" and year and year not in dispTitle:
                    dispTitle = "%s (%s)" % (dispTitle, year)
            else:
                dispTitle = title
            params.update({"category": "ak_video", "title": dispTitle})
            if kind == "movie":
                params.update({"meta_type": "movie", "meta_title": self._metaTitle(self._clean(title)), "meta_year": year})
            self.addVideo(params)

        # pager: rel="next" = there is a next page, the highest "page=N" = the last page
        pager = data[data.find('<ul class="pagination'):] if '<ul class="pagination' in data else ""
        hasNext = bool(seen) and 'rel="next"' in pager
        lastPage = max([int(n) for n in re.findall(r'href="[^"]*[?&](?:amp;)?page=(\d+)"', pager)] + [page])
        listItem = dict(cItem)
        # list_items, not the copied "search": that would rebuild page 1 from the search pattern
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageUrlTpl)

    def listEpisodes(self, cItem):
        printDBG("Akoam.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'id="series-episodes"', '<footer', False)[1]
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", cItem.get("title", ""))
        season = cItem.get("s_season", 1)
        episodes = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="bg-primary2', '</picture>'):
            m = re.search(r'<h2[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', item, re.DOTALL)
            if not m:
                continue
            url = self._canonUrl(m.group(1))
            kind, pid = self._pageId(url)
            if kind != "episode" or pid in seen:
                continue
            seen.add(pid)
            label = self.cleanHtmlStr(m.group(2))
            epNum = self.cm.ph.getSearchGroups(label, r"حلقة\s*(\d+)")[0] or self.cm.ph.getSearchGroups(urllib_unquote(url), r"(\d+)/?$")[0]
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            date = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)entry-date[^>]*>(.*?)</p>')[0])
            if normalize and epNum:
                title = "%s - %s" % (show, formatSxxExx(season, epNum))
            else:
                title = label or show
            episodes.append({"name": "category", "good_for_fav": True, "category": "ak_video", "title": title, "url": url,
                             "icon": self.getFullIconUrl(icon) if icon else cItem.get("icon", ""), "desc": date,
                             "s_title": show, "s_season": season, "s_episode": epNum,
                             "meta_type": "tv", "meta_title": cItem.get("meta_title", ""), "meta_year": cItem.get("meta_year", "")})
        episodes.reverse()  # the site lists the newest first
        for params in episodes:
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Akoam.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("search?q=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cm.ph.getSearchGroups(data, r'(?s)<div class="text-white font-size-18"[^>]*>(.*?)</div>')[0]
        story = self.cleanHtmlStr(story)
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, poster

    def getLinksForVideo(self, cItem):
        printDBG("Akoam.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]

        # quality tabs: <a href="#tab-5">1080p</a> ... <div class="tab-content quality" id="tab-5"> ... /watch/ link
        labels = dict(re.findall(r'<a href="#(tab-\d+)"[^>]*>([^<]+)<', data))
        watch = []
        for block in data.split('class="tab-content quality"')[1:]:
            tab = self.cm.ph.getSearchGroups(block, r'id="(tab-\d+)"')[0]
            href = self.cm.ph.getSearchGroups(block, r'href="([^"]+/watch/[^"]+)"')[0]
            if href:
                watch.append((self.cm.ph.getSearchGroups(labels.get(tab, ""), r"(\d{3,4})")[0], self._canonUrl(href)))

        # one /watch/ page usually carries the <source> of every quality; the others only when missing
        sources = {}
        subtitles = []
        for size, href in watch:
            if size and size in sources:
                continue
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=pageUrl)
            sts, page = self.getPage(href, params)
            if not sts:
                continue
            video = self.cm.ph.getDataBeetwenMarkers(page, "<video", "</video>", False)[1]
            for src in re.findall(r"<source[^>]+>", video):
                # the file names hold raw spaces and Arabic letters ("/download/<id>/<hash>/Zanb Insani ... .mp4")
                url = self.cm.iriToUri(self.cm.ph.getSearchGroups(src, r'src="([^"]+)"')[0].strip()).replace(" ", "%20")
                if not self.cm.isValidUrl(url):
                    continue
                key = self.cm.ph.getSearchGroups(src, r'size="(\d+)"')[0] or size or "#%d" % (len(sources) + 1)
                if key not in sources:
                    sources[key] = url
            for trk in re.findall(r"<track[^>]+>", video):
                sub = self.getFullUrl(self.cm.ph.getSearchGroups(trk, r'src="([^"]+)"')[0])
                if self.cm.isValidUrl(sub) and sub not in [s["url"] for s in subtitles]:
                    lang = self.cm.ph.getSearchGroups(trk, r'srclang="([^"]+)"')[0] or "ar"
                    subtitles.append({"title": self.cm.ph.getSearchGroups(trk, r'label="([^"]+)"')[0] or lang, "url": sub, "lang": lang,
                                      "format": "vtt" if ".vtt" in sub else "srt"})

        urltab = []
        meta = {"User-Agent": self.HEADER.get("User-Agent"), "Referer": self.MAIN_URL}
        if subtitles:
            meta["external_sub_tracks"] = subtitles
        for key in sorted(sources, key=lambda k: int(k) if k.isdigit() else 0, reverse=True):
            name = ("Akwam %sp" % key) if key.isdigit() else ("Akwam %s" % key)
            urltab.append({"name": name, "url": strwithmeta(sources[key], dict(meta)), "need_resolve": 0})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Akoam.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""))
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster = self._siteInfo(data)
            for key, word in INFO_FIELDS:
                val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"<span>\s*%s[^:<]*:\s*([^<]+)<" % word)[0])
                if val:
                    info[key] = val
            genres = [self.cleanHtmlStr(g) for g in re.findall(r'<a href="[^"]+/(?:movies|series|shows)\?category=\d+"[^>]*>([^<]+)<', data)]
            if genres:
                info["genres"] = ", ".join(genres[:6])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or _stripColors(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
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
        printDBG("Akoam.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "ak_section":
            self.listSection(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "ak_series":
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
        CHostBase.__init__(self, Akoam(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("akoam")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("ak_video", "ak_series")
