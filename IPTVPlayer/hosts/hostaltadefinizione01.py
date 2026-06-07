# -*- coding: utf-8 -*-
# Last Modified: 07.06.2026 - passata
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin

###################################################
# FOREIGN import
###################################################
import re

try:
    import json
except Exception:
    import simplejson as json
###################################################


def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return "https://altadefinizione.ovh/"


class Altadefinizione(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "altadefinizione.ovh", "cookie": "altadefinizione.ovh.cookie"})

        self.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest"})

        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = gettytul() + "static/favicon.ico"

        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)

        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)

        addParams["cloudflare_params"] = {"domain": self.up.getDomain(baseUrl), "cookie_file": self.COOKIE_FILE, "User-Agent": self.USER_AGENT, "full_url_handle": _getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("Altadefinizione.listMainMenu")

        main_menu = [{"title": "Home", "url": self.MAIN_URL, "category": "list_items"}, {"title": "Film", "url": self.MAIN_URL + "archive?type=movie", "category": "list_items"}, {"title": "Serie TV", "url": self.MAIN_URL + "archive?type=tv", "category": "list_items"}, {"title": "Archivio", "url": self.MAIN_URL + "archive", "category": "list_items"}, {"title": "Trending", "url": self.MAIN_URL + "archive?sort=trending", "category": "list_items"}, {"title": "Top Rated", "url": self.MAIN_URL + "archive?sort=rating", "category": "list_items"}, {"title": "Random", "url": self.MAIN_URL + "random", "category": "explore_item"}, {"title": "Cerca", "url": "", "category": "search", "need_letters": False}]

        for item in main_menu:
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

        # Extract genres from homepage
        sts, data = self.getPage(self.MAIN_URL)
        if sts:
            genre_links = re.findall(r'<a href="([^"]+archive\?[^"]+genre_id=\d+[^"]+)">([^<]+)</a>', data)
            if genre_links:
                genres = []
                seen = set()
                for url, title in genre_links:
                    if title and url and title not in seen:
                        seen.add(title)
                        genres.append({"name": "category", "category": "list_items", "title": title.strip(), "url": self.getFullUrl(url)})
                if genres:
                    params = dict(cItem)
                    params.update({"name": "category", "category": "sub_items", "title": "Generi", "sub_items": genres})
                    self.addDir(params)

    def extractMoviesFromHTML(self, html, cItem):
        """Extract movie/TV items from HTML"""
        items = []

        # Carousel items (homepage)
        carousel_items = re.findall(r'<div class="carousel-item poster-item">(.*?)</div>\s*</div>', html, re.DOTALL)

        for block in carousel_items:
            item = self.parseMovieBlock(block, cItem)
            if item:
                items.append(item)

        # Archive grid items
        if not items:
            archive_items = re.findall(r'<div class="[^"]*poster-item[^"]*">(.*?)</div>\s*</div>', html, re.DOTALL)
            for block in archive_items:
                item = self.parseMovieBlock(block, cItem)
                if item:
                    items.append(item)

        # Fallback: generic pattern
        if not items:
            movie_links = re.findall(r'<a href="(/detail/[^"]+)"[^>]*>.*?<img[^>]+src="([^"]+)"[^>]*>.*?<h[^>]*>([^<]+)</h', html, re.DOTALL)
            for url, icon, title in movie_links:
                if url and title:
                    params = dict(cItem)
                    params.update({"good_for_fav": True, "category": "explore_item", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url), "icon": self.getFullIconUrl(icon), "desc": title})
                    items.append(params)

        return items

    def parseMovieBlock(self, block, cItem):
        """Parse a single movie block"""
        url_match = re.search(r'href="([^"]+)"', block)
        if not url_match:
            return None
        url = self.getFullUrl(url_match.group(1))

        if "/detail/" not in url:
            return None

        title_match = re.search(r'<h[^>]*class="[^"]*movie-card-title[^"]*"[^>]*>([^<]+)</h', block)
        if not title_match:
            title_match = re.search(r'alt="([^"]+)"', block)
        if not title_match:
            return None

        title = self.cleanHtmlStr(title_match.group(1))

        icon_match = re.search(r'<img[^>]+src="([^"]+)"', block)
        icon = self.getFullIconUrl(icon_match.group(1)) if icon_match else self.DEFAULT_ICON_URL

        rating_match = re.search(r'<span class="label rate">([^<]+)</span>', block)
        rating = rating_match.group(1) if rating_match else ""

        desc_parts = []
        if rating:
            desc_parts.append("Rating: " + rating)

        year_match = re.search(r"/(?:film|tv)-[^-]+-(\d{4})", url)
        if year_match:
            desc_parts.append(year_match.group(1))

        if "/tv/" in url:
            desc_parts.append("Serie TV")
        elif "/film/" in url:
            desc_parts.append("Film")

        desc = " | ".join(desc_parts) if desc_parts else title

        params = dict(cItem)
        params.update({"good_for_fav": True, "category": "explore_item", "title": title, "url": url, "icon": icon, "desc": desc})
        return params

    def listItems(self, cItem, nextCategory):
        printDBG("Altadefinizione.listItems - URL: %s" % cItem["url"])
        page = cItem.get("page", 1)

        url = cItem["url"]
        if page > 1:
            if "?" in url:
                if "page=" in url:
                    url = re.sub(r"page=\d+", f"page={page}", url)
                else:
                    url += f"&page={page}"
            else:
                url += f"?page={page}"

        sts, data = self.getPage(url)
        if not sts:
            return
        self.setMainUrl(self.cm.meta["url"])

        items = self.extractMoviesFromHTML(data, cItem)

        for item in items:
            self.addDir(item)

        # Check for next page
        next_match = re.search(r'<a[^>]*href="([^"]*page=(\d+)[^"]*)"[^>]*>.*?(?:Next|Successivo|»).*?</a>', data, re.IGNORECASE)
        if next_match:
            next_page_num = int(next_match.group(2))
            if next_page_num > page:
                params = dict(cItem)
                params.update({"title": "Next page", "page": next_page_num, "url": cItem["url"]})
                self.addDir(params)

    def getArticleContent(self, cItem):
        """Extract movie info - full description and metadata with correct cover"""
        retTab = []

        # Get the detail page URL
        url = cItem.get("prev_url", cItem.get("url", ""))
        if not url:
            printDBG("No URL for article content")
            return retTab

        printDBG("Fetching article for: %s" % cItem.get("title", ""))

        sts, data = self.getPage(url)
        if not sts:
            printDBG("Failed to fetch page")
            return retTab

        # Get title from the detail page
        title_match = re.search(r"<h1[^>]*>([^<]+)</h1>", data)
        if title_match:
            title = self.cleanHtmlStr(title_match.group(1))
        else:
            title = cItem.get("title", "")

        # Extract description/plot
        desc = ""
        desc_match = re.search(r'<p class="slide-plot">([^<]+)</p>', data)
        if desc_match:
            desc = self.cleanHtmlStr(desc_match.group(1))
        else:
            desc_match = re.search(r'<meta name="description" content="([^"]+)"', data)
            if desc_match:
                desc = self.cleanHtmlStr(desc_match.group(1))

        # Clean description
        if desc:
            desc = re.sub(r"\s+", " ", desc).strip()
            if len(desc) > 500:
                desc = desc[:497] + "..."
        else:
            desc = "Nessuna descrizione disponibile"

        # Use the correct cover from cItem (from the movie list)
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)

        # Build items list for additional info
        itemsList = []

        # Year
        year_match = re.search(r'<span class="meta-list"><span>(\d{4})</span></span>', data)
        if year_match:
            itemsList.append(("Anno", year_match.group(1)))

        # Rating
        rating_match = re.search(r'<span class="label rate">([^<]+)</span>', data)
        if rating_match:
            itemsList.append(("Voto", rating_match.group(1) + "/10"))

        # Genre
        genre_match = re.search(r'<a href="[^"]*genre_id=\d+[^"]*">([^<]+)</a>', data)
        if genre_match:
            itemsList.append(("Genere", genre_match.group(1)))

        # Duration
        duration_match = re.search(r"(\d+)\s*(?:min|minuti)", data, re.IGNORECASE)
        if duration_match:
            itemsList.append(("Durata", duration_match.group(1) + " minuti"))

        # Build result
        result = {"title": title, "text": desc, "images": [{"title": "", "url": icon}], "other_info": {"custom_items_list": itemsList}}

        retTab.append(result)
        printDBG("Article content ready for: %s" % title)

        return retTab

    def exploreItem(self, cItem):
        printDBG("Altadefinizione.exploreItem - %s" % cItem["title"])

        # Store the URL for article content
        cItem["prev_url"] = cItem["url"]

        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        self.setMainUrl(self.cm.meta["url"])

        urlTab = []
        seen_urls = set()

        # Find iframes (main video sources)
        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\'][^>]*>', data, re.IGNORECASE)

        for src in iframes:
            src = src.strip()
            if src.startswith("//"):
                src = "https:" + src

            if src and src not in seen_urls:
                video_keywords = ["vixsrc", "streamtape", "doodstream", "mp4upload", "vidcloud", "voe", "vudeo", "netu", "m3u8", ".mp4"]
                if any(keyword in src.lower() for keyword in video_keywords):
                    seen_urls.add(src)
                    host_name = self.getVideoHostName(src)
                    url_with_meta = strwithmeta(src, {"Referer": cItem["url"]})
                    urlTab.append({"name": host_name, "url": url_with_meta, "need_resolve": 1})

        # Find data-link attributes
        data_links = re.findall(r'data-link=["\']([^"\']+)["\']', data)
        for link in data_links:
            if link and link not in seen_urls:
                if self.up.checkHostSupport(link):
                    seen_urls.add(link)
                    host_name = self.getVideoHostName(link)
                    url_with_meta = strwithmeta(link, {"Referer": cItem["url"]})
                    urlTab.append({"name": host_name, "url": url_with_meta, "need_resolve": 1})

        # Find direct video URLs
        video_urls = re.findall(r'file:\s*["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', data, re.IGNORECASE)
        for vurl in video_urls:
            if vurl and vurl not in seen_urls:
                seen_urls.add(vurl)
                url_with_meta = strwithmeta(vurl, {"Referer": cItem["url"]})
                urlTab.append({"name": "Direct Stream", "url": url_with_meta, "need_resolve": 1})

        if urlTab:
            # Add trailer if available
            trailer_match = re.search(r'(?:youtube\.com|youtu\.be)[^"\']*["\']', data)
            if trailer_match:
                trailer_url = re.search(r'(https?://[^"\']+youtu[^"\']+)', data)
                if trailer_url:
                    params = dict(cItem)
                    params.update({"good_for_fav": False, "url": trailer_url.group(1), "title": "Trailer: " + cItem["title"], "type": "video"})
                    self.addVideo(params)

            # Add main video sources
            params = dict(cItem)
            params.update({"good_for_fav": False, "urls_tab": urlTab})
            self.addVideo(params)
        else:
            printDBG("No video sources found for: %s" % cItem["title"])

    def getVideoHostName(self, url):
        url_lower = url.lower()
        if "vixsrc" in url_lower:
            return "VixSrc"
        elif "streamtape" in url_lower:
            return "StreamTape"
        elif "doodstream" in url_lower or "dood" in url_lower:
            return "DoodStream"
        elif "mp4upload" in url_lower:
            return "MP4Upload"
        elif "vidcloud" in url_lower:
            return "VidCloud"
        elif "voe" in url_lower:
            return "Voe"
        elif ".m3u8" in url_lower:
            return "HLS Stream"
        else:
            domain_match = re.search(r"https?://([^/]+)", url)
            if domain_match:
                return domain_match.group(1).split(".")[0].capitalize()
            return "Video Source"

    def getLinksForVideo(self, cItem):
        if cItem.get("url") and 1 == self.up.checkHostSupport(cItem["url"]):
            return self.up.getVideoLinkExt(cItem["url"])
        return cItem.get("urls_tab", [])

    def getVideoLinks(self, videoUrl):
        return self.up.getVideoLinkExt(videoUrl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        search_url = self.getFullUrl(f"search?q={searchPattern.replace(' ', '+')}")
        cItem = dict(cItem)
        cItem["url"] = search_url
        cItem["category"] = "list_items"
        self.listItems(cItem, "explore_item")

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")

        printDBG("handleService: name[%s], category[%s]" % (name, category))

        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop("good_for_fav", None)

        if name is None:
            self.listMainMenu({"name": "category", "type": "category"})
        elif category == "list_items":
            self.listItems(self.currItem, "explore_item")
        elif category == "explore_item":
            self.exploreItem(self.currItem)
        elif category == "sub_items":
            self.currList = self.currItem.get("sub_items", [])
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc", _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Altadefinizione(), True, favouriteTypes=[])

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "explore_item"
