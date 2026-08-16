# -*- coding: utf-8 -*-
# Last modified: 08/04/2026
# Brstej Host (Modified By Mohamed Elsafty)
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR, CSearchHistoryHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.jsunpack import get_packed_data
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
import re
import json
import time
import os

try:
    from urlparse import urlparse, parse_qs, urljoin  # Python2
except ImportError:
    from urllib.parse import urlparse, parse_qs, urljoin  # Python3
###################################################
Y = E2ColoR("yellow")
W = E2ColoR("white")
G = E2ColoR("green")
R = E2ColoR("red")


###################################################
def gettytul():
    return "https://hd1.brstej.com"


class Brstej(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"cookie": "brstej.cookie", "use_cookie": True, "load_cookie": True, "save_cookie": True})
        self.MAIN_URL = "https://hd1.brstej.com"
        self.DEFAULT_ICON_URL = "https://hd1.brstej.com/22.png"
        self.HEADER = self.cm.getDefaultHeader()
        self.HEADER.update({"X-Requested-With": "XMLHttpRequest"})
        self.AJAX_HEADER = self.HEADER.copy()
        self.history = CSearchHistoryHelper("brstej")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if any(ord(c) > 127 for c in baseUrl):
            baseUrl = urllib_quote_plus(baseUrl, safe="://")
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def getFullIconUrl(self, url):
        if url.startswith("//"):
            url = "https:" + url
        return CBaseHostClass.getFullIconUrl(self, url)

    def listMainMenu(self, cItem):
        printDBG("Brstej.listMainMenu")
        self.MAIN_CAT_TAB = [
            {"category": "movies_folder", "title": "الافلام"},
            {"category": "series_folder", "title": "مسلسلات برستيج"},
            {"category": "series_packs_folder", "title": "مسلسلات كاملة"},
            {"category": "list_items", "title": "برامج تلفزيونية", "url": self.getFullUrl("/category.php?cat=tv4-2024")},
            {"category": "list_items", "title": "أخر الاضافات", "url": self.getFullUrl("/newvideo.php")},
            {"category": "search", "title": _("Search"), "search_item": True},
            {"category": "search_history", "title": _("Search history")},
            {"category": "delete_history", "title": _("Delete search history")},
        ]
        self.MOVIES_CAT_TAB = [
            {"category": "list_items", "title": "افلام عربية", "url": self.getFullUrl("/category.php?cat=aflam02-2024")},
            {"category": "list_items", "title": "افلام اجنبية", "url": self.getFullUrl("/category.php?cat=aflamajnby3-2024")},
            {"category": "list_items", "title": "افلام تركية", "url": self.getFullUrl("/category.php?cat=turkish3-movies2024")},
            {"category": "list_items", "title": "افلام هندية", "url": self.getFullUrl("/category.php?cat=hindi1-moviess")},
            {"category": "list_items", "title": "افلام انمي", "url": self.getFullUrl("/category.php?cat=anime1")},
        ]
        self.SERIES_CAT_TAB = [
            {"category": "list_items", "title": "مسلسلات كاملة", "url": self.getFullUrl("/moslslat.php")},
            {"category": "list_items", "title": "مسلسلات مصرية 2026", "url": self.getFullUrl("/category.php?cat=eg8-2025")},
            {"category": "list_items", "title": "مسلسلات شامية 2026", "url": self.getFullUrl("/category.php?cat=syy5-2025")},
            {"category": "list_items", "title": "مسلسلات عربية 2026", "url": self.getFullUrl("/category.php?cat=arab8-2025")},
            {"category": "list_items", "title": "مسلسلات خليجية 2026", "url": self.getFullUrl("/category.php?cat=5a7-2024")},
            {"category": "list_items", "title": "مسلسلات تركية 2026", "url": self.getFullUrl("/category.php?cat=ty9-2025")},
            {"category": "list_items", "title": "مسلسلات رمضان 2026", "url": self.getFullUrl("/category.php?cat=ramdan2026")},
            {"category": "list_items", "title": "مسلسلات رمضان 2025", "url": self.getFullUrl("/category.php?cat=ramadan2-2025")},
            {"category": "list_items", "title": "مسلسلات رمضان 2024", "url": self.getFullUrl("/category.php?cat=ramdan1-2024")},
            {"category": "list_items", "title": "مسلسلات رمضان 2023", "url": self.getFullUrl("/category.php?cat=ramda1-2023")},
            {"category": "list_items", "title": "مسلسلات رمضان 2022", "url": self.getFullUrl("/category.php?cat=rm42-2022")},
            {"category": "list_items", "title": "مسلسلات 2021", "url": self.getFullUrl("/category.php?cat=rmdan31-2021")},
            {"category": "list_items", "title": "مسلسلات اجنبية", "url": self.getFullUrl("/category.php?cat=english1-2025")},
            {"category": "list_items", "title": "مسلسلات هندية", "url": self.getFullUrl("/category.php?cat=2ind2-2025")},
            {"category": "list_items", "title": "مسلسلات اسيوية", "url": self.getFullUrl("/category.php?cat=asia")},
            {"category": "list_items", "title": "مسلسلات انمي", "url": self.getFullUrl("/category.php?cat=anmei")},
            {"category": "list_items", "title": "حلقات التجهيز", "url": self.getFullUrl("/category.php?cat=wait")},
        ]
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMoviesFolder(self, cItem):
        printDBG("Brstej.listMoviesFolder")
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesFolder(self, cItem):
        printDBG("Brstej.listSeriesFolder")
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listSeriesPacks(self, cItem):
        printDBG("Brstej.listSeriesPacks")
        url = self.getFullUrl("/category818.php")
        sts, data = self.getPage(url)
        if not sts:
            return
        images_map = {}
        img_blocks = re.findall(r'(<div class="pm-thumb-fix pm-thumb-234">.*?<img[^>]+>.*?</div>)', data, re.S)
        for ib in img_blocks:
            title = self.cm.ph.getSearchGroups(ib, r'alt="([^"]+)"')[0].strip()
            icon = self.cm.ph.getSearchGroups(ib, r'src="([^"]+)"')[0]
            if title and icon:
                images_map[title] = self.getFullIconUrl(icon)
        printDBG("IMAGES MAP: %s" % images_map)
        main_blocks = re.findall(r'(<li[^>]*class="sub_ca"[^>]*>.*?<b>.*?</b>.*?<ul[^>]*dropdown-menu[^>]*>.*?</ul>.*?</li>)', data, re.S)
        printDBG("MAIN BLOCKS COUNT = %d" % len(main_blocks))
        for block in main_blocks:
            main_title = self.cm.ph.getSearchGroups(block, r"<b>([^<]+)</b>")[0].strip()
            main_url = self.cm.ph.getSearchGroups(block, r'<a[^>]+href="([^"]+)"')[0]
            if not main_title or not main_url:
                continue
            if main_title in ["افلام", "مسلسلات برستيج"]:
                continue
            if main_title == "مسلسلات عربية 2026":
                main_title = "مسلسلات خليجية 2026"
            elif main_title == "برامج ومنوعات تلفزيونية":
                main_title = "مسلسلات شامية 2026"
            icon = images_map.get(main_title)
            params = {"good_for_fav": True, "category": "sub_series_packs", "title": main_title, "url": self.getFullUrl(main_url), "raw_block": block}
            if icon:
                params["icon"] = icon
            self.addDir(params)

    def listSubSeriesPacks(self, cItem):
        printDBG("Brstej.listSubSeriesPacks")
        block = cItem.get("raw_block", "")
        printDBG("BLOCK ====> %s" % block[:500])
        if not block:
            printDBG("NO raw_block")
            return
        sub_menu = self.cm.ph.getDataBeetwenMarkers(block, ("<ul", "dropdown-menu"), ("</ul>", ">"), True)[1]
        printDBG("SUBMENU ====> %s" % sub_menu[:500])
        if not sub_menu:
            printDBG("NO sub_menu")
            return
        links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', sub_menu, re.S)
        printDBG("SUB ITEMS COUNT = %d" % len(links))
        for url, title in links:
            title = self.cleanHtmlStr(title)
            if url and title:
                self.addDir({"good_for_fav": True, "category": "list_items", "title": title, "url": self.getFullUrl(url)})

    def listSeriesPacksFolder(self, cItem):
        printDBG("Brstej.listSeriesPacksFolder")
        self.listSeriesPacks(cItem)

    def listItems(self, cItem, nextCategory="explore_item"):
        printDBG("Brstej.listItems cItem[%s]" % (cItem))
        page = cItem.get("page", 1)
        url = cItem.get("url", "")
        is_movies_section = cItem.get("is_movies_section")
        if is_movies_section is None:
            is_movies_section = False
            parent_title = cItem.get("title", "")
            parent_url = cItem.get("url", "")
            if "فيلم" in parent_title or "افلام" in parent_title:
                is_movies_section = True
            if "/movie" in parent_url or "film" in parent_url:
                is_movies_section = True
            if "moslslat.php" in parent_url:
                is_movies_section = False
        base_url = url
        if page > 1:
            if "newvideo.php" in base_url:
                url = self.getFullUrl("/newvideos.php")
                url += "?page=%d" % page
            elif "category.php" in base_url:
                url = base_url.replace("category.php", "category818.php")
                if "?" in url:
                    url += "&page=%d" % page
                else:
                    url += "?page=%d" % page
            else:
                if "?" in base_url:
                    url = base_url + "&page=%d" % page
                else:
                    url = base_url + "?page=%d" % page
        sts, data = self.getPage(url)
        if not sts:
            return
        if "لا توجد اى ملفات" in data:
            msg = "عذراً- لا توجد اى ملفات بهذا التصنيف حالياً"
            params = {"good_for_fav": False, "title": Y + msg + W, "type": "marker"}
            self.addMarker(params)
            return
        if "moslslat.php" in url:
            items = re.findall(r'(<li[^>]*class="col-xs-6[^"]*"[^>]*>.*?</li>)', data, re.S)
            for item in items:
                url_match = re.search(r"""href=["']([^"']+view-serie\.php\?id=\d+)["']""", item)
                title_match = re.search(r"""title=["']([^"']+)["']""", item)
                img_match = re.search(r"""<img[^>]+src=["']([^"']+?)["']""", item)
                if not url_match or not title_match:
                    continue
                item_url = self.getFullUrl(url_match.group(1).strip())
                title = self.cleanTitle(title_match.group(1))
                icon = img_match.group(1).strip() if img_match else ""
                if title and item_url:
                    params = {"good_for_fav": True, "category": "explore_item", "title": title, "url": item_url}
                    if icon:
                        params["icon"] = self.getFullIconUrl(icon)
                    self.addDir(params)
            pagination = self.cm.ph.getDataBeetwenMarkers(data, ("<div", 'class="col-md-12 text-center"'), ("</div", ">"), True)[1]
            if pagination:
                pages = []
                for link in self.cm.ph.getAllItemsBeetwenMarkers(pagination, ("<a", "href="), ("</a", ">")):
                    page_num = self.cm.ph.getSearchGroups(link, "page=([0-9]+)")[0]
                    if page_num:
                        pages.append(int(page_num))
                if pages and max(pages) > page:
                    pages_left = max(pages) - page
                    self.addDir({"good_for_fav": False, "title": Y + _("Next Page") + " ▶▶▶" + W, "desc": Y + _("There are %d more pages in this section") % pages_left + W, "page": page + 1, "url": cItem.get("url", ""), "category": cItem.get("category", ""), "is_movies_section": False})
            return
        grid = self.cm.ph.getDataBeetwenMarkers(data, ("<ul", 'id="pm-grid"'), ("</ul>", ">"), False)[1]
        if not grid:
            grid = self.cm.ph.getDataBeetwenMarkers(data, ("<ul", 'class="row pm-ul-browse-videos'), ("</ul>", ">"), False)[1]
        if not grid:
            printDBG("Brstej.listItems: لم يتم العثور على قائمة العناصر (pm-grid)")
            return
        tmp = re.findall(r'<li[^>]*class="col-xs-6[^"]*"[^>]*>.*?</li>', grid, re.S)
        seen_titles = set()
        for item in tmp:
            icon = self.cm.ph.getSearchGroups(item, r"""data-echo=['"]([^"^']+?)['"]""")[0].strip()
            if not icon:
                icon = self.cm.ph.getSearchGroups(item, r"""src=['"]([^"^']+?)['"]""")[0].strip()
            if icon.startswith("data:image"):
                icon = ""
            title = self.cm.ph.getDataBeetwenNodes(item, ("<h3", ">"), ("</h3", ">"), False)[1]
            title = self.cleanTitle(title)
            title = re.sub(r"\s*(الحلقة|حلقة|ep|episode).*$", "", title, flags=re.I).strip()
            if title in seen_titles:
                continue
            seen_titles.add(title)
            thumb_block = self.cm.ph.getDataBeetwenMarkers(item, ("<div", 'class="pm-video-thumb"'), ("</div", ">"), False)[1]
            url = self.cm.ph.getSearchGroups(thumb_block, r"""href=["']([^"']*watch\.php\?vid=[^"']+)["']""", 1, True)[0].strip()
            if not url:
                url = self.cm.ph.getSearchGroups(item, r"""href=["']([^"']+watch\.php[^\s"']+)["']""", 1, True)[0].strip()
            if not url or not title or url == "#":
                continue
            duration = self.cm.ph.getSearchGroups(item, r"""<span[^>]*class=["']pm-label-duration["'][^>]*>([^<]+)""")[0].strip()
            quality = ""
            ribon_match = re.search(r'<div[^>]*class=["\']ribon["\'][^>]*>.*?<span[^>]*class=["\']hot["\'][^>]*>.*?<span[^>]*class=["\']after["\'][^>]*>.*?</span>\s*([^<>\s].*?)\s*<span[^>]*class=["\']before["\']', item, re.S)
            if ribon_match:
                quality = ribon_match.group(1).strip()
            desc_parts = []
            if quality:
                desc_parts.append(Y + "Quality: %s" % quality + W)
            if duration:
                desc_parts.append(Y + "Duration: %s" % duration + W)
            desc = " | ".join(desc_parts) if desc_parts else ""
            params = {"good_for_fav": True, "category": nextCategory, "title": title, "url": self.getFullUrl(url), "desc": desc}
            if icon and not icon.startswith("data:image"):
                params["icon"] = self.getFullIconUrl(icon)
            if "فيلم" in title:
                params["type"] = "FILM"
                self.addVideo(params)
            else:
                self.addDir(params)
        tmp = self.cm.ph.getDataBeetwenMarkers(data, ("<div", 'class="col-md-12 text-center"'), ("</div", ">"), True)[1]
        if tmp:
            pagination_links = self.cm.ph.getAllItemsBeetwenMarkers(tmp, ("<a", "href="), ("</a", ">"))
            if pagination_links:
                pages = []
                for link in pagination_links:
                    page_num = self.cm.ph.getSearchGroups(link, "page=([0-9]+)")[0]
                    if page_num:
                        pages.append(int(page_num))
                if pages and max(pages) > page:
                    pages_left = max(pages) - page
                    next_title = Y + _("Next Page") + " ▶▶▶" + W
                    next_desc = Y + _("There are %d more pages in this section") % pages_left + W
                    params = dict(cItem)
                    params.update({"good_for_fav": True, "title": next_title, "desc": next_desc, "page": page + 1, "url": cItem.get("url", ""), "is_movies_section": is_movies_section})
                    self.addDir(params)

    def exploreItems(self, cItem):
        printDBG("Brstej.exploreItems cItem[%s]" % (cItem))
        url = cItem["url"]
        if "view-serie.php" in url:
            url = url.replace("view-serie.php", "series1.php")
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = ""
        desc_match = re.search(r'<div[^>]+class=["\']pm-video-description["\'][^>]*>.*?<div[^>]+class=["\']txtv show-more-height["\'][^>]*>(.*?)</div>', data, re.S)
        if desc_match:
            desc_html = desc_match.group(1)
            desc = self.cleanHtmlStr(desc_html).replace("\n", " ").strip()
        seasons_box = self.cm.ph.getDataBeetwenMarkers(data, ("<div", 'class="SeasonsBox"'), ("</div", ">"), False)[1]
        if seasons_box:
            season_items = re.findall(r'<li[^>]*data-serie=["\']([^"\']+?)["\'][^>]*>([^<]+)</li>', seasons_box, re.S)
            if season_items:
                for season_id, season_title in season_items:
                    season_title = self.cleanHtmlStr(season_title)
                    if season_title:
                        params = dict(cItem)
                        params.update({"good_for_fav": True, "category": "list_season_episodes", "title": season_title, "season_id": season_id, "url": url, "desc": desc})
                        self.addDir(params)
                return
        grid = self.cm.ph.getDataBeetwenMarkers(data, ("<ul", 'id="pm-grid"'), ("</ul>", ">"), False)[1]
        if not grid:
            grid = self.cm.ph.getDataBeetwenMarkers(data, ("<ul", 'class="row pm-ul-browse-videos'), ("</ul>", ">"), False)[1]
        if not grid:
            return
        items = re.findall(r'<li[^>]*class="col-xs-6[^"]*"[^>]*>.*?</li>', grid, re.S)
        for item in items:
            url_match = re.search(r"""href=["']([^"']+)["']""", item)
            title_match = re.search(r"""title=["']([^"']+)["']""", item)
            img_match = re.search(r"""src=["']([^"']+?)["']""", item)
            if not url_match or not title_match:
                continue
            item_url = self.getFullUrl(url_match.group(1).strip())
            title = self.cleanTitle(title_match.group(1))
            icon = img_match.group(1).strip() if img_match else ""
            if not item_url or not title or item_url == "#" or "javascript:" in item_url:
                continue
            params = {"good_for_fav": True, "title": title, "url": item_url, "desc": desc}
            if icon:
                params["icon"] = self.getFullIconUrl(icon)
            if "الحلقة" in title:
                params["type"] = "Episode"
                self.addVideo(params)
            elif "فيلم" in title:
                params["type"] = "FILM"
                self.addVideo(params)
            else:
                params["category"] = "explore_item"
                params["type"] = "category"
                self.addDir(params)

    def listSeasonEpisodes(self, cItem):
        """عرض حلقات موسم معين"""
        printDBG("Brstej.listSeasonEpisodes cItem[%s]" % (cItem))
        season_id = cItem.get("season_id", "")
        url = cItem["url"]
        serie_icon = cItem.get("icon")
        sts, data = self.getPage(url)
        if not sts:
            return
        seasons_blocks = re.findall(r'<div[^>]+class="SeasonsEpisodes"[^>]+data-serie="(\d+)"[^>]*>(.*?)</div>', data, re.S)
        if not seasons_blocks:
            printDBG("No SeasonsEpisodes blocks found")
            return
        episodes_section = ""
        for s_id, s_html in seasons_blocks:
            if s_id == season_id:
                episodes_section = s_html
                break
        if not episodes_section:
            printDBG("Season %s not found" % season_id)
            return
        episodes = re.findall(r'<a[^>]+href=["\']([^"\']+?)["\'][^>]*title=["\']([^"\']+?)["\']', episodes_section, re.S)
        if not episodes:
            return
        episodes.reverse()
        for episode_url, episode_title in episodes:
            episode_url = self.getFullUrl(episode_url.strip())
            episode_title = self.cleanHtmlStr(episode_title)
            if episode_url and episode_title:
                params = {"good_for_fav": True, "title": episode_title, "url": episode_url, "type": "Episode"}
                if serie_icon:
                    params["icon"] = serie_icon
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Brstej.listSearchResult |%s|" % searchPattern)
        url = self.getFullUrl("/ajax-search.php")
        custom_headers = {
            "Referer": "https://hd1.brstej.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "Accept": "text/html, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en,ar;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://hd1.brstej.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        post_data = {"queryString": searchPattern}
        addParams = dict(self.defaultParams)
        if "header" in addParams:
            addParams["header"].update(custom_headers)
        else:
            addParams["header"] = custom_headers
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": custom_headers["User-Agent"]}
        sts, data = self.getPage(url, addParams=addParams, post_data=post_data)
        if not sts or not data:
            printDBG("Brstej.listSearchResult - No data received")
            return
        items = re.findall(r'<li[^>]*data-video-id=["\']([^"\']+)["\'][^>]*>.*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', data, re.S | re.I)
        if not items:
            printDBG("Brstej.listSearchResult - No items found")
            printDBG("Response: %s..." % data[:500])
            return
        added = set()
        for vid, item_url, title in items:
            title = self.cleanTitle(title.strip())
            item_url = self.getFullUrl(item_url.strip())
            if not title or not item_url or item_url in added:
                continue
            added.add(item_url)
            icon = ""
            desc = ""
            sts_vid, vid_data = self.getPage(item_url)
            if sts_vid and vid_data:
                og_image = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', vid_data, re.I)
                if og_image:
                    icon = self.getFullIconUrl(og_image.group(1).strip())
                else:
                    thumb_match = re.search(r'<img[^>]+src=[\'"]([^\'"]*thumbs/[^\'"]+)[\'"]', vid_data, re.I)
                    if thumb_match:
                        icon = self.getFullIconUrl(thumb_match.group(1).strip())
                duration = ""
                dur_match = re.search(r'<span[^>]*class=["\']pm-label-duration["\'][^>]*>([^<]+)', vid_data, re.I)
                if dur_match:
                    duration = dur_match.group(1).strip()
                quality = ""
                ribon_match = re.search(r'<div[^>]*class=["\']ribon["\'][^>]*>.*?<span[^>]*class=["\']hot["\'][^>]*>.*?<span[^>]*class=["\']after["\'][^>]*>([^<>]+?)\s*<span[^>]*class=["\']before["\']', vid_data, re.S | re.I)
                if ribon_match:
                    quality = ribon_match.group(1).strip()
                desc_parts = []
                if quality:
                    desc_parts.append(Y + "Quality: %s" % quality + W)
                if duration:
                    desc_parts.append(Y + "Duration: %s" % duration + W)
                desc = " | ".join(desc_parts)
                title_lower = title.lower()
                url_lower = item_url.lower()
                if re.search(r"\bفيلم\b|movie\b|film\b", title_lower, re.I) and not re.search(r"مسلسل|حلقة", title_lower, re.I):
                    is_series = False
                elif re.search(r"مسلسل|حلقة|season|episode|part\s*\d+", title_lower, re.I):
                    is_series = True
                elif re.search(r"series|season|episode", url_lower, re.I):
                    is_series = True
                else:
                    seasons_block = re.search(r'<div[^>]*id=["\']?seasons[^"\'>]*["\']?[^>]*>.*?</div>', vid_data, re.S | re.I)
                    if not seasons_block:
                        seasons_block = re.search(r'<div[^>]*class=["\'][^"\']*SeasonsEpisodes[^"\']*["\'][^>]*>(?:(?!<div[^>]*class=["\']similar|recommended|also|قد-يعجبك).)*?</div>', vid_data, re.S | re.I)
                    is_series = bool(seasons_block)
            else:
                title_lower = title.lower()
                if re.search(r"مسلسل|حلقة|season|episode|part\s*\d+", title_lower, re.I):
                    is_series = True
                else:
                    is_series = False
            params = {
                "good_for_fav": True,
                "title": title,
                "url": item_url,
                "icon": icon,
                "desc": desc,
            }
            if is_series:
                params.update({"category": "explore_item", "type": "category"})
                self.addDir(params)
            else:
                params.update({"type": "video"})
                self.addVideo(params)

    def getLinksForVideo(self, cItem):
        printDBG("Brstej.getLinksForVideo [%s]" % (cItem))
        linksTab = []
        url = cItem.get("url", "").strip()
        if "watch.php" in url:
            url = url.replace("watch.php", "play.php")
        printDBG("Final play URL: %s" % url)
        sts, data = self.getPage(url)
        if not sts:
            printDBG("Failed to fetch page")
            return []
        servers = re.findall(r"(<button[^>]+watchButton[^>]*>.*?</button>)", data, re.S)
        if servers:
            printDBG("Found %d server buttons" % len(servers))
            for i, server in enumerate(servers):
                server_name = self.cm.ph.cleanHtmlStr(server)
                if not server_name or "fa-play" in server_name:
                    server_name = "سيرفر %d" % (i + 1)
                embed_url = self.cm.ph.getSearchGroups(server, r"""data-embed-url=['"]([^"^']+?)['"]""")[0].strip()
                if embed_url:
                    try:
                        host = re.search(r"https?://([^/]+)/?", embed_url).group(1).lower()
                        host = host.replace("www.", "")
                        parts = host.split(".")
                        if len(parts) >= 2:
                            server_tag = parts[-2]
                        else:
                            server_tag = host
                    except:
                        server_tag = ""
                    if server_tag:
                        final_name = "%s [ %s ]" % (server_name, server_tag)
                    else:
                        final_name = server_name
                    printDBG("Add server: %s - %s" % (final_name, embed_url))
                    linksTab.append({"name": final_name, "url": embed_url, "need_resolve": 1})
                else:
                    printDBG("No embed URL found for server: %s" % server_name)
            printDBG("Returning %d servers from WatchServers" % len(linksTab))
        if not linksTab:
            printDBG("No server buttons found. Searching for iframe...")
            iframe_url = self.cm.ph.getSearchGroups(data, r"""<iframe[^>]+src=['"]([^"^']+?)['"]""")[0].strip()
            if iframe_url and "embed" in iframe_url:
                try:
                    host = re.search(r"https?://([^/]+)/?", iframe_url).group(1).lower()
                    host = host.replace("www.", "")
                    parts = host.split(".")
                    if len(parts) >= 2:
                        server_tag = parts[-2]
                    else:
                        server_tag = host
                except:
                    server_tag = ""
                if server_tag:
                    name = "السيرفر الافتراضي [ %s ]" % server_tag
                else:
                    name = "السيرفر الافتراضي"
                printDBG("Found iframe URL: %s" % iframe_url)
                linksTab.append({"name": name, "url": iframe_url, "need_resolve": 1})
            else:
                printDBG("No valid iframe found")
        if not linksTab:
            printDBG("No video links found at all")
            linksTab.append({"name": "الفيديو غير متوفر حاليًا", "url": "", "need_resolve": 0})
        printDBG("Final linksTab: %s" % linksTab)
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("Brstej.getVideoLinks -> %s" % videoUrl)
        if "hdup20.com" in videoUrl or "hdup.com" in videoUrl:
            return self._getHDUPLinks(videoUrl)
        elif "film77.xyz" in videoUrl or "vood78.xyz" in videoUrl:
            return self._getFilm77Links(videoUrl)
        elif "hd-vk.com" in videoUrl:
            return self._getHDVKLinks(videoUrl)
        elif "vk.com" in videoUrl:
            return self._getVKLinks(videoUrl)
        return self.up.getVideoLinkExt(videoUrl)

    def _getHDUPLinks(self, embed_url):
        def manual_unpack(p, a, c, k, e=None, d=None):
            def baseN(num, b):
                digits = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                res = ""
                while num > 0:
                    res = digits[num % b] + res
                    num //= b
                return res or "0"

            for i in range(len(k) - 1, -1, -1):
                if k[i]:
                    p = re.sub(r"\b%s\b" % baseN(i, a), k[i], p)
            return p

        def localGetDomain(url):
            parsed_uri = urlparse(url)
            return "{uri.scheme}://{uri.netloc}/".format(uri=parsed_uri)

        urlTab = []
        try:
            printDBG("HDUP extractor start -> %s" % embed_url)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36", "Referer": "https://hd1.brstej.com/"}
            params = dict(self.defaultParams)
            params.update({"header": headers, "use_cookie": True, "load_cookie": True, "save_cookie": True})
            sts, html = self.getPage(embed_url, params)
            if not sts:
                return []
            if "<form" in html:
                data = {}
                action = re.search(r'action\s*=\s*[\'"]([^\'"]+)', html)
                post_url = action.group(1) if action else embed_url
                if post_url.startswith("/"):
                    post_url = localGetDomain(embed_url)[:-1] + post_url
                fields = re.findall(r'type=["\']?(?:hidden|submit)[\'"]?[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']', html)
                for name, value in fields:
                    data[name] = value
                if data.get("file_code") == "":
                    mediaid = embed_url.rstrip(".html").split("/")[-1].split("-")[-1]
                    data["file_code"] = mediaid
                printDBG("HDUP: Waiting 6 seconds for bypass...")
                time.sleep(6)
                sts, html = self.getPage(post_url, params, post_data=data)
                if not sts:
                    return []
            packed_match = re.search(r"eval\(function\(p,a,c,k,e,d\).+?\}\('(.+?)',(\d+),(\d+),'(.+?)'\.split\('\|'\)", html, re.S)
            if packed_match:
                p, a, c, k = packed_match.groups()
                html = manual_unpack(p, int(a), int(c), k.split("|"))
            links = re.findall(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html)
            for url in links:
                url = url.replace("\\/", "/")
                meta = {"Referer": embed_url, "User-Agent": headers["User-Agent"]}
                if ".m3u8" in url:
                    try:
                        urlTab.extend(getDirectM3U8Playlist(strwithmeta(url, meta)))
                    except Exception:
                        urlTab.append({"name": "HDUP m3u8", "url": strwithmeta(url, meta)})
                else:
                    urlTab.append({"name": "HDUP MP4", "url": strwithmeta(url, meta)})
        except Exception as e:
            printDBG("HDUP error: %s" % str(e))
        return urlTab

    def _resolveXShared(self, embed_url):
        def manual_unpack(p, a, c, k, e=None, d=None):
            def baseN(num, b):
                digits = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                res = ""
                while num > 0:
                    res = digits[num % b] + res
                    num //= b
                return res or "0"

            for i in range(len(k) - 1, -1, -1):
                if k[i]:
                    p = re.sub(r"\b%s\b" % baseN(i, a), k[i], p)
            return p

        def localGetDomain(url):
            parsed_uri = urlparse(url)
            return "{uri.scheme}://{uri.netloc}/".format(uri=parsed_uri)

        urlTab = []
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36", "Referer": "https://hd1.brstej.com/"}
            params = dict(self.defaultParams)
            params.update({"header": headers, "use_cookie": True, "load_cookie": True, "save_cookie": True})
            sts, html = self.getPage(embed_url, params)
            if not sts:
                return []
            if "<form" in html:
                printDBG("XShared: Form detected, processing...")
                data = {}
                action = re.search(r'action=["\']([^"\']+)["\']', html)
                post_url = action.group(1) if action else embed_url
                if post_url.startswith("/"):
                    post_url = localGetDomain(embed_url)[:-1] + post_url
                fields = re.findall(r'type=["\']?(?:hidden|submit)[\'"]?[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']', html)
                for name, value in fields:
                    data[name] = value
                if data.get("file_code") == "":
                    mediaid = embed_url.rstrip(".html").split("/")[-1].split("-")[-1]
                    data["file_code"] = mediaid
                printDBG("XShared: Waiting 6 seconds...")
                time.sleep(6)
                sts, html = self.getPage(post_url, params, post_data=data)
                if not sts:
                    return []
            if "function(p,a,c,k,e,d)" in html:
                packed = re.search(r"eval\(function\(p,a,c,k,e,d\).+?\}\('(.+?)',(\d+),(\d+),'(.+?)'\.split\('\|'\)", html, re.S)
                if packed:
                    p, a, c, k = packed.groups()
                    html = manual_unpack(p, int(a), int(c), k.split("|"))
            links = re.findall(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html)
            for url in links:
                url = url.replace("\\/", "/")
                meta = {"User-Agent": headers["User-Agent"], "Referer": embed_url}
                if ".m3u8" in url:
                    try:
                        urlTab.extend(getDirectM3U8Playlist(strwithmeta(url, meta)))
                    except Exception:
                        urlTab.append({"name": "Direct m3u8", "url": strwithmeta(url, meta)})
                else:
                    urlTab.append({"name": "Direct MP4", "url": strwithmeta(url, meta)})
        except Exception as e:
            printDBG("XShared Error: %s" % str(e))
        return urlTab

    def _getVKLinks(self, url):
        printDBG("Trying VK extractor v4 (flexible parser)")
        links = []
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://vk.com/"}
            params = dict(self.defaultParams)
            params["header"] = headers
            sts, data = self.getPage(url, params)
            if not sts or not data:
                return links
            try:
                if isinstance(data, bytes):
                    data = data.decode("cp1251", "ignore")
            except Exception:
                pass
            files_block = re.search(r'"files"\s*:\s*\{(.*?)\}', data, re.S)
            if not files_block:
                printDBG("VK: files block not found (dump first 3000 chars)")
                printDBG(data[:3000])
                return links
            files_data = files_block.group(1)
            items = re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', files_data)
            for k, v in items:
                if not v.startswith("http"):
                    continue
                if k.lower() == "hls_fmp4":
                    continue
                video_url = v.replace("\\/", "/")
                if k.startswith("mp4_"):
                    name = "MP4 " + k.replace("mp4_", "")
                elif k.lower() == "hls":
                    name = "HLS (Adaptive)"
                elif "hls" in k.lower():
                    name = k.upper()
                else:
                    name = k.upper()
                links.append({"name": "VK " + name, "url": strwithmeta(video_url, {"Referer": "https://vk.com/", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}), "need_resolve": 0})
            printDBG("VK links found: %s" % links)
        except Exception as e:
            printExc("VK extractor error: %s" % e)
        return links

    def _getFilm77Links(self, embed_url):
        urlTab = []
        main_cookie = self.defaultParams.get("cookiefile", "/tmp/brstej.cookie")
        try:
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
            referer = "https://rty1.film77.xyz/"
            params = dict(self.defaultParams)
            params.update({"header": {"User-Agent": user_agent, "Referer": "https://hd1.brstej.com/"}, "cookiefile": main_cookie})
            sts, html = self.getPage(embed_url, params)
            if not sts:
                return []
            packed_match = re.search(r"eval\(function\(p,a,c,k,e,d\).+?\}\('(.+?)',(\d+),(\d+),'(.+?)'\.split\('\|'\)", html, re.S)
            if packed_match:
                p, a, c, k = packed_match.groups()

                def js_unpack(p, a, c, k):
                    def baseN(num, b):
                        digits = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                        res = ""
                        while num > 0:
                            res = digits[num % b] + res
                            num //= b
                        return res or "0"

                    for i in range(int(c) - 1, -1, -1):
                        if k[i]:
                            p = re.sub(r"\b%s\b" % baseN(i, int(a)), k[i], p)
                    return p

                decoded_js = js_unpack(p, a, c, k.split("|"))
            else:
                decoded_js = html
            links = re.findall(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', decoded_js)
            for url in links:
                url = url.replace("\\/", "/")
                video_meta = {"Referer": referer, "Origin": "https://rty1.film77.xyz", "User-Agent": user_agent, "iptv_proto": "m3u8", "iptv_m3u8_key_referer": referer, "allow_unverified_ssl": True}
                urlTab.append({"name": "Film77 (Server 2)", "url": strwithmeta(url, video_meta), "need_resolve": 0})
        except Exception as e:
            printExc("Film77 error: %s" % e)
        return urlTab

    def _getHDVKLinks(self, embed_url):
        printDBG("HD-VK extractor -> %s" % embed_url)
        urlTab = []
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://ss.hd-vk.com/"}
            params = dict(self.defaultParams)
            params["header"] = headers
            sts, html = self.getPage(embed_url, params)
            if not sts or not html:
                return urlTab

            def js_unpack(p, a, c, k):
                def baseN(num, base):
                    digits = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    res = ""
                    while num > 0:
                        res = digits[num % base] + res
                        num //= base
                    return res or "0"

                for i in range(c - 1, -1, -1):
                    if k[i]:
                        p = re.sub(r"\b%s\b" % baseN(i, a), k[i], p)
                return p

            decoded_js = html
            packed_match = re.search(r"eval\(function\(p,a,c,k,e,d\).+?\}\('(.+?)',(\d+),(\d+),'(.+?)'\.split\('\|'\)", html, re.S)
            if packed_match:
                p, a, c, k = packed_match.groups()
                decoded_js = js_unpack(p, int(a), int(c), k.split("|"))
            links = re.findall(r'[\'"](https?://[^\'"]+?\.m3u8[^\'"]*)[\'"]', decoded_js)
            for url in links:
                url = url.replace("\\/", "/").replace("\\", "")
                query = ""
                if "?" in url:
                    query = url[url.find("?"):]
                if "master.m3u8" in url:
                    sts, data = self.getPage(url, params)
                    if sts:
                        sub_links = re.findall(r"RESOLUTION=(\d+x\d+).*?\n(.*?\.m3u8)", data)
                        for res, sub_url in sub_links:
                            if not sub_url.startswith("http"):
                                sub_url = urljoin(url, sub_url)
                            if "?" not in sub_url:
                                sub_url += query
                            urlTab.append({"name": "HD-VK HLS %s" % res, "url": strwithmeta(sub_url, {"Referer": embed_url, "User-Agent": headers["User-Agent"]}), "need_resolve": 0})
                urlTab.append({"name": "HD-VK HLS (Auto)", "url": strwithmeta(url, {"Referer": embed_url, "User-Agent": headers["User-Agent"]}), "need_resolve": 0})
        except Exception as e:
            printDBG("HD-VK error: %s" % str(e))
        return urlTab

    def getArticleContent(self, cItem):
        """استخراج القصة من صفحة الفيديو"""
        printDBG("Brstej.getArticleContent [%s]" % cItem)
        retTab = []
        url = cItem.get("url", "").strip()
        if not url:
            return []
        if "watch.php" in url:
            url = url.replace("watch.php", "play.php")
        sts, data = self.getPage(url)
        if not sts:
            return []
        title = cItem.get("title", "")
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        old_desc = cItem.get("desc", "")
        story = ""
        desc_block = self.cm.ph.getDataBeetwenMarkers(data, ("<div", 'class="pm-video-description"'), ("</div", ">"), False)[1]
        if desc_block:
            h2_content = self.cm.ph.getDataBeetwenMarkers(desc_block, ("<h2", ">"), ("</h2", ">"), False)[1]
            if h2_content:
                story = self.cm.ph.cleanHtmlStr(h2_content)
            else:
                p_match = re.search(r"<p[^>]*>(.*?)</p>", desc_block, re.S)
                if p_match:
                    story = self.cm.ph.cleanHtmlStr(p_match.group(1))
        final_text = ""
        if story.strip():
            story_colored = "\\c0000FF00 القصة: \\n\\c00FFFFFF" + story.strip()
            if old_desc:
                clean_old_desc = old_desc.replace(Y, "\\c00FFFF00").replace(W, "\\c00FFFFFF")
                final_text = story_colored + "\\n\\c00FFFFFF-------------------\\n" + clean_old_desc
            else:
                final_text = story_colored
        else:
            final_text = old_desc if old_desc else "\\c00FF0000لا يوجد قصة متاحة حالياً."
        retTab.append({"title": title, "text": final_text, "images": [{"title": "", "url": icon}], "other_info": {}})
        return retTab

    def cleanTitle(self, title):
        title = self.cleanHtmlStr(title)
        remove_words = ["مشاهدة", "اونلاين HD", "اون لاين HD", "اونلاين", "اون لاين"]
        for w in remove_words:
            title = title.replace(w, "")
        title = re.sub(r"\s+", " ", title)
        return title.strip()

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG(">>> Brstej.handleService BEGIN <<<")
        printDBG(">>> self.currItem = %s" % str(self.currItem))
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "":
            self.listMainMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "explore_item":
            self.exploreItems(self.currItem)
        elif category == "list_season_episodes":
            self.listSeasonEpisodes(self.currItem)
        elif category == "movies_folder":
            self.listMoviesFolder(self.currItem)
        elif category == "series_folder":
            self.listSeriesFolder(self.currItem)
        elif category == "series_packs_folder":
            self.listSeriesPacksFolder(self.currItem)
        elif category == "series_packs":
            self.listSeriesPacks(self.currItem)
        elif category == "sub_series_packs":
            self.listSubSeriesPacks(self.currItem)
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
        CHostBase.__init__(self, Brstej(), True, [])

    def withArticleContent(self, cItem):
        if "video" == cItem.get("type", "") or "explore_item" == cItem.get("category", ""):
            return True
        return False
