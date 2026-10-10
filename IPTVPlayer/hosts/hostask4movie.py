# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.10.2026 - new host for ask4movie.life (English films, a few series seasons; WordPress behind Cloudflare)
#   - Latest / Genres / Year (categories of the site, with the number of titles) / Search, First / Jump / Next
#     page with the last page from the pager
#   - links: the player iframe of the post. netembed.xyz (and the older vidsrc.* / vsembed / moviesapi embeds of
#     the same network) is opened as netembed.xyz/embed/<IMDb or TMDb id>/ (urlparser parserVIDSRC); other
#     hosters only when urlparser knows them. Most posts of 2024/2025 embed 02tvseries.cyou, a parked domain
#     now - for them (and every post without a netembed id) the IMDb id of "Title (Year)" is looked up in the
#     IMDb suggestion API and played through netembed.
#   - series: a "<Show> Season N" post lists its episodes (episode list of the netembed / vidsrc API), a post
#     without a season lists the seasons first; episodes keyed on post url + "#sXeY"
#   - watched flag (series -> season -> episode), favourites reopen without state, downloaded marker on the
#     post / episode url, "Title (Year)" / "Show - SxxExx" names, sidecar on the links
#   - INFO via moviemeta (IMDb id where the post has one) merged with the site's fields
# 10.10.2026 - review: IMDb suggestion titles with accents on py2, episodes without the season's "Episodes: N" text
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://ask4movie.life/"


NETEMBED_URL = "https://netembed.xyz/embed/"
# the embeds of the vidsrc network all play the same streams by IMDb / TMDb id
VIDSRC_RE = re.compile(r"//(?:[^/]+\.)?(?:netembed|vidsrc[\w-]*|vsembed|moviesapi)\.[a-z]+/", re.I)
# player domains the site used before that are gone (parked)
DEAD_RE = re.compile(r"//(?:[^/]+\.)?02tvseries\.", re.I)
# episode list of a series: the API behind the netembed / vidsrc player (no token needed for it)
VIDSRC_META_API = "https://data.vidsrc.sh/api.php?type=tv&%s=%s"
VIDSRC_META_REFERER = "https://cloudorchestranova.com/"
IMDB_SUGGEST_URL = "https://v3.sg.media-imdb.com/suggestion/%s/%s.json"
POSTS_PER_PAGE = 12


class Ask4Movie(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Ask4Movie", "cookie": "Ask4Movie.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("wp-content/uploads/2024/05/cropped-ask4movie-270x270.png")
        self.MENU = [{"category": "list_items", "title": _("Latest"), "url": self.MAIN_URL, "page_tpl": self.MAIN_URL + "page/{page}/"},
                     {"category": "list_cats", "title": _("Genres"), "cat_kind": "genre"},
                     {"category": "list_cats", "title": _("Year"), "cat_kind": "year"}] + self.searchItems()
        self.cacheCats = []
        self.cacheImdb = {}
        self.watchedHelper = IPTVWatchedHelper("ask4movie")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl.split("#", 1)[0], addParams, post_data)

    def getFullIconUrl(self, url, currUrl=None):
        # the covers sit behind the same Cloudflare check as the pages: cf_clearance + the UA that passed it
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith("http"):
            return url
        meta = {"Referer": self.MAIN_URL, "User-Agent": self.USER_AGENT}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.USER_AGENT, "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    def _getJson(self, url, header=None):
        sts, data = self.cm.getPage(url, {"header": header or self.HEADER})
        if not sts:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG("Ask4Movie: no JSON from %s" % url)
        return None

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if not url:
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % url
            if cItem.get("category", "") == "list_episodes":
                return "%s:%s" % ("season" if "#s" in url else "series", url)
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _splitYear(title):
        # "Verity 2026" / "Boneyard (2024)" -> ("Verity", "2026")
        match = re.match(r"^(.+?)\s*\(?((?:19|20)\d\d)\)?\s*$", title)
        return (match.group(1).strip(), match.group(2)) if match else (title.strip(), "")

    @staticmethod
    def _splitSeason(title):
        # "From Season 4" -> ("From", "4"); no season -> (title, "")
        match = re.match(r"^(.*?)\s*[-:]?\s*\bSeason\s+(\d+)\b", title, re.I)
        return (match.group(1).strip(), match.group(2)) if match else (title, "")

    def _pager(self, data, page):
        # (hasNext, lastPage) from <div class="nav-links">
        pager = self.cm.ph.getDataBeetwenMarkers(data, 'class="nav-links"', "</div>", False)[1]
        if not pager:
            return False, 0
        nums = [int(n) for n in re.findall(r'class="page-numbers[^"]*"[^>]*>\s*(\d+)\s*<', pager)]
        lastPage = max(nums + [page])
        hasNext = 'class="next page-numbers' in pager
        return hasNext, lastPage

    def _iframes(self, data):
        # player urls of the post (lazy loaded: data-litespeed-src, src="about:blank")
        content = self.cm.ph.getDataBeetwenMarkers(data, 'class="post-content"', 'class="shareit', False)[1] or data
        urls = []
        for tag in re.findall(r"<iframe[^>]+>", content, re.I):
            for attr in ("data-litespeed-src", "data-lazy-src", "data-src", "src"):
                url = self.cm.ph.getSearchGroups(tag, r'\s%s="([^"]+)"' % attr)[0].replace("&#038;", "&").replace("&amp;", "&")
                if url.startswith("//"):
                    url = "https:" + url
                if self.cm.isValidUrl(url):
                    if url not in urls:
                        urls.append(url)
                    break
        return urls

    @staticmethod
    def _embedId(url):
        # (kind, id, season, episode) of a vidsrc network embed, kind "" when it has no id
        query = dict(re.findall(r"[?&](imdb|tmdb|season|episode)=([^&#]+)", url))
        kind = "tv" if re.search(r"/(?:embed/)?tv\b", url) else "movie"
        mid = query.get("imdb") or query.get("tmdb") or ""
        season, episode = query.get("season", ""), query.get("episode", "")
        if not mid:
            match = re.search(r"/(?:embed/)?(?:movie/|tv/)?(tt\d+|\d+)(?:/(\d+)(?:[/-](\d+))?)?/?(?:[?#]|$)", url)
            if not match:
                return "", "", "", ""
            mid, season, episode = match.group(1), match.group(2) or "", match.group(3) or ""
        return kind, mid, season, episode

    @staticmethod
    def _netembedUrl(mid, season="", episode=""):
        if season and episode:
            return "%stv/%s/%s/%s/" % (NETEMBED_URL, mid, season, episode)
        return "%s%s/" % (NETEMBED_URL, mid)

    def _imdbId(self, title, year, kind="movie"):
        # IMDb id of "Title (Year)" from the IMDb suggestion API (keyless)
        key = "%s|%s|%s" % (kind, title.lower(), year)
        if key in self.cacheImdb:
            return self.cacheImdb[key]
        query = re.sub(r"[^\w\s]", " ", title.lower(), flags=re.U)
        query = re.sub(r"\s+", " ", query).strip()
        mid = ""
        data = self._getJson(IMDB_SUGGEST_URL % (urllib_quote(query[:1] or "x"), urllib_quote(query))) if query else None
        kinds = ("movie", "tvMovie", "video", "short") if kind == "movie" else ("tvSeries", "tvMiniSeries")
        best = -1
        for row in (data or {}).get("d", []) if isinstance(data, dict) else []:
            # ensure_str: the JSON strings are unicode on py2 (str() fails on non-ASCII titles)
            if not isinstance(row, dict) or not ensure_str(row.get("id") or "").startswith("tt") or row.get("qid") not in kinds:
                continue
            score = 0
            if re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", ensure_str(row.get("l") or "").lower(), flags=re.U)).strip() == query:
                score += 2
            try:
                diff = abs(int(row.get("y") or 0) - int(year)) if year else 9
            except ValueError:
                diff = 9
            if diff == 0:
                score += 2
            elif diff == 1:
                score += 1
            elif year:
                continue  # another film of the same name
            if score > best:
                mid, best = ensure_str(row["id"]), score
        self.cacheImdb[key] = mid
        return mid

    def _seriesData(self, cItem):
        # (tv id, season of the post, {season: [episodes]}) of a series post
        mid, season = cItem.get("tv_id", ""), cItem.get("post_season", "")
        if not mid:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return "", "", {}
            for url in self._iframes(data):
                if VIDSRC_RE.search(url):
                    _kind, mid, season, _episode = self._embedId(url)
                    if mid:
                        break
            if not mid:
                show = self._splitSeason(cItem.get("s_title", "") or cItem.get("title", ""))[0]
                mid = self._imdbId(show, "", "tv")
        if not mid:
            return "", "", {}
        hdr = dict(self.HEADER)
        hdr.update({"Referer": VIDSRC_META_REFERER, "Accept": "application/json"})
        js = self._getJson(VIDSRC_META_API % ("imdb" if mid.startswith("tt") else "tmdb", mid), hdr)
        eps = ((js or {}).get("data") or {}).get("eps") if isinstance(js, dict) else {}
        episodes = {}
        if isinstance(eps, dict):
            for snum, nums in eps.items():
                if str(snum).isdigit() and isinstance(nums, list):
                    episodes[str(int(snum))] = sorted({str(int(n)) for n in nums if str(n).isdigit()}, key=int)
        return mid, season or cItem.get("s_season", ""), episodes

    ###################################################
    # lists
    ###################################################
    def listCats(self, cItem):
        printDBG("Ask4Movie.listCats |%s|" % cItem)
        if not self.cacheCats:
            js = self._getJson(self.getFullUrl("wp-json/wp/v2/categories?per_page=100&_fields=name,slug,count,link"))
            for row in js if isinstance(js, list) else []:
                if isinstance(row, dict) and row.get("count") and row.get("link"):
                    self.cacheCats.append({"title": self.cleanHtmlStr(row.get("name", "")), "url": row["link"], "slug": row.get("slug", ""), "count": int(row["count"])})
            if not self.cacheCats:
                # the menu of the page when the JSON API is not answering
                sts, data = self.getPage(self.MAIN_URL)
                for url, title in re.findall(r'href="([^"]+/category/([^"/]+)/)"', data if sts else ""):
                    if url not in [c["url"] for c in self.cacheCats]:
                        self.cacheCats.append({"title": title.replace("-", " ").title(), "url": url, "slug": title, "count": 0})
        wantYear = cItem.get("cat_kind") == "year"
        cats = [c for c in self.cacheCats if bool(re.match(r"^(?:19|20)\d\d-", c["slug"])) == wantYear]
        cats.sort(key=lambda c: c["slug"], reverse=wantYear)
        for cat in cats:
            url = self.getFullUrl(cat["url"])
            if not url.endswith("/"):
                url += "/"
            params = {"name": "category", "category": "list_items", "good_for_fav": True, "title": cat["title"], "url": url, "page_tpl": url + "page/{page}/"}
            if cat["count"]:
                params["desc"] = "%s: %d" % (_("Movies"), cat["count"])
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("Ask4Movie.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        hasNext, lastPage = self._pager(data, page)
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, "<article", "</article>"):
            url = self.cm.ph.getSearchGroups(item, r'<h2[^>]*>\s*<a href="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            url = self.getFullUrl(url)
            if not url or url in seen or "/category/" in url:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h2[^>]*>\s*<a[^>]*>(.*?)</a>')[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not label:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+src="(http[^"]+)"')[0]
            sTitle, year = self._splitYear(label)
            show, season = self._splitSeason(sTitle)
            params = stripPagerKeys(dict(cItem), ("page_tpl", "cat_kind"))
            params.update({"good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon), "desc": "", "s_year": year, "meta_year": year})
            if season:
                title = label
                if normalize:
                    title = "%s - %s" % (show, formatSxxExx(season))
                params.update({"category": "list_episodes", "title": title, "s_title": show, "s_season": season, "meta_type": "tv", "meta_title": show})
                self.addDir(params)
            else:
                title = "%s (%s)" % (sTitle, year) if (normalize and year) else label
                params.update({"category": "video", "title": title, "s_title": sTitle, "meta_type": "movie", "meta_title": sTitle})
                self.addVideo(params)
        tpl = cItem.get("page_tpl", "")
        if tpl:
            addPagingItems(self, cItem, page, hasNext, lastPage, tpl)

    def listEpisodes(self, cItem):
        printDBG("Ask4Movie.listEpisodes |%s|" % cItem)
        postUrl = cItem["url"].split("#", 1)[0]
        mid, postSeason, episodes = self._seriesData(cItem)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        normalize = IsMediaNamingNormalized()
        sTitle = cItem.get("s_title", "") or cItem.get("title", "")
        fields = {"tv_id": mid, "post_season": postSeason, "s_title": sTitle}
        season = str(cItem.get("season", "") or "")
        if not season:
            if postSeason in episodes:
                season = postSeason
            elif len(episodes) == 1:
                season = next(iter(episodes))
        if not season:
            for snum in sorted(episodes, key=int):
                params = stripPagerKeys(dict(cItem))
                params.update(fields)
                title = "%s - %s" % (sTitle, formatSxxExx(snum)) if normalize else "%s - %s %s" % (sTitle, _("Season"), snum)
                params.update({"good_for_fav": True, "category": "list_episodes", "title": title, "season": snum, "url": "%s#s%s" % (postUrl, snum),
                               "desc": "%s: %d" % (_("Episodes"), len(episodes[snum]))})
                self.addDir(params)
            return
        for epNum in episodes.get(season, []):
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            title = "%s - %s" % (sTitle, formatSxxExx(season, epNum)) if normalize else "%s - %s %s, %s %s" % (sTitle, _("Season"), season, _("Episode"), epNum)
            # desc: not the season folder's "Episodes: N"
            params.update({"good_for_fav": True, "category": "episode", "title": title, "season": season, "episode": epNum,
                           "url": "%s#s%se%s" % (postUrl, season, epNum), "desc": ""})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Ask4Movie.listSearchResult [%s]" % searchPattern)
        query = urllib_quote_plus(searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": "%s?s=%s" % (self.MAIN_URL, query), "page_tpl": "%spage/{page}/?s=%s" % (self.MAIN_URL, query)})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _addLink(self, urltab, name, url):
        if url in [str(x["url"]) for x in urltab]:
            return
        urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})

    def getLinksForVideo(self, cItem):
        printDBG("Ask4Movie.getLinksForVideo [%s]" % cItem)
        urltab = []
        if cItem.get("category") == "episode":
            mid = cItem.get("tv_id", "")
            if not mid:
                mid = self._seriesData(cItem)[0]
            if mid and cItem.get("season") and cItem.get("episode"):
                self._addLink(urltab, "Netembed", self._netembedUrl(mid, cItem["season"], cItem["episode"]))
        else:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return []
            hasId = False
            for url in self._iframes(data):
                if DEAD_RE.search(url):
                    printDBG("Ask4Movie: dead player skipped [%s]" % url)
                    continue
                if VIDSRC_RE.search(url):
                    kind, mid, season, episode = self._embedId(url)
                    if kind == "tv" and not (season and episode):
                        continue  # a whole series / season: no film to play
                    if mid:
                        hasId = True
                        self._addLink(urltab, "Netembed", self._netembedUrl(mid, season, episode))
                        continue
                if self.up.checkHostSupport(url) == 1:
                    self._addLink(urltab, self.up.getHostName(url).split(".")[0].capitalize(), url)
            if not hasId:
                # player gone or unknown: the same network by the IMDb id of the title
                title = cItem.get("s_title", "") or self._splitYear(cItem.get("title", ""))[0]
                mid = self._imdbId(title, cItem.get("s_year", ""))
                if mid:
                    self._addLink(urltab, "Netembed (IMDb %s)" % mid, self._netembedUrl(mid))
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("Ask4Movie.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # "<strong>Director:</strong> Michael Showalter<br />" ... -> (info dict, plot)
        content = self.cm.ph.getDataBeetwenMarkers(data, 'class="post-content"', 'class="shareit', False)[1]
        info = {}
        for key, label in (("genres", "Genres"), ("directors", "Director"), ("writers", "Writers"), ("cast", "Stars"),
                           ("duration", "Duration"), ("released", "Date"), ("rating", "Rating"), ("quality", "Quality"), ("country", "Country")):
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(content, r"(?s)<strong>\s*%s:\s*</strong>(.*?)(?:<br|</p>)" % label)[0])
            if key == "genres":
                # "2026 Movies | Drama, Mystery and Thriller"
                value = value.split("|")[-1].replace(" and ", ", ").strip()
            if value:
                info[key] = value
        plot = ""
        for par in re.findall(r"(?s)<p[^>]*>(.*?)</p>", content):
            text = self.cleanHtmlStr(par)
            if len(text) > 80 and "<strong>Title:" not in par:
                plot = re.sub(r"\s*Follow Ask4Movies?\s+for more\.?\s*$", "", text, flags=re.I)
                break
        return info, plot

    def getArticleContent(self, cItem):
        printDBG("Ask4Movie.getArticleContent [%s]" % cItem)
        info, plot, imdb = {}, "", ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot = self._siteInfo(data)
            for url in self._iframes(data):
                mid = self._embedId(url)[1] if VIDSRC_RE.search(url) else ""
                if mid.startswith("tt"):
                    imdb = mid
                    break
        mediaType = cItem.get("meta_type", "") or "movie"
        title = cItem.get("meta_title", "") or cItem.get("s_title", "") or cItem.get("title", "")
        year = cItem.get("meta_year", "") or cItem.get("s_year", "")
        if mediaType == "tv":
            # the post of one season: its year, date and rating are the season's
            info.pop("released", None)
            year = ""
            if not imdb and str(cItem.get("tv_id", "")).startswith("tt"):
                imdb = cItem["tv_id"]
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and title:
                meta = getMeta(mediaType, title, year)
        except Exception:
            printExc()
        metaInfo = dict(meta.get("info", {}))
        for key, value in info.items():
            # the services' fields first, the site's fill the gaps (its rating is the IMDb one)
            if key == "rating" and metaInfo.get("imdb_rating"):
                continue
            metaInfo.setdefault(key, value)
        if year and "year" not in metaInfo:
            metaInfo["year"] = year
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": metaInfo}]

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
        elif category == "list_cats":
            self.listCats(self.currItem)
        elif category == "list_episodes":
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
        CHostBase.__init__(self, Ask4Movie(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("ask4movie")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") == "list_episodes"
