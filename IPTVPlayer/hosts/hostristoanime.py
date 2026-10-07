# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 framework / host standard
#   - ristoanime.me (Arabic-subtitled anime): latest episodes, anime series, anime movies, most viewed and
#     search, with First page / Jump / Next page (the site mixes ?page=N/, ?offset=N and /page/N/ - the
#     template is read from the page's own pager links)
#   - series -> seasons (site AJAX Episodes.php, when the show has more than one) -> episodes (ascending,
#     local paging over 100); movies and episodes are VIDEO rows keyed on their page url; the episode's
#     /watch/ page server list (data-watch) is handed to urlparser
#   - watched flag (series:/season:/video: keys), downloaded flag, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the page's story / taxonomy rows
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
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://ristoanime.me/"


LOCAL_PAGE_SIZE = 100
EPISODES_AJAX = "/wp-content/themes/TopAnime/Ajaxt/Single/Episodes.php"
# "انمي Ao no Hako الموسم 2 الحلقة 1 مترجمة اون لاين" -> "Ao no Hako", season 2, episode 1
PREFIX_RE = re.compile(r"^\s*(?:مشاهدة\s+)?(?:جميع\s+حلقات\s+)?(?:انمي|أنمي|فيلم)\s+")
# the tail from the first of these words on is cut off ("اونلاين" is covered by "اون\s*لاين")
TAIL_RE = re.compile(r"مترجمة|مترجم|مدبلجة|مدبلج|اون\s*لاين|أون\s*لاين")
LINK_TAG_RE = re.compile(r"<a([^>]*)>")
HREF_RE = re.compile(r'href="([^"]+)"')
EPISODE_RE = re.compile(r"الحلقة\s*(\d+)")
SEASON_ORDINALS = [
    ("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثانى", 2), ("الثالث", 3), ("الرابع", 4), ("الخامس", 5),
    ("السادس", 6), ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
# "<span>النوع : </span><a>..</a>" rows of the page -> INFO keys
TAX_KEYS = (("category", "التصنيف"), ("genres", "النوع"), ("duration", "مدة العرض"), ("year", "تاريخ الاصدار"),
            ("quality", "الجودة"), ("status", "الحالة"))


def _cutTail(name):
    # name without its tail from the first TAIL_RE word on that ends the name or is followed by a space (and the
    # spaces before it), like the former re.sub(r"\s*(?:words)(?:\s.*)?$", "", name)
    pos = 0
    while True:
        match = TAIL_RE.search(name, pos)
        if not match:
            return name
        rest = name[match.end():]
        body = rest[1:-1] if rest.endswith("\n") else rest[1:]
        if not rest or (rest[0].isspace() and "\n" not in body):
            return name[:match.start()].rstrip()
        pos = match.start() + 1


def _links(data):
    # [(href, inner html)] of the <a ... href="..." ...>...</a> links (the last href of a tag, like the greedy
    # r'(?s)<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>')
    rows, pos = [], 0
    while True:
        tag = LINK_TAG_RE.search(data, pos)
        if not tag:
            return rows
        end = data.find("</a>", tag.end())
        if end < 0:
            return rows
        href, attrPos = "", 1
        while True:
            match = HREF_RE.search(tag.group(1), attrPos)
            if not match:
                break
            href, attrPos = match.group(1), match.start() + 1
        if href:
            rows.append((href, data[tag.end():end]))
            pos = end + 4
        else:
            pos = tag.start() + 1


def _cleanName(title):
    # -> (show / movie name, season, episode)
    episode = EPISODE_RE.search(title or "")
    season = SEASON_RE.search(title or "")
    name = PREFIX_RE.sub("", title or "")
    name = EPISODE_RE.split(name)[0]
    name = SEASON_RE.split(name)[0]
    name = re.sub(r"\s+", " ", _cutTail(name)).strip(" -:")
    seasonNum = 0
    if season:
        val = season.group(1)
        seasonNum = int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)
    return (name or title), seasonNum, (str(int(episode.group(1))) if episode else "")


def _metaTitle(name):
    # add 071026: "ون بيس One Piece" / "Kimetsu no Yaiba قاتل الشياطين" -> the Latin words for the metadata search
    latin = " ".join(word for word in (name or "").split() if re.search(r"[A-Za-z0-9]", word))
    return latin or name


class RistoAnime(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "season_id", "series_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "ristoanime", "cookie": "ristoanime.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/ristoanime135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "list_items", "title": _("Latest episodes"), "url": self.getMainUrl()},
            {"category": "list_items", "title": _("Anime Series"), "url": self.getFullUrl("/series/")},
            {"category": "list_items", "title": _("Anime Movies"), "url": self.getFullUrl("/movies/")},
            {"category": "list_items", "title": _("Most viewed"), "url": self.getFullUrl("/views/")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("ristoanime")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

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
        # domain independent identity of a page
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("ra_video", "ra_series", "ra_season"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    @staticmethod
    def _episodeTitle(show, season, episode, label):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (show, formatSxxExx(season or 1, episode))
        return label

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            prefix = {"ra_video": "video", "ra_series": "series", "ra_season": "season"}.get(category, "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            if path and category == "ra_season":
                path = "%s#%s" % (path, cItem.get("season_id", ""))
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _pageTpl(self, pager):
        # the url of any numbered pager link with its number replaced by {page}
        for href, num in re.findall(r"""href=['"]([^'"]+)['"][^>]*>\s*(\d+)\s*<""", pager):
            href = self._canonUrl(href)
            tpl = re.sub(r"(offset=|page=|/page/)%s(?=\D|$)" % num, r"\g<1>{page}", href, count=1)
            if "{page}" in tpl:
                return tpl
        return ""

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or self._canonUrl(cItem.get("url", ""))
        pageTpl = cItem.get("page_tpl", "")
        url = baseUrl if page <= 1 or not pageTpl else pageTpl.format(page=page)
        printDBG("RistoAnime.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="MovieItem">', "</a>"):
            href = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0]
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h4>(.*?)</h4>")[0])
            if not href or not rawTitle:
                continue
            url = self._canonUrl(href)
            if url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(item, r"url\(([^)'\"]+)\)")[0]
            fields = [self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="%s">(.*?)</span>' % cls)[0])
                      for cls in ("categorySpan", "genre", "quality", "release-year")]
            ribbon = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="ribbon">([^<]*)<')[0])
            name, season, episode = _cleanName(rawTitle)
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(self._quote(icon)) if icon else "",
                      "desc": " | ".join(x for x in fields + [ribbon] if x), "meta_title": name}
            if "/series/" in url:
                params.update({"category": "ra_series", "title": name if normalize else rawTitle, "s_title": name,
                               "s_season": season or 1, "meta_type": "tv"})
                self.addDir(params)
            elif episode:
                params.update({"category": "ra_video", "title": self._episodeTitle(name, season, episode, rawTitle), "s_title": name,
                               "s_season": season or 1, "s_episode": episode, "meta_type": "tv"})
                self.addVideo(params)
            else:
                params.update({"category": "ra_video", "title": name if normalize else rawTitle, "meta_type": "movie"})
                self.addVideo(params)

        pager = self.cm.ph.getDataBeetwenMarkers(data, "class='pagination'", "</ul>", False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', "</ul>", False)[1]
        pageTpl = pageTpl or self._pageTpl(pager)
        lastPage = max([int(n) for n in re.findall(r">\s*(\d+)\s*<", pager)] + [page])
        hasNext = bool(seen) and bool(pageTpl) and lastPage > page
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "page_tpl": pageTpl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def listSeries(self, cItem):
        # one season -> its episodes, more seasons -> season folders (episodes come from the site's AJAX call)
        printDBG("RistoAnime.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="SeasonsList"', "</ul>", False)[1]
        seasons = re.findall(r'(?s)data-season="(\d+)"[^>]*>(.*?)</a>', block)
        if len(seasons) <= 1:
            self.listEpisodes(cItem, data)
            return
        for idx, (seasonId, label) in enumerate(seasons):
            label = self.cleanHtmlStr(label)
            num = _cleanName(label)[1] or idx + 1
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "ra_season", "title": "%s - %s" % (cItem.get("s_title", ""), formatSxxExx(num))
                           if IsMediaNamingNormalized() else label, "season_id": seasonId, "s_season": num})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("RistoAnime.listEpisodes [%s]" % cItem.get("url", ""))
        if data is None:
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=cItem["url"])
            params["header"]["X-Requested-With"] = "XMLHttpRequest"
            sts, data = self.getPage(self.getFullUrl(EPISODES_AJAX), params, {"season": cItem.get("season_id", ""), "post_id": "0"})
            if not sts:
                return
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, 'class="EpisodesList', "</div>", False)[1]
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 1)
        episodes = []
        seen = set()
        for href, label in _links(data):
            url = self._canonUrl(href)
            label = self.cleanHtmlStr(label)
            # "الحلقة N" first: a label like "الموسم 2 الحلقة 5" must not give episode 2
            episode = EPISODE_RE.search(label)
            num = episode.group(1) if episode else self.cm.ph.getSearchGroups(label, r"(\d+)")[0]
            if url in seen or not num:
                continue
            seen.add(url)
            episodes.append({"name": "category", "good_for_fav": True, "category": "ra_video", "url": url, "icon": cItem.get("icon", ""),
                             "title": self._episodeTitle(show, season, num, "%s - %s" % (cItem.get("title", show), label)),
                             "desc": cItem.get("desc", ""), "series_url": cItem["url"], "s_title": show, "s_season": season,
                             "s_episode": str(int(num)), "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        episodes.sort(key=lambda e: int(e["s_episode"]))  # the site lists the newest first
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("RistoAnime.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        base = self.getFullUrl("/?s=%s" % urllib_quote_plus(searchPattern.strip()))
        cItem.update({"category": "list_items", "page": 1, "url": base, "base_url": base})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        info = {}
        tax = self.cm.ph.getDataBeetwenMarkers(data, 'class="TaxContent"', 'class="Others"', False)[1]
        for key, word in TAX_KEYS:
            val = self.cm.ph.getSearchGroups(tax, r"(?s)<span>\s*%s\s*:\s*</span>(.*?)</li>" % word)[0]
            val = ", ".join(v for v in [self.cleanHtmlStr(a) for a in re.findall(r"(?s)<a[^>]*>(.*?)</a>", val)] if v)
            if val:
                info[key] = val
        rating = self.cm.ph.getSearchGroups(data, r"(?s)IMDb.{0,200}?>\s*10\s*/\s*([\d.]+)")[0]
        if rating:
            info["imdb_rating"] = rating
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="StoryArea">.*?<p>(.*?)</p>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(self._quote(poster)) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("RistoAnime.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = self._canonUrl(cItem.get("url", ""))
        if not url.endswith("/watch/"):
            url = url.rstrip("/") + "/watch/"
        sts, data = self.getPage(url)
        if not sts:
            return []
        referer = self.cm.meta.get("url", url)
        servers = self.cm.ph.getDataBeetwenMarkers(data, 'class="ServersList"', "</ul>", False)[1]
        urltab = []
        seen = set()
        for link, label in re.findall(r'(?s)data-watch="([^"]+)"[^>]*>(.*?)</li>', servers):
            link = link.replace("&amp;", "&").strip()
            if link.startswith("//"):
                link = "https:" + link
            if not self.cm.isValidUrl(link) or link in seen or "mega.nz/" in link:
                continue  # mega.nz: no resolver in urlparser (it needs the MEGA crypto API)
            seen.add(link)
            label = self.cleanHtmlStr(re.sub(r"(?s)<span>.*?</span>|<noscript>.*?</noscript>", "", label))
            hostName = self.up.getHostName(link)
            urltab.append({"name": "%s - %s" % (label, hostName) if label else hostName,
                           "url": strwithmeta(link, {"Referer": referer}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("RistoAnime.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("RistoAnime.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("series_url") or cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], _metaTitle(cItem["meta_title"]), info.get("year", ""))
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
        printDBG("RistoAnime.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "ra_series":
            self.listSeries(self.currItem)
        elif category == "ra_season":
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
        CHostBase.__init__(self, RistoAnime(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("ristoanime")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("ra_video", "ra_series", "ra_season")
