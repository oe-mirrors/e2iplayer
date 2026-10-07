# -*- coding: utf-8 -*-
# Last Modified: 04.10.2026
# 03.10.2026 - brought to the current host standard
#   (Asia TV Drama, as1tv.com - Asian dramas with Arabic subtitles - originally by Mohamed Elsafty)
#   - new domain as1tv.com (asiatvdrama.com redirects there); no sleeping 3x retry wrapper; no
#     f-string (Python 2); no 200-page "all actors" loop and no pre-fetch of the next page
#   - drama -> seasons (when there are several) -> episodes (ascending); movies and the
#     "new episodes" cards are VIDEO rows keyed on their page; the servers (asiawiki.me
#     fetch_episode) are read in getLinksForVideo, asiatvplayer.com is unpacked here, every
#     other iframe goes to urlparser (need_resolve=1)
#   - paging (First page / Jump / Next page with the last page), search + history, actors,
#     watched flag, favourites, sidecar, INFO (site fields/story/poster + moviemeta by the
#     original title), name normalisation ("Title (Year)", "Show - SxxExx"), no colour codes in titles
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.jsunpack import get_packed_data
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://as1tv.com/"


AJAX_URL = "https://asiawiki.me/wp-admin/admin-ajax.php?action=fetch_episode&id=%s"
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادس", 6),
    ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:الموسم|الجزء)\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
REPORT_RE = re.compile(r"\s*تقرير\s*\+\s*حلقات\s*مترجمة")
INFO_FIELDS = (("البلد", "country"), ("اسم العمل", "original_title"), ("الاسم العربي", "alternate_title"), ("مواعيد البث", "broadcast"),
               ("عدد الحلقات", "episodes"))


class Asi1TV(GenericFolderWatchedScraperMixin, CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "asi1tv", "cookie": "asi1tv.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://as1tv.com/wp-content/uploads/2021/09/cropped-asiadrama-192x192.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.DRAMA_TAB = [
            (_("Korean"), "types/الدراما-الكورية/"), (_("Chinese"), "types/الدراما-الصينية/"),
            (_("Thai"), "types/الدراما-التايلندية/"), (_("Taiwanese"), "types/الدراما-التايونية/"),
            (_("Japanese"), "types/الدراما-اليابانية/"),
        ]
        self.MENU = [
            {"category": "as_list", "title": _("Newest Episodes"), "url": "الحلقات-الجديدة/"},
            {"category": "as_drama_menu", "title": _("Drama")},
            {"category": "as_list", "title": _("Asian movies"), "url": "types/افلام-اسيوية/"},
            {"category": "as_list", "title": _("Airing now"), "url": "دراما-تبث-حاليا/"},
            {"category": "as_list", "title": _("Completed"), "url": "دراما-مكتملة/"},
            {"category": "as_list", "title": _("Top rated"), "url": "الدراما-الاكثر-تقييما/"},
            {"category": "as_actors", "title": _("Actors"), "url": "قائمة-الفنانين/"},
        ]
        self.watchedHelper = IPTVWatchedHelper("asi1tv")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        # the site links the same page raw-Arabic or percent-encoded (lower/upper case) - one ASCII form
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        url = self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    @staticmethod
    def _path(url):
        try:
            return urllib_unquote(re.sub(r"^https?://[^/]+", "", url or "")).strip("/")
        except Exception:
            return url or ""

    @staticmethod
    def _seasonNum(label):
        m = SEASON_RE.search(label or "")
        if not m:
            return 1
        val = m.group(1)
        return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 1)

    @staticmethod
    def _parseTitle(title):
        # "2026 Portrait of a Family فيلم صورة عائلية الكوري 2026 مترجم" -> ("Portrait of a Family", "2026")
        # "Four Hands, Two Sonatas ح11 مسلسل ..." -> ("Four Hands, Two Sonatas", "")
        title = REPORT_RE.sub("", title or "").strip()
        full = title
        year = ""
        m = re.match(r"^((?:19|20)\d{2})\s+", title)
        if m:
            year = m.group(1)
            title = title[m.end():]
        if not year:
            years = re.findall(r"(?:^|\s)((?:19|20)\d{2})(?=\s|$)", title)
            year = years[-1] if years else ""
        # the original (Latin) name: the longest Latin run before / between the Arabic words
        runs = [r.strip(" -:|,") for r in re.findall(r"[A-Za-z0-9][\x20-\x7e]*", re.sub(r"\s+ح\s*\d+.*$", "", title))]
        runs = [r for r in runs if re.search(r"[A-Za-z]", r)]
        name = max(runs, key=len) if runs else ""
        # "... Love in 1995" keeps its year, a trailing release year (twice in the title or recent) goes
        if year and name.endswith(" " + year) and (full.count(year) > 1 or int(year) >= 2010):
            name = name[:-len(year)].strip(" -:|,")
        return name, year

    def _dispTitle(self, title, name, year):
        if not IsMediaNamingNormalized() or not name:
            return REPORT_RE.sub("", title).strip()
        return "%s (%s)" % (name, year) if year else name

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            kind = {"as_series": "drama", "as_season": "season", "as_video": "video"}.get(cItem.get("category", ""), "")
            path = self._path(cItem.get("url", ""))
            return "%s:%s" % (kind, path) if kind and path else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        for item in self.MENU:
            params = dict(item, name="category", good_for_fav=True)
            if "url" in params:
                params["url"] = self._canonUrl(params["url"])
            self.addDir(params)
        self.listsTab(self.searchItems(), cItem)

    def listDramaMenu(self, cItem):
        for title, path in self.DRAMA_TAB:
            self.addDir({"name": "category", "category": "as_list", "good_for_fav": True, "title": title, "url": self._canonUrl(path)})

    def _pageTpl(self, cItem):
        if cItem.get("search_pattern"):
            return self.MAIN_URL + "page/{page}/?s=" + urllib_quote_plus(cItem["search_pattern"])
        return re.sub(r"page/\d+/?$", "", cItem["url"]).rstrip("/") + "/page/{page}/"

    def _lastPage(self, data):
        block = self.cm.ph.getDataBeetwenMarkers(data, "<ul class='page-numbers'>", "</ul>", False)[1]
        nums = [int(n) for n in re.findall(r"page/(\d+)/", block)]
        return (max(nums) if nums else 0), ('class="next page-numbers"' in block)

    def _addCard(self, item, normalize):
        # one card of a list: episode / movie -> VIDEO, drama -> DIR; False when it is no card
        m = re.search(r'<a href="([^"]+)" title="([^"]*)"', item)
        if not m:
            return False
        url = self._canonUrl(m.group(1))
        title = self.cleanHtmlStr(m.group(2))
        eps = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="eps">(.*?)</div>')[0])
        translate = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="translate">(.*?)</div>')[0])
        info = [self.cleanHtmlStr(x) for x in re.findall(r'(?s)<span><i class="iconFont-movie"></i>(.*?)</span>', item)]
        vip = ["VIP"] if '<div class="vip-ribbon">' in item else []
        name, year = self._parseTitle(title)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": self._canonUrl(self.cm.ph.getSearchGroups(item, r'data-img="([^"]+)"')[0]),
                  "desc": " | ".join([x for x in [eps, translate] + info + vip if x]), "meta_title": name, "meta_year": year}
        if "/episodes/" in url:
            epNum = self.cm.ph.getSearchGroups(title, r"ح\s*(\d+)")[0] or self.cm.ph.getSearchGroups(title, r"الحلقة\s*(\d+)")[0]
            season = self._seasonNum(title)
            disp = REPORT_RE.sub("", title).strip()
            if normalize and name and epNum:
                disp = "%s - %s" % (name, formatSxxExx(season, epNum))
            params.update({"category": "as_video", "title": disp, "s_title": name, "s_season": season, "s_episode": epNum, "meta_type": "tv"})
            self.addVideo(params)
        elif "فيلم" in title or "فيلم" in eps:
            params.update({"category": "as_video", "title": self._dispTitle(title, name, year), "meta_type": "movie"})
            self.addVideo(params)
        else:
            params.update({"category": "as_series", "title": self._dispTitle(title, name, year), "s_title": name, "meta_type": "tv"})
            self.addDir(params)
        return True

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        tpl = self._pageTpl(cItem)
        if page > 1:
            url = tpl.format(page=page)
        elif cItem.get("search_pattern"):
            url = self.MAIN_URL + "?s=" + urllib_quote_plus(cItem["search_pattern"])
        else:
            url = cItem["url"]
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        count = 0
        for item in re.findall(r'<article class="post(?:Ep)?">(.*?)</article>', data, re.S):
            if self._addCard(item, normalize):
                count += 1
        lastPage, hasNext = self._lastPage(data)
        addPagingItems(self, cItem, page, count > 0 and hasNext, lastPage if lastPage >= page else 0, tpl)

    def listActors(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        tpl = self._pageTpl(cItem)
        sts, data = self.getPage(tpl.format(page=page) if page > 1 else cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="listActors">', "</div>", False)[1]
        count = 0
        for url, title, inner in re.findall(r"<a href=\"([^\"]+)\"\s+title='([^']*)'\s*>(.*?)</a>", block, re.S):
            title = self.cleanHtmlStr(title) or self.cleanHtmlStr(inner)
            if not title:
                continue
            count += 1
            self.addDir({"name": "category", "category": "as_actor", "good_for_fav": True, "title": title, "url": self._canonUrl(url),
                         "icon": self._canonUrl(self.cm.ph.getSearchGroups(inner, r'src="([^"]+)"')[0])})
        lastPage, hasNext = self._lastPage(data)
        addPagingItems(self, cItem, page, count > 0 and hasNext, lastPage if lastPage >= page else 0, tpl)

    def listActor(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        bio = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, "<p>", "</p>", False)[1])
        if bio:
            self.addMarker({"title": cItem.get("title", ""), "desc": bio, "icon": cItem.get("icon", "")})
        normalize = IsMediaNamingNormalized()
        for item in re.findall(r'<article class="post">(.*?)</article>', data, re.S):
            self._addCard(item, normalize)

    def listSeries(self, cItem):
        # drama page: seasons when there are several, else the episodes of the page
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="list-seasons"', "</ul>", False)[1]
        seasons = []
        for url, label in re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', block):
            url = self._canonUrl(url)
            if url not in [s[0] for s in seasons]:
                seasons.append((url, self.cleanHtmlStr(label)))
        show = cItem.get("s_title", "") or cItem.get("title", "")
        normalize = IsMediaNamingNormalized()
        if len(seasons) > 1:
            for url, label in seasons:
                season = self._seasonNum(label)
                self.addDir(dict(cItem, category="as_season", good_for_fav=True, url=url, s_season=season, s_url=cItem["url"],
                                 title="%s - %s" % (show, formatSxxExx(season)) if normalize else label))
            return
        self._listEpisodes(dict(cItem, s_season=self._seasonNum(seasons[0][1]) if seasons else 1), data)

    def listSeason(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if sts:
            self._listEpisodes(cItem, data)

    def _listEpisodes(self, cItem, data):
        show = cItem.get("s_title", "")
        season = cItem.get("s_season", 1)
        block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="eplist2 list-eps">', "</ul>", False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="description">', "</div>", False)[1])
        normalize = IsMediaNamingNormalized()
        episodes = []
        for url, title, inner in re.findall(r'<a href="([^"]+)"[^>]*title="([^"]*)"[^>]*>(.*?)</a>', block, re.S):
            url = self._canonUrl(url)
            if url in [e[1] for e in episodes]:
                continue
            num = self.cm.ph.getSearchGroups(inner, r"</strong>\s*(\d+)")[0] or self.cm.ph.getSearchGroups(title, r"(\d+)")[0]
            episodes.append((int(num) if num else 0, url, self.cleanHtmlStr(title) or self.cleanHtmlStr(inner)))
        episodes.sort(key=lambda e: e[0])
        isMovie = len(episodes) == 1 and not episodes[0][0]
        used = {}
        for num, url, title in episodes:
            if normalize and show and num:
                disp = "%s - %s" % (show, formatSxxExx(season, num))
            elif normalize and isMovie:
                disp = cItem.get("title", title)
            else:
                disp = title
            used[disp] = used.get(disp, 0) + 1
            if used[disp] > 1:
                disp = "%s (%d)" % (disp, used[disp])
            self.addVideo({"name": "category", "category": "as_video", "good_for_fav": True, "url": url, "title": disp, "icon": cItem.get("icon", ""),
                           "desc": story, "s_title": show, "s_season": season, "s_episode": num, "s_url": cItem.get("s_url") or cItem["url"],
                           "meta_type": "movie" if isMovie else "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        if not episodes:
            self.addMarker({"title": _("No episodes available yet."), "desc": story})

    def listSearchResult(self, cItem, searchPattern, searchType):
        self.listItems(dict(cItem, category="as_list", url=self.MAIN_URL, search_pattern=searchPattern))

    ###################################################
    # links
    ###################################################
    def _epWatchId(self, data):
        return self.cm.ph.getSearchGroups(data, r'name="epwatch"\s+value="(\d+)"')[0]

    def getLinksForVideo(self, cItem):
        printDBG("Asi1TV.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        epId = self._epWatchId(data)
        if not epId:
            # a movie row keyed on its drama page: the (only) episode page holds the player
            block = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="eplist2 list-eps">', "</ul>", False)[1]
            epUrl = self.cm.ph.getSearchGroups(block, r'<a href="([^"]+)"')[0]
            if epUrl:
                sts, data = self.getPage(epUrl)
                epId = self._epWatchId(data) if sts else ""
        if not epId:
            if "single-vip-btn" in (data or ""):
                # no watch form, only the "gold membership" button: VIP-only title
                SetIPTVPlayerLastHostError(_("This video is Premium-only content."))
            return []
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="description">', "</div>", False)[1])
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer="https://asiawiki.me/")
        sts, raw = self.cm.getPage(AJAX_URL % epId, params)
        if not sts:
            return []
        try:
            servers = json_loads(raw).get("servers", {})
        except Exception:
            printExc()
            return []
        links = []
        for server, html in servers.items():
            link = self.cm.ph.getSearchGroups(html, r'<iframe[^>]+src=["\']([^"\']+)["\']', ignoreCase=True)[0].replace("\\/", "/")
            if link.startswith("//"):
                link = "https:" + link
            if not self.cm.isValidUrl(link) or link in [x["url"] for x in links]:
                continue
            hostName = self.up.getHostName(link, True)
            name = ("%s - %s" % (self.cleanHtmlStr(server), hostName)) if self.cleanHtmlStr(server) else hostName
            if name in [x["name"] for x in links]:
                name = "%s %d" % (name, len(links) + 1)
            links.append({"name": name, "url": link, "need_resolve": 1})
        return applySidecarToLinks(links, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def getVideoLinks(self, url):
        printDBG("Asi1TV.getVideoLinks [%s]" % url)
        sidecar = sidecarFromUrlMeta(url, IsSidecarEnabled())
        if "asiatvplayer.com/embed-" in url:
            return decorateResolvedLinkItems(self.resolveAsiaTvPlayer(url), sidecar)
        if self.cm.isValidUrl(url):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(url), sidecar)
        return []

    def resolveAsiaTvPlayer(self, embedUrl):
        # p.a.c.k.e.d jwplayer setup -> mp4 qualities / HLS master
        header = dict(self.HEADER, Referer="https://asiawiki.me/")
        sts, html = self.cm.getPage(embedUrl, dict(self.defaultParams, header=header))
        if not sts:
            return []
        try:
            code = get_packed_data(html) or html
        except Exception:
            printExc()
            code = html
        meta = {"User-Agent": header["User-Agent"], "Referer": "https://asiawiki.me/"}
        links = []
        for url, label in re.findall(r'file\s*:\s*"([^"]+\.mp4[^"]*)"\s*,\s*label\s*:\s*"([^"]+)"', code):
            links.append({"name": "AsiaTVPlayer %s" % label, "url": strwithmeta(url, dict(meta)), "need_resolve": 0})
        hls = re.findall(r'https?://[^\s\'"]+?\.m3u8[^\s\'"]*', code)
        if hls:
            links.append({"name": "AsiaTVPlayer HLS", "url": strwithmeta(hls[0], dict(meta, iptv_proto="m3u8")), "need_resolve": 0})
        return links

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Asi1TV.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("s_url") or cItem.get("url", ""))
        if sts:
            wrapper = self.cm.ph.getDataBeetwenMarkers(data, '<div class="wrapper-info">', '<div class="description">', False)[1]
            for word, key in INFO_FIELDS:
                val = self.cleanHtmlStr(self.cm.ph.getSearchGroups(wrapper, r"(?s)<span>\s*%s[^<]*</span>(.*?)</div>" % word)[0])
                if val:
                    info[key] = val
            genres = [self.cleanHtmlStr(g) for g in re.findall(r'<a href="[^"]+/genre/[^"]+"[^>]*>([^<]+)<', wrapper)]
            if genres:
                info["genres"] = ", ".join(genres)
            team = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="team">', "</ul>", False)[1]
            names = [self.cleanHtmlStr(n) for n in re.findall(r"<span>([^<]+)</span>", team)]
            names = [n for n in names if n]
            if names:
                info["actors"] = ", ".join(names[:8])
            story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="description">', "</div>", False)[1])
            poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        meta = {}
        title = info.get("original_title") or cItem.get("meta_title", "")
        if cItem.get("meta_type") and title:
            try:
                meta = getMeta(cItem["meta_type"], title, cItem.get("meta_year", ""))
            except Exception:
                printExc()
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
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
        printDBG("Asi1TV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "as_drama_menu":
            self.listDramaMenu(self.currItem)
        elif category == "as_list":
            self.listItems(self.currItem)
        elif category == "as_actors":
            self.listActors(self.currItem)
        elif category == "as_actor":
            self.listActor(self.currItem)
        elif category == "as_series":
            self.listSeries(self.currItem)
        elif category == "as_season":
            self.listSeason(self.currItem)
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
        CHostBase.__init__(self, Asi1TV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("asi1tv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("as_video", "as_series", "as_season")
