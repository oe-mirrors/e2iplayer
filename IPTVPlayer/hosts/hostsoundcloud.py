# -*- coding: utf-8 -*-
LAST_MODIFIED = "19.11.2026"
# 19.11.2026 - new host for soundcloud.com: search (tracks, playlists, artists), trending by genre, featured playlists
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCacheSubDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
try:
    from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
except ImportError:
    # E2iPlayer without tools/iptvpaging.py: only "Next page"
    addPagingItems = isJumpItem = jumpTarget = None
###################################################
# FOREIGN import
###################################################
import os
import re
###################################################

API_URL = "https://api-v2.soundcloud.com/"
# client_id of SoundCloud's web player for api-v2, kept for the session (getClientId)
CLIENT_ID = []
SEARCH_PAGE_SIZE = 30
# the search api stops at offset 300
SEARCH_MAX_RESULTS = 300
PLAYLIST_PAGE_SIZE = 50
GENRES_SELECTION = "soundcloud:selections:trending-by-genre-playlists"
# "Trending by genre" of soundcloud.com/discover when the api does not list it (SoundCloud's own genre names)
GENRES = (("All Genres", "all-genres"), ("Alternative Hip Hop", "alternative-hip-hop"), ("Alternative Rock", "alternative-rock"),
          ("Ambient", "ambient"), ("Dancehall", "dancehall"), ("Downtempo", "downtempo"), ("Dubstep", "dubstep"),
          ("Electronic", "electronic"), ("Folk", "folk"), ("Hardcore", "hardcore"), ("Hip Hop", "hip-hop"), ("House", "house"),
          ("Indie", "indie"), ("Latin", "latin"), ("Metal", "metal"), ("Pop", "pop"), ("R&B", "r-n-b"), ("Reggae", "reggae"),
          ("Rock", "rock"), ("Trap", "trap"))


def GetConfigList():
    return []


def gettytul():
    return "https://soundcloud.com/"


def trendingUrn(slug):
    return "soundcloud:system-playlists:trending-by-genre:%s" % slug


class SoundCloud(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "title", "url", "icon", "desc", "pl_api", "user_id", "sel_urn")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "soundcloud", "cookie": "soundcloud.cookie"})
        self.MAIN_URL = gettytul()
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER}
        self.MENU = [
            {"category": "sc_playlist", "title": _("Trending"), "url": self.MAIN_URL + "discover/sets/trending-by-genre:all-genres",
             "pl_api": API_URL + "system-playlists/" + trendingUrn("all-genres")},
            {"category": "sc_selection", "title": _("Genres"), "sel_urn": GENRES_SELECTION},
            {"category": "sc_selections", "title": _("Featured")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("soundcloud")
        self.wfInitFolderCache()

    ###################################################
    # api-v2 with the web player's client_id
    ###################################################
    def getClientId(self, force=False):
        # no fixed key: SoundCloud changes it now and then. Read like yt-dlp: client_id:"..." in the
        # a-v2.sndcdn.com/assets/*.js scripts of soundcloud.com (the last one has it); kept for the session and in
        # the cache dir, force = the api rejected it (401/403): a newer one in the file (written by
        # urlparser.parserSOUNDCLOUDCOM, which keeps the same code) or read it again. Never logged.
        if not force and CLIENT_ID:
            return CLIENT_ID[0]
        rejected = CLIENT_ID[0] if CLIENT_ID else ""
        del CLIENT_ID[:]
        cacheFile = ""
        try:
            cacheFile = GetCacheSubDir("soundcloud", "client_id.txt")
            with open(cacheFile) as f:
                clientId = f.read().strip()
            if re.match(r"^[0-9A-Za-z]{32}$", clientId) and clientId != rejected:
                CLIENT_ID[:] = [clientId]
                return clientId
        except Exception:
            pass
        sts, data = self.cm.getPage(self.MAIN_URL, self.defaultParams)
        clientId = ""
        if sts:
            for url in reversed(re.findall(r'<script[^>]+src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', data)):
                sts, js = self.cm.getPage(url, self.defaultParams)
                clientId = self.cm.ph.getSearchGroups(js, r'client_id\s*:\s*"([0-9A-Za-z]{32})"')[0] if sts else ""
                if clientId:
                    break
        printDBG("SoundCloud.getClientId: %s" % ("read" if clientId else "not found"))
        if clientId:
            CLIENT_ID[:] = [clientId]
        if clientId and cacheFile:
            # written to a temporary file and renamed: the parser may read it at the same time
            try:
                with open(cacheFile + ".tmp", "w") as f:
                    f.write(clientId)
                getattr(os, "replace", os.rename)(cacheFile + ".tmp", cacheFile)
            except Exception:
                printExc()
        return clientId

    def apiGet(self, url):
        # json of an api-v2 url (next_href included), None when it fails; a rejected client_id is read again once
        url = re.sub(r"([?&])client_id=[^&]*&?", r"\1", url).rstrip("?&")
        params = dict(self.defaultParams)
        params.update({"with_metadata": True, "ignore_http_code_ranges": [(400, 499)]})
        for force in (False, True):
            clientId = self.getClientId(force)
            if not clientId:
                break
            sts, data = self.cm.getPage("%s%sclient_id=%s" % (url, "&" if "?" in url else "?", clientId), params)
            if not sts:
                return None
            code = getattr(data, "meta", {}).get("status_code", 200)
            if code in (401, 403) and not force:
                continue
            if code != 200:
                # a new client_id rejected as well: the item itself is refused, not the key
                printDBG("SoundCloud.apiGet HTTP %s [%s]" % (code, url))
                return None
            try:
                return json_loads(data)
            except Exception:
                printExc()
                return None
        SetIPTVPlayerLastHostError(_("The site's web player key could not be read - please try again later."))
        return None

    def hydrate(self, tracks):
        # playlists carry the full data of the first tracks only, the others as {"id": ...}
        need = [str(t["id"]) for t in tracks if isinstance(t, dict) and t.get("id") and not t.get("media")]
        full = {}
        for i in range(0, len(need), 50):
            data = self.apiGet("%stracks?ids=%s" % (API_URL, ",".join(need[i:i + 50])))
            for t in data if isinstance(data, list) else []:
                if isinstance(t, dict):
                    full[t.get("id")] = t
        return [full.get(t.get("id"), t) if isinstance(t, dict) and not t.get("media") else t for t in tracks]

    ###################################################
    # watched flag and favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or not cItem.get("url"):
                return ""
            category = cItem.get("category", "")
            if category == "sc_track":
                return "video:%s" % cItem["url"]
            # a playlist of a user keeps its tracks, the trending ones change every day
            if category == "sc_playlist" and "/playlists/" in cItem.get("pl_api", ""):
                return "folder:%s" % cItem["url"]
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        return self.getFavouriteFieldsData(cItem)

    ###################################################
    # rows
    ###################################################
    @staticmethod
    def bigImage(url):
        # artworks-...-large.jpg (100x100) -> t500x500
        return (url or "").replace("-large.", "-t500x500.")

    @staticmethod
    def formatDuration(ms):
        try:
            secs = int(ms or 0) // 1000
        except (TypeError, ValueError):
            return ""
        if not secs:
            return ""
        if secs >= 3600:
            return "%d:%02d:%02d" % (secs // 3600, secs % 3600 // 60, secs % 60)
        return "%d:%02d" % (secs // 60, secs % 60)

    @staticmethod
    def shortText(text, limit=300):
        text = re.sub(r"\s+", " ", text or "").strip()
        return text[:limit] + "..." if len(text) > limit else text

    def addTrack(self, t):
        url = t.get("permalink_url", "")
        title = (t.get("title") or "").strip()
        transcodings = (t.get("media") or {}).get("transcodings") or []
        # BLOCK: not in the user's country, SNIP: only a 30 second preview (SoundCloud Go+); a track with only
        # DRM-encrypted streams ("cbc-/ctr-encrypted-hls", major labels) cannot be played either
        playable = [x for x in transcodings if not x.get("snipped") and "encrypted" not in str((x.get("format") or {}).get("protocol", ""))]
        if not url or not title or t.get("policy") in ("BLOCK", "SNIP") or not playable:
            return False
        user = ((t.get("user") or {}).get("username") or "").strip()
        if IsMediaNamingNormalized() and user and not title.lower().startswith(user.lower()):
            title = "%s - %s" % (user, title)
        info = [x for x in (user, self.formatDuration(t.get("full_duration") or t.get("duration")), t.get("genre") or "") if x]
        if t.get("playback_count"):
            info.append("%s: %s" % (_("Views"), t["playback_count"]))
        desc = " | ".join(info)
        text = self.shortText(t.get("description"))
        if text:
            desc += "[/br]" + text
        icon = self.bigImage(t.get("artwork_url") or (t.get("user") or {}).get("avatar_url"))
        self.addAudio({"name": "category", "category": "sc_track", "good_for_fav": True, "title": title, "url": url, "icon": icon, "desc": desc})
        return True

    def addPlaylist(self, p):
        url = p.get("permalink_url", "")
        title = (p.get("title") or "").strip()
        if not url or not title:
            return
        if p.get("kind") == "system-playlist" and p.get("urn"):
            plApi = API_URL + "system-playlists/" + p["urn"]
        elif p.get("id"):
            plApi = "%splaylists/%s" % (API_URL, p["id"])
        else:
            return
        user = ((p.get("user") or {}).get("username") or "").strip()
        info = [x for x in (p.get("short_description") or user, self.formatDuration(p.get("duration"))) if x]
        count = p.get("track_count") or len(p.get("tracks") or [])
        if count:
            info.append("%s: %s" % (_("Titles"), count))
        desc = " | ".join(info)
        text = self.shortText(p.get("description"))
        if text:
            desc += "[/br]" + text
        icon = self.bigImage(p.get("artwork_url") or p.get("calculated_artwork_url") or (p.get("user") or {}).get("avatar_url"))
        self.addDir({"name": "category", "category": "sc_playlist", "good_for_fav": True, "title": title, "url": url, "pl_api": plApi,
                     "icon": icon, "desc": desc})

    def addUser(self, u):
        url = u.get("permalink_url", "")
        title = (u.get("username") or "").strip()
        if not url or not title or not u.get("id"):
            return
        info = [x for x in (u.get("full_name"), u.get("city"), u.get("country_code")) if x]
        if u.get("track_count"):
            info.append("%s: %s" % (_("Titles"), u["track_count"]))
        desc = " | ".join(info)
        text = self.shortText(u.get("description"))
        if text:
            desc += "[/br]" + text
        self.addDir({"name": "category", "category": "sc_user", "good_for_fav": True, "title": title, "url": url, "user_id": u["id"],
                     "icon": self.bigImage(u.get("avatar_url")), "desc": desc})

    def addPaging(self, cItem, page, hasNext, lastPage=0, pageUrlTpl="", nextParams=None):
        if addPagingItems is not None:
            addPagingItems(self, cItem, page, hasNext, lastPage, pageUrlTpl, nextParams)
        elif hasNext:
            params = dict(cItem)
            params.update({"good_for_fav": False, "title": _("Next page"), "page": page + 1})
            params.update(nextParams or {})
            self.addDir(params)

    ###################################################
    # lists
    ###################################################
    def listSelections(self, cItem):
        # soundcloud.com/discover: "Artists to watch out for", "Curated by SoundCloud" ...
        data = self.apiGet(API_URL + "mixed-selections?limit=50")
        for sel in (data or {}).get("collection") or []:
            if not isinstance(sel, dict) or not sel.get("urn") or sel["urn"] == GENRES_SELECTION:
                continue
            items = (sel.get("items") or {}).get("collection") or []
            if not items or not sel.get("title"):
                continue
            icon = self.bigImage(items[0].get("artwork_url") or items[0].get("calculated_artwork_url"))
            self.addDir({"name": "category", "category": "sc_selection", "good_for_fav": True, "title": sel["title"],
                         "sel_urn": sel["urn"], "icon": icon, "desc": sel.get("description") or ""})

    def listSelection(self, cItem):
        urn = cItem.get("sel_urn", "")
        data = self.apiGet(API_URL + "mixed-selections?limit=50")
        for sel in (data or {}).get("collection") or []:
            if isinstance(sel, dict) and sel.get("urn") == urn:
                for p in (sel.get("items") or {}).get("collection") or []:
                    if isinstance(p, dict):
                        self.addPlaylist(p)
                break
        if not self.currList and urn == GENRES_SELECTION:
            for title, slug in GENRES:
                self.addDir({"name": "category", "category": "sc_playlist", "good_for_fav": True, "title": title,
                             "url": self.MAIN_URL + "discover/sets/trending-by-genre:" + slug,
                             "pl_api": API_URL + "system-playlists/" + trendingUrn(slug)})

    def listPlaylist(self, cItem):
        # all track ids in one answer: local pages of PLAYLIST_PAGE_SIZE, only the listed page is loaded in full
        page = int(cItem.get("page", 1) or 1)
        data = self.apiGet(cItem.get("pl_api", ""))
        tracks = [t for t in (data or {}).get("tracks") or [] if isinstance(t, dict)] if isinstance(data, dict) else []
        if not tracks:
            return
        lastPage = (len(tracks) + PLAYLIST_PAGE_SIZE - 1) // PLAYLIST_PAGE_SIZE
        for t in self.hydrate(tracks[(page - 1) * PLAYLIST_PAGE_SIZE:page * PLAYLIST_PAGE_SIZE]):
            self.addTrack(t)
        self.addPaging(cItem, page, page < lastPage, lastPage)

    def listUser(self, cItem):
        # the user's tracks, newest first; the api pages with a cursor (next_href), so only "Next page"
        page = int(cItem.get("page", 1) or 1)
        url = cItem.get("next_url", "") if page > 1 else ""
        data = self.apiGet(url or "%susers/%s/tracks?limit=%d" % (API_URL, cItem.get("user_id", ""), SEARCH_PAGE_SIZE))
        if not isinstance(data, dict):
            return
        for t in data.get("collection") or []:
            if isinstance(t, dict):
                self.addTrack(t)
        # without the client_id (apiGet adds the current one): the row url lands in favourites and the log
        nextUrl = re.sub(r"([?&])client_id=[^&]*&?", r"\1", data.get("next_href") or "").rstrip("?&")
        self.addPaging(cItem, page, bool(nextUrl and data.get("collection")), 0, "", {"next_url": nextUrl})

    def listSearch(self, cItem):
        searchType = cItem.get("search_type", "tracks")
        pattern = cItem.get("q", "")
        page = int(cItem.get("page", 1) or 1)
        offset = (page - 1) * SEARCH_PAGE_SIZE
        data = self.apiGet("%ssearch/%s?q=%s&limit=%d&offset=%d" % (API_URL, searchType, urllib_quote_plus(pattern), SEARCH_PAGE_SIZE, offset))
        if not isinstance(data, dict):
            return
        for item in data.get("collection") or []:
            if not isinstance(item, dict):
                continue
            if searchType == "tracks":
                self.addTrack(item)
            elif searchType == "playlists":
                self.addPlaylist(item)
            else:
                self.addUser(item)
        total = min(int(data.get("total_results") or 0), SEARCH_MAX_RESULTS)
        lastPage = (total + SEARCH_PAGE_SIZE - 1) // SEARCH_PAGE_SIZE
        if not self.currList and page == 1:
            SetIPTVPlayerLastHostError(_("No results found for: %s") % pattern)
        # the web search of the same query as the folder url ("Jump" builds the url of the page from it)
        urlTpl = "%ssearch/%s?q=%s&page={page}" % (self.MAIN_URL, "sounds" if searchType == "tracks" else searchType, urllib_quote_plus(pattern))
        self.addPaging(cItem, page, bool(data.get("next_href")) and page < lastPage, lastPage, urlTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SoundCloud.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        self.listSearch({"name": "category", "category": "sc_search", "q": searchPattern, "search_type": searchType or "tracks"})

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("SoundCloud.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        if not self.cm.isValidUrl(url):
            return []
        # the stream (signed, expires after a few hours) is read by urlparser.parserSOUNDCLOUDCOM when the link is opened
        links = [{"name": "SoundCloud", "url": strwithmeta(url), "need_resolve": 1}]
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    ###################################################
    # INFO key
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("SoundCloud.getArticleContent [%s]" % cItem.get("url", ""))
        if cItem.get("pl_api"):
            apiUrl = cItem["pl_api"]
        elif cItem.get("user_id"):
            apiUrl = "%susers/%s" % (API_URL, cItem["user_id"])
        elif cItem.get("url"):
            apiUrl = API_URL + "resolve?url=" + urllib_quote(cItem["url"], safe="")
        else:
            apiUrl = ""
        data = self.apiGet(apiUrl) if apiUrl else None
        if not isinstance(data, dict):
            return [{"title": cItem.get("title", ""), "text": cItem.get("desc", ""), "images": [{"title": "", "url": cItem.get("icon", "")}], "other_info": {}}]
        user = data.get("user") or {}
        info = {}
        if data.get("kind") == "user":
            title = data.get("username", "")
            icon = self.bigImage(data.get("avatar_url"))
            if data.get("country_code"):
                info["country"] = data["country_code"]
        else:
            title = data.get("title", "")
            icon = self.bigImage(data.get("artwork_url") or data.get("calculated_artwork_url") or user.get("avatar_url"))
            if user.get("username"):
                info["creator"] = user["username"]
            if data.get("genre"):
                info["genre"] = data["genre"]
            duration = self.formatDuration(data.get("full_duration") or data.get("duration"))
            if duration:
                info["duration"] = duration
            if data.get("playback_count"):
                info["views"] = str(data["playback_count"])
            released = (data.get("release_date") or data.get("display_date") or data.get("created_at") or "")[:10]
            if released:
                info["released"] = released
        text = (data.get("description") or "").strip().replace("\n", "[/br]") or cItem.get("desc", "")
        return [{"title": title or cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon or cItem.get("icon", "")}], "other_info": info}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("SoundCloud.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem is not None and isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "sc_selections":
            self.listSelections(self.currItem)
        elif category == "sc_selection":
            self.listSelection(self.currItem)
        elif category == "sc_playlist":
            self.listPlaylist(self.currItem)
        elif category == "sc_user":
            self.listUser(self.currItem)
        elif category == "sc_search":
            self.listSearch(self.currItem)
        elif category in ("search", "search_next_page"):
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
        CHostBase.__init__(self, SoundCloud(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("soundcloud")

    def getSearchTypes(self):
        return [(_("Titles"), "tracks"), (_("Playlists"), "playlists"), (_("Artists"), "users")]

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("sc_track", "sc_playlist", "sc_user")
