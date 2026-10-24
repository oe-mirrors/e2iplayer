# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
#   fullhdfilmizlesene.now (the .de domain redirects there): Turkish film site - latest, popular, trending, IMDb top,
#   yerli (Turkish) / dubbed / subtitled films, genres, years, film collections, search (First / Jump / Next page)
#   streams: the inline "scx" object of a film page, one entry per player, each link ROT13 + base64; the players
#   are rapidvid.org embeds (urlparser parserRAPIDVID: Turkish and original audio, Turkish / English subtitles)
import base64
import codecs
import json
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.fullhdfilmizlesene_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.fullhdfilmizlesene_domain)]


def gettytul():
    return "https://www.fullhdfilmizlesene.now/"


def _jsonLoads(text):
    # stdlib json gives unicode on Python 2 - as UTF-8 str like the rest of the host's texts
    return ensure_str_deep(json.loads(text))


class FullHDFilmizlesene(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "fullhdfilmizlesene", "cookie": "fullhdfilmizlesene.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.fullhdfilmizlesene_domain.value.strip()
        self.MAIN_URL = domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul()
        lists = ((_("Latest added"), ""), (_("Most popular"), "populer-filmler"), (_("Trending"), "trend-filmler"),
                 ("IMDb Puanı Yüksek Filmler", "filmizle/imdb-puani-yuksek-filmler"), ("Yerli Filmler", "filmizle/yerli-filmler"),
                 ("Türkçe Dublaj", "filmizle/turkce-dublaj-filmler-1"), ("Türkçe Altyazılı", "filmizle/turkce-altyazili-filmler-1"))
        self.MENU = [{"category": "list_items", "good_for_fav": True, "title": title, "url": self.MAIN_URL + path} for title, path in lists]
        self.MENU += [{"category": "list_links", "title": _("Genres"), "link_type": "genres"},
                      {"category": "list_links", "title": _("Categories"), "link_type": "categories"},
                      {"category": "list_links", "title": _("Year"), "link_type": "years"},
                      {"category": "list_items", "good_for_fav": True, "title": _("Collections"), "url": self.MAIN_URL + "seri-filmler"}]
        self.MENU += self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("fullhdfilmizlesene")
        self.wfInitFolderCache()

    def _siteUrl(self, url):
        # favourites keep the domain of the day they were added - the site hops domains (.de, .now ...)
        return re.sub(r"^https?://[^/]+/", self.MAIN_URL, self.getFullUrl(url))

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._siteUrl(baseUrl), addParams, post_data)

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", str(url or "").strip()).rstrip("/")

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            if cItem.get("category") == "video":
                return "video:%s" % path
            if cItem.get("category") == "list_items" and "/serifilm/" in path:
                return "folder:%s" % path
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listLinks(self, cItem):
        # the genre / category (language, quality) blocks of the side bar, the year links of the menu
        printDBG("FullHDFilmizlesene.listLinks |%s|" % cItem)
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        linkType = cItem.get("link_type", "")
        if linkType == "years":
            links = re.findall(r'<a[^>]+href="([^"]*/yil/[^"]+)"[^>]*>([^<]+)<', data)
        else:
            blocks = re.findall(r'(?s)<ul class="turler">(.*?)</ul>', data)
            block = blocks[0 if linkType == "genres" else 1] if len(blocks) > 1 else (blocks[0] if blocks else "")
            links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)<', block)
        seen = set()
        for url, title in links:
            url = self.getFullUrl(url)
            title = self.cleanHtmlStr(title)
            if linkType == "years":
                # "2026 Filmleri" ... "2020 Filmleri", then "2019" ... "2011"
                title = self.cm.ph.getSearchGroups(title, r"(\d{4})")[0] or title
            elif "/yil/" in url:
                continue  # the category block repeats some years - they are under "Year"
            if url in seen or not title:
                continue
            seen.add(url)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": url})

    def _pageUrl(self, baseUrl, page):
        baseUrl = self._siteUrl(baseUrl).rstrip("/")
        if page <= 1:
            return baseUrl + "/" if baseUrl + "/" == self.MAIN_URL else baseUrl
        if baseUrl + "/" == self.MAIN_URL:
            return "%syeni-filmler/%d" % (self.MAIN_URL, page)
        return "%s/%d" % (baseUrl, page)

    def _addCard(self, card, cItem):
        url = self.getFullUrl(self.cm.ph.getSearchGroups(card, r'href="([^"]+)"')[0])
        # <span class="film-title">Title</span>, trending: <a class="film-title" href=..>Title<span class="kt">Original</span></a>
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'class="film-title"[^>]*>([^<]+)')[0])
        if not url or not title:
            return False
        origTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<span class="kt">(.*?)</span>')[0])
        if origTitle.lower() == title.lower():
            origTitle = ""
        icon = self.cm.ph.getSearchGroups(card, r'data-src="([^"]+)"')[0]
        year = self.cm.ph.getSearchGroups(card, r'class="film-yil">\s*(\d{4})')[0]
        if "/serifilm/" in url:
            count = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'class="film-cnt">([^<]+)<')[0])
            label = " - ".join(x for x in (title, origTitle) if x)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": label, "url": url, "icon": icon,
                         "desc": " | ".join(x for x in (origTitle, count) if x)})
            return True
        lang = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'class="trz[^"]*"[^>]*>([^<]+)<')[0])
        uhd = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'class="uhd">([^<]+)<')[0])
        imdbRating = self.cm.ph.getSearchGroups(card, r'class="imdb">\s*([\d.]+)')[0]
        genres = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'class="ktt">([^<]+)<')[0])
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="seri-content[^"]*">(.*?)</div>')[0])
        # film covers of a collection page are named after the IMDb id
        imdb = self.cm.ph.getSearchGroups(card, r"/(tt\d{5,})\.(?:jpg|webp)")[0]
        descLine = " | ".join(x for x in (year, lang, uhd, "IMDb %s" % imdbRating if imdbRating else "", genres) if x)
        desc = "[/br]".join(x for x in (origTitle and "%s: %s" % (_("Original title"), origTitle), descLine, plot) if x)
        if IsMediaNamingNormalized():
            label = "%s (%s)" % (title, year) if year else title
        else:
            label = " - ".join(x for x in (title, origTitle) if x)
        params = stripPagerKeys(dict(cItem))
        params.update({"name": "category", "good_for_fav": True, "category": "video", "title": label, "url": url, "icon": icon, "desc": desc,
                       "meta_type": "movie", "meta_title": origTitle or title, "meta_alt_title": title if origTitle else "", "meta_year": year,
                       "meta_imdb": imdb})
        params.pop("base_url", None)
        self.addVideo(params)
        return True

    def listItems(self, cItem):
        printDBG("FullHDFilmizlesene.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        baseUrl = cItem.get("base_url") or cItem["url"]
        sts, data = self.getPage(self._pageUrl(baseUrl, page))
        if not sts:
            return
        count = 0
        for card in data.split('<li class="film">')[1:]:
            if self._addCard(card.split("</li>")[0], cItem):
                count += 1
        if not count:
            return
        pager = self.cm.ph.getSearchGroups(data, r'(?s)<div class="sayfalama">(.*?)</div>')[0]
        pages = [int(p) for p in re.findall(r"""href=['"][^'"]*/(\d+)/?['"]""", pager)]
        lastPage = max(pages + [page])
        nextItem = stripPagerKeys(dict(cItem))
        nextItem["base_url"] = baseUrl
        addPagingItems(self, nextItem, page, page < lastPage, lastPage, self._pageUrl(baseUrl, 987654).replace("987654", "{page}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FullHDFilmizlesene.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.MAIN_URL + "arama/" + urllib_quote(searchPattern.strip())
        self.listItems(dict(cItem, category="list_items", url=url))

    ###################################################
    # links
    ###################################################
    def _players(self, data):
        # scx = {"atom": {"tt": base64 name, "sx": {"t": [ROT13(base64(url)), ...] or {label: ...}}, "order": n}, ...}
        start = data.find("scx = ")
        if start < 0:
            return []
        try:
            scx = json.JSONDecoder().raw_decode(data[start + 6:])[0]
        except Exception:
            printExc()
            return []
        if not isinstance(scx, dict):
            return []

        def _order(kv):
            # "order" may come as number or as string - a mixed int/str sort fails on Python 3
            try:
                return (int(kv[1].get("order", 99)), kv[0])
            except (AttributeError, TypeError, ValueError):
                return (99, kv[0])

        players = []
        for key, item in sorted(scx.items(), key=_order):
            if not isinstance(item, dict):
                continue
            try:
                name = ensure_str(base64.b64decode(item.get("tt") or "")).strip()
            except Exception:
                name = ""
            name = name or ensure_str(key).capitalize()
            links = item.get("sx")
            links = (links.get("t") or []) if isinstance(links, dict) else []
            if not isinstance(links, (dict, list)):
                links = []
            if isinstance(links, dict):
                links = [("%s %s" % (name, ensure_str(label)), value) for label, value in sorted(links.items())]
            else:
                links = [("%s %d" % (name, idx + 1) if len(links) > 1 else name, value) for idx, value in enumerate(links)]
            for label, value in links:
                try:
                    url = ensure_str(base64.b64decode(codecs.encode(ensure_str(value), "rot13"))).strip()
                except Exception:
                    printExc()
                    continue
                if url.startswith("//"):
                    url = "https:" + url
                players.append((label, url))
        return players

    def getLinksForVideo(self, cItem):
        printDBG("FullHDFilmizlesene.getLinksForVideo [%s]" % cItem)
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        urltab = []
        seen = set()
        for label, url in self._players(data):
            if url in seen or not self.cm.isValidUrl(url) or self.up.checkHostSupport(url) != 1:
                printDBG("FullHDFilmizlesene.getLinksForVideo skipped [%s] [%s]" % (label, url))
                continue
            seen.add(url)
            urltab.append({"name": "%s - %s" % (label, self.up.getHostName(url, True)), "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        sidecarTxt = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="ozet-ic">(.*?)</div>')[0]) or cItem.get("desc", "")
        altTitles = (cItem["meta_alt_title"],) if cItem.get("meta_alt_title") else ()
        metaQuery = sidecarMetaQuery("movie", cItem.get("meta_title", ""), cItem.get("meta_year", ""), cItem.get("meta_imdb", ""), altTitles=altTitles)
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt, metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("FullHDFilmizlesene.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _detail(self, data, label):
        # <li><span class="dt">Yönetmen</span><div class="dd">...</div></li>
        return self.cm.ph.getSearchGroups(data, r'(?s)<span class="dt">\s*%s[^<]*</span>\s*<div class="dd">(.*?)</div>' % re.escape(label))[0]

    def getArticleContent(self, cItem):
        printDBG("FullHDFilmizlesene.getArticleContent [%s]" % cItem)
        info = {}
        desc = ""
        icon = cItem.get("icon", "")
        title = cItem.get("meta_title", "")
        altTitle = cItem.get("meta_alt_title", "")
        year = cItem.get("meta_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="ozet-ic">(.*?)</div>')[0])
            pageTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="izle-titles">\s*<h1>(.*?)</h1>')[0])
            pageOrig = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="izle-titles">.*?<h2>(.*?)</h2>')[0])
            if pageTitle and not title:
                title, altTitle = (pageOrig, pageTitle) if pageOrig and pageOrig.lower() != pageTitle.lower() else (pageTitle, "")
            year = year or self.cm.ph.getSearchGroups(self._detail(data, "Yap"), r"(\d{4})")[0]
            for key, label in (("director", "Yönetmen"), ("actors", "Oyuncular"), ("genres", "Tür"), ("language", "Dil")):
                value = ", ".join(x for x in (self.cleanHtmlStr(v) for v in self._detail(data, label).split(",")) if x)
                if value:
                    info[key] = value
            duration = self.cm.ph.getSearchGroups(data, r'class="sure">\s*(\d+)')[0]
            if duration:
                info["duration"] = "%s min" % duration
            rating = self.cm.ph.getSearchGroups(data, r'(?s)class="imdb-ic">.*?<span>([\d.]+)<')[0]
            if rating:
                info["imdb_rating"] = "%s/10" % rating
            icon = self.cm.ph.getSearchGroups(data, r'property="og:image" content="([^"]+)"')[0] or icon
        if altTitle:
            # meta_title is the original title when the site has one, the Turkish title is the other one
            info["original_title"] = title
        meta = {}
        try:
            if cItem.get("meta_imdb"):
                meta = getMetaByImdbId("movie", cItem["meta_imdb"])
            for name in (title, altTitle):
                if meta or not name:
                    continue
                meta = getMeta("movie", name, year)
        except Exception:
            printExc()
        meta = meta or {}
        info.update(meta.get("info", {}))
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in info:
                info.pop(siteKey, None)
        if year and "year" not in info:
            info["year"] = year
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
        elif category == "list_links":
            self.listLinks(self.currItem)
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
        CHostBase.__init__(self, FullHDFilmizlesene(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("fullhdfilmizlesene")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "video"
