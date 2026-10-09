# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - DuLourd (French series, VF / VOSTFR, DLE template "dulourd2"): the whole site sits behind a Cloudflare
#     managed challenge (curl-impersonate does not get through either): pages go through getPageCFProtection
#     -> MyE2i solve on the box; posters on the site's own domain get the cf_clearance cookie + solving UA
#   - latest additions / all series / VF / VOSTFR / genres / years (site pager: First page / Jump / Next page)
#     and the site search (paged with search_start); the pager urls come from the site's own pager links
#     (the home page pages through /voir-series/page/N/); film cards are left out (the site answers 403)
#   - series -> seasons (/N-saison.html) -> episodes (/N-episode.html); episodes are VIDEO rows keyed on their
#     page path (domain independent)
#   - every player link of an episode is handed out by engine/ajax/controller.php?mod=getxfield only with a
#     Cloudflare Turnstile token (action "getxfield", cData + page_token of the episode page): solved per
#     link through the configured captcha service (MyE2i by default; one retry on captcha_error), then the
#     iframe goes to urlparser (unknown voe / filemoon / ... mirror domains -> the player's main domain)
#   - watched flag (series -> season -> episode), downloaded flag, favourites, name normalisation
#     ("Show - SxxExx"), sidecar, INFO via moviemeta + the site's info block
import os
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.dulourd_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.dulourd_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.dulourd_proxy))
    if config.plugins.iptvplayer.dulourd_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.dulourd_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://www.dulourd.cash/"


SITE_URL_RE = re.compile(r"^https?://(?:www\.)?dulourd\.[a-z]+/", re.I)
SITE_MARKER = "dulourd2"
SEASON_URL_RE = re.compile(r"/(\d+)-saison\.html")
EPISODE_URL_RE = re.compile(r"/(\d+)-episode\.html")
PAGE_HREF_RE = re.compile(r'href="([^"]*/page/(\d+)/)"')
# getxfield(this, '137030', 'voe_vostfr', 'serial')
XFIELD_RE = re.compile(r"""getxfield\(this,\s*'(\d+)',\s*'([^']+)',\s*'(\w+)'\)""")
LOCAL_PAGE_SIZE = 100
# the site's films (/films-streaming/...) answer HTTP 403 with an empty page ("dulourd for films") -> not listed
FILM_URL_RE = re.compile(r"/films-streaming/", re.I)
# getxfield hands out ever new mirror domains of these players (ralphysuccessfull.org, kaydendown.lol ...);
# an unknown one goes to the player's main domain (same /e/<id> path, voe.sx redirects to its current mirror)
SERVER_DOMAINS = {"voe": "voe.sx", "filemoon": "filemoon.sx", "doodstream": "dood.to", "vidoza": "vidoza.net", "netu": "netu.tv", "uqload": "uqload.net"}


class DuLourd(GenericFolderWatchedScraperMixin, CBaseHostClass, CaptchaHelper):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "series_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "dulourd", "cookie": "dulourd.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/dulourd135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("dulourd")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.dulourd_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        if DuLourd.DOMAIN_CACHE:
            self.MAIN_URL = DuLourd.DOMAIN_CACHE
            return
        domain = config.plugins.iptvplayer.dulourd_alt_domain.value.strip()
        self.MAIN_URL = domain.rstrip("/") + "/" if self.cm.isValidUrl(domain) else gettytul()
        sts, data = self.getPage(self.MAIN_URL)
        if sts and SITE_MARKER in data:
            self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", self.MAIN_URL))
            DuLourd.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / older lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        return SITE_URL_RE.sub(self.MAIN_URL, url)

    @staticmethod
    def _path(url):
        # domain independent identity of a page
        return re.sub(r"^https?://[^/]+", "", (url or "").split("#")[0].split("?")[0]).rstrip("/").lower()

    def getFullIconUrl(self, url, currUrl=None):
        # posters on the site's own domain (/uploads/...) sit behind the same Cloudflare check as the pages
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        if not url.startswith("http"):
            return url
        meta = {}
        if SITE_URL_RE.match(url):
            meta["Referer"] = self.MAIN_URL or gettytul()
            try:
                # getCookieHeader logs tracebacks for a cookie file that does not exist yet
                cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ["cf_clearance"]).rstrip("; ") if os.path.isfile(self.COOKIE_FILE) else ""
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
            if cItem.get("category") in ("dl_video", "dl_series", "dl_season"):
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
            category = cItem.get("category", "")
            path = self._path(cItem.get("url", ""))
            if not path:
                return ""
            if category == "dl_video":
                return "video:%s" % path
            if category == "dl_series":
                return "series:%s" % path
            if category == "dl_season":
                return "season:%s" % path
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        def lst(title, path):
            return {"category": "list_items", "good_for_fav": True, "title": title, "url": self.getFullUrl(path)}

        menu = [
            lst(_("Latest"), "/"),
            lst(_("Series"), "/voir-series/"),
            lst("VF", "/voir-series/series-vf/"),
            lst("VOSTFR", "/voir-series/series-vostfr/"),
            {"category": "dl_genres", "title": _("Genres")},
            {"category": "dl_years", "title": _("Year")},
        ]
        self.listsTab(menu + self.searchItems(), cItem)

    def listFilters(self, cItem):
        # the header menu of every page: "Les séries par genre" / "Les séries par Année"
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        years = cItem["category"] == "dl_years"
        pattern = r'href="([^"]*/voir-series/annee/(\d{4})/)"' if years else r'href="([^"]*/voir-series/([a-z-]+[_-]s)/)"[^>]*>([^<]+)<'
        seen = set()
        items = []
        for match in re.findall(pattern, data):
            href = match[0]
            if href in seen:
                continue
            seen.add(href)
            # the site's year menu repeats the 2020 link under the labels 2021-2024 -> the year of the link
            items.append((match[1] if years else self.cleanHtmlStr(match[2]), href))
        if years:
            items.sort(key=lambda x: x[0], reverse=True)
        for title, href in items:
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": self._rebase(href)})

    def _addCard(self, block):
        url = self.cm.ph.getSearchGroups(block, r'href="([^"]+\.html)"')[0]
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="name">(.*?)</div>')[0]) or self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'\balt="([^"]+)"')[0])
        if not url or not title or FILM_URL_RE.search(url):
            return False
        icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+?data-src="([^"]+)"')[0]
        year = self.cm.ph.getSearchGroups(block, r'class="icon-hd"[^>]*>\s*((?:19|20)\d{2})\s*<')[0]
        lang = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="icon-voicer"[^>]*>(.*?)</span>')[0])
        latest = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="category">(.*?)</div>')[0])
        desc = "[/br]".join(x for x in ("%s: %s" % (_("Year"), year) if year else "", lang, latest) if x)
        self.addDir({"name": "category", "category": "dl_series", "good_for_fav": True, "url": self._rebase(url), "title": title,
                     "icon": self.getFullIconUrl(icon) if icon else "", "desc": desc, "s_title": title,
                     "meta_type": "tv", "meta_title": title, "meta_year": year})
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = cItem["url"]
        printDBG("DuLourd.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        cards = self.cm.ph.getAllItemsBeetwenMarkers(data, ("<article", ">", "movie-box m-info"), ("</article", ">"))
        for block in cards:
            self._addCard(block)
        if not cards:
            # DLE notice ("Aucun résultat ...")
            message = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "alert"), ("</div", ">"), False)[1])
            if message:
                SetIPTVPlayerLastHostError(message)
            return
        nav = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "navigation"), ("</div", ">"), False)[1]
        firstUrl = cItem.get("first_url") or url
        if "search_story" in cItem:
            # search pager: javascript:list_submit(N)
            lastPage = max([int(x) for x in re.findall(r"list_submit\((\d+)\)", nav)] + [page])
            pageTpl = self.getFullUrl("/index.php?do=search&subaction=search&story=%s&search_start={page}" % urllib_quote_plus(cItem["search_story"]))
        else:
            pages = PAGE_HREF_RE.findall(nav)
            lastPage = max([int(num) for _href, num in pages] + [page])
            if pages:
                # the pager's own links: the home page ("Latest") pages through /voir-series/page/N/, its own
                # /page/N/ answers page 1 again; the links may name a sister domain -> _rebase
                pageTpl = re.sub(r"/page/\d+/?$", "/page/{page}/", self._rebase(pages[0][0]))
            else:
                pageTpl = re.sub(r"page/\d+/?$", "", firstUrl).rstrip("/") + "/page/{page}/"
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "first_url": firstUrl, "url": firstUrl})
        addPagingItems(self, listItem, page, page < lastPage, lastPage, pageTpl)
        for item in self.currList:
            # "First page" back to the list the user opened (the pager's page 1 would be /voir-series/ for "Latest")
            if item.get("image_type") == "FIRST":
                item["url"] = firstUrl

    def listSeasons(self, cItem):
        printDBG("DuLourd.listSeasons [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        block = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "seasontab"), ("<div", ">", "home-con"), False)[1]
        seasons = []
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, ("<a", ">", "th-hover"), ("</a", ">")):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            num = self.cm.ph.getSearchGroups(href, SEASON_URL_RE.pattern)[0]
            if not href or not num:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'data-src="([^"]+)"')[0]
            seasons.append((int(num), href, icon))
        if not seasons:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        seasons.sort()
        for num, href, icon in seasons:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "dl_season", "url": self._rebase(href), "series_url": cItem["url"], "s_season": num,
                           "icon": self.getFullIconUrl(icon) if icon else cItem.get("icon", ""),
                           "title": "%s - %s" % (show, formatSxxExx(num)) if IsMediaNamingNormalized() else "%s %s" % (_("Season"), num)})
            self.addDir(params)

    def listEpisodes(self, cItem):
        printDBG("DuLourd.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season") or int(self.cm.ph.getSearchGroups(cItem["url"], SEASON_URL_RE.pattern)[0] or 1)
        block = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "saisontab"), ("</article", ">"), False)[1]
        episodes = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, ("<a", ">"), ("</a", ">")):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            episode = self.cm.ph.getSearchGroups(href, EPISODE_URL_RE.pattern)[0]
            if not episode or href in seen:
                continue
            seen.add(href)
            label = self.cleanHtmlStr(item)
            if IsMediaNamingNormalized():
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = "%s - %s" % (show, label) if label else show
            episodes.append((int(episode), {"name": "category", "good_for_fav": True, "category": "dl_video", "url": self._rebase(href), "icon": cItem.get("icon", ""),
                                            "title": title, "desc": cItem.get("desc", ""), "series_url": cItem.get("series_url", ""), "s_title": show,
                                            "s_season": season, "s_episode": episode, "meta_type": "tv",
                                            "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")}))
        # the site lists the newest episode first
        episodes = [params for _num, params in sorted(episodes, key=lambda x: x[0])]
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, category="dl_season"), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("DuLourd.listSearchResult [%s]" % searchPattern)
        story = searchPattern.strip()
        url = self.getFullUrl("/index.php?do=search&subaction=search&story=%s" % urllib_quote_plus(story))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "page": 1, "url": url, "first_url": url, "search_story": story})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        url = cItem.get("url", "")
        printDBG("DuLourd.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        page = self._rebase(url).split("#")[0]
        urltab = []
        for block in self.cm.ph.getAllItemsBeetwenMarkers(data, ("<div", ">", "lien fx-row"), ("</li", ">")):
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
            printDBG("DuLourd.getxfield captcha_error, attempt %d" % attempt)
        if not url:
            if answer:
                SetIPTVPlayerLastHostError("%s (%s)" % (_("No stream available"), answer[:40]))
            return ""
        server = parts[1].split("_")[0].lower()
        if server in SERVER_DOMAINS and self.up.checkHostSupport(url) != 1:
            url = re.sub(r"^(https?://)[^/]+", r"\g<1>" + SERVER_DOMAINS[server], url)
            printDBG("DuLourd.getxfield unknown %s mirror -> %s" % (server, url))
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
            printDBG("DuLourd.getxfield answer [%s]" % data.strip()[:200])
            return "", data.strip()
        return url, ""

    def getVideoLinks(self, videoUrl):
        printDBG("DuLourd.getVideoLinks [%s]" % videoUrl)
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        url = self._getXfieldUrl(videoUrl) if "#xf=" in str(videoUrl) else str(videoUrl)
        if not self.cm.isValidUrl(url):
            return []
        return decorateResolvedLinkItems(self.up.getVideoLinkExt(strwithmeta(url, {"Referer": self.getMainUrl()})), sidecar)

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        block = self.cm.ph.getDataBeetwenMarkers(data, ("<div", ">", "film-bilgileri"), ("<div", ">", "seasontab"), False)[1] or data
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="description">.*?</div>(.*?)</div>')[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]+)"')[0])
        info = {}
        year = self.cm.ph.getSearchGroups(block, r'(?s)class="release">.*?<span>\s*((?:19|20)\d{2})')[0]
        if year:
            info["year"] = year
        country = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="country">.*?<span>(.*?)</span>')[0])
        if country:
            info["country"] = country
        for key, cls in (("duration", "duration"), ("directors", "director"), ("actors", "actors"), ("rating", "premiere")):
            value = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)<div class="%s list">\s*<span>.*?</span>(.*?)</div>' % cls)[0])
            if value:
                info[key] = value
        genres = [self.cleanHtmlStr(g) for g in re.findall(r"(?s)<a[^>]*>(.*?)</a>", self.cm.ph.getSearchGroups(block, r'(?s)<div class="category">(.*?)</div>')[0])]
        genres = ", ".join(g for g in genres if g)
        if genres:
            info["genres"] = genres
        poster = self.cm.ph.getSearchGroups(block, r'<img[^>]+?data-src="([^"]+)"')[0]
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getArticleContent(self, cItem):
        printDBG("DuLourd.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_title"):
            try:
                meta = getMeta("tv", cItem["meta_title"], cItem.get("meta_year", ""))
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        # episode / season pages carry no info block -> the show page
        sts, data = self.getPage(cItem.get("series_url") or cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
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
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("DuLourd.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category in ("dl_genres", "dl_years"):
            self.listFilters(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "dl_series":
            self.listSeasons(self.currItem)
        elif category == "dl_season":
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
        CHostBase.__init__(self, DuLourd(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("dulourd")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("dl_video", "dl_series", "dl_season")
