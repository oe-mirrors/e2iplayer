# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# NRK TV (tv.nrk.no) - the Norwegian public broadcaster: front page and category pages with their rows, series ->
# seasons -> episodes, search; HLS from the psapi playback manifest (no DRM), WebVTT subtitles. Many titles are
# only open in Norway ("(geo NO)" in the description), the live channels are Norway-only and left out.
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
    return "https://tv.nrk.no/"


API = "https://psapi.nrk.no/"
# the playback API hands out working stream urls only with this Accept header (yt-dlp #12192)
PLAYBACK_ACCEPT = "application/vnd.nrk.psapi+json; version=9; player=tv-player; device=player-core"
PROGRAM_URL = "https://tv.nrk.no/se?v=%s"
SECTION_PAGE = 100
GEO_LABEL = "(geo NO)"
PLAYABLE_PLUGS = ("episode", "standaloneProgram")
DURATION_RE = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?')
UNDECODABLE_AUDIO = ("ac-3", "ec-3")


class NRKTV(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "s_title", "prf_id", "series_id", "series_type", "season_href",
                  "season", "episode", "page_id", "section_id", "icon", "desc", "geo")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "nrktv", "cookie": "nrktv.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = {"User-Agent": self.cm.getDefaultUserAgent(), "Accept": "application/json, */*",
                       "Referer": self.MAIN_URL, "Origin": "https://tv.nrk.no"}
        self.defaultParams = {"header": self.HEADER}
        self.watchedHelper = IPTVWatchedHelper("nrktv")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("type", "") in ("video", "audio") and cItem.get("prf_id"):
                return "video:%s" % cItem["prf_id"]
            if cItem.get("category") == "nrk_series" and cItem.get("series_id"):
                return "series:%s" % cItem["series_id"]
            if cItem.get("category") == "nrk_season" and cItem.get("season_href"):
                return "season:%s" % cItem["season_href"]
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _json(self, path, accept=""):
        params = dict(self.defaultParams)
        params["ignore_http_code_ranges"] = [(400, 499)]
        if accept:
            params["header"] = dict(self.HEADER)
            params["header"]["Accept"] = accept
        url = path if path.startswith("http") else API + path.lstrip("/")
        sts, data = self.cm.getPage(url, params)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG("NRKTV._json no JSON [%s]" % url)
        return None

    @staticmethod
    def _img(obj, width=600):
        # webImages [{uri|url|imageUrl, width|pixelWidth}]: the smallest one at least `width` wide, else the largest
        if isinstance(obj, dict):
            obj = obj.get("webImages") or obj.get("images") or []
        best, bestW = "", 0
        for image in obj if isinstance(obj, list) else []:
            if not isinstance(image, dict):
                continue
            url = image.get("uri") or image.get("url") or image.get("imageUrl") or ""
            try:
                imgW = int(image.get("width") or image.get("pixelWidth") or 0)
            except Exception:
                imgW = 0
            if not url:
                continue
            if not best or (bestW < width and imgW > bestW) or (width <= imgW < bestW):
                best, bestW = url, imgW
        return best

    @staticmethod
    def _minutes(value):
        try:
            if isinstance(value, (int, float)):
                secs = float(value)
            else:
                match = DURATION_RE.match(str(value or ""))
                if not match:
                    return ""
                secs = int(match.group(1) or 0) * 3600 + int(match.group(2) or 0) * 60 + float(match.group(3) or 0)
            return "%d min" % max(1, int(secs + 30) // 60) if secs > 0 else ""
        except Exception:
            return ""

    def _desc(self, parts, geo, text):
        parts = [p for p in parts if p]
        if geo:
            parts.append(GEO_LABEL)
        return "\n".join([x for x in (" | ".join(parts), self.cleanHtmlStr(text or "")) if x])

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except Exception:
            return 1

    @staticmethod
    def _seasonUrl(href):
        return "https://tv.nrk.no" + href.replace("/tv/catalog/series/", "/serie/").replace("/seasons/", "/sesong/")

    ###################################################
    # rows
    ###################################################
    def _addSeries(self, cItem, seriesId, title, icon, desc, geo=False):
        params = stripPagerKeys(dict(cItem), ("page_id", "section_id", "season_href", "season", "episode", "next_href"))
        params.update({"good_for_fav": True, "category": "nrk_series", "series_id": seriesId, "url": self.MAIN_URL + "serie/" + seriesId,
                       "title": title, "s_title": title, "icon": icon, "desc": desc, "geo": geo})
        self.addDir(params)

    def _addProgram(self, cItem, prfId, title, icon, desc, geo, extra=None):
        params = stripPagerKeys(dict(cItem), ("page_id", "section_id", "season_href", "season", "episode", "next_href", "series_id"))
        params.update({"good_for_fav": True, "category": "nrk_video", "prf_id": prfId, "url": PROGRAM_URL % prfId,
                       "title": title, "icon": icon, "desc": desc, "geo": geo})
        params.update(extra or {})
        self.addVideo(params)

    def _addPlug(self, cItem, plug):
        try:
            ttype = plug.get("targetType") or ""
            content = plug.get("displayContractContent") or {}
            target = plug.get(ttype) or {}
            title = self.cleanHtmlStr(content.get("contentTitle") or "")
            if not title or not isinstance(target, dict):
                return False
            icon = self._img(content.get("displayContractImage")) or self._img(content.get("fallbackImage"))
            geo = bool((target.get("usageRights") or {}).get("isGeoBlocked"))
            if ttype == "series" and target.get("seriesId"):
                self._addSeries(cItem, target["seriesId"], title, icon, self._desc([], geo, content.get("description")), geo)
                return True
            if ttype == "page" and target.get("pageId"):
                params = stripPagerKeys(dict(cItem), ("section_id",))
                params.update({"good_for_fav": True, "category": "nrk_page", "page_id": target["pageId"], "title": title, "icon": icon,
                               "url": self.MAIN_URL + target["pageId"], "desc": self.cleanHtmlStr(content.get("description") or "")})
                self.addDir(params)
                return True
            if ttype in PLAYABLE_PLUGS and target.get("programId"):
                age = (target.get("legalAge") or {}).get("displayValue") or ""
                desc = self._desc([self._minutes(target.get("duration")), age], geo, content.get("description"))
                self._addProgram(cItem, target["programId"], title, icon, desc, geo, {"s_title": title})
                return True
        except Exception:
            printExc()
        # channel / liveChannelProgram: the live channels only play in Norway
        return False

    ###################################################
    # lists
    ###################################################
    def listCategories(self, cItem):
        data = self._json("tv/pages")
        for page in (data or {}).get("pageListItems") or []:
            if not isinstance(page, dict) or not page.get("id"):
                continue
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "nrk_page", "page_id": page["id"], "url": self.MAIN_URL + page["id"],
                           "title": self.cleanHtmlStr(page.get("title") or page["id"]), "icon": self._img(page.get("image")), "desc": ""})
            self.addDir(params)

    def _sections(self, pageId):
        data = self._json("tv/pages/" + pageId)
        ret = []
        for section in (data or {}).get("sections") or []:
            included = (section or {}).get("included") or {}
            plugs = [p for p in (included.get("plugs") or []) if isinstance(p, dict)]
            if plugs and section.get("id"):
                ret.append((section["id"], self.cleanHtmlStr(included.get("title") or ""), plugs))
        return ret

    def listPage(self, cItem):
        pageId = cItem.get("page_id", "")
        for sectionId, title, plugs in self._sections(pageId):
            if len(plugs) == 1:
                # the big single teaser rows (no title most of the time)
                self._addPlug(cItem, plugs[0])
                continue
            if not title:
                titles = [self.cleanHtmlStr((p.get("displayContractContent") or {}).get("contentTitle") or "") for p in plugs[:2]]
                title = ", ".join([t for t in titles if t]) + " ..."
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "nrk_section", "section_id": sectionId, "title": title,
                           "desc": "%s: %d" % (_("Programmes"), len(plugs))})
            self.addDir(params)

    def listSection(self, cItem):
        page = self._page(cItem)
        for sectionId, title, plugs in self._sections(cItem.get("page_id", "")):
            if sectionId != cItem.get("section_id"):
                continue
            # the category pages put up to some hundred titles in one row - paged here
            start = (page - 1) * SECTION_PAGE
            for plug in plugs[start:start + SECTION_PAGE]:
                self._addPlug(cItem, plug)
            lastPage = (len(plugs) + SECTION_PAGE - 1) // SECTION_PAGE
            addPagingItems(self, dict(cItem, desc=""), page, page < lastPage, lastPage, self.MAIN_URL + "#page={page}")
            break

    def listSeries(self, cItem):
        seriesId = cItem.get("series_id", "")
        data = self._json("tv/catalog/series/" + seriesId)
        if not isinstance(data, dict):
            return
        seriesType = data.get("seriesType") or ""
        info = data.get(seriesType) or {}
        show = self.cleanHtmlStr((info.get("titles") or {}).get("title") or "") or cItem.get("s_title") or cItem.get("title", "")
        links = data.get("_links") or {}
        entries = [s for s in (links.get("seasons") or []) if isinstance(s, dict) and s.get("href")]
        extra = links.get("extramaterial")
        if isinstance(extra, dict) and extra.get("href"):
            entries.append(extra)
        base = stripPagerKeys(dict(cItem), ("next_href",))
        base.update({"s_title": show, "series_type": seriesType})
        if not entries:
            self._addEpisodes(base, data)
            return
        if len(entries) == 1:
            # its "Next page" rows must open the season list (listSeries does not page)
            self.listSeason(dict(base, category="nrk_season", season_href=entries[0]["href"], season=self._seasonNumber(entries[0], seriesType)))
            return
        for entry in entries:
            label = self.cleanHtmlStr(entry.get("title") or entry.get("name") or "")
            params = dict(base)
            params.update({"good_for_fav": True, "category": "nrk_season", "season_href": entry["href"], "url": self._seasonUrl(entry["href"]),
                           "title": "%s - %s" % (show, label) if label else show, "season": self._seasonNumber(entry, seriesType)})
            self.addDir(params)

    @staticmethod
    def _seasonNumber(entry, seriesType):
        name = str(entry.get("name") or "")
        return name if seriesType == "sequential" and name.isdigit() else ""

    def listSeason(self, cItem):
        page = self._page(cItem)
        href = cItem.get("next_href") if page > 1 and cItem.get("next_href") else cItem.get("season_href", "")
        data = self._json(href)
        if not isinstance(data, dict):
            return
        count, nextHref = self._addEpisodes(cItem, data)
        # the API hands out the next slice as a link: no page count, no "Jump"
        addPagingItems(self, dict(cItem, desc=""), page, bool(count and nextHref), 0, "", {"next_href": nextHref})

    def _addEpisodes(self, cItem, data):
        embedded = data.get("_embedded") or {}
        nextHref = ((data.get("_links") or {}).get("next") or {}).get("href") or ""
        episodes = []
        for key in ("episodes", "instalments"):
            value = embedded.get(key)
            if isinstance(value, dict):
                nextHref = nextHref or ((value.get("_links") or {}).get("next") or {}).get("href") or ""
                value = (value.get("_embedded") or {}).get(key)
            if value:
                episodes = value
                break
        show = cItem.get("s_title", "")
        season = cItem.get("season", "")
        count = 0
        coming = ""
        for episode in episodes:
            try:
                prfId = episode.get("prfId") or episode.get("id") or ""
                titles = episode.get("titles") or {}
                name = self.cleanHtmlStr(titles.get("title") or "")
                availability = episode.get("availability") or {}
                if availability.get("status") == "coming":
                    coming = coming or self.cleanHtmlStr(availability.get("label") or "")
                    continue
                if not prfId or not name or availability.get("status") == "expired":
                    continue
                number = str(episode.get("sequenceNumber") or "")
                if IsMediaNamingNormalized() and season and number:
                    title = "%s - %s" % (show, formatSxxExx(season, number))
                    epName = re.sub(r'^\d+\.\s*', '', name)
                    title = "%s - %s" % (title, epName) if epName else title
                else:
                    title = "%s - %s" % (show, name) if show and show != name else name
                geo = bool(((episode.get("usageRights") or {}).get("geoBlock") or {}).get("isGeoBlocked"))
                age = ((((episode.get("legalAge") or {}).get("body") or {}).get("rating") or {}).get("displayAge")) or ""
                desc = self._desc([self._minutes(episode.get("durationInSeconds") or episode.get("duration")), age], geo, titles.get("subtitle"))
                self._addProgram(cItem, prfId, title, self._img(episode.get("image")) or cItem.get("icon", ""), desc, geo,
                                 {"s_title": show, "season": season, "episode": number})
                count += 1
            except Exception:
                printExc()
        if not count and coming:
            # only announced episodes so far ("Kommer om 9 dager")
            SetIPTVPlayerLastHostError("NRK: %s" % coming)
        return count, nextHref

    def listSearchResult(self, cItem, searchPattern):
        data = self._json("search?q=%s&maxResultsPerPage=50" % urllib_quote_plus(searchPattern))
        for hit in (data or {}).get("hits") or []:
            try:
                kind = hit.get("type")
                item = hit.get("hit") or {}
                title = self.cleanHtmlStr(item.get("title") or "")
                if not title or not item.get("id"):
                    continue
                icon = self._img(item.get("image"))
                geo = bool((item.get("usageRights") or {}).get("isGeoBlocked"))
                if kind == "serie":
                    self._addSeries(cItem, item["id"], title, icon, self._desc([], False, item.get("description")))
                elif kind in ("program", "episode"):
                    show = self.cleanHtmlStr(item.get("seriesTitle") or "")
                    season = str(item.get("seasonNumber") or "")
                    number = str(item.get("episodeNumber") or "")
                    extra = {"s_title": show or title}
                    if show:
                        if IsMediaNamingNormalized() and season.isdigit() and number.isdigit():
                            epName = re.sub(r'^\d+\.\s*', '', title)
                            title = "%s - %s - %s" % (show, formatSxxExx(season, number), epName)
                        else:
                            title = "%s - %s" % (show, title)
                        extra.update({"season": season, "episode": number})
                    self._addProgram(cItem, item["id"], title, icon, self._desc([], geo, item.get("description")), geo, extra)
            except Exception:
                printExc()

    ###################################################
    # links
    ###################################################
    def _manifest(self, prfId):
        data = self._json("playback/manifest/program/%s?preferredCdn=akamai" % prfId, PLAYBACK_ACCEPT)
        if not isinstance(data, dict) or not data.get("playability"):
            data = self._json("playback/manifest/%s?preferredCdn=akamai" % prfId, PLAYBACK_ACCEPT)
        return data if isinstance(data, dict) else {}

    def getLinksForVideo(self, cItem):
        prfId = cItem.get("prf_id", "")
        printDBG("NRKTV.getLinksForVideo [%s]" % prfId)
        if not prfId:
            return []
        data = self._manifest(prfId)
        if data.get("playability") != "playable" or not isinstance(data.get("playable"), dict):
            reason = data.get("nonPlayable") or {}
            if (data.get("availability") or {}).get("isGeoBlocked") or "geoblock" in str(reason.get("messageType") or "").lower():
                SetIPTVPlayerLastHostError(_("This content is not available in your region."))
            elif reason.get("endUserMessage"):
                SetIPTVPlayerLastHostError("NRK: %s" % self.cleanHtmlStr(reason["endUserMessage"]))
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        playable = data["playable"]
        subTracks = []
        for sub in playable.get("subtitles") or []:
            url = (sub or {}).get("webVtt") or ""
            if self.cm.isValidUrl(url):
                subTracks.append({"title": self.cleanHtmlStr(sub.get("label") or sub.get("type") or "Norsk"), "lang": sub.get("language") or "nb",
                                  "url": url, "format": "vtt"})
        baseMeta = {"iptv_proto": "m3u8", "Referer": self.MAIN_URL, "Origin": "https://tv.nrk.no", "User-Agent": self.HEADER["User-Agent"]}
        links = []
        drm = False
        for asset in playable.get("assets") or []:
            if not isinstance(asset, dict) or not self.cm.isValidUrl(asset.get("url") or ""):
                continue
            if asset.get("encrypted") or str(asset.get("encryptionScheme") or "none").lower() != "none":
                drm = True
                continue
            if str(asset.get("format") or "").upper() != "HLS":
                continue
            # without "adap" the master lists every quality (AVC up to 1080p), not only the HEVC set of "large_h265"
            master = re.sub(r'([?&])adap=[^&]*&?', r'\1', asset["url"]).rstrip("?&")
            links.extend(self._hlsLinks(master, baseMeta, subTracks))
        if not links:
            SetIPTVPlayerLastHostError(_("Video with DRM protection.") if drm else _("No stream available"))
            return []
        sidecarTxt = cItem.get("desc", "").split("\n")[-1]
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def _hlsLinks(self, master, baseMeta, subTracks):
        hls = getDirectM3U8Playlist(strwithmeta(master, dict(baseMeta)), checkExt=False, checkContent=True, mergeAltAudio=False)
        if not hls:
            return []
        # AAC stereo next to AC-3 5.1 and AVC next to HEVC: the box plays AAC + AVC everywhere
        for bad in (UNDECODABLE_AUDIO, ("hvc1", "hev1")):
            kept = [i for i in hls if not any(c in str(i.get("codecs") or "").lower() for c in bad)]
            hls = kept or hls
        hls.sort(key=lambda x: int(x.get("bitrate") or 0), reverse=True)
        links = []
        seen = set()
        for item in hls:
            name = "%sp" % item["height"] if item.get("height") else "%d kbit/s" % (int(item.get("bitrate") or 0) // 1000)
            if name in seen:
                continue
            seen.add(name)
            meta = dict(baseMeta)
            if subTracks:
                meta["external_sub_tracks"] = subTracks
            audios = item.get("alt_audio_streams") or []
            audio = None
            for stream in audios:
                if stream.default:
                    audio = stream
                    break
            if audio is None and audios:
                audio = audios[0]
            if audio is None:
                url = strwithmeta(str(item["url"]), meta)
            else:
                # CMAF: the video playlist has no sound - muxed with the audio rendition by ffmpeg (like SVT Play)
                meta.update({"audio_url": strwithmeta(audio.absolute_uri, dict(baseMeta)), "video_url": strwithmeta(str(item["url"]), dict(baseMeta)),
                             "iptv_use_ffmpeg": True, "ff_out_container": "matroska", "iptv_format": "mkv"})
                meta.pop("iptv_proto", None)
                url = self.up.decorateUrl("merge://audio_url|video_url", meta)
            links.append({"name": name, "url": url, "need_resolve": 0})
        meta = dict(baseMeta)
        if subTracks:
            meta["external_sub_tracks"] = subTracks
        # the master itself: adaptive, and the only option for gstplayer (no merge:// support)
        links.append({"name": "HLS (adaptive)", "url": strwithmeta(master, meta), "need_resolve": 0})
        return links

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
        try:
            if cItem.get("category") == "nrk_video" and cItem.get("prf_id"):
                data = self._json("tv/catalog/programs/" + cItem["prf_id"]) or {}
                titles = (data.get("programInformation") or {}).get("titles") or {}
                more = data.get("moreInformation") or {}
                text = self.cleanHtmlStr(titles.get("subtitle") or "") or text
                if more.get("productionYear"):
                    otherInfo["year"] = str(more["productionYear"])
                if (more.get("duration") or {}).get("displayValue"):
                    otherInfo["duration"] = more["duration"]["displayValue"]
                if (more.get("category") or {}).get("displayValue"):
                    otherInfo["category"] = self.cleanHtmlStr(more["category"]["displayValue"])
                rating = (((more.get("legalAge") or {}).get("body") or {}).get("rating") or {}).get("displayValue")
                if rating:
                    otherInfo["age_limit"] = rating
                if more.get("originalTitle") and more["originalTitle"] != titles.get("title"):
                    otherInfo["original_title"] = self.cleanHtmlStr(more["originalTitle"])
                rights = more.get("usageRights") or {}
                if (rights.get("to") or {}).get("displayValue"):
                    otherInfo["remaining"] = rights["to"]["displayValue"]
                geoBlock = rights.get("geoBlock") or {}
                otherInfo["status"] = GEO_LABEL if geoBlock.get("isGeoBlocked") else _("Available worldwide")
                first = ((more.get("transmissions") or {}).get("first") or {}).get("displayValue")
                if first:
                    otherInfo["broadcast"] = first
                # [{"role": "Skuespillere", "name": ["...", ...]}, {"role": "Regissør", "name": [...]}, ...]
                for person in data.get("contributors") or []:
                    if not isinstance(person, dict):
                        continue
                    names = person.get("name") or []
                    names = [self.cleanHtmlStr(n) for n in (names if isinstance(names, list) else [names]) if n]
                    role = str(person.get("role") or "")
                    for prefix, field in (("Regi", "director"), ("Manus", "writers"), ("Skuespill", "actors"), ("Medvirk", "cast"), ("Programleder", "cast")):
                        if names and role.startswith(prefix) and field not in otherInfo:
                            otherInfo[field] = ", ".join(names[:8])
                year = otherInfo.get("year", "")
                if (more.get("category") or {}).get("id") == "film" and year:
                    # films: the NRK text stays, moviemeta adds rating / cast / plot
                    meta = getMeta("movie", more.get("originalTitle") or titles.get("title") or title, year) or {}
                    for key, value in (meta.get("info") or {}).items():
                        if value:
                            otherInfo.setdefault(key, value)
                    icon = icon or meta.get("poster", "")
            elif cItem.get("category") in ("nrk_series", "nrk_season") and cItem.get("series_id"):
                data = self._json("tv/catalog/series/" + cItem["series_id"]) or {}
                info = data.get(data.get("seriesType") or "") or {}
                text = self.cleanHtmlStr((info.get("titles") or {}).get("subtitle") or "") or text
                icon = self._img(info.get("image"), 960) or icon
                if (info.get("category") or {}).get("name"):
                    otherInfo["category"] = self.cleanHtmlStr(info["category"]["name"])
                seasons = (data.get("_links") or {}).get("seasons") or []
                if seasons:
                    otherInfo["seasons"] = str(len(seasons))
        except Exception:
            printExc()
        return [{"title": title, "text": text.replace("\n", "[/br]"), "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("nrk_"):
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
        printDBG("NRKTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            menu = [{"category": "nrk_page", "title": _("Home page"), "page_id": "frontpage", "url": self.MAIN_URL, "good_for_fav": True},
                    {"category": "nrk_categories", "title": _("Categories")}]
            self.listsTab(menu + self.searchItems(), {"name": "category"})
        elif category == "nrk_categories":
            self.listCategories(self.currItem)
        elif category == "nrk_page":
            self.listPage(self.currItem)
        elif category == "nrk_section":
            self.listSection(self.currItem)
        elif category == "nrk_series":
            self.listSeries(self.currItem)
        elif category == "nrk_season":
            self.listSeason(self.currItem)
        elif category in ("search", "search_next_page"):
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, NRKTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("nrktv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("nrk_video", "nrk_series", "nrk_season")
