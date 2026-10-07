# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - new host for goojara.to (ww1.goojara.to)
#   English movies and TV series. Lists: /watch-movies[-popular|-genre-X|-year-Y|-az-L]?p=N,
#   /watch-series[...] (recent/popular = episodes, genre/year/A-Z = shows), search = POST /xmre.php,
#   seasons = POST /xmre.php s=<season>&t=<show id>. Every page sets a JS cookie (_3chk(name, value));
#   search and the "Direct Links" (/go.php?url=.., 302 to the hoster) need it plus the PHP session cookie.
#   Hosters: Wootly (goojara's own player, resolved here: embed -> POST qdfx -> /grabm -> mp4),
#   dood / luluvdo / ... via urlparser.
#   + watched flag / downloaded flag / name normalisation / sidecar / moviemeta INFO / favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://ww1.goojara.to/"


# /m<id> movie, /t<id> show, /e<id> episode (links come as www.goojara.to or ww1.goojara.to)
ITEM_RE = re.compile(r'^https?://(?:[a-z0-9]+\.)?goojara\.[a-z]+/([mte][A-Za-z0-9]{4,})/?$')


class Goojara(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "season", "episode", "show_id",
                  "series_url", "icon", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "goojara", "cookie": "goojara.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.jsCookies = {}
        self.MENU = [{"category": "gj_sub", "title": _("Movies"), "kind": "movies"},
                     {"category": "gj_sub", "title": _("Series"), "kind": "series"}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("goojara")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            url = str(cItem.get("url", "") or "").strip()
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url if url else ""
            if category == "gj_show":
                return "series:%s" % url if url else ""
            if category == "gj_season":
                showId = str(cItem.get("show_id", "") or "").strip()
                season = str(cItem.get("season", "") or "").strip()
                return "season:%s|%s" % (showId, season) if showId and season else ""
            return ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # http
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        params = dict(self.defaultParams if addParams is None else addParams)
        # what the page's _3chk() does in a browser: send name=value with every request, next to the
        # PHP session cookie from the cookie file. Kept in memory and passed as cookie_items - rewriting
        # the cookie file with cookielib breaks it for pycurl (session cookies get an empty expiry field,
        # which curl rejects, so the session cookie is lost and go.php / xmre.php answer 404 / empty).
        if self.jsCookies:
            cookieItems = dict(params.get("cookie_items", {}))
            cookieItems.update(self.jsCookies)
            params["cookie_items"] = cookieItems
        sts, data = self.cm.getPage(url, params, post_data)
        if sts and data:
            jsCookies = re.findall(r"_3chk\('([0-9a-f]+)','([0-9a-f]+)'\)", data)
            if jsCookies:
                self.jsCookies = dict(jsCookies)
        return sts, data

    def _ajaxParams(self, referer):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Referer": referer, "X-Requested-With": "XMLHttpRequest",
                                 "Content-Type": "application/x-www-form-urlencoded"})
        return params

    def _normUrl(self, url):
        url = self.getFullUrl(url.replace("&amp;", "&"))
        m = ITEM_RE.search(url)
        if m:
            return self.MAIN_URL + m.group(1)
        return url

    def _kindOf(self, url):
        m = ITEM_RE.search(url)
        return m.group(1)[0] if m else ""

    ###################################################
    # naming
    ###################################################
    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year:
            return "%s (%s)" % (title, year)
        return title

    def _episodeTitle(self, sTitle, season, episode, epName=""):
        if IsMediaNamingNormalized():
            title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
        else:
            title = "%s S%s, E%s" % (sTitle, season, episode)
        return "%s - %s" % (title, epName) if epName else title

    ###################################################
    # lists
    ###################################################
    def listSub(self, cItem):
        kind = cItem["kind"]
        base = "watch-%s" % kind
        if kind == "series":
            tab = [{"category": "list_items", "title": _("Newest Episodes"), "url": self.getFullUrl(base)},
                   {"category": "list_items", "title": _("Popular episodes"), "url": self.getFullUrl(base + "-popular")}]
        else:
            tab = [{"category": "list_items", "title": _("Recent"), "url": self.getFullUrl(base)},
                   {"category": "list_items", "title": _("Popular"), "url": self.getFullUrl(base + "-popular")}]
        tab += [{"category": "list_filters", "title": _("Genres"), "url": self.getFullUrl(base + "-genre")},
                {"category": "list_filters", "title": _("Year"), "url": self.getFullUrl(base + "-year")},
                {"category": "list_filters", "title": _("A-Z"), "url": self.getFullUrl(base + "-az")}]
        params = dict(cItem)
        params.pop("title", None)
        self.listsTab(tab, params)

    def listFilters(self, cItem):
        printDBG("Goojara.listFilters |%s|" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'id="sesh"', "</div></div>", False)[1]
        prefix = cItem["url"].rsplit("/", 1)[-1] + "-"
        seen = set()
        for href, title in re.findall(r'<a href="(/%s[^"]+)"[^>]*>([^<]+)</a>' % re.escape(prefix), data):
            url = self.getFullUrl(href)
            title = self.cleanHtmlStr(title)
            if url in seen or not title:
                continue
            seen.add(url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url})
            self.addDir(params)

    def _addEntry(self, cItem, url, title, icon, extra=""):
        # extra: "2026" for movies / shows, "2.2" (season.episode) for episode tiles
        kind = self._kindOf(url)
        params = stripPagerKeys(dict(cItem), ("search_pattern",))
        params.update({"good_for_fav": True, "url": url, "icon": icon, "desc": ""})
        if kind == "m":
            year = extra if re.match(r"^\d{4}$", extra) else ""
            params.update({"category": "gj_movie", "title": self._movieTitle(title, year), "s_title": title,
                           "desc": year, "meta_type": "movie", "meta_title": title, "meta_year": year})
            self.addVideo(params)
        elif kind == "t":
            year = extra if re.match(r"^\d{4}$", extra) else ""
            params.update({"category": "gj_show", "title": title, "s_title": title, "desc": year,
                           "meta_type": "tv", "meta_title": title, "meta_year": year})
            self.addDir(params)
        elif kind == "e":
            m = re.match(r"^(\d+)\.(\d+)$", extra) or re.match(r"^S(\d+), Ep(\d+)$", extra)
            season, episode = m.groups() if m else ("", "")
            vTitle = self._episodeTitle(title, season, episode) if m else title
            params.update({"category": "gj_episode", "title": vTitle, "s_title": title, "season": season, "episode": episode,
                           "meta_type": "tv", "meta_title": title, "meta_year": ""})
            self.addVideo(params)
        else:
            return False
        return True

    def listItems(self, cItem):
        printDBG("Goojara.listItems |%s|" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextPage = self.cm.ph.getSearchGroups(data, r'<a href="([^"]+)"[^>]*>Next &raquo;</a>')[0]
        # /watch-movies and /watch-series start with a "featured" strip - the real list follows id="xbcg"
        pos = data.find('id="xbcg"')
        if pos > 0:
            data = data[pos:]
        pos = data.find('id="pgs"')
        if pos > 0:
            data = data[:pos]
        cnt = 0
        seen = set()
        for href, attrTitle, body in re.findall(r'<a href="([^"]+)" title="([^"]*)">(.*?)</a>', data, re.DOTALL):
            url = self._normUrl(href)
            if url in seen or not ITEM_RE.search(url):
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="mtl">([^<]+)<')[0])
            extra = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'class="hd[^"]*">([^<]+)<')[0])
            if not extra:
                extra = self.cm.ph.getSearchGroups(attrTitle, r'\(([^()]+)\)\s*$')[0]
            if not title:
                title = self.cleanHtmlStr(re.sub(r'\s*\([^()]+\)\s*$', '', attrTitle))
            if not title:
                continue
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(body, r'data-src="([^"]+)"')[0])
            if self._addEntry(cItem, url, title, icon, extra):
                cnt += 1
        # pager "?p=N" (a window of 10 pages, the last page is not shown)
        page = cItem.get("page", 1)
        base = re.sub(r"\?p=\d+$", "", cItem["url"])
        hasNext = bool(cnt and nextPage and self.getFullUrl(nextPage.replace("&amp;", "&")) != cItem["url"])
        addPagingItems(self, cItem, page, hasNext, 0, base + "?p={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Goojara.listSearchResult [%s]" % searchPattern)
        # the live search key changes with every page view: take a fresh one from a list page
        listUrl = self.getFullUrl("watch-movies")
        sts, data = self.getPage(listUrl)
        if not sts:
            return
        key = self.cm.ph.getSearchGroups(data, r'"x=([0-9a-f]+)&q="')[0]
        if not key:
            SetIPTVPlayerLastHostError(_("Search is not available right now."))
            return
        sts, data = self.getPage(self.getFullUrl("xmre.php"), self._ajaxParams(listUrl), {"x": key, "q": searchPattern})
        if not sts:
            return
        # no hits = "No result"; an empty answer = the session cookie was not sent
        cnt = 0
        for item in re.findall(r'<li>(.*?)</li>', data, re.DOTALL):
            url = self._normUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<strong>(.*?)</strong>')[0])
            year = self.cm.ph.getSearchGroups(item, r'</strong>\s*\((\d{4})\)')[0]
            if title and ITEM_RE.search(url) and self._addEntry(cItem, url, title, "", year):
                cnt += 1
        if not cnt:
            SetIPTVPlayerLastHostError(_("No results found for: %s") % searchPattern)

    def listSeasons(self, cItem):
        printDBG("Goojara.listSeasons |%s|" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        info = self._parsePage(data)
        showId = self.cm.ph.getSearchGroups(data, r'id="seon" data-id="(\d+)"')[0]
        seasons = re.findall(r'data-season="(\d+)"', data)
        if not showId or not seasons:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
            return
        sTitle = cItem.get("s_title", cItem["title"])
        for season in sorted(set(seasons), key=int):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "gj_season", "title": "%s - %s %s" % (sTitle, _("Season"), season),
                           "s_title": sTitle, "show_id": showId, "season": season, "series_url": cItem["url"],
                           "url": "%s?s=%s" % (cItem["url"], season), "desc": info["desc"] or cItem.get("desc", ""),
                           "icon": cItem.get("icon", "") or info["poster"]})
            if info["year"] and not params.get("meta_year"):
                params["meta_year"] = info["year"]
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("Goojara.listEpisodes show[%s] season[%s]" % (cItem.get("show_id", ""), cItem.get("season", "")))
        referer = cItem.get("series_url", self.MAIN_URL)
        sts, data = self.getPage(self.getFullUrl("xmre.php"), self._ajaxParams(referer), {"s": cItem["season"], "t": cItem["show_id"]})
        if not sts:
            return
        sTitle = cItem.get("s_title", cItem["title"])
        eps = []
        for item in data.split('<div class="seho">')[1:]:
            episode = self.cm.ph.getSearchGroups(item, r'class="sea">\s*(\d+)')[0]
            href = self.cm.ph.getSearchGroups(item, r'<h1><a href="([^"]+)"')[0]
            if not href or not episode:
                continue
            epName = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<h1><a[^>]+>(.*?)</a>')[0])
            date = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="date">([^<]+)<')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<p>(.*?)</p>')[0])
            eps.append((int(episode), href, epName, date, desc))
        eps.sort(key=lambda x: x[0])
        for episode, href, epName, date, desc in eps:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "gj_episode", "url": self._normUrl(href),
                           "title": self._episodeTitle(sTitle, cItem["season"], episode, epName),
                           "s_title": sTitle, "episode": str(episode),
                           "desc": "[/br]".join([t for t in (date, desc) if t])})
            self.addVideo(params)

    ###################################################
    # title page
    ###################################################
    def _parsePage(self, data):
        info = {"desc": "", "poster": "", "year": "", "imdb": "", "duration": "", "genres": "", "cast": "", "director": ""}
        info["imdb"] = self.cm.ph.getSearchGroups(data, r'data-ubv="(tt\d+)')[0]
        info["poster"] = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, r'class="imrl"><a href="[^"]*"><img src="([^"]+)"')[0])
        h1 = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'class="marl"><h1>(.*?)</h1>')[0])
        info["year"] = self.cm.ph.getSearchGroups(h1, r'\((\d{4})\)')[0]
        fimm = self.cm.ph.getDataBeetwenMarkers(data, '<div class="fimm">', "</div>", False)[1]
        if fimm:
            paras = re.findall(r'<p>(.*?)</p>', fimm, re.DOTALL)
            for p in paras:
                txt = self.cleanHtmlStr(p)
                if txt.startswith("Director:"):
                    info["director"] = txt.split(":", 1)[1].strip()
                elif txt.startswith("Cast:"):
                    info["cast"] = txt.split(":", 1)[1].strip()
                elif not info["desc"]:
                    info["desc"] = txt
        else:
            marl = self.cm.ph.getDataBeetwenMarkers(data, '<div class="marl">', "</div>", False)[1]
            for p in re.findall(r'<p>(.*?)</p>', marl, re.DOTALL):
                txt = self.cleanHtmlStr(p)
                if txt.startswith("Cast:"):
                    info["cast"] = txt.split(":", 1)[1].strip()
                elif not info["desc"]:
                    info["desc"] = txt
        date = self.cm.ph.getDataBeetwenMarkers(data, '<div class="date">', "</div>", False)[1]
        parts = [self.cleanHtmlStr(t) for t in re.split(r'<span class="gh">\|</span>', date)]
        for part in parts:
            if re.match(r"^\d+\s*min$", part):
                info["duration"] = part
            elif re.search(r"[A-Za-z]+ \d{4}$", part) and not info["year"]:
                info["year"] = part[-4:]
            elif part and not re.search(r"\d", part):
                info["genres"] = part
        return info

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Goojara.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        sidecarTxt = self._parsePage(data)["desc"]
        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'id="drl"', "</div>", False)[1]
        links = []
        counts = {}
        for href, label, quality in re.findall(r'<a class="bcg" href="([^"]+)">([^<]*)<span>([^<]*)</span>', tmp):
            label = self.cleanHtmlStr(label)
            quality = self.cleanHtmlStr(quality)
            counts[label.lower()] = counts.get(label.lower(), 0) + 1
            name = "%s %s" % (label, quality) if quality else label
            if counts[label.lower()] > 1:
                name += " #%d" % counts[label.lower()]
            url = strwithmeta(self.getFullUrl(href.replace("&amp;", "&")), {"Referer": pageUrl, "goojara_page": pageUrl})
            # Wootly (direct mp4 from goojara's own player) first, its AV1 encodes (most boxes can't decode them) last
            if "av1" in label.lower():
                order = 2
            else:
                order = 0 if label.lower() == "wootly" else 1
            links.append((order, {"name": name, "url": url, "need_resolve": 1}))
        links.sort(key=lambda x: x[0])
        urltab = [x[1] for x in links]
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def _resolveGoLink(self, videoUrl):
        # /go.php answers 302 -> hoster only with the PHP session cookie AND the JS cookie, else 404.
        # The redirect is not followed (no request to the hoster here): the target is the Location header.
        pageUrl = videoUrl.meta.get("goojara_page", "") if isinstance(videoUrl, strwithmeta) else ""
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"]["Referer"] = pageUrl or self.MAIN_URL
        params["no_redirection"] = True
        for attempt in (0, 1):
            if attempt or not self.jsCookies:
                # no / stale JS cookie (e.g. reopened from favourites, session expired): load the title page again
                if not pageUrl:
                    break
                self.getPage(pageUrl)
            self.getPage(str(videoUrl), params)
            target = self.cm.meta.get("location", "")
            if target:
                return self.getFullUrl(target)
            if not self.jsCookies:
                break
        return ""

    def _resolveWootly(self, url):
        printDBG("Goojara._resolveWootly [%s]" % url)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"]["Referer"] = self.MAIN_URL
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return []
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<title>([^<]+)</title>')[0])
        embed = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0]
        if not embed:
            return []
        params["header"]["Referer"] = url
        sts, data = self.cm.getPage(embed, params)
        if not sts:
            return []
        params["header"]["Referer"] = embed
        if 'name="qdfx"' in data:
            sts, data = self.cm.getPage(embed, params, {"qdfx": "1"})
            if not sts:
                return []
        vd = self.cm.ph.getSearchGroups(data, r'''var vd="([^"]+)"''')[0]
        tk = self.cm.ph.getSearchGroups(data, r'''tk="([^"]+)"''')[0]
        if not vd or not tk:
            return []
        sts, src = self.cm.getPage(self.cm.getBaseUrl(embed) + "grabm?t=%s&id=%s" % (tk, vd), params)
        src = (src or "").strip()
        if not sts or not self.cm.isValidUrl(src):
            return []
        # /source?.. answers with a 302 to the (signed, short-lived) mp4 on the CDN - the players follow it
        quality = self.cm.ph.getSearchGroups(title, r'[.\s](\d{3,4}p)[.\s]')[0]
        name = "Wootly %s" % quality if quality else "Wootly"
        return [{"name": name, "url": strwithmeta(src, {"User-Agent": self.HEADER["User-Agent"], "Referer": "https://web.wootly.ch/"}), "need_resolve": 0}]

    def getVideoLinks(self, videoUrl):
        printDBG("Goojara.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        target = videoUrl
        if "/go.php" in videoUrl:
            target = self._resolveGoLink(videoUrl)
            if not target:
                SetIPTVPlayerLastHostError(_("The link could not be resolved."))
                return []
        if "wootly." in target:
            links = self._resolveWootly(target)
        else:
            links = self.up.getVideoLinkExt(target)
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Goojara.getArticleContent [%s]" % cItem.get("url", ""))
        mediaType = cItem.get("meta_type", "")
        pageUrl = cItem.get("series_url") or cItem.get("url", "")
        info = {"desc": "", "poster": "", "year": "", "imdb": "", "duration": "", "genres": "", "cast": "", "director": ""}
        if self.cm.isValidUrl(pageUrl):
            sts, data = self.getPage(pageUrl)
            if sts:
                info = self._parsePage(data)
        meta = {}
        try:
            if info["imdb"]:
                meta = getMetaByImdbId(mediaType, info["imdb"])
            if not meta:
                meta = getMeta(mediaType, cItem.get("meta_title", ""), cItem.get("meta_year", "") or info["year"])
        except Exception:
            printExc()
            meta = {}
        otherInfo = dict(meta.get("info", {}) or {})
        for key in ("year", "duration", "genres", "director"):
            if info[key]:
                otherInfo.setdefault(key, info[key])
        if info["cast"]:
            otherInfo.setdefault("actors", info["cast"])
        text = meta.get("plot", "") or info["desc"] or cItem.get("desc", "")
        icon = meta.get("poster", "") or info["poster"] or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text,
                 "images": [{"title": "", "url": icon}] if icon else [],
                 "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("meta_type"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Goojara.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "gj_sub":
            self.listSub(self.currItem)
        elif category == "list_filters":
            self.listFilters(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "gj_show":
            self.listSeasons(self.currItem)
        elif category == "gj_season":
            self.listEpisodes(self.currItem)
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
        CHostBase.__init__(self, Goojara(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("goojara")

    def withArticleContent(self, cItem):
        return bool(cItem.get("meta_type"))
