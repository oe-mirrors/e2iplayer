# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
#   hdfilmcehennemi.nl: Turkish film + series site (Türkçe Dublaj / Türkçe Altyazılı), film lists, genres, years,
#   countries, film series, foreign series -> seasons -> episodes, search (the site's JSON search). Page 1 of a
#   list is the html page, the next ones /load/page/<n>/<data-page-action>/ (JSON html)
#   streams: the language tabs + player buttons of a title page -> /video/<id>/ -> hdfilmcehennemi.mobi embed
#   ("Close") or <site>/rplayer/<id>/ ("Rapidrame"), both resolved by urlparser parserHDFILMCEHENNEMI
import json
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str_deep
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.hdfilmcehennemi_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.hdfilmcehennemi_domain)]


def gettytul():
    return "https://www.hdfilmcehennemi.nl/"


EPISODES_PER_PAGE = 100
# the urlparser knows these domains of the site (its /rplayer/ pages)
PARSER_DOMAINS = ("hdfilmcehennemi.nl", "hdfilmcehennemi.ws")


def _jsonLoads(text):
    # stdlib json gives unicode on Python 2 - as UTF-8 str like the rest of the host's texts
    return ensure_str_deep(json.loads(text))


class HDFilmCehennemi(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "hdfilmcehennemi", "cookie": "hdfilmcehennemi.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE,
                              "ignore_http_code_ranges": [(451, 451)]}
        domain = config.plugins.iptvplayer.hdfilmcehennemi_domain.value.strip()
        self.MAIN_URL = domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul()
        self.MENU = [{"category": "list_movies", "title": _("Movies")},
                     {"category": "list_series_menu", "title": _("Series")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("hdfilmcehennemi")
        self.wfInitFolderCache()

    def _siteUrl(self, url):
        # favourites keep the domain of the day they were added - the site hops domains
        return re.sub(r"^https?://[^/]+/", self.MAIN_URL, self.getFullUrl(url))

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        sts, data = self.cm.getPageCFProtection(self._siteUrl(baseUrl), addParams, post_data)
        if sts and "Unavailable For Legal Reasons" in data[:5000]:
            # some titles are blocked by country (HTTP 451, also from Germany)
            SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking)."))
            return False, ""
        return sts, data

    def _fetch(self, url, referer=""):
        # the site's own json requests (/load/..., /search/, /video/<id>/)
        header = dict(self.HEADER)
        header.update({"X-Requested-With": "fetch", "Accept": "application/json, text/plain, */*", "Referer": self._siteUrl(referer or self.MAIN_URL)})
        sts, data = self.getPage(url, dict(self.defaultParams, header=header))
        if not sts:
            return {}
        try:
            data = _jsonLoads(data)
        except Exception:
            printExc()
            return {}
        return data if isinstance(data, dict) else {}

    def _ldJson(self, data, types):
        # the schema.org object (Movie / TVSeries / TVEpisode) of a title page
        for block in re.findall(r'(?s)<script type="application/ld\+json">(.*?)</script>', data):
            try:
                obj = _jsonLoads(block)
            except Exception:
                continue
            for item in obj.get("@graph", [obj]) if isinstance(obj, dict) else []:
                if isinstance(item, dict) and item.get("@type") in types:
                    return item
        return {}

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if not path:
                return ""
            category = cItem.get("category", "")
            if category in ("video", "episode"):
                return "video:%s" % path
            if category == "hd_series":
                return "series:%s" % path
            if category == "hd_season":
                return "season:%s|%s" % (path, cItem.get("season", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # menus
    ###################################################
    def listMovies(self, cItem):
        # the list urls carry a number the site changes now and then: taken from the menu of the home page
        printDBG("HDFilmCehennemi.listMovies")
        sts, data = self.getPage(self.MAIN_URL)
        links = re.findall(r'href="(https?://[^"]+)"', data) if sts else []

        def find(pattern, default):
            for url in links:
                if re.search(pattern, url):
                    return url
            return self.MAIN_URL + default

        entries = ((_("Latest added"), self.MAIN_URL),
                   (_("All movies"), find(r"/category/film-izle-\d+/", "category/film-izle-2/")),
                   ("Türkçe Dublaj", find(r"/dil/[^/]*dublaj", "dil/turkce-dublajli-film-izleyin-6/")),
                   ("Türkçe Altyazılı", find(r"/dil/[^/]*altyazi", "dil/turkce-altyazili-filmleri-izleme-sitesi-3/")),
                   (_("Recommended"), find(r"/category/tavsiye-filmler", "category/tavsiye-filmler-izle2/")),
                   ("IMDb 7+", find(r"/imdb-7-puan", "imdb-7-puan-uzeri-filmler-2/")),
                   ("En Çok Beğenilenler", find(r"/en-cok-begenilen", "en-cok-begenilen-filmleri-izle-4/")),
                   (_("Most commented"), find(r"/en-cok-yorumlanan", "en-cok-yorumlananlar-2/")),
                   ("Nette İlk", find(r"/category/nette-ilk", "category/nette-ilk-filmler-1/")),
                   (_("Collections"), find(r"/serifilmlerim", "serifilmlerim-4/")))
        for title, url in entries:
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": url})
        for title, kind in ((_("Genres"), "tur"), (_("Year"), "yil"), (_("Countries"), "ulke"), (_("Categories"), "category")):
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_tags", "title": title, "url": self.MAIN_URL, "tag": kind})

    def listTags(self, cItem):
        # genres / years / countries / categories of the site menu
        printDBG("HDFilmCehennemi.listTags |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        kind = cItem["tag"]
        seen = set()
        for url, title in re.findall(r'<a[^>]+href="([^"]*/%s/[^"]+)"[^>]*>([^<]*)<' % re.escape(kind), data):
            title = self.cleanHtmlStr(title)
            if kind == "yil":
                title = self.cm.ph.getSearchGroups(url, r"/yil/(?:\d-)?(\d{4})")[0] or title
            if kind == "category" and (not title or re.search(r"/(?:film-izle|tavsiye-filmler|nette-ilk|fragman)", url)):
                continue  # already in the film menu / trailers
            if not title or url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": url})

    def listSeriesMenu(self, cItem):
        printDBG("HDFilmCehennemi.listSeriesMenu")
        sts, data = self.getPage(self.MAIN_URL)
        url = self.cm.ph.getSearchGroups(data, r'href="(https?://[^"]+/yabancidiziizle-\d+/)"')[0] if sts else ""
        url = url or self.MAIN_URL + "yabancidiziizle-5/"
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": _("Series"), "url": url})
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": _("Latest episodes"), "url": url, "section": "recent-episodes"})

    ###################################################
    # lists
    ###################################################
    def _addCard(self, url, attrs, inner):
        url = self.getFullUrl(url)
        cssClass = self.cm.ph.getSearchGroups(attrs, r'class="([^"]*)"')[0].split()
        episode = re.search(r"/sezon-(\d+)/bolum-(\d+)", url)
        # list posters; "mini-poster" rows are episodes (or the side bar of the home page), sliders are the top films again
        if not url or not ("poster" in cssClass or ("mini-poster" in cssClass and episode)):
            return False
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(attrs, r'title="([^"]*)"')[0])
        title = title or self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'(?s)class="(?:mini-)?poster-title">(.*?)</h')[0])
        title = title or re.sub(r"\s+izle$", "", self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'alt="([^"]*)"')[0]))
        if not title:
            return False
        icon = self.cm.ph.getSearchGroups(inner, r'data-src="([^"]+)"')[0]
        meta = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'(?s)class="poster-meta">(.*?)</div>')[0])
        year = self.cm.ph.getSearchGroups(meta, r"\b((?:19|20)\d{2})\b")[0]
        rating = self.cm.ph.getSearchGroups(meta, r"\b(\d{1,2}\.\d)\b")[0]
        lang = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r'(?s)class="poster-lang">(.*?)</span>\s*</span>')[0])
        return self._addTitle(url, title, icon, year, "" if rating in ("0.0", "") else rating, lang, episode)

    def _addTitle(self, url, title, icon, year="", rating="", lang="", episode=None, kind=""):
        descLine = " | ".join(x for x in (kind, year, "%s: %s" % (_("Rating"), rating) if rating else "", lang) if x)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": descLine, "meta_title": title, "meta_year": year}
        if episode:
            # "Latest episodes": the show's title, season / episode from the url
            season, epNum = episode.groups()
            seriesUrl = url.split("/sezon-")[0] + "/"
            label = "%s - %s" % (title, formatSxxExx(season, epNum) if IsMediaNamingNormalized() else "%s. Sezon %s. Bölüm" % (season, epNum))
            params.update({"category": "episode", "title": label, "s_title": title, "season": season, "ep_num": epNum, "series_url": seriesUrl, "meta_type": "tv"})
            self.addVideo(params)
        elif "/dizi/" in url:
            params.update({"category": "hd_series", "title": title, "s_title": title, "meta_type": "tv"})
            self.addDir(params)
        elif "/serifilmlerim" in url:
            params.update({"category": "list_items", "title": title})
            self.addDir(params)
        else:
            label = "%s (%s)" % (title, year) if (year and IsMediaNamingNormalized()) else title
            params.update({"category": "video", "title": label, "meta_type": "movie"})
            self.addVideo(params)
        return True

    def _pager(self, data, section):
        # (load url template with {page}, last page or 0 when unknown) of a list page
        if section:
            # a second list on the page ("recent-episodes"): "load more" without a page count
            action = "page/%s" % section if 'data-loadmore-items="%s"' % section in data else ""
            pages = ""
        else:
            action = self.cm.ph.getSearchGroups(data, r'data-page-action="([^"]+)"')[0]
            pages = self.cm.ph.getSearchGroups(data, r'data-pages="(\d+)"')[0]
            if action:
                action = "page/" + action
            else:
                action = self.cm.ph.getSearchGroups(data, r'data-loadmore-action="([^"]+)"')[0]
                pages = self.cm.ph.getSearchGroups(data, r'data-loadmore-pages="(\d+)"')[0]
        if not action:
            return "", 0
        action = action.strip("/")
        if action.startswith("page/"):
            tpl = "%sload/page/{page}/%s/" % (self.MAIN_URL, action[5:])
        else:
            tpl = "%sload/{page}/%s/" % (self.MAIN_URL, action)
        return tpl, int(pages) if pages else 0

    def listItems(self, cItem):
        printDBG("HDFilmCehennemi.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        section = cItem.get("section", "")
        loadTpl = cItem.get("load_tpl", "")
        lastPage = int(cItem.get("last_page", 0) or 0)
        if page == 1 or not loadTpl:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
            loadTpl, lastPage = self._pager(data, section)
            marker = ('data-loadmore-items="%s"' % section) if section else ("data-page-items" if "data-page-items" in data else "data-loadmore-items")
            if marker in data:
                data = data.split(marker, 1)[1].split("</section>")[0]
            if page > 1:
                data = ""
        else:
            data = ""
        if page > 1 and loadTpl:
            data = str(self._fetch(loadTpl.format(page=page), cItem["url"]).get("html") or "")
        count = 0
        for url, attrs, inner in re.findall(r'(?s)<a\s+href="([^"]+)"([^>]*)>(.*?)</a>', data):
            if self._addCard(url, attrs, inner):
                count += 1
        hasNext = bool(count) and bool(loadTpl) and (page < lastPage if lastPage else True)
        nextItem = stripPagerKeys(dict(cItem), ("load_tpl",))
        nextParams = {"load_tpl": loadTpl} if loadTpl else None
        # the page lives in cItem["page"] - the template keeps the list url unchanged
        addPagingItems(self, nextItem, page, hasNext, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}") if lastPage else "", nextParams)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("HDFilmCehennemi.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        results = self._fetch(self.MAIN_URL + "search/?q=" + urllib_quote_plus(searchPattern.strip())).get("results") or []
        for item in results if isinstance(results, list) else []:
            item = str(item)
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h4 class="title">(.*?)</h4>')[0])
            if not url or not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'\ssrc="(http[^"]+)"')[0].replace("/thumb/", "/list/")
            year = self.cm.ph.getSearchGroups(item, r'class="year">\s*(\d{4})')[0]
            rating = self.cm.ph.getSearchGroups(item, r'(?s)class="imdb">.*?([\d.]+)\s*</span>')[0]
            kind = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="type">([^<]*)<')[0])
            self._addTitle(url, title, icon, year, "" if rating in ("0.0", "") else rating, kind=kind)

    def listSeasons(self, cItem):
        printDBG("HDFilmCehennemi.listSeasons |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        imdb = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
        seasons = re.findall(r'<button class="section-tab"[^>]*data-tab="(\d+)">([^<]+)<', data.split('class="seasons"', 1)[-1])
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", cItem["title"])
        fields = {"s_title": sTitle, "imdb": imdb, "meta_type": "tv", "meta_title": cItem.get("meta_title", sTitle), "meta_year": cItem.get("meta_year", "")}
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category="hd_season", season=seasons[0][0], **fields), data)
            return
        for num, label in seasons:
            title = "%s - %s" % (sTitle, formatSxxExx(num) if IsMediaNamingNormalized() else self.cleanHtmlStr(label))
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "hd_season", "title": title, "season": num, "desc": self.cleanHtmlStr(label)})
            params.update(fields)
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("HDFilmCehennemi.listEpisodes |%s|" % cItem)
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        if not cItem.get("imdb"):
            cItem = dict(cItem, imdb=self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0])
        season = str(cItem.get("season", ""))
        panel = data.split('id="seasons-%s"' % season, 1)
        panel = panel[1].split('class="seasons-tab-content"')[0] if len(panel) > 1 else ""
        episodes = re.findall(r'(?s)<a href="([^"]+/sezon-\d+/bolum-(\d+)/?)"(.*?)</a>', panel)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        lastPage = (len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
        normalize = IsMediaNamingNormalized()
        sTitle = cItem.get("s_title", cItem["title"])
        for url, epNum, item in episodes[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]:
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="mini-poster-title">(.*?)</h4>')[0])
            aired = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<time[^>]*>(.*?)</time>')[0])
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, epNum))
            else:
                title = "%s - %s" % (sTitle, label or "%s. Sezon %s. Bölüm" % (season, epNum))
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "episode", "title": title, "url": self.getFullUrl(url), "ep_num": epNum, "ep_name": label,
                           "series_url": cItem["url"], "desc": " | ".join(x for x in (label, aired) if x)})
            self.addVideo(params)
        if lastPage > 1:
            addPagingItems(self, dict(cItem, category="hd_season"), page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("HDFilmCehennemi.getLinksForVideo [%s]" % cItem)
        pageUrl = self._siteUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        # language tabs ("Türkçe Dublaj", "Türkçe Altyazılı", "DUAL (Türkçe Dublaj & Altyazılı)") and their players
        # (the dual one shortened to "Türkçe Dublaj & Altyazılı")
        tabs = dict((key, re.sub(r"^DUAL\s*\((.+)\)$", r"\1", self.cleanHtmlStr(label))) for key, label in re.findall(r'(?s)<button class="language-link"[^>]*data-lang="([^"]*)"[^>]*>(.*?)</button>', data))
        urltab = []
        for group in data.split('<div class="alternative-links"')[1:]:
            key = self.cm.ph.getSearchGroups(group, r'data-lang="([^"]*)"')[0]
            group = group.split("</div>")[0]
            for videoId, label in re.findall(r'(?s)data-video="(\d+)"[^>]*>(.*?)</button>', group):
                name = " ".join(x for x in (tabs.get(key, key.upper()), self.cleanHtmlStr(label)) if x)
                url = strwithmeta("%svideo/%s/" % (self.MAIN_URL, videoId), {"Referer": pageUrl})
                urltab.append({"name": name, "url": url, "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        ld = self._ldJson(data, ("Movie", "TVEpisode", "TVSeries"))
        sidecarTxt = self.cleanHtmlStr(ld.get("description", "")) or cItem.get("desc", "")
        imdb = cItem.get("imdb", "") or self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
        if cItem.get("category") == "episode":
            metaQuery = sidecarMetaQuery("tv", cItem.get("meta_title", "") or cItem.get("s_title", ""), cItem.get("meta_year", ""), imdb, skip=())
        else:
            metaQuery = sidecarMetaQuery("movie", cItem.get("meta_title", ""), cItem.get("meta_year", ""), imdb, skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt, metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("HDFilmCehennemi.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        referer = strwithmeta(videoUrl).meta.get("Referer", "")
        # the player of the button: <iframe data-src="https://hdfilmcehennemi.mobi/video/embed/..."> or ".../rplayer/<id>/"
        data = self._fetch(videoUrl, referer).get("data")
        html = data.get("html") if isinstance(data, dict) else ""
        html = html if isinstance(html, str) else ""
        url = self.cm.ph.getSearchGroups(html, r'data-src="([^"]+)"')[0].replace("\\/", "/")
        if url.startswith("//"):
            url = "https:" + url
        if not self.cm.isValidUrl(url):
            SetIPTVPlayerLastHostError(_("Video link not found."))
            return []
        meta = {"Referer": self.MAIN_URL}
        domain = self.up.getHostName(url)
        if "/rplayer/" in url and domain not in PARSER_DOMAINS:
            meta["host_name"] = PARSER_DOMAINS[0]  # an alternative domain of the site: the same player
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(url, meta)), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("HDFilmCehennemi.getArticleContent [%s]" % cItem)
        category = cItem.get("category", "")
        mediaType = "movie" if category == "video" else "tv"
        info = {}
        desc = ""
        imdb = cItem.get("imdb", "")
        icon = cItem.get("icon", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            imdb = imdb or self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
            ld = self._ldJson(data, ("TVEpisode", "TVSeries") if category == "episode" else ("Movie", "TVSeries"))
            desc = self.cleanHtmlStr(ld.get("description", ""))
            # schema.org values come as text, list of texts or objects with a "name"
            genres = ld.get("genre") or []
            genres = [g.get("name", "") if isinstance(g, dict) else g for g in (genres if isinstance(genres, list) else [genres])]
            genres = [g for g in genres if isinstance(g, str) and g]
            if genres:
                info["genres"] = self.cleanHtmlStr(", ".join(genres))
            names = [p.get("name", "") for p in ld.get("actor") or [] if isinstance(p, dict)]
            if names:
                info["actors"] = ", ".join(names[:5])
            names = [p.get("name", "") for p in ld.get("director") or [] if isinstance(p, dict)]
            if names:
                info["director"] = ", ".join(names)
            duration = self.cm.ph.getSearchGroups(str(ld.get("duration", "")), r"PT(\d+)M")[0]
            if duration and duration != "0":
                info["duration"] = "%s min" % duration
            rating = self.cm.ph.getSearchGroups(data, r'(?s)class="post-info-imdb-rating">.*?<span>\s*([\d.]+)')[0]
            if rating and rating != "0.0":
                info["rating"] = "%s/10" % rating
            image = ld.get("image") or ""
            image = image[0] if isinstance(image, list) and image else image
            image = image.get("url", "") if isinstance(image, dict) else image
            icon = icon or (image if isinstance(image, str) else "")
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            title = cItem.get("meta_title", "") or cItem.get("s_title", "")
            if not meta and title:
                meta = getMeta(mediaType, title.split(" - ")[-1], cItem.get("meta_year", ""))
        except Exception:
            printExc()
        meta = meta or {}
        info.update(meta.get("info", {}))
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in info:
                info.pop(siteKey, None)
        if cItem.get("meta_year") and "year" not in info:
            info["year"] = cItem["meta_year"]
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
        elif category == "list_movies":
            self.listMovies(self.currItem)
        elif category == "list_tags":
            self.listTags(self.currItem)
        elif category == "list_series_menu":
            self.listSeriesMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "hd_series":
            self.listSeasons(self.currItem)
        elif category == "hd_season":
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
        CHostBase.__init__(self, HDFilmCehennemi(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("hdfilmcehennemi")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("video", "episode", "hd_series", "hd_season")
