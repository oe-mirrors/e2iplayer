# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - rewrite for the current SVT Play APIs:
#   contento GraphQL (api.svt.se/contento/graphql, plain POST queries - the GET
#   variant is CDN-cached unreliably), video.svt.se/video/<svtId> for streams +
#   WebVTT subtitles, live channels (ch-svt1 ...), A-Ö, categories, search.
#   Many titles are geo-blocked to Sweden ("onlyAvailableInSweden"): marked in
#   the description, optionally hidden, and a clear message when the CDN refuses.
#   Watched flag / downloaded marker / favourites / name normalisation / sidecar.
import re

from Components.config import config, ConfigYesNo, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

config.plugins.iptvplayer.svtplayse_hide_geo = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Hide titles only available in Sweden") + ":", config.plugins.iptvplayer.svtplayse_hide_geo))
    return optionList


def gettytul():
    return "https://www.svtplay.se/"


GRAPHQL_URL = "https://api.svt.se/contento/graphql?ua=svtplaywebb-play-render-prod-client"
VIDEO_API_URL = "https://video.svt.se/video/%s"
IMAGE_URL = "https://www.svtstatic.se/image/medium/%s/%s/%s"
PAGE_SIZE = 40
AZ_PAGE_SIZE = 100

SERIES_TYPES = ("TvSeries", "TvShow", "KidsTvShow")
VIDEO_TYPES = ("Single", "Episode", "Clip", "Trailer", "Variant")
# start page rows that only make sense with an SVT account / are not playable yet
SKIP_SELECTION_TYPES = ("keepWatching", "favorites", "personalRecommendations", "upcoming")
# accessibility / audio flags SVT files under "genres"
NON_GENRES = ("Tydligare tal", "Uppläst undertext", "5.1", "Dolby Atmos", "Syntolkat", "Teckenspråk", "Kristallen", "Duo")
# HLS masters in order of preference (AVC only, TS segments first)
HLS_FORMATS = ("hls-ts-full", "hls", "hls-cmaf-avc", "hls-cmaf-live", "hls-cmaf-full")

VIDEO_ID_RE = re.compile(r'/video/([A-Za-z0-9_-]+)')
CHANNEL_RE = re.compile(r'/kanaler/([A-Za-z0-9_-]+)')
SEASON_ID_RE = re.compile(r'^season-(\d+)-')
POSITION_RE = re.compile(r'S\S*song\s+(\d+)\D+?Avsnitt\s+(\d+)', re.I)

TEASER_FRAGMENT = ("fragment T on Teaser { heading subHeading description durationFormatted liveNow image { id changed } "
                   "item { __typename svtId name slug urls { svtplay } restrictions { onlyAvailableInSweden drmCopyProtection } "
                   "... on Episode { number positionInSeason productionYear live { liveNow } parent { name } } "
                   "... on Single { productionYear originalProgramTitle genres { name } live { liveNow } } } } ")


class SVTPlaySE(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # letter / cat_id: the A-Ö letter and category folders are good_for_fav too and need them to open again
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "video_id", "slug", "sel_id", "season", "episode",
                  "letter", "cat_id", "icon", "desc", "svt_type", "geo", "live", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "svtplayse", "cookie": "svtplayse.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Referer": "https://www.svtplay.se/", "Origin": "https://www.svtplay.se"})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.azCache = None
        self.MENU = [{"category": "svt_selection", "title": _("Popular"), "sel_id": "popular_start"},
                     {"category": "svt_selection", "title": _("Latest"), "sel_id": "latest_start"},
                     {"category": "svt_selection", "title": _("Last chance"), "sel_id": "lastchance_start"},
                     {"category": "svt_start", "title": _("Home page")},
                     {"category": "svt_channels", "title": _("Live channels")},
                     {"category": "svt_selection", "title": _("Live streams"), "sel_id": "live_start"},
                     {"category": "svt_az_letters", "title": "A-Ö"},
                     {"category": "svt_categories", "title": _("Categories")}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("svtplayse")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live"):
                return ""
            category = cItem.get("category", "")
            url = str(cItem.get("url", "") or "").strip()
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url if url else ""
            if category == "svt_series":
                return "series:%s" % url if url else ""
            if category == "svt_season":
                slug = str(cItem.get("slug", "") or "").strip()
                selId = str(cItem.get("sel_id", "") or "").strip()
                return "season:%s|%s" % (slug, selId) if slug and selId else ""
            return ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # API helpers
    ###################################################
    def _gql(self, query, variables=None):
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Content-Type": "application/json", "Accept": "application/json"})
        params["raw_post_data"] = True
        sts, data = self.cm.getPage(GRAPHQL_URL, params, json_dumps({"query": query, "variables": variables or {}}))
        if not sts:
            return {}
        try:
            data = json_loads(data)
            if data.get("errors"):
                printDBG("SVTPlaySE._gql errors: %s" % data["errors"])
            return data.get("data") or {}
        except Exception:
            printExc()
        return {}

    def _imageUrl(self, image, width=400):
        try:
            if isinstance(image, dict) and image.get("id") and image.get("changed"):
                return IMAGE_URL % (width, image["id"], image["changed"])
        except Exception:
            printExc()
        return ""

    def _fullUrl(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        return self.MAIN_URL.rstrip("/") + "/" + path.lstrip("/")

    def _hideGeo(self):
        try:
            return config.plugins.iptvplayer.svtplayse_hide_geo.value
        except Exception:
            return False

    def _geoLabel(self):
        return _("Only available in %s") % _("Sweden")

    def _movieTitle(self, title, year):
        if IsMediaNamingNormalized() and year:
            return "%s (%s)" % (title, year)
        return title

    def _episodeTitle(self, show, epName, season, episode):
        epName = (epName or "").strip()
        if IsMediaNamingNormalized() and season and episode:
            # "3. Dag 3 - ..." -> "Dag 3 - ..." (the number lives in SxxExx now)
            epName = re.sub(r'^\d+\.\s*', '', epName)
            title = "%s - %s" % (show, formatSxxExx(season, episode))
            return "%s - %s" % (title, epName) if epName else title
        if not show or show == epName:
            return epName or show
        return "%s - %s" % (show, epName) if epName else show

    def _seasonEpisode(self, item, selId=""):
        season = ""
        episode = ""
        match = SEASON_ID_RE.search(selId or "")
        if match:
            season = match.group(1)
        pos = POSITION_RE.search(item.get("positionInSeason") or "")
        if pos:
            season = season or pos.group(1)
            episode = pos.group(2)
        if season and not episode and item.get("number"):
            episode = str(item["number"])
        return season, episode

    ###################################################
    # rows
    ###################################################
    def _addTeaser(self, cItem, teaser, show="", selId=""):
        item = teaser.get("item") or {}
        itemType = item.get("__typename", "")
        path = (item.get("urls") or {}).get("svtplay", "")
        if not path:
            return False
        restrictions = item.get("restrictions") or {}
        if restrictions.get("drmCopyProtection"):
            # Widevine-only streams can't be played on enigma2
            return False
        geo = bool(restrictions.get("onlyAvailableInSweden"))
        if geo and self._hideGeo():
            return False
        heading = self.cleanHtmlStr(teaser.get("heading") or "")
        name = self.cleanHtmlStr(item.get("name") or "")
        icon = self._imageUrl(teaser.get("image")) or cItem.get("icon", "")
        desc = []
        sub = self.cleanHtmlStr(teaser.get("description") or teaser.get("subHeading") or "")
        if teaser.get("liveNow") or (item.get("live") or {}).get("liveNow"):
            desc.append(_("On Air"))
        if teaser.get("durationFormatted") and teaser["durationFormatted"] not in sub:
            desc.append(teaser["durationFormatted"])
        if geo:
            desc.append(self._geoLabel())
        descText = " | ".join(desc)
        if sub:
            descText = "%s\n%s" % (descText, sub) if descText else sub

        params = stripPagerKeys(dict(cItem), ("search_pattern", "letter", "cat_id", "sel_id", "season", "episode", "video_id"))
        params.update({"good_for_fav": True, "url": self._fullUrl(path), "icon": icon, "desc": descText,
                       "svt_type": itemType, "geo": geo, "live": False})
        if itemType in SERIES_TYPES:
            title = heading or name
            params.update({"category": "svt_series", "title": title, "s_title": title, "slug": path.strip("/").split("/")[0],
                           "meta_type": "tv", "meta_title": title, "meta_year": ""})
            self.addDir(params)
            return True
        if itemType not in VIDEO_TYPES:
            return False
        videoId = item.get("svtId", "")
        match = VIDEO_ID_RE.search(path)
        if match:
            videoId = match.group(1)
        params["video_id"] = videoId
        if itemType == "Episode":
            showName = show or self.cleanHtmlStr((item.get("parent") or {}).get("name") or "") or heading
            season, episode = self._seasonEpisode(item, selId)
            epName = name if name and name != showName else (heading if heading != showName else "")
            params.update({"category": "svt_video", "title": self._episodeTitle(showName, epName, season, episode),
                           "s_title": showName, "season": season, "episode": episode,
                           "meta_type": "", "meta_title": showName, "meta_year": ""})
        elif itemType == "Single":
            year = str(item.get("productionYear") or "")
            isFilm = "Filmer" in [g.get("name") for g in (item.get("genres") or [])]
            title = name or heading
            params.update({"category": "svt_video", "title": self._movieTitle(title, year) if isFilm else title, "s_title": title,
                           "meta_type": "movie" if isFilm else "", "meta_title": self.cleanHtmlStr(item.get("originalProgramTitle") or "") or title,
                           "meta_year": year})
        else:
            title = heading if heading and heading != name and name else (name or heading)
            if heading and name and heading != name:
                title = "%s - %s" % (heading, name)
            params.update({"category": "svt_video", "title": title, "s_title": heading or name, "meta_type": "", "meta_title": "", "meta_year": ""})
        self.addVideo(params)
        return True

    ###################################################
    # lists
    ###################################################
    def listSelection(self, cItem):
        selId = cItem.get("sel_id", "")
        page = max(1, int(cItem.get("page", 1) or 1))
        offset = (page - 1) * PAGE_SIZE
        printDBG("SVTPlaySE.listSelection [%s] page %s" % (selId, page))
        query = TEASER_FRAGMENT + ("query($id:String!, $limit:Int, $offset:Int) { selectionById(id:$id) { id name "
                                   "itemsPaginated(pagination:{limit:$limit, offset:$offset}) { totalSize items { ...T } } } }")
        data = self._gql(query, {"id": selId, "limit": PAGE_SIZE, "offset": offset})
        sel = data.get("selectionById") or {}
        paginated = sel.get("itemsPaginated") or {}
        items = paginated.get("items") or []
        if not items and not offset:
            # personalised start rows (e.g. "Vi rekommenderar") answer only through the start page
            query = TEASER_FRAGMENT + "query($ids:[String!]) { startForSvtPlay { selections(includeById:$ids) { items { ...T } } } }"
            sels = (self._gql(query, {"ids": [selId]}).get("startForSvtPlay") or {}).get("selections") or []
            items = (sels[0].get("items") or []) if sels else []
            paginated = {}
        for teaser in items:
            self._addTeaser(cItem, teaser)
        total = int(paginated.get("totalSize", 0) or 0)
        lastPage = (total + PAGE_SIZE - 1) // PAGE_SIZE
        # GraphQL offset paging: a constant template only lets "Jump" through
        addPagingItems(self, dict(cItem, desc=""), page, bool(items) and page < lastPage, lastPage, cItem.get("url") or self.MAIN_URL)

    def listStart(self, cItem):
        printDBG("SVTPlaySE.listStart")
        data = self._gql("query { startForSvtPlay { selections { id name selectionType } } }")
        for sel in (data.get("startForSvtPlay") or {}).get("selections") or []:
            if sel.get("selectionType") in SKIP_SELECTION_TYPES or not sel.get("id"):
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "svt_selection", "title": self.cleanHtmlStr(sel.get("name") or sel["id"]),
                           "sel_id": sel["id"], "desc": ""})
            self.addDir(params)

    def listChannels(self, cItem):
        printDBG("SVTPlaySE.listChannels")
        query = ("query { channels { channels { id name drmCopyProtection logo { id changed } "
                 "running { name subHeading startTime image { id changed } } } } }")
        data = self._gql(query)
        for channel in (data.get("channels") or {}).get("channels") or []:
            chId = channel.get("id", "")
            if not chId or channel.get("drmCopyProtection"):
                continue
            running = channel.get("running") or {}
            desc = []
            if running.get("name"):
                now = "%s %s" % (running.get("startTime", ""), self.cleanHtmlStr(running["name"]))
                if running.get("subHeading"):
                    now += " - " + self.cleanHtmlStr(running["subHeading"])
                desc.append(now.strip())
            desc.append(self._geoLabel())
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "svt_channel", "title": self.cleanHtmlStr(channel.get("name") or chId),
                           "url": self._fullUrl("kanaler/%s" % chId.replace("ch-", "", 1)), "video_id": chId, "live": True, "geo": True,
                           "icon": self._imageUrl(running.get("image")) or self._imageUrl(channel.get("logo"), 200), "desc": "\n".join(desc)})
            self.addVideo(params)

    def _getAZ(self):
        if self.azCache is None:
            query = ("query { programAtillO { selections { id name items { heading image { id changed } "
                     "item { __typename svtId name slug urls { svtplay } restrictions { onlyAvailableInSweden drmCopyProtection } } } } } }")
            data = self._gql(query)
            sels = (data.get("programAtillO") or {}).get("selections") or []
            if sels:
                self.azCache = sels
            return sels
        return self.azCache

    def _azTeasers(self, sel):
        # the titles of one A-Ö letter that are listed (no DRM, geo-blocked ones only when not hidden)
        ret = []
        for teaser in sel.get("items") or []:
            restrictions = (teaser.get("item") or {}).get("restrictions") or {}
            if not restrictions.get("drmCopyProtection") and not (restrictions.get("onlyAvailableInSweden") and self._hideGeo()):
                ret.append(teaser)
        return ret

    def listAZLetters(self, cItem):
        for sel in self._getAZ():
            letter = sel.get("name", "")
            count = len(self._azTeasers(sel))
            if not letter or not count:
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "svt_az", "title": "%s (%d)" % (letter, count), "letter": letter, "desc": ""})
            self.addDir(params)

    def listAZ(self, cItem):
        # one letter holds up to ~200 titles in one answer - paged here
        letter = cItem.get("letter", "")
        page = max(1, int(cItem.get("page", 1) or 1))
        for sel in self._getAZ():
            if sel.get("name") == letter:
                teasers = self._azTeasers(sel)
                start = (page - 1) * AZ_PAGE_SIZE
                for teaser in teasers[start:start + AZ_PAGE_SIZE]:
                    self._addTeaser(cItem, teaser)
                lastPage = (len(teasers) + AZ_PAGE_SIZE - 1) // AZ_PAGE_SIZE
                # constant template: the page number drives the list, the template only lets "Jump" through
                addPagingItems(self, dict(cItem, desc=""), page, page < lastPage, lastPage, self.MAIN_URL)
                break

    def listCategories(self, cItem):
        printDBG("SVTPlaySE.listCategories")
        data = self._gql("query { mainCategories { categories { id heading byline image { id changed } } } }")
        for cat in (data.get("mainCategories") or {}).get("categories") or []:
            if not cat.get("id"):
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "svt_category", "title": self.cleanHtmlStr(cat.get("heading") or cat["id"]),
                           "cat_id": cat["id"], "icon": self._imageUrl(cat.get("image")), "desc": self.cleanHtmlStr(cat.get("byline") or "")})
            self.addDir(params)

    def listCategory(self, cItem):
        catId = cItem.get("cat_id", "")
        printDBG("SVTPlaySE.listCategory [%s]" % catId)
        query = "query($id:String!) { categoryPage(id:$id) { tabs { id name selections { id name selectionType } } } }"
        data = self._gql(query, {"id": catId})
        seen = set()
        for tab in (data.get("categoryPage") or {}).get("tabs") or []:
            sels = [s for s in (tab.get("selections") or []) if s.get("id") and s.get("selectionType") not in SKIP_SELECTION_TYPES]
            for sel in sels:
                if sel["id"] in seen:
                    continue
                seen.add(sel["id"])
                title = sel.get("name") or tab.get("name") or sel["id"]
                if len(sels) == 1 and tab.get("name"):
                    title = tab["name"]
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "svt_selection", "title": self.cleanHtmlStr(title), "sel_id": sel["id"], "desc": ""})
                self.addDir(params)

    def _seriesData(self, slug):
        query = TEASER_FRAGMENT + ("query($slugs:[String!]!) { listablesBySlug(slugs:$slugs) { __typename name image { id changed } "
                                   "associatedContent(include:[productionPeriod, season]) { id name items { ...T } } } }")
        data = self._gql(query, {"slugs": [slug]})
        listables = data.get("listablesBySlug") or []
        return listables[0] if listables else {}

    def listSeasons(self, cItem):
        slug = cItem.get("slug", "")
        printDBG("SVTPlaySE.listSeasons [%s]" % slug)
        series = self._seriesData(slug)
        sels = [s for s in (series.get("associatedContent") or []) if s.get("items")]
        show = cItem.get("s_title", "") or self.cleanHtmlStr(series.get("name") or "")
        if len(sels) == 1:
            for teaser in sels[0]["items"]:
                self._addTeaser(cItem, teaser, show, sels[0].get("id", ""))
            return
        for sel in sels:
            match = SEASON_ID_RE.search(sel.get("id", ""))
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "svt_season", "title": "%s - %s" % (show, self.cleanHtmlStr(sel.get("name") or "")),
                           "s_title": show, "sel_id": sel.get("id", ""), "season": match.group(1) if match else "",
                           "desc": "%s: %d" % (_("Episodes"), len(sel["items"]))})
            self.addDir(params)

    def listEpisodes(self, cItem):
        series = self._seriesData(cItem.get("slug", ""))
        show = cItem.get("s_title", "")
        selId = cItem.get("sel_id", "")
        for sel in series.get("associatedContent") or []:
            if sel.get("id") == selId:
                for teaser in sel.get("items") or []:
                    self._addTeaser(cItem, teaser, show, selId)
                break

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SVTPlaySE.listSearchResult [%s]" % searchPattern)
        query = TEASER_FRAGMENT + ("query($q:String) { searchPage(query:$q) { flat { hits { teaser { ...T } categoryTeaser { id heading } } } "
                                   "sectioned { hits { teaser { ...T } categoryTeaser { id heading } } } } }")
        data = self._gql(query, {"q": searchPattern})
        page = data.get("searchPage") or {}
        hits = list((page.get("flat") or {}).get("hits") or [])
        if not hits:
            for section in page.get("sectioned") or []:
                hits.extend(section.get("hits") or [])
        cItem = dict(cItem)
        cItem.pop("search_pattern", None)
        seen = set()
        for hit in hits:
            if hit.get("teaser"):
                path = ((hit["teaser"].get("item") or {}).get("urls") or {}).get("svtplay", "")
                if path in seen:
                    continue
                seen.add(path)
                self._addTeaser(cItem, hit["teaser"])
            elif (hit.get("categoryTeaser") or {}).get("id"):
                cat = hit["categoryTeaser"]
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "svt_category", "title": "%s %s" % (_("Category:"), self.cleanHtmlStr(cat.get("heading") or cat["id"])),
                               "cat_id": cat["id"], "desc": ""})
                self.addDir(params)

    ###################################################
    # links
    ###################################################
    def _videoId(self, cItem):
        videoId = cItem.get("video_id", "")
        if videoId:
            return videoId
        url = cItem.get("url", "")
        match = VIDEO_ID_RE.search(url)
        if match:
            return match.group(1)
        match = CHANNEL_RE.search(url)
        if match:
            return "ch-" + match.group(1)
        return ""

    def getLinksForVideo(self, cItem):
        printDBG("SVTPlaySE.getLinksForVideo [%s]" % cItem.get("url", ""))
        videoId = self._videoId(cItem)
        if not videoId:
            return []
        sts, data = self.cm.getPage(VIDEO_API_URL % videoId, self.defaultParams)
        if not sts:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []
        rights = data.get("rights") or {}
        geo = bool(rights.get("geoBlockedSweden"))
        if rights.get("drmCopyProtection"):
            SetIPTVPlayerLastHostError(_("Video with DRM protection."))
            return []
        live = bool(cItem.get("live")) or bool(data.get("live")) or videoId.startswith("ch-")

        refs = {}
        for ref in data.get("videoReferences") or []:
            if ref.get("format") and ref.get("url"):
                refs.setdefault(ref["format"], ref["url"])
        master = ""
        for fmt in HLS_FORMATS:
            if refs.get(fmt):
                master = refs[fmt]
                break
        if not master:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        if not live and ("svt-live-" in master or data.get("liveStatus") == "LIVE"):
            # a broadcast that is on air or just ended (VOD not ready yet) comes from the live origin
            # (svt-live-event.akamaized.net/.../master-fmp4.m3u8) with "live": false - its split renditions
            # became merge:// links that did not start, the master itself plays
            live = True

        subTracks = []
        for sub in data.get("subtitleReferences") or []:
            subUrl = sub.get("url", "")
            if not subUrl or (sub.get("format") or "webvtt") != "webvtt" or not subUrl.split("?", 1)[0].endswith(".vtt"):
                continue
            subTracks.append({"title": sub.get("label") or sub.get("languageName") or sub.get("language") or "SV",
                              "lang": sub.get("language") or "sv", "url": subUrl, "format": "vtt"})

        geoMsg = _("This content is not available in your region.")
        baseMeta = {"iptv_proto": "m3u8", "iptv_livestream": live, "Referer": self.MAIN_URL, "User-Agent": self.HEADER.get("User-Agent")}
        if subTracks:
            baseMeta["external_sub_tracks"] = subTracks

        if live:
            # live masters carry separate audio renditions - give the master straight to the player
            sts = self.cm.getPage(master, self.defaultParams)[0]
            if not sts and geo:
                SetIPTVPlayerLastHostError(geoMsg)
                return []
            return [{"name": "HLS live", "url": strwithmeta(master, baseMeta), "need_resolve": 0}]

        urlTab = []
        hls = getDirectM3U8Playlist(strwithmeta(master, dict(baseMeta)), checkExt=False, checkContent=True, mergeAltAudio=False)
        for item in hls:
            videoUrl = strwithmeta(item["url"])
            meta = dict(videoUrl.meta)
            meta.update(baseMeta)
            if not subTracks:
                meta.pop("external_sub_tracks", None)
            name = "%sp" % item.get("height") if item.get("height") else item.get("name", "HLS")
            audios = item.get("alt_audio_streams") or []
            if audios:
                audio = audios[0]
                for stream in audios:
                    if getattr(stream, "default", False):
                        audio = stream
                        break
                # split CMAF/TS renditions: mux audio + video with ffmpeg (like ARTE)
                meta.update({"audio_url": strwithmeta(audio.absolute_uri, dict(baseMeta)), "video_url": strwithmeta(videoUrl, dict(baseMeta)),
                             "iptv_use_ffmpeg": True, "ff_out_container": "matroska", "iptv_format": "mkv"})
                meta.pop("iptv_proto", None)
                url = self.up.decorateUrl("merge://audio_url|video_url", meta)
            else:
                url = strwithmeta(videoUrl, meta)
            urlTab.append({"name": name, "url": url, "need_resolve": 0, "bitrate": item.get("bitrate", 0)})

        if not urlTab:
            if geo:
                SetIPTVPlayerLastHostError(geoMsg)
                return []
        else:
            try:
                urlTab.sort(key=lambda x: int(x.get("bitrate") or 0), reverse=True)
            except Exception:
                printExc()
        # the master itself: adaptive, and the only option for gstplayer (no merge:// support)
        urlTab.append({"name": "HLS (adaptive)", "url": strwithmeta(master, dict(baseMeta)), "need_resolve": 0})
        sidecarTxt = cItem.get("desc", "")
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        return []

    ###################################################
    # info / favourites
    ###################################################
    def _genres(self, genres):
        names = []
        for genre in genres or []:
            name = (genre or {}).get("name", "")
            if name and name not in NON_GENRES and name not in names:
                names.append(name)
        return ", ".join(names)

    def getArticleContent(self, cItem):
        printDBG("SVTPlaySE.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        category = cItem.get("category", "")
        try:
            if category in ("svt_series", "svt_season"):
                query = ("query($slugs:[String!]!) { listablesBySlug(slugs:$slugs) { __typename name longDescription image { id changed } "
                         "restrictions { onlyAvailableInSweden } ... on Content { genres { name } countriesOfOriginWithNames { name } } "
                         "... on TvSeries { seasons { number } } } }")
                listables = self._gql(query, {"slugs": [cItem.get("slug", "")]}).get("listablesBySlug") or []
                if listables:
                    info = listables[0]
                    text = self.cleanHtmlStr(info.get("longDescription") or "") or text
                    icon = self._imageUrl(info.get("image"), 800) or icon
                    if info.get("genres"):
                        otherInfo["genres"] = self._genres(info["genres"])
                    countries = ", ".join([c.get("name", "") for c in info.get("countriesOfOriginWithNames") or [] if c.get("name")])
                    if countries:
                        otherInfo["country"] = countries
                    if info.get("seasons"):
                        otherInfo["seasons"] = str(len(info["seasons"]))
                    otherInfo["status"] = self._geoLabel() if (info.get("restrictions") or {}).get("onlyAvailableInSweden") else _("Available worldwide")
            elif category == "svt_video" and not self._videoId(cItem).startswith("ch-"):
                query = ("query($ids:[String!]) { listables(ids:$ids) { __typename name longDescription image { id changed } "
                         "restrictions { onlyAvailableInSweden } "
                         "... on Single { productionYear duration originalProgramTitle genres { name } countriesOfOriginWithNames { name } validToFormatted } "
                         "... on Episode { productionYear duration genres { name } validToFormatted positionInSeason parent { name } } "
                         "... on Clip { duration validToFormatted } } }")
                listables = self._gql(query, {"ids": [self._videoId(cItem)]}).get("listables") or []
                if listables:
                    info = listables[0]
                    text = self.cleanHtmlStr(info.get("longDescription") or "") or text
                    icon = self._imageUrl(info.get("image"), 800) or icon
                    if info.get("productionYear"):
                        otherInfo["year"] = str(info["productionYear"])
                    if info.get("duration"):
                        otherInfo["duration"] = "%d min" % max(1, int(info["duration"]) // 60)
                    if info.get("genres"):
                        otherInfo["genres"] = self._genres(info["genres"])
                    countries = ", ".join([c.get("name", "") for c in info.get("countriesOfOriginWithNames") or [] if c.get("name")])
                    if countries:
                        otherInfo["country"] = countries
                    if info.get("originalProgramTitle") and info["originalProgramTitle"] != cItem.get("s_title", ""):
                        otherInfo["original_title"] = info["originalProgramTitle"]
                    if info.get("validToFormatted"):
                        otherInfo["remaining"] = info["validToFormatted"]
                    if info.get("positionInSeason"):
                        otherInfo["episodes"] = info["positionInSeason"]
                    otherInfo["status"] = self._geoLabel() if (info.get("restrictions") or {}).get("onlyAvailableInSweden") else _("Available worldwide")
            elif category == "svt_channel":
                otherInfo["status"] = self._geoLabel()
        except Exception:
            printExc()

        if cItem.get("meta_type") in ("movie", "tv") and cItem.get("meta_title"):
            # films and series: the SVT text stays, moviemeta adds rating / cast / director
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""))
            except Exception:
                printExc()
                meta = {}
            for key, value in (meta.get("info", {}) or {}).items():
                if value:
                    otherInfo.setdefault(key, value)
            if not icon:
                icon = meta.get("poster", "")
            if not text:
                text = meta.get("plot", "")
        return [{"title": title, "text": text,
                 "images": [{"title": "", "url": icon}] if icon else [],
                 "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("svt_"):
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
        printDBG("SVTPlaySE.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "svt_selection":
            self.listSelection(self.currItem)
        elif category == "svt_start":
            self.listStart(self.currItem)
        elif category == "svt_channels":
            self.listChannels(self.currItem)
        elif category == "svt_az_letters":
            self.listAZLetters(self.currItem)
        elif category == "svt_az":
            self.listAZ(self.currItem)
        elif category == "svt_categories":
            self.listCategories(self.currItem)
        elif category == "svt_category":
            self.listCategory(self.currItem)
        elif category == "svt_series":
            self.listSeasons(self.currItem)
        elif category == "svt_season":
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
        CHostBase.__init__(self, SVTPlaySE(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("svtplayse")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("svt_series", "svt_season", "svt_video", "svt_channel")
