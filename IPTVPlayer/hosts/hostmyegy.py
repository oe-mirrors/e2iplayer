# -*- coding: utf-8 -*-
# Last modified: 20/11/2025
# MyEegy Host (Modified By Mohamed Elsafty)
import re
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, E2ColoR
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse, urlunparse


def GetConfigList():
    return []


def gettytul():
    return "https://myeegy.com/"


class MyEegy(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "myeegy", "cookie": "myeegy.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "wp-content/uploads/2025/09/cropped-favicon-3-238x238.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, base_url, add_params=None, post_data=None):
        printDBG("MyEegy.getPage [%s]" % base_url)
        if any(ord(c) > 127 for c in base_url):
            base_url = urllib_quote_plus(base_url, safe="://")
        if add_params is None:
            add_params = dict(self.defaultParams)
        add_params["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(base_url, add_params, post_data)

    def getLinksForVideo(self, cItem):
        printDBG("MyEegy.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        if not url:
            return []
        return [{"name": "MyEegy - %s" % cItem.get("title", ""), "url": url, "need_resolve": 1}]

    def getVideoLinks(self, url):
        printDBG("MyEegy.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def listMainMenu(self, cItem):
        printDBG("MyEegy.listMainMenu")
        self.MAIN_CAT_TAB = [{"category": "movies_folder", "title": "الأفلام"}, {"category": "series_folder", "title": "المسلسلات"}, {"category": "anime_folder", "title": "الأنمي"}, {"category": "wrestling_folder", "title": "عروض المصارعة"}, {"category": "tv_shows_folder", "title": "برامج تلفزيونية"}, {"category": "unsorted_folder", "title": "عروض وحفلات"}, {"category": "list_items", "title": "المضاف حديثا", "cat_id": None}] + self.searchItems()
        self.MOVIES_CAT_TAB = [{"category": "list_items", "title": "أفلام أجنبي", "cat_id": 74}, {"category": "list_items", "title": "أفلام أجنبية مدبلجة", "cat_id": 22668}, {"category": "list_items", "title": "أفلام آسيوي", "cat_id": 1129}, {"category": "list_items", "title": "أفلام آسيوية", "cat_id": 19946}, {"category": "list_items", "title": "أفلام أنمي", "cat_id": 411}, {"category": "list_items", "title": "أفلام أونلاين 2025", "cat_id": 17168}, {"category": "list_items", "title": "أفلام تركي", "cat_id": 21278}, {"category": "list_items", "title": "أفلام تركية", "cat_id": 19943}, {"category": "list_items", "title": "أفلام تركية مدبلجة", "cat_id": 22637}, {"category": "list_items", "title": "أفلام صينية", "cat_id": 19937}, {"category": "list_items", "title": "أفلام عربي", "cat_id": 11988}, {"category": "list_items", "title": "أفلام مدبلجة", "cat_id": 12688}, {"category": "list_items", "title": "أفلام هندي", "cat_id": 20208}, {"category": "list_items", "title": "أفلام هندية", "cat_id": 12654}, {"category": "list_items", "title": "أفلام وثائقية", "cat_id": 22605}]
        self.SERIES_CAT_TAB = [{"category": "list_items", "title": "مسلسلات أجنبي", "cat_id": 20249}, {"category": "list_items", "title": "مسلسلات أسيوي", "cat_id": 20234}, {"category": "list_items", "title": "مسلسلات اجنبي", "cat_id": 162}, {"category": "list_items", "title": "مسلسلات اسيوية", "cat_id": 12}, {"category": "list_items", "title": "مسلسلات تركي", "cat_id": 20116}, {"category": "list_items", "title": "مسلسلات تركية", "cat_id": 16395}, {"category": "list_items", "title": "مسلسلات تركيه", "cat_id": 12490}, {"category": "list_items", "title": "مسلسلات عربية", "cat_id": 12466}, {"category": "list_items", "title": "مسلسلات لاتينية", "cat_id": 22729}, {"category": "list_items", "title": "مسلسلات وثائقية", "cat_id": 22507}]
        self.ANIME_CAT_TAB = [{"category": "list_items", "title": "أفلام أنمي", "cat_id": 411}, {"category": "list_items", "title": "أفلام كرتون", "cat_id": 22608}, {"category": "list_items", "title": "مسلسلات أنمي", "cat_id": 2}, {"category": "list_items", "title": "أنمي مترجم", "cat_id": 20158}]
        self.OTHER_CAT_TAB = [{"category": "list_items", "title": "عروض وحفلات", "cat_id": 22603}]
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMoviesFolder(self, cItem):
        printDBG("MyEegy.listMoviesFolder")
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesFolder(self, cItem):
        printDBG("MyEegy.listSeriesFolder")
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listAnimeFolder(self, cItem):
        printDBG("MyEegy.listAnimeFolder")
        self.listsTab(self.ANIME_CAT_TAB, cItem)

    def listWrestlingFolder(self, cItem):
        printDBG("MyEegy.listWrestlingFolder")
        cItem = dict(cItem)
        cItem["cat_id"] = 20604
        self.listItems(cItem)

    def listTVShowsFolder(self, cItem):
        printDBG("MyEegy.listTVShowsFolder")
        cItem = dict(cItem)
        cItem["cat_id"] = 20564
        self.listItems(cItem)

    def listUnsortedFolder(self, cItem):
        printDBG("MyEegy.listUnsortedFolder")
        cItem = dict(cItem)
        cItem["cat_id"] = 22603
        self.listItems(cItem)

    def getCategoryIdBySlug(self, slug):
        """
        Fetches the category ID (cat_id) for a given slug automatically.
        Uses the WordPress REST API.
        """
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

    def listItems(self, cItem):
        printDBG("MyEegy.listItems >>>>")
        page = cItem.get("page", 1)
        per_page = 20
        current_url = cItem.get("url", "")
        if current_url and "?s=" in current_url:
            printDBG("MyEegy.listItems: Processing HTML search URL: %s" % current_url)
            params = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
            sts, data = self.cm.getPage(current_url, params)
            if not sts or not data:
                printDBG("MyEegy.listItems: Failed to get search page HTML.")
                self.addDir({"title": "Failed to load search results", "category": "none"})
                return
            friends_post_pattern = r'<div[^>]+class="friends_post"[^>]*>.*?' r'<h1[^>]+class="post-title"[^>]*>.*?' r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>.*?</h1>.*?' r'<img[^>]+data-src="([^"]+)"[^>]+alt="([^"]*)"[^>]*/?>.*?</div>'
            matches = re.findall(friends_post_pattern, data, re.DOTALL)
            printDBG("MyEegy.listItems: Found %d search results from HTML." % len(matches))
            for link, title, icon, desc in matches:
                clean_title = self.cleanHtmlStr(title)
                clean_desc = self.cleanHtmlStr(desc)
                clean_icon_raw = self.cm.getFullUrl(icon)
                if clean_icon_raw:
                    try:
                        parsed_url = urlparse(clean_icon_raw)
                        encoded_path = urllib_quote_plus(parsed_url.path, safe="/")
                        clean_icon = urlunparse(parsed_url._replace(path=encoded_path))
                    except Exception as e:
                        printDBG("MyEegy.listItems: Error encoding icon URL: %s" % e)
                        clean_icon = clean_icon_raw
                else:
                    clean_icon = clean_icon_raw
                clean_title_for_list = re.sub(r"^\s*([^ ]+)\s+", "", clean_title, flags=re.IGNORECASE)
                params = {"title": clean_title_for_list, "desc": clean_desc, "icon": clean_icon, "good_for_fav": True, "url": link, "category": "explore_item"}
                self.addDir(params)
            next_page_pattern = r'<a[^>]+class="nextpostslink"[^>]+href="([^"]+)"[^>]*>'
            next_page_match = re.search(next_page_pattern, data)
            if next_page_match:
                next_url = next_page_match.group(1)
                if next_url:
                    next_url_full = self.cm.getFullUrl(next_url)
                    printDBG("MyEegy.listItems: Found next page URL: %s" % next_url_full)
                    next_item = dict(cItem)
                    next_item.update({"title": "%s▶ NEXT عرض المزيد" % E2ColoR("yellow"), "url": next_url_full, "category": "list_items"})
                    self.addDir(next_item)
            return
        else:
            cat_id = cItem.get("cat_id") or (self.getCategoryIdBySlug(cItem.get("slug")) if cItem.get("slug") else None)
            api_url = "%swp-json/wp/v2/posts?categories=%d&per_page=%d&page=%d&_embed" % (self.MAIN_URL, cat_id, per_page, page) if cat_id else "%swp-json/wp/v2/posts?orderby=date&per_page=%d&page=%d&_embed" % (self.MAIN_URL, per_page, page)
            sts, data = self.getPage(api_url)
            if not sts or not data:
                self.addDir({"title": "Failed to load data from API", "category": "none"})
                return
            try:
                posts = json_loads(data)
            except Exception as e:
                printDBG("MyEegy JSON parse error: %s" % e)
                self.addDir({"title": "JSON read error - Check /tmp/myeegy_debug.html", "category": "none"})
                return
            for post in posts:
                title = self.cleanHtmlStr(post.get("title", {}).get("rendered", "No Title"))
                clean_title = re.sub(r"^\s*([^ ]+)\s+", "", title, flags=re.IGNORECASE)
                link = post.get("link", "")
                desc = self.cleanHtmlStr(post.get("excerpt", {}).get("rendered", "") or clean_title)
                icon = post.get("jetpack_featured_media_url") or (post.get("_embedded", {}).get("wp:featuredmedia", [{}])[0].get("source_url")) or (lambda mid=post.get("featured_media"): self.getPage("%swp-json/wp/v2/media/%d" % (self.MAIN_URL, mid))[1] if mid else "")()
                if icon:
                    try:
                        icon = urllib_quote_plus(icon, safe=":/%#?=&")
                    except Exception:
                        pass
                params = {"title": clean_title, "desc": desc, "icon": icon, "good_for_fav": True, "url": link, "category": "explore_item"}
                self.addDir(params)
            if len(posts) == per_page:
                next_page = page + 1
                base_url = cItem.get("url", "").rstrip("/")
                base_url = re.sub(r"/page/\d+/?$", "", base_url) if "/page/" in base_url else base_url
                next_item = dict(cItem)
                next_item.update({"title": "%s▶ NEXT عرض المزيد" % E2ColoR("yellow"), "url": "%s/page/%d/" % (base_url, next_page), "page": next_page, "category": "list_items"})
                self.addDir(next_item)

    def exploreItems(self, cItem):
        printDBG("MyEegy.exploreItems [%s]" % cItem["url"])
        simple_header = dict(self.HEADER)
        if "Accept-Encoding" in simple_header:
            del simple_header["Accept-Encoding"]
        params = {"header": simple_header, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        sts, data = self.cm.getPage(cItem["url"], params)
        if not sts or not data:
            self.addDir({"title": "Failed to load page", "category": "none"})
            return
        original_title = cItem.get("title", "Video")
        clean_title = original_title.replace("[", "(").replace("]", ")")
        if cItem.get("from_episodes_list"):
            pass
        else:
            seasons_section = re.search(r'<div class="seasons-episodes-section">(.*?)</div>\s*</div>', data, re.DOTALL)
            episodes_list = []
            if seasons_section:
                block = seasons_section.group(1)
                eps_matches = re.findall(r'<a href="([^"]+)"[^>]*>\s*<span class="ep-number">([^<]+)</span>', block, re.DOTALL)
                for ep_url, ep_title in eps_matches:
                    episodes_list.append({"title": ep_title.strip(), "url": self.cm.getFullUrl(ep_url)})
            if episodes_list:
                params2 = dict(cItem)
                params2.update({"category": "list_episodes", "title": "المواسم والحلقات", "episodes_list": episodes_list})
                self.addDir(params2)
        servers_section_match = re.search(r'<div class="server-list"[^>]*>(.*?)</div>', data, re.DOTALL)
        if servers_section_match:
            servers_section = servers_section_match.group(1)
            printDBG("Found servers section: %s..." % servers_section[:200])
            servers = re.findall(r'<button[^>]+class="server-button"[^>]+data-src="([^"]+)"[^>]*>([^<]+)</button>', servers_section)
            printDBG("Found %d servers" % len(servers))
            if not servers:
                servers = re.findall(r'<button[^>]+data-src="([^"]+)"[^>]*>([^<]+)</button>', servers_section)
                printDBG("Found %d servers with alternative method" % len(servers))
            for link, name in servers:
                clean_name = self.cleanHtmlStr(name)
                full_url = self.cm.getFullUrl(link)
                printDBG("Server: %s -> %s" % (clean_name, full_url))
                if full_url:
                    final_title = "%s [ %s ]" % (clean_title, clean_name)
                    quality_match = re.search(r"(\d+p)", clean_name, re.IGNORECASE)
                    if quality_match:
                        quality = quality_match.group(1)
                        final_title += " %s" % quality
                    self.addVideo({"title": final_title, "name": final_title, "url": strwithmeta(full_url, {"Referer": cItem["url"], "Origin": self.up.getDomain(full_url)}), "need_resolve": 1})
        else:
            printDBG("No servers section found!")
            iframes = re.findall(r'<iframe[^>]+src="([^"]+)"', data)
            printDBG("Found %d iframes" % len(iframes))
            for iframe in iframes:
                full_url = self.cm.getFullUrl(iframe)
                if full_url:
                    host_name = self.up.getHostName(full_url)
                    final_title = "%s [ %s ]" % (clean_title, host_name)
                    self.addVideo({"title": final_title, "name": final_title, "url": strwithmeta(full_url, {"Referer": cItem["url"], "Origin": self.up.getDomain(full_url)}), "need_resolve": 1})
        if not servers_section_match and not iframes:
            self.addDir({"title": "No servers found", "category": "none"})

    def listEpisodes(self, cItem):
        printDBG("MyEegy.listEpisodes >>>>")
        episodes = cItem.get("episodes_list", [])
        for ep in episodes:
            params = {"title": ep["title"], "url": ep["url"], "category": "explore_item", "good_for_fav": True, "from_episodes_list": True}
            self.addDir(params)

    def exploreSeriesItems(self, cItem):
        printDBG("MyEegy.exploreSeriesItems [%s]" % cItem["url"])
        self.exploreItems(cItem)

    def getArticleContent(self, cItem):
        printDBG("MyEegy.getArticleContent [%s]" % cItem)
        simple_header = dict(self.HEADER)
        if "Accept-Encoding" in simple_header:
            del simple_header["Accept-Encoding"]
        params = {"header": simple_header, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        sts, data = self.cm.getPage(cItem["url"], params)
        if not sts or not data:
            printDBG("MyEegy.getArticleContent: Failed to get page data.")
            return []
        meta_pattern = re.compile(r'<div class="meta-row">.*?' r'<span class="meta-label">(.*?)</span>.*?' r'<span class="meta-term">.*?' r"<a.*?>(.*?)</a>.*?" r"</div>", re.DOTALL)
        matches = meta_pattern.findall(data)
        movie_info = {}
        for label, value in matches:
            clean_label = self.cleanHtmlStr(label).replace(":", "").strip()
            clean_value = self.cleanHtmlStr(value).strip()
            if clean_label and clean_value:
                movie_info[clean_label] = clean_value
        formatted_description = ""
        if movie_info:
            year = movie_info.get("Year of issue", "")
            if year:
                formatted_description += "%s\n" % year
            desired_order = ["Year of issue", "Category", "Quality", "Language", "Country"]
            details_list = []
            for key in desired_order:
                if key in movie_info:
                    details_list.append("%s : %s" % (key, movie_info[key]))
            if details_list:
                formatted_description += " | ".join(details_list)
        story_pattern = r'<div class="story-content"[^>]*>(.*?)</div>'
        story_match = re.search(story_pattern, data, re.DOTALL)
        if story_match:
            story_content = self.cleanHtmlStr(story_match.group(1))
            full_description = "%s\n%s" % (story_content, formatted_description)
        else:
            full_description = formatted_description
        title = self.cleanHtmlStr(cItem.get("title", "Information"))
        if not full_description:
            printDBG("MyEegy.getArticleContent: Could not extract any description.")
            return []
        return [{"title": title, "content": full_description}]

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MyEegy.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem["url"] = "%s?s=%s" % (gettytul(), urllib_quote_plus(searchPattern))
        self.listItems(cItem)

    def getFavouriteData(self, cItem):
        printDBG("MyEegy.getFavouriteData")
        return json_dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG("MyEegy.getLinksForFavourite")
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG("MyEegy.setInitListFromFavouriteItem")
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
        typ = self.currItem.get("type", "")
        printDBG("handleService: >> name[%s], category[%s], type[%s]" % (name, category, typ))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "movies_folder":
            self.listMoviesFolder(self.currItem)
        elif category == "series_folder":
            self.listSeriesFolder(self.currItem)
        elif category == "anime_folder":
            self.listAnimeFolder(self.currItem)
        elif category == "wrestling_folder":
            self.listWrestlingFolder(self.currItem)
        elif category == "tv_shows_folder":
            self.listTVShowsFolder(self.currItem)
        elif category == "unsorted_folder":
            self.listUnsortedFolder(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "explore_item":
            self.exploreItems(self.currItem)
        elif category == "explore_episodes":
            self.exploreSeriesItems(self.currItem)
        elif category == "list_episodes":
            cItem = dict(self.currItem)
            self.listEpisodes(cItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        elif typ == "video" or (self.currItem.get("need_resolve", 0) == 1 and self.currItem.get("url", "").startswith("http")):
            printDBG("Handling video item: %s" % self.currItem)
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, MyEegy(), True, [])

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category") == "explore_item"
