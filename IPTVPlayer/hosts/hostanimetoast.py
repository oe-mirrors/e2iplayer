# -*- coding: utf-8 -*-
LAST_MODIFIED = "24.10.2026"
# 24.10.2026 - new host: AnimeToast (German dub / sub anime, WordPress; own domain in the settings)
#   series page: one tab per hoster with an "?link=N" button per episode (the ?link page holds the embed), a button
#   for many episodes ("S21:E892-1072") opens further pages with the episode buttons; newer series load the
#   episodes per admin-ajax (get_episode_data, numbered servers). Dub / Sub from the title is shown in the link names.
import re

from Components.config import ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import applySidecarToLinks, buildSidecarFromItem, decorateResolvedLinkItems, sidecarFromUrlMeta, sidecarMetaQuery
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedHostMixin, GenericFolderWatchedScraperMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper

config.plugins.iptvplayer.animetoast_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    return [getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.animetoast_alt_domain)]


def gettytul():
    return "https://www.animetoast.cc/"


PAGE_SIZE = 100  # rows per page of the A-Z letters (the index comes in one piece)
# genre tags left out of the genre list (adult content)
SKIP_TAGS = ("adult", "smut")
# hoster tabs of dead hosters: "ToastP" = listeamed.net (VidGuard family, gone since 01.2026 - box log 24.10.2026)
DEAD_TABS = ("toastp",)
LANG_RE = re.compile(r"\s+Ger\.?\s*(Dub|Sub)\s*$", re.I)
SEASON_RES = (re.compile(r"\s+(\d+)(?:st|nd|rd|th)\s+Season$", re.I), re.compile(r"\s+Season\s+(\d+)$", re.I),
              re.compile(r"\s+Staffel\s+(\d+)$", re.I))
EPISODE_RES = (re.compile(r"^(?:Ep\.?|Episode|Folge|E)\s*(\d+)$", re.I), re.compile(r"^(\d+)$"))
# "S21:E892-1072", and the open part of a running series "S22:E1086-"
RANGE_RE = re.compile(r"\d+\s*-\s*(?:\d+|$)")
VIDEO_CAT = "at_video"
FOLDER_CATS = ("at_series", "at_part")


class AnimeToast(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "s_lang", "at_pages",
                  "meta_type", "meta_title")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "animetoast", "cookie": "animetoast.cookie"})
        self.HEADER = self.cm.getDefaultHeader()
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        domain = config.plugins.iptvplayer.animetoast_alt_domain.value.strip()
        if domain and not domain.startswith("http"):
            domain = "https://" + domain
        if not self.setMainUrl(domain if domain.endswith("/") else domain + "/"):
            self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl("wp-content/uploads/2018/03/toastfavi-300x300.png")
        self.cache = {}
        self.watchedHelper = IPTVWatchedHelper("animetoast")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        baseUrl = self._onMain(baseUrl)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def _onMain(self, url):
        # urls of an older address (favourites, history) are moved to the current one; the fragment is ours
        url = (url or "").split("#")[0]
        if self._isSite(url):
            return self.getMainUrl() + re.sub(r"^https?://[^/]+/", "", url)
        return url

    def _isSite(self, url):
        return bool(re.match(r"^https?://(?:www\.)?animetoast\.[a-z]+/", url or "")) or (url or "").startswith(self.getMainUrl())

    def _cachedPage(self, url):
        # the series page is read again for every episode / link list - once per folder is enough
        url = self._onMain(url)
        if url not in self.cache:
            sts, data = self.getPage(url)
            if not sts:
                return ""
            if len(self.cache) > 6:
                self.cache = {}
            self.cache[url] = data
        return self.cache[url]

    @staticmethod
    def _path(url):
        # domain independent identity of a page (+ our fragment)
        return re.sub(r"^https?://[^/]+", "", url or "").lower()

    @staticmethod
    def _pageNum(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    def _splitTitle(self, title):
        # "Kusuriya no Hitorigoto 3rd Season Ger Dub" -> ("Kusuriya no Hitorigoto", 3, "Ger Dub")
        title = (title or "").strip()
        lang = ""
        match = LANG_RE.search(title)
        if match:
            lang = "Ger %s" % match.group(1).capitalize()
            title = title[:match.start()].strip()
        season = 0
        for regex in SEASON_RES:
            match = regex.search(title)
            if match:
                season = int(match.group(1))
                title = title[:match.start()].strip()
                break
        return title, season, lang

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in (VIDEO_CAT,) + FOLDER_CATS:
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            prefix = {VIDEO_CAT: "video", "at_series": "series", "at_part": "part"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", "")) if prefix else ""
            return "%s:%s" % (prefix, path) if path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        def sub(slug):
            return [{"category": "list_items", "title": _("All"), "url": self.getFullUrl("category/%s/" % slug[0])},
                    {"category": "list_items", "title": "Serie", "url": self.getFullUrl("category/%s/%s/" % (slug[0], slug[1]))},
                    {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("category/%s/%s/" % (slug[0], slug[2]))},
                    {"category": "list_items", "title": "OVA", "url": self.getFullUrl("category/%s/%s/" % (slug[0], slug[3]))}]
        menu = [{"category": "list_latest", "title": _("Latest added"), "url": self.getFullUrl("latest-uploads/")},
                {"category": "list_items", "title": "Airing", "url": self.getFullUrl("category/airing/")},
                {"category": "list_items", "title": "Dub Update", "url": self.getFullUrl("category/dub-update/")},
                {"category": "list_tab", "title": "Ger Dub", "tab": sub(("ger-dub", "serie", "movie", "ova"))},
                {"category": "list_tab", "title": "Ger Sub", "tab": sub(("ger-sub", "serie-ger-sub", "movie-ger-sub", "ova-ger-sub"))},
                {"category": "list_genres", "title": _("Genres"), "url": self.MAIN_URL},
                {"category": "list_tab", "title": _("A-Z"), "tab": [
                    {"category": "list_letters", "title": _("All"), "url": self.getFullUrl("a-z-index/")},
                    {"category": "list_letters", "title": "Ger Dub", "url": self.getFullUrl("a-z-index-dub/")},
                    {"category": "list_letters", "title": "Ger Sub", "url": self.getFullUrl("a-z-index-sub/")}]}]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def _seriesParams(self, cItem, url, title, icon="", desc=""):
        show, season, lang = self._splitTitle(title)
        params = stripPagerKeys(dict(cItem), ("base_url", "tab", "letter"))
        for key in ("s_season", "s_episode", "at_pages", "search_item"):
            params.pop(key, None)
        params.update({"name": "category", "good_for_fav": True, "category": "at_series", "title": title, "url": url, "icon": icon, "desc": desc,
                       "s_title": show, "s_lang": lang, "meta_type": "tv", "meta_title": show})
        if season:
            params["s_season"] = season
        return params

    def _parseCards(self, data):
        items = []
        seen = set()
        for item in re.split(r'class="(?:[^"]* )?video-item[ "]', data)[1:]:
            url = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0]
            if not self._isSite(url) or url in seen:
                continue
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<h3><a[^>]*>(.*?)</a>')[0])
            if not title:
                continue
            seen.add(url)
            info = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="[^"]*time_dur">(.*?)</span>')[0])
            text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="(?:item-content|blog-excerpt)[^"]*">(.*?)</div>')[0])
            items.append({"url": url, "title": title, "icon": self.cm.ph.getSearchGroups(item, r'<img[^>]+?src="([^"]+)"')[0],
                          "desc": "[/br]".join(x for x in (info.replace("/#", ""), text) if x)})
        return items

    def listItems(self, cItem):
        page = self._pageNum(cItem)
        baseUrl = cItem.get("base_url") or cItem["url"]
        printDBG("AnimeToast.listItems [%s] page %d" % (baseUrl, page))
        sts, data = self.getPage(self._listUrl(baseUrl, page))
        if not sts:
            return
        items = self._parseCards(data)
        for item in items:
            self.addDir(self._seriesParams(cItem, item["url"], item["title"], item["icon"], item["desc"]))
        self._addPager(cItem, data, baseUrl, page, bool(items))

    def _listUrl(self, url, page):
        # https://site/tag/x/page/3/ ; search: https://site/page/3/?s=...
        path, sep, query = url.partition("?")
        path = re.sub(r"page/\d+/?$", "", path)
        if not path.endswith("/"):
            path += "/"
        if page > 1:
            path += "page/%d/" % page
        return path + sep + query

    def _addPager(self, cItem, data, baseUrl, page, hasItems):
        pager = self.cm.ph.getDataBeetwenMarkers(data, "class='wp-pagenavi'", "</div>", False)[1]
        lastPage = self.cm.ph.getSearchGroups(pager, r"class='pages'>[^<]*?(\d+)\s*<")[0]
        lastPage = int(lastPage) if lastPage else 0
        hasNext = hasItems and (page < lastPage or 'class="nextpostslink"' in pager)
        listItem = stripPagerKeys(dict(cItem))
        listItem.update({"base_url": baseUrl, "url": baseUrl})
        addPagingItems(self, listItem, page, hasNext, lastPage, self._listUrl(baseUrl, 987654).replace("987654", "{page}"))

    def listLatest(self, cItem):
        printDBG("AnimeToast.listLatest")
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        for item in self._parseCards(data):
            self.addDir(self._seriesParams(cItem, item["url"], item["title"], item["icon"], item["desc"]))

    def listGenres(self, cItem):
        printDBG("AnimeToast.listGenres")
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        for url, label, title in re.findall(r'<a href="([^"]+/tag/[^"]+)" class="tag-cloud-link[^"]*"[^>]*aria-label="([^"]*)"[^>]*>([^<]+)<', data):
            if self.cm.ph.getSearchGroups(url, r"/tag/([^/]+)")[0] in SKIP_TAGS:
                continue
            count = self.cm.ph.getSearchGroups(label, r"\(([\d.]+)")[0]
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": self.cleanHtmlStr(title), "url": self.getFullUrl(url),
                         "desc": count})

    def _azIndex(self, url):
        # {letter: [(url, title)]} and the letter order of an A-Z index page (~800 kB, read once)
        key = "az:" + url
        if key not in self.cache:
            data = self._cachedPage(url)
            letters = []
            index = {}
            for letterId, block in re.findall(r'(?s)<div class="letter-section"\s+id="letter-([^"]+)">(.*?)</ul>', data):
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<h2 class="letter-title">(.*?)</h2>')[0]) or letterId
                rows = [(u, self.cleanHtmlStr(t)) for u, t in re.findall(r'(?s)<a href="([^"]+)">(.*?)</a>', block)]
                if rows:
                    letters.append((letterId, title))
                    index[letterId] = rows
            self.cache.pop(self._onMain(url), None)
            self.cache[key] = (letters, index)
        return self.cache[key]

    def listLetters(self, cItem):
        printDBG("AnimeToast.listLetters [%s]" % cItem["url"])
        letters, index = self._azIndex(cItem["url"])
        for letterId, title in letters:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_letter", "title": title, "letter": letterId, "desc": str(len(index.get(letterId, [])))})
            self.addDir(params)

    def listLetter(self, cItem):
        page = self._pageNum(cItem)
        letters, index = self._azIndex(cItem["url"])
        rows = index.get(cItem.get("letter", ""), [])
        start = (page - 1) * PAGE_SIZE
        for url, title in rows[start:start + PAGE_SIZE]:
            if title:
                self.addDir(self._seriesParams(cItem, url, title))
        lastPage = (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE
        # the whole letter is in memory: the (constant) index url only serves "Jump" as the page template
        addPagingItems(self, stripPagerKeys(dict(cItem)), page, page < lastPage, lastPage, cItem["url"].replace("{", "%7B").replace("}", "%7D"))

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("AnimeToast.listSearchResult [%s]" % searchPattern)
        searchPattern = (searchPattern or "").strip()
        if not searchPattern:
            return
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # series page
    ###################################################
    def _tabs(self, data):
        # [(hoster tab label, [(episode label, ?link url)])] of a series page
        area = self.cm.ph.getDataBeetwenMarkers(data, 'class="multi_link-area"', 'class="clearfix"', False)[1] or \
            self.cm.ph.getDataBeetwenMarkers(data, 'class="multi_link-area"', "</article>", False)[1]
        names = dict(re.findall(r'href="#multi_link_tab(\d+)">([^<]+)</a>', area))
        tabs = []
        for tabId, pane in re.findall(r'(?s)id="multi_link_tab(\d+)" class="tab-pane[^"]*">(.*?)</div>', area):
            buttons = [(self.cleanHtmlStr(label), url.replace("&amp;", "&")) for url, label in
                       re.findall(r'(?s)href="([^"]+\?link=\d+)"><i\s+class="fa fa-play"></i>(.*?)</a>', pane)]
            buttons = [(label or "?", url) for label, url in buttons]
            tabLabel = self.cleanHtmlStr(names.get(tabId, "")) or "Server %s" % tabId
            if buttons and tabLabel.lower() not in DEAD_TABS:
                tabs.append((tabLabel, buttons))
        return tabs

    @staticmethod
    def _mergeTabs(tabs):
        # episode keys in site order over all hoster tabs, {key: [(tab label, url)]}; a label that is there twice in
        # one tab ("Special") gets " (2)"; keys only one tab has are put after the key before them in that tab
        order = []
        groups = {}
        for tabLabel, buttons in tabs:
            seen = {}
            pos = 0
            for label, url in buttons:
                seen[label] = seen.get(label, 0) + 1
                key = label if seen[label] == 1 else "%s (%d)" % (label, seen[label])
                if key in groups:
                    pos = order.index(key) + 1
                else:
                    order.insert(pos, key)
                    groups[key] = []
                    pos += 1
                groups[key].append((tabLabel, url))
        return order, groups

    def _players(self, data):
        # the admin-ajax players: [(data-title, [server ids])]
        players = []
        for title, block in re.findall(r'(?s)class="simple-iframe-player" data-title="([^"]*)">(.*?)</select>', data):
            servers = re.findall(r'<option value="([^"]+)"', block)
            players.append((self.cleanHtmlStr(title), servers or ["1"]))
        return players

    def _ajax(self, data, pageUrl, title, server, episode=None):
        nonce = self.cm.ph.getSearchGroups(data, r'iframe_loader\s*=\s*\{[^}]*"nonce":"([^"]+)"')[0]
        post = {"action": "get_episode_data", "title": title, "server": server, "nonce": nonce}
        if episode is not None:
            post["episode"] = episode
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER)
        params["header"].update({"Referer": pageUrl, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*; q=0.01"})
        sts, answer = self.getPage(self.getFullUrl("wp-admin/admin-ajax.php"), params, post)
        if not sts:
            return {}
        try:
            answer = json_loads(answer)
            if answer.get("success"):
                return answer.get("data") or {}
        except Exception:
            printDBG("AnimeToast._ajax: no JSON [%s]" % (answer or "")[:200])
        return {}

    def _seriesInfo(self, data):
        # INFO fields of a series page; "_" keys are no INFO fields
        info = {}
        content = self.cm.ph.getDataBeetwenMarkers(data, 'class="item-content">', 'class="item-tax-list"', False)[1].split('<div class="vc_row', 1)[0]
        story = []
        alt = []
        for para in re.findall(r"(?s)<p>(.*?)</p>", content):
            text = self.cleanHtmlStr(para)
            if not text:
                continue
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(para, r"(?s)^\s*<strong>([^<]*:)\s*</strong>")[0])
            if label:
                value = text[len(label):].strip()
                if label.lower().startswith("genre"):
                    info["genres"] = value
                elif label.lower().startswith("season start"):
                    info["released"] = value
                    info["_year"] = self.cm.ph.getSearchGroups(value, r"(\d{4})")[0]
                continue
            if para.strip().startswith("<strong>") or "youtube.com" in para:
                alt.extend(x for x in (self.cleanHtmlStr(t) for t in re.split(r"<br\s*/?>", para)) if x and "TRAILER" not in x.upper())
                continue
            story.append(text)
        info["_story"] = "[/br]".join(story)
        info["_alt"] = alt
        if alt:
            info["alternate_title"] = ", ".join(alt[:4])
        info["_cover"] = self.cm.ph.getSearchGroups(content, r'<img[^>]+?src="([^"]+)"')[0]
        info["_trailer"] = self.cm.ph.getSearchGroups(content, r'href="(https?://(?:www\.)?youtube\.com/watch\?v=[^"]+)"')[0].replace("&amp;", "&")
        cats = self.cm.ph.getSearchGroups(data, r'<article class="post-\d+ ([^"]+)"')[0]
        info["_movie"] = bool(re.search(r"\bcategory-movie(?:-ger-sub)?\b", cats))
        info["_lang"] = "Ger Dub" if "category-ger-dub" in cats else ("Ger Sub" if "category-ger-sub" in cats else "")
        tax = self.cm.ph.getDataBeetwenMarkers(data, 'class="item-tax-list"', "</div>\n", False)[1]
        catNames = [self.cleanHtmlStr(c) for c in re.findall(r'rel="category tag">([^<]+)<', tax)]
        if catNames:
            info["categories"] = ", ".join(catNames)
        return info

    def _metaTitles(self, cItem, info):
        # moviemeta lookups: the show title, without a roman part number ("Mushoku Tensei III"), the English / other
        # titles the page lists (without "Season 3" / "Staffel 3")
        titles = []
        first = cItem.get("meta_title") or cItem.get("s_title") or self._splitTitle(cItem.get("title", ""))[0]
        for title in [first, re.sub(r"\s+(?:II|III|IV|V|VI)(?=:|$)", "", first)] + [self._splitTitle(t)[0] for t in info.get("_alt", [])]:
            title = re.sub(r"\s+Season\s+\d+$|\s+Staffel\s+\d+$", "", title or "", flags=re.I).strip()
            if title and title not in titles and re.search(r"[A-Za-z]", title):
                titles.append(title)
        return titles

    @staticmethod
    def _labelNumber(label):
        # "Ep. 12" / "Folge 12" / "12" -> 12, 0 for anything else
        for regex in EPISODE_RES:
            match = regex.match(label)
            if match:
                return int(match.group(1))
        return 0

    def _episodeTitle(self, cItem, label, single=False, offset=0):
        # offset: the pages of a part ("S21:E1000-1085") count their buttons from "Ep. 1"
        show = cItem.get("s_title") or cItem.get("title", "")
        if IsMediaNamingNormalized():
            if cItem.get("meta_type") == "movie" and single:
                return show
            season, episode = cItem.get("s_season") or 1, 0
            match = re.match(r"^S(\d+)\s*:?\s*E(\d+)$", label, re.I)
            if match:
                season, episode = int(match.group(1)), int(match.group(2))
            else:
                episode = self._labelNumber(label)
                if episode:
                    episode += offset
            if episode:
                return "%s - %s" % (show, formatSxxExx(season, episode))
        if single:
            return cItem.get("title", "")
        return "%s - %s" % (cItem.get("s_series_title") or cItem.get("title", ""), label)

    def _videoParams(self, cItem, url, title, label, pages=None):
        params = stripPagerKeys(dict(cItem), ("base_url", "tab", "letter"))
        params.update({"good_for_fav": True, "category": VIDEO_CAT, "title": title, "url": url, "desc": label, "s_episode": label})
        if pages:
            params["at_pages"] = pages
        else:
            params.pop("at_pages", None)
        return params

    def listSeries(self, cItem):
        url = self._onMain(cItem["url"])
        printDBG("AnimeToast.listSeries [%s]" % url)
        data = self._cachedPage(url)
        if not data:
            return
        info = self._seriesInfo(data)
        cItem = dict(cItem)
        if not cItem.get("s_title"):
            # an item without the split title (an older favourite): the same as _seriesParams
            show, season, lang = self._splitTitle(cItem.get("title", ""))
            cItem.update({"s_title": show, "s_lang": cItem.get("s_lang") or lang, "meta_type": cItem.get("meta_type") or "tv", "meta_title": show})
            if season:
                cItem["s_season"] = season
        if not cItem.get("s_lang") and info["_lang"]:
            cItem["s_lang"] = info["_lang"]
        cItem["icon"] = cItem.get("icon") or self.getFullIconUrl(info["_cover"])
        cItem["s_series_title"] = cItem.get("title", "")
        if info["_movie"]:
            cItem["meta_type"] = "movie"
        players = self._players(data)
        if len(players) > 1:
            for idx, (title, _servers) in enumerate(players):
                params = stripPagerKeys(dict(cItem), ("base_url", "tab", "letter"))
                params.update({"good_for_fav": True, "category": "at_part", "title": "%s - %s" % (cItem["title"], title), "url": "%s#p%d" % (url, idx)})
                self.addDir(params)
            return
        if players:
            self._listAjaxEpisodes(cItem, url, data, 0, players[0])
            return
        order, groups = self._mergeTabs(self._tabs(data))
        if not order:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        single = len(order) == 1
        for key in order:
            itemUrl = "%s#%s" % (url, urllib_quote(key))
            if RANGE_RE.search(key) and not single:
                params = stripPagerKeys(dict(cItem), ("base_url", "tab", "letter"))
                params.update({"good_for_fav": True, "category": "at_part", "title": "%s - %s" % (cItem["title"], key), "url": itemUrl})
                match = re.match(r"^S(\d+)\s*:", key)
                if match:
                    params["s_season"] = int(match.group(1))
                self.addDir(params)
            else:
                self.addVideo(self._videoParams(cItem, itemUrl, self._episodeTitle(cItem, key, single), key))

    def _listAjaxEpisodes(self, cItem, url, data, idx, player):
        title, servers = player
        episodes = []
        numbers = set()
        for server in servers:
            for episode in self._ajax(data, url, title, server).get("episodes") or []:
                try:
                    number = int(episode.get("number"))
                except (TypeError, ValueError, AttributeError):
                    continue
                if number not in numbers:
                    numbers.add(number)
                    episodes.append((number, self.cleanHtmlStr(episode.get("title") or "") or "%s %d" % (_("Episode"), number)))
        episodes.sort()
        single = len(episodes) == 1
        for number, label in episodes:
            itemUrl = "%s#p%d-%d" % (url, idx, number)
            video = self._videoParams(cItem, itemUrl, self._episodeTitle(cItem, "E%d" % number, single), label)
            if not IsMediaNamingNormalized() and not single:
                video["title"] = "%s - %s" % (cItem.get("s_series_title") or cItem.get("title", ""), label)
            self.addVideo(video)

    def listPart(self, cItem):
        url, _sep, key = cItem["url"].partition("#")
        url = self._onMain(url)
        key = urllib_unquote(key)
        printDBG("AnimeToast.listPart [%s] [%s]" % (url, key))
        data = self._cachedPage(url)
        if not data:
            return
        cItem = dict(cItem)
        cItem["s_series_title"] = cItem.get("title", "")
        players = self._players(data)
        match = re.match(r"^p(\d+)$", key)
        if match and int(match.group(1)) < len(players):
            self._listAjaxEpisodes(cItem, url, data, int(match.group(1)), players[int(match.group(1))])
            return
        order, groups = self._mergeTabs(self._tabs(data))
        # every hoster of the button has its own page with the episodes
        pages = []
        for _tab, linkUrl in groups.get(key, []):
            embed = self._embed(linkUrl)
            if self._isSite(embed):
                page = self._onMain(embed.split("?")[0])
                if page not in pages and page != url:
                    pages.append(page)
        if not pages:
            # no further pages: the button is one video (e.g. a double episode)
            self.addVideo(self._videoParams(cItem, cItem["url"], self._episodeTitle(cItem, key, True), key))
            return
        tabs = []
        for page in pages:
            tabs.extend(self._tabs(self._cachedPage(page)))
        order, groups = self._mergeTabs(tabs)
        # "S21:E1000-1085" whose pages count "Ep. 1" ... "Ep. 86": the site's episode numbers are 1000 ... 1085
        offset = 0
        match = re.match(r"^S\d+\s*:\s*E(\d+)\s*-", key)
        numbers = [n for n in (self._labelNumber(epKey) for epKey in order) if n]
        if match and numbers and min(numbers) < int(match.group(1)):
            offset = int(match.group(1)) - 1
        for epKey in order:
            self.addVideo(self._videoParams(cItem, "%s#%s" % (pages[0], urllib_quote(epKey)), self._episodeTitle(cItem, epKey, offset=offset), epKey, pages))

    ###################################################
    # links
    ###################################################
    def _embed(self, linkUrl):
        # the hoster url on a "?link=N" page (a link or an iframe in #player-embed)
        sts, data = self.getPage(linkUrl)
        if not sts:
            return ""
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="player-embed"', "</div>", False)[1]
        url = self.cm.ph.getSearchGroups(block, r'<a[^>]+href="([^"]+)"')[0] or self.cm.ph.getSearchGroups(block, r'<iframe[^>]+src="([^"]+)"')[0]
        url = url.replace("&amp;", "&")
        if url.startswith("//"):
            url = "https:" + url
        return url

    def getLinksForVideo(self, cItem):
        printDBG("AnimeToast.getLinksForVideo [%s]" % cItem.get("url"))
        url, _sep, key = cItem.get("url", "").partition("#")
        url = self._onMain(url)
        key = urllib_unquote(key)
        lang = cItem.get("s_lang", "")
        urltab = []
        data = self._cachedPage(url)
        info = self._seriesInfo(data) if data else {}
        lang = lang or info.get("_lang", "")
        match = re.match(r"^p(\d+)-(\d+)$", key)
        players = self._players(data) if (data and match) else []
        if match and int(match.group(1)) < len(players):
            title, servers = players[int(match.group(1))]
            for server in servers:
                hosterUrl = (self._ajax(data, url, title, server, match.group(2)).get("url") or "").replace("\\/", "/")
                if self.cm.isValidUrl(hosterUrl):
                    name = re.sub(r"^www\.", "", self.up.getDomain(hosterUrl, onlyDomain=True)) or "Server %s" % server
                    urltab.append({"name": "%s (%s)" % (name, lang) if lang else name, "url": strwithmeta(hosterUrl, {"Referer": self.getMainUrl()}),
                                   "need_resolve": 1})
        else:
            for page in cItem.get("at_pages") or [url]:
                page = self._onMain(page)
                _order, groups = self._mergeTabs(self._tabs(self._cachedPage(page) if page != url else data))
                for tabLabel, linkUrl in groups.get(key, []):
                    urltab.append({"name": "%s (%s)" % (tabLabel, lang) if lang else tabLabel, "url": strwithmeta(linkUrl, {"Referer": page}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        names = {}
        for link in urltab:
            # the same hoster tab on two pages of a part: "Voe (Ger Sub)", "Voe (Ger Sub) 2"
            names[link["name"]] = names.get(link["name"], 0) + 1
            if names[link["name"]] > 1:
                link["name"] = "%s %d" % (link["name"], names[link["name"]])
        metaType = "movie" if info.get("_movie") else (cItem.get("meta_type") or "tv")
        titles = self._metaTitles(cItem, info)[:3] or [""]
        metaQuery = sidecarMetaQuery(metaType, titles[0], info.get("_year", "") if metaType == "movie" else "", skip=(), altTitles=tuple(titles[1:]))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), info.get("_story", ""), metaQuery))

    def getVideoLinks(self, videoUrl):
        printDBG("AnimeToast.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        hosterUrl = videoUrl
        # a ?link page of the site: its embed; a link to another page of the site (a page of a bigger part): its first embed
        for _hop in range(2):
            if not (self._isSite(hosterUrl) and "?link=" in hosterUrl):
                break
            hosterUrl = self._embed(hosterUrl)
        if not self.cm.isValidUrl(hosterUrl) or self._isSite(hosterUrl):
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(hosterUrl, {"Referer": self.getMainUrl()})), sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("AnimeToast.getArticleContent [%s]" % cItem.get("url"))
        data = self._cachedPage(cItem.get("url", ""))
        info = self._seriesInfo(data) if data else {}
        metaType = "movie" if info.get("_movie") else (cItem.get("meta_type") or "tv")
        meta = {}
        try:
            for title in self._metaTitles(cItem, info)[:3]:
                meta = getMeta(metaType, title, info.get("_year", "") if metaType == "movie" else "") or {}
                if meta:
                    break
        except Exception:
            printExc()
        otherInfo = dict((k, v) for k, v in info.items() if not k.startswith("_"))
        otherInfo.update(meta.get("info", {}))
        if cItem.get("category") == VIDEO_CAT and cItem.get("s_episode"):
            otherInfo["episodes"] = cItem["s_episode"]
        plot = meta.get("plot", "")
        text = info.get("_story", "") or cItem.get("desc", "")
        if plot and text and plot != text:
            text = "%s[/br][/br]%s" % (text, plot)
        else:
            text = text or plot
        icon = self.getFullIconUrl(info.get("_cover", "")) or cItem.get("icon", "") or meta.get("poster", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": otherInfo}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("AnimeToast.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "list_tab":
            self.listsTab(self.currItem.get("tab", []), {"name": "category"})
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_latest":
            self.listLatest(self.currItem)
        elif category == "list_genres":
            self.listGenres(self.currItem)
        elif category == "list_letters":
            self.listLetters(self.currItem)
        elif category == "list_letter":
            self.listLetter(self.currItem)
        elif category == "at_series":
            self.listSeries(self.currItem)
        elif category == "at_part":
            self.listPart(self.currItem)
        elif category in ("search", "search_next_page"):
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
        CHostBase.__init__(self, AnimeToast(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("animetoast")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in (VIDEO_CAT,) + FOLDER_CATS
