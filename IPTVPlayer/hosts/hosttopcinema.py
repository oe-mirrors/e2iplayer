# -*- coding: utf-8 -*-
LAST_MODIFIED = "09.11.2026"
# Original File from: 01/12/2025 - popking (odem2014)
# Previous change: 04/04/2026 - Mohamed Elsafty (angel_heart)
# 09.11.2026 - moved to the original site topcinemaa.vip (domain followed via redirect, proxy / alternative domain options)
###################################################

import re
from os.path import isfile as pathIsfile

from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getImage169, getSeasonImages169, isImages169
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.topcinema_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.topcinema_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.topcinema_proxy))
    if config.plugins.iptvplayer.topcinema_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.topcinema_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://topcinemaa.vip/"


SITE_URL_RE = re.compile(r"^https?://(?:www\.)?topcinemaa\.[a-z]+/", re.I)
# Enigma2 colour codes ("\c00RRGGBB") - only for the list description, never in sidecar / INFO text
COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


# Arabic ordinals used in season labels ("الموسم الثاني"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الاولي", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6), ("السادس", 6),
    ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:^|\s)(?:الموسم|الجزء|ج)\s*(\d+|%s)(?=\s|$)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"(?:^|\s)(?:الحلقة|حلقة)\s*(\d+)(.*)$")
# leading content-type words of the site titles ("فيلم X", "مسلسل X", "انمي فيلم X" ...)
PREFIX_RE = re.compile(r"^(?:(?:فيلم|مسلسل|برنامج|عرض|انمي|سلسلة افلام|سلاسل افلام)\s+)+")
# site words that do not belong into a title / file name
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|اون لاين|أون لاين|مشاهدة|كامل|كاملة|والاخير|والاخيرة|والأخيرة|HD|hd)(?=\s|$)")
# episode-name suffixes that are only the episode number spelled out ("الحلقة 30 الثلاثون والاخيرة")
EP_ORDINAL_RE = re.compile(r"^(?:ال(?:اولي|اولى|أولى|ثاني|ثانية|ثالث|ثالثة|رابع|رابعة|خامس|خامسة|سادس|سادسة|سابع|سابعة|ثامن|ثامنة|تاسع|تاسعة|عاشر|عاشرة|حادي|حادية|عشرون|ثلاثون|اربعون|أربعون|خمسون|ستون|سبعون|ثمانون|تسعون|مائة|مئة))(?:\s|$)")
YEAR_RE = re.compile(r"\(?\s*(?<![\d.])((?:19|20)\d{2})(?![\d.])\s*\)?")
DUB_WORD = "مدبلج"
# left-to-right / right-to-left marks the site puts in front of some episode names
BIDI_MARKS = (ensure_str(u"\u200e"), ensure_str(u"\u200f"))
# "<span>نوع الفيلم : </span> <a>..</a>" fields of a title page -> INFO keys
INFO_FIELDS = (("genres", ("نوع",)), ("year", ("تاريخ", "السنة")), ("language", ("لغة",)), ("quality", ("جودة",)), ("released", ("موعد",)),
               ("country", ("دولة", "البلد")), ("duration", ("مدة", "توقيت")), ("director", ("المخرج",)), ("actors", ("بطولة", "الممثلين")),
               ("category", ("قسم",)))


class TopCinema(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    DOMAIN_CACHE_FOR = None  # the "alternative domain" setting the cached domain belongs to
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "tc_mode", "tc_season", "first_url", "s_title", "s_year", "s_season", "s_episode", "meta_type", "meta_title", "meta_year", "meta_season", "meta_episode")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "topcinema", "cookie": "topcinema.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/topcinema.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("topcinema")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.topcinema_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        domain = config.plugins.iptvplayer.topcinema_alt_domain.value.strip()
        if TopCinema.DOMAIN_CACHE and TopCinema.DOMAIN_CACHE_FOR == domain:
            self.MAIN_URL = TopCinema.DOMAIN_CACHE
            return
        self.MAIN_URL = domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul()
        sts, _data = self.getPage(self.MAIN_URL)
        finalUrl = self.cm.meta.get("url", self.MAIN_URL)
        if sts and SITE_URL_RE.match(finalUrl):
            # the site moves between topcinema.* domains -> the one the old domain redirects to
            self.MAIN_URL = self.cm.getBaseUrl(finalUrl)
            TopCinema.DOMAIN_CACHE = self.MAIN_URL
            TopCinema.DOMAIN_CACHE_FOR = domain

    def _ajax(self, url, referer, post_data=None):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, **{"X-Requested-With": "XMLHttpRequest", "Referer": referer, "Accept": "*/*"})
        if post_data:
            params["header"]["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        sts, data = self.getPage(url, params, post_data)
        return data if sts and data else ""

    def _rebase(self, url):
        # urls of favourites / older lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return SITE_URL_RE.sub(self.MAIN_URL, url)

    def _icon(self, block):
        icon = self.cm.ph.getSearchGroups(block, r'data-src="([^"]+)"')[0]
        if not icon:
            icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="(http[^"]+)"')[0]
        return self.getFullIconUrl(icon) if icon else ""

    @staticmethod
    def _clean(text):
        for mark in BIDI_MARKS:
            text = (text or "").replace(mark, "")
        text = PREFIX_RE.sub("", (text or "").strip())
        text = JUNK_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip(" -:|")

    @staticmethod
    def _splitYear(title):
        # "Verity 2026" / "انستونا ( 2022 )" -> ("Verity", "2026"); a date like 22.06.2026 is no year
        years = list(YEAR_RE.finditer(title or ""))
        if not years:
            return title, ""
        m = years[-1]
        rest = re.sub(r"\s+", " ", (title[:m.start()] + " " + title[m.end():])).strip(" -:|")
        return (rest or title), m.group(1)

    def _parseEpisode(self, raw):
        # "مسلسل Red Queen الموسم الثاني الحلقة 6 والاخيرة مترجمة" -> show "Red Queen", season 2, episode 6
        text = self._clean(raw)
        m = EPISODE_RE.search(text)
        if not m:
            return None
        head, epNum, rest = text[:m.start()].strip(), m.group(1), m.group(2).strip(" -:|")
        show, season = self._splitSeason(head)
        if rest and EP_ORDINAL_RE.search(rest):
            rest = ""
        return {"show": show, "season": season, "episode": epNum, "name": rest, "head": self.cleanHtmlStr(re.split(r"\s(?:الحلقة|حلقة)\s*\d", raw)[0])}

    def _splitSeason(self, title):
        # "Reacher الموسم الرابع" -> ("Reacher", 4); no season label -> (title, 1)
        title = self._clean(title)
        season = 1
        m = SEASON_RE.search(title)
        if m:
            val = m.group(1)
            season = int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 1)
            title = (title[:m.start()] + " " + title[m.end():]).strip()
        return re.sub(r"\s+", " ", title).strip(" -:|"), season

    @staticmethod
    def _metaTitle(title):
        return re.sub(r"\s+", " ", (title or "").replace(DUB_WORD, " ")).strip()

    @staticmethod
    def _pageUrlTpl(url):
        # .../films-streaming/page/{page}/ , .../films-streaming/comedie/page/{page}/
        base, query = (url.split("?", 1) + [""])[:2]
        base = re.sub(r"/page/\d+/?$", "/", base).rstrip("/").replace("{", "{{").replace("}", "}}")
        query = query.replace("{", "{{").replace("}", "}}")
        return base + "/page/{page}/" + ("?" + query if query else "")

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    def getFullIconUrl(self, url, currUrl=None):
        # posters on the site's own domain (/uploads/...) sit behind the same Cloudflare check as the pages
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        if not url.startswith("http"):
            return url
        meta = {}
        if SITE_URL_RE.match(url):
            meta["Referer"] = self.MAIN_URL or gettytul()
            try:
                # getCookieHeader logs tracebacks for a cookie file that does not exist yet
                cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if pathIsfile(self.COOKIE_FILE) else ""
                if cookieHeader:
                    meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
            except Exception:
                printExc()
        proxy = self.getProxy()
        if proxy:
            meta["iptv_http_proxy"] = proxy
        return strwithmeta(url, meta) if meta else url

    def getFavouriteData(self, cItem):
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)
    ###################################################
    # watched flag
    ###################################################

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("category", "") not in ("tc_video", "tc_series"):
                return ""
            path = urllib_unquote(self._rebase(cItem.get("url", ""))).split("://", 1)[-1].split("/", 1)[-1].strip("/")
            if not path:
                return ""
            return "%s:%s" % ("video" if cItem["category"] == "tc_video" else "folder", path)
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listFolder(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, cItem.get("marker", ""), ("</ul", ">"), False)[1]
        if not block:
            printDBG("TopCinema.listValue: filter block [%s] not found" % cItem.get("title", ""))
            return
        for url, title in re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', block):
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self._rebase(url)})
            self.addDir(params)

    def _itemDesc(self, block):
        fields = ((_("Genre"), "liList"), (_("Quality"), "ribbon"), (_("Year"), "meta-year"), (_("IMDb"), "fa fa-star"), (_("Runtime"), "meta-runtime"))
        parts = []
        for label, cls in fields:
            val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s) class="%s">(.*?)</(?:li>|div>)' % cls)[0])
            if val:
                parts.append("%s: %s" % (label, val))
        return " | ".join(parts)

    def listItems(self, cItem):
        printDBG("TopCinema.listItems [%s]" % cItem.get("url", ""))
        page = self._page(cItem)
        firstUrl = cItem.get("first_url") or cItem.get("url", "")
        mode = cItem.get("tc_mode", "")
        story = cItem.get("search_story")
        if story is not None:
            # the site's own search pages through offset
            pageUrlTpl = self.getFullUrl("/search/?query=%s&type=all&offset={page}" % urllib_quote_plus(story))
        else:
            pageUrlTpl = self._pageUrlTpl(firstUrl)
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else firstUrl)
        if not sts:
            return
        if "/assemblies/" in pageUrlTpl and "/assemblies/page/" not in pageUrlTpl and pageUrlTpl.rstrip("/") != self.getFullUrl("assemblies").rstrip("/"):
            # one collection page: only its own movies, not the "other collections" tab
            data = self.cm.ph.getDataBeetwenMarkers(data, ("<section", ">", "allseasonss"), "</section>", False)[1]
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, ("<main", ">", "site-inner"), "</main>", False)[1] or data
        normalize = IsMediaNamingNormalized()
        seen, seenSeasons = set(), set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, ("<div", ">", "Small--Box"), "</a>"):
            itemUrl = self._rebase(self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0])
            if not itemUrl or itemUrl in seen:
                continue
            seen.add(itemUrl)
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            if not rawTitle:
                rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3[^>]*>(.*?)</h3>')[0])
            if not rawTitle:
                continue
            year = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<li class="meta-year">(.*?)</li>')[0])
            params = {"name": "category", "good_for_fav": True, "url": itemUrl, "icon": self._icon(item), "desc": self._itemDesc(item)}
            if "/assemblies/" in itemUrl:
                params.update({"category": "list_items", "title": self._clean(rawTitle) if normalize else rawTitle})
                self.addDir(params)
                continue
            if "/series/" in itemUrl:
                show, season = self._splitSeason(rawTitle)
                hasSeason = bool(SEASON_RE.search(self._clean(rawTitle)))
                params.update({"category": "tc_series", "title": ("%s - %s" % (show, formatSxxExx(season)) if hasSeason else show) if normalize else rawTitle,
                               "s_title": show, "s_season": season, "tc_season": hasSeason,
                               "meta_type": "tv", "meta_title": self._metaTitle(show), "meta_year": year})
                self.addDir(params)
                continue
            ep = self._parseEpisode(rawTitle) if EPISODE_RE.search(rawTitle) else None
            if ep and mode != "last" and "?key=episodes" not in pageUrlTpl:
                # one folder per show+season - its episode page lists the season's episodes
                key = (ep["show"], ep["season"])
                if key in seenSeasons:
                    continue
                seenSeasons.add(key)
                params.update({"category": "tc_series", "title": "%s - %s" % (ep["show"], formatSxxExx(ep["season"])) if normalize else ep["head"],
                               "s_title": ep["show"], "s_season": ep["season"], "tc_season": False,
                               "meta_type": "tv", "meta_title": self._metaTitle(ep["show"]), "meta_year": year})
                self.addDir(params)
                continue
            if ep:
                params.update(self._episodeParams(ep, rawTitle, normalize))
                params.update({"meta_title": self._metaTitle(ep["show"]), "meta_year": year})
                self.addVideo(params)
                continue
            clean = self._clean(rawTitle)
            metaTitle, titleYear = self._splitYear(clean)
            if year and titleYear and titleYear != year:
                metaTitle, titleYear = clean, ""  # not the release year: a part of the name ("Blade Runner 2049")
            year = year or titleYear
            if normalize:
                title = "%s (%s)" % (metaTitle, year) if year else clean
            else:
                title = rawTitle
            params.update({"category": "tc_video", "title": title, "meta_type": "movie", "meta_title": self._metaTitle(metaTitle), "meta_year": year})
            self.addVideo(params)

        if not seen:
            return
        pager = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "paginate"), "</ul>", False)[1]
        pages = [int(n) for n in re.findall(r'href="[^"]*/page/(\d+)/[^"]*', pager) + re.findall(r"offset=(\d+)", pager)]
        lastPage = max(pages + [page])
        hasNext = "&raquo;" in pager or lastPage > page
        addPagingItems(self, dict(cItem, category="list_items", url=firstUrl, first_url=firstUrl), page, hasNext, lastPage, pageUrlTpl)
        for item in self.currList:
            # "First page" back to the list the user opened (the search's first page has no search_start)
            if item.get("image_type") == "FIRST":
                item["url"] = firstUrl

    def _episodeParams(self, ep, rawTitle, normalize):
        if normalize:
            title = "%s - %s" % (ep["show"], formatSxxExx(ep["season"], ep["episode"]))
            if ep["name"]:
                title = "%s - %s" % (title, ep["name"])
            if DUB_WORD in rawTitle:
                title = "%s %s" % (title, DUB_WORD)
        else:
            title = rawTitle
        return {"category": "tc_video", "title": title, "s_title": ep["show"], "s_season": ep["season"], "s_episode": ep["episode"], "meta_type": "tv",
                "meta_season": str(ep["season"]), "meta_episode": str(ep["episode"])}

    def listSeries(self, cItem):
        # show / season / episode page: several seasons -> season folders, else its episodes
        printDBG("TopCinema.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or self._splitSeason(cItem.get("title", ""))[0]
        if not cItem.get("tc_season"):
            block = self.cm.ph.getDataBeetwenMarkers(data, '<section class="allseasonss', "</section>", False)[1]
            seasons = []
            for item in self.cm.ph.getAllItemsBeetwenMarkers(block, '<div class="Small--Box', "</a>"):
                url = self._rebase(self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0])
                if not url or url in [s["url"] for s in seasons]:
                    continue
                label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
                num = self.cm.ph.getSearchGroups(item, r'(?s)class="epnum">\s*<span>[^<]*</span>\s*(\d+)')[0]
                season = int(num) if num else self._splitSeason(label)[1]
                seasons.append({"name": "category", "category": "tc_series", "good_for_fav": True, "url": url, "icon": self._icon(item) or cItem.get("icon", ""),
                                "title": "%s - %s" % (show, formatSxxExx(season)) if normalize else label, "desc": cItem.get("desc", ""),
                                "s_title": show, "s_season": season, "tc_season": True,
                                "meta_type": "tv", "meta_title": cItem.get("meta_title", ""), "meta_year": cItem.get("meta_year", "")})
            if len(seasons) > 1:
                seasons.sort(key=lambda s: s["s_season"])
                for params in seasons:
                    self.addDir(params)
                return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<section class="allepcont', "</section>", False)[1]
        episodes, seen, seenEpisodes, stills = [], set(), set(), {}
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<a ", "</a>"):
            url = self._rebase(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
            if not url or url in seen:
                continue
            seen.add(url)
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h2>(.*?)</h2>')[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            ep = self._parseEpisode(rawTitle) or {"show": show, "season": cItem.get("s_season", 1), "name": "", "head": rawTitle,
                                                  "episode": self.cm.ph.getSearchGroups(item, r'(?s)class="epnum">\s*<span>[^<]*</span>\s*(\d+)')[0]}
            if not ep["episode"]:
                continue
            # the folder knows show + season better than a single (sometimes shortened) episode label
            ep["show"] = show or ep["show"]
            if cItem.get("tc_season") or not ep.get("season"):
                ep["season"] = cItem.get("s_season", ep.get("season", 1))
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self._icon(item) or cItem.get("icon", ""), "desc": cItem.get("desc", ""),
                      "meta_title": cItem.get("meta_title", ""), "meta_year": cItem.get("meta_year", "")}
            params.update(self._episodeParams(ep, rawTitle, normalize))
            # the site sometimes has two posts of one episode - keep the first (newest) of them
            epKey = (params["s_season"], int(params["s_episode"]), DUB_WORD in rawTitle)
            if epKey in seenEpisodes:
                continue
            seenEpisodes.add(epKey)
            if isImages169():
                # a 16:9 still per episode (one lookup per season), the site's own icon where no service has one
                if params["s_season"] not in stills:
                    stills[params["s_season"]] = getSeasonImages169(params["meta_title"], params["meta_year"], params["s_season"])
                params["icon"] = stills[params["s_season"]].get(int(params["s_episode"])) or params["icon"]
            episodes.append(params)
        episodes.sort(key=lambda p: (p["s_season"], int(p["s_episode"])))
        for params in episodes:
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TopCinema.listSearchResult [%s]" % searchPattern)
        story = searchPattern.strip()
        url = self.getFullUrl("/search/?query=%s&type=all" % urllib_quote_plus(story))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "page": 1, "url": url, "first_url": url, "search_story": story})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "story"), "</p>", False)[1])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<img[^>]+src="(http[^"]+)"')[0] or self.cm.ph.getSearchGroups(data, r'(?s)<div class="image">.*?data-src="([^"]+)"')[0]
        info = {}
        block = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "infoAndWatch"), "</ul>", False)[1]
        for item in re.findall(r"(?s)<li[^>]*>(.*?)</li>", block):
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<span>(.*?)</span>")[0])
            values = [self.cleanHtmlStr(v) for v in re.findall(r"(?s)<a[^>]*>(.*?)</a>", item)]
            value = ", ".join([v for v in values if v][:6])
            if not label or not value:
                continue
            for key, words in INFO_FIELDS:
                if key not in info and any(w in label for w in words):
                    info[key] = value
                    break
        rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="imdbR[^"]*">(.*?)</div>')[0])
        if rating:
            info["rating"] = rating
        return story, poster, info

    def getLinksForVideo(self, cItem):
        printDBG("TopCinema.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._rebase(cItem.get("url", ""))
        if not pageUrl:
            return []
        sts, data = self.getPage(pageUrl.rstrip("/") + "/watch/")
        if not sts:
            return []
        referer = self.cm.meta.get("url", pageUrl)
        ajaxPath = self.cm.ph.getSearchGroups(data, r'''MyAjaxURL\s*=\s*['"]([^'"]+)['"]''')[0]
        if not ajaxPath:
            # without it every server call would go to the site's start page
            SetIPTVPlayerLastHostError(_('Could not read the server list of the page.'))
            return []
        ajaxURL = self.getFullUrl(ajaxPath)
        story = self._siteInfo(data)[0]
        block = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "watch--servers--list"), "</ul>", False)[1] or data
        servers, seen = [], set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            Sid = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''data-id=['"]([^'"]+)['"]''')[0])
            Serv = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''data-server=['"]([^'"]+)['"]''')[0])
            if not Sid or not Serv:
                continue
            frame = self._ajax(ajaxURL.rstrip("/") + "/Single/Server.php", referer, {"id": Sid, "i": Serv})
            url = self.cm.ph.getSearchGroups(frame, r'<iframe\s*src="([^"]+)"')[0].replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>'), ('</span', '>'), False)[1]) or self.up.getHostName(url)
            seen.add(url)
            servers.append((name, url))
        counts = {}
        for name, url in servers:
            counts[name] = counts.get(name, 0) + 1
        numbers = {}
        linksTab = []
        for name, url in servers:
            if counts[name] > 1:
                numbers[name] = numbers.get(name, 0) + 1
                name = "%s %d" % (name, numbers[name])
            linkMeta = {"Referer": self.MAIN_URL}
            if self.getProxy():
                linkMeta["iptv_http_proxy"] = self.getProxy()
            linksTab.append({"name": name, "url": strwithmeta(url, linkMeta), "need_resolve": 1})
        if not linksTab:
            SetIPTVPlayerLastHostError(_('This video is only on hosters E2iPlayer cannot play.'))
            return []
        # the moviemeta query of INFO: all services also for an Arabic title
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", ""), cItem.get("meta_title", ""), cItem.get("meta_year", ""), skip=(),
                                  season=cItem.get("meta_season", ""), episode=cItem.get("meta_episode", ""))
        return applySidecarToLinks(linksTab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story, metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("TopCinema.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("TopCinema.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""))
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        for key, value in meta.get("info", {}).items():
            info.setdefault(key, value)  # the site's own fields stay, the services fill what is missing
        plot = meta.get("plot", "")
        text = plot or story or _stripColors(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        if isImages169() and cItem.get("meta_type") and cItem.get("meta_title"):
            # the episode's 16:9 still (the title's backdrop for a film / show), else the poster
            icon = getImage169(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), cItem.get("meta_season", ""), cItem.get("meta_episode", "")) or icon
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
        printDBG("TopCinema.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            menu = [
                {"category": "tc_folder", "title": _("Movies"), "tc_mode": "movies", "marker": ("<li", ">", "menu-item-74")},
                {"category": "tc_folder", "title": _("Series"), "tc_mode": "series", "marker": ("<li", ">", "menu-item-112")},
                {"category": "tc_folder", "title": _("Asian"), "tc_mode": "asian", "marker": ("<li", ">", "menu-item-226592")},
                {"category": "tc_folder", "title": _("Anime"), "tc_mode": "anime", "marker": ("<li", ">", "menu-item-159")},
                {"category": "list_items", "title": _("Recently added"), "url": self.getFullUrl("recent/"), "tc_mode": "last"},
            ]
            self.listsTab(menu + self.searchItems(), {"name": "category"})
        elif category == "tc_folder":
            self.listFolder(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "tc_series":
            self.listSeries(self.currItem)
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
        CHostBase.__init__(self, TopCinema(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("topcinema")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("tc_video", "tc_series")
