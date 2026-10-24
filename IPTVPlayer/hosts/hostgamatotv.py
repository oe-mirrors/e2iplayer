# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host (successor of gamatotv.me)
#   films / series / kids with Greek subtitles (WordPress): movies, series, kids, Top 250, genres, years, search;
#   series -> seasons -> episodes from the "Season N:" lines of the page; links = gtv4.site pages (iframe of
#   a hoster or the site's own MP4); the domain hops: own domain option, else the gamatotv.info redirect
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.gamatotv_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.gamatotv_domain)]


def gettytul():
    return "https://gamatotv.gs/"


# gamatotv.info -> <x>.workers.dev -> the current domain
REDIRECTOR_URL = "https://gamatotv.info/"
LOCAL_PAGE_SIZE = 100
# "Director ..." / "Stars: ..." lines of a film page -> INFO keys
INFO_LINES = (("director", r"Director[s]?"), ("writers", r"Writer[s]?"), ("creator", r"Creator[s]?"), ("stars", r"Stars"))


class GamatoTV(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "gamatotv", "cookie": "gamatotv.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.USER_AGENT = self.HEADER.get("User-Agent", "")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.gamatotv_domain.value.strip()
        if domain and not domain.startswith("http"):
            domain = "https://" + domain
        self.MAIN_URL = domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul()
        self.domainChecked = False
        self.MENU = [{"category": "list_items", "title": _("Movies"), "path": "el/11088/"},
                     {"category": "list_items", "title": _("Series"), "path": "el/11016/"},
                     {"category": "list_items", "title": _("Kids"), "path": "el/animation/"},
                     {"category": "list_top", "title": "Top 250", "path": "el/top/"},
                     {"category": "list_menu", "title": _("Genres"), "section": "movie"},
                     {"category": "list_menu", "title": _("Series genres"), "section": "series"},
                     {"category": "list_menu", "title": _("Year"), "section": "year"}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("gamatotv")
        self.wfInitFolderCache()

    ###################################################
    # domain + http
    ###################################################
    def _toCurrentDomain(self, url):
        # favourites keep the domain of the day they were added: every gamatotv.* url goes to the current one
        match = re.match(r"^https?://(?:www\.)?gamatotv\.[a-z0-9.-]+/(.*)$", url or "")
        return self.MAIN_URL + match.group(1) if match else url

    def _discoverDomain(self):
        # the redirect chain of gamatotv.info ends on the domain of the day
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        sts, data = self.cm.getPage(REDIRECTOR_URL, params)
        candidates = [self.cm.meta.get("url", "")]
        if sts:
            candidates.extend(re.findall(r"https?://(?:www\.)?gamatotv\.[a-z]{2,}/", data))
        for url in candidates:
            domain = self.up.getDomain(url) if self.cm.isValidUrl(url) else ""
            if domain and domain.startswith("gamatotv.") and domain != "gamatotv.info":
                return "https://%s/" % domain
        return ""

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        url = self._toCurrentDomain(baseUrl.split("#", 1)[0])
        sts, data = self.cm.getPageCFProtection(url, dict(addParams), post_data)
        # a WordPress page has wp-content (the static navlinks/*.html menus do not); a parked domain does not either
        dead = not sts or ("wp-content" not in data and not url.endswith(".html"))
        if dead and not self.domainChecked and url.startswith(self.MAIN_URL):
            # once per session: the configured / default domain is gone - ask the redirector
            self.domainChecked = True
            newUrl = self._discoverDomain()
            printDBG("GamatoTV.getPage domain [%s] -> [%s]" % (self.MAIN_URL, newUrl))
            if newUrl and newUrl != self.MAIN_URL:
                self.MAIN_URL = newUrl
                sts, data = self.cm.getPageCFProtection(self._toCurrentDomain(url), dict(addParams), post_data)
        return sts, data

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        return strwithmeta(url, {"Referer": self.MAIN_URL, "User-Agent": self.USER_AGENT}) if url.startswith("http") else url

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            if cItem.get("type", "") == "video" or cItem.get("category", "") == "video":
                prefix = "video"
            # path only (/<id>/<slug>/#s1e2): the key survives a domain hop
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _splitYear(title):
        # "Our Flag Means Death (2022-)" -> ("Our Flag Means Death", "2022")
        match = re.match(r"^(.*?)\s*\(((?:19|20)\d\d)[^)]*\)\s*$", title)
        return (match.group(1).strip(), match.group(2)) if match else (title.strip(), "")

    @staticmethod
    def _metaTitle(title):
        # "Hope / Hopeu" -> "Hope"
        return title.split(" / ", 1)[0].strip()

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    def _url(self, cItem):
        return self._toCurrentDomain(cItem.get("url", "")) if cItem.get("url") else self.MAIN_URL + cItem.get("path", "")

    def _content(self, data):
        # the text of a film / series page: from the entry content to the byline
        content = self.cm.ph.getDataBeetwenMarkers(data, '<div class="entry-content">', '<div class="byline', False)[1]
        return content or self.cm.ph.getDataBeetwenMarkers(data, '<div class="entry-content">', "<!-- .entry-content", False)[1]

    def _linkAnchors(self, html):
        # (url, label) of the links worth a try: the site's gtv4 pages and hosters urlparser knows
        result = []
        for url, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
            url = url.replace("&amp;", "&").replace("&#038;", "&")
            if "gtv4." in url or (self.cm.isValidUrl(url) and "youtube" not in url and self.up.checkHostSupport(url) == 1):
                result.append((url, self.cleanHtmlStr(label)))
        return result

    def _altLink(self, content):
        # "Δείτε την σειρά εδώ": a gtv4 page with the coverapi player of the whole series
        for url, label in re.findall(r'<a[^>]+href="([^"]*gtv4\.[^"]+)"[^>]*>([^<]*)</a>', content):
            if not re.match(r"^\s*(?:LINK\s*\d+|\d+)\s*$", label, re.I):
                return url, self.cleanHtmlStr(label)
        return "", ""

    def _seasons(self, content):
        # {season: {episode: [url]}} from "Season 4: <a>01</a>, <a>01</a>, 02, ..." - two links of one number are
        # two mirrors, a number without a link is not out yet, a link to an ad page / dead hoster gives no url
        seasons = {}
        parts = re.split(r"Season\s*(\d+)\s*:?", content)
        for idx in range(1, len(parts) - 1, 2):
            episodes = seasons.setdefault(str(int(parts[idx])), {})
            for url, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*(\d+)\s*</a>', parts[idx + 1]):
                links = episodes.setdefault(str(int(label)), [])
                url = url.replace("&amp;", "&")
                if ("gtv4." in url or self.up.checkHostSupport(url) == 1) and url not in links:
                    links.append(url)
        return seasons

    def _siteInfo(self, data):
        # (info dict, plot, title, year, kind, dubbed) of a film / series page; kind: "tv" / "movie"
        info = {}
        content = self._content(data)
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h1 class="post-title[^"]*">(.*?)</h1>')[0])
        title, year = self._splitYear(title)
        if year:
            info["year"] = year
        lines = [self.cleanHtmlStr(x) for x in re.split(r"<br\s*/?>|</p>", content)]
        plot = ""
        for line in lines:
            if not line:
                continue
            for key, label in INFO_LINES:
                match = re.match(r"^%s:?\s+(.+)$" % label, line)
                if match:
                    # "Yahya Abdul-Mateen IIMark Wahlberg" - the names of the site run together
                    info[key] = re.sub(r"(?<=[a-z])(?=[A-Z])", ", ", match.group(1)).strip()
                    break
            else:
                if not plot and len(line) > 40 and not re.match(r"^(?:Trailer|Season\s*\d)", line):
                    plot = re.sub(r"\s*Trailer\s*(?:\S\s*LINK.*)?$", "", line)
        byline = self.cm.ph.getDataBeetwenMarkers(data, '<div class="byline', "</div>", False)[1]
        cats = re.findall(r'href="[^"]*/el/([^/"]+)/"[^>]*rel="category tag">([^<]+)<', byline)
        genres = [self.cleanHtmlStr(t) for slug, t in cats if slug not in ("11088", "11016")]
        if genres:
            info["genres"] = ", ".join(genres)
        added = self.cleanHtmlStr(self.cm.ph.getSearchGroups(byline, r'rel="bookmark"[^>]*>([^<]+)<')[0] or self.cm.ph.getSearchGroups(byline, r"<a[^>]*>([^<]+)</a>")[0])
        if added:
            info["released"] = added
        slugs = [slug for slug, _t in cats]
        kind = "tv" if ("11016" in slugs or re.search(r"Season\s*\d+", content)) else "movie"
        # "Παιδικά" (/el/animation/) are the Greek dubbed ones, everything else has Greek subtitles
        dubbed = "animation" in slugs
        if not dubbed:
            info["subtitles"] = _("Greek")
        return info, plot, title, year, kind, dubbed

    ###################################################
    # lists
    ###################################################
    def _addEntry(self, cItem, url, label, icon, classes, summary=""):
        label = self.cleanHtmlStr(label)
        if not url or not label:
            return
        sTitle, year = self._splitYear(label)
        params = stripPagerKeys(dict(cItem), ("path", "section", "search", "base_url"))
        params.update({"good_for_fav": True, "url": url, "title": label, "icon": self.getFullIconUrl(icon), "desc": "[/br]".join(x for x in (year, summary) if x),
                       "s_title": sTitle, "s_year": year})
        if "category-11016" in classes:
            params.update({"category": "list_seasons", "meta_type": "tv"})
            self.addDir(params)
        else:
            if IsMediaNamingNormalized() and year:
                params["title"] = "%s (%s)" % (sTitle, year)
            params.update({"category": "video", "meta_type": "movie"})
            self.addVideo(params)

    def listItems(self, cItem):
        printDBG("GamatoTV.listItems |%s|" % cItem)
        page = self._page(cItem)
        baseUrl = self._url(dict(cItem, url=cItem.get("base_url", "") or cItem.get("url", "")))
        if cItem.get("search"):
            pageTpl = "%s?s=%s&paged={page}" % (self.MAIN_URL, urllib_quote_plus(cItem["search"]))
        else:
            pageTpl = re.sub(r"page/\d+/?$", "", baseUrl).rstrip("/").replace("{", "{{").replace("}", "}}") + "/page/{page}/"
        url = pageTpl.format(page=page) if page > 1 else pageTpl.format(page=1).replace("&paged=1", "").replace("page/1/", "")
        sts, data = self.getPage(url)
        if not sts:
            return
        for classes, item in re.findall(r'(?s)<div id="post-\d+" class="([^"]*hentry[^"]*)">(.*?)<!-- \.hentry -->', data):
            if "type-page" in classes or " page " in classes:
                continue
            # lists: <h2>, search results: <h1> + the start of the plot
            url, label = self.cm.ph.getSearchGroups(item, r'(?s)<h[12] class=.post-title[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', 2)
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            summary = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="entry-summary">\s*<p>(.*?)</p>')[0])
            self._addEntry(cItem, url, label, icon, classes, summary)
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<nav class="pagination', "</nav>", False)[1]
        pages = [int(p) for p in re.findall(r'class="page-numbers"[^>]*>(\d+)<', pager)]
        lastPage = max(pages + [page]) if pages else 0
        hasNext = 'class="next page-numbers"' in pager
        nextItem = stripPagerKeys(dict(cItem))
        nextItem["base_url"] = baseUrl
        addPagingItems(self, nextItem, page, hasNext, lastPage, pageTpl)

    def listTop(self, cItem):
        printDBG("GamatoTV.listTop |%s|" % cItem)
        url = self._url(cItem)
        sts, data = self.getPage(url)
        if not sts:
            return
        items = re.findall(r'(?s)<div class="weekly-item3">\s*<a href="([^"]+)"[^>]*>\s*<img[^>]+src="([^"]+)".*?alt="([^"]*)"', data)
        page = self._page(cItem)
        lastPage = max(1, (len(items) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE)
        page = min(page, lastPage)
        for idx, (itemUrl, icon, label) in enumerate(items[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]):
            sTitle, year = self._splitYear(self.cleanHtmlStr(label))
            # Top 250 has films only; the rank before the title
            params = stripPagerKeys(dict(cItem), ("path",))
            rank = (page - 1) * LOCAL_PAGE_SIZE + idx + 1
            title = "%s (%s)" % (sTitle, year) if (year and IsMediaNamingNormalized()) else self.cleanHtmlStr(label)
            params.update({"good_for_fav": True, "category": "video", "url": itemUrl, "title": title, "icon": self.getFullIconUrl(icon),
                           "desc": "#%d | %s" % (rank, year) if year else "#%d" % rank, "s_title": sTitle, "s_year": year, "meta_type": "movie"})
            self.addVideo(params)
        addPagingItems(self, dict(cItem, url=url), page, page < lastPage, lastPage, url.replace("{", "{{").replace("}", "}}"))

    def listMenu(self, cItem):
        # the genre / year menu of the site: "Είδος ταινίας:" <ul>, "Είδος σειράς:" <ul>, then the years
        printDBG("GamatoTV.listMenu |%s|" % cItem)
        sts, data = self.getPage(self.MAIN_URL + "navlinks/menu.html")
        if not sts:
            return
        genres, years = [], []
        for block in re.findall(r"(?s)<ul>(.*?)</ul>", data):
            links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', block)
            if any("?s=" in url for url, _t in links):
                years.extend(links)
            elif links:
                genres.append(links)
        section = cItem.get("section", "")
        if section == "year":
            links = years
        else:
            links = genres[{"movie": 0, "series": 1}.get(section, 0)] if len(genres) > 1 else (genres[0] if genres and section == "movie" else [])
        for url, title in links:
            params = {"name": "category", "good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url)}
            if "?s=" in url:
                # the years are searches for the year
                params["search"] = url.split("?s=", 1)[1]
            self.addDir(params)

    def listSeasons(self, cItem):
        printDBG("GamatoTV.listSeasons |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        content = self._content(data)
        _info, plot, title, year, _kind, _dubbed = self._siteInfo(data)
        seasons = self._seasons(content)
        altUrl, altLabel = self._altLink(content)
        sTitle = cItem.get("s_title", "") or title or cItem["title"]
        fields = {"s_title": sTitle, "s_year": year or cItem.get("s_year", ""), "desc": plot or cItem.get("desc", "")}
        # an episode without a usable link still plays from the coverapi player of the whole series
        order = [s for s in sorted(seasons, key=int) if any(links or altUrl for links in seasons[s].values())]
        if len(order) == 1:
            self.listEpisodes(dict(cItem, category="list_episodes", season=order[0], url="%s#s%s" % (url, order[0]), **fields), data)
            return
        normalize = IsMediaNamingNormalized()
        for season in order:
            count = len([1 for links in seasons[season].values() if links or altUrl])
            seasonTag = formatSxxExx(season) if normalize else "%s %s" % (_("Season"), season)
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            params.update({"good_for_fav": True, "category": "list_episodes", "title": "%s - %s" % (sTitle, seasonTag), "season": season,
                           "url": "%s#s%s" % (url, season), "desc": "%s: %d[/br]%s" % (_("Episodes"), count, fields["desc"])})
            self.addDir(params)
        if altUrl and not order:
            # no season list on the page: the player of the whole series
            params = stripPagerKeys(dict(cItem))
            params.update(fields)
            params.update({"good_for_fav": True, "category": "video", "title": "%s - %s" % (sTitle, altLabel), "url": "%s#all" % url})
            self.addVideo(params)
        if not order and not altUrl:
            SetIPTVPlayerLastHostError(_("No stream available"))

    def listEpisodes(self, cItem, data=None):
        printDBG("GamatoTV.listEpisodes |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        season = str(cItem.get("season", "") or self.cm.ph.getSearchGroups(cItem["url"], r"#s(\d+)$")[0])
        if data is None:
            sts, data = self.getPage(url)
            if not sts:
                return
            _info, plot, title, year, _kind, _dubbed = self._siteInfo(data)
            cItem = dict(cItem, s_title=cItem.get("s_title", "") or title, s_year=cItem.get("s_year", "") or year, desc=cItem.get("desc", "") or plot)
        content = self._content(data)
        altUrl = self._altLink(content)[0]
        sTitle = cItem.get("s_title", "") or cItem["title"]
        normalize = IsMediaNamingNormalized()
        for episode, links in sorted(self._seasons(content).get(season, {}).items(), key=lambda r: int(r[0])):
            if not links and not altUrl:
                continue
            if normalize:
                title = "%s - %s" % (sTitle, formatSxxExx(season, episode))
            else:
                title = "%s - %s %s - %s %s" % (sTitle, _("Season"), season, _("Episode"), episode)
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "video", "title": title, "s_title": sTitle, "url": "%s#s%se%s" % (url, season, episode),
                           "season": season, "episode": episode, "meta_type": "tv"})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GamatoTV.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "search": searchPattern.strip(), "url": "%s?s=%s" % (self.MAIN_URL, urllib_quote_plus(searchPattern.strip()))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _gtv4(self, url):
        # a gtv4.site page: the hoster iframe or the site's own MP4 (video.js <source>); "" when it has neither
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self.MAIN_URL)
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return "", False
        data = self.cm.ph.getDataBeetwenMarkers(data, 'class="entry-content"', "<!-- .entry-content", False)[1] or data
        src = self.cm.ph.getSearchGroups(data, r'<source[^>]+src="([^"]+\.(?:mp4|m3u8)[^"]*)"')[0]
        if src:
            return self.getFullUrl(src, url), True
        src = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0].replace("&amp;", "&")
        return (self.getFullUrl(src, url) if src else ""), False

    def _hosterLink(self, name, url, referer, lang, meta=None):
        # one link row of a gtv4 page / hoster url, None when nothing plays there
        if "gtv4." in url:
            target, direct = self._gtv4(url)
            referer = url
        else:
            target, direct = url, False
        if not self.cm.isValidUrl(target):
            return None
        if direct:
            return {"name": "%s - MP4 [%s]" % (name, lang), "url": strwithmeta(target, {"Referer": self.cm.getBaseUrl(referer), "User-Agent": self.USER_AGENT}), "need_resolve": 0}
        if "voe" in self.up.getDomain(target) and self.up.checkHostSupport(target) != 1:
            # VOE plays its files on ever new domains; voe.sx takes the same id
            target = re.sub(r"^https?://[^/]+/", "https://voe.sx/", target)
        if self.up.checkHostSupport(target) != 1:
            printDBG("GamatoTV: no parser for [%s]" % target)
            return None
        linkMeta = {"Referer": referer}
        linkMeta.update(meta or {})
        hoster = self.up.getDomain(target).split(".")[0].capitalize()
        return {"name": "%s - %s [%s]" % (name, hoster, lang), "url": strwithmeta(target, linkMeta), "need_resolve": 1}

    def getLinksForVideo(self, cItem):
        printDBG("GamatoTV.getLinksForVideo [%s]" % cItem)
        pageUrl, _sep, frag = cItem.get("url", "").partition("#")
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        content = self._content(data)
        _info, plot, title, year, kind, dubbed = self._siteInfo(data)
        lang = "Greek dub" if dubbed else "Greek subs"
        urltab = []
        episode = re.match(r"^s(\d+)e(\d+)$", frag)
        altUrl, altLabel = self._altLink(content)
        if episode:
            season, epNum = episode.group(1), episode.group(2)
            for idx, url in enumerate(self._seasons(content).get(season, {}).get(epNum, [])):
                link = self._hosterLink("%s %d" % (_("Server"), idx + 1), url, self.MAIN_URL, lang)
                if link:
                    urltab.append(link)
            if altUrl:
                link = self._hosterLink(altLabel, altUrl, self.MAIN_URL, lang, {"Season": season, "Episode": epNum})
                if link and "coverapi" in link["url"]:
                    urltab.append(link)
        elif frag == "all":
            link = self._hosterLink(altLabel or _("Server"), altUrl, self.MAIN_URL, lang) if altUrl else None
            if link:
                urltab.append(link)
        else:
            for url, label in self._linkAnchors(content):
                if url == altUrl and kind == "tv":
                    continue
                link = self._hosterLink(label or _("Server"), url, self.MAIN_URL, lang)
                if link:
                    urltab.append(link)
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        trailer = self.cm.ph.getSearchGroups(content, r'href="(https?://(?:www\.)?youtu[^"]+)"')[0]
        if trailer and not episode:
            urltab.append({"name": _("Trailer"), "url": trailer, "need_resolve": 1})
        mediaType = "tv" if (episode or kind == "tv") else "movie"
        sTitle = cItem.get("s_title", "") or title
        metaQuery = sidecarMetaQuery(mediaType, self._metaTitle(sTitle), cItem.get("s_year", "") or year, skip=())
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), plot or cItem.get("desc", ""), metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("GamatoTV.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("GamatoTV.getArticleContent [%s]" % cItem)
        info, plot, title, year, kind = {}, "", "", "", ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, title, year, kind, _dubbed = self._siteInfo(data)
        isEpisode = bool(re.search(r"#s\d+e\d+$", cItem.get("url", "")))
        mediaType = cItem.get("meta_type", "") or kind or "movie"
        sTitle = cItem.get("s_title", "") or title or cItem.get("title", "")
        year = cItem.get("s_year", "") or year
        meta = {}
        try:
            if sTitle:
                meta = getMeta(mediaType, self._metaTitle(sTitle), year)
        except Exception:
            printExc()
        meta = meta or {}
        metaInfo = dict(meta.get("info", {}))
        if "cast" in metaInfo:
            info.pop("stars", None)
        if "directors" in metaInfo:
            info.pop("director", None)
        metaInfo.update(info)
        text = plot or cItem.get("desc", "")
        if isEpisode:
            text = "%s[/br]%s" % (cItem.get("title", ""), text)
        metaPlot = meta.get("plot", "")
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": metaInfo}]

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
        elif category == "list_top":
            self.listTop(self.currItem)
        elif category == "list_menu":
            self.listMenu(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
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
        CHostBase.__init__(self, GamatoTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("gamatotv")

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
