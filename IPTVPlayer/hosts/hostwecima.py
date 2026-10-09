# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Based on the WeCima hosts by popking (odem2014) and MOHAMED_OS
# 08.10.2026 - revived from Backup for wecima.gripe (wecima.rent redirects there; cima.wecima.show is
#   gone, wecima.cx sits behind a Cloudflare managed challenge for every request); rewrite against the
#   current site (WeCima "maycima" theme, its own catalogue and players - not the mycima host's site):
#   - lists from the "GridItem" cards; First page / Jump / Next page (n/last) from the site's pager
#     (/page/N/, ?offset=N or ?s=..&page=N, whatever the list uses); search via /?s=..
#   - episode posts are grouped per show + season into a season folder; it lists the season's
#     episodes ("EpisodesList") and the show's other seasons (SeasonsList, loaded through the theme's
#     Ajaxt/Single/Episodes.php like the page does); /series/ pages are season folders too
#   - movies and episodes are VIDEO rows keyed on their page url; links: the watch servers (an
#     akhbarworld.online player page; the hoster embed in its base64 parameter goes to urlparser, else
#     the player page's own HLS/MP4 source is played) plus the vidtube download qualities
#     (base64 + ROT13 links) resolved by urlparser
#   - getPageCFProtection (MyE2i / curl-impersonate if the site turns the check on), alternative domain
#     + proxy options, favourites re-based on the current domain
#   - watched flag (season folder -> episodes), downloaded flag (page url), favourites, sidecar,
#     INFO via moviemeta + the site's story/fields, name normalisation ("Title (Year)",
#     "Show - SxxExx"; raw site labels when off), no colour codes in titles
import base64
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.wecima_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.wecima_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.wecima_proxy))
    if config.plugins.iptvplayer.wecima_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.wecima_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://wecima.gripe/"


# wecima.rent forwards to the site's current domain
MIRRORS = ("https://wecima.rent/",)
# Arabic ordinals used in season labels ("الموسم الثاني"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6), ("السادس", 6),
    ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:^|\s)(?:ال)?موسم\s*(\d+|%s)(?=\s|$)" % "|".join(o[0] for o in SEASON_ORDINALS))
# "الحلقة 15 الخامسة عشر" / "حلقة 3 والاخيرة" - everything from the episode word on is the episode label
EPISODE_RE = re.compile(r"(?:^|\s)(?:ال)?(?:حلقة|حلقه)\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s)\(?((?:19|20)\d\d)\)?((?:\s+(?:مدبلج|مدبلجة))*)\s*$")
SUBDUB_RE = re.compile(r"مترجم(?:ة)?\s+و\s*(مدبلج(?:ة)?)")
# site words that do not belong into a title / file name (only removed when normalising)
JUNK_RE = re.compile(r"(?:^|\s)(?:مشاهدة|فيلم|مسلسل|انمي|أنمي|كرتون|برنامج|عرض|مترجم|مترجمة|اون لاين|أون لاين|اونلاين|"
                     r"كامل|كاملة|والاخيرة|والأخيرة|HD)(?=\s|$)")
# "<li><span>النوع</span><p><a>..</a></p></li>" fields of a title page -> INFO keys
INFO_FIELDS = (("category", "التصنيف"), ("genres", "النوع"), ("quality", "الجودة"), ("language", "اللغة"), ("country", "الدولة"))
# the player page of a watch server: its own HLS / MP4 source
PLAYER_SRC_RE = re.compile(r"""(?:videoUrl|videoSrc)\s*=\s*["'](https?://[^"']+)["']""")
# a show without episode list on its posts: at most this many search pages (40 posts each) for its episodes
SEARCH_EPISODE_PAGES = 8


def _b64Link(value):
    # base64 parameter of the player / download links -> hoster url ("uggcf://" = ROT13 of "https://")
    value = urllib_unquote(value or "").strip()
    try:
        link = base64.b64decode(value + "=" * (-len(value) % 4))
        if not isinstance(link, str):
            link = link.decode("utf-8", "ignore")
    except Exception:
        return ""
    if link.startswith("uggc"):
        out = []
        for ch in link:
            o = ord(ch)
            if 65 <= o <= 90:
                ch = chr((o - 52) % 26 + 65)
            elif 97 <= o <= 122:
                ch = chr((o - 84) % 26 + 97)
            out.append(ch)
        link = "".join(out)
    if link.startswith("//"):
        link = "https:" + link
    return link if re.match(r"https?://[^/\s]+", link) else ""


class WeCima(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "kind", "wf_id", "season_id", "post_id", "ajax_url", "desc",
                  "s_title", "s_season", "s_episode", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "wecima", "cookie": "wecima.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/wecima135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("wecima")
        self.wfInitFolderCache()
        self.MENU = [
            {"category": "wc_section", "title": _("Movies"), "section": "movies"},
            {"category": "wc_section", "title": _("Series"), "section": "series"},
        ] + self.searchItems()
        self.SECTIONS = {
            "movies": [
                ("%s - %s" % (_("Movies"), _("Latest")), "movies/"),
                (_("English movies"), "category/افلام-اجنبي/"),
                (_("Arabic movies"), "category/افلام-عربي/"),
                (_("Indian movies"), "category/افلام-هندي/"),
                (_("Asian movies"), "category/افلام-اسيوي/"),
                (_("Turkish Movies"), "category/افلام-تركية/"),
                (_("Anime movies"), "category/افلام-انمي/"),
            ],
            "series": [
                (_("Newest Episodes"), "episodes/"),
                ("%s - %s" % (_("Series"), _("Latest")), "series/"),
                (_("Arabic Series"), "category/مسلسلات-عربية/"),
                (_("English TV series"), "category/مسلسلات-اجنبي/"),
                (_("Turkish TV series"), "category/مسلسلات-تركية/"),
                (_("Indian TV series"), "category/مسلسلات-هندية/"),
                (_("Asian TV series"), "category/مسلسلات-اسيوية/"),
                (_("Anime TV series"), "category/مسلسلات-انمي/"),
                (_("Dubbed series"), "category/مسلسلات-مدبلجة/"),
                ("%s 2026" % _("Ramadan"), "category/مسلسلات-رمضان-2026/"),
                ("%s 2025" % _("Ramadan"), "category/مسلسلات-رمضان-2025/"),
                ("%s 2024" % _("Ramadan"), "category/مسلسلات-رمضان-2024/"),
            ],
        }

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.wecima_proxy.value) or None

    def _params(self, addParams=None):
        params = dict(self.defaultParams) if addParams is None else addParams
        proxy = self.getProxy()
        if proxy and "http_proxy" not in params:
            params = dict(params, http_proxy=proxy)
        params["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return params

    def getPage(self, baseUrl, addParams=None, post_data=None):
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), self._params(addParams), post_data)

    def selectDomain(self):
        if WeCima.DOMAIN_CACHE:
            self.MAIN_URL = WeCima.DOMAIN_CACHE
            return
        domains = [gettytul()] + list(MIRRORS)
        domain = config.plugins.iptvplayer.wecima_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        self.MAIN_URL = domains[0]
        for domain in domains:
            sts, data = self.cm.getPageCFProtection(domain, self._params())
            if sts and "GridItem" in data:
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", "") or domain)
                break
        WeCima.DOMAIN_CACHE = self.MAIN_URL

    def _canonUrl(self, url):
        # site urls of favourites / old lists on a previous domain -> the current one; the site links the
        # same page raw-Arabic or percent-encoded - one ASCII form
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if not url:
            return ""
        m = re.match(r"https?://[^/]+/(.*)$", url)
        url = (self.MAIN_URL + m.group(1)) if m else self.getFullUrl(url)
        try:
            url = urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")
        except Exception:
            printExc()
        return url

    def getFullIconUrl(self, url, currUrl=None):
        url = (url or "").strip()
        if "://" in url and not url.startswith("http"):
            return url  # the local logo (file://)
        url = self._canonUrl(url) if url else ""
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    @staticmethod
    def _path(url):
        # domain-independent part of a page url (watched keys survive the frequent domain changes)
        path = re.sub(r"^https?://[^/]+", "", url or "").split("?")[0].split("#")[0]
        try:
            path = urllib_unquote(path)
        except Exception:
            printExc()
        return path.rstrip("/").lower() + "/"

    @staticmethod
    def _clean(text):
        text = re.sub(r"(مسلسل|فيلم|انمي)(?=[A-Za-z0-9])", r"\1 ", text or "")  # "مسلسلBatman ..."
        text = JUNK_RE.sub(" ", SUBDUB_RE.sub(r"\1", text))
        return re.sub(r"\s+", " ", text).strip(" -:|")

    @staticmethod
    def _metaTitle(title):
        return re.sub(r"\s+", " ", re.sub(r"(?:^|\s)(?:مدبلج|مدبلجة)(?=\s|$)", " ", title or "")).strip()

    @staticmethod
    def _seasonNum(val):
        return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)

    def _parseTitle(self, title):
        # -> (name, year, season, episode) of a site label
        name = self._clean(title)
        season, episode, year = 0, 0, ""
        m = EPISODE_RE.search(name)
        if m:
            episode = int(m.group(1))
            name = name[:m.start()].strip()
        m = SEASON_RE.search(name)
        if m:
            season = self._seasonNum(m.group(1))
            name = (name[:m.start()] + " " + name[m.end():]).strip()
        name = re.sub(r"\s+", " ", name).strip(" -:|")
        m = YEAR_RE.search(name)
        if m and m.start() > 0:
            year = m.group(1)
            name = (name[:m.start()] + " " + m.group(2).strip()).strip(" -:|")
        return name, year, season, episode

    @staticmethod
    def _seasonId(show, season):
        return "%s|%d" % (re.sub(r"\s+", " ", show or "").strip().lower(), season or 1)

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict) or not cItem.get("kind"):
                return ""
            category = cItem.get("category", "")
            if category == "wc_video" and cItem.get("url"):
                return "video:%s" % self._path(cItem["url"])
            if category == "wc_season" and cItem.get("wf_id"):
                return "season:%s" % cItem["wf_id"]
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("kind"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # lists
    ###################################################
    def listSection(self, cItem):
        for title, path in self.SECTIONS.get(cItem.get("section", ""), []):
            self.addDir({"name": "category", "category": "wc_list", "good_for_fav": True, "title": title, "url": self._canonUrl(path)})

    def _pageTemplate(self, pagination):
        # url of any page with "{page}" in it, from a numbered pager link: /page/N/, ?offset=N or &page=N
        for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>\s*(\d+)\s*</a>', pagination):
            url = self._canonUrl(href)
            tpl = re.sub(r"(/page/|[?&](?:page|offset)=)%s(?=/|&|$)" % label, r"\g<1>{page}", url, 1)
            if "{page}" in tpl:
                return tpl
        return ""

    def _gridItems(self, data):
        # -> ([(url, label, icon, year)] of the "GridItem" cards, pager html)
        grid = data[data.find('id="MainFiltar"'):] if 'id="MainFiltar"' in data else data
        pagination = self.cm.ph.getDataBeetwenMarkers(grid, '<div class="pagination">', "</ul>", False)[1]
        items = []
        for item in grid.split('<div class="pagination">')[0].split('<div class="GridItem">')[1:]:
            url = self._canonUrl(self.cm.ph.getSearchGroups(item, r'<a href="([^"]+)"')[0])
            if not url:
                continue
            raw = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a href="[^"]+" title="([^"]+)"')[0])
            if not raw:
                raw = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, "<strong", "<span", False)[1])
            icon = self.cm.ph.getSearchGroups(item, r"url\(([^)]+)\)")[0].strip("'\" ")
            year = self.cm.ph.getSearchGroups(item, r'<span class="year">\s*\(?\s*(\d{4})')[0]
            items.append((url, raw, icon, year))
        return items, pagination

    def listItems(self, cItem):
        printDBG("WeCima.listItems [%s]" % cItem.get("url", ""))
        page = int(cItem.get("page", 1) or 1)
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        items, pagination = self._gridItems(data)
        normalize = IsMediaNamingNormalized()
        seen = set()
        for url, raw, icon, siteYear in items:
            name, year, season, episode = self._parseTitle(raw)
            year = year or siteYear
            params = {"name": "category", "good_for_fav": True, "icon": self.getFullIconUrl(icon), "url": url}
            if episode or self._path(url).startswith("/series/"):
                # an episode post or a show's own page -> its season folder (one per show + season on this page)
                season = season or 1
                wfId = self._seasonId(name, season)
                if wfId in seen:
                    continue
                seen.add(wfId)
                title = ("%s - %s %d" % (name, _("Season"), season)) if normalize else raw
                params.update({"category": "wc_season", "kind": "season", "title": title, "wf_id": wfId, "desc": raw,
                               "s_title": name, "s_season": season, "meta_type": "tv", "meta_title": self._metaTitle(name), "meta_year": year})
                self.addDir(params)
            else:
                title = ("%s (%s)" % (name, year) if year else name) if normalize else raw
                params.update({"category": "wc_video", "kind": "movie", "title": title or raw,
                               "meta_type": "movie", "meta_title": self._metaTitle(name), "meta_year": year})
                self.addVideo(params)
        hasNext = bool(items) and "next page-numbers" in pagination
        nums = [int(n) for n in re.findall(r'class="page-numbers[^"]*"[^>]*>\s*(\d+)\s*<', pagination)]
        lastPage = max(nums + [page]) if hasNext else page
        addPagingItems(self, dict(cItem, category="wc_list"), page, hasNext, lastPage, self._pageTemplate(pagination))

    def _episodeRow(self, cItem, url, epNum, label, season):
        show = cItem.get("s_title", "")
        if IsMediaNamingNormalized() and epNum and show:
            title = "%s - %s" % (show, formatSxxExx(season, epNum))
        else:
            title = label
        return {"name": "category", "good_for_fav": True, "category": "wc_video", "kind": "episode", "title": title, "url": url,
                "icon": cItem.get("icon", ""), "s_title": show, "s_season": season, "s_episode": epNum,
                "meta_type": "tv", "meta_title": cItem.get("meta_title", ""), "meta_year": cItem.get("meta_year", "")}

    def _otherSeasons(self, cItem, data):
        # the show's other seasons as folders; -> number of the season shown on this page
        show = cItem.get("s_title", "")
        season = cItem.get("s_season", 1) or 1
        postId = self.cm.ph.getSearchGroups(data, r"post_id:\s*'(\d+)'")[0]
        ajaxUrl = self.cm.ph.getSearchGroups(data, r'AjaxtURL\s*=\s*"([^"]+)"')[0]
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="SeasonsList">', "</ul>", False)[1]
        normalize = IsMediaNamingNormalized()
        others = []
        for attrs, inner in re.findall(r"<li([^>]*)>(.*?)</li>", block, re.S):
            label = self.cleanHtmlStr(inner)
            num = self._parseTitle(label)[2]
            sid = self.cm.ph.getSearchGroups(inner, r'data-season="(\d+)"')[0]
            if "active" in attrs:
                season = num or season
                continue
            if not sid or not postId:
                continue
            others.append((num, {"name": "category", "good_for_fav": True, "category": "wc_season", "kind": "season",
                                 "title": ("%s - %s %d" % (show, _("Season"), num)) if (normalize and num) else ("%s %s" % (show, label)).strip(),
                                 "url": cItem["url"], "icon": cItem.get("icon", ""),
                                 "wf_id": self._seasonId(show, num) if num else "%s|id%s" % (show.lower(), sid),
                                 "season_id": sid, "post_id": postId, "ajax_url": ajaxUrl, "s_title": show, "s_season": num or 1,
                                 "meta_type": "tv", "meta_title": cItem.get("meta_title", ""), "meta_year": cItem.get("meta_year", "")}))
        others.sort(key=lambda o: o[0])
        for _num, params in others:
            # siblings, not children of the season shown: kept out of its watched chain (it would only count as
            # watched once every other season is)
            CBaseHostClass.addDir(self, params)
        return season

    def listSeason(self, cItem):
        printDBG("WeCima.listSeason [%s]" % cItem.get("url", ""))
        season = cItem.get("s_season", 1) or 1
        if cItem.get("season_id"):
            # another season of the show: the theme loads its episodes by Ajax
            params = dict(self.defaultParams)
            params["header"] = dict(self.HEADER, Referer=self._canonUrl(cItem["url"]))
            params["header"]["X-Requested-With"] = "XMLHttpRequest"
            ajaxUrl = cItem.get("ajax_url") or "wp-content/themes/maycima/Ajaxt/"
            sts, block = self.getPage(ajaxUrl.rstrip("/") + "/Single/Episodes.php", params,
                                      {"season": cItem["season_id"], "post_id": cItem.get("post_id", "")})
            if not sts:
                return
            data = ""
        else:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
            season = self._otherSeasons(cItem, data)
            block = data[data.find('<div class="EpisodesList">'):] if '<div class="EpisodesList">' in data else ""
            block = block.split("</singlesection>")[0].split("<script")[0]
        episodes = []
        seen = set()
        for href, inner in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S):
            url = self._canonUrl(href)
            if url in seen or "episodetitle" not in inner:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(inner, "<episodetitle>", "</episodetitle>", False)[1]) or self.cleanHtmlStr(inner)
            epNum = self._parseTitle(label)[3] or int(self.cm.ph.getSearchGroups(label, r"(\d+)")[0] or 0)
            episodes.append((epNum, self._episodeRow(cItem, url, epNum, label, season)))
        if not episodes and data:
            # a post without an episode list (show not linked to a season on the site): its episodes from the search
            episodes = self._searchEpisodes(cItem, season)
        if not episodes and data:
            # no episode found at all: the post itself is the only episode
            label = cItem.get("desc", "") or cItem.get("title", "")
            episodes.append((0, self._episodeRow(cItem, self._canonUrl(cItem["url"]), self._parseTitle(label)[3], label, season)))
        episodes.sort(key=lambda e: e[0])
        for _num, params in episodes:
            self.addVideo(params)

    def _searchEpisodes(self, cItem, season):
        # the site search for the show name, pages of 40 posts: the posts of this show + season
        show = cItem.get("s_title", "")
        if not show:
            return []
        key = self._seasonId(show, season)
        base = self.getFullUrl("?s=%s" % urllib_quote_plus(show))
        episodes = []
        seen = set()
        for page in range(1, SEARCH_EPISODE_PAGES + 1):
            sts, data = self.getPage(base if page == 1 else "%s&page=%d" % (base, page))
            if not sts:
                break
            items, pagination = self._gridItems(data)
            for url, raw, _icon, _year in items:
                name, _y, num, epNum = self._parseTitle(raw)
                if not epNum or url in seen or self._seasonId(name, num or 1) != key:
                    continue
                seen.add(url)
                episodes.append((epNum, self._episodeRow(cItem, url, epNum, raw, season)))
            if "next page-numbers" not in pagination:
                break
        return episodes

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("WeCima.listSearchResult [%s]" % searchPattern)
        self.listItems(dict(cItem, url=self.getFullUrl("?s=%s" % urllib_quote_plus(searchPattern.strip())), page=1))

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<div class="StoryMovieContent">', "</div>", False)[1])
        info = {}
        terms = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="Terms--Content--Single-begin">', "</ul>", False)[1]
        for li in re.findall(r"<li>(.*?)</li>", terms, re.S):
            label = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(li, "<span>", "</span>", False)[1])
            values = [self.cleanHtmlStr(v) for v in re.findall(r"<a[^>]*>(.*?)</a>", li, re.S)]
            values = [v for v in values if v]
            for key, word in INFO_FIELDS:
                if label == word and values:
                    info[key] = ", ".join(values)
        year = self.cm.ph.getSearchGroups(data, r"/release-year/(\d{4})/")[0]
        if year:
            info["year"] = year
        return story, info

    def getLinksForVideo(self, cItem):
        printDBG("WeCima.getLinksForVideo [%s]" % cItem.get("url", ""))
        pageUrl = self._canonUrl(cItem.get("url", ""))
        sts, data = self.getPage(pageUrl)
        if not sts:
            return []
        urltab = []
        names = {}

        def add(name, url):
            if not self.cm.isValidUrl(url) or url in [u["url"] for u in urltab]:
                return
            names[name.lower()] = names.get(name.lower(), 0) + 1
            if names[name.lower()] > 1:
                name = "%s %d" % (name, names[name.lower()])
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": pageUrl}), "need_resolve": 1})

        watch = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="WatchServersList">', "</div>", False)[1]
        for li in re.findall(r"<li[^>]+data-watch=.*?</li>", watch, re.S):
            url = self.cm.ph.getSearchGroups(li, r'data-watch="([^"]+)"')[0].replace("&amp;", "&").strip()
            # akhbarworld.online?<key>=<base64 of the hoster embed> or ?my_player=<id> (the site's own MP4)
            embed = _b64Link(self.cm.ph.getSearchGroups(url, r"[?&][a-z_]+=([A-Za-z0-9+/=%]{16,})")[0])
            domain = self.up.getDomain(embed or url, onlyDomain=True)
            label = self.cleanHtmlStr(li)
            add("%s (%s)" % (label, domain) if label else domain, url)
        # downloads: topvi..?vt_download=<base64 of the ROT13 vidtube url>&q=1080p+FHD; the site's own
        # secure_stream downloads are the watch server's file again (or a page that prepares it by script)
        download = self.cm.ph.getDataBeetwenMarkers(data, "List--Download--Wecima--Single", "</ul>", False)[1]
        for href, inner in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', download, re.S):
            href = href.replace("&#038;", "&").replace("&amp;", "&").strip()
            link = _b64Link(self.cm.ph.getSearchGroups(href, r"vt_download=([^&]+)")[0]) or href
            if 1 != self.up.checkHostSupport(link):
                continue
            quality = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(inner, "<resolution>", "</resolution>", False)[1])
            add("%s (%s)" % (" ".join(x for x in (_("Download"), quality) if x), self.up.getDomain(link, onlyDomain=True)), link)
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), self._siteInfo(data)[0]))

    def _playerSources(self, playerUrl):
        # the player page of a watch server: "const videoUrl = .." (MP4 / HLS master, needs the page as Referer)
        params = self._params()
        params["header"] = dict(self.HEADER, Referer=self.getMainUrl())
        sts, data = self.cm.getPage(playerUrl, params)
        if not sts:
            return []
        src = self.cm.ph.getSearchGroups(data, PLAYER_SRC_RE.pattern)[0].replace("&#038;", "&").replace("&amp;", "&")
        if not src:
            return []
        origin = self.cm.getBaseUrl(self.cm.meta.get("url", "") or playerUrl)
        meta = {"Referer": origin, "Origin": origin.rstrip("/"), "User-Agent": self.HEADER.get("User-Agent")}
        if re.search(r"\.(?:m3u8|txt)(?:\?|$)", src) or "/hls" in src:
            return getDirectM3U8Playlist(strwithmeta(src, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)
        return [{"name": "MP4", "url": strwithmeta(src, meta)}]

    def getVideoLinks(self, videoUrl):
        printDBG("WeCima.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        if 1 == self.up.checkHostSupport(videoUrl):
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        # a watch server's player page: the hoster embed of its base64 parameter when urlparser knows it,
        # else the page's own source
        embed = _b64Link(self.cm.ph.getSearchGroups(videoUrl, r"[?&][a-z_]+=([A-Za-z0-9+/=%]{16,})")[0])
        links = []
        if embed and 1 == self.up.checkHostSupport(embed):
            links = self.up.getVideoLinkExt(strwithmeta(embed, {"Referer": self.cm.getBaseUrl(videoUrl)}))
        if not links:
            links = self._playerSources(videoUrl)
        if not links:
            SetIPTVPlayerLastHostError(_("No stream available"))
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("WeCima.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        story, info = "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, info = self._siteInfo(data)
            # episode posts have no story: their full site title instead
            story = story or self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, "<h1", "</h1>", True)[1])
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        info.update(meta.get("info", {}))
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
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
        printDBG("WeCima.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listsTab(self.MENU, {"name": "category"})
        elif category == "wc_section":
            self.listSection(self.currItem)
        elif category == "wc_list":
            self.listItems(self.currItem)
        elif category == "wc_season":
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
        CHostBase.__init__(self, WeCima(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("wecima")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("wc_video", "wc_season")
