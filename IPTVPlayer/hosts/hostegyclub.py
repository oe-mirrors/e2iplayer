# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# EgyClub (ايجي كلوب, my.egy-club.com): WordPress site with older world cinema (1930s-1990s classics,
# Italian/French/Asian/Hindi films) with Arabic subtitles
#   - catalogue from the site's WordPress REST API: "Latest", the site categories (largest first) and search,
#     First page / Jump / Next page (page count from X-WP-TotalPages)
#   - every post is one film (VIDEO row on the post url); "Title (Year)" from the Arabic post title
#   - links: the post page's server list - the active server's iframe is in the page, the others come from
#     the theme's Inc/Ajax/Single/Server.php (POST id + i); today vidmoly (.biz/.org), older posts vidmoly.to /
#     updown / streamtape / uqload (most of those files are gone on the hoster side)
#   - links of hosters urlparser has no parser for (verystream, streamango, vidlox ... - closed years ago) are
#     left out (09.10.2026)
#   - watched flag, downloaded flag, favourites (urls re-based on the current domain), sidecar, INFO via
#     moviemeta (the titles are the original Latin titles + year) + the site's poster/category/date
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, E2ColoR, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.egyclub_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.egyclub_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.egyclub_proxy))
    if config.plugins.iptvplayer.egyclub_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.egyclub_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://my.egy-club.com/"


PER_PAGE = 30
POST_FIELDS = "id,title,link,date,categories,yoast_head_json.og_image"
SERVER_AJAX = "wp-content/themes/Elshaikh/Inc/Ajax/Single/Server.php"
YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d{2})(?=\s|\)|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مشاهدة|مشاهدم|الفيلم|فيلم|المميز|مترجم|مترجمة|كامل|اون لاين|اونلاين|أون لاين|ترجمة|حصرية|حصريا|HD)(?=\s|$)")
TAG_LI_RE = re.compile(r"<li\s([^>]*)>")
TAG_IFRAME_RE = re.compile(r"<iframe\s([^>]*)>")
SRC_RE = re.compile(r"""src=["']([^"']*)["']""")
# download pages, not playable
SKIP_HOSTERS = ("megaup.net",)


class EgyClub(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "post_id", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "egyclub", "cookie": "egyclub.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/egyclub135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.categories = None
        self.watchedHelper = IPTVWatchedHelper("egyclub")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.egyclub_proxy.value) or None

    def _params(self, addParams=None):
        params = dict(addParams if addParams is not None else self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in params:
            params = MergeDicts(params, {"http_proxy": proxy})
        return params

    def getPage(self, baseUrl, addParams=None, post_data=None):
        return self.cm.getPageCFProtection(self._rebase(baseUrl), self._params(addParams), post_data)

    def selectDomain(self):
        if EgyClub.DOMAIN_CACHE:
            self.MAIN_URL = EgyClub.DOMAIN_CACHE
            return
        domains = [gettytul()]
        domain = config.plugins.iptvplayer.egyclub_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.cm.getPageCFProtection(domain + "wp-json/", self._params())
            if sts and '"namespaces"' in data:
                break
        else:
            self.MAIN_URL = domains[-1]
        EgyClub.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / old lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
        m = re.match(r"https?://[^/]+/(.*)$", url)
        return (self.MAIN_URL + m.group(1)) if m else self.getFullUrl(url)

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    def _api(self, endpoint):
        # (json, X-WP-TotalPages) of a REST call
        params = self._params()
        params.update({"with_metadata": True, "collect_all_headers": True})
        sts, data = self.getPage(self.getFullUrl("/wp-json/wp/v2/" + endpoint), params)
        if not sts:
            return None, 0
        try:
            total = int((getattr(data, "meta", None) or {}).get("x-wp-totalpages", 0) or 0)
        except (TypeError, ValueError):
            total = 0
        try:
            return json_loads(data), total
        except Exception:
            printExc()
        return None, 0

    def _splitTitle(self, title):
        # "مشاهدة فيلم A Kiss Before Dying 1956 مترجم" -> ("A Kiss Before Dying", "1956")
        # "فيلم 1972 The Grand Duel / Il grande duello مترجم" -> ("The Grand Duel / Il grande duello", "1972")
        years = YEAR_RE.findall(title)
        year = years[-1] if years else ""
        name = JUNK_RE.sub(" ", title)
        if year:
            name = re.sub(r"\(?\b%s\b\)?" % year, " ", name)
        name = re.sub(r"\s+", " ", name).strip(" -:|/")
        return name, year

    def _categoryNames(self):
        if self.categories is None:
            cats, _total = self._api("categories?per_page=100&hide_empty=true&_fields=id,name,count")
            self.categories = cats if isinstance(cats, list) else []
        return {c.get("id"): self.cleanHtmlStr(c.get("name", "")) for c in self.categories}

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") == "ec_video":
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if isinstance(cItem, dict) and cItem.get("category") == "ec_video":
                postId = cItem.get("post_id", "")
                return ("post:%s" % postId) if postId else ("url:%s" % cItem.get("url", "").rstrip("/").rsplit("/", 1)[-1])
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "ec_posts", "title": _("Latest"), "good_for_fav": True},
            {"category": "ec_categories", "title": _("Categories")},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listCategories(self, cItem):
        self._categoryNames()
        for cat in sorted(self.categories, key=lambda c: -int(c.get("count", 0) or 0)):
            title = self.cleanHtmlStr(cat.get("name", ""))
            if not title or not cat.get("count"):
                continue
            self.addDir({"name": "category", "category": "ec_posts", "good_for_fav": True, "title": "%s (%s)" % (title, cat["count"]), "cat_id": cat["id"]})

    def listPosts(self, cItem):
        page = cItem.get("page", 1)
        endpoint = "posts?per_page=%d&page=%d&_fields=%s" % (PER_PAGE, page, POST_FIELDS)
        if cItem.get("cat_id"):
            endpoint += "&categories=%s" % cItem["cat_id"]
        if cItem.get("search"):
            endpoint += "&search=%s" % urllib_quote_plus(cItem["search"])
        printDBG("EgyClub.listPosts [%s]" % endpoint)
        posts, total = self._api(endpoint)
        if not isinstance(posts, list):
            return
        names = self._categoryNames()
        normalize = IsMediaNamingNormalized()
        for post in posts:
            rawTitle = self.cleanHtmlStr((post.get("title") or {}).get("rendered", ""))
            url = post.get("link", "")
            if not rawTitle or not url:
                continue
            name, year = self._splitTitle(rawTitle)
            icon = ""
            images = (post.get("yoast_head_json") or {}).get("og_image") or []
            if images and isinstance(images[0], dict):
                icon = self.getFullIconUrl(images[0].get("url", ""))
            genres = ", ".join([names[c] for c in post.get("categories", []) if names.get(c)])
            fields = ((_("Year"), year, "cyan"), (_("Genre"), genres, "green"), (_("Added"), (post.get("date") or "")[:10], "yellow"))
            desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
            title = rawTitle
            if normalize and name:
                title = "%s (%s)" % (name, year) if year else name
            self.addVideo({"name": "category", "category": "ec_video", "good_for_fav": True, "title": title, "url": self._rebase(url), "icon": icon,
                           "desc": desc, "post_id": post.get("id", ""), "meta_type": "movie", "meta_title": name.split(" / ")[0] or rawTitle,
                           "meta_year": year})
        listItem = dict(cItem)
        listItem.update({"category": "ec_posts"})
        # listPosts builds the request from cItem["page"]: the REST url as the template only enables "Jump"
        pageTpl = self.getFullUrl("/wp-json/wp/v2/" + endpoint.replace("&page=%d&" % page, "&page={page}&"))
        addPagingItems(self, listItem, page, page < total, total, pageTpl)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("EgyClub.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "ec_posts", "search": searchPattern.strip(), "page": 1})
        self.listPosts(cItem)

    ###################################################
    # links
    ###################################################
    def _servers(self, data):
        # [(data-i, data-id, label)] of the "سيرفرات المشاهدة" list
        out = []
        for attrs in TAG_LI_RE.findall(data):
            cls = self.cm.ph.getSearchGroups(attrs, r'class="([^"]*)"')[0]
            postId = self.cm.ph.getSearchGroups(attrs, r'data-id="(\d+)"')[0]
            if "server--item" in cls and postId:
                out.append((self.cm.ph.getSearchGroups(attrs, r'data-i="(\d+)"')[0] or "0", postId, "active" in cls))
        return out

    def _iframeSrc(self, data):
        for attrs in TAG_IFRAME_RE.findall(data or ""):
            src = self.cm.ph.getSearchGroups(attrs, SRC_RE.pattern)[0]
            if src:
                return src
        return ""

    def getLinksForVideo(self, cItem):
        printDBG("EgyClub.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._rebase(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        frames = []
        player = self.cm.ph.getDataBeetwenMarkers(data, 'class="player--iframe"', "</iframe>", False)[1]
        for num, postId, active in self._servers(data):
            frame = self._iframeSrc(player) if active else ""
            if not frame:
                params = self._params()
                params["header"] = dict(self.HEADER, Referer=pageUrl, **{"X-Requested-With": "XMLHttpRequest"})
                sts, answer = self.getPage(self.getFullUrl("/" + SERVER_AJAX), params, {"id": postId, "i": num})
                if sts:
                    frame = self._iframeSrc(answer) or answer.strip()
            frames.append(frame.replace("&amp;", "&").strip())
        if not frames:
            # posts without a server list: the player iframe alone
            frames.append(self._iframeSrc(player))
        urltab = []
        seen = set()
        for frame in frames:
            frame = "https:" + frame if frame.startswith("//") else frame
            if not self.cm.isValidUrl(frame) or frame in seen or any(h in frame for h in SKIP_HOSTERS):
                continue
            seen.add(frame)
            if self.up.checkHostSupport(frame) != 1:
                # hosters closed years ago (verystream, streamango, vidlox, openload ... on the 2019/2020 posts)
                # have no parser - such a link could never play
                printDBG("EgyClub.getLinksForVideo skip unsupported [%s]" % frame)
                continue
            domain = self.cm.ph.getSearchGroups(frame, r"https?://(?:www\.)?([^/:]+)")[0]
            urltab.append({"name": "%s %d (%s)" % (_("Server"), len(urltab) + 1, domain), "url": strwithmeta(frame, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("EgyClub.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("EgyClub.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem.get("meta_type", "movie"), cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        info = {}
        if cItem.get("meta_year"):
            info["year"] = cItem["meta_year"]
        info.update(meta.get("info", {}))
        text = meta.get("plot", "") or StripColorCodes(cItem.get("desc", ""))
        icon = meta.get("poster") or cItem.get("icon", "")
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
        printDBG("EgyClub.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "ec_categories":
            self.listCategories(self.currItem)
        elif category == "ec_posts":
            self.listPosts(self.currItem)
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
        CHostBase.__init__(self, EgyClub(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("egyclub")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") == "ec_video"
