# -*- coding: utf-8 -*-
# Original File from: 01/12/2025 - popking (odem2014)
# Last modified: 04/04/2026 - Mohamed Elsafty (angel_heart)
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
from Plugins.Extensions.IPTVPlayer.libs import ph

###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_quote
from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry

###################################################
# FOREIGN import
###################################################
import re

###################################################
# Constants
C = E2ColoR("cyan")
L = E2ColoR("lime")
O = E2ColoR("orange")
R = E2ColoR("red")
W = E2ColoR("white")
Y = E2ColoR("yellow")
###################################################


def gettytul():
    return "https://topcima.online"  # main url of host


class TopCinema(CBaseHostClass):
    def __init__(self):
        # init global variables for this class
        CBaseHostClass.__init__(self, {"history": "topcinema", "cookie": "topcinema.cookie"})  # names for history and cookie files in cache
        self.ph = ph
        # vars default values
        # various urls
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + "?s="
        # url for default icon
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/topcinema.png"
        # default header and http params
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.AJAX_HEADER = self.HEADER
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty", "Sec-Fetch-Site": "same-origin"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, base_url, add_params=None, post_data=None):
        if add_params is None:
            add_params = dict(self.defaultParams)
        base_url = self._fixUrl(base_url)
        add_params["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(base_url, add_params, post_data)

    def listMainMenu(self, cItem):
        # items of main menu
        printDBG("TopCinema.listMainMenu")
        # Define main categories statically like FilmPalast does
        self.MAIN_CAT_TAB = [
            {"category": "movies_folder", "title": "Movies"},
            {"category": "series_folder", "title": "Series"},
            {"category": "list_items", "title": "TV Shows", "url": self.getFullUrl("/category/%d8%a8%d8%b1%d8%a7%d9%85%d8%ac-%d8%aa%d9%84%d9%81%d8%b2%d9%8a%d9%88%d9%86%d9%8a%d8%a9/")},
            {"category": "list_items", "title": "Arabic plays", "url": self.getFullUrl("/category/%d9%85%d8%b3%d8%b1%d8%ad%d9%8a%d8%a7%d8%aa-%d8%b9%d8%b1%d8%a8%d9%8a%d9%87/")},
            {"category": "list_items", "title": "WWE Shows", "url": self.getFullUrl("/category/%d9%85%d8%b5%d8%a7%d8%b1%d8%b9%d9%87/")},
            {"category": "list_items", "title": "Newly added", "url": self.getFullUrl("/last/")},
        ] + self.searchItems()
        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {"category": "list_items", "title": "Arabic", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%b9%d8%b1%d8%a8%d9%8a/")},
            {"category": "list_items", "title": "English", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/")},
            {"category": "list_items", "title": "English Dubbed", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a%d8%a9-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/")},
            {"category": "list_items", "title": "Turkish", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/")},
            {"category": "list_items", "title": "Asian", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/")},
            {"category": "list_items", "title": "Indian", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%87%d9%86%d8%af%d9%89/")},
            {"category": "list_items", "title": "Netfilx", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-netfilx/")},
            {"category": "list_items", "title": "Anime", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%85%d9%8a/")},
            {"category": "list_items", "title": "Cartoon", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%83%d8%b1%d8%aa%d9%88%d9%86/")},
            {"category": "list_items", "title": "Dubbed", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/")},
            {"category": "list_items", "title": "Classic", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%83%d9%84%d8%a7%d8%b3%d9%8a%d9%83%d9%8a%d9%87/")},
            {"category": "list_items", "title": "Documentry", "url": self.getFullUrl("/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%88%d8%ab%d8%a7%d8%a6%d9%82%d9%8a%d8%a9/")},
            {"category": "list_items", "title": "Top Rating IMDB", "url": self.getFullUrl("/imdb/")},
            {"category": "list_items", "title": "Movies Series", "url": self.getFullUrl("/assemblies/")},
        ]
        self.SERIES_CAT_TAB = [
            {"category": "series", "title": "Arabic", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b9%d8%b1%d8%a8%d9%8a/")},
            {"category": "series", "title": "English", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%ac%d9%86%d8%a8%d9%8a/")},
            {"category": "series", "title": "Turkish", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%aa%d8%b1%d9%83%d9%8a%d8%a9/")},
            {"category": "series", "title": "Turkish 2", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%aa%d8%b1%d9%83%d9%8a%d9%87/")},
            {"category": "series", "title": "Asian", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d8%b3%d9%8a%d9%88%d9%8a%d8%a9/")},
            {"category": "series", "title": "Indian", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%87%d9%86%d8%af%d9%8a%d8%a9/")},
            {"category": "series", "title": "Korian", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%83%d9%88%d8%b1%d9%8a%d9%87/")},
            {"category": "series", "title": "Latin", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%84%d8%a7%d8%aa%d9%8a%d9%86%d9%8a%d8%a9/")},
            {"category": "series", "title": "Netfilx", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-netfilx/")},
            {"category": "series", "title": "Ramadan 2026", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2026/")},
            {"category": "series", "title": "Anime", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%a7%d9%86%d9%85%d9%8a/")},
            {"category": "series", "title": "Cartoon", "url": self.getFullUrl("/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%83%d8%b1%d8%aa%d9%88%d9%86/")},
            {"category": "series", "title": "Top Rating IMDB", "url": self.getFullUrl("/top-rating-imdb-series/")},
            {"category": "series", "title": "Complated Series", "url": self.getFullUrl("/complated-series/")},
        ]
        # Display main categories
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMoviesFolder(self, cItem):
        printDBG("TopCinema.listMoviesFolder")
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesFolder(self, cItem):
        printDBG("TopCinema.listSeriesFolder")
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def _cleanTitle(self, title):
        if not title:
            return ""
        title = self.cleanHtmlStr(title)
        words_to_remove = ["مترجم اون لاين", "مشاهدة", "مسلسل", "فيلم", "برنامج", "عرض"]
        for word in words_to_remove:
            title = title.replace(word, "")
        return title.strip()

    def _fixUrl(self, url):
        if url:
            url = self.getFullUrl(url)
            if any(ord(c) > 127 for c in url):
                return urllib_quote(url.encode("utf-8"), safe=":/%?&=+@#,")
        return url

    def listItems(self, cItem):
        printDBG("TopCinema.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<main class="site-inner', "</main>", True)[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box', "</a>", True)
        for m in items:
            url = self.cm.ph.getSearchGroups(m, r"href=[\"']([^\"']+)[\"']")[0]
            if not url:
                continue
            url = self._fixUrl(url)
            raw_title = self.cm.ph.getSearchGroups(m, r"title=[\"']([^\"']+)[\"']")[0]
            title = self._cleanTitle(raw_title)
            poster = self.cm.ph.getSearchGroups(m, r"data-src=[\"']([^\"']+)[\"']")[0]
            if not poster:
                poster = self.cm.ph.getSearchGroups(m, r"src=[\"']([^\"']+)[\"']")[0]
            if not poster:
                poster = "https://topcima.online/wp-content/uploads/2025/10/block-1.png"
            poster = self._fixUrl(poster)
            category = self.cleanHtmlStr(self.cm.ph.getSearchGroups(m, r"<li class=\"category\">([^<]+)</li>")[0])
            ##############################################################
            # Extraction of Metadata for Description
            ##############################################################
            genre = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<li class="genre">', "</li>")[1])
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<li class="quality">', "</li>")[1])
            runtime = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<li class="meta-runtime">', "</li>")[1])
            year = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<li class="meta-year">', "</li>")[1])
            imdb = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<li class="imdbRating">', "</li>")[1])
            desc_list = []
            if genre:
                desc_list.append("{}Genre:{} {}".format(Y, W, genre))
            if quality:
                desc_list.append("{}Quality:{} {}".format(Y, W, quality))
            if year:
                desc_list.append("{}Year:{} {}".format(Y, W, year))
            if imdb:
                desc_list.append("{}Imdb Rating:{} {}".format(Y, W, imdb))
            if runtime:
                desc_list.append("{}Runtime:{} {}".format(Y, W, runtime))
            separator = " {}|{} ".format(C, W)
            final_desc = separator.join(desc_list)
            params = {
                "category": "movie_details",
                "title": title,
                "url": url,
                "icon": poster,
                "desc": final_desc,
                "good_for_fav": True,
            }
            self.addDir(params)
        # === PAGINATION ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', "</div>", True)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r"<a[^>]+class=\"[^\"]*next[^\"]*\"[^>]+href=\"([^\"]+)\"")[0]
        if not next_page:
            next_page = self.cm.ph.getSearchGroups(pagination, r"<a[^>]+href=\"([^\"]+)\"[^>]*>[^<]*?(?:Next|←|»|&laquo;|التالي)[^<]*?</a>")[0]
        if next_page:
            next_url = self.getFullUrl(next_page).replace("&amp;", "&").replace("&#038;", "&")
            next_p_num = self.cm.ph.getSearchGroups(next_url, r"[pP]age[=/](\d+)")[0]
            display_num = " [ " + next_p_num + " ]" if next_p_num else ""
            params = dict(cItem)
            params.update({"title": L + _("Next Page »»»") + W + display_num, "url": next_url, "category": "list_items"})
            self.addDir(params)

    def showMovieDetails(self, cItem):
        printDBG("TopCinema.showMovieDetails [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return
        sts, data = self.getPage(url)
        if not sts or not data:
            return
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="story clearfix">', "</div>", False)[1])
        meta_parts = []
        info_part = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="RightTaxContent">', "</ul>", False)[1]
        if info_part:
            info_items = re.findall(r"<li[^>]*>(.*?)</li>", info_part, re.S)
            for item in info_items:
                label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<span>", "</span>", False)[1]).replace(":", "").strip()
                values = self.cm.ph.getAllItemsBeetwenMarkers(item, "<a", "</a>")
                clean_values = [self.cleanHtmlStr(v) for v in values if self.cleanHtmlStr(v)]
                value = ", ".join(clean_values)
                if not label or not value:
                    continue
                key = ""
                if any(x in label for x in ["تصنيف", "قسم"]):
                    key = "{}Category:{}".format(Y, W)
                elif "نوع" in label:
                    key = "{}Genre:{}".format(Y, W)
                elif "جودة" in label:
                    key = "{}Quality:{}".format(Y, W)
                elif any(x in label for x in ["تاريخ", "السنة"]):
                    key = "{}Year:{}".format(Y, W)
                elif "لغة" in label:
                    key = "{}Language:{}".format(Y, W)
                elif any(x in label for x in ["الدولة", "البلد"]):
                    key = "{}Country:{}".format(Y, W)
                elif "مدة" in label:
                    key = "{}Runtime:{}".format(Y, W)
                elif "بطولة" in label:
                    key = "{}Stars:{}".format(Y, W)
                if key and value:
                    meta_parts.append("{} {}".format(key, value))
        separator = " {}|{} ".format(C, W)
        one_line_info = separator.join(meta_parts)
        if story:
            full_desc = "{}\n{}Story:{} {}".format(one_line_info, L, W, story)
        else:
            full_desc = one_line_info
        params = {"category": "explore_item", "title": "{}".format(cItem.get("title", "")), "url": url, "icon": cItem.get("icon", ""), "desc": full_desc, "good_for_fav": True, "type": "category"}
        self.addDir(params)

    def listSeriesItems(self, cItem):
        printDBG("TopCinema.listSeriesItems [%s]" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        ############################################################
        # Extract series block (All episodes)
        ############################################################
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="BlocksHolder', '<script type="speculationrules', True)[1]
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box', "</a>", True)
        if not data_items:
            # fallback if needed
            parts = tmp.split('<div class="Small--Box')
            data_items = ['<div class="Small--Box' + p for p in parts[1:]]
        for m in data_items:
            ############################################################
            # URL
            ############################################################
            url = self.cm.ph.getSearchGroups(m, r"href=[\"']([^\"']+)[\"']")[0]
            if not url:
                continue
            ############################################################
            # Title
            ############################################################
            raw_title = self.cm.ph.getSearchGroups(m, r"title=[\"']([^\"']+)[\"']")[0]
            title = self.cleanHtmlStr(raw_title)
            title = self._cleanTitle(raw_title)
            ############################################################
            # Episode number
            ############################################################
            episode = self.cm.ph.getSearchGroups(m, r"<span>الحلقة</span>\s*<em>(\d+)</em>")[0]
            ##############################################################
            # Extraction of Metadata for Description
            ##############################################################
            genre = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<li class="genre">', "</li>")[1])
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<li class="quality">', "</li>")[1])
            runtime = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<li class="meta-runtime">', "</li>")[1])
            year = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<li class="meta-year">', "</li>")[1])
            imdb = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(m, '<li class="imdbRating">', "</li>")[1])
            desc_list = []
            if genre:
                desc_list.append("{}Genre:{} {}".format(Y, W, genre))
            if quality:
                desc_list.append("{}Quality:{} {}".format(Y, W, quality))
            if year:
                desc_list.append("{}Year:{} {}".format(Y, W, year))
            if imdb:
                desc_list.append("{}Imdb Rating:{} {}".format(Y, W, imdb))
            if runtime:
                desc_list.append("{}Runtime:{} {}".format(Y, W, runtime))
            final_desc = " | ".join(desc_list)
            ############################################################
            # Icon (data-src preferred)
            ############################################################
            pureicon = self.cm.ph.getSearchGroups(m, r"data-src=[\"']([^\"']+)[\"']")[0]
            if not pureicon:
                pureicon = self.cm.ph.getSearchGroups(m, r"src=[\"']([^\"']+)[\"']")[0]
            # Fallback icon
            if not pureicon:
                pureicon = "https://topcima.online/wp-content/uploads/2025/10/block-1.png"
            icon = pureicon.strip()
            ############################################################
            # Category
            ############################################################
            category = self.cm.ph.getSearchGroups(m, r"<li class=\"category\">([^<]+)</li>")[0]
            ############################################################
            # Build params
            ############################################################
            params = {
                "category": "show_seasons",
                "title": title,
                "good_for_fav": True,
                "url": url,
                "icon": self._fixUrl(icon),
                "episode": episode,
                "desc": final_desc,
                "category_name": category,
            }
            printDBG(str(params))
            self.addDir(params)
        # === PAGINATION HANDLING ===
        pagination = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination">', "</div>", True)[1]
        next_page = self.cm.ph.getSearchGroups(pagination, r"<a[^>]+class=\"[^\"]*next[^\"]*\"[^>]+href=\"([^\"]+)\"")[0]
        if not next_page:
            next_page = self.cm.ph.getSearchGroups(pagination, r"<a[^>]+href=\"([^\"]+)\"[^>]*>[^<]*?(?:Next|←|»|&laquo;|التالي)[^<]*?</a>")[0]
        if next_page:
            next_url = self.getFullUrl(next_page).replace("&amp;", "&").replace("&#038;", "&")
            next_p_num = self.cm.ph.getSearchGroups(next_url, r"[pP]age[=/](\d+)")[0]
            display_num = " [ " + next_p_num + " ]" if next_p_num else ""
            params = dict(cItem)
            params.update({"title": L + _("Next Page »»»") + W + display_num, "url": next_url, "category": cItem.get("category", "list_items")})
            self.addDir(params)

    def exploreItems(self, cItem):
        printDBG("TopCinema.exploreItems [%s]" % cItem)
        url = cItem["url"]
        item_title = cItem.get("title", "")
        url = url.replace("//watch", "/watch")
        if "/watch" not in url:
            test_url = url.rstrip("/") + "/watch"
        else:
            test_url = url
        sts, data = self.getPage(test_url)
        if not sts:
            return
        if "data-watch" not in data and "series-movies" not in data:
            printDBG("Fallback → loading original URL")
            sts, data = self.getPage(url)
            if not sts:
                return
        ##########################################################
        # Check for Movie Collections / Assembly sets
        ##########################################################
        if "series-movies" in data:
            printDBG("Detected Series/Assembly page")
            series_block = self.cm.ph.getDataBeetwenMarkers(data, '<section class="series-movies"', "</section>")[1]
            items = self.cm.ph.getAllItemsBeetwenMarkers(series_block, '<div class="Small--Box"', "</a>")
            for item in items:
                url = self.cm.ph.getSearchGroups(item, r"""href=["']([^"']+)["']""")[0]
                title = self.cm.ph.getSearchGroups(item, r"""title=["']([^"']+)["']""")[0]
                icon = self.cm.ph.getSearchGroups(item, r"""data-src=["']([^"']+)["']""")[0]
                if not icon:
                    icon = self.cm.ph.getSearchGroups(item, r"""src=["']([^"']+)["']""")[0]
                if not url:
                    continue
                params = MergeDicts(cItem, {"title": self.cleanHtmlStr(title), "url": self.getFullUrl(url), "icon": self._fixUrl(icon), "type": "category", "category": "explore_item"})
                self.addDir(params)
            return
        ##########################################################
        # Extract Hosts (Format: Movie Title + Server Name)
        ##########################################################
        server_block = self.cm.ph.getDataBeetwenMarkers(data, '<ul id="watch"', "</ul>", False)[1]
        printDBG("server_block >>> %s" % server_block)
        items = self.cm.ph.getAllItemsBeetwenMarkers(server_block, "<li", "</li>")
        for item in items:
            video_url = self.cm.ph.getSearchGroups(item, r"data-watch=\"([^\"]+)\"")[0]
            if not video_url:
                continue
            server_name = self.cm.ph.getSearchGroups(item, r"<span[^>]*>([^<]+)</span>")[0]
            server_name = self.cleanHtmlStr(server_name) or "Server"
            final_title = "{} Server - {}{}{}".format(item_title, Y, server_name, W)
            printDBG("Server: %s -> %s" % (final_title, video_url))
            params = MergeDicts(cItem, {"title": final_title, "url": video_url, "type": "video", "category": "video", "need_resolve": 1})
            self.addVideo(params)

    def showSeasons(self, cItem):
        printDBG("TopCinema.showSeasons >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        ############################################################
        # Extract seasons block
        ############################################################
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<section class="allseasonss', "</section>", False)[1]
        if not tmp:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="Blocks--List', "</ul>", False)[1]
        printDBG("tmp.showSeasons >>> %s" % tmp)
        # Each season is one <div class="Small--Box"> ... </a>
        seasons = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<div class="Small--Box', "</a>", True)
        for s in seasons:
            ############################################################
            # URL
            ############################################################
            url = self.cm.ph.getSearchGroups(s, r"href=\"([^\"]+)\"")[0]
            if not url:
                continue
            ############################################################
            # Title from <h2>
            ############################################################
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(s, "<h2>", "</h2>", False)[1])
            if not title:
                title = self.cm.ph.getSearchGroups(s, r"title=\"([^\"]+)\"")[0]
            title = self._cleanTitle(title)
            ############################################################
            # Icon: Prefer data-src, fallback to src
            ############################################################
            icon = self.cm.ph.getSearchGroups(s, r"data-src=\"([^\"]+)\"")[0]
            if not icon:
                icon = self.cm.ph.getSearchGroups(s, r"src=\"([^\"]+)\"")[0]
            icon = self._fixUrl(icon)
            ############################################################
            # Add the season entry
            ############################################################
            params = dict(cItem)
            params.update({"title": title, "good_for_fav": True, "url": self.getFullUrl(url), "icon": icon, "category": "show_episodes"})
            printDBG("season.params >>> %s" % params)
            self.addDir(params)

    def showEpisodes(self, cItem):
        printDBG("TopCinema.showEpisodes >>> %s" % cItem)
        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return
        info_part = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="RightTaxContent">', "</ul>", False)[1]
        info_items = re.findall(r"<li[^>]*>(.*?)</li>", info_part, re.S)
        meta_data = []
        for item in info_items:
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<span>", "</span>", False)[1]).replace(":", "").strip()
            values = self.cm.ph.getAllItemsBeetwenMarkers(item, "<a", "</a>")
            clean_values = [self.cleanHtmlStr(v) for v in values if self.cleanHtmlStr(v)]
            value = ", ".join(clean_values)
            if not label or not value:
                continue
            key = ""
            if any(x in label for x in ["تصنيف", "قسم"]):
                key = "Category"
            elif "نوع" in label:
                key = "Genre"
            elif "جودة" in label:
                key = "Quality"
            elif any(x in label for x in ["تاريخ", "السنة"]):
                key = "Year"
            elif "لغة" in label:
                key = "Lang"
            elif any(x in label for x in ["الدولة", "البلد"]):
                key = "Country"
            if key:
                meta_data.append("{}{}:{} {}".format(Y, key, W, value))
        imdb = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="imdbRating">', "</div>", False)[1])
        if imdb:
            meta_data.append("{}IMDb:{} {}".format(Y, W, imdb))
        raw_story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="story clearfix">', "</div>", False)[1])
        separator = " {}|{} ".format(C, W)
        one_line_info = separator.join(meta_data)
        final_desc = "{}\n{}Story:{} {}".format(one_line_info, L, W, raw_story)
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<section class="allepcont', "</section>", True)[1]
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<a ", "</a>", True)
        data_items.reverse()
        for ep in data_items:
            pureurl = self.cm.ph.getSearchGroups(ep, r"href=\"([^\"]+)\"")[0]
            if not pureurl:
                continue
            raw_title = self.cm.ph.getDataBeetwenMarkers(ep, "<h2>", "</h2>", False)[1].strip()
            title = self._cleanTitle(raw_title)
            icon = self.cm.ph.getSearchGroups(ep, r"data-src=\"([^\"]+)\"")[0] or self.cm.ph.getSearchGroups(ep, r"src=\"([^\"]+)\"")[0]
            icon = self._fixUrl(icon)
            full_url = self._fixUrl(pureurl)
            params = {
                "category": "explore_item",
                "title": title,
                "desc": final_desc,
                "icon": icon,
                "url": full_url,
                "good_for_fav": True,
            }
            self.addDir(params)

    def listSearchResult(self, cItem, search_pattern, search_type):
        printDBG("TopCinema.listSearchResult cItem[%s], search_pattern[%s]" % (cItem, search_pattern))
        cItem = dict(cItem)
        if "url" not in cItem or not cItem["url"]:
            cItem["url"] = self.getFullUrl("?s=") + urllib_quote_plus(search_pattern)
        self.listItems(cItem)

    def getFavouriteData(self, cItem):
        printDBG("TopCinema.getFavouriteData")
        return json_dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG("TopCinema.getLinksForFavourite")
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG("TopCinema.setInitListFromFavouriteItem")
        try:
            cItem = json_loads(fav_data)
        except Exception:
            cItem = {}
            printExc()
        return cItem

    ###################################################
    # GET LINKS FOR VIDEO
    ###################################################

    def getLinksForVideo(self, cItem):
        printDBG("TopCinema.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return []
        return [{"name": "TopCinema - %s" % cItem.get("title", ""), "url": url, "need_resolve": 1}]

    def getVideoLinks(self, url):
        printDBG("TopCinema.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def getArticleContent(self, cItem):
        printDBG("TopCinema.getArticleContent [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return []
        sts, data = self.getPage(url)
        if not sts or not data:
            return []
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1 class="title">', "</h1>", False)[1])
        if not title:
            title = cItem.get("title", "")
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="story clearfix">', "</div>", False)[1])
        icon = self.cm.ph.getSearchGroups(data, r"<div class=\"Poster\">.*?<img[^>]+src=\"([^\"]+)\"")[0]
        if not icon:
            icon = cItem.get("icon", "")
        images = [{"title": "", "url": self._fixUrl(icon)}] if icon else []
        otherInfo = {}
        info_part = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="RightTaxContent">', "</ul>", False)[1]
        info_items = re.findall(r"<li[^>]*>(.*?)</li>", info_part, re.S)
        for item in info_items:
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<span>", "</span>", False)[1]).replace(":", "").strip()
            values = self.cm.ph.getAllItemsBeetwenMarkers(item, "<a", "</a>")
            clean_values = [self.cleanHtmlStr(v) for v in values if self.cleanHtmlStr(v)]
            value = ", ".join(clean_values)
            if not label or not value:
                continue
            if any(x in label for x in ["تصنيف", "قسم"]):
                otherInfo["category"] = value
            elif "نوع" in label:
                otherInfo["genre"] = value
            elif "لغة" in label:
                otherInfo["language"] = value
            elif any(x in label for x in ["الدولة", "البلد", "دولة"]):
                otherInfo["country"] = value
            elif any(x in label for x in ["تاريخ", "السنة", "موعد", "صدور"]):
                otherInfo["year"] = value
            elif "جودة" in label:
                otherInfo["quality"] = value
            elif any(x in label for x in ["بطولة", "الممثلين"]):
                otherInfo["stars"] = value
            elif "عدد" in label:
                otherInfo["seasons"] = value
        return [{"title": self.cleanHtmlStr(title), "text": story, "images": images, "other_info": otherInfo}]

    def handleService(self, index, refresh=0, search_pattern="", search_type=""):
        printDBG("TopCinema.handleService start")
        CBaseHostClass.handleService(self, index, refresh, search_pattern, search_type)
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
        elif category == "explore_item":
            self.exploreItems(self.currItem)
        elif category == "movie_details":
            self.showMovieDetails(self.currItem)
        elif category == "show_seasons":
            self.showSeasons(self.currItem)
        elif category == "show_episodes":
            self.showEpisodes(self.currItem)
        # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, search_pattern, search_type)
        # HISTORY SEARCH
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, TopCinema(), True, [])

    def withArticleContent(self, cItem):
        if "video" == cItem.get("type", "") or "explore_item" == cItem.get("category", ""):
            return True
        return False
