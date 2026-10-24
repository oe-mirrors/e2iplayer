# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host: Filmo (German films; own domain in the settings). A provider chip of the film page is
#   opened in two steps: POST /n with the page's CSRF token -> {"x": token}, GET /n/<token> -> redirect to the
#   hoster (VOE, Byse) -> urlparser. The language of a link comes from the flag row it sits in.
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.filmo_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.filmo_alt_domain)]


def gettytul():
    return "https://filmo.to/"


# site paths: urls of an older address (favourites, history) are moved to the current one
SITE_PATH_RE = re.compile(r"^https?://[^/]+/((?:movies|genres|letters|collections|search|popular|n)(?:[/?].*)?)$")
# grid cards (lists) and spotlight cards (search)
CARD_RE = re.compile(r'(?s)<a href="([^"]*/movies/[^"/?#]+)" class="(?:movie-poster-grid-card|popular-spotlight-card__link)[^"]*"[^>]*>(.*?)</a>')
# "Mehr Infos" rows of the film page -> INFO keys
INFO_FIELDS = {"laufzeit": "duration", "bewertung": "rating", "originalsprache": "language", "länder": "country", "genres": "genres",
               "regie": "director", "darsteller": "actors"}


class Filmo(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "filmo", "cookie": "filmo.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.filmo_alt_domain.value.strip()
        if domain and not domain.startswith("http"):
            domain = "https://" + domain
        if not self.setMainUrl(domain if domain.endswith("/") else domain + "/"):
            self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("apple-touch-icon.png")
        self.csrfToken = ""
        self.watchedHelper = IPTVWatchedHelper("filmo")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        baseUrl = self._onMain(baseUrl)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _onMain(self, url):
        match = SITE_PATH_RE.match(url or "")
        return self.getMainUrl() + match.group(1) if match else (url or "")

    @staticmethod
    def _path(url):
        return re.sub(r"^https?://[^/]+", "", url or "").split("#")[0].rstrip("/")

    @staticmethod
    def _icon(url):
        # the site serves its images as WebP by default; JPEG works on every box
        url = (url or "").replace("&amp;", "&")
        return re.sub(r"format=(?:webp|avif)", "format=jpg", url)

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _pageUrl(url, page):
        url = re.sub(r"([?&])page=\d+&?", r"\1", url).rstrip("?&")
        if page <= 1:
            return url
        return "%s%spage=%s" % (url, "&" if "?" in url else "?", page)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("category", "") != "video":
                return ""
            path = self._path(cItem.get("url", ""))
            return "video:%s" % path if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("movies")},
                {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl("collections/explore-popular-movies")},
                {"category": "list_items", "title": _("Top rated"), "url": self.getFullUrl("movies?sort=rating_desc")},
                {"category": "list_collections", "title": _("Collections"), "url": self.getFullUrl("collections")},
                {"category": "list_genres", "title": _("Genres"), "url": self.MAIN_URL},
                {"category": "list_years", "title": _("Year"), "url": self.getFullUrl("movies")},
                {"category": "list_az", "title": _("A-Z"), "url": self.MAIN_URL}]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def _addCards(self, data, year=""):
        # the cards carry no year: "Title (Year)" only in the lists of one year (Year menu), the site's title elsewhere
        count = 0
        seen = set()
        for url, item in CARD_RE.findall(data):
            url = self.getFullUrl(url)
            if url in seen:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)(?:card__title[^"]*"|<h4[^>]*)>(.*?)</(?:div|h4)>')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0])
            if not title:
                continue
            seen.add(url)
            icon = self._icon(self.cm.ph.getSearchGroups(item, r'<img[^>]+?src="([^"]+)"')[0])
            label = "%s (%s)" % (title, year) if (year and IsMediaNamingNormalized()) else title
            self.addVideo({"name": "category", "category": "video", "good_for_fav": True, "url": url, "title": label, "icon": icon, "desc": "",
                           "meta_type": "movie", "meta_title": title, "meta_year": year})
            count += 1
        return count

    def listItems(self, cItem):
        page = self._page(cItem)
        baseUrl = cItem.get("base_url") or cItem["url"]
        printDBG("Filmo.listItems [%s] page %d" % (baseUrl, page))
        sts, data = self.getPage(self._pageUrl(baseUrl, page))
        if not sts:
            return
        count = self._addCards(data, cItem.get("f_year", ""))
        self._addPager(cItem, data, baseUrl, page, count)

    def _addPager(self, cItem, data, baseUrl, page, count):
        # the first pager is the mobile one (back / next only); the desktop one has the last page number
        pager = self.cm.ph.getDataBeetwenMarkers(data, "site-pagination__desktop", "</ul>", False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, 'class="pagination', "</ul>", False)[1]
        nums = [int(n) for n in re.findall(r"[?&]page=(\d+)", pager)]
        lastPage = max(nums + [page]) if nums else 0
        hasNext = bool(count) and (page < lastPage or bool(re.search(r'<a[^>]+rel="next"', data)))
        listItem = stripPagerKeys(dict(cItem))
        listItem.update({"base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, self._pageUrl(baseUrl, 987654).replace("987654", "{page}"))

    def listCollections(self, cItem):
        page = self._page(cItem)
        baseUrl = cItem.get("base_url") or cItem["url"]
        printDBG("Filmo.listCollections page %d" % page)
        sts, data = self.getPage(self._pageUrl(baseUrl, page))
        if not sts:
            return
        count = 0
        for url, item in re.findall(r'(?s)<a class="collection-index-card[^"]*" href="([^"]+)">(.*?)</a>', data):
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)card__title[^"]*">(.*?)</span>')[0])
            if not title:
                continue
            icon = self._icon(self.cm.ph.getSearchGroups(item, r'<img[^>]+?src="([^"]+)"')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)card__meta[^"]*">(.*?)</span>')[0])
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url), "icon": icon, "desc": desc})
            count += 1
        self._addPager(cItem, data, baseUrl, page, count)

    def listGenres(self, cItem):
        printDBG("Filmo.listGenres")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        seen = set()
        for title, url in re.findall(r'<a aria-label="([^"]+)" class="navbarButton[^"]*" href="([^"]*/genres/[^"]+)"', data):
            url = self.getFullUrl(url)
            if url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": url})

    def listYears(self, cItem):
        printDBG("Filmo.listYears")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'name="year"', "</select>", False)[1]
        for year in re.findall(r'<option value="(\d{4})"', block):
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": year, "f_year": year,
                         "url": self.getFullUrl("movies?year=%s" % year)})

    def listAZ(self, cItem):
        printDBG("Filmo.listAZ")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        seen = set()
        for url, title in re.findall(r'<a href="([^"]*/letters/[^"]+)"[^>]*>([^<]+)<', data):
            url = self.getFullUrl(url)
            if url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": url})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Filmo.listSearchResult [%s]" % searchPattern)
        searchPattern = (searchPattern or "").strip()
        if not searchPattern:
            return
        sts, data = self.getPage(self.getFullUrl("search?q=%s" % urllib_quote_plus(searchPattern)))
        if sts:
            self._addCards(data)

    ###################################################
    # links
    ###################################################
    def _chips(self, data):
        # (link id, language code, language name, hoster, tags, data-p) of every provider chip, German rows first
        chips = []
        data = data.split('class="movie-link-report-row', 1)[0]
        for row in data.split('<div class="provider-row">')[1:]:
            code = self.cm.ph.getSearchGroups(row, r'class="fi fi-([a-z]+)"')[0]
            lang = self.cleanHtmlStr(self.cm.ph.getSearchGroups(row, r'provider-row__lang">([^<]+)<')[0]) or code.upper()
            for chip in row.split("data-provider-chip")[1:]:
                linkId = self.cm.ph.getSearchGroups(chip, r'data-movie-link-id="(\d+)"')[0]
                p = self.cm.ph.getSearchGroups(chip, r'data-p="([^"]+)"')[0]
                hoster = self.cleanHtmlStr(self.cm.ph.getSearchGroups(chip, r'provider-chip__name">([^<]+)<')[0]) or \
                    self.cleanHtmlStr(self.cm.ph.getSearchGroups(chip, r'aria-label="([^"]+)"')[0])
                tags = [self.cleanHtmlStr(t) for t in re.findall(r'provider-chip__metadata-tag[^"]*">([^<]+)<', chip)]
                if linkId and p:
                    chips.append((linkId, code, lang, hoster, " ".join(t for t in tags if t), p))
        chips.sort(key=lambda c: c[1] != "de")
        return chips

    def _readToken(self, data):
        token = self.cm.ph.getSearchGroups(data, r'<meta name="csrf-token" content="([^"]+)"')[0]
        if token:
            self.csrfToken = token

    def getLinksForVideo(self, cItem):
        printDBG("Filmo.getLinksForVideo [%s]" % cItem.get("url"))
        url = self._onMain(cItem.get("url", ""))
        sts, data = self.getPage(url)
        if not sts:
            return []
        self._readToken(data)
        urltab = []
        for linkId, code, lang, hoster, tags, p in self._chips(data):
            name = "%s (%s)" % (hoster or "Link", lang)
            if tags:
                name += " " + tags
            # a stable url (the used-mirror mark and the download key stay valid), data-p changes on every page load
            linkUrl = strwithmeta("%s#%s-%s" % (url, linkId, code), {"filmo_p": p, "Referer": url})
            urltab.append({"name": name, "url": linkUrl, "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        trailer = self.cm.ph.getSearchGroups(data, r'href="(https://www\.youtube\.com/watch\?v=[^"]+)"')[0]
        if trailer:
            urltab.append({"name": _("Trailer"), "url": trailer.replace("&amp;", "&"), "need_resolve": 1})
        info = self._siteInfo(data)
        metaQuery = sidecarMetaQuery("movie", cItem.get("meta_title") or info.get("_title", ""), info.get("year", ""), skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info.get("_story", ""), metaQuery))

    def _mint(self, pageUrl, p):
        # POST /n {p} -> {"x": token}; "" when the session / CSRF token is gone (HTTP 419)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"X-CSRF-TOKEN": self.csrfToken, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json",
                                 "Referer": pageUrl, "Origin": self.getMainUrl().rstrip("/")})
        sts, data = self.getPage(self.getFullUrl("n"), params, {"p": p})
        if not sts:
            return ""
        try:
            return str(json_loads(data).get("x") or "")
        except Exception:
            printDBG("Filmo._mint: no token in [%s]" % (data or "")[:200])
        return ""

    def getVideoLinks(self, videoUrl):
        printDBG("Filmo.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if "#" not in videoUrl or "/movies/" not in videoUrl:
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        pageUrl, key = str(videoUrl).split("#", 1)
        pageUrl = self._onMain(pageUrl)
        p = videoUrl.meta.get("filmo_p", "") if hasattr(videoUrl, "meta") else ""
        token = self._mint(pageUrl, p) if (p and self.csrfToken) else ""
        if not token:
            # a new session (or a link from an older list): the page again for a fresh CSRF token and data-p
            sts, data = self.getPage(pageUrl)
            if not sts:
                return []
            self._readToken(data)
            for linkId, code, _lang, _hoster, _tags, newP in self._chips(data):
                if "%s-%s" % (linkId, code) == key:
                    p = newP
                    break
            token = self._mint(pageUrl, p) if p else ""
        if not token:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"]["Referer"] = pageUrl
        params["no_redirection"] = True
        sts, data = self.getPage(self.getFullUrl("n/%s" % token), params)
        location = self.cm.meta.get("location", "")
        if not self.cm.isValidUrl(location) and sts:
            # hosters that do not allow embedding (Byse): a "Video öffnen" page with the hoster link
            location = self.cm.ph.getSearchGroups(data, r'<a class="open" href="([^"]+)"')[0].replace("&amp;", "&")
        if not self.cm.isValidUrl(location):
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(location, {"Referer": self.getMainUrl()})), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # INFO fields of a film page; "_" keys are no INFO fields
        info = {}
        info["_title"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h1[^>]*>(.*?)</h1>')[0])
        info["_story"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="[^"]*movie-detail-synopsis">(.*?)</p>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'(/img/poster/desktop/[A-Za-z0-9]+)')[0]
        info["_poster"] = self.getFullUrl(poster + "?format=jpg") if poster else ""
        for label, value in re.findall(r'(?s)<h3 class="section-headline">(.*?)</h3>\s*</dt>\s*<dd[^>]*>(.*?)</dd>', data):
            label = self.cleanHtmlStr(label).lower()
            value = self.cleanHtmlStr(value)
            if not value:
                continue
            if label == "erscheinungsdatum":
                info["released"] = value
                info["year"] = value[:4]
            elif label in INFO_FIELDS:
                info[INFO_FIELDS[label]] = value
        age = self.cm.ph.getSearchGroups(data, r'aria-label="(\d+) — [^"]*\(FSK \d+\)\."')[0]
        if age:
            info["age_limit"] = "FSK %s" % age
        return info

    def getArticleContent(self, cItem):
        printDBG("Filmo.getArticleContent [%s]" % cItem.get("url"))
        sts, data = self.getPage(cItem.get("url", ""))
        info = self._siteInfo(data if sts else "")
        title = cItem.get("meta_title") or info.get("_title", "")
        meta = {}
        try:
            if title:
                meta = getMeta("movie", title, info.get("year", "") or cItem.get("meta_year", ""))
        except Exception:
            printExc()
        otherInfo = dict((k, v) for k, v in info.items() if not k.startswith("_"))
        otherInfo.update(meta.get("info", {}))
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in otherInfo:
                otherInfo.pop(siteKey, None)
        plot = meta.get("plot", "")
        text = info.get("_story", "") or cItem.get("desc", "")
        if plot and text and plot != text:
            text = "%s[/br][/br]%s" % (text, plot)
        else:
            text = text or plot
        icon = info.get("_poster") or cItem.get("icon", "") or meta.get("poster", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Filmo.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_collections":
            self.listCollections(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_years":
            self.listYears(self.currItem)
        elif category == "list_az":
            self.listAZ(self.currItem)
        elif category in ("search", "search_next_page"):
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
        CHostBase.__init__(self, Filmo(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("filmo")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "video"
