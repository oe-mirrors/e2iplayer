# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host
#   directory of Greek films, series, shows, animation, theatre, short films and sport: the filters of the site
#   (year, letter, genre, channel, country), series by season / episode or by date, search per type;
#   links: YouTube, Dailymotion, Vimeo, ok.ru through urlparser, Alpha / OPEN pages directly, other
#   broadcasters (geo GR / CY) marked "(geo)"
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, getMetaByImdbId, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://greek-movies.com/"


LOCAL_PAGE_SIZE = 100
# the lists of these need a year range: without one the site shows 2020-today only
NEEDS_YEAR = ("movies.php", "shortfilm.php", "theater.php")
# the site's filter parameters in menu order
FILTER_KEYS = ("y", "l", "g", "c", "p", "s")
# hosters that play outside Greece (urlparser or the broadcaster's own world-open files); the rest are marked "(geo)"
WORLD_HOSTS = ("youtube", "dailymotion", "vimeo", "ok", "odnoklassniki", "bit chute", "alpha", "open")
# "Τίτλος: value" lines of a title page -> INFO keys
INFO_FIELDS = {"Έτος": "year", "Είδος": "genre", "Διάρκεια": "duration", "Χώρα": "country", "Σενάριο": "writer", "Σκηνοθεσία": "director",
               "Ηθοποιοί": "cast", "Κύκλοι επεισοδίων": "seasons"}
MONTHS = {"Ιαν": 1, "Φεβ": 2, "Μάρ": 3, "Μαρ": 3, "Απρ": 4, "Μάι": 5, "Μαΐ": 5, "Μαι": 5, "Ιούν": 6, "Ιουν": 6, "Ιούλ": 7, "Ιουλ": 7, "Αύγ": 8, "Αυγ": 8,
          "Σεπ": 9, "Οκτ": 10, "Νοέ": 11, "Νοε": 11, "Δεκ": 12}


class GreekMovies(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "greekmovies", "cookie": "greekmovies.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Referer": gettytul()})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("icon/logo.png")
        self.MENU = [{"category": "list_section", "title": _("Movies"), "url": self.getFullUrl("movies.php")},
                     {"category": "list_section", "title": _("Series"), "url": self.getFullUrl("series.php")},
                     {"category": "list_section", "title": _("Animation"), "url": self.getFullUrl("animation.php")},
                     {"category": "list_section", "title": _("Shows"), "url": self.getFullUrl("shows.php")},
                     {"category": "list_section", "title": "Theatre", "url": self.getFullUrl("theater.php")},
                     {"category": "list_section", "title": _("Short films"), "url": self.getFullUrl("shortfilm.php")},
                     {"category": "list_section", "title": _("Sport"), "url": self.getFullUrl("sports.php")}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("greekmovies")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl.split("#", 1)[0], addParams, post_data)

    def _ajax(self, post):
        params = dict(self.defaultParams)
        params["header"] = self.AJAX_HEADER
        sts, data = self.getPage(self.getFullUrl("ajax.php"), params, post)
        return data if sts else ""

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"list_show": "series", "list_part": "season", "list_games": "series"}.get(cItem.get("category", ""), "")
            if cItem.get("type", "") == "video" or cItem.get("category", "") == "video":
                prefix = "video"
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
        # "Grand hotel (2024-2026)" -> ("Grand hotel", "2024")
        match = re.match(r"^(.*?)\s*\(((?:18|19|20)\d\d)[^)]*\)\s*$", title)
        return (match.group(1).strip(), match.group(2)) if match else (title.strip(), "")

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _section(url):
        return re.sub(r"^https?://[^/]+/", "", url).split("?", 1)[0].split("#", 1)[0]

    def _localPaging(self, cItem, rows, add):
        # rows of one page of a long local list + First / Jump / Next page
        page = self._page(cItem)
        lastPage = max(1, (len(rows) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE)
        page = min(page, lastPage)
        for row in rows[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]:
            add(row)
        if lastPage > 1:
            addPagingItems(self, cItem, page, page < lastPage, lastPage, cItem["url"].replace("{", "{{").replace("}", "}}"))

    def _addTitle(self, cItem, url, label, icon="", desc=""):
        label = self.cleanHtmlStr(label)
        url = self.getFullUrl(url)
        if not label or not url:
            return
        section = self._section(url)
        sTitle, year = self._splitYear(label)
        params = stripPagerKeys(dict(cItem), ("filter_url",))
        params.update({"good_for_fav": True, "url": url, "title": label, "icon": self.getFullIconUrl(icon) if icon else "", "desc": desc,
                       "s_title": sTitle, "s_year": year})
        if section == "sports.php":
            params["category"] = "list_games"
            self.addDir(params)
        elif section in ("series.php", "shows.php", "animation.php"):
            params.update({"category": "list_show", "meta_type": "tv"})
            self.addDir(params)
        else:
            if year and IsMediaNamingNormalized():
                params["title"] = "%s (%s)" % (sTitle, year)
            params.update({"category": "video", "meta_type": "movie"})
            self.addVideo(params)

    def _thumbs(self, data):
        # (url, icon, title) of the poster grid
        return re.findall(r"(?s)<a class='thumbnail' href='([^']+)'>.*?<img src='([^']*)'.*?<h4[^>]*>(.*?)</h4>", data)

    def _selects(self, data):
        # {param: [(title, url)]} of the filter boxes of a list page
        result = {}
        for block in re.findall(r"(?s)<select class='form-control'[^>]*onChange=[^>]*>(.*?)</select>", data):
            options = re.findall(r"""<option[^>]*value=["']([^"']+)["'][^>]*>([^<]*)</option>""", block)
            for url, title in options[1:]:
                key = self.cm.ph.getSearchGroups(url, r"[?&]([a-z])=[^&]")[0]
                if key and title.strip():
                    result.setdefault(key, []).append((self.cleanHtmlStr(title), self.getFullUrl(url.replace("&amp;", "&"))))
        return result

    def _pageInfo(self, data):
        # (info, title, year, icon, imdb) of a title page
        info = {}
        head = self.cm.ph.getDataBeetwenMarkers(data, "<div class='col-sm-7 col-md-8'>", "<div id='leaderboard'>", False)[1]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(head, r"<h2>(.*?)</h2>")[0])
        for label, value in re.findall(r"<h4[^>]*>([^<:]+):\s*(.*?)</h4>", head):
            key = INFO_FIELDS.get(self.cleanHtmlStr(label))
            value = self.cleanHtmlStr(value)
            if key and value:
                info[key] = value
        year = self.cm.ph.getSearchGroups(info.get("year", ""), r"((?:18|19|20)\d\d)")[0]
        icon = self.cm.ph.getSearchGroups(head, r'<img class="thumbnail[^"]*" src="([^"]+)"')[0]
        channel = self.cm.ph.getSearchGroups(head, r"<img src='icon/([a-z0-9]+)\.(?:jpg|png)'")[0]
        if channel:
            info["station"] = channel.upper()
        imdb = self.cm.ph.getSearchGroups(head, r"imdb\.com/title/(tt\d+)")[0]
        return info, title, year, self.getFullIconUrl(icon) if icon else "", imdb

    def _episodes(self, data):
        # numbered: [(season, label, epid)]; dated: [(date, epid)] (newest first, as the site)
        numbered, dated = [], []
        parts = re.split(r"<h4>(Ταξινόμηση[^<]*)</h4>", data)
        for idx in range(1, len(parts) - 1, 2):
            body = parts[idx + 1].split("<div class='pull-right'>", 1)[0]
            if "ημερομηνία" in parts[idx]:
                year = ""
                month = 0
                for yearTxt, monthTxt, epid, day in re.findall(r"(?:font-weight:bold;'>(\d{4})</h4>)|(?:width:50px;'>([^<]+)</div>)|(?:loadEpisode\('([^']+)',\s*'d'\)\">([^<]+)</button>)", body):
                    if yearTxt:
                        year = yearTxt
                    elif monthTxt:
                        month = MONTHS.get(monthTxt.strip(), 0)
                    elif epid:
                        dated.append(("%s-%02d-%02d" % (year, month, int(day)) if (month and day.strip().isdigit()) else "%s %s" % (year, day.strip()), epid))
            else:
                for group in re.split(r"<div style='margin-left: 10px;[^']*'>", body)[1:]:
                    for epid, label in re.findall(r"loadEpisode\('([^']+)',\s*'n'\)\">([^<]+)</button>", group):
                        label = label.strip()
                        season = label.split(".", 1)[0] if "." in label else ""
                        numbered.append((season, label, epid))
        return numbered, dated

    ###################################################
    # lists
    ###################################################
    def listSection(self, cItem):
        printDBG("GreekMovies.listSection |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        section = self._section(cItem["url"])
        if section != "sports.php":
            # sport: the competitions of the start page are listed below the filters
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "list_recent", "title": _("Recently added"), "desc": ""})
            self.addDir(params)
        selects = self._selects(data)
        titles = {"y": _("Year"), "l": _("A-Z"), "g": _("Genres"), "c": _("Channels"), "p": _("Country"), "s": _("Sport")}
        for key in FILTER_KEYS:
            title = titles[key]
            if key in selects:
                params = stripPagerKeys(dict(cItem))
                params.update({"good_for_fav": True, "category": "list_filter", "title": title, "filter_key": key, "desc": ", ".join(t for t, _u in selects[key][:6])})
                self.addDir(params)
        if section == "sports.php":
            self.listItems(dict(cItem, category="list_items"), data)

    def listRecent(self, cItem):
        printDBG("GreekMovies.listRecent |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        if "class='u2'" in data:
            # series / shows / animation: "Πρόσφατες καταχωρήσεις" by day, a title with its new episodes
            seen, rows = set(), []
            for url, title, eps in re.findall(r"""<p class='u2'><a href=["']([^"']+)["']>([^<]+)</a>\s*-\s*([^<]*)""", data):
                if url not in seen:
                    seen.add(url)
                    rows.append((url, title, eps))
            self._localPaging(cItem, rows, lambda r: self._addTitle(cItem, r[0], r[1], desc="%s: %s" % (_("New episodes"), self.cleanHtmlStr(r[2]))))
            return
        for url, icon, title in self._thumbs(data):
            self._addTitle(cItem, url, title, icon)

    def listFilter(self, cItem):
        printDBG("GreekMovies.listFilter |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        key = cItem.get("filter_key", "")
        needsYear = self._section(cItem["url"]) in NEEDS_YEAR and key != "y"
        for title, url in self._selects(data).get(key, []):
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "title": title, "url": url, "desc": ""})
            if needsYear:
                # the list of a letter / genre / country is per year range
                params.update({"category": "list_years", "filter_url": url})
            else:
                params["category"] = "list_items"
            self.addDir(params)

    def listYears(self, cItem):
        printDBG("GreekMovies.listYears |%s|" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        base = cItem.get("filter_url", "") or cItem["url"]
        for title, url in self._selects(data).get("y", []):
            year = self.cm.ph.getSearchGroups(url, r"[?&]y=(\d+)")[0]
            params = stripPagerKeys(dict(cItem), ("filter_url",))
            params.update({"good_for_fav": True, "category": "list_items", "title": "%s - %s" % (cItem["title"], title),
                           "url": re.sub(r"([?&])y=\d*", r"\1y=%s" % year, base) if re.search(r"[?&]y=", base) else "%s&y=%s" % (base, year)})
            self.addDir(params)

    def listItems(self, cItem, data=None):
        printDBG("GreekMovies.listItems |%s|" % cItem)
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        rows = self._thumbs(data)
        if not rows:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        self._localPaging(cItem, rows, lambda r: self._addTitle(cItem, r[0], r[2], r[1]))

    def listShow(self, cItem):
        # a series / show: seasons of the numbered list, else the years of the dated one
        printDBG("GreekMovies.listShow |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        info, title, year, icon, _imdb = self._pageInfo(data)
        numbered, dated = self._episodes(data)
        fields = {"s_title": cItem.get("s_title", "") or title, "s_year": cItem.get("s_year", "") or year, "icon": cItem.get("icon", "") or icon,
                  "desc": " | ".join(info[k] for k in ("year", "station", "genre") if info.get(k))}
        if numbered:
            seasons = []
            for season, _label, _epid in numbered:
                if season not in seasons:
                    seasons.append(season)
            if len(seasons) == 1:
                # list_part: the pager rows of a long season open the season, not the show again
                self.listPart(dict(cItem, category="list_part", url="%s#s%s" % (url, seasons[0]), **fields), data)
                return
            normalize = IsMediaNamingNormalized()
            for season in seasons:
                count = len([1 for s, _l, _e in numbered if s == season])
                if not season.isdigit():
                    # an unnumbered part next to numbered seasons (specials)
                    tag = season or _("Episodes")
                else:
                    tag = formatSxxExx(season) if normalize else "%s %d" % (_("Season"), int(season))
                params = stripPagerKeys(dict(cItem))
                params.update(fields)
                params.update({"good_for_fav": True, "category": "list_part", "title": "%s - %s" % (fields["s_title"], tag), "url": "%s#s%s" % (url, season),
                               "desc": "%s: %d[/br]%s" % (_("Episodes"), count, fields["desc"])})
                self.addDir(params)
        elif dated:
            years = []
            for date, _epid in dated:
                if date[:4] not in years:
                    years.append(date[:4])
            if len(years) == 1:
                self.listPart(dict(cItem, category="list_part", url="%s#y%s" % (url, years[0]), **fields), data)
                return
            for yearTxt in years:
                count = len([1 for d, _e in dated if d[:4] == yearTxt])
                params = stripPagerKeys(dict(cItem))
                params.update(fields)
                params.update({"good_for_fav": True, "category": "list_part", "title": "%s - %s" % (fields["s_title"], yearTxt), "url": "%s#y%s" % (url, yearTxt),
                               "desc": "%s: %d[/br]%s" % (_("Episodes"), count, fields["desc"])})
                self.addDir(params)
        else:
            SetIPTVPlayerLastHostError(_("No stream available"))

    def listPart(self, cItem, data=None):
        # the episodes of one season (#s<n>) or of one year (#y<yyyy>)
        printDBG("GreekMovies.listPart |%s|" % cItem)
        url, _sep, frag = cItem["url"].partition("#")
        if data is None:
            sts, data = self.getPage(url)
            if not sts:
                return
            _info, title, year, icon, _imdb = self._pageInfo(data)
            cItem = dict(cItem, s_title=cItem.get("s_title", "") or title, s_year=cItem.get("s_year", "") or year, icon=cItem.get("icon", "") or icon)
        numbered, dated = self._episodes(data)
        dates = dict((epid, date) for date, epid in dated)
        sTitle = cItem.get("s_title", "") or cItem["title"]
        normalize = IsMediaNamingNormalized()
        rows = []
        if frag.startswith("s"):
            for season, label, epid in numbered:
                if season != frag[1:]:
                    continue
                episode = label.split(".", 1)[1] if "." in label else label
                if normalize and episode.isdigit():
                    title = "%s - %s" % (sTitle, formatSxxExx(season or 1, episode))
                else:
                    title = "%s - %s %s" % (sTitle, _("Episode"), label)
                rows.append((title, epid, dates.get(epid, ""), season, episode))
        else:
            for date, epid in dated:
                if date[:4] == frag[1:]:
                    # ajax.php answers an episode of the dated list with view=d only
                    rows.append(("%s - %s" % (sTitle, date), "%s&v=d" % epid, date, "", ""))

        def add(row):
            title, epid, date, season, episode = row
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "video", "title": title, "url": "%s#ep=%s" % (url, epid), "s_title": sTitle,
                           "season": season, "episode": episode, "desc": date or cItem.get("desc", "")})
            self.addVideo(params)
        self._localPaging(cItem, rows, add)

    def listGames(self, cItem):
        printDBG("GreekMovies.listGames |%s|" % cItem)
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        rows = []
        for when, gameId, teams in re.findall(r"(?s)<span class='pull-right'>([^<]*)</span>.*?loadLinks\('([^']+)'\)\">([^<]+)</button>", data):
            rows.append((self.cleanHtmlStr(teams), gameId, self.cleanHtmlStr(when)))
        if not rows:
            SetIPTVPlayerLastHostError(_("No stream available"))

        def add(row):
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "video", "title": row[0], "url": "%s#game=%s" % (url, row[1]), "desc": row[2], "meta_type": ""})
            self.addVideo(params)
        self._localPaging(cItem, rows, add)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("GreekMovies.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        post = {"searchcategory": searchType or "movies", "searchtext": searchPattern.strip()}
        sts, data = self.getPage(self.getFullUrl("search.php"), dict(self.defaultParams), post)
        if not sts:
            return
        for url, icon, title in self._thumbs(data):
            self._addTitle(cItem, url, title, icon)

    ###################################################
    # links
    ###################################################
    def _parseLinks(self, html):
        # [(hoster label, view.php url)] - "προβολή στο X: <a>1</a> <a>2</a>" are the parts of one video
        links = []
        for label, parts in re.findall(r"(?s)<p[^>]*>\s*([^<:]+):\s*(.*?)</p>", html):
            for viewUrl, num in re.findall(r"""href=["'](view\.php\?v=[^"']+)["'][^>]*>\s*(\d+)\s*<""", parts):
                links.append(("%s - %s %s" % (self._hoster(label), _("Part"), num), viewUrl, self._hoster(label)))
        html = re.sub(r"(?s)<p[^>]*>\s*[^<:]+:\s*.*?</p>", "", html)
        for viewUrl, label in re.findall(r"""href=["'](view\.php\?v=[^"']+)["'][^>]*>([^<]+)<""", html):
            links.append((self._hoster(label), viewUrl, self._hoster(label)))
        return links

    def _hoster(self, label):
        # "προβολή στο Dailymotion" / "προβολή σε YouTube" -> "Dailymotion" / "YouTube"
        return re.sub(r"^\s*προβολή\s+σ\S*\s+", "", self.cleanHtmlStr(label)).strip()

    def getLinksForVideo(self, cItem):
        printDBG("GreekMovies.getLinksForVideo [%s]" % cItem)
        pageUrl, _sep, frag = cItem.get("url", "").partition("#")
        imdb = ""
        if frag.startswith("ep="):
            epid, _sep, view = frag[3:].partition("&v=")
            html = self._ajax({"type": "episode", "epid": epid, "view": view or "n"})
        elif frag.startswith("game="):
            html = self._ajax({"type": "sports_game", "game_id": frag[5:]})
        else:
            sts, data = self.getPage(pageUrl)
            html = self.cm.ph.getDataBeetwenMarkers(data, "Video</h3>", "<div class='pull-right'>", False)[1] if sts else ""
            imdb = self._pageInfo(data)[4] if sts else ""
        bitchute = self.up.checkHostSupport("https://www.bitchute.com/video/x/") == 1
        world, geo, counts = [], [], {}
        for name, viewUrl, hoster in self._parseLinks(html):
            key = hoster.lower()
            if key == "bit chute" and not bitchute:
                continue
            counts[name] = counts.get(name, 0) + 1
            label = name if counts[name] == 1 else "%s %d" % (name, counts[name])
            link = {"name": label, "url": strwithmeta(self.getFullUrl(viewUrl), {"Referer": self.MAIN_URL}), "need_resolve": 1}
            if key in WORLD_HOSTS:
                world.append(link)
            else:
                link["name"] = "%s (geo)" % label
                geo.append(link)
        urltab = world + geo
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        mediaType = cItem.get("meta_type", "")
        if mediaType in ("movie", "tv") and (imdb or cItem.get("s_year")):
            # as INFO: a title without a year is no lookup
            metaQuery = sidecarMetaQuery(mediaType, cItem.get("s_title", "") or cItem.get("title", ""), cItem.get("s_year", ""), imdbId=imdb)
        else:
            metaQuery = {}
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), cItem.get("desc", ""), metaQuery))

    def _broadcaster(self, url):
        # the video of a broadcaster's page: OPEN's player JSON, Alpha's data-video-url, else an HLS / MP4 url of the page
        links = []
        cid = self.cm.ph.getSearchGroups(url, r"tvopen\.gr/watch/(\d+)")[0]
        if cid:
            sts, data = self.getPage("https://www.tvopen.gr/templates/data/player?cid=%s" % cid)
            try:
                js = json_loads(data) if sts else {}
                for key, name in (("stream", "HLS"), ("httpstream", "MP4")):
                    if js.get(key):
                        links.append({"name": "OPEN %s" % name, "url": strwithmeta(ensure_str(js[key]), {"Referer": url})})
            except Exception:
                printExc()
            return links
        sts, data = self.getPage(url)
        if not sts:
            return links
        found = re.findall(r"""data-video-url=["']([^"']+)["']""", data) + re.findall(r"""(https?://[^"'\s<>\\]+\.(?:m3u8|mp4)(?:\?[^"'\s<>\\]*)?)""", data)
        for src in found:
            src = src.replace("&amp;", "&")
            if src not in [str(x["url"]) for x in links]:
                links.append({"name": "%s %s" % (re.sub(r"^www\.", "", self.up.getDomain(url)), "HLS" if ".m3u8" in src else "MP4"), "url": strwithmeta(src, {"Referer": url})})
        return links[:2]

    def getVideoLinks(self, videoUrl):
        printDBG("GreekMovies.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        target = str(videoUrl)
        if "greek-movies.com/view.php" in target:
            sts, data = self.getPage(target)
            target = self.cm.ph.getSearchGroups(data, r"class='btn btn-primary' role='button' href='([^']+)'")[0].replace("&amp;", "&") if sts else ""
            printDBG("GreekMovies.getVideoLinks -> [%s]" % target)
            if not self.cm.isValidUrl(target):
                SetIPTVPlayerLastHostError(_("No stream available"))
                return []
        if self.up.checkHostSupport(target) == 1:
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(target), sidecar)
        links = self._broadcaster(target)
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("GreekMovies.getArticleContent [%s]" % cItem)
        url = cItem.get("url", "").split("#", 1)[0]
        info, title, year, icon, imdb = {}, "", "", "", ""
        sts, data = self.getPage(url)
        if sts:
            info, title, year, icon, imdb = self._pageInfo(data)
        mediaType = cItem.get("meta_type", "")
        meta = {}
        try:
            if mediaType in ("movie", "tv") and imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            metaTitle = cItem.get("s_title", "") or title
            if not meta and mediaType in ("movie", "tv") and metaTitle and (cItem.get("s_year") or year):
                # a Greek title: not to the services that answer it with unrelated hits (as the sidecar lookup)
                meta = getMeta(mediaType, metaTitle, cItem.get("s_year", "") or year, skip=() if isLatinTitle(metaTitle) else LATIN_ONLY)
        except Exception:
            printExc()
        meta = meta or {}
        metaInfo = dict(meta.get("info", {}))
        for siteKey, metaKey in (("cast", "cast"), ("director", "directors"), ("writer", "writers"), ("genre", "genres")):
            if metaKey in metaInfo:
                info.pop(siteKey, None)
        metaInfo.update(info)
        text = cItem.get("desc", "") if "#" in cItem.get("url", "") else ""
        plot = meta.get("plot", "")
        text = "%s[/br][/br]%s" % (text, plot) if (text and plot) else (text or plot)
        if not text:
            # the site has no plot: title and the main fields
            text = " | ".join(x for x in (title or cItem.get("title", ""), info.get("year", ""), info.get("genre", ""), info.get("duration", "")) if x)
        icon = cItem.get("icon", "") or icon or meta.get("poster", "")
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
        elif category == "list_section":
            self.listSection(self.currItem)
        elif category == "list_recent":
            self.listRecent(self.currItem)
        elif category == "list_filter":
            self.listFilter(self.currItem)
        elif category == "list_years":
            self.listYears(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_show":
            self.listShow(self.currItem)
        elif category == "list_part":
            self.listPart(self.currItem)
        elif category == "list_games":
            self.listGames(self.currItem)
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
        CHostBase.__init__(self, GreekMovies(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("greekmovies")

    def getSearchTypes(self):
        return [(_("Movies"), "movies"), (_("Series"), "series"), (_("Shows"), "shows"), (_("Animation"), "animation"), ("Theatre", "theater")]

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_show", "list_part")
