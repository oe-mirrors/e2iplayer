# -*- coding: utf-8 -*-
# Last modified: 14/5/2026
# AlooyTV Host (Created By Dr HYTHAM MAHMOUD)


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
    return "AlooyTV"


class AlooyTV(CBaseHostClass):

    # مسارات تدل على أن الرابط فيديو حتى لو امتداده صورة
    VIDEO_PATH_HINTS = [
        "/file/wp-",
        "/file/wp-alooytv",
        "/uploads/20",
        "/stream/",
        "/hls/",
        "/video/",
        "/media/",
        "/cdn/",
        "/content/",
        "/episode/",
    ]

    # مسارات تدل على أن الرابط صورة thumbnail حقيقية
    THUMB_PATH_HINTS = [
        "/uploads/video_thumb/",
        "/thumbs/",
        "/thumbnail/",
        "/thumbnails/",
        "/poster/",
        "/posters/",
        "/cover/",
        "/covers/",
        "/img/",
        "/images/",
        "/icons/",
    ]

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "alooytv", "cookie": "alooytv.cookie"})

        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "https://ci.alooytv12.xyz/uploads/system_logo/logo.png"

        self.HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Encoding": "gzip, deflate", "Connection": "keep-alive", "Accept-Language": "ar,en-US;q=0.9,en;q=0.8", "DNT": "1"}

        # headers مطابقة لما يرسله Chrome عند تشغيل فيديو
        self.VIDEO_HEADER = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
            "Accept-Encoding": "identity;q=1, *;q=0",
            "Range": "bytes=0-",
            "Sec-Fetch-Dest": "video",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Storage-Access": "active",
            "Sec-Ch-Ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Connection": "keep-alive",
        }

        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Referer": ""})

        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE, "return_data": True}

        self.cacheLinks = {}

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

        return self.cm.getPage(baseUrl, addParams, post_data)

    def selectDomain(self):
        domains = [
            "https://ci.alooytv12.xyz/",
            "https://www.ci.alooytv12.xyz/",
            "https://alooytv12.xyz/",
        ]

        altDomain = config.plugins.iptvplayer.cimalina_alt_domain.value.strip()
        if self.cm.isValidUrl(altDomain):
            if not altDomain.endswith("/"):
                altDomain += "/"
            domains.insert(0, altDomain)

        for domain in domains:
            sts, data = self.getPage(domain)
            if not sts:
                continue
            low = data.lower()
            if "tv-series" in low or "autocompleteajax" in low or "alooytv" in low:
                try:
                    self.setMainUrl(self.cm.meta["url"])
                except Exception:
                    self.setMainUrl(domain)
                self.MAIN_URL = self.getMainUrl()
                return

        self.setMainUrl(domains[0])
        self.MAIN_URL = self.getMainUrl()

    def getFullIconUrl(self, url):
        url = (url or "").strip()
        url = CBaseHostClass.getFullIconUrl(self, url)
        if not url:
            return ""
        proxy = self.getProxy()
        if proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    def _normUrl(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        url = html_unescape(url)
        url = url.replace("\\/", "/").replace("\\\\/", "/").replace("&amp;", "&")
        url = url.strip().strip("\\").strip('"').strip("'")
        if url.startswith("//"):
            url = "https:" + url
        return self.getFullUrl(url)

    def _cleanTitle(self, txt):
        return self.cleanHtmlStr(html_unescape(txt or "")).strip()

    def _slugToTitle(self, url):
        url = (url or "").split("?", 1)[0].split("#", 1)[0]
        slug = url.rstrip("/").split("/")[-1]
        if slug.endswith(".html"):
            slug = slug[:-5]
        if slug.startswith("watch"):
            slug = slug[5:]
        slug = slug.replace("-", " ").replace("_", " ")
        slug = re.sub(r"\s+", " ", slug).strip()
        return self._cleanTitle(slug)

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
        patterns = [r'<iframe[^>]+src=["\']([^"\']+?)["\']', r"<iframe[^>]+src=([^\s>]+)", r'src=["\']([^"\']+?)["\']', r"src=([^\s>]+)"]
        for pattern in patterns:
            val = self.cm.ph.getSearchGroups(html, pattern)[0]
            if val:
                return self._normUrl(val)
        return ""

    def _decodeBase64JsonValue(self, value):
        if not value or not base64 or not json:
            return {}
        try:
            value = html_unescape(value).strip().strip('"').strip("'")
            missing = len(value) % 4
            if missing:
                value += "=" * (4 - missing)
            txt = base64.b64decode(value)
            try:
                txt = txt.decode("utf-8")
            except Exception:
                txt = txt.decode("utf-8", "ignore")
            return json.loads(txt)
        except Exception:
            printExc()
        return {}

    def _decodeBase64Text(self, value):
        if not value or not base64:
            return ""
        try:
            value = html_unescape(value).strip().strip('"').strip("'")
            missing = len(value) % 4
            if missing:
                value += "=" * (4 - missing)
            txt = base64.b64decode(value)
            try:
                return txt.decode("utf-8")
            except Exception:
                return txt.decode("utf-8", "ignore")
        except Exception:
            return ""

    def _isVideoUrl(self, url):
        """
        يتعرف على روابط الفيديو بما فيها الملفات المموهة بامتداد صورة.
        مثال: /file/wp-alooytv/uploads/2023/Echo/s01/01.jpg => فيديو حقيقي
        """
        rawUrl = self._normUrl(url)
        if not rawUrl:
            return False
        low = rawUrl.lower().split("#")[0].split("?")[0]

        # امتدادات فيديو مباشرة
        if ".m3u8" in low or ".mp4" in low or ".ts" in low or ".mkv" in low or ".avi" in low:
            return True

        # ملفات بامتداد صورة لكن في مسار فيديو معروف (تمويه)
        imgExts = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
        if any(low.endswith(ext) for ext in imgExts):
            for hint in self.VIDEO_PATH_HINTS:
                if hint in low:
                    return True
            return False

        return False

    def _isImageUrl(self, url):
        """
        يتحقق إذا كان الرابط صورة thumbnail حقيقية وليس فيديو مموه.
        يفحص المسار أولاً قبل الاعتماد على الامتداد وحده.
        """
        rawUrl = (url or "").lower().split("?")[0].split("#")[0]

        # مسارات thumbnail معروفة => صورة دائماً
        for hint in self.THUMB_PATH_HINTS:
            if hint in rawUrl:
                return True

        # مسارات فيديو معروفة => ليست صورة حتى لو امتدادها jpg
        for hint in self.VIDEO_PATH_HINTS:
            if hint in rawUrl:
                return False

        # فحص الامتداد الاعتيادي للحالات الأخرى
        for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"]:
            if rawUrl.endswith(ext):
                return True

        return False

    def _findNextPage(self, data, page, currentUrl=""):
        nextPageUrl = self.cm.ph.getSearchGroups(data, r'<a[^>]+href=["\']([^"\']+?)["\'][^>]*rel=["\']next["\']')[0]
        if nextPageUrl:
            nextPageUrl = self.getFullUrl(nextPageUrl)
            if nextPageUrl and nextPageUrl != currentUrl:
                return nextPageUrl

        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination-container', "</div>", False)[1]
        if not pagination:
            pagination = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', "</ul>", False)[1]
        if not pagination:
            return ""

        patterns = [r'href=["\']([^"\']+?)["\'][^>]*data-ci-pagination-page=["\']%d["\']' % (page + 1), r'href=["\']([^"\']+?)["\'][^>]*>\s*(?:Next|التالي|›|»|&raquo;)\s*<', r'href=["\']([^"\']+?)["\'][^>]*>\s*%d\s*<' % (page + 1), r'href=["\']([^"\']*?[?&]page=%d[^"\']*)["\']' % (page + 1), r'href=["\']([^"\']*?/page/%d/?[^"\']*)["\']' % (page + 1), r'href=["\']([^"\']*?%d\.html[^"\']*)["\']' % ((page + 1) * 50)]

        for pattern in patterns:
            nextPageUrl = self.cm.ph.getSearchGroups(pagination, pattern)[0]
            if nextPageUrl:
                nextPageUrl = self.getFullUrl(nextPageUrl)
                if nextPageUrl and nextPageUrl != currentUrl:
                    return nextPageUrl

        return ""

    def _extractIconFromSegment(self, segment):
        icon = self.cm.ph.getSearchGroups(segment, r'<img[^>]+src=["\']([^"\']+?)["\']')[0]
        if not icon:
            icon = self.cm.ph.getSearchGroups(segment, r'data-src=["\']([^"\']+?)["\']')[0]
        if not icon:
            icon = self.cm.ph.getSearchGroups(segment, r'data-original=["\']([^"\']+?)["\']')[0]
        # تجاهل أيقونات play
        if icon and (".svg" in icon.lower() or "play" in icon.lower()):
            icon = ""
        return self.getFullIconUrl(icon)

    def _collectCategoryEntries(self, data):
        entries = []
        seen = set()

        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="movie-container">', '<div class="pagination-container', False)[1]
        if not block:
            block = self.cm.ph.getDataBeetwenMarkers(data, 'class="movie-container"', 'class="pagination', False)[1]
        if not block:
            block = data

        parts = re.split(r'<div[^>]+class=["\'][^"\']*col-md-2[^"\']*col-sm-3[^"\']*col-xs-4[^"\']*["\']', block)
        if len(parts) < 2:
            parts = re.split(r'<div[^>]+class=["\'][^"\']*latest-movie-img-container[^"\']*["\']', block)

        for part in parts[1:]:
            segment = part[:5000]

            itemUrl = self.cm.ph.getSearchGroups(segment, r'<a[^>]+href=["\']([^"\']+?\.html(?:\?[^"\']*)?)["\'][^>]*class=["\'][^"\']*ico-play[^"\']*["\']')[0]
            if not itemUrl:
                itemUrl = self.cm.ph.getSearchGroups(segment, r'<a[^>]+href=["\']([^"\']+?\.html(?:\?[^"\']*)?)["\']')[0]

            itemUrl = self._normUrl(itemUrl)
            if not itemUrl or itemUrl in seen:
                continue

            title = self.cm.ph.getSearchGroups(segment, r'class=["\']movie-title["\'][^>]*>.*?<h3[^>]*>.*?<a[^>]*>(.*?)</a>')[0]
            if not title:
                title = self.cm.ph.getSearchGroups(segment, r"<h3[^>]*>\s*<a[^>]*>(.*?)</a>")[0]
            if not title:
                title = self.cm.ph.getSearchGroups(segment, r'<img[^>]+alt=["\']([^"\']+?)["\']')[0]
            title = self._cleanTitle(title)
            if not title:
                title = self._slugToTitle(itemUrl)

            icon = self._extractIconFromSegment(segment)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(segment, r'<span[^>]+class=["\']label label-primary["\'][^>]*>\s*([^<]+?)\s*<')[0])

            seen.add(itemUrl)
            entries.append({"url": itemUrl, "title": title, "icon": icon, "label": label})

        return entries

    def _extractEpisodesBlock(self, data):
        start = data.find('class="season"')
        if start < 0:
            start = data.find("class='season'")
        if start < 0:
            return ""

        endMarkers = ["You May Like", "similler-movie", 'class="similler-movie"', "class='similler-movie'", "<!-- End row1 player -->", "<!-- row2 movie info -->"]
        endPos = len(data)
        for marker in endMarkers:
            pos = data.find(marker, start)
            if pos > start and pos < endPos:
                endPos = pos
        return data[start:endPos]

    def _collectEpisodeEntries(self, data, currentUrl):
        block = self._extractEpisodesBlock(data)
        if not block:
            return []

        entries = []
        seen = set()

        patterns = [
            r'<a[^>]+href=["\']([^"\']+?)["\'][^>]*class=["\']([^"\']*btn-inline[^"\']*)["\'][^>]*>(.*?)</a>',
            r'<a[^>]+href=["\']([^"\']*watch[^"\']+?\?key=[^"\']+)["\'][^>]*>(.*?)</a>',
            r'<a[^>]+href=["\']([^"\']*watch[^"\']+?&key=[^"\']+)["\'][^>]*>(.*?)</a>',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, block, re.I | re.S):
                if len(match.groups()) == 3:
                    itemUrl = self._normUrl(match.group(1))
                    cssClass = match.group(2)
                    title = self._cleanTitle(match.group(3))
                    if "btn-inline" not in cssClass:
                        continue
                else:
                    itemUrl = self._normUrl(match.group(1))
                    title = self._cleanTitle(match.group(2))

                if not itemUrl or itemUrl in seen:
                    continue
                if "watch" not in itemUrl:
                    continue
                if "?key=" not in itemUrl and "&key=" not in itemUrl:
                    continue

                seen.add(itemUrl)
                entries.append({"url": itemUrl, "title": title, "icon": "", "label": _("Episode")})

        if not entries:
            for itemUrl in re.findall(r'href=["\']([^"\']*watch[^"\']+?(?:\?|&)key=[^"\']+)["\']', block, re.I):
                itemUrl = self._normUrl(itemUrl)
                if not itemUrl or itemUrl in seen:
                    continue
                seen.add(itemUrl)
                entries.append({"url": itemUrl, "title": self._slugToTitle(itemUrl), "icon": "", "label": _("Episode")})

        return entries

    def _getDirectUrlWithMeta(self, url, referer=""):
        url = self._normUrl(url)
        if not url:
            return ""
        if not referer:
            referer = self.getMainUrl()

        mainDomain = self.getMainUrl()
        if not mainDomain.endswith("/"):
            mainDomain += "/"

        videoMeta = dict(self.VIDEO_HEADER)
        videoMeta["Referer"] = mainDomain
        videoMeta["Origin"] = mainDomain.rstrip("/")

        proxy = self.getProxy()
        if proxy:
            videoMeta["iptv_http_proxy"] = proxy

        return strwithmeta(url, videoMeta)

    def _extractDownloadVideoUrl(self, data):
        items = re.findall(r'href=["\']([^"\']*downloadvideo\.php\?[^"\']+)["\']', data, re.I)
        for item in items:
            full = self._normUrl(item)
            encoded = self.cm.ph.getSearchGroups(full, r"[?&]videourl=([^&]+)")[0]
            if not encoded:
                continue
            decoded = self._decodeBase64Text(encoded)
            decoded = self._normUrl(decoded)
            if decoded and self._isVideoUrl(decoded) and not self._isImageUrl(decoded):
                return decoded
        return ""

    def listMainMenu(self, cItem):
        tab = [
            {"category": "list_items", "title": "أحدث الإضافات", "url": self.getFullUrl("/tv-series.html"), "icon": self.DEFAULT_ICON_URL},
            {"category": "sections", "title": "الأقسام", "icon": self.DEFAULT_ICON_URL},
            {"category": "ramadan", "title": "رمضان", "icon": self.DEFAULT_ICON_URL},
            {"category": "list_items", "title": "الرئيسية", "url": self.getMainUrl(), "icon": self.DEFAULT_ICON_URL},
        ] + self.searchItems()
        self.listsTab(tab, cItem)

    def listSections(self, cItem):
        tab = [
            {"category": "list_items", "title": "عربي", "url": self.getFullUrl("/genre/arabic.html")},
            {"category": "list_items", "title": "خليجي", "url": self.getFullUrl("/genre/kleeji.html")},
            {"category": "list_items", "title": "تركي", "url": self.getFullUrl("/genre/turki.html")},
            {"category": "list_items", "title": "فارسي", "url": self.getFullUrl("/genre/farisi.html")},
            {"category": "list_items", "title": "أنمي", "url": self.getFullUrl("/genre/anmi.html")},
            {"category": "list_items", "title": "أفلام أجنبية", "url": self.getFullUrl("/genre/foreign-movies.html")},
            {"category": "list_items", "title": "أفلام كورية", "url": self.getFullUrl("/genre/Korean-movies.html")},
            {"category": "list_items", "title": "مسلسلات أجنبية", "url": self.getFullUrl("/genre/Foreign-series.html")},
            {"category": "list_items", "title": "مسلسلات كورية", "url": self.getFullUrl("/genre/Korean-series.html")},
            {"category": "list_items", "title": "مسلسلات آسيوية", "url": self.getFullUrl("/genre/asia-series.html")},
        ]
        self.listsTab(tab, cItem)

    def listRamadanYears(self, cItem):
        tab = [
            {"category": "ramadan_year", "title": "رمضان 2026", "year": "2026"},
            {"category": "ramadan_year", "title": "رمضان 2025", "year": "2025"},
            {"category": "ramadan_year", "title": "رمضان 2024", "year": "2024"},
            {"category": "ramadan_year", "title": "رمضان 2023", "year": "2023"},
        ]
        self.listsTab(tab, cItem)

    def listRamadanYear(self, cItem):
        year = cItem.get("year", "")
        if year == "2023":
            tab = [
                {"category": "list_items", "title": "عربي", "url": self.getFullUrl("/genre/ramadan-arabi.html")},
                {"category": "list_items", "title": "خليجي", "url": self.getFullUrl("/genre/ramadan-kleeji.html")},
            ]
        else:
            tab = [
                {"category": "list_items", "title": "عربي", "url": self.getFullUrl("/genre/ramadan-arabi-%s.html" % year)},
                {"category": "list_items", "title": "خليجي", "url": self.getFullUrl("/genre/ramadan-kleeji-%s.html" % year)},
            ]
        self.listsTab(tab, cItem)

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = self._normUrl(cItem.get("url", ""))
        if not url:
            return

        sts, data = self.getPage(url)
        if not sts:
            return

        try:
            self.setMainUrl(self.cm.meta.get("url", self.getMainUrl()))
        except Exception:
            pass

        entries = self._collectCategoryEntries(data)

        if not entries:
            seen = set()
            for href in re.findall(r'<a[^>]+href=["\']([^"\']+?\.html(?:\?[^"\']*)?)["\']', data, re.I):
                itemUrl = self._normUrl(href)
                if not itemUrl or itemUrl in seen:
                    continue
                if any(x in itemUrl for x in ["/genre/", "/search", "tv-series.html", "javascript"]):
                    continue
                if "/watch/" not in itemUrl and not re.search(r"/watch[^/]", itemUrl):
                    continue
                seen.add(itemUrl)
                entries.append({"url": itemUrl, "title": self._slugToTitle(itemUrl), "icon": self.DEFAULT_ICON_URL, "label": ""})

        for entry in entries:
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": entry["title"], "url": entry["url"], "prev_url": entry["url"], "icon": entry["icon"] or self.DEFAULT_ICON_URL, "desc": entry.get("label", ""), "category": "explore_item"})
            self.addDir(params)

        nextPageUrl = self._findNextPage(data, page, url)
        if nextPageUrl and nextPageUrl != url:
            params = dict(cItem)
            params.update({"title": _("Next page"), "url": nextPageUrl, "page": page + 1, "category": "list_items"})
            self.addDir(params)

    def exploreItems(self, cItem):
        url = cItem.get("url", "")
        sts, data = self.getPage(url)
        if not sts:
            return

        episodeEntries = self._collectEpisodeEntries(data, url)
        uniqueEpisodes = []
        seen = set()

        for item in episodeEntries:
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            uniqueEpisodes.append(item)

        if len(uniqueEpisodes) > 1:
            for entry in uniqueEpisodes:
                epTitle = entry["title"]
                if not epTitle:
                    epTitle = cItem.get("title", "")
                elif cItem.get("title", "") and cItem.get("title", "") not in epTitle:
                    epTitle = "%s - %s" % (cItem.get("title", ""), epTitle)
                params = dict(cItem)
                params.update({"good_for_fav": True, "title": epTitle, "url": entry["url"], "prev_url": entry["url"], "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": _("Episode"), "urlSeparateRequest": 1})
                self.addVideo(params)
            return

        if len(uniqueEpisodes) == 1:
            entry = uniqueEpisodes[0]
            epTitle = entry["title"] or cItem.get("title", "")
            params = dict(cItem)
            params.update({"good_for_fav": True, "title": epTitle, "url": entry["url"], "prev_url": entry["url"], "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": _("Episode"), "urlSeparateRequest": 1})
            self.addVideo(params)
            return

        params = dict(cItem)
        params.update({"good_for_fav": True, "prev_url": url, "url": url, "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "urlSeparateRequest": 1})
        self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        if searchType == "movies":
            pattern = "فيلم " + searchPattern
        elif searchType == "series":
            pattern = "مسلسل " + searchPattern
        else:
            pattern = searchPattern

        url = self.getFullUrl("/search?q=%s" % urllib_quote_plus(pattern))
        params = dict(cItem)
        params.update({"name": "category", "category": "list_items", "url": url, "good_for_fav": False})
        self.listItems(params)

    def _extractWatchForm(self, data):
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
        patterns = [r'name=["\']%s["\'][^>]*value=["\']([^"\']+?)["\']' % re.escape(name), r'value=["\']([^"\']+?)["\'][^>]*name=["\']%s["\']' % re.escape(name)]
        for pattern in patterns:
            val = self.cm.ph.getSearchGroups(formData, pattern)[0]
            if val:
                return html_unescape(val).strip()
        return ""

    def _appendLinksFromEncodedMap(self, retTab, encodedData, cItemTitle):
        dataMap = self._decodeBase64JsonValue(encodedData)
        if not isinstance(dataMap, dict):
            return
        idx = 0
        for key in dataMap:
            idx += 1
            link = self._normUrl(dataMap[key])
            if not link or not self._isVideoUrl(link) or self._isImageUrl(link):
                continue
            label = self.cleanHtmlStr(key) or ("Server %d" % idx)
            hostName = self.up.getHostName(link, True)
            self._appendUniqueLink(retTab, "%s [%s] - %s" % (cItemTitle, label, hostName), link, 1)

    def _parseServersPage(self, pageData, cItem):
        retTab = []
        cItemTitle = cItem.get("title", "")

        serversSection = self.cm.ph.getDataBeetwenMarkers(pageData, "serversList", "</ul>", False)[1]
        if not serversSection:
            serversSection = self.cm.ph.getDataBeetwenMarkers(pageData, "list_servers", "</ul>", False)[1]

        if serversSection:
            items = self.cm.ph.getAllItemsBeetwenMarkers(serversSection, "<li", "</li>")
            for item in items:
                serverName = self.cleanHtmlStr(item) or "Server"
                serverData = self.cm.ph.getSearchGroups(item, r'data-server=["\']([^"\']+?)["\']')[0]
                if not serverData:
                    serverData = self.cm.ph.getSearchGroups(item, r"data-server=([^ >]+)")[0]
                if not serverData:
                    serverData = self.cm.ph.getSearchGroups(item, r'data-embed=["\']([^"\']+?)["\']')[0]

                iframeUrl = self._extractIframeSrc(serverData)
                if not iframeUrl:
                    rawUrl = self.cm.ph.getSearchGroups(serverData, r'(https?://[^\s"\']+|//[^\s"\']+)')[0]
                    iframeUrl = self._normUrl(rawUrl)

                if iframeUrl:
                    hostName = self.up.getHostName(iframeUrl, True)
                    self._appendUniqueLink(retTab, "%s [%s] - %s" % (cItemTitle, serverName, hostName), iframeUrl, 1)

        if not retTab:
            for iframeUrl in re.findall(r'<iframe[^>]+src=["\']([^"\']+?)["\']', pageData, re.I):
                iframeUrl = self._normUrl(iframeUrl)
                if not iframeUrl:
                    continue
                hostName = self.up.getHostName(iframeUrl, True)
                self._appendUniqueLink(retTab, "%s [Default] - %s" % (cItemTitle, hostName), iframeUrl, 1)

        return retTab

    def getLinksForVideo(self, cItem):
        url = cItem.get("prev_url", cItem.get("url", ""))
        cacheKey = str(url)
        if cacheKey in self.cacheLinks:
            return self.cacheLinks[cacheKey]

        retTab = []
        if not url:
            return retTab

        mainDomain = self.getMainUrl()
        if not mainDomain.endswith("/"):
            mainDomain += "/"

        ajaxParams = dict(self.defaultParams)
        ajaxParams["header"] = dict(self.AJAX_HEADER)
        ajaxParams["header"]["Referer"] = mainDomain

        sts, data = self.getPage(url, ajaxParams)
        if not sts:
            sts, data = self.getPage(url)
            if not sts:
                return retTab

        # أنماط استخراج روابط الفيديو - تشمل الملفات المموهة بامتداد صورة
        directPatterns = [
            r'["\'](https?://[^"\']+?\.mp4(?:\?[^"\']*)?)["\']',
            r'["\'](https?://[^"\']+?\.m3u8(?:\?[^"\']*)?)["\']',
            r'["\'](https?://[^"\']+?\.ts(?:\?[^"\']*)?)["\']',
            # ملفات jpg/jpeg في مسارات فيديو معروفة (تمويه)
            r'["\'](https?://[^"\']*(?:/file/wp-|/uploads/20)[^"\']+?\.jpe?g(?:\?[^"\']*)?)["\']',
            r'["\'](https?://[^"\']*(?:/file/wp-|/uploads/20)[^"\']+?\.png(?:\?[^"\']*)?)["\']',
            r'file["\']?\s*:\s*["\']([^"\']+?)["\']',
            r'<source[^>]+src=["\']([^"\']+?)["\']',
            r'contentUrl["\']?\s*:\s*["\']([^"\']+?)["\']',
        ]

        def add_direct(candidate):
            candidate = self._normUrl(candidate)
            if not candidate:
                return
            if not self._isVideoUrl(candidate):
                return
            if self._isImageUrl(candidate):
                return
            hostName = self.up.getHostName(candidate, True) or "direct"
            finalUrl = self._getDirectUrlWithMeta(candidate, mainDomain)
            for t in retTab:
                if str(t.get("url", "")) == str(finalUrl):
                    return
            retTab.append({"name": "%s - %s" % (cItem.get("title", ""), hostName), "url": finalUrl, "need_resolve": 0})

        for pattern in directPatterns:
            for itemUrl in re.findall(pattern, data, re.I):
                add_direct(itemUrl)

        if not retTab:
            dlUrl = self._extractDownloadVideoUrl(data)
            if dlUrl:
                add_direct(dlUrl)

        if not retTab:
            formData = self._extractWatchForm(data)
            if formData:
                actionUrl = self.getFullUrl(self.cm.ph.getSearchGroups(formData, r'action=["\']([^"\']+?)["\']')[0])
                servers = self._getInputValue(formData, "servers")
                downloads = self._getInputValue(formData, "downloads")

                if actionUrl:
                    sts2, postData = self.getPage(actionUrl, ajaxParams, {"servers": servers, "downloads": downloads, "submit": ""})
                    if sts2 and postData:
                        for pattern in directPatterns:
                            for itemUrl in re.findall(pattern, postData, re.I):
                                add_direct(itemUrl)

                        if not retTab:
                            dlUrl = self._extractDownloadVideoUrl(postData)
                            if dlUrl:
                                add_direct(dlUrl)

                        if not retTab:
                            retTab.extend(self._parseServersPage(postData, cItem))

                if not retTab:
                    self._appendLinksFromEncodedMap(retTab, servers, cItem.get("title", ""))
                    self._appendLinksFromEncodedMap(retTab, downloads, cItem.get("title", ""))

        if not retTab:
            retTab.extend(self._parseServersPage(data, cItem))

        self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, videoUrl):
        if not self.cm.isValidUrl(videoUrl):
            return []
        if ".mp4" in videoUrl or ".m3u8" in videoUrl or self._isVideoUrl(videoUrl):
            return [{"name": "direct", "url": videoUrl}]
        return self.up.getVideoLinkExt(videoUrl)

    def getArticleContent(self, cItem):
        otherInfo = {}
        url = cItem.get("prev_url", cItem.get("url", ""))
        sts, data = self.getPage(url)
        if not sts:
            return []

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "StoryMovie"), ("</div", ">"), False)[1])
        if not desc:
            desc = cItem.get("desc", "")

        year = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"([12][0-9]{3})")[0])
        if year:
            otherInfo["year"] = year

        genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"genre[^>]*>\s*([^<]+?)\s*<")[0])
        if genre:
            otherInfo["genre"] = genre

        duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r"مده العرض[^<]*</[^>]+>\s*([^<]+?)\s*<")[0])
        if duration:
            otherInfo["duration"] = duration

        return [{"title": cItem.get("title", ""), "text": desc, "images": [{"title": "", "url": cItem.get("icon", self.DEFAULT_ICON_URL)}], "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        if self.MAIN_URL is None:
            self.selectDomain()

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        self.currList = []

        try:
            if not name and not category:
                self.listMainMenu({"name": "category"})
            elif category == "sections":
                self.listSections(self.currItem)
            elif category == "ramadan":
                self.listRamadanYears(self.currItem)
            elif category == "ramadan_year":
                self.listRamadanYear(self.currItem)
            elif category == "list_items":
                self.listItems(self.currItem)
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
        CHostBase.__init__(self, AlooyTV(), True)

    def getSearchTypes(self):
        return [("All", "all"), ("Movies", "movies"), ("Tv Series", "series")]

    def withArticleContent(self, cItem):
        return cItem.get("urlSeparateRequest", 0) == 1 or "prev_url" in cItem or cItem.get("category", "") == "explore_item"
