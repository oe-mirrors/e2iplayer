# -*- coding: utf-8 -*-
# Last Modified: 09.10.2026
# Coding: BY MOHAMED_OS
# 08.10.2026 - ported to the python3 framework / host standard
#   - 5tv (Arabic-subtitled Asian drama + movies, WordPress theme "5tv"): the numbered domain rotates
#     (new61.5tv.lol ...), 5tv.lol redirects to the current one -> the domain is taken from that redirect,
#     links of favourites / older lists are re-based on it
#   - the whole site sits behind a Cloudflare managed challenge (curl-impersonate does not get through
#     either): pages go through getPageCFProtection -> MyE2i solve on the box; the posters on the site's
#     own domain get the cf_clearance cookie + the solving User-Agent
#   - latest episodes / series / movies, Asian section, the site's categories (/discover/) and search,
#     First page / Jump / Next page from the site's pager
#   - series -> seasons (data-season-panel) -> episodes; movies and episodes are VIDEO rows keyed on their
#     page path (domain independent); the episode page's free servers (data-server-url) go to urlparser
#   - watched flag (series -> season -> episode), downloaded flag, favourites, name normalisation
#     ("Title (Year)", "Show - SxxExx"), sidecar, INFO via moviemeta + the site's hero/credits block
import os
import re

from Components.config import ConfigSelection, ConfigText, config, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import GetAlternativeProxyChoices, GetAlternativeProxyUrl, IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.libs.botprotection import remembered_user_agent
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetIconDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.fivetv_proxy = ConfigSelection(default="None", choices=GetAlternativeProxyChoices())
config.plugins.iptvplayer.fivetv_alt_domain = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Use proxy server:"), config.plugins.iptvplayer.fivetv_proxy))
    if config.plugins.iptvplayer.fivetv_proxy.value == "None":
        optionList.append(getConfigListEntry(_("Alternative domain:"), config.plugins.iptvplayer.fivetv_alt_domain))
    return optionList
###################################################


def gettytul():
    return "https://5tv.lol/"


# 5tv.lol redirects to the current numbered domain; new61 is the last one seen (08.10.2026)
DOMAINS = ["https://5tv.lol/", "https://new61.5tv.lol/"]
SITE_URL_RE = re.compile(r"^https?://(?:[a-z0-9-]+\.)*5tv\.lol/", re.I)
SITE_MARKER = "wp-theme-5tv"
SEASON_ORDINALS = [
    ("الأول", 1), ("الاول", 1), ("الثاني", 2), ("الثانى", 2), ("الثالث", 3), ("الرابع", 4), ("الخامس", 5),
    ("السادس", 6), ("السابع", 7), ("الثامن", 8), ("التاسع", 9), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:الموسم\s*(\d+|%s)|Season\s*(\d+))" % "|".join(o[0] for o in SEASON_ORDINALS), re.I)
EPISODE_RE = re.compile(r"(?:الحلقة|حلقة)\s*(\d+)")
# episode slugs: ".../<show>-1x28/" (season x episode) or ".../<show>-28/"
SLUG_SXE_RE = re.compile(r"-(\d+)x(\d+)/?$")
SLUG_EP_RE = re.compile(r"-(\d+)/?$")
YEAR_RE = re.compile(r"(?:^|\s|\()((?:19|20)\d{2})(?=\s|\)|$)")
DUB_RE = re.compile(r"(?:^|\s)(مدبلجة|مدبلج)(?=\s|$)")
JUNK_RE = re.compile(r"(?:^|\s)(?:مترجمة|مترجم|مدبلجة|مدبلج|اون لاين|أون لاين|مشاهدة|فيلم|مسلسل|دراما|كامل|كاملة|HD)(?=\s|$)")
# "لا بديل لها Irreplaceable — الحلقة 12": separators around the episode label (alternation: the dashes are
# multi-byte in py2)
EDGE_RE = re.compile(r"(?:^(?:\s|-|:|\||–|—)+)|(?:(?:\s|-|:|\||–|—)+$)")
LATIN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 :;,.!?'&()\-]*[A-Za-z0-9)!?]|[A-Za-z]")
CARD_HREF_RE = r'href="([^"]*/(?:series|movie|movies|episode)/[^"#]+)"'
PAGE_HREF_RE = re.compile(r'href="([^"]*(?:/page/|[?&](?:paged|page)=)(\d+)[^"]*)"')
LOCAL_PAGE_SIZE = 100


def _seasonNum(text):
    m = SEASON_RE.search(text or "")
    if not m:
        return 0
    val = m.group(1) or m.group(2)
    return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 0)


def _clean(text):
    text = JUNK_RE.sub(" ", text or "")
    return EDGE_RE.sub("", re.sub(r"\s+", " ", text))


def _latinTitle(title):
    # "لا بديل لها Irreplaceable" -> "Irreplaceable" (the metadata services know the original title)
    parts = [p.strip() for p in LATIN_RE.findall(title or "") if re.search(r"[A-Za-z]", p)]
    return max(parts, key=len) if parts else ""


def _kind(url):
    m = re.search(r"/(series|movie|movies|episode)/", url or "")
    return {"movies": "movie"}.get(m.group(1), m.group(1)) if m else ""


class FiveTV(GenericFolderWatchedScraperMixin, CBaseHostClass):
    DOMAIN_CACHE = None
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "s_title", "s_season", "s_episode",
                  "series_url", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "fivetv", "cookie": "fivetv.cookie"})
        self.MAIN_URL = None
        self.DEFAULT_ICON_URL = "file://" + GetIconDir("PlayerSelector/fivetv135.png")
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.watchedHelper = IPTVWatchedHelper("fivetv")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getProxy(self):
        return GetAlternativeProxyUrl(config.plugins.iptvplayer.fivetv_proxy.value) or None

    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        proxy = self.getProxy()
        if proxy and "http_proxy" not in addParams:
            addParams = MergeDicts(addParams, {"http_proxy": proxy})
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._rebase(baseUrl), addParams, post_data)

    def selectDomain(self):
        if FiveTV.DOMAIN_CACHE:
            self.MAIN_URL = FiveTV.DOMAIN_CACHE
            return
        domains = list(DOMAINS)
        domain = config.plugins.iptvplayer.fivetv_alt_domain.value.strip()
        if self.cm.isValidUrl(domain):
            domains.insert(0, domain.rstrip("/") + "/")
        for domain in domains:
            self.MAIN_URL = domain
            sts, data = self.getPage(domain)
            if sts and SITE_MARKER in data:
                self.MAIN_URL = self.cm.getBaseUrl(self.cm.meta.get("url", domain))
                FiveTV.DOMAIN_CACHE = self.MAIN_URL
                return
            if not sts and self.cm.meta.get("status_code") == 403:
                # the Cloudflare check was not solved - the other domains sit behind the same check
                break
        self.MAIN_URL = domains[-1]

    def _rebase(self, url):
        # urls of favourites / older lists on a previous numbered domain -> the current one
        if self.MAIN_URL is None:
            self.selectDomain()
        url = (url or "").replace("&amp;", "&").replace("&#038;", "&").strip()
        if not url.startswith("http"):
            url = CBaseHostClass.getFullUrl(self, url)
        url = SITE_URL_RE.sub(self.MAIN_URL, url)
        # Arabic slugs -> one percent-encoded form
        return urllib_quote(urllib_unquote(url), safe=":/?&=#+,;@%")

    @staticmethod
    def _path(url):
        # domain independent identity of a page ("?ftv_vip_checked=1" and friends dropped)
        url = urllib_unquote((url or "").split("?")[0])
        return re.sub(r"^https?://[^/]+", "", url).rstrip("/").lower()

    def getFullIconUrl(self, url, currUrl=None):
        # posters on the site's own domain sit behind the same Cloudflare check as the pages: the download
        # needs the cf_clearance cookie and the User-Agent that passed the check
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
            if cItem.get("category") in ("ft_video", "ft_series", "ft_season"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    @staticmethod
    def _episodeTitle(show, season, episode, label):
        if IsMediaNamingNormalized() and episode:
            return "%s - %s" % (show, formatSxxExx(season or 1, episode))
        return label or "%s - %s %s" % (show, _("Episode"), episode)

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
            if category == "ft_video":
                return "video:%s" % path
            if category == "ft_series":
                return "series:%s" % path
            if category == "ft_season":
                return "season:%s#%s" % (path, cItem.get("s_season", 1))
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
            lst(_("Latest episodes"), "/latest-episodes/"),
            lst(_("Series"), "/latest-series/"),
            lst(_("Movies"), "/latest-movies/"),
            lst(_("Asian"), "/category/%D8%A7%D8%B3%D9%8A%D9%88%D9%8A/"),
            {"category": "ft_categories", "title": _("Categories")},
        ]
        self.listsTab(menu + self.searchItems(), cItem)

    def listCategories(self, cItem):
        sts, data = self.getPage(self.getFullUrl("/discover/"))
        if not sts:
            return
        block = self.cm.ph.getDataBeetwenMarkers(data, "ftv-discover-categories", "</section>", False)[1] or data
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(block, ("<a", ">", "ftv-discover-category"), ("</a", ">")):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'(?s)<span[^>]+category__name[^>]*>(.*?)</span>')[0]) or self.cleanHtmlStr(item)
            if not href or not title or href in seen:
                continue
            seen.add(href)
            self.addDir({"name": "category", "category": "list_items", "good_for_fav": True, "title": title, "url": self._rebase(href)})

    def _cards(self, data):
        # (url, block) of every content card: <article ..> cards (home / taxonomy pages) and <a class="..card.."> tiles
        cards = []
        seen = set()
        blocks = self.cm.ph.getAllItemsBeetwenMarkers(data, "<article", "</article>")
        blocks += [b for b in self.cm.ph.getAllItemsBeetwenMarkers(data, "<a ", "</a>") if "card" in self.cm.ph.getSearchGroups(b, r'class="([^"]*)"')[0]]
        for block in blocks:
            href = self.cm.ph.getSearchGroups(block, CARD_HREF_RE)[0]
            if not href:
                continue
            path = self._path(href)
            if path in seen:
                continue
            seen.add(path)
            cards.append((self._rebase(href), block))
        return cards

    def _cardTitle(self, block):
        for pattern in (r'(?s)class="[^"]*__title[^"]*"[^>]*>(.*?)</', r"(?s)<h[23][^>]*>(.*?)</h[23]>", r'\balt="([^"]+)"', r'\btitle="([^"]+)"'):
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, pattern)[0])
            if title:
                return title
        return ""

    def _icon(self, block):
        icon = self.cm.ph.getSearchGroups(block, r'<img[^>]+?(?:data-src|data-lazy-src)="([^"]+)"')[0] or self.cm.ph.getSearchGroups(block, r'<img[^>]+?src="([^"]+)"')[0]
        if not icon or icon.startswith("data:"):
            icon = self.cm.ph.getSearchGroups(block, r"""url\(['"]?([^'")]+)""")[0]
        return self.getFullIconUrl(icon) if icon else ""

    def _addCard(self, url, block, normalize):
        kind = _kind(url)
        label = self._cardTitle(block)
        if not label:
            return False
        icon = self._icon(block)
        year = self.cm.ph.getSearchGroups(block, r'class="[^"]*year[^"]*"[^>]*>\s*((?:19|20)\d{2})')[0] or self.cm.ph.getSearchGroups(label, YEAR_RE.pattern)[0]
        badge = self.cleanHtmlStr(self.cm.ph.getSearchGroups(block, r'(?s)class="[^"]*badge--category[^"]*"[^>]*>(.*?)</')[0])
        desc = "[/br]".join(x for x in ("%s: %s" % (_("Year"), year) if year else "", "%s: %s" % (_("Category"), badge) if badge else "") if x)
        params = {"name": "category", "good_for_fav": True, "url": url, "icon": icon, "desc": desc}
        if kind == "episode":
            # the card title is the show ("سر في براغ A Secret in Prague"), the episode is in its meta line
            # ("الحلقة 83") or in the slug (".../<show>-1x28/", ".../<show>-83/")
            m = EPISODE_RE.search(label)
            show = _clean(label[:m.start()] if m else label) or label
            slug = urllib_unquote(url.split("?")[0])
            sxe = SLUG_SXE_RE.search(slug)
            episode = (m.group(1) if m else "") or (sxe.group(2) if sxe else "") or self.cm.ph.getSearchGroups(self.cleanHtmlStr(block), EPISODE_RE.pattern)[0] or self.cm.ph.getSearchGroups(slug, SLUG_EP_RE.pattern)[0]
            season = (int(sxe.group(1)) if sxe else 0) or _seasonNum(show) or 1
            show = _clean(SEASON_RE.sub(" ", show)) or show
            rawLabel = "%s - %s %s" % (label, _("Episode"), episode) if episode and not m else label
            params.update({"category": "ft_video", "title": self._episodeTitle(show, season, episode, rawLabel), "s_title": show, "s_season": season,
                           "s_episode": str(int(episode)) if episode else "", "meta_type": "tv", "meta_title": _latinTitle(show) or show})
            self.addVideo(params)
        elif kind == "movie":
            clean = _clean(re.sub(r"\(?\b%s\b\)?" % year, " ", label) if year else label) or label
            title = "%s (%s)" % (clean, year) if year else clean
            dubbed = DUB_RE.search(label)
            if dubbed:
                # the site lists the dubbed and the subtitled version of a movie side by side
                title = "%s %s" % (title, dubbed.group(1))
            params.update({"category": "ft_video", "title": title if normalize else label,
                           "meta_type": "movie", "meta_title": _latinTitle(clean) or clean, "meta_year": year})
            self.addVideo(params)
        else:
            show = _clean(label) or label
            params.update({"category": "ft_series", "title": label, "s_title": show, "s_season": _seasonNum(label) or 1,
                           "meta_type": "tv", "meta_title": _latinTitle(show) or show, "meta_year": year})
            self.addDir(params)
        return True

    def listItems(self, cItem):
        page = cItem.get("page", 1)
        url = cItem["url"]
        printDBG("FiveTV.listItems [%s]" % url)
        sts, data = self.getPage(url)
        if not sts:
            return
        # the home page nests <main> in <main> -> everything up to the footer
        main = self.cm.ph.getDataBeetwenMarkers(data, "<main", "<footer", False)[1] or data
        normalize = IsMediaNamingNormalized()
        found = 0
        for cardUrl, block in self._cards(main):
            if self._addCard(cardUrl, block, normalize):
                found += 1

        # pager: <a href="<list>/page/3/">3</a> (or ?paged=3) -> the template follows the list's own url
        firstUrl = cItem.get("first_url") or cItem["url"]
        pages = [(int(num), href) for href, num in PAGE_HREF_RE.findall(main)]
        lastPage = max([num for num, _href in pages] + [page])
        nextHref = ([href for num, href in pages if num == page + 1] or [""])[0]
        pageTpl = ""
        if nextHref and re.search(r"/page/\d+/", nextHref):
            base, sep, query = firstUrl.partition("?")
            pageTpl = re.sub(r"page/\d+/?$", "", base).rstrip("/") + "/page/{page}/" + (sep + query.replace("{", "{{").replace("}", "}}") if sep else "")
        elif nextHref:
            pageTpl = re.sub(r"([?&](?:paged|page)=)\d+", r"\g<1>{page}", self._rebase(nextHref).replace("{", "{{").replace("}", "}}"))
        listItem = dict(cItem)
        listItem.update({"category": "list_items", "first_url": firstUrl, "url": firstUrl})
        addPagingItems(self, listItem, page, bool(found) and bool(nextHref), lastPage, pageTpl)

    def _seriesPanels(self, data):
        # [(season number, panel html)] from <div class="ftv-season-panel .." data-season-panel="N">
        panels = []
        for part in re.split(r'<div[^>]+data-season-panel="', data)[1:]:
            num = self.cm.ph.getSearchGroups(part, r'^([^"]+)"')[0]
            panels.append((int(num) if num.isdigit() else len(panels) + 1, part.split("</section>")[0]))
        return panels

    def listSeries(self, cItem):
        printDBG("FiveTV.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem["url"])
        if not sts:
            return
        panels = self._seriesPanels(data)
        if not panels:
            # "no episodes yet" notice of the site
            message = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div class="ftv-series-episodes-empty"[^>]*>(.*?)</div>')[0])
            SetIPTVPlayerLastHostError(message or _("No stream available"))
            return
        if len(panels) == 1:
            self.listEpisodes(dict(cItem, s_season=panels[0][0]), data)
            return
        show = cItem.get("s_title", "") or cItem.get("title", "")
        for num, _panel in panels:
            params = dict(cItem)
            params.update({"good_for_fav": True, "category": "ft_season", "s_season": num,
                           "title": "%s - %s" % (show, formatSxxExx(num)) if IsMediaNamingNormalized() else "%s %s" % (_("Season"), num)})
            self.addDir(params)

    def listEpisodes(self, cItem, data=None):
        printDBG("FiveTV.listEpisodes [%s] [%s]" % (cItem.get("url", ""), cItem.get("s_season", "")))
        if data is None:
            sts, data = self.getPage(cItem["url"])
            if not sts:
                return
        season = cItem.get("s_season", 1)
        panel = dict(self._seriesPanels(data)).get(season, "")
        show = cItem.get("s_title", "") or cItem.get("title", "")
        episodes = []
        seen = set()
        for item in self.cm.ph.getAllItemsBeetwenMarkers(panel, ("<a", ">", "ftv-series-episode-card"), ("</a", ">")):
            href = self.cm.ph.getSearchGroups(item, r'href="([^"]+)"')[0]
            path = self._path(href)
            # every tile has a "ftv-series-episode-card__play" icon link in front of the card itself
            if not href or path in seen or "episode-card__play" in item[:200]:
                continue
            seen.add(path)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<strong[^>]*>(.*?)</strong>")[0])
            slug = urllib_unquote(href.split("?")[0])
            sxe = SLUG_SXE_RE.search(slug)
            episode = self.cm.ph.getSearchGroups(label, EPISODE_RE.pattern)[0] or (sxe.group(2) if sxe else self.cm.ph.getSearchGroups(slug, SLUG_EP_RE.pattern)[0])
            episodes.append({"name": "category", "good_for_fav": True, "category": "ft_video", "url": self._rebase(href), "icon": cItem.get("icon", ""),
                             "title": self._episodeTitle(show, season, episode, "%s - %s" % (show, label) if label else show),
                             "desc": cItem.get("desc", ""), "series_url": cItem["url"], "s_title": show, "s_season": season,
                             "s_episode": str(int(episode)) if episode else "", "meta_type": "tv",
                             "meta_title": cItem.get("meta_title", show), "meta_year": cItem.get("meta_year", "")})
        page = cItem.get("page", 1)
        start = (page - 1) * LOCAL_PAGE_SIZE
        for params in episodes[start:start + LOCAL_PAGE_SIZE]:
            self.addVideo(params)
        if len(episodes) > LOCAL_PAGE_SIZE:
            lastPage = (len(episodes) + LOCAL_PAGE_SIZE - 1) // LOCAL_PAGE_SIZE
            addPagingItems(self, dict(cItem, category="ft_season"), page, page < lastPage, lastPage)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("FiveTV.listSearchResult [%s]" % searchPattern)
        # the site's search form: GET /search/?q=<words>
        url = self.getFullUrl("/search/?q=%s" % urllib_quote_plus(searchPattern.strip()))
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "page": 1, "url": url, "first_url": url})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("FiveTV.getLinksForVideo [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return []
        # <button class="ftv-watch-tab .." data-server-url="<embed>" data-server-vip="0"><span>سيرفر 1</span>
        # <strong>71Stream</strong><small>1080p</small></button>
        tabs = self.cm.ph.getDataBeetwenMarkers(data, "ftv-watch-tabs", "ftv-player-frame", False)[1]
        urltab = []
        vipOnly = False
        for item in self.cm.ph.getAllItemsBeetwenMarkers(tabs, "<button", "</button>"):
            url = self.cm.ph.getSearchGroups(item, r'data-server-url="([^"]+)"')[0].replace("&amp;", "&").strip()
            if url.startswith("//"):
                url = "https:" + url
            if not self.cm.isValidUrl(url):
                continue
            if self.cm.ph.getSearchGroups(item, r'data-server-vip="([^"]*)"')[0] not in ("", "0"):
                # VIP servers need a paid account on the site
                vipOnly = True
                continue
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<strong[^>]*>(.*?)</strong>")[0])
            quality = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r"(?s)<small[^>]*>(.*?)</small>")[0])
            name = " ".join(x for x in (label or self.up.getHostName(url), quality) if x)
            urltab.append({"name": name, "url": strwithmeta(url, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            iframe = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+class="ftv-player-iframe"[^>]+src="([^"]+)"')[0]
            if self.cm.isValidUrl(iframe):
                urltab.append({"name": self.up.getHostName(iframe), "url": strwithmeta(iframe, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            SetIPTVPlayerLastHostError(_("No stream available") + (" (VIP)" if vipOnly else ""))
            return []
        story = self._siteInfo(data)[0]
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), story))

    def getVideoLinks(self, videoUrl):
        printDBG("FiveTV.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def _chips(self, data, kind):
        values = [self.cleanHtmlStr(c) for c in re.findall(r'(?s)class="ftv-content-chip ftv-content-chip--%s"[^>]*>(.*?)</a>' % kind, data)]
        return ", ".join(v for v in values if v)

    def _siteInfo(self, data):
        story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)class="ftv-content-hero__description"[^>]*>(.*?)</div>')[0])
        if not story:
            story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta (?:property="og:description"|name="description") content="([^"]+)"')[0])
        info = {}
        year = self.cm.ph.getSearchGroups(data, r'href="[^"]*/year/((?:19|20)\d{2})/')[0]
        if year:
            info["year"] = year
        for key, kind in (("category", "category"), ("status", "status"), ("genres", "genre")):
            value = self._chips(data, kind)
            if value:
                info[key] = value
        for key, value in re.findall(r'(?s)class="ftv-content-chip ftv-content-chip--secondary"\s+href="[^"]*/(country|language)/[^"]*"[^>]*>(.*?)</a>', data):
            info.setdefault(key, self.cleanHtmlStr(value))
        # <div class="ftv-credits-group"><strong class="ftv-credits-label">إخراج</strong> (directing) / طاقم التمثيل (cast)
        for group in data.split('class="ftv-credits-group"')[1:]:
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(group, r'(?s)class="ftv-credits-label"[^>]*>(.*?)</strong>')[0])
            names = [self.cleanHtmlStr(n) for n in re.findall(r"(?s)<a[^>]*>\s*<strong[^>]*>(.*?)</strong>", group.split("</section>")[0])]
            names = ", ".join(n for n in names[:8] if n)
            if names:
                info.setdefault("directors" if "إخراج" in label else "cast", names)
        poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
        return story, self.getFullIconUrl(poster) if poster else "", info

    def getArticleContent(self, cItem):
        printDBG("FiveTV.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        if cItem.get("meta_type") and cItem.get("meta_title"):
            try:
                # Arabic-only titles -> no IMDb/Cinemeta/OMDb (they answer with unrelated English hits)
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
        printDBG("FiveTV.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "ft_categories":
            self.listCategories(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category == "ft_series":
            self.listSeries(self.currItem)
        elif category == "ft_season":
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
        CHostBase.__init__(self, FiveTV(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("fivetv")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("ft_video", "ft_series", "ft_season")
