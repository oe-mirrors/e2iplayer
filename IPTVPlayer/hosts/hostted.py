# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - rewrite for the current ted.com (Next.js "zenith" frontend):
#   talk lists (newest / most viewed / topics / subtitle languages / search) come from the
#   site's Algolia proxy (POST /api/search, sort replicas "newest" / "popular" / "relevance"),
#   playlists, playlist talks and the talk data (HLS master, MP4 fallback, subtitle languages,
#   speaker) from the public GraphQL API (graphql.ted.com). The HLS masters carry separate
#   audio renditions, so the variants are offered as merge:// audio+video links (plus the master
#   itself for gstplayer); all subtitle languages go in as external WebVTT tracks.
#   + watched flag / downloaded flag / sidecar / INFO (speaker, description) / favourites.
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, decorateUrl
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.ted.com/"


GRAPHQL_URL = "https://graphql.ted.com/"
SEARCH_URL = "https://www.ted.com/api/search"
PAGE_SIZE = 24
LOCAL_PAGE_SIZE = 100
TALK_RE = re.compile(r"/talks/([A-Za-z0-9_\-]+)")

VIDEO_NODE_FIELDS = "slug title duration presenterDisplayName canonicalUrl recordedOn primaryImageSet { url aspectRatioName }"
Q_PLAYLISTS = ("query($first: Int, $after: String) { playlists(first: $first, after: $after) { pageInfo { endCursor hasNextPage } "
               "nodes { id slug title description author primaryImageSet { url aspectRatioName } videos { totalCount } } } }")
Q_PLAYLIST = ("query($id: ID!, $first: Int, $after: String) { playlist(id: $id) { id title videos(first: $first, after: $after) { "
              "pageInfo { endCursor hasNextPage } nodes { %s } } } }" % VIDEO_NODE_FIELDS)
Q_VIDEO = ("query($slug: String!) { video(slug: $slug) { id slug title description presenterDisplayName duration recordedOn publishedAt "
           "videoContext viewedCount canonicalUrl hlsUrl primaryImageSet { url aspectRatioName } topics { nodes { name } } "
           "speakers { nodes { firstname middlename lastname description } } "
           "videoPlayerData { resources { h264 { file bitrate } hls { stream metadata } } external { service code } "
           "languages { languageCode languageName } } } }")


class TED(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "slug", "speaker", "talk_title", "icon", "desc")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "ted.com", "cookie": "ted.com.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://pa.tedcdn.com/apple-touch-icon.png"
        self.facetCache = {}
        self.MENU = [{"category": "list_talks", "title": _("Latest"), "index": "newest"},
                     {"category": "list_talks", "title": _("Most viewed"), "index": "popular"},
                     {"category": "list_facets", "title": _("Topics"), "facet": "tags"},
                     {"category": "list_facets", "title": _("Subtitle languages"), "facet": "subtitle_languages"},
                     {"category": "list_playlists", "title": _("Playlists")}] + self.searchItems()

        self.watchedHelper = IPTVWatchedHelper("ted")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            url = str(cItem.get("url", "") or "").strip()
            if cItem.get("type", "") in ("video", "audio"):
                return "video:%s" % url if url else ""
            if cItem.get("category", "") == "list_playlist" and cItem.get("playlist_id"):
                return "folder:playlist:%s" % cItem["playlist_id"]
            return ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # http
    ###################################################
    def _postJson(self, url, payload, referer=None):
        header = dict(self.HEADER)
        header.update({"Accept": "application/json", "Content-Type": "application/json",
                       "Origin": "https://www.ted.com", "Referer": referer or self.MAIN_URL})
        params = dict(self.defaultParams)
        params.update({"header": header, "raw_post_data": True})
        sts, data = self.cm.getPage(url, params, json_dumps(payload))
        if not sts:
            printDBG("TED._postJson failed: %s" % url)
            return {}
        try:
            data = json_loads(data)
        except Exception:
            printExc("TED._postJson JSON error: %s" % url)
            return {}
        return data if isinstance(data, dict) else {}

    def _graphql(self, query, variables):
        data = self._postJson(GRAPHQL_URL, {"query": query, "variables": variables})
        if data.get("errors"):
            printDBG("TED._graphql errors: %s" % data["errors"])
        return data.get("data") or {}

    def _search(self, index, params):
        req = {"indexName": index, "params": params}
        data = self._postJson(SEARCH_URL, [req], self.getFullUrl("/talks"))
        try:
            return data["results"][0] or {}
        except Exception:
            printDBG("TED._search: no results for %s" % params)
        return {}

    ###################################################
    # helpers
    ###################################################
    def _icon(self, url, width=480):
        # pi.tedcdn.com/r/<host>/<path> resizes - the originals are 2880px / ~400 KB
        url = (url or "").strip()
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("https://pi.tedcdn.com/r/"):
            url = "https://pi.tedcdn.com/r/" + re.sub(r"^https?://", "", url)
        return "%s%sw=%d" % (url, "&" if "?" in url else "?", width)

    def _pickImage(self, imageSet):
        images = dict((img.get("aspectRatioName", ""), img.get("url", "")) for img in (imageSet or []) if isinstance(img, dict))
        for ratio in ("16x9", "2x1", "400x209", "4x3", "1x1"):
            if images.get(ratio):
                return self._icon(images[ratio])
        return ""

    def _duration(self, seconds):
        try:
            seconds = int(float(seconds))
        except Exception:
            return ""
        if seconds <= 0:
            return ""
        if seconds >= 3600:
            return "%d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)
        return "%d:%02d" % (seconds // 60, seconds % 60)

    def _talkTitle(self, speaker, title):
        # "Speaker - Title" with name normalisation on, the site's title otherwise
        speaker = (speaker or "").strip()
        title = (title or "").strip()
        if IsMediaNamingNormalized() and speaker and title and speaker.lower() not in title.lower():
            return "%s - %s" % (speaker, title)
        return title or speaker

    def _addTalk(self, cItem, slug, title, speaker, duration, icon, extraDesc=""):
        if not slug or not title:
            return False
        url = self.getFullUrl("/talks/%s" % slug)
        desc = []
        if speaker:
            desc.append(speaker)
        dur = self._duration(duration)
        if dur:
            desc.append(dur)
        if extraDesc:
            desc.append(extraDesc)
        params = {"name": "category", "good_for_fav": True, "category": "ted_talk", "url": url, "slug": slug,
                  "title": self._talkTitle(speaker, title), "talk_title": title, "speaker": speaker,
                  "icon": icon, "desc": " | ".join(desc)}
        self.addVideo(params)
        return True

    def _addNextPage(self, cItem, extra):
        params = dict(cItem)
        params.update({"good_for_fav": False, "title": _("Next page")})
        params.update(extra)
        self.addDir(params)

    ###################################################
    # lists
    ###################################################
    def listTalks(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        index = cItem.get("index", "newest")
        params = {"query": cItem.get("search_pattern", ""), "hitsPerPage": PAGE_SIZE, "page": page - 1}  # Algolia pages count from 0
        if cItem.get("facet") and cItem.get("facet_value"):
            params["facetFilters"] = [["%s:%s" % (cItem["facet"], cItem["facet_value"])]]
        printDBG("TED.listTalks index[%s] params[%s]" % (index, params))
        data = self._search(index, params)
        cnt = 0
        for hit in data.get("hits") or []:
            icon = ""
            for photo in hit.get("photos") or []:
                sizes = dict((size.get("talkstar_aspect_ratio_id"), size.get("url", "")) for size in (photo.get("photo_sizes") or []))
                # 2 = 16x9 (embed), 36 = 2x1 (1350x675), 3 = 4x3 (stage shot)
                icon = sizes.get(2) or sizes.get(36) or sizes.get(3) or ""
                if icon:
                    break
            if self._addTalk(cItem, hit.get("slug", ""), self.cleanHtmlStr(hit.get("title", "")),
                             self.cleanHtmlStr(hit.get("speakers", "")), hit.get("duration"), self._icon(icon)):
                cnt += 1
        try:
            nbPages = int(data.get("nbPages", 0))
        except Exception:
            nbPages = 0
        # the list is not url based: a constant template only lets "Jump" through
        addPagingItems(self, cItem, page, cnt > 0 and page < nbPages, nbPages, self.MAIN_URL + "talks")

    def listFacets(self, cItem):
        facet = cItem.get("facet", "tags")
        values = self.facetCache.get(facet)
        if not values:
            data = self._search("newest", {"query": "", "hitsPerPage": 0, "facets": [facet], "maxValuesPerFacet": 500})
            values = (data.get("facets") or {}).get(facet) or {}
            if values:
                self.facetCache[facet] = values
        # ~400 topics / ~120 languages: shown LOCAL_PAGE_SIZE at a time
        keys = [v for v in sorted(values.keys(), key=lambda x: x.strip().lower()) if v.strip()]
        page = max(1, int(cItem.get("page", 1) or 1))
        lastPage = max(1, (len(keys) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE)
        page = min(page, lastPage)
        for value in keys[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]:
            title = value.strip()
            title = title[:1].upper() + title[1:]
            if facet == "subtitle_languages":
                title = title.title()
            params = stripPagerKeys(dict(cItem))
            params.update({"good_for_fav": True, "category": "list_talks", "index": "newest", "facet_value": value,
                           "title": title, "desc": _("%s talks") % values[value], "page": 1})
            self.addDir(params)
        if lastPage > 1:
            # the url template only serves "Jump" - the list is cut by cItem['page']
            addPagingItems(self, cItem, page, page < lastPage, lastPage, self.MAIN_URL + "topics")

    def listPlaylists(self, cItem):
        data = self._graphql(Q_PLAYLISTS, {"first": PAGE_SIZE, "after": cItem.get("after") or None}).get("playlists") or {}
        cnt = 0
        for node in data.get("nodes") or []:
            pid = node.get("id", "")
            title = self.cleanHtmlStr(node.get("title", ""))
            if not pid or not title:
                continue
            desc = []
            total = (node.get("videos") or {}).get("totalCount")
            if total:
                desc.append(_("%s talks") % total)
            if node.get("author"):
                desc.append(node["author"])
            text = self.cleanHtmlStr(node.get("description", ""))
            params = {"name": "category", "good_for_fav": True, "category": "list_playlist", "playlist_id": pid,
                      "url": self.getFullUrl("/playlists/%s/%s" % (pid, node.get("slug", ""))), "title": title,
                      "icon": self._pickImage(node.get("primaryImageSet")),
                      "desc": " | ".join(desc) + ("[/br]" + text if text else "")}
            self.addDir(params)
            cnt += 1
        pageInfo = data.get("pageInfo") or {}
        if cnt and pageInfo.get("hasNextPage") and pageInfo.get("endCursor"):
            self._addNextPage(cItem, {"after": pageInfo["endCursor"]})

    def listPlaylist(self, cItem):
        playlist = self._graphql(Q_PLAYLIST, {"id": cItem.get("playlist_id", ""), "first": PAGE_SIZE, "after": cItem.get("after") or None}).get("playlist") or {}
        data = playlist.get("videos") or {}
        cnt = 0
        for node in data.get("nodes") or []:
            year = (node.get("recordedOn") or "")[:4]
            if self._addTalk(cItem, node.get("slug", ""), self.cleanHtmlStr(node.get("title", "")),
                             self.cleanHtmlStr(node.get("presenterDisplayName", "")), node.get("duration"),
                             self._pickImage(node.get("primaryImageSet")), year):
                cnt += 1
        pageInfo = data.get("pageInfo") or {}
        if cnt and pageInfo.get("hasNextPage") and pageInfo.get("endCursor"):
            self._addNextPage(cItem, {"after": pageInfo["endCursor"]})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("TED.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_talks", "index": "relevance", "search_pattern": searchPattern, "page": 1})
        self.listTalks(cItem)

    ###################################################
    # talk data
    ###################################################
    def _slugFromItem(self, cItem):
        slug = cItem.get("slug", "")
        if not slug:
            slug = self.cm.ph.getSearchGroups(cItem.get("url", ""), TALK_RE.pattern)[0]
        return slug

    def _getVideo(self, cItem):
        slug = self._slugFromItem(cItem)
        if not slug:
            return {}
        return self._graphql(Q_VIDEO, {"slug": slug}).get("video") or {}

    def _getSubtitles(self, video, hlsUrl):
        # metadata.json next to the HLS master lists one full.vtt per language; its URLs keep the
        # intro_master_id, so the cues are shifted by the TED intro that the HLS stream starts with
        subs = []
        metaUrl = ""
        if hlsUrl:
            metaUrl = hlsUrl.replace("/manifest.m3u8", "/metadata.json")
        if not metaUrl:
            metaUrl = ((video.get("videoPlayerData") or {}).get("resources") or {}).get("hls", {}).get("metadata", "") or ""
        if metaUrl and "/metadata.json" in metaUrl:
            sts, data = self.cm.getPage(metaUrl, self.defaultParams)
            if sts:
                try:
                    for sub in json_loads(data).get("subtitles") or []:
                        if sub.get("webvtt"):
                            subs.append({"title": sub.get("name") or sub.get("code", ""), "lang": sub.get("code", ""), "url": sub["webvtt"], "format": "vtt"})
                except Exception:
                    printExc()
        if not subs and hlsUrl:
            base = hlsUrl.split("?", 1)
            query = ("?" + base[1]) if len(base) > 1 else ""
            base = base[0].rsplit("/", 1)[0]
            for lang in (video.get("videoPlayerData") or {}).get("languages") or []:
                code = lang.get("languageCode", "")
                if code:
                    subs.append({"title": lang.get("languageName") or code, "lang": code, "url": "%s/subtitles/%s/full.vtt%s" % (base, code, query), "format": "vtt"})
        # own language first, then English, the rest as TED lists them
        userLang = GetDefaultLang()
        subs.sort(key=lambda s: 0 if s["lang"].split("-")[0] == userLang else (1 if s["lang"] == "en" else 2))
        return subs

    def _noIntroSubs(self, subs):
        # the MP4 fallback has no intro, so its cues must not be shifted
        ret = []
        for sub in subs:
            sub = dict(sub)
            sub["url"] = re.sub(r"[?&]intro_master_id=\d+", "", sub["url"]).replace("full.vtt&", "full.vtt?")
            ret.append(sub)
        return ret

    def _pickAudio(self, audioStreams):
        byName = dict(((a.name or "").lower(), a) for a in audioStreams)
        if "high" in byName:
            return byName["high"]
        for audio in audioStreams:
            if audio.default:
                return audio
        return audioStreams[0] if audioStreams else None

    def _hlsLinks(self, hlsUrl, subs):
        meta = {"iptv_proto": "m3u8", "User-Agent": self.HEADER.get("User-Agent", "")}
        best = {}
        for item in getDirectM3U8Playlist(strwithmeta(hlsUrl, meta), checkExt=False, checkContent=True, mergeAltAudio=False):
            height = int(item.get("height", 0) or 0)
            try:
                bitrate = int(item.get("bitrate", 0) or 0)
            except Exception:
                bitrate = 0
            if height not in best or bitrate > best[height][0]:
                best[height] = (bitrate, item)
        links = []
        for height in sorted(best.keys(), reverse=True):
            item = best[height][1]
            videoMeta = dict(strwithmeta(item["url"]).meta)
            videoMeta.pop("external_sub_tracks", None)
            videoUrl = strwithmeta(item["url"], videoMeta)
            name = "HLS %dp" % height if height else "HLS"
            audio = self._pickAudio(item.get("alt_audio_streams") or [])
            if audio is not None and audio.absolute_uri:
                # TED's video renditions carry no audio track - mux the audio rendition in with ffmpeg
                mergeMeta = dict(videoMeta)
                mergeMeta.update({"audio_url": strwithmeta(audio.absolute_uri, videoMeta), "video_url": videoUrl,
                                  "iptv_use_ffmpeg": True, "ff_out_container": "matroska", "iptv_format": "mkv"})
                if subs:
                    mergeMeta["external_sub_tracks"] = subs
                links.append({"name": name, "url": decorateUrl("merge://audio_url|video_url", mergeMeta), "need_resolve": 0})
            else:
                if subs:
                    videoMeta["external_sub_tracks"] = subs
                links.append({"name": name, "url": strwithmeta(item["url"], videoMeta), "need_resolve": 0})
        if links:
            # the master itself: the player picks video + audio (gstplayer cannot play merge://)
            masterMeta = dict(meta)
            if subs:
                masterMeta["external_sub_tracks"] = subs
            links.append({"name": "HLS auto (master)", "url": strwithmeta(hlsUrl, masterMeta), "need_resolve": 0})
        return links

    def getLinksForVideo(self, cItem):
        printDBG("TED.getLinksForVideo [%s]" % cItem.get("url", ""))
        video = self._getVideo(cItem)
        if not video:
            return []
        playerData = video.get("videoPlayerData") or {}
        resources = playerData.get("resources") or {}
        hlsUrl = video.get("hlsUrl") or ""
        if not hlsUrl:
            hlsUrl = re.sub(r"[?&]preview(?:=[^&]*)?$", "", (resources.get("hls") or {}).get("stream", "") or "")
        subs = self._getSubtitles(video, hlsUrl)
        urltab = []
        if hlsUrl:
            urltab.extend(self._hlsLinks(hlsUrl, subs))
        mp4Subs = self._noIntroSubs(subs)
        h264 = sorted([x for x in (resources.get("h264") or []) if x.get("file")], key=lambda x: -int(x.get("bitrate") or 0))
        for item in h264:
            meta = {"User-Agent": self.HEADER.get("User-Agent", "")}
            if mp4Subs:
                meta["external_sub_tracks"] = mp4Subs
            urltab.append({"name": "MP4 %sk" % item.get("bitrate", ""), "url": strwithmeta(item["file"], meta), "need_resolve": 0})
        external = playerData.get("external") or {}
        if not urltab and (external.get("service") or "").lower() == "youtube" and external.get("code"):
            urltab.append({"name": "YouTube", "url": "https://www.youtube.com/watch?v=%s" % external["code"], "need_resolve": 1})
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self.cleanHtmlStr(video.get("description", ""))))

    def getVideoLinks(self, videoUrl):
        printDBG("TED.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("TED.getArticleContent [%s]" % cItem.get("url", ""))
        video = self._getVideo(cItem)
        if not video:
            return [{"title": cItem.get("title", ""), "text": cItem.get("desc", ""),
                     "images": [{"title": "", "url": cItem["icon"]}] if cItem.get("icon") else [], "other_info": {}}]
        otherInfo = {}
        speakers = []
        speakerText = []
        for sp in (video.get("speakers") or {}).get("nodes") or []:
            name = " ".join(x for x in (sp.get("firstname"), sp.get("middlename"), sp.get("lastname")) if x).strip()
            if not name:
                continue
            speakers.append(name)
            if sp.get("description"):
                speakerText.append("%s: %s" % (name, self.cleanHtmlStr(sp["description"])))
        if speakers:
            otherInfo["cast"] = ", ".join(speakers)
        elif video.get("presenterDisplayName"):
            otherInfo["cast"] = video["presenterDisplayName"]
        dur = self._duration(video.get("duration"))
        if dur:
            otherInfo["duration"] = dur
        if video.get("recordedOn"):
            otherInfo["year"] = video["recordedOn"][:4]
            otherInfo["released"] = video["recordedOn"]
        if video.get("videoContext"):
            otherInfo["source"] = self.cleanHtmlStr(video["videoContext"])
        topics = [t.get("name", "") for t in (video.get("topics") or {}).get("nodes") or [] if t.get("name")]
        if topics:
            otherInfo["genres"] = ", ".join(topics)
        if video.get("viewedCount"):
            otherInfo["views"] = str(video["viewedCount"])
        langs = len((video.get("videoPlayerData") or {}).get("languages") or [])
        if langs:
            otherInfo["subtitles"] = str(langs)
        text = self.cleanHtmlStr(video.get("description", "")) or cItem.get("desc", "")
        if speakerText:
            text += "[/br][/br]" + "[/br]".join(speakerText)
        icon = self._pickImage(video.get("primaryImageSet")) or cItem.get("icon", "")
        title = self._talkTitle(video.get("presenterDisplayName", ""), self.cleanHtmlStr(video.get("title", ""))) or cItem.get("title", "")
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") == "ted_talk":
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
        printDBG("TED.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_talks":
            self.listTalks(self.currItem)
        elif category == "list_facets":
            self.listFacets(self.currItem)
        elif category == "list_playlists":
            self.listPlaylists(self.currItem)
        elif category == "list_playlist":
            self.listPlaylist(self.currItem)
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
        CHostBase.__init__(self, TED(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("ted")

    def withArticleContent(self, cItem):
        return cItem.get("category") == "ted_talk"
