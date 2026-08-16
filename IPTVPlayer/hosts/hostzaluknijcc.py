# -*- coding: utf-8 -*-
# Last Modified: 29.06.2026 - damagic
###################################################
import re
import json
import base64
import time
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Components.config import config, getConfigListEntry

try:
    import json
except Exception:
    import simplejson as json

# Regex patterns used across multiple methods
RE_DESCRIPTION_PARAGRAPH = r'<p\s+class="description">([^<]+)'
RE_META_DESCRIPTION = r'<meta\s+name="description"\s+content="([^"]+)'
RE_NEXT_PAGE = r"""href=['"]([^"']+)["'](?: data-pagenumber='\d+'>|>)Nast"""
RE_ITEM_TITLE = r'title="([^"]+)'
RE_ITEM_HREF = r'href="([^"]+)'
RE_ITEM_IMAGE = r'src="([^"]+)'
RE_META_LINE = r'<span class="meta-line">(S\d+\s*E\d+)</span>'
RE_YEAR_SUP = r'<sup><a href="[^"]+">(\d{4})</a></sup>'
RE_YEAR_CLASS = r'class="year">(\d{4})'
RE_YEAR_PRODUCTION = r'<li>Rok\s+Produkcji:</li>\s*<li>(\d{4})</li>'
RE_GENRE_ITEMPROP = r'<li itemprop="genre"><a href="[^"]+">([^<]+)</a></li>'
RE_IFRAME_DATA = r"""data-iframe=['"]([^"^']+?)['"]"""
RE_HREF_LINK = r"""href=['"]([^"^']+?)['"]"""
RE_EPISODE_LINK = r'href="([^"]+)">\W(s\d+e\d+)'
RE_CLEAN_TITLE = r"\s*\[\]\s*"
RE_DESCRIPTION_FALLBACK = r'class="description">([^<]+)'
RE_ALT_TITLE = r'alt="([^"]+)'
RE_DIV_TITLE = r'<div\s+class="title">([^<]+)'


def GetConfigList():
    """Return configuration options for the plugin."""
    optionList = []
    return optionList


def gettytul():
    """Return the base URL for the Zaluknij service."""
    return "https://zaluknij.cc/"


class Zaluknij(CBaseHostClass):
    """
    Parser for Zaluknij.cc video hosting service.

    Features:
    - Browse movies by premiere, new links, and ratings
    - Browse TV series with episode listing
    - Search functionality with POST/GET fallback
    - Cloudflare protection handling
    - Multiple video quality and version support
    """

    def __init__(self):
        """Initialize the parser with default settings and menu structure."""
        CBaseHostClass.__init__(
            self, {"history": "Zaluknij", "cookie": "Zaluknij.cookie"}
        )
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        try:
            self.HEADER["User-Agent"] = config.plugins.iptvplayer.cloudflare_user.value
        except AttributeError:
            self.HEADER["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0"
            )
        self.defaultParams = {
            "header": self.HEADER,
            "use_cookie": True,
            "load_cookie": True,
            "save_cookie": True,
            "cookiefile": self.COOKIE_FILE,
            "with_metadata": True,
        }
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.fixIconUrl(
            self.MAIN_URL + "public/dist/images/lgbt.png", self.MAIN_URL
        )
        self.cacheLinks = {}
        self.cacheDescriptions = {}
        self.cacheDetails = {}
        self.cacheQuickDescs = {}
        self.MENU = [
            {
                "category": "list_items",
                "title": "Filmy Premiery",
                "url": self.getFullUrl("filmy-online/sort:premiere/"),
            },
            {
                "category": "list_items",
                "title": "Filmy Nowe Linki",
                "url": self.getFullUrl("filmy-online/sort:link/"),
            },
            {
                "category": "list_items",
                "title": "Filmy Oceny na Zaluknij",
                "url": self.getFullUrl("filmy-online/sort:rate/"),
            },
            {
                "category": "list_items",
                "title": "Seriale",
                "url": self.getFullUrl(
                    "seriale-online/index?url=seriale-online%2Findex"
                    "&sort=recent_series&page=1"
                ),
            },
            {
                "category": "list_episodes_direct",
                "title": "Seriale Nowe Odcinki",
                "url": self.getFullUrl(
                    "seriale-online/index?url=seriale-online%2Findex"
                    "&sort=latest_episodes&page=1"
                ),
            },
            {
                "category": "list_items",
                "title": "Dla dzieci",
                "url": self.getFullUrl("dla-dzieci/"),
            },
        ] + self.searchItems()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        """
        Fetch page content with Cloudflare protection support.

        Args:
            baseUrl: The URL to fetch
            addParams: Additional parameters for the request
            post_data: POST data if using POST method

        Returns:
            Tuple of (status, response_data)
        """
        if addParams is None:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(baseUrl)
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        # Check if Cloudflare user agent changed and reinitialize if needed
        if data.meta.get("cf_user", self.HEADER["User-Agent"]) != self.HEADER["User-Agent"]:
            self.__init__()
        return sts, data

    def fixIconUrl(self, icon_url, referer=None):
        """
        Fix icon URL with proper metadata and Cloudflare cookies.

        Args:
            icon_url: Raw icon URL from the page
            referer: Referer URL for the request header

        Returns:
            strwithmeta object with proper headers
        """
        if not icon_url:
            return ""
        if "thumb" in icon_url:
            icon_url = icon_url.replace("thumb", "big")
        icon_url = self.getFullUrl(icon_url)
        cf = self.cm.getCookieItem(self.COOKIE_FILE, "cf_clearance")
        return strwithmeta(
            icon_url,
            {
                "Referer": referer if referer else self.MAIN_URL,
                "User-Agent": self.HEADER["User-Agent"],
                "Cookie": "cf_clearance=%s" % cf if cf else "",
            },
        )

    def getQuickDescription(self, url):
        """
        Get a short description for a video from cache or fetch it.

        Args:
            url: The video page URL

        Returns:
            Description text string (max 200 characters)
        """
        if url in self.cacheQuickDescs:
            return self.cacheQuickDescs[url]
        try:
            sts, data = self.getPage(url)
            if not sts:
                self.cacheQuickDescs[url] = ""
                return ""
            # Try to extract description from paragraph tag
            desc = self.cm.ph.getSearchGroups(
                data, RE_DESCRIPTION_PARAGRAPH
            )
            # Fallback to meta description tag
            if not desc:
                desc = self.cm.ph.getSearchGroups(
                    data, RE_META_DESCRIPTION
                )
            if desc:
                desc_text = self.cleanHtmlStr(desc[0]).strip()
                if len(desc_text) > 200:
                    desc_text = desc_text[:200] + "..."
            else:
                desc_text = ""
            self.cacheQuickDescs[url] = desc_text
            self.cacheDescriptions[url] = desc_text
            return desc_text
        except Exception as e:
            printDBG("getQuickDescription error: %s" % str(e))
            self.cacheQuickDescs[url] = ""
            return ""

    def extractMovieDetails(self, data):
        """
        Extract movie metadata from the page HTML.

        Parses year, categories, versions and quality information
        from the movie details page.

        Args:
            data: HTML content of the movie page

        Returns:
            Dictionary with keys: categories, version, quality, year
        """
        details = {"categories": [], "version": "", "quality": "", "year": ""}
        # Extract release year from superscript link (movies)
        year = self.cm.ph.getSearchGroups(data, RE_YEAR_SUP)
        printDBG("extractMovieDetails RE_YEAR_SUP result: %s" % str(year))
        if year and year[0].isdigit():
            details["year"] = year[0]
        else:
            # Extract year from production info (series)
            year = self.cm.ph.getSearchGroups(data, RE_YEAR_PRODUCTION)
            printDBG("extractMovieDetails RE_YEAR_PRODUCTION result: %s" % str(year))
            if year:
                details["year"] = year[0]
        printDBG("extractMovieDetails final year: %s" % details["year"])
        # Extract genre categories using itemprop attribute
        categories = re.findall(RE_GENRE_ITEMPROP, data)
        if categories:
            details["categories"] = categories
        # Parse the versions table for quality and version info
        table_parts = self.cm.ph.getDataBeetwenNodes(
            data, ("<table", ">"), ("</table", ">")
        )
        if table_parts and len(table_parts) > 1:
            table = table_parts[1]
            rows = self.cm.ph.getAllItemsBeetwenNodes(
                table, ("<tr", ">"), ("</tr", ">")
            )
            versions = set()
            qualities = set()
            for row in rows:
                # Skip header rows
                if "<th" in row:
                    continue
                cells = self.cm.ph.getAllItemsBeetwenNodes(
                    row, ("<td", ">"), ("</td", ">")
                )
                if len(cells) >= 4:
                    # Check if cell contains video link
                    if "link-to-video" in cells[1]:
                        if len(cells) > 2:
                            version = self.cleanHtmlStr(cells[2])
                            if version and version not in ["", "Wersja"]:
                                versions.add(version)
                        if len(cells) > 3:
                            quality = self.cleanHtmlStr(cells[3])
                            if quality and quality not in ["", "Jakość"]:
                                qualities.add(quality)
            if versions:
                details["version"] = ", ".join(sorted(versions))
            if qualities:
                details["quality"] = ", ".join(sorted(qualities))
        return details

    def getArticleContent(self, cItem):
        """
        Build article content with movie details and description.

        Used for displaying detailed information about a movie.

        Args:
            cItem: Current item dictionary with url, title, icon

        Returns:
            List of dictionaries with title, text, images and other_info
        """
        printDBG("Zaluknij.getArticleContent [%s]" % cItem)
        url = cItem.get("url", "")
        title = cItem.get("title", "")
        icon = cItem.get("icon", self.DEFAULT_ICON_URL)
        if not url:
            return []
        details = {}
        if url in self.cacheDetails:
            details = self.cacheDetails[url]
            desc = self.cacheDescriptions.get(url, "")
        else:
            sts, data = self.getPage(url)
            if sts:
                # Extract description from the page
                desc = self.cm.ph.getSearchGroups(
                    data, RE_DESCRIPTION_PARAGRAPH
                )
                if not desc:
                    desc = self.cm.ph.getSearchGroups(
                        data, RE_META_DESCRIPTION
                    )
                if desc:
                    desc_text = self.cleanHtmlStr(desc[0])
                    self.cacheDescriptions[url] = desc_text
                else:
                    desc_text = ""
                details = self.extractMovieDetails(data)
                self.cacheDetails[url] = details
            else:
                desc_text = ""
        # Build the display text with all available metadata
        text_parts = []
        text_parts.append(title)
        text_parts.append("")
        if details.get("year"):
            text_parts.append("Rok: %s" % details["year"])
        if details.get("categories"):
            text_parts.append("Kategoria: %s" % ", ".join(details["categories"]))
        if details.get("version"):
            text_parts.append("Wersja: %s" % details["version"])
        if details.get("quality"):
            text_parts.append("Jakość: %s" % details["quality"])
        desc_text = self.cacheDescriptions.get(url, "")
        if desc_text:
            text_parts.append("")
            text_parts.append("Opis:")
            text_parts.append(desc_text)
        if not desc_text and not details:
            text_parts.append("")
            text_parts.append("Brak opisu i szczegółów")
        final_text = "\n".join(text_parts)
        return [
            {
                "title": title,
                "text": final_text,
                "images": [{"title": "", "url": icon}],
                "other_info": {"custom_items_list": []},
            }
        ]

    def listItems(self, cItem, isSearch=False):
        """
        List movies and series from a category page with descriptions.

        Parses the page for video items and adds them with quick descriptions
        to improve user experience when browsing content.

        Args:
            cItem: Current item with url to parse
            isSearch: Flag indicating if this is a search result
        """
        printDBG("Zaluknij.listItems |%s| isSearch=%s" % (cItem, isSearch))
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            printDBG("Zaluknij.listItems - failed to get page after retries")
            return
        # Find next page link if available
        nextPage = self.cm.ph.getSearchGroups(htm, RE_NEXT_PAGE)
        if nextPage:
            nextPage = nextPage[0]
        # Extract video items from the page using multiple patterns
        data = self.cm.ph.getAllItemsBeetwenMarkers(
            htm, 'role="listitem', "</a>"
        ) or self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-sm-4">', "</a>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, RE_ITEM_HREF)
            if not url:
                continue
            url = url[0]
            # Extract and fix thumbnail icon
            icon = self.cm.ph.getSearchGroups(item, RE_ITEM_IMAGE)
            if icon:
                icon = self.fixIconUrl(icon[0], cItem["url"])
                if isSearch:
                    icon = self.fixIconUrl(icon)
            else:
                icon = self.DEFAULT_ICON_URL
            # Extract title from the item
            title = self.cm.ph.getSearchGroups(item, RE_ITEM_TITLE)
            if not title:
                title = self.cm.ph.getSearchGroups(item, RE_ALT_TITLE)
            if title:
                title = self.cleanHtmlStr(title[0])
            else:
                title = "Brak tytułu"
            title = re.sub(RE_CLEAN_TITLE, "", title)
            # Determine if this is a series and add episode info if available
            is_serial = "serial" in url.lower()
            if is_serial:
                meta_line = self.cm.ph.getSearchGroups(item, RE_META_LINE)
                if meta_line:
                    meta_line = self.cleanHtmlStr(meta_line[0])
                    title = "%s [%s]" % (title, meta_line)
            else:
                year = self.cm.ph.getSearchGroups(item, RE_YEAR_CLASS)
                if year:
                    year = year[0]
                    if not isSearch:
                        title = "%s (%s)" % (title, year)
            title = re.sub(RE_CLEAN_TITLE, "", title)
            title = title.strip()
            # Get quick description for the item
            quick_desc = self.getQuickDescription(url)
            # Also try to extract description directly from the item HTML
            if not quick_desc:
                item_desc = self.cm.ph.getSearchGroups(
                    item, r'<p[^>]*>([^<]+)</p>'
                )
                if item_desc:
                    quick_desc = self.cleanHtmlStr(item_desc[0]).strip()
                    if len(quick_desc) > 200:
                        quick_desc = quick_desc[:200] + "..."
            # Prepare item parameters with description
            params = dict(cItem)
            params.update(
                {
                    "good_for_fav": True,
                    "category": "video",
                    "title": title.replace("amp;", ""),
                    "url": url,
                    "icon": icon,
                    "desc": quick_desc,
                }
            )
            if is_serial:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)
        # Add next page navigation if available
        if nextPage:
            params = dict(cItem)
            next_url = cItem["url"].split("?")[0] + nextPage.replace("amp;", "")
            params.update(
                {"good_for_fav": False, "title": _("Next page"), "url": next_url}
            )
            self.addDir(params)

    def listEpisodes(self, cItem):
        """
        List all episodes for a TV series.

        Extracts season and episode numbers from the series page
        and adds them as individual video items.

        Args:
            cItem: Current item with series URL
        """
        printDBG("Zaluknij.listEpisodes")
        icon = cItem["icon"]
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        # Get series description if available
        desc = self.cm.ph.getSearchGroups(data, RE_DESCRIPTION_FALLBACK)
        if desc:
            desc = desc[0]
        else:
            desc = ""
        # Find all episode links with season/episode patterns
        episodes = re.findall(RE_EPISODE_LINK, data, re.DOTALL)
        for url, episode_num in episodes:
            params = dict(cItem)
            title = cItem["title"]
            title = re.sub(RE_CLEAN_TITLE, "", title)
            title = title.strip()
            params.update(
                {
                    "good_for_fav": True,
                    "title": "%s [%s]" % (title, episode_num.upper()),
                    "url": self.getFullUrl(url),
                    "icon": icon,
                    "desc": desc,
                }
            )
            self.addVideo(params)

    def listEpisodesDirect(self, cItem):
        """
        List latest episodes directly with pagination support.

        Similar to listItems but specifically for new episodes
        with season/episode metadata in the title.

        Args:
            cItem: Current item with episodes listing URL
        """
        printDBG("Zaluknij.listEpisodesDirect |%s|" % cItem)
        sts, htm = self.getPage(cItem["url"])
        if not sts:
            return
        # Find next page link
        nextPage = self.cm.ph.getSearchGroups(htm, RE_NEXT_PAGE)
        if nextPage:
            nextPage = nextPage[0]
        # Extract video items from the page
        data = self.cm.ph.getAllItemsBeetwenMarkers(
            htm, 'role="listitem', "</a>"
        ) or self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-sm-4">', "</a>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, RE_ITEM_HREF)
            if not url:
                continue
            url = url[0]
            icon = self.cm.ph.getSearchGroups(item, RE_ITEM_IMAGE)
            if icon:
                icon = self.fixIconUrl(icon[0], cItem["url"])
            else:
                icon = self.DEFAULT_ICON_URL
            # Extract title from alt attribute of img or from title div
            title = self.cm.ph.getSearchGroups(item, RE_ALT_TITLE)
            if not title:
                title = self.cm.ph.getSearchGroups(item, RE_DIV_TITLE)
            if title:
                title = self.cleanHtmlStr(title[0])
                # Get only the Polish title (before first slash if multiple titles)
                if "/" in title:
                    title = title.split("/")[0].strip()
            else:
                title = "Brak tytułu"
            title = re.sub(RE_CLEAN_TITLE, "", title)
            # Add season/episode info if available
            meta_line = self.cm.ph.getSearchGroups(item, RE_META_LINE)
            if meta_line:
                meta_line = self.cleanHtmlStr(meta_line[0])
                title = "%s [%s]" % (title, meta_line)
            title = re.sub(RE_CLEAN_TITLE, "", title)
            title = title.strip()
            quick_desc = self.getQuickDescription(url)
            params = dict(cItem)
            params.update(
                {
                    "good_for_fav": True,
                    "category": "video",
                    "title": title.replace("amp;", ""),
                    "url": url,
                    "icon": icon,
                    "desc": quick_desc,
                }
            )
            self.addVideo(params)
        # Add next page if available
        if nextPage:
            params = dict(cItem)
            next_url = cItem["url"].split("?")[0] + nextPage.replace("amp;", "")
            params.update(
                {"good_for_fav": False, "title": _("Next page"), "url": next_url}
            )
            self.addDir(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        """
        Handle search functionality with POST and GET fallback.

        Displays search results with descriptions for better user experience.
        First attempts POST search, falls back to GET if POST fails.

        Args:
            cItem: Current item context
            searchPattern: The search query string
            searchType: Type of search being performed
        """
        printDBG(
            "Zaluknij.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]"
            % (cItem, searchPattern, searchType)
        )
        cItem = dict(cItem)
        search_url = "%sszukaj" % gettytul()
        post_data = "phrase=%s" % urllib_quote(searchPattern)
        printDBG("Zaluknij.listSearchResult - using POST to: %s" % search_url)
        sts, htm = self.getPage(search_url, post_data=post_data)
        if not sts:
            printDBG("Zaluknij.listSearchResult - POST failed, trying GET fallback")
            cItem["url"] = "%swyszukiwarka?phrase=%s" % (
                gettytul(),
                urllib_quote(searchPattern),
            )
            self.listItems(cItem, isSearch=True)
            return
        # Parse search results same as regular listing
        nextPage = self.cm.ph.getSearchGroups(htm, RE_NEXT_PAGE)
        if nextPage:
            nextPage = nextPage[0]
        data = self.cm.ph.getAllItemsBeetwenMarkers(
            htm, 'role="listitem', "</a>"
        ) or self.cm.ph.getAllItemsBeetwenMarkers(htm, 'class="col-sm-4">', "</a>")
        for item in data:
            url = self.cm.ph.getSearchGroups(item, RE_ITEM_HREF)
            if not url:
                continue
            url = url[0]
            icon = self.cm.ph.getSearchGroups(item, RE_ITEM_IMAGE)
            if icon:
                icon = self.fixIconUrl(icon[0], cItem["url"])
                icon = self.fixIconUrl(icon)
            else:
                icon = self.DEFAULT_ICON_URL
            title = self.cm.ph.getSearchGroups(item, RE_ITEM_TITLE)
            if not title:
                title = self.cm.ph.getSearchGroups(item, RE_ALT_TITLE)
            if title:
                title = self.cleanHtmlStr(title[0])
            else:
                title = "Brak tytułu"
            title = re.sub(RE_CLEAN_TITLE, "", title)
            is_serial = "serial" in url.lower()
            if is_serial:
                meta_line = self.cm.ph.getSearchGroups(item, RE_META_LINE)
                if meta_line:
                    meta_line = self.cleanHtmlStr(meta_line[0])
                    title = "%s [%s]" % (title, meta_line)
            title = re.sub(RE_CLEAN_TITLE, "", title)
            title = title.strip()
            # Get description for search results
            quick_desc = self.getQuickDescription(url)
            if not quick_desc:
                # Try to get description from search result snippet
                item_desc = self.cm.ph.getSearchGroups(
                    item, r'<p[^>]*>([^<]+)</p>'
                )
                if item_desc:
                    quick_desc = self.cleanHtmlStr(item_desc[0]).strip()
                    if len(quick_desc) > 200:
                        quick_desc = quick_desc[:200] + "..."
            params = dict(cItem)
            params.update(
                {
                    "good_for_fav": True,
                    "category": "video",
                    "title": title.replace("amp;", ""),
                    "url": url,
                    "icon": icon,
                    "desc": quick_desc,
                }
            )
            if is_serial:
                params.update({"category": "list_episodes"})
                self.addDir(params)
            else:
                self.addVideo(params)
        if nextPage:
            params = dict(cItem)
            next_url = "%sszukaj?page=%s" % (gettytul(), nextPage)
            params.update(
                {"good_for_fav": False, "title": _("Next page"), "url": next_url}
            )
            self.addDir(params)

    def getLinksForVideo(self, cItem):
        """
        Extract video playback links from the movie/episode page.

        Handles both iframe-embedded links (base64 encoded JSON)
        and direct href links with version and quality metadata.

        Args:
            cItem: Current item with video page URL

        Returns:
            List of dictionaries with name, url and need_resolve flag
        """
        printDBG("Zaluknij.getLinksForVideo [%s]" % cItem)
        cacheKey = cItem["url"]
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab
        retTab = []
        url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return []
        # Cache the description for later use
        desc = self.cm.ph.getSearchGroups(data, RE_DESCRIPTION_PARAGRAPH)
        if desc:
            self.cacheDescriptions[url] = self.cleanHtmlStr(desc[0])
        # Find the link list container
        link_list_div = ""
        link_list_parts = self.cm.ph.getDataBeetwenNodes(
            data, ("<div", ">", "link-list"), ("</div", ">")
        )
        if link_list_parts and len(link_list_parts) > 1:
            link_list_div = link_list_parts[1]
        if not link_list_div:
            link_list_div = data
        # Parse the versions table for video links
        table_parts = self.cm.ph.getDataBeetwenNodes(
            link_list_div, ("<table", ">"), ("</table", ">")
        )
        if table_parts and len(table_parts) > 1:
            table = table_parts[1]
            rows = self.cm.ph.getAllItemsBeetwenNodes(
                table, ("<tr", ">"), ("</tr", ">")
            )
            for row in rows:
                if "<th" in row:
                    continue
                cells = self.cm.ph.getAllItemsBeetwenNodes(
                    row, ("<td", ">"), ("</td", ">")
                )
                if len(cells) < 2:
                    continue
                player_url = ""
                version = ""
                quality = ""
                for idx, cell in enumerate(cells):
                    if "link-to-video" in cell:
                        # Try to decode base64 encoded iframe data
                        iframe_match = re.search(RE_IFRAME_DATA, cell)
                        if iframe_match:
                            try:
                                decoded = base64.b64decode(
                                    iframe_match.group(1)
                                ).decode("utf-8")
                                iframe_data = json.loads(decoded)
                                player_url = iframe_data.get("src", "")
                            except Exception as e:
                                printDBG("iframe decode error: %s" % str(e))
                        # Fallback to direct href link
                        if not player_url:
                            href_match = re.search(RE_HREF_LINK, cell)
                            if href_match:
                                player_url = href_match.group(1)
                    elif idx == 2:
                        version = self.cleanHtmlStr(cell)
                    elif idx == 3:
                        quality = self.cleanHtmlStr(cell)
                if not player_url:
                    continue
                if player_url and not player_url.startswith("http"):
                    player_url = self.getFullUrl(player_url)
                # Build descriptive name with version and quality info
                hostname = self.up.getHostName(player_url)
                name = hostname.split(".")[0] if "." in hostname else hostname
                if version and version not in ["", "Wersja"]:
                    name += " [%s" % version
                    if quality and quality not in ["", "Jakość"]:
                        name += " / %s" % quality
                    name += "]"
                elif quality and quality not in ["", "Jakość"]:
                    name += " [%s]" % quality
                retTab.append(
                    {
                        "name": name,
                        "url": strwithmeta(player_url, {"Referer": url}),
                        "need_resolve": 1,
                    }
                )
        # Fallback: look for direct links if table parsing failed
        if not retTab:
            data_links = self.cm.ph.getAllItemsBeetwenMarkers(
                data, 'link-to-video">', "None"
            )
            for item in data_links:
                url_match = re.search(r'href="([^"]+)', item)
                if url_match:
                    video_url = url_match.group(1)
                    hostname = self.up.getHostName(video_url)
                    short_name = (
                        hostname.split(".")[0] if "." in hostname else hostname
                    )
                    retTab.append(
                        {
                            "name": short_name.capitalize(),
                            "url": strwithmeta(video_url, {"Referer": gettytul()}),
                            "need_resolve": 1,
                        }
                    )
        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, url):
        """
        Resolve video URL and mark cached links as used.

        Args:
            url: The video URL to resolve

        Returns:
            Resolved video link from the appropriate parser
        """
        printDBG("Zaluknij.getVideourls [%s]" % url)
        url = strwithmeta(url)
        # Mark used links with asterisks in cache
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if url in self.cacheLinks[key][idx]["url"]:
                        if not self.cacheLinks[key][idx]["name"].startswith("*"):
                            self.cacheLinks[key][idx]["name"] = (
                                "*" + self.cacheLinks[key][idx]["name"] + "*"
                            )
                        break
        return self.up.getVideoLinkExt(url)

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        """
        Main service handler - routes requests to appropriate methods.

        Handles menu navigation, item listing, episode listing,
        search functionality and search history.

        Args:
            index: Current menu index
            refresh: Refresh flag
            searchPattern: Search query string
            searchType: Type of search
        """
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG(
            "handleService: |||||||||||||||||||||||||||||||||||| "
            "name[%s], category[%s] " % (name, category)
        )
        self.currList = []
        # Route to appropriate handler based on category
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem, isSearch=False)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category == "list_episodes_direct":
            self.listEpisodesDirect(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory(
                {"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    """IPTVPlayer host class for Zaluknij.cc integration."""

    def __init__(self):
        CHostBase.__init__(self, Zaluknij(), True, [])

    def withArticleContent(self, cItem):
        """Enable article content display for detailed descriptions."""
        return True
