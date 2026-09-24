# -*- coding: utf-8 -*-
# original file from: 14/11/2025 - popking (odem2014)
# Last modified: 24/09/2026 - Mohamed Elsafty (angel_heart)
# Modified for new domain: https://w1.qrmzi.cyou/ with Movies & Series sections
###################################################
# LOCAL import
###################################################
# localization library
# host main class
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass

# tools - write on log, write exception infos and merge dicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR

# add metadata to url
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

# library for json (instead of standard json.loads and json.dumps)
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads

# read informations in m3u8
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus

###################################################
# FOREIGN import
###################################################
import re
from base64 import b64decode

Y, W, L, C, OR = (
    E2ColoR("yellow"),
    E2ColoR("white"),
    E2ColoR("lime"),
    E2ColoR("cyan"),
    E2ColoR("orange"),
)


###################################################
def GetConfigList():
    return []


def gettytul():
    return "https://w1.qrmzi.cyou/"  # main url of host


class Krmzy(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "krmzy", "cookie": "krmzy.cookie"})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + "?s="
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/krmzy.png"
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
        Unified getPage() for Krmzy
        - Handles Unicode / Arabic URLs safely
        - Preserves cookies between requests
        - Integrates Cloudflare protection
        - Retries once on failure
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
        addParams["cloudflare_params"] = {
            "cookie_file": self.COOKIE_FILE,
            "User-Agent": self.HEADER.get("User-Agent", "Mozilla/5.0"),
        }
        # --- Ensure cookie persistence
        addParams["use_cookie"] = True
        addParams["save_cookie"] = True
        addParams["load_cookie"] = True
        addParams["cookiefile"] = self.COOKIE_FILE
        # --- Retry logic (no sleep, it would block the GUI)
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
                if sts and data:
                    return sts, data
            except Exception as e:
                printDBG("[Krmzy] getPage attempt %d failed: %s" % (attempt, str(e)))
        printDBG("[Krmzy] getPage failed after %d retries: %s" % (max_retries, baseUrl))
        return False, ""

    ###################################################
    # MAIN MENU
    ###################################################
    def listMainMenu(self, cItem):
        printDBG("Krmzy.listMainMenu")
        MAIN_CAT_TAB = [
            {
                "category": "list_series",
                "title": "المسلسلات",
                "url": self.getFullUrl("all-turkish-series/"),
            },
            {
                "category": "list_movies",
                "title": "الافلام",
                "url": self.getFullUrl("all-turkish-movies/"),
            },
        ] + self.searchItems()
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listContentUnits(self, cItem):
        printDBG("Krmzy.listContentUnits >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("listContentUnits: failed to load page")
            return
        items = re.findall(
            r"<article[^>]*>(.*?)</article>", data, re.DOTALL | re.IGNORECASE
        )
        printDBG("listContentUnits: Found %d items" % len(items))
        is_search = cItem.get("is_search", False)
        is_movies = "movies" in cItem["url"]
        for item in items:
            # --- URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)
            if is_search:
                if "/movies/" not in url and "/series/" not in url:
                    continue
            elif is_movies and "/movies/" not in url:
                continue
            elif not is_movies and "/series/" not in url:
                continue
            # --- TITLE ---
            title = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(
                    item, '<div class="title">', "</div>", False
                )[1]
            )
            if not title:
                title = self.cleanHtmlStr(
                    self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0]
                )
            if not title:
                continue
            # --- POSTER (Hybrid - supports quoted & unquoted) ---
            icon = ""
            # 1. background-image (old sites)
            bg_match = re.search(r"background-image:\s*url\(([^)]+)\)", item)
            if bg_match:
                icon = bg_match.group(1).strip().strip("'\"")
            # 2. <img> tag - extract img tag itself
            if not icon:
                img_match = re.search(r"<img[^>]+>", item, re.IGNORECASE | re.DOTALL)
                if img_match:
                    img_tag = img_match.group(0)
                    ds_match = re.search(
                        r'data-src=["\']?([^"\'\s>]+)', img_tag, re.IGNORECASE
                    )
                    if ds_match:
                        icon = ds_match.group(1)
                    else:
                        src_match = re.search(
                            r'src=["\']?([^"\'\s>]+)', img_tag, re.IGNORECASE
                        )
                        if src_match:
                            icon = src_match.group(1)
            # 3. Clean
            if icon:
                icon = icon.strip().strip("'\"")
                if "base64" in icon or icon.startswith("data:"):
                    icon = ""
                elif not icon.startswith("http"):
                    icon = self.getFullUrl(icon)
            printDBG("Title: %s | Icon: [%s]" % (title[:30], icon))
            params = dict(cItem)
            params.update(
                {
                    "title": f"{Y}{title}{W}",
                    "url": url,
                    "icon": icon,
                    "desc": f"{Y}Click to view details{W}",
                    "category": (
                        "series_details" if "/series/" in url else "explore_item"
                    ),
                    "good_for_fav": True,
                }
            )
            self.addDir(params)
        # Pagination
        pagination = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="navigation', "</div>", True
        )[1]
        if not pagination:
            pagination = self.cm.ph.getDataBeetwenMarkers(
                data, '<div class="col-md-12">', "<footer>", True
            )[1]
        if pagination:
            current_page = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(
                    pagination, "<span class='current'>", "</span>", False
                )[1]
            )
            if not current_page:
                current_page = self.cleanHtmlStr(
                    self.cm.ph.getDataBeetwenMarkers(
                        pagination, '<span class="current">', "</span>", False
                    )[1]
                )
            all_pages = re.findall(
                r"href=['\"]([^'\"]+)['\"][^>]*>(\d+)</a>", pagination
            )
            nextPage = ""
            if current_page.isdigit() and all_pages:
                for href, num in all_pages:
                    if num.isdigit() and int(num) == int(current_page) + 1:
                        nextPage = href
                        break
            if nextPage:
                nextPage = self.getFullUrl(nextPage)
                params = dict(cItem)
                # search pages must not go back through listSearchResult,
                # it would rebuild the page 1 search URL
                params.update({"title": "Next Page >>", "url": nextPage, "category": "list_items"})
                self.addDir(params)

    def listSeriesEpisodes(self, cItem):
        printDBG("Krmzy.listSeriesEpisodes >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("listSeriesEpisodes: failed to load page")
            return
        # Check "Coming Soon" marker
        if "يعرض قريباً في موقع قرمزي" in data or "يعرض قريبا في موقع قرمزي" in data:
            printDBG("listSeriesEpisodes: Series not yet available")
            episode_desc = f"{Y}هذا المسلسل لم تُضف حلقاته بعد{W}"
            story_block = self.cm.ph.getDataBeetwenMarkers(
                data, '<div class="story">', "</div>", False
            )[1]
            if story_block:
                story = self.cleanHtmlStr(story_block)
                if story:
                    episode_desc = (
                        f"{L}القصة :{W} {story}\n\n" f"{Y} يعرض قريباً في موقع قرمزي{W}"
                    )
            self.addMarker(
                {
                    "title": f"{Y} يعرض قريباً في موقع قرمزي{W}",
                    "desc": episode_desc,
                    "icon": cItem.get("icon", ""),
                }
            )
            return
        ###################################################
        # Build episode description (Story)
        ###################################################
        episode_desc = f"{Y}Click to play episode{W}"
        story_block = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="story">', "</div>", False
        )[1]
        if story_block:
            story = self.cleanHtmlStr(story_block)
            if story:
                episode_desc = f"{L}القصة :{W} {story}"
        ###################################################
        # Extract episodes
        ###################################################
        items = re.findall(
            r"<article[^>]*>(.*?)</article>", data, re.DOTALL | re.IGNORECASE
        )
        printDBG("listSeriesEpisodes: Found %d episodes" % len(items))
        if not items:
            printDBG("listSeriesEpisodes: No episode items found")
            self.addMarker(
                {
                    "title": f"{Y} لا توجد حلقات متاحة{W}",
                    "desc": episode_desc,
                    "icon": cItem.get("icon", ""),
                }
            )
            return
        items.reverse()
        for item in items:
            # --- Episode URL ---
            url = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if not url:
                continue
            url = self.getFullUrl(url)
            # --- Episode Title ---
            title = self.cleanHtmlStr(
                self.cm.ph.getDataBeetwenMarkers(
                    item, '<div class="title">', "</div>", False
                )[1]
            )
            if not title:
                title = self.cleanHtmlStr(
                    self.cm.ph.getSearchGroups(item, r'title="([^"]+)"')[0]
                )
            # --- Episode Number ---
            ep_num_match = re.search(r"<span>(\d+)</span>", item)
            if ep_num_match and title:
                title = f"حلقة {ep_num_match.group(1)} - {title}"
            # --- Episode Poster ---
            icon = ""
            img_match = re.search(r"<img[^>]+>", item, re.IGNORECASE | re.DOTALL)
            if img_match:
                img_tag = img_match.group(0)
                ds_match = re.search(
                    r'data-src=["\']?([^"\'\s>]+)', img_tag, re.IGNORECASE
                )
                if ds_match:
                    icon = ds_match.group(1)
                else:
                    src_match = re.search(
                        r'src=["\']?([^"\'\s>]+)', img_tag, re.IGNORECASE
                    )
                    if src_match:
                        icon = src_match.group(1)
            if icon and "base64" not in icon:
                icon = self.getFullUrl(icon.strip().strip("'\""))
            else:
                icon = cItem.get("icon", "")
            params = dict(cItem)
            params.update(
                {
                    "title": f"{C}{title}{W}",
                    "url": url,
                    "icon": icon,
                    "desc": episode_desc,
                    "category": "explore_item",
                    "good_for_fav": True,
                }
            )
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG("Krmzy.exploreItems >>> %s" % cItem)
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("exploreItems: failed to load page")
            return
        raw_title = cItem.get("title", "")
        video_title = re.sub(r"\\c00[0-9A-Fa-f]{6}", "", raw_title)
        video_title = self.cleanHtmlStr(video_title).strip()
        # --- Story ---
        story_desc = ""
        story_block = self.cm.ph.getDataBeetwenMarkers(
            data, '<div class="story">', "</div>", False
        )[1]
        if story_block:
            story = self.cleanHtmlStr(story_block)
            if story:
                story_desc = f"{L}القصة :{W} {story}"
        data_no_ta = re.sub(
            r"<textarea[^>]*>.*?</textarea>", "", data, flags=re.DOTALL | re.IGNORECASE
        )
        video_con_match = re.search(
            r'<div[^>]+class=["\'][^"\']*video-con[^"\']*["\'][^>]*>.*?<iframe[^>]+src=["\']([^"\']+)["\']',
            data_no_ta,
            re.DOTALL | re.IGNORECASE,
        )
        iframe_url = ""
        if video_con_match:
            iframe_url = video_con_match.group(1)
        else:
            any_iframe = re.search(
                r'<iframe[^>]+src=["\']([^"\']+)["\']',
                data_no_ta,
                re.DOTALL | re.IGNORECASE,
            )
            if any_iframe:
                iframe_url = any_iframe.group(1)
        printDBG("exploreItems: iframe_url = %s" % iframe_url)
        ###################################################
        # ✅ 2) If iframe is from albaplayer, open it and extract servers
        ###################################################
        if iframe_url and "albaplayer" in iframe_url:
            printDBG("Opening albaplayer page: %s" % iframe_url)
            sts2, data2 = self.getPage(iframe_url)
            if sts2 and data2:
                server_items = re.findall(
                    r'href=["\']([^"\']*albaplayer[^"\']*serv=\d+[^"\']*)["\'][^>]*>([^<]+)</a>',
                    data2,
                    re.IGNORECASE,
                )
                printDBG(
                    "exploreItems: Found %d server items in albaplayer page"
                    % len(server_items)
                )
                seen = set()
                unique_servers = []
                for s_url, s_name in server_items:
                    s_url = s_url.strip()
                    if s_url in seen:
                        continue
                    seen.add(s_url)
                    unique_servers.append((s_url, s_name.strip()))
                if unique_servers:
                    for s_url, s_name in unique_servers:
                        s_name_clean = self.cleanHtmlStr(s_name).strip()
                        serv_id = self.cm.ph.getSearchGroups(s_url, r"serv=(\d+)")[0]
                        if not s_name_clean:
                            s_name_clean = f"Server {serv_id}" if serv_id else "Server"
                        printDBG("Adding server: %s => %s" % (s_name_clean, s_url))
                        params = dict(cItem)
                        params.update(
                            {
                                "title": f"{video_title} - {s_name_clean}",
                                "url": s_url,
                                "category": "video",
                                "type": "video",
                                "desc": story_desc,
                                "need_resolve": 1,
                            }
                        )
                        self.addVideo(params)
                    return
                inner_iframe = re.search(
                    r'<div[^>]+class=["\'][^"\']*video-con[^"\']*["\'][^>]*>.*?<iframe[^>]+src=["\']([^"\']+)["\']',
                    data2,
                    re.DOTALL | re.IGNORECASE,
                )
                if inner_iframe:
                    real_url = inner_iframe.group(1)
                    printDBG("Found inner iframe: %s" % real_url)
                    params = dict(cItem)
                    params.update(
                        {
                            "title": f"{video_title} - Direct",
                            "url": real_url,
                            "category": "video",
                            "type": "video",
                            "desc": story_desc,
                            "need_resolve": 1,
                        }
                    )
                    self.addVideo(params)
                    return
        ###################################################
        # ✅ 3) If iframe is direct (cdnplus.space...)
        ###################################################
        if iframe_url:
            printDBG("Adding direct iframe: %s" % iframe_url)
            params = dict(cItem)
            params.update(
                {
                    "title": f"{video_title} - Direct",
                    "url": iframe_url,
                    "category": "video",
                    "type": "video",
                    "desc": story_desc,
                    "need_resolve": 1,
                }
            )
            self.addVideo(params)
            return
        ###################################################
        # ✅ 4) Fallback: qesen.net
        ###################################################
        redirect_url = self.cm.ph.getSearchGroups(
            data, r'href="([^"]+qesen\.net[^"]+)"'
        )[0]
        if redirect_url:
            redirect_url = redirect_url.replace(
                "qesen.net/krmzi?post=", "qesen.net/krmzi/?post="
            )
            sts_r, data_r = self.getPage(redirect_url)
            if sts_r and data_r:
                post_param = self.cm.ph.getSearchGroups(redirect_url, r"post=([^&]+)")[
                    0
                ]
                if post_param:
                    try:
                        json_str = b64decode(post_param.encode("utf-8")).decode("utf-8")
                        json_data = json_loads(json_str)
                        for server in json_data.get("servers", []):
                            name = server.get("name", "").strip()
                            sid = server.get("id", "").strip()
                            if name and sid:
                                video_url = ""
                                name_lower = name.lower()
                                if name_lower == "ok":
                                    video_url = f"https://ok.ru/videoembed/{sid}"
                                elif name_lower == "arab hd":
                                    video_url = (
                                        f"https://v.turkvearab.com/embed-{sid}.html"
                                    )
                                elif name_lower == "pro hd":
                                    video_url = f"https://w.larhu.com/play.php?id={sid}"
                                elif name_lower == "red hd":
                                    video_url = f"https://iplayerhls.com/e/{sid}"
                                elif name_lower == "estream":
                                    video_url = (
                                        f"https://arabveturk.com/embed-{sid}.html"
                                    )
                                elif name_lower == "box":
                                    video_url = f"https://youdboox.com/embed-{sid}.html"
                                elif name_lower == "now":
                                    video_url = (
                                        f"https://extreamnow.org/embed-{sid}.html"
                                    )
                                elif name_lower == "dailymotion":
                                    video_url = (
                                        f"https://www.dailymotion.com/video/{sid}.html"
                                    )
                                elif name_lower == "express":
                                    video_url = sid
                                else:
                                    video_url = sid
                                params = dict(cItem)
                                params.update(
                                    {
                                        "title": f"{video_title} - {name}",
                                        "url": video_url,
                                        "category": "video",
                                        "type": "video",
                                        "desc": story_desc,
                                    }
                                )
                                self.addVideo(params)
                    except Exception as e:
                        printDBG("Failed to decode fallback post param: %s" % e)
        if len(self.currList) == 0:
            printDBG("exploreItems: WARNING - No video sources found!")

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Krmzy.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return []
        return [
            {
                "name": "Krmzy - %s" % cItem.get("title", ""),
                "url": url,
                "need_resolve": 1,
            }
        ]

    def getVideoLinks(self, url):
        printDBG("Krmzy.getVideoLinks [%s]" % url)
        urlTab = []
        if not self.cm.isValidUrl(url):
            return urlTab
        ###################################################
        # ✅ 1) albaplayer → extract inner iframe, pass to urlparser
        ###################################################
        if "albaplayer" in url:
            sts, data = self.getPage(url)
            if sts and data:
                data_no_ta = re.sub(
                    r"<textarea[^>]*>.*?</textarea>",
                    "",
                    data,
                    flags=re.DOTALL | re.IGNORECASE,
                )
                iframe_match = re.search(
                    r'<div[^>]+class=["\'][^"\']*video-con[^"\']*["\'][^>]*>.*?<iframe[^>]+src=["\']([^"\']+)["\']',
                    data_no_ta,
                    re.DOTALL | re.IGNORECASE,
                )
                if iframe_match:
                    real_url = iframe_match.group(1)
                    printDBG("Extracted real iframe: %s" % real_url)
                    return self.up.getVideoLinkExt(real_url)
            return urlTab
        ###################################################
        # ✅ 2) anafast → extract m3u8 directly (to avoid 403)
        ###################################################
        if "anafast" in url.lower():
            sts, data = self.getPage(url)
            if sts and data:
                m3u8_match = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', data)
                if m3u8_match:
                    video_url = m3u8_match.group(1)
                    printDBG("Found anafast m3u8: %s" % video_url)
                    urlTab.append(
                        {
                            "name": "Krmzy - anafast",
                            "url": strwithmeta(
                                video_url, {"Referer": "https://anafast.cyou/"}
                            ),
                            "need_resolve": 0,
                        }
                    )
                    return urlTab
            return self.up.getVideoLinkExt(url)
        ###################################################
        return self.up.getVideoLinkExt(url)

    ###################################################
    # SEARCH
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG(
            "Krmzy.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]"
            % (cItem, searchPattern, searchType)
        )
        cItem = dict(cItem)
        cItem["url"] = self.SEARCH_URL + urllib_quote_plus(searchPattern)
        cItem["is_search"] = True
        self.listContentUnits(cItem)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("Krmzy.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category in ["list_series", "list_movies", "list_items"]:
            self.listContentUnits(self.currItem)
        elif category == "series_details":
            self.listSeriesEpisodes(self.currItem)
        elif category == "explore_item":
            self.exploreItems(self.currItem)
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
        CHostBase.__init__(self, Krmzy(), True, [])
