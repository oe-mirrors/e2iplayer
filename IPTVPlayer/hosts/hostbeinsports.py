# -*- coding: utf-8 -*-
# Last Modified: 08.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - beinsports.com video clips (highlights, news) in Arabic (ar-mena) or English (en-mena)
#   - the menu ("Leagues" rail: sports + competitions) and the clip lists come from the site's
#     content API (prod-kontentadapter, a few KB per page) instead of the 8 MB Next.js page data;
#     lists 0 before: the f-string / compat code did not run on our framework
#   - the clips are Dailymotion videos of the Beinsports-MENA channel that may only be played on
#     beinsports.com (DM016 "Content not available" without the embedder) - the host asks the
#     Dailymotion metadata with beinsports.com as embedder and returns the HLS variants itself
#   - paging First page / Jump / Next page (total count known), watched / downloaded flag keyed on the
#     Dailymotion id, favourites, sidecar, INFO with the clip's teaser, date, duration and league
import re
import time

from Components.config import ConfigSelection, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

config.plugins.iptvplayer.beinsports_lang = ConfigSelection(default="ar-mena", choices=[("ar-mena", _("Arabic")), ("en-mena", _("English"))])


def GetConfigList():
    return [getConfigListEntry(_("Language:"), config.plugins.iptvplayer.beinsports_lang)]


def gettytul():
    return "https://www.beinsports.com/"


API_URL = "https://prod-kontentadapter.beinsports.com/kp/domain/items/"
PAGE_SIZE = 24
DM_ID_RE = re.compile(r"dailymotion\.com/(?:embed/)?video/([A-Za-z0-9]+)")


class BeinSports(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "beinsports", "cookie": "beinsports.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/beinsports135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        # the site's own front-end key of its content API
        self.API_HEADER = dict(self.HEADER, **{"Accept": "application/json", "Origin": self.MAIN_URL.rstrip("/"),
                                               "Referer": self.MAIN_URL, "x-kp-api-key": "qwerty"})
        self.watchedHelper = IPTVWatchedHelper("beinsports")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def _lang(self):
        return config.plugins.iptvplayer.beinsports_lang.value

    def _api(self, path, query):
        params = dict(self.defaultParams)
        params["header"] = self.API_HEADER
        sts, data = self.getPage(API_URL + path + "?" + urllib_urlencode(query), params)
        if not sts:
            return {}
        try:
            data = json_loads(data)
            return data if isinstance(data, dict) else {}
        except Exception:
            printExc()
        return {}

    def _dmId(self, url):
        m = DM_ID_RE.search(url or "")
        return m.group(1) if m else ""

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("category") == "bs_video":
                dmId = self._dmId(cItem.get("url", ""))
                return ("video:dm:%s" % dmId) if dmId else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [{"name": "category", "category": "bs_clips", "title": _("Latest videos"), "tag_id": ""}]
        # the "Leagues" rail of the video page: sports and competitions (ids are the clips' tags)
        data = self._api("block___hybrid_rail", {"depth": 2, "limit": 5, "desiredLanguage": self._lang(), "filterByLanguage": self._lang(),
                                                 "elements": "title,competition_and_sports,display_name",
                                                 "elements.competition_and_sports[nempty]": ""})
        for rail in data.get("items", [])[:1]:
            for entry in rail.get("competition_and_sports") or []:
                title = self.cleanHtmlStr(entry.get("display_name", ""))
                if title and entry.get("_id"):
                    menu.append({"name": "category", "category": "bs_clips", "title": title, "tag_id": entry["_id"], "good_for_fav": True})
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def _clipRow(self, title, teaser, video, date, folder):
        url = video.get("url", "")
        if not title or not self._dmId(url):
            return None
        thumbs = (video.get("resizedThumbnails") or [{}])[0]
        icon = thumbs.get("url480") or thumbs.get("url720") or video.get("thumbnail", "")
        duration = video.get("duration") or 0
        info = [x for x in (date[:10], ("%d:%02d" % (duration // 60, duration % 60)) if duration else "", folder) if x]
        desc = " | ".join(info)
        if teaser:
            desc = "%s[/br]%s" % (desc, teaser) if desc else teaser
        return {"name": "category", "category": "bs_video", "good_for_fav": True, "title": title, "url": "https://www.dailymotion.com/video/%s" % self._dmId(url),
                "icon": icon, "desc": desc, "teaser": teaser, "date": date[:10], "duration": duration, "folder": folder}

    def listClips(self, cItem):
        page = cItem.get("page", 1)
        tagId = cItem.get("tag_id", "")
        query = {"depth": 3, "limit": PAGE_SIZE, "skip": (page - 1) * PAGE_SIZE, "desiredLanguage": self._lang(), "filterByLanguage": self._lang(),
                 "system.workflow_step[in]": "published", "includeTotalCount": "true", "order": "elements.publication_date[desc]",
                 "elements": "title,teaser,publication_date,video_manager,video_manager__video_manager",
                 "elements.video_manager__video_manager[nempty]": "",
                 "elements.publication_date[lte]": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())}
        if tagId:
            query["elements.tags_generator__main[all]"] = tagId
        data = self._api("article", query)
        # league / sport name for the clip's desc and INFO (pager rows carry it, their own title is "Next page")
        folder = (cItem.get("folder_title") or cItem.get("title", "")) if tagId else ""
        count = 0
        for item in data.get("items", []):
            try:
                videos = json_loads((item.get("video_manager") or {}).get("video_manager__video_manager") or "[]")
            except Exception:
                printExc()
                continue
            if not videos:
                continue
            row = self._clipRow(self.cleanHtmlStr(item.get("title", "")), self.cleanHtmlStr(item.get("teaser", "")), videos[0],
                                item.get("publication_date") or "", folder)
            if row:
                self.addVideo(row)
                count += 1
        pagination = data.get("pagination", {})
        total = pagination.get("total_count") or 0
        lastPage = (total + PAGE_SIZE - 1) // PAGE_SIZE if total else 0
        listItem = dict(cItem)
        # the clip API pages by "skip": the list function builds it from cItem["page"], the url is only the row's template
        listItem.update({"category": "bs_clips", "folder_title": folder, "url": API_URL + "article"})
        addPagingItems(self, listItem, page, count > 0 and bool(pagination.get("has_next_page")), lastPage, API_URL + "article#page={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("BeinSports.listSearchResult [%s]" % searchPattern)
        sts, data = self.getPage(self.getFullUrl("/%s/search?query=%s" % (self._lang(), urllib_quote(searchPattern.strip()))))
        if not sts:
            return
        try:
            nextData = json_loads(self.cm.ph.getSearchGroups(data, r'(?s)<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')[0])
            queries = nextData["props"]["pageProps"]["initialState"]["searchApi"]["queries"]
        except Exception:
            printExc()
            return
        for key in queries:
            if not key.startswith("getContentSearch"):
                continue
            for item in (queries[key].get("data") or {}).get("NEWS") or []:
                article = item.get("articleData") or {}
                videos = article.get("videos") or []
                if not videos:
                    continue
                row = self._clipRow(self.cleanHtmlStr(article.get("title", "")), self.cleanHtmlStr(article.get("teaser", "")), videos[0],
                                    article.get("publicationDate") or "", "")
                if row:
                    self.addVideo(row)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("BeinSports.getLinksForVideo [%s]" % url)
        if not self._dmId(url):
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        urltab = [{"name": "Dailymotion", "url": url, "need_resolve": 1}]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("BeinSports.getVideoLinks [%s]" % videoUrl)
        dmId = self._dmId(videoUrl)
        if not dmId:
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        # Beinsports-MENA limits its videos to its own site: without the embedder the metadata says DM016
        sts, data = self.getPage("https://www.dailymotion.com/player/metadata/video/%s?%s" % (dmId, urllib_urlencode({"embedder": self.MAIN_URL})))
        try:
            metadata = json_loads(data) if sts else {}
        except Exception:
            printExc()
            metadata = {}
        error = metadata.get("error")
        if error or not metadata.get("qualities"):
            SetIPTVPlayerLastHostError((error or {}).get("title") or _("No stream available"))
            return []
        cookieParams = {"header": self.HEADER, "cookiefile": self.COOKIE_FILE, "use_cookie": True, "save_cookie": True, "load_cookie": True}
        urltab = []
        for media in metadata["qualities"].get("auto") or []:
            if media.get("type") != "application/x-mpegURL" or not media.get("url"):
                continue
            hlsUrl = strwithmeta(media["url"], {"User-Agent": self.HEADER["User-Agent"], "Referer": self.MAIN_URL})
            for item in getDirectM3U8Playlist(hlsUrl, checkExt=False, checkContent=True, sortWithMaxBitrate=99999999, cookieParams=cookieParams):
                meta = dict(item["url"].meta) if hasattr(item["url"], "meta") else {}
                meta.update({"iptv_proto": "m3u8", "User-Agent": self.HEADER["User-Agent"], "Cookie": self.cm.getCookieHeader(self.COOKIE_FILE)})
                item["url"] = strwithmeta(str(item["url"]).split("#")[0], meta)
                item["name"] = "Dailymotion %sp" % item.get("height", 0) if item.get("height") else item.get("name", "Dailymotion")
                urltab.append(item)
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return decorateResolvedLinkItems(urltab, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        info = {}
        if cItem.get("date"):
            info["released"] = cItem["date"]
        duration = cItem.get("duration") or 0
        if duration:
            info["duration"] = "%d:%02d" % (duration // 60, duration % 60)
        if cItem.get("folder"):
            info["category"] = cItem["folder"]
        icon = cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": cItem.get("teaser") or cItem.get("title", ""),
                 "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("BeinSports.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "bs_clips":
            self.listClips(self.currItem)
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
        CHostBase.__init__(self, BeinSports(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("beinsports")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "bs_video"
