# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - rewrite for the current m.myseed.pics layout and the current host standard
#   (earlier versions: popking (odem2014), M.Elsafty (angel_heart))
#   - menus read the site's current category paths (the old "-14"/"-7"/"-2" slugs only redirect now);
#     movies, songs, plays, WWE: VIDEO rows; series lists ("latest episodes"): episode VIDEO rows;
#     "seasons" (packs) lists: series folders -> seasons (/selary/ pages) -> episodes
#   - VIDEO rows are keyed on the stable details page url; the servers are read in getLinksForVideo from
#     the /watch/ page (1 GET) + one get__quality__servers POST per further quality - no per-server AJAX
#     storm and no sleeps; servers without a link on the page are asked for (get__watch__server) only
#     when the user picks them, in getVideoLinks
#   - own "MySeed" server: /vids.php?t=.. -> d.myseed.tv player gateway -> MP4 (needs the gateway Referer);
#     the other servers go to urlparser (need_resolve=1, "/vid/?id=<base64>" unwrapped)
#   - getVideoLinks restored (PR #660 had removed it - every hoster link crashed in getResolvedURL)
#   - watched flag (series -> season -> episode), downloaded flag, favourites, sidecar,
#     name normalisation ("Title (Year)", "Show - SxxExx"), INFO via moviemeta + the site's story/fields,
#     First/Jump/Next paging, search + history; no colour codes in video titles
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://m.myseed.pics/"


# Enigma2 colour codes ("\c00RRGGBB") - only for the list description, never in titles / sidecar / INFO text
COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")
# Arabic ordinals of season labels ("الموسم الثاني"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("السادس عشر", 16), ("السابع عشر", 17), ("الثامن عشر", 18), ("التاسع عشر", 19), ("العشرون", 20),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5),
    ("السادسة", 6), ("السادس", 6), ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8),
    ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:^|\s)(?:الموسم|موسم)\s*(\d+|%s)(?=\s|$)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"(?:^|\s)(?:الحلقة|حلقة)\s*(\d+)")
PREFIX_RE = re.compile(r"^(?:فيلم|افلام|أفلام|مسلسل|انمي|أنمي|برنامج|عرض|مسرحية|اغنية|أغنية|كليب)\s+")
# site words that do not belong into a title / file name
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|اون لاين|أون لاين|مشاهدة|كامل|كاملة|بجودة عالية|HD)(?=\s|$)")
DUB_RE = re.compile(r"(?:^|\s)(?:مدبلج|مدبلجة)(?=\s|$)")
DUB_WORD = "مدبلج"
YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d{2})\)?\s*$")
# "<span>سنة العرض : </span>" rows of a details page -> INFO keys
INFO_FIELDS = (("نوع العرض", "genres"), ("سنة العرض", "year"), ("لغة العرض", "language"), ("جودة العرض", "quality"),
               ("بلد العرض", "country"), ("تصنيف العرض", "category"), ("مدة العرض", "duration"))
SEARCH_PAGE_SIZE = 24
# the site's former own players, still linked by old titles: redirect to other sites / ad pages now
DEAD_HOSTS_RE = re.compile(r"^https?://(?:[^/]+\.)?(?:arabseed\.me|reviewrate\.net|reviewtech\.me)/", re.I)
# fields that identify a row (the description carries the changing rating)
FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "s_title", "s_season", "s_episode", "s_term",
              "meta_type", "meta_title", "meta_year")


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


class MySeed(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "MySeed", "cookie": "MySeed.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://m.myseed.pics/lgo222.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*; q=0.01",
                                 "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Origin": self.MAIN_URL.rstrip("/")})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("arabseed")
        self.wfInitFolderCache()

        def cat(path):
            return self.getFullUrl("category/" + path)

        movies = [(_("Foreign movies"), "foreign-movies/"), (_("Arabic Movies"), "arabic-movies/"), (_("Netflix movies"), "netflix/netflix-movies/"),
                  (_("Indian Movies"), "indian-movies/"), (_("Turkish Movies"), "turkish-movies/"), (_("Asian movies"), "asian-movies/"),
                  (_("Classic movies"), "افلام-كلاسيكيه/"), (_("Dubbed movies"), "dubbed-movies/"), (_("Animated movies"), "animation-movies/")]
        series = [(_("Foreign series"), "foreign-series/"), (_("Arabic Series"), "arabic-series/"), (_("Egyptian series"), "مسلسلات-مصريه/"),
                  (_("Netflix series"), "netflix/netflix-series/"), (_("Turkish Series"), "turkish-series/"), (_("Indian TV series"), "مسلسلات-هندية/"),
                  (_("Korean TV series"), "مسلسلات-كوريه/"), (_("Dubbed series"), "dubbed-series/"), (_("Animated series"), "cartoon-series/"),
                  (_("TV Shows"), "برامج-تلفزيونية/")]
        ramadan = [("%s %s" % (_("Ramadan"), year), path) for year, path in (
            ("2026", "ramadan-series-2026/"), ("2025", "ramadan-series-2025/"), ("2024", "ramadan-series-2024/"),
            ("2023", "ramadan-series-2023/"), ("2022", "مسلسلات-رمضان-2022/"), ("2021", "مسلسلات-رمضان-2021/"),
            ("2020", "مسلسلات-رمضان-2020-hd/"), ("2019", "مسلسلات-رمضان-2019/"))]
        other = [(_("Wrestling"), "wwe-shows/"), (_("Arabic songs"), "arabic-songs/"), (_("Arabic plays"), "مسرحيات-عربي/")]

        def tab(entries, suffix=""):
            return [{"category": "list_items", "good_for_fav": True, "title": t, "url": cat(p + suffix)} for t, p in entries]

        self.SUB_TABS = {
            "movies_folder": tab(movies),
            "series_folder": tab(series),
            "series_packs_folder": tab(series, "packs/") + tab(ramadan, "packs/"),
            "ramadan_folder": tab(ramadan),
            "other_folder": tab(other),
        }
        self.MAIN_CAT_TAB = [
            {"category": "list_items", "good_for_fav": True, "title": _("Recently added"), "url": self.getFullUrl("recently/")},
            {"category": "list_items", "good_for_fav": True, "title": _("Most viewed"), "url": self.getFullUrl("trend/")},
            {"category": "movies_folder", "title": _("Movies")},
            {"category": "series_folder", "title": _("Series - latest episodes")},
            {"category": "series_packs_folder", "title": _("Series - seasons")},
            {"category": "ramadan_folder", "title": _("Ramadan")},
            {"category": "other_folder", "title": _("Other")},
        ] + self.searchItems()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def _ajax(self, endpoint, postData, referer):
        params = dict(self.defaultParams)
        params["header"] = dict(self.AJAX_HEADER, Referer=referer)
        sts, data = self.getPage(self.getFullUrl(endpoint + "/"), params, postData)
        if not sts:
            return {}
        try:
            ret = json_loads(data)
            return ret if isinstance(ret, dict) else {}
        except Exception:
            printDBG("MySeed._ajax %s: no JSON" % endpoint)
        return {}

    def _canonUrl(self, url):
        # the site links the same page raw-Arabic or percent-encoded (lower case) - one ASCII form for
        # requests, the watched/downloaded markers and favourites
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        url = self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _pageUrl(self, url):
        # details page of a title (old favourites / links point to its "watch/" page)
        url = self._canonUrl(url)
        if url.endswith("/watch/"):
            url = url[:-len("watch/")]
        return url

    @staticmethod
    def _seasonNum(text):
        m = SEASON_RE.search(text or "")
        if not m:
            return 0
        val = m.group(1)
        return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)

    def _parseTitle(self, title):
        # "مسلسل X الموسم الثاني الحلقة 3 الثالثة مترجمة" -> {"name": "X", "season": 2, "episode": "3", "year": "", "dub": False}
        # "فيلم Y 2026 مترجم" -> {"name": "Y", "year": "2026", ...}
        text = self.cleanHtmlStr(title)
        dub = bool(DUB_RE.search(text))
        text = DUB_RE.sub(" ", text)
        text = PREFIX_RE.sub("", text.strip())
        ret = {"name": "", "season": 0, "episode": "", "year": "", "dub": dub}
        m = EPISODE_RE.search(text)
        if m:
            ret["episode"] = m.group(1)
            text = text[:m.start()]
        ret["season"] = self._seasonNum(text)
        m = SEASON_RE.search(text)
        if m:
            text = text[:m.start()]
        text = re.sub(r"\s+", " ", JUNK_RE.sub(" ", text)).strip(" -:|")
        m = YEAR_RE.search(text)
        if m and not ret["episode"]:
            ret["year"] = m.group(1)
            text = text[:m.start()].strip(" -:|(")
        ret["name"] = text or self.cleanHtmlStr(title)
        return ret

    def _displayName(self, info, kind):
        name = info["name"]
        if kind == "episode":
            name = "%s - %s" % (name, formatSxxExx(info["season"] or 1, info["episode"]))
        elif kind == "season" and info["season"]:
            name = "%s - %s" % (name, formatSxxExx(info["season"]))
        elif kind == "movie" and info["year"]:
            name = "%s (%s)" % (name, info["year"])
        if info["dub"]:
            name = "%s %s" % (name, DUB_WORD)
        return name

    def _field(self, item, cls):
        return self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="%s[^"]*">(.*?)</div>' % cls)[0])

    def _parseItems(self, data):
        # the boxes of a category / packs / search page (not the side widgets)
        start = data.find('id="ajax__area"')
        if start < 0:
            start = data.find('class="series__list')
        block = data[start:] if start >= 0 else data
        end = block.find('class="paginate"')
        if end >= 0:
            block = block[:end]
        items = []
        for chunk in block.split('<li class="box__xs__')[1:]:
            m = re.search(r'<a href="([^"]+)"[^>]*?title="([^"]*)"', chunk)
            if not m:
                continue
            url = self._pageUrl(m.group(1))
            title = self.cleanHtmlStr(m.group(2)) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(chunk, r"(?s)<h3[^>]*>(.*?)</h3>")[0])
            if not url or not title:
                continue
            story = self.cm.ph.getSearchGroups(chunk, r'(?s)<p class="(?:hide__md|story)">(.*?)</p>')[0]
            dots = [self.cleanHtmlStr(x) for x in re.findall(r"<span>([^<]+)</span>", self.cm.ph.getDataBeetwenMarkers(chunk, 'class="dots__info"', "</ul>", False)[1])]
            bottom = [self.cleanHtmlStr(x) for x in re.findall(r"<li>([^<]+)</li>", self.cm.ph.getDataBeetwenMarkers(chunk, 'class="bottom__ul"', "</ul>", False)[1])]
            items.append({
                "url": url, "title": title, "story": self.cleanHtmlStr(story),
                "icon": self._canonUrl(self.cm.ph.getSearchGroups(chunk, r'data-src="([^"]+)"')[0]),
                "genre": self._field(chunk, "__genre") or (bottom[1] if len(bottom) > 1 else ""),
                "quality": self._field(chunk, "__quality") or (bottom[0] if bottom else ""),
                "rating": self._field(chunk, "post__ratings"),
                "section": self._field(chunk, "post__category"),
                "year": dots[0] if dots and re.match(r"^\d{4}$", dots[0]) else "",
                "country": dots[1] if len(dots) > 1 else "",
                "is_series": "/selary/" in url,
                "is_episode": "is__episode" in chunk[:300] or bool(EPISODE_RE.search(title)),
            })
        return items

    def _desc(self, it):
        fields = ((_("Rating"), it.get("rating"), "green"), (_("Quality"), it.get("quality"), "yellow"), (_("Year"), it.get("year"), "cyan"),
                  (_("Genres"), it.get("genre"), "magenta"), (_("Category"), it.get("section"), "white"), (_("Country"), it.get("country"), "white"))
        desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
        if it.get("story"):
            desc = ("%s\n%s" % (desc, it["story"])) if desc else it["story"]
        return desc

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category == "as_video":
                return "video:%s" % self._pageUrl(cItem.get("url", ""))
            if category == "as_series":
                return "series:%s" % self._pageUrl(cItem.get("url", ""))
            if category == "as_season":
                term = cItem.get("s_term", "")
                return ("season:%s" % term) if term else ("season:%s" % self._pageUrl(cItem.get("url", "")))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        page = cItem.get("page", 1)
        word = cItem.get("search_word", "")
        if word:
            # the search list is built from search_word + page; the template only enables "Jump"
            pageUrlTpl = self.getFullUrl("find/?word=%s&type=&page_number={page}" % urllib_quote_plus(word))
            url = pageUrlTpl.format(page=page)
        else:
            base = re.sub(r"page/\d+/?$", "", self._canonUrl(cItem.get("base_url") or cItem.get("url", "")))
            url = base if page <= 1 else "%spage/%d/" % (base, page)
            pageUrlTpl = base + "page/{page}/"
        printDBG("MySeed.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for it in self._parseItems(data):
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            info = self._parseTitle(it["title"])
            year = it["year"] or info["year"]
            params = {"name": "category", "good_for_fav": True, "url": it["url"], "icon": it["icon"], "desc": self._desc(it)}
            if it["is_series"]:
                params.update({"category": "as_series", "title": self._displayName(info, "season") if normalize else it["title"],
                               "s_title": info["name"], "s_season": info["season"],
                               "meta_type": "tv", "meta_title": info["name"], "meta_year": year})
                self.addDir(params)
                continue
            params["category"] = "as_video"
            if it["is_episode"]:
                params.update({"title": self._displayName(info, "episode") if normalize else it["title"],
                               "s_title": info["name"], "s_season": info["season"] or 1, "s_episode": info["episode"],
                               "meta_type": "tv", "meta_title": info["name"], "meta_year": ""})
            else:
                params["title"] = self._displayName(dict(info, year=year), "movie") if normalize else it["title"]
                if self.cleanHtmlStr(it["title"]).startswith(("فيلم", "افلام", "أفلام")):
                    params.update({"meta_type": "movie", "meta_title": info["name"], "meta_year": year})
            self.addVideo(params)

        if word:
            hasNext, lastPage = len(seen) >= SEARCH_PAGE_SIZE, 0
        else:
            pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="paginate"', "</ul>", False)[1]
            hasNext = 'class="next page-numbers"' in pager
            pages = [int(x) for x in re.findall(r"/page/(\d+)/", pager)]
            lastPage = max(pages + [page]) if pages else 0
        if seen or page > 1:
            params = dict(cItem)
            params.update({"category": "list_items", "base_url": "" if word else re.sub(r"page/\{page\}/$", "", pageUrlTpl)})
            addPagingItems(self, params, page, hasNext and bool(seen), lastPage, pageUrlTpl)

    def _seasonsOf(self, data):
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="seasons__list"', "</ul>", False)[1]
        ret = []
        for li in re.findall(r"(?s)<li[^>]*data-term=.*?</li>", block):
            term = self.cm.ph.getSearchGroups(li, r'data-term="(\d+)"')[0]
            url = self.cm.ph.getSearchGroups(li, r'data-url="([^"]+)"')[0]
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(li, r"<span>([^<]+)</span>")[0])
            if term and url:
                ret.append({"term": term, "url": self._canonUrl(url), "name": name, "selected": 'class="selected"' in li})
        return ret

    def listSeries(self, cItem):
        printDBG("MySeed.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._seasonsOf(data)
        if len(seasons) <= 1:
            term = seasons[0]["term"] if seasons else ""
            self._addEpisodes(cItem, data, cItem.get("s_season") or (self._seasonNum(seasons[0]["name"]) if seasons else 0) or 1, term)
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or self._parseTitle(cItem.get("title", ""))["name"]
        for idx, s in enumerate(seasons):
            num = self._seasonNum(s["name"]) or (idx + 1)
            params = dict(cItem)
            params.update({"category": "as_season", "good_for_fav": True, "url": s["url"], "s_term": s["term"], "s_title": show, "s_season": num,
                           "title": ("%s - %s" % (show, formatSxxExx(num))) if normalize else (s["name"] or cItem.get("title", ""))})
            self.addDir(params)

    def listSeason(self, cItem):
        printDBG("MySeed.listSeason [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        self._addEpisodes(cItem, data, cItem.get("s_season") or 1, cItem.get("s_term", ""))

    def _addEpisodes(self, cItem, data, season, term):
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="episodes__list', "</ul>", False)[1]
        if 'load__more__episodes' in data and term:
            # long seasons: the rest comes in pages of the season__episodes call (not seen on the site so far)
            token = self.cm.ph.getSearchGroups(data, r"""csrf__token['"]\s*:\s*["']([^"']+)""")[0]
            for _i in range(10):
                ret = self._ajax("season__episodes", {"season_id": term, "offset": str(block.count("epi__num")), "csrf_token": token}, cItem["url"])
                if ret.get("type") != "success" or not ret.get("html"):
                    break
                block += ret["html"]
                if not ret.get("hasmore"):
                    break
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or self._parseTitle(cItem.get("title", ""))["name"]
        seen = set()
        for href, label in re.findall(r'(?s)<a href="([^"]+)"[^>]*>(.*?)</a>', block):
            url = self._pageUrl(href)
            epNum = self.cm.ph.getSearchGroups(label, r"<b>(\d+)</b>")[0]
            if not url or url in seen:
                continue
            seen.add(url)
            raw = self.cleanHtmlStr(label) or show
            raw = re.sub(r"(الحلقة)(\d)", r"\1 \2", raw)
            title = ("%s - %s" % (show, formatSxxExx(season, epNum))) if (normalize and epNum) else raw
            self.addVideo({"name": "category", "category": "as_video", "good_for_fav": True, "title": title, "url": url,
                           "icon": cItem.get("icon", ""), "desc": _stripColors(cItem.get("desc", "")),
                           "s_title": show, "s_season": season, "s_episode": epNum,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title") or show, "meta_year": cItem.get("meta_year", "")})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MySeed.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"search_word": searchPattern, "page": 1, "category": "list_items"})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _serverName(self, url, srvIdx):
        if "vids.php" in url:
            return "MySeed"
        host = self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/]+)")[0]
        return host or ("%s %s" % (_("Server"), srvIdx))

    def _unwrap(self, link):
        # "/vid/?id=<base64 of the hoster url>" -> hoster url; "/vids.php?t=.." -> full url (own server)
        link = (link or "").replace("&amp;", "&").strip()
        if not link:
            return ""
        enc = self.cm.ph.getSearchGroups(link, r"/vid/\?(?:id|url)=([A-Za-z0-9+/=_-]+)")[0]
        if enc:
            try:
                link = b64Decode(urllib_unquote(enc))
            except Exception:
                printExc()
                return ""
        return self.getFullUrl(link)

    def getLinksForVideo(self, cItem):
        pageUrl = self._pageUrl(cItem.get("url", ""))
        watchUrl = pageUrl + "watch/"
        printDBG("MySeed.getLinksForVideo [%s]" % watchUrl)
        sts, data = self.getPage(watchUrl)
        if not sts:
            return []
        token = self.cm.ph.getSearchGroups(data, r"""csrf__token['"]\s*:\s*["']([^"']+)""")[0]
        postId = self.cm.ph.getSearchGroups(data, r"""psot_id['"]\s*:\s*["']?(\d+)""")[0]

        def parseServers(html, quality, firstLink=""):
            ret = []
            for li in re.findall(r"(?s)<li[^>]+data-server=.*?>", html):
                srv = self.cm.ph.getSearchGroups(li, r'data-server="(\d+)"')[0]
                qu = self.cm.ph.getSearchGroups(li, r'data-qu="(\d+)"')[0] or quality
                link = self.cm.ph.getSearchGroups(li, r'data-link="([^"]+)"')[0]
                if not link and srv == "0" and firstLink:
                    link = firstLink
                ret.append((int(qu or 0), int(srv or 0), self._unwrap(link)))
            return ret

        servers = parseServers(self.cm.ph.getDataBeetwenMarkers(data, 'class="servers__list', "</ul>", False)[1], "")
        qualities = re.findall(r'data-quality="(\d+)"', data)
        done = set(q for q, _s, _l in servers)
        for quality in qualities:
            if int(quality) in done or not (token and postId):
                continue
            ret = self._ajax("get__quality__servers", {"post_id": postId, "quality": quality, "csrf_token": token}, watchUrl)
            if ret.get("type") == "success":
                servers.extend(parseServers(ret.get("html", ""), quality, ret.get("server", "")))
                done.add(int(quality))

        servers.sort(key=lambda x: (-x[0], x[1]))
        urlTab = []
        names = {}
        for quality, srv, link in servers:
            if DEAD_HOSTS_RE.search(link):
                continue
            if link:
                url = strwithmeta(link, {"Referer": watchUrl, "User-Agent": self.HEADER.get("User-Agent")})
            elif token and postId:
                # no link on the page: asked for when the user picks it (getVideoLinks)
                url = strwithmeta(self.getFullUrl("get__watch__server/?" + urllib_urlencode({"post_id": postId, "quality": quality, "server": srv, "csrf_token": token})),
                                  {"Referer": watchUrl})
            else:
                continue
            name = "%s %sp" % (self._serverName(link, srv) if link else ("%s %d" % (_("Server"), srv)), quality) if quality else self._serverName(link, srv)
            names[name] = names.get(name, 0) + 1
            if names[name] > 1:
                name = "%s (%d)" % (name, names[name])
            urlTab.append({"name": name, "url": url, "need_resolve": 1})
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="post__story[^"]*">(.*?)</div>')[0])
        return applySidecarToLinks(urlTab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    def _resolveOwnServer(self, url):
        # /vids.php?t=.. -> <iframe> d.myseed.tv/player-gateway.php -> <video><source src=".mp4|.m3u8">
        referer = getattr(url, "meta", {}).get("Referer", self.MAIN_URL)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=referer)
        sts, data = self.getPage(url, params)
        if not sts:
            return []
        gateway = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0].replace("&amp;", "&")
        if gateway:
            gateway = self.getFullUrl(gateway)
            params["header"] = dict(self.HEADER, Referer=self.MAIN_URL)
            sts, data = self.cm.getPage(gateway, params)
            if not sts:
                return []
        else:
            gateway = url
        origin = self.cm.ph.getSearchGroups(gateway, r"(https?://[^/]+)")[0] or self.MAIN_URL.rstrip("/")
        meta = {"Referer": origin + "/", "Origin": origin, "User-Agent": self.HEADER.get("User-Agent")}
        links = []
        for src in re.findall(r"<source[^>]+>", data):
            video = self.cm.ph.getSearchGroups(src, r'src="([^"]+)"')[0].replace("&amp;", "&")
            if not self.cm.isValidUrl(video):
                continue
            if ".m3u8" in video:
                links.extend(getDirectM3U8Playlist(strwithmeta(video, meta), checkContent=True, sortWithMaxBitrate=999999999))
            else:
                label = self.cm.ph.getSearchGroups(src, r'(?:label|size|res)="([^"]+)"')[0]
                links.append({"name": "MySeed %s" % label if label else "MySeed MP4", "url": strwithmeta(video, meta)})
        return links

    def getVideoLinks(self, videoUrl):
        printDBG("MySeed.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        url = videoUrl
        if "/get__watch__server/?" in url:
            query = url.split("?", 1)[1]
            post = dict((k, urllib_unquote(v)) for k, v in re.findall(r"([^&=]+)=([^&]*)", query))
            referer = getattr(videoUrl, "meta", {}).get("Referer", self.MAIN_URL)
            ret = self._ajax("get__watch__server", post, referer)
            if ret.get("type") != "success" and ret.get("message") == "unauthorized request":
                # the token expired - one retry with a fresh one from the watch page
                sts, data = self.getPage(referer)
                post["csrf_token"] = self.cm.ph.getSearchGroups(data, r"""csrf__token['"]\s*:\s*["']([^"']+)""")[0] if sts else ""
                ret = self._ajax("get__watch__server", post, referer) if post["csrf_token"] else {}
            link = self._unwrap(ret.get("server", "")) if ret.get("type") == "success" else ""
            if not link or DEAD_HOSTS_RE.search(link):
                return []
            url = strwithmeta(link, {"Referer": referer, "User-Agent": self.HEADER.get("User-Agent")})
        elif "/vid/?" in url:
            url = strwithmeta(self._unwrap(url), getattr(videoUrl, "meta", {}))
        if not self.cm.isValidUrl(url):
            return []
        if "vids.php" in url:
            links = self._resolveOwnServer(url)
        else:
            links = self.up.getVideoLinkExt(url)
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("MySeed.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info, imdbId, pageTitle = "", "", {}, "", ""
        sts, data = self.getPage(self._pageUrl(cItem.get("url", "")))
        if sts:
            pageTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h1 class="post__name"[^>]*>(.*?)</h1>')[0])
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="post__story[^"]*">(.*?)</div>')[0])
            poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
            imdbId = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
            area = self.cm.ph.getDataBeetwenMarkers(data, 'class="info__area__ul', 'class="watch__and__download', False)[1] or data
            for li in area.split('<div class="title__kit">')[1:]:
                label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(li, r"<span>([^<]+)</span>")[0])
                for word, key in INFO_FIELDS:
                    if word in label:
                        values = [self.cleanHtmlStr(v) for v in re.findall(r"<a[^>]*>([^<]+)</a>", li.split("</ul>")[0])]
                        if values:
                            info[key] = ", ".join(values[:6])
            persons = {"ممثل": [], "مخرج": [], "كاتب": []}
            for name, role in re.findall(r'<h3 class="name">([^<]+)</h3>\s*<span class="role">([^<]+)</span>', data):
                for word in persons:
                    if word in role and len(persons[word]) < 8:
                        persons[word].append(self.cleanHtmlStr(name))
            for word, key in (("ممثل", "actors"), ("مخرج", "directors"), ("كاتب", "writers")):
                if persons[word]:
                    info[key] = ", ".join(persons[word])
        meta = {}
        mediaType = cItem.get("meta_type", "")
        if not mediaType and pageTitle.startswith(("فيلم", "مسلسل")):
            mediaType = "movie" if pageTitle.startswith("فيلم") else "tv"
        try:
            if mediaType and imdbId:
                meta = getMetaByImdbId(mediaType, imdbId)
            if not meta and mediaType:
                parsed = self._parseTitle(pageTitle or cItem.get("title", ""))
                meta = getMeta(mediaType, cItem.get("meta_title") or parsed["name"], cItem.get("meta_year") or info.get("year", "") or parsed["year"])
        except Exception:
            printExc()
        meta = meta or {}
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or _stripColors(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = poster or meta.get("poster") or cItem.get("icon", "")
        return [{"title": _stripColors(cItem.get("title", "")) or pageTitle, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # favourites
    ###################################################
    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("as_video", "as_series", "as_season", "list_items"):
                return json_dumps(dict((key, cItem[key]) for key in FAV_FIELDS + ("base_url",) if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("MySeed.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MAIN_CAT_TAB, {"name": "category"})
        elif category in self.SUB_TABS:
            self.listsTab(self.SUB_TABS[category], self.currItem)
        elif category in ("list_items", "series", "series_packs"):
            self.listItems(self.currItem)
        elif category in ("as_series", "series_seasons_list"):
            self.listSeries(self.currItem)
        elif category == "as_season":
            self.listSeason(self.currItem)
        elif category in ("explore_item", "explore_episodes"):
            # favourites of the old host version: one playable row for the title
            params = dict(self.currItem)
            params.update({"category": "as_video", "url": self._pageUrl(params.get("url", "")), "title": _stripColors(params.get("title", ""))})
            self.addVideo(params)
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
        CHostBase.__init__(self, MySeed(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("arabseed")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("as_video", "as_series", "as_season")
