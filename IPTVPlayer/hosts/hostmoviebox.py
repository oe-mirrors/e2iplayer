# -*- coding: utf-8 -*-
# MovieBox (officialmoviebox.com)
# Catalogue: Nuxt pages of officialmoviebox.com (__NUXT_DATA__) + the wefeed H5 API on h5-api.aoneroom.com
# Football Live: h5-sport-api.aoneroom.com (the sportslive.wine web app)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase, RetHost
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxItem
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, GetSubtitlesDir, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode, urllib_unquote
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse, parse_qs
###################################################
# FOREIGN import
###################################################
import base64
import os
import re
import time
###################################################

Y, W, L, C, OR = (E2ColoR("yellow"), E2ColoR("white"), E2ColoR("lime"), E2ColoR("cyan"), E2ColoR("orange"))


def GetConfigList():
    return []


def gettytul():
    return "https://officialmoviebox.com/"


class MovieBox(GenericFolderWatchedScraperMixin, CBaseHostClass):
    MAIN_URL = "https://officialmoviebox.com"
    API = "https://h5-api.aoneroom.com/wefeed-h5api-bff"
    SPORT_API = "https://h5-sport-api.aoneroom.com/wefeed-h5api-bff"
    SPORT_URL = "https://www.sportslive.wine/"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    # search type -> subjectType of /subject/search (0 = everything)
    SEARCH_TYPES = {"all": 0, "movies": 1, "series": 2}
    # general Most Watched lists; the site's own ranking-list page only offers the anime lists (added behind these)
    RANKING_LISTS = [
        ("Popular", "1232643093049001320"), ("TOP100", "6159907949583500480"), ("Anime", "62133389738001440"),
        ("K-Drama", "4380734070238626200"), ("Black Drama", "8505361996374835640"), ("SA Drama", "1503943377597910848"),
        ("C-Drama", "173752404280836544"), ("Thai-Drama", "1164329479448281992"), ("New", "2529702013798074864"),
        ("Returnings", "8109661952110199232"), ("Action", "6978603205429526968"), ("Fantasy", "7219449993227633120"),
        ("Sci-Fi", "4075118481979722960"), ("Superhero", "7317586330186645624"), ("Romance", "2389813900859556536"),
        ("Comedy", "8785384881686725944"), ("Period", "1826888755169346232"), ("Teen Romance", "1746633591129342248"),
        ("Teen Fantasy", "6934224112055632896"), ("Cop Drama", "8897504261530175160"), ("Medical Drama", "4162236365956153536"),
        ("Animation", "3130672938110833528"),
    ]
    # the favourite data of a title: what identifies it and is needed to open it again (see getFavouriteData)
    FAV_FIELDS = ("name", "category", "type", "url", "subjectId", "subjectType", "detailPath", "s_title", "season", "episode", "desc", "icon")
    # devalue wrappers Nuxt puts around reactive values: ["Reactive", <index>]
    NUXT_WRAPPERS = ("Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef", "NuxtError")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "MovieBox", "cookie": "MovieBox.cookie"})
        self.DEFAULT_ICON_URL = self.MAIN_URL + "/logo.png"
        self.HEADER = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": self.MAIN_URL,
            "Referer": self.MAIN_URL + "/",
            "x-request-lang": "en",
        }
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.token = ""
        self.detailCache = {}
        self.watchedHelper = IPTVWatchedHelper("moviebox")
        self.wfInitFolderCache()
        self.MAIN_CAT_TAB = [
            {"category": "list_sections", "title": _("Home / Sections")},
            {"category": "list_filter_page", "title": _("Movies"), "page_url": "/web/film", "channel_id": 1},
            {"category": "list_filter_page", "title": _("TV Shows"), "page_url": "/newWeb/tv-series", "channel_id": 2},
            {"category": "list_filter_page", "title": _("Animation"), "page_url": "/newWeb/animated-series", "channel_id": 1006},
            {"category": "list_most_watched_tabs", "title": _("Most Watched")},
            {"category": "list_upcoming_tabs", "title": _("Upcoming")},
            {"category": "list_football_live", "title": _("Football Live")},
        ] + self.searchItems()

    ###################################################
    # HTTP
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        params = dict(self.defaultParams if addParams is None else addParams)
        params["header"] = dict(params.get("header") or self.HEADER)
        return self.cm.getPageCFProtection(url, params, post_data)

    def _api(self, endpoint, query=None, post=None, base=None, auth=True, referer=None):
        url = (base or self.API) + endpoint
        if query:
            url += "?" + urllib_urlencode(query)
        header = dict(self.HEADER)
        header.update({"Accept": "application/json", "Referer": referer or self.MAIN_URL + "/"})
        if auth:
            header["Authorization"] = "Bearer %s" % self.getBearerToken()
        params = dict(self.defaultParams)
        params.update({"header": header, "collect_all_headers": True})
        post_data = None
        if post is not None:
            header["Content-Type"] = "application/json"
            params["raw_post_data"] = True
            post_data = json_dumps(post)
        sts, data = self.cm.getPage(url, params, post_data)
        if not sts:
            printDBG("MovieBox._api failed: %s" % url)
            return {}
        self._takeTokenFromHeaders(getattr(data, "meta", None) or self.cm.meta)
        try:
            data = json_loads(data)
        except Exception:
            printExc("MovieBox._api JSON error: %s" % url)
            return {}
        if data.get("code") != 0:
            printDBG("MovieBox._api %s -> code %s: %s" % (endpoint, data.get("code"), data.get("message")))
            return {}
        return data.get("data") or {}

    ###################################################
    # guest token: every API answer carries it in the x-user header (and as the "token" cookie)
    ###################################################
    def _takeTokenFromHeaders(self, meta):
        try:
            token = json_loads((meta or {}).get("x-user", "") or "{}").get("token", "")
        except Exception:
            token = ""
        if token and self._isTokenValid(token):
            self.token = token

    def _isTokenValid(self, token):
        try:
            payload = token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            exp = json_loads(base64.urlsafe_b64decode(payload.encode("ascii"))).get("exp", 0)
            return time.time() < exp - 3600
        except Exception:
            return False

    def _cookieToken(self):
        # pCommon logs two tracebacks for a cookie file that does not exist yet (first start)
        if not os.path.isfile(self.COOKIE_FILE):
            return ""
        return urllib_unquote(self.cm.getCookieItem(self.COOKIE_FILE, "token") or "").strip('"')

    def getBearerToken(self):
        if self.token and self._isTokenValid(self.token):
            return self.token
        token = self._cookieToken()
        if token and self._isTokenValid(token):
            self.token = token
            return token
        printDBG("MovieBox: fetching a new guest token")
        self.token = ""
        self._api("/subject/filter", post={"page": 1, "perPage": 1, "channelId": 1}, auth=False)
        if not self.token:
            token = self._cookieToken()
            if self._isTokenValid(token):
                self.token = token
        if not self.token:
            printDBG("MovieBox: no guest token")
        return self.token

    ###################################################
    # Nuxt payload (__NUXT_DATA__ is a flat devalue array: every value inside an object/list is an index)
    ###################################################
    def _nuxtData(self, html):
        match = re.search(r'id="__NUXT_DATA__"[^>]*>(\[[\s\S]*?)\s*</script>', html or "")
        if not match:
            printDBG("MovieBox: no __NUXT_DATA__")
            return []
        try:
            data = json_loads(match.group(1))
        except Exception:
            printExc()
            return []
        return data if isinstance(data, list) else []

    def _nuxtValue(self, nuxt, idx, depth=0):
        if depth > 15 or isinstance(idx, bool) or not isinstance(idx, int) or not 0 <= idx < len(nuxt):
            return None
        value = nuxt[idx]
        if isinstance(value, dict):
            return dict((k, self._nuxtValue(nuxt, v, depth + 1)) for k, v in value.items())
        if isinstance(value, list):
            if len(value) == 2 and value[0] in self.NUXT_WRAPPERS:
                return self._nuxtValue(nuxt, value[1], depth + 1)
            if len(value) == 2 and value[0] == "Date":
                return value[1]
            return [self._nuxtValue(nuxt, v, depth + 1) for v in value]
        return value

    def _nuxtFind(self, nuxt, key):
        # value of the first object in the payload that has this key
        for item in nuxt:
            if isinstance(item, dict) and key in item:
                return self._nuxtValue(nuxt, item[key])
        return None

    ###################################################
    # list helpers
    ###################################################
    def _addNextPage(self, cItem, page):
        params = dict(cItem)
        params.update({"good_for_fav": False, "title": _("Next page"), "page": page + 1})
        self.addDir(params)

    def _addSubjects(self, cItem, subjects):
        # the API lists one entry per season of a series ("Breaking Bad S1" ... "S5"), all with the same
        # subjectId - they open the same seasons list, so the series is shown once, with the release date of
        # its first season (the year of "Title (Year)")
        entries = {}
        order = []
        for subj in subjects or []:
            if not isinstance(subj, dict) or not subj.get("subjectId") or not subj.get("title"):
                continue
            sid = str(subj["subjectId"])
            if sid not in entries:
                entries[sid] = dict(subj)
                order.append(sid)
            elif subj.get("releaseDate") and str(subj["releaseDate"]) < str(entries[sid].get("releaseDate") or "9999"):
                entries[sid]["releaseDate"] = subj["releaseDate"]
                entries[sid]["season"] = subj.get("season")
        for sid in order:
            self._addSubject(cItem, entries[sid])
        return len(order)

    def _addSubject(self, cItem, subj):
        subjectType = subj.get("subjectType") or 1
        title = self.cleanHtmlStr(str(subj.get("title") or ""))
        if subjectType == 2:
            # "Breaking Bad S5" / "Prison Break S1-S5": the seasons list covers the whole series
            title = re.sub(r"\s+S\d+(?:\s*-\s*S\d+)?$", "", title)
        cover = subj.get("cover")
        icon = cover.get("url", "") if isinstance(cover, dict) else (cover or "")
        stills = subj.get("stills")
        trailer = subj.get("trailer")
        trailerUrl = ""
        if isinstance(trailer, dict) and isinstance(trailer.get("videoAddress"), dict):
            trailerUrl = trailer["videoAddress"].get("url", "") or ""
        releaseDate = str(subj.get("releaseDate") or "")
        year = releaseDate[:4] if releaseDate[:4].isdigit() else ""
        try:
            season = int(subj.get("season") or 0)
        except (TypeError, ValueError):
            season = 0
        if subjectType == 2 and season > 1:
            # only a later season of the series is in this list ("Title S5"): its date is not the series' year
            year = ""
        try:
            minutes = int(subj.get("duration") or 0) // 60
        except (TypeError, ValueError):
            minutes = 0
        info = []
        if subj.get("imdbRatingValue"):
            info.append("%sIMDb: %s" % (L, subj["imdbRatingValue"]))
        for value in (year, subj.get("countryName")):
            if value:
                info.append(str(value))
        if subj.get("genre"):
            info.append("%s%s" % (Y, subj["genre"]))
        for value in (releaseDate, subj.get("corner")):
            if value:
                info.append(str(value))
        story = self.cleanHtmlStr(str(subj.get("description") or ""))
        desc = " | ".join(info)
        if subj.get("hasResource") is False:
            desc += "\n%s%s" % (OR, _("Not available yet"))
        if story:
            desc += "\n\n%sStory: %s" % (C, story)
        item = {
            "subjectId": str(subj["subjectId"]),
            "subjectType": subjectType,
            "detailPath": subj.get("detailPath") or "",
        }
        item.update({
            # a fresh item: copying cItem would drag banner lists, filter state etc. into every title (and its favourite)
            "name": cItem.get("name", "category"),
            "url": self._titleUrl(item),
            "title": self._titleWithYear(title, year),
            "s_title": title,
            "year": year,
            "genre": str(subj.get("genre") or ""),
            "country": str(subj.get("countryName") or ""),
            "imdb": str(subj.get("imdbRatingValue") or ""),
            "duration": minutes,
            "subtitles_info": str(subj.get("subtitles") or ""),
            "stills": stills.get("url", "") if isinstance(stills, dict) else "",
            "icon": self.getFullIconUrl(icon) if icon else "",
            "desc": desc,
            "txt": story,
            "trailer_url": trailerUrl,
            "good_for_fav": True,
        })
        if subjectType == 2:
            item["category"] = "list_seasons"
            self.addDir(item)
        else:
            # a movie is a video of its own: watched flag, download and favourite marker sit on its row
            item["category"] = ""
            self.addVideo(item)

    def _titleWithYear(self, title, year):
        # media-server friendly "Title (Year)" when the global naming switch is on (the download file name follows the title)
        if year and IsMediaNamingNormalized() and ("(%s)" % year) not in title:
            return "%s (%s)" % (title, year)
        return title

    ###################################################
    # watched flag / favourites / INFO
    ###################################################
    def _titleUrl(self, cItem, season=None, episode=None):
        # the stable page url of a title (season / episode appended) - the stream urls are signed and change on every
        # request, so the watched flag, the download marker and the favourite identity are keyed by this one
        url = "%s/movies/%s?id=%s" % (self.MAIN_URL, cItem.get("detailPath", ""), cItem.get("subjectId", ""))
        if season is not None:
            url += "&se=%d" % season
        if episode is not None:
            url += "&ep=%d" % episode
        return url

    def _getWatchedKeyForItem(self, cItem):
        # movies and episodes are marked themselves; series and season folders get their state from their
        # episodes (GenericFolderWatchedScraperMixin); trailers, football and navigation entries have none
        try:
            if not isinstance(cItem, dict) or not cItem.get("subjectId") or cItem.get("is_trailer"):
                return ""
            url = str(cItem.get("url", "") or "")
            if url == "":
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            if cItem.get("category", "") in ("list_seasons", "list_episodes"):
                return "folder:%s" % url
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        # only what identifies the title and is needed to open it again: the same movie comes with a different
        # title year / trailer / rating from the different lists and must still be recognised as the same favourite
        try:
            if cItem.get("subjectId"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def getArticleContent(self, cItem):
        printDBG("MovieBox.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("s_title") or cItem.get("title", "")
        text = cItem.get("txt", "")
        if not text and cItem.get("detailPath"):
            text = self._getDetail(cItem)["story"]
        other = {}
        if cItem.get("subjectType") == 2:
            other["type"] = _("Series")
        elif cItem.get("subjectId"):
            other["type"] = _("Movie")
        if cItem.get("season"):
            # "Seasons:"/"Episodes:" of the article view read as counts - the position goes into the title instead
            title = "%s - %s" % (title, formatSxxExx(cItem["season"], cItem.get("episode")))
        for key, field in (("year", "year"), ("genres", "genre"), ("country", "country"), ("imdb_rating", "imdb"), ("subtitles", "subtitles_info")):
            if cItem.get(field):
                other[key] = str(cItem[field])
        if cItem.get("duration"):
            other["duration"] = "%d min" % cItem["duration"]
        # the article view shows the first image as its cover: the poster, then the scene still
        images = [{"title": "", "url": url} for url in (cItem.get("icon"), cItem.get("stills")) if url]
        return [{"title": title, "text": text or cItem.get("desc", ""), "images": images, "other_info": other}]

    ###################################################
    # Home / Sections
    ###################################################
    def listSections(self, cItem):
        printDBG("MovieBox.listSections")
        sts, data = self.getPage(self.MAIN_URL + "/")
        if not sts:
            return
        operatingList = self._nuxtFind(self._nuxtData(data), "operatingList") or []
        seen = set()
        for op in operatingList:
            if not isinstance(op, dict):
                continue
            opType = str(op.get("type") or "")
            title = str(op.get("title") or "").strip()
            if not title or title in seen or opType in ("SPORT_LIVE", "CUSTOM", "FILTER"):
                continue
            seen.add(title)
            params = dict(cItem)
            params.update({"title": title, "good_for_fav": True})
            if opType in ("BANNER", "APPOINTMENT_LIST"):
                if opType == "BANNER":
                    items = ((op.get("banner") or {}).get("items") or [])
                    subjects = [it.get("subject") for it in items if isinstance(it, dict)]
                else:
                    subjects = op.get("subjects") or []
                subjects = [s for s in subjects if isinstance(s, dict) and s.get("subjectId")]
                if not subjects:
                    continue
                # a snapshot of the home page (the subjects themselves are in the item) - no favourite
                params.update({"category": "list_section_banner", "_banner_items": subjects, "good_for_fav": False})
            else:
                # PLAY_LIST, SUBJECTS_MOVIE and unknown types: the ranking list behind the section
                rankingId = str(op.get("genreTopId") or op.get("opId") or "")
                if not rankingId:
                    continue
                params.update({"category": "list_ranking_content", "ranking_id": rankingId})
            self.addDir(params)

    def listSectionBanner(self, cItem):
        self._addSubjects(cItem, cItem.get("_banner_items", []))

    ###################################################
    # Movies / TV Shows / Animation with filters
    ###################################################
    def _filterPost(self, cItem, page):
        post = {"page": page, "perPage": 36, "channelId": int(cItem["channel_id"]), "sort": "ForYou"}
        post.update(cItem.get("anim_filter") or {})
        return post

    def listFilterPage(self, cItem):
        printDBG("MovieBox.listFilterPage [%s]" % cItem.get("title", ""))
        page = cItem.get("page", 1)
        if cItem.get("selected_filter_type"):
            self._listFilterPageOptions(cItem)
            return
        if cItem.get("show_filters"):
            self._listFilterPageCategories(cItem, cItem.get("_filter_groups", {}))
            return
        if page == 1 and not cItem.get("_apply_filter"):
            self._addFilterEntry(cItem)
        data = self._api("/subject/filter", post=self._filterPost(cItem, page))
        self._addSubjects(cItem, data.get("items"))
        if (data.get("pager") or {}).get("hasMore"):
            self._addNextPage(cItem, page)

    def _addFilterEntry(self, cItem):
        sts, data = self.getPage(self.MAIN_URL + cItem["page_url"])
        if not sts:
            return
        groups = {}
        nuxt = self._nuxtData(data)
        for idx, item in enumerate(nuxt):
            if not (isinstance(item, dict) and "filterType" in item and "filterVals" in item):
                continue
            item = self._nuxtValue(nuxt, idx)
            options = [{"name": str(v.get("name")), "id": str(v.get("id"))} for v in item.get("filterVals") or [] if isinstance(v, dict) and v.get("name")]
            if options and item.get("filterType"):
                groups[str(item["filterType"])] = {"title": str(item.get("title") or item["filterType"]), "options": options}
        if groups:
            params = dict(cItem)
            params.update({"title": "%s%s" % (Y, _("Filter")), "_filter_groups": groups, "show_filters": True, "good_for_fav": False})
            self.addDir(params)

    def _listFilterPageCategories(self, cItem, groups):
        current = cItem.get("anim_filter") or {}
        for ft, fdata in groups.items():
            selected = _("All")
            for opt in fdata["options"]:
                if opt["id"] == str(current.get(ft, "")):
                    selected = opt["name"]
            params = dict(cItem)
            params.update({"category": "list_filter_page", "title": "%s: %s%s" % (fdata["title"], L, selected), "selected_filter_type": ft,
                           "_filter_groups": groups, "anim_filter": current, "show_filters": False, "good_for_fav": False})
            self.addDir(params)
        if current:
            names = []
            for ft, fid in current.items():
                fdata = groups.get(ft, {})
                value = fid
                for opt in fdata.get("options", []):
                    if opt["id"] == str(fid):
                        value = opt["name"]
                names.append("%s=%s" % (fdata.get("title", ft), value))
            params = dict(cItem)
            params.update({"category": "list_filter_page", "title": "%s%s (%s)" % (Y, _("Show results"), ", ".join(names)), "anim_filter": current,
                           "_apply_filter": True, "show_filters": False, "selected_filter_type": "", "page": 1, "good_for_fav": False})
            self.addDir(params)

    def _listFilterPageOptions(self, cItem):
        groups = cItem.get("_filter_groups", {})
        ft = cItem["selected_filter_type"]
        current = dict(cItem.get("anim_filter") or {})
        for opt in groups.get(ft, {}).get("options", []):
            newFilter = dict(current)
            if opt["name"].lower() == "all":
                newFilter.pop(ft, None)
            else:
                newFilter[ft] = opt["id"]
            prefix = "✓ " if str(current.get(ft, "")) == opt["id"] else ""
            params = dict(cItem)
            params.update({"category": "list_filter_page", "title": prefix + opt["name"], "anim_filter": newFilter, "_filter_groups": groups,
                           "selected_filter_type": "", "show_filters": True, "good_for_fav": False})
            self.addDir(params)

    ###################################################
    # Most Watched / ranking lists
    ###################################################
    def listMostWatchedTabs(self, cItem):
        printDBG("MovieBox.listMostWatchedTabs")
        tabs = list(self.RANKING_LISTS)
        seen = set(rankingId for _title, rankingId in tabs)
        sts, data = self.getPage(self.MAIN_URL + "/ranking-list")
        if sts:
            nuxt = self._nuxtData(data)
            for idx, item in enumerate(nuxt):
                if not (isinstance(item, dict) and "rankingList" in item):
                    continue
                block = self._nuxtValue(nuxt, idx) or {}
                for tab in block.get("rankingList") or []:
                    if isinstance(tab, dict) and tab.get("name") and tab.get("id") and str(tab["id"]) not in seen:
                        seen.add(str(tab["id"]))
                        name = str(tab["name"])
                        if block.get("title"):
                            name = "%s - %s" % (block["title"], name)
                        tabs.append((name, str(tab["id"])))
        for title, rankingId in tabs:
            params = dict(cItem)
            params.update({"category": "list_ranking_content", "title": title, "ranking_id": rankingId, "good_for_fav": True})
            self.addDir(params)

    def listRankingContent(self, cItem):
        printDBG("MovieBox.listRankingContent [%s]" % cItem.get("title", ""))
        page = cItem.get("page", 1)
        data = self._api("/ranking-list/content", {"id": cItem.get("ranking_id", ""), "page": page, "perPage": 30})
        self._addSubjects(cItem, data.get("subjectList"))
        if (data.get("pager") or {}).get("hasMore"):
            self._addNextPage(cItem, page)

    ###################################################
    # Upcoming
    ###################################################
    def listUpcomingTabs(self, cItem):
        for title, category in (("Movie", "movie"), ("TV", "tv"), ("Anime", "anime")):
            params = dict(cItem)
            params.update({"category": "list_upcoming", "title": title, "upcoming_category": category, "good_for_fav": True})
            self.addDir(params)

    def listUpcoming(self, cItem):
        printDBG("MovieBox.listUpcoming [%s]" % cItem.get("title", ""))
        page = cItem.get("page", 1)
        data = self._api("/upcoming-subject-list", {"page": page, "perPage": 23, "category": cItem.get("upcoming_category", "")})
        self._addSubjects(cItem, data.get("subjects"))
        if (data.get("pager") or {}).get("hasMore"):
            self._addNextPage(cItem, page)

    ###################################################
    # detail page: story, trailer, seasons
    ###################################################
    def _getDetail(self, cItem):
        subjectId = cItem.get("subjectId", "")
        if subjectId in self.detailCache:
            return self.detailCache[subjectId]
        detail = {"story": "", "trailer": "", "seasons": []}
        detailPath = cItem.get("detailPath", "")
        if not subjectId or not detailPath:
            return detail
        sts, data = self.getPage("%s/moviesDetail/%s?id=%s&type=/movie/detail" % (self.MAIN_URL, detailPath, subjectId))
        if not sts:
            return detail
        story = self.cm.ph.getSearchGroups(data, r'''<meta\s+name=["']description["'][^>]+content=["']([^"']+)["']''')[0].strip()
        story = re.sub(r"^Watch\s+.*?free streaming online on\s+\w+\.?\s*", "", story, flags=re.IGNORECASE)
        story = re.sub(r"\s*Enjoy HD quality, no ads, and free downloads\.?\s*", " ", story, flags=re.IGNORECASE).strip()
        if len(story) > 10:
            detail["story"] = self.cleanHtmlStr(story)
        detail["trailer"] = self.cm.ph.getSearchGroups(data, r'''<meta\s+(?:name=["']video["']|property=["']og:video:url["'])[^>]+content=["']([^"']+)["']''')[0]
        for season in self._nuxtFind(self._nuxtData(data), "seasons") or []:
            if not isinstance(season, dict):
                continue
            try:
                se, maxEp = int(season.get("se") or 0), int(season.get("maxEp") or 0)
            except (TypeError, ValueError):
                continue
            # allEp lists the episodes that really exist when some are missing ("1,2,4,5,6,7"), empty = 1..maxEp
            episodes = [int(ep) for ep in str(season.get("allEp") or "").split(",") if ep.strip().isdigit()]
            if se > 0 and (episodes or maxEp > 0):
                detail["seasons"].append((se, episodes or list(range(1, maxEp + 1))))
        self.detailCache[subjectId] = detail
        return detail

    def _descWithStory(self, cItem, detail):
        desc = cItem.get("desc", "")
        if detail["story"] and "Story:" not in desc:
            desc += "\n\n%sStory: %s" % (C, detail["story"])
        return desc

    def listSeasons(self, cItem):
        printDBG("MovieBox.listSeasons [%s]" % cItem.get("title", ""))
        detail = self._getDetail(cItem)
        desc = self._descWithStory(cItem, detail)
        txt = cItem.get("txt") or detail["story"]
        for se, episodes in detail["seasons"]:
            params = dict(cItem)
            params.update({"category": "list_episodes", "title": _("Season %d (%d episodes)") % (se, len(episodes)), "url": self._titleUrl(cItem, se),
                           "season": se, "episodes": episodes, "desc": desc, "txt": txt, "good_for_fav": False})
            self.addDir(params)
        if not detail["seasons"]:
            # no seasons list on the page: the series as one video (the API then serves S1E1)
            params = dict(cItem)
            params.update({"category": "", "title": cItem.get("s_title") or cItem.get("title", ""), "desc": desc, "txt": txt})
            self.addVideo(params)
        trailerUrl = cItem.get("trailer_url") or detail["trailer"]
        if trailerUrl:
            params = dict(cItem)
            params.update({"category": "", "title": "%s - %s" % (_("Trailer"), cItem.get("s_title") or cItem.get("title", "")), "url": trailerUrl,
                           "is_trailer": True, "desc": desc, "good_for_fav": False})
            self.addVideo(params)

    def listEpisodes(self, cItem):
        season = cItem.get("season", 1)
        show = cItem.get("s_title") or ""
        for ep in cItem.get("episodes") or []:
            params = dict(cItem)
            params.pop("episodes", None)
            if IsMediaNamingNormalized() and show:
                title = "%s - %s" % (show, formatSxxExx(season, ep))
            else:
                # the download manager names the file after the title: "Episode 2" alone would collide between series
                title = " - ".join(x for x in (show, _("Season %d") % season, _("Episode %d") % ep) if x)
            # category "" - the episode must not be mistaken for its own season folder
            params.update({"category": "", "title": title, "url": self._titleUrl(cItem, season, ep), "season": season, "episode": ep, "good_for_fav": True})
            self.addVideo(params)

    ###################################################
    # streams
    ###################################################
    def _playerReferer(self, cItem):
        # /subject/play answers with empty stream lists unless the request comes from the title's player page
        return "%s/movies/%s?id=%s&type=/movie/detail&detailSe=&detailEp=&lang=en" % (self.MAIN_URL, cItem.get("detailPath", ""), cItem.get("subjectId", ""))

    def _play(self, cItem):
        subjectId = cItem.get("subjectId", "")
        if not subjectId:
            return {}
        if cItem.get("episode"):
            tries = [(cItem.get("season", 1), cItem["episode"])]
        else:
            # movies play as se=0/ep=0; a series without a seasons list falls back to S1E1
            tries = [(0, 0), (1, 1)]
        for se, ep in tries:
            data = self._api("/subject/play", {"subjectId": subjectId, "se": se, "ep": ep, "detailPath": cItem.get("detailPath", "")}, referer=self._playerReferer(cItem))
            if data.get("streams") or data.get("dash") or data.get("hls"):
                return data
        return {}

    def _getCaptions(self, cItem, streamId):
        if not streamId:
            return []
        data = self._api("/subject/caption", {"format": "MP4", "id": streamId, "subjectId": cItem.get("subjectId", ""), "detailPath": cItem.get("detailPath", "")},
                         referer=self._playerReferer(cItem))
        captions = []
        for cap in data.get("captions") or []:
            if cap.get("url"):
                lang = cap.get("lan", "")
                captions.append({"title": cap.get("lanName") or lang.upper(), "lang": lang, "url": cap["url"], "format": "srt"})
        return captions

    def _getStreamLinks(self, cItem):
        playData = self._play(cItem)
        streams = playData.get("streams") or []
        captions = self._getCaptions(cItem, streams[0].get("id", "") if streams else "")
        meta = {"Referer": self.MAIN_URL + "/", "User-Agent": self.USER_AGENT}
        if captions:
            meta["external_sub_tracks"] = captions
        links = []
        for kind, items in (("", streams), ("DASH", playData.get("dash") or []), ("HLS", playData.get("hls") or [])):
            for stream in items:
                if not stream.get("url"):
                    continue
                try:
                    sizeMb = int(stream.get("size") or 0) // (1024 * 1024)
                except (TypeError, ValueError):
                    sizeMb = 0
                res = str(stream.get("resolutions") or "?")
                name = "%sp %s" % (res, kind or stream.get("format") or "MP4")
                if sizeMb:
                    name += " (%dMB)" % sizeMb
                if stream.get("codecName"):
                    name += " [%s]" % stream["codecName"]
                linkMeta = dict(meta)
                if kind == "HLS":
                    linkMeta["iptv_proto"] = "m3u8"
                links.append({"name": name, "url": strwithmeta(stream["url"], linkMeta), "need_resolve": 0, "_res": int(res) if res.isdigit() else 0})
        links.sort(key=lambda x: -x.pop("_res"))
        printDBG("MovieBox: %d links, %d subtitles" % (len(links), len(captions)))
        return links, captions

    def getLinksForVideo(self, cItem):
        printDBG("MovieBox.getLinksForVideo [%s]" % cItem.get("url", ""))
        if not cItem.get("subjectId") or cItem.get("is_trailer"):
            # trailers and football streams carry their playable url themselves
            url = cItem.get("url", "")
            if not url:
                return []
            if not cItem.get("need_resolve"):
                url = strwithmeta(url, {"Referer": self.MAIN_URL + "/", "User-Agent": self.USER_AGENT}) if cItem.get("is_trailer") else url
            return [{"name": cItem.get("title", "") or "stream", "url": url, "need_resolve": cItem.get("need_resolve", 0)}]
        # the streams are fetched now, not while listing: their urls are signed and run out
        links = self._getStreamLinks(cItem)[0]
        if not cItem.get("episode"):
            trailerUrl = cItem.get("trailer_url", "")
            if trailerUrl:
                links.append({"name": _("Trailer"), "url": strwithmeta(trailerUrl, {"Referer": self.MAIN_URL + "/", "User-Agent": self.USER_AGENT}), "need_resolve": 0})
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    ###################################################
    # subtitle files (MENU "Save subtitles"; the same subtitles are also attached to every stream)
    ###################################################
    def saveSubtitles(self, cItem, langs):
        # -> (saved file paths, error text)
        streams = self._play(cItem).get("streams") or []
        captions = self._getCaptions(cItem, streams[0].get("id", "") if streams else "")
        if not captions:
            return [], _("No subtitles available for this title.")
        wanted = [c for c in captions if c["lang"].split("_")[0].lower() in langs] or [c for c in captions if c["lang"].lower().startswith("en")]
        if not wanted:
            return [], _("No subtitles in %s. Available: %s") % (", ".join(langs), ", ".join(c["lang"] for c in captions))
        # the same name the download manager gives the video (its list title), so the files sit side by side in the list
        fileName = re.sub(r'[/:*?"<>|\\]', "-", cItem.get("title", "") or "subtitle").strip()
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        saved = []
        for cap in wanted:
            filePath = GetSubtitlesDir("%s.%s.srt" % (fileName, cap["lang"]))
            if self.cm.saveWebFile(filePath, cap["url"], params).get("sts", False):
                saved.append(filePath)
        if not saved:
            return [], _("Failed to download subtitle.")
        return saved, ""

    ###################################################
    # Search
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MovieBox.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        searchPattern = (searchPattern or "").strip()
        if not searchPattern:
            return
        page = cItem.get("page", 1)
        data = self._api("/subject/search", post={"keyword": searchPattern, "page": page, "perPage": 28, "subjectType": self.SEARCH_TYPES.get(searchType, 0)})
        added = self._addSubjects(cItem, data.get("items"))
        if (data.get("pager") or {}).get("hasMore"):
            self._addNextPage(cItem, page)
        if not added and page == 1:
            self._listSearchSuggestions(cItem, searchPattern, searchType)

    def _listSearchSuggestions(self, cItem, keyword, searchType):
        data = self._api("/subject/search-suggest", post={"keyword": keyword, "perPage": 10})
        for item in data.get("items") or []:
            word = str(item.get("word") or "").strip()
            if word:
                params = dict(cItem)
                params.update({"category": "search_suggestion", "title": "%s%s" % (_("Search: "), word), "search_keyword": word,
                               "search_type": searchType, "page": 1, "good_for_fav": False})
                self.addDir(params)

    ###################################################
    # Football Live
    ###################################################
    def _dayStart(self, offset):
        # local midnight, "offset" days from today
        lt = time.localtime()
        return int(time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + offset, 0, 0, 0, 0, 0, -1)))

    def _dayLabel(self, dayStart):
        lt = time.localtime(dayStart)
        return "%s %s" % (("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")[lt.tm_wday], time.strftime("%d/%m", lt))

    def _addDay(self, cItem, offset, label):
        dayStart = self._dayStart(offset)
        params = dict(cItem)
        params.update({"category": "list_football_live_day", "title": label % self._dayLabel(dayStart),
                       "day_start_ts": dayStart, "day_end_ts": self._dayStart(offset + 1), "good_for_fav": False})
        self.addDir(params)

    def listFootballLive(self, cItem):
        params = dict(cItem)
        params.update({"category": "list_football_replays", "title": "%s%s" % (L, _("Replays & highlights")), "replay_offset": 0, "good_for_fav": False,
                       "desc": _("Finished matches with a full replay, highlights or match cuts, newest first (usually a few days after the match).")})
        self.addDir(params)
        params = dict(cItem)
        params.update({"category": "list_football_live_past", "title": "%s%s" % (OR, _("Previous days")), "past_offset": 1, "good_for_fav": False})
        self.addDir(params)
        for offset in range(0, 7):
            if offset == 0:
                label = C + _("TODAY") + " - %s"
            elif offset == 1:
                label = Y + _("TOMORROW") + " - %s"
            else:
                label = W + "%s"
            self._addDay(cItem, offset, label)

    def listFootballLivePast(self, cItem):
        start = cItem.get("past_offset", 1)
        for i in range(start, start + 7):
            self._addDay(cItem, -i, (W + _("YESTERDAY") + " - %s") if i == 1 else (W + "%s" + " (-%d)" % i))
        params = dict(cItem)
        params.update({"category": "list_football_live_past", "title": _("Older days"), "past_offset": start + 7, "good_for_fav": False})
        self.addDir(params)

    def _getMatchDay(self, dayStart, dayEnd):
        # [(league name, [match, ...]), ...] of one day, None when the list could not be loaded
        header = {"User-Agent": self.USER_AGENT, "Accept": "application/json", "Referer": self.SPORT_URL, "Origin": self.SPORT_URL.rstrip("/"), "X-Device-Info": "{}"}
        url = self.SPORT_API + "/live/match-list-v3?" + urllib_urlencode({"status": 0, "matchType": "football", "startTime": dayStart * 1000, "endTime": dayEnd * 1000 - 1})
        sts, data = self.cm.getPage(url, {"header": header})
        try:
            data = json_loads(data) if sts else {}
        except Exception:
            data = {}
        if data.get("code") != 0:
            return None
        return [(league.get("league") or "", league.get("matchList") or []) for league in (data.get("data") or {}).get("list") or []]

    def listFootballLiveDay(self, cItem):
        printDBG("MovieBox.listFootballLiveDay")
        dayStart = cItem.get("day_start_ts", 0)
        if not dayStart:
            return
        leagues = self._getMatchDay(dayStart, cItem.get("day_end_ts") or dayStart + 86400)
        if leagues is None:
            self.addMarker({"title": "%s%s" % (OR, _("Failed to load the match list")), "desc": ""})
            return
        for league, matches in leagues:
            if not matches:
                continue
            if league:
                self.addMarker({"title": "%s%s (%d)" % (Y, league, len(matches)), "desc": ""})
            for match in matches:
                self._addFootballMatch(cItem, match)

    def listFootballReplays(self, cItem):
        # the matches of 7 days that have something to watch afterwards, grouped by day; replays usually
        # appear a few days after the match and only for part of the matches (none in an international break)
        printDBG("MovieBox.listFootballReplays")
        start = cItem.get("replay_offset", 0)
        found = 0
        for i in range(start, start + 7):
            dayStart = self._dayStart(-i)
            leagues = self._getMatchDay(dayStart, self._dayStart(-i + 1)) or []
            matches = [m for _league, ms in leagues for m in ms if m.get("replay") or m.get("highlights") or m.get("cuts")]
            if not matches:
                continue
            self.addMarker({"title": "%s%s (%d)" % (Y, self._dayLabel(dayStart), len(matches)), "desc": ""})
            for match in matches:
                self._addFootballMatch(cItem, match)
            found += len(matches)
        if not found:
            self.addMarker({"title": "%s%s" % (OR, _("No replays in these days")), "desc": ""})
        params = dict(cItem)
        params.update({"category": "list_football_replays", "title": _("Older replays"), "replay_offset": start + 7, "good_for_fav": False})
        self.addDir(params)

    def _addFootballMatch(self, cItem, m):
        team1, team2 = m.get("team1") or {}, m.get("team2") or {}
        name1, name2 = team1.get("name", "?"), team2.get("name", "?")
        league = m.get("leagueName") or m.get("league") or (m.get("leagueItem") or {}).get("name", "")
        status = m.get("status", "")
        if status in ("MatchIng", "1", 1) or m.get("statusLive") == "LIVE":
            statusText, title = "LIVE", "%sLIVE %s %s - %s %s" % (C, name1, team1.get("score", "0"), team2.get("score", "0"), name2)
        elif status in ("MatchEnded", "2", 2, "FT"):
            statusText, title = "Full Time", "%s%s %s - %s %s" % (L, name1, team1.get("score", "0"), team2.get("score", "0"), name2)
        else:
            statusText, title = "Upcoming", "%s%s vs %s" % (Y, name1, name2)
        desc = []
        if league:
            desc.append("%s%s" % (Y, league))
        if m.get("matchRound"):
            desc.append(str(m["matchRound"]))
        try:
            lt = time.localtime(int(m.get("startTime")) / 1000)
            desc.extend([time.strftime("%d/%m", lt), time.strftime("%H:%M", lt)])
        except Exception:
            pass
        desc.append(statusText)
        # what there is to watch, so a replay can be found without opening every match
        extras = [label for key, label in (("replay", _("Replay")), ("highlights", _("Highlights")), ("cuts", _("Match cuts"))) if m.get(key)]
        if extras:
            title += " %s[%s]" % (C, ", ".join(extras))
            desc.append(", ".join(extras))
        avatar = team1.get("avatar", "")
        self.addDir({"name": "category", "category": "list_football_live_streams", "title": title, "desc": " | ".join(desc),
                     "icon": self.getFullIconUrl(avatar) if avatar else "", "match_play_path": m.get("playPath", ""),
                     "match_play_source": m.get("playSource") or [], "match_replay": m.get("replay") or [], "match_highlights": m.get("highlights") or [],
                     "match_cuts": m.get("cuts") or [], "match_status": status, "good_for_fav": False})

    def _addSportVideo(self, cItem, title, url, referer=None, icon=None, needResolve=0):
        # no colour codes in a video title: the download manager names the file after it
        title = re.sub(r"\\c[0-9A-Fa-f]{8}", "", title).strip()
        params = dict(cItem)
        params.update({"title": title, "type": "video", "need_resolve": needResolve, "good_for_fav": False,
                       "url": strwithmeta(url, {"Referer": referer or self.SPORT_URL, "User-Agent": self.USER_AGENT}) if not needResolve else url})
        if icon:
            params["icon"] = icon
        self.addVideo(params)

    def listFootballLiveStreams(self, cItem):
        printDBG("MovieBox.listFootballLiveStreams [%s]" % cItem.get("title", ""))
        count = len(self.currList)
        playPath = cItem.get("match_play_path", "")
        # after the final whistle the live pull URL is dead (404), the replay entries below take over
        if playPath.startswith("http") and cItem.get("match_status") != "MatchEnded":
            self._addSportVideo(cItem, "%sLive - Main" % C, playPath)
        for src in cItem.get("match_play_source") or []:
            srcTitle, srcPath = "%s%s" % (C, src.get("title") or "Channel"), src.get("path") or ""
            if not srcPath.startswith("http"):
                continue
            if "88player.top/m3u8.html" in srcPath:
                realUrl = urllib_unquote((parse_qs(urlparse(srcPath).query).get("url") or [""])[0])
                if realUrl:
                    self._addSportVideo(cItem, srcTitle, realUrl, "https://play.88player.top/")
                    continue
            if ".m3u8" in srcPath or "playlist" in srcPath:
                self._addSportVideo(cItem, srcTitle, srcPath)
                continue
            extracted = self._extractStreamFromPage(srcPath)
            if ".m3u8" in extracted or ".mp4" in extracted:
                self._addSportVideo(cItem, srcTitle, extracted, srcPath)
            elif extracted and self.up.checkHostSupport(extracted) == 1:
                self._addSportVideo(cItem, srcTitle, extracted, needResolve=1)
            elif self.up.checkHostSupport(srcPath) == 1:
                self._addSportVideo(cItem, srcTitle, srcPath, needResolve=1)
            else:
                printDBG("MovieBox: no playable stream in %s" % srcPath)
        for key, color, label, unit in (("match_replay", Y, "Replay", 60), ("match_highlights", L, "Highlights", 60), ("match_cuts", W, "Cut", 1)):
            clips = [c for c in cItem.get(key) or [] if c.get("path")]
            if key == "match_cuts" and clips:
                self.addMarker({"title": "%s%s (%d)" % (Y, _("Match cuts"), len(clips)), "desc": ""})
            for clip in clips:
                try:
                    duration = int(clip.get("duration") or 0) // unit
                except (TypeError, ValueError):
                    duration = 0
                cover = clip.get("cover")
                self._addSportVideo(cItem, "%s%s (%d%s)" % (color, clip.get("title") or label, duration, "min" if unit == 60 else "s"), clip["path"],
                                    icon=cover.get("url", "") if isinstance(cover, dict) else "")
        if len(self.currList) == count:
            if cItem.get("match_status") == "MatchNotStart":
                self.addMarker({"title": "%s%s" % (Y, _("Match not started yet")), "desc": ""})
            else:
                self.addMarker({"title": "%s%s" % (OR, _("No stream available")), "desc": ""})

    def _extractStreamFromPage(self, url):
        sts, data = self.cm.getPage(url, {"header": {"User-Agent": self.USER_AGENT, "Referer": self.SPORT_URL}})
        if not sts:
            return ""
        found = self.cm.ph.getSearchGroups(data, r'''(https?://[^\s"'<>]+\.m3u8[^\s"'<>]*)''')[0]
        if found:
            return found
        iframe = self.cm.ph.getSearchGroups(data, r'''<iframe[^>]+src=["']([^"']+)["']''', ignoreCase=True)[0]
        return self.cm.getFullUrl(iframe, url) if iframe else ""

    def getVideoLinks(self, url):
        printDBG("MovieBox.getVideoLinks [%s]" % url)
        return self.up.getVideoLinkExt(url)

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("MovieBox.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: name[%s], category[%s]" % (name, category))
        self.currList = []
        handlers = {
            "list_sections": self.listSections,
            "list_section_banner": self.listSectionBanner,
            "list_filter_page": self.listFilterPage,
            "list_most_watched_tabs": self.listMostWatchedTabs,
            "list_ranking_content": self.listRankingContent,
            "list_upcoming_tabs": self.listUpcomingTabs,
            "list_upcoming": self.listUpcoming,
            "list_seasons": self.listSeasons,
            "list_episodes": self.listEpisodes,
            "list_football_live": self.listFootballLive,
            "list_football_live_past": self.listFootballLivePast,
            "list_football_live_day": self.listFootballLiveDay,
            "list_football_replays": self.listFootballReplays,
            "list_football_live_streams": self.listFootballLiveStreams,
        }
        if name is None:
            self.listsTab(self.MAIN_CAT_TAB, {"name": "category"})
        elif category in handlers:
            handlers[category](self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category", "category": "search_next_page"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_suggestion":
            cItem = dict(self.currItem)
            self.listSearchResult(cItem, cItem.get("search_keyword", ""), cItem.get("search_type", ""))
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MovieBox(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("moviebox")

    def getSearchTypes(self):
        return [(_("All"), "all"), (_("Movies"), "movies"), (_("Series"), "series")]

    def withArticleContent(self, cItem):
        return bool(cItem.get("subjectId")) and not cItem.get("is_trailer")

    def _subtitleLangs(self):
        langs = [GetDefaultLang(), "en"]
        return [lang for idx, lang in enumerate(langs) if lang and lang not in langs[:idx]]

    def getCustomActions(self, Index=0):
        # MENU: the watched entries of the shared helper + "Save subtitles" on a movie / episode
        ret = GenericFolderWatchedHostMixin.getCustomActions(self, Index)
        actions = list(ret.value) if ret.status == RetHost.OK and isinstance(ret.value, list) else []
        try:
            cItem = self.host.currList[Index]
            if cItem.get("type") == "video" and cItem.get("subjectId") and not cItem.get("is_trailer"):
                langs = self._subtitleLangs()
                actions.append(IPTVChoiceBoxItem(_("Save subtitles (%s)") % ", ".join(langs), "", {"action": "moviebox_save_subtitles", "item_index": Index}))
        except Exception:
            printExc()
        return RetHost(RetHost.OK if actions else RetHost.ERROR, value=actions)

    def performCustomAction(self, privateData):
        if privateData.get("action") != "moviebox_save_subtitles":
            return GenericFolderWatchedHostMixin.performCustomAction(self, privateData)
        Index = privateData.get("item_index", -1)
        if not 0 <= Index < len(self.host.currList):
            return RetHost(RetHost.ERROR, value=[])
        saved, error = self.host.saveSubtitles(self.host.currList[Index], self._subtitleLangs())
        if not saved:
            return RetHost(RetHost.ERROR, value=[error])
        GetIPTVNotify().push(_("Subtitles saved:\n%s") % "\n".join(saved), "info", 10)
        return RetHost(RetHost.OK, value=[])
