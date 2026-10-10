# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 04.09.2025 - filmehd.net
# 09.10.2026 - rewrite for filmehd.to (filmehd.net is gone; backup domain filmehd.app), DooPlay theme:
#   - lists: Movies / Series / Top IMDb / Most viewed / genres / years / countries / search with First / Jump /
#     Next page and the last page from the pager ("Page x of y")
#   - movies are video rows, a series season (the site has one page per season) lists its episodes; episodes get
#     their own url (season page + "#e<episode>") for the downloaded marker / watched key
#   - links: the cdn.filmehd.to player pages redirect to the hoster (Filesun = vidmoly white-label embedsun.cc,
#     VOE, Doodstream) - resolved through urlparser; the trailer is not offered as a link
#   - watched flag (season -> episode), favourites reopen without state (old filmehd.net "<slug>.html" rows are
#     looked up through the site search - those pages are gone), "Title (Year)" / "Show - SxxExx" names, sidecar
#     on the links, INFO via moviemeta merged with the site's fields, default user agent, getPageCFProtection
# 10.10.2026 - titles with an empty "()" of the site keep their year, the "()" is also dropped from the raw titles
#   (name normalisation off)
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://filmehd.to/"


# favourites / history of the old version carry filmehd.net urls; their "<slug>.html" pages are gone on filmehd.to
# (404) - they are looked up through the site search (_currentUrl)
OLD_DOMAIN_RE = re.compile(r"^https?://(?:www\.)?filmehd\.(?:net|app|to)/", re.I)
OLD_SLUG_RE = re.compile(r"^https?://[^/]+/([^/?#]+)\.html$")
SEASON_RE = re.compile(r"^(.*?)\s+(?:Sezonul|Season)\s+(\d+)\s*$", re.I)
MOVIE_RE = re.compile(r"^(.*?)\s*\(((?:19|20)\d\d)\)\s*$")
# the site writes some titles with an empty pair of brackets at the end ("Doll of Deceit (2026) ()")
EMPTY_BRACKETS_RE = re.compile(r"\s*\(\s*\)\s*$")
# Filesun: a vidmoly white-label (embedsun.cc/embed-<id>.html) - vidmoly.biz serves the same file ids
VIDMOLY_LABEL_RE = re.compile(r"^https?://[^/]+/embed-([A-Za-z0-9]{12})\.html")


class FilmeHD(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "filmehd.net", "cookie": "filmehd.net.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "wp-content/uploads/2020/01/filmehd.png"
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("filme/")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("seriale/")},
                     {"category": "list_items", "title": _("Top IMDb"), "url": self.getFullUrl("top-imdb/")},
                     {"category": "list_items", "title": _("Most viewed"), "url": self.getFullUrl("cele-mai-vizionate/")},
                     {"category": "list_filters", "title": _("Genres"), "f_type": "gen"},
                     {"category": "list_filters", "title": _("Year"), "f_type": "anul"},
                     {"category": "list_filters", "title": _("Countries"), "f_type": "country"}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("filmehdnet")
        self.wfInitFolderCache()
        self.oldUrlCache = {}

    def fixUrl(self, url):
        return OLD_DOMAIN_RE.sub(self.MAIN_URL, str(url or ""))

    @staticmethod
    def _tokens(text):
        # "Freddy's" -> "freddys" as in the slug
        return re.sub(r"[^a-z0-9]+", " ", text.lower().replace("'", "")).split()

    def _currentUrl(self, url):
        # the page of an old filmehd.net favourite: "a-man-apart-2003-filme-online.html" -> /filme/a-man-apart-2003/,
        # "19-2-2014-serial-tv-sezonul-1.html" -> /seriale/19-2-sezonul-1/ (found through the search: the new slugs
        # drop the Romanian title part); "" when the site has no such title any more
        url = self.fixUrl(url)
        match = OLD_SLUG_RE.match(url)
        if not match:
            return url
        if url in self.oldUrlCache:
            return self.oldUrlCache[url]
        slug = match.group(1).lower()
        season = self.cm.ph.getSearchGroups(slug, r"-sezonul-(\d+)")[0]
        name = re.split(r"-(?:serial-tv|filme?-online|sezonul-\d)", slug)[0]
        years = list(re.finditer(r"-((?:19|20)\d\d)(?=-|$)", name))
        year = years[-1].group(1) if years else ""
        if years:
            name = name[:years[-1].start()]
        words = name.split("-")
        found = ""
        # WordPress needs every word in the title: the full name, then without the Romanian title part
        # ("12 years a slave 12 ani de sclavie" -> "12 years a slave"), then the first two words; a short name
        # may hold a hyphen of the title itself ("19-2")
        patterns = []
        for count in (len(words), max(2, (len(words) + 1) // 2), 2):
            pattern = " ".join(words[:count])
            if pattern not in patterns:
                patterns.append(pattern)
        if len(words) <= 3:
            patterns.append('"%s"' % name)
        for pattern in patterns:
            found = self._bestRow(self._searchRows(pattern), words, season, year)
            if found:
                break
        printDBG("FilmeHD._currentUrl %s -> %s" % (url, found))
        self.oldUrlCache[url] = found
        return found

    def _bestRow(self, rows, words, season, year):
        # the search row with the same season / year that shares the most words with the old slug
        best, bestScore = "", 0
        for rowUrl, rowTitle in rows:
            rowName, rowSeason, rowYear = self._splitTitle(rowTitle)
            if season != rowSeason or (year and rowYear and year != rowYear):
                continue
            rowTokens = self._tokens(rowName)
            score = len(set(rowTokens) & set(words))
            if score * 2 >= len(rowTokens) and score > bestScore:
                best, bestScore = rowUrl, score
        return best

    def _searchRows(self, pattern):
        sts, data = self.getPage("%s?s=%s" % (self.MAIN_URL, urllib_quote_plus(pattern)))
        rows = []
        if sts:
            for block in data.split("<article")[1:]:
                url = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)"')[0]
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0])
                if url and title:
                    rows.append((self.fixUrl(self.getFullUrl(url)), title))
        return rows

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(self.fixUrl(baseUrl).split("#", 1)[0], addParams, post_data)

    def getFullIconUrl(self, url, currUrl=None):
        # covers on the site itself sit behind the same Cloudflare as the pages (TMDb covers do not)
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        if not url.startswith(self.MAIN_URL):
            return url
        meta = {"Referer": self.MAIN_URL, "User-Agent": self.USER_AGENT}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.USER_AGENT, "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

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
            category = cItem.get("category", "")
            if category == "list_episodes" or (category == "explore_item" and self._isSeriesUrl(url)):
                return "season:%s" % url
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _isSeriesUrl(url):
        return "/seriale/" in url or "sezonul" in url.lower()

    @staticmethod
    def _pageUrlTpl(url):
        # the list url with "{page}": .../filme/page/{page}/ - the search: /page/{page}/?s=..
        base, sep, query = url.partition("?")
        base = re.sub(r"page/\d+/?$", "", base)
        if not base.endswith("/"):
            base += "/"
        tpl = (base + "page/{page}/").replace("{", "{{").replace("}", "}}").replace("{{page}}", "{page}")
        return tpl + (sep + query).replace("{", "{{").replace("}", "}}")

    @staticmethod
    def _splitTitle(title):
        # (show / film title, season, year) of "Below Sezonul 1" / "Fight Club (1999)"
        title = EMPTY_BRACKETS_RE.sub("", title)
        m = SEASON_RE.match(title)
        if m:
            return m.group(1).strip(), m.group(2), ""
        m = MOVIE_RE.match(title)
        if m:
            return m.group(1).strip(), "", m.group(2)
        return title, "", ""

    def _seasonTitle(self, sTitle, season, rawTitle):
        if IsMediaNamingNormalized() and season:
            return "%s - %s" % (sTitle, formatSxxExx(season))
        return rawTitle

    def _servers(self, data):
        # [(server name, episode number or "", player url)] of a movie / season page:
        # movies: one "SERVER n" block per server (name in the option), seasons: "SERVER n - Name" with
        # one option per episode
        ret = []
        for block in data.split('<div class="allservers">')[1:]:
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'class="lables">(.*?)</label>')[0])
            serverName = label.split(" - ", 1)[1].strip() if " - " in label else ""
            for url, text in re.findall(r'data-vs="([^"]+)"[^>]*>.*?class="servers">([^<]*)<', block, re.S):
                text = self.cleanHtmlStr(text)
                url = url.replace("&amp;", "&")
                if "youtube" in url or "trailer" in label.lower():
                    continue
                if serverName:
                    ret.append((serverName, text if text.isdigit() else "", url))
                else:
                    ret.append((text or label, "", url))
        return ret

    def _episodes(self, data):
        episodes = []
        for _name, episode, _url in self._servers(data):
            if episode and episode not in episodes:
                episodes.append(episode)
        return sorted(episodes, key=int)

    def _siteInfo(self, data):
        # the fields of a movie / season page: (info dict, plot, year, imdb id, title, icon)
        info = {}
        head = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "sheader"), ("<div", ">", "clear"), False)[1] or data
        # "Țară" / "Tara" (py2: lower() leaves the "Ț" bytes alone)
        keys = (("gen", "genres"), ("actori", "actors"), ("director", "director"), ("creator", "creator"), ("ț", "country"), ("Ț", "country"),
                ("tara", "country"), ("dat", "released"), ("calitate", "quality"))
        for label, value in re.findall(r'<div class="dt">([^<]*)</div>\s*<div class="dd[^"]*">(.*?)</div>', head, re.S):
            label = self.cleanHtmlStr(label).lower()
            value = self.cleanHtmlStr(value).strip(" ,")
            for prefix, key in keys:
                if value and label.startswith(prefix) and key not in info:
                    info[key] = value
                    break
        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r'class="span-clock">(.*?)</span>')[0])
        if duration:
            info["duration"] = duration
        year = self.cm.ph.getSearchGroups(info.get("released", ""), r"((?:19|20)\d\d)")[0]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r"<h1[^>]*>(.*?)</h1>")[0])
        title = EMPTY_BRACKETS_RE.sub("", re.sub(r"\s+-\s+Online Subtitrat.*$", "", title, flags=re.I))
        if not year:
            year = self._splitTitle(title)[2]
        if year:
            info["year"] = year
        plot = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r'class="wp-content"[^>]*>(.*?)</div>', 1, True)[0])
        imdb = self.cm.ph.getSearchGroups(data, r'data-title="(tt\d{6,9})"')[0]
        icon = self.cm.ph.getSearchGroups(head, r'class="poster">\s*<img[^>]+src="([^"]+)"')[0]
        return info, plot, year, imdb, title, self.getFullIconUrl(icon) if icon else ""

    ###################################################
    # lists
    ###################################################
    def listFilters(self, cItem):
        printDBG("FilmeHD.listFilters |%s|" % cItem)
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        fType = cItem.get("f_type", "gen")
        rows, seen = [], set()
        for url, title in re.findall(r'<a href="(https?://[^/"]+/%s/[^"]+)">([^<]+)</a>' % re.escape(fType), data):
            url = self.fixUrl(url)
            if url in seen:
                continue
            seen.add(url)
            rows.append((url, self.cleanHtmlStr(title)))
        if fType == "anul":
            rows.sort(key=lambda row: row[1], reverse=True)
        for url, title in rows:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("FilmeHD.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        pageUrlTpl = self._pageUrlTpl(cItem["url"])
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else cItem["url"])
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for block in data.split("<article")[1:]:
            block = block.split("</article>", 1)[0]
            url = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)"')[0]
            if not url or url in seen:
                continue
            seen.add(url)
            url = self.fixUrl(self.getFullUrl(url))
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'alt="([^"]+)"')[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"<h3[^>]*>(.*?)</h3>")[0])
            title = EMPTY_BRACKETS_RE.sub("", title)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(block, r'<img[^>]+src="([^"]+)"')[0])
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'class="quality">([^<]*)<')[0])
            eps = self.cm.ph.getSearchGroups(block, r'class="ep-number">(\d+)<')[0]
            sTitle, season, year = self._splitTitle(title)
            params = stripPagerKeys(dict(cItem))
            params.pop("f_type", None)
            params.update({"good_for_fav": True, "url": url, "icon": icon, "s_title": sTitle, "s_year": year})
            if self._isSeriesUrl(url):
                params.update({"category": "list_episodes", "title": self._seasonTitle(sTitle, season, title), "season": season,
                               "meta_type": "tv", "desc": "%s: %s" % (_("Episodes"), eps) if eps else ""})
                self.addDir(params)
            else:
                dispTitle = ("%s (%s)" % (sTitle, year) if year else sTitle) if normalize else title
                desc = " | ".join("%s: %s" % (label, value) for label, value in ((_("Year"), year), (_("Quality"), quality)) if value)
                params.update({"category": "video", "title": dispTitle, "meta_type": "movie", "desc": desc})
                self.addVideo(params)
        pager = self.cm.ph.getSearchGroups(data, r'<div class="pagination"><span>[^<]*?(\d+)\D+(\d+)</span>', 2)
        lastPage = int(pager[1]) if pager[1].isdigit() else page
        addPagingItems(self, cItem, page, page < lastPage, lastPage, pageUrlTpl)

    def listEpisodes(self, cItem, data=None):
        printDBG("FilmeHD.listEpisodes |%s|" % cItem)
        url = self.fixUrl(cItem["url"]).split("#", 1)[0]
        if data is None:
            sts, data = self.getPage(url)
            if not sts:
                return
        _info, plot, year, _imdb, pageTitle, icon = self._siteInfo(data)
        pageSTitle, season, _year = self._splitTitle(pageTitle)
        # favourites of the old version: no show name / season fields - the ones of the page
        sTitle = (cItem.get("s_title", "") if cItem.get("season") else "") or pageSTitle or cItem.get("title", "")
        season = str(cItem.get("season", "") or season or "")
        episodes = self._episodes(data)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        normalize = IsMediaNamingNormalized()
        rawTitle = cItem.get("title", "") if cItem.get("category") == "list_episodes" else pageTitle
        for episode in episodes:
            if normalize and season:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s" % (rawTitle or sTitle, _("Episode"), episode)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "s_year": year, "url": "%s#e%s" % (url, episode),
                           "season": season, "episode": episode, "meta_type": "tv", "icon": cItem.get("icon", "") or icon, "desc": plot})
            self.addVideo(params)

    def exploreItem(self, cItem):
        # favourites of the old version (a movie / season folder with the trailer and the film inside)
        printDBG("FilmeHD.exploreItem |%s|" % cItem)
        url = self._currentUrl(cItem["url"])
        if not url:
            SetIPTVPlayerLastHostError(_("Page not found - please check the address."))
            return
        sts, data = self.getPage(url)
        if not sts:
            return
        canonical = self.cm.ph.getSearchGroups(data, r'<link rel="canonical" href="([^"]+)"')[0]
        url = self.fixUrl(canonical) if canonical else url
        if self._isSeriesUrl(url) or self._episodes(data):
            self.listEpisodes(dict(cItem, url=url, category="list_episodes", season="", s_title=""), data)
            return
        _info, plot, year, _imdb, pageTitle, icon = self._siteInfo(data)
        sTitle = self._splitTitle(pageTitle)[0] or cItem.get("title", "")
        title = ("%s (%s)" % (sTitle, year) if year else sTitle) if IsMediaNamingNormalized() else (pageTitle or cItem.get("title", ""))
        params = dict(cItem)
        params.update({"good_for_fav": True, "category": "video", "title": title, "url": url, "s_title": sTitle, "s_year": year, "meta_type": "movie",
                       "icon": cItem.get("icon", "") or icon, "desc": plot or cItem.get("desc", "")})
        self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmeHD.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": "%s?s=%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("FilmeHD.getLinksForVideo [%s]" % cItem)
        url = self.fixUrl(cItem.get("url", ""))
        pageUrl = url.split("#", 1)[0]
        episode = str(cItem.get("episode", "") or "") or self.cm.ph.getSearchGroups(url, r"#e(\d+)$")[0]
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        urltab = []
        for name, number, playerUrl in self._servers(data):
            if number != episode:
                continue
            urltab.append({"name": name, "url": strwithmeta(self.getFullUrl(playerUrl), {"Referer": pageUrl}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", "")))

    def getVideoLinks(self, videoUrl):
        printDBG("FilmeHD.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        url = videoUrl
        if "filmehd." in self.up.getDomain(videoUrl):
            # cdn.filmehd.to/.../iframe/<id> answers with a redirect to the hoster
            params = dict(self.defaultParams)
            params.update({"header": dict(self.HEADER, Referer=videoUrl.meta.get("Referer", self.MAIN_URL)), "no_redirection": True})
            sts, data = self.cm.getPage(videoUrl, params)
            url = self.cm.meta.get("location", "") or ""
            if not url and sts:
                url = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+?src="([^"]+)"', 1, True)[0]
            url = "https:" + url if url.startswith("//") else url
            if not self.cm.isValidUrl(url):
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
                return []
        m = VIDMOLY_LABEL_RE.match(url)
        if m and 1 != self.up.checkHostSupport(url):
            url = "https://vidmoly.biz/embed-%s.html" % m.group(1)
        url = strwithmeta(url, {"Referer": self.MAIN_URL})
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("FilmeHD.getArticleContent [%s]" % cItem)
        info, plot, year, imdb, pageTitle, icon = {}, "", cItem.get("s_year", ""), "", "", ""
        url = self._currentUrl(cItem.get("url", ""))
        sts, data = self.getPage(url) if url else (False, "")
        if sts:
            info, plot, siteYear, imdb, pageTitle, icon = self._siteInfo(data)
            year = siteYear or year
        url = url or self.fixUrl(cItem.get("url", ""))
        mediaType = cItem.get("meta_type", "") or ("tv" if self._isSeriesUrl(url) else "movie")
        title = cItem.get("s_title", "") or self._splitTitle(pageTitle)[0] or self._splitTitle(cItem.get("title", ""))[0]
        meta = {}
        try:
            if imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and title:
                meta = getMeta(mediaType, title, year)
        except Exception:
            printExc()
        metaInfo = meta.get("info", {})
        if metaInfo.get("director") or metaInfo.get("directors"):
            # the site's "Director" field lists the whole crew of a movie
            info.pop("director", None)
        for key, value in metaInfo.items():
            if value and (key not in info or key in ("genres", "actors", "director", "duration")):
                info[key] = value
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or icon or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", "") or pageTitle, "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        if self.currItem.get("url"):
            self.currItem["url"] = self.fixUrl(self.currItem["url"])
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService start\nhandleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_filters":
            self.listFilters(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "explore_item":
            self.exploreItem(self.currItem)
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
        CHostBase.__init__(self, FilmeHD(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("filmehdnet")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_episodes", "explore_item")
