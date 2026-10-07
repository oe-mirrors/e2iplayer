# -*- coding: utf-8 -*-
# Last Modified: 07.10.2026
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 framework / host standard (site now "سيما وبس", cimawbs.cfd):
#   - "Latest" (newvideos.php), the site categories grouped into Movies / Series / Other (the old
#     'programmes' entry crashed: a tuple was tested with `in` against a string) and search, with
#     First page / Jump / Next page (n/last) from the site's pager
#   - episode rows of a list -> one series folder per show/season (the episode page lists all its
#     episodes, more season tabs -> season folders); movies and plays are VIDEO rows on their page url
#   - links: the servers of play.php?vid=<id> handed to urlparser
#   - watched flag (series -> season -> episode), downloaded flag, favourites (urls re-based on the
#     current domain), name normalisation ("Title (Year)", "Show - SxxExx" from the Arabic labels),
#     sidecar, INFO via moviemeta + the site's story/actors/poster; no colour codes in titles
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir, E2ColoR, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.cimacity_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.cimacity_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.cimacity_proxy))
    if config.plugins.iptvplayer.cimacity_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.cimacity_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://cimawbs.cfd/"


# Arabic ordinals of season labels ("الموسم الثاني")
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5),
    ("السادسة", 6), ("السادس", 6), ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8),
    ("التاسعة", 9), ("التاسع", 9), ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"الموسم\s*(\d+|%s)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d{2})(?=\s|\)|$)")
KIND_RE = re.compile(r"^\s*(?:مسلسل|برنامج|انمي|أنمي)\s+")
# fix 071026: + "جميع الحلقات" / "كل الحلقات" ("all episodes", "مسلسل X كامل جميع الحلقات" made a second folder
# "X جميع الحلقات" next to the episode rows of X), "جميع المواسم", "حصريا", "والأخيرة" (last episode)
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجم|اون لاين|أون لاين|مشاهدة|فيلم|كامل|كاملة|بجودة عالية|HD|FHD|"
                     r"جميع الحلقات|جميع حلقات|كل الحلقات|جميع المواسم|كل المواسم|حصريا|حصرياً|والأخيرة|والاخيرة)(?=\s|$)")
MENU_GROUPS = (("movies", "افلام"), ("series", "مسلسلات"))


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


CAT_KEY = "category.php?cat="
WATCH_KEY = "watch.php?vid="
EPISODE_LINK_RE = re.compile(r'(?s)<a href="([^"]*)"([^>]*)>(.*?)</a>')
ACTOR_SEP_RE = re.compile(r"[-.،]\s*")


def _isCategoryHref(value):
    # "...category.php?cat=<id>" with no "&" after the id
    i = value.find(CAT_KEY)
    while i >= 0:
        tail = value[i + len(CAT_KEY):]
        if tail and "&" not in tail:
            return True
        i = value.find(CAT_KEY, i + 1)
    return False


def _categoryLinks(data):
    # (href, label) of the <a ... href="..category.php?cat=..">label</a> links, scanned like a regex findall
    out = []
    pos = 0
    while True:
        s = data.find("<a", pos)
        if s < 0:
            return out
        gt = data.find(">", s + 2)
        if gt < 0:
            gt = len(data)
        found = None
        h = data.rfind('href="', s + 3, gt)
        while h >= 0 and found is None:
            q = data.find('"', h + 6)
            if q >= 0 and _isCategoryHref(data[h + 6:q]):
                g = data.find(">", q + 1)
                e = data.find("</a>", g + 1) if g >= 0 else -1
                if e >= 0:
                    found = (data[h + 6:q], data[g + 1:e])
                    pos = e + 4
            h = data.rfind('href="', s + 3, h)
        if found:
            out.append(found)
        else:
            pos = s + 1


def _episodeLinks(block):
    # (href, attrs, inner) of the <a href="..watch.php?vid=.." ...>inner</a> links
    out = []
    pos = 0
    while True:
        m = EPISODE_LINK_RE.search(block, pos)
        if not m:
            return out
        if WATCH_KEY in m.group(1)[:-1]:
            out.append(m.groups())
            pos = m.end()
        else:
            pos = m.start() + 1


def _joinActors(text):
    # "a - b . c ، d" -> "a, b, c, d"
    parts = ACTOR_SEP_RE.split(text)
    return ", ".join([p.rstrip() for p in parts[:-1]] + parts[-1:])


class CimaCity(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode", "season_id",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "cimacity", "cookie": "cimacity.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/cimacity135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("cimacity")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.cimacity_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        if CimaCity.DOMAIN_CACHE:
            self.MAIN_URL = CimaCity.DOMAIN_CACHE
            return
        domains = [gettytul()]
        domain = config.plugins.iptvplayer.cimacity_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.getPage(domain)
            if sts and "listCat" in data:
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", domain))
                break
        else:
            self.MAIN_URL = domains[-1]
        CimaCity.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / old lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
        m = re.match(r"https?://[^/]+/(.*)$", url)
        url = (self.MAIN_URL + m.group(1)) if m else self.getFullUrl(url)
        # Arabic search words in the pager links -> one percent-encoded form
        return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, (url or "").strip(), currUrl)
        proxy = self.getProxy()
        if url and proxy:
            url = strwithmeta(url, {"iptv_http_proxy": proxy})
        return url

    @staticmethod
    def _vid(url):
        m = re.search(r"[?&]vid=([^&#]+)", url or "")
        return m.group(1) if m else ""

    @staticmethod
    def _cleanSpaces(text):
        return re.sub(r"\s+", " ", text or "").strip(" -:|")

    def _splitTitle(self, title):
        # "مسلسل From الموسم الرابع الحلقة 3 الثالثة مترجمة" -> show "From", season 4, episode 3
        # "فيلم Nimrods 2025 مترجم كامل HD" -> "Nimrods", year 2025
        episode = self.cm.ph.getSearchGroups(title, EPISODE_RE.pattern)[0]
        season = _seasonNum(title)
        show = title
        if episode:
            show = EPISODE_RE.split(show)[0]
        show = SEASON_RE.split(show)[0] if season else show
        show = KIND_RE.sub("", show)
        show = JUNK_RE.sub(" ", show)
        years = YEAR_RE.findall(show)
        year = years[-1] if years else ""
        if year and not episode:
            show = re.sub(r"\(?%s\)?" % year, " ", show)
        return self._cleanSpaces(show), season, episode, year

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category") in ("cc_video", "cc_series", "cc_season"):
                return json_dumps({key: cItem[key] for key in self.FAV_FIELDS if key in cItem})
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
            if category == "cc_video":
                vid = self._vid(cItem.get("url", ""))
                return "video:%s" % vid if vid else ""
            show = cItem.get("s_title", "").lower()
            if category == "cc_series" and show:
                return "series:%s|%s" % (show, cItem.get("s_season", 0))
            if category == "cc_season" and show:
                return "season:%s|%s" % (show, cItem.get("s_season", 0))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        tab = [
            {"category": "list_items", "title": _("Latest"), "url": self.getFullUrl("/newvideos.php"), "good_for_fav": True},
            {"category": "cc_menu", "title": _("Movies"), "group": "movies"},
            {"category": "cc_menu", "title": _("Series"), "group": "series"},
            {"category": "cc_menu", "title": _("Other"), "group": "other"},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listSiteMenu(self, cItem):
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        group = cItem.get("group", "")
        seen = set()
        for href, label in _categoryLinks(data):
            title = self.cleanHtmlStr(label)
            url = self._rebase(href)
            if not title or url in seen:
                continue
            itemGroup = "other"
            for name, word in MENU_GROUPS:
                if title.startswith(word):
                    itemGroup = name
            if itemGroup != group:
                continue
            seen.add(url)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": url})

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = self._rebase(cItem["url"])
        printDBG("CimaCity.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        grid = self.cm.ph.getDataBeetwenMarkers(data, 'id="pm-grid"', "</ul>", False)[1]
        seen = set()
        count = 0
        for item in self.cm.ph.getAllItemsBeetwenMarkers(grid, "<li", "</li>"):
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]*watch\.php\?vid=[^"]+)"')[0]
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="ellipsis"[^>]*>(.*?)</a>')[0])
            if not rawTitle:
                rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            if not href or not rawTitle:
                continue
            count += 1
            url = self._rebase(href)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            show, season, episode, year = self._splitTitle(rawTitle)
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)class="pm-label-duration">(.*?)</span>')[0])
            if episode or KIND_RE.match(rawTitle):
                # one folder per show / season - the episode page lists all episodes of it
                key = (show.lower(), season)
                if not show or key in seen:
                    continue
                seen.add(key)
                title = show
                if season:
                    title = ("%s - %s" % (show, formatSxxExx(season))) if normalize else "%s - %s %d" % (show, _("Season"), season)
                self.addDir({"name": "category", "category": "cc_series", "good_for_fav": True, "title": title, "url": url, "icon": icon,
                             "desc": "", "s_title": show, "s_season": season, "meta_type": "tv", "meta_title": show})
            else:
                if url in seen:
                    continue
                seen.add(url)
                fields = ((_("Year"), year, "cyan"), (_("Duration"), duration, "green"))
                desc = " | ".join(["%s%s:%s %s" % (E2ColoR(color), label, E2ColoR("white"), value) for label, value, color in fields if value])
                title = rawTitle
                if normalize and show:
                    title = "%s (%s)" % (show, year) if year else show
                self.addVideo({"name": "category", "category": "cc_video", "good_for_fav": True, "title": title, "url": url, "icon": icon,
                               "desc": desc, "meta_type": "movie", "meta_title": show or rawTitle, "meta_year": year})

        # pager links: category.php?cat=x&page=N&order=DESC, newvideos.php?&page=N, search.php?keywords=x&page=N
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<ul class="pagination', "</ul>", False)[1]
        nums = [int(n) for n in re.findall(r"<a[^>]*>\s*(\d+)\s*</a>", pager)]
        lastPage = max(nums + [page])
        pageTpl = ""
        for href in re.findall(r'<a[^>]+href="([^"#]+)"', pager):
            tpl = re.sub(r"([?&]page=)\d+", r"\1{page}", self._rebase(href), 1)
            if "{page}" in tpl:
                pageTpl = tpl
        hasNext = count > 0 and lastPage > page and bool(pageTpl)
        listItem = dict(cItem)
        listItem.update({"category": "list_items"})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def _seasonTabs(self, data):
        # [(tab id, season number, label)] of the "المواسم والحلقات" box
        box = self.cm.ph.getDataBeetwenMarkers(data, 'class="SeasonsBoxUL"', "</div>", False)[1]
        tabs = []
        for tabId, label in re.findall(r"openCity\(event,\s*'([^']+)'\)\"?[^>]*>([^<]+)<", box):
            label = self.cleanHtmlStr(label)
            tabs.append((tabId, _seasonNum(label), label))
        return tabs

    def listSeries(self, cItem):
        printDBG("CimaCity.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        tabs = self._seasonTabs(data)
        if len(tabs) > 1:
            normalize = IsMediaNamingNormalized()
            for tabId, num, label in sorted(tabs, key=lambda t: t[1]):
                num = num or cItem.get("s_season", 0)
                title = ("%s - %s" % (cItem.get("s_title", ""), formatSxxExx(num))) if normalize and num else label
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "cc_season", "title": title, "season_id": tabId, "s_season": num})
                self.addDir(params)
            return
        if tabs:
            cItem = dict(cItem, season_id=tabs[0][0], s_season=tabs[0][1] or cItem.get("s_season", 0))
        self.listEpisodes(cItem, data)

    def listEpisodes(self, cItem, data=None):
        printDBG("CimaCity.listEpisodes [%s]" % cItem.get("url", ""))
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 0) or 1
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="%s"' % cItem.get("season_id", "Season0"), "</ul>", False)[1]
        normalize = IsMediaNamingNormalized()
        seen = set()
        for href, attrs, inner in _episodeLinks(block):
            url = self._rebase(href)
            if url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(attrs, r'title="([^"]+)"')[0])
            episode = self.cleanHtmlStr(self.cm.ph.getSearchGroups(inner, r"(?s)<em>(.*?)</em>")[0])
            if not episode.isdigit():
                episode = self.cm.ph.getSearchGroups(label, EPISODE_RE.pattern)[0]
            if normalize and episode:
                title = "%s - %s" % (show, formatSxxExx(season, episode))
            else:
                title = label or ("%s - %s %s" % (show, _("Episode"), episode))
            self.addVideo({"name": "category", "category": "cc_video", "good_for_fav": True, "title": title, "url": url,
                           "icon": cItem.get("icon", ""), "desc": "", "s_title": show, "s_season": season, "s_episode": episode,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        if not seen:
            # a series page without an episode box - the page itself is the video
            params = dict(cItem)
            params.update({"category": "cc_video", "good_for_fav": True})
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("CimaCity.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/search.php?keywords=%s" % urllib_quote_plus(searchPattern.strip())), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        box = self.cm.ph.getDataBeetwenMarkers(data, 'itemprop="Meta2Desc"', '<div class="video-info-container', False)[1]
        # "<h3>قصة ...</h3> story <h3|h4>ابطال ...</h3|h4> actors"
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r"(?s)قصة[^<]*</h3>(.*?)(?:<h[34][^>]*>\s*(?:<strong>)?\s*ابطال|</div>)")[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta property="og:description" content="([^"]+)"')[0])
        info = {}
        actors = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r"(?s)ابطال[^<]*(?:</strong>)?\s*</h[34]>(.*?)(?:<h[34]|</div>|<dl)")[0])
        actors = _joinActors(actors).strip(" ,")
        if actors:
            info["actors"] = actors
        genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="seasonEp"><a[^>]*>(.*?)</a>')[0])
        if genre:
            info["category"] = genre
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        if "social-thumb" in poster:
            poster = ""
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("CimaCity.getLinksForVideo [%s]" % cItem.get("url", ""))
        vid = self._vid(cItem.get("url", ""))
        if not vid:
            return []
        sts, data = self.getPage(self.getFullUrl("/play.php?vid=%s" % vid))
        if not sts:
            return []
        urltab = []
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="list_servers', "</ul>", False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<li", "</li>"):
            embed = self.cm.ph.getSearchGroups(item, r'data-embed="([^"]+)"')[0].replace("&lt;", "<").replace("&gt;", ">")
            url = self.cm.ph.getSearchGroups(embed, r"""src=['"]([^'"]+)['"]""")[0].strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url):
                continue
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<strong>(.*?)</strong>")[0])
            domain = self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]
            urltab.append({"name": "%s (%s)" % (label, domain) if label else domain, "url": strwithmeta(url, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("CimaCity.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("CimaCity.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
                meta = getMeta(cItem["meta_type"], cItem["meta_title"], cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
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
        printDBG("CimaCity.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "cc_menu":
            self.listSiteMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "cc_series":
            self.listSeries(self.currItem)
        elif category == "cc_season":
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
        CHostBase.__init__(self, CimaCity(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("cimacity")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("cc_video", "cc_series", "cc_season")
