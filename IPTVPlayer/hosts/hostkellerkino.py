# -*- coding: utf-8 -*-
LAST_MODIFIED = "21.10.2026"
# 21.10.2026 - new host
#   films only (WordPress): Cinema movies / Neuerscheinungen / Topics from the start page, Latest added,
#   Top rated, genres and A-Z (First / Jump / Next page), search through the WordPress REST API (the /?s=
#   page is behind a Cloudflare challenge; posters from the attachments of the posts)
#   streams: the player tabs of the film page hold the hoster iframes, plus the YouTube trailer
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://www.kellerkino.com/"


SEARCH_PAGE_SIZE = 40
# film page "Filminfos" rows -> INFO keys
INFO_FIELDS = {"jahr:": "year", "laufzeit:": "duration", "imdb-bewertung:": "imdb_rating", "genre:": "genres", "regie:": "director", "schauspieler:": "actors"}


class KellerKino(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "kellerkino", "cookie": "kellerkino.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.MENU = [{"category": "list_home", "title": _("Cinema movies"), "url": self.MAIN_URL, "section": "cinema"},
                     {"category": "list_home", "title": "Neuerscheinungen", "url": self.MAIN_URL, "section": "new"},
                     {"category": "list_items", "title": _("Latest added"), "url": self.getFullUrl("/archiv/?sort=newest")},
                     {"category": "list_items", "title": _("Top rated"), "url": self.getFullUrl("/imdb-rating/?sort=imdb")},
                     {"category": "list_topics", "title": _("Topics"), "url": self.MAIN_URL},
                     {"category": "list_genres", "title": _("Genres"), "url": self.getFullUrl("/kategorien/")},
                     {"category": "list_az", "title": _("A-Z"), "url": self.getFullUrl("/filme-a-z/")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("kellerkino")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _getJson(self, url):
        sts, data = self.getPage(url)
        if not sts:
            return None
        try:
            return json.loads(data)
        except Exception:
            printExc()
        return None

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("category", "") != "video":
                return ""
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            return "video:%s" % url if url else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def _addMovie(self, url, title, icon, year="", runtime="", rating="", desc=""):
        title = self.cleanHtmlStr(title)
        if not url or not title:
            return False
        descLine = " | ".join(x for x in (year, "%s Min" % runtime if runtime else "", "IMDb %s" % rating if rating else "") if x)
        if descLine:
            desc = "%s[/br]%s" % (descLine, desc) if desc else descLine
        label = "%s (%s)" % (title, year) if (year and IsMediaNamingNormalized()) else title
        self.addVideo({"name": "category", "category": "video", "good_for_fav": True, "url": self.getFullUrl(url), "title": label,
                       "icon": self.getFullIconUrl(icon), "desc": desc, "meta_type": "movie", "meta_title": title, "meta_year": year})
        return True

    def _meta(self, html):
        # "<span>1973</span> <span>91 Min</span> <span>IMDb 5.8</span>"
        spans = [self.cleanHtmlStr(s) for s in re.findall(r"<span>([^<]*)</span>", html)]
        year = ([s for s in spans if re.match(r"^\d{4}$", s)] or [""])[0]
        runtime = ([s.split()[0] for s in spans if re.match(r"^\d+ Min$", s)] or [""])[0]
        rating = ([s[5:] for s in spans if re.match(r"^IMDb [\d.]+$", s)] or [""])[0]
        return year, runtime, rating

    def _addCards(self, data):
        count = 0
        for item in re.findall(r'(?s)<article class="movie-card[^"]*">(.*?)</article>', data):
            url, title = self.cm.ph.getSearchGroups(item, r'<h2><a href="([^"]+)">(.*?)</a>', 2)
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            year, runtime, rating = self._meta(self.cm.ph.getDataBeetwenMarkers(item, 'class="movie-meta-small"', "</div>", False)[1])
            if self._addMovie(url, title, icon, year, runtime, rating):
                count += 1
        return count

    def listHome(self, cItem):
        printDBG("KellerKino.listHome |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        kinds = ("focus", "secondary") if cItem.get("section") == "cinema" else ("more-card",)
        for kind, url, item in re.findall(r'(?s)<a class="dmt-home-cinema-([a-z-]+)" href="([^"]+)">(.*?)</a>', data):
            if kind not in kinds:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'srcset="([^"\s]+)')[0]
            title = self.cm.ph.getSearchGroups(item, r"<strong>(.*?)</strong>")[0]
            year, runtime, rating = self._meta(item)
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="dmt-home-cinema-overview">(.*?)</span>')[0])
            self._addMovie(url, title, icon, year, runtime, rating, desc)

    def listTopics(self, cItem):
        printDBG("KellerKino.listTopics")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for key, title in re.findall(r'data-dmt-home-theme-tab="([^"]+)"[^>]*>([^<]+)<', data):
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_topic", "title": self.cleanHtmlStr(title), "url": cItem["url"], "topic": key})

    def listTopic(self, cItem):
        printDBG("KellerKino.listTopic |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        marker = 'id="dmt-home-theme-panel-%s"' % cItem.get("topic", "")
        if marker in data:
            self._addCards(re.split(r'id="dmt-home-theme-panel-|</section>', data.split(marker, 1)[1], 1)[0])

    def listGenres(self, cItem):
        printDBG("KellerKino.listGenres")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for item in re.findall(r'(?s)<div class="category-card">(.*?)</span>\s*</div>', data):
            url, title = self.cm.ph.getSearchGroups(item, r'class="category-card-name" href="([^"]+)"[^>]*>(.*?)</a>', 2)
            title = self.cleanHtmlStr(title)
            if not url or not title:
                continue
            count = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="category-card-count">([^<]+)<')[0])
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url.rstrip("/") + "/?sort=newest"),
                         "icon": self.getFullIconUrl(icon), "desc": count})

    def listAZ(self, cItem):
        printDBG("KellerKino.listAZ")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for url, letter, count in re.findall(r'(?s)class="dmt-az-letter-link[^"]*"\s+href="([^"]+)"[^>]*>\s*<span class="dmt-az-letter-main">([^<]+)</span>\s*<span class="dmt-az-letter-count">([^<]*)</span>', data):
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(letter), "url": self.getFullUrl(url.replace("&amp;", "&").replace("&#038;", "&")),
                         "desc": self.cleanHtmlStr(count)})

    def _pageUrl(self, url, page):
        # /archiv/seite/<n>/?sort=newest, /filme-a-z/?dmt_letter=a&az_page=<n>
        if "dmt_letter=" in url:
            url = re.sub(r"&az_page=\d+", "", url)
            return "%s&az_page=%s" % (url, page) if page != 1 else url
        path, sep, query = url.partition("?")
        path = re.sub(r"seite/\d+/?$", "", path)
        if not path.endswith("/"):
            path += "/"
        if page != 1:
            path += "seite/%s/" % page
        return path + sep + query

    def listItems(self, cItem):
        printDBG("KellerKino.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        baseUrl = cItem.get("base_url") or cItem["url"]
        sts, data = self.getPage(self._pageUrl(baseUrl, page))
        if not sts:
            return
        count = self._addCards(data)
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination"', "</div>", False)[1]
        if not pager:
            pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="page-numbers', "</nav>", True)[1]
        pages = [int(p) for p in re.findall(r'class="page-numbers[^"]*"[^>]*>(\d+)<', pager)]
        lastPage = max(pages) if pages else 0
        hasNext = bool(count) and 'class="next page-numbers"' in pager
        nextItem = dict(cItem)
        nextItem["base_url"] = baseUrl
        addPagingItems(self, nextItem, page, hasNext, lastPage, self._pageUrl(baseUrl, 987654).replace("987654", "{page}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KellerKino.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        query = urllib_quote_plus(searchPattern.strip())
        posts = self._getJson(self.getFullUrl("/wp-json/wp/v2/posts?search=%s&per_page=%d&page=%d&_fields=id,link,title,excerpt" % (query, SEARCH_PAGE_SIZE, page)))
        if not isinstance(posts, list) or not posts:
            return
        # the poster is the first picture uploaded to the post (the second one is the backdrop)
        icons = {}
        ids = ",".join(str(p.get("id", "")) for p in posts if p.get("id"))
        media = self._getJson(self.getFullUrl("/wp-json/wp/v2/media?parent=%s&per_page=100&orderby=id&order=asc&_fields=post,source_url" % ids)) if ids else None
        for item in media if isinstance(media, list) else []:
            icons.setdefault(item.get("post"), ensure_str(item.get("source_url") or ""))
        for post in posts:
            title = ensure_str((post.get("title") or {}).get("rendered", ""))
            desc = self.cleanHtmlStr(ensure_str((post.get("excerpt") or {}).get("rendered", "")))
            self._addMovie(ensure_str(post.get("link") or ""), title, icons.get(post.get("id"), ""), desc=desc)
        if len(posts) >= SEARCH_PAGE_SIZE:
            nextItem = dict(cItem)
            nextItem.update({"category": "search_next_page", "page": page + 1})
            addPagingItems(self, nextItem, page, True)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("KellerKino.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab = []
        for key, label, item in re.findall(r'(?s)data-nfo-player-panel="([^"]+)"\s+data-nfo-player-label="([^"]+)"(.*?)</template>', data):
            src = self.cm.ph.getSearchGroups(item, r'<iframe[^>]+src="([^"]+)"')[0].replace("&amp;", "&")
            if not self.cm.isValidUrl(src):
                continue
            if key == "voe" and self.up.checkHostSupport(src) != 1:
                # VOE plays its films on ever new domains; voe.sx takes the same file id
                src = re.sub(r"^https?://[^/]+/", "https://voe.sx/", src)
            urltab.append({"name": self.cleanHtmlStr(label), "url": strwithmeta(src, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        trailer = self.cm.ph.getSearchGroups(data, r'class="[^"]*nfo-movie-trailer-link[^"]*" href="([^"]+)"')[0]
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        if self.cm.isValidUrl(trailer):
            urltab.append({"name": _("Trailer"), "url": trailer, "need_resolve": 1})
        sidecarTxt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="movie-description">\s*<h2>[^<]*</h2>(.*?)</section>')[0]) or cItem.get("desc", "")
        year = cItem.get("meta_year", "") or self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)info-row-jahr.*?class="info-value">(.*?)</dd>')[0])
        metaQuery = sidecarMetaQuery("movie", cItem.get("meta_title", ""), year, skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt, metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("KellerKino.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("KellerKino.getArticleContent [%s]" % cItem)
        info = {}
        desc = ""
        imdb = ""
        icon = cItem.get("icon", "")
        year = cItem.get("meta_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="movie-description">\s*<h2>[^<]*</h2>(.*?)</section>')[0])
            imdb = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
            icon = icon or self.cm.ph.getSearchGroups(data, r'(?s)class="poster-box">\s*<img src="([^"]+)"')[0]
            for label, value in re.findall(r'(?s)<dt class="info-label">(.*?)</dt>\s*<dd class="info-value">(.*?)</dd>', data):
                key = INFO_FIELDS.get(self.cleanHtmlStr(label).lower(), "")
                # the genres and the director are there twice: linked and as plain text
                value = self.cleanHtmlStr(re.sub(r'(?s)<span class="nfo-info-plain-responsive">.*?</span>', "", value))
                if key and value:
                    info[key] = value
            year = year or info.get("year", "")
            release = self.cm.ph.getSearchGroups(data, r'data-nfo-release-title="([^"]+)"')[0]
            if release:
                info["quality"] = self.cleanHtmlStr(release)
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId("movie", imdb)
            if not meta and cItem.get("meta_title"):
                meta = getMeta("movie", cItem["meta_title"], year)
        except Exception:
            printExc()
        meta = meta or {}
        info.update(meta.get("info", {}))
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in info:
                info.pop(siteKey, None)
        plot = meta.get("plot", "")
        text = desc or cItem.get("desc", "")
        if plot and text and plot != text:
            text = "%s[/br][/br]%s" % (text, plot)
        else:
            text = text or plot
        icon = icon or meta.get("poster", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_home":
            self.listHome(self.currItem)
        elif category == "list_topics":
            self.listTopics(self.currItem)
        elif category == "list_topic":
            self.listTopic(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_az":
            self.listAZ(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
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
        CHostBase.__init__(self, KellerKino(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("kellerkino")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "video"
