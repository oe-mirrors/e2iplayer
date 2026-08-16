# -*- coding: utf-8 -*-
# Last modified: 24/05/2026 - M.Esafty (angel_heart)
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

###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
import re
import time


def GetConfigList():
    return []


def gettytul():
    return "https://b.3isq.cam/"  # main url of host


class Q3isk(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "q3isk", "cookie": "q3isk.cookie"})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + "?s="
        self.DEFAULT_ICON_URL = "https://3d.q9w8e7.shop/wp-content/themes/QisatEishq/UI//Assets/img/logo.webp"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {
            "header": self.HEADER,
            "use_cookie": True,
            "load_cookie": True,
            "save_cookie": True,
            "cookiefile": self.COOKIE_FILE,
        }

    def getPage(self, baseUrl, addParams=None, post_data=None):
        """
        Unified getPage() for Q3isk
        - Handles Unicode / Arabic URLs safely
        - Preserves cookies between requests
        - Integrates Cloudflare protection
        - Retries automatically up to 3 times
        """
        # --- Normalize URL safely (for Arabic / UTF-8 URLs)
        try:
            if not isinstance(baseUrl, str):
                baseUrl = str(baseUrl)
            if any(ord(c) > 127 for c in baseUrl):
                baseUrl = urllib_quote_plus(baseUrl, safe=":/?&=%")
        except Exception as e:
            printDBG("[Q3isk] URL normalization failed: %s" % str(e))
        # --- Prepare request parameters
        if addParams is None:
            addParams = dict(self.defaultParams)
        else:
            tmp = dict(self.defaultParams)
            tmp.update(addParams)
            addParams = tmp
        # --- Always attach Cloudflare parameters
        addParams["cloudflare_params"] = {
            "cookie_file": self.COOKIE_FILE,
            "User-Agent": self.HEADER.get("User-Agent", "Mozilla/5.0"),
        }
        # --- Ensure cookie persistence
        addParams["use_cookie"] = True
        addParams["save_cookie"] = True
        addParams["load_cookie"] = True
        addParams["cookiefile"] = self.COOKIE_FILE
        # --- Retry logic
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
                if sts and data:
                    return sts, data
            except Exception as e:
                printDBG("[Q3isk] getPage attempt %d failed: %s" % (attempt, str(e)))
            time.sleep(1.5)
        printDBG("[Q3isk] getPage failed after %d retries: %s" % (max_retries, baseUrl))
        return False, ""

    ###################################################
    # MAIN MENU
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("Q3isk.listMainMenu")
        MAIN_CAT_TAB = [
            {
                "category": "list_movies",
                "title": "Movies",
                "url": self.getFullUrl("category/افلام-تركية-مترجمة/"),
            },
            {"category": "series_categories", "title": "Series"},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)
        self.SERIES_CAT_TAB = [
            {
                "category": "list_series",
                "title": "Full Series",
                "url": self.getFullUrl("جميع-المسلسلات-2d7ig/"),
            },
            {
                "category": "list_movies",
                "title": "Last Added Episodes",
                "url": self.getFullUrl("آخر-الحلقات-hfgrtjf/"),
            },
        ]

    def listSeriesCategories(self, cItem):
        printDBG("Q3isk.listSeriesCategories")
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def exploreItems(self, cItem):
        printDBG("Q3isk.exploreItems >>> %s" % cItem)
        url = cItem["url"]
        printDBG("url.exploreItems >>> %s" % url)
        sts, data = self.getPage(url)
        printDBG("data.exploreItems >>> %s" % data)
        if not sts or not data:
            printDBG("exploreItems: failed to load page")
            return
        ###################################################
        # MAIN INFO BLOCK (Story + Cast)
        ###################################################
        info_desc = ""
        work_title = ""
        main_info_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="story">', '<div style="clear', True)[1]
        if main_info_block:
            work_title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, "<h1>", "</h1>", False)[1])
            # --- Story ---
            story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(main_info_block, '<div class="story">', "</div>", False)[1])
            tax_info = {}
            all_tax_blocks = re.findall(r'<div class="tax">(.*?)</div>', main_info_block, re.S)
            label_map = {
                "الممثلين": "Cast",
                "السنة": "Year",
                "اللغة": "Lang",
                "التصنيفات": "Category",
                "الأنواع": "Type",
            }
            for tax_block in all_tax_blocks:
                label_match = re.search(r"<span>([^<]+)</span>", tax_block)
                if not label_match:
                    continue
                label_ar = label_match.group(1).strip().replace(":", "").strip()
                values = re.findall(r">([^<]+)</a>", tax_block)
                values = [self.cleanHtmlStr(v) for v in values if v.strip()]
                if label_ar in label_map:
                    tax_info[label_map[label_ar]] = ", ".join(values)
            field_order = ["Category", "Lang", "Year", "Type", "Cast"]
            info_parts = []
            for key in field_order:
                if key in tax_info and tax_info[key]:
                    info_parts.append(f"{E2ColoR('yellow')}{key}:{E2ColoR('white')} {tax_info[key]}")
            if info_parts:
                info_desc = " | ".join(info_parts)
            if story:
                info_desc += f"\n{E2ColoR('yellow')}Story:{E2ColoR('white')} {story}"
        ###################################################
        # MAIN SERVERS BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="watch">', "</ul>", True)[1]
        printDBG("main_block.exploreItems >>> %s" % main_block)
        ###################################################
        # PARSE ITEMS CORRECTLY
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, "<li", "</li>")
        if not items:
            printDBG("exploreItems: no <li> items found!")
            return
        printDBG("exploreItems: Found %d items" % len(items))
        for item in items:
            printDBG("ITEM >>> %s" % item)
            # --- VIDEO URL ---
            video_url = self.cm.ph.getSearchGroups(item, r'data-watch="([^"]+)"')[0]
            if not video_url:
                continue
            video_url = self.getFullUrl(video_url)
            # --- TITLE ---
            server_name = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<em>", "</em>", False)[1])
            if not server_name:
                server_name = _("Server")
            if work_title:
                video_title = f"{E2ColoR('yellow')}{work_title}{E2ColoR('white')} - [{server_name}]"
            else:
                video_title = server_name
            params = dict(cItem)
            params.update(
                {
                    "title": video_title,
                    "url": video_url,
                    "desc": info_desc,
                    "type": "video",
                    "category": "video",
                }
            )
            self.addVideo(params)
        printDBG("exploreItems: completed parsing servers")

    def listSeriesUnits(self, cItem):
        printDBG("Q3isk.listSeriesUnits >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("listSeriesUnits: failed to load page")
            return
        ###################################################
        # MAIN SERIES BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="Small--Box">', '<div class="pagination">', True)[1]
        if not main_block:
            printDBG("listSeriesUnits: No main_block found")
            return
        ###################################################
        # PARSE ITEMS CORRECTLY
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="Small--Box">', "</a>")
        printDBG("listSeriesUnits: Found %d items" % len(items))
        for item in items:
            # URL
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)
            # POSTER
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            icon = self.getFullUrl(icon)
            # TITLE
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="title">', "</div>", False)[1])
            title = title.replace("اون لاين", "")
            # DESCRIPTION
            desc = "%sClick to view episodes%s" % (E2ColoR("yellow"), E2ColoR("white"))
            params = dict(cItem)
            params.update(
                {
                    "title": "%s%s%s" % (E2ColoR("yellow"), title, E2ColoR("white")),
                    "url": url,
                    "icon": icon,
                    "desc": desc,
                    "category": "list_series_episodes",
                }
            )
            self.addDir(params)
        ###################################################
        # PAGINATION FIX (KRMZY STYLE)
        ###################################################
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', "</ul>", True)[1]
        nextPage = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
        if nextPage:
            nextPage = self.getFullUrl(nextPage)
            printDBG("Next page found: %s" % nextPage)
            params = dict(cItem)
            params.update({"title": "Next Page >>", "url": nextPage})
            self.addDir(params)
        else:
            printDBG("No next page found")

    def listSeriesEpisodes(self, cItem):
        printDBG("Q3isk.listSeriesEpisodes >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("listSeriesEpisodes: failed to load page")
            return
        ###################################################
        # MAIN INFO BLOCK (Story + Cast)
        ###################################################
        main_info_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="story">', '<div style="clear', True)[1]
        if main_info_block:
            # --- Poster ---
            info_icon = self.cm.ph.getSearchGroups(data, r'<img[^>]+data-src="([^"]+)"')[0]
            info_icon = self.getFullUrl(info_icon)
            # --- Title ---
            info_title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, "<h1>", "</h1>", False)[1])
            # --- Story ---
            story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(main_info_block, '<div class="story">', "</div>", False)[1])
            tax_info = {}
            all_tax_blocks = re.findall(r'<div class="tax">(.*?)</div>', main_info_block, re.S)
            label_map = {
                "الممثلين": "Cast",
                "السنة": "Year",
                "اللغة": "Lang",
                "التصنيفات": "Category",
                "الأنواع": "Type",
            }
            for tax_block in all_tax_blocks:
                label_match = re.search(r"<span>([^<]+)</span>", tax_block)
                if not label_match:
                    continue
                label_ar = label_match.group(1).strip().replace(":", "").strip()
                values = re.findall(r">([^<]+)</a>", tax_block)
                values = [self.cleanHtmlStr(v) for v in values if v.strip()]
                values_str = ", ".join(values)
                if label_ar in label_map:
                    tax_info[label_map[label_ar]] = values_str
            field_order = ["Category", "Lang", "Year", "Type", "Cast"]
            info_parts = []
            for key in field_order:
                if key in tax_info and tax_info[key]:
                    info_parts.append(f"{E2ColoR('yellow')}{key}:{E2ColoR('white')} {tax_info[key]}")
            if info_parts:
                info_desc = " | ".join(info_parts)
            else:
                info_desc = ""
            if story:
                info_desc += f"\n{E2ColoR('yellow')}Story:{E2ColoR('white')} {story}"
            marker_params = {
                "title": f"{E2ColoR('lime')}{info_title}{E2ColoR('white')}",
                "desc": info_desc,
                "icon": info_icon,
                "type": "marker",
                "good_for_fav": False,
            }
            self.addMarker(marker_params)
        items = re.findall(r'(<div class="Small--Box">.*?</a>)', data, re.S | re.I)
        if not items:
            printDBG("listSeriesEpisodes: Trying regex fallback for episodes")
            items = re.findall(
                r'(<a[^>]+class="[^"]*recent--block[^"]*"[^>]*>.*?</a>)',
                data,
                re.S | re.I,
            )
        if not items:
            sample = re.sub(r"\s+", " ", data[:1500])
            printDBG("CRITICAL: No episodes found! Page sample: %s" % sample)
            return
        printDBG("listSeriesEpisodes: Found %d episodes via direct search" % len(items))
        items.reverse()  # oldest → newest
        for item in items:
            url_match = re.search(r'href="([^"]+)"', item)
            if not url_match:
                continue
            url = url_match.group(1)
            if not url.endswith("see/"):
                url = url + "see/"
            url = self.getFullUrl(url)
            icon = ""
            icon_match = re.search(r'data-src="([^"]+)"', item)
            if icon_match:
                icon = icon_match.group(1)
            else:
                icon_match = re.search(r'src="([^"]+)"', item)
                if icon_match:
                    icon = icon_match.group(1)
            icon = self.getFullUrl(icon)
            title = ""
            title_match = re.search(r'<div class="title">([^<]+)</div>', item)
            if title_match:
                title = title_match.group(1)
            else:
                title_match = re.search(r'title="([^"]+)"', item)
                if title_match:
                    title = title_match.group(1)
            title = self.cleanHtmlStr(title).replace("اون لاين", "").strip()
            if not title:
                title = _("Episode")
            colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"
            params = dict(cItem)
            params.update(
                {
                    "title": colored_title,
                    "url": url,
                    "icon": icon,
                    "category": "explore_item",
                }
            )
            self.addDir(params)

    def listMoviesUnits(self, cItem):
        printDBG("Q3isk.listMoviesUnits >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("listMoviesUnits: failed to load page")
            return
        ###################################################
        # MAIN SERIES BLOCK
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="Small--Box">', '<div class="pagination">', True)[1]
        if not main_block:
            printDBG("listMoviesUnits: No main_block found")
            return
        ###################################################
        # PARSE ITEMS CORRECTLY
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, '<div class="Small--Box">', "</a>")
        printDBG("listMoviesUnits: Found %d items" % len(items))
        for item in items:
            # URL
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            url = url + "see/"
            if not url:
                continue
            url = self.getFullUrl(url)
            # POSTER
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            icon = self.getFullUrl(icon)
            # TITLE
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="title">', "</div>", False)[1])
            title = title.replace("اون لاين", "")
            desc = "%sClick to view episodes%s" % (E2ColoR("yellow"), E2ColoR("white"))
            params = dict(cItem)
            params.update(
                {
                    "title": "%s%s%s" % (E2ColoR("yellow"), title, E2ColoR("white")),
                    "url": url,
                    "icon": icon,
                    "desc": desc,
                    "category": "explore_item",
                }
            )
            self.addDir(params)
        ###################################################
        # PAGINATION FIX (KRMZY STYLE)
        ###################################################
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', "</ul>", True)[1]
        nextPage = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
        if nextPage:
            nextPage = self.getFullUrl(nextPage)
            printDBG("Next page found: %s" % nextPage)
            params = dict(cItem)
            params.update({"title": "Next Page >>", "url": nextPage})
            self.addDir(params)
        else:
            printDBG("No next page found")

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Q3isk.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return []
        return [
            {
                "name": "Q3isk - %s" % cItem.get("title", ""),
                "url": url,
                "need_resolve": 1,
            }
        ]

    def getVideoLinks(self, url):
        printDBG("Q3isk.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    ###################################################
    # SEARCH
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Q3isk.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        self.listMoviesUnits(cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("Q3isk.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []
        # MAIN MENU
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "series_categories":
            self.listSeriesCategories(self.currItem)
        elif category == "movies_categories":
            self.listMoviesCategories(self.currItem)
        elif category == "list_series":
            self.listSeriesUnits(self.currItem)
        elif category == "list_movies":
            self.listMoviesUnits(self.currItem)
        elif category == "explore_item":
            self.exploreItems(self.currItem)
        elif category == "list_series_episodes":
            self.listSeriesEpisodes(self.currItem)
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
        CHostBase.__init__(self, Q3isk(), True, [])

    def withArticleContent(self, cItem):
        if "video" == cItem.get("type", "") or "explore_item" == cItem.get("category", ""):
            return True
        return False
