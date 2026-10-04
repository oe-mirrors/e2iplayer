# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - current standard (cimalina host created by Dr HYTHAM MAHMOUD)
#   - domain: cema-lin.shop (2.cema-lin.shop is a parked cPanel page now), own "Alternative domain" first
#   - movie / series categories read live from the site menu, collections (/assemblies/), search;
#     First Page / Jump / Next page (n/last) from the WordPress pager
#   - movies and episodes are VIDEO rows on their page url; series -> "all episodes" (/selary/) list
#   - links: the base64 server map of the page's watch form (no extra request), every server handed to
#     urlparser - the Megamax family (megamax.me/.cam, share4max.com, megatuktuk.store) included, the
#     in-host Megamax resolver is gone; names numbered when a label repeats; episode trailers left out
#   - watched flag (domain-free page keys), downloaded flag, favourites (urls re-based on the current
#     domain), name normalisation ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the
#     site's story / genres / year / poster
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps, loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, b64Decode
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

config.plugins.iptvplayer.cimalina_proxy = ConfigSelection(default="None", choices=[("None", _("None")), ("proxy_1", _("Alternative proxy server (1)")), ("proxy_2", _("Alternative proxy server (2)"))])
config.plugins.iptvplayer.cimalina_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.cimalina_proxy))
    if config.plugins.iptvplayer.cimalina_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.cimalina_alt_domain))
    return optionList


def gettytul():
    return "CimaLina"


DOMAINS = ["https://cema-lin.shop/", "https://1.cema-lin.shop/", "https://cimalina.live/"]
# the site's own domains (current and former) - their urls are re-based on the domain in use
SITE_RE = re.compile(r"^https?://(?:[a-z0-9-]+\.)*(?:cema-lin\.shop|cimalina\.live|cimalena\.cfd)/", re.I)
MENU_IDS = {"movies": "menu-item-380427", "series": "menu-item-380436"}
STR_TYPES = (type(""), type(u""))

SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1),
    ("الثانية", 2), ("الثاني", 2), ("الثانى", 2), ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4),
    ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6), ("السادس", 6), ("السابعة", 7), ("السابع", 7),
    ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
_ORD_RE = "|".join(o[0] for o in SEASON_ORDINALS)
# "الموسم الرابع", "الموسم 4 الرابع", "الجزء 2"
SEASON_RE = re.compile(r"\s*(?:الموسم|الجزء)\s*(\d+|%s)(?:\s+(?:%s))?" % (_ORD_RE, _ORD_RE))
EPISODE_RE = re.compile(r"\s*(?:الحلقة|ح)\s*(\d+|الأخيرة|الاخيرة)")
PREFIX_RE = re.compile(r"^(?:\s*(?:مشاهدة|فيلم|فلم|مسلسل|انمي|أنمي|برنامج)\s+)+")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجم|اون لاين|أون لاين|كاملة|كامل|بجودة عالية|HD)(?=\s|$)")
YEAR_RE = re.compile(r"^(.*?)\s*\(?((?:19|20)\d{2})\)?$")
DUB_WORD = "مدبلج"


def _ordinal(val):
    if not val:
        return 1
    if val.isdigit():
        return int(val)
    return dict(SEASON_ORDINALS).get(val, 1)


class CimaLina(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "media_type", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cimalina", "cookie": "cimalina.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/cimalina135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.HEADER.update({"Accept-Language": "ar,en-US;q=0.9,en;q=0.8"})
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("cimalina")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        proxy = config.plugins.iptvplayer.cimalina_proxy.value
        try:
            if proxy == "proxy_1":
                return config.plugins.iptvplayer.alternativeproxy1.value
            if proxy == "proxy_2":
                return config.plugins.iptvplayer.alternativeproxy2.value
        except Exception:
            printExc()
        return None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def selectDomain(self):
        if CimaLina.DOMAIN_CACHE:
            self.MAIN_URL = CimaLina.DOMAIN_CACHE
            return
        domains = list(DOMAINS)
        altDomain = config.plugins.iptvplayer.cimalina_alt_domain.value.strip()
        if self.cm.isValidUrl(altDomain):
            domains.insert(0, altDomain.rstrip("/") + "/")
        for domain in domains:
            sts, data = self.getPage(domain)
            if sts and ("moviesBlocks" in data or MENU_IDS["movies"] in data):
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", domain) or domain)
                break
            printDBG("CimaLina.selectDomain: %s is not the site" % domain)
        if not self.MAIN_URL:
            self.MAIN_URL = DOMAINS[0]
        CimaLina.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if url.startswith("//"):
            url = "https:" + url
        m = SITE_RE.match(url)
        if m:
            return self.MAIN_URL + url[m.end():]
        return self.getFullUrl(url)

    @staticmethod
    def _pathKey(url):
        # domain-free identity of a page
        m = re.match(r"^https?://[^/]+/(.*?)/?$", url or "")
        return urllib_unquote(m.group(1)) if m else ""

    @staticmethod
    def _clean(text):
        text = PREFIX_RE.sub("", text or "")
        text = JUNK_RE.sub(" ", text)
        return re.sub(r"\s+", " ", text).strip(" -:|")

    @staticmethod
    def _splitYear(title):
        m = YEAR_RE.match(title or "")
        if m and m.group(1).strip():
            return m.group(1).strip(), m.group(2)
        return title, ""

    def _parseTitle(self, rawTitle):
        # "مسلسل Reacher الموسم الرابع الحلقة 8 مترجمة" -> show, year, season, episode ("" / "last" / number)
        title = self._clean(rawTitle)
        episode = ""
        m = EPISODE_RE.search(title)
        if m:
            episode = m.group(1) if m.group(1).isdigit() else "last"
            title = title[:m.start()]
        season, hasSeason = 1, False
        m = SEASON_RE.search(title)
        if m:
            season, hasSeason = _ordinal(m.group(1)), True
            title = title[:m.start()]
        title = re.sub(r"\s+", " ", title).strip(" -:|")
        dub = DUB_WORD in title
        if dub:
            title = re.sub(r"\s+", " ", title.replace("مدبلجة", " ").replace("مدبلجه", " ").replace(DUB_WORD, " ")).strip()
        show, year = self._splitYear(title)
        return {"show": show, "year": year, "season": season, "has_season": hasSeason, "episode": episode, "dub": dub}

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip())
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            key = self._pathKey(cItem.get("url", ""))
            if not key:
                return ""
            if category in ("cl_movie", "cl_episode"):
                return "video:%s" % key
            if category == "cl_series":
                return "season:%s" % key
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "") in ("cl_movie", "cl_episode", "cl_series", "cl_collection"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # menus
    ###################################################
    def listMainMenu(self, cItem):
        tab = [{"category": "cl_cats", "title": _("Movies"), "media_type": "movies"},
               {"category": "cl_cats", "title": _("Series"), "media_type": "series"}] + self.searchItems()
        self.listsTab(tab, cItem)

    def listCats(self, cItem):
        sts, data = self.getPage(self.MAIN_URL)
        if not sts:
            return
        menuId = MENU_IDS.get(cItem.get("media_type", ""), "")
        start = data.find(menuId) if menuId else -1
        if start < 0:
            return
        block = data[start:data.find("</ul>", start)]
        seen = set()
        for url, title in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)<', block):
            title = self.cleanHtmlStr(title)
            url = self._rebase(url)
            if not title or url in seen or not ("/category/" in url or "/assemblies" in url):
                continue
            seen.add(url)
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "list_items", "title": title, "url": url})
            self.addDir(params)

    def _itemParams(self, url, rawTitle, icon, desc, mediaType, normalize):
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": self.getFullIconUrl(icon), "desc": desc, "media_type": mediaType}
        info = self._parseTitle(rawTitle)
        show = info["show"] + (" " + DUB_WORD if info["dub"] else "")
        if "/assemblies/" in url:
            params.update({"category": "cl_collection", "title": self._clean(rawTitle) if normalize else rawTitle, "media_type": "movies"})
        elif info["episode"]:
            title = rawTitle
            if normalize and info["episode"] != "last":
                title = "%s - %s" % (show, formatSxxExx(info["season"], info["episode"]))
            params.update({"category": "cl_episode", "title": title, "s_title": show, "s_season": info["season"],
                           "s_episode": info["episode"], "meta_type": "tv", "meta_title": info["show"], "meta_year": info["year"]})
        elif "/selary/" in url or mediaType == "series" or rawTitle.startswith("مسلسل"):
            title = rawTitle
            if normalize:
                title = "%s (%s)" % (show, info["year"]) if info["year"] else show
                if info["has_season"]:
                    title = "%s - %s %d" % (title, _("Season"), info["season"])
            params.update({"category": "cl_series", "title": title, "s_title": show, "s_season": info["season"],
                           "meta_type": "tv", "meta_title": info["show"], "meta_year": info["year"]})
        else:
            title = rawTitle
            if normalize:
                title = "%s (%s)" % (show, info["year"]) if info["year"] else show
            params.update({"category": "cl_movie", "title": title, "meta_type": "movie", "meta_title": info["show"], "meta_year": info["year"]})
        return params

    def _blocks(self, data):
        # (url, raw title, icon, desc) of the "movie" cards of a page
        ret = []
        for item in data.split('<div class="movie">')[1:]:
            url = self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h3>(.*?)</h3>")[0])
            if not url or not title:
                continue
            icon = self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]
            ribbon = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<div class="ribbon">([^<]*)<')[0])
            fields = [self.cleanHtmlStr(x) for x in re.findall(r'<li class="(?:category|genre)">(.*?)</li>', item)]
            ret.append((self._rebase(url), title, icon, " | ".join([x for x in [ribbon] + fields if x])))
        return ret

    def _mainBlock(self, data):
        main = data.split('class="pagination"')[0]
        start = main.find("moviesBlocks")
        return main[start:] if start > -1 else main

    def listItems(self, cItem):
        url = self._rebase(cItem.get("url", ""))
        page = int(cItem.get("page", 1) or 1)
        printDBG("CimaLina.listItems page[%d] [%s]" % (page, url))
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        mediaType = cItem.get("media_type", "")
        seen = set()
        for itemUrl, rawTitle, icon, desc in self._blocks(self._mainBlock(data)):
            if itemUrl in seen:
                continue
            seen.add(itemUrl)
            params = self._itemParams(itemUrl, rawTitle, icon, desc, mediaType, normalize)
            if params["category"] in ("cl_movie", "cl_episode"):
                self.addVideo(params)
            else:
                self.addDir(params)
        if not seen:
            return
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<div class="pagination', "</ul>", False)[1]
        nums = [int(n) for n in re.findall(r">\s*(\d+)\s*</a>", pager)]
        hasNext = bool(re.search(r'href="[^"]+/page/%d/' % (page + 1), pager))
        last = max(nums + [page]) if nums else 0
        cItem = dict(cItem)
        if cItem.get("category") not in ("list_items", "cl_collection"):
            cItem.update({"category": "list_items", "search_item": False})
        base = re.sub(r"/page/\d+/?", "/", url)
        if "?" in base:
            path, query = base.split("?", 1)
            tpl = path.rstrip("/") + "/page/{page}/?" + query
        else:
            tpl = base.rstrip("/") + "/page/{page}/"
        addPagingItems(self, cItem, page, hasNext, last, tpl)

    def listEpisodes(self, cItem):
        url = self._rebase(cItem.get("url", ""))
        printDBG("CimaLina.listEpisodes [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        # the series page shows a few episodes, "كل الحلقات" (/selary/) all of them
        allEps = "" if "/selary/" in url else self.cm.ph.getSearchGroups(data, r'(?s)<ul class="SeasonsList">.*?href="([^"]+/selary/[^"]+)"')[0]
        if allEps and self._rebase(allEps) != url:
            sts, data2 = self.getPage(self._rebase(allEps))
            if sts and '<div class="movie">' in data2:
                data = data2
        normalize = IsMediaNamingNormalized()
        show = cItem.get("s_title", "")
        episodes = []
        seen = set()
        for itemUrl, rawTitle, icon, desc in self._blocks(self._mainBlock(data)):
            info = self._parseTitle(rawTitle)
            if itemUrl in seen or not info["episode"]:
                continue
            seen.add(itemUrl)
            season = info["season"] if info["has_season"] else cItem.get("s_season", 1)
            episodes.append((itemUrl, rawTitle, icon, desc, season, info["episode"]))
        numbers = [int(e[5]) for e in episodes if e[5].isdigit()]
        for itemUrl, rawTitle, icon, desc, season, epNum in sorted(episodes, key=lambda e: int(e[5]) if e[5].isdigit() else 9999):
            if epNum == "last":
                epNum = str(max(numbers) + 1) if numbers else ""
            if normalize and epNum and show:
                title = "%s - %s" % (show, formatSxxExx(season, epNum))
            else:
                title = rawTitle
            self.addVideo({"name": "category", "good_for_fav": True, "category": "cl_episode", "title": title, "url": itemUrl,
                           "icon": self.getFullIconUrl(icon) if icon else cItem.get("icon", ""), "desc": desc, "s_title": show,
                           "s_season": season, "s_episode": epNum, "meta_type": "tv", "meta_title": cItem.get("meta_title", ""),
                           "meta_year": cItem.get("meta_year", "")})

    def listSearchResult(self, cItem, searchPattern, searchType):
        if searchType == "movies":
            pattern = "فيلم " + searchPattern
        elif searchType == "series":
            pattern = "مسلسل " + searchPattern
        else:
            pattern = searchPattern
        params = dict(cItem)
        params.update({"name": "category", "category": "list_items", "url": self.MAIN_URL + "?s=" + urllib_quote_plus(pattern),
                       "good_for_fav": False, "page": 1, "media_type": ""})
        self.listItems(params)

    ###################################################
    # links
    ###################################################
    def _serverMap(self, value):
        # watch form field: base64 of {"label": "embed url", ...}
        try:
            data = json_loads(b64Decode(value.strip())) if value.strip() else {}
            if isinstance(data, dict):
                return [(self.cleanHtmlStr(k), v) for k, v in data.items() if isinstance(v, STR_TYPES) and v]
        except Exception:
            printExc()
        return []

    def getLinksForVideo(self, cItem):
        url = self._rebase(cItem.get("url", ""))
        printDBG("CimaLina.getLinksForVideo [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return []
        form = self.cm.ph.getSearchGroups(data, r'(?s)(<form[^>]+class="formWatch".*?</form>)')[0]
        servers = []
        if form:
            for name in ("servers", "downloads"):
                value = self.cm.ph.getSearchGroups(form, r'name="%s"\s+value="([^"]*)"' % name)[0]
                found = self._serverMap(value)
                # the downloads repeat the servers' files - only when there is no stream server
                if name == "servers" or not servers:
                    servers.extend(found)
        if form and not servers:
            # fallback: the server page the form posts to
            action = self.cm.ph.getSearchGroups(form, r'action="([^"]+)"')[0]
            postData = dict(re.findall(r'name="(servers|downloads)"\s+value="([^"]*)"', form))
            postData["submit"] = ""
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=url)
            sts, page = self.getPage(action, params, postData) if action else (False, "")
            if sts:
                for li in self.cm.ph.getAllItemsBeetwenMarkers(page, "<li", "</li>"):
                    link = self.cm.ph.getSearchGroups(li, r"data-server=\"[^\"]*?src='([^']+)'")[0]
                    if link:
                        servers.append((self.cleanHtmlStr(li), link))
        found = []
        for label, link in servers:
            link = link.replace("\\/", "/").strip()
            if link.startswith("//"):
                link = "https:" + link
            if not self.cm.isValidUrl(link) or link in [f[1] for f in found] or "اعلان" in label or "youtube.com" in link:
                continue
            hoster = self.up.getHostName(link)
            if hoster.startswith("www."):
                hoster = hoster[4:]
            found.append(("%s - %s" % (label, hoster) if label else hoster, link))
        counts = {}
        for name, _link in found:
            counts[name] = counts.get(name, 0) + 1
        numbers = {}
        urltab = []
        for name, link in found:
            if counts[name] > 1:
                numbers[name] = numbers.get(name, 0) + 1
                name = "%s #%d" % (name, numbers[name])
            urltab.append({"name": name, "url": strwithmeta(link, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        story = self._siteInfo(data)[0]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("CimaLina.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="StoryMovie">(.*?)</div>')[0])
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, poster

    def getArticleContent(self, cItem):
        url = self._rebase(cItem.get("url", ""))
        printDBG("CimaLina.getArticleContent [%s]" % url)
        meta = {}
        story, poster, info = "", "", {}
        sts, data = self.getPage(url)
        if sts:
            story, poster = self._siteInfo(data)
            block = self.cm.ph.getSearchGroups(data, r'(?s)<li class="genre">(.*?)</li>')[0]
            genres = [self.cleanHtmlStr(g) for g in re.findall(r'<a href="[^"]+/genre/[^"]+"[^>]*>([^<]+)<', block)]
            if genres:
                info["genres"] = ", ".join(genres[:6])
            year = self.cm.ph.getSearchGroups(data, r"/release-year/(\d{4})/")[0]
            if year:
                info["year"] = year
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year") or info.get("year", ""))
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
        if self.MAIN_URL is None:
            self.selectDomain()
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", "")
        category = self.currItem.get("category", "")
        printDBG("CimaLina.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "cl_cats":
            self.listCats(self.currItem)
        elif category in ("list_items", "cl_collection"):
            self.listItems(self.currItem)
        elif category == "cl_series":
            self.listEpisodes(self.currItem)
        elif category in ("search", "search_next_page"):
            params = dict(self.currItem)
            params.update({"search_item": False, "name": "category"})
            self.listSearchResult(params, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({"name": "history", "category": "search"}, "desc")
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, CimaLina(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cimalina")

    def getSearchTypes(self):
        return [(_("All"), "all"), (_("Movies"), "movies"), (_("Series"), "series")]

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("cl_movie", "cl_episode", "cl_series")
