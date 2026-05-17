# -*- coding: utf-8 -*-
# Last modified: 22/02/2026
# Myegy Host (Modified By Mohamed Elsafty)
# ===================== Standard library =====================
import re
from urllib.parse import urlparse, urlunparse, quote

# ===================== IPTVPlayer =====================
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus

# ===================== COLORS =====================
Y = E2ColoR("yellow")
W = E2ColoR("white")
# ======================================================
TAG_RE = re.compile(r"<.*?>", re.DOTALL)
LEADING_SYMBOLS_RE = re.compile(r"^[^\w\s]+")


def GetConfigList():
    return []


def gettytul():
    return "https://myigy.cam/"


class MyYegy(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "Myegy", "cookie": "Myegy.cookie"})
        self.MAIN_URL = gettytul()
        self.SEARCH_URL = self.MAIN_URL + "search.php?keywords="
        self.DEFAULT_ICON_URL = gettytul() + "wp-content/uploads/2026/02/myegylogo3.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, base_url, add_params=None, post_data=None):
        printDBG("Myegy.getPage [%s]" % base_url)
        if base_url and any(ord(c) > 127 for c in base_url):
            parts = list(urlparse(base_url))
            parts[2] = urllib_quote_plus(parts[2], safe="/")
            parts[4] = urllib_quote_plus(parts[4], safe="=&?")
            base_url = urlunparse(parts)
        if add_params is None:
            add_params = dict(self.defaultParams)
        add_params["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(base_url, add_params, post_data)

    def getLinksForVideo(self, cItem):
        printDBG("Myegy.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return []
        return [{"name": "Myegy - %s" % cItem.get("title", ""), "url": url, "need_resolve": 1}]

    def getVideoLinks(self, url):
        printDBG("Myegy.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def listMainMenu(self, cItem):
        printDBG("Myegy.listMainMenu")
        MAIN_CAT = [
            {"category": "sub_folder", "title": "المسلسلات", "tab_id": "SERIES"},
            {"category": "sub_folder", "title": "الأفلام", "tab_id": "MOVIES"},
            {"category": "sub_folder", "title": "الأنمي", "tab_id": "ANIME"},
            {"category": "list_items", "title": "برامج تلفزيونية", "url": self.MAIN_URL + "category/برامج-تلفزيونية/"},
            {"category": "list_items", "title": "عروض وحفلات", "url": self.MAIN_URL + "category/عروض-وحفلات/"},
        ] + self.searchItems()
        self.listsTab(MAIN_CAT, cItem)

    def listSubFolder(self, cItem):
        tab_id = cItem.get("tab_id")
        tabs = {
            "SERIES": [
                {"category": "list_items", "title": "كل المسلسلات", "url": self.MAIN_URL + "category/series/"},
                {"category": "list_items", "title": "مسلسلات اجنبي", "url": self.MAIN_URL + "category/مسلسلات-اجنبي/"},
                {"category": "list_items", "title": "مسلسلات اسيوية", "url": self.MAIN_URL + "category/مسلسلات-اسيوية/"},
                {"category": "list_items", "title": "مسلسلات تركية", "url": self.MAIN_URL + "category/مسلسلات-تركية/"},
                {"category": "list_items", "title": "مسلسلات تركية مدبلجة", "url": self.MAIN_URL + "category/مسلسلات-تركية-مدبلجة/"},
                {"category": "list_items", "title": "مسلسلات لاتينية", "url": self.MAIN_URL + "category/مسلسلات-لاتينية/"},
                {"category": "list_items", "title": "مسلسلات هندية", "url": self.MAIN_URL + "category/مسلسلات-هندية/"},
                {"category": "list_items", "title": "مسلسلات وثائقية", "url": self.MAIN_URL + "category/مسلسلات-وثائقية/"},
            ],
            "MOVIES": [
                {"category": "list_items", "title": "كل الافلام", "url": self.MAIN_URL + "category/movies/"},
                {"category": "list_items", "title": "افلام عربي", "url": self.MAIN_URL + "category/افلام-عربي/"},
                {"category": "list_items", "title": "افلام اجنبي", "url": self.MAIN_URL + "category/افلام-اجنبي/"},
                {"category": "list_items", "title": "افلام اجنبية مدبلجة", "url": self.MAIN_URL + "category/افلام-اجنبية-مدبلجة/"},
                {"category": "list_items", "title": "افلام اسيوية", "url": self.MAIN_URL + "category/افلام-اسيوية/"},
                {"category": "list_items", "title": "افلام تركية", "url": self.MAIN_URL + "category/افلام-تركية/"},
                {"category": "list_items", "title": "افلام سعودية", "url": self.MAIN_URL + "category/افلام-سعودية/"},
                {"category": "list_items", "title": "افلام هندية", "url": self.MAIN_URL + "category/افلام-هندية/"},
                {"category": "list_items", "title": "افلام وثائقية", "url": self.MAIN_URL + "category/افلام-وثائقية/"},
            ],
            "ANIME": [
                {"category": "list_items", "title": "مسلسلات انمي", "url": self.MAIN_URL + "category/مسلسلات-انمي/"},
                {"category": "list_items", "title": "مسلسلات كرتون", "url": self.MAIN_URL + "category/مسلسلات-كرتون/"},
                {"category": "list_items", "title": "افلام انمي", "url": self.MAIN_URL + "category/افلام-انمي/"},
                {"category": "list_items", "title": "افلام اسلام الجيزاوي", "url": self.MAIN_URL + "category/افلام-اسلام-الجيزاوي/"},
                {"category": "list_items", "title": "افلام كرتون", "url": self.MAIN_URL + "category/افلام-كرتون/"},
            ],
        }
        self.listsTab(tabs.get(tab_id, []), cItem)

    def getCategoryIdBySlug(self, slug):
        url = "%swp-json/wp/v2/categories?slug=%s" % (self.MAIN_URL, slug)
        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("Cannot fetch category id for slug: %s" % slug)
            return None
        try:
            j = json_loads(data)
            if isinstance(j, list) and len(j) > 0:
                return j[0].get("id")
        except Exception as e:
            printDBG("getCategoryIdBySlug JSON error: %s" % e)
        return None

    def _cleanTitle(self, title):
        if not title:
            return ""
        title = self.cleanHtmlStr(title).replace("[", "(").replace("]", ")")
        while True:
            new_title = re.sub(r"^\s*(تحميل|مشاهدة|و|تحميل ومشاهدة|مشاهدة وتحميل)\s*", "", title, flags=re.IGNORECASE).strip()
            if new_title == title:
                break
            title = new_title
        title = re.sub(r"(مترجم[هة]?|مدبلج[هة]?)\s*.*$", r"\1", title, flags=re.IGNORECASE)
        patterns = [r"\s*نسخ[هة]\s*حصر[يياأآ]+\s*\s*", r"\s*حصر[يياأآ]+\s*ًا\s*", r"\s*نسخ[هة]\s*حصر[يياأآ]*\s*"]
        for p in patterns:
            title = re.sub(p, " ", title, flags=re.IGNORECASE)
        return re.sub(r"\s{2,}", " ", title).strip()

    def listItems(self, cItem):
        printDBG("Myegy.listItems >>>>")
        url = cItem.get("url")
        if not url:
            return
        sts, data = self.getPage(url)
        if not sts or not data:
            return
        page = int(cItem.get("page", 1))
        articles = re.findall(r'<article class="[^"]*(?:series-card|movie-card)[^"]*".*?</article>', data, re.DOTALL)
        for item in articles:
            link = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]+)"')[0]
            title = self.cm.ph.getSearchGroups(item, r'<h3 class="card-title">(.*?)</h3>')[0]
            img = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            if not img:
                img = self.cm.ph.getSearchGroups(item, r'srcset="([^"]+)"')[0].split(",")[0].split(" ")[0]
            if not link or not title:
                continue
            title = self.cleanHtmlStr(title)
            title = re.sub(r"^(مشاهدة\s+(مسلسل|فيلم|انمي|عرض|مشاهدة)\s+و?تحميل\s+)", "", title, flags=re.IGNORECASE)
            full_icon = self.cm.getFullUrl(img)
            try:
                full_icon = quote(full_icon, safe=":/?=&")
            except (TypeError, ValueError):
                pass
            genre = ""
            country = ""
            meta_block = self.cm.ph.getDataBeetwenMarkers(item, '<div class="card-meta">', "</div>", False)[1]
            if meta_block:
                meta_items = re.findall(r"<a[^>]*>([^<]+)</a>", meta_block)
                meta_items = [self.cleanHtmlStr(x).strip() for x in meta_items if self.cleanHtmlStr(x).strip()]
                genre_match = re.search(r'meta-genre".*?</a>\s*<a[^>]*>([^<]+)</a>', meta_block, re.DOTALL)
                if genre_match:
                    genre = self.cleanHtmlStr(genre_match.group(1))
                country_match = re.search(r'meta-country".*?<a[^>]*>([^<]+)</a>', meta_block, re.DOTALL)
                if country_match:
                    country = self.cleanHtmlStr(country_match.group(1))
                if not genre and len(meta_items) > 0:
                    genre = meta_items[0]
                if not country and len(meta_items) > 1:
                    country = meta_items[1]
            desc_parts = []
            if genre:
                desc_parts.append(Y + "النوع: " + W + genre)
            if country:
                desc_parts.append(Y + "الدولة: " + W + country)
            desc = " | ".join(desc_parts)
            printDBG("DEBUG FINAL DESC: " + desc)
            self.addDir({"title": title, "url": self.cm.getFullUrl(link), "icon": full_icon, "category": "explore_item", "good_for_fav": True, "desc": desc})
        next_page = self.cm.ph.getSearchGroups(data, r'<a class="next page-numbers" href="([^"]+)"')[0]
        if next_page:
            self.addDir(
                {
                    "title": Y + _("Next Page") + " ▶▶▶" + W,
                    "url": self.cm.getFullUrl(next_page),
                    "category": "list_items",
                    "page": page + 1,
                    "icon": self.DEFAULT_ICON_URL,
                }
            )

    def exploreItems(self, cItem):
        printDBG("Myegy.exploreItems [%s]" % cItem["url"])
        url = cItem["url"].replace("watch.php", "view.php")
        sts, data = self.getPage(url)
        if not sts or not data:
            return
        icon = cItem.get("icon", "")
        series_title = self._cleanTitle(cItem.get("title", "Video"))
        seasons_found = False
        description_parts = []
        info_parts = []
        details_section = re.search(r'<section class="series-details-section">(.*?)</section>', data, re.DOTALL)
        if details_section:
            rows = re.findall(r'<div class="detail-row">(.*?)</div>', details_section.group(1), re.DOTALL)
            for idx, row in enumerate(rows):
                key_match = re.search(r'<span class="detail-key">(.*?)</span>', row, re.DOTALL)
                val_match = re.search(r'<span class="detail-val">(.*?)</span>', row, re.DOTALL)
                if key_match and val_match:
                    key = TAG_RE.sub("", key_match.group(1)).strip()
                    val = TAG_RE.sub("", val_match.group(1)).strip()
                    key_clean = LEADING_SYMBOLS_RE.sub("", key).strip()
                    key_clean = key_clean.rstrip(":").strip()
                    val = val.rstrip(",").strip()
                    if key_clean and val:
                        info_parts.append(Y + key_clean + ":" + W + " " + val)
        if info_parts:
            description_parts.append(" | ".join(info_parts))
        story = ""
        story_match = re.search(r'<section class="series-story-section">.*?<p>(.*?)</p>', data, re.DOTALL)
        if story_match:
            story = TAG_RE.sub("", story_match.group(1)).strip()
            story = re.sub(r"^القصه", "", story).strip()
            if story:
                description_parts.append(Y + "القصــــة:" + W + "\n" + story)
        desc = "\n".join(description_parts)
        if not cItem.get("from_episodes_list"):
            episodes_section = re.search(r'<section class="episodes-grid-section">(.*?)</section>', data, re.DOTALL)
            if episodes_section:
                episode_items = re.findall(r'<a[^>]+href="([^"]+\?episode=(\d+))"[^>]*class="([^"]*episode-number-btn[^"]*)"[^>]*>.*?class="ep-number">\s*(\d+)\s*</span>', episodes_section.group(1), re.DOTALL)
                if episode_items:
                    seasons_found = True
                    episode_items = sorted(episode_items, key=lambda x: int(x[1]))
                    total_eps = len(episode_items)
                    self.addMarker({"title": f"{Y}قائمة الحلقات المتاحة ({total_eps}){W}", "icon": icon})
                    for full_url, ep_num, class_attr, ep_number in episode_items:
                        ep_num_int = int(ep_num)
                        if "active" in class_attr:
                            title = f"{Y}▶ الحلقة {ep_num_int}{W}"
                        else:
                            title = f"الحلقة {ep_num_int}"
                        self.addDir({"category": "explore_item", "title": title, "url": self.cm.getFullUrl(full_url), "icon": icon, "desc": desc, "from_episodes_list": True, "good_for_fav": True})
        if not seasons_found:
            printDBG("Showing servers directly...")
            self.addMarker({"title": f"{Y}سيرفرات المشاهدة{W}", "icon": icon})
            servers = re.findall(r'data-server-url="([^"]+)"[^>]*data-server-name="([^"]+)"', data)
            for embed_link, srv_name in servers:
                host_name = self.up.getHostName(embed_link)
                self.addVideo({"title": "%s [%s] - %s" % (series_title, srv_name.strip(), host_name), "url": strwithmeta(embed_link, {"Referer": url}), "icon": icon, "desc": desc, "need_resolve": 1})

    def listEpisodes(self, cItem):
        printDBG("Myegy.listEpisodes >>>>")
        episodes = cItem.get("episodes_list", [])
        self.addMarker({"title": f"{Y}قائمة الحلقات{W}", "icon": cItem.get("icon", "")})
        for ep in episodes:
            params = {"category": "explore_item", "title": ep["title"], "url": ep["url"], "icon": cItem.get("icon", ""), "from_episodes_list": True, "good_for_fav": True}
            self.addDir(params)

    def exploreSeriesItems(self, cItem):
        printDBG("Myegy.exploreSeriesItems [%s]" % cItem["url"])
        self.exploreItems(cItem)

    def getArticleContent(self, cItem):
        printDBG("Myegy.getArticleContent [%s]" % cItem)
        simple_header = dict(self.HEADER)
        if "Accept-Encoding" in simple_header:
            del simple_header["Accept-Encoding"]
        params = {"header": simple_header, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        sts, data = self.cm.getPage(cItem["url"], params)
        if not sts or not data:
            printDBG("DEBUG: Failed to load page or empty content")
            return []
        story_text = ""
        story_match = re.search(r'<section class="series-story-section">.*?<p>(.*?)</p>', data, re.DOTALL)
        if story_match:
            story_text = TAG_RE.sub("", story_match.group(1)).strip()
            printDBG("DEBUG: story found in series-story-section -> %s" % story_text)
        story_text = re.sub(r"^القصه", "", story_text).strip()
        description_parts = []
        details_section = re.search(r'<section class="series-details-section">(.*?)</section>', data, re.DOTALL)
        if details_section:
            printDBG("DEBUG: Found details_section")
            rows = re.findall(r'<div class="detail-row">(.*?)</div>', details_section.group(1), re.DOTALL)
            printDBG("DEBUG: Number of rows found -> %d" % len(rows))
            for idx, row in enumerate(rows):
                key_match = re.search(r'<span class="detail-key">(.*?)</span>', row, re.DOTALL)
                val_match = re.search(r'<span class="detail-val">(.*?)</span>', row, re.DOTALL)
                if key_match and val_match:
                    key = TAG_RE.sub("", key_match.group(1)).strip()
                    val = TAG_RE.sub("", val_match.group(1)).strip()
                    key_clean = self.LEADING_SYMBOLS_RE.sub("", key).strip()
                    key_clean = key_clean.rstrip(":").strip()
                    val = val.rstrip(",").strip()
                    if key_clean and val:
                        description_parts.append(Y + key_clean + ":" + W + " " + val)
                        printDBG("DEBUG: row[%d] key=%s val=%s" % (idx, key_clean, val))
                else:
                    printDBG("DEBUG: row[%d] skipped, key or val not found" % idx)
        if story_text:
            description_parts.append(Y + "القصــــة:" + W + "\n" + story_text)
        final_text = "\n".join(description_parts)
        icon = cItem.get("icon", "")
        poster_match = re.search(r'<div class="movie-poster">\s*<img src="([^"]+)"', data)
        if poster_match:
            icon = self.cm.getFullUrl(poster_match.group(1))
            try:
                icon = quote(icon, safe=":/?=&")
            except (TypeError, ValueError):
                pass
        printDBG("DEBUG: poster url -> %s" % icon)
        otherInfo = {}
        return [{"title": cItem.get("title", "Information"), "text": final_text, "images": [{"title": "", "url": icon}], "other_info": otherInfo}]

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Myegy.listSearchResult searchPattern[%s]" % searchPattern)
        url = self.MAIN_URL + "?s=" + quote(searchPattern)
        sts, data = self.getPage(url)
        if not sts:
            return
        blocks = re.findall(r'<li class="box__.*?">(.*?)</li>', data, re.DOTALL)
        for item in blocks:
            link_match = re.search(r'<a href="([^"]+)"', item)
            if not link_match:
                continue
            link = self.getFullUrl(link_match.group(1))
            title_match = re.search(r"<h3>(.*?)</h3>", item)
            if not title_match:
                continue
            title = title_match.group(1)
            title = self.cleanHtmlStr(title)
            title = re.sub(r"^(مشاهدة\s+(مسلسل|فيلم|انمي|عرض|مشاهدة)\s+و?تحميل\s+)", "", title, flags=re.IGNORECASE)
            img = re.search(r'data-src="([^"]+)"', item)
            icon = self.getFullUrl(img.group(1)) if img else ""
            link = quote(link, safe=":/?&=%")
            icon = quote(icon, safe=":/?&=%") if icon else ""
            title = f"{Y}{self._cleanTitle(title)}{W}"
            self.addDir({"category": "explore_item", "title": title, "url": link, "icon": icon, "good_for_fav": True})

    def getFavouriteData(self, cItem):
        printDBG("Myegy.getFavouriteData")
        return json_dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG("Myegy.getLinksForFavourite")
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG("Myegy.setInitListFromFavouriteItem")
        try:
            cItem = json_loads(fav_data)
        except Exception:
            cItem = {}
            printExc()
        return cItem

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        mode = self.currItem.get("type", "")
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "sub_folder":
            self.listSubFolder(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "explore_item":
            self.exploreItems(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        elif mode == "video" or self.currItem.get("need_resolve"):
            pass
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, MyYegy(), True, [])

    def withArticleContent(self, cItem):
        if "video" == cItem.get("type", "") or "explore_item" == cItem.get("category", ""):
            return True
        return False
