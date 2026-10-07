# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# Original File from: 01/12/2025 - popking (odem2014)
# Previous change: 04/04/2026 - Mohamed Elsafty (angel_heart)
# 03.10.2026 - revived for topcinema.vip (topcima.online 301s there)
#   - menus checked against the live site: "Arabic plays" slug fixed (مسرحيات-عربية), the dead
#     "Turkish 2" series category and the download-only "complated series" page dropped
#   - movies, plays, shows and episodes are VIDEO rows keyed on their page url; the hoster
#     embeds of the /watch/ page are fetched in getLinksForVideo (duplicates removed, equal
#     hoster names numbered, no colour codes) and resolved by urlparser
#   - series categories / search: one folder per show+season (episode page or /series/ page)
#     -> season list when the show has several seasons -> episodes (ascending)
#   - movie collections (/assemblies/) -> the movies of the collection
#   - paging via iptvpaging (First page / Jump / Next page with the last page number)
#   - watched flag, downloaded flag (canonical page url), name normalisation ("Title (Year)",
#     "Show - SxxExx"), sidecar, INFO via moviemeta + the site's story/poster/fields, favourites
###################################################
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://topcinema.vip/"


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
BIDI_MARKS = ("\xe2\x80\x8e", "\xe2\x80\x8f") if isPY2() else (u"‎", u"‏")
# "<span>نوع الفيلم : </span> <a>..</a>" fields of a title page -> INFO keys
INFO_FIELDS = (("genres", ("نوع",)), ("year", ("تاريخ", "السنة")), ("language", ("لغة",)), ("quality", ("جودة",)),
               ("country", ("الدولة", "البلد")), ("duration", ("مدة",)), ("director", ("المخرج",)), ("actors", ("بطولة", "الممثلين")))


class TopCinema(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "topcinema", "cookie": "topcinema.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/topcinema.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        cat = self._catUrl
        self.MENU = [
            {"category": "tc_folder", "title": _("Movies"), "tc_folder": "movies"},
            {"category": "tc_folder", "title": _("Series"), "tc_folder": "series"},
            {"category": "list_items", "title": _("TV Shows"), "url": cat("برامج-تلفزيونية"), "tc_mode": "series"},
            {"category": "list_items", "title": _("Arabic plays"), "url": cat("مسرحيات-عربية")},
            {"category": "list_items", "title": _("WWE shows"), "url": cat("مصارعه")},
            {"category": "list_items", "title": _("Recently added"), "url": self.getFullUrl("last/"), "tc_mode": "last"},
        ] + self.searchItems()
        self.FOLDERS = {
            "movies": [
                {"title": _("Arabic"), "url": cat("افلام-عربي")},
                {"title": _("English"), "url": cat("افلام-اجنبي")},
                {"title": _("English dubbed"), "url": cat("افلام-اجنبية-مدبلجة")},
                {"title": _("Turkish"), "url": cat("افلام-تركية")},
                {"title": _("Asian"), "url": cat("افلام-اسيوية")},
                {"title": _("Indian"), "url": cat("افلام-هندى")},
                {"title": "Netflix", "url": cat("افلام-netfilx")},
                {"title": _("Anime"), "url": cat("افلام-انمي")},
                {"title": _("Cartoons"), "url": cat("افلام-كرتون")},
                {"title": _("Dubbed"), "url": cat("افلام-مدبلجة")},
                {"title": _("Classic"), "url": cat("افلام-كلاسيكيه")},
                {"title": _("Documentary"), "url": cat("افلام-وثائقية")},
                {"title": _("Top IMDb"), "url": self.getFullUrl("imdb/")},
                {"title": _("Movie collections"), "url": self.getFullUrl("assemblies/")},
            ],
            "series": [
                {"title": _("Arabic"), "url": cat("مسلسلات-عربي")},
                {"title": _("English"), "url": cat("مسلسلات-اجنبي")},
                {"title": _("Turkish"), "url": cat("مسلسلات-تركية")},
                {"title": _("Asian"), "url": cat("مسلسلات-اسيوية")},
                {"title": _("Indian"), "url": cat("مسلسلات-هندية")},
                {"title": _("Korean"), "url": cat("مسلسلات-كوريه")},
                {"title": _("Latino"), "url": cat("مسلسلات-لاتينية")},
                {"title": "Netflix", "url": cat("مسلسلات-netfilx")},
                {"title": _("Ramadan") + " 2026", "url": cat("مسلسلات-رمضان-2026")},
                {"title": _("Anime"), "url": cat("مسلسلات-انمي")},
                {"title": _("Cartoons"), "url": cat("مسلسلات-كرتون")},
                {"title": _("Top IMDb"), "url": self.getFullUrl("top-rating-imdb-series/")},
            ],
        }
        self.watchedHelper = IPTVWatchedHelper("topcinema")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def _catUrl(self, slug):
        return self._canonUrl(self.getFullUrl("category/%s/" % slug))

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        # the site links the same page raw-Arabic or percent-encoded (lower case) - one ASCII
        # form for requests, the watched / downloaded markers and favourites
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if not url:
            return ""
        url = self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _icon(self, block):
        icon = self.cm.ph.getSearchGroups(block, r'data-src="([^"]+)"')[0]
        if not icon:
            icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="(http[^"]+)"')[0]
        return self._canonUrl(icon) if icon else ""

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

    def _pageTpl(self, url):
        base = re.sub(r"/page/\d+/?", "/", url.split("?")[0])
        if not base.endswith("/"):
            base += "/"
        return base + "page/{page}/"

    @staticmethod
    def _lastPage(pagination, page):
        pagination = pagination.replace("&#038;", "&").replace("&amp;", "&")
        nums = [int(x) for x in re.findall(r"(?:/page/|[?&]page=)(\d+)", pagination)]
        return max(nums + [page])

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("category", "") not in ("tc_video", "tc_series"):
                return ""
            path = urllib_unquote(self._canonUrl(cItem.get("url", ""))).split("://", 1)[-1].split("/", 1)[-1].strip("/")
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
        for item in self.FOLDERS.get(cItem.get("tc_folder", ""), []):
            params = {"name": "category", "category": "list_items", "good_for_fav": True, "title": item["title"], "url": item["url"]}
            if cItem.get("tc_folder") == "series":
                params["tc_mode"] = "series"
            self.addDir(params)

    def _itemDesc(self, block):
        fields = ((_("Genre"), "genre"), (_("Quality"), "quality"), (_("Year"), "meta-year"), (_("IMDb"), "imdbRating"), (_("Runtime"), "meta-runtime"))
        parts = []
        for label, cls in fields:
            val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<li class="%s">(.*?)</li>' % cls)[0])
            if val:
                parts.append("%s%s:%s %s" % (E2ColoR("yellow"), label, E2ColoR("white"), val))
        return " | ".join(parts)

    def listItems(self, cItem):
        printDBG("TopCinema.listItems [%s]" % cItem.get("url", ""))
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        page = cItem.get("page", 1)
        mode = cItem.get("tc_mode", "")
        if "/assemblies/" in url and "/assemblies/page/" not in url and url.rstrip("/") != self.getFullUrl("assemblies").rstrip("/"):
            # one collection page: only its own movies, not the "other collections" tab
            data = self.cm.ph.getDataBeetwenMarkers(data, 'id="series-movies"', "</section>", False)[1]
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, '<main class="site-inner', "</main>", False)[1] or data
        normalize = IsMediaNamingNormalized()
        seen, seenSeasons = set(), set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="Small--Box', "</a>"):
            itemUrl = self._canonUrl(self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0])
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
            if ep and mode != "last":
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
            year = titleYear or year
            if normalize:
                title = "%s (%s)" % (metaTitle, year) if year else clean
            else:
                title = rawTitle
            params.update({"category": "tc_video", "title": title, "meta_type": "movie", "meta_title": self._metaTitle(metaTitle), "meta_year": year})
            self.addVideo(params)

        if not seen:
            return
        pagination = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination', "</div>", False)[1]
        hasNext = "next page-numbers" in pagination
        tpl = cItem.get("tc_tpl") or self._pageTpl(url)
        cItem = dict(cItem, tc_tpl=tpl)
        if cItem.get("category") != "list_items":
            # search: the pager rows must list the pages, not search again
            cItem.update({"category": "list_items", "search_item": False})
        addPagingItems(self, cItem, page, hasNext, self._lastPage(pagination, page), tpl)

    def _episodeParams(self, ep, rawTitle, normalize):
        if normalize:
            title = "%s - %s" % (ep["show"], formatSxxExx(ep["season"], ep["episode"]))
            if ep["name"]:
                title = "%s - %s" % (title, ep["name"])
            if DUB_WORD in rawTitle:
                title = "%s %s" % (title, DUB_WORD)
        else:
            title = rawTitle
        return {"category": "tc_video", "title": title, "s_title": ep["show"], "s_season": ep["season"], "s_episode": ep["episode"], "meta_type": "tv"}

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
                url = self._canonUrl(self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0])
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
        episodes, seen, seenEpisodes = [], set(), set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<a ", "</a>"):
            url = self._canonUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
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
            episodes.append(params)
        episodes.sort(key=lambda p: (p["s_season"], int(p["s_episode"])))
        for params in episodes:
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TopCinema.listSearchResult [%s]" % searchPattern)
        query = urllib_quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem.update({"url": self.getFullUrl("?s=%s" % query), "tc_tpl": self.getFullUrl("?s=%s&page={page}" % query), "tc_mode": "", "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="story clearfix">', "</div>", False)[1])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'(?s)<div class="image">.*?data-src="([^"]+)"')[0]
        info = {}
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="RightTaxContent">', "</ul>", False)[1]
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
        pageUrl = self._canonUrl(cItem.get("url", ""))
        if not pageUrl:
            return []
        sts, data = self.getPage(pageUrl.rstrip("/") + "/watch/")
        if not sts or "data-watch" not in data:
            sts, data = self.getPage(pageUrl)
            if not sts:
                return []
        story = self._siteInfo(data)[0]
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="watch"', "</ul>", False)[1] or data
        servers, seen = [], set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            url = self.cm.ph.getSearchGroups(item, r'data-watch="([^"]+)"')[0].replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<span[^>]*>([^<]+)</span>')[0]) or self.up.getHostName(url)
            servers.append((name, url))
        counts = {}
        for name, url in servers:
            counts[name] = counts.get(name, 0) + 1
        numbers = {}
        urltab = []
        for name, url in servers:
            if counts[name] > 1:
                numbers[name] = numbers.get(name, 0) + 1
                name = "%s %d" % (name, numbers[name])
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))

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
        printDBG("TopCinema.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
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
