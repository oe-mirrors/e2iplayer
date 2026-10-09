# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard (showbox.media):
#   - home sections, movies, 4K movies, TV shows, top IMDb, genres, countries and search, with First page /
#     Jump / Next page (n/last when the site's pager shows it)
#   - TV shows -> seasons (only when there are more than one) -> episodes (tv/episode); movies and episodes
#     are VIDEO rows on their page url
#   - links: the site's files live on FebBox (febbox.com/mbp/to_share_page -> file_share_list): one link per
#     file (episodes: the "season N" folder, SxxEyy in the file name); the stream urls of a file
#     (console/video_quality_list) need a FebBox login - the "ui" cookie of the user's own FebBox account
#     in the host settings (MOHAMED_OS's urlparser part sent two built-in account tokens instead)
#   - watched flag (show -> season -> episode), downloaded flag, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the site's story/IMDb/details;
#     no colour codes in titles
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigSecret
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, E2ColoR, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.showbox_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.showbox_alt_domain = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.showbox_febbox_token = ConfigSecret(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("FebBox token (\"ui\" cookie of www.febbox.com):"), config.plugins.iptvplayer.showbox_febbox_token))
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.showbox_proxy))
    if config.plugins.iptvplayer.showbox_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.showbox_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://www.showbox.media/"


FEBBOX_URL = "https://www.febbox.com/"
YEAR_RE = re.compile(r"-((?:19|20)\d{2})$")
EPISODE_RE = re.compile(r"Eps\s*(\d+)", re.I)
DETAIL_FIELDS = (("Released", "released"), ("Duration", "duration"), ("Country", "country"), ("Production", "production"),
                 ("Latest Episode", "last_air_date"))


class ShowBox(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "season_id", "tid",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "showbox", "cookie": "showbox.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/showbox135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*; q=0.01"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("showbox")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.showbox_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        if ShowBox.DOMAIN_CACHE:
            self.MAIN_URL = ShowBox.DOMAIN_CACHE
            return
        domains = [gettytul()]
        domain = config.plugins.iptvplayer.showbox_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.getPage(domain)
            if sts and "flw-item" in data:
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", domain))
                break
        else:
            self.MAIN_URL = domains[-1]
        ShowBox.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / old lists on a previous domain -> the current one (FebBox urls stay as they are)
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
        if FEBBOX_URL[8:-1] in url:
            return url
        m = re.match(r"https?://[^/]+/(.*)$", url)
        return (self.MAIN_URL + m.group(1)) if m else self.getFullUrl(url)

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        if not url.startswith("http"):
            return url
        meta = {"Referer": self.getMainUrl()}
        proxy = self.getProxy()
        if proxy:
            meta["iptv_http_proxy"] = proxy
        return strwithmeta(url, meta)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("sb_video", "sb_series", "sb_season"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    @staticmethod
    def _path(url):
        m = re.match(r"https?://[^/]+(/[^#?]*)", url or "")
        return m.group(1).rstrip("/") if m else ""

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            if category == "sb_video":
                if cItem.get("s_episode"):
                    return "episode:%s|%s|%s" % (path, cItem.get("s_season", 0), cItem["s_episode"])
                return "video:%s" % path
            if category == "sb_series":
                return "series:%s" % path
            if category == "sb_season":
                return "season:%s|%s" % (path, cItem.get("s_season", 0))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "sb_home", "title": _("Home")},
            {"category": "list_items", "title": _("Movies"), "url": self.getFullUrl("/movie"), "good_for_fav": True},
            {"category": "list_items", "title": "%s 4K" % _("Movies"), "url": self.getFullUrl("/movie?quality=4K&release_year=all&genre=all&rating=all"), "good_for_fav": True},
            {"category": "list_items", "title": _("TV Shows"), "url": self.getFullUrl("/tv"), "good_for_fav": True},
            {"category": "list_items", "title": "%s (IMDb)" % _("Top rated"), "url": self.getFullUrl("/index/top_imdb"), "good_for_fav": True},
            {"category": "sb_sidebar", "title": _("Genre"), "box": "sidebar_subs_genre"},
            {"category": "sb_sidebar", "title": _("Country"), "box": "sidebar_subs_country"},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listHome(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        for heading in self.cm.ph.getAllItemsBeetwenMarkers(data, ('<h2', '>', 'cat-heading'), ('</h2', '>')):
            title = self.cleanHtmlStr(heading)
            if title:
                self.addDir({"name": "category", "category": "sb_section", "title": title, "section": title, "good_for_fav": True})

    def listSection(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, ">%s<" % cItem.get("section", ""), "</section", False)[1]
        self._listRows(block, set())

    def listSidebar(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="%s"' % cItem.get("box", ""), "</ul>", False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            title = self.cleanHtmlStr(item)
            if href and title:
                self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": self._rebase(href)})

    def _listRows(self, data, seen):
        normalize = IsMediaNamingNormalized()
        count = 0
        for item in self.cm.ph.getAllItemsBeetwenMarkers(data, ('<div', '>', 'flw-item'), ('<div', '>', 'clearfix')):
            href = self.cm.ph.getSearchGroups(item, r'href="(/(?:movie|tv)/[^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            if not href or not title:
                continue
            url = self._rebase(href)
            if url in seen:
                continue
            seen.add(url)
            count += 1
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            infos = [self.cleanHtmlStr(x) for x in re.findall(r'(?s)class="fdi-item[^"]*">(.*?)</span>', item)]
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)film-poster-quality">(.*?)</div>')[0])
            year = self.cm.ph.getSearchGroups(href, YEAR_RE.pattern)[0]
            desc = " | ".join([x for x in [quality] + infos if x])
            if year and year not in desc:
                desc = "%s%s:%s %s | %s" % (E2ColoR("cyan"), _("Year"), E2ColoR("white"), year, desc) if desc else year
            params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc, "meta_title": title, "meta_year": year}
            if "/tv/" in href:
                params.update({"category": "sb_series", "title": title, "s_title": title, "meta_type": "tv"})
                self.addDir(params)
            else:
                params.update({"category": "sb_video", "title": ("%s (%s)" % (title, year)) if normalize and year else title, "meta_type": "movie"})
                self.addVideo(params)
        return count

    def listItems(self, cItem):
        page = int(cItem.get("page", 1) or 1)
        url = self._rebase(cItem["url"])
        printDBG("ShowBox.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, ('<div', '>', 'film_list-wrap'), "</section", False)[1] or data
        count = self._listRows(block, set())
        # pager: "?page=N" / "&page=N" links, numbers only on some lists
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', "</ul>", False)[1]
        nums = [int(n) for n in re.findall(r"<a[^>]*>\s*(\d+)\s*</a>", pager)]
        lastPage = max(nums + [page]) if nums else 0
        pageTpl = ""
        hasNext = False
        for href in re.findall(r'href="([^"#]+)"', pager):
            href = self._rebase(href)
            if re.search(r"[?&]page=%d(?:&|$)" % (page + 1), href):
                hasNext = True
            tpl = re.sub(r"([?&]page=)\d+", r"\1{page}", href, 1)
            if "{page}" in tpl:
                pageTpl = tpl
        if hasNext and lastPage <= page:
            # prev / current / next pager without the page count
            lastPage = 0
        listItem = dict(cItem)
        listItem["category"] = "list_items"
        addPagingItems(self, listItem, page, count > 0 and hasNext, lastPage, pageTpl)

    def _seasons(self, data):
        # [(season number, show id, label)] of the "slt-seasons-dropdown" box
        box = self.cm.ph.getDataBeetwenMarkers(data, "slt-seasons-dropdown", "</div>\n", False)[1] or data
        seasons = []
        for attrs, label in re.findall(r'(?s)<a([^>]*data-tid="[^"]+"[^>]*)>(.*?)</a>', box):
            num = self.cm.ph.getSearchGroups(attrs, r'data-id="(\d+)"')[0]
            tid = self.cm.ph.getSearchGroups(attrs, r'data-tid="(\d+)"')[0]
            if num and tid:
                seasons.append((int(num), tid, self.cleanHtmlStr(label)))
        return seasons

    def listSeries(self, cItem):
        printDBG("ShowBox.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        seasons = self._seasons(data)
        if len(seasons) == 1:
            self.listEpisodes(dict(cItem, s_season=seasons[0][0], tid=seasons[0][1]))
            return
        normalize = IsMediaNamingNormalized()
        for num, tid, label in seasons:
            title = ("%s - %s" % (cItem.get("s_title", ""), formatSxxExx(num))) if normalize else (label or "%s %d" % (_("Season"), num))
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "sb_season", "title": title, "s_season": num, "tid": tid})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("ShowBox.listEpisodes [%s|%s]" % (cItem.get("tid", ""), cItem.get("s_season", "")))
        season = cItem.get("s_season", 1)
        params = dict(self.defaultParams)
        params["header"] = dict(self.AJAX_HEADER, Referer=self._rebase(cItem.get("url", "")))
        sts, data = self.getPage(self.getFullUrl("/tv/episode?%s" % urllib_urlencode({"id": cItem.get("tid", ""), "season": season})), params)
        if not sts:
            return
        try:
            # a JSON string with the HTML of the episode list
            data = "%s" % json_loads(data)
        except Exception:
            printExc()
        show = cItem.get("s_title", "") or cItem.get("title", "")
        normalize = IsMediaNamingNormalized()
        baseUrl = cItem.get("url", "").split("#")[0]
        for attrs in re.findall(r'<a([^>]*class="[^"]*eps-item[^"]*"[^>]*)>', data):
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(attrs, r'title="([^"]+)"')[0])
            num = self.cm.ph.getSearchGroups(label, EPISODE_RE.pattern)[0]
            if not num:
                continue
            title = "%s - %s" % (show, formatSxxExx(season, num)) if normalize else "%s - %s" % (show, label)
            item = dict(cItem)
            item.update({"category": "sb_video", "good_for_fav": True, "title": title, "url": "%s#s%se%s" % (baseUrl, season, num),
                         "s_season": season, "s_episode": num, "desc": label})
            self.addVideo(item)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ShowBox.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/search?keyword=%s" % urllib_quote_plus(searchPattern.strip())), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links (FebBox)
    ###################################################
    def _febbox(self, path, params, extra=None):
        header = dict(self.HEADER)
        header.update(extra or {})
        sts, data = self.cm.getPage("%s%s?%s" % (FEBBOX_URL, path, urllib_urlencode(params)), {"header": header})
        if not sts:
            return {}
        try:
            return json_loads(data)
        except Exception:
            printExc()
        return {}

    @staticmethod
    def _files(answer):
        files = (answer.get("data") or {}).get("file_list") if isinstance(answer, dict) else None
        return [f for f in files or [] if isinstance(f, dict) and f.get("fid")]

    def getLinksForVideo(self, cItem):
        printDBG("ShowBox.getLinksForVideo [%s]" % cItem.get("url", ""))
        season = cItem.get("s_season", 0) if cItem.get("s_episode") else 0
        mid = cItem.get("tid", "")
        if not season:
            sts, data = self.getPage(cItem.get("url", "").split("#")[0])
            if not sts:
                return []
            mid = self.cm.ph.getSearchGroups(data, r'/movie/detail/(\d+)')[0]
        if not mid:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        share = self._febbox("mbp/to_share_page", {"box_type": "2" if season else "1", "mid": mid, "json": "1"})
        shareData = share.get("data") or {} if isinstance(share, dict) else {}
        shareKey = shareData.get("link") or ("%s" % shareData.get("share_link", "")).rstrip("/").split("/")[-1]
        if not shareKey:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        files = self._files(self._febbox("file/file_share_list", {"share_key": shareKey}))
        if season:
            folder = [f["fid"] for f in files if f.get("is_dir") and ("%s" % f.get("file_name", "")).strip().lower() == "season %s" % season]
            files = self._files(self._febbox("file/file_share_list", {"share_key": shareKey, "parent_id": folder[0], "page": "1"})) if folder else []
            tag = "s%02de%02d" % (int(season), int(cItem["s_episode"]))
            files = [f for f in files if tag in ("%s" % f.get("file_name", "")).lower()]
        urltab = []
        # best resolution first (from the release name, "...2160p...")
        files.sort(key=lambda f: -int(self.cm.ph.getSearchGroups("%s" % f.get("file_name", ""), r"(?i)(\d{3,4})p")[0] or 0))
        for f in files:
            if f.get("is_dir"):
                continue
            name = "%s (%s)" % (f.get("file_name", ""), f.get("file_size", "")) if f.get("file_size") else f.get("file_name", "")
            urltab.append({"name": name, "url": "%sshare/%s#fid=%s" % (FEBBOX_URL, shareKey, f["fid"]), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def _febboxStreams(self, shareKey, fid):
        token = config.plugins.iptvplayer.showbox_febbox_token.value.strip()
        if not token:
            printDBG("ShowBox._febboxStreams: no FebBox \"ui\" token in the host configuration -> login message")
            SetIPTVPlayerLastHostError(_("ShowBox streams need a FebBox login: enter the \"ui\" cookie of your FebBox account in the host configuration."))
            return []
        extra = {"Origin": FEBBOX_URL[:-1], "Referer": "%sshare/%s" % (FEBBOX_URL, shareKey), "X-Requested-With": "XMLHttpRequest",
                 "Accept": "text/plain, */*; q=0.01", "Cookie": "ui=%s" % token}
        answer = self._febbox("console/video_quality_list", {"share_key": shareKey, "fid": fid}, extra)
        html = answer.get("html", "") if isinstance(answer, dict) else ""
        if not html:
            SetIPTVPlayerLastHostError("FebBox: %s" % (answer.get("msg") if isinstance(answer, dict) and answer.get("msg") else _("No stream available")))
            return []
        links = []
        parts = re.split(r"(?=<[^>]+data-url=)", html)
        for part in parts:
            url = self.cm.ph.getSearchGroups(part, r"""data-url=['"]([^'"]+)""")[0].replace("&amp;", "&")
            if not self.cm.isValidUrl(url):
                continue
            quality = self.cm.ph.getSearchGroups(part, r"""data-quality=['"]([^'"]+)""")[0]
            if quality.upper() == "ORG":
                quality = self.cm.ph.getSearchGroups(url, r"(\d{3,4}p)")[0] or "Original"
            size = self.cleanHtmlStr(self.cm.ph.getSearchGroups(part, r"""class=['"]size['"]>([^<]+)<""")[0])
            name = " ".join([x for x in (quality, "(%s)" % size if size else "") if x]) or "FebBox"
            links.append({"name": name, "url": strwithmeta(url, {"User-Agent": self.HEADER.get("User-Agent", ""), "Referer": FEBBOX_URL}), "need_resolve": 0})
        return links

    def getVideoLinks(self, videoUrl):
        printDBG("ShowBox.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        m = re.search(r"febbox\.com/share/([^/#?]+)#fid=(\d+)", "%s" % videoUrl)
        if m:
            return decorateResolvedLinkItems(self._febboxStreams(m.group(1), m.group(2)), sidecar)
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        box = self.cm.ph.getDataBeetwenMarkers(data, ('<div', '>', 'detail_page-infor'), ('<div', '>', 'detail-tags'), False)[1]
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(box, ('<div', '>', 'description'), ('</div', '>'), False)[1])
        info = {}
        imdb = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r'(?s)btn-imdb">(.*?)</button>')[0]).replace("IMDB:", "").strip()
        if imdb:
            info["imdb_rating"] = imdb
        quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r'(?s)btn-quality">(.*?)</button>')[0])
        if quality:
            info["quality"] = quality
        rows = dict((self.cleanHtmlStr(k).rstrip(":"), self.cleanHtmlStr(v)) for k, v in
                    re.findall(r'(?s)<div class="row-line"><span class="type"><strong>(.*?)</strong></span>(.*?)</div>', box))
        for label, key in DETAIL_FIELDS:
            if rows.get(label) and rows[label] != "无":
                info[key] = rows[label]
        # the site puts the genres under "Casts:" and leaves "Genre:" empty
        genre = rows.get("Genre") or rows.get("Casts")
        if genre:
            info["genres"] = genre.replace(",", ", ")
        poster = self.cm.ph.getSearchGroups(box, r'<img[^>]+src="([^"]+)"')[0]
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getArticleContent(self, cItem):
        printDBG("ShowBox.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""))
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", "").split("#")[0])
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or StripColorCodes(cItem.get("desc", ""))
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or poster or cItem.get("icon", "")
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}] if icon else [], "other_info": info}]

    ###################################################
    # service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern="", searchType=""):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("ShowBox.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "sb_home":
            self.listHome(self.currItem)
        elif category == "sb_section":
            self.listSection(self.currItem)
        elif category == "sb_sidebar":
            self.listSidebar(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "sb_series":
            self.listSeries(self.currItem)
        elif category == "sb_season":
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
        CHostBase.__init__(self, ShowBox(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("showbox")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("sb_video", "sb_series", "sb_season")
