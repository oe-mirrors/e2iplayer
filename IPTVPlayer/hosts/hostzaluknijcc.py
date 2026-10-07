# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 04.10.2026 - zaluknij.cc rework (Polish movies and series)
#   - Cloudflare: every request goes through getPageCFProtection (MyE2i solves the browser check, the
#     solving User-Agent is remembered next to the cookie jar); the UA pCommon really used is taken
#     over for the posters, which need the same UA + cf_clearance (damagic)
#   - movies: sort orders, genres, years, versions (Lektor, Napisy PL ...); series: new episodes,
#     recently added, popular, most viewed, all; kids; search (movies + series with description)
#   - First page / Jump / Next page on every list (?page=N), long seasons paged by 100 episodes
#   - title from <div class="title">, alt or title attribute, "S01 E04" meta line (damagic)
#   - movies and episodes are VIDEO rows keyed on their page url; series -> seasons (when more than
#     one) -> episodes (ascending)
#   - links: the hosting table of the page (version / quality in the name) -> urlparser
#   - watched flag, downloaded flag, favourites (old favourites keep working), name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the site's fields
###################################################
import re
import json
import base64

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://zaluknij.cc/"


COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")
TILE_RE = re.compile(r'(?s)<a href="(https?://[^"]+/(?:film|serial-online)/[^"]+)"([^>]*)>(.*?)</a>')
EPISODE_RE = re.compile(r'<a href="([^"]+)">\s*\[s(\d+)e(\d+)[^\]]*\]\s*([^<]*)</a>', re.I)
# episode pages: /serial-online/<slug>/<id>/odcinek-4, daily shows /odcinki-1862-1868
EPISODE_URL_RE = re.compile(r"/serial-online/[^/]+/\d+/odcin", re.I)
META_LINE_RE = r'<span\s+class="meta-line">([^<]+)</span>'
SXXEXX_RE = re.compile(r"S\s*(\d+)\s*E\s*(\d+)", re.I)
PAGING_KEYS = ("base_url", "page_tpl")
EPISODES_PER_PAGE = 100
# categories of the rows the INFO view / favourites / watched flag know (list_items, list_episodes and
# list_episodes_direct are also the categories of the favourites saved by the old host)
VIDEO_CATEGORIES = ("zal_video", "list_items", "list_episodes_direct")
SERIES_CATEGORIES = ("list_episodes", "zal_season")


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


def _titleParts(title):
    return [p.strip() for p in (title or "").split(" / ") if p.strip()]


def _shortTitle(title):
    # "Zanim koszulka wyschnie / Until the T-shirt Dries / ..." -> the Polish title for episode rows
    parts = _titleParts(title)
    return parts[0] if parts else (title or "").strip()


def _isLatin(text):
    try:
        text = text.decode("utf-8") if isinstance(text, bytes) else text
        return all(ord(c) < 0x2E80 for c in text)  # no CJK / kana / hangul
    except Exception:
        return False


def _metaTitle(title):
    # the original title (after " / ") finds more on TMDb / IMDb than the Polish one - the first one
    # in Latin script ("Snowball Earth / スノウボールアース" -> "Snowball Earth")
    parts = _titleParts(title)
    others = [p for p in parts[1:] if _isLatin(p)]
    return others[0] if others else (parts[0] if parts else "")


class Zaluknij(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Zaluknij", "cookie": "Zaluknij.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        # the UA that solved the browser check replaces this one after the first page (see getPage)
        self.HEADER["User-Agent"] = self.cm.getDefaultUserAgent("edge")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True,
                              "cookiefile": self.COOKIE_FILE, "with_metadata": True}
        self.cacheLinks = {}
        movies = self.getFullUrl("filmy-online/")
        series = self.getFullUrl("seriale-online/index?url=seriale-online%2Findex&sort={sort}&page=1")
        self.MOVIES_MENU = [
            {"category": "list_items", "title": _("Recently added"), "url": movies + "sort:date/"},
            {"category": "list_items", "title": _("Latest"), "url": movies + "sort:premiere/"},
            {"category": "list_items", "title": _("New links"), "url": movies + "sort:link/"},
            {"category": "list_items", "title": _("Most viewed"), "url": movies + "sort:view/"},
            {"category": "list_items", "title": _("Top rated"), "url": movies + "sort:rate/"},
            {"category": "zal_filter", "title": _("Genres"), "url": movies, "filter": "category"},
            {"category": "zal_filter", "title": _("Year"), "url": movies, "filter": "year"},
            {"category": "zal_filter", "title": _("Version"), "url": movies, "filter": "version"},
        ]
        self.SERIES_MENU = [
            {"category": "list_episodes_direct", "title": _("New episodes"), "url": series.format(sort="latest_episodes")},
            {"category": "list_items", "title": _("Recently added"), "url": series.format(sort="recent_series")},
            {"category": "list_items", "title": _("Popular"), "url": series.format(sort="popular_series")},
            {"category": "list_items", "title": _("Most viewed"), "url": series.format(sort="most_viewed_recently")},
            {"category": "list_items", "title": _("All"), "url": series.format(sort="all_series")},
        ]
        self.MENU = [
            {"category": "zal_menu", "title": _("Movies"), "sub_menu": "movies"},
            {"category": "zal_menu", "title": _("Series"), "sub_menu": "series"},
            {"category": "list_episodes_direct", "title": _("New episodes"), "url": series.format(sort="latest_episodes")},
            {"category": "list_items", "title": _("Kids"), "url": self.getFullUrl("dla-dzieci/")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("zaluknijcc")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        sts, data = self.cm.getPageCFProtection(self.cm.iriToUri(baseUrl), addParams, post_data)
        # cf_clearance is bound to the UA that solved the check - the posters (fixIconUrl) need it too
        try:
            cfUser = data.meta.get("cf_user", "")
        except Exception:
            cfUser = ""
        if cfUser and cfUser != self.HEADER.get("User-Agent"):
            self.HEADER["User-Agent"] = cfUser
        return sts, data

    def fixIconUrl(self, iconUrl, referer=None):
        if not iconUrl:
            return ""
        iconUrl = self.getFullIconUrl(iconUrl.replace("/thumb/", "/big/"))
        cf = self.cm.getCookieItem(self.COOKIE_FILE, "cf_clearance")
        # the UA that solved the check (remembered across restarts), else the current one
        meta = {"Referer": referer or self.MAIN_URL, "User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER["User-Agent"]}
        if cf:
            meta["Cookie"] = "cf_clearance=%s" % cf
        return strwithmeta(iconUrl, meta)

    def getDefaulIcon(self, cItem=None):
        # the site's image sits behind the same Cloudflare check as the pages: built when a row is shown
        # (with the current cf_clearance), none before the check was solved (was an HTTP 403 per row)
        if not self.cm.getCookieItem(self.COOKIE_FILE, "cf_clearance"):
            return ""
        return self.fixIconUrl(self.MAIN_URL + "public/dist/images/lgbt.png", self.MAIN_URL)

    def _path(self, url):
        return re.sub(r"^https?://[^/]+", "", url or "").split("#")[0].rstrip("/").lower()

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + SERIES_CATEGORIES:
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _tileTitle(self, attrs, block):
        # (title, meta line) of a tile - <div class="title">Title<br><span class="meta-line">S01 E04</span></div>,
        # else the alt of the poster, else the title attribute of the link (damagic)
        meta = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, META_LINE_RE)[0])
        title = self.cm.ph.getSearchGroups(block, r'(?s)<div\s+class="title">(.*?)</div>')[0]
        title = self.cleanHtmlStr(re.sub(r'(?s)<span\s+class="meta-line">.*?</span>', "", title).replace("<br>", " "))
        if not title:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'<img[^>]+alt="([^"]+)"')[0])
        if not title:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(attrs, r'title="([^"]+)"')[0])
        return title, meta

    def _desc(self, fields, plot=""):
        desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
        if plot:
            desc = "%s[/br]%s" % (desc, plot) if desc else plot
        return desc

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
            category = cItem.get("category", "")
            if cItem.get("type") == "video" and ("/film/" in path or EPISODE_URL_RE.search(path)):
                return "video:%s" % path
            if category == "list_episodes":
                return "series:%s" % path
            if category == "zal_season":
                return "season:%s#s%s" % (path, cItem.get("s_season", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMenu(self, cItem):
        menu = self.MOVIES_MENU if cItem.get("sub_menu") == "movies" else self.SERIES_MENU
        self.listsTab(menu, {"name": "category"})

    def listFilter(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        kind = cItem.get("filter", "")
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="filter-%s"' % kind, "</ul>", False)[1]
        for fid, label in re.findall(r'(?s)<li data-id="([^"]+)"[^>]*>\s*<a[^>]*>([^<]+)</a>', block):
            label = self.cleanHtmlStr(label)
            if not label:
                continue
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "category": "list_items", "title": label, "good_for_fav": True,
                           "url": "%s%s:%s/" % (cItem["url"], kind, fid)})
            params.pop("filter", None)
            self.addDir(params)

    def _paging(self, data, baseUrl, page):
        # (url template with "{page}", last page, has a next page) from the "Następna" / "Ostatnia" links
        def absolute(href):
            href = href.replace("&amp;", "&")
            if href.startswith("?"):
                return baseUrl.split("?")[0] + href
            return self.getFullUrl(href)

        nextUrl = self.cm.ph.getSearchGroups(data, r"""href=['"]([^'"]+)['"][^>]*>\s*Nast""")[0]
        lastUrl = self.cm.ph.getSearchGroups(data, r"""href=['"]([^'"]+)['"][^>]*>\s*Ostat""")[0]
        lastPage = int(self.cm.ph.getSearchGroups(lastUrl, r"page=(\d+)")[0] or 0)
        tpl = ""
        for href in (nextUrl, lastUrl):
            if href and re.search(r"page=\d+", href):
                tpl = re.sub(r"page=\d+", "page={page}", absolute(href).replace("{", "{{").replace("}", "}}"), 1)
                break
        hasNext = bool(nextUrl) or lastPage > page
        return tpl, lastPage, hasNext

    def _addTile(self, url, attrs, block, normalize):
        title, metaLine = self._tileTitle(attrs, block)
        if not title:
            return False
        icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0]
        icon = self.fixIconUrl(icon) if icon else self.getDefaulIcon()
        year = self.cm.ph.getSearchGroups(block, r'<div class="year">\s*(\d{4})\s*<')[0]
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="description[^"]*">(.*?)</div>')[0])
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon}
        if "/film/" in url:
            year = year or self.cm.ph.getSearchGroups(url, r"-((?:19|20)\d{2})/?$")[0]
            rating = self.cm.ph.getSearchGroups(block, r'<div class="rate">([\d.]+)<')[0]
            views = self.cm.ph.getSearchGroups(block, r'<div class="views" title="([\d\s]+)')[0].strip()
            fields = ((_("Year"), year, "cyan"), (_("Rating"), "%s/5" % rating if rating.strip("0.") else "", "green"), (_("Views"), views, "yellow"))
            params.update({"category": "zal_video", "title": "%s (%s)" % (title, year) if year else title,
                           "desc": self._desc(fields, plot), "meta_type": "movie", "meta_title": _metaTitle(title), "meta_year": year})
            self.addVideo(params)
        elif EPISODE_URL_RE.search(url):
            numbers = SXXEXX_RE.search(metaLine)
            show = _shortTitle(title)
            added = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="year">(.*?)</div>')[0]).replace("Dodano:", "").strip()
            if numbers:
                season, episode = int(numbers.group(1)), int(numbers.group(2))
                dispTitle = "%s - %s" % (show, formatSxxExx(season, episode) if normalize else metaLine)
                params.update({"s_season": season, "s_episode": episode})
            else:
                dispTitle = show
            params.update({"category": "zal_video", "title": dispTitle, "desc": self._desc(((_("Added"), added, "cyan"),), title),
                           "s_title": show, "meta_type": "tv", "meta_title": _metaTitle(title), "meta_year": ""})
            self.addVideo(params)
        else:
            views = self.cm.ph.getSearchGroups(block, r"Odsłony\s*(\d+)")[0]
            params.update({"category": "list_episodes", "title": title, "desc": self._desc(((_("Views"), views, "yellow"),), plot),
                           "s_title": title, "meta_type": "tv", "meta_title": _metaTitle(title), "meta_year": ""})
            self.addDir(params)
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        tpl = cItem.get("page_tpl", "")
        url = baseUrl if page <= 1 or not tpl else tpl.format(page=page)
        printDBG("Zaluknij.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        content = data[data.find('role="list"'):] if 'role="list"' in data else data
        normalize = IsMediaNamingNormalized()
        seen = set()
        for tileUrl, attrs, block in TILE_RE.findall(content):
            if tileUrl not in seen and self._addTile(tileUrl, attrs, block, normalize):
                seen.add(tileUrl)
        pageTpl, lastPage, hasNext = self._paging(data, baseUrl, page)
        pageTpl = pageTpl or tpl
        listItem = dict(cItem)
        listItem.update({"base_url": baseUrl, "url": baseUrl, "page_tpl": pageTpl})
        addPagingItems(self, listItem, page, hasNext and bool(seen) and bool(pageTpl), lastPage, pageTpl)

    def _seasons(self, data):
        # {season: [(episode, url, name)]} from the episode list of a series page
        seasons = {}
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="episode-list"', "<hr>", False)[1] or data
        for url, season, episode, name in EPISODE_RE.findall(block):
            season, episode = int(season), int(episode)
            if url not in [e[1] for e in seasons.get(season, [])]:
                seasons.setdefault(season, []).append((episode, url, self.cleanHtmlStr(name)))
        return seasons

    def listSeries(self, cItem):
        printDBG("Zaluknij.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._seasons(data)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        if len(seasons) == 1:
            season = list(seasons)[0]
            self.listEpisodes(dict(cItem, s_season=season), seasons[season])
            return
        for season in sorted(seasons):
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "good_for_fav": True, "category": "zal_season", "s_season": season,
                           "title": "%s %d" % (_("Season"), season), "desc": "%s: %d" % (_("Episodes"), len(seasons[season]))})
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        printDBG("Zaluknij.listEpisodes [%s]" % cItem.get("url", ""))
        season = cItem.get("s_season", 1)
        if episodes is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
            episodes = self._seasons(data).get(season, [])
        episodes = sorted(episodes)
        # long running soaps have thousands of episodes in one season - 100 per page
        page = cItem.get("page", 1)
        lastPage = (len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
        normalize = IsMediaNamingNormalized()
        show = _shortTitle(cItem.get("s_title", "") or cItem.get("title", ""))
        for episode, url, name in episodes[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]:
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = " - ".join(x for x in (show, "S%02d E%02d" % (season, episode), name) if x)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"name": "category", "good_for_fav": True, "category": "zal_video", "title": title, "url": url,
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)
        if lastPage > 1:
            # the page lives in cItem["page"] - the template keeps the series url unchanged
            listItem = dict(cItem, s_season=season, category="zal_season")
            addPagingItems(self, listItem, page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Zaluknij.listSearchResult [%s]" % searchPattern)
        sts, data = self.getPage(self.getFullUrl("wyszukiwarka?phrase=%s" % urllib_quote_plus(searchPattern.strip())))
        if not sts:
            return
        content = self.cm.ph.getDataBeetwenMarkers(data, 'id="advanced-search"', "<footer", False)[1] or data
        normalize = IsMediaNamingNormalized()
        seen = set()
        for tileUrl, attrs, block in TILE_RE.findall(content):
            if tileUrl not in seen and self._addTile(tileUrl, attrs, block, normalize):
                seen.add(tileUrl)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of a movie / series / episode page
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="description">(.*?)</p>')[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta\s+name="description"\s+content="([^"]+)"')[0])
        poster = self.cm.ph.getSearchGroups(data, r'(?s)id="single-poster".*?<img src="([^"]+)"')[0]
        info = {}
        info["year"] = (self.cm.ph.getSearchGroups(data, r'<sup><a href="[^"]+">(\d{4})</a></sup>')[0] or
                        self.cm.ph.getSearchGroups(data, r"<li>Rok\s+Produkcji:</li>\s*<li>(\d{4})</li>")[0])
        info["genres"] = ", ".join(self.cleanHtmlStr(g) for g in re.findall(r'(?s)<li itemprop="genre">\s*<a href="[^"]+">([^<]+)</a>', data))
        info["views"] = self.cm.ph.getSearchGroups(data, r"<li>Odsłony\s*:</li>\s*<li>(\d+)</li>")[0]
        rating = self.cm.ph.getSearchGroups(data, r'itemprop="ratingValue">([\d.]+)<')[0]
        if rating.strip("0."):
            info["rating"] = "%s/5" % rating
        versions, qualities = [], []
        for _url, version, quality in self._linkRows(data):
            if version and version not in versions:
                versions.append(version)
            if quality and quality not in qualities:
                qualities.append(quality)
        info["translation"] = ", ".join(versions)
        info["quality"] = ", ".join(qualities)
        return story, poster, dict((k, v) for k, v in info.items() if v)

    def _linkRows(self, data):
        # [(player url, version, quality)] from the hosting table
        rows = []
        table = self.cm.ph.getDataBeetwenNodes(data, ("<table", ">"), ("</table", ">"), False)[1]
        for row in self.cm.ph.getAllItemsBeetwenNodes(table, ("<tr", ">"), ("</tr", ">")):
            cells = self.cm.ph.getAllItemsBeetwenNodes(row, ("<td", ">"), ("</td", ">"))
            if "<th" in row or len(cells) < 2:
                continue
            playerUrl, version, quality = "", "", ""
            for idx, cell in enumerate(cells):
                if "link-to-video" in cell:
                    # data-iframe = base64 JSON {"src": embed url}, href = the hoster's page
                    frame = self.cm.ph.getSearchGroups(cell, r"""data-iframe=['"]([^'"]+)['"]""")[0]
                    if frame:
                        try:
                            playerUrl = json.loads(base64.b64decode(frame).decode("utf-8")).get("src", "")
                        except Exception:
                            printExc()
                    if not playerUrl:
                        playerUrl = self.cm.ph.getSearchGroups(cell, r"""href=['"]([^'"]+)['"]""")[0]
                elif idx == 2:
                    version = self.cleanHtmlStr(cell)
                elif idx == 3:
                    quality = self.cleanHtmlStr(cell)
            if playerUrl:
                rows.append((self.getFullUrl(playerUrl), version, quality))
        return rows

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("Zaluknij.getLinksForVideo [%s]" % url)
        if self.cacheLinks.get(url):
            return self.cacheLinks[url]
        sts, data = self.getPage(url)
        if not sts:
            return []
        urltab, seen = [], set()
        for playerUrl, version, quality in self._linkRows(data):
            if playerUrl in seen or not self.cm.isValidUrl(playerUrl):
                continue
            seen.add(playerUrl)
            host = self.up.getHostName(playerUrl)
            label = " / ".join(x for x in (version, quality) if x)
            urltab.append({"name": "%s [%s]" % (host, label) if label else host, "url": strwithmeta(playerUrl, {"Referer": url}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = self._siteInfo(data)[0]
        urltab = applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))
        self.cacheLinks[url] = urltab
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("Zaluknij.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Zaluknij.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        meta = {}
        mediaType = cItem.get("meta_type", "") or ("tv" if "/serial-online/" in cItem.get("url", "") else "movie")
        # old favourites have no meta_title: the title without " (Year)" / " [S01 E04]"
        metaTitle = cItem.get("meta_title", "") or _metaTitle(re.sub(r"\s*[(\[][^)\]]*[)\]]$", "", cItem.get("s_title", "") or cItem.get("title", "")))
        try:
            if metaTitle:
                meta = getMeta(mediaType, metaTitle, cItem.get("meta_year", "") or info.get("year", ""))
        except Exception:
            printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = story or plot or _stripColors(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = meta.get("poster") or (self.fixIconUrl(poster) if poster else cItem.get("icon", ""))
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
        printDBG("Zaluknij.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "zal_menu":
            self.listMenu(self.currItem)
        elif category == "zal_filter":
            self.listFilter(self.currItem)
        elif category in ("list_items", "list_episodes_direct"):
            self.listItems(self.currItem)
        elif category == "list_episodes":
            self.listSeries(self.currItem)
        elif category == "zal_season":
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
        CHostBase.__init__(self, Zaluknij(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("zaluknijcc")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in SERIES_CATEGORIES
