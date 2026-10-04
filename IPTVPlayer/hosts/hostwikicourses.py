# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - brought to the current host standard
#   (WikiCourses, www.wikicourses.net - Arabic video courses - originally by popking (odem2014))
#   - no f-strings (Python 2), no sleeping 3x retry wrapper, no colour codes; categories ->
#     sub-categories -> courses -> lessons, search + search history (the site has no paging)
#   - lessons are VIDEO rows keyed on their lesson page, the MP4 is read from the page in
#     getLinksForVideo (it used to be the row url, so the download marker followed the file)
#   - watched flag (course -> lessons), favourites, sidecar, INFO (course description / lesson
#     duration and size - no moviemeta, these are courses), name normalisation
#     ("Course - S01Exx - Lesson")
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://www.wikicourses.net/"


class WikiCourses(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "wikicourses", "cookie": "wikicourses.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/wikicourses.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("wikicourses")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        url = self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    @staticmethod
    def _path(url):
        try:
            return urllib_unquote(re.sub(r"^https?://[^/]+", "", url or "")).strip("/")
        except Exception:
            return url or ""

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            kind = {"wc_course": "course", "wc_lesson": "lesson"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", ""))
            return "%s:%s" % (kind, path) if kind and path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        self.addDir({"name": "category", "category": "wc_categories", "good_for_fav": True, "title": _("Categories"), "url": self.getFullUrl("categories/")})
        self.listsTab(self.searchItems(), cItem)

    def listCategories(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for item in re.findall(r'<div class="category-box">(.*?)</a>', data, re.S):
            url = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h3[^>]*>(.*?)</h3>")[0])
            if not url or not title:
                continue
            self.addDir({"name": "category", "category": "wc_subcategories", "good_for_fav": True, "title": title, "url": self._canonUrl(url),
                         "icon": self._canonUrl(self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]),
                         "desc": self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<p class="light-text[^"]*">(.*?)</p>')[0])})

    def listSubCategories(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for item in re.findall(r'<div class="sub-category-box(.*?)</a>', data, re.S):
            url = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h3[^>]*>(.*?)</h3>")[0])
            if not url or not title:
                continue
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<p class="mb-0 mt-2 light-text">(.*?)</p>')[0])
            count = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<span class="light-text d-block[^"]*">(.*?)</span>')[0])
            self.addDir({"name": "category", "category": "wc_courses", "good_for_fav": True, "title": title, "url": self._canonUrl(url),
                         "icon": self._canonUrl(self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]),
                         "desc": " | ".join([x for x in (count, desc) if x])})

    def listCourses(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        self._listCourseBoxes(data)

    def _listCourseBoxes(self, data):
        seen = set()
        for item in re.findall(r'<div class="course-box[^"]*">(.*?)</a>', data, re.S):
            m = re.search(r'<a href="([^"]+)"\s+title="([^"]*)"', item)
            if not m or "/course/" not in m.group(1):
                continue
            url = self._canonUrl(m.group(1))
            if url in seen:
                continue
            seen.add(url)
            videos = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<span>(\d+)</span>\s*<span>")[0])
            lang = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="course-language[^"]*">(.*?)</div>')[0])
            self.addDir({"name": "category", "category": "wc_course", "good_for_fav": True, "title": self.cleanHtmlStr(m.group(2)), "url": url,
                         "icon": self._canonUrl(self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]),
                         "desc": " | ".join([x for x in ((_("videos: %s") % videos) if videos else "", lang) if x])})

    def listLessons(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        course = cItem.get("title", "")
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="playlist-videos">', "</section>", False)[1]
        normalize = IsMediaNamingNormalized()
        seen = set()
        lessons = []
        for item in re.findall(r"<a(.*?)</a>", block, re.S):
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self._canonUrl(url)
            if url in seen:
                continue
            seen.add(url)
            num = self.cm.ph.getSearchGroups(item, r'<span class="primary-clr fw-bold">\s*(\d+)\s*<')[0]
            name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<p class="m-0">(.*?)</p>')[0])
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)fa-clock"></i>\s*<span>(.*?)</span>')[0])
            if normalize and num:
                lesson = re.sub(r"^\d+\s*[.\-_)]\s*", "", name) or name
                title = "%s - %s - %s" % (course, formatSxxExx(1, num), lesson)
            else:
                title = ("%s. %s" % (num, name)) if num and not name.startswith(num) else (name or course)
            lessons.append((int(num) if num else 0, {"name": "category", "category": "wc_lesson", "good_for_fav": True, "title": title, "url": url, "icon": cItem.get("icon", ""),
                           "desc": " | ".join([x for x in (duration, story) if x]), "course_url": cItem["url"], "duration": duration}))
        lessons.sort(key=lambda x: x[0])  # the site sorts the lessons as text (1, 10, 11, 2 ...)
        for _num, params in lessons:
            self.addVideo(params)
        if not seen:
            self.addMarker({"title": _("No stream available"), "desc": story})

    def listSearchResult(self, cItem, searchPattern, searchType):
        sts, data = self.getPage(self.getFullUrl("search?q=%s" % urllib_quote_plus(searchPattern)))
        if sts:
            self._listCourseBoxes(data)

    ###################################################
    # links
    ###################################################
    def _lessonInfo(self, data):
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="playlist-content', '<div class=" col-lg-4', False)[1] or data
        video = self.cm.ph.getSearchGroups(block, r'<source[^>]+src="([^"]+)"')[0]
        # (duration, size) - the site labels them "المدة" / "الحجم"
        fields = [self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r"(?s)<span>%s:</span>\s*<span>(.*?)</span>" % label)[0]) for label in ("المدة", "الحجم")]
        return self._canonUrl(video) if video else "", fields

    def getLinksForVideo(self, cItem):
        printDBG("WikiCourses.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        if re.search(r"\.(mp4|m4v|webm)(\?|$)", url):  # an old favourite with the file itself
            video = url
        else:
            sts, data = self.getPage(url)
            # some lesson pages of old courses are gone (HTTP 404)
            video = self._lessonInfo(data)[0] if sts else ""
        if not video:
            SetIPTVPlayerLastHostError(_("Content not available"))
            return []
        links = [{"name": "WikiCourses MP4", "url": strwithmeta(video, {"User-Agent": self.HEADER["User-Agent"], "Referer": self.MAIN_URL}), "need_resolve": 0}]
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("WikiCourses.getArticleContent [%s]" % cItem.get("url", ""))
        info, text, icon, size = {}, "", cItem.get("icon", ""), ""
        if cItem.get("category") == "wc_lesson":
            sts, data = self.getPage(cItem.get("url", ""))
            if sts:
                duration, size = self._lessonInfo(data)[1]
                if duration:
                    info["duration"] = duration
                if size:
                    size = "%s %s" % (_("Size:"), size)
            courseUrl = cItem.get("course_url", "")
        else:
            courseUrl = cItem.get("url", "")
        if courseUrl:
            sts, data = self.getPage(courseUrl)
            if sts:
                text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]*)"')[0])
                icon = self._canonUrl(self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]) or icon
        text = text or cItem.get("desc", "")
        if size:
            text = "%s[/br][/br]%s" % (size, text) if text else size
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("WikiCourses.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "wc_categories":
            self.listCategories(self.currItem)
        elif category == "wc_subcategories":
            self.listSubCategories(self.currItem)
        elif category == "wc_courses":
            self.listCourses(self.currItem)
        elif category == "wc_course":
            self.listLessons(self.currItem)
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
        CHostBase.__init__(self, WikiCourses(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("wikicourses")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("wc_course", "wc_lesson")
