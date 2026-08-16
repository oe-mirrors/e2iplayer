# -*- coding: utf-8 -*-
# original file from: 14/11/2025 - popking (odem2014)
# Last modified: 27/03/2026 - Mohamed Elsafty (angel_heart)
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
from base64 import b64decode
import json


###################################################
def GetConfigList():
    return []


def gettytul():
    return "https://krmzy.org/"  # main url of host


class Krmzy(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "krmzy", "cookie": "krmzy.cookie"})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + "?s="
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/krmzy.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams=None, post_data=None):
        """
        Unified getPage() for Krmzy
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
            printDBG("[Krmzy] URL normalization failed: %s" % str(e))
        # --- Prepare request parameters
        if addParams is None:
            addParams = dict(self.defaultParams)
        else:
            tmp = dict(self.defaultParams)
            tmp.update(addParams)
            addParams = tmp
        # --- Always attach Cloudflare parameters
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent", "Mozilla/5.0")}
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
                printDBG("[Krmzy] getPage attempt %d failed: %s" % (attempt, str(e)))
            time.sleep(1.5)
        printDBG("[Krmzy] getPage failed after %d retries: %s" % (max_retries, baseUrl))
        return False, ""

    ###################################################
    # MAIN MENU
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("Krmzy.listMainMenu")
        MAIN_CAT_TAB = [
            {"category": "list_series", "title": "Series", "url": self.getFullUrl("series-list/")},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listSeriesCategories(self, cItem):
        printDBG("Krmzy.listMoviesCategories")
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def exploreItems(self, cItem):
        printDBG("Krmzy.exploreItems >>> %s" % cItem)
        url = cItem["url"]
        printDBG("url.exploreItems >>> %s" % url)
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("exploreItems: failed to load page")
            return
        # 1️⃣ Extract qesen.net redirect link
        redirect_url = self.cm.ph.getSearchGroups(data, r'href="([^"]+qesen\.net[^"]+)"')[0]
        if not redirect_url:
            printDBG("No redirect URL found")
            return
        # 2️⃣ Normalize URL (fix missing slash before ?post=)
        redirect_url = redirect_url.replace("qesen.net/krmzi?post=", "qesen.net/krmzi/?post=")
        printDBG("redirect_url >>> %s" % redirect_url)
        # 3️⃣ Fetch redirected page
        sts, data2 = self.getPage(redirect_url)
        if not sts or not data2:
            printDBG("Failed to open redirect link: %s" % redirect_url)
            return
        printDBG("data2.exploreItems >>> %s" % data2)
        # 4️⃣ Extract "post=" base64-like JSON string from URL
        post_param = self.cm.ph.getSearchGroups(redirect_url, r"post=([^&]+)")[0]
        if not post_param:
            printDBG("No post parameter found")
            return
        try:
            json_str = b64decode(post_param.encode("utf-8")).decode("utf-8")
            json_data = json_loads(json_str)
        except Exception as e:
            printDBG("Failed to decode post param: %s" % e)
            return
        printDBG("Decoded post data >>> %s" % json_data)
        raw_title = cItem.get("title", "")
        episode_title = re.sub(r"\\c00[0-9A-Fa-f]{6}", "", raw_title)
        episode_title = self.cleanHtmlStr(episode_title).strip()
        printDBG('exploreItems: Cleaned episode_title = "%s"' % episode_title)
        # 5️⃣ Extract and build server URLs
        for server in json_data.get("servers", []):
            name = server.get("name", "").strip()
            sid = server.get("id", "").strip()
            if not name or not sid:
                continue
            video_url = ""
            if name.lower() == "ok":
                video_url = f"https://ok.ru/videoembed/{sid}"
            elif name.lower() == "arab hd":
                video_url = f"https://v.turkvearab.com/embed-{sid}.html"
            elif name.lower() == "pro hd":
                video_url = f"https://w.larhu.com/play.php?id={sid}"
            elif name.lower() == "red hd":
                video_url = f"https://iplayerhls.com/e/{sid}"
            elif name.lower() == "estream":
                video_url = f"https://arabveturk.com/embed-{sid}.html"
            elif name.lower() == "box":
                video_url = f"https://youdboox.com/embed-{sid}.html"
            elif name.lower() == "now":
                video_url = f"https://extreamnow.org/embed-{sid}.html"
            elif name.lower() == "dailymotion":
                video_url = f"https://www.dailymotion.com/video/{sid}.html"
            elif name.lower() == "express":
                video_url = sid  # direct URL
            else:
                # fallback
                video_url = sid
            printDBG(f"Found server: {name} => {video_url}")
            video_title = f"{episode_title} - {name}" if episode_title else name
            params = dict(cItem)
            params.update(
                {
                    "title": video_title,
                    "url": video_url,
                    "category": "video",
                    "type": "video",
                }
            )
            self.addVideo(params)
        printDBG("exploreItems: completed parsing servers")

    def listSeriesUnits(self, cItem):
        printDBG("Krmzy.listSeriesUnits >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("listSeriesUnits: failed to load page")
            return
        is_search = cItem.get("is_search", False)
        ###################################################
        # MAIN SERIES BLOCK
        ###################################################
        if is_search:
            main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="sec-line">', "<footer>", False)[1]
        else:
            main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div id="load-post-episodes">', "<footer>", False)[1]
        if not main_block:
            printDBG("listSeriesUnits: No main_block found")
            return
        ###################################################
        # PARSE SERIES ITEMS
        ###################################################
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, "<article", "</article>")
        printDBG("listSeriesUnits: Found %d items" % len(items))
        for item in items:
            # --- URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)
            # --- TITLE ---
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="title">', "</div>", False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            # --- POSTER (from background-image style) ---
            icon = self.cm.ph.getSearchGroups(item, r"background-image:url\(([^)]+)\)")[0]
            icon = self.getFullUrl(icon)
            # --- DESCRIPTION ---
            desc = f"{E2ColoR('yellow')}Click to view episodes{E2ColoR('white')}"
            # --- COLORIZED TITLE ---
            colored_title = f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"
            # --- ADD ITEM ---
            params = dict(cItem)
            params.update(
                {
                    "title": colored_title,
                    "url": url,
                    "icon": icon,
                    "desc": desc,
                    "category": "list_series_episodes",
                    "good_for_fav": True,
                }
            )
            self.addDir(params)
        if len(items) == 0:
            printDBG("listSeriesUnits: No <article> items found")
        ###################################################
        # === PAGINATION HANDLING (FIXED FOR KRMZY) ===
        ###################################################
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="col-md-12">', "<footer>", True)[1]
        printDBG("pagination.listSeriesUnits >>> %s" % pagination)
        if pagination:
            # Current page
            current_page = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(pagination, "<span class='current'>", "</span>", False)[1])
            # All page numbers
            all_pages = re.findall(r"href='([^']+)'[^>]*>(\d+)</a>", pagination)
            nextPage = ""
            if current_page and all_pages:
                for href, num in all_pages:
                    if num.isdigit() and int(num) == int(current_page) + 1:
                        nextPage = href
                        break
            if nextPage:
                nextPage = self.getFullUrl(nextPage)
                printDBG("Next page found: %s" % nextPage)
                params = dict(cItem)
                params.update({"title": "Next Page >>", "url": nextPage})
                self.addDir(params)
            else:
                printDBG("No next page found in pagination")

    def listSeriesEpisodes(self, cItem):
        printDBG("Krmzy.listSeriesEpisodes >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("listSeriesEpisodes: failed to load page")
            return
        ###################################################
        # MAIN INFO BLOCK (Story + Cast) - Extract series info for episodes description
        ###################################################
        episode_desc = f"{E2ColoR('yellow')}Click to view episodes{E2ColoR('white')}"
        main_info_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="singleSeries">', '<div class="sec-line">', True)[1]
        if main_info_block:
            # --- Extract Cast ---
            cast_list = []
            cast_block = self.cm.ph.getDataBeetwenMarkers(main_info_block, '<div class="tax">', "</div>", False)[1]
            if cast_block:
                # Extract actor names from title attribute (cleaner and more accurate)
                cast_names = re.findall(r'<a[^>]*title="([^"]*)"[^>]*>', cast_block, re.IGNORECASE)
                for name in cast_names:
                    name_clean = self.cleanHtmlStr(name).strip()
                    # Ignore invalid texts (punctuation, short strings, etc.)
                    if name_clean and len(name_clean) > 2 and name_clean not in [",", " - ", "and", "with"]:
                        cast_list.append(name_clean)
            # --- Extract Story ---
            story_raw = self.cm.ph.getDataBeetwenMarkers(main_info_block, '<div class="story">', "</div>", False)[1]
            story = self.cleanHtmlStr(story_raw) if story_raw else ""
            # Clean story from empty lines and extra whitespace
            story_clean = " ".join([line.strip() for line in story.split("\n") if line.strip()])
            # --- Build colored description ---
            desc_parts = []
            # Cast: (Yellow color) + names (White) separated by " - "
            if cast_list:
                cast_str = " - ".join(cast_list)
                desc_parts.append(f"{E2ColoR('yellow')}الممثلين :{E2ColoR('white')} {cast_str}")
            # Story: (Green color) + text (White)
            if story_clean:
                desc_parts.append(f"{E2ColoR('lime')}القصة :{E2ColoR('white')} {story_clean}")
            # Final description
            if desc_parts:
                episode_desc = "\n".join(desc_parts)
                printDBG("listSeriesEpisodes: ✓ episode_desc created - cast=%d, story_len=%d" % (len(cast_list), len(story_clean)))
        ###################################################
        # EPISODE LIST BLOCK - Parse and add episodes
        ###################################################
        main_block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="sec-line">', "<footer>", True)[1]
        printDBG("main_block.listSeriesEpisodes >>> %s" % main_block)
        if not main_block:
            printDBG("listSeriesEpisodes: No main_block found")
            return
        items = self.cm.ph.getAllItemsBeetwenMarkers(main_block, "<article", "</article>")
        printDBG("listSeriesEpisodes: Found %d episode items" % len(items))
        if not items:
            printDBG("listSeriesEpisodes: No episode items found")
            return
        # Reverse to display episodes from oldest to newest
        items.reverse()
        for item in items:
            # --- Episode URL ---
            e_url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not e_url:
                continue
            e_url = self.getFullUrl(e_url)
            # --- Episode Poster ---
            icon = self.cm.ph.getSearchGroups(item, r"background-image:url\(([^)]+)\)")[0]
            icon = self.getFullUrl(icon)
            printDBG("Episode icon: %s" % icon)
            # --- Episode Title ---
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<div class="title">', "</div>", False)[1])
            if not title:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0])
            printDBG("Episode title: %s" % title)
            # --- Colorized Title (Cyan) ---
            colored_title = f"{E2ColoR('cyan')}{title}{E2ColoR('white')}"
            # --- Add episode to list with shared description (Cast + Story) ---
            params = dict(cItem)
            params.update({"title": colored_title, "url": e_url, "icon": icon, "desc": episode_desc, "good_for_fav": True, "category": "explore_item"})
            self.addDir(params)
            printDBG("Added episode: %s with desc" % title)

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Krmzy.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return []
        return [{"name": "Krmzy - %s" % cItem.get("title", ""), "url": url, "need_resolve": 1}]

    def getVideoLinks(self, url):
        printDBG("Krmzy.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    ###################################################
    # SEARCH
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Krmzy.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        cItem["is_search"] = True
        self.listSeriesUnits(cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("Krmzy.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []
        # MAIN MENU
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_series":
            self.listSeriesUnits(self.currItem)
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
        CHostBase.__init__(self, Krmzy(), True, [])
