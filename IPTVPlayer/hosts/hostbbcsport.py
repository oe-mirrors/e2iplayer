# -*- coding: utf-8 -*-
LAST_MODIFIED = "13.11.2026"
# BBC Sport video clips: the pages carry their data as JSON in window.__INITIAL_DATA__; a section
# opens its /video page when it has one (video rails + a paged grid), else the section page itself.
# Streams through urlparser parserBBC (mediaselector). Watched flag / favourites / sidecar / INFO.
import re
import time

from Components.config import config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
# defines the bbc_* options below
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.bbc import BBCCoUkIE  # noqa: F401
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Default video quality:"), config.plugins.iptvplayer.bbc_default_quality))
    optionList.append(getConfigListEntry(_("Use default video quality:"), config.plugins.iptvplayer.bbc_use_default_quality))
    optionList.append(getConfigListEntry(_("Preferred streaming protocol") + ":", config.plugins.iptvplayer.bbc_prefered_format))
    return optionList


def gettytul():
    return "https://www.bbc.co.uk/sport"


MAIN_URL = "https://www.bbc.co.uk/"
VPID_URL = MAIN_URL + "iplayer/vpid/%s/"
# "topic-stream": the paged stream of the smaller sports (gymnastics, gaelic games ...)
PROMO_COLLECTIONS = ("hierarchical-promo-collection", "simple-promo-collection", "simple-promo-grid", "billboard", "topic-stream")
PAGED_COLLECTIONS = ("simple-promo-grid", "topic-stream")
# promo types with a /videos/ page ("portrait-video" = the vertical clips)
VIDEO_PROMO_TYPES = ("video", "portrait-video")
VIDEO_PATH_RE = re.compile(r'^/sport/(?:[^/?#]+/)*videos/[A-Za-z0-9]+$')


class BBCSport(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "vpid", "page_url", "duration", "published", "summary")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "bbcsport", "cookie": "bbcsport.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = MAIN_URL
        self.watchedHelper = IPTVWatchedHelper("bbcsport")
        self.wfInitFolderCache()

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        # clips only - the sections change every hour, they are no series
        try:
            if isinstance(cItem, dict) and cItem.get("type", "") == "video" and cItem.get("url"):
                return "video:%s" % cItem["url"]
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    def _fullUrl(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        return MAIN_URL.rstrip("/") + "/" + path.lstrip("/")

    def _pageData(self, url):
        # window.__INITIAL_DATA__ = "<JSON in a JS string>" -> {"data": {<component key>: {"name", "data", "props"}}}
        sts, data = self.cm.getPage(url, self.defaultParams)
        if not sts:
            return {}
        match = re.search(r'window\.__INITIAL_DATA__\s*=\s*(".*?"|\{.*?\});?\s*</script>', data, re.S)
        if not match:
            printDBG("BBCSport._pageData no page data [%s]" % url)
            return {}
        try:
            state = json_loads(match.group(1))
            if not isinstance(state, dict):
                state = json_loads(state)
            return state if isinstance(state, dict) else {}
        except Exception:
            printExc()
        return {}

    def _components(self, state):
        return [c for c in (state.get("data") or {}).values() if isinstance(c, dict)]

    def _findDicts(self, obj, test, out):
        if isinstance(obj, dict):
            if test(obj):
                out.append(obj)
            for value in obj.values():
                self._findDicts(value, test, out)
        elif isinstance(obj, list):
            for value in obj:
                self._findDicts(value, test, out)
        return out

    def _image(self, image):
        url = ""
        if isinstance(image, dict):
            url = image.get("src", "") or image.get("url", "") or ""
        elif hasattr(image, "lower"):
            # str / py2 unicode
            url = image
        # the box decodes no webp: the jpg / png the webp variant is made from
        return url.replace(".jpg.webp", ".jpg").replace(".png.webp", ".png").replace("{width}", "480")

    def _duration(self, seconds):
        try:
            seconds = int(seconds)
        except Exception:
            return ""
        if seconds <= 0:
            return ""
        hours, rest = divmod(seconds, 3600)
        minutes, secs = divmod(rest, 60)
        return "%d:%02d:%02d" % (hours, minutes, secs) if hours else "%d:%02d" % (minutes, secs)

    def _published(self, isoTime):
        try:
            return time.strftime("%d.%m.%Y", time.strptime(isoTime[:10], "%Y-%m-%d"))
        except Exception:
            return ""

    ###################################################
    # rows
    ###################################################
    def _addPromo(self, cItem, promo, seen):
        path = (promo.get("url") or "").split("?", 1)[0]
        title = self.cleanHtmlStr(promo.get("headline") or promo.get("contentTitle") or "")
        if promo.get("type") not in VIDEO_PROMO_TYPES or not title or not VIDEO_PATH_RE.match(path):
            return False
        url = self._fullUrl(path)
        if url in seen:
            return False
        seen.add(url)
        duration = self._duration((promo.get("duration") or 0) // 1000)
        published = self._published(promo.get("lastPublished") or "")
        text = self.cleanHtmlStr(promo.get("description") or promo.get("summary") or "")
        params = stripPagerKeys(dict(cItem), ("vpid", "page_url"))
        params.update({"good_for_fav": True, "category": "sport_video", "title": title, "url": url, "page_url": url,
                       "icon": self._image(promo.get("image") or promo.get("backgroundImage")),
                       "duration": duration, "published": published, "summary": text, "desc": self._desc(duration, published, text)})
        self.addVideo(params)
        return True

    def _desc(self, duration, published, text):
        head = " | ".join([t for t in (duration, published) if t])
        if head and text:
            return "%s\n%s" % (head, text)
        return head or text

    def _addShort(self, cItem, entry, seen):
        # portrait clips: the version id is in the list itself, there is no page
        media = ((entry.get("media") or {}).get("items") or [{}])[0]
        vpid = media.get("id", "") if media.get("idType") == "versionID" else ""
        title = self.cleanHtmlStr((entry.get("promo") or {}).get("headline") or media.get("title") or "")
        if not vpid or not title:
            return False
        url = VPID_URL % vpid
        if url in seen:
            return False
        seen.add(url)
        duration = self._duration(media.get("duration"))
        params = stripPagerKeys(dict(cItem), ("vpid", "page_url"))
        params.update({"good_for_fav": True, "category": "sport_video", "title": title, "url": url, "vpid": vpid, "page_url": "",
                       "icon": self._image((entry.get("promo") or {}).get("image")) or self._image(media.get("holdingImageUrl")),
                       "duration": duration, "published": "", "summary": "", "desc": duration})
        self.addVideo(params)
        return True

    ###################################################
    # lists
    ###################################################
    def _navigation(self, state):
        # (primary sections, A-Z of all sports) as (label, path)
        primary, allSports = [], []
        for comp in self._components(state):
            if comp.get("name") != "product-navigation":
                continue
            nav = (comp.get("data") or {}).get("productNav") or {}
            for item in nav.get("primary") or []:
                if item.get("url", "").startswith("/sport") and not item.get("hidden") and not item["url"].startswith("/sport/my"):
                    primary.append((item.get("label", ""), item["url"]))
            for group in nav.get("more") or []:
                if "A-Z" in (group.get("title") or ""):
                    for item in group.get("items") or []:
                        if item.get("url", "").startswith("/sport") and not item.get("hidden"):
                            allSports.append((item.get("label", ""), item["url"]))
            break
        return primary, allSports

    def _addSection(self, cItem, label, path):
        params = dict(cItem)
        params.update({"good_for_fav": True, "category": "sport_section", "title": self.cleanHtmlStr(label), "url": self._fullUrl(path), "desc": ""})
        self.addDir(params)

    def listMainMenu(self, cItem):
        primary, allSports = self._navigation(self._pageData(MAIN_URL + "sport"))
        for label, path in primary:
            self._addSection(cItem, label, path)
        if allSports:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "sport_all", "title": "A-Z", "desc": ""})
            self.addDir(params)

    def listAllSports(self, cItem):
        for label, path in self._navigation(self._pageData(MAIN_URL + "sport"))[1]:
            if path.rstrip("/") == "/sport/all-sports":
                continue  # "Full Sports A-Z": a page of links, no clips
            self._addSection(cItem, label, path)

    def listSection(self, cItem):
        # the section's /video page when it has one (only some sports do), else the section page
        base = cItem.get("url", "").rstrip("/")
        page = max(1, int(cItem.get("page", 1) or 1))
        printDBG("BBCSport.listSection [%s] page %s" % (base, page))
        pageQuery = "?page=%d" % page if page > 1 else ""
        state = self._pageData((base if base.endswith("/video") else base + "/video") + pageQuery)
        if not state.get("data"):
            state = self._pageData(base + pageQuery)
        seen = set()
        lastPage = 0
        pagedRows = 0
        for comp in self._components(state):
            name = comp.get("name", "")
            data = comp.get("data") or {}
            paged = name in PAGED_COLLECTIONS and isinstance(data.get("page"), dict)
            if paged:
                lastPage = int(data["page"].get("total", 0) or 0)
            elif page > 1:
                # further pages only page the grid / stream
                continue
            rows = len(self.currList)
            if name in PROMO_COLLECTIONS:
                for promo in self._findDicts(data, lambda d: "url" in d and "headline" in d and "type" in d, []):
                    self._addPromo(cItem, promo, seen)
            elif name == "portrait-video-experience":
                for entry in data.get("items") or []:
                    self._addShort(cItem, entry, seen)
            if paged:
                pagedRows += len(self.currList) - rows
            title = data.get("title") if hasattr(data.get("title"), "lower") else ""
            if title and len(self.currList) > rows:
                # the rail's heading above its clips
                self.currList.insert(rows, {"type": "marker", "title": self.cleanHtmlStr(title)})
        if not [item for item in self.currList if item.get("type") != "marker"]:
            # sections like Horse Racing / Motorsport carry only articles
            SetIPTVPlayerLastHostError(_("No items found"))
        if lastPage and (pagedRows or page > 1):
            # a grid of articles only gets no pager (its pages would be empty here); the page lives in
            # cItem["page"]: Jump / First page keep the section url unchanged
            addPagingItems(self, dict(cItem, desc=""), page, page < lastPage, lastPage, cItem.get("url", "").replace("{", "{{").replace("}", "}}"))

    ###################################################
    # links
    ###################################################
    def _pageVersionId(self, url):
        # the clip of a video page: media-experience -> initialItem (the rest is "more videos");
        # returns (vpid, geoBlocked) - outside the UK the page leaves "media" empty for UK-only clips
        state = self._pageData(url)
        for comp in self._components(state):
            if comp.get("name") != "media-experience":
                continue
            initialItem = (comp.get("data") or {}).get("initialItem") or {}
            media = (initialItem.get("mediaItem") or {}).get("media")
            ids = self._findDicts(media or {}, lambda d: d.get("idType") == "versionID" and d.get("id"), [])
            if ids:
                return ids[0]["id"], False
            return "", media is None
        return "", False

    def getLinksForVideo(self, cItem):
        printDBG("BBCSport.getLinksForVideo [%s]" % cItem.get("url", ""))
        vpid, geo = cItem.get("vpid", ""), False
        if not vpid:
            vpid, geo = self._pageVersionId(cItem.get("page_url") or cItem.get("url", ""))
        if not vpid:
            SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking).") if geo else _("No stream available"))
            return []
        links = [{"name": cItem.get("title", ""), "url": VPID_URL % vpid, "need_resolve": 1}]
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("BBCSport.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        # sport clips: the site's own text (no film / series data to look up)
        title = cItem.get("title", "")
        otherInfo = {}
        if cItem.get("duration"):
            otherInfo["duration"] = cItem["duration"]
        if cItem.get("published"):
            otherInfo["released"] = cItem["published"]
        return [{"title": title, "text": cItem.get("summary") or title,
                 "images": [{"title": "", "url": cItem.get("icon", "")}] if cItem.get("icon") else [],
                 "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("sport_"):
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
        printDBG("BBCSport.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            # most match clips are UK-only, interviews / features play worldwide
            self.informAboutGeoBlockingIfNeeded("GB")
            self.listMainMenu({"name": "category"})
        elif category == "sport_all":
            self.listAllSports(self.currItem)
        elif category == "sport_section":
            self.listSection(self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, BBCSport(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("bbcsport")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "sport_video"
