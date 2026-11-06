# -*- coding: utf-8 -*-
LAST_MODIFIED = "06.11.2026"
# Coding: BY MOHAMED_OS
# FilmoFlix (French films and series, DLE): pages behind Cloudflare (getPageCFProtection), player links per
# Turnstile token through engine/ajax/controller.php?mod=getxfield (same flow as dulourd)

###################################################
# FOREIGN import
###################################################
import re
from os.path import isfile as pathIsfile

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import GetIconDir, MergeDicts, printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsMediaNamingNormalized, IsSidecarEnabled
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.filmoflix_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.filmoflix_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.filmoflix_proxy))
    if config.plugins.iptvplayer.filmoflix_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.filmoflix_alt_domain))
    return optionList
###################################################


def gettytul():
    # the domain the site really serves from (filmoflixi.forum / filmoflix.fans redirect here): the Cloudflare
    # cookie of the MyE2i check is bound to it, a redirecting start domain would ask again after every solve
    return 'https://filmoflixi.homes/'


# with the trailing "/": _rebase() swaps the whole "https://host/" for MAIN_URL (which ends with "/")
SITE_DOMAIN_RE = re.compile(r"^https?://(?:[a-z0-9-]+\.)*filmoflix[a-z]*\.[a-z]+/", re.I)
SEASON_URL_RE = re.compile(r"(\d+)-saison(?:[a-z\-]+)?\.html$", re.I)
EPISODE_URL_RE = re.compile(r"(\d+)-saison(?:[a-z\-]+)?/(\d+)-episode\.html$", re.I)
# getxfield(this, '137030', 'voe_vostfr', 'serial')
XFIELD_RE = re.compile(r"""getxfield\(this,\s*'(\d+)',\s*'([^']+)',\s*'(\w+)'\)""")
# getxfield hands out ever new mirror domains of these players (ralphysuccessfull.org, kaydendown.lol ...);
# an unknown one goes to the player's main domain (same /e/<id> path, voe.sx redirects to its current mirror)
SERVER_DOMAINS = {"voe": "voe.sx", "filemoon": "filemoon.sx", "doodstream": "dood.to", "vidoza": "vidoza.net", "netu": "netu.tv", "uqload": "uqload.net"}
# labels of the info list of a film / series page -> INFO key
INFO_LABELS = (
    ("genres", "Genre"), ("released", "Date de sortie"), ("actors", "Acteurs"),
    ("directors", "Réalisé par"), ("duration", "Durée"), ("rating", "Évaluation")
)
LOCAL_PAGE_SIZE = 100


class FilmoFlix(GenericFolderWatchedScraperMixin, CBaseHostClass, CaptchaHelper):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "group", "s_title", "s_season", "s_episode", "meta_type")

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'filmoflix', 'cookie': 'filmoflix.cookie'})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/filmoflix135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("filmoflix")
        self.wfInitFolderCache()

    ###################################################
    # HTTP
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.filmoflix_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        if FilmoFlix.DOMAIN_CACHE:
            self.MAIN_URL = FilmoFlix.DOMAIN_CACHE
            return
        domain = config.plugins.iptvplayer.filmoflix_alt_domain.value.strip()
        self.MAIN_URL = domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul()
        sts, _data = self.getPage(self.MAIN_URL)
        finalUrl = self.cm.meta.get("url", self.MAIN_URL)
        if sts and SITE_DOMAIN_RE.match(finalUrl):
            # the site moves between filmoflix.* domains -> the one the old domain redirects to
            self.MAIN_URL = self.cm.getBaseUrl(finalUrl)
            FilmoFlix.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / older lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return SITE_DOMAIN_RE.sub(self.MAIN_URL, url)

    @staticmethod
    def _path(url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", (url or "").split("#")[0].split("?")[0]).rstrip("/").lower()

    @staticmethod
    def _isMovieUrl(url):
        # True / False from the site's url layout, None when the url does not tell
        path = FilmoFlix._path(url)
        if "/film/" in path:
            return True
        if "/serie/" in path or "-saison" in path:
            return False
        return None

    @staticmethod
    def _pageUrlTpl(url):
        # .../film/page/{page}/ , .../film/comedie/page/{page}/
        base, query = (url.split("?", 1) + [""])[:2]
        base = re.sub(r"/page/\d+/?$", "/", base).rstrip("/").replace("{", "{{").replace("}", "}}")
        query = query.replace("{", "{{").replace("}", "}}")
        return base + "/page/{page}/" + ("?" + query if query else "")

    @staticmethod
    def _page(cItem):
        try:
            return max(1, int(cItem.get("page", 1) or 1))
        except (TypeError, ValueError):
            return 1

    def getFullIconUrl(self, url, currUrl=None):
        # posters on the site's own domain (/uploads/...) sit behind the same Cloudflare check as the pages
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        if not url.startswith("http"):
            return url
        meta = {}
        if SITE_DOMAIN_RE.match(url):
            meta["Referer"] = self.MAIN_URL or gettytul()
            try:
                # getCookieHeader logs tracebacks for a cookie file that does not exist yet
                cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if pathIsfile(self.COOKIE_FILE) else ""
                if cookieHeader:
                    meta.update({"User-Agent": remembered_user_agent(self.COOKIE_FILE) or self.HEADER.get("User-Agent"), "Cookie": cookieHeader})
            except Exception:
                printExc()
        proxy = self.getProxy()
        if proxy:
            meta["iptv_http_proxy"] = proxy
        return strwithmeta(url, meta) if meta else url

    def getFavouriteData(self, cItem):
        try:
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
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            if cItem.get("type", "") == "video":
                return "video:%s" % path
            prefix = {"list_seasons": "series", "list_episodes": "season"}.get(cItem.get("category", ""), "")
            return "%s:%s" % (prefix, path) if prefix else ""
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listGroupMenu(self, cItem):
        # Movies / Series: the same four lists on film/ and serie/
        url = self.getFullUrl("film/" if cItem.get("group") == "movies" else "serie/")
        tab = [
            {"category": "list_items", "title": cItem.get("title", ""), "url": url},
            {"category": "list_genres", "title": _("Genres"), "url": url},
            {"category": "list_year", "title": _("Year"), "url": url}
        ]
        self.listsTab(tab, dict(cItem, good_for_fav=True))

    def listValue(self, cItem):
        printDBG("FilmoFlix.listValue [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return

        block = self.cm.ph.getDataBeetwenMarkers(data, ("<main", ">", "col-mid fx-1"), ("<div", ">", "main fx-col"), False)[1]
        if not block:
            printDBG("FilmoFlix.listValue: filter block [%s] not found" % cItem.get("title", ""))
            return
        years = cItem.get("category") == "list_year"
        pattern = r'href="([^"]*/(?:serie|film)/annee/(\d{4})/)"' if years else r'href="([^"]*/(?:serie|film)/([a-z-]+)/)"[^>]*>([^<]+)<'
        for match in re.findall(pattern, block):
            url = match[0]
            title = match[1] if years else self.cleanHtmlStr(match[2])
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": self._rebase(url)})
            self.addDir(params)

    def _addCard(self, cItem, block, itemUrl, normalize):
        title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(block, ('<h2', '>', 'th-title'), ('</h2', '>'), False)[1]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'''(?:title|alt)=['"]([^'"]+)['"]''')[0])
        if not title:
            return
        icon = self.cm.ph.getSearchGroups(block, r'''data-src=['"]([^'"]+)['"]''')[0] or self.cm.ph.getSearchGroups(block, r'''<img[^>]+?src=['"]([^'"]+)['"]''')[0]
        rating = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)th-rating">.*?</span>(.*?)</div>')[0])
        if not re.search(r"[1-9]", rating):
            # "0,0": nobody voted yet
            rating = ""
        quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)th-qual">(.*?)</div>')[0])
        genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)th-cat nowrap">(.*?)</div>')[0])
        desc = " | ".join(["%s: %s" % (label, value) for label, value in ((_("Rating"), rating), (_("Quality"), quality), (_("Genres"), genre)) if value])
        params = stripPagerKeys(dict(cItem), ("search_story", "first_url"))
        params.update({"name": "category", "good_for_fav": True, "url": self._rebase(itemUrl), "icon": self.getFullIconUrl(icon) if icon else "",
                       "desc": desc, "s_title": title})
        isMovie = self._isMovieUrl(itemUrl)
        if isMovie is None and cItem.get("group") in ("movies", "series"):
            isMovie = cItem["group"] == "movies"
        if isMovie:
            params.update({"category": "fif_video", "group": "movies", "meta_type": "movie", "title": title, "meta_year": ""})
            self.addVideo(params)
        else:
            # a series, or a search hit the url does not tell: listSeasons shows a film page as its video row
            params.update({"category": "list_seasons", "group": "series", "meta_type": "tv", "title": title, "meta_year": ""})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG('FilmoFlix.listItems [%s]' % cItem)
        page = self._page(cItem)
        firstUrl = cItem.get("first_url") or cItem.get("url", "")
        story = cItem.get("search_story")
        if story is not None:
            # DLE search pages through search_start
            pageUrlTpl = self.getFullUrl("/index.php?do=search&subaction=search&story=%s&search_start={page}" % urllib_quote_plus(story))
        else:
            pageUrlTpl = self._pageUrlTpl(firstUrl)
        sts, data = self.getPage(pageUrlTpl.format(page=page) if page > 1 else firstUrl)
        if not sts:
            return

        normalize = IsMediaNamingNormalized()
        seen = set()
        for block in data.split('class="th-item')[1:]:
            itemUrl = self.cm.ph.getSearchGroups(block, r'href="(https?://[^"]+)"')[0]
            if not itemUrl or itemUrl in seen:
                continue
            seen.add(itemUrl)
            self._addCard(cItem, block, itemUrl, normalize)

        if not seen:
            # empty category / page or no search hits: a marker instead of an empty list
            self.addMarker({"title": _("No items found"), "desc": ""})
            return

        pager = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "navigation"), "</div>", False)[1] or data
        pages = [int(n) for n in re.findall(r'href="[^"]*/page/(\d+)/[^"]*', pager) + re.findall(r"list_submit\((\d+)\)", pager)]
        lastPage = max(pages + [page])
        hasNext = "nav_ext" in pager or lastPage > page
        addPagingItems(self, dict(cItem, category="list_items", url=firstUrl, first_url=firstUrl), page, hasNext, lastPage, pageUrlTpl)
        for item in self.currList:
            # "First page" back to the list the user opened (the search's first page has no search_start)
            if item.get("image_type") == "FIRST":
                item["url"] = firstUrl

    def _seasons(self, data):
        # [(season, url, icon)] of the season tiles of a series page
        block = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "saisontab"), ("<div", ">", "full-ser-keywords"), True)[1]
        seasons, seen = [], set()
        for url, inner in re.findall(r'(?s)href="([^"]+\d+-saison(?:[A-Za-z-]+)?\.html)"[^>]*>(.*?)</a>', block):
            season = int(SEASON_URL_RE.search(url).group(1))
            if season in seen:
                continue
            seen.add(season)
            icon = self.cm.ph.getSearchGroups(inner, r'data-src="([^"]+)"')[0]
            seasons.append((season, self._rebase(url), self.getFullIconUrl(icon) if icon else ""))
        return sorted(seasons)

    def listSeasons(self, cItem):
        printDBG('FilmoFlix.listSeasons [%s]' % cItem)
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return
        seasons = self._seasons(data)
        if not seasons:
            if XFIELD_RE.search(data):
                # a film page (search hit whose url does not tell): its video row
                title = cItem.get("s_title") or cItem.get("title", "")
                self.addVideo(MergeDicts(cItem, {"category": "fif_video", "group": "movies", "meta_type": "movie", "title": title}))
            else:
                SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        if len(seasons) == 1:
            season, url, icon = seasons[0]
            self.listEpisodes(dict(cItem, url=url, s_season=season, icon=icon or cItem.get("icon", "")))
            return
        show = cItem.get("s_title") or cItem.get("title", "")
        normalize = IsMediaNamingNormalized()
        for season, url, icon in seasons:
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "list_episodes", "good_for_fav": True, "url": url, "s_title": show, "s_season": season,
                           "title": "%s - %s" % (show, formatSxxExx(season)) if normalize else "%s %d" % (_("Season"), season),
                           "icon": icon or cItem.get("icon", ""), "meta_type": "tv"})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG('FilmoFlix.listEpisodes [%s]' % cItem)
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "fsa-items"), "</div>\n</div>", True)[1] or data
        current = cItem.get("s_season")
        episodes, seen = [], set()
        for url in re.findall(r'<a href="([^"]+\d+-saison(?:[a-z\-]+)?/\d+-episode\.html)"', block):
            numbers = EPISODE_URL_RE.search(url)
            key = (int(numbers.group(1)), int(numbers.group(2)))
            # the page may also link episodes of other seasons
            if key in seen or (current and key[0] != current):
                continue
            seen.add(key)
            episodes.append(key + (self._rebase(url),))
        if not episodes:
            SetIPTVPlayerLastHostError(_("No streams are available for this title yet."))
            return
        episodes.sort()
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title") or cItem.get("title", "")
        page = self._page(cItem)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for season, episode, url in episodes[start:start + LOCAL_PAGE_SIZE]:
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - %s %d - %s %d" % (show, _("Season"), season, _("Episode"), episode)
            params = stripPagerKeys(dict(cItem))
            params.update({"name": "category", "category": "fif_video", "good_for_fav": True, "title": title, "url": url,
                           "s_title": show, "s_season": season, "s_episode": episode, "meta_type": "tv"})
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, category="list_episodes"), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FilmoFlix.listSearchResult [%s]" % searchPattern)
        story = searchPattern.strip()
        url = self.getFullUrl("/index.php?do=search&subaction=search&story=%s" % urllib_quote_plus(story))
        cItem = dict(cItem)
        cItem.pop("group", None)
        cItem.update({"category": "list_items", "page": 1, "url": url, "first_url": url, "search_story": story})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("FilmoFlix.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        page = self._rebase(url).split("#")[0]
        urltab = []
        for block in self.cm.ph.getAllItemsBeetwenMarkers(data, ("<div", ">", "lien-bis fx-row"), ("</li", ">")):
            match = XFIELD_RE.search(block)
            if not match:
                continue
            newsId, xfield, xtype = match.groups()
            server = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="serv"[^>]*>(.*?)</span>')[0]) or xfield.split("_")[0]
            lang = self.cm.ph.getSearchGroups(block, r"/images/([A-Za-z]+)\.png")[0].upper() or xfield.split("_")[-1].upper()
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="pl-5"[^>]*>(.*?)</span>')[0])
            name = " ".join(x for x in (server, "[%s]" % lang if lang else "", quality) if x)
            # the player link is fetched in getVideoLinks (it needs a Turnstile token per request)
            urltab.append({"name": name, "url": "%s#xf=%s|%s|%s" % (page, newsId, xfield, xtype), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        story = self._siteInfo(data)[0]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def _getXfieldUrl(self, videoUrl):
        page, _sep, frag = str(videoUrl).partition("#xf=")
        parts = frag.split("|")
        if len(parts) != 3:
            return ""
        # a Turnstile token is now and then refused (captcha_error) -> one more try with a fresh page token
        for attempt in (1, 2):
            url, answer = self._requestXfield(page, parts)
            if url or answer != "captcha_error":
                break
            printDBG("FilmoFlix.getxfield captcha_error, attempt %d" % attempt)
        if not url:
            if answer:
                SetIPTVPlayerLastHostError("%s (%s)" % (_("No stream available"), answer[:40]))
            return ""
        server = parts[1].split("_")[0].lower()
        if server in SERVER_DOMAINS and self.up.checkHostSupport(url) != 1:
            url = re.sub(r"^(https?://)[^/]+", r"\g<1>" + SERVER_DOMAINS[server], url)
            printDBG("FilmoFlix.getxfield unknown %s mirror -> %s" % (server, url))
        return url

    def _requestXfield(self, page, parts):
        # -> (player url, "") or ("", site answer such as captcha_error / page_error / rate_limit / session_error)
        sts, data = self.getPage(page)
        if not sts:
            return "", ""
        pageToken = self.cm.ph.getSearchGroups(data, r'xfPageToken\s*=\s*"([^"]+)"')[0]
        cData = self.cm.ph.getSearchGroups(data, r'xfPageCData\s*=\s*"([^"]+)"')[0]
        userHash = self.cm.ph.getSearchGroups(data, r"dle_login_hash\s*=\s*'([^']*)'")[0]
        sitekey = self.cm.ph.getSearchGroups(data, r"""sitekey\s*:\s*['"]([^'"]+)['"]""")[0]
        action = self.cm.ph.getSearchGroups(data, r"""action\s*:\s*['"]([^'"]+)['"]""")[0] or "getxfield"
        if not pageToken or not sitekey:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return "", ""
        # no captcha service set ("Auto"): MyE2i, else the user only gets a wiki hint
        bypass = config.plugins.iptvplayer.captcha_bypass.value or "mye2i"
        token = self.processCaptcha(sitekey, page, bypassCaptchaService=bypass, captchaType="cf_re", captchaAction=action, captchaData=cData)[0]
        if not token:
            SetIPTVPlayerLastHostError(_("Captcha was not entered."))
            return "", ""
        params = dict(self.defaultParams)
        params["header"] = MergeDicts(self.HEADER, {"Referer": page, "X-Requested-With": "XMLHttpRequest"})
        post = {"id": parts[0], "xfield": parts[1], "type": parts[2], "page_token": pageToken, "g_recaptcha_response": token, "user_hash": userHash}
        sts, data = self.getPage(self.getFullUrl("/engine/ajax/controller.php?mod=getxfield"), params, post)
        if not sts:
            return "", ""
        url = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0].replace("&amp;", "&")
        if url.startswith("//"):
            url = "https:" + url
        if not self.cm.isValidUrl(url):
            printDBG("FilmoFlix.getxfield answer [%s]" % data.strip()[:200])
            return "", data.strip()
        return url, ""

    def getVideoLinks(self, videoUrl):
        printDBG("FilmoFlix.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        url = self._getXfieldUrl(videoUrl) if "#xf=" in str(videoUrl) else str(videoUrl)
        if not self.cm.isValidUrl(url):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(url, {"Referer": self.getMainUrl()})), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        # -> (info, plot, year) from the info list of a film / series page
        info = {}
        for key, label in INFO_LABELS:
            value = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, (label, ":"), ("</div", ">"), False)[1])
            # rating "3,0 / 5"; without votes the page shows "/ 5" or "0 / 5"
            if value and not (key == "rating" and not re.match(r"\s*0*[1-9]|\s*0*[.,]\d*[1-9]", value)):
                info[key] = value
        year = self.cm.ph.getSearchGroups(info.get("released", ""), r"((?:19|20)\d{2})")[0]
        # "fdesc full-text" = the story; episode pages put a sign-up box (also "full-text", its first div is an "i" icon) before it
        plot = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "fdesc"), ("</div", ">"), False)[1])
        return info, plot, year

    def getArticleContent(self, cItem):
        printDBG("FilmoFlix.getArticleContent [%s]" % cItem.get("url", ""))
        info, plot, year = {}, "", cItem.get("s_year", "")
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            info, plot, siteYear = self._siteInfo(data)
            year = year or siteYear
        mediaType = cItem.get("meta_type", "") or ("movie" if self._isMovieUrl(cItem.get("url", "")) else "tv")
        title = cItem.get("s_title", "") or cItem.get("title", "")
        meta = {}
        try:
            meta = getMeta(mediaType, title, year, maxYearDiff=1)
        except Exception:
            printExc()
        for key, value in meta.get("info", {}).items():
            info.setdefault(key, value)
        metaPlot = meta.get("plot", "")
        text = plot or cItem.get("desc", "")
        if metaPlot and text and metaPlot != text:
            text = "%s[/br][/br]%s" % (text, metaPlot)
        else:
            text = text or metaPlot
        icon = cItem.get("icon", "") or meta.get("poster", "") or self.DEFAULT_ICON_URL
        return [{"title": cItem.get("title", ""), "text": text, "images": [{"title": "", "url": icon}], "other_info": info}]

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
        printDBG("FilmoFlix.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            menu = [{"category": "fif_group", "title": _("Movies"), "group": "movies"},
                    {"category": "fif_group", "title": _("Series"), "group": "series"}]
            self.listsTab(menu + self.searchItems(), {"name": "category"})

        elif category == "fif_group":
            self.listGroupMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "list_genres":
            self.listValue(self.currItem)
        elif category == "list_year":
            self.listValue(self.currItem)
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
        CHostBase.__init__(self, FilmoFlix(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('filmoflix')

    def withArticleContent(self, cItem):
        return cItem.get("type") == "video" or cItem.get("category", "") in ("list_seasons", "list_episodes")
