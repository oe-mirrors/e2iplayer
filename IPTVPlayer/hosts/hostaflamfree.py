# -*- coding: utf-8 -*-
LAST_MODIFIED = "18.10.2026"
# 17.10.2026 - new host for aflamfree.one (Arabic subtitled films and series: foreign, Arabic, Asian, Turkish,
#   Indian, cartoons and anime): latest added (the site's /last list), sections, series and search with
#   First page / Jump / Next page from the site's own pager; all categories, genres, languages, countries,
#   release years and qualities of the site from its sitemaps
#   - films are VIDEO rows keyed on their page url; the episodes of a series (one post per episode) are grouped
#     in a series folder that lists every episode of the show
#   - links: the servers of <page>/watch (data-watch embeds) plus the hosters of <page>/download that urlparser
#     knows; everything is resolved through urlparser
#   - watched flag (series -> episodes), downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx"), sidecar, INFO via moviemeta + the page's story / info rows
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://aflamfree.one/"


# "مشاهدة فيلم Lucky Baskhar 2024 مترجم اون لاين و" -> "Lucky Baskhar", 2024
PREFIX_RE = re.compile(r"^\s*(?:مشاهدة\s+|مشاهده\s+)?(?:فيلم|فلم|مسلسل|انمي)\s+")
YEAR_RE = re.compile(r"(?:^|\s)(19\d\d|20\d\d)(?=\s|$)")
JUNK_WORDS = ("مترجم", "مترجمة", "اون", "أون", "لاين", "اونلاين", "أونلاين", "و", "وتحميل", "تحميل", "كامل", "كاملة",
              "بجودة", "عالية", "HD", "مشاهدة", "مدبلج", "مدبلجة", "للعربية")
DUB_RE = re.compile(r"مدبلج")
# episode posts: "مسلسل الخليفة الحلقة 33 مترجمة", "... الموسم الثاني الحلقة 4"
EPISODE_RE = re.compile(r"الحلقة\s*(\d+)")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2),
    ("الثاني", 2), ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5),
    ("السادسة", 6), ("السادس", 6), ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9),
    ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
# "<span>لغة الفيلم : </span> ..." rows of the page -> INFO keys
INFO_ROWS = (("تصنيف", "category"), ("نوع", "genres"), ("تاريخ اصدار", "year"), ("لغة", "language"),
             ("جودة", "quality"), ("دولة", "country"), ("التصنيف العمرى", "age_limit"), ("المخرجين", "director"),
             ("الممثلين", "actors"), ("مدة", "duration"))
# category slugs left out: Latin copies of Arabic sections, and the adults-only section
SKIP_CATEGORIES = ("all-movies", "asian-movies", "indian-movies", "movis", "افلام-movis", "cartoon-animation",
                   "افلام-للكبار-فقط")


def _cleanName(title):
    # -> (film name, year, dubbed); the Arabic name after the year stays out of the name ("Ghamasaan 2024 جوماستان")
    title = re.sub(r"\s+", " ", title or "").strip()
    name = PREFIX_RE.sub("", title)
    # the release year is the last year with a name in front ("1917 2019", "Blade Runner 2049 2017")
    year = None
    for match in YEAR_RE.finditer(name):
        if name[:match.start()].strip():
            year = match
    if year:
        name = name[:year.start()]
    # filler words only at the end ("... مترجم اون لاين و"): inside a name they belong to it
    words = name.split()
    while words and words[-1] in JUNK_WORDS:
        words.pop()
    name = " ".join(words).strip(" -:|")
    return (name or title), (year.group(1) if year else ""), bool(DUB_RE.search(title))


def _episodeInfo(title):
    # "مسلسل الخليفة الحلقة 33 مترجمة" -> ("الخليفة", season (0 = none), "33"); None for a film
    title = re.sub(r"\s+", " ", title or "").strip()
    episode = EPISODE_RE.search(title)
    if not episode:
        return None
    season = SEASON_RE.search(title)
    cut = min(m.start() for m in (episode, season) if m)
    show = PREFIX_RE.sub("", title[:cut]).strip(" -:|")
    seasonNum = 0
    if season:
        val = season.group(1)
        seasonNum = int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)
    return show or title, seasonNum, str(int(episode.group(1)))


def _metaTitle(name):
    # the Latin words of the name for the metadata search, else the name as it is
    latin = " ".join(word for word in name.split() if re.search(r"[A-Za-z]", word))
    return latin or name


def _metaSkip(title):
    # IMDb, Cinemeta and OMDb answer Arabic titles with unrelated hits
    return () if isLatinTitle(title) else LATIN_ONLY


class AflamFree(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "series_key", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "aflamfree", "cookie": "aflamfree.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/aflamfree135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

        def cat(slug):
            return self.getFullUrl("/category/%s" % slug)

        self.MENU = [
            {"category": "list_items", "title": _("Latest added"), "url": self.getFullUrl("/last")},
            {"category": "list_items", "title": _("Foreign movies"), "url": cat("افلام-اجنبية")},
            {"category": "list_items", "title": _("Arabic Movies"), "url": cat("افلام-عربية")},
            {"category": "list_items", "title": _("Asian movies"), "url": cat("افلام-اسيوية")},
            {"category": "list_items", "title": _("Turkish Movies"), "url": cat("افلام-تركية")},
            {"category": "list_items", "title": _("Indian Movies"), "url": cat("افلام-هنديه")},
            {"category": "list_items", "title": _("Cartoons and anime"), "url": cat("كارتون-وانمي")},
            {"category": "list_items", "title": _("Series"), "url": cat("مسلسلات")},
            # the site's taxonomies, each from its sitemap (<tax>-sitemap.xml)
            {"category": "af_tax", "title": _("Categories"), "tax": "category"},
            {"category": "af_tax", "title": _("Genres"), "tax": "genre"},
            {"category": "af_tax", "title": _("Language"), "tax": "language"},
            {"category": "af_tax", "title": _("Country"), "tax": "country"},
            {"category": "af_tax", "title": _("Year"), "tax": "release-year"},
            {"category": "af_tax", "title": _("Quality"), "tax": "quality"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("aflamfree")
        self.wfInitFolderCache()
        self.taxCache = {}

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def getFullUrl(self, url, currUrl=None):
        # menu urls are written in Arabic - one ASCII (percent-encoded) form for everything
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
        if url.startswith("//"):
            url = "https:" + url
        elif not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        # favourites from an older domain of the site -> the current one
        url = re.sub(r"^https?://(?:www\.)?aflamfree\.[a-z]+/", self.MAIN_URL, url)
        return self._quote(url)

    def _path(self, url):
        # domain independent identity of a page
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def _seriesKey(self, url):
        # episode pages are <show-slug>-<number>.html ("halef-koklerin-cagrisi-33.html", "...-01.html")
        return re.sub(r"-\d+(?:\.html)?$", "", self._path(url).split("?")[0])

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("af_video", "af_series"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    @staticmethod
    def _episodeTitle(show, season, episode, label):
        if IsMediaNamingNormalized():
            return "%s - %s" % (show, formatSxxExx(season or 1, episode))
        return label

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("category") == "af_video":
                path = self._path(cItem.get("url", ""))
                return "video:%s" % path if path else ""
            if cItem.get("category") == "af_series":
                key = cItem.get("series_key") or self._seriesKey(cItem.get("url", ""))
                return "series:%s" % key if key else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listTaxonomy(self, cItem):
        # every entry of the site's sitemap of this taxonomy (categories, genres, languages ...)
        tax = cItem.get("tax", "")
        if tax not in self.taxCache:
            sts, data = self.getPage(self.getFullUrl("/%s-sitemap.xml" % tax))
            entries = []
            marker = "/%s/" % tax
            for loc in re.findall(r"<loc>([^<]+)</loc>", data if sts else ""):
                path = urllib_unquote(loc.strip())
                slug = path.split(marker, 1)[1].strip("/") if marker in path else ""
                if not slug or slug.split("/")[-1] in SKIP_CATEGORIES:
                    continue
                # sub-sections ("افلام-اجنبية/افلام-الأكشن") by their own name
                entries.append((slug.split("/")[-1].replace("-", " "), self._canonUrl(loc.strip())))
            if tax == "release-year":
                entries.sort(key=lambda e: e[0], reverse=True)
            else:
                entries.sort(key=lambda e: e[0])
            self.taxCache[tax] = entries
        for title, url in self.taxCache[tax]:
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": url,
                         "icon": self.DEFAULT_ICON_URL})

    def _pager(self, data, page):
        # (url template with {page}, last page) from the numbered links of the site's pager (?page=N, /last: ?paged=N)
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination', "</ul>", False)[1]
        pageTpl = ""
        for href, num in re.findall(r"""href=['"]([^'"#]+)['"][^>]*>\s*(\d+)\s*<""", pager):
            tpl = re.sub(r"([?&]paged?=)%s(?=\D|$)" % num, r"\g<1>{page}", self._canonUrl(href), count=1)
            if "{page}" in tpl:
                pageTpl = tpl
                break
        lastPage = max([int(n) for n in re.findall(r">\s*(\d+)\s*</(?:a|span)>", pager)] + [page])
        return pageTpl, lastPage

    @staticmethod
    def _pageTpl(baseUrl):
        # the site's own form: ?page=N (also after ?s=), ?paged=N on /last
        param = "paged" if re.search(r"/last/?(?:\?|$)", baseUrl) else "page"
        return "%s%s%s={page}" % (baseUrl, "&" if "?" in baseUrl else "?", param)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem.get("url", ""))
        pageTpl = cItem.get("page_tpl", "") or self._pageTpl(baseUrl)
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("AflamFree.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        # only the main grid: the sidebar and the "latest" boxes use the same cards
        grid = self.cm.ph.getDataBeetwenMarkers(data, 'id="MainFiltar"', 'class="pagination', False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, 'id="MainFiltar"', "</main>", False)[1]
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(grid, '<div class="Small--Box">', "</a>"):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3 class="title">(.*?)</h3>')[0]) or \
                self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            if not href or not rawTitle:
                continue
            url = self._canonUrl(href)
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            icon = self.getFullIconUrl(self._quote(icon)) if icon else ""
            fields = [self.cleanHtmlStr(x) for x in re.findall(r'(?s)<li class="(?:genre|quality)">(.*?)</li>', item)]
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<li class="imdbRating">(.*?)</li>')[0])
            if rating:
                fields.append("IMDb %s" % rating)
            desc = " | ".join(x for x in fields if x)
            episode = _episodeInfo(rawTitle)
            if episode:
                # an episode post: one folder per show (the newest episodes of a show follow each other)
                key = self._seriesKey(url)
                if key in seen:
                    continue
                seen.add(key)
                show, season = episode[0], episode[1]
                self.addDir({"name": "category", "category": "af_series", "good_for_fav": True, "url": url, "series_key": key,
                             "title": show if normalize else rawTitle, "icon": icon, "desc": desc, "s_title": show,
                             "s_season": season or 1, "meta_type": "tv", "meta_title": show, "meta_year": ""})
                continue
            if url in seen:
                continue
            seen.add(url)
            name, year, dubbed = _cleanName(rawTitle)
            title = rawTitle
            if normalize:
                title = "%s (%s)" % (name, year) if year else name
                if dubbed:
                    # the dubbed version is its own page next to the subtitled one
                    title = "%s - مدبلج" % title
            self.addVideo({"name": "category", "category": "af_video", "good_for_fav": True, "url": url, "title": title,
                           "icon": icon, "desc": desc, "meta_type": "movie", "meta_title": name, "meta_year": year})

        pageTpl2, lastPage = self._pager(data, page)
        pageTpl = pageTpl2 or pageTpl
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "page_tpl": pageTpl, "url": baseUrl})
        addPagingItems(self, listItem, page, bool(seen) and lastPage > page, lastPage, pageTpl)

    def listSeries(self, cItem):
        # every episode page lists all episodes of the show (newest first)
        printDBG("AflamFree.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="allepcont', "</section>", False)[1]
        episodes = []
        seen = set()
        for href, label, item in re.findall(r'(?s)<a href="([^"]+)" title="([^"]+)">(.*?)</a>', block):
            url = self._canonUrl(href)
            info = _episodeInfo(self.cleanHtmlStr(label))
            num = self.cm.ph.getSearchGroups(item, r'(?s)<div class="epnum">.*?(\d+)\s*</div>')[0]
            if url in seen or not (info or num):
                continue
            seen.add(url)
            show, season, episode = info or (cItem.get("s_title", ""), 0, str(int(num)))
            show = cItem.get("s_title") or show
            season = season or cItem.get("s_season", 1)
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            episodes.append((int(episode), {"name": "category", "category": "af_video", "good_for_fav": True, "url": url,
                                            "title": self._episodeTitle(show, season, episode, self.cleanHtmlStr(label)),
                                            "icon": self.getFullIconUrl(self._quote(icon)) if icon else cItem.get("icon", ""),
                                            "desc": cItem.get("desc", ""), "s_title": show, "s_season": season, "s_episode": episode,
                                            "series_key": cItem.get("series_key", ""), "meta_type": "tv", "meta_title": show, "meta_year": ""}))
        episodes.sort(key=lambda e: e[0])
        for _num, params in episodes:
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AflamFree.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/?s=%s" % urllib_quote_plus(searchPattern.strip()))
        cItem.update({"category": "list_items", "page": 1, "url": base, "base_url": base, "page_tpl": ""})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("AflamFree.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem.get("url", "")).rstrip("/")
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=pageUrl)
        urltab = []
        seen = set()
        sts, data = self.getPage(pageUrl + "/watch", params)
        if sts:
            block = self.cm.ph.getDataBeetwenMarkers(data, 'id="watch"', "</ul>", False)[1]
            for url, label in re.findall(r'(?s)<li[^>]+data-watch="([^"]+)"[^>]*>(.*?)(?:<noscript>|</li>)', block):
                url = url.strip()
                if url.startswith("//"):
                    url = "https:" + url
                if not self.cm.isValidUrl(url) or url in seen:
                    continue
                seen.add(url)
                name = self.cleanHtmlStr(label) or self.up.getDomain(url, onlyDomain=True)
                urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        sts, data = self.getPage(pageUrl + "/download", params)
        if sts:
            main = self.cm.ph.getDataBeetwenMarkers(data, '<main', "</main>", False)[1]
            for url, label in re.findall(r'(?s)<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', main):
                # only the hosters urlparser resolves (Mega, UsersDrive ... are left out)
                if "aflamfree" in url or url in seen or self.up.checkHostSupport(url) != 1:
                    continue
                seen.add(url)
                name = self.cleanHtmlStr(label) or self.up.getDomain(url, onlyDomain=True)
                urltab.append({"name": "%s (%s)" % (name, _("Download")), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        # the same lookup as the INFO view (getArticleContent), so an INFO opened before answers from the cache
        title = _metaTitle(cItem.get("meta_title", ""))
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", "movie"), title, cItem.get("meta_year", ""), skip=_metaSkip(title))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), "", metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("AflamFree.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="StoryArea">(.*?)</div>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        info = {}
        tax = self.cm.ph.getDataBeetwenMarkers(data, 'class="TaxContent"', "</div>", False)[1]
        for row in re.findall(r"(?s)<li[^>]*>(.*?)</li>", tax):
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(row, r"(?s)<span>(.*?)</span>")[0]).rstrip(" :")
            if not label:
                continue
            key = ""
            for word, infoKey in INFO_ROWS:
                if label.startswith(word):
                    key = infoKey
                    break
            # one value per link; the section row repeats some names ("افلام اجنبية" twice)
            values = []
            for val in [self.cleanHtmlStr(v) for v in re.findall(r"(?s)<a[^>]*>(.*?)</a>", row)] or [self.cleanHtmlStr(row.split("</span>", 1)[-1])]:
                if val and val not in values:
                    values.append(val)
            if key and values:
                info[key] = ", ".join(values)
        rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="imdbR">.*?<span>(.*?)</span>')[0])
        if rating:
            info["imdb_rating"] = rating
        return story, self.getFullIconUrl(self._quote(poster)) if poster else "", info

    def getArticleContent(self, cItem):
        printDBG("AflamFree.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        meta = {}
        if cItem.get("meta_title"):
            try:
                title = _metaTitle(cItem["meta_title"])
                meta = getMeta(cItem.get("meta_type", "movie"), title, cItem.get("meta_year") or info.get("year", ""), _metaSkip(title))
            except Exception:
                printExc()
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
        printDBG("AflamFree.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "af_series":
            self.listSeries(self.currItem)
        elif category == "af_tax":
            self.listTaxonomy(self.currItem)
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
        CHostBase.__init__(self, AflamFree(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("aflamfree")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("af_video", "af_series")
