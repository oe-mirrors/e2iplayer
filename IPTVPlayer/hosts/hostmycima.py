# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - revived for mycima.poker (mycima.boo -> .band -> ... -> .poker)
#   Rewrite against the current site (WeCima theme; the wecima host went to Backup, this is the
#   one MyCima/WeCima host left):
#   - lists from the "Grid--WecimaPosts" cards; paging via tools/iptvpaging (First page / Jump /
#     Next page (n/last)); search via /filtering/?keywords=..
#   - episode posts are grouped per show + season into a season folder; it lists the season's
#     episodes ("EpisodesList") and the show's other seasons (SeasonsList, loaded through the
#     theme's Ajaxt/Single/Episodes.php like the page does)
#   - movies and episodes are VIDEO rows keyed on their page url; the hoster links are read in
#     getLinksForVideo: "data-watch" (govid.live/play/<token>, urlparser.parserGOVID) plus the
#     direct download hosters that are not among the watch servers, all resolved by urlparser
#   - Cloudflare: getPageCFProtection with the stored cookies (a MyE2i cf_clearance is reused);
#     no retry/sleep loops
#   - watched flag (season folder -> episodes), downloaded flag (page url), favourites, sidecar,
#     INFO via moviemeta + the site's story/poster/fields, name normalisation ("Title (Year)",
#     "Show - SxxExx"; raw site labels when off), no colour codes in titles
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
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
    return "https://mycima.poker/"


# Arabic ordinals used in season labels ("الموسم الثاني"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6), ("السادس", 6),
    ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:^|\s)(?:ال)?موسم\s*(\d+|%s)(?=\s|$)" % "|".join(o[0] for o in SEASON_ORDINALS))
# "الحلقة 15 الخامسة عشر" / "حلقة 3 والاخيرة" - everything from the episode word on is the episode label
EPISODE_RE = re.compile(r"(?:^|\s)(?:ال)?(?:حلقة|حلقه)\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s)\(?((?:19|20)\d\d)\)?((?:\s+(?:مدبلج|مدبلجة))*)\s*$")
SUBDUB_RE = re.compile(r"مترجم(?:ة)?\s+و\s*(مدبلج(?:ة)?)")
# site words that do not belong into a title / file name (only removed when normalising)
JUNK_RE = re.compile(r"(?:^|\s)(?:مشاهدة|فيلم|مسلسل|انمي|أنمي|كرتون|برنامج|عرض|مترجم|مترجمة|اون لاين|أون لاين|اونلاين|"
                     r"كامل|كاملة|HD)(?=\s|$)")
# "<li><span>النوع</span><p><a>..</a></p></li>" fields of a title page -> INFO keys
INFO_FIELDS = (("category", "التصنيف"), ("genres", "النوع"), ("quality", "الجودة"))


class MyCima(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "kind", "wf_id", "season_id", "post_id", "desc",
                  "s_title", "s_season", "s_episode", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "mycima", "cookie": "mycima.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/mycima.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("mycima")
        self.wfInitFolderCache()
        self.MENU = [
            {"category": "mc_section", "title": _("Movies"), "section": "movies"},
            {"category": "mc_section", "title": _("Series"), "section": "series"},
            {"category": "mc_section", "title": _("Anime") + " / " + _("Cartoons"), "section": "anime"},
            {"category": "mc_section", "title": _("Others"), "section": "other"},
        ] + self.searchItems()
        self.SECTIONS = {
            "movies": [
                ("%s - %s" % (_("Movies"), _("Latest")), "movies/"),
                (_("English movies"), "category/افلام-اجنبي/"),
                (_("Arabic movies"), "category/افلام-عربي/"),
                (_("Indian movies"), "category/افلام-هندي/"),
                (_("Turkish Movies"), "category/افلام-تركية/"),
                (_("Asian movies"), "category/افلام-اسيوية/"),
            ],
            "series": [
                (_("Newest Episodes"), "episodes/"),
                ("%s - %s" % (_("Series"), _("Latest")), "series/"),
                (_("English TV series"), "category/مسلسلات-اجنبي/"),
                (_("Arabic Series"), "category/مسلسلات-عربي/"),
                (_("Turkish TV series"), "category/مسلسلات-تركية/"),
                (_("Asian TV series"), "category/مسلسلات-اسيوية/"),
                (_("Dubbed series"), "category/مسلسلات-مدبلجة/"),
                ("%s 2026" % _("Ramadan"), "category/مسلسلات-رمضان-2026/"),
                ("%s 2025" % _("Ramadan"), "category/مسلسلات-رمضان-2025/"),
                ("%s 2024" % _("Ramadan"), "category/مسلسلات-رمضان-2024/"),
                ("%s 2023" % _("Ramadan"), "category/مسلسلات-رمضان-2023/"),
            ],
            "anime": [
                (_("Anime movies"), "category/افلام-انمي/"),
                (_("Anime TV series"), "category/مسلسلات-انمي/"),
            ],
            "other": [
                (_("Wrestling shows"), "category/عروض-مصارعة/"),
                (_("Pro wrestling"), "category/مصارعة-حرة/"),
                (_("TV Shows"), "category/برامج-تليفزيونية/"),
            ],
        }

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        # the site links the same page raw-Arabic or percent-encoded - one ASCII form
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
    def _path(url):
        # domain-independent part of a page url (watched keys survive the frequent domain changes)
        path = re.sub(r"^https?://[^/]+", "", url or "").split("?")[0].split("#")[0]
        try:
            path = urllib_unquote(path)
        except Exception:
            printExc()
        return path.rstrip("/").lower() + "/"

    @staticmethod
    def _clean(text):
        text = re.sub(r"(مسلسل|فيلم|انمي)(?=[A-Za-z0-9])", r"\1 ", text or "")  # "مسلسلBatman ..."
        text = JUNK_RE.sub(" ", SUBDUB_RE.sub(r"\1", text))
        return re.sub(r"\s+", " ", text).strip(" -:|")

    @staticmethod
    def _metaTitle(title):
        return re.sub(r"\s+", " ", re.sub(r"(?:^|\s)(?:مدبلج|مدبلجة)(?=\s|$)", " ", title or "")).strip()

    @staticmethod
    def _seasonNum(val):
        return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)

    def _parseTitle(self, title):
        # -> (name, year, season, episode) of a site label
        name = self._clean(title)
        season, episode, year = 0, 0, ""
        m = EPISODE_RE.search(name)
        if m:
            episode = int(m.group(1))
            name = name[:m.start()].strip()
        m = SEASON_RE.search(name)
        if m:
            season = self._seasonNum(m.group(1))
            name = (name[:m.start()] + " " + name[m.end():]).strip()
        name = re.sub(r"\s+", " ", name).strip(" -:|")
        m = YEAR_RE.search(name)
        if m and m.start() > 0:
            year = m.group(1)
            name = (name[:m.start()] + " " + m.group(2).strip()).strip(" -:|")
        return name, year, season, episode

    @staticmethod
    def _seasonId(show, season):
        return "%s|%d" % (re.sub(r"\s+", " ", show or "").strip().lower(), season or 1)

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or not cItem.get("kind"):
                return ""
            category = cItem.get("category", "")
            if category == "mc_video" and cItem.get("url"):
                return "video:%s" % self._path(cItem["url"])
            if category == "mc_season" and cItem.get("wf_id"):
                return "season:%s" % cItem["wf_id"]
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("kind"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def listSection(self, cItem):
        for title, path in self.SECTIONS.get(cItem.get("section", ""), []):
            self.addDir({"name": "category", "category": "mc_list", "good_for_fav": True, "title": title, "url": self._canonUrl(path)})

    def listItems(self, cItem):
        printDBG("MyCima.listItems [%s]" % cItem.get("url", ""))
        page = int(cItem.get("page", 1) or 1)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        grid = data[data.find("Grid--WecimaPosts"):] if "Grid--WecimaPosts" in data else data
        pagination = self.cm.ph.getDataBeetwenMarkers(grid, '<div class="pagination">', "</ul>", False)[1]
        grid = grid.split('<div class="pagination">')[0]
        normalize = IsMediaNamingNormalized()
        seen = set()
        count = 0
        for item in grid.split('<div class="GridItem">')[1:]:
            url = self._canonUrl(self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0])
            if not url:
                continue
            raw = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a href="[^"]+" title="([^"]+)"')[0])
            if not raw:
                raw = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<strong", "<span", False)[1])
            icon = self.cm.ph.getSearchGroups(item, r"url\(([^)]+)\)")[0].strip("'\" ")
            siteYear = self.cm.ph.getSearchGroups(item, r'<span class="year">\s*\(?\s*(\d{4})')[0]
            name, year, season, episode = self._parseTitle(raw)
            year = year or siteYear
            count += 1
            params = {"name": "category", "good_for_fav": True, "icon": self._canonUrl(icon) if icon else "", "url": url}
            if "/series/" in self._path(url):
                # a show's own page: the list of its episodes
                params.update({"category": "mc_list", "title": (name or raw) if normalize else raw})
                self.addDir(params)
            elif episode:
                # an episode post -> its season folder (one per show + season on this page)
                season = season or 1
                wfId = self._seasonId(name, season)
                if wfId in seen:
                    continue
                seen.add(wfId)
                title = ("%s - %s %d" % (name, _("Season"), season)) if normalize else raw
                params.update({"category": "mc_season", "kind": "season", "title": title, "wf_id": wfId, "desc": raw,
                               "s_title": name, "s_season": season, "meta_type": "tv", "meta_title": self._metaTitle(name), "meta_year": year})
                self.addDir(params)
            else:
                title = ("%s (%s)" % (name, year) if year else name) if normalize else raw
                params.update({"category": "mc_video", "kind": "movie", "title": title or raw,
                               "meta_type": "movie", "meta_title": self._metaTitle(name), "meta_year": year})
                self.addVideo(params)
        nextUrl = self.cm.ph.getSearchGroups(pagination, r'class="next page-numbers"[^>]*href="([^"]+)"')[0] or \
            self.cm.ph.getSearchGroups(pagination, r'href="([^"]+)"[^>]*class="next page-numbers"')[0]
        hasNext = bool(count and nextUrl)
        nums = [int(re.sub(r"\D", "", n)) for n in re.findall(r'class="page-numbers[^"]*"[^>]*>([^<]+)<', pagination) if re.sub(r"\D", "", n)]
        lastPage = max(nums + [page]) if hasNext else page
        base = cItem.get("page_base") or re.sub(r"/page/\d+/?", "/", cItem["url"])
        pager = dict(cItem, category="mc_list", page_base=base, url=base)
        if "?" in base:
            # search: only the site's own "next" link, no jump
            addPagingItems(self, pager, page, hasNext, lastPage, "", {"url": self._canonUrl(nextUrl)} if hasNext else None)
        else:
            addPagingItems(self, pager, page, hasNext, lastPage, base.rstrip("/") + "/page/{page}/")

    def _episodeRow(self, cItem, url, epNum, label, season):
        show = cItem.get("s_title", "")
        if IsMediaNamingNormalized() and epNum and show:
            title = "%s - %s" % (show, formatSxxExx(season, epNum))
        else:
            title = label
        return {"name": "category", "good_for_fav": True, "category": "mc_video", "kind": "episode", "title": title, "url": url,
                "icon": cItem.get("icon", ""), "s_title": show, "s_season": season, "s_episode": epNum,
                "meta_type": "tv", "meta_title": cItem.get("meta_title", ""), "meta_year": cItem.get("meta_year", "")}

    def _otherSeasons(self, cItem, data):
        # the show's other seasons as folders; -> number of the season shown on this page
        show = cItem.get("s_title", "")
        season = cItem.get("s_season", 1) or 1
        postId = self.cm.ph.getSearchGroups(data, r"post_id:\s*'(\d+)'")[0]
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="SeasonsList">', "</ul>", False)[1]
        normalize = IsMediaNamingNormalized()
        others = []
        for attrs, inner in re.findall(r"<li([^>]*)>(.*?)</li>", block, re.S):
            label = self.cleanHtmlStr(inner)
            num = self._parseTitle(label)[2]
            sid = self.cm.ph.getSearchGroups(inner, r'data-season="(\d+)"')[0]
            if "active" in attrs:
                season = num or season
                continue
            if not sid or not postId:
                continue
            others.append((num, {"name": "category", "good_for_fav": True, "category": "mc_season", "kind": "season",
                                 "title": ("%s - %s %d" % (show, _("Season"), num)) if (normalize and num) else ("%s %s" % (show, label)).strip(),
                                 "url": cItem["url"], "icon": cItem.get("icon", ""),
                                 "wf_id": self._seasonId(show, num) if num else "%s|id%s" % (show.lower(), sid),
                                 "season_id": sid, "post_id": postId, "s_title": show, "s_season": num or 1,
                                 "meta_type": "tv", "meta_title": cItem.get("meta_title", ""), "meta_year": cItem.get("meta_year", "")}))
        others.sort(key=lambda o: o[0])
        for _num, params in others:
            self.addDir(params)
        return season

    def listSeason(self, cItem):
        printDBG("MyCima.listSeason [%s]" % cItem.get("url", ""))
        season = cItem.get("s_season", 1) or 1
        if cItem.get("season_id"):
            # another season of the show: the theme loads its episodes by Ajax
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=self._canonUrl(cItem["url"]))
            params["header"]["X-Requested-With"] = "XMLHttpRequest"
            sts, block = self.getPage(self.getFullUrl("wp-content/themes/mycima/Ajaxt/Single/Episodes.php"), params,
                                      {"season": cItem["season_id"], "post_id": cItem.get("post_id", "")})
            if not sts:
                return
            data = ""
        else:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
            season = self._otherSeasons(cItem, data)
            block = data[data.find('<div class="EpisodesList">'):] if '<div class="EpisodesList">' in data else ""
            block = block.split("</singlesection>")[0].split("<script")[0]
        episodes = []
        seen = set()
        for href, inner in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S):
            url = self._canonUrl(href)
            if url in seen or "episodetitle" not in inner:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(inner, "<episodetitle>", "</episodetitle>", False)[1]) or self.cleanHtmlStr(inner)
            epNum = self._parseTitle(label)[3] or int(self.cm.ph.getSearchGroups(label, r"(\d+)")[0] or 0)
            episodes.append((epNum, self._episodeRow(cItem, url, epNum, label, season)))
        if not episodes and data:
            # no episode list on the page: the post itself is the only episode
            label = cItem.get("desc", "") or cItem.get("title", "")
            episodes.append((0, self._episodeRow(cItem, self._canonUrl(cItem["url"]), self._parseTitle(label)[3], label, season)))
        episodes.sort(key=lambda e: e[0])
        for _num, params in episodes:
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MyCima.listSearchResult [%s]" % searchPattern)
        base = self.getFullUrl("filtering/?keywords=%s" % urllib_quote_plus(searchPattern))
        self.listItems(dict(cItem, url=base, page_base=base, page=1))

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="StoryMovieContent">', "</div>", False)[1])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0] or \
            self.cm.ph.getSearchGroups(data, r'separated--top" style="--img:url\(([^)]+)\)')[0]
        return story, self._canonUrl(poster) if poster else ""

    def getLinksForVideo(self, cItem):
        printDBG("MyCima.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        urltab = []
        names = {}

        def add(name, url):
            if not self.cm.isValidUrl(url) or url in [u["url"] for u in urltab]:
                return
            names[name.lower()] = names.get(name.lower(), 0) + 1
            if names[name.lower()] > 1:
                name = "%s %d" % (name, names[name.lower()])
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": pageUrl}), "need_resolve": 1})

        watch = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="WatchServersList">', "</div>", False)[1]
        watchNames = set()
        for li in re.findall(r"<li[^>]+data-watch=.*?</li>", watch, re.S):
            url = self.cm.ph.getSearchGroups(li, r'data-watch="([^"]+)"')[0].strip()
            name = self.cleanHtmlStr(li) or self.up.getDomain(url, onlyDomain=True)
            watchNames.add(name.lower())
            add(name, url)
        download = self.cm.ph.getDataBeetwenMarkers(data, "List--Download--Wecima--Single", "</ul>", False)[1]
        for href, inner in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', download, re.S):
            name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(inner, "<quality>", "</quality>", False)[1]) or self.up.getDomain(href, onlyDomain=True)
            if name.lower() not in watchNames:
                add(name, href.strip())
        if not urltab:
            # posts whose server list the site lost show {"error":"Invalid ID"} instead of servers
            SetIPTVPlayerLastHostError(_("No stream available"))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        # watch servers are govid.live/play/<token> pages (urlparser.parserGOVID), downloads go to their hoster
        printDBG("MyCima.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("MyCima.getArticleContent [%s]" % cItem.get("url", ""))
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
            terms = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="Terms--Content--Single-begin">', "</ul>", False)[1]
            for li in re.findall(r"<li>(.*?)</li>", terms, re.S):
                label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(li, "<span>", "</span>", False)[1])
                values = [self.cleanHtmlStr(v) for v in re.findall(r"<a[^>]*>(.*?)</a>", li, re.S)]
                values = [v for v in values if v and v != "ماي سيما"]
                for key, word in INFO_FIELDS:
                    if label == word and values:
                        info[key] = ", ".join(values)
            year = self.cm.ph.getSearchGroups(data, r"/release-year/(\d{4})/")[0]
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
        printDBG("MyCima.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "mc_section":
            self.listSection(self.currItem)
        elif category == "mc_list":
            self.listItems(self.currItem)
        elif category == "mc_season":
            self.listSeason(self.currItem)
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
        CHostBase.__init__(self, MyCima(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("mycima")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("mc_video", "mc_season")
