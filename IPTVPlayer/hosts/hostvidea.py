# -*- coding: utf-8 -*-
###################################################
# 2026-08-24 by WhiteWolf
###################################################
HOST_VERSION = "1.5"
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetLogoDir, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs import ph

###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigYesNo, ConfigDirectory, getConfigListEntry
from os.path import normpath
import os
import re
import urllib.parse
import random
import datetime
import time
import zlib
import base64
import codecs
import traceback

try:
    import subprocess

    FOUND_SUB = True
except Exception:
    FOUND_SUB = False
from Tools.Directories import resolveFilename, SCOPE_PLUGINS
from Screens.MessageBox import MessageBox

###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.videa_id = ConfigYesNo(default=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("id:", config.plugins.iptvplayer.videa_id))
    return optionList


###################################################


def gettytul():
    return "Videa"


class videa(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "videa", "cookie": "videa.cookie"})
        self.USER_AGENT = "User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
        self.HEADER = self.cm.getDefaultHeader()
        self.DEFAULT_ICON_URL = "https://www.figyelmeztetes.hu/videa_logo.jpg"
        self.MAIN_URL = "https://videa.hu"
        self.vmkrs = self.MAIN_URL + "/kereses"
        self.aid = config.plugins.iptvplayer.videa_id.value
        self.aid_ki = ""
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
            else:
                return urllib.parse.urljoin(baseUrl, url)

        addParams["cloudflare_params"] = {"domain": self.up.getDomain(baseUrl), "cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT, "full_url_handle": _getFullUrl}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data

    def listMainMenu(self, cItem):
        try:
            if not self.ebbtit():
                return
            tab_kat = "videa_kategoriak"
            desc_kat = self.getdvdsz(tab_kat, "Videa kategóriáinak megjelenítése...")
            tab_csat = "videa_csatornak"
            desc_csat = self.getdvdsz(tab_csat, "Videa csatornáinak megjelenítése...")
            MAIN_CAT_TAB = [{"category": "list_main", "title": "Kategóriák", "tab_id": tab_kat, "desc": desc_kat}, {"category": "list_main", "title": "Csatornák", "tab_id": tab_csat, "desc": desc_csat}] + self.searchItems()
            self.listsTab(MAIN_CAT_TAB, {"name": "category"})
            vtb = self.malvadnav(cItem, "7", "12", "0", "14")
            if len(vtb) > 0:
                for item in vtb:
                    item["category"] = "list_third"
                    self.addVideo(item)
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
            elif tabID == "videa_ajanlott":
                self.Vdajnzttt(cItem, tabID)
            else:
                return
        except Exception:
            return

    def Vdktgrk(self, cItem, tabID):
        mlt = []
        try:
            url_ere = self.MAIN_URL
            sts, data = self.getPage(url_ere)
            if not sts:
                return
            if len(data) == 0:
                return
            data = data.split('class="category-item">')
            if len(data) > 0:
                del data[0]
            if len(data) == 0:
                return
            for item in data:
                url = self.cm.ph.getSearchGroups(item, "href=['\"]([^\"^']+?)['\"]")[0]
                if url.startswith("/"):
                    url = url_ere + url
                if not self.cm.isValidUrl(url):
                    continue
                title = self.cm.ph.getSearchGroups(item, "text\"[>]([^\"^']+?)[<]")[0].capitalize()
                desc = self.getdvdsz(url, '"' + title + '" kategória videóinak megjelenítése...')
                icon = ""
                params = MergeDicts(cItem, {"good_for_fav": False, "category": "list_second", "title": title, "url": url, "icon": icon, "desc": desc, "tab_id": tabID})
                mlt.append(params)
            if len(mlt) > 0:
                random.shuffle(mlt)
                for ipv in mlt:
                    self.addDir(ipv)
        except Exception:
            return

    def Vdcstrnk(self, cItem, tabID):
        mlt = []
        try:
            url_ere = self.MAIN_URL
            sts, data = self.getPage(url_ere)
            if not sts:
                return
            if len(data) == 0:
                return
            data = self.cm.ph.getDataBeetwenMarkers(data, 'title list-opener">', "</ul>")[1]
            if len(data) == 0:
                return
            data = data.split("<li>")
            if len(data) > 0:
                del data[0]
            if len(data) == 0:
                return
            for item in data:
                url = self.cm.ph.getSearchGroups(item, "href=['\"]([^\"^']+?)['\"]")[0]
                if url.startswith("/"):
                    url = url_ere + url
                if not self.cm.isValidUrl(url):
                    continue
                title = self.cm.ph.getSearchGroups(item, "text\"[>]([^\"^']+?)[<]")[0].capitalize()
                desc = self.getdvdsz(url, '"' + title + '"  csatorna videóinak megjelenítése...')
                icon = ""
                params = MergeDicts(cItem, {"good_for_fav": False, "category": "list_second", "title": title, "url": url, "icon": icon, "desc": desc, "tab_id": tabID})
                mlt.append(params)
            if len(mlt) > 0:
                random.shuffle(mlt)
                for ipv in mlt:
                    self.addDir(ipv)
        except Exception:
            return

    def Vdajnzttt(self, cItem, tabID):
        try:
            tab_ams = "videa_ajnlt_musor"
            desc_ams = self.getdvdsz(tab_ams, "Ajánlott, nézett tartalmak megjelenítése műsorok szerint...")
            tab_adt = "videa_ajnlt_datum"
            desc_adt = self.getdvdsz(tab_adt, "Ajánlott, nézett tartalmak megjelenítése dátum szerint...")
            tab_anzt = "videa_ajnlt_nezettseg"
            desc_anzt = self.getdvdsz(tab_anzt, "Ajánlott, nézett tartalmak megjelenítése nézettség szerint...")
            A_CAT_TAB = [{"category": "list_third", "title": "Dátum szerint", "tab_id": tab_adt, "desc": desc_adt}, {"category": "list_third", "title": "Műsorok szerint", "tab_id": tab_ams, "desc": desc_ams}, {"category": "list_third", "title": "Nézettség szerint", "tab_id": tab_anzt, "desc": desc_anzt}]
            self.listsTab(A_CAT_TAB, cItem)
        except Exception:
            return

    def listSecondItems(self, cItem):
        try:
            tabID = cItem.get("tab_id", "")
            if tabID == "videa_kategoriak":
                url = cItem["url"]
                VK_CAT_TAB = [{"category": "list_items", "title": "Feltöltés ideje szerint", "url": url + "?page=1", "desc": ""}, {"category": "list_items", "title": "Nézettség szerint", "url": url + "?popular&page=1", "desc": ""}, {"category": "list_items", "title": "Legrégebbi elöl", "url": url + "?oldest&page=1", "desc": ""}]
                self.listsTab(VK_CAT_TAB, cItem)
            elif tabID == "videa_csatornak":
                url = cItem["url"]
                VCS_CAT_TAB = [{"category": "list_items", "title": "Feltöltés ideje szerint", "url": url + "?page=1", "desc": ""}, {"category": "list_items", "title": "Nézettség szerint", "url": url + "?popular&page=1", "desc": ""}, {"category": "list_items", "title": "Legrégebbi elöl", "url": url + "?oldest&page=1", "desc": ""}]
                self.listsTab(VCS_CAT_TAB, cItem)
            else:
                return
        except Exception:
            return

    def listThirdItems(self, cItem):
        try:
            tabID = cItem.get("tab_id", "")
            if tabID == "videa_ajnlt_musor":
                self.Vajnltmsr(cItem)
            elif tabID == "videa_ajnlt_datum":
                self.Vajnltdtm(cItem)
            elif tabID == "videa_ajnlt_nezettseg":
                self.Vajnltnztsg(cItem)
            else:
                return
        except Exception:
            return

    def Vajnltmsr(self, cItem):
        try:
            vtb = self.malvadnav(cItem, "3", "12", "0")
            if len(vtb) > 0:
                for item in vtb:
                    self.addVideo(item)
        except Exception:
            return

    def Vajnltdtm(self, cItem):
        vtb = []
        try:
            vtb = self.malvadnav(cItem, "4", "12", "0")
            if len(vtb) > 0:
                for item in vtb:
                    self.addVideo(item)
        except Exception:
            return

    def Vajnltnztsg(self, cItem):
        try:
            vtb = self.malvadnav(cItem, "5", "12", "0")
            if len(vtb) > 0:
                for item in vtb:
                    self.addVideo(item)
        except Exception:
            return

    def listItems(self, cItem):
        try:
            url_ere = cItem["url"]
            page = cItem.get("page", 1)
            searchMode = cItem.get("search_mode", False)
            if not searchMode:
                if page > 0 and "page=" in url_ere:
                    idx1 = url_ere.rfind("page=")
                    if -1 < idx1:
                        url_ere = url_ere[:idx1].strip()
                        url_ere = url_ere + "page=" + str(page)
            sts, data = self.getPage(url_ere)
            if not sts:
                return
            if len(data) == 0:
                return
            nextPage = False
            if not searchMode:
                nextPage = self.cm.ph.getSearchGroups(data, "next\"\\shref=['\"]([^\"^']+?)['\"]")[0]
                if nextPage:
                    nextPage = True
            data = data.split('class="col video-item">')
            if len(data) > 0:
                del data[0]
            lastItemId = ""
            for item in data:
                itemId = self.cm.ph.getSearchGroups(item, """data-item-id=['"]([^"']+?)['"]""")[0]
                if itemId != "":
                    lastItemId = itemId
                url = self.cm.ph.getSearchGroups(item, "<a\\shref=['\"]([^\"^']+?)['\"]\\sa")[0]
                if not self.cm.isValidUrl(url):
                    continue
                icon = self.cm.ph.getSearchGroups(item, """data-image=['"]([^"^']+?)['"]""")[0]
                if icon == "":
                    icon = self.DEFAULT_ICON_URL
                else:
                    if icon.startswith("/"):
                        icon = self.MAIN_URL + icon
                vszrz = self.cm.ph.getSearchGroups(item, """aria-label=['"]([^"^']+?)['"].+\n.+href""")[0]
                if not vszrz:
                    vszrz = self.cm.ph.getSearchGroups(item, """uploader.{,50}[>]([^"^']+?)[<]/a""")[0]
                if not vszrz:
                    vszrz = self.cm.ph.getSearchGroups(item, """tagok[/]([^"^']+?)[-"]""")[0]
                if len(self.vszkzrs) > 0:
                    if self.check_string(vszrz, self.vszkzrs):
                        continue
                vhz = self.cm.ph.getSearchGroups(item, """length"[>]([0-9:]+?)[<]""")[0]
                vmsg = self.cm.ph.getDataBeetwenMarkers(item, 'div class="hd">', "</div>", False)[1]
                if vmsg != "":
                    vmsg = "  |  " + vmsg
                title = self.cm.ph.getSearchGroups(item, """aria-label=['"]([^"^']+?)['"].+\n.+div""")[0]
                if title == "":
                    continue
                ftlv = self.cm.ph.getSearchGroups(item, """uploaded-at"[>]([^"^']+?)[<]""")[0]
                desc = title + "\n" + "Időtartam: " + vhz + vmsg + "\nSzerző: " + vszrz + "\nFeltöltve: " + ftlv
                params = MergeDicts(cItem, {"good_for_fav": False, "title": title, "url": url, "icon": icon, "desc": desc, "tps": "0"})
                self.addVideo(params)
            if searchMode:
                if lastItemId != "":
                    searchPattern = cItem.get("search_pattern", "")
                    lazyUrl = self.MAIN_URL + "/lazy/kereses/" + urllib.parse.quote_plus(searchPattern) + "?cacheId=" + urllib.parse.quote_plus(searchPattern) + "&lastItemId=" + urllib.parse.quote_plus(lastItemId) + "&itemCount=432&sort=0"
                    params = dict(cItem)
                    params.update({"title": _("Next page"), "url": lazyUrl, "category": "list_items", "search_mode": True, "desc": "Nyugi...\nVan még további tartalom, lapozz tovább!"})
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

        printDBG("PROTOCOL [%s] " % protocol)

        urlSupport = self.up.checkHostSupport(uri)
        if 1 == urlSupport:
            retTab = self.up.getVideoLinkExt(uri)
            videoUrls.extend(retTab)
        elif 0 == urlSupport and self._uriIsValid(uri):
            if protocol == "m3u8":
                retTab = getDirectM3U8Playlist(uri, checkExt=False, checkContent=True)
                videoUrls.extend(retTab)
            elif protocol == "f4m":
                retTab = getF4MLinksWithMeta(uri)
                videoUrls.extend(retTab)
            elif protocol == "mpd":
                retTab = getMPDLinksWithMeta(uri, False)
                videoUrls.extend(retTab)
            else:
                videoUrls.append({"name": "direct link", "url": uri})
        return videoUrls

    def cpve(self, cfpv=""):
        vissza = False
        try:
            if cfpv != "":
                mk = cfpv
                if mk != "":
                    vissza = True
        except Exception:
            return False
        return vissza

    def check_string(self, string, substring_list):
        for substring in substring_list:
            if substring in string:
                return True
        return False

    def getdvdsz(self, pu="", psz=""):
        bv = ""
        if pu != "" and psz != "":
            n_atnav = self.malvadst("1", "12", pu)
            if n_atnav != "" and self.aid:
                if pu == "videa_kategoriak":
                    self.aid_ki = "ID: " + n_atnav + "  |  Videa  v" + HOST_VERSION + "\n"
                else:
                    self.aid_ki = "ID: " + n_atnav + "\n"
            else:
                if pu == "videa_kategoriak":
                    self.aid_ki = "Videa  v" + HOST_VERSION + "\n"
                else:
                    self.aid_ki = ""
            bv = self.aid_ki + psz
        return bv

    def malvadst(self, i_md="", i_hgk="", i_mpu=""):
        uhe = zlib.decompress(base64.b64decode("eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUL04sSdQvS8wD0ilJegUZBQD8FROZ")).decode("utf-8")
        pstd = {"md": i_md, "hgk": i_hgk, "mpu": i_mpu}
        t_s = ""
        temp_vn = ""
        temp_vni = ""
        try:
            if i_md != "" and i_hgk != "" and i_mpu != "":
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
                if not sts:
                    return t_s
                if len(data) == 0:
                    return t_s
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="div_a_div', "</div>")[1]
                if len(data) == 0:
                    return t_s
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<input", "/>")
                if len(data) == 0:
                    return t_s
                for item in data:
                    t_i = self.cm.ph.getSearchGroups(item, "id=['\"]([^\"^']+?)['\"]")[0]
                    if t_i == "vn":
                        temp_vn = self.cm.ph.getSearchGroups(item, "value=['\"]([^\"^']+?)['\"]")[0]
                    elif t_i == "vni":
                        temp_vni = self.cm.ph.getSearchGroups(item, "value=['\"]([^\"^']+?)['\"]")[0]
                if temp_vn != "":
                    t_s = temp_vn
            return t_s
        except Exception:
            return t_s

    def malvadnav(self, cItem, i_md="", i_hgk="", i_mptip="", i_mpdb=""):
        uhe = zlib.decompress(base64.b64decode("eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUzy0tSQQTxYklKUl6BRkFABGoFBk=")).decode("utf-8")
        t_s = []
        try:
            if i_md != "" and i_hgk != "" and i_mptip != "":
                if i_hgk != "":
                    i_hgk = base64.b64encode(i_hgk).replace("\n", "").strip()
                if i_mptip != "":
                    i_mptip = base64.b64encode(i_mptip).replace("\n", "").strip()
                if i_mpdb != "":
                    i_mpdb = base64.b64encode(i_mpdb).replace("\n", "").strip()
                pstd = {"md": i_md, "hgk": i_hgk, "mptip": i_mptip, "mpdb": i_mpdb}
                sts, data = self.cm.getPage(uhe, self.defaultParams, pstd)
                if not sts:
                    return t_s
                if len(data) == 0:
                    return t_s
                data = self.cm.ph.getDataBeetwenMarkers(data, '<div id="div_a1_div"', '<div id="div_a2_div"')[1]
                if len(data) == 0:
                    return t_s
                data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="d_sor_d"', "</div>")
                if len(data) == 0:
                    return t_s
                for temp_item in data:
                    temp_data = self.cm.ph.getAllItemsBeetwenMarkers(temp_item, "<span", "</span>")
                    if len(temp_data) == 0:
                        return t_s
                    for item in temp_data:
                        t_vp = self.cm.ph.getSearchGroups(item, "class=['\"]([^\"^']+?)['\"]")[0]
                        if t_vp == "c_sor_u":
                            temp_u = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_u">', "</span>", False)[1]
                            if temp_u != "":
                                temp_u = base64.b64decode(temp_u)
                        if t_vp == "c_sor_t":
                            temp_t = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_t">', "</span>", False)[1]
                            if temp_t != "":
                                temp_t = base64.b64decode(temp_t)
                        if t_vp == "c_sor_i":
                            temp_i = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_i">', "</span>", False)[1]
                            if temp_i != "":
                                temp_i = base64.b64decode(temp_i)
                        if t_vp == "c_sor_l":
                            temp_l = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_l">', "</span>", False)[1]
                            if temp_l != "":
                                temp_l = base64.b64decode(temp_l)
                        if t_vp == "c_sor_n":
                            temp_n = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_n">', "</span>", False)[1]
                            if temp_n != "":
                                temp_n = base64.b64decode(temp_n)
                        if t_vp == "c_sor_tip":
                            temp_tp = self.cm.ph.getDataBeetwenMarkers(item, '<span class="c_sor_tip">', "</span>", False)[1]
                            if temp_tp != "":
                                temp_tp = base64.b64decode(temp_tp)
                    if temp_u == "" and temp_t == "":
                        continue
                    if temp_n == "":
                        temp_n = "1"
                    params = MergeDicts(cItem, {"good_for_fav": False, "url": temp_u, "title": temp_t, "icon": temp_i, "desc": temp_l, "nztsg": temp_n, "tps": temp_tp})
                    t_s.append(params)
            return t_s
        except Exception:
            return []

    def malvadkiszrz(self):
        bv = []
        ukszrz = zlib.decompress(base64.b64decode("eJzLKCkpsNLXLy8v10vLTK9MzclNrSpJLUkt1sso1c9IzanUzy0tSQQTxYklKUnZmXoFGQUAO30U7Q==")).decode("utf-8")
        try:
            sts, data = self.cm.getPage(ukszrz)
            if not sts:
                return []
            if len(data) == 0:
                return []
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<div>", "</div>", False)
            if len(data) == 0:
                return []
            for item in data:
                bv.append(item)
            return bv
        except Exception:
            return []

    def ebbtit(self):
        return True

    def listSearchResult(self, cItem, searchPattern, searchType):
        try:
            cItem = dict(cItem)
            cItem["url"] = self.vmkrs + "/" + urllib.parse.quote_plus(searchPattern) + "?page=1"
            cItem["search_pattern"] = searchPattern
            cItem["search_mode"] = True
            self.listItems(cItem)
        except Exception:
            return

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
            elif category == "list_third":
                self.listThirdItems(self.currItem)
            elif category == "list_items":
                self.listItems(self.currItem)
            elif category in ["search", "search_next_page"]:
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
