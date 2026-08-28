# -*- coding: utf-8 -*-
###################################################
# 2026-08-28 - add automatic videa-quality - by Blindspot
###################################################
HOST_VERSION = "1.7"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigYesNo, getConfigListEntry
import re
import random
import urllib.parse
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.videa_id = ConfigYesNo(default=False)
config.plugins.iptvplayer.videa_quality = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("id:", config.plugins.iptvplayer.videa_id))
    optionList.append(getConfigListEntry(_("Select best available quality"), config.plugins.iptvplayer.videa_quality))
    return optionList


###################################################


def gettytul():
    return "Videa"


class videa(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "videa", "cookie": "videa.cookie"})
        self.USER_AGENT = "User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
        self.HEADER = self.cm.getDefaultHeader()
        self.DEFAULT_ICON_URL = "https://videa.hu/static/uis/redesign/images/product-logos/videa-logo-footer.png"
        self.MAIN_URL = "https://videa.hu"
        self.vmkrs = self.MAIN_URL + "/kereses"
        self.aid = config.plugins.iptvplayer.videa_id.value
        self.vszkzrs = []
        self.defaultParams = {"header": self.HEADER, "use_cookie": False, "load_cookie": False, "save_cookie": False, "cookiefile": self.COOKIE_FILE}

    def _uriIsValid(self, url):
        return "://" in url

    def getFullIconUrl(self, url):
        url = url.replace("&amp;", "&")
        return CBaseHostClass.getFullIconUrl(self, url)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            return urllib.parse.urljoin(baseUrl, url)

        addParams["cloudflare_params"] = {"domain": self.up.getDomain(baseUrl), "cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT, "full_url_handle": _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        try:
            tab_kat = "videa_kategoriak"
            desc_kat = self.getdvdsz(tab_kat, "Videa kategóriáinak megjelenítése...")
            tab_csat = "videa_csatornak"
            desc_csat = self.getdvdsz(tab_csat, "Videa csatornáinak megjelenítése...")
            MAIN_CAT_TAB = [{"category": "list_main", "title": _("Categories"), "tab_id": tab_kat, "desc": desc_kat}, {"category": "list_main", "title": _("Channels"), "tab_id": tab_csat, "desc": desc_csat}] + self.searchItems()
            self.listsTab(MAIN_CAT_TAB, {"name": "category"})
        except Exception:
            return

    def listMainItems(self, cItem):
        try:
            self.vszkzrs = self.malvadkiszrz()
            tabID = cItem.get("tab_id", "")
            if tabID == "videa_kategoriak":
                self.Vdktgrk(cItem, tabID)
            elif tabID == "videa_csatornak":
                self.Vdcstrnk(cItem, tabID)
        except Exception:
            return

    def _listMainSection(self, cItem, tabID, items, descSuffix):
        mlt = []
        try:
            for item in items:
                url = self.cm.ph.getSearchGroups(item, "href=['\"]([^\"']+?)['\"]")[0]
                if url.startswith("/"):
                    url = self.MAIN_URL + url
                if not self.cm.isValidUrl(url):
                    continue
                title = self.cm.ph.getSearchGroups(item, "text\"[>]([^\"']+?)[<]")[0].capitalize()
                desc = self.getdvdsz(url, '"' + title + '" ' + descSuffix)
                params = MergeDicts(cItem, {"good_for_fav": False, "category": "list_second", "title": title, "url": url, "icon": "", "desc": desc, "tab_id": tabID})
                mlt.append(params)
            if len(mlt) > 0:
                random.shuffle(mlt)
                for ipv in mlt:
                    self.addDir(ipv)
        except Exception:
            return

    def Vdktgrk(self, cItem, tabID):
        sts, data = self.getPage(self.MAIN_URL)
        if not sts or len(data) == 0:
            return
        data = data.split('class="category-item">')
        del data[0]
        self._listMainSection(cItem, tabID, data, "kategória videóinak megjelenítése...")

    def Vdcstrnk(self, cItem, tabID):
        sts, data = self.getPage(self.MAIN_URL)
        if not sts or len(data) == 0:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'title list-opener">', "</ul>")[1]
        if len(data) == 0:
            return
        data = data.split("<li>")
        del data[0]
        self._listMainSection(cItem, tabID, data, " csatorna videóinak megjelenítése...")

    def listSecondItems(self, cItem):
        try:
            tabID = cItem.get("tab_id", "")
            if tabID in ("videa_kategoriak", "videa_csatornak"):
                url = cItem["url"]
                CAT_TAB = [{"category": "list_items", "title": "Feltöltés ideje szerint", "url": url + "?page=1", "desc": ""}, {"category": "list_items", "title": "Nézettség szerint", "url": url + "?popular&page=1", "desc": ""}, {"category": "list_items", "title": "Legrégebbi elöl", "url": url + "?oldest&page=1", "desc": ""}]
                self.listsTab(CAT_TAB, cItem)
        except Exception:
            return

    def listItems(self, cItem):
        try:
            url_ere = cItem["url"]
            page = cItem.get("page", 1)
            searchMode = cItem.get("search_mode", False)
            channelMode = cItem.get("channel_mode", False)
            if not searchMode and not channelMode and "/csatornak/" in url_ere:
                channelMode = True
            if channelMode:
                url_ere = re.sub(r"[?&]page=\d+", "", url_ere)
            elif not searchMode and page > 0 and "page=" in url_ere:
                idx1 = url_ere.rfind("page=")
                url_ere = url_ere[:idx1].strip() + "page=" + str(page)
            sts, data = self.getPage(url_ere)
            if not sts or len(data) == 0:
                return
            nextPage = False
            if not searchMode and not channelMode:
                nextPage = bool(self.cm.ph.getSearchGroups(data, "next\"\\shref=['\"]([^\"']+?)['\"]")[0])
            data = data.split('class="col video-item">')
            del data[0]
            if channelMode:
                data = data[:36]
            lastItemId = ""
            for item in data:
                itemId = self.cm.ph.getSearchGroups(item, """data-item-id=['"]([^"']+?)['"]""")[0]
                if itemId != "":
                    lastItemId = itemId
                url = self.cm.ph.getSearchGroups(item, "<a\\shref=['\"]([^\"']+?)['\"]\\sa")[0]
                if not self.cm.isValidUrl(url):
                    continue
                icon = self.cm.ph.getSearchGroups(item, """data-image=['"]([^"']+?)['"]""")[0]
                if icon == "":
                    icon = self.DEFAULT_ICON_URL
                elif icon.startswith("/"):
                    icon = self.MAIN_URL + icon
                vszrz = self.cm.ph.getSearchGroups(item, """aria-label=['"]([^"']+?)['"].+\n.+href""")[0]
                if not vszrz:
                    vszrz = self.cm.ph.getSearchGroups(item, """uploader.{,50}[>]([^"']+?)[<]/a""")[0]
                if not vszrz:
                    vszrz = self.cm.ph.getSearchGroups(item, """tagok[/]([^"']+?)[-"]""")[0]
                if self.vszkzrs and any(s in vszrz for s in self.vszkzrs):
                    continue
                vhz = self.cm.ph.getSearchGroups(item, """length"[>]([0-9:]+?)[<]""")[0]
                vmsg = self.cm.ph.getDataBeetwenMarkers(item, 'div class="hd">', "</div>", False)[1]
                if vmsg != "":
                    vmsg = "  |  " + vmsg
                title = self.cm.ph.getSearchGroups(item, """aria-label=['"]([^"']+?)['"].+\n.+div""")[0]
                if title == "":
                    continue
                ftlv = self.cm.ph.getSearchGroups(item, """uploaded-at"[>]([^"']+?)[<]""")[0]
                desc = title + "\n" + _("Duration:") + " " + vhz + vmsg + "\nSzerző: " + vszrz + "\nFeltöltve: " + ftlv
                params = MergeDicts(cItem, {"good_for_fav": False, "title": title, "url": url, "icon": icon, "desc": desc, "tps": "0"})
                self.addVideo(params)
            if searchMode:
                if lastItemId != "":
                    searchPattern = cItem.get("search_pattern", "")
                    lazyUrl = self.MAIN_URL + "/lazy/kereses/" + urllib.parse.quote_plus(searchPattern) + "?cacheId=" + urllib.parse.quote_plus(searchPattern) + "&lastItemId=" + urllib.parse.quote_plus(lastItemId) + "&itemCount=432&sort=0"
                    params = dict(cItem)
                    params.update({"title": _("Next page"), "url": lazyUrl, "category": "list_items", "search_mode": True, "desc": "Nyugi...\nVan még további tartalom, lapozz tovább!"})
                    self.addDir(params)
            elif channelMode:
                if lastItemId != "":
                    itemCount = self.cm.ph.getSearchGroups(url_ere, "itemCount=([0-9]+)")[0]
                    count = (int(itemCount) if itemCount else 0) + len(data)
                    channelUrl = url_ere.split("?")[0]
                    if "/lazy/csatornak/" not in channelUrl:
                        channelUrl = channelUrl.replace("/csatornak/", "/lazy/csatornak/")
                    lazyUrl = "%s?cacheId=&lastItemId=%s&itemCount=%s&sort=0" % (channelUrl, urllib.parse.quote_plus(lastItemId), count)
                    params = dict(cItem)
                    params.update({"title": _("Next page"), "url": lazyUrl, "category": "list_items", "channel_mode": True, "desc": "Nyugi...\nVan még további tartalom, lapozz tovább!"})
                    self.addDir(params)
            elif nextPage:
                params = dict(cItem)
                params.update({"title": _("Next page"), "page": page + 1, "desc": "Nyugi...\nVan még további tartalom, lapozz tovább!"})
                self.addDir(params)
        except Exception:
            return

    def getLinksForVideo(self, cItem):
        videoUrls = []
        baseUrl = strwithmeta(cItem["url"])
        sts, data = self.getPage(baseUrl)
        if not sts:
            return videoUrls
        url = self.cm.ph.getDataBeetwenMarkers(data, '"embedURL": "', '"', False)[1]
        if not url:
            return videoUrls
        url = url.replace("/v/", "?v=").replace("?autoplay=1", "&autoplay=0")
        uri = urlparser.decorateParamsFromUrl(url)
        protocol = uri.meta.get("iptv_proto", "")
        printDBG("Videa: protocol [%s]" % protocol)
        urlSupport = self.up.checkHostSupport(uri)
        if 1 == urlSupport:
            videoUrls.extend(self.up.getVideoLinkExt(uri))
        elif 0 == urlSupport and self._uriIsValid(uri):
            if protocol == "m3u8":
                videoUrls.extend(getDirectM3U8Playlist(uri, checkExt=False, checkContent=True))
            elif protocol == "f4m":
                videoUrls.extend(getF4MLinksWithMeta(uri))
            elif protocol == "mpd":
                videoUrls.extend(getMPDLinksWithMeta(uri, False))
            else:
                videoUrls.append({"name": "direct link", "url": uri})
        return videoUrls

    def getdvdsz(self, pu="", psz=""):
        if pu == "" or psz == "":
            return ""
        header = "Videa  v" + HOST_VERSION + "\n" if pu == "videa_kategoriak" else ""
        if self.aid:
            n_atnav = self.malvadst("1", "12", pu)
            if n_atnav != "":
                if pu == "videa_kategoriak":
                    header = "ID: " + n_atnav + "  |  Videa  v" + HOST_VERSION + "\n"
                else:
                    header = "ID: " + n_atnav + "\n"
        return header + psz

    def malvadst(self, i_md="", i_hgk="", i_mpu=""):
        uhe = "https://www.figyelmeztetes.hu/hely/sata/vansatdb.php"
        try:
            if i_md == "" or i_hgk == "" or i_mpu == "":
                return ""
            sts, data = self.cm.getPage(uhe, self.defaultParams, {"md": i_md, "hgk": i_hgk, "mpu": i_mpu})
            if not sts or len(data) == 0:
                return ""
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="div_a_div', "</div>")[1]
            if len(data) == 0:
                return ""
            for item in self.cm.ph.getAllItemsBeetwenMarkers(data, "<input", "/>"):
                if self.cm.ph.getSearchGroups(item, "id=['\"]([^\"']+?)['\"]")[0] == "vn":
                    return self.cm.ph.getSearchGroups(item, "value=['\"]([^\"']+?)['\"]")[0]
            return ""
        except Exception:
            return ""

    def malvadkiszrz(self):
        ukszrz = "https://www.figyelmeztetes.hu/hely/muta/mutasatdbki.php"
        try:
            sts, data = self.cm.getPage(ukszrz)
            if not sts or len(data) == 0:
                return []
            return self.cm.ph.getAllItemsBeetwenMarkers(data, "<div>", "</div>", False)
        except Exception:
            return []

    def listSearchResult(self, cItem, searchPattern, searchType):
        try:
            cItem = dict(cItem)
            cItem["url"] = self.vmkrs + "/" + urllib.parse.quote_plus(searchPattern) + "?page=1"
            cItem["search_pattern"] = searchPattern
            cItem["search_mode"] = True
            self.listItems(cItem)
        except Exception as e:
            printDBG("Videa search ERROR: listSearchResult [%s]" % str(e))
            printExc()

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        try:
            CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
            name = self.currItem.get("name", "")
            category = self.currItem.get("category", "")
            self.currList = []
            if name is None:
                self.listMainMenu({"name": "category"})
            elif category == "list_main":
                self.listMainItems(self.currItem)
            elif category == "list_second":
                self.listSecondItems(self.currItem)
            elif category == "list_items":
                self.listItems(self.currItem)
            elif category in ("search", "search_next_page"):
                cItem = dict(self.currItem)
                cItem.update({"search_item": False, "name": "category"})
                self.listSearchResult(cItem, searchPattern, searchType)
            elif category == "search_history":
                self.listsHistory({"name": "history", "category": "search", "tab_id": ""}, "desc", _("Type: "))
            else:
                return
            CBaseHostClass.endHandleService(self, index, refresh)
        except Exception:
            return


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, videa(), True, [])

    def withArticleContent(self, cItem):
        if cItem["type"] != "article":
            return False
        return True
