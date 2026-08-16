# -*- coding: utf-8 -*-
# Last modified: 17/10/2025 - popking (odem2014)
# typical import for a standard host
###################################################
# LOCAL import
###################################################
# localization library
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _

# host main class
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass

# tools - write on log, write exception infos and merge dicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR

# add metadata to url
# library for json (instead of standard json.loads and json.dumps)
# read informations in m3u8
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus

###################################################
# FOREIGN import
###################################################
import re
import time
import base64


###################################################
def GetConfigList():
    return []


def gettytul():
    return "https://mycima.boo/"  # main url of host


class MyCima(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "mycima", "cookie": "mycima.cookie"})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + "search/"
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/mycima.jpg"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams=None, post_data=None):
        # Handle unicode URLs safely
        if any(ord(c) > 127 for c in baseUrl):
            baseUrl = urllib_quote_plus(baseUrl, safe="://")
        if addParams is None:
            addParams = dict(self.defaultParams)
        # Always re-init CF parameters
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        # For GET requests: reload cookie each time
        if post_data is None:
            addParams["load_cookie"] = False  # don’t reuse
            addParams["save_cookie"] = True  # save new one
        max_retries = 3
        for attempt in range(max_retries):
            try:
                sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
                if sts and data:
                    return sts, data
            except Exception as e:
                printDBG("MyCima.getPage retry %d failed: %s" % (attempt + 1, str(e)))
            # Cloudflare timing window delay
            time.sleep(1.5)
        printDBG(f"[MyCima] Retrying {baseUrl} failed after {max_retries} attempts due to timeout.")
        return False, ""

    ###################################################
    # MAIN MENU
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("MyCima.listMainMenu")
        MAIN_CAT_TAB = [{"category": "movies_categories", "title": "الافلام"}, {"category": "series_categories", "title": "المسلسلات"}, {"category": "anime_categories", "title": "الكارتون"}, {"category": "other_categories", "title": "Others"}]
        self.listsTab(MAIN_CAT_TAB, cItem)
        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [{"category": "list_movies", "title": "افلام اجنبية", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/")}, {"category": "list_movies", "title": "افلام عربية", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%b9%d8%b1%d8%a8%d9%8a/")}, {"category": "list_movies", "title": "افلام هندية", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%87%d9%86%d8%af%d9%8a/")}, {"category": "list_movies", "title": "افلام تركية", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/")}, {"category": "list_movies", "title": "افلام اسيوية", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/")}]
        self.SERIES_CAT_TAB = [
            {"category": "list_series", "title": "مسلسلات اجنبية", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/")},
            {"category": "list_series", "title": "مسلسلات عربية", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b9%d8%b1%d8%a8%d9%8a/")},
            {"category": "list_series", "title": "مسلسلات هندية", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%87%d9%86%d8%af%d9%8a%d8%a9/")},
            {"category": "list_series", "title": "مسلسلات تركية", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/")},
            {"category": "list_series", "title": "مسلسلات اسيوية", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/")},
            {"category": "list_series", "title": "مسلسلات مدبلجة", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/")},
            {"category": "list_series", "title": "مسلسلات رمضان 2026", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2026/")},
            {"category": "list_series", "title": "مسلسلات رمضان 2025", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2025/")},
            {"category": "list_series", "title": "مسلسلات رمضان 2024", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2024/")},
            {"category": "list_series", "title": "مسلسلات رمضان 2023", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2023/")},
        ]
        self.ANIME_CAT_TAB = [{"category": "list_anime", "title": "افلام كارتون", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%85%d9%8a/")}, {"category": "list_anime", "title": "مسلسلات كارتون", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d9%86%d9%85%d9%8a/")}]
        self.OTHER_CAT_TAB = [{"category": "list_other", "title": "مصارعة", "url": self.getFullUrl("/category/%d8%b9%d8%b1%d9%88%d8%b6-%d9%85%d8%b5%d8%a7%d8%b1%d8%b9%d8%a9/")}, {"category": "list_other", "title": "برامج تليفزيونية", "url": self.getFullUrl("/category/%d8%a8%d8%b1%d8%a7%d9%85%d8%ac-%d8%aa%d9%84%d9%81%d8%b2%d9%8a%d9%88%d9%86%d9%8a%d8%a9/")}]

    def listMoviesCategories(self, cItem):
        printDBG("MyCima.listMoviesCategories")
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesCategories(self, cItem):
        printDBG("MyCima.listMoviesCategories")
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listAnimeCategories(self, cItem):
        printDBG("MyCima.listAnimeCategories")
        self.listsTab(self.ANIME_CAT_TAB, cItem)

    def listOtherCategories(self, cItem):
        printDBG("MyCima.listOtherCategories")
        self.listsTab(self.OTHER_CAT_TAB, cItem)

    ###################################################
    # LIST UNITS FROM CATEGORY PAGE (WITH PAGINATION)
    ###################################################
    def listUnits(self, cItem):
        printDBG("MyCima.listUnits >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        # printDBG('data.listUnits >>> %s' % data)
        if not sts or not data:
            printDBG("listUnits: failed to load page")
            return
        ###################################################
        # MAIN MOVIE BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="Grid--WecimaPosts"', '<script type="speculationrules">', False)[1]
        # printDBG('main_block.listUnits >>> %s' % main_block)
        if not main_block:
            printDBG("listUnits: No main_block found")
            return
        ###################################################
        # MOVIE BOXES
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="GridItem"', '<ul class="PostItemStats">')
        # items2 = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="GridItem"', '<ul class="PostItemStats">')[1]
        # printDBG('items2.listUnits >>> %s' % items2)
        printDBG("listUnits: Found %d items" % len(items))
        for item in items:
            # --- URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            # --- ICON FIX ---
            icon = self.cm.ph.getSearchGroups(item, r'data-lazy-style="[^"]*url\(([^)]+)\)')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r'src="([^"]+)"')[0]
            icon = self.getFullUrl(icon)
            printDBG("icon.listUnits >>> %s" % icon)
            # --- TITLE ---
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<strong", "</strong>", False)[1])
            title = title.replace("مشاهدة فيلم", "").replace("مشاهدة", "").replace("فيلم", "").replace("مسلسل", "").replace("مترجمة اون لاين", "").replace("مترجم اون لاين", "").replace("مترجمة", "").replace("مترجم", "").replace("اون لاين", "").replace("مدبلجة", "").replace("مدبلج", "").strip()
            printDBG("title.listUnits >>> %s" % title)
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<strong dir="auto" class="hasyear">', "</strong>", False)[1])
            if not desc:
                desc = title
            desc = desc.replace(" ", "").strip()
            year = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<span class="year">', "</span>", False)[1])
            year = year.replace("(", "").replace(")", "").strip()
            desc = desc + "(" + year + ")"
            # --- QUALITY ---
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<em class="ribbon">', "</em>", False)[1])
            printDBG("quality.listUnits >>> %s" % quality)
            ###################################################
            # COLORIZE TITLE (movie name + year)
            ###################################################
            match = re.search(r"(.+?)\s*\(?(\d{4})\)?$", title)
            if match:
                movie_title = match.group(1).strip()
                movie_year = match.group(2).strip()
                colored_title = f"{E2ColoR('yellow')}{movie_title} " f"{E2ColoR('cyan')}{movie_year}" f"{E2ColoR('white')}"
            else:
                colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"
            ###################################################
            # COLORIZE QUALITY
            ###################################################
            q_color = "white"
            if re.search(r"4K|1080|BluRay", quality, re.I):
                q_color = "green"
            elif re.search(r"720|HDRip|WEB", quality, re.I):
                q_color = "yellow"
            elif re.search(r"CAM|TS|HDCAM", quality, re.I):
                q_color = "red"
            colored_quality = f"{E2ColoR(q_color)}{quality if quality else 'N/A'}{E2ColoR('white')}"
            ###################################################
            # FINAL ITEM
            ###################################################
            params = dict(cItem)
            params.update({"title": colored_title, "url": self.getFullUrl(url), "icon": icon, "desc": f"{colored_quality} | {desc}", "category": "explore_items"})
            self.addDir(params)
        if len(items) == 0:
            printDBG("listUnits: No media-card items found")
        ###################################################
        # PAGINATION
        ###################################################
        pagination_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', "</div>", False)[1]
        if pagination_block:
            next_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
            prev_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="prev page-numbers"[^>]+href="([^"]+)"')[0]
            if prev_url:
                params = dict(cItem)
                params.update({"title": "<<< " + _("Previous"), "url": self.getFullUrl(prev_url), "category": "list_movies"})
                self.addDir(params)
                printDBG("listUnits: Found previous page %s" % prev_url)
            if next_url:
                params = dict(cItem)
                params.update({"title": _("Next") + " >>>", "url": self.getFullUrl(next_url), "category": "list_movies"})
                self.addDir(params)
                printDBG("listUnits: Found next page %s" % next_url)

    ###################################################
    # EXPLORE ITEM (get list of servers)
    ###################################################
    def exploreItems(self, cItem):
        printDBG("MyCima.exploreItems >>> %s" % cItem)
        url = cItem["url"]
        printDBG("url.exploreItems >>> %s" % url)
        sts, data = self.getPage(url)
        # printDBG('data.exploreItems >>> %s' % data)
        if not sts:
            return
        # Extract the watch list block
        watch_list = self.cm.ph.getDataBeetwenMarkers(data, '<div class="WatchServers"', "</div>", False)[1]
        printDBG("watch_list.exploreItems >>> %s" % watch_list)
        if not watch_list:
            printDBG("No watch list found")
            return
        # Extract all <li> items
        li_items = self.cm.ph.getAllItemsBeetwenMarkers(watch_list, "<li", "</li>")
        printDBG("Found %d servers" % len(li_items))
        for item in li_items:
            # --- Extract data-watch attribute ---
            data_watch = self.cm.ph.getSearchGroups(item, r'data-watch="([^"]+)"')[0]
            printDBG("data_watch.exploreItems >>> %s" % data_watch)
            if not data_watch:
                continue
            # --- Extract the base64 part ---
            # Example: https://sharevid.online/play/aHR0cHM6Ly9taXZhbHlvLmNvbS92L2s5YnAxbmZvNWU4MA==/
            b64_part = self.cm.ph.getSearchGroups(data_watch, r"/play/([^/]+)")[0]
            printDBG("b64_part.exploreItems >>> %s" % b64_part)
            if not b64_part:
                continue
            # --- Decode Base64 safely ---
            try:
                decoded_bytes = base64.b64decode(b64_part)
                decoded_url = decoded_bytes.decode("utf-8", errors="ignore")
                url = decoded_url.strip()
            except Exception as e:
                printDBG("Base64 decode error: %s" % e)
                continue
            printDBG("decoded_url.exploreItems >>> %s" % url)
            # --- Extract server name (text inside <li>) ---
            # Example: <li ...>vikingfile</li>
            title = self.cleanHtmlStr(item)
            if not title:
                title = "Unknown Server"
            printDBG("title.exploreItems >>> %s" % title)
            # --- Final video entry ---
            params = dict(cItem)
            params.update(
                {
                    "title": title,
                    "url": url,
                    "category": "video",
                    "type": "video",
                }
            )
            self.addVideo(params)
        if len(li_items) == 0:
            printDBG("No <li> items found in server-list")

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("MyCima.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return []
        return [{"name": "MyCima - %s" % cItem.get("title", ""), "url": url, "need_resolve": 1}]

    def getVideoLinks(self, url):
        printDBG("MyCima.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    ###################################################
    # SEARCH
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MyCima.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        self.listUnits(cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("MyCima.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []
        # MAIN MENU
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "explore_items":
            self.exploreItems(self.currItem)
        elif category == "movies_categories":
            self.listMoviesCategories(self.currItem)
        elif category == "series_categories":
            self.listSeriesCategories(self.currItem)
        elif category == "anime_categories":
            self.listAnimeCategories(self.currItem)
        elif category == "other_categories":
            self.listOtherCategories(self.currItem)
        elif category == "list_movies":
            self.listUnits(self.currItem)
        elif category == "list_series":
            self.listUnits(self.currItem)
        elif category == "list_anime":
            self.listUnits(self.currItem)
        elif category == "list_other":
            self.listUnits(self.currItem)
        # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        # HISTORY SEARCH
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, MyCima(), True, [])

    def withArticleContent(self, cItem):
        if "video" == cItem.get("type", "") or "explore_item" == cItem.get("category", ""):
            return True
        return False
