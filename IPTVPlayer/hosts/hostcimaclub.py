# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - revived for w.cimacub.com (ciimaclub.club is dead, cimacub.com 301s here)
#   - categories read live from the site's "القسم" dropdown (movies / series & shows), home page
#     "latest", search (?s=..&page=n); First Page / Jump / Next page (n/last) from the page-numbers block
#   - movies are VIDEO rows keyed on their page url; the hoster embeds (<ul id="watch"> data-watch on
#     <page>/watch/) are fetched in getLinksForVideo and handed to urlparser, names numbered per hoster
#   - the site lists single episodes: one folder per show+season instead, opening the season's episode
#     list (ascending) plus "Other seasons" when the page links more than one season
#   - watched flag (movie/episode page url, season folders), downloaded flag (page url), favourites,
#     name normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the site's
#     story / genres / quality / year / poster
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://w.cimacub.com/"


# Arabic ordinals used in season labels ("الموسم الثاني"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6),
    ("السادس", 6), ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9),
    ("العاشرة", 10), ("العاشر", 10),
]
_ORD_RE = "|".join(o[0] for o in SEASON_ORDINALS)
# "<show> [الموسم X] الحلقة N" - the episode titles of the site
EPISODE_RE = re.compile(r"^(.*?)\s*(?:(?:الموسم|الجزء)\s*(\d+|%s)\s*)?(?:الحلقة|حلقة)\s*(\d+)" % _ORD_RE)
SEASON_RE = re.compile(r"(?:الموسم|الجزء)\s*(\d+|%s)" % _ORD_RE)
# site words that do not belong into a title / file name
PREFIX_RE = re.compile(r"^(?:\s*(?:مشاهدة|فيلم|فلم|مسلسل|انمي|أنمي|برنامج|عرض)\s+)+")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجم|اون لاين|أون لاين|كاملة|كامل|بجودة عالية|HD)(?=\s|$)")
YEAR_RE = re.compile(r"^(.*?)\s*\(?((?:19|20)\d{2})\)?$")
DUB_WORD = "مدبلج"
SERIES_CAT_WORDS = ("مسلسلات", "برامج", "عروض")
# right-to-left mark in some category names (py2: utf-8 bytes like the page data)
RLM = u"\u200f" if isinstance("", type(u"")) else "\xe2\x80\x8f"


def _ordinal(val):
    if not val:
        return 1
    if val.isdigit():
        return int(val)
    return dict(SEASON_ORDINALS).get(val, 1)


class CimaClub(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_key", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cimaclub", "cookie": "cimaclub.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/cimaclub.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "list_items", "title": _("Latest"), "url": self.MAIN_URL, "good_for_fav": True},
            {"category": "cc_cats", "title": _("Movies"), "cat_kind": "movies"},
            {"category": "cc_cats", "title": _("Series"), "cat_kind": "series"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("cimaclub")
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
        # one ASCII form (lower-case percent escapes like the site's own links) for requests,
        # the downloaded marker, watched keys and favourites
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if not url:
            return ""
        url = self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
            url = re.sub(r"%[0-9A-F]{2}", lambda m: m.group(0).lower(), url)
        except Exception:
            printExc()
        return url

    @staticmethod
    def _clean(text):
        text = PREFIX_RE.sub("", text or "")
        text = JUNK_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip(" -:|")

    def _splitYear(self, title):
        # "Dark Matter 2024" -> ("Dark Matter", "2024")
        m = YEAR_RE.match(title or "")
        if m and m.group(1).strip():
            return m.group(1).strip(), m.group(2)
        return title, ""

    def _parseEpisode(self, rawTitle):
        # "مسلسل Dark Matter 2024 الموسم الثاني الحلقة 6 مترجمة" -> (show, year, season, episode, seasonLabel)
        title = self._clean(rawTitle)
        m = EPISODE_RE.match(title)
        if not m:
            return None
        show = m.group(1).strip()
        dub = DUB_WORD in show
        if dub:
            show = re.sub(r"\s+", " ", show.replace("مدبلجة", " ").replace("مدبلجه", " ").replace(DUB_WORD, " ")).strip()
        show, year = self._splitYear(show)
        if not show:
            return None
        rawSeason = rawTitle[:rawTitle.find("الحلقة")].strip() if "الحلقة" in rawTitle else rawTitle
        return {"show": show, "year": year, "season": _ordinal(m.group(2)), "episode": m.group(3), "dub": dub, "raw_season": rawSeason,
                "has_season": m.group(2) is not None}

    def _showKey(self, show, year, season):
        return "%s|%s|%d" % (show.lower(), year, season)

    def _lastPage(self, data, page):
        nums = [int(n) for n in re.findall(r'class="page-numbers"[^>]*>\s*(\d+)\s*<', data)]
        # the last page links only the earlier ones
        return max(nums + [page]) if nums else 0

    @staticmethod
    def _pageTpl(url):
        # the url of any page of a listing with "{page}" in it
        url = re.sub(r"/page/\d+/?", "/", url)
        if "?s=" in url or "&s=" in url:
            url = re.sub(r"[&?]page=\d+", "", url)
            return url.replace("{", "%7B").replace("}", "%7D") + "&page={page}"
        return url.replace("{", "%7B").replace("}", "%7D").rstrip("/") + "/page/{page}/"

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category in ("cc_movie", "cc_episode"):
                url = self._canonUrl(cItem.get("url", ""))
                return "video:%s" % urllib_unquote(url).replace(self.MAIN_URL, "/") if url else ""
            if category == "cc_season" and cItem.get("s_key"):
                return "season:%s" % cItem["s_key"]
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "") in ("cc_movie", "cc_episode", "cc_season"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # menus
    ###################################################
    def listCats(self, cItem):
        printDBG("CimaClub.listCats [%s]" % cItem.get("cat_kind", ""))
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="dropdown select-menu">', "</ul>", False)[1] or data
        wantSeries = cItem.get("cat_kind") == "series"
        seen = set()
        for url, title in re.findall(r'<li data-tax="category"[^>]*><a href="([^"]+)">(?:<div class="Checkbox">.*?</div>)?([^<]+)</a>', block):
            title = self.cleanHtmlStr(title).replace(RLM, "").strip()
            url = self._canonUrl(url)
            if not title or url in seen or "غير مصنف" in title:
                continue
            isSeries = any(word in title for word in SERIES_CAT_WORDS)
            if isSeries != wantSeries:
                continue
            seen.add(url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url})
            self.addDir(params)

    def listItems(self, cItem):
        url = self._canonUrl(cItem["url"])
        page = int(cItem.get("page", 1) or 1)
        printDBG("CimaClub.listItems page[%d] [%s]" % (page, url))
        sts, data = self.getPage(url)
        if not sts:
            return
        start = data.find('<div class="BlocksHolder')
        end = data.find('<div class="pagination">', start if start > -1 else 0)
        block = data[start if start > -1 else 0:end if end > -1 else len(data)]
        normalize = IsMediaNamingNormalized()
        seenSeasons = set()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, '<div class="Small--Box">', "</inner--title>"):
            itemUrl = self._canonUrl(self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0])
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not itemUrl or not rawTitle or itemUrl in seen:
                continue
            seen.add(itemUrl)
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            cat = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<li class="category">([^<]*)<')[0])
            ribbon = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="ribbon">(.*?)</div>')[0])
            desc = " | ".join([x for x in (ribbon, cat) if x])
            params = {"name": "category", "good_for_fav": True, "url": itemUrl, "icon": self.getFullIconUrl(icon), "desc": desc}
            ep = self._parseEpisode(rawTitle) if ("الحلقة" in rawTitle or "حلقة" in rawTitle) else None
            if ep:
                key = self._showKey(ep["show"], ep["year"], ep["season"])
                if key in seenSeasons:
                    continue
                seenSeasons.add(key)
                params.update(self._seasonParams(ep, key, normalize))
                self.addDir(params)
                continue
            clean = self._clean(rawTitle)
            if DUB_WORD in clean:
                metaTitle = re.sub(r"\s+", " ", clean.replace("مدبلجة", " ").replace("مدبلجه", " ").replace(DUB_WORD, " ")).strip()
            else:
                metaTitle = clean
            metaTitle, year = self._splitYear(metaTitle)
            if normalize:
                # metaTitle has the dub word removed - it is added back once at the end
                title = "%s (%s)" % (metaTitle, year) if year else metaTitle
                if DUB_WORD in clean:
                    title = "%s %s" % (title, DUB_WORD)
            else:
                title = rawTitle
            params.update({"category": "cc_movie", "title": title, "meta_type": "movie", "meta_title": metaTitle, "meta_year": year})
            self.addVideo(params)

        if not seen:
            return
        hasNext = 'class="next page-numbers"' in data
        tpl = cItem.get("cc_tpl") or self._pageTpl(url)
        cItem = dict(cItem, cc_tpl=tpl)
        if cItem.get("category") != "list_items":
            # search: the pager rows must list the pages, not search again
            cItem.update({"category": "list_items", "search_item": False})
        addPagingItems(self, cItem, page, hasNext, self._lastPage(data, page), tpl)

    def _seasonParams(self, ep, key, normalize):
        show = ep["show"]
        if ep["dub"]:
            show = "%s %s" % (show, DUB_WORD)
        if normalize:
            title = "%s (%s)" % (show, ep["year"]) if ep["year"] else show
            if ep["has_season"]:
                title = "%s - %s %d" % (title, _("Season"), ep["season"])
        else:
            title = ep["raw_season"]
        return {"category": "cc_season", "title": title, "s_title": show, "s_key": key, "s_season": ep["season"],
                "meta_type": "tv", "meta_title": ep["show"], "meta_year": ep["year"]}

    def listEpisodes(self, cItem):
        printDBG("CimaClub.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        block = self.cm.ph.getDataBeetwenMarkers(data, '<section class="allepcont', "</section>", False)[1]
        seasons = self._otherSeasons(data, cItem)
        # episode titles without a season label: the season of the page when it names exactly one
        pageSeason = seasons[0]["season"] if len(seasons) == 1 else cItem.get("s_season", 1)
        episodes = []
        seen = set()
        for url, rawTitle, body in re.findall(r'(?s)<a href="([^"]+)" title="([^"]*)">(.*?)</a>', block):
            url = self._canonUrl(url)
            if url in seen:
                continue
            seen.add(url)
            rawTitle = self.cleanHtmlStr(rawTitle)
            epNum = self.cm.ph.getSearchGroups(body, r'(?s)<div class="epnum">.*?(\d+)')[0]
            ep = self._parseEpisode(rawTitle)
            if ep and not epNum:
                epNum = ep["episode"]
            season = ep["season"] if ep and ep["has_season"] else pageSeason
            show = cItem.get("s_title") or (ep["show"] if ep else "")
            if normalize and epNum and show:
                title = "%s - %s" % (show, formatSxxExx(season, epNum))
            else:
                title = rawTitle or show
            icon = self.cm.ph.getSearchGroups(body, r'data-src="([^"]+)"')[0]
            episodes.append({"name": "category", "good_for_fav": True, "category": "cc_episode", "title": title, "url": url,
                             "icon": self.getFullIconUrl(icon) if icon else cItem.get("icon", ""), "desc": cItem.get("desc", ""),
                             "s_title": show, "s_key": cItem.get("s_key", ""), "s_season": season, "s_episode": epNum,
                             "meta_type": "tv", "meta_title": cItem.get("meta_title", ""), "meta_year": cItem.get("meta_year", "")})
        episodes.sort(key=lambda e: int(e["s_episode"]) if str(e["s_episode"]).isdigit() else 0)
        # the site sometimes has two pages for one episode ("...-الحلقة-1-الاولي" and "...-الحلقة-1") - number
        # the second one so the rows (and download file names) differ
        titles = {}
        for params in episodes:
            titles[params["title"]] = titles.get(params["title"], 0) + 1
            if titles[params["title"]] > 1:
                params["title"] = "%s (%d)" % (params["title"], titles[params["title"]])
        for params in episodes:
            self.addVideo(params)

        if len(seasons) > 1:
            params = dict(cItem)
            params.update({"good_for_fav": False, "category": "cc_seasons", "title": _("Other seasons"), "cc_seasons": seasons})
            self.addDir(params)

    def _otherSeasons(self, data, cItem):
        block = self.cm.ph.getDataBeetwenMarkers(data, '<section class="otherser', "</section>", False)[1]
        seasons = []
        for url, body in re.findall(r'(?s)<a href="([^"]+)"[^>]*>(.*?)</a>', block):
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)<div class="epnum">(.*?)</div>')[0])
            m = re.search(r"(?:الموسم\s*)?(\d+|%s)" % _ORD_RE, label)
            snum = _ordinal(m.group(1)) if m else 1
            icon = self.cm.ph.getSearchGroups(body, r'data-src(?:cs)?="([^"]+)"')[0]
            seasons.append({"url": self._canonUrl(url), "season": snum, "label": label, "icon": icon})
        return seasons

    def listSeasons(self, cItem):
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "")
        base = cItem.get("s_key", "").rsplit("|", 1)[0]
        for s in sorted(cItem.get("cc_seasons", []), key=lambda x: x["season"]):
            title = "%s - %s %d" % (show, _("Season"), s["season"]) if normalize else ("%s %s" % (show, s["label"])).strip()
            params = {"name": "category", "good_for_fav": True, "category": "cc_season", "title": title, "url": s["url"],
                      "icon": self.getFullIconUrl(s["icon"]) if s["icon"] else cItem.get("icon", ""), "s_title": show,
                      "s_key": "%s|%d" % (base, s["season"]), "s_season": s["season"], "meta_type": "tv",
                      "meta_title": cItem.get("meta_title", ""), "meta_year": cItem.get("meta_year", "")}
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CimaClub.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"url": self.MAIN_URL + "?s=" + urllib_quote_plus(searchPattern), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="StoryArea">(.*?)</div>')[0])
        story = re.sub(r"^القصه\s*", "", story)
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, poster

    def getLinksForVideo(self, cItem):
        printDBG("CimaClub.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem.get("url", ""))
        if not pageUrl:
            return []
        watchUrl = pageUrl.rstrip("/") + "/watch/"
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=pageUrl)
        sts, data = self.getPage(watchUrl, params)
        if not sts:
            return []
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="watch">', "</ul>", False)[1]
        urltab = []
        counts = {}
        found = []
        for li in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            url = self.cm.ph.getSearchGroups(li, r'data-watch="([^"]+)"')[0].replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or url in [f[1] for f in found]:
                continue
            name = self.cleanHtmlStr(re.sub(r"(?s)<noscript>.*?</noscript>", "", li)) or self.up.getHostName(url)
            name = name.strip() or self.up.getHostName(url)
            found.append((name, url))
            counts[name.lower()] = counts.get(name.lower(), 0) + 1
        numbers = {}
        for name, url in found:
            if counts[name.lower()] > 1:
                numbers[name.lower()] = numbers.get(name.lower(), 0) + 1
                name = "%s #%d" % (name, numbers[name.lower()])
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        story = self._siteInfo(data)[0]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("CimaClub.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("CimaClub.getArticleContent [%s]" % cItem.get("url", ""))
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
            genres = [self.cleanHtmlStr(g) for g in re.findall(r'<a href="[^"]+/genre/[^"]+"[^>]*>([^<]+)<', self.cm.ph.getDataBeetwenMarkers(data, '<div class="TaxContent">', '<div class="SingleContent">', False)[1])]
            if genres:
                info["genres"] = ", ".join(genres[:6])
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<a href="[^"]+/quality/[^"]+"[^>]*>([^<]+)<')[0])
            if quality:
                info["quality"] = quality
            year = self.cm.ph.getSearchGroups(data, r'/release-year/(\d{4})/')[0]
            if year:
                info["year"] = year
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
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
        printDBG("CimaClub.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "cc_cats":
            self.listCats(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "cc_season":
            self.listEpisodes(self.currItem)
        elif category == "cc_seasons":
            self.listSeasons(self.currItem)
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
        CHostBase.__init__(self, CimaClub(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cimaclub")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("cc_movie", "cc_episode", "cc_season")
