# -*- coding: utf-8 -*-
# Last Modified: 10.10.2026
# 10.10.2026 - host standard: video categories, "najnowsze" and "top" lists read from the site (the old kat* ids
#   are gone), CDA Premium with the site's access / category / sort filters and its json "load more" paging,
#   channel categories from the site's json (the old parser broke on "&oacute;"), channel folders with the
#   folder pager, First page / Jump / Next page, watched flag (channel -> folder -> video), downloaded marker,
#   favourites, sidecar, INFO (films: moviemeta + the site's text, clips: the video page's own data),
#   "Title (Year)" naming for films, covers with "//" urls fixed, links resolved through urlparser (parserCDA)
#   only when played, pages through getPageCFProtection (the search sits behind a Cloudflare check), login only
#   with the user's own account, default user agent
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, GetCookieDir, GetIconDir, ReadTextFile, WriteTextFile
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import normalizeMediathekTitle
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_binary
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
from Screens.MessageBox import MessageBox
from binascii import hexlify
from hashlib import md5
import os
import re
###################################################

config.plugins.iptvplayer.cda_searchsort = ConfigSelection(default="best", choices=[("best", "Best match"), ("date", _("Latest")), ("rate", _("Top rated")), ("alf", _("Sort A-Z"))])
config.plugins.iptvplayer.cda_login = ConfigLogin(default="", fixed_size=False)
config.plugins.iptvplayer.cda_password = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Username:"), config.plugins.iptvplayer.cda_login))
    optionList.append(getConfigListEntry(_("Password:"), config.plugins.iptvplayer.cda_password))
    optionList.append(getConfigListEntry(_("Sort by:"), config.plugins.iptvplayer.cda_searchsort))
    return optionList


def gettytul():
    return "https://www.cda.pl/"


VIDEO_ID_RE = re.compile(r"/video/([0-9a-zA-Z]+)")
FILM_TITLE_RE = re.compile(r"^(.+?)\s*\(((?:19|20)\d\d)\)\s*(.*)$")


class cda(GenericFolderWatchedScraperMixin, CBaseHostClass, CaptchaHelper):

    # stable identity of a row (views, counters and the next page state change)
    FAV_FIELDS = ("name", "category", "type", "url", "title", "raw_title", "icon", "desc", "meta_title", "meta_year")

    def __init__(self):
        printDBG("cda.__init__")
        CBaseHostClass.__init__(self, {"history": "cda.pl", "cookie": "cdapl.cookie"})
        self.MAIN_URL = "https://www.cda.pl/"
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/cdapl135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept": "text/html", "Referer": self.MAIN_URL})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.loggedIn = None
        self.login = ""
        self.password = ""
        self.watchedHelper = IPTVWatchedHelper("cdapl")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams = dict(addParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self.cm.iriToUri(url), addParams, post_data)

    def _icon(self, url):
        url = (url or "").strip()
        return self.getFullIconUrl(url) if url else ""

    def _videoUrl(self, url):
        # one form for every clip url: https://www.cda.pl/video/<id> (the lists add "/vfilm", http:// or "?...")
        m = VIDEO_ID_RE.search(url or "")
        return "%svideo/%s" % (self.MAIN_URL, m.group(1)) if m else url

    def _parseFilmTitle(self, title):
        # "Przeklęty Szpital (2026) Lektor PL" -> ("Przeklęty Szpital", "2026", "Lektor PL")
        m = FILM_TITLE_RE.match(title or "")
        if not m:
            return title, "", ""
        return m.group(1).strip(), m.group(2), m.group(3).strip(" -|")

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            if cItem.get("type") == "video":
                m = VIDEO_ID_RE.search(cItem.get("url", ""))
                return "video:%s" % m.group(1) if m else ""
            if cItem.get("category") in ("list_folders", "list_folder_sort", "list_folder_items"):
                url = re.sub(r"^https?://(?:www\.)?cda\.pl", "", cItem.get("url", "")).split("?")[0]
                url = re.sub(r"/vfilm(?:/\d+)?/?$", "", url)
                return "folder:%s" % url if url else ""
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("type") == "video":
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def getLinksForFavourite(self, fav_data):
        # rows of very old versions stored only the url
        if self.cm.isValidUrl(fav_data):
            return self.getLinksForVideo({"url": fav_data})
        return CBaseHostClass.getLinksForFavourite(self, fav_data)

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        MAIN_TAB = [{"category": "video_menu", "title": _("Videos"), "url": self.getFullUrl("/video")},
                    {"category": "premium", "title": "CDA Premium", "url": self.getFullUrl("/premium")},
                    {"category": "channels_cats", "title": _("Channels"), "url": self.getFullUrl("/partial/polecanekanaly_paski")}]
        self.listsTab(MAIN_TAB + self.searchItems(), cItem)

    def listVideoMenu(self, cItem):
        printDBG("cda.listVideoMenu")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        self.addDir(MergeDicts(cItem, {"good_for_fav": True, "category": "list_items", "title": "Wideo użytkowników", "url": self.getFullUrl("/video")}))
        for block in self.cm.ph.getAllItemsBeetwenMarkers(data, '<ul class="kategoryList"', "</ul>"):
            for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<a", "</a>"):
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]+)['"]''')[0])
                if "/video" not in url:
                    continue  # "Filmy pełnometrażowe" is CDA Premium (own menu entry)
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "txt"), ("</span", ">"), False)[1])
                count = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "count-category"), ("</span", ">"), False)[1])
                if title:
                    self.addDir(MergeDicts(cItem, {"good_for_fav": True, "category": "list_items", "title": title, "url": url, "desc": count.strip("()")}))

    ###################################################
    # clip lists (video portal, search)
    ###################################################
    def _addClip(self, url, title, icon, descTab):
        url = self._videoUrl(self.getFullUrl(url))
        if not title or "/video/" not in url:
            return False
        self.addVideo({"good_for_fav": True, "title": title, "url": url, "icon": self._icon(icon), "desc": "[/br]".join([x for x in descTab if x])})
        return True

    def _parseClips(self, data):
        count = 0
        seen = set()
        blocks = data.split('<div class="video-clip-wrapper">')[1:]
        for item in blocks:
            item = item.split("</label>", 1)[0]
            url = self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]*?/video/[^'"]+)['"]''')[0]
            if not url or url in seen:
                continue
            seen.add(url)
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<a", ">", "link-title-visit"), ("</a", ">"), False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''alt=['"]([^'"]+)['"]''')[0])
            duration = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "timeElem"), ("</span", ">"), False)[1])
            author = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<a", ">", "video-clip-info-link"), ("</a", ">"), False)[1])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''<label[^>]+title=['"]([^'"]+)['"]''')[0].replace("&lt;br /&gt;", "[/br]").replace("<br />", "[/br]"))
            icon = self.cm.ph.getSearchGroups(item, r'''<img[^>]+src=['"]([^'"]+)['"]''')[0]
            if self._addClip(url, title, icon, [" | ".join([x for x in (duration, author) if x]), desc]):
                count += 1
        if count:
            return count
        # "najnowsze" list
        for item in data.split('class="videoInfo"')[1:]:
            url = self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]*?/video/[^'"]+)['"]''')[0]
            if not url or url in seen:
                continue
            seen.add(url)
            img = self.cm.ph.getSearchGroups(item, r'''(<img[^>]+>)''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(img, r'''alt=['"]([^'"]+)['"]''')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<a", ">", "link-title-visit"), ("</a", ">"), False)[1])
            duration = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "timeElem"), ("</span", ">"), False)[1])
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "hd-ico-elem"), ("</span", ">"), False)[1])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(img, r'''title=['"]([^'"]+)['"]''')[0].replace("<br />", "[/br]"))
            icon = self.cm.ph.getSearchGroups(img, r'''src=['"]([^'"]+)['"]''')[0]
            if self._addClip(url, title, icon, [" | ".join([x for x in (duration, quality) if x]), desc]):
                count += 1
        return count

    def _pageTemplate(self, nextUrl, nextPage):
        # the url of the next page with its number replaced by {page} ("/video/p2", "/video/sport/2", "/p2?o=top")
        if not nextUrl:
            return ""
        tpl = re.sub(r"(/p?)%d(?=$|[/?])" % nextPage, r"\g<1>{page}", nextUrl.replace("{", "%7B").replace("}", "%7D"), count=1)
        return tpl if "{page}" in tpl else ""

    def listItems(self, cItem):
        printDBG("cda.listItems [%s]" % cItem.get("url", ""))
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        nextUrl = self.cm.ph.getSearchGroups(data, r'''class=['"]sbmBigNext[^'"]*['"][^>]+href=['"]([^'"]+)['"]''')[0]
        nextUrl = self.getFullUrl(nextUrl) if nextUrl else ""
        params = stripPagerKeys(dict(cItem))
        count = self._parseClips(data)
        if cItem.get("f_first_url"):
            # search: page 1 is the "/info/<pattern>" page, the next pages are the site's "/video/show/..." links
            params["url"] = cItem["f_first_url"]
            tpl = ""
        else:
            tpl = self._pageTemplate(nextUrl, page + 1)
        addPagingItems(self, params, page, bool(count) and bool(nextUrl), 0, tpl, None if tpl else {"url": nextUrl})
        if cItem.get("category") == "search_next_page" and not count and page == 1:
            SetIPTVPlayerLastHostError(_("No matching entries found."))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("cda.listSearchResult [%s] [%s]" % (searchPattern, searchType))
        # "/video/show/<pattern>" sits behind a Cloudflare check, "/info/<pattern>" (the site's own redirect target) not
        url = self.getFullUrl("/info/%s?s=%s" % (urllib_quote(searchPattern.strip(), safe=""), config.plugins.iptvplayer.cda_searchsort.value))
        if searchType and searchType != "all":
            url += "&duration=" + searchType
        self.listItems(MergeDicts(cItem, {"category": "search_next_page", "url": url, "f_first_url": url, "page": 1}))

    ###################################################
    # CDA Premium (films)
    ###################################################
    def listPremium(self, cItem):
        # access filter (premium / free) of the site; the categories and sort orders go along in the item
        printDBG("cda.listPremium")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        cats = [[_("All"), self.getFullUrl("/premium")]]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<ul class="kat-kino">', "</ul>")
        if tmp:
            for item in self.cm.ph.getAllItemsBeetwenMarkers(tmp[0], "<a", "</a>"):
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]+)['"]''')[0])
                title = self.cleanHtmlStr(item)
                if "/premium/" in url and title:
                    cats.append([title, url])
        sorts = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<select name="s"', "</select>", False)[1]
        for value, title in re.findall(r'''<option[^>]+value=['"]([^'"]+)['"][^>]*>([^<]+)''', tmp):
            sorts.append([self.cleanHtmlStr(title), value])
        access = [[_("All"), ""]]
        for value, title in re.findall(r'''name=['"]d\[\]['"]\s+value=['"](\d+)['"][^>]*data-label=['"]([^'"]+)['"]''', data):
            access.append([self.cleanHtmlStr(title), value])
        for title, value in access:
            self.addDir(MergeDicts(cItem, {"good_for_fav": False, "category": "premium_cats", "title": title, "f_access": value, "f_cats": cats, "f_sorts": sorts}))

    def listPremiumCats(self, cItem):
        for title, url in cItem.get("f_cats", []):
            self.addDir(MergeDicts(cItem, {"good_for_fav": False, "category": "premium_sort", "title": title, "url": url}))

    def listPremiumSort(self, cItem):
        sorts = cItem.get("f_sorts", []) or [[_("Latest"), "new"]]
        for title, value in sorts:
            params = dict(cItem)
            for key in ("f_cats", "f_sorts"):
                params.pop(key, None)
            query = ["sort=%s" % value]
            if cItem.get("f_access"):
                query.append("d=%s" % cItem["f_access"])
            params.update({"good_for_fav": True, "category": "premium_items", "title": title, "url": cItem["url"].split("?")[0] + "?" + "&".join(query)})
            self.addDir(params)

    def _addPremiumItems(self, data):
        count = 0
        for item in data.split('<span class="cover-area">')[1:]:
            url = self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]*?/video/[^'"]+)['"]''')[0]
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<a", ">", "kino-title"), ("</a", ">"), False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''alt=['"]([^'"]+)['"]''')[0])
            if not url or not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'''<img[^>]+src=['"]([^'"]+)['"]''')[0]
            plot = self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "description-cover-container"), ("<span", ">", "btn-more-desc"), False)[1]
            genres, plot = (plot.split("<br /><br />", 1) + [""])[:2] if "<br /><br />" in plot else ("", plot)
            access = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "cloud-gray"), ("</span", ">"), False)[1])
            name, year, lang = self._parseFilmTitle(title)
            desc = [" | ".join([x for x in (year, self.cleanHtmlStr(genres), lang, access) if x]), self.cleanHtmlStr(plot)]
            self.addVideo({"good_for_fav": True, "title": normalizeMediathekTitle(name, year=year, isMovie=True, lang=lang) if year else title,
                           "raw_title": title, "url": self._videoUrl(self.getFullUrl(url)), "icon": self._icon(icon),
                           "desc": "[/br]".join([x for x in desc if x]), "meta_title": name, "meta_year": year})
            count += 1
        return count

    def listPremiumItems(self, cItem):
        printDBG("cda.listPremiumItems [%s] page[%s]" % (cItem.get("url", ""), cItem.get("page", 1)))
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        nextParams = {}
        hasNext = False
        if page == 1:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
            tmp = self.cm.ph.getSearchGroups(data, r'''katalogLoadMore\([^,]+,\s*"([^"]+)"\s*,\s*"([^"]+)"''', 2)
            hasNext = tmp[0] != "" and 'id="loadMore' in data
            nextParams = {"f_load_cat": tmp[0], "f_load_sort": tmp[1]}
            data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="covers-container">', 'id="loadMore', False)[1]
        else:
            params = dict(self.defaultParams)
            params["header"] = MergeDicts(self.HEADER, {"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json", "Referer": cItem["url"]})
            params["raw_post_data"] = True
            post = json_dumps({"jsonrpc": "2.0", "method": "katalogLoadMore", "params": [page, cItem.get("f_load_cat", "all"), cItem.get("f_load_sort", "new"), {}], "id": page})
            sts, data = self.getPage(self.getFullUrl("/premium"), params, post)
            if not sts:
                return
            try:
                data = json_loads(data)["result"]
                hasNext = data.get("status") == "continue"
                data = ensure_str(data.get("html", ""))
            except Exception:
                printExc()
                return
        count = self._addPremiumItems(data)
        params = stripPagerKeys(dict(cItem))
        addPagingItems(self, params, page, bool(count) and hasNext, 0, "", nextParams or None)

    ###################################################
    # channels
    ###################################################
    def _getChannelCats(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return [], {}
        raw = self.cm.ph.getSearchGroups(data, r"polecani_partnerzy\s*=\s*(\{.*?\});\s*\n")[0]
        try:
            cats = json_loads(raw)
            # the order of the site (the dict of py2 has none)
            order = re.findall(r'"([^"]+)"\s*:\s*\[\s*\{', raw)
            order = [ensure_str(json_loads('"%s"' % x)) for x in order]
            return order, dict((ensure_str(k), v) for k, v in cats.items())
        except Exception:
            printExc()
        return [], {}

    def listChannelsCategories(self, cItem):
        printDBG("cda.listChannelsCategories")
        order, cats = self._getChannelCats(cItem)
        for title in order:
            if title in cats:
                self.addDir(MergeDicts(cItem, {"good_for_fav": False, "category": "list_channels", "title": title, "f_cat": title, "desc": ""}))

    def listChannels(self, cItem):
        printDBG("cda.listChannels [%s]" % cItem.get("f_cat", ""))
        order, cats = self._getChannelCats(cItem)
        for item in cats.get(cItem.get("f_cat", ""), []):
            login = ensure_str(item.get("login", ""))
            if not login:
                continue
            icon = ensure_str(item.get("thumb", "") or "")
            if icon and not icon.startswith("http"):
                icon = "https://" + icon.lstrip("/")
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_folders", "title": self.cleanHtmlStr(ensure_str(item.get("tytul", "") or login)),
                         "url": self.getFullUrl("/%s/vfilm" % login), "icon": icon, "desc": ensure_str(item.get("video_count", "") or "")})

    def listFolders(self, cItem):
        printDBG("cda.listFolders [%s]" % cItem["url"])
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "navigation_foldery"), ("<div", ">", "panel-footer"))[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, "<a", "</a>"):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'''href=['"]([^'"]+)['"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "folder-title"), ("</span", ">"), False)[1]) or self.cleanHtmlStr(item)
            count = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "item-file"), ("</span", ">"), False)[1])
            if url and title:
                self.addDir(MergeDicts(cItem, {"good_for_fav": True, "category": "list_folder_sort", "title": title, "url": url, "desc": count.strip("() ")}))

    def listFolderSort(self, cItem):
        sorts = [("", _("Sort A-Z")), ("sortby=name&order=desc", _("Sort Z-A")), ("sortby=created&order=desc", "Newest first"), ("sortby=created&order=asc", "Oldest first")]
        for query, title in sorts:
            self.addDir(MergeDicts(cItem, {"good_for_fav": True, "category": "list_folder_items", "title": title, "f_sort": query, "url": cItem["url"].split("?")[0]}))

    def listFolderItems(self, cItem):
        printDBG("cda.listFolderItems [%s]" % cItem["url"])
        try:
            page = max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            page = 1
        query = "?type=pliki" + ("&" + cItem["f_sort"] if cItem.get("f_sort") else "")
        base = re.sub(r"/\d+$", "", cItem["url"].split("?")[0].rstrip("/"))
        url = base + ("/%d" % page if page > 1 else "") + query
        sts, data = self.getPage(url)
        if not sts:
            return
        nextUrl = ph.getattr(ph.find(data, ("<a", ">", "btn-primary block"))[1], "href")
        count = 0
        for item in self.cm.ph.getAllItemsBeetwenNodes(data, ("<div", ">", "list-when-small"), ("</div", ">")):
            tmp = self.cm.ph.getDataBeetwenNodes(item, ("<a", ">", "link-title"), ("</a", ">"))[1]
            vurl = self.cm.ph.getSearchGroups(tmp, r'''\shref=['"]([^'"]+)['"]''')[0]
            title = self.cleanHtmlStr(tmp)
            duration = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<", ">", "time-inline"), ("<", ">"), False)[1])
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<span", ">", "hd-ico-elem"), ("</span", ">"), False)[1])
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''title=['"]([^'"]+)['"]''')[0].replace("&lt;br /&gt;", "[/br]"))
            icon = self.cm.ph.getSearchGroups(item, r'''\ssrc=['"]([^'"]+)['"]''')[0]
            if self._addClip(vurl, title, icon, [" | ".join([x for x in (duration, quality) if x]), desc]):
                count += 1
        params = stripPagerKeys(dict(cItem))
        params["url"] = base
        addPagingItems(self, params, page, bool(count) and "/%d?" % (page + 1) in nextUrl, 0, "")

    ###################################################
    # links / INFO
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("cda.getLinksForVideo [%s]" % url)
        if not self.cm.isValidUrl(url):
            return []
        # resolved by parserCDA (qualities, login cookie of this host) when the link is played
        linksTab = [{"name": "cda.pl", "url": self._videoUrl(url), "need_resolve": 1}]
        return applySidecarToLinks(linksTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, url):
        printDBG("cda.getVideoLinks [%s]" % url)
        self.tryTologin()
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecarFromUrlMeta(url, IsSidecarEnabled()))

    def _parseVideoPage(self, data):
        def meta(name):
            return self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'''<meta[^>]+(?:property|itemprop|name)=['"]%s['"][^>]+content=['"]([^'"]*)['"]''' % name)[0])
        info = {"title": meta("og:title"), "desc": meta("og:description") or meta("description"), "icon": meta("og:image")}
        date = meta("uploadDate")[:10]
        info["released"] = date if re.match(r"\d{4}-\d\d-\d\d$", date) else ""
        m = re.match(r"T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", meta("duration"))
        info["duration"] = ""
        if m and any(m.groups()):
            h, mi, s = [int(x or 0) for x in m.groups()]
            info["duration"] = "%d:%02d:%02d" % (h, mi, s) if h else "%d:%02d" % (mi, s)
        return info

    def getArticleContent(self, cItem):
        printDBG("cda.getArticleContent [%s]" % cItem.get("url", ""))
        title = cItem.get("raw_title", cItem.get("title", ""))
        text = cItem.get("desc", "")
        icon = cItem.get("icon", "")
        otherInfo = {}
        if cItem.get("type") == "video" and self.cm.isValidUrl(cItem.get("url", "")):
            sts, data = self.getPage(cItem["url"])
            if sts:
                info = self._parseVideoPage(data)
                title = info["title"] or title
                text = info["desc"] if len(info["desc"]) >= len(text) else text  # some clips have only a word or two there
                icon = info["icon"] or icon
                for key in ("released", "duration"):
                    if info[key]:
                        otherInfo[key] = info[key]
        if cItem.get("meta_title"):
            meta = getMeta("movie", cItem["meta_title"], cItem.get("meta_year", ""), maxYearDiff=1)
            if meta:
                text = meta.get("plot") or text
                icon = meta.get("poster") or icon
                otherInfo.update(meta.get("info", {}))
        return [{"title": title, "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    ###################################################
    # login (the user's own account from the host settings, empty = off)
    ###################################################
    def tryTologin(self):
        printDBG("cda.tryTologin start")
        login = ensure_str(config.plugins.iptvplayer.cda_login.value)
        password = ensure_str(config.plugins.iptvplayer.cda_password.value)
        if self.loggedIn is not None and self.login == login and self.password == password:
            return self.loggedIn
        self.login = login
        self.password = password
        loginCookie = GetCookieDir("cda.pl.login")
        self.loggedIn = False
        if "" == login.strip() or "" == password.strip():
            if os.path.isfile(loginCookie):
                # the account was removed from the settings - drop its session
                rm(loginCookie)
                rm(self.COOKIE_FILE)
            return False

        loginHash = ensure_str(hexlify(md5(ensure_binary("%s@***@%s" % (login, password))).digest()))
        sts, data = self.getPage(self.getMainUrl())
        if sts and "/logout" in data and loginHash == ReadTextFile(loginCookie)[1].strip():
            self.loggedIn = True
            return True
        rm(loginCookie)
        rm(self.COOKIE_FILE)

        actionUrl = self.getFullUrl("/login")
        sts, data = self.getPage(actionUrl)
        msgTab = [_("Login failed.")]
        sitekey = ""
        for _try in range(2):
            if not sts:
                break
            r = ph.search(data, r'''name=['"]r['"][^>]+?value=['"]([^'"]+?)['"]''', flags=ph.I)[0]
            post_data = {"r": r, "username": login, "password": password, "login": "zaloguj"}
            params = dict(self.defaultParams)
            params["header"] = MergeDicts(self.HEADER, {"Referer": actionUrl})
            for item in ph.findall(data, ("<form", ">", "/login"), "</form>", flags=ph.I):
                if "data-sitekey" in item:
                    sitekey = ph.search(item, r'''data\-sitekey=['"]([^'"]+?)['"]''')[0]
                    break
            if sitekey != "":
                token, errorMsgTab = self.processCaptcha(sitekey, self.cm.meta.get("url", actionUrl))
                if token != "":
                    post_data["g-recaptcha-response"] = token
            sts, data = self.getPage(actionUrl, params, post_data)
            if sts and "/logout" in data:
                self.loggedIn = True
                break
            if sts and sitekey == "" and "data-sitekey" in data:
                continue  # the site asks for the captcha only now
            if sts:
                msgTab.append(ph.clean_html(ph.find(data, ("<p", ">", "error-form"), "</p>", flags=0)[1]))
            break
        if self.loggedIn:
            WriteTextFile(loginCookie, loginHash)
        else:
            self.sessionEx.waitForFinishOpen(MessageBox, "\n".join([x for x in msgTab if x]), type=MessageBox.TYPE_ERROR, timeout=10)
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("cda.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        self.tryTologin()

        name = self.currItem.get("name", None)
        category = self.currItem.get("category", "")
        printDBG("cda.handleService: name[%s], category[%s]" % (name, category))
        self.currList = []

        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "video_menu":
            self.listVideoMenu(self.currItem)
        elif category in ("list_items", "search_next_page"):
            self.listItems(self.currItem)
        elif category == "premium":
            self.listPremium(self.currItem)
        elif category == "premium_cats":
            self.listPremiumCats(self.currItem)
        elif category == "premium_sort":
            self.listPremiumSort(self.currItem)
        elif category == "premium_items":
            self.listPremiumItems(self.currItem)
        elif category == "channels_cats":
            self.listChannelsCategories(self.currItem)
        elif category == "list_channels":
            if self.currItem.get("f_cat"):
                self.listChannels(self.currItem)
        elif category == "list_folders":
            self.listFolders(self.currItem)
        elif category == "list_folder_sort":
            self.listFolderSort(self.currItem)
        elif category == "list_folder_items":
            self.listFolderItems(self.currItem)
        elif category == "search":
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
        CHostBase.__init__(self, cda(), True, [CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cdapl")

    def withArticleContent(self, cItem):
        return cItem.get("type", "") == "video"

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append(("Any duration", "all"))
        searchTypesOptions.append(("Short (up to 5 min)", "krotkie"))
        searchTypesOptions.append(("Medium (over 20 min)", "srednie"))
        searchTypesOptions.append(("Long (over 60 min)", "dlugie"))
        return searchTypesOptions
