# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# UR Play (urplay.se) - the Swedish public education broadcaster: latest, popular, series A-Ö, the site's categories
# (rows and sub-categories), search; series -> seasons -> episodes; HLS with the "Uppläst undertext" audio and the
# audio-described / sign-language versions as own links, WebVTT subtitles. Some titles are only open in Sweden.
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
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
    return "https://urplay.se/"


SEARCH_API = "https://urplay.se/api/v1/search"
EPISODES_API = "https://urplay.se/api/v1/season_episodes?seriesId=%s"
INFO_API = "https://urplay.se/api/v1/episode_info?programId=%s"
SOURCES_API = "https://media-api.urplay.se/config-streaming/v1/urplay/sources/%s"
IMAGE_URL = "https://assets.ur.se/id/%s/images/1_l.jpg"
ROWS = 24  # the search API answers 24 rows per request, whatever "rows" asks for

# the Next.js flight data of the HTML pages (categories, series seasons)
RSC_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)
ID_RE = re.compile(r'/(?:program|serie)/(\d+)')
# titles only open in Sweden lack the "uraccess" platform (checked against the 403 "restricted_to_sweden_only")
OPEN_PLATFORM = "uraccess"
FILM_GENRES = ("Dokumentärfilm", "Kortfilm", "Spelfilm", "Långfilm", "Film")
GEO_LABEL = "(geo SE)"


class URPlay(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "ur_id", "ur_query", "ur_slug", "block_id",
                  "season", "episode", "icon", "desc", "geo", "ur_genre")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "urplay", "cookie": "urplay.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = {"User-Agent": self.cm.getDefaultUserAgent(), "Accept": "application/json, text/html, */*",
                       "Referer": self.MAIN_URL, "Origin": "https://urplay.se"}
        self.defaultParams = {"header": self.HEADER}
        self.categoryCache = None
        self.watchedHelper = IPTVWatchedHelper("urplay")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if not url or not cItem.get("ur_id"):
                return ""
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url
            if cItem.get("category") in ("ur_series", "ur_season"):
                return "series:%s" % url
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _json(self, url):
        params = dict(self.defaultParams)
        params["ignore_http_code_ranges"] = [(400, 499)]
        sts, data = self.cm.getPage(url, params)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG("URPlay._json no JSON [%s]" % url)
        return None

    def _rsc(self, url):
        # the page data of the server-rendered pages: the joined self.__next_f chunks (JS string literals)
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return ""
        parts = []
        for part in RSC_RE.findall(data):
            try:
                parts.append(json.loads('"%s"' % part))
            except Exception:
                continue
        return "".join(parts)

    @staticmethod
    def _rscValue(rsc, key, start=0):
        idx = rsc.find('"%s":' % key, start)
        if idx < 0:
            return None
        try:
            return json.JSONDecoder().raw_decode(rsc, idx + len(key) + 3)[0]
        except Exception:
            printExc()
        return None

    @staticmethod
    def _qv(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return ensure_str(value)

    def _searchUrl(self, query, page):
        pairs = []
        for key in sorted(query.keys()):
            if key in ("start", "rows"):
                continue
            value = query[key]
            if isinstance(value, list):
                for val in value:
                    pairs.append((key + "[]", val))
            elif value is not None:
                pairs.append((key, value))
        if "platform" not in query:
            pairs.append(("platform", "urplay"))
        pairs.extend([("rows", ROWS), ("start", (page - 1) * ROWS)])
        return SEARCH_API + "?" + "&".join(["%s=%s" % (urllib_quote_plus(self._qv(k)), urllib_quote_plus(self._qv(v))) for k, v in pairs])

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except Exception:
            return 1

    @staticmethod
    def _image(prod):
        image = prod.get("image") or {}
        if isinstance(image, dict):
            for key in ("640x360", "480x270", "960x540", "1280x720"):
                if image.get(key):
                    return image[key]
        if prod.get("imageUrl"):
            return prod["imageUrl"]
        return IMAGE_URL % prod["id"] if prod.get("id") else ""

    @staticmethod
    def _isGeo(prod):
        platforms = prod.get("accessiblePlatforms")
        return isinstance(platforms, dict) and bool(platforms) and OPEN_PLATFORM not in platforms

    @staticmethod
    def _number(text):
        match = re.search(r'(\d+)', str(text or ""))
        return match.group(1) if match else ""

    def _desc(self, prod, geo):
        parts = []
        try:
            if prod.get("duration"):
                parts.append("%d min" % max(1, int(prod["duration"]) // 60))
        except Exception:
            pass
        if prod.get("mainGenre"):
            parts.append(self.cleanHtmlStr(prod["mainGenre"]))
        if geo:
            parts.append(GEO_LABEL)
        text = self.cleanHtmlStr(prod.get("usp") or prod.get("description") or "")
        return "\n".join([x for x in (" | ".join(parts), text) if x])

    ###################################################
    # rows
    ###################################################
    def _addProduct(self, cItem, prod, show="", season=""):
        try:
            if not isinstance(prod, dict) or not prod.get("id"):
                return False
            pid = str(prod["id"])
            link = prod.get("link") or ""
            ptype = prod.get("productType") or ("series" if link.startswith("/serie/") else "program")
            if not link:
                slug = prod.get("slug") or pid
                link = "/%s/%s" % ("serie" if ptype == "series" else "program", slug)
            title = self.cleanHtmlStr(prod.get("title") or "")
            if not title:
                return False
            mainTitle = self.cleanHtmlStr(prod.get("mainTitle") or prod.get("seriesTitle") or "")
            geo = self._isGeo(prod)
            params = stripPagerKeys(dict(cItem), ("ur_query", "ur_pattern", "block_id", "ur_slug", "season", "episode", "search_pattern"))
            params.update({"good_for_fav": True, "ur_id": pid, "url": self.getFullUrl(link), "icon": self._image(prod),
                           "desc": self._desc(prod, geo), "geo": geo, "ur_genre": self.cleanHtmlStr(prod.get("mainGenre") or "")})
            if ptype == "series":
                params.update({"category": "ur_series", "title": title, "s_title": title})
                self.addDir(params)
                return True
            episode = str(prod.get("episodeNumber") or "")
            if show:
                if IsMediaNamingNormalized() and season and episode:
                    label = "%s - %s" % (show, formatSxxExx(season, episode))
                    label = "%s - %s" % (label, title) if title != show else label
                else:
                    label = "%s - %s" % (show, title) if title != show else title
                params.update({"s_title": show, "season": season, "episode": episode})
            else:
                label = "%s - %s" % (mainTitle, title) if mainTitle and mainTitle != title else title
                params["s_title"] = mainTitle or title
            params.update({"category": "ur_video", "title": label})
            if prod.get("format") == "audio":
                self.addAudio(params)
            else:
                self.addVideo(params)
            return True
        except Exception:
            printExc()
        return False

    ###################################################
    # lists
    ###################################################
    def listSearchApi(self, cItem, pattern=""):
        page = self._page(cItem)
        try:
            query = json_loads(cItem.get("ur_query") or "{}")
        except Exception:
            query = {}
        if pattern:
            query["query"] = pattern
        data = self._json(self._searchUrl(query, page))
        if not isinstance(data, dict):
            return
        count = 0
        for prod in data.get("results") or []:
            if self._addProduct(cItem, prod):
                count += 1
        hasNext = bool(count) and bool(data.get("nextPageInfo"))
        # the list is read from ur_query + page, the template only lets "Jump" through
        addPagingItems(self, dict(cItem, desc=""), page, hasNext, 0, self.MAIN_URL + "sok#page={page}")

    def _categories(self):
        if self.categoryCache is None:
            items = self._rscValue(self._rsc(self.MAIN_URL), "categoryMenuItems") or []
            items = [c for c in items if isinstance(c, dict) and c.get("slug") and not c.get("hideCategory")]
            if items:
                self.categoryCache = items
            return items
        return self.categoryCache

    def listCategories(self, cItem):
        for cat in self._categories():
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "ur_category", "title": self.cleanHtmlStr(cat.get("name") or cat["slug"]),
                           "ur_slug": cat["slug"], "url": self.MAIN_URL + "bladdra/" + cat["slug"], "icon": cat.get("imageUrl", ""), "desc": ""})
            self.addDir(params)

    def _categoryBlocks(self, rsc):
        idx = rsc.find('"blocks":[{')
        blocks = self._rscValue(rsc, "blocks", idx) if idx >= 0 else None
        return [b for b in (blocks or []) if isinstance(b, dict)]

    def listCategory(self, cItem):
        slug = cItem.get("ur_slug", "")
        rsc = self._rsc(self.MAIN_URL + "bladdra/" + slug)
        if not rsc:
            return
        base = stripPagerKeys(dict(cItem))
        base.update({"good_for_fav": True, "desc": ""})
        allParams = self._rscValue(rsc, "initialSearchParams")
        if isinstance(allParams, dict) and allParams:
            params = dict(base)
            params.update({"category": "ur_list", "title": _("All programmes"), "ur_query": json_dumps(allParams)})
            self.addDir(params)
        for tag in self._rscValue(rsc, "tags") or []:
            # level 1 is the curated page itself (its rows follow below)
            if not isinstance(tag, dict) or int(tag.get("level") or 0) < 2 or not isinstance(tag.get("query"), dict):
                continue
            params = dict(base)
            params.update({"category": "ur_list", "title": self.cleanHtmlStr(tag.get("name") or ""), "ur_query": json_dumps(tag["query"])})
            self.addDir(params)
        for block in self._categoryBlocks(rsc):
            title = self.cleanHtmlStr(block.get("title") or "")
            if block.get("blockType") == "search" and isinstance(block.get("searchQuery"), dict):
                if title:
                    params = dict(base)
                    params.update({"category": "ur_list", "title": title, "ur_query": json_dumps(block["searchQuery"])})
                    self.addDir(params)
                continue
            products = [p for p in (block.get("products") or block.get("lightweightProducts") or []) if isinstance(p, dict)]
            if len(products) == 1:
                self._addProduct(base, products[0])
            elif products and title:
                params = dict(base)
                params.update({"category": "ur_block", "title": title, "block_id": str(block.get("id") or "")})
                self.addDir(params)

    def listBlock(self, cItem):
        rsc = self._rsc(self.MAIN_URL + "bladdra/" + cItem.get("ur_slug", ""))
        for block in self._categoryBlocks(rsc):
            if str(block.get("id") or "") == cItem.get("block_id"):
                for prod in block.get("products") or block.get("lightweightProducts") or []:
                    self._addProduct(cItem, prod)
                break

    def listSeries(self, cItem):
        rsc = self._rsc(cItem.get("url", ""))
        show = cItem.get("s_title") or cItem.get("title", "")
        seasons = [s for s in (self._rscValue(rsc, "superSeriesSeasons") or []) if isinstance(s, dict) and s.get("id")]
        if len(seasons) > 1:
            for season in seasons:
                label = self.cleanHtmlStr(season.get("label") or season.get("title") or "")
                params = stripPagerKeys(dict(cItem))
                params.update({"good_for_fav": True, "category": "ur_season", "ur_id": str(season["id"]),
                               "url": self.getFullUrl(season.get("link") or "/serie/%s" % season["id"]),
                               "title": "%s - %s" % (show, label) if label else show, "s_title": show,
                               "season": self._number(label), "desc": cItem.get("desc", "")})
                self.addDir(params)
            return
        # one season: its episodes in place of the season folder
        season = self._number(self._rscValue(rsc, "seriesLabel") or "") or "1"
        self.listEpisodes(dict(cItem, season=season, s_title=show))

    def listEpisodes(self, cItem):
        data = self._json(EPISODES_API % cItem.get("ur_id", ""))
        if not isinstance(data, dict):
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        for prod in data.get("accessibleEpisodes") or []:
            self._addProduct(cItem, prod, show, cItem.get("season", ""))

    ###################################################
    # links
    ###################################################
    @staticmethod
    def _subTracks(tracks):
        # the HLS subtitle renditions of the master (their .vtt segments are fetched by the framework where used)
        ret = []
        for track in tracks or []:
            lang = str(track.get("lang") or "sv").lower()
            ret.append(dict(track, lang="sv" if lang.startswith(("sv", "swe")) else lang[:2], title=track.get("title") or "Svenska"))
        return ret

    def _streamLinks(self, pid, label="", allVariants=True):
        # ([links], "geo" | "none" | "") for one program id
        data = self._json(SOURCES_API % pid)
        if not isinstance(data, dict):
            return [], "none"
        if data.get("message") == "restricted_to_sweden_only":
            return [], "geo"
        master = (data.get("sources") or {}).get("hls") or ""
        if not self.cm.isValidUrl(master):
            return [], "none"
        baseMeta = {"iptv_proto": "m3u8", "Referer": self.MAIN_URL, "Origin": "https://urplay.se", "User-Agent": self.HEADER["User-Agent"]}
        hls = getDirectM3U8Playlist(strwithmeta(master, dict(baseMeta)), checkExt=False, checkContent=True, mergeAltAudio=False)
        if not hls:
            return [], "none"
        hls.sort(key=lambda x: int(x.get("bitrate") or 0), reverse=True)
        subTracks = self._subTracks(strwithmeta(hls[0]["url"]).meta.get("external_sub_tracks")) if allVariants else []
        links = []
        for num, item in enumerate(hls):
            if num and not allVariants:
                break
            audios = item.get("alt_audio_streams") or []
            default = None
            for audio in audios:
                if audio.default:
                    default = audio
                    break
            if default is None and audios:
                default = audios[0]
            name = "%sp" % item["height"] if item.get("height") else "%d kbit/s" % (int(item.get("bitrate") or 0) // 1000)
            links.append(self._link(item, default, "%s - %s" % (name, label) if label else name, baseMeta, subTracks))
            if num == 0:
                # "Uppläst undertext" (the subtitles read out) and other extra audio tracks of the best quality
                for audio in audios:
                    if audio is not default:
                        links.append(self._link(item, audio, "%s - %s" % (name, self.cleanHtmlStr(audio.name or audio.language or "")), baseMeta, subTracks))
        return links, ""

    def _link(self, item, audio, name, baseMeta, subTracks):
        meta = dict(baseMeta)
        if subTracks:
            meta["external_sub_tracks"] = subTracks
        if audio is None:
            url = strwithmeta(str(item["url"]), meta)
        elif not item.get("height"):
            # audio-only program: the audio rendition itself
            url = strwithmeta(audio.absolute_uri, meta)
        else:
            # fMP4 video without sound + the audio rendition, muxed with ffmpeg (like SVT Play)
            meta.update({"audio_url": strwithmeta(audio.absolute_uri, dict(baseMeta)), "video_url": strwithmeta(str(item["url"]), dict(baseMeta)),
                         "iptv_use_ffmpeg": True, "ff_out_container": "matroska", "iptv_format": "mkv"})
            meta.pop("iptv_proto", None)
            url = self.up.decorateUrl("merge://audio_url|video_url", meta)
        return {"name": name, "url": url, "need_resolve": 0}

    def _programId(self, cItem):
        pid = str(cItem.get("ur_id") or "")
        if not pid:
            match = ID_RE.search(cItem.get("url", ""))
            pid = match.group(1) if match else ""
        return pid

    def getLinksForVideo(self, cItem):
        pid = self._programId(cItem)
        printDBG("URPlay.getLinksForVideo [%s]" % pid)
        if not pid:
            return []
        links, error = self._streamLinks(pid)
        info = self._json(INFO_API % pid)
        info = info if isinstance(info, dict) else {}
        for version in info.get("allVersions") or []:
            vid = str((version or {}).get("id") or "")
            if not vid or vid == pid:
                continue
            kind = version.get("version") or ""
            label = {"AUDIO_DESCRIPTION": _("Audio description"), "SIGN_LANGUAGE": "Teckenspråkstolkat", "ORIGINAL": "Original"}.get(kind, kind)
            links.extend(self._streamLinks(vid, label, False)[0])
        pod = (info.get("about") or {}).get("podInfo") or {}
        if pod.get("isDownloadable") and self.cm.isValidUrl(pod.get("file") or ""):
            links.append({"name": "MP4", "url": strwithmeta(pod["file"], {"Referer": self.MAIN_URL, "User-Agent": self.HEADER["User-Agent"]}), "need_resolve": 0})
        if not links:
            SetIPTVPlayerLastHostError(_("This content is not available in your region.") if error == "geo" else _("No stream available"))
            return []
        sidecarTxt = cItem.get("desc", "").split("\n")[-1]
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("ur_genre"):
            otherInfo["genre"] = cItem["ur_genre"]
        if cItem.get("category") == "ur_video":
            info = self._json(INFO_API % self._programId(cItem))
            info = info if isinstance(info, dict) else {}
            try:
                about = info.get("about") or {}
                if about.get("description"):
                    text = self.cleanHtmlStr(about["description"].replace("\n", "[/br]"))
                if about.get("productionYear"):
                    otherInfo["year"] = str(about["productionYear"])
                if about.get("duration"):
                    otherInfo["duration"] = "%d min" % max(1, int(about["duration"]) // 60)
                if about.get("keywords"):
                    otherInfo["categories"] = ", ".join([self.cleanHtmlStr(k) for k in about["keywords"] if k])
                if about.get("languagesTranslations"):
                    otherInfo["language"] = ", ".join(about["languagesTranslations"])
                if about.get("subtitleLanguagesTranslations"):
                    otherInfo["subtitles"] = ", ".join(about["subtitleLanguagesTranslations"])
                if about.get("internationalTitle"):
                    otherInfo["original_title"] = self.cleanHtmlStr(about["internationalTitle"])
                people = []
                for person in about.get("participants") or []:
                    name = ("%s %s" % (person.get("firstname") or "", person.get("lastname") or "")).strip()
                    if name:
                        people.append("%s (%s)" % (name, person["role"]) if person.get("role") else name)
                if people:
                    otherInfo["cast"] = ", ".join(people[:10])
                ages = ((info.get("pedagogical") or {}).get("product") or {}).get("typicalAgeRangeTranslations") or []
                if ages:
                    otherInfo["age_limit"] = ", ".join(ages)
                until = (((about.get("accessiblePlatforms") or {}).get("urplay") or {}).get("endTime") or "")[:10]
                if until:
                    otherInfo["remaining"] = until
                otherInfo["status"] = (_("Only available in %s") % _("Sweden")) if cItem.get("geo") else _("Available worldwide")
                year = otherInfo.get("year", "")
                if cItem.get("ur_genre") in FILM_GENRES and year:
                    # films: the UR text stays, moviemeta adds rating / cast / director
                    meta = getMeta("movie", otherInfo.get("original_title") or cItem.get("s_title") or title, year) or {}
                    for key, value in (meta.get("info") or {}).items():
                        if value:
                            otherInfo.setdefault(key, value)
                    icon = icon or meta.get("poster", "")
            except Exception:
                printExc()
        return [{"title": title, "text": text.replace("\n", "[/br]"), "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("ur_"):
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
        printDBG("URPlay.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            menu = [{"category": "ur_list", "title": _("Latest"), "ur_query": json_dumps({"sort": "published"})},
                    {"category": "ur_list", "title": _("Popular"), "ur_query": json_dumps({"sort": "most_viewed"})},
                    {"category": "ur_list", "title": "%s A-Ö" % _("Series"), "ur_query": json_dumps({"product_type": "series", "sort": "title"})},
                    {"category": "ur_categories", "title": _("Categories")}]
            for item in menu:
                item["good_for_fav"] = item["category"] == "ur_list"
            self.listsTab(menu + self.searchItems(), {"name": "category"})
        elif category == "ur_list":
            self.listSearchApi(self.currItem)
        elif category == "ur_categories":
            self.listCategories(self.currItem)
        elif category == "ur_category":
            self.listCategory(self.currItem)
        elif category == "ur_block":
            self.listBlock(self.currItem)
        elif category == "ur_series":
            self.listSeries(self.currItem)
        elif category == "ur_season":
            self.listEpisodes(self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category", "category": "ur_search", "ur_query": "{}", "ur_pattern": searchPattern})
            self.listSearchApi(cItem, searchPattern)
        elif category == "ur_search":
            # "Next page" / "Jump" of a search result: the pattern travels in the item
            self.listSearchApi(self.currItem, self.currItem.get("ur_pattern", ""))
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, URPlay(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("urplay")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("ur_video", "ur_series", "ur_season")
