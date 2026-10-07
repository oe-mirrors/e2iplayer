# -*- coding: utf-8 -*-
# Last Modified: 06.10.2026
# 03.10.2026 - revived for the redesigned hd1.brstej.com (Brstej / Prestige)
#   Rewrite against the current site (based on the host by Mohamed Elsafty):
#   - categories read live from the site menu (no hard-coded yearly slugs), Ramadan seasons grouped;
#     "Latest additions" (new-videos.php), all series (moslslat.php), search via search.php
#   - lists parse the new card markup (pmc / pcg / pln / prs / psd cards); a category with series
#     gets a "series of this category" folder; paging via iptvpaging (First / Jump / Next (n/last))
#   - series1.php?id=N -> seasons -> episodes; movies and episodes are VIDEO rows keyed on their
#     watch.php?vid= page; the hoster embeds (play.php) are fetched in getLinksForVideo
#   - film77 / vood78 / hd-vk / hdupNNN embeds unpacked here (no form + sleep any more),
#     everything else (ok.ru, vk ...) goes to urlparser
#   - watched flag (video:/series:/season: keys), downloaded flag, favourites, sidecar,
#     name normalisation ("Title (Year)", "Show - SxxExx"), INFO via moviemeta + the site's story
# 05.10.2026 - "No items found" marker, episode / label of search hits, INFO shows
#   the upload date and keeps the site's categories / duration (moviemeta no longer overwrites them)
# 06.10.2026 - Ramadan 2021 / 2022 (filed by the site under "Brstej series") go to "Ramadan series",
#   INFO asks only TMDb / TVmaze for Arabic-only titles (faster, no unrelated IMDb hits), then retries
#   without a season subtitle / number ("المداح 2 - ...", "المداح 3" -> "المداح")
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.jsunpack import get_packed_data
from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    # no host settings - the BLUE button (host settings) needs the function anyway
    return []


def gettytul():
    return "https://hd1.brstej.com/"


# Arabic ordinals used in season labels ("الموسم الثاني"), compound ones first
SEASON_ORDINALS = [
    ("الحادي عشر", 11), ("الثاني عشر", 12), ("الثالث عشر", 13), ("الرابع عشر", 14), ("الخامس عشر", 15),
    ("الأولى", 1), ("الاولى", 1), ("الأول", 1), ("الاول", 1), ("الثانية", 2), ("الثاني", 2), ("الثانى", 2),
    ("الثالثة", 3), ("الثالث", 3), ("الرابعة", 4), ("الرابع", 4), ("الخامسة", 5), ("الخامس", 5), ("السادسة", 6),
    ("السادس", 6), ("السابعة", 7), ("السابع", 7), ("الثامنة", 8), ("الثامن", 8), ("التاسعة", 9), ("التاسع", 9),
    ("العاشرة", 10), ("العاشر", 10),
]
SEASON_RE = re.compile(r"(?:^|\s)(?:الموسم|الجزء)\s*(\d+|%s)(?=\s|$)" % "|".join(o[0] for o in SEASON_ORDINALS))
EPISODE_RE = re.compile(r"(?:^|\s)(?:الحلقة|حلقة)\s*(\d+)")
YEAR_RE = re.compile(r"(?:^|\s)\(?((?:19|20)\d{2})\)?(?=\s|$)")
# site words that do not belong into a title / file name (only removed when normalising)
JUNK_RE = re.compile(r"(?:^|\s)(?:مشاهدة|فيلم|مسلسل|مترجم|مترجمة|اون لاين|أون لاين|اونلاين|كامل|كاملة|بجودة عالية|HD|FHD|HDTV|WEB-DL)(?=\s|$)", re.I)
DUB_WORD = "مدبلج"
# embeds unpacked by the host itself (packed JWPlayer pages), anything else -> urlparser
PACKED_EMBED_RE = re.compile(r"https?://(?:[^/]+\.)?(?:film77\.xyz|vood78\.xyz|hd-vk\.com|hdup\d*\.com)/", re.I)
# Ramadan categories by their slug too: the site files 2021 / 2022 under "Brstej series", 2021 without "رمضان"
RAMADAN_SLUG_RE = re.compile(r"[?&]cat=ra?ma?d?a?n?\d", re.I)
CARD_RE = re.compile(r'(?s)<article class="(?:pmc|pln|prs|psd)-card">.*?</article>|<div class="thumbnail pcg-card">.*?</li>|<a class="pcg-series-card".*?</a>')


class Brstej(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ("name", "category", "type", "url", "title", "icon", "desc", "menu_key", "s_title", "s_season", "s_episode",
                  "season_num", "meta_type", "meta_title", "meta_year")

    def __init__(self):
        CBaseHostClass.__init__(self, {"history": "brstej", "cookie": "brstej.cookie"})
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = "https://hd1.brstej.com/22.png"
        self.HEADER = self.cm.getDefaultHeader(browser="chrome")
        self.defaultParams = {"header": self.HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": self.COOKIE_FILE}
        self.menuCache = None
        self.watchedHelper = IPTVWatchedHelper("brstej")
        self.wfInitFolderCache()

    ###################################################
    # helpers
    ###################################################
    def getPage(self, baseUrl, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        addParams["cloudflare_params"] = {"cookie_file": self.COOKIE_FILE, "User-Agent": self.HEADER.get("User-Agent")}
        return self.cm.getPageCFProtection(self._canonUrl(baseUrl), addParams, post_data)

    def _canonUrl(self, url):
        # absolute, ASCII, and the current page names (the old ones only answer with a 301)
        url = (url or "").replace("&amp;", "&").strip()
        if not url:
            return ""
        url = self.getFullUrl(url)
        url = re.sub(r"/category(?:818)?\.php", "/cat03.php", url)
        url = re.sub(r"/cat67\.php", "/cat03.php", url)
        url = re.sub(r"/newvideos?\.php", "/new-videos.php", url)
        url = url.replace("/moslsalat.php", "/moslslat.php").replace("/view-serie.php", "/series1.php")
        url = url.split("#", 1)[0]
        try:
            if any(ord(c) > 127 for c in url):
                url = urllib_quote(url, safe=":/?&=%#+,;@")
        except Exception:
            printExc()
        return url

    @staticmethod
    def _pageTpl(url):
        url = re.sub(r"([?&])page=\d+&?", r"\1", url).rstrip("?&")
        return url + ("&" if "?" in url else "?") + "page={page}"

    @staticmethod
    def _vid(url):
        m = re.search(r"[?&]vid=([^&#]+)", url or "")
        return m.group(1) if m else ""

    @staticmethod
    def _seriesId(url):
        m = re.search(r"(?:series1|view-serie)\.php\?id=(\d+)", url or "")
        return m.group(1) if m else ""

    @staticmethod
    def _clean(text):
        text = JUNK_RE.sub(" ", text or "")
        return re.sub(r"\s+", " ", text).strip(" -:|")

    @staticmethod
    def _seasonNum(val):
        return int(val) if val.isdigit() else dict(SEASON_ORDINALS).get(val, 1)

    def _splitShow(self, label):
        # "مسلسل X الموسم الثاني الحلقة 5 الخامسة مترجمة" -> ("X", 2, "5"); no episode -> ("", 0, "")
        m = EPISODE_RE.search(label or "")
        if not m:
            return "", 0, ""
        show = self._clean(label[:m.start()])
        season = 1
        s = SEASON_RE.search(show)
        if s:
            season = self._seasonNum(s.group(1))
            show = (show[:s.start()] + " " + show[s.end():]).strip()
        return re.sub(r"\s+", " ", show).strip(" -:|"), season, m.group(1)

    def _splitMovie(self, label):
        # "مشاهدة فيلم Union County 2026 مترجم اون لاين HD" -> ("Union County", "2026")
        title = self._clean(label)
        year = ""
        m = None
        for m in YEAR_RE.finditer(title):
            pass
        if m and m.start() > 0:
            year = m.group(1)
            title = (title[:m.start()] + " " + title[m.end():]).strip()
        return re.sub(r"\s+", " ", title).strip(" -:|"), year

    @staticmethod
    def _metaTitle(title):
        return re.sub(r"\s+", " ", (title or "").replace(DUB_WORD, " ")).strip()

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ""
            category = cItem.get("category", "")
            url = cItem.get("url", "")
            if category == "brstej_video":
                vid = self._vid(url)
                return ("video:%s" % vid) if vid else ""
            if category in ("brstej_series", "brstej_season"):
                sid = self._seriesId(url)
                if not sid:
                    return ""
                if category == "brstej_season":
                    return "season:%s:%s" % (sid, cItem.get("season_num", 1))
                return "series:%s" % sid
        except Exception:
            printExc()
        return ""

    def getFavouriteData(self, cItem):
        try:
            if cItem.get("category", "") in ("brstej_video", "brstej_series", "brstej_season", "list_items", "brstej_submenu"):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # menus
    ###################################################
    def _loadMenu(self):
        # [(title, url, [(title, url), ...]), ...] from the site's side menu
        if self.menuCache is not None:
            return self.menuCache
        menu = []
        ramadan = []
        sts, data = self.getPage(self.getFullUrl("/home03"))
        if not sts:
            return menu
        block = self.cm.ph.getSearchGroups(data, r'(?s)<ul class="psm-categories">(.*?)<details')[0]
        if not block:
            block = self.cm.ph.getSearchGroups(data, r'(?s)<ul class="psm-categories">(.*)</ul>')[0]
        for m in re.finditer(r'(?s)<li class="sub_ca"[^>]*>\s*<a href="([^"]+)"[^>]*>\s*<b>(.*?)</b>.*?</a>(.*?)(?=<li class="sub_ca"[^>]*>\s*<a href="[^"]+"[^>]*>\s*<b>|$)', block):
            title = self.cleanHtmlStr(m.group(2))
            url = self._canonUrl(m.group(1))
            if not title or not url:
                continue
            children = []
            for curl, ctitle in re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', m.group(3)):
                ctitle = self.cleanHtmlStr(ctitle)
                if not ctitle:
                    continue
                curl = self._canonUrl(curl)
                if self._isRamadan(ctitle, curl):
                    # a Ramadan season inside another menu -> the "Ramadan series" folder
                    if "رمضان" not in ctitle:
                        year = self.cm.ph.getSearchGroups(ctitle, r"((?:19|20)\d{2})")[0]
                        ctitle = ("مسلسلات رمضان %s" % year) if year else ctitle
                    ramadan.append((ctitle, curl, []))
                else:
                    children.append((ctitle, curl))
            menu.append((title, url, children))
        menu.extend(ramadan)
        if menu:
            self.menuCache = menu
        return menu

    @staticmethod
    def _isRamadan(title, url):
        return "رمضان" in title or bool(RAMADAN_SLUG_RE.search(url or ""))

    def listMainMenu(self, cItem):
        printDBG("Brstej.listMainMenu")
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": _("Recently added"), "url": self.getFullUrl("/new-videos.php")})
        self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": _("All series"), "url": self.getFullUrl("/moslslat.php")})
        ramadan = False
        for title, url, children in self._loadMenu():
            if self._isRamadan(title, url) and not children:
                ramadan = True
                continue
            if children:
                self.addDir({"name": "category", "good_for_fav": True, "category": "brstej_submenu", "title": title, "url": url, "menu_key": url})
            else:
                self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": url})
        if ramadan:
            self.addDir({"name": "category", "good_for_fav": True, "category": "brstej_submenu", "title": _("Ramadan series"), "url": self.getFullUrl("/cat03.php"), "menu_key": "ramadan"})
        self.listsTab(self.searchItems(), {"name": "category"})

    def listSubMenu(self, cItem):
        printDBG("Brstej.listSubMenu [%s]" % cItem.get("menu_key", ""))
        key = cItem.get("menu_key", "")
        entries = []
        for title, url, children in self._loadMenu():
            if key == "ramadan":
                if self._isRamadan(title, url) and not children:
                    entries.append((title, url))
            elif url == key:
                entries = [(_("All"), url)] + children
                break
        if key == "ramadan":
            entries.sort(key=lambda e: e[0], reverse=True)
        for title, url in entries:
            self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title, "url": url})

    ###################################################
    # lists
    ###################################################
    def _videoParams(self, label, url, icon, desc, isMovie, normalize):
        params = {"name": "category", "good_for_fav": True, "category": "brstej_video", "url": url, "icon": icon, "desc": desc, "title": label}
        show, season, episode = self._splitShow(label)
        if show and episode:
            params.update({"s_title": show, "s_season": season, "s_episode": episode,
                           "meta_type": "tv", "meta_title": self._metaTitle(show), "meta_year": ""})
            if normalize:
                params["title"] = "%s - %s" % (show, formatSxxExx(season, episode))
        elif isMovie or "فيلم" in label:
            title, year = self._splitMovie(label)
            if title:
                params.update({"meta_type": "movie", "meta_title": self._metaTitle(title), "meta_year": year})
                if normalize:
                    params["title"] = ("%s (%s)" % (title, year)) if year else title
        elif normalize:
            params["title"] = self._clean(label) or label
        return params

    def _parseCards(self, data, seen, normalize):
        for card in CARD_RE.findall(data):
            href = self.cm.ph.getSearchGroups(card, r'href="([^"]*(?:watch\.php\?vid=|series1\.php\?id=)[^"]+)"')[0]
            url = self._canonUrl(href)
            if not url or url in seen:
                continue
            seen.add(url)
            label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<h[34][^>]*>(.*?)</h[34]>')[0])
            if not label:
                label = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'title="([^"]+)"')[0])
            if not label:
                continue
            icon = self.cm.ph.getSearchGroups(card, r'<img[^>]+src="([^"]+)"')[0]
            icon = self.getFullIconUrl(icon) if icon and not icon.startswith("data:") else ""
            if "series1.php" in url:
                show = self._clean(label)
                s = SEASON_RE.search(show)
                season = self._seasonNum(s.group(1)) if s else 0
                if s:
                    show = (show[:s.start()] + " " + show[s.end():]).strip()
                self.addDir({"name": "category", "good_for_fav": True, "category": "brstej_series", "title": label, "url": url, "icon": icon,
                             "s_title": show or label, "s_season": season, "meta_type": "tv", "meta_title": self._metaTitle(show or label), "meta_year": ""})
                continue
            fields = []
            duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<span class="(?:pmc|pln|prs)-duration"[^>]*>(.*?)</span>')[0] or
                                         self.cm.ph.getSearchGroups(card, r'(?s)<span class="pm-label-duration"[^>]*>(.*?)</span>')[0])
            if duration:
                fields.append("%s: %s" % (_("Duration"), duration))
            category = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)class="(?:pmc-category-link|pln-category)"[^>]*>(.*?)</a>')[0])
            if category:
                fields.append(category)
            # search hits (prs cards): episode number and the site's badge
            episode = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<span class="prs-episode"[^>]*>(.*?)</span>')[0])
            if episode:
                fields.append("%s: %s" % (_("Episode"), episode))
            badge = self.cleanHtmlStr(self.cm.ph.getSearchGroups(card, r'(?s)<span class="prs-label"[^>]*>(.*?)</span>')[0])
            if badge:
                fields.append(badge)
            self.addVideo(self._videoParams(label, url, icon, " | ".join(fields), "pmc-card" in card, normalize))

    def _lastPage(self, data, page):
        # (hasNext, lastPage) from the pagination block of the page
        block = self.cm.ph.getSearchGroups(data, r'(?s)(<nav class="[a-z]+-(?:pagination|pages)".*?</nav>)')[0]
        pages = [int(p) for p in re.findall(r"[?&](?:amp;)?page=(\d+)", block)]
        lastPage = max(pages) if pages else 0
        return lastPage > page, (lastPage if lastPage >= page else 0)

    def listItems(self, cItem):
        printDBG("Brstej.listItems [%s] page[%s]" % (cItem.get("url", ""), cItem.get("page", 1)))
        page = int(cItem.get("page", 1) or 1)
        url = self._canonUrl(cItem.get("url", ""))
        sts, data = self.getPage(url)
        if not sts:
            return
        # the movies landing page (one row per sub category) -> its full, paged list
        allUrl = self.cm.ph.getSearchGroups(data, r'<a class="pmc-all" href="([^"]+)"')[0]
        if allUrl and "pmc-pagination" not in data:
            url = self._canonUrl(allUrl)
            sts, data = self.getPage(url)
            if not sts:
                return
        normalize = IsMediaNamingNormalized()
        # a series category page: "series of the category" folder + the episodes grid only
        # (the featured / series panels above it repeat the same videos)
        if 'id="pm-grid"' in data:
            if page == 1 and "pcg-series-panel" in data and "type=series" not in url:
                allSeries = self.cm.ph.getSearchGroups(data, r'<a class="pcg-view-all" href="([^"]+)"')[0]
                if allSeries:
                    title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)id="pcg-series-title">(.*?)</h2>')[0]) or _("Series")
                    self.addDir({"name": "category", "good_for_fav": True, "category": "list_items", "title": title,
                                 "url": self._canonUrl(allSeries), "icon": cItem.get("icon", "")})
            data = self.cm.ph.getSearchGroups(data, r'(?s)(<ul[^>]+id="pm-grid".*?</ul>)')[0] + self.cm.ph.getSearchGroups(data, r'(?s)(<nav class="pcg-pagination".*?</nav>)')[0]
        seen = set()
        before = len(self.currList)
        self._parseCards(data, seen, normalize)
        if len(self.currList) == before:
            if not self.currList:
                # empty category / page or no search hits: a marker instead of an empty list
                self.addMarker({"title": _("No items found"), "desc": ""})
            return
        hasNext, lastPage = self._lastPage(data, page)
        addPagingItems(self, cItem, page, hasNext, lastPage, self._pageTpl(url))

    def listSeries(self, cItem):
        printDBG("Brstej.listSeries [%s]" % cItem.get("url", ""))
        sts, data = self.getPage(cItem.get("url", ""))
        if not sts:
            return
        seasons = re.findall(r'(?s)<section class="pds-season" id="pds-season-(\d+)"[^>]*>(.*?)</section>', data)
        if len(seasons) > 1 and cItem.get("category") != "brstej_season":
            for num, body in seasons:
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)<h3>(.*?)</h3>')[0]) or ("%s %s" % (_("Season"), num))
                count = self.cleanHtmlStr(self.cm.ph.getSearchGroups(body, r'(?s)</h3>\s*<span>(.*?)</span>')[0])
                params = dict(cItem)
                params.update({"good_for_fav": True, "category": "brstej_season", "title": title, "season_num": int(num), "desc": count})
                self.addDir(params)
            return
        wanted = str(cItem.get("season_num", "")) if cItem.get("category") == "brstej_season" else ""
        show = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<h1 id="pds-title">(.*?)</h1>')[0]) or cItem.get("title", "")
        showClean = self._clean(show)
        s = SEASON_RE.search(showClean)
        nameSeason = 0
        if s:
            nameSeason = self._seasonNum(s.group(1))
            showClean = (showClean[:s.start()] + " " + showClean[s.end():]).strip()
        showClean = re.sub(r"\s+", " ", showClean) or show
        normalize = IsMediaNamingNormalized()
        seen = set()
        for num, body in seasons:
            if wanted and num != wanted:
                continue
            # a single section "الموسم 1" of a series whose name carries the season ("X الموسم 3")
            season = nameSeason if (nameSeason and len(seasons) == 1) else int(num)
            for art in re.findall(r'(?s)<article class="pds-episode".*?</article>', body):
                m = re.search(r'(?s)<h4><a href="([^"]+)"([^>]*)>(.*?)</a>', art)
                if not m:
                    continue
                url = self._canonUrl(m.group(1))
                if not url or url in seen:
                    continue
                seen.add(url)
                full = self.cleanHtmlStr(self.cm.ph.getSearchGroups(m.group(2), r'title="([^"]+)"')[0])
                label = self.cleanHtmlStr(m.group(3))
                epNum = self.cm.ph.getSearchGroups(label, r"(\d+)")[0] or self._splitShow(full)[2]
                icon = self.cm.ph.getSearchGroups(art, r'<img[^>]+src="([^"]+)"')[0]
                params = {"name": "category", "good_for_fav": True, "category": "brstej_video", "url": url,
                          "icon": self.getFullIconUrl(icon) if icon else cItem.get("icon", ""), "desc": label,
                          "title": full or label, "s_title": showClean, "s_season": season, "s_episode": epNum,
                          "meta_type": "tv", "meta_title": self._metaTitle(showClean), "meta_year": ""}
                if normalize and epNum:
                    params["title"] = "%s - %s" % (showClean, formatSxxExx(season, epNum))
                self.addVideo(params)
        if not self.currList:
            self.addMarker({"title": _("No items found"), "desc": ""})

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Brstej.listSearchResult [%s]" % searchPattern)
        cItem = dict(cItem)
        cItem.update({"category": "list_items", "page": 1, "url": self.getFullUrl("/search.php?keywords=%s" % urllib_quote_plus(searchPattern))})
        self.listItems(cItem)

    ###################################################
    # links
    ###################################################
    def getLinksForVideo(self, cItem):
        printDBG("Brstej.getLinksForVideo [%s]" % cItem.get("url", ""))
        vid = self._vid(cItem.get("url", ""))
        if not vid:
            return []
        watchUrl = self.getFullUrl("/watch.php?vid=%s" % vid)
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=watchUrl)
        sts, data = self.getPage(self.getFullUrl("/play.php?vid=%s" % vid), params)
        if not sts:
            return []
        if "watchButton" not in data:
            # merged duplicates: play.php?vid=old answers with a 301 to the watch page of the new vid
            newVid = self.cm.ph.getSearchGroups(data, r"play\.php\?vid=([^\"'&#]+)")[0]
            if newVid and newVid != vid:
                sts, data = self.getPage(self.getFullUrl("/play.php?vid=%s" % newVid), params)
                if not sts:
                    return []
        urltab = []
        seen = set()
        for button in re.findall(r"(?s)<button[^>]+watchButton[^>]*>.*?</button>", data):
            embed = self.cm.ph.getSearchGroups(button, r'data-embed-url="([^"]+)"')[0].strip()
            if embed.startswith("//"):
                embed = "https:" + embed
            if not self.cm.isValidUrl(embed) or embed in seen:
                continue
            seen.add(embed)
            name = self.cleanHtmlStr(button) or ("%s %d" % (_("Server"), len(urltab) + 1))
            host = self.cm.ph.getSearchGroups(embed, r"https?://(?:www\.)?([^/]+)")[0].split(".")
            tag = host[-2] if len(host) >= 2 else ""
            urltab.append({"name": ("%s [%s]" % (name, tag)) if tag else name, "url": strwithmeta(embed, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        if not urltab:
            embed = self.cm.ph.getSearchGroups(data, r'<iframe[^>]+src="([^"]+)"')[0].strip()
            if self.cm.isValidUrl(embed):
                urltab.append({"name": "%s 1" % _("Server"), "url": strwithmeta(embed, {"Referer": self.MAIN_URL}), "need_resolve": 1})
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def _resolvePackedEmbed(self, embedUrl):
        # film77 / vood78 / hd-vk / hdupNNN: JWPlayer setup inside eval(function(p,a,c,k,e,d)...)
        urltab = []
        origin = self.cm.ph.getSearchGroups(embedUrl, r"(https?://[^/]+)")[0]
        params = dict(self.defaultParams)
        params["header"] = dict(self.HEADER, Referer=self.MAIN_URL)
        sts, data = self.getPage(embedUrl, params)
        if not sts:
            return urltab
        try:
            unpacked = get_packed_data(data)
        except Exception:
            printExc()
            unpacked = ""
        script = (unpacked or "") + data
        meta = {"Referer": origin + "/", "Origin": origin, "User-Agent": self.HEADER.get("User-Agent")}
        subtitles = []
        for sub, label in re.findall(r'file\s*:\s*"([^"]+\.(?:vtt|srt)[^"]*)"[^}]*?label\s*:\s*"([^"]*)"', script):
            sub = sub.replace("\\/", "/")
            if self.cm.isValidUrl(sub) and "thumbnails" not in sub:
                subtitles.append({"title": label or "ar", "url": sub, "lang": "ar", "format": "vtt" if ".vtt" in sub else "srt"})
        if subtitles:
            meta["external_sub_tracks"] = subtitles
        seen = set()
        for url in re.findall(r'["\'](https?://[^"\']+?\.(?:m3u8|mp4)(?:\?[^"\']*)?)["\']', script):
            url = url.replace("\\/", "/")
            if url in seen:
                continue
            seen.add(url)
            if ".m3u8" in url:
                hlsMeta = dict(meta, iptv_proto="m3u8")
                variants = []
                try:
                    variants = getDirectM3U8Playlist(strwithmeta(url, hlsMeta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999)
                except Exception:
                    printExc()
                if variants:
                    urltab.extend(variants)
                else:
                    urltab.append({"name": "HLS", "url": strwithmeta(url, hlsMeta), "need_resolve": 0})
            else:
                urltab.append({"name": "MP4", "url": strwithmeta(url, dict(meta)), "need_resolve": 0})
        return urltab

    def getVideoLinks(self, videoUrl):
        printDBG("Brstej.getVideoLinks [%s]" % videoUrl)
        if not self.cm.isValidUrl(videoUrl):
            return []
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        links = []
        if PACKED_EMBED_RE.match(videoUrl):
            links = self._resolvePackedEmbed(videoUrl)
        if not links:
            links = self.up.getVideoLinkExt(videoUrl)
        return decorateResolvedLinkItems(links, sidecar)

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Brstej.getArticleContent [%s]" % cItem.get("url", ""))
        meta = {}
        # Arabic-only titles (Ramadan / Arabic series): only TMDb (translated titles) and TVmaze (alternative
        # names) can find them, IMDb / Cinemeta / OMDb only made INFO slow and gave unrelated hits
        if cItem.get("meta_type") and cItem.get("meta_title"):
            skip = () if isLatinTitle(cItem["meta_title"]) else LATIN_ONLY
            try:
                title = cItem["meta_title"]
                meta = getMeta(cItem["meta_type"], title, cItem.get("meta_year", ""), skip)
                if not meta and skip:
                    # "المداح 2 - اسطورة الوادي" / "المداح 3": a later season with its own subtitle / number,
                    # the show is the part before (TVmaze knows "المداح" only)
                    tried = [title]
                    base = title.split(" - ", 1)[0].strip()
                    for alt in (base, re.sub(r"\s+\d{1,2}$", "", base)):
                        if alt and alt not in tried and not meta:
                            tried.append(alt)
                            meta = getMeta(cItem["meta_type"], alt, cItem.get("meta_year", ""), skip)
            except Exception:
                printExc()
        story, poster, info = "", "", {}
        sts, data = self.getPage(cItem.get("url", ""))
        if sts:
            poster = self.cm.ph.getSearchGroups(data, r'<meta property="og:image" content="([^"]+)"')[0]
            if "pds-hero" in data:
                story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<p class="pds-description">(.*?)</p>')[0])
                hero = self.cm.ph.getSearchGroups(data, r'(?s)<section class="pds-hero"(.*?)</section>')[0]
                if not poster:
                    poster = self.cm.ph.getSearchGroups(hero, r'<img[^>]+src="([^"]+)"')[0]
                genre = self.cleanHtmlStr(self.cm.ph.getSearchGroups(hero, r'(?s)class="pds-category"[^>]*>(.*?)</a>')[0])
                if genre:
                    info["categories"] = genre
                extra = [self.cleanHtmlStr(x) for x in re.findall(r'(?s)<span>(.*?)</span>', self.cm.ph.getSearchGroups(hero, r'(?s)<div class="pds-meta">(.*?)</div>')[0])]
                if extra:
                    info["episodes"] = ", ".join([x for x in extra if x])
            else:
                story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<div id="pwr-description-copy"[^>]*>(.*?)</div>')[0])
                duration = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<span class="pwu-duration"[^>]*>(.*?)</span>')[0])
                if duration:
                    info["duration"] = duration
                cats = self.cm.ph.getSearchGroups(data, r'(?s)<dt>الأقسام</dt>\s*<dd>(.*?)</dd>')[0]
                genres = [self.cleanHtmlStr(g) for g in re.findall(r"(?s)<a[^>]*>(.*?)</a>", cats)]
                if any(genres):
                    info["categories"] = ", ".join([g for g in genres if g])
                # upload date: <time datetime="2026-05-20T02:42:51+0300">أضيفت منذ 4 شهور</time>
                added = self.cm.ph.getSearchGroups(data, r'<time[^>]+datetime="(\d{4}-\d{2}-\d{2})')[0] or \
                    self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'(?s)<time[^>]*>(.*?)</time>')[0])
                if added:
                    info["broadcast"] = added
            if not story:
                story = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, r'<meta name="description" content="([^"]*)"')[0])
        # the site's own values (this video's duration, its categories) win over the moviemeta ones,
        # the moviemeta genres stay as a separate line
        siteInfo, info = info, {}
        if cItem.get("meta_year"):
            info["year"] = cItem["meta_year"]
        info.update(meta.get("info", {}))
        info.update(siteInfo)
        plot = meta.get("plot", "")
        text = plot or story or cItem.get("desc", "")
        if plot and story and story != plot:
            text = "%s[/br][/br]%s" % (plot, story)
        icon = meta.get("poster") or (self.getFullIconUrl(poster) if poster else "") or cItem.get("icon", "")
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
        printDBG("Brstej.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMainMenu({"name": "category"})
        elif category == "brstej_submenu":
            self.listSubMenu(self.currItem)
        elif category == "list_items":
            self.listItems(self.currItem)
        elif category in ("brstej_series", "brstej_season", "explore_item"):
            # explore_item: favourites of the old host (series pages)
            self.listSeries(self.currItem)
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
        CHostBase.__init__(self, Brstej(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("brstej")

    def withArticleContent(self, cItem):
        return cItem.get("category", "") in ("brstej_video", "brstej_series", "brstej_season")
