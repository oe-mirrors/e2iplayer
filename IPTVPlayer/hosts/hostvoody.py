# -*- coding: utf-8 -*-
LAST_MODIFIED = "28.10.2026"
# 28.10.2026 - new host
#   voody-online.com (DLE, films / series / cartoons with Greek subtitles): lists with First / Jump / Next page,
#   categories from the site menu, search; streams through the coverapi.store player (urlparser parserCOVERAPI),
#   series seasons / episodes from its playlist
import base64
import json
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, getMetaByImdbId, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.voody_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.voody_alt_domain)]


def gettytul():
    return "https://voody-online.com/"


# results per page of the site search (DLE search_start)
SEARCH_PAGE_SIZE = 20


def _mainUrl():
    domain = config.plugins.iptvplayer.voody_alt_domain.value.strip()
    if re.match(r"^https?://[^/\s]+", domain):
        return domain.rstrip("/") + "/"
    return gettytul()


class Voody(GenericFolderWatchedScraperMixin, CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "voody", "cookie": "voody.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.seasonsCache = {}
        self.missingEmbeds = set()  # coverapi players that answer 404 (no stream for the title)
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/voody135.png")
        self.MAIN_URL = _mainUrl()
        self.MENU = [{"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/load/")},
                     {"category": "list_items", "title": _("Recommended"), "url": self.getFullUrl("/load/top_250_movies/")},
                     {"category": "list_items", "title": _("Series"), "url": self.getFullUrl("/load/seir/")},
                     {"category": "list_items", "title": _("Cartoons"), "url": self.getFullUrl("/load/kino_mena_sch_dia/")},
                     {"category": "list_items", "title": _("Kids"), "url": self.getFullUrl("/load/metaglwtism_na_paidik_online/")},
                     {"category": "list_cats", "title": _("Categories"), "url": self.MAIN_URL}] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("voody")
        self.wfInitFolderCache()

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        url = baseUrl.split("#", 1)[0]
        if self.MAIN_URL != gettytul() and url.startswith(gettytul()):
            # a favourite of the default domain while the alternative one is set
            url = self.MAIN_URL + url[len(gettytul()):]
        return self.cm.getPageCFProtection(url, addParams, post_data)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {"video": "video", "list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            url = re.sub(r"^https?://[^/]+", "", str(cItem.get("url", "") or "").strip())
            if prefix == "season":
                url = "%s#s%s" % (url.split("#", 1)[0], cItem.get("s_season", ""))
            return "%s:%s" % (prefix, url) if (prefix and url) else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # helpers
    ###################################################
    @staticmethod
    def _splitTitle(title):
        # "Η Κούκλα / The Doll (2026)" -> ("Η Κούκλα / The Doll", "2026", "The Doll"): base title, year, title for moviemeta
        year = ""
        m = re.search(r"\(\s*((?:19|20)\d\d)[^)]*\)\s*$", title)
        if m:
            year = m.group(1)
            title = title[:m.start()].strip()
        metaTitle = title
        for part in title.split(" / "):
            part = part.strip()
            if part and re.search(r"[A-Za-z]", part) and all(ord(c) < 128 for c in part):
                metaTitle = part
                break
        return title, year, metaTitle

    def _coverapiUrl(self, data):
        # the player iframes are base64 strings in a script ("aHR0cHM6Ly9jb3ZlcmFwaS5zdG9yZS9lbWJlZC90dDEyMzQ1Lw==")
        urls = [data]
        for item in re.findall(r"""['"](aHR0[A-Za-z0-9+/=]+)['"]""", data):
            try:
                urls.append(ensure_str(base64.b64decode(item)))
            except Exception:
                printExc()
        return self.cm.ph.getSearchGroups(" ".join(urls), r"""(https?://coverapi\.[a-z]+/embed/[^"'\s<]+)""")[0]

    def _coverapiSeasons(self, embedUrl):
        # [(season number, season label, [(episode number, episode label)])] from the coverapi player 2 playlist;
        # kept for the session: the season list and its episode list read the same three pages
        if not embedUrl:
            return []
        if embedUrl not in self.seasonsCache:
            seasons = self._loadCoverapiSeasons(embedUrl)
            if seasons:
                self.seasonsCache[embedUrl] = seasons
            return seasons
        return self.seasonsCache[embedUrl]

    def _loadCoverapiSeasons(self, embedUrl):
        seasons = []
        host = self.cm.getBaseUrl(embedUrl)
        header = dict(self.HEADER)
        header["Referer"] = self.MAIN_URL
        # Cloudflare of coverapi.store answers IPv6 clients with 403 (error 1106)
        sts, data = self.cm.getPage(embedUrl, {"header": header, "ipv4_only": True})
        # a 404 comes back with sts True (pCommon's default ignore_http_code_ranges)
        if self.cm.meta.get("status_code") == 404:
            self.missingEmbeds.add(embedUrl)
            return seasons
        if not sts:
            return seasons
        content = data
        tabs = self.cm.ph.getSearchGroups(data, r"""data-tabs='([^']+)'""")[0]
        if tabs:
            content = ""
            try:
                for tab in json.loads(tabs.replace("&quot;", '"')):
                    if tab.get("type") == "inline":
                        content += ensure_str(base64.b64decode(tab.get("data", "")))
            except Exception:
                printExc()
        newsId = self.cm.ph.getSearchGroups(content, r"""news_id['"]?\s*:\s*['"](\d+)""")[0]
        if not newsId:
            return seasons
        header.update({"Referer": embedUrl, "X-Requested-With": "XMLHttpRequest"})
        # the same request as urlparser parserCOVERAPI, so both number the seasons / episodes alike
        post = {"mod": "players3" if "player3" in content else "players", "news_id": newsId}
        sts, data = self.cm.getPage(host + "engine/ajax/controller.php", {"header": header, "ipv4_only": True}, post)
        try:
            js = json.loads(data) if sts else {}
            url = ensure_str((js.get("file") or "").split(" or ")[0].strip())
        except Exception:
            js, url = {}, ""
        if not url.startswith("http") or (js.get("type") != "serial" and "/playlist" not in url):
            return seasons
        sts, data = self.cm.getPage(url, {"header": header, "ipv4_only": True})
        try:
            playlist = json.loads(data).get("playlist", []) if sts else []
        except Exception:
            playlist = []
        if playlist and isinstance(playlist[0], dict) and "playlist" not in playlist[0]:
            playlist = [{"comment": "Season 1", "playlist": playlist}]  # one season without a season level
        for sIdx, sItem in enumerate(playlist):
            if not isinstance(sItem, dict) or not isinstance(sItem.get("playlist"), list):
                continue
            sNum = str(int(self.cm.ph.getSearchGroups(sItem.get("comment", ""), r"(\d+)")[0] or sIdx + 1))
            # a season listed twice (another voice / translation): one row, its episodes once
            known = [s for s in seasons if s[0] == sNum]
            episodes = known[0][2] if known else []
            for eIdx, eItem in enumerate(sItem["playlist"]):
                if isinstance(eItem, dict) and eItem.get("file"):
                    eNum = str(int(self.cm.ph.getSearchGroups(eItem.get("comment", ""), r"(\d+)")[0] or eIdx + 1))
                    if eNum not in [e[0] for e in episodes]:
                        episodes.append((eNum, self.cleanHtmlStr(eItem.get("comment", ""))))
            if episodes and not known:
                seasons.append((sNum, self.cleanHtmlStr(sItem.get("comment", "")), episodes))
        return seasons

    def _pageInfo(self, data):
        # (description, {INFO key: value}) of a title page
        desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)itemprop="description">(.*?)</div>')[0])
        if not desc:
            desc = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '<meta name="description" content="([^"]+)')[0])
        # without the search engine lead-in "ταινια Crawlers (2026) online greek subtitles"
        desc = re.sub(r"(?i)^.{0,200}?online greek sub(?:title)?s\s*", "", desc)
        info = {}
        labels = {"Είδος ταινίας": "genres", "Χώρα": "country", "Director": "director", "Υπότιτλοι": "subtitles", "imdb": "rating", "Date": "year", "Ηθοποιοί": "actors"}
        for label, value in re.findall(r'(?s)<li class="label">([^<:]+):?</li>\s*<li[^>]*>(.*?)</li>', data):
            key = labels.get(label.strip())
            value = self.cleanHtmlStr(value)
            if key == "rating":
                value = self.cm.ph.getSearchGroups(value, r"(\d+(?:\.\d+)?)")[0]
            if key and value:
                info[key] = value
        return desc, info

    ###################################################
    # lists
    ###################################################
    def listCategories(self, cItem):
        printDBG("Voody.listCategories")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        data = self.cm.ph.getDataBeetwenMarkers(data, 'class="reset menu"', 'class="overlayMenu"', False)[1]
        # the menu sections (Ταινίες / Σειρές / Κινούμενα Σχέδια), each with its category links
        for section in re.split(r"<span>", data)[1:]:
            title = self.cleanHtmlStr(section.split("</span>", 1)[0])
            links = [(self.getFullUrl(url), self.cleanHtmlStr(name)) for url, name in re.findall(r'<a href="(/load/[^"]+)"[^>]*>([^<]+)</a>', section)]
            if title and links:
                self.addDir({"name": "category", "category": "list_cat_links", "title": title, "url": cItem["url"], "links": links})

    def listCategoryLinks(self, cItem):
        printDBG("Voody.listCategoryLinks")
        for url, title in cItem.get("links", []):
            if title:
                self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": url})

    def listItems(self, cItem):
        printDBG("Voody.listItems |%s|" % cItem)
        try:
            page = max(1, int(cItem.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        query = cItem.get("query", "")
        pageUrlTpl = ""
        if query:
            post = {"do": "search", "subaction": "search", "search_start": str(page), "full_search": "0", "story": query}
            sts, data = self.getPage(self.getFullUrl("/index.php?do=search"), None, post)
        else:
            baseUrl = re.sub(r"page/\d+/?$", "", cItem["url"])
            pageUrlTpl = baseUrl + "page/{page}/"
            sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else baseUrl)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, '<div class="shortItem">', '<div class="itemInfo">'):
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, r'href="([^"]+\.html)"')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="title">(.*?)</div>')[0])
            if not url or not title or url in seen:
                continue
            seen.add(url)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)')[0])
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="shortEps">(.*?)</div>')[0])
            base, year, metaTitle = self._splitTitle(title)
            year = year or self.cm.ph.getSearchGroups(item, r'<a href="#">((?:19|20)\d\d)</a>')[0]
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": quality,
                      "s_title": base, "meta_title": metaTitle, "meta_year": year}
            if "/load/seir/" in url or "/load/oloklhrwmenes_seires/" in url:
                params.update({"category": "list_seasons", "title": title, "meta_type": "tv"})
                self.addDir(params)
            else:
                params.update({"category": "video", "title": "%s (%s)" % (base, year) if (normalize and year) else title, "meta_type": "movie"})
                self.addVideo(params)

        if query:
            nums = [int(n) for n in re.findall(r"list_submit\((\d+)\)", data)]
        else:
            nums = [int(n) for n in re.findall(r'href="[^"]*/page/(\d+)/?"', data)]
        lastPage = max(nums) if nums else 0
        hasNext = bool(seen) and lastPage > page
        if query:
            # fix 281026: the search page has no links to the pages ahead (at most one back to page 1) and a wrong
            # total ("Found 20 responses") while search_start=2.. go on (box test "love") - a full page means
            # there is a next one; the last page is unknown
            hasNext = hasNext or len(seen) >= SEARCH_PAGE_SIZE
            if lastPage <= page:
                lastPage = 0
        addPagingItems(self, cItem, page, hasNext, lastPage, pageUrlTpl)

    def listSeasons(self, cItem):
        printDBG("Voody.listSeasons")
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        desc = self._pageInfo(data)[0] or cItem.get("desc", "")
        embedUrl = self._coverapiUrl(data)
        seasons = self._coverapiSeasons(embedUrl)
        if embedUrl in self.missingEmbeds:
            # fix 281026: the player has no entry for the title (coverapi 404, box log 28.10. "Roommates (2009)") - say so
            # here instead of a video row that fails on play
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        for sNum, sLabel, episodes in seasons:
            params = dict(cItem)
            params.update({"category": "list_episodes", "title": _("Season %d (%d episodes)") % (int(sNum), len(episodes)), "url": url, "s_season": sNum, "desc": desc})
            self.addDir(params)
        if not seasons:
            # no episode playlist - the page itself is the video
            params = dict(cItem)
            params.update({"category": "video", "url": url, "desc": desc})
            self.addVideo(params)

    def listEpisodes(self, cItem):
        printDBG("Voody.listEpisodes")
        url = cItem["url"].split("#", 1)[0]
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or self._splitTitle(cItem.get("title", ""))[0]
        season = cItem.get("s_season") or "1"
        for sNum, _sLabel, episodes in self._coverapiSeasons(self._coverapiUrl(data)):
            if sNum != season:
                continue
            for eNum, _eLabel in episodes:
                if normalize:
                    title = "%s - %s" % (show, formatSxxExx(season, eNum))
                else:
                    # the playlist labels are English ("Episode 3") or missing
                    title = "%s - %s - %s" % (show, _("Season %s") % season, _("Episode %d") % int(eNum))
                params = dict(cItem)
                params.update({"category": "video", "title": title, "url": "%s#s%se%s" % (url, season, eNum), "s_episode": eNum, "good_for_fav": True})
                self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Voody.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        query = searchPattern.strip()
        if len(query) < 4:
            # the site's search ignores shorter words (no results at all)
            SetIPTVPlayerLastHostError(_("Search string must have at least 4 characters."))
            return
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "query": query, "url": "", "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Voody.getLinksForVideo [%s]" % cItem)
        url = cItem.get("url", "")
        sts, data = self.getPage(url)
        if not sts:
            return []
        embed = self._coverapiUrl(data)
        if not embed:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        desc, info = self._pageInfo(data)
        imdb = self.cm.ph.getSearchGroups(embed, r"/(tt\d+)")[0]
        year = self.cm.ph.getSearchGroups(info.get("year", ""), r"((?:19|20)\d\d)")[0] or cItem.get("meta_year", "")
        metaQuery = sidecarMetaQuery(cItem.get("meta_type", ""), cItem.get("meta_title", ""), year, imdbId=imdb)
        meta = {"Referer": self.MAIN_URL}
        season, episode = self.cm.ph.getSearchGroups(url, r"#s(\d+)e(\d+)$", 2)
        if episode:
            meta.update({"Season": season, "Episode": episode})
        urltab = [{"name": "coverapi", "url": strwithmeta(embed, meta), "need_resolve": 1}]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), desc or cItem.get("desc", ""), metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("Voody.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Voody.getArticleContent [%s]" % cItem)
        desc, info, imdb = "", {}, ""
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            desc, info = self._pageInfo(data)
            imdb = self.cm.ph.getSearchGroups(self._coverapiUrl(data), r"/(tt\d+)")[0]
        year = self.cm.ph.getSearchGroups(info.get("year", ""), r"((?:19|20)\d\d)")[0] or cItem.get("meta_year", "")
        mediaType = cItem.get("meta_type", "")
        meta = {}
        try:
            if mediaType and imdb:
                meta = getMetaByImdbId(mediaType, imdb)
            if not meta and mediaType and cItem.get("meta_title"):
                # a Greek-only title: not to the services that answer it with unrelated hits (as the sidecar lookup)
                meta = getMeta(mediaType, cItem["meta_title"], year, skip=() if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY)
        except Exception:
            printExc()
        meta = meta or {}
        info.update(meta.get("info", {}))
        for siteKey, metaKey in (("actors", "cast"), ("director", "directors")):
            if metaKey in info:
                info.pop(siteKey, None)
        plot = meta.get("plot", "")
        text = desc or cItem.get("desc", "")
        if plot and text and plot != text:
            text = "%s[/br][/br]%s" % (text, plot)
        else:
            text = text or plot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        printDBG("handleService start")
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("handleService: name[%s], category[%s] " % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_cats":
            self.listCategories(self.currItem)
        elif category == "list_cat_links":
            self.listCategoryLinks(self.currItem)
        elif category == "list_seasons":
            self.listSeasons(self.currItem)
        elif category == "list_episodes":
            self.listEpisodes(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({"search_item": False, "name": "category"})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, Voody(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("voody")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ["video", "list_seasons", "list_episodes"]
