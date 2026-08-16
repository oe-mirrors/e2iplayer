# -*- coding: utf-8 -*-
# Last modified: 9/5/2026
# cimalina Host (Created By Dr HYTHAM MAHMOUD)

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

import re

try:
    import json
except Exception:
    json = None

try:
    import base64
except Exception:
    base64 = None

try:
    basestring
except NameError:
    basestring = str

try:
    from urllib.parse import quote_plus as urllib_quote_plus
except ImportError:
    from urllib import quote_plus as urllib_quote_plus

try:
    from html import unescape as html_unescape
except Exception:
    try:
        from HTMLParser import HTMLParser

        html_unescape = HTMLParser().unescape
    except Exception:

        def html_unescape(txt):
            return txt


config.plugins.iptvplayer.cimalina_proxy = ConfigSelection(default="None", choices=[("None", _("None")), ("proxy_1", _("Alternative proxy server (1)")), ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.cimalina_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.cimalina_proxy))
    if config.plugins.iptvplayer.cimalina_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.cimalina_alt_domain))
    return optionList


def gettytul():
    return "CimaLina"


class CimaLina(CBaseHostClass):
    DOMAIN_CACHE = None

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cimalina", "cookie": "cimalina.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "https://up6.cc/2026/05/177764060279971.png"

        self.HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Encoding": "gzip, deflate", "Connection": "keep-alive", "Accept-Language": "en-US,en;q=0.9,ar;q=0.8,en-GB;q=0.7", "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7", "DNT": 1}

        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest"})

        self.MEGAMAX_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"

        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE, "return_data": True}

        self.cacheLinks = {}
        self.cacheMegamax = {}
        self.cacheHostNames = {}
        self.cacheArticles = {}
        self.cacheCatItems = {}
        self.cachePages = {}
        self.homePageData = None

    def getProxy(self):
        proxy = config.plugins.iptvplayer.cimalina_proxy.value
        if proxy != "None":
            if proxy == "proxy_1":
                try:
                    proxy = config.plugins.iptvplayer.alternativeproxy1.value
                except Exception:
                    proxy = None
            else:
                try:
                    proxy = config.plugins.iptvplayer.alternativeproxy2.value
                except Exception:
                    proxy = None
        else:
            proxy = None
        return proxy

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        else:
            addParams = dict(addParams)

        for k, v in self.defaultParams.items():
            if k not in addParams:
                addParams[k] = v

        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})

        cacheKey = None
        canCache = post_data is None and addParams.get("header", {}) == self.HEADER
        if canCache:
            cacheKey = str(baseUrl)
            if cacheKey in self.cachePages:
                return True, self.cachePages[cacheKey]

        sts, data = self.cm.getPage(baseUrl, addParams, post_data)
        if sts and canCache and data:
            self.cachePages[cacheKey] = data
        return sts, data

    def _getHostNameCached(self, url):
        url = self._normUrl(url)
        if not url:
            return ""
        if url in self.cacheHostNames:
            return self.cacheHostNames[url]
        host = ""
        try:
            host = self.up.getHostName(url, True)
        except Exception:
            pass
        self.cacheHostNames[url] = host
        return host

    def _getHomePageData(self):
        if self.homePageData is not None:
            return True, self.homePageData
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            self.homePageData = data
        return sts, data

    def selectDomain(self):
        if CimaLina.DOMAIN_CACHE:
            self.setMainUrl(CimaLina.DOMAIN_CACHE)
            self.MAIN_URL = self.getMainUrl()
            return

        domains = ["https://2.cema-lin.shop/", "https://cema-lin.shop/", "https://cimalena.cfd/", "https://cimalina.live/"]

        altDomain = config.plugins.iptvplayer.cimalina_alt_domain.value.strip()
        if self.cm.isValidUrl(altDomain):
            if not altDomain.endswith("/"):
                altDomain += "/"
            domains.insert(0, altDomain)

        for domain in domains:
            sts, data = self.getPage(domain)
            if sts and data and ("سيما" in data or "Cima" in data or "cima" in data):
                try:
                    self.setMainUrl(self.cm.meta["url"])
                except Exception:
                    self.setMainUrl(domain)
                self.MAIN_URL = self.getMainUrl()
                CimaLina.DOMAIN_CACHE = self.MAIN_URL
                return

        self.setMainUrl(domains[0])
        self.MAIN_URL = self.getMainUrl()
        CimaLina.DOMAIN_CACHE = self.MAIN_URL

    def getFullIconUrl(self, url):
        url = (url or "").strip()
        url = CBaseHostClass.getFullIconUrl(self, url)
        if not url:
            return ""
        proxy = self.getProxy()
        if proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    def listMainMenu(self, cItem):
        printDBG("CimaLina.listMainMenu")
        tab = [{"category": "movies", "title": "الأفلام", "icon": self.DEFAULT_ICON_URL}, {"category": "series", "title": "المسلسلات", "icon": self.DEFAULT_ICON_URL}] + self.searchItems()
        self.listsTab(tab, cItem)

    def listCatItems(self, cItem, nextCategory):
        printDBG("CimaLina.listCatItems")
        cat = self.currItem.get("category", "")

        if cat in self.cacheCatItems:
            cachedItems = self.cacheCatItems[cat]
        else:
            sts, data = self._getHomePageData()
            if not sts:
                return

            menuIds = {"movies": "menu-item-380427", "series": "menu-item-380436"}
            menuId = menuIds.get(cat, "")

            section = ""
            if menuId:
                try:
                    startPattern = re.compile(r'<[^>]+class=["\'][^"\']*%s[^"\']*["\']' % re.escape(menuId), re.I)
                    section = self.cm.ph.getDataBeetwenReMarkers(data, startPattern, re.compile("</ul>", re.I), True)[1]
                except Exception:
                    section = ""

            cachedItems = []
            items = self.cm.ph.getAllItemsBeetwenMarkers(section, "<li", "</li>")
            for item in items:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'href=["\']([^"\']+?)["\']')[0])
                title = self.cleanHtmlStr(item)
                if title and title not in ["anime4up", "DMCA", "اتصل بنا"] and url:
                    cachedItems.append({"title": title, "url": url})

            self.cacheCatItems[cat] = cachedItems

        for item in cachedItems:
            params = dict(cItem)
            params.update({"category": nextCategory, "media_type": cat, "good_for_fav": True, "title": item["title"], "url": item["url"], "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": ""})
            self.addDir(params)

    def listItems(self, cItem, nextCategory):
        printDBG("CimaLina.listItems")
        page = cItem.get("page", 1)
        mediaType = cItem.get("media_type", "")
        url = cItem.get("url", "")

        sts, data = self.getPage(url)
        if not sts:
            return

        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination', "</ul>", False)[1]
        nextPageUrl = self.getFullUrl(self.cm.ph.getSearchGroups(pagination, r'href=["\']([^"\']+?)["\'][^>]*?>\s*%s\s*<' % (page + 1))[0])

        section = self.cm.ph.getDataBeetwenMarkers(data, "moviesBlocks", "footer", False)[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(section, "<div", "</a>")

        for item in items:
            if "movie" not in item:
                continue

            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'src=["\']([^"\']+?)["\']')[0])
            itemUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'href=["\']([^"\']+?)["\']')[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<h3", ">"), ("</h3", ">"), False)[1])

            if not title or not itemUrl:
                continue

            desc = ""
            rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"imdbRating[^>]*>\s*([^<]+?)\s*<")[0])
            if rating:
                desc += "Rating: %s | " % rating

            genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"category[^>]*>\s*([^<]+?)\s*<")[0])
            if genre:
                desc += "Genre: %s | " % genre

            year = self.cm.ph.getSearchGroups(item, r"([12][0-9]{3})")[0]
            if year:
                desc += "Year: %s" % year

            desc = desc.strip(" |")

            params = dict(cItem)
            params.update({"good_for_fav": True, "title": title, "url": itemUrl, "prev_url": itemUrl, "icon": icon or self.DEFAULT_ICON_URL, "desc": desc})

            if "/assemblies/" in itemUrl or "/selary/" in itemUrl:
                params["category"] = nextCategory
                self.addDir(params)
            elif mediaType == "movies":
                params["urlSeparateRequest"] = 1
                self.addVideo(params)
            else:
                params["category"] = nextCategory
                self.addDir(params)

        if nextPageUrl:
            params = dict(cItem)
            params.update({"title": _("Next page"), "url": nextPageUrl, "page": page + 1})
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG("CimaLina.exploreItems")
        page = cItem.get("page", 1)
        url = cItem.get("url", "")

        sts, data = self.getPage(url)
        if not sts:
            return

        cItem["prev_url"] = url
        storyDesc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "StoryMovie"), ("</div", ">"), False)[1])

        if "/selary/" in url or "/assemblies/" in url:
            section = self.cm.ph.getDataBeetwenMarkers(data, "moviesBlocks", "footer", False)[1]
            pagination = self.cm.ph.getDataBeetwenMarkers(section, '<div class="pagination', "</ul>", False)[1]
            nextPageUrl = self.getFullUrl(self.cm.ph.getSearchGroups(pagination, r'href=["\']([^"\']+?)["\'][^>]*?>\s*%s\s*<' % (page + 1))[0])

            items = self.cm.ph.getAllItemsBeetwenMarkers(section, "<div", "</a>")
            for item in items:
                if "movie" not in item:
                    continue

                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'src=["\']([^"\']+?)["\']')[0])
                if not icon:
                    icon = cItem.get("icon", self.DEFAULT_ICON_URL)

                itemUrl = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'href=["\']([^"\']+?)["\']')[0])
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ("<h3", ">"), ("</h3", ">"), False)[1])

                if not title or not itemUrl:
                    continue

                params = dict(cItem)
                params.update({"good_for_fav": True, "title": title, "url": itemUrl, "prev_url": itemUrl, "icon": icon, "desc": storyDesc, "urlSeparateRequest": 1})
                self.addVideo(params)

            if nextPageUrl:
                params = dict(cItem)
                params.update({"title": _("Next page"), "url": nextPageUrl, "page": page + 1})
                self.addMore(params)
        else:
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": cItem.get("title", ""), "url": url, "prev_url": url, "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": storyDesc, "urlSeparateRequest": 1})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CimaLina.listSearchResult")
        if searchType == "all":
            url = self.getFullUrl("/?s=%s" % urllib_quote_plus(searchPattern))
        elif searchType == "movies":
            url = self.getFullUrl("/?s=%s" % urllib_quote_plus("فيلم " + searchPattern))
        else:
            url = self.getFullUrl("/?s=%s" % urllib_quote_plus("مسلسل " + searchPattern))

        params = {"name": "category", "media_type": searchType, "good_for_fav": False, "url": url}
        self.listItems(params, "explore_item")

    def _normUrl(self, url):
        if not url:
            return ""
        url = html_unescape(url).strip()
        url = url.replace("\\/", "/").replace("&amp;", "&")
        if url.startswith("//"):
            url = "https:" + url
        return self.getFullUrl(url)

    def _isMegamaxUrl(self, url):
        low = (url or "").lower()
        return "megamax.me/" in low or "megamax.cam/" in low

    def _appendUniqueLink(self, retTab, name, url, need_resolve=1):
        url = self._normUrl(url)
        if not url or not self.cm.isValidUrl(url):
            return False

        for item in retTab:
            if str(item.get("url", "")) == str(url):
                return False

        retTab.append({"name": name, "url": url, "need_resolve": need_resolve})
        return True

    def _extractIframeSrc(self, html):
        html = html_unescape(html or "")
        if not html:
            return ""

        patterns = [r'<iframe[^>]+src=["\']([^"\']+?)["\']', r"<iframe[^>]+src=([^\s>]+)", r'src=["\']([^"\']+?)["\']', r"src=([^\s>]+)"]
        for pattern in patterns:
            url = self.cm.ph.getSearchGroups(html, pattern)[0]
            if url:
                url = url.replace("&quot;", '"').replace("&#039;", "'").strip()
                url = url.strip("'\"")
                return self._normUrl(url)
        return ""

    def _decodeBase64JsonValue(self, value):
        if not value or not base64 or not json:
            return {}
        try:
            value = html_unescape(value).strip()
            missing = len(value) % 4
            if missing:
                value += "=" * (4 - missing)

            txt = base64.b64decode(value)
            if not isinstance(txt, type("")):
                try:
                    txt = txt.decode("utf-8")
                except Exception:
                    txt = txt.decode("utf-8", "ignore")
            return json.loads(txt)
        except Exception:
            printExc()
        return {}

    def _extractWatchForm(self, data):
        if not data:
            return ""

        patterns = [r'(<form[^>]+id=["\']formWatch["\'][\s\S]+?</form>)', r'(<form[^>]+class=["\'][^"\']*formWatch[^"\']*["\'][\s\S]+?</form>)', r'(<form[^>]+method=["\']post["\'][\s\S]+?</form>)']
        for pattern in patterns:
            try:
                m = re.search(pattern, data, re.I)
                if m:
                    return m.group(1)
            except Exception:
                pass
        return ""

    def _getInputValue(self, formData, name):
        if not formData:
            return ""
        patterns = [r'name=["\']%s["\'][^>]*value=["\']([^"\']+?)["\']' % re.escape(name), r'value=["\']([^"\']+?)["\'][^>]*name=["\']%s["\']' % re.escape(name)]
        for pattern in patterns:
            val = self.cm.ph.getSearchGroups(formData, pattern)[0]
            if val:
                return html_unescape(val).strip()
        return ""

    def _findMegamaxInertiaVersion(self, data):
        if not data:
            return ""
        patterns = [r'"version"\s*:\s*"([^"]+?)"', r"'version'\s*:\s*'([^']+?)'", r'X-Inertia-Version["\']?\s*[:=]\s*["\']([^"\']+?)["\']']
        for pattern in patterns:
            try:
                m = re.search(pattern, data, re.I)
                if m:
                    return m.group(1)
            except Exception:
                pass
        return ""

    def _parseMegamaxInertiaJson(self, rawJson, cItemTitle):
        retTab = []
        if not json or not rawJson:
            return retTab

        try:
            obj = json.loads(rawJson)
            streams = obj.get("props", {}).get("streams", {})
            if streams.get("status") != "success":
                return retTab

            for qualityObj in streams.get("data", []):
                label = qualityObj.get("label", "Default")
                for mirror in qualityObj.get("mirrors", []):
                    driver = mirror.get("driver", "")
                    symbol = mirror.get("symbol", "")
                    link = mirror.get("link", "")
                    if not link:
                        continue
                    link = self._normUrl(link)
                    if not self.cm.isValidUrl(link):
                        continue
                    displayName = symbol if symbol else driver
                    self._appendUniqueLink(retTab, "%s [%s] - %s" % (cItemTitle, label, displayName), link, 1)
        except Exception:
            printExc()

        return retTab

    def _expandMegamaxToMirrors(self, iframeUrl, cItemTitle):
        retTab = []
        iframeUrl = self._normUrl(iframeUrl)
        if not iframeUrl:
            return retTab

        if iframeUrl in self.cacheMegamax:
            return list(self.cacheMegamax[iframeUrl])

        pageParams = {"return_data": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE, "header": {"User-Agent": self.MEGAMAX_UA}}

        sts, htmlData = self.getPage(iframeUrl, pageParams)
        if not sts:
            return retTab

        version = self._findMegamaxInertiaVersion(htmlData)

        inertiaHeaders = {"User-Agent": self.MEGAMAX_UA, "Referer": iframeUrl, "Sec-Fetch-Mode": "cors", "X-Inertia": "true", "X-Inertia-Partial-Component": "files/mirror/video", "X-Inertia-Partial-Data": "streams"}
        if version:
            inertiaHeaders["X-Inertia-Version"] = version

        inertiaParams = {"return_data": True, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE, "header": inertiaHeaders}

        sts, jsonData = self.getPage(iframeUrl, inertiaParams)
        if sts and jsonData:
            retTab = self._parseMegamaxInertiaJson(jsonData, cItemTitle)

        self.cacheMegamax[iframeUrl] = list(retTab)
        return retTab

    def _appendMegamaxLinks(self, retTab, cItemTitle, iframeUrl, label="Default"):
        expanded = self._expandMegamaxToMirrors(iframeUrl, cItemTitle)
        if expanded:
            added = False
            for item in expanded:
                if self._appendUniqueLink(retTab, item.get("name", cItemTitle), item.get("url", ""), item.get("need_resolve", 1)):
                    added = True
            if added:
                return True

        lazyUrl = strwithmeta(self._normUrl(iframeUrl), {"cimalina_megamax_lazy": "1", "cimalina_title": cItemTitle, "cimalina_label": label})
        hostName = self._getHostNameCached(iframeUrl) or "Megamax"
        return self._appendUniqueLink(retTab, "%s [%s] - %s" % (cItemTitle, label, hostName), lazyUrl, 1)

    def _appendLinksFromEncodedMap(self, retTab, encodedData, cItemTitle):
        try:
            dataMap = self._decodeBase64JsonValue(encodedData)
            if not isinstance(dataMap, dict):
                return

            idx = 0
            for key in dataMap:
                idx += 1
                link = self._normUrl(dataMap[key])
                if not link:
                    continue

                label = self.cleanHtmlStr(key) or ("Server %d" % idx)

                if self._isMegamaxUrl(link):
                    self._appendMegamaxLinks(retTab, cItemTitle, link, label)
                else:
                    hostName = self._getHostNameCached(link)
                    self._appendUniqueLink(retTab, "%s [%s] - %s" % (cItemTitle, label, hostName), link, 1)
        except Exception:
            printExc()

    def _parseServersPage(self, pageData, cItem):
        retTab = []
        cItemTitle = cItem.get("title", "")

        serversSection = self.cm.ph.getDataBeetwenMarkers(pageData, ("<ul", ">", "serversList"), ("</ul", ">"), True)[1]

        if serversSection:
            items = self.cm.ph.getAllItemsBeetwenMarkers(serversSection, "<li", "</li>")
            for item in items:
                serverName = self.cleanHtmlStr(item) or "Server"
                serverData = self.cm.ph.getSearchGroups(item, r'data-server=["\']([^"\']+?)["\']')[0]
                if not serverData:
                    serverData = self.cm.ph.getSearchGroups(item, r"data-server=([^>]+)")[0]

                iframeUrl = self._extractIframeSrc(serverData)
                if not iframeUrl:
                    rawUrl = self.cm.ph.getSearchGroups(serverData, r'(https?://[^\s"\']+|//[^\s"\']+)')[0]
                    iframeUrl = self._normUrl(rawUrl)

                if not iframeUrl:
                    continue

                if self._isMegamaxUrl(iframeUrl):
                    self._appendMegamaxLinks(retTab, cItemTitle, iframeUrl, serverName)
                else:
                    hostName = self._getHostNameCached(iframeUrl)
                    self._appendUniqueLink(retTab, "%s [%s] - %s" % (cItemTitle, serverName, hostName), iframeUrl, 1)

        if not retTab:
            embedSection = self.cm.ph.getDataBeetwenMarkers(pageData, ("<div", ">", "embedServer"), ("</div", ">"), True)[1]
            iframeUrl = self._extractIframeSrc(embedSection)
            if iframeUrl:
                if self._isMegamaxUrl(iframeUrl):
                    self._appendMegamaxLinks(retTab, cItemTitle, iframeUrl, "Default")
                else:
                    hostName = self._getHostNameCached(iframeUrl)
                    self._appendUniqueLink(retTab, "%s [Default] - %s" % (cItemTitle, hostName), iframeUrl, 1)

        return retTab

    def _removeDefaultFallbackIfNeeded(self, retTab):
        if len(retTab) <= 1:
            return retTab

        cleanTab = []
        for item in retTab:
            name = item.get("name", "")
            if " [Default] - " in name:
                continue
            cleanTab.append(item)

        if cleanTab:
            return cleanTab
        return retTab

    def getLinksForVideo(self, cItem):
        printDBG("CimaLina.getLinksForVideo [%s]" % cItem)

        url = cItem.get("prev_url", cItem.get("url", ""))
        cacheKey = str(url)
        if cacheKey in self.cacheLinks:
            return self.cacheLinks[cacheKey]

        retTab = []
        ajaxParams = dict(self.defaultParams)
        ajaxParams["header"] = self.AJAX_HEADER

        sts, data = self.getPage(url)
        if not sts:
            return retTab

        formData = self._extractWatchForm(data)
        if formData:
            actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(formData, r'action=["\']([^"\']+?)["\']')[0])
            servers = self._getInputValue(formData, "servers")
            downloads = self._getInputValue(formData, "downloads")

            if actionUrl:
                sts2, postData = self.getPage(actionUrl, ajaxParams, {"servers": servers, "downloads": downloads, "submit": ""})
                if sts2 and postData:
                    retTab.extend(self._parseServersPage(postData, cItem))

            self._appendLinksFromEncodedMap(retTab, servers, cItem.get("title", ""))
            self._appendLinksFromEncodedMap(retTab, downloads, cItem.get("title", ""))

        if not retTab:
            retTab.extend(self._parseServersPage(data, cItem))

        retTab = self._removeDefaultFallbackIfNeeded(retTab)
        self.cacheLinks[cacheKey] = retTab
        printDBG("CimaLina.getLinksForVideo -> final count[%d]" % len(retTab))
        return retTab

    def getVideoLinks(self, videoUrl):
        printDBG("CimaLina.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []

        meta = {}
        try:
            meta = getattr(videoUrl, "meta", {})
        except Exception:
            meta = {}

        if str(meta.get("cimalina_megamax_lazy", "")) == "1" or self._isMegamaxUrl(videoUrl):
            title = meta.get("cimalina_title", "Megamax")
            mirrors = self._expandMegamaxToMirrors(str(videoUrl), title)
            for item in mirrors:
                link = item.get("url", "")
                if not link:
                    continue
                try:
                    videoTab = self.up.getVideoLinkExt(link)
                    if videoTab:
                        return videoTab
                except Exception:
                    printExc()
            try:
                return self.up.getVideoLinkExt(str(videoUrl))
            except Exception:
                printExc()
            return []

        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem):
        printDBG("CimaLina.getArticleContent")
        otherInfo = {}
        url = cItem.get("prev_url", cItem.get("url", ""))

        if url in self.cacheArticles:
            return self.cacheArticles[url]

        sts, data = self.getPage(url)
        if not sts:
            return []

        section = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "MovieDetails"), ("<div", ">", "socialSharer"), True)[1]

        duration = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("مده العرض", ">"), ("</span", ">"), False)[1])
        if duration:
            otherInfo["duration"] = duration

        year = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("release-year", ">"), ("</a", ">"), False)[1])
        if year:
            otherInfo["year"] = year

        genre = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(section, ("<li", ">", "genre"), ("</li", ">"), False)[1])
        if genre:
            otherInfo["genre"] = genre

        category = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(section, ("<li", ">", "category"), ("</li", ">"), False)[1])
        if category:
            otherInfo["category"] = category

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "StoryMovie"), ("</div", ">"), False)[1])
        if not desc:
            desc = cItem.get("desc", "")

        article = [{"title": cItem.get("title", ""), "text": desc, "images": [{"title": "", "url": cItem.get("icon", "")}], "other_info": otherInfo}]
        self.cacheArticles[url] = article
        return article

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("CimaLina.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        if self.MAIN_URL is None:
            self.selectDomain()

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")

        self.currList = []

        try:
            if not name and not category:
                self.listMainMenu({"name": "category"})
            elif category in ("movies", "series"):
                self.listCatItems(self.currItem, "listItems")
            elif category == "listItems":
                self.listItems(self.currItem, "explore_item")
            elif category == "explore_item":
                self.exploreItems(self.currItem)
            elif category in ("search", "search_next_page"):
                params = dict(self.currItem)
                params.update({"search_item": False, "name": "category"})
                self.listSearchResult(params, searchPattern, searchType)
            elif category == "search_history":
                self.listsHistory({"name": "history", "category": "search"}, "desc")
        except Exception:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, CimaLina(), True)

    def getSearchTypes(self):
        return [("All", "all"), ("Movies", "movies"), ("Tv Series", "series")]

    def withArticleContent(self, cItem):
        return "prev_url" in cItem or cItem.get("category", "") == "explore_item"
