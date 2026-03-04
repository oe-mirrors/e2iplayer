# -*- coding: utf-8 -*-
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.libs import ph
import re
import json

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote
try:
    from urllib.parse import quote as urlQuote
except ImportError:
    from urllib import quote as urlQuote
C = E2ColoR("cyan")
G = E2ColoR("green")
L = E2ColoR("lime")
R = E2ColoR("red")
W = E2ColoR("white")
Y = E2ColoR("yellow")


def gettytul():
    return "https://ar.ifilmtv.ir"


class IFilmArabicHost(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "ifilmarabic", "cookie": "ifilmarabic.cookie"})
        self.MAIN_URL = "https://ar.ifilmtv.ir/"
        self.LIVE_URL = "https://ar.ifilmtv.ir/Home/Live"
        self.SEARCH_URL = "https://ar.ifilmtv.ir/Search/Content?q="
        self.SERIES_URL = "https://ar.ifilmtv.ir/Series"
        self.MOVIES_URL = "https://ar.ifilmtv.ir/Film"
        self.PROGRAMS_URL = "https://ar.ifilmtv.ir/Program"
        self.KIDS_URL = "https://ar.ifilmtv.ir/News/Tag?id=18379&page=1"
        self.DEFAULT_ICON_URL = "https://ar.ifilmtv.ir/img/colorize-logo-final.png"
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HTTP_HEADER.update(
            {
                "Referer": self.MAIN_URL,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ar-SA,ar;q=0.9,en;q=0.8",
            }
        )
        self.defaultParams = {"header": self.HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.MAIN_CAT_TAB = [
            {"category": "live", "title": _("البث المباشر"), "url": self.LIVE_URL},
            {"category": "series", "title": _("المسلسلات"), "url": self.SERIES_URL},
            {"category": "movies", "title": _("الأفلام"), "url": self.MOVIES_URL},
            {"category": "programs", "title": _("البرامج"), "url": self.PROGRAMS_URL},
            {"category": "kids", "title": _("أطفال آي فيلم"), "url": self.KIDS_URL},
        ] + self.searchItems()
        self.LIVE_STREAMS = [
            {"name": "iFilm Arabic", "url": "https://live.presstv.ir/hls/ifilmar.m3u8"},
            {"name": "iFilm Arabic 2", "url": "https://live.presstv.ir/hls/ifilmar_4_482/index.m3u8"},
            {"name": "iFilm Persian", "url": "https://live.presstv.ir/hls/ifilmfa.m3u8"},
            {"name": "iFilm Persian 2", "url": "https://live.presstv.ir/hls/ifilmfa_4_482/index.m3u8"},
            {"name": "iFilm English", "url": "https://live.presstv.ir/hls/ifilmen.m3u8"},
            {"name": "iFilm English 2", "url": "https://live.presstv.ir/hls/ifilmen_4_482/index.m3u8"},
        ]

    def getPage(self, url, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        url = url.strip()
        return self.cm.getPage(url, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("IFilmArabicHost.listMainMenu")
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listLiveStreams(self, cItem):
        printDBG("IFilmArabicHost.listLiveStreams")
        for stream in self.LIVE_STREAMS:
            name = stream["name"]
            if "Arabic" in name:
                colored_title = Y + name + W
            elif "Persian" in name:
                colored_title = C + name + W
            elif "English" in name:
                colored_title = L + name + W
            else:
                colored_title = name
            params = {"name": "category", "category": "video", "title": colored_title, "url": stream["url"], "icon": self.DEFAULT_ICON_URL, "desc": Y + _("بث مباشر جودة عالية باللغة المختارة") + W}
            self.addVideo(params)

    def listContent(self, cItem, nextCategory):
        printDBG("IFilmArabicHost.listContent")
        baseUrl = cItem.get("url", "").strip()
        if "/Program" in baseUrl and "PageingItem" not in baseUrl:
            apiUrl = self.getFullUrl("/Home/PageingItem?category=7&page=1&size=150&orderby=1")
            sts, data = self.getPage(apiUrl)
            if sts:
                try:
                    result = json.loads(data)
                    for item in result:
                        title = item.get("Title", "").strip()
                        match = re.search(r"^(.*?)\((\d{4})\)$", title)
                        colored_title = "{0}{1} {2}({3}){4}".format(Y, match.group(1).strip(), C, match.group(2).strip(), W) if match else Y + title + W
                        icon = item.get("ImageAddress_M", "")
                        if icon:
                            icon = self.getFullUrl(icon)
                            icon = urlQuote(icon.encode("utf-8"), safe=":/")
                        itemUrl = self.getFullUrl("/Program/Content/" + str(item.get("Id", "")))
                        self.addDir({"name": "category", "category": "episodes", "title": colored_title, "url": itemUrl, "icon": icon})
                    return
                except Exception:
                    printExc()
        sts, data = self.getPage(baseUrl)
        if not sts:
            return
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, "<a", "</a>")
        numItems = 0
        for item in items:
            if "result[i]" in item or "inner-panel" not in item and "panel-inner-small" not in item:
                continue
            itemUrl = self.cm.ph.getSearchGroups(item, """href=['"]([^'"]+?)['"]""")[0]
            if not itemUrl or itemUrl == "#" or "result[i]" in itemUrl:
                continue
            itemUrl = self.getFullUrl(itemUrl)
            title = self.cm.ph.getDataBeetwenMarkers(item, "<h6>", "</h6>")[1]
            title = self.cm.ph.cleanHtmlStr(title).strip()
            if not title:
                continue
            match = re.search(r"^(.*?)\((\d{4})\)$", title)
            colored_title = "{0}{1} {2}({3}){4}".format(Y, match.group(1).strip(), C, match.group(2).strip(), W) if match else Y + title + W
            icon = self.cm.ph.getSearchGroups(item, """src=['"]([^'"]+?)['"]""")[0]
            if not icon or "result[i]" in icon:
                icon = self.cm.ph.getSearchGroups(item, """url\(&quot;([^&]+?)&quot;\)""")[0]
            if icon and "result[i]" not in icon:
                icon = self.getFullUrl(icon)
                icon = urlQuote(icon.encode("utf-8"), safe=":/")
            if "/Film/" in itemUrl:
                new_category = "movie_details"
            else:
                new_category = "episodes"
            self.addDir({"name": "category", "category": new_category, "title": colored_title, "url": itemUrl, "icon": icon})
            numItems += 1
        if numItems > 0 and "PageingItem" not in baseUrl:
            page = self.cm.ph.getSearchGroups(baseUrl, "page=(\d+)")[0]
            if page == "":
                page = "1"
            nextPage = int(page) + 1
            nextUrl = baseUrl.replace("page=" + page, "page=" + str(nextPage)) if "page=" in baseUrl else (baseUrl + ("&" if "?" in baseUrl else "?") + "page=" + str(nextPage))
            self.addDir({"name": "category", "category": nextCategory, "title": L + _("Next Page »»» (%d)") % nextPage, "url": nextUrl})

    def listEpisodes(self, cItem):
        printDBG("IFilmArabicHost.listEpisodes")
        url = cItem.get("url", "")
        sts, data = self.getPage(url)
        if not sts:
            printDBG("IFilmArabicHost: Page request failed, trying fallback ID")
            seriesId = self.cm.ph.getSearchGroups(url + "/", r"Content/(\d+)")[0]
            if seriesId:
                fallback_url = self.getFullUrl("/Series/Content/" + seriesId)
                sts, data = self.getPage(fallback_url)
        if not sts:
            self.addMarker({"title": L + _("! عذراً، هذا المحتوى غير متاح حالياً (خطأ في الاتصال)") + W, "desc": Y + _("المصدر لا يستجيب للطلب، يرجى المحاولة لاحقاً.") + W})
            return
        story = self.cm.ph.getDataBeetwenMarkers(data, '<div id="wrapper"', "</div>")[1]
        story = self.cm.ph.cleanHtmlStr(story).strip()
        artists_data = self.cm.ph.getDataBeetwenMarkers(data, "Film-Artists-panel", "Film-movies-panel", False)[1]
        artists = self.cm.ph.getAllItemsBeetwenMarkers(artists_data, "<a", "</a>")
        cast_list = [self.cm.ph.cleanHtmlStr(a).strip() for a in artists if self.cm.ph.cleanHtmlStr(a).strip()]
        cast_string = " | ".join(cast_list)
        full_desc = "{0}الطاقم: {1}{2}\n{0}القصة: {1}{3}".format(Y, W, cast_string, story)
        episodes_found = False
        seriesId = self.cm.ph.getSearchGroups(data, r"id\s*=\s*parseInt\((\d+)\)")[0]
        if not seriesId:
            seriesId = self.cm.ph.getSearchGroups(url + "/", r"Content/(\d+)")[0]
        numEpisodes = self.cm.ph.getSearchGroups(data, r"var\s+inter_\s*=\s*(\d+)")[0]
        lang = self.cm.ph.getSearchGroups(data, r'var\s+langE\s*=\s*["\']([^"\']+)["\']')[0]
        if lang == "fa":
            lang = ""
        if seriesId and numEpisodes and int(numEpisodes) > 0:
            printDBG("IFilmArabicHost: Using Script Method (Classic)")
            for i in range(1, int(numEpisodes) + 1):
                title = "الحلقة: %s" % i
                icon = "https://preview.presstv.ir/ifilm/%s%s/%s.png" % (lang, seriesId, i)
                videoUrl = "https://vod.ifilmtv.ir/hls/%s%s/,%s,%s_320,.mp4.urlset/master.m3u8" % (lang, seriesId, i, i)
                self.addVideo({"title": title, "url": videoUrl, "icon": icon, "desc": full_desc, "need_resolve": 1})
                episodes_found = True
            if episodes_found:
                return
        if seriesId:
            printDBG("IFilmArabicHost: Using JSON Method (New)")
            apiUrl = self.getFullUrl("/Home/PageingAttachmentItem?id={0}&page=1&size=150".format(seriesId))
            sts_json, json_data = self.getPage(apiUrl)
            if sts_json:
                try:
                    result = json.loads(json_data)
                    if result and isinstance(result, list) and len(result) > 0:
                        try:
                            result.sort(key=lambda x: int(x.get("Episode", 0)))
                        except Exception:
                            pass
                        for item in result:
                            episode_num = str(item.get("Episode", ""))
                            title = "الحلقة: " + episode_num
                            videoUrl = item.get("VideoAddress", "")
                            if videoUrl:
                                if not videoUrl.startswith("http"):
                                    videoUrl = "https://fa.ifilmtv.ir/" + videoUrl
                                icon = self.getFullUrl(item.get("ImageAddress_M", ""))
                                self.addVideo({"title": title, "url": videoUrl, "icon": icon, "desc": full_desc, "need_resolve": 1})
                                episodes_found = True
                        if episodes_found:
                            return
                except Exception:
                    printExc()
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="panel-inner-movies">', "</div>")
        for item in items:
            title = self.cm.ph.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<a class="neme-movie">', "</a>")[1]).strip()
            videoUrl = self.cm.ph.getSearchGroups(item, """data-url=['"]([^'"]+?)['"]""")[0]
            if videoUrl and title:
                self.addVideo({"title": title, "url": self.getFullUrl(videoUrl), "desc": full_desc})
                episodes_found = True
        if not episodes_found:
            printDBG("IFilmArabicHost: No episodes added, showing marker.")
            self.addMarker({"title": L + _("! لا توجد فيديوهات متاحة حالياً لهذا العمل") + W, "desc": Y + _("يبدو أن الحلقات لم يتم رفعها بعد في هذا القسم من المصدر.") + W})

    def listMovies(self, cItem):
        printDBG("IFilmArabicHost.listMovies")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        story = self.cm.ph.getDataBeetwenMarkers(data, '<div id="wrapper"', "</div>")[1]
        story = self.cm.ph.cleanHtmlStr(story).strip()
        artists_data = self.cm.ph.getDataBeetwenMarkers(data, 'class="Film-Artists-panel"', "</div>\n\t\t\t\t</div>", False)[1]
        if not artists_data:
            artists_data = self.cm.ph.getDataBeetwenMarkers(data, 'class="Film-Artists-panel"', '<div class="row"', False)[1]
        artists = self.cm.ph.getAllItemsBeetwenMarkers(artists_data, "<a", "</a>")
        cast_list = []
        for artist in artists:
            role = self.cm.ph.getDataBeetwenMarkers(artist, "<h6>", "</h6>")[1]
            name = self.cm.ph.getDataBeetwenMarkers(artist, "<span>", "</span>")[1]
            if name:
                cast_list.append("{0} ({1})".format(self.cm.ph.cleanHtmlStr(name), self.cm.ph.cleanHtmlStr(role)))
        full_desc = Y + "الطاقم: " + W + " | ".join(cast_list) + "\n" + Y + "القصة: " + W + story
        videoUrl = self.cm.ph.getSearchGroups(data, "<source\s+src=[\"']([^\"']+\.mp4[^\"']*)[\"']")[0]
        if videoUrl == "":
            videoUrl = self.cm.ph.getSearchGroups(data, 'id="plyr_video".+?src=["\']([^"\']+)["\']')[0]
        if videoUrl.startswith("//"):
            videoUrl = "https:" + videoUrl
        cleanTitle = self.cm.ph.cleanHtmlStr(cItem.get("title", ""))
        if videoUrl and videoUrl != "":
            printDBG("IFilmArabicHost: Video URL found: " + videoUrl)
            params = dict(cItem)
            params.update({"title": W + "▶ " + Y + cleanTitle, "url": videoUrl, "desc": full_desc, "need_resolve": 1})
            self.addVideo(params)
        else:
            printDBG("IFilmArabicHost: No video URL found for this movie")
            self.addMarker({"title": L + "! لا يوجد فيديو متاح حالياً لهذا الفيلم" + W, "desc": full_desc})

    def listKidsContent(self, cItem):
        printDBG("IFilmArabicHost.listKidsContent")
        url = cItem.get("url", "")
        page = self.cm.ph.getSearchGroups(url, "page=(\d+)")[0]
        if not page:
            page = "1"
        sts, data = self.getPage(url)
        if not sts:
            return
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, "<a", "</a>")
        unique_ids = []
        items_found = False
        for item in items:
            if "panel-inner-small" in item or "Jashnvarh-slider-item" in item:
                itemUrl = self.cm.ph.getSearchGroups(item, """href=['"]([^'"]+?)['"]""")[0]
                if not itemUrl:
                    continue
                content_id = self.cm.ph.getSearchGroups(itemUrl, r"Content/(\d+)/")[0]
                if content_id:
                    if content_id in unique_ids:
                        continue
                    unique_ids.append(content_id)
                else:
                    clean_url = itemUrl.split("?")[0].lower().strip("/")
                    if clean_url in unique_ids:
                        continue
                    unique_ids.append(clean_url)
                title = self.cm.ph.getDataBeetwenMarkers(item, "<h4>", "</h4>")[1]
                title = self.cm.ph.cleanHtmlStr(title).strip()
                if not title:
                    continue
                match = re.search(r"(.+?)\s*\(([^)]+)\)", title)
                colored_title = "{0}{1} {2}({3}){4}".format(Y, match.group(1).strip(), C, match.group(2).strip(), W) if match else Y + title + W
                icon = self.cm.ph.getSearchGroups(item, r"url\(&quot;([^&]+?)&quot;\)")[0]
                if not icon:
                    icon = self.cm.ph.getSearchGroups(item, """src=['"]([^'"]+?)['"]""")[0]

                def encode_url(u):
                    full_u = self.getFullUrl(u)
                    try:
                        if any(ord(char) > 128 for char in full_u):
                            prot, rest = full_u.split("://", 1)
                            domain, path = rest.split("/", 1)
                            full_u = prot + "://" + domain + "/" + quote(path.encode("utf-8"))
                    except Exception:
                        pass
                    return full_u

                final_item_url = encode_url(itemUrl)
                final_icon_url = encode_url(icon)
                self.addDir({"name": "category", "category": "episodes", "title": colored_title, "url": final_item_url, "icon": final_icon_url, "desc": Y + title + W + " - [أطفال آي فيلم]"})
                items_found = True
        if not items_found:
            self.addMarker({"title": R + _("! لا توجد مسلسلات أطفال متاحة في هذه الصفحة حالياً") + W, "desc": Y + _("ربما يتم تحديث القسم أو أن هناك عطلاً في المصدر.") + W})
        if items_found:
            next_page_num = str(int(page) + 1)
            if "page=" + next_page_num in data:
                nextUrl = url.replace("page=" + page, "page=" + next_page_num) if "page=" in url else url + "&page=" + next_page_num
                self.addDir({"name": "category", "category": "kids", "title": L + _("Next Page »»»") + W, "url": nextUrl})

    def getLinksForVideo(self, cItem):
        printDBG("IFilmArabicHost.getLinksForVideo [%s]" % cItem)
        videoUrl = cItem.get("url", "").strip()
        linksTab = []
        if ".mp4" in videoUrl.lower() and ".m3u8" not in videoUrl.lower():
            url = self.up.decorateUrl(videoUrl, {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://ar.ifilmtv.ir/"})
            linksTab.append({"name": "ifilm [Direct MP4]", "url": url, "need_resolve": 0})
            return linksTab
        if "master.m3u8" in videoUrl:
            sts, data = self.getPage(videoUrl)
            if sts:
                found = re.findall(r"RESOLUTION=(\d+x\d+).*?\n(http[^\s\n]+)", data, re.S)
                for res, url in found:
                    quality = res.split("x")[-1] + "p"
                    fullUrl = self.up.decorateUrl(url.strip(), {"User-Agent": "Mozilla/5.0", "Referer": "https://ar.ifilmtv.ir/"})
                    linksTab.append({"name": "ifilm [%s]" % quality, "url": fullUrl, "need_resolve": 0})
        if not linksTab and ".m3u8" in videoUrl:
            url = self.up.decorateUrl(videoUrl, {"User-Agent": "Mozilla/5.0", "Referer": "https://ar.ifilmtv.ir/"})
            linksTab.append({"name": "ifilm-hls [Auto]", "url": url, "need_resolve": 0})
        if not linksTab and self.up.checkHostSupport(videoUrl) == 1:
            return self.up.getVideoLinkExt(videoUrl)
        return linksTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("IFilmArabicHost.listSearchResult")
        url = "https://ar.ifilmtv.ir/Home/Search?searchstring=" + quote(searchPattern)
        params = {"header": {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json", "Referer": "https://ar.ifilmtv.ir/"}}
        sts, data = self.getPage(url, params)
        if not sts:
            return
        try:
            results = json.loads(data)
            unique_ids = []
            for item in results:
                catId = item.get("CategoryId", 0)
                if catId not in [3, 5, 7]:
                    continue
                id = str(item.get("Id", ""))
                if not id or id in unique_ids:
                    continue
                unique_ids.append(id)
                title = item.get("Title", "")
                title = self.cm.ph.cleanHtmlStr(title).strip()
                if not title:
                    continue
                section_name = ""
                if catId == 3:
                    if any(word in title for word in ["حكايات", "مغامرات", "كرتون", "سكرستان", "تابتا"]):
                        section_name = "قسم أطفال آي فيلم"
                    else:
                        section_name = "قسم المسلسلات"
                elif catId == 5:
                    section_name = "قسم الأفلام"
                elif catId == 7:
                    section_name = "قسم البرامج"
                full_desc = "{0} - [{1}]".format(title, section_name)
                match = re.search(r"(.+?)\s*\(([^)]+)\)", title)
                colored_title = "{0}{1} {2}({3}){4}".format(Y, match.group(1).strip(), C, match.group(2).strip(), W) if match else Y + title + W

                def fix_encoding(u):
                    full_u = self.getFullUrl(u)
                    try:
                        if any(ord(char) > 128 for char in full_u):
                            prot, rest = full_u.split("://", 1)
                            domain, path = rest.split("/", 1)
                            full_u = prot + "://" + domain + "/" + quote(path.encode("utf-8"))
                    except Exception:
                        pass
                    return full_u

                icon = item.get("ImageAddress_S", "")
                if catId == 3:
                    itemUrl = "/Series/Content/" + id + "/"
                    category = "episodes"
                elif catId == 5:
                    itemUrl = "/Movies/Content/" + id + "/"
                    category = "video"
                elif catId == 7:
                    itemUrl = "/Series/Content/" + id + "/"
                    category = "episodes"
                self.addDir({"name": "category", "category": category, "title": colored_title, "url": fix_encoding(itemUrl), "icon": fix_encoding(icon), "desc": L + full_desc + W})
        except Exception as e:
            printDBG("Search Error: " + str(e))

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("IFilmArabicHost.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: >> name[%s], category[%s]" % (name, category))
        self.currList = []
        if name == None:
            self.listMainMenu({"name": "category"})
        elif category == "live":
            self.listLiveStreams(self.currItem)
        elif category == "series":
            self.listContent(self.currItem, "series")
        elif category == "movies":
            self.listContent(self.currItem, "movies")
        elif category == "movie_details":
            self.listMovies(self.currItem)
        elif category == "programs":
            self.listContent(self.currItem, "programs")
        elif category == "kids":
            self.listKidsContent(self.currItem)
        elif category == "episodes":
            self.listEpisodes(self.currItem)
        elif category == "video":
            links = self.getLinksForVideo(self.currItem)
            if links:
                self.listsTab(links, self.currItem)
            else:
                params = {"name": "category", "category": "video", "title": self.currItem.get("title", ""), "url": self.currItem.get("url", ""), "icon": self.currItem.get("icon", self.DEFAULT_ICON_URL), "desc": self.currItem.get("desc", "")}
                self.addVideo(params)
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
        CHostBase.__init__(self, IFilmArabicHost(), True, [])
