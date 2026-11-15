# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
#   sololatino.net (Laravel): films, series, animes and doramas in Spanish (Latino), sorted lists, genres,
#   years and platforms (First / Jump / Next page), search through the site's suggest API (the /buscar page
#   is behind a Cloudflare challenge)
#   streams: the player buttons of the title page -> POST api/player-url -> embed69.org page, its hoster
#   mirrors per language (Latino / Castellano / Subtitulado) listed one by one (urlparser embed69Mirrors)
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
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.sololatino_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.sololatino_domain)]


def gettytul():
    return "https://sololatino.net/"


EPISODES_PER_PAGE = 100
# embed69 mirrors of one title, in the order the site lists its languages
LANGUAGES = ("LAT", "ESP", "SUB")


def _jsonLoads(text):
    # stdlib json gives unicode on Python 2 - as UTF-8 str like the rest of the host's texts
    return ensure_str_deep(json.loads(text))


class SoloLatino(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "sololatino", "cookie": "sololatino.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.sololatino_domain.value.strip()
        self.MAIN_URL = domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul()
        sections = (("peliculas", _("Movies")), ("series", _("Series")), ("animes", _("Anime")), ("doramas", "Doramas"))
        self.MENU = [{"category": "list_section", "title": title, "section": path} for path, title in sections]
        self.MENU += [{"category": "list_networks", "title": "Plataformas", "url": self.MAIN_URL}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("sololatino")
        self.wfInitFolderCache()

    def _siteUrl(self, url):
        # favourites keep the domain of the day they were added - the site hops domains
        return re.sub(r"^https?://[^/]+/", self.MAIN_URL, self.getFullUrl(url))

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._siteUrl(baseUrl), addParams, post_data)

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
            if category == "sl_series":
                return "series:%s" % path
            if category == "sl_season":
                return "season:%s|%s" % (path, cItem.get("season", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listSection(self, cItem):
        printDBG("SoloLatino.listSection |%s|" % cItem)
        base = self.MAIN_URL + cItem["section"]
        for sort, title in (("updated", _("Latest added")), ("popular", _("Most popular")), ("rating", _("Top rated")), ("az", _("A-Z"))):
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": "%s?sort=%s" % (base, sort)})
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_filter", "title": _("Genres"), "url": base, "filter": "genero"})
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_filter", "title": _("Year"), "url": base, "filter": "a%C3%B1o"})

    def listFilter(self, cItem):
        # the options of the genre / year selector of a section page
        printDBG("SoloLatino.listFilter |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        name = urllib_unquote(cItem["filter"])
        block = self.cm.ph.getSearchGroups(data, r'(?s)<select name="%s"[^>]*>(.*?)</select>' % re.escape(name))[0]
        base = self._siteUrl(cItem["url"]).split("?")[0]
        for value, title in re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)<', block):
            if value in ("", "0"):
                continue
            # the site lists a genre by popularity (like its own selector does)
            url = "%s?genero=%s&sort=popular" % (base, value) if name == "genero" else "%s?%s=%s" % (base, cItem["filter"], value)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": url})

    def listNetworks(self, cItem):
        printDBG("SoloLatino.listNetworks")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for url, icon, title in re.findall(r'<a href="([^"]*/red/[^"]+)"[^>]*>\s*<img src="([^"]*)"[^>]*alt="([^"]*)"', data):
            if url in seen:
                continue
            seen.add(url)
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": url, "icon": icon})

    def _addTitle(self, url, title, icon, year="", rating="", kind="", desc=""):
        title = self.cleanHtmlStr(title)
        url = self.getFullUrl(url)
        if not url or not title:
            return False
        descLine = " | ".join(x for x in (kind, year, "%s: %s" % (_("Rating"), rating) if rating else "") if x)
        if descLine:
            desc = "%s[/br]%s" % (descLine, desc) if desc else descLine
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc, "meta_title": title, "meta_year": year}
        if "/pelicula/" in url:
            label = "%s (%s)" % (title, year) if (year and IsMediaNamingNormalized()) else title
            params.update({"category": "video", "title": label, "meta_type": "movie"})
            self.addVideo(params)
        else:
            params.update({"category": "sl_series", "title": title, "s_title": title, "meta_type": "tv"})
            self.addDir(params)
        return True

    def _pageUrl(self, url, page):
        url = re.sub(r"[?&]page=\d+", "", url)
        if page == 1:
            return url
        return "%s%spage=%s" % (url, "&" if "?" in url else "?", page)

    def listItems(self, cItem):
        printDBG("SoloLatino.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        baseUrl = cItem.get("base_url") or cItem["url"]
        sts, data = self.getPage(self._pageUrl(baseUrl, page))
        if not sts:
            return
        count = 0
        for card in data.split('<div class="card">')[1:]:
            url = self.cm.ph.getSearchGroups(card, r'<a href="([^"]+)"')[0]
            title = self.cm.ph.getSearchGroups(card, r'alt="([^"]*)"')[0]
            icon = self.cm.ph.getSearchGroups(card, r'<img\s+src="([^"]+)"')[0]
            year = self.cm.ph.getSearchGroups(card, r'class="card__year">\s*(\d{4})')[0]
            rating = self.cm.ph.getSearchGroups(card, r'class="card__rating">[^\d<]*([\d.]+)')[0]
            kind = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'class="badge card__badge[^"]*">([^<]+)<')[0])
            if self._addTitle(url, title, icon, year, rating, kind):
                count += 1
        pages = [int(p) for p in re.findall(r'class="page-item[^"]*">\s*<a href="[^"]*[?&;]page=(\d+)"', data)]
        lastPage = max(pages + [page]) if count else 0
        nextItem = stripPagerKeys(dict(cItem))
        nextItem["base_url"] = baseUrl
        addPagingItems(self, nextItem, page, bool(count) and page < lastPage, lastPage, self._pageUrl(baseUrl, 987654).replace("987654", "{page}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SoloLatino.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        sts, data = self.getPage(self.MAIN_URL + "api/search/suggest?q=" + urllib_quote_plus(searchPattern.strip()))
        if not sts:
            return
        try:
            results = _jsonLoads(data)
        except Exception:
            printExc()
            return
        for item in results if isinstance(results, list) else []:
            if isinstance(item, dict) and item.get("type") != "person":
                self._addTitle(str(item.get("url") or ""), str(item.get("title") or ""), str(item.get("poster") or ""), str(item.get("year") or ""))

    def listSeasons(self, cItem):
        printDBG("SoloLatino.listSeasons |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        imdb = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
        seasons = [(num, self.cleanHtmlStr(label)) for num, label in re.findall(r'<option value="(\d+)"[^>]*>([^<]+)<', data) if "data-season-panel=\"%s\"" % num in data]
        if not seasons:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        sTitle = cItem.get("s_title", cItem["title"])
        fields = {"s_title": sTitle, "imdb": imdb, "meta_type": "tv", "meta_title": cItem.get("meta_title", sTitle), "meta_year": cItem.get("meta_year", "")}
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, category="sl_season", season=seasons[0][0], **fields), data)
            return
        for num, label in seasons:
            title = "%s - %s" % (sTitle, formatSxxExx(num) if IsMediaNamingNormalized() else label)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "sl_season", "title": title, "season": num, "desc": label})
            params.update(fields)
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("SoloLatino.listEpisodes |%s|" % cItem)
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        if not cItem.get("imdb"):
            cItem = dict(cItem, imdb=self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0])
        season = str(cItem.get("season", ""))
        panel = data.split('data-season-panel="%s"' % season, 1)
        panel = panel[1].split("data-season-panel=")[0] if len(panel) > 1 else ""
        episodes = re.findall(r'(?s)<a href="([^"]+)"\s+class="ep-item(.*?)</a>', panel)
        page = max(1, int(cItem.get("page", 1) or 1))
        lastPage = (len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
        normalize = IsMediaNamingNormalized()
        sTitle = cItem.get("s_title", cItem["title"])
        for url, item in episodes[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]:
            epNum = self.cm.ph.getSearchGroups(item, r'class="ep-num">\s*E?(\d+)')[0] or self.cm.ph.getSearchGroups(url, r"episodio-(\d+)")[0]
            epName = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<p class="text-sm font-semibold[^"]*">(.*?)</p>')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<p class="text-xs mt-1 line-clamp-2"[^>]*>(.*?)</p>')[0])
            aired = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<p class="text-xs mt-1"[^>]*>([^<]*)</p>')[0])
            if normalize and epNum:
                title = "%s - %s" % (sTitle, formatSxxExx(season, epNum))
            else:
                title = " - ".join(x for x in (sTitle, "T%s E%s" % (season, epNum) if epNum else "", epName) if x)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "episode", "title": title, "url": self.getFullUrl(url), "ep_num": epNum, "ep_name": epName,
                           "icon": self.cm.ph.getSearchGroups(item, r'<img\s+src="([^"]+)"')[0] or cItem.get("icon", ""),
                           "desc": "[/br]".join(x for x in (" | ".join(y for y in (epName, aired) if y), desc) if x)})
            self.addVideo(params)
        if lastPage > 1:
            # the page lives in cItem["page"] - the template keeps the series url unchanged
            addPagingItems(self, dict(cItem, category="sl_season"), page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def _playerUrls(self, pageUrl, data):
        # [(language tab, button label, player url)] of a title page: each button carries a token, the
        # api turns it into the player url (Laravel Sanctum: XSRF cookie + X-XSRF-TOKEN header)
        # tab "<flag> Latino", button "<star> Principal": only the words go into the link name
        tabs = dict((key, " ".join(re.findall(r"[A-Za-z0-9]+", self.cleanHtmlStr(label)))) for key, label in re.findall(r'(?s)data-lang-tab="([^"]+)"[^>]*>(.*?)</button>', data))
        buttons = []
        for group in data.split('data-lang-group="')[1:]:
            key = group.split('"', 1)[0]
            group = group.split('id="main-player-wrap"')[0]
            for token, label in re.findall(r'(?s)data-player-token="([^"]+)"[^>]*>(.*?)</button>', group):
                buttons.append((tabs.get(key, key), " ".join(re.findall(r"[A-Za-z0-9]+", self.cleanHtmlStr(label))), token))
        if not buttons:
            return []
        self.getPage(self.MAIN_URL + "sanctum/csrf-cookie")
        xsrf = urllib_unquote(self.cm.getCookieItem(self.COOKIE_FILE, "XSRF-TOKEN") or "")
        header = dict(self.HEADER)
        header.update({"Content-Type": "application/json", "Accept": "application/json", "X-XSRF-TOKEN": xsrf, "Referer": self._siteUrl(pageUrl),
                       "Origin": self.MAIN_URL.rstrip("/")})
        params = dict(self.defaultParams)
        params.update({"header": header, "raw_post_data": True})
        result = []
        for tab, label, token in buttons:
            sts, answer = self.getPage(self.MAIN_URL + "api/player-url", dict(params), json.dumps({"t": token}))
            try:
                url = str(_jsonLoads(answer).get("url") or "") if sts else ""
            except Exception:
                url = ""
            if url.startswith("//"):
                url = "https:" + url
            if self.cm.isValidUrl(url):
                result.append((tab, label, url))
                if "/embed69." in url or "/player.pelisserieshoy." in url:
                    # the other buttons are the same embed69 page again (or its mirror domain) - and the api
                    # answers 429 to a few quick requests
                    break
        return result

    def _embed69Url(self, cItem, data):
        # the embed69 page by IMDb id when the player api gave nothing: films /f/tt<id>, episodes /f/tt<id>-<s>x<ee>
        imdb = cItem.get("imdb", "") or self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
        if not imdb:
            return ""
        if cItem.get("category") == "episode":
            try:
                return "https://embed69.org/f/%s-%dx%02d" % (imdb, int(cItem.get("season", "")), int(cItem.get("ep_num", "")))
            except (TypeError, ValueError):
                return ""
        return "https://embed69.org/f/%s" % imdb

    def getLinksForVideo(self, cItem):
        printDBG("SoloLatino.getLinksForVideo [%s]" % cItem)
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        players = self._playerUrls(cItem["url"], data)
        if not players:
            fallback = self._embed69Url(cItem, data)
            players = [("", "", fallback)] if fallback else []
        urltab = []
        seen = set()
        for tab, label, url in players:
            if "/embed69." in url or "/player.pelisserieshoy." in url:
                # the player page of all languages: its hoster mirrors one by one, "Latino voe" ...
                key = re.sub(r"^https?://[^/]+/", "", url)
                if key in seen:
                    continue
                seen.add(key)
                url = strwithmeta(url, {"Referer": self.MAIN_URL})
                try:
                    mirrors = self.up.getEmbed69Mirrors(url)
                except Exception:
                    printExc()
                    mirrors = []
                # the site order of the languages is Latino, Castellano, Subtitulado - keep it whatever the page sends
                mirrors.sort(key=lambda m: LANGUAGES.index(m["lang"]) if m["lang"] in LANGUAGES else len(LANGUAGES))
                for mirror in mirrors:
                    if str(mirror["url"]) not in seen:
                        seen.add(str(mirror["url"]))
                        urltab.append({"name": mirror["name"], "url": mirror["url"], "need_resolve": 1})
                if not mirrors:
                    # no mirror list: the player page itself, urlparser resolves its mirrors when it is picked
                    urltab.append({"name": " ".join(x for x in (tab, label, "embed69") if x), "url": url, "need_resolve": 1})
            elif url not in seen and self.up.checkHostSupport(url) == 1:
                seen.add(url)
                name = " ".join(x for x in (tab, label or self.up.getHostName(url, True)) if x)
                urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        ld = self._ldJson(data, ("Movie", "TVEpisode"))
        sidecarTxt = self.cleanHtmlStr(ld.get("description", "")) or cItem.get("desc", "")
        if cItem.get("category") == "episode":
            metaQuery = sidecarMetaQuery("tv", cItem.get("meta_title", "") or cItem.get("s_title", ""), cItem.get("meta_year", ""), cItem.get("imdb", ""), skip=())
        else:
            imdb = self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
            metaQuery = sidecarMetaQuery("movie", cItem.get("meta_title", ""), cItem.get("meta_year", ""), imdb, skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt, metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("SoloLatino.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("SoloLatino.getArticleContent [%s]" % cItem)
        category = cItem.get("category", "")
        mediaType = "movie" if category == "video" else "tv"
        info = {}
        desc = ""
        imdb = cItem.get("imdb", "")
        icon = cItem.get("icon", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            imdb = imdb or self.cm.ph.getSearchGroups(data, r"imdb\.com/title/(tt\d+)")[0]
            ld = self._ldJson(data, ("TVEpisode",) if category == "episode" else ("Movie", "TVSeries"))
            desc = self.cleanHtmlStr(ld.get("description", ""))
            if desc.lower() in (str(cItem.get("s_title", "")).lower(), str(ld.get("name", "")).lower()):
                desc = ""  # episodes without a synopsis carry the show name as "description"
            genres = ld.get("genre") or []
            if genres:
                info["genres"] = ", ".join(genres) if isinstance(genres, list) else str(genres)
            names = [p.get("name", "") for p in ld.get("actor") or [] if isinstance(p, dict)]
            if names:
                info["actors"] = ", ".join(names[:5])
            names = [p.get("name", "") for p in ld.get("director") or [] if isinstance(p, dict)]
            if names:
                info["director"] = ", ".join(names)
            duration = self.cm.ph.getSearchGroups(str(ld.get("duration", "")), r"PT(\d+)M")[0]
            if duration:
                info["duration"] = "%s min" % duration
            released = str(ld.get("datePublished", "") or "")
            if released:
                info["released"] = released
            rating = (ld.get("aggregateRating") or {}).get("ratingValue")
            if rating:
                info["rating"] = "%s/10" % rating
            icon = icon or str(ld.get("image") or "")
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            title = cItem.get("meta_title", "") or cItem.get("s_title", "")
            if not meta and title:
                meta = getMeta(mediaType, title, cItem.get("meta_year", ""))
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
        if category == "episode":
            # the episode's own synopsis, the series plot when the site has none for it
            text = desc or plot or cItem.get("desc", "")
        else:
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
        elif category == "list_section":
            self.listSection(self.currItem)
        elif category == "list_filter":
            self.listFilter(self.currItem)
        elif category == "list_networks":
            self.listNetworks(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "sl_series":
            self.listSeasons(self.currItem)
        elif category == "sl_season":
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
        CHostBase.__init__(self, SoloLatino(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("sololatino")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("video", "episode", "sl_series", "sl_season")
