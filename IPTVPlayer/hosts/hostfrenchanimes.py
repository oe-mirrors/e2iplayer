# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - French Anime (french-anime.com, French anime VF / VOSTFR, DataLife Engine site): Animes VF, Animes
#     VOSTFR, films, top animes, genres and search; First page / Jump / Next page over /page/N/ (last page
#     read from the page navigation)
#   - Cloudflare challenges every request there (curl-impersonate included, 08.10.2026): pages go through
#     getPageCFProtection (MyE2i solve on the box), covers (/images/ on the same domain) get the same
#     cf_clearance cookie and the User-Agent that passed the check
#   - a series card ("Saison NN") -> episodes, a film card -> one VIDEO row; the episodes and their hoster
#     links come from the hidden "eps" block of the title page ("N!url,url,..."), the hosters go to urlparser
#   - watched flag (title -> episode), downloaded flag (episode rows keyed on "<title page>#ep=N"),
#     favourites, name normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the
#     title page's fields
import os
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return "https://french-anime.com/"


LOCAL_PAGE_SIZE = 100
CARD_START = '<div class="mov clearfix">'
CARD_LINK_RE = re.compile(r'(?s)<a class="mov-t[^"]*" href="([^"]+)"[^>]*>(.*?)</a>')
SEASON_RE = re.compile(r"(?s)Saison\s*(\d+)")
# the hidden episode list of a title page: "1!https://..,https://..\n2!..."
EPS_RE = re.compile(r'(?s)<div class="eps"[^>]*>(.*?)</div>')
EPS_LINE_RE = re.compile(r"(\d+)!([^\s<]+)")
# <li><div class="mov-label">Label:</div> <div class="mov-desc">value</div></li>
FIELD_RE = re.compile(r'(?s)<div class="mov-label">\s*([^<]+?)\s*:?\s*</div>\s*<div class="mov-desc"[^>]*>(.*?)</div>\s*</li>')
VIDEO_CATEGORIES = ("fa_video",)
FOLDER_CATEGORIES = ("fa_show",)


class FrenchAnimes(GenericFolderWatchedScraperMixin, CBaseHostClass):

    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "show_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "frenchanimes", "cookie": "frenchanimes.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/frenchanimes135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("frenchanimes")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        # "<title page>#ep=N" of the episode rows: the fragment is ours, not the site's
        url = self.getFullUrl((baseUrl or "").split("#", 1)[0].replace("&amp;", "&"))
        return self.cm.getPageCFProtection(url, addParams, post_data)

    def _path(self, url):
        # domain independent identity of a page (the episode fragment stays part of it)
        return re.sub(r"^https?://[^/]+", "", url or "").rstrip("/").lower()

    def _cfMeta(self):
        # cf_clearance + the User-Agent that passed the check, for downloads outside getPage (covers)
        meta = {"Referer": self.MAIN_URL}
        try:
            # getCookieHeader logs a traceback for a cookie file that does not exist yet
            cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
            if cookieHeader:
                meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
        except Exception:
            printExc()
        return meta

    def getFullIconUrl(self, url, currUrl=None):
        # the covers (/images/ on the site) sit behind the same Cloudflare check as the pages
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        if not url.startswith("http") or not self.up.getDomain(url).endswith("french-anime.com"):
            return url
        return strwithmeta(url, self._cfMeta())

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in VIDEO_CATEGORIES + FOLDER_CATEGORIES + ("fa_list",):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            category = cItem.get("category", "")
            if category in VIDEO_CATEGORIES:
                return "video:%s" % path
            if category in FOLDER_CATEGORIES:
                return "folder:%s" % path
        except Exception:
            printExc()
        return ""

    @staticmethod
    def _episodes(data):
        # [(number, [hoster urls])] of the title page's "eps" block, in episode order
        block = EPS_RE.search(data or "")
        episodes = {}
        for number, links in EPS_LINE_RE.findall(block.group(1) if block else ""):
            urls = episodes.setdefault(int(number), [])
            for link in links.split(","):
                link = link.strip()
                if link.startswith("//"):
                    link = "https:" + link
                if link.startswith("http") and link not in urls:
                    urls.append(link)
        return sorted((number, urls) for number, urls in episodes.items() if urls)

    @staticmethod
    def _cards(data):
        # the cards of a list page: <div class="mov clearfix"> .. up to the next one (the pager / sidebar cut off)
        content = data.split("id='dle-content'", 1)[-1].split('<div class="pagi-nav', 1)[0].split("<aside", 1)[0]
        return content.split(CARD_START)[1:]

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self):
        menu = [
            {"category": "fa_list", "good_for_fav": True, "title": "Animes VF", "url": self.getFullUrl("/animes-vf/")},
            {"category": "fa_list", "good_for_fav": True, "title": "Animes VOSTFR", "url": self.getFullUrl("/animes-vostfr/")},
            {"category": "fa_list", "good_for_fav": True, "title": _("Movies"), "url": self.getFullUrl("/films-vf-vostfr/")},
            {"category": "fa_list", "good_for_fav": True, "title": _("Popular"), "url": self.getFullUrl("/exclue/")},
            # the genre box sits in the sidebar of the list pages
            {"category": "fa_genres", "title": _("Genres"), "url": self.getFullUrl("/animes-vf/")},
        ]
        self.listsTab(menu + self.searchItems(), {"name": "category"})

    def listGenres(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, ">Animes par genre<", "</ul>", False)[1]
        genres = []
        for href, label in re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', block):
            title = self.cleanHtmlStr(label)
            if title:
                genres.append((title, self.getFullUrl(href)))
        for title, url in sorted(genres):
            self.addDir({"name": "category", "category": "fa_list", "good_for_fav": True, "title": title, "url": url})

    def _addCard(self, card):
        found = CARD_LINK_RE.search(card)
        if not found:
            return False
        url, name = found.group(1), self.cleanHtmlStr(found.group(2))
        if not name:
            name = re.sub(r"\s+(?:wiflix|flemmix)\s*$", "", self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'alt="([^"]+)"')[0]))
        if not url or not name:
            return False
        fields = dict((self.cleanHtmlStr(label).rstrip(":").lower(), self.cleanHtmlStr(value))
                      for label, value in re.findall(r'(?s)<div class="ml-label">(.*?)</div>\s*<div class="ml-desc">(.*?)</div>', card))
        year = self.cm.ph.getSearchGroups(fields.get("date de sortie", ""), r"((?:19|20)\d{2})")[0]
        icon = self.cm.ph.getSearchGroups(card, r'<img src="([^"]+)"')[0]
        version = fields.get("version", "") or self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<span class="nbloc1">(.*?)</span>')[0])
        sai = self.cm.ph.getSearchGroups(card, r'(?s)<span class="block-sai">(.*?)</span>')[0]
        lastEp = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<div class="block-ep">(.*?)</div>')[0])
        info = " | ".join(x for x in ("%s: %s" % (_("Year"), year) if year else "", version, lastEp) if x)
        story = fields.get("synopsis", "")
        desc = "%s[/br]%s" % (info, story) if info and story else (info or story)
        params = {"name": "category", "good_for_fav": True, "url": url, "desc": desc, "icon": self.getFullIconUrl(icon) if icon else "",
                  "s_title": name, "meta_title": name, "meta_year": year}
        if sai:
            season = SEASON_RE.search(sai)
            params.update({"category": "fa_show", "title": name, "s_season": int(season.group(1)) if season else 1, "meta_type": "tv"})
            self.addDir(params)
        else:
            withYear = year and IsMediaNamingNormalized()
            params.update({"category": "fa_video", "title": "%s (%s)" % (name, year) if withYear else name, "meta_type": "movie"})
            self.addVideo(params)
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        baseUrl = cItem.get("base_url") or cItem["url"]
        url = baseUrl if page <= 1 else "%spage/%d/" % (baseUrl, page)
        printDBG("FrenchAnimes.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        count = 0
        for card in self._cards(data):
            if self._addCard(card):
                count += 1
        nav = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagi-nav', "</div>", False)[1]
        pages = [int(n) for n in re.findall(r">(\d+)</a>", nav)]
        lastPage = max(pages + [page]) if pages else 0
        hasNext = bool(count) and ("/page/%d/" % (page + 1)) in nav
        listItem = dict(cItem, base_url=baseUrl, url=baseUrl)
        addPagingItems(self, listItem, page, hasNext, lastPage, baseUrl.replace("{", "{{").replace("}", "}}") + "page/{page}/")

    def listShow(self, cItem):
        printDBG("FrenchAnimes.listShow [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        episodes = self._episodes(data)
        if not episodes:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        # the pager rows carry the title "Next page": page 2+ keeps the folder's own title
        folderTitle = cItem.get("folder_title") or cItem.get("title", show)
        season = cItem.get("s_season", 1)
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for number, urls in episodes[start:start + LOCAL_PAGE_SIZE]:
            if IsMediaNamingNormalized():
                title = "%s - %s" % (show, formatSxxExx(season, number))
            else:
                title = "%s - %s %d" % (folderTitle, _("Episode"), number)
            self.addVideo({"name": "category", "category": "fa_video", "good_for_fav": True, "url": "%s#ep=%d" % (cItem["url"], number),
                           "title": title, "icon": cItem.get("icon", ""), "desc": ", ".join(self.up.getDomain(u) for u in urls),
                           "show_url": cItem["url"], "s_title": show, "s_season": season, "s_episode": str(number),
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, folder_title=folderTitle), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        pattern = cItem.get("s_pattern") or searchPattern.strip()
        page = cItem.get("page", 1)
        printDBG("FrenchAnimes.listSearchResult [%s] page %d" % (pattern, page))
        # DataLife Engine search, the page goes in search_start
        pageTpl = self.getFullUrl("/index.php?do=search&subaction=search&full_search=0&story=%s&search_start=" % urllib_quote_plus(pattern)) + "{page}"
        sts, data = self.getPage(pageTpl.format(page=page))
        if not sts:
            return
        count = 0
        for card in self._cards(data):
            if self._addCard(card):
                count += 1
        hasNext = bool(count) and ("list_submit(%d)" % (page + 1)) in data
        nav = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagi-nav', "</div>", False)[1]
        pages = [int(n) for n in re.findall(r"list_submit\((\d+)\)", nav)]
        listItem = dict(cItem, s_pattern=pattern)
        addPagingItems(self, listItem, page, hasNext, max(pages + [page]) if pages else 0, pageTpl)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("FrenchAnimes.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        episodes = self._episodes(data)
        wanted = self.cm.ph.getSearchGroups(url, r"#ep=(\d+)$")[0]
        if wanted:
            episodes = [e for e in episodes if str(e[0]) == wanted]
        urltab = []
        for number, urls in episodes:
            for link in urls:
                host = self.up.getDomain(link)
                name = host if len(episodes) == 1 else "%s - %s %d" % (host, _("Episode"), number)
                urltab.append({"name": name, "url": strwithmeta(link, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("FrenchAnimes.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecarFromUrlMeta(videoUrl, IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # (story, poster, {INFO fields}) of a title page
        fields = dict((self.cleanHtmlStr(label).lower(), self.cleanHtmlStr(value)) for label, value in FIELD_RE.findall(data or ""))
        info = {}
        for key, label in (("original_title", "titre original"), ("genres", "genre"), ("actors", "acteurs"),
                           ("director", "réalisateur"), ("language", "version"), ("duration", "durée")):
            if fields.get(label):
                info[key] = fields[label]
        year = self.cm.ph.getSearchGroups(fields.get("date de sortie", ""), r"((?:19|20)\d{2})")[0]
        if year:
            info["year"] = year
        poster = self.cm.ph.getSearchGroups(data or "", r'id="posterimg"\s+src="([^"]+)"')[0]
        return fields.get("synopsis", ""), poster, info

    def getArticleContent(self, cItem):
        printDBG("FrenchAnimes.getArticleContent [%s]" % cItem.get("url", ""))
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("show_url") or cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        title = cItem.get("meta_title") or cItem.get("s_title") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(cItem.get("meta_type") or "tv", title, cItem.get("meta_year") or info.get("year", ""))
        except Exception:
            printExc()
        siteInfo = dict(info)
        info.update(meta.get("info", {}))
        info.update(dict((k, v) for k, v in siteInfo.items() if k in ("language", "original_title")))
        plot = meta.get("plot", "")
        text = story or plot or cItem.get("desc", "")
        if plot and story and plot != story:
            text = "%s[/br][/br]%s" % (story, plot)
        icon = (self.getFullIconUrl(poster) if poster else "") or meta.get("poster") or cItem.get("icon", "")
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
        printDBG("FrenchAnimes.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu()
        elif category == "fa_list":
            self.listItems(self.currItem)
        elif category == "fa_genres":
            self.listGenres(self.currItem)
        elif category == "fa_show":
            self.listShow(self.currItem)
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
        CHostBase.__init__(self, FrenchAnimes(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("frenchanimes")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in VIDEO_CATEGORIES + FOLDER_CATEGORIES
