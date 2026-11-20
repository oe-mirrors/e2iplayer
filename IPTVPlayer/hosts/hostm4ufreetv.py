# -*- coding: utf-8 -*-
LAST_MODIFIED = "20.11.2026"
# 20.11.2026 - new host for m4ufreetv.net: films and series of the m4u Laravel site behind Cloudflare, servers via /ajax to urlparser
import os
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getItemMeta, metaArticle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://m4ufreetv.net/"


COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")
EPISODE_RE = re.compile(r"S(\d+)\s*-\s*E(\d+)", re.I)
# "<li><strong>Label:</strong><span>value</span></li>" rows of the info box -> INFO keys
INFO_FIELDS = (("rating", "Vote"), ("status", "Status"), ("seasons", "Total_seasons"), ("quality", "Quality"),
               ("duration", "Duration"), ("rated", "Content Rating"), ("language", "Language"), ("country", "Country"),
               ("released", "Released"), ("genres", "Genre"), ("actors", "Stars"), ("director", "Director"),
               ("creator", "Creators"))
PAGING_KEYS = ("base_url", "page_tpl")
RATE_LIMIT_WAIT = 10


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


def _splitTitle(title, year=""):
    # "Batman Begins (2005)", "Tulsa King (2022-)", "War (2025–)", "Justice League: War 2014" -> (name, year)
    title = (title or "").strip()
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", title)
    if m and m.group(1):
        found = re.search(r"(?:19|20)\d{2}", m.group(2))
        return m.group(1).strip(), year or (found.group(0) if found else "")
    m = re.match(r"^(.*\S)\s+((?:19|20)\d{2})$", title)
    if m and (not year or year == m.group(2)):
        return m.group(1).strip(), m.group(2)
    return title, year


def _slug(text):
    # like the site's keyme(): lower case, apostrophes dropped, everything else but a-z0-9 becomes "-"
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower().replace("'", "")).strip("-")


class M4uFreeTV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "ep_id",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "m4ufreetv", "cookie": "m4ufreetv.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        # /movies and /tvshows only redirect; the lists live under these paths
        self.MENU = [
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/new-movies")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/new-tv-series")},
            {"category": "list_items", "title": _("Popular movies"), "url": self.getFullUrl("/top-movies")},
            {"category": "list_items", "title": _("Popular series"), "url": self.getFullUrl("/top-tv-series")},
            {"category": "list_items", "title": _("Top rated movies"), "url": self.getFullUrl("/top-imdb-movies")},
            {"category": "list_items", "title": _("Top rated series"), "url": self.getFullUrl("/top-imdb-tvshows")},
            {"category": "mf_filter", "title": _("Genres"), "filter": "genre-"},
            {"category": "mf_filter", "title": _("Year"), "filter": "release-year-"},
            {"category": "mf_filter", "title": _("Country"), "filter": "country/"},
            {"category": "mf_filter", "title": _("Tags"), "filter": "tag/"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("m4ufreetv")
        self.wfInitFolderCache()
        self.rateWaited = False

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        status = self._status(data)
        if not sts and post_data is None and status in (500, 502):
            # the m4u sites answer now and then with a bare "500 Internal Server Error"
            printDBG("M4uFreeTV.getPage: HTTP %s - asking once more" % status)
            sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data

    def _status(self, data):
        # HTTP status of the last failed request (the answer's meta, else the one pCommon kept)
        meta = getattr(data, "meta", None) or getattr(self.cm, "meta", None) or {}
        return meta.get("status_code") if isinstance(meta, dict) else None

    def _post(self, url, referer, post_data):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, **{"Referer": referer, "X-Requested-With": "XMLHttpRequest", "Origin": self.MAIN_URL.rstrip("/")})
        return self.getPage(url, params, post_data)

    def _token(self, data):
        # the Laravel _token of the page's ajax scripts, else the csrf-token meta
        return self.cm.ph.getSearchGroups(data, r"_token:\s*'([^']+)'")[0] or \
            self.cm.ph.getSearchGroups(data, r'<meta[^>]+name="csrf-token"[^>]+content="([^"]+)"')[0]

    def _pageToken(self, pageUrl):
        # the page and its token; a page that came back as a server error page has none - ask once more
        sts, data, token = False, "", ""
        for _attempt in range(2):
            sts, data = self.getPage(pageUrl)
            token = self._token(data) if sts else ""
            if token:
                break
        return sts, data, token

    def _postWithToken(self, path, pageUrl, post_data, token):
        # HTTP 419 = the token expired (new session): fetch a fresh one from the page and post once more
        sts, data = self._post(self.getFullUrl(path), pageUrl, dict(post_data, _token=token))
        if not sts and self._status(data) == 419:
            printDBG("M4uFreeTV._postWithToken: HTTP 419 - token expired, refreshing it")
            newToken = self._pageToken(pageUrl)[2]
            if newToken:
                token = newToken
                sts, data = self._post(self.getFullUrl(path), pageUrl, dict(post_data, _token=token))
        if not sts and self._status(data) == 429 and not self.rateWaited:
            # rate limit of the ajax calls (about seven in ten seconds, "Retry-After: 10"): wait once per link list
            printDBG("M4uFreeTV._postWithToken: HTTP 429 - waiting %ss" % RATE_LIMIT_WAIT)
            self.rateWaited = True
            time.sleep(RATE_LIMIT_WAIT)
            sts, data = self._post(self.getFullUrl(path), pageUrl, dict(post_data, _token=token))
        return sts, data, token

    def _iconMeta(self):
        # the posters (image.m4ufreetv.net) sit behind the same Cloudflare check as the pages: the icon
        # download needs the cf_clearance cookie and the User-Agent that passed the check
        meta = {"Referer": self.MAIN_URL}
        try:
            if os.path.isfile(self.COOKIE_FILE):
                cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ")
                if cookieHeader:
                    meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent", ""), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return meta

    def _icon(self, url, meta):
        url = self.getFullIconUrl(url) if url else ""
        return strwithmeta(url, meta) if url.startswith("http") else url

    def _path(self, url):
        # domain independent identity of a page (episode rows keep their "#<episode id>")
        return re.sub(r"^https?://[^/]+", "", url or "").rstrip("/").lower()

    def getFavouriteData(self, cItem):
        if cItem.get("category") in ("mf_video", "mf_series", "mf_season"):
            return self.getFavouriteFieldsData(cItem)
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            prefix = {"mf_video": "video", "mf_series": "series", "mf_season": "season"}.get(category, "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            if path and category == "mf_season":
                path = "%s#s%s" % (path, cItem.get("s_season", ""))
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listFilter(self, cItem):
        # genres, years, countries and tags from the menu / footer / tag cloud of a list page
        sts, data = self.getPage(self.getFullUrl("/new-movies"))
        if not sts:
            return
        prefix = cItem.get("filter", "")
        seen = set()
        for href, label in re.findall(r'<a[^>]+href="/?(%s[^"]+)"[^>]*>(.*?)</a>' % re.escape(prefix), data, re.S):
            label = self.cleanHtmlStr(label)
            if not label or href in seen:
                continue
            seen.add(href)
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"category": "list_items", "title": label, "url": self.getFullUrl("/" + href), "good_for_fav": True})
            params.pop("filter", None)
            self.addDir(params)

    def _pageTemplate(self, pager):
        # the url of any numbered page with "{page}" in place of its number, and the last page
        # (pagers seen: new-movies?page=N, top-imdb-movies/page/N, country/india/N, search/x/page/N)
        tpl, lastPage = "", 0
        for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>', pager):
            num = int(label) if label.isdigit() else 0
            if label.lower() == "last":
                found = re.findall(r"\d+", href)
                num = int(found[-1]) if found else 0
            if num < 2:
                continue
            lastPage = max(lastPage, num)
            if not tpl:
                head, sep, tail = href.rpartition(str(num))
                if sep:
                    tpl = self.getFullUrl(head.replace("{", "{{").replace("}", "}}") + "{page}" + tail.replace("{", "{{").replace("}", "}}"))
        return tpl, lastPage

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        tpl = cItem.get("page_tpl", "")
        url = baseUrl if page <= 1 or not tpl else tpl.format(page=page)
        printDBG("M4uFreeTV.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        content, pager = data.split("<!-- sidebar -->", 1)[0], ""
        if 'class="pagination' in content:
            # "pagination-custom" on the lists, "pagination" on the search results
            content, pager = content.split('class="pagination', 1)
            pager = pager.split("</ul>", 1)[0]
        normalize = IsMediaNamingNormalized()
        iconMeta = self._iconMeta()
        seen = set()
        for item in content.split('<div class="movie-item">')[1:]:
            # the movie-name link is a "..." placeholder: the image anchor has the page url
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]*watch-(?:movie|tvseries)-[^"]+)"')[0]
            if not href:
                continue
            url = self.getFullUrl(href)
            if url in seen:
                continue
            seen.add(url)
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            yearLabel = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="movie-year">(.*?)</div>')[0])
            year = self.cm.ph.getSearchGroups(yearLabel, r"((?:19|20)\d{2})")[0]
            title, year = _splitTitle(rawTitle, year)
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="badge-quality">(.*?)</span>')[0])
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="overlay-desc">(.*?)</p>')[0])
            if plot.upper() in ("NA", "N/A"):
                plot = ""
            fields = ((_("Quality"), quality, "yellow"), (_("Year"), yearLabel or year, "cyan"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
            if plot:
                desc = "%s[/br]%s" % (desc, plot) if desc else plot
            dispTitle = rawTitle
            if normalize:
                # the site's series titles carry a running year ("Tulsa King (2022-)", "War (2025–)")
                dispTitle = "%s (%s)" % (title, year) if year else title
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self._icon(icon, iconMeta), "desc": desc,
                      "title": dispTitle, "meta_title": title, "meta_year": year}
            if "watch-tvseries-" in url:
                params.update({"category": "mf_series", "s_title": title, "meta_type": "tv"})
                self.addDir(params)
            else:
                params.update({"category": "mf_video", "meta_type": "movie"})
                self.addVideo(params)

        pageTpl, lastPage = self._pageTemplate(pager)
        pageTpl = pageTpl or tpl
        lastPage = max(lastPage, page)
        hasNext = bool(seen) and bool(pageTpl) and lastPage > page
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl, "page_tpl": pageTpl})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def _episodes(self, data):
        # [(season, episode, episode id)] ascending (the page lists them newest first)
        episodes, seen = [], set()
        for epId, label in re.findall(r'<button[^>]+class="btn-episode[^"]*"[^>]+idepisode="([^"]+)"[^>]*>([^<]*)<', data):
            m = EPISODE_RE.search(label)
            if not m or epId in seen:
                continue
            seen.add(epId)
            episodes.append((int(m.group(1)), int(m.group(2)), epId))
        episodes.sort()
        return episodes

    def listSeries(self, cItem):
        printDBG("M4uFreeTV.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        episodes = self._episodes(data)
        seasons = sorted(set(e[0] for e in episodes))
        if len(seasons) <= 1:
            self.listEpisodes(cItem, episodes)
            return
        for season in seasons:
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            show = cItem.get("s_title", "") or cItem["title"]
            params.update({"good_for_fav": True, "category": "mf_season", "title": "%s - %s %d" % (show, _("Season"), season), "s_title": show,
                           "s_season": season})
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        printDBG("M4uFreeTV.listEpisodes [%s]" % cItem.get("url", ""))
        seriesUrl = cItem["url"].split("#", 1)[0]
        if episodes is None:
            sts, data = self.getPage(seriesUrl)
            if not sts:
                return
            episodes = [e for e in self._episodes(data) if e[0] == cItem.get("s_season")]
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        for season, episode, epId in episodes:
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - S%02d-E%02d" % (show, season, episode)  # the site's own episode label
            params = stripPagerKeys(dict(cItem), PAGING_KEYS)
            params.update({"good_for_fav": True, "category": "mf_video", "title": title, "url": "%s#%s" % (seriesUrl, epId), "ep_id": epId,
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("M4uFreeTV.listSearchResult [%s]" % searchPattern)
        slug = _slug(searchPattern)
        if not slug:
            return
        cItem = dict(cItem)
        base = self.getFullUrl("/search/%s.html" % slug)
        cItem.update({"category": "list_items", "url": base, "base_url": base, "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        info = {}
        for key, label in INFO_FIELDS:
            val = self.cm.ph.getSearchGroups(data, r'(?s)<li><strong>%s:</strong>\s*<span[^>]*>(.*?)</span>\s*</li>' % re.escape(label))[0]
            val = re.sub(r"\s*,\s*", ", ", self.cleanHtmlStr(val)).strip(" ,")
            if val and val.upper() not in ("N/A", "NA"):
                info[key] = val
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="storyline-content">(.*?)</div>')[0])
        if story.upper() in ("NA", "N/A"):
            story = ""
        poster = self.cm.ph.getSearchGroups(data, r'<img[^>]+class="img-responsive"[^>]+src="([^"]+)"')[0]
        return story, self._icon(poster, self._iconMeta()), info

    def getLinksForVideo(self, cItem):
        printDBG("M4uFreeTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl, _sep, epId = cItem.get("url", "").partition("#")
        epId = epId or cItem.get("ep_id", "")
        self.rateWaited = False
        sts, data, token = self._pageToken(pageUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        if not token:
            # without the Laravel _token every /ajax POST answers 419 "Page Expired"
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        if epId:
            # an episode's server buttons come from /ajaxtv (with a fresh token of their own)
            sts, data, token = self._postWithToken("/ajaxtv", pageUrl, {"idepisode": epId}, token)
            if not sts:
                return []
            token = self._token(data) or token
        urltab, seen = [], set()
        for serverData, label in re.findall(r'class="server-item[^"]*"\s+data="([^"]+)"\s*>([^<]*)<', data):
            sts, html, token = self._postWithToken("/ajax", pageUrl, {"m4u": serverData}, token)
            if not sts:
                continue
            src = self.cm.ph.getSearchGroups(html, r'<iframe[^>]+src="([^"]+)"')[0]
            if src.startswith("//"):
                src = "https:" + src
            if not self.cm.isValidUrl(src) or src in seen:
                continue
            seen.add(src)
            if self.up.checkHostSupport(src) != 1:
                # servers urlparser does not know are left out
                printDBG("M4uFreeTV.getLinksForVideo unsupported server %s [%s]" % (label, src))
                continue
            name = "%s (%s)" % (self.up.getHostName(src).capitalize(), self.cleanHtmlStr(label)) if label.strip() else self.up.getHostName(src).capitalize()
            urltab.append({"name": name, "url": strwithmeta(src, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    # getVideoLinks: the base default (urlparser + the sidecar the link carries)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("M4uFreeTV.getArticleContent [%s]" % cItem.get("url", ""))
        meta = getItemMeta(cItem, checkLatin=False)
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", "").split("#", 1)[0])
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        # the site's own poster first, the moviemeta one only when the page has none
        return metaArticle(cItem, dict(meta, poster="") if poster else meta, story=story, poster=poster, info=info,
                           desc=_stripColors(cItem.get("desc", "")))

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("M4uFreeTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "mf_filter":
            self.listFilter(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "mf_series":
            self.listSeries(self.currItem)
        elif category == "mf_season":
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
        CHostBase.__init__(self, M4uFreeTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("m4ufreetv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("mf_video", "mf_series", "mf_season")
