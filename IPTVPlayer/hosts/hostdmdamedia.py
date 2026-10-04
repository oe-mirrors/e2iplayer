# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - revival + rewrite for the redesigned dmdamedia.hu
#   ("movie-card" grids with First page / Jump / Next page, /kategoria/<slug> lists, POST /search,
#    seasons via POST /epizod_betoltes, ?a=<provider> switches the player <iframe>:
#    Filemoon = byse embed, Videa) + watched flag / downloaded flag / name normalisation /
#    sidecar / moviemeta INFO (IMDb id from the title page) / favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://dmdamedia.hu/"


# episode page: /<slug>/<season>.evad/<episode>.resz
EPISODE_RE = re.compile(r'^https?://[^/]+/([^/?#]+)/(\d+)\.evad/(\d+)\.resz')
# paging / search state of a list that must not reach the rows listed in it
LIST_STATE_KEYS = ("base_url", "page_tpl", "search_pattern")


class Dmdamedia(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # what identifies a row and is needed to open it again (desc carries the IMDb rating, which changes)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "slug", "season", "episode", "lang",
                  "series_url", "icon", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "dmdamedia", "cookie": "dmdamedia.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        # orderby: legnezettebb = most viewed, feltoltes = newest uploads, friss = recently updated
        self.MENU = [{"category": "list_items", "title": "%s - %s" % (_("Movies"), _("Most viewed")), "url": self.getFullUrl("filmek?orderby=legnezettebb"), "kind": "movie"},
                     {"category": "list_items", "title": "%s - %s" % (_("Movies"), _("Latest")), "url": self.getFullUrl("filmek?orderby=feltoltes"), "kind": "movie"},
                     {"category": "list_items", "title": "%s - %s" % (_("Movies"), _("Latest updates")), "url": self.getFullUrl("filmek?orderby=friss"), "kind": "movie"},
                     {"category": "list_items", "title": "%s - %s" % (_("Series"), _("Latest updates")), "url": self.getFullUrl("sorozatok?orderby=friss"), "kind": "series"},
                     {"category": "list_items", "title": "%s - %s" % (_("Series"), _("Most viewed")), "url": self.getFullUrl("sorozatok?orderby=legnezettebb"), "kind": "series"},
                     {"category": "list_items", "title": "%s - %s" % (_("Series"), _("Latest")), "url": self.getFullUrl("sorozatok?orderby=feltoltes"), "kind": "series"},
                     {"category": "list_cats", "title": _("Categories"), "url": self.MAIN_URL}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("dmdamedia")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            url = str(cItem.get("url", "") or "").strip()
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url if url else ""
            if category == "dm_series":
                return "series:%s" % url if url else ""
            if category == "dm_season":
                slug = str(cItem.get("slug", "") or "").strip()
                season = str(cItem.get("season", "") or "").strip()
                return "season:%s|%s" % (slug, season) if slug and season else ""
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _posterUrl(self, url, currUrl=None):
        # the pages reference /kepek/<slug>_poster.jpg, but many of these jpgs are 404 - the .webp
        # next to it always exists (the browser lives with the broken pictures)
        if not url or "default.jpg" in url:
            return ""
        url = self.getFullIconUrl(url, currUrl)
        return re.sub(r'(/kepek/[^/?#]+_poster)\.(?:jpe?g|png)$', r'\1.webp', url)

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year:
            return "%s (%s)" % (title, year)
        return title

    @staticmethod
    def _episodeTitle(sTitle, season, episode):
        if IsMediaNamingNormalized():
            return "%s - %s" % (sTitle, formatSxxExx(season, episode))
        # the site's own wording ("4. évad", "9. rész")
        return "%s %s. évad %s. rész" % (sTitle, season, episode)

    ###################################################
    # lists
    ###################################################
    def listCategories(self, cItem):
        printDBG("Dmdamedia.listCategories")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'class="cat-grid"', "</div>", False)[1]
        seen = set()
        for url, title in re.findall(r'href="(/kategoria/[^"]+)"[^>]*>(.*?)</a>', data, re.DOTALL):
            url = self.getFullUrl(url)
            title = self.cleanHtmlStr(title)
            if url in seen or not title:
                continue
            seen.add(url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url, "kind": "mixed"})
            self.addDir(params)

    def _isMovieCard(self, kind, url, cls, badge):
        if kind in ("movie", "series"):
            return kind == "movie"
        classes = cls.split()
        if "film" in classes or badge == "film":
            return True
        if "sorozat" in classes or badge == "sorozat":
            return False
        return url.endswith("_film")

    def _addCards(self, cItem, data, currUrl):
        kind = cItem.get("kind", "mixed")
        cnt = 0
        seen = set()
        for href, cls, cardTitle, body in re.findall(r'<a href="([^"]+)" class="movie-card([^"]*)" title="([^"]*)">(.*?)</a>', data, re.DOTALL):
            url = self.getFullUrl(href, currUrl).split("#", 1)[0]
            if not self.cm.isValidUrl(url) or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="card-title">([^<]+)<')[0]) or self.cleanHtmlStr(cardTitle)
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(body, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(body, r'src="([^"]+)"')[0]
            icon = self._posterUrl(icon, currUrl)
            year = self.cm.ph.getSearchGroups(body, r'class="card-year">\s*(\d{4})')[0]
            rating = self.cm.ph.getSearchGroups(body, r'badge-imdb">\s*([0-9.]+)')[0]
            badge = self.cm.ph.getSearchGroups(body, r'badge-type">([^<]+)<')[0].strip().lower()
            desc = []
            if year:
                desc.append(year)
            if rating:
                desc.append("IMDb %s" % rating)
            params = stripPagerKeys(dict(cItem), LIST_STATE_KEYS)
            params.update({"good_for_fav": True, "url": url, "icon": icon, "desc": " | ".join(desc)})
            epMatch = EPISODE_RE.search(url)
            if epMatch:
                slug, season, episode = epMatch.groups()
                params.update({"category": "dm_episode", "title": self._episodeTitle(title, season, episode), "s_title": title,
                               "slug": slug, "season": season, "episode": episode,
                               "meta_type": "tv", "meta_title": title, "meta_year": ""})
                self.addVideo(params)
            elif self._isMovieCard(kind, url, cls, badge):
                params.update({"category": "dm_movie", "title": self._movieTitle(title, year), "s_title": title,
                               "meta_type": "movie", "meta_title": title, "meta_year": year})
                self.addVideo(params)
            else:
                params.update({"category": "dm_series", "title": title, "s_title": title,
                               "meta_type": "tv", "meta_title": title, "meta_year": year})
                self.addDir(params)
            cnt += 1
        return cnt

    def listItems(self, cItem):
        # pager links are "/filmek/legnezettebb/oldal/N" or "?kategoria=..&oldal=N": the "next" link of
        # page 1 gives the url template of every page (kept as page_tpl)
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        pageTpl = cItem.get("page_tpl", "")
        url = pageTpl.format(page=page) if pageTpl and page > 1 else baseUrl
        printDBG("Dmdamedia.listItems |%s|" % url)
        postData = None
        if cItem.get("search_pattern"):
            postData = {"search": cItem["search_pattern"]}
        sts, data = self.getPage(url, None, postData)
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'<a class="oldal" href="([^"]+)" title="Következő"')[0]
        pos = data.find('class="lapozo"')
        pager = data[pos:] if pos > 0 else ""
        if pos > 0:
            data = data[:pos]
        cnt = self._addCards(cItem, data, url)
        if not cnt or postData:
            return
        if nextPage and not pageTpl:
            nextUrl = self.getFullUrl(nextPage.replace("&amp;", "&"), url)
            if re.search(r"oldal[/=]%d(?:$|[&#])" % (page + 1), nextUrl):
                pageTpl = re.sub(r"(oldal[/=])%d(?=$|[&#])" % (page + 1), r"\g<1>{page}", nextUrl.replace("{", "%7B").replace("}", "%7D"))
        if not pageTpl:
            return
        lastPage = max([int(n) for n in re.findall(r'class="oldal" href="[^"]*oldal[/=](\d+)', pager)] + [page])
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl, "page_tpl": pageTpl})
        addPagingItems(self, listItem, page, bool(nextPage), lastPage, pageTpl)

    def listSeasons(self, cItem):
        printDBG("Dmdamedia.listSeasons |%s|" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        info = self._parseTitlePage(data)
        seasons = []
        slug = ""
        for snum, slug in re.findall(r"loadSeason\((\d+),\s*'([^']+)'", data):
            if snum not in seasons:
                seasons.append(snum)
        if not slug:
            slug = cItem["url"].rstrip("/").rsplit("/", 1)[-1]
        if not seasons:
            # no season picker: take the episode links of the page itself
            seasons = sorted(set(re.findall(r'/%s/(\d+)\.evad/\d+\.resz' % re.escape(slug), data)), key=int)
        sTitle = cItem.get("s_title", cItem["title"])
        for snum in seasons:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "dm_season", "title": "%s - %s %s" % (sTitle, _("Season"), snum),
                           "s_title": sTitle, "slug": slug, "season": snum, "url": "%s/%s.evad" % (cItem["url"].rstrip("/"), snum),
                           "series_url": cItem["url"], "desc": info["desc"] or cItem.get("desc", ""), "icon": cItem.get("icon", "") or info["poster"]})
            if info["year"] and not params.get("meta_year"):
                params["meta_year"] = info["year"]
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Dmdamedia.listEpisodes |%s| season %s" % (cItem.get("slug", ""), cItem.get("season", "")))
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Referer": cItem.get("series_url", self.MAIN_URL), "X-Requested-With": "XMLHttpRequest"})
        sts, data = self.getPage(self.getFullUrl("epizod_betoltes"), params, {"evad": cItem["season"], "sorozatKod": cItem["slug"]})
        if not sts:
            return
        sTitle = cItem.get("s_title", cItem["title"])
        langLabels = {"sub": _("With subtitles"), "original": _("Original version")}
        seen = set()
        for cls, attrs in re.findall(r'<a class="episode-btn([^"]*)"([^>]*)>', data):
            href = self.cm.ph.getSearchGroups(attrs, r'href="([^"]+)"')[0]
            url = self.getFullUrl(href).split("#", 1)[0]
            epMatch = EPISODE_RE.search(url)
            if not epMatch or url in seen:
                continue
            seen.add(url)
            slug, season, episode = epMatch.groups()
            # the language of the episode (only subtitled / only original so far) goes to the description, not the name
            lang = "sub" if "sub" in cls.split() else ("original" if "original" in cls.split() else "")
            desc = " | ".join([x for x in (langLabels.get(lang, ""), cItem.get("desc", "")) if x])
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "dm_episode", "title": self._episodeTitle(sTitle, season, episode),
                           "s_title": sTitle, "slug": slug, "season": season, "episode": episode, "lang": lang, "url": url, "desc": desc})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Dmdamedia.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"url": self.getFullUrl("search"), "search_pattern": searchPattern, "kind": "mixed"})
        self.listItems(cItem)

    ###################################################
    # title page
    ###################################################
    def _parseTitlePage(self, data):
        info = {"desc": "", "poster": "", "year": "", "imdb": "", "original_title": "", "duration": ""}
        info["desc"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="hero-desc">', "</div>", False)[1])
        if not info["desc"]:
            info["desc"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]+)"')[0])
        info["poster"] = self._posterUrl(self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0])
        info["imdb"] = self.cm.ph.getSearchGroups(data, r'data-title="(tt\d+)"')[0]
        info["original_title"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="hero-original-title">', "</div>", False)[1])
        for badge in re.findall(r'<span class="meta-badge">(.*?)</span>', data, re.DOTALL):
            badge = self.cleanHtmlStr(badge)
            if not info["year"] and re.match(r"^\d{4}$", badge):
                info["year"] = badge
            elif not info["duration"] and re.search(r"\d+\s*(?:perc|p)$", badge):
                info["duration"] = badge
        return info

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Dmdamedia.getLinksForVideo [%s]" % cItem.get("url", ""))
        urltab = []
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        sidecarTxt = self._parseTitlePage(data)["desc"]

        # provider buttons: "?a=<key>#lejatszo"; the active one is already in the page's <iframe>
        providers = []
        activeKey = ""
        for cls, key, label in re.findall(r'<a class="provider-btn([^"]*)" href="\?a=([^"#&]+)[^"]*"[^>]*>(.*?)</a>', data, re.DOTALL):
            label = self.cleanHtmlStr(label) or key
            if key not in [p[0] for p in providers]:
                providers.append((key, label))
            if "aktiv" in cls.split():
                activeKey = key
        if not providers:
            providers = [("", "")]
            activeKey = ""

        seenEmbeds = set()
        for key, label in providers:
            if key == activeKey:
                pageData = data
            else:
                sts, pageData = self.getPage("%s?a=%s" % (pageUrl, key))
                if not sts:
                    continue
            frame = self.cm.ph.getSearchGroups(self.cm.ph.getDataBeetwenMarkers(pageData, 'id="lejatszo"', "</div>", False)[1], r'<iframe[^>]+src="([^"]+)"')[0]
            if not frame:
                frame = self.cm.ph.getSearchGroups(pageData, r'<iframe[^>]+src="([^"]+)"')[0]
            frame = frame.replace("&amp;", "&")
            if frame.startswith("//"):
                frame = "https:" + frame
            if not self.cm.isValidUrl(frame) or frame in seenEmbeds:
                continue
            seenEmbeds.add(frame)
            hostName = self.up.getHostName(frame)
            name = "%s (%s)" % (label, hostName) if label and hostName else (label or hostName)
            urltab.append({"name": name, "url": strwithmeta(frame, {"Referer": self.MAIN_URL}), "need_resolve": 1})

        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        printDBG("Dmdamedia.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Dmdamedia.getArticleContent [%s]" % cItem.get("url", ""))
        mediaType = cItem.get("meta_type", "")
        pageUrl = cItem.get("series_url") or cItem.get("url", "")
        epMatch = EPISODE_RE.search(pageUrl)
        if epMatch:
            # the series page carries the same IMDb id, poster and story
            pageUrl = self.getFullUrl(epMatch.group(1))
        info = {"desc": "", "poster": "", "year": "", "imdb": "", "original_title": "", "duration": ""}
        if self.cm.isValidUrl(pageUrl):
            sts, data = self.getPage(pageUrl)
            if sts:
                info = self._parseTitlePage(data)
        meta = {}
        try:
            if info["imdb"]:
                meta = getMetaByImdbId(mediaType, info["imdb"])
            if not meta:
                meta = getMeta(mediaType, info["original_title"] or cItem.get("meta_title", ""), cItem.get("meta_year", "") or info["year"])
        except Exception:
            printExc()
            meta = {}
        otherInfo = dict(meta.get("info", {}) or {})
        if info["original_title"] and info["original_title"] != cItem.get("s_title", ""):
            otherInfo.setdefault("original_title", info["original_title"])
        if info["year"]:
            otherInfo.setdefault("year", info["year"])
        if info["duration"]:
            otherInfo.setdefault("duration", info["duration"])
        text = meta.get("plot", "") or info["desc"] or cItem.get("desc", "")
        icon = meta.get("poster", "") or info["poster"] or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text,
                 "images": [{"title": "", "url": icon}] if icon else [],
                 "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("meta_type"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Dmdamedia.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_cats":
            self.listCategories(self.currItem)
        elif category == "dm_series":
            self.listSeasons(self.currItem)
        elif category == "dm_season":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Dmdamedia(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("dmdamedia")

    def withArticleContent(self, cItem):
        return bool(cItem.get("meta_type"))
