# -*- coding: utf-8 -*-
# Last modified: 13/10/2025 - popking (odem2014)
# Last updated:  18/04/2025 - M.Elsafty (angel_heart)
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
import base64
import json

try:
    from urllib.parse import urlparse, parse_qs, urlencode, unquote, quote
except ImportError:
    from urllib import urlencode, urlopen, unquote, quote

    ###################################################


def GetConfigList():
    return []


def gettytul():
    return "https://asd.pics/"  # main url of host


class ArabSeed(CBaseHostClass):
    def __init__(self):
        # init global variables for this class
        CBaseHostClass.__init__(self, {"history": "arabseed", "cookie": "arabseed.cookie"})  # names for history and cookie files in cache
        # vars default values
        self.urlencode = urlencode
        # various urls
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = "https://asd.pics/search"
        # url for default icon
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/arabseed.png"
        # default header and http params
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, base_url, add_params=None, post_data=None):
        if any(ord(c) > 127 for c in base_url):
            base_url = urllib_quote_plus(base_url, safe="://")
        if add_params is None:
            add_params = dict(self.defaultParams)
        add_params["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(base_url, add_params, post_data)

    def getLinksForVideo(self, cItem):
        printDBG("ArabSeed.getLinksForVideo [%s]" % cItem)
        linksTab = []
        url = cItem.get("url", "")
        # ===============================
        # IMDb Resolver
        # ===============================
        if "imdb.com/video/" in url:
            printDBG("Detected IMDb trailer")
            return self.getIMDBTrailer(url)
        referer = cItem.get("url", self.MAIN_URL)
        headers = {"Referer": referer, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        sts, data = self.getPage(cItem["url"], self.defaultParams)
        if not sts:
            return []
        # Prevent redirect/park traps (like yfdpco2.com)
        redirect_domains = ["yfdpco2.com", "ww38.m.seeeed.xyz", "ww38.m.reviewrate.net"]
        # --- Step 1: find embedded iframes ---
        iframes = self.cm.ph.getAllItemsBeetwenMarkers(data, "<iframe", ">")
        for iframe in iframes:
            url = self.cm.ph.getSearchGroups(iframe, 'src="([^"]+)"')[0]
            if not url:
                continue
            # Skip redirect trap URLs
            if any(dom in url for dom in redirect_domains):
                continue
            # Auto-wrap only for known domains (fix for seeeed.xyz embeds)
            if "m.seeeed.xyz" in url and not url.startswith("https://m.reviewrate.net/asd.php?url="):
                import base64

                b64url = base64.b64encode(url.encode()).decode().replace("+", "-").replace("/", "_").replace("=", "")
                wrapped = "https://m.reviewrate.net/asd.php?url=" + b64url
                url = wrapped
                printDBG("Auto-wrapped seeeed.xyz URL -> %s" % url)
            linksTab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, headers), "need_resolve": 1})
        # --- Step 2: try <source> tags (direct .mp4) ---
        video_links = self.cm.ph.getAllItemsBeetwenMarkers(data, "<source", ">")
        for link in video_links:
            url = self.cm.ph.getSearchGroups(link, 'src="([^"]+)"')[0]
            if not url:
                continue
            if any(dom in url for dom in redirect_domains):
                continue
            linksTab.append({"name": self.up.getHostName(url).capitalize(), "url": strwithmeta(url, headers), "need_resolve": 0})
        # --- Step 3: fallback to getVideoLinks ---
        if not linksTab:
            printDBG("ArabSeed.getLinksForVideo: no direct links found, fallback to parser")
            resolved = self.getVideoLinks(cItem["url"])
            for entry in resolved:
                if isinstance(entry, dict):
                    entry["url"] = strwithmeta(entry.get("url"), headers)
                    linksTab.append(entry)
                else:
                    linksTab.append({"name": self.up.getHostName(cItem["url"]), "url": strwithmeta(entry, headers), "need_resolve": 0})
        printDBG("ArabSeed.getLinksForVideo -> Final linksTab: %s" % str(linksTab))
        return linksTab

    def getVideoLinks(self, url):
        printDBG("ArabSeed.getVideoLinks [%s]" % url)
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)

    def listMainMenu(self, cItem):
        # items of main menu
        printDBG("ArabSeed.listMainMenu")
        # Define main categories statically like FilmPalast does
        self.MAIN_CAT_TAB = [
            {"category": "movies_folder", "title": "الافلام"},
            {"category": "series_folder", "title": "المسلسلات"},
            {"category": "ramadan_folder", "title": "رمضان"},
            {"category": "anime_folder", "title": "انمي"},
            {"category": "series_packs_folder", "title": "مواسم مسلسلات - برامج - أنمي"},
            {"category": "other_folder", "title": "اخري"},
        ] + self.searchItems()
        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {"category": "list_items", "title": "افلام عربي", "url": self.getFullUrl("/category/arabic-movies-10/")},
            {"category": "list_items", "title": "افلام اجنبي", "url": self.getFullUrl("/category/foreign-movies-10/")},
            {"category": "list_items", "title": "افلام Netfilx", "url": self.getFullUrl("/category/netfilx/افلام-netfilx/")},
            {"category": "list_items", "title": "افلام هندى", "url": self.getFullUrl("/category/indian-movies/")},
            {"category": "list_items", "title": "افلام تركية", "url": self.getFullUrl("/category/turkish-movies/")},
            {"category": "list_items", "title": "افلام اسيوية", "url": self.getFullUrl("/category/asian-movies/")},
            {"category": "list_items", "title": "افلام كلاسيكيه", "url": self.getFullUrl("/category/افلام-كلاسيكيه/")},
            {"category": "list_items", "title": "افلام مدبلجة", "url": self.getFullUrl("/category/افلام-مدبلجة-1/")},
        ]
        self.SERIES_CAT_TAB = [
            {"category": "series", "title": "مسلسلات عربية", "url": self.getFullUrl("/category/arabic-series-8/")},
            {"category": "series", "title": "مسلسلات مصرية", "url": self.getFullUrl("/category/مسلسلات-مصريه/")},
            {"category": "series", "title": "مسلسلات اجنبية", "url": self.getFullUrl("/category/foreign-series-3/")},
            {"category": "series", "title": "مسلسلات Netfilx", "url": self.getFullUrl("/category/netfilx/مسلسلات-netfilx-1/")},
            {"category": "series", "title": "مسلسلات تركية", "url": self.getFullUrl("/category/turkish-series-2/")},
            {"category": "series", "title": "مسلسلات هندية", "url": self.getFullUrl("/category/مسلسلات-هندية/")},
            {"category": "series", "title": "مسلسلات كورية", "url": self.getFullUrl("/category/مسلسلات-كوريه/")},
            {"category": "series", "title": "مسلسلات مدبلجة", "url": self.getFullUrl("/category/مسلسلات-مدبلجة/")},
            {"category": "series", "title": "مسلسلات كرتون", "url": self.getFullUrl("/category/cartoon-series/")},
        ]
        self.SERIES_PACKS_CAT_TAB = [
            {"category": "series_packs", "title": "مواسم مسلسلات عربية", "url": self.getFullUrl("/category/arabic-series-8/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات مصرية", "url": self.getFullUrl("/category/مسلسلات-مصريه/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات اجنبية", "url": self.getFullUrl("/category/foreign-series-3/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات تركية", "url": self.getFullUrl("/category/turkish-series-2/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات هندية", "url": self.getFullUrl("/category/مسلسلات-هندية/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات كورية", "url": self.getFullUrl("/category/مسلسلات-كوريه/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات مدبلجة", "url": self.getFullUrl("/category/مسلسلات-مدبلجة/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2026", "url": self.getFullUrl("/category/مسلسلات-رمضان/ramadan-series-2026/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2025", "url": self.getFullUrl("/category/مسلسلات-رمضان/ramadan-series-2025/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2024", "url": self.getFullUrl("/category/مسلسلات-رمضان/ramadan-series-2024/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2023", "url": self.getFullUrl("/category/مسلسلات-رمضان/ramadan-series-2023/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2022", "url": self.getFullUrl("/category/مسلسلات-رمضان/مسلسلات-رمضان-2022/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2021", "url": self.getFullUrl("/category/مسلسلات-رمضان/مسلسلات-رمضان-2021/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2020", "url": self.getFullUrl("/category/مسلسلات-رمضان/مسلسلات-رمضان-2020-hd/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات رمضان 2019", "url": self.getFullUrl("/category/مسلسلات-رمضان/مسلسلات-رمضان-2019/packs/")},
            {"category": "series_packs", "title": "مواسم برامج تليفزيونية", "url": self.getFullUrl("/category/برامج-تلفزيونية/packs/")},
            {"category": "series_packs", "title": "مواسم مسلسلات كرتون", "url": self.getFullUrl("/category/cartoon-series/packs/")},
        ]
        self.RAMADAN_CAT_TAB = [
            {"category": "series", "title": "مسلسلات رمضان 2026", "url": self.getFullUrl("/category/مسلسلات-رمضان/ramadan-series-2026/")},
            {"category": "series", "title": "مسلسلات رمضان 2025", "url": self.getFullUrl("/category/مسلسلات-رمضان/ramadan-series-2025/")},
            {"category": "series", "title": "مسلسلات رمضان 2024", "url": self.getFullUrl("/category/مسلسلات-رمضان/ramadan-series-2024/")},
            {"category": "series", "title": "مسلسلات رمضان 2023", "url": self.getFullUrl("/category/مسلسلات-رمضان/ramadan-series-2023/")},
            {"category": "series", "title": "مسلسلات رمضان 2022", "url": self.getFullUrl("/category/مسلسلات-رمضان/مسلسلات-رمضان-2022/")},
            {"category": "series", "title": "مسلسلات رمضان 2021", "url": self.getFullUrl("/category/مسلسلات-رمضان/مسلسلات-رمضان-2021/")},
            {"category": "series", "title": "مسلسلات رمضان 2020", "url": self.getFullUrl("/category/مسلسلات-رمضان/مسلسلات-رمضان-2020-hd/")},
            {"category": "series", "title": "مسلسلات رمضان 2019", "url": self.getFullUrl("/category/مسلسلات-رمضان/مسلسلات-رمضان-2019/")},
        ]
        self.ANIME_CAT_TAB = [
            {"category": "list_items", "title": "افلام انيميشن", "url": self.getFullUrl("/category/افلام-انيميشن/")},
            {"category": "series", "title": "مسلسلات كرتون", "url": self.getFullUrl("/category/cartoon-series/")},
        ]
        self.OTHER_CAT_TAB = [{"category": "list_items", "title": "اغاني عربي", "url": self.getFullUrl("/category/اغاني-عربي/")}, {"category": "list_items", "title": "مصارعه", "url": self.getFullUrl("/category/wwe-shows-1/")}, {"category": "list_items", "title": "برامج تلفزيونية", "url": self.getFullUrl("/category/برامج-تلفزيونية/")}, {"category": "list_items", "title": "مسرحيات عربيه", "url": self.getFullUrl("/category/مسرحيات-عربي/")}]
        # Display main categories
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMoviesFolder(self, cItem):
        printDBG("ArabSeed.listMoviesFolder")
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesFolder(self, cItem):
        printDBG("ArabSeed.listSeriesFolder")
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listSeriesPacksFolder(self, cItem):
        printDBG("ArabSeed.listSeriesPacksFolder")
        self.listsTab(self.SERIES_PACKS_CAT_TAB, cItem)

    def listRamadanFolder(self, cItem):
        printDBG("ArabSeed.listRamadanFolder")
        self.listsTab(self.RAMADAN_CAT_TAB, cItem)

    def listAnimeFolder(self, cItem):
        printDBG("ArabSeed.listAnimeFolder")
        self.listsTab(self.ANIME_CAT_TAB, cItem)

    def listOtherFolder(self, cItem):
        printDBG("ArabSeed.listOtherFolder")
        self.listsTab(self.OTHER_CAT_TAB, cItem)

    def listItems(self, cItem):
        printDBG("ArabSeed.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        data_items = re.findall(r'<li[^>]*class="[^"]*box__xs__2[^"]*"[^>]*>(.*?)</li>', data, re.S)
        printDBG("Items found: %s" % len(data_items))
        for m in data_items:
            # Extract basic info
            title = self.cm.ph.getSearchGroups(m, r'title=[\'"]([^\'"]+)[\'"]')[0]
            pureurl = self.cm.ph.getSearchGroups(m, r'href=[\'"]([^\'"]+)[\'"]')[0]
            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=[\'"]([^\'"]+)[\'"]')[0]
            # Fix URLs safely
            if pureurl:
                baseurl, filenameurl = pureurl.rsplit("/", 1)
                fixedfilenameurl = urllib_quote_plus(filenameurl)
                url = baseurl + "/" + fixedfilenameurl + "watch/"
            else:
                url = ""
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit("/", 1)
                fixedfilenameicon = urllib_quote_plus(filenameicon)
                icon = baseicon + "/" + fixedfilenameicon
            else:
                icon = ""
            ###################################################
            # Extract genre, quality, and story
            ###################################################
            genre = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__genre hide__md">', "</div>", False)[1]).strip()
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__quality hide__md">', "</div>", False)[1]).strip()
            Ratings = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="post__ratings">', "</div>", False)[1]).strip()
            story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, "<p>", "</p>", False)[1]).strip()
            # # Build combined description
            line1_parts = []
            line2_parts = []
            if genre:
                line1_parts.append(f"{E2ColoR('yellow')}Genre:{E2ColoR('white')} {genre}")
            if quality:
                q_color = "white"
                if re.search(r"4K|1080|HD|BluRay", quality, re.I):
                    q_color = "green"
                elif re.search(r"720|HDRip|WEB", quality, re.I):
                    q_color = "orange"
                elif re.search(r"CAM|TS|HDCAM", quality, re.I):
                    q_color = "red"
                line1_parts.append(f"{E2ColoR('yellow')}Quality:{E2ColoR('white')} " f"{E2ColoR(q_color)}{quality}{E2ColoR('white')}")
            if Ratings:
                rate_match = re.search(r"(\d+(\.\d+)?)", Ratings)
                rate_color = "white"
                if rate_match:
                    rate_value = float(rate_match.group(1))
                    if rate_value >= 7:
                        rate_color = "green"
                    elif rate_value >= 5:
                        rate_color = "orange"
                    else:
                        rate_color = "red"
                line1_parts.append(f"{E2ColoR('yellow')}Ratings:{E2ColoR('white')} " f"{E2ColoR(rate_color)}{Ratings}{E2ColoR('white')}")
            if story:
                line2_parts.append(f"{E2ColoR('yellow')}Story:{E2ColoR('white')} {story}")
            desc = " | ".join(line1_parts)
            if line2_parts:
                desc += "\n" + " ".join(line2_parts)
            ###################################################
            # Colorize title (movie name + year)
            ###################################################
            colored_title = self.colorizeTitle(title)
            ###################################################
            # Final item
            ###################################################
            params = {"category": "explore_item", "title": colored_title, "icon": icon, "url": url, "desc": desc}
            self.addDir(params)
        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', "</div>", False)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
        if next_page:
            next_page = self.getFullUrl(next_page)
            printDBG("NEXT PAGE FOUND >>> %s" % next_page)
            params = dict(cItem)
            params.update(
                {
                    "title": "Next Page ▶",
                    "url": next_page,
                    "category": "list_items",
                }
            )
            self.addDir(params)

    def listSeriesItems(self, cItem):
        printDBG("ArabSeed.listSeriesItems ----------")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="box__xs__2', "</li>")
        for m in data_items:
            title = self.cm.ph.getSearchGroups(m, r'title=[\'"]([^\'"]+)[\'"]')[0]
            pureurl = self.cm.ph.getSearchGroups(m, r'href=[\'"]([^\'"]+)[\'"]')[0]
            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=[\'"]([^\'"]+)[\'"]')[0]
            if pureurl:
                baseurl, filenameurl = pureurl.rsplit("/", 1)
                fixedfilenameurl = urllib_quote_plus(filenameurl)
                url = baseurl + "/" + fixedfilenameurl + "watch/"
            else:
                url = ""
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit("/", 1)
                fixedfilenameicon = urllib_quote_plus(filenameicon)
                icon = baseicon + "/" + fixedfilenameicon
            else:
                icon = ""
            ###################################################
            # Extract genre, quality, and story
            ###################################################
            genre = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__genre hide__md">', "</div>", False)[1]).strip()
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__quality hide__md">', "</div>", False)[1]).strip()
            Ratings = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="post__ratings">', "</div>", False)[1]).strip()
            story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, "<p>", "</p>", False)[1]).strip()
            first_line_parts = []
            if genre:
                first_line_parts.append(f"{E2ColoR('yellow')}Genre:{E2ColoR('white')} {genre}")
            if quality:
                q_color = "white"
                if re.search(r"4K|1080|HD|BluRay", quality, re.I):
                    q_color = "green"
                elif re.search(r"720|HDRip|WEB", quality, re.I):
                    q_color = "orange"
                elif re.search(r"CAM|TS|HDCAM", quality, re.I):
                    q_color = "red"
                first_line_parts.append(f"{E2ColoR('yellow')}Quality:{E2ColoR('white')} " f"{E2ColoR(q_color)}{quality}{E2ColoR('white')}")
            if Ratings:
                rate_match = re.search(r"(\d+(\.\d+)?)", Ratings)
                rate_color = "white"
                rate_text = Ratings
                if rate_match:
                    rate_value = float(rate_match.group(1))
                    if rate_value >= 7:
                        rate_color = "green"
                    elif rate_value >= 5:
                        rate_color = "orange"
                    else:
                        rate_color = "red"
                first_line_parts.append(f"{E2ColoR('yellow')}Ratings:{E2ColoR('white')} " f"{E2ColoR(rate_color)}{rate_text}{E2ColoR('white')}")
            line1 = " | ".join(first_line_parts)
            line2 = ""
            if story:
                line2 = f"{E2ColoR('yellow')}Story:{E2ColoR('white')} {story}"
            desc = line1
            if line2:
                desc += "\n" + line2
            ###################################################
            # Colorize title (movie name + year)
            ###################################################
            colored_title = self.colorizeTitle(title)
            ###################################################
            # Final item
            ###################################################
            params = {"category": "explore_item", "title": colored_title, "icon": icon, "url": url, "desc": desc}
            printDBG(str(params))
            self.addDir(params)
        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="paginate">', "</div>", False)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"')[0]
        if next_page:
            next_page = self.getFullUrl(next_page)
            printDBG("NEXT PAGE FOUND >>> %s" % next_page)
            params = dict(cItem)
            params.update(
                {
                    "title": "Next Page ▶",
                    "url": next_page,
                    "category": "series",
                }
            )
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG("ArabSeed.exploreItems >>> %s" % cItem)
        url = cItem.get("url")
        sts, data = self.cm.getPage(url)
        if not sts or not data:
            return
        videos = []
        processed_urls = []
        csrf_token = self.cm.ph.getSearchGroups(data, r"['\s]csrf__token['\s:]+['\"]([^'\"]+)")[0]
        post_id = self.cm.ph.getSearchGroups(data, r"psot_id['\s:]+['\"](\d+)")[0] or self.cm.ph.getSearchGroups(data, r"post_id['\s:]+['\"](\d+)")[0]
        if csrf_token and post_id:
            qualities = ["1080", "720", "480"]
            for qu in qualities:
                for server_id in range(0, 6):
                    ajax_url = "https://asd.pics/get__watch__server/"
                    post_data = {"post_id": post_id, "quality": qu, "server": str(server_id), "csrf_token": csrf_token}
                    ajax_headers = {"X-Requested-With": "XMLHttpRequest", "Referer": url, "User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
                    sts_ajax, json_data = self.cm.getPage(ajax_url, {"header": ajax_headers}, post_data)
                    if not sts_ajax:
                        continue
                    try:
                        res = json.loads(json_data)
                        if res.get("type") == "success" and res.get("server"):
                            video_url = res["server"]
                            if "url=" in video_url or "id=" in video_url:
                                b64_match = re.search(r"(?:url=|id=)([A-Za-z0-9+/=]+)", video_url)
                                if b64_match:
                                    b64_str = b64_match.group(1)
                                    b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
                                    video_url = base64.b64decode(b64_str).decode("utf-8")
                            if video_url not in processed_urls:
                                domain = re.search(r"https?://([^/]+)", video_url)
                                domain_name = domain.group(1) if domain else ""
                                is_arabseed = server_id == 0 or "reviewrate" in domain_name
                                s_name = "سيرفر عرب سيد" if is_arabseed else ("سيرفر %s (%s)" % (server_id, domain_name))
                                videos.append({"quality": qu, "server": s_name, "url": video_url, "is_arabseed": is_arabseed, "need_resolve": 0 if is_arabseed else 1})
                                processed_urls.append(video_url)
                    except:
                        continue

        def sort_key(v):
            q_val = int(v["quality"])
            priority = 0 if v["is_arabseed"] else 1
            quality_order = -q_val
            return (priority, quality_order)

        videos.sort(key=sort_key)
        for v in videos:
            clean_title = "[%sP] - %s" % (v["quality"], v["server"])
            title = clean_title
            if hasattr(self, "colorizeServer"):
                title = self.colorizeServer(v["server"], v["quality"])
            self.addVideo({"title": title, "url": v["url"], "type": "video", "need_resolve": v["need_resolve"]})
        printDBG("ArabSeed.exploreItems <<< done")

    def exploreSeriesItems(self, cItem):
        printDBG("ArabSeed.exploreSeriesItems >>> %s" % cItem)
        url = cItem.get("url")
        if not url:
            return
        # --- Load the episode page ---
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("[ArabSeed] Failed to load episode page: %s" % url)
            return

        # --- Extract token and post_id ---
        def extract_first(patterns, data_src):
            for p in patterns:
                try:
                    v = self.cm.ph.getSearchGroups(data_src, p)[0]
                    if v:
                        return v.strip()
                except Exception:
                    continue
            return ""

        token = extract_first([r"csrf__token['\"]:\s*['\"]([^'\"]+)", r"csrf_token['\"]:\s*['\"]([^'\"]+)", r"name=['\"]csrf-token['\"]\s+content=['\"]([^'\"]+)"], data)
        post_id = extract_first([r"psot_id['\"]:\s*'([^']+)'", r"post_id['\"]:\s*['\"]([^'\"]+)", r"post_id\s*:\s*'([^']+)'"], data)
        if not token or not post_id:
            printDBG("[ArabSeed] Missing required POST params (csrf_token or post_id/psot_id)")
            return
        # --- Constants ---
        post_url = "https://asd.pics/get__watch__server/"
        servers = [0, 1, 2, 3, 4]
        qualities = [480, 720, 1080]
        # --- Loop through servers and qualities ---
        for server in servers:
            for quality in qualities:
                payload = {"post_id": post_id, "quality": str(quality), "server": str(server), "csrf_token": token}
                headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest", "Referer": url}
                sts2, response = self.cm.getPage(post_url, {"header": headers, "raw_post_data": True}, self.urlencode(payload))
                if not sts2 or not response:
                    continue
                try:
                    result = json_loads(response)
                except Exception as e:
                    printDBG("JSON decode error (series): %s" % str(e))
                    continue
                if result.get("type") != "success":
                    continue
                link = result.get("server", "")
                if not link:
                    continue
                # --- Normalize server name ---
                server_name = self.cm.ph.getSearchGroups(link, r"https?://([^/]+)/")[0]
                if server_name in ["m.reviewrate.net", "m.reviewtech.me"]:
                    server_name = "ArabSeed"
                if not server_name:
                    server_name = "server%d" % server
                # --- Add video entry ---
                colored_server = self.colorizeServer(server_name, quality)
                colored_title = self.colorizeTitle(cItem.get("title", "Episode"))
                params_video = MergeDicts(
                    cItem,
                    {
                        "title": f"{colored_title} - {colored_server}",
                        "url": link,
                        "type": "video",
                        "category": "video",
                        "need_resolve": 1,
                    },
                )
                self.addVideo(params_video)

    def safe_b64decode(self, data):
        """Base64 decode with automatic padding fix."""
        data += "=" * (-len(data) % 4)
        return base64.b64decode(data).decode("utf-8")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ArabSeed.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        page = cItem.get("page", 1)
        cItem = dict(cItem)
        cItem["search_pattern"] = searchPattern
        cItem["page"] = page
        cItem["url"] = self.getFullUrl("find/?word=") + urllib_quote_plus(searchPattern) + "&type&page_number=" + str(page)
        self.listSearchItems(cItem)

    def listSearchItems(self, cItem):
        printDBG("ArabSeed.listSearchItems [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="series__list">', '<div class="paginate">', False)[1]
        printDBG("tmp.listSearchItems [%s]" % tmp)
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li class="box__xs__2', "</li>")
        printDBG("data_items.listSearchItems [%s]" % data_items)
        for m in data_items:
            # Extract basic info
            title = self.cm.ph.getSearchGroups(m, r'title=[\'"]([^\'"]+)[\'"]')[0]
            pureurl = self.cm.ph.getSearchGroups(m, r'href=[\'"]([^\'"]+)[\'"]')[0]
            pureicon = self.cm.ph.getSearchGroups(m, r'data-src=[\'"]([^\'"]+)[\'"]')[0]
            # Fix URLs safely
            if pureurl:
                baseurl, filenameurl = pureurl.rsplit("/", 1)
                fixedfilenameurl = urllib_quote_plus(filenameurl)
                url = baseurl + "/" + fixedfilenameurl + "watch/"
            else:
                url = ""
            if pureicon:
                baseicon, filenameicon = pureicon.rsplit("/", 1)
                fixedfilenameicon = urllib_quote_plus(filenameicon)
                icon = baseicon + "/" + fixedfilenameicon
            else:
                icon = ""
            ###################################################
            # Extract genre, quality, and story
            ###################################################
            genre = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__genre hide__md">', "</div>", False)[1]).strip()
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="__quality hide__md">', "</div>", False)[1]).strip()
            section = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<div class="post__category hide__md">', "</div>", False)[1]).strip()
            story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, "<p>", "</p>", False)[1]).strip()
            # Build combined description
            line1_parts = []
            line2_parts = []
            if genre:
                line1_parts.append(f"{E2ColoR('yellow')}Genre:{E2ColoR('white')} {genre}")
            if quality:
                q_color = "white"
                if re.search(r"4K|1080|HD|BluRay", quality, re.I):
                    q_color = "green"
                elif re.search(r"720|HDRip|WEB", quality, re.I):
                    q_color = "orange"
                elif re.search(r"CAM|TS|HDCAM", quality, re.I):
                    q_color = "red"
                line1_parts.append(f"{E2ColoR('yellow')}Quality:{E2ColoR('white')} " f"{E2ColoR(q_color)}{quality}{E2ColoR('white')}")
            if section:
                line1_parts.append(f"{E2ColoR('yellow')}Section:{E2ColoR('white')} {section}")
            if story:
                line2_parts.append(f"{E2ColoR('yellow')}Story:{E2ColoR('white')} {story}")
            desc = " | ".join(line1_parts)
            if line2_parts:
                desc += "\n" + " ".join(line2_parts)
            ###################################################
            # Colorize title (movie name + year)
            ###################################################
            colored_title = self.colorizeTitle(title)
            ###################################################
            # Final item
            ###################################################
            params = {"category": "explore_item", "title": colored_title, "icon": icon, "url": url, "desc": desc}
            printDBG(str(params))
            self.addDir(params)
        page = cItem.get("page", 1)
        next_page = page + 1
        if len(data_items) > 0:
            params = dict(cItem)
            params.update(
                {
                    "title": _("Next Page") + " ▶",
                    "page": next_page,
                }
            )
            self.addDir(params)

    def getFavouriteData(self, cItem):
        printDBG("ArabSeed.getFavouriteData")
        return json_dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG("ArabSeed.getLinksForFavourite")
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG("ArabSeed.setInitListFromFavouriteItem")
        try:
            cItem = json_loads(fav_data)
        except Exception:
            cItem = {}
            printExc()
        return cItem

    ###################################################
    # SERIES PACKS FLOW
    # series_packs_folder → listSeriesPacks()
    # series_seasons_list   → listSeasons()
    # series_episodes_list → listEpisodes()
    # explore_episodes    → exploreSeriesItems()
    ###################################################
    def listSeriesPacks(self, cItem):
        printDBG("ArabSeed.listSeriesPacks >>> %s" % cItem)
        url = cItem.get("url", "").strip()
        if not url:
            return
        # Step 1: Load the page directly (GET request)
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("[ArabSeed] Failed to load packs page: %s" % url)
            return
        # Step 2: Extract csrf__token from the page (for pagination)
        token = self.cm.ph.getSearchGroups(data, r"csrf__token['\"]:\s*[\"']([^\"']+)")[0]
        printDBG("listSeriesPacks token >>> %s" % token)
        if not token:
            printDBG("[ArabSeed] No csrf__token found!")
        # Step 3: Parse the page content directly
        start_marker = '<div class="movie__blocks" id="ajax__area">'
        end_marker = '<div class="footer'
        if start_marker in data:
            content = self.cm.ph.getDataBeetwenMarkers(data, start_marker, end_marker, False)[1]
            html = content
        else:
            html = data
        # Step 4: Parse HTML list
        items = re.findall(r'(<li class="box__xs__1.*?)(?=<li class="box__xs__1|\Z)', html, re.DOTALL)
        for item in items:
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0].strip()
            title = self.cm.ph.getSearchGroups(item, r'<div class="title___">([^<]+)</div>')[0].strip()
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0].strip()
            href = quote(href, safe=":/?&=%")
            icon = quote(icon, safe=":/?&=%")
            if not href or not title:
                continue
            colored_title = self.colorizeTitle(title)
            # ===== DESCRIPTION (FIXED & ROBUST) =====
            year = country = genre = quality = story = ""
            desc_parts = []
            # ---------- STORY ----------
            story = self.cm.ph.getDataBeetwenMarkers(item, '<p class="story">', "</p>", False)[1].strip()
            # ---------- HOVER BOX ----------
            hover_box = self.cm.ph.getDataBeetwenMarkers(item, '<div class="hover__box', "</div>", False)[1]
            # ---------- DOTS INFO ----------
            dots_info = self.cm.ph.getDataBeetwenMarkers(hover_box, '<ul class="dots__info">', "</ul>", False)[1]
            if dots_info:
                spans = self.cm.ph.getAllItemsBeetwenMarkers(dots_info, "<span>", "</span>")
                if len(spans) > 0:
                    year = self.cleanHtmlStr(spans[0])
                if len(spans) > 1:
                    country = self.cleanHtmlStr(spans[1])
            # ---------- QUALITY / GENRE ----------
            bottom_ul = self.cm.ph.getDataBeetwenMarkers(hover_box, '<ul class="bottom__ul">', "</ul>", False)[1]
            if bottom_ul:
                li_items = self.cm.ph.getAllItemsBeetwenMarkers(bottom_ul, "<li>", "</li>")
                if len(li_items) > 0:
                    quality = self.cleanHtmlStr(li_items[0])
                if len(li_items) > 1:
                    genre = self.cleanHtmlStr(li_items[1])
            # ---------- QUALITY COLOR ----------
            q_color = "white"
            if quality:
                if re.search(r"4K|2160|1080|BluRay|FHD", quality, re.I):
                    q_color = "green"
                elif re.search(r"720|WEB|HDRip|HD", quality, re.I):
                    q_color = "orange"
                elif re.search(r"CAM|TS|HDCAM|SD", quality, re.I):
                    q_color = "red"
            # ---------- BUILD DESC ----------
            if quality:
                desc_parts.append(f"{E2ColoR('yellow')}Quality : {E2ColoR(q_color)}{quality}{E2ColoR('white')}")
            if genre:
                desc_parts.append(f"{E2ColoR('yellow')}Genre : {E2ColoR('white')}{genre}")
            if year:
                desc_parts.append(f"{E2ColoR('yellow')}Year : {E2ColoR('white')}{year}")
            if country:
                desc_parts.append(f"{E2ColoR('yellow')}Country : {E2ColoR('white')}{country}")
            desc = " | ".join(desc_parts)
            if story:
                desc += f"\n{E2ColoR('yellow')}Story : {E2ColoR('white')}{story}"
            printDBG("ICON URL >>> %s" % icon)
            params = dict(cItem)
            params.update({"category": "series_seasons_list", "title": colored_title, "url": href, "icon": icon, "desc": desc, "csrf_token": token})
            printDBG(f"Description for '{colored_title}': {desc}")
            self.addDir(params)
        # Step 5: Pagination
        pagination_match = re.search(r"<ul class=\'page-numbers\'>(.*?)</ul>", data, re.DOTALL)
        if pagination_match:
            pagination_html = pagination_match.group(1)
            printDBG("pagination_html >>> %s" % pagination_html)
            next_page_match = re.search(r'<a[^>]+class="next page-numbers"[^>]+href="([^"]+)"', pagination_html)
            if next_page_match:
                next_page = next_page_match.group(1).strip()
                next_page = next_page.replace(" ", "")
                if next_page.startswith("http://") or next_page.startswith("https://"):
                    parsed = re.search(r"https?://[^/]+(/.*)", next_page)
                    if parsed:
                        next_page = parsed.group(1)
                    else:
                        next_page = "/" + next_page.split("/", 3)[-1] if len(next_page.split("/")) > 3 else next_page
                next_page = next_page.replace("/packs/packs/", "/packs/")
                if not next_page.startswith("/"):
                    next_page = "/" + next_page
                next_page_url = self.MAIN_URL.rstrip("/") + next_page
                printDBG("Built next_page_url >>> %s" % next_page_url)
                params = dict(cItem)
                params.update({"title": _("Next Page") + " ▶", "url": next_page_url, "category": "series_packs"})
                self.addDir(params)
        printDBG("ArabSeed.listSeriesPacks <<< done")

    def listSeasons(self, cItem):
        printDBG("ArabSeed.listSeasons >>> %s" % cItem)
        url = cItem.get("url")
        csrf_token = cItem.get("csrf_token", "")
        if not url or not csrf_token:
            printDBG("[ArabSeed] Missing params in listSeasons")
            return
        # Step 1: Load series page
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("[ArabSeed] Failed to load series page")
            return
        # --- Trailer ---
        trailer_url = self.cm.ph.getSearchGroups(data, r'data-iframe="([^"]+)"')[0]
        if trailer_url:
            # YouTube
            if "youtube.com/embed/" in trailer_url:
                trailer_url = trailer_url.replace("youtube.com/embed/", "youtube.com/watch?v=")
            # IMDb
            elif "imdb.com/video/" in trailer_url:
                pass
            params = dict(cItem)
            params.update({"title": f"{E2ColoR('lime')}TRAILER{E2ColoR('white')}", "url": trailer_url, "type": "video", "need_resolve": 1})
            self.addVideo(params)
        printDBG("[ArabSeed] trailer_url = %s" % trailer_url)
        # Step 2: Try to get seasons list
        seasons_block = self.cm.ph.getDataBeetwenMarkers(data, 'id="seasons__list"', "</div></div>", False)[1]
        if seasons_block:
            # Seasons exist
            season_items = self.cm.ph.getAllItemsBeetwenMarkers(seasons_block, "<li", "</li>")
            for s in season_items:
                season_id = self.cm.ph.getSearchGroups(s, r'data-term="([^"]+)"')[0]
                title = self.cm.ph.getSearchGroups(s, r"<span>([^<]+)</span>")[0]
                if not season_id or not title:
                    continue
                params = dict(cItem)
                params.update({"category": "series_episodes_list", "title": title.strip(), "url": url, "season_id": season_id, "csrf_token": csrf_token})
                self.addDir(params)
            printDBG("ArabSeed.listSeasons <<< done with seasons")
        else:
            # No seasons → try direct episodes
            printDBG("[ArabSeed] No seasons found → trying direct episodes")
            episodes_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="episodes__list', "</ul>", False)[1]
            if episodes_block:
                episodes = self.cm.ph.getAllItemsBeetwenMarkers(episodes_block, "<li", "</li>")
                episodes.reverse()
                for ep in episodes:
                    ep_url = self.cm.ph.getSearchGroups(ep, r'href="([^"]+)"')[0]
                    if not ep_url:
                        continue
                    ep_num = self.cm.ph.getSearchGroups(ep, r"<b>(\d+)</b>")[0]
                    title = "الحلقة %s" % ep_num if ep_num else "حلقة"
                    params = dict(cItem)
                    params.update({"title": title, "url": ep_url + "watch/", "type": "video", "category": "explore_episodes"})
                    self.addDir(params)
                printDBG("ArabSeed.listSeasons <<< done with direct episodes")
                return
            # ==================================================
            # STEP EXTRA: single promo / one episode only
            # ==================================================
            promo_url = self.cm.ph.getSearchGroups(
                data,
                r'<div class="watch__and__download.*?<a href="([^"]+/watch/)"',
            )[0]
            if promo_url:
                printDBG("[ArabSeed] Single promo episode detected")
                params = dict(cItem)
                params.update({"title": f"{E2ColoR('yellow')}برومو المسلسل{E2ColoR('white')}", "url": promo_url, "type": "video", "category": "explore_episodes"})
                self.addDir(params)
                return
            printDBG("[ArabSeed] No episodes found at all")

    def getIMDBTrailer(self, url):
        printDBG("IMDB resolver start >>> %s" % url)
        links = []
        vid = self.cm.ph.getSearchGroups(url, r"(vi\d+)")[0]
        if not vid:
            printDBG("IMDB: video id not found")
            return []
        embed_url = "https://www.imdb.com/video/embed/%s/" % vid
        printDBG("IMDB embed URL >>> %s" % embed_url)
        sts, data = self.cm.getPage(embed_url)
        if not sts:
            printDBG("IMDB: failed to load embed page")
            return []
        json_data = self.cm.ph.getSearchGroups(data, r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')[0]
        if not json_data:
            printDBG("IMDB: __NEXT_DATA__ not found")
            return []
        json_data = json.loads(json_data)
        try:
            videoData = json_data["props"]["pageProps"].get("videoEmbedPlaybackData")
            if not videoData:
                printDBG("IMDB: videoEmbedPlaybackData not found")
                return []
            qualities = []
            for item in videoData.get("playbackURLs", []):
                mime = item.get("videoMimeType", "").lower()
                url = item.get("url")
                if not url:
                    continue
                if mime != "mp4":
                    continue
                display = item.get("displayName", {})
                quality_txt = display.get("value", "")
                try:
                    quality = int(quality_txt.replace("p", "").strip())
                except:
                    continue
                qualities.append({"q": quality, "name": "IMDb %dp" % quality, "url": url, "need_resolve": 0})
            qualities.sort(key=lambda x: x["q"], reverse=True)
            for q in qualities:
                links.append({"name": q["name"], "url": q["url"], "need_resolve": 0})
        except Exception as e:
            printDBG("IMDB extraction error: %s" % e)
        return links

    def listEpisodes(self, cItem):
        printDBG("ArabSeed.listEpisodes >>> %s" % cItem)
        url = cItem.get("url")
        season_id = cItem.get("season_id", "")
        csrf_token = cItem.get("csrf_token", "")
        if not url or not season_id or not csrf_token:
            printDBG("[ArabSeed] Missing required params")
            return
        sts, page_data = self.getPage(url)
        if sts:
            selected_season = self.cm.ph.getSearchGroups(page_data, r'<li[^>]+class="selected"[^>]+data-term="(\d+)"')[0]
            if selected_season == season_id:
                printDBG("[ArabSeed] First season detected")
                episodes = self.cm.ph.getAllItemsBeetwenMarkers(page_data, "<li", "</li>")
                episodes.reverse()
                count = 0
                for ep in episodes:
                    ep_num = self.cm.ph.getSearchGroups(ep, r"الحلقة[^0-9]*<b>(\d+)</b>")[0]
                    if not ep_num:
                        continue
                    ep_url = self.cm.ph.getSearchGroups(ep, r'href="([^"]+)"')[0]
                    if not ep_url:
                        continue
                    ep_url += "watch/"
                    title = "الحلقة %s" % ep_num
                    icon = self.cm.ph.getSearchGroups(ep, r'data-src="([^"]+)"')[0] or cItem.get("icon", "")
                    params = dict(cItem)
                    params.update({"category": "explore_episodes", "type": "video", "title": title, "url": ep_url, "icon": icon})
                    self.addDir(params)
                    count += 1
                printDBG("Found %d episodes (first season clean)" % count)
                printDBG("ArabSeed.listEpisodes <<< done (first season)")
                return
        post_url = self.getFullUrl("/season__episodes/")
        post_data = {"season_id": season_id, "csrf_token": csrf_token}
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest", "Referer": url}
        sts, response = self.cm.getPage(post_url, {"header": headers}, post_data)
        if not sts:
            return
        try:
            result = json_loads(response)
        except:
            return
        if result.get("type") != "success":
            return
        html = result.get("html", "")
        episodes = self.cm.ph.getAllItemsBeetwenMarkers(html, "<li", "</li>")
        episodes.reverse()
        count = 0
        for ep in episodes:
            ep_num = self.cm.ph.getSearchGroups(ep, r"الحلقة[^0-9]*<b>(\d+)</b>")[0]
            if not ep_num:
                continue
            ep_url = self.cm.ph.getSearchGroups(ep, r'href="([^"]+)"')[0]
            if not ep_url:
                continue
            ep_url += "watch/"
            title = "الحلقة %s" % ep_num
            icon = self.cm.ph.getSearchGroups(ep, r'data-src="([^"]+)"')[0] or cItem.get("icon", "")
            params = dict(cItem)
            params.update({"category": "explore_episodes", "type": "video", "title": title, "url": ep_url, "icon": icon})
            self.addDir(params)
            count += 1
        printDBG("Found %d episodes (ajax clean)" % count)
        printDBG("ArabSeed.listEpisodes <<< done (ajax)")

    ###################################################
    # COLOR HELPERS
    ###################################################
    def colorizeTitle(self, title):
        """
        Detects movie title and year in different formats and colorizes both.
        Handles: 2025, (2025), ( 2025 ), - 2025, [2025]
        """
        if not title:
            return title
        # Match year in various wrapping formats
        match = re.search(r"(.+?)\s*(?:\(|\[|-)?\s*(\d{4})\s*(?:\)|\])?$", title)
        if match:
            movie_title = match.group(1).strip()
            movie_year = match.group(2).strip()
            return f"{E2ColoR('yellow')}{movie_title} " f"{E2ColoR('cyan')}{movie_year}{E2ColoR('white')}"
        else:
            return f"{E2ColoR('yellow')}{title}{E2ColoR('white')}"

    def colorizeQuality(self, quality):
        """
        Detect quality level and assign colors
        """
        q_color = "white"
        if re.search(r"4K|1080|BluRay", quality, re.I):
            q_color = "green"
        elif re.search(r"720|HDRip|WEB", quality, re.I):
            q_color = "yellow"
        elif re.search(r"CAM|TS|HDCAM", quality, re.I):
            q_color = "red"
        return f"{E2ColoR(q_color)}{quality if quality else 'N/A'}{E2ColoR('white')}"

    def colorizeServer(self, name, quality):
        """
        Combine server name + quality with colorized labels
        """
        q_colored = self.colorizeQuality(str(quality))
        return f"{E2ColoR('cyan')}{name}{E2ColoR('white')} [{q_colored}]"

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("ArabSeed.handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []
        # MAIN MENU
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "series":
            self.listSeriesItems(self.currItem)
        # FOLDERS
        elif category == "movies_folder":
            self.listMoviesFolder(self.currItem)
        elif category == "series_folder":
            self.listSeriesFolder(self.currItem)
        elif category == "series_packs_folder":
            self.listSeriesPacksFolder(self.currItem)
        elif category == "series_packs":
            self.listSeriesPacks(self.currItem)
        elif category == "series_seasons_list":
            self.listSeasons(self.currItem)
        elif category == "series_episodes_list":
            self.listEpisodes(self.currItem)
        elif category == "explore_episodes":
            self.exploreSeriesItems(self.currItem)
        elif category == "ramadan_folder":
            self.listRamadanFolder(self.currItem)
        elif category == "anime_folder":
            self.listAnimeFolder(self.currItem)
        elif category == "other_folder":
            self.listOtherFolder(self.currItem)
        elif category == "explore_item":
            self.exploreItems(self.currItem)
        # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        # HISTORY SEARCH
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, ArabSeed(), True, [])

    def withArticleContent(self, cItem):
        if "video" == cItem.get("type", "") or "explore_item" == cItem.get("category", ""):
            return True
        return False
