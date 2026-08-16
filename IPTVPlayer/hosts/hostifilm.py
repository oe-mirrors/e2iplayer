# -*- coding: utf-8 -*-
# Last modified: 12/03/2026
# iFilm Host (Modified By Mohamed Elsafty)
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs import ph
import re
import json

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

# Constants
C = E2ColoR("cyan")
L = E2ColoR("lime")
O = E2ColoR("orange")
R = E2ColoR("red")
W = E2ColoR("white")
Y = E2ColoR("yellow")
RESULT_TOKEN = "result[i]"
PAGE_PARAM = "page="
SERIES_CONTENT = "/Series/Content/"
MOVIES_CONTENT = "/Film/Content/"
COLOR_TITLE_FORMAT = "{0}{1} {2}({3}){4}"


def gettytul():
    return "https://ar.ifilmtv.ir/"


class IFilmArabicHost(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "ifilmarabic", "cookie": "ifilmarabic.cookie"})
        self.MAIN_URL = gettytul()
        self.STREAM_URL = "https://live.presstv.ir/hls/"
        self.LIVE_URL = self.MAIN_URL + "Home/Live"
        self.SEARCH_URL = self.MAIN_URL + "Search/Content?q="
        self.SERIES_URL = self.MAIN_URL + "Series"
        self.MOVIES_URL = self.MAIN_URL + "Film"
        self.PROGRAMS_URL = self.MAIN_URL + "Program"
        self.KIDS_URL = self.MAIN_URL + "News/Tag?id=18379&page=1"
        self.CLIPS_URL = self.MAIN_URL + "Music/Clips"
        self.ARTIST_URL = self.MAIN_URL + "artist/Index?id="
        self.DEFAULT_ICON_URL = self.MAIN_URL + "img/colorize-logo-final.png"
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
            {"category": "live", "title": "البث المباشر", "url": self.LIVE_URL},
            {"category": "series", "title": "المسلسلات", "url": self.SERIES_URL},
            {"category": "movies", "title": "الأفلام", "url": self.MOVIES_URL},
            {"category": "programs", "title": "البرامج", "url": self.PROGRAMS_URL},
            {"category": "kids", "title": "أطفال آي فيلم", "url": self.KIDS_URL},
            {"category": "clips", "title": "كليبات", "url": self.CLIPS_URL},
            {"category": "artists_main", "title": "الفنانين", "url": self.ARTIST_URL},
        ] + self.searchItems()
        self.LIVE_STREAMS = [
            {"name": "iFilm Arabic", "url": self.STREAM_URL + "ifilmar.m3u8"},
            {"name": "iFilm Persian", "url": self.STREAM_URL + "ifilmfa.m3u8"},
            {"name": "iFilm 2 Persian", "url": self.STREAM_URL + "ifilm2.m3u8", "icon": "https://fa2.ifilmtv.ir/img/Logoifilm2.png"},
            {"name": "iFilm English", "url": self.STREAM_URL + "ifilmen.m3u8"},
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
                colored_title = C + name + W
            elif "English" in name:
                colored_title = L + name + W
            elif "Persian" in name:
                colored_title = O + name + W
            else:
                colored_title = name
            stream_icon = stream.get("icon", self.DEFAULT_ICON_URL)
            params = {"name": "category", "category": "video", "title": colored_title, "url": stream["url"], "icon": stream_icon, "desc": Y + "بث مباشر جودة عالية باللغة المختارة" + W}
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
                        YEAR_REGEX = re.compile(r"(.+?)\s*\(([^)]+)\)")
                        match = YEAR_REGEX.search(title)
                        colored_title = COLOR_TITLE_FORMAT.format(Y, match.group(1).strip(), C, match.group(2).strip(), W) if match else Y + title + W
                        icon = item.get("ImageAddress_M", "")
                        if icon:
                            icon = self.getFullUrl(icon)
                            icon = quote(icon.encode("utf-8"), safe=":/")
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
            if RESULT_TOKEN in item:
                continue
            if "inner-panel" not in item and "panel-inner-small" not in item:
                continue
            itemUrl = self.cm.ph.getSearchGroups(item, """href=['"]([^'"]+?)['"]""")[0]
            if not itemUrl or itemUrl == "#" or RESULT_TOKEN in itemUrl:
                continue
            itemUrl = self.getFullUrl(itemUrl)
            title = self.cm.ph.getDataBeetwenMarkers(item, "<h6>", "</h6>")[1]
            title = self.cm.ph.cleanHtmlStr(title).strip()
            if not title:
                continue
            YEAR_REGEX = re.compile(r"(.+?)\s*\(([^)]+)\)")
            match = YEAR_REGEX.search(title)
            colored_title = COLOR_TITLE_FORMAT.format(Y, match.group(1).strip(), C, match.group(2).strip(), W) if match else Y + title + W
            icon = self.cm.ph.getSearchGroups(item, """src=['"]([^'"]+?)['"]""")[0]
            if not icon or RESULT_TOKEN in icon:
                icon = self.cm.ph.getSearchGroups(item, r"""url\(&quot;([^&]+?)&quot;\)""")[0]
            if icon and RESULT_TOKEN not in icon:
                icon = self.getFullUrl(icon)
                icon = quote(icon.encode("utf-8"), safe=":/")
            if "/Film/" in itemUrl:
                new_category = "movie_details"
            else:
                new_category = "episodes"
            self.addDir({"name": "category", "category": new_category, "title": colored_title, "url": itemUrl, "icon": icon})
            numItems += 1
        if numItems > 0 and "PageingItem" not in baseUrl:
            page = self.cm.ph.getSearchGroups(baseUrl, PAGE_PARAM + r"(\d+)")[0]
            if page == "":
                page = "1"
            nextPage = int(page) + 1
            nextUrl = baseUrl.replace(PAGE_PARAM + page, PAGE_PARAM + str(nextPage)) if PAGE_PARAM in baseUrl else (baseUrl + ("&" if "?" in baseUrl else "?") + PAGE_PARAM + str(nextPage))
            self.addDir({"name": "category", "category": nextCategory, "title": L + _("Next Page") + " »»» (%d)" % nextPage, "url": nextUrl})

    def listEpisodes(self, cItem):
        printDBG("IFilmArabicHost.listEpisodes")
        url = cItem.get("url", "")
        sts, data = self.getPage(url)
        if not sts:
            printDBG("IFilmArabicHost: Page request failed, trying fallback ID")
            seriesId = self.cm.ph.getSearchGroups(url + "/", r"Content/(\d+)")[0]
            if seriesId:
                fallback_url = self.getFullUrl(SERIES_CONTENT + seriesId)
                sts, data = self.getPage(fallback_url)
        if not sts:
            self.addMarker({"title": L + "! عذراً، هذا المحتوى غير متاح حالياً (خطأ في الاتصال)" + W, "desc": Y + "المصدر لا يستجيب للطلب، يرجى المحاولة لاحقاً." + W})
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
            printDBG("IFilmArabicHost: Checking for main player video...")
        mainVideoUrl = self.cm.ph.getSearchGroups(data, r'<source[^>]+?src="([^"]+?\.mp4)"')[0]
        if not mainVideoUrl:
            mainVideoUrl = self.cm.ph.getSearchGroups(data, r'data-plyr="download"[^>]+?href="([^"]+?\.mp4)"')[0]
        if mainVideoUrl:
            mainVideoUrl = self.getFullUrl(mainVideoUrl)
            mainIcon = self.cm.ph.getSearchGroups(data, r'poster="([^"]+?)"')[0]
            mainIcon = self.getFullUrl(mainIcon) if mainIcon else cItem.get("icon", "")
            self.addVideo({"title": L + _("Trailer") + W, "url": mainVideoUrl, "icon": mainIcon, "desc": full_desc, "need_resolve": 1})
        numEpisodes = self.cm.ph.getSearchGroups(data, r"var\s+inter_\s*=\s*(\d+)")[0]
        lang = self.cm.ph.getSearchGroups(data, r'var\s+langE\s*=\s*["\']([^"\']+)["\']')[0]
        if lang == "fa":
            lang = ""
        if seriesId and numEpisodes and int(numEpisodes) > 0:
            printDBG("IFilmArabicHost: Using Script Method (Classic)")
            for i in range(1, int(numEpisodes) + 1):
                title = C + "▶ " + Y + "الحلقة: " + W + str(i)
                icon = "https://preview.presstv.ir/ifilm/%s%s/%s.png" % (lang, seriesId, i)
                icon = self.up.decorateUrl(icon, {"Referer": self.MAIN_URL, "User-Agent": "Mozilla/5.0"})
                videoUrl = "https://vod.ifilmtv.ir/hls/%s%s/,%s,%s_320,.mp4.urlset/master.m3u8" % (lang, seriesId, i, i)
                self.addVideo({"title": title, "url": videoUrl, "icon": icon, "desc": full_desc, "need_resolve": 1})
                episodes_found = True
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
                            title = C + "▶ " + Y + "الحلقة: " + W + episode_num
                            videoUrl = item.get("VideoAddress", "")
                            if videoUrl:
                                if not videoUrl.startswith("http"):
                                    videoUrl = "https://fa.ifilmtv.ir/" + videoUrl
                                icon = self.getFullUrl(item.get("ImageAddress_M", ""))
                                self.addVideo({"title": title, "url": videoUrl, "icon": icon, "desc": full_desc, "need_resolve": 1})
                                episodes_found = True
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
            self.addMarker({"title": L + "! لا توجد فيديوهات متاحة حالياً لهذا العمل" + W, "desc": Y + "يبدو أن الحلقات لم يتم رفعها بعد في هذا القسم من المصدر." + W})

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
        videoUrl = self.cm.ph.getSearchGroups(data, r'<source\s+src=["\']([^"\']+\.mp4[^"\']*)["\']')[0]
        if not videoUrl:
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
        page = self.cm.ph.getSearchGroups(url, r"page=(\d+)")[0]
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
                YEAR_REGEX = re.compile(r"(.+?)\s*\(([^)]+)\)")
                match = YEAR_REGEX.search(title)
                colored_title = COLOR_TITLE_FORMAT.format(Y, match.group(1).strip(), C, match.group(2).strip(), W) if match else Y + title + W
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
            self.addMarker({"title": L + "! لا توجد مسلسلات أطفال متاحة في هذه الصفحة حالياً" + W, "desc": Y + "ربما يتم تحديث القسم أو أن هناك عطلاً في المصدر." + W})
        if items_found:
            next_page_num = str(int(page) + 1)
            if PAGE_PARAM + next_page_num in data:
                nextUrl = url.replace(PAGE_PARAM + page, PAGE_PARAM + next_page_num) if PAGE_PARAM in url else url + "&page=" + next_page_num
                self.addDir({"name": "category", "category": "kids", "title": L + _("Next Page") + " »»»" + W, "url": nextUrl})

    def listClips(self, cItem):
        printDBG("IFilmArabicHost.listClips")
        page = cItem.get("page", 1)
        url = "https://ar.ifilmtv.ir/Music/GetTracksBy?type=15&size=30&page=%s&id=" % page
        params = dict(self.defaultParams)
        params["header"] = dict(self.defaultParams["header"])
        params["header"].update({"X-Requested-With": "XMLHttpRequest"})
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return
        try:
            result = json.loads(data)
            for item in result:
                title = item.get("Caption", "")
                icon = self.getFullUrl(item.get("ImageAddress_M", ""))
                url = self.getFullUrl(item.get("VideoAddress", ""))
                desc = item.get("Discription", "")
                if url == "":
                    continue
                params = {
                    "title": L + title + W,
                    "url": url,
                    "icon": icon,
                    "desc": desc,
                }
                self.addVideo(params)
            if len(result) >= 30:
                params = dict(cItem)
                params.update({"title": Y + _("Next Page") + " »»»" + W, "page": page + 1})
                self.addDir(params)
        except Exception:
            printExc()

    def listArtistsMain(self, cItem):
        printDBG("IFilmArabicHost.listArtistsMain")
        params = dict(cItem)
        params.update({"category": "artists_list", "title": "المخرجون", "url": self.ARTIST_URL + "1", "page": 1})
        self.addDir(params)
        params = dict(cItem)
        params.update({"category": "artists_list", "title": "الممثلون", "url": self.ARTIST_URL + "2", "page": 1})
        self.addDir(params)

    def listArtistsItems(self, cItem):
        printDBG("IFilmArabicHost.listArtistsItems")
        page = cItem.get("page", 1)
        url = cItem["url"]
        if not url.startswith("http"):
            url = self.getFullUrl(url)
        if "?" not in url:
            requestUrl = url + "?sort=0&page=" + str(page)
        elif "&page=" not in url:
            requestUrl = url + "&sort=0&page=" + str(page)
        else:
            requestUrl = re.sub(r"page=\d+", PAGE_PARAM + str(page), url)
        sts, data = self.cm.getPage(requestUrl, self.defaultParams)
        if not sts:
            return
        artistsList = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a href="/artist/Content/', "</a>")
        for item in artistsList:
            url_part = self.cm.ph.getSearchGroups(item, 'href="([^"]+)"')[0]
            if not url_part:
                continue
            full_url = self.getFullUrl(url_part)
            title = self.cm.ph.getDataBeetwenMarkers(item, "<h3>", "</h3>")[1]
            title = self.cm.ph.cleanHtmlStr(title).strip()
            icon = self.cm.ph.getSearchGroups(item, 'src="([^"]+)"')[0]
            if icon:
                icon = self.getFullUrl(icon)
                icon = quote(icon.encode("utf-8"), safe=":/?&=")
            if not title:
                continue
            params = dict(cItem)
            params.update({"title": title, "url": full_url, "icon": icon, "category": "artist_details"})
            self.addDir(params)
        totalPages = self.cm.ph.getSearchGroups(data, r"totalPages:\s*(\d+)")[0]
        if totalPages == "":
            totalPages = self.cm.ph.getSearchGroups(data, r"TotalPages\s*=\s*(\d+)")[0]
        if totalPages and int(page) < int(totalPages):
            params = dict(cItem)
            params.update({"title": Y + _("Next Page") + " »»»" + W, "page": page + 1, "url": url})
            self.addDir(params)

    def listArtistDetails(self, cItem):
        printDBG("IFilmArabicHost.listArtistDetails start")
        sts, data = self.cm.getPage(cItem["url"], self.defaultParams)
        if not sts:
            return
        artistDesc = self.cm.ph.getDataBeetwenMarkers(data, '<div id="wrapper"', "</div>", False)[1]
        artistDesc = artistDesc.replace("</p>", "\n")
        artistDesc = self.cm.ph.cleanHtmlStr(artistDesc).strip()
        artistDesc = re.sub(r"\n\s*\n", "\n", artistDesc)
        data = self.cm.ph.getDataBeetwenMarkers(data, '<div class="artist-movies-panel">', "</footer>", False)[1]
        workBlocks = re.findall(r'<div class="panel-inner-movies">(.*?)</div>\s*</div>', data, re.S)
        if not workBlocks:
            self.addMarker({"title": L + "! لا يوجد أعمال متاحة حاليا" + W, "desc": artistDesc, "icon": cItem.get("icon", "")})
            return
        for i, block in enumerate(workBlocks):
            url = self.cm.ph.getSearchGroups(block, r'href="([^"]+)"')[0]
            if url == "":
                continue
            title = self.cm.ph.getSearchGroups(block, r'class="neme-movie"[^>]*>([^<]+)')[0]
            title = self.cm.ph.cleanHtmlStr(title).strip()
            YEAR_REGEX = re.compile(r"(.+?)\s*\(([^)]+)\)")
            match = YEAR_REGEX.search(title)
            if match:
                colored_title = COLOR_TITLE_FORMAT.format(Y, match.group(1).strip(), C, match.group(2).strip(), W)
            else:
                colored_title = Y + title + W
            icon = self.cm.ph.getSearchGroups(block, r'src=["\']?([^"\'>]+)')[0]
            url = self.getFullUrl(url)
            if icon:
                icon = self.getFullUrl(icon)
                icon = quote(icon.encode("utf-8"), safe=":/?&=")
            if "/Film/" in url:
                category = "movie_details"
            elif "/Series/" in url:
                category = "episodes"
            else:
                continue
            params = dict(cItem)
            params.update({"title": colored_title, "url": url, "icon": icon, "desc": L + artistDesc[:900] + "...." + W, "category": category})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("IFilmArabicHost.getLinksForVideo [%s]" % cItem)
        videoUrl = cItem.get("url", "").strip()
        linksTab = []
        if ".mp4" in videoUrl.lower() and ".m3u8" not in videoUrl.lower():
            url = self.up.decorateUrl(videoUrl, {"User-Agent": "Mozilla/5.0", "Referer": self.MAIN_URL})
            linksTab.append({"name": "ifilm [Direct MP4]", "url": url, "need_resolve": 0})
            return linksTab
        if ".m3u8" in videoUrl:
            try:
                playlist = getDirectM3U8Playlist(videoUrl, checkExt=False, variantCheck=True, cookieParams={"header": self.HTTP_HEADER})
            except Exception:
                playlist = []
            if playlist:
                for item in playlist:
                    try:
                        bitrate = int(item.get("bitrate", 0))
                    except Exception:
                        bitrate = 0
                    if bitrate >= 2000000:
                        continue
                    name = item.get("name", "HLS")
                    url = self.up.decorateUrl(item["url"], {"User-Agent": "Mozilla/5.0", "Referer": self.MAIN_URL})
                    linksTab.append({"name": "iFilm [%s]" % name, "url": url, "need_resolve": 0})
            if not linksTab:
                linksTab.append({"name": "المشكلة من موقع iFilm - الفيديو غير متاح حالياً", "url": "", "need_resolve": 0})
        elif self.up.checkHostSupport(videoUrl) == 1:
            return self.up.getVideoLinkExt(videoUrl)
        return linksTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("IFilmArabicHost.listSearchResult")
        url = self.MAIN_URL + "Home/Search?searchstring=" + quote(searchPattern)
        params = {
            "header": {
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
                "Referer": self.MAIN_URL,
            }
        }
        sts, data = self.getPage(url, params)
        if not sts:
            return
        items_found = False
        try:
            results = json.loads(data)
            unique_ids = []
            if results and len(results) > 0:
                for item in results:
                    catId = item.get("CategoryId", 0)
                    if catId not in [3, 5, 7]:
                        continue
                    item_id = str(item.get("Id", ""))
                    if not item_id or item_id in unique_ids:
                        continue
                    unique_ids.append(item_id)
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
                    YEAR_REGEX = re.compile(r"(.+?)\s*\(([^)]+)\)")
                    match = YEAR_REGEX.search(title)
                    colored_title = COLOR_TITLE_FORMAT.format(Y, match.group(1).strip(), C, match.group(2).strip(), W) if match else Y + title + W

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
                    if catId == 5:
                        itemUrl = MOVIES_CONTENT + item_id + "/"
                        category = "movie_details"
                    else:
                        itemUrl = SERIES_CONTENT + item_id + "/"
                        category = "episodes"
                    self.addDir({"name": "category", "category": category, "title": colored_title, "url": fix_encoding(itemUrl), "icon": fix_encoding(icon), "desc": L + full_desc + W})
                    items_found = True
            if not items_found:
                self.addMarker({"title": C + "! عذراً، لا توجد نتائج للبحث عن: " + Y + searchPattern + W, "desc": Y + "تأكد من كتابة الكلمة بشكل صحيح أو جرب كلمات بحث أخرى." + W})
        except Exception as e:
            printDBG("Search Error: " + str(e))
            self.addMarker({"title": R + "خطأ في جلب البيانات من المصدر" + W})

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("IFilmArabicHost.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: >> name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
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
        elif category == "clips":
            self.listClips(self.currItem)
        elif category == "artists_main":
            self.listArtistsMain(self.currItem)
        elif category == "artists_list":
            self.listArtistsItems(self.currItem)
        elif category == "artist_details":
            self.listArtistDetails(self.currItem)
        elif category == "video":
            links = self.getLinksForVideo(self.currItem)
            if links:
                self.listsTab(links, self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, IFilmArabicHost(), True, [])
