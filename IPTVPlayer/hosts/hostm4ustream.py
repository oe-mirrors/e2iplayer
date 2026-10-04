# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026 - new host for m4ustream.com (the new domain of StreamM4u)
#   - Cloudflare: every page and ajax request goes through getPageCFProtection (MyE2i solves the
#     browser check, the solving User-Agent is remembered next to the cookie jar)
#   - movies, TV series, best movies / TV shows, genres, years and search, with First page / Jump /
#     Next page (the pager urls differ per list: movies/page/N, category/x-N, ?page=N ...)
#   - movies are VIDEO rows keyed on their page url; series -> seasons (when more than one) ->
#     episodes (ascending), episodes are VIDEO rows keyed on the series url + the site's episode id
#   - links: the page's server buttons are posted to /ajax (Laravel _token of the page; episodes
#     first through /ajaxtv), the iframe of every server goes to urlparser (abyss, vidsrc, ...);
#     servers urlparser does not know (9stream) are left out
#   - watched flag, downloaded flag, favourites, name normalisation ("Title (Year)",
#     "Show - SxxExx"), sidecar, INFO via moviemeta + the site's fields
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://m4ustream.com/"


COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")
EPISODE_RE = re.compile(r"S(\d+)\s*-\s*E(\d+)", re.I)
# "Label:<span> value</span>" rows of the info box -> INFO keys
INFO_FIELDS = (("genres", "Genre"), ("director", "Director"), ("creator", "Creators"), ("actors", "Starring"),
               ("writer", "Writers"), ("released", "Release date"), ("country", "Countries"),
               ("language", "Languages"), ("duration", "Runtime"), ("quality", "Quality"))
PAGING_KEYS = ("base_url", "page_tpl")


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


def _splitTitle(title, year=""):
    # "Zero Sum (2016)", "Foundation (2021 )", "War (2025–)", "Justice League: War 2014" -> (name, year)
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
    # like the site's locdau(): lower case, everything but a-z0-9 becomes "-"
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


class M4uStream(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "s_title", "s_season", "s_episode", "ep_id",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "m4ustream", "cookie": "m4ustream.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MENU = [
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/movies")},
            {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/tv-series")},
            {"category": "list_items", "title": _("Best movies"), "url": self.getFullUrl("/best-movies")},
            {"category": "list_items", "title": _("Best series"), "url": self.getFullUrl("/best-tvshows")},
            {"category": "m4_filter", "title": _("Genres"), "filter": "category/"},
            {"category": "m4_filter", "title": _("Year"), "filter": "movies-year-"},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("m4ustream")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        status = self._status(data)
        if not sts and post_data is None and status in (500, 502):
            # the site answers about one page request in ten with a bare "500 Internal Server Error"
            printDBG("M4uStream.getPage: HTTP %s - asking once more" % status)
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

    def _pageToken(self, pageUrl):
        # the page and its Laravel _token; a page that came back as a server error page (HTTP 500 seen)
        # has no token - ask once more before giving up
        sts, data, token = False, "", ""
        for _attempt in range(2):
            sts, data = self.getPage(pageUrl)
            token = self.cm.ph.getSearchGroups(data, r"_token:\s*'([^']+)'")[0] if sts else ""
            if token:
                break
        return sts, data, token

    def _postWithToken(self, path, pageUrl, post_data, token):
        # HTTP 419 = the token expired (new session): fetch a fresh one from the page and post once more
        sts, data = self._post(self.getFullUrl(path), pageUrl, dict(post_data, _token=token))
        if not sts and self._status(data) == 419:
            printDBG("M4uStream._postWithToken: HTTP 419 - token expired, refreshing it")
            newToken = self._pageToken(pageUrl)[2]
            if newToken:
                token = newToken
                sts, data = self._post(self.getFullUrl(path), pageUrl, dict(post_data, _token=token))
        return sts, data, token

    def _iconMeta(self):
        # the posters (photo.m4ustream.com) sit behind the same Cloudflare check as the pages: the icon
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
        try:
            if cItem.get("category") in ("m4_video", "m4_series", "m4_season"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            prefix = {"m4_video": "video", "m4_series": "series", "m4_season": "season"}.get(category, "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            if path and category == "m4_season":
                path = "%s#s%s" % (path, cItem.get("s_season", ""))
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listFilter(self, cItem):
        sts, data = self.getPage(self.MAIN_URL)
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
        printDBG("M4uStream.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        content, pager = data, ""
        if 'class="pagination"' in data:
            content, pager = data.split('class="pagination"', 1)
            pager = pager.split("</ul>", 1)[0]
        normalize = IsMediaNamingNormalized()
        iconMeta = self._iconMeta()
        seen = set()
        for item in content.split("<div class=item>")[1:]:
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]*(?:movies|tv-series)/[^"]+)"')[0]
            if not href:
                continue
            url = self.getFullUrl(href)
            if url in seen:
                continue
            seen.add(url)
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            year = self.cm.ph.getSearchGroups(item, r"<div class=jt-info>\s*((?:19|20)\d{2})\s*<")[0]
            title, year = _splitTitle(rawTitle, year)
            if not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"<div class=quality>(.*?)</div>")[0])
            plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"<p class=f-desc>(.*?)</div>")[0])
            fields = ((_("Quality"), quality, "yellow"), (_("Year"), year, "cyan"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
            if plot:
                desc = "%s[/br]%s" % (desc, plot) if desc else plot
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": self._icon(icon, iconMeta), "desc": desc,
                      "meta_title": title, "meta_year": year}
            if "/tv-series/" in url:
                # the site's series titles carry a running year ("Dummy (2020 )", "Coven Academy (2026–)")
                dispTitle = rawTitle
                if normalize:
                    dispTitle = "%s (%s)" % (title, year) if year else title
                params.update({"category": "m4_series", "title": dispTitle, "s_title": title, "meta_type": "tv"})
                self.addDir(params)
            else:
                dispTitle = rawTitle
                if normalize:
                    dispTitle = "%s (%s)" % (title, year) if year else title
                params.update({"category": "m4_video", "title": dispTitle, "meta_type": "movie"})
                self.addVideo(params)

        pageTpl, lastPage = self._pageTemplate(pager)
        pageTpl = pageTpl or tpl
        lastPage = max(lastPage, page)
        hasNext = bool(seen) and bool(pageTpl) and lastPage > page
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "base_url": baseUrl, "url": baseUrl, "page_tpl": pageTpl})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def _episodes(self, data):
        # [(season, episode, episode id)] ascending
        episodes, seen = [], set()
        for epId, label in re.findall(r'<button[^>]+class="episode"[^>]+idepisode="([^"]+)"[^>]*>([^<]*)<', data):
            m = EPISODE_RE.search(label)
            if not m or epId in seen:
                continue
            seen.add(epId)
            episodes.append((int(m.group(1)), int(m.group(2)), epId))
        episodes.sort()
        return episodes

    def listSeries(self, cItem):
        printDBG("M4uStream.listSeries [%s]" % cItem.get("url", ""))
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
            params.update({"good_for_fav": True, "category": "m4_season", "title": "%s %d" % (_("Season"), season), "s_season": season})
            self.addDir(params)

    def listEpisodes(self, cItem, episodes=None):
        printDBG("M4uStream.listEpisodes [%s]" % cItem.get("url", ""))
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
            params.update({"good_for_fav": True, "category": "m4_video", "title": title, "url": "%s#%s" % (seriesUrl, epId), "ep_id": epId,
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("M4uStream.listSearchResult [%s]" % searchPattern)
        slug = _slug(searchPattern)
        if not slug:
            return
        cItem = dict(cItem)
        base = self.getFullUrl("/search/%s" % slug)
        cItem.update({"category": "list_items", "url": base, "base_url": base, "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        info = {}
        for key, label in INFO_FIELDS:
            val = self.cm.ph.getSearchGroups(data, r'(?s)class="h3-detail"[^>]*>\s*%s:\s*<span>(.*?)</span>' % re.escape(label))[0]
            val = re.sub(r"\s*,\s*", ", ", self.cleanHtmlStr(val)).strip(" ,")
            if val and val.upper() != "N/A":
                info[key] = val
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"(?s)<strong>Plot:\s*</strong>(.*?)</pre>")[0])
        if story.upper().endswith(" NA") and len(story) < 60:
            story = ""
        poster = self.cm.ph.getSearchGroups(data, r'<img[^>]+class="mvinfo"[^>]+src="([^"]+)"')[0]
        return story, self._icon(poster, self._iconMeta()), info

    def getLinksForVideo(self, cItem):
        printDBG("M4uStream.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl, _sep, epId = cItem.get("url", "").partition("#")
        epId = epId or cItem.get("ep_id", "")
        sts, data, token = self._pageToken(pageUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        if not token:
            # without the Laravel _token every /ajax POST answers 419 "Page Expired"
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        if epId:
            sts, data, token = self._postWithToken("/ajaxtv", pageUrl, {"idepisode": epId}, token)
            if not sts:
                return []
            token = self.cm.ph.getSearchGroups(data, r"_token:\s*'([^']+)'")[0] or token
        urltab, seen = [], set()
        for serverData, label in re.findall(r'class="singlemv[^"]*"\s+data="([^"]+)"\s*>([^<]*)<', data):
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
                printDBG("M4uStream.getLinksForVideo unsupported server %s [%s]" % (label, src))
                continue
            name = "%s (%s)" % (self.up.getHostName(src).capitalize(), self.cleanHtmlStr(label)) if label.strip() else self.up.getHostName(src)
            urltab.append({"name": name, "url": strwithmeta(src, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("M4uStream.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("M4uStream.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""))
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", "").split("#", 1)[0])
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or _stripColors(cItem.get("desc", ""))
        icon = meta.get("poster") or poster or cItem.get("icon", "")
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
        printDBG("M4uStream.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "m4_filter":
            self.listFilter(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "m4_series":
            self.listSeries(self.currItem)
        elif category == "m4_season":
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
        CHostBase.__init__(self, M4uStream(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("m4ustream")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("m4_video", "m4_series", "m4_season")
