# -*- coding: utf-8 -*-
# Modified: 09.06.2026 - passata
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
        self.DEFAULT_ICON_URL = self.MAIN_URL + "static/favicon.ico"

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

        main_menu = [{"title": "Home", "url": self.MAIN_URL, "category": "list_items"}, {"title": "Film", "url": self.MAIN_URL + "archive?type=movie", "category": "list_items"}, {"title": "Serie TV", "url": self.MAIN_URL + "archive?type=tv", "category": "list_items"}, {"title": "Archivio", "url": self.MAIN_URL + "archive", "category": "list_items"}, {"title": "Cerca", "url": "", "category": "search", "need_letters": False}]

        for item in main_menu:
            params = dict(cItem)
            params.update(item)
            self.addDir(params)

    def extractMoviesFromHTML(self, html, cItem):
        """Extract movie/TV items from HTML with full info"""
        items = []

        if not html:
            return items

        # Pattern for movie cards
        card_pattern = r'<a href="([^"]+)" class="movie-card">.*?<img[^>]+src="([^"]+)"[^>]*alt="([^"]+)".*?(?:<span class="label rate">([^<]+)</span>)?.*?<h6 class="movie-card-title">([^<]+)</h6>'

        matches = re.findall(card_pattern, html, re.DOTALL)

        for match in matches:
            url, img_src, alt_title, rating, h6_title = match
            title = alt_title if alt_title else h6_title

            if url and title:
                is_tv = "/tv-" in url or "/detail/tv-" in url

                # Build detailed description for main screen
                desc_parts = []
                if rating and rating.strip():
                    desc_parts.append("Rating: " + rating.strip())

                # Try to extract year from URL
                year_match = re.search(r"-(\d{4})(?:/|$)", url)
                if year_match:
                    desc_parts.append(year_match.group(1))

                desc_parts.append("Serie TV" if is_tv else "Film")

                desc = " | ".join(desc_parts) if desc_parts else title

                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "explore_item", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url), "icon": self.getFullIconUrl(img_src), "desc": desc, "is_tv": is_tv})
                items.append(params)

        return items

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
        if not sts or not data:
            printDBG("Failed to get page")
            return

        self.setMainUrl(self.cm.meta["url"])

        items = self.extractMoviesFromHTML(data, cItem)

        for item in items[:50]:
            self.addDir(item)

        # Check for next page
        next_match = re.search(r'<a href="([^"]*page=(\d+)[^"]*)"[^>]*class="page-link"[^>]*>(\d+|\»|Next)</a>', data, re.IGNORECASE)
        if next_match:
            next_page_num = int(next_match.group(2))
            if 1 < next_page_num <= 20:
                params = dict(cItem)
                params.update({"title": "Pagina %d" % next_page_num, "page": next_page_num, "url": cItem["url"]})
                self.addDir(params)

    def exploreItem(self, cItem):
        """Handle TV series or movie"""
        printDBG("Altadefinizione.exploreItem - %s" % cItem["title"])

        cItem["prev_url"] = cItem["url"]

        if cItem.get("is_tv", False) or "/tv-" in cItem.get("url", ""):
            self.getSeriesInfo(cItem)
        else:
            self.getVideoPlayer(cItem)

    def getSeriesInfo(self, cItem):
        """Get series info - seasons and episodes from the page"""
        printDBG("Altadefinizione.getSeriesInfo - %s" % cItem["url"])

        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("Failed to get series page")
            return

        # Extract TMDB ID
        tmdb_id = None
        tmdb_id_match = re.search(r"var tmdbID\s*=\s*(\d+);", data)
        if tmdb_id_match:
            tmdb_id = tmdb_id_match.group(1)
        else:
            tmdb_id_match = re.search(r"/tv-(\d+)-", cItem["url"])
            if tmdb_id_match:
                tmdb_id = tmdb_id_match.group(1)

        # Extract seasons from dropdown
        season_items = re.findall(r'<span[^>]*data-season="(\d+)"[^>]*>Stagione\s*\d+</span>', data, re.IGNORECASE)

        if season_items:
            for season_num in set(season_items):
                # Extract episodes for this season
                episodes = []
                episode_group = re.search(r'<div class="episode-group" data-group-season="%s">(.*?)</div>' % season_num, data, re.DOTALL)
                if episode_group:
                    eps = re.findall(r'data-episode="%s-(\d+)"' % season_num, episode_group.group(1))
                    episodes = [int(e) for e in eps]
                else:
                    eps = re.findall(r'data-episode="%s-(\d+)"' % season_num, data)
                    episodes = [int(e) for e in eps]

                if episodes:
                    params = dict(cItem)
                    params.update({"title": "Stagione %s" % season_num, "season": season_num, "tmdb_id": tmdb_id, "episodes": sorted(episodes), "category": "list_episodes", "icon": cItem.get("icon", self.DEFAULT_ICON_URL)})
                    self.addDir(params)
        else:
            # No seasons, try to get player directly
            self.getVideoPlayer(cItem)

    def listEpisodes(self, cItem):
        """List episodes for a specific season"""
        printDBG("Altadefinizione.listEpisodes - Season: %s" % cItem.get("season"))

        episodes = cItem.get("episodes", [])
        season_num = cItem.get("season", 1)
        tmdb_id = cItem.get("tmdb_id")

        if episodes:
            for ep_num in sorted(episodes):
                params = dict(cItem)
                params.update({"title": "Episodio %d" % ep_num, "season": season_num, "episode": ep_num, "tmdb_id": tmdb_id, "category": "play_video", "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": "%s - Episodio %d" % (cItem.get("title", ""), ep_num)})
                self.addDir(params)

    def getVideoPlayer(self, cItem):
        """Get video player URL and extract actual stream"""
        printDBG("Altadefinizione.getVideoPlayer - %s" % cItem.get("url"))

        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("Failed to get page")
            return

        player_base = "https://vixsrc.to"

        # Try to get TMDB ID from page
        tmdb_id = cItem.get("tmdb_id")
        if not tmdb_id:
            tmdb_match = re.search(r"var tmdbID\s*=\s*(\d+);", data)
            if tmdb_match:
                tmdb_id = tmdb_match.group(1)

        season = cItem.get("season")
        episode = cItem.get("episode")

        embed_url = None

        if tmdb_id and season and episode:
            embed_url = "%s/tv/%s/%s/%s?lang=it" % (player_base, tmdb_id, season, episode)
        elif tmdb_id:
            media_type = "movie"
            media_match = re.search(r'var mediaType\s*=\s*"([^"]+)"', data)
            if media_match:
                media_type = media_match.group(1)
            embed_url = "%s/%s/%s?lang=it" % (player_base, media_type, tmdb_id)
        else:
            iframe_match = re.search(r'<iframe[^>]+src="([^"]+vixsrc[^"]+)"', data, re.IGNORECASE)
            if iframe_match:
                embed_url = iframe_match.group(1)

        if embed_url:
            printDBG("Found VixSrc embed URL: %s" % embed_url)
            stream_url = self.extractVixSrcStream(embed_url, cItem["url"])
            if stream_url:
                urlTab = [{"name": "VixSrc Stream", "url": strwithmeta(stream_url, {"Referer": embed_url}), "need_resolve": 0}]
                params = dict(cItem)
                params.update({"good_for_fav": False, "urls_tab": urlTab})
                self.addVideo(params)
            else:
                if self.up.checkHostSupport(embed_url):
                    urlTab = [{"name": "VixSrc Player", "url": strwithmeta(embed_url, {"Referer": cItem["url"]}), "need_resolve": 1}]
                    params = dict(cItem)
                    params.update({"good_for_fav": False, "urls_tab": urlTab})
                    self.addVideo(params)
                else:
                    params = dict(cItem)
                    params.update({"title": "Apri nel browser", "url": embed_url, "category": "external", "type": "url"})
                    self.addDir(params)
        else:
            params = dict(cItem)
            params.update({"title": "Apri nel browser", "url": cItem["url"], "category": "external", "type": "url"})
            self.addDir(params)

    def extractVixSrcStream(self, embed_url, referer):
        """Extract m3u8 stream URL from VixSrc embed page"""
        printDBG("Extracting stream from: %s" % embed_url)

        try:
            headers = dict(self.HEADER)
            headers["Referer"] = referer
            headers["Origin"] = "https://vixsrc.to"

            params = dict(self.defaultParams)
            params["header"] = headers

            sts, data = self.getPage(embed_url, params)
            if not sts or not data:
                printDBG("Failed to get embed page")
                return None

            patterns = [
                r'(https?://[^\s"\']+\.m3u8[^\s"\']*)',
                r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)',
                r'src\s*:\s*["\']([^"\']+\.m3u8[^"\']*)',
                r'url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)',
                r'"file"\s*:\s*"([^"]+\.m3u8[^"]*)"',
                r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"',
                r"(https?://[^\s]+vix-content\.net[^\s]+\.m3u8[^\s]*)",
                r"(https?://[^\s]+\.vix-content\.net[^\s]+)",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, data, re.IGNORECASE)
                if matches:
                    stream_url = matches[0].strip()
                    if stream_url.startswith("//"):
                        stream_url = "https:" + stream_url
                    printDBG("Found stream URL: %s" % stream_url)
                    return stream_url

            video_sources = re.findall(r'<source[^>]+src="([^"]+)"', data, re.IGNORECASE)
            for src in video_sources:
                if ".m3u8" in src or ".mp4" in src:
                    printDBG("Found video source: %s" % src)
                    return src

            js_blocks = re.findall(r"<script[^>]*>([^<]+)</script>", data, re.DOTALL)
            for js in js_blocks:
                if "m3u8" in js.lower():
                    url_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', js, re.IGNORECASE)
                    if url_match:
                        return url_match.group(1)

            printDBG("No stream URL found in embed page")
            return None

        except Exception as e:
            printDBG("Error extracting VixSrc stream: %s" % str(e))
            return None

    def getArticleContent(self, cItem):
        """Extract movie/TV info for the info panel"""
        retTab = []

        url = cItem.get("prev_url", cItem.get("url", ""))
        if not url:
            return retTab

        sts, data = self.getPage(url)
        if not sts or not data:
            return retTab

        # Get title
        title = cItem.get("title", "")
        title_match = re.search(r"<h1[^>]*>([^<]+)</h1>", data)
        if title_match:
            title = self.cleanHtmlStr(title_match.group(1))

        # Get description
        desc = ""
        desc_match = re.search(r'<p class="detail-overview">([^<]+)</p>', data)
        if desc_match:
            desc = self.cleanHtmlStr(desc_match.group(1))
        if not desc:
            desc_match = re.search(r'<meta name="description" content="([^"]+)"', data)
            if desc_match:
                desc = self.cleanHtmlStr(desc_match.group(1))

        if not desc:
            desc = "Nessuna descrizione disponibile"

        if len(desc) > 500:
            desc = desc[:497] + "..."

        # Get rating
        rating_match = re.search(r'<span class="label rate">([^<]+)</span>', data)
        rating = rating_match.group(1) if rating_match else ""

        # Get year
        year_match = re.search(r'<span class="meta-item">(\d{4})</span>', data)
        year = year_match.group(1) if year_match else ""

        # Get genres
        genres = re.findall(r'<a href="[^"]*genre_id=\d+[^"]*"[^>]*>([^<]+)</a>', data)

        itemsList = []
        if rating:
            itemsList.append(("Voto", rating + "/10"))
        if year:
            itemsList.append(("Anno", year))
        if genres:
            itemsList.append(("Genere", ", ".join(genres[:3])))

        result = {"title": title, "text": desc, "images": [{"title": "", "url": cItem.get("icon", self.DEFAULT_ICON_URL)}], "other_info": {"custom_items_list": itemsList}}
        retTab.append(result)

        return retTab

    def getLinksForVideo(self, cItem):
        if cItem.get("url") and 1 == self.up.checkHostSupport(cItem["url"]):
            return self.up.getVideoLinkExt(cItem["url"])
        return cItem.get("urls_tab", [])

    def getVideoLinks(self, videoUrl):
        return self.up.getVideoLinkExt(videoUrl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Altadefinizione.listSearchResult - Pattern: %s" % searchPattern)
        if not searchPattern or len(searchPattern) < 2:
            return

        search_url = self.getFullUrl("/search?q=%s" % searchPattern.replace(" ", "+"))
        cItem = dict(cItem)
        cItem["url"] = search_url
        cItem["category"] = "list_items"
        self.listItems(cItem, "explore_item")

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")

        try:
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
            elif category == "list_episodes":
                self.listEpisodes(self.currItem)
            elif category == "play_video":
                self.getVideoPlayer(self.currItem)
            elif category == "external":
                self.addDir(self.currItem)
            elif category in ["search", "search_next_page"]:
                cItem = dict(self.currItem)
                cItem.update({"search_item": False, "name": "category"})
                self.listSearchResult(cItem, searchPattern, searchType)
            elif category == "search_history":
                self.listsHistory({"name": "history", "category": "search"}, "desc")
            else:
                printDBG("Unknown category: %s" % category)

        except Exception as e:
            printDBG("Error in handleService: %s" % str(e))
        finally:
            CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Altadefinizione(), True, favouriteTypes=[])

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ["explore_item", "list_episodes", "play_video"]
