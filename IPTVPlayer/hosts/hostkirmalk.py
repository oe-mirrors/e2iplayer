# -*- coding: utf-8 -*-
LAST_MODIFIED = "20.11.2026"
# Coding: BY MOHAMED_OS
# 06.10.2026 - ported to the python3 framework / host standard (kirmalk.com, home now /kr20):
#   - "Latest", latest episodes, movies, series, the site categories and search, with First page /
#     Jump / Next page (n/last) from the site's pager
#   - episode rows of a list -> one series folder per show/season (the episode page lists all
#     episodes of it); movies and plays are VIDEO rows on their page url
#   - links: the servers of view.php?vid=<id> handed to urlparser
#   - watched flag (series -> episode), downloaded flag, favourites (urls re-based on the current domain),
#     name normalisation ("Title (Year)", "Show - SxxExx" from the Arabic labels), sidecar, INFO via
#     moviemeta + the site's story/actors/poster; no colour codes in titles
# 20.11.2026 - new site layout: movie / latest / series cards, series-profile.php seasons + episodes, new pagers
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getItemMeta, metaArticle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, E2ColoR, StripColorCodes
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.kirmalk_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.kirmalk_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.kirmalk_proxy))
    if config.plugins.iptvplayer.kirmalk_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.kirmalk_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://kirmalk.com/"


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
EPISODES_PER_PAGE = 100
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجم|اون لاين|أون لاين|مشاهدة|فيلم|كامل|كاملة|بجودة عالية|HD|FHD|720p|1080p)(?=\s|$)")


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


WATCH_KEY = "watch.php?vid="
EPISODE_LINK_RE = re.compile(r'<a href="([^"]*)"[^>]*>\s*<div class="episode-number-large">\s*(\d+)')
ACTOR_SEP_RE = re.compile(r"(?:،|,|\s و)\s*")
CARD_RE = re.compile(r'<div class="video-card">|<article class="kr-(?:vcard|latest-card|series-tile)\b[^"]*">')
PAGERS = (("pagination-section", "</ul>"), ('<nav class="kr-latest-pagination', "</nav>"), ('<nav class="kr-pagination', "</nav>"),
          ('<nav class="kr-directory-pages', "</nav>"))
# series-profile.php: <article class="kr-episode"><a href="..watch.php?vid=.."> .. <h4>title</h4>
PROFILE_EPISODE_RE = re.compile(r'(?s)<article class="kr-episode">\s*<a href="([^"]*watch\.php\?vid=[^"]+)".*?<img[^>]+src="([^"]*)".*?<h4>(.*?)</h4>')


def _episodeLinks(block):
    # (href, number) of the <a href="..watch.php?vid=.."><div class="episode-number-large">N links
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
    # "a، b, c و d" -> "a, b, c, d"
    parts = ACTOR_SEP_RE.split(text)
    return ", ".join([p.rstrip() for p in parts[:-1]] + parts[-1:])


class KirMalk(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "kirmalk", "cookie": "kirmalk.cookie"})
        self.MAIN_URL = None
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("kirmalk")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.kirmalk_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        if KirMalk.DOMAIN_CACHE:
            self.MAIN_URL = KirMalk.DOMAIN_CACHE
            return
        domains = [gettytul()]
        domain = config.plugins.iptvplayer.kirmalk_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.getPage(domain)
            if sts and "video-card" in data:
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", domain))
                break
        else:
            self.MAIN_URL = domains[-1]
        KirMalk.DOMAIN_CACHE = self.MAIN_URL

    def _rebase(self, url):
        # urls of favourites / old lists on a previous domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").strip()
        if url.startswith("./"):
            url = url[2:]
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

    def _splitTitle(self, title):
        # "مسلسل سر الحنين الحلقة 162 مدبلجة HD" -> show "سر الحنين مدبلجة", season 0, episode 162
        # "مشاهدة فيلم المهايطية 2026 HD" -> "المهايطية", year 2026
        episode = self.cm.ph.getSearchGroups(title, EPISODE_RE.pattern)[0]
        season = _seasonNum(title)
        show = title
        if episode:
            show = EPISODE_RE.split(show)[0]
        show = SEASON_RE.split(show)[0] if season else show
        show = KIND_RE.sub("", JUNK_RE.sub(" ", show))
        years = YEAR_RE.findall(show)
        year = years[-1] if years else ""
        if year and not episode:
            show = re.sub(r"\(?%s\)?" % year, " ", show)
        show = re.sub(r"\(\s*\)", " ", show)
        return re.sub(r"\s+", " ", show).strip(" -:|"), season, episode, year

    def getFavouriteData(self, cItem):
        if cItem.get("category") in ("km_video", "km_series"):
            return self.getFavouriteFieldsData(cItem)
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            if category == "km_video":
                vid = self._vid(cItem.get("url", ""))
                return "video:%s" % vid if vid else ""
            show = cItem.get("s_title", "").lower()
            if category == "km_series" and show:
                return "series:%s|%s" % (show, cItem.get("s_season", 0))
        except Exception:
            printExc()
        return ""

    ###################################################
    # lists
    ###################################################
    def listMainMenu(self, cItem):
        def item(title, path):
            return {"category": "list_items", "title": title, "url": self.getFullUrl(path), "good_for_fav": True}
        tab = [
            item(_("Latest"), "/newvideos.php"),
            item(_("Latest episodes"), "/episodes.php"),
            item(_("Movies"), "/movies.php"),
            item(_("Series"), "/all-series.php"),
            {"category": "km_categories", "title": _("Categories"), "url": self.getFullUrl("/category.php")},
        ]
        self.listsTab(tab + self.searchItems(), cItem)

    def listCategories(self, cItem):
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        grid = self.cm.ph.getDataBeetwenMarkers(data, "categories-grid-section", "</section>", False)[1]
        for href, label in re.findall(r'(?s)<a href="([^"]+)" class="category-card-link">.*?alt="([^"]*)"', grid):
            title = self.cleanHtmlStr(label)
            if title:
                self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": self._rebase(href),
                             "icon": self.getFullIconUrl(self.cm.ph.getSearchGroups(grid.split(href, 1)[-1], r'<img[^>]+src="([^"]+)"')[0])})

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = self._rebase(cItem["url"])
        printDBG("KirMalk.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        normalize = IsMediaNamingNormalized()
        seriesList = "all-series.php" in url
        seen = set()
        count = 0
        # cards: <div class="video-card"> (episodes, categories, search), <article class="kr-vcard"> (movies),
        # <article class="kr-latest-card"> (latest), <article class="kr-series-tile"> (series -> series-profile.php)
        for item in CARD_RE.split(data)[1:]:
            profile = self.cm.ph.getSearchGroups(item, r'<a href="([^"]*series-profile\.php\?id=\d+)"')[0]
            if profile:
                rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<h3>(.*?)</h3>")[0] or self.cm.ph.getSearchGroups(item, r'<img[^>]+alt="([^"]+)"')[0])
                if not rawTitle:
                    continue
                count += 1
                show = self._splitTitle(rawTitle)[0] or rawTitle
                if profile in seen:
                    continue
                seen.add(profile)
                seasons = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)</h3>\s*<p>(.*?)</p>")[0])
                self.addDir({"name": "category", "category": "km_series", "good_for_fav": True, "title": show, "url": self._rebase(profile),
                             "icon": self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0]), "desc": seasons,
                             "s_title": show, "s_season": 0, "meta_type": "tv", "meta_title": show})
                continue
            href = self.cm.ph.getSearchGroups(item, r'<a[^>]+href="([^"]*watch\.php\?vid=[^"]+)"')[0]
            rawTitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'<a[^>]+title="([^"]+)"')[0])
            if not href or not rawTitle:
                continue
            count += 1
            url = self._rebase(href)
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, r'<img[^>]+src="([^"]+)"')[0])
            show, season, episode, year = self._splitTitle(rawTitle)
            if seriesList and (episode or KIND_RE.match(rawTitle)):
                # the card title of the series list is the show name ("لا احد سواك مدبلج")
                show = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<div class="video-title">\s*<a[^>]*>(.*?)</a>')[0]) or show
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)fa-clock"></i>\s*<span>(.*?)</span>')[0] or
                                         self.cm.ph.getSearchGroups(item, r'class="kr-(?:latest-)?duration"[^>]*>([^<]+)<')[0])
            if episode or KIND_RE.match(rawTitle):
                key = (show.lower(), season)
                if not show or key in seen:
                    continue
                seen.add(key)
                title = show
                if season:
                    title = ("%s - %s" % (show, formatSxxExx(season))) if normalize else "%s - %s %d" % (show, _("Season"), season)
                self.addDir({"name": "category", "category": "km_series", "good_for_fav": True, "title": title, "url": url, "icon": icon,
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
                self.addVideo({"name": "category", "category": "km_video", "good_for_fav": True, "title": title, "url": url, "icon": icon,
                               "desc": desc, "meta_type": "movie", "meta_title": show or rawTitle, "meta_year": year})

        # pager links: movies02?page=N, newvideos.php?&page=N, series01?q=&type=&page=N, category.php?cat=x&page=N&order=DESC,
        # search.php?keywords=x&page=N
        pager = ""
        for start, end in PAGERS:
            pager = self.cm.ph.getDataBeetwenMarkers(data, start, end, False)[1]
            if pager:
                break
        nums = [int(n) for n in re.findall(r"<a[^>]*>\s*(\d+)\s*</a>", pager)]
        lastPage = max(nums + [page])
        pageTpl = ""
        for href in re.findall(r'<a href="([^"#]+)"', pager):
            tpl = re.sub(r"([?&]page=)\d+", r"\1{page}", self._rebase(href), count=1)
            if "{page}" in tpl:
                pageTpl = tpl
        hasNext = count > 0 and lastPage > page and bool(pageTpl)
        listItem = dict(cItem)
        listItem.update({"category": "list_items"})
        addPagingItems(self, listItem, page, hasNext, lastPage, pageTpl)

    def listEpisodes(self, cItem):
        printDBG("KirMalk.listEpisodes [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        if "series-profile.php" in cItem["url"]:
            self.listProfile(cItem, data)
            return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        season = cItem.get("s_season", 0) or 1
        block = self.cm.ph.getDataBeetwenMarkers(data, 'class="episodes-grid-classic"', "</section>", False)[1]
        profile = self.cm.ph.getSearchGroups(data, r'href="([^"]*series-profile\.php\?id=\d+)"')[0]
        if not block and profile:
            # since 11.2026 the episode page has no episode box any more: the series page has them
            url = self._rebase(profile)
            if cItem.get("s_season"):
                url += "&season=%s" % cItem["s_season"]
            sts, data = self.getPage(url)
            if sts:
                self.listProfile(dict(cItem, url=url, page=1), data)
                if self.currList:
                    return
        normalize = IsMediaNamingNormalized()
        episodes = []
        for href, num in _episodeLinks(block):
            url = self._rebase(href)
            if url not in [e[0] for e in episodes]:
                episodes.append((url, num))
        # long shows (160+ episodes) -> local pages of EPISODES_PER_PAGE
        page = cItem.get("page", 1)
        lastPage = max(1, (len(episodes) + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE)
        for url, num in episodes[(page - 1) * EPISODES_PER_PAGE:page * EPISODES_PER_PAGE]:
            if normalize:
                title = "%s - %s" % (show, formatSxxExx(season, num))
            else:
                title = "%s - %s %s" % (show, _("Episode"), num)
            self.addVideo({"name": "category", "category": "km_video", "good_for_fav": True, "title": title, "url": url,
                           "icon": cItem.get("icon", ""), "desc": "", "s_title": show, "s_season": season, "s_episode": num,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        if lastPage > 1:
            # the "template" is the episode page itself (no {page} in it, the braces are percent-encoded):
            # Jump only needs it to exist, the page number travels in cItem["page"]
            addPagingItems(self, dict(cItem), page, page < lastPage, lastPage, self._rebase(cItem["url"]))
        if not episodes:
            # a series page without an episode box - the page itself is the video
            params = dict(cItem)
            params.update({"category": "km_video", "good_for_fav": True})
            self.addVideo(params)

    def listProfile(self, cItem, data):
        # series-profile.php?id=N[&season=S][&page=P]: season tabs, then the episodes of one season in site pages
        printDBG("KirMalk.listProfile [%s]" % cItem.get("url", ""))
        url = re.sub(r"&page=\d+", "", cItem["url"].split("#", 1)[0])
        title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h1 id="series-title">(.*?)</h1>')[0])
        show = cItem.get("s_title", "") or self._splitTitle(title)[0] or cItem.get("title", "")
        normalize = IsMediaNamingNormalized()
        tabs = self.cm.ph.getDataBeetwenMarkers(data, '<nav class="kr-season-tabs', "</nav>", False)[1]
        seasons = [(self._rebase(href).split("#", 1)[0], int(num)) for href, num in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>[^<]*?(\d+)\s*</a>', tabs)]
        if len(seasons) > 1 and "season=" not in url:
            for seasonUrl, num in seasons:
                seasonTitle = ("%s - %s" % (show, formatSxxExx(num))) if normalize else "%s - %s %d" % (show, _("Season"), num)
                params = dict(cItem)
                params.update({"good_for_fav": True, "title": seasonTitle, "url": seasonUrl, "s_title": show, "s_season": num, "page": 1})
                self.addDir(params)
            return
        active = self.cm.ph.getSearchGroups(tabs, r'class="kr-button active"[^>]*>[^<]*?(\d+)\s*<')[0]
        season = int(active) if active else (cItem.get("s_season", 0) or 1)
        page = cItem.get("page", 1)
        block = self.cm.ph.getDataBeetwenMarkers(data, '<div class="kr-episodes">', "</section>", False)[1]
        for idx, (href, icon, label) in enumerate(PROFILE_EPISODE_RE.findall(block)):
            label = self.cleanHtmlStr(label)
            num = self.cm.ph.getSearchGroups(label, EPISODE_RE.pattern)[0] or str(idx + 1)
            if normalize:
                epTitle = "%s - %s" % (show, formatSxxExx(season, num))
            else:
                epTitle = "%s - %s %s" % (show, _("Episode"), num)
            self.addVideo({"name": "category", "category": "km_video", "good_for_fav": True, "title": epTitle, "url": self._rebase(href),
                           "icon": self.getFullIconUrl(icon) or cItem.get("icon", ""), "desc": "", "s_title": show, "s_season": season, "s_episode": num,
                           "meta_type": "tv", "meta_title": cItem.get("meta_title", show)})
        # <nav class="kr-pagination"><span>1 / 2</span><a href="..&page=2#episodes">
        pager = self.cm.ph.getDataBeetwenMarkers(data, '<nav class="kr-pagination', "</nav>", False)[1]
        lastPage = int(self.cm.ph.getSearchGroups(pager, r"\d+\s*/\s*(\d+)")[0] or page)
        if lastPage > 1:
            addPagingItems(self, dict(cItem, url=url), page, page < lastPage, lastPage, self._rebase(url) + "&page={page}")

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("KirMalk.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "url": self.getFullUrl("/search.php?keywords=%s" % urllib_quote_plus(searchPattern.strip())), "page": 1})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def _siteInfo(self, data):
        box = self.cm.ph.getDataBeetwenMarkers(data, 'class="video-description', "</section>", False)[1]
        text = self.cleanHtmlStr(self.cm.ph.getSearchGroups(box, r'(?s)<div class="description-text[^"]*">(.*?)</div>')[0])
        story = self.cm.ph.getSearchGroups(text, r"قصة\s*(?:المسلسل|الفيلم|المسرحية)\s*:\s*(.+)$")[0] or text
        info = {}
        actors = self.cm.ph.getSearchGroups(text, r"(?:ابطال|بطولة)\s*(?:المسلسل|الفيلم|المسرحية)?\s*:\s*(.+?)(?:\s*قصة\s|$)")[0]
        actors = _joinActors(actors).strip(" ,")
        if actors:
            info["actors"] = actors
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story.strip(), self.getFullIconUrl(poster) if poster else "", info

    def getLinksForVideo(self, cItem):
        printDBG("KirMalk.getLinksForVideo [%s]" % cItem.get("url", ""))
        vid = self._vid(cItem.get("url", ""))
        if not vid:
            return []
        sts, data = self.getPage(self.getFullUrl("/view.php?vid=%s" % vid))
        if not sts:
            return []
        urltab = []
        block = self.cm.ph.getDataBeetwenMarkers(data, 'id="WatchServers"', "</div>", False)[1]
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, "<button", "</button>"):
            url = self.cm.ph.getSearchGroups(item, r'data-embed="([^"]+)"')[0].replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url):
                continue
            # fix 071026: the vhdup200.com CDN only accepts the Referer of the player's own domain s1.hdup400.com
            # (the embed's sharing code names it) - hd1.hdup20.com hands out the same master.m3u8, but with
            # its Referer the CDN answers 403 every time (box log + PC); the same file plays from s1.hdup400.com
            url = re.sub(r"^https?://[^/]*hdup20\.com/", "https://s1.hdup400.com/", url)
            if url in [link["url"] for link in urltab]:
                continue
            label = self.cleanHtmlStr(item)
            domain = self.cm.ph.getSearchGroups(url, r"https?://(?:www\.)?([^/:]+)")[0]
            urltab.append({"name": "%s (%s)" % (label, domain) if label else domain, "url": strwithmeta(url, {"Referer": self.getMainUrl()}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return []
        return applySidecarToLinks(urltab, buildSidecarFromItem(dict(cItem, desc=StripColorCodes(cItem.get("desc", ""))), IsSidecarEnabled()))

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("KirMalk.getArticleContent [%s]" % cItem.get("url", ""))
        meta = getItemMeta(cItem)
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            story, poster, info = self._siteInfo(data)
        if cItem.get("meta_year"):
            info.setdefault("year", cItem["meta_year"])
        return metaArticle(cItem, meta, story, poster, info, StripColorCodes(cItem.get("desc", "")))

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
        printDBG("KirMalk.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "km_categories":
            self.listCategories(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "km_series":
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
        CHostBase.__init__(self, KirMalk(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("kirmalk")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("km_video", "km_series")
