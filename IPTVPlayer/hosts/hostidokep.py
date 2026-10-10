# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 04.07.2025 - Blindspot
# 10.10.2026 - rework for the current site: the sections and their maps come from the site's own menu, a map page
#   gives its animations (video rows) and maps (picture rows) without fetching every file first; webcams: the tag
#   lists and all cameras (local pages), a camera plays its live stream (when it has one) and the animation of the
#   last hours, INFO shows the current camera picture; picture albums fixed; dead forecast pictures removed;
#   favourites without menu state (also those of version 1.3), INFO from the site's own data, local icons, default
#   user agent
###################################################
HOST_VERSION = "1.4"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://www.idokep.hu/"


MAIN_URL = "https://www.idokep.hu/"
MENU_URL = MAIN_URL + "idojaras/Budapest"
CAM_URL = MAIN_URL + "webkamera/"
LOCAL_PAGE_SIZE = 100

# files of the maps / animations a page shows (also inside its scripts); legends and backgrounds are left out
MEDIA_RE = re.compile(r'''(?:https?:)?(?://[a-z0-9.]*idokep\.(?:hu|eu))?/(?:terkep|radar|idokepradar|csapadek|villam)/[^'"\s<>()?]+?\.(?:mp4|jpg|jpeg|png|gif)(?:\?[^'"\s<>()]*)?''', re.I)
MEDIA_SKIP = ("scale", "skala", "poster", "_bg", "background", "transparent", "legend", "jelmagyarazat")

# forecast maps for the next days (wetterkontor.de)
FORECAST_TAB = [("Előrejelzés holnapra", "http://img.wetterkontor.de/karten/ungarn1.jpg"),
                ("Előrejelzés 2 napra", "http://img.wetterkontor.de/karten/ungarn2.jpg"),
                ("Előrejelzés 3 napra", "http://img.wetterkontor.de/karten/ungarn3.jpg"),
                ("Előrejelzés 4 napra", "http://img.wetterkontor.de/karten/ungarn4.jpg"),
                ("Előrejelzés 5 napra", "http://img.wetterkontor.de/karten/ungarn5.jpg")]

# sections of the site menu (= the label of the menu entry)
SECTIONS_TAB = ["Időkép", "Hőtérkép", "Felhőkép", "Radar", "Térképek"]


class Idokep(CBaseHostClass):

    # stable identity of a row (no state of an earlier menu)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "f_section", "f_cam")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "idokep", "cookie": "idokep.cookie"})
        self.MAIN_URL = MAIN_URL
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/idokep135.png")
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self.cm.iriToUri(url), addParams, post_data)

    def _meta(self, data, name):
        return self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta[^>]+(?:property|name)=['"]%s['"][^>]+content=['"]([^'"]*)['"]''' % name, ignoreCase=True)[0])

    def _listTitle(self, cItem):
        # the list's own title: on page 2+ the item is the "Next page" row
        return cItem.get("f_title") or cItem.get("title", "")

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("Idokep.listMainMenu")
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_forecast", "title": "Előrejelzés", "url": MAIN_URL + "elorejelzes"})
        for title in SECTIONS_TAB:
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_section", "title": title, "f_section": title, "url": MAIN_URL + "#" + title})
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_cam_tags", "title": "Kamerák", "url": CAM_URL})
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_albums", "title": "Képtár", "url": MAIN_URL + "keptar"})

    def listForecast(self, cItem):
        for title, url in FORECAST_TAB:
            self.addPicture({"name": "category", "good_for_fav": True, "title": title, "url": url, "icon": url, "desc": "wetterkontor.de"})

    def _menuEntries(self, label):
        # the entries of a drop-down of the site menu: [(title, url)]
        sts, data = self.getPage(MENU_URL)
        if not sts:
            return []
        menu = self.cm.ph.getDataBeetwenMarkers(data, ">%s</a>" % label, "</ul>", False)[1]
        entries = []
        seen = set()
        for url, title in re.findall(r'''<a[^>]+href=['"]([^'"#]+)[^'"]*['"][^>]*>(.*?)</a>''', menu, re.S):
            url = self.getFullUrl(url)
            title = self.cleanHtmlStr(title)
            if title and url not in seen:
                seen.add(url)
                entries.append((title, url))
        return entries

    def listSection(self, cItem):
        printDBG("Idokep.listSection [%s]" % cItem.get("f_section", ""))
        for title, url in self._menuEntries(cItem.get("f_section", "")):
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_page", "title": title, "url": url})

    def listPage(self, cItem):
        # the maps (pictures) and animations (videos) of a map page
        printDBG("Idokep.listPage [%s]" % cItem["url"])
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self._meta(data, "description") or self._meta(data, "og:description")
        start = data.find("siteMainOuter")
        if start < 0:
            # idokep.eu pages have no siteMainOuter - their head names the Hungarian map as og:image
            start = max(0, data.find("<body"))
        ends = [x for x in [data.find(x, start) for x in ("frontpage600OuterLockup", "sidebar160x600Container", "promo-news-item", "<footer")] if x > 0]
        found = self._pageMedia(data[start:min(ends) if ends else len(data)], url)
        if not found:
            # maps drawn by a script (Időkép, Radar): their files are named only in the script
            found = self._pageMedia(data, url)
        title = cItem["title"]
        icon = ""
        for mediaUrl in found:
            if not mediaUrl.split("?")[0].endswith(".mp4"):
                icon = mediaUrl
                break
        icon = icon or self.DEFAULT_ICON_URL
        for mediaUrl in found:
            name = mediaUrl.split("?")[0].rsplit("/", 1)[-1].rsplit(".", 1)[0]
            rowTitle = title if len(found) == 1 else "%s - %s" % (title, name)
            params = {"name": "category", "good_for_fav": True, "title": rowTitle, "url": mediaUrl, "desc": desc}
            if mediaUrl.split("?")[0].endswith(".mp4"):
                params["icon"] = icon
                self.addVideo(params)
            else:
                params["icon"] = mediaUrl
                self.addPicture(params)

    def _pageMedia(self, data, pageUrl):
        found = []
        paths = set()
        for match in MEDIA_RE.finditer(data):
            mediaUrl = match.group(0)
            path = mediaUrl.split("?")[0].split("idokep.hu", 1)[-1].split("idokep.eu", 1)[-1]
            if path in paths or any(x in path.lower() for x in MEDIA_SKIP):
                continue
            paths.add(path)
            found.append(self.getFullUrl(mediaUrl, pageUrl))
        return found

    ###################################################
    # webcams
    ###################################################
    def listCamTags(self, cItem):
        printDBG("Idokep.listCamTags")
        entries = self._menuEntries("Kamerák")
        if not entries:
            entries = [("Összes", CAM_URL + "mindegyik")]
        if "Élő" not in [x[0] for x in entries]:
            entries.insert(0, ("Élő", CAM_URL + "tag/%C3%A9l%C5%91"))  # the cameras with a live stream
        for title, url in entries:
            if url.rstrip("/") in (CAM_URL.rstrip("/"), MAIN_URL + "webkamera/mindegyik"):
                title, url = "Összes", CAM_URL + "mindegyik"  # the site's "all" link shows only a few cameras
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_cams", "title": title, "url": url})

    def listCams(self, cItem):
        printDBG("Idokep.listCams [%s]" % cItem["url"])
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        cams = []
        seen = set()
        for item in data.split('class="ik kamera-ajanlo"')[1:]:
            cam = self.cm.ph.getSearchGroups(item, r'''href=['"]/webkamera/([^'"/?#]+)['"]''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''<span>(.*?)</span>''')[0])
            if not cam or not title or cam in seen:
                continue
            seen.add(cam)
            icon = self.cm.ph.getSearchGroups(item, r'''(?:poster|src)=['"]([^'"]+?thumbnail\.jpg[^'"]*)['"]''')[0]
            cams.append((cam, title, self.getFullIconUrl(icon) if icon else ""))
        lastPage = max(1, (len(cams) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE)
        page = min(page, lastPage)
        listTitle = self._listTitle(cItem)
        for cam, title, icon in cams[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]:
            self.addVideo({"name": "category", "good_for_fav": True, "title": title, "url": CAM_URL + cam, "f_cam": cam, "icon": icon or self.DEFAULT_ICON_URL,
                           "desc": listTitle})
        if lastPage > 1:
            addPagingItems(self, dict(stripPagerKeys(dict(cItem)), f_title=listTitle), page, page < lastPage, lastPage)

    def _getCamLinks(self, cItem):
        cam = cItem.get("f_cam") or cItem["url"].rstrip("/").rsplit("/", 1)[-1]
        linksTab = []
        sts, data = self.getPage(CAM_URL + cam)
        if sts:
            hls = self.cm.ph.getSearchGroups(data, r'''['"]((?:https?:)?//[^'"]+?\.m3u8[^'"]*)['"]''')[0]
            if hls:
                linksTab.extend(getDirectM3U8Playlist(self.getFullUrl(hls), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))
        # the animation of the last hours (every camera has one)
        linksTab.append({"name": _("Animation"), "url": "https://cam.idokep.hu/%s/animation.mp4" % cam, "need_resolve": 0})
        return linksTab

    ###################################################
    # picture albums
    ###################################################
    def listAlbums(self, cItem):
        printDBG("Idokep.listAlbums")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seen = set()
        for item in data.split('class="col keptar-album"')[1:]:
            url = self.cm.ph.getSearchGroups(item, r'''href=['"](/keptar/album/[^'"]+)['"]''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "ik text"), ("</div", ">"), False)[1])
            if not url or not title or url in seen:
                continue
            seen.add(url)
            icon = self.cm.ph.getSearchGroups(item, r'''<img[^>]+src=['"]([^'"]+)['"]''')[0]
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_album_pics", "title": title, "url": self.getFullUrl(url),
                         "icon": self.getFullIconUrl(icon) if icon else self.DEFAULT_ICON_URL})

    def listAlbum(self, cItem):
        printDBG("Idokep.listAlbum [%s]" % cItem["url"])
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        listTitle = self._listTitle(cItem)
        pics = []
        for item in data.split("album-image-container\">")[1:]:
            url = self.cm.ph.getSearchGroups(item, r'''<img[^>]+src=['"]([^'"]+)['"]''')[0]
            if not url:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "image-title"), ("</div", ">"), False)[1])
            pageUrl = self.cm.ph.getSearchGroups(item, r'''href=['"](/keptar/[^'"]+/kep/\d+)['"]''')[0]
            pics.append((title or listTitle, self.getFullUrl(url), self.getFullUrl(pageUrl) if pageUrl else ""))
        lastPage = max(1, (len(pics) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE)
        page = min(page, lastPage)
        for title, url, pageUrl in pics[(page - 1) * LOCAL_PAGE_SIZE:page * LOCAL_PAGE_SIZE]:
            self.addPicture({"name": "category", "good_for_fav": True, "title": title, "url": url, "icon": url, "desc": "[/br]".join([x for x in (listTitle, pageUrl) if x])})
        if lastPage > 1:
            addPagingItems(self, dict(stripPagerKeys(dict(cItem)), f_title=listTitle), page, page < lastPage, lastPage)

    ###################################################
    # links / INFO / favourites
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Idokep.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        if cItem.get("f_cam") or url.startswith(CAM_URL):
            linksTab = self._getCamLinks(cItem)
        elif self.cm.isValidUrl(url):
            # an animation (mp4) or a map (picture)
            linksTab = [{"name": url.split("?")[0].rsplit(".", 1)[-1], "url": url, "need_resolve": 0}]
        else:
            linksTab = []
        if not linksTab:
            SetIPTVPlayerLastHostError(_("No valid links available."))
        return linksTab

    def getFavouriteData(self, cItem):
        return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))

    def getArticleContent(self, cItem):
        printDBG("Idokep.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("title", "")
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("f_cam"):
            # the camera page: its description and the current picture
            sts, data = self.getPage(CAM_URL + cItem["f_cam"])
            if sts:
                title = self._meta(data, "og:title") or title
                text = self._meta(data, "og:description") or text
                current = self.cm.ph.getSearchGroups(data, r'''<img[^>]+src=['"]([^'"]*kamera\.php\?[^'"]+)['"]''')[0]
                if current:
                    icon = self.getFullIconUrl(current.replace("&amp;", "&"))
                if "m3u8" in data:
                    otherInfo["status"] = _("Live")
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon or self.DEFAULT_ICON_URL}], "other_info": otherInfo}]

    ###################################################
    # favourites of version 1.3 (any row could be saved, without menu state)
    ###################################################
    LEGACY_CATEGORIES = ("list_static", "list_filters", "list_items", "list_riaszt", "list_kamera", "picture_camera", "list_album", "list_pics", "show_pic")

    def listLegacy(self, cItem):
        category = cItem.get("category", "")
        title = cItem.get("title", "")
        printDBG("Idokep.listLegacy [%s] [%s]" % (category, title))
        if category == "list_static":
            self.listForecast(cItem)
        elif category == "list_filters":
            # main menu entries: the sections of the site menu, "Kamerák" the camera tags
            if title == "Kamerák":
                self.listCamTags(cItem)
            else:
                self.listSection(dict(cItem, f_section=title))
        elif category in ("list_items", "list_riaszt"):
            # a map page of a section (url of the site menu entry)
            self.listPage(cItem)
        elif category == "list_kamera":
            self.listCams(cItem)
        elif category == "picture_camera":
            # a camera folder (url https://idokep.hu/webkamera/<cam>) -> the camera row
            cam = cItem.get("url", "").rstrip("/").rsplit("/", 1)[-1]
            if cam:
                self.addVideo({"name": "category", "good_for_fav": True, "title": title or cam, "url": CAM_URL + cam, "f_cam": cam,
                               "icon": cItem.get("icon") or self.DEFAULT_ICON_URL})
        elif category == "list_album":
            self.listAlbums(cItem)
        elif category == "list_pics":
            self.listAlbum(cItem)
        elif category == "show_pic":
            # the page of one album picture -> the picture
            sts, data = self.getPage(cItem.get("url", ""))
            url = self.cm.ph.getSearchGroups(data, r'''<meta[^>]+property=['"]og:image['"][^>]+content=['"]([^'"]+)['"]''')[0] if sts else ""
            if url:
                self.addPicture({"name": "category", "good_for_fav": True, "title": title, "url": self.getFullUrl(url), "icon": self.getFullUrl(url)})

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("Idokep.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Idokep.handleService: name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_forecast":
            self.listForecast(self.currItem)
        elif category == "list_section":
            self.listSection(self.currItem)
        elif category == "list_page":
            self.listPage(self.currItem)
        elif category == "list_cam_tags":
            self.listCamTags(self.currItem)
        elif category == "list_cams":
            self.listCams(self.currItem)
        elif category == "list_albums":
            self.listAlbums(self.currItem)
        elif category == "list_album_pics":
            self.listAlbum(self.currItem)
        elif category in self.LEGACY_CATEGORIES:
            self.listLegacy(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Idokep(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_PICTURE])

    def withArticleContent(self, cItem):
        return cItem.get("type", "") in ("video", "picture")
