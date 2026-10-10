# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.10.2026 - host standard: the "newest" / "recently viewed" lists answer only to ajax requests now (the
#   X-Requested-With header was missing - empty body, json error), First page / Next page, films and music as
#   VIDEO / AUDIO rows with watched flag (user -> directory -> file), downloaded marker, favourites, sidecar,
#   INFO (moviemeta for file names with a year or SxxExx, else the file's own data), "Title (Year)" /
#   "Show - SxxExx" naming, links resolved through urlparser (parserFREEDISC) only when played, local default
#   icon, default user agent, login only with the user's own account
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm, GetTmpDir, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle, parseSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from Components.config import config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
from Screens.MessageBox import MessageBox
from copy import deepcopy
import re
###################################################

config.plugins.iptvplayer.freediscpl_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.freediscpl_password = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("e-mail") + ":", config.plugins.iptvplayer.freediscpl_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.freediscpl_password))
    return optionList


def gettytul():
    return "https://freedisc.pl/"


FILE_ID_RE = re.compile(r",f-(\d+)")
FILE_EXT_RE = re.compile(r"\.(?:avi|mkv|mp4|mpe?g|mov|wmv|flv|webm|m4v|ts|mp3|m4a|aac|ogg|flac|wma|wav)$", re.I)
YEAR_RE = re.compile(r"^(.+?)[\s._(\[-]+((?:19|20)\d\d)(?:[\s._)\]-]|$)")


class FreeDiscPL(GenericFolderWatchedScraperMixin, CBaseHostClass):
    TYPES = {"movies": 7, "music": 6}
    # stable identity of a row
    FAV_FIELDS = ("name", "category", "type", "url", "title", "raw_title", "icon", "desc", "f_type", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "FreeDiscPL.tv", "cookie": "FreeDiscPL.cookie"})
        self.MAIN_URL = "https://freedisc.pl/"
        self.SEARCH_URL = self.MAIN_URL + "search/get"
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/freediscpl135.png")
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HTTP_HEADER.update({"Accept": "text/html", "Referer": self.MAIN_URL})
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*; q=0.01"})
        self.defaultParams = {"with_metadata": True, "ignore_http_code_ranges": [(410, 410), (404, 404)], "header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_CAT_TAB = [{"category": "list_filters", "title": "Najnowsze publiczne pliki użytkowników", "url": self.MAIN_URL + "explore/start/get_tabs_pages_data/%s/newest/"},
                             {"category": "list_filters", "title": "Ostatnio przeglądane pliki", "url": self.MAIN_URL + "explore/start/get_tabs_pages_data/%s/visited/"}]
        self.FILTERS_TAB = [{"title": _("Movies"), "filter": "movies"}, {"title": _("Music"), "filter": "music"}]
        self.loggedIn = None
        self.login = ""
        self.password = ""
        self.treeCache = {}
        self.watchedHelper = IPTVWatchedHelper("freediscpl")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def _ajaxParams(self, referer=None, json=False):
        params = dict(self.defaultParams)
        params["header"] = dict(self.AJAX_HEADER)
        if json:
            params["raw_post_data"] = True
            params["header"]["Content-Type"] = "application/json; charset=UTF-8"
        if referer:
            params["header"]["Referer"] = referer
        return params

    def getPage(self, url, params=None, post_data=None):
        if not params:
            params = dict(self.defaultParams)
        sts, data = self.cm.getPage(url, params, post_data)
        if sts and data.meta.get("status_code", 0) in [410, 404]:
            tmp = re.sub(r"<!--[\s\S]*?-->", "", data)
            if "sitekey" in tmp:
                errorMsg = [_("Link protected with google recaptcha v2.")]
                errorMsg.append(_('Please visit "%s" and confirm that you are human.') % self.getMainUrl())
                if not self.loggedIn:
                    errorMsg.append(_("Please register and set login and password in the host configuration, to solve this problems permanently."))
                errorMsg = "\n".join(errorMsg)
                GetIPTVNotify().push(errorMsg, "info", 10)
                SetIPTVPlayerLastHostError(errorMsg)
            elif "captcha" in tmp:
                self._solveCaptcha(tmp)
        return sts, data

    def _solveCaptcha(self, tmp):
        # the site's own image captcha on its 404/410 page
        paramsUrl = dict(self.defaultParams)
        paramsUrl["header"] = dict(paramsUrl["header"])
        cUrl = self.cm.meta.get("url", self.getMainUrl())
        tmp = ph.find(tmp, ("<div", ">", "footer-404"), "</form>")[1]
        captchaTitle = self.cleanHtmlStr(tmp.split("<form", 1)[0])
        sendLabel = self.cleanHtmlStr(ph.getattr(ph.find(tmp, ("<input", ">", "Button"), flags=(ph.IGNORECASE | ph.START_E))[1], "value"))
        captchaLabel = ("%s %s" % (sendLabel, self.cleanHtmlStr(ph.getattr(tmp, "placeholder")))).strip() or _("Captcha")
        captchaTitle = "%s\n\n%s" % (captchaTitle, captchaLabel) if captchaTitle else captchaLabel
        imgUrl = self.getFullIconUrl(ph.search(tmp, ph.IMAGE_SRC_URI_RE)[1], cUrl)
        actionUrl = self.getFullUrl(ph.getattr(tmp, "action"), cUrl) or cUrl
        captcha_post_data = {}
        for it in ph.findall(tmp, "<input", ">", flags=ph.IGNORECASE):
            name = ph.getattr(it, "name")
            if name:
                captcha_post_data[name] = ph.getattr(it, "value").strip()
        params = dict(self.defaultParams)
        params.update({"maintype": "image", "subtypes": ["jpeg", "png"], "check_first_bytes": [b"\xff\xd8", b"\xff\xd9", b"\x89\x50\x4e\x47"],
                       "header": dict(self.HTTP_HEADER, Accept="image/png,image/*;q=0.8,*/*;q=0.5")})
        filePath = GetTmpDir(".iptvplayer_captcha.jpg")
        rm(filePath)
        ret = self.cm.saveWebFile(filePath, imgUrl.replace("&amp;", "&"), params)
        if not ret.get("sts"):
            errorMsg = _('Fail to get "%s".') % imgUrl
            SetIPTVPlayerLastHostError(errorMsg)
            GetIPTVNotify().push(errorMsg, "error", 10)
            return
        params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
        params.update({"accep_label": _("Send"), "title": captchaLabel, "status_text": captchaTitle, "status_text_hight": 200, "with_accept_button": True, "list": []})
        item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
        item.update({"label_size": (660, 110), "input_size": (680, 25), "icon_path": filePath, "title": _("Answer")})
        item["input"]["text"] = ""
        params["list"].append(item)
        params["vk_params"] = {"invert_letters_case": True}
        retArg = self.sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
        if retArg and len(retArg) and retArg[0]:
            captcha_post_data["captcha"] = retArg[0][0]
            paramsUrl["header"]["Referer"] = cUrl
            self.cm.getPage(actionUrl, paramsUrl, captcha_post_data)

    def _fileMeta(self, name):
        # "Dragon Ball Super Film 02 - Super Hero (2022) Dubbing.mkv" -> title, year ("movie");
        # "I tak po prostu__And Just Like That.S03E03.PL.avi" -> show, SxxExx ("tv")
        # (Polish and original title are often joined by "__" - the lookup uses the original one)
        clean = FILE_EXT_RE.sub("", (name or "").strip())
        season, episode = parseSxxExx(clean)
        if season and episode:
            show = re.split(r"[\s._\[(-]*S\d+\s*[ .:/x_-]*E\d+[\])]?", clean, 1, flags=re.I)[0]
            label = re.sub(r"[._]+", " ", show).strip(" -[(")
            if not label:
                # "[S03e15] Descentc vf4 av.mp4": no show name before SxxExx - keep the file's own title
                return {}
            return {"meta_type": "tv", "label": label, "meta_title": re.sub(r"[._]+", " ", show.split("__")[-1]).strip(" -[("),
                    "meta_year": "", "sxe": "S%02dE%02d" % (int(season), int(episode))}
        m = YEAR_RE.match(clean)
        if m:
            return {"meta_type": "movie", "label": re.sub(r"[._]+", " ", m.group(1)).strip(" -(["),
                    "meta_title": re.sub(r"[._]+", " ", m.group(1).split("__")[-1]).strip(" -(["), "meta_year": m.group(2), "sxe": ""}
        return {}

    def _addFile(self, params, fileType):
        title = params["title"]
        meta = self._fileMeta(title) if fileType == "7" else {}
        if meta:
            params["raw_title"] = title
            if IsMediaNamingNormalized() and meta["label"]:
                if meta["sxe"]:
                    params["title"] = "%s - %s" % (meta["label"], meta["sxe"])
                else:
                    params["title"] = normalizeMediathekTitle(meta["label"], year=meta["meta_year"], isMovie=True)
            params.update({"meta_type": meta["meta_type"], "meta_title": meta["meta_title"], "meta_year": meta["meta_year"]})
        params["f_type"] = fileType
        if fileType == "7":
            self.addVideo(params)
        elif fileType == "6":
            self.addAudio(params)

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("type") in ("video", "audio"):
                m = FILE_ID_RE.search(cItem.get("url", ""))
                return "video:%s" % m.group(1) if m else ""
            if cItem.get("category") == "list_dir" and cItem.get("f_user_id"):
                return "folder:%s/%s" % (cItem["f_user_id"], cItem.get("f_dir_id", ""))
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("type") in ("video", "audio"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG("FreeDiscPL.getLinksForFavourite")
        self.tryTologin()
        if self.cm.isValidUrl(fav_data):
            return self.getLinksForVideo({"url": fav_data})
        try:
            return self.getLinksForVideo(json_loads(fav_data))
        except Exception:
            printExc()
        return []

    ###################################################
    # lists
    ###################################################
    def listItems(self, cItem):
        printDBG("FreeDiscPL.listItems")
        fileType = self.TYPES.get(cItem.get("filter", ""), -1)
        if fileType == -1:
            return
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        # the site counts its pages from 0
        url = cItem["url"] % fileType + "%d" % (page - 1)
        sts, data = self.getPage(url, self._ajaxParams(self.getMainUrl()))
        if not sts:
            return
        count = 0
        hasNext = False
        try:
            data = json_loads(data)["response"]
            data = ensure_str(data.get("html_visited" if "/visited/" in url else "html_newest", ""))
            hasNext = 'data-page="%d"' % page in data
            for item in data.split("<div class='imageDisplay'>")[1:]:
                fileUrl = self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]+?,f-\d+[^'"]*)['"]''')[0]
                if fileUrl == "":
                    continue
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "fileTitle"), ("</div", ">"), False)[1])
                if not title:
                    title = FILE_EXT_RE.sub("", self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''title=['"]([^'"]+)['"]''')[0]))
                user = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "userNick"), ("</div", ">"), False)[1])
                fileName = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''title=['"]([^'"]+)['"]''')[0])
                icon = self.cm.ph.getSearchGroups(item, r'''url\(['"]([^'"]+?)['"]''')[0]
                fileTypeTag = self.cm.ph.getSearchGroups(item, r"file_icon_(\d+)")[0]
                params = {"good_for_fav": True, "title": title, "url": self.getFullUrl(fileUrl), "icon": self.getFullIconUrl(icon),
                          "desc": "[/br]".join([x for x in (fileName, user) if x])}
                self._addFile(params, fileTypeTag)
                count += 1
        except Exception:
            printExc()
        addPagingItems(self, stripPagerKeys(dict(cItem)), page, bool(count) and hasNext)

    def listSearchItems(self, cItem):
        printDBG("FreeDiscPL.listSearchItems cItem[%s]" % (cItem))
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        pattern = cItem.get("f_search_pattern", "")
        sType = cItem.get("f_search_type", "")
        post_data = {"search_phrase": pattern, "search_type": sType, "search_saved": 0, "pages": 0, "limit": 0}
        if page > 1:
            post_data["search_page"] = page - 1
        referer = self.getMainUrl() + "search/%s/%s" % (sType, urllib_quote(pattern))
        sts, data = self.getPage(self.SEARCH_URL, self._ajaxParams(referer, True), json_dumps(post_data))
        if not sts or not data.strip():
            return  # 10.10.2026: an empty 404 outside Poland (like the file pages)
        count = 0
        hasNext = False
        try:
            data = json_loads(data)["response"]
            logins = data["logins_translated"]
            translated = data["directories_translated"]
            for item in data["data_files"]["data"]:
                fileType = ensure_str(str(item.get("type_fk", "")))
                if fileType not in ("7", "6"):
                    continue
                userItem = logins[str(item["user_id"])]
                dirItem = translated[str(item["parent_id"])]
                nameUrl = ensure_str(item["name_url"])
                url = "/%s,f-%s,%s" % (ensure_str(userItem["url"]), item["id"], nameUrl)
                desc = " | ".join([ensure_str(item["date_add_format"]), ensure_str(item["size_format"])])
                desc += "[/br]" + (_("Added by: %s, directory: %s") % (ensure_str(userItem["display"]), ensure_str(dirItem["name"])))
                params = {"good_for_fav": True, "title": self.cleanHtmlStr(ensure_str(item["name"])), "url": self.getFullUrl(url),
                          "icon": "https://img.freedisc.pl/photo/%s/7/2/%s.png" % (item["id"], nameUrl) if fileType == "7" else "", "desc": desc}
                self._addFile(params, fileType)
                # the uploader's root folder and the file's folder
                self.addDir({"name": "category", "good_for_fav": True, "category": "list_dir", "title": "@%s" % ensure_str(userItem["display"]),
                             "url": self.getFullUrl("/%s,d-%s,%s" % (ensure_str(userItem["url"]), userItem["userRootDirID"], ensure_str(userItem["url"]))),
                             "f_user_id": ensure_str(userItem["url"]), "f_dir_id": str(userItem["userRootDirID"]), "desc": desc})
                count += 1
            hasNext = int(data.get("pages", 0) or 0) > page
        except Exception:
            printExc()
        addPagingItems(self, stripPagerKeys(dict(cItem)), page, bool(count) and hasNext)

    def listDir(self, cItem):
        printDBG("FreeDiscPL.listDir cItem[%s]" % (cItem))
        userId = cItem.get("f_user_id", "")
        dirId = cItem.get("f_dir_id", "")
        params = self._ajaxParams(cItem["url"])
        try:
            dirIcon = self.getFullIconUrl("/static/img/icons/big_dir.png")
            if userId not in self.treeCache:
                self.treeCache = {}
                sts, data = self.getPage(self.getFullUrl("/directory/directory_data/get_tree/%s" % userId), params)
                if not sts:
                    return
                self.treeCache[userId] = json_loads(data)["response"]["data"]
            tree = self.treeCache[userId]
            # sub folders first
            dirsTab = [x for x in tree.get(dirId, {}).values() if x.get("type") == "d" and x.get("id") not in ["0", dirId]]
            dirsTab.sort(key=lambda item: item["name"])
            for item in dirsTab:
                desc = ["Katalogów: %s" % item["dir_count"], "Plików: %s" % item["file_count"]]
                self.addDir({"name": "category", "good_for_fav": True, "category": "list_dir", "title": self.cleanHtmlStr(ensure_str(item["name"])),
                             "url": self.getFullUrl("/%s,d-%s,%s" % (userId, item["id"], ensure_str(item["name_url"]))), "icon": dirIcon,
                             "f_user_id": userId, "f_dir_id": str(item["id"]), "desc": "[/br]".join(desc)})
            # then the files
            sts, data = self.getPage(self.getFullUrl("/directory/directory_data/get/%s/%s" % (userId, dirId)), params)
            if not sts:
                return
            data = json_loads(data)["response"]["data"].get("data", {})
            filesTab = [x for x in data.values() if x.get("type") == "f" and x.get("type_fk") in ["7", "6"]]
            filesTab.sort(key=lambda item: item["name"])
            for item in filesTab:
                nameUrl = ensure_str(item["name_url"])
                icon = "https://img.freedisc.pl/photo/%s/7/2/%s.png" % (item["id"], nameUrl) if item["type_fk"] == "7" else ""
                params = {"good_for_fav": True, "title": self.cleanHtmlStr(ensure_str(item["name"])), "url": self.getFullUrl("/%s,f-%s,%s" % (userId, item["id"], nameUrl)),
                          "icon": icon, "desc": " | ".join([ensure_str(item["date_add_format"]), ensure_str(item["size_format"])])}
                self._addFile(params, item["type_fk"])
        except Exception:
            printExc()

    ###################################################
    # links / INFO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("FreeDiscPL.getLinksForVideo [%s]" % cItem.get("url", ""))
        url = cItem.get("url", "")
        if not self.cm.isValidUrl(url):
            return []
        linksTab = [{"name": "freedisc.pl", "url": url, "need_resolve": 1}]
        return applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, url):
        printDBG("FreeDiscPL.getVideoLinks [%s]" % url)
        self.tryTologin()
        urlTab = self.up.getVideoLinkExt(url)
        if not urlTab:
            SetIPTVPlayerLastHostError(_("Content not available"))
        return decorateResolvedLinkItems(urlTab, sidecarFromUrlMeta(url, IsSidecarEnabled()))

    def getArticleContent(self, cItem):
        printDBG("FreeDiscPL.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("raw_title", cItem.get("title", ""))
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), maxYearDiff=1)
            if meta:
                text = "%s[/br][/br]%s" % (meta.get("plot", ""), text) if meta.get("plot") else text
                icon = meta.get("poster") or icon
                otherInfo.update(meta.get("info", {}))
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    ###################################################
    # login (the user's own account from the host settings, empty = off)
    ###################################################
    def tryTologin(self):
        printDBG("FreeDiscPL.tryTologin start")
        login = config.plugins.iptvplayer.freediscpl_login.value
        password = config.plugins.iptvplayer.freediscpl_password.value
        if self.loggedIn is not None and self.login == login and self.password == password:
            return self.loggedIn
        self.login = login
        self.password = password
        if "" == login.strip() or "" == password.strip():
            self.loggedIn = False
            return False
        sts, data = self.getPage(self.getMainUrl())
        if not sts or 200 != data.meta.get("status_code", 0):
            return None
        self.loggedIn = False
        errMsg = []
        sts, data = self.getPage(self.getFullUrl("/account/signin_set"), self._ajaxParams(self.getMainUrl(), True),
                                 json_dumps({"email_login": login, "password_login": password, "remember_login": 1, "provider_login": ""}))
        if not sts:
            return None
        try:
            data = json_loads(data)
            if data["success"] is True:
                self.loggedIn = True
            else:
                errMsg = [self.cleanHtmlStr(ensure_str(data["response"]["info"]))]
        except Exception:
            printExc()
        if self.loggedIn is not True:
            self.sessionEx.open(MessageBox, _("Login failed.") + "\n" + "\n".join(errMsg), type=MessageBox.TYPE_ERROR, timeout=10)
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("FreeDiscPL.handleService start")
        self.tryTologin()
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("FreeDiscPL.handleService: name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MAIN_CAT_TAB + self.searchItems(), {"name": "category"})
        elif category == "list_filters":
            cItem = dict(self.currItem)
            cItem["category"] = "list_items"
            for item in self.FILTERS_TAB:
                self.addDir(dict(cItem, good_for_fav=True, **item))
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category in ("list_items2", "list_search"):
            self.listSearchItems(self.currItem)
        elif category == "list_dir":
            self.listDir(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category", "category": "list_search", "url": self.SEARCH_URL,
                          "f_search_pattern": searchPattern, "f_search_type": searchType})
            self.listSearchItems(cItem)
            if not self.currList:
                SetIPTVPlayerLastHostError(_("No matching entries found."))
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, FreeDiscPL(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("freediscpl")

    def withArticleContent(self, cItem):
        return cItem.get("type", "") in ("video", "audio")

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Movies"), "movies"))
        searchTypesOptions.append((_("Music"), "music"))
        return searchTypesOptions
