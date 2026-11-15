# -*- coding: utf-8 -*-
LAST_MODIFIED = "15.11.2026"
# 15.11.2026 - new host: filmovi.me "Filmovizija" (Serbian/Croatian subtitles; Cloudflare check -> MyE2i)
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMetaByImdbId, getItemMeta, metaArticle
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized


def GetConfigList():
    return []


def gettytul():
    return "https://www.filmovi.me/"


class FilmoviMe(GenericFolderWatchedScraperMixin, CBaseHostClass):
    USE_CF_PROTECTION = True
    # what a favourite needs to open the row again - nothing list/page specific
    FAV_FIELDS = ("name", "category", "type", "title", "url", "icon", "desc", "s_title", "season", "episode",
                  "meta_type", "meta_title", "meta_year", "meta_season", "meta_episode", "good_for_fav")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "filmovime", "cookie": "filmovime.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        # no DEFAULT_ICON_URL: the site's logo sits behind the Cloudflare check (base class default icon);
        # the covers come from m.media-amazon.com
        # the site sorts every list itself; series are listed episode by episode ("Show S03E04 (2026)")
        self.MENU = [
            {"category": "list_items", "title": _("Latest added"), "url": self.MAIN_URL},
            {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("popularni")},
            {"category": "list_items", "title": _("Random"), "url": self.getFullUrl("nasumicni")},
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("filmovi")},
            {"category": "list_items", "title": _("Latest episodes"), "url": self.getFullUrl("serije")},
            {"category": "list_items", "title": _("Cartoons"), "url": self.getFullUrl("crtani")},
            {"category": "list_items", "title": "IMDb filmovi", "url": self.getFullUrl("imdb")},
            {"category": "list_filters", "title": _("Genres"), "filter": "zanr"},
            {"category": "list_filters", "title": _("Year"), "filter": "godina"},
        ] + self.searchItems()
        self.filtersCache = {}
        self.pageCache = {}
        self.watchedHelper = IPTVWatchedHelper("filmovime")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        return self.wfCategoryKey(cItem, lambda url: url if url.startswith(self.MAIN_URL) else "", ("fm_video",), ())

    ###################################################
    # helpers
    ###################################################
    def _getCachedPage(self, url):
        data = self.pageCache.get(url)
        if data is not None:
            return True, data
        sts, data = self.getPage(url)
        if not sts or not data:
            return False, ""
        if len(self.pageCache) > 20:
            self.pageCache = {}
        self.pageCache[url] = data
        return True, data

    ###################################################
    # lists
    ###################################################
    def listFilters(self, cItem):
        flt = cItem.get("filter", "")
        if not self.filtersCache:
            sts, data = self.getPage(self.MAIN_URL)
            if not sts:
                return
            for key in ("zanr", "godina"):
                tab = []
                seen = set()
                for url, title in re.findall(r'href="((?:https?://[^"/]+)?/%s/[^"]+)"[^>]*>(.*?)</a>' % key, data, re.S):
                    url = self.getFullUrl(url)
                    title = self.cleanHtmlStr(title)
                    if url in seen or title == "":
                        continue
                    seen.add(url)
                    tab.append({"title": title, "url": url})
                tab.sort(key=lambda item: item["title"].lower(), reverse=(key == "godina"))
                self.filtersCache[key] = tab
        for item in self.filtersCache.get(flt, []):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": item["title"], "url": item["url"]})
            params.pop("filter", None)
            self.addDir(params)

    def _listCards(self, cItem, data):
        normalize = IsMediaNamingNormalized()
        seen = set()
        # the pager and the footer (year links) follow the last card
        data = re.split(r'<nav>|<footer', data, maxsplit=1)[0]
        for item in re.split(r'<div class="col-6 col-md-4 col-xl-2', data)[1:]:
            # internal links only - the first tile is the site's Telegram group
            url = self.cm.ph.getSearchGroups(item, r'<div class="slika">\s*<a href="(/[^"]+)"')[0]
            if url == "":
                continue
            url = self.getFullUrl(url)
            if url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<img[^>]+alt="([^"]+)"')[0])
            if label == "":
                label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h2[^>]*>(.*?)</h2>')[0])
            year = self.cm.ph.getSearchGroups(label, r'\((\d{4})\)\s*$')[0] or self.cm.ph.getSearchGroups(item, r'/godina/(\d{4})')[0]
            base = re.sub(r'\s*\(\d{4}\)\s*$', '', label).strip()
            if base == "":
                continue
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+?(?:data-src|src)="((?!data:)[^"]+)"')[0]
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="ocena[^"]*"[^>]*>(.*?)</span>')[0])
            params = stripPagerKeys(dict(cItem), ("base_url",))
            # "The Lord of the Rings: The Rings of Power S03E04" - an episode row
            ep = re.search(r'^(.*?)\s+S(\d+)E(\d+)$', base, re.I)
            if ep:
                sTitle, season, episode = ep.group(1).strip(), str(int(ep.group(2))), str(int(ep.group(3)))
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode)) if normalize else label
                # the row's year is the episode's, not the show's first year - no meta_year for the show lookup
                params.update({"s_title": sTitle, "season": season, "episode": episode, "meta_type": "tv", "meta_title": sTitle,
                               "meta_season": season, "meta_episode": episode})
                desc = _("Episode")
            else:
                title = "%s (%s)" % (base, year) if (normalize and year) else label
                params.update({"meta_type": "movie", "meta_title": re.split(r'\s+aka\s+', base, maxsplit=1, flags=re.I)[0]})
                desc = _("Movie")
            if year:
                desc += " | %s" % year
            if re.match(r'^\d+(?:\.\d+)?$', rating):  # "N/A" on new titles, the episode code on episode cards
                desc += " | IMDb %s" % rating
            params.update({"good_for_fav": True, "category": "fm_video", "title": title, "url": url,
                           "icon": self.getFullIconUrl(icon), "desc": desc, "meta_year": "" if ep else year})
            self.addVideo(params)

    def listItems(self, cItem):
        # paging: <url>?page=N (also on the search url)
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or re.sub(r"[?&]page=\d+$", "", cItem["url"])
        pageUrlTpl = baseUrl + ("&" if "?" in baseUrl else "?") + "page={page}"
        url = baseUrl if page <= 1 else pageUrlTpl.format(page=page)
        printDBG("FilmoviMe.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        self._listCards(cItem, data)
        lastPage = max([int(n) for n in re.findall(r'class="page-link" href="[^"]*[?&]page=(\d+)"', data)] + [page])
        hasNext = bool(re.search(r'<a class="page-link" href="[^"]*[?&]page=%d"' % (page + 1), data))
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext and bool(self.currList), lastPage, pageUrlTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmoviMe.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("pretraga?pretraga=%s" % urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _pageDesc(self, data):
        # <h1 ...>Title <small>online sa prevodom</small></h1> <hr> <div class="text-muted"><p>plot</p></div>
        m = re.search(r'</h1>\s*<hr>\s*<div class="text-muted">(.*?)</div>', data, re.S)
        return self.cleanHtmlStr(m.group(1)) if m else ""

    def getLinksForVideo(self, cItem):
        printDBG("FilmoviMe.getLinksForVideo [%s]" % cItem.get("url"))
        sts, data = self._getCachedPage(cItem.get("url", ""))
        if not sts:
            return []
        player = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "embed-responsive"), ("</div", ">"), False)[1] or data
        urltab = []
        unsupported = []
        for url in re.findall(r'<iframe[^>]+src="([^"]+)"', player):
            url = url.replace("&amp;", "&")
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url) or re.search(r'youtube|facebook\.com', url):
                continue
            host = self.up.getHostName(url)
            if self.up.checkHostSupport(url) != 1:
                printDBG("FilmoviMe: hoster not supported [%s]" % url)
                if host not in unsupported:
                    unsupported.append(host)
                continue
            urltab.append({"name": "%d. %s" % (len(urltab) + 1, host), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            if unsupported:
                SetIPTVPlayerLastHostError(_("Only unsupported hosters available: %s") % ", ".join(unsupported))
            else:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        imdbId = self.cm.ph.getSearchGroups(player, r'imdb=(tt\d+)')[0]
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", ""), cItem.get("meta_title", ""), cItem.get("meta_year", ""), imdbId, skip=(),
                                     season=cItem.get("meta_season", ""), episode=cItem.get("meta_episode", ""))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self._pageDesc(data) or cItem.get("desc", ""), metaQuery=metaQuery))

    ###################################################
    # favourites / INFO
    ###################################################
    def getFavouriteData(self, cItem):
        if cItem.get("good_for_fav"):
            return self.getFavouriteFieldsData(cItem)
        return CBaseHostClass.getFavouriteData(self, cItem)

    def getArticleContent(self, cItem):
        printDBG("FilmoviMe.getArticleContent [%s]" % cItem.get("url"))
        text = ""
        icon = cItem.get("icon", "")
        other = {}
        imdbId = ""
        mediaType = cItem.get("meta_type", "")
        sts, data = self._getCachedPage(cItem.get("url", ""))
        if sts:
            text = self._pageDesc(data)
            imdbId = self.cm.ph.getSearchGroups(data, r'imdb=(tt\d+)')[0]
            # <div class="informacije"> Režiser: ...<br><br> Glumci: ...<br><br> Datum izlaska: ...<br><br> Ocena: 7.9/10<br>
            info = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "informacije"), ("</div", ">"), False)[1]
            icon = icon or self.cm.ph.getSearchGroups(info, r'<img[^>]+src="([^"]+)"')[0]
            # the moviemeta keys (directors / cast): a meta answer replaces the site's line instead of adding a second one
            for key, label in (("directors", "Režiser"), ("cast", "Glumci"), ("released", "Datum izlaska"), ("imdb_rating", "Ocena")):
                value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(info, r'%s:\s*([^<]+)' % label)[0])
                if value and not value.upper().startswith("N/A"):
                    other[key] = value
        meta = {}
        if imdbId and mediaType in ("movie", "tv"):
            try:
                meta = getMetaByImdbId(mediaType, imdbId)
            except Exception:
                printExc()
        return metaArticle(cItem, meta or getItemMeta(cItem), story=text, poster=icon, info=other)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("FilmoviMe.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_filters":
            self.listFilters(self.currItem)
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
        CHostBase.__init__(self, FilmoviMe(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("filmovime")

    def withArticleContent(self, cItem):
        return cItem.get("meta_type", "") in ("movie", "tv")
