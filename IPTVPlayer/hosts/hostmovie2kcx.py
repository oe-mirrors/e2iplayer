# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# 07.10.2026 - First/Jump/Next paging (last page from the pager); "Title (Year)" / "Show - SxxExx";
#   episodes keyed on their own url (season page + "#<episode id>"); watched flag (series -> season ->
#   episode), favourites, sidecar, downloaded marker; INFO via moviemeta (the IMDb id is base64 inside
#   the page slug: /stream/<name>-<year>-<b64 "tt0470055-...">) merged with the site's fields;
#   no crash on an empty/changed page; the JS template "loadMirror\('(...)'" is no link any more.
import base64
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://movie2k.cx/"


def _b64Imdb(text):
    # "dHQwNDcwMDU1LWU1ZWJjYz" -> "tt0470055-e5ebcc" -> "tt0470055" (page slugs and episode ids)
    try:
        raw = base64.b64decode(text + "=" * (-len(text) % 4)).decode("utf-8", "ignore")
    except Exception:
        return ""
    m = re.match(r"(tt\d+)", raw)
    return m.group(1) if m else ""


def _imdbFromUrl(url):
    m = re.search(r"/stream/[^?#]*-(dHQ[A-Za-z0-9_-]+)", url or "")
    return _b64Imdb(m.group(1)) if m else ""


def _pageUrl(url):
    return (url or "").split("#")[0]


class Movie2kcx(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Movie2kcx", "cookie": "Movie2kcx.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "img/logo.png"
        self.MENU = [{"category": "list_items", "title": _("Cinema movies"), "url": gettytul()},
                     {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies")},
                     {"category": "list_value", "title": _("Movies genres"), "url": self.getFullUrl("genres")},
                     {"category": "list_items", "title": _("Top series"), "url": self.getFullUrl("tv")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("tv/all")},
                     {"category": "list_value", "title": _("Series genres"), "url": self.getFullUrl("tv/genres")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("movie2kcx")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        baseUrl = _pageUrl(baseUrl).replace("%C3%B6", "ö").replace("%20%26%20", " & ")
        baseUrl = urllib_quote(baseUrl, safe="/:@$&'()*+,;=?[]!")
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if not url:
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            category = cItem.get("category", "")
            if category == "list_seasons":
                return "series:%s" % url
            if category == "list_episodes":
                return "season:%s" % url
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("Movie2kcx.listItems |%s|" % cItem)
        page = int(cItem.get("page", 1) or 1)
        url = cItem["url"]
        sts, htm = self.getPage("%s%spage=%s" % (url, "&" if "?" in url else "?", str(page)))
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'id="maincontent', '<div id="maincontent2">') or self.cm.ph.getAllItemsBeetwenMarkers(htm, 'id="maincontent', "</html>")
        normalize = IsMediaNamingNormalized()
        count = 0
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data[0].replace("amp;", ""), "<tr>", 'id="xline">') if data else []:
            itemUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)')[0])
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, 'img src="([^"]+)')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, 'alt="([^"]+)')[0])
            if not title or not self.cm.isValidUrl(itemUrl):
                continue
            year = self.cm.ph.getSearchGroups(item, r"\|\s*((?:19|20)\d{2})\s*&nbsp;")[0] or self.cm.ph.getSearchGroups(itemUrl, r"-((?:19|20)\d{2})-dHQ")[0]
            desc = self.cm.ph.getAllItemsBeetwenMarkers(item, 'class="info">', "</div>")
            desc = self.cleanHtmlStr(desc[0]).replace('class="info">', "") if desc else ""
            line = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="beschreibung"[^>]*>(.*?)</div>')[0]).replace(" Info", "")
            desc = "\n".join(x for x in (line, desc) if x.strip())
            isSeries = "type=tv" in itemUrl or "type=series" in itemUrl
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "url": itemUrl, "icon": icon, "desc": desc, "s_title": title, "meta_title": title, "meta_year": year,
                           "meta_type": "tv" if isSeries else "movie"})
            if isSeries:
                params.update({"category": "list_seasons", "title": title})
                self.addDir(params)
            else:
                params.update({"category": "video", "title": "%s (%s)" % (title, year) if (normalize and year) else title})
                self.addVideo(params)
            count += 1
        pages = [int(x) for x in re.findall(r"[?&]page=(\d+)", htm)]
        lastPage = max(pages) if pages else 0
        hasNext = bool(count) and (page < lastPage or "chste &raquo;</a>" in htm)
        # the page lives in cItem["page"]; the template keeps the list url unchanged
        addPagingItems(self, cItem, page, hasNext, lastPage if lastPage > page or not hasNext else 0, url.replace("{", "{{").replace("}", "}}"))

    def listSeasons(self, cItem):
        printDBG("Movie2kcx.listSeasons")
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(htm, """description" content="([^"]+)""")[0])
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'id="season-select"', "</select>")
        seasons = re.findall(r'<option value="(\d+)"', data[0]) if data else []
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        show = cItem.get("s_title", "") or cItem["title"]
        base = re.sub(r"&season=\d+", "", cItem["url"])
        for sn in seasons:
            seasonTag = formatSxxExx(int(sn)) if IsMediaNamingNormalized() else "%s %s" % (_("Season"), sn)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (show, seasonTag), "url": "%s&season=%s" % (base, sn),
                           "desc": desc, "s_num": int(sn), "s_title": show})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Movie2kcx.listEpisodes")
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'id="episode-select"', "</select>")
        episodes = re.findall(r'value="([^"]+)" data-name="([^"]*)" data-overview="([^"]*)">([^<]+)', data[0]) if data else []
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem["title"]
        season = int(cItem.get("s_num", 0) or self.cm.ph.getSearchGroups(cItem["url"], r"season=(\d+)")[0] or 1)
        for value, name, overview, label in episodes:
            label = self.cleanHtmlStr(label)
            epNum = self.cm.ph.getSearchGroups(label, r"^E(\d+)")[0]
            if normalize and epNum:
                title = "%s - %s" % (show, formatSxxExx(season, int(epNum)))
            else:
                title = "%s - %s" % (show, label)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "video", "title": title, "url": "%s#%s" % (_pageUrl(cItem["url"]), value),
                           "desc": self.cleanHtmlStr(overview) or cItem.get("desc", ""), "ep_desc": self.cleanHtmlStr(overview), "ep": value, "meta_type": "tv"})
            self.addVideo(params)

    def listValue(self, cItem):
        printDBG("Movie2kcx.listValue")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, 'id="genres', "</html>")
        for url, title, count in re.findall(r'href="([^"]+).*?name">([^<]+).*?count">(\d+)', data[0].replace("amp;", ""), re.DOTALL) if data else []:
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "list_items", "title": "%s (%s)" % (self.cleanHtmlStr(title), count), "url": self.getFullUrl(url)})
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Movie2kcx.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = "%ssearch?q=%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern))
        # the pager rows open as an ordinary list
        self.listItems(dict(cItem, category="list_items", url=url))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Movie2kcx.getLinksForVideo [%s]" % cItem)
        urltab = []
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return []
        if cItem.get("ep"):
            block = self.cm.ph.getAllItemsBeetwenMarkers(htm, 'data-episode-id="%s' % cItem["ep"], "</td>")
            htm = block[0] if block else ""
        for url in re.findall(r"loadMirror\('(https?://[^']+)", htm):
            if url in [str(x["url"]) for x in urltab]:
                continue
            urltab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, {"Referer": gettytul()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("ep_desc", "") or cItem.get("desc", "")))

    def getVideoLinks(self, url):
        printDBG("Movie2kcx.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecarFromUrlMeta(url, IsSidecarEnabled()))
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Movie2kcx.getArticleContent [%s]" % cItem)
        url = cItem.get("url", "")
        mediaType = cItem.get("meta_type", "") or ("tv" if "type=tv" in url else "movie")
        imdb = _imdbFromUrl(url)
        info, story = {}, ""
        sts, data = self.getPage(url)
        if sts:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, """<meta name="description" content="([^"]+)""")[0])
            # "<title> online Film anschauen. <plot>... <title> runterladen und kostenlos bei movie2k.cx angucken"
            story = re.sub(r"^.*?(?:anschauen|ansehen)\.\s*", "", story)
            story = re.sub(r"\s*\S.*?runterladen und kostenlos bei movie2k\.cx angucken\s*$", "", story)
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and cItem.get("meta_title"):
                meta = getMeta(mediaType, cItem["meta_title"], cItem.get("meta_year", ""))
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        if cItem.get("meta_year") and "year" not in info:
            info["year"] = cItem["meta_year"]
        plot = meta.get("plot", "")
        text = cItem.get("ep_desc", "") or plot or story or cItem.get("desc", "")
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

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
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_value":
            self.listValue(self.currItem)
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
        CHostBase.__init__(self, Movie2kcx(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("movie2kcx")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
