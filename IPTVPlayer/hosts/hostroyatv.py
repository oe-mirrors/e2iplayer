# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Roya TV (roya.tv) - the Jordanian broadcaster's own streaming site.
#   - all data from the public API the web site itself uses (backend.roya.tv/api/v01), no login:
#     live channels (Roya TV, Roya News, Roya Sport, Roya Kids, the FAST channels, Al Sharqiya ...),
#     programmes by category and series by genre (24 per page), programme -> episodes (12 per page,
#     First page / Jump / Next page); search through the site's search page (programmes, series, episodes)
#   - links: the ticket request of the web player (ticket.roya-tv.com/api/v5/...) on every play - the live
#     channels get their public kwikmotion HLS, the episodes an hdnts-tokenised kwikmotion HLS; episodes
#     the site plays from YouTube go through urlparser
#   - "Roya Plus" (subscription) programmes and episodes are not listed; no DRM content
#   - watched flag (programme -> episode), favourites, name normalisation ("Show - SxxExx" for series),
#     sidecar, INFO via moviemeta + the site's own description
import json
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
    return "https://roya.tv/"


API = "https://backend.roya.tv/api/v01/"
TICKET = "https://ticket.roya-tv.com/api/v5/"
LIST_SIZE = 24
EPISODE_PAGE = 12
# Arabic ordinals ("الحلقة الثامنة", "الموسم السابع", "الحلقة الحادية عشرة", "الحلقة الخامسة والعشرون")
UNITS = (("الحادية", 1), ("الحادي", 1), ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2),
         ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6), ("السادس", 6),
         ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10))
TENS = (("العشرون", 20), ("الثلاثون", 30), ("الأربعون", 40), ("الاربعون", 40), ("الخمسون", 50))
# \S instead of an Arabic character class: the patterns are byte strings on python 2
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+|\S+(?:\s+(?:عشرة|عشر)|\s+و\S+)?)")
SEASON_RE = re.compile(r"الموسم\s*(\d+|\S+(?:\s+(?:عشرة|عشر))?)")


def _ordinal(text):
    # "12" / "الثانية عشرة" / "الخامسة والعشرون" / "العشرون" -> 12 / 12 / 25 / 20, 0 when unknown
    text = (text or "").strip()
    if text.isdigit():
        return int(text)
    total = 0
    for word in text.replace(" و", " ").split():
        value = 10 if word in ("عشر", "عشرة") else (dict(TENS).get(word) or dict(UNITS).get(word))
        if not value:
            break  # a word after the number ("الحلقة الثامنة وفاء ...")
        total += value
    return total


def _num(regex, text):
    m = regex.search(text or "")
    return _ordinal(m.group(1)) if m else 0


class RoyaTV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "item_id", "channel_id", "stream_url", "list_url",
                  "s_title", "s_season", "s_episode", "is_series", "episodes_count", "site_plot", "youtube_id")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "royatv", "cookie": "royatv.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/royatv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Referer": self.MAIN_URL})
        self.defaultParams = {"header": self.HEADER}
        self.watchedHelper = IPTVWatchedHelper("royatv")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def _json(self, url):
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return None

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("rv_channel", "rv_video", "rv_program", "rv_list"):
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
            if category == "rv_video":
                return "video:%s" % cItem["item_id"]
            if category == "rv_program":
                return "program:%s" % cItem["item_id"]
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "rv_channels", "title": _("Live channels")},
            {"category": "rv_cats", "title": _("Programmes"), "kind": "categories"},
            {"category": "rv_cats", "title": _("Series"), "kind": "genres"},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listChannels(self, cItem):
        data = self._json(API + "homepage/rows?device_size=Size03Q40&page=1")
        rows = ((data.get("data") or {}).get("rows") or []) if isinstance(data, dict) else []
        for row in rows:
            if not isinstance(row, dict) or row.get("type") != "channels":
                continue
            for channel in row.get("items") or []:
                if not isinstance(channel, dict) or not channel.get("id") or not self.cm.isValidUrl(channel.get("url", "")):
                    continue
                if "%s" % channel.get("status", 1) != "1":
                    continue
                desc = self.cleanHtmlStr(channel.get("description", ""))
                kind = self.cleanHtmlStr(channel.get("type", ""))
                self.addVideo({"name": "category", "category": "rv_channel", "good_for_fav": True, "title": self.cleanHtmlStr(channel.get("title", "")),
                               "url": "%slive-stream/%s" % (self.MAIN_URL, channel["id"]), "channel_id": "%s" % channel["id"], "stream_url": channel["url"],
                               "icon": self.getFullIconUrl(channel.get("thumbnail_web") or channel.get("logo") or ""),
                               "desc": "%s[/br]%s" % (kind, desc) if kind and desc else (desc or kind)})
            break

    def listCategories(self, cItem):
        kind = cItem.get("kind", "categories")
        if kind == "genres":
            data = self._json(API + "genres") or {}
            entries = [(g.get("id"), g.get("name")) for g in data.get("genres") or [] if isinstance(g, dict)] if isinstance(data, dict) else []
        else:
            data = self._json(API + "categories?device_size=Size1920Q40") or {}
            entries = [(c.get("category_id"), c.get("category_name")) for c in data.get("categories") or [] if isinstance(c, dict)] if isinstance(data, dict) else []
        for entryId, name in entries:
            if entryId is None or not name:
                continue
            url = "%s%s/%s/" % (API, kind, entryId)
            self.addDir({"name": "category", "category": "rv_list", "good_for_fav": True, "title": self.cleanHtmlStr(name), "url": url, "list_url": url})

    def _programParams(self, program):
        programId = program.get("value") or program.get("id")
        name = self.cleanHtmlStr(program.get("title") or program.get("name") or "")
        if not programId or not name or program.get("plus"):
            return None
        parent = self.cleanHtmlStr(program.get("season_title") or "")
        title = "%s - %s" % (parent, name) if parent and parent not in name else name
        isSeries = "%s" % program.get("program_type", "") == "2"
        count = program.get("episodesCount") or program.get("episodes_count") or 0
        if not count and ("episodesCount" in program or "episodes_count" in program):
            return None  # announced ("coming soon"), no episode online yet
        plot = self.cleanHtmlStr(program.get("description") or "")
        parts = []
        if count:
            parts.append("%s: %s" % (_("Episodes"), count))
        if program.get("days_namespace"):
            parts.append(self.cleanHtmlStr(program["days_namespace"]))
        desc = " | ".join(parts)
        if plot:
            desc = "%s[/br]%s" % (desc, plot) if desc else plot
        # a season programme ("الموسم السابع" of "بين قوسين"): the show is its parent
        show = parent if parent and SEASON_RE.search(name) else title
        return {"name": "category", "category": "rv_program", "good_for_fav": True, "title": title, "s_title": show,
                "s_season": _num(SEASON_RE, name) or 1, "is_series": isSeries, "episodes_count": int(count or 0),
                "url": "%sprogram/%s" % (self.MAIN_URL, programId), "item_id": "%s" % programId, "site_plot": plot, "desc": desc,
                "icon": self.getFullIconUrl(program.get("thumbnail_web") or program.get("image_url") or program.get("cover_image") or "")}

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        base = cItem.get("list_url") or cItem["url"]
        printDBG("RoyaTV.listItems [%s] page %d" % (base, page))
        data = self._json("%s%d?device_size=Size03Q40&device_type=1" % (base, page))
        programs = []
        if isinstance(data, dict):
            programs = data.get("programs") or data.get("series") or []
        for program in programs:
            params = self._programParams(program) if isinstance(program, dict) else None
            if params:
                self.addDir(params)
        addPagingItems(self, dict(cItem, category="rv_list", list_url=base), page, len(programs) >= LIST_SIZE, 0, base)

    def _addEpisode(self, cItem, episode, normalize):
        episodeId = episode.get("value")
        if not episodeId or episode.get("plus"):
            return
        label = self.cleanHtmlStr(episode.get("name") or episode.get("episode_title") or "")
        show = cItem.get("s_title", "") or self.cleanHtmlStr(episode.get("tree_name") or "")
        num = _num(EPISODE_RE, label)
        if normalize and num and show and cItem.get("is_series"):
            title = "%s - %s" % (show, formatSxxExx(cItem.get("s_season", 1) or 1, num))
        elif show and show not in label:
            title = "%s - %s" % (show, label)
        else:
            title = label
        parts = []
        if episode.get("duration"):
            parts.append("%s: %s" % (_("Duration"), episode["duration"]))
        if episode.get("created_at"):
            parts.append("%s: %s" % (_("Published"), episode["created_at"]))
        note = self.cleanHtmlStr(episode.get("description") or "")
        desc = " | ".join(parts)
        if note:
            desc = "%s[/br]%s" % (desc, note) if desc else note
        self.addVideo({"name": "category", "category": "rv_video", "good_for_fav": True, "title": title, "url": "%svideos/%s" % (self.MAIN_URL, episodeId),
                       "item_id": "%s" % episodeId, "s_title": show, "s_season": cItem.get("s_season", 1), "s_episode": num,
                       "is_series": cItem.get("is_series", False), "site_plot": cItem.get("site_plot", ""), "youtube_id": episode.get("youtube_video_id") or "",
                       "icon": self.getFullIconUrl(episode.get("image_url") or episode.get("thumbnail") or "") or cItem.get("icon", ""), "desc": desc})

    def listEpisodes(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        printDBG("RoyaTV.listEpisodes [%s] page %d" % (cItem.get("item_id", ""), page))
        data = self._json("%sepisodes/%s/%d?device_size=Size03Q40&device_type=1" % (API, cItem.get("item_id", ""), page))
        episodes = (data.get("episodes") or []) if isinstance(data, dict) else []
        normalize = IsMediaNamingNormalized()
        for episode in episodes:
            if isinstance(episode, dict):
                self._addEpisode(cItem, episode, normalize)
        count = int(cItem.get("episodes_count", 0) or 0)
        lastPage = (count + EPISODE_PAGE - 1) // EPISODE_PAGE if count else 0
        addPagingItems(self, dict(cItem, category="rv_program"), page, len(episodes) >= EPISODE_PAGE and (not lastPage or page < lastPage), lastPage,
                       cItem.get("url", ""))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("RoyaTV.listSearchResult [%s]" % searchPattern)
        # the site's search page renders the result on the server: the "result" object of its Next.js data
        sts, data = self.cm.getPage("%ssearch-results?for=%s" % (self.MAIN_URL, urllib_quote(searchPattern.strip(), safe="")), self.defaultParams)
        if not sts:
            return
        result = {}
        try:
            text = "".join(json_loads('"%s"' % chunk) for chunk in re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', data, re.S))
            start = text.find('"result":{')
            if start > -1:
                result = json.JSONDecoder().raw_decode(text[start + 9:])[0]
        except Exception:
            printExc()
        if not isinstance(result, dict):
            return
        for key in ("series", "programs"):
            for program in result.get(key) or []:
                params = self._programParams(program) if isinstance(program, dict) else None
                if params:
                    self.addDir(params)
        normalize = IsMediaNamingNormalized()
        for episode in result.get("episodes") or []:
            if isinstance(episode, dict):
                self._addEpisode({}, episode, normalize)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("RoyaTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        if cItem.get("category") == "rv_channel" and cItem.get("channel_id"):
            urltab = [{"name": "Roya HLS", "url": strwithmeta(cItem["url"], {"rv_channel": cItem["channel_id"], "rv_stream": cItem.get("stream_url", "")}),
                       "need_resolve": 1}]
        elif cItem.get("youtube_id"):
            urltab = [{"name": "YouTube", "url": "https://www.youtube.com/watch?v=%s" % cItem["youtube_id"], "need_resolve": 1}]
        elif cItem.get("item_id"):
            urltab = [{"name": "Roya HLS", "url": strwithmeta(cItem.get("url", ""), {"rv_video": cItem["item_id"]}), "need_resolve": 1}]
        else:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), ""))

    def _ticket(self, path):
        data = self._json(TICKET + path)
        url = ((data or {}).get("data") or {}).get("secured_url", "") if isinstance(data, dict) else ""
        return url if self.cm.isValidUrl(url) else ""

    def _hlsLinks(self, url, live):
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
        printDBG("RoyaTV.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        meta = getattr(videoUrl, "meta", {}) or {}
        links = []
        if meta.get("rv_channel"):
            # the web player's ticket request on every play; the channel list's own address as fallback
            url = self._ticket("fastchannel/%s?device_type=1" % meta["rv_channel"]) or meta.get("rv_stream", "")
            if self.cm.isValidUrl(url):
                links = self._hlsLinks(url, True)
        elif meta.get("rv_video"):
            url = self._ticket("video/%s/ticket?device_type=1" % meta["rv_video"])
            if url:
                links = self._hlsLinks(url, False)
        elif self.cm.isValidUrl(videoUrl):
            links = self.up.getVideoLinkExt(videoUrl)
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("RoyaTV.getArticleContent [%s]" % cItem.get("url", ""))
        icon = cItem.get("icon", "")
        if cItem.get("category") == "rv_channel":
            return [{"title": cItem.get("title", ""), "text": cItem.get("desc", "") or cItem.get("title", ""),
                     "images": [{"title": "", "url": icon}] if icon else [], "other_info": {}}]
        title = cItem.get("s_title", "") or cItem.get("title", "")
        meta = {}
        try:
            skip = () if isLatinTitle(title) else LATIN_ONLY
            meta = getMeta("tv", title, "", skip)
        except Exception:
            printExc()
        info = dict(meta.get("info", {}))
        plot = meta.get("plot", "")
        story = cItem.get("site_plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        if cItem.get("category") == "rv_video" and cItem.get("desc"):
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
        printDBG("RoyaTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "rv_channels":
            self.listChannels(self.currItem)
        elif category == "rv_cats":
            self.listCategories(self.currItem)
        elif category == "rv_list":
            self.listItems(self.currItem)
        elif category == "rv_program":
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
        CHostBase.__init__(self, RoyaTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("royatv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("rv_channel", "rv_video", "rv_program")
