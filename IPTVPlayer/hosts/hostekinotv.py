# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - ekino-tv.pl moved to ekino.ws: movies (latest / genres / years /
#   version), series (sections of /serie/, A-Z catalogue -> seasons -> episodes), search
#   (movies + series), players via /watch/f/<host>/<id> (session bound ids, Cloudflare Turnstile
#   after some plays -> CaptchaHelper "cf_re" + /watch/verify.php) -> play.ekino.link iframe ->
#   urlparser + watched flag / downloaded flag / name normalisation / sidecar / moviemeta INFO /
#   favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://ekino.ws/"


# episode page: /serie/watch/<slug>+season[<s>]+episode[<e>](+)
EPISODE_RE = re.compile(r'/serie/watch/([^/+"\[\]]+)\+season\[(\d+)\]\+episode\[(\d+)\]')
# " - HD", " - CAM", " - HD AI" ... behind the Polish title
QUALITY_RE = re.compile(r'\s+-\s+((?:HD|CAM|TS|AI|4K|FHD|UHD|SD)(?:\s+(?:HD|CAM|AI|4K))*)\s*$', re.IGNORECASE)


class EkinoTv(GenericFolderWatchedScraperMixin, CBaseHostClass, CaptchaHelper):
    # what identifies a row and is needed to open it again
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "season", "episode", "series_url",
                  "icon", "desc", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "EkinoTv", "cookie": "EkinoTv.cookie"})
        self.USER_AGENT = self.cm.getDefaultUserAgent('firefox')
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "pl,en;q=0.7"}
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("views/img/logo.png")
        self.MENU = [{"category": "list_items", "title": _("Movies") + " - " + _("Latest"), "url": self.getFullUrl("movie/cat/+")},
                     {"category": "list_genres", "title": _("Movies") + " - " + _("Genres"), "url": self.getFullUrl("movie/cat/+")},
                     {"category": "list_years", "title": _("Movies") + " - " + _("Year"), "url": self.getFullUrl("movie/cat/+")},
                     {"category": "list_versions", "title": _("Movies") + " - " + _("Version"), "url": self.getFullUrl("movie/cat/+")},
                     {"category": "list_serie_sections", "title": _("Series"), "url": self.getFullUrl("serie/")},
                     {"category": "list_serie_az", "title": _("Series") + " - A-Z", "url": self.getFullUrl("serie/")}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("ekinotv")
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
            if category == "ek_series":
                return "series:%s" % url if url else ""
            if category == "ek_season":
                seriesUrl = str(cItem.get("series_url", "") or "").strip()
                season = str(cItem.get("season", "") or "").strip()
                return "season:%s|%s" % (seriesUrl, season) if seriesUrl and season else ""
            return ""
        except Exception:
            printExc()
        return ""

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _refererParams(self, referer):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"]["Referer"] = referer
        return params

    ###################################################
    # naming
    ###################################################
    def _splitQuality(self, title):
        match = QUALITY_RE.search(title)
        if match:
            return title[:match.start()].strip(), match.group(1).upper()
        return title, ""

    def _movieTitle(self, title, year, version):
        if IsMediaNamingNormalized():
            name = self._splitQuality(title)[0]
            if year:
                name = "%s (%s)" % (name, year)
            return "%s - %s" % (name, version) if version else name
        return title

    def _episodeTitle(self, sTitle, season, episode, epTitle=""):
        if IsMediaNamingNormalized():
            return "%s - %s" % (sTitle, formatSxxExx(season, episode))
        title = "%s - s%se%s" % (sTitle, season, episode)
        return "%s %s" % (title, epTitle) if epTitle else title

    def _episodeUrl(self, slug, season, episode):
        return self.getFullUrl("serie/watch/%s+season[%s]+episode[%s]" % (slug, season, episode))

    ###################################################
    # lists
    ###################################################
    def _getNextPage(self, data, currUrl):
        nextPage = self.cm.ph.getSearchGroups(data, r'title="Nast[^"]*pna strona"\s+href="([^"]+)"')[0]
        if not nextPage:
            return ""
        return self.getFullUrl(nextPage.replace("&amp;", "&"), currUrl)

    def _parseCard(self, item, currUrl):
        # one "movies-list-item" block -> dict or None
        href = self.cm.ph.getSearchGroups(item, r'href="([^"]*/(?:movie|serie)/show/[^"]+)"')[0]
        if not href:
            return None
        url = self.getFullUrl(href, currUrl)
        titleBlock = self.cm.ph.getDataBeetwenMarkers(item, 'class="title"', "</div>", False)[1]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(titleBlock, r'<a[^>]+href="[^"]+"[^>]*>([^<]+)</a>')[0])
        if not title:
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'alt="([^"]+)"')[0]).split(" / ")[0]
        origTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(titleBlock, r'<a class="blue"[^>]*>([^<]*)</a>')[0])
        icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0], currUrl)
        year = self.cm.ph.getSearchGroups(item, r'class="cates">\s*(\d{4})')[0]
        origYear = self.cm.ph.getSearchGroups(origTitle, r'\((\d{4})\)\s*$')[0]
        if origYear:
            origTitle = origTitle[:origTitle.rfind("(")].strip()
            year = year or origYear
        version = self.cm.ph.getSearchGroups(item, r'<i title="([^"]+)" class="glyphicon')[0]
        genres = [self.cleanHtmlStr(g) for g in re.findall(r'<a href="/movie/cat/kategoria[^"]*"[^>]*>([^<]+)</a>', item)]
        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, 'class="movieDesc">', "</div>", False)[1])
        epMatch = EPISODE_RE.search(item)
        return {"url": url, "title": title, "orig_title": origTitle, "icon": icon, "year": year, "version": version,
                "genres": genres, "plot": desc, "is_movie": "/movie/show/" in url, "ep_match": epMatch}

    def _addCard(self, cItem, card, asEpisode=False):
        title = card["title"]
        info = []
        if card["year"]:
            info.append(card["year"])
        if card["version"]:
            info.append(card["version"])
        if card["genres"]:
            info.append(", ".join([g for g in card["genres"] if g]))
        if card["orig_title"] and card["orig_title"] != title:
            info.insert(0, card["orig_title"])
        desc = " | ".join(info)
        if card["plot"]:
            desc = "%s[/br]%s" % (desc, card["plot"]) if desc else card["plot"]
        params = stripPagerKeys(dict(cItem), ("search_pattern", "page_tpl"))
        params.update({"good_for_fav": True, "icon": card["icon"], "desc": desc})
        if card["is_movie"]:
            name = self._splitQuality(title)[0]
            params.update({"category": "ek_movie", "url": card["url"], "title": self._movieTitle(title, card["year"], card["version"]),
                           "s_title": name, "meta_type": "movie", "meta_title": card["orig_title"] or name, "meta_year": card["year"]})
            self.addVideo(params)
        elif asEpisode and card["ep_match"]:
            slug, season, episode = card["ep_match"].groups()
            params.update({"category": "ek_episode", "url": self._episodeUrl(slug, season, episode),
                           "title": self._episodeTitle(title, season, episode), "s_title": title, "season": season, "episode": episode,
                           "series_url": card["url"], "meta_type": "tv", "meta_title": card["orig_title"] or title, "meta_year": card["year"]})
            self.addVideo(params)
        else:
            params.update({"category": "ek_series", "url": card["url"], "title": title, "s_title": title,
                           "meta_type": "tv", "meta_title": card["orig_title"] or title, "meta_year": card["year"]})
            self.addDir(params)

    def _addCards(self, cItem, data, currUrl, asEpisode=False):
        cnt = 0
        seen = set()
        for item in data.split('class="movies-list-item')[1:]:
            # one card = up to the next card / pager / next section
            for marker in ('id="pager"', "<h4", 'class="col-md-4 menu-wrap"'):
                item = item.split(marker, 1)[0]
            card = self._parseCard(item, currUrl)
            if not card or not card["title"]:
                continue
            key = card["url"] if not (asEpisode and card["ep_match"]) else card["ep_match"].group(0)
            if key in seen:
                continue
            seen.add(key)
            self._addCard(cItem, card, asEpisode)
            cnt += 1
        return cnt

    def listItems(self, cItem):
        printDBG("EkinoTv.listItems |%s|" % cItem.get("url", ""))
        url = cItem["url"]
        page = cItem.get("page", 1)
        sts, data = self.getPage(url)
        if not sts:
            return
        nextPage = self._getNextPage(data, url)
        cnt = self._addCards(cItem, data, url)
        hasNext = bool(cnt and nextPage and nextPage != url)
        # pager urls: ".../kategoria[1]+strona[2]+" (movies) or "a,strona=2" (series A-Z)
        tpl = cItem.get("page_tpl", "")
        match = re.search(r"strona([\[=])(\d+)", nextPage) if hasNext else None
        if match and not tpl:
            tpl = "%sstrona%s{page}%s" % (nextPage[:match.start()], match.group(1), nextPage[match.end():])
        lastPage = max([int(n) for n in re.findall(r'href="[^"]*strona[\[=](\d+)[^"]*"', data)] + [page])
        listItem = dict(cItem)
        listItem["page_tpl"] = tpl
        addPagingItems(self, listItem, page, hasNext, lastPage if tpl else 0, tpl, None if tpl else {"url": nextPage})

    def listGenres(self, cItem):
        printDBG("EkinoTv.listGenres")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'class="movieCategories"', "</ul>", False)[1]
        data = re.sub(r'<!--.*?-->', '', data, flags=re.DOTALL)
        for url, title in re.findall(r'<a href="([^"]+)">([^<]+)</a>', data):
            title = self.cleanHtmlStr(title)
            if not title:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url) + "+"})
            self.addDir(params)

    def listYears(self, cItem):
        printDBG("EkinoTv.listYears")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'class="filtyear"', "</ul>", False)[1]
        for year in re.findall(r'data-id="(\d{4})"', data):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": year, "url": self.getFullUrl("movie/cat/rok[%s]+" % year)})
            self.addDir(params)

    def listVersions(self, cItem):
        printDBG("EkinoTv.listVersions")
        versions = [("Lektor", _("Voice-over")), ("Napisy", _("Subtitles")), ("Dubbing", _("Dubbed")),
                    ("PL", _("Polish films")), ("ENG", _("Original version"))]
        for key, title in versions:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl("movie/cat/wersja[%s]+" % key)})
            self.addDir(params)

    def _serieSections(self, data):
        # [(title, html)] of the /serie/ start page (<h4> headed blocks)
        sections = []
        parts = re.split(r'<h4[^>]*>', data)
        for part in parts[1:]:
            title = self.cleanHtmlStr(part.split("</h4>", 1)[0])
            if title:
                sections.append((title, part))
        return sections

    def listSerieSections(self, cItem):
        printDBG("EkinoTv.listSerieSections")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for idx, (title, part) in enumerate(self._serieSections(data)):
            if 'class="movies-list-item' not in part and 'class="b"' not in part:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_serie_section", "title": title, "section_idx": idx})
            self.addDir(params)

    def listSerieSection(self, cItem):
        printDBG("EkinoTv.listSerieSection %s" % cItem.get("section_idx"))
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        sections = self._serieSections(data)
        idx = cItem.get("section_idx", 0)
        if idx >= len(sections):
            return
        title, part = sections[idx]
        if 'class="movies-list-item' in part:
            # sections with a proper episode link (slug in it) list the episode itself
            asEpisode = bool(EPISODE_RE.search(part))
            self._addCards(cItem, part, url, asEpisode)
            return
        # "Popularne": numbered rows with a small cover
        seen = set()
        for row in part.split('class="row lspc"')[1:]:
            href, name = self.cm.ph.getSearchGroups(row, r'<a class="b"\s+href="([^"]+)">([^<]+)</a>', 2)
            if not href or href in seen:
                continue
            seen.add(href)
            name = self.cleanHtmlStr(name)
            year = self.cm.ph.getSearchGroups(name, r'\((\d{4})\)\s*$')[0]
            pl = name.split(" / ")[0]
            orig = name.split(" / ")[1] if " / " in name else ""
            if year:
                pl = re.sub(r'\s*\(\d{4}\)\s*$', "", pl)
                orig = re.sub(r'\s*\(\d{4}\)\s*$', "", orig)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "ek_series", "url": self.getFullUrl(href), "title": pl, "s_title": pl,
                           "icon": self.getFullIconUrl(self.cm.ph.getSearchGroups(row, r'<img[^>]+src="([^"]+)"')[0]), "desc": name,
                           "meta_type": "tv", "meta_title": orig or pl, "meta_year": year})
            self.addDir(params)

    def listSerieAZ(self, cItem):
        printDBG("EkinoTv.listSerieAZ")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'class="serialsmenu"', "</ul>", False)[1]
        for url, title, count in re.findall(r'href="([^"]+)"><span class="name">([^<]+)</span><span\s+class="count">(\d+)<', data):
            if count == "0":
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": "%s (%s)" % (self.cleanHtmlStr(title), count), "url": self.getFullUrl(url)})
            self.addDir(params)

    def _parseSeasons(self, data):
        # [(season, html of its <ul class="list-series">)]
        seasons = []
        for season, block in re.findall(r'<p>Sezon (\d+)</p>\s*<ul class="list-series">(.*?)</ul>', data, re.DOTALL):
            seasons.append((season, block))
        return seasons

    def listSeasons(self, cItem):
        printDBG("EkinoTv.listSeasons |%s|" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        info = self._parseTitlePage(data)
        sTitle = cItem.get("s_title", cItem["title"])
        seasons = sorted(self._parseSeasons(data), key=lambda x: int(x[0]))
        for season, block in seasons:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "ek_season", "title": "%s - %s %s" % (sTitle, _("Season"), season),
                           "s_title": sTitle, "season": season, "series_url": cItem["url"],
                           "desc": info["desc"] or cItem.get("desc", ""), "icon": cItem.get("icon", "") or info["poster"]})
            self.addDir(params)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))

    def listEpisodes(self, cItem):
        printDBG("EkinoTv.listEpisodes |%s| season %s" % (cItem.get("series_url", ""), cItem.get("season", "")))
        seriesUrl = cItem.get("series_url", cItem["url"])
        sts, data = self.getPage(seriesUrl)
        if not sts:
            return
        sTitle = cItem.get("s_title", cItem["title"])
        for season, block in self._parseSeasons(data):
            if season != cItem.get("season"):
                continue
            episodes = []
            for href, epTitle in re.findall(r'<a href="([^"]+)">([^<]*)</a>', block):
                epMatch = EPISODE_RE.search(href)
                if not epMatch:
                    continue
                slug, sNum, eNum = epMatch.groups()
                episodes.append((int(eNum), slug, sNum, eNum, self.cleanHtmlStr(epTitle)))
            for _num, slug, sNum, eNum, epTitle in sorted(episodes):
                if re.match(r'^Odcinek\s+\d+$', epTitle):
                    epTitle = ""
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "ek_episode", "url": self._episodeUrl(slug, sNum, eNum),
                               "title": self._episodeTitle(sTitle, sNum, eNum, epTitle), "s_title": sTitle, "season": sNum, "episode": eNum,
                               "series_url": seriesUrl, "desc": epTitle or cItem.get("desc", "")})
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EkinoTv.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem["url"] = self.getFullUrl("search/qf/?q=%s" % urllib_quote_plus(searchPattern))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        if not self._addCards(cItem, data, cItem["url"]):
            SetIPTVPlayerLastHostError(_("No matching entries found."))

    ###################################################
    # title page
    ###################################################
    def _parseTitlePage(self, data):
        info = {"desc": "", "poster": "", "title": "", "subtitle": "", "actors": ""}
        info["desc"] = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'class="descriptionMovie">', "</div>", False)[1])
        info["poster"] = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, r'<img class="moviePoster"\s+src="([^"]+)"')[0])
        info["title"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h1 class="title">(.*?)</h1>')[0])
        info["subtitle"] = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<h2 class="title">(.*?)</h2>')[0])
        actors = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="actors">', "</ul>", False)[1]
        info["actors"] = ", ".join([self.cleanHtmlStr(x) for x in re.findall(r'aktor\[[^"]*"\s*>([^<]+)</a>', actors)][:10])
        return info

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("EkinoTv.getLinksForVideo [%s]" % cItem.get("url", ""))
        urlTab = []
        pageUrl = cItem.get("url", "")
        if not self.cm.isValidUrl(pageUrl):
            return []
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        sidecarTxt = self._parseTitlePage(data)["desc"]

        # tab labels: <a href="#<id>-<host>">host <i title="Lektor PL"> <img title="Wysoka jakość">
        labels = {}
        tabs = self.cm.ph.getDataBeetwenMarkers(data, 'class="players"', "</ul>", False)[1]
        for tabId, body in re.findall(r'<a href="#([^"]+)"[^>]*>(.*?)</a>', tabs, re.DOTALL):
            extra = [self.cleanHtmlStr(t) for t in re.findall(r'title="([^"]+)"', body)]
            labels[tabId] = ", ".join([t for t in extra if t])

        seen = set()
        for host, playerId in re.findall(r"ShowPlayer\('([^']+)','([^']+)'\)", data):
            if (host, playerId) in seen:
                continue
            seen.add((host, playerId))
            label = labels.get("%s-%s" % (playerId, host), "")
            name = "%s (%s)" % (host, label) if label else host
            url = self.getFullUrl("watch/f/%s/%s" % (host, playerId))
            urlTab.append({"name": name, "url": strwithmeta(url, {"Referer": pageUrl}), "need_resolve": 1})

        if not urlTab:
            if "removed_player" in data and "ShowPlayer" not in data:
                SetIPTVPlayerLastHostError(_("No free player available for this title."))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def _getWatchPage(self, url, referer):
        sts, data = self.getPage(url, self._refererParams(referer))
        if not sts:
            return False, ""
        sitekey = self.cm.ph.getSearchGroups(data, r"""sitekey\s*:\s*['"]([^'"]+)['"]""")[0]
        if sitekey and "turnstile" in data:
            # the site asks for a Cloudflare Turnstile after some plays in a session
            token = self.processCaptcha(sitekey, url, captchaType="cf_re")[0]
            if not token:
                return False, ""
            params = self._refererParams(url)
            params["header"]["X-Requested-With"] = "XMLHttpRequest"
            sts, _resp = self.getPage(self.getFullUrl("watch/verify.php"), params, {"verify": token})
            if not sts:
                return False, ""
            sts, data = self.getPage(url, self._refererParams(referer))
            if not sts:
                return False, ""
        return True, data

    def getVideoLinks(self, videoUrl):
        printDBG("EkinoTv.getVideoLinks [%s]" % videoUrl)
        videoUrl = strwithmeta(videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        referer = videoUrl.meta.get("Referer", self.MAIN_URL)
        url = videoUrl
        if "/watch/f/" in videoUrl:
            sts, data = self._getWatchPage(videoUrl, referer)
            if not sts:
                return []
            url = self.cm.ph.getSearchGroups(data, r'href="(https?://[^"]+)"[^>]*target')[0]
            if not url:
                url = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="(https?://[^"]+)"')[0]
            if not url:
                SetIPTVPlayerLastHostError(_("This player is not available any more - reload the links."))
                return []
            if "ekino.link" in url:
                linkUrl = url
                sts, data = self.getPage(linkUrl, self._refererParams(self.MAIN_URL))
                if not sts:
                    return []
                url = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0]
                if url.startswith("//"):
                    url = "https:" + url
                url = strwithmeta(url, {"Referer": linkUrl})
        if not self.cm.isValidUrl(url):
            return []
        if 1 != self.up.checkHostSupport(url):
            SetIPTVPlayerLastHostError(_("Hosting \"%s\" not supported.") % self.up.getHostName(url))
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecar)

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("EkinoTv.getArticleContent [%s]" % cItem.get("url", ""))
        mediaType = cItem.get("meta_type", "")
        pageUrl = cItem.get("series_url") or cItem.get("url", "")
        info = {"desc": "", "poster": "", "title": "", "subtitle": "", "actors": ""}
        if self.cm.isValidUrl(pageUrl):
            sts, data = self.getPage(pageUrl)
            if sts:
                info = self._parseTitlePage(data)
        meta = {}
        try:
            meta = getMeta(mediaType, cItem.get("meta_title", "") or cItem.get("s_title", ""), cItem.get("meta_year", ""))
        except Exception:
            printExc()
            meta = {}
        otherInfo = dict(meta.get("info", {}) or {})
        if info["actors"]:
            otherInfo.setdefault("actors", info["actors"])
        if cItem.get("meta_year"):
            otherInfo.setdefault("year", cItem["meta_year"])
        if cItem.get("meta_title") and cItem.get("meta_title") != cItem.get("s_title"):
            otherInfo.setdefault("original_title", cItem["meta_title"])
        text = info["desc"] or meta.get("plot", "") or cItem.get("desc", "")
        icon = info["poster"] or meta.get("poster", "") or cItem.get("icon", "")
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
        printDBG("EkinoTv.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_years":
            self.listYears(self.currItem)
        elif category == "list_versions":
            self.listVersions(self.currItem)
        elif category == "list_serie_sections":
            self.listSerieSections(self.currItem)
        elif category == "list_serie_section":
            self.listSerieSection(self.currItem)
        elif category == "list_serie_az":
            self.listSerieAZ(self.currItem)
        elif category == "ek_series":
            self.listSeasons(self.currItem)
        elif category == "ek_season":
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
        CHostBase.__init__(self, EkinoTv(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("ekinotv")

    def withArticleContent(self, cItem):
        return bool(cItem.get("meta_type"))
