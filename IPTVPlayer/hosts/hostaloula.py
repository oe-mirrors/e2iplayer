# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Aloula (aloula.sba.sa) - the streaming platform of the Saudi Broadcasting Authority (SBA).
#   - all data from the public JSON API the web site itself uses (aloula.faulio.com/api), no login:
#     live TV channels (Saudia, SBC, Al Ekhbariya, Thikrayat, Quran, Sunna, KSA Sports 1-3 ...) and the
#     radio stations; programmes and series by genre (24 per page, First page / Jump / Next page),
#     programme -> seasons (only when there are more than one) -> episodes; search (programmes / episodes)
#   - live: the channel's player request (/channels/<id>/player, the same one the web player makes) is sent
#     on every play, its kwikmotion HLS carries a short-lived hdnts token; the live-edge playlist of the same
#     token is used instead of the 6 h DVR playlist
#   - VOD: the episode's player request (/video/<id>/player) gives an unprotected HLS playlist; only items
#     open to guests are listed (no subscription content, no DRM)
#   - watched flag (programme -> season -> episode), favourites, name normalisation ("Show - SxxExx"),
#     sidecar, INFO via moviemeta + the site's own description
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://aloula.sba.sa/"


API = "https://aloula.faulio.com/api/"
PAGE_SIZE = 24
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")
SEASON_RE = re.compile(r"الموسم\s*(\d+)")


def _num(regex, text):
    m = regex.search(text or "")
    return int(m.group(1)) if m else 0


def _guest(item):
    # the item is open without an account (no subscription / pay-per-view content)
    access = (item.get("item_access") or {}).get("access") if isinstance(item.get("item_access"), dict) else None
    if isinstance(access, dict):
        return bool(access.get("guest"))
    return item.get("access", "guest") in ("guest", None, "")


class Aloula(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "item_id", "channel_id", "content_type", "genre_id",
                  "season_id", "s_title", "s_season", "s_episode", "site_plot", "meta_year", "list_url")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "aloula", "cookie": "aloula.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/aloula135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Referer": self.MAIN_URL, "Origin": self.MAIN_URL.rstrip("/"), "Accept": "application/json, text/plain, */*"})
        self.defaultParams = {"header": self.HEADER}
        self.watchedHelper = IPTVWatchedHelper("aloula")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def _api(self, path):
        sts, data = self.cm.getPage(API + path, self.defaultParams)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def _block(self, data):
        # the first block of a v1.1 / list answer: {"paging": {...}, "projects": [...]}
        try:
            return data["blocks"][0]
        except Exception:
            return {}

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("al_channel", "al_video", "al_project", "al_season", "al_list"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or not cItem.get("item_id"):
                return ""
            category = cItem.get("category", "")
            if category == "al_video":
                return "video:%s" % cItem["item_id"]
            if category == "al_project":
                return "project:%s" % cItem["item_id"]
            if category == "al_season":
                return "season:%s|%s" % (cItem["item_id"], cItem.get("season_id", ""))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "al_channels", "title": _("Live channels"), "kind": "video"},
            {"category": "al_channels", "title": _("Radio stations"), "kind": "audio"},
            {"category": "al_genres", "title": _("Programmes"), "content_type": "program"},
            {"category": "al_genres", "title": _("Series"), "content_type": "series"},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listChannels(self, cItem):
        data = self._api("v1/channels")
        kind = cItem.get("kind", "video")
        for channel in data if isinstance(data, list) else []:
            if not isinstance(channel, dict) or not channel.get("id") or (channel.get("type") or "video") != kind:
                continue
            if not channel.get("livestream_available") or not _guest(channel):
                continue
            title = self.cleanHtmlStr(channel.get("title", "")).split(" – ")[0].strip()
            logo = (channel.get("logo") or {}).get("full") or (channel.get("logo") or {}).get("small") or ""
            self.addVideo({"name": "category", "category": "al_channel", "good_for_fav": True, "title": title,
                           "url": "%sar/live/%s" % (self.MAIN_URL, channel.get("url") or channel["id"]), "channel_id": "%s" % channel["id"],
                           "icon": self.getFullIconUrl(logo), "desc": self.cleanHtmlStr(channel.get("description", ""))})

    def listGenres(self, cItem):
        contentType = cItem.get("content_type", "program")
        data = self._api("v1/home?content_type=%s" % contentType)
        genres = []
        for block in (data.get("blocks") or []) if isinstance(data, dict) else []:
            if isinstance(block, dict) and block.get("block_type") == "block_genre":
                genres = block.get("genres") or []
                break
        for genre in genres:
            if not isinstance(genre, dict) or not genre.get("name"):
                continue
            genreId = "%s" % genre.get("id", "0")
            url = "%sv1/project?content_type=%s" % (API, contentType)
            if genreId != "0":
                url += "&genre=%s" % genreId
            icon = (genre.get("cover") or {}).get("small") if isinstance(genre.get("cover"), dict) else ""
            self.addDir({"name": "category", "category": "al_list", "good_for_fav": True, "title": self.cleanHtmlStr(genre["name"]),
                         "url": url, "list_url": url, "icon": self.getFullIconUrl(icon or "")})

    def _projectParams(self, project):
        projectId = project.get("id")
        title = self.cleanHtmlStr(project.get("title", ""))
        if not projectId or not title or not _guest(project):
            return None
        year = "%s" % (project.get("year") or "")
        plot = self.cleanHtmlStr(project.get("description") or "")
        channels = [self.cleanHtmlStr(c.get("title", "")).split(" – ")[0].strip() for c in project.get("channels") or [] if isinstance(c, dict)]
        parts = []
        if year:
            parts.append("%s: %s" % (_("Year"), year))
        if project.get("count_episodes"):
            parts.append("%s: %s" % (_("Episodes"), project["count_episodes"]))
        if channels:
            parts.append("%s: %s" % (_("Channel"), ", ".join(channels)))
        desc = " | ".join(parts)
        if plot:
            desc = "%s[/br]%s" % (desc, plot) if desc else plot
        return {"name": "category", "category": "al_project", "good_for_fav": True, "title": title, "s_title": title,
                "url": "%stitle/%s" % (self.MAIN_URL, projectId), "item_id": "%s" % projectId,
                "icon": self.getFullIconUrl(project.get("image") or project.get("image_internal") or ""),
                "desc": desc, "site_plot": plot, "meta_year": year, "content_type": project.get("type", "")}

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        base = cItem.get("list_url") or cItem["url"]
        printDBG("Aloula.listItems [%s] page %d" % (base, page))
        block = self._block(self._api("%s&page=%d&ipp=%d" % (base[len(API):], page, PAGE_SIZE)))
        for project in block.get("projects") or []:
            params = self._projectParams(project) if isinstance(project, dict) else None
            if params:
                self.addDir(params)
        lastPage = int((block.get("paging") or {}).get("last_page") or 0) if isinstance(block.get("paging"), dict) else 0
        addPagingItems(self, dict(cItem, category="al_list", list_url=base), page, page < lastPage, lastPage, base)

    def listProject(self, cItem):
        printDBG("Aloula.listProject [%s]" % cItem.get("item_id", ""))
        data = self._api("v1.1/project/%s" % cItem.get("item_id", ""))
        seasons = []
        for block in (data.get("blocks") or []) if isinstance(data, dict) else []:
            if isinstance(block, dict) and block.get("block_type") == "block_seasons":
                seasons = [s for s in block.get("seasons") or [] if isinstance(s, dict) and s.get("id") and _guest(s)]
        if len(seasons) <= 1:
            season = seasons[0] if seasons else {}
            label = (season.get("season") or {}).get("label", "") if isinstance(season.get("season"), dict) else ""
            self.listEpisodes(dict(cItem, season_id="%s" % season.get("id", ""), s_season=_num(SEASON_RE, label) or 1))
            return
        normalize = IsMediaNamingNormalized()
        for season in seasons:
            label = self.cleanHtmlStr((season.get("season") or {}).get("label") or season.get("title", ""))
            num = _num(SEASON_RE, label)
            title = ("%s - %s" % (cItem.get("s_title", ""), formatSxxExx(num))) if normalize and num else label
            params = dict(cItem)
            params.update({"category": "al_season", "good_for_fav": True, "title": title, "season_id": "%s" % season["id"], "s_season": num or 1,
                           "page": 1})
            if season.get("image"):
                params["icon"] = self.getFullIconUrl(season["image"])
            self.addDir(params)

    def _addEpisode(self, cItem, video, normalize):
        videoId = video.get("id")
        if not videoId or not _guest(video):
            return
        label = self.cleanHtmlStr(video.get("title", ""))
        show = cItem.get("s_title", "") or self.cleanHtmlStr(video.get("program_title", ""))
        seasonNum = int(video.get("season_number") or 0) or cItem.get("s_season", 0) or 1
        num = _num(EPISODE_RE, label)
        if normalize and num and show:
            title = "%s - %s" % (show, formatSxxExx(seasonNum, num))
        elif show and show != label:
            title = "%s - %s" % (show, label)
        else:
            title = label
        duration = int((video.get("duration") or {}).get("total") or 0) if isinstance(video.get("duration"), dict) else 0
        parts = []
        if duration:
            parts.append("%s: %d:%02d:%02d" % (_("Duration"), duration // 3600, duration // 60 % 60, duration % 60))
        if video.get("season_title"):
            parts.append("%s: %s" % (_("Season"), self.cleanHtmlStr(video["season_title"])))
        note = self.cleanHtmlStr(video.get("description") or "")
        desc = " | ".join(parts)
        for extra in (note, cItem.get("site_plot", "")):
            if extra:
                desc = "%s[/br]%s" % (desc, extra) if desc else extra
        params = {"name": "category", "category": "al_video", "good_for_fav": True, "title": title, "url": "%sepisode/%s" % (self.MAIN_URL, videoId),
                  "item_id": "%s" % videoId, "s_title": show, "s_season": seasonNum, "s_episode": num, "site_plot": cItem.get("site_plot", ""),
                  "meta_year": cItem.get("meta_year", ""), "content_type": cItem.get("content_type", ""),
                  "icon": self.getFullIconUrl(video.get("image") or "") or cItem.get("icon", ""), "desc": desc}
        self.addVideo(params)

    def listEpisodes(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        query = "v1.1/video?program=%s&type=regular" % cItem.get("item_id", "")
        if cItem.get("season_id"):
            query += "&season=%s" % cItem["season_id"]
        block = self._block(self._api("%s&page=%d&ipp=%d" % (query, page, PAGE_SIZE)))
        normalize = IsMediaNamingNormalized()
        for video in block.get("projects") or []:
            if isinstance(video, dict):
                self._addEpisode(cItem, video, normalize)
        lastPage = int((block.get("paging") or {}).get("last_page") or 0) if isinstance(block.get("paging"), dict) else 0
        listItem = dict(cItem)
        listItem["category"] = "al_season" if cItem.get("category") == "al_season" else "al_project"
        addPagingItems(self, listItem, page, page < lastPage, lastPage, cItem.get("url", ""))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Aloula.listSearchResult [%s] type[%s]" % (searchPattern, searchType))
        page = int(cItem.get("page", 1) or 1)
        kind = "videos" if searchType == "videos" else "programs"
        data = self._api("v1/search?like=%s&type=%s&page=%d&ipp=%d" % (urllib_quote(searchPattern.strip(), safe=""), kind, page, PAGE_SIZE))
        if not isinstance(data, dict):
            return
        normalize = IsMediaNamingNormalized()
        for entry in data.get("list") or []:
            item = entry.get("item") if isinstance(entry, dict) else None
            if not isinstance(item, dict):
                continue
            item = dict(item, item_access=entry.get("item_access") or item.get("item_access"))
            if entry.get("item_type") == "programs":
                params = self._projectParams(item)
                if params:
                    self.addDir(params)
            elif entry.get("item_type") == "videos":
                self._addEpisode({}, item, normalize)
        lastPage = int(data.get("last_page") or 0)
        addPagingItems(self, dict(cItem, category="search_next_page"), page, page < lastPage, lastPage)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Aloula.getLinksForVideo [%s]" % cItem.get("url", ""))
        if cItem.get("category") == "al_channel":
            url = strwithmeta(cItem.get("url", ""), {"al_channel": cItem.get("channel_id", "")})
        else:
            url = strwithmeta(cItem.get("url", ""), {"al_video": cItem.get("item_id", "")})
        if not cItem.get("channel_id") and not cItem.get("item_id"):
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks([{"name": "Aloula HLS", "url": url, "need_resolve": 1}], buildSidecarFromItem(cItem, IsSidecarEnabled(), ""))

    def _hlsLinks(self, url, live):
        # no Origin header: the kwikmotion edge answers the variant playlists with 403 when it is sent
        meta = {"User-Agent": self.HEADER["User-Agent"], "Referer": self.MAIN_URL, "iptv_proto": "m3u8"}
        if live:
            meta["iptv_livestream"] = True
        links = getDirectM3U8Playlist(strwithmeta(url, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)
        if not links:
            sts, data = self.cm.getPage(url, self.defaultParams)
            if sts and "#EXTM3U" in data:
                links = [{"name": "HLS", "url": strwithmeta(url, meta)}]
        return links

    def getVideoLinks(self, videoUrl):
        printDBG("Aloula.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        meta = getattr(videoUrl, "meta", {}) or {}
        links = []
        if meta.get("al_channel"):
            # the player request of the web site: a fresh token on every play
            data = self._api("v1.1/channels/%s/player" % meta["al_channel"]) or {}
            hls = (data.get("streams") or {}).get("hls") or (data.get("audio_streams") or {}).get("hls") or ""
            if self.cm.isValidUrl(hls):
                if "/playlist_dvr.m3u8" in hls:
                    # same token: the live-edge playlist instead of the 6 h DVR window
                    links = self._hlsLinks(hls.replace("/playlist_dvr.m3u8", "/playlist.m3u8"), True)
                if not links:
                    links = self._hlsLinks(hls, True)
        elif meta.get("al_video"):
            data = self._api("v1/video/%s/player" % meta["al_video"]) or {}
            settings = (data.get("settings") or {}) if isinstance(data, dict) else {}
            hls = (settings.get("protocols") or {}).get("hls") or ""
            if self.cm.isValidUrl(hls):
                links = self._hlsLinks(hls, False)
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Aloula.getArticleContent [%s]" % cItem.get("url", ""))
        icon = cItem.get("icon", "")
        if cItem.get("category") == "al_channel":
            return [{"title": cItem.get("title", ""), "text": cItem.get("desc", "") or cItem.get("title", ""),
                     "images": [{"title": "", "url": icon}] if icon else [], "other_info": {}}]
        title = cItem.get("s_title", "") or cItem.get("title", "")
        meta = {}
        try:
            skip = () if isLatinTitle(title) else LATIN_ONLY
            meta = getMeta("tv", title, cItem.get("meta_year", ""), skip)
        except Exception:
            printExc()
        info = {}
        if cItem.get("meta_year"):
            info["year"] = cItem["meta_year"]
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        story = cItem.get("site_plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        if cItem.get("category") == "al_video" and cItem.get("desc"):
            text = "%s[/br][/br]%s" % (cItem["desc"], text) if text and text not in cItem["desc"] else cItem["desc"]
        icon = meta.get("poster") or icon
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Aloula.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "al_channels":
            self.listChannels(self.currItem)
        elif category == "al_genres":
            self.listGenres(self.currItem)
        elif category == "al_list":
            self.listItems(self.currItem)
        elif category == "al_project" and int(self.currItem.get("page", 1) or 1) == 1:
            self.listProject(self.currItem)
        elif category in ("al_project", "al_season"):
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
        CHostBase.__init__(self, Aloula(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("aloula")

    def getSearchTypes(self):
        return [(_("Programmes"), "programs"), (_("Episodes"), "videos")]

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("al_channel", "al_video", "al_project", "al_season")
