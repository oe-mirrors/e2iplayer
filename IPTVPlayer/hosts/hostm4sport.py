# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.12.2022 - Blindspot
# 10.10.2026 - rework for the current site: the usage counter / box data sent to figyelmeztetes.hu (and its config
#   options and logos) removed; live channels (M4 Sport, M4 Sport +, M4 Sport 1-5 while they broadcast) with the
#   programme now on air from the site's stream list; the video rows of m4sport.hu/video (the old ajax lists answer
#   empty); streams through the MTVA player with the page as referer, "only in Hungary" told instead of an empty
#   list; watched flag (row -> video), downloaded marker, favourites (also those of version 1.8), sidecar,
#   "Title (YYYY-MM-DD)" naming, INFO from the site's own data, local icons, default user agent
###################################################
HOST_VERSION = "2.0"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
import re
###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://m4sport.hu/"


MAIN_URL = "https://m4sport.hu/"
VIDEO_URL = MAIN_URL + "video"
STREAMS_URL = MAIN_URL + "wp-content/plugins/hms-global-widgets/interfaces/streamJSONs/StreamSelector.json"
PLAYER_URL = "https://player.mediaklikk.hu/playernew/player.php?video=%s"
# the M4 Sport channels of the stream list (M4 Sport 2-5 only while they broadcast)
LIVE_CODES = ("mtv4live", "mtv4plus", "m4sport1", "m4sport2", "m4sport3", "m4sport4", "m4sport5")


class M4Sport(GenericFolderWatchedScraperMixin, CBaseHostClass):

    # stable identity of a row (no state of an earlier menu)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "raw_title", "icon", "desc", "date", "live", "f_code", "f_row")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "m4sport.hu", "cookie": "m4sport.cookie"})
        self.MAIN_URL = MAIN_URL
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/m4sport135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("m4sport")
        self.wfInitFolderCache()

    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def _meta(self, data, name):
        return self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta[^>]+(?:property|name)=['"]%s['"][^>]+content=['"]([^'"]*)['"]''' % name)[0])

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or cItem.get("live") or cItem.get("md") == "elo":
                return ""
            if cItem.get("type") == "video":
                path = re.sub(r"^https?://[^/]+", "", cItem.get("url", "")).rstrip("/")
                return "video:%s" % path if path else ""
            if cItem.get("category") == "list_row" and cItem.get("f_row"):
                return "folder:row:%s" % cItem["f_row"]
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("type") == "video" or cItem.get("category") == "list_row":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("M4Sport.listMainMenu")
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_live", "title": _("Live"), "url": MAIN_URL + "#live", "icon": self.DEFAULT_ICON_URL})
        self.listVideoRows(cItem)

    def _getStreams(self):
        sts, data = self.getPage(STREAMS_URL)
        if not sts:
            return []
        try:
            return json_loads(data).get("streams", []) or []
        except Exception:
            printExc()
        return []

    def _programme(self, streams, code):
        # (now, next) programme of a channel: dicts of the stream list
        now, nxt = {}, {}
        for item in streams:
            if ensure_str(item.get("code", "")) == code:
                if item.get("type") == "live" and not now:
                    now = item
                elif item.get("type") == "next" and not nxt:
                    nxt = item
        return now, nxt

    def _programmeDesc(self, now, nxt):
        lines = []
        for item in (now, nxt):
            if item:
                lines.append("%s-%s %s" % (ensure_str(item.get("time", "")), ensure_str(item.get("endTime", "")), self.cleanHtmlStr(ensure_str(item.get("title", "")))))
        if now.get("description"):
            lines.append(self.cleanHtmlStr(ensure_str(now["description"]).replace("\n", "<br>")))
        return "[/br]".join(lines)

    def listLive(self, cItem):
        printDBG("M4Sport.listLive")
        streams = self._getStreams()
        for code in LIVE_CODES:
            now, nxt = self._programme(streams, code)
            if not now:
                continue
            name = self.cleanHtmlStr(ensure_str(now.get("name", code)))
            icon = self.getFullIconUrl(ensure_str(now.get("image", "")).split("?")[0]) or self.DEFAULT_ICON_URL
            self.addVideo({"name": "category", "good_for_fav": True, "live": True, "title": name, "url": MAIN_URL + "#" + code, "f_code": code,
                           "icon": icon, "desc": self._programmeDesc(now, nxt)})

    def _getVideoRows(self):
        # [(row title, [(url, title, icon)])] of the video page
        sts, data = self.getPage(VIDEO_URL)
        if not sts:
            return []
        rows = []
        parts = re.split(r"<h2[^>]*>", data)
        for part in parts[1:]:
            title = self.cleanHtmlStr(part.split("</h2>", 1)[0])
            items = []
            seen = set()
            for item in re.split(r'''<a class=['"][^'"]*ItemLink[^'"]*['"]''', part)[1:]:
                url = self.cm.ph.getSearchGroups(item, r'''href=['"](https?://(?:www\.)?(?:m4sport|mediaklikk)\.hu/videok?/[^'"]+)['"]''')[0]
                name = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''pMultiplerowGridTitle['"]>(.*?)</p>''')[0]) or \
                    self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<h1", ">"), ("</h1", ">"), False)[1])
                if not url or not name or url in seen:
                    continue
                seen.add(url)
                icon = self.cm.ph.getSearchGroups(item, r'''data-src=['"]([^'"]+)['"]''')[0] or self.cm.ph.getSearchGroups(item, r'''<img[^>]+src=['"]([^'"]+)['"]''')[0]
                items.append((url, name, icon))
            if title and items:
                rows.append((title, items))
        return rows

    def listVideoRows(self, cItem):
        for title, items in self._getVideoRows():
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_row", "title": title, "f_row": title, "url": VIDEO_URL + "#" + title,
                         "icon": items[0][2] or self.DEFAULT_ICON_URL, "desc": "%d %s" % (len(items), _("Videos"))})

    def listRow(self, cItem):
        printDBG("M4Sport.listRow [%s]" % cItem.get("f_row", ""))
        for title, items in self._getVideoRows():
            if title != cItem.get("f_row"):
                continue
            for url, name, icon in items:
                date = self.cm.ph.getSearchGroups(url, r"/videok?/(\d{4})/(\d\d)/(\d\d)/", 3)
                date = "-".join(date) if date[0] else ""
                desc = " | ".join([x for x in ("%s.%s.%s" % (date[8:10], date[5:7], date[:4]) if date else "", "M4 Sport - %s" % title) if x])
                self.addVideo({"name": "category", "good_for_fav": True, "title": normalizeMediathekTitle(name, date=date), "raw_title": name, "url": url,
                               "icon": icon or self.DEFAULT_ICON_URL, "desc": desc, "date": date})
            break

    ###################################################
    # links
    ###################################################
    def _getPlayerLinks(self, video, referer):
        # MTVA player: the stream url only with the page of the video as referer
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=referer)
        sts, data = self.getPage(PLAYER_URL % video, params)
        if not sts:
            return []
        linksTab = []
        for url in re.findall(r'''['"]file['"]\s*:\s*['"]([^'"]+)['"]''', data):
            url = url.replace("\\/", "/")
            if url.startswith("//"):
                url = "https:" + url
            if self.cm.isValidUrl(url) and ".m3u8" in url:
                linksTab = getDirectM3U8Playlist(strwithmeta(url, {"User-Agent": self.HEADER["User-Agent"], "Referer": "https://player.mediaklikk.hu/"}),
                                                 checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
                if linksTab:
                    break
        if not linksTab:
            if "INVALID_LOCATION" in data:
                SetIPTVPlayerLastHostError(_("Not available in your country (geo-blocking)."))
            else:
                SetIPTVPlayerLastHostError(_("No valid links available."))
        return linksTab

    def _liveCode(self, cItem):
        # live rows: "f_code"; favourites of version 1.8: "md" = "elo" with the channel in "id"
        if cItem.get("f_code"):
            return cItem["f_code"]
        return cItem.get("id", "") if cItem.get("md") == "elo" else ""

    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("M4Sport.getLinksForVideo [%s]" % url)
        code = self._liveCode(cItem)
        if code:
            return self._getPlayerLinks(code, MAIN_URL)
        token = ""
        # favourites of version 1.8 may carry a fixed-up page url in "url2" ("videok//" -> "video/<date>/")
        url2 = cItem.get("url2", "")
        for pageUrl in [url] + ([url2] if url2 and url2 != url else []):
            sts, data = self.getPage(pageUrl)
            if not sts:
                continue
            token = self.cm.ph.getSearchGroups(data, r'''['"]token['"]\s*:\s*['"]([^'"]+)['"]''')[0]
            if token:
                token = urllib_quote(urllib_unquote(token.replace("\\/", "/")), safe="")
            else:
                token = self.cm.ph.getSearchGroups(data, r'''['"]streamId['"]\s*:\s*['"]([^'"]+)['"]''')[0]
            if token:
                url = pageUrl
                break
        if not token:
            SetIPTVPlayerLastHostError(_("No valid links available."))
            return []
        return applySidecarToLinks(self._getPlayerLinks(token, url), buildSidecarFromItem(cItem, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("M4Sport.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("raw_title", cItem.get("title", ""))
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        code = self._liveCode(cItem)
        if code:
            now, nxt = self._programme(self._getStreams(), code)
            if now:
                text = self._programmeDesc(now, nxt)
                otherInfo["status"] = _("Live")
        elif cItem.get("type") == "video":
            sts, data = self.getPage(cItem["url"])
            if sts:
                # "... | MédiaKlikk" (\S*: the é is two bytes on py2)
                title = re.sub(r"\s*\|\s*M\S*diaKlikk$", "", self._meta(data, "og:title")) or title
                # (the plain "description" is the site's slogan on every page)
                text = self._meta(data, "og:description") or text
                image = self._meta(data, "og:image")
                if image and "logo" not in image:
                    icon = image
            if cItem.get("date"):
                otherInfo["released"] = cItem["date"]
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon or self.DEFAULT_ICON_URL}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("M4Sport.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("M4Sport.handleService: name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_live":
            self.listLive(self.currItem)
        elif category == "list_row":
            self.listRow(self.currItem)
        elif category == "list_main":
            # folder favourites of version 1.8 (BOXUTCA, MAGYAR FOCI ...): their ajax lists are gone, the video rows instead
            self.listVideoRows(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, M4Sport(), True, [CDisplayListItem.TYPE_VIDEO])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("m4sport")

    def withArticleContent(self, cItem):
        return cItem.get("type", "") == "video"
