# -*- coding: utf-8 -*-
# Last Modified: 27.09.2026
# Modified: 09.06.2026 - passata
# 27.09.2026 - paging past page 2, seasons in order, movies/episodes are playable rows (no extra folder),
# the player url goes straight to urlparser (parserVIXSRC), no "open in browser" dead end; Python 2 safe.
# Default icon = the bundled PNG logo instead of the site's favicon.ico (red X on the box). Domain alta-definizione.beer.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
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
    return "https://alta-definizione.beer/"


class Altadefinizione(CBaseHostClass):

    def __init__(self):
        # named after the host, not the domain: search history and cookies survive the next domain move
        CBaseHostClass.__init__(self, {"history": "altadefinizione01", "cookie": "altadefinizione01.cookie"})

        self.USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.HEADER = {"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest"})

        self.MAIN_URL = gettytul()
        # the site only has a 16x16 favicon.ico, which the box can't draw (red X on the categories) - use our own logo
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/altadefinizione01135.png")

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
                params.pop("page", None)
                params.update({"good_for_fav": True, "category": "explore_item" if is_tv else "video", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url), "icon": self.getFullIconUrl(img_src), "desc": desc, "is_tv": is_tv})
                items.append(params)

        return items

    def listItems(self, cItem, nextCategory):
        printDBG("Altadefinizione.listItems - URL: %s" % cItem["url"])
        page = cItem.get("page", 1)

        url = cItem["url"]
        if page > 1:
            if "page=" in url:
                url = re.sub(r"page=\d+", "page=%d" % page, url)
            else:
                url += ("&" if "?" in url else "?") + "page=%d" % page

        sts, data = self.getPage(url)
        if not sts or not data:
            printDBG("Failed to get page")
            return

        self.setMainUrl(self.cm.meta["url"])

        for item in self.extractMoviesFromHTML(data, cItem)[:50]:
            if item["is_tv"]:
                self.addDir(item)
            else:
                self.addVideo(item)

        # next page: the pagination bar links every page ("<", 1, 3, 4 ...) - look for page + 1, not the first link
        pages = [int(n) for n in re.findall(r'<a href="[^"]*[?&]page=(\d+)[^"]*"[^>]*class="page-link"', data)]
        if page + 1 in pages:
            params = dict(cItem)
            params.update({"title": _("Next page"), "page": page + 1, "url": cItem["url"]})
            self.addDir(params)

    def exploreItem(self, cItem):
        """series -> seasons; a movie (e.g. an old favourite of the former movie folder) -> its playable row"""
        printDBG("Altadefinizione.exploreItem - %s" % cItem["title"])

        cItem["prev_url"] = cItem["url"]

        if cItem.get("is_tv", False) or "/tv-" in cItem.get("url", ""):
            self.getSeriesInfo(cItem)
        else:
            params = dict(cItem)
            params["category"] = "video"
            self.addVideo(params)

    def getSeriesInfo(self, cItem):
        """Get series info - seasons and episodes from the page"""
        printDBG("Altadefinizione.getSeriesInfo - %s" % cItem["url"])

        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            printDBG("Failed to get series page")
            return

        tmdb_id = self._tmdbId(data, cItem["url"])

        # seasons from the dropdown, in their real order (1, 2, 3 ... not set() order)
        season_items = re.findall(r'<span[^>]*data-season="(\d+)"[^>]*>Stagione\s*\d+</span>', data, re.IGNORECASE)
        seasons = sorted(set(season_items), key=int)

        for season_num in seasons:
            episode_group = re.search(r'<div class="episode-group" data-group-season="%s">(.*?)</div>' % season_num, data, re.DOTALL)
            eps = re.findall(r'data-episode="%s-(\d+)"' % season_num, episode_group.group(1) if episode_group else data)
            episodes = sorted(set(int(e) for e in eps))
            if episodes:
                params = dict(cItem)
                params.update({"title": "Stagione %s" % season_num, "season": season_num, "tmdb_id": tmdb_id, "episodes": episodes, "category": "list_episodes", "icon": cItem.get("icon", self.DEFAULT_ICON_URL)})
                self.addDir(params)

        if not seasons:
            # no season list on the page: play it like a movie
            params = dict(cItem)
            params.update({"category": "video", "tmdb_id": tmdb_id})
            self.addVideo(params)

    def listEpisodes(self, cItem):
        """episodes of a season, directly playable"""
        printDBG("Altadefinizione.listEpisodes - Season: %s" % cItem.get("season"))

        season_num = cItem.get("season", 1)
        for ep_num in sorted(cItem.get("episodes", [])):
            params = dict(cItem)
            params.pop("episodes", None)
            params.update({"good_for_fav": True, "title": "Episodio %d" % ep_num, "season": season_num, "episode": ep_num, "category": "video", "icon": cItem.get("icon", self.DEFAULT_ICON_URL), "desc": "%s - Stagione %s - Episodio %d" % (cItem.get("title", ""), season_num, ep_num)})
            self.addVideo(params)

    def _tmdbId(self, data, url=""):
        match = re.search(r"var tmdbID\s*=\s*(\d+)\s*;", data)
        if match:
            return match.group(1)
        match = re.search(r"/tv-(\d+)-", url)
        return match.group(1) if match else None

    def getPlayerUrl(self, cItem):
        """vixsrc.to embed url of a movie / episode, or '' (the page's tmdbID + mediaType, like its own player script)"""
        tmdb_id = cItem.get("tmdb_id")
        season = cItem.get("season")
        episode = cItem.get("episode")
        if tmdb_id and season and episode:
            return "https://vixsrc.to/tv/%s/%s/%s?lang=it" % (tmdb_id, season, episode)

        sts, data = self.getPage(cItem["url"])
        if not sts or not data:
            return ""
        tmdb_id = self._tmdbId(data)
        if tmdb_id:
            media_match = re.search(r'var mediaType\s*=\s*"([^"]+)"', data)
            return "https://vixsrc.to/%s/%s?lang=it" % (media_match.group(1) if media_match else "movie", tmdb_id)
        iframe_match = re.search(r'<iframe[^>]+src="([^"]+vixsrc[^"]+)"', data, re.IGNORECASE)
        return iframe_match.group(1) if iframe_match else ""

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
        printDBG("Altadefinizione.getLinksForVideo [%s]" % cItem.get("url"))
        embed_url = self.getPlayerUrl(cItem)
        if not embed_url:
            SetIPTVPlayerLastHostError(_("No player found for this title."))
            return []
        # resolved by urlparser (parserVIXSRC: token playlist, audio/video variants)
        return [{"name": "VixSrc", "url": strwithmeta(embed_url, {"Referer": cItem["url"]}), "need_resolve": 1}]

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
            elif category in ("play_video", "video"):
                # rows from before 27.09.2026 (episode folders, favourites) - now the playable row itself
                params = dict(self.currItem)
                params["category"] = "video"
                self.addVideo(params)
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
        return cItem.get("category", "") in ["explore_item", "list_episodes", "play_video", "video"]
