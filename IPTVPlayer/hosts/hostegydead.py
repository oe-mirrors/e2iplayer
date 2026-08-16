# -*- coding: utf-8 -*-
# Last modified: 24/10/2025 - popking (odem2014)
# Last modified: 17/05/2026 - Mohamed Elsafty (angel_heart)
# typical import for a standard host
###################################################
# LOCAL import
###################################################
# localization library
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _

# host main class
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass

# tools - write on log, write exception infos and merge dicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, E2ColoR

# add metadata to url
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

# library for json (instead of standard json.loads and json.dumps)
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps

# read informations in m3u8
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist

###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
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
    return "https://c4u1r.sbs"  # main url of host


class EgyDead(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "egydead", "cookie": "egydead.cookie"})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + "?s="
        self.DEFAULT_ICON_URL = "https://c4u1r.sbs/wp-content/uploads/2026/03/EgyDead-Logo.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        # Unified words list for cleaning titles
        self.CLEAN_WORDS = ["مشاهدة فيلم", "مشاهدة", "فيلم", "مسلسل", "مترجمة اون لاين", "مترجم اون لاين", "مترجمة", "مترجم", "اون لاين", "مدبلجة", "مدبلج", "كرتون", "انمي", "بالمصري", "سلسلة افلام", "عرض", "برنامج", "جميع مواسم"]

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if any(ord(c) > 127 for c in baseUrl):
            baseUrl = urllib_quote_plus(baseUrl, safe="://")
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
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
                printDBG("EgyDead.getPage retry %d failed: %s" % (attempt + 1, str(e)))
                time.sleep(1.5)
        printDBG(f"[EgyDead] Retrying {baseUrl} failed after {max_retries} attempts due to timeout.")
        return False, ""

    def listMainMenu(self, cItem):
        printDBG("EgyDead.listMainMenu")
        MAIN_CAT_TAB = [
            {"category": "movies_categories", "title": "Movies"},
            {"category": "series_categories", "title": "Series"},
            {"category": "anime_categories", "title": "Anime"},
            {"category": "other_categories", "title": "Others"},
            {"category": "watch_by_type", "title": "Watch By Type"},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)
        self.MOVIES_CAT_TAB = [
            {"category": "list_units", "title": "English Movies", "url": self.getFullUrl("/category/english-movies/")},
            {"category": "list_units", "title": "Arabic Movies", "url": self.getFullUrl("/category/افلام-عربي/")},
            {"category": "list_units", "title": "Asian Movies", "url": self.getFullUrl("/category/افلام-اسيوية/")},
            {"category": "list_units", "title": "Turkish Movies", "url": self.getFullUrl("/category/افلام-تركية/")},
            {"category": "list_units", "title": "Indian Movies", "url": self.getFullUrl("/category/افلام-هندية/")},
            {"category": "list_units", "title": "English Dubbed Movies", "url": self.getFullUrl("/category/افلام-اجنبية-مدبلجة/")},
            {"category": "list_units", "title": "Turkish Dubbed Movies", "url": self.getFullUrl("/category/افلام-تركية-مدبلجة/")},
            {"category": "list_units", "title": "Indian Dubbed Movies", "url": self.getFullUrl("/category/افلام-هندية-مدبلجة/")},
            {"category": "list_units", "title": "Eslam Elgizawy Subbed Movies", "url": self.getFullUrl("/category/ترجمات-اسلام-الجيزاوي/")},
            {"category": "list_units", "title": "Documentary Movies", "url": self.getFullUrl("/category/افلام-وثائقية/")},
            {"category": "list_units", "title": "Cartoon Movies", "url": self.getFullUrl("/category/افلام-كرتون/")},
            {"category": "list_units", "title": "Cartoon Movies Egyptian Voice", "url": self.getFullUrl("/category/افلام-كرتون/افلام-كرتون-ديزني-باللهجة-المصرية/")},
            {"category": "list_seasons", "title": "Full Seasons Movies", "url": self.getFullUrl("/assembly/")},
        ]
        self.SERIES_CAT_TAB = [
            {"category": "list_units", "title": "English Series", "url": self.getFullUrl("/series-category/english-series/")},
            {"category": "list_units", "title": "Arabic Series", "url": self.getFullUrl("/series-category/arabic-series/")},
            {"category": "list_units", "title": "Turkish Series", "url": self.getFullUrl("/series-category/turkish-series/")},
            {"category": "list_units", "title": "Latin Series", "url": self.getFullUrl("/series-category/latino-series/")},
            {"category": "list_units", "title": "Asian Series", "url": self.getFullUrl("/series-category/asian-series/")},
            {"category": "list_units", "title": "African Series", "url": self.getFullUrl("/series-category/african-series/")},
            {"category": "list_units", "title": "Documentary Series", "url": self.getFullUrl("/series-category/documentary-series/")},
            {"category": "list_units", "title": "English Dubbed Series", "url": self.getFullUrl("/series-category/english-series-dubbed/")},
            {"category": "list_units", "title": "Turkish Dubbed Series", "url": self.getFullUrl("/series-category/turkish-series-dubbed/")},
            {"category": "list_units", "title": "Latin Dubbed Series", "url": self.getFullUrl("/series-category/latino-series-dubbed/")},
            {"category": "list_units", "title": "Asian Dubbed Series", "url": self.getFullUrl("/series-category/asian-series-dubbed/")},
            {"category": "list_series", "title": "Full Series", "url": self.getFullUrl("/serie/")},
            {"category": "list_series", "title": "Full Seasons", "url": self.getFullUrl("/season/")},
            {"category": "list_seasons", "title": "Full Episodes", "url": self.getFullUrl("/episode/")},
        ]
        self.ANIME_CAT_TAB = [
            {"category": "list_anime", "title": "Anime Movies", "url": self.getFullUrl("/category/افلام-انمي/")},
            {"category": "list_anime", "title": "Anime Movies 2", "url": self.getFullUrl("/series-category/anime-movies/")},
            {"category": "list_anime", "title": "انميات ربيع 2026", "url": self.getFullUrl("/tag/انميات-ربيع-2026/")},
            {"category": "list_anime", "title": "انميات شتاء 2026", "url": self.getFullUrl("/tag/انميات-شتاء-2026/")},
            {"category": "list_anime", "title": "انميات صينية", "url": self.getFullUrl("/series-category/chinese-anime/")},
            {"category": "list_anime", "title": "انميات كورية", "url": self.getFullUrl("/series-category/korean-anime/")},
            {"category": "list_anime", "title": "Anime Series", "url": self.getFullUrl("/series-category/anime-series/")},
            {"category": "list_anime", "title": "Anime Dubbed Series", "url": self.getFullUrl("/series-category/anime-series-dubbed/")},
            {"category": "list_anime", "title": "Cartoon Series", "url": self.getFullUrl("/series-category/cartoon-series/")},
            {"category": "list_anime", "title": "Cartoon Dubbed Series", "url": self.getFullUrl("/series-category/cartoon-series-dubbed/")},
        ]
        self.OTHER_CAT_TAB = [
            {"category": "list_other", "title": "Stand UP Shows", "url": self.getFullUrl("/category/عروض-وحفلات/")},
            {"category": "list_other", "title": "Sport", "url": self.getFullUrl("/category/رياضة/")},
            {"category": "list_other", "title": "TV Shows", "url": self.getFullUrl("/series-category/tv-shows/")},
            {"category": "list_other", "title": "كاس العالم 2022", "url": self.getFullUrl("/tag/كاس-العالم-2022/")},
        ]

    def listMoviesCategories(self, cItem):
        printDBG("EgyDead.listMoviesCategories")
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesCategories(self, cItem):
        printDBG("EgyDead.listMoviesCategories")
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listAnimeCategories(self, cItem):
        printDBG("EgyDead.listAnimeCategories")
        self.listsTab(self.ANIME_CAT_TAB, cItem)

    def listOtherCategories(self, cItem):
        printDBG("EgyDead.listOtherCategories")
        self.listsTab(self.OTHER_CAT_TAB, cItem)

    def _formatTitle(self, title):
        title = self.cleanHtmlStr(title)
        for word in self.CLEAN_WORDS:
            title = title.replace(word, "")
        title = title.strip()
        match = re.search(r"(\d{4})", title)
        if match:
            year = match.group(1)
            parts = title.split(year, 1)
            prefix = parts[0].strip()
            suffix = parts[1].strip()
            formatted = (f"{E2ColoR('yellow')}{prefix} " f"{E2ColoR('cyan')}{year} " f"{E2ColoR('yellow')}{suffix}{E2ColoR('white')}").replace("  ", " ").strip()
        else:
            formatted = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"
        return formatted

    def _extractMetadata(self, data):
        """Helper to extract metadata (info, story) from page data"""
        label_map = {"القسم": "Section", "النوع": "Genre", "اللغه": "Language", "البلد": "Country", "السنه": "Year", "مده العرض": "Duration", "الجوده": "Quality"}
        order = ["Section", "Genre", "Language", "Country", "Year", "Duration", "Quality"]
        info_part = self.cm.ph.getDataBeetwenMarkers(data, '<div class="LeftBox">', "</div>", False)[1]
        info_items = re.findall(r"<li>.*?</li>", info_part, re.S)
        info_dict = {}
        for item in info_items:
            raw_label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<span>", "</span>", False)[1])
            label = raw_label.replace(":", "").strip()
            value = ", ".join(re.findall(r">([^<]+)</a>", item))
            if not value:
                continue
            label_en = label_map.get(label, label)
            info_dict[label_en] = value
        info_parts = []
        for key in order:
            if key in info_dict:
                info_parts.append("%s%s%s : %s%s%s" % (E2ColoR("cyan"), key, E2ColoR("white"), E2ColoR("yellow"), info_dict[key], E2ColoR("white")))
        info_text = " | ".join(info_parts)
        story_part = self.cm.ph.getDataBeetwenMarkers(data, '<div class="extra-content">', "</div>", False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(story_part, "<p>", "</p>", False)[1])
        full_desc = "%s\n%sStory : %s%s%s" % (info_text, E2ColoR("lime"), E2ColoR("white"), story, E2ColoR("white"))
        return info_text, story, full_desc

    def _addMediaDir(self, cItem, item_html, next_category, data_source="li"):
        """Helper to parse an item HTML and add it as a directory"""
        if data_source == "li":
            url = self.cm.ph.getSearchGroups(item_html, r'href="([^"]+)"')[0]
            icon = self.cm.ph.getSearchGroups(item_html, r'data-lazy-style="[^"]*url\(([^)]+)\)')[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(item_html, r'(?:data-src|src)="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item_html, r'title="([^"]+)"')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item_html, "<h1", "</h1>", False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item_html, "<h2", "</h2>", False)[1])
            category = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item_html, '<span class="cat_name">', "</span>", False)[1])
        else:  # For assembly links
            url = self.cm.ph.getSearchGroups(item_html, r'href="([^"]+)"')[0]
            icon = self.cm.ph.getSearchGroups(item_html, r'<img[^>]+src="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item_html, r'title="([^"]+)"')[0])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item_html, "<h1", "</h1>", False)[1])
            category = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item_html, '<span class="cat_name">', "</span>", False)[1])
        if not url:
            return
        if icon:
            try:
                icon = urllib_quote_plus(icon, safe=":/?&=#%")
            except Exception as e:
                printDBG("icon encode error: %s" % e)
        title = self._formatTitle(title)
        desc = f"{category}"
        params = dict(cItem)
        params.update({"title": title, "url": self.getFullUrl(url), "icon": self.getFullUrl(icon), "desc": desc, "category": next_category})
        self.addDir(params)

    def _listPosts(self, cItem, next_category, posts_list_index=1, block_marker='<ul class="posts-list">'):
        """Generic method for listing units, series, and search results"""
        printDBG("EgyDead._listPosts >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("_listPosts: failed to load page")
            return
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="catHolder">', '<div class="pagination">', False)[1]
        if not main_block:
            # Fallback for search results which might not have catHolder
            main_block = data
        allblocks = self.cm.ph.getAllItemsBeetwenMarkers(main_block, block_marker, "</ul>")
        if len(allblocks) > posts_list_index:
            allblocks = allblocks[posts_list_index]
            items = self.cm.ph.getAllItemsBeetwenMarkers(allblocks, "<li", "</li>")
        else:
            # Fallback directly to li if block not found
            items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, "<li", "</li>")
        for item in items:
            self._addMediaDir(cItem, item, next_category, data_source="li")
        if len(items) == 0:
            printDBG("_listPosts: No media-card items found")
        # Pagination
        pagination_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', "</div>", False)[1]
        if pagination_block:
            next_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
            prev_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="prev page-numbers"[^>]+href="([^"]+)"')[0]
            category_name = cItem.get("category", "list_units")
            if prev_url:
                params = dict(cItem)
                params.update({"title": f"{E2ColoR('cyan')}<<<" + _("Previous"), "url": self.getFullUrl(prev_url), "category": category_name})
                self.addDir(params)
            if next_url:
                params = dict(cItem)
                params.update({"title": _("Next") + f" {E2ColoR('cyan')}>>>", "url": self.getFullUrl(next_url), "category": category_name})
                self.addDir(params)

    def listUnits(self, cItem):
        self._listPosts(cItem, next_category="explore_items", posts_list_index=1)

    def listSeries(self, cItem):
        self._listPosts(cItem, next_category="explore_seasons", posts_list_index=0)

    def listSearchUnits(self, cItem):
        # Search uses slightly different structure sometimes
        printDBG("EgyDead.listSearchUnits >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="catHolder">', "</div>", False)[1]
        if not main_block:
            main_block = data
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, "<li", "</li>")
        # Debug line kept as per original
        items1 = self.cm.ph.getAllItemsBeetwenMarkers(main_block, "<li", "</li>")[0] if items else []
        printDBG("item1.listSearchUnits >>> %s" % items1)
        for item in items:
            self._addMediaDir(cItem, item, next_category="explore_items", data_source="li")
        # Pagination for search
        pagination_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', "</div>", False)[1]
        if pagination_block:
            next_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
            if next_url:
                params = dict(cItem)
                params.update({"title": _("Next") + f" {E2ColoR('cyan')}>>>", "url": self.getFullUrl(next_url), "category": "search_next_page"})
                self.addDir(params)

    def listAssembly(self, cItem):
        printDBG("EgyDead.listAssembly >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="posts-list">', "</ul>", False)
        if len(main_block) < 2:
            printDBG("listAssembly: No posts-list found")
            return
        main_block = main_block[1]
        items = re.findall(r'<a[^>]+href="[^"]+"[^>]*>.*?</a>', main_block, re.S)
        for item in items:
            self._addMediaDir(cItem, item, next_category="explore_items", data_source="a")
        pagination_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', "</div>", False)
        if len(pagination_block) > 1:
            pagination_block = pagination_block[1]
            next_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
            prev_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="prev page-numbers"[^>]+href="([^"]+)"')[0]
            if not prev_url:
                prev_url = self.cm.ph.getSearchGroups(pagination_block, r'<a[^>]+class="page-numbers"[^>]+href="([^"]+)"[^>]*>\s*1\s*</a>')[0]
            if prev_url:
                params = dict(cItem)
                params.update({"title": f"{E2ColoR('cyan')}<<< " + _("Previous"), "url": self.getFullUrl(prev_url), "category": "list_seasons"})
                self.addDir(params)
            if next_url:
                params = dict(cItem)
                params.update({"title": _("Next") + f" {E2ColoR('cyan')}>>>", "url": self.getFullUrl(next_url), "category": "list_seasons"})
                self.addDir(params)

    def exploreItems(self, cItem):
        printDBG("EgyDead.exploreItems >>> %s" % cItem)
        url = cItem.get("url", "")
        sts, data1 = self.getPage(url)
        if not sts or not data1:
            return
        info_text, story, full_desc = self._extractMetadata(data1)
        # --- Work Title ---
        work_title = cItem.get("title", "").strip()
        if '<div class="EpsList">' in data1:
            printDBG("Season page detected — listing episodes...")
            cItem = dict(cItem)
            cItem["desc"] = full_desc
            return self.listEpisodes(cItem, data1)
        params = dict(self.defaultParams)
        params.update({"header": {"Content-Type": "application/x-www-form-urlencoded", "Referer": url}})
        post_data = {"View": "1"}
        sts, data = self.getPage(url, params, post_data)
        if not sts or not data:
            return
        if "salery-list" in data1:
            block = self.cm.ph.getDataBeetwenMarkers(data1, '<div class="salery-list">', "</ul>", False)[1]
            items = self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>")
            for item in items:
                self._addMediaDir(cItem, item, next_category="explore_items", data_source="li")
            return
        if "seasons-list" in data1:
            block = self.cm.ph.getDataBeetwenMarkers(data1, '<div class="seasons-list">', "</ul>", False)[1]
            items = self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>")
            for item in items:
                self._addMediaDir(cItem, item, next_category="explore_items", data_source="li")
            return
        watch_list = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="serversList">', "</ul>", False)[1]
        if not watch_list:
            return
        li_items = self.cm.ph.getAllItemsBeetwenMarkers(watch_list, "<li", "</li>")
        for item in li_items:
            video_url = self.cm.ph.getSearchGroups(item, r'data-link="([^"]+)"')[0]
            title = self.cm.ph.getSearchGroups(item, r"<p>([^<]+)</p>")[0].strip()
            if not title:
                title = self.cm.ph.getSearchGroups(item, r">([^<]+)</span>")[0].strip()
            title = self.cleanHtmlStr(title)
            # --- Combine Movie Title + Server Name ---
            if work_title:
                video_title = "%s%s%s - [%s]" % (E2ColoR("yellow"), work_title, E2ColoR("white"), title)
            else:
                video_title = title
            params = dict(cItem)
            params.update({"title": video_title, "url": video_url, "category": "video", "type": "video", "desc": full_desc})
            self.addVideo(params)

    def listEpisodes(self, cItem, data1):
        printDBG("EgyDead.listEpisodes >>> %s" % cItem)
        list_episode_part = self.cm.ph.getDataBeetwenMarkers(data1, '<div class="EpsList">', "</div>", False)[1]
        if not list_episode_part:
            return
        episodes = self.cm.ph.getAllItemsBeetwenMarkers(list_episode_part, "<li", "</li>")
        episodes.reverse()
        for item in episodes:
            ep_url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            ep_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not ep_title:
                ep_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r">([^<]+)</a>")[0])
            params = dict(cItem)
            params.update({"title": ep_title, "url": ep_url, "category": "explore_items"})
            self.addDir(params)

    def exploreSeasons(self, cItem):
        printDBG("EgyDead.exploreSeasons >>> %s" % cItem)
        url = cItem.get("url", "")
        if "/episode/" in url:
            params = dict(cItem)
            params.update({"category": "explore_items", "title": cItem.get("title", ""), "url": url, "desc": cItem.get("desc", "")})
            self.addDir(params)
            return
        sts, data = self.getPage(url)
        if not sts or not data:
            return
        label_map = {"القسم": "Section", "النوع": "Genre", "اللغه": "Language", "البلد": "Country", "السنه": "Year", "مده العرض": "Duration", "الجوده": "Quality"}
        order = ["Section", "Genre", "Language", "Country", "Year", "Duration", "Quality"]
        info_part = self.cm.ph.getDataBeetwenMarkers(data, '<div class="LeftBox">', "</div>", False)[1]
        info_items = re.findall(r"<li>.*?</li>", info_part, re.S)
        info_dict = {}
        for item in info_items:
            raw_label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<span>", "</span>", False)[1])
            label = raw_label.replace(":", "").strip()
            value = ", ".join(re.findall(r">([^<]+)</a>", item))
            if not value:
                continue
            label_en = label_map.get(label, label)
            info_dict[label_en] = value
        info_parts = []
        for key in order:
            if key in info_dict:
                info_parts.append("%s%s%s : %s%s%s" % (E2ColoR("cyan"), key, E2ColoR("white"), E2ColoR("yellow"), info_dict[key], E2ColoR("white")))
        info_text = " | ".join(info_parts)
        story_part = self.cm.ph.getDataBeetwenMarkers(data, '<div class="extra-content">', "</div>", False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(story_part, "<p>", "</p>", False)[1])
        full_desc = "%s\n%sStory : %s%s%s" % (info_text, E2ColoR("lime"), E2ColoR("white"), story, E2ColoR("white"))

        def colorTitle(title):
            match = re.search(r"(\d{4})", title)
            if match:
                year = match.group(1)
                parts = title.split(year, 1)
                return f"{E2ColoR('yellow')}{parts[0].strip()} {E2ColoR('cyan')}{year} {E2ColoR('yellow')}{parts[1].strip()}".replace("  ", " ").strip()
            else:
                return f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

        list_seasons_part = self.cm.ph.getDataBeetwenMarkers(data, '<div class="seasons-list">', "</div>", False)[1]
        if not list_seasons_part:
            eps_part = self.cm.ph.getDataBeetwenMarkers(data, '<div class="EpsList">', "</div>", False)[1]
            if not eps_part:
                return
            episodes = self.cm.ph.getAllItemsBeetwenMarkers(eps_part, "<li", "</li>")
            episodes.reverse()
            for item in episodes:
                ep_url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
                ep_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
                if not ep_title:
                    ep_title = self.cleanHtmlStr(item)
                ep_title = f"{E2ColoR('cyan')}▶ {colorTitle(ep_title)}"
                params = dict(cItem)
                params.update({"title": ep_title, "url": ep_url, "category": "explore_items", "desc": full_desc})
                self.addDir(params)
            return
        seasons = self.cm.ph.getAllItemsBeetwenMarkers(list_seasons_part, "<li", "</li>")
        seasons.reverse()
        for item in seasons:
            season_url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            season_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            if not season_title:
                season_title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r">([^<]+)</a>")[0])
            season_title = f"{E2ColoR('cyan')}★ {colorTitle(season_title)}"
            params = dict(cItem)
            params.update({"title": season_title, "url": season_url, "category": "explore_items", "desc": full_desc})
            self.addDir(params)

    def listWatchByType(self, cItem):
        printDBG("EgyDead.listWatchByType")
        url = self.getFullUrl("/type/")
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("listWatchByType: failed to load page")
            return
        genres_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="genresList">', "</div>", False)[1]
        if not genres_block:
            printDBG("listWatchByType: No genresList found")
            return
        items = self.cm.ph.getAllItemsBeetwenMarkers(genres_block, "<li", "</li>")
        printDBG("listWatchByType: Found %d genres" % len(items))
        for item in items:
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"<em>([^<]+)</em>")[0])
            if not title:
                continue
            params = dict(cItem)
            params.update({"title": title, "url": self.getFullUrl(url), "icon": self.DEFAULT_ICON_URL, "desc": "Watch by type: %s" % title, "category": "list_units"})
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        printDBG("EgyDead.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return []
        return [{"name": "EgyDead - %s" % cItem.get("title", ""), "url": url, "need_resolve": 1}]

    def getVideoLinks(self, url):
        printDBG("EgyDead.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EgyDead.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        self.listSearchUnits(cItem)

    def getArticleContent(self, cItem):
        printDBG("EgyDead.getArticleContent [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return []
        sts, data = self.getPage(url)
        if not sts or not data:
            return []
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="singleTitle">', "</div>", False)[1])
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="singleStory">', "</div>", False)[1])
        extra_story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="extra-content">', "</div>", False)[1])
        full_story = story + "\n" + extra_story
        icon = self.cm.ph.getSearchGroups(data, r'<div class="single-thumbnail">.*?<img[^>]+src="([^"]+)"')[0]
        if not icon:
            icon = cItem.get("icon", "")
        images = [{"title": "", "url": self.getFullUrl(icon)}] if icon else []
        info_part = self.cm.ph.getDataBeetwenMarkers(data, '<div class="LeftBox">', "</div>", False)[1]
        info_items = re.findall(r"<li>.*?</li>", info_part, re.S)
        otherInfo = {}
        for item in info_items:
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<span>", "</span>", False)[1])
            values = self.cm.ph.getAllItemsBeetwenMarkers(item, "<a", "</a>")
            clean_values = [self.cleanHtmlStr(v) for v in values if self.cleanHtmlStr(v)]
            value = ", ".join(clean_values)
            if "القسم" in label:
                otherInfo["category"] = value
            elif "النوع" in label:
                otherInfo["genre"] = value
            elif "اللغه" in label:
                otherInfo["language"] = value
            elif "البلد" in label:
                otherInfo["country"] = value
            elif "السنه" in label:
                otherInfo["year"] = value
            elif "القناه" in label:
                otherInfo["station"] = value
        views = self.cm.ph.getSearchGroups(data, r'<i class="fa fa-eye"></i><em>([^<]+)</em>')[0]
        date = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="postDate">', "</div>", False)[1])
        if views:
            otherInfo["views"] = views
        if date:
            otherInfo["date"] = date
        return [{"title": title if title else self.cleanHtmlStr(cItem.get("title", "")), "text": full_story, "images": images, "other_info": otherInfo}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("EgyDead.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []
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
        elif category == "list_units":
            self.listUnits(self.currItem)
        elif category == "list_seasons":
            self.listAssembly(self.currItem)
        elif category == "list_anime":
            self.listUnits(self.currItem)
        elif category == "list_other":
            self.listUnits(self.currItem)
        elif category == "list_series":
            self.listSeries(self.currItem)
        elif category == "explore_seasons":
            self.exploreSeasons(self.currItem)
        elif category == "watch_by_type":
            self.listWatchByType(self.currItem)
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
        CHostBase.__init__(self, EgyDead(), True, [])

    def withArticleContent(self, cItem):
        if "video" == cItem.get("type", "") or "explore_items" == cItem.get("category", ""):
            return True
        return False
