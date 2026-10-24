# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
#   - Kids-Tube.nl: Dutch-spoken children's films, series clips and songs (YouTube videos picked by the site)
#   - sections of the site menu -> all videos / series, A-Z of all series, search
#   - First page / Jump / Next page on the video lists (60 per page)
#   - links: the YouTube video of the page -> urlparser
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper


def GetConfigList():
    return []


def gettytul():
    return "https://kids-tube.nl/"


PAGE_SIZE = 60
# the site menu, when the start page can not be read
SECTIONS = (("/baby-filmpjes/", "Baby"), ("/peuterfilmpjes/", "Peuter"), ("/kleuterfilmpjes/", "Kleuter"), ("/kids/", "Kids 6+"),
            ("/kinderfilms/", "Films"), ("/kinderliedjes/", "Liedjes"), ("/sinterklaas-filmpjes-en-liedjes/", "Sinterklaas"),
            ("/thema-filmpjes-kinderen/", "Thema's"))
YOUTUBE_ID_RES = (re.compile(r"videoId:\s*'([A-Za-z0-9_-]{11})'"), re.compile(r'youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{11})'),
                  re.compile(r'bbvms\.com/p/[^/]+/y/([A-Za-z0-9_-]{11})\.html'), re.compile(r'img\.youtube\.com/vi/([A-Za-z0-9_-]{11})/'),
                  # older pages: the bare id as the iframe source
                  re.compile(r'<iframe src="([A-Za-z0-9_-]{11})"'))
THUMB_ID_RE = re.compile(r'/YouTubeVideo/.*/([A-Za-z0-9_-]{11})\.[a-z]+$')


class KidsTubeNL(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "letter", "yt_id")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "kidstubenl", "cookie": "kidstubenl.cookie"})
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Referer": gettytul()})
        self.defaultParams = {"header": self.HEADER}
        self.MAIN_URL = gettytul()
        self.watchedHelper = IPTVWatchedHelper("kidstubenl")
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        return self.cm.getPage(url, addParams or self.defaultParams, post_data)

    def _path(self, url):
        return re.sub(r'^https?://[^/]+', '', str(url or "").split("?", 1)[0].strip())

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            if cItem.get("type", "") == "video" and cItem.get("category", "") == "kt_video":
                return "video:%s" % path
            if cItem.get("category", "") == "kt_videos":
                return "folder:%s" % path
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMain(self, cItem):
        sts, data = self.getPage(self.MAIN_URL)
        sections = []
        # the sections of the site menu (the entries with a drop-down)
        for path, title in re.findall(r'<a href="(/[^"/]+/)" class="submenu">([^<]+)</a>', data if sts else ""):
            title = self.cleanHtmlStr(title)
            if (path, title) not in sections:
                sections.append((path, title))
        menu = [{"good_for_fav": True, "category": "kt_section", "title": title, "url": self.getFullUrl(path)} for path, title in sections or SECTIONS]
        menu.append({"good_for_fav": True, "category": "kt_az", "title": _("A-Z"), "url": self.getFullUrl("/a-z/")})
        self.listsTab(menu + self.searchItems(), cItem)

    def _categories(self, data):
        ret = []
        for item in data.split('<div class="category">')[1:]:
            url = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0]
            icon = self.cm.ph.getSearchGroups(item, r'<img src="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3>(.*?)</h3>')[0])
            if url and title:
                ret.append((self.getFullUrl(url), title, self.getFullUrl(icon) if icon else ""))
        return ret

    def _addCategory(self, cItem, url, title, icon):
        params = stripPagerKeys(dict(cItem), ("letter",))
        params.update({"good_for_fav": True, "category": "kt_videos", "title": title, "url": url, "icon": icon, "desc": ""})
        self.addDir(params)

    def listSection(self, cItem):
        printDBG("KidsTubeNL.listSection [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        count = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'class="results">([^<]+)<')[0])
        if data.count('<div class="video">'):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "kt_videos", "title": _("All videos"), "desc": count})
            self.addDir(params)
        # the series of the section: a box in the side bar
        box = self.cm.ph.getDataBeetwenMarkers(data, 'class="box categories"', '<div id="footer"', False)[1] or data.split('class="box categories"', 1)[-1]
        for url, title, icon in self._categories(box):
            self._addCategory(cItem, url, title, icon)

    def _azCategories(self):
        sts, data = self.getPage(self.getFullUrl("/a-z/"))
        if not sts:
            return []
        return self._categories(self.cm.ph.getDataBeetwenMarkers(data, '<div class="categories">', '<div id="sidebar"', False)[1])

    @staticmethod
    def _letter(title):
        first = title[:1].upper()
        return first if "A" <= first <= "Z" else "#"

    def listAZ(self, cItem):
        letters = []
        counts = {}
        for url, title, icon in self._azCategories():
            letter = self._letter(title)
            if letter not in counts:
                letters.append(letter)
            counts[letter] = counts.get(letter, 0) + 1
        for letter in sorted(letters):
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "kt_az_letter", "title": "%s (%d)" % (letter, counts[letter]), "letter": letter, "desc": ""})
            self.addDir(params)

    def listAZLetter(self, cItem):
        for url, title, icon in self._azCategories():
            if self._letter(title) == cItem.get("letter", ""):
                self._addCategory(cItem, url, title, icon)

    def _addVideos(self, cItem, data):
        count = 0
        for item in data.split('<div class="video">')[1:]:
            url = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3>(.*?)</h3>')[0])
            if not url or not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'<img src="([^"]+)"')[0]
            ytId = ""
            match = THUMB_ID_RE.search(icon)
            if match:
                # the thumbnail of a YouTube video is named after its id: the JPEG of YouTube instead of the WebP copy
                ytId = match.group(1)
                icon = "https://i.ytimg.com/vi/%s/hqdefault.jpg" % ytId
            series = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<p>(.*?)</p>')[0])
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'class="duration">([^<]*)<')[0])
            params = stripPagerKeys(dict(cItem), ("letter",))
            params.update({"good_for_fav": True, "category": "kt_video", "title": title, "url": self.getFullUrl(url), "yt_id": ytId,
                           "icon": self.getFullIconUrl(icon) if icon else "", "desc": " | ".join(x for x in (series, duration) if x)})
            self.addVideo(params)
            count += 1
        return count

    def listVideos(self, cItem):
        page = max(1, int(cItem.get("page", 1) or 1))
        baseUrl = cItem["url"].split("?", 1)[0]
        url = baseUrl if page == 1 else "%s?start=%d" % (baseUrl, (page - 1) * PAGE_SIZE)
        printDBG("KidsTubeNL.listVideos [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        # only the video list - the page also shows the other series of the section
        videos = self.cm.ph.getDataBeetwenMarkers(data, '<div class="videos">', '<div class="pagination">', False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, '<div class="videos">', 'class="box categories"', False)[1]
        count = self._addVideos(cItem, videos)
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', '</div>', False)[1]
        starts = [int(x) for x in re.findall(r'start=(\d+)', pager)]
        lastPage = max(starts) // PAGE_SIZE + 1 if starts else page
        # ?start= offsets: the constant template only lets "Jump" through, the page number drives the list
        addPagingItems(self, dict(cItem, url=baseUrl, desc=""), page, bool(count) and page < lastPage, lastPage, baseUrl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KidsTubeNL.listSearchResult [%s]" % searchPattern)
        sts, data = self.getPage(self.getFullUrl("/search/%s" % urllib_quote(searchPattern.strip())))
        if not sts:
            return
        # 24 hits at most, no paging
        self._addVideos(cItem, self.cm.ph.getDataBeetwenMarkers(data, '<div class="videos">', '<div id="sidebar"', False)[1])

    ###################################################
    # links
    ###################################################
    def _youtubeId(self, data):
        for regex in YOUTUBE_ID_RES:
            match = regex.search(data)
            if match:
                return match.group(1)
        return ""

    def _description(self, data):
        # the text after the "Series | Title" heading (some pages put it in a <p>, older ones not)
        box = self.cm.ph.getDataBeetwenMarkers(data, '<div class="description">', '<div class="tags">', False)[1]
        return self.cleanHtmlStr(re.sub(r'(?s)<h([12])[^>]*>.*?</h\1>', ' ', box))

    def getLinksForVideo(self, cItem):
        printDBG("KidsTubeNL.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        ytId = self._youtubeId(data) if sts else ""
        ytId = ytId or cItem.get("yt_id", "")
        urlTab = []
        if ytId:
            urlTab.append({"name": "YouTube", "url": "https://www.youtube.com/watch?v=%s" % ytId, "need_resolve": 1})
        elif sts:
            # a few older pages embed another player
            for src in re.findall(r'<iframe[^>]+src="([^"]+)"', data):
                src = self.getFullUrl(src.replace("&amp;", "&"))
                if self.cm.isValidUrl(src) and self.up.checkHostSupport(src) == 1:
                    urlTab.append({"name": self.up.getHostName(src), "url": strwithmeta(src, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urlTab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urlTab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self._description(data) if sts else "", {}))

    def getVideoLinks(self, videoUrl):
        printDBG("KidsTubeNL.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    ###################################################
    # info / favourites
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("KidsTubeNL.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        parts = [x.strip() for x in text.split("|")]
        if len(parts) == 2 and re.match(r'^\d+:\d\d(?::\d\d)?$', parts[1]):
            otherInfo["duration"] = parts[1]
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            description = self._description(data)
            if description:
                text = "%s\n%s" % (text, description) if text else description
            header = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="description">\s*<h1>(.*?)</h1>')[0])
            if " | " in header:
                otherInfo["category"] = header.split(" | ", 1)[0]
            tags = [self.cleanHtmlStr(x) for x in re.findall(r'<a href="/tags/[^"]*" class="tag">(.*?)</a>', data)]
            if tags:
                otherInfo["genres"] = ", ".join(tags)
            views = self.cm.ph.getSearchGroups(data, r'<span class="views">(\d+)</span>')[0]
            if views:
                otherInfo["views"] = views
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "").startswith("kt_"):
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
        printDBG("KidsTubeNL.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({"name": "category"})
        elif category == "kt_section":
            self.listSection(self.currItem)
        elif category == "kt_az":
            self.listAZ(self.currItem)
        elif category == "kt_az_letter":
            self.listAZLetter(self.currItem)
        elif category == "kt_videos":
            self.listVideos(self.currItem)
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
        CHostBase.__init__(self, KidsTubeNL(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("kidstubenl")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "kt_video"
