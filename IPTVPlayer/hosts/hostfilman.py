# -*- coding: utf-8 -*-
# Last Modified: 23.04.2026 - damagic

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute

###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox

###################################################
# FOREIGN import
###################################################
import re
import base64

try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, ConfigSelection, getConfigListEntry

###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.filman_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.filman_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Filman login:", config.plugins.iptvplayer.filman_login))
    optionList.append(getConfigListEntry("Filman hasło:", config.plugins.iptvplayer.filman_password))
    return optionList


###################################################


def gettytul():
    return "https://filman.cc/"


class Filman(CBaseHostClass, CaptchaHelper):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Filman.online", "cookie": "filman.cookie"})
        config.plugins.iptvplayer.cloudflare_user = ConfigText(default="Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0", fixed_size=False)
        self.USER_AGENT = config.plugins.iptvplayer.cloudflare_user.value
        self.MAIN_URL = "https://filman.cc/"
        self.DEFAULT_ICON_URL = "https://filman.cc/public/dist/images/logo.png"
        self.HTTP_HEADER = {"User-Agent": self.USER_AGENT, "DNT": "1", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Encoding": "gzip, deflate", "Accept-Language": "pl,en-US;q=0.7,en;q=0.3", "Referer": self.getMainUrl(), "Origin": self.getMainUrl(), "Connection": "keep-alive", "Upgrade-Insecure-Requests": "1"}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Accept": "application/json, text/javascript, */*; q=0.01"})

        self.cacheMovieFilters = {"cats": [], "sort": [], "years": [], "az": []}
        self.cacheLinks = {}
        self.defaultParams = {"header": self.HTTP_HEADER, "with_metadata": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

        self.loggedIn = None
        self.login = ""
        self.password = ""
        self.loginMessage = ""

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)

        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        if data.meta.get("cf_user", self.USER_AGENT) != self.USER_AGENT:
            self.__init__()
        return sts, data

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def listMainMenu(self, cItem):
        printDBG("Filman.listMainMenu")

        MAIN_CAT_TAB = [
            {"category": "list_items", "title": "Filmy Premiery", "url": self.getFullUrl("/filmy/sort:premiere/")},
            {"category": "list_items", "title": "Filmy Nowe Linki", "url": self.getFullUrl("/filmy/")},
            {"category": "list_items", "title": "Filmy Oceny na Filmweb", "url": self.getFullUrl("/filmy/sort:filmweb/")},
            {"category": "list_items", "title": "Seriale Nowe Odcinki", "url": self.getFullUrl("/seriale/")},
            {"category": "list_sort", "title": _("Series"), "url": self.getFullUrl("/seriale/")},
            {"category": "list_items", "title": _("Children"), "url": self.getFullUrl("/dla-dzieci-pl/")},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    ###################################################
    def _fillMovieFilters(self, cItem):
        self.cacheMovieFilters = {"cats": [], "sort": [], "years": [], "az": []}

        sts, data = self.getPage(cItem["url"])
        if not sts:
            return

        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="filter-sort"', "</ul>", False)[1]
        dat = re.compile('<li[^>]+?data-sort="([^"]+?)".*?<a[^>]*?>(.+?)</a>').findall(dat)
        for item in dat:
            self.cacheMovieFilters["sort"].append({"title": self.cleanHtmlStr(item[1]), "sort": item[0]})

        dat = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="filter-category"', "</ul>", False)[1]
        dat = re.compile('<li[^>]+?data-id="([^"]+?)".*?<a[^>]*?>(.+?)</a>').findall(dat)
        for item in dat:
            self.cacheMovieFilters["cats"].append({"title": self.cleanHtmlStr(item[1]), "url": cItem["url"] + "category:%s/" % item[0]})

    ###################################################
    def listMovieFilters(self, cItem, category):
        printDBG("Filman.listMovieFilters")

        filter = cItem["category"].split("_")[-1]
        self._fillMovieFilters(cItem)
        if len(self.cacheMovieFilters[filter]) > 0:
            filterTab = []
            filterTab.extend(self.cacheMovieFilters[filter])
            self.listsTab(filterTab, cItem, category)

    def listsTab(self, tab, cItem, category=None):
        printDBG("Filman.listsTab")
        for item in tab:
            params = dict(cItem)
            if None is not category:
                params["category"] = category
            params.update(item)
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("Filman.listItems %s" % cItem)
        page = cItem.get("page", 1)

        url = cItem["url"]
        sort = cItem.get("sort", "")
        if sort not in url:
            url = url + sort

        if page > 1:
            if "?" in url:
                url += "&"
            else:
                url += "?"
            url = url + "page={0}".format(page)

        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(data.meta["url"])

        is_search = "phrase=" in cItem["url"]

        if is_search:
            items = []

            pattern = r'<div class="col-xs-6 col-sm-3 col-lg-2">.*?</div>\s*</div>'
            matches = re.findall(pattern, data, re.DOTALL)

            for match in matches:
                items.append(match)

            printDBG("Filman.listItems search found %d items" % len(items))
        else:
            content_data = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "wrapper"), ("<footer", ">"))[1]

            item_list_data = self.cm.ph.getDataBeetwenNodes(content_data, ("<div", ">", "item-list"), ("<div", ">", "text-center"))[1]
            if not item_list_data:
                item_list_data = self.cm.ph.getDataBeetwenNodes(content_data, ("<div", ">", "item-list"), ("</div", ">"))[1]

            if item_list_data:
                items = item_list_data.split('<div class="col-xs-6 col-sm-3 col-lg-2">')[1:]
                for i in range(len(items)):
                    items[i] = '<div class="col-xs-6 col-sm-3 col-lg-2">' + items[i]
            else:
                items = []

        for item in items:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, """href=['"]([^"^']+?)['"]""")[0])
            if url == "":
                continue

            img_data = self.cm.ph.getDataBeetwenNodes(item, ("<img", ">"), ("/>", ">"))[1]
            if not img_data:
                img_data = item
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(img_data, """src=['"]([^"^']+?)['"]""")[0])

            title = self.cm.ph.getSearchGroups(item, """title=['"]([^"^']+?)['"]""")[0]
            if not title:
                title = self.cm.ph.getSearchGroups(item, """data-title=['"]([^"^']+?)['"]""")[0]
            title = title.replace("&quot;", '"').replace("&amp;", "&")

            desc = self.cm.ph.getSearchGroups(item, """data-text=['"]([^"^']+?)['"]""")[0]

            year = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "film_year"), ("</div", ">"))[1])

            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "quality-version"), ("</div", ">"), False)[1])

            rating = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<div", ">", "rate"), ("</div", ">"))[1])

            desc_parts = []
            if year:
                desc_parts.append(_("Year: ") + year)
            if rating:
                desc_parts.append(_("Rating: ") + rating)
            if quality:
                desc_parts.append(_("Quality:") + " " + quality)
            if desc:
                desc_parts.append(desc)

            full_desc = "[/br]".join(desc_parts)

            if "/s/" in url or "/serial/" in url:
                params = {"good_for_fav": True, "category": "list_series", "url": url, "title": title, "desc": full_desc, "icon": icon}
                self.addDir(params)
            else:
                params = {"good_for_fav": True, "url": url, "title": title, "desc": full_desc, "icon": icon}
                self.addVideo(params)

        nextPage = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "pagination"), ("</u", ">"))[1]
        if "" != self.cm.ph.getSearchGroups(nextPage, "page=(%s)[^0-9]" % (page + 1))[0]:
            params = dict(cItem)
            params.update({"title": _("Next page"), "page": page + 1})
            self.addDir(params)

    def listSeries(self, cItem):
        printDBG("Filman.listSeries %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        self.setMainUrl(data.meta["url"])

        data = self.cm.ph.getDataBeetwenNodes(data, ("<ul", ">", "episode-list"), ("<hr", ">"))[1]
        if data:
            data = data.split("<span")
            for sitem in data:
                tmp = self.cm.ph.getAllItemsBeetwenNodes(sitem, ("<li", ">"), ("</li", ">"))
                for item in tmp:
                    url = self.getFullUrl(self.cm.ph.getSearchGroups(item, """href=['"]([^"^']+?)['"]""")[0])
                    if url == "":
                        continue
                    title = self.cleanHtmlStr(item)
                    params = {"good_for_fav": True, "url": url, "title": title, "icon": cItem["icon"]}
                    self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Filman.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        url = self.getFullUrl("/search?phrase=%s") % urllib_quote_plus(searchPattern)
        params = {"name": "category", "category": "list_items", "good_for_fav": False, "url": url}
        self.listItems(params)

    def rot13(self, s):
        result = []
        for c in s:
            if 'a' <= c <= 'z':
                result.append(chr((ord(c) - ord('a') + 13) % 26 + ord('a')))
            elif 'A' <= c <= 'Z':
                result.append(chr((ord(c) - ord('A') + 13) % 26 + ord('A')))
            else:
                result.append(c)
        return ''.join(result)

    def decodeEmbedUrl(self, encoded_string):
        try:
            decoded_base64 = ensure_str(base64.b64decode(encoded_string))
            decoded_rot13 = self.rot13(decoded_base64)
            return decoded_rot13
        except:
            return ""

    def getHostNameFromUrl(self, url):
        try:
            host = re.search(r'https?://([^/]+)', url).group(1)
            host = host.replace('www.', '')
            return host.split('.')[0]
        except:
            return "filman"

    def resolveEmbedUrl(self, embedUrl):
        printDBG("Filman.resolveEmbedUrl [%s]" % embedUrl)

        params = dict(self.defaultParams)
        params["header"] = dict(params["header"])
        params["header"]["Referer"] = "https://filman.cc/"

        sts, data = self.getPage(embedUrl, params)
        if not sts:
            return embedUrl

        finalUrl = ""

        pattern = r'''var\s+_e\s*=\s*['"]([^'"]+)['"]'''
        encoded_var = self.cm.ph.getSearchGroups(data, pattern)[0]
        if encoded_var:
            decoded_url = self.decodeEmbedUrl(encoded_var)
            if decoded_url:
                finalUrl = decoded_url

        if not finalUrl:
            iframe_src = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src=["\']([^"\']+)["\']')[0]
            if iframe_src:
                finalUrl = iframe_src

        if finalUrl and not finalUrl.startswith("http"):
            finalUrl = self.getFullUrl(finalUrl)

        return finalUrl if finalUrl else embedUrl

    def getLinksForVideo(self, cItem):
        printDBG("Filman.getLinksForVideo [%s]" % cItem)

        cacheKey = cItem["url"]
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        params = dict(self.defaultParams)
        params["header"] = dict(params["header"])

        cUrl = cItem["url"]
        url = cItem["url"]

        retTab = []

        params["header"]["Referer"] = cUrl
        sts, data = self.getPage(url, params)
        if not sts:
            return []

        cUrl = data.meta["url"]
        self.setMainUrl(cUrl)

        links_section = self.cm.ph.getDataBeetwenNodes(data, ("<table", ">", "links"), ("</table", ">"))[1]
        if links_section:
            rows = self.cm.ph.getAllItemsBeetwenNodes(links_section, ("<tr", ">"), ("</tr", ">"))

            for row in rows:
                if "<th" in row:
                    continue

                player_data = self.cm.ph.getDataBeetwenNodes(row, ("<td", ">", "link-to-video"), ("</td", ">"))[1]
                if not player_data:
                    continue

                iframe_data = self.cm.ph.getSearchGroups(player_data, r'''data-iframe=['"]([^"^']+?)['"]''')[0]
                playerUrl = ""
                if iframe_data:
                    try:
                        decoded = ensure_str(base64.b64decode(iframe_data))
                        try:
                            player_data_json = json.loads(decoded)
                            playerUrl = player_data_json.get("src", "")
                        except:
                            playerUrl = decoded
                    except:
                        playerUrl = ""

                if not playerUrl:
                    playerUrl = self.cm.ph.getSearchGroups(player_data, """href=['"]([^"^']+?)['"]""")[0]

                if playerUrl and not playerUrl.startswith("http"):
                    playerUrl = self.getFullUrl(playerUrl)

                if not playerUrl:
                    continue

                tds = self.cm.ph.getAllItemsBeetwenNodes(row, ("<td", ">"), ("</td", ">"))
                version = ""
                quality = ""
                if len(tds) > 2:
                    version = self.cleanHtmlStr(tds[1])
                    quality = self.cleanHtmlStr(tds[2])

                resolved_url = self.resolveEmbedUrl(playerUrl)
                host_name = self.getHostNameFromUrl(resolved_url)
                name = host_name
                if version:
                    name += " - " + version
                if quality:
                    name += " - " + quality

                retTab.append({"name": name, "url": strwithmeta(resolved_url, {"Referer": url}), "need_resolve": 1})

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("Filman.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)

        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if baseUrl in self.cacheLinks[key][idx]["url"]:
                        if not self.cacheLinks[key][idx]["name"].startswith("*"):
                            self.cacheLinks[key][idx]["name"] = "*" + self.cacheLinks[key][idx]["name"] + "*"
                        break

        return self.up.getVideoLinkExt(baseUrl)

    def getArticleContent(self, cItem):
        printDBG("Filman.getArticleContent [%s]" % cItem)
        itemsList = []

        sts, data = self.cm.getPage(cItem["url"])
        if not sts:
            return []

        title = cItem["title"]
        icon = cItem.get("icon", "")
        desc = cItem.get("desc", "")

        desc = self.cm.ph.getDataBeetwenNodes(data, ("<p", ">", "description"), ("</p", ">"))[1]

        if title == "":
            title = cItem["title"]
        if icon == "":
            icon = cItem.get("icon", "")
        if desc == "":
            desc = cItem.get("desc", "")

        return [{"title": self.cleanHtmlStr(title), "text": self.cleanHtmlStr(desc), "images": [{"title": "", "url": self.getFullUrl(icon)}], "other_info": {"custom_items_list": itemsList}}]

    def tryTologin(self):
        printDBG("tryTologin start")

        if None is self.loggedIn or self.login != config.plugins.iptvplayer.filman_login.value or self.password != config.plugins.iptvplayer.filman_password.value:

            sts, data = self.getPage(self.getFullUrl("/logowanie"))
            if not sts:
                return False

            if sts and "/wylogowanie" not in data:
                self.login = config.plugins.iptvplayer.filman_login.value
                self.password = config.plugins.iptvplayer.filman_password.value

                self.cm.clearCookie(self.COOKIE_FILE, ["__cfduid", "cf_clearance"])

                self.loggedIn = False

                if "" == self.login.strip() or "" == self.password.strip():
                    return False

                cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["PHPSESSID"])
                printDBG("tryTologin cookieHeader [%s]" % cookieHeader)

                post_data = {"login": self.login, "password": self.password, "remember": "on", "submit": ""}

                httpParams = dict(self.defaultParams)
                httpParams["header"] = dict(httpParams["header"])
                httpParams["header"]["Referer"] = self.getFullUrl("/logowanie")

                sitekey = ""
                if "data-sitekey" in data:
                    sitekey = self.cm.ph.getSearchGroups(data, r'data\-sitekey="([^"]+?)"')[0]

                if sitekey != "":
                    token, errorMsgTab = self.processCaptcha(sitekey, self.cm.meta["url"])
                    if token != "":
                        post_data["g-recaptcha-response"] = token

                sts, data = self.getPage(self.getFullUrl("/logowanie"), httpParams, post_data)
                sts, data = self.getPage(self.getFullUrl("/logowanie"))

            if sts and "/wylogowanie" in data:
                self.loggedIn = True
            else:
                if sts:
                    message = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "alert"), ("</div", ">"))[1])
                else:
                    message = ""
                self.sessionEx.open(MessageBox, _("Login failed.") + "\n" + message, type=MessageBox.TYPE_ERROR, timeout=10)
                printDBG("tryTologin failed")
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")

        self.tryTologin()

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        mode = self.currItem.get("mode", "")

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

        if name is None and category == "":
            self.listMainMenu({"name": "category"})
        elif "list_cats" == category:
            self.listMovieFilters(self.currItem, "list_sort")
        elif "list_years" == category:
            self.listMovieFilters(self.currItem, "list_sort")
        elif "list_az" == category:
            self.listMovieFilters(self.currItem, "list_sort")
        elif "list_sort" == category:
            self.listMovieFilters(self.currItem, "list_items")
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_series":
            self.listSeries(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Filman(), True, [])

    def withArticleContent(self, cItem):
        return True
