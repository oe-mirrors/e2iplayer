# -*- coding: utf-8 -*-
LAST_MODIFIED = "21.11.2026"
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
# 21.11.2026 - new site theme ("madar"): new list paths, cards, episode pages and player sources
#   - Space Power Fan (spacepowerfan.com, Arabic-dubbed cartoons and anime, WordPress): movies, series, anime,
#     cartoons, latest episodes and search; First page / Jump / Next page over /page/N/ (last page from the pager)
#   - Cloudflare challenged every request there in 10.2026 (not in 11.2026): pages go through
#     getPageCFProtection (MyE2i solve on the box), covers (wp-content/uploads) get the same cf_clearance
#     cookie and the User-Agent that passed the check
#   - title -> episodes (VIDEO rows keyed on the episode page url, the site's episode pages ?ep_page=N of 60);
#     a movie is one VIDEO row (its watch page); links: the watch page's JSON player sources (server + quality),
#     the site's own player pages give their <source> directly, the rest goes to urlparser
#   - watched flag (title -> episode), downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx", the season taken from "الجزء/الموسم <n>" in the title), sidecar, INFO via moviemeta +
#     the title page's fields
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://spacepowerfan.com/"


# list urls of the old theme (favourites) -> the new ones
OLD_LIST_PATHS = {"/anime-type/movie/": "/movies/", "/anime-type/tv/": "/series/", "/anime-type/%D9%83%D8%B1%D8%AA%D9%88%D9%86/": "/cartoon/"}
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثانى", 2), ("الثالث", 3),
    ("الرابع", 4), ("الخامس", 5), ("السادس", 6), ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10),
]
# "وان بيس الجزء الثاني مدبلج" / "... الموسم 3" / "الجزء الخامس والعشرون" (25)
SEASON_TENS = {"العشرون": 20, "الثلاثون": 30}
SEASON_RE = re.compile(r"\s*(?:الجزء|الموسم)\s*(\d+|%s)(?:\s+و(%s))?" % ("|".join(o[0] for o in SEASON_ORDINALS), "|".join(SEASON_TENS)))
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")
# words behind every name of the site: "مدبلج بالعربية" / "اونلاين"
TAIL_RE = re.compile(r"\s+(?:مدبلج(?:ة)?|بالعربية|بالعربي|اونلاين|أونلاين)(?=\s|$)")
VIDEO_CATEGORIES = ("spf_video",)
FOLDER_CATEGORIES = ("spf_show",)


def _cleanName(name):
    return re.sub(r"\s{2,}", " ", TAIL_RE.sub("", name or "")).strip(" -")


def _splitSeason(name):
    # "وان بيس الجزء الثاني" -> ("وان بيس", 2); no season word -> (name, 1)
    match = SEASON_RE.search(name or "")
    if not match:
        return name, 1
    value = match.group(1)
    season = int(value) if value.isdigit() else dict(SEASON_ORDINALS).get(value, 1) + SEASON_TENS.get(match.group(2) or "", 0)
    return (name[:match.start()] + name[match.end():]).strip(" -") or name, season


class SpacePowerFan(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "show_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "spacepowerfan", "cookie": "spacepowerfan.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("spacepowerfan")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(self.getFullUrl((baseUrl or "").replace("&amp;", "&")), addParams, post_data)

    def _path(self, url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", url or "").split("?")[0].rstrip("/").lower()

    def _cfMeta(self):
        # cf_clearance + the User-Agent that passed the check, for downloads outside getPage (covers, own player)
        meta = {"Referer": self.MAIN_URL}
        try:
            # getCookieHeader logs a traceback for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return meta

    def _isSite(self, url):
        return self.up.getDomain(url).endswith("spacepowerfan.com")

    def getFullIconUrl(self, url, currUrl=None):
        # the covers (wp-content/uploads) sit behind the same Cloudflare check as the pages
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        if not url.startswith("http") or not self._isSite(url):
            return url
        return strwithmeta(url, self._cfMeta())

    def getFavouriteData(self, cItem):
        if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("spf_list",):
            return self.getFavouriteFieldsData(cItem)
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        return self.wfCategoryKey(cItem, self._path, VIDEO_CATEGORIES, FOLDER_CATEGORIES)

    def _icon(self, html):
        icon = self.cm.ph.getSearchGroups(html, r"""<img[^>]+src=['"]([^'"]+)['"]""")[0]
        if not icon or icon.startswith("data:"):
            icon = self.cm.ph.getSearchGroups(html, r"""srcset=['"]([^'" ]+)""")[0]
        return self.getFullIconUrl(icon) if icon and not icon.startswith("data:") else ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "spf_list", "title": _("Movies"), "url": self.getFullUrl("/movies/")},
            {"category": "spf_list", "title": _("Series"), "url": self.getFullUrl("/series/")},
            {"category": "spf_list", "title": _("Anime"), "url": self.getFullUrl("/anime/")},
            {"category": "spf_list", "title": _("Cartoons"), "url": self.getFullUrl("/cartoon/")},
            {"category": "spf_list", "title": _("Latest episodes"), "url": self.getFullUrl("/episodes/")},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    @staticmethod
    def _metaTitle(enName):
        # "One Piece Arabic S2" / "Detective Conan: The Raven Chaser AR" -> the name for moviemeta
        return re.sub(r"(?i)\s+(?:arabic|ar|arc|S\d+)\b.*$", "", enName or "").strip()

    def _episodeTitle(self, show, season, number, folderTitle, label):
        if IsMediaNamingNormalized() and number:
            return "%s - %s" % (show, formatSxxExx(season, number))
        return "%s - %s" % (folderTitle, label or number)

    def _addCard(self, card):
        url = self.cm.ph.getSearchGroups(card, r'class="card__link"[^>]+href="([^"]+)"')[0]
        name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="card__title"[^>]*>(.*?)</h3>')[0])
        if not url or not name:
            return False
        cardMeta = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="card__meta"[^>]*>(.*?)</span>')[0])
        show, season = _splitSeason(_cleanName(name))
        if "/watch/" in url:
            # "latest episodes": the card is one episode ("الحلقة 1219") of the show in the title
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="card__ep"[^>]*>(.*?)</span>')[0])
            number = EPISODE_RE.search(label)
            number = number.group(1) if number else ""
            self.addVideo({"name": "category", "category": "spf_video", "good_for_fav": True, "url": url, "icon": self._icon(card),
                           "title": self._episodeTitle(show, season, number, name, label), "desc": " | ".join(x for x in (label, cardMeta) if x),
                           "s_title": show, "s_season": season, "s_episode": number, "meta_type": "tv", "meta_title": show})
            return True
        badge = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="card__badge"[^>]*>(.*?)</span>')[0])
        isMovie = self.cm.ph.getSearchGroups(card, r'data-type="([^"]+)"')[0] == "movie"
        self.addDir({"name": "category", "category": "spf_show", "good_for_fav": True, "url": url, "title": name,
                     "desc": " | ".join(x for x in (cardMeta, badge) if x), "icon": self._icon(card), "s_title": show,
                     "s_season": season, "meta_type": "movie" if isMovie else "tv", "meta_title": show})
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        for old, new in OLD_LIST_PATHS.items():
            if baseUrl.endswith(old):
                baseUrl = self.getFullUrl(new)
        if "?" in baseUrl:
            base, query = baseUrl.split("?", 1)
            pageTpl = base.rstrip("/") + "/page/{page}/?" + query.replace("{", "{{").replace("}", "}}")
        else:
            pageTpl = baseUrl.replace("{", "{{").replace("}", "}}") + "page/{page}/"
        url = baseUrl if page <= 1 else pageTpl.format(page=page)
        printDBG("SpacePowerFan.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = 0
        for card in data.split('<article class="card')[1:]:
            if self._addCard(card.split("</article>", 1)[0]):
                count += 1
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pager"', "</nav>", False)[1]
        lastPage = max([int(n) for n in re.findall(r"/page/(\d+)/", pager)] + [page])
        hasNext = bool(count) and ("next page-numbers" in pager or lastPage > page)
        addPagingItems(self, dict(cItem, base_url=baseUrl, url=baseUrl), page, hasNext, lastPage, pageTpl)

    def listShow(self, cItem):
        printDBG("SpacePowerFan.listShow [%s] page[%s]" % (cItem.get("url", ""), cItem.get("page", 1)))
        page = cItem.get("page", 1)
        # the site lists 60 episodes per page: <title url>?ep_page=N
        url = cItem["url"] if page <= 1 else "%s%sep_page=%d" % (cItem["url"], "&" if "?" in cItem["url"] else "?", page)
        sts, data = self.getPage(url)
        if not sts:
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        folderTitle = cItem.get("folder_title") or cItem.get("title", show)
        # the year and the English name INFO takes from this show page: the moviemeta query of the download sidecar
        info = self._siteInfo(data)[2]
        year = info.get("year", "")
        metaTitle = self._metaTitle(info.get("original_title", "")) or cItem.get("meta_title", show)
        episodes, seen = [], set()
        for item in data.split('<li class="ep"')[1:]:
            item = item.split("</li>", 1)[0]
            href = self.cm.ph.getSearchGroups(item, r'class="ep__link"[^>]+href="([^"]+)"')[0]
            if not href or href in seen:
                continue
            seen.add(href)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="ep__title"[^>]*>(.*?)</span>')[0])
            number = EPISODE_RE.search(label) or re.search(r'data-ep-search="(\d+)', item)
            episodes.append((int(number.group(1)) if number else len(episodes) + 1, href, label, self._icon(item)))
        if not episodes:
            # a movie: one watch page behind the "watch" button of the title page
            watch = self.cm.ph.getSearchGroups(data, r'class="btn btn--primary[^"]*"[^>]+href="([^"]+/watch/[^"]+)"')[0]
            if watch:
                self.addVideo(dict(cItem, category="spf_video", url=watch, show_url=cItem["url"], meta_title=metaTitle, meta_year=year))
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return
        episodes.sort(key=lambda e: e[0])
        if cItem.get("meta_type") == "movie" and len(episodes) == 1 and page <= 1:
            self.addVideo(dict(cItem, category="spf_video", url=episodes[0][1], show_url=cItem["url"], meta_title=metaTitle, meta_year=year))
            return
        for number, href, label, icon in episodes:
            self.addVideo({"name": "category", "category": "spf_video", "good_for_fav": True, "url": href,
                           "title": self._episodeTitle(show, season, number, folderTitle, label),
                           "icon": icon or cItem.get("icon", ""), "desc": label, "show_url": cItem["url"], "s_title": show,
                           "s_season": season, "s_episode": str(number), "meta_type": "tv", "meta_title": metaTitle,
                           "meta_year": year})
        ranges = self.cm.ph.getDataBeetwenMarkers(data, 'class="ep-ranges"', "</nav>", False)[1]
        lastPage = max([int(n) for n in re.findall(r"[?&]ep_page=(\d+)", ranges)] + [page])
        if lastPage > 1:
            addPagingItems(self, dict(cItem, folder_title=folderTitle), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        printDBG("SpacePowerFan.listSearchResult [%s]" % pattern)
        cItem = dict(cItem)
        # WordPress search, pages /page/N/?s=
        base = self.getFullUrl("/?s=%s" % urllib_quote_plus(pattern))
        cItem.update({"category": "spf_list", "s_pattern": pattern, "url": base, "base_url": base})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("SpacePowerFan.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab, seen = [], set()
        # <script type="application/json" data-player-sources>[{"name": server, "links": [{"q": "1080p", "url": .., "broken": false}]}]
        sources = []
        try:
            sources = json_loads(self.cm.ph.getSearchGroups(data, r"(?s)<script[^>]+data-player-sources[^>]*>(.*?)</script>")[0] or "[]")
        except Exception:
            printExc()
        for server in sources if isinstance(sources, list) else []:
            if not isinstance(server, dict):
                continue
            for item in server.get("links") or []:
                link = (item.get("url") or "").strip().replace("&#038;", "&").replace("&amp;", "&")
                if link.startswith("//"):
                    link = "https:" + link
                # mega.nz (cloud player, no parser) can never play here
                if item.get("broken") or not self.cm.isValidUrl(link) or link in seen or self.up.getDomain(link).endswith("mega.nz"):
                    continue
                seen.add(link)
                name = " ".join(x for x in (self.cleanHtmlStr(server.get("name") or "") or self.up.getDomain(link), item.get("q") or "") if x)
                urltab.append({"name": name, "url": strwithmeta(link, {"Referer": url}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("SpacePowerFan.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if self.up.getDomain(videoUrl).endswith("4shared.com"):
            return decorateResolvedLinkItems(self._fourShared(videoUrl), sidecar)
        if not self._isSite(videoUrl):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        # the site's own player: /video-embed-page/?video_url=<mp4 on its video CDN, no Cloudflare check there>
        direct = self.cm.ph.getSearchGroups(videoUrl, r"[?&]video_url=([^&]+)")[0]
        if direct:
            direct = urllib_unquote(direct)
            if self.cm.isValidUrl(direct):
                header = {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
                return decorateResolvedLinkItems([{"name": "mp4", "url": strwithmeta(direct, header)}], sidecar)
        # other own player pages: <video><source src="..mp4"></video> on the same Cloudflare domain
        sts, data = self.getPage(videoUrl)
        if not sts:
            return []
        links = []
        for src, label in re.findall(r"""<source[^>]+src=['"]([^'"]+)['"](?:[^>]+(?:label|size)=['"]([^'"]*)['"])?""", data):
            src = self.getFullUrl(src.replace("&amp;", "&"))
            meta = self._cfMeta() if self._isSite(src) else {"Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
            links.append({"name": label or "mp4", "url": strwithmeta(src, meta)})
        if not links:
            iframe = self.cm.ph.getSearchGroups(data, r"""<iframe[^>]+src=['"]([^'"]+)['"]""")[0]
            if self.cm.isValidUrl(iframe):
                links = self.up.getVideoLinkExt(strwithmeta(iframe, {"Referer": videoUrl}))
        return decorateResolvedLinkItems(links, sidecar)

    def _fourShared(self, embedUrl):
        # www.4shared.com/web/embed/file/<id> (not in urlparser's hostMap, 08.10.2026): <source src="..preview.mp4">
        # on its own CDN, the link is bound to the client IP
        sts, data = self.cm.getPage(str(embedUrl), {"header": dict(self.HEADER, Referer=self.MAIN_URL)})
        if not sts:
            return []
        src = self.cm.ph.getSearchGroups(data, r"""<source[^>]+src=['"]([^'"]+)['"]""")[0].replace("&amp;", "&")
        if not self.cm.isValidUrl(src):
            return []
        return [{"name": "4shared", "url": strwithmeta(src, {"Referer": "https://www.4shared.com/", "User-Agent": self.HEADER.get("User-Agent")})}]

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of a title page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="detail__story[^"]*"[^>]*>(.*?)</div>')[0])
        # <div class="info-item"><dt>label</dt><dd>value</dd></div>
        fields = {}
        for label, value in re.findall(r"(?s)<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", data):
            fields[self.cleanHtmlStr(label)] = value
        info = {}
        for key, labels in (("original_title", ("الاسم الأصلي",)), ("released", ("تاريخ العرض",)), ("duration", ("مدة الفيلم", "مدة الحلقة")),
                            ("episodes", ("الحلقات المتاحة",)), ("rating", ("التقييم",)), ("status", ("الحالة",))):
            value = "".join(self.cleanHtmlStr(fields.get(label, "")) for label in labels)
            if value:
                info[key] = value
        genres = [self.cleanHtmlStr(g) for g in re.findall(r'(?s)class="tag"[^>]+href="[^"]*/genre/[^"]*"[^>]*>(.*?)</a>', data)]
        if genres:
            info["genres"] = ", ".join(g for g in genres if g)
        year = self.cm.ph.getSearchGroups(self.cleanHtmlStr(fields.get("سنة الإصدار", "")) + " " + info.get("released", ""), r"((?:19|20)\d{2})")[0]
        if year:
            info["year"] = year
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, poster, info

    def getArticleContent(self, cItem):
        printDBG("SpacePowerFan.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("show_url") or cItem.get("url", ""))
        # an episode of "latest episodes" knows only its watch page: the title page is its "work" link
        workUrl = self.cm.ph.getSearchGroups(data, r'class="watch__work"[^>]+href="([^"]+)"')[0] if sts and not cItem.get("show_url") else ""
        if workUrl:
            sts, data = self.getPage(workUrl)
        if sts:
            story, poster, info = self._siteInfo(data)
        title = cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
        if not isLatinTitle(title):
            # the cards carry only the Arabic name, the title page its English one ("Detective Conan S25")
            title = self._metaTitle(info.get("original_title", "")) or title
        meta = {}
        try:
            meta = getMeta(cItem.get("meta_type") or "tv", title, info.get("year", ""), () if isLatinTitle(title) else LATIN_ONLY)
        except Exception:
            printExc()
        status = info.get("status", "")
        info.update(meta.get("info", {}))
        if status:
            info["status"] = status  # the site's airing status, not moviemeta's
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = (self.getFullIconUrl(poster) if poster else "") or meta.get("poster") or cItem.get("icon", "")
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
        printDBG("SpacePowerFan.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "spf_list":
            self.listItems(self.currItem)
        elif category == "spf_show":
            self.listShow(self.currItem)
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
        CHostBase.__init__(self, SpacePowerFan(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("spacepowerfan")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
