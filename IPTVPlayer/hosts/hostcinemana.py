# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - host standard rework; cinemana.vip -> cinemana.cc -> cinamana.cc (Cloudflare
#   challenges every non-browser request there, curl-impersonate included: pages need a MyE2i solve on the box)
#   - parsers follow the 2026 Tailwind theme: list cards "<a href=".../watch=<id>/"> .. <h3>title</h3>",
#     "/page/<n>/" pager (last page may carry an Arabic thousands separator); the categories come from the
#     WordPress REST api (the site's nav points to external pages), search from admin-ajax typesense_search
#   - series lists show the latest episodes; every show is one folder (episode page -> season tabs
#     "season-<id>" -> "EP n" tiles, the rest through admin-ajax load_more_episodes, which never returns
#     episode 1 -> found through the search)
#   - movies and episodes are VIDEO rows keyed on their page url ("watch=<post id>"); the answer of the
#     site's Server.php (server 0) is read in getLinksForVideo: "masterUrl" of the site's own player is
#     played directly (mp4 / HLS), an iframe (acm.php?url=<hoster>) goes to urlparser
#   - First page / Jump / Next page from the site's pager, watched flag (show -> season -> episode),
#     downloaded flag, favourites, name normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via
#     moviemeta + the site's post data; no colour codes in titles, py2 compatible (no f-strings)
import os
import re
import time

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://cinamana.cc/"


COLOR_CODE_RE = re.compile(r"\\c[0-9A-Fa-f]{8}")
# Arabic ordinals used in season labels ("موسم الثالث", "الموسم الثاني")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("السادس عشر", 16), ("السابع عشر", 17), ("الثامن عشر", 18), ("التاسع عشر", 19), ("العشرون", 20),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6),
    ("السادس", 6), ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9),
    ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:الموسم|موسم)\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"^(.*?)\s*(?:الحلقة|حلقة)\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|[\s(])((?:19|20)\d{2})(?=[\s)]|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجم|مترجمة|مدبلج|مدبلجة|اون لاين|أون لاين|مشاهدة|فيلم|مسلسل|انمي|كامل|كاملة|HD)(?=\s|$)")
# "7٬820": the pager prints big page numbers with the Arabic thousands separator (no character class:
# the py2 regex runs on utf-8 bytes)
PAGE_NUM_RE = r"(\d(?:\d|,|٬)*)"
MAX_MORE_EPISODE_PAGES = 30
SEARCH_PER_PAGE = 48
# separators around show names: "Batman: Caped Crusader الموسم الثاني – الحلقة 10" (alternation, not a
# character class: the en dash is three bytes in py2)
EDGE_RE = re.compile(r"(?:^(?:[\s:|-]|–)+)|(?:(?:[\s:|-]|–)+$)")
# season tab tile: <a href=".../watch=<id>/" ..><span ..>EP</span><span ..>12</span></a>
EPISODE_TILE_RE = re.compile(r'(?s)<a href="([^"]+/watch=\d+/?)"[^>]*>\s*<span[^>]*>\s*EP\s*</span>\s*<span[^>]*>\s*(\d+)\s*</span>')


def _stripColors(text):
    return COLOR_CODE_RE.sub("", text or "")


def _clean(text):
    text = JUNK_RE.sub(" ", JUNK_RE.sub(" ", text or ""))
    return EDGE_RE.sub("", re.sub(r"\s+", " ", text))


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


def _pageNum(text):
    try:
        return int(re.sub(r"\D", "", text or ""))
    except ValueError:
        return 0


class Cinemana(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "season_id", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cinemana", "cookie": "cinemana.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/cinemana.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}

        self.MENU = [
            {"category": "list_items", "good_for_fav": True, "title": _("Series"), "url": self.getFullUrl("/series/")},
            {"category": "list_items", "good_for_fav": True, "title": _("Movies"), "url": self.getFullUrl("/movies/")},
            {"category": "cm_categories", "title": _("Categories")},
        ] + self.searchItems()
        self.watchedHelper = IPTVWatchedHelper("cinemana")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def _ajax(self, url, referer, post_data):
        header = dict(self.HEADER)
        header.update({"Referer": referer, "Accept": "*/*", "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        params = dict(self.defaultParams)
        params["header"] = header
        return self.getPage(url, params, post_data)

    def getFullUrl(self, url, currUrl=None):
        # category urls are written in Arabic - one ASCII (percent-encoded) form for everything
        return self._quote(CBaseHostClass.getFullUrl(self, url, currUrl))

    @staticmethod
    def _quote(url):
        try:
            return urllib_quote(urllib_unquote(url.replace("&amp;", "&").replace("&#038;", "&")), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def _canonUrl(self, url):
        url = (url or "").strip()
        if not url:
            return ""
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return self._quote(url)

    def _path(self, url):
        # domain independent identity of a page (the site moved cinemana.vip -> cinemana.cc -> cinamana.cc)
        url = urllib_unquote(self._canonUrl(url))
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def _icon(self, url):
        url = (url or "").strip().strip("'\"")
        return self.getFullIconUrl(self._quote(url)) if url else ""

    def getFullIconUrl(self, url, currUrl=None):
        # covers on the site's own domain sit behind the same Cloudflare check as the pages: the download
        # needs the cf_clearance cookie and the User-Agent that passed the check. The meta is attached here
        # because the host base runs every icon through getFullIconUrl again (getFullUrl returns a plain str)
        url = CBaseHostClass.getFullIconUrl(self, url, currUrl)
        # posters still linked on the old domains redirect to the current one
        url = re.sub(r"^https?://(?:www\.)?cinemana\.(?:vip|cc)/+", self.MAIN_URL, url)
        if not url.startswith("http") or self.up.getDomain(url) != self.up.getDomain(self.MAIN_URL):
            return url
        meta = {"Referer": self.MAIN_URL}
        try:
            # getCookieHeader logs tracebacks for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return strwithmeta(url, meta)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("cm_video", "cm_series", "cm_season"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        # a show folder is opened from any of its episode pages -> keyed on the show name
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category == "cm_video":
                path = self._path(cItem.get("url", ""))
                return "video:%s" % path if path else ""
            if category == "cm_series":
                show = cItem.get("s_title", "").strip().lower()
                return "series:%s" % show if show else ""
            if category == "cm_season":
                return "season:%s" % cItem["season_id"] if cItem.get("season_id") else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listCategories(self, cItem):
        # the nav menu links to external pages; the REST api lists the real categories ("watch=category/<slug>/")
        sts, data = self.getPage(self.getFullUrl("/wp-json/wp/v2/categories?per_page=100&orderby=count&order=desc&hide_empty=true&_fields=name,link,count"))
        if not sts:
            return
        try:
            categories = json_loads(data)
        except Exception:
            printExc()
            return
        for category in categories if isinstance(categories, list) else []:
            title = self.cleanHtmlStr(category.get("name", ""))
            url = category.get("link", "")
            if title and "/watch=category/" in url:
                self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": self._canonUrl(url),
                             "desc": "%s: %s" % (_("Videos"), category.get("count", ""))})

    def _addCard(self, label, url, icon, normalize, shows):
        show = self._showName(label)
        if show:
            # an episode card -> one folder per show (the list holds several episodes of a show)
            if show.lower() in shows:
                return
            shows.add(show.lower())
            self.addDir({"name": "category", "good_for_fav": True, "category": "cm_series", "title": show, "url": url, "icon": icon,
                         "desc": label, "s_title": show, "meta_type": "tv", "meta_title": show})
        else:
            self.addVideo(self._movieParams(label, url, icon, normalize))

    def _showName(self, label):
        m = EPISODE_RE.search(label)
        if not m:
            return ""
        return _clean(SEASON_RE.sub(" ", m.group(1))) or _clean(label)

    def _movieParams(self, label, url, icon, normalize):
        year = YEAR_RE.search(label)
        year = year.group(1) if year else ""
        metaTitle = _clean(re.sub(r"\(?\b%s\b\)?" % year, " ", label) if year else label) or label
        title = ("%s (%s)" % (metaTitle, year) if year else metaTitle) if normalize else label
        return {"name": "category", "good_for_fav": True, "category": "cm_video", "title": title, "url": url, "icon": icon,
                "meta_type": "movie", "meta_title": metaTitle, "meta_year": year}

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = cItem["url"]
        printDBG("Cinemana.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seen = set()
        shows = set()
        # cards: <a href=".../watch=<id>/" class="block relative w-full"> .. background-image: url('<cover>') .. <h3>title</h3></a>
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, "<a ", "</a>"):
            if "<h3" not in item or "cn-mega-item" in item:
                continue
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            if "/watch=" not in href or "/watch=category/" in href:
                continue
            url = self._canonUrl(href)
            if url in seen:
                continue
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h3[^>]*>(.*?)</h3>")[0])
            if not label:
                continue
            seen.add(url)
            icon = self._icon(self.cm.ph.getSearchGroups(item, r"background-image:\s*url\(([^),]+)\)")[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+?(?:data-src|src)="([^"]+)"')[0])
            self._addCard(label, url, icon, normalize, shows)

        # pager: <a class=".." href="<list>/page/3/">3</a> .. <a class="next .." href=..> ("page-numbers" on /series/;
        # the category pages print broken links "watch=category%2F<slug>%2Fpage%2F2%2F/page/3/" -> the template
        # is built from the list's own url)
        lastPage = max([_pageNum(n) for n in re.findall(r'<a[^>]+href="[^"]*/page/\d+/?"[^>]*>\s*%s\s*</a>' % PAGE_NUM_RE, data)] + [page])
        nextTag = self.cm.ph.getSearchGroups(data, r'(<a[^>]+class="next[\s"][^>]*>)')[0]
        firstUrl = re.sub(r"page/\d+/?$", "", cItem.get("first_url") or cItem["url"])
        pageTpl = "" if "?" in firstUrl else firstUrl.rstrip("/") + "/page/{page}/"
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "first_url": firstUrl, "url": firstUrl})
        hasNext = bool(seen) and "href=" in nextTag
        nextUrl = self.cm.ph.getSearchGroups(nextTag, r'href="([^"]+)"')[0]
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl, None if pageTpl else {"url": self._canonUrl(nextUrl)})

    def listSearch(self, cItem):
        # the search page shows the first hits, its "more" button asks admin-ajax typesense_search (48 per page, json)
        page = cItem.get("page", 1)
        query = cItem.get("query", "")
        sts, data = self._ajax(self.getFullUrl("/wp-admin/admin-ajax.php"), self.getFullUrl("/?s=%s" % urllib_quote(query, safe="")),
                               {"action": "typesense_search", "q": query, "page": page})
        if not sts:
            return
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return
        normalize = IsMediaNamingNormalized()
        shows = set()
        hits = data.get("hits", []) if isinstance(data, dict) else []
        for hit in hits:
            doc = hit.get("document", {}) if isinstance(hit, dict) else {}
            label = self.cleanHtmlStr(doc.get("title", ""))
            url = doc.get("url", "")
            if label and "/watch=" in url:
                self._addCard(label, self._canonUrl(url), self._icon(doc.get("image", "")), normalize, shows)
        try:
            lastPage = (int(data.get("found", 0)) + SEARCH_PER_PAGE - 1) // SEARCH_PER_PAGE
        except (TypeError, ValueError):
            lastPage = 0
        # "url" only carries the page number for Jump (the list itself is built from query + page)
        pageTpl = self.getFullUrl("/?s=%s" % urllib_quote(query, safe="")) + "&page={page}"
        addPagingItems(self, dict(cItem, category="cm_search"), page, bool(hits) and page < lastPage, lastPage, pageTpl)

    def _seasons(self, data):
        # [(season number, "season-<id>" wrapper id, label)] in site order: <button data-target="season-<id>"> موسم 1 </button>
        seasons = []
        for target, label in re.findall(r'(?s)<button[^>]+data-target="(season-\d+)"[^>]*>(.*?)</button>', data):
            label = self.cleanHtmlStr(label)
            if target not in [s[1] for s in seasons]:
                seasons.append((_seasonNum(label), target, label))
        return seasons

    def listSeries(self, cItem):
        # the show folder is one of its episode pages: season tabs -> season folders, one season -> episodes
        printDBG("Cinemana.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._seasons(data)
        if len(seasons) <= 1:
            season = cItem.get("s_season") or (seasons[0][0] if seasons else 0) or 1
            self.listEpisodes(dict(cItem, s_season=season, season_id=seasons[0][1] if seasons else ""), data)
            return
        # the site sorts the tabs by name ("الاول", "الثالث", "الثاني") -> by number, unknown numbers keep their place
        order = sorted(range(len(seasons)), key=lambda i: (seasons[i][0] or i + 1, i))
        for idx in order:
            num, target, label = seasons[idx]
            num = num or idx + 1
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "cm_season", "title": "%s - %s" % (cItem.get("s_title", ""), formatSxxExx(num)) if IsMediaNamingNormalized() else label,
                           "s_season": num, "season_id": target, "desc": label})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("Cinemana.listEpisodes [%s] [%s]" % (cItem.get("url", ""), cItem.get("season_id", "")))
        pageUrl = self._canonUrl(cItem.get("url", ""))
        if data is None:
            sts, data = self.getPage(pageUrl)
            if not sts:
                return
        seasonId = cItem.get("season_id", "")
        if seasonId:
            # <div id="season-<id>" class="season-wrapper .."> .. up to the next season's wrapper
            block = self.cm.ph.getDataBeetwenMarkers(data, 'id="%s"' % seasonId, "</section>", False)[1]
            block = block.split('id="season-')[0]
        else:
            block = data
        tiles = EPISODE_TILE_RE.findall(block)
        # long seasons: <button data-season=".." data-page="2" data-current=".."> -> admin-ajax load_more_episodes.
        # The page shows the newest 31 episodes, the ajax pages count from the oldest (30 each, without
        # episode 1 and the current one) -> all ajax pages from 1, duplicates dropped below
        more = self.cm.ph.getSearchGroups(block, r'(<button[^>]+data-season="[^"]+"[^>]*>)')[0]
        if more:
            seasonParam = self.cm.ph.getSearchGroups(more, r'data-season="([^"]+)"')[0]
            currentParam = self.cm.ph.getSearchGroups(more, r'data-current="([^"]+)"')[0] or self.cm.ph.getSearchGroups(pageUrl, r"watch=(\d+)")[0]
            ajaxUrl = self.getFullUrl("/wp-admin/admin-ajax.php")
            for morePage in range(1, MAX_MORE_EPISODE_PAGES + 1):
                sts, answer = self._ajax(ajaxUrl, pageUrl, {"action": "load_more_episodes", "season_id": seasonParam, "page": morePage, "current_post_id": currentParam})
                found = EPISODE_TILE_RE.findall(answer) if sts else []
                if not found:
                    break
                tiles.extend(found)
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season") or 1
        if more and tiles and min(int(num) for _href, num in tiles) == 2:
            tiles.extend(self._findEpisodeOne(show, season))
        normalize = IsMediaNamingNormalized()
        episodes = {}
        seen = set()
        for href, num in tiles:
            url = self._canonUrl(href)
            episode = int(num)
            if url in seen:
                continue
            seen.add(url)
            title = "%s - %s" % (show, formatSxxExx(season, episode)) if normalize else "%s %s %d" % (show, _("Episode"), episode)
            episodes[(episode, url)] = {"name": "category", "good_for_fav": True, "category": "cm_video", "title": title, "url": url,
                                        "icon": cItem.get("icon", ""), "desc": cItem.get("desc", "") if url == pageUrl else "",
                                        "s_title": show, "s_season": season, "s_episode": str(episode),
                                        "meta_type": "tv", "meta_title": cItem.get("meta_title", show)}
        if not episodes:
            # no episode tiles (yet): the page itself is the only episode
            m = EPISODE_RE.search(cItem.get("desc", ""))
            episode = int(m.group(2)) if m else 1
            episodes[(episode, pageUrl)] = {"name": "category", "good_for_fav": True, "category": "cm_video", "url": pageUrl, "icon": cItem.get("icon", ""),
                                            "title": "%s - %s" % (show, formatSxxExx(season, episode)) if normalize else cItem.get("desc", "") or show,
                                            "s_title": show, "s_season": season, "s_episode": str(episode), "meta_type": "tv", "meta_title": show}
        for key in sorted(episodes.keys()):
            self.addVideo(episodes[key])

    def _findEpisodeOne(self, show, season):
        # load_more_episodes never returns episode 1 -> one search for "<show> الحلقة 1"
        sts, data = self._ajax(self.getFullUrl("/wp-admin/admin-ajax.php"), self.MAIN_URL, {"action": "typesense_search", "q": "%s الحلقة 1" % show, "page": 1})
        try:
            hits = json_loads(data).get("hits", []) if sts else []
        except Exception:
            printExc()
            return []
        for hit in hits:
            doc = hit.get("document", {}) if isinstance(hit, dict) else {}
            label = self.cleanHtmlStr(doc.get("title", ""))
            m = EPISODE_RE.search(label)
            if m and m.group(2) == "1" and "/watch=" in doc.get("url", "") and self._showName(label).lower() == show.lower() and (_seasonNum(label) or 1) == season:
                return [(doc["url"], "1")]
        return []

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Cinemana.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "cm_search", "query": searchPattern.strip(), "page": 1})
        self.listSearch(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        # the theme writes the post data as js: const postData = {id: '..', title: '..', poster: '..', categories: [..], genres: [..]}
        block = self.cm.ph.getDataBeetwenMarkers(data, "postData", "};", False)[1]
        poster = self.cm.ph.getSearchGroups(block, r"""poster:\s*['"]([^'"]+)['"]""")[0] or self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        story = self.cm.ph.getSearchGroups(data, r'<meta (?:property="og:description"|name="description") content="([^"]+)"')[0]
        story = self.cleanHtmlStr(story)
        info = {}
        for key in ("categories", "genres"):
            values = re.findall(r'"([^"]+)"', self.cm.ph.getSearchGroups(block, r"%s:\s*\[([^\]]*)\]" % key)[0])
            values = ", ".join(v for v in (urllib_unquote(v).replace("-", " ").strip() for v in values) if v)
            if values:
                info["category" if key == "categories" else "genres"] = values
        return story, self._icon(poster) if poster else "", info

    def _serverLinks(self, answer, userAgent, seen):
        links = []
        # the site's own player: const masterUrl = "https://...mp4" (or .m3u8)
        master = self.cm.ph.getSearchGroups(answer, r'''masterUrl\s*=\s*["']([^"']+)["']''')[0].replace("\\/", "/")
        if self.cm.isValidUrl(master) and master not in seen:
            seen.add(master)
            if ".m3u8" in master:
                for item in getDirectM3U8Playlist(strwithmeta(master, {"User-Agent": userAgent}), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999):
                    links.append({"name": item.get("name", "HLS"), "url": item["url"], "need_resolve": 0})
            else:
                links.append({"name": "%s %d" % (_("Server"), len(seen)), "url": strwithmeta(master, {"User-Agent": userAgent}), "need_resolve": 0})
        src = self.cm.ph.getSearchGroups(answer, r'<iframe[^>]+src="([^"]+)"')[0].replace("&amp;", "&").strip()
        if src.startswith("//"):
            src = "https:" + src
        if src:
            # acm.php?url=<hoster embed> (2026) / video-proxy.php?url=<mp4> (older theme)
            inner = urllib_unquote(self.cm.ph.getSearchGroups(src, r"(?:acm|video-proxy)\.php\?url=([^&]+)")[0])
            if self.cm.isValidUrl(inner):
                if "video-proxy.php" in src:
                    if inner not in seen:
                        seen.add(inner)
                        links.append({"name": "%s %d" % (_("Server"), len(seen)), "url": strwithmeta(inner, {"Referer": self.MAIN_URL, "User-Agent": userAgent}), "need_resolve": 0})
                    return links
                src = inner
            if self.cm.isValidUrl(src) and src not in seen:
                seen.add(src)
                links.append({"name": self.up.getHostName(src), "url": strwithmeta(src, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        return links

    def getLinksForVideo(self, cItem):
        pageUrl = self._canonUrl(cItem.get("url", ""))
        printDBG("Cinemana.getLinksForVideo [%s]" % pageUrl)
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        story = self._siteInfo(data)[0]
        postId = self.cm.ph.getSearchGroups(pageUrl, r"watch=(\d+)")[0] or self.cm.ph.getSearchGroups(data, r"""postData\s*=\s*\{\s*id:\s*['"](\d+)""")[0]
        if not postId:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        servers = []
        for num in re.findall(r'(?:data-server="|loadVideo\()(\d+)', data):
            if num not in servers:
                servers.append(num)
        ajaxUrl = self.getFullUrl("/wp-content/themes/EEE/Inc/Ajax/Single/Server.php")
        userAgent = self.HEADER.get("User-Agent")
        urltab = []
        seen = set()
        siteMsg = ""
        for num in servers or ["0"]:
            # "RE_RENDER_NOW": the site renders the player in the background, its own page asks again after 4 s
            for attempt in range(3):
                sts, answer = self._ajax(ajaxUrl, pageUrl, {"post_id": postId, "server": num})
                if not sts or answer.strip() != "RE_RENDER_NOW":
                    break
                if attempt < 2:
                    time.sleep(4)
            if sts:
                urltab.extend(self._serverLinks(answer, userAgent, seen))
                # a plain text answer is the site's own notice, e.g. "هناك مشكلة في سيرفر العرض لهذا العمل جاري حلها"
                # (the player server of this title has a problem)
                if "<" not in answer and answer.strip() != "RE_RENDER_NOW":
                    siteMsg = siteMsg or self.cleanHtmlStr(answer)[:200]
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available") + ("\n" + siteMsg if siteMsg else ""))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=_stripColors(cItem.get("desc", ""))), IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("Cinemana.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Cinemana.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""))
            except Exception:
                printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or _stripColors(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("Cinemana.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "cm_categories":
            self.listCategories(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "cm_search":
            self.listSearch(self.currItem)
        elif category == "cm_series":
            self.listSeries(self.currItem)
        elif category == "cm_season":
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
        CHostBase.__init__(self, Cinemana(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cinemana")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("cm_video", "cm_series", "cm_season")
